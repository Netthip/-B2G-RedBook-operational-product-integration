# -*- coding: utf-8 -*-
"""Security gate — attack-surface regression ผ่าน HTTP (Issue #23 · หมวด C)

ทุกกรณีใช้ข้อมูลสังเคราะห์/ค่าที่แต่งขึ้น · ไม่มีไฟล์จริง
check id ที่ matrix อ้าง: ``T:tests/test_security_gate_web.py::<ชื่อ test>``
"""
import re

import pytest
from fastapi.testclient import TestClient

from redbook.app import create_app
from security_gate.http_probes import UNSAFE_BODY_PATTERNS
from redbook.storage import repository as repo
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD, SECURITY_HEADERS


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


def _token(client):
    client.get("/")
    return client.cookies.get(CSRF_COOKIE)


def _assert_safe(body: str):
    hits = [p.pattern for p in UNSAFE_BODY_PATTERNS if p.search(body)]
    assert not hits, f"หน้าข้อผิดพลาดมีสิ่งที่ไม่ควรเผย: {hits}"


def _assert_headers(r):
    for k in ("x-content-type-options", "content-security-policy", "cache-control"):
        assert k in r.headers, f"ไม่มี {k} บน {r.request.method} {r.request.url.path}"
    assert r.headers["x-content-type-options"] == SECURITY_HEADERS["X-Content-Type-Options"]


@pytest.mark.parametrize("path", [
    "/projects/zz-unknown", "/runs/zz-unknown", "/runs/zz-unknown/review",
    "/runs/zz-unknown/compare", "/findings/zz-unknown", "/t1b/runs/zz-unknown",
    "/t1b/runs/zz-unknown/queue", "/t1b/runs/zz-unknown/export", "/t1b/runs/zz-unknown/audit",
    "/t1b/runs/zz-unknown/findings/zz", "/t1b/runs/zz-unknown/personnel",
    "/evidence/zz-unknown", "/evidence/zz-unknown/file", "/evidence/zz-unknown/page/1.png",
    "/indicators/runs/zz-unknown", "/indicators/runs/zz-unknown/verify",
    "/indicators/runs/zz-unknown/keybuild", "/files/zz-unknown/structure",
    "/t1b/exports/exp_zz-unknown.csv", "/indicators/exports/zz-unknown.csv",
])
def test_unknown_object_ids_fail_closed(client, path):
    r = client.get(path)
    # 410 = เส้นทางดาวน์โหลดแบบเดิมที่ปฏิเสธเสมอโดยออกแบบ (P4-2) — fail-closed เช่นกัน
    assert r.status_code in (400, 404, 410), (path, r.status_code)
    _assert_safe(r.text)
    _assert_headers(r)


@pytest.mark.parametrize("path", [
    "/t1b/exports/..%5c..%5cx", "/t1b/exports/%2e%2e/x", "/t1b/exports/exp_..%2f..%2fx",
    "/t1b/exports/exp_%2e%2e%5cx.csv", "/indicators/exports/..%2fx",
    "/indicators/runs/x/exports/..%2fx", "/static/..%2f..%2fapp.py",
    "/static/..%5c..%5capp.py", "/static/../../redbook/app.py",
])
def test_export_download_rejects_traversal(client, path):
    r = client.get(path)
    assert r.status_code in (400, 404), (path, r.status_code)
    assert "def create_app" not in r.text
    _assert_safe(r.text)


def test_cross_site_referer_only_is_rejected(client):
    token = _token(client)
    r = client.post("/projects/new", data={"name": "x", "mode": "before_after_reduction",
                                           CSRF_FIELD: token},
                    headers={"Referer": "https://evil.example/attack.html"})
    assert r.status_code == 403
    _assert_safe(r.text)


def test_scriptish_path_param_is_not_reflected_raw(client):
    payload = "<script>alert(1)</script>"
    r = client.get("/projects/" + payload)
    assert r.status_code in (400, 404)
    assert payload not in r.text
    r = client.get("/queue?q=" + payload)
    assert r.status_code in (200, 400, 404)
    assert payload not in r.text


