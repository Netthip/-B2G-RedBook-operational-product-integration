# -*- coding: utf-8 -*-
"""ทดสอบชั้น presentation ของแบบฟอร์ม Human Review รุ่น 1.2.0

ทดสอบด้วยผลการรันสังเคราะห์ในหน่วยทดสอบ (ไม่พึ่งไฟล์ใน `.data/`)
เพื่อกันการเปลี่ยนโครงหน้าที่จะทำให้ผลตรวจหรือ Audit Trail เพี้ยน
"""
from pathlib import Path

import openpyxl
import pytest

from reviewpack import review_layout_v2 as L
from reviewpack.build_review_v2 import rows_for_hash
from reviewpack.migrate_answers import canonical_content_hash, read_old_answers
from reviewpack.review_writer_v2 import COL_INDEX, write_workbook


class _FakeReader:
    """แทนไฟล์ต้นทาง — คืนแถวบริบทตามที่กำหนด ไม่แตะดิสก์"""

    def __init__(self, rows_by_file):
        self._rows = rows_by_file

    def rows(self, file_name, row_numbers):
        wanted = {int(r) for r in row_numbers if r}
        return {r: v for r, v in self._rows.get(file_name, {}).items() if r in wanted}

    def path_of(self, file_name):
        return None


def _src_row(agency, item, amount):
    return ["21000", "กระทรวงสาธารณสุข", agency, "หน่วยงานทดสอบ",
            "งบประมาณรายจ่ายของหน่วยรับงบประมาณ", "แผนงานทดสอบ", "ผลผลิตทดสอบ",
            "กิจกรรมทดสอบ", "งบเงินอุดหนุน", "ค่าตอบแทนใช้สอยและวัสดุ",
            "รายจ่ายประจำ", item, amount]


def _finding(idx, category, amount_a, amount_b, machine_status="match", item=None):
    item = item or ("รายการทดสอบ %d" % idx)
    return {
        "category": category,
        "category_label": "ทดสอบ",
        "machine_status": machine_status,
        "match_level": "exact",
        "match_step": 1,
        "match_score": 1.0,
        "match_basis": "คีย์ผสม 9 บทบาท",
        "reason": "ทดสอบ",
        "review_status": "pending",
        "rule_set_version": "rules-t1-1.0.0",
        "unit": "บาท",
        "pct_change": None,
        "pct_note": "",
        "key": ["21011", "งบประมาณรายจ่ายของหน่วยรับงบประมาณ", "แผนงานทดสอบ",
                "ผลผลิตทดสอบ", "กิจกรรมทดสอบ", "งบเงินอุดหนุน",
                "ค่าตอบแทนใช้สอยและวัสดุ", "รายจ่ายประจำ", item],
        "amount_a": amount_a,
        "amount_b": amount_b,
        "amount_diff": (None if amount_a is None or amount_b is None
                        else amount_b - amount_a),
        "evidence_a": {"file_label": "T1-01", "file_name": "a.xlsx",
                       "sha256": "a" * 64, "sheet_name": "data",
                       "row_number": 100 + idx, "amount_cell": "M%d" % (100 + idx)},
        "evidence_b": {"file_label": "T1-02", "file_name": "b.xlsx",
                       "sha256": "b" * 64, "sheet_name": "data",
                       "row_number": 200 + idx, "amount_cell": "M%d" % (200 + idx)},
    }


@pytest.fixture
def built(tmp_path):
    findings = [
        _finding(0, "C3", 1000, 1000),
        _finding(1, "C1", 5000, 4000),
        _finding(2, "C2", 2000, 2500),
    ]
    run = {"findings": findings,
           "files": {"a": {"name": "a.xlsx"}, "b": {"name": "b.xlsx"}},
           "versions": {"engine": "t1-engine-1.0.0"}}
    reader = _FakeReader({
        "a.xlsx": {100: _src_row("21011", "รายการทดสอบ 0", 1000),
                   101: _src_row("21011", "รายการทดสอบ 1", 5000),
                   102: _src_row("21011", "รายการทดสอบ 2", 2000)},
        "b.xlsx": {200: _src_row("21011", "รายการทดสอบ 0", 1000),
                   201: _src_row("21011", "รายการทดสอบ 1", 4000),
                   202: _src_row("21011", "รายการทดสอบ 2", 2500)},
    })
    records = L.build_records(run, reader)
    meta = {"versions": "engine=t1-engine-1.0.0", "generated_at": "2026-08-28T00:00:00",
            "reviewpack_version": L.REVIEWPACK_VERSION_V2,
            "canonical_content_hash": "x"}
    path = tmp_path / "form.xlsx"
    write_workbook(path, records, meta, {})
    return path, records


