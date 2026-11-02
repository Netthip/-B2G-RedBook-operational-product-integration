# -*- coding: utf-8 -*-
"""สายเทียบเล่ม PDF รับคำขอพร้อมกันได้โดยไม่หลุดกติกา (หน้าบ้าน ``/r/`` ยิงคำขอพร้อมกัน · แจ้งจากแชตหน้าบ้าน 26 ต.ค.)

1. ทุกเส้นทาง ``/pdfpair/*`` · ``/projects/{pid}/pdfpair`` · ``/api/pdfpair/*`` ไม่ทำงานที่บล็อก (SQLite · อ่านชั้นเล่ม)
   บน event loop — วนจาก **รายการเส้นทางจริงของแอป** + ตัวควบคุมที่ต้องจับเส้นทาง ``async`` ที่บล็อกได้จริง
2. คำขอเร็วไม่ต้องรอคำขอช้า (ภาพหน้า/คำนวณ) ที่กำลังทำงาน + ตัวควบคุมว่าวิธีวัดจับการบล็อกได้
3. ผลที่แยก JSON ไว้ของรอบ (แคช): คำตัดสินอ่านใหม่ทุกครั้ง · รอบที่ไม่มีในฐานข้อมูลแล้วไม่ถูกเสิร์ฟ · มีขอบเขต ·
   ผู้เรียกตั้งค่าช่องของข้อเท็จจริงแล้วไม่รั่วเข้าแคช
4. ด่านในธุรกรรมเขียน: รอบถูกแทนหลังผู้เรียกตรวจไปแล้ว · เปลี่ยนค่าเดิมโดยไม่มีหมายเหตุ — บันทึกผล/ยืนยันปี/ส่งออก
   ถูกปฏิเสธ และไม่มีอะไรถูกเขียน (ทั้งชั้นที่เก็บ · ชั้นบริการ · API)
5. รายการรอบ: ป้าย/ไฟล์ของสองฉบับ + จำนวนข้อ ตรงกับ :class:`RunView` · ตัวเลือกคำตัดสินบอกผลต่อการใช้ผล

🔴 SYNTHETIC DEMONSTRATION DATA — ชั้นเล่มสังเคราะห์ชุดเดียวกับ ``test_trial.py``
"""
import asyncio
import concurrent.futures as cf
import re
import threading
import time

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from test_trial import AG, _env, client, shelf  # noqa: F401  (fixture ร่วม)
from test_api_pdfpair import _tamper_year
from redbook.app import create_app
from redbook.evidence import pdftext
from redbook.services import pdfpair as svc, pdfshelf
from redbook.storage import audit, files as filestore, pdfpair_repo, repository, source_pdfs
from redbook.storage.db import connect
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD

pytestmark = pytest.mark.skipif(pdftext.product_backend() is None, reason="ไม่มี pdfplumber + pypdfium2")


@pytest.fixture(autouse=True)
def _fresh_runs(monkeypatch):
    """เทสต์ในไฟล์นี้ต้องการรอบใหม่ทุกครั้งที่เรียก ``pdfshelf.start`` — ปิดการกันกดซ้ำ (เทสต์ของมันอยู่ test_pdf_upload.py)"""
    monkeypatch.setattr(pdfshelf, "START_DEDUPE_S", -1.0)

_LANE = re.compile(r"^(/pdfpair|/api/pdfpair|/projects/\{pid\}/pdfpair)")


def _new_run():
    return pdfshelf.start("S_2570_draft", "S_2570_act", AG)


def _fill(path, **ids):
    return re.sub(r"\{(\w+)(?::[^}]*)?\}", lambda m: ids.get(m.group(1), "x"), path)


def _on_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _audit_rows():
    return audit.verify_chain()["checked"]


