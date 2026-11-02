# -*- coding: utf-8 -*-
"""`PROVISIONAL_LOCAL_RETENTION POLICY` — การลบงานตรวจและไฟล์ต้นฉบับ

🔴 **คำตัดสินกิ๊ฟ (7 ก.ย. 2569)** — นโยบายชั่วคราวสำหรับต้นแบบ
**ไม่ใช่นโยบายใช้งานจริงของหน่วยงาน**

* ประมวลผลบนเครื่อง local เท่านั้น
* ไฟล์จริงห้าม commit ห้าม push
* ผู้ใช้ต้องลบ project และไฟล์ต้นฉบับได้เอง
* หลังลบเหลือได้เฉพาะ audit metadata ที่ **ไม่มีเนื้อหางบประมาณ** —
  เวลา · แฮชไฟล์ · รุ่นเครื่องยนต์ · สถานะการดำเนินการ
* **ยังไม่ทำการลบอัตโนมัติ** จนกว่าจะมีหน้าจอที่ผู้ใช้เห็นชัดและทดสอบได้

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานทุกไฟล์ในชุดนี้แต่งขึ้นทั้งหมด

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import inspect
import json

import pytest
from fastapi.testclient import TestClient

from redbook.app import create_app
from redbook.storage import audit, files as filestore, repository as repo
from redbook.storage import t1b_repo
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD
from t1b_synth import build_workbook

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"
SECRET_LABEL = "รวมทั้งสิ้น"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


def _token(client):
    client.get("/projects/new")
    return client.cookies.get(CSRF_COOKIE)


@pytest.fixture()
def analysed(client, tmp_path):
    """งานตรวจที่อัปโหลดจริง วิเคราะห์จริง แล้วพร้อมให้ลบ"""
    a = build_workbook(tmp_path, filename="a.xlsx", agency="สถาบันทดสอบ",
                       cover_year=2569, section_title=TITLE)
    b = build_workbook(tmp_path, filename="b.xlsx", agency="สถาบันทดสอบ",
                       cover_year=2570, section_title=TITLE, invest=12.0)
    token = _token(client)
    r = client.post("/projects/new",
                    data={"name": "งานตรวจที่จะลบ", "mode": "year_to_year",
                          "note": "", CSRF_FIELD: token},
                    follow_redirects=False)
    pid = r.headers["location"].rsplit("/", 1)[-1]
    for side, path, year in (("A", a, "2569"), ("B", b, "2570")):
        with open(path, "rb") as fh:
            client.post(f"/projects/{pid}/upload",
                        data={"side": side, "fiscal_year": year,
                              "agency_code": "21016",
                              "agency_name": "หน่วยงานทดสอบ",
                              "doc_kind": "ทดสอบ", CSRF_FIELD: token},
                        files={"upload": (path.name, fh,
                                          "application/octet-stream")},
                        follow_redirects=False)
    r = client.post(f"/projects/{pid}/analyze", data={CSRF_FIELD: token},
                    follow_redirects=False)
    assert r.status_code == 303, r.text[:400]
    rid = r.headers["location"].rsplit("/", 1)[-1]
    stored = [f["stored_name"] for f in repo.project_files(pid).values()]
    return {"pid": pid, "rid": rid, "token": token, "stored": stored}


# ══════════════════════════════════════════════════════════════════════════════
#  D1 — หน้ายืนยันต้องบอกให้ครบก่อนลบ
# ══════════════════════════════════════════════════════════════════════════════

def test_confirm_page_lists_what_will_be_deleted(client, analysed):
    body = client.get(f"/projects/{analysed['pid']}/delete").text
    assert "สิ่งที่จะถูกลบ" in body
    assert "สิ่งที่จะยังเหลืออยู่" in body
    assert "PROVISIONAL_LOCAL_RETENTION" in body


def test_confirm_page_says_no_automatic_deletion(client, analysed):
    """นโยบายห้ามลบอัตโนมัติ — หน้าจอต้องบอกผู้ใช้ตรง ๆ"""
    body = client.get(f"/projects/{analysed['pid']}/delete").text
    assert "ไม่ลบไฟล์ให้เองโดยอัตโนมัติ" in body
    assert "ไม่ใช่นโยบายใช้งานจริงของหน่วยงาน" in body


def test_preview_counts_match_what_is_actually_there(analysed):
    p = repo.project_deletion_preview(analysed["pid"])
    assert len(p["files"]) == 2
    assert p["t1b_runs"] == 1
    assert p["t1b_findings"] == t1b_repo.count_findings(analysed["rid"])


def test_delete_requires_typing_the_confirmation_word(client, analysed):
    r = client.post(f"/projects/{analysed['pid']}/delete",
                    data={"confirm": "", CSRF_FIELD: analysed["token"]},
                    follow_redirects=False)
    assert r.status_code == 400
    assert repo.get_project(analysed["pid"]) is not None, "ห้ามลบเมื่อยังไม่ยืนยัน"


def test_delete_requires_csrf(client, analysed):
    r = client.post(f"/projects/{analysed['pid']}/delete",
                    data={"confirm": "ลบ"}, follow_redirects=False)
    assert r.status_code == 403
    assert repo.get_project(analysed["pid"]) is not None


# ══════════════════════════════════════════════════════════════════════════════
#  D2 — ลบแล้วต้องหายจริงทั้งบนดิสก์และในฐานข้อมูล
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def deleted(client, analysed):
    r = client.post(f"/projects/{analysed['pid']}/delete",
                    data={"confirm": "ลบ", CSRF_FIELD: analysed["token"]},
                    follow_redirects=False)
    assert r.status_code == 303
    return analysed


def test_source_files_are_removed_from_disk(deleted):
    for name in deleted["stored"]:
        assert not filestore.path_for(name).exists(), \
            "ไฟล์ต้นฉบับต้องหายจากเครื่อง ไม่ใช่แค่หายจากฐานข้อมูล"


def test_project_and_its_rows_are_gone(deleted):
    assert repo.get_project(deleted["pid"]) is None
    assert repo.project_files(deleted["pid"]) == {}
    assert repo.list_runs(deleted["pid"]) == []


def test_t1b_run_and_findings_are_gone(deleted):
    assert t1b_repo.get_run(deleted["rid"]) is None
    assert t1b_repo.count_findings(deleted["rid"]) == 0
    assert not [r for r in t1b_repo.list_runs()
                if r["project_id"] == deleted["pid"]]


def test_deleting_twice_is_not_an_error(client, deleted):
    r = client.post(f"/projects/{deleted['pid']}/delete",
                    data={"confirm": "ลบ", CSRF_FIELD: deleted["token"]},
                    follow_redirects=False)
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
#  D3 — สิ่งที่เหลือต้องเป็น metadata ล้วน
# ══════════════════════════════════════════════════════════════════════════════

def test_audit_records_the_deletion_with_metadata_only(deleted):
    entries = [e for e in audit.entries(object_id=deleted["pid"])
               if e["action"] == "project_deleted"]
    assert len(entries) == 1
    detail = json.loads(entries[0]["detail_json"])
    assert detail["retention_policy"] == "PROVISIONAL_LOCAL_RETENTION"
    assert detail["outcome"] == "success"
    assert detail["t1b_schema_version"] == t1b_repo.T1B_SCHEMA_VERSION
    blob = json.dumps(detail, ensure_ascii=False)
    assert "note" not in blob and "corrected_value" not in blob
    assert len(detail["file_hashes"]) == 2
    assert all(len(h) == 64 for h in detail["file_hashes"])


def test_nothing_budget_shaped_survives_anywhere_in_the_audit(deleted):
    """🔴 ข้อสำคัญที่สุดของนโยบาย — ตรวจ **ทั้ง Audit Trail** ไม่ใช่แถวเดียว"""
    blob = json.dumps([dict(e) for e in audit.entries(limit=2000)],
                      ensure_ascii=False, default=str)
    for forbidden in (SECRET_LABEL, "งบลงทุน", "งบเงินอุดหนุน", "สถาบันทดสอบ"):
        assert forbidden not in blob, f"เนื้อหางบประมาณหลงเหลือใน audit: {forbidden}"


def test_audit_trail_itself_still_verifies_after_deletion(deleted):
    """ลบข้อมูลแล้วโซ่แฮชของ Audit ต้องยังตรวจผ่าน"""
    assert audit.verify_chain()["ok"]


def test_audit_rows_cannot_be_deleted(deleted):
    """นโยบายเก็บ audit ไว้ได้เพราะลบไม่ได้จริง — ไม่ใช่เพราะตกลงกันว่าจะไม่ลบ"""
    import sqlite3

    from redbook.storage.db import connect

    conn = connect()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM audit_log")
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  D4 — ไม่มีการลบอัตโนมัติในโค้ด
# ══════════════════════════════════════════════════════════════════════════════

def test_startup_purge_only_touches_temp_upload_parts():
    """``purge_temp`` ต้องไม่แตะไฟล์ที่ผู้ใช้อัปโหลดไว้"""
    src = inspect.getsource(filestore.purge_temp)
    assert "TEMP_DIR" in src
    assert "UPLOAD_DIR" not in src


def test_no_scheduler_or_timer_deletes_user_files():
    """ต้องไม่มีตัวจับเวลาใดในแพ็กเกจที่ลบไฟล์ของผู้ใช้เอง"""
    from pathlib import Path

    package = Path(filestore.__file__).resolve().parent.parent
    banned = ("sched.scheduler", "apscheduler", "threading.Timer",
              "BackgroundScheduler")
    hits = []
    for path in package.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        text = path.read_text(encoding="utf-8")
        hits += [f"{path.name}:{b}" for b in banned if b in text]
    assert not hits, hits


def test_delete_stored_refuses_paths_outside_the_upload_folder():
    for bad in ("../secret.xlsx", "sub/dir.xlsx", r"..\..\a.xlsx"):
        with pytest.raises(filestore.UploadRejected):
            filestore.delete_stored(bad)
