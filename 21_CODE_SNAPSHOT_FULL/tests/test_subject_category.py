# -*- coding: utf-8 -*-
"""หมวดจุดตรวจสอบ 6 หมวด — *สิ่งที่เปลี่ยน* แยกจาก *เกิดอะไรขึ้น*

🔴 **คำตัดสินกิ๊ฟ (7 ก.ย. 2569)** — ไม่อนุมัติ mapping เดิมที่โยน
``ROW_ADDED`` / ``ROW_REMOVED`` / ``PROJECT_ORDINAL_CHANGED`` เข้าโครงการ
หรือกิจกรรมแบบเหมารวม ต้องดูบทบาทเชิงความหมาย ป้ายแถว และบริบทของแถวนั้น
**ห้ามเดาหมวดเพื่อทำให้ครบ** — จัดไม่ได้ต้องอยู่หมวดที่หกพร้อมเหตุผล

ตัวอย่างสี่ข้อที่กิ๊ฟให้ไว้อยู่ในหมู่ ``G1``–``G4``

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from dataclasses import dataclass

import pytest

from redbook.services import categories as cat


@dataclass(frozen=True)
class FakeFinding:
    """โครงร่างเท่าที่ตัวจัดหมวดใช้จริง — จงใจไม่พึ่ง FindingView ทั้งใบ

    ทำให้เห็นชัดว่าการจัดหมวดอาศัยข้อมูลกี่ช่อง และเพิ่มช่องใหม่เมื่อใดจะรู้ตัว
    """

    finding_type: str = ""
    row_label: str = ""
    section_title: str = ""
    parent_plan: str = ""
    sheet_role: str = ""


# ══════════════════════════════════════════════════════════════════════════════
#  G1–G4 — ตัวอย่างสี่ข้อที่กิ๊ฟกำหนดไว้ตรง ๆ
# ══════════════════════════════════════════════════════════════════════════════

def test_g1_row_removed_on_an_activity_row_is_activity():
    c = cat.classify_subject(FakeFinding(
        finding_type="ROW_REMOVED", row_label="กิจกรรมที่ 2 พัฒนาระบบข้อมูล"))
    assert c.category == cat.CAT_ACTIVITY
    assert c.evidence


def test_g2_row_removed_on_an_indicator_row_is_indicator():
    c = cat.classify_subject(FakeFinding(
        finding_type="ROW_REMOVED",
        row_label="ตัวชี้วัดเชิงปริมาณ : จำนวนผลงานวิจัย"))
    assert c.category == cat.CAT_INDICATOR


def test_g3_unit_changed_on_a_target_value_is_outcome():
    c = cat.classify_subject(FakeFinding(
        finding_type="UNIT_CHANGED", row_label="ค่าเป้าหมาย"))
    assert c.category == cat.CAT_OUTCOME


def test_g4_insufficient_evidence_stays_unclassified_with_a_reason():
    c = cat.classify_subject(FakeFinding(finding_type="ROW_ADDED",
                                         row_label="รายการที่ 4"))
    assert c.category == cat.CAT_OTHER
    assert c.confidence == cat.CONF_LOW
    assert c.reason, "ต้องบอกเหตุผลที่จัดไม่ได้ ไม่ใช่เงียบ"


# ══════════════════════════════════════════════════════════════════════════════
#  C1 — สองมิติแยกกันจริง
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("ftype", ["AMOUNT_INCREASED", "AMOUNT_DECREASED",
                                   "AMOUNT_UNCHANGED"])
def test_amount_findings_are_amount_whatever_the_row_says(ftype):
    """ยอดเงินที่เปลี่ยนคือ *ยอดเงิน* — ป้ายแถวบอกว่ายอดของอะไร ซึ่งเป็นบริบท"""
    c = cat.classify_subject(FakeFinding(
        finding_type=ftype, row_label="กิจกรรมที่ 3 อบรมบุคลากร"))
    assert c.category == cat.CAT_AMOUNT
    assert c.confidence == cat.CONF_HIGH


@pytest.mark.parametrize("ftype", ["INDICATOR_CHANGED", "INDICATOR_UNCHANGED"])
def test_indicator_findings_are_indicator(ftype):
    c = cat.classify_subject(FakeFinding(finding_type=ftype))
    assert c.category == cat.CAT_INDICATOR
    assert c.confidence == cat.CONF_HIGH


def test_the_same_finding_type_can_land_in_different_categories():
    """🔴 หัวใจของคำสั่งกิ๊ฟ — ``ROW_REMOVED`` ไม่ได้แปลว่าหมวดเดียวเสมอ"""
    got = {
        cat.classify_subject(FakeFinding("ROW_REMOVED", row_label=label)).category
        for label in ("กิจกรรมที่ 1 ก", "ตัวชี้วัด : ข", "โครงการที่ 2 : ค",
                      "ค่าเป้าหมาย", "รายการทั่วไป")
    }
    assert got == {cat.CAT_ACTIVITY, cat.CAT_INDICATOR, cat.CAT_PROJECT,
                   cat.CAT_OUTCOME, cat.CAT_OTHER}


# ══════════════════════════════════════════════════════════════════════════════
#  C2 — ห้ามเดาเพื่อให้ครบ
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("ftype", [
    "NOT_COMPARABLE", "AMBIGUOUS_REQUIRES_HUMAN_REVIEW",
    "UNMAPPED_REQUIRES_HUMAN_REVIEW", "YEAR_PRESENT_ON_ONE_SIDE_ONLY"])
def test_comparison_level_findings_are_never_guessed_into_a_category(ftype):
    """ชนิดที่บอกว่า *เทียบไม่ได้* ยังไม่รู้ด้วยซ้ำว่าแถวนั้นคืออะไร

    แม้ป้ายแถวจะมีคำว่า "กิจกรรม" ก็ห้ามจัดเป็น ``ACTIVITY``
    """
    c = cat.classify_subject(FakeFinding(
        finding_type=ftype, row_label="กิจกรรมที่ 9 อะไรสักอย่าง"))
    assert c.category == cat.CAT_OTHER
    assert c.confidence == cat.CONF_LOW
    assert c.reason


def test_indicator_beats_target_when_both_words_appear():
    """ข้อความจริงมักเขียน "ตัวชี้วัดเชิงปริมาณ : เป้าหมาย …" — ต้องได้ตัวชี้วัด"""
    c = cat.classify_subject(FakeFinding(
        finding_type="ROW_ADDED",
        row_label="ตัวชี้วัดเชิงปริมาณ : เป้าหมายจำนวนผู้รับบริการ"))
    assert c.category == cat.CAT_INDICATOR


def test_sheet_role_is_used_only_when_the_label_says_nothing():
    weak = cat.classify_subject(FakeFinding(finding_type="ROW_ADDED",
                                            sheet_role="SECTION_05"))
    assert weak.category == cat.CAT_OUTCOME
    assert weak.confidence == cat.CONF_MEDIUM

    strong = cat.classify_subject(FakeFinding(
        finding_type="ROW_ADDED", row_label="กิจกรรมที่ 1 ก",
        sheet_role="SECTION_05"))
    assert strong.category == cat.CAT_ACTIVITY, "ป้ายแถวต้องชนะบทบาทของชีต"


# ══════════════════════════════════════════════════════════════════════════════
#  C3 — สัญญาของผลลัพธ์
# ══════════════════════════════════════════════════════════════════════════════

def test_six_categories_exactly():
    assert cat.CATEGORY_ORDER == (
        "AMOUNT", "INDICATOR", "OUTCOME", "PROJECT", "ACTIVITY",
        "OTHER_OR_UNCLASSIFIED")
    assert set(cat.CATEGORY_LABELS) == set(cat.CATEGORY_ORDER)


def test_every_result_carries_evidence_and_a_readable_label():
    for f in (FakeFinding("AMOUNT_DECREASED"),
              FakeFinding("ROW_ADDED", row_label="โครงการที่ 1 : ก"),
              FakeFinding("UNMAPPED_REQUIRES_HUMAN_REVIEW")):
        c = cat.classify_subject(f)
        assert c.evidence, f
        assert c.label and c.label != c.category
        assert c.confidence_label
        assert (c.reason != "") == (c.category == cat.CAT_OTHER)


def test_low_confidence_is_reserved_for_the_sixth_category():
    for f in (FakeFinding("AMOUNT_DECREASED"),
              FakeFinding("ROW_ADDED", row_label="ตัวชี้วัด : ก")):
        c = cat.classify_subject(f)
        assert c.confidence != cat.CONF_LOW
        assert c.classified