class _Watch:
    """จับว่างานที่บล็อกถูกเรียกจากเส้นทางไหน และเรียกบน event loop หรือไม่"""

    def __init__(self, monkeypatch):
        self.route, self.calls = "", []
        for mod, name in ((pdfpair_repo, "connect"), (source_pdfs, "connect"), (repository, "connect"),
                          (pdfshelf, "volumes"), (filestore, "save_stream")):
            self._spy(monkeypatch, mod, name)

    def _spy(self, monkeypatch, mod, name):
        real = getattr(mod, name)

        def spy(*a, **k):
            self.calls.append((self.route, _on_loop()))
            return real(*a, **k)
        monkeypatch.setattr(mod, name, spy)

    def walk(self, c, routes, ids):
        tok = c.cookies.get(CSRF_COOKIE) or c.get("/api/csrf").json()["token"]
        body = {"choice": "checked", "note": "", "side": "A", "year": "2570", "a": "S_2570_draft",
                "b": "S_2570_act", "agency": AG}
        for method, path in sorted(routes, key=lambda x: (x[0] != "GET", x[1])):
            self.route = f"{method} {path}"
            url = _fill(path, **ids)
            if method == "GET":
                c.get(url, follow_redirects=False)
            elif path == "/api/pdfpair/uploads":      # multipart · ไฟล์จากชั้นเล่มสังเคราะห์
                with open(pdfshelf.get("S_2570_draft").path, "rb") as fh:
                    c.post(url, data={"side": "A"}, files={"file": ("a.pdf", fh, "application/pdf")},
                           headers={"X-CSRF-Token": tok})
            elif path.startswith("/api/"):
                c.post(url, json={**body, "seen": True}, headers={"X-CSRF-Token": tok}, follow_redirects=False)
            else:
                c.post(url, data={**body, "seen": "1", CSRF_FIELD: tok}, follow_redirects=False)
        self.route = ""

    @property
    def on_loop(self):
        return sorted({r for r, loop in self.calls if loop and r})

    @property
    def touched(self):
        return {r for r, _loop in self.calls if r}


def _lane_routes(app):
    return sorted((m, r.path) for r in app.routes if isinstance(r, APIRoute) and _LANE.match(r.path)
                  for m in r.methods)


# ── 1. ไม่มีงานที่บล็อกบน event loop ─────────────────────────────────────────────────────
def test_no_lane_route_blocks_the_event_loop(client, monkeypatch):
    pid, rid = _new_run()
    v = svc.view(rid)
    fid = next(f.id for f in v.result.findings if not f.info and f.a.page)
    routes = _lane_routes(client.app)
    assert {("GET", "/pdfpair/runs/{rid}/f/{fid}/{side}.png"), ("POST", "/api/pdfpair/runs/{rid}/f/{fid}/decide"),
            ("GET", "/api/pdfpair/runs"), ("POST", "/projects/{pid}/pdfpair")} <= set(routes)   # รายการจริง
    w = _Watch(monkeypatch)
    w.walk(client, routes, {"rid": rid, "fid": fid, "side": "A", "n": "1", "pid": pid})
    assert w.on_loop == []
    assert {f"{m} {p}" for m, p in routes} <= w.touched      # ทุกเส้นทางทำงานจริง (ไม่ผ่านเพราะไม่ได้แตะอะไร)


def test_watch_catches_an_async_route_that_blocks(monkeypatch):
    """ตัวควบคุม: เส้นทาง async ที่เรียกที่เก็บข้อมูลตรง ๆ ต้องถูกจับ — ส่วนเส้นทางจริงข้างกันไม่ถูกจับ"""
    app = create_app()

    @app.get("/api/pdfpair/zz_blocking")
    async def zz_blocking():
        pdfpair_repo.list_runs(limit=1)
        return {"ok": True}
    with TestClient(app) as c:
        c.get("/api/csrf")
        w = _Watch(monkeypatch)
        w.walk(c, [("GET", "/api/pdfpair/zz_blocking"), ("GET", "/api/pdfpair/runs")], {})
    assert w.on_loop == ["GET /api/pdfpair/zz_blocking"]
    assert "GET /api/pdfpair/runs" in w.touched


# ── 2. คำขอเร็วไม่ต่อคิวหลังคำขอช้า ──────────────────────────────────────────────────────────
SLOW_S = 3.0


def _fast_while_slow(c, slow_url, fast_url, started: threading.Event) -> tuple[float, bool]:
    with cf.ThreadPoolExecutor(1) as pool:
        slow = pool.submit(c.get, slow_url)
        assert started.wait(5)
        t = time.perf_counter()
        r = c.get(fast_url)
        took, slow_still_running = time.perf_counter() - t, not slow.done()
        assert r.status_code == 200 and slow.result().status_code == 200
    return took, slow_still_running


