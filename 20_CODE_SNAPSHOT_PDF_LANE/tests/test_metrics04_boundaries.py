"""ผลทดสอบสังเคราะห์ที่โบขอก่อนรับ implementation (#36 6911580651) — วิธีวัดผล 0.4 ร่าง ๒

ข้อมูลสมมติทั้งหมด ไม่เปิดชุดประเมิน:
1) ตัวหาร 0 / 1–9 / ≥ 10 ทั้งตัวรวมผล (trial_aggregate.rate) และค่าบนหน้าผู้ตรวจ (trial._rate)
2) สถานะยังตัดสินไม่ครบ = ไม่แสดงสัดส่วน
3) รอบเก่า 0.2 คงสูตรเดิม — ดู test_trial.py::test_worked_example_v02_round_keeps_old_denominator ·
   ::test_v02_zero_denominator_stays_old_text · test_trial.py::test_v02_rounds_keep_0_2_rules_after_upgrade และ
   ::test_v03_dashboard_hides_old_a2_card_and_marks_old_rates_as_supplementary (รันพร้อมไฟล์นี้)
4) รุ่นที่จะนำเข้าระบบ: ไฟล์หน้าจอที่ build แล้วไม่อ่านชื่อค่าที่ตัดไปแล้ว
"""
from pathlib import Path

import pytest

from redbook.services import trial
from redbook.services import trial_aggregate as ag

BOUNDARY = [  # (ตัวเศษ, ตัวหาร, ข้อความตัวรวมผล, ข้อความหน้าผู้ตรวจ, ร้อยละ)
    (0, 0, "คำนวณไม่ได้", "คำนวณไม่ได้", None),
    (1, 1, "1/1", "1 จาก 1", None),
    (5, 9, "5/9", "5 จาก 9", None),
    (7, 10, "7/10 (70.0%)", "7 จาก 10 (70.0%)", 70.0),
    (28, 33, "28/33 (84.8%)", "28 จาก 33 (84.8%)", 84.8),
]


@pytest.mark.parametrize("num,den,agg_text,ui_text,pct", BOUNDARY)
def test_denominator_boundaries_aggregate_and_reviewer_page(num, den, agg_text, ui_text, pct):
    a = ag.rate(num, den)
    assert (a["num"], a["den"], a["pct"], a["text"]) == (num, den, pct, agg_text)
    assert a["reason"] == ("denominator_zero" if den == 0 else "denominator_lt_10" if den < 10 else "")
    if den == 0:
        assert a["value"] is None                                  # ไม่ใช่ 0 หรือ 0%
    u = trial._rate(num, den)
    assert (u["num"], u["den"], u["pct"], u["text"]) == (num, den, pct, ui_text)
    assert ("%" in u["text"]) == (den >= 10)


@pytest.mark.parametrize("n0,exact,text", [(0, 0, "คำนวณไม่ได้"), (9, 4, "4/9"), (10, 4, "4/10 (40.0%)")])
def test_detection_on_n0_at_boundaries(n0, exact, text):
    rest = n0 - exact
    d = ag.issues({"N0": n0, "undecidable": 0, "exact": exact, "partial": 0, "miss": {"p1": rest}})["detection"]
    assert d["text"] == text and d["den"] == n0


@pytest.mark.parametrize("p,und,text", [(1, 1, "คำนวณไม่ได้"), (10, 1, "9/9"), (11, 1, "10/10 (100.0%)")])
def test_location_correct_excludes_undecidable_from_denominator(p, und, text):
    loc = ag.location({"all_sides": {"exact": p - und}, "undecidable": {"exact": und}}, P=p)
    assert loc["location_correct"]["text"] == text
    assert loc["all_over_P"]["den"] == p                         # ผลเสริมคงไว้ ตัวหาร P


@pytest.mark.parametrize("num,den", [(0, 0), (3, 5), (12, 20)])
def test_pending_shows_no_rate(num, den):
    u = trial._rate(num, den, ready=False)
    assert u["text"] == "ยังตัดสินไม่ครบ" and u["pct"] is None and "จาก" not in u["text"]


def test_shipped_build_reads_no_cut_fields():
    """ไฟล์หน้าจอที่ build แล้ว (รุ่นที่จะนำเข้าระบบ) ไม่อ่านชื่อค่าของ 0.3 ที่ 0.4 ตัดไป ·
    strict / with_partial / false_alarm ยังอยู่ได้ เพราะรอบก่อน 0.3 คงสูตรเดิม (Bo #44 6968338871)"""
    assets = Path(trial.__file__).resolve().parents[1] / "static" / "app" / "assets"
    js = "".join(p.read_text(encoding="utf-8") for p in assets.glob("index-*.js"))
    assert js
    for gone in (".H1.", ".H2.", "H2_exact", "H2_partial", ".supplement", "incl_partial", "A3_fidelity",
                 "A3_assertion", ".overflag", "meets_H3"):
        assert gone not in js, gone
    for kept in ("detection", "location_correct", "all_over_P"):
        assert kept in js, kept
