#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
leak_check.py — ตรวจว่าไฟล์ที่จะเผยแพร่ไม่มีข้อมูลที่ห้ามออกนอกเครื่อง

รูปแบบที่ตรวจ 8 หมวด (A–H) ดูใน PATTERNS ด้านล่าง
exit code 0 = ผ่าน (0 hit ทุกหมวด) · 1 = ไม่ผ่าน

การใช้งาน:
    python leak_check.py <ไฟล์หรือโฟลเดอร์> [...]
    python leak_check.py publish/          # ตรวจทั้งชุดก่อน push
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# รูปแบบทั้ง 8 หมวดเก็บไว้ในไฟล์ local นอก repo
# (ตัวตรวจการรั่วไหลที่ฝังคำต้องห้ามไว้ในตัวเอง ก็คือการรั่วไหลอย่างหนึ่ง)
_DEFAULT_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "_local", "local_identity.json")
_LOCAL_PATH = os.environ.get("P1REG_LOCAL_CONFIG", _DEFAULT_LOCAL)
try:
    with open(_LOCAL_PATH, encoding="utf-8") as _f:
        _cfg = json.load(_f)
    _LP = _cfg.get("leak_patterns", {})
    _LOCAL_LABELS = _cfg.get("leak_pattern_labels", {})
except (OSError, ValueError):
    _LP, _LOCAL_LABELS = {}, {}
    print("[warn] ไม่พบไฟล์รูปแบบ local — ตรวจอะไรไม่ได้", file=sys.stderr)

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
# ทุกรูปแบบอยู่ในไฟล์ local — ไม่มีคำต้องห้ามคำใดปรากฏในสคริปต์นี้
PATTERNS = [(k, _LOCAL_LABELS.get(k, _LABELS.get(k, k)), _LP[k]) for k in sorted(_LP)]
if not PATTERNS:
    print("[warn] ไม่มีรูปแบบให้ตรวจเลย — ตรวจสอบไฟล์ local", file=sys.stderr)

TEXT_EXT = {".md", ".py", ".csv", ".json", ".txt", ".yml", ".yaml", ".toml", ".cfg"}


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


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    files = collect(argv[1:])
    if not files:
        print("ไม่พบไฟล์ข้อความให้ตรวจ")
        return 2

    total = 0
    print(f"{'ไฟล์':52s} " + "  ".join(k for k, _, _ in PATTERNS))
    print("-" * 84)
    detail = []
    for f in files:
        try:
            txt = io.open(f, encoding="utf-8-sig").read()
        except UnicodeDecodeError:
            txt = io.open(f, encoding="utf-8", errors="replace").read()
        cells, hits_here = [], {}
        for key, label, pat in PATTERNS:
            hits = re.findall(pat, txt)
            n = len(hits)
            total += n
            cells.append(f"{n:>2d}" if n == 0 else f"\x1b[31m{n:>2d}\x1b[0m" if sys.stdout.isatty() else f"{n:>2d}")
            if hits:
                hits_here[f"{key}. {label}"] = sorted({h if isinstance(h, str) else h[0] for h in hits})[:8]
        rel = os.path.relpath(f).replace("\\", "/")
        print(f"{rel:52s} " + "  ".join(cells))
        if hits_here:
            detail.append((rel, hits_here))

    print()
    if detail:
        print("=" * 84)
        print("รายละเอียดที่พบ")
        for rel, d in detail:
            print(f"\n### {rel}")
            for k, v in d.items():
                print(f"   {k}: {v}")
        print()
        print(f"🔴 LEAK CHECK FAILED — พบทั้งหมด {total} รายการใน {len(detail)} ไฟล์")
        return 1

    print(f"✅ LEAK CHECK PASSED — ตรวจ {len(files)} ไฟล์ · 0 hit ทั้ง 8 หมวด")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
