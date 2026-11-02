# -*- coding: utf-8 -*-
"""ทะเบียนตัวชี้วัด — ข้อสังเกตต้นทางที่แก้ไม่ได้ + การจับคู่เก่า↔ใหม่ 8 สถานะ

งานตามคำสั่งกิ๊ฟ 9 ก.ย. 2569 (`GIFT DECISION` §2 · Gate 1–2 · Gate 4)

🔴 **หลักที่บังคับในโค้ด**

* *"Normalization may propose candidates but must not decide semantic identity."*
  ⇒ เครื่องเสนอได้เฉพาะ ``proposed_status`` · สถานะ 3 · 4 · 5 · 8 ต้องมีมนุษย์ยืนยัน
  และ ``RELATED_NOT_EQUIVALENT`` เครื่อง **ไม่เสนอเลย** (เป็นทางเลือกของผู้ตรวจ)
* *"Preserve both original texts; never replace one with the normalized form."*
  ⇒ ``observed_text`` กับ ``normalized_text`` เป็นคนละคอลัมน์ และแถวข้อสังเกต
  มี trigger กัน UPDATE/DELETE
* *"Do not show detector scores in the key-verification view"*
  ⇒ คะแนนภายในไม่อยู่ใน view/package ใด ๆ (มีเทสต์กัน)

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
INDICATORS_VERSION = "indicators-0.1.0"

__all__ = ["INDICATORS_VERSION"]
