# -*- coding: utf-8 -*-
"""ตัวสร้างสมุดงานสังเคราะห์ที่มีตารางรายปีพร้อมคอลัมน์ช่วงเวลา (G5/G6 · #14)

🔴 **SYNTHETIC TEST FIXTURE** — ทุกชื่อ ทุกยอด แต่งขึ้นทั้งหมด (``กระทรวงทดสอบ`` ·
``หน่วยงานทดสอบ`` · เลขกลม) · ห้ามรายงานผลจากไฟล์เหล่านี้ว่าเป็นข้อผิดพลาดในเอกสารจริง

โครงสร้างเลียนแบบตารางประมาณการล่วงหน้าของโครงการผูกพันในแบบฟอร์มทั่วไป:
ป้ายแถวคอลัมน์ ``A`` · หน่วยนับคอลัมน์ ``F`` · คอลัมน์ค่า ``G``–``K`` =
``เริ่มต้น - ปี`` · ปีเดี่ยวสามปี · ``ปี - จบ`` · และคอลัมน์ ``L`` ที่ **ไม่มีหัว**
"""
from __future__ import annotations

import openpyxl

from redbook.adapters.ao_workbook import AOWorkbookAdapter

HEADERS = {
    "G": "เริ่มต้น - ปี 2569",
    "H": "ปี 2570",
    "I": "ปี 2571",
    "J": "ปี 2572",
    "K": "ปี 2573 - จบ",
}
ROWS = ("รวมทั้งสิ้น", "เงินงบประมาณ", "เงินนอกงบประมาณ")


def records(path):
    return [env.canonical_record for env in AOWorkbookAdapter().extract(path)]


def build(tmp_path, name="XL_FY2570_draft-bill_99999_TEST.xlsx", *,
          headers=None, values=None, extra_column=True, unit="ล้านบาท"):
    """``values[(row_label, column_letter)]`` แทนค่าตั้งต้น (เลขกลม)"""
    headers = dict(HEADERS if headers is None else headers)
    values = dict(values or {})
    wb = openpyxl.Workbook()
    cover = wb.active
    cover.title = "ปก"
    cover["A2"] = "กระทรวงทดสอบ"
    cover["A3"] = "หน่วยงานทดสอบ"
    cover["A5"] = "ปี 2570"

    ws = wb.create_sheet("โครงการ")
    ws["A1"] = "7.3 แผนงานยุทธศาสตร์ทดสอบ"
    ws["A2"] = "7.3.1 โครงการทดสอบ"
    ws["B3"] = "7.3.1.6 ประมาณการรายจ่ายล่วงหน้า"
    ws["A4"] = "รายการ"
    ws["F4"] = "หน่วยนับ"
    for col, text in headers.items():
        ws[f"{col}5"] = text
    for offset, label in enumerate(ROWS):
        r = 6 + offset
        ws[f"A{r}"] = label
        ws[f"F{r}"] = unit
        for n, col in enumerate(headers):
            ws[f"{col}{r}"] = values.get((label, col), float((offset + 1) * 10 + n))
        if extra_column:
            ws[f"L{r}"] = values.get((label, "L"), 1.0 + offset)
    path = tmp_path / name
    wb.save(path)
    wb.close()
    return path


def numeric_cells_in_value_region(path, sheet="โครงการ", first_row=6,
                                  last_row=6 + len(ROWS) - 1, first_col="G"):
    """เซลล์ตัวเลข **ทุกเซลล์** ในเขตค่า — นับจากไฟล์ตรง ๆ อิสระจากเอนจิน"""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet]
    start = openpyxl.utils.column_index_from_string(first_col)
    out = set()
    for r in range(first_row, last_row + 1):
        for c in range(start, ws.max_column + 1):
            v = ws.cell(r, c).value
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.add(f"{openpyxl.utils.get_column_letter(c)}{r}")
    wb.close()
    return out
