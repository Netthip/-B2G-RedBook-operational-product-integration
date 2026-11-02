# -*- coding: utf-8 -*-
"""หลักฐานความปลอดภัยของหน้าบ้าน Svelte (/r) สำหรับ #23 — ตรวจทั้งไฟล์ที่ build แล้ว โค้ดต้นทาง และหัว HTTP ที่เซิร์ฟเวอร์ส่งจริง

🔴 SYNTHETIC DEMONSTRATION DATA — ใช้ fixture ชั้นเล่มสังเคราะห์ชุดเดียวกับ ``test_trial.py``

* หน้า /r และไฟล์ JS/CSS ได้หัว CSP แบบเดียวกับหน้าเดิม (ไม่มี unsafe-inline/unsafe-eval · ไม่โหลดจากเครื่องอื่น)
* โค้ดต้นทางไม่ใช้ช่องทางที่ทำให้ข้อความกลายเป็น HTML/สคริปต์ ไม่เก็บข้อมูลไว้ในเบราว์เซอร์ และเรียกเฉพาะ origin เดียวกัน
* คำขอ JSON ที่เปลี่ยนสถานะ: ไม่มีโทเคน/โทเคนผิด/Origin อื่น = 403 · ทั้งบนแอปเต็มและเซิร์ฟเวอร์สาย PDF
* F-01 (Host allowlist) ของ #23: เซิร์ฟเวอร์สาย PDF ปฏิเสธ Host นอกรายการ (400) · แอปเต็มยังไม่มีการแก้ของ #23 (รอ consolidation)
"""
import re

import pytest
from fastapi.testclient import TestClient

from test_trial import PROJECT_ROOT, _env, client, shelf  # noqa: F401  (fixture ร่วม)

APP = PROJECT_ROOT / "redbook" / "static" / "app"
SRC = PROJECT_ROOT / "frontend" / "src"
SOURCES = sorted(p for p in SRC.rglob("*") if p.suffix in (".svelte", ".ts"))
PAGES = ("/r", "/r/lib", "/r/about", "/r/dev", "/r/p", "/r/p/new", "/r/p/pp_x", "/r/p/pp_x/f/abc123", "/r/p/pp_x/preflight", "/r/p/pp_x/audit", "/r/p/pp_x/summary", "/r/s/tr_x")
built = pytest.mark.skipif(not (APP / "index.html").exists(), reason="ยังไม่ได้ build หน้าบ้าน (npm run build)")


def _csp(h: str) -> dict:
    return {d.split()[0]: d.split()[1:] for d in (x.strip() for x in h.split(";")) if d}


@built
def test_pages_and_assets_carry_the_same_security_headers(client):
    assets = [f"/static/app/assets/{p.name}" for p in (APP / "assets").iterdir()]
    for path in [*PAGES, *assets]:
        r = client.get(path)
        assert r.status_code == 200, path
        csp = _csp(r.headers["content-security-policy"])
        assert csp["script-src"] == ["'self'"] and csp["style-src"] == ["'self'"], path
        assert csp["default-src"] == ["'none'"] and csp["object-src"] == ["'none'"] and csp["frame-ancestors"] == ["'none'"]
        assert csp["connect-src"] == ["'self'"] and csp["base-uri"] == ["'none'"]
        assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "same-origin"
    page = client.get("/r/p")
    assert page.headers["cache-control"] == "no-store"
    assert '<meta name="referrer" content="same-origin">' in page.text          # ตรงกับหัว (บทเรียน F-04)


@built
def test_built_bundle_loads_nothing_from_elsewhere():
    for f in (APP / "assets").iterdir():
        text = f.read_text(encoding="utf-8")
        # ข้อความ URL ที่ยอมได้: namespace ของ XHTML และลิงก์คำอธิบายในข้อความ error ของ Svelte (ไม่ใช่การโหลด · CSP บล็อกอยู่แล้ว)
        assert not re.search(r"https?://(?!www\.w3\.org/1999/xhtml|svelte\.dev/e/)", text), f.name
        if f.suffix == ".css":
            for url in re.findall(r"url\(([^)]+)\)", text):
                assert url.strip("'\"").startswith(("/static/", "data:")), url


def test_sources_have_no_html_injection_storage_or_dynamic_code_sinks():
    banned = {r"\{@html": "แทรก HTML ดิบ", r"\.innerHTML|\.outerHTML|insertAdjacentHTML": "เขียน HTML ด้วยมือ",
              r"document\.write": "document.write", r"\beval\(|new Function\(": "สร้างโค้ดจากข้อความ",
              r"localStorage|sessionStorage|indexedDB": "เก็บข้อมูลไว้ในเบราว์เซอร์", r"document\.cookie": "อ่าน/เขียนคุกกี้",
              r"window\.open\(|postMessage\(": "เปิดหน้าต่าง/ส่งข้อความข้าม origin", r"\bstyle=\"": "สไตล์ฝังในแท็ก (CSP)",
              r"from\s+[\"']svelte/transition[\"']": "svelte/transition ฉีด <style> (CSP)"}
    assert SOURCES
    for p in SOURCES:
        text = p.read_text(encoding="utf-8")
        for pat, why in banned.items():
            assert not re.search(pat, text), f"{p.name}: {why}"


def test_external_links_open_without_opener_and_fetches_stay_on_this_origin():
    for p in SOURCES:
        text = p.read_text(encoding="utf-8")
        for tag in re.findall(r"<a\b[^>]*target=\"_blank\"[^>]*>", text):
            assert 'rel="noopener"' in tag, f"{p.name}: {tag}"
        for arg in re.findall(r"(?<![\w.])fetch\(\s*([^,)]+)", text):
            assert arg.strip().startswith(("\"/", "'/", "`/", "url")), f"{p.name}: fetch({arg})"


def _lane_client():
    from redbook.pdf_lane_app import create_lane_app
    return TestClient(create_lane_app(guard=False), base_url="http://127.0.0.1:8645")


@pytest.mark.parametrize("which", ["full", "lane"])
def test_json_writes_refuse_missing_wrong_or_cross_origin_tokens(client, which):
    c = client if which == "full" else _lane_client()
    tok = c.get("/api/csrf").json()["token"]
    url, body = "/api/pdfpair/shelf/start", {"a": "x", "b": "y", "agency": "z"}
    assert c.post(url, json=body).json()["code"] == "csrf"
    assert c.post(url, json=body, headers={"X-CSRF-Token": "wrong"}).json()["code"] == "csrf"
    evil = c.post(url, json=body, headers={"X-CSRF-Token": tok, "Origin": "http://evil.example"})
    assert evil.status_code == 403 and evil.json()["code"] == "csrf"
    ok = c.post(url, json=body, headers={"X-CSRF-Token": tok})
    assert ok.status_code != 403 and "Traceback" not in ok.text      # ผ่านด่าน CSRF แล้วจึงถึงการตรวจข้อมูล


def test_lane_server_serves_r_and_refuses_excel_lane_pages():
    c = _lane_client()
    assert c.get("/api/lane").json()["lane"] == "pdf_only"
    assert c.get("/r/p").status_code == 200
    for path in ("/books", "/audit", "/t1b", "/projects"):
        assert c.get(path).status_code == 404, path


def test_foreign_host_header_is_refused_on_the_lane_server():
    c = _lane_client()
    assert c.get("/r/p", headers={"Host": "evil.example"}).status_code == 400
    assert c.get("/r/p").status_code == 200                    # localhost ยังเปิดได้ปกติ
