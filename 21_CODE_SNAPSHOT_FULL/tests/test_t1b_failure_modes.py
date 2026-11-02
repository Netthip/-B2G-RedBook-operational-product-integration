# -*- coding: utf-8 -*-
"""T1B — ชุดทดสอบ silent failure ที่พบจริงในไฟล์คาดแดง

**SYNTHETIC TEST FIXTURE** — ค่าที่ใช้ทดสอบในไฟล์นี้เป็นข้อมูลจำลองที่สร้างขึ้น
เพื่อ**จำลองอาการ**ที่ตรวจพบในไฟล์จริงเท่านั้น
🔴 ห้ามรายงานผลจากชุดทดสอบนี้ว่าเป็นข้อผิดพลาดที่พบใน workbook จริง
(คำสั่ง Gift ข้อ 8 · 1 ก.ย. 2569)

ที่มาของแต่ละอาการอ้างไฟล์จริงไว้ใน docstring ของแต่ละการทดสอบ
หลักฐานเต็มอยู่ที่ ``09_RESEARCH_BRIDGE/T1B_STRUCTURAL_MAP.md``
และ ``09_RESEARCH_BRIDGE/T1B_CANONICAL_KEY_SPEC.md``

ลำดับข้อ 1–8 ตามคำสั่ง Gift · ข้อ 9–11 เป็นอาการที่ Giho พบเพิ่มจากข้อมูลจริง
"""
from decimal import Decimal

import pytest

from redbook.t1b import (
    DOCUMENT_LEVEL_AGENCY,
    DOCUMENT_LEVEL_MINISTRY,
    SHEET_CLASS_MAIN,
    SHEET_CLASS_SUPPORTING,
    UNIT_MILLION_BAHT,
    UNIT_PERCENT,
    UNIT_UNRESOLVED,
    SheetFacts,
    T1BKey,
    align_years,
    amounts_equal,
    classify_sheet,
    comparable_units,
    is_monetary,
    locate_header_row,
    normalize_amount,
    normalize_label,
    parse_hierarchy,
    resolve_declared_unit,
    resolve_document_level,
    resolve_sheet_role,
    resolve_year_columns,
)
from redbook.t1b.header import years_only_in

# ข้อความ A1 จริงจากไฟล์ (ตัดให้สั้น) — ใช้เป็น fixture ของบทบาทชีต
A1_AGENCY_S5 = "5. เป้าหมายการให้บริการหน่วยงาน งบประมาณและประมาณการรายจ่ายล่วงหน้า"
A1_MINISTRY_S5 = "5. เป้าหมายการให้บริการกระทรวง งบประมาณและประมาณการรายจ่ายล่วงหน้า"
A1_AGENCY_S8 = "8. รายงานสถานะและแผนการใช้จ่ายเงินนอกงบประมาณ"


# ────────────────────────────────────────────────────────────── 1
def test_fm01_sheet_name_changes_but_a1_role_is_stable():
    """FM-01 · ชื่อชีตเปลี่ยนแต่บทบาทเดิม → ต้องจับคู่ได้

    จริง: 21000 มีชีต ``ข้อ 5`` · 21011 และ 21016 มีชีต ``Sheet5``
    ทั้งสามไฟล์มี ``A1`` ขึ้นต้นด้วย ``5.`` เหมือนกัน
    และ 21011 เปลี่ยน ``Sheet7_2 (2)`` (FY2569) เป็น ``Sheet 7.2`` (FY2570)
    """
    assert resolve_sheet_role(A1_AGENCY_S5) == "SECTION_05"
    assert resolve_sheet_role(A1_MINISTRY_S5) == "SECTION_05"
    assert resolve_sheet_role(A1_AGENCY_S8) == "SECTION_08"

    # ชื่อชีตต่างกันสิ้นเชิงแต่บทบาทต้องเท่ากัน
    for name in ("Sheet5", "ข้อ 5", "Sheet 7.2", "Sheet7_2 (2)"):
        assert resolve_sheet_role(A1_AGENCY_S5) == "SECTION_05", name


