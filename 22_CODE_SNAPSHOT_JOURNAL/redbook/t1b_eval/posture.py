# -*- coding: utf-8 -*-
"""ตารางท่าทีที่ประกาศล่วงหน้า (predeclared posture table)

ที่มา — `BO REVIEW COMPLETE` 6 ก.ย. 2569 ระบุว่า protocol ยังตรึงไม่ได้เพราะ

    หมวด 4 ยังไม่มี **predeclared posture table** ครบทุก defect type:
    `finding/defect type -> expected disposition -> evaluation stratum`
    ตารางนี้ต้องเป็น source เดียวของทั้ง ``expected_referral_types``
    และ output stratum; ตรึงก่อนสร้าง/เปิด answer key

โมดูลนี้ทำให้ข้อนั้นเป็น **โครงสร้างข้อมูลที่รันได้** แทนที่จะเป็นข้อความในเอกสาร
เพื่อให้ผู้เรียกทุกรายได้คำตอบชุดเดียวกัน และเพื่อให้ "ยังประกาศไม่ครบ"
กลายเป็นสิ่งที่ **ด่านจับได้เอง** ไม่ใช่สิ่งที่ต้องหวังว่าจะมีคนจำได้

🔴 **หลักที่ห้ามละเมิด**

* ค่าทุกช่องในตารางนี้ **คัดมาจากที่ประกาศไว้ล่วงหน้าในโปรโตคอล** เท่านั้น
  ชนิดที่โปรโตคอล **ยังไม่ประกาศ** ต้องเป็น :data:`POSTURE_UNDECLARED`
  **ห้ามเติมให้เองแม้จะเดาได้ว่าน่าจะเป็นอะไร** — การเดาแทนคือการทำลาย
  คุณสมบัติ "ประกาศล่วงหน้า" ทั้งหมดของการประเมิน
* **ห้ามย้ายชนิดข้าม stratum หลังเห็นผล** (โปรโตคอล §5.7 ข้อ 2)
  ผลต่างจากที่ประกาศ ⇒ **รายงานว่าต่าง** ไม่ใช่ย้ายช่อง
* ชั้นนี้ **ไม่รู้จักเฉลย** ไม่รับ ไม่อ่าน ไม่เก็บ — รู้จักเพียง *ชนิด* ของข้อบกพร่อง
"""
from __future__ import annotations

from dataclasses import dataclass

POSTURE_TABLE_VERSION = "t1b-posture-0.2.0"

#: เอกสารต้นทางของทุกค่าในตารางนี้
SPEC_SOURCE = "LANE_C_BLIND_EVALUATION_PROTOCOL.md หมวด 4 + §5.7"

#: คำตัดสินของกิ๊ฟที่ประกาศท่าทีให้ห้าชนิดที่โปรโตคอลเว้นว่างไว้ (6 ต.ค. 2569)
#:
#: 🔴 นี่คือการประกาศ **ก่อนสร้างเฉลยและก่อนเห็นผลประเมินใด ๆ** — ไม่ใช่การเติมย้อนหลัง
#: ห้ามเปลี่ยนท่าทีเหล่านี้หลังเห็นผล · ต้องเปลี่ยน ⇒ เปิดรุ่นใหม่แบบ forward-only
DECISION_SOURCE = (
    "Issue #5 comment 6012653884 (ซ้ำ 6012657125) · Gift DECISION 2026-10-06"
)

#: ประวัติรุ่นของตาราง — เพิ่มต่อท้ายเท่านั้น ห้ามแก้แถวเดิม
VERSION_HISTORY = (
    ("t1b-posture-0.1.0", "2026-09-27",
     "ตารางครบ 25 ชนิดจากโปรโตคอล · ห้าชนิดยังไม่ประกาศท่าที "
     "(V-04 V-05 S-06 T-02 F-03) · ไม่มีชนิดที่ควรส่งต่อ"),
    ("t1b-posture-0.2.0", "2026-10-06",
     "กิ๊ฟประกาศท่าทีห้าชนิด: V-04 V-05 F-03 = AUTOMATIC · "
     "S-06 T-02 = REFERRED (expected referral ของรอบนี้)"),
)

