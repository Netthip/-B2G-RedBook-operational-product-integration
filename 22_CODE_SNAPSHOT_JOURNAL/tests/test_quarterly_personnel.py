# -*- coding: utf-8 -*-
"""กฎการกันงบบุคลากรและการแบ่งสี่ไตรมาส (Issue #8)

ที่มา — directive ข้อ 2 ของ Bo 13 ก.ย. 2569 + คำตัดสินกิ๊ฟ 27 ก.ย. 2569
ว่า **งบบุคลากรระบุจากหมวดงบรายจ่าย**

สิ่งที่ชุดนี้ยืนยัน

* หารด้วย 400 บาทไม่ลงตัว ⇒ **ปฏิเสธ** ไม่ปัดเศษ ไม่โยกเศษ
* ผลรวมรายไตรมาส = ยอดรายปี เสมอ เมื่อคำนวณได้
* หน่วยที่แปลงเป็นบาทไม่ได้ ⇒ ตกให้คนตัดสิน ไม่เดาอัตราแปลง
* งบบุคลากรมาจาก canonical category ไม่ใช่การจับคำจากชื่อรายการ
* ลำดับ 1 ที่รับเข้ามา **ไม่ถูกแตะ**

🔴 **SYNTHETIC TEST FIXTURE** — ตัวเลขทุกตัวในชุดนี้แต่งขึ้นทั้งหมด

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from redbook.app import create_app
from redbook.services import quarterly as q
from redbook.services import t1b as svc
from redbook.storage import t1b_preflight, t1b_repo
from t1b_synth import build_workbook, records

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


# ══════════════════════════════════════════════════════ กฎการแบ่ง

@pytest.mark.parametrize("annual,per_quarter", [
    (400, 100),
    (1_200, 300),
    (7_400_000, 1_850_000),
    (400_000_000, 100_000_000),
])
def test_divisible_amounts_split_into_four_equal_quarters(annual, per_quarter):
    s = q.split_annual(annual, q.UNIT_BAHT)
    assert s.ok
    assert len(s.quarters) == q.QUARTERS
    assert all(x == Decimal(per_quarter) for x in s.quarters)
    assert s.per_quarter_baht == Decimal(per_quarter)


@pytest.mark.parametrize("annual", [1, 100, 300, 500, 7_400_100, 999_999])
def test_amounts_not_divisible_by_400_fail_closed(annual):
    """🔴 ข้อที่กฎเน้นที่สุด — ปฏิเสธ ไม่ใช่ปัดเศษ"""
    s = q.split_annual(annual, q.UNIT_BAHT)
    assert not s.ok
    assert s.reason == q.NOT_DIVISIBLE
    assert s.per_quarter_baht is None, "ห้ามให้ยอดรายไตรมาสเมื่อแบ่งไม่ลงตัว"
    assert s.quarters == (), "ห้ามสร้างยอดรายไตรมาสที่ปัดแล้ว"
    assert s.how_to_fix.strip()


def test_the_remainder_is_reported_but_never_used():
    s = q.split_annual(500, q.UNIT_BAHT)
    assert s.remainder_baht == Decimal(100)      # บอกให้คนเห็น
    assert s.per_quarter_baht is None            # แต่ไม่เอาไปคำนวณต่อ


def test_quarterly_sum_always_equals_the_annual_total():
    for annual in (400, 800, 1_200_000, 88_888_800):
        s = q.split_annual(annual, q.UNIT_BAHT)
        assert s.ok
        assert s.quarters_sum == Decimal(annual)
        assert s.sum_matches_annual


# ══════════════════════════════════════════════════════ หน่วย

def test_million_baht_converts_exactly():
    """0.0001 ล้านบาท = 100 บาท พอดี — นี่คือที่มาของ "หน่วยร้อยบาท" """
    s = q.split_annual("1.2", q.UNIT_MILLION_BAHT)
    assert s.ok and s.annual_baht == Decimal("1200000.0")
    assert s.per_quarter_baht == Decimal("300000.0")

    smallest = q.split_annual("0.0004", q.UNIT_MILLION_BAHT)
    assert smallest.ok and smallest.per_quarter_baht == Decimal("100.0000")


def test_a_million_baht_amount_can_also_fail_closed():
    s = q.split_annual("1.2345", q.UNIT_MILLION_BAHT)
    assert not s.ok and s.reason == q.NOT_DIVISIBLE
    assert s.annual_baht == Decimal("1234500.0000")


@pytest.mark.parametrize("unit", ["ร้อยละ", "UNRESOLVED", "", "คน"])
def test_units_that_cannot_be_converted_go_to_a_human(unit):
    s = q.split_annual(1000, unit)
    assert not s.ok and s.reason == q.UNIT_NOT_CONVERTIBLE
    assert s.annual_baht is None, "ห้ามเดาอัตราแปลงเป็นบาท"


@pytest.mark.parametrize("value", ["", "  ", "abc", None, "1.2.3"])
def test_unreadable_amounts_go_to_a_human(value):
    s = q.split_annual(value, q.UNIT_BAHT)
    assert not s.ok and s.reason == q.AMOUNT_UNREADABLE


@pytest.mark.parametrize("value", [0, -400, "-1200"])
def test_non_positive_amounts_are_refused(value):
    s = q.split_annual(value, q.UNIT_BAHT)
    assert not s.ok and s.reason == q.AMOUNT_NOT_POSITIVE


def test_thousand_separators_are_read_not_rejected():
    s = q.split_annual("7,400,000", q.UNIT_BAHT)
    assert s.ok and s.annual_baht == Decimal(7_400_000)


# ══════════════════════════════════════════════════════ ลำดับการกันงบ

def test_priority_one_items_are_carried_through_untouched():
    plan = q.build_plan(
        personnel_annual=1_200_000,
        existing_priority_1=[("ภาระผูกพันปีก่อน", "สัญญาต่อเนื่อง")],
        other_planned=[("ค่าสาธารณูปโภค", "วางแผนไว้ Q1")])
    first = plan.lines[0]
    assert first.priority == q.PRIORITY_EXISTING
    assert first.untouched and first.split is None
    assert first.ok, "ลำดับ 1 ต้องไม่ถูกตัดสินว่าไม่ผ่านโดยระบบนี้"


def test_personnel_is_always_priority_two_and_before_other_spending():
    plan = q.build_plan(
        personnel_annual=1_200_000,
        existing_priority_1=[("ภาระผูกพันเดิม", "")],
        other_planned=[("รายจ่ายอื่น", "")])
    order = [ln.priority for ln in plan.lines]
    assert order == [q.PRIORITY_EXISTING, q.PRIORITY_PERSONNEL, q.PRIORITY_OTHER]
    assert plan.personnel.category == q.CATEGORY_PERSONNEL
    assert plan.ok


def test_a_blocked_personnel_split_blocks_the_whole_plan():
    plan = q.build_plan(personnel_annual=500)
    assert not plan.ok
    assert plan.blocked and plan.blocked[0].priority == q.PRIORITY_PERSONNEL


# ══════════════════════════════════════════════════════ มาจากหมวดงบรายจ่าย

def test_candidates_come_from_the_budget_category_not_from_row_text(tmp_path):
    """กิ๊ฟตัดสิน 27 ก.ย. — ระบุจากหมวดงบรายจ่าย ไม่ใช่จับคำจากชื่อรายการ"""
    base = records(build_workbook(tmp_path, filename="pa.xlsx",
                                  agency="สถาบันทดสอบ", cover_year=2569,
                                  section_title=TITLE))
    curr = records(build_workbook(tmp_path, filename="pb.xlsx",
                                  agency="สถาบันทดสอบ", cover_year=2570,
                                  section_title=TITLE, invest=12.0))
    view = svc.run_from_records(base, curr, run_id="PERS-1")
    for c in q.personnel_candidates(view):
        f = view.by_id(c.finding_id)
        assert f.budget_category == q.CATEGORY_PERSONNEL

    # แถวที่ชื่อมีคำว่าบุคลากรแต่หมวดไม่ใช่ PERSONNEL ต้องไม่ถูกหยิบมา
    ids = {c.finding_id for c in q.personnel_candidates(view)}
    for f in view.findings:
        if f.budget_category != q.CATEGORY_PERSONNEL:
            assert f.finding_id not in ids


# ══════════════════════════════════════════════════════ หน้าจอ

@pytest.fixture(scope="module")
def run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("pers_web")
    base = records(build_workbook(tmp, filename="wa.xlsx", agency="สถาบันทดสอบ",
                                  cover_year=2569, section_title=TITLE))
    curr = records(build_workbook(tmp, filename="wb.xlsx", agency="สถาบันทดสอบ",
                                  cover_year=2570, section_title=TITLE, invest=12.0))
    view = svc.run_from_records(base, curr, run_id="PERS-WEB")
    t1b_repo.init_t1b_schema()
    t1b_preflight.init_preflight_schema()
    t1b_repo.save_run(view, run_id="PERS-WEB")
    return view


def test_page_states_the_rule_and_does_not_claim_a_measured_result(client, run):
    body = client.get("/t1b/runs/PERS-WEB/personnel").text
    assert "กันงบบุคลากรและแบ่งสี่ไตรมาส" in body
    assert "หน่วยร้อยบาท" in body
    assert "ไม่ปัดเศษ" in body
    # 🔴 Bo: keep evaluation/performance claims out of the UI
    for banned in ("ความแม่นยำ", "accuracy", "precision", "recall", "F1"):
        assert banned not in body, banned


def test_page_computes_a_lawful_split(client, run):
    body = client.get("/t1b/runs/PERS-WEB/personnel",
                      params={"amount": "7400000", "unit": "บาท"}).text
    assert "แบ่งสี่ไตรมาสได้ลงตัว" in body
    assert "1,850,000" in body


def test_page_refuses_and_explains_when_not_divisible(client, run):
    body = client.get("/t1b/runs/PERS-WEB/personnel",
                      params={"amount": "500", "unit": "บาท"}).text
    assert "หารด้วย 400 บาทไม่ลงตัว" in body
    assert "ทางแก้" in body
    assert "125" not in body, "ห้ามแสดงยอดรายไตรมาสที่ปัดแล้ว"


def test_page_says_where_priority_one_comes_from_and_what_is_still_undecided(client, run):
    """ลำดับ 1 มีที่มาแล้ว (ยอดผูกพัน) · แต่ "รายจ่ายอื่น" ยังไม่มีคำตัดสิน"""
    body = client.get("/t1b/runs/PERS-WEB/personnel",
                      params={"amount": "400", "unit": "บาท"}).text
    assert "ลำดับ 1 มาจากยอดผูกพันที่ผู้ตรวจเลือก" in body
    assert "รายจ่ายอื่นที่วางแผนไว้" in body
    assert "ยังไม่มีคำตัดสินว่ามาจากแหล่งใดในเอกสาร" in body


# ══════════════════════════════════════════════════════ คู่ไฟล์สาธิต

def test_the_demo_pair_exercises_both_sides_of_the_rule(tmp_path):
    """คู่ไฟล์สาธิตต้องโชว์ได้ทั้งกรณีผ่านและกรณีที่ด่านปฏิเสธ

    ถ้าสาธิตได้แต่กรณีผ่าน คนดูจะไม่เห็นว่าด่าน fail-closed ทำงานจริง
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import demo_ao_workbooks as gen

    a, b = gen.build(tmp_path / "demo")
    view = svc.run_from_workbooks(a, b, run_id="PERS-DEMO")
    candidates = q.personnel_candidates(view)
    assert candidates, "คู่ไฟล์สาธิตต้องมีหมวดงบบุคลากรให้เห็น"

    c = candidates[0]
    assert c.declared_unit == q.UNIT_MILLION_BAHT
    before = q.split_annual(c.baseline_value, c.declared_unit)
    after = q.split_annual(c.current_value, c.declared_unit)
    assert before.ok, "ฝั่งตั้งต้นต้องแบ่งสี่ไตรมาสได้ลงตัว"
    assert before.per_quarter_baht == Decimal("1850000.0000")
    assert after.reason == q.NOT_DIVISIBLE, "ฝั่งปัจจุบันต้องทำให้ด่านปฏิเสธ"
    assert after.remainder_baht == Decimal("100.0000")