def test_fm01_sheet_name_is_never_used_as_role():
    """FM-01b · ชื่อชีตล้วน ๆ ต้องไม่ให้บทบาทใด — กันการเผลอใช้ชื่อเป็นคีย์"""
    for name in ("Sheet5", "Sheet7_1", "บุค", "bบุค", "Bยุท"):
        assert resolve_sheet_role(name) is None


# ────────────────────────────────────────────────────────────── 2
def test_fm02_sheet_index_shift_does_not_affect_role():
    """FM-02 · index ของชีตเลื่อน → ต้องไม่กระทบการจับคู่

    จริง: 21016 มี 17 ชีตในปี 2569 แต่ 19 ชีตในปี 2570
    ชีตบทบาท ``8.`` อยู่ index 16 ในปี 2569 แต่ index 18 ในปี 2570
    """
    fy69 = SheetFacts(name="Sheet8", index=16, a1=A1_AGENCY_S8,
                      max_row=30, max_column=8, merged_count=5)
    fy70 = SheetFacts(name="Sheet8", index=18, a1=A1_AGENCY_S8,
                      max_row=32, max_column=10, merged_count=7)

    assert fy69.index != fy70.index
    assert resolve_sheet_role(fy69.a1) == resolve_sheet_role(fy70.a1) == "SECTION_08"
    assert classify_sheet(fy69) == classify_sheet(fy70) == SHEET_CLASS_MAIN


# ────────────────────────────────────────────────────────────── 3
def test_fm03_thai_supporting_sheet_is_classified():
    """FM-03 · ชีต ``บุค`` ภาษาไทย → ต้อง classify ได้

    จริง: 21011 FY2569 มีชีต ``บุค`` (837 แถว · merged = 0)
    ซึ่ง defect เดิม ``supporting_sheet_prefixes = ("b","B")`` จับไม่ได้
    เพราะขึ้นต้นด้วย ``บ`` ภาษาไทย ไม่ใช่ ``b`` ละติน
    """
    thai = SheetFacts(name="บุค", index=5, a1=None,
                      max_row=837, max_column=12, merged_count=0)
    latin = SheetFacts(name="bบุค", index=5, a1=None,
                       max_row=811, max_column=12, merged_count=0)
    upper = SheetFacts(name="Bยุท", index=9, a1=None,
                       max_row=840, max_column=12, merged_count=0)

    assert classify_sheet(thai) == SHEET_CLASS_SUPPORTING
    assert classify_sheet(latin) == SHEET_CLASS_SUPPORTING
    assert classify_sheet(upper) == SHEET_CLASS_SUPPORTING


def test_fm03_main_sheet_not_misread_as_supporting():
    """FM-03b · ชีตหลักต้องไม่ถูกจัดเป็นชีตประกอบแม้ชื่อขึ้นต้นด้วยตัวอักษรใด"""
    main = SheetFacts(name="B", index=7, a1=A1_AGENCY_S5,
                      max_row=17, max_column=9, merged_count=1)
    assert classify_sheet(main) == SHEET_CLASS_MAIN


# ────────────────────────────────────────────────────────────── 4
def test_fm04_year_columns_align_by_label_not_position():
    """FM-04 · คอลัมน์ปีเลื่อน → ต้องจับด้วยป้ายปี ไม่ใช่ตัวอักษรคอลัมน์

    จริง: ไฟล์ FY2569 มีป้าย ``ปี 2568``..``ปี 2572``
    ไฟล์ FY2570 มีป้าย ``ปี 2569``..``ปี 2573``
    คอลัมน์ C ของสองไฟล์จึงเป็นคนละปีงบประมาณ
    """
    hdr69 = ["ตัวชี้วัด", "หน่วยนับ", "ปี 2568", "ปี 2569", "ปี 2570", "ปี 2571", "ปี 2572"]
    hdr70 = ["ตัวชี้วัด", "หน่วยนับ", "ปี 2569", "ปี 2570", "ปี 2571", "ปี 2572", "ปี 2573"]

    # ปี 2569 อยู่คอลัมน์ index 3 ในไฟล์เก่า แต่ index 2 ในไฟล์ใหม่
    assert resolve_year_columns(hdr69)[2569] == 3
    assert resolve_year_columns(hdr70)[2569] == 2

    aligned = align_years(hdr69, hdr70)
    assert aligned[2569] == (3, 2)
    assert set(aligned) == {2569, 2570, 2571, 2572}

    # ปีที่มีข้างเดียวต้องถูกแยกออก ไม่ใช่เทียบมั่ว
    assert years_only_in(hdr69, hdr70) == [2568]
    assert years_only_in(hdr70, hdr69) == [2573]


