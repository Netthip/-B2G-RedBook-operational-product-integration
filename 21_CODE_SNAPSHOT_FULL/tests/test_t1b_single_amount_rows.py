# -*- coding: utf-8 -*-
"""G1 (#14) — แถว "ป้าย + ค่าเดี่ยว + หน่วย" และบทบาทเชิงเวลา (RC-E)

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานสร้างจากโค้ด ชื่อ/ยอดแต่งขึ้นทั้งหมด

ลายเซ็นเชิงโครงสร้าง (ไม่ใช้ชื่อชีต): ตัวเลขหนึ่งช่อง · หน่วยที่รู้จักทางขวา ·
ป้ายข้อความหนึ่งช่องทางซ้าย — ไม่เข้า ⇒ คง UNMAPPED ตามเดิม

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from decimal import Decimal

import openpyxl
import pytest

from redbook.adapters.ao_workbook import AOWorkbookAdapter
from redbook.t1b.compare import (
    F_AMBIGUOUS,
    F_AMOUNT_DECREASED,
    FLAG_SINGLE_AMOUNT_YEAR_DIFFERS,
    compare,
)
from redbook.t1b.matching import match_records
from redbook.t1b.records import (
    AXIS_SINGLE_AMOUNT,
    ROW_KIND_UNMAPPED,
    UNC_SINGLE_AMOUNT_KEY_AMBIGUOUS,
    UNC_SINGLE_AMOUNT_YEAR_UNRESOLVED,
)
from redbook.t1b.rollup import check_rollups
from redbook.t1b.temporal import (
    ROLE_FROM_LABEL,
    ROLE_FROM_PARENT_HEADING,
    ROLE_LIFETIME_CEILING,
)


def build(tmp_path, name="XL_FY2570_draft-bill_99999_A.xlsx", *, year=2570,
          values=None, extra=None, cover=True):
    """ชีตสรุป: บล็อก 6.1 (ค่าเดี่ยว) เหนือตารางหมวด · ชีตโครงการ: วงเงินตลอดอายุ + ตารางรายปี"""
    v = {"C3": 300.0, "C4": 200.0, "C5": 100.0, "F8": 900.0, "F9": 900.0}
    v.update(values or {})
    wb = openpyxl.Workbook()
    ws0 = wb.active
    if cover:
        ws0.title = "ปก"
        ws0["A2"], ws0["A3"], ws0["A5"] = "กระทรวงทดสอบ", "หน่วยงานทดสอบ", f"ปี {year}"
        ws = wb.create_sheet("สรุป")
    else:
        ws = ws0
        ws.title = "สรุป"
    ws["A1"] = "6. สรุปงบประมาณทดสอบ"
    ws["A2"] = "6.1 จำแนกตามลักษณะรายจ่าย"
    for r, label in ((3, "งบประมาณรายจ่าย"), (4, "รายจ่ายประจำ"), (5, "รายจ่ายลงทุน")):
        ws[f"A{r}"], ws[f"C{r}"], ws[f"E{r}"] = label, v[f"C{r}"], "บาท"
        ws.merge_cells(f"C{r}:D{r}")      # ตามแฟ้มจริง: เซลล์ค่าผสานถึงก่อนเซลล์หน่วย
    # ตารางหมวดอยู่ล่างสุด — แถว 6–16 เว้นไว้ให้เทสต์เติมแถวค่าเดี่ยวนอกตาราง
    ws["G17"] = "หน่วย : ล้านบาท"
    ws["A18"] = "แผนงาน"
    for col, text in zip("BCDE", ("งบบุคลากร", "งบดำเนินงาน", "งบลงทุน", "รวม")):
        ws[f"{col}18"] = text
    ws["A19"] = "รวมทั้งสิ้น"
    for col in "BCDE":
        ws[f"{col}19"] = 1.0

    pj = wb.create_sheet("โครงการ")
    pj["A1"] = "7.3 แผนงานยุทธศาสตร์ทดสอบ"
    pj["A2"] = "7.3.1 โครงการทดสอบ"
    pj["B8"], pj["F8"], pj["H8"] = "7.3.1.4 วงเงินทั้งสิ้นของโครงการ", v["F8"], "บาท"
    pj["B9"], pj["F9"], pj["H9"] = "- เงินงบประมาณ", v["F9"], "บาท"
    pj.merge_cells("F8:G8")
    pj.merge_cells("F9:G9")
    pj["A12"], pj["F12"] = "รายการ", "หน่วยนับ"
    pj["G13"], pj["H13"] = "ปี 2570", "ปี 2571"
    pj["A14"], pj["F14"], pj["G14"], pj["H14"] = "เงินงบประมาณ", "ล้านบาท", 1.0, 2.0
    for cell, val in (extra or {}).items():
        sheet, ref = cell.split("!")
        wb[sheet][ref] = val
    path = tmp_path / name
    wb.save(path)
    wb.close()
    return path


def recs(path):
    return [e.canonical_record for e in AOWorkbookAdapter().extract(path)]


def singles(rs):
    return {r.cell_ref: r for r in rs if r.comparison_axis == AXIS_SINGLE_AMOUNT}


# ══════════════════════════════════════════ ลายเซ็น

def test_labelled_single_amount_rows_become_comparable_records(tmp_path):
    s = singles(recs(build(tmp_path)))
    assert sorted(s) == ["C3", "C4", "C5", "F8", "F9"]
    for r in s.values():
        assert r.declared_unit and r.is_monetary
        assert r.value_decimal is not None
        assert r.fiscal_year is None and r.category_table_fiscal_year == 2570
        assert r.axis_valid and not r.needs_review
    assert s["C3"].value_decimal == Decimal("300")


@pytest.mark.parametrize("extra, cell, why", [
    ({"สรุป!F3": 5.0}, "C3", "ตัวเลขสองช่อง"),
    ({"สรุป!E4": None}, "C4", "ไม่มีหน่วย"),
    ({"สรุป!E4": "หมายเหตุ"}, "C4", "เซลล์ขวาไม่ใช่หน่วยที่รู้จัก"),
    ({"สรุป!B5": "ป้ายที่สอง"}, "C5", "ป้ายสองช่อง"),
])
def test_rows_outside_the_signature_stay_unmapped(tmp_path, extra, cell, why):
    rs = recs(build(tmp_path, extra=extra))
    assert cell not in singles(rs), why
    row = int(cell[1:])
    assert any(r.row_kind == ROW_KIND_UNMAPPED and r.sheet_name_actual == "สรุป"
               and r.row_index == row for r in rs), f"{why}: ต้องยังมองเห็น"


def test_unit_after_an_unmerged_gap_is_not_the_next_cell(tmp_path):
    """REVIEW ของ Bo (#14) — "เซลล์ถัดไป" ห้ามข้ามเซลล์ว่างที่ไม่ได้ผสาน"""
    path = build(tmp_path)
    wb = openpyxl.load_workbook(path)
    wb["สรุป"].unmerge_cells("C3:D3")
    wb.save(path)
    rs = recs(path)
    assert "C3" not in singles(rs)
    assert any(r.row_kind == ROW_KIND_UNMAPPED and r.sheet_name_actual == "สรุป"
               and r.row_index == 3 for r in rs)


def test_unit_directly_adjacent_is_the_next_cell(tmp_path):
    extra = {"สรุป!A11": "ยอดทดสอบติดหน่วย", "สรุป!C11": 7.0, "สรุป!D11": "บาท"}
    assert "C11" in singles(recs(build(tmp_path, extra=extra)))


def test_sheet_name_is_not_part_of_the_rule(tmp_path):
    path = build(tmp_path)
    wb = openpyxl.load_workbook(path)
    wb["สรุป"].title = "ชีตชื่ออื่น"
    wb.save(path)
    assert sorted(singles(recs(path))) == ["C3", "C4", "C5", "F8", "F9"]


def test_hierarchy_separates_same_label_under_different_headings(tmp_path):
    extra = {"สรุป!A11": "6.3 หัวข้อทดสอบ", "สรุป!A12": "- เงินงบประมาณ",
             "สรุป!C12": 7.0, "สรุป!D12": "บาท",
             "สรุป!A13": "6.4 หัวข้อทดสอบสอง", "สรุป!A14": "- เงินงบประมาณ",
             "สรุป!C14": 8.0, "สรุป!D14": "บาท"}
    s = singles(recs(build(tmp_path, extra=extra)))
    assert s["C12"].key != s["C14"].key
    assert not any(UNC_SINGLE_AMOUNT_KEY_AMBIGUOUS in r.uncertainty for r in s.values())


def test_colliding_keys_are_flagged_not_collapsed(tmp_path):
    extra = {"สรุป!A11": "งบประมาณรายจ่าย", "สรุป!C11": 7.0, "สรุป!D11": "บาท"}
    rs = recs(build(tmp_path, extra=extra))
    s = singles(rs)
    assert UNC_SINGLE_AMOUNT_KEY_AMBIGUOUS in s["C3"].uncertainty
    assert UNC_SINGLE_AMOUNT_KEY_AMBIGUOUS in s["C11"].uncertainty
    assert s["C3"].needs_review


def test_missing_document_year_blocks_matching(tmp_path):
    s = singles(recs(build(tmp_path, cover=False)))
    assert s and all(UNC_SINGLE_AMOUNT_YEAR_UNRESOLVED in r.uncertainty
                     and r.needs_review for r in s.values())


# ══════════════════════════════════════════ เทียบสองฝั่ง

def _compare(tmp_path, **kw_b):
    a = recs(build(tmp_path, "XL_FY2570_draft-bill_99999_A.xlsx"))
    b = recs(build(tmp_path, "XL_FY2570_draft-bill_99999_B.xlsx", **kw_b))
    m = match_records(a, b)
    assert m.accounted() == len(a) + len(b)
    return compare(m)


def test_a_change_is_found_at_the_single_amount_cell(tmp_path):
    res = _compare(tmp_path, values={"C5": 50.0})
    dec = [f for f in res.findings if f.finding_type == F_AMOUNT_DECREASED]
    assert len(dec) == 1
    assert dec[0].comparison_axis == AXIS_SINGLE_AMOUNT
    assert dec[0].baseline_location.cell == dec[0].current_location.cell == "C5"
    assert not dec[0].requires_human_decision


def test_documents_of_different_years_are_flagged(tmp_path):
    res = _compare(tmp_path, year=2571)
    flagged = [f for f in res.findings if FLAG_SINGLE_AMOUNT_YEAR_DIFFERS in f.flags]
    assert len(flagged) == 5 and all(f.requires_human_decision for f in flagged)


def test_ambiguous_single_amounts_are_not_auto_matched(tmp_path):
    extra = {"สรุป!A11": "งบประมาณรายจ่าย", "สรุป!C11": 7.0, "สรุป!D11": "บาท"}
    a = recs(build(tmp_path, "XL_FY2570_draft-bill_99999_A.xlsx", extra=extra))
    b = recs(build(tmp_path, "XL_FY2570_draft-bill_99999_B.xlsx", extra=extra))
    res = compare(match_records(a, b))
    amb = [f for f in res.findings if f.finding_type == F_AMBIGUOUS
           and (f.baseline_location or f.current_location).cell in ("C3", "C11")]
    assert len(amb) == 4


# ══════════════════════════════════════════ บทบาทเชิงเวลา (RC-E)

def test_lifetime_ceiling_role_from_label_and_inherited_by_bullet(tmp_path):
    s = singles(recs(build(tmp_path)))
    assert (s["F8"].amount_role, s["F8"].amount_role_source) == (
        ROLE_LIFETIME_CEILING, ROLE_FROM_LABEL)
    assert (s["F9"].amount_role, s["F9"].amount_role_source) == (
        ROLE_LIFETIME_CEILING, ROLE_FROM_PARENT_HEADING)
    assert s["C3"].amount_role == ""


def test_role_reaches_the_finding(tmp_path):
    res = _compare(tmp_path, values={"F8": 800.0})
    dec = [f for f in res.findings if f.finding_type == F_AMOUNT_DECREASED]
    assert len(dec) == 1 and dec[0].amount_role == ROLE_LIFETIME_CEILING


def test_yearly_rollups_never_include_single_amounts(tmp_path):
    """🔴 วงเงินตลอดอายุโครงการต้องไม่ถูกบวกรวมกับยอดปี — ผลรวมรายปีไม่เปลี่ยน"""
    src = dict(source_file="synthetic.xlsx", source_hash="0" * 64)
    base = check_rollups(recs(build(tmp_path, "XL_FY2570_draft-bill_99999_A.xlsx")), **src)
    bumped = check_rollups(recs(build(tmp_path, "XL_FY2570_draft-bill_99999_B.xlsx",
                                      values={"F8": 9_999_999.0, "F9": 9_999_999.0})),
                           **src)
    assert base.summary() == bumped.summary()
    for chk in bumped.checks:
        for comp in chk.components:
            assert comp.cell not in ("F8", "F9", "C3", "C4", "C5") or \
                comp.sheet not in ("โครงการ", "สรุป")


# ══════════════════════════════════════════ แฟ้มจริง (development เท่านั้น)

from test_t1b_extract import ALL_FILES, SOURCE_DIR, needs_sources  # noqa: E402


@needs_sources
@pytest.mark.parametrize("name", ALL_FILES)
def test_no_rollup_component_is_a_single_amount_in_development_workbooks(name):
    """ชุดสังเคราะห์มี check รายปีน้อย — ยืนยันซ้ำกับแฟ้มจริงที่มี check หลายสิบรายการ"""
    path = SOURCE_DIR / name
    rs = recs(path)
    single_cells = {(r.sheet_name_actual, r.cell_ref) for r in rs
                    if r.comparison_axis == AXIS_SINGLE_AMOUNT}
    result = check_rollups(rs, source_file=name, source_hash="0" * 64)
    used = {(c.sheet, c.cell) for chk in result.checks
            for c in chk.components + chk.targets}
    assert result.checks
    assert not (used & single_cells)
