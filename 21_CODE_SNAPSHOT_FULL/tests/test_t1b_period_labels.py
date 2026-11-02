# -*- coding: utf-8 -*-
"""G5 (#14) — grammar ของป้ายช่วงเวลา

🔴 **SYNTHETIC TEST FIXTURE** — ป้ายทั้งหมดในไฟล์นี้แต่งขึ้น ไม่มีข้อมูลจริง

กติกาที่ตัดสินไว้ (กิ๊ฟ · 8 ก.ย. 2569 ข้อ 2)

* ปีเดี่ยวเท่านั้นเข้าแกนปีเดิม · ช่วงเวลาเข้าแกนใหม่
* จับคู่ได้เฉพาะเมื่อป้ายดิบตรงกันหลัง normalization อนุรักษนิยม
* 🔴 ห้ามจับคู่เพียงเพราะปีเริ่มต้นตรงกัน

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import pytest

from redbook.t1b import parse_year_label
from redbook.t1b.header import (
    PERIOD_OPEN_END,
    PERIOD_OPEN_START,
    PERIOD_RANGE,
    PERIOD_YEAR,
    normalize_period_label,
    parse_period_label,
    resolve_period_columns,
)


@pytest.mark.parametrize("raw, kind, start, end", [
    ("ปี 2570", PERIOD_YEAR, 2570, 2570),
    ("ปี2570", PERIOD_YEAR, 2570, 2570),
    ("พ.ศ. 2570", PERIOD_YEAR, 2570, 2570),
    ("พ.ศ.2570", PERIOD_YEAR, 2570, 2570),
    ("2570", PERIOD_YEAR, 2570, 2570),
    ("เริ่มต้น - ปี 2569", PERIOD_OPEN_START, None, 2569),
    ("เริ่มต้น–ปี 2569", PERIOD_OPEN_START, None, 2569),
    ("เริ่มต้น ถึง ปี 2569", PERIOD_OPEN_START, None, 2569),
    ("ปี 2573 - จบ", PERIOD_OPEN_END, 2573, None),
    ("ปี 2573–จบ", PERIOD_OPEN_END, 2573, None),
    ("ปี 2573—จบ", PERIOD_OPEN_END, 2573, None),
    ("ปี 2573 ถึง จบ", PERIOD_OPEN_END, 2573, None),
    ("ปี 2573 เป็นต้นไป", PERIOD_OPEN_END, 2573, None),
    ("ปี 2571 - 2573", PERIOD_RANGE, 2571, 2573),
    ("ปี 2571-2573", PERIOD_RANGE, 2571, 2573),
    ("2571–2573", PERIOD_RANGE, 2571, 2573),
    ("  ปี   2573   -   จบ  ", PERIOD_OPEN_END, 2573, None),
    ("ปี ๒๕๗๓ - จบ", PERIOD_OPEN_END, 2573, None),
])
def test_grammar(raw, kind, start, end):
    label = parse_period_label(raw)
    assert label is not None, raw
    assert (label.kind, label.start_year, label.end_year) == (kind, start, end)
    assert label.raw == raw, "ป้ายดิบต้องถูกเก็บไว้ ห้ามทิ้งหลัง normalize"


@pytest.mark.parametrize("raw", [
    "ปี", "ปีที่ 3", "2570 บาท", "หน่วยนับ", "รวม", "", "ปี 1999",
    "ปี 2573 - 2571",          # ช่วงกลับด้าน — ไม่เดา
    "ปี 2571 - 2571",          # ช่วงปีเดียวซ้ำ — ไม่ใช่ช่วง
    "เริ่มต้น - จบ",            # ไม่มีปี
])
def test_labels_that_must_not_parse(raw):
    assert parse_period_label(raw) is None


@pytest.mark.parametrize("value", [2570, 2570.0, None, True])
def test_numbers_are_values_not_labels(value):
    """เซลล์ตัวเลข ``2570`` คือค่า ไม่ใช่ป้าย — ห้ามถูกอ่านเป็นหัวคอลัมน์"""
    assert parse_period_label(value) is None


@pytest.mark.parametrize("a, b", [
    ("ปี 2573 - จบ", "ปี 2573–จบ"),
    ("ปี 2573 - จบ", "  ปี 2573  —  จบ "),
    ("เริ่มต้น - ปี 2569", "เริ่มต้น–ปี  2569"),
])
def test_conservative_normalization_equates_dash_and_space_variants(a, b):
    assert normalize_period_label(a) == normalize_period_label(b)


@pytest.mark.parametrize("a, b", [
    ("ปี 2573 - จบ", "ปี 2573 - 2575"),     # ปีเริ่มต้นตรง แต่คนละช่วง
    ("ปี 2573 - จบ", "ปี 2573"),
    ("ปี 2573 - จบ", "ปี 2574 - จบ"),
    ("ปี 2573 - จบ", "ปี ๒๕๗๓ - จบ"),       # ตัวเลขไทยไม่ถูกแปลงตอนจับคู่
    ("ปี 2573 - จบ", "ปี 2573 ถึง จบ"),     # คำต่างกัน = ป้ายต่างกัน
])
def test_different_periods_never_normalize_to_the_same_label(a, b):
    """🔴 ห้ามจับคู่เพียงเพราะปีเริ่มต้นตรงกัน"""
    assert normalize_period_label(a) != normalize_period_label(b)


def test_strict_year_axis_is_unchanged():
    """ปีเดี่ยวแบบเดิม (``ปี dddd``) ยังเข้าแกนปีเหมือนเดิม — ไม่มีการขยายแกนปีเดิม

    รูปแบบปีเดี่ยวอื่น (``พ.ศ.`` · เลขล้วน) ถูก **จำได้** แต่ยังไม่เข้าแกนปี
    รอบนี้ — ตกไปที่ G6 ให้คนเห็นแทน (ไม่มีหลักฐานจากแฟ้มจริงว่าใช้รูปแบบเหล่านี้)

    หมายเหตุ: ``ปี ๒๕๗๐`` (เลขไทย) เข้าแกนปีอยู่แล้วตั้งแต่ก่อน G5 เพราะคลาสตัวเลข
    ของ ``re`` และ ``int()`` รับเลขไทย — พฤติกรรมเดิม ไม่ได้เปลี่ยนรอบนี้
    """
    assert parse_year_label("ปี 2570") == 2570
    assert parse_year_label("ปี ๒๕๗๐") == 2570          # พฤติกรรมเดิม
    for raw in ("พ.ศ. 2570", "2570", "ปี 2573 - จบ"):
        assert parse_year_label(raw) is None, raw


def test_resolve_period_columns_skips_single_years():
    header = ["รายการ", "หน่วยนับ", "เริ่มต้น - ปี 2569", "ปี 2570", "ปี 2573 - จบ"]
    cols = resolve_period_columns(header)
    assert sorted(cols) == [2, 4]
    assert cols[2].kind == PERIOD_OPEN_START
    assert cols[4].kind == PERIOD_OPEN_END
