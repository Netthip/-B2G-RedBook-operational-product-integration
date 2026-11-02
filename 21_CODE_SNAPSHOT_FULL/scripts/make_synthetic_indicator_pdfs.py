# -*- coding: utf-8 -*-
"""สร้าง PDF สังเคราะห์สองฉบับ (เก่า/ใหม่) สำหรับทดสอบทะเบียนตัวชี้วัด + การเปิดหลักฐาน

🔴 **SYNTHETIC TEST FIXTURE** — เนื้อหาทั้งหมดแต่งขึ้น · หน่วยงาน "สถาบันทดสอบสังเคราะห์"
ไม่มีอยู่จริง · ตัวเลขทุกตัวสมมติ · ห้ามรายงานผลจากไฟล์ชุดนี้ว่าเป็นข้อค้นพบในเอกสารจริง
และ **ไม่ใช่เฉลยของการประเมิน** (ตารางคาดหมายท้ายไฟล์ใช้กับ unit test เท่านั้น)

อยู่นอกแพ็กเกจ ``redbook/`` โดยเจตนา (ฝ่ายสร้างไฟล์แยกจากฝ่ายตรวจ · เทสต์สถาปัตยกรรม
กัน ``.save()`` ในแพ็กเกจ) · ต้องมี PyMuPDF และฟอนต์ไทยในเครื่อง

กรณีที่ฝังไว้ (คำสั่งกิ๊ฟ Gate 3 ข้อ 3):
  * ตัวชี้วัดย้ายหน้า (เก่า p2 → ใหม่ p3)
  * เลขหน้าเปลี่ยน · ข้อความซ้ำในฉบับใหม่ (one-to-many) · หน้าที่ไม่มีชั้นข้อความ (เก่า p4)
  * ทุกบรรทัดต้องอยู่ในขอบหน้า (x1 < 539 pt) — บรรทัดที่ล้นหน้าทำให้ backend ต่างกันอ่านได้ไม่เท่ากัน
  * ทั้ง 8 สถานะมีตัวอย่างอย่างน้อยหนึ่งกรณี (ยกเว้น RELATED_NOT_EQUIVALENT ที่เครื่องไม่เสนอ —
    มีคู่ที่คนอาจตัดสินเป็นสถานะนั้น)

ใช้: .venv\\Scripts\\python.exe scripts\\make_synthetic_indicator_pdfs.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "fixtures" / "synthetic_pdf"
FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/tahoma.ttf"),
    Path("C:/Windows/Fonts/leelawad.ttf"),
    Path("/usr/share/fonts/truetype/tlwg/Garuda.ttf"),
]

AGENCY = "สถาบันทดสอบสังเคราะห์ (สทส.)"
MINISTRY = "กระทรวงทดสอบ (สังเคราะห์)"

OLD_PAGES = [
    # p1 ปก — ไม่มีตัวชี้วัด
    ["เอกสารประกอบการทดสอบระบบ (สังเคราะห์)", MINISTRY, AGENCY,
     "ปีงบประมาณ พ.ศ. 2569 — ร่างพระราชบัญญัติงบประมาณรายจ่าย (สมมติ)",
     "SYNTHETIC TEST FIXTURE — เนื้อหาทั้งหมดแต่งขึ้นเพื่อทดสอบซอฟต์แวร์"],
    # p2
    ["7.1 แผนงานพื้นฐานด้านการทดสอบ (สังเคราะห์)",
     "ผลผลิต : การพัฒนาบุคลากรทดสอบ  งบประมาณ 12,345,600 บาท",
     "ตัวชี้วัดที่ 1 : ร้อยละของหน่วยงานที่ได้รับการอบรม เป้าหมาย ร้อยละ 80",
     "ตัวชี้วัดที่ 2 : ร้อยละของบุคลากรที่ผ่านการประเมิน (ร้อยละ 90)",
     "ตัวชี้วัดที่ 3 : จำนวนรายงานวิจัยที่เผยแพร่ ไม่น้อยกว่า 5 เรื่อง",
     "1. งบดำเนินงาน 3,000,000 บาท", "2. งบเงินอุดหนุน 9,345,600 บาท"],
    # p3
    ["7.2 แผนงานยุทธศาสตร์ทดสอบ (สังเคราะห์)",
     "โครงการ : โครงการทดสอบความพร้อมของระบบ  งบประมาณ 4,500,000 บาท",
     "ตัวชี้วัดที่ 4 : ร้อยละของโครงการที่แล้วเสร็จตามแผน (นับจากโครงการทั้งหมด) ร้อยละ 85",
     "ตัวชี้วัดที่ 5 : จำนวนผู้เข้ารับการอบรม 200 คน",
     "ตัวชี้วัดที่ 6 : ร้อยละของข้อร้องเรียนที่ได้รับการแก้ไข ร้อยละ 100",
     "ตัวชี้วัดที่ 7 : จำนวนกิจกรรมเผยแพร่ความรู้ 12 ครั้ง"],
    # p4 — หน้าที่ **ไม่มีชั้นข้อความ** (ฝังเป็นภาพ)
    {"image_only": ["7.3 แผนงานบูรณาการทดสอบ (สังเคราะห์) — หน้านี้เป็นภาพสแกนจำลอง",
                    "ตัวชี้วัดที่ 8 : จำนวนคู่มือที่จัดทำ 3 ฉบับ"]},
]

NEW_PAGES = [
    ["เอกสารประกอบการทดสอบระบบ (สังเคราะห์)", MINISTRY, AGENCY,
     "ปีงบประมาณ พ.ศ. 2570 — ร่างพระราชบัญญัติงบประมาณรายจ่าย (สมมติ)",
     "SYNTHETIC TEST FIXTURE — เนื้อหาทั้งหมดแต่งขึ้นเพื่อทดสอบซอฟต์แวร์"],
    # p2 — ตัวชี้วัดใหม่ล้วน
    ["สรุปภาพรวม (สังเคราะห์)", "หน่วยงานปรับโครงสร้างผลผลิตในปีงบประมาณ 2570",
     "ตัวชี้วัดที่ 8 : ร้อยละของระบบที่ผ่านการทดสอบความปลอดภัย ร้อยละ 95"],
    # p3 — ตัวชี้วัด 1–3 ย้ายมาหน้านี้
    ["7.1 แผนงานพื้นฐานด้านการทดสอบ (สังเคราะห์)",
     "ผลผลิต : การพัฒนาบุคลากรทดสอบ  งบประมาณ 11,900,000 บาท",
     "ตัวชี้วัดที่ 1 : ร้อยละของหน่วยงานที่ได้รับการอบรม เป้าหมาย ร้อยละ 80",
     "ตัวชี้วัดที่ 2 : ร้อยละ ของบุคลากร ที่ผ่านการประเมิน ( ร้อยละ ๙๐ )",
     "ตัวชี้วัดที่ 3 : จำนวนรายงานวิจัยที่ได้รับการเผยแพร่ ไม่น้อยกว่า 5 เรื่อง"],
    # p4
    ["7.2 แผนงานยุทธศาสตร์ทดสอบ (สังเคราะห์)",
     "โครงการ : โครงการทดสอบความพร้อมของระบบ  งบประมาณ 4,200,000 บาท",
     "ตัวชี้วัดที่ 4 : ร้อยละของโครงการที่แล้วเสร็จตามแผน (นับจากโครงการที่ได้รับจัดสรร) ร้อยละ 85",
     "ตัวชี้วัดที่ 5 : จำนวนหลักสูตรอบรมที่เปิดสอน 4 หลักสูตร",
     "ตัวชี้วัดที่ 7 : จำนวนกิจกรรมเผยแพร่ความรู้ 12 ครั้ง"],
    # p5 — ข้อความซ้ำกับ p4 (ตัวชี้วัดเดียวกันปรากฏใต้สองผลผลิต)
    ["ผลผลิต : การสื่อสารองค์กร (สังเคราะห์)  งบประมาณ 800,000 บาท",
     "ตัวชี้วัดที่ 7 : จำนวนกิจกรรมเผยแพร่ความรู้ 12 ครั้ง"],
]

# ── P1-2 · ชุดขอบเขต (edge case) ที่ **คง** ข้อความล้น/ชนขอบหน้าไว้โดยเจตนา ──────────
#
# 🔴 Bo (`5598957701` P1-2) — *"อย่าลบ edge case ที่ทำให้ backend ต่างกัน"*
# ชุดหลักถูกแก้ให้ทุกบรรทัดอยู่ในหน้าแล้ว (happy path) · ชุดนี้จึงเก็บกรณีที่ทำให้ตัวอ่าน
# ต่างชนิดอ่านได้ไม่เท่ากันไว้เป็น regression แยก · **ห้ามแก้ให้บรรทัดสั้นลง**
# ระบบต้องติดธง `TEXT_CLIPPED_AT_PAGE_EDGE` และห้ามเสนอ mapping เป็นผลปกติ

_LONG_OLD = ("ตัวชี้วัดที่ 9 : ร้อยละของโครงการที่ดำเนินการแล้วเสร็จตามแผนปฏิบัติการประจำปี "
             "(นับจากโครงการทั้งหมดที่ได้รับอนุมัติในปีงบประมาณ) เป้าหมาย ร้อยละ 85")
_LONG_NEW = ("ตัวชี้วัดที่ 9 : ร้อยละของโครงการที่ดำเนินการแล้วเสร็จตามแผนปฏิบัติการประจำปี "
             "(นับจากโครงการที่ได้รับจัดสรรงบประมาณจริงในปีงบประมาณ) เป้าหมาย ร้อยละ 85")

CLIPPED_OLD_PAGES = [
    ["เอกสารทดสอบกรณีข้อความล้นขอบหน้า (สังเคราะห์) ฉบับเก่า", MINISTRY, AGENCY,
     "SYNTHETIC EDGE-CASE FIXTURE — บรรทัดด้านล่างตั้งใจให้ยาวเกินขอบหน้า"],
    ["7.9 แผนงานทดสอบขอบเขต (สังเคราะห์)",
     _LONG_OLD,
     "ตัวชี้วัดที่ 10 : จำนวนรายงานที่จัดทำ 6 เรื่อง"],
]
CLIPPED_NEW_PAGES = [
    ["เอกสารทดสอบกรณีข้อความล้นขอบหน้า (สังเคราะห์) ฉบับใหม่", MINISTRY, AGENCY,
     "SYNTHETIC EDGE-CASE FIXTURE — บรรทัดด้านล่างตั้งใจให้ยาวเกินขอบหน้า"],
    ["7.9 แผนงานทดสอบขอบเขต (สังเคราะห์)",
     _LONG_NEW,
     "ตัวชี้วัดที่ 10 : จำนวนรายงานที่จัดทำ 6 เรื่อง"],
]

CLIPPED_EXPECTATIONS = {
    "note": ("บรรทัดตัวชี้วัดที่ 9 ทั้งสองฉบับล้นขอบหน้าโดยเจตนา — ตัวอ่าน PDF ต่างชนิด"
             " อ่านได้ไม่เท่ากัน · ระบบต้องติดธง TEXT_CLIPPED_AT_PAGE_EDGE และคู่ของมัน"
             " ต้องเป็น AMBIGUOUS_REVIEW_REQUIRED เสมอ ห้ามเสนอสถานะอัตโนมัติ"),
    "clipped_line_contains": "ตัวชี้วัดที่ 9",
    "unclipped_line_contains": "ตัวชี้วัดที่ 10",
}

#: คาดหมายสำหรับ unit test เท่านั้น — 🔴 ไม่ใช่เฉลยของการประเมิน
EXPECTATIONS = {
    "SAME_EXACT": ["ตัวชี้วัดที่ 1"],
    "SAME_WORDING_VARIANT": ["ตัวชี้วัดที่ 2"],
    "SAME_CONCEPT_REPHRASED": ["ตัวชี้วัดที่ 3"],
    "DEFINITION_CHANGED": ["ตัวชี้วัดที่ 4"],
    "REMOVED_INDICATOR": ["ตัวชี้วัดที่ 6"],
    "NEW_INDICATOR": ["ตัวชี้วัดที่ 8 : ร้อยละของระบบ"],
    "AMBIGUOUS_REVIEW_REQUIRED": ["ตัวชี้วัดที่ 7"],
    "RELATED_NOT_EQUIVALENT (human option only)": ["ตัวชี้วัดที่ 5"],
    "pages_without_text_layer": {"old": [4], "new": []},
    "moved": {"ตัวชี้วัดที่ 1": {"old_page": 2, "new_page": 3}},
}


def _font() -> Path:
    for p in FONT_CANDIDATES:
        if p.is_file():
            return p
    sys.exit("ไม่พบฟอนต์ไทยในเครื่อง — ระบุใน FONT_CANDIDATES")


def _write_lines(page, lines, font: Path, *, size=13.0, start_y=80.0, gap=28.0):
    y = start_y
    for text in lines:
        page.insert_text(fitz.Point(56, y), text, fontsize=size, fontname="thai",
                         fontfile=str(font))
        y += gap


def build(pages, out_path: Path, font: Path, title: str) -> None:
    doc = fitz.open()
    for spec in pages:
        page = doc.new_page(width=595, height=842)   # A4
        if isinstance(spec, dict) and "image_only" in spec:
            # วาดข้อความลงเอกสารชั่วคราว แล้วฝังเป็นภาพ ⇒ หน้านี้ไม่มีชั้นข้อความ
            tmp = fitz.open()
            tp = tmp.new_page(width=595, height=842)
            _write_lines(tp, spec["image_only"], font)
            pix = tp.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            page.insert_image(page.rect, pixmap=pix)
            tmp.close()
        else:
            _write_lines(page, spec, font)
    doc.set_metadata({"title": title, "author": "SYNTHETIC TEST FIXTURE",
                      "subject": "RedBook Verify — synthetic indicator fixture",
                      "creationDate": "D:20260909000000Z", "modDate": "D:20260909000000Z"})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.subset_fonts()
    doc.save(str(out_path), garbage=4, deflate=True)
    doc.close()


def main() -> None:
    font = _font()
    old = OUT / "synthetic_old_fy2569.pdf"
    new = OUT / "synthetic_new_fy2570.pdf"
    clip_old = OUT / "synthetic_clipped_old.pdf"
    clip_new = OUT / "synthetic_clipped_new.pdf"
    build(OLD_PAGES, old, font, "SYNTHETIC old FY2569")
    build(NEW_PAGES, new, font, "SYNTHETIC new FY2570")
    # 🔴 P1-2 — ชุดขอบเขตแยก · ห้ามตัดบรรทัดให้อยู่ในหน้า
    build(CLIPPED_OLD_PAGES, clip_old, font, "SYNTHETIC clipped old")
    build(CLIPPED_NEW_PAGES, clip_new, font, "SYNTHETIC clipped new")
    manifest = {
        "label": "SYNTHETIC TEST FIXTURE — not real documents, not an evaluation answer key",
        "font_used": font.name,
        "files": {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                           "bytes": p.stat().st_size}
                  for p in (old, new, clip_old, clip_new)},
        "expectations_for_unit_tests_only": EXPECTATIONS,
        "clipped_edge_case_expectations": CLIPPED_EXPECTATIONS,
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    print(json.dumps(manifest["files"], indent=2))


if __name__ == "__main__":
    main()