def test_fast_request_does_not_wait_for_a_slow_page_render(client, monkeypatch):
    _pid, rid = _new_run()
    assert client.get(f"/api/pdfpair/runs/{rid}").status_code == 200   # อุ่นผลรอบก่อนวัด (วัดการต่อคิว ไม่ใช่การแยก JSON)
    started = threading.Event()

    def slow_page(*_a, **_k):
        started.set()
        time.sleep(SLOW_S)
        return b"\x89PNG"
    monkeypatch.setattr(svc, "page_png", slow_page)
    took, still = _fast_while_slow(client, f"/pdfpair/runs/{rid}/page/A/1.png", f"/api/pdfpair/runs/{rid}",
                                   started)
    assert took < SLOW_S / 2 and still


def test_fast_while_slow_detects_a_blocking_route():
    """ตัวควบคุม: เส้นทาง async ที่บล็อก event loop ทำให้คำขอเร็วต้องรอจริง (วิธีวัดข้างบนไม่ผ่านฟรี)"""
    app = create_app()
    started = threading.Event()

    @app.get("/api/pdfpair/zz_slow")
    async def zz_slow():
        started.set()
        time.sleep(SLOW_S)
        return {"ok": True}
    with TestClient(app) as c:
        took, still = _fast_while_slow(c, "/api/pdfpair/zz_slow", "/api/csrf", started)
    assert took >= SLOW_S / 2      # ต้องรอจริง (ไม่ตรวจ "ช้าเสร็จแล้ว" — สองคำตอบกลับมาพร้อมกันได้เมื่อ loop ว่าง)
    del still


# ── 3. แคชผลที่แยก JSON แล้วของรอบ ──────────────────────────────────────────────────────────
def test_cached_run_reads_fresh_state_and_never_serves_a_deleted_run(client):
    _pid, rid = _new_run()
    v1 = svc.view(rid)
    fid = next(f.id for f in v1.result.findings if not f.info)
    svc.decide(rid, fid, "checked", "")
    v2 = svc.view(rid)
    assert v2.result is v1.result                              # แยก JSON ครั้งเดียว ใช้ร่วม
    assert fid in v2.decisions and fid not in v1.decisions     # คำตัดสินอ่านใหม่ทุกครั้ง
    year = v1.facts_b.fiscal_year
    v2.facts_b.fiscal_year, v2.run["agency"] = None, "แก้ในคำขอเดียว"
    v3 = svc.view(rid)
    assert (v3.facts_b.fiscal_year, v3.run["agency"]) == (year, AG)  # ไม่รั่วเข้าแคช
    conn = connect()
    try:
        conn.execute("DELETE FROM pdfpair_runs WHERE id = ?", (rid,))   # จำลองแถวรอบถูกลบ
    finally:
        conn.close()
    assert svc.view(rid) is None
    assert client.get(f"/api/pdfpair/runs/{rid}").json()["code"] == "not_found"
    assert client.get(f"/pdfpair/runs/{rid}/page/A/1.png").status_code == 404


def test_run_cache_is_bounded(client, monkeypatch):
    monkeypatch.setattr(svc, "RUN_CACHE_MAX", 1)
    a, b = _new_run()[1], _new_run()[1]
    svc.view(a), svc.view(b)
    assert [k[1] for k in svc._run_mem] == [b]
    assert svc.view(a).rid == a and [k[1] for k in svc._run_mem] == [a]


# ── 4. ด่านในธุรกรรมเขียน ───────────────────────────────────────────────────────────────────
def _link(old, new="pp_winner_test"):
    """จำลองการคำนวณซ้ำที่ commit หลังผู้เรียกตรวจสถานะรอบไปแล้ว"""
    conn = connect()
    try:
        conn.execute("INSERT INTO pdfpair_run_links (old_run_id, new_run_id, reason, created_at) VALUES (?,?,?,?)",
                     (old, new, "เทสต์", "2026-10-26T00:00:00+07:00"))
    finally:
        conn.close()
    return new


