# -*- coding: utf-8 -*-
"""T1B — matching และ compare

🔒 ใช้คีย์ ``t1b-key-0.2.0`` ที่ตรึงไว้ (5 กันยายน 2569)

ข้ามอัตโนมัติเมื่อไม่พบคลังข้อมูล · 🔴 อ่านอย่างเดียว
"""
import os
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from redbook.adapters.ao_workbook import AOWorkbookAdapter
from redbook.t1b import (
    DOCUMENT_LEVEL_AGENCY,
    KEY_VERSION,
    UNIT_MILLION_BAHT,
    UNIT_PERCENT,
    UNIT_UNRESOLVED,
    CATEGORY_INVESTMENT,
    CATEGORY_SUBSIDY,
    CATEGORY_TOTAL,
    CATEGORY_UNRESOLVED,
    T1BKey,
    compare,
    match_records,
)
from redbook.t1b.compare import (
    F_AMOUNT_DECREASED,
    F_AMOUNT_INCREASED,
    F_AMOUNT_UNCHANGED,
    F_NOT_COMPARABLE,
    F_PROJECT_ORDINAL_CHANGED,
    F_ROW_ADDED,
    F_ROW_REMOVED,
    F_UNIT_CHANGED,
    F_YEAR_ONLY_ONE_SIDE,
)
from redbook.t1b.records import (
    AXIS_BUDGET_CATEGORY,
    AXIS_FISCAL_YEAR,
    AXIS_UNRESOLVED,
    ROW_KIND_VALUE,
    T1BRecord,
)
from redbook.t1b.roles import SECTION_ROLE_PROJECT

# 🔴 คิดจากที่อยู่ของไฟล์นี้ ไม่ใช่เส้นทางตายตัวที่มีชื่อผู้ใช้
# คลังข้อมูลเป็น repo พี่น้องที่วางข้าง ๆ repo โค้ด ⇒ ได้เส้นทางเดิมทุกประการ
# ห้ามเขียนกลับเป็นเส้นทางตายตัว — ชื่อผู้ใช้จะติดขึ้น git ไปด้วย
_DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "redbook-verify-data" / "sources" / "public" / "ao_workbook"
)
SOURCE_DIR = Path(os.environ.get("REDBOOK_T1B_SOURCE_DIR", _DEFAULT_SOURCE))
FY69 = "XL_FY2569_draft-bill_21011_HSRI.xlsx"
FY70 = "XL_FY2570_draft-bill_21011_HSRI.xlsx"

needs_sources = pytest.mark.skipif(
    not (SOURCE_DIR / FY69).exists(),
    reason=f"ไม่พบคลังข้อมูล T1B ที่ {SOURCE_DIR} (ไฟล์ข้อมูลอยู่นอก Git ตาม SYS-D-05)",
)

#: 🔴 ด่านตัวตนหน่วยงานเป็น **fail-closed** ตั้งแต่ BO REVIEW (Issue #1) —
#: สอง record ที่ไม่มี ``agency_identity`` จะไม่ถูกจับคู่อัตโนมัติอีกต่อไป
#:
#: ชุดทดสอบในไฟล์นี้วัด *กลไกการจับคู่และการเทียบ* ไม่ได้วัดด่านตัวตน
#: (ด่านตัวตนมีชุดของตัวเองที่ ``tests/test_t1b_identity_gate.py``)
#: fixture จึงต้องประกาศให้ชัดว่าเป็น **หน่วยงานเดียวกันที่ยืนยันแล้ว**
#: ซึ่งเป็นการทำสมมติฐานเดิมที่ซ่อนอยู่ให้เห็นชัด ไม่ใช่การผ่อนด่าน
AGENCY = "สถาบันทดสอบ"


