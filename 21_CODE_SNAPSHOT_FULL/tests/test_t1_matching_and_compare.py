# -*- coding: utf-8 -*-
"""ทดสอบ G3–G4: normalization · pipeline 5 ขั้น · หมวดผล C1–C7"""
import pytest

from redbook.t1.canonical import CanonicalT1Record, EvidenceLocation
from redbook.t1.compare import (AMOUNT_TOLERANCE_BAHT, C1_AMOUNT_DECREASED,
                                C2_AMOUNT_INCREASED, C3_AMOUNT_UNCHANGED,
                                C4_ITEM_ADDED, C5_ITEM_MISSING,
                                C6_POSSIBLE_STRUCTURE_MOVE, C7_UNRESOLVED,
                                CATEGORIES_PENDING_REVIEW, classify, summarize)
from redbook.t1.matching import (COMPOSITE_KEY_ROLES, MATCH_AMBIGUOUS, MATCH_EXACT,
                                 MATCH_SUGGESTED, MATCH_UNMATCHED, composite_key,
                                 match_records)
from redbook.t1.normalize import (collapse_whitespace, normalize_name,
                                  split_leading_number, thai_to_arabic_digits)


def rec(item="รายการรายจ่ายประจำ", amount=1000, act="กิจกรรม ก", agc="21011", row=2):
    return CanonicalT1Record(
        ministry_code="21000", ministry_name="กระทรวงทดสอบ",
        agency_code=agc, agency_name="หน่วยงานทดสอบ",
        budget_group="งบประมาณรายจ่ายของหน่วยรับงบประมาณ",
        plan_name="แผนงานทดสอบ", output_name="ผลผลิตทดสอบ", activity_name=act,
        objective_category="งบดำเนินงาน", objective_subcategory="ค่าตอบแทน",
        capital_class="รายจ่ายประจำ", item_label=item,
        amount_stored=amount, amount_normalized=amount, scale_factor=1.0,
        declared_unit="บาท", unit_confidence="confirmed", row_ordinal=row - 1,
        evidence_location=EvidenceLocation(file_label="X", sheet_name="data",
                                           row_number=row, amount_cell=f"M{row}"))


# ------------------------------------------------------------ normalize
def test_normalization_rules():
    assert collapse_whitespace("  ก   ข \n ค ") == "ก ข ค"
    assert thai_to_arabic_digits("๗.๔.๑") == "7.4.1"
    assert split_leading_number("7.4.1 โครงการทดสอบ") == ("7.4.1", "โครงการทดสอบ")
    assert split_leading_number("(2) รายการ") == ("2", "รายการ")
    assert split_leading_number("ไม่มีเลขนำหน้า")[0] is None
    n = normalize_name("  ๑) ค่าหนังสือเรียน  ")
    assert n["outline_number"] == "1"
    assert n["comparable"] == "ค่าหนังสือเรียน"
    assert n["raw"] == "  ๑) ค่าหนังสือเรียน  "   # เก็บ raw เสมอ


def test_parentheses_and_punctuation_are_preserved():
    n = normalize_name("ค่าเช่า (อาคาร) ปี 2569")
    assert "(อาคาร)" in n["comparable"]


# --------------------------------------------------------------- key
def test_composite_key_has_nine_roles_and_excludes_row_ordinal():
    assert len(COMPOSITE_KEY_ROLES) == 9
    assert "row_ordinal" not in COMPOSITE_KEY_ROLES
    a = rec(row=2)
    b = rec(row=999)          # ลำดับแถวต่างกันมาก
    assert composite_key(a) == composite_key(b)


def test_key_absorbs_name_formatting_but_not_meaning():
    plain = composite_key(rec(item="ค่าหนังสือ"))
    decorated = composite_key(rec(item=" ๑)  ค่าหนังสือ "))
    assert plain == decorated          # รูปแบบต่างแต่ความหมายเดียวกัน
    assert plain != composite_key(rec(item="ค่าหนังสือเรียน"))  # คนละรายการ


# ---------------------------------------------------------- pipeline
def test_exact_match_step1():
    pairs = match_records([rec()], [rec()])
    assert len(pairs) == 1
    assert pairs[0].match_level == MATCH_EXACT and pairs[0].step == 1


def test_structure_move_is_suggested_not_auto_merged():
    a = [rec(act="กิจกรรม ก")]
    b = [rec(act="กิจกรรม ข")]
    pairs = match_records(a, b)
    p = next(x for x in pairs if x.match_level == MATCH_SUGGESTED)
    assert p.step == 3
    assert "activity_name" in p.score_basis
    assert "ต้องให้มนุษย์ยืนยัน" in p.note


