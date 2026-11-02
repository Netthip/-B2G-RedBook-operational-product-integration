# -*- coding: utf-8 -*-
"""นโยบายที่ผู้ใช้ล็อกแล้ว (Decision Log ในรูปโค้ด) — แก้ได้เมื่อผู้ใช้สั่งเท่านั้น

ที่มา: คำตัดสินของผู้รับผิดชอบงานวิจัย 27 ส.ค. 2569 (บันทึกใน docs/DECISIONS_LOG.md)

ข้อ 1 (Q5): เกณฑ์ร้อยละใช้เป็นตัวช่วยเน้น/จัดลำดับเท่านั้น ปรับได้ต่องาน
  ห้ามใช้ตัดสินถูก-ผิด และห้ามซ่อนผลต่างที่ต่ำกว่าเกณฑ์
ข้อ 2: เมื่อฐานเป็นศูนย์หรือว่าง ให้แสดงข้อความตามที่กำหนดไว้ตายตัว
  พร้อมแสดงค่าฝั่ง A ค่าฝั่ง B และผลต่างสัมบูรณ์ตามจริงเสมอ
"""

# --- Q5: บทบาทของเกณฑ์ร้อยละ (ล็อกแล้ว) ---------------------------------
PCT_HIGHLIGHT_DEFAULT = 10.0          # ค่าเริ่มต้น ผู้ใช้ปรับได้ต่องาน
PCT_HIGHLIGHT_ROLE = "highlight_only"  # บทบาทเดียวที่อนุญาต (บังคับใน mapping_model)

# --- ข้อความเมื่อไม่มีฐานคำนวณร้อยละ (ล็อกแล้ว — ห้ามแก้ถ้อยคำ) ----------
PCT_NO_BASE_MESSAGE = (
    "ไม่สามารถคำนวณร้อยละการเปลี่ยนแปลงได้ เนื่องจากไม่มีค่าฐานสำหรับการคำนวณ")


def abs_diff(value_a, value_b):
    """ผลต่างสัมบูรณ์เชิงเครื่องหมาย (B - A) — คืน None เมื่อฝั่งใดไม่มีค่า

    ระบบต้องแสดงค่าฝั่ง A ค่าฝั่ง B และผลต่างนี้ตามจริงเสมอ ไม่ขึ้นกับเกณฑ์ร้อยละ
    """
    if value_a is None or value_b is None:
        return None
    return float(value_b) - float(value_a)


def pct_change(base_value, current_value):
    """ร้อยละการเปลี่ยนแปลงเทียบฐาน — คืน (pct, message)

    - ฐานเป็น None หรือ 0  → (None, PCT_NO_BASE_MESSAGE) ตามคำตัดสินที่ล็อก
    - ค่าปัจจุบันเป็น None → (None, None) คำนวณไม่ได้แต่ไม่ใช่กรณีข้อความล็อก
    - กรณีปกติ            → (ร้อยละ, None)

    ฟังก์ชันนี้ไม่ตัดสินถูก-ผิด และไม่กรองค่าใดออก — ผู้เรียกต้องรายงาน
    ค่าฝั่ง A ค่าฝั่ง B และผลต่างสัมบูรณ์คู่กันเสมอ
    """
    if base_value is None or float(base_value) == 0.0:
        return None, PCT_NO_BASE_MESSAGE
    if current_value is None:
        return None, None
    pct = (float(current_value) - float(base_value)) / float(base_value) * 100.0
    return pct, None


def exceeds_highlight(pct, threshold_pct=PCT_HIGHLIGHT_DEFAULT):
    """ผลต่างนี้ควรถูก "เน้น" หรือไม่ — ใช้จัดลำดับ/ระดับความสำคัญเท่านั้น

    คืน False เมื่อ pct เป็น None (คำนวณไม่ได้ ไม่นับเข้าตัวกรองร้อยละ)
    ห้ามนำผลนี้ไปซ่อนรายการหรือเรียกรายการว่าเป็นข้อผิดพลาด
    """
    if pct is None:
        return False
    return abs(pct) > float(threshold_pct)