def _rec(*, label, year, value, unit=UNIT_MILLION_BAHT, sheet="Sheet5",
         cell="C6", row=6, role="SECTION_05", ordinal=None, monetary=True,
         uncertainty=(), hierarchy=()):
    return T1BRecord(
        key=T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                   agency_identity=AGENCY,
                   sheet_role=role, hierarchy_path=hierarchy, row_label_norm=label),
        row_kind=ROW_KIND_VALUE, comparison_axis=AXIS_FISCAL_YEAR,
        fiscal_year=year, fiscal_year_label=f"ปี {year}",
        declared_unit=unit, is_monetary=monetary,
        value_decimal=Decimal(value) if value is not None else None,
        raw_value=value, sheet_name_actual=sheet, cell_ref=cell, row_index=row,
        project_ordinal_raw=ordinal, uncertainty=tuple(uncertainty),
    )


# ────────────────────────────────────────────────────── matching (synthetic)
def test_match_pairs_by_key_and_year_not_by_cell():
    """จับคู่ด้วยคีย์ + ปี — ตำแหน่งเซลล์ต่างกันได้"""
    base = [_rec(label="รวมทั้งสิ้น", year=2569, value="58.4401", cell="D6")]
    curr = [_rec(label="รวมทั้งสิ้น", year=2569, value="55.0000", cell="C6")]
    result = match_records(base, curr)

    assert len(result.matched) == 1
    pair = result.matched[0]
    assert pair.fiscal_year == 2569
    assert pair.baseline.cell_ref == "D6"
    assert pair.current.cell_ref == "C6"


def test_match_never_pairs_different_years():
    """คนละปีต้องไม่ถูกจับคู่ แม้คีย์เดียวกันและอยู่เซลล์เดียวกัน"""
    base = [_rec(label="รวมทั้งสิ้น", year=2568, value="53.2712", cell="C6")]
    curr = [_rec(label="รวมทั้งสิ้น", year=2569, value="58.4401", cell="C6")]
    result = match_records(base, curr)

    assert result.matched == []
    # ปีคิด **รายขอบเขตชีต** ไม่ใช่ union ระดับสมุดงาน
    gaps = result.scopes_with_year_gap()
    assert len(gaps) == 1
    assert gaps[0].baseline_only == (2568,)
    assert gaps[0].current_only == (2569,)
    assert gaps[0].comparable == ()


def test_match_routes_blocking_uncertainty_to_human():
    """record ที่กำกวมแบบ blocking ต้องไม่ถูกจับคู่อัตโนมัติ"""
    base = [_rec(label="ก", year=2569, value="1", unit=UNIT_UNRESOLVED,
                 uncertainty=("declared_unit_unresolved",))]
    curr = [_rec(label="ก", year=2569, value="1", unit=UNIT_UNRESOLVED,
                 uncertainty=("declared_unit_unresolved",))]
    result = match_records(base, curr)

    assert result.matched == []
    assert len(result.needs_human) == 2
    assert {s.side for s in result.needs_human} == {"baseline", "current"}


def test_match_accounts_for_every_input_record():
    """🔴 ทุก record ขาเข้าต้องถูกจัดกลุ่ม — ห้ามหายเงียบ"""
    base = [
        _rec(label="ก", year=2569, value="1"),
        _rec(label="ข", year=2569, value="2"),
        _rec(label="ค", year=2570, value="3"),
    ]
    curr = [
        _rec(label="ก", year=2569, value="9"),
        _rec(label="ง", year=2570, value="4"),
    ]
    result = match_records(base, curr)
    assert result.accounted() == len(base) + len(curr)


def test_match_uses_frozen_key_version():
    assert match_records([], []).summary()["key_version"] == KEY_VERSION == "t1b-key-0.2.0"


# ────────────────────────────────────────────────────── compare (synthetic)
@pytest.mark.parametrize(
    "before, after, expected",
    [
        ("53.2712", "58.4401", F_AMOUNT_INCREASED),
        ("58.4401", "53.2712", F_AMOUNT_DECREASED),
        ("53.2712", "53.2712", F_AMOUNT_UNCHANGED),
    ],
)
def test_compare_classifies_amount_direction(before, after, expected):
    result = compare(match_records(
        [_rec(label="รวมทั้งสิ้น", year=2569, value=before)],
        [_rec(label="รวมทั้งสิ้น", year=2569, value=after)],
    ))
    assert [f.finding_type for f in result.findings] == [expected]


