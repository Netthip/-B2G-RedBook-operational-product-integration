#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
leak_check.py — ตรวจว่าไฟล์ที่จะเผยแพร่ไม่มีข้อมูลที่ห้ามออกนอกเครื่อง

รุ่น leak-check-0.2.0 — แก้ BLOCKER 2 ของ Bo (#13)

* **fail-closed** — ถ้าโหลดไฟล์รูปแบบ local ไม่ได้ หรือหมวด A–H ไม่ครบ
  ⇒ exit 3 `INCOMPLETE` **ไม่ใช่ PASSED** (รุ่นเดิมคืน PASSED ทั้งที่ไม่มีรูปแบบให้ตรวจ)
* **ไม่พิมพ์ข้อความที่ตรงเงื่อนไข** — รายงานแค่ ไฟล์ · หมวด · เลขบรรทัด · จำนวน
  (รุ่นเดิมพิมพ์ค่าที่ hit ออก stdout ⇒ ย้ายข้อมูลต้องห้ามไปอยู่ใน log/issue)
  ต้องการดูค่าจริงบนเครื่องตัวเอง ใช้ ``--reveal`` เท่านั้น
* **ชุดตรวจพื้นฐานในตัว** (หมวด `Z*`) ทำงานเสมอโดยไม่พึ่งไฟล์ภายนอก —
  จับเฉพาะรูปแบบทั่วไปที่ไม่ใช่คำต้องห้ามเฉพาะโครงการ
* ``--self-test`` ตรวจตัวเองว่าสามข้อข้างบนทำงานจริง

exit code: 0 = ผ่าน (ตรวจครบ 0 hit) · 1 = พบ hit · 2 = ใช้ผิด/ไม่มีไฟล์ ·
3 = ตรวจไม่ครบ (รูปแบบ local โหลดไม่ได้/ไม่ครบ A–H) — ไม่ใช่ใบอนุญาตเผยแพร่

🔴 แม้ exit 0 ก็เป็นแค่ "ไม่พบรูปแบบที่ตรวจ" ไม่ใช่หลักฐานว่าปลอดการเปิดเผย
(Bo · BLOCKER 1: fingerprint/การประกอบข้อมูลหลายชิ้น ตัวตรวจนี้มองไม่เห็น)

การใช้งาน:
    python leak_check.py <ไฟล์หรือโฟลเดอร์> [...]
    python leak_check.py --reveal <ไฟล์>     # เฉพาะในเครื่อง ห้ามแปะผลลง GitHub
    python leak_check.py --self-test
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile

LEAK_CHECK_VERSION = "leak-check-0.2.0"
REQUIRED_KEYS = tuple("ABCDEFGH")

# รูปแบบทั้ง 8 หมวดเก็บไว้ในไฟล์ local นอก repo
# (ตัวตรวจการรั่วไหลที่ฝังคำต้องห้ามไว้ในตัวเอง ก็คือการรั่วไหลอย่างหนึ่ง)
_DEFAULT_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "_local", "local_identity.json")

_LABELS = {
    "A": "absolute machine path / ชื่อผู้ใช้เครื่อง",
    "B": "ชื่อบุคคล",
    "C": "ชื่อหน่วยงาน/กระทรวงจริง",
    "D": "รหัสหน่วยงาน/กระทรวง/หน่วยปฏิบัติ",
    "E": "ยอดขั้นคำขอ/ระหว่างพิจารณา — ประชาชนยังไม่ทราบ",
    "F": "ผลต่าง internal→public — เปิดแล้วย้อนหายอดคำขอได้",
    "G": "ชื่อไฟล์ข้อมูลงานจริง",
    "H": "path/โฟลเดอร์ภายในโปรเจกต์",
}

#: ชุดพื้นฐานในตัว — รูปแบบทั่วไปเท่านั้น ไม่มีคำเฉพาะโครงการ
#: ตัวยึดที่กลบแล้ว (ขึ้นต้นด้วย ``<`` หรือ ``…``) ไม่นับ เช่น ``C:\Users\<user>``
BASELINE = [
    ("Z1", "เส้นทางโฟลเดอร์ผู้ใช้วินโดวส์",
     r"(?i)\b[A-Z]:[\\/]{1,2}Users[\\/]{1,2}(?![<…])[^\\/\s<>\"'`|]+"),
    ("Z2", "เส้นทางโฟลเดอร์ผู้ใช้ยูนิกซ์/แมก",
     r"(?<![\w.])/(?:home|Users)/(?!<)[A-Za-z0-9._-]+"),
    ("Z3", "เส้นทาง UNC",
     r"\\\\(?!<)[A-Za-z0-9._-]+\\[^\s\\<>\"'`|]+"),
]

