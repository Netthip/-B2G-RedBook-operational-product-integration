# -*- coding: utf-8 -*-
"""เส้นทางเว็บของ "ทดลองตรวจเล่ม" (#43) — เรียกชั้นบริการ :mod:`redbook.services.trial` เท่านั้น"""
from __future__ import annotations

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ..services import pdfpair, pdfshelf, trial as svc
from ..storage import trial_repo
from .security import verify_csrf


def register(app, page, fail) -> None:
    trial_repo.init_schema()

    def _ctx(**extra) -> dict:
        return {"tsvc": svc, "pens": svc.PENS, "topics": svc.TOPIC_CODES, **extra}

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
                          again: str = Form(""), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            sid = svc.start(book_id, reviewer, again=again == "1")
        except (svc.TrialError, pdfshelf.ShelfError) as e:
            return _home(request, 400, error=str(e))
        s = svc.session(sid)
        return RedirectResponse(f"/trial/s/{sid}" + ("/result" if s and s.locked else ""), status_code=303)

    def _review(request, sid, pg=0, prev=False, ppg=0, status=200, **extra):
        s = svc.session(sid)
        if s is None:
            return fail(request, "ไม่พบรอบตรวจ", 404)
        pages = s.pages("cur")
        pg = pg if pg in pages else next((p for p in pages if ("cur", p) not in s.done), pages[0])
        ppages = s.pages("prev")
        i = pages.index(pg)
        ppg = ppg if ppg in ppages else ppages[min(i, len(ppages) - 1)]
        if not s.locked:
            svc.log_view(sid, pg, ppg if prev else 0)
        data = {"sid": sid, "locked": s.locked, "marks": s.marks, "two": prev,
                "pages": {"cur": pages, "prev": ppages}, "done": sorted(p for side, p in s.done if side == "cur"),
                "topics": dict(svc.TOPIC_CODES), "pens": svc.PENS,
                # ภาพหน้าถัดไปโหลดเตรียมไว้ — กด "ตรวจหน้านี้แล้ว" แล้วไม่ต้องรอวาดภาพ
                "preload": [f"/trial/s/{sid}/page/cur/{p}.png" for p in pages[i + 1:i + 2]]
                           + ([f"/trial/s/{sid}/page/prev/{p}.png" for p in ppages[ppages.index(ppg) + 1:ppages.index(ppg) + 2]]
                              if prev else [])}
        return page(request, "trial_review.html", _ctx(
            s=s, pg=pg, pages=pages, ppg=ppg, ppages=ppages, prev=prev, data=data, i=i,
            next_pg=pages[i + 1] if i + 1 < len(pages) else 0, prev_pg=pages[i - 1] if i else 0,
            done=s.done, **extra), status)

    @app.get("/trial/s/{sid}", response_class=HTMLResponse)
    async def trial_review(request: Request, sid: str, page_no: int = 0, prev: int = 1, pp: int = 0):
        # ค่าเริ่มต้น = สองฉบับวางข้างกัน (การตรวจคือการเทียบ) · ``prev=0`` = ดูฉบับเดียว
        return _review(request, sid, page_no, bool(prev), pp)

    @app.get("/trial/s/{sid}/page/{side}/{n}.png")
    async def trial_png(request: Request, sid: str, side: str, n: int):
        try:
            png = svc.page_png(sid, side, n)
        except (svc.TrialError, pdfshelf.ShelfError) as e:
            return fail(request, str(e), 409)
        if png is None:
            return fail(request, "เปิดได้เฉพาะหน้าของหน่วยงานในเล่มนี้", 404)
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})

    @app.post("/trial/s/{sid}/marks")
    async def trial_mark_add(request: Request, sid: str, side: str = Form(""), page_no: str = Form(""),
                             fx: str = Form(""), fy: str = Form(""), pen: str = Form(""),
                             csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            m = svc.add_mark(sid, side, page_no, fx, fy, pen)
        except svc.TrialError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return JSONResponse(m)

    @app.post("/trial/s/{sid}/marks/{mid}")
    async def trial_mark_edit(request: Request, sid: str, mid: str, topic: str = Form(None),
                              note: str = Form(None), pen: str = Form(None), delete: str = Form(""),
                              csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            svc.update_mark(sid, mid, topic=topic, note=note, pen=pen, delete=delete == "1")
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

    @app.post("/trial/s/{sid}/done")
    async def trial_page_done(request: Request, sid: str, side: str = Form("cur"), page_no: str = Form(""),
                              go: str = Form(""), prev: str = Form("1"), pp: str = Form(""),
                              csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            svc.page_done(sid, side, page_no)
        except (svc.TrialError, ValueError) as e:
            return _review(request, sid, int(page_no or 0), status=400, error=str(e))
        dest = f"/trial/s/{sid}?page_no={int(go)}" if go.isdigit() and int(go) else f"/trial/s/{sid}?page_no={page_no}"
        dest += "&prev=0" if prev == "0" else (f"&pp={int(pp)}" if pp.isdigit() else "")
        return RedirectResponse(dest, status_code=303)

    @app.post("/trial/s/{sid}/lock")
    async def trial_lock(request: Request, sid: str, confirm: str = Form(""), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        if confirm != "1":
            return _review(request, sid, status=400, error="ติ๊กยืนยันก่อนส่ง — ส่งแล้วแก้จุดที่วงไม่ได้")
        try:
            svc.lock(sid)
        except (svc.TrialError, pdfshelf.ShelfError, pdfpair.PairError) as e:
            return _review(request, sid, status=400, error=str(e))
        return RedirectResponse(f"/trial/s/{sid}/result", status_code=303)

    def _result(request, sid, status=200, **extra):
        try:
            r = svc.result(sid)
        except (svc.TrialError, pdfshelf.ShelfError, pdfpair.PairError) as e:
            return fail(request, str(e), 409)
        return page(request, "trial_result.html", _ctx(r=r, sid=sid, psvc=pdfpair,
                                                        candidates=svc.candidates, **extra), status)

    @app.get("/trial/s/{sid}/result", response_class=HTMLResponse)
    async def trial_result(request: Request, sid: str):
        return _result(request, sid)

    @app.post("/trial/s/{sid}/link/{mid}")
    async def trial_link(request: Request, sid: str, mid: str, verdict: str = Form(""),
                         finding_id: str = Form(""), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            svc.decide_link(sid, mid, verdict, finding_id)
        except svc.TrialError as e:
            return _result(request, sid, 400, error=str(e), error_at=f"m-{mid}")
        return RedirectResponse(f"/trial/s/{sid}/result#m-{mid}", status_code=303)

    @app.post("/trial/s/{sid}/extra/{fid}")
    async def trial_extra(request: Request, sid: str, fid: str, verdict: str = Form(""),
                          csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            svc.decide_extra(sid, fid, verdict)
        except svc.TrialError as e:
            return _result(request, sid, 400, error=str(e), error_at=f"x-{fid}")
        return RedirectResponse(f"/trial/s/{sid}/result#x-{fid}", status_code=303)

    @app.get("/trial/s/{sid}/survey", response_class=HTMLResponse)
    async def trial_survey(request: Request, sid: str):
        s = svc.session(sid)
        if s is None:
            return fail(request, "ไม่พบรอบตรวจ", 404)
        return page(request, "trial_survey.html", _ctx(s=s, sid=sid, answers=trial_repo.answers(sid)))

    @app.post("/trial/s/{sid}/survey")
    async def trial_survey_save(request: Request, sid: str):
        form = await request.form()
        verify_csrf(request, form.get("csrf_token", ""))
        try:
            svc.save_answers(sid, dict(form))
        except svc.TrialError as e:
            s = svc.session(sid)
            return page(request, "trial_survey.html", _ctx(s=s, sid=sid, answers=dict(form), error=str(e)), 400)
        return RedirectResponse(f"/trial/s/{sid}/dashboard", status_code=303)

    @app.get("/trial/s/{sid}/dashboard", response_class=HTMLResponse)
    async def trial_dashboard(request: Request, sid: str):
        try:
            r = svc.result(sid)
        except (svc.TrialError, pdfshelf.ShelfError, pdfpair.PairError) as e:
            return fail(request, str(e), 409)
        return page(request, "trial_dashboard.html", _ctx(r=r, sid=sid, m=r.metrics))

    @app.get("/trial/s/{sid}/summary.json")
    async def trial_summary(request: Request, sid: str):
        try:
            data = svc.summary_bytes(sid)
        except (svc.TrialError, pdfshelf.ShelfError, pdfpair.PairError) as e:
            return fail(request, str(e), 409)
        return Response(content=data, media_type="application/json; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="trial_summary_{sid}.json"'})
