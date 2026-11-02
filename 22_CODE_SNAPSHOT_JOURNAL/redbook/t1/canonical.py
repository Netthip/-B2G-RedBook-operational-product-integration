# -*- coding: utf-8 -*-
"""G1 — Canonical Schema ของชุดข้อมูล T1 (freeze: cdm-t1-1.0.0)

หลักการที่บังคับด้วยโค้ด:
  - ฟิลด์บังคับที่ว่าง → หยุดเป็น DataQualityHalt ไม่เดาค่าแทน
  - เก็บค่าเงินแยก 6 ค่าตามคำตัดสิน D-2569-08-27-09:
    stored · displayed · declared unit · scale factor · normalized · evidence location
  - row_ordinal เก็บไว้เป็นหลักฐานเท่านั้น **ห้ามใช้เป็น identity ข้ามไฟล์**
    (บังคับด้วยการที่ composite_key() ไม่แตะฟิลด์นี้ และมีชุดทดสอบกำกับ)
"""
from dataclasses import dataclass, field, asdict
from typing import Optional

from . import CANONICAL_SCHEMA_VERSION

# ฟิลด์เชิงความหมาย 12 ฟิลด์ตามลำดับชั้นของเอกสารงบประมาณ
HIERARCHY_FIELDS = (
    "ministry_code", "ministry_name",
    "agency_code", "agency_name",
    "budget_group", "plan_name", "output_name", "activity_name",
    "objective_category", "objective_subcategory",
    "capital_class", "item_label",
)

# ฟิลด์ที่ห้ามว่าง — ว่างเมื่อใดต้องหยุด ไม่เดา
REQUIRED_FIELDS = (
    "ministry_code", "agency_code", "budget_group", "plan_name",
    "output_name", "activity_name", "objective_category",
    "objective_subcategory", "capital_class", "item_label",
    "amount_stored",
)

UNIT_CONFIRMED = "confirmed"
UNIT_UNCONFIRMED = "unconfirmed"


class DataQualityHalt(Exception):
    """ข้อมูลไม่ครบตามที่ schema บังคับ — ระบบหยุด ไม่เดาค่าให้"""

    def __init__(self, message: str, location: dict = None):
        super().__init__(message)
        self.message = message
        self.location = location or {}


@dataclass(frozen=True)
class EvidenceLocation:
    """ตำแหน่งต้นทางของหนึ่งเรคอร์ด — ต้องเปิดไฟล์กลับไปตรวจได้จริง"""

    file_label: str = ""      # เช่น "T1-01"
    file_name: str = ""
    sha256: str = ""
    sheet_name: str = "data"
    row_number: int = 0       # เลขแถวจริงในชีต (แถวหัว = 1)
    amount_cell: str = ""     # เช่น "M1234"

    def as_dict(self) -> dict:
        return asdict(self)

    def label(self) -> str:
        return f"{self.file_label} · {self.sheet_name}!{self.amount_cell}"


@dataclass
class CanonicalT1Record:
    """หนึ่งแถวข้อมูลงบประมาณในรูปแบบกลางของชั้น T1"""

    # --- ลำดับชั้น ---
    ministry_code: Optional[str] = None
    ministry_name: Optional[str] = None
    agency_code: Optional[str] = None
    agency_name: Optional[str] = None
    budget_group: Optional[str] = None
    plan_name: Optional[str] = None
    output_name: Optional[str] = None
    activity_name: Optional[str] = None
    objective_category: Optional[str] = None
    objective_subcategory: Optional[str] = None
    capital_class: Optional[str] = None
    item_label: Optional[str] = None

    # --- จำนวนเงิน (เก็บแยก 6 ค่าตาม D-2569-08-27-09) ---
    amount_stored: Optional[int] = None
    amount_displayed: Optional[str] = None
    declared_unit: Optional[str] = None
    scale_factor: Optional[float] = None
    amount_normalized: Optional[int] = None
    unit_confidence: str = UNIT_UNCONFIRMED

    # --- หลักฐานและลำดับ ---
    evidence_location: Optional[EvidenceLocation] = None
    row_ordinal: Optional[int] = None   # หลักฐานเท่านั้น ห้ามใช้เป็น identity

    # --- เวอร์ชัน ---
    schema_version: str = CANONICAL_SCHEMA_VERSION

    # --- ค่าดิบตามที่ปรากฏจริงก่อน normalize ---
    raw_values: dict = field(default_factory=dict)

    def validate(self) -> None:
        """ตรวจฟิลด์บังคับ — ว่างเมื่อใดโยน DataQualityHalt ทันที"""
        for name in REQUIRED_FIELDS:
            value = getattr(self, name)
            if value is None or (isinstance(value, str) and not value.strip()):
                loc = self.evidence_location.as_dict() if self.evidence_location else {}
                raise DataQualityHalt(
                    f"ฟิลด์บังคับ {name!r} ว่างหรือไม่มีค่า — ระบบหยุดและไม่เดาค่าแทน", loc)
        if self.unit_confidence == UNIT_CONFIRMED and self.scale_factor is None:
            raise DataQualityHalt(
                "unit_confidence = confirmed แต่ไม่มี scale_factor — ขัดกับ D-2569-08-27-09")

    def hierarchy_path(self) -> tuple:
        """สายลำดับชั้นเหนือระดับรายการ (ใช้ตรวจการย้าย parent)"""
        return (self.agency_code, self.budget_group, self.plan_name,
                self.output_name, self.activity_name,
                self.objective_category, self.objective_subcategory,
                self.capital_class)

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.evidence_location is not None:
            d["evidence_location"] = self.evidence_location.as_dict()
        return d
