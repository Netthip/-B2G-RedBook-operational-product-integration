# -*- coding: utf-8 -*-
"""T1B — หน่วยนับระดับแถว และการปัดทศนิยมตามที่เอกสารประกาศ

🔴 **silent failure #2 — หน่วยอยู่ที่ระดับแถว ไม่ใช่ระดับไฟล์**
ในชีตเดียวกันมีทั้ง ``ล้านบาท`` และ ``ร้อยละ`` และในสมุดงานเล่มเดียวกัน
มีทั้ง ``บาท`` และ ``ล้านบาท`` ซึ่งต่างกันหนึ่งล้านเท่า

🔴 **silent failure #3 — ค่าที่เก็บมีเศษ floating-point เกินทศนิยมที่ประกาศ**
ตัวอย่างจริง ``937.5201000000001`` ในชีตที่ประกาศว่า ``ล้านบาท (ทศนิยม 4 ตำแหน่ง)``
การเทียบด้วย ``==`` บน ``float`` จะรายงานว่าต่างกันทั้งที่ตัวเลขในเอกสารเท่ากัน

🔴 **silent failure #10 — เซลล์หน่วยนับบรรจุตัวเลขแทนชื่อหน่วย**
พบจริงใน ``XL_FY2570_draft-bill_21011_HSRI.xlsx`` ชีต ``Sheet5`` แถว 13–14
คอลัมน์ ``B`` มีค่า ``100`` แทนที่จะเป็น ``ร้อยละ``
⇒ เป็นข้อบกพร่องของไฟล์ต้นทาง ระบบต้อง **รายงาน ไม่ใช่เดาแทน**
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .normalize import normalize_label

UNIT_MILLION_BAHT = "ล้านบาท"
UNIT_BAHT = "บาท"
UNIT_PERCENT = "ร้อยละ"
UNIT_UNRESOLVED = "UNRESOLVED"

#: หน่วยที่ถือเป็นจำนวนเงิน — ใช้ตัดสินว่านำไปกระทบยอดได้หรือไม่
MONETARY_UNITS = frozenset({UNIT_MILLION_BAHT, UNIT_BAHT})

#: ทศนิยมที่เอกสารประกาศต่อหน่วย
DECLARED_PLACES = {
    UNIT_MILLION_BAHT: 4,
    UNIT_BAHT: 2,
    UNIT_PERCENT: 2,
}

#: ดึงทศนิยมจากข้อความประกาศหน่วย เช่น "หน่วย : ล้านบาท (ทศนิยม 4 ตำแหน่ง)"
_DECLARED_PLACES_PAT = re.compile(r"ทศนิยม\s*(\d+)\s*ตำแหน่ง")

#: เรียงจากยาวไปสั้น — "ล้านบาท" ต้องถูกจับก่อน "บาท"
_UNIT_MARKERS: tuple[tuple[str, str], ...] = (
    (UNIT_MILLION_BAHT, UNIT_MILLION_BAHT),
    (UNIT_PERCENT, UNIT_PERCENT),
    (UNIT_BAHT, UNIT_BAHT),
)


def resolve_declared_unit(value: object) -> str:
    """อ่านหน่วยนับของแถวหนึ่ง

    คืน ``UNRESOLVED`` เมื่อเซลล์ว่าง หรือ **บรรจุตัวเลขแทนชื่อหน่วย**
    ซึ่งเป็นข้อบกพร่องที่พบจริงในไฟล์ต้นทาง

    >>> resolve_declared_unit("ล้านบาท")
    'ล้านบาท'
    >>> resolve_declared_unit("หน่วย : ล้านบาท (ทศนิยม 4 ตำแหน่ง)")
    'ล้านบาท'
    >>> resolve_declared_unit(100)
    'UNRESOLVED'
    """
    if value is None or isinstance(value, bool):
        return UNIT_UNRESOLVED
    if isinstance(value, (int, float, Decimal)):
        # เซลล์หน่วยนับที่เป็นตัวเลข = defect ของไฟล์ต้นทาง ห้ามเดาแทน
        return UNIT_UNRESOLVED
    text = normalize_label(value)
    if not text:
        return UNIT_UNRESOLVED
    for marker, unit in _UNIT_MARKERS:
        if marker in text:
            return unit
    return UNIT_UNRESOLVED


def find_sheet_unit_declaration(rows: list[list[object]]) -> tuple[str, object]:
    """หาการประกาศหน่วยที่ **ระดับชีต** — ใช้เมื่อชีตไม่มีคอลัมน์หน่วยรายแถว

    บทบาท ``8.`` ประกาศหน่วยไว้ครั้งเดียวที่หัวชีต
    (``"หน่วย : ล้านบาท (ทศนิยม 4 ตำแหน่ง)"``) และใช้คอลัมน์ ``B`` เป็น**ค่า**
    ไม่ใช่หน่วย ต่างจากบทบาท ``5.`` ที่มีหน่วยรายแถวในคอลัมน์ ``B``

    คืน ``(unit, declaration_text)`` — ``(UNRESOLVED, None)`` เมื่อไม่พบ
    """
    for row in rows:
        for cell in row:
            if not isinstance(cell, str):
                continue
            if "หน่วย" not in cell:
                continue
            unit = resolve_declared_unit(cell)
            if unit != UNIT_UNRESOLVED:
                return unit, cell
    return UNIT_UNRESOLVED, None


def has_row_unit_column(rows: list[list[object]], column: int) -> bool:
    """ชีตนี้ใช้คอลัมน์ ``column`` เป็นคอลัมน์หน่วยนับรายแถวจริงหรือไม่

    🔴 จำเป็นเพื่อ**ไม่กลบข้อบกพร่อง** — ถ้าชีตมีคอลัมน์หน่วยจริง
    แถวที่หน่วยอ่านไม่ออกคือ *ความผิดปกติ* ต้องคง ``UNRESOLVED`` ไว้
    แต่ถ้าชีตไม่มีคอลัมน์หน่วยเลย จึงจะใช้การประกาศระดับชีตแทนได้
    """
    return any(
        len(row) > column and resolve_declared_unit(row[column]) != UNIT_UNRESOLVED
        for row in rows
    )


def declared_places(unit: str, declaration: object = None) -> int:
    """จำนวนทศนิยมที่เอกสารประกาศ

    ถ้า ``declaration`` มีข้อความ ``"ทศนิยม N ตำแหน่ง"`` ให้ใช้ค่านั้นก่อน
    มิฉะนั้นใช้ค่าปริยายตามหน่วย
    """
    if declaration is not None:
        m = _DECLARED_PLACES_PAT.search(normalize_label(declaration))
        if m:
            return int(m.group(1))
    return DECLARED_PLACES.get(unit, 4)


def is_monetary(unit: str) -> bool:
    """หน่วยนี้เป็นจำนวนเงินหรือไม่ — ``ร้อยละ`` และ ``UNRESOLVED`` ไม่ใช่"""
    return unit in MONETARY_UNITS


def quantum_for(unit: str, declaration: object = None) -> Decimal:
    """หน่วยละเอียดที่สุดของค่าหนึ่ง ตามทศนิยมที่ **เอกสารประกาศจริง**

    ใช้ :func:`declared_places` ตัวเดียวกับที่ :func:`normalize_amount` ใช้ปัดค่า
    ⇒ ขอบการปัดกับการปัดจริงอิงกติกาเดียวกันเสมอ

    🔴 BO REVIEW (2 ก.ย.): การกระทบยอดเคยใช้ ``0.0001`` กับทุกหน่วย
    ⇒ ยอดหน่วย ``บาท`` ที่ต่างกัน ``0.01`` ถูกจัดเป็นยอดผิดจริง

    🔴 BO REVIEW (3 ก.ย.): รอบก่อนยังอิง **ค่าปริยายตามชนิดหน่วย** อย่างเดียว
    ทั้งที่ ``normalize_amount()`` รองรับข้อความอย่าง ``"บาท (ทศนิยม 3 ตำแหน่ง)"``
    ⇒ ขอบไม่ตรงกับความละเอียดที่ค่านั้นถูกปัดมาจริง

    >>> quantum_for('ล้านบาท')
    Decimal('0.0001')
    >>> quantum_for('บาท')
    Decimal('0.01')
    >>> quantum_for('บาท', 'หน่วย : บาท (ทศนิยม 3 ตำแหน่ง)')
    Decimal('0.001')
    """
    return Decimal(1).scaleb(-declared_places(unit, declaration))


def normalize_amount(value: object, unit: str, declaration: object = None) -> Decimal | None:
    """แปลงค่าเป็น ``Decimal`` แล้วปัดตามทศนิยมที่เอกสารประกาศ

    ใช้ ``repr()`` ของ ``float`` เพื่อไม่ให้ได้เศษ binary เพิ่มเข้ามาอีกชั้น

    >>> normalize_amount(937.5201000000001, "ล้านบาท")
    Decimal('937.5201')
    >>> normalize_amount(None, "ล้านบาท") is None
    True
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.replace(",", "").strip()
        if not text:
            return None
        try:
            dec = Decimal(text)
        except InvalidOperation:
            return None
    elif isinstance(value, Decimal):
        dec = value
    elif isinstance(value, (int, float)):
        dec = Decimal(repr(value))
    else:
        return None
    places = declared_places(unit, declaration)
    return dec.quantize(Decimal(1).scaleb(-places))


def amounts_equal(a: object, b: object, unit: str, declaration: object = None) -> bool:
    """เทียบสองค่าหลังปัดตามทศนิยมที่ประกาศ

    ``937.5201000000001`` กับ ``937.5201`` ถือว่าเท่ากันภายใต้ ``ล้านบาท``
    เพราะเอกสารประกาศทศนิยม 4 ตำแหน่ง
    """
    return normalize_amount(a, unit, declaration) == normalize_amount(b, unit, declaration)


def comparable_units(unit_a: str, unit_b: str) -> bool:
    """หน่วยสองค่านี้นำมาเทียบกันตรง ๆ ได้หรือไม่

    ``บาท`` กับ ``ล้านบาท`` **ไม่** comparable โดยตรง (ต่างกันล้านเท่า) —
    ต้องแปลงก่อนและต้องรายงานว่าแปลง
    ``UNRESOLVED`` ไม่ comparable กับอะไรเลย ต้องยกเป็น finding
    """
    if UNIT_UNRESOLVED in (unit_a, unit_b):
        return False
    return unit_a == unit_b