def _review(path):
    wb = openpyxl.load_workbook(path)
    return wb, wb["Review"]


# ------------------------------------------------------- โครงและความครบถ้วน
def test_sheets_and_row_count(built):
    path, records = built
    wb, ws = _review(path)
    for name in ("วิธีตรวจ", "Review", "Evidence Preview", "ตำแหน่งตรวจสอบต้นทาง",
                 "Technical Details", "ตัวเลือก"):
        assert name in wb.sheetnames
    assert ws.max_row - L.HEADER_ROW == len(records) == 3


def test_finding_ids_present_and_unique(built):
    path, records = built
    _, ws = _review(path)
    ids = [ws.cell(row=r, column=COL_INDEX["sample_id"]).value
           for r in range(L.HEADER_ROW + 1, ws.max_row + 1)]
    assert ids == ["P-001", "P-002", "P-003"]
    assert len(set(ids)) == len(ids)
    refs = [r["finding_ref"] for r in records]
    assert len(set(refs)) == len(refs)


def test_no_merged_cells_in_data_area(built):
    """merge ได้เฉพาะแถบหัวเรื่องเหนือหัวตาราง — ในตารางข้อมูลห้ามมีเด็ดขาด"""
    path, _ = built
    _, ws = _review(path)
    for rng in ws.merged_cells.ranges:
        assert rng.max_row < L.HEADER_ROW, "พบ merge cell ในตารางข้อมูล: %s" % rng


def test_hierarchy_value_in_every_row(built):
    """sort/filter แล้วบริบทต้องไม่หาย — ทุกแถวต้องมีค่าลำดับชั้นครบ"""
    path, _ = built
    _, ws = _review(path)
    for r in range(L.HEADER_ROW + 1, ws.max_row + 1):
        for role, _label in L.KEY_ROLES:
            key = "agency_display" if role == "agency_code" else role
            if key in COL_INDEX:
                v = ws.cell(row=r, column=COL_INDEX[key]).value
                assert v not in (None, ""), "แถว %d ขาดค่า %s" % (r, key)


def test_reviewer_fields_blank_on_generation(built):
    path, _ = built
    _, ws = _review(path)
    for r in range(L.HEADER_ROW + 1, ws.max_row + 1):
        for field in L.REVIEWER_FIELDS:
            assert ws.cell(row=r, column=COL_INDEX[field]).value in (None, "")


def test_no_supplementary_content(built):
    path, _ = built
    wb, _ = _review(path)
    for sheet in wb.sheetnames:
        for row in wb[sheet].iter_rows(values_only=True):
            for v in row:
                if isinstance(v, str):
                    assert "SUPPLEMENTARY" not in v.upper()


def test_only_hyperlink_formulas(built):
    """ห้ามมีสูตรที่แก้ค่าผลตรวจ — อนุญาตเฉพาะ HYPERLINK ซึ่งเป็นการนำทาง"""
    path, _ = built
    wb, _ = _review(path)
    for sheet in wb.sheetnames:
        for row in wb[sheet].iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    assert c.value.startswith("=HYPERLINK("), c.value


# ------------------------------------------------------- สามแกนต้องไม่ปนกัน
def test_three_axes_use_distinct_visual_languages(built):
    path, _ = built
    _, ws = _review(path)
    r = L.HEADER_ROW + 2                      # แถว C1 = วงเงินลดลง
    match_cell = ws.cell(row=r, column=COL_INDEX["matching_status"])
    dir_cell = ws.cell(row=r, column=COL_INDEX["direction"])
    # แกน 1 ใช้พื้นขาว + สีตัวอักษร · แกน 2 ใช้สีพื้นหลัง
    assert match_cell.fill.fgColor.rgb.endswith("FFFFFF")
    assert dir_cell.fill.fgColor.rgb.endswith(L.DIR_DOWN[1])
    assert match_cell.fill.fgColor.rgb != dir_cell.fill.fgColor.rgb
    # แกน 3 ไม่ใช้สีคงที่ แต่เป็น conditional formatting โทนน้ำเงิน/ม่วง
    vcol = openpyxl.utils.get_column_letter(COL_INDEX["reviewer_verdict"])
    rules = [rule for rng, rules_ in ws.conditional_formatting._cf_rules.items()
             for rule in rules_ if vcol in str(rng.sqref)]
    assert len(rules) == len(L.VERDICT_CHOICES)
    verdict_fills = {f.upper() for f, _, _, _ in L.VERDICT_STYLE.values()}
    money_fills = {L.DIR_DOWN[1], L.DIR_UP[1], L.DIR_SAME[1], L.DIR_UNKNOWN[1]}
    assert not (verdict_fills & {m.upper() for m in money_fills})


