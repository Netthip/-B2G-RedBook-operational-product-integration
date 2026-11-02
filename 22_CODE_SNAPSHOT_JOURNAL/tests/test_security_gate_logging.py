# -*- coding: utf-8 -*-
"""Security gate — security events ถูกบันทึกครบและไม่มีค่าลับ"""
import io
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from redbook.app import create_app
from redbook.storage import audit
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


def test_csrf_rejection_is_logged_without_token_value(client):
    client.get("/")
    cookie = client.cookies.get(CSRF_COOKIE)
    wrong = "WRONG-TOKEN-VALUE-9f1c"
    r = client.post("/projects/new", data={"name": "x", "mode": "before_after_reduction",
                                           CSRF_FIELD: wrong})
    assert r.status_code == 403
    ev = audit.security_events(limit=5)
    assert ev and ev[0]["event"] == "csrf_rejected"
    assert ev[0]["severity"] == "warning"
    blob = json.dumps(ev[0], ensure_ascii=False)
    assert wrong not in blob and cookie not in blob


def test_upload_rejection_is_logged_with_sanitized_name(client):
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post("/projects/new", data={"name": "log gate", "mode": "before_after_reduction",
                                           CSRF_FIELD: token}, follow_redirects=False)
    pid = r.headers["location"].rsplit("/", 1)[-1]
    evil_name = "..\\..\\evil\x01\x02 name.exe"
    r = client.post(f"/projects/{pid}/upload", data={"side": "A", CSRF_FIELD: token},
                    files={"upload": (evil_name, io.BytesIO(b"MZ not a workbook"),
                                      "application/octet-stream")})
    assert r.status_code == 400
    ev = audit.security_events(limit=5)
    assert ev[0]["event"].startswith("upload_rejected_")
    detail = json.loads(ev[0]["detail_json"])
    declared = detail.get("declared_name", "")
    assert "\\" not in declared and "/" not in declared and ".." not in declared
    assert "\x01" not in declared and "\x02" not in declared
    assert ev[0]["client"]  # TestClient ส่ง client host มาเสมอ


# ─────────────────────────────────────────────────────────────────────────────
#  #28 (Bo #23 รอบ 3): อะไรจาก request เข้า shared log ได้บ้าง — synthetic adversarial
# ─────────────────────────────────────────────────────────────────────────────
import logging
import re

from redbook import config

_TS = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} (INFO|WARNING|ERROR|CRITICAL) ")


def _log_text() -> str:
    for h in logging.getLogger("redbook").handlers:
        h.flush()
    p = config.LOG_DIR / "app.log"
    return p.read_text("utf-8") if p.exists() else ""


def test_log_lines_are_never_forged_by_control_chars_in_request(client):
    """log injection: CR/LF/TAB ใน path/path-param ต้องไม่ทำให้เกิดบรรทัดใหม่หรืออักขระควบคุมในล็อก"""
    for u in ("/projects/x%0d%0a2026-01-01 00:00:00,000 WARNING redbook FORGED_LINE_9c1",
              "/evidence/a%0d%0aFORGED_LINE_9c2/file", "/t1b/runs/r%0d%0aFORGED_LINE_9c3/export",
              "/indicators/runs/q%0d%0aFORGED_LINE_9c4/exports/exp_x.csv",
              "/projects/%09tab%00nul%1bESC_9c5", "/projects/%E2%80%A8ls_9c6"):
        r = client.get(u)
        assert r.status_code < 500
    text = _log_text()
    lines = text.splitlines()
    assert lines
    forged = [ln for ln in lines if not _TS.match(ln)]
    assert not forged, f"บรรทัดที่ไม่ขึ้นต้นด้วย timestamp (ถูกปลอม?): {forged[:3]}"
    assert not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f  ]", text), "อักขระควบคุมหลุดลงล็อก"
    assert "FORGED_LINE_9c1" not in [ln.split(" ", 4)[-1][:17] for ln in lines]


def test_request_path_is_logged_sanitized_but_query_headers_and_form_are_not(client):
    """ขอบเขตที่ประกาศ: path (sanitize แล้ว) เข้าล็อกได้เมื่อเกิดข้อผิดพลาด · query/header/ฟอร์ม/ชื่อไฟล์ ไม่เข้า"""
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    client.get("/projects/PATHMARK_9d1")
    client.get("/queue?q=QUERYMARK_9d2")
    client.get("/nope", headers={"User-Agent": "UAMARK_9d3", "Referer": "https://evil.example/REFMARK_9d4"})
    client.post("/projects/new", data={"name": "FORMMARK_9d5", "mode": "zzz", CSRF_FIELD: token})
    client.post("/projects/new", data={"name": "x", CSRF_FIELD: "WRONGTOKEN_9d6"})
    r = client.post("/projects/new", data={"name": "p", "mode": "before_after_reduction",
                                           CSRF_FIELD: token}, follow_redirects=False)
    pid = r.headers["location"].rsplit("/", 1)[-1]
    client.post(f"/projects/{pid}/upload", data={"side": "A", CSRF_FIELD: token},
                files={"upload": ("UPLOADMARK_9d7.xlsx", io.BytesIO(b"not a workbook"),
                                  "application/octet-stream")})
    text = _log_text()
    assert "PATHMARK_9d1" in text                     # path ของคำขอที่ล้มเหลว — บันทึกโดยตั้งใจ (sanitize แล้ว)
    for mark in ("QUERYMARK_9d2", "UAMARK_9d3", "REFMARK_9d4", "FORMMARK_9d5", "WRONGTOKEN_9d6",
                 "UPLOADMARK_9d7"):
        assert mark not in text, f"{mark} ไม่ควรเข้าล็อก"


def test_oversized_path_is_truncated_in_log(client):
    client.get("/projects/" + "A" * 20000)
    text = _log_text()
    longest = max(len(ln) for ln in text.splitlines())
    assert longest < 5000, "ข้อความล็อกหนึ่งรายการต้องถูกตัดความยาว"
    assert "[truncated]" in text


def test_security_event_timestamp_is_iso8601_with_offset(client):
    client.post("/projects/new", data={"name": "x"})     # ทำให้เกิด csrf_rejected หนึ่งรายการ
    ev = audit.security_events(limit=1)[0]
    ts = datetime.fromisoformat(ev["ts"])
    assert ts.tzinfo is not None and ts.utcoffset() is not None
    assert ev["event"] and ev["severity"]