# ---------------------------------------------------------------- ท่าทีที่คาดไว้
#: คาดว่าระบบ **ฟันธงได้เอง**
POSTURE_AUTOMATIC = "AUTOMATIC"
#: คาดว่าระบบ **ควรส่งต่อให้มนุษย์** — พฤติกรรมที่ปลอดภัยคือส่งต่อ
POSTURE_REFERRED = "REFERRED"
#: คาดว่า **ตรวจไม่ได้ด้วยความสามารถวันนี้**
POSTURE_NOT_DETECTABLE = "NOT_DETECTABLE"
#: ตัวล่อ — **ต้องไม่ถูกแจ้งว่าเป็นข้อผิดพลาด** · แจ้งเมื่อใดนับเป็น false positive
POSTURE_MUST_NOT_REPORT = "MUST_NOT_REPORT"
#: 🔴 โปรโตคอล **ยังไม่ประกาศท่าทีของชนิดนี้** — ใช้ประเมินไม่ได้
POSTURE_UNDECLARED = "UNDECLARED"

POSTURES = (POSTURE_AUTOMATIC, POSTURE_REFERRED, POSTURE_NOT_DETECTABLE,
            POSTURE_MUST_NOT_REPORT, POSTURE_UNDECLARED)

POSTURE_LABELS = {
    POSTURE_AUTOMATIC: "คาดว่าฟันธงได้",
    POSTURE_REFERRED: "คาดว่าควรส่งต่อให้มนุษย์",
    POSTURE_NOT_DETECTABLE: "คาดว่าตรวจไม่ได้ด้วยความสามารถวันนี้",
    POSTURE_MUST_NOT_REPORT: "ตัวล่อ — ต้องไม่ถูกแจ้ง",
    POSTURE_UNDECLARED: "🔴 ยังไม่ประกาศท่าที",
}

# ---------------------------------------------------------------- stratum
STRATUM_PRIMARY = "PRIMARY"
STRATUM_EXPLORATORY = "EXPLORATORY"
#: ตัวล่อไม่ใช่ข้อบกพร่องที่ต้องหา จึงไม่อยู่ในตัวหารของ stratum ใด
STRATUM_NEGATIVE_CONTROL = "NEGATIVE_CONTROL"
#: ชนิดที่ยังไม่ประกาศท่าที — ระบุ stratum ไม่ได้ และห้ามใช้ประเมิน
STRATUM_UNASSIGNED = "UNASSIGNED"

#: 🔴 ท่าที **กำหนด** stratum — ไม่ใช่สองค่าที่ตั้งอิสระจากกัน
#:
#: นี่คือหัวใจของข้อที่ Bo สั่ง: ให้ตารางเดียวเป็นที่มาของทั้งสองอย่าง
#: ถ้าปล่อยให้ตั้ง stratum แยกได้ จะเกิดคู่ที่ขัดกันเอง เช่น
#: "คาดว่าตรวจไม่ได้" แต่ไปนั่งอยู่ใน stratum ที่มีเกณฑ์ผ่าน
STRATUM_OF_POSTURE = {
    POSTURE_AUTOMATIC: STRATUM_PRIMARY,
    POSTURE_REFERRED: STRATUM_PRIMARY,
    POSTURE_NOT_DETECTABLE: STRATUM_EXPLORATORY,
    POSTURE_MUST_NOT_REPORT: STRATUM_NEGATIVE_CONTROL,
    POSTURE_UNDECLARED: STRATUM_UNASSIGNED,
}


@dataclass(frozen=True)
class PostureEntry:
    """หนึ่งชนิดข้อบกพร่องพร้อมท่าทีที่ประกาศไว้"""

    code: str
    group: str
    title: str
    posture: str
    #: ข้อความกำกับที่โปรโตคอลเขียนไว้ เช่น "บางส่วน" · "ข้ามชีต"
    #: 🔴 มีค่านี้ = การประกาศ **ไม่ครบถ้วน** ต้องขอความชัดเจนก่อนตรึง
    caveat: str = ""
    #: ที่มาของท่าที — ``"protocol"`` = หมวด 4 ของโปรโตคอล ·
    #: ค่าอื่น = คำตัดสินของมนุษย์ที่ประกาศภายหลังแต่ **ก่อนสร้างเฉลย**
    declared_by: str = "protocol"

    @property
    def stratum(self) -> str:
        return STRATUM_OF_POSTURE[self.posture]

    @property
    def posture_label(self) -> str:
        return POSTURE_LABELS.get(self.posture, self.posture)

    @property
    def declared(self) -> bool:
        return self.posture != POSTURE_UNDECLARED

    @property
    def scorable(self) -> bool:
        """นับเข้าคะแนนได้หรือไม่ — ตัวล่อและชนิดที่ยังไม่ประกาศ นับไม่ได้"""
        return self.posture in (POSTURE_AUTOMATIC, POSTURE_REFERRED,
                                POSTURE_NOT_DETECTABLE)