@pytest.mark.parametrize("a,b,expected", [
    (100, 90, L.DIR_DOWN), (100, 110, L.DIR_UP), (100, 100, L.DIR_SAME),
    (None, 100, L.DIR_UNKNOWN), (100, None, L.DIR_UNKNOWN),
])
def test_change_direction_mapping(a, b, expected):
    assert L.change_direction(a, b) == expected


@pytest.mark.parametrize("category,status,expected", [
    ("C3", "match", L.MATCH_OK),
    ("C1", "diff_found", L.MATCH_OK),        # เงินต่าง ≠ จับคู่ไม่ได้ — คนละแกน
    ("C4", "diff_found", L.MATCH_NO),
    ("C5", "diff_found", L.MATCH_NO),
    ("C6", "needs_human", L.MATCH_PENDING),
    ("C7", "needs_human", L.MATCH_PENDING),
    ("SC1", "needs_human", L.MATCH_SCHEMA),
])
def test_matching_status_mapping(category, status, expected):
    assert L.matching_status({"category": category, "machine_status": status}) == expected


def test_matching_status_never_says_pass_or_fail():
    for label, _ in (L.MATCH_OK, L.MATCH_NO, L.MATCH_PENDING, L.MATCH_SCHEMA):
        assert "ผ่าน" not in label
    assert "ไม่ได้ตัดสินว่ารายการหรือเอกสารผิด" in L.MATCHING_NOTE


# ------------------------------------------------------- ค่าต้องไม่เปลี่ยน
def test_values_match_frozen_run(built):
    path, records = built
    wb, ws = _review(path)
    tech = wb["Technical Details"]
    tech_hdr = {c.value: c.column for c in tech[4] if c.value}
    for i, rec in enumerate(records):
        r = L.HEADER_ROW + 1 + i
        assert ws.cell(row=r, column=COL_INDEX["amount_a"]).value == rec["amount_a"]
        assert ws.cell(row=r, column=COL_INDEX["amount_b"]).value == rec["amount_b"]
        assert ws.cell(row=r, column=COL_INDEX["amount_diff"]).value == rec["amount_diff"]
        tr = 4 + 1 + i
        assert tech.cell(row=tr, column=tech_hdr["หมวดผลตรวจ"]).value == rec["category"]
        assert tech.cell(row=tr, column=tech_hdr["ค่าดิบฝั่ง A (จากเซลล์)"]).value \
            == rec["raw_value_a"]
        assert tech.cell(row=tr, column=tech_hdr["SHA-256 ไฟล์ A"]).value \
            == rec["file_a_sha256"]


def test_money_number_format_is_display_only(built):
    path, records = built
    _, ws = _review(path)
    r = L.HEADER_ROW + 1
    assert ws.cell(row=r, column=COL_INDEX["amount_a"]).number_format == "#,##0"
    assert ws.cell(row=r, column=COL_INDEX["amount_a"]).value == records[0]["amount_a"]


def test_canonical_content_hash_stable_across_layout(built):
    """แฮชเนื้อหาต้องขึ้นกับผลการประเมินเท่านั้น ไม่ขึ้นกับลำดับ/รูปแบบคอลัมน์"""
    _, records = built
    h1 = canonical_content_hash(rows_for_hash(records))
    shuffled = list(reversed(records))
    assert canonical_content_hash(rows_for_hash(shuffled)) == h1
    changed = [dict(r) for r in records]
    changed[0]["amount_b"] = changed[0]["amount_b"] + 1
    assert canonical_content_hash(rows_for_hash(changed)) != h1


