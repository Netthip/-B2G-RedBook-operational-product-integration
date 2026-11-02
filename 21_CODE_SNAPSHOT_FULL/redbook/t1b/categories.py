# -*- coding: utf-8 -*-
"""T1B — หมวดงบรายจ่ายแบบ canonical

🔴 **ต้องใช้ canonical code ไม่ใช่ข้อความไทยดิบ** (BO REVIEW · 1 กันยายน 2569)
ข้อความไทยดิบเปลี่ยนได้ตามการสะกดของแต่ละแฟ้ม จึงเก็บไว้เป็น
``budget_category_raw`` (provenance) และใช้ canonical code เป็นตัวเทียบ

🔴 **หมวดที่ resolve ไม่ได้ ต้องเป็น ``UNRESOLVED`` และเข้าคิวมนุษย์**
ห้ามเดาว่าเป็นหมวดที่ใกล้เคียงที่สุด และ **ห้ามข้ามคอลัมน์นั้นเงียบ ๆ**

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

from .normalize import normalize_label

CATEGORY_PERSONNEL = "PERSONNEL"
CATEGORY_OPERATING = "OPERATING"
CATEGORY_INVESTMENT = "INVESTMENT"
CATEGORY_SUBSIDY = "SUBSIDY"
CATEGORY_OTHER_EXPENDITURE = "OTHER_EXPENDITURE"
CATEGORY_TOTAL = "TOTAL"
CATEGORY_UNRESOLVED = "UNRESOLVED"

#: canonical set ทั้งหมด
CANONICAL_CATEGORIES = (
    CATEGORY_PERSONNEL,
    CATEGORY_OPERATING,
    CATEGORY_INVESTMENT,
    CATEGORY_SUBSIDY,
    CATEGORY_OTHER_EXPENDITURE,
    CATEGORY_TOTAL,
)

#: ข้อความไทยที่พบในแบบฟอร์มจริง → canonical code
#:
#: ``งบบุคลากร`` มาจากข้อค้นพบของชั้น ``T1B`` เอง (ชีตบทบาท ``6.``)
CATEGORY_LABELS: dict[str, str] = {
    "งบบุคลากร": CATEGORY_PERSONNEL,
    "งบดำเนินงาน": CATEGORY_OPERATING,
    "งบลงทุน": CATEGORY_INVESTMENT,
    "งบเงินอุดหนุน": CATEGORY_SUBSIDY,
    "งบรายจ่ายอื่น": CATEGORY_OTHER_EXPENDITURE,
    "รวม": CATEGORY_TOTAL,
}


def resolve_budget_category(raw: object) -> str:
    """แปลงข้อความหัวคอลัมน์เป็น canonical code

    คืน ``UNRESOLVED`` เมื่อไม่รู้จัก — **ห้ามเดาหมวดที่ใกล้เคียง**

    >>> resolve_budget_category("งบลงทุน")
    'INVESTMENT'
    >>> resolve_budget_category("งบชดใช้เงินคงคลัง")
    'UNRESOLVED'
    """
    return CATEGORY_LABELS.get(normalize_label(raw), CATEGORY_UNRESOLVED)


def is_known_category(raw: object) -> bool:
    """หัวคอลัมน์นี้เป็นหมวดงบรายจ่ายที่รู้จักหรือไม่"""
    return normalize_label(raw) in CATEGORY_LABELS
