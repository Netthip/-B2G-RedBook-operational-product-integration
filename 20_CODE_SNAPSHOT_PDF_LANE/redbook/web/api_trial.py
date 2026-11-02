# -*- coding: utf-8 -*-
"""JSON API ของ "ทดลองตรวจเล่ม" สำหรับหน้าบ้าน Svelte (``frontend/`` → ``/r/``) — วิธีวัดผลฉบับ 0.2

* เรียกชั้นบริการ :mod:`redbook.services.trial` เท่านั้น — กติกาเดียวกับหน้าเว็บเดิมทุกข้อ
  (ไม่มีผลเทียบก่อนล็อก · ล็อก = ส่งใบประกาศก่อนเห็นผล ไม่ใช่กดตรวจครบทุกหน้า · ข้อเสนอคู่ ≠ พบ ·
  การเปิดดูผลไม่สร้างรอบเทียบ · สรุปมีแต่จำนวน)
* ด่านกลางจาก :mod:`.api_common` (สัญญา ``docs/API_CONTRACT_R.md``): CSRF ในหัว ``X-CSRF-Token`` ·
  body ≤ 64 KB · ข้อผิดพลาด = ``{"error", "code"}`` — ``not_found`` 404 · ``locked`` 409 (ส่งแล้ว/หยุดแล้ว แก้ไม่ได้) ·
  ``not_locked`` 409 (ยังไม่ส่ง จึงยังไม่มีผลระบบ) · ``conflict`` 409 (เทียบไม่สำเร็จ/บัญชีข้อสังเกตไม่ปิด) ·
  ``invalid`` 400 · ``csrf`` 403 · ``server`` 500 (+ ``error_id``)
* ป้ายภาษาไทยทุกชุดมาจาก ``GET /api/trial/meta`` (รหัส + ป้าย) — หน้าบ้านไม่เขียนป้ายของโดเมนเอง
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
MARK_KEYS = ("id", "side", "page", "fx", "fy", "pen", "topic", "note", "level", "cause", "part", "searched",
             "found_in", "origin", "seq", "ref", "row_source", "xtype")


def _need(sid: str, *, locked: bool | None = None, active: bool = False):
    """รอบตรวจ — ไม่พบ = 404 · ``locked=False`` ต้องยังไม่ส่ง (409 locked) · ``locked=True`` ต้องส่งแล้วและมีรอบเทียบ
    (409 not_locked / conflict) · ``active=True`` ต้องยังไม่หยุด/ถอนตัว (409 locked)"""
    s = svc.session(sid)
    if s is None:
        raise ApiError("ไม่พบรอบตรวจ", 404, "not_found")
    if active and not s.active:
        raise ApiError("รอบนี้หยุดหรือถอนตัวแล้ว — บันทึกเพิ่มไม่ได้ (ข้อมูลเดิมเก็บไว้ตามเดิม)", 409, "locked")
    if locked is False and s.locked:
        raise ApiError("ส่งใบประกาศแล้ว — แก้รายการที่ล็อกไม่ได้ (ข้อมูลเดิมเก็บไว้ตามเดิม)", 409, "locked")
    if locked is True and not s.locked:
        raise ApiError("ต้องส่งใบประกาศก่อน ระบบจึงเทียบให้ดู", 409, "not_locked")
    if locked is True and not s.rec["run_id"]:
        raise ApiError("ระบบยังเทียบไม่สำเร็จ" + (f" ({s.rec['run_error']})" if s.rec.get("run_error") else "")
                       + " — ลองเทียบอีกครั้ง", 409, "conflict")
    return s


def _mark(m: dict) -> dict:
    return {k: m.get(k, "") for k in MARK_KEYS}


def _session(s) -> dict:
    """สถานะรอบ — ก่อนล็อกไม่มีข้อมูลใดของผลระบบ (ไม่มีข้อสังเกต ไม่มีตัวนับ ไม่มีคำตัดสิน)"""
    b = s.book
    out = {"sid": s.sid, "locked": s.locked, "locked_at": s.rec["locked_at"], "reviewer": s.rec["reviewer"],
           "path": s.path, "protocol": s.protocol, "legacy": s.legacy, "read_only_legacy": s.read_only_legacy,
           "status": s.status, "active": s.active, "pair_kind": s.pair_kind, "labels": s.labels,
           "topics": [c for c, _l in svc.topic_codes(s.xkind)], "xkind": s.xkind, "v03": s.v03,
           "book": {"id": b["id"], "title": b["title"], "agency": b["agency"], "pair": b["pair"],
                    "cur": {"title": b["cur"]["title"], "fy": b["cur"]["fiscal_year"]},
                    "prev": {"title": b["prev"]["title"], "fy": b["prev"]["fiscal_year"]}},
           "pages": {"cur": s.pages("cur"), "prev": s.pages("prev")},
           "done": {"cur": s.done_pages("cur"), "prev": s.done_pages("prev")},
           "marks": [_mark(m) for m in s.circles],
           "gaps": {m["id"]: svc.mark_gaps(m, s.xkind) for m in s.circles},
           "run": {"done": bool(s.rec["run_id"]), "error": s.rec.get("run_error", ""),
                   "failures": int(s.rec.get("run_failures") or 0)},
           "use_done": bool(s.rec.get("use_done_at")), "survey_state": svc.survey_state(s),
           "consented": s.consented}
    if not s.locked and s.active:
        out["defaults"] = svc.declaration_defaults(s)
    return out


def _finding(f, rid: str, level: str = "") -> dict:
    return {"id": f.id, "subject": f.subject, "kind": f.kind_label, "column": f.column, "topic": f.topic_label,
            "topic_code": svc.SYSTEM_TOPIC_CODE.get(f.topic, ""), "level": level or svc.finding_level(f),
            "within": f.within, "page_cur": f.b.page, "page_prev": f.a.page,
            "a": pdfpair.amount_text(f.a) if (f.a.value or f.a.status) else "",
            "b": pdfpair.amount_text(f.b) if (f.b.value or f.b.status) else "",
            "evidence": f"/pdfpair/runs/{rid}/f/{f.id}", "obs_kind": svc.obs_kind(f), **finding_extras(f)}


def _history(rows: list) -> list:
    return [{"at": h["changed_at"], "before": h["before"], "after": h["after"], "reason": h["reason"]} for h in rows]


def _legacy_result(r) -> dict:
    rid = r.view.rid
    marks = []
    for m in r.s.circles:
        ln = r.links.get(m["id"]) or {}
        f = r.finding(ln.get("finding_id", ""))
        marks.append({**_mark(m), "proposed": bool(ln.get("proposed")), "verdict": ln.get("verdict", ""),
                      "finding": _finding(f, rid) if f else None})
    return {"session": _session(r.s), "legacy": True, "metrics": r.metrics, "complete": r.complete, "marks": marks,
            "extras": [{**_finding(f, rid), "verdict": r.extras.get(f.id, "")} for f in r.unlinked_findings],
            "versions": r.view.run["versions"], "answers": r.answers}


def _result(r) -> dict:
    if r.legacy:
        return _legacy_result(r)
    try:
        metrics = r.metrics
    except svc.LedgerError as e:
        raise ApiError(str(e), 409, "conflict")
    rid = r.view.rid
    issues = []
    for m in r.issues:
        d = r.decisions.get(m["id"])
        issues.append({**_mark(m), "in_scope": r.in_scope(m), "proposal": r.proposals.get(m["id"], ""),
                       "links": r.links.get(m["id"], []), "decision": d, "gaps": r.gaps(m),
                       "history": _history(r.history("issue", m["id"]))})
    body = r.decl["body"]
    return {"session": _session(r.s), "legacy": False,
            "findings": {f.id: _finding(f, rid, r.level[f.id]) for f in r.findings},
            "issues": issues,
            "unmatched": [{"id": f.id, "group": r.groups.get(f.id), "history": _history(r.history("finding", f.id))}
                          for f in r.unmatched_must],
            "info_ids": [f.id for f in r.of_level("info")], "unread_ids": [f.id for f in r.of_level("unread")],
            "read_problem_ids": {k: [f.id for f in r.findings if svc.read_problem(f) == k] for k in svc.READ_PROBLEMS},
            "review": [{"id": f.id, "reason": r.level_reason[f.id]} for f in r.of_level("review")],
            "u_ids": r.u_ids if r.s.v03 else [], "obs_eval": r.obs_eval,
            "obs_history": {fid: _history(r.history("obs", fid)) for fid in r.obs_eval},
            "metrics": metrics, "complete": r.complete,
            "declaration": {"hash": r.decl["hash"], "received_at": r.decl["received_at"], **body},
            "declaration_check": r.declaration_check, "status": svc.status_of(r.s, r),
            "notes": len(r.notes), "versions": r.view.run["versions"], "answers": r.answers}


def register(app) -> None:
    trial_repo.init_schema()

    @app.get("/api/csrf")
    async def api_csrf(request: Request):
        return {"token": getattr(request.state, "csrf_token", "")}

    @app.get("/api/trial/meta")
    @api
    async def api_meta(request: Request):
        pairs = lambda seq: [{"code": c, "label": l} for c, l in seq]     # noqa: E731
        return {"pens": svc.PENS, "levels": svc.LEVELS, "causes": svc.CAUSES, "paths": svc.PATHS,
                "topics": pairs(svc.TOPIC_CODES), "parts": pairs(svc.PARTS), "coverage": svc.COVERAGE,
                "sources": svc.SOURCES, "made": svc.MADE, "seen": svc.SEEN, "verdicts": svc.VERDICTS,
                "partial_reasons": svc.PARTIAL_REASONS, "miss_reasons": svc.MISS_REASONS, "evidence": svc.EVIDENCE,
                "basis": svc.BASIS, "groups": svc.GROUPS, "s3_reasons": svc.S3_REASONS,
                "finding_levels": svc.FINDING_LEVELS, "level_definition": svc.LEVEL_DEFINITION,
                "statuses": svc.STATUSES, "row_sources": svc.ROW_SOURCES, "post_dims": svc.POST_DIMS, "kind_labels": svc.KIND_LABELS, "xtypes": svc.XTYPES, "xtype_by_topic": svc.XTYPE_BY_TOPIC,
                "partial_reasons_v03": svc.PARTIAL_REASONS_V03, "locations": svc.LOCATIONS, "fidelity": svc.FIDELITY,
                "fidelity_reasons": svc.FIDELITY_REASONS, "assertion": svc.ASSERTION, "dim_values": svc.DIM_VALUES,
                "dims": svc.DIMS, "obs_kinds": svc.OBS_KINDS, "dims_by_obs_kind": svc.DIMS_BY_OBS_KIND,
                "likert_v03": [{"group": g, "items": [{"key": k, "text": t} for k, t in it]}
                               for g, it in svc.LIKERT_ITEMS_V03],
                "likert_scale_v03": svc.LIKERT_SCALE_V03,
                "read_problems": svc.READ_PROBLEMS, "p1_hint": svc.P1_HINT,
                "xyear": {"topics": list(svc.XYEAR_TOPICS), "label": svc.XYEAR_SCOPE_LABEL, "rule": svc.XYEAR_RULE}, "status_text": svc.STATUS_TEXT, "pair_kinds": svc.PAIR_KIND_LABELS,
                "survey_state_text": svc.SURVEY_STATE_TEXT,
                "consent": [{"key": k, "text": t} for k, t in svc.CONSENT_ITEMS],
                "steps": [{"key": k, "text": t} for k, t in svc.STEPS], "step_choices": svc.STEP_CHOICES,
                "likert": [{"group": g, "items": [{"key": k, "text": t} for k, t in items]}
                           for g, items in svc.LIKERT_ITEMS],
                "open": [{"key": k, "text": t} for k, t in svc.OPEN_ITEMS],
                "general": [{"key": k, "text": t, "choices": c} for k, t, c in svc.GENERAL_ITEMS],
                "legacy_link_verdicts": svc.LEGACY_LINK_VERDICTS,
                "legacy_extra_verdicts": svc.LEGACY_EXTRA_VERDICTS,
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
        return {"books": [{"id": b.id, "title": b.title, "agency": b.agency, "pair": b.pair, "pair_kind": b.pair_kind,
                           "status": st.get(b.id)} for b in books],
                "shelf": pdfshelf.shelf_label()}

    @app.post("/api/trial/start")
    @api
    async def api_start(request: Request):
        d = await read_json(request)
        sid = svc.start(str(d.get("book_id", "")), str(d.get("reviewer", "")), again=bool(d.get("again")),
                        path=str(d.get("path") or "r1"))
        s = svc.session(sid)
        return {"sid": sid, "locked": s.locked, "result": bool(s.locked and s.rec["run_id"])}

    @app.get("/api/trial/s/{sid}")
    @api
    async def api_session(request: Request, sid: str):
        return _session(_need(sid))

    @app.post("/api/trial/s/{sid}/path")
    @api
    async def api_path(request: Request, sid: str):
        d = await read_json(request)
        _need(sid, locked=False, active=True)
        svc.set_path(sid, str(d.get("path", "")))
        return _session(_need(sid))

    @app.post("/api/trial/s/{sid}/consent")
    @api
    async def api_consent(request: Request, sid: str):
        """ความยินยอมก่อนเริ่มทำรายการ — ``{c1, c2, c3}`` ครบทั้งสามข้อ"""
        d = await read_json(request)
        _need(sid)
        svc.give_consent(sid, {k: ("1" if v is True else str(v)) for k, v in d.items() if isinstance(v, (str, bool))})
        return _session(_need(sid))

    @app.post("/api/trial/s/{sid}/marks")
    @api
    async def api_mark_add(request: Request, sid: str):
        d = await read_json(request)
        _need(sid, locked=False, active=True)
        return _mark(svc.add_mark(sid, d.get("side", ""), d.get("page"), d.get("fx"), d.get("fy"), d.get("pen", "")))

    @app.post("/api/trial/s/{sid}/marks/{mid}")
    @api
    async def api_mark_edit(request: Request, sid: str, mid: str):
        d = await read_json(request)
        _need(sid, locked=False, active=True)
        svc.update_mark(sid, mid, topic=d.get("topic"), note=d.get("note"), pen=d.get("pen"), level=d.get("level"),
                        cause=d.get("cause"), part=d.get("part"), searched=d.get("searched"),
                        delete=bool(d.get("delete")), xtype=d.get("xtype"))
        return {"ok": True}

    @app.post("/api/trial/s/{sid}/done")
    @api
    async def api_done(request: Request, sid: str):
        """"ตรวจหน้านี้แล้ว" = ดูหน้านี้ครบ (ไม่ใช่ "ถูกต้อง") — ตัวช่วยของผู้ตรวจ ไม่ใช่เงื่อนไขการส่ง"""
        d = await read_json(request)
        _need(sid, locked=False, active=True)
        svc.page_done(sid, str(d.get("side") or "cur"), d.get("page"))
        return {"ok": True}

    @app.post("/api/trial/s/{sid}/undone")
    @api
    async def api_undone(request: Request, sid: str):
        """ยกเลิก "ตรวจหน้านี้แล้ว" (กดพลาด) — ก่อนส่งเท่านั้น · ยังไม่เคยกด = ``undone: false`` ไม่ error"""
        d = await read_json(request)
        _need(sid, locked=False, active=True)
        return {"ok": True, "undone": bool(svc.page_undone(sid, str(d.get("side") or "cur"), d.get("page")))}

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
        """ส่งใบประกาศก่อนเห็นผล (= ล็อก) → ระบบเทียบครั้งเดียว · เทียบไม่สำเร็จ = ``run: false`` + เหตุ (ใบประกาศยังอยู่)"""
        d = await read_json(request)
        _need(sid, locked=False, active=True)
        form = {k: ("1" if v is True else "" if v is False else str(v)) for k, v in d.items()
                if isinstance(v, (str, int, bool))}
        rid = svc.lock(sid, form)
        s = svc.session(sid)
        return {"ok": True, "run": bool(rid), "run_error": s.rec.get("run_error", "") if not rid else ""}

    @app.post("/api/trial/s/{sid}/run")
    @api
    async def api_run(request: Request, sid: str):
        """ลองเทียบอีกครั้ง — เมื่อรอบเทียบล้มเหลวหลังส่งใบประกาศ"""
        await read_json(request)
        s = _need(sid, active=True)
        if not s.locked:
            raise ApiError("ต้องส่งใบประกาศก่อน ระบบจึงเทียบให้ดู", 409, "not_locked")
        try:
            svc.retry_run(sid)
        except svc.TrialError as e:
            raise ApiError(str(e), 409, "conflict")
        return {"ok": True}

    @app.get("/api/trial/s/{sid}/result")
    @api
    async def api_result(request: Request, sid: str):
        _need(sid, locked=True)
        return _result(svc.result(sid))

    @app.post("/api/trial/s/{sid}/row/{mid}")
    @api
    async def api_row(request: Request, sid: str, mid: str):
        d = await read_json(request)
        _need(sid, locked=True, active=True)
        svc.update_row(sid, mid, part=d.get("part"), cause=d.get("cause"), level=d.get("level"),
                       found_in=d.get("found_in"), searched=d.get("searched"), side=d.get("side"),
                       page=d.get("page"), ref=d.get("ref"), row_source=d.get("row_source"), xtype=d.get("xtype"))
        return _result(svc.result(sid))

    @app.post("/api/trial/s/{sid}/issue/{mid}")
    @api
    async def api_issue(request: Request, sid: str, mid: str):
        d = await read_json(request)
        _need(sid, locked=True, active=True)
        ids = d.get("finding_ids") or []
        svc.decide_issue(sid, mid, str(d.get("verdict", "")), [str(x) for x in ids] if isinstance(ids, list) else [],
                         reason=str(d.get("reason", "")), evidence=str(d.get("evidence", "")),
                         basis=str(d.get("basis", "")), change_reason=str(d.get("change_reason", "")),
                         location=str(d.get("location", "")),
                         relevant_sides=[str(x) for x in d.get("relevant_sides") or [] if str(x)]
                         if isinstance(d.get("relevant_sides"), list) else [],
                         search_scope=str(d.get("search_scope", "")))
        return _result(svc.result(sid))

    @app.post("/api/trial/s/{sid}/finding/{fid}")
    @api
    async def api_finding(request: Request, sid: str, fid: str):
        d = await read_json(request)
        _need(sid, locked=True, active=True)
        svc.decide_finding(sid, fid, str(d.get("group", "")), s3_reason=str(d.get("s3_reason", "")),
                           basis=str(d.get("basis", "")), issue_ref=str(d.get("issue_ref", "")),
                           change_reason=str(d.get("change_reason", "")), part=str(d.get("part", "")),
                           note=str(d.get("note", "")))
        return _result(svc.result(sid))

    @app.post("/api/trial/s/{sid}/obs/{fid}")
    @api
    async def api_obs(request: Request, sid: str, fid: str):
        d = await read_json(request)
        _need(sid, locked=True, active=True)
        dims = d.get("dims") if isinstance(d.get("dims"), dict) else {}
        svc.decide_obs(sid, fid, str(d.get("fidelity", "")), fidelity_reason=str(d.get("fidelity_reason", "")),
                       dims={str(k): str(v) for k, v in dims.items()},
                       assertion_undecidable=bool(d.get("assertion_undecidable")), basis=str(d.get("basis", "")),
                       change_reason=str(d.get("change_reason", "")))
        return _result(svc.result(sid))

    @app.post("/api/trial/s/{sid}/note")
    @api
    async def api_note(request: Request, sid: str):
        d = await read_json(request)
        _need(sid, locked=True, active=True)
        svc.add_post_note(sid, str(d.get("part", "")), str(d.get("topic", "")), str(d.get("note", "")))
        return _result(svc.result(sid))

    @app.post("/api/trial/s/{sid}/finish")
    @api
    async def api_finish(request: Request, sid: str):
        d = await read_json(request)
        _need(sid, locked=True, active=True)
        svc.finish_use(sid, str(d.get("reason", "")))
        return {"ok": True, "survey_state": svc.survey_state(svc.session(sid))}

    @app.post("/api/trial/s/{sid}/status")
    @api
    async def api_status(request: Request, sid: str):
        """หยุดรอบนี้ / ถอนตัว — ต้องยืนยัน · หลังจากนี้บันทึกเพิ่มไม่ได้"""
        d = await read_json(request)
        _need(sid, active=True)
        if not d.get("confirm"):
            raise ApiError("ยืนยันก่อน — หยุด/ถอนตัวแล้วบันทึกเพิ่มไม่ได้")
        svc.set_status(sid, str(d.get("status", "")), str(d.get("reason", "")), bool(d.get("no_data_use")))
        return _session(_need(sid))

    @app.post("/api/trial/s/{sid}/survey")
    @api
    async def api_survey(request: Request, sid: str):
        d = await read_json(request)
        _need(sid, active=True)
        svc.save_answers(sid, {k: ("1" if v is True else "" if v is False else v) for k, v in d.items()
                               if isinstance(v, (str, bool))})
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
