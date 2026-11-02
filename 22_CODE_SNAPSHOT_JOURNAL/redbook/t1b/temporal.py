# -*- coding: utf-8 -*-
"""T1B — บทบาทเชิงเวลาของยอดเงินในแถวค่าเดี่ยว (G1 + RC-E · #14)

ยอดเงินในเอกสารไม่ได้เป็น "ยอดของปีงบประมาณ" เสมอไป — แถว ``วงเงินทั้งสิ้น`` คือ
**วงเงินตลอดอายุโครงการ** และแถว ``ปี xxxx ผูกพันงบประมาณ`` คือ **ยอดผูกพันของปีนั้น**
ถ้านำไปรวมกับยอดรายปีจะนับซ้ำ (FC-NVI-01 · เซลล์ #11)

กติกาเดียวกับที่ชั้นบริการใช้อยู่แล้ว (``redbook/services/quarterly.py`` ·
ที่มา ``FORMATIVE_CASE_NVI`` §2.2) — ย้ายมาไว้ที่ชั้นเอนจินเพื่อติดไปกับ record ได้
🔴 ตัดสินจาก **ป้าย** เท่านั้น ไม่ใช้ชื่อชีต ตำแหน่ง หรือขนาดยอด
"""
from __future__ import annotations

import re

from .normalize import normalize_label, split_leading_number

ROLE_COMMITMENT_YEAR = "COMMITMENT_YEAR"
ROLE_LIFETIME_CEILING = "PROJECT_LIFETIME_CEILING"
ROLE_COMMITMENT_UNCLEAR = "COMMITMENT_UNCLEAR"
#: แถว ``ปี xxxx ตั้งงบประมาณ`` ในตารางย่อยของรายการผูกพัน (แผน §2.2 ``COMMITMENT_SCHEDULE``)
ROLE_COMMITMENT_SCHEDULE = "COMMITMENT_SCHEDULE"

#: ที่มาของบทบาท — จากป้ายของแถวเอง หรือสืบจากหัวข้อแม่ (แถว ``- …`` ใต้หัวข้อ)
ROLE_FROM_LABEL = "label"
ROLE_FROM_PARENT_HEADING = "parent_heading"

CEILING_PREFIX = "วงเงินทั้งสิ้น"
COMMITMENT_MARKER = "ผูกพัน"
SCHEDULE_MARKER = "ตั้งงบประมาณ"
_YEAR_ROW = re.compile(r"^ปี\s*(\d{4})")
_BULLET = re.compile(r"^[-–—•]\s*")


def classify_amount_role(raw_label: object) -> str:
    """บทบาทจากป้าย — คืน ``""`` เมื่อเป็นยอดทั่วไป

    >>> classify_amount_role("7.3.1.4 วงเงินทั้งสิ้นของโครงการ")
    'PROJECT_LIFETIME_CEILING'
    >>> classify_amount_role("ปี 2570 ผูกพันงบประมาณ")
    'COMMITMENT_YEAR'
    >>> classify_amount_role("ปี 2568 ตั้งงบประมาณ")
    'COMMITMENT_SCHEDULE'
    >>> classify_amount_role("งบประมาณรายจ่าย")
    ''
    """
    _number, rest = split_leading_number(normalize_label(raw_label))
    text = rest.strip()
    if not text:
        return ""
    if _YEAR_ROW.match(text) and COMMITMENT_MARKER in text:
        return ROLE_COMMITMENT_YEAR
    if _YEAR_ROW.match(text) and SCHEDULE_MARKER in text:
        return ROLE_COMMITMENT_SCHEDULE
    if text.startswith(CEILING_PREFIX):
        return ROLE_LIFETIME_CEILING
    if COMMITMENT_MARKER in text:
        return ROLE_COMMITMENT_UNCLEAR
    return ""


def is_bullet(raw_label: object) -> bool:
    """แถวย่อยแบบขีดนำหน้า เช่น ``- เงินงบประมาณ``"""
    return bool(_BULLET.match(normalize_label(raw_label)))
