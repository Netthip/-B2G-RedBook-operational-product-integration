"""ตัวรวมผลฉบับ 0.3 — กรณีตรวจรับ AC-1..AC-12 ตาม ``RESULT_SCHEMA_R3_0.3.md`` (ตัวเลขสมมติจากหมวด 16 ของวิธีวัดผล 0.3)"""
import pytest

from redbook.services import trial_aggregate as ag

LOC = {"all_sides": {"exact": 26, "partial": 2}, "some_sides": {"exact": 2}, "adjacent": {"exact": 1, "partial": 1},
       "wrong": {"exact": 1}, "no_box": {}, "undecidable": {"partial": 1}}
CROSSTAB = {"full": {"full": 36, "partial": 2, "none": 2}, "partial": {"partial": 3, "none": 1},
            "none": {"none": 4}, "undecidable": {"undecidable": 2}}
GROUPS = {"matched": 32, "s1": 3, "s2": 6, "s3": 7, "s4": 2}
BY_GROUP = {"matched": {"full": {"full": 32}}, "s1": {"full": {"full": 3}},
            "s2": {"full": {"full": 1, "partial": 2, "none": 2}, "partial": {"partial": 1}},
            "s3": {"partial": {"partial": 2, "none": 1}, "none": {"none": 4}},
            "s4": {"undecidable": {"undecidable": 2}}}


def test_ac1_h1_uses_n0_with_supplement_and_partial():
    a = ag.issues({"N0": 40, "undecidable": 2, "exact": 30, "partial": 4, "miss": {"p1": 1, "p3": 2, "p4": 1}})
    assert (a["H1"]["text"], a["supplement"]["text"], a["incl_partial"]["text"]) == \
        ("30/40 (75.0%)", "30/38 (78.9%)", "34/40 (85.0%)")
    assert a["N"] == 38 and a["P"] == 34 and a["miss_codes"]["p1"] == 1
    with pytest.raises(ag.AggregateError, match="N0"):
        ag.issues({"N0": 41, "undecidable": 2, "exact": 30, "partial": 4, "miss": {"p1": 1, "p3": 2, "p4": 1}})


def test_ac2_ac3_h2_and_partial_location():
    loc = ag.location(LOC, P=34)
    assert loc["H2"]["text"] == "28/33 (84.8%)" and loc["P"] == 34 and loc["undecidable"] == 1
    assert loc["all_over_P"]["text"] == "28/34 (82.4%)"
    assert (loc["H2_partial"]["num"], loc["H2_partial"]["den"], loc["H2_partial"]["pct"],
            loc["H2_partial"]["reason"]) == (2, 3, None, "denominator_lt_10")          # AC-3
    assert loc["H2_exact"]["text"] == "26/30 (86.7%)"
    assert set(loc["grid"]) == set(ag.LOCATION_STATUSES)                              # 6 × 2 ครบทุกช่อง
    with pytest.raises(ag.AggregateError, match="P"):
        ag.location(LOC, P=35)


def test_ac4_ac5_ledger_overflag_and_crosstab():
    o = ag.observations({"F": 50, "groups": GROUPS, "s3_reasons": {"misread": 4, "mismatch": 2, "rounding": 1},
                         "crosstab": CROSSTAB, "crosstab_by_group": BY_GROUP})
    assert o["overflag"]["text"] == "7/48 (14.6%)"
    assert o["A3_fidelity"]["text"] == "40/48 (83.3%)" and o["A3_assertion"]["text"] == "36/48 (75.0%)"
    assert o["read_ok_assertion_wrong"] == 2
    assert o["fidelity"] == {"full": 40, "partial": 4, "none": 4, "undecidable": 2}
    assert o["assertion"] == {"full": 36, "partial": 5, "none": 7, "undecidable": 2}


def test_a3_missing_crosstab_is_rejected_not_zero_percent():
    """Bo #43 6463289837 กรณี 1: F=10 จับคู่ได้ 10 ไม่ส่งตารางไขว้ — เดิมได้ A3 0/10 (0.0%) ต้องปฏิเสธ"""
    with pytest.raises(ag.AggregateError, match="ตารางไขว้ A3"):
        ag.observations({"F": 10, "groups": {"matched": 10}})
    with pytest.raises(ag.AggregateError, match="ตารางไขว้ A3"):                      # ส่งมาไม่ครบ
        ag.observations({"F": 10, "groups": {"matched": 10}, "crosstab": {"full": {"full": 9}},
                         "crosstab_by_group": {"matched": {"full": {"full": 9}}}})


def test_a3_missing_group_crosstab_is_rejected():
    """Bo #43 6463289837 กรณี 2: ตารางไขว้รวม 10 ครบ แต่ไม่ส่งตารางรายกลุ่ม (รวม 0) — ต้องปฏิเสธ"""
    with pytest.raises(ag.AggregateError, match="กลุ่ม matched"):
        ag.observations({"F": 10, "groups": {"matched": 10}, "crosstab": {"full": {"full": 10}}})