TEXT_EXT = {".md", ".py", ".csv", ".json", ".txt", ".yml", ".yaml", ".toml", ".cfg"}


def load_local(path: str):
    """คืน (patterns, labels, error) — error ไม่ว่าง ⇒ ตรวจไม่ครบ"""
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        return {}, {}, f"โหลดไฟล์รูปแบบ local ไม่ได้ ({type(e).__name__})"
    lp = cfg.get("leak_patterns") or {}
    missing = [k for k in REQUIRED_KEYS if not lp.get(k)]
    if missing:
        return lp, cfg.get("leak_pattern_labels", {}), f"หมวดที่ขาด: {','.join(missing)}"
    bad = []
    for k, p in lp.items():
        try:
            re.compile(p)
        except re.error:
            bad.append(k)
    if bad:
        return lp, cfg.get("leak_pattern_labels", {}), f"regex เสีย: {','.join(bad)}"
    return lp, cfg.get("leak_pattern_labels", {}), ""


def build_patterns(lp, labels):
    local = [(k, labels.get(k, _LABELS.get(k, k)), lp[k]) for k in sorted(lp)]
    return local + list(BASELINE)


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for dp, dn, fn in os.walk(p):
                dn[:] = [d for d in dn if d not in (".git", "__pycache__")]
                for f in sorted(fn):
                    if os.path.splitext(f)[1].lower() in TEXT_EXT:
                        out.append(os.path.join(dp, f))
        elif os.path.isfile(p):
            out.append(p)
    return out


def _read(f):
    try:
        return io.open(f, encoding="utf-8-sig").read()
    except UnicodeDecodeError:
        return io.open(f, encoding="utf-8", errors="replace").read()


def scan(files, patterns):
    """คืน {file: {key: [(line_no, match_text), ...]}} เฉพาะไฟล์ที่มี hit"""
    compiled = [(k, re.compile(p)) for k, _, p in patterns]
    result = {}
    for f in files:
        txt = _read(f)
        per = {}
        for key, rx in compiled:
            for m in rx.finditer(txt):
                line = txt.count("\n", 0, m.start()) + 1
                per.setdefault(key, []).append((line, m.group(0)))
        if per:
            result[f] = per
    return result


def run(files, patterns, load_error, reveal, out):
    labels = {k: lab for k, lab, _ in patterns}
    keys = [k for k, _, _ in patterns]
    hits = scan(files, patterns)
    out.write(f"{LEAK_CHECK_VERSION} · หมวดที่ใช้: {' '.join(keys)}\n")
    out.write(f"{'ไฟล์':52s} " + "  ".join(f"{k:>2s}" for k in keys) + "\n")
    out.write("-" * 84 + "\n")
    total = 0
    for f in files:
        per = hits.get(f, {})
        cells = [f"{len(per.get(k, [])):>2d}" for k in keys]
        total += sum(len(v) for v in per.values())
        out.write(f"{os.path.relpath(f).replace(os.sep, '/'):52s} " + "  ".join(cells) + "\n")
    out.write("\n")
    if hits:
        out.write("=" * 84 + "\nตำแหน่งที่พบ (ไม่แสดงค่า" + (" — ⚠ --reveal เปิดอยู่" if reveal else "") + ")\n")
        for f, per in hits.items():
            out.write(f"\n### {os.path.relpath(f).replace(os.sep, '/')}\n")
            for k in keys:
                if k not in per:
                    continue
                lines = sorted({ln for ln, _ in per[k]})
                out.write(f"   {k}. {labels[k]}: {len(per[k])} จุด · บรรทัด {lines[:20]}\n")
                if reveal:
                    for ln, t in per[k][:8]:
                        out.write(f"      L{ln}: {t!r}\n")
    if load_error:
        out.write(f"\n🟠 LEAK CHECK INCOMPLETE — {load_error} · ตรวจได้เฉพาะชุดพื้นฐาน · "
                  "ห้ามใช้เป็นใบอนุญาตเผยแพร่\n")
        return 3
    if hits:
        out.write(f"\n🔴 LEAK CHECK FAILED — พบทั้งหมด {total} จุดใน {len(hits)} ไฟล์\n")
        return 1
    out.write(f"✅ LEAK CHECK PASSED — ตรวจ {len(files)} ไฟล์ · 0 hit · "
              f"หมวด A–H ครบ + ชุดพื้นฐาน {len(BASELINE)} หมวด "
              "(ไม่พบรูปแบบที่ตรวจ ≠ ปลอดการเปิดเผย)\n")
    return 0


