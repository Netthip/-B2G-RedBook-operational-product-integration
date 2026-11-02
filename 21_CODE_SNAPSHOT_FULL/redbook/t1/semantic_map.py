# -*- coding: utf-8 -*-
"""G2 (ส่วนที่ 2) — Semantic Mapping จาก Data Dict และการตรวจ schema conflict

กติกาที่บังคับด้วยโค้ด (ตาม D-2569-08-27-12 ข้อ D7 และคำตัดสิน P1):
  - canonical key **ห้ามผูกกับชื่อคอลัมน์กายภาพ** (`objc`, `objc_5`, `objc_8_name`)
    การ map ทำผ่านลำดับและนิยามใน Data Dict เท่านั้น
  - ชื่อคอลัมน์กายภาพไม่ตรงกับ Data Dict = `physical_name_drift` (ข้อสังเกต ไม่ใช่ข้อผิดพลาด)
  - นิยามใน Data Dict ของสองไฟล์ไม่ตรงกัน = **schema_conflict → หยุด**
    ไม่เริ่มเปรียบเทียบเนื้อหาระดับรายการ และไม่สร้างรายการใหม่/หาย/ยอดเปลี่ยนใด ๆ
"""
from dataclasses import dataclass, field, asdict

from . import SEMANTIC_MAPPING_VERSION
from .canonical import UNIT_CONFIRMED, UNIT_UNCONFIRMED

# ---------------------------------------------------------------------------
# แผนที่ "ชื่อฟิลด์ตาม Data Dict" → canonical field ของ G1
# ผูกกับชื่อฟิลด์ที่ Data Dict ประกาศ ไม่ใช่ชื่อคอลัมน์ในแถวหัวตาราง
# ---------------------------------------------------------------------------
DATADICT_TO_CANONICAL = {
    "min": "ministry_code",
    "min_name": "ministry_name",
    "agc": "agency_code",
    "agc_name": "agency_name",
    "group_budget": "budget_group",
    "plan_name": "plan_name",
    "output_name": "output_name",
    "act_name": "activity_name",
    "objc": "objective_category",
    "objc_8": "objective_subcategory",
    "cap_ncap": "capital_class",
    "item_name": "item_label",
    "p_total_bud": "amount_stored",
}

# หน่วยเงินที่ยืนยันแล้วสำหรับ T1 (D-2569-08-27-12 ข้อ D6)
AMOUNT_DECLARED_UNIT = "บาท"
AMOUNT_SCALE_FACTOR = 1.0


@dataclass
class ColumnMapping:
    """หลักฐานการ map หนึ่งคอลัมน์ — ครบตามที่ D7 กำหนดให้เก็บ"""

    source_column: str          # ชื่อคอลัมน์กายภาพ
    column_index: int           # ลำดับคอลัมน์ (0-based)
    datadict_field: str         # ชื่อฟิลด์ตาม Data Dict
    datadict_definition: str    # นิยามตาม Data Dict
    canonical_field: str        # canonical field ของ G1
    schema_fingerprint: str
    mapping_version: str = SEMANTIC_MAPPING_VERSION
    physical_name_drift: bool = False
    evidence: str = ""          # เช่น "Data Dict!A9 · data!I1"

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class SchemaConflict:
    """ความขัดแย้งเชิงความหมายระหว่างสอง schema — เหตุให้หยุด"""

    canonical_field: str
    datadict_field: str
    definition_a: str
    definition_b: str
    file_label_a: str
    file_label_b: str

    def as_dict(self) -> dict:
        return asdict(self)

    def reason(self) -> str:
        return (f"ฟิลด์ {self.datadict_field!r} มีนิยามใน Data Dict ต่างกันระหว่างสองไฟล์ — "
                f"{self.file_label_a}: {self.definition_a!r} · "
                f"{self.file_label_b}: {self.definition_b!r}")


@dataclass
class MappingResult:
    file_label: str
    columns: list = field(default_factory=list)         # list[ColumnMapping]
    unmapped_datadict_fields: list = field(default_factory=list)
    extra_physical_columns: list = field(default_factory=list)
    drifts: list = field(default_factory=list)          # ชื่อคอลัมน์ที่ไม่ตรง

    def canonical_to_index(self) -> dict:
        return {c.canonical_field: c.column_index for c in self.columns}

    def as_dict(self) -> dict:
        return {
            "file_label": self.file_label,
            "mapping_version": SEMANTIC_MAPPING_VERSION,
            "columns": [c.as_dict() for c in self.columns],
            "unmapped_datadict_fields": list(self.unmapped_datadict_fields),
            "extra_physical_columns": list(self.extra_physical_columns),
            "physical_name_drifts": list(self.drifts),
        }


