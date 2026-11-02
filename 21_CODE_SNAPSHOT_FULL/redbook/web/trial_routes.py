# -*- coding: utf-8 -*-
"""เส้นทางเว็บของ "ทดลองตรวจเล่ม" (#43 · วิธีวัดผลฉบับ 0.2) — เรียกชั้นบริการ :mod:`redbook.services.trial` เท่านั้น"""
from __future__ import annotations

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ..services import pdfpair, pdfshelf, trial as svc
from ..storage import trial_repo
from .security import verify_csrf

ERRORS = (svc.TrialError, pdfshelf.ShelfError, pdfpair.PairError)


def register(app, page, fail) -> None:
    trial_repo.init_schema()

    def _ctx(**extra) -> dict:
        return {"tsvc": svc, "pens": svc.PENS, "topics": svc.TOPIC_CODES, "parts": svc.PARTS, **extra}

    def _home(request, status=200, **extra):
        books = svc.books()
        # เตรียมสารบัญของทุกเล่มทดสอบไว้ระหว่างที่ผู้ตรวจอ่านขั้นตอน — กด "เริ่มตรวจ" แล้วไม่ต้องรอ
        import threading
        threading.Thread(target=pdfshelf.prewarm, args=([k for b in books for k in (b.current, b.previous)],),
                         daemon=True).start()
        return page(request, "trial_home.html", _ctx(
            books=books, status=svc.book_status(), books_file=pdfshelf.shelf_label(), **extra), status)

    @app.get("/trial", response_class=HTMLResponse)
    async def trial_home(request: Request):
        return _home(request)

    @app.post("/trial/start")
    async def trial_start(request: Request, book_id: str = Form(""), reviewer: str = Form(""),
                          again: str = Form(""), path: str = Form("r1"), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            sid = svc.start(book_id, reviewer, again=again == "1", path=path or "r1")
        except ERRORS as e:
            return _home(request, 400, error=str(e))
        s = svc.session(sid)
        return RedirectResponse(f"/trial/s/{sid}" + ("/result" if s and s.locked and s.rec["run_id"] else ""),
                                status_code=303)

    def _review(request, sid, pg=0, prev=True, ppg=0, status=200, form=None, **extra):
        s = svc.session(sid)
        if s is None:
            return fail(request, "ไม่พบรอบตรวจ", 404)
        pages, ppages = s.pages("cur"), s.pages("prev")
        pg = pg if pg in pages else next((p for p in pages if ("cur", p) not in s.done), pages[0])
        i = pages.index(pg)
        ppg = ppg if ppg in ppages else ppages[min(i, len(ppages) - 1)]
        if not s.locked and s.active and not s.legacy:
            svc.log_view(sid, pg, ppg if prev else 0)
        lab = s.labels
        data = {"sid": sid, "locked": s.locked or not s.active or s.legacy or not s.consented, "path": s.path,
                "two": prev,
                "marks": [{k: m.get(k, "") for k in ("id", "side", "page", "fx", "fy", "pen", "topic", "note", "level",
                                                      "cause", "part", "searched", "xtype")} for m in s.circles],
                "xkind": s.xkind, "xtypes": svc.XTYPES, "xtype_by_topic": svc.XTYPE_BY_TOPIC,
                "pages": {"cur": pages, "prev": ppages},
                "done": {"cur": s.done_pages("cur"), "prev": s.done_pages("prev")},
                "topics": dict(svc.topic_codes(s.xkind)), "parts": dict(svc.PARTS), "pens": svc.PENS, "levels": svc.LEVELS,
                "causes": svc.CAUSES, "labels": lab,
                # ภาพหน้าถัดไปของเอกสารโหลดเตรียมไว้ (ภาพหน้าเอกสารเท่านั้น — ก่อนล็อกไม่มีผลระบบให้โหลด)
                "preload": [f"/trial/s/{sid}/page/cur/{p}.png" for p in pages[i + 1:i + 2]]
                           + ([f"/trial/s/{sid}/page/prev/{p}.png" for p in ppages[ppages.index(ppg) + 1:ppages.index(ppg) + 2]]
                              if prev else [])}
        gaps = [(m, svc.mark_gaps(m, s.xkind)) for m in s.circles]
        return page(request, "trial_review.html", _ctx(
            topics=svc.topic_codes(s.xkind), s=s, pg=pg, pages=pages, ppg=ppg, ppages=ppages, prev=prev, data=data, i=i, lab=lab,
            open_=s.active and not s.locked and not s.legacy,
            next_pg=pages[i + 1] if i + 1 < len(pages) else 0, prev_pg=pages[i - 1] if i else 0,
            done=s.done, gaps=[(m, x) for m, x in gaps if x], defaults=svc.declaration_defaults(s),
            form=form or {}, **extra), status)

    @app.get("/trial/s/{sid}", response_class=HTMLResponse)
    async def trial_review(request: Request, sid: str, page_no: int = 0, prev: int = 1, pp: int = 0):
        # ค่าเริ่มต้น = สองฉบับวางข้างกันเท่ากัน · ``prev=0`` = ดูฉบับ B/ปีนี้อย่างเดียว
        return _review(request, sid, page_no, bool(prev), pp)

    @app.get("/trial/s/{sid}/page/{side}/{n}.png")
    async def trial_png(request: Request, sid: str, side: str, n: int):
        try:
            png = svc.page_png(sid, side, n)
        except ERRORS as e:
            return fail(request, str(e), 409)
        if png is None:
            return fail(request, "เปิดได้เฉพาะหน้าของหน่วยงานในเล่มนี้", 404)
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})

    @app.post("/trial/s/{sid}/path")
    async def trial_path(request: Request, sid: str, path: str = Form(""), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            svc.set_path(sid, path)
        except ERRORS as e:
            return _review(request, sid, status=400, error=str(e), error_at="path")
        return RedirectResponse(f"/trial/s/{sid}", status_code=303)

    @app.post("/trial/s/{sid}/consent")
    async def trial_consent(request: Request, sid: str):
        """ความยินยอมก่อนเริ่มทำรายการ (ติ๊ก ไม่ลงชื่อ)"""
        form = await request.form()
        verify_csrf(request, form.get("csrf_token", ""))
        try:
            svc.give_consent(sid, {k: v for k, v in form.items() if isinstance(v, str)})
        except ERRORS as e:
            return _review(request, sid, status=400, error=str(e), error_at="consent")
        return RedirectResponse(f"/trial/s/{sid}", status_code=303)

    @app.post("/trial/s/{sid}/marks")
    async def trial_mark_add(request: Request, sid: str, side: str = Form(""), page_no: str = Form(""),
                             fx: str = Form(""), fy: str = Form(""), pen: str = Form(""),
                             csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            m = svc.add_mark(sid, side, page_no, fx, fy, pen)
        except svc.TrialError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return JSONResponse({k: m.get(k, "") for k in ("id", "side", "page", "fx", "fy", "pen", "topic", "note",
                                                       "level", "cause", "part", "searched")})

    @app.post("/trial/s/{sid}/marks/{mid}")
    async def trial_mark_edit(request: Request, sid: str, mid: str, topic: str = Form(None), note: str = Form(None),
                              pen: str = Form(None), level: str = Form(None), cause: str = Form(None),
                              part: str = Form(None), searched: str = Form(None), delete: str = Form(""),
                              xtype: str = Form(None), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            svc.update_mark(sid, mid, topic=topic, note=note, pen=pen, level=level, cause=cause, part=part,
                            searched=searched, delete=delete == "1", xtype=xtype)
        except (svc.TrialError, ValueError) as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return JSONResponse({"ok": True})

    @app.post("/trial/s/{sid}/view")
    async def trial_view(request: Request, sid: str, cur: str = Form(""), prev_page: str = Form("0"),
                         csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            svc.log_view(sid, cur, prev_page)
        except svc.TrialError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return JSONResponse({"ok": True})

    def _back(sid, side, page_no, go, prev, pp, cur):
        """กลับหน้าตรวจ — ฝั่งที่กดไปหน้าถัดไป (``go``) อีกฝั่งอยู่หน้าเดิม"""
        nxt = int(go) if go.isdigit() and int(go) else (int(page_no) if page_no.isdigit() else 0)
        if side == "prev":
            return f"/trial/s/{sid}?pp={nxt}" + (f"&page_no={int(cur)}" if cur.isdigit() else "")
        return f"/trial/s/{sid}?page_no={nxt}" + ("&prev=0" if prev == "0" else (f"&pp={int(pp)}" if pp.isdigit() else ""))

    @app.post("/trial/s/{sid}/done")
    async def trial_page_done(request: Request, sid: str, side: str = Form("cur"), page_no: str = Form(""),
                              go: str = Form(""), prev: str = Form("1"), pp: str = Form(""), cur: str = Form(""),
                              csrf_token: str = Form("")):
        """"ตรวจหน้านี้แล้ว" = ดูหน้านี้ครบ (ไม่ใช่ "ถูกต้อง") — ตัวช่วยของผู้ตรวจ ไม่ใช่เงื่อนไขการส่ง"""
        verify_csrf(request, csrf_token)
        try:
            svc.page_done(sid, side, page_no)
        except (svc.TrialError, ValueError) as e:
            return _review(request, sid, status=400, error=str(e))
        return RedirectResponse(_back(sid, side, page_no, go, prev, pp, cur), status_code=303)

    @app.post("/trial/s/{sid}/undone")
    async def trial_page_undone(request: Request, sid: str, side: str = Form("cur"), page_no: str = Form(""),
                                prev: str = Form("1"), pp: str = Form(""), cur: str = Form(""),
                                csrf_token: str = Form("")):
        """ยกเลิก "ตรวจหน้านี้แล้ว" (กดพลาด) — ก่อนส่งใบประกาศเท่านั้น"""
        verify_csrf(request, csrf_token)
        try:
            svc.page_undone(sid, side, page_no)
        except (svc.TrialError, ValueError) as e:
            return _review(request, sid, status=400, error=str(e))
        return RedirectResponse(_back(sid, side, page_no, "", prev, pp, cur), status_code=303)

    @app.post("/trial/s/{sid}/lock")
    async def trial_lock(request: Request, sid: str):
        form = await request.form()
        verify_csrf(request, form.get("csrf_token", ""))
        fd = {k: v for k, v in form.items() if isinstance(v, str)}
        try:
            svc.lock(sid, fd)
        except ERRORS as e:
            return _review(request, sid, status=400, error=str(e), form=fd, error_at="lock")
        return RedirectResponse(f"/trial/s/{sid}/result", status_code=303)

    @app.post("/trial/s/{sid}/run")
    async def trial_run(request: Request, sid: str, csrf_token: str = Form("")):
        """ลองเทียบอีกครั้ง — เมื่อรอบเทียบล้มเหลวหลังส่งใบประกาศ (ใบประกาศเดิมยังอยู่)"""
        verify_csrf(request, csrf_token)
        try:
            svc.retry_run(sid)
        except ERRORS as e:
            return _run_failed(request, sid, str(e), 409)
        return RedirectResponse(f"/trial/s/{sid}/result", status_code=303)

    def _run_failed(request, sid, message, status):
        s = svc.session(sid)
        if s is None:
            return fail(request, "ไม่พบรอบตรวจ", 404)
        return page(request, "trial_run_failed.html", _ctx(s=s, sid=sid, error=message), status)

    def _result(request, sid, status=200, **extra):
        s = svc.session(sid)
        if s is None:
            return fail(request, "ไม่พบรอบตรวจ", 404)
        if s.locked and not s.rec["run_id"]:
            return _run_failed(request, sid, s.rec.get("run_error") or "ระบบยังเทียบไม่สำเร็จ", 409)
        try:
            r = svc.result(sid)
            if r.legacy:
                return page(request, "trial_result_v01.html", _ctx(r=r, sid=sid, psvc=pdfpair, lab=s.labels, **extra),
                            status)
            m = r.metrics
        except ERRORS as e:
            return fail(request, str(e), 409)
        return page(request, "trial_result.html", _ctx(r=r, sid=sid, m=m, psvc=pdfpair, lab=r.s.labels,
                                                        topics=svc.topic_codes(r.s.xkind),
                                                        st=svc.status_of(r.s, r), **extra), status)

    @app.get("/trial/s/{sid}/result", response_class=HTMLResponse)
    async def trial_result(request: Request, sid: str):
        return _result(request, sid)

    @app.post("/trial/s/{sid}/row/{mid}")
    async def trial_row(request: Request, sid: str, mid: str, part: str = Form(None), cause: str = Form(None),
                        level: str = Form(None), found_in: str = Form(None), searched: str = Form(None),
                        side: str = Form(None), page_no: str = Form(None), ref: str = Form(None),
                        row_source: str = Form(None), xtype: str = Form(None), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        if row_source == "post_result":            # มิติที่จัดใหม่หลังเห็นผล → post:part,level
            dims = [d for d in (await request.form()).getlist("post_dim") if d in svc.POST_DIMS]
            row_source = "post:" + ",".join(dims) if dims else "post:"
        try:
            svc.update_row(sid, mid, part=part, cause=cause, level=level, found_in=found_in, searched=searched,
                           side=side, page=page_no, ref=ref, row_source=row_source, xtype=xtype)
        except ERRORS as e:
            return _result(request, sid, 400, error=str(e), error_at=f"i-{mid}")
        return RedirectResponse(f"/trial/s/{sid}/result#i-{mid}", status_code=303)

    @app.post("/trial/s/{sid}/issue/{mid}")
    async def trial_issue(request: Request, sid: str, mid: str):
        form = await request.form()
        verify_csrf(request, form.get("csrf_token", ""))
        verdict = str(form.get("verdict", ""))
        reason = str(form.get("reason_b" if verdict == "partial" else "reason_p", "")) \
            if verdict in ("partial", "missed") else ""
        try:
            svc.decide_issue(sid, mid, verdict, [str(x) for x in form.getlist("finding_ids") if str(x)],
                             reason=reason, evidence=str(form.get("evidence", "")), basis=str(form.get("basis", "")),
                             change_reason=str(form.get("change_reason", "")), location=str(form.get("location", "")),
                             relevant_sides=[str(x) for x in form.getlist("relevant_side") if str(x)],
                             search_scope=str(form.get("search_scope", "")))
        except ERRORS as e:
            return _result(request, sid, 400, error=str(e), error_at=f"i-{mid}")
        return RedirectResponse(f"/trial/s/{sid}/result#i-{mid}", status_code=303)

    @app.post("/trial/s/{sid}/finding/{fid}")
    async def trial_finding(request: Request, sid: str, fid: str, group: str = Form(""), s3_reason: str = Form(""),
                            basis: str = Form(""), issue_ref: str = Form(""), change_reason: str = Form(""),
                            part: str = Form(""), note: str = Form(""), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            svc.decide_finding(sid, fid, group, s3_reason=s3_reason, basis=basis, issue_ref=issue_ref,
                               change_reason=change_reason, part=part, note=note)
        except ERRORS as e:
            return _result(request, sid, 400, error=str(e), error_at=f"f-{fid}")
        return RedirectResponse(f"/trial/s/{sid}/result#f-{fid}", status_code=303)

    @app.post("/trial/s/{sid}/obs/{fid}")
    async def trial_obs(request: Request, sid: str, fid: str):
        form = await request.form()
        verify_csrf(request, form.get("csrf_token", ""))
        dims = {k[4:]: str(v) for k, v in form.items() if k.startswith("dim_")}
        try:
            svc.decide_obs(sid, fid, str(form.get("fidelity", "")), fidelity_reason=str(form.get("fidelity_reason", "")),
                           dims=dims, assertion_undecidable=form.get("assertion_undecidable") == "1",
                           basis=str(form.get("basis", "")), change_reason=str(form.get("change_reason", "")))
        except ERRORS as e:
            return _result(request, sid, 400, error=str(e), error_at=f"o-{fid}")
        return RedirectResponse(f"/trial/s/{sid}/result#o-{fid}", status_code=303)

    @app.post("/trial/s/{sid}/note")
    async def trial_note(request: Request, sid: str, part: str = Form(""), topic: str = Form(""),
                         note: str = Form(""), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            svc.add_post_note(sid, part, topic, note)
        except ERRORS as e:
            return _result(request, sid, 400, error=str(e), error_at="notes")
        return RedirectResponse(f"/trial/s/{sid}/result#notes", status_code=303)

    @app.post("/trial/s/{sid}/finish")
    async def trial_finish(request: Request, sid: str, reason: str = Form(""), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            svc.finish_use(sid, reason)
        except ERRORS as e:
            return _result(request, sid, 400, error=str(e), error_at="finish")
        return RedirectResponse(f"/trial/s/{sid}/survey", status_code=303)

    @app.post("/trial/s/{sid}/status")
    async def trial_status(request: Request, sid: str, status: str = Form(""), reason: str = Form(""),
                           no_data_use: str = Form(""), confirm: str = Form(""), csrf_token: str = Form("")):
        """หยุดรอบนี้ / ถอนตัว — ต้องติ๊กยืนยัน · หลังจากนี้บันทึกเพิ่มไม่ได้"""
        verify_csrf(request, csrf_token)
        s = svc.session(sid)
        if s is None:
            return fail(request, "ไม่พบรอบตรวจ", 404)
        try:
            if confirm != "1":
                raise svc.TrialError("ติ๊กยืนยันก่อน — หยุด/ถอนตัวแล้วบันทึกเพิ่มไม่ได้")
            svc.set_status(sid, status, reason, no_data_use == "1")
        except ERRORS as e:
            if s.locked and s.rec["run_id"]:
                return _result(request, sid, 400, error=str(e), error_at="status")
            return _review(request, sid, status=400, error=str(e), error_at="status")
        return RedirectResponse(f"/trial/s/{sid}" + ("/result" if s.locked and s.rec["run_id"] else ""),
                                status_code=303)

    def _survey(request, sid, status=200, answers=None, **extra):
        s = svc.session(sid)
        if s is None:
            return fail(request, "ไม่พบรอบตรวจ", 404)
        state = svc.survey_state(s)
        return page(request, "trial_survey.html", _ctx(s=s, sid=sid, state=state,
                                                        answers=trial_repo.answers(sid) if answers is None else answers,
                                                        **extra), status)

    @app.get("/trial/s/{sid}/survey", response_class=HTMLResponse)
    async def trial_survey(request: Request, sid: str):
        return _survey(request, sid)

    @app.post("/trial/s/{sid}/survey")
    async def trial_survey_save(request: Request, sid: str):
        form = await request.form()
        verify_csrf(request, form.get("csrf_token", ""))
        try:
            svc.save_answers(sid, {k: v for k, v in form.items() if isinstance(v, str)})
        except svc.TrialError as e:
            return _survey(request, sid, 400, answers=dict(form), error=str(e))
        return RedirectResponse(f"/trial/s/{sid}/dashboard", status_code=303)

    @app.get("/trial/s/{sid}/dashboard", response_class=HTMLResponse)
    async def trial_dashboard(request: Request, sid: str):
        try:
            r = svc.result(sid)
            m = r.metrics
        except ERRORS as e:
            return fail(request, str(e), 409)
        tpl = "trial_result_v01.html" if r.legacy else "trial_dashboard.html"
        return page(request, tpl, _ctx(r=r, sid=sid, m=m, psvc=pdfpair, lab=r.s.labels,
                                       st=svc.status_of(r.s, r)))

    @app.get("/trial/s/{sid}/summary.json")
    async def trial_summary(request: Request, sid: str):
        try:
            data = svc.summary_bytes(sid)
        except ERRORS as e:
            return fail(request, str(e), 409)
        return Response(content=data, media_type="application/json; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="trial_summary_{sid}.json"'})
