# -*- coding: utf-8 -*-
"""ตารางท่าทีที่ประกาศล่วงหน้า (Issue #5)

ข้อที่ Bo สั่งไว้เมื่อ 6 ก.ย. 2569 และยังปิดไม่ได้:

    หมวด 4 ยังไม่มี predeclared posture table ครบทุก defect type
    ตารางนี้ต้องเป็น source เดียวของทั้ง `expected_referral_types`
    และ output stratum · ตรึงก่อนสร้าง/เปิด answer key

สิ่งที่ชุดนี้ยืนยัน

* ตารางครอบคลุม **ทุกชนิด** ที่โปรโตคอลประกาศไว้ — ไม่มีชนิดใดหายเงียบ
* stratum **มาจากท่าที** ตั้งแยกไม่ได้ ⇒ ไม่มีทางเกิดคู่ที่ขัดกันเอง
* ชนิดที่ยังไม่ประกาศ = `UNDECLARED` และ **ด่านปฏิเสธการสร้างเฉลย**
* ไม่มีการเติมท่าทีให้เองแทนมนุษย์ — รุ่น 0.2.0 เติมห้าชนิดจากคำตัดสินของกิ๊ฟ
  (6 ต.ค. 2569) เท่านั้น และทุกชนิดที่เติมติดป้ายที่มา

🔴 ชุดนี้ **ไม่แตะเฉลย** และไม่รู้จักเฉลย — รู้จักเพียงชนิดของข้อบกพร่อง

**สายงานวิจัย · `PRE-FREEZE`**
"""
import pytest

from redbook.t1b_eval import posture as P


# ══════════════════════════════════════════════ ความครบถ้วนของตาราง

def test_every_defect_type_in_the_protocol_has_a_row():
    """บัญชีชนิดในโปรโตคอล: V 7 · S 6 · T 3 · F 4 · N 5 = 25"""
    expected_per_group = {"V": 7, "S": 6, "T": 3, "F": 4, "N": 5}
    actual: dict[str, int] = {}
    for e in P.TABLE:
        actual[e.group] = actual.get(e.group, 0) + 1
    assert actual == expected_per_group
    assert len(P.TABLE) == 25


def test_codes_are_unique_and_well_formed():
    codes = [e.code for e in P.TABLE]
    assert len(codes) == len(set(codes)), "รหัสซ้ำ"
    for c in codes:
        group, _, num = c.partition("-")
        assert group in ("V", "S", "T", "F", "N")
        assert num.isdigit() and len(num) == 2


def test_every_row_has_a_known_posture():
    for e in P.TABLE:
        assert e.posture in P.POSTURES, e.code


# ══════════════════════════════════════════════ แหล่งเดียว

def test_stratum_is_derived_from_posture_never_set_separately():
    """🔴 หัวใจของข้อที่ Bo สั่ง — ตารางเดียวเป็นที่มาของทั้งสองอย่าง"""
    for e in P.TABLE:
        assert e.stratum == P.STRATUM_OF_POSTURE[e.posture], e.code
    # ไม่มีทางตั้ง stratum ให้ขัดกับท่าทีได้ เพราะไม่มีฟิลด์ให้ตั้ง
    assert not hasattr(P.PostureEntry("x", "V", "t", P.POSTURE_AUTOMATIC),
                       "_stratum")


def test_not_detectable_types_never_sit_in_the_stratum_that_has_a_pass_mark():
    """§5.7 — stratum สำรวจ **ห้ามใช้รองรับเกณฑ์ผ่าน**"""
    for e in P.TABLE:
        if e.posture == P.POSTURE_NOT_DETECTABLE:
            assert e.stratum == P.STRATUM_EXPLORATORY, e.code
        if e.stratum == P.STRATUM_PRIMARY:
            assert e.posture in (P.POSTURE_AUTOMATIC, P.POSTURE_REFERRED), e.code


def test_decoys_are_not_in_any_scoring_stratum():
    """ตัวล่อไม่ใช่ข้อบกพร่องที่ต้องหา จึงต้องไม่อยู่ในตัวหารของ stratum ใด"""
    for code in P.must_not_report_types():
        e = P.entry(code)
        assert e.stratum == P.STRATUM_NEGATIVE_CONTROL
        assert not e.scorable


def test_expected_referral_types_comes_from_the_table_only():
    derived = set(P.expected_referral_types())
    from_table = {e.code for e in P.TABLE if e.posture == P.POSTURE_REFERRED}
    assert derived == from_table


