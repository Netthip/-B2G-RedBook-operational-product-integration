# -*- coding: utf-8 -*-
"""T1B — ขอบเขตของตาราง (blocker #4)

🔴 คำตัดสิน Bo · 3 กันยายน 2569 — `EXTRACTION OVERLAP P0`

body ของตารางหมวดต้องหยุดก่อน **บล็อกหัว** ของตารางถัดไป
เดิมตัดที่ **แถวป้ายปี** อย่างเดียว ⇒ แถวหัวคอลัมน์ของตารางถัดไปตกเป็น
แถวข้อมูลของตารางก่อนหน้า และข้อความหัวคอลัมน์ถูกอ่านเป็นค่าของหมวดงบรายจ่าย

**ข้อห้ามที่ผูกกับคำตัดสิน**

* ห้ามแก้โดยกรองรายการออกใน ``rollup.py``
* ห้าม hard-code ข้อความหัวคอลัมน์ ตำแหน่งเซลล์ หรือชื่อชีตใด ๆ
* ขอบเขตแข่งกันจนตัดสินไม่ได้ → ``TABLE_BOUNDARY_AMBIGUOUS`` / คิวมนุษย์
* raw และตำแหน่งแถวต้องยังอยู่ใน provenance — ห้ามทำให้หายเพื่อคืนตัวเลขเดิม

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import os
from pathlib import Path

import pytest

from redbook.adapters.ao_workbook import AOWorkbookAdapter
from redbook.t1b import CATEGORY_TOTAL
from redbook.t1b.header import (
    _header_block_start,
    _is_caption_row,
    find_category_tables,
    find_year_tables,
)
from redbook.t1b.records import (
    ROW_KIND_UNMAPPED,
    ROW_KIND_VALUE,
    UNC_TABLE_BOUNDARY_AMBIGUOUS,
)

# 🔴 คิดจากที่อยู่ของไฟล์นี้ ไม่ใช่เส้นทางตายตัวที่มีชื่อผู้ใช้
# คลังข้อมูลเป็น repo พี่น้องที่วางข้าง ๆ repo โค้ด ⇒ ได้เส้นทางเดิมทุกประการ
# ห้ามเขียนกลับเป็นเส้นทางตายตัว — ชื่อผู้ใช้จะติดขึ้น git ไปด้วย
_DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "redbook-verify-data" / "sources" / "public" / "ao_workbook"
)
SOURCE_DIR = Path(os.environ.get("REDBOOK_T1B_SOURCE_DIR", _DEFAULT_SOURCE))
FILES = (
    "XL_FY2569_draft-bill_21000_MOPH-summary.xlsx",
    "XL_FY2569_draft-bill_21011_HSRI.xlsx",
    "XL_FY2569_draft-bill_21016_NVI.xlsx",
    "XL_FY2570_draft-bill_21000_MOPH-summary.xlsx",
    "XL_FY2570_draft-bill_21011_HSRI.xlsx",
    "XL_FY2570_draft-bill_21016_NVI.xlsx",
)
needs_sources = pytest.mark.skipif(
    not (SOURCE_DIR / FILES[0]).exists(),
    reason=f"ไม่พบคลังข้อมูล T1B ที่ {SOURCE_DIR} (ข้อมูลอยู่นอก Git ตาม SYS-D-05)",
)


def _records(path):
    return [e.canonical_record for e in AOWorkbookAdapter().extract(path)]


def _build_two_table_sheet(tmp_path, caption_a="งบประมาณ", caption_b="ล่วงหน้า**"):
    """🔴 **SYNTHETIC TEST FIXTURE** — ผังเดียวกับแฟ้มจริง

    ห้ามรายงานผลจากชุดนี้ว่าเป็นข้อผิดพลาดที่พบใน workbook จริง

    ตารางหมวด (แถว 4-5) → แถวว่าง → หัวข้อย่อย → **แถวหัวคอลัมน์** →
    แถวป้ายปี → แถวข้อมูล

    แถวหัวคอลัมน์คือแถวที่เคยตกเป็นแถวข้อมูลของตารางหมวด
    """
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet7_2"
    ws["A1"] = "7.2 แผนงานพื้นฐานทดสอบ"
    ws["A2"] = "5. เป้าหมายการให้บริการหน่วยงาน"
    ws["J3"] = "หน่วย : ล้านบาท"
    ws["A4"] = "กิจกรรม"
    ws["G4"], ws["H4"], ws["J4"] = "งบดำเนินงาน", "งบลงทุน", "รวม"
    ws["A5"] = "รวมทั้งสิ้น"
    ws["G5"], ws["H5"], ws["J5"] = 1.0, 2.0, 3.0
    # แถว 6 เว้นว่างเป็นตัวคั่น
    ws["B7"] = "7.2.1.2 เป้าหมายผลผลิต งบประมาณ และกรอบงบประมาณรายจ่ายล่วงหน้า"
    ws["A8"] = "ตัวชี้วัด/\nแหล่งเงิน"
    ws["F8"] = "หน่วยนับ"
    ws["G8"], ws["I8"] = caption_a, caption_b          # ← แถวหัวคอลัมน์
    ws["G9"], ws["H9"] = "ปี 2568", "ปี 2569"
    ws["I9"], ws["J9"], ws["K9"] = "ปี 2570", "ปี 2571", "ปี 2572"
    ws["A10"] = "เชิงคุณภาพ : ตัวชี้วัดทดสอบ"
    ws["F10"] = "ร้อยละ"
    for col, val in zip("GHIJK", (100, 100, 100, 100, 100)):
        ws[f"{col}10"] = val
    path = tmp_path / "XL_FY2569_draft-bill_21011_BOUNDARY.xlsx"
    wb.save(path)
    wb.close()
    return path


# ══════════════════════════════ ① แถวหัวตารางถัดไปต้องไม่เป็นแถวข้อมูลของตารางหมวด
def test_next_table_header_row_is_not_a_category_data_row(tmp_path):
    """🔴 regression หลักของ blocker #4 — ต้องล้มบน ``f8201ea``

    ก่อนแก้: ``G8``/``I8`` ถูกอ่านเป็นค่าของหมวด ``OPERATING``/``SUBSIDY``
    ทั้งที่เป็น **ข้อความหัวคอลัมน์** ของตารางถัดไป
    """
    records = _records(_build_two_table_sheet(tmp_path))
    category_rows = {
        r.row_index for r in records
        if r.row_kind == ROW_KIND_VALUE and r.budget_category is not None
    }

    assert 8 not in category_rows, "แถวหัวคอลัมน์ต้องไม่เป็นแถวข้อมูลของตารางหมวด"
    assert 5 in category_rows, "แถวข้อมูลจริงของตารางหมวดต้องยังอยู่"


def test_no_category_record_is_produced_without_a_value(tmp_path):
    """หลังแก้แล้ว ต้องไม่มี record หมวดที่ไม่มีค่าเลย"""
    values = [
        r for r in _records(_build_two_table_sheet(tmp_path))
        if r.row_kind == ROW_KIND_VALUE and r.budget_category is not None
    ]

    assert values
    assert all(r.value_decimal is not None for r in values)


def test_the_caption_row_is_still_accounted_with_its_raw_text(tmp_path):
    """🔴 ห้ามทำให้แถวนั้นหายไปเพื่อคืนตัวเลขเดิม — ต้องยังถูกนับและมี raw"""
    records = _records(_build_two_table_sheet(tmp_path))
    row8 = [r for r in records if r.row_index == 8]

    assert row8, "แถวหัวคอลัมน์ต้องยังมี record ครอบคลุม"
    assert any(r.row_kind == ROW_KIND_UNMAPPED for r in row8)
    assert any(r.raw_label for r in row8), "ต้องเก็บข้อความดิบไว้"


@pytest.mark.parametrize(
    "caption_a, caption_b",
    [
        ("งบประมาณ", "ประมาณการรายจ่ายล่วงหน้า**"),
        ("ปีที่ขอตั้ง", "ปีล่วงหน้า"),
        ("คำขอ", "หมายเหตุ"),
        ("A", "B"),
    ],
)
def test_detection_uses_structure_not_specific_wording(tmp_path, caption_a, caption_b):
    """🔴 ห้าม hard-code ข้อความ — เปลี่ยนคำแล้วต้องยังตรวจจับได้"""
    records = _records(_build_two_table_sheet(tmp_path, caption_a, caption_b))
    category_rows = {
        r.row_index for r in records
        if r.row_kind == ROW_KIND_VALUE and r.budget_category is not None
    }

    assert 8 not in category_rows, f"ไม่ควรขึ้นกับคำว่า {caption_a!r}"


# ══════════════════════════════ ② กติกาของ "แถวหัวคอลัมน์"
@pytest.mark.parametrize(
    "row, expected, why",
    [
        (["ตัวชี้วัด", None, "งบประมาณ", "ล่วงหน้า"], True, "ข้อความล้วน"),
        (["รายการ", 1.0, 2.0], False, "มีตัวเลข = แถวข้อมูล"),
        (["รายการ", None, None], False, "ไม่มีข้อความในเขตค่า"),
        ([None, None, None], False, "แถวว่าง"),
        (["ก", "ข", 0], False, "มีตัวเลขแม้เป็นศูนย์"),
    ],
)
def test_caption_row_rule(row, expected, why):
    assert _is_caption_row(row) is expected, why


def test_header_block_start_stops_at_a_data_row():
    """บล็อกหัวต้องไม่กินแถวข้อมูลของตารางก่อนหน้า"""
    rows = [
        ["รวมทั้งสิ้น", 1.0, 2.0],          # 1 แถวข้อมูล
        ["ตัวชี้วัด", "คำขอ", "ล่วงหน้า"],   # 2 แถวหัวคอลัมน์
        ["รายการ", "ปี 2568", "ปี 2569"],   # 3 แถวป้ายปี
    ]
    assert _header_block_start(rows, 3) == 2


def test_header_block_start_respects_the_floor():
    """``floor_row`` กันไม่ให้ไล่ขึ้นข้ามหัวตารางก่อนหน้า"""
    rows = [
        ["ตัวชี้วัด", "ก", "ข"],
        ["ตัวชี้วัด", "ค", "ง"],
        ["รายการ", "ปี 2568", "ปี 2569"],
    ]
    assert _header_block_start(rows, 3, floor_row=2) == 3


# ══════════════════════════════ ③ ขอบเขตแข่งกัน → ต้องไม่ข้ามเงียบ
def test_conflicting_boundary_is_flagged_not_skipped():
    """ตารางหมวดที่ตามด้วยบล็อกหัวทันที ⇒ ไม่เหลือแถวข้อมูล

    เดิม ``continue`` เงียบ ⇒ **ทั้งตารางหายโดยไม่มีร่องรอย**
    """
    rows = [
        ["กิจกรรม", "งบดำเนินงาน", "งบลงทุน", "รวม"],
        ["รายการ", "ปี 2568", "ปี 2569", "ปี 2570"],
        ["x", 1.0, 2.0, 3.0],
    ]
    tables = find_category_tables(rows)

    assert len(tables) == 1, "ต้องยังรายงานตาราง ห้ามข้ามเงียบ"
    assert tables[0].boundary_ambiguous is True


def test_ambiguous_boundary_reaches_human_review(tmp_path):
    """end-to-end · ตารางที่ขอบเขตกำกวมต้องขึ้นคิวมนุษย์"""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet7_2"
    ws["A1"] = "7.2 แผนงานทดสอบ"
    ws["A2"] = "5. เป้าหมายการให้บริการหน่วยงาน"
    ws["A4"] = "กิจกรรม"
    ws["G4"], ws["H4"], ws["J4"] = "งบดำเนินงาน", "งบลงทุน", "รวม"
    ws["A5"] = "รายการ"
    ws["G5"], ws["H5"], ws["J5"] = "ปี 2568", "ปี 2569", "ปี 2570"
    ws["A6"] = "x"
    ws["G6"], ws["H6"], ws["J6"] = 1.0, 2.0, 3.0
    path = tmp_path / "XL_FY2569_draft-bill_21011_AMB.xlsx"
    wb.save(path)
    wb.close()

    flagged = [
        r for r in _records(path)
        if UNC_TABLE_BOUNDARY_AMBIGUOUS in r.uncertainty
    ]
    assert len(flagged) == 1
    assert flagged[0].needs_review, "ต้องขึ้นคิวมนุษย์"
    assert flagged[0].row_index > 0, "ต้องรู้ตำแหน่งแถว"
    assert flagged[0].raw_label, "ต้องเก็บข้อความดิบ"


# ══════════════════════════════ ④ body ของตารางต้องไม่ซ้อนกัน
@needs_sources
def test_logical_table_bodies_never_overlap():
    """🔴 พิสูจน์ว่า body ของตารางในชีตเดียวกันไม่ซ้อนกัน

    รวมถึง **ไม่กินบล็อกหัว** ของตารางอื่น — นี่คือ invariant ที่ blocker #4
    ละเมิดอยู่ และเป็นตัวกันไม่ให้ข้อบกพร่องชนิดเดียวกันกลับมาอีก
    """
    from openpyxl import load_workbook

    checked = 0
    for name in FILES:
        wb = load_workbook(SOURCE_DIR / name, data_only=True)
        for ws in wb.worksheets:
            rows = [[c.value for c in r] for r in ws.iter_rows()]
            spans = []
            for t in find_year_tables(rows):
                spans.append(("year", t.block_start, t.last_data_row))
            for t in find_category_tables(rows):
                if t.boundary_ambiguous:
                    continue
                spans.append(("category", t.header_row, t.last_data_row))

            for i, (kind_a, a1, a2) in enumerate(spans):
                for kind_b, b1, b2 in spans[i + 1:]:
                    overlap = max(a1, b1) <= min(a2, b2)
                    assert not overlap, (
                        f"{name}!{ws.title}: {kind_a} [{a1}-{a2}] ซ้อนกับ "
                        f"{kind_b} [{b1}-{b2}]"
                    )
                    checked += 1
        wb.close()
    assert checked > 0, "ต้องมีคู่ให้ตรวจจริง"


@needs_sources
def test_real_workbooks_have_no_valueless_category_records():
    """🔴 30 record หมวดที่ไม่มีค่าต้องหายไปหมด — เป็นตัววัดตรงของ blocker #4"""
    for name in FILES:
        empty = [
            r for r in _records(SOURCE_DIR / name)
            if r.row_kind == ROW_KIND_VALUE and r.budget_category is not None
            and r.value_decimal is None
        ]
        assert empty == [], f"{name}: เหลือ {len(empty)} รายการ"


@needs_sources
def test_real_workbooks_still_detect_nineteen_category_tables():
    """จำนวนตารางหมวดต้องไม่ขยับ — การแก้ขอบเขตห้ามทำให้ตารางหาย"""
    from openpyxl import load_workbook

    total = 0
    for name in FILES:
        wb = load_workbook(SOURCE_DIR / name, data_only=True)
        for ws in wb.worksheets:
            rows = [[c.value for c in r] for r in ws.iter_rows()]
            total += len(find_category_tables(rows))
        wb.close()
    assert total == 19, f"จำนวนตารางหมวดเปลี่ยนไป: {total}"


@needs_sources
def test_real_category_rows_still_carry_a_total_column():
    """ทุกแถวหมวดที่เหลือต้องมีคอลัมน์ ``รวม`` — ยืนยันว่าเหลือแต่ของจริง"""
    for name in FILES:
        rows = {}
        for r in _records(SOURCE_DIR / name):
            if r.row_kind == ROW_KIND_VALUE and r.budget_category is not None:
                rows.setdefault((r.sheet_name_actual, r.row_index), set()).add(
                    r.budget_category
                )
        for key, cats in rows.items():
            assert CATEGORY_TOTAL in cats, f"{name}!{key}: {sorted(cats)}"
