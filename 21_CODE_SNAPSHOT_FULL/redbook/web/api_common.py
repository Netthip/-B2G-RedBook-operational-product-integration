# -*- coding: utf-8 -*-
"""ส่วนกลางของ JSON API (``/api/*``) — ด่านเดียวกับฟอร์มเดิม แต่คืนข้อผิดพลาดเป็น JSON (สัญญา ``docs/API_CONTRACT_R.md``)

* :func:`read_json` — CSRF แบบ double-submit จากหัว ``X-CSRF-Token`` ผ่าน :func:`security.verify_csrf` ตัวเดียวกับฟอร์มเดิม
  (ตรวจ Origin + คุกกี้ ``SameSite=Strict``) · body เกิน :data:`MAX_BODY` = 413 · JSON ที่ไม่ใช่ object = ``{}``
* :func:`api` — ตัวครอบ handler: CSRF ไม่ผ่าน → 403 ``code=csrf`` + บันทึก ``csrf_rejected`` แบบเดียวกับ handler เดิมใน
  ``app.py`` · :class:`ApiError` → สถานะ/รหัสที่ระบุ · ข้อผิดพลาดของ service (ValueError) → 400 ``invalid`` ·
  ข้อผิดพลาดที่ไม่คาด → 500 ``code=server`` + ``error_id`` (บันทึก log · ไม่มี stack trace/path ในคำตอบ) ·
  handler แบบ ``def`` ธรรมดารันใน threadpool (งาน SQLite/แยก JSON/วาดภาพไม่บล็อก event loop — คำขออื่นไม่ต่อคิว)
* :func:`finding_json` / :func:`finding_extras` — วัตถุข้อสังเกตตามสัญญาข้อ 2 (ธง/คำเตือนไปถึงจุดที่ใช้ผล)
"""
from __future__ import annotations

import functools
import inspect
import json
import logging
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .. import privacy
from ..services import pdfpair
from ..storage import audit
from .security import CSRFError, verify_csrf

log = logging.getLogger("redbook.api")

#: ขนาด body สูงสุดของคำขอ JSON (ไบต์) — คำขอของหน้าบ้านเป็นข้อความสั้น (คำตัดสิน · หมายเหตุ · พิกัดจุดที่วง)
MAX_BODY = 64 * 1024
CSRF_MESSAGE = "คำขอนี้ไม่ผ่านการตรวจสอบความปลอดภัย โปรดเปิดหน้าใหม่แล้วลองอีกครั้ง"


class ApiError(Exception):
    """ข้อผิดพลาดที่ handler ตั้งใจคืน — ``status`` + ``code`` ตามสัญญาข้อ 1"""

    def __init__(self, message: str, status: int = 400, code: str = "invalid"):
        super().__init__(message)
        self.status, self.code = status, code


def json_error(message: str, status: int = 400, code: str = "invalid", **extra) -> JSONResponse:
    return JSONResponse({"error": privacy.redact_text(str(message)), "code": code, **extra}, status_code=status)


TOO_LARGE_MESSAGE = "คำขอใหญ่เกินกว่าที่ระบบรับได้"


async def _body_capped(request: Request) -> bytes:
    """อ่าน body โดย **ไม่สะสมเกิน** :data:`MAX_BODY` (Bo REVIEW 6409941573 ข้อ 2) — ``Content-Length`` เกิน = ปฏิเสธก่อนอ่าน ·
    ไม่แจ้งความยาว (chunked) = นับระหว่างรับ เกินเมื่อไรหยุดทันที"""
    declared = request.headers.get("content-length", "")
    if declared.strip().isdigit() and int(declared) > MAX_BODY:
        raise ApiError(TOO_LARGE_MESSAGE, 413, "too_large")
    parts, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY:
            raise ApiError(TOO_LARGE_MESSAGE, 413, "too_large")
        parts.append(chunk)
    return b"".join(parts)


async def read_json(request: Request) -> dict:
    """body ของคำขอที่เปลี่ยนสถานะ — ตรวจ CSRF **ก่อน** อ่าน body (ไม่ผ่าน = :class:`CSRFError`)"""
    verify_csrf(request, request.headers.get("x-csrf-token", ""))
    raw = await _body_capped(request)
    try:
        data = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, ValueError):
        raise ApiError("รูปแบบคำขอไม่ถูกต้อง (ต้องเป็น JSON)")
    return data if isinstance(data, dict) else {}


def csrf_rejected(request: Request, exc: CSRFError) -> JSONResponse:
    """เหมือน handler ``csrf_error`` ใน ``app.py`` (บันทึกเหตุการณ์ความปลอดภัย) แต่ตอบเป็น JSON"""
    audit.security_event("csrf_rejected", "warning", {"event": exc.event, "api": True},
                         client=request.client.host if request.client else None)
    return json_error(CSRF_MESSAGE, 403, "csrf")


