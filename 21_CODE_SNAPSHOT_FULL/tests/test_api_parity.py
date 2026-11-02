# -*- coding: utf-8 -*-
"""ทุกเส้นทาง ``/api/*`` ต้องผ่านด่านเดียวกับหน้าเว็บเดิม (สัญญา ``docs/API_CONTRACT_R.md``)

เทสต์วนจาก **รายการเส้นทางจริงของแอป** — เส้นทาง API ที่เพิ่มภายหลัง (ทั้งของหลังบ้านและหน้าบ้าน) ถูกตรวจอัตโนมัติ

1. ทุก POST ใต้ ``/api/`` ต้องผ่าน CSRF: ไม่มีโทเคน · โทเคนผิด · Origin ของเว็บอื่น = 403 + บันทึก ``csrf_rejected``
   และไม่มีอะไรถูกเขียนลง Audit
2. ทุก GET ใต้ ``/api/`` ไม่เขียน Audit (อ่านอย่างเดียว)
3. ล็อกผลผู้ตรวจ (สายทดลอง): ก่อนล็อกไม่มีรอบเทียบ/ผลระบบ ทั้งทางหน้าเดิมและ API · หลังล็อกแก้จุด/หน้าไม่ได้ทั้งสองทาง
4. ด่านส่งออก (สายเทียบเล่ม): API ไม่มีทางส่งออก · สถานะด่านที่ API รายงาน = ผลของ ``export.csv`` เดิมเสมอ
5. รอบที่ถูกแทน: เขียนไม่ได้ทั้งทางหน้าเดิมและ API
6. ชั้นเว็บ/API ไม่ import ``redbook.pdfbook`` ตรง (เรียกผ่านชั้นบริการเดียวกัน)

🔴 SYNTHETIC DEMONSTRATION DATA — ชั้นเล่มสังเคราะห์ชุดเดียวกับ ``test_trial.py``
"""
import re

from fastapi.routing import APIRoute

from test_trial import AG, PROJECT_ROOT, _env, client, decl, shelf, start  # noqa: F401  (fixture ร่วม)
from redbook.services import pdfpair as psvc, pdfshelf, trial
from redbook.storage import audit, pdfpair_repo
from redbook.storage.db import connect
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_runs(monkeypatch):
    """เทสต์ในไฟล์นี้ต้องการรอบใหม่ทุกครั้งที่เรียก ``pdfshelf.start`` — ปิดการกันกดซ้ำ (เทสต์ของมันอยู่ test_pdf_upload.py)"""
    monkeypatch.setattr(pdfshelf, "START_DEDUPE_S", -1.0)


def _routes(client, method):
    return sorted(r.path for r in client.app.routes
                  if isinstance(r, APIRoute) and r.path.startswith("/api/") and method in r.methods)


def _fill(path, **ids):
    return re.sub(r"\{(\w+)(?::[^}]*)?\}", lambda m: ids.get(m.group(1), "x"), path)


def _audit_rows():
    return audit.verify_chain()["checked"]


def _csrf_events():
    conn = connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM security_events WHERE event = 'csrf_rejected'").fetchone()[0]
    finally:
        conn.close()


def _h(client):
    return {"X-CSRF-Token": client.get("/api/csrf").json()["token"]}


def _post_violations(client) -> list:
    """POST ใต้ /api/ ที่ยอมรับคำขอที่ไม่มี/ผิดโทเคน หรือมาจาก Origin อื่น — หรือเขียน Audit ทั้งที่ถูกปฏิเสธ"""
    bad = []
    tok = client.cookies.get(CSRF_COOKIE) or client.get("/api/csrf").json()["token"]
    for path in _routes(client, "POST"):
        for headers in ({}, {"X-CSRF-Token": "not-the-cookie"},
                        {"X-CSRF-Token": tok, "Origin": "http://evil.example"}):
            rows = _audit_rows()
            r = client.post(_fill(path), json={"confirm": True, "choice": "checked"}, headers=headers)
            json_reply = r.headers.get("content-type", "").startswith("application/json")
            if r.status_code != 403 or _audit_rows() != rows or (json_reply and r.json().get("code") != "csrf"):
                bad.append((path, tuple(headers), r.status_code))
    return bad


