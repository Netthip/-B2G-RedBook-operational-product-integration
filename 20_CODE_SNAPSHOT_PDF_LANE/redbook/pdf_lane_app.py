# -*- coding: utf-8 -*-
"""เซิร์ฟเวอร์ **สาย PDF เท่านั้น** — ทางเลือก ก ของ #42 (Bo REVIEW 6409941573 · กิ๊ฟเลือก 26 ต.ค. 2569)

PDFium (pypdfium2) ใช้จากหลายเธรดพร้อมกันไม่ได้ · สาย PDF เรียกผ่านกุญแจ ``reader._PDFIUM`` แต่สาย Excel วาดภาพหลักฐาน
ผ่าน ``evidence/pdftext.py`` ซึ่งอยู่ใน tag ที่ตรึงไว้ (แก้ไม่ได้) จึงไม่ถือกุญแจนี้ — รอบนี้แยก process แทนการแก้โค้ดที่ตรึง:

1. **เปิดเฉพาะเส้นทางสาย PDF** (:data:`LANE_PREFIXES` · :data:`LANE_PROJECT_PATHS`) — เส้นทางอื่นทั้งหมด (สาย Excel/T1B ·
   หลักฐาน · ตัวชี้วัด · โต๊ะทำงาน) ได้ 404 **ก่อนถึงแอป** · ``/`` พาไป ``/r/``
2. **ด่าน PDFium** (:func:`install_pdfium_guard`): การวาดภาพของ backend ที่ไม่ได้ถือกุญแจร่วม = ปฏิเสธ + นับ — ใน process นี้
   ทุกการวาดต้องมาจากสาย PDF ที่ถือกุญแจ · ตัวนับเป็น 0 = หลักฐานว่าไม่มีเส้นทาง Excel วาดภาพใน process นี้
3. ``GET /api/lane`` รายงานตัวนับ (คำขอที่ปิด · การวาดที่ถูกปฏิเสธ · การวาดที่ผ่านกุญแจ · หัว Host ที่ถูกปฏิเสธ)
4. **หัว Host ต้องอยู่ในรายการอนุญาต** (กัน DNS rebinding) — การแก้ของ Security Gate #23 (F-01 · ``SecurityMiddleware``)
   รวมเข้าสายนี้แล้ว (กิ๊ฟเลือกทางเลือก ก 27 ต.ค.) · ด่านนี้คงไว้เป็นชั้นนอกสุดซ้อนอีกชั้น — กติกาและ
   ``REDBOOK_ALLOWED_HOSTS`` เหมือน ``config.ALLOWED_HOSTS`` (ไม่สนพอร์ต) · คำขอที่ Host ผิดไม่ถึงแอปเลย

รัน (process แยกจากเซิร์ฟเวอร์ที่ใช้สาย Excel — ไม่ import ไฟล์ที่ตรึงใหม่ · ไม่แก้ tag/ผลเดิม)::

    python -m uvicorn --factory redbook.pdf_lane_app:create_lane_app --host 127.0.0.1 --port <พอร์ต> --no-server-header

🔴 ห้ามเปิดสาย Excel ใน process เดียวกันกับเซิร์ฟเวอร์นี้ · เมนูของหน้าเดิมที่ชี้ไปสาย Excel จะได้ 404 (ตั้งใจ)
"""
from __future__ import annotations

import os
import re
import threading

from starlette.responses import PlainTextResponse, RedirectResponse

LANE = "pdf_only"
#: ขึ้นต้นเส้นทางที่เปิด (ตรงตัว หรือ ตามด้วย "/")
LANE_PREFIXES = ("/pdfpair", "/api/pdfpair", "/trial", "/api/trial", "/r", "/static", "/healthz", "/api/csrf",
                 "/api/lane", "/api/books")
#: เส้นทางของงานตรวจที่สาย PDF ใช้ (แนบ PDF · เริ่มรอบเทียบ)
LANE_PROJECT_PATHS = re.compile(r"^/projects/[^/]+/(pdfpair|source-pdf)$")
CLOSED_MESSAGE = "เซิร์ฟเวอร์นี้เปิดเฉพาะสายเทียบเล่ม PDF (#42 ทางเลือก ก) — สาย Excel ใช้เซิร์ฟเวอร์อีกตัว"

