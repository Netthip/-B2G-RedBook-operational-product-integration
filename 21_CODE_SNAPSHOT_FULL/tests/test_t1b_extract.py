# -*- coding: utf-8 -*-
"""T1B — ``AOWorkbookAdapter.extract()`` กับไฟล์จริงทั้ง 6 ไฟล์

ครอบคลุม invariant 8 ข้อที่ Gift กำหนด (1 ก.ย. 2569)

1. ทุก main/supporting sheet ที่ควรถูกอ่านต้องถูก account ครบ
2. ชีต ``บุค`` ต้องไม่หายเงียบ
3. sheet name/index เปลี่ยนต้องไม่เปลี่ยน canonical role
4. fiscal-year alignment ต้องอิง label ปี
5. ``บาท`` · ``ล้านบาท`` · ``ร้อยละ`` ต้องแยก type/semantic ถูก
6. float residue ต้อง normalize ด้วย ``Decimal`` ตาม declared precision
7. source location ต้อง trace กลับ workbook ได้
8. record ที่ระบบยังตีความไม่ได้ต้องออก ``REVIEW/UNRESOLVED`` ไม่เดา

ข้ามอัตโนมัติเมื่อไม่พบคลังข้อมูล (ไฟล์ข้อมูลอยู่นอก Git ตาม ``SYS-D-05``)
🔴 ชุดนี้ **อ่านอย่างเดียว** ไม่เขียนทับไฟล์ต้นทางใด
"""
import hashlib
import os
from decimal import Decimal
from pathlib import Path

import pytest

from redbook.adapters.ao_workbook import AOWorkbookAdapter, summarize
from redbook.adapters.base import ExtractionStatus, LocationKind
from redbook.t1b import (
    SECTION_ROLE_PLAN,
    SECTION_ROLE_PROJECT,
    UNIT_BAHT,
    UNIT_MILLION_BAHT,
    UNIT_PERCENT,
    UNIT_UNRESOLVED,
    resolve_declared_unit,
)
from redbook.t1b.records import ROW_KIND_UNMAPPED, ROW_KIND_VALUE

# 🔴 คิดจากที่อยู่ของไฟล์นี้ ไม่ใช่เส้นทางตายตัวที่มีชื่อผู้ใช้
# คลังข้อมูลเป็น repo พี่น้องที่วางข้าง ๆ repo โค้ด ⇒ ได้เส้นทางเดิมทุกประการ
# ห้ามเขียนกลับเป็นเส้นทางตายตัว — ชื่อผู้ใช้จะติดขึ้น git ไปด้วย
_DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "redbook-verify-data" / "sources" / "public" / "ao_workbook"
)
SOURCE_DIR = Path(os.environ.get("REDBOOK_T1B_SOURCE_DIR", _DEFAULT_SOURCE))

ALL_FILES = [
    "XL_FY2569_draft-bill_21000_MOPH-summary.xlsx",
    "XL_FY2569_draft-bill_21011_HSRI.xlsx",
    "XL_FY2569_draft-bill_21016_NVI.xlsx",
    "XL_FY2570_draft-bill_21000_MOPH-summary.xlsx",
    "XL_FY2570_draft-bill_21011_HSRI.xlsx",
    "XL_FY2570_draft-bill_21016_NVI.xlsx",
]
FY69_AGENCY, FY70_AGENCY = ALL_FILES[1], ALL_FILES[4]
FY69_NVI, FY70_NVI = ALL_FILES[2], ALL_FILES[5]

needs_sources = pytest.mark.skipif(
    not (SOURCE_DIR / ALL_FILES[0]).exists(),
    reason=f"ไม่พบคลังข้อมูล T1B ที่ {SOURCE_DIR} (ไฟล์ข้อมูลอยู่นอก Git ตาม SYS-D-05)",
)


@pytest.fixture(scope="module")
def adapter():
    return AOWorkbookAdapter()


def _records(envelopes):
    return [e.canonical_record for e in envelopes]