def test_fm04_same_column_position_is_a_different_year():
    """FM-04b · ตำแหน่งคอลัมน์เดียวกัน = คนละปี — กันการเทียบตามตำแหน่ง"""
    hdr69 = ["ตัวชี้วัด", "หน่วยนับ", "ปี 2568"]
    hdr70 = ["ตัวชี้วัด", "หน่วยนับ", "ปี 2569"]
    assert resolve_year_columns(hdr69)[2568] == resolve_year_columns(hdr70)[2569] == 2
    assert align_years(hdr69, hdr70) == {}


# ────────────────────────────────────────────────────────────── 5
def test_fm05_units_are_not_interchangeable():
    """FM-05 · ``บาท`` / ``ล้านบาท`` / ``ร้อยละ`` → ห้ามตีความเป็นชนิดเดียวกัน

    จริง: ชีตบทบาท ``5.`` มีทั้งแถว ``ล้านบาท`` และแถว ``ร้อยละ``
    และในสมุดงานเล่มเดียวกันมีทั้งหน่วย ``บาท`` และ ``ล้านบาท``
    """
    assert resolve_declared_unit("ล้านบาท") == UNIT_MILLION_BAHT
    assert resolve_declared_unit("ร้อยละ") == UNIT_PERCENT
    assert resolve_declared_unit("หน่วย : ล้านบาท (ทศนิยม 4 ตำแหน่ง)") == UNIT_MILLION_BAHT

    assert is_monetary(UNIT_MILLION_BAHT)
    assert not is_monetary(UNIT_PERCENT)

    assert not comparable_units("บาท", UNIT_MILLION_BAHT)
    assert not comparable_units(UNIT_MILLION_BAHT, UNIT_PERCENT)
    assert comparable_units(UNIT_MILLION_BAHT, UNIT_MILLION_BAHT)


# ────────────────────────────────────────────────────────────── 6
@pytest.mark.parametrize(
    "raw, expected",
    [
        (937.5201000000001, "937.5201"),
        (1066.0012000000002, "1066.0012"),
        (1119.3357999999998, "1119.3358"),
        (1182.6797000000001, "1182.6797"),
        (53.2712, "53.2712"),
    ],
)
def test_fm06_float_residue_is_normalized(raw, expected):
    """FM-06 · เศษ floating-point → ต้อง normalize เป็นค่าที่เอกสารประกาศ

    จริง: ``XL_FY2569_draft-bill_21011_HSRI.xlsx`` ชีต ``Sheet8``
    ประกาศ ``หน่วย : ล้านบาท (ทศนิยม 4 ตำแหน่ง)`` แต่เก็บค่า
    ``937.5201000000001`` ไว้ในเซลล์ D6
    """
    assert normalize_amount(raw, UNIT_MILLION_BAHT) == Decimal(expected)


def test_fm06_equal_after_normalization_no_false_positive():
    """FM-06b · ค่าที่ต่างกันเฉพาะเศษ binary ต้องไม่ถูกรายงานว่าเปลี่ยน"""
    assert amounts_equal(937.5201000000001, 937.5201, UNIT_MILLION_BAHT)
    # แต่ความต่างจริงในหลักที่เอกสารประกาศต้องยังจับได้
    assert not amounts_equal(937.5201, 937.5202, UNIT_MILLION_BAHT)