def test_types_in_stratum_partitions_the_table_with_nothing_lost():
    seen: list[str] = []
    for s in (P.STRATUM_PRIMARY, P.STRATUM_EXPLORATORY,
              P.STRATUM_NEGATIVE_CONTROL, P.STRATUM_UNASSIGNED):
        seen.extend(P.types_in_stratum(s))
    assert sorted(seen) == sorted(e.code for e in P.TABLE)
    assert len(seen) == len(set(seen)), "ชนิดเดียวอยู่ได้ stratum เดียว"


# ══════════════════════════════════════════════ ห้ามเดาแทนมนุษย์

#: ท่าทีที่กิ๊ฟประกาศ 6 ต.ค. 2569 (Issue #5) — คัดตรงจากคำตัดสิน
GIFT_20261006 = {
    "V-04": P.POSTURE_AUTOMATIC,
    "V-05": P.POSTURE_AUTOMATIC,
    "S-06": P.POSTURE_REFERRED,
    "T-02": P.POSTURE_REFERRED,
    "F-03": P.POSTURE_AUTOMATIC,
}


def test_no_type_is_left_undeclared_in_0_2_0():
    assert P.POSTURE_TABLE_VERSION == "t1b-posture-0.2.0"
    assert P.undeclared_types() == ()


def test_the_five_types_carry_exactly_the_postures_gift_declared():
    for code, posture in GIFT_20261006.items():
        assert P.posture_of(code) == posture, code


def test_only_the_five_decided_types_are_labelled_as_human_decisions():
    """ทุกแถวบอกที่มาได้ — แยกได้เสมอว่าแถวใดมาจากโปรโตคอล แถวใดมาจากคำตัดสิน"""
    decided = {e.code for e in P.TABLE if e.declared_by != "protocol"}
    assert decided == set(GIFT_20261006)
    for code in decided:
        assert P.entry(code).declared_by == "gift-decision-2026-10-06"
    assert P.summary()["declared_by_decision"] == sorted(
        decided, key=[e.code for e in P.TABLE].index)


def test_version_history_is_append_only_and_records_the_old_gap():
    """0.1.0 ยังอยู่ในประวัติพร้อมช่องว่างเดิม — ไม่ถูกเขียนทับ"""
    versions = [v for v, _, _ in P.VERSION_HISTORY]
    assert versions == ["t1b-posture-0.1.0", "t1b-posture-0.2.0"]
    assert versions[-1] == P.POSTURE_TABLE_VERSION
    for code in GIFT_20261006:
        assert code in P.VERSION_HISTORY[0][2]
    assert "6012653884" in P.DECISION_SOURCE


def _undeclared(code="X-01"):
    return P.PostureEntry(code, "V", "สังเคราะห์", P.POSTURE_UNDECLARED)


def test_an_undeclared_type_cannot_be_given_a_scoring_stratum():
    e = _undeclared()
    assert e.stratum == P.STRATUM_UNASSIGNED
    assert not e.scorable
    assert not e.declared


@pytest.fixture
def with_undeclared(monkeypatch):
    """ใส่ชนิดที่ยังไม่ประกาศท่าทีลงตารางชั่วคราว — พิสูจน์ว่าด่านยังทำงาน"""
    e = _undeclared("V-04")
    by_code = dict(P.BY_CODE)
    by_code["V-04"] = e
    table = tuple(e if x.code == "V-04" else x for x in P.TABLE)
    monkeypatch.setattr(P, "BY_CODE", by_code)
    monkeypatch.setattr(P, "TABLE", table)
    return e


def test_an_unknown_code_raises_instead_of_guessing():
    with pytest.raises(P.UndeclaredDefectType):
        P.entry("Z-99")
    with pytest.raises(P.UndeclaredDefectType):
        P.stratum_of("V-99")


# ══════════════════════════════════════════════ ด่านก่อนสร้างเฉลย

def test_the_0_2_0_table_is_ready_to_build_an_answer_key():
    r = P.readiness()
    assert r.ok and r.blocking_reason == ""
    assert not r.no_referral_types


def test_the_gate_still_blocks_when_a_type_is_undeclared(with_undeclared):
    """ด่านไม่ได้ถูกปลดถาวร — มีชนิดใดว่างเมื่อใด ปฏิเสธทันที"""
    r = P.readiness()
    assert not r.ok
    assert r.undeclared
    assert "ยังมีชนิดข้อบกพร่องที่โปรโตคอลไม่ได้ประกาศท่าทีไว้" in r.blocking_reason
    for code in r.undeclared:
        assert code in r.blocking_reason


def test_caveats_warn_but_do_not_block():
    r = P.readiness()
    assert set(r.caveated) == {"S-01", "S-02"}
    assert r.warning and "ไม่ block" in r.warning


def test_readiness_would_pass_only_when_every_type_is_declared():
    """พิสูจน์ว่าด่านไม่ได้ปฏิเสธทุกกรณีแบบตายตัว — ผ่านได้เมื่อประกาศครบ"""
    full = P.Readiness(undeclared=(), caveated=("S-01",))
    assert full.ok and full.blocking_reason == ""
    assert full.warning