# ─────────────────────────────────────────── invariant 1 · account ครบทุกชีต
@needs_sources
@pytest.mark.parametrize("filename", ALL_FILES)
def test_inv1_every_sheet_is_accounted_for(adapter, filename):
    """ทุกชีตในไฟล์ต้องปรากฏใน record อย่างน้อยหนึ่งรายการ — ห้ามหายเงียบ"""
    path = SOURCE_DIR / filename
    inspected = adapter.inspect(path)
    summary = summarize(adapter.extract(path))

    sheets_in_file = {s["name_actual"] for s in inspected["sheets"]}
    sheets_in_records = set(summary["by_sheet_name"])
    assert sheets_in_file == sheets_in_records, (
        f"ชีตที่หายไปจากผลสกัด: {sorted(sheets_in_file - sheets_in_records)}"
    )
    assert summary["total"] > 0


# ─────────────────────────────────────────── invariant 2 · ชีต บุค ต้องไม่หาย
@needs_sources
def test_inv2_thai_supporting_sheet_is_not_dropped(adapter):
    """ชีต ``บุค`` (บ ภาษาไทย) ต้องมี record และต้องเห็นเนื้อหาจริง

    ``max_row`` ของชีตนี้คือ 837 แต่แถวที่มีเนื้อหาจริงมี 6 แถว
    (ส่วนที่เหลือเป็นแถวว่างที่ค้างจากการจัดรูปแบบ)
    """
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    buk = [r for r in records if r.sheet_name_actual == "บุค"]

    assert buk, "ชีต บุค หายไปจากผลสกัด"
    assert all(r.row_kind == ROW_KIND_UNMAPPED for r in buk)
    assert any("บุคลากรภาครัฐ" in str(r.raw_label) for r in buk)
    # ต้องบอกเหตุผลว่าทำไมยังไม่ map ไม่ใช่เงียบ ๆ
    assert all(r.uncertainty for r in buk)


# ─────────────────────────────────────────── invariant 3 · role คงที่
@needs_sources
def test_inv3_role_stable_although_sheet_name_and_index_change(adapter):
    """ชื่อชีตและ index เปลี่ยน แต่ canonical role ต้องไม่เปลี่ยน"""
    a = adapter.inspect(SOURCE_DIR / FY69_NVI)
    b = adapter.inspect(SOURCE_DIR / FY70_NVI)
    assert a["sheet_count"] != b["sheet_count"]        # 17 vs 19

    def roles(result):
        return {s["sheet_role"] for s in result["sheets"] if s["sheet_role"]}

    # บทบาทโครงสร้างคงที่ต้องมีครบทั้งสองปี
    #
    # **ปรับเมื่อ map 7.x (1 ก.ย. 2569)** — เดิมคาดว่ามี ``SECTION_07``
    # แต่ชีต ``Sheet7_1`` มี ``A1`` เป็นหัวบท ``7.`` ขณะที่ ``A2`` คือแผนงาน ``7.1``
    # ที่ชีตนั้นบรรจุข้อมูลอยู่จริง ⇒ ตอนนี้ชีตนั้นได้บทบาท ``SECTION_07_PLAN``
    for role in ("SECTION_04", "SECTION_05", "SECTION_06", "SECTION_08"):
        assert role in roles(a) and role in roles(b)
    assert SECTION_ROLE_PLAN in roles(a) and SECTION_ROLE_PLAN in roles(b)


@needs_sources
def test_inv3b_plan_sheets_match_by_name_not_section_number(adapter):
    """🔴 FM-12 · เลขข้อของชีตแผนงานเปลี่ยนความหมายระหว่างปี

    หลักฐานจริง (หน่วยงาน 21016)

    * ``7.3`` ปี 2569 = *แผนงานยุทธศาสตร์ส่งเสริมความสัมพันธ์ระหว่างประเทศ*
    * ``7.3`` ปี 2570 = *แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี*
    * ``7.4`` ปี 2569 = *แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี*

    ⇒ จับคู่ด้วยเลขข้อจะเทียบ **คนละแผนงาน** เข้าด้วยกัน
    และจะพลาดคู่ที่เป็นแผนงานเดียวกันแต่ถูกเรียงเลขใหม่
    """
    def plan_titles(filename):
        records = _records(adapter.extract(SOURCE_DIR / filename))
        return {
            r.key.section_title_norm
            for r in records
            if r.key.sheet_role == SECTION_ROLE_PLAN and r.key.section_title_norm
        }

    fy69 = plan_titles(FY69_NVI)
    fy70 = plan_titles(FY70_NVI)

    health = "แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี"
    intl = "แผนงานยุทธศาสตร์ส่งเสริมความสัมพันธ์ระหว่างประเทศ"

    # แผนเดียวกันถูกเรียงเลขใหม่ — ต้องจับคู่ได้ทั้งสองปี
    assert any(health in t for t in fy69)
    assert any(health in t for t in fy70)
    # แผนที่มีเฉพาะปี 2569 — ต้องไม่ถูกจับคู่กับแผนอื่น
    assert any(intl in t for t in fy69)
    assert not any(intl in t for t in fy70)


