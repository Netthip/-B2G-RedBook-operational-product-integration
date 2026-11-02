# -*- coding: utf-8 -*-
"""สถานะผลตรวจ — แยก "สิ่งที่เครื่องบอกได้" ออกจาก "สิ่งที่มนุษย์ตัดสิน"

ข้อกำหนดหลักของระบบ: ห้ามสรุปว่า "ผิด" เพียงเพราะข้อมูลต่างกัน
โค้ดจึงบังคับให้สถานะที่เครื่องกำหนดเองได้ (MachineStatus) ไม่มีค่า "ผิด" อยู่เลย
ค่า "ยืนยันว่าผิด" อยู่ใน ReviewStatus ซึ่งตั้งได้จากการตัดสินของมนุษย์เท่านั้น
"""
from enum import Enum


class MachineStatus(str, Enum):
    """สถานะที่ระบบกำหนดได้เองจากการเปรียบเทียบ — ไม่มีค่าที่แปลว่า "ผิด" """

    MATCH = "match"                              # ตรงกัน
    DIFF_FOUND = "diff_found"                    # พบความแตกต่าง
    LIKELY_YEAR_CHANGE = "likely_year_change"    # คาดว่าเป็นการเปลี่ยนแปลงตามปี
    LIKELY_REDUCTION = "likely_reduction"        # คาดว่าเกี่ยวข้องกับการปรับลด
    NEEDS_HUMAN = "needs_human"                  # ต้องให้มนุษย์ตรวจสอบ


class ReviewStatus(str, Enum):
    """ผลการพิจารณาของมนุษย์ — ตั้งค่าได้จาก Human Review เท่านั้น"""

    PENDING = "pending"                              # ยังไม่พิจารณา
    CONFIRMED_ERROR = "confirmed_error"              # ยืนยันว่าเป็นข้อผิดพลาด
    CONFIRMED_VALID_CHANGE = "confirmed_valid_change"  # ยืนยันว่าเป็นการเปลี่ยนแปลงที่ถูกต้อง
    EXEMPTED = "exempted"                            # ยกเว้น (พร้อมเหตุผล)


TH_LABEL = {
    MachineStatus.MATCH: "ตรงกัน",
    MachineStatus.DIFF_FOUND: "พบความแตกต่าง",
    MachineStatus.LIKELY_YEAR_CHANGE: "คาดว่าเป็นการเปลี่ยนแปลงตามปี",
    MachineStatus.LIKELY_REDUCTION: "คาดว่าเกี่ยวข้องกับการปรับลด",
    MachineStatus.NEEDS_HUMAN: "ต้องให้มนุษย์ตรวจสอบ",
    ReviewStatus.PENDING: "รอพิจารณา",
    ReviewStatus.CONFIRMED_ERROR: "ยืนยันว่าเป็นข้อผิดพลาด",
    ReviewStatus.CONFIRMED_VALID_CHANGE: "ยืนยันว่าเป็นการเปลี่ยนแปลงที่ถูกต้อง",
    ReviewStatus.EXEMPTED: "ยกเว้นโดยผู้ตรวจ",
}

# สีสถานะตามข้อกำหนดหน้าจอ
COLOR_GREEN, COLOR_RED, COLOR_YELLOW, COLOR_BLUE, COLOR_GRAY = (
    "green", "red", "yellow", "blue", "gray")

_MACHINE_COLOR = {
    MachineStatus.MATCH: COLOR_GREEN,
    MachineStatus.DIFF_FOUND: COLOR_YELLOW,
    MachineStatus.LIKELY_YEAR_CHANGE: COLOR_BLUE,
    MachineStatus.LIKELY_REDUCTION: COLOR_BLUE,
    MachineStatus.NEEDS_HUMAN: COLOR_YELLOW,
}

_REVIEW_COLOR = {
    ReviewStatus.CONFIRMED_ERROR: COLOR_RED,
    ReviewStatus.CONFIRMED_VALID_CHANGE: COLOR_GREEN,
    ReviewStatus.EXEMPTED: COLOR_GRAY,
}


def effective_status(machine: MachineStatus, review: ReviewStatus):
    """สถานะที่ใช้แสดงผล: ถ้ามนุษย์ตัดสินแล้วให้ผลของมนุษย์มาก่อนเสมอ"""
    return machine if review == ReviewStatus.PENDING else review


def status_color(machine: MachineStatus, review: ReviewStatus,
                 presentation_only: bool = False) -> str:
    """สีสถานะ — เทาใช้กับ "ความต่างด้านการแสดงผลที่ไม่มีผลต่อค่า" เท่านั้น

    ถ้ามนุษย์ตัดสินแล้ว สีของผลการตัดสินมาก่อน presentation_only
    เพราะการยืนยันของมนุษย์คือข้อมูลที่หนักแน่นที่สุดในระบบ
    """
    if review != ReviewStatus.PENDING:
        return _REVIEW_COLOR[review]
    if presentation_only:
        return COLOR_GRAY
    return _MACHINE_COLOR[machine]


def th_label(status) -> str:
    return TH_LABEL.get(status, str(getattr(status, "value", status)))
