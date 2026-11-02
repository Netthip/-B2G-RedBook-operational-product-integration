# -*- coding: utf-8 -*-
"""เส้นทางเว็บของสายเทียบเล่ม PDF ↔ PDF — เรียกชั้นบริการ :mod:`redbook.services.pdfpair` เท่านั้น

ทุกเส้นทางเป็น ``def`` ธรรมดา — FastAPI อ่านฟอร์ม (รวมโทเคน CSRF) บน event loop แล้วรัน handler ใน threadpool
งาน SQLite · แยก JSON ของรอบ · วาดภาพ PDF จึงไม่บล็อกคำขออื่น (ภาพ/ไฟล์ static/API ไม่ต้องต่อคิว)"""
from __future__ import annotations

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ..services import pdfpair as svc, pdfshelf
from ..storage import pdfpair_repo, repository as repo, source_pdfs
from .security import verify_csrf


def _nav(v, pf=None) -> dict:
    """เมนูซ้ายของสายเทียบเล่ม — ชี้ไปของรอบนี้ + ตัวเลขข้อค้าง/สถานะด่าน"""
    counts = {"queue": (v.pending, v.pending > 0)}
    if pf is not None:
        counts["preflight"] = (len(pf.failing), not pf.ok)
    return {"nav_pdfpair": {"rid": v.rid, "pid": v.run["project_id"]}, "nav_counts": counts}


