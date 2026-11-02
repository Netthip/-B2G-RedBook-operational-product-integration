# -*- coding: utf-8 -*-
"""T1B — boundary cases จาก ``BO REVIEW — CONDITIONAL PASS`` (2 กันยายน 2569)

ปิดสามช่องโหว่ที่ ``306 passed`` รอบก่อน **ยังพิสูจน์ไม่ได้**

① หัวคอลัมน์ที่ไม่รู้จักซึ่งวางอยู่ **ก่อน** หมวดที่รู้จักคอลัมน์แรก
② หัวคอลัมน์ที่ไม่รู้จักหลายคอลัมน์ถูกบีบเป็น ``UNRESOLVED`` เดียวกัน
③ semantic truth table ของ ``axis_valid`` — แกนกับฟิลด์ที่เติมต้องตรงกัน

🔒 การแก้ของรอบ BO REVIEW นี้อยู่นอกคีย์ทั้งหมด — คีย์ขึ้นเป็น ``t1b-key-0.2.0``
ในภายหลังจาก blocker #3 เท่านั้น (ดู ``test_t1b_shadow_blockers.py``)

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from dataclasses import replace
from decimal import Decimal

import pytest

from redbook.adapters.ao_workbook import AOWorkbookAdapter
from redbook.t1b.keys import PREVIOUS_KEY_VERSION
from redbook.t1b import (
    CATEGORY_INVESTMENT,
    CATEGORY_OPERATING,
    CATEGORY_TOTAL,
    CATEGORY_UNRESOLVED,
    DOCUMENT_LEVEL_AGENCY,
    KEY_VERSION,
    UNIT_MILLION_BAHT,
    T1BKey,
    compare,
    match_records,
)
from redbook.t1b.compare import F_AMBIGUOUS
from redbook.t1b.header import (
    _category_columns,
    _category_header_rows,
    find_category_tables,
)
from redbook.t1b.matching import _signature
from redbook.t1b.records import (
    AXIS_BUDGET_CATEGORY,
    AXIS_FISCAL_YEAR,
    AXIS_UNRESOLVED,
    ROW_KIND_VALUE,
    T1BRecord,
)

#: 🔴 ด่านตัวตนหน่วยงานเป็น **fail-closed** ตั้งแต่ BO REVIEW (Issue #1) —
#: สอง record ที่ไม่มี ``agency_identity`` จะไม่ถูกจับคู่อัตโนมัติอีกต่อไป
#:
#: ชุดทดสอบในไฟล์นี้วัด *ขอบของหมวดงบรายจ่ายที่ resolve ไม่ได้* ไม่ได้วัดด่านตัวตน
#: (ด่านตัวตนมีชุดของตัวเองที่ ``tests/test_t1b_identity_gate.py``)
#: fixture จึงต้องประกาศให้ชัดว่าเป็น **หน่วยงานเดียวกันที่ยืนยันแล้ว**
#: ซึ่งเป็นการทำสมมติฐานเดิมที่ซ่อนอยู่ให้เห็นชัด ไม่ใช่การผ่อนด่าน
AGENCY = "สถาบันทดสอบ"

# หัวคอลัมน์สมมติที่ไม่อยู่ใน canonical set — 🔴 SYNTHETIC TEST FIXTURE
UNKNOWN_EARLY = "งบภารกิจเฉพาะกิจ"      # วางไว้ **ก่อน** หมวดที่รู้จักตัวแรก
UNKNOWN_LATE = "งบชดใช้เงินคงคลัง"       # วางไว้หลังหมวดที่รู้จัก


def _build_workbook(tmp_path):
    """🔴 **SYNTHETIC TEST FIXTURE** — แฟ้มจำลอง ไม่ใช่แฟ้มจริง

    ห้ามรายงานผลจากชุดนี้ว่าเป็นข้อผิดพลาดที่พบใน workbook จริง
    (คำสั่ง Gift · Q-08 · master directive)

    ผังหัวตาราง (แถว 4)::

        A=กิจกรรม  F=งบภารกิจเฉพาะกิจ  G=งบดำเนินงาน  H=งบลงทุน
                   I=งบชดใช้เงินคงคลัง  J=รวม

    คอลัมน์ ``F`` อยู่ **ก่อน** หมวดที่รู้จักตัวแรก (``G``) — คือกรณี ①
    คอลัมน์ ``F`` กับ ``I`` เป็นหมวดที่ไม่รู้จัก **ทั้งคู่** — คือกรณี ②
    """
    import openpyxl

    wb = openpyxl.Workbook()
    # 🔴 ชีตปกจำเป็นตั้งแต่ด่านตัวตนหน่วยงานเป็น fail-closed (BO REVIEW · Issue #1)
    # ถ้าไม่มี ตัวตนจะอ่านไม่ได้ ⇒ ด่านปฏิเสธการเทียบ ⇒ ทดสอบนี้จะวัดด่านตัวตน
    # แทนที่จะวัดขอบของหมวดที่ resolve ไม่ได้ ซึ่งเป็นสิ่งที่ตั้งใจวัดจริง
    cover = wb.active
    cover.title = "ปก"
    cover["A2"] = "กระทรวงทดสอบ"
    cover["A3"] = AGENCY
    cover["A5"] = "ปี 2569"
    ws = wb.create_sheet("Sheet7_2")
    ws["A1"] = "7.2 แผนงานพื้นฐานทดสอบ"
    ws["A2"] = "5. เป้าหมายการให้บริการหน่วยงาน"
    ws["J3"] = "หน่วย : ล้านบาท"
    ws["A4"] = "กิจกรรม"
    ws["F4"] = UNKNOWN_EARLY
    ws["G4"], ws["H4"] = "งบดำเนินงาน", "งบลงทุน"
    ws["I4"], ws["J4"] = UNKNOWN_LATE, "รวม"
    ws["A5"] = "รวมทั้งสิ้น"
    ws["F5"], ws["G5"], ws["H5"] = 77.0, 1.0, 2.0
    ws["I5"], ws["J5"] = 99.0, 102.0
    path = tmp_path / "XL_FY2569_draft-bill_21011_TEST.xlsx"
    wb.save(path)
    wb.close()
    return path


def _values(path):
    records = [e.canonical_record for e in AOWorkbookAdapter().extract(path)]
    return [r for r in records if r.row_kind == ROW_KIND_VALUE]


# ═════════════════════════════ ① unknown column ก่อนหมวดที่รู้จักคอลัมน์แรก
def test_bo_b1_unknown_column_before_first_known_is_captured():
    """🔴 เดิมเริ่มนับที่หมวดที่รู้จักตัวแรก ⇒ คอลัมน์ก่อนหน้านั้นหายเงียบ"""
    header = ["รายการ", UNKNOWN_EARLY, "งบดำเนินงาน", "งบลงทุน", "รวม"]
    got = {c.index: c for c in _category_columns(header)}

    assert 1 in got, "คอลัมน์ที่ไม่รู้จักซึ่งอยู่ก่อนหมวดแรกต้องไม่ถูกข้าม"
    assert got[1].canonical == CATEGORY_UNRESOLVED
    assert got[1].raw_header == UNKNOWN_EARLY
    assert set(got) == {1, 2, 3, 4}


def test_bo_b1_label_column_is_never_a_value_column():
    """ขอบซ้ายของเขตค่าคือคอลัมน์ป้ายรายการ — ป้ายต้องไม่กลายเป็นหมวด

    ``ผลผลิต / โครงการ`` เป็นข้อความจริงที่พบในคอลัมน์ ``A`` ของแฟ้มจริง
    ถ้าถูกจับเป็นคอลัมน์ค่า คิวมนุษย์จะเต็มไปด้วยรายการปลอม
    """
    header = ["ผลผลิต / โครงการ", "งบดำเนินงาน", "งบลงทุน"]
    indexes = {c.index for c in _category_columns(header)}

    assert 0 not in indexes
    assert indexes == {1, 2}


def test_bo_b1_unit_column_is_never_a_value_column():
    """คอลัมน์ ``หน่วยนับ`` เป็นคอลัมน์โครงสร้าง ไม่ใช่คอลัมน์ค่า"""
    header = ["รายการ", "หน่วยนับ", "งบดำเนินงาน", "งบลงทุน"]
    indexes = {c.index for c in _category_columns(header)}

    assert indexes == {2, 3}


def test_bo_b1_still_requires_a_known_category_to_be_a_category_table():
    """ไม่มีหมวดที่รู้จักเลย = ไม่ใช่ตารางชนิดนี้ — กันการจับผิดเป็นวงกว้าง"""
    assert _category_columns(["รายการ", "ปี 2569", "ปี 2570"]) == ()


def test_bo_b1_e2e_value_before_first_known_survives_to_human_review(tmp_path):
    """end-to-end · ค่า ``77.0`` ที่อยู่ก่อนหมวดแรกต้องถึงคิวมนุษย์ครบถ้วน"""
    values = _values(_build_workbook(tmp_path))

    assert {float(r.value_decimal) for r in values} == {77.0, 1.0, 2.0, 99.0, 102.0}

    early = [r for r in values if r.budget_category_raw == UNKNOWN_EARLY]
    assert len(early) == 1, "คอลัมน์ก่อนหมวดแรกต้องได้ record ของตัวเอง"
    rec = early[0]

    assert rec.budget_category == CATEGORY_UNRESOLVED
    assert float(rec.value_decimal) == 77.0
    assert float(rec.raw_value) == 77.0
    assert rec.cell_ref == "F5"
    assert rec.needs_review
    assert "budget_category_unresolved" in rec.uncertainty
    # 🔴 ห้ามเดาหมวดที่ใกล้เคียงที่สุด
    assert rec.budget_category not in (
        CATEGORY_OPERATING, CATEGORY_INVESTMENT, CATEGORY_TOTAL,
    )


# ═════════════════════════════ ② unknown สองคอลัมน์ต้องไม่ถูกบีบเป็นรายการเดียว
def _unknown_rec(raw_header, value):
    return T1BRecord(
        key=T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                   agency_identity=AGENCY,
                   sheet_role="SECTION_07_PROJECT",
                   section_title_norm="โครงการทดสอบ",
                   parent_plan_norm="แผนงานทดสอบ",
                   row_label_norm="เงินงบประมาณ"),
        row_kind=ROW_KIND_VALUE, comparison_axis=AXIS_BUDGET_CATEGORY,
        budget_category=CATEGORY_UNRESOLVED, budget_category_raw=raw_header,
        declared_unit=UNIT_MILLION_BAHT, is_monetary=True,
        value_decimal=Decimal(value), raw_value=value,
        sheet_name_actual="Sheet7_2", cell_ref="F5", row_index=5,
        uncertainty=("budget_category_unresolved",),
    )


def test_bo_b2_two_unknown_headers_do_not_collide_in_signature():
    """🔴 หัวคอลัมน์ไม่รู้จักคนละอันต้องมีลายเซ็นคนละอัน — collision = 0"""
    a = _unknown_rec(UNKNOWN_LATE, "99.0")
    b = _unknown_rec(UNKNOWN_EARLY, "88.0")

    assert _signature(a) != _signature(b)
    assert len({_signature(a), _signature(b)}) == 2


def test_bo_b2_known_categories_still_compare_by_canonical_code():
    """ตัวแยกหัวคอลัมน์ดิบใช้เฉพาะกรณี ``UNRESOLVED`` — สะกดต่างกันยังจับคู่ได้"""
    base = replace(_unknown_rec("งบลงทุน", "1.0"),
                   budget_category=CATEGORY_INVESTMENT, uncertainty=())
    curr = replace(_unknown_rec("งบลงทุน ", "2.0"),
                   budget_category=CATEGORY_INVESTMENT, uncertainty=())

    assert _signature(base) == _signature(curr)
    assert len(match_records([base], [curr]).matched) == 1


def test_bo_b2_unknown_categories_never_auto_match_each_other():
    """🔴 ห้าม auto-match / auto-reconcile หัวคอลัมน์ไม่รู้จักสองอันเข้าด้วยกัน"""
    base = [_unknown_rec(UNKNOWN_LATE, "99.0")]
    curr = [_unknown_rec(UNKNOWN_EARLY, "88.0")]
    result = match_records(base, curr)

    assert result.matched == [], "หมวดที่ยัง resolve ไม่ได้ต้องไม่ถูกจับคู่อัตโนมัติ"
    assert len(result.needs_human) == 2
    assert result.accounted() == 2


def test_bo_b2_identical_unknown_header_is_still_held_for_human():
    """แม้หัวคอลัมน์ดิบตรงกันทั้งสองฝั่ง ก็ยังต้องรอมนุษย์ตัดสินก่อน"""
    result = match_records(
        [_unknown_rec(UNKNOWN_LATE, "99.0")],
        [_unknown_rec(UNKNOWN_LATE, "77.0")],
    )

    assert result.matched == []
    assert len(result.needs_human) == 2


def test_bo_b2_hold_out_does_not_depend_on_the_uncertainty_flag():
    """ด่านกันที่ชั้นจับคู่ต้องทำงานแม้ชั้นสกัดในอนาคต **ลืมติดธง**"""
    unflagged = replace(_unknown_rec(UNKNOWN_LATE, "99.0"), uncertainty=())

    assert unflagged.uncertainty == ()
    assert unflagged.needs_review, "record contract ต้องบังคับเองด้วย"

    result = match_records([unflagged], [replace(unflagged, raw_value="1.0")])
    assert result.matched == []
    assert len(result.needs_human) == 2


def test_bo_b2_each_unknown_gets_its_own_provenance_trace():
    """แต่ละใบต้องชี้หัวคอลัมน์ดิบและค่าของ **ตัวเอง** ถูกต้อง"""
    base = [_unknown_rec(UNKNOWN_LATE, "99.0"),
            _unknown_rec(UNKNOWN_EARLY, "88.0")]
    findings = [f for f in compare(match_records(base, [])).findings
                if f.finding_type == F_AMBIGUOUS]

    assert len(findings) == 2
    traced = {f.budget_category_raw: f for f in findings}
    assert set(traced) == {UNKNOWN_LATE, UNKNOWN_EARLY}

    assert traced[UNKNOWN_LATE].baseline_value == Decimal("99.0")
    assert traced[UNKNOWN_EARLY].baseline_value == Decimal("88.0")
    for raw, finding in traced.items():
        assert finding.requires_human_decision
        assert finding.baseline_location is not None
        assert finding.comparison_axis == AXIS_BUDGET_CATEGORY
        assert finding.budget_category == CATEGORY_UNRESOLVED
        assert raw in finding.detail, "เหตุผลในคิวต้องระบุหัวคอลัมน์ดิบ"


def test_bo_b2_e2e_two_unknown_columns_produce_two_records(tmp_path):
    """end-to-end · สองคอลัมน์ที่ไม่รู้จักในแถวเดียวกัน = สอง record สองร่องรอย"""
    values = _values(_build_workbook(tmp_path))
    unknown = [r for r in values if r.budget_category == CATEGORY_UNRESOLVED]

    assert len(unknown) == 2, "ต้องไม่ถูกบีบเหลือรายการเดียว"
    assert len({_signature(r) for r in unknown}) == 2, "collision ต้องเป็น 0"

    by_raw = {r.budget_category_raw: r for r in unknown}
    assert set(by_raw) == {UNKNOWN_EARLY, UNKNOWN_LATE}
    assert float(by_raw[UNKNOWN_EARLY].value_decimal) == 77.0
    assert float(by_raw[UNKNOWN_LATE].value_decimal) == 99.0
    assert by_raw[UNKNOWN_EARLY].cell_ref == "F5"
    assert by_raw[UNKNOWN_LATE].cell_ref == "I5"


def test_bo_b2_e2e_accounting_stays_complete(tmp_path):
    """end-to-end · มีหมวดที่ resolve ไม่ได้สองคอลัมน์ accounting ต้องยังครบ"""
    values = _values(_build_workbook(tmp_path))
    result = match_records(values, [])

    assert result.accounted() == len(values)
    assert result.matched == []
    assert len([s for s in result.needs_human
                if s.record.budget_category == CATEGORY_UNRESOLVED]) == 2


# ═════════════════════════════ ③ semantic truth table ของ axis_valid
def _axis_rec(axis, year, category):
    return T1BRecord(
        key=T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                   agency_identity=AGENCY,
                   sheet_role="SECTION_05", row_label_norm="รวมทั้งสิ้น"),
        row_kind=ROW_KIND_VALUE, comparison_axis=axis,
        fiscal_year=year, budget_category=category,
        declared_unit=UNIT_MILLION_BAHT, is_monetary=True,
        value_decimal=Decimal("1.0"), raw_value="1.0",
        sheet_name_actual="Sheet5", cell_ref="C6", row_index=6,
    )


@pytest.mark.parametrize(
    "axis, year, category, expected",
    [
        # แกนตรงกับฟิลด์ที่เติม — ถูกต้องเพียงสองกรณีนี้เท่านั้น
        (AXIS_FISCAL_YEAR, 2570, None, True),
        (AXIS_BUDGET_CATEGORY, None, CATEGORY_INVESTMENT, True),
        # 🔴 แกนกับฟิลด์ที่เติม **สลับกัน** — มีค่าเดียวแต่ความหมายผิดแกน
        (AXIS_FISCAL_YEAR, None, CATEGORY_INVESTMENT, False),
        (AXIS_BUDGET_CATEGORY, 2570, None, False),
        # มีทั้งสองค่า
        (AXIS_FISCAL_YEAR, 2570, CATEGORY_INVESTMENT, False),
        (AXIS_BUDGET_CATEGORY, 2570, CATEGORY_INVESTMENT, False),
        # ไม่มีทั้งสองค่า
        (AXIS_FISCAL_YEAR, None, None, False),
        (AXIS_BUDGET_CATEGORY, None, None, False),
        # แกนไม่ระบุ
        (AXIS_UNRESOLVED, 2570, None, False),
        (AXIS_UNRESOLVED, None, CATEGORY_INVESTMENT, False),
    ],
)
def test_bo_b3_axis_semantic_truth_table(axis, year, category, expected):
    """🔴 XOR อย่างเดียวไม่พอ — แกนต้อง **ตรงกับ** ฟิลด์ที่ถูกเติม"""
    rec = _axis_rec(axis, year, category)

    assert rec.axis_valid is expected, (
        f"axis={axis} year={year} category={category} → {rec.axis_valid} "
        f"แต่คาด {expected}"
    )
    if not expected:
        assert rec.needs_review
        assert match_records([rec], [_axis_rec(axis, year, category)]).matched == []


def test_bo_b3_key_version_unchanged():
    """🔒 คีย์ที่ตรึงไว้ต้องเป็นค่าเดียวกับที่ประกาศ และเวอร์ชันเก่าต้องไม่หาย"""
    assert KEY_VERSION == "t1b-key-0.2.0"
    assert PREVIOUS_KEY_VERSION == "t1b-key-0.1.0"


# ═════════════ ③ contract "known >= 1" ต้องตรงกันทุกชั้นของ detector
#
# 🔴 BO REVIEW รอบสอง (2 ก.ย.): `_category_columns()` รับ known >= 1
# แต่เส้นทางจริงต้องผ่าน `_category_header_rows()` ซึ่งเดิมบังคับ known >= 2
# ⇒ ตารางที่มีหมวดที่รู้จักเพียงหมวดเดียวถูกตัดทิ้ง **ทั้งตาราง** ก่อนถึงชั้นนั้น

def _build_single_known_workbook(tmp_path):
    """🔴 **SYNTHETIC TEST FIXTURE** — ตาราง ``unknown | known×1 | unknown``

    ห้ามรายงานผลจากชุดนี้ว่าเป็นข้อผิดพลาดที่พบใน workbook จริง
    """
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet7_2"
    # 🔴 ปีงบประมาณในหัวเรื่อง — เอกสารจริงมีปีบริบทเสมอ (blocker #1)
    #    ``canonical_section`` ตัดปีออกจากคีย์อยู่แล้ว จึงไม่กระทบ identity
    ws["A1"] = "7.2 แผนงานพื้นฐานทดสอบ ประจำปีงบประมาณ พ.ศ. 2569"
    ws["A2"] = "5. เป้าหมายการให้บริการหน่วยงาน"
    ws["H3"] = "หน่วย : ล้านบาท"
    ws["A4"] = "กิจกรรม"
    ws["F4"], ws["G4"], ws["H4"] = UNKNOWN_EARLY, "งบลงทุน", UNKNOWN_LATE
    ws["A5"] = "รวมทั้งสิ้น"
    ws["F5"], ws["G5"], ws["H5"] = 77.0, 2.0, 99.0
    path = tmp_path / "XL_FY2569_draft-bill_21011_SINGLE.xlsx"
    wb.save(path)
    wb.close()
    return path


def test_bo_b4_single_known_category_table_is_detected():
    """หมวดที่รู้จักหมวดเดียวก็ต้องนับเป็นตาราง — ไม่ใช่ตัดทิ้งทั้งตาราง"""
    rows = [
        ["กิจกรรม", UNKNOWN_EARLY, "งบลงทุน", UNKNOWN_LATE],
        ["รวมทั้งสิ้น", 77.0, 2.0, 99.0],
    ]

    assert _category_header_rows(rows) == [1]
    tables = find_category_tables(rows)
    assert len(tables) == 1
    assert {c.canonical for c in tables[0].columns} == {
        CATEGORY_UNRESOLVED, CATEGORY_INVESTMENT,
    }


def test_bo_b4_e2e_single_known_category_reaches_human_review(tmp_path):
    """end-to-end · ตาราง ``unknown | known×1 | unknown`` ต้องไม่หายทั้งตาราง"""
    values = _values(_build_single_known_workbook(tmp_path))

    assert {float(r.value_decimal) for r in values} == {77.0, 2.0, 99.0}

    known = [r for r in values if r.budget_category == CATEGORY_INVESTMENT]
    assert len(known) == 1, "หมวดที่รู้จักต้องยัง extract ได้ตามปกติ"
    assert float(known[0].value_decimal) == 2.0
    assert not known[0].needs_review

    unknown = [r for r in values if r.budget_category == CATEGORY_UNRESOLVED]
    assert len(unknown) == 2
    assert all(r.needs_review for r in unknown)
    by_raw = {r.budget_category_raw: float(r.value_decimal) for r in unknown}
    assert by_raw == {UNKNOWN_EARLY: 77.0, UNKNOWN_LATE: 99.0}


@pytest.mark.parametrize(
    "row, why",
    [
        (["รวม", 100.0, 200.0], "แถวข้อมูลที่ป้ายบังเอิญเป็นชื่อหมวดพอดี"),
        (["รวมงบประมาณทั้งสิ้นของหน่วยงาน", 1.0, 2.0], "ป้ายเป็นประโยคยาว"),
        (["ผลผลิต / โครงการ", "รวม", 5.0], "มีหมวดเดียวในเขตค่า ไม่มีหัวข้อความอื่น"),
        (["หมายเหตุ", None, None], "ไม่มีหมวดที่รู้จักเลย"),
    ],
)
def test_bo_b4_ordinary_row_is_never_mistaken_for_a_category_table(row, why):
    """🔴 negative — แถวข้อความทั่วไปที่มีชื่อหมวดคำเดียวต้องไม่ถูกจับเป็นตาราง

    นี่คือเหตุผลที่เดิมตั้ง ``known >= 2`` ไว้ · เมื่อผ่อนเป็น ``known >= 1``
    จึงต้องมีตัวกันใหม่: หมวดต้องอยู่ใน **เขตค่า** และเขตค่าต้องมีคอลัมน์
    หัวข้อความอย่างน้อย ``MIN_CATEGORY_HEADER_TEXTS`` คอลัมน์
    """
    rows = [row, ["ถัดไป", 1.0, 2.0]]

    assert _category_header_rows(rows) == [], why
    assert find_category_tables(rows) == [], why


def test_bo_b4_detector_does_not_steal_year_table_headers():
    """หัวตาราง **รายปี** ที่บังเอิญมีคำว่า ``รวม`` ต้องไม่ถูกจับเป็นตารางหมวด"""
    rows = [
        ["รายการ", "รวม", "ปี 2569", "ปี 2570", "ปี 2571"],
        ["รวมทั้งสิ้น", 3.0, 1.0, 1.0, 1.0],
    ]

    assert _category_header_rows(rows) == []


def test_bo_b4_real_header_rows_may_contain_numbers():
    """🔴 ห้ามใช้ "แถวหัวต้องไม่มีตัวเลข" เป็นเงื่อนไข

    ตรวจแฟ้มจริงแล้วพบหัวตาราง 2 ใน 19 แถวมีตัวเลขปนในเขตค่า
    (``Sheet7.2`` และ ``Sheet7.3.1`` ของ FY2570 · 21016)
    ถ้าใช้เงื่อนไขนั้นจะตัดตารางจริงทิ้ง
    """
    rows = [
        ["กิจกรรม", "งบดำเนินงาน", "งบลงทุน", "รวม", 1],
        ["รวมทั้งสิ้น", 1.0, 2.0, 3.0, None],
    ]

    assert _category_header_rows(rows) == [1]


# ═════════════ ④ end-to-end จริง: extract -> match -> compare -> Finding
def _findings_from(path):
    records = [e.canonical_record for e in AOWorkbookAdapter().extract(path)]
    result = match_records(records, [])
    return records, result, compare(result).findings


def test_bo_b5_e2e_workbook_to_finding_keeps_both_unknown_values(tmp_path):
    """🔴 หนึ่ง test เดียวไล่ตั้งแต่ ``extract()`` จนถึง ``Finding``

    ก่อนหน้านี้การพิสูจน์ถูกแบ่งเป็นช่วง — extract จบที่ record · finding
    เริ่มจาก record ที่สร้างด้วยมือ ⇒ ไม่มีหลักฐานว่าสายงานทั้งเส้นต่อกันจริง
    """
    records, result, findings = _findings_from(_build_workbook(tmp_path))

    ambiguous = [
        f for f in findings
        if f.finding_type == F_AMBIGUOUS
        and f.budget_category == CATEGORY_UNRESOLVED
    ]
    assert len(ambiguous) == 2, "หมวดที่ resolve ไม่ได้สองคอลัมน์ = สองใบพอดี"

    traced = {f.budget_category_raw: f for f in ambiguous}
    assert set(traced) == {UNKNOWN_EARLY, UNKNOWN_LATE}

    # ค่าต้องไม่หายและ **ไม่สลับกัน**
    assert traced[UNKNOWN_EARLY].baseline_value == Decimal("77.0")
    assert traced[UNKNOWN_LATE].baseline_value == Decimal("99.0")
    assert traced[UNKNOWN_EARLY].baseline_location.cell == "F5"
    assert traced[UNKNOWN_LATE].baseline_location.cell == "I5"
    assert float(traced[UNKNOWN_EARLY].baseline_location.raw_value) == 77.0
    assert float(traced[UNKNOWN_LATE].baseline_location.raw_value) == 99.0

    for raw, finding in traced.items():
        assert finding.requires_human_decision is True
        assert finding.comparison_axis == AXIS_BUDGET_CATEGORY
        assert raw in finding.detail

    # ต้องไม่หลุดไปอยู่ในกลุ่มที่ระบบตัดสินเอง
    unknown_ids = {
        id(r) for r in records if r.budget_category == CATEGORY_UNRESOLVED
    }
    assert unknown_ids
    for pair in result.matched:
        assert id(pair.baseline) not in unknown_ids
        assert id(pair.current) not in unknown_ids
    for rec in result.baseline_only + result.current_only:
        assert id(rec) not in unknown_ids

    assert result.accounted() == len(records)


def test_bo_b5_e2e_single_known_workbook_to_finding(tmp_path):
    """end-to-end เส้นเดียวกัน สำหรับตาราง ``unknown | known×1 | unknown``"""
    records, result, findings = _findings_from(
        _build_single_known_workbook(tmp_path)
    )

    ambiguous = [
        f for f in findings
        if f.finding_type == F_AMBIGUOUS
        and f.budget_category == CATEGORY_UNRESOLVED
    ]
    assert len(ambiguous) == 2

    traced = {f.budget_category_raw: f.baseline_value for f in ambiguous}
    assert traced == {UNKNOWN_EARLY: Decimal("77.0"), UNKNOWN_LATE: Decimal("99.0")}
    assert result.accounted() == len(records)
    assert all(f.requires_human_decision for f in ambiguous)