def build_mapping(schema) -> MappingResult:
    """สร้าง semantic mapping ของไฟล์หนึ่งไฟล์จาก Data Dict + หัวตารางจริง

    จับคู่ตามลำดับ: ฟิลด์ลำดับที่ n ใน Data Dict คู่กับคอลัมน์ลำดับที่ n ในแถวหัว
    ถ้าชื่อไม่ตรงให้บันทึกเป็น physical_name_drift โดยยังคง map ต่อได้
    """
    result = MappingResult(file_label=schema.file_label)
    fp = schema.data_dict_fingerprint()
    physical = schema.physical_columns

    for i, fd in enumerate(schema.data_dict):
        canonical = DATADICT_TO_CANONICAL.get(fd.field_name)
        if canonical is None:
            result.unmapped_datadict_fields.append(fd.field_name)
            continue
        source = physical[i] if i < len(physical) else ""
        drift = source != fd.field_name
        if drift:
            result.drifts.append(
                f"ลำดับ {i + 1}: Data Dict = {fd.field_name!r} · หัวตาราง = {source!r}")
        result.columns.append(ColumnMapping(
            source_column=source,
            column_index=i,
            datadict_field=fd.field_name,
            datadict_definition=fd.definition,
            canonical_field=canonical,
            schema_fingerprint=fp,
            physical_name_drift=drift,
            evidence=f"Data Dict แถว {fd.ordinal + 1} · data คอลัมน์ลำดับ {i + 1}",
        ))

    n_dd = len(schema.data_dict)
    for j in range(n_dd, len(physical)):
        result.extra_physical_columns.append(
            f"คอลัมน์ลำดับ {j + 1}: {physical[j]!r} (ไม่มีใน Data Dict)")
    return result


def detect_schema_conflicts(schema_a, schema_b) -> list:
    """เทียบนิยามใน Data Dict ของสองไฟล์ — คืนรายการ SchemaConflict (ว่าง = ไม่ขัดแย้ง)

    เทียบเฉพาะฟิลด์ที่ map เข้า canonical ได้ทั้งสองฝั่ง
    """
    defs_a, defs_b = schema_a.definitions_by_name(), schema_b.definitions_by_name()
    conflicts = []
    for name, canonical in DATADICT_TO_CANONICAL.items():
        if name not in defs_a or name not in defs_b:
            continue
        if defs_a[name] != defs_b[name]:
            conflicts.append(SchemaConflict(
                canonical_field=canonical,
                datadict_field=name,
                definition_a=defs_a[name],
                definition_b=defs_b[name],
                file_label_a=schema_a.file_label,
                file_label_b=schema_b.file_label,
            ))
    return conflicts


def amount_unit_profile(mapping: MappingResult) -> dict:
    """โปรไฟล์หน่วยเงินของชั้น T1 ที่ผู้รับผิดชอบยืนยันแล้ว (D6)

    ยืนยันได้ก็ต่อเมื่อ map ฟิลด์ p_total_bud ได้จริงและมีนิยามใน Data Dict กำกับ
    มิฉะนั้นเป็น unconfirmed และจะไม่ถูกนำไปคำนวณ
    """
    col = next((c for c in mapping.columns
                if c.canonical_field == "amount_stored"), None)
    if col is None:
        return {"declared_unit": None, "scale_factor": None,
                "unit_confidence": UNIT_UNCONFIRMED,
                "evidence": "ไม่พบฟิลด์จำนวนเงินใน Data Dict"}
    return {
        "declared_unit": AMOUNT_DECLARED_UNIT,
        "scale_factor": AMOUNT_SCALE_FACTOR,
        "unit_confidence": UNIT_CONFIRMED,
        "evidence": (f"Data Dict: {col.datadict_field} = {col.datadict_definition!r} · "
                     f"ยืนยันหน่วยโดยผู้รับผิดชอบงานวิจัย (D-2569-08-27-12 ข้อ D6)"),
    }
