# -*- coding: utf-8 -*-
"""T1B — การสำรวจโครงสร้างด้วย ``AOWorkbookAdapter.inspect()``

ชุดนี้แบ่งเป็นสองส่วน

* **ส่วนที่ 1 — การแยกชั้น** ทำงานเสมอ ไม่ต้องใช้ไฟล์ข้อมูล
* **ส่วนที่ 2 — ไฟล์จริง** ข้ามอัตโนมัติเมื่อไม่พบคลังข้อมูล
  (ไฟล์ข้อมูลอยู่นอก Git ตาม ``SYS-D-05``)
  ตั้งพาธด้วยตัวแปรแวดล้อม ``REDBOOK_T1B_SOURCE_DIR`` ได้

🔴 ชุดนี้ **อ่านอย่างเดียว** ไม่เขียนทับไฟล์ต้นทางใด
"""
import os
from pathlib import Path

import pytest

from redbook.adapters.ao_workbook import AOWorkbookAdapter
from redbook.datasets.kinds import DatasetKind
from redbook.t1b import (
    DOCUMENT_LEVEL_AGENCY,
    DOCUMENT_LEVEL_MINISTRY,
    SHEET_CLASS_COVER,
    SHEET_CLASS_MAIN,
    SHEET_CLASS_SUPPORTING,
)

# 🔴 คิดจากที่อยู่ของไฟล์นี้ ไม่ใช่เส้นทางตายตัวที่มีชื่อผู้ใช้
# คลังข้อมูลเป็น repo พี่น้องที่วางข้าง ๆ repo โค้ด ⇒ ได้เส้นทางเดิมทุกประการ
# ห้ามเขียนกลับเป็นเส้นทางตายตัว — ชื่อผู้ใช้จะติดขึ้น git ไปด้วย
_DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "redbook-verify-data" / "sources" / "public" / "ao_workbook"
)
SOURCE_DIR = Path(os.environ.get("REDBOOK_T1B_SOURCE_DIR", _DEFAULT_SOURCE))

FY69_AGENCY = "XL_FY2569_draft-bill_21011_HSRI.xlsx"
FY70_AGENCY = "XL_FY2570_draft-bill_21011_HSRI.xlsx"
FY69_MINISTRY = "XL_FY2569_draft-bill_21000_MOPH-summary.xlsx"

needs_sources = pytest.mark.skipif(
    not (SOURCE_DIR / FY69_AGENCY).exists(),
    reason=f"ไม่พบคลังข้อมูล T1B ที่ {SOURCE_DIR} (ไฟล์ข้อมูลอยู่นอก Git ตาม SYS-D-05)",
)


# ─────────────────────────────────────────────── ส่วนที่ 1 — การแยกชั้น
def test_adapter_rejects_flat_data_table_kind():
    """🔴 T1B adapter ต้องไม่รับชั้น T1A (``RES-D-24``)"""
    adapter = AOWorkbookAdapter()
    assert adapter.accepts(DatasetKind.OFFICIAL_AO_WORKBOOK)
    assert adapter.accepts(DatasetKind.UNCONFIRMED_LOCAL_WORKBOOK)
    assert not adapter.accepts(DatasetKind.OFFICIAL_FLAT_DATA_TABLE)
    assert not adapter.accepts(DatasetKind.OFFICIAL_MINISTRY_PDF)

    with pytest.raises(ValueError, match="ห้ามใช้ adapter ข้ามชนิดเอกสาร"):
        adapter.require_kind(DatasetKind.OFFICIAL_FLAT_DATA_TABLE)


def test_t1b_package_does_not_import_frozen_t1a_engine():
    """🔴 ชั้น T1B ต้องไม่พึ่งพาโมดูลของ T1A ที่ freeze แล้ว

    บังคับให้การแยกชั้นเป็นจริงในระดับ import ไม่ใช่แค่ข้อตกลงบนกระดาษ
    """
    import redbook.t1b as t1b

    root = Path(t1b.__file__).parent
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "from ..t1 import" not in text, path.name
        assert "from redbook.t1 import" not in text, path.name
        assert "redbook.t1." not in text.replace("redbook.t1b.", ""), path.name


def test_extract_fails_loudly_on_missing_file():
    """``extract()`` implement แล้ว (1 ก.ย. 2569) — ไฟล์ที่ไม่มีต้องล้มชัดเจน

    ต้องไม่คืนรายการว่างเงียบ ๆ เพราะผู้เรียกจะแยกไม่ออกระหว่าง
    "ไฟล์ไม่มี" กับ "ไฟล์มีแต่ไม่มีข้อมูล"
    """
    with pytest.raises((FileNotFoundError, OSError)):
        AOWorkbookAdapter().extract(Path("ไม่มีไฟล์.xlsx"))


