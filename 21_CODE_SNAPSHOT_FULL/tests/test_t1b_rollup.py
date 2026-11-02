# -*- coding: utf-8 -*-
"""T1B — การกระทบยอด (roll-up / reconciliation)

ปลดโดย ``BO FINAL PASS`` (2 กันยายน 2569 · ผูกกับ commit ``50a97de``)

ข้อจำกัดที่ผูกกับคำตัดสินนั้นและถูกบังคับด้วย test ในไฟล์นี้

* 🔒 คีย์ที่ตรึงไว้ไม่ถูกแตะโดย roll-up
* 🔴 ``UNRESOLVED`` ห้ามเข้า roll-up อัตโนมัติ
* รักษา raw provenance ทุกชั้น — ``source_file`` · ``source_hash`` · ชีต · เซลล์ · ค่าดิบ
* **ทุก record ต้อง accounted ห้าม silent-drop**

🔴 **ไฟล์นี้เคยล็อกพฤติกรรมที่ผิดไว้เอง** (BO REVIEW · 2 ก.ย. 2569) —
`test_unresolved_unit_records_never_enter_a_sum` เดิมยืนยันว่าการ **ทิ้ง**
record ที่หน่วยยัง resolve ไม่ได้แล้วคืน ``OK`` เป็นพฤติกรรมที่ถูกต้อง
ซึ่งขัดกับข้อจำกัดข้อ 4 ตรง ๆ · ตอนนี้กลับด้านแล้ว

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import os
from decimal import Decimal
from pathlib import Path

import pytest

from redbook.adapters.ao_workbook import AOWorkbookAdapter
from redbook.t1b import (
    CATEGORY_INVESTMENT,
    CATEGORY_OPERATING,
    CATEGORY_TOTAL,
    CATEGORY_UNRESOLVED,
    DOCUMENT_LEVEL_AGENCY,
    KEY_VERSION,
    UNIT_MILLION_BAHT,
    T1BKey,
)
from redbook.t1b.records import (
    AXIS_BUDGET_CATEGORY,
    AXIS_FISCAL_YEAR,
    ROW_KIND_VALUE,
    T1BRecord,
)
from redbook.t1b.rollup import (
    QUANTUM,
    ROLLUP_VERSION,
    RULE_CATEGORY_TOTAL,
    RULE_CROSS_SHEET_GRAND,
    RULE_FUNDING_LINE_SUM,
    RULE_GRAND_SPLIT,
    STATUS_HUMAN_REVIEW,
    STATUS_INCOMPLETE,
    STATUS_MISMATCH,
    STATUS_OK,
    STATUS_ROUNDING_RESIDUE_CANDIDATE,
    check_rollups,
    check_rollups_for_envelopes,
)
from redbook.t1b.units import UNIT_BAHT, UNIT_UNRESOLVED, quantum_for

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

SRC_FILE = "XL_FY2569_draft-bill_21011_TEST.xlsx"
SRC_HASH = "a" * 64


def _run(records):
    return check_rollups(records, source_file=SRC_FILE, source_hash=SRC_HASH)


def _cat(label, category, value, *, row=11, cell="C11", raw="งบลงทุน",
         sheet="Sheet6", unit=UNIT_MILLION_BAHT,
         axis=AXIS_BUDGET_CATEGORY, year=None):
    return T1BRecord(
        key=T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                   sheet_role="SECTION_06", row_label_norm=label),
        row_kind=ROW_KIND_VALUE, comparison_axis=axis, fiscal_year=year,
        budget_category=category, budget_category_raw=raw,
        declared_unit=unit, is_monetary=True,
        value_decimal=Decimal(value), raw_value=value,
        sheet_name_actual=sheet, cell_ref=cell, row_index=row,
    )


def _year(label, value, *, year=2569, hierarchy=(), sheet="Sheet5",
          cell="D6", row=6, role="SECTION_05", unit=UNIT_MILLION_BAHT,
          axis=AXIS_FISCAL_YEAR, category=None, decl=None):
    return T1BRecord(
        key=T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                   sheet_role=role, hierarchy_path=hierarchy,
                   row_label_norm=label),
        row_kind=ROW_KIND_VALUE, comparison_axis=axis,
        fiscal_year=year, fiscal_year_label=f"ปี {year}",
        budget_category=category, declared_unit=unit, is_monetary=True,
        value_decimal=Decimal(value), raw_value=value, raw_unit_cell=decl,
        sheet_name_actual=sheet, cell_ref=cell, row_index=row,
    )


def _only(result, rule):
    return [c for c in result.checks if c.rule == rule]


def _values(check):
    """ค่าทุกตัวที่ปรากฏใน provenance ของชุดนี้ (ตัวตั้ง + ยอดอ้างอิง)"""
    return {str(c.value) for c in check.components + check.targets}


# ══════════════════════════════════ หมวดย่อยรวมกันได้ 'รวม'
def test_category_subtotals_matching_total_is_ok():
    recs = [
        _cat("รวมทั้งสิ้น", CATEGORY_OPERATING, "1.5000", cell="G11"),
        _cat("รวมทั้งสิ้น", CATEGORY_INVESTMENT, "2.5000", cell="H11"),
        _cat("รวมทั้งสิ้น", CATEGORY_TOTAL, "4.0000", cell="J11", raw="รวม"),
    ]
    checks = _only(_run(recs), RULE_CATEGORY_TOTAL)

    assert len(checks) == 1
    assert checks[0].status == STATUS_OK
    assert checks[0].computed == Decimal("4.0000")
    assert checks[0].difference == Decimal("0.0000")
    assert not checks[0].requires_human_decision


def test_category_subtotals_not_matching_total_is_a_material_mismatch():
    recs = [
        _cat("รวมทั้งสิ้น", CATEGORY_OPERATING, "1.5000", cell="G11"),
        _cat("รวมทั้งสิ้น", CATEGORY_INVESTMENT, "2.5000", cell="H11"),
        _cat("รวมทั้งสิ้น", CATEGORY_TOTAL, "9.9999", cell="J11", raw="รวม"),
    ]
    check = _only(_run(recs), RULE_CATEGORY_TOTAL)[0]

    assert check.status == STATUS_MISMATCH
    assert check.difference == Decimal("5.9999")
    assert check.requires_human_decision


# ══════════════════════════════════ 🔴 provenance ต้องย้อนถึงต้นทางจริง
def test_components_trace_back_to_source_file_hash_cell_and_raw_value():
    """🔴 BO REVIEW — ต้องย้อนถึง ``source_file``/``source_hash`` + เซลล์ + ค่าดิบ

    เดิมมีแค่ชีตกับเซลล์ ซึ่งชี้กลับแฟ้มต้นทางไม่ได้จริงเมื่อมีหลายแฟ้ม
    """
    recs = [
        _cat("รวมทั้งสิ้น", CATEGORY_OPERATING, "1.0000", cell="G11"),
        _cat("รวมทั้งสิ้น", CATEGORY_INVESTMENT, "2.0000", cell="H11"),
        _cat("รวมทั้งสิ้น", CATEGORY_TOTAL, "3.0000", cell="J11", raw="รวม"),
    ]
    check = _only(_run(recs), RULE_CATEGORY_TOTAL)[0]

    assert check.fully_traceable
    for comp in check.components + check.targets:
        assert comp.source_file == SRC_FILE
        assert comp.source_hash == SRC_HASH
        assert comp.sheet and comp.cell and comp.row > 0
        assert comp.raw_value is not None
        assert comp.declared_unit == UNIT_MILLION_BAHT
        assert comp.traceable


@needs_sources
def test_envelope_entry_point_supplies_real_source_hash():
    envelopes = AOWorkbookAdapter().extract(SOURCE_DIR / FILES[1])
    result = check_rollups_for_envelopes(envelopes)

    assert result.checks
    for check in result.checks:
        assert check.fully_traceable
        for comp in check.components + check.targets:
            assert comp.source_file == FILES[1]
            assert len(comp.source_hash) == 64


@needs_sources
def test_envelope_entry_point_refuses_mixed_workbooks():
    """🔴 การกระทบยอดต้องทำทีละสมุดงาน — ปนแฟ้มถือเป็นการใช้ผิดวิธี"""
    adapter = AOWorkbookAdapter()
    mixed = (adapter.extract(SOURCE_DIR / FILES[1])[:5]
             + adapter.extract(SOURCE_DIR / FILES[2])[:5])

    with pytest.raises(ValueError, match="หลายแฟ้ม"):
        check_rollups_for_envelopes(mixed)


# ══════════════════════════════════ 🔴 ห้าม silent-drop
def test_unit_unresolved_child_is_never_dropped_from_the_sum():
    """🔴 **test นี้เคยยืนยันพฤติกรรมที่ผิด** (BO REVIEW · 2 ก.ย. 2569)

    เดิม: subtotal 3 · ลูกปกติ 3 · ลูกหน่วยไม่ทราบ 500
    ⇒ ระบบ **ทิ้ง 500 เงียบ** แล้วคืน ``OK`` และ test เดิมยืนยันว่าถูกต้อง
    ซึ่งขัดกับข้อจำกัด "ทุก record ต้อง accounted" ตรง ๆ

    ที่ถูก: ทั้งชุดเป็น ``HUMAN_REVIEW`` · ``computed is None`` ·
    และค่า ``500`` ต้องยังอยู่ใน provenance ครบ
    """
    recs = [
        _year("รวมเงินงบประมาณ", "3.0000", cell="D7", row=7),
        _year("เงินงบประมาณ", "3.0000", cell="D10", row=10, hierarchy=("1",)),
        _year("เงินงบประมาณ", "500.0000", cell="D14", row=14, hierarchy=("2",),
              unit=UNIT_UNRESOLVED),
    ]
    check = _only(_run(recs), RULE_FUNDING_LINE_SUM)[0]

    assert check.status == STATUS_HUMAN_REVIEW
    assert check.computed is None, "ห้ามสรุปยอดเมื่อมีรายการที่บวกไม่ได้"
    assert check.requires_human_decision
    assert len(check.components) == 2, "ลูกทั้งสองต้องอยู่ครบ"
    assert "500.0000" in _values(check), "🔴 ค่า 500 ต้องไม่หายเงียบ"
    assert "D14" in check.detail and "หน่วย" in check.detail

    unusable = [c for c in check.components if not c.usable]
    assert len(unusable) == 1
    assert unusable[0].cell == "D14"
    assert unusable[0].value == Decimal("500.0000")
    assert unusable[0].unusable_reason


def test_non_monetary_record_is_never_dropped_from_the_sum():
    """แถวที่ไม่ใช่จำนวนเงิน (เช่นตัวชี้วัดร้อยละ) ก็ต้องไม่ถูกทิ้งเงียบ"""
    indicator = T1BRecord(
        key=T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                   sheet_role="SECTION_05", hierarchy_path=("2",),
                   row_label_norm="เงินงบประมาณ"),
        row_kind=ROW_KIND_VALUE, comparison_axis=AXIS_FISCAL_YEAR,
        fiscal_year=2569, declared_unit="ร้อยละ", is_monetary=False,
        value_decimal=Decimal("100.0000"), raw_value="100",
        sheet_name_actual="Sheet5", cell_ref="D14", row_index=14,
    )
    recs = [
        _year("รวมเงินงบประมาณ", "3.0000", cell="D7", row=7),
        _year("เงินงบประมาณ", "3.0000", cell="D10", row=10, hierarchy=("1",)),
        indicator,
    ]
    check = _only(_run(recs), RULE_FUNDING_LINE_SUM)[0]

    assert check.status == STATUS_HUMAN_REVIEW
    assert check.computed is None
    assert "100.0000" in _values(check)


# ══════════════════════════════════ 🔴 ชุดไม่ครบ ห้ามได้ OK
def test_grand_split_missing_one_side_is_incomplete():
    """มีแต่ 'ในงบ' ไม่มี 'นอกงบ' → ``INCOMPLETE`` **ห้าม OK**"""
    recs = [
        _year("รวมทั้งสิ้น", "3.0000", cell="D6", row=6),
        _year("รวมเงินงบประมาณ", "3.0000", cell="D7", row=7),
    ]
    check = _only(_run(recs), RULE_GRAND_SPLIT)[0]

    assert check.status == STATUS_INCOMPLETE
    assert check.computed is None, "ชุดไม่ครบ ห้ามสรุปยอด"
    assert check.requires_human_decision
    assert "รวมเงินนอกงบประมาณ" in check.detail


def test_grand_split_missing_grand_total_is_incomplete():
    """มีแถวแยกแหล่งเงินแต่ไม่มี 'รวมทั้งสิ้น' → ``INCOMPLETE``"""
    recs = [
        _year("รวมเงินงบประมาณ", "3.0000", cell="D7", row=7),
        _year("รวมเงินนอกงบประมาณ", "0.0000", cell="D8", row=8),
    ]
    check = _only(_run(recs), RULE_GRAND_SPLIT)[0]

    assert check.status == STATUS_INCOMPLETE
    assert "รวมทั้งสิ้น" in check.detail


def test_funding_subtotal_without_any_child_is_incomplete_not_silent():
    """🔴 เดิม ``continue`` เงียบ — ไม่มีผลตรวจสักรายการ"""
    recs = [_year("รวมเงินงบประมาณ", "3.0000", cell="D7", row=7)]
    checks = _only(_run(recs), RULE_FUNDING_LINE_SUM)

    assert len(checks) == 1, "ต้องมีผลตรวจหนึ่งรายการ ห้ามข้ามเงียบ"
    assert checks[0].status == STATUS_INCOMPLETE
    assert checks[0].computed is None
    assert "ไม่พบตัวตั้งเลย" in checks[0].detail


def test_duplicate_category_in_one_row_is_incomplete_and_keeps_both_values():
    """🔴 dict เดิม overwrite เงียบ ⇒ ค่าแรกหายไปทั้งค่า

    ก่อนแก้: หมวด ``OPERATING`` ปรากฏสองคอลัมน์ ระบบเก็บอันหลังทับอันแรก
    ⇒ ค่า ``1.0000`` หายไปโดยไม่มีร่องรอย และยังสรุปยอดต่อ
    """
    recs = [
        _cat("รวมทั้งสิ้น", CATEGORY_OPERATING, "1.0000", cell="G11"),
        _cat("รวมทั้งสิ้น", CATEGORY_OPERATING, "77.0000", cell="H11"),
        _cat("รวมทั้งสิ้น", CATEGORY_TOTAL, "78.0000", cell="J11", raw="รวม"),
    ]
    check = _only(_run(recs), RULE_CATEGORY_TOTAL)[0]

    assert check.status == STATUS_INCOMPLETE
    assert check.computed is None
    assert len(check.components) == 2
    assert {"1.0000", "77.0000"} <= _values(check), "🔴 ทั้งสองค่าต้องอยู่ครบ"
    assert "ซ้ำ" in check.detail
    assert "G11" in check.detail and "H11" in check.detail


def test_duplicate_subtotal_row_is_incomplete():
    """ป้ายยอดอ้างอิงซ้ำในชีต+ปีเดียวกัน → ``INCOMPLETE``"""
    recs = [
        _year("รวมเงินงบประมาณ", "3.0000", cell="D7", row=7),
        _year("รวมเงินงบประมาณ", "9.0000", cell="D8", row=8),
        _year("เงินงบประมาณ", "3.0000", cell="D10", row=10, hierarchy=("1",)),
    ]
    check = _only(_run(recs), RULE_FUNDING_LINE_SUM)[0]

    assert check.status == STATUS_INCOMPLETE
    assert check.computed is None
    assert {"3.0000", "9.0000"} <= _values(check)


def test_duplicate_cross_sheet_grand_total_is_incomplete():
    recs = [
        _year("รวมทั้งสิ้น", "1.0000", sheet="Sheet4", cell="D6", role="SECTION_04"),
        _year("รวมทั้งสิ้น", "2.0000", sheet="Sheet4", cell="E6", row=7,
              role="SECTION_04"),
        _year("รวมทั้งสิ้น", "1.0000", sheet="Sheet5", cell="D6", role="SECTION_05"),
    ]
    check = _only(_run(recs), RULE_CROSS_SHEET_GRAND)[0]

    assert check.status == STATUS_INCOMPLETE
    assert {"1.0000", "2.0000"} <= _values(check)


# ══════════════════════════════════ 🔴 UNRESOLVED ห้ามเข้า roll-up
def test_unresolved_category_is_never_summed_automatically():
    recs = [
        _cat("รวมทั้งสิ้น", CATEGORY_OPERATING, "1.0000", cell="G11"),
        _cat("รวมทั้งสิ้น", CATEGORY_UNRESOLVED, "99.0000", cell="I11",
             raw="งบชดใช้เงินคงคลัง"),
        _cat("รวมทั้งสิ้น", CATEGORY_TOTAL, "100.0000", cell="J11", raw="รวม"),
    ]
    check = _only(_run(recs), RULE_CATEGORY_TOTAL)[0]

    assert check.status == STATUS_HUMAN_REVIEW
    assert check.computed is None
    assert "งบชดใช้เงินคงคลัง" in check.detail
    assert "99.0000" in _values(check)


def test_unresolved_is_held_even_when_the_arithmetic_would_have_worked():
    recs = [
        _cat("รวมทั้งสิ้น", CATEGORY_OPERATING, "1.0000", cell="G11"),
        _cat("รวมทั้งสิ้น", CATEGORY_UNRESOLVED, "2.0000", cell="I11",
             raw="งบภารกิจเฉพาะกิจ"),
        _cat("รวมทั้งสิ้น", CATEGORY_TOTAL, "3.0000", cell="J11", raw="รวม"),
    ]
    check = _only(_run(recs), RULE_CATEGORY_TOTAL)[0]

    assert check.status == STATUS_HUMAN_REVIEW
    assert check.computed is None


def test_cross_unit_components_are_never_summed():
    recs = [
        _cat("รวมทั้งสิ้น", CATEGORY_OPERATING, "1.0000", cell="G11"),
        _cat("รวมทั้งสิ้น", CATEGORY_INVESTMENT, "2.0000", cell="H11",
             unit=UNIT_BAHT),
        _cat("รวมทั้งสิ้น", CATEGORY_TOTAL, "3.0000", cell="J11", raw="รวม"),
    ]
    check = _only(_run(recs), RULE_CATEGORY_TOTAL)[0]

    assert check.status == STATUS_HUMAN_REVIEW
    assert check.computed is None


# ══════════════════════════════════ กฎรายปี
def test_grand_total_splits_by_funding_source():
    recs = [
        _year("รวมทั้งสิ้น", "58.4401", cell="D6", row=6),
        _year("รวมเงินงบประมาณ", "58.4401", cell="D7", row=7),
        _year("รวมเงินนอกงบประมาณ", "0.0000", cell="D8", row=8),
    ]
    check = _only(_run(recs), RULE_GRAND_SPLIT)[0]

    assert check.status == STATUS_OK
    assert check.computed == Decimal("58.4401")


def test_grand_total_split_mismatch_is_reported():
    recs = [
        _year("รวมทั้งสิ้น", "60.0000", cell="D6", row=6),
        _year("รวมเงินงบประมาณ", "58.4401", cell="D7", row=7),
        _year("รวมเงินนอกงบประมาณ", "0.0000", cell="D8", row=8),
    ]
    check = _only(_run(recs), RULE_GRAND_SPLIT)[0]

    assert check.status == STATUS_MISMATCH
    assert check.difference == Decimal("1.5599")


def test_funding_lines_sum_to_sheet_subtotal():
    recs = [
        _year("รวมเงินงบประมาณ", "58.4401", cell="D7", row=7),
        _year("เงินงบประมาณ", "39.5670", cell="D10", row=10, hierarchy=("1",)),
        _year("เงินงบประมาณ", "18.8731", cell="D15", row=15, hierarchy=("2",)),
    ]
    check = _only(_run(recs), RULE_FUNDING_LINE_SUM)[0]

    assert check.status == STATUS_OK
    assert len(check.components) == 2


def test_different_years_are_never_mixed_in_one_sum():
    recs = [
        _year("รวมเงินงบประมาณ", "10.0000", cell="D7", row=7, year=2569),
        _year("เงินงบประมาณ", "10.0000", cell="D10", row=10,
              hierarchy=("1",), year=2569),
        _year("เงินงบประมาณ", "999.0000", cell="E10", row=10,
              hierarchy=("1",), year=2570),
    ]
    checks = {c.scope: c for c in _only(_run(recs), RULE_FUNDING_LINE_SUM)}

    # ปี 2569 ครบทั้งยอดย่อยและแถวลูก ⇒ ตรง · 999 ของปี 2570 ต้องไม่เข้ามาปน
    same_year = next(c for s, c in checks.items() if "2569" in s)
    assert same_year.status == STATUS_OK
    assert same_year.computed == Decimal("10.0000")
    assert "999.0000" not in _values(same_year)

    # ปี 2570 มีแถวลูกแต่ไม่มียอดย่อย ⇒ ต้องได้ผลตรวจของตัวเองเป็น INCOMPLETE
    # (พฤติกรรมใหม่ตาม BO REVIEW รอบสี่ — เดิมกลุ่มนี้หายเงียบทั้งกลุ่ม)
    other_year = next(c for s, c in checks.items() if "2570" in s)
    assert other_year.status == STATUS_INCOMPLETE
    assert "999.0000" in _values(other_year)


def test_grand_total_agrees_across_agency_sheets():
    recs = [
        _year("รวมทั้งสิ้น", "58.4401", sheet="Sheet4", cell="D6",
              role="SECTION_04"),
        _year("รวมทั้งสิ้น", "58.4401", sheet="Sheet5", cell="D6",
              role="SECTION_05"),
    ]
    assert _only(_run(recs), RULE_CROSS_SHEET_GRAND)[0].status == STATUS_OK


def test_plan_sheets_are_excluded_from_the_cross_sheet_rule():
    """🔴 ชีตแผนงาน ``7.x`` รายงานยอดของแผนตนเอง ไม่ใช่ยอดรวมหน่วยงาน"""
    recs = [
        _year("รวมทั้งสิ้น", "58.4401", sheet="Sheet5", cell="D6",
              role="SECTION_05"),
        _year("รวมทั้งสิ้น", "1.4499", sheet="Sheet7_2", cell="D6",
              role="SECTION_07_PLAN"),
    ]
    assert _only(_run(recs), RULE_CROSS_SHEET_GRAND) == []


def test_plan_sheet_without_funding_split_produces_no_split_check():
    """ชีตที่ไม่ได้แยกแหล่งเงินเลย = กฎนี้ไม่ใช้ — ไม่ใช่ ``INCOMPLETE``

    ถ้าใช้ ``รวมทั้งสิ้น`` เป็นตัวชี้ว่ากฎใช้ได้ จะได้ ``INCOMPLETE`` ปลอม
    จากชีต ``7.x`` จำนวนมาก (ตรวจแฟ้มจริงแล้วได้ 85 รายการ)
    """
    recs = [
        _year("รวมทั้งสิ้น", "1.4499", sheet="Sheet7_2", cell="D6",
              role="SECTION_07_PLAN"),
    ]
    assert _only(_run(recs), RULE_GRAND_SPLIT) == []


# ══════════════════════════════════ ขอบเศษการปัด — ล็อกทั้งด้านในและด้านนอก
def test_rounding_bound_uses_round_to_nearest_formula():
    """ขอบ = ``(n+1) × q ÷ 2`` — ตัวตั้ง n ตัวและยอดที่ประกาศไว้อีกหนึ่ง"""
    recs = [
        _year("รวมเงินงบประมาณ", "10.0000", cell="D7", row=7),
        _year("เงินงบประมาณ", "5.0000", cell="D10", row=10, hierarchy=("1",)),
        _year("เงินงบประมาณ", "5.0001", cell="D15", row=15, hierarchy=("2",)),
    ]
    check = _only(_run(recs), RULE_FUNDING_LINE_SUM)[0]

    assert len(check.components) == 2
    assert check.rounding_bound == (Decimal(3) * QUANTUM) / 2   # 0.00015
    assert check.rounding_bound < QUANTUM * 2, "ต้องแคบกว่าขอบเดิม n×q"


def test_difference_exactly_at_the_bound_is_a_candidate():
    """ด้านใน — ตัวตั้งหนึ่งตัว ขอบ = ``0.0001`` · ส่วนต่างเท่าขอบพอดี"""
    recs = [
        _year("รวมเงินงบประมาณ", "5.0001", cell="D7", row=7),
        _year("เงินงบประมาณ", "5.0000", cell="D10", row=10, hierarchy=("1",)),
    ]
    check = _only(_run(recs), RULE_FUNDING_LINE_SUM)[0]

    assert check.rounding_bound == QUANTUM
    assert check.difference == QUANTUM
    assert check.status == STATUS_ROUNDING_RESIDUE_CANDIDATE
    assert check.within_rounding_bound is True
    assert check.requires_human_decision, "candidate ยังต้องให้มนุษย์ยืนยัน"


def test_difference_one_step_outside_the_bound_is_a_material_mismatch():
    """ด้านนอก — ส่วนต่างเกินขอบไปหนึ่งขั้นต้องเป็น ``MISMATCH``"""
    recs = [
        _year("รวมเงินงบประมาณ", "5.0002", cell="D7", row=7),
        _year("เงินงบประมาณ", "5.0000", cell="D10", row=10, hierarchy=("1",)),
    ]
    check = _only(_run(recs), RULE_FUNDING_LINE_SUM)[0]

    assert check.difference == QUANTUM * 2
    assert check.difference > check.rounding_bound
    assert check.status == STATUS_MISMATCH
    assert check.within_rounding_bound is False


def test_candidate_wording_does_not_claim_rounding_was_proven():
    """🔴 ถ้อยคำต้องไม่ยืนยันว่าเกิดจากการปัดแล้ว — ระบบยังพิสูจน์ไม่ได้"""
    recs = [
        _year("รวมเงินงบประมาณ", "5.0001", cell="D7", row=7),
        _year("เงินงบประมาณ", "5.0000", cell="D10", row=10, hierarchy=("1",)),
    ]
    check = _only(_run(recs), RULE_FUNDING_LINE_SUM)[0]

    assert "ยังไม่ยืนยัน" in check.detail
    assert "รอมนุษย์ตัดสิน" in check.detail


def test_every_non_ok_status_requires_a_human_decision():
    """ไม่มีสถานะใดนอกจาก ``OK`` ที่หลุดออกจากคิวมนุษย์ได้

    🔴 BO REVIEW (2 ก.ย.): test เดิมเทียบแค่ว่าสตริงของแต่ละสถานะ != ``"OK"``
    ซึ่ง **ผ่านแม้ property ``requires_human_decision`` จะพังและคืน ``False``**
    รอบนี้สร้างผลจริงของทุกสถานะ แล้วตรวจทั้ง property และการปรากฏในคิว
    """
    cases = {
        STATUS_MISMATCH: [
            _year("รวมเงินงบประมาณ", "9.0000", cell="D7", row=7),
            _year("เงินงบประมาณ", "1.0000", cell="D10", row=10,
                  hierarchy=("1",)),
        ],
        STATUS_ROUNDING_RESIDUE_CANDIDATE: [
            _year("รวมเงินงบประมาณ", "5.0001", cell="D7", row=7),
            _year("เงินงบประมาณ", "5.0000", cell="D10", row=10,
                  hierarchy=("1",)),
        ],
        STATUS_INCOMPLETE: [
            _year("รวมเงินงบประมาณ", "5.0000", cell="D7", row=7),
        ],
        STATUS_HUMAN_REVIEW: [
            _year("รวมเงินงบประมาณ", "5.0000", cell="D7", row=7),
            _year("เงินงบประมาณ", "5.0000", cell="D10", row=10,
                  hierarchy=("1",), unit=UNIT_UNRESOLVED),
        ],
    }
    for status, recs in cases.items():
        result = _run(recs)
        check = _only(result, RULE_FUNDING_LINE_SUM)[0]
        assert check.status == status, f"คาด {status} ได้ {check.status}"
        assert check.requires_human_decision is True, status
        assert check in result.needing_human(), f"{status} ไม่อยู่ในคิวมนุษย์"

    ok = _run([
        _year("รวมเงินงบประมาณ", "5.0000", cell="D7", row=7),
        _year("เงินงบประมาณ", "5.0000", cell="D10", row=10, hierarchy=("1",)),
    ])
    ok_check = _only(ok, RULE_FUNDING_LINE_SUM)[0]
    assert ok_check.status == STATUS_OK
    assert ok_check.requires_human_decision is False
    assert ok_check not in ok.needing_human()


def test_key_version_unchanged():
    """🔒 roll-up ไม่แตะคีย์ที่ freeze แล้ว"""
    assert KEY_VERSION == "t1b-key-0.2.0"
    assert ROLLUP_VERSION == "t1b-rollup-0.5.0"


# ══════════════════════════════════ แฟ้มจริง — regression baseline
@needs_sources
def test_real_workbooks_rollup_baseline():
    """baseline ของแฟ้มจริงทั้ง 6 · **ผลการรันในเครื่องผู้พัฒนา ไม่ใช่ CI**

    ตรวจ **167** ชุด · exact OK **166** · material mismatch **0** ·
    rounding-residue candidate **1** · incomplete **0**

    🔴 ประวัติของตัวเลขนี้ — ต้องไม่ลืม:
    ``167`` → ``182`` เมื่อ ``rollup 0.5.0`` ให้ record ที่มีเนื้อหาดิบแต่แปลง
    ไม่ได้เข้าสู่ด่านตรวจ ⇒ เผยข้อบกพร่องของชั้นสกัดที่ดึง **แถวหัวของ
    ตารางถัดไป** เข้ามาในช่วงข้อมูลของตารางหมวด (15 ชุดปลอม)
    ``182`` → ``167`` เมื่อแก้รากที่ขอบเขตตาราง (blocker #4 · Bo · 3 ก.ย.)
    **ไม่ใช่** ด้วยการกรองรายการออกใน ``rollup.py`` ซึ่งถูกห้ามไว้ชัดเจน
    ดู ``tests/test_t1b_table_boundary.py``
    """
    adapter = AOWorkbookAdapter()
    total = ok = material = candidate = incomplete = 0
    found = []
    for name in FILES:
        result = check_rollups_for_envelopes(adapter.extract(SOURCE_DIR / name))
        total += len(result.checks)
        ok += len(result.exact_ok())
        material += len(result.mismatches())
        incomplete += len(result.incomplete())
        for check in result.rounding_residue_candidates():
            candidate += 1
            found.append((name, check))

    assert total == 167, f"จำนวนการกระทบยอดเปลี่ยนไป: {total}"
    assert ok == 166, f"จำนวนที่ตรงแบบตรงตัวเปลี่ยนไป: {ok}"
    assert material == 0, f"พบยอดที่ต่างเกินขอบการปัด: {material}"
    assert incomplete == 0, f"พบชุดที่ไม่สมบูรณ์: {incomplete}"
    assert candidate == 1, f"จำนวน candidate เปลี่ยนไป: {candidate}"

    name, check = found[0]
    assert "21000_MOPH-summary" in name
    assert check.rule == RULE_FUNDING_LINE_SUM
    assert check.difference == -QUANTUM
    assert len(check.components) == 6
    assert check.rounding_bound == (Decimal(7) * QUANTUM) / 2
    assert check.requires_human_decision
    assert check.fully_traceable, "ต้องย้อนถึง source_file/source_hash/cell/ค่าดิบ"


@needs_sources
def test_real_workbooks_have_no_held_groups():
    """แฟ้มจริงยังไม่มีชุดที่ถูกกันไว้จากเหตุหมวด/หน่วย/แกนเทียบ"""
    adapter = AOWorkbookAdapter()
    for name in FILES:
        result = check_rollups_for_envelopes(adapter.extract(SOURCE_DIR / name))
        held = [c for c in result.checks if c.status == STATUS_HUMAN_REVIEW]
        assert held == [], f"{name}: {[c.detail for c in held]}"


@needs_sources
def test_real_workbooks_have_no_incomplete_groups():
    """🔴 ชุดไม่สมบูรณ์ 15 รายการต้องหายไปหมดหลังแก้ blocker #4

    ทั้ง 15 เกิดจากแถวหัวของตารางถัดไปถูกนับเป็นแถวข้อมูลของตารางหมวด
    แก้ที่ **ขอบเขตตาราง** ไม่ใช่ที่ ``rollup.py``
    """
    adapter = AOWorkbookAdapter()
    for name in FILES:
        result = check_rollups_for_envelopes(adapter.extract(SOURCE_DIR / name))
        assert result.incomplete() == [], (
            f"{name}: {[c.scope for c in result.incomplete()]}"
        )

# ══════════════════════════════════ 🔴 BO REVIEW รอบสี่ (2 ก.ย. 2569)
def test_year_record_declaring_category_axis_is_never_summed():
    """① แกนบอก ``BUDGET_CATEGORY`` แต่มีปี ไม่มีหมวด → ห้ามบวก

    เดิมยอดบังเอิญตรงก็คืน ``OK`` เพราะ roll-up ไม่เคยถาม ``axis_valid``
    ทั้งที่ตัว record เองมี ``needs_review = True`` อยู่แล้ว
    """
    bad = _year("เงินงบประมาณ", "3.0000", cell="D10", row=10, hierarchy=("1",),
                axis=AXIS_BUDGET_CATEGORY)
    assert bad.axis_valid is False and bad.needs_review

    check = _only(_run([
        _year("รวมเงินงบประมาณ", "3.0000", cell="D7", row=7), bad,
    ]), RULE_FUNDING_LINE_SUM)[0]

    assert check.status == STATUS_HUMAN_REVIEW
    assert check.computed is None, "ยอดบังเอิญตรงก็ห้ามสรุป"
    assert "แกนเทียบไม่ถูกต้อง" in check.detail
    assert "3.0000" in _values(check), "ค่าต้องยังอยู่ใน provenance"
    assert check.fully_traceable


def test_category_record_declaring_year_axis_is_never_summed():
    """① อีกด้าน — แกนบอก ``FISCAL_YEAR`` แต่มีหมวด ไม่มีปี"""
    bad = _cat("รวมทั้งสิ้น", CATEGORY_OPERATING, "1.0000", cell="G11",
               axis=AXIS_FISCAL_YEAR)
    assert bad.axis_valid is False

    check = _only(_run([
        bad,
        _cat("รวมทั้งสิ้น", CATEGORY_INVESTMENT, "2.0000", cell="H11"),
        _cat("รวมทั้งสิ้น", CATEGORY_TOTAL, "3.0000", cell="J11", raw="รวม"),
    ]), RULE_CATEGORY_TOTAL)[0]

    assert check.status == STATUS_HUMAN_REVIEW
    assert check.computed is None
    assert {"1.0000", "2.0000", "3.0000"} <= _values(check)
    assert check.fully_traceable


def test_funding_children_without_subtotal_is_incomplete():
    """② มีแถวลูกแต่ไม่มียอดย่อย → เดิมข้ามทั้งชุดเงียบ"""
    checks = _only(_run([
        _year("เงินงบประมาณ", "3.0000", cell="D10", row=10, hierarchy=("1",)),
    ]), RULE_FUNDING_LINE_SUM)

    assert len(checks) == 1, "ต้องมีผลตรวจ ห้ามข้ามเงียบ"
    assert checks[0].status == STATUS_INCOMPLETE
    assert checks[0].computed is None
    assert "รวมเงินงบประมาณ" in checks[0].detail
    assert "3.0000" in _values(checks[0])


def test_categories_without_total_column_is_incomplete():
    """② มีหมวดย่อยแต่ไม่มีคอลัมน์ ``รวม`` → เดิมข้ามเงียบ"""
    checks = _only(_run([
        _cat("รวมทั้งสิ้น", CATEGORY_OPERATING, "1.0000", cell="G11"),
        _cat("รวมทั้งสิ้น", CATEGORY_INVESTMENT, "2.0000", cell="H11"),
    ]), RULE_CATEGORY_TOTAL)

    assert len(checks) == 1
    assert checks[0].status == STATUS_INCOMPLETE
    assert "TOTAL" in checks[0].detail
    assert {"1.0000", "2.0000"} <= _values(checks[0])


def test_total_column_without_any_category_is_incomplete():
    """② มี ``รวม`` แต่ไม่มีหมวดย่อยเลย → เดิมข้ามเงียบ"""
    checks = _only(_run([
        _cat("รวมทั้งสิ้น", CATEGORY_TOTAL, "3.0000", cell="J11", raw="รวม"),
    ]), RULE_CATEGORY_TOTAL)

    assert len(checks) == 1
    assert checks[0].status == STATUS_INCOMPLETE
    assert "ไม่พบตัวตั้งเลย" in checks[0].detail
    assert "3.0000" in _values(checks[0])


def test_category_cells_without_a_value_form_no_group():
    """เซลล์หัวตารางที่ถูกติดป้ายหมวดแต่ไม่มีค่า — ไม่มียอดให้กระทบ

    🔴 พบในแฟ้มจริง **30 รายการ** · เป็นข้อจำกัดของ **ชั้นสกัด** ไม่ใช่ roll-up
    ถ้านับเป็นชุด จะได้ ``HUMAN_REVIEW`` ปลอม 15 รายการ
    """
    empty = T1BRecord(
        key=T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                   sheet_role="SECTION_07_PLAN",
                   row_label_norm="ตัวชี้วัด/ แหล่งเงิน"),
        row_kind=ROW_KIND_VALUE, comparison_axis=AXIS_BUDGET_CATEGORY,
        budget_category=CATEGORY_OPERATING, budget_category_raw="งบดำเนินงาน",
        declared_unit=UNIT_MILLION_BAHT, is_monetary=True,
        value_decimal=None, raw_value=None,
        sheet_name_actual="Sheet7_2", cell_ref="G13", row_index=13,
    )
    assert _only(_run([empty]), RULE_CATEGORY_TOTAL) == []


# ══════════════════════════════════ ③ ขอบการปัดต้องคิดตามหน่วย
def test_rounding_bound_follows_the_declared_unit_precision():
    """③ หน่วย ``บาท`` ประกาศทศนิยม 2 ตำแหน่ง ⇒ ขอบต้องเป็น ``0.015``

    เดิมใช้ ``QUANTUM`` ตายตัว ``0.0001`` กับทุกหน่วย ทำให้ยอดหน่วยบาทที่ต่าง
    ``0.01`` (หนึ่งหน่วยละเอียดของบาท) ถูกตัดสินเป็น **material mismatch**
    """
    assert quantum_for(UNIT_BAHT) == Decimal("0.01")
    assert quantum_for(UNIT_MILLION_BAHT) == QUANTUM

    check = _only(_run([
        _year("รวมเงินงบประมาณ", "10.01", cell="D7", row=7, unit=UNIT_BAHT),
        _year("เงินงบประมาณ", "5.00", cell="D10", row=10, hierarchy=("1",),
              unit=UNIT_BAHT),
        _year("เงินงบประมาณ", "5.00", cell="D15", row=15, hierarchy=("2",),
              unit=UNIT_BAHT),
    ]), RULE_FUNDING_LINE_SUM)[0]

    assert check.rounding_bound == (Decimal(3) * Decimal("0.01")) / 2
    assert check.status == STATUS_ROUNDING_RESIDUE_CANDIDATE
    assert check.requires_human_decision


def test_baht_difference_beyond_its_own_precision_is_material():
    """หน่วยบาทที่ต่างเกินขอบของตัวเอง ยังต้องเป็น ``MISMATCH``"""
    check = _only(_run([
        _year("รวมเงินงบประมาณ", "10.05", cell="D7", row=7, unit=UNIT_BAHT),
        _year("เงินงบประมาณ", "5.00", cell="D10", row=10, hierarchy=("1",),
              unit=UNIT_BAHT),
        _year("เงินงบประมาณ", "5.00", cell="D15", row=15, hierarchy=("2",),
              unit=UNIT_BAHT),
    ]), RULE_FUNDING_LINE_SUM)[0]

    assert check.status == STATUS_MISMATCH


# ══════════════════════════════════ provenance contract
def test_check_rollups_requires_source_identity():
    """🔴 ผลที่ย้อนกลับต้นทางไม่ได้ ใช้เป็นหลักฐานไม่ได้"""
    recs = [_cat("รวมทั้งสิ้น", CATEGORY_TOTAL, "1.0000", cell="J11", raw="รวม")]

    with pytest.raises(TypeError):
        check_rollups(recs)
    with pytest.raises(ValueError, match="source_file"):
        check_rollups(recs, source_file="", source_hash=SRC_HASH)
    with pytest.raises(ValueError, match="source_file"):
        check_rollups(recs, source_file=SRC_FILE, source_hash="")


@needs_sources
def test_envelope_entry_point_refuses_same_hash_different_name():
    """🔴 ต้องดู **ทั้งชื่อและแฮช** — แฟ้มคนละชื่อเนื้อหาเดียวกันมีแฮชเท่ากัน

    ถ้าตรวจแฮชอย่างเดียว การปนจะผ่าน แล้วผลทั้งชุดจะระบุชื่อเป็นแฟ้มแรกทั้งหมด
    """
    from dataclasses import replace as dc_replace

    envelopes = AOWorkbookAdapter().extract(SOURCE_DIR / FILES[1])[:6]
    renamed = [
        dc_replace(e, source_file=e.source_file.with_name("สำเนา.xlsx"))
        for e in envelopes[3:]
    ]
    mixed = envelopes[:3] + renamed
    assert len({e.source_hash for e in mixed}) == 1, "แฮชเดียวกันทั้งชุด"

    with pytest.raises(ValueError, match="หลายแฟ้ม"):
        check_rollups_for_envelopes(mixed)


# ══════════════════════════════════ cross-sheet applicability (สำรวจแล้ว)
def test_cross_sheet_year_present_in_one_role_only_is_not_applicable():
    """ปีที่มีบทบาทเดียว = กฎใช้ไม่ได้ **ไม่ใช่** ชุดไม่สมบูรณ์

    🔴 สำรวจแฟ้มจริง 6 แฟ้มตามคำสั่ง Bo: มีทั้งสองบทบาท **8 ปี** ·
    มีเฉพาะบทบาท 4. **4 ปี** · มีเฉพาะบทบาท 5. **22 ปี**
    ⇒ การมีข้างเดียวเป็นเรื่องปกติ (บทบาท 4. รายงานปีย้อนหลัง ·
    บทบาท 5. รายงานปีปัจจุบันและล่วงหน้า) ถ้าตั้งเป็น ``INCOMPLETE``
    จะสร้างรายการปลอม 26 รายการ
    """
    only_05 = _run([
        _year("รวมทั้งสิ้น", "58.4401", sheet="Sheet5", cell="D6",
              role="SECTION_05"),
    ])
    assert _only(only_05, RULE_CROSS_SHEET_GRAND) == []

    only_04 = _run([
        _year("รวมทั้งสิ้น", "48.4143", sheet="Sheet4", cell="D6",
              role="SECTION_04", year=2567),
    ])
    assert _only(only_04, RULE_CROSS_SHEET_GRAND) == []


# ══════════════════════════════════ 🔴 BO REVIEW (3 ก.ย. 2569) — สอง boundary สุดท้าย
def _cat_raw(category, value, raw_value, *, cell="C11"):
    """record หมวดที่กำหนด ``value_decimal`` และ ``raw_value`` แยกกันได้"""
    return T1BRecord(
        key=T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                   sheet_role="SECTION_06", row_label_norm="รวมทั้งสิ้น"),
        row_kind=ROW_KIND_VALUE, comparison_axis=AXIS_BUDGET_CATEGORY,
        budget_category=category, budget_category_raw="งบลงทุน",
        declared_unit=UNIT_MILLION_BAHT, is_monetary=True,
        value_decimal=value, raw_value=raw_value,
        sheet_name_actual="Sheet6", cell_ref=cell, row_index=11,
    )


def test_raw_value_that_cannot_be_parsed_is_never_dropped():
    """🔴 ``#VALUE!`` อาจเป็นยอดจริงที่อ่านไม่ออก — ห้ามตัดทิ้งแล้วคืน ``OK``

    เดิม ``_category_totals()`` รับเฉพาะ ``value_decimal is not None``
    ⇒ record แรกถูกตัดก่อนถึง ``_check()`` แล้วสองค่าที่เหลือคืน ``OK``
    """
    recs = [
        _cat_raw(CATEGORY_OPERATING, None, "#VALUE!", cell="G11"),
        _cat_raw(CATEGORY_INVESTMENT, Decimal("3.0000"), "3", cell="H11"),
        _cat_raw(CATEGORY_TOTAL, Decimal("3.0000"), "3", cell="J11"),
    ]
    check = _only(_run(recs), RULE_CATEGORY_TOTAL)[0]

    assert check.status == STATUS_HUMAN_REVIEW
    assert check.computed is None, "ยอดที่เหลือบวกลงตัวก็ห้ามสรุป"
    assert len(check.components) == 2
    assert "#VALUE!" in {c.raw_value for c in check.components}
    assert "#VALUE!" in check.detail
    assert "แปลงเป็นตัวเลขไม่ได้" in check.detail

    broken = next(c for c in check.components if c.raw_value == "#VALUE!")
    assert broken.usable is False
    assert broken.value is None
    assert broken.traceable, "ยังต้องย้อนถึงต้นทางได้"


@pytest.mark.parametrize("raw", ["#REF!", "n/a", "-", "  ๑๐  ", 0.0])
def test_any_non_empty_raw_content_reaches_the_check(raw):
    """เนื้อหาดิบชนิดใดก็ตามที่ไม่ว่าง ต้องไปถึงด่านตรวจเสมอ"""
    recs = [
        _cat_raw(CATEGORY_OPERATING, None, raw, cell="G11"),
        _cat_raw(CATEGORY_INVESTMENT, Decimal("3.0000"), "3", cell="H11"),
        _cat_raw(CATEGORY_TOTAL, Decimal("3.0000"), "3", cell="J11"),
    ]
    check = _only(_run(recs), RULE_CATEGORY_TOTAL)[0]

    assert check.status == STATUS_HUMAN_REVIEW
    assert check.computed is None
    assert raw in {c.raw_value for c in check.components}


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_truly_empty_cell_carries_no_amount_and_does_not_block(raw):
    """เซลล์ว่างจริงไม่มียอดให้กระทบ — ต้องไม่กลายเป็นรายการค้างปลอม

    🔴 นี่คือเส้นแบ่งที่ Bo กำหนด: แยก **ว่างจริง** ออกจาก
    **มีเนื้อหาแต่แปลงไม่ได้** ด้วย ``raw_value``
    """
    recs = [
        _cat_raw(CATEGORY_OPERATING, None, raw, cell="G11"),
        _cat_raw(CATEGORY_INVESTMENT, Decimal("3.0000"), "3", cell="H11"),
        _cat_raw(CATEGORY_TOTAL, Decimal("3.0000"), "3", cell="J11"),
    ]
    check = _only(_run(recs), RULE_CATEGORY_TOTAL)[0]

    assert check.status == STATUS_OK
    assert check.computed == Decimal("3.0000")
    assert len(check.components) == 1, "เซลล์ว่างไม่นับเป็นตัวตั้ง"


def test_empty_and_unparseable_are_reported_differently():
    """เหตุผลในคิวต้องบอกได้ว่าเป็นเซลล์ว่างหรือแปลงไม่ได้"""
    unparseable = _only(_run([
        _cat_raw(CATEGORY_OPERATING, None, "#VALUE!", cell="G11"),
        _cat_raw(CATEGORY_TOTAL, Decimal("1.0000"), "1", cell="J11"),
    ]), RULE_CATEGORY_TOTAL)[0]

    assert "แปลงเป็นตัวเลขไม่ได้" in unparseable.detail
    assert "เซลล์ว่าง" not in unparseable.detail


# ── ขอบการปัดต้องอิงทศนิยมที่ประกาศจริง ไม่ใช่ค่าปริยายของหน่วย
DECL_3 = "หน่วย : บาท (ทศนิยม 3 ตำแหน่ง)"


def test_quantum_for_uses_the_declaration_when_present():
    """``quantum_for`` ต้องใช้กติกาเดียวกับที่ ``normalize_amount`` ใช้ปัดค่า"""
    assert quantum_for(UNIT_BAHT) == Decimal("0.01")
    assert quantum_for(UNIT_BAHT, DECL_3) == Decimal("0.001")
    assert quantum_for(UNIT_MILLION_BAHT, DECL_3) == Decimal("0.001")
    assert quantum_for(UNIT_MILLION_BAHT, "หน่วย : ล้านบาท") == QUANTUM


def test_rounding_bound_follows_the_per_record_declaration():
    """🔴 ประกาศ 3 ตำแหน่ง ⇒ ขอบต้องเป็น ``0.0015`` ไม่ใช่ ``0.015``

    เดิม ``quantum_for(unit)`` ใช้ค่าปริยายตามชนิดหน่วยอย่างเดียว
    ทั้งที่ ``normalize_amount()`` เคารพข้อความประกาศของแต่ละแถว
    ⇒ ขอบการปัดไม่ตรงกับความละเอียดที่ค่านั้นถูกปัดมาจริง
    """
    check = _only(_run([
        _year("รวมเงินงบประมาณ", "10.001", cell="D7", row=7, unit=UNIT_BAHT,
              decl=DECL_3),
        _year("เงินงบประมาณ", "5.000", cell="D10", row=10, hierarchy=("1",),
              unit=UNIT_BAHT, decl=DECL_3),
        _year("เงินงบประมาณ", "5.000", cell="D15", row=15, hierarchy=("2",),
              unit=UNIT_BAHT, decl=DECL_3),
    ]), RULE_FUNDING_LINE_SUM)[0]

    assert check.rounding_bound == (Decimal(3) * Decimal("0.001")) / 2
    assert check.difference == Decimal("0.001")
    assert check.status == STATUS_ROUNDING_RESIDUE_CANDIDATE
    assert all(c.unit_declaration == DECL_3 for c in check.components)


def test_declaration_can_make_the_bound_stricter_than_the_unit_default():
    """ประกาศละเอียดกว่าค่าปริยาย ⇒ ขอบต้อง **แคบลง** ไม่ใช่กว้างตามหน่วย"""
    check = _only(_run([
        _year("รวมเงินงบประมาณ", "10.010", cell="D7", row=7, unit=UNIT_BAHT,
              decl=DECL_3),
        _year("เงินงบประมาณ", "5.000", cell="D10", row=10, hierarchy=("1",),
              unit=UNIT_BAHT, decl=DECL_3),
        _year("เงินงบประมาณ", "5.000", cell="D15", row=15, hierarchy=("2",),
              unit=UNIT_BAHT, decl=DECL_3),
    ]), RULE_FUNDING_LINE_SUM)[0]

    assert check.difference == Decimal("0.010")
    assert check.difference > check.rounding_bound
    assert check.status == STATUS_MISMATCH, (
        "ถ้ายังใช้ค่าปริยายของบาท (ขอบ 0.015) จะถูกจัดเป็น candidate อย่างผิด"
    )