# ══════════════════════════════════════════════════════ ลำดับ 1 = ยอดผูกพัน

@pytest.mark.parametrize("label,role,year", [
    ("ปี 2570 ผูกพันงบประมาณ", q.ROLE_COMMITMENT_YEAR, 2570),
    ("ปี 2571 ผูกพันงบประมาณ", q.ROLE_COMMITMENT_YEAR, 2571),
    ("วงเงินทั้งสิ้นของโครงการ", q.ROLE_LIFETIME_CEILING, None),
    ("วงเงินทั้งสิ้น", q.ROLE_LIFETIME_CEILING, None),
    ("งบประมาณผูกพัน", q.ROLE_COMMITMENT_UNCLEAR, None),
    ("ค่าสาธารณูปโภค", "", None),
    ("", "", None),
    ("ปี 2570 ตั้งงบประมาณ", "", None),
])
def test_commitment_roles_follow_the_documented_markers(label, role, year):
    """ตัวบ่งชี้มาจากที่ FORMATIVE_CASE_NVI บันทึกไว้จากเอกสารจริง ไม่ได้คิดเอง"""
    assert q.classify_commitment(label) == (role, year)


def test_only_a_year_commitment_can_become_priority_one(tmp_path):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import demo_ao_workbooks as gen

    a, b = gen.build(tmp_path / "commit")
    view = svc.run_from_workbooks(a, b, run_id="COMMIT-1")
    personnel = [c for c in q.personnel_candidates(view) if c.eligible]
    assert personnel, "ต้องมีรายการงบบุคลากรที่ใช้เป็นยอดรายปีได้"
    sheet = personnel[0].sheet

    rows = q.commitment_rows(view, sheet=sheet)
    by_role = {r.role: r for r in rows}
    assert q.ROLE_COMMITMENT_YEAR in by_role
    assert q.ROLE_LIFETIME_CEILING in by_role

    assert by_role[q.ROLE_COMMITMENT_YEAR].eligible
    assert not by_role[q.ROLE_LIFETIME_CEILING].eligible, \
        "วงเงินตลอดอายุโครงการต้องไม่ถูกเสนอเป็นลำดับ 1 — รวมแล้วนับซ้ำ"


