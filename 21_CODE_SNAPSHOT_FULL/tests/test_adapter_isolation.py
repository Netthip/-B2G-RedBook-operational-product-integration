# -*- coding: utf-8 -*-
"""ทดสอบว่า adapter และ schema ของแต่ละชนิดเอกสารไม่ปนกัน

บังคับข้อห้ามตาม adapter boundary:
  - T1A Data Dict mapping ห้ามถูกใช้กับ Sheet5 ของ AO workbook
  - anchor code ของ AO workbook ห้ามถูกใช้กับ flat Data Table
  - ตำแหน่งหน้า/บรรทัดของ PDF ห้ามถูกปลอมเป็นตำแหน่งเซลล์ Excel
  - ผลจาก adapter หนึ่งห้ามถูกนับแทนอีก adapter
"""
from pathlib import Path

import pytest

from redbook.adapters import (
    AOWorkbookAdapter,
    CanonicalEnvelope,
    ExtractionStatus,
    FlatDataTableAdapter,
    LocationKind,
    MinistryPdfAdapter,
    SourceLocation,
)
from redbook.datasets import DatasetKind, SPECS, adapter_for, kinds_for_tier


def _envelope(kind: DatasetKind, loc: SourceLocation) -> CanonicalEnvelope:
    return CanonicalEnvelope(
        source_file=Path("dummy.xlsx"),
        source_hash="0" * 64,
        dataset_kind=kind,
        agency="21011",
        fiscal_year=2569,
        document_status="draft_bill",
        canonical_record={},
        source_location=loc,
        declared_unit="บาท",
        schema_version="test",
        extraction_status=ExtractionStatus.OK,
    )


# ---------- adapter รับเฉพาะชนิดของตัวเอง ----------

def test_flat_adapter_rejects_other_kinds():
    a = FlatDataTableAdapter()
    assert a.accepts(DatasetKind.OFFICIAL_FLAT_DATA_TABLE)
    for other in (DatasetKind.OFFICIAL_AO_WORKBOOK, DatasetKind.OFFICIAL_MINISTRY_PDF):
        assert not a.accepts(other)
        with pytest.raises(ValueError, match="ห้ามใช้ adapter ข้ามชนิดเอกสาร"):
            a.require_kind(other)


def test_pdf_adapter_rejects_excel_kinds():
    a = MinistryPdfAdapter()
    for other in (DatasetKind.OFFICIAL_FLAT_DATA_TABLE, DatasetKind.OFFICIAL_AO_WORKBOOK):
        assert not a.accepts(other)
        with pytest.raises(ValueError):
            a.require_kind(other)


def test_ao_adapter_rejects_flat_table():
    """AO adapter รับไฟล์ภายในได้ แต่ต้องไม่รับ flat data table"""
    a = AOWorkbookAdapter()
    assert a.accepts(DatasetKind.OFFICIAL_AO_WORKBOOK)
    assert a.accepts(DatasetKind.UNCONFIRMED_LOCAL_WORKBOOK)
    assert not a.accepts(DatasetKind.OFFICIAL_FLAT_DATA_TABLE)


# ---------- ตำแหน่งหลักฐานห้ามข้ามชนิด ----------

def test_pdf_location_cannot_be_used_for_excel_dataset():
    loc = SourceLocation(location_kind=LocationKind.PDF_PAGE_LINE, pdf_page_index=567, line=3)
    with pytest.raises(ValueError, match="ใช้กับ dataset kind"):
        _envelope(DatasetKind.OFFICIAL_FLAT_DATA_TABLE, loc)


def test_excel_location_cannot_be_used_for_pdf_dataset():
    loc = SourceLocation(location_kind=LocationKind.EXCEL_CELL, sheet="Sheet5", cell="C6")
    with pytest.raises(ValueError, match="ใช้กับ dataset kind"):
        _envelope(DatasetKind.OFFICIAL_MINISTRY_PDF, loc)


def test_excel_location_must_not_carry_pdf_fields():
    loc = SourceLocation(
        location_kind=LocationKind.EXCEL_CELL, sheet="data", cell="A2", pdf_page_index=10
    )
    with pytest.raises(ValueError, match="ต้องไม่มีฟิลด์ของ PDF"):
        _envelope(DatasetKind.OFFICIAL_FLAT_DATA_TABLE, loc)


def test_pdf_location_must_not_carry_excel_fields():
    loc = SourceLocation(
        location_kind=LocationKind.PDF_PAGE_LINE, pdf_page_index=595, sheet="Sheet5"
    )
    with pytest.raises(ValueError, match="ต้องไม่มีฟิลด์ของ Excel"):
        _envelope(DatasetKind.OFFICIAL_MINISTRY_PDF, loc)


def test_valid_locations_pass():
    excel = SourceLocation(location_kind=LocationKind.EXCEL_CELL, sheet="data", cell="A2")
    assert _envelope(DatasetKind.OFFICIAL_FLAT_DATA_TABLE, excel)
    pdf = SourceLocation(
        location_kind=LocationKind.PDF_PAGE_LINE, pdf_page_index=595, printed_page="581"
    )
    assert _envelope(DatasetKind.OFFICIAL_MINISTRY_PDF, pdf)


# ---------- schema version ต้องแยกกันคนละ adapter ----------

def test_adapters_have_distinct_schema_versions():
    versions = {
        FlatDataTableAdapter.schema_version,
        AOWorkbookAdapter.schema_version,
        MinistryPdfAdapter.schema_version,
    }
    assert len(versions) == 3, "schema version ของแต่ละ adapter ต้องไม่ซ้ำกัน"