def _get_violations(client, **ids) -> list:
    bad = []
    for path in _routes(client, "GET"):
        rows, runs = _audit_rows(), len(pdfpair_repo.list_runs(limit=500))
        r = client.get(_fill(path, **ids))
        if r.status_code not in (200, 404, 409) or "Traceback" in r.text or _audit_rows() != rows \
                or len(pdfpair_repo.list_runs(limit=500)) != runs:
            bad.append((path, r.status_code))
    return bad


def test_every_api_post_requires_csrf_and_writes_nothing(client):
    posts = _routes(client, "POST")
    assert {"/api/pdfpair/runs/{rid}/f/{fid}/decide", "/api/pdfpair/runs/{rid}/rerun",
            "/api/trial/s/{sid}/lock"} <= set(posts)                      # รายการจริง ไม่ใช่รายการที่เขียนมือ
    before = _csrf_events()
    assert _post_violations(client) == []
    assert _csrf_events() - before == 3 * len(posts)                       # ทุกครั้งที่ปฏิเสธมีบันทึกความปลอดภัย


def test_every_api_get_is_read_only(client):
    _pid, rid = pdfshelf.start("S_2570_draft", "S_2570_act", AG)
    fid = next(f.id for f in psvc.view(rid).result.findings if not f.info)
    sid = trial.start("t1", "G1", again=True)                              # ยังไม่ล็อก
    assert _get_violations(client, rid=rid, fid=fid, sid=sid) == []


def test_parity_checks_catch_an_unsafe_route():
    """ตัวควบคุม: ตัวตรวจข้างบนต้องจับเส้นทางที่ไม่ตรวจ CSRF / GET ที่เขียน Audit ได้จริง (ไม่ผ่านฟรี)"""
    from fastapi.testclient import TestClient
    from redbook.app import create_app
    app = create_app()

    @app.post("/api/zz_unsafe")
    async def unsafe():
        audit.record("zz_unsafe_write", "test", "x", {})
        return {"ok": True}

    @app.get("/api/zz_writes_on_get")
    async def writes_on_get():
        audit.record("zz_get_write", "test", "x", {})
        return {"ok": True}
    with TestClient(app) as c:
        c.get("/api/csrf")
        assert {p for p, _h, _s in _post_violations(c)} == {"/api/zz_unsafe"}
        assert [p for p, _s in _get_violations(c)] == ["/api/zz_writes_on_get"]


def test_lock_parity_between_old_pages_and_api(client):
    # วิธีวัดผลฉบับ 0.2: ล็อก = ใบประกาศก่อนเห็นผล (ไม่ใช่กด "ตรวจหน้านี้แล้ว" ครบทุกหน้า) — สาระของด่านคงเดิม
    sid = start("t1", "L1", again=True, path="r2")
    s = trial.session(sid)
    p0 = s.pages("cur")[0]
    h, tok = _h(client), client.cookies.get(CSRF_COOKIE)
    m = client.post(f"/api/trial/s/{sid}/marks", json={"side": "cur", "page": p0, "fx": .5, "fy": .4, "pen": "red"},
                    headers=h).json()
    client.post(f"/api/trial/s/{sid}/marks/{m['id']}", json={"topic": "ก", "part": "๗", "cause": "t"}, headers=h)
    runs = len(pdfpair_repo.list_runs(limit=500))
    # ก่อนล็อก: ไม่มีผลระบบทั้งสองทาง · ไม่มีรอบเทียบเกิดขึ้น
    assert client.get(f"/trial/s/{sid}/result").status_code == 409
    assert client.get(f"/api/trial/s/{sid}/result").status_code == 409
    assert client.get(f"/trial/s/{sid}/summary.json").status_code == 409
    assert client.post(f"/trial/s/{sid}/issue/{m['id']}", data={CSRF_FIELD: tok, "verdict": "exact"}).status_code >= 400
    assert client.post(f"/api/trial/s/{sid}/issue/{m['id']}", json={"verdict": "exact"}, headers=h).status_code >= 400
    body = client.get(f"/api/trial/s/{sid}").text
    assert "finding" not in body and "metrics" not in body and "verdict" not in body
    assert len(pdfpair_repo.list_runs(limit=500)) == runs and trial.session(sid).rec["run_id"] == ""
    # ใบประกาศไม่ครบ = ไม่ล็อก ไม่มีรอบเทียบ · ครบแล้วล็อกผ่าน API → ระบบเทียบครั้งเดียว (ไม่ได้กดหน้าใดเลย)
    assert client.post(f"/api/trial/s/{sid}/lock", json={"confirm": True}, headers=h).status_code == 400
    assert len(pdfpair_repo.list_runs(limit=500)) == runs
    assert client.post(f"/api/trial/s/{sid}/lock", json={**decl("r2"), "confirm": True}, headers=h).status_code == 200
    assert len(pdfpair_repo.list_runs(limit=500)) == runs + 1
    marks = [dict(x) for x in trial.session(sid).marks]
    # หลังล็อก: แก้จุด/หน้าไม่ได้ทั้งสองทาง และข้อมูลไม่เปลี่ยน
    assert client.post(f"/api/trial/s/{sid}/marks", json={"side": "cur", "page": p0, "fx": .1, "fy": .1, "pen": "red"},
                       headers=h).status_code >= 400
    assert client.post(f"/trial/s/{sid}/marks", data={CSRF_FIELD: tok, "side": "cur", "page_no": p0, "fx": .1,
                                                      "fy": .1, "pen": "red"}).status_code >= 400
    assert client.post(f"/api/trial/s/{sid}/marks/{m['id']}", json={"delete": True}, headers=h).status_code >= 400
    assert client.post(f"/trial/s/{sid}/marks/{m['id']}", data={CSRF_FIELD: tok, "delete": "1"}).status_code >= 400
    assert client.post(f"/trial/s/{sid}/done", data={CSRF_FIELD: tok, "side": "cur",
                                                     "page_no": p0}).status_code >= 400
    assert [dict(x) for x in trial.session(sid).marks] == marks and trial.session(sid).locked