def _e(code, group, title, posture, caveat="", declared_by="protocol"):
    return PostureEntry(code=code, group=group, title=title,
                        posture=posture, caveat=caveat, declared_by=declared_by)


#: ป้ายที่มาของห้าชนิดที่กิ๊ฟประกาศ 6 ต.ค. 2569
_GIFT_20261006 = "gift-decision-2026-10-06"


#: ตารางท่าที — **ทุกชนิดในหมวด 4 ของโปรโตคอลต้องมีอยู่ที่นี่**
#:
#: ชนิดที่โปรโตคอลไม่ได้ประกาศท่าทีไว้ เคยปรากฏเป็น ``UNDECLARED`` ในรุ่น 0.1.0
#: รุ่น 0.2.0 เติมจาก :data:`DECISION_SOURCE` เท่านั้น และติดป้าย ``declared_by``
TABLE: tuple[PostureEntry, ...] = (
    # ── กลุ่ม V — ค่าและยอด ──────────────────────────────────────────────
    _e("V-01", "V", "ยอดของแถวลูกเปลี่ยน แต่ยอดแม่ไม่เปลี่ยนตาม", POSTURE_AUTOMATIC),
    _e("V-02", "V", "ยอดแม่เปลี่ยน แต่ลูกไม่เปลี่ยน", POSTURE_AUTOMATIC),
    _e("V-03", "V", "ผลรวมรายหมวดไม่เท่าคอลัมน์รวม", POSTURE_AUTOMATIC),
    _e("V-04", "V", "สลับหลักพัน/ล้าน (ผิดหน่วยหนึ่งขั้น)", POSTURE_AUTOMATIC,
       declared_by=_GIFT_20261006),
    _e("V-05", "V", "เครื่องหมายกลับด้าน", POSTURE_AUTOMATIC,
       declared_by=_GIFT_20261006),
    _e("V-06", "V", "ตัวเลขถูกปัดจนไม่ตรงยอดรวม", POSTURE_AUTOMATIC),
    _e("V-07", "V", "ยอดปีอนาคต/ภาระผูกพันไม่สอดคล้องกับปีฐาน",
       POSTURE_NOT_DETECTABLE),
    # ── กลุ่ม S — โครงสร้างและความสอดคล้องข้ามชีต ────────────────────────
    _e("S-01", "S", "ยอดเดียวกันในสองชีตไม่ตรงกัน", POSTURE_AUTOMATIC,
       caveat="โปรโตคอลเขียนว่า “บางส่วน” — ยังไม่ระบุว่าส่วนใดตรวจได้"),
    _e("S-02", "S", "หน่วยบาทกับล้านบาทปนกันในสายเดียว", POSTURE_NOT_DETECTABLE,
       caveat="โปรโตคอลประกาศเฉพาะกรณี “ข้ามชีต” — กรณีในชีตเดียวยังไม่ประกาศ"),
    _e("S-03", "S", "แถวถูกลบออกจากฉบับหลัง โดยยอดรวมไม่ถูกปรับ", POSTURE_AUTOMATIC),
    _e("S-04", "S", "แถวถูกเพิ่มเข้ามาโดยไม่มีที่มา", POSTURE_AUTOMATIC),
    _e("S-05", "S", "ลำดับโครงการเปลี่ยน แต่เนื้อหาเดิม", POSTURE_MUST_NOT_REPORT),
    _e("S-06", "S", "ชื่อแผนงาน/ผลผลิตเปลี่ยน แต่เป็นรายการเดียวกัน",
       POSTURE_REFERRED, declared_by=_GIFT_20261006),
    # ── กลุ่ม T — ข้อความและตัวชี้วัด ────────────────────────────────────
    _e("T-01", "T", "ตัวชี้วัดเปลี่ยนค่าโดยงบไม่เปลี่ยน", POSTURE_AUTOMATIC),
    _e("T-02", "T", "คำอธิบายเปลี่ยนจนความหมายเปลี่ยน", POSTURE_REFERRED,
       declared_by=_GIFT_20261006),
    _e("T-03", "T", "ป้ายแถวเปลี่ยนเฉพาะช่องว่าง/เครื่องหมาย",
       POSTURE_MUST_NOT_REPORT),
    # ── กลุ่ม F — สูตรและการแปลงค่า ──────────────────────────────────────
    _e("F-01", "F", "ค่าที่ควรมาจากสูตรถูกพิมพ์ทับด้วยมือ", POSTURE_NOT_DETECTABLE),
    _e("F-02", "F", "สูตรชี้ช่วงผิด", POSTURE_NOT_DETECTABLE),
    _e("F-03", "F", "ค่า error ตกค้าง", POSTURE_AUTOMATIC,
       declared_by=_GIFT_20261006),
    _e("F-04", "F", "แฟ้ม value-only ที่สูตรไม่เคยถูกคำนวณ", POSTURE_NOT_DETECTABLE),
    # ── กลุ่ม N — ตัวล่อ ────────────────────────────────────────────────
    _e("N-01", "N", "เปลี่ยนเฉพาะรูปแบบการแสดงผล ค่าคงเดิม", POSTURE_MUST_NOT_REPORT),
    _e("N-02", "N", "ช่องว่างนำหน้า/ตามหลังเปลี่ยน", POSTURE_MUST_NOT_REPORT),
    _e("N-03", "N", "เรียงลำดับแถวใหม่โดยเนื้อหาเดิม", POSTURE_MUST_NOT_REPORT),
    _e("N-04", "N", "เพิ่มชีตประกอบที่ไม่เกี่ยวกับผลตรวจ", POSTURE_MUST_NOT_REPORT),
    _e("N-05", "N", "เปลี่ยนชื่อชีตโดยหัวเรื่องเดิม", POSTURE_MUST_NOT_REPORT),
)

