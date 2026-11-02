# -*- coding: utf-8 -*-
"""T1B — เส้นเชื่อมระหว่าง "อัปโหลดได้" กับ "วิเคราะห์ได้"

ก่อนหน้านี้ระบบรับไฟล์ได้ และเครื่องยนต์เปรียบเทียบก็ทำงานได้ แต่ **ไม่มีเส้นทาง
ใดในเว็บที่พาไฟล์ที่ผู้ใช้อัปโหลดเข้าไปถึงเครื่องยนต์** ชุดนี้ทดสอบเส้นนั้นทั้งเส้น
ตั้งแต่ ``POST /projects/{pid}/analyze`` จนถึงแถวที่บันทึกในที่เก็บของ T1B

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานทุกไฟล์ในชุดนี้แต่งขึ้นทั้งหมด
ห้ามรายงานผลที่ได้ว่าเป็นข้อผิดพลาดในเอกสารจริง

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import inspect
import json
import re

import pytest
from fastapi.testclient import TestClient

from redbook.app import create_app
from redbook.storage import audit, t1b_repo
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD
from t1b_synth import build_workbook

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


def _token(client):
    client.get("/projects/new")
    token = client.cookies.get(CSRF_COOKIE)
    assert token
    return token


def _project(client, token, mode="year_to_year"):
    r = client.post("/projects/new",
                    data={"name": "งานตรวจเส้นเชื่อม", "mode": mode, "note": "",
                          CSRF_FIELD: token}, follow_redirects=False)
    assert r.status_code == 303
    return r.headers["location"].rsplit("/", 1)[-1]


def _upload(client, token, pid, side, path, *, year="2570", name=None):
    with open(path, "rb") as fh:
        r = client.post(f"/projects/{pid}/upload",
                        data={"side": side, "fiscal_year": year,
                              "agency_code": "21016",
                              "agency_name": "หน่วยงานทดสอบ",
                              "doc_kind": "เอกสารทดสอบ", CSRF_FIELD: token},
                        files={"upload": (name or path.name, fh,
                                          "application/octet-stream")},
                        follow_redirects=False)
    assert r.status_code == 303, r.text[:400]
    return r


def _ao_pair(tmp_path):
    """คู่สมุดงานที่ต่างกันหนึ่งจุด — ยอดงบลงทุนขยับ"""
    a = build_workbook(tmp_path, filename="ao_a.xlsx", agency="สถาบันทดสอบ",
                       cover_year=2569, section_title=TITLE, invest=10.0)
    b = build_workbook(tmp_path, filename="ao_b.xlsx", agency="สถาบันทดสอบ",
                       cover_year=2570, section_title=TITLE, invest=12.0)
    return a, b


# ══════════════════════════════════════════════════════════════════════════════
#  U1 — เส้นทางทำงานครบวง
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def completed(client, tmp_path_factory):
    """อัปโหลดจริงผ่านหน้าเว็บแล้วสั่งเปรียบเทียบ — คืน ``(pid, rid)``"""
    tmp = tmp_path_factory.mktemp("wiring_ok")
    a, b = _ao_pair(tmp)
    token = _token(client)
    pid = _project(client, token)
    _upload(client, token, pid, "A", a, year="2569")
    _upload(client, token, pid, "B", b, year="2570")
    r = client.post(f"/projects/{pid}/analyze", data={CSRF_FIELD: token},
                    follow_redirects=False)
    assert r.status_code == 303, r.text[:600]
    loc = r.headers["location"]
    assert loc.startswith("/t1b/runs/"), loc
    return pid, loc.rsplit("/", 1)[-1]


def test_analyze_persists_a_real_t1b_run(completed):
    """แถวในที่เก็บต้องมีจริง ไม่ใช่แค่หน้าเว็บตอบ 303"""
    pid, rid = completed
    row = t1b_repo.get_run(rid)
    assert row is not None, "ต้องบันทึกรอบลงที่เก็บของ T1B"
    assert row["project_id"] == pid
    assert row["total_findings"] == len(t1b_repo.list_findings(rid))
    assert t1b_repo.count_findings(rid) == row["total_findings"]


def test_analyze_run_carries_engine_versions(completed):
    """รอบที่บันทึกต้องระบุรุ่นของทุกชั้นที่ใช้ผลิตผลนั้น"""
    _, rid = completed
    row = t1b_repo.get_run(rid)
    for col in ("key_version", "matching_version", "compare_version",
                "service_version"):
        assert row[col], f"ต้องบันทึก {col}"


def test_analyze_result_is_viewable(client, completed):
    """ผลที่บันทึกต้องเปิดอ่านได้จากหน้าสรุปของ T1B"""
    _, rid = completed
    r = client.get(f"/t1b/runs/{rid}")
    assert r.status_code == 200
    assert rid in r.text


def test_analyze_detects_the_planted_difference(completed):
    """คู่ทดสอบต่างกันหนึ่งจุด ระบบต้องรายงานอย่างน้อยหนึ่งรายการ"""
    _, rid = completed
    findings = t1b_repo.list_findings(rid)
    assert findings, "สมุดงานสองฝั่งต่างกัน ต้องได้ finding อย่างน้อยหนึ่งรายการ"


def test_analyze_appears_in_audit_trail(completed):
    """ต้องมีร่องรอยว่ารันเมื่อใด — และร่องรอยนั้นต้องเป็น **ตัวเลขล้วน**"""
    _, rid = completed
    entries = [e for e in audit.entries(object_id=rid)
               if e["action"] == "t1b_run_completed"]
    assert len(entries) == 1, "ต้องมีรายการ audit หนึ่งรายการต่อหนึ่งรอบ"
    detail = entries[0]["detail_json"]
    # 🔴 audit ลบไม่ได้ตาม trigger — สิ่งที่เขียนลงไปจะอยู่ถาวร
    # จึงห้ามมีชื่อรายการหรือยอดเงินจากเอกสารอยู่ในนั้นเด็ดขาด
    assert "สถาบันทดสอบ" not in detail
    assert "รวมทั้งสิ้น" not in detail
    assert "file_a_sha256" in detail and "file_b_sha256" in detail


def test_analyze_audit_stamps_privacy_version(completed):
    """#6 ข้อ 1 — รอบใหม่ต้องระบุรุ่นนโยบายกลบข้อมูลที่ใช้ตอนรัน"""
    from redbook import privacy
    _, rid = completed
    entries = [e for e in audit.entries(object_id=rid)
               if e["action"] == "t1b_run_completed"]
    detail = entries[0]["detail_json"]
    if isinstance(detail, str):
        detail = json.loads(detail)
    assert detail["privacy_version"] == privacy.PRIVACY_VERSION


