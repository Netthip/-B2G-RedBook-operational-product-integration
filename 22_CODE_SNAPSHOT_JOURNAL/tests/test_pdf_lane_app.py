# -*- coding: utf-8 -*-
"""เซิร์ฟเวอร์สาย PDF เท่านั้น (#42 ทางเลือก ก · กิ๊ฟเลือก 26 ต.ค.) — หลักฐานว่าเส้นทาง Excel ไม่ถูกเรียกใน process นี้

1. วนทุกเส้นทางจริงของแอป: นอกสาย PDF = 404 และ **ไม่ถึงแอป** · ในสาย PDF = ถึงแอป
2. เดินสาย PDF ครบ (หน้าเดิม + API + ภาพหลักฐาน/ภาพหน้า + สายทดลอง): ไม่มีการเรียกบริการวาดภาพของสาย Excel ·
   ทุกการวาด PDFium ถือกุญแจร่วม (ตัวนับการวาดที่ถูกปฏิเสธ = 0 และมีการวาดจริง > 0)
3. ตัวควบคุม: เส้นทางวาดภาพของสาย Excel ที่ไม่ถือกุญแจ ถูกด่านปฏิเสธและนับได้จริง

🔴 SYNTHETIC DEMONSTRATION DATA — ชั้นเล่มสังเคราะห์ชุดเดียวกับ ``test_trial.py``
"""
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from test_trial import AG, _env, client, shelf  # noqa: F401  (fixture ร่วม)
from test_pdfpair_concurrency import _Watch, _fill, _lane_routes
from redbook import pdf_lane_app as lane
from redbook.app import create_app
from redbook.evidence import pdftext
from redbook.pdfbook import reader
from redbook.services import evidence as evidence_service, pdf_evidence, pdfpair as svc, pdfshelf, trial

pytestmark = pytest.mark.skipif(pdftext.product_backend() is None, reason="ไม่มี pdfplumber + pypdfium2")


@pytest.fixture()
def lane_client(monkeypatch):
    lane.install_pdfium_guard(monkeypatch.setattr)          # ถอดคืนหลังเทสต์ (ไม่กระทบเทสต์สาย Excel)
    for k in lane.STATS:
        monkeypatch.setitem(lane.STATS, k, 0)
    with TestClient(lane.create_lane_app(guard=False), base_url="http://127.0.0.1") as c:
        c.get("/api/csrf")
        yield c


def test_every_route_outside_the_pdf_lane_is_closed_before_the_app(lane_client):
    inner = lane_client.app.app
    seen = []

    async def spy(scope, receive, send):                       # จับว่าคำขอถึงแอปหรือไม่
        if scope["type"] == "http":
            seen.append(scope["path"])
        return await inner(scope, receive, send)
    lane_client.app.app = spy
    closed = opened = 0
    for r in create_app().routes:
        if not isinstance(r, APIRoute):
            continue
        path = _fill(r.path, pid="p", rid="r", fid="f", sid="s", side="A", n="1", name="x", book_id="b",
                     document_id="d", page_no="1", file_id="f", run_id="r", mapping_id="m", mid="m")
        for m in r.methods:
            seen.clear()
            resp = lane_client.request(m, path, follow_redirects=False)
            if lane.allowed(path) or path == "/":
                opened += 1
                assert seen == [path] or (path == "/" and resp.status_code == 303), (m, path)
            else:
                closed += 1
                assert (resp.status_code, seen) == (404, []), (m, path)
    lane_client.app.app = inner
    assert closed > 60 and opened > 30                          # ปิดสาย Excel/T1B/หลักฐาน/ตัวชี้วัดจริง ไม่ใช่รายการว่าง
    for p in ("/t1b/runs", "/evidence/d/page/1.png", "/indicators/runs", "/projects/p", "/books", "/queue"):
        assert not lane.allowed(p)
    assert lane_client.get("/api/lane").json()["blocked_requests"] == closed


def test_foreign_host_header_is_refused_before_the_app(lane_client):
    """DNS rebinding (#23 F-01) — ชั่วคราวในเซิร์ฟเวอร์สาย PDF จนกว่าการแก้ของ #23 จะรวมเข้าสายนี้"""
    for host in ("evil.example", "evil.example:8645", "127.0.0.1.evil.example", ""):
        r = lane_client.get("/r/p", headers={"Host": host})
        assert r.status_code == 400, host
    for host in ("127.0.0.1:8645", "localhost", "LOCALHOST:8644", "[::1]:8645"):
        assert lane_client.get("/healthz", headers={"Host": host}).status_code == 200, host
    assert lane_client.get("/api/lane").json()["host_rejected"] == 4


def test_pdf_lane_walk_never_reaches_excel_rendering(lane_client, monkeypatch):
    excel_calls = []
    for mod, name in ((evidence_service, "render_page_png"), (pdf_evidence, "render")):
        real = getattr(mod, name)
        monkeypatch.setattr(mod, name, lambda *a, _n=f"{mod.__name__}.{name}", _r=real, **k:
                            excel_calls.append(_n) or _r(*a, **k))
    pid, rid = pdfshelf.start("S_2570_draft", "S_2570_act", AG)
    v = svc.view(rid)
    fid = next(f.id for f in v.result.findings if not f.info and f.a.page)
    sid = trial.start("t1", "lane-proof", again=True)
    svc.clear_png_cache()
    w = _Watch(monkeypatch)
    routes = [(m, p) for m, p in _lane_routes(lane_client.app.app) if lane.allowed(_fill(p, pid=pid))]
    w.walk(lane_client, routes, {"rid": rid, "fid": fid, "side": "A", "n": "1", "pid": pid})
    for path in (f"/trial/s/{sid}", f"/trial/s/{sid}/page/cur/{trial.session(sid).pages('cur')[0]}.png"):
        assert lane_client.get(path).status_code == 200
    st = lane_client.get("/api/lane").json()
    assert excel_calls == []
    assert st["refused_unlocked_renders"] == 0 and st["locked_renders"] > 0      # วาดจริง และทุกครั้งถือกุญแจ


def test_guard_refuses_an_unlocked_excel_style_render(lane_client):
    """ตัวควบคุม: วาดผ่าน backend ตรง ๆ แบบสาย Excel (ไม่ถือกุญแจ) ต้องถูกปฏิเสธและนับ"""
    path = pdfshelf.volumes()[0].path
    with pytest.raises(RuntimeError, match="outside the shared lock"):
        pdftext.product_backend().render_png(path, 1)
    assert lane_client.get("/api/lane").json()["refused_unlocked_renders"] == 1
    assert reader.render_png(path, 1)[:4] == b"\x89PNG"                            # ทางสาย PDF ผ่าน
