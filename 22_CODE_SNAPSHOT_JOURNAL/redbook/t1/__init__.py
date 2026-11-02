# -*- coding: utf-8 -*-
"""ชุดข้อมูลสาธารณะ T1 — ตัวเปรียบเทียบตามประตู G1–G5 ที่อนุมัติแล้ว 27 ส.ค. 2569

เวอร์ชันในไฟล์นี้ถูก **freeze** ตามคำตัดสิน P6 · การเปลี่ยนค่าใดค่าหนึ่ง
ต้องขึ้นเวอร์ชันใหม่ บันทึกใน DECISIONS_LOG.md และรันการทดลองใหม่ทั้งหมด
ผลของเวอร์ชันก่อนหน้าทำเครื่องหมาย superseded ไม่ลบทิ้ง
"""

# --- เวอร์ชันที่ freeze แล้ว (G1–G5) ---------------------------------------
CANONICAL_SCHEMA_VERSION = "cdm-t1-1.0.0"      # G1
SEMANTIC_MAPPING_VERSION = "semmap-t1-1.0.0"   # G2
COMPOSITE_KEY_VERSION = "key-t1-1.0.0"         # G3
RULE_SET_VERSION_T1 = "rules-t1-1.0.0"         # G4
# protocol-1.0.1: ปรับเฉพาะวิธีสุ่มตัวอย่างให้มนุษย์ตรวจ (สลับลำดับชั้นด้วย seed
#   และให้ครบทุกหมวดผลก่อน)
# protocol-1.0.2: ปรับเฉพาะ "เครื่องมือตรวจตำแหน่งหลักฐาน" ให้รับรู้ว่าเซลล์อาจจัดเก็บ
#   จำนวนเงินเป็นข้อความมีจุลภาค และรายงานแยกเป็น exact_numeric / text_equivalent
#   (รุ่น 1.0.1 นับกรณีข้อความว่าไม่ตรง ทำให้รายงาน 93.75% ทั้งที่ระบบอ่านถูกต้อง)
# ทั้งสองรุ่น **ไม่กระทบ engine กฎ ผลการจำแนก หรือ result_hash**
PROTOCOL_VERSION = "protocol-1.0.2"            # G5

# engine ของชั้น T1 โดยเฉพาะ (แยกจาก ENGINE_VERSION ของแกนกลาง)
T1_ENGINE_VERSION = "t1-engine-1.0.0"

FROZEN_AT = "2569-08-27"

# --- ค่าที่ผู้รับผิดชอบกำหนด (P1–P6) ---------------------------------------
SAMPLING_SEED = 20260827          # P2
SAMPLE_SIZE_FOR_HUMAN_CHECK = 40  # P3

# ถ้อยคำบังคับสำหรับเรียกผลการตรวจตัวอย่าง (P3) — ห้ามแก้
SAMPLE_CHECK_LABEL = (
    "ผลการตรวจสอบตัวอย่าง findings เพื่อประเมินความสอดคล้องของผลระบบกับหลักฐาน")

# ถ้อยคำบังคับสำหรับเรียกคู่เปรียบเทียบภายในปี 2569 (D3.1) — ห้ามแก้
EXPERIMENT_LABEL_FY2569 = (
    "คู่ร่างพระราชบัญญัติงบประมาณรายจ่ายกับพระราชบัญญัติงบประมาณรายจ่าย"
    "ประจำปีงบประมาณ พ.ศ. 2569")


def frozen_versions() -> dict:
    """ชุดเวอร์ชันที่ต้องบันทึกคู่กับผลการทดลองทุกครั้ง"""
    return {
        "t1_engine_version": T1_ENGINE_VERSION,
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "semantic_mapping_version": SEMANTIC_MAPPING_VERSION,
        "composite_key_version": COMPOSITE_KEY_VERSION,
        "rule_set_version": RULE_SET_VERSION_T1,
        "protocol_version": PROTOCOL_VERSION,
        "frozen_at": FROZEN_AT,
    }
