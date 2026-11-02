# -*- coding: utf-8 -*-
"""RedBook Verify - เว็บแอปพลิเคชันสำหรับตรวจสอบเอกสารงบประมาณ (local-first)

Phase 1 ให้เส้นทางทำงานครบวงหนึ่งเส้น: สร้างงานตรวจ อัปโหลดไฟล์จริงสองฝั่ง
ตรวจ metadata ดูผล ยืนยันหรือยกเว้นพร้อมเหตุผล และตรวจสอบ Audit Trail
การเปรียบเทียบเนื้อหา Excel และ PDF เป็นงานของ Phase 2 และ Phase 3
หน้าจอทุกหน้าจึงระบุสถานะการพัฒนาไว้ตรง ๆ ไม่แสดงผลตรวจตัวอย่างปนกับผลจริง
"""
import copy
import json
import logging
import mimetypes
import re
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, Query, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import (APP_NAME, APP_VERSION, CANONICAL_MODEL_VERSION, ENGINE_VERSION,
               RULE_SET_VERSION, config, holdout, privacy)
from .core.hashing import sha256_text
from .core.status import (MachineStatus, ReviewStatus, status_color, th_label)
from .readers import excel_reader
from .rules import catalog
from .rules.finding import assign_ids, result_hash
from .rules.metadata_checks import check_metadata
from .services import amounts as amounts_service
from .services import books as book_service
from .services import categories as cat_service
from .services import decisions as dec_service
from .services import evidence as evidence_service
from .services import export as export_service
from .services import preflight as preflight_service
from .services import quarterly as quarterly_service
from .services import review as review_service
from .services import source_rows as source_rows_service
from .services import pdf_evidence as pdf_ev
from .services import pdf_upload
from .services import t1b as t1b_service
from .services import verify_view as vv
from .services import workflow as workflow_service
from .storage import audit, book_links, files as filestore, repository as repo, source_pdfs
from .storage import t1b_decisions, t1b_preflight, t1b_repo
from .storage.db import init_db, jdump
from .web.security import (CSRF_FIELD, SECURITY_HEADERS, CSRFError, SecurityMiddleware,
                           verify_csrf)

# Python บน Windows ไม่รู้จัก .woff2 แล้วส่งเป็น application/octet-stream — ระบุชนิดให้ถูก (#24 D2)
mimetypes.add_type("font/woff2", ".woff2")

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

MODE_LABELS = {
    "year_to_year": "ปีก่อนเทียบปีปัจจุบัน",
    "before_after_reduction": "ก่อนเทียบหลังปรับลด",
}
SIDE_LABELS = {
    "year_to_year": {"A": "ฝั่ง A - ปีก่อน", "B": "ฝั่ง B - ปีปัจจุบัน",
                     "REF": "ไฟล์อ้างอิงเพิ่มเติม (ถ้ามี)"},
    "before_after_reduction": {"A": "ฝั่ง A - ฉบับก่อนปรับลด",
                               "B": "ฝั่ง B - ฉบับหลังปรับลด",
                               "REF": "หลักฐานรายการปรับลดที่อนุมัติ (ถ้ามี)"},
}

# ป้ายแสดงผลของงานที่อ้างอิงคู่ ร่าง พ.ร.บ. → พ.ร.บ. ปีเดียวกัน (Bo · #24 ก่อน merge)
# workflow/engine ยังใช้โหมด ``before_after_reduction`` เดิม — เปลี่ยนเฉพาะคำบนหน้าจอ
# เพราะ "ก่อนเทียบหลังปรับลด" ทำให้เข้าใจผิดว่า พ.ร.บ. คือฉบับหลังปรับลดของร่าง
DRAFT_ACT_MODE_LABEL = "ตรวจความแตกต่างระหว่างร่างและ พ.ร.บ."
DRAFT_ACT_SIDE_LABELS = {"A": "ฝั่ง A - ร่าง พ.ร.บ.", "B": "ฝั่ง B - พ.ร.บ.",
                         "REF": "เอกสารอ้างอิงเพิ่มเติม (ถ้ามี)"}


def is_draft_act(a, b) -> bool:
    """คู่ที่ฝั่ง A เป็นร่าง และฝั่ง B เป็น พ.ร.บ. ปีงบเดียวกัน — อ่านขั้นจากทะเบียน ไม่เดาจากชื่อ"""
    return bool(a and b and a.fiscal_year == b.fiscal_year
                and a.stage_code == "draft" and b.stage_code == "act")


def mode_display(mode: str, a=None, b=None) -> str:
    if mode == "before_after_reduction" and is_draft_act(a, b):
        return DRAFT_ACT_MODE_LABEL
    return MODE_LABELS.get(mode, mode)


# จำกัดจำนวนแถวที่สแกนตอนทำรายการโครงสร้างไฟล์ เพื่อไม่ให้หน้าเว็บค้างกับไฟล์ใหญ่
STRUCTURE_SCAN_ROWS = 2000

# ══════════════════════════════════════════════════════════════════════════════
#  เมนูซ้ายคงที่ (คำสั่งกิ๊ฟ 23 ก.ย. 2569)
# ══════════════════════════════════════════════════════════════════════════════
#
# 🔴 เหตุที่ต้องมี — ก่อนหน้านี้หน้าคิว หน้าส่งออก และหน้า Audit ของรอบตรวจ
# ไปถึงได้ด้วยการถูก redirect หรือพิมพ์ URL เท่านั้น ผู้ใช้ที่เปิดแอปขึ้นมาใหม่
# จึง "หาไม่เจอ" ทั้งที่ของมีอยู่ · เมนูนี้จึงต้องครบทุกขั้นของงานเสมอ
#
# รายการเมนู: (key, ชื่อบนจอ, path กลาง, path เมื่อรู้ว่าอยู่รอบตรวจใด)
NAV_ITEMS = (
    ("projects", "งานตรวจ", "/", ""),
    ("runs", "รอบตรวจ", "/t1b/runs", ""),
    ("queue", "คิวพิจารณา", "/queue", "/t1b/runs/{rid}/queue"),
    ("preflight", "Preflight", "/preflight", "/t1b/runs/{rid}/preflight"),
    ("export", "ส่งออก", "/export", "/t1b/runs/{rid}/export"),
    ("audit", "Audit", "/audit", "/t1b/runs/{rid}/audit"),
    ("rules", "บัญชีกฎ", "/rules", ""),
)


def nav_active_for(path: str) -> str:
    """เมนูใดควรถูกเน้น สำหรับ path ที่กำลังเปิดอยู่

    ตัดสินจาก **ส่วนท้ายของ path** ก่อน เพราะหน้าของรอบตรวจใช้ prefix เดียวกัน
    (``/t1b/runs/<id>/queue`` กับ ``/t1b/runs/<id>/export``)
    """
    if path == "/projects/new":
        return "new"
    if path.startswith("/books"):
        return "books"
    if path.startswith("/verify"):
        return "verify"
    for key in ("queue", "preflight", "export", "audit"):
        if path == f"/{key}" or path.endswith(f"/{key}"):
            return key
    if path.startswith("/rules"):
        return "rules"
    if path.startswith("/pdfpair/shelf"):
        return "pdfshelf"
    if path.startswith("/pdfpair/runs/"):
        return "queue"                      # รายการข้อสังเกต/หลักฐานของรอบเทียบเล่ม = คิวพิจารณาของสายนี้
    if path.startswith("/t1b/") or path.startswith("/runs/"):
        return "runs"
    if path == "/" or path.startswith("/projects") or path.startswith("/findings"):
        return "projects"
    return ""


#: เมนูเมื่ออยู่ในสายเทียบเล่ม PDF ↔ PDF — ชี้ไปของรอบเทียบเล่มที่เปิดอยู่ ไม่ใช่รอบตรวจ Excel (T1B)
PDFPAIR_NAV = {"runs": "/projects/{pid}/pdfpair", "queue": "/pdfpair/runs/{rid}",
               "preflight": "/pdfpair/runs/{rid}/preflight", "export": "/pdfpair/runs/{rid}/export",
               "audit": "/pdfpair/runs/{rid}/audit"}


def nav_context(path: str, *, run_id: str = "", counts: dict = None, pdfpair: dict = None) -> dict:
    """ข้อมูลที่เมนูซ้ายต้องใช้ — ไม่แตะฐานข้อมูล ไม่คำนวณอะไรเอง

    ``counts`` เป็น ``{key: (จำนวน, เตือนหรือไม่)}`` ที่หน้านั้น ๆ นับมาแล้ว
    หน้าที่ไม่มีตัวเลขให้บอกก็ไม่ต้องส่งมา — เมนูจะไม่แสดงตัวเลขเปล่า ๆ
    ``pdfpair`` = ``{"rid", "pid"}`` เมื่ออยู่ในสายเทียบเล่ม PDF — เมนูของขั้นงานชี้ไปของรอบนั้น
    """
    counts = counts or {}
    items = []
    for key, label, base, scoped in NAV_ITEMS:
        if pdfpair and key in PDFPAIR_NAV:
            items.append({"key": key, "label": label, "count": counts.get(key, (None, False))[0],
                          "alert": counts.get(key, (None, False))[1],
                          "href": PDFPAIR_NAV[key].format(rid=pdfpair["rid"], pid=pdfpair["pid"])})
            continue
        href = scoped.format(rid=run_id) if (run_id and scoped) else base
        n, alert = counts.get(key, (None, False))
        items.append({"key": key, "label": label, "href": href,
                      "count": n, "alert": alert})
    # 🔴 คีย์ชื่อ "menu" ไม่ใช่ "items" — ใน Jinja ``nav.items`` จะไปได้
    # เมธอด ``dict.items`` ของ Python แทนค่าในดิกต์ แล้วลูปพังเงียบ ๆ
    return {"menu": items, "active": nav_active_for(path), "run_id": run_id,
            "lane": "pdfpair" if pdfpair else ""}

log = logging.getLogger("redbook")


class RedactingFormatter(logging.Formatter):
    """ตัวจัดรูปแบบล็อกที่ **กลบเส้นทางสัมบูรณ์ทิ้งเสมอ**

    🔴 คำสั่ง Bo (Issue #1 · SECURITY PRIORITY ข้อ 2) — ล็อกของแอปนี้อยู่บน
    เครื่องผู้ใช้ก็จริง แต่ถูกแนบไปกับรายงานปัญหาได้ง่ายที่สุดในบรรดาแฟ้มทั้งหมด
    การกลบที่ formatter ทำให้ **ทุก** จุดที่เรียก ``log.*`` ปลอดภัยโดยอัตโนมัติ
    แทนที่จะต้องหวังว่าผู้เขียนโค้ดทุกคนจะจำได้ทุกครั้ง

    ครอบคลุมทั้งข้อความหลักและ traceback ที่ ``log.exception`` แนบมา
    """

    #: อักขระควบคุมทั้งหมด (รวม CR/LF/TAB) — ค่าที่มาจาก request ห้ามขึ้นบรรทัดใหม่ในล็อก
    _CONTROL = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]")
    _CONTROL_EXCEPT_LF = re.compile(r"[\x00-\x09\x0b-\x1f\x7f  ]")
    #: คำนำหน้าบรรทัดต่อของรายการเดียว (traceback) — บรรทัดต่อจึงไม่มีทางขึ้นด้วย timestamp หรือค่าของผู้ใช้
    CONTINUATION = "  | "
    #: เพดานความยาวข้อความหนึ่งรายการ — กัน request ขนาดใหญ่ถล่มล็อก
    MAX_MESSAGE_CHARS = 4000

    @classmethod
    def sanitize(cls, text: str) -> str:
        """แทนอักขระควบคุมด้วย escape ที่อ่านออก (เช่น ``\\x0d``) และตัดความยาว"""
        out = cls._CONTROL.sub(lambda m: "\\x%02x" % ord(m.group()), text)
        if len(out) > cls.MAX_MESSAGE_CHARS:
            out = out[:cls.MAX_MESSAGE_CHARS] + "…[truncated]"
        return out

    def format(self, record: logging.LogRecord) -> str:
        # 🔴 กัน log injection (Security Gate #23 · F-11): ข้อความหลักถูกกลบอักขระควบคุม **ก่อน**
        # ประกอบบรรทัด — traceback ที่ logging แนบเอง (exc_text) ยังขึ้นบรรทัดใหม่ได้ตามปกติ
        record = copy.copy(record)
        record.msg = self.sanitize(record.getMessage())
        record.args = ()
        text = super().format(record)
        head, sep, rest = text.partition("\n")
        if sep:
            # traceback/stack ที่ logging แนบ มีข้อความ exception ซึ่งอาจมีค่าจากผู้ใช้ (CR/LF + timestamp ปลอม) —
            # กลบอักขระควบคุม (ยกเว้น LF ของ traceback เอง) และนำหน้าทุกบรรทัดต่อด้วย CONTINUATION ⇒ มีแต่บรรทัดแรก
            # ของรายการที่ขึ้นด้วย timestamp (Bo REVIEW #42 6433564226 ข้อ 3 · พบจากเทสต์ 500 จริง)
            rest = self._CONTROL_EXCEPT_LF.sub(lambda m: "\\x%02x" % ord(m.group()), rest)
            text = head + "\n" + "\n".join(self.CONTINUATION + ln for ln in rest.split("\n"))
        return privacy.redact_text(text)


