# -*- coding: utf-8 -*-
"""ข้อความและตัวเลขจากชั้นข้อความ PDF — รูปมาตรฐานสำหรับเทียบ (ไม่ใช้แทนข้อความต้นฉบับ)

* ``squash`` ตัดช่องว่างทั้งหมด (PDF ไทยมักแตกคำด้วยช่องว่างไม่สม่ำเสมอ)
* ``skeleton`` ตัดสระบน/ล่างและวรรณยุกต์ — ทางสำรองเมื่อการสกัดเรียงอักขระไม่ตรงกัน
  ระหว่างสองไฟล์ (พบจริงในเล่มที่บันทึกในทะเบียนขอบเขตหน้า)
* ``parse_amount`` อ่านจำนวนเงินแบบ Decimal ไม่ปัดเศษ · ``-`` เดี่ยว = ช่องว่าง (ไม่มีค่า)
  · ``- 8.4496`` (ลบมีช่องว่าง) = ค่าลบ
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from ..indicators.normalize import normalize as _ind_normalize
from .thai_repair import repair as _thai_repair

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_THAI_MARKS = re.compile(r"[ัิ-ฺ็-๎]")
_WS = re.compile(r"[\s​‌‍﻿ ]+")
_LEAD_NO = re.compile(r"^\s*(?:\(\d+\)|\d+\)|\d+(?:\.\d+)*\.?)\s*")
_LEVEL_PREFIX = re.compile(r"^(?:แผนงาน|ผลผลิต(?:ที่\s*\d+)?|โครงการ(?:ที่\s*\d+)?|กิจกรรม(?:ที่\s*\d+)?)"
                           r"\s*[:：]?\s*")
_LEVEL_PREFIX_SK = re.compile(r"^(?:แผนงาน|ผลผลิต|ผลผลต|โครงการ|โครงกร|กิจกรรม|กจกรรม)(?:ท[ี]?\s*\d+)?\s*[:：]?\s*")
NUMBER_TOKEN = re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^-?\d+(?:\.\d+)?$")
DASH_TOKENS = {"-", "–", "—", "−", "‐", "‑"}
#: ขีดที่ PDF บางไฟล์ถอดออกมาเป็นอักขระอื่น (soft hyphen ฯลฯ) — แปลงเป็น "-" ก่อนเทียบ
_DASH_MAP = str.maketrans({"\u00ad": "-", "\u2010": "-", "\u2011": "-", "\u2212": "-"})


def clean(s: str) -> str:
    """ข้อความแสดงผล — NFC · เลขไทยเป็นอารบิก · ช่องว่างเดียว"""
    s = _thai_repair(unicodedata.normalize("NFC", s or "")).translate(_THAI_DIGITS).translate(_DASH_MAP)
    return _WS.sub(" ", s).strip()


def _is_thai(ch: str) -> bool:
    return "\u0e00" <= ch <= "\u0e7f"


def join_wrapped(a: str, b: str) -> str:
    """ต่อบรรทัดที่ห่อ — ไทยชนไทยไม่เว้นวรรค (การห่อบรรทัดไม่ใช่ช่องว่างจริงของข้อความ)"""
    a, b = (a or "").rstrip(), (b or "").lstrip()
    if not a or not b:
        return a or b
    return a + ("" if _is_thai(a[-1]) and _is_thai(b[0]) else " ") + b


def squash(s: str) -> str:
    return _WS.sub("", clean(s))


_JUNK = re.compile("[�​-‍﻿]")


def skeleton(s: str) -> str:
    """ตัดสระบน/ล่าง วรรณยุกต์ ช่องว่าง และอักขระเสีย (U+FFFD) — ใช้จับคู่เมื่อการถอดข้อความเพี้ยน"""
    return _THAI_MARKS.sub("", _JUNK.sub("", squash(s)).replace("ำ", "า"))   # ำ ที่แตกเหลือ า


def strip_number(s: str) -> str:
    """ตัดเลขข้อนำหน้า "7.2.1 " / "(3) " ออก"""
    return _LEAD_NO.sub("", clean(s))


def label_key(s: str) -> str:
    """กุญแจจับคู่ชื่อรายการ — ตัดเลขข้อ · ตัดคำนำระดับ ("ผลผลิต :") · รูปมาตรฐาน · **ตัดสระ/วรรณยุกต์**

    เล่มจริงถอดลำดับสระ/วรรณยุกต์ต่างกันระหว่างตาราง ("ทีมี่" ↔ "ที่มี") และทำ ำ หาย ⇒ กุญแจต้องไม่ไวต่อ
    เครื่องหมาย · ข้อความที่แสดงยังเป็นข้อความเดิม
    """
    t = strip_number(s)
    t = _LEVEL_PREFIX.sub("", t)
    return skeleton(_ind_normalize(_LEVEL_PREFIX_SK.sub("", t)))


def exact_key(s: str) -> str:
    """รูปเทียบชื่อ **คงสระ/วรรณยุกต์** — ใช้ตรวจว่าคู่ที่จับด้วย :func:`label_key` ชื่อตรงกันจริงหรือไม่"""
    t = _LEVEL_PREFIX.sub("", strip_number(s))
    return squash(_ind_normalize(t))


def text_key(s: str) -> str:
    """กุญแจเทียบข้อความยาว (วิสัยทัศน์/พันธกิจ) — ต่างเฉพาะช่องว่าง/เครื่องหมาย = เท่ากัน"""
    return squash(_ind_normalize(strip_number(s)))


def similarity(a: str, b: str) -> float:
    """ความคล้ายเชิงอักขระ 0–1 (ใช้ *เสนอ* คู่ให้คนตัดสินเท่านั้น)"""
    from difflib import SequenceMatcher
    a, b = label_key(a), label_key(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def is_number(tok: str) -> bool:
    return bool(NUMBER_TOKEN.match(clean(tok)))


def parse_amount(tok: str) -> Decimal | None:
    t = clean(tok).replace(",", "")
    if not t or t in DASH_TOKENS:
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


#: ตัวคูณแปลงหน่วยเป็นบาท
UNIT_SCALE = {"บาท": Decimal(1), "ล้านบาท": Decimal(1_000_000)}


def fmt(v: Decimal | None, unit: str = "") -> str:
    """ตัวเลขแสดงผล **ตามทศนิยมที่พิมพ์** — ไม่ปัด และไม่เติมศูนย์ให้ดูละเอียดกว่าเอกสาร

    ``Decimal`` เก็บจำนวนหลักตามข้อความต้นฉบับอยู่แล้ว ("0.1760" ยังเป็น 4 ตำแหน่ง · "1.2" เป็น 1 ตำแหน่ง)
    """
    if v is None:
        return "—"
    if unit == "บาท" and v == v.to_integral_value():
        return f"{int(v):,}"          # ค่าที่แปลงจากล้านบาท (×1,000,000) ไม่ต้องมีศูนย์ท้ายจากการคูณ
    return f"{v:,}"


def to_baht(v: Decimal | None, unit: str) -> Decimal | None:
    if v is None:
        return None
    return v * UNIT_SCALE.get(unit, Decimal(1))
