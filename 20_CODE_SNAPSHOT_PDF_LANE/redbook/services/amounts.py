# -*- coding: utf-8 -*-
"""มาตรฐานการแสดงจำนวนเงินของทั้งระบบ (#24 · requirement หน่วยและทศนิยม 7 ต.ค. 2569)

ตัวจัดรูปแบบตัวเดียวที่ทุกหน้าใช้ — ภาพรวม · คิว · เทียบ A | B · ตรวจก่อนส่งออก
· ส่งออก · Audit · แถวหลักฐาน — เพื่อไม่ให้ค่าเดียวกันดูต่างกัน (เช่น ``7.4`` กับ ``7.4000``)

กติกา

1. หน่วย **ล้านบาท** → ทศนิยม **4 ตำแหน่งเสมอ** · ห้ามตัดศูนย์ท้าย
   (``7.4`` → ``7.4000`` · ``7.4001`` → ``7.4001``)
2. หน่วย **บาท** → คงเป็นบาทตามค่าจริง คั่นหลักพัน (``7,400,100``) · มีสตางค์ = 2 ตำแหน่ง
3. 🔴 **ไม่ปัดเศษ** — การเติมศูนย์ให้ครบ 4 ตำแหน่งไม่เปลี่ยนค่า · ถ้าค่าจริงละเอียดกว่า
   ที่มาตรฐานกำหนด ให้แสดงครบทุกหลัก (ตัวเลขบนจอต้องเป็นตัวเลขเดียวกับที่ใช้ตัดสิน)
4. หน่วยอื่น (ร้อยละ ฯลฯ) → แสดงค่าจริง ตัดศูนย์ท้ายที่ไม่มีความหมาย ไม่ปัดเศษ
5. 🔴 **การเปรียบเทียบใช้ค่าตัวเลข (``Decimal``) เสมอ** — ห้ามเทียบสตริงที่จัดรูปแบบแล้ว
   (:func:`same_value`)
6. ไม่แปลงหน่วยเอง — การแปลง ล้านบาท → บาท มีเฉพาะ "ค่าที่แปลงเพื่อสรุป" ที่ต้องติดป้ายบอก
   (:func:`to_baht`)

ข้อมูลที่เก็บไว้ (ตาราง ``t1b_findings`` · ค่า ``engine_*`` ที่ตรึงในคำตัดสิน) **ไม่ถูกแก้**
— มาตรฐานนี้ใช้ตอนแสดงผลและตอนเขียนไฟล์ส่งออก
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

FORMAT_VERSION = "amount-format-1.0.0"

UNIT_BAHT = "บาท"
UNIT_MILLION = "ล้านบาท"
MILLION_PLACES = 4
_Q4 = Decimal("0.0001")
_Q2 = Decimal("0.01")
_SCALE = {UNIT_BAHT: Decimal(1), UNIT_MILLION: Decimal(1_000_000)}


def norm_unit(unit) -> str:
    return "".join(str(unit or "").split())


def to_decimal(value) -> Decimal | None:
    """``Decimal`` จากค่าที่เครื่องยนต์/ไฟล์ให้มา — สตริงมีจุลภาคได้ · แปลงไม่ได้ = ``None``"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _places(d: Decimal) -> int:
    exp = d.as_tuple().exponent
    return -exp if isinstance(exp, int) and exp < 0 else 0


def format_number(value, unit="") -> str:
    """ตัวเลขตามมาตรฐานของหน่วยนั้น (ไม่มีชื่อหน่วย) · แปลงไม่ได้ = คืนข้อความเดิม"""
    d = to_decimal(value)
    if d is None:
        return "" if value is None else str(value)
    u = norm_unit(unit)
    if u == UNIT_MILLION:
        q = d if _places(d) > MILLION_PLACES else d.quantize(_Q4)   # เติมศูนย์ ไม่ปัด
        return format(q, ",f")
    if u == UNIT_BAHT:
        if d == d.to_integral_value():
            return format(d.quantize(Decimal(1)), ",f")
        q = d if _places(d) > 2 else d.quantize(_Q2)
        return format(q, ",f")
    if d == d.to_integral_value():
        return format(d.quantize(Decimal(1)), ",f")
    return format(d.normalize(), ",f")


def format_amount(value, unit="", *, empty: str = "—") -> str:
    """ตัวเลข + หน่วย เช่น ``7.4000 ล้านบาท`` · ไม่มีค่า = ``empty``"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return empty
    num = format_number(value, unit)
    u = str(unit or "").strip()
    return f"{num} {u}" if u and to_decimal(value) is not None else num


def to_baht(value, unit) -> Decimal | None:
    """แปลงเป็นบาทด้วยการคูณตรง (ไม่ปัด) — **ใช้กับค่าสรุปที่ติดป้ายว่าแปลงแล้วเท่านั้น**"""
    d = to_decimal(value)
    scale = _SCALE.get(norm_unit(unit))
    return None if d is None or scale is None else d * scale


def same_value(a, b) -> bool:
    """เทียบค่าตัวเลขจริง — ``7.4`` เท่ากับ ``7.4000`` · แปลงไม่ได้ฝั่งใด = เทียบข้อความ"""
    da, db = to_decimal(a), to_decimal(b)
    if da is None or db is None:
        return str(a or "").strip() == str(b or "").strip()
    return da == db


__all__ = ["FORMAT_VERSION", "UNIT_BAHT", "UNIT_MILLION", "norm_unit", "to_decimal",
           "format_number", "format_amount", "to_baht", "same_value"]