def self_test() -> int:
    """ตรวจสามพฤติกรรมที่ BLOCKER 2 กำหนด — ใช้ข้อมูลสังเคราะห์ล้วน"""
    fails = []
    secret = "ZZQ-SYNTH-SECRET-777"
    with tempfile.TemporaryDirectory() as d:
        doc = os.path.join(d, "doc.md")
        with open(doc, "w", encoding="utf-8") as f:
            bs = chr(92)   # ประกอบตอนรัน — ซอร์สนี้จะได้ไม่ถูกชุด Z จับเอง
            f.write("hello\nline2 " + secret + "\n"
                    + bs.join(["C:", "Users", "synthuser", "x.txt"]) + "\n"
                    + bs.join(["C:", "Users", "<user>", "ok"]) + "\n")
        cfg_ok = os.path.join(d, "ok.json")
        with open(cfg_ok, "w", encoding="utf-8") as f:
            json.dump({"leak_patterns": {k: (re.escape(secret) if k == "B" else "QQ_NEVER_" + k)
                                         for k in REQUIRED_KEYS}}, f)
        cfg_short = os.path.join(d, "short.json")
        with open(cfg_short, "w", encoding="utf-8") as f:
            json.dump({"leak_patterns": {"A": "QQ_NEVER"}}, f)

        def go(cfg, reveal=False):
            lp, lab, err = load_local(cfg)
            buf = io.StringIO()
            rc = run([doc], build_patterns(lp, lab), err, reveal, buf)
            return rc, buf.getvalue()

        rc, txt = go(os.path.join(d, "missing.json"))
        if rc != 3:
            fails.append(f"ไม่มีไฟล์รูปแบบ ต้องได้ 3 ได้ {rc}")
        rc, txt = go(cfg_short)
        if rc != 3:
            fails.append(f"หมวดไม่ครบ ต้องได้ 3 ได้ {rc}")
        rc, txt = go(cfg_ok)
        if rc != 1:
            fails.append(f"มี hit ต้องได้ 1 ได้ {rc}")
        if secret in txt or "synthuser" in txt:
            fails.append("พิมพ์ค่าที่ hit ออกมาโดยไม่ได้ขอ")
        if "บรรทัด [2]" not in txt:
            fails.append("ไม่รายงานเลขบรรทัดของ hit")
        z1 = scan([doc], BASELINE).get(doc, {}).get("Z1", [])
        if len(z1) != 1:
            fails.append(f"ชุดพื้นฐาน Z1 ต้องจับ 1 จุด (ไม่นับตัวยึด <user>) ได้ {len(z1)}")
        rc, txt = go(cfg_ok, reveal=True)
        if secret not in txt:
            fails.append("--reveal ไม่แสดงค่า")
        clean = os.path.join(d, "clean.md")
        with open(clean, "w", encoding="utf-8") as f:
            f.write("nothing here\n")
        lp, lab, err = load_local(cfg_ok)
        if run([clean], build_patterns(lp, lab), err, False, io.StringIO()) != 0:
            fails.append("ไฟล์สะอาด + รูปแบบครบ ต้องได้ 0")
    for x in fails:
        print("FAIL:", x)
    print(f"self-test {LEAK_CHECK_VERSION}: " + ("PASS" if not fails else f"{len(fails)} FAIL"))
    return 0 if not fails else 1


def main(argv):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    args = argv[1:]
    if "--self-test" in args:
        return self_test()
    reveal = "--reveal" in args
    args = [a for a in args if a != "--reveal"]
    if not args:
        print(__doc__)
        return 2
    files = collect(args)
    if not files:
        print("ไม่พบไฟล์ข้อความให้ตรวจ")
        return 2
    lp, lab, err = load_local(os.environ.get("P1REG_LOCAL_CONFIG", _DEFAULT_LOCAL))
    return run(files, build_patterns(lp, lab), err, reveal, sys.stdout)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
