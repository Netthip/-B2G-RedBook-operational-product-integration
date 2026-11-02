# -*- coding: utf-8 -*-
"""ทดสอบกลไก inventory (Phase 2A): อ่านอย่างเดียว รายงาน candidate ไม่ตัดสินใจแทน

ไฟล์ทดสอบทั้งหมดเป็นข้อมูลสมมติที่สร้างในโฟลเดอร์ชั่วคราวของ pytest เท่านั้น
"""
import json

import openpyxl
from openpyxl.styles import Alignment, Font

import pytest

from redbook.core.hashing import sha256_file
from redbook.readers import excel_inventory
from redbook import inventory_cli


def _build_budget_like(path, year_current=2569, year_base=2568, extra_col=False,
                       code_prefix=""):
    """สร้างสมุดงานที่มีโครงคล้ายเอกสารงบประมาณทั่วไป (ข้อมูลสมมติทั้งหมด)"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "รายละเอียด"
    ws["A1"] = "สถาบันตัวอย่างเพื่อการทดสอบ (ข้อมูลสมมติ)"
    ws["A1"].font = Font(b=True)
    ws["A2"] = f"เอกสารประกอบ ปีงบประมาณ พ.ศ. {year_current}"
    ws["F2"] = "หน่วย : ล้านบาท"
    ws.merge_cells("A1:G1")

    # แถบหัวตารางสองแถว (4-5)
    headers4 = ["ลำดับ", "รหัส", "รายการ", f"งบประมาณ ปี {year_base}",
                f"งบประมาณ ปี {year_current}", "เพิ่ม/ลด", "ร้อยละ"]
    if extra_col:
        headers4.append("คำชี้แจง")
    for c, h in enumerate(headers4, start=1):
        ws.cell(row=4, column=c, value=h)
    ws.cell(row=5, column=4, value="(ล้านบาท)")
    ws.cell(row=5, column=5, value="(ล้านบาท)")

    rows = [
        (1, f"{code_prefix}0101", "แผนงานตัวอย่างที่หนึ่ง", 10.5, 12.0),
        (2, f"{code_prefix}0101.01", "ผลผลิตตัวอย่าง ก", 6.5, 7.0),
        (3, f"{code_prefix}0101.02", "ผลผลิตตัวอย่าง ข", 4.0, 5.0),
        (4, f"{code_prefix}0202", "แผนงานตัวอย่างที่สอง", 3.0, 2.5),
    ]
    r = 6
    for seq, code, name, base, cur in rows:
        ws.cell(row=r, column=1, value=seq)
        ws.cell(row=r, column=2, value=code)
        cell_name = ws.cell(row=r, column=3, value=name)
        cell_name.alignment = Alignment(indent=1 if "." in code else 0)
        b = ws.cell(row=r, column=4, value=base)
        b.number_format = "#,##0.0000"
        cur_cell = ws.cell(row=r, column=5, value=cur)
        cur_cell.number_format = "#,##0.0000"
        ws.cell(row=r, column=6, value=f"=E{r}-D{r}")
        ws.cell(row=r, column=7, value=f"=IF(D{r}=0,0,(E{r}-D{r})/D{r}*100)")
        r += 1
    ws.cell(row=r, column=3, value="รวมทั้งสิ้น").font = Font(b=True)
    ws.cell(row=r, column=5, value=f"=SUM(E6:E{r-1})")

    ws2 = wb.create_sheet("สรุป")
    ws2["A1"] = "สรุปงบประมาณ (ข้อมูลสมมติ)"
    ws2["A3"] = "รวมทุกแผนงาน"
    ws2["B3"] = "='รายละเอียด'!E10"

    hidden = wb.create_sheet("ชีตซ่อน")
    hidden["A1"] = "ข้อมูลชั่วคราว"
    hidden.sheet_state = "hidden"

    wb.save(path)
    wb.close()
    return path


@pytest.fixture()
def budget_pair(tmp_path):
    a = _build_budget_like(tmp_path / "A_2569.xlsx", year_current=2569, year_base=2568)
    b = _build_budget_like(tmp_path / "B_2570.xlsx", year_current=2570, year_base=2569,
                           extra_col=True)
    return a, b


def test_inventory_is_read_only(budget_pair):
    a, _ = budget_pair
    before = sha256_file(a)
    excel_inventory.inventory_workbook(a)
    assert sha256_file(a) == before


def test_inventory_detects_structure(budget_pair):
    a, _ = budget_pair
    inv = excel_inventory.inventory_workbook(a)

    assert inv["sheet_names"] == ["รายละเอียด", "สรุป", "ชีตซ่อน"]
    assert inv["hidden_sheets"] == ["ชีตซ่อน"]

    detail = inv["sheets"][0]
    assert detail["header_band"]["best_rows"] == [4, 5]
    assert detail["data_range"]["first_data_row"] == 6
    assert detail["merged_count"] == 1
    assert any(t["row"] == 10 for t in detail["total_row_candidates"])

    # ปี พ.ศ. ต้องขึ้นเป็น candidate ทั้งปีปัจจุบันและปีฐาน
    years = {y["year"] for y in inv["year_candidates"]}
    assert 2569 in years
    # ชื่อหน่วยงาน candidate ต้องเจอจาก token "สถาบัน"
    assert any("สถาบันตัวอย่าง" in a_["text"] for a_ in inv["agency_candidates"])
    # หน่วยเงิน
    assert any("ล้านบาท" in u["text"] for u in inv["unit_hints"])

    cols = {c["letter"]: c for c in detail["columns"]}
    assert cols["B"]["code_like"] is True
    assert cols["B"]["code_values"]  # เก็บชุดค่ารหัสไว้ให้เทียบข้ามไฟล์
    assert cols["D"]["dominant_number_format"] == "#,##0.0000"
    assert cols["C"]["indent_levels"]  # ร่องรอยลำดับชั้นจากการเยื้อง

    # สูตรจากชีตสรุปต้องบันทึกการอ้างถึงชีตรายละเอียด
    summary = inv["sheets"][1]
    assert summary["formulas"]["refs_to_sheets"].get("รายละเอียด")


def test_inventory_reports_candidates_not_decisions(budget_pair):
    a, _ = budget_pair
    inv = excel_inventory.inventory_workbook(a)
    # โครงสร้างผลลัพธ์ไม่มี key ที่สื่อว่าระบบสรุปเลือกแล้ว
    assert "chosen_mapping" not in inv
    assert "decided" not in json.dumps(inv, ensure_ascii=False, default=str)


def test_compare_structures_reports_diffs(budget_pair):
    a, b = budget_pair
    inv_a = excel_inventory.inventory_workbook(a)
    inv_b = excel_inventory.inventory_workbook(b)
    cmp_ = excel_inventory.compare_structures(inv_a, inv_b)

    detail = next(cs for cs in cmp_["common_sheets"] if cs["name"] == "รายละเอียด")
    changed_letters = {d["letter"] for d in detail["header_diffs"]}
    # ปีในหัวตารางเปลี่ยน (D, E) และคอลัมน์ H เพิ่มเฉพาะไฟล์ B
    assert {"D", "E", "H"} <= changed_letters
    # ค่ารหัสร่วมกันต้องถูกวัด (ไฟล์ทั้งสองใช้รหัสชุดเดียวกัน)
    ov = next(o for o in detail["code_column_overlap"] if o["letter"] == "B")
    assert ov["containment_pct"] == 100.0


def test_cli_end_to_end(budget_pair, tmp_path, capsys):
    a, b = budget_pair
    out = tmp_path / "reports"
    rc = inventory_cli.main([str(a), str(b), "--outdir", str(out)])
    assert rc == 0
    for name in ("FILE_INVENTORY.md", "WORKBOOK_STRUCTURE_REPORT.md",
                 "MAPPING_CANDIDATES.md", "inventory.json"):
        assert (out / name).exists(), name

    fi = (out / "FILE_INVENTORY.md").read_text(encoding="utf-8")
    assert "SHA-256 ก่อนอ่าน" in fi and "✔ ยืนยัน (แฮชตรงกัน)" in fi
    mc = (out / "MAPPING_CANDIDATES.md").read_text(encoding="utf-8")
    assert "รอผู้ใช้ยืนยัน" in mc
    assert "ห้าม commit เข้า git" in mc
    data = json.loads((out / "inventory.json").read_text(encoding="utf-8"))
    assert len(data["entries"]) == 2 and data["comparison"] is not None
    # ไฟล์ต้นฉบับไม่ถูกแตะ
    assert sha256_file(a) == data["entries"][0]["file"]["sha256_before"]


def test_cli_blocks_onedrive_outdir(budget_pair, tmp_path):
    a, _ = budget_pair
    bad = tmp_path / "OneDrive" / "reports"
    rc = inventory_cli.main([str(a), "--outdir", str(bad)])
    assert rc == inventory_cli.EXIT_BAD_ARGS
    assert not bad.exists()
    rc2 = inventory_cli.main([str(a), "--outdir", str(bad), "--allow-onedrive"])
    assert rc2 == 0


def test_cli_records_pdf_without_reading_content(budget_pair, tmp_path):
    a, _ = budget_pair
    pdf = tmp_path / "อนุมัติปรับลด.pdf"
    pdf.write_bytes(b"%PDF-1.7\n" + "ไฟล์ทดสอบ".encode("utf-8"))
    out = tmp_path / "rep2"
    rc = inventory_cli.main([str(a), str(pdf), "--outdir", str(out)])
    assert rc == 0
    fi = (out / "FILE_INVENTORY.md").read_text(encoding="utf-8")
    assert "อนุมัติปรับลด.pdf" in fi
    assert "Phase 3" in fi
