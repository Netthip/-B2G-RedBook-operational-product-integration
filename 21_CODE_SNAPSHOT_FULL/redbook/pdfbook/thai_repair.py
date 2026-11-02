# -*- coding: utf-8 -*-
"""ซ่อมข้อความไทยที่ถอดจากชั้นข้อความ PDF แบบอนุรักษ์นิยม — เรียกจาก :func:`text.clean`

ปัญหาที่พบจริงในเล่ม/เอกสารที่เคยอ่าน (สรุปจากโค้ดเดิมใน Gift Command Center และทะเบียนขอบเขตหน้า)

1. **สระอำแตก** — ``ํ`` + ``า`` หรือ ช่องว่าง + ``า`` แทน ``ำ``
2. **ลำดับเครื่องหมายสลับ** — วรรณยุกต์มาก่อนสระบน/ล่าง (``่`` + ``ิ``) · วรรณยุกต์ซ้อนซ้ำ
3. **อักขระ PUA** — ฟอนต์ตระกูล SarabunPSK/Angsana วางรูปสระ/วรรณยุกต์ที่เลื่อนตำแหน่งไว้ใน U+F700–F71A

🔴 ข้อจำกัด

* ตาราง PUA ใช้ผัง "Thai PUA" ที่ฟอนต์ Windows ใช้ทั่วไป (เหมือน libthai) — **ยังไม่ได้ยืนยันกับ cmap
  ของฟอนต์ในเล่มจริง** · ตาราง PUA ในโค้ดเดิม (``read_form.clean``) ต่างจากผังนี้ จึงไม่ได้ยกมาใช้
* ไม่เดาคำ ไม่ใช้รายการคำเฉพาะเอกสาร · ข้อความดิบยังอยู่ใน PDF ต้นฉบับเสมอ (หลักฐานคือภาพหน้า)
* ทำซ้ำได้ผลเดิม (idempotent) · ข้อความไทยปกติไม่เปลี่ยน (มีเทสต์)
"""
from __future__ import annotations

import re

THAI_REPAIR_VERSION = "thai-repair-0.1.0"
PUA_MAP_STATUS = "UNVERIFIED_AGAINST_REAL_FONT"

#: ผัง Thai PUA ที่ใช้ทั่วไป (U+F700–F71A) → อักขระมาตรฐาน
PUA_MAP = {
    0xF700: "ฐ", 0xF70F: "ญ",
    0xF701: "ิ", 0xF702: "ี", 0xF703: "ึ", 0xF704: "ื",
    0xF705: "่", 0xF706: "้", 0xF707: "๊", 0xF708: "๋", 0xF709: "์",
    0xF70A: "่", 0xF70B: "้", 0xF70C: "๊", 0xF70D: "๋", 0xF70E: "์",
    0xF710: "ั", 0xF711: "ํ", 0xF712: "็",
    0xF713: "่", 0xF714: "้", 0xF715: "๊", 0xF716: "๋", 0xF717: "์",
    0xF718: "ุ", 0xF719: "ู", 0xF71A: "ฺ",
}
_PUA = str.maketrans({k: v for k, v in PUA_MAP.items()})

_TONES = "่้๊๋"
_UPPER = "ัิีึื็"
_LOWER = "ฺุู"
_SARA_AM_SPLIT = re.compile("ํ([่้๊๋]?)า")             # นิคหิต (+วรรณยุกต์) + า → (วรรณยุกต์) + ำ
_SPACE_AA = re.compile("([ก-ฮ][่้๊๋]?)\\s+า")           # "ต าแหน่ง" — นิคหิตหายเหลือช่องว่าง (สระอาขึ้นต้นคำไม่ได้)
_SPACE_AM = re.compile("([ก-ฮ][่้๊๋]?)\\s+ำ")
_TONE_BEFORE_VOWEL = re.compile(f"([{_TONES}])([{_UPPER}{_LOWER}])")
_DOUBLE_MARK = re.compile(f"([{_TONES}์])\\1+")
#: เรียงตามตำแหน่งแล้ววรรณยุกต์/สระบนเลยไปอยู่หลัง า/ำ ("ลา้น" → "ล้าน") — เครื่องหมายไม่เกาะ า/ำ
_MARK_AFTER_AA = re.compile(f"([าำ])([{_TONES}์{_UPPER}])")


def repair(s: str) -> str:
    if not s:
        return s
    t = s.translate(_PUA)
    t = _SARA_AM_SPLIT.sub(lambda m: m.group(1) + "ำ", t)
    t = _SPACE_AM.sub(r"\1ำ", t)
    t = _SPACE_AA.sub(r"\1ำ", t)
    t = _MARK_AFTER_AA.sub(r"\2\1", t)
    t = _TONE_BEFORE_VOWEL.sub(r"\2\1", t)
    t = _DOUBLE_MARK.sub(r"\1", t)
    return t