def test_no_data_marker_when_level_missing():
    """ระดับที่ไม่มีข้อมูลต้องเป็น — ไม่เดาและไม่เลื่อนค่าจากระดับอื่น"""
    run = {"findings": [{"category": "C3", "machine_status": "match",
                         "key": ["21011", "งบ", "แผน"], "amount_a": 1,
                         "amount_b": 1, "amount_diff": 0,
                         "evidence_a": {}, "evidence_b": {}}],
           "files": {"a": {"name": "a.xlsx"}, "b": {"name": "b.xlsx"}}}
    rec = L.build_records(run, _FakeReader({}))[0]
    assert rec["activity_name"] == L.NO_DATA
    assert rec["item_label"] == L.NO_DATA
    assert rec["count_unit"] == L.NO_DATA


def test_value_consistency_flags_text_equivalent():
    ok, note = L.value_consistency("1,987,000", 1987000)
    assert ok is False and "text-equivalent" in note
    ok2, note2 = L.value_consistency(1987000, 1987000)
    assert ok2 is True and note2 == ""


# ------------------------------------------------------- การย้ายคำตอบ
def test_migration_moves_answers_by_finding_id(built, tmp_path):
    path, records = built
    old = tmp_path / "old.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "review"
    ws.append(["ชุดทดสอบ"]); ws.append([]); ws.append([])
    ws.append(["รหัสตัวอย่าง", "คำตอบผู้วิจัย", "ความมั่นใจผู้วิจัย", "เหตุผล",
               "วันเวลาที่ตรวจ", "เปิดหลักฐาน A แล้ว", "เปิดหลักฐาน B แล้ว"])
    ws.append(["P-002", "ไม่ยืนยัน", "สูง", "ค่าไม่ตรง", "28/08/2569 10:00",
               "เปิดแล้ว", "เปิดแล้ว"])
    wb.save(old)
    wb.close()

    answers, notes, touched = read_old_answers(old)
    assert touched == ["P-002"]
    assert answers["P-002"]["reviewer_verdict"] == "ไม่ยืนยัน"

    from reviewpack.migrate_answers import apply_answers
    report = apply_answers(path, answers, notes)
    assert report["answers_moved"] == 6 and not report["answers_failed"]

    _, ws2 = _review(path)
    r = L.HEADER_ROW + 2                      # P-002 อยู่แถวที่สองของข้อมูล
    assert ws2.cell(row=r, column=COL_INDEX["sample_id"]).value == "P-002"
    assert ws2.cell(row=r, column=COL_INDEX["reviewer_verdict"]).value == "ไม่ยืนยัน"
    assert ws2.cell(row=r, column=COL_INDEX["reviewer_reason"]).value == "ค่าไม่ตรง"


def test_migration_maps_legacy_verdict_wording(tmp_path):
    """คำตอบรุ่น 1.0.0 (ถูกต้อง/ไม่ถูกต้อง/ตัดสินไม่ได้) ต้องแปลงเป็นคำปัจจุบัน"""
    old = tmp_path / "legacy.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "review"
    ws.append([]); ws.append([]); ws.append([])
    ws.append(["รหัสตัวอย่าง", "คำตัดสินผู้วิจัย"])
    ws.append(["P-001", "ถูกต้อง"])
    ws.append(["P-002", "ตัดสินไม่ได้"])
    wb.save(old)
    wb.close()
    answers, _, _ = read_old_answers(old)
    assert answers["P-001"]["reviewer_verdict"] == "ยืนยัน"
    assert answers["P-002"]["reviewer_verdict"] == "ไม่แน่ใจ"


def test_dropdown_and_schema_version_recorded(built):
    path, _ = built
    wb, ws = _review(path)
    formulas = [dv.formula1 for dv in ws.data_validations.dataValidation]
    assert any(all(v in (f or "") for v in L.VERDICT_CHOICES) for f in formulas)
    assert any("เปิดแล้ว" in (f or "") for f in formulas)
    meta_line = ws.cell(row=2, column=1).value
    assert L.REVIEW_SCHEMA_VERSION in meta_line
    assert L.REVIEWPACK_VERSION_V2 in meta_line