def _setup_logging() -> None:
    config.ensure_dirs()
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    handler = logging.FileHandler(config.LOG_DIR / "app.log", encoding="utf-8")
    handler.setFormatter(RedactingFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.addHandler(handler)


def create_app() -> FastAPI:
    _setup_logging()
    config.ensure_dirs()
    init_db()
    t1b_repo.init_t1b_schema()
    t1b_preflight.init_preflight_schema()
    evidence_service.init_schemas()
    book_links.init_schema()
    source_pdfs.init_schema()
    removed = filestore.purge_temp()
    if removed:
        log.info("purge_temp removed=%s", removed)

    app = FastAPI(title=APP_NAME, version=APP_VERSION,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SecurityMiddleware)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.autoescape = True
    # มาตรฐานหน่วย/ทศนิยมตัวเดียวทั้งระบบ (#24) — ล้านบาท = 4 ตำแหน่งเสมอ · บาท = บาท
    templates.env.filters["amount"] = amounts_service.format_amount
    templates.env.filters["amount_num"] = amounts_service.format_number
    templates.env.globals.update(
        app_name=APP_NAME, app_version=APP_VERSION,
        engine_version=ENGINE_VERSION, rule_set_version=RULE_SET_VERSION,
        canonical_model_version=CANONICAL_MODEL_VERSION,
        mode_labels=MODE_LABELS, mode_display=mode_display, csrf_field=CSRF_FIELD,
        demo_mode=config.DEMO_MODE,
        th_label=th_label, status_color=status_color,
        MachineStatus=MachineStatus, ReviewStatus=ReviewStatus,
    )

    def page(request: Request, name: str, ctx: dict = None, status_code: int = 200):
        data = {"csrf_token": getattr(request.state, "csrf_token", ""),
                "steps": None}
        data.update(ctx or {})
        # ทะเบียนเล่มเป็น DEV fixture (ประกาศ synthetic) → ทุกหน้าต้องติดป้าย ไม่ให้เข้าใจว่าเป็นทะเบียนจริง
        try:
            _cat = book_service.catalog()
            data.setdefault("book_fixture_synthetic", _cat.synthetic)
            data.setdefault("book_lookup", _cat.get)      # แถบเล่มอ้างอิง (_refs.html) อ่านขั้น/ปก/ป้ายจากทะเบียน
        except (OSError, ValueError, KeyError):
            data.setdefault("book_fixture_synthetic", False)
            data.setdefault("book_lookup", lambda _id: None)
        # เมนูซ้ายประกอบที่นี่ที่เดียว — ทุกหน้าจึงมีทางเข้าครบเหมือนกันเสมอ
        # โดยที่ route แต่ละเส้นไม่ต้องจำว่าต้องส่งอะไรมาให้เทมเพลต
        summary = data.get("s")
        run_id = data.get("nav_run_id") or getattr(summary, "run_id", "") or ""
        data.setdefault("nav", nav_context(request.url.path, run_id=run_id,
                                           counts=data.get("nav_counts"),
                                           pdfpair=data.get("nav_pdfpair")))
        return templates.TemplateResponse(request, name, data, status_code=status_code)

    def _project_books(pid: str):
        """(เล่ม A, เล่ม B) ของงานตรวจ ตามทะเบียนปัจจุบัน — ไม่มี/หาไม่เจอ = None"""
        refs = book_links.for_project(pid or "")
        try:
            cat = book_service.catalog()
        except (OSError, ValueError, KeyError):
            return None, None
        return tuple(cat.get(refs[s]["book_id"]) if s in refs else None for s in ("A", "B"))

    def _mode_label_for(mode: str, pid: str) -> str:
        return mode_display(mode, *_project_books(pid))

    def fail(request: Request, message: str, status_code: int = 400,
             detail: str = None):
        """หน้าแสดงข้อผิดพลาดที่ผู้ใช้เห็น - ไม่มี stack trace ไม่มี path ภายใน"""
        error_id = uuid.uuid4().hex[:12]
        log.warning("error_id=%s status=%s path=%s detail=%s",
                    error_id, status_code, request.url.path, detail or message)
        # 🔴 ข้อความที่ผู้ใช้เห็นต้องผ่านการกลบเส้นทางอีกชั้น แม้จะเป็นข้อความ
        # ที่เราเขียนเองก็ตาม — เพราะบางข้อความประกอบจากชื่อไฟล์ที่ผู้ใช้ส่งมา
        return page(request, "error.html",
                    {"message": privacy.redact_text(message),
                     "error_id": error_id}, status_code)

    # ---------------------------------------------------------------- errors
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        messages = {
            403: "คำขอนี้ไม่ผ่านการตรวจสอบความปลอดภัย โปรดเปิดหน้าเดิมใหม่แล้วลองอีกครั้ง",
            404: "ไม่พบหน้าที่เรียก",
            405: "วิธีเรียกหน้านี้ไม่ถูกต้อง",
            413: "ไฟล์ใหญ่เกินกว่าที่ระบบรับได้",
        }
        return fail(request, messages.get(exc.status_code, "ไม่สามารถดำเนินการได้"),
                    exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # 🔴 ค่าปริยายของ FastAPI ตอบ JSON 422 ที่ **สะท้อนค่าที่ผู้ใช้ส่งมา** (ฟิลด์ input) —
        # เปลี่ยนเป็นหน้าข้อผิดพลาดมาตรฐาน 400 ที่ไม่สะท้อนค่า (Security Gate #23 · F-10)
        return fail(request, "ค่าที่ส่งมาไม่ถูกต้องตามรูปแบบที่ระบบรับได้", 400,
                    detail="request_validation_error")

    @app.exception_handler(CSRFError)
    async def csrf_error(request: Request, exc: CSRFError):
        audit.security_event("csrf_rejected", "warning", {"event": exc.event},
                             client=request.client.host if request.client else None)
        return fail(request,
                    "คำขอนี้ไม่ผ่านการตรวจสอบความปลอดภัย โปรดเปิดหน้าเดิมใหม่แล้วลองอีกครั้ง",
                    403, detail=exc.event)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        error_id = uuid.uuid4().hex[:12]
        log.exception("error_id=%s unhandled at %s", error_id, request.url.path)
        resp = page(request, "error.html",
                    {"message": "เกิดข้อผิดพลาดภายในระบบ ระบบบันทึกเหตุการณ์ไว้แล้ว",
                     "error_id": error_id}, 500)
        # 🔴 handler ของ Exception ทำงาน **นอก** SecurityMiddleware (ชั้น ServerErrorMiddleware)
        # หน้า 500 จึงเคยออกไปโดยไม่มี CSP/nosniff/no-store — พบจาก Security Gate #23 (F-02)
        for k, v in SECURITY_HEADERS.items():
            resp.headers[k] = v
        return resp

    # ------------------------------------------------------------- dashboard
    #: จำนวนรอบตรวจล่าสุดที่แดชบอร์ดเปิดกลับเข้าไปได้ทันที
    #: 🔴 จำกัดจำนวนเพราะแต่ละใบต้องประเมินด่านใหม่จากของจริง (ไม่มีแคช)
    DASHBOARD_RECENT_RUNS = 6

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        all_t1b = t1b_repo.list_runs(limit=200)
        # 🔴 ``run_count`` ของ repo นับรอบตรวจ metadata (สาย T1A) เท่านั้น
        # ถ้าเอามาแสดงเฉย ๆ งานที่เทียบเอกสารไปแล้วจะขึ้นเลข 0 ซึ่งอ่านผิด
        t1b_per_project: dict[str, int] = {}
        for row in all_t1b:
            key = row.get("project_id") or ""
            t1b_per_project[key] = t1b_per_project.get(key, 0) + 1

        projects = repo.list_projects()
        from .storage import pdfpair_repo
        for p in projects:
            p["mode_label"] = _mode_label_for(p["mode"], p["id"])
            p["compare_count"] = t1b_per_project.get(p["id"], 0)
            # 🔴 สายเทียบเล่ม PDF เก็บ PDF และรอบเทียบคนละตาราง — ไม่นับ = งานที่แนบ PDF แล้วขึ้น "ไฟล์ 0"
            p["file_count"] = (p.get("file_count") or 0) + len(source_pdfs.for_project(p["id"]))
            p["compare_count"] += len(pdfpair_repo.list_runs(p["id"], limit=1000))

        # 🔴 คำสั่งกิ๊ฟ 23 ก.ย. — แดชบอร์ดต้องเห็นรอบตรวจล่าสุดพร้อมสถานะทันที
        # และกดกลับเข้ารอบเดิมได้ โดยไม่ต้องจำหรือพิมพ์ URL
        project_names = {p["id"]: p["name"] for p in projects}
        recent = []
        for row in all_t1b[:DASHBOARD_RECENT_RUNS]:
            state = _run_state(row["id"])
            if state is None:
                continue
            view, ann, counts, bundle, pf = state
            exported = _exported(row["id"])
            steps = _run_steps(row["id"], counts, pf,
                               current=workflow_service.STEP_ANALYZE,
                               exported=exported)
            current = steps.current
            recent.append({
                "row": row, "s": view.summary, "counts": counts, "pf": pf,
                "project_name": project_names.get(row.get("project_id") or "", ""),
                "exported": exported,
                "next_label": current.label if current else "ส่งออกเรียบร้อยแล้ว",
                "next_detail": current.detail if current else "",
                "next_href": (current.href if current and current.href
                              else f"/t1b/runs/{row['id']}"),
                "next_no": current.no if current else len(steps.steps),
            })
        cat = book_service.catalog()
        return page(request, "dashboard.html",
                    {"projects": projects, "recent": recent, "cat": cat,
                     "type_groups": book_service.TYPE_GROUPS})

    # ══════════════════════════════════════════════════════════ คลังเล่ม (#24)
    # หาเล่ม → ดูรายละเอียด → เปิด PDF ทางการ → "ตั้งงานตรวจโดยอ้างอิงเล่มนี้" (D3)
    # 🔴 route กลุ่มนี้อ่านทะเบียนเล่มอย่างเดียว ยกเว้นการตั้งงานตรวจ ซึ่งเรียก
    # ``repo.create_project`` เดิม แล้วส่งต่อเข้าขั้น 2 ของ workflow เดิม — ไม่มีเส้นทางคู่ขนาน
    def _catalog(request: Request):
        """ทะเบียนเล่ม หรือหน้าข้อผิดพลาดที่บอกผู้ใช้ตรง ๆ — ไม่ปล่อย 500 เปล่า"""
        try:
            return book_service.catalog(), None
        except (OSError, ValueError, KeyError) as e:
            log.warning("book catalog unavailable: %s", type(e).__name__)
            return None, fail(request, "โหลดทะเบียนเล่มไม่สำเร็จ — ลองใหม่อีกครั้ง หรือแจ้งผู้ดูแลระบบ"
                              " (ไฟล์ทะเบียนเล่มหายหรืออ่านไม่ได้)", 503)

    @app.get("/books", response_class=HTMLResponse)
    async def books_index(request: Request):
        cat, err = _catalog(request)
        if err:
            return err
        query = book_service.Query.from_params(request.query_params, cat.years)
        result = book_service.search(cat, query)
        # โหมดเลือกฉบับที่สอง: "ID" = ไปหน้าเริ่มตรวจ (#24 เดิม) · "ID~cmp" = กลับหน้าเปรียบเทียบ
        pick_raw = (request.query_params.get("pick") or "")[:80]
        pick_cmp = pick_raw.endswith("~cmp")
        pick_for = cat.get(pick_raw.removesuffix("~cmp"))
        return page(request, "books.html", {
            "cat": cat, "query": query, "result": result, "pick_for": pick_for,
            "pick_raw": pick_raw if pick_for else "",
            "pick_target": "/books/compare" if pick_cmp else "/verify/start",
            "sorts": book_service.SORTS, "type_groups": book_service.TYPE_GROUPS,
            "type_labels": book_service.TYPE_GROUP_LABEL,
            "views": book_service.VIEWS, "stages": book_service.STAGES,
            "files": book_service.FILES, "stage_labels": dict(book_service.STAGES),
            "file_labels": dict(book_service.FILES),
        })

    @app.get("/books/thumb/{book_id}.jpg")
    async def book_thumb(book_id: str):
        """ภาพปกหน้าแรก (สร้างในเครื่องด้วย scripts/build_book_thumbnails.py) — ไม่มี = 404
        การ์ดจะแสดงปกจำลองจาก metadata แทนเอง · รับเฉพาะรหัสที่มีในทะเบียน กัน path traversal"""
        cat = book_service.catalog()
        book = cat.get(book_id)
        path = book_service.THUMB_DIR / f"{book.id}.jpg" if book else None
        if not path or not path.is_file():
            return JSONResponse({"detail": "no thumbnail"}, status_code=404)
        return FileResponse(path, media_type="image/jpeg",
                            headers={"Cache-Control": "private, max-age=86400"})

    @app.get("/books/compare", response_class=HTMLResponse)
    async def book_compare(request: Request, a: str = "", b: str = ""):
        """ทางเข้าการเปรียบเทียบ — เลือกคู่ (ร่าง↔พ.ร.บ. หรือ ปีต่อปี) แล้วส่งต่อเข้างานตรวจเดิม
        หน้านี้เทียบ "ข้อมูลเล่ม" เท่านั้น ไม่มีกฎเปรียบเทียบใหม่ (non-goal)"""
        cat, err = _catalog(request)
        if err:
            return err
        anchor = cat.get(a)
        if not anchor:
            # ยังไม่เลือกเล่ม = สถานะว่างที่บอกทางไปต่อ ไม่ใช่หน้าข้อผิดพลาด (#24 P3)
            return page(request, "book_compare_empty.html", {"cat": cat, "unknown": bool(a)},
                        status_code=404 if a else 200)
        pair = book_service.make_pair(cat, a, b) if b else None
        counterpart = cat.counterpart(anchor)
        return page(request, "book_compare.html", {
            "cat": cat, "anchor": anchor, "pair": pair, "counterpart": counterpart,
            "others": cat.confirmed_other_years(anchor),
            "pending": cat.pending_pairs(anchor),
            "is_stage_pair": bool(pair and pair.complete and counterpart
                                  and {pair.a.id, pair.b.id} == {anchor.id, counterpart.id}),
        }, status_code=400 if pair and pair.error else 200)

    @app.get("/books/states", response_class=HTMLResponse)
    async def book_states(request: Request):
        """แค็ตตาล็อกสถานะของการ์ด (ว่าง / ไม่มีไฟล์ / ลิงก์เสีย / ไม่มีภาพปก / กำลังโหลด / ผิดพลาด)
        สำหรับตรวจ UX — ทะเบียนจริงไม่มีลิงก์เสีย จึงต้องมีหน้าที่ให้เห็นทุกสถานะ
        ใช้เล่มจริงหนึ่งเล่มเป็นฐานแล้วเปลี่ยนเฉพาะสถานะ พร้อมป้าย "ตัวอย่างสถานะ" ทุกการ์ด"""
        cat, err = _catalog(request)
        if err:
            return err
        return page(request, "book_states.html",
                    {"cat": cat, "samples": book_service.state_samples(cat)})

    @app.get("/books/{book_id}", response_class=HTMLResponse)
    async def book_detail(request: Request, book_id: str):
        cat, err = _catalog(request)
        if err:
            return err
        book = cat.get(book_id)
        if not book:
            return fail(request, "ไม่พบเล่มที่ระบุในคลังเล่ม — ลิงก์อาจมาจากทะเบียนเล่มรุ่นเก่า", 404)
        # ความสัมพันธ์ทุกชนิดมาจาก pairs[] ของ #27 เท่านั้น (คำตัดสิน Bo) — ไม่มีรายการที่เดาจากชื่อ
        return page(request, "book_detail.html", {
            "cat": cat, "book": book, "others": cat.confirmed_other_years(book),
            "pending": cat.pending_pairs(book),
            "counterpart": cat.counterpart(book),
        })

    @app.get("/verify/start", response_class=HTMLResponse)
    async def verify_start(request: Request, a: str = "", b: str = ""):
        cat = book_service.catalog()
        pair = book_service.make_pair(cat, a, b)
        anchor = pair.a or pair.b
        # แนะนำเฉพาะคู่ที่ทะเบียน #27 ยืนยัน (MATCHED) — ห้ามใช้ pair_key ที่จับจากชื่อ (= การเดา)
        suggestions = ([x for x in [cat.counterpart(anchor)] if x] + cat.confirmed_other_years(anchor)
                       if anchor and not pair.complete else [])
        return page(request, "verify_start.html", {
            "pair": pair, "suggestions": suggestions, "anchor": anchor,
            "steps": workflow_service.build(current=workflow_service.STEP_PROJECT),
        }, status_code=400 if pair.error else 200)

    @app.post("/verify/start")
    async def verify_start_submit(request: Request, a: str = Form(""), b: str = Form(""),
                                  name: str = Form(""), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        cat = book_service.catalog()
        pair = book_service.make_pair(cat, a, b)
        if not pair.complete:
            return fail(request, pair.error or "ต้องเลือกเล่มให้ครบสองฉบับก่อนเริ่มตรวจ", 400)
        note = (f"เล่มอ้างอิงจากคลังเล่ม · ฝั่ง A: {pair.a.kicker} ปี {pair.a.fiscal_year}"
                f" · ฝั่ง B: {pair.b.kicker} ปี {pair.b.fiscal_year}")
        try:
            pid = repo.create_project(name.strip() or pair.suggested_name, pair.mode, note)
        except ValueError as e:
            return fail(request, str(e), 400)
        book_links.link(pid, "A", pair.a)
        book_links.link(pid, "B", pair.b)
        return RedirectResponse(f"/projects/{pid}", status_code=303)

    def _demo_pair_paths():
        """คู่ไฟล์สาธิตสังเคราะห์ที่ ``scripts/demo_launch.py`` สร้างไว้ — เฉพาะโหมดสาธิต

        🔴 ตัวสร้างไฟล์อยู่นอกแพ็กเกจโดยเจตนา (ด่านสถาปัตยกรรมเดิม #9) แอปจึงแค่
        **หยิบไฟล์ที่สร้างไว้แล้ว** มาใส่ผ่านเส้นทางเก็บไฟล์จริง ไม่สร้างเอง
        """
        if not config.DEMO_MODE:
            return None
        folder = config.DATA_DIR / "demo_files"
        a = folder / "DEMO_SYNTHETIC_A_before_reduction.xlsx"
        b = folder / "DEMO_SYNTHETIC_B_after_reduction.xlsx"
        return (a, b) if a.is_file() and b.is_file() else None

    @app.post("/projects/{pid}/demo-files")
    async def project_demo_files(request: Request, pid: str, csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        project = repo.get_project(pid)
        paths = _demo_pair_paths()
        if not project or paths is None:
            return fail(request, "ใช้ได้เฉพาะโหมดสาธิต", 404)
        refs = book_links.for_project(pid)
        for side, path in zip(("A", "B"), paths):
            with open(path, "rb") as fh:
                stored = filestore.save_stream(fh, path.name)
            ref = refs.get(side) or {}
            repo.attach_file(pid, side, stored, {
                "fiscal_year": ref.get("fiscal_year") or (2569 if side == "A" else 2570),
                "agency_name": "สำนักงานสาธิตระบบตรวจคาดแดง",
                "doc_kind": "ข้อมูลสาธิต (สังเคราะห์)",
            })
        return RedirectResponse(f"/projects/{pid}", status_code=303)


    # ------------------------------------------- ทางลัดจากเมนูเมื่อยังไม่รู้รอบ
    #: เมนูซ้ายชี้มาที่นี่เมื่อผู้ใช้ยังไม่ได้เปิดรอบตรวจใด — หน้าที่ของ route
    #: กลุ่มนี้คือ **พาไปให้ถึง** ไม่ใช่ขึ้น 404 ให้ผู้ใช้ไปหาทางเอง
    RUN_PICK_INTENTS = {
        "queue": ("คิวพิจารณา", "เลือกรอบตรวจที่ต้องการพิจารณารายการ", "queue"),
        "preflight": ("ตรวจก่อนส่งออก", "เลือกรอบตรวจที่ต้องการตรวจก่อนส่งออก",
                      "preflight"),
        "export": ("ส่งออกชุดงาน", "เลือกรอบตรวจที่ต้องการส่งออก", "export"),
    }

    def _pick_run(request: Request, intent: str):
        title, sub, leaf = RUN_PICK_INTENTS[intent]
        runs = t1b_repo.list_runs()
        if len(runs) == 1:
            return RedirectResponse(f"/t1b/runs/{runs[0]['id']}/{leaf}",
                                    status_code=303)
        return page(request, "pick_run.html", {
            "runs": runs, "title": title, "sub": sub, "leaf": leaf,
            "intent": intent,
        })

    @app.get("/queue", response_class=HTMLResponse)
    async def pick_queue(request: Request):
        return _pick_run(request, "queue")

    @app.get("/preflight", response_class=HTMLResponse)
    async def pick_preflight(request: Request):
        return _pick_run(request, "preflight")

    @app.get("/export", response_class=HTMLResponse)
    async def pick_export(request: Request):
        return _pick_run(request, "export")

    @app.get("/healthz")
    async def healthz():
        return JSONResponse({"status": "ok", "app": APP_NAME, "version": APP_VERSION})

    # ------------------------------------------------------------- projects
    @app.get("/projects/new", response_class=HTMLResponse)
    async def project_new_form(request: Request):
        return page(request, "project_new.html", {})

    @app.post("/projects/new")
    async def project_new(request: Request, name: str = Form(""), mode: str = Form(""),
                          note: str = Form(""), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            pid = repo.create_project(name, mode, note)
        except ValueError as e:
            return fail(request, str(e), 400)
        return RedirectResponse(f"/projects/{pid}", status_code=303)

    @app.get("/projects/{pid}", response_class=HTMLResponse)
    async def project_detail(request: Request, pid: str):
        project = repo.get_project(pid)
        if not project:
            return fail(request, "ไม่พบงานตรวจที่ระบุ", 404)
        pf = repo.project_files(pid)
        runs = repo.list_runs(pid)
        ready = bool(pf.get("A") and pf.get("B"))
        # รอบตรวจ T1B ของงานนี้ — ใช้ทั้งบอกขั้นตอนและเป็นทางเข้ากลับเข้ารอบเดิม
        t1b_runs = [r for r in t1b_repo.list_runs(limit=50)
                    if r.get("project_id") == pid]
        return page(request, "project_detail.html", {
            "project": project,
            "mode_label": _mode_label_for(project["mode"], pid),
            "side_labels": (DRAFT_ACT_SIDE_LABELS if is_draft_act(*_project_books(pid))
                            else SIDE_LABELS.get(project["mode"], SIDE_LABELS["year_to_year"])),
            "pf": pf, "runs": runs, "t1b_runs": t1b_runs,
            "max_mb": config.MAX_UPLOAD_BYTES // (1024 * 1024),
            "ready": ready,
            "book_refs": book_links.for_project(pid),
            "demo_pair_available": _demo_pair_paths() is not None,
            "steps": workflow_service.build(
                current=(workflow_service.STEP_ANALYZE if ready
                         else workflow_service.STEP_UPLOAD),
                project_id=pid,
                run_id=t1b_runs[0]["id"] if t1b_runs else "",
                files_ready=ready, analyzed=bool(t1b_runs),
                pending=0, total_findings=0),
        })

    @app.post("/projects/{pid}/upload")
    async def project_upload(request: Request, pid: str, side: str = Form(""),
                             fiscal_year: str = Form(""), agency_code: str = Form(""),
                             agency_name: str = Form(""), doc_kind: str = Form(""),
                             upload: UploadFile = File(...), csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        project = repo.get_project(pid)
        if not project:
            return fail(request, "ไม่พบงานตรวจที่ระบุ", 404)
        if side not in repo.SIDES:
            return fail(request, "ฝั่งไฟล์ไม่ถูกต้อง", 400)

        # 🔴 ด่านชุดข้อมูลกันไว้ (P1) — ตรวจ **ชื่อที่ผู้ใช้ส่งมา** เพราะชื่อที่
        # ระบบตั้งเองตอนเก็บจะไม่เหลือร่องรอยเดิมให้ตรวจอีก · ปฏิเสธตั้งแต่ยัง
        # ไม่เขียนลงดิสก์ เพื่อไม่ให้ไฟล์ holdout เข้ามาอยู่ในพื้นที่งานเลย
        if holdout.is_holdout(upload.filename or ""):
            await upload.close()
            audit.security_event(
                "upload_rejected_p1_holdout", "info",
                {"project_id": pid, "side": side,
                 "reason": holdout.holdout_reason(upload.filename or "")},
                client=request.client.host if request.client else None)
            return fail(request, holdout.UPLOAD_NOTICE, 400,
                        detail="p1_holdout_upload_blocked")

        client = request.client.host if request.client else None
        try:
            stored = filestore.save_stream(upload.file, upload.filename)
        except filestore.UploadRejected as e:
            audit.security_event(e.event, "warning",
                                 {"project_id": pid, "side": side,
                                  "declared_name": filestore.sanitize_display_name(
                                      upload.filename), **e.detail},
                                 client=client)
            return fail(request, e.user_message, 400, detail=e.event)
        finally:
            await upload.close()

        year = None
        if fiscal_year.strip():
            try:
                year = int(fiscal_year.strip())
            except ValueError:
                return fail(request, "ปีงบประมาณต้องเป็นตัวเลข", 400)

        repo.attach_file(pid, side, stored, {
            "fiscal_year": year,
            "agency_code": agency_code.strip()[:40] or None,
            "agency_name": agency_name.strip()[:200] or None,
            "doc_kind": doc_kind.strip()[:100] or None,
        })
        return RedirectResponse(f"/projects/{pid}", status_code=303)

    @app.get("/projects/{pid}/delete", response_class=HTMLResponse)
    async def project_delete_confirm(request: Request, pid: str):
        """หน้ายืนยันก่อนลบ — แสดงให้เห็นชัดว่าอะไรจะหายไปและอะไรจะเหลือ

        🔴 `PROVISIONAL_LOCAL_RETENTION POLICY` — กิ๊ฟกำหนดว่ายังไม่ทำการลบ
        อัตโนมัติจนกว่าจะมีหน้าจอที่ผู้ใช้เห็นชัดและทดสอบการลบได้
        หน้านี้คือเงื่อนไขนั้น การลบเกิดจากการกดของผู้ใช้เท่านั้น
        """
        project = repo.get_project(pid)
        if not project:
            return fail(request, "ไม่พบงานตรวจที่ระบุ", 404)
        return page(request, "project_delete.html", {
            "project": project,
            "preview": repo.project_deletion_preview(pid),
        })

    @app.post("/projects/{pid}/delete")
    async def project_delete(request: Request, pid: str,
                             confirm: str = Form(""),
                             csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        project = repo.get_project(pid)
        if not project:
            return fail(request, "ไม่พบงานตรวจที่ระบุ", 404)
        if confirm != "ลบ":
            return fail(request,
                        "ต้องพิมพ์คำว่า ลบ ในช่องยืนยัน จึงจะลบงานตรวจนี้ได้",
                        400)
        result = repo.delete_project(pid)
        book_links.delete_for_project(pid)
        log.info("project_deleted pid=%s files=%s t1b_runs=%s", pid,
                 result.get("removed_files"), result.get("t1b_runs_removed"))
        return RedirectResponse("/?deleted=1", status_code=303)

    @app.post("/projects/{pid}/precheck")
    async def project_precheck(request: Request, pid: str, csrf_token: str = Form("")):
        """ตรวจ metadata ก่อนเริ่ม (กฎ M01-M05) แล้วบันทึกเป็นการรันหนึ่งครั้ง"""
        verify_csrf(request, csrf_token)
        project = repo.get_project(pid)
        if not project:
            return fail(request, "ไม่พบงานตรวจที่ระบุ", 404)
        pf = repo.project_files(pid)
        if not (pf.get("A") and pf.get("B")):
            return fail(request, "ต้องอัปโหลดไฟล์ให้ครบทั้งฝั่ง A และฝั่ง B ก่อน", 400)

        started = time.perf_counter()
        cfg = {"stage": "metadata_precheck", "mode": project["mode"]}
        cfg_hash = sha256_text(jdump(cfg))
        versions = {"engine_version": ENGINE_VERSION,
                    "rule_set_version": RULE_SET_VERSION,
                    "canonical_model_version": CANONICAL_MODEL_VERSION,
                    "parsers": excel_reader.parser_versions()}
        rid = repo.create_run(pid, project["mode"], pf, versions, cfg, cfg_hash)
        repo.save_run_rules(rid, catalog.snapshot(project["mode"]))

        findings = check_metadata(project["mode"], pf.get("A"), pf.get("B"), pf.get("REF"))
        findings = assign_ids(rid, findings)
        if findings:
            repo.insert_findings(rid, findings)
        duration_ms = int((time.perf_counter() - started) * 1000)
        repo.finish_run(rid, "completed_precheck", duration_ms, len(findings),
                        result_hash(findings))
        audit.record("run_completed", "run", rid,
                     {"project_id": pid, "stage": "metadata_precheck",
                      "findings": len(findings), "duration_ms": duration_ms,
                      "engine_version": ENGINE_VERSION,
                      "rule_set_version": RULE_SET_VERSION,
                      "file_a_sha256": pf["A"]["sha256"],
                      "file_b_sha256": pf["B"]["sha256"]})
        repo.set_project_status(pid, "prechecked")
        return RedirectResponse(f"/runs/{rid}", status_code=303)

    # ------------------------------------------------------------------ runs
    @app.get("/runs/{rid}", response_class=HTMLResponse)
    async def run_summary(request: Request, rid: str, machine_status: str = "",
                          review_status: str = "", severity: str = "",
                          rule_id: str = ""):
        run = repo.get_run(rid)
        if not run:
            return fail(request, "ไม่พบผลการตรวจที่ระบุ", 404)
        project = repo.get_project(run["project_id"])
        findings = repo.list_findings(rid, machine_status or None, review_status or None,
                                      severity or None, rule_id or None)
        summary = repo.summarize_findings(rid)
        return page(request, "run_summary.html", {
            "run": run, "project": project, "findings": findings, "summary": summary,
            "mode_label": _mode_label_for(run["mode"], run["project_id"]),
            "file_a": repo.get_file(run["file_a_id"]) if run["file_a_id"] else None,
            "file_b": repo.get_file(run["file_b_id"]) if run["file_b_id"] else None,
            "filters": {"machine_status": machine_status, "review_status": review_status,
                        "severity": severity, "rule_id": rule_id},
            "catalog": catalog,
        })

    @app.get("/runs/{rid}/review", response_class=HTMLResponse)
    async def review_queue(request: Request, rid: str):
        run = repo.get_run(rid)
        if not run:
            return fail(request, "ไม่พบผลการตรวจที่ระบุ", 404)
        pending = repo.list_findings(rid, review_status=ReviewStatus.PENDING.value)
        return page(request, "review_queue.html", {
            "run": run, "findings": pending, "catalog": catalog,
            "project": repo.get_project(run["project_id"]),
        })

    @app.get("/runs/{rid}/compare", response_class=HTMLResponse)
    async def compare_view(request: Request, rid: str):
        run = repo.get_run(rid)
        if not run:
            return fail(request, "ไม่พบผลการตรวจที่ระบุ", 404)
        file_a = repo.get_file(run["file_a_id"]) if run["file_a_id"] else None
        file_b = repo.get_file(run["file_b_id"]) if run["file_b_id"] else None
        struct = {}
        errors = {}
        for label, f in (("A", file_a), ("B", file_b)):
            if not f:
                continue
            if f["kind"] != "xlsx":
                errors[label] = "ระยะนี้ยังอ่านโครงสร้างได้เฉพาะไฟล์ Excel"
                continue
            try:
                struct[label] = excel_reader.read_structure(
                    filestore.path_for(f["stored_name"]), STRUCTURE_SCAN_ROWS)
            except excel_reader.ExcelReadError as e:
                errors[label] = str(e)
        return page(request, "compare_view.html", {
            "run": run, "project": repo.get_project(run["project_id"]),
            "file_a": file_a, "file_b": file_b, "struct": struct, "errors": errors,
            "scan_rows": STRUCTURE_SCAN_ROWS,
        })

    # -------------------------------------------------------------- findings
    @app.get("/findings/{fid}", response_class=HTMLResponse)
    async def finding_detail(request: Request, fid: str):
        f = repo.get_finding(fid)
        if not f:
            return fail(request, "ไม่พบผลตรวจที่ระบุ", 404)
        run = repo.get_run(f["run_id"])
        rule = catalog.BY_ID.get(f["rule_id"])
        return page(request, "finding_detail.html", {
            "f": f, "run": run, "rule": rule,
            "project": repo.get_project(run["project_id"]) if run else None,
            "file_a": repo.get_file(run["file_a_id"]) if run and run["file_a_id"] else None,
            "file_b": repo.get_file(run["file_b_id"]) if run and run["file_b_id"] else None,
        })

    @app.post("/findings/{fid}/decide")
    async def finding_decide(request: Request, fid: str, decision: str = Form(""),
                             note: str = Form(""), reviewer: str = Form(""),
                             csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        allowed = {ReviewStatus.CONFIRMED_ERROR.value,
                   ReviewStatus.CONFIRMED_VALID_CHANGE.value,
                   ReviewStatus.EXEMPTED.value}
        if decision not in allowed:
            return fail(request, "ผลการพิจารณาไม่ถูกต้อง", 400)
        f = repo.get_finding(fid)
        if not f:
            return fail(request, "ไม่พบผลตรวจที่ระบุ", 404)
        who = (reviewer or "").strip()[:120] or "ไม่ระบุชื่อผู้ตรวจ"
        try:
            repo.decide_finding(fid, decision, note, who)
        except ValueError as e:
            return fail(request, str(e), 400)
        return RedirectResponse(f"/findings/{fid}", status_code=303)

    # ------------------------------------------------------------------- T1B
    # 🔴 เส้นทางของ T1B แยกจากเส้นทางของ T1A ทั้งชุด (prefix ``/t1b/``)
    # และ **ไม่มี route ใดใน block นี้ import ``redbook.t1b.*`` โดยตรง** —
    # ทุกอย่างผ่าน ``services.t1b`` ตามคำสั่ง Bo (LANE B)
    def _t1b_filters(q: str, flag: list[str] | None, ftype: list[str] | None,
                     only_review: str, cat: list[str] | None = None,
                     status: list[str] | None = None) -> dict:
        return {
            "query": (q or "").strip()[:200],
            "flags": tuple(x for x in (flag or []) if x)[:20],
            "types": tuple(x for x in (ftype or []) if x)[:40],
            "only_review": only_review in ("1", "true", "on", "yes"),
            "categories_": tuple(x for x in (cat or []) if x in cat_service.CATEGORY_ORDER),
            "statuses": tuple(x for x in (status or []) if x in review_service.QUEUE_STATUSES),
        }

    def _t1a_filters(filters: dict) -> dict:
        """ตัวกรองชุดย่อยที่ finding_detail() ของชั้น t1b เดิมรู้จัก"""
        return {k: filters[k] for k in ("query", "flags", "types", "only_review")}

    def _run_state(rid: str):
        """สถานะครบชุดของหนึ่งรอบตรวจ — โหลดจากของจริงทุกครั้ง ไม่แคช

        คืน ``(view, ann, counts, bundle, pf)`` หรือ ``None`` เมื่อไม่พบรอบ

        🔴 ``pf`` คำนวณใหม่ทุกครั้งที่เรียก — ห้ามเก็บผลไว้ที่ใด
        มิฉะนั้นด่านจะอ้างอิงสภาพเก่าที่ไม่ตรงกับความจริงตอนกดส่งออก
        """
        view = t1b_service.load_run(rid)
        if view is None:
            return None
        ann = review_service.annotate(view, review_service.status_map(rid))
        counts = review_service.counts(view, ann)
        bundle = export_service.build(view)
        ids = preflight_service.unmapped_ids(view)
        scope = t1b_preflight.scope_hash(ids)
        ack = t1b_preflight.get_ack(rid, scope) if ids else None
        pf = preflight_service.evaluate(view, counts, bundle, ack=ack,
                                        unmapped_scope=scope)
        return view, ann, counts, bundle, pf

    def _run_nav_counts(counts, pf) -> dict:
        """ตัวเลขบนเมนูซ้ายของหน้าที่อยู่ในรอบตรวจหนึ่ง"""
        return {
            "queue": (counts.pending, counts.pending > 0),
            "preflight": (pf.blocking_count, pf.blocking_count > 0),
            "export": (pf.export_count, False),
        }

    def _run_steps(rid: str, counts, pf, *, current: str, exported: bool = False):
        return workflow_service.build(
            current=current, run_id=rid, files_ready=True, analyzed=True,
            pending=counts.pending, total_findings=counts.total,
            preflight_ok=pf.ok, preflight_blocking=pf.blocking_count,
            exported=exported)

    def _filters_desc(filters: dict) -> str:
        parts = []
        if filters["query"]: parts.append(f"ค้นหา “{filters['query']}”")
        if filters["types"]: parts.append("ชนิด " + ", ".join(filters["types"]))
        if filters["categories_"]: parts.append("หมวด " + ", ".join(filters["categories_"]))
        if filters["statuses"]: parts.append("สถานะ " + ", ".join(filters["statuses"]))
        if filters["only_review"]: parts.append("เฉพาะที่ต้องให้คนตรวจ")
        return " · ".join(parts) or "ไม่มีตัวกรอง (ทั้งรอบ)"

    @app.post("/projects/{pid}/analyze")
    async def project_analyze(request: Request, pid: str,
                              csrf_token: str = Form("")):
        """เปรียบเทียบเนื้อในสมุดงานสองฝั่งด้วยเครื่องยนต์ T1B

        🔴 เส้นนี้คือสิ่งที่หายไประหว่าง "อัปโหลดได้" กับ "วิเคราะห์ได้" ·
        ``ฝั่ง A`` = ฉบับตั้งต้น (ก่อนปรับลด) · ``ฝั่ง B`` = ฉบับที่นำมาตรวจ

        🔴 **แยกจาก ``/precheck`` โดยเจตนา** — precheck เป็นของสาย T1A
        (กฎ ``M01``–``M05`` ตรวจ metadata) การรวมสองอย่างจะทำให้ผลของสองระเบียบวิธี
        ปนกันในการรันเดียว ซึ่งเป็นสิ่งที่โครงสร้างข้อมูลตั้งใจแยกไว้ตั้งแต่ต้น
        """
        verify_csrf(request, csrf_token)
        project = repo.get_project(pid)
        if not project:
            return fail(request, "ไม่พบงานตรวจที่ระบุ", 404)
        pf = repo.project_files(pid)
        if not (pf.get("A") and pf.get("B")):
            return fail(request,
                        "ต้องอัปโหลดไฟล์ให้ครบทั้งฝั่ง A และฝั่ง B ก่อน", 400)

        rid = f"t1b_{uuid.uuid4().hex[:16]}"
        started = time.perf_counter()
        try:
            view = t1b_service.run_from_workbooks(
                filestore.path_for(pf["A"]["stored_name"]),
                filestore.path_for(pf["B"]["stored_name"]),
                run_id=rid)
        except holdout.HoldoutViolation as e:
            # ด่านชั้นสุดท้าย — ปกติถูกกันไปตั้งแต่ตอนอัปโหลดแล้ว
            return fail(request, holdout.UPLOAD_NOTICE, 400,
                        detail=f"p1_holdout_blocked:{e.reason}")
        except t1b_service.WorkbookRejected as e:
            # 🔴 ผู้ใช้เห็นเฉพาะ ``user_message`` · รายละเอียดลงล็อกอย่างเดียว
            # **ไม่บันทึกรอบ** เมื่อแฟ้มใช้เทียบไม่ได้ — รอบที่พบ 0 รายการ
            # อ่านได้ว่า "ตรวจแล้วไม่พบความต่าง" ซึ่งคนละเรื่องกับ "อ่านไม่ออก"
            audit.security_event("t1b_workbook_rejected", "info",
                                 {"project_id": pid, "code": e.code},
                                 client=request.client.host
                                 if request.client else None)
            return fail(request, e.user_message, 400,
                        detail=f"{e.code}: {e.detail}")
        except filestore.UploadRejected as e:
            # ชื่อไฟล์ภายในผิดรูป — ไม่ควรเกิดเพราะระบบเป็นผู้ตั้งชื่อเอง
            return fail(request, "ไม่พบไฟล์ที่อัปโหลดไว้ในระบบ", 400, detail=str(e))

        t1b_repo.save_run(view, project_id=pid, run_id=rid)
        duration_ms = int((time.perf_counter() - started) * 1000)

        # 🔴 audit trail บันทึก **จำนวนนับและแฮชไฟล์** เท่านั้น
        # ห้ามบันทึกยอดเงินหรือชื่อรายการ — ตารางนี้ลบไม่ได้ตาม trigger
        s = view.summary
        audit.record("t1b_run_completed", "t1b_run", rid, {
            "project_id": pid, "duration_ms": duration_ms,
            "identity_verdict": s.identity_verdict,
            "automatic_pairs": s.automatic_pairs,
            "total_findings": s.total_findings,
            "requiring_review": s.requiring_review,
            "key_version": s.key_version,
            "matching_version": s.matching_version,
            "compare_version": s.compare_version,
            "service_version": s.service_version,
            "privacy_version": privacy.PRIVACY_VERSION,
            "file_a_sha256": pf["A"]["sha256"],
            "file_b_sha256": pf["B"]["sha256"],
        })
        return RedirectResponse(f"/t1b/runs/{rid}", status_code=303)

    @app.get("/t1b/runs", response_class=HTMLResponse)
    async def t1b_runs(request: Request):
        return page(request, "t1b_runs.html", {"runs": t1b_repo.list_runs()})

    # ------------------------------------------------ ผู้ช่วยตรวจงบ (#24 · IA รอบใหม่)
    # หน้าแรกของรอบตรวจตอบสามคำถาม — เงิน · ตัวชี้วัดและรายการ · ความต่าง A↔B
    # แล้วเจาะลงทีละชั้นจนถึงแถวในไฟล์ต้นฉบับ (Discover → Compare → Explain → Verify)
    # 🔴 ชั้นแสดงผลเท่านั้น — ตัวเลขทุกตัวมาจากข้อสังเกตที่เครื่องยนต์ออกแล้ว
    #    (``services/verify_view.py``) · ศัพท์เครื่องยนต์ย้ายไปหน้า /details

    def _run_sha256(rid: str) -> dict:
        """SHA-256 ของไฟล์สองฝั่งที่รอบนี้ใช้จริง — จาก Audit Trail (ไม่มี = ว่าง)"""
        for e in audit.entries(limit=50, object_id=rid):
            if e.get("action") == "t1b_run_completed":
                try:
                    d = json.loads(e.get("detail_json") or "{}")
                except ValueError:
                    d = {}
                return {"A": d.get("file_a_sha256") or "", "B": d.get("file_b_sha256") or ""}
        return {"A": "", "B": ""}

    def _run_sources(rid: str, view):
        """(SourceVerification, {ฝั่ง: path ไฟล์ที่ใช้ตรวจ}, ป้ายชนิดการเทียบ)"""
        run_row = t1b_repo.get_run(rid) or {}
        pid = run_row.get("project_id") or ""
        refs = book_links.for_project(pid) if pid else {}
        files = repo.project_files(pid) if pid else {}
        proj = repo.get_project(pid) if pid else None
        run_sha = _run_sha256(rid)
        try:
            cat = book_service.catalog()
        except (OSError, ValueError, KeyError):
            cat = None
        sides, paths, books = {}, {}, {}
        for side in ("A", "B"):
            r = refs.get(side) or {}
            bk = cat.get(r["book_id"]) if (r and cat) else None
            books[side] = bk
            fr = files.get(side) or {}
            path, stored = None, ""
            if fr.get("stored_name"):
                try:
                    path = filestore.path_for(fr["stored_name"])
                except filestore.UploadRejected:
                    path = None
                if path is not None and path.exists():
                    stored = source_rows_service.sha256_file(path)
                else:
                    path = None
            paths[side] = path
            sides[side] = vv.SourceSide(
                side=side,
                title=(bk.headline if bk else r.get("title", "")),
                fiscal_year=(bk.fiscal_year if bk else r.get("fiscal_year")),
                stage=(bk.stage if bk else ""),
                ministries=(tuple(bk.ministries) if bk else ()),
                source_url=(bk.pdf_url if bk else r.get("pdf_url", "")),
                source_page=(bk.source_page if bk else r.get("source_page", "")),
                retrieved_at=(bk.retrieved_at if bk else ""),
                linked_at=r.get("linked_at", ""),
                book_id=r.get("book_id", ""),
                synthetic=bool(bk and bk.synthetic),
                file_name=fr.get("original_name", ""),
                uploaded_at=fr.get("uploaded_at", ""),
                run_sha256=run_sha.get(side, ""),
                stored_sha256=stored,
                declared_kind=(fr.get("declared_doc_kind") or "")[:100],
                declared_year=fr.get("declared_fiscal_year"),
            )
        sv = vv.source_verification(
            summary=view.summary, a=sides["A"], b=sides["B"],
            a_stage_code=books["A"].stage_code if books["A"] else "",
            b_stage_code=books["B"].stage_code if books["B"] else "")
        mode_label = mode_display(proj["mode"], books["A"], books["B"]) if proj else ""
        return sv, paths, mode_label

    def _verify_ctx(rid: str):
        state = _run_state(rid)
        if state is None:
            return None
        view, ann, counts, bundle, pf = state
        run_row = t1b_repo.get_run(rid) or {}
        sv, paths, mode_label = _run_sources(rid, view)
        rc = vv.run_context(
            sv,
            source_rows_service.workbook_context(paths.get("A"), sv.a.run_sha256)
            if sv.a.file_matches_run else {},
            source_rows_service.workbook_context(paths.get("B"), sv.b.run_sha256)
            if sv.b.file_matches_run else {},
            scope=vv.year_scope(view))
        return {
            "book_refs": book_links.for_project(run_row.get("project_id") or ""),
            "view": view, "s": view.summary, "ov": vv.build_overview(view),
            "sv": sv, "src_paths": paths, "mode_label": mode_label, "rc": rc,
            "vv": vv, "dec": dec_service, "counts": counts, "pf": pf, "ann": ann,
            "nav_counts": _run_nav_counts(counts, pf),
            "steps": _run_steps(rid, counts, pf,
                                current=workflow_service.STEP_ANALYZE,
                                exported=_exported(rid)),
        }

    @app.get("/t1b/runs/{rid}", response_class=HTMLResponse)
    async def t1b_run_summary(request: Request, rid: str):
        ctx = _verify_ctx(rid)
        if ctx is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        return page(request, "verify_overview.html", ctx)

    @app.get("/t1b/runs/{rid}/money", response_class=HTMLResponse)
    @app.get("/t1b/runs/{rid}/changes", response_class=HTMLResponse)
    @app.get("/t1b/runs/{rid}/differences", response_class=HTMLResponse)
    @app.get("/t1b/runs/{rid}/review", response_class=HTMLResponse)
    async def t1b_verify_list(request: Request, rid: str, kind: str = ""):
        ctx = _verify_ctx(rid)
        if ctx is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        lens = request.url.path.rstrip("/").rsplit("/", 1)[-1]
        all_items = vv.items_for(ctx["ov"], lens)
        ctx.update({"lens": lens, "kind": kind if kind in vv.KIND_LABELS else "",
                    "items": vv.items_for(ctx["ov"], lens, kind),
                    "kinds": vv.kind_counts(all_items), "all_count": len(all_items)})
        return page(request, "verify_list.html", ctx)

    def _compare_back(back: str) -> str:
        return back if (back in vv.LENSES or back in ("review", "queue", "preflight")) else "differences"

    def _compare_siblings(ctx, back: str) -> list[str]:
        if back == "queue":
            return [x.id for g in vv.queue_groups(ctx["ov"], ctx["ann"]) for x in g.items]
        if back == "preflight":
            return [x.id for g in vv.queue_groups(ctx["ov"], ctx["ann"], state="pending")
                    for x in g.items]
        return [x.id for x in vv.items_for(ctx["ov"], back)]

    @app.get("/t1b/runs/{rid}/compare/{fid}", response_class=HTMLResponse)
    async def t1b_verify_compare(request: Request, rid: str, fid: str, back: str = ""):
        return _render_compare(request, rid, fid, back)

    @app.post("/t1b/runs/{rid}/compare/{fid}/decide", response_class=HTMLResponse)
    async def t1b_verify_decide(request: Request, rid: str, fid: str,
                                choice: str = Form(""), note: str = Form(""),
                                back: str = Form(""), ret: str = Form(""),
                                csrf_token: str = Form("")):
        """ตัดสินจากหน้าหลักฐาน A | B — ใช้กับทุกข้อสังเกตในรายการนี้ (หนึ่ง audit ต่อหนึ่งใบ)

        ปุ่มภาษาคน 6 แบบ map ลงสถานะเดิม 4 แบบ (``vv.DECISION_CHOICES``)
        เหตุผลที่เลือกบันทึกนำหน้าหมายเหตุ · กลับคำตัดสินเดิมต้องเขียนเหตุผลเพิ่มเสมอ
        """
        verify_csrf(request, csrf_token)
        back = _compare_back(back)
        ctx = _verify_ctx(rid)
        if ctx is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        it = ctx["ov"].by_id(fid)
        if it is None:
            return fail(request, "ไม่พบรายการที่ระบุในรอบการตรวจนี้", 404)
        if choice not in vv.DECISION_BY_KEY:
            return _render_compare(request, rid, fid, back, "เลือกผลการตรวจก่อนบันทึก", 400)
        ann, view = ctx["ann"], ctx["view"]
        decided_before = [f for f in it.findings
                          if ann.get(f.finding_id) and ann[f.finding_id].status != dec_service.PENDING]
        if decided_before and not (note or "").strip():
            return _render_compare(request, rid, fid, back,
                                   "รายการนี้เคยตัดสินแล้ว — การเปลี่ยนคำตัดสินต้องเขียนเหตุผลเพิ่ม", 400)
        status = vv.DECISION_BY_KEY[choice][1]
        full_note = vv.decision_note(choice, note)
        sib = _compare_siblings(ctx, back)
        errors = []
        for f in it.findings:
            a = ann.get(f.finding_id)
            try:
                dec_service.record(view, f, status, note=full_note,
                                   expected_latest_seq=a.latest_seq if a else 0)
            except dec_service.DecisionError as e:
                errors.append(str(e))
        if errors:
            return _render_compare(request, rid, fid, back,
                                   "บันทึกไม่ครบทุกข้อสังเกตในรายการนี้ — " + errors[0], 409)
        if back == "preflight":
            return RedirectResponse(f"/t1b/runs/{rid}/preflight?decided=1", status_code=303)
        if ret == "list" and back == "queue":
            # ตัดสินจากหน้าต่างซ้อนของคิว → กลับคิวที่แถวเดิม
            return RedirectResponse(f"/t1b/runs/{rid}/queue?decided=1#it-{it.id}", status_code=303)
        pos = sib.index(it.id) + 1 if it.id in sib else 0
        if pos and pos < len(sib):
            return RedirectResponse(f"/t1b/runs/{rid}/compare/{sib[pos]}?back={back}&saved=1",
                                    status_code=303)
        return RedirectResponse(f"/t1b/runs/{rid}/compare/{it.id}?back={back}&saved=1",
                                status_code=303)

    def _render_compare(request: Request, rid: str, fid: str, back: str,
                        decision_error: str = "", status_code: int = 200):
        ctx = _verify_ctx(rid)
        if ctx is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        it = ctx["ov"].by_id(fid)
        if it is None:
            return fail(request, "ไม่พบรายการที่ระบุในรอบการตรวจนี้", 404)
        sv, paths = ctx["sv"], ctx["src_paths"]
        # เซลล์ที่ "เปลี่ยน" (เน้นแรงกว่าเซลล์ที่ระบบแค่อ้างอิง)
        changed_refs = {
            "A": {c.f.baseline.cell for c in it.cells if c.changed and c.f.baseline},
            "B": {c.f.current.cell for c in it.cells if c.changed and c.f.current},
        }
        excerpts = {}
        for side, loc, src in (("A", it.a_loc, sv.a), ("B", it.b_loc, sv.b)):
            if loc is None:
                excerpts[side] = None
                continue
            locs = [c.f.baseline if side == "A" else c.f.current for c in it.cells]
            excerpts[side] = source_rows_service.excerpt(
                paths.get(side), expected_sha256=src.run_sha256, sheet=loc.sheet,
                row=loc.row, target_cells=[x.cell for x in locs if x is not None and x.cell],
                file_name=src.file_name,
                # หน่วยสองฝั่งต่างกัน ⇒ ไม่จัดรูปแบบตามหน่วยใดหน่วยหนึ่ง (แสดงค่าดิบ)
                unit="" if "unit" in it.kinds else it.unit)
        back = _compare_back(back)
        sib = _compare_siblings(ctx, back)
        pos = sib.index(it.id) + 1 if it.id in sib else 0
        ctx.update({"it": it, "excerpts": excerpts, "back": back, "changed_refs": changed_refs,
                    "back_label": {"queue": "คิวพิจารณา", "preflight": "ตรวจก่อนส่งออก",
                                   "review": "ควรตรวจทาน"}.get(back) or vv.LENSES.get(back, ""),
                    "ist": vv.item_state(it, ctx["ann"]), "unread": vv.item_unread(it),
                    "reasons": vv.issue_reasons(it), "decision_error": decision_error,
                    "saved": request.query_params.get("saved") == "1",
                    "pos": pos, "sib_total": len(sib),
                    "prev_id": sib[pos - 2] if pos > 1 else "",
                    "next_id": sib[pos] if pos and pos < len(sib) else ""})
        run_row = t1b_repo.get_run(rid) or {}
        pid = run_row.get("project_id") or ""
        pdfv = {s_: _pdf_view(pid, it, s_) for s_ in ("A", "B")}
        ctx.update({"pdfv": pdfv, "pid": pid, "pdf_ev": pdf_ev,
                    "pdf_origin_labels": source_pdfs.ORIGIN_LABELS,
                    "panel": request.query_params.get("panel") == "1"})
        if ctx["panel"]:
            # โหมดหน้าต่างซ้อน (คิว/Preflight) — ส่งเฉพาะเนื้อหลักฐาน ไม่มีโครงหน้า
            return templates.TemplateResponse(request, "verify_panel.html",
                                              {**ctx, "csrf_token": getattr(
                                                  request.state, "csrf_token", "")},
                                              status_code=status_code)
        return page(request, "verify_compare.html", ctx, status_code)

    # ------------------------------------------- PDF ต้นฉบับเป็นภาพหลักฐาน (PDF-first)
    # 🔴 แพ็กเกจไม่มีโค้ดเครือข่าย — PDF เข้ามาทาง "แนบเอง" หรือเครื่องมือนอกแพ็กเกจ
    #    ``scripts/fetch_source_pdfs.py`` (ดึงจากลิงก์ทางการในทะเบียนเล่ม) เท่านั้น
    #    ตำแหน่งบน PDF = ผลค้นข้อความ (services/pdf_evidence) ไม่ใช่ผลจับคู่ของเครื่องยนต์

    def _source_pdf(pid: str, side: str):
        """(แถว PDF ที่ผูกไว้, path ที่ใช้ได้) — ไฟล์หาย/แฮชไม่ตรง = path เป็น None"""
        row = source_pdfs.for_project(pid).get(side) if pid else None
        if not row:
            return None, None
        try:
            path = filestore.path_for(row["stored_name"])
        except filestore.UploadRejected:
            return row, None
        if not path.exists() or source_rows_service.sha256_file(path) != row["sha256"]:
            return row, None
        return row, path

    def _pdf_numbers(it, side: str) -> list:
        out = []
        for i, c in enumerate(it.cells, 1):
            v = c.a if side == "A" else c.b
            if v is None:
                continue
            col = (str(c.f.fiscal_year) if c.f.fiscal_year
                   else vv.CATEGORY_TH.get(c.f.budget_category or "", ""))
            # ปีนอกช่วงเทียบ (มีฉบับเดียว) = กรอบเทาไม่มีเลขกำกับ — ไม่ใช่ประเด็นที่ต้องอธิบาย
            out.append(pdf_ev.Number(vv.number_variants(v, it.unit), c.changed,
                                     0 if c.only_side else i, col))
        return out

    def _pdf_view(pid: str, it, side: str) -> dict:
        row, path = _source_pdf(pid, side)
        view = {"row": row, "ok": False, "loc": None, "error": ""}
        if row is None:
            return view
        if path is None:
            view["error"] = "ไฟล์ PDF ที่แนบไว้หายหรือถูกแก้หลังแนบ (SHA-256 ไม่ตรง) — แนบใหม่"
            return view
        loc_xl = it.a_loc if side == "A" else it.b_loc
        try:
            if loc_xl is not None:
                label = it.label_a if side == "A" else it.label_b
                loc = pdf_ev.locate(path, row["sha256"], label=label or it.title,
                                    numbers=_pdf_numbers(it, side),
                                    context=[it.first.parent_plan, it.first.section_title],
                                    side=side)
            else:
                loc = pdf_ev.locate_area(path, row["sha256"], side=side, anchors=[
                    x for x in (it.heading, it.first.section_title, it.first.parent_plan) if x])
        except RuntimeError:
            view["error"] = "เครื่องนี้ไม่มีตัวอ่าน PDF ของผลิตภัณฑ์ (pdfplumber + pypdfium2)"
            return view
        except Exception:  # noqa: BLE001 — PDF เสีย/อ่านไม่ได้ ต้องไม่ทำให้หน้าล้ม
            view["error"] = "อ่าน PDF ฉบับนี้ไม่ได้ (ไฟล์อาจเสียหายหรือไม่มีชั้นข้อความ)"
            return view
        view.update({"ok": loc.ok, "loc": loc, "path": path})
        return view

    @app.get("/t1b/runs/{rid}/compare/{fid}/pdf/{side}.png")
    async def t1b_verify_pdf_png(request: Request, rid: str, fid: str, side: str, full: str = ""):
        if side not in ("A", "B"):
            return fail(request, "ฝั่งไม่ถูกต้อง", 404)
        ctx = _verify_ctx(rid)
        it = ctx["ov"].by_id(fid) if ctx else None
        if it is None:
            return fail(request, "ไม่พบรายการที่ระบุในรอบการตรวจนี้", 404)
        pid = (t1b_repo.get_run(rid) or {}).get("project_id") or ""
        view = _pdf_view(pid, it, side)
        if not view["ok"]:
            return fail(request, "ไม่มีภาพ PDF ของรายการนี้", 404)
        png = pdf_ev.render(view["path"], view["row"]["sha256"], view["loc"],
                            full_page=full == "1")
        return Response(content=png, media_type="image/png",
                        headers={"Cache-Control": "private, max-age=300"})

    @app.post("/projects/{pid}/source-pdf")
    async def project_source_pdf(request: Request, pid: str, side: str = Form(""),
                                 back: str = Form(""), upload: UploadFile = File(...),
                                 csrf_token: str = Form("")):
        """แนบ PDF ต้นฉบับของฉบับ A/B เป็นภาพหลักฐาน — ผ่านด่านเดียวกับการอัปโหลดสมุดงาน"""
        verify_csrf(request, csrf_token)
        if not repo.get_project(pid):
            return fail(request, "ไม่พบงานตรวจที่ระบุ", 404)
        if side not in ("A", "B"):
            return fail(request, "ฝั่งไฟล์ไม่ถูกต้อง", 400)
        # ด่านเดียวกับ API อัปโหลด (services.pdf_upload): ชนิด · ขนาด · โครงสร้าง PDF · จำนวนหน้า · ไฟล์เสียถูกลบ
        try:
            stored, _pages = pdf_upload.accept_pdf(upload.file, upload.filename)
        except pdf_upload.UploadError as e:
            return fail(request, str(e), 400, detail=e.event)
        finally:
            await upload.close()
        source_pdfs.link(pid, side, stored, origin=source_pdfs.ORIGIN_UPLOAD)
        # กลับไปหน้าเดิมได้เฉพาะ path ภายในของรอบตรวจ (กัน open redirect)
        dest = back if ((back.startswith("/t1b/runs/") or back == f"/projects/{pid}/pdfpair")
                        and "//" not in back) else f"/projects/{pid}"
        return RedirectResponse(dest, status_code=303)

    @app.get("/t1b/runs/{rid}/sources", response_class=HTMLResponse)
    async def t1b_verify_sources(request: Request, rid: str):
        ctx = _verify_ctx(rid)
        if ctx is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        return page(request, "verify_sources.html", ctx)

    @app.get("/t1b/runs/{rid}/details", response_class=HTMLResponse)
    async def t1b_run_details(request: Request, rid: str):
        state = _run_state(rid)
        if state is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        view, ann, counts, bundle, pf = state
        return page(request, "t1b_run_details.html", {
            "book_refs": book_links.for_project((t1b_repo.get_run(rid) or {}).get("project_id") or ""),
            "view": view, "s": view.summary, "svc": t1b_service,
            "counts": counts, "pf": pf,
            "nav_counts": _run_nav_counts(counts, pf),
            "steps": _run_steps(rid, counts, pf,
                                current=workflow_service.STEP_ANALYZE,
                                exported=_exported(rid)),
        })

    @app.get("/t1b/runs/{rid}/queue", response_class=HTMLResponse)
    async def t1b_queue(request: Request, rid: str, q: str = "",
                        flag: list[str] = Query(default=None),
                        ftype: list[str] = Query(default=None),
                        cat: list[str] = Query(default=None),
                        status: list[str] = Query(default=None),
                        only_review: str = "", page_no: int = Query(
                            default=1, alias="page"),
                        per_page: int = t1b_service.DEFAULT_PER_PAGE):
        # IA #24: ค่าเริ่มต้นคือคิวแบบ "ดูหลักฐาน" (หนึ่งแถว = หนึ่งรายการในเอกสาร)
        # ตารางเดิม (ค้นหา · ตัวกรองรหัส · แบ่งหน้า · ตัดสินแบบกลุ่ม) = ``?view=table``
        # ลิงก์เดิมที่พกตัวกรองของตารางมาด้วยยังเปิดตารางเหมือนเดิม
        table_params = {"view", "q", "flag", "ftype", "cat", "page", "per_page"}
        if request.query_params.get("view") != "table" and not (
                table_params & set(request.query_params.keys())):
            ctx = _verify_ctx(rid)
            if ctx is None:
                return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
            st = "pending" if (only_review or "PENDING" in (status or [])) else \
                request.query_params.get("state", "")
            flt = request.query_params.get("f", "")
            st = st if st in ("pending", "done") else ""
            ctx["steps"] = _run_steps(rid, ctx["counts"], ctx["pf"],
                                      current=workflow_service.STEP_REVIEW,
                                      exported=_exported(rid))
            ctx.update({"state": st, "flt": flt,
                        "groups": vv.queue_groups(ctx["ov"], ctx["ann"], state=st, flt=flt),
                        "filters": vv.queue_filter_counts(ctx["ov"]),
                        "n_pending": len(vv.queue_items(ctx["ov"], ctx["ann"], state="pending")),
                        "n_all": len(ctx["ov"].items)})
            return page(request, "verify_queue.html", ctx)
        state = _run_state(rid)
        if state is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        view, ann, counts, bundle, pf = state
        filters = _t1b_filters(q, flag, ftype, only_review, cat, status)
        result = review_service.review_page(view, ann, page=page_no,
                                            per_page=per_page, **filters)
        qs = lambda pg: review_service.query_string(  # noqa: E731
            per_page=result.per_page, page=pg, **filters)
        return page(request, "t1b_queue.html", {
            "view": view, "s": view.summary, "queue": result, "ann": ann,
            "counts": counts, "filters": filters, "pf": pf,
            "cats": cat_service, "dec": dec_service, "rv": review_service,
            "qs_here": qs(result.page), "qs_prev": qs(result.page - 1),
            "qs_next": qs(result.page + 1),
            "nav_counts": _run_nav_counts(counts, pf),
            "steps": _run_steps(rid, counts, pf,
                                current=workflow_service.STEP_REVIEW,
                                exported=_exported(rid)),
        })

    @app.post("/t1b/runs/{rid}/bulk/confirm", response_class=HTMLResponse)
    async def t1b_bulk_confirm(request: Request, rid: str,
                               scope: str = Form("checked"),
                               bulk_status: str = Form(""),
                               fid: list[str] = Form(default=[]),
                               q: str = Form(""), flag: list[str] = Form(default=[]),
                               ftype: list[str] = Form(default=[]),
                               cat: list[str] = Form(default=[]),
                               status: list[str] = Form(default=[]),
                               only_review: str = Form(""),
                               csrf_token: str = Form("")):
        """หน้ายืนยัน — แสดงจำนวนที่แน่นอนและเงื่อนไขก่อนบันทึก (ยังไม่เขียนอะไร)"""
        verify_csrf(request, csrf_token)
        view = t1b_service.load_run(rid)
        if view is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        filters = _t1b_filters(q, flag, ftype, only_review, cat, status)
        ann = review_service.annotate(view, review_service.status_map(rid))
        select_all = scope == "all_filtered"
        if select_all:
            items = list(review_service.filter_findings(view, ann, **filters))
        else:
            items = [view.by_id(x) for x in fid if view.by_id(x)]
        error = ""
        try:
            review_service.validate_bulk(bulk_status, "x", len(items))
        except dec_service.DecisionError as e:
            error = str(e)
        return page(request, "t1b_bulk_confirm.html", {
            "view": view, "s": view.summary, "status": bulk_status,
            "status_label": dec_service.STATUS_LABELS.get(bulk_status, bulk_status),
            "note": "", "items": items, "ann": ann, "count": len(items),
            "select_all": select_all, "filters_desc": _filters_desc(filters),
            "filters": filters, "dec": dec_service, "error": error,
            "qs_here": review_service.query_string(**filters),
        }, status_code=400 if error else 200)

    @app.post("/t1b/runs/{rid}/bulk/apply", response_class=HTMLResponse)
    async def t1b_bulk_apply(request: Request, rid: str,
                             bulk_status: str = Form(""), note: str = Form(""),
                             fid: list[str] = Form(default=[]),
                             csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        view = t1b_service.load_run(rid)
        if view is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        form = await request.form()
        expected = {x: int(form.get(f"expected_{x}", 0) or 0) for x in fid}
        try:
            result = review_service.bulk_decide(
                view, fid, bulk_status, note=note, expected_seqs=expected)
        except dec_service.DecisionError as e:
            return fail(request, str(e), 400)
        audit.record("t1b_bulk_decision", "t1b_run", rid, {
            "status": bulk_status, "requested": result.requested,
            "succeeded": len(result.succeeded), "failed": len(result.failed)})
        return page(request, "t1b_bulk_result.html", {
            "view": view, "s": view.summary, "result": result,
            "dec": dec_service, "qs_here": "",
        })

    @app.post("/t1b/runs/{rid}/findings/{fid}/decide")
    async def t1b_decide(request: Request, rid: str, fid: str,
                         status: str = Form(""), note: str = Form(""),
                         corrected_value: str = Form(""),
                         expected_latest_seq: int = Form(0),
                         csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        view = t1b_service.load_run(rid)
        if view is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        f = view.by_id(fid)
        if f is None:
            return fail(request, "ไม่พบรายการที่ระบุในรอบการตรวจนี้", 404)
        qs = request.url.query
        try:
            dec_service.record(view, f, status, note=note,
                               corrected_value=corrected_value,
                               expected_latest_seq=expected_latest_seq)
        except dec_service.DecisionError as e:
            # แสดงหน้าเดิมพร้อมข้อความ — ไม่เด้งไปหน้า error ให้ผู้ใช้เสียบริบท
            return await _render_detail(request, rid, fid, qs, error=str(e),
                                        status_code=409 if isinstance(
                                            e, dec_service.StaleDecisionError) else 400)
        return RedirectResponse(f"/t1b/runs/{rid}/findings/{fid}?{qs}",
                                status_code=303)

    async def _render_detail(request: Request, rid: str, fid: str, qs: str,
                             error: str = "", status_code: int = 200):
        view = t1b_service.load_run(rid)
        if view is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        # 🔴 ไม่ใช้ urllib (ด่านห้ามไลบรารีเครือข่ายในแพ็กเกจ) — Starlette แยก query ให้แล้ว
        params = request.query_params
        g = lambda k: params.get(k, "")  # noqa: E731
        filters = _t1b_filters(g("q"), params.getlist("flag"), params.getlist("ftype"),
                               g("only_review"), params.getlist("cat"), params.getlist("status"))
        detail = t1b_service.finding_detail(view, fid, **_t1a_filters(filters))
        if detail is None:
            return fail(request, "ไม่พบรายการที่ระบุในรอบการตรวจนี้", 404)
        ann = review_service.annotate(view, review_service.status_map(rid))
        history = t1b_decisions.list_for_finding(rid, fid)
        run_row = t1b_repo.get_run(rid) or {}
        # 🔴 page/per_page มาจาก query ของผู้ใช้ — ค่าที่ไม่ใช่จำนวนเต็มต้องเป็น 400 ไม่ใช่ 500
        # (Security Gate #23 · F-09 · จุดสะท้อนที่ ZAP 10031 ชี้)
        try:
            page_i = int(g("page") or 1)
            per_page_i = int(g("per_page") or t1b_service.DEFAULT_PER_PAGE)
        except ValueError:
            return fail(request, "ค่าหน้า/จำนวนต่อหน้าต้องเป็นตัวเลข", 400, detail="bad_pagination")
        return page(request, "t1b_finding_detail.html", {
            "book_refs": book_links.for_project(run_row.get("project_id") or ""),
            "view": view, "s": view.summary, "d": detail, "f": detail.finding,
            "filters": filters, "svc": t1b_service, "a": ann[fid],
            "history": history, "dec": dec_service, "cats": cat_service,
            "decision_error": error,
            "qs_here": review_service.query_string(
                per_page=per_page_i, page=page_i, **filters),
        }, status_code)

    @app.get("/t1b/runs/{rid}/findings/{fid}", response_class=HTMLResponse)
    async def t1b_finding_detail(request: Request, rid: str, fid: str):
        return await _render_detail(request, rid, fid, request.url.query)

    # --------------------------------------------- กันงบบุคลากร + สี่ไตรมาส
    # directive ข้อ 2 ของ Bo (13 ก.ย. 2569) · กิ๊ฟตัดสิน 27 ก.ย. ว่า
    # **งบบุคลากรระบุจากหมวดงบรายจ่าย** ⇒ ใช้ canonical category ของเครื่องยนต์
    #
    # 🔴 หน้านี้เป็น **เครื่องคิดตามกฎ** ไม่ใช่การอ้างผลการวัดใด ๆ
    # ระบบไม่เดาว่าแถวใดคือยอดรายปีของหมวดนี้ — เสนอรายการให้ผู้ตรวจเลือกเท่านั้น
    @app.get("/t1b/runs/{rid}/personnel", response_class=HTMLResponse)
    async def t1b_personnel(request: Request, rid: str,
                            amount: str = "", unit: str = "", sheet: str = "",
                            commit: list[str] = Query(default=None)):
        """เครื่องคิดตามกฎกันงบบุคลากร

        ``sheet``   ชีตของยอดงบบุคลากรที่ผู้ตรวจเลือก — ใช้จำกัดขอบเขต
                    การหายอดผูกพัน **ให้อยู่ในชีตเดียวกัน** (คำตัดสินกิ๊ฟ 27 ก.ย.)
        ``commit``  รหัสแถวผูกพันที่ผู้ตรวจเลือกให้เป็นลำดับ 1
        """
        state = _run_state(rid)
        if state is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        view, ann, counts, pf = state[0], state[1], state[2], state[4]
        amount = (amount or "").strip()[:40]
        unit = (unit or "").strip()[:40]
        sheet = (sheet or "").strip()[:120]
        chosen_ids = tuple(x for x in (commit or []) if x)[:40]

        rows = quarterly_service.commitment_rows(view, sheet=sheet)
        chosen = [r for r in rows if r.finding_id in chosen_ids and r.eligible]

        plan = None
        if amount:
            plan = quarterly_service.build_plan(
                personnel_annual=amount,
                personnel_unit=unit or quarterly_service.UNIT_BAHT,
                existing_priority_1=quarterly_service.priority_1_from_commitments(chosen))
        return page(request, "t1b_personnel.html", {
            "view": view, "s": view.summary, "q": quarterly_service,
            "candidates": quarterly_service.personnel_candidates(view),
            "amount": amount, "unit": unit, "sheet": sheet, "plan": plan,
            "split": plan.personnel.split if plan else None,
            "units": tuple(quarterly_service.BAHT_PER_UNIT),
            "commitments": rows, "chosen_ids": chosen_ids,
            "nav_counts": _run_nav_counts(counts, pf),
            "steps": _run_steps(rid, counts, pf,
                                current=workflow_service.STEP_REVIEW,
                                exported=_exported(rid)),
        })

    # ------------------------------------------------------------- preflight
    # 🔴 คำสั่งกิ๊ฟ 23 ก.ย. 2569 — ด่านนี้เป็น **ด่านจริง** ไม่ใช่คำเตือน
    # ปุ่มที่กดไม่ได้บนหน้าจอไม่ใช่ด่าน · route ที่เขียนไฟล์ต้องประเมินซ้ำเอง
    def _exported(rid: str) -> bool:
        return any(e.get("action") == "t1b_export_written"
                   for e in audit.entries(limit=200, object_id=rid))

    @app.get("/t1b/runs/{rid}/preflight", response_class=HTMLResponse)
    async def t1b_preflight_page(request: Request, rid: str, ack_done: str = "",
                                 decided: str = ""):
        state = _run_state(rid)
        if state is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        view, ann, counts, bundle, pf = state
        # IA #24: Preflight = "เหลือกี่เรื่องที่คนยังต้องตรวจ" → แต่ละเรื่องเปิดหน้าหลักฐาน A | B
        # เดียวกับคิว (ไม่ใช่ตรรกะชุดที่สอง) · เรื่อง = รายการที่ยังมีข้อสังเกตรอตัดสิน
        vctx = _verify_ctx(rid) or {}
        ov = vctx.get("ov") or vv.build_overview(view)
        return page(request, "t1b_preflight.html", {
            "view": view, "s": view.summary, "counts": counts, "pf": pf,
            "ann": ann, "vv": vv, "decided": decided == "1", "rc": vctx.get("rc"),
            "todo": vv.queue_items(ov, ann, state="pending"),
            "groups": vv.queue_groups(ov, ann, state="pending"),
            "rec": view.reconciliation, "ack_done": ack_done == "1",
            "nav_counts": _run_nav_counts(counts, pf),
            "steps": _run_steps(rid, counts, pf,
                                current=workflow_service.STEP_PREFLIGHT,
                                exported=_exported(rid)),
        })

    @app.post("/t1b/runs/{rid}/preflight/ack")
    async def t1b_preflight_ack(request: Request, rid: str,
                                reviewer: str = Form(""), note: str = Form(""),
                                scope: str = Form(""), csrf_token: str = Form("")):
        """รับทราบชุดรายการที่ระบบอ่านไม่ครบ — ผูกกับชุดนั้นด้วยแฮช

        🔴 ``scope`` ที่ฟอร์มส่งกลับมาต้องตรงกับชุดปัจจุบัน มิฉะนั้นแปลว่า
        รายการเปลี่ยนไประหว่างที่ผู้ใช้เปิดหน้าไว้ — ต้องให้อ่านใหม่
        ไม่ใช่รับทราบชุดที่ตัวเองไม่ได้เห็น
        """
        verify_csrf(request, csrf_token)
        state = _run_state(rid)
        if state is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        view, ann, counts, bundle, pf = state
        ids = preflight_service.unmapped_ids(view)
        if not ids:
            return fail(request, "รอบนี้ไม่มีรายการที่ระบบอ่านไม่ครบ "
                                 "จึงไม่มีอะไรต้องรับทราบ", 400)
        if scope != pf.unmapped_scope:
            return fail(request,
                        "รายการที่ระบบอ่านไม่ครบเปลี่ยนไปตั้งแต่ตอนที่เปิดหน้านี้ "
                        "โปรดเปิดหน้าตรวจก่อนส่งออกใหม่แล้วอ่านรายการชุดล่าสุด "
                        "ก่อนกดรับทราบ", 409)
        digest = t1b_preflight.acknowledge(rid, ids, who=reviewer, note=note)
        audit.record("t1b_unmapped_acknowledged", "t1b_run", rid, {
            "scope_hash": digest, "unmapped_count": len(ids),
            "preflight_version": preflight_service.PREFLIGHT_SERVICE_VERSION})
        return RedirectResponse(f"/t1b/runs/{rid}/preflight?ack_done=1",
                                status_code=303)

    # ---------------------------------------------------------------- export
    @app.get("/t1b/runs/{rid}/export", response_class=HTMLResponse)
    async def t1b_export_page(request: Request, rid: str):
        state = _run_state(rid)
        if state is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        view, ann, counts, bundle, pf = state
        return page(request, "t1b_export.html", {
            "view": view, "s": view.summary, "bundle": bundle, "pf": pf,
            "files": None, "error": "", "ex": export_service, "dec": dec_service,
            "nav_counts": _run_nav_counts(counts, pf),
            "steps": _run_steps(rid, counts, pf,
                                current=workflow_service.STEP_EXPORT,
                                exported=_exported(rid)),
        })

    @app.post("/t1b/runs/{rid}/export", response_class=HTMLResponse)
    async def t1b_export_write(request: Request, rid: str, csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        state = _run_state(rid)
        if state is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        view, ann, counts, bundle, pf = state

        # 🔴 ด่านจริงอยู่ตรงนี้ — ประเมินใหม่จากของจริง **ก่อน** แตะไฟล์ใด ๆ
        # ผู้ใช้ที่เปิดหน้าไว้ก่อนแล้วสถานะเปลี่ยนทีหลังจึงข้ามด่านไม่ได้
        if not pf.ok:
            audit.record("t1b_export_blocked", "t1b_run", rid, {
                "blocking": [g.code for g in pf.blocking],
                "preflight_version": preflight_service.PREFLIGHT_SERVICE_VERSION})
            return page(request, "t1b_preflight.html", {
                "view": view, "s": view.summary, "counts": counts, "pf": pf,
                "rec": view.reconciliation, "ack_done": False,
                "blocked_notice": preflight_service.BLOCKED_NOTICE,
                "nav_counts": _run_nav_counts(counts, pf),
                "steps": _run_steps(rid, counts, pf,
                                    current=workflow_service.STEP_EXPORT),
            }, status_code=409)

        files, error = None, ""
        try:
            files = export_service.write(bundle, config.EXPORT_DIR)
            audit.record("t1b_export_written", "t1b_run", rid, {
                "export_id": files.export_id, "rows": bundle.count,
                "decision_cutoff_seq": bundle.snapshot["decision_cutoff_seq"],
                "export_version": export_service.EXPORT_SERVICE_VERSION})
        except Exception as e:                        # noqa: BLE001
            log.warning("export failed rid=%s err=%s", rid, type(e).__name__)
            error = "สร้างไฟล์ส่งออกไม่สำเร็จ — ไม่มีไฟล์ใดถูกเขียน"
        return page(request, "t1b_export.html", {
            "view": view, "s": view.summary, "bundle": bundle, "files": files,
            "pf": pf, "error": error, "ex": export_service, "dec": dec_service,
            "nav_counts": _run_nav_counts(counts, pf),
            "steps": _run_steps(rid, counts, pf,
                                current=workflow_service.STEP_EXPORT,
                                exported=files is not None),
        })

    @app.get("/t1b/exports/{name}")
    async def t1b_export_download(request: Request, name: str):
        if "/" in name or "\\" in name or ".." in name or not name.startswith("exp_"):
            return fail(request, "ชื่อไฟล์ส่งออกไม่ถูกต้อง", 400)
        path = (config.EXPORT_DIR / name).resolve()
        if config.EXPORT_DIR.resolve() not in path.parents or not path.is_file():
            return fail(request, "ไม่พบไฟล์ส่งออก", 404)
        return FileResponse(path, filename=name)

    @app.get("/t1b/runs/{rid}/audit", response_class=HTMLResponse)
    async def t1b_audit_page(request: Request, rid: str):
        view = t1b_service.load_run(rid)
        if view is None:
            return fail(request, "ไม่พบรอบการตรวจ T1B ที่ระบุ", 404)
        ann = review_service.annotate(view, review_service.status_map(rid))
        return page(request, "t1b_audit.html", {
            "view": view, "s": view.summary,
            "decisions_list": t1b_decisions.list_for_run(rid),
            "links": t1b_decisions.verify_audit_links(rid),
            "chain": audit.verify_chain(),
            "counts": review_service.counts(view, ann), "dec": dec_service})

    # --------------------------------------------- evidence (PDF old/new) + indicators
    # คำสั่งกิ๊ฟ 9 ก.ย. 2569 §3 — route ภายในแอปแทน path/file:// · เอกสารอ้างด้วย
    # document_id (content hash) ผ่านทะเบียน · ไม่มี path ในหน้า/ล็อก/URL
    EV_CTX = {
        "notice": evidence_service.MANDATORY_NOTICE,
        "loc_review_label": evidence_service.LOCATION_REVIEW_REQUIRED,
        "src_label": evidence_service.SOURCE_UNAVAILABLE,
        "run_missing_label": evidence_service.RUN_CONTEXT_MISSING,
        "run_mismatch_label": evidence_service.RUN_CONTEXT_MISMATCH,
        "stage_labels": evidence_service.STAGE_LABELS_TH,
        "stage_keybuild": evidence_service.STAGE_KEY_BUILD,
        "stage_adjudication": evidence_service.STAGE_ADJUDICATION,
    }

    def _locked(request: Request, run_id: str, reason: str = ""):
        """หน้าล็อกของขอบเขตการประเมิน — 🔴 ไม่ประกอบผลเครื่องใด ๆ (ไม่เรียก ``run_view``)

        Bo (`5606392284` P4-1) — ทุก route ที่เปิดข้อสังเกต/คู่/สถานะ/จำนวน/สรุปของเครื่อง
        ต้องมาที่นี่จนกว่าผนึกครบสามชั้นและตรวจแล้วว่ายังตรง
        """
        return page(request, "indicator_locked.html", {
            **EV_CTX, "run_id": run_id,
            "reason": reason or evidence_service.ADJUDICATION_LOCKED,
            # 🔴 P5-1 — view ที่ทำความสะอาดแล้ว: ชั้นของเครื่องบอกได้แค่ผนึกแล้ว/ยังไม่ผนึก
            "verification": (evidence_service.blind_verification(run_id)
                             if run_id and evidence_service.run_row(run_id) else None)}, 409)

    def _doc_id_ok(document_id: str) -> bool:
        return bool(document_id) and document_id.startswith("doc_") and \
            document_id[4:].isalnum() and len(document_id) <= 40

    @app.get("/evidence/compare", response_class=HTMLResponse)
    async def evidence_compare(request: Request, run: str = Query(""),
                               map: str = Query("")):
        # 🔴 P4-1 — ตรวจผนึกก่อน **ประกอบคู่** · รอบที่ยังล็อกได้ 409 ไม่ว่าคู่นั้นจะมีอยู่หรือไม่
        if not evidence_service.detector_output_allowed(run):
            return _locked(request, run)
        p = evidence_service.pair_view(run, map)
        if p is None:
            return fail(request, "ไม่พบคู่ตัวชี้วัดที่ระบุ", 404)
        return page(request, "evidence_compare.html", {
            **EV_CTX, "p": p, "can_render": evidence_service.can_render(),
            "decisions": evidence_service.decision_choices(),
            "statuses": evidence_service.statuses(),
            "status_labels": evidence_service.status_labels(),
            "reviewer_default": "", "error": ""})

    @app.get("/evidence/{document_id}", response_class=HTMLResponse)
    async def evidence_page(request: Request, document_id: str,
                            page_no: int = Query(1, alias="page"),
                            obs: str = Query(""), run: str = Query("")):
        # 🔴 B5 — ชี้ข้อสังเกตต้องมาพร้อม run context และต้องตรวจว่าอยู่ในรอบ+เอกสารนั้นจริง
        if not _doc_id_ok(document_id):
            return fail(request, "รหัสเอกสารไม่ถูกต้อง", 400)
        # 🔴 P4-1 — ``obs=`` คือข้อสังเกตที่ **เครื่องสกัด** (ข้อความ · กรอบ · indicator id)
        # จึงเปิดได้เฉพาะรอบที่ผนึกครบและตรวจผ่าน · ไม่ระบุรอบ ⇒ ตรวจไม่ได้ ⇒ ล็อก
        # หน้าเอกสาร/หน้ากระดาษ **ไม่มี** ``obs`` ยังเปิดได้ (ขั้นเฉลยต้องใช้)
        allowed = bool(run) and evidence_service.detector_output_allowed(run)
        if obs and not allowed:
            return _locked(request, run, evidence_service.RUN_CONTEXT_MISSING
                           if not run else evidence_service.ADJUDICATION_LOCKED)
        v = evidence_service.page_view(document_id, page_no, obs, run)
        if v is None:
            return fail(request, "ไม่พบเอกสารในทะเบียน", 404)
        return page(request, "evidence_page.html", {**EV_CTX, "v": v,
                                                    "report_allowed": allowed})

    @app.get("/evidence/{document_id}/file")
    async def evidence_file(request: Request, document_id: str):
        if not _doc_id_ok(document_id):
            return fail(request, "รหัสเอกสารไม่ถูกต้อง", 400)
        try:
            path = evidence_service.open_document_path_for_streaming(document_id)
        except evidence_service.SourceUnavailable as e:
            log.warning("evidence_file unavailable document_id=%s reason=%s",
                        document_id, e.reason)
            return fail(request, "ไฟล์ต้นทางของเอกสารนี้ไม่พร้อมใช้ (SOURCE_UNAVAILABLE)", 404)
        # 🔴 ชื่อไฟล์ที่ผู้ใช้เห็น = document_id เท่านั้น ไม่ใช่ชื่อ/ที่อยู่ไฟล์จริง
        return FileResponse(path, media_type="application/pdf",
                            filename=f"{document_id}.pdf",
                            content_disposition_type="inline")

    @app.get("/evidence/{document_id}/page/{page_no}.png")
    async def evidence_page_png(request: Request, document_id: str, page_no: int,
                                hl: str = Query("")):
        if not _doc_id_ok(document_id):
            return fail(request, "รหัสเอกสารไม่ถูกต้อง", 400)
        try:
            highlight = evidence_service.parse_highlight(hl)
        except ValueError:
            return fail(request, "พารามิเตอร์กรอบเน้นไม่ถูกต้อง", 400)
        try:
            png = evidence_service.render_page_png(document_id, page_no, highlight)
        except evidence_service.SourceUnavailable as e:
            log.warning("evidence_png unavailable document_id=%s reason=%s",
                        document_id, e.reason)
            return fail(request, "ไฟล์ต้นทางของเอกสารนี้ไม่พร้อมใช้ (SOURCE_UNAVAILABLE)", 404)
        except (RuntimeError, ValueError) as e:
            return fail(request, "วาดภาพหน้าไม่ได้", 404, detail=type(e).__name__)
        from fastapi.responses import Response
        return Response(content=png, media_type="image/png")

    @app.get("/indicators/runs", response_class=HTMLResponse)
    async def indicator_runs(request: Request):
        # 🔴 P4-1 — จำนวนข้อสังเกต/คู่ของเครื่องเปิดเฉพาะรอบที่ตรวจผนึกผ่าน
        return page(request, "indicator_runs.html", {"runs": evidence_service.runs_overview()})

    @app.get("/indicators/runs/{run_id}", response_class=HTMLResponse)
    async def indicator_report(request: Request, run_id: str):
        # 🔴 P4-1 — รายงานประกอบด้วยคู่/สถานะ/สรุปของเครื่อง ⇒ ตรวจผนึกก่อนประกอบ
        if evidence_service.run_row(run_id) is None:
            return fail(request, "ไม่พบรอบทะเบียนตัวชี้วัดที่ระบุ", 404)
        if not evidence_service.detector_output_allowed(run_id):
            return _locked(request, run_id)
        rv = evidence_service.run_view(run_id)
        return page(request, "indicator_report.html", {
            **EV_CTX, "rv": rv, "synthetic": evidence_service.is_synthetic(rv)})

    # ── B4 (Pass 3) · ขั้นจัดทำ/ยืนยันเฉลย ───────────────────────────────────
    # 🔴 ทุก handler ในบล็อกนี้ใช้ ``key_universe_view`` เท่านั้น — ห้ามเรียก ``run_view``
    # เพราะ ``run_view`` ประกอบคู่ที่ detector เสนอ (Bo `5600162467`)
    def _keybuild_page(request: Request, run_id: str, error: str = "", code: int = 200):
        kv = evidence_service.key_universe_view(run_id)
        if kv is None:
            return fail(request, "ไม่พบรอบทะเบียนตัวชี้วัดที่ระบุ", 404)
        return page(request, "indicator_keybuild.html", {
            **EV_CTX, "kv": kv,
            "key_title": evidence_service.KEY_BUILD_TITLE,
            "key_notice": evidence_service.KEY_BUILD_NOTICE,
            "error": error}, code)

    @app.get("/indicators/runs/{run_id}/keybuild", response_class=HTMLResponse)
    async def indicator_keybuild(request: Request, run_id: str):
        """B4 · ขั้นจัดทำ/ยืนยันเฉลย — **ไม่มี** คู่ สถานะ เหตุผล หรือคะแนนของเครื่อง"""
        return _keybuild_page(request, run_id)

    @app.post("/indicators/runs/{run_id}/keybuild/source")
    async def indicator_source_item(request: Request, run_id: str,
                                    side: str = Form(""), page: str = Form(""),
                                    observed_text: str = Form(""),
                                    occurrence: str = Form("1"), hint: str = Form(""),
                                    entered_by: str = Form(""),
                                    csrf_token: str = Form("")):
        """P3-2 · กรอกหนึ่งรายการเข้าทะเบียนข้อสังเกต **อิสระ**

        รายการนี้มาจากการที่คนเปิดอ่านหน้าเอกสารเอง จึงบันทึกตัวชี้วัดที่เครื่องสกัด
        ไม่เจอได้ด้วย (Bo `5605652708` P3-2)
        """
        verify_csrf(request, csrf_token)
        try:
            evidence_service.record_source_item(
                run_id, side=side.strip(), page=page.strip(),
                observed_text=observed_text, occurrence=(occurrence.strip() or "1"),
                hint=hint.strip(), entered_by=entered_by.strip())
        except evidence_service.KeyStageError as e:
            return _keybuild_page(request, run_id, str(e), 400)
        return RedirectResponse(f"/indicators/runs/{run_id}/keybuild", status_code=303)

    @app.post("/indicators/runs/{run_id}/keybuild/source/retract")
    async def indicator_source_retract(request: Request, run_id: str,
                                       identity_key: str = Form(""),
                                       retracted_by: str = Form(""),
                                       reason: str = Form(""),
                                       csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            evidence_service.retract_source_item(run_id, identity_key.strip(),
                                                 retracted_by=retracted_by.strip(),
                                                 reason=reason.strip())
        except evidence_service.KeyStageError as e:
            return _keybuild_page(request, run_id, str(e), 400)
        return RedirectResponse(f"/indicators/runs/{run_id}/keybuild", status_code=303)

    @app.post("/indicators/runs/{run_id}/keybuild/build")
    async def indicator_key_universe_build(request: Request, run_id: str,
                                           built_by: str = Form(""),
                                           csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            evidence_service.build_key_universe(run_id, built_by=built_by.strip())
        except evidence_service.KeyStageError as e:
            return _keybuild_page(request, run_id, str(e), 400)
        return RedirectResponse(f"/indicators/runs/{run_id}/keybuild", status_code=303)

    @app.post("/indicators/runs/{run_id}/keybuild/freeze")
    async def indicator_key_universe_freeze(request: Request, run_id: str,
                                            frozen_by: str = Form(""),
                                            csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            evidence_service.freeze_key_universe(run_id, frozen_by=frozen_by.strip())
        except evidence_service.KeyStageError as e:
            return _keybuild_page(request, run_id, str(e), 400)
        return RedirectResponse(f"/indicators/runs/{run_id}/keybuild", status_code=303)

    @app.post("/indicators/runs/{run_id}/keybuild/answer")
    async def indicator_key_answer(request: Request, run_id: str,
                                   item_id: str = Form(""), key_status: str = Form(""),
                                   counterpart_item_id: str = Form(""),
                                   reason: str = Form(""), entered_by: str = Form(""),
                                   csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            evidence_service.record_key_answer(
                run_id, item_id.strip(), key_status=key_status.strip(),
                counterpart_item_id=counterpart_item_id.strip(), reason=reason.strip(),
                entered_by=entered_by.strip())
        except evidence_service.KeyStageError as e:
            return _keybuild_page(request, run_id, str(e), 400)
        return RedirectResponse(f"/indicators/runs/{run_id}/keybuild", status_code=303)

    @app.post("/indicators/runs/{run_id}/keybuild/seal")
    async def indicator_key_seal(request: Request, run_id: str,
                                 sealed_by: str = Form(""), note: str = Form(""),
                                 csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        try:
            evidence_service.seal_key(run_id, sealed_by=sealed_by.strip(),
                                      note=note.strip())
        except evidence_service.KeyStageError as e:
            return _keybuild_page(request, run_id, str(e), 400)
        return RedirectResponse(f"/indicators/runs/{run_id}/keybuild", status_code=303)

    @app.post("/indicators/runs/{run_id}/keybuild/detector-seal")
    async def indicator_detector_seal(request: Request, run_id: str,
                                      sealed_by: str = Form(""), note: str = Form(""),
                                      csrf_token: str = Form("")):
        """ผนึก **ผลลัพธ์ของ detector** — artifact คนละชิ้นกับเฉลย · ต้องผนึกทั้งคู่จึงเปิด
        ขั้นตัดสินหลังรันได้ (Bo `5600162467` ข้อ 4)"""
        verify_csrf(request, csrf_token)
        try:
            evidence_service.seal_detector_snapshot(run_id, sealed_by=sealed_by.strip(),
                                                    note=note.strip())
        except evidence_service.KeyStageError as e:
            return _keybuild_page(request, run_id, str(e), 400)
        return RedirectResponse(f"/indicators/runs/{run_id}/keybuild", status_code=303)

    @app.get("/indicators/runs/{run_id}/verify", response_class=HTMLResponse)
    async def indicator_verify(request: Request, run_id: str, status: str = Query("")):
        """B4 · ขั้นตัดสินหลังรัน — เปิดได้ก็ต่อเมื่อผนึกครบสามชั้นและตรวจผ่าน"""
        if evidence_service.run_row(run_id) is None:
            return fail(request, "ไม่พบรอบทะเบียนตัวชี้วัดที่ระบุ", 404)
        if not evidence_service.detector_output_allowed(run_id):
            return _locked(request, run_id)
        rv = evidence_service.run_view(run_id)
        pairs = [p for p in rv.pairs if not status or p.proposed_status == status]
        return page(request, "indicator_verify.html", {
            **EV_CTX, "rv": rv, "pairs": pairs, "status_filter": status,
            "package_notice": evidence_service.PACKAGE_NOTICE,
            "package": None, "package_error": ""})

    @app.post("/indicators/runs/{run_id}/package", response_class=HTMLResponse)
    async def indicator_package(request: Request, run_id: str, csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        if evidence_service.run_row(run_id) is None:
            return fail(request, "ไม่พบรอบทะเบียนตัวชี้วัดที่ระบุ", 404)
        if not evidence_service.detector_output_allowed(run_id):
            return _locked(request, run_id)
        rv = evidence_service.run_view(run_id)
        pkg, error = None, ""
        try:
            pkg = evidence_service.write_package(rv, config.EXPORT_DIR)
            audit.record("indicator_package_written", "ind_run", run_id, {
                "package_id": pkg.package_id, "rows": pkg.rows,
                "scores_included": False})
        except Exception as e:                        # noqa: BLE001
            log.warning("indicator package failed run_id=%s err=%s", run_id, type(e).__name__)
            error = "สร้างชุดตรวจไม่สำเร็จ — ไม่มีไฟล์ใดถูกเขียน"
        return page(request, "indicator_verify.html", {
            **EV_CTX, "rv": rv, "pairs": rv.pairs, "status_filter": "",
            "package_notice": evidence_service.PACKAGE_NOTICE,
            "package": pkg, "package_error": error})

    @app.get("/indicators/exports/{name}")
    async def indicator_export_download_legacy(request: Request, name: str):
        """🔴 P4-2 — route เดิมไม่มีบริบทของรอบ จึงตรวจผนึกไม่ได้ ⇒ **ปฏิเสธเสมอ**

        ไฟล์เดิมใน ``EXPORT_DIR`` ไม่ถูกลบ · ไฟล์ที่ผูกกับรอบแล้วดาวน์โหลดผ่าน
        ``/indicators/runs/{run_id}/exports/{name}`` ซึ่งตรวจผนึกใหม่ทุกครั้ง
        """
        return fail(request, "ลิงก์ดาวน์โหลดแบบเดิมเลิกใช้แล้ว — ไฟล์ส่งออกต้องดาวน์โหลดผ่าน"
                             "ลิงก์ที่ระบุรอบประเมิน เพื่อให้ระบบตรวจผนึกก่อนส่งไฟล์", 410)

    @app.get("/indicators/runs/{run_id}/exports/{name}")
    async def indicator_export_download(request: Request, run_id: str, name: str):
        """P4-2 · ดาวน์โหลดไฟล์ส่งออก — manifest · รอบ · ผนึกตรวจผ่าน ณ ตอนนี้ · เนื้อไฟล์"""
        if not evidence_service.export_name_ok(name):
            return fail(request, "ชื่อไฟล์ส่งออกไม่ถูกต้อง", 400)
        check = evidence_service.check_export(run_id, name, config.EXPORT_DIR)
        if not check.ok:
            audit.record("indicator_export_refused", "ind_export", name,
                         {"run_id": run_id, "reasons": list(check.reasons)})
            return fail(request, "ดาวน์โหลดไม่ได้ — " + " · ".join(check.labels), 409)
        return FileResponse(check.path, filename=name)

    @app.post("/indicators/runs/{run_id}/mappings/{mapping_id}/decide")
    async def indicator_decide(request: Request, run_id: str, mapping_id: str,
                               decision: str = Form(""), final_status: str = Form(""),
                               reason: str = Form(""), reviewer: str = Form(""),
                               csrf_token: str = Form("")):
        verify_csrf(request, csrf_token)
        # 🔴 P4-1 — เดิมประกอบคู่ก่อนแล้วค่อยให้ชั้นบริการปฏิเสธ ⇒ หน้า error แสดงคู่ของเครื่องได้
        if not evidence_service.detector_output_allowed(run_id):
            return _locked(request, run_id)
        p = evidence_service.pair_view(run_id, mapping_id)
        if p is None:
            return fail(request, "ไม่พบคู่ตัวชี้วัดที่ระบุ", 404)
        try:
            evidence_service.decide(run_id, mapping_id, decision=decision,
                                    final_status=final_status.strip(),
                                    reason=reason.strip(), reviewer=reviewer.strip())
        except evidence_service.DecisionError as e:
            return page(request, "evidence_compare.html", {
                **EV_CTX, "p": p, "can_render": evidence_service.can_render(),
                "decisions": evidence_service.decision_choices(),
                "statuses": evidence_service.statuses(),
                "status_labels": evidence_service.status_labels(),
                "reviewer_default": reviewer, "error": str(e)}, 400)
        return RedirectResponse(evidence_service.compare_url(run_id, mapping_id),
                                status_code=303)

    # ------------------------------------------------------------------ misc
    @app.get("/rules", response_class=HTMLResponse)
    async def rules_page(request: Request):
        return page(request, "rules.html", {
            "rules": catalog.RULES, "counts": catalog.counts_by_status(),
            "mode_label": catalog.MODE_LABEL,
        })

    @app.get("/audit", response_class=HTMLResponse)
    async def audit_page(request: Request):
        # 🔴 P5-1 (Pass 6) — รายการ audit ของรอบที่ยังไม่ตรวจผ่านมีจำนวน/สถานะ/แฮชของเครื่อง
        # ปิดบังเฉพาะตอนแสดง · audit chain ที่บันทึกไว้ไม่ถูกแตะ
        return page(request, "audit.html", {
            "entries": evidence_service.redact_audit_entries(audit.entries(limit=300)),
            "chain": audit.verify_chain(),
            "security_events": audit.security_events(limit=100),
        })

    @app.get("/files/{file_id}/structure", response_class=HTMLResponse)
    async def file_structure(request: Request, file_id: str):
        f = repo.get_file(file_id)
        if not f:
            return fail(request, "ไม่พบไฟล์ที่ระบุ", 404)
        if f["kind"] != "xlsx":
            return fail(request, "ระยะนี้ยังอ่านโครงสร้างได้เฉพาะไฟล์ Excel", 400)
        try:
            structure = excel_reader.read_structure(
                filestore.path_for(f["stored_name"]), STRUCTURE_SCAN_ROWS)
        except excel_reader.ExcelReadError as e:
            return fail(request, str(e), 400)
        return page(request, "file_structure.html", {
            "file": f, "structure": structure, "scan_rows": STRUCTURE_SCAN_ROWS,
        })

    # ── เทียบเล่ม PDF ↔ PDF (สายแยก · ชั้นบริการ services/pdfpair) ──
    from .web import pdfpair_routes
    pdfpair_routes.register(app, page, fail)
    # ── ทดลองตรวจเล่มสำหรับผู้ปฏิบัติงาน (#43 · ชั้นบริการ services/trial) ──
    from .web import trial_routes
    trial_routes.register(app, page, fail)
    # ── หน้าบ้าน Svelte (/r/) + JSON API ของทดลองตรวจเล่ม ──
    from .web import api_trial
    api_trial.register(app)
    # คลังเล่ม (อ่านอย่างเดียว) สำหรับหน้าแรกของ /r — Giho 29 ต.ค.
    from .web import api_library
    api_library.register(app)

    return app


app = create_app()