def test_flat_adapter_knows_only_its_own_sheets():
    """ชื่อชีตของ flat table ต้องไม่ปนกับชื่อชีตของ AO workbook"""
    assert FlatDataTableAdapter.known_sheets == ("Data Dict", "data")
    assert not any(
        s.lower().startswith("sheet") for s in FlatDataTableAdapter.known_sheets
    ), "flat adapter ต้องไม่รู้จักชีตแบบ Sheet5 ของ AO workbook"


def test_ao_adapter_has_no_data_dict_concept():
    """AO adapter ต้องไม่มีแนวคิด Data Dict ของ flat table

    **ปรับเมื่อ 1 ก.ย. 2569** — เดิมตรวจว่ามี ``supporting_sheet_prefixes``
    ซึ่งภายหลังพบว่าเป็น **defect**: การจำแนกด้วย prefix ``("b","B")``
    จับชีต ``บุค`` (บ ภาษาไทย · 837 แถว) ไม่ได้ และปล่อยให้ไหลเข้าผลหลักทั้งก้อน
    คำสั่ง Gift ข้อ 3 (1 ก.ย. 2569) ห้ามใช้วิธีนี้เป็น logic หลักของ T1B ใหม่
    จึงเปลี่ยนมาตรวจว่า adapter ผูกกับชั้น T1B ผ่าน ``schema_version`` แทน
    (ไฟล์นี้ไม่อยู่ใน tag ``t1-frozen-1.0.0`` — เพิ่มหลัง freeze)
    """
    assert not hasattr(AOWorkbookAdapter, "known_sheets")
    # ต้องไม่กลับไปใช้การจำแนกด้วย prefix ตัวอักษรอีก
    assert not hasattr(AOWorkbookAdapter, "supporting_sheet_prefixes")
    # แต่ต้องยังผูกกับ schema ของชั้น T1B ของตนเอง
    assert "ao-workbook-schema" in AOWorkbookAdapter.schema_version
    assert "t1b-structural" in AOWorkbookAdapter.schema_version


def test_flat_adapter_has_no_anchor_concept():
    """flat adapter ต้องไม่มีแนวคิด anchor code ของ AO workbook"""
    assert not hasattr(FlatDataTableAdapter, "supporting_sheet_prefixes")


# ---------- crosswalk รหัสวิจัย ↔ dataset kind ----------

def test_research_tier_crosswalk_is_consistent():
    assert kinds_for_tier("T1A") == [DatasetKind.OFFICIAL_FLAT_DATA_TABLE]
    assert set(kinds_for_tier("T1B")) == {
        DatasetKind.OFFICIAL_AO_WORKBOOK,
        DatasetKind.OFFICIAL_MINISTRY_PDF,
    }
    assert kinds_for_tier("T2") == [DatasetKind.UNCONFIRMED_LOCAL_WORKBOOK]


def test_t1a_and_t1b_are_never_the_same_kind():
    t1a = set(kinds_for_tier("T1A"))
    t1b = set(kinds_for_tier("T1B"))
    assert t1a.isdisjoint(t1b), "T1A และ T1B ต้องไม่ใช้ dataset kind ร่วมกัน"


def test_unconfirmed_and_archive_not_usable_in_primary_results():
    assert not SPECS[DatasetKind.UNCONFIRMED_LOCAL_WORKBOOK].usable_in_primary_results
    assert not SPECS[DatasetKind.ARCHIVED_PRIOR_ARTIFACT].usable_in_primary_results


def test_every_official_kind_has_a_dedicated_adapter():
    for kind in (
        DatasetKind.OFFICIAL_FLAT_DATA_TABLE,
        DatasetKind.OFFICIAL_AO_WORKBOOK,
        DatasetKind.OFFICIAL_MINISTRY_PDF,
    ):
        assert adapter_for(kind), f"{kind.value} ต้องผูกกับ adapter"


def test_flat_and_ao_use_different_adapters():
    assert adapter_for(DatasetKind.OFFICIAL_FLAT_DATA_TABLE) != adapter_for(
        DatasetKind.OFFICIAL_AO_WORKBOOK
    )


# ---------- ยังไม่ implement การสกัด ----------

@pytest.mark.parametrize(
    "adapter", [FlatDataTableAdapter(), MinistryPdfAdapter()]
)
def test_extraction_not_implemented_yet(adapter):
    """skeleton เท่านั้น — การมี adapter ยังไม่ถือว่า Phase 2C เริ่มแล้ว

    **ปรับเมื่อ 1 ก.ย. 2569** — เอา ``AOWorkbookAdapter`` ออกจากรายการ
    เพราะ ``extract()`` ของชั้น T1B implement แล้วตามคำสั่ง Gift ข้อ A
    ส่วน ``FlatDataTableAdapter`` (T1A ที่ freeze) และ ``MinistryPdfAdapter``
    (Phase 3 ที่ยัง blocked) **ต้องยังไม่ implement** — เป็นการยืนยันขอบเขต
    (ไฟล์นี้ไม่อยู่ใน tag ``t1-frozen-1.0.0`` — เพิ่มหลัง freeze)
    """
    with pytest.raises(NotImplementedError):
        adapter.extract(Path("dummy"))


def test_ao_extract_is_implemented_but_others_are_not():
    """ยืนยันขอบเขต: implement เฉพาะ T1B — ไม่แตะ T1A และ Phase 3"""
    from redbook.adapters.base import DocumentAdapter

    assert AOWorkbookAdapter.extract is not DocumentAdapter.extract
    with pytest.raises(NotImplementedError):
        FlatDataTableAdapter().extract(Path("dummy"))
    with pytest.raises(NotImplementedError):
        MinistryPdfAdapter().extract(Path("dummy"))