BY_CODE: dict[str, PostureEntry] = {e.code: e for e in TABLE}


class UndeclaredDefectType(ValueError):
    """ถูกถามถึงชนิดที่ยังไม่ประกาศท่าที — **ห้ามเดาแทน**"""


def entry(code: str) -> PostureEntry:
    """คืนรายการของชนิดนี้ — ไม่รู้จัก ⇒ ยกข้อผิดพลาด **ไม่เดา**"""
    try:
        return BY_CODE[code]
    except KeyError:
        raise UndeclaredDefectType(
            f"ชนิดข้อบกพร่อง {code!r} ไม่อยู่ในบัญชีของโปรโตคอล — "
            "เพิ่มลงหมวด 4 ของโปรโตคอลก่อน แล้วจึงเพิ่มในตารางนี้"
        ) from None


def posture_of(code: str) -> str:
    return entry(code).posture


def stratum_of(code: str) -> str:
    """stratum ของชนิดนี้ — มาจากท่าทีเสมอ **ตั้งแยกไม่ได้**

    🔴 ชนิดที่ยังไม่ประกาศท่าที จะได้ :data:`STRATUM_UNASSIGNED`
    ซึ่ง :func:`readiness` ปฏิเสธไม่ให้สร้างเฉลย
    """
    return entry(code).stratum


def expected_referral_types() -> tuple[str, ...]:
    """ชนิดที่ประกาศไว้ว่า **พฤติกรรมที่ปลอดภัยคือส่งต่อ**

    เป็นค่าที่ :func:`redbook.t1b_eval.scoring_v2.score` ต้องใช้ —
    ดึงจากตารางนี้ที่เดียว ห้ามให้ผู้เรียกพิมพ์รายการเองซ้ำอีกชุด
    """
    return tuple(e.code for e in TABLE if e.posture == POSTURE_REFERRED)


def types_in_stratum(stratum: str) -> tuple[str, ...]:
    return tuple(e.code for e in TABLE if e.stratum == stratum)


