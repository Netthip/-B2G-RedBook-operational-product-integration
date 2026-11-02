# -*- coding: utf-8 -*-
"""T1B — ตารางกระทบยอด: ตัวเลขบนหน้าจอต้องบวกกลับได้

🔴 ที่มา — กิ๊ฟจับได้ว่ารายงานเขียน `จับคู่อัตโนมัติ 541` คู่กับ
`ต้องให้คนตรวจ 1,060` ข้าง `ทั้งหมด 1,577` ซึ่งบวกกันได้ 1,601 ไม่ตรง
สาเหตุคือ **สองตัวนั้นใช้หน่วยคนละอย่าง** และไม่ได้แบ่งกันแบบไม่ทับซ้อน
ชุดนี้บังคับว่าจะไม่กลับไปเป็นแบบนั้นอีก

🔴 **SYNTHETIC TEST FIXTURE** — ยกเว้นที่ระบุไว้ชัดว่าเป็นรอบจริง

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import pytest
from fastapi.testclient import TestClient

from redbook.app import create_app
from redbook.services import t1b as svc
from redbook.storage import t1b_repo
from t1b_synth import build_workbook, records

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def view(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("recon")
    base = records(build_workbook(tmp, filename="a.xlsx", agency="สถาบันทดสอบ",
                                  cover_year=2569, section_title=TITLE))
    curr = records(build_workbook(tmp, filename="b.xlsx", agency="สถาบันทดสอบ",
                                  cover_year=2570, section_title=TITLE,
                                  invest=12.0))
    v = svc.run_from_records(base, curr, run_id="RECON-1")
    t1b_repo.init_t1b_schema()
    t1b_repo.save_run(v, run_id="RECON-1")
    return v


# ══════════════════════════════════════════════════════════════════════════════
#  R1 — เอกลักษณ์การอนุรักษ์: ทุกใบตกในช่องเดียว ไม่มีใบใดหายหรือถูกนับซ้ำ
# ══════════════════════════════════════════════════════════════════════════════

def test_every_finding_lands_in_exactly_one_cell(view):
    rc = view.reconciliation
    assert rc.total == len(view.findings)


def test_row_totals_add_up_to_the_grand_total(view):
    rc = view.reconciliation
    assert sum(r.total for r in rc.rows) == rc.total
    assert rc.total_automatic + rc.total_review == rc.total


def test_grand_total_matches_the_declared_summary(view):
    rc = view.reconciliation
    assert rc.total == view.summary.total_findings
    assert rc.balanced


def test_review_column_matches_the_declared_review_count(view):
    """คอลัมน์ขวาต้องเท่ากับตัวเลขที่หน้าสรุปประกาศ ไม่ใช่ตัวเลขคนละชุด"""
    assert view.reconciliation.total_review == view.summary.requiring_review


def test_sides_do_not_repeat(view):
    sides = [r.side for r in view.reconciliation.rows]
    assert len(sides) == len(set(sides))


# ══════════════════════════════════════════════════════════════════════════════
#  R2 — จำนวน "คู่" กับจำนวน "ใบ" เป็นคนละหน่วย
# ══════════════════════════════════════════════════════════════════════════════

def test_pair_count_is_reported_as_a_separate_unit(view):
    """``automatic_pairs`` อยู่นอกตาราง ไม่ถูกนับรวมเป็นแถวหนึ่ง"""
    rc = view.reconciliation
    assert rc.automatic_pairs == view.summary.automatic_pairs
    assert rc.pair_findings == sum(r.total for r in rc.rows
                                   if r.side == svc.SIDE_PAIR)
    assert rc.extra_findings_from_pairs == rc.pair_findings - rc.automatic_pairs


def test_extra_findings_from_pairs_is_visible_when_a_pair_emits_two(view):
    """หนึ่งคู่ออกได้หลายใบ — ส่วนต่างต้องโผล่ ไม่ใช่ถูกกลบ

    สร้าง view สังเคราะห์ขึ้นตรง ๆ เพราะกำลังทดสอบ **เลขคณิตของตาราง**
    ไม่ใช่พฤติกรรมของเครื่องยนต์
    """
    f = next(x for x in view.findings if x.side == svc.SIDE_PAIR)
    doubled = svc.T1BRunView(
        summary=view.summary, findings=view.findings + (f,))
    rc = doubled.reconciliation
    assert rc.extra_findings_from_pairs == 1
    assert not rc.balanced, "ยอดที่ประกาศไว้ไม่ตรงกับชุดจริงแล้ว ต้องประกาศว่าไม่ลง"


# ══════════════════════════════════════════════════════════════════════════════
#  R3 — จับได้เองเมื่อได้ชุดข้อสังเกตไม่ครบ
# ══════════════════════════════════════════════════════════════════════════════

def test_partial_findings_are_declared_unbalanced_not_silently_summed(view):
    """ถ้าหน้าจอได้ finding มาไม่ครบ ตารางต้อง **ประกาศว่ากระทบยอดไม่ลง**

    เงียบแล้วแสดงผลรวมที่น้อยกว่าความจริง คือความผิดพลาดที่อ่านไม่ออกจากหน้าจอ
    """
    partial = svc.T1BRunView(summary=view.summary,
                             findings=view.findings[:3])
    rc = partial.reconciliation
    assert rc.total == 3
    assert rc.declared_total == view.summary.total_findings
    assert not rc.balanced


def test_empty_run_is_balanced_at_zero():
    summary = svc.RunSummaryView(
        run_id="EMPTY", readiness=svc.CANNOT_DETERMINE,
        readiness_label=svc.READINESS_LABELS[svc.CANNOT_DETERMINE],
        identity_verdict="CANNOT_DETERMINE", identity_verdict_label="x",
        identity_gate_blocked=True, identity_reason="", automatic_pairs=0,
        total_findings=0, requiring_review=0, by_type={}, by_flag={})
    rc = svc.T1BRunView(summary=summary).reconciliation
    assert rc.rows == ()
    assert rc.total == 0 and rc.balanced


# ══════════════════════════════════════════════════════════════════════════════
#  R4 — หน้าจอต้องบอกผู้อ่านว่าห้ามบวก
# ══════════════════════════════════════════════════════════════════════════════

def test_summary_page_shows_the_reconciliation_table(client, view):
    body = client.get("/t1b/runs/RECON-1/details").text
    assert "ตารางกระทบยอด" in body
    assert "ระบบสรุปได้เอง" in body
    assert "ต้องให้ผู้ตรวจตัดสิน" in body


def test_summary_page_warns_that_the_three_numbers_use_different_units(client,
                                                                       view):
    """ป้ายกำกับต้องกันการอ่านผิดแบบที่กิ๊ฟเจอ"""
    body = client.get("/t1b/runs/RECON-1/details").text
    assert "ห้ามบวกกัน" in body
    assert "(คู่)" in body and "(ใบ)" in body


def test_summary_page_numbers_are_traceable_to_the_table(client, view):
    """ยอดรวมในตารางต้องเป็นตัวเลขเดียวกับที่โชว์ไว้ด้านบน"""
    rc = view.reconciliation
    body = client.get("/t1b/runs/RECON-1/details").text
    assert str(rc.total) in body
    assert str(rc.total_review) in body
    assert str(rc.automatic_pairs) in body
