# -*- coding: utf-8 -*-
"""T1B — แยก "ไฟล์ผิดประเภท" ออกจาก "แถวใน AO ที่ยังจับคู่ไม่ได้"

🔴 **คำสั่งกิ๊ฟ (7 ก.ย. 2569)** — เดิมระบบรับแฟ้มอะไรก็ได้แล้วแปลงทุกแถวเป็น
``UNMAPPED`` ผู้ใช้จึงอ่านได้ว่าเป็นข้อมูล AO ที่ระบบตรวจแล้ว ทั้งที่จริงอาจเป็น
ไฟล์ผิดประเภท · ต้องแยกอย่างน้อยสี่ทาง

======================================  =====================================
สถานการณ์                                ผลลัพธ์
======================================  =====================================
เปิดไม่ได้ / เสียหาย / ชนิดไม่รองรับ        ``WORKBOOK_NOT_READABLE``
เปิดได้ ไม่พบหลักฐานว่าเป็น AO            ``UNSUPPORTED_WORKBOOK``
เป็น AO แต่บางแถวจับคู่ไม่ได้              ``UNMAPPED`` (ในผลการเทียบ)
หลักฐานไม่พอจะตัดสิน                      ``NEEDS_FILE_CLASSIFICATION``
======================================  =====================================

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานทุกไฟล์ในชุดนี้แต่งขึ้นทั้งหมด

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import openpyxl
import pytest

from redbook.services import t1b as svc
from t1b_synth import build_workbook, records

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"


@pytest.fixture()
def ao_records(tmp_path):
    return records(build_workbook(tmp_path, filename="ao.xlsx",
                                  agency="สถาบันทดสอบ", cover_year=2570,
                                  section_title=TITLE))


def _workbook(tmp_path, name, rows, sheet="Sheet1"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    for cell, value in rows:
        ws[cell] = value
    path = tmp_path / name
    wb.save(path)
    wb.close()
    return path


# ══════════════════════════════════════════════════════════════════════════════
#  C1 — สี่ทางแยก
# ══════════════════════════════════════════════════════════════════════════════

def test_real_ao_workbook_is_classified_as_ao(ao_records):
    c = svc.classify_workbook(ao_records)
    assert c.code == svc.CLS_AO
    assert c.usable
    assert c.mapped_rows > 0


def test_ordinary_workbook_is_unsupported_not_ao(tmp_path):
    """สมุดงานทั่วไป — ไม่มีทั้งแถวที่ตีความได้และสัญญาณ AO ใด ๆ"""
    path = _workbook(tmp_path, "plain.xlsx",
                     [("A1", "หัวข้อ"), ("B1", "จำนวน"),
                      ("A2", "ก"), ("B2", 1)])
    c = svc.classify_workbook(_extract(path))
    assert c.code == svc.CLS_UNSUPPORTED
    assert not c.usable
    assert c.mapped_rows == 0
    assert c.ao_signals == ()


def _extract(path):
    from redbook.adapters.ao_workbook import AOWorkbookAdapter
    return [e.canonical_record for e in AOWorkbookAdapter().extract(path)]


def test_ao_shaped_but_empty_workbook_needs_classification(tmp_path):
    """มีหัวเรื่องแบบ AO แต่ไม่มีแถวข้อมูลเลย — **ห้ามเดาไปทางใดทางหนึ่ง**

    เป็นเคสจริงที่เกิดได้ เช่นแฟ้มแม่แบบที่ยังไม่ได้กรอก
    """
    path = _workbook(tmp_path, "stub.xlsx", [("A1", TITLE)])
    c = svc.classify_workbook(_extract(path))
    assert c.code == svc.CLS_NEEDS_CLASSIFICATION
    assert not c.usable
    assert c.mapped_rows == 0
    assert c.ao_signals, "ต้องบอกได้ว่าสัญญาณอะไรทำให้ยังตัดสินไม่ได้"


def test_classification_always_explains_itself(ao_records, tmp_path):
    """ทุกผลต้องมีตัวนับที่ใช้ตัดสินติดมาด้วย ไม่ใช่รหัสลอย ๆ"""
    for recs in (ao_records, _extract(_workbook(tmp_path, "p.xlsx",
                                                [("A1", "x")]))):
        c = svc.classify_workbook(recs)
        assert c.mapped_rows + c.unmapped_rows == len(recs)
        assert c.label and c.label != c.code


# ══════════════════════════════════════════════════════════════════════════════
#  C2 — read_workbook ยกข้อยกเว้นคนละชนิดตามสาเหตุ
# ══════════════════════════════════════════════════════════════════════════════

def test_unsupported_workbook_raises_its_own_exception(tmp_path):
    path = _workbook(tmp_path, "plain2.xlsx", [("A1", "หัวข้อ"), ("A2", "ก")])
    with pytest.raises(svc.UnsupportedWorkbook) as e:
        svc.read_workbook(path)
    assert e.value.code == svc.CLS_UNSUPPORTED
    assert e.value.classification.mapped_rows == 0


def test_needs_classification_raises_its_own_exception(tmp_path):
    path = _workbook(tmp_path, "stub2.xlsx", [("A1", TITLE)])
    with pytest.raises(svc.WorkbookNeedsClassification) as e:
        svc.read_workbook(path)
    assert e.value.code == svc.CLS_NEEDS_CLASSIFICATION


def test_pdf_raises_not_readable(tmp_path):
    path = tmp_path / "x.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    with pytest.raises(svc.WorkbookNotReadable) as e:
        svc.read_workbook(path)
    assert e.value.code == svc.CLS_NOT_READABLE


def test_corrupt_workbook_raises_not_readable(tmp_path):
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"not a workbook at all")
    with pytest.raises(svc.WorkbookNotReadable) as e:
        svc.read_workbook(path)
    assert e.value.code == svc.CLS_NOT_READABLE


def test_all_rejections_share_one_base_class(tmp_path):
    """route จับคลาสเดียวได้ทุกสาเหตุ — เพิ่มสาเหตุใหม่แล้วไม่หลุดเป็น 500"""
    for cls in (svc.WorkbookNotReadable, svc.UnsupportedWorkbook,
                svc.WorkbookNeedsClassification):
        assert issubclass(cls, svc.WorkbookRejected)
        assert cls.code != svc.WorkbookRejected.code or cls is svc.WorkbookNotReadable


def test_rejection_messages_carry_no_file_path(tmp_path):
    """ข้อความที่ผู้ใช้เห็นห้ามมีเส้นทางไฟล์ แม้ข้อยกเว้นต้นทางจะมี"""
    path = tmp_path / "ชื่อไฟล์ ที่มีช่องว่าง.xlsx"
    path.write_bytes(b"broken")
    with pytest.raises(svc.WorkbookRejected) as e:
        svc.read_workbook(path)
    assert str(tmp_path) not in e.value.user_message
    assert str(tmp_path) not in e.value.detail
    assert "ชื่อไฟล์ ที่มีช่องว่าง" not in e.value.user_message


# ══════════════════════════════════════════════════════════════════════════════
#  C3 — UNMAPPED ยังคงความหมายเดิมสำหรับแฟ้ม AO จริง
# ══════════════════════════════════════════════════════════════════════════════

def test_unmapped_still_used_for_rows_inside_a_real_ao_file(tmp_path):
    """แฟ้ม AO ที่มีทั้งแถวที่ตีความได้และไม่ได้ ต้องผ่านและใช้ ``UNMAPPED``

    นี่คือความหมายเดียวที่เหลือของ ``UNMAPPED`` หลังคำสั่งกิ๊ฟ
    """
    base = records(build_workbook(tmp_path, filename="a.xlsx",
                                  agency="สถาบันทดสอบ", cover_year=2569,
                                  section_title=TITLE))
    curr = records(build_workbook(tmp_path, filename="b.xlsx",
                                  agency="สถาบันทดสอบ", cover_year=2570,
                                  section_title=TITLE, invest=12.0))
    assert svc.classify_workbook(base).code == svc.CLS_AO
    view = svc.run_from_records(base, curr, run_id="CLS-AO")
    kinds = {f.finding_type for f in view.findings}
    assert "UNMAPPED_REQUIRES_HUMAN_REVIEW" in kinds, \
        "แถวปกที่ยังไม่ map ยังต้องออกเป็น UNMAPPED ตามเดิม"
    assert view.summary.automatic_pairs > 0, "แฟ้ม AO จริงต้องจับคู่ได้จริง"
