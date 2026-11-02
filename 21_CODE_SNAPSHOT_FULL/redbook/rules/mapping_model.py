# -*- coding: utf-8 -*-
"""โครงสร้าง mapping ที่ผู้ใช้ยืนยัน (Mapping Profile) — ภาชนะ ไม่ใช่การเดา

ออกแบบตามข้อกำหนด Phase 2:
  - รองรับหลายหน่วยงาน หลายปีงบประมาณ หลายประเภทเอกสาร ด้วย "โปรไฟล์" หลายชุด
    ห้าม hard-code ชื่อชีต/แถว/คอลัมน์/หน่วย ในโค้ด — ทุกอย่างอยู่ในโปรไฟล์
    ที่ผู้ใช้ยืนยัน พร้อมหลักฐานอ้างอิง (evidence) ของแต่ละการตัดสินใจ
  - บันไดการจับคู่ (matching ladder) เป็นลำดับขั้นที่ผู้ใช้กำหนด
    ขั้นที่เป็นการเทียบชื่อแบบ normalize หรือ fuzzy ต้องเป็น suggest-only เสมอ
    และห้ามมีขั้นที่ใช้เลขแถวเป็นตัวระบุข้ามปี — validate() บังคับทั้งสองข้อ
  - threshold ร้อยละเป็นเพียงตัวช่วยจัดลำดับ/ระดับความสำคัญ ไม่ใช่เกณฑ์ถูกผิด
    และห้ามใช้ตัดผลต่างออกจากรายงาน — เก็บ policy นี้ไว้ในโปรไฟล์อย่างชัดแจ้ง

โปรไฟล์ที่ยังไม่ approved ใช้ตรวจจริงไม่ได้
"""
import json
from dataclasses import asdict, dataclass, field
from typing import Optional

from ..core.hashing import sha256_text

MAPPING_SCHEMA_VERSION = "mapping-schema-0.1.0"

# วิธีจับคู่ที่อนุญาต — เรียงตามความน่าเชื่อถือ
METHOD_OFFICIAL_CODE = "official_code"            # รหัสทางการตรงกันทั้งสองฝั่ง
METHOD_CODE_HIERARCHY = "code_plus_hierarchy"     # รหัส + สายลำดับชั้น/รหัสแม่
METHOD_CODE_NAME_CONTEXT = "code_plus_name_context"  # รหัส + ชื่อ + บริบทหมวด
METHOD_NORMALIZED_NAME = "normalized_name"        # ชื่อหลัง normalize (suggest-only)
METHOD_FUZZY_NAME = "fuzzy_name"                  # ความคล้ายชื่อ (suggest-only)

ALLOWED_METHODS = (METHOD_OFFICIAL_CODE, METHOD_CODE_HIERARCHY,
                   METHOD_CODE_NAME_CONTEXT, METHOD_NORMALIZED_NAME,
                   METHOD_FUZZY_NAME)
SUGGEST_ONLY_METHODS = {METHOD_NORMALIZED_NAME, METHOD_FUZZY_NAME}

# วิธีที่ห้ามเด็ดขาด — มีไว้เพื่อตรวจจับและปฏิเสธ
FORBIDDEN_METHODS = {"row_order", "row_number", "sequence_only"}

COLUMN_ROLES = ("item_code", "item_name", "item_sequence", "amount", "unit_count",
                "unit_price", "category", "plan", "output_or_project", "activity",
                "level", "pct_change", "note", "flag", "other")

SHEET_ROLES = ("source_detail", "summary", "investment", "allocation",
               "supporting_reference", "non_data_presentation")


@dataclass
class Evidence:
    """หลักฐานประกอบการตัดสินใจหนึ่งจุด — ต้องชี้ตำแหน่งจริงในเอกสารได้"""
    sheet: str = ""
    ref: str = ""            # เช่น "B4" หรือช่วง "B4:B5"
    description: str = ""


@dataclass
class ColumnMapping:
    column_letter: str
    role: str
    header_text: Optional[str] = None
    declared_unit: Optional[str] = None      # หน่วยตามที่เอกสารประกาศ เช่น "ล้านบาท"
    scale_to_baht: Optional[float] = None    # ตัวคูณแปลงเป็นบาท (ยืนยันแล้วเท่านั้น)
    decimals: Optional[int] = None
    evidence: list = field(default_factory=list)   # list[Evidence]
    notes: str = ""


@dataclass
class SheetMapping:
    sheet_name: str
    role: str
    header_rows: list = field(default_factory=list)
    data_start_row: Optional[int] = None
    data_end_row: Optional[int] = None
    total_rows: list = field(default_factory=list)
    hierarchy_rule: dict = field(default_factory=dict)  # {"type": ..., "params": {...}}
    columns: list = field(default_factory=list)          # list[ColumnMapping]
    evidence: list = field(default_factory=list)


