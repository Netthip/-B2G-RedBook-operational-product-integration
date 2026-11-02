# -*- coding: utf-8 -*-
"""คิวตรวจ · ตัวนับแปดตัว · คำตัดสินแบบกลุ่ม · หน้าเว็บ (กิ๊ฟ ข้อ D)

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานทุกไฟล์ในชุดนี้แต่งขึ้นทั้งหมด
**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import pytest
from fastapi.testclient import TestClient

from redbook.app import create_app
from redbook.services import categories as cat
from redbook.services import decisions as dec
from redbook.services import review as rv
from redbook.services import t1b as svc
from redbook.storage import t1b_decisions as drepo, t1b_repo
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD
from t1b_synth import build_workbook, records

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"
RID = "RQ-1"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rq")
    base = records(build_workbook(tmp, filename="a.xlsx", agency="สถาบันทดสอบ",
                                  cover_year=2569, section_title=TITLE))
    curr = records(build_workbook(tmp, filename="b.xlsx", agency="สถาบันทดสอบ",
                                  cover_year=2570, section_title=TITLE, invest=12.0))
    view = svc.run_from_records(base, curr, run_id=RID)
    t1b_repo.init_t1b_schema()
    t1b_repo.save_run(view, run_id=RID)
    return view


def _ann(run):
    return rv.annotate(run, rv.status_map(RID))


def _token(client):
    client.get("/")
    return client.cookies.get(CSRF_COOKIE)


# ── ตัวนับ ────────────────────────────────────────────────────────────────
def test_counts_balance_and_start_all_pending(run):
    c = rv.counts(run, _ann(run))
    assert c.total == len(run.findings)
    assert c.pending == c.total and c.decided == 0
    assert c.balanced
    assert c.change_detected <= c.total
    assert sum(c.by_category.values()) == c.total


def test_change_detected_excludes_unchanged_and_comparison_types():
    assert "AMOUNT_UNCHANGED" not in rv.CHANGE_DETECTED_TYPES
    assert "UNMAPPED_REQUIRES_HUMAN_REVIEW" not in rv.CHANGE_DETECTED_TYPES
    assert "AMOUNT_DECREASED" in rv.CHANGE_DETECTED_TYPES


# ── ตัวกรอง ───────────────────────────────────────────────────────────────
def test_filter_by_category_and_status(run):
    ann = _ann(run)
    amt = rv.filter_findings(run, ann, categories_=(cat.CAT_AMOUNT,))
    assert amt and all(ann[f.finding_id].subject.category == cat.CAT_AMOUNT for f in amt)
    pend = rv.filter_findings(run, ann, statuses=(dec.PENDING,))
    assert len(pend) == len(run.findings)
    assert rv.filter_findings(run, ann, statuses=(dec.CONFIRMED,)) == ()


def test_server_side_pagination(run):
    ann = _ann(run)
    p1 = rv.review_page(run, ann, page=1, per_page=2)
    p2 = rv.review_page(run, ann, page=2, per_page=2)
    assert len(p1.items) == 2 and p1.total == len(run.findings)
    assert p1.items[0].finding_id != p2.items[0].finding_id
    assert rv.review_page(run, ann, page=999, per_page=2).page == p1.pages


# ── bulk ──────────────────────────────────────────────────────────────────
def test_bulk_refuses_edit_and_unresolved():
    for st in (dec.CONFIRMED_WITH_EDIT, dec.UNRESOLVED):
        with pytest.raises(rv.BulkNotAllowed):
            rv.validate_bulk(st, "x", 1)


def test_bulk_dismissed_requires_shared_note():
    with pytest.raises(dec.DecisionError, match="เหตุผลร่วม"):
        rv.validate_bulk(dec.DISMISSED, "", 3)
    assert rv.validate_bulk(dec.CONFIRMED, "", 3) == ""


def test_bulk_has_a_ceiling():
    with pytest.raises(dec.DecisionError):
        rv.validate_bulk(dec.CONFIRMED, "", rv.BULK_MAX + 1)


def test_bulk_creates_one_decision_and_one_audit_per_finding(run):
    from redbook.storage import audit
    ann = _ann(run)
    ids = [f.finding_id for f in run.findings[:3]]
    # 🔴 นับแบบไม่ติดเพดาน — เดิม ``limit=1000`` ทำให้ผลต่างเป็น 0 เมื่อฐานข้อมูลของชุดทดสอบ
    # มีรายการเกิน 1,000 (Pass 6 · addendum `5628401191`) · สิ่งที่ยืนยันไม่เปลี่ยน
    before = audit.entries(limit=1)[0]["seq"] if audit.entries(limit=1) else 0
    res = rv.bulk_decide(run, ids, dec.CONFIRMED,
                         expected_seqs={i: ann[i].latest_seq for i in ids})
    assert res.all_ok and len(res.succeeded) == 3
    assert audit.entries(limit=1)[0]["seq"] - before == 3
    for i in ids:
        assert len(drepo.list_for_finding(RID, i)) == 1


def test_bulk_reports_partial_stale_failures_honestly(run):
    ann = _ann(run)
    ids = [f.finding_id for f in run.findings[3:6]]
    seqs = {i: ann[i].latest_seq for i in ids}
    # อีกแท็บตัดสิน ids[1] ไปก่อน
    dec.record(run, run.by_id(ids[1]), dec.UNRESOLVED, note="x",
               expected_latest_seq=seqs[ids[1]])
    res = rv.bulk_decide(run, ids, dec.CONFIRMED, expected_seqs=seqs)
    assert not res.all_ok
    assert {o.finding_id for o in res.failed} == {ids[1]}
    assert "stale" in res.failed[0].reason
    assert len(res.succeeded) == 2


def test_bulk_on_same_status_does_not_duplicate(run):
    ann = _ann(run)
    ids = [f.finding_id for f in run.findings[:2]]      # ยืนยันไปแล้วข้างบน
    res = rv.bulk_decide(run, ids, dec.CONFIRMED,
                         expected_seqs={i: ann[i].latest_seq for i in ids})
    assert not res.all_ok and all("ไม่บันทึกซ้ำ" in o.reason for o in res.failed)


# ── หน้าเว็บ ──────────────────────────────────────────────────────────────
def test_queue_page_shows_eight_counters_and_filters(client, run):
    body = client.get(f"/t1b/runs/{RID}/queue?view=table").text
    for label in ("ข้อสังเกตทั้งหมด", "มีการเปลี่ยนแปลงที่ระบบตรวจพบ", "ต้องให้คนตรวจ",
                  "รอการตัดสิน", "ยืนยันว่าเป็นจุดที่ต้องแก้", "ยืนยันโดยแก้ไขข้อเสนอ",
                  "ยังตัดสินไม่ได้", "ไม่ใช่ประเด็นที่ต้องแก้"):
        assert label in body
    assert 'name="cat"' in body and 'name="status"' in body
    assert "เลือกทั้งหมดตามตัวกรอง" in body
    assert dec.E_BUDGETING_DISCLAIMER in body


def test_queue_has_no_one_click_confirm_all(client, run):
    body = client.get(f"/t1b/runs/{RID}/queue?view=table").text
    assert "ยืนยันทั้งหมด" not in body
    assert 'action="/t1b/runs/' + RID + '/bulk/confirm"' in body   # ต้องผ่านหน้ายืนยัน


def test_bulk_confirm_page_shows_exact_count_before_apply(client, run):
    token = _token(client)
    r = client.post(f"/t1b/runs/{RID}/bulk/confirm",
                    data={"scope": "all_filtered", "bulk_status": dec.DISMISSED,
                          "status": dec.PENDING, CSRF_FIELD: token})
    assert r.status_code == 200
    pend = sum(1 for a in _ann(run).values() if a.status == dec.PENDING)
    assert f"<b>{pend}</b> รายการ" in r.text
    assert "เหตุผลร่วม" in r.text and "(บังคับ)" in r.text
    assert drepo.count_by_status(RID).get(dec.DISMISSED, 0) == 0, "หน้ายืนยันต้องไม่เขียนอะไร"


def test_single_decide_route_records_and_shows_history(client, run):
    token = _token(client)
    f = run.findings[-1]
    seq = drepo.latest_seq_for(RID, f.finding_id)
    r = client.post(f"/t1b/runs/{RID}/findings/{f.finding_id}/decide",
                    data={"status": dec.UNRESOLVED, "note": "ขอดูต้นฉบับ",
                          "expected_latest_seq": seq, CSRF_FIELD: token},
                    follow_redirects=False)
    assert r.status_code == 303
    body = client.get(f"/t1b/runs/{RID}/findings/{f.finding_id}").text
    assert "ประวัติคำตัดสินของรายการนี้" in body and "ขอดูต้นฉบับ" in body


def test_single_decide_stale_returns_409_with_reload_hint(client, run):
    token = _token(client)
    f = run.findings[-1]
    r = client.post(f"/t1b/runs/{RID}/findings/{f.finding_id}/decide",
                    data={"status": dec.CONFIRMED, "note": "x",
                          "expected_latest_seq": 0, CSRF_FIELD: token})
    assert r.status_code == 409
    assert "โหลดสถานะล่าสุด" in r.text


def test_audit_page_verifies_links_and_chain(client, run):
    body = client.get(f"/t1b/runs/{RID}/audit").text
    assert "โซ่แฮชของ Audit Trail" in body
    assert "ไม่ผ่าน" not in body.split("ประวัติคำตัดสิน (Audit)")[1][:2000]