# ─────────────────────────────────────────────── ส่วนที่ 2 — ไฟล์จริง
@needs_sources
def test_inspect_resolves_document_level_correctly():
    """🔴 แฟ้มระดับหน่วยงานต้องไม่ถูกระบุเป็นระดับกระทรวง

    ชีตปกของแฟ้มหน่วยงานเขียนว่า ``กระทรวงสาธารณสุข`` ไว้
    การจับคำว่า "กระทรวง" ลอย ๆ จะระบุระดับผิดทั้งแฟ้ม
    """
    adapter = AOWorkbookAdapter()
    assert adapter.inspect(SOURCE_DIR / FY69_AGENCY)["document_level"] == DOCUMENT_LEVEL_AGENCY
    assert adapter.inspect(SOURCE_DIR / FY70_AGENCY)["document_level"] == DOCUMENT_LEVEL_AGENCY
    assert adapter.inspect(SOURCE_DIR / FY69_MINISTRY)["document_level"] == DOCUMENT_LEVEL_MINISTRY


@needs_sources
def test_inspect_aligns_roles_across_years_despite_renamed_sheets():
    """FM-01 + FM-02 กับไฟล์จริง — ชื่อชีตต่างกันแต่บทบาทต้องตรงกัน

    **ปรับเมื่อ map 7.x (1 ก.ย. 2569)** — บทบาทของชีตแผนงานถูกยุบเป็น
    ``SECTION_07_PLAN`` แล้วใช้ **ชื่อแผนงาน** เป็นตัวระบุ (FM-12)
    จึงเทียบด้วย ``(sheet_role, section_title)`` แทนเลขข้อ

    ชีต ``Sheet7_2`` (FY2569) กับ ``Sheet7_2`` (FY2570) ชื่อเดียวกันแต่คนละแผน
    ส่วนแผน *พื้นฐานด้านการพัฒนาฯ* มีอยู่ทั้งสองปี
    """
    adapter = AOWorkbookAdapter()
    a = adapter.inspect(SOURCE_DIR / FY69_AGENCY)
    b = adapter.inspect(SOURCE_DIR / FY70_AGENCY)

    def roles(result):
        return sorted(s["sheet_role"] for s in result["sheets"] if s["sheet_role"])

    assert roles(a) == roles(b)
    assert roles(a).count("SECTION_07_PLAN") >= 2

    def plan_titles(result):
        return {
            s["section_title"] for s in result["sheets"]
            if s["sheet_role"] == "SECTION_07_PLAN" and s["section_title"]
        }

    shared = plan_titles(a) & plan_titles(b)
    assert shared, "ต้องมีแผนงานที่ปรากฏทั้งสองปี"

    def by_title(result, title):
        return next(
            s for s in result["sheets"]
            if s["sheet_role"] == "SECTION_07_PLAN" and s["section_title"] == title
        )

    title = sorted(shared)[0]
    s69, s70 = by_title(a, title), by_title(b, title)
    assert s69["plan_role"] == s70["plan_role"]


@needs_sources
def test_inspect_classifies_thai_supporting_sheet_in_real_file():
    """FM-03 กับไฟล์จริง — ชีต ``บุค`` ต้องถูกจัดเป็นชีตประกอบ"""
    sheets = AOWorkbookAdapter().inspect(SOURCE_DIR / FY69_AGENCY)["sheets"]
    by_name = {s["name_actual"]: s for s in sheets}

    assert by_name["บุค"]["sheet_class"] == SHEET_CLASS_SUPPORTING
    assert by_name["Bยุท"]["sheet_class"] == SHEET_CLASS_SUPPORTING
    assert by_name["Sheet5"]["sheet_class"] == SHEET_CLASS_MAIN
    assert by_name["Sheet123"]["sheet_class"] == SHEET_CLASS_COVER


@needs_sources
def test_inspect_reports_year_shift_between_files():
    """FM-04 กับไฟล์จริง — คอลัมน์ปีของชีตบทบาท ``5.`` เลื่อนหนึ่งปี"""
    adapter = AOWorkbookAdapter()

    def years(path):
        sheets = adapter.inspect(path)["sheets"]
        s5 = next(s for s in sheets if s["sheet_role"] == "SECTION_05")
        return sorted(s5["year_columns"])

    assert years(SOURCE_DIR / FY69_AGENCY) == [2568, 2569, 2570, 2571, 2572]
    assert years(SOURCE_DIR / FY70_AGENCY) == [2569, 2570, 2571, 2572, 2573]


@needs_sources
def test_inspect_does_not_modify_source_files():
    """🔴 ``inspect()`` ต้องไม่แตะไฟล์ต้นทาง — ตรวจด้วยแฮชก่อน/หลัง"""
    import hashlib

    path = SOURCE_DIR / FY69_AGENCY
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    AOWorkbookAdapter().inspect(path)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after