def test_compare_float_residue_is_not_a_finding():
    """🔴 เศษ floating-point ต้องไม่กลายเป็น finding ว่าเปลี่ยน"""
    base = [_rec(label="ก", year=2569, value=None)]
    curr = [_rec(label="ก", year=2569, value=None)]
    base[0] = _rec(label="ก", year=2569, value="937.5201")
    curr[0] = _rec(label="ก", year=2569, value="937.5201")
    result = compare(match_records(base, curr))
    assert result.findings[0].finding_type == F_AMOUNT_UNCHANGED
    assert result.findings[0].difference == Decimal("0.0000")


def test_compare_refuses_cross_unit_comparison():
    """``บาท`` กับ ``ล้านบาท`` ต่างกันล้านเท่า — ห้ามเทียบตรง ๆ"""
    result = compare(match_records(
        [_rec(label="ก", year=2569, value="1", unit="บาท")],
        [_rec(label="ก", year=2569, value="1", unit=UNIT_MILLION_BAHT)],
    ))
    finding = result.findings[0]
    assert finding.finding_type == F_UNIT_CHANGED
    assert finding.requires_human_decision


def test_compare_unresolved_unit_is_not_comparable():
    result = compare(match_records(
        [_rec(label="ก", year=2569, value="1", unit=UNIT_UNRESOLVED)],
        [_rec(label="ก", year=2569, value="1", unit=UNIT_PERCENT)],
    ))
    # ทั้งสองฝั่งถูกส่งเข้าคิวมนุษย์ก่อนถึงขั้นเทียบ
    assert all(f.requires_human_decision for f in result.findings)


def test_compare_reports_added_and_removed_rows():
    result = compare(match_records(
        [_rec(label="เดิม", year=2569, value="1")],
        [_rec(label="ใหม่", year=2569, value="2")],
    ))
    types = {f.finding_type for f in result.findings}
    assert types == {F_ROW_REMOVED, F_ROW_ADDED}
    assert all(f.requires_human_decision for f in result.findings)


def test_compare_reports_year_present_on_one_side_only():
    result = compare(match_records(
        [_rec(label="ก", year=2568, value="1")],
        [_rec(label="ก", year=2573, value="1")],
    ))
    years = {f.fiscal_year for f in result.findings if f.finding_type == F_YEAR_ONLY_ONE_SIDE}
    assert years == {2568, 2573}


def test_compare_emits_finding_when_project_ordinal_changes():
    """🔴 ชื่อโครงการตรงกันแต่เลขลำดับเปลี่ยน → จับคู่ได้ **และต้องออก finding**

    คำตัดสิน Gift ทาง (ค) — จับคู่ได้แต่ต้องไม่กลบข้อเท็จจริง
    """
    key_args = dict(label="รวมทั้งสิ้น", year=2569, role=SECTION_ROLE_PROJECT)
    base = [_rec(value="10", ordinal="โครงการที่ 2", **key_args)]
    curr = [_rec(value="12", ordinal="โครงการที่ 3", **key_args)]
    result = compare(match_records(base, curr))

    types = [f.finding_type for f in result.findings]
    assert F_AMOUNT_INCREASED in types      # จับคู่ได้
    assert F_PROJECT_ORDINAL_CHANGED in types   # และแจ้งว่าเลขลำดับเปลี่ยน

    ordinal_finding = next(
        f for f in result.findings if f.finding_type == F_PROJECT_ORDINAL_CHANGED
    )
    assert "โครงการที่ 2" in ordinal_finding.detail
    assert "โครงการที่ 3" in ordinal_finding.detail
    assert ordinal_finding.requires_human_decision


