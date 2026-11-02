# -*- coding: utf-8 -*-
"""ทดสอบนโยบายที่ผู้ใช้ล็อกแล้ว (27 ส.ค. 2569) — กันการแก้โดยไม่ตั้งใจ"""
from redbook.rules import policy


def test_no_base_message_is_locked_verbatim():
    """ถ้อยคำนี้ผู้ใช้กำหนดตายตัว — ห้ามเปลี่ยนแม้แต่ตัวอักษรเดียว"""
    assert policy.PCT_NO_BASE_MESSAGE == (
        "ไม่สามารถคำนวณร้อยละการเปลี่ยนแปลงได้ เนื่องจากไม่มีค่าฐานสำหรับการคำนวณ")


def test_pct_change_with_zero_or_missing_base():
    pct, msg = policy.pct_change(0, 500)
    assert pct is None and msg == policy.PCT_NO_BASE_MESSAGE
    pct, msg = policy.pct_change(None, 500)
    assert pct is None and msg == policy.PCT_NO_BASE_MESSAGE
    # ค่าฝั่ง A/B และผลต่างสัมบูรณ์ยังต้องรายงานได้ตามจริง
    assert policy.abs_diff(0, 500) == 500.0
    assert policy.abs_diff(None, 500) is None


def test_pct_change_normal_cases():
    pct, msg = policy.pct_change(100, 110)
    assert msg is None and round(pct, 6) == 10.0
    pct, _ = policy.pct_change(200, 150)
    assert round(pct, 6) == -25.0
    pct, msg = policy.pct_change(100, None)
    assert pct is None and msg is None


def test_highlight_is_filter_only_and_hides_nothing():
    """เกณฑ์ร้อยละใช้เน้นเท่านั้น — ค่าต่ำกว่าเกณฑ์ยังคืนผลจริง ไม่หายไป"""
    pct, _ = policy.pct_change(100, 104)          # +4% ต่ำกว่าเกณฑ์
    assert pct == 4.0                              # ค่าไม่ถูกซ่อนหรือปัดทิ้ง
    assert policy.exceeds_highlight(pct) is False  # แค่ไม่ถูกเน้น
    assert policy.exceeds_highlight(15.0) is True
    assert policy.exceeds_highlight(-12.0) is True
    assert policy.exceeds_highlight(None) is False  # คำนวณไม่ได้ ไม่เข้าตัวกรอง
    # ผู้ใช้ปรับเกณฑ์ต่องานได้
    assert policy.exceeds_highlight(4.0, threshold_pct=3) is True


def test_default_threshold_and_role():
    assert policy.PCT_HIGHLIGHT_DEFAULT == 10.0
    assert policy.PCT_HIGHLIGHT_ROLE == "highlight_only"
