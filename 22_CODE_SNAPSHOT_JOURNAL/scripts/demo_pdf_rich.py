# -*- coding: utf-8 -*-
"""PDF **สังเคราะห์** คู่กับสมุดงาน ``demo_ao_workbooks_rich.py`` — ใช้สาธิตหน้าเทียบภาพ PDF (#24)

🔴 **SYNTHETIC DEMONSTRATION DATA** — จัดหน้าเลียนแบบ *รูปแบบ* เล่มงบประมาณ (หัวเรื่อง ·
ตารางรายการ · ตัวเลขชิดขวา) จากข้อมูลสาธิตชุดเดียวกับสมุดงาน · ไม่ได้ลอกเนื้อหาจากเล่มใด
ทุกหน้ามีป้าย "ข้อมูลสังเคราะห์" · ห้ามใช้เป็นหลักฐานงานวิจัย

ฉบับ B มีหน้าคำนำเพิ่ม 1 หน้า ⇒ รายการเดียวกันอยู่คนละเลขหน้า (A หน้า N · B หน้า N+1)
เพื่อให้เห็นว่า locator บอกหน้าของแต่ละฝั่งแยกกัน · ตัวเลขงบในตารางพิมพ์เป็น **บาท**
ส่วนหน้าสรุปพิมพ์เป็น **ล้านบาท 4 ตำแหน่ง** ตามมาตรฐาน

อยู่นอกแพ็กเกจ ``redbook`` (ฝ่ายสร้างไฟล์แยกจากฝ่ายตรวจ) · ใช้ PyMuPDF + ฟอนต์ไทยในเครื่อง
"""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF — ใช้ได้ในเครื่องมือสร้าง fixture เท่านั้น

import demo_ao_workbooks_rich as rich

FONT_CANDIDATES = [Path("C:/Windows/Fonts/tahoma.ttf"), Path("C:/Windows/Fonts/leelawad.ttf"),
                   Path("/usr/share/fonts/truetype/tlwg/Garuda.ttf")]
MARK = "ข้อมูลสังเคราะห์ — สาธิตระบบเท่านั้น ไม่ใช่เอกสารงบประมาณจริง"
W, H = 595.0, 842.0


def _font() -> str:
    for p in FONT_CANDIDATES:
        if p.exists():
            return str(p)
    raise SystemExit("ไม่พบฟอนต์ไทยในเครื่อง")


def _baht(v) -> str:
    return f"{int(v):,}"


def _text(page, x, y, s, font, size=12.0):
    page.insert_text(fitz.Point(x, y), s, fontsize=size, fontname="thai", fontfile=font)


def _right(page, x_right, y, s, font, size=12.0):
    f = fitz.Font(fontfile=font)
    page.insert_text(fitz.Point(x_right - f.text_length(s, fontsize=size), y), s,
                     fontsize=size, fontname="thai", fontfile=font)


def _header(page, font, title, page_no):
    _text(page, 56, 40, MARK, font, 9)
    _text(page, 56, 70, title, font, 13)
    _right(page, W - 56, 820, f"หน้า {page_no}", font, 9)


def _table(page, font, rows, y0, years):
    _text(page, 56, y0, "รายการ", font, 11)
    _right(page, 440, y0, f"ปี {years[0]}", font, 11)
    _right(page, W - 56, y0, f"ปี {years[1]}", font, 11)
    _text(page, 56, y0 + 14, "(หน่วย : บาท)", font, 9)
    y = y0 + 40
    for label, indicator, unit, vals in rows:
        head = label.split(" ", 1)[0]
        indent = 72 if head.count(".") >= 1 and not head.endswith(".") else 56
        _text(page, indent, y, label, font, 11)
        for x, yr in ((440, years[0]), (W - 56, years[1])):
            v = vals.get(yr)
            if v is None:
                continue
            _right(page, x, y, f"ร้อยละ {v}" if unit == "ร้อยละ" else _baht(v), font, 11)
        y += 26


def build_pdf(out: Path, *, stage: str, fiscal_year: int, years, plan, project, summary,
              intro: bool) -> Path:
    font = _font()
    doc = fitz.open()
    n = 0

    def new(title):
        nonlocal n
        n += 1
        p = doc.new_page(width=W, height=H)
        _header(p, font, title, n)
        return p

    cover = new(f"{stage} งบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. {fiscal_year} (สาธิต)")
    _text(cover, 56, 120, rich.MINISTRY, font, 14)
    _text(cover, 56, 146, rich.AGENCY, font, 14)
    if intro:
        p = new("คำชี้แจงประกอบ (สาธิต)")
        _text(p, 56, 120, "หน้านี้เพิ่มเฉพาะฉบับ B เพื่อให้เลขหน้าของสองฉบับไม่ตรงกัน", font, 11)
    p = new(rich.PLAN_TITLE)
    _table(p, font, plan, 110, years)
    p = new(rich.PROJECT_TITLE)
    _text(p, 56, 92, f"ภายใต้ {rich.PLAN_TITLE[4:]}", font, 10)
    _table(p, font, project, 120, years)
    p = new(f"{rich.SUMMARY_TITLE} ปี {fiscal_year}")
    _right(p, W - 56, 100, "หน่วย : ล้านบาท", font, 10)
    per, op, inv, sub = summary
    # ตารางแนวนอนแบบเล่มงบ: หัวคอลัมน์ = หมวดงบรายจ่าย · แถว = รวมทั้งสิ้น (ล้านบาท 4 ตำแหน่ง)
    cols = [("งบบุคลากร", per), ("งบดำเนินงาน", op), ("งบลงทุน", inv), ("งบเงินอุดหนุน", sub),
            ("รวม", round(per + op + inv + sub, 4))]
    xs = [215, 290, 365, 450, W - 56]
    _text(p, 56, 140, "รายการ", font, 10)
    for (name, _v), x in zip(cols, xs):
        _right(p, x, 140, name, font, 10)
    _text(p, 56, 172, "รวมทั้งสิ้น", font, 11)
    for (_name, v), x in zip(cols, xs):
        _right(p, x, 172, f"{v:,.4f}", font, 11)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    doc.close()
    return out


def build(out_dir, scenario: str = "draft_act") -> tuple[Path, Path]:
    out = Path(out_dir)
    paths = []
    for side in ("A", "B"):
        sc = rich.SCENARIOS[scenario][side]
        paths.append(build_pdf(out / (rich.file_stem(scenario, side) + ".pdf"),
                               stage=sc["stage"], fiscal_year=sc["fiscal_year"], years=sc["years"],
                               plan=sc["plan"], project=sc["project"], summary=sc["summary"],
                               intro=side == "B"))
    return paths[0], paths[1]


if __name__ == "__main__":
    import sys
    sc = sys.argv[2] if len(sys.argv) > 2 else "draft_act"
    a, b = build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".data_demo/files_rich"), sc)
    print(f"สร้าง PDF สาธิต ({sc}) (สังเคราะห์ 100%) A: {a.name} · B: {b.name}")