def test_form_inputs_are_validated_server_side(client, xlsx_factory):
    token = _token(client)
    r = client.post("/projects/new", data={"name": "ด่านตรวจอินพุต", "mode": "before_after_reduction",
                                           CSRF_FIELD: token}, follow_redirects=False)
    assert r.status_code == 303
    pid = r.headers["location"].rsplit("/", 1)[-1]
    path = xlsx_factory("ok.xlsx")

    with open(path, "rb") as fh:          # side นอก A/B/REF
        r = client.post(f"/projects/{pid}/upload", data={"side": "Z", CSRF_FIELD: token},
                        files={"upload": ("ok.xlsx", fh, "application/octet-stream")})
    assert r.status_code == 400
    _assert_safe(r.text)

    with open(path, "rb") as fh:          # ปีงบประมาณไม่ใช่ตัวเลข
        r = client.post(f"/projects/{pid}/upload",
                        data={"side": "A", "fiscal_year": "abc", CSRF_FIELD: token},
                        files={"upload": ("ok.xlsx", fh, "application/octet-stream")})
    assert r.status_code == 400
    _assert_safe(r.text)

    with open(path, "rb") as fh:          # ฟิลด์ยาวเกิน — ต้องถูกตัด ไม่ใช่ 500
        r = client.post(f"/projects/{pid}/upload",
                        data={"side": "A", "agency_code": "x" * 500, "agency_name": "y" * 5000,
                              "doc_kind": "z" * 5000, CSRF_FIELD: token},
                        files={"upload": ("ok.xlsx", fh, "application/octet-stream")},
                        follow_redirects=False)
    assert r.status_code == 303
    pf = repo.project_files(pid)
    assert len(pf["A"].get("agency_code") or "") <= 40
    assert len(pf["A"].get("agency_name") or "") <= 200

    r = client.post("/projects/new", data={"name": "", "mode": "nonsense", CSRF_FIELD: token})
    assert r.status_code == 400
    _assert_safe(r.text)


def test_malformed_multipart_body_fails_safely(client):
    r = client.post("/projects/new", content=b"\xff\xfe\x00garbage\r\n--zz--",
                    headers={"Content-Type": "multipart/form-data; boundary=zz"})
    assert 400 <= r.status_code < 500
    _assert_safe(r.text)
    _assert_headers(r)
    r = client.post("/projects/new", json={"name": "x"})
    assert 400 <= r.status_code < 500
    _assert_safe(r.text)


def test_unhandled_exception_renders_generic_500_page(client, monkeypatch):
    import redbook.app as app_module

    def boom(*a, **k):
        raise RuntimeError("secret detail Q:\\synthetic_home\\someone\\private\\x.sqlite")

    monkeypatch.setattr(app_module.repo, "list_projects", boom)
    r = client.get("/")
    assert r.status_code == 500
    assert "RuntimeError" not in r.text and "secret detail" not in r.text
    assert "someone" not in r.text
    _assert_safe(r.text)
    _assert_headers(r)
    assert re.search(r"รหัสอ้างอิงเหตุการณ์", r.text)


@pytest.mark.parametrize("method", ["TRACE", "PUT", "PATCH", "DELETE", "OPTIONS"])
@pytest.mark.parametrize("path", ["/", "/projects/new", "/healthz"])
def test_unexpected_methods_fail_safely(client, method, path):
    r = client.request(method, path, headers={"X-Echo": "zapline-9f1"})
    assert r.status_code in (404, 405), (method, path, r.status_code)
    assert "zapline-9f1" not in r.text
    _assert_safe(r.text)
    _assert_headers(r)


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8600", "127.0.0.1.evil.example"])
def test_unknown_host_header_is_rejected(client, host):
    """กัน DNS rebinding — เว็บแอปบน loopback ต้องไม่ตอบคำขอที่หัว Host ไม่อยู่ในรายการอนุญาต"""
    r = client.get("/", headers={"Host": host})
    assert r.status_code in (400, 421), (host, r.status_code)
    _assert_safe(r.text)
    _assert_headers(r)