def test_compare_no_ordinal_finding_when_unchanged():
    key_args = dict(label="ก", year=2569, role=SECTION_ROLE_PROJECT,
                    ordinal="โครงการที่ 2")
    result = compare(match_records(
        [_rec(value="10", **key_args)], [_rec(value="12", **key_args)]
    ))
    assert F_PROJECT_ORDINAL_CHANGED not in {f.finding_type for f in result.findings}


# ────────────────────────────────────────────────────── ไฟล์จริง
@needs_sources
def test_real_pair_accounts_for_every_record():
    """🔴 ไฟล์จริง — ทุก record ต้องถูกจัดกลุ่ม ห้ามหายเงียบ"""
    adapter = AOWorkbookAdapter()
    base = [e.canonical_record for e in adapter.extract(SOURCE_DIR / FY69)]
    curr = [e.canonical_record for e in adapter.extract(SOURCE_DIR / FY70)]
    result = match_records(base, curr)
    assert result.accounted() == len(base) + len(curr)
    assert result.matched


@needs_sources
def test_real_pair_matches_same_year_across_different_cells():
    """🔑 ปีเดียวกันจับคู่ได้แม้อยู่คนละเซลล์ — พิสูจน์ว่าไม่ได้เทียบตามตำแหน่ง

    ในไฟล์จริง ``ปี 2570`` ของ ``รวมทั้งสิ้น`` อยู่ที่ ``Sheet5!E6`` ของแฟ้ม FY2569
    แต่อยู่ที่ ``Sheet5!D6`` ของแฟ้ม FY2570
    """
    adapter = AOWorkbookAdapter()
    base = [e.canonical_record for e in adapter.extract(SOURCE_DIR / FY69)]
    curr = [e.canonical_record for e in adapter.extract(SOURCE_DIR / FY70)]
    result = match_records(base, curr)

    hits = [
        p for p in result.matched
        if p.key.row_label_norm == "รวมทั้งสิ้น"
        and p.key.sheet_role == "SECTION_05"
        and p.fiscal_year == 2570
    ]
    assert len(hits) == 1
    pair = hits[0]
    assert pair.baseline.cell_ref == "E6"
    assert pair.current.cell_ref == "D6"
    assert pair.baseline.cell_ref != pair.current.cell_ref


@needs_sources
def test_real_pair_produces_traceable_findings():
    """ทุก finding ที่เทียบค่าได้ต้องชี้กลับเซลล์จริงทั้งสองฝั่ง"""
    adapter = AOWorkbookAdapter()
    base = [e.canonical_record for e in adapter.extract(SOURCE_DIR / FY69)]
    curr = [e.canonical_record for e in adapter.extract(SOURCE_DIR / FY70)]
    result = compare(match_records(base, curr))

    valued = [
        f for f in result.findings
        if f.finding_type in (F_AMOUNT_INCREASED, F_AMOUNT_DECREASED, F_AMOUNT_UNCHANGED)
    ]
    assert valued
    for finding in valued:
        assert finding.baseline_location and finding.baseline_location.cell
        assert finding.current_location and finding.current_location.cell
        assert finding.difference == finding.current_value - finding.baseline_value
        # G1 (#14) — แถวค่าเดี่ยวหน่วยบาทเป็นแกน SINGLE_AMOUNT เท่านั้น
        assert (finding.declared_unit == UNIT_MILLION_BAHT or not finding.declared_unit
                or finding.comparison_axis == "SINGLE_AMOUNT")


@needs_sources
def test_real_pair_flags_unmapped_for_human_review():
    """ชีตที่ยังไม่ map ต้องปรากฏเป็น finding ที่ต้องให้มนุษย์ตรวจ"""
    adapter = AOWorkbookAdapter()
    base = [e.canonical_record for e in adapter.extract(SOURCE_DIR / FY69)]
    curr = [e.canonical_record for e in adapter.extract(SOURCE_DIR / FY70)]
    result = compare(match_records(base, curr))

    by_type = result.by_type()
    assert by_type.get("UNMAPPED_REQUIRES_HUMAN_REVIEW", 0) > 0
    assert all(f.requires_human_decision for f in result.requiring_review())


