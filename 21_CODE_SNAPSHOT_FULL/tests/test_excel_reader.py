# -*- coding: utf-8 -*-
"""ทดสอบตัวอ่าน Excel: อ่านได้จริง ไม่แก้ไฟล์ต้นฉบับ และไม่เดาค่าที่อ่านไม่ได้"""
import openpyxl
import pytest

from redbook.core.hashing import sha256_file
from redbook.readers import excel_reader


def test_structure_reports_sheets_and_counts(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "บัญชีและคำชี้แจง"
    ws.append(["รายการ", "จำนวน", "ราคาต่อหน่วย", "รวมเงิน"])
    ws.append(["ก", 2, 100, "=B2*C2"])
    ws.append(["ข", 3, 50, "=B3*C3"])
    ws.append(["ค", "1,250", 10, 12500])          # ตัวเลขที่เก็บเป็นข้อความ
    ws.merge_cells("A6:D6")
    ws.row_dimensions[5].hidden = True
    wb.create_sheet("ชีตที่สอง")
    path = tmp_path / "t.xlsx"
    wb.save(path)
    wb.close()

    s = excel_reader.read_structure(path)
    assert s["sheet_count"] == 2
    assert s["sheet_names"][0] == "บัญชีและคำชี้แจง"
    first = s["sheets"][0]
    assert first["counts"]["formula"] == 2
    assert first["counts"]["number_stored_as_text"] == 1
    assert "A6:D6" in first["merged_ranges"]
    assert 5 in first["hidden_rows"]


def test_reading_does_not_modify_source(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.append(["a", 1])
    path = tmp_path / "src.xlsx"
    wb.save(path)
    wb.close()

    before = sha256_file(path)
    excel_reader.read_structure(path)
    excel_reader.read_cells(path, "Sheet")
    assert sha256_file(path) == before


def test_formula_without_cached_value_is_reported_not_guessed(tmp_path):
    """openpyxl เขียนไฟล์โดยไม่มีค่าที่คำนวณไว้ ระบบต้องรายงานว่าอ่านค่าไม่ได้"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = 2
    ws["A2"] = 3
    ws["A3"] = "=A1+A2"
    path = tmp_path / "f.xlsx"
    wb.save(path)
    wb.close()

    s = excel_reader.read_structure(path)
    assert s["totals"]["cached_value_missing"] == 1

    cells = excel_reader.read_cells(path, "Sheet")
    a3 = cells["rows"][2][0]
    assert a3["formula"] == "=A1+A2"
    assert a3["value"] is None
    assert a3["value_available"] is False   # ไม่เดาว่าเท่ากับ 5


def test_missing_sheet_raises_safe_error(tmp_path):
    wb = openpyxl.Workbook()
    path = tmp_path / "x.xlsx"
    wb.save(path)
    wb.close()
    with pytest.raises(excel_reader.ExcelReadError):
        excel_reader.read_cells(path, "ไม่มีชีตนี้")


def test_bad_file_raises_safe_error(tmp_path):
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"PK\x03\x04not-a-real-workbook")
    with pytest.raises(excel_reader.ExcelReadError):
        excel_reader.read_structure(path)


def test_parser_versions_recorded():
    v = excel_reader.parser_versions()
    assert v["excel"].startswith("openpyxl/")