def test_export_gate_parity_and_no_export_in_api(client):
    assert not [p for p in _routes(client, "GET") + _routes(client, "POST") if "export" in p]
    _pid, rid = pdfshelf.start("S_2570_draft", "S_2570_act", AG)

    def both():
        return (client.get(f"/api/pdfpair/runs/{rid}/preflight").json()["ok"],
                client.get(f"/pdfpair/runs/{rid}/export.csv").status_code)
    assert both() == (False, 409)
    pf = client.get(f"/api/pdfpair/runs/{rid}/preflight").json()
    assert pf["failing"] == [c.key for c in psvc.preflight(rid).failing]
    h = _h(client)
    for f in psvc.view(rid).result.findings:
        if not f.info:
            client.post(f"/api/pdfpair/runs/{rid}/f/{f.id}/decide", json={"choice": "checked"}, headers=h)
    assert both() == (True, 200)
    assert pdfpair_repo.audit_entries(rid)[-1]["action"] == "pdfpair_exported"


def test_superseded_run_is_read_only_both_ways(client):
    from test_api_pdfpair import _tamper_year
    _pid, rid = pdfshelf.start("S_2570_draft", "S_2570_act", AG)
    _tamper_year(rid, "B", None, "not_found")
    psvc.confirm_year(rid, "B", "2570", "หน้าเริ่มหน่วยงาน", True)
    new = psvc.rerun(rid)
    f = next(x for x in psvc.view(rid).result.findings if not x.info)
    h, tok = _h(client), client.cookies.get(CSRF_COOKIE)
    assert client.post(f"/pdfpair/runs/{rid}/f/{f.id}/decide", data={CSRF_FIELD: tok, "choice": "checked"}).status_code >= 400
    r = client.post(f"/api/pdfpair/runs/{rid}/f/{f.id}/decide", json={"choice": "checked"}, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "superseded"
    assert client.post(f"/pdfpair/runs/{rid}/year", data={CSRF_FIELD: tok, "side": "A", "year": "2570",
                                                          "seen": "1"}).status_code >= 400
    assert client.post(f"/api/pdfpair/runs/{rid}/year", json={"side": "A", "year": "2570", "seen": True},
                       headers=h).status_code == 409
    v = psvc.view(rid)
    assert f.id not in v.decisions and "A" not in v.year_confirms and v.superseded_by == new
    assert client.get(f"/pdfpair/runs/{rid}/export.csv").status_code == 409


def test_web_and_api_layers_go_through_services():
    for p in (PROJECT_ROOT / "redbook" / "web").glob("*.py"):
        src = p.read_text(encoding="utf-8")
        assert "from ..pdfbook" not in src and "redbook.pdfbook" not in src, p.name
