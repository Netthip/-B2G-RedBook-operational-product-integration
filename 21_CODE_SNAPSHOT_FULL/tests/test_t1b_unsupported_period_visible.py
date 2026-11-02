# -*- coding: utf-8 -*-
"""G6 (#14) — fail-visible: คอลัมน์ค่าที่หัวอ่านไม่ออกต้องไม่หายเงียบ

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานสร้างจากโค้ด (``tests/t1b_period_synth.py``)

ก่อนแก้: ``_extract_year_table`` วนเฉพาะคอลัมน์ที่ parse เป็นปีได้ ⇒ คอลัมน์อื่น
ในเขตค่า **ไม่มี record เลย** = silent omission (FC-NVI-01 · RC-D · 3 เซลล์)

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import random

import pytest

import t1b_period_synth as S
from redbook.t1b.compare import F_UNSUPPORTED_PERIOD, MUST_REVIEW, compare
from redbook.t1b.matching import match_records
from redbook.t1b.records import (
    ROW_KIND_UNSUPPORTED_PERIOD,
    ROW_KIND_VALUE,
    UNC_UNSUPPORTED_PERIOD_LABEL,
)


def _sheet(recs):
    return [r for r in recs if r.sheet_name_actual == "โครงการ"]


def test_unreadable_header_column_becomes_one_record_per_cell(tmp_path):
    recs = _sheet(S.records(S.build(tmp_path)))
    unsupported = [r for r in recs if r.row_kind == ROW_KIND_UNSUPPORTED_PERIOD]
    assert sorted(r.cell_ref for r in unsupported) == ["L6", "L7", "L8"]
    for r in unsupported:
        assert r.uncertainty == (UNC_UNSUPPORTED_PERIOD_LABEL,)
        assert r.needs_review
        assert r.raw_value is not None, "ต้องเก็บค่าดิบไว้ให้คนเห็น"
        assert r.value_decimal is None, "ไม่รู้ความหมายของคอลัมน์ ⇒ ห้ามตีความค่า"


def test_raw_header_text_is_carried_when_present(tmp_path):
    headers = dict(S.HEADERS, K="งวดสุดท้าย (ไม่ระบุปี)")
    recs = _sheet(S.records(S.build(tmp_path, headers=headers, extra_column=False)))
    k = [r for r in recs if r.cell_ref and r.cell_ref.startswith("K")]
    assert k and all(r.row_kind == ROW_KIND_UNSUPPORTED_PERIOD for r in k)
    assert all("งวดสุดท้าย" in str(r.raw_header_label) for r in k)


def test_unsupported_reaches_a_must_review_finding_on_both_sides(tmp_path):
    a = S.records(S.build(tmp_path, "XL_FY2570_draft-bill_99999_A.xlsx"))
    b = S.records(S.build(tmp_path, "XL_FY2570_draft-bill_99999_B.xlsx"))
    res = compare(match_records(a, b))
    found = [f for f in res.findings if f.finding_type == F_UNSUPPORTED_PERIOD]
    assert len(found) == 6
    assert F_UNSUPPORTED_PERIOD in MUST_REVIEW
    assert all(f.requires_human_decision for f in found)
    cells = sorted((f.baseline_location or f.current_location).cell for f in found)
    assert cells == ["L6", "L6", "L7", "L7", "L8", "L8"]


def test_the_finding_names_the_raw_header(tmp_path):
    headers = dict(S.HEADERS, K="งวดสุดท้าย")
    a = S.records(S.build(tmp_path, "XL_FY2570_draft-bill_99999_A.xlsx",
                          headers=headers, extra_column=False))
    b = S.records(S.build(tmp_path, "XL_FY2570_draft-bill_99999_B.xlsx",
                          headers=headers, extra_column=False))
    found = [f for f in compare(match_records(a, b)).findings
             if f.finding_type == F_UNSUPPORTED_PERIOD]
    assert found and all("งวดสุดท้าย" in f.detail for f in found)


def test_unreadable_column_does_not_break_the_readable_ones(tmp_path):
    recs = _sheet(S.records(S.build(tmp_path)))
    values = [r for r in recs if r.row_kind == ROW_KIND_VALUE]
    assert len(values) == 3 * 5            # 3 แถว × (ปี 3 + ช่วง 2)


# ══════════════════════════════════════════ invariant — conservation of numeric cells

def _accounted_cells(recs):
    return {r.cell_ref for r in recs
            if r.row_kind in (ROW_KIND_VALUE, ROW_KIND_UNSUPPORTED_PERIOD) and r.cell_ref}


def test_every_numeric_cell_in_the_value_region_has_a_record(tmp_path):
    path = S.build(tmp_path)
    assert S.numeric_cells_in_value_region(path) <= _accounted_cells(
        _sheet(S.records(path)))


_POOL = ["ปี 2570", "ปี 2571", "ปี 2572", "เริ่มต้น - ปี 2569", "ปี 2573 - จบ",
         "ปี 2571 - 2573", "พ.ศ. 2570", "งวดสุดท้าย", "???", "หมายเหตุ", None]


@pytest.mark.parametrize("seed", range(40))
def test_conservation_holds_for_random_header_layouts(tmp_path, seed):
    """property: ไม่ว่าหัวคอลัมน์จะผสมแบบใด เซลล์ตัวเลขทุกเซลล์ต้องมี record

    สุ่มแบบกำหนด seed (ทำซ้ำได้) · บังคับให้มีป้ายปีเดี่ยวอย่างน้อยสองคอลัมน์
    เพื่อให้แถวนั้นเป็นหัวตารางรายปีตามนิยามเดิม (นอกนั้นเป็นอีกเส้นทางหนึ่ง)
    """
    rng = random.Random(seed)
    cols = ["G", "H", "I", "J", "K"]
    labels = rng.sample(["ปี 2570", "ปี 2571", "ปี 2572"], 2) + [
        rng.choice(_POOL) for _ in range(3)]
    rng.shuffle(labels)
    headers = {c: t for c, t in zip(cols, labels) if t is not None}
    path = S.build(tmp_path, headers=headers, extra_column=rng.random() < 0.5)
    numeric = S.numeric_cells_in_value_region(path)
    accounted = _accounted_cells(_sheet(S.records(path)))
    missing = numeric - accounted
    assert not missing, f"seed={seed} headers={headers} หายเงียบ: {sorted(missing)}"