def test_commitment_rows_are_scoped_to_the_same_sheet(tmp_path):
    """คำตัดสินกิ๊ฟ 27 ก.ย. — ดูจากยอดผูกพัน **ในชีตเดียวกัน**"""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import demo_ao_workbooks as gen

    a, b = gen.build(tmp_path / "scope")
    view = svc.run_from_workbooks(a, b, run_id="COMMIT-2")
    assert q.commitment_rows(view, sheet="ชีตที่ไม่มีอยู่จริง") == ()
    assert q.commitment_rows(view, sheet="สรุป")


def test_a_lifetime_ceiling_is_never_offered_as_an_annual_personnel_amount(tmp_path):
    """🔴 กับดักที่ FORMATIVE_CASE_NVI เตือนไว้ — ตัวเลขบังเอิญเท่ากันแล้วนับซ้ำ"""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import demo_ao_workbooks as gen

    a, b = gen.build(tmp_path / "ceiling")
    view = svc.run_from_workbooks(a, b, run_id="COMMIT-3")
    for c in q.personnel_candidates(view):
        if c.temporal_role:
            assert not c.eligible, c.row_label
            assert "นับซ้ำ" in c.note


def test_priority_one_lines_keep_the_document_amount_untouched():
    rows = [q.CommitmentRow(finding_id="f1", row_label="ปี 2570 ผูกพันงบประมาณ",
                            role=q.ROLE_COMMITMENT_YEAR, fiscal_year=2570,
                            declared_unit="ล้านบาท", baseline_value="3.2000",
                            current_value="3.2000", sheet="สรุป")]
    plan = q.build_plan(personnel_annual=7_400_000,
                        existing_priority_1=q.priority_1_from_commitments(rows))
    first = plan.lines[0]
    assert first.priority == q.PRIORITY_EXISTING and first.untouched
    assert first.split is None, "ลำดับ 1 ต้องไม่ถูกนำไปคำนวณแบ่งไตรมาส"
    assert "3.2000" in first.note and "ไม่คำนวณใหม่" in first.note


