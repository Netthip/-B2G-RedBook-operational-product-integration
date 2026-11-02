# -*- coding: utf-8 -*-
"""แถวที่เก็บไว้ต้องไม่ย้อนออกหน้าเว็บพร้อมเส้นทางไฟล์

🔴 `BO REVIEW COMPLETE — HANDOFFS A/B/C/D (consolidated)` · หัวข้อ B ข้อ 2 —
*"`view_from_storage()` ประกอบ `FindingView` ด้วย `str(...)` โดยไม่ผ่าน
`_text()/redact_text()` · แถวเก่าหรือแถวที่ถูก seed/import ซึ่งมี path ใน
`detail`, label หรือ location สามารถย้อนออกหน้าเว็บได้
**แม้เส้นทาง live projection จะสะอาด**"*

**ทำไมเส้นทาง live ถึงสะอาดแต่ยังรั่วได้**

``project_finding()`` เรียก ``_text()`` ทุกช่อง ⇒ รอบที่เพิ่งรันจากเครื่องยนต์สะอาด
แต่ ``view_from_storage()`` อ่านกลับจากฐานข้อมูลโดยแปลงด้วย ``str(...)`` เฉย ๆ
⇒ แถวที่ถูกเขียนไว้ **ก่อน** ชั้นกลบมีผล หรือถูก import/seed จากที่อื่น
จะไหลออกหน้าเว็บโดยไม่ผ่านด่านใดเลย

🔴 ชุดนี้จึงเขียนแถวลงฐานข้อมูล **โดยตรง** ไม่ผ่านชั้นบริการ — เพราะนั่นคือ
สภาพที่ข้อบกพร่องนี้เกิดจริง การ seed ผ่านชั้นบริการจะกลบให้ก่อนแล้ววัดอะไรไม่ได้

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from redbook import privacy
from redbook.app import create_app
from redbook.services import t1b as svc
from redbook.storage import t1b_repo
from redbook.storage.db import session

SECRET_USER = "someone"
SECRET_DIR = "โฟลเดอร์ลับ"
SECRET_FILE = "งบลับ.xlsx"

DIRTY = (
    rf"C:\Users\{SECRET_USER}\OneDrive\เรียน ป.โท\{SECRET_DIR}"
    rf"\Budget Intelligence System\{SECRET_FILE}"
)

RUN_ID = "LEAK-TEST-RUN"


def _assert_clean(blob: str, where: str):
    for secret in (SECRET_USER, SECRET_DIR, SECRET_FILE):
        assert secret not in blob, f"{where} รั่ว {secret!r}"
    assert privacy.find_absolute_paths(blob) == [], where


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def seeded(client):
    """เขียนแถวสกปรกลงฐานข้อมูลตรง ๆ — จำลองแถวเก่า/แถวที่ import มา"""
    t1b_repo.init_t1b_schema()
    loc = json.dumps({"side": "baseline", "sheet": f"ชีต {DIRTY}", "cell": "C6",
                      "row": 6, "label": DIRTY, "value": DIRTY},
                     ensure_ascii=False)
    with session() as conn:
        conn.execute("DELETE FROM t1b_findings WHERE run_id = ?", (RUN_ID,))
        conn.execute("DELETE FROM t1b_runs WHERE id = ?", (RUN_ID,))
        conn.execute(
            "INSERT INTO t1b_runs (id, project_id, started_at, finished_at, "
            "key_version, matching_version, compare_version, service_version, "
            "identity_reason, identity_verdict, identity_blocked, "
            "automatic_pairs, total_findings, requiring_review, by_type_json, "
            "by_flag_json, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (RUN_ID, "", "2026-09-06T00:00:00+00:00", "2026-09-06T00:00:00+00:00",
             "t1b-key-0.2.0", "t1b-matching-0.7.0", "t1b-compare-0.6.0",
             "t1b-service-0.1.0", "agency_identity_confirmed_from_content",
             "COMPARED", 0, 1, 1, 1, "{}", "{}", DIRTY))
        conn.execute(
            "INSERT INTO t1b_findings (id, run_id, finding_id, identity_basis, "
            "side, ordinal, finding_type, requires_review, comparison_axis, "
            "fiscal_year, budget_category, row_label, sheet_role, "
            "section_title, parent_plan, declared_unit, baseline_value, "
            "current_value, difference, baseline_table_year, "
            "current_table_year, baseline_loc_json, current_loc_json, "
            "flags_json, detail) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, RUN_ID, "leakfid0000000a", "content", "baseline",
             0, "ROW_REMOVED", 1, "FISCAL_YEAR", 2570, None,
             f"รวมทั้งสิ้น {DIRTY}", f"SECTION_05 {DIRTY}", f"หัวเรื่อง {DIRTY}",
             f"แผนงาน {DIRTY}", f"ล้านบาท {DIRTY}", "10.0", "12.0", "2.0",
             None, None, loc, "{}", "[]", f"อ่านจาก {DIRTY} ไม่สำเร็จ"))
    yield RUN_ID
    t1b_repo.delete_run(RUN_ID)


# ══════════════════════════════════════════════════════════════════════════════
#  SL1 — ชั้น projection
# ══════════════════════════════════════════════════════════════════════════════


def test_sl1_view_from_storage_redacts_every_text_field(seeded):
    view = svc.load_run(RUN_ID)
    assert view is not None
    blob = json.dumps([f.__dict__ for f in view.findings] + [view.summary.__dict__],
                      ensure_ascii=False, default=str)
    _assert_clean(blob, "view_from_storage")


def test_sl2_location_fields_are_redacted_too(seeded):
    """🔴 ตำแหน่งหลักฐานเป็นช่องที่ถูกลืมง่ายที่สุด เพราะซ้อนอยู่ใน JSON"""
    f = svc.load_run(RUN_ID).findings[0]
    assert f.baseline is not None
    _assert_clean(json.dumps(f.baseline.__dict__, ensure_ascii=False), "location")


# ══════════════════════════════════════════════════════════════════════════════
#  SL2 — หน้าเว็บทั้งสามหน้า
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("suffix", ["", "/queue", "/findings/leakfid0000000a"])
def test_sl10_no_page_serves_the_stored_path(client, seeded, suffix):
    r = client.get(f"/t1b/runs/{RUN_ID}{suffix}")
    assert r.status_code == 200, suffix
    _assert_clean(r.text, f"/t1b/runs/{{rid}}{suffix}")


def test_sl11_run_list_page_is_clean(client, seeded):
    _assert_clean(client.get("/t1b/runs").text, "/t1b/runs")
