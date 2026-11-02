# -*- coding: utf-8 -*-
"""G2 (#14) — ผูกบล็อกของชีตประกอบกับชีตหลักด้วยชื่อ

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานสร้างจากโค้ด ชื่อ/ยอดแต่งขึ้นทั้งหมด

* ผูกด้วยชื่อ ไม่ใช่เลขข้อ ชื่อชีต หรือลำดับชีต
* ผูกได้เมื่อพบคู่หนึ่งเดียว · ไม่พบ/พบหลายแห่ง ⇒ record ยังออก + ธง ไม่ collapse
* แถวที่ไม่เข้าลายเซ็น G1 คง UNMAPPED แต่มีชื่อบล็อกในคีย์

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import openpyxl
import pytest

from redbook.adapters.ao_workbook import AOWorkbookAdapter
from redbook.t1b.compare import F_AMBIGUOUS, F_AMOUNT_DECREASED, compare
from redbook.t1b.matching import match_records
from redbook.t1b.records import (
    AXIS_SINGLE_AMOUNT,
    ROW_KIND_UNMAPPED,
    UNC_PARENT_LINK_UNRESOLVED,
    UNC_PARENT_LINK_VIA_LINE_BREAK_JOIN,
    UNC_SINGLE_AMOUNT_KEY_AMBIGUOUS,
    UNC_SUPPORTING_LAYOUT_NOT_MAPPED,
)
from redbook.t1b.supporting import (
    KIND_OUTPUT,
    KIND_PERSONNEL,
    KIND_PROJECT,
    SHEET_ROLE_SUPPORTING_DETAIL,
    NameIndex,
    parse_block,
)
from redbook.t1b.temporal import ROLE_COMMITMENT_SCHEDULE, ROLE_LIFETIME_CEILING

PROJECT = "โครงการทดสอบความร่วมมือระหว่างประเทศ"


def build(tmp_path, name="XL_FY2570_draft-bill_99999_A.xlsx", *, title_raw=None,
          block_name=PROJECT, second_plan_same_name=False, values=None,
          duplicate_support=False, support_sheet="ย1"):
    v = {"E2": 500.0, "B4": 900.0, "B5": 300.0}
    v.update(values or {})
    wb = openpyxl.Workbook()
    cover = wb.active
    cover.title = "ปก"
    cover["A2"], cover["A3"], cover["A5"] = "กระทรวงทดสอบ", "หน่วยงานทดสอบ", "ปี 2570"

    def plan_sheet(sheet_name, number, project_title):
        ws = wb.create_sheet(sheet_name)
        ws["A1"] = f"{number} แผนงานยุทธศาสตร์ทดสอบ{number}"
        ws["B2"] = project_title
        ws["B3"] = f"{number}.1.1 วัตถุประสงค์"
        ws["A6"], ws["F6"] = "รายการ", "หน่วยนับ"
        ws["G7"], ws["H7"] = "ปี 2570", "ปี 2571"
        ws["A8"], ws["F8"], ws["G8"], ws["H8"] = "เงินงบประมาณ", "ล้านบาท", 1.0, 2.0

    plan_sheet("แผน", "7.3", title_raw or f"7.3.1 โครงการที่ 1 : {PROJECT}")
    if second_plan_same_name:
        plan_sheet("แผนสอง", "7.4", f"7.4.1 โครงการที่ 1 : {PROJECT}")

    def support(sheet_name):
        ws = wb.create_sheet(sheet_name)
        ws["A1"] = "รายละเอียดงบประมาณจำแนกตามงบรายจ่าย"
        ws["A2"], ws["E2"], ws["F2"] = f"โครงการ : {block_name}", v["E2"], "บาท"
        ws["A3"], ws["D3"], ws["E3"], ws["F3"] = "1. งบเงินอุดหนุน", 1.0, 500.0, "บาท"
        ws["A4"], ws["B4"], ws["E4"] = "วงเงินทั้งสิ้น", v["B4"], "บาท"
        ws["A5"], ws["B5"], ws["E5"] = "ปี 2568 ตั้งงบประมาณ", v["B5"], "บาท"
        ws.merge_cells("B4:D4")
        ws.merge_cells("B5:D5")

    support(support_sheet)
    if duplicate_support:
        support(support_sheet + "สำเนา")
    path = tmp_path / name
    wb.save(path)
    wb.close()
    return path


def recs(path):
    return [e.canonical_record for e in AOWorkbookAdapter().extract(path)]


def support_recs(rs):
    return [r for r in rs if r.key.sheet_role == SHEET_ROLE_SUPPORTING_DETAIL]


# ══════════════════════════════════════════ ตัวแยกหัวบล็อก

@pytest.mark.parametrize("raw, kind, name", [
    ("ผลผลิต : ผลผลิตทดสอบ", KIND_OUTPUT, "ผลผลิตทดสอบ"),
    ("โครงการ : โครงการทดสอบ", KIND_PROJECT, "โครงการทดสอบ"),
    ("โครงการ：โครงการทดสอบ", KIND_PROJECT, "โครงการทดสอบ"),
    ("รายการบุคลากรภาครัฐ", KIND_PERSONNEL, "รายการบุคลากรภาครัฐ"),
])
def test_block_headers(raw, kind, name):
    b = parse_block(raw)
    assert (b.kind, b.name) == (kind, name)


@pytest.mark.parametrize("raw", ["1. งบเงินอุดหนุน", "ผลผลิตทดสอบ", "7.3.1 โครงการที่ 1 : x", None, 5])
def test_non_block_rows(raw):
    assert parse_block(raw) is None


def test_index_ignores_numbers_with_fewer_than_three_levels():
    idx = NameIndex()
    idx.add_heading("7.3 โครงการ : ไม่ควรถูกนับ", "SECTION_07_PLAN", "แผน")
    assert not idx.bind(parse_block("โครงการ : ไม่ควรถูกนับ")).bound


# ══════════════════════════════════════════ การผูก

def test_block_binds_by_name_and_records_carry_the_context(tmp_path):
    rs = support_recs(recs(build(tmp_path)))
    assert rs
    for r in rs:
        assert r.key.section_title_norm == f"โครงการ : {PROJECT}"
        assert r.key.parent_plan_norm, "ต้องผูกกับบริบทของชีตหลักได้"
        assert UNC_PARENT_LINK_UNRESOLVED not in r.uncertainty
    singles = {r.cell_ref: r for r in rs if r.comparison_axis == AXIS_SINGLE_AMOUNT}
    assert sorted(singles) == ["B4", "B5", "E2"]
    assert singles["B4"].amount_role == ROLE_LIFETIME_CEILING
    assert singles["B5"].amount_role == ROLE_COMMITMENT_SCHEDULE


def test_row_with_several_numbers_stays_unmapped_but_keeps_block_context(tmp_path):
    """G1 เดิม: ตัวเลขมากกว่าหนึ่งช่อง ⇒ คง UNMAPPED (ไม่เปลี่ยนกติกาในขั้นนี้)"""
    rs = support_recs(recs(build(tmp_path)))
    row3 = [r for r in rs if r.row_index == 3]
    assert len(row3) == 1 and row3[0].row_kind == ROW_KIND_UNMAPPED
    assert UNC_SUPPORTING_LAYOUT_NOT_MAPPED in row3[0].uncertainty
    assert row3[0].key.section_title_norm == f"โครงการ : {PROJECT}"


def test_sheet_name_and_order_are_not_used(tmp_path):
    a = {r.key for r in support_recs(recs(build(tmp_path, support_sheet="ย1")))}
    b = {r.key for r in support_recs(recs(build(tmp_path, "XL_FY2570_draft-bill_99999_B.xlsx",
                                                support_sheet="ชีตอื่นเลย")))}
    assert a == b


def test_wrapped_title_binds_only_via_line_break_rule_and_says_so(tmp_path):
    wrapped = f"7.3.1 โครงการที่ 1 : {PROJECT[:20]}\n{PROJECT[20:]}"
    rs = support_recs(recs(build(tmp_path, title_raw=wrapped)))
    assert all(UNC_PARENT_LINK_UNRESOLVED not in r.uncertainty for r in rs)
    assert all(UNC_PARENT_LINK_VIA_LINE_BREAK_JOIN in r.uncertainty for r in rs)
    assert all(not r.needs_review for r in rs if r.comparison_axis == AXIS_SINGLE_AMOUNT
               and r.key.section_title_norm)


def test_unknown_name_is_unresolved_not_dropped(tmp_path):
    rs = support_recs(recs(build(tmp_path, block_name="โครงการที่ไม่มีในชีตหลัก")))
    assert rs, "record ต้องยังออก"
    assert all(UNC_PARENT_LINK_UNRESOLVED in r.uncertainty for r in rs)
    assert all(r.key.parent_plan_norm == "" for r in rs)
    assert all(r.needs_review for r in rs)


def test_same_name_under_two_plans_is_unresolved_not_collapsed(tmp_path):
    rs = support_recs(recs(build(tmp_path, second_plan_same_name=True)))
    assert rs and all(UNC_PARENT_LINK_UNRESOLVED in r.uncertainty for r in rs)


def test_same_block_on_two_supporting_sheets_is_flagged_workbook_wide(tmp_path):
    rs = support_recs(recs(build(tmp_path, duplicate_support=True)))
    singles = [r for r in rs if r.comparison_axis == AXIS_SINGLE_AMOUNT]
    assert len(singles) == 6
    assert all(UNC_SINGLE_AMOUNT_KEY_AMBIGUOUS in r.uncertainty for r in singles)


def test_sheet_without_block_header_keeps_old_behaviour(tmp_path):
    path = build(tmp_path)
    wb = openpyxl.load_workbook(path)
    wb["ย1"]["A2"] = "หัวที่ไม่ใช่บล็อก"
    wb.save(path)
    rs = [r for r in recs(path) if r.sheet_name_actual == "ย1"]
    assert rs and all(r.row_kind == ROW_KIND_UNMAPPED for r in rs)
    assert not support_recs(rs)


# ══════════════════════════════════════════ เทียบสองฝั่ง

def test_bound_change_is_found_at_the_supporting_cell(tmp_path):
    a = recs(build(tmp_path, "XL_FY2570_draft-bill_99999_A.xlsx"))
    b = recs(build(tmp_path, "XL_FY2570_draft-bill_99999_B.xlsx", values={"E2": 400.0}))
    res = compare(match_records(a, b))
    dec = [f for f in res.findings if f.finding_type == F_AMOUNT_DECREASED]
    assert len(dec) == 1 and dec[0].baseline_location.cell == "E2"


def test_unresolved_blocks_are_never_auto_matched(tmp_path):
    kw = dict(block_name="โครงการที่ไม่มีในชีตหลัก")
    a = recs(build(tmp_path, "XL_FY2570_draft-bill_99999_A.xlsx", **kw))
    b = recs(build(tmp_path, "XL_FY2570_draft-bill_99999_B.xlsx", values={"E2": 400.0}, **kw))
    res = compare(match_records(a, b))
    assert not [f for f in res.findings if f.finding_type == F_AMOUNT_DECREASED]
    amb = [f for f in res.findings if f.finding_type == F_AMBIGUOUS
           and (f.baseline_location or f.current_location).cell == "E2"]
    assert len(amb) == 2


# ══════════════════════════════════════════ #19 — หัวข้อชื่อซ้ำใต้บริบทเดียวกัน

def test_issue19_two_same_name_headings_in_one_context_do_not_bind():
    """reproducer จากใบ #19 (สังเคราะห์) — เดิม set ยุบสอง occurrence เหลือหนึ่ง ⇒ bound=True"""
    idx = NameIndex()
    idx.add_heading("7.3.1 โครงการที่ 1 : Demo", "SECTION_07_PLAN", "Plan A")
    idx.add_heading("7.3.2 โครงการที่ 2 : Demo", "SECTION_07_PLAN", "Plan A")
    result = idx.bind(parse_block("โครงการ : Demo"))
    assert not result.bound
    assert result.candidates == 2


