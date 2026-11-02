# -*- coding: utf-8 -*-
"""T1B — ด่านตัวตนหน่วยงานแบบ **fail-closed**

🔴 คำสั่ง Bo · BO REVIEW COMPLETE (Issue #1) — *"In an operational verifier,
unverified identity must not be equivalent to permission to compare."*

ก่อนแก้ (``bb399a0``) ``IDENTITY_UNVERIFIED`` **ไม่หยุด** การจับคู่ ⇒

============================  ==================================================
สภาพของสองแฟ้ม                 สิ่งที่ระบบทำก่อนแก้ (วัดจริง)
============================  ==================================================
ตัวตนว่าง **ทั้งสองฝั่ง**        จับคู่อัตโนมัติ 3 คู่ · ออก ``AMOUNT_INCREASED`` 2 ใบ
ตัวตนว่าง **ฝั่งเดียว**          ออก ``ROW_ADDED`` 3 + ``ROW_REMOVED`` 3 ใบ
============================  ==================================================

ทั้งสองกรณีคือการ **ตัดสินอัตโนมัติ** ว่ายอดเพิ่ม/แถวหาย ทั้งที่ยังไม่เคยพิสูจน์ว่า
สองแฟ้มเป็นของหน่วยงานเดียวกัน

กติกาหลังแก้ — อนุญาตให้จับคู่อัตโนมัติ **เฉพาะ** ``IDENTITY_OK`` เท่านั้น
เหตุผลอื่นทุกค่า (รวมค่าที่ยังไม่มีในวันนี้) ต้องตกไปทาง **ปฏิเสธ** เสมอ
โดยยัง ``accounted`` ครบและคงไว้ว่า record มาจากฝั่งใด

🔴 **SYNTHETIC TEST FIXTURE** — ดู :mod:`t1b_synth`

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import os
from dataclasses import replace
from pathlib import Path

import pytest

from redbook.t1b.compare import compare
from redbook.t1b.keys import T1BKey
from redbook.t1b.matching import (
    IDENTITY_AMBIGUOUS,
    IDENTITY_CONFLICT,
    IDENTITY_OK,
    IDENTITY_UNVERIFIED,
    SIDE_BASELINE,
    SIDE_CURRENT,
    VERDICT_CANNOT_DETERMINE,
    VERDICT_COMPARED,
    VERDICT_REVIEW_REQUIRED,
    IdentityCheck,
    check_identity,
    match_records,
)
from redbook.t1b.records import T1BRecord
from t1b_synth import build_workbook, records

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

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"


def _blind(tmp_path, name, **kw):
    """แฟ้มที่อ่านตัวตนหน่วยงานจากเนื้อในไม่ได้ — ไม่มีชีตปก"""
    return records(build_workbook(
        tmp_path, filename=name, agency=None, cover_year=2570,
        section_title=TITLE, **kw))


def _named(tmp_path, name, agency, **kw):
    return records(build_workbook(
        tmp_path, filename=name, agency=agency, cover_year=2570,
        section_title=TITLE, **kw))


def _assert_refused(base, curr, result, *, expect_reason, expect_verdict):
    """ข้อผูกพันร่วมของทุกกรณีที่ด่านปฏิเสธ"""
    s = result.summary()
    assert s["identity_reason"] == expect_reason
    assert s["identity_verdict"] == expect_verdict
    assert s["identity_gate_blocked"] is True
    assert s["identity_verified"] is False

    # ① ห้ามมีคู่อัตโนมัติแม้แต่คู่เดียว
    assert result.matched == [], "🔴 ด่านไม่ผ่านแต่ยังจับคู่อัตโนมัติ"
    # ② ห้ามตัดสินอัตโนมัติว่าแถวหาย/แถวเพิ่ม
    assert result.baseline_only == [], "🔴 ด่านไม่ผ่านแต่ยังสรุปว่าแถวหาย"
    assert result.current_only == [], "🔴 ด่านไม่ผ่านแต่ยังสรุปว่าแถวเพิ่ม"
    # ③ ทุก record ต้องยังถูกนับครบ
    assert result.accounted() == len(base) + len(curr), "🔴 มี record หายเงียบ"
    # ④ provenance สองฝั่งต้องอยู่ครบ
    sides = [sr.side for sr in result.needs_human]
    assert sides.count(SIDE_BASELINE) == len(base)
    assert sides.count(SIDE_CURRENT) == len(curr)


# ══════════════════════════════════════════════════════════════════════════════
#  G1–G4 — สี่กรณีที่ Bo สั่งให้มี regression
# ══════════════════════════════════════════════════════════════════════════════


def test_g1_both_identities_blank_refuses_automatic_matching(tmp_path):
    """🔴 หัวใจของการแก้ — ตัวตนว่างทั้งคู่ ⇒ คีย์เท่ากัน ⇒ เดิมจับคู่ได้เงียบ ๆ"""
    base = _blind(tmp_path, "blind_baseline.xlsx")
    curr = _blind(tmp_path, "blind_current.xlsx", invest=12.0)

    check = check_identity(base, curr)
    assert check.reason == IDENTITY_UNVERIFIED
    assert not check.may_match, "🔴 ยืนยันไม่ได้ ≠ อนุญาตให้เทียบ"

    result = match_records(base, curr)
    _assert_refused(base, curr, result,
                    expect_reason=IDENTITY_UNVERIFIED,
                    expect_verdict=VERDICT_CANNOT_DETERMINE)

    cmp_result = compare(result)
    assert cmp_result.summary()["automatic_pairs"] == 0
    assert cmp_result.summary()["identity_verdict"] == VERDICT_CANNOT_DETERMINE
    # เดิมออก AMOUNT_INCREASED — ยอดที่เพิ่มขึ้นของหน่วยงานที่ยังไม่รู้ว่าใช่หรือไม่
    assert not [f for f in cmp_result.findings
                if f.finding_type.startswith("AMOUNT_")], (
        "🔴 ห้ามสรุปยอดเพิ่ม/ลด เมื่อยังไม่ยืนยันว่าเป็นหน่วยงานเดียวกัน")
    assert all(f.requires_human_decision for f in cmp_result.findings)


def test_g2_one_identity_blank_refuses_automatic_matching(tmp_path):
    """ฝั่งเดียวที่อ่านตัวตนไม่ได้ ⇒ เดิมออก ``ROW_ADDED``/``ROW_REMOVED`` เต็มไปหมด"""
    base = _blind(tmp_path, "blind_only.xlsx")
    curr = _named(tmp_path, "named_only.xlsx", "หน่วยงาน ก")

    result = match_records(base, curr)
    _assert_refused(base, curr, result,
                    expect_reason=IDENTITY_UNVERIFIED,
                    expect_verdict=VERDICT_CANNOT_DETERMINE)

    types = compare(result).by_type()
    assert "ROW_ADDED" not in types and "ROW_REMOVED" not in types, (
        "🔴 ห้ามสรุปว่าแถวถูกเพิ่ม/ถูกลบ ทั้งที่ยังไม่รู้ว่าเป็นหน่วยงานเดียวกัน")


def test_g2b_blank_on_the_other_side_is_treated_the_same(tmp_path):
    """สลับฝั่ง — ด่านต้องไม่ขึ้นกับว่าฝั่งไหนอ่านไม่ได้"""
    base = _named(tmp_path, "named_first.xlsx", "หน่วยงาน ก")
    curr = _blind(tmp_path, "blind_second.xlsx")

    result = match_records(base, curr)
    _assert_refused(base, curr, result,
                    expect_reason=IDENTITY_UNVERIFIED,
                    expect_verdict=VERDICT_CANNOT_DETERMINE)


def test_g3_conflicting_name_evidence_refuses_automatic_matching(tmp_path):
    """ชื่อหน่วยงานในเนื้อแฟ้มขัดแย้งกัน ⇒ ``REVIEW_REQUIRED``"""
    base = _named(tmp_path, "conflict_a.xlsx", "หน่วยงาน ก")
    curr = _named(tmp_path, "conflict_b.xlsx", "หน่วยงาน ข")

    result = match_records(base, curr)
    _assert_refused(base, curr, result,
                    expect_reason=IDENTITY_CONFLICT,
                    expect_verdict=VERDICT_REVIEW_REQUIRED)
    assert result.summary()["identity_conflict"] is True


def test_g3b_conflicting_code_evidence_without_content_identity(tmp_path):
    """รหัสจากชื่อไฟล์ขัดแย้งแต่เนื้อในอ่านตัวตนไม่ได้

    🔴 กรณีนี้ **ห้ามอ่านว่าปลอดภัยเพราะไม่มีคู่ออกมา** — ก่อนแก้ คีย์ต่างกัน
    เพราะ ``agency_code`` ต่างกัน จึงไม่มีคู่จริง แต่ระบบกลับสรุปเองว่า
    ทุกแถว "ถูกลบ" และ "ถูกเพิ่ม" ซึ่งเป็นการตัดสินอัตโนมัติเช่นกัน
    """
    base = _blind(tmp_path, "XL_FY2570_draft-bill_21011_A.xlsx")
    curr = _blind(tmp_path, "XL_FY2570_draft-bill_21016_B.xlsx")

    codes = {r.key.agency_code for r in base} | {r.key.agency_code for r in curr}
    assert len(codes) == 2, f"ชื่อไฟล์ต้องให้รหัสสองค่าที่ต่างกัน ได้ {codes}"

    result = match_records(base, curr)
    _assert_refused(base, curr, result,
                    expect_reason=IDENTITY_UNVERIFIED,
                    expect_verdict=VERDICT_CANNOT_DETERMINE)


def test_g4_confirmed_same_agency_still_matches(tmp_path):
    """ด่านต้องไม่ปิดงานที่ถูกต้อง — ยืนยันได้ว่าหน่วยงานเดียวกัน ⇒ เทียบได้"""
    base = _named(tmp_path, "same_a.xlsx", "หน่วยงานเดียวกัน")
    curr = _named(tmp_path, "same_b.xlsx", "หน่วยงานเดียวกัน", invest=12.0)

    result = match_records(base, curr)
    s = result.summary()
    assert s["identity_reason"] == IDENTITY_OK
    assert s["identity_verdict"] == VERDICT_COMPARED
    assert s["identity_gate_blocked"] is False
    assert result.matched, "หน่วยงานเดียวกันต้องยังจับคู่ได้ตามเดิม"
    assert result.accounted() == len(base) + len(curr)

    cmp_result = compare(result)
    assert cmp_result.summary()["automatic_pairs"] == len(result.matched)
    assert [f for f in cmp_result.findings if f.finding_type == "AMOUNT_INCREASED"]


# ══════════════════════════════════════════════════════════════════════════════
#  G5–G8 — ขอบของด่านเอง
# ══════════════════════════════════════════════════════════════════════════════


def _rec(identity: str) -> T1BRecord:
    return T1BRecord(key=T1BKey(
        agency_code="", document_level="agency", sheet_role="SECTION_05",
        agency_identity=identity, row_label_norm="รวมทั้งสิ้น"))


def test_g5_more_than_one_identity_on_one_side_is_refused():
    """หลายตัวตนในฝั่งเดียว ⇒ ตัดสินไม่ได้ ⇒ ปฏิเสธ (เดิมไม่ถูกหยุดเช่นกัน)"""
    base = [_rec("หน่วยงาน ก"), _rec("หน่วยงาน ข")]
    curr = [_rec("หน่วยงาน ก")]

    check = check_identity(base, curr)
    assert check.reason == IDENTITY_AMBIGUOUS
    assert not check.may_match
    assert check.verdict == VERDICT_CANNOT_DETERMINE

    result = match_records(base, curr)
    _assert_refused(base, curr, result,
                    expect_reason=IDENTITY_AMBIGUOUS,
                    expect_verdict=VERDICT_CANNOT_DETERMINE)


def test_g6_gate_is_closed_by_default_for_unknown_reasons():
    """🔴 เหตุผลใหม่ที่ยังไม่มีในวันนี้ ต้องตกไปทาง **ปฏิเสธ** ไม่ใช่ทางผ่าน

    ป้องกันไม่ให้การเพิ่มสถานะในอนาคตเปิดช่องเทียบข้ามหน่วยงานโดยไม่ตั้งใจ
    """
    check = IdentityCheck((), (), "a_reason_added_in_the_future")
    assert not check.may_match
    assert check.blocked
    assert check.verdict == VERDICT_CANNOT_DETERMINE
    assert not check.verified and not check.conflict


def test_g7_only_identity_ok_opens_the_gate():
    """ตารางความจริงของด่านทั้งใบ — มีทางผ่านทางเดียว"""
    opened = [
        r for r in (IDENTITY_OK, IDENTITY_CONFLICT, IDENTITY_UNVERIFIED,
                    IDENTITY_AMBIGUOUS)
        if IdentityCheck(("x",), ("x",), r).may_match
    ]
    assert opened == [IDENTITY_OK]


def test_g8_every_blocked_finding_carries_its_own_reason(tmp_path):
    """ผู้อ่านต้องรู้ว่าถูกกันเพราะอะไร — ห้ามเห็นเหตุผลว่างเปล่า"""
    base = _blind(tmp_path, "why_a.xlsx")
    curr = _blind(tmp_path, "why_b.xlsx", invest=12.0)

    result = compare(match_records(base, curr))
    blocked = [f for f in result.findings
               if f.finding_type == "AMBIGUOUS_REQUIRES_HUMAN_REVIEW"]
    assert blocked
    for f in blocked:
        assert "ตัวตนหน่วยงาน" in f.detail, f.detail
        assert f.requires_human_decision


# ══════════════════════════════════════════════════════════════════════════════
#  G9–G10 — ไม่ถอยหลังกับแฟ้มจริง
# ══════════════════════════════════════════════════════════════════════════════


@needs_sources
def test_g9_real_same_agency_pair_is_unchanged():
    base = records(SOURCE_DIR / "XL_FY2569_draft-bill_21011_HSRI.xlsx")
    curr = records(SOURCE_DIR / "XL_FY2570_draft-bill_21011_HSRI.xlsx")

    result = match_records(base, curr)
    s = result.summary()
    assert s["identity_verdict"] == VERDICT_COMPARED
    assert s["identity_gate_blocked"] is False
    assert result.matched
    assert result.accounted() == len(base) + len(curr)


@needs_sources
def test_g10_real_pair_with_identity_stripped_is_refused():
    """จำลองสภาพจริงของ Shadow Run — แฟ้มที่ผู้ใช้ตั้งชื่อเอง อ่านตัวตนไม่ได้

    🔴 นี่คือสภาพที่ ``bb399a0`` ปล่อยผ่าน: ทั้งรหัสจากชื่อไฟล์และตัวตนจากเนื้อใน
    ว่างทั้งสองฝั่ง ⇒ คีย์เท่ากัน ⇒ จับคู่อัตโนมัติทั้งชุด
    """
    def stripped(name):
        return [replace(r, key=replace(r.key, agency_code="", agency_identity=""))
                for r in records(SOURCE_DIR / name)]

    base = stripped("XL_FY2570_draft-bill_21011_HSRI.xlsx")
    curr = stripped("XL_FY2570_draft-bill_21016_NVI.xlsx")

    result = match_records(base, curr)
    _assert_refused(base, curr, result,
                    expect_reason=IDENTITY_UNVERIFIED,
                    expect_verdict=VERDICT_CANNOT_DETERMINE)
