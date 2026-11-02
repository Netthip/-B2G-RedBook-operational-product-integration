# -*- coding: utf-8 -*-
"""G3 (ส่วนที่ 1) — การปรับรูปข้อความก่อนเปรียบเทียบ (freeze: key-t1-1.0.0)

กติกาที่อนุมัติแล้ว (D-2569-08-27-12 ข้อ D7):
  1. ตัดช่องว่างซ้ำและช่องว่างหัวท้าย
  2. แยกเลขหัวข้อนำหน้าออกเป็นฟิลด์ต่างหาก
  3. คงวงเล็บและเครื่องหมายไว้ (ต่างกันต้องเห็น)
  4. แปลงเลขไทยเป็นเลขอารบิก **เฉพาะชั้นเปรียบเทียบ**
  5. เก็บค่า raw เสมอ

ข้อ 5 บังคับด้วยการที่ทุกฟังก์ชันคืนค่าใหม่ ไม่มีการแก้ค่าเดิม
"""
import re

THAI_DIGITS = "๐๑๒๓๔๕๖๗๘๙"
ARABIC_DIGITS = "0123456789"
_THAI_TO_ARABIC = str.maketrans(THAI_DIGITS, ARABIC_DIGITS)

# เลขหัวข้อนำหน้า เช่น "7.4.1 " · "1) " · "๓. " · "(2) "
_LEADING_NUMBER_RE = re.compile(
    r"^\s*\(?\s*([0-9๐-๙]+(?:\.[0-9๐-๙]+)*)\s*[.)\]]?\s+")

_WHITESPACE_RE = re.compile(r"\s+")


def thai_to_arabic_digits(text: str) -> str:
    """แปลงเลขไทยเป็นเลขอารบิก — ใช้เฉพาะชั้นเปรียบเทียบเท่านั้น"""
    return text.translate(_THAI_TO_ARABIC)


def collapse_whitespace(text: str) -> str:
    """ยุบช่องว่างซ้ำให้เหลือช่องเดียว และตัดช่องว่างหัวท้าย

    รวมถึงอักขระขึ้นบรรทัดใหม่ที่พบในหัวตารางของเอกสารงบประมาณ
    """
    return _WHITESPACE_RE.sub(" ", text).strip()


def split_leading_number(text: str):
    """แยกเลขหัวข้อนำหน้าออกจากชื่อ — คืน (เลขหัวข้อหรือ None, ชื่อที่เหลือ)"""
    m = _LEADING_NUMBER_RE.match(text)
    if not m:
        return None, text.strip()
    number = thai_to_arabic_digits(m.group(1))
    return number, text[m.end():].strip()


def normalize_name(value) -> dict:
    """ปรับรูปชื่อรายการหนึ่งค่า — คืนทั้งค่า raw และค่าเปรียบเทียบ

    คืน dict: raw · collapsed · outline_number · comparable
    `comparable` คือค่าที่ใช้ประกอบ composite key เท่านั้น
    """
    raw = "" if value is None else str(value)
    collapsed = collapse_whitespace(raw)
    outline, remainder = split_leading_number(collapsed)
    comparable = thai_to_arabic_digits(remainder)
    return {
        "raw": raw,
        "collapsed": collapsed,
        "outline_number": outline,
        "comparable": comparable,
    }


def normalize_for_key(value) -> str:
    """ค่าที่ใช้ประกอบคีย์สำหรับฟิลด์ทั่วไป (ไม่แยกเลขหัวข้อ)

    ฟิลด์โครงสร้าง เช่น ชื่อแผนงาน มีเลขนำหน้าเป็นส่วนหนึ่งของชื่อทางการ
    จึงยุบช่องว่างและแปลงเลขไทยเท่านั้น ไม่ตัดเลขหัวข้อออก
    """
    if value is None:
        return ""
    return thai_to_arabic_digits(collapse_whitespace(str(value)))
