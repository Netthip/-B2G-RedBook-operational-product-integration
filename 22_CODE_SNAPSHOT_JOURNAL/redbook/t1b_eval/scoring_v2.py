# -*- coding: utf-8 -*-
"""T1B — schema การให้คะแนนสามชั้นแบบ **บัญชีปิดได้** (conservation)

🔴 `BO REVIEW COMPLETE — C/D SCORING CONSERVATION` (6 กันยายน 2569) ·
สเปกต้นทาง: `LANE_C_BLIND_EVALUATION_PROTOCOL.md` §5.1–5.9 ที่ bridge `7f2390a`

**ทำไมเป็นไฟล์ใหม่ ไม่ใช่แก้ `scoring.py`**

Bo สั่งว่า *"ทำ scoring schema version ใหม่ (อย่า rewrite `0.1.0` history)"* ·
`scoring.py` (`t1b-scoring-3layer-0.1.0`) จึงคงไว้ทั้งชุดพร้อมเทสต์ 29 ข้อ
ในฐานะบันทึกว่าเคยตัดสินอย่างไร · เวอร์ชันนั้นถูกจัดสถานะเป็น
**`PRE-CONSERVATION DRAFT — SUPERSEDED FOR FREEZE PURPOSES`**

**ช่องว่างแปดข้อที่ Bo ตรวจโค้ด `8842bd3` แล้วพบ และปิดที่นี่**

===  ====================================================================
 #   สิ่งที่ขาดใน ``0.1.0``
===  ====================================================================
 1   ``ReferralLayer`` ไม่มี referral precision / yield
 2   ``missed`` = uncovered ทั้งหมด · ไม่รับชนิดที่ predeclared ว่าควรส่งต่อ
 3   ไม่มีมิติ ``PRIMARY`` / ``EXPLORATORY`` และไม่มีผลแยก stratum
 4   ไม่มีการตรวจ conservation ที่รันได้
 5   out-of-scope นับด้วย location hit แบบไม่ one-to-one ⇒ ใบซ้ำได้เงินฟรี
 6   exact-before-loc-only ไม่รับประกันข้าม outputs (เรียงตาม ``finding_type``)
 7   ไม่ปฏิเสธ ``defect_id`` / ``output_id`` ที่ซ้ำกัน
 8   ``fn`` ใช้ชื่อมาตรฐานทั้งที่นิยามไม่มาตรฐาน
===  ====================================================================

🔴 **ไม่สร้างเฉลย ไม่ใส่ข้อบกพร่อง ไม่รู้จักแฟ้มใด** — ฟังก์ชันบริสุทธิ์ล้วน ·
การสร้าง generator / answer key ยังถูกระงับ โมดูลนี้ไม่ปลดล็อกข้อนั้น

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

from dataclasses import dataclass, field

SCORING_SCHEMA_VERSION = "t1b-scoring-3layer-0.2.0"
SPEC_SOURCE = "LANE_C_BLIND_EVALUATION_PROTOCOL.md §5.1–5.9 @ bridge 7f2390a"

# ------------------------------------------------------------------ ท่าทีของระบบ
DISPOSITION_AUTOMATIC = "AUTOMATIC"
DISPOSITION_REFERRED = "REFERRED"
DISPOSITIONS = frozenset({DISPOSITION_AUTOMATIC, DISPOSITION_REFERRED})

# ------------------------------------------------------------------------ stratum
#: ชนิดที่ประกาศล่วงหน้าว่า *คาดว่าฟันธงได้* หรือ *คาดว่าควรส่งต่อ*
STRATUM_PRIMARY = "PRIMARY"
#: ชนิดที่ประกาศล่วงหน้าว่า *คาดว่าตรวจไม่ได้*
#: 🔴 **ห้ามใช้รองรับเกณฑ์ใด ๆ** — รายงานเพื่อบอกขอบของความสามารถเท่านั้น
STRATUM_EXPLORATORY = "EXPLORATORY"
STRATA = (STRATUM_PRIMARY, STRATUM_EXPLORATORY)

# ------------------------------------------------------- ช่องของ **ข้อบกพร่อง**
#: ระบบฟันธงเอง · ตำแหน่งถูก **และ** ชนิดถูก
BUCKET_EXACT_AUTO = "EXACT_AUTO"
#: ระบบฟันธงเอง · ตำแหน่งถูก **แต่ชนิดผิด** (เดิมเรียก ``TP-loc``)
BUCKET_LOCTYPE_AUTO = "LOCTYPE_AUTO"
#: ระบบไม่ฟันธง แต่ส่งต่อให้คนตรวจถูกจุด
BUCKET_REFERRED = "REFERRED"
#: ทั้งไม่ฟันธงและไม่ส่งต่อ — หลุดทั้งระบบ
BUCKET_UNCOVERED = "UNCOVERED"
DEFECT_BUCKETS = (BUCKET_EXACT_AUTO, BUCKET_LOCTYPE_AUTO,
                  BUCKET_REFERRED, BUCKET_UNCOVERED)

# ------------------------------------------------------------- ช่องของ **ใบ**
OUTPUT_FP = "FP"
OUTPUT_REFERRAL_WRONG = "REFERRAL_WRONG"

#: ใบที่ไม่ตรงข้อบกพร่องใดเลย และไม่มีข้อบกพร่องอยู่ที่ตำแหน่งนั้นด้วย
#:
#: 🔴 สเปก §5.8 วางตาราง ``FP`` / ``REFERRAL_WRONG`` ไว้ **ในตาราง stratum**
#: แต่ใบที่ไม่ตรงข้อบกพร่องใดเลยไม่มีทางรู้ว่าควรอยู่ stratum ไหน
#: จึงแยกกองไว้ต่างหากและ **รายงานเสมอ** แทนที่จะเลือกยัดเข้า stratum ใดเงียบ ๆ
#: (ดู :attr:`ConservationReport.unattributed` · ตั้งเป็นคำถามถึงเจ้าของสเปก)
NO_STRATUM = "NO_STRATUM"


class ScoringInputError(ValueError):
    """ข้อมูลเข้าไม่ถูกต้องจนให้คะแนนอย่างซื่อสัตย์ไม่ได้

    🔴 ยกข้อผิดพลาด **ดัง ๆ** ดีกว่าคืนตัวเลขที่บัญชีไม่ปิด
    """


@dataclass(frozen=True)
class Location:
    """ตำแหน่งหลักฐานหนึ่งจุด — เทียบด้วย **ความเท่ากันแบบตรงตัว** (§5.2 ข้อ 6)"""

    sheet: str
    row: int
    cell: str = ""

    def key(self) -> tuple:
        return (self.sheet, self.row, self.cell)


@dataclass(frozen=True)
class GoldDefect:
    """ข้อบกพร่องหนึ่งตัวในเฉลย พร้อม stratum ที่ **ประกาศไว้ล่วงหน้า**"""

    defect_id: str
    defect_type: str
    location: Location
    stratum: str = STRATUM_PRIMARY


@dataclass(frozen=True)
class DetectorOutput:
    """ใบที่ระบบออกหนึ่งใบ พร้อม **ท่าที** ของระบบต่อใบนั้น"""

    output_id: str
    finding_type: str
    location: Location
    disposition: str = DISPOSITION_AUTOMATIC


# ══════════════════════════════════════════════════════════════════════════════
#  ผลราย stratum
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class StratumScore:
    """คะแนนครบสามชั้นของ stratum เดียว — บัญชีต้องปิดในตัวเอง (§5.7 ข้อ 1)"""

    stratum: str
    exact_auto: int = 0
    loctype_auto: int = 0
    referred: int = 0
    uncovered: int = 0
    fp: int = 0
    referral_wrong: int = 0
    referral_missed: int = 0
    records_total: int = 0

    # ------------------------------------------------------------- ตัวหารกลาง
    @property
    def defects_total(self) -> int:
        """ข้อบกพร่องในขอบเขตทั้งหมดของ stratum นี้"""
        return (self.exact_auto + self.loctype_auto
                + self.referred + self.uncovered)

    @property
    def automatic_outputs(self) -> int:
        return self.exact_auto + self.loctype_auto + self.fp

    @property
    def referral_outputs(self) -> int:
        return self.referred + self.referral_wrong

    @property
    def outputs_total(self) -> int:
        return self.automatic_outputs + self.referral_outputs

    # ----------------------------------------------------------------- ชั้น ①
    @property
    def precision(self) -> float | None:
        """``EXACT_AUTO / (EXACT_AUTO + LOCTYPE_AUTO + FP)`` (§5.3)

        🔴 ``LOCTYPE_AUTO`` **อยู่ในตัวหาร** — การเดาชนิดมั่ว ๆ ต้องมีต้นทุน
        """
        n = self.automatic_outputs
        return (self.exact_auto / n) if n else None

    @property
    def recall(self) -> float | None:
        """``EXACT_AUTO / ข้อบกพร่องในขอบเขตทั้งหมด`` (§5.3)

        🔴 ตัวหารรวม ``REFERRED`` และ ``UNCOVERED`` — การโยนของยากเข้าคิว
        ไม่ทำให้ค่านี้สูงขึ้น
        """
        n = self.defects_total
        return (self.exact_auto / n) if n else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)

    @property
    def location_accuracy(self) -> float | None:
        """ชี้ตำแหน่งถูกบ่อยแค่ไหนโดยไม่สนชนิด — 🔴 **ห้ามรายงานแทน** ``precision``"""
        n = self.automatic_outputs
        return ((self.exact_auto + self.loctype_auto) / n) if n else None

    # ----------------------------------------------------------------- ชั้น ②
    @property
    def referral_precision(self) -> float | None:
        """``REFERRED / (REFERRED + REFERRAL_WRONG)`` (§5.4)

        🔑 คู่กับ :attr:`referral_recall` เสมอ — recall ที่สูงเพราะส่งทุกอย่าง
        เข้าคิวจะถูกลงโทษที่ค่านี้ทันที
        """
        n = self.referral_outputs
        return (self.referred / n) if n else None

    @property
    def referral_recall(self) -> float | None:
        """``REFERRED / (REFERRED + REFERRAL_MISSED)`` (§5.4)"""
        n = self.referred + self.referral_missed
        return (self.referred / n) if n else None

    @property
    def review_burden_per_1000(self) -> float | None:
        """``(REFERRED + REFERRAL_WRONG) ต่อ 1,000 record``

        🔴 ไม่ประกาศตัวหาร ⇒ คืน ``None`` **ห้ามเดา**
        """
        if not self.records_total:
            return None
        return self.referral_outputs * 1000 / self.records_total

    # ----------------------------------------------------------------- ชั้น ③
    @property
    def coverage(self) -> float | None:
        n = self.defects_total
        if not n:
            return None
        return (self.exact_auto + self.loctype_auto + self.referred) / n

    @property
    def uncovered_rate(self) -> float | None:
        n = self.defects_total
        return (self.uncovered / n) if n else None

    # ------------------------------------------------------------ conservation
    @property
    def defects_conserved(self) -> bool:
        """สมการที่หนึ่ง — ทุกข้อบกพร่องอยู่ในหนึ่งช่องเท่านั้น"""
        return self.defects_total == (
            self.exact_auto + self.loctype_auto + self.referred + self.uncovered)

    @property
    def coverage_conserved(self) -> bool:
        """``coverage + uncovered rate = 1`` — ด่านกันบัญชีรั่ว (§5.8 ข้อ 1)"""
        c, u = self.coverage, self.uncovered_rate
        if c is None or u is None:
            return self.defects_total == 0
        return abs((c + u) - 1.0) < 1e-9

    def summary(self) -> dict[str, object]:
        return {
            "stratum": self.stratum,
            "buckets": {
                BUCKET_EXACT_AUTO: self.exact_auto,
                BUCKET_LOCTYPE_AUTO: self.loctype_auto,
                BUCKET_REFERRED: self.referred,
                BUCKET_UNCOVERED: self.uncovered,
            },
            "outputs": {
                "matched_automatic": self.exact_auto + self.loctype_auto,
                "matched_referral": self.referred,
                OUTPUT_FP: self.fp,
                OUTPUT_REFERRAL_WRONG: self.referral_wrong,
                # 🔴 ชื่อเดิมคือ ``total`` ซึ่งอ่านได้ว่า "ใบทั้งหมดที่ระบบออก"
                # ทั้งที่เป็นยอดของ stratum นี้เท่านั้น · เปลี่ยนชื่อให้ตรงความหมาย
                # เพราะใบที่ระบุ stratum ไม่ได้จะไม่อยู่ในยอดนี้
                "total_in_this_stratum": self.outputs_total,
            },
            "layer_1_automatic": {
                "precision": self.precision, "recall": self.recall,
                "f1": self.f1, "location_accuracy": self.location_accuracy,
            },
            "layer_2_referral": {
                "referral_precision": self.referral_precision,
                "referral_recall": self.referral_recall,
                "referral_missed": self.referral_missed,
                "burden_per_1000": self.review_burden_per_1000,
            },
            "layer_3_coverage": {
                "coverage": self.coverage,
                "uncovered_rate": self.uncovered_rate,
            },
            "denominators": {
                "defects_total": self.defects_total,
                "records_total": self.records_total,
            },
            "conservation": {
                "defects_conserved": self.defects_conserved,
                "coverage_conserved": self.coverage_conserved,
            },
        }


@dataclass(frozen=True)
class ConservationReport:
    """ผลทั้งก้อน — แยกราย stratum และมีด่านตรวจบัญชีที่รันได้"""

    strata: dict[str, StratumScore] = field(default_factory=dict)
    #: ใบที่ไม่มีข้อบกพร่องอยู่ที่ตำแหน่งนั้นเลย ⇒ ระบุ stratum ไม่ได้
    unattributed_fp: int = 0
    unattributed_referral_wrong: int = 0
    records_total: int = 0
    by_defect_type: dict[str, dict[str, int]] = field(default_factory=dict)
    schema_version: str = SCORING_SCHEMA_VERSION
    spec_source: str = SPEC_SOURCE

    @property
    def unattributed(self) -> int:
        return self.unattributed_fp + self.unattributed_referral_wrong

    @property
    def outputs_conserved(self) -> bool:
        """สมการที่สอง — ทุกใบที่ระบบออกอยู่ในหนึ่งช่องเท่านั้น"""
        return all(s.defects_conserved for s in self.strata.values())

    def total_outputs(self) -> int:
        return sum(s.outputs_total for s in self.strata.values()) + self.unattributed

    def conservation_ok(self) -> bool:
        """🔴 ด่านเดียวที่ต้องเป็นจริงเสมอ — ใช้ในเทสต์และก่อนรายงานทุกครั้ง"""
        return all(s.defects_conserved and s.coverage_conserved
                   for s in self.strata.values())

    def folded(self, stratum: str = STRATUM_PRIMARY) -> StratumScore:
        """คืนคะแนนของ stratum นั้น **โดยรวมใบที่ระบุ stratum ไม่ได้เข้าไปด้วย**

        🔴 **จุดที่สเปกยังไม่ระบุ — ต้องให้เจ้าของสเปกตัดสิน**

        §5.8 วางตาราง ``FP`` / ``REFERRAL_WRONG`` ไว้ **ในตารางของ stratum**
        แต่ใบที่ยิงไปยังตำแหน่งที่ **ไม่มีข้อบกพร่องใดเลย** ไม่มีข้อมูลพอจะบอกว่า
        ควรอยู่ stratum ไหน · ตัวอย่าง 100 ข้อบกพร่องในสเปกให้
        ``precision ① = 62/(62+8+14) = 0.738`` ซึ่งเป็นการอ่านแบบ **รวมเข้า**

        โมดูลนี้จึงเก็บสองมุมมองไว้ทั้งคู่ **แทนที่จะเลือกเงียบ ๆ**

        * :attr:`strata` — แยกกอง · ใบที่ระบุ stratum ไม่ได้อยู่ที่
          :attr:`unattributed_fp` / :attr:`unattributed_referral_wrong`
        * :meth:`folded` — รวมเข้า stratum ที่ระบุ · ตรงกับตัวอย่างในสเปก

        ⇒ ตัวเลขที่จะใช้จริงต้องรอคำตัดสินว่าอ่านแบบใดเป็นทางการ
        """
        base = self.strata.get(stratum)
        if base is None:
            base = StratumScore(stratum=stratum, records_total=self.records_total)
        return StratumScore(
            stratum=base.stratum,
            exact_auto=base.exact_auto, loctype_auto=base.loctype_auto,
            referred=base.referred, uncovered=base.uncovered,
            fp=base.fp + self.unattributed_fp,
            referral_wrong=base.referral_wrong + self.unattributed_referral_wrong,
            referral_missed=base.referral_missed,
            records_total=base.records_total,
        )

    def headline_readings(self) -> dict[str, object]:
        """ทั้งสองการอ่านของ ``precision`` ① เคียงกัน + ป้ายว่า **ยังไม่มีคำตัดสิน**

        🔴 เดิม :meth:`summary` แสดงเฉพาะการอ่านแบบ *แยกกอง* ซึ่งเป็นด้านที่
        **ตัวเลขดูดีกว่าเสมอ** — ใบที่ยิงไปในที่ว่างไม่มีต้นทุนใน stratum ที่มีเกณฑ์

        ตัวอย่างที่วัดจริง: detector ที่จับถูก 1 ใบ แล้วยิงมั่วอีก 4 ใบ
        ได้ ``precision`` **1.0** แบบแยกกอง แต่ **0.2** แบบรวมเข้า

        ⇒ ผู้อ่านที่เรียก ``summary()`` แล้วรายงานค่าที่เห็น จะรายงานด้านที่ดีกว่า
        โดยไม่รู้ว่ามีอีกด้าน · จึงต้องแสดง **ทั้งคู่** จนกว่าจะมีคำตัดสิน
        """
        out: dict[str, object] = {
            "status": "OPEN — ยังไม่มีคำตัดสินว่าการอ่านใดเป็นทางการ",
            "why": ("§5.8 วาง FP/REFERRAL_WRONG ไว้ในตารางของ stratum "
                    "แต่ใบที่ยิงไปยังตำแหน่งที่ไม่มีข้อบกพร่องใดเลย ระบุ stratum ไม่ได้ "
                    "— stratum เป็นคุณสมบัติของข้อบกพร่อง ไม่ใช่ของตำแหน่ง"),
            "🔴": "ห้ามเลือกค่าใดค่าหนึ่งไปรายงานเดี่ยว ๆ จนกว่าจะมีคำตัดสิน",
        }
        for stratum in sorted(self.strata):
            sep = self.strata[stratum]
            fold = self.folded(stratum)
            out[stratum] = {
                "separated": {
                    "precision": sep.precision,
                    "referral_precision": sep.referral_precision,
                    "location_accuracy": sep.location_accuracy,
                    # 🔴 ภาระการตรวจคือ "ต้นทุนที่ตกกับคน" — เป็นตัวเลขที่คำตัดสิน
                    # สามชั้นทั้งข้อสร้างขึ้นมาเพื่อปกป้อง · ถ้าไม่แสดงคู่กัน
                    # ใบที่ยิงมั่วในที่ว่างจะไม่ปรากฏเป็นภาระเลย
                    "burden_per_1000": sep.review_burden_per_1000,
                },
                "folded": {
                    "precision": fold.precision,
                    "referral_precision": fold.referral_precision,
                    "location_accuracy": fold.location_accuracy,
                    "burden_per_1000": fold.review_burden_per_1000,
                },
                "agree": (sep.precision == fold.precision
                          and sep.review_burden_per_1000
                          == fold.review_burden_per_1000),
            }
        return out

    def _stratum_block(self, s: StratumScore) -> dict[str, object]:
        """บล็อกของ stratum ที่ **บอกเองว่ามีใบอยู่นอกบล็อกนี้**

        🔴 ข้อบกพร่องที่เจ้าของสเปทักมา และร้ายกว่าเรื่องตัวเลขต่างห้าเท่า

        ในบล็อกของ stratum เดิม ``precision = 1.0`` อยู่คู่กับ ``FP = 0`` ·
        **สองค่านี้สอดคล้องกันเองอย่างสมบูรณ์** คนอ่านจึงไม่มีทางสงสัยว่าขาดอะไร
        และยอด ``total`` ยังบอกว่ามีใบเดียว ทั้งที่ระบบออกมาห้าใบ

        ⇒ ตัวสร้างรายงานที่ดึง ``summary()["strata"]["PRIMARY"]`` ไปตรง ๆ
        จะรายงานว่า *"1 ใบ · ไม่มีการเตือนผิด · precision 1.0"* ให้กับ detector
        ที่ยิงห้าใบแล้วผิดสี่ · บล็อกจึงต้อง **ชี้ออกไปข้างนอกตัวเอง**
        """
        block = s.summary()

        # 🔴 ตัวชี้วัดของชั้น ① ที่มี **ใบของ detector** อยู่ในสมการ —
        # ``precision`` และ ``location_accuracy`` — คิดจากใบของ stratum นี้เท่านั้น
        # ⇒ ใบฟันธงที่ระบุ stratum ไม่ได้ **ไม่ถูกนับเป็นความผิด**
        # (``recall`` และ ``f1`` ไม่ต้องประกาศ เพราะตัวหารเป็นข้อบกพร่องล้วน
        #  และข้อบกพร่องทุกตัวมี stratum เสมอ)
        if self.unattributed_fp:
            layer1 = dict(block["layer_1_automatic"])
            layer1["🔴"] = (
                f"ยังมีใบฟันธงอีก {self.unattributed_fp} ใบที่ระบุ stratum ไม่ได้ "
                f"· **ไม่ได้นับใน precision และ location_accuracy ข้างบน** "
                f"⇒ สองค่านี้สูงกว่าความจริง · ดู headline_readings_OPEN"
            )
            block["layer_1_automatic"] = layer1

        # 🔴 ตัวชี้วัดของชั้น ② คำนวณจากยอดใบของ stratum นี้เท่านั้น
        # ⇒ ใบส่งต่อที่ระบุ stratum ไม่ได้ **ไม่ปรากฏเป็นภาระการตรวจเลย**
        # ทั้งที่เป็นงานที่ตกกับคนจริง ๆ · ต้องบอกในบล็อกเดียวกับตัวเลข
        if self.unattributed_referral_wrong:
            layer2 = dict(block["layer_2_referral"])
            layer2["🔴"] = (
                f"ยังมีใบส่งต่ออีก {self.unattributed_referral_wrong} ใบที่ระบุ "
                f"stratum ไม่ได้ · **ไม่ได้นับใน burden_per_1000 ข้างบน** "
                f"⇒ ภาระการตรวจจริงสูงกว่าตัวเลขนี้ · ดู headline_readings_OPEN"
            )
            block["layer_2_referral"] = layer2

        outputs = dict(block["outputs"])
        outputs["unattributed_elsewhere"] = {
            OUTPUT_FP: self.unattributed_fp,
            OUTPUT_REFERRAL_WRONG: self.unattributed_referral_wrong,
        }
        if self.unattributed:
            outputs["🔴"] = (
                f"ยังมีใบอีก {self.unattributed} ใบที่ระบุ stratum ไม่ได้ "
                f"จึง **ไม่อยู่ในยอดของบล็อกนี้** — ตัวเลขในบล็อกนี้ไม่ใช่ยอดรวม "
                f"ทั้งหมดที่ระบบออก · ดู headline_readings_OPEN ก่อนนำไปรายงาน"
            )
        block["outputs"] = outputs
        return block

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "spec_source": self.spec_source,
            # 🔴 ต้องอยู่ก่อน ``strata`` เพื่อให้ผู้อ่านเห็นก่อนจะไปหยิบตัวเลข
            "headline_readings_OPEN": self.headline_readings(),
            "strata": {k: self._stratum_block(v)
                       for k, v in sorted(self.strata.items())},
            "unattributed_outputs": {
                OUTPUT_FP: self.unattributed_fp,
                OUTPUT_REFERRAL_WRONG: self.unattributed_referral_wrong,
                "note": ("ใบที่ไม่มีข้อบกพร่องอยู่ที่ตำแหน่งนั้นเลย "
                         "จึงระบุ stratum ไม่ได้ — รายงานแยก ห้ามยัดเข้า stratum ใด"),
            },
            "records_total": self.records_total,
            "by_defect_type": self.by_defect_type,
            "conservation_ok": self.conservation_ok(),
            "outputs_total": self.total_outputs(),
        }


# ══════════════════════════════════════════════════════════════════════════════
#  การให้คะแนน
# ══════════════════════════════════════════════════════════════════════════════


def _defect_order(d: GoldDefect) -> tuple:
    return (*d.location.key(), d.defect_type, d.defect_id)


def _output_order(o: DetectorOutput) -> tuple:
    return (*o.location.key(), o.finding_type, o.output_id)


def _validate(gold: list[GoldDefect], outputs: list[DetectorOutput]) -> None:
    """🔴 gap ข้อ 7 — id ซ้ำทำให้บัญชีกับชุดที่ claim แล้วไม่สอดคล้องกัน"""
    seen: set[str] = set()
    for d in gold:
        if d.defect_id in seen:
            raise ScoringInputError(
                f"defect_id ซ้ำ: {d.defect_id!r} — บัญชีจะปิดไม่ได้")
        seen.add(d.defect_id)
        if d.stratum not in STRATA:
            raise ScoringInputError(
                f"stratum ต้องเป็นหนึ่งใน {list(STRATA)} ได้ {d.stratum!r}")

    seen_out: set[str] = set()
    for o in outputs:
        if o.output_id in seen_out:
            raise ScoringInputError(
                f"output_id ซ้ำ: {o.output_id!r} — บัญชีจะปิดไม่ได้")
        seen_out.add(o.output_id)
        if o.disposition not in DISPOSITIONS:
            raise ScoringInputError(
                f"ท่าทีของระบบต้องเป็นหนึ่งใน {sorted(DISPOSITIONS)} "
                f"ได้ {o.disposition!r} — 🔴 ห้ามเดาแทนผู้รัน")


def score(
    gold: list[GoldDefect],
    outputs: list[DetectorOutput],
    *,
    records_total: int = 0,
    expected_referral_types=(),
) -> ConservationReport:
    """ให้คะแนนตามสเปก `7f2390a` §5.1–5.8

    ``expected_referral_types`` = ชนิดที่ **ประกาศไว้ล่วงหน้า** ในหมวด 4 ว่า
    *"พฤติกรรมที่ปลอดภัยคือส่งต่อ"* · 🔴 ต้องส่งเข้ามา **ห้ามคำนวณย้อนหลัง**
    (gap ข้อ 2) · ไม่ส่ง ⇒ ``REFERRAL_MISSED`` = 0 และ ``referral recall``
    จะไม่นิยาม ซึ่งซื่อสัตย์กว่าการเดาแทน

    **ลำดับการจับคู่ — เป็น global phase ไม่ใช่การค้นภายในใบเดียว** (gap ข้อ 6)

    1. ใบ **ฟันธง** ที่ตำแหน่งถูก **และชนิดถูก** ทั้งหมดก่อน ⇒ ``EXACT_AUTO``
    2. ใบ **ฟันธง** ที่เหลือซึ่งตำแหน่งถูก ⇒ ``LOCTYPE_AUTO``
    3. ใบ **ส่งต่อ** ที่ตำแหน่งถูก ⇒ ``REFERRED``
    4. ใบที่เหลือ ⇒ ``FP`` / ``REFERRAL_WRONG``

    เฟสที่ 1 ต้องจบก่อนเฟสที่ 2 **ทั้งชุด** มิฉะนั้นใบชนิดผิดที่มาก่อนจะยึด
    ข้อบกพร่องไปแล้วผลักใบชนิดถูกให้กลายเป็น ``FP``
    """
    _validate(gold, outputs)

    by_loc: dict[tuple, list[GoldDefect]] = {}
    for d in sorted(gold, key=_defect_order):
        by_loc.setdefault(d.location.key(), []).append(d)

    claimed: dict[str, tuple[str, str]] = {}      # defect_id -> (bucket, stratum)
    autos = sorted((o for o in outputs if o.disposition == DISPOSITION_AUTOMATIC),
                   key=_output_order)
    refs = sorted((o for o in outputs if o.disposition == DISPOSITION_REFERRED),
                  key=_output_order)

    consumed: set[str] = set()

    def _take(o: DetectorOutput, *, exact_only: bool) -> GoldDefect | None:
        for d in by_loc.get(o.location.key(), ()):
            if d.defect_id in claimed:
                continue
            if exact_only and d.defect_type != o.finding_type:
                continue
            return d
        return None

    # เฟส 1 — ชนิดถูกก่อน **ทั้งชุด**
    for o in autos:
        hit = _take(o, exact_only=True)
        if hit is not None:
            claimed[hit.defect_id] = (BUCKET_EXACT_AUTO, hit.stratum)
            consumed.add(o.output_id)

    # เฟส 2 — ฟันธงที่ตำแหน่งถูกแต่ชนิดผิด
    for o in autos:
        if o.output_id in consumed:
            continue
        hit = _take(o, exact_only=False)
        if hit is not None:
            claimed[hit.defect_id] = (BUCKET_LOCTYPE_AUTO, hit.stratum)
            consumed.add(o.output_id)

    # เฟส 3 — ส่งต่อ (หลังฟันธงเสมอ · §5.2 ข้อ 3)
    for o in refs:
        hit = _take(o, exact_only=False)
        if hit is not None:
            claimed[hit.defect_id] = (BUCKET_REFERRED, hit.stratum)
            consumed.add(o.output_id)

    # เฟส 4 — ใบที่เหลือ · ใบซ้ำที่ตำแหน่งที่มีข้อบกพร่องอยู่แล้ว
    # ถูกผูกเข้ากับ stratum ของตำแหน่งนั้น ⇒ **ไม่ได้เงินฟรี** (gap ข้อ 5)
    counts: dict[str, dict[str, int]] = {
        s: {"fp": 0, "referral_wrong": 0} for s in STRATA}
    un_fp = un_ref = 0
    for o in autos + refs:
        if o.output_id in consumed:
            continue
        here = by_loc.get(o.location.key())
        bucket = "fp" if o.disposition == DISPOSITION_AUTOMATIC else "referral_wrong"
        if here:
            counts[here[0].stratum][bucket] += 1
        elif bucket == "fp":
            un_fp += 1
        else:
            un_ref += 1

    expected = frozenset(expected_referral_types or ())
    strata: dict[str, StratumScore] = {}
    for stratum in STRATA:
        members = [d for d in gold if d.stratum == stratum]
        if not members and not any(counts[stratum].values()):
            continue
        tally = {b: 0 for b in DEFECT_BUCKETS}
        missed = 0
        for d in members:
            bucket = claimed.get(d.defect_id, (BUCKET_UNCOVERED, stratum))[0]
            tally[bucket] += 1
            if bucket == BUCKET_UNCOVERED and d.defect_type in expected:
                missed += 1
        strata[stratum] = StratumScore(
            stratum=stratum,
            exact_auto=tally[BUCKET_EXACT_AUTO],
            loctype_auto=tally[BUCKET_LOCTYPE_AUTO],
            referred=tally[BUCKET_REFERRED],
            uncovered=tally[BUCKET_UNCOVERED],
            fp=counts[stratum]["fp"],
            referral_wrong=counts[stratum]["referral_wrong"],
            referral_missed=missed,
            records_total=records_total,
        )

    return ConservationReport(
        strata=strata, unattributed_fp=un_fp, unattributed_referral_wrong=un_ref,
        records_total=records_total,
        by_defect_type=_by_type(gold, claimed),
    )


def _by_type(gold, claimed) -> dict:
    """แจกแจงรายชนิด — §5.10 บังคับให้ประกาศตัวหารรายชนิด"""
    out: dict[str, dict[str, int]] = {}
    for d in sorted(gold, key=_defect_order):
        row = out.setdefault(d.defect_type, {
            "stratum": d.stratum, "injected": 0,
            **{b: 0 for b in DEFECT_BUCKETS},
        })
        row["injected"] += 1
        row[claimed.get(d.defect_id, (BUCKET_UNCOVERED,))[0]] += 1
    return dict(sorted(out.items()))


__all__ = [
    "SCORING_SCHEMA_VERSION", "SPEC_SOURCE", "ScoringInputError",
    "DISPOSITION_AUTOMATIC", "DISPOSITION_REFERRED", "DISPOSITIONS",
    "STRATUM_PRIMARY", "STRATUM_EXPLORATORY", "STRATA", "NO_STRATUM",
    "BUCKET_EXACT_AUTO", "BUCKET_LOCTYPE_AUTO", "BUCKET_REFERRED",
    "BUCKET_UNCOVERED", "DEFECT_BUCKETS", "OUTPUT_FP", "OUTPUT_REFERRAL_WRONG",
    "Location", "GoldDefect", "DetectorOutput", "StratumScore",
    "ConservationReport", "score",
]
