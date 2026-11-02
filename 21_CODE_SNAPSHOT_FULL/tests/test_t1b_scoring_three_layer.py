# -*- coding: utf-8 -*-
"""T1B — schema การให้คะแนนสามชั้น (Lane C)

🔴 คำสั่ง Bo · `BO REVIEW COMPLETE` (Issue #1) · LANE C

    *"A referral is not an automatic TP and is not automatically an FP.
    It must be scored in its own stratum. **This decision removes the incentive
    to inflate F1 by sending everything to review.**"*

ชุดนี้ทำให้ประโยคสุดท้ายเป็น **ข้อบังคับที่ทดสอบได้** ไม่ใช่เจตนาในเอกสาร

🔴 **ไม่มีเฉลยจริงในไฟล์นี้** — ทุกอย่างเป็นตัวอย่างสังเคราะห์ที่แต่งขึ้นเพื่อวัด
*ตัวสูตร* ไม่ใช่เพื่อวัดระบบ · การสร้าง generator และเฉลยจริงยังถูกระงับ

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import pytest

from redbook.t1b_eval.scoring import (
    DISPOSITION_AUTOMATIC,
    DISPOSITION_REFERRED,
    DetectorOutput,
    InjectedDefect,
    Location,
    score,
)


def _loc(n: int) -> Location:
    return Location(sheet="Sheet5", row=n, cell=f"C{n}")


def _defect(n: int, dtype: str = "V-01", in_scope: bool = True) -> InjectedDefect:
    return InjectedDefect(defect_id=f"D{n}", defect_type=dtype,
                          location=_loc(n), in_scope=in_scope)


def _out(n: int, ftype: str = "V-01", disp: str = DISPOSITION_AUTOMATIC,
         suffix: str = "") -> DetectorOutput:
    return DetectorOutput(output_id=f"O{n}{suffix}", finding_type=ftype,
                          location=_loc(n), disposition=disp)


# ══════════════════════════════════════════════════════════════════════════════
#  C1 — ชั้น ① การตัดสินอัตโนมัติ
# ══════════════════════════════════════════════════════════════════════════════


def test_c1_exact_hit_is_a_true_positive():
    r = score([_defect(1)], [_out(1)], records_total=100).summary()
    a = r["layer_1_automatic"]
    assert (a["tp"], a["fp"], a["fn"], a["tp_location_only"]) == (1, 0, 0, 0)
    assert a["precision"] == 1.0 and a["recall"] == 1.0 and a["f1"] == 1.0


def test_c2_right_location_wrong_type_is_counted_separately():
    """🔴 ห้ามรวมกับ ``tp`` — ชนิดผิดคือการยืนยันที่ไม่ถูกต้อง"""
    r = score([_defect(1, "V-01")], [_out(1, "V-05")]).summary()
    a = r["layer_1_automatic"]
    assert a["tp"] == 0
    assert a["tp_location_only"] == 1
    assert a["fp"] == 0, "ตำแหน่งถูกอยู่ ไม่ใช่การเตือนผิดที่"
    assert a["recall"] == 0.0, "ยังไม่ถือว่าระบบตัดสินถูก"


def test_c3_wrong_type_still_costs_precision():
    """การเดาชนิดมั่ว ๆ ต้องมีต้นทุน มิฉะนั้นจะเป็นการกระทำที่ไม่มีโทษ"""
    r = score([_defect(1, "V-01"), _defect(2, "V-01")],
              [_out(1, "V-01"), _out(2, "V-99")]).summary()
    a = r["layer_1_automatic"]
    assert a["automatic_outputs"] == 2
    assert a["precision"] == 0.5


def test_c4_false_positive_when_nothing_is_there():
    r = score([], [_out(9)], records_total=100).summary()
    a = r["layer_1_automatic"]
    assert (a["tp"], a["fp"]) == (0, 1)
    assert a["precision"] == 0.0
    assert a["recall"] is None, "ไม่มีข้อบกพร่องเลย ⇒ recall ไม่นิยาม ห้ามคืน 0"


def test_c5_missed_defect_is_a_false_negative():
    r = score([_defect(1)], []).summary()
    a = r["layer_1_automatic"]
    assert (a["tp"], a["fn"]) == (0, 1)
    assert a["recall"] == 0.0


def test_c6_one_output_cannot_claim_two_defects():
    """ยิงรัวที่ตำแหน่งเดียวต้องไม่ได้ ``tp`` หลายใบ"""
    r = score([_defect(1)], [_out(1, suffix="a"), _out(1, suffix="b")]).summary()
    a = r["layer_1_automatic"]
    assert a["tp"] == 1
    assert a["fp"] == 1, "ใบที่เหลือไม่มีข้อบกพร่องรองรับ ⇒ เป็นการเตือนผิด"


def test_c7_scoring_does_not_depend_on_input_order():
    """รวมกรณีที่มีข้อบกพร่อง **หลายตัวที่ตำแหน่งเดียวกัน** ซึ่งเป็นจุดที่เปราะที่สุด"""
    twin_a = InjectedDefect("Dx", "V-01", _loc(4))
    twin_b = InjectedDefect("Dy", "V-05", _loc(4))
    key = [_defect(1), _defect(2), _defect(3), twin_a, twin_b]
    outs = [_out(1), _out(3), _out(2, "V-09"), _out(4, "V-05")]

    a = score(key, outs).summary()
    b = score(list(reversed(key)), list(reversed(outs))).summary()
    assert a == b, "ผลต้องไม่ขึ้นกับลำดับที่ผู้เรียกส่งเข้ามา"
    assert a["layer_1_automatic"]["tp"] == 3, "V-05 ที่แถว 4 ต้องจับกับตัวที่ชนิดตรง"


def test_c8_out_of_scope_hit_is_excluded_from_the_precision_denominator():
    """ใบที่ไปตรงชนิดนอกขอบเขต ไม่ใช่ความถูกและไม่ใช่ความผิดของชั้น ①

    จึงต้องไม่อยู่ในตัวหารของ precision — ปรากฏเฉพาะที่ ``out_of_scope_detected``
    """
    key = [_defect(1), _defect(2, "F-01", in_scope=False)]
    a = score(key, [_out(1), _out(2, "F-01")]).summary()
    assert a["layer_1_automatic"]["automatic_outputs"] == 1
    assert a["layer_1_automatic"]["precision"] == 1.0
    assert a["denominators"]["out_of_scope_detected"] == 1


# ══════════════════════════════════════════════════════════════════════════════
#  C2 — ชั้น ② การส่งต่อ
# ══════════════════════════════════════════════════════════════════════════════


def test_c10_referral_is_neither_tp_nor_fp():
    """🔴 หัวใจของคำตัดสิน Bo"""
    r = score([_defect(1)], [_out(1, disp=DISPOSITION_REFERRED)],
              records_total=1000).summary()
    a, ref = r["layer_1_automatic"], r["layer_2_referral"]
    assert a["tp"] == 0, "การส่งต่อไม่ใช่การตัดสินถูก"
    assert a["fp"] == 0, "และไม่ใช่การเตือนผิดเช่นกัน"
    assert a["fn"] == 0, "ข้อบกพร่องนี้ไม่ได้หลุด — มีคนถูกพาไปดูแล้ว"
    assert ref["correct"] == 1 and ref["wrong"] == 0 and ref["missed"] == 0
    assert ref["recall"] == 1.0


def test_c11_unnecessary_referral_is_counted_as_wrong_not_as_fp():
    r = score([], [_out(9, disp=DISPOSITION_REFERRED)], records_total=500).summary()
    assert r["layer_1_automatic"]["fp"] == 0
    assert r["layer_2_referral"]["wrong"] == 1


def test_c12_review_burden_is_reported_per_1000_records():
    outs = [_out(n, disp=DISPOSITION_REFERRED) for n in range(1, 6)]
    r = score([], outs, records_total=2000).summary()
    assert r["layer_2_referral"]["referred_total"] == 5
    assert r["layer_2_referral"]["burden_per_1000"] == 2.5


def test_c13_burden_is_none_without_a_declared_denominator():
    """🔴 ห้ามเดาตัวหาร — ไม่ประกาศจำนวน record ก็ไม่มีสิทธิ์รายงานภาระการตรวจ"""
    r = score([], [_out(1, disp=DISPOSITION_REFERRED)]).summary()
    assert r["layer_2_referral"]["burden_per_1000"] is None


def test_c14_automatic_claims_a_location_before_a_referral_does():
    """ณ ตำแหน่งเดียวกัน การฟันธงเป็นข้อกล่าวอ้างที่หนักกว่า ต้องถูกวัดก่อน"""
    r = score([_defect(1)],
              [_out(1, disp=DISPOSITION_REFERRED), _out(1, suffix="z")]).summary()
    assert r["layer_1_automatic"]["tp"] == 1
    assert r["layer_2_referral"]["correct"] == 0
    assert r["layer_2_referral"]["wrong"] == 1


# ══════════════════════════════════════════════════════════════════════════════
#  C3 — ชั้น ③ ความครอบคลุมรวม
# ══════════════════════════════════════════════════════════════════════════════


def test_c20_coverage_counts_asserted_or_correctly_referred():
    key = [_defect(1), _defect(2), _defect(3)]
    outs = [_out(1), _out(2, disp=DISPOSITION_REFERRED)]
    r = score(key, outs).summary()
    c = r["layer_3_coverage"]
    assert c["covered"] == 2 and c["uncovered"] == 1
    assert c["coverage"] == pytest.approx(2 / 3)


def test_c21_coverage_is_not_the_same_number_as_automatic_f1():
    """🔴 หมวด 5.3 — ต้องรายงานแยก ห้ามนำมาแทนกัน"""
    key = [_defect(n) for n in range(1, 5)]
    outs = [_out(1)] + [_out(n, disp=DISPOSITION_REFERRED) for n in (2, 3, 4)]
    r = score(key, outs).summary()
    assert r["layer_3_coverage"]["coverage"] == 1.0
    assert r["layer_1_automatic"]["f1"] != 1.0
    assert r["layer_1_automatic"]["recall"] == 0.25


def test_c22_uncovered_equals_the_automatic_false_negatives():
    key = [_defect(n) for n in range(1, 4)]
    r = score(key, [_out(1)]).summary()
    assert r["layer_3_coverage"]["uncovered"] == r["layer_1_automatic"]["fn"] == 2


# ══════════════════════════════════════════════════════════════════════════════
#  C4 — แรงจูงใจที่คำตัดสินนี้ตั้งใจตัดทิ้ง
# ══════════════════════════════════════════════════════════════════════════════


def test_c30_referring_everything_cannot_inflate_automatic_f1():
    """🔴 **ข้อบังคับที่เป็นเหตุผลของคำตัดสินทั้งข้อ**

    detector ที่ขี้เกียจ โยนทุกอย่างเข้าคิวมนุษย์ ต้องได้ ``F1`` ชั้น ① = 0
    และภาระการตรวจต้องพุ่ง — ตัวเลขต้องบอกความจริงข้อนี้เอง
    """
    key = [_defect(n) for n in range(1, 11)]
    lazy = [_out(n, disp=DISPOSITION_REFERRED) for n in range(1, 11)]

    r = score(key, lazy, records_total=1000).summary()
    assert r["layer_1_automatic"]["tp"] == 0
    assert r["layer_1_automatic"]["recall"] == 0.0
    assert r["layer_1_automatic"]["f1"] in (0.0, None)
    assert r["layer_3_coverage"]["coverage"] == 1.0, (
        "ความครอบคลุมสูงได้ — แต่ต้องอ่านคู่กับภาระการตรวจ")
    assert r["layer_2_referral"]["burden_per_1000"] == 10.0


def test_c31_referring_everything_never_beats_deciding_correctly():
    """เทียบสองระบบตรง ๆ — ระบบที่ตัดสินเองถูกต้องได้คะแนนชั้น ① สูงกว่าเสมอ"""
    key = [_defect(n) for n in range(1, 11)]
    lazy = [_out(n, disp=DISPOSITION_REFERRED) for n in range(1, 11)]
    decisive = [_out(n) for n in range(1, 11)]

    lazy_f1 = score(key, lazy, records_total=1000).summary()["layer_1_automatic"]["f1"]
    good_f1 = score(key, decisive, records_total=1000).summary()["layer_1_automatic"]["f1"]
    assert good_f1 == 1.0
    assert lazy_f1 in (0.0, None)


def test_c32_recall_denominator_includes_referred_defects():
    """ถ้าตัวหารไม่รวมรายการที่ส่งต่อ recall จะพุ่งเองโดยระบบไม่ได้เก่งขึ้น"""
    key = [_defect(n) for n in range(1, 11)]
    outs = [_out(1)] + [_out(n, disp=DISPOSITION_REFERRED) for n in range(2, 11)]
    a = score(key, outs).summary()["layer_1_automatic"]
    assert a["defects_in_scope"] == 10
    assert a["recall"] == 0.1, "ถ้าเป็น 1.0 แปลว่าตัวหารไม่รวมรายการที่ส่งต่อ"


# ══════════════════════════════════════════════════════════════════════════════
#  C5 — ตัวหารและรายการนอกขอบเขต
# ══════════════════════════════════════════════════════════════════════════════


def test_c40_out_of_scope_defects_are_reported_separately_not_as_fn():
    """🔴 หมวด 5.4 — ชนิดที่ประกาศไว้ว่าตรวจไม่ได้ ห้ามนับเป็น ``FN`` เงียบ ๆ"""
    key = [_defect(1), _defect(2, "F-01", in_scope=False)]
    r = score(key, [_out(1)]).summary()
    assert r["layer_1_automatic"]["fn"] == 0
    assert r["layer_1_automatic"]["defects_in_scope"] == 1
    assert r["denominators"]["out_of_scope_defects"] == 1
    assert r["denominators"]["defects_total"] == 2


def test_c41_finding_an_out_of_scope_defect_is_not_a_false_positive():
    """เจอของที่ประกาศว่าไม่คาดว่าจะเจอ — เป็นข่าวดี ไม่ใช่การเตือนผิด"""
    key = [_defect(2, "F-01", in_scope=False)]
    r = score(key, [_out(2, "F-01")]).summary()
    assert r["layer_1_automatic"]["fp"] == 0
    assert r["denominators"]["out_of_scope_detected"] == 1


def test_c42_every_denominator_is_declared():
    r = score([_defect(1)], [_out(1)], records_total=42).summary()
    for name in ("defects_total", "defects_in_scope", "out_of_scope_defects",
                 "out_of_scope_detected", "records_total"):
        assert name in r["denominators"], name
    assert r["denominators"]["records_total"] == 42


def test_c43_breakdown_by_defect_type_is_reported():
    key = [_defect(1, "V-01"), _defect(2, "V-01"), _defect(3, "S-03")]
    r = score(key, [_out(1), _out(3, disp=DISPOSITION_REFERRED)]).summary()
    bt = r["by_defect_type"]
    assert bt["V-01"]["injected"] == 2 and bt["V-01"]["tp"] == 1
    assert bt["V-01"]["missed"] == 1
    assert bt["S-03"]["referred_correct"] == 1


# ══════════════════════════════════════════════════════════════════════════════
#  C6 — กติกาการรายงาน
# ══════════════════════════════════════════════════════════════════════════════


def test_c50_report_always_contains_all_three_layers():
    """🔴 หมวด 5.5 ข้อ 1 — ห้ามรายงานตัวเลขเดียวเป็น "ความแม่นยำของระบบ" """
    r = score([_defect(1)], [_out(1)]).summary()
    assert {"layer_1_automatic", "layer_2_referral",
            "layer_3_coverage"} <= set(r)


def test_c51_raw_accuracy_is_never_reported():
    """🔴 หมวด 5.5 ข้อ 2 — true negative ท่วม ⇒ accuracy ดิบไร้ความหมาย"""
    import json

    blob = json.dumps(score([_defect(1)], [_out(1)]).summary())
    assert "accuracy" not in blob.lower()


def test_c52_schema_version_is_reported():
    r = score([], []).summary()
    assert r["schema_version"].startswith("t1b-scoring-3layer-")


def test_c53_unknown_disposition_is_refused_loudly():
    """🔴 ห้ามเดาแทนผู้รันว่าใบนี้เป็นการฟันธงหรือการส่งต่อ"""
    with pytest.raises(ValueError):
        DetectorOutput(output_id="x", finding_type="V-01",
                       location=_loc(1), disposition="MAYBE")


def test_c54_clean_negative_control_scores_as_expected():
    """หมวด 6 — แฟ้มสะอาดล้วน ระบบไม่ควรฟันธงอะไรเลย"""
    r = score([], [], records_total=1000).summary()
    assert r["layer_1_automatic"]["fp"] == 0
    assert r["layer_2_referral"]["referred_total"] == 0
    assert r["layer_2_referral"]["burden_per_1000"] == 0.0
    assert r["layer_3_coverage"]["coverage"] is None


def test_c55_scoring_module_is_separate_from_the_frozen_t1a_scorer():
    """🔴 ห้ามปนกับเครื่องให้คะแนน M-SET ของ T1A ที่ตรึงไว้แล้ว"""
    import inspect

    from redbook.t1b_eval import scoring

    src = inspect.getsource(scoring)
    assert "mset_reconcile" not in src
    assert "redbook.report" not in src and "from ..report" not in src