@dataclass
class MatchingStep:
    """หนึ่งขั้นของบันไดการจับคู่ — ขั้นต้นก่อน ขั้นหลังใช้เมื่อขั้นก่อนไม่จับคู่"""
    priority: int
    method: str
    fields: list = field(default_factory=list)   # ฟิลด์ canonical ที่ใช้ในขั้นนี้
    suggest_only: bool = False                   # True = เสนอให้มนุษย์ยืนยันเท่านั้น
    min_confidence: Optional[float] = None
    notes: str = ""


@dataclass
class MappingProfile:
    """mapping หนึ่งชุดสำหรับ (หน่วยงาน, ประเภทเอกสาร, ช่วงปี) หนึ่งบริบท"""
    profile_id: str
    agency_label: str                 # ป้ายชื่อที่ผู้ใช้ตั้ง — ไม่ hard-code ในโค้ด
    doc_kind: str
    fiscal_years: list = field(default_factory=list)
    sheet_mappings: list = field(default_factory=list)   # list[SheetMapping]
    matching_ladder: list = field(default_factory=list)  # list[MatchingStep]
    tolerances: dict = field(default_factory=dict)       # {"amount_abs": ..., "basis": ...}
    thresholds: dict = field(default_factory=dict)
    schema_version: str = MAPPING_SCHEMA_VERSION
    approved_by: str = ""
    approved_at: str = ""
    notes: str = ""

    # ------------------------------------------------------------------
    def is_approved(self) -> bool:
        return bool(self.approved_by.strip() and self.approved_at.strip())

    def content_hash(self) -> str:
        """แฮชเนื้อหา mapping (ไม่รวมข้อมูลผู้อนุมัติ) — ใช้ระบุเวอร์ชัน mapping ใน run"""
        data = asdict(self)
        data.pop("approved_by", None)
        data.pop("approved_at", None)
        return sha256_text(json.dumps(data, ensure_ascii=False, sort_keys=True))

    def validate(self) -> list:
        """ตรวจว่าโปรไฟล์เคารพข้อห้ามของโครงการ — คืนรายการปัญหา (ว่าง = ผ่าน)"""
        problems = []
        if not self.sheet_mappings:
            problems.append("ต้องมี sheet mapping อย่างน้อย 1 ชีต")
        for sm in self.sheet_mappings:
            if sm.role not in SHEET_ROLES:
                problems.append(f"ชีต {sm.sheet_name}: role {sm.role!r} ไม่อยู่ในชุดที่กำหนด")
            for cm in sm.columns:
                if cm.role not in COLUMN_ROLES:
                    problems.append(
                        f"ชีต {sm.sheet_name} คอลัมน์ {cm.column_letter}: "
                        f"role {cm.role!r} ไม่อยู่ในชุดที่กำหนด")
                if cm.role == "amount" and cm.scale_to_baht is not None and not cm.evidence:
                    problems.append(
                        f"ชีต {sm.sheet_name} คอลัมน์ {cm.column_letter}: "
                        "กำหนด scale_to_baht โดยไม่มีหลักฐาน (evidence) ประกอบ")
        if not self.matching_ladder:
            problems.append("ต้องมีบันไดการจับคู่อย่างน้อย 1 ขั้น")
        seen_priority = set()
        for step in self.matching_ladder:
            if step.method in FORBIDDEN_METHODS:
                problems.append(
                    f"ขั้นที่ {step.priority}: ห้ามใช้ {step.method} — "
                    "เลขแถว/ลำดับอย่างเดียวใช้เป็นตัวระบุรายการข้ามปีไม่ได้")
                continue
            if step.method not in ALLOWED_METHODS:
                problems.append(f"ขั้นที่ {step.priority}: ไม่รู้จักวิธี {step.method!r}")
            if step.method in SUGGEST_ONLY_METHODS and not step.suggest_only:
                problems.append(
                    f"ขั้นที่ {step.priority} ({step.method}): "
                    "ต้องเป็น suggest_only — ระบบห้ามรวมรายการจากชื่ออัตโนมัติ")
            if step.priority in seen_priority:
                problems.append(f"priority {step.priority} ซ้ำกันในบันไดการจับคู่")
            seen_priority.add(step.priority)
        thr = self.thresholds.get("pct_highlight")
        if thr is not None and self.thresholds.get("role") != "highlight_only":
            problems.append(
                'thresholds ต้องระบุ role = "highlight_only" — '
                "ร้อยละเป็นตัวช่วยจัดลำดับเท่านั้น ห้ามใช้ตัดผลต่างออกจากรายงาน")
        return problems

    # ------------------------------------------------------------------
    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "MappingProfile":
        data = json.loads(text)
        data["sheet_mappings"] = [
            SheetMapping(**{**sm, "columns": [
                ColumnMapping(**{**cm, "evidence": [Evidence(**e) for e in
                                                    cm.get("evidence", [])]})
                for cm in sm.get("columns", [])],
                "evidence": [Evidence(**e) for e in sm.get("evidence", [])]})
            for sm in data.get("sheet_mappings", [])]
        data["matching_ladder"] = [MatchingStep(**st)
                                   for st in data.get("matching_ladder", [])]
        return cls(**data)