def test_fm06_declared_places_override():
    """FM-06c · ทศนิยมที่ประกาศในหัวชีตต้องมีน้ำหนักเหนือค่าปริยาย"""
    declaration = "หน่วย : ล้านบาท (ทศนิยม 4 ตำแหน่ง)"
    assert normalize_amount(1.23456789, UNIT_MILLION_BAHT, declaration) == Decimal("1.2346")


# ────────────────────────────────────────────────────────────── 7
def test_fm07_document_levels_must_not_match():
    """FM-07 · ระดับเอกสารต่างกัน → ห้ามจับคู่

    จริง: ``รวมทั้งสิ้น`` ปรากฏทั้งใน 21000 (ระดับกระทรวง · 173,390.171)
    และ 21011 (ระดับหน่วยงาน · 53.2712) โดยข้อความเหมือนกันทุกตัวอักษร
    """
    assert resolve_document_level(A1_MINISTRY_S5) == DOCUMENT_LEVEL_MINISTRY
    assert resolve_document_level(A1_AGENCY_S5) == DOCUMENT_LEVEL_AGENCY

    ministry = T1BKey(agency_code="21000", document_level=DOCUMENT_LEVEL_MINISTRY,
                      sheet_role="SECTION_05", row_label_norm="รวมทั้งสิ้น")
    agency = T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                    sheet_role="SECTION_05", row_label_norm="รวมทั้งสิ้น")

    assert ministry.row_label_norm == agency.row_label_norm
    assert not ministry.matchable_with(agency)
    assert ministry.is_ministry_level and not agency.is_ministry_level


def test_fm07_same_level_same_agency_matches():
    """FM-07b · คู่ที่ควรจับกันได้ต้องยังจับได้ — กันการกันเข้มเกินจนไม่เหลืออะไร"""
    a = T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
               sheet_role="SECTION_05", row_label_norm="รวมทั้งสิ้น")
    b = T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
               sheet_role="SECTION_05", row_label_norm="รวมทั้งสิ้น")
    assert a.matchable_with(b)


# ────────────────────────────────────────────────────────────── 8
def test_fm08_header_row_located_by_signature():
    """FM-08 · แถวหัวตารางอยู่คนละตำแหน่ง → ต้อง locate ด้วยลายเซ็น

    จริง: ระดับกระทรวงมีหัวตารางที่แถว 3 · ระดับหน่วยงานมีที่แถว 5
    """
    ministry_rows = [
        ["5. เป้าหมายการให้บริการกระทรวง …"],
        ["เป้าหมายการให้บริการกระทรวง", "งบประมาณ/ประมาณการรายจ่ายล่วงหน้า*"],
        ["ตัวชี้วัด", "หน่วยนับ", "ปี 2568", "ปี 2569"],
        ["รวมทั้งสิ้น", "ล้านบาท", 173390.171, 178795.0496],
    ]
    agency_rows = [
        ["5. เป้าหมายการให้บริการหน่วยงาน …"],
        [],
        [],
        ["เป้าหมายการให้บริการหน่วยงาน", "งบประมาณ / ประมาณการรายจ่ายล่วงหน้า"],
        ["ตัวชี้วัด", "หน่วยนับ", "ปี 2568", "ปี 2569"],
        ["รวมทั้งสิ้น", "ล้านบาท", 53.2712, 58.4401],
    ]

    assert locate_header_row(ministry_rows) == 3
    assert locate_header_row(agency_rows) == 5


def test_fm08_missing_header_returns_none_not_guess():
    """FM-08b · หาหัวตารางไม่พบต้องคืน ``None`` — ห้ามเดาแถวแรก"""
    assert locate_header_row([["ก"], ["ข"], ["ค"]]) is None