@needs_sources
def test_inv3c_project_sheets_do_not_cross_match_with_plan_sheets(adapter):
    """ชั้นแผนงานกับชั้นโครงการต้องไม่จับคู่ข้ามกัน"""
    records = _records(adapter.extract(SOURCE_DIR / FY70_NVI))
    roles = {r.key.sheet_role for r in records}
    assert SECTION_ROLE_PLAN in roles
    assert SECTION_ROLE_PROJECT in roles
    assert SECTION_ROLE_PLAN != SECTION_ROLE_PROJECT


# ─────────────────────────────────────────── invariant 4 · ปีจากป้าย
@needs_sources
def test_inv4_fiscal_year_comes_from_label(adapter):
    """ปีของ record ต้องมาจากป้าย ``ปี 25xx`` ไม่ใช่ตำแหน่งคอลัมน์"""
    def years_of(filename):
        records = _records(adapter.extract(SOURCE_DIR / filename))
        return {
            r.fiscal_year
            for r in records
            if r.row_kind == ROW_KIND_VALUE and r.key.sheet_role == "SECTION_05"
        }

    assert years_of(FY69_AGENCY) == {2568, 2569, 2570, 2571, 2572}
    assert years_of(FY70_AGENCY) == {2569, 2570, 2571, 2572, 2573}

    # ป้ายดิบต้องถูกเก็บไว้ด้วย — เฉพาะ record ของตารางรายปี
    # (ตารางจำแนกตามงบรายจ่ายไม่มีปี ใช้ ``budget_category`` แทน)
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    year_rows = [
        r for r in records
        if r.row_kind == ROW_KIND_VALUE and r.fiscal_year is not None
    ]
    assert year_rows
    assert all(r.fiscal_year_label == f"ปี {r.fiscal_year}" for r in year_rows)

    category_rows = [
        r for r in records
        if r.row_kind == ROW_KIND_VALUE and r.budget_category is not None
    ]
    assert category_rows
    assert all(r.fiscal_year is None and r.fiscal_year_label is None for r in category_rows)


@needs_sources
def test_inv4b_same_cell_reference_is_a_different_year(adapter):
    """เซลล์ตำแหน่งเดียวกันในสองไฟล์ต้องได้คนละปี — กันการเทียบตามตำแหน่ง"""
    def year_at(filename, cell):
        records = _records(adapter.extract(SOURCE_DIR / filename))
        hits = [
            r for r in records
            if r.cell_ref == cell and r.sheet_name_actual == "Sheet5"
        ]
        assert hits, f"ไม่พบเซลล์ {cell}"
        return hits[0].fiscal_year

    assert year_at(FY69_AGENCY, "C6") == 2568
    assert year_at(FY70_AGENCY, "C6") == 2569


# ─────────────────────────────────────────── invariant 5 · หน่วยนับ
@needs_sources
def test_inv5_units_are_separated_by_semantic_type(adapter):
    """``บาท`` · ``ล้านบาท`` · ``ร้อยละ`` ต้องแยกชนิดถูก และ ``ร้อยละ`` ต้องไม่ใช่เงิน"""
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    values = [r for r in records if r.row_kind == ROW_KIND_VALUE]

    units = {r.declared_unit for r in values}
    assert UNIT_MILLION_BAHT in units
    assert UNIT_PERCENT in units

    for rec in values:
        if rec.declared_unit == UNIT_PERCENT:
            assert not rec.is_monetary
        if rec.declared_unit in (UNIT_MILLION_BAHT, UNIT_BAHT):
            assert rec.is_monetary
        if rec.declared_unit == UNIT_UNRESOLVED:
            assert not rec.is_monetary