def test_filter_and_freeze_configured(built):
    path, _ = built
    _, ws = _review(path)
    assert ws.auto_filter.ref is not None
    assert ws.freeze_panes is not None
    # ต้อง freeze ครอบถึงคอลัมน์ชื่อรายการ เพื่อให้เลื่อนขวาแล้วยังเห็นรายการ
    frozen_row, frozen_col = openpyxl.utils.cell.coordinate_to_tuple(ws.freeze_panes)
    assert frozen_row > L.HEADER_ROW          # ตรึงแถวหัวตารางไว้
    assert frozen_col > COL_INDEX["item_label"]


def test_hyperlink_targets_are_absolute(tmp_path):
    """Excel ตีความ path สัมพัทธ์เทียบที่ตั้งของ workbook — ลิงก์หลักฐานจึงต้องเป็น absolute"""
    import re
    from reviewpack.review_layout_v2 import SourceReader, hyperlink_formula

    src = tmp_path / "sources" / "fy2569"
    src.mkdir(parents=True)
    book = src / "evidence.xlsx"
    openpyxl.Workbook().save(book)

    # เรียกด้วย path สัมพัทธ์ (แบบที่ CLI ใช้จริง) แล้วต้องได้ absolute กลับมา
    import os
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        reader = SourceReader("sources")
        resolved = reader.path_of("evidence.xlsx")
    finally:
        os.chdir(cwd)
    assert resolved is not None
    assert resolved.is_absolute(), resolved

    formula = hyperlink_formula(str(resolved), "data", "M10", "ดูหลักฐาน")
    target = re.match(r'=HYPERLINK\("\[([^\]]+)\]', formula).group(1)
    assert re.match(r"^[A-Za-z]:[\\/]", target), target


# ============================================================================
# ตรวจแบบฟอร์มจริง — รองรับหลาย schema (reviewpack 1.2.0 และ 1.3.0)
# ============================================================================
# ทดสอบระดับ integration · ข้ามอัตโนมัติถ้าไม่มีไฟล์นั้นในเครื่อง
# (ข้อมูลจริงอยู่นอก git ตาม SYS-D-03)
#
# **สาระของ assertion ต้องเท่าเดิมทุกรุ่น** — สิ่งที่ต่างกันได้คือ locator เท่านั้น
# (ชื่อคอลัมน์และป้ายแสดงผลเปลี่ยนได้ตามรุ่น แต่ตัวเลขและตรรกะสีต้องเหมือนเดิม)

_REPO = Path(__file__).resolve().parents[1]
_ONEDRIVE_ROUND1 = (Path.home() / "OneDrive" / "เรียน ป.โท" / "Red Vertify Project"
                    / "04_HUMAN_REVIEW" / "Round1")

REAL_FORMS = {
    "reviewpack-1.2.0": _REPO / ".data" / "review" / "primary"
    / "HUMAN_CHECK_SAMPLE_primary_reviewpack-1.2.0.xlsx",
    # v1.3.0 ถูกแทนด้วย v1.3.1 หลังชุดทดสอบจับได้ว่าป้ายทิศทาง 19 แถวถูกเก็บเป็นสูตร
    # ทำให้ Excel แสดง #NAME? (ไฟล์ v1.3.0 ยังเก็บไว้เป็นหลักฐาน ไม่ถูกลบหรือทับ)
    "reviewpack-1.3.1": _ONEDRIVE_ROUND1
    / "HUMAN_CHECK_SAMPLE_primary_R1_WORKING_v1.3.1.xlsx",
}

# ยอดที่บันทึกไว้ในทะเบียนชุดข้อมูล T1 สำหรับคู่ปี 2569 (ฝั่ง A · ฝั่ง B · ผลต่าง · จำนวนรายการ)
AGENCY_TOTALS = {
    "21011": (58_440_100, 58_440_100, 0, 9),
    "21016": (132_307_300, 120_959_900, -11_347_400, 12),
}
TOTAL_REDUCTION = -11_347_400
ROW_DIFFS = {"P-017": -500_000, "P-018": -10_847_400}
EXPECTED_DIRECTION_COUNTS = {"same": 19, "down": 2}