# ────────────────────────────────────────────────────────────── 9 (พบเพิ่ม)
def test_fm09_leading_and_trailing_space_drift():
    """FM-09 · ช่องว่างนำหน้า/ท้ายเปลี่ยนระหว่างปี → ต้องยังจับคู่ได้

    **อาการที่ Giho พบเพิ่ม** (ไม่อยู่ในรายการ 8 ข้อเดิม)
    จริง: ``'รวมเงินนอกงบประมาณ'`` ในไฟล์ FY2569 แถว 8
    กลายเป็น ``' รวมเงินนอกงบประมาณ'`` ในไฟล์ FY2570 แถว 8
    และ ``'- เงินกู้ต่างประเทศ '`` มีช่องว่างท้ายข้อความ
    """
    assert normalize_label("รวมเงินนอกงบประมาณ") == normalize_label(" รวมเงินนอกงบประมาณ")
    assert normalize_label("- เงินกู้ต่างประเทศ ") == "- เงินกู้ต่างประเทศ"

    fy69 = T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                  sheet_role="SECTION_05",
                  row_label_norm=normalize_label("รวมเงินนอกงบประมาณ"))
    fy70 = T1BKey(agency_code="21011", document_level=DOCUMENT_LEVEL_AGENCY,
                  sheet_role="SECTION_05",
                  row_label_norm=normalize_label(" รวมเงินนอกงบประมาณ"))
    assert fy69.matchable_with(fy70)


# ────────────────────────────────────────────────────────────── 10 (พบเพิ่ม)
def test_fm10_numeric_in_unit_cell_is_unresolved_not_guessed():
    """FM-10 · เซลล์หน่วยนับบรรจุตัวเลข → ต้องคืน ``UNRESOLVED`` ห้ามเดา

    **อาการที่ Giho พบเพิ่ม — เป็น data defect ของไฟล์ต้นทางเอง**
    จริง: ``XL_FY2570_draft-bill_21011_HSRI.xlsx`` ชีต ``Sheet5`` แถว 13–14
    คอลัมน์ ``B`` มีค่า ``100`` แทนที่จะเป็น ``ร้อยละ``
    ระบบต้องรายงาน ไม่ใช่ซ่อมให้เงียบ ๆ
    """
    assert resolve_declared_unit(100) == UNIT_UNRESOLVED
    assert resolve_declared_unit(None) == UNIT_UNRESOLVED
    assert resolve_declared_unit("") == UNIT_UNRESOLVED

    # UNRESOLVED เทียบกับอะไรไม่ได้เลย และไม่ใช่จำนวนเงิน
    assert not comparable_units(UNIT_UNRESOLVED, UNIT_PERCENT)
    assert not comparable_units(UNIT_UNRESOLVED, UNIT_UNRESOLVED)
    assert not is_monetary(UNIT_UNRESOLVED)


# ────────────────────────────────────────────────────────────── 11 (พบเพิ่ม)
def test_fm11_internal_whitespace_drift():
    """FM-11 · จำนวนช่องว่างภายในข้อความเปลี่ยน → ต้องยังจับคู่ได้

    **อาการที่ Giho พบเพิ่ม**
    จริง: ``'- ตัวชี้วัดเชิงคุณภาพ : การบริหารจัดการภายใต้'`` (FY2569 · เว้นวรรคเดียว)
    กลายเป็น ``'- ตัวชี้วัดเชิงคุณภาพ :  การบริหารจัดการภายใต้'`` (FY2570 · เว้นวรรคสองครั้ง)
    และป้ายจริงบางแถวมี ``\\n`` คั่นกลางข้อความ
    """
    one = "- ตัวชี้วัดเชิงคุณภาพ : การบริหารจัดการภายใต้\nโครงการเดิม"
    two = "- ตัวชี้วัดเชิงคุณภาพ :  การบริหารจัดการภายใต้ โครงการเดิม"
    assert normalize_label(one) == normalize_label(two)