def test_issue19_same_ambiguity_via_line_break_fallback():
    idx = NameIndex()
    idx.add_heading("7.3.1 โครงการที่ 1 : De\nmo", "SECTION_07_PLAN", "Plan A")
    idx.add_heading("7.3.2 โครงการที่ 2 : D\nemo", "SECTION_07_PLAN", "Plan A")
    result = idx.bind(parse_block("โครงการ : Demo"))
    assert not result.bound and result.candidates == 2


def test_issue19_unique_heading_still_binds():
    idx = NameIndex()
    idx.add_heading("7.3.1 โครงการที่ 1 : Demo", "SECTION_07_PLAN", "Plan A")
    idx.add_heading("7.3.2 โครงการที่ 2 : อื่น", "SECTION_07_PLAN", "Plan A")
    result = idx.bind(parse_block("โครงการ : Demo"))
    assert result.bound and result.candidates == 1


def test_issue19_through_adapter_and_matching(tmp_path):
    """integration: สองหัวข้อชื่อเดียวกันในชีตแผนเดียว ⇒ record ชีตประกอบยังออก + unresolved ·
    ไม่จับคู่อัตโนมัติ"""
    def two_headings(path):
        wb = openpyxl.load_workbook(path)
        wb["แผน"]["B4"] = f"7.3.2 โครงการที่ 2 : {PROJECT}"
        wb.save(path)
        return path
    a = recs(two_headings(build(tmp_path, "XL_FY2570_draft-bill_99999_A.xlsx")))
    b = recs(two_headings(build(tmp_path, "XL_FY2570_draft-bill_99999_B.xlsx",
                                values={"E2": 400.0})))
    sa = support_recs(a)
    assert sa and all(UNC_PARENT_LINK_UNRESOLVED in r.uncertainty for r in sa)
    res = compare(match_records(a, b))
    assert not [f for f in res.findings if f.finding_type == F_AMOUNT_DECREASED
                and f.baseline_location.cell == "E2"]
