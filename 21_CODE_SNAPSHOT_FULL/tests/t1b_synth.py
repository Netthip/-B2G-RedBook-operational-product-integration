# -*- coding: utf-8 -*-
"""ตัวสร้างสมุดงานสังเคราะห์สำหรับชุดทดสอบ T1B

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานที่สร้างจากโมดูลนี้ถูกแต่งขึ้นทั้งหมด
ห้ามรายงานผลที่ได้จากไฟล์เหล่านี้ว่าเป็นข้อผิดพลาดที่พบในเอกสารจริง
และห้ามใช้เป็นหลักฐานงานวิจัย

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

from redbook.adapters.ao_workbook import AOWorkbookAdapter


def records(path):
    """สกัด record ตามเส้นทางจริงของผลิตภัณฑ์ — ไม่ลัดชั้นใด"""
    return [env.canonical_record for env in AOWorkbookAdapter().extract(path)]


def _cover(ws, agency: str, year: int) -> None:
    ws["A2"] = "กระทรวงทดสอบ"
    ws["A3"] = agency
    ws["A5"] = f"ปี {year}"


def _category_sheet(ws, title: str, *, invest: float, subsidy: float) -> None:
    ws["A1"] = title
    ws["E2"] = "หน่วย : ล้านบาท"
    ws["A3"] = "รายการ"
    ws["C3"], ws["D3"], ws["E3"] = "งบลงทุน", "งบเงินอุดหนุน", "รวม"
    ws["A4"] = "รวมทั้งสิ้น"
    ws["C4"], ws["D4"], ws["E4"] = invest, subsidy, invest + subsidy


def build_workbook(
    tmp_path,
    *,
    filename: str,
    agency: str | None,
    cover_year: int,
    section_title: str,
    invest: float = 10.0,
    subsidy: float = 5.0,
    second_agency: str | None = None,
):
    """สมุดงานสังเคราะห์

    ``agency=None``       ⇒ **ไม่มีชีตปก** ⇒ ``agency_identity`` ว่าง
                            (จำลองแฟ้มที่อ่านตัวตนหน่วยงานจากเนื้อในไม่ได้)
    ``second_agency``     ⇒ เพิ่มชีตปกที่สองที่ชื่อหน่วยงานต่างออกไป
                            (จำลองแฟ้มที่มีตัวตนหน่วยงานมากกว่าหนึ่งค่า)
    """
    import openpyxl

    wb = openpyxl.Workbook()
    first = wb.active
    if agency is None:
        first.title = "หมวด"
        _category_sheet(first, section_title, invest=invest, subsidy=subsidy)
    else:
        first.title = "ปก"
        _cover(first, agency, cover_year)
        if second_agency is not None:
            _cover(wb.create_sheet("ปก 2"), second_agency, cover_year)
        _category_sheet(
            wb.create_sheet("หมวด"), section_title, invest=invest, subsidy=subsidy
        )
    path = tmp_path / filename
    wb.save(path)
    wb.close()
    return path
