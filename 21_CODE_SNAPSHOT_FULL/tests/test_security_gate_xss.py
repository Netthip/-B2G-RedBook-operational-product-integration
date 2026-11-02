# -*- coding: utf-8 -*-
"""Security gate — attribute-context XSS regression (Bo REVIEW 6027478811 · ZAP alert 10031)

ZAP (passive) ชี้ว่า query `page`/`per_page` ของหน้ารายละเอียด finding ถูกสะท้อนเข้า attribute
ของ HTML (ลิงก์/ฟอร์มที่พกตัวกรองของคิว) · ชุดนี้ยิง payload แบบ **quote-break · event-handler ·
unquoted-attribute · javascript: URL** ลงทุกจุดสะท้อนที่รู้ แล้วตรวจด้วย oracle ที่ไม่ผูกกับ
implementation: parse HTML จริง — ห้ามเกิด attribute ชื่อ ``on*`` · ห้ามมี URL ``javascript:`` ·
ห้ามมี tag ใหม่จาก payload · และ response ต้องไม่เป็น 500

SYNTHETIC ONLY — คู่สมุดงานจาก scripts/demo_ao_workbooks.py
"""
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import demo_ao_workbooks as gen  # noqa: E402

from redbook.app import create_app  # noqa: E402
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD  # noqa: E402

MARK = "zapattr9f1"
PAYLOADS = [
    f'1" onmouseover="alert({MARK})',             # quote-break (double) + event handler
    f"1' onfocus='alert({MARK})",                 # quote-break (single)
    f"1 onmouseover=alert({MARK})",               # unquoted attribute injection
    f'"><img src=x onerror=alert({MARK})>',       # tag break-out
    f"javascript:alert({MARK})",                  # URL scheme
    f"1&quot; onclick=&quot;alert({MARK})",       # pre-encoded entities (double-decoding)
    f"%22%20onmouseover%3D%22alert({MARK})",      # percent-encoded (raw, ไม่ให้ client ถอด)
]


class _Oracle(HTMLParser):
    def __init__(self):
        super().__init__()
        self.violations: list[str] = []
        self.tags: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        for name, value in attrs:
            if name.lower().startswith("on"):
                self.violations.append(f"<{tag} {name}=…>")
            # javascript: อันตรายเฉพาะ attribute ที่เป็น URL — ใน value= ของ input เป็นแค่ข้อความ
            if name.lower() in ("href", "src", "action", "formaction", "data", "xlink:href") \
                    and value and value.strip().lower().replace(" ", "").startswith("javascript:"):
                self.violations.append(f"<{tag} {name}=javascript:…>")
            if value and MARK in value and name.lower() in ("src", "href", "action") \
                    and "alert(" in value and not value.startswith(("/", "?")):
                self.violations.append(f"<{tag} {name} carries payload>")


def _check(resp, where: str):
    assert resp.status_code < 500, f"{where}: {resp.status_code}"
    if "text/html" not in resp.headers.get("content-type", ""):
        return
    o = _Oracle()
    o.feed(resp.text)
    assert not o.violations, f"{where}: {o.violations}"
    # payload ที่หลุดเป็น tag ใหม่ต้องไม่มี — <img src=x onerror> จาก payload ที่ 4
    assert "img" not in o.tags or all(
        "onerror" not in a for a in [resp.text]), where
    assert f"<img src=x onerror=alert({MARK})>" not in resp.text, where
    assert f'onmouseover="alert({MARK})"' not in resp.text, where


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """สร้างงาน → อัปโหลดคู่สังเคราะห์ → วิเคราะห์ → คืน (client, rid, fid)"""
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.__enter__()
    a, b = gen.build(tmp_path_factory.mktemp("xss_pair"))
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post("/projects/new", data={CSRF_FIELD: token, "name": "xss gate",
                                           "mode": "before_after_reduction"},
                    follow_redirects=False)
    pid = r.headers["location"].rsplit("/", 1)[-1]
    for side, path, year in (("A", a, "2569"), ("B", b, "2570")):
        with open(path, "rb") as fh:
            r = client.post(f"/projects/{pid}/upload",
                            data={"side": side, "fiscal_year": year, CSRF_FIELD: token},
                            files={"upload": (path.name, fh, "application/octet-stream")},
                            follow_redirects=False)
        assert r.status_code == 303, r.text[:200]
    r = client.post(f"/projects/{pid}/analyze", data={CSRF_FIELD: token}, follow_redirects=False)
    assert r.status_code == 303, r.text[:200]
    rid = r.headers["location"].rstrip("/").split("/t1b/runs/")[-1].split("/")[0]
    q = client.get(f"/t1b/runs/{rid}/queue")
    assert q.status_code == 200
    import re
    # คิวลิงก์ไปหน้าเทียบ (/compare/{fid}) ตั้งแต่หน้าเทียบใหม่ — รหัส finding ชุดเดียวกับหน้ารายละเอียด (/findings/{fid})
    # ที่ ZAP ชี้ (Bo REVIEW #42 6433564226 ข้อ 2: แก้จุดค้น ไม่ลดเทสต์)
    fids = list(dict.fromkeys(re.findall(rf'/t1b/runs/{rid}/(?:findings|compare)/([0-9a-f]+)', q.text)))
    assert fids, "ไม่พบ finding ในคิวสังเคราะห์"
    detail = client.get(f"/t1b/runs/{rid}/findings/{fids[0]}")
    assert detail.status_code == 200 and fids[0] in detail.text, \
        "หน้ารายละเอียด finding (sink เดิม) เปิดไม่ได้ — ไม่ยิง payload ใส่หน้าที่ไม่ได้ทดสอบ"
    yield client, rid, fids[0]
    client.__exit__(None, None, None)