def register(app, page, fail) -> None:
    pdfpair_repo.init_schema()

    def _start_ctx(pid: str, project: dict, **extra) -> dict:
        return {"project": project, "pid": pid, "srcs": source_pdfs.for_project(pid),
                "runs": pdfpair_repo.list_runs(pid), "mode_labels": svc.MODE_LABELS,
                "profile_status": svc.PROFILE_STATUS_LABEL, "topics": svc.TOPICS,
                "form": {}, **extra}

    # ── ชั้นเล่มในเครื่อง: เลือกเล่ม A/B + หน่วยงาน แล้วเทียบทันที ────────────────────────
    def _shelf_ctx(a_key: str = "", agency: str = "", **extra) -> dict:
        shelf = pdfshelf.volumes()
        a = next((v for v in shelf if v.key == a_key), None) if a_key else None
        ctx = {"shelf": shelf, "shelf_dir": pdfshelf.shelf_label(), "a": a, "agency": agency,
               "agencies": [], "suggest": [], "others": [], **extra}
        if a is not None:
            try:
                ctx["agencies"] = pdfshelf.agencies(a)
            except pdfshelf.ShelfError as e:
                ctx["agency_error"] = str(e)
            ctx["suggest"] = pdfshelf.suggest_b(a, shelf)
            picked = {v.key for v, _w in ctx["suggest"]} | {a.key}
            ctx["others"] = [v for v in shelf if v.key not in picked]
        return ctx

    @app.get("/pdfpair/shelf", response_class=HTMLResponse)
    def pdfpair_shelf(request: Request, a: str = "", agency: str = ""):
        return page(request, "pdfpair_shelf.html", _shelf_ctx(a, agency))

    @app.post("/pdfpair/shelf")
    def pdfpair_shelf_start(request: Request, a: str = Form(""), b: str = Form(""),
                                  agency: str = Form(""), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            _pid, rid = pdfshelf.start(a, b, agency)
        except (pdfshelf.ShelfError, svc.PairError) as e:
            return page(request, "pdfpair_shelf.html", _shelf_ctx(a, agency, error=str(e)), 400)
        return RedirectResponse(f"/pdfpair/runs/{rid}", status_code=303)

    @app.get("/projects/{pid}/pdfpair", response_class=HTMLResponse)
    def pdfpair_start(request: Request, pid: str):
        project = repo.get_project(pid)
        if not project:
            return fail(request, "ไม่พบงานตรวจที่ระบุ", 404)
        return page(request, "pdfpair_start.html", _start_ctx(pid, project))

    @app.post("/projects/{pid}/pdfpair")
    def pdfpair_run(request: Request, pid: str, agency: str = Form(""), mode: str = Form(""),
                          a_first: str = Form(""), a_last: str = Form(""),
                          b_first: str = Form(""), b_last: str = Form(""),
                          csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        project = repo.get_project(pid)
        if not project:
            return fail(request, "ไม่พบงานตรวจที่ระบุ", 404)
        try:
            rid = svc.run(pid, agency=agency, mode=mode, a_first=a_first, a_last=a_last,
                          b_first=b_first, b_last=b_last)
        except svc.PairError as e:
            return page(request, "pdfpair_start.html", _start_ctx(
                pid, project, error=str(e),
                form={"agency": agency, "mode": mode, "a_first": a_first, "a_last": a_last,
                      "b_first": b_first, "b_last": b_last}), 400)
        return RedirectResponse(f"/pdfpair/runs/{rid}", status_code=303)

    @app.get("/pdfpair/runs/{rid}", response_class=HTMLResponse)
    def pdfpair_overview(request: Request, rid: str):
        v = svc.view(rid)
        if v is None:
            return fail(request, "ไม่พบรอบเทียบเล่มที่ระบุ", 404)
        pf = svc.preflight(rid, v)
        return page(request, "pdfpair_run.html", {
            "v": v, "svc": svc, "project": repo.get_project(v.run["project_id"]), "pf": pf,
            "profile_status": svc.PROFILE_STATUS_LABEL, **_nav(v, pf)})

    @app.get("/pdfpair/runs/{rid}/f/{fid}", response_class=HTMLResponse)
    def pdfpair_finding(request: Request, rid: str, fid: str, error: str = ""):
        v = svc.view(rid)
        f = v.finding(fid) if v else None
        if f is None:
            return fail(request, "ไม่พบข้อสังเกตที่ระบุ", 404)
        ids = [x.id for x in v.result.findings]
        i = ids.index(fid)
        da, db = svc.text_diff(f.a.value, f.b.value) if f.topic == "text" and f.a.value and f.b.value \
            else ([], [])
        return page(request, "pdfpair_finding.html", {
            "v": v, "f": f, "svc": svc, "diff_a": da, "diff_b": db,
            "prev_id": ids[i - 1] if i > 0 else "", "next_id": ids[i + 1] if i + 1 < len(ids) else "",
            "decision": v.decisions.get(fid), "decision_error": error,
            "profile_status": svc.PROFILE_STATUS_LABEL, **_nav(v)})

    @app.get("/pdfpair/runs/{rid}/f/{fid}/{side}.png")
    def pdfpair_png(request: Request, rid: str, fid: str, side: str, full: str = ""):
        try:
            png = svc.evidence_png(rid, fid, side, full=full == "1")
        except svc.PairError as e:
            return fail(request, str(e), 409)
        if png is None:
            return fail(request, "ไม่มีภาพหลักฐานของฝั่งนี้", 404)
        return Response(content=png, media_type="image/png",
                        headers={"Cache-Control": "private, max-age=300"})

    @app.post("/pdfpair/runs/{rid}/f/{fid}/decide")
    def pdfpair_decide(request: Request, rid: str, fid: str, choice: str = Form(""),
                             note: str = Form(""), go_next: str = Form(""),
                             csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            svc.decide(rid, fid, choice, note)
        except svc.PairError as e:
            v = svc.view(rid)
            f = v.finding(fid) if v else None
            if f is None:
                return fail(request, str(e), 404)
            ids = [x.id for x in v.result.findings]
            i = ids.index(fid)
            return page(request, "pdfpair_finding.html", {
                "v": v, "f": f, "svc": svc, "diff_a": [], "diff_b": [],
                "prev_id": ids[i - 1] if i > 0 else "",
                "next_id": ids[i + 1] if i + 1 < len(ids) else "",
                "decision": v.decisions.get(fid), "decision_error": str(e),
                "profile_status": svc.PROFILE_STATUS_LABEL, **_nav(v)}, 400)
        dest = f"/pdfpair/runs/{rid}/f/{go_next}" if go_next and go_next.isalnum() \
            else f"/pdfpair/runs/{rid}#f-{fid}"
        return RedirectResponse(dest, status_code=303)

    def _pf_page(request, rid, name, status=200, **extra):
        v = svc.view(rid)
        if v is None:
            return fail(request, "ไม่พบรอบเทียบเล่มที่ระบุ", 404)
        pf = svc.preflight(rid, v)
        return page(request, name, {"v": v, "svc": svc, "pf": pf,
                                    "project": repo.get_project(v.run["project_id"]),
                                    "profile_status": svc.PROFILE_STATUS_LABEL, **_nav(v, pf), **extra},
                    status)

    @app.get("/pdfpair/runs/{rid}/preflight", response_class=HTMLResponse)
    def pdfpair_preflight(request: Request, rid: str):
        return _pf_page(request, rid, "pdfpair_preflight.html")

    @app.post("/pdfpair/runs/{rid}/year")
    def pdfpair_confirm_year(request: Request, rid: str, side: str = Form(""), year: str = Form(""),
                                   note: str = Form(""), seen: str = Form(""), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            svc.confirm_year(rid, side, year, note, seen == "1")
        except svc.PairError as e:
            return _pf_page(request, rid, "pdfpair_preflight.html", 400, year_error=str(e), year_side=side)
        return RedirectResponse(f"/pdfpair/runs/{rid}/preflight#years", status_code=303)

    @app.post("/pdfpair/runs/{rid}/rerun")
    def pdfpair_rerun(request: Request, rid: str, csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            new = svc.rerun(rid)
        except (svc.PairError, ValueError) as e:
            return _pf_page(request, rid, "pdfpair_preflight.html", 409, rerun_error=str(e))
        return RedirectResponse(f"/pdfpair/runs/{new}/preflight", status_code=303)

    @app.get("/pdfpair/runs/{rid}/page/{side}/{n}.png")
    def pdfpair_page_png(request: Request, rid: str, side: str, n: int):
        try:
            png = svc.page_png(rid, side, n)
        except svc.PairError as e:
            return fail(request, str(e), 409)
        if png is None:
            return fail(request, "เปิดได้เฉพาะหน้าที่รอบนี้อ่าน (หน้าต้นไฟล์และหน้าของหน่วยงาน)", 404)
        return Response(content=png, media_type="image/png",
                        headers={"Cache-Control": "private, max-age=300"})

    @app.get("/pdfpair/runs/{rid}/export", response_class=HTMLResponse)
    def pdfpair_export_page(request: Request, rid: str):
        return _pf_page(request, rid, "pdfpair_export.html")

    @app.get("/pdfpair/runs/{rid}/audit", response_class=HTMLResponse)
    def pdfpair_audit(request: Request, rid: str):
        from ..storage import audit
        return _pf_page(request, rid, "pdfpair_audit.html", entries=pdfpair_repo.audit_entries(rid),
                        chain=audit.verify_chain())

    @app.get("/pdfpair/runs/{rid}/export.csv")
    def pdfpair_export(request: Request, rid: str):
        try:
            data = svc.export_csv_checked(rid)
        except svc.PairError as e:
            return fail(request, str(e), 409)
        # ส่งไบต์ชุดเดียวกับที่แฮชลง Audit — ห้าม encode ซ้ำที่นี่
        return Response(content=data, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="pdfpair_{rid}.csv"'})

    # JSON API ของสายนี้ (หน้าบ้าน /r/) — ลงทะเบียนที่นี่ ไม่แตะ app.py (สัญญา docs/API_CONTRACT_R.md ข้อ 5)
    from . import api_pdfpair
    api_pdfpair.register(app)
