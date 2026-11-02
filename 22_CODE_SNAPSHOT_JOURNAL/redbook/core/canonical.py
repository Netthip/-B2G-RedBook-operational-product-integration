# -*- coding: utf-8 -*-
"""Canonical Data Model — โครงสร้างกลางที่ Excel และ PDF แปลงเข้ามาเหมือนกัน

กติกาสำคัญ 2 ข้อที่บังคับด้วยโค้ด:
  1. ห้ามเดา — ฟิลด์ที่เอกสารไม่มี ต้องเป็น None และต้องมีเหตุผลกำกับใน `nulls`
     (ใช้ `set_null()` เท่านั้น จะไม่มีทางลืมเหตุผล)
  2. ทุกค่าที่ดึงมาได้ต้องมีตำแหน่งต้นทาง (SourceLocation) ติดมาด้วยเสมอ
"""
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

# เหตุผลมาตรฐานที่ใช้อธิบายว่าทำไมฟิลด์เป็น null
NULL_NOT_IN_DOCUMENT = "ไม่มีข้อมูลนี้ในเอกสารต้นฉบับ"
NULL_NOT_MAPPED = "ยังไม่มี mapping ที่ผู้ใช้อนุมัติสำหรับฟิลด์นี้"
NULL_UNREADABLE = "อ่านค่าไม่ได้จากตำแหน่งที่ระบุ"
NULL_AMBIGUOUS = "พบมากกว่าหนึ่งค่าที่เป็นไปได้ ระบบไม่เลือกให้"
NULL_NOT_APPLICABLE = "ไม่ใช้กับเอกสารประเภทนี้"


@dataclass
class SourceLocation:
    """ตำแหน่งต้นทางของค่าหนึ่งค่า — ใช้ทำ Evidence View ย้อนกลับ"""

    source_file: str = ""            # ชื่อไฟล์ที่ผู้ใช้อัปโหลด (ชื่อที่ผู้ใช้เห็น)
    source_file_id: str = ""         # id ภายในระบบ (ผูกกับ SHA-256)
    source_type: str = ""            # "xlsx" | "pdf"
    sheet_name: Optional[str] = None
    cell_reference: Optional[str] = None   # เช่น "F12"
    row_number: Optional[int] = None
    column_letter: Optional[str] = None
    page_number: Optional[int] = None
    table_number: Optional[int] = None
    line_number: Optional[int] = None
    bounding_box: Optional[tuple] = None   # (x0, y0, x1, y1) หน่วยตาม PDF point
    extraction_method: str = ""            # "openpyxl_cached" | "pdf_text_layer" | "ocr" ...
    extraction_confidence: Optional[float] = None  # None = ไม่ใช่ค่าประมาณ (อ่านตรง)

    def label(self) -> str:
        """ข้อความสั้นสำหรับแสดงในตารางผลตรวจ"""
        if self.source_type == "xlsx":
            parts = [self.sheet_name or "-", self.cell_reference or "-"]
            return " / ".join(str(p) for p in parts)
        if self.source_type == "pdf":
            parts = []
            if self.page_number is not None:
                parts.append(f"หน้า {self.page_number}")
            if self.table_number is not None:
                parts.append(f"ตาราง {self.table_number}")
            if self.line_number is not None:
                parts.append(f"บรรทัด {self.line_number}")
            return " / ".join(parts) if parts else "-"
        return "-"


@dataclass
class CanonicalItem:
    """หนึ่งรายการงบประมาณในรูปแบบกลาง

    ทุกฟิลด์เชิงความหมายเป็น Optional โดยตั้งใจ — เอกสารจริงไม่ได้มีครบทุกช่อง
    และระบบต้องไม่เติมค่าแทนผู้ใช้
    """

    # ตัวระบุเอกสาร
    document_id: str = ""
    document_version: Optional[str] = None
    fiscal_year: Optional[int] = None

    # โครงสร้างงบประมาณ
    agency_code: Optional[str] = None
    agency_name: Optional[str] = None
    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    output_or_project_code: Optional[str] = None
    output_or_project_name: Optional[str] = None
    category_code: Optional[str] = None
    category_name: Optional[str] = None

    # ตัวรายการ
    item_code: Optional[str] = None
    item_sequence: Optional[int] = None
    item_name: Optional[str] = None
    amount: Optional[float] = None
    unit: Optional[str] = None

    # ตำแหน่งต้นทางของทั้งรายการ และของรายฟิลด์ (ถ้าต่างกัน)
    location: SourceLocation = field(default_factory=SourceLocation)
    field_locations: dict = field(default_factory=dict)   # field_name -> SourceLocation

    # ค่าดิบตามที่ปรากฏในเอกสาร (ก่อน normalize) — ใช้เทียบ "รูปแบบ" แยกจาก "ค่า"
    raw_values: dict = field(default_factory=dict)        # field_name -> str ตามที่เห็น

    # เหตุผลที่ฟิลด์เป็น null
    nulls: dict = field(default_factory=dict)             # field_name -> reason

    # เวอร์ชันที่ใช้สกัดข้อมูลรายการนี้
    extraction_method: str = ""
    extraction_confidence: Optional[float] = None
    rule_version: Optional[str] = None

    def set_null(self, field_name: str, reason: str) -> None:
        """ตั้งฟิลด์เป็น null พร้อมเหตุผล — ทางเดียวที่ควรใช้ตั้งค่าว่าง"""
        if not hasattr(self, field_name):
            raise KeyError(f"ไม่มีฟิลด์ {field_name!r} ใน CanonicalItem")
        if not reason:
            raise ValueError("ต้องระบุเหตุผลที่ฟิลด์เป็น null")
        setattr(self, field_name, None)
        self.nulls[field_name] = reason

    def null_reason(self, field_name: str) -> Optional[str]:
        return self.nulls.get(field_name)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CanonicalDocument:
    """เอกสารหนึ่งฉบับหลังแปลงเข้าโครงสร้างกลาง"""

    document_id: str = ""
    source_file_id: str = ""
    source_file_name: str = ""
    source_type: str = ""
    sha256: str = ""
    fiscal_year: Optional[int] = None
    agency_code: Optional[str] = None
    agency_name: Optional[str] = None
    document_kind: Optional[str] = None       # เช่น "ป.1", "คาดแดง" — ผู้ใช้เป็นผู้ระบุ
    items: list = field(default_factory=list)  # list[CanonicalItem]
    nulls: dict = field(default_factory=dict)
    extraction_method: str = ""
    warnings: list = field(default_factory=list)

    def set_null(self, field_name: str, reason: str) -> None:
        if not hasattr(self, field_name):
            raise KeyError(f"ไม่มีฟิลด์ {field_name!r} ใน CanonicalDocument")
        if not reason:
            raise ValueError("ต้องระบุเหตุผลที่ฟิลด์เป็น null")
        setattr(self, field_name, None)
        self.nulls[field_name] = reason
