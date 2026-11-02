# -*- coding: utf-8 -*-
"""Adapter boundary — ขอบเขตการอ่านเอกสารแยกตามชนิด

กติกาที่บังคับ (RES-D-24 · adapter boundary):
  - adapter แต่ละตัวรับผิดชอบ dataset kind เดียว
  - ทุก adapter ส่งออก **canonical envelope ร่วมกัน** แต่ schema ภายในและกฎ extraction
    **ต้องแยกตามประเภทเอกสาร**
  - ห้าม: Data Dict mapping ของ flat table ถูกใช้กับ Sheet5 ของ workbook ·
    anchor code ของ workbook ถูกใช้กับ flat table ·
    ตำแหน่งหน้า/บรรทัดของ PDF ถูกปลอมเป็นตำแหน่งเซลล์ Excel ·
    ผลจาก adapter หนึ่งถูกนับแทนอีก adapter

**สถานะ: skeleton — ยังไม่ implement การสกัดจริง**
การมี skeleton นี้ยังไม่ถือว่า Phase 2C เริ่มแล้ว
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ..datasets.kinds import DatasetKind


class LocationKind(str, Enum):
    """ชนิดของตำแหน่งหลักฐาน — ผูกกับชนิดเอกสาร ห้ามข้ามชนิด"""

    EXCEL_CELL = "excel_cell"       # ใช้ได้เฉพาะเอกสาร Excel
    EXCEL_ROW = "excel_row"         # ใช้ได้เฉพาะเอกสาร Excel
    PDF_PAGE_LINE = "pdf_page_line" # ใช้ได้เฉพาะเอกสาร PDF


class ExtractionStatus(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    UNCONFIRMED = "unconfirmed"
    BLOCKED_SCHEMA_CONFLICT = "blocked_schema_conflict"
    FAILED = "failed"


# ตำแหน่งหลักฐานที่อนุญาตต่อ dataset kind — บังคับด้วย validate_envelope()
ALLOWED_LOCATION_KINDS: dict[DatasetKind, set[LocationKind]] = {
    DatasetKind.OFFICIAL_FLAT_DATA_TABLE: {LocationKind.EXCEL_CELL, LocationKind.EXCEL_ROW},
    DatasetKind.OFFICIAL_AO_WORKBOOK: {LocationKind.EXCEL_CELL, LocationKind.EXCEL_ROW},
    DatasetKind.UNCONFIRMED_LOCAL_WORKBOOK: {LocationKind.EXCEL_CELL, LocationKind.EXCEL_ROW},
    DatasetKind.OFFICIAL_MINISTRY_PDF: {LocationKind.PDF_PAGE_LINE},
}


@dataclass(frozen=True)
class SourceLocation:
    """ตำแหน่งหลักฐานในเอกสารต้นทาง"""

    location_kind: LocationKind
    sheet: str | None = None        # Excel เท่านั้น
    cell: str | None = None         # Excel เท่านั้น
    row: int | None = None          # Excel เท่านั้น
    pdf_page_index: int | None = None   # PDF เท่านั้น
    printed_page: str | None = None     # PDF เท่านั้น
    line: int | None = None             # PDF เท่านั้น


@dataclass
class CanonicalEnvelope:
    """ผลลัพธ์ขั้นต่ำร่วมกันของทุก adapter

    ฟิลด์เหล่านี้เป็น **ส่วนที่ร่วมกันได้** เท่านั้น —
    โครงสร้างของ `canonical_record` ต่างกันตามชนิดเอกสาร และห้ามนำข้ามชนิด
    """

    source_file: Path
    source_hash: str
    dataset_kind: DatasetKind
    agency: str | None
    fiscal_year: int | None
    document_status: str | None      # draft_bill / revised_per_act / unknown
    canonical_record: Any            # โครงสร้างเฉพาะชนิด — ห้าม assume ข้ามชนิด
    source_location: SourceLocation
    declared_unit: str | None        # หน่วยเงินที่เอกสารประกาศ
    schema_version: str
    extraction_status: ExtractionStatus
    uncertainty: list[str] = field(default_factory=list)
    adapter_name: str = ""

    def __post_init__(self) -> None:
        validate_envelope(self)


def validate_envelope(env: CanonicalEnvelope) -> None:
    """บังคับว่าตำแหน่งหลักฐานตรงกับชนิดเอกสาร — กันการปลอมตำแหน่งข้ามชนิด"""
    allowed = ALLOWED_LOCATION_KINDS.get(env.dataset_kind)
    if allowed is None:
        return
    if env.source_location.location_kind not in allowed:
        raise ValueError(
            f"ตำแหน่งหลักฐานชนิด {env.source_location.location_kind.value} "
            f"ใช้กับ dataset kind {env.dataset_kind.value} ไม่ได้ "
            f"(อนุญาตเฉพาะ {sorted(k.value for k in allowed)})"
        )
    loc = env.source_location
    if loc.location_kind in (LocationKind.EXCEL_CELL, LocationKind.EXCEL_ROW):
        if loc.pdf_page_index is not None or loc.printed_page is not None:
            raise ValueError("ตำแหน่ง Excel ต้องไม่มีฟิลด์ของ PDF")
    if loc.location_kind is LocationKind.PDF_PAGE_LINE:
        if loc.sheet is not None or loc.cell is not None:
            raise ValueError("ตำแหน่ง PDF ต้องไม่มีฟิลด์ของ Excel")


class DocumentAdapter(ABC):
    """สัญญาร่วมของ adapter ทุกตัว

    แต่ละ subclass ผูกกับ dataset kind เดียว และต้องปฏิเสธไฟล์ของชนิดอื่น
    """

    #: dataset kind ที่ adapter นี้รับผิดชอบ — subclass ต้องกำหนด
    dataset_kind: DatasetKind
    #: เวอร์ชัน schema ภายในของ adapter นี้ — แยกกันคนละสาย
    schema_version: str = "unversioned"

    def accepts(self, kind: DatasetKind) -> bool:
        return kind is self.dataset_kind

    def require_kind(self, kind: DatasetKind) -> None:
        if not self.accepts(kind):
            raise ValueError(
                f"{type(self).__name__} รับเฉพาะ {self.dataset_kind.value} "
                f"แต่ได้รับ {kind.value} — ห้ามใช้ adapter ข้ามชนิดเอกสาร"
            )

    @abstractmethod
    def inspect(self, path: Path) -> dict[str, Any]:
        """สำรวจโครงสร้างไฟล์แบบอ่านอย่างเดียว (ยังไม่สกัดเนื้อหา)"""

    @abstractmethod
    def extract(self, path: Path) -> list[CanonicalEnvelope]:
        """สกัดเป็น canonical envelope — **ยังไม่ implement ในรอบนี้**"""
