# -*- coding: utf-8 -*-
"""G3 (#14) — ป้ายแถวหลายบรรทัด

🔴 ส่วนสังเคราะห์: **SYNTHETIC TEST FIXTURE** สร้างจากโค้ด ชื่อ/ยอดแต่งขึ้นทั้งหมด

หลักฐานที่พบ (แฟ้มพัฒนา คู่ข้ามปี): ป้ายเดียวกันขึ้นบรรทัดคนละตำแหน่ง ⇒
``normalize_label`` ได้ช่องว่างฝั่งหนึ่งแต่ไม่ได้อีกฝั่ง ⇒ รายงานเป็น "ลบ + เพิ่ม"
ทั้งที่รายการยังอยู่

ทางแก้: ขั้นสำรองของการจับคู่ (คีย์ไม่เปลี่ยน) · หนึ่งต่อหนึ่งเท่านั้น · ติดธงให้คนตรวจ

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import openpyxl
import pytest

from redbook.adapters.ao_workbook import AOWorkbookAdapter
from redbook.t1b.compare import (
    F_AMOUNT_DECREASED,
    F_ROW_ADDED,
    F_ROW_REMOVED,
    FLAG_LABEL_MATCHED_AFTER_JOINING_LINE_BREAKS,
    compare,
)
from redbook.t1b.keys import KEY_VERSION
from redbook.t1b.matching import VIA_LINE_BREAK_JOINED, match_records
from redbook.t1b.normalize import join_line_breaks, normalize_label
from test_t1b_extract import SOURCE_DIR, needs_sources

ITEM = "ค่าใช้จ่ายในการพัฒนาระบบทดสอบเพื่อสนับสนุนการดำเนินงาน"


@pytest.mark.parametrize("a, b", [
    (f"{ITEM[:12]}\n{ITEM[12:]}", ITEM),
    (f"{ITEM[:12]}\n{ITEM[12:]}", f"{ITEM[:30]}\n{ITEM[30:]}"),
    (f"{ITEM[:12]} \r\n {ITEM[12:]}", ITEM),
])
def test_join_line_breaks_equates_wrap_variants(a, b):
    assert join_line_breaks(a) == join_line_breaks(b)
    assert normalize_label(a) != normalize_label(b) or a == b


def test_join_line_breaks_keeps_real_differences():
    assert join_line_breaks(ITEM) != join_line_breaks(ITEM + "เพิ่มเติม")
    assert join_line_breaks(None) == ""


def test_key_spec_is_not_changed():
    assert KEY_VERSION == "t1b-key-0.2.0"


def build(tmp_path, name, labels, values=None):
    values = values or {}
    wb = openpyxl.Workbook()
    cover = wb.active
    cover.title = "ปก"
    cover["A2"], cover["A3"], cover["A5"] = "กระทรวงทดสอบ", "หน่วยงานทดสอบ", "ปี 2570"
    ws = wb.create_sheet("สรุป")
    ws["A1"] = "6. สรุปงบประมาณทดสอบ"
    ws["E3"] = "หน่วย : ล้านบาท"
    ws["A4"] = "แผนงาน"
    for col, text in zip("BCDE", ("งบบุคลากร", "งบดำเนินงาน", "งบลงทุน", "รวม")):
        ws[f"{col}4"] = text
    for r, label in enumerate(labels, 5):
        ws[f"A{r}"] = label
        for col in "BCDE":
            ws[f"{col}{r}"] = values.get((r, col), 10.0)
    path = tmp_path / name
    wb.save(path)
    wb.close()
    return path


def pair(tmp_path, a_labels, b_labels, b_values=None):
    ad = AOWorkbookAdapter()
    A = [e.canonical_record for e in ad.extract(build(tmp_path, "XL_FY2570_draft-bill_99999_A.xlsx", a_labels))]
    B = [e.canonical_record for e in ad.extract(build(tmp_path, "XL_FY2570_draft-bill_99999_B.xlsx", b_labels, b_values))]
    m = match_records(A, B)
    assert m.accounted() == len(A) + len(B)
    return m, compare(m)


def test_wrap_variant_becomes_one_flagged_pair_not_removed_plus_added(tmp_path):
    m, res = pair(tmp_path, ["รวมทั้งสิ้น", f"{ITEM[:12]}\n{ITEM[12:]}"],
                  ["รวมทั้งสิ้น", ITEM], b_values={(6, "C"): 5.0})
    via = [p for p in m.matched if p.via == VIA_LINE_BREAK_JOINED]
    assert len(via) == 4                        # 4 คอลัมน์หมวดของแถวนั้น
    assert not [f for f in res.findings if f.finding_type in (F_ROW_ADDED, F_ROW_REMOVED)]
    dec = [f for f in res.findings if f.finding_type == F_AMOUNT_DECREASED]
    assert len(dec) == 1 and dec[0].baseline_location.cell == "C6"
    flagged = [f for f in res.findings
               if FLAG_LABEL_MATCHED_AFTER_JOINING_LINE_BREAKS in f.flags]
    assert len(flagged) == 4 and all(f.requires_human_decision for f in flagged)
    assert all("\\n" in f.detail or "\n" in f.detail for f in flagged), \
        "ต้องเห็นป้ายดิบทั้งสองฝั่ง"


def test_exact_matches_carry_no_flag(tmp_path):
    m, res = pair(tmp_path, ["รวมทั้งสิ้น", ITEM], ["รวมทั้งสิ้น", ITEM])
    assert all(p.via == "" for p in m.matched)
    assert not any(FLAG_LABEL_MATCHED_AFTER_JOINING_LINE_BREAKS in f.flags for f in res.findings)


def test_many_to_one_is_left_unmatched(tmp_path):
    """สองแถวฝั่งตั้งต้นต่างกันแค่การขึ้นบรรทัด ⇒ ไม่รู้ว่าแถวไหนคู่ใคร ⇒ ไม่จับ"""
    m, res = pair(tmp_path,
                  ["รวมทั้งสิ้น", f"{ITEM[:12]}\n{ITEM[12:]}", f"{ITEM[:30]}\n{ITEM[30:]}"],
                  ["รวมทั้งสิ้น", ITEM])
    assert not [p for p in m.matched if p.via]


def test_different_text_is_never_joined(tmp_path):
    m, _ = pair(tmp_path, ["รวมทั้งสิ้น", f"{ITEM[:12]}\n{ITEM[12:]}"],
                ["รวมทั้งสิ้น", ITEM + "เพิ่มเติม"])
    assert not [p for p in m.matched if p.via]


def test_long_labels_are_not_truncated_in_the_key(tmp_path):
    long_label = ITEM * 6
    ad = AOWorkbookAdapter()
    rs = [e.canonical_record for e in ad.extract(
        build(tmp_path, "XL_FY2570_draft-bill_99999_L.xlsx", ["รวมทั้งสิ้น", long_label]))]
    assert any(r.key.row_label_norm == long_label for r in rs)


@needs_sources
def test_development_cross_year_pair_recovers_wrap_variants():
    """หลักฐานต้นเรื่องอยู่ในคู่นี้ — ต้องมีคู่ขั้นสำรองอย่างน้อยหนึ่งคู่ และทุกคู่ต่างกันแค่การขึ้นบรรทัด"""
    ad = AOWorkbookAdapter()
    A = [e.canonical_record for e in ad.extract(SOURCE_DIR / "XL_FY2569_draft-bill_21016_NVI.xlsx")]
    B = [e.canonical_record for e in ad.extract(SOURCE_DIR / "XL_FY2570_draft-bill_21016_NVI.xlsx")]
    m = match_records(A, B)
    via = [p for p in m.matched if p.via == VIA_LINE_BREAK_JOINED]
    assert via
    for p in via:
        assert join_line_breaks(p.baseline.raw_label) == join_line_breaks(p.current.raw_label)
        assert normalize_label(p.baseline.raw_label) != normalize_label(p.current.raw_label)


def test_records_without_text_labels_are_never_joined(tmp_path):
    """ป้ายดิบว่างสองฝั่งต้องไม่ถูกถือว่า "ตรงกัน" (บั๊กที่พบระหว่างทำ G3)"""
    from dataclasses import replace as _r
    m, _ = pair(tmp_path, ["รวมทั้งสิ้น", "แถวเดิม"], ["รวมทั้งสิ้น", "แถวใหม่"])
    stripped = match_records([_r(r, raw_label=None) for r in m.baseline_only],
                             [_r(r, raw_label=None) for r in m.current_only])
    assert not stripped.matched


def test_labels_without_any_line_break_are_not_handled_by_this_step(tmp_path):
    m, _ = pair(tmp_path, ["รวมทั้งสิ้น", "ค่าใช้จ่าย  ทดสอบ"], ["รวมทั้งสิ้น", "ค่าใช้จ่ายทดสอบ"])
    assert not [p for p in m.matched if p.via]