def test_a3_group_tables_must_add_back_to_the_whole_table():
    ct = {"full": {"full": 8}, "none": {"none": 2}}
    ok = ag.observations({"F": 10, "groups": {"matched": 8, "s3": 2}, "crosstab": ct,
                          "crosstab_by_group": {"matched": {"full": {"full": 8}}, "s3": {"none": {"none": 2}}}})
    assert ok["A3_fidelity"]["text"] == "8/10 (80.0%)"
    # รายกลุ่มรวมตรงจำนวนกลุ่ม แต่ช่องไม่ตรงตารางรวม
    with pytest.raises(ag.AggregateError, match="ไม่ตรงตารางไขว้ทั้งหมด"):
        ag.observations({"F": 10, "groups": {"matched": 8, "s3": 2}, "crosstab": ct,
                         "crosstab_by_group": {"matched": {"full": {"full": 6, "partial": 2}},
                                               "s3": {"none": {"none": 2}}}})
    # จำนวนติดลบที่ทำให้ผลรวมดูครบ
    with pytest.raises(ag.AggregateError, match="ติดลบ"):
        ag.observations({"F": 10, "groups": {"matched": 10}, "crosstab": {"full": {"full": 11, "none": -1}},
                         "crosstab_by_group": {"matched": {"full": {"full": 11, "none": -1}}}})
    # ตารางเกิน F
    with pytest.raises(ag.AggregateError, match="ตารางไขว้ A3"):
        ag.observations({"F": 10, "groups": {"matched": 10}, "crosstab": {"full": {"full": 11}},
                         "crosstab_by_group": {"matched": {"full": {"full": 11}}}})


def test_a3_f_zero_is_not_computable():
    """F=0: ไม่มีข้อใน U — คำนวณไม่ได้ (null + เหตุ) ไม่ใช่ 0% และตารางที่มีค่าเมื่อ F=0 = ปฏิเสธ"""
    o = ag.observations({"F": 0, "groups": {}})
    for k in ("A3_fidelity", "A3_assertion", "overflag"):
        assert o[k]["value"] is None and o[k]["reason"] == "denominator_zero" and o[k]["text"] == "คำนวณไม่ได้"
    with pytest.raises(ag.AggregateError, match="ตารางไขว้ A3"):
        ag.observations({"F": 0, "groups": {}, "crosstab": {"full": {"full": 1}}})


def test_ac6_ac9_ac10_survey_aspect():
    a = ag.aspect([[4, 4, 5], [3, 4, 4], [4, 3, 3], [4, None, 4]])
    assert (round(a["mean"], 3), round(a["sd"], 3), a["n"], a["missing"], a["level"]) == (3.778, 0.509, 3, 1, "มาก")
    assert a["meets_H3"] and [i["n"] for i in a["items"]] == [4, 3, 4] and a["items"][0]["mean"] == 3.75
    one = ag.aspect([[4, 5]])                                                        # AC-9
    assert one["mean"] == 4.5 and one["sd"] is None and one["n"] == 1
    assert ag.aspect([])["mean"] is None and ag.aspect([])["level"] is None
    assert ag.b2_level(3.505) == "มาก" and ag.b2_level(3.50) == "ปานกลาง"              # AC-10 ตัดสินก่อนปัด
    assert ag.b2_level(4.5) == "มาก" and ag.b2_level(4.51) == "มากที่สุด" and ag.b2_level(1.5) == "น้อยที่สุด"


def test_ac7_ledger_mismatch_reports_nothing():
    with pytest.raises(ag.AggregateError, match="ห้ามรายงาน"):
        ag.observations({"F": 50, "groups": {"matched": 32, "s1": 3, "s2": 6, "s3": 7, "s4": 1}})


def test_ac8_zero_denominator_is_null_not_zero():
    r = ag.location({"undecidable": {"exact": 2}})
    assert r["H2"]["value"] is None and r["H2"]["reason"] == "denominator_zero" and r["H2"]["text"] == "คำนวณไม่ได้"
    assert ag.rate(0, 0)["value"] is None and ag.rate(0, 12)["value"] == 0.0


def test_ac11_identity_warning_na_dims_stay_in_u():
    assert ag.assertion_from_dims({"real": "ok", "direction": "na", "unit": "na", "kind": "na"}) == "full"
    assert ag.assertion_from_dims({"real": "ok", "unit": "wrong", "year": "ok"}) == "partial"
    assert ag.assertion_from_dims({"real": "wrong", "unit": "ok"}) == "none"
    assert ag.assertion_from_dims({"real": "na"}) == "undecidable"
    assert ag.assertion_from_dims({"real": "ok"}, undecidable=True) == "undecidable"


def test_ac12_one_sided_location_needs_search_scope():
    assert ag.location_errors("all_sides", ["B"], "") == ["ขอบเขตที่ค้นในอีกฉบับ (เพิ่ม/หายมีหลักฐานฝั่งเดียว)"]
    assert ag.location_errors("all_sides", ["B"], "ส่วน ๗ หน้า 8–12") == []
    assert ag.location_errors("some_sides", ["A"], "x") == ["ถูกบางฝั่งใช้ได้เฉพาะประเด็นที่มีฝั่งที่เกี่ยวข้อง 2 ฝั่ง"]
    assert ag.location_errors("some_sides", ["A", "B"], "") == []
    assert ag.location_errors("near", ["A", "B"], "") == ["สถานะตำแหน่ง"]


def test_combine_counts_never_across_pair_kinds_or_sets():
    a = {"pair_kind": "same_year", "set": "dev", "counts": {"N0": 22, "miss": {"p1": 1}}}
    b = {"pair_kind": "same_year", "set": "dev", "counts": {"N0": 18, "miss": {"p3": 2}}}
    assert ag.combine([a, b]) == {"N0": 40, "miss": {"p1": 1, "p3": 2}}
    with pytest.raises(ag.AggregateError, match="ห้ามรวม"):
        ag.combine([a, {**b, "pair_kind": "cross_year"}])
    with pytest.raises(ag.AggregateError, match="ห้ามรวม"):
        ag.combine([a, {**b, "set": "eval"}])