# ────────────────────────────────────── review fixes จาก BO REVIEW COMPLETE
def test_reviewfix_one_sided_findings_preserve_side():
    """🔴 review fix 1 — record ฝั่งเดียวต้องคงไว้ว่ามาจาก baseline หรือ current

    ก่อนแก้: ทั้ง ``needs_human`` และ ``unmapped`` ถูกยัดลง ``baseline_location``
    หมด ทำให้ finding ของฝั่ง current ชี้ผิดฝั่ง
    """
    blocked = dict(unit=UNIT_UNRESOLVED, uncertainty=("declared_unit_unresolved",))
    base = [_rec(label="ฝั่งตั้งต้น", year=2569, value="1", cell="C9", **blocked)]
    curr = [_rec(label="ฝั่งปัจจุบัน", year=2569, value="2", cell="D9", **blocked)]
    result = compare(match_records(base, curr))

    ambiguous = [f for f in result.findings if f.finding_type == "AMBIGUOUS_REQUIRES_HUMAN_REVIEW"]
    assert len(ambiguous) == 2

    from_base = next(f for f in ambiguous if f.key.row_label_norm == "ฝั่งตั้งต้น")
    from_curr = next(f for f in ambiguous if f.key.row_label_norm == "ฝั่งปัจจุบัน")

    assert from_base.baseline_location and from_base.baseline_location.cell == "C9"
    assert from_base.current_location is None
    assert "[baseline]" in from_base.detail

    assert from_curr.current_location and from_curr.current_location.cell == "D9"
    assert from_curr.baseline_location is None
    assert "[current]" in from_curr.detail


def test_reviewfix_ordinal_finding_has_both_source_locations():
    """🔴 review fix 2 — ``PROJECT_ORDINAL_CHANGED`` ต้องชี้กลับทั้งสองฝั่ง"""
    args = dict(label="รวมทั้งสิ้น", year=2569, role=SECTION_ROLE_PROJECT)
    base = [_rec(value="10", ordinal="โครงการที่ 2", sheet="Sheet7.4.2", cell="C6", **args)]
    curr = [_rec(value="12", ordinal="โครงการที่ 3", sheet="Sheet7.3.3", cell="D6", **args)]
    result = compare(match_records(base, curr))

    finding = next(
        f for f in result.findings if f.finding_type == F_PROJECT_ORDINAL_CHANGED
    )
    assert finding.baseline_location.sheet == "Sheet7.4.2"
    assert finding.baseline_location.cell == "C6"
    assert finding.current_location.sheet == "Sheet7.3.3"
    assert finding.current_location.cell == "D6"
    assert finding.fiscal_year == 2569


def test_reviewfix_comparable_years_are_scoped_per_sheet_not_workbook():
    """🔴 review fix 3 — ปีที่เทียบได้ต้องคิด **รายขอบเขตชีต**

    จำลองอาการจริง: ชีตบทบาท ``5.`` มีปี 2569–2570 ทั้งสองฝั่ง
    แต่ชีตบทบาท ``8.`` ของฝั่งตั้งต้นเริ่มที่ปี 2567 ซึ่งอีกฝั่งไม่มี

    ถ้าคิด union ระดับสมุดงาน ปี 2567 จะถูกนับว่า "เทียบได้"
    ทั้งที่ไม่มีชีตใดของอีกฝั่งมีปีนั้นเลย
    """
    base = [
        _rec(label="ก", year=2569, value="1", role="SECTION_05"),
        _rec(label="ข", year=2567, value="2", role="SECTION_08"),
    ]
    curr = [
        _rec(label="ก", year=2569, value="3", role="SECTION_05"),
        _rec(label="ข", year=2569, value="4", role="SECTION_08"),
    ]
    result = match_records(base, curr)

    scopes = {s.scope[0]: s for s in result.year_scopes}
    assert scopes["SECTION_05"].comparable == (2569,)
    assert scopes["SECTION_05"].baseline_only == ()
    # ขอบเขต 8. ไม่มีปีร่วมกันเลย
    assert scopes["SECTION_08"].comparable == ()
    assert scopes["SECTION_08"].baseline_only == (2567,)
    assert scopes["SECTION_08"].current_only == (2569,)

    # จับคู่ได้เฉพาะขอบเขต 5.
    assert len(result.matched) == 1
    assert result.matched[0].key.sheet_role == "SECTION_05"


