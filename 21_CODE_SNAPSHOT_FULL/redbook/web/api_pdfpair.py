# -*- coding: utf-8 -*-
"""JSON API ของสายเทียบเล่ม PDF ↔ PDF สำหรับหน้าบ้าน Svelte (``/r/``) — สัญญา ``docs/API_CONTRACT_R.md`` ข้อ 4

เรียกชั้นบริการ :mod:`redbook.services.pdfpair` / :mod:`redbook.services.pdfshelf` ตัวเดียวกับหน้าเว็บเดิม
(:mod:`.pdfpair_routes`) — กติกาเหมือนกันทุกข้อ:

* ทุก POST ผ่าน :func:`api_common.read_json` (CSRF แบบ double-submit + Origin) ก่อนแตะข้อมูล
* รอบที่ถูกแทน (superseded) อ่านได้อย่างเดียว — บันทึกผล/ยืนยันปี/คำนวณซ้ำ = 409 ``superseded``
* **ไม่มีทางส่งออกใน API** — ส่งออกใช้ ``GET /pdfpair/runs/{rid}/export.csv`` เดิม ซึ่งประเมินด่านก่อนส่งออกใหม่
  ฝั่งเซิร์ฟเวอร์ทุกครั้ง (``export_csv_checked``) · API ให้แค่สถานะด่านไว้แสดง
* ภาพหลักฐาน/ภาพหน้าใช้ URL เดิม (จำกัดหน้าที่รอบนั้นอ่านเหมือนเดิม)
* งานที่บล็อก (SQLite · แยก JSON ของรอบ · อ่าน PDF) รันใน threadpool — GET เป็น ``def`` ธรรมดา · POST อ่าน body
  บน event loop แล้วส่งงานต่อด้วย ``run_in_threadpool`` · ด่านที่ต้องตรวจซ้ำเมื่อคำขอพร้อมกันอยู่ในธุรกรรมเขียนของ
  ``pdfpair_repo`` (รอบถูกแทน · เปลี่ยนค่าเดิมต้องมีหมายเหตุ)
"""
from __future__ import annotations

import json

from fastapi import Request

from .. import config
from ..services import pdf_upload, pdfpair as svc, pdfshelf
from ..storage import files as filestore, pdfpair_repo, repository as repo, source_pdfs
from .api_common import MAX_BODY, ApiError, api, finding_json, read_json, run_in_threadpool
from .security import verify_csrf


def _view(rid: str):
    v = svc.view(rid)
    if v is None:
        raise ApiError("ไม่พบรอบเทียบเล่มที่ระบุ", 404, "not_found")
    return v


def _writable(v) -> None:
    """รอบที่ถูกแทน = อ่านได้อย่างเดียว (เหมือน ``svc._blocked`` ของหน้าเดิม แต่บอกรหัสให้หน้าบ้านพาไปรอบใหม่)"""
    if v.superseded_by:
        raise ApiError(f"รอบนี้ถูกแทนด้วยรอบ {v.superseded_by} ที่คำนวณด้วยปีงบที่ยืนยันแล้ว — ผลและคำตัดสินเดิม"
                       "เก็บไว้ดูย้อนหลังได้ แต่บันทึกเพิ่มไม่ได้", 409, "superseded")


def _f(v, f) -> dict:
    return finding_json(f, v.rid, v.decisions.get(f.id), v.use_of(f))


def _decisions() -> list:
    """ตัวเลือกคำตัดสิน + ผลต่อการใช้ผลของแต่ละตัวเลือก (``DECISION_USE``) — ให้เห็นก่อนกดว่าข้อจะปิด/ไม่นับ/ยังไม่ปิด"""
    out = []
    for k, label in svc.DECISIONS:
        use = svc.DECISION_USE.get(k, "open")
        out.append({"key": k, "label": label, "use": use, "use_label": svc.USE_LABELS[use],
                    "when": svc.DECISION_WHEN.get(k, ""), "after": svc.DECISION_AFTER.get(k, "")})
    return out


def _next_pending(v, after: str = "") -> str:
    ids = [f.id for f in v.result.findings]
    start = ids.index(after) + 1 if after in ids else 0
    for f in v.result.findings[start:] + v.result.findings[:start]:
        if not f.info and f.id not in v.decisions and f.id != after:
            return f.id
    return ""