# ══════════════════════════════════════════════ รายงาน

def test_summary_reports_counts_and_never_leaks_an_answer_key():
    s = P.summary()
    assert s["types_total"] == 25
    assert s["ready_to_build_answer_key"] is True
    assert s["by_posture"][P.POSTURE_UNDECLARED] == 0
    assert s["by_posture"][P.POSTURE_AUTOMATIC] == 11
    assert s["by_posture"][P.POSTURE_REFERRED] == 2
    assert s["by_stratum"] == {P.STRATUM_PRIMARY: 13, P.STRATUM_EXPLORATORY: 5,
                               P.STRATUM_NEGATIVE_CONTROL: 7}
    assert sum(s["by_posture"].values()) == 25
    assert sum(s["by_stratum"].values()) == 25
    blob = repr(s)
    for banned in ("defect_id", "location", "sheet", "cell"):
        assert banned not in blob, banned


def test_summary_pins_the_version_and_its_source():
    s = P.summary()
    assert s["posture_table_version"] == P.POSTURE_TABLE_VERSION
    assert "LANE_C_BLIND_EVALUATION_PROTOCOL" in s["spec_source"]


# ══════════════════════════════════════════════ ด่านบังคับกับเฉลย

class _Gold:
    """ตัวแทนเฉลยหนึ่งตัว — ชั้นนี้ไม่ import โมดูลคะแนน จึงใช้ของปลอมได้"""

    def __init__(self, defect_id, defect_type, stratum):
        self.defect_id = defect_id
        self.defect_type = defect_type
        self.stratum = stratum


def test_a_gold_set_that_matches_the_table_passes():
    P.validate_gold([
        _Gold("d1", "V-01", P.STRATUM_PRIMARY),
        _Gold("d2", "F-01", P.STRATUM_EXPLORATORY),
    ])


def test_moving_a_type_into_another_stratum_is_refused():
    """🔴 §5.7 ข้อ 2 — ห้ามย้ายชนิดข้าม stratum หลังเห็นผล"""
    with pytest.raises(P.PostureViolation) as ei:
        P.validate_gold([_Gold("d1", "F-01", P.STRATUM_PRIMARY)])
    assert "ห้ามย้ายชนิดข้าม stratum" in str(ei.value)


def test_a_decoy_cannot_be_put_in_the_answer_key():
    with pytest.raises(P.PostureViolation) as ei:
        P.validate_gold([_Gold("d1", "N-01", P.STRATUM_NEGATIVE_CONTROL)])
    assert "ตัวล่อ" in str(ei.value)


def test_an_undeclared_type_cannot_be_put_in_the_answer_key(with_undeclared):
    with pytest.raises(P.PostureViolation) as ei:
        P.validate_gold([_Gold("d1", "V-04", P.STRATUM_PRIMARY)])
    assert "ยังไม่ประกาศท่าที" in str(ei.value)


def test_an_unknown_type_cannot_be_put_in_the_answer_key():
    with pytest.raises(P.PostureViolation):
        P.validate_gold([_Gold("d1", "Z-01", P.STRATUM_PRIMARY)])


def test_all_problems_are_reported_at_once_not_just_the_first(with_undeclared):
    with pytest.raises(P.PostureViolation) as ei:
        P.validate_gold([
            _Gold("d1", "V-04", P.STRATUM_PRIMARY),
            _Gold("d2", "N-01", P.STRATUM_NEGATIVE_CONTROL),
            _Gold("d3", "F-01", P.STRATUM_PRIMARY),
        ])
    msg = str(ei.value)
    for did in ("d1", "d2", "d3"):
        assert did in msg


# ══════════════════════════════════════════════ ชนิดที่ควรส่งต่อ

def test_expected_referral_types_are_the_two_gift_declared():
    """0.1.0 ไม่มีชนิดใดเป็น "ควรส่งต่อ" ⇒ วัด referral recall ไม่ได้
    0.2.0 กิ๊ฟประกาศ S-06 · T-02 ⇒ วัดได้ในรอบนี้"""
    assert P.expected_referral_types() == ("S-06", "T-02")
    for code in P.expected_referral_types():
        assert P.stratum_of(code) == P.STRATUM_PRIMARY
    r = P.readiness()
    assert not r.no_referral_types
    assert "referral recall" not in r.warning
    assert P.summary()["no_referral_types_declared"] is False


def test_an_empty_referral_set_is_still_reported_if_it_ever_returns():
    r = P.Readiness(undeclared=(), caveated=(), no_referral_types=True)
    assert r.ok
    assert "referral recall" in r.warning
