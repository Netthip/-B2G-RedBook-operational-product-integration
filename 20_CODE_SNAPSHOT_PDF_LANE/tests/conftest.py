# -*- coding: utf-8 -*-
"""ค่าตั้งร่วมของชุดทดสอบ

สำคัญ: ตั้ง REDBOOK_DATA_DIR ก่อน import แพ็กเกจ redbook เสมอ
เพื่อไม่ให้ชุดทดสอบไปแตะฐานข้อมูลหรือไฟล์อัปโหลดของงานจริง
"""
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))   # ตัวช่วยของชุดทดสอบ

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="redbook_test_"))
os.environ["REDBOOK_DATA_DIR"] = str(_TEST_DATA_DIR)
# TestClient ส่งหัว Host เป็น "testserver" — ต้องอยู่ในรายการอนุญาต (ด่านกัน DNS rebinding · #23)
os.environ.setdefault("REDBOOK_ALLOWED_HOSTS", "testserver")
# รายชื่อชุดประเมินจริงของเครื่อง (~/.redbook/eval_guard.json) ต้องไม่มีผลกับเทสต์ — ชี้ไปไฟล์ที่ไม่มีอยู่ ·
# เทสต์ของด่านตั้งไฟล์สังเคราะห์เองผ่าน fixture ``guard`` (#44 G4)
os.environ["REDBOOK_EVAL_GUARD"] = str(_TEST_DATA_DIR / "eval_guard_absent.json")

import pytest  # noqa: E402

from redbook import config  # noqa: E402
from redbook.storage.db import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_data_dir():
    config.ensure_dirs()
    init_db()
    yield


@pytest.fixture()
def fresh_db(tmp_path):
    """ฐานข้อมูลเปล่าแยกต่อหนึ่งการทดสอบ"""
    db_path = tmp_path / "t.sqlite3"
    init_db(db_path)
    return db_path


@pytest.fixture()
def xlsx_factory(tmp_path):
    """สร้างไฟล์ Excel สำหรับใช้เป็น fixture ของการทดสอบเท่านั้น

    ไฟล์เหล่านี้อยู่ในโฟลเดอร์ชั่วคราวของ pytest ไม่เข้าสู่คลังไฟล์ของระบบจริง
    และไม่ปรากฏในผลตรวจใด
    """
    import openpyxl

    def make(name="t.xlsx", rows=None, sheet="Sheet1"):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet
        for row in (rows or [["หัวข้อ", "จำนวน"], ["ก", 1], ["ข", 2]]):
            ws.append(row)
        path = tmp_path / name
        wb.save(path)
        wb.close()
        return path

    return make

# ══════════════════════════════════════════════════════════════════════════════
#  G — private real-data integration tests (คำสั่งกิ๊ฟ 7 ก.ย.)
# ══════════════════════════════════════════════════════════════════════════════
#
# ชุดทดสอบ 7 ไฟล์นี้อ่านสมุดงานจริงจาก repo พี่น้อง ``redbook-verify-data``
# (นอก git) · บนเครื่องที่ไม่มีข้อมูล ต้องรายงาน
# ``SKIPPED: PRIVATE DATASET NOT AVAILABLE`` อย่างชัดเจน — **ห้ามนับ skip เป็น pass**
# และห้ามทำให้ยอดรวม "ผ่านทั้งหมด" ชวนเข้าใจผิด · ดู scripts/test_report.py

PRIVATE_DATA_TEST_FILES = frozenset({
    "test_t1b_extract.py", "test_t1b_rollup.py", "test_t1b_identity_gate.py",
    "test_t1b_matching_compare.py", "test_t1b_adapter_inspect.py",
    "test_t1b_shadow_blockers.py", "test_t1b_table_boundary.py",
})
PRIVATE_SKIP_REASON = "PRIVATE DATASET NOT AVAILABLE"


def _private_source_dir():
    raw = os.environ.get("REDBOOK_T1B_SOURCE_DIR")
    if raw:
        return Path(raw)
    return (PROJECT_ROOT.parent / "redbook-verify-data" / "sources" / "public"
            / "ao_workbook")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "private_data: ต้องใช้ชุดข้อมูลจริงนอก git (skip ถ้าไม่มี)")


def pytest_collection_modifyitems(config, items):
    available = _private_source_dir().is_dir()
    marker = pytest.mark.private_data
    skip = pytest.mark.skip(reason=PRIVATE_SKIP_REASON)
    for item in items:
        if Path(str(item.fspath)).name in PRIVATE_DATA_TEST_FILES:
            item.add_marker(marker)
            if not available:
                item.add_marker(skip)