# ป้ายทิศทางที่แต่ละรุ่นใช้ — ความหมายเดียวกัน ถ้อยคำต่างกันได้
DIRECTION_LABELS = {
    "down": {"▼ วงเงินลดลง", "▼ ลดลง"},
    "up": {"▲ วงเงินเพิ่มขึ้น", "▲ เพิ่มขึ้น"},
    "same": {"＝ ไม่เปลี่ยนแปลง", "= ไม่เปลี่ยนแปลง",
             "＝ เท่าเดิม", "= เท่าเดิม"},
    "unknown": {"? ต้องตรวจหลักฐานเพิ่ม", "? ตรวจเพิ่ม", "? คำนวณไม่ได้"},
}
DIRECTION_FILLS = {
    "down": {L.DIR_DOWN[1], "FDE7E9"},
    "up": {L.DIR_UP[1], "E6F4EA"},          # 1.3.0 ใช้เฉดเขียวต่างเล็กน้อย
    "same": {L.DIR_SAME[1], "F0F1F3"},
    "unknown": {L.DIR_UNKNOWN[1], "FFF3CD"},
}


def _direction_key(amount_a, amount_b):
    """ทิศทางที่ 'ควรจะเป็น' จากค่าเงินจริง — ไม่ผูกกับ row ID หรือถ้อยคำของรุ่นใด"""
    return {L.DIR_DOWN: "down", L.DIR_UP: "up",
            L.DIR_SAME: "same", L.DIR_UNKNOWN: "unknown"}[
        L.change_direction(amount_a, amount_b)]


def _resolve_review_schema(ws):
    """หาแถวหัวตารางและ map ชื่อคอลัมน์ของรุ่นนั้นเข้าสู่ชื่อเชิงตรรกะ

    รองรับความต่างของถ้อยคำระหว่างรุ่น เช่น
    `วงเงินฝั่ง ร่าง พ.ร.บ. …` (1.2.0) กับ `จำนวนเงินตามร่าง พ.ร.บ. 2569 (บาท)` (1.3.0)
    และ `ทิศทางการเปลี่ยนแปลง` (1.2.0) กับ `ทิศทาง` (1.3.0)
    """
    header_row = None
    for r in range(1, 11):
        titles = [str(c.value) for c in ws[r] if c.value]
        if "รหัสรายการตรวจ" in titles:
            header_row = r
            break
    assert header_row, "หาแถวหัวตารางไม่พบ"

    hdr = {str(c.value): c.column for c in ws[header_row] if c.value}

    def find(pred, what):
        hits = [name for name in hdr if pred(name)]
        assert len(hits) == 1, "คอลัมน์ %s: คาดว่าเจอ 1 รายการ แต่เจอ %s" % (what, hits)
        return hdr[hits[0]]

    money = lambda n: n.startswith(("วงเงิน", "จำนวนเงิน"))       # noqa: E731
    return {
        "header_row": header_row,
        "sample_id": hdr["รหัสรายการตรวจ"],
        "agency": find(lambda n: n == "หน่วยงาน", "หน่วยงาน"),
        "amount_a": find(lambda n: money(n) and "ร่าง" in n, "จำนวนเงินฝั่งร่าง"),
        "amount_b": find(lambda n: money(n) and "ร่าง" not in n, "จำนวนเงินฝั่ง พ.ร.บ."),
        "amount_diff": find(lambda n: n.startswith("ผลต่าง"), "ผลต่าง"),
        "direction": find(lambda n: n.startswith("ทิศทาง"), "ทิศทาง"),
    }


def _open_real_form(version):
    path = REAL_FORMS[version]
    if not path.exists():
        pytest.skip("ไม่มีไฟล์ %s ในเครื่องนี้" % version)
    wb = openpyxl.load_workbook(path)
    ws = wb["Review"]
    return wb, ws, _resolve_review_schema(ws)


@pytest.mark.parametrize("version", sorted(REAL_FORMS))
def test_real_form_money_totals_match_dataset_register(version):
    """ยอดรวมรายหน่วยงานในแบบฟอร์มต้องตรงกับทะเบียนชุดข้อมูลทุกบาท"""
    wb, ws, col = _open_real_form(version)
    totals, per_row = {}, {}
    for r in range(col["header_row"] + 1, ws.max_row + 1):
        sid = ws.cell(row=r, column=col["sample_id"]).value
        if not sid:
            continue
        agency = str(ws.cell(row=r, column=col["agency"]).value).split(" ")[0]
        a = ws.cell(row=r, column=col["amount_a"]).value or 0
        b = ws.cell(row=r, column=col["amount_b"]).value or 0
        d = ws.cell(row=r, column=col["amount_diff"]).value or 0
        cur = totals.setdefault(agency, [0, 0, 0, 0])
        cur[0] += a
        cur[1] += b
        cur[2] += d
        cur[3] += 1
        per_row[sid] = d
        # ผลต่างของทุกแถวต้องเท่ากับ B − A เสมอ (ไม่ใช่ค่าที่พิมพ์มาเอง)
        assert d == b - a, (version, sid, a, b, d)
    wb.close()

    assert {k: tuple(v) for k, v in totals.items()} == AGENCY_TOTALS, (version, totals)
    assert sum(v[2] for v in totals.values()) == TOTAL_REDUCTION
    for sid, expected in ROW_DIFFS.items():
        assert per_row[sid] == expected, (version, sid, per_row[sid])
    # ผลรวมของเฉพาะรายการที่ลดลง ต้องเท่ากับยอดลดที่บันทึกไว้
    assert sum(d for d in per_row.values() if d < 0) == TOTAL_REDUCTION