# ══════════════════════════════════════════════════════════════════════════════
#  U2 — ไฟล์ที่เปรียบเทียบไม่ได้ ต้องบอกเหตุผลโดยไม่รั่วอะไรออกไป
# ══════════════════════════════════════════════════════════════════════════════

def _analyze_expecting_failure(client, files, mode="year_to_year"):
    token = _token(client)
    pid = _project(client, token, mode)
    for side, (path, name) in zip(("A", "B"), files):
        _upload(client, token, pid, side, path, name=name)
    r = client.post(f"/projects/{pid}/analyze", data={CSRF_FIELD: token},
                    follow_redirects=False)
    return pid, r


def test_pdf_pair_is_refused_with_a_plain_reason(client, tmp_path_factory):
    """PDF ยังไม่รองรับ — ต้องบอกตรง ๆ ไม่ใช่พังเป็น 500"""
    tmp = tmp_path_factory.mktemp("wiring_pdf")
    pdf = tmp / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% synthetic fixture\n")
    pid, r = _analyze_expecting_failure(client, [(pdf, "a.pdf"), (pdf, "b.pdf")])
    assert r.status_code == 400
    assert "Excel" in r.text
    assert not [r for r in t1b_repo.list_runs() if r["project_id"] == pid]


def test_non_ao_workbook_is_refused_as_unsupported(client, xlsx_factory):
    """สมุดงานที่ไม่ใช่แฟ้ม AO ต้องถูกปฏิเสธด้วย ``UNSUPPORTED_WORKBOOK``

    🔴 ประวัติของข้อนี้ ควรอ่านก่อนแก้ — เขียนครั้งแรกว่าต้องปฏิเสธ แล้วสอบตก
    เพราะตอนนั้นเครื่องยนต์รับไว้แล้วออกมาเป็น ``UNMAPPED`` ทั้งก้อน
    จึงแก้เทสต์ให้ตรงกับพฤติกรรมจริง · ต่อมา **กิ๊ฟตัดสิน (7 ก.ย.) ว่าพฤติกรรม
    นั้นเองที่ไม่ถูกต้อง** เพราะผู้ใช้อ่านผลได้ว่าเป็นข้อมูล AO ที่ตรวจแล้ว
    ทั้งที่อาจเป็นไฟล์ผิดประเภท ⇒ ``UNMAPPED`` สงวนไว้ให้
    *แถวในแฟ้ม AO ที่ยังจับคู่ไม่ได้* เท่านั้น
    """
    plain = xlsx_factory("plain.xlsx")
    pid, r = _analyze_expecting_failure(
        client, [(plain, "a.xlsx"), (plain, "b.xlsx")])
    assert r.status_code == 400
    assert "ไม่พบโครงสร้างของเอกสารคาดแดง" in r.text
    assert not [x for x in t1b_repo.list_runs() if x["project_id"] == pid],         "ห้ามบันทึกรอบที่อ่านไฟล์ไม่ได้ให้ดูเหมือนรอบที่ตรวจแล้วไม่พบอะไร"