def test_far_parent_difference_is_not_matched():
    """ชื่อรายการเหมือนกันแต่คนละหน่วยงานและคนละแผนงาน ต้องไม่จับคู่กัน"""
    a = [rec(agc="21011")]
    b = [CanonicalT1Record(
        ministry_code="21000", ministry_name="กระทรวงทดสอบ",
        agency_code="99999", agency_name="อีกหน่วยงาน",
        budget_group="กลุ่มอื่น", plan_name="แผนงานอื่น", output_name="ผลผลิตอื่น",
        activity_name="กิจกรรมอื่น", objective_category="งบลงทุน",
        objective_subcategory="ครุภัณฑ์", capital_class="รายจ่ายลงทุน",
        item_label="รายการรายจ่ายประจำ", amount_stored=1000, amount_normalized=1000,
        evidence_location=EvidenceLocation(row_number=2, amount_cell="M2"))]
    pairs = match_records(a, b)
    assert all(p.match_level == MATCH_UNMATCHED for p in pairs)
    assert len(pairs) == 2


def test_duplicate_key_is_ambiguous():
    pairs = match_records([rec()], [rec(amount=1000), rec(amount=1001, row=3)])
    assert any(p.match_level == MATCH_AMBIGUOUS and p.step == 5 for p in pairs)


def test_no_record_disappears_from_pipeline():
    a = [rec(item="ก"), rec(item="ข", row=3)]
    b = [rec(item="ก")]
    pairs = match_records(a, b)
    covered_a = {p.a_index for p in pairs if p.a_index is not None}
    covered_b = {p.b_index for p in pairs if p.b_index is not None}
    assert covered_a == {0, 1} and covered_b == {0}


# ------------------------------------------------------------ compare
def _classify(a, b):
    return classify(match_records(a, b), a, b)


def test_c1_c2_c3_by_amount():
    assert _classify([rec(amount=1000)], [rec(amount=900)])[0].category == C1_AMOUNT_DECREASED
    assert _classify([rec(amount=1000)], [rec(amount=1100)])[0].category == C2_AMOUNT_INCREASED
    assert _classify([rec(amount=1000)], [rec(amount=1000)])[0].category == C3_AMOUNT_UNCHANGED


def test_one_baht_difference_is_never_hidden():
    assert AMOUNT_TOLERANCE_BAHT == 0
    f = _classify([rec(amount=1000)], [rec(amount=999)])[0]
    assert f.category == C1_AMOUNT_DECREASED
    assert f.amount_diff == -1


def test_c4_c5_added_and_missing():
    assert _classify([rec(item="ก")], [])[0].category == C5_ITEM_MISSING
    assert _classify([], [rec(item="ก")])[0].category == C4_ITEM_ADDED


def test_c6_structure_move_is_pending_not_counted_as_move_or_pair():
    f = _classify([rec(act="ก")], [rec(act="ข")])[0]
    assert f.category == C6_POSSIBLE_STRUCTURE_MOVE
    assert f.machine_status == "needs_human"
    assert "ยังไม่นับเป็นการย้าย" in f.reason
    assert C6_POSSIBLE_STRUCTURE_MOVE in CATEGORIES_PENDING_REVIEW


def test_c7_for_ambiguous():
    findings = _classify([rec()], [rec(amount=1000), rec(amount=1001, row=3)])
    assert any(f.category == C7_UNRESOLVED for f in findings)


def test_percentage_uses_locked_message_when_base_is_zero():
    f = _classify([rec(amount=0)], [rec(amount=500)])[0]
    assert f.pct_change is None
    assert f.pct_note == ("ไม่สามารถคำนวณร้อยละการเปลี่ยนแปลงได้ "
                          "เนื่องจากไม่มีค่าฐานสำหรับการคำนวณ")
    assert f.amount_a == 0 and f.amount_b == 500 and f.amount_diff == 500


def test_summary_separates_pending_from_settled():
    findings = _classify([rec(item="ก", amount=1000), rec(item="ข", act="ก", row=3)],
                         [rec(item="ก", amount=900), rec(item="ข", act="ข", row=3)])
    s = summarize(findings)
    assert s["counts"][C1_AMOUNT_DECREASED] == 1
    assert s["counts"][C6_POSSIBLE_STRUCTURE_MOVE] == 1
    assert s["settled_count"] + s["pending_review_count"] == s["total_findings"]
    assert s["pending_review_count"] == 1
    assert s["sum_amount_decreased"] == -100


def test_no_finding_claims_error_status():
    findings = _classify([rec(amount=1000)], [rec(amount=1)])
    for f in findings:
        assert f.machine_status in {"match", "diff_found", "needs_human",
                                    "likely_year_change", "likely_reduction"}
        assert f.review_status == "pending"