def test_page_scopes_commitments_to_the_chosen_sheet(client, run):
    body = client.get("/t1b/runs/PERS-WEB/personnel").text
    assert "ลำดับ 1 ดูจากยอดผูกพันในชีตเดียวกัน" in body


@pytest.mark.parametrize("value,text", [
    (Decimal("7400000.0000"), "7,400,000"),
    (Decimal("1850000.0000"), "1,850,000"),
    (Decimal("400"), "400"),
    (Decimal("100.50"), "100.50"),
    (None, "—"),
])
def test_baht_display_strips_noise_without_changing_the_value(value, text):
    """ชั้นแสดงผลล้วน — ตัดศูนย์ท้ายทิ้ง แต่ห้ามปัดค่าจริง"""
    assert q.format_baht(value) == text


def test_page_shows_readable_baht_figures(client, run):
    body = client.get("/t1b/runs/PERS-WEB/personnel",
                      params={"amount": "7.4", "unit": "ล้านบาท"}).text
    assert "7,400,000 บาท" in body
    assert "7,400,000.0000" not in body


def test_sub_satang_precision_is_never_hidden():
    """🔴 ถ้าค่าละเอียดกว่าสตางค์ ต้องแสดงตามจริง ห้ามปัดให้ดูเรียบร้อย"""
    assert q.format_baht(Decimal("0.001")) == "0.001"
    assert q.format_baht(Decimal("1234.0567")) == "1,234.0567"