def _action(c, v) -> dict | None:
    """ปุ่มของข้อที่ยังไม่ผ่าน → รหัสให้หน้าบ้านพาไปหน้าของตัวเอง (``href`` = หน้าเดิม ใช้เป็นทางสำรอง)"""
    if not c.action_href:
        return None
    a = {"label": c.action_label, "href": c.action_href}
    if c.action_post:
        return {**a, "code": "rerun"}
    if c.key == "superseded" or (v.superseded_by and f"/pdfpair/runs/{v.superseded_by}" in c.action_href):
        return {**a, "code": "open_run", "run_id": v.superseded_by}
    if "/f/" in c.action_href:
        return {**a, "code": "open_finding", "finding_id": c.action_href.rsplit("/f/", 1)[1]}
    if c.action_href.endswith("#years"):
        return {**a, "code": "confirm_year"}
    return {**a, "code": "reattach"}


def _preflight(v, full: bool = True) -> dict:
    pf = svc.preflight(v.rid, v)
    out = {"ok": pf.ok, "use_status": pf.use_status, "use_status_label": svc.USE_STATUS_LABELS[pf.use_status],
           "use_status_scope": svc.USE_STATUS_SCOPE, "use_reasons": list(pf.use_reasons),
           "use_counts": dict(pf.use_counts), "actionable": pf.actionable, "use_breakdown": pf.use_breakdown,
           "failing": [c.key for c in pf.failing],
           "failing_checks": [{"key": c.key, "label": c.label} for c in pf.failing],
           "export_url": f"/pdfpair/runs/{v.rid}/export.csv"}
    if not full:
        return out
    years = {}
    for s, bf in (("A", v.facts_a), ("B", v.facts_b)):
        sc = v.run["scope"][s]
        conf = v.year_confirms.get(s)
        front = list(range(1, min(svc.META_FRONT_PAGES, sc.get("pages_in_file") or svc.META_FRONT_PAGES) + 1))
        years[s] = {"used": v.used_year(s), "known": v.year_of(s), "detected": bf.fiscal_year,
                    "status": bf.year_status, "status_label": svc.year_status_label(bf.year_status),
                    "status_state": svc.year_status_state(bf.year_status), "confirmable": v.year_confirmable(s),
                    "origin": bf.year_origin, "origin_label": svc.YEAR_ORIGIN_LABELS.get(bf.year_origin, ""),
                    "candidates": list(bf.year_candidates),
                    "evidence": [{**e, "kind_label": svc.YEAR_EVIDENCE_KINDS.get(e.get("kind"), e.get("kind", ""))}
                                 for e in bf.year_evidence],
                    "confirmed": ({"year": conf["year"], "note": conf["note"], "confirmed_at": conf["confirmed_at"]}
                                  if conf else None),
                    "pages_allowed": sorted(set(front) | set(range(int(sc["first"]), int(sc["last"]) + 1))),
                    "page_png": f"/pdfpair/runs/{v.rid}/page/{s}/{{n}}.png"}
    return {**out, "checks": [{"key": c.key, "label": c.label, "ok": c.ok, "detail": c.detail,
                               "action": None if c.ok else _action(c, v)} for c in pf.checks],
            "years": years, "needs_rerun": v.needs_rerun, "mode_for_years": v.mode_for_years,
            "stage_warnings": [{"side": s, "text": t} for s, t in v.stage_warnings]}


def _run(v) -> dict:
    sides = {}
    for s, bf in (("A", v.facts_a), ("B", v.facts_b)):
        sc = v.run["scope"][s]
        sides[s] = {"label": v.side_label(s), "file": v.run[f"{s.lower()}_name"],
                    "sha256": v.run[f"{s.lower()}_sha256"], "fiscal_year": bf.fiscal_year,
                    "year_status": bf.year_status, "year_status_label": svc.year_status_label(bf.year_status),
                    "year_origin_label": svc.YEAR_ORIGIN_LABELS.get(bf.year_origin, ""),
                    "stage": bf.stage, "stage_status": bf.stage_status, "stage_origin": bf.stage_origin,
                    "first": sc["first"], "last": sc["last"], "pages_in_file": sc.get("pages_in_file"),
                    "method_label": sc.get("method_label", ""),
                    "printed_offset": sc.get("printed_offset"),
                    "coverage": {"sections_found": len(bf.coverage.sections_found),
                                 "repaired_words": bf.coverage.repaired_words,
                                 "pages_no_text": list(bf.coverage.pages_no_text)}}
    return {"id": v.rid, "created_at": v.run["created_at"], "mode": v.result.mode,
            "mode_label": svc.MODE_LABELS.get(v.result.mode, v.result.mode), "agency": v.run["agency"],
            "versions": v.run["versions"], "profile_status_label": svc.PROFILE_STATUS_LABEL,
            "superseded_by": v.superseded_by, "supersedes": v.supersedes, "sides": sides}