# ────────────────────────────────────────── ลำดับชั้น (รองรับ FM-07 และ FM-09)
def test_hierarchy_disambiguates_repeated_labels():
    """ป้ายซ้ำใต้หัวข้อต่างกันต้องได้ ``hierarchy_path`` ต่างกัน

    จริง: ``' เงินงบประมาณ'`` อยู่ทั้งแถว 10 (ใต้ ``1.``) และแถว 15 (ใต้ ``2.``)
    ของชีต ``Sheet5`` ไฟล์ ``XL_FY2569_draft-bill_21011_HSRI.xlsx``
    โดยมีค่า 38.1527 กับ 15.1185 ตามลำดับ
    """
    labels = [
        "รวมทั้งสิ้น",
        "รวมเงินงบประมาณ",
        "รวมเงินนอกงบประมาณ",
        "1. เพื่อเป็นค่าใช้จ่ายในการดำเนินการภาครัฐ",
        " เงินงบประมาณ",
        " เงินนอกงบประมาณ",
        "2. การเพิ่มขีดความสามารถในการบริหารจัดการ",
        " เงินงบประมาณ",
    ]
    paths = parse_hierarchy(labels)

    assert paths[0] == ()                              # รวมทั้งสิ้น = ระดับบนสุด
    assert paths[3] == ("1",)                          # หัวข้อ 1
    assert paths[4] == ("1", "เงินงบประมาณ")
    assert paths[7] == ("2", "เงินงบประมาณ")
    assert paths[4] != paths[7]                        # ← จุดสำคัญ


def test_hierarchy_leading_space_before_first_parent_stays_top_level():
    """ช่องว่างนำหน้าที่เพิ่มเข้ามาก่อนหัวข้อแรกต้องไม่ทำให้กลายเป็นลูก

    จริง: ``' รวมเงินนอกงบประมาณ'`` ในไฟล์ FY2570 อยู่ก่อนหัวข้อ ``1.``
    """
    labels = ["รวมทั้งสิ้น", "รวมเงินงบประมาณ", " รวมเงินนอกงบประมาณ", "1. หัวข้อแรก"]
    paths = parse_hierarchy(labels)
    assert paths[2] == ()
    assert paths[3] == ("1",)


# ────────────────────────────────────────────────────────────── 12 (Gift อนุมัติ)
# FM-12 · section number semantic drift across fiscal years
# ป้ายกำกับ: PRODUCT EVIDENCE — POST-FREEZE
# 🔴 ห้ามเขียนย้อนกลับว่า FM-12 ถูกตรวจพบใน frozen T1A research evaluation
from redbook.t1b import SECTION_ROLE_PLAN, SECTION_ROLE_PROJECT, canonical_section  # noqa: E402
from redbook.t1b.normalize import strip_fiscal_years  # noqa: E402


def test_fm12_same_number_different_plan_must_not_match():
    """FM-12a · เลขข้อเหมือนกันแต่ชื่อแผนต่างกัน → **ห้าม match**

    จริง (21016): ``7.3`` ปี 2569 = *ส่งเสริมความสัมพันธ์ระหว่างประเทศ*
    แต่ ``7.3`` ปี 2570 = *เสริมสร้างให้คนมีสุขภาวะที่ดี*
    """
    fy69 = canonical_section("7.3 แผนงานยุทธศาสตร์ส่งเสริมความสัมพันธ์ระหว่างประเทศ")
    fy70 = canonical_section("7.3 แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี")

    assert fy69[0] == fy70[0] == SECTION_ROLE_PLAN     # บทบาทเดียวกัน
    assert fy69[1] != fy70[1]                          # แต่ตัวระบุต่างกัน

    a = T1BKey(agency_code="21016", document_level=DOCUMENT_LEVEL_AGENCY,
               sheet_role=fy69[0], section_title_norm=fy69[1])
    b = T1BKey(agency_code="21016", document_level=DOCUMENT_LEVEL_AGENCY,
               sheet_role=fy70[0], section_title_norm=fy70[1])
    assert not a.matchable_with(b)


