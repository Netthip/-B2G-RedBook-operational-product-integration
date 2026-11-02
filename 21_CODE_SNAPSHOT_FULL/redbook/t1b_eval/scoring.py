# -*- coding: utf-8 -*-
"""T1B — schema การให้คะแนนสามชั้น · 🔴 `PRE-CONSERVATION DRAFT`

> ## 🔴 `PRE-CONSERVATION DRAFT — SUPERSEDED FOR FREEZE PURPOSES`
>
> `BO REVIEW COMPLETE — C/D SCORING CONSERVATION` (6 กันยายน 2569) ตรวจโค้ดนี้
> แล้วพบช่องว่าง **แปดข้อ** เทียบกับสเปก `7f2390a` §5.1–5.9
> ⇒ เวอร์ชันนี้ **ตรึงไม่ได้** และห้ามใช้เป็นฐานของการประกาศเกณฑ์ใด
>
> ใช้ :mod:`redbook.t1b_eval.scoring_v2` (`t1b-scoring-3layer-0.2.0`) แทน
>
> **ห้ามลบไฟล์นี้และห้ามแก้ตรรกะ** — Bo สั่งว่า *"อย่า rewrite `0.1.0` history"*
> เก็บไว้พร้อมเทสต์ 29 ข้อในฐานะบันทึกว่าเคยตัดสินอย่างไร · เทสต์ชุดนั้น
> พิสูจน์ **เฉพาะ semantics ของฉบับเดิม** ไม่ใช่สเปก `7f2390a`


🔴 คำสั่ง Bo · `BO REVIEW COMPLETE` (Issue #1) · LANE C

    *"Do not force human-review referrals into a binary TP/FP choice. …
    A referral is not an automatic TP and is not automatically an FP.
    It must be scored in its own stratum. This decision removes the incentive
    to inflate F1 by sending everything to review."*

    *"Before generating any answer key: **freeze the revised protocol and
    scoring schema** …"*

เอกสาร `LANE_C_BLIND_EVALUATION_PROTOCOL.md` หมวด 5 บรรยายสามชั้นไว้เป็นตาราง
โมดูลนี้ทำให้ตารางนั้น **รันได้และทดสอบได้** — เพราะ schema ที่ตรึงไม่ได้แปลว่า
"เขียนไว้ในเอกสาร" แต่แปลว่า **มีนิยามเดียวที่ตีความไม่ได้สองแบบ**

🔴 **โมดูลนี้ไม่สร้างเฉลย ไม่ใส่ข้อบกพร่อง และไม่รู้จักแฟ้มใด** — เป็นฟังก์ชัน
บริสุทธิ์ที่รับ *เฉลย* กับ *ผลของ detector* แล้วคืนตัวเลข · การสร้าง generator
ยังถูกระงับตามคำสั่ง Bo และโมดูลนี้ไม่ปลดล็อกข้อนั้น

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

from dataclasses import dataclass, field

SCORING_SCHEMA_VERSION = "t1b-scoring-3layer-0.1.0"

# ------------------------------------------------------------------ ท่าทีของระบบ
#: ระบบ **ฟันธงเอง** ว่าเป็นปัญหา — เข้าชั้น ① เท่านั้น
DISPOSITION_AUTOMATIC = "AUTOMATIC"
#: ระบบ **ส่งต่อให้มนุษย์ตัดสิน** — เข้าชั้น ② เท่านั้น
#: 🔴 ไม่ใช่ TP อัตโนมัติ และไม่ใช่ FP อัตโนมัติ
DISPOSITION_REFERRED = "REFERRED"

DISPOSITIONS = frozenset({DISPOSITION_AUTOMATIC, DISPOSITION_REFERRED})


@dataclass(frozen=True)
class Location:
    """ตำแหน่งหลักฐานหนึ่งจุด — เทียบกันด้วย **ความเท่ากันแบบตรงตัว**

    🔴 ห้ามจับคู่แบบ "ใกล้กัน" หรือ "ภายใน ±n แถว" ด้วยเหตุผลเดียวกับที่ชั้นจับคู่
    ของเครื่องยนต์ห้าม fuzzy — ผู้ให้คะแนนต้องอธิบายได้ว่าทำไมใบนี้ถือว่าตรง
    การผ่อนเกณฑ์ตำแหน่งคือการทำให้คะแนนดีขึ้นโดยที่ระบบไม่ได้ดีขึ้น
    """

    sheet: str
    row: int
    cell: str = ""

    def matches(self, other: "Location") -> bool:
        return (self.sheet, self.row, self.cell) == (other.sheet, other.row, other.cell)


@dataclass(frozen=True)
class InjectedDefect:
    """ข้อบกพร่องหนึ่งตัวในเฉลย

    ``in_scope=False`` = ชนิดที่ **ประกาศไว้ล่วงหน้าแล้วว่าตรวจไม่ได้** ในหมวด 4
    ของโปรโตคอล ⇒ ต้องรายงานแยก 🔴 **ห้ามนับเป็น ``FN`` เงียบ ๆ**
    """

    defect_id: str
    defect_type: str
    location: Location
    in_scope: bool = True


@dataclass(frozen=True)
class DetectorOutput:
    """สิ่งที่ detector ออกมาหนึ่งใบ พร้อม **ท่าที** ของระบบต่อใบนั้น"""

    output_id: str
    finding_type: str
    location: Location
    disposition: str = DISPOSITION_AUTOMATIC

    def __post_init__(self):
        if self.disposition not in DISPOSITIONS:
            raise ValueError(
                f"ท่าทีของระบบต้องเป็นหนึ่งใน {sorted(DISPOSITIONS)} "
                f"ได้ {self.disposition!r} — 🔴 ห้ามเดาแทนผู้รัน"
            )


# ══════════════════════════════════════════════════════════════════════════════
#  ผลลัพธ์รายชั้น
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class AutomaticLayer:
    """ชั้น ① — เฉพาะรายการที่ระบบ **ฟันธงเอง**"""

    tp: int = 0
    #: ตำแหน่งถูก ชนิดผิด — 🔴 **นับแยก ห้ามรวมกับ ``tp``**
    tp_location_only: int = 0
    fp: int = 0
    #: ข้อบกพร่องที่ทั้งไม่ฟันธงและไม่ส่งต่อ
    fn: int = 0
    #: ตัวหารของ recall = ข้อบกพร่องที่อยู่ในขอบเขตทั้งหมด
    defects_in_scope: int = 0

    @property
    def automatic_outputs(self) -> int:
        """จำนวนใบที่ระบบฟันธงทั้งหมด = ตัวหารของ precision"""
        return self.tp + self.tp_location_only + self.fp

    @property
    def precision(self) -> float | None:
        """🔴 ตัวหารคือ **ทุกใบที่ระบบฟันธง** รวม ``tp_location_only`` ด้วย

        การฟันธงถูกที่แต่ผิดชนิดยังเป็นการยืนยันที่ไม่ถูกต้อง จึงต้องมีต้นทุน
        มิฉะนั้นการเดาชนิดมั่ว ๆ จะกลายเป็นการกระทำที่ไม่มีโทษ
        """
        n = self.automatic_outputs
        return (self.tp / n) if n else None

    @property
    def recall(self) -> float | None:
        """🔴 ตัวหารคือ **ข้อบกพร่องในขอบเขตทั้งหมด** รวมที่ถูกส่งต่อด้วย

        นี่คือหัวใจของคำตัดสิน Bo — ถ้าตัวหารไม่รวมรายการที่ถูกส่งต่อ
        การโยนของยากเข้าคิวมนุษย์จะดัน recall ① ขึ้นเองโดยที่ระบบไม่ได้เก่งขึ้น
        """
        return (self.tp / self.defects_in_scope) if self.defects_in_scope else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)


@dataclass(frozen=True)
class ReferralLayer:
    """ชั้น ② — การส่งต่อให้มนุษย์

    ตอบคนละคำถามกับชั้น ① — *"พาคนไปดูถูกที่หรือเปล่า"* ไม่ใช่ *"ตัดสินถูกหรือเปล่า"*
    """

    correct: int = 0
    wrong: int = 0
    #: ข้อบกพร่องที่ควรถูกส่งต่อแต่ไม่ถูกส่ง และระบบก็ไม่ฟันธง (= ``fn`` ของชั้น ①)
    missed: int = 0
    referred_total: int = 0
    records_total: int = 0

    @property
    def recall(self) -> float | None:
        n = self.correct + self.missed
        return (self.correct / n) if n else None

    @property
    def burden_per_1000(self) -> float | None:
        """ภาระการตรวจต่อ 1,000 record

        🔴 **ต้องอ่านคู่กับ ``recall`` เสมอ** — referral recall ที่สูงเพราะส่งทุกอย่าง
        เข้าคิวไม่มีค่าในทางปฏิบัติ ตัวเลขคู่นี้แยกกันอ่านไม่ได้
        """
        if not self.records_total:
            return None
        return self.referred_total * 1000 / self.records_total


@dataclass(frozen=True)
class CoverageLayer:
    """ชั้น ③ — ความครอบคลุมรวมของ **กระบวนการทั้งกระบวนการ** (ระบบ + คน)"""

    covered: int = 0
    uncovered: int = 0

    @property
    def total(self) -> int:
        return self.covered + self.uncovered

    @property
    def coverage(self) -> float | None:
        return (self.covered / self.total) if self.total else None


@dataclass(frozen=True)
class ScoreReport:
    """ผลครบสามชั้น + ตัวหารที่ต้องประกาศทุกครั้ง

    🔴 ``summary()`` คืนทั้งสามชั้นเสมอ **ไม่มีทางเรียกเอาชั้นเดียว** —
    เพราะกติกาข้อ 1 ของหมวด 5.5 ห้ามรายงานตัวเลขเดียวว่าเป็น "ความแม่นยำของระบบ"
    """

    automatic: AutomaticLayer
    referral: ReferralLayer
    coverage: CoverageLayer
    #: ข้อบกพร่องชนิดที่ประกาศไว้ว่าตรวจไม่ได้ — รายงานแยก ห้ามปนกับ ``fn``
    out_of_scope_defects: int = 0
    out_of_scope_detected: int = 0
    defects_total: int = 0
    records_total: int = 0
    by_defect_type: dict[str, dict[str, int]] = field(default_factory=dict)
    schema_version: str = SCORING_SCHEMA_VERSION

    def summary(self) -> dict[str, object]:
        a, r, c = self.automatic, self.referral, self.coverage
        return {
            "schema_version": self.schema_version,
            "layer_1_automatic": {
                "tp": a.tp, "tp_location_only": a.tp_location_only,
                "fp": a.fp, "fn": a.fn,
                "automatic_outputs": a.automatic_outputs,
                "defects_in_scope": a.defects_in_scope,
                "precision": a.precision, "recall": a.recall, "f1": a.f1,
            },
            "layer_2_referral": {
                "correct": r.correct, "wrong": r.wrong, "missed": r.missed,
                "referred_total": r.referred_total,
                "recall": r.recall, "burden_per_1000": r.burden_per_1000,
            },
            "layer_3_coverage": {
                "covered": c.covered, "uncovered": c.uncovered,
                "coverage": c.coverage,
            },
            "denominators": {
                "defects_total": self.defects_total,
                "defects_in_scope": a.defects_in_scope,
                "out_of_scope_defects": self.out_of_scope_defects,
                "out_of_scope_detected": self.out_of_scope_detected,
                "records_total": self.records_total,
            },
            "by_defect_type": self.by_defect_type,
        }


# ══════════════════════════════════════════════════════════════════════════════
#  การให้คะแนน
# ══════════════════════════════════════════════════════════════════════════════


def _sort_key(o: DetectorOutput) -> tuple:
    """ลำดับการจับคู่ที่ **กำหนดแน่นอน** — ผลต้องไม่ขึ้นกับลำดับที่ผู้เรียกส่งเข้ามา"""
    return (o.location.sheet, o.location.row, o.location.cell,
            o.finding_type, o.output_id)


def score(
    answer_key: list[InjectedDefect],
    detector_output: list[DetectorOutput],
    *,
    records_total: int = 0,
) -> ScoreReport:
    """ให้คะแนนครบสามชั้นจากเฉลยและผลของ detector

    **กติกาการจับคู่**

    1. ตำแหน่งต้องตรง **แบบตรงตัว** (ดู :meth:`Location.matches`)
    2. หนึ่งใบของ detector จับได้กับข้อบกพร่อง **ไม่เกินหนึ่งตัว** และกลับกัน —
       ป้องกันไม่ให้การยิงรัวที่ตำแหน่งเดียวได้ ``TP`` หลายใบ
    3. ใบที่ **ฟันธง** ได้สิทธิ์จับก่อนใบที่ **ส่งต่อ** ณ ตำแหน่งเดียวกัน
       เพราะการฟันธงเป็นข้อกล่าวอ้างที่หนักกว่าและต้องถูกวัดก่อน
    4. ชนิดต้องตรงจึงเป็น ``tp`` · ตำแหน่งตรงแต่ชนิดผิดเป็น ``tp_location_only``

    ``records_total`` ใช้เป็นตัวหารของภาระการตรวจเท่านั้น
    """
    for o in detector_output:
        if o.disposition not in DISPOSITIONS:      # กันไว้อีกชั้นสำหรับ dict ที่แปลงมา
            raise ValueError(f"ท่าทีของระบบไม่ถูกต้อง: {o.disposition!r}")

    def _defect_order(d: InjectedDefect) -> tuple:
        return (d.location.sheet, d.location.row, d.location.cell,
                d.defect_type, d.defect_id)

    in_scope = sorted((d for d in answer_key if d.in_scope), key=_defect_order)
    out_scope = sorted((d for d in answer_key if not d.in_scope),
                       key=_defect_order)

    autos = sorted((o for o in detector_output
                    if o.disposition == DISPOSITION_AUTOMATIC), key=_sort_key)
    refs = sorted((o for o in detector_output
                   if o.disposition == DISPOSITION_REFERRED), key=_sort_key)

    claimed: set[str] = set()          # defect_id ที่ถูกจับไปแล้ว
    used_outputs: set[str] = set()     # output_id ที่จับได้แล้ว

    def _claim(outputs, pool):
        """จับคู่แบบหนึ่งต่อหนึ่ง คืน (ตรงทั้งชนิด, ตรงเฉพาะตำแหน่ง, ไม่ตรงเลย)

        🔴 เรียงทั้งสองฝั่งก่อนเสมอ และเมื่อมีข้อบกพร่องหลายตัวที่ตำแหน่งเดียวกัน
        ให้เลือก **ตัวแรกตามลำดับมาตรฐาน** ถ้าไม่มีตัวใดชนิดตรง — ผลจึงไม่ขึ้นกับ
        ลำดับที่ผู้เรียกส่งเฉลยเข้ามา ซึ่งเป็นเงื่อนไขจำเป็นของการให้คะแนนที่ตรวจซ้ำได้
        """
        exact, loc_only, unmatched = [], [], []
        for o in outputs:
            fallback = None
            hit = None
            for d in pool:
                if d.defect_id in claimed:
                    continue
                if not d.location.matches(o.location):
                    continue
                if d.defect_type == o.finding_type:
                    hit = d
                    break              # ชนิดตรงด้วย — ดีที่สุดแล้ว
                if fallback is None:
                    fallback = d       # ตัวแรกตามลำดับมาตรฐานเท่านั้น
            hit = hit or fallback
            if hit is None:
                unmatched.append(o)
                continue
            claimed.add(hit.defect_id)
            used_outputs.add(o.output_id)
            (exact if hit.defect_type == o.finding_type else loc_only).append((o, hit))
        return exact, loc_only, unmatched

    # ① ฟันธงก่อน
    auto_exact, auto_loc, auto_unmatched = _claim(autos, in_scope)
    # ② แล้วจึงส่งต่อ
    ref_exact, ref_loc, ref_unmatched = _claim(refs, in_scope)

    # 🔴 ใบที่ไม่ตรงข้อบกพร่องในขอบเขต อาจไปตรงกับชนิดที่ประกาศว่าตรวจไม่ได้
    # ต้องรายงานแยก ห้ามนับเป็น FP เพราะระบบ "เจอ" ของจริง เพียงแต่เราประกาศไว้ว่าไม่คาด
    #
    # ใบเหล่านี้จึง **ไม่อยู่ในตัวหารของ precision ① ด้วย** — ทั้งไม่ใช่ความถูก
    # และไม่ใช่ความผิดของชั้นนั้น · ปรากฏเฉพาะที่ ``out_of_scope_detected``
    out_scope_hit = 0
    still_fp = []
    for o in auto_unmatched + ref_unmatched:
        if any(d.location.matches(o.location) for d in out_scope):
            out_scope_hit += 1
        else:
            still_fp.append(o)

    fp = sum(1 for o in still_fp if o.disposition == DISPOSITION_AUTOMATIC)
    referral_wrong = sum(1 for o in still_fp
                         if o.disposition == DISPOSITION_REFERRED)

    referral_correct = len(ref_exact) + len(ref_loc)
    missed = len(in_scope) - len(auto_exact) - len(auto_loc) - referral_correct
    covered = len(auto_exact) + len(auto_loc) + referral_correct

    automatic = AutomaticLayer(
        tp=len(auto_exact), tp_location_only=len(auto_loc), fp=fp, fn=missed,
        defects_in_scope=len(in_scope),
    )
    referral = ReferralLayer(
        correct=referral_correct, wrong=referral_wrong, missed=missed,
        referred_total=len(refs), records_total=records_total,
    )
    coverage = CoverageLayer(covered=covered, uncovered=missed)

    return ScoreReport(
        automatic=automatic, referral=referral, coverage=coverage,
        out_of_scope_defects=len(out_scope), out_of_scope_detected=out_scope_hit,
        defects_total=len(answer_key), records_total=records_total,
        by_defect_type=_by_type(in_scope, auto_exact, auto_loc,
                                ref_exact + ref_loc, claimed),
    )


def _by_type(in_scope, auto_exact, auto_loc, ref_hits, claimed) -> dict:
    """แจกแจงรายชนิดของข้อบกพร่อง — หมวด 5.4 บังคับให้ประกาศตัวหารรายชนิด"""
    out: dict[str, dict[str, int]] = {}
    for d in in_scope:
        out.setdefault(d.defect_type, {
            "injected": 0, "tp": 0, "tp_location_only": 0,
            "referred_correct": 0, "missed": 0,
        })["injected"] += 1
    for _o, d in auto_exact:
        out[d.defect_type]["tp"] += 1
    for _o, d in auto_loc:
        out[d.defect_type]["tp_location_only"] += 1
    for _o, d in ref_hits:
        out[d.defect_type]["referred_correct"] += 1
    for d in in_scope:
        if d.defect_id not in claimed:
            out[d.defect_type]["missed"] += 1
    return dict(sorted(out.items()))


__all__ = [
    "SCORING_SCHEMA_VERSION", "DISPOSITION_AUTOMATIC", "DISPOSITION_REFERRED",
    "DISPOSITIONS", "Location", "InjectedDefect", "DetectorOutput",
    "AutomaticLayer", "ReferralLayer", "CoverageLayer", "ScoreReport", "score",
]