def must_not_report_types() -> tuple[str, ...]:
    """ตัวล่อ — แจ้งเมื่อใดนับเป็น false positive"""
    return tuple(e.code for e in TABLE if e.posture == POSTURE_MUST_NOT_REPORT)


def undeclared_types() -> tuple[str, ...]:
    return tuple(e.code for e in TABLE if not e.declared)


def caveated_types() -> tuple[str, ...]:
    """ชนิดที่ประกาศไว้แล้วแต่ **มีเงื่อนไขกำกับที่ยังไม่ชัด**"""
    return tuple(e.code for e in TABLE if e.declared and e.caveat)


@dataclass(frozen=True)
class Readiness:
    """ตารางนี้พร้อมให้ตรึงและสร้างเฉลยหรือยัง"""

    undeclared: tuple[str, ...]
    caveated: tuple[str, ...]
    #: ไม่มีชนิดใดถูกประกาศว่า "คาดว่าควรส่งต่อ" เลยหรือไม่
    no_referral_types: bool = False

    @property
    def ok(self) -> bool:
        """🔴 ยังมีชนิดที่ไม่ประกาศท่าที = **ยังสร้างเฉลยไม่ได้**"""
        return not self.undeclared

    @property
    def blocking_reason(self) -> str:
        if self.ok:
            return ""
        return (
            "ยังมีชนิดข้อบกพร่องที่โปรโตคอลไม่ได้ประกาศท่าทีไว้ %d ชนิด (%s) — "
            "ตารางท่าทีต้องครบทุกชนิดก่อนสร้างหรือเปิดเฉลย "
            "🔴 ห้ามเติมท่าทีให้เองย้อนหลัง เพราะจะทำให้การประกาศล่วงหน้าไม่มีความหมาย"
            % (len(self.undeclared), " · ".join(self.undeclared))
        )

    @property
    def warning(self) -> str:
        parts = []
        if self.caveated:
            parts.append(
                "ชนิดที่ประกาศแล้วแต่มีเงื่อนไขกำกับที่ยังไม่ชัด %d ชนิด (%s) — "
                "ควรขอความชัดเจนก่อนตรึง แต่ไม่ block การสร้างเฉลย"
                % (len(self.caveated), " · ".join(self.caveated)))
        if self.no_referral_types:
            # 🔴 ช่องว่างที่พบระหว่างประกอบตาราง — โปรโตคอลมีท่าที "ควรส่งต่อ"
            # อยู่ใน §5.7 แต่หมวด 4 ไม่เคยประกาศชนิดใดเป็นท่าทีนี้เลย
            parts.append(
                "ไม่มีชนิดใดถูกประกาศว่า “คาดว่าควรส่งต่อ” เลย ⇒ "
                "expected_referral_types ว่าง ⇒ **วัด referral recall ไม่ได้** "
                "ต้องตัดสินว่าจะประกาศชนิดใดเป็นท่าทีนี้ "
                "หรือประกาศว่ารอบนี้ไม่วัด referral recall")
        return " · ".join(parts)


def readiness() -> Readiness:
    """ด่านก่อนสร้างเฉลย — **ประเมินจากตารางจริงทุกครั้ง**"""
    return Readiness(undeclared=undeclared_types(), caveated=caveated_types(),
                     no_referral_types=not expected_referral_types())


def summary() -> dict:
    """สรุปตารางสำหรับใส่ในรายงาน — ตัวเลขล้วน ไม่มีเนื้อหาเฉลย"""
    counts: dict[str, int] = {p: 0 for p in POSTURES}
    strata: dict[str, int] = {}
    for e in TABLE:
        counts[e.posture] += 1
        strata[e.stratum] = strata.get(e.stratum, 0) + 1
    r = readiness()
    return {
        "posture_table_version": POSTURE_TABLE_VERSION,
        "spec_source": SPEC_SOURCE,
        "decision_source": DECISION_SOURCE,
        "declared_by_decision": [e.code for e in TABLE
                                 if e.declared_by != "protocol"],
        "types_total": len(TABLE),
        "by_posture": counts,
        "by_stratum": strata,
        "expected_referral_types": list(expected_referral_types()),
        "must_not_report_types": list(must_not_report_types()),
        "undeclared_types": list(r.undeclared),
        "caveated_types": list(r.caveated),
        "no_referral_types_declared": r.no_referral_types,
        "ready_to_build_answer_key": r.ok,
    }


