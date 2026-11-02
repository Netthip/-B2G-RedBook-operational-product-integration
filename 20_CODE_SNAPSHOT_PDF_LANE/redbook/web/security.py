# -*- coding: utf-8 -*-
"""มาตรการความปลอดภัยระดับเว็บ - ส่วนกลาง

ครอบคลุมข้อกำหนดที่จะถูกทดสอบด้วย OWASP ZAP:
  - security headers (CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy,
    Permissions-Policy, Cache-Control)
  - CSRF แบบ double-submit cookie พร้อมตรวจ Origin/Referer ทุกคำขอที่เปลี่ยนสถานะ
  - ไม่เปิดเผย stack trace หรือ path ภายในให้ผู้ใช้เห็น (จัดการที่ app.py)

CSP ตั้งใจไม่อนุญาตทรัพยากรจากภายนอกเลย ระบบนี้ไม่โหลดอะไรจากอินเทอร์เน็ต
CSRF ตรวจภายใน handler ไม่ใช่ middleware เพราะการอ่าน body ใน middleware
จะทำให้ handler อ่านฟอร์มต่อไม่ได้
"""
import html
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse

from .. import config

CSRF_COOKIE = "redbook_csrf"
CSRF_FIELD = "csrf_token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

CSP = (
    "default-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'"
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    # 🔴 เคยเป็น ``no-referrer`` ซึ่ง **ทำให้ทุกแบบฟอร์มในระบบส่งไม่ได้บนเบราว์เซอร์จริง**
    # (พบจาก browser smoke test · 23 ก.ย. 2569) — เมื่อนโยบายเป็น ``no-referrer``
    # Chrome/Firefox จะส่ง ``Origin: null`` มากับการ submit ฟอร์มแม้เป็น same-origin
    # ด่าน :func:`verify_csrf` จึงอ่านว่า origin ไม่ตรงและปฏิเสธทุกคำขอ
    # ชุดทดสอบเดิมจับไม่ได้เพราะ ``TestClient`` ไม่ส่งหัว ``Origin`` มาเลย
    #
    # ``same-origin`` ให้หัว referrer/origin เฉพาะกับปลายทางที่เป็น origin เดียวกัน
    # เว็บภายนอกยังไม่ได้รับ referrer เลย — ระบบนี้ไม่ลิงก์ออกนอกเครื่องอยู่แล้ว
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}


class CSRFError(Exception):
    def __init__(self, event: str):
        super().__init__(event)
        self.event = event


def host_allowed(host_header: str) -> bool:
    """เทียบหัว Host (ตัดพอร์ตออก) กับรายการอนุญาตใน :data:`config.ALLOWED_HOSTS`"""
    host = (host_header or "").strip().lower()
    if not host:
        return False
    if host.startswith("["):                       # IPv6 literal เช่น [::1]:8600
        host = host.split("]", 1)[0] + "]"
    elif host.count(":") == 1:
        host = host.rsplit(":", 1)[0]
    return host in config.ALLOWED_HOSTS


_HOST_REJECTED_HTML = (
    '<!doctype html><html lang="th"><head><meta charset="utf-8">'
    "<title>ไม่สามารถดำเนินการได้</title></head><body>"
    "<h1>ไม่สามารถดำเนินการได้</h1><p>{msg}</p></body></html>")


def host_rejected_response() -> HTMLResponse:
    """400 แบบไม่พึ่ง template — ใช้ใน middleware ก่อนถึง router · ใส่ security headers เอง"""
    resp = HTMLResponse(_HOST_REJECTED_HTML.format(
        msg=html.escape("คำขอนี้ไม่ได้ส่งถึงที่อยู่ของระบบที่อนุญาต โปรดเปิดระบบผ่านที่อยู่ที่ตั้งค่าไว้")),
        status_code=400)
    for k, v in SECURITY_HEADERS.items():
        resp.headers[k] = v
    return resp


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


class SecurityMiddleware(BaseHTTPMiddleware):
    """เตรียม CSRF token ให้ handler ใช้ และใส่ security headers ทุก response"""

    async def dispatch(self, request, call_next):
        # 🔴 ด่านแรกสุด: หัว Host ต้องอยู่ในรายการอนุญาต (กัน DNS rebinding · #23 F-01)
        if not host_allowed(request.headers.get("host", "")):
            try:
                from ..storage import audit
                audit.security_event("host_rejected", "warning",
                                     {"host": request.headers.get("host", "")[:120]},
                                     client=request.client.host if request.client else None)
            except Exception:  # noqa: BLE001 — การบันทึกล้มต้องไม่ทำให้การปฏิเสธล้ม
                pass
            return host_rejected_response()
        existing = request.cookies.get(CSRF_COOKIE)
        token = existing or new_csrf_token()
        request.state.csrf_token = token

        response = await call_next(request)

        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
        if not existing:
            response.set_cookie(CSRF_COOKIE, token, httponly=True, samesite="strict",
                                secure=False, path="/")
        return response


def verify_csrf(request, form_token: str) -> None:
    """เรียกต้น handler ของทุกเส้นทางที่เปลี่ยนสถานะ - โยน CSRFError ถ้าไม่ผ่าน"""
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    host = request.headers.get("host", "")
    # 🔴 ``Origin: null`` ไม่ใช่ origin ที่ไม่ตรง แต่แปลว่า **เบราว์เซอร์ไม่บอก**
    # เกิดได้จากนโยบาย referrer ที่เข้มงวด หรือจาก sandboxed iframe
    # ถือเป็น "ไม่มีข้อมูล" แล้วไปตัดสินด้วย double-submit cookie แทน —
    # ซึ่งยังกัน cross-site ได้อยู่ เพราะคุกกี้เป็น ``SameSite=Strict``
    # คำขอข้ามไซต์จึงไม่มีคุกกี้ติดมาเลย และตกด่านโทเคนข้างล่างแน่นอน
    if origin and origin != "null":
        netloc = origin.split("//", 1)[-1].split("/", 1)[0]
        if netloc != host:
            raise CSRFError("origin_mismatch")

    cookie_token = request.cookies.get(CSRF_COOKIE)
    if not cookie_token or not form_token or not secrets.compare_digest(
            str(cookie_token), str(form_token)):
        raise CSRFError("csrf_token_invalid")
