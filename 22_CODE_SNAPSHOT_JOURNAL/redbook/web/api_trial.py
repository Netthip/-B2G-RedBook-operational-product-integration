# -*- coding: utf-8 -*-
"""JSON API ของ "ทดลองตรวจเล่ม" สำหรับหน้าบ้าน Svelte (``frontend/`` → ``/r/``)

* เรียกชั้นบริการ :mod:`redbook.services.trial` เท่านั้น — กติกาเดียวกับหน้าเว็บเดิมทุกข้อ
  (ไม่มีผลเทียบก่อนล็อก · ล็อกต้องครบทุกหน้า · ข้อเสนอคู่ ≠ พบ · สรุปมีแต่จำนวน)
* ด่านกลางจาก :mod:`.api_common` (สัญญา ``docs/API_CONTRACT_R.md``): CSRF ในหัว ``X-CSRF-Token`` ·
  body ≤ 64 KB · ข้อผิดพลาด = ``{"error", "code"}`` — ``not_found`` 404 · ``locked`` 409 (ส่งผลแล้ว แก้ไม่ได้) ·
  ``not_locked`` 409 (ยังไม่ส่งผล จึงยังไม่มีผลระบบ) · ``invalid`` 400 · ``csrf`` 403 · ``server`` 500 (+ ``error_id``)
* ข้อสังเกตส่ง :func:`api_common.finding_extras` ต่อท้ายเสมอ — คำเตือน "ต้องให้คนยืนยัน" ไปถึงหน้าที่ใช้ผล
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse

from .. import config
from ..services import pdfpair, pdfshelf, trial as svc
from ..storage import trial_repo
from .api_common import ApiError, api, finding_extras, read_json

APP_DIR = config.PROJECT_ROOT / "redbook" / "static" / "app"


def _need(sid: str, *, locked: bool | None = None):
    """รอบตรวจ — ไม่พบ = 404 · ``locked=False`` ต้องยังไม่ส่งผล (409 locked) · ``locked=True`` ต้องส่งผลแล้ว (409 not_locked)"""
    s = svc.session(sid)
    if s is None:
        raise ApiError("ไม่พบรอบตรวจ", 404, "not_found")
    if locked is False and s.locked:
        raise ApiError("ส่งผลตรวจแล้ว — แก้จุดที่วงไม่ได้ (ผลเดิมเก็บไว้ตามเดิม)", 409, "locked")
    if locked is True and not s.locked:
        raise ApiError("ต้องส่งผลตรวจก่อน ระบบจึงเทียบให้ดู", 409, "not_locked")
    return s


def _session(s) -> dict:
    b = s.book
    return {"sid": s.sid, "locked": s.locked, "locked_at": s.rec["locked_at"], "reviewer": s.rec["reviewer"],
            "book": {"id": b["id"], "title": b["title"], "agency": b["agency"], "pair": b["pair"],
                     "cur": {"title": b["cur"]["title"], "fy": b["cur"]["fiscal_year"]},
                     "prev": {"title": b["prev"]["title"], "fy": b["prev"]["fiscal_year"]}},
            "pages": {"cur": s.pages("cur"), "prev": s.pages("prev")},
            "done": sorted(p for side, p in s.done if side == "cur"),
            "marks": [_mark(m) for m in s.marks]}


def _mark(m: dict) -> dict:
    return {k: m[k] for k in ("id", "side", "page", "fx", "fy", "pen", "topic", "note")}


def _finding(f, rid: str) -> dict:
    return {"id": f.id, "subject": f.subject, "kind": f.kind_label, "column": f.column, "topic": f.topic_label,
            "within": f.within, "page_cur": f.b.page, "page_prev": f.a.page,
            "a": pdfpair.amount_text(f.a) if (f.a.value or f.a.status) else "",
            "b": pdfpair.amount_text(f.b) if (f.b.value or f.b.status) else "",
            "evidence": f"/pdfpair/runs/{rid}/f/{f.id}", **finding_extras(f)}


def _result(r) -> dict:
    rid = r.view.rid
    marks = []
    for m in r.s.marks:
        ln = r.links.get(m["id"]) or {}
        f = r.finding(ln.get("finding_id", ""))
        marks.append({**_mark(m), "proposed": bool(ln.get("proposed")), "verdict": ln.get("verdict", ""),
                      "finding": _finding(f, rid) if f else None,
                      "candidates": [_finding(c, rid) for c in svc.candidates(r, m)]})
    return {"session": _session(r.s), "metrics": r.metrics, "complete": r.complete, "marks": marks,
            "extras": [{**_finding(f, rid), "verdict": r.extras.get(f.id, "")} for f in r.unlinked_findings],
            "versions": r.view.run["versions"], "answers": r.answers}


def register(app) -> None:
    trial_repo.init_schema()

    @app.get("/api/csrf")
    async def api_csrf(request: Request):
        return {"token": getattr(request.state, "csrf_token", "")}

    @app.get("/api/trial/meta")
    @api
    async def api_meta(request: Request):
        return {"pens": svc.PENS, "topics": [{"code": c, "label": l} for c, l in svc.TOPIC_CODES],
                "link_verdicts": svc.LINK_VERDICTS, "extra_verdicts": svc.EXTRA_VERDICTS,
                "likert": [{"group": g, "items": [{"key": k, "text": t} for k, t in items]}
                           for g, items in svc.LIKERT_ITEMS],
                "open": [{"key": k, "text": t} for k, t in svc.OPEN_ITEMS],
                "versions": {"trial": svc.TRIAL_VERSION, "pdfbook": svc.PDFBOOK_VERSION,
                             "protocol": svc.PROTOCOL_VERSION}}

    @app.get("/api/trial/books")
    @api
    async def api_books(request: Request):
        books = svc.books()
        import threading
        threading.Thread(target=pdfshelf.prewarm, args=([k for b in books for k in (b.current, b.previous)],),
                         daemon=True).start()
        st = svc.book_status()
        return {"books": [{"id": b.id, "title": b.title, "agency": b.agency, "pair": b.pair,
                           "status": st.get(b.id)} for b in books],
                "shelf": pdfshelf.shelf_label()}

    @app.post("/api/trial/start")
    @api
    async def api_start(request: Request):
        d = await read_json(request)
        sid = svc.start(str(d.get("book_id", "")), str(d.get("reviewer", "")), again=bool(d.get("again")))
        return {"sid": sid, "locked": svc.session(sid).locked}

    @app.get("/api/trial/s/{sid}")
    @api
    async def api_session(request: Request, sid: str):
        return _session(_need(sid))

    @app.post("/api/trial/s/{sid}/marks")
    @api
    async def api_mark_add(request: Request, sid: str):
        d = await read_json(request)
        _need(sid, locked=False)
        return _mark(svc.add_mark(sid, d.get("side", ""), d.get("page"), d.get("fx"), d.get("fy"), d.get("pen", "")))

    @app.post("/api/trial/s/{sid}/marks/{mid}")
    @api
    async def api_mark_edit(request: Request, sid: str, mid: str):
        d = await read_json(request)
        _need(sid, locked=False)
        svc.update_mark(sid, mid, topic=d.get("topic"), note=d.get("note"), pen=d.get("pen"),
                        delete=bool(d.get("delete")))
        return {"ok": True}

    @app.post("/api/trial/s/{sid}/done")
    @api
    async def api_done(request: Request, sid: str):
        d = await read_json(request)
        _need(sid, locked=False)
        svc.page_done(sid, "cur", d.get("page"))
        return {"ok": True}

    @app.post("/api/trial/s/{sid}/undone")
    @api
    async def api_undone(request: Request, sid: str):
        """ยกเลิก "ตรวจหน้านี้แล้ว" (กดพลาด) — ก่อนส่งผลเท่านั้น · ยังไม่เคยกด = ``undone: false`` ไม่ error"""
        d = await read_json(request)
        _need(sid, locked=False)
        return {"ok": True, "undone": bool(svc.page_undone(sid, "cur", d.get("page")))}

    @app.post("/api/trial/s/{sid}/view")
    @api
    async def api_view(request: Request, sid: str):
        d = await read_json(request)
        _need(sid)
        svc.log_view(sid, d.get("cur"), d.get("prev") or 0)
        return {"ok": True}

    @app.post("/api/trial/s/{sid}/lock")
    @api
    async def api_lock(request: Request, sid: str):
        d = await read_json(request)
        _need(sid, locked=False)
        if not d.get("confirm"):
            raise ApiError("ติ๊กยืนยันก่อนส่ง — ส่งแล้วแก้จุดที่วงไม่ได้")
        svc.lock(sid)
        return {"ok": True}

    @app.get("/api/trial/s/{sid}/result")
    @api
    async def api_result(request: Request, sid: str):
        _need(sid, locked=True)
        return _result(svc.result(sid))

    @app.post("/api/trial/s/{sid}/link/{mid}")
    @api
    async def api_link(request: Request, sid: str, mid: str):
        d = await read_json(request)
        _need(sid, locked=True)
        svc.decide_link(sid, mid, str(d.get("verdict", "")), str(d.get("finding_id", "")))
        return _result(svc.result(sid))

    @app.post("/api/trial/s/{sid}/extra/{fid}")
    @api
    async def api_extra(request: Request, sid: str, fid: str):
        d = await read_json(request)
        _need(sid, locked=True)
        svc.decide_extra(sid, fid, str(d.get("verdict", "")))
        return _result(svc.result(sid))

    @app.post("/api/trial/s/{sid}/survey")
    @api
    async def api_survey(request: Request, sid: str):
        d = await read_json(request)
        _need(sid)
        svc.save_answers(sid, {k: v for k, v in d.items() if isinstance(v, str)})
        return {"ok": True, "answers": trial_repo.answers(sid)}

    # ── หน้าบ้าน (ไฟล์ที่ build แล้ว) — ทุกเส้นทางใต้ /r/ คืน index.html (SPA) ─────────────────
    @app.get("/r", response_class=HTMLResponse)
    @app.get("/r/{path:path}", response_class=HTMLResponse)
    async def spa(path: str = ""):
        index = APP_DIR / "index.html"
        if not index.exists():
            return HTMLResponse("<p>ยังไม่ได้ build หน้าบ้าน — รัน <code>npm run build</code> ในโฟลเดอร์ frontend</p>",
                                status_code=503)
        return FileResponse(index, media_type="text/html")
