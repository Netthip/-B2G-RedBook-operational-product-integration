# -*- coding: utf-8 -*-
"""ทดสอบเว็บแอป: security headers, CSRF, เส้นทางทำงานหลัก และการไม่รั่วข้อมูลภายใน"""
import re

import pytest
from fastapi.testclient import TestClient

from redbook.app import create_app
from redbook.storage import repository as repo
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


def _csrf(client, path="/"):
    r = client.get(path)
    token = client.cookies.get(CSRF_COOKIE)
    assert token, "ต้องได้รับ CSRF cookie จากหน้าเว็บ"
    return token, r


def test_security_headers_present(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    # 🔴 เปลี่ยนจาก ``no-referrer`` เป็น ``same-origin`` เมื่อ 23 ก.ย. 2569 —
    # ``no-referrer`` ทำให้เบราว์เซอร์จริงส่ง ``Origin: null`` มากับทุกแบบฟอร์ม
    # ด่าน CSRF จึงปฏิเสธทุกคำขอ และ **ไม่มีฟอร์มใดในระบบใช้งานได้เลย**
    # เว็บภายนอกยังไม่ได้รับ referrer เพราะนโยบายนี้ให้เฉพาะ origin เดียวกัน
    assert r.headers["referrer-policy"] == "same-origin"
    assert r.headers["cache-control"] == "no-store"


def test_api_docs_are_disabled(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_post_without_csrf_is_rejected(client):
    _csrf(client)
    r = client.post("/projects/new", data={"name": "x", "mode": "year_to_year"})
    assert r.status_code == 403


def test_post_with_wrong_csrf_is_rejected(client):
    _csrf(client)
    r = client.post("/projects/new",
                    data={"name": "x", "mode": "year_to_year", CSRF_FIELD: "not-the-token"})
    assert r.status_code == 403


def test_cross_origin_post_is_rejected(client):
    token, _ = _csrf(client)
    r = client.post("/projects/new",
                    data={"name": "x", "mode": "year_to_year", CSRF_FIELD: token},
                    headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


def test_full_flow_create_upload_precheck_decide(client, xlsx_factory):
    token, _ = _csrf(client, "/projects/new")

    r = client.post("/projects/new",
                    data={"name": "งานตรวจทดสอบ", "mode": "year_to_year",
                          "note": "", CSRF_FIELD: token},
                    follow_redirects=False)
    assert r.status_code == 303
    pid = r.headers["location"].rsplit("/", 1)[-1]

    for side, year in (("A", "2569"), ("B", "2569")):
        path = xlsx_factory(f"{side}.xlsx")
        with open(path, "rb") as fh:
            r = client.post(f"/projects/{pid}/upload",
                            data={"side": side, "fiscal_year": year,
                                  "agency_code": "21016", "agency_name": "หน่วยงานทดสอบ",
                                  "doc_kind": "เอกสารทดสอบ", CSRF_FIELD: token},
                            files={"upload": (f"{side}.xlsx", fh,
                                              "application/vnd.ms-excel")},
                            follow_redirects=False)
        assert r.status_code == 303

    r = client.post(f"/projects/{pid}/precheck", data={CSRF_FIELD: token},
                    follow_redirects=False)
    assert r.status_code == 303
    rid = r.headers["location"].rsplit("/", 1)[-1]

    # โหมดปีต่อปีแต่ระบุปีเดียวกันทั้งสองฝั่ง ต้องได้ข้อสังเกต M01
    findings = repo.list_findings(rid)
    assert any(f["rule_id"] == "M01" for f in findings)
    assert all(f["review_status"] == "pending" for f in findings)

    page = client.get(f"/runs/{rid}").text
    assert "ยังไม่ได้เปรียบเทียบเนื้อหาภายในไฟล์" in page

    fid = findings[0]["id"]
    r = client.post(f"/findings/{fid}/decide",
                    data={"decision": "confirmed_valid_change",
                          "note": "ตรวจกับต้นฉบับแล้วเป็นการจัดทำฉบับเดียวกัน",
                          "reviewer": "ผู้ทดสอบ", CSRF_FIELD: token},
                    follow_redirects=False)
    assert r.status_code == 303
    assert repo.get_finding(fid)["review_status"] == "confirmed_valid_change"


def test_decision_requires_reason(client, xlsx_factory):
    token, _ = _csrf(client, "/projects/new")
    r = client.post("/projects/new",
                    data={"name": "งานตรวจเหตุผล", "mode": "year_to_year",
                          CSRF_FIELD: token}, follow_redirects=False)
    pid = r.headers["location"].rsplit("/", 1)[-1]
    for side in ("A", "B"):
        with open(xlsx_factory(f"{side}.xlsx"), "rb") as fh:
            client.post(f"/projects/{pid}/upload",
                        data={"side": side, "fiscal_year": "2570",
                              "agency_code": "21016", CSRF_FIELD: token},
                        files={"upload": (f"{side}.xlsx", fh, "application/octet-stream")},
                        follow_redirects=False)
    rid = client.post(f"/projects/{pid}/precheck", data={CSRF_FIELD: token},
                      follow_redirects=False).headers["location"].rsplit("/", 1)[-1]
    fid = repo.list_findings(rid)[0]["id"]
    r = client.post(f"/findings/{fid}/decide",
                    data={"decision": "confirmed_error", "note": "   ",
                          "reviewer": "x", CSRF_FIELD: token})
    assert r.status_code == 400
    assert repo.get_finding(fid)["review_status"] == "pending"


def test_rejected_upload_shows_safe_message_only(client):
    token, _ = _csrf(client, "/projects/new")
    r = client.post("/projects/new",
                    data={"name": "งานตรวจไฟล์เสีย", "mode": "year_to_year",
                          CSRF_FIELD: token}, follow_redirects=False)
    pid = r.headers["location"].rsplit("/", 1)[-1]
    r = client.post(f"/projects/{pid}/upload",
                    data={"side": "A", CSRF_FIELD: token},
                    files={"upload": ("x.xlsx", b"MZ\x90\x00", "application/octet-stream")})
    assert r.status_code == 400
    body = r.text
    assert "Traceback" not in body
    assert "C:\\" not in body and "/home/" not in body
    assert "redbook/storage/files.py" not in body


def test_not_found_page_has_no_internals(client):
    r = client.get("/projects/prj_doesnotexist")
    assert r.status_code == 404
    assert "Traceback" not in r.text
    assert "ไม่พบงานตรวจที่ระบุ" in r.text


def test_uploaded_filename_is_escaped_in_html(client, xlsx_factory):
    """ชื่อไฟล์ที่มีสคริปต์ต้องถูก escape ไม่กลายเป็น HTML ที่ทำงานได้"""
    token, _ = _csrf(client, "/projects/new")
    r = client.post("/projects/new",
                    data={"name": "<script>alert(1)</script>", "mode": "year_to_year",
                          CSRF_FIELD: token}, follow_redirects=False)
    pid = r.headers["location"].rsplit("/", 1)[-1]
    with open(xlsx_factory("ok.xlsx"), "rb") as fh:
        client.post(f"/projects/{pid}/upload",
                    data={"side": "A", CSRF_FIELD: token},
                    files={"upload": ("<img src=x onerror=alert(1)>.xlsx", fh,
                                      "application/octet-stream")},
                    follow_redirects=False)
    body = client.get(f"/projects/{pid}").text
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body
    assert "<img src=x onerror=alert(1)>" not in body


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_rules_page_marks_planned_rules(client):
    body = client.get("/rules").text
    assert "อยู่ในแผน" in body
    assert "ใช้ตรวจจริง" in body


def test_audit_page_reports_chain_state(client):
    body = client.get("/audit").text
    assert re.search(r"สายโซ่แฮช", body)