@needs_sources
def test_inv5b_unit_anomaly_is_flagged_not_guessed(adapter):
    """เซลล์หน่วยนับที่บรรจุตัวเลขต้องออกเป็น ``UNRESOLVED`` และติดธง

    หลักฐานจริง: ``XL_FY2570_draft-bill_21011_HSRI.xlsx`` ชีต ``Sheet5``
    แถว 13–14 คอลัมน์ ``B`` มีค่า ``100`` แทนที่จะเป็น ``ร้อยละ``
    """
    records = _records(adapter.extract(SOURCE_DIR / FY70_AGENCY))
    anomalies = [
        r for r in records
        if r.sheet_name_actual == "Sheet5"
        and r.declared_unit == UNIT_UNRESOLVED
        and r.row_kind == ROW_KIND_VALUE
    ]
    assert anomalies, "ควรพบ record ที่หน่วยนับ resolve ไม่ได้"
    assert all("declared_unit_unresolved" in r.uncertainty for r in anomalies)
    assert all(r.needs_review for r in anomalies)
    # ค่าดิบของเซลล์หน่วยนับต้องถูกเก็บไว้ให้ตรวจย้อน
    # ในไฟล์จริงค่านี้เก็บเป็นข้อความ "100" ไม่ใช่ตัวเลข — ทั้งสองแบบต้องไม่ผ่านเป็นหน่วย
    raw_units = {r.raw_unit_cell for r in anomalies}
    assert raw_units, "ต้องเก็บค่าดิบของเซลล์หน่วยนับไว้"
    assert all(resolve_declared_unit(u) == UNIT_UNRESOLVED for u in raw_units)
    assert any(str(u).strip() == "100" for u in raw_units)


# ─────────────────────────────────────────── invariant 6 · Decimal
@needs_sources
def test_inv6_float_residue_normalized_by_declared_precision(adapter):
    """ค่าที่มีเศษ float ต้องถูกปัดตามทศนิยมที่เอกสารประกาศ"""
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    money = [
        r for r in records
        if r.row_kind == ROW_KIND_VALUE and r.declared_unit == UNIT_MILLION_BAHT
        and r.value_decimal is not None
    ]
    assert money

    for rec in money:
        assert isinstance(rec.value_decimal, Decimal)
        assert -rec.value_decimal.as_tuple().exponent <= 4

    # ต้องมีอย่างน้อยหนึ่ง record ที่ค่าดิบยาวกว่าทศนิยมที่ประกาศ
    noisy = [
        r for r in money
        if isinstance(r.raw_value, float)
        and len(repr(r.raw_value).split(".")[-1]) > 4
    ]
    assert noisy, "ควรพบเศษ float ในไฟล์จริง"
    for rec in noisy:
        assert rec.value_decimal == Decimal(repr(rec.raw_value)).quantize(Decimal("0.0001"))
        assert rec.raw_value != rec.value_decimal    # ค่าดิบต้องไม่ถูกทับ


# ─────────────────────────────────────────── invariant 7 · trace กลับได้
@needs_sources
def test_inv7_source_location_traces_back_to_workbook(adapter):
    """ทุก record ต้องชี้กลับไฟล์ ชีต และแถว/เซลล์จริงได้"""
    import openpyxl

    path = SOURCE_DIR / FY69_AGENCY
    envelopes = adapter.extract(path)
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    for env in envelopes:
        assert env.source_hash == file_hash
        assert env.source_file == path
        assert env.source_location.sheet
        assert env.source_location.row and env.source_location.row > 0
        if env.canonical_record.row_kind == ROW_KIND_VALUE:
            assert env.source_location.location_kind is LocationKind.EXCEL_CELL
            assert env.source_location.cell
        else:
            assert env.source_location.location_kind is LocationKind.EXCEL_ROW

    # เปิดไฟล์จริงแล้วอ่านเซลล์ตามที่ record ชี้ ต้องได้ค่าดิบเดิม
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        checked = 0
        for env in envelopes:
            rec = env.canonical_record
            if rec.row_kind != ROW_KIND_VALUE or checked >= 25:
                continue
            assert wb[rec.sheet_name_actual][rec.cell_ref].value == rec.raw_value
            checked += 1
        assert checked >= 20
    finally:
        wb.close()


