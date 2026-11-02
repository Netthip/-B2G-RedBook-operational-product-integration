# -*- coding: utf-8 -*-
"""ความครอบคลุมของการสุ่มทวนระเบียนกับภาพ — อะไร **ยังไม่อยู่ในตัวอย่าง** (REVIEW 6360210542)

อ่าน ``manifest.json`` ที่ ``scripts/pdfpair_sample_records.py`` สร้าง (ระเบียนที่สุ่ม + จำนวนประชากรต่อชนิด) แล้วสกัด
ไฟล์เดียวกันใหม่ด้วยรุ่นปัจจุบันเพื่อจัดชั้นละเอียด (ตาราง · ระดับโหนด · หัวข้อ · ชนิดหลักฐานปี) และจับคู่ระเบียนที่สุ่ม
ด้วย (หน้า · กรอบ · ข้อความ) — พิมพ์ตาราง **จำนวนเท่านั้น** (ไม่มีข้อความจากเล่ม) ลง stdout

    python scripts/pdfpair_sample_coverage.py --manifests <โฟลเดอร์ sample_check> --pdf-dir <โฟลเดอร์ไฟล์ชุดพัฒนา>

🔴 ใช้กับชุดพัฒนาเท่านั้น · ระเบียนที่จับคู่ไม่ได้ในรุ่นปัจจุบัน = ถูกแก้/ถอดหลังสุ่ม (รายงานแยก)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from redbook.pdfbook import PDFBOOK_VERSION, profile, reader  # noqa: E402
from redbook.pdfbook import extract as ex  # noqa: E402

KINDS = ("amount", "dash_blank", "node", "indicator", "text", "year")
#: ชนิดระเบียนที่ตัวสุ่มยังไม่ได้สุ่มเลย (อยู่นอกกรอบการสุ่ม)
OUTSIDE = {"item": "รายการในรายละเอียด (ยอดรายการ)", "commitment_line": "บรรทัดวงเงินรายการผูกพัน",
           "stage": "หลักฐานขั้นเอกสาร", "identity": "ปัญหาระบุตัวรายการ", "numbering": "เลขนำหน้าโหนด (รูปแบบ)"}


def strata(bf) -> dict:
    """{ชนิด: [(ชั้น, page, bbox, read)]} — ลำดับเดียวกับ ``pdfpair_sample_records._records``"""
    out = {k: [] for k in KINDS}
    for a in bf.amounts:
        out["amount"].append((a.table, a.ev.page, list(a.ev.bbox), a.raw))
    for a in list(bf.dashes) + list(bf.blanks):
        out["dash_blank"].append((f"{a.status}·{a.table}", a.ev.page, list(a.ev.bbox), a.raw or "(ว่าง)"))
    for n in bf.nodes.values():
        out["node"].append((n.level, n.ev.page, list(n.ev.bbox), n.label))
    for i in bf.indicators:
        rng = "มีช่วงปี" if any(not k.isdigit() for k in i.targets) else "ปีเดี่ยว"
        out["indicator"].append((f"{i.table or 'ระดับหน่วยงาน'}·{rng}", i.ev.page, list(i.ev.bbox), i.name))
    for t in bf.texts:
        out["text"].append((t.section, t.ev.page, list(t.ev.bbox), t.text[:200]))
    for e in bf.year_evidence:
        out["year"].append((e["kind"], e["page"], list(e.get("bbox") or []), e["line"]))
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--pdf-dir", required=True)
    a = ap.parse_args()
    pop, got, gone, outside = Counter(), Counter(), Counter(), Counter()
    files = 0
    for man_path in sorted(Path(a.manifests).glob("*/manifest.json")):
        man = json.loads(man_path.read_text(encoding="utf-8"))
        pdf = Path(a.pdf_dir) / man["file"]
        n = len(reader.page_texts(pdf))
        bf = ex.extract(reader.page_words(pdf, list(range(1, n + 1))), fiscal_year=man["fiscal_year"])
        from redbook.services.pdfpair import _locate_year, year_texts
        bf.year_evidence = _locate_year(pdf, ex.detect_year(year_texts(pdf, n, 1), 1).evidence)
        st = strata(bf)
        files += 1
        for kind, recs in st.items():
            for s, *_ in recs:
                pop[(kind, s)] += 1
        for row in man["rows"]:
            hit = next((s for s, p, b, r in st[row["kind"]]
                        if p == row["page"] and [round(x) for x in b] == [round(x) for x in row["bbox"]]
                        and (r or "")[:60] == (row["read"] or "")[:60]), None)
            if hit is None:
                gone[row["kind"]] += 1
            else:
                got[(row["kind"], hit)] += 1
        outside["item"] += sum(1 for i in bf.items if i.amount)
        outside["commitment_line"] += sum(len(c.lines) for c in bf.commitments)
        outside["identity"] += len(bf.identity_issues)
        outside["numbering"] += len(bf.numbering)
    print(f"# ความครอบคลุมของตัวอย่างทวนระเบียนกับภาพ ({files} ไฟล์ · ตัวสกัด {PDFBOOK_VERSION} · "
          f"โปรไฟล์ {profile.PROFILE_VERSION})\n")
    print("| ชนิด | ชั้น | ประชากร | อยู่ในตัวอย่าง |\n|---|---|---:|---:|")
    for (kind, s), n in sorted(pop.items()):
        print(f"| {kind} | {s} | {n} | {got.get((kind, s), 0)} |")
    print("\n**ชั้นที่ยังไม่มีในตัวอย่างเลย:** " + " · ".join(
        f"{k}/{s} ({n})" for (k, s), n in sorted(pop.items()) if not got.get((k, s))))
    print("\n**ระเบียนที่สุ่มแต่หาไม่พบในรุ่นนี้ (ถูกแก้/ถอดหลังสุ่ม):** "
          + (" · ".join(f"{k} {n}" for k, n in sorted(gone.items())) or "ไม่มี"))
    print("\n**อยู่นอกกรอบการสุ่ม (ตัวสุ่มไม่เคยเลือก):** " + " · ".join(
        f"{OUTSIDE[k]} {n}" for k, n in outside.items()) + f" · {OUTSIDE['stage']} (ไม่ได้สุ่ม)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