# ── งานของ POST (รันใน threadpool หลังอ่าน body + ผ่าน CSRF แล้ว) ──────────────────────────────────────
def _decide(rid: str, fid: str, d: dict) -> dict:
    v = _view(rid)
    if v.finding(fid) is None:
        raise ApiError("ไม่พบข้อสังเกตที่ระบุ", 404, "not_found")
    _writable(v)
    try:
        svc.decide(rid, fid, str(d.get("choice", "")), str(d.get("note", "")))
    except svc.RunSuperseded as e:          # ถูกแทนระหว่างคำขอนี้ (คำนวณซ้ำพร้อมกัน) — จับได้ในธุรกรรมเขียน
        raise ApiError(str(e), 409, "superseded")
    v = _view(rid)
    return {"finding": _f(v, v.finding(fid)), "next_pending_id": _next_pending(v, fid),
            "preflight": _preflight(v, full=False)}


def _year(rid: str, d: dict) -> dict:
    _writable(_view(rid))
    try:
        svc.confirm_year(rid, str(d.get("side", "")), str(d.get("year", "")), str(d.get("note", "")),
                         d.get("seen") in (True, 1, "1"))
    except svc.RunSuperseded as e:
        raise ApiError(str(e), 409, "superseded")
    return _preflight(_view(rid))


def _upload(side: str, pid: str, source_url: str, stream, filename: str) -> dict:
    """แนบ PDF ที่ผู้ใช้เลือกจากเครื่องเป็นฉบับ ``side`` ของงานตรวจ (สร้างงานตรวจใหม่ถ้าไม่ระบุ) — ด่านของ #23 ใน
    :mod:`services.pdf_upload` · คืนรายชื่อหน่วยงานจากสารบัญของไฟล์ (ไม่รวมหน่วยที่กันไว้/ชุดประเมินที่ยังไม่ปลดล็อก)"""
    if side not in ("A", "B"):
        raise ApiError("ฝั่งไฟล์ต้องเป็น A หรือ B")
    source_url = pdf_upload.clean_source_url(source_url)
    if pid:
        if not repo.get_project(pid):
            raise ApiError("ไม่พบงานตรวจที่ระบุ", 404, "not_found")
    stored, pages = pdf_upload.accept_pdf(stream, filename)
    if not pid:
        pid = repo.create_project("อัปโหลดเอง · เทียบเล่ม PDF", "before_after_reduction",
                                  "PDF ที่ผู้ใช้เลือกจากเครื่อง (ไม่ได้มาจากชั้นเล่ม)")
    source_pdfs.link(pid, side, stored, origin=source_pdfs.ORIGIN_UPLOAD, source_url=source_url)
    srcs = source_pdfs.for_project(pid)
    return {"project_id": pid, "side": side, "pages": pages, "sha256": stored.sha256,
            "file": stored.original_name, "sides_ready": sorted(srcs),
            "agencies": pdfshelf.agencies_of_file(filestore.path_for(stored.stored_name), stored.sha256)}


def _upload_run(pid: str, d: dict) -> dict:
    if not repo.get_project(pid):
        raise ApiError("ไม่พบงานตรวจที่ระบุ", 404, "not_found")
    if set(source_pdfs.for_project(pid)) != {"A", "B"}:
        raise ApiError("อัปโหลด PDF ให้ครบทั้งฉบับ A และฉบับ B ก่อน")
    return {"rid": pdfshelf.start_uploaded(pid, str(d.get("agency", "")))}