@pytest.mark.parametrize("payload", PAYLOADS, ids=[f"p{i}" for i in range(len(PAYLOADS))])
@pytest.mark.parametrize("param", ["page", "per_page"])
def test_finding_detail_reflected_pagination_cannot_break_attribute(world, payload, param):
    """จุดที่ ZAP 10031 ชี้: /t1b/runs/{rid}/findings/{fid}?page=&per_page="""
    client, rid, fid = world
    r = client.get(f"/t1b/runs/{rid}/findings/{fid}", params={param: payload,
                                                            "per_page" if param == "page" else "page": "1"})
    _check(r, f"detail {param}={payload!r}")
    assert r.status_code in (200, 400), r.status_code   # ค่าไม่ใช่ตัวเลข ⇒ 400 ไม่ใช่ 500


@pytest.mark.parametrize("payload", PAYLOADS, ids=[f"p{i}" for i in range(len(PAYLOADS))])
@pytest.mark.parametrize("param", ["q", "flag", "ftype", "cat", "status", "only_review"])
def test_queue_filters_cannot_break_attribute(world, payload, param):
    """ตัวกรองของคิวสะท้อนกลับเข้า value= ของ input/hidden และ option — ต้องถูก escape ครบ"""
    client, rid, _ = world
    r = client.get(f"/t1b/runs/{rid}/queue", params={param: payload})
    _check(r, f"queue {param}={payload!r}")


@pytest.mark.parametrize("payload", PAYLOADS[:4], ids=["p0", "p1", "p2", "p3"])
def test_queue_pagination_non_int_fails_safely(world, payload):
    client, rid, _ = world
    r = client.get(f"/t1b/runs/{rid}/queue", params={"page_no": payload})
    assert r.status_code in (200, 400), r.status_code
    _check(r, "queue page_no")
    assert "Traceback" not in r.text and '"input"' not in r.text   # ไม่สะท้อนค่าดิบใน JSON 422


@pytest.mark.parametrize("path,param", [
    ("/evidence/compare", "run"), ("/evidence/compare", "map"),
    ("/queue", "q"), ("/t1b/runs", "q"),
])
@pytest.mark.parametrize("payload", PAYLOADS[:5], ids=["p0", "p1", "p2", "p3", "p4"])
def test_other_query_reflection_points_are_safe(world, path, param, payload):
    client, _, _ = world
    r = client.get(path, params={param: payload})
    _check(r, f"{path} {param}")


def test_markupsafe_escapes_both_quote_styles():
    """หลักฐานว่า autoescape ส่วนกลางครอบ attribute context: escape ทั้ง " และ ' (ไม่ใช่แค่ < >)"""
    from markupsafe import escape
    assert str(escape('a"b\'c<d>e&f')) == "a&#34;b&#39;c&lt;d&gt;e&amp;f"


def test_sinks_still_reflect_so_payload_tests_are_real(world):
    """ตัวควบคุม (Bo REVIEW #42 6433564226 ข้อ 2): เทสต์ payload มีความหมายเมื่อหน้ายังสะท้อนค่าที่ส่ง —
    q · page · per_page · page_no ต้องสะท้อนค่าธรรมดากลับ (sink ยังอยู่) · ตัวกรองแบบรายการ (flag/ftype/cat/status/
    only_review) ต้อง **ไม่** สะท้อนค่าที่ไม่อยู่ในรายการ (ปลอดภัยเพราะคัดค่า ไม่ใช่เพราะเทสต์ไม่ได้ยิง)"""
    client, rid, fid = world
    mark = "zqrefl7731"
    assert mark in client.get(f"/t1b/runs/{rid}/queue", params={"q": mark}).text
    for p in ("page", "per_page"):
        assert 'value="37"' in client.get(f"/t1b/runs/{rid}/findings/{fid}", params={p: "37"}).text or \
            "=37" in client.get(f"/t1b/runs/{rid}/findings/{fid}", params={p: "37"}).text, p
    assert "37" in client.get(f"/t1b/runs/{rid}/queue", params={"page_no": "37"}).text
    for p in ("flag", "ftype", "cat", "status", "only_review"):
        assert mark not in client.get(f"/t1b/runs/{rid}/queue", params={p: mark}).text, p