def test_failure_page_leaks_no_internal_detail(client, tmp_path_factory):
    """หน้าจอผิดพลาดต้องไม่มีเส้นทางไฟล์ ชื่อคลาสข้อยกเว้น หรือ traceback"""
    tmp = tmp_path_factory.mktemp("wiring_leak")
    pdf = tmp / "leak.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% synthetic fixture\n")
    _, r = _analyze_expecting_failure(client, [(pdf, "a.pdf"), (pdf, "b.pdf")])
    body = r.text
    assert "Traceback" not in body
    assert "WorkbookNotReadable" not in body
    assert not re.search(r"[A-Za-z]:[\/]{1,2}[A-Za-z]", body), "พบเส้นทางสัมบูรณ์"
    for token in ("redbook_test_", ".sqlite3", "openpyxl", "Exception"):
        assert token not in body, f"หน้าจอผิดพลาดรั่ว {token!r}"


# ══════════════════════════════════════════════════════════════════════════════
#  U3 — ด่านก่อนถึงเครื่องยนต์
# ══════════════════════════════════════════════════════════════════════════════

def test_analyze_requires_both_sides(client):
    token = _token(client)
    pid = _project(client, token)
    r = client.post(f"/projects/{pid}/analyze", data={CSRF_FIELD: token},
                    follow_redirects=False)
    assert r.status_code == 400
    assert "ฝั่ง A" in r.text


def test_analyze_requires_csrf(client, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("wiring_csrf")
    a, b = _ao_pair(tmp)
    token = _token(client)
    pid = _project(client, token)
    _upload(client, token, pid, "A", a, year="2569")
    _upload(client, token, pid, "B", b, year="2570")
    r = client.post(f"/projects/{pid}/analyze", data={}, follow_redirects=False)
    assert r.status_code == 403


def test_analyze_on_unknown_project_is_404(client):
    token = _token(client)
    r = client.post("/projects/prj_doesnotexist/analyze",
                    data={CSRF_FIELD: token}, follow_redirects=False)
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
#  U4 — ขอบของสถาปัตยกรรมยังอยู่ครบหลังต่อสาย
# ══════════════════════════════════════════════════════════════════════════════

def test_route_layer_still_does_not_import_the_engine():
    """เส้นทางเว็บต้องคุยกับเครื่องยนต์ผ่านชั้นบริการเท่านั้น"""
    import ast
    from pathlib import Path

    from redbook import app as app_module

    path = Path(app_module.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    offenders = [m for m in imported
                 if m == "t1b" or m.startswith("t1b.")
                 or ".t1b." in m or m.endswith(".t1b")]
    assert not offenders, f"ชั้น route import เครื่องยนต์ตรง ๆ: {offenders}"
    assert "t1b_service.run_from_workbooks" in inspect.getsource(app_module)


def test_analyze_route_is_separate_from_precheck():
    """T1A precheck กับ T1B analyze ต้องเป็นคนละรอบ คนละตาราง

    รวมสองอย่างเข้าด้วยกันเมื่อใด ผลของสองระเบียบวิธีจะปนกันในรายงานเดียว
    """
    from redbook import app as app_module

    src = inspect.getsource(app_module)
    assert '@app.post("/projects/{pid}/analyze")' in src
    assert '@app.post("/projects/{pid}/precheck")' in src
    precheck = src.split('@app.post("/projects/{pid}/precheck")')[1].split("@app.")[0]
    assert "t1b" not in precheck, "precheck ต้องไม่แตะสาย T1B"