#: หัว Host ที่ยอมรับ — ค่าเดียวกับ ``config.ALLOWED_HOSTS`` ของ #23 (loopback + ``REDBOOK_HOST`` + ``REDBOOK_ALLOWED_HOSTS``)
ALLOWED_HOSTS = frozenset(
    h.strip().lower() for h in
    (os.environ.get("REDBOOK_ALLOWED_HOSTS", "") + ",127.0.0.1,localhost,[::1],"
     + os.environ.get("REDBOOK_HOST", "127.0.0.1")).split(",") if h.strip())
HOST_REJECTED_MESSAGE = "ไม่สามารถดำเนินการได้ — ชื่อโฮสต์ของคำขอไม่อยู่ในรายการที่อนุญาต"

_lock = threading.Lock()
STATS = {"blocked_requests": 0, "refused_unlocked_renders": 0, "locked_renders": 0, "host_rejected": 0}


def _count(key: str) -> None:
    with _lock:
        STATS[key] += 1


def host_allowed(host_header: str) -> bool:
    """เทียบหัว Host (ตัดพอร์ต) กับ :data:`ALLOWED_HOSTS` — เหมือน ``security.host_allowed`` ของ #23"""
    host = (host_header or "").strip().lower()
    if not host:
        return False
    if host.startswith("["):
        host = host.split("]", 1)[0] + "]"
    elif host.count(":") == 1:
        host = host.rsplit(":", 1)[0]
    return host in ALLOWED_HOSTS


def allowed(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in LANE_PREFIXES) or bool(LANE_PROJECT_PATHS.match(path))


class LaneOnly:
    """ASGI ชั้นนอกสุด — คำขอนอกสาย PDF ไม่ถึงแอปเลย (ไม่ผ่าน handler · ไม่แตะฐานข้อมูล · ไม่แตะ PDF)"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            host = next((v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"host"), "")
            if not host_allowed(host):
                _count("host_rejected")
                return await PlainTextResponse(HOST_REJECTED_MESSAGE, status_code=400)(scope, receive, send)
            path = scope.get("path", "")
            if path == "/":
                return await RedirectResponse("/r/", status_code=303)(scope, receive, send)
            if not allowed(path):
                _count("blocked_requests")
                return await PlainTextResponse(CLOSED_MESSAGE, status_code=404)(scope, receive, send)
        return await self.app(scope, receive, send)


def install_pdfium_guard(setattr_=setattr) -> None:
    """ให้ ``render_png`` ของ backend วาดได้เฉพาะเมื่อเธรดนี้ถือกุญแจ PDFium ร่วม (``reader._PDFIUM``) — สาย PDF ถือเสมอ ·
    เส้นทางที่ไม่ถือ (สาย Excel) ถูกปฏิเสธ + นับ · ``setattr_`` ให้เทสต์ส่ง ``monkeypatch.setattr`` (ถอดคืนเอง)"""
    from .evidence import pdftext
    from .pdfbook import reader
    backend = pdftext.product_backend()
    if backend is None:
        return
    cls = type(backend)
    orig = cls.render_png
    if getattr(orig, "_pdf_lane_guard", False):
        return

    def render_png(self, *a, **k):
        if not reader._PDFIUM._is_owned():
            _count("refused_unlocked_renders")
            raise RuntimeError("PDF lane process: PDFium render outside the shared lock refused")
        _count("locked_renders")
        return orig(self, *a, **k)
    render_png._pdf_lane_guard = True
    setattr_(cls, "render_png", render_png)


def create_lane_app(guard: bool = True):
    from .app import create_app
    app = create_app()

    @app.get("/api/lane")
    async def api_lane():
        with _lock:
            from . import eval_guard
            return {"lane": LANE, **STATS, "eval_guard": eval_guard.status(), "open_prefixes": list(LANE_PREFIXES),
                    "open_project_paths": LANE_PROJECT_PATHS.pattern}
    if guard:
        install_pdfium_guard()
    return LaneOnly(app)


__all__ = ["LANE", "ALLOWED_HOSTS", "host_allowed", "LANE_PREFIXES", "LANE_PROJECT_PATHS", "STATS", "allowed", "LaneOnly", "install_pdfium_guard",
           "create_lane_app"]
