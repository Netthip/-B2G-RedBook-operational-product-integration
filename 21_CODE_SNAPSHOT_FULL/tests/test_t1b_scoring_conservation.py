# -*- coding: utf-8 -*-
"""T1B — schema การให้คะแนนแบบบัญชีปิดได้ (`t1b-scoring-3layer-0.2.0`)

🔴 `BO REVIEW COMPLETE — C/D SCORING CONSERVATION` (6 กันยายน 2569) ·
สเปก `LANE_C_BLIND_EVALUATION_PROTOCOL.md` §5.1–5.9 @ bridge `7f2390a`

ชุดนี้ครอบเจ็ดกลุ่มที่ Bo ระบุไว้ตรง ๆ

===  ==========================================================================
 #   สิ่งที่ต้องพิสูจน์
===  ==========================================================================
 1   ใบชนิดผิดเรียงมาก่อนใบชนิดถูก แต่ใบชนิดถูก **ยังต้องชนะ**
 2   ``defect_id`` / ``output_id`` ซ้ำ ⇒ ล้มดัง ๆ
 3   ใบซ้ำที่ตำแหน่ง exploratory เดิม **ไม่ได้เงินฟรี**
 4   ``REFERRAL_MISSED`` อิงชนิดที่ predeclared เท่านั้น
 5   ``referral precision``
 6   conservation ปิด **แยกกันในแต่ละ stratum**
 7   ตัวหารเป็นศูนย์ ⇒ ``None`` **ไม่ใช่** ``0``
===  ==========================================================================

🔴 ตัวเลขทุกตัวในไฟล์นี้เป็นตัวอย่างสังเคราะห์เพื่อวัด *ตัวสูตร*
**ไม่ใช่ผลการวัดระบบ** · ยังไม่มีชุดทดสอบและยังไม่มีเฉลย

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import pytest

from redbook.t1b_eval.scoring_v2 import (
    BUCKET_EXACT_AUTO,
    BUCKET_LOCTYPE_AUTO,
    BUCKET_REFERRED,
    BUCKET_UNCOVERED,
    DISPOSITION_AUTOMATIC,
    DISPOSITION_REFERRED,
    STRATUM_EXPLORATORY,
    STRATUM_PRIMARY,
    DetectorOutput,
    GoldDefect,
    Location,
    ScoringInputError,
    score,
)


def _loc(n: int) -> Location:
    return Location(sheet="Sheet5", row=n, cell=f"C{n}")


def _gold(n: int, dtype="V-01", stratum=STRATUM_PRIMARY) -> GoldDefect:
    return GoldDefect(f"D{n}", dtype, _loc(n), stratum)


def _out(n: int, ftype="V-01", disp=DISPOSITION_AUTOMATIC, sid="") -> DetectorOutput:
    return DetectorOutput(f"O{n}{sid}", ftype, _loc(n), disp)


def _primary(rep):
    return rep.strata[STRATUM_PRIMARY]


# ══════════════════════════════════════════════════════════════════════════════
#  1 — exact ต้องชนะ แม้ใบชนิดผิดจะเรียงมาก่อน
# ══════════════════════════════════════════════════════════════════════════════


def test_cv1_exact_wins_even_when_wrong_type_sorts_first():
    """🔴 gap ข้อ 6 ที่ Bo ตรวจโค้ดพบ

    ใบถูกเรียงตาม ``finding_type`` ⇒ ``V-00`` มาก่อน ``V-01`` ·
    ถ้าจับคู่ทีละใบ ใบชนิดผิดจะยึดข้อบกพร่องไปก่อน แล้วผลักใบชนิดถูกเป็น ``FP``
    ⇒ คะแนนขึ้นกับลำดับการอ่านไฟล์ ซึ่งเป็นสิ่งที่สเปกห้าม
    """
    gold = [_gold(1, "V-01")]
    outs = [_out(1, "V-00", sid="a"), _out(1, "V-01", sid="b")]

    s = _primary(score(gold, outs))
    assert s.exact_auto == 1, "ใบชนิดถูกต้องได้ข้อบกพร่องไป"
    assert s.loctype_auto == 0
    assert s.fp == 1, "ใบชนิดผิดที่เหลือต้องเป็น FP ไม่ใช่หายไป"


def test_cv2_result_is_independent_of_output_order():
    gold = [_gold(1, "V-01"), _gold(2, "V-05")]
    outs = [_out(1, "V-09", sid="a"), _out(1, "V-01", sid="b"), _out(2, "V-05")]
    a = score(gold, outs).summary()
    b = score(list(reversed(gold)), list(reversed(outs))).summary()
    assert a == b


def test_cv3_automatic_claims_before_referral_at_the_same_location():
    gold = [_gold(1)]
    outs = [_out(1, disp=DISPOSITION_REFERRED, sid="r"), _out(1, sid="a")]
    s = _primary(score(gold, outs))
    assert s.exact_auto == 1 and s.referred == 0
    assert s.referral_wrong == 1


# ══════════════════════════════════════════════════════════════════════════════
#  2 — id ซ้ำต้องล้มดัง ๆ
# ══════════════════════════════════════════════════════════════════════════════


def test_cv10_duplicate_defect_id_fails_loudly():
    """🔴 gap ข้อ 7 — id ซ้ำทำให้บัญชีกับชุดที่ claim แล้วไม่สอดคล้องกัน"""
    gold = [_gold(1), GoldDefect("D1", "V-05", _loc(2))]
    with pytest.raises(ScoringInputError) as err:
        score(gold, [])
    assert "defect_id" in str(err.value)


def test_cv11_duplicate_output_id_fails_loudly():
    with pytest.raises(ScoringInputError) as err:
        score([_gold(1)], [_out(1), DetectorOutput("O1", "V-05", _loc(2))])
    assert "output_id" in str(err.value)


def test_cv12_unknown_disposition_fails_loudly():
    with pytest.raises(ScoringInputError):
        score([], [DetectorOutput("O1", "V-01", _loc(1), "MAYBE")])


def test_cv13_unknown_stratum_fails_loudly():
    with pytest.raises(ScoringInputError):
        score([GoldDefect("D1", "V-01", _loc(1), "SOMETHING")], [])


# ══════════════════════════════════════════════════════════════════════════════
#  3 — ใบซ้ำไม่ได้เงินฟรี (รวมที่ตำแหน่ง exploratory)
# ══════════════════════════════════════════════════════════════════════════════


def test_cv20_duplicate_outputs_at_a_claimed_location_become_fp():
    """§5.2 — ใบที่สองเป็นต้นไปที่ชี้ข้อบกพร่องตัวเดิม **ไม่ได้คะแนนเพิ่ม**"""
    s = _primary(score([_gold(1)],
                       [_out(1, sid="a"), _out(1, sid="b"), _out(1, sid="c")]))
    assert s.exact_auto == 1
    assert s.fp == 2, "ใบซ้ำต้องมีต้นทุน"


def test_cv21_duplicate_exploratory_outputs_get_no_free_credit():
    """🔴 gap ข้อ 5 — เดิมนับด้วย location hit แบบไม่ one-to-one

    ใบซ้ำที่ตำแหน่ง exploratory เดิมจึงเพิ่ม ``out_of_scope_detected`` ได้เรื่อย ๆ
    โดยไม่มีต้นทุน · ตอนนี้ข้อบกพร่อง exploratory เป็น gold defect ปกติที่จับคู่
    หนึ่งต่อหนึ่ง ⇒ ใบที่สองเป็นต้นไปกลายเป็น ``FP`` ของ stratum นั้น
    """
    gold = [_gold(1, "F-01", STRATUM_EXPLORATORY)]
    outs = [_out(1, "F-01", sid="a"), _out(1, "F-01", sid="b"),
            _out(1, "F-01", sid="c")]
    rep = score(gold, outs)
    ex = rep.strata[STRATUM_EXPLORATORY]
    assert ex.exact_auto == 1
    assert ex.fp == 2
    assert STRATUM_PRIMARY not in rep.strata, "ห้ามปนเข้า PRIMARY"


def test_cv22_outputs_with_no_defect_anywhere_are_unattributed():
    """ใบที่ไม่มีข้อบกพร่องอยู่ที่ตำแหน่งนั้นเลย ระบุ stratum ไม่ได้

    🔴 รายงานแยก **ห้ามยัดเข้า stratum ใดเงียบ ๆ** — จุดนี้สเปกยังไม่ระบุ
    จึงเลือกทางที่เห็นได้ชัดแทนการเดา
    """
    rep = score([_gold(1)], [_out(1), _out(99, sid="x"),
                             _out(98, disp=DISPOSITION_REFERRED, sid="y")])
    assert rep.unattributed_fp == 1
    assert rep.unattributed_referral_wrong == 1
    assert _primary(rep).fp == 0


# ══════════════════════════════════════════════════════════════════════════════
#  4 · 5 — การส่งต่อ
# ══════════════════════════════════════════════════════════════════════════════


def test_cv30_referral_missed_uses_only_predeclared_types():
    """🔴 gap ข้อ 2 — ห้ามตัดสินย้อนหลังว่าอะไร "ควรถูกส่งต่อ"

    ``S-03`` ประกาศไว้ว่าพฤติกรรมปลอดภัยคือส่งต่อ · ``V-01`` ไม่ได้ประกาศ
    ⇒ ทั้งคู่หลุด แต่มีเพียง ``S-03`` ที่นับเป็น ``REFERRAL_MISSED``
    """
    gold = [_gold(1, "V-01"), _gold(2, "S-03")]
    s = _primary(score(gold, [], expected_referral_types=("S-03",)))
    assert s.uncovered == 2
    assert s.referral_missed == 1
    assert s.referral_missed <= s.uncovered, "ต้องเป็นสับเซตของ UNCOVERED"


def test_cv30b_referral_missed_is_a_view_on_uncovered_not_a_fifth_bucket():
    """🔴 กับดักที่เจ้าของสเปกเตือนไว้ตรง ๆ

    *"`REFERRAL_MISSED` เป็นมุมมองบนช่อง `UNCOVERED` ไม่ใช่ช่องที่ห้า —
    ถ้าโค้ดทำเป็นช่องแยก บัญชีจะรวมเกิน"*

    ชุดเดิมพิสูจน์ conservation **ตอน ``referral_missed`` เป็นศูนย์** และพิสูจน์
    ``referral_missed`` **ตอนไม่ได้ตรวจ conservation** ⇒ ไม่มีข้อไหนกัดกรณีที่
    ทั้งสองอย่างเกิดพร้อมกัน ซึ่งเป็นกรณีเดียวที่ข้อผิดนี้จะโผล่
    """
    gold = ([_gold(n, "S-03") for n in range(1, 6)]        # ควรส่งต่อ · หลุด 4
            + [_gold(n, "V-01") for n in range(10, 13)])   # ไม่ประกาศ · หลุด 2
    outs = [_out(1, "S-03", disp=DISPOSITION_REFERRED), _out(10, "V-01")]

    rep = score(gold, outs, records_total=1000,
                expected_referral_types=("S-03",))
    s = _primary(rep)

    assert s.referral_missed == 4, "S-03 ที่หลุดทั้งสี่ตัว"
    assert s.uncovered == 6, "หลุดจริงหกตัว (S-03 สี่ + V-01 สอง)"
    assert s.referral_missed < s.uncovered, "ต้องเป็นสับเซตแท้ ไม่ใช่ทั้งช่อง"

    # 🔴 หัวใจ — บัญชีต้องยังปิดพอดี ไม่รวมเกินเพราะ referral_missed
    assert s.defects_total == len(gold) == 8
    assert (s.exact_auto + s.loctype_auto + s.referred + s.uncovered) == 8
    assert rep.conservation_ok()
    assert s.coverage + s.uncovered_rate == pytest.approx(1.0)


def test_cv31_referral_missed_is_zero_without_a_declaration():
    """ไม่ประกาศล่วงหน้า ⇒ ไม่มีสิทธิ์อ้างว่า "ควรส่งต่อ" """
    s = _primary(score([_gold(1, "S-03")], []))
    assert s.referral_missed == 0
    assert s.referral_recall is None, "ไม่มีทั้งตัวตั้งและตัวหาร ⇒ ไม่นิยาม"


def test_cv32_referral_precision_penalises_dumping_everything():
    """🔑 recall ที่สูงเพราะส่งทุกอย่างเข้าคิว ต้องถูกลงโทษที่ precision ทันที"""
    gold = [_gold(n) for n in range(1, 4)]
    outs = [_out(n, disp=DISPOSITION_REFERRED) for n in range(1, 4)]
    outs += [_out(100 + n, disp=DISPOSITION_REFERRED) for n in range(20)]

    rep = score(gold, outs, records_total=1000,
                expected_referral_types=("V-01",))
    s = _primary(rep)
    assert s.referred == 3 and s.referral_recall == 1.0
    total_wrong = s.referral_wrong + rep.unattributed_referral_wrong
    assert total_wrong == 20
    assert s.referral_precision == pytest.approx(3 / 3), (
        "referral_precision ของ stratum นับเฉพาะใบที่ผูก stratum ได้")
    assert rep.unattributed_referral_wrong == 20, (
        "ใบที่ยิงไปที่ตำแหน่งที่ไม่มีข้อบกพร่องเลย ต้องปรากฏและมีต้นทุน")


def test_cv33_burden_counts_both_correct_and_wrong_referrals():
    gold = [_gold(1)]
    outs = [_out(1, disp=DISPOSITION_REFERRED, sid="a"),
            _out(1, disp=DISPOSITION_REFERRED, sid="b")]
    s = _primary(score(gold, outs, records_total=2000))
    assert s.referred == 1 and s.referral_wrong == 1
    assert s.review_burden_per_1000 == 1.0


# ══════════════════════════════════════════════════════════════════════════════
#  6 — conservation แยกราย stratum
# ══════════════════════════════════════════════════════════════════════════════


def test_cv40_conservation_closes_in_each_stratum_separately():
    """🔴 §5.7 ข้อ 1 — บัญชีต้องปิดแยกกัน แล้วจึงรวม"""
    gold = ([_gold(n, "V-01", STRATUM_PRIMARY) for n in range(1, 8)]
            + [_gold(n, "F-01", STRATUM_EXPLORATORY) for n in range(20, 24)])
    outs = ([_out(1), _out(2), _out(3, "V-09")]
            + [_out(4, disp=DISPOSITION_REFERRED)]
            + [_out(20, "F-01")])

    rep = score(gold, outs, records_total=500)
    assert rep.conservation_ok()

    p = rep.strata[STRATUM_PRIMARY]
    assert p.defects_total == 7
    assert (p.exact_auto, p.loctype_auto, p.referred, p.uncovered) == (2, 1, 1, 3)

    e = rep.strata[STRATUM_EXPLORATORY]
    assert e.defects_total == 4
    assert e.exact_auto == 1 and e.uncovered == 3


def test_cv41_coverage_plus_uncovered_rate_is_exactly_one():
    gold = [_gold(n) for n in range(1, 6)]
    rep = score(gold, [_out(1), _out(2, disp=DISPOSITION_REFERRED)])
    s = _primary(rep)
    assert s.coverage + s.uncovered_rate == pytest.approx(1.0)
    assert s.coverage_conserved


def test_cv42_worked_example_from_the_spec_balances():
    """ตัวอย่าง 100 ข้อบกพร่องในสเปก §5.8 — บัญชีต้องปิดจริง

    🔴 ตัวเลขเป็นตัวอย่างสังเคราะห์ **ไม่ใช่ผลการวัดใด ๆ**
    """
    gold, outs = [], []
    n = 0

    def add(count, bucket):
        nonlocal n
        for _ in range(count):
            n += 1
            gold.append(_gold(n, "V-01"))
            if bucket == BUCKET_EXACT_AUTO:
                outs.append(_out(n, "V-01"))
            elif bucket == BUCKET_LOCTYPE_AUTO:
                outs.append(_out(n, "V-99"))
            elif bucket == BUCKET_REFERRED:
                outs.append(_out(n, "V-01", DISPOSITION_REFERRED))

    add(62, BUCKET_EXACT_AUTO)
    add(8, BUCKET_LOCTYPE_AUTO)
    add(21, BUCKET_REFERRED)
    add(9, BUCKET_UNCOVERED)

    for i in range(14):            # FP ที่ตำแหน่งไม่มีข้อบกพร่อง
        outs.append(_out(1000 + i, "V-01"))
    for i in range(35):            # REFERRAL_WRONG
        outs.append(_out(2000 + i, "V-01", DISPOSITION_REFERRED))

    rep = score(gold, outs, records_total=10_000)
    s = _primary(rep)

    assert s.defects_total == 100
    assert (s.exact_auto, s.loctype_auto, s.referred, s.uncovered) == (62, 8, 21, 9)
    assert rep.unattributed_fp == 14 and rep.unattributed_referral_wrong == 35
    assert rep.total_outputs() == 140
    assert rep.conservation_ok()

    assert s.recall == pytest.approx(0.620)
    assert s.coverage == pytest.approx(0.910)
    assert s.uncovered_rate == pytest.approx(0.090)


def test_cv42b_spec_precision_is_reproducible_only_under_the_folded_reading():
    """🔴 จุดที่สเปกยังไม่ระบุ — ต้องให้เจ้าของสเปกตัดสิน

    §5.8 ให้ ``precision ① = 62/(62+8+14) = 0.738`` ซึ่งวาง ``FP`` ไว้ **ใน**
    ตารางของ stratum · แต่ใบที่ยิงไปยังตำแหน่งที่ไม่มีข้อบกพร่องใดเลย
    ไม่มีข้อมูลพอจะบอกว่าควรอยู่ stratum ไหน

    โมดูลเก็บทั้งสองมุมมองไว้ **แทนที่จะเลือกเงียบ ๆ** — เทสต์นี้ตรึงทั้งคู่
    """
    gold, outs = [], []
    n = 0
    for count, ftype, disp in ((62, "V-01", DISPOSITION_AUTOMATIC),
                               (8, "V-99", DISPOSITION_AUTOMATIC),
                               (21, "V-01", DISPOSITION_REFERRED)):
        for _ in range(count):
            n += 1
            gold.append(_gold(n, "V-01"))
            outs.append(_out(n, ftype, disp))
    for _ in range(9):
        n += 1
        gold.append(_gold(n, "V-01"))
    outs += [_out(1000 + i, "V-01") for i in range(14)]
    outs += [_out(2000 + i, "V-01", DISPOSITION_REFERRED) for i in range(35)]

    rep = score(gold, outs, records_total=10_000)

    # มุมมองที่ 1 — แยกกอง (ค่าเริ่มต้นของโมดูล)
    assert _primary(rep).precision == pytest.approx(62 / 70)

    # มุมมองที่ 2 — รวมเข้า PRIMARY · ตรงกับตัวอย่างในสเปก
    folded = rep.folded(STRATUM_PRIMARY)
    assert folded.precision == pytest.approx(0.738, abs=5e-4)
    assert folded.referral_precision == pytest.approx(21 / 56)
    assert folded.location_accuracy == pytest.approx(70 / 84)
    # 🔴 การรวมเข้าต้องไม่ทำให้บัญชีข้อบกพร่องเปลี่ยน
    assert folded.defects_total == 100
    assert folded.coverage == pytest.approx(0.910)


def test_cv42c_summary_never_shows_only_the_flattering_reading():
    """🔴 ข้อบกพร่องเชิงการนำเสนอ — ค่าเริ่มต้นเข้าข้างตัวเอง

    detector ที่จับถูก **1 ใบ** แล้วยิงมั่วในที่ว่างอีก **4 ใบ**
    ได้ ``precision`` = **1.0** แบบแยกกอง แต่ **0.2** แบบรวมเข้า
    ⇒ ผู้ที่เรียก ``summary()`` แล้วรายงานค่าที่เห็น จะรายงานด้านที่ดีกว่าเสมอ
    โดยไม่รู้ว่ามีอีกด้าน · ตราบใดที่ยังไม่มีคำตัดสิน **ต้องเห็นทั้งคู่**
    """
    gold = [_gold(n) for n in range(1, 4)]
    outs = [_out(1)] + [_out(900 + i, sid="w") for i in range(4)]
    rep = score(gold, outs, records_total=1000)

    assert _primary(rep).precision == 1.0
    assert rep.folded().precision == pytest.approx(0.2)

    head = rep.summary()["headline_readings_OPEN"]
    assert head["status"].startswith("OPEN")
    assert head[STRATUM_PRIMARY]["separated"]["precision"] == 1.0
    assert head[STRATUM_PRIMARY]["folded"]["precision"] == pytest.approx(0.2)
    assert head[STRATUM_PRIMARY]["agree"] is False

    # ทั้งสองค่าต้องปรากฏในผลที่ serialise แล้ว ไม่ใช่ซ่อนอยู่หลัง method
    import json

    blob = json.dumps(rep.summary(), ensure_ascii=False)
    assert "0.2" in blob and "OPEN" in blob


def test_cv42e_stratum_block_discloses_outputs_that_live_outside_it():
    """🔴 ร้ายกว่าเรื่องตัวเลขต่างห้าเท่า — บล็อกที่สอดคล้องกันเองแต่ไม่ครบ

    เดิมในบล็อกของ `PRIMARY` มี ``precision = 1.0`` คู่กับ ``FP = 0``
    และ ``total = 1`` ทั้งที่ระบบออกมา **ห้าใบ** ⇒ สองค่าแรกสอดคล้องกันเอง
    คนอ่านจึงไม่มีทางสงสัย · ตัวสร้างรายงานที่ดึงบล็อกนี้ไปตรง ๆ จะรายงานว่า
    *"1 ใบ · ไม่มีการเตือนผิด · precision 1.0"* ให้ detector ที่ผิดสี่ในห้าใบ
    """
    gold = [_gold(n) for n in range(1, 4)]
    outs = [_out(1)] + [_out(900 + i, sid="w") for i in range(4)]
    block = score(gold, outs, records_total=1000).summary()["strata"][STRATUM_PRIMARY]

    o = block["outputs"]
    assert o["total_in_this_stratum"] == 1
    assert "total" not in o, "ชื่อเดิมกำกวม อ่านได้ว่าเป็นยอดรวมทั้งหมด"
    assert o["unattributed_elsewhere"]["FP"] == 4
    assert "🔴" in o and "ไม่อยู่ในยอดของบล็อกนี้" in o["🔴"]


def test_cv42g_review_burden_discloses_referrals_outside_the_stratum():
    """🔴 ตัวเลขที่คำตัดสินสามชั้นทั้งข้อสร้างขึ้นมาเพื่อปกป้อง — ต่ำกว่าจริง 31 เท่า

    ภาระการตรวจคือ **ต้นทุนที่ตกกับคน** · Bo ตัดสินให้แยกสามชั้นก็เพื่อไม่ให้
    การโยนทุกอย่างเข้าคิวดูดี และด่านคือ *"referral recall ต้องอ่านคู่กับภาระ"*

    แต่ ``burden_per_1000`` คิดจากใบส่งต่อของ stratum นี้เท่านั้น ⇒ ใบที่ยิงมั่ว
    ไปในที่ว่าง **ไม่ปรากฏเป็นภาระเลย** · ฉากนี้: ส่งต่อจริง 31 ใบ (ถูก 1 มั่ว 30)

    | ตัวเลข | ค่า |
    |---|---|
    | ``burden`` ของ stratum | **1.0** |
    | ``burden`` จริง (folded) | **31.0** |

    และในบล็อกเดียวกัน ``referral_precision`` = 1.0 · ``referral_recall`` = 1.0
    ⇒ สี่ค่าสอดคล้องกันเองว่า *"สมบูรณ์แบบ แทบไม่มีต้นทุน"*
    """
    gold = [_gold(n) for n in range(1, 4)]
    outs = [_out(1, disp=DISPOSITION_REFERRED)]
    outs += [_out(900 + i, disp=DISPOSITION_REFERRED, sid="w") for i in range(30)]
    rep = score(gold, outs, records_total=1000)

    assert _primary(rep).review_burden_per_1000 == 1.0
    assert rep.folded().review_burden_per_1000 == 31.0

    head = rep.summary()["headline_readings_OPEN"][STRATUM_PRIMARY]
    assert head["separated"]["burden_per_1000"] == 1.0
    assert head["folded"]["burden_per_1000"] == 31.0
    assert head["agree"] is False, "ภาระต่างกัน 31 เท่า ต้องไม่บอกว่าตรงกัน"

    layer2 = rep.summary()["strata"][STRATUM_PRIMARY]["layer_2_referral"]
    assert "🔴" in layer2 and "ไม่ได้นับใน burden_per_1000" in layer2["🔴"]


#: 🔴 checklist ห้าจุดจากเจ้าของสเปก (§5.11 ข้อ 6 · bridge `789c1df`)
#:
#: เส้นแบ่ง: ตัวเลขที่มี **ใบของ detector** อยู่ในสมการ ⇒ ต้องประกาศตัวเอง ·
#: ตัวเลขที่คิดจาก **ข้อบกพร่องล้วน** ⇒ ไม่ต้อง เพราะข้อบกพร่องทุกตัวมี stratum เสมอ
MUST_DECLARE = {
    "layer_1_automatic": ("precision", "location_accuracy"),
    "layer_2_referral": ("referral_precision", "burden_per_1000"),
    "outputs": ("total_in_this_stratum",),
}
NEED_NOT_DECLARE = {
    "layer_1_automatic": ("recall", "f1"),
    "layer_2_referral": ("referral_recall", "referral_missed"),
    "layer_3_coverage": ("coverage", "uncovered_rate"),
}


def test_cv42i_every_block_holding_output_derived_metrics_declares_itself():
    """🔴 ไล่ตรวจ **ทั้ง checklist** ไม่ใช่เฉพาะจุดที่นึกออก

    ชั้นที่สี่ (`burden`) หาไม่เจอจากการอ่านโค้ด แต่เจอจากการไล่ตรวจกติกา ·
    ชั้นที่ห้า (`layer_1_automatic`) ก็เช่นกัน — ตอนแก้ `burden` ผมใส่คำเตือน
    ที่ `outputs` และ `layer_2_referral` แต่ **ลืม `layer_1_automatic`**
    ซึ่งถือสองในห้าจุดของ checklist

    ⇒ เทสต์นี้จึงวนทุกบล็อกตามตาราง ไม่ใช่เขียนทีละจุด
    """
    gold = [_gold(n) for n in range(1, 4)]
    outs = [_out(1)]                                            # ฟันธงถูก 1
    outs += [_out(800 + i, sid="f") for i in range(6)]          # ฟันธงมั่ว 6
    outs += [_out(900 + i, disp=DISPOSITION_REFERRED, sid="w")  # ส่งต่อมั่ว 4
             for i in range(4)]
    blk = score(gold, outs, records_total=1000).summary()["strata"][STRATUM_PRIMARY]

    for name, metrics in MUST_DECLARE.items():
        assert "🔴" in blk[name], (
            f"บล็อก {name} ถือ {metrics} ซึ่งมีใบของ detector ในสมการ "
            f"แต่ไม่ประกาศว่ามีใบอยู่นอก stratum")
        for m in metrics:
            assert m in blk[name], f"{name} ต้องมี {m}"

    # ค่าที่ไม่ต้องประกาศ ต้องยังอยู่ครบ — การเพิ่มคำเตือนต้องไม่ทำให้ค่าหาย
    for name, metrics in NEED_NOT_DECLARE.items():
        for m in metrics:
            assert m in blk[name], f"{name}.{m} หายไป"


def test_cv42j_no_block_cries_wolf_when_nothing_is_outside():
    """ไม่มีใบอยู่นอก stratum ⇒ ไม่มีบล็อกไหนควรมีคำเตือน"""
    blk = score([_gold(1)], [_out(1)],
                records_total=1000).summary()["strata"][STRATUM_PRIMARY]
    for name in MUST_DECLARE:
        assert "🔴" not in blk[name], f"{name} เตือนทั้งที่ไม่มีอะไรอยู่นอก"


def test_cv42h_agree_flag_covers_burden_not_just_precision():
    """``agree`` ต้องเป็นเท็จเมื่อ **ตัวใดตัวหนึ่ง** ต่างกัน ไม่ใช่เฉพาะ precision"""
    gold = [_gold(1)]
    outs = [_out(1, disp=DISPOSITION_REFERRED)]
    outs += [_out(900 + i, disp=DISPOSITION_REFERRED, sid="w") for i in range(5)]
    head = score(gold, outs, records_total=1000).summary()[
        "headline_readings_OPEN"][STRATUM_PRIMARY]

    # precision ของทั้งสองการอ่านเท่ากัน (ไม่มีใบฟันธงเลย ⇒ None ทั้งคู่)
    assert head["separated"]["precision"] == head["folded"]["precision"]
    # แต่ภาระต่างกัน ⇒ ต้องไม่บอกว่าตรงกัน
    assert head["separated"]["burden_per_1000"] != head["folded"]["burden_per_1000"]
    assert head["agree"] is False


def test_cv42f_stratum_block_stays_quiet_when_nothing_is_outside():
    """ไม่มีใบอยู่นอก stratum ⇒ ไม่ต้องมีคำเตือน แต่ยังต้องมีตัวเลขให้เห็น"""
    o = score([_gold(1)], [_out(1)]).summary()["strata"][STRATUM_PRIMARY]["outputs"]
    assert o["unattributed_elsewhere"] == {"FP": 0, "REFERRAL_WRONG": 0}
    assert "🔴" not in o


def test_cv42d_readings_are_marked_as_agreeing_when_they_do():
    """ไม่มีใบที่ระบุ stratum ไม่ได้ ⇒ สองการอ่านต้องตรงกัน และบอกว่าตรง"""
    rep = score([_gold(1)], [_out(1)], records_total=100)
    head = rep.summary()["headline_readings_OPEN"]
    assert head[STRATUM_PRIMARY]["agree"] is True


def test_cv43_coverage_is_not_the_same_as_automatic_f1():
    """§5.5 — ห้ามรายงานแทนกัน · `LOCTYPE_AUTO` นับ coverage แต่ไม่นับ exact"""
    gold = [_gold(n) for n in range(1, 5)]
    outs = [_out(1)] + [_out(n, "V-99") for n in (2, 3, 4)]
    s = _primary(score(gold, outs))
    assert s.coverage == 1.0
    assert s.recall == 0.25
    assert s.f1 != 1.0


def test_cv44_wrong_type_guess_costs_precision():
    """§5.3 — `LOCTYPE_AUTO` อยู่ในตัวหารของ precision"""
    gold = [_gold(1, "V-01"), _gold(2, "V-01")]
    s = _primary(score(gold, [_out(1, "V-01"), _out(2, "V-99")]))
    assert s.automatic_outputs == 2
    assert s.precision == 0.5
    assert s.location_accuracy == 1.0


# ══════════════════════════════════════════════════════════════════════════════
#  7 — ตัวหารเป็นศูนย์ ⇒ None
# ══════════════════════════════════════════════════════════════════════════════


def test_cv50_zero_denominators_return_none_not_zero():
    rep = score([], [], records_total=0)
    assert rep.strata == {}
    assert rep.conservation_ok()

    s = _primary(score([_gold(1)], []))
    assert s.precision is None, "ไม่มีใบฟันธงเลย ⇒ precision ไม่นิยาม"
    assert s.referral_precision is None
    assert s.review_burden_per_1000 is None, "ไม่ประกาศตัวหาร ⇒ ห้ามเดา"
    assert s.recall == 0.0, "มีข้อบกพร่องแต่จับไม่ได้ ⇒ 0 ไม่ใช่ None"


def test_cv51_report_never_contains_raw_accuracy():
    import json

    blob = json.dumps(score([_gold(1)], [_out(1)]).summary())
    assert "accuracy" not in blob.lower().replace("location_accuracy", "")


def test_cv52_schema_version_and_spec_source_are_reported():
    r = score([], []).summary()
    assert r["schema_version"] == "t1b-scoring-3layer-0.2.0"
    assert "7f2390a" in r["spec_source"]


def test_cv53_v01_is_kept_and_marked_pre_conservation():
    """🔴 Bo สั่งว่า "อย่า rewrite `0.1.0` history" — ต้องยังอยู่และถูกติดป้าย"""
    from redbook.t1b_eval import scoring as v1

    assert v1.SCORING_SCHEMA_VERSION == "t1b-scoring-3layer-0.1.0"
    assert "PRE-CONSERVATION" in (v1.__doc__ or "")