@pytest.mark.parametrize("version", sorted(REAL_FORMS))
def test_real_form_direction_derived_from_amounts(version):
    """ป้ายและสีทิศทางต้อง derive จากจำนวนเงินจริงทุกแถว ไม่ใช่ hard-code ตาม row ID"""
    wb, ws, col = _open_real_form(version)
    seen = {}
    for r in range(col["header_row"] + 1, ws.max_row + 1):
        sid = ws.cell(row=r, column=col["sample_id"]).value
        if not sid:
            continue
        a = ws.cell(row=r, column=col["amount_a"]).value
        b = ws.cell(row=r, column=col["amount_b"]).value
        want = _direction_key(a, b)
        cell = ws.cell(row=r, column=col["direction"])

        # ป้ายต้องเป็นถ้อยคำที่รุ่นนั้นใช้แทนทิศทางเดียวกัน
        assert cell.value in DIRECTION_LABELS[want], (version, sid, a, b, cell.value)
        # สีพื้นต้องตรงกับทิศทางที่คำนวณจากค่าเงิน
        rgb = str(cell.fill.fgColor.rgb)
        assert any(rgb.endswith(f) for f in DIRECTION_FILLS[want]), (version, sid, rgb)
        seen[want] = seen.get(want, 0) + 1
    wb.close()

    # ต้องพบทั้งสองประเภทจริง ไม่ใช่สีเดียวทั้งตาราง
    assert seen == EXPECTED_DIRECTION_COUNTS, (version, seen)


@pytest.mark.parametrize("version", sorted(REAL_FORMS))
def test_real_form_direction_label_is_text_not_formula(version):
    """ป้ายทิศทางต้องเป็นข้อความ ไม่ใช่สูตร

    ข้อความที่ขึ้นต้นด้วย `=` จะถูก Excel ตีความเป็นสูตรและแสดง `#NAME?`
    ทำให้ผู้ตรวจไม่เห็นทิศทางเลย — เป็นข้อบกพร่องที่มองไม่เห็นจากการอ่านค่าด้วย openpyxl
    """
    wb, ws, col = _open_real_form(version)
    broken = [ws.cell(row=r, column=col["sample_id"]).value
              for r in range(col["header_row"] + 1, ws.max_row + 1)
              if ws.cell(row=r, column=col["direction"]).data_type == "f"]
    wb.close()
    assert not broken, (version, "แถวที่ป้ายทิศทางถูกเก็บเป็นสูตร", broken)


@pytest.mark.parametrize("version", sorted(REAL_FORMS))
def test_real_form_has_no_text_stored_as_formula(version):
    """ทุกชีต: ข้อความที่ถูกเก็บเป็นสูตรโดยไม่ตั้งใจต้องไม่มี"""
    import re as _re
    path = REAL_FORMS[version]
    if not path.exists():
        pytest.skip("ไม่มีไฟล์ %s ในเครื่องนี้" % version)
    valid = _re.compile(r"^=\s*[A-Z$(]", _re.I)     # สูตรจริงเริ่มด้วยฟังก์ชัน/อ้างอิง
    wb = openpyxl.load_workbook(path)
    bad = []
    for sheet in wb.sheetnames:
        for row in wb[sheet].iter_rows():
            for c in row:
                if c.data_type == "f" and not valid.match(str(c.value)):
                    bad.append((sheet, c.coordinate, str(c.value)[:40]))
    wb.close()
    assert not bad, (version, len(bad), bad[:5])