def api(handler):
    """ตัวครอบ handler ของ ``/api/*`` — พารามิเตอร์แรกต้องเป็น ``request: Request``

    ``def`` ธรรมดา (GET ที่ไม่อ่าน body) = รันใน threadpool · ``async def`` = รันบน event loop — handler ที่ต้อง
    ``await read_json`` จึงเป็น ``async def`` แล้วส่งงานที่บล็อกต่อด้วย ``run_in_threadpool`` เอง"""
    blocking = not inspect.iscoroutinefunction(handler)

    @functools.wraps(handler)
    async def wrapper(request: Request, *args, **kwargs):
        try:
            if blocking:
                return await run_in_threadpool(handler, request, *args, **kwargs)
            return await handler(request, *args, **kwargs)
        except CSRFError as e:
            return csrf_rejected(request, e)
        except ApiError as e:
            return json_error(str(e), e.status, e.code)
        except ValueError as e:                 # TrialError · PairError · ShelfError ฯลฯ = ข้อความที่ผู้ใช้อ่านได้
            return json_error(str(e))
        except Exception:                       # noqa: BLE001 — ห้ามหลุด stack trace/path ไปถึงผู้ใช้
            error_id = uuid.uuid4().hex[:12]
            log.exception("error_id=%s unhandled api at %s", error_id, request.url.path)
            return json_error("เกิดข้อผิดพลาดภายในระบบ ระบบบันทึกเหตุการณ์ไว้แล้ว", 500, "server", error_id=error_id)
    return wrapper


# ── วัตถุข้อสังเกต (สัญญาข้อ 2) ───────────────────────────────────────────────────────────────
def side_json(s, evidence_png: str | None = None, unit: str = "") -> dict:
    """``unit`` = หน่วยของข้อสังเกต — ใช้แทนเมื่อฝั่งนี้ไม่มีหน่วยของตัวเอง (เหมือน ``amount_text(f.a, f.unit)`` ในหน้าเดิม)"""
    return {"value": s.value, "raw": s.raw, "unit": s.unit, "unit_origin": s.unit_origin,
            "unit_note": pdfpair.unit_note(s), "raw_note": pdfpair.raw_note(s), "status": s.status,
            "amount_text": pdfpair.amount_text(s, unit) if (s.value or s.status) else "",
            "page": s.page, "bbox": list(s.bbox) if s.bbox else None, "text": s.text,
            "evidence_png": evidence_png}


def part_json(p: dict) -> dict:
    return {"label": p.get("label", ""), "value": p.get("value", ""), "raw": p.get("raw", ""),
            "unit": p.get("unit", ""), "page": p.get("page"), "bbox": p.get("bbox"),
            "flags": list(p.get("flags", [])),
            "flag_labels": [pdfpair.CAVEAT_LABELS[x] for x in p.get("flags", []) if x in pdfpair.CAVEAT_LABELS]}


def finding_extras(f) -> dict:
    """ฟิลด์เพิ่มเติมที่ทุกที่ที่แสดงข้อสังเกตต้องส่งต่อ — ใช้เติมให้วัตถุข้อสังเกตของสายทดลองได้โดยไม่เปลี่ยนฟิลด์เดิม"""
    return {"kind_code": f.kind, "info": bool(f.info), "caveats": list(f.caveats),
            "delta_text": pdfpair.delta_text(f), "tolerance": f.tolerance,
            "tolerance_text": pdfpair.tolerance_text(f), "tolerance_basis": getattr(f, "tolerance_basis", ""),
            "parts": [part_json(p) for p in f.parts]}


def finding_json(f, rid: str = "", decision: dict | None = None, use: str | None = None) -> dict:
    base = f"/pdfpair/runs/{rid}/f/{f.id}" if rid else ""
    out = {"id": f.id, "topic": f.topic, "topic_label": f.topic_label, "kind": f.kind,
           "kind_label": f.kind_label, "subject": f.subject, "column": f.column, "within": f.within,
           "info": bool(f.info), "a": side_json(f.a, f"{base}/A.png" if base and f.a.page else None, f.unit),
           "b": side_json(f.b, f"{base}/B.png" if base and f.b.page else None, f.unit),
           "delta": f.delta, "delta_text": pdfpair.delta_text(f), "unit": f.unit, "note": f.note,
           "caveats": list(f.caveats), "parts": [part_json(p) for p in f.parts],
           "tolerance": f.tolerance, "tolerance_text": pdfpair.tolerance_text(f),
           "tolerance_basis": getattr(f, "tolerance_basis", ""), "evidence": base}
    if use is not None:
        out["decision"] = ({"choice": decision["choice"], "choice_label": pdfpair.DECISION_LABELS.get(decision["choice"], ""),
                            "after": pdfpair.DECISION_AFTER.get(decision["choice"], ""),
                            "note": decision.get("note", ""), "decided_at": decision.get("decided_at", "")}
                           if decision else None)
        out["use"], out["use_label"] = use, pdfpair.USE_LABELS.get(use, use)
    return out


__all__ = ["MAX_BODY", "ApiError", "json_error", "read_json", "csrf_rejected", "api", "run_in_threadpool",
           "side_json", "part_json", "finding_extras", "finding_json"]
