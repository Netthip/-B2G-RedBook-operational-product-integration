# -*- coding: utf-8 -*-
"""ด่านตรวจก่อนส่งออก + เมนูซ้าย + แถบขั้นตอน 1–6 (คำสั่งกิ๊ฟ 23 ก.ย. 2569)

สิ่งที่ชุดนี้ยืนยัน

* ด่านเป็น **ด่านจริงฝั่งเซิร์ฟเวอร์** — ปิดปุ่มบนหน้าจออย่างเดียวไม่นับ
* เมื่อด่านไม่ผ่าน **ไม่มีไฟล์ใดถูกเขียน** แม้แต่ไฟล์เดียว
* การรับทราบรายการที่ระบบอ่านไม่ครบ **ผูกกับชุดรายการ** ไม่ใช่ผูกกับรอบ
* ทุกขั้นของงานมีทางเข้าจากเมนูซ้าย ไม่ต้องพิมพ์ URL

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานทุกไฟล์ในชุดนี้แต่งขึ้นทั้งหมด
ห้ามรายงานผลจากชุดนี้ว่าเป็นข้อผิดพลาดที่พบในเอกสารจริง

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import re

import pytest
from fastapi.testclient import TestClient

from redbook import config
from redbook.app import create_app, nav_active_for, nav_context
from redbook.services import decisions as dec
from redbook.services import export as ex
from redbook.services import preflight as pre
from redbook.services import review
from redbook.services import t1b as svc
from redbook.services import workflow as wf
from redbook.storage import t1b_preflight, t1b_repo
from redbook.storage.db import init_db
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD
from t1b_synth import build_workbook, records

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"


def _pair(tmp_path, rid, *, agency="สถาบันทดสอบ", agency_b=None):
    base = records(build_workbook(
        tmp_path, filename=f"{rid}_a.xlsx", agency=agency, cover_year=2569,
        section_title=TITLE))
    curr = records(build_workbook(
        tmp_path, filename=f"{rid}_b.xlsx",
        agency=agency if agency_b is None else agency_b, cover_year=2570,
        section_title=TITLE, invest=12.0))
    view = svc.run_from_records(base, curr, run_id=rid)
    t1b_repo.init_t1b_schema()
    t1b_preflight.init_preflight_schema()
    t1b_repo.save_run(view, run_id=rid)
    return view


def _state(rid):
    view = svc.load_run(rid)
    ann = review.annotate(view, review.status_map(rid))
    counts = review.counts(view, ann)
    bundle = ex.build(view)
    ids = pre.unmapped_ids(view)
    scope = t1b_preflight.scope_hash(ids)
    ack = t1b_preflight.get_ack(rid, scope) if ids else None
    return view, pre.evaluate(view, counts, bundle, ack=ack, unmapped_scope=scope)


def _decide_all(view):
    for f in view.findings:
        dec.record(view, f, dec.CONFIRMED, expected_latest_seq=0)


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


# ══════════════════════════════════════════════════════ ตัวด่านเอง (ชั้นบริการ)

def test_every_gate_is_present_and_ordered(tmp_path):
    view = _pair(tmp_path, "PF-ORDER")
    _, pf = _state("PF-ORDER")
    assert tuple(g.code for g in pf.gates) == pre.GATE_ORDER
    assert len(pf.gates) == 5


def test_pending_decisions_block_the_export(tmp_path):
    _pair(tmp_path, "PF-PEND")
    _, pf = _state("PF-PEND")
    gate = pf.gate(pre.GATE_PENDING)
    assert not gate.ok and not pf.ok
    assert "ยังไม่ได้ตัดสิน" in gate.detail


def test_every_failing_gate_explains_how_to_fix(tmp_path):
    _pair(tmp_path, "PF-FIX")
    _, pf = _state("PF-FIX")
    assert pf.blocking, "รอบที่ยังไม่ได้ตัดสินอะไรเลยต้องติดด่าน"
    for g in pf.blocking:
        assert g.how_to_fix.strip(), g.code
        assert g.detail.strip(), g.code


def test_unmapped_needs_an_acknowledgement_bound_to_that_exact_set(tmp_path):
    view = _pair(tmp_path, "PF-UNMAP")
    _decide_all(view)
    view, pf = _state("PF-UNMAP")
    ids = pre.unmapped_ids(view)
    assert ids, "ชุด fixture นี้ต้องมีรายการที่เครื่องยนต์อ่านไม่ครบ"
    assert not pf.gate(pre.GATE_UNMAPPED).ok

    t1b_preflight.acknowledge("PF-UNMAP", ids, who="ผู้ตรวจ")
    _, pf2 = _state("PF-UNMAP")
    assert pf2.gate(pre.GATE_UNMAPPED).ok and pf2.ok

    # ชุดเปลี่ยน ⇒ การรับทราบเดิมใช้ไม่ได้อีก โดยไม่ต้องไปลบอะไรทิ้ง
    moved = t1b_preflight.scope_hash(list(ids)[:-1])
    assert t1b_preflight.get_ack("PF-UNMAP", moved) is None


def test_identity_gate_blocks_when_the_two_files_may_be_different_agencies(tmp_path):
    _pair(tmp_path, "PF-ID", agency_b="หน่วยงานอื่น")
    _, pf = _state("PF-ID")
    assert not pf.gate(pre.GATE_IDENTITY).ok


def test_nothing_to_export_is_its_own_gate(tmp_path):
    view = _pair(tmp_path, "PF-EMPTY")
    for f in view.findings:
        dec.record(view, f, dec.DISMISSED, note="ไม่ใช่ประเด็น",
                   expected_latest_seq=0)
    view, pf = _state("PF-EMPTY")
    t1b_preflight.acknowledge("PF-EMPTY", pre.unmapped_ids(view), who="ผู้ตรวจ")
    _, pf = _state("PF-EMPTY")
    assert pf.gate(pre.GATE_PENDING).ok
    assert not pf.gate(pre.GATE_EMPTY).ok and not pf.ok


# ══════════════════════════════════════════════════════ ด่านฝั่งเซิร์ฟเวอร์

def test_blocked_export_writes_no_file_at_all(client, tmp_path):
    _pair(tmp_path, "PF-BLOCK")
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    before = sorted(p.name for p in config.EXPORT_DIR.glob("exp_*"))

    r = client.post("/t1b/runs/PF-BLOCK/export", data={CSRF_FIELD: token})
    assert r.status_code == 409
    assert pre.BLOCKED_NOTICE in r.text
    after = sorted(p.name for p in config.EXPORT_DIR.glob("exp_*"))
    assert before == after, "ด่านไม่ผ่านแล้วยังมีไฟล์ถูกเขียน — ด่านไม่ทำงาน"


def test_export_button_is_disabled_but_that_is_not_the_gate(client, tmp_path):
    _pair(tmp_path, "PF-BTN")
    body = client.get("/t1b/runs/PF-BTN/export").text
    assert "disabled" in body
    assert "ด่านตรวจก่อนส่งออกยังไม่ผ่าน" in body


def test_acknowledging_a_stale_set_is_refused(client, tmp_path):
    view = _pair(tmp_path, "PF-STALE")
    _decide_all(view)
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post("/t1b/runs/PF-STALE/preflight/ack",
                    data={CSRF_FIELD: token, "scope": "0" * 64,
                          "reviewer": "ผู้ตรวจ"})
    assert r.status_code == 409
    assert t1b_preflight.list_for_run("PF-STALE") == []


def test_preflight_page_lists_reason_and_fix_for_each_blocking_gate(client, tmp_path):
    _pair(tmp_path, "PF-PAGE")
    body = client.get("/t1b/runs/PF-PAGE/preflight").text
    assert "ยังส่งออกไม่ได้" in body and "ทางแก้" in body
    assert "ตารางกระทบยอดข้อสังเกต" in body


def test_full_gate_walk_from_blocked_to_exported(client, tmp_path):
    view = _pair(tmp_path, "PF-WALK")
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    assert client.post("/t1b/runs/PF-WALK/export",
                       data={CSRF_FIELD: token}).status_code == 409

    _decide_all(view)
    pre_body = client.get("/t1b/runs/PF-WALK/preflight").text
    scope = re.search(r'name="scope" value="([0-9a-f]+)"', pre_body).group(1)
    assert client.post("/t1b/runs/PF-WALK/preflight/ack",
                       data={CSRF_FIELD: token, "scope": scope,
                             "reviewer": "ผู้ตรวจ"},
                       follow_redirects=False).status_code == 303

    ok = client.get("/t1b/runs/PF-WALK/preflight").text
    assert "ผ่านทุกเงื่อนไขแล้ว" in ok
    wrote = client.post("/t1b/runs/PF-WALK/export", data={CSRF_FIELD: token})
    assert wrote.status_code == 200 and "exp_" in wrote.text


# ══════════════════════════════════════════════════════ เมนูซ้าย + แถบขั้นตอน

@pytest.mark.parametrize("path,expected", [
    ("/", "projects"),
    ("/projects/new", "new"),
    ("/projects/abc", "projects"),
    ("/t1b/runs", "runs"),
    ("/t1b/runs/R1", "runs"),
    ("/t1b/runs/R1/queue", "queue"),
    ("/t1b/runs/R1/preflight", "preflight"),
    ("/t1b/runs/R1/export", "export"),
    ("/t1b/runs/R1/audit", "audit"),
    ("/audit", "audit"),
    ("/rules", "rules"),
])
def test_nav_highlights_the_page_you_are_on(path, expected):
    assert nav_active_for(path) == expected


def test_nav_has_every_step_and_scopes_to_the_open_run():
    ctx = nav_context("/t1b/runs/R1/queue", run_id="R1")
    keys = [i["key"] for i in ctx["menu"]]
    assert keys == ["projects", "runs", "queue", "preflight", "export",
                    "audit", "rules"]
    by_key = {i["key"]: i["href"] for i in ctx["menu"]}
    assert by_key["queue"] == "/t1b/runs/R1/queue"
    assert by_key["preflight"] == "/t1b/runs/R1/preflight"
    assert by_key["export"] == "/t1b/runs/R1/export"
    assert by_key["audit"] == "/t1b/runs/R1/audit"
    # ไม่รู้ว่ารอบไหน ⇒ ชี้ไปหน้ากลางที่ให้เลือกรอบ ไม่ใช่ลิงก์ตาย
    plain = {i["key"]: i["href"] for i in nav_context("/")["menu"]}
    assert plain["queue"] == "/queue" and plain["preflight"] == "/preflight"


@pytest.mark.parametrize("path", ["/", "/rules", "/audit", "/projects/new",
                                  "/t1b/runs", "/queue", "/preflight", "/export"])
def test_every_page_carries_the_sidebar(client, path):
    body = client.get(path, follow_redirects=True).text
    for label in ("งานตรวจ", "รอบตรวจ", "คิวพิจารณา", "Preflight", "ส่งออก",
                  "Audit", "บัญชีกฎ"):
        assert label in body, f"{path} ขาดเมนู {label}"


def test_run_pages_show_where_you_are_in_the_six_steps(client, tmp_path):
    _pair(tmp_path, "PF-STEPS")
    body = client.get("/t1b/runs/PF-STEPS/queue").text
    for label in wf.STEP_LABELS.values():
        assert label in body, label
    assert "ยังไม่ได้ตัดสิน" in body


def test_dashboard_reopens_an_existing_run_without_typing_a_url(client, tmp_path):
    _pair(tmp_path, "PF-DASH")
    body = client.get("/").text
    assert "PF-DASH" in body
    assert "/t1b/runs/PF-DASH" in body
    assert "ขั้นต่อไป" in body


def test_workflow_marks_done_current_and_outstanding():
    w = wf.build(current=wf.STEP_REVIEW, run_id="R1", files_ready=True,
                 analyzed=True, pending=3, total_findings=10,
                 preflight_ok=False, preflight_blocking=2)
    states = {s.code: s.state for s in w.steps}
    assert states[wf.STEP_PROJECT] == wf.DONE
    assert states[wf.STEP_ANALYZE] == wf.DONE
    assert states[wf.STEP_REVIEW] == wf.CURRENT
    assert states[wf.STEP_EXPORT] == wf.TODO
    assert any("3 รายการ" in s.detail for s in w.outstanding)


# ══════════════════════════════════════════ ด่าน CSRF กับเบราว์เซอร์จริง

def test_a_same_origin_form_post_from_a_real_browser_is_accepted(client, tmp_path):
    """🔴 regression — เดิมทุกแบบฟอร์มส่งไม่ได้บนเบราว์เซอร์จริง

    นโยบาย ``Referrer-Policy: no-referrer`` ทำให้ Chrome/Firefox ส่ง
    ``Origin: null`` มากับการ submit ฟอร์ม แม้เป็น same-origin ·
    ``verify_csrf`` อ่านว่า origin ไม่ตรงแล้วปฏิเสธทุกคำขอ ·
    ชุดทดสอบเดิมจับไม่ได้เพราะ ``TestClient`` ไม่ส่งหัว ``Origin`` เลย
    """
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post("/projects/new", follow_redirects=False,
                    headers={"Origin": "null"},
                    data={CSRF_FIELD: token, "name": "ผ่านเบราว์เซอร์",
                          "mode": "before_after_reduction"})
    assert r.status_code == 303, "same-origin form post ต้องผ่าน"


def test_a_genuinely_cross_site_post_is_still_refused(client):
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post("/projects/new",
                    headers={"Origin": "http://evil.example"},
                    data={CSRF_FIELD: token, "name": "x",
                          "mode": "year_to_year"})
    assert r.status_code == 403


def test_referrer_policy_does_not_blind_the_origin_check(client):
    """นโยบาย referrer ต้องไม่ทำให้ด่าน origin ใช้การไม่ได้ทั้งระบบ"""
    from redbook.web.security import SECURITY_HEADERS
    assert SECURITY_HEADERS["Referrer-Policy"] == "same-origin"
    assert client.get("/").headers["Referrer-Policy"] == "same-origin"