def test_reviewfix_year_gap_finding_names_its_scope():
    """finding ของปีที่มีข้างเดียวต้องบอกด้วยว่าเป็นขอบเขตใด"""
    base = [_rec(label="ข", year=2567, value="2", role="SECTION_08")]
    curr = [_rec(label="ข", year=2569, value="4", role="SECTION_08")]
    result = compare(match_records(base, curr))

    gaps = [f for f in result.findings if f.finding_type == F_YEAR_ONLY_ONE_SIDE]
    assert len(gaps) == 2
    assert all("SECTION_08" in f.detail for f in gaps)
    assert all(f.key.sheet_role == "SECTION_08" for f in gaps)


# ─────────────────────────── มิติ budget_category (1 ก.ย. 2569)
def _cat_rec(*, label, category, value, sheet="Sheet6", cell="C11", row=11,
             role="SECTION_06", raw_header="งบลงทุน"):
    return T1BRecord(
        key=T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                   agency_identity=AGENCY,
                   sheet_role=role, row_label_norm=label),
        row_kind=ROW_KIND_VALUE, comparison_axis=AXIS_BUDGET_CATEGORY,
        budget_category=category, budget_category_raw=raw_header,
        declared_unit=UNIT_MILLION_BAHT, is_monetary=True,
        value_decimal=Decimal(value), raw_value=value,
        sheet_name_actual=sheet, cell_ref=cell, row_index=row,
    )


def test_category_dimension_matches_like_fiscal_year():
    """``budget_category`` เป็นมิติเทียบ เหมือน ``fiscal_year``"""
    base = [_cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_INVESTMENT, value="1.0", cell="D11")]
    curr = [_cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_INVESTMENT, value="2.0", cell="C11")]
    result = compare(match_records(base, curr))

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.finding_type == F_AMOUNT_INCREASED
    assert finding.budget_category == CATEGORY_INVESTMENT
    assert finding.baseline_location.cell == "D11"
    assert finding.current_location.cell == "C11"


def test_different_budget_categories_never_match():
    """🔴 คนละหมวดงบรายจ่ายต้องไม่ถูกจับคู่ แม้คีย์และแถวเดียวกัน"""
    base = [_cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_INVESTMENT, value="1.0")]
    curr = [_cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_SUBSIDY, value="1.0")]
    result = match_records(base, curr)

    assert result.matched == []
    assert len(result.baseline_only) == 1
    assert len(result.current_only) == 1


def test_category_and_year_records_never_cross_match():
    """record ของตารางรายปีต้องไม่จับคู่กับ record ของตารางงบรายจ่าย"""
    base = [_cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_TOTAL, value="1.0", role="SECTION_05")]
    curr = [_rec(label="รวมทั้งสิ้น", year=2569, value="1.0")]
    result = match_records(base, curr)
    assert result.matched == []


