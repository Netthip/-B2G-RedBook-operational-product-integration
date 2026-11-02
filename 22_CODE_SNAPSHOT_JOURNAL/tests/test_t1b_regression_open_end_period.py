# -*- coding: utf-8 -*-
"""G5 (#14) — regression ของตารางที่มีคอลัมน์เปิดหัว/เปิดท้าย

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานสร้างจากโค้ด (``tests/t1b_period_synth.py``)

เคสต้นเรื่อง (FC-NVI-01 · RC-D): ค่าในคอลัมน์ ``ปี xxxx - จบ`` เปลี่ยน แต่เอนจิน
ไม่มี record ของคอลัมน์นั้นเลย ⇒ การเปลี่ยนหายเงียบ

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from decimal import Decimal

import t1b_period_synth as S
from redbook.t1b.compare import (
    F_AMOUNT_DECREASED,
    F_AMOUNT_UNCHANGED,
    F_PERIOD_LABEL_CHANGED,
    F_ROW_ADDED,
    F_ROW_REMOVED,
    MUST_REVIEW,
    compare,
)
from redbook.t1b.matching import match_records
from redbook.t1b.records import AXIS_PERIOD_RANGE


def _pair(tmp_path, *, base=None, curr=None, base_headers=None, curr_headers=None):
    a = S.records(S.build(tmp_path, "XL_FY2570_draft-bill_99999_A.xlsx",
                          values=base, headers=base_headers, extra_column=False))
    b = S.records(S.build(tmp_path, "XL_FY2570_draft-bill_99999_B.xlsx",
                          values=curr, headers=curr_headers, extra_column=False))
    m = match_records(a, b)
    assert m.accounted() == len(a) + len(b), "ทุก record ต้องถูกจัดกลุ่ม"
    return m, compare(m)


def test_a_change_only_in_the_open_end_column_is_found_at_that_cell(tmp_path):
    _, res = _pair(tmp_path, curr={("เงินงบประมาณ", "K"): 1.0})
    dec = [f for f in res.findings if f.finding_type == F_AMOUNT_DECREASED]
    assert len(dec) == 1
    f = dec[0]
    assert f.comparison_axis == AXIS_PERIOD_RANGE
    assert f.period_label == "ปี 2573-จบ"
    assert f.fiscal_year is None
    assert f.baseline_location.cell == f.current_location.cell == "K7"
    assert f.difference < Decimal(0)


def test_open_start_column_is_compared_too(tmp_path):
    _, res = _pair(tmp_path)
    g = [f for f in res.findings
         if f.baseline_location and f.baseline_location.cell
         and f.baseline_location.cell.startswith("G")]
    assert len(g) == 3 and all(f.finding_type == F_AMOUNT_UNCHANGED for f in g)


def test_dash_and_space_variants_still_match(tmp_path):
    curr_headers = dict(S.HEADERS, K="ปี 2573–จบ", G="เริ่มต้น–ปี  2569")
    _, res = _pair(tmp_path, curr_headers=curr_headers,
                   curr={("เงินงบประมาณ", "K"): 1.0})
    assert sum(f.finding_type == F_AMOUNT_DECREASED for f in res.findings) == 1
    assert not any(f.finding_type == F_PERIOD_LABEL_CHANGED for f in res.findings)


def test_same_start_year_different_period_is_not_matched(tmp_path):
    """🔴 ``ปี 2573 - จบ`` กับ ``ปี 2573 - 2575`` ปีเริ่มต้นตรงกัน แต่คนละช่วงเวลา"""
    curr_headers = dict(S.HEADERS, K="ปี 2573 - 2575")
    m, res = _pair(tmp_path, curr_headers=curr_headers)
    assert not any(p.baseline.comparison_axis == AXIS_PERIOD_RANGE
                   and p.baseline.period_label != p.current.period_label
                   for p in m.matched)
    changed = [f for f in res.findings if f.finding_type == F_PERIOD_LABEL_CHANGED]
    assert len(changed) == 6                  # 3 แถว × 2 ฝั่ง
    assert F_PERIOD_LABEL_CHANGED in MUST_REVIEW
    for f in changed:
        assert "ปี 2573 - จบ" in f.detail and "ปี 2573 - 2575" in f.detail, \
            "ต้องเห็นป้ายดิบทั้งสองฝั่ง"


def test_a_relabelled_period_is_not_reported_as_rows_added_or_removed(tmp_path):
    curr_headers = dict(S.HEADERS, K="ปี 2574 - จบ")
    _, res = _pair(tmp_path, curr_headers=curr_headers)
    k_cells = [f for f in res.findings
               if f.finding_type in (F_ROW_ADDED, F_ROW_REMOVED)
               and ((f.baseline_location and f.baseline_location.cell == "K6")
                    or (f.current_location and f.current_location.cell == "K6"))]
    assert not k_cells


def test_a_period_column_that_exists_on_one_side_only_is_still_visible(tmp_path):
    """ป้ายมีฝั่งเดียว (ไม่มีคู่ในแถวเดียวกัน) ⇒ เพิ่ม/ลบตามเดิม — ไม่หาย"""
    curr_headers = {k: v for k, v in S.HEADERS.items() if k != "K"}
    _, res = _pair(tmp_path, curr_headers=curr_headers)
    removed = [f for f in res.findings if f.finding_type == F_ROW_REMOVED
               and f.comparison_axis == AXIS_PERIOD_RANGE]
    assert len(removed) == 3
