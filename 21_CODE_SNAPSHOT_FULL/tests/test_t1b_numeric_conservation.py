# -*- coding: utf-8 -*-
"""invariant (#14) — conservation of numeric cells

**ทุกเซลล์ตัวเลขในสมุดงานต้องมี record อย่างน้อยหนึ่ง** — ระดับเซลล์
(``VALUE`` · ``UNSUPPORTED_PERIOD`` · ``UNSUPPORTED_COLUMN``) หรือระดับแถว (``UNMAPPED``)

นับเซลล์จากไฟล์ตรง ๆ ด้วย openpyxl — **อิสระจากเอนจิน** แล้วเทียบกับ record

🔴 ส่วนสังเคราะห์: **SYNTHETIC TEST FIXTURE** สร้างจากโค้ด ไม่มีข้อมูลจริง
🔴 ส่วนแฟ้มจริง: ใช้เฉพาะแฟ้มที่ชุดทดสอบเดิมเปิดอยู่แล้ว (``ALL_FILES``) —
   ไม่เปิดแฟ้มใหม่ที่อาจถูกเลือกเป็นชุดประเมินสุดท้าย

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import random

import openpyxl
import pytest

from redbook.adapters.ao_workbook import AOWorkbookAdapter
from redbook.t1b.compare import (
    F_UNMAPPED,
    F_UNSUPPORTED_COLUMN,
    compare,
)
from redbook.t1b.matching import match_records
from redbook.t1b.records import (
    ROW_KIND_UNMAPPED,
    ROW_KIND_UNSUPPORTED_COLUMN,
    UNC_NUMERIC_CELL_NOT_ACCOUNTED,
)
from test_t1b_extract import ALL_FILES, SOURCE_DIR, needs_sources

CELL_KINDS = ("VALUE", "UNSUPPORTED_PERIOD", "UNSUPPORTED_COLUMN")


def _numeric(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def uncovered(path):
    """เซลล์ตัวเลขที่ไม่มี record ครอบ — คืน ``[(ชีต, เซลล์)]``"""
    recs = [e.canonical_record for e in AOWorkbookAdapter().extract(path)]
    cells = {(r.sheet_name_actual, r.cell_ref) for r in recs
             if r.cell_ref and r.row_kind in CELL_KINDS}
    rows = {(r.sheet_name_actual, r.row_index) for r in recs
            if r.row_kind == ROW_KIND_UNMAPPED}
    wb = openpyxl.load_workbook(path, data_only=True)
    out = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if not _numeric(c.value):
                    continue
                if (ws.title, c.coordinate) in cells or (ws.title, c.row) in rows:
                    continue
                out.append((ws.title, c.coordinate))
    wb.close()
    return out


# ══════════════════════════════════════════ สังเคราะห์

def _category_workbook(tmp_path, name="XL_FY2570_draft-bill_99999_C.xlsx", *,
                       helper_cols=("H", "I"), number_in_header=False, seed=None):
    """ตารางจำแนกตามงบรายจ่าย + คอลัมน์ช่วยคำนวณที่ไม่มีหัว + (ถ้าเลือก) ตัวเลขในแถวหัว"""
    rng = random.Random(seed)
    wb = openpyxl.Workbook()
    cover = wb.active
    cover.title = "ปก"
    cover["A2"], cover["A3"], cover["A5"] = "กระทรวงทดสอบ", "หน่วยงานทดสอบ", "ปี 2570"
    ws = wb.create_sheet("สรุป")
    ws["A1"] = "6. สรุปงบประมาณทดสอบ"
    ws["G3"] = "หน่วย : บาท"
    ws["A4"] = "แผนงาน"
    for col, text in zip("BCDEFG", ("งบบุคลากร", "งบดำเนินงาน", "งบลงทุน",
                                    "งบเงินอุดหนุน", "งบรายจ่ายอื่น", "รวม")):
        ws[f"{col}4"] = text
    if number_in_header:
        ws["J4"] = 1.0
    for r, label in enumerate(("รวมทั้งสิ้น", "1. แผนงานทดสอบ", "2. แผนงานทดสอบสอง"), 5):
        ws[f"A{r}"] = label
        for col in "BCDEFG":
            ws[f"{col}{r}"] = float(rng.randint(1, 9) * 10 if seed is not None else 10)
        for col in helper_cols:
            ws[f"{col}{r}"] = 1.0
    path = tmp_path / name
    wb.save(path)
    wb.close()
    return path


def test_headerless_helper_columns_of_a_category_table_are_visible(tmp_path):
    path = _category_workbook(tmp_path)
    recs = [e.canonical_record for e in AOWorkbookAdapter().extract(path)]
    helper = [r for r in recs if r.row_kind == ROW_KIND_UNSUPPORTED_COLUMN]
    assert sorted(r.cell_ref for r in helper) == ["H5", "H6", "H7", "I5", "I6", "I7"]
    assert all(r.needs_review and r.value_decimal is None for r in helper)
    assert uncovered(path) == []


def test_numbers_in_a_header_row_are_caught_by_the_safety_net(tmp_path):
    path = _category_workbook(tmp_path, number_in_header=True)
    recs = [e.canonical_record for e in AOWorkbookAdapter().extract(path)]
    net = [r for r in recs if UNC_NUMERIC_CELL_NOT_ACCOUNTED in r.uncertainty]
    assert [r.row_index for r in net] == [4]
    assert net[0].row_kind == ROW_KIND_UNMAPPED
    assert uncovered(path) == []


def test_both_reach_findings_that_require_a_human(tmp_path):
    a = _category_workbook(tmp_path, "XL_FY2570_draft-bill_99999_A.xlsx",
                           number_in_header=True)
    b = _category_workbook(tmp_path, "XL_FY2570_draft-bill_99999_B.xlsx",
                           number_in_header=True)
    ad = AOWorkbookAdapter()
    res = compare(match_records([e.canonical_record for e in ad.extract(a)],
                                [e.canonical_record for e in ad.extract(b)]))
    kinds = {f.finding_type for f in res.findings if f.requires_human_decision}
    assert {F_UNSUPPORTED_COLUMN, F_UNMAPPED} <= kinds


@pytest.mark.parametrize("seed", range(30))
def test_conservation_holds_for_random_category_layouts(tmp_path, seed):
    """property: คอลัมน์ช่วย/ตัวเลขในแถวหัวสุ่มแบบกำหนด seed — ต้องไม่มีเซลล์ตกหล่น"""
    rng = random.Random(seed)
    helpers = tuple(c for c in "HIJK" if rng.random() < 0.5)
    path = _category_workbook(tmp_path, helper_cols=helpers,
                              number_in_header=rng.random() < 0.5, seed=seed)
    assert uncovered(path) == [], f"seed={seed} helpers={helpers}"


# ══════════════════════════════════════════ แฟ้มจริง (development เท่านั้น)

@needs_sources
@pytest.mark.parametrize("name", ALL_FILES)
def test_no_numeric_cell_is_silently_dropped_in_development_workbooks(name):
    missing = uncovered(SOURCE_DIR / name)
    assert missing == [], f"{name}: เซลล์ตัวเลขไม่มี record {len(missing)} เซลล์"