def test_ordinal_finding_is_one_per_project_not_per_row():
    """🔴 ``PROJECT_ORDINAL_CHANGED`` = **หนึ่งใบต่อหนึ่งโครงการ**

    ก่อนแก้: dedupe ด้วย ``T1BKey`` เต็ม (ซึ่งมี ``row_label_norm``)
    ⇒ ได้ finding หนึ่งใบต่อหนึ่งแถวที่จับคู่ได้ — พบจริง **15 ใบสำหรับ 2 โครงการ**
    """
    common = dict(role=SECTION_ROLE_PROJECT, year=2569)
    base = [
        _rec(label="รวมทั้งสิ้น", value="1", ordinal="โครงการที่ 2", **common),
        _rec(label="เงินงบประมาณ", value="2", ordinal="โครงการที่ 2", **common),
        _rec(label="เงินนอกงบประมาณ", value="3", ordinal="โครงการที่ 2", **common),
    ]
    curr = [
        _rec(label="รวมทั้งสิ้น", value="1", ordinal="โครงการที่ 3", **common),
        _rec(label="เงินงบประมาณ", value="2", ordinal="โครงการที่ 3", **common),
        _rec(label="เงินนอกงบประมาณ", value="3", ordinal="โครงการที่ 3", **common),
    ]
    result = compare(match_records(base, curr))

    ordinal = [f for f in result.findings if f.finding_type == F_PROJECT_ORDINAL_CHANGED]
    assert len(ordinal) == 1, "สามแถวของโครงการเดียวกันต้องได้ finding ใบเดียว"
    assert "หนึ่ง finding ต่อหนึ่งโครงการ" in ordinal[0].detail


# ═══════════ BO REVIEW — semantics ของแกนเทียบและหมวดงบรายจ่าย (9 ข้อ)
def test_bo1_same_key_same_canonical_category_matches():
    """1 · คีย์เดียวกัน + หมวด canonical เดียวกัน → จับคู่ได้"""
    base = [_cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_INVESTMENT, value="1.0")]
    curr = [_cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_INVESTMENT, value="2.0")]
    result = match_records(base, curr)
    assert len(result.matched) == 1


def test_bo2_same_key_different_category_does_not_match():
    """2 · คีย์เดียวกันแต่คนละหมวด → ไม่จับคู่ตรง ๆ"""
    base = [_cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_INVESTMENT, value="1.0")]
    curr = [_cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_SUBSIDY, value="1.0")]
    result = match_records(base, curr)
    assert result.matched == []
    assert len(result.baseline_only) == 1 and len(result.current_only) == 1


def test_bo3_fiscal_year_axis_never_matches_budget_category_axis():
    """3 · แกน ``FISCAL_YEAR`` ห้ามจับคู่กับแกน ``BUDGET_CATEGORY``

    บังคับด้วย ``comparison_axis`` ในลายเซ็นโดยตรง ไม่พึ่ง invariant ที่ซ่อนอยู่
    """
    year_rec = _rec(label="รวมทั้งสิ้น", year=2569, value="1.0")
    cat_rec = _cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_TOTAL,
                       value="1.0", role="SECTION_05")
    assert year_rec.comparison_axis == AXIS_FISCAL_YEAR
    assert cat_rec.comparison_axis == AXIS_BUDGET_CATEGORY

    result = match_records([year_rec], [cat_rec])
    assert result.matched == []
    assert len(result.baseline_only) == 1 and len(result.current_only) == 1


def test_bo4_total_never_collides_with_sub_categories():
    """4 · ``TOTAL`` ห้ามชนกับหมวดย่อย"""
    total = _cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_TOTAL, value="3.0")
    for sub in (CATEGORY_INVESTMENT, CATEGORY_SUBSIDY):
        result = match_records(
            [total], [_cat_rec(label="รวมทั้งสิ้น", category=sub, value="3.0")]
        )
        assert result.matched == [], f"TOTAL ไม่ควรจับคู่กับ {sub}"


def test_bo5_unknown_category_is_unresolved_and_needs_review():
    """5 · หัวคอลัมน์หมวดที่ไม่รู้จัก → ``UNRESOLVED`` + เข้าคิวมนุษย์ · ค่าห้ามหาย"""
    unknown = _cat_rec(
        label="รวมทั้งสิ้น", category=CATEGORY_UNRESOLVED, value="99.0",
        raw_header="งบชดใช้เงินคงคลัง",
    )
    unknown = replace(unknown, uncertainty=("budget_category_unresolved",))

    assert unknown.needs_review
    assert unknown.value_decimal == Decimal("99.0")      # ค่ายังอยู่

    result = match_records([unknown], [])
    assert result.matched == []
    assert len(result.needs_human) == 1
    assert result.needs_human[0].record.budget_category_raw == "งบชดใช้เงินคงคลัง"


