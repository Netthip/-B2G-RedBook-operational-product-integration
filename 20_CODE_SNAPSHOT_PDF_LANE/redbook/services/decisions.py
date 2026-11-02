# -*- coding: utf-8 -*-
"""คำตัดสินของมนุษย์ต่อข้อสังเกต T1B — **เพิ่มอย่างเดียว ไม่มีการเขียนทับ**

🔴 **คำตัดสินกิ๊ฟ (7 ก.ย. 2569)**

สี่สถานะ

============================  ==================================  =========
รหัสภายใน                      ข้อความบนหน้าจอ                      หมายเหตุ
============================  ==================================  =========
``CONFIRMED``                 ยืนยันว่าเป็นจุดที่ต้องแก้              ไม่บังคับ
``CONFIRMED_WITH_EDIT``       ยืนยันโดยแก้ไขข้อเสนอ                  **บังคับ**
``UNRESOLVED``                ยังตัดสินไม่ได้                        **บังคับ**
``DISMISSED``                 ไม่ใช่ประเด็นที่ต้องแก้                  **บังคับ**
============================  ==================================  =========

🔴 ชื่อ ``CONFIRMED_WITH_EDIT`` ถูกเลือกแทน ``CORRECTED`` โดยเจตนา —
คำว่า *corrected* ทำให้เข้าใจผิดว่าได้ไปแก้ข้อมูลใน e-Budgeting แล้ว
**ระบบนี้ไม่เคยแก้ e-Budgeting** ทุกหน้าจอและทุกไฟล์ส่งออกต้องบอกเรื่องนี้ตรง ๆ

🔴 สถานะปัจจุบันของ finding = คำตัดสิน **ล่าสุด** ของ finding นั้น
ไม่มีคอลัมน์เก็บสถานะปัจจุบันที่ไหน ⇒ ประวัติกับสถานะขัดกันเองไม่ได้

🔴 ``identity_basis == "position"`` — id ของใบนั้นคำนวณจากตำแหน่ง ไม่ใช่เนื้อหา
ตัดสินได้ในรอบปัจจุบัน แต่ติดธง ``not_rebindable`` และ
**ห้ามผูกคำตัดสินกลับอัตโนมัติในรอบใหม่** ต้องให้มนุษย์ยืนยันซ้ำเท่านั้น

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from . import categories
from .t1b import BASIS_POSITION

DECISION_SERVICE_VERSION = "t1b-decisions-0.2.0"

# ── สถานะ ──────────────────────────────────────────────────────────────────
PENDING = "PENDING"
CONFIRMED = "CONFIRMED"
CONFIRMED_WITH_EDIT = "CONFIRMED_WITH_EDIT"
UNRESOLVED = "UNRESOLVED"
DISMISSED = "DISMISSED"

#: สถานะที่ผู้ใช้เลือกได้ — ``PENDING`` เป็นสถานะตั้งต้น เลือกเองไม่ได้
DECIDABLE = (CONFIRMED, CONFIRMED_WITH_EDIT, UNRESOLVED, DISMISSED)

STATUS_LABELS = {
    PENDING: "ยังไม่ตัดสิน",
    CONFIRMED: "ยืนยันว่าเป็นจุดที่ต้องแก้",
    CONFIRMED_WITH_EDIT: "ยืนยันโดยแก้ไขข้อเสนอ",
    UNRESOLVED: "ยังตัดสินไม่ได้",
    DISMISSED: "ไม่ใช่ประเด็นที่ต้องแก้",
}

#: สถานะที่บังคับให้กรอกเหตุผล — ``CONFIRMED`` ไม่บังคับตามคำตัดสินกิ๊ฟ
NOTE_REQUIRED = frozenset({CONFIRMED_WITH_EDIT, UNRESOLVED, DISMISSED})

#: สถานะที่ออกไปอยู่ในไฟล์ส่งออก — อีกสองสถานะห้ามปนเข้าไปเด็ดขาด
EXPORTABLE = (CONFIRMED, CONFIRMED_WITH_EDIT)

#: ข้อความที่ต้องปรากฏทั้งบนหน้าจอและในไฟล์ส่งออก
E_BUDGETING_DISCLAIMER = (
    "การตัดสินในระบบนี้ยังไม่ได้แก้ไขข้อมูลใน e-Budgeting "
    "เป็นรายการสำหรับนำไปตรวจและแก้ไขด้วยผู้ปฏิบัติงานเอง"
)


class DecisionError(ValueError):
    """คำตัดสินไม่ผ่านกติกา — ข้อความพร้อมแสดงต่อผู้ใช้"""


class StaleDecisionError(DecisionError):
    """คำตัดสินค้าง — หน้าจอที่ส่งมาเห็นสถานะเก่ากว่าที่ฐานข้อมูลมีอยู่ (B.1)

    เกิดเมื่อเปิด finding เดียวกันสองแท็บ แล้วแท็บเก่ากดบันทึกหลังจากอีกแท็บ
    ตัดสินไปแล้ว · **ต้องปฏิเสธและให้โหลดสถานะล่าสุด** ห้ามสร้างคำตัดสินจาก
    ``status_from`` ที่ไม่ตรงกับแถวล่าสุด
    """

    def __init__(self, *, expected: int, actual: int):
        self.expected = expected
        self.actual = actual
        super().__init__(
            "มีคำตัดสินใหม่กว่าที่หน้าจอนี้เห็น — โปรดโหลดสถานะล่าสุดแล้วตัดสินอีกครั้ง "
            f"(หน้าจอเห็นลำดับ {expected} แต่ล่าสุดคือ {actual})")


class NoChangeDecision(DecisionError):
    """กดสถานะเดิมซ้ำโดยไม่มีข้อมูลเปลี่ยน — **ไม่สร้างแถวซ้ำ** (B.2)"""


@dataclass(frozen=True)
class DecisionView:
    """คำตัดสินหนึ่งครั้งในรูปที่หน้าเว็บใช้ได้ทันที"""

    seq: int
    id: str
    run_id: str
    finding_id: str
    identity_basis: str
    not_rebindable: bool
    status_from: str
    status_to: str
    engine_finding_type: str
    engine_baseline_value: str
    engine_current_value: str
    engine_difference: str
    subject_category: str
    category_confidence: str
    category_evidence: tuple[str, ...]
    corrected_field: str
    corrected_value: str
    note: str
    decided_at: str
    decided_by: str
    audit_seq: int | None
    audit_entry_hash: str

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status_to, self.status_to)

    @property
    def status_from_label(self) -> str:
        return STATUS_LABELS.get(self.status_from, self.status_from)

    @property
    def category_label(self) -> str:
        return categories.CATEGORY_LABELS.get(self.subject_category,
                                              self.subject_category)

    @property
    def confidence_label(self) -> str:
        return categories.CONFIDENCE_LABELS.get(self.category_confidence,
                                                self.category_confidence)

    @property
    def edited(self) -> bool:
        return self.status_to == CONFIRMED_WITH_EDIT

    @property
    def exportable(self) -> bool:
        return self.status_to in EXPORTABLE


def validate(status: str, *, note: str = "",
             corrected_value: str = "") -> tuple[str, str]:
    """ตรวจกติกาของคำตัดสินหนึ่งครั้ง คืน ``(note, corrected_value)`` ที่สะอาดแล้ว

    ยก :class:`DecisionError` พร้อมข้อความภาษาไทยที่แสดงต่อผู้ใช้ได้ทันที
    """
    if status not in DECIDABLE:
        raise DecisionError(
            f"สถานะคำตัดสินไม่ถูกต้อง — เลือกได้เฉพาะ {', '.join(DECIDABLE)}")

    note = (note or "").strip()
    corrected_value = (corrected_value or "").strip()

    if status in NOTE_REQUIRED and not note:
        raise DecisionError(
            f"สถานะ “{STATUS_LABELS[status]}” ต้องกรอกเหตุผลประกอบทุกครั้ง")

    if status == CONFIRMED_WITH_EDIT and not corrected_value:
        raise DecisionError(
            "สถานะ “ยืนยันโดยแก้ไขข้อเสนอ” ต้องระบุค่าที่แก้ไข "
            "มิฉะนั้นจะไม่ต่างจากการยืนยันตามที่ระบบเสนอ")

    if status != CONFIRMED_WITH_EDIT and corrected_value:
        # 🔴 กันการแก้ค่าแบบเงียบ ๆ — ค่าที่แก้ต้องมาคู่กับสถานะที่ประกาศว่าแก้
        raise DecisionError(
            "ระบุค่าที่แก้ไขได้เฉพาะเมื่อเลือกสถานะ “ยืนยันโดยแก้ไขข้อเสนอ”")

    return note[:2000], corrected_value[:500]


def current_status(decisions) -> str:
    """สถานะปัจจุบันจากประวัติ — **ล่าสุดชนะ** · ไม่มีประวัติ = ``PENDING``"""
    latest = None
    for d in decisions:
        if latest is None or d.seq > latest.seq:
            latest = d
    return PENDING if latest is None else latest.status_to


def _same_decision(latest, status: str, note: str,
                   corrected_field: str, corrected_value: str) -> bool:
    """สถานะเดิม ค่าเดิม ⇒ ไม่มีอะไรเปลี่ยน — เหตุผลว่างถือว่า "ไม่ได้เพิ่มข้อมูล" """
    if latest is None or latest.status_to != status:
        return False
    if (latest.corrected_field, latest.corrected_value) != (corrected_field, corrected_value):
        return False
    return not note or note == latest.note


def record(view, finding, status: str, *, expected_latest_seq: int,
           note: str = "", corrected_field: str = "", corrected_value: str = "",
           decided_by: str = "local-user", db_path=None) -> DecisionView:
    """บันทึกคำตัดสินหนึ่งครั้ง แล้วคืนแถวที่บันทึก

    ``view``    — :class:`~redbook.services.t1b.T1BRunView` ของรอบนั้น
    ``finding`` — ใบที่กำลังตัดสิน
    ``expected_latest_seq`` — ``seq`` ล่าสุดที่หน้าจอเห็นตอนโหลด (``0`` = ยังไม่เคย
    ตัดสิน) · ไม่ตรงกับฐานข้อมูล ⇒ :class:`StaleDecisionError`

    กติกาการเปลี่ยนสถานะ (กิ๊ฟ B.2)

    * เปลี่ยนจากสถานะที่ **เคยตัดสินแล้ว** ไปสถานะอื่น ⇒ **บังคับเหตุผล** เสมอ
      แม้ปลายทางจะเป็น ``CONFIRMED`` ซึ่งปกติไม่บังคับ
    * ค่าที่เครื่องยนต์เสนอ **คงเดิมทุกรุ่นของคำตัดสิน** — คัดลอกจากคำตัดสินแรก
      ไม่ใช่จาก finding ปัจจุบัน · ถ้าสองอย่างต่างกันแปลว่ารันใหม่ทับรอบเดิม
      ซึ่งต้องยกเป็นข้อผิดพลาด ไม่ใช่เขียนทับเงียบ ๆ
    * กดสถานะเดิมซ้ำโดยไม่มีข้อมูลเปลี่ยน ⇒ :class:`NoChangeDecision` ไม่สร้างแถว

    🔴 ค่าที่เครื่องยนต์เสนอถูก **คัดลอกมาตรึงไว้** ในแถวคำตัดสิน ไม่ใช่อ้างอิง
    ไปยังตาราง finding — เพราะถ้ารันใหม่แล้วค่าเปลี่ยน จะพิสูจน์ไม่ได้ว่า
    ตอนที่มนุษย์ตัดสิน เขาเห็นตัวเลขอะไรอยู่ตรงหน้า
    """
    from ..storage import t1b_decisions as repo

    note, corrected_value = validate(status, note=note,
                                     corrected_value=corrected_value)
    corrected_field = corrected_field.strip()[:80]
    if status == CONFIRMED_WITH_EDIT and not corrected_field:
        corrected_field = "current_value"
    if status != CONFIRMED_WITH_EDIT:
        corrected_field = ""

    history = repo.list_for_finding(view.summary.run_id, finding.finding_id,
                                    db_path=db_path)
    latest = history[-1] if history else None
    status_from = current_status(history)

    # 🔴 stale ต้องถูกรายงานเป็น stale — ตรวจก่อนกติกาอื่นทุกข้อ
    # (ภายในธุรกรรมของ repo.append ยังตรวจซ้ำอีกครั้งเพื่อกัน race จริง)
    if int(expected_latest_seq) != (latest.seq if latest else 0):
        raise StaleDecisionError(expected=int(expected_latest_seq),
                                 actual=latest.seq if latest else 0)

    if _same_decision(latest, status, note, corrected_field, corrected_value):
        raise NoChangeDecision(
            "คำตัดสินนี้เหมือนคำตัดสินล่าสุดทุกประการ — ไม่ได้บันทึกซ้ำ")

    if latest is not None and latest.status_to != status and not note:
        raise DecisionError(
            f"การเปลี่ยนจาก “{STATUS_LABELS[latest.status_to]}” เป็น "
            f"“{STATUS_LABELS[status]}” ต้องระบุเหตุผล เพราะเป็นการกลับคำตัดสินเดิม")

    # 🔴 ค่า engine ตรึงจากคำตัดสินแรก — ถ้า finding ปัจจุบันไม่ตรง แปลว่ารอบถูกรันทับ
    first = history[0] if history else None
    engine = {
        "engine_finding_type": finding.finding_type,
        "engine_baseline_value": finding.baseline_value,
        "engine_current_value": finding.current_value,
        "engine_difference": finding.difference,
    }
    if first is not None:
        frozen = {
            "engine_finding_type": first.engine_finding_type,
            "engine_baseline_value": first.engine_baseline_value,
            "engine_current_value": first.engine_current_value,
            "engine_difference": first.engine_difference,
        }
        if frozen != engine:
            raise DecisionError(
                "ค่าที่เครื่องยนต์เสนอสำหรับข้อสังเกตนี้ต่างจากตอนที่ตัดสินครั้งแรก "
                "— รอบนี้อาจถูกรันใหม่ทับ ต้องตรวจสอบก่อน ไม่บันทึกทับให้")
        engine = frozen

    subject = categories.classify_subject(finding)
    row = {
        "id": f"dec_{uuid.uuid4().hex[:16]}",
        "run_id": view.summary.run_id,
        "finding_id": finding.finding_id,
        "identity_basis": finding.identity_basis,
        "not_rebindable": int(finding.identity_basis == BASIS_POSITION),
        "status_from": status_from,
        "status_to": status,
        **engine,
        "subject_category": subject.category,
        "category_confidence": subject.confidence,
        "category_evidence": list(subject.evidence),
        "corrected_field": corrected_field,
        "corrected_value": corrected_value,
        "note": note,
        "decided_by": decided_by,
        "key_version": view.summary.key_version,
        "matching_version": view.summary.matching_version,
        "compare_version": view.summary.compare_version,
        "service_version": view.summary.service_version,
    }
    return repo.append(row, expected_latest_seq=expected_latest_seq,
                       db_path=db_path)


__all__ = [
    "DECISION_SERVICE_VERSION", "PENDING", "CONFIRMED", "CONFIRMED_WITH_EDIT",
    "UNRESOLVED", "DISMISSED", "DECIDABLE", "STATUS_LABELS", "NOTE_REQUIRED",
    "EXPORTABLE", "E_BUDGETING_DISCLAIMER", "DecisionError",
    "StaleDecisionError", "NoChangeDecision", "DecisionView",
    "validate", "current_status", "record",
]