def test_fm12_different_number_same_plan_can_match():
    """FM-12b · เลขข้อต่างกันแต่เป็นแผนเดียวกัน → **match ได้**

    จริง (21016): ``7.4`` ปี 2569 กับ ``7.3`` ปี 2570 เป็นแผนงานเดียวกัน
    """
    fy69 = canonical_section("7.4 แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี")
    fy70 = canonical_section("7.3 แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี")

    assert fy69 == fy70

    a = T1BKey(agency_code="21016", document_level=DOCUMENT_LEVEL_AGENCY,
               sheet_role=fy69[0], section_title_norm=fy69[1])
    b = T1BKey(agency_code="21016", document_level=DOCUMENT_LEVEL_AGENCY,
               sheet_role=fy70[0], section_title_norm=fy70[1])
    assert a.matchable_with(b)


def test_fm12_fiscal_year_in_title_normalized_without_destroying_identity():
    """FM-12c · หัวเรื่องที่ฝังปีงบประมาณ → ตัดปีออกโดยไม่ทำลาย semantic identity

    จริง: หัวเรื่องของบทบาท ``4.`` และ ``6.`` ฝังปีไว้
    (``"สรุปงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. 2569"`` เทียบ ``"… พ.ศ. 2570"``)
    ถ้าไม่ตัดปีออก รายการเดียวกันคนละปีจะไม่มีทางจับคู่กันได้เลย
    """
    a = strip_fiscal_years("สรุปงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. 2569")
    b = strip_fiscal_years("สรุปงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. 2570")
    assert a == b == "สรุปงบประมาณรายจ่ายประจำปีงบประมาณ"

    # 🔴 แต่ต้องไม่ทำลาย identity — ชื่อที่ต่างความหมายต้องยังต่างกัน
    c = strip_fiscal_years("แผนงานยุทธศาสตร์ส่งเสริมความสัมพันธ์ระหว่างประเทศ")
    d = strip_fiscal_years("แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี")
    assert c != d
    assert c and d

    # และหัวเรื่องของบทบาทโครงสร้างคงที่ต้อง **ไม่** ถูกนำเข้าคีย์เลย
    assert canonical_section("6. สรุปงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. 2569")[1] == ""
    assert canonical_section("4. เปรียบเทียบงบประมาณ พ.ศ. 2567 - 2569")[1] == ""


def test_fm12_plan_and_project_layers_never_cross_match():
    """FM-12d · ชั้นแผนงานกับชั้นโครงการต้องไม่จับคู่ข้ามกัน"""
    plan = canonical_section("7.3 แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี")
    project = canonical_section("7.3.2 โครงการที่ 2 : โครงการเครือข่ายความร่วมมือ")
    assert plan[0] == SECTION_ROLE_PLAN
    assert project[0] == SECTION_ROLE_PROJECT
    assert plan[0] != project[0]


def test_fm12_non_plan_sections_keep_their_number():
    """FM-12e · บทบาทโครงสร้างคงที่ต้องยังใช้เลขข้อเป็นคีย์ตามเดิม"""
    assert canonical_section("5. เป้าหมายการให้บริการหน่วยงาน")[0] == "SECTION_05"
    assert canonical_section("8. รายงานสถานะและแผนการใช้จ่ายเงิน")[0] == "SECTION_08"
    assert canonical_section("4.2 ความเชื่อมโยงแผนพัฒนา")[0] == "SECTION_04_02"


# ────────────────────────── FM-12 · ทาง (ค) — เลขลำดับโครงการไม่ใช่ identity
from redbook.t1b import split_project_title  # noqa: E402