def test_bo6_budget_category_raw_is_preserved_through_compare():
    """6 · ``budget_category_raw`` ต้องรอดมาถึงชั้น finding"""
    base = [_cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_INVESTMENT,
                     value="1.0", raw_header="งบลงทุน")]
    curr = [_cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_INVESTMENT,
                     value="2.0", raw_header="งบลงทุน")]
    finding = compare(match_records(base, curr)).findings[0]

    assert finding.budget_category == CATEGORY_INVESTMENT
    assert finding.budget_category_raw == "งบลงทุน"
    assert finding.comparison_axis == AXIS_BUDGET_CATEGORY


def test_bo7_accounting_complete_when_unknown_category_present():
    """7 · มี record หมวดที่ resolve ไม่ได้ปนอยู่ accounting ต้องยังครบ"""
    unknown = replace(
        _cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_UNRESOLVED, value="99.0",
                 raw_header="งบชดใช้เงินคงคลัง"),
        uncertainty=("budget_category_unresolved",),
    )
    base = [
        _cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_INVESTMENT, value="1.0"),
        unknown,
    ]
    curr = [_cat_rec(label="รวมทั้งสิ้น", category=CATEGORY_INVESTMENT, value="2.0")]
    result = match_records(base, curr)

    assert result.accounted() == len(base) + len(curr)
    assert len(result.needs_human) == 1


def test_bo8_ordinal_finding_is_one_per_project_across_rows_and_years():
    """8 · ordinal changed = **หนึ่งใบต่อหนึ่งคู่โครงการ** แม้หลายแถวและหลายปี"""
    rows = ("รวมทั้งสิ้น", "เงินงบประมาณ", "เงินนอกงบประมาณ")
    years = (2569, 2570, 2571)
    base = [
        _rec(label=r, year=y, value="1", role=SECTION_ROLE_PROJECT,
             ordinal="โครงการที่ 2")
        for r in rows for y in years
    ]
    curr = [
        _rec(label=r, year=y, value="2", role=SECTION_ROLE_PROJECT,
             ordinal="โครงการที่ 3")
        for r in rows for y in years
    ]
    result = compare(match_records(base, curr))

    ordinal = [f for f in result.findings if f.finding_type == F_PROJECT_ORDINAL_CHANGED]
    assert len(ordinal) == 1, f"9 คู่ของโครงการเดียวกันต้องได้ finding ใบเดียว ได้ {len(ordinal)}"


@pytest.mark.parametrize(
    "axis, year, category",
    [
        (AXIS_FISCAL_YEAR, 2569, CATEGORY_INVESTMENT),   # มีทั้งคู่
        (AXIS_FISCAL_YEAR, None, None),                  # ไม่มีทั้งคู่
        (AXIS_BUDGET_CATEGORY, 2569, CATEGORY_INVESTMENT),
        (AXIS_BUDGET_CATEGORY, None, None),
        (AXIS_UNRESOLVED, 2569, None),                   # แกนไม่ระบุ
    ],
)
def test_bo9_invalid_axis_combination_never_auto_matches(axis, year, category):
    """9 · แกนเทียบไม่ถูกต้อง → ไม่จับคู่อัตโนมัติ **ห้ามเดา**"""
    bad = T1BRecord(
        key=T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                   agency_identity=AGENCY,
                   sheet_role="SECTION_05", row_label_norm="รวมทั้งสิ้น"),
        row_kind=ROW_KIND_VALUE, comparison_axis=axis,
        fiscal_year=year, budget_category=category,
        declared_unit=UNIT_MILLION_BAHT, is_monetary=True,
        value_decimal=Decimal("1.0"), raw_value="1.0",
        sheet_name_actual="Sheet5", cell_ref="C6", row_index=6,
    )
    assert not bad.axis_valid
    assert bad.needs_review

    result = match_records([bad], [bad])
    assert result.matched == []
    assert len(result.needs_human) == 2
