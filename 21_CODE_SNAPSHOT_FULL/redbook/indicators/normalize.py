# -*- coding: utf-8 -*-
"""การทำข้อความให้เป็นรูปมาตรฐาน (normalization) — **เสนอได้ ตัดสินไม่ได้**

ผลของโมดูลนี้ใช้ได้เพียงสองอย่าง

1. ตรวจว่าข้อความสองข้อความ *ต่างกันเฉพาะรูปแบบ* (ช่องว่าง · เครื่องหมาย · เลขไทย)
   ⇒ เสนอ ``SAME_WORDING_VARIANT``
2. คำนวณความคล้ายเชิงอักขระ เพื่อ *เสนอ* คู่ให้มนุษย์ตัดสิน

🔴 โมดูลนี้ **ไม่รู้ความหมาย** — "ผู้ป่วย" กับ "ผู้ป่วยนอก" คล้ายกันทางอักขระมาก
แต่เป็นคนละตัวชี้วัด · จึงมีเทสต์เชิงลบบังคับว่าความคล้ายสูงต้องไม่กลายเป็น
``SAME_*`` โดยอัตโนมัติ (ดู :mod:`redbook.indicators.mapping`)

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import re
import unicodedata

NORMALIZE_VERSION = "indicator-normalize-0.1.0"

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_ZERO_WIDTH = re.compile("[​‌‍﻿­]")
_PUNCT_MAP = str.maketrans({
    "：": ":", "（": "(", "）": ")", "／": "/", "－": "-", "–": "-", "—": "-",
    "‐": "-", "，": ",", "．": ".", "％": "%", " ": " ", "　": " ",
    "“": '"', "”": '"', "‘": "'", "’": "'",
})
_WS = re.compile(r"\s+")
_SPACE_AROUND = re.compile(r"\s*([:()/,;%\-])\s*")
_TRAILING_PUNCT = re.compile(r"[\s:;,.\-]+$")
_LEADING_PUNCT = re.compile(r"^[\s:;,.\-]+")

#: หน่วยนับที่รู้จัก — ใช้เพื่อ *ตรวจว่าหน่วยเปลี่ยน* เท่านั้น ไม่ใช่เพื่อตีความ
UNIT_LEXICON = (
    "ร้อยละ", "%", "ล้านบาท", "บาท", "คน", "ราย", "เรื่อง", "ครั้ง", "แห่ง",
    "หลักสูตร", "ฉบับ", "หน่วยงาน", "โครงการ", "ระดับ", "คะแนน", "วัน", "ชิ้น",
    "ตัว", "รายการ", "ผลงาน", "ชุด", "ระบบ", "จังหวัด", "พื้นที่", "องค์กร",
)

#: ถ้อยคำที่บ่งชี้ *วิธีคำนวณ/ตัวหาร/ขอบเขต* — การเปลี่ยนตรงนี้ = นิยามเปลี่ยน
METHOD_CUES = ("นับจาก", "คำนวณจาก", "คิดจาก", "วัดจาก", "เทียบกับ", "หารด้วย",
               "ตัวหาร", "ฐาน", "นิยาม", "วิธีคำนวณ", "ขอบเขต", "เฉพาะ")

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def normalize(text: str) -> str:
    """รูปมาตรฐานสำหรับเทียบ — **ไม่ใช้แทนข้อความต้นฉบับ**"""
    if text is None:
        return ""
    s = unicodedata.normalize("NFC", str(text))
    s = _ZERO_WIDTH.sub("", s)
    s = s.translate(_THAI_DIGITS).translate(_PUNCT_MAP)
    s = s.casefold()
    s = _WS.sub(" ", s)
    s = _SPACE_AROUND.sub(r"\1", s)
    s = _LEADING_PUNCT.sub("", s)
    s = _TRAILING_PUNCT.sub("", s)
    return s.strip()


def compact(norm: str) -> str:
    """ตัดช่องว่างทั้งหมด — ภาษาไทยไม่มีช่องว่างคั่นคำ การเว้นวรรคจึงเป็นเรื่องรูปแบบ"""
    return norm.replace(" ", "")


_VARIANT_PUNCT = re.compile(r"[\s:;,.()\[\]\-\"'/]+")


def variant_key(text: str) -> str:
    """กุญแจสำหรับ ``SAME_WORDING_VARIANT`` — ตัดช่องว่างและเครื่องหมายวรรคตอนทั้งหมด

    สองข้อความที่ให้กุญแจเดียวกัน ต่างกันได้เฉพาะ *รูปแบบ* (ช่องว่าง · วงเล็บ ·
    เครื่องหมาย · เลขไทย/อารบิก) — ตัวอักษรและตัวเลขต้องเหมือนกันทุกตัว
    """
    return _VARIANT_PUNCT.sub("", normalize(text))


def trigrams(norm: str) -> frozenset[str]:
    c = compact(norm)
    if len(c) < 3:
        return frozenset({c}) if c else frozenset()
    return frozenset(c[i:i + 3] for i in range(len(c) - 2))


def dice(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


def numeric_tokens(text: str) -> tuple[str, ...]:
    """ตัวเลขทั้งหมดในข้อความ (หลังแปลงเลขไทย) — ลำดับตามที่ปรากฏ"""
    return tuple(m.group(0).replace(",", "") for m in _NUMBER.finditer(normalize(text)))


_UNIT_AFTER_NUMBER = re.compile(
    r"\d+(?:[.,]\d+)*\s*(" + "|".join(re.escape(u) for u in UNIT_LEXICON if u not in ("ร้อยละ", "%")) + r")(?![ก-๙])")


def unit_tokens(text: str) -> tuple[str, ...]:
    """หน่วยนับที่ *ตามหลังตัวเลข* (เช่น "200 คน") + ร้อยละ/% ที่ใดก็ได้

    ตรวจเฉพาะหลังตัวเลขเพื่อกัน false positive จากคำที่มีหน่วยเป็นส่วนประกอบ
    ("ตัว" ใน "ตัวชี้วัด" · "ราย" ใน "รายงาน")
    """
    norm = normalize(text)
    found = {m.group(1) for m in _UNIT_AFTER_NUMBER.finditer(norm)}
    if "ร้อยละ" in norm or "%" in norm:
        found.add("ร้อยละ")
    return tuple(sorted(found))


def method_span(text: str) -> str:
    """ส่วนของข้อความที่พูดถึงวิธีคำนวณ/ตัวหาร — ว่างถ้าไม่มี"""
    norm = normalize(text)
    hits = [norm.find(c.casefold()) for c in METHOD_CUES]
    hits = [h for h in hits if h >= 0]
    if not hits:
        return ""
    start = min(hits)
    # ถ้าคำบ่งชี้อยู่ในวงเล็บ ให้เอาเฉพาะเนื้อในวงเล็บนั้น
    open_idx = norm.rfind("(", 0, start)
    close_idx = norm.find(")", start)
    if open_idx >= 0 and close_idx >= 0:
        return norm[open_idx + 1:close_idx]
    return norm[start:]


__all__ = [
    "NORMALIZE_VERSION", "UNIT_LEXICON", "METHOD_CUES", "normalize", "compact", "variant_key",
    "trigrams", "dice", "numeric_tokens", "unit_tokens", "method_span",
]