@needs_sources
def test_inv7b_extract_does_not_modify_source(adapter):
    """``extract()`` ต้องไม่แตะไฟล์ต้นทาง"""
    path = SOURCE_DIR / FY69_NVI
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    adapter.extract(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


# ─────────────────────────────────────────── invariant 8 · ไม่เดา
@needs_sources
@pytest.mark.parametrize("filename", ALL_FILES)
def test_inv8_unmapped_records_declare_a_reason(adapter, filename):
    """record ที่ตีความไม่ได้ต้องบอกเหตุผทและต้องเข้าคิวให้มนุษย์ตรวจ"""
    envelopes = adapter.extract(SOURCE_DIR / filename)
    for env in envelopes:
        rec = env.canonical_record
        if rec.row_kind == ROW_KIND_UNMAPPED:
            assert rec.uncertainty, "UNMAPPED ต้องระบุเหตุผลเสมอ"
            assert rec.needs_review
            assert env.extraction_status is ExtractionStatus.PARTIAL
            # ห้ามเดาค่า — ค่าที่ยังไม่ map ต้องไม่ถูกแปลงเป็น Decimal
            assert rec.value_decimal is None


@needs_sources
@pytest.mark.parametrize("filename", ALL_FILES)
def test_inv8b_provenance_uncertainty_is_always_declared(adapter, filename):
    """``agency_code`` และ ``document_status`` อ่านจากชื่อไฟล์ ต้องติดธงทุก record"""
    for env in adapter.extract(SOURCE_DIR / filename):
        assert "agency_code_from_filename" in env.uncertainty
        assert "document_status_from_filename" in env.uncertainty


# ─────────────────────────────────── regression · bug ที่พบตอนทำตัวอย่าง record
@needs_sources
@pytest.mark.parametrize(
    "filename, expected",
    [
        (FY69_AGENCY, "สถาบันวิจัยระบบสาธารณสุข"),
        (FY70_NVI, "สถาบันวัคซีนแห่งชาติ"),
        (ALL_FILES[0], "กระทรวงสาธารณสุข"),
    ],
)
def test_reg_agency_name_comes_from_first_cover_sheet_only(adapter, filename, expected):
    """🔴 ชื่อหน่วยงานต้องมาจากชีตปก **แรก** เท่านั้น

    bug ที่พบ: เดิมทุกชีตที่ถูกจัดเป็น ``COVER`` เขียนทับชื่อหน่วยงาน
    ทำให้ ``agency_name`` ของแฟ้ม 21016 กลายเป็นชื่อ *โครงการ* ของชีตท้าย ๆ
    (``'โครงการ : โครงการพัฒนาบุคลากรและการบริหารจัดการองค์กร'``)
    ⇒ provenance ของทุก record ในแฟ้มนั้นผิดหมด
    """
    records = _records(adapter.extract(SOURCE_DIR / filename))
    names = {r.agency_name for r in records}
    assert names == {expected}


@needs_sources
def test_reg_raw_unit_cell_points_at_what_decided_the_unit(adapter):
    """🔴 ``raw_unit_cell`` ต้องชี้ไปที่สิ่งที่ใช้ตัดสินหน่วยจริง

    bug ที่พบ: ในชีตบทบาท ``8.`` ที่ไม่มีคอลัมน์หน่วยรายแถว
    เดิมบันทึกค่าในคอลัมน์ ``B`` (ซึ่งเป็น **ค่าเงินของปี 2567**) เป็น
    ``raw_unit_cell`` ทำให้ผู้ตรวจย้อนกลับเห็นตัวเลขแทนที่จะเห็นข้อความประกาศหน่วย
    """
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    sheet8 = [
        r for r in records
        if r.sheet_name_actual == "Sheet8" and r.row_kind == ROW_KIND_VALUE
    ]
    assert sheet8

    for rec in sheet8:
        assert "unit_from_sheet_level_declaration" in rec.uncertainty
        assert isinstance(rec.raw_unit_cell, str)
        assert "ล้านบาท" in rec.raw_unit_cell
        assert rec.declared_unit == UNIT_MILLION_BAHT


@needs_sources
def test_reg_two_row_header_recovers_all_years(adapter):
    """🔴 หัวตารางสองแถวต้องรวมป้ายปีให้ครบ

    bug ที่พบ: ชีตบทบาท ``8.`` มีป้ายปีกระจายสองแถว (``B3`` และ ``C4..G4``)
    เดิมอ่านแถวเดียวจึงได้ปี 2567 ปีเดียว ⇒ record ทั้งหมดถูกติดป้ายปีผิด
    และค่าอีกห้าปีหายเงียบ (26 record แทนที่จะเป็น 156)
    """
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    sheet8 = [
        r for r in records
        if r.sheet_name_actual == "Sheet8" and r.row_kind == ROW_KIND_VALUE
    ]
    assert {r.fiscal_year for r in sheet8} == {2567, 2568, 2569, 2570, 2571, 2572}
    assert len(sheet8) == 156


@needs_sources
def test_reg_normalization_does_not_collapse_distinct_rows(adapter):
    """🔴 ห้าม normalize แรงจนรวมรายการที่ความหมายต่างกันเป็น record เดียว

    ข้อกำกับของ Gift (1 ก.ย. 2569) — ตรวจว่าในชีตเดียวกันและปีเดียวกัน
    ไม่มีคีย์ซ้ำที่ชี้ไปคนละเซลล์
    """
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    seen: dict[tuple, str] = {}
    for rec in records:
        if rec.row_kind != ROW_KIND_VALUE:
            continue
        # ลายเซ็นต้องรวม **ทุกมิติที่ใช้เทียบ** ให้ตรงกับ matching
        # G5 (#14) — matching 0.8.0 เพิ่ม period_label เข้าลายเซ็น
        signature = (rec.key, rec.fiscal_year, rec.budget_category,
                     rec.period_label)
        if signature in seen:
            assert seen[signature] == rec.cell_ref, (
                f"คีย์ซ้ำแต่ชี้คนละเซลล์: {seen[signature]} กับ {rec.cell_ref} "
                f"— normalize แรงเกินไปจนรวมคนละรายการเข้าด้วยกัน"
            )
        seen[signature] = rec.cell_ref


# ─────────────────────────────────────────── การ map ชีต 7.x (1 ก.ย. 2569)
@needs_sources
def test_7x_plan_sheets_now_yield_year_values(adapter):
    """ชีตแผนงาน ``7.x`` ต้องให้ค่ารายปีจริง ไม่ใช่ ``UNMAPPED`` อีกต่อไป"""
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    plan_values = [
        r for r in records
        if r.key.sheet_role == SECTION_ROLE_PLAN and r.row_kind == ROW_KIND_VALUE
    ]
    assert plan_values, "ชีตแผนงานต้องมี record ที่มีค่ารายปี"
    assert {r.fiscal_year for r in plan_values} >= {2568, 2569, 2570, 2571, 2572}
    assert all(r.key.section_title_norm for r in plan_values)


@needs_sources
def test_7x_plan_identity_comes_from_second_row_when_a1_is_chapter_heading(adapter):
    """🔴 ชีต ``Sheet7_1`` มี ``A1`` เป็นหัวบท ``7.`` แต่แผนจริงอยู่ ``A2``

    ถ้าไม่แก้ ชีตนี้จะได้บทบาท ``SECTION_07`` (หัวบท) แทนที่จะเป็นแผนงาน
    ⇒ ข้อมูลแผนบุคลากรภาครัฐจะไม่ถูกจับคู่กับแผนเดียวกันของอีกปี
    """
    sheets = adapter.inspect(SOURCE_DIR / FY69_AGENCY)["sheets"]
    sheet71 = next(s for s in sheets if s["name_actual"] == "Sheet7_1")

    assert sheet71["sheet_role"] == SECTION_ROLE_PLAN
    assert "บุคลากรภาครัฐ" in sheet71["section_title"]
    assert sheet71["plan_role"] == "PLAN_PERSONNEL"


@needs_sources
def test_7x_unit_column_is_not_hard_coded(adapter):
    """คอลัมน์หน่วยนับของ ``7.x`` คือ ``F`` ไม่ใช่ ``B`` ของบทบาท ``5.``"""
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    plan_money = [
        r for r in records
        if r.key.sheet_role == SECTION_ROLE_PLAN
        and r.row_kind == ROW_KIND_VALUE
        and r.declared_unit == UNIT_MILLION_BAHT
    ]
    assert plan_money
    # หน่วยมาจากเซลล์จริง ไม่ใช่การประกาศระดับชีต
    assert any(r.raw_unit_cell == UNIT_MILLION_BAHT for r in plan_money)


@needs_sources
def test_7x_rows_outside_year_tables_are_kept_as_unmapped(adapter):
    """แถวนอกตารางรายปี (เช่น ตารางจำแนกตามงบรายจ่าย) ต้องไม่หายเงียบ"""
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    outside = [
        r for r in records
        if "rows_outside_year_table_not_mapped" in r.uncertainty
    ]
    assert outside, "ต้องมี record ของแถวที่อยู่นอกตารางรายปี"
    assert all(r.row_kind == ROW_KIND_UNMAPPED for r in outside)
    assert all(r.needs_review for r in outside)
    assert all(r.value_decimal is None for r in outside)


@needs_sources
def test_7x_multi_table_sheet_reports_more_than_one_table(adapter):
    """ชีต ``7.x`` บางชีตมีตารางรายปีมากกว่าหนึ่งชุด — ต้องนับได้ครบ"""
    sheets = adapter.inspect(SOURCE_DIR / FY69_NVI)["sheets"]
    counts = {s["name_actual"]: s.get("year_table_count", 0) for s in sheets}
    assert any(v >= 1 for v in counts.values())
    # ชีตปกมีสองตารางรายปี
    assert counts.get("Sheet123", 0) >= 2


# ─────────────────────────── ตารางจำแนกตามงบรายจ่าย (1 ก.ย. 2569)
@needs_sources
def test_category_tables_produce_records_with_budget_category(adapter):
    """ตารางจำแนกตามงบรายจ่ายต้องให้ record พร้อม ``budget_category``"""
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    category = [r for r in records if r.budget_category]

    assert category, "ต้องมี record ของตารางจำแนกตามงบรายจ่าย"
    # canonical code ไม่ใช่ข้อความไทยดิบ (BO REVIEW)
    assert {r.budget_category for r in category} >= {
        "OPERATING", "INVESTMENT", "SUBSIDY", "OTHER_EXPENDITURE", "TOTAL"
    }
    # ข้อความหัวคอลัมน์ดิบต้องถูกเก็บไว้เป็น provenance เสมอ
    assert all(r.budget_category_raw for r in category)
    assert {str(r.budget_category_raw) for r in category} >= {"งบลงทุน", "รวม"}
    # record ของตารางนี้ไม่มีปี — ใช้หมวดงบรายจ่ายเป็นมิติแทน
    assert all(r.fiscal_year is None for r in category)
    assert all(r.row_kind == ROW_KIND_VALUE for r in category)
    assert all(r.cell_ref for r in category)


@needs_sources
def test_category_table_unlocks_section_06(adapter):
    """ชีตบทบาท ``6.`` ไม่มีตารางรายปี แต่มีตารางจำแนกตามงบรายจ่าย

    เดิมชีตนี้เป็น ``UNMAPPED`` ทั้งชีตเพราะหาป้ายปีไม่พบ
    """
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    section6 = [r for r in records if r.key.sheet_role == "SECTION_06"]

    assert section6
    valued = [r for r in section6 if r.row_kind == ROW_KIND_VALUE]
    assert valued, "บทบาท 6. ต้องมี record ที่มีค่าแล้ว"
    # G1 (#14) — แถวค่าเดี่ยวของบล็อก 6.1 (นอกตาราง) เป็นแกน SINGLE_AMOUNT
    assert all(r.budget_category or r.comparison_axis == "SINGLE_AMOUNT"
               for r in valued)
    assert any(r.budget_category for r in valued)


@needs_sources
def test_category_records_do_not_collide_with_year_records(adapter):
    """record ของสองตารางต้องไม่ชนกัน — มิติที่ใช้เทียบต่างกัน"""
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    seen: dict[tuple, str] = {}
    for rec in records:
        if rec.row_kind != ROW_KIND_VALUE:
            continue
        # G5 (#14) — matching 0.8.0 เพิ่ม period_label เข้าลายเซ็น
        signature = (rec.key, rec.fiscal_year, rec.budget_category,
                     rec.period_label)
        if signature in seen:
            assert seen[signature] == rec.cell_ref
        seen[signature] = rec.cell_ref


@needs_sources
def test_category_rows_in_sheet_71_are_not_mistaken_for_category_table(adapter):
    """🔴 ชีต ``7.1`` มีหมวดงบรายจ่ายเป็น **แถว** ไม่ใช่คอลัมน์

    (``- งบบุคลากร`` · ``- งบดำเนินงาน`` ฯลฯ เรียงลงมาในคอลัมน์ ``A``)
    ต้องไม่ถูกจับเป็นตารางจำแนกตามงบรายจ่าย
    """
    records = _records(adapter.extract(SOURCE_DIR / FY69_AGENCY))
    sheet71 = [r for r in records if r.sheet_name_actual == "Sheet7_1"]

    assert sheet71
    assert all(r.budget_category is None for r in sheet71)
    # และต้องยังเป็น record รายปีตามเดิม
    assert any(r.fiscal_year for r in sheet71 if r.row_kind == ROW_KIND_VALUE)


# ═══════ BO REVIEW — คอลัมน์หมวดที่ไม่รู้จักต้องไม่หายเงียบ (SYNTHETIC TEST FIXTURE)
def test_unknown_category_column_is_not_silently_dropped(tmp_path):
    """🔴 คอลัมน์หมวดงบรายจ่ายที่ระบบไม่รู้จักต้อง **ไม่หายเงียบ**

    **SYNTHETIC TEST FIXTURE** — สร้างแฟ้มจำลองที่มีหมวด ``งบชดใช้เงินคงคลัง``
    ซึ่งไม่อยู่ใน canonical set
    🔴 ห้ามรายงานผลจากชุดนี้ว่าเป็นข้อผิดพลาดที่พบใน workbook จริง

    ก่อนแก้: extractor iterate เฉพาะคอลัมน์ที่ resolve สำเร็จ ⇒ ค่าในคอลัมน์
    ที่ไม่รู้จัก **หายไปเงียบ ๆ โดยไม่มี HUMAN REVIEW**
    """
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet7_2"
    ws["A1"] = "7.2 แผนงานพื้นฐานทดสอบ"
    ws["A2"] = "5. เป้าหมายการให้บริการหน่วยงาน"      # ให้ระบุ document_level ได้
    ws["J3"] = "หน่วย : ล้านบาท"
    ws["A4"] = "กิจกรรม"
    ws["G4"], ws["H4"] = "งบดำเนินงาน", "งบลงทุน"
    ws["I4"], ws["J4"] = "งบชดใช้เงินคงคลัง", "รวม"     # ← หมวดที่ไม่รู้จัก
    ws["A5"] = "รวมทั้งสิ้น"
    ws["G5"], ws["H5"], ws["I5"], ws["J5"] = 1.0, 2.0, 99.0, 102.0
    path = tmp_path / "XL_FY2569_draft-bill_21011_TEST.xlsx"
    wb.save(path)
    wb.close()

    records = _records(AOWorkbookAdapter().extract(path))
    values = [r for r in records if r.row_kind == ROW_KIND_VALUE]

    # ค่าทั้งสี่คอลัมน์ต้องอยู่ครบ — รวมคอลัมน์ที่ไม่รู้จัก
    assert {float(r.value_decimal) for r in values} == {1.0, 2.0, 99.0, 102.0}

    unknown = [r for r in values if r.budget_category == "UNRESOLVED"]
    assert len(unknown) == 1
    assert float(unknown[0].value_decimal) == 99.0
    assert unknown[0].budget_category_raw == "งบชดใช้เงินคงคลัง"
    assert unknown[0].needs_review
    assert "budget_category_unresolved" in unknown[0].uncertainty
    # ต้องไม่เดาว่าเป็นหมวดที่ใกล้เคียง
    assert unknown[0].budget_category not in ("OPERATING", "INVESTMENT", "TOTAL")


def test_every_value_record_declares_a_valid_comparison_axis(tmp_path):
    """ทุก record ที่มีค่าในไฟล์จริงต้องมีแกนเทียบที่ถูกต้อง"""
    if not (SOURCE_DIR / FY69_AGENCY).exists():
        pytest.skip("ไม่พบคลังข้อมูล T1B")

    records = _records(AOWorkbookAdapter().extract(SOURCE_DIR / FY69_AGENCY))
    values = [r for r in records if r.row_kind == ROW_KIND_VALUE]

    assert values
    for rec in values:
        # G5 (#14) — แกนช่วงเวลาเพิ่มเข้ามา แยกจากปีเดี่ยว
        assert rec.comparison_axis in ("FISCAL_YEAR", "BUDGET_CATEGORY",
                                       "PERIOD_RANGE", "SINGLE_AMOUNT")
        assert rec.axis_valid, (
            f"แกนไม่ถูกต้อง: axis={rec.comparison_axis} "
            f"year={rec.fiscal_year} category={rec.budget_category}"
        )