def test_fm12f_project_ordinal_is_not_identity():
    """เลขลำดับ ``โครงการที่ N`` ต้องถูกแยกออกจาก identity

    จริง (21016): ``โครงการที่ 2`` ปี 2569 กับ ``โครงการที่ 3`` ปี 2570
    เป็น *โครงการขับเคลื่อนงานวัคซีนกับองค์กรภาคีเครือข่าย* เดียวกัน
    """
    ordinal_a, name_a = split_project_title(
        "โครงการที่ 2 : โครงการขับเคลื่อนงานวัคซีนกับองค์กรภาคีเครือข่าย"
    )
    ordinal_b, name_b = split_project_title(
        "โครงการที่ 3 : โครงการขับเคลื่อนงานวัคซีนกับองค์กรภาคีเครือข่าย"
    )
    assert ordinal_a == "โครงการที่ 2"
    assert ordinal_b == "โครงการที่ 3"
    assert ordinal_a != ordinal_b       # เลขลำดับต่างกันจริง
    assert name_a == name_b             # แต่ชื่อโครงการเดียวกัน

    a = T1BKey(agency_code="21016", document_level=DOCUMENT_LEVEL_AGENCY,
               sheet_role=SECTION_ROLE_PROJECT, section_title_norm=name_a,
               parent_plan_norm="แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี")
    b = T1BKey(agency_code="21016", document_level=DOCUMENT_LEVEL_AGENCY,
               sheet_role=SECTION_ROLE_PROJECT, section_title_norm=name_b,
               parent_plan_norm="แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี")
    assert a.matchable_with(b)          # ⇒ จับคู่กันได้


def test_fm12g_same_project_name_under_different_plan_must_not_match():
    """โครงการชื่อเดียวกันแต่อยู่คนละแผนงาน → **ห้าม match**"""
    name = "โครงการพัฒนาบุคลากรและการบริหารจัดการองค์กร"
    a = T1BKey(agency_code="21016", document_level=DOCUMENT_LEVEL_AGENCY,
               sheet_role=SECTION_ROLE_PROJECT, section_title_norm=name,
               parent_plan_norm="แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี")
    b = T1BKey(agency_code="21016", document_level=DOCUMENT_LEVEL_AGENCY,
               sheet_role=SECTION_ROLE_PROJECT, section_title_norm=name,
               parent_plan_norm="แผนงานบูรณาการรัฐบาลดิจิทัล")
    assert not a.matchable_with(b)


def test_fm12h_key_uses_exact_equality_not_fuzzy_similarity():
    """🔴 ``t1b-key-0.1.0`` ต้องจับคู่ด้วยความเท่ากันแบบตรงตัว **ห้าม fuzzy**

    ชื่อที่ต่างกันเพียงตัวอักษรเดียวต้อง **ไม่** ถูกจับเป็นรายการเดียวกัน
    ค่า similarity ใช้ได้เฉพาะเป็น *candidate ให้มนุษย์ดู* ในรายงาน audit
    """
    a = T1BKey(agency_code="21016", document_level=DOCUMENT_LEVEL_AGENCY,
               sheet_role=SECTION_ROLE_PROJECT,
               section_title_norm="โครงการขับเคลื่อนงานวัคซีนกับองค์กรภาคีเครือข่าย")
    b = T1BKey(agency_code="21016", document_level=DOCUMENT_LEVEL_AGENCY,
               sheet_role=SECTION_ROLE_PROJECT,
               section_title_norm="โครงการขับเคลื่อนงานวัคซีนกับองค์กรภาคีเครือข่ายฯ")
    assert not a.matchable_with(b)


def test_fm12i_ordinal_prefix_only_stripped_for_projects():
    """ต้องตัดเลขลำดับเฉพาะรูปแบบ ``โครงการที่ N :`` เท่านั้น

    ข้อความอื่นที่มีเครื่องหมาย ``:`` ต้องไม่ถูกตัดส่วนหน้าทิ้ง
    """
    assert split_project_title("ผลผลิต : การวิจัยเพื่อพัฒนา") == (
        None, "ผลผลิต : การวิจัยเพื่อพัฒนา"
    )
    assert split_project_title("แผนงานพื้นฐานด้านการพัฒนา") == (
        None, "แผนงานพื้นฐานด้านการพัฒนา"
    )