__all__ = [
    "POSTURE_TABLE_VERSION", "SPEC_SOURCE", "DECISION_SOURCE", "VERSION_HISTORY",
    "POSTURE_AUTOMATIC", "POSTURE_REFERRED", "POSTURE_NOT_DETECTABLE",
    "POSTURE_MUST_NOT_REPORT", "POSTURE_UNDECLARED", "POSTURES", "POSTURE_LABELS",
    "STRATUM_PRIMARY", "STRATUM_EXPLORATORY", "STRATUM_NEGATIVE_CONTROL",
    "STRATUM_UNASSIGNED", "STRATUM_OF_POSTURE",
    "PostureEntry", "TABLE", "BY_CODE", "UndeclaredDefectType",
    "entry", "posture_of", "stratum_of", "expected_referral_types",
    "types_in_stratum", "must_not_report_types", "undeclared_types",
    "caveated_types", "Readiness", "readiness", "summary",
]


# ══════════════════════════════════════════════════════════════════════════════
#  ด่านบังคับว่าเฉลยต้องสอดคล้องกับตารางนี้
# ══════════════════════════════════════════════════════════════════════════════

class PostureViolation(ValueError):
    """เฉลยขัดกับตารางท่าทีที่ประกาศไว้"""


def validate_gold(gold) -> None:
    """ตรวจว่าเฉลยทุกตัวสอดคล้องกับตารางนี้ — **ยกข้อผิดพลาดเมื่อไม่ตรง**

    นี่คือจุดที่ทำให้ตารางเป็น *source เดียว* จริง ๆ ไม่ใช่เอกสารที่ตั้งไว้เฉย ๆ

    ตรวจสามข้อ

    1. ชนิดของข้อบกพร่องต้องอยู่ในบัญชีของโปรโตคอล
    2. ชนิดนั้นต้อง **ประกาศท่าทีแล้ว** และนับเข้าคะแนนได้
       (ตัวล่อไม่ใช่ข้อบกพร่องที่ต้องหา จึงห้ามอยู่ในเฉลย)
    3. ``stratum`` ที่ติดมากับเฉลยต้องตรงกับที่ตารางกำหนด
       🔴 ข้อนี้กัน "การย้ายชนิดข้าม stratum หลังเห็นผล" ตามโปรโตคอล §5.7 ข้อ 2

    ``gold`` เป็นลำดับของอ็อบเจกต์ที่มี ``defect_id`` · ``defect_type`` · ``stratum``
    (ชั้นนี้ไม่ import โมดูลคะแนน เพื่อไม่ให้สองโมดูลอ้างวนกัน)
    """
    problems: list[str] = []
    for d in gold:
        code = getattr(d, "defect_type", "")
        did = getattr(d, "defect_id", "?")
        try:
            e = entry(code)
        except UndeclaredDefectType as exc:
            problems.append(f"{did}: {exc}")
            continue
        if not e.declared:
            problems.append(
                f"{did}: ชนิด {code} ยังไม่ประกาศท่าที — สร้างเฉลยของชนิดนี้ไม่ได้")
            continue
        if not e.scorable:
            problems.append(
                f"{did}: ชนิด {code} เป็นตัวล่อ ({e.posture_label}) "
                "ห้ามอยู่ในเฉลย — ตัวล่อวัดด้วย false positive ไม่ใช่ด้วยการนับว่าหาเจอ")
            continue
        declared_stratum = e.stratum
        got = getattr(d, "stratum", declared_stratum)
        if got != declared_stratum:
            problems.append(
                f"{did}: ชนิด {code} ตารางกำหนด stratum = {declared_stratum} "
                f"แต่เฉลยระบุ {got} — 🔴 ห้ามย้ายชนิดข้าม stratum")
    if problems:
        raise PostureViolation(
            "เฉลยขัดกับตารางท่าทีที่ประกาศไว้ %d รายการ:\n- %s"
            % (len(problems), "\n- ".join(problems)))


__all__ += ["PostureViolation", "validate_gold"]