def _rerun(rid: str) -> dict:
    _writable(_view(rid))
    try:
        return {"rid": svc.rerun(rid)}
    except svc.PairError as e:              # ไม่ต้องคำนวณซ้ำ · ไฟล์เปลี่ยน · กดซ้ำพร้อมกัน — รอบเดิมไม่ถูกบล็อก
        raise ApiError(str(e), 409, "conflict")


def register(app) -> None:
    # ① ภาพรวม/คิว ───────────────────────────────────────────────────────────────────────────
    @app.get("/api/pdfpair/runs/{rid}")
    @api
    def api_pdfpair_run(request: Request, rid: str):
        v = _view(rid)
        return {"run": _run(v),
                "groups": [{"key": g.key, "label": g.label, "total": g.total, "decided": g.decided,
                            "pending": g.pending, "info": len(g.info)} for g in v.groups],
                "counts": {"actionable": v.actionable, "pending": v.pending, "info": v.info_count},
                "use_counts": v.use_counts, "next_pending_id": _next_pending(v),
                "item_change_ids": [f.id for f in v.item_changes], "rounding_policy": svc.ROUNDING_POLICY,
                "year_warnings": [{"side": s, "text": t} for s, t in v.year_warnings],
                "stage_warnings": [{"side": s, "text": t} for s, t in v.stage_warnings],
                "decisions": _decisions(), "preflight": _preflight(v, full=False)}

    @app.get("/api/pdfpair/runs/{rid}/findings")
    @api
    def api_pdfpair_findings(request: Request, rid: str, topic: str = ""):
        v = _view(rid)
        if topic and topic not in svc.TOPIC_LABELS:
            raise ApiError("หัวข้อไม่ถูกต้อง")
        return {"topic": topic, "findings": [_f(v, f) for f in v.result.findings if not topic or f.topic == topic]}

    # ② หลักฐาน A|B + บันทึกผล ───────────────────────────────────────────────────────────────
    @app.get("/api/pdfpair/runs/{rid}/f/{fid}")
    @api
    def api_pdfpair_finding(request: Request, rid: str, fid: str):
        v = _view(rid)
        f = v.finding(fid)
        if f is None:
            raise ApiError("ไม่พบข้อสังเกตที่ระบุ", 404, "not_found")
        ids = [x.id for x in v.result.findings]
        i = ids.index(fid)
        da, db = svc.text_diff(f.a.value, f.b.value) if f.topic == "text" and f.a.value and f.b.value else ([], [])
        fj = _f(v, f)
        for s, side in (("A", f.a), ("B", f.b)):            # ขนาดหน้า (pt · CropBox) ให้เลื่อนภาพทั้งหน้าไปที่กรอบ
            fj[s.lower()]["page_size"] = svc.page_size_of(v, s, side.page) if side.page else None
        return {"finding": fj, "prev_id": ids[i - 1] if i > 0 else "",
                "next_id": ids[i + 1] if i + 1 < len(ids) else "", "next_pending_id": _next_pending(v, fid),
                "diff": {"a": [list(x) for x in da], "b": [list(x) for x in db]},
                "rounding_policy": svc.ROUNDING_POLICY if f.parts else "",
                "writable": not v.superseded_by}

    @app.post("/api/pdfpair/runs/{rid}/f/{fid}/decide")
    @api
    async def api_pdfpair_decide(request: Request, rid: str, fid: str):
        d = await read_json(request)
        return await run_in_threadpool(_decide, rid, fid, d)

    # ③ ด่านก่อนส่งออก + ยืนยันปี + คำนวณซ้ำ ─────────────────────────────────────────────────
    @app.get("/api/pdfpair/runs/{rid}/preflight")
    @api
    def api_pdfpair_preflight(request: Request, rid: str):
        return _preflight(_view(rid))

    @app.post("/api/pdfpair/runs/{rid}/year")
    @api
    async def api_pdfpair_year(request: Request, rid: str):
        d = await read_json(request)
        return await run_in_threadpool(_year, rid, d)

    @app.post("/api/pdfpair/runs/{rid}/rerun")
    @api
    async def api_pdfpair_rerun(request: Request, rid: str):
        await read_json(request)
        return await run_in_threadpool(_rerun, rid)

    # ④ Audit ของรอบ ────────────────────────────────────────────────────────────────────────────
    @app.get("/api/pdfpair/runs/{rid}/audit")
    @api
    def api_pdfpair_audit(request: Request, rid: str):
        from ..storage import audit
        _view(rid)
        entries = []
        for e in pdfpair_repo.audit_entries(rid):
            try:
                detail = json.loads(e.get("detail_json") or "{}")
            except ValueError:
                detail = {}
            entries.append({"seq": e["seq"], "at": e["ts"], "action": e["action"],
                            "action_label": svc.AUDIT_ACTION_LABELS.get(e["action"], e["action"]),
                            "object_id": e["object_id"], "summary": svc.audit_summary(e), "detail": detail,
                            "entry_hash": e["entry_hash"]})
        return {"entries": entries, "chain": audit.verify_chain()}

    # ⑤ ชั้นเล่ม + เริ่มรอบ + รายการรอบ ─────────────────────────────────────────────────────────
    @app.get("/api/pdfpair/shelf")
    @api
    def api_pdfpair_shelf(request: Request, a: str = "", agency: str = ""):
        shelf = pdfshelf.volumes()
        vol = lambda x: {"key": x.key, "title": x.title, "fiscal_year": x.fiscal_year, "stage": x.stage,   # noqa: E731
                         "stage_label": x.stage_label, "volume_no": x.volume_no}
        out = {"shelf_label": pdfshelf.shelf_label(), "volumes": [vol(x) for x in shelf], "a": None,
               "agency": agency, "agencies": [], "suggest": [], "others": []}
        cur = next((x for x in shelf if x.key == a), None) if a else None
        if cur is not None:
            out["a"] = vol(cur)
            try:
                out["agencies"] = pdfshelf.agencies(cur)
            except pdfshelf.ShelfError as e:
                out["agency_error"] = str(e)
            sug = pdfshelf.suggest_b(cur, shelf)
            out["suggest"] = [{"key": x.key, "why": why} for x, why in sug]
            picked = {x.key for x, _w in sug} | {cur.key}
            out["others"] = [x.key for x in shelf if x.key not in picked]
        return out

    @app.post("/api/pdfpair/shelf/start")
    @api
    async def api_pdfpair_shelf_start(request: Request):
        d = await read_json(request)
        _pid, rid = await run_in_threadpool(pdfshelf.start, str(d.get("a", "")), str(d.get("b", "")),
                                            str(d.get("agency", "")))
        return {"rid": rid}

    # ⑥ อัปโหลด PDF จากเครื่อง (Bo แนะนำ · กิ๊ฟเลือก 28 ต.ค.) — ไม่ดึงจากลิงก์ ──────────────────────────────────
    @app.post("/api/pdfpair/uploads")
    @api
    async def api_pdfpair_upload(request: Request):
        verify_csrf(request, request.headers.get("x-csrf-token", ""))     # ก่อนอ่าน body
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > config.MAX_UPLOAD_BYTES + MAX_BODY:
            raise ApiError("ไฟล์ใหญ่เกินกว่าที่ระบบรับได้", 413, "too_large")
        form = await request.form(max_files=1, max_fields=4)
        f = form.get("file")
        if f is None or not hasattr(f, "read"):
            raise ApiError("กรุณาเลือกไฟล์ PDF")
        try:
            return await run_in_threadpool(_upload, str(form.get("side", "")), str(form.get("project_id", "")),
                                           str(form.get("source_url", "")), f.file, f.filename or "")
        finally:
            await f.close()

    @app.post("/api/pdfpair/uploads/{pid}/run")
    @api
    async def api_pdfpair_upload_run(request: Request, pid: str):
        d = await read_json(request)
        return await run_in_threadpool(_upload_run, pid, d)

    @app.get("/api/pdfpair/runs")
    @api
    def api_pdfpair_runs(request: Request, limit: int = 50):
        return {"runs": [{"id": r["id"], "created_at": r["created_at"], "mode": r["mode"],
                          "mode_label": svc.MODE_LABELS.get(r["mode"], r["mode"]), "agency": r["agency"],
                          "superseded_by": r["superseded_by"], "sides": r["sides"], "counts": r["counts"]}
                         for r in svc.run_list(limit=max(1, min(int(limit), 200)))]}


__all__ = ["register"]
