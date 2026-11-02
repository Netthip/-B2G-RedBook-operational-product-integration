# -*- coding: utf-8 -*-
"""T1B — สาม blocker ที่เหลือจาก Shadow Run 21011 รอบที่ 1

🔴 คำสั่ง Bo · 5 กันยายน 2569 — *"ดำเนินการปิดสาม blocker ที่เหลือจาก Shadow Run
ครั้งแรก โดยรักษา provenance และห้ามกรอง finding เพื่อให้ตัวเลขสวย"*

ลำดับตามตาราง ``D`` ของ ``docs/T1B_SHADOW_RUN_21011_R1_LIMITATIONS.md``
(blocker ตัวที่ 4 คือขอบเขตตารางหมวด ปิดไปแล้วที่ ``95229e9``)

===========  ==============  ==================================================
ชื่อในไฟล์นี้   ข้อจำกัดเดิม     สาระ
===========  ==============  ==================================================
``BLOCKER_A``  ``B2``          ติดป้ายปีให้ finding แกน ``BUDGET_CATEGORY``
``BLOCKER_B``  ``B1``          หัวเรื่องชีตต้องไม่ถูกเซลล์ธงแย่ง
``BLOCKER_C``  ``B3``          ยืนยันหน่วยงานจากเนื้อในแฟ้ม ไม่ใช่ชื่อไฟล์
===========  ==============  ==================================================

**ข้อห้ามที่ผูกกับคำสั่ง**

* ห้ามกรอง finding ทิ้งเพื่อให้ตัวเลขดูดี — การแก้ต้อง **ติดป้าย** ไม่ใช่ **ตัดออก**
* ห้าม hard-code ถ้อยคำ ตำแหน่งเซลล์ ชื่อชีต หรือชื่อหน่วยงานใด ๆ
* ทุก record ต้องยัง ``accounted`` ครบ — ห้าม silent drop
* raw / provenance ต้องอยู่ครบทุกชั้น

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานในไฟล์นี้สร้างขึ้นเพื่อทดสอบทั้งหมด
ห้ามรายงานผลจากชุดนี้ว่าเป็นข้อผิดพลาดที่พบในเอกสารจริง

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import os
from pathlib import Path

import pytest

from redbook.adapters.ao_workbook import AOWorkbookAdapter, _category_table_year
from redbook.t1b import CATEGORY_INVESTMENT, CATEGORY_TOTAL
from redbook.t1b.compare import (
    F_AMOUNT_UNCHANGED,
    FLAG_CATEGORY_TABLE_YEAR_DIFFERS,
    FLAG_CATEGORY_TABLE_YEAR_UNKNOWN,
    compare,
)
from redbook.t1b.keys import KEY_VERSION, PREVIOUS_KEY_VERSION, T1BKey
from redbook.t1b.matching import (
    IDENTITY_CONFLICT,
    IDENTITY_OK,
    IDENTITY_UNVERIFIED,
    check_identity,
    match_records,
)
from redbook.t1b.records import (
    CAT_YEAR_FROM_SECTION_TITLE,
    CAT_YEAR_FROM_WORKBOOK_COVER,
    ROW_KIND_UNMAPPED,
    ROW_KIND_VALUE,
    UNC_CATEGORY_TABLE_YEAR_UNRESOLVED,
    UNC_SHEET_TITLE_AMBIGUOUS,
)
from redbook.t1b.roles import (
    SHEET_CLASS_MAIN,
    SHEET_CLASS_SUPPORTING,
    classify_sheet,
    find_title,
    title_evidence,
)

# 🔴 คิดจากที่อยู่ของไฟล์นี้ ไม่ใช่เส้นทางตายตัวที่มีชื่อผู้ใช้
# คลังข้อมูลเป็น repo พี่น้องที่วางข้าง ๆ repo โค้ด ⇒ ได้เส้นทางเดิมทุกประการ
# ห้ามเขียนกลับเป็นเส้นทางตายตัว — ชื่อผู้ใช้จะติดขึ้น git ไปด้วย
_DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "redbook-verify-data" / "sources" / "public" / "ao_workbook"
)
SOURCE_DIR = Path(os.environ.get("REDBOOK_T1B_SOURCE_DIR", _DEFAULT_SOURCE))
_PROBE = SOURCE_DIR / "XL_FY2569_draft-bill_21011_HSRI.xlsx"
needs_sources = pytest.mark.skipif(
    not _PROBE.exists(),
    reason=f"ไม่พบคลังข้อมูล T1B ที่ {SOURCE_DIR} (ข้อมูลอยู่นอก Git ตาม SYS-D-05)",
)


def _records(path):
    return [e.canonical_record for e in AOWorkbookAdapter().extract(path)]


def _values(records):
    return [r for r in records if r.row_kind == ROW_KIND_VALUE]


# ══════════════════════════════════════════════════════════════════════════════
#  ตัวสร้างสมุดงานสังเคราะห์
# ══════════════════════════════════════════════════════════════════════════════

#: ข้อความธงของเครื่องมือสร้างแฟ้ม — **ตั้งใจให้เป็นคำที่ระบบไม่รู้จัก**
#: เพื่อพิสูจน์ว่าการแก้ไม่ได้ hard-code ถ้อยคำใด
TOOL_FLAG = "Ω"
#: คอลัมน์ที่ธงวางอยู่ (ฐาน 1) — ขวาของเขตข้อมูล
FLAG_COLUMN = 14


def _cover(ws, agency: str, year: int) -> None:
    """ชีตปกอย่างย่อ — ``A2`` กระทรวง · ``A3`` หน่วยงาน · มีป้ายปี"""
    ws["A2"] = "กระทรวงทดสอบ"
    ws["A3"] = agency
    ws["A5"] = f"ปี {year}"


def _category_sheet(ws, title: str) -> None:
    """ชีตที่มีตารางจำแนกตามงบรายจ่ายหนึ่งตาราง"""
    ws["A1"] = title
    ws["E2"] = "หน่วย : ล้านบาท"
    ws["A3"] = "รายการ"
    ws["C3"], ws["D3"], ws["E3"] = "งบลงทุน", "งบเงินอุดหนุน", "รวม"
    ws["A4"] = "รวมทั้งสิ้น"
    ws["C4"], ws["D4"], ws["E4"] = 10.0, 5.0, 15.0


def _build_workbook(tmp_path, *, filename, agency, cover_year, section_title):
    """สมุดงานสองชีต — ชีตปก + ชีตตารางหมวด"""
    import openpyxl

    wb = openpyxl.Workbook()
    cover = wb.active
    cover.title = "ปก"
    _cover(cover, agency, cover_year)
    _category_sheet(wb.create_sheet("หมวด"), section_title)
    path = tmp_path / filename
    wb.save(path)
    wb.close()
    return path


# ══════════════════════════════════════════════════════════════════════════════
#  BLOCKER_A — ปีบริบทของตารางแกน BUDGET_CATEGORY  (ข้อจำกัดเดิม B2)
# ══════════════════════════════════════════════════════════════════════════════


def test_a1_table_year_comes_from_section_title_when_single_year():
    """หัวเรื่องที่ระบุปีเดียว ⇒ ใช้ปีนั้น และรายงานที่มาว่า ``section_title``"""
    year, source = _category_table_year(
        "6. สรุปงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. 2570", 2569
    )
    assert year == 2570
    assert source == CAT_YEAR_FROM_SECTION_TITLE


def test_a2_table_year_falls_back_to_cover_when_title_has_no_year():
    year, source = _category_table_year("7.2 แผนงานพื้นฐาน", 2569)
    assert year == 2569
    assert source == CAT_YEAR_FROM_WORKBOOK_COVER


def test_a3_title_with_multiple_years_must_not_be_guessed():
    """🔴 ``"พ.ศ. 2568 - 2570"`` มีสองปี — **ห้ามเดา** ให้ถอยไปใช้ปีของเอกสาร"""
    year, source = _category_table_year(
        "4. เปรียบเทียบงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. 2568 - 2570", 2569
    )
    assert year == 2569
    assert source == CAT_YEAR_FROM_WORKBOOK_COVER


def test_a4_no_year_anywhere_is_flagged_not_guessed():
    assert _category_table_year("7.2 แผนงานพื้นฐาน", None) == (None, "")


def test_a5_category_record_carries_table_year_end_to_end(tmp_path):
    path = _build_workbook(
        tmp_path, filename="A5.xlsx", agency="หน่วยงานทดสอบ",
        cover_year=2570, section_title="6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570",
    )
    cats = [r for r in _values(_records(path)) if r.budget_category is not None]
    assert cats, "ต้องสกัดตารางหมวดได้"
    assert {r.category_table_fiscal_year for r in cats} == {2570}
    assert {r.category_table_year_source for r in cats} == {CAT_YEAR_FROM_SECTION_TITLE}


def test_a6_missing_table_year_reaches_human_queue(tmp_path):
    """🔴 ไม่มีปีบริบทเลย ⇒ ติดธง **และ** ต้องเข้าคิวมนุษย์ ห้ามเทียบเงียบ ๆ"""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "หมวด"
    _category_sheet(ws, "7.2 แผนงานพื้นฐานไม่มีปี")
    path = tmp_path / "A6.xlsx"
    wb.save(path)
    wb.close()

    cats = [r for r in _values(_records(path)) if r.budget_category is not None]
    assert cats
    assert all(r.category_table_fiscal_year is None for r in cats)
    assert all(UNC_CATEGORY_TABLE_YEAR_UNRESOLVED in r.uncertainty for r in cats)
    assert all(r.needs_review for r in cats)


def _category_pair(tmp_path, base_year, curr_year):
    base = _build_workbook(
        tmp_path, filename="base.xlsx", agency="หน่วยงานเดียวกัน",
        cover_year=base_year,
        section_title=f"6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. {base_year}",
    )
    curr = _build_workbook(
        tmp_path, filename="curr.xlsx", agency="หน่วยงานเดียวกัน",
        cover_year=curr_year,
        section_title=f"6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. {curr_year}",
    )
    return _records(base), _records(curr)


def test_a7_cross_year_category_finding_is_flagged_and_must_be_reviewed(tmp_path):
    """🔴 เกณฑ์หยุดทันทีข้อ 6 — ยอดเท่ากันแต่คนละปี **ต้องไม่ผ่านเงียบ ๆ**"""
    base, curr = _category_pair(tmp_path, 2569, 2570)
    result = compare(match_records(base, curr))

    flagged = [f for f in result.findings
               if FLAG_CATEGORY_TABLE_YEAR_DIFFERS in f.flags]
    assert flagged, "ตารางหมวดคนละปีต้องถูกติดธง"
    for f in flagged:
        assert f.baseline_category_table_year == 2569
        assert f.current_category_table_year == 2570
        assert f.requires_human_decision, "ธงนี้ต้องบังคับให้เข้าคิวมนุษย์"

    unchanged = [f for f in flagged if f.finding_type == F_AMOUNT_UNCHANGED]
    assert unchanged, "กรณีที่อันตรายที่สุดคือยอด 'ไม่เปลี่ยน' ข้ามปี"
    assert result.summary()["by_flag"][FLAG_CATEGORY_TABLE_YEAR_DIFFERS] == len(flagged)


def test_a8_same_year_category_pair_is_not_flagged(tmp_path):
    base, curr = _category_pair(tmp_path, 2570, 2570)
    result = compare(match_records(base, curr))

    assert FLAG_CATEGORY_TABLE_YEAR_DIFFERS not in result.summary()["by_flag"]
    same = [f for f in result.findings if f.finding_type == F_AMOUNT_UNCHANGED]
    assert same, "ปีเดียวกันต้องยังเทียบได้ตามปกติ"
    assert not any(f.requires_human_decision for f in same)


def test_a9_flagging_does_not_remove_any_finding(tmp_path):
    """🔴 คำสั่ง Bo — ห้ามกรอง finding เพื่อให้ตัวเลขสวย

    จำนวน finding ของคู่คนละปี ต้อง **ไม่น้อยกว่า** คู่ปีเดียวกันที่มีโครงสร้างเท่ากัน
    """
    dir_same = tmp_path / "s"
    dir_cross = tmp_path / "c"
    dir_same.mkdir()
    dir_cross.mkdir()
    same = compare(match_records(*_category_pair(dir_same, 2570, 2570)))
    cross = compare(match_records(*_category_pair(dir_cross, 2569, 2570)))
    assert len(cross.findings) >= len(same.findings)


def test_a10_unknown_table_year_flag_forces_review(tmp_path):
    base, curr = _category_pair(tmp_path, 2570, 2570)
    stripped = [
        r if r.category_table_fiscal_year is None
        else type(r)(**{**r.__dict__, "category_table_fiscal_year": None})
        for r in curr
    ]
    result = compare(match_records(base, stripped))
    flagged = [f for f in result.findings
               if FLAG_CATEGORY_TABLE_YEAR_UNKNOWN in f.flags]
    assert flagged, "ปีบริบทอ่านไม่ได้ต้องติดธง ไม่ใช่ถือว่าเท่ากัน"
    assert all(f.requires_human_decision for f in flagged)


# ══════════════════════════════════════════════════════════════════════════════
#  BLOCKER_B — หัวเรื่องชีตถูกเซลล์ธงแย่ง  (ข้อจำกัดเดิม B1)
# ══════════════════════════════════════════════════════════════════════════════


def _rows_with_flag_above_title(flag=TOOL_FLAG):
    """แถว 1 มีธงอยู่คอลัมน์ขวาสุด · แถว 2 คอลัมน์ A คือหัวเรื่องจริง"""
    row1 = [None] * (FLAG_COLUMN - 1) + [flag]
    return [
        row1,
        ["7. รายละเอียดงบประมาณจำแนกตามแผนงาน และ ผลผลิต/โครงการ"],
        ["7.1 แผนงานบุคลากรภาครัฐ"],
        [None],
    ]


def test_b1_title_is_not_stolen_by_flag_cell_to_the_right():
    """🔴 เดิมไล่ **แถวก่อนคอลัมน์** ⇒ ธงที่คอลัมน์ขวาของแถวบนแย่งหัวเรื่องไป"""
    title = find_title(_rows_with_flag_above_title())
    assert title == "7. รายละเอียดงบประมาณจำแนกตามแผนงาน และ ผลผลิต/โครงการ"


def test_b2_selection_is_structural_not_word_based():
    """เปลี่ยนถ้อยคำของธงเป็นอะไรก็ได้ ผลต้องเหมือนเดิม — **ไม่ hard-code คำ**"""
    for flag in ("G", "A-H", "zzz", "๙", "1"):
        title = find_title(_rows_with_flag_above_title(flag))
        assert title.startswith("7. "), f"ธง {flag!r} ไม่ควรถูกเลือกเป็นหัวเรื่อง"


def test_b3_ordinary_title_at_a1_is_unchanged():
    rows = [["6. สรุปงบประมาณ"], ["6.1 จำแนกตามลักษณะรายจ่าย"], [None], [None]]
    assert find_title(rows) == "6. สรุปงบประมาณ"


def test_b4_numbered_candidate_below_a_tool_header_must_not_win():
    """🔴 regression กันการแก้แบบง่าย ๆ ว่า *"เลือกตัวที่มีเลขข้อ"*

    ชีตประกอบที่ซ่อนอยู่ (``mask5`` ``mask6``) มีบล็อกหัวรายงานที่คอลัมน์ A
    แล้วจึงตามด้วยข้อความที่มีเลขข้อ — ถ้าเลือกตัวที่มีเลขข้อ ชีตประกอบ
    จะไหลเข้าผลหลักทันที (ดูข้อจำกัด ``B6``)
    """
    rows = [
        ["bis64rdoc001_1_all: ข้อมูล ณ Version ร่าง พ.ร.บ."],
        ["(ผู้พิมพ์รายงาน PSIT)"],
        ["5. เป้าหมายการให้บริการหน่วยงาน"],
        [None],
    ]
    assert find_title(rows).startswith("bis64rdoc001_1_all")
    ev = title_evidence(rows)
    assert ev.displaced_numbered, "ต้องบันทึกไว้ว่ามีผู้สมัครที่มีเลขข้อถูกข้าม"


def test_b5_title_evidence_reports_position_of_the_choice():
    ev = title_evidence(_rows_with_flag_above_title())
    assert (ev.chosen.row, ev.chosen.column) == (2, 1)
    assert ev.displaced_numbered == (), "หัวเรื่องที่เลือกมีเลขข้อแล้ว จึงไม่มีข้อค้าง"


def _build_hijacked_workbook(tmp_path):
    """ชีตหลักที่มีธงวางอยู่เหนือหัวเรื่องจริง — รูปแบบที่พบใน ``Sheet7_1``"""
    import openpyxl
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    cover = wb.active
    cover.title = "ปก"
    _cover(cover, "หน่วยงานทดสอบ", 2570)

    ws = wb.create_sheet("แผนงาน")
    ws[f"{get_column_letter(FLAG_COLUMN)}1"] = TOOL_FLAG
    ws["A2"] = "7.2 แผนงานพื้นฐานทดสอบ"
    ws["A3"] = "หน่วย : ล้านบาท"
    ws["A4"] = "รายการ"
    ws["C4"], ws["D4"] = "ปี 2569", "ปี 2570"
    ws["A5"] = "รวมทั้งสิ้น"
    ws["C5"], ws["D5"] = 1.0, 2.0

    path = tmp_path / "hijacked.xlsx"
    wb.save(path)
    wb.close()
    return path


def test_b6_hijacked_main_sheet_is_extracted_not_dropped(tmp_path):
    """🔴 end-to-end — ชีตหลักทั้งชีตเคยหลุดจากการตรวจด้วยเหตุเดียว"""
    records = _records(_build_hijacked_workbook(tmp_path))
    plan = [r for r in records if r.sheet_name_actual == "แผนงาน"]
    assert plan

    assert {r.sheet_class for r in plan} == {SHEET_CLASS_MAIN}
    assert all(r.key.sheet_role for r in plan)
    assert any(r.row_kind == ROW_KIND_VALUE for r in plan), \
        "ชีตหลักต้องออกเป็น record ที่เทียบได้ ไม่ใช่ UNMAPPED ทั้งชีต"


def test_b7_supporting_sheet_with_displaced_number_says_why(tmp_path):
    """ชีตที่ไม่ใช่ชีตหลักแต่มีผู้สมัครที่มีเลขข้อ ต้องบอกเหตุผลไว้ในคิว"""
    import openpyxl

    wb = openpyxl.Workbook()
    cover = wb.active
    cover.title = "ปก"
    _cover(cover, "หน่วยงานทดสอบ", 2570)

    ws = wb.create_sheet("ประกอบ")
    ws["A1"] = "bis64rdoc001_1_all: ข้อมูล ณ Version"
    ws["A2"] = "(ผู้พิมพ์รายงาน)"
    ws["A3"] = "5. เป้าหมายการให้บริการหน่วยงาน"
    ws["A4"] = "รายการ"
    path = tmp_path / "supporting.xlsx"
    wb.save(path)
    wb.close()

    rows = [r for r in _records(path) if r.sheet_name_actual == "ประกอบ"]
    assert rows
    assert {r.sheet_class for r in rows} == {SHEET_CLASS_SUPPORTING}
    assert all(UNC_SHEET_TITLE_AMBIGUOUS in r.uncertainty for r in rows)
    assert all(r.row_kind == ROW_KIND_UNMAPPED for r in rows)
    assert all(r.needs_review for r in rows)


@needs_sources
def test_b8_real_workbook_has_no_sheet_dropped_by_a_flag_cell():
    """แฟ้มจริงทั้ง 6 — ชีตที่ถูกจัดเป็นชีตประกอบ ต้องไม่ใช่เพราะธงแย่งหัวเรื่อง

    เกณฑ์: ชีตประกอบที่หัวเรื่องถูกเลือกจาก **คอลัมน์อื่นที่ไม่ใช่คอลัมน์ซ้ายสุด
    ของชีต** ⇒ เป็นรูปแบบที่ทำให้ชีตหลักหลุด
    """
    import openpyxl

    from redbook.adapters.ao_workbook import INSPECT_SCAN_ROWS
    from redbook.t1b.roles import SheetFacts

    offenders = []
    for path in sorted(SOURCE_DIR.glob("*.xlsx")):
        wb = openpyxl.load_workbook(path, data_only=True)
        for index, ws in enumerate(wb.worksheets):
            rows = [
                [c.value for c in row]
                for row in ws.iter_rows(
                    min_row=1, max_row=min(ws.max_row or 1, INSPECT_SCAN_ROWS)
                )
            ]
            ev = title_evidence(rows)
            if ev.chosen is None:
                continue
            facts = SheetFacts(
                name=ws.title, index=index, a1=ev.title, max_row=ws.max_row or 0,
                max_column=ws.max_column or 0,
                merged_count=len(ws.merged_cells.ranges),
            )
            leftmost = min(c.column for c in ev.candidates)
            if classify_sheet(facts) != SHEET_CLASS_MAIN and ev.chosen.column > leftmost:
                offenders.append((path.name, ws.title))
        wb.close()
    assert offenders == []


# ══════════════════════════════════════════════════════════════════════════════
#  BLOCKER_C — ตัวตนหน่วยงานจากเนื้อในแฟ้ม  (ข้อจำกัดเดิม B3)
# ══════════════════════════════════════════════════════════════════════════════


def test_c1_key_version_moved_and_previous_version_is_kept():
    assert KEY_VERSION == "t1b-key-0.2.0"
    assert PREVIOUS_KEY_VERSION == "t1b-key-0.1.0"


def test_c2_agency_identity_is_part_of_identity_not_comparison():
    a = T1BKey(agency_code="", document_level="agency", sheet_role="SECTION_05",
               agency_identity="หน่วยงาน ก", row_label_norm="รวมทั้งสิ้น")
    b = T1BKey(agency_code="", document_level="agency", sheet_role="SECTION_05",
               agency_identity="หน่วยงาน ข", row_label_norm="รวมทั้งสิ้น")
    assert a != b, "คนละหน่วยงานต้องมีคีย์ต่างกันแม้ agency_code จะว่างทั้งคู่"
    assert not a.matchable_with(b)


def test_c3_identity_is_read_from_content_when_filename_has_no_code(tmp_path):
    """🔴 หัวใจของ blocker — ชื่อไฟล์ไม่ตรงรูปแบบ แต่ยังยืนยันหน่วยงานได้"""
    path = _build_workbook(
        tmp_path, filename="AO_ชื่อไฟล์ที่ผู้ใช้ตั้งเอง.xlsx",
        agency="สถาบันทดสอบ", cover_year=2570,
        section_title="6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570",
    )
    records = _records(path)
    assert {r.key.agency_code for r in records} == {""}, "ชื่อไฟล์ให้รหัสไม่ได้"
    assert {r.key.agency_identity for r in records} == {"สถาบันทดสอบ"}


def test_c4_two_agencies_are_refused_before_any_match(tmp_path):
    """🔴 เดิม: รหัสว่างทั้งสองฝั่ง ⇒ คีย์เท่ากัน ⇒ จับคู่ข้ามหน่วยงานได้เงียบ ๆ"""
    a = _records(_build_workbook(
        tmp_path, filename="AO_ก.xlsx", agency="หน่วยงาน ก", cover_year=2570,
        section_title="6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"))
    b = _records(_build_workbook(
        tmp_path, filename="AO_ข.xlsx", agency="หน่วยงาน ข", cover_year=2570,
        section_title="6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"))

    check = check_identity(a, b)
    assert check.reason == IDENTITY_CONFLICT
    assert check.conflict and not check.verified

    result = match_records(a, b)
    assert result.matched == [], "ห้ามจับคู่อัตโนมัติแม้แต่คู่เดียว"
    assert result.accounted() == len(a) + len(b), "🔴 ต้องยัง accounted ครบ"
    assert result.summary()["identity_conflict"] is True


def test_c5_conflict_reason_reaches_every_finding(tmp_path):
    a = _records(_build_workbook(
        tmp_path, filename="AO_ก.xlsx", agency="หน่วยงาน ก", cover_year=2570,
        section_title="6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"))
    b = _records(_build_workbook(
        tmp_path, filename="AO_ข.xlsx", agency="หน่วยงาน ข", cover_year=2570,
        section_title="6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"))

    result = compare(match_records(a, b))
    assert result.summary()["identity_conflict"] is True
    assert result.findings
    assert all("คนละหน่วยงาน" in f.detail for f in result.findings)
    assert all(f.requires_human_decision for f in result.findings)


def test_c6_same_agency_still_matches(tmp_path):
    a = _records(_build_workbook(
        tmp_path, filename="AO_69.xlsx", agency="หน่วยงานเดียวกัน", cover_year=2569,
        section_title="6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2569"))
    b = _records(_build_workbook(
        tmp_path, filename="AO_70.xlsx", agency="หน่วยงานเดียวกัน", cover_year=2570,
        section_title="6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"))

    result = match_records(a, b)
    assert result.summary()["identity_reason"] == IDENTITY_OK
    assert result.matched, "หน่วยงานเดียวกันต้องยังจับคู่ได้ตามเดิม"


def test_c7_unreadable_identity_is_reported_not_treated_as_pass(tmp_path):
    """🔴 ``ยืนยันไม่ได้`` ต้องไม่ถูกนับเป็น ``ผ่าน``"""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "หมวด"
    _category_sheet(ws, "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570")
    blind = tmp_path / "blind.xlsx"
    wb.save(blind)
    wb.close()

    named = _build_workbook(
        tmp_path, filename="named.xlsx", agency="หน่วยงาน ก", cover_year=2570,
        section_title="6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570")

    check = check_identity(_records(blind), _records(named))
    assert check.reason == IDENTITY_UNVERIFIED
    assert not check.verified
    assert not check.conflict, "ยืนยันไม่ได้ ยังไม่ใช่ข้อขัดแย้ง — ต้องแยกสองสถานะ"


@needs_sources
def test_c8_real_workbooks_resolve_identity_from_content():
    """แฟ้มจริงทั้ง 6 ต้องอ่านตัวตนหน่วยงานจากเนื้อในแฟ้มได้ครบ"""
    seen = {}
    for path in sorted(SOURCE_DIR.glob("*.xlsx")):
        ids = {r.key.agency_identity for r in _records(path)}
        assert len(ids) == 1, f"{path.name} ให้ตัวตนหน่วยงานมากกว่าหนึ่งค่า: {ids}"
        identity = ids.pop()
        assert identity, f"{path.name} อ่านตัวตนหน่วยงานจากเนื้อในแฟ้มไม่ได้"
        seen[path.name] = identity
    assert len(set(seen.values())) >= 2, "ชุดข้อมูลต้องมีมากกว่าหนึ่งหน่วยงาน"


@needs_sources
def test_c9_real_cross_agency_pair_is_refused():
    """🔴 คู่ข้ามหน่วยงานจากแฟ้มจริง ต้องถูกปฏิเสธก่อนจับคู่"""
    a = _records(SOURCE_DIR / "XL_FY2570_draft-bill_21011_HSRI.xlsx")
    b = _records(SOURCE_DIR / "XL_FY2570_draft-bill_21016_NVI.xlsx")
    result = match_records(a, b)
    assert result.summary()["identity_conflict"] is True
    assert result.matched == []
    assert result.accounted() == len(a) + len(b)


@needs_sources
def test_c10_real_files_would_collide_without_content_identity():
    """🔴 **หลักฐานขนาดจริงของ blocker #3**

    แฟ้มในคลังถูก *ตั้งชื่อใหม่* ให้ตรงรูปแบบ ``XL_FY####_<status>_#####_``
    จึงมี ``agency_code`` ⇒ คีย์ของสองหน่วยงานต่างกันอยู่แล้ว
    **แต่ชื่อแฟ้มที่ผู้ปฏิบัติงานใช้จริงไม่ตรงรูปแบบนี้** ⇒ ``agency_code`` ว่าง
    ทั้งสองฝั่ง ซึ่งเป็นสภาพที่ Shadow Run รอบที่ 1 เจอจริง

    ทดสอบนี้จำลองสภาพนั้นโดย **ลบรหัสจากชื่อไฟล์ทิ้ง** แล้ววัดว่า

    * ถ้าไม่มี ``agency_identity`` ⇒ คีย์ของคนละหน่วยงาน **ชนกัน**
    * เมื่อมี ``agency_identity`` ⇒ ต้องไม่ชนกันแม้แต่คีย์เดียว
    """
    from dataclasses import replace

    a = [r for r in _records(SOURCE_DIR / "XL_FY2570_draft-bill_21011_HSRI.xlsx")
         if r.row_kind == ROW_KIND_VALUE]
    b = [r for r in _records(SOURCE_DIR / "XL_FY2570_draft-bill_21016_NVI.xlsx")
         if r.row_kind == ROW_KIND_VALUE]

    def blank_code(recs):
        return {replace(r.key, agency_code="") for r in recs}

    def blank_code_and_identity(recs):
        return {replace(r.key, agency_code="", agency_identity="") for r in recs}

    without = blank_code_and_identity(a) & blank_code_and_identity(b)
    assert without, "ชุดข้อมูลนี้ต้องมีคีย์ที่ชนกันได้จริง มิฉะนั้นทดสอบไม่มีความหมาย"

    with_identity = blank_code(a) & blank_code(b)
    assert with_identity == set(), (
        f"ยังชนกัน {len(with_identity)} คีย์ ทั้งที่มี agency_identity แล้ว")


# ══════════════════════════════════════════════════════════════════════════════
#  invariant ที่ต้องไม่ถอยหลังหลังปิดทั้งสาม blocker
# ══════════════════════════════════════════════════════════════════════════════


@needs_sources
def test_z1_real_pair_keeps_accounting_and_reports_year_context():
    base = _records(SOURCE_DIR / "XL_FY2569_draft-bill_21011_HSRI.xlsx")
    curr = _records(SOURCE_DIR / "XL_FY2570_draft-bill_21011_HSRI.xlsx")

    m = match_records(base, curr)
    assert m.accounted() == len(base) + len(curr), "🔴 ห้ามมี record หายเงียบ"
    assert m.summary()["identity_reason"] == IDENTITY_OK

    result = compare(m)
    cats = [f for f in result.findings if f.budget_category in
            (CATEGORY_INVESTMENT, CATEGORY_TOTAL)]
    assert cats, "ต้องยังมี finding แกนหมวดออกมา — ห้ามหายไปเพราะการติดธง"
    for f in cats:
        known = (f.baseline_category_table_year is not None
                 or f.current_category_table_year is not None)
        flagged = bool(f.flags)
        assert known or flagged, "ทุก finding แกนหมวดต้องมีปีบริบทหรือธงกำกับ"