def test_repo_writes_recheck_inside_the_transaction(client):
    _pid, rid = _new_run()
    fid = next(f.id for f in svc.view(rid).result.findings if not f.info)
    pdfpair_repo.decide(rid, fid, "checked", "")
    with pytest.raises(pdfpair_repo.NoteRequired):
        pdfpair_repo.decide(rid, fid, "mismatch", "  ")
    pdfpair_repo.confirm_year(rid, "B", 2570, "", {})
    with pytest.raises(pdfpair_repo.NoteRequired):
        pdfpair_repo.confirm_year(rid, "B", 2569, "", {})
    new = _link(rid)
    rows = _audit_rows()
    for write in (lambda: pdfpair_repo.decide(rid, fid, "mismatch", "เหตุผล"),
                  lambda: pdfpair_repo.confirm_year(rid, "A", 2570, "เหตุผล", {}),
                  lambda: pdfpair_repo.record_export(rid, "0" * 64, 1)):
        with pytest.raises(pdfpair_repo.SupersededError) as e:
            write()
        assert e.value.new_run_id == new
    assert _audit_rows() == rows
    st = pdfpair_repo.run_state(rid)
    assert st["decisions"][fid]["choice"] == "checked" and set(st["year_confirms"]) == {"B"}


def test_service_and_api_refuse_when_superseded_after_the_check(client, monkeypatch):
    _pid, rid = _new_run()
    stale = svc.view(rid)                                      # มุมมองก่อนรอบถูกแทน
    for f in stale.result.findings:
        if not f.info:
            svc.decide(rid, f.id, "checked", "")
    stale = svc.view(rid)
    assert svc.preflight(rid, stale).ok
    fid = next(f.id for f in stale.result.findings if not f.info)
    new = _link(rid)
    monkeypatch.setattr(svc, "view", lambda r: stale if r == rid else None)
    rows = _audit_rows()
    with pytest.raises(svc.RunSuperseded) as e:
        svc.decide(rid, fid, "fix", "เปลี่ยนเพราะเทสต์")
    assert e.value.new_run_id == new
    with pytest.raises(svc.RunSuperseded):
        svc.export_csv_checked(rid)                           # ผ่านด่านบนมุมมองเก่า แต่ธุรกรรมจับได้ = ไม่บันทึก
    h = {"X-CSRF-Token": client.get("/api/csrf").json()["token"]}
    r = client.post(f"/api/pdfpair/runs/{rid}/f/{fid}/decide", json={"choice": "fix", "note": "x"}, headers=h)
    assert (r.status_code, r.json()["code"]) == (409, "superseded")
    r = client.post(f"/api/pdfpair/runs/{rid}/year", json={"side": "A", "year": "2570", "seen": True}, headers=h)
    assert (r.status_code, r.json()["code"]) == (409, "superseded")
    assert client.get(f"/pdfpair/runs/{rid}/export.csv").status_code == 409
    assert _audit_rows() == rows


# ── 5. รายการรอบ + ผลของตัวเลือกคำตัดสิน ─────────────────────────────────────────────────────
def _listed(client, rid):
    return next(r for r in client.get("/api/pdfpair/runs?limit=200").json()["runs"] if r["id"] == rid)


def test_run_list_sides_and_counts_match_the_run_view(client):
    _pid, rid = _new_run()
    fid = next(f.id for f in svc.view(rid).result.findings if not f.info)
    svc.decide(rid, fid, "checked", "")
    _tamper_year(rid, "B", None, "not_found")
    v = svc.view(rid)
    row = _listed(client, rid)
    assert row["counts"] == {"actionable": v.actionable, "pending": v.pending} and v.pending == v.actionable - 1
    assert row["sides"] == {s: {"label": v.side_label(s), "file": v.run[f"{s.lower()}_name"]} for s in "AB"}
    assert "ไม่ทราบปีงบ" in row["sides"]["B"]["label"]
    svc.confirm_year(rid, "B", "2570", "ปกหน้า 1", True)      # สถานะที่เปลี่ยนได้ไม่ถูกแคช
    row = _listed(client, rid)
    assert row["sides"]["B"]["label"] == svc.view(rid).side_label("B") and "ผู้ตรวจยืนยัน" in row["sides"]["B"]["label"]


def test_decision_choices_say_what_each_does_to_use(client):
    _pid, rid = _new_run()
    got = client.get(f"/api/pdfpair/runs/{rid}").json()["decisions"]
    assert [d["key"] for d in got] == [k for k, _label in svc.DECISIONS]
    for d in got:
        assert d["use"] == svc.DECISION_USE.get(d["key"], "open") and d["use_label"] == svc.USE_LABELS[d["use"]]
    assert {d["use"] for d in got} == {"usable", "excluded", "open"}
