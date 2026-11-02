# -*- coding: utf-8 -*-
"""กฎการกันงบบุคลากรและการแบ่งสี่ไตรมาส

ที่มาของกฎ — directive ข้อ 2 ของ Bo (`BO REVIEW COMPLETE — TECHNICAL FREEZE TAG`
13 ก.ย. 2569) ซึ่งระบุว่าเลนผลิตภัณฑ์ทำข้อนี้ได้เลยโดยไม่ต้องรอใคร

    preserve existing priority 1; reserve personnel budget as priority 2 before
    other planned Q1–Q2 spending; divide the annual personnel amount equally
    across four quarters in hundred-baht units; require quarterly sum = annual
    total; if the annual amount is not divisible by 400, fail closed to human
    review rather than rounding or moving a remainder.

คำตัดสินของกิ๊ฟ 27 ก.ย. 2569 — **งบบุคลากรระบุจากหมวดงบรายจ่าย**
จึงใช้ ``CATEGORY_PERSONNEL`` ที่ชั้นเครื่องยนต์ resolve ไว้แล้ว
ไม่ใช่การเดาจากชื่อรายการ

หลักการที่ยึด

* **คิดเป็นหน่วยบาทเสมอ** — กฎพูดถึง "หน่วยร้อยบาท" ซึ่งมีความหมายเดียว
  ก็ต่อเมื่อรู้ว่าค่าที่ถืออยู่เป็นเงินกี่บาท · หน่วยที่แปลงเป็นบาทแบบตรงไปตรงมา
  ไม่ได้ **ต้องตกไปให้คนตัดสิน ห้ามเดา**
* **ห้ามปัดเศษ ห้ามโยกเศษ** — เมื่อยอดรายปีหารไม่ลงตัว ผลคือ *ปฏิเสธ*
  ไม่ใช่ผลลัพธ์ที่ดูสวยแต่ผิด
* **ฟังก์ชันบริสุทธิ์** — ไม่มีที่เก็บสถานะ ไม่มีการเขียนฐานข้อมูล
  หลักการเดียวกับ :func:`redbook.services.t1b.readiness_of`
  และ :mod:`redbook.services.preflight`

🔴 ชั้นนี้ **ห้าม import fastapi/jinja2**
🔴 ชั้นนี้ **ไม่แก้ผลของเครื่องยนต์ที่ตรึงแล้ว** — อ่านค่าคงที่จาก ``redbook.t1b``
   อย่างเดียว เหมือนที่ ``services/t1b.py`` ทำ
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from ..t1b.categories import CATEGORY_PERSONNEL
from ..t1b.units import UNIT_BAHT, UNIT_MILLION_BAHT

QUARTERLY_SERVICE_VERSION = "t1b-quarterly-0.1.0"

#: จำนวนไตรมาสในหนึ่งปีงบประมาณ
QUARTERS = 4
#: "หน่วยร้อยบาท" ตามถ้อยคำของกฎ
HUNDRED_BAHT = Decimal(100)
#: ยอดรายปีต้องหารด้วยค่านี้ลงตัว — สี่ไตรมาส × หน่วยร้อยบาท
DIVISOR_BAHT = Decimal(QUARTERS) * HUNDRED_BAHT          # 400

#: หน่วยที่แปลงเป็นบาทได้แบบไม่ต้องตีความ
#:
#: 🔴 หน่วยอื่น (รวมถึง ``UNRESOLVED`` และหน่วยที่ไม่ใช่เงิน) **ต้องตกให้คนตัดสิน**
#: การเดาอัตราแปลงเองคือการสร้างตัวเลขที่ไม่มีอยู่ในเอกสาร
BAHT_PER_UNIT: dict[str, Decimal] = {
    UNIT_BAHT: Decimal(1),
    UNIT_MILLION_BAHT: Decimal(1_000_000),
}

# ---------------------------------------------------------------- เหตุผลของผล
OK = "OK"
#: อ่านค่าเป็นตัวเลขไม่ได้
AMOUNT_UNREADABLE = "AMOUNT_UNREADABLE"
#: ยอดไม่เป็นบวก — กันงบจากยอดศูนย์หรือติดลบไม่ได้
AMOUNT_NOT_POSITIVE = "AMOUNT_NOT_POSITIVE"
#: หน่วยของค่านี้แปลงเป็นบาทแบบตรงไปตรงมาไม่ได้
UNIT_NOT_CONVERTIBLE = "UNIT_NOT_CONVERTIBLE"
#: ยอดรายปีหารด้วย 400 บาทไม่ลงตัว — **ผลคือปฏิเสธ ไม่ใช่ปัดเศษ**
NOT_DIVISIBLE = "ANNUAL_NOT_DIVISIBLE_BY_400"

REASON_LABELS = {
    OK: "แบ่งสี่ไตรมาสได้ลงตัว",
    AMOUNT_UNREADABLE: "อ่านยอดรายปีเป็นตัวเลขไม่ได้",
    AMOUNT_NOT_POSITIVE: "ยอดรายปีไม่เป็นจำนวนบวก",
    UNIT_NOT_CONVERTIBLE: "หน่วยของยอดนี้แปลงเป็นบาทไม่ได้",
    NOT_DIVISIBLE: "ยอดรายปีหารด้วย 400 บาทไม่ลงตัว",
}

HOW_TO_FIX = {
    AMOUNT_UNREADABLE: (
        "ตรวจเซลล์ต้นทางว่าเก็บยอดเป็นข้อความหรือมีอักขระปนหรือไม่ "
        "แล้วให้ผู้ตรวจกรอกยอดรายปีที่ถูกต้องเอง"
    ),
    AMOUNT_NOT_POSITIVE: (
        "ยอดที่จะกันไว้ต้องมากกว่าศูนย์ "
        "ถ้ารายการนี้ไม่มีงบบุคลากรจริง ก็ไม่ต้องกันงบสำหรับรายการนี้"
    ),
    UNIT_NOT_CONVERTIBLE: (
        "ระบบแปลงเป็นบาทให้เฉพาะหน่วยที่เอกสารประกาศชัดว่าเป็น บาท หรือ ล้านบาท "
        "หน่วยอื่นระบบจะไม่เดาอัตราแปลงให้ "
        "ให้ผู้ตรวจระบุยอดรายปีเป็นบาทเอง แล้วคำนวณใหม่"
    ),
    NOT_DIVISIBLE: (
        "กฎกำหนดให้แบ่งสี่ไตรมาสเท่ากันในหน่วยร้อยบาท ยอดรายปีจึงต้องหารด้วย "
        "400 บาทลงตัว · ยอดนี้หารไม่ลงตัว "
        "🔴 ระบบจะไม่ปัดเศษและไม่โยกเศษไปไตรมาสใดไตรมาสหนึ่ง "
        "ให้ผู้ตรวจทบทวนยอดรายปีกับเอกสารต้นทาง "
        "หรือขอคำตัดสินเรื่องวิธีจัดการเศษก่อนดำเนินการต่อ"
    ),
}


@dataclass(frozen=True)
class QuarterlySplit:
    """ผลการแบ่งยอดรายปีหนึ่งก้อนออกเป็นสี่ไตรมาส"""

    #: ยอดรายปีในหน่วยบาท — ``None`` เมื่อแปลงไม่ได้
    annual_baht: Decimal | None
    #: ยอดต่อไตรมาสในหน่วยบาท — ``None`` เมื่อแบ่งไม่ได้
    per_quarter_baht: Decimal | None
    #: ยอดรายไตรมาส Q1–Q4 — ว่างเมื่อแบ่งไม่ได้
    quarters: tuple[Decimal, ...] = ()
    reason: str = OK
    #: ยอดที่อ่านมาได้ก่อนแปลงหน่วย และหน่วยที่เอกสารประกาศ (ไว้ตรวจย้อน)
    source_amount: Decimal | None = None
    source_unit: str = ""
    #: เศษที่เหลือจากการหาร — บอกไว้ให้คนเห็น **ไม่ได้เอาไปใช้คำนวณ**
    remainder_baht: Decimal | None = None

    @property
    def ok(self) -> bool:
        return self.reason == OK

    @property
    def reason_label(self) -> str:
        return REASON_LABELS.get(self.reason, self.reason)

    @property
    def how_to_fix(self) -> str:
        return HOW_TO_FIX.get(self.reason, "")

    @property
    def quarters_sum(self) -> Decimal:
        """ผลรวมรายไตรมาส — กฎบังคับว่าต้องเท่ายอดรายปีเสมอ"""
        return sum(self.quarters, Decimal(0))

    @property
    def sum_matches_annual(self) -> bool:
        """ตรวจกฎ ``quarterly sum = annual total`` จากค่าที่ได้จริง"""
        return bool(self.quarters) and self.annual_baht is not None \
            and self.quarters_sum == self.annual_baht


def _to_decimal(value: object) -> Decimal | None:
    """อ่านค่าเป็น ``Decimal`` — คืน ``None`` เมื่ออ่านไม่ได้ **ไม่เดา**"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, str):
        text = value.replace(",", "").strip()
        if not text:
            return None
        try:
            return Decimal(text)
        except InvalidOperation:
            return None
    return None


def to_baht(value: object, unit: str) -> Decimal | None:
    """แปลงยอดหนึ่งค่าเป็นบาท — คืน ``None`` เมื่อหน่วยนั้นแปลงไม่ได้

    >>> to_baht("1.2345", "ล้านบาท")
    Decimal('1234500.00')
    >>> to_baht(500, "บาท")
    Decimal('500')
    >>> to_baht(500, "ร้อยละ") is None
    True
    """
    factor = BAHT_PER_UNIT.get(unit)
    if factor is None:
        return None
    amount = _to_decimal(value)
    if amount is None:
        return None
    return amount * factor


def format_baht(value: object) -> str:
    """ข้อความของยอดเงินบาทสำหรับแสดงผล — **ชั้นแสดงผลล้วน ไม่แตะการคำนวณ**

    ยอดที่แปลงมาจากล้านบาทจะติดทศนิยมตามความละเอียดที่เอกสารประกาศ
    (เช่น ``7400000.0000``) ซึ่งอ่านแล้วสะดุดทั้งที่เป็นจำนวนเต็มบาท
    ฟังก์ชันนี้ตัดศูนย์ท้ายทิ้ง **เฉพาะตอนแสดงผล** โดยไม่เปลี่ยนค่าที่คำนวณไว้

    🔴 ไม่ปัดค่า — ถ้ายังมีเศษสตางค์จริง จะแสดงทศนิยมไว้ตามเดิม

    >>> format_baht(Decimal("7400000.0000"))
    '7,400,000'
    >>> format_baht(Decimal("100.50"))
    '100.50'
    >>> format_baht(None)
    '—'
    """
    if value is None:
        return "—"
    dec = _to_decimal(value)
    if dec is None:
        return "—"
    if dec == dec.to_integral_value():
        return f"{dec.to_integral_value():,}"
    # มีเศษสตางค์ — แสดงสองตำแหน่งตามธรรมเนียมเงินบาท
    # 🔴 ใช้ได้เฉพาะเมื่อไม่ทำให้ค่าเปลี่ยน · ถ้าละเอียดกว่าสตางค์ต้องแสดงตามจริง
    try:
        two = dec.quantize(Decimal("0.01"))
    except InvalidOperation:                     # pragma: no cover - ค่ามหาศาล
        return f"{dec.normalize():,f}"
    if two == dec:
        return f"{two:,}"
    return f"{dec.normalize():,f}"


def split_annual(value: object, unit: str = UNIT_BAHT) -> QuarterlySplit:
    """แบ่งยอดรายปีหนึ่งก้อนเป็นสี่ไตรมาสตามกฎ — **fail closed**

    >>> split_annual(400, "บาท").quarters
    (Decimal('100'), Decimal('100'), Decimal('100'), Decimal('100'))
    >>> split_annual(500, "บาท").reason
    'ANNUAL_NOT_DIVISIBLE_BY_400'
    >>> split_annual(500, "บาท").per_quarter_baht is None
    True
    """
    source = _to_decimal(value)
    if source is None:
        return QuarterlySplit(annual_baht=None, per_quarter_baht=None,
                              reason=AMOUNT_UNREADABLE, source_unit=unit)
    if unit not in BAHT_PER_UNIT:
        return QuarterlySplit(annual_baht=None, per_quarter_baht=None,
                              reason=UNIT_NOT_CONVERTIBLE,
                              source_amount=source, source_unit=unit)

    annual = source * BAHT_PER_UNIT[unit]
    if annual <= 0:
        return QuarterlySplit(annual_baht=annual, per_quarter_baht=None,
                              reason=AMOUNT_NOT_POSITIVE,
                              source_amount=source, source_unit=unit)

    remainder = annual % DIVISOR_BAHT
    if remainder != 0:
        # 🔴 จุดที่กฎสั่งให้ปฏิเสธ — ห้ามปัด ห้ามโยกเศษไปไตรมาสใด
        return QuarterlySplit(annual_baht=annual, per_quarter_baht=None,
                              reason=NOT_DIVISIBLE, source_amount=source,
                              source_unit=unit, remainder_baht=remainder)

    per_quarter = annual / QUARTERS
    quarters = tuple(per_quarter for _ in range(QUARTERS))
    # กฎข้อ "quarterly sum = annual total" — ตรวจจากค่าที่ได้จริง ไม่ใช่เชื่อสูตร
    if sum(quarters, Decimal(0)) != annual:      # pragma: no cover - กันไว้เชิงป้องกัน
        return QuarterlySplit(annual_baht=annual, per_quarter_baht=None,
                              reason=NOT_DIVISIBLE, source_amount=source,
                              source_unit=unit, remainder_baht=remainder)
    return QuarterlySplit(annual_baht=annual, per_quarter_baht=per_quarter,
                          quarters=quarters, reason=OK,
                          source_amount=source, source_unit=unit,
                          remainder_baht=Decimal(0))


# ══════════════════════════════════════════════════════════════════════════════
#  ลำดับการกันงบ
# ══════════════════════════════════════════════════════════════════════════════

#: ภาระผูกพันเดิมที่ต้องคงไว้ — ระบบนี้ **ไม่แตะ** รายการลำดับนี้
PRIORITY_EXISTING = 1
#: งบบุคลากร — กันไว้ก่อนรายจ่ายอื่นที่วางแผนไว้ใน Q1–Q2
PRIORITY_PERSONNEL = 2
#: รายจ่ายอื่นที่วางแผนไว้
PRIORITY_OTHER = 3

PRIORITY_LABELS = {
    PRIORITY_EXISTING: "ลำดับ 1 — ภาระผูกพันเดิม (คงไว้ ไม่แตะ)",
    PRIORITY_PERSONNEL: "ลำดับ 2 — งบบุคลากร (กันก่อนรายจ่ายอื่นใน Q1–Q2)",
    PRIORITY_OTHER: "ลำดับ 3 — รายจ่ายอื่นที่วางแผนไว้",
}


@dataclass(frozen=True)
class ReservationLine:
    """หนึ่งบรรทัดในลำดับการกันงบ"""

    priority: int
    label: str
    #: หมวดงบรายจ่าย canonical — ว่างได้สำหรับรายการที่ไม่ผูกกับหมวด
    category: str = ""
    split: QuarterlySplit | None = None
    #: บรรทัดลำดับ 1 ที่รับมาแล้วคงไว้ตามเดิม ไม่ถูกคำนวณใหม่
    untouched: bool = False
    note: str = ""

    @property
    def priority_label(self) -> str:
        return PRIORITY_LABELS.get(self.priority, str(self.priority))

    @property
    def ok(self) -> bool:
        """บรรทัดนี้ติดขัดหรือไม่

        🔴 บรรทัดที่ **ระบบนี้ไม่ได้คำนวณ** (ลำดับ 1 ที่รับมาคงไว้ และรายจ่ายอื่น
        ที่ยังไม่มีสเปกว่ามาจากไหน) ไม่มี ``split`` จึงไม่ถูกตัดสินว่าผ่านหรือไม่ผ่าน
        — โมดูลนี้ตัดสินได้เฉพาะสิ่งที่ตัวเองคำนวณเท่านั้น
        """
        return self.split is None or self.split.ok


@dataclass(frozen=True)
class ReservationPlan:
    """ลำดับการกันงบทั้งชุดของหนึ่งหน่วยงาน/หนึ่งปี"""

    lines: tuple[ReservationLine, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return all(ln.ok for ln in self.lines)

    @property
    def blocked(self) -> tuple[ReservationLine, ...]:
        return tuple(ln for ln in self.lines if not ln.ok)

    @property
    def personnel(self) -> ReservationLine | None:
        for ln in self.lines:
            if ln.priority == PRIORITY_PERSONNEL:
                return ln
        return None


def build_plan(*, personnel_annual: object, personnel_unit: str = UNIT_BAHT,
               existing_priority_1=(), other_planned=()) -> ReservationPlan:
    """ประกอบลำดับการกันงบ

    ``existing_priority_1``
        รายการภาระผูกพันเดิมที่ **รับมาแล้วคงไว้ตามเดิม** — แต่ละรายการเป็น
        ``(label, note)`` · ระบบนี้ไม่คำนวณใหม่ ไม่ย้าย ไม่ปรับยอด
        🔴 ยังไม่มีการตัดสินว่าข้อมูลลำดับ 1 มาจากแหล่งใดในเอกสาร
        ผู้เรียกจึงต้องส่งเข้ามาเอง ระบบจะไม่ไปหาเอง
    ``other_planned``
        รายจ่ายอื่นที่วางแผนไว้ — ``(label, note)`` เช่นกัน
        อยู่ **หลัง** งบบุคลากรเสมอ
    """
    lines: list[ReservationLine] = []
    for label, note in existing_priority_1:
        lines.append(ReservationLine(
            priority=PRIORITY_EXISTING, label=label, untouched=True, note=note))

    lines.append(ReservationLine(
        priority=PRIORITY_PERSONNEL, label="งบบุคลากร",
        category=CATEGORY_PERSONNEL,
        split=split_annual(personnel_annual, personnel_unit)))

    for label, note in other_planned:
        lines.append(ReservationLine(
            priority=PRIORITY_OTHER, label=label, note=note))

    return ReservationPlan(lines=tuple(lines))


# ══════════════════════════════════════════════════════════════════════════════
#  ตัวช่วยหารายการงบบุคลากรในรอบตรวจ
# ══════════════════════════════════════════════════════════════════════════════

def _sheet_of(f) -> str:
    """ชีตที่ finding ใบนี้อยู่ — ฝั่งปัจจุบันก่อน แล้วค่อยฝั่งตั้งต้น"""
    for loc in (f.current, f.baseline):
        if loc is not None and getattr(loc, "sheet", ""):
            return loc.sheet
    return ""


@dataclass(frozen=True)
class PersonnelCandidate:
    """รายการที่ระบบ **เสนอ** ว่าอาจเป็นยอดงบบุคลากรรายปี

    🔴 เป็นตัวเลือกให้ผู้ตรวจเลือก **ไม่ใช่การตัดสินของระบบ**
    ระบบไม่รู้ว่าแถวใดคือยอดรายปีของหมวดนี้ จึงไม่เดาให้
    """

    finding_id: str
    row_label: str
    fiscal_year: int | None
    declared_unit: str
    baseline_value: str
    current_value: str
    section_title: str
    sheet: str = ""
    #: บทบาทเชิงเวลาของแถว — ว่าง = เป็นยอดของปีตามปกติ
    temporal_role: str = ""

    @property
    def eligible(self) -> bool:
        """ใช้เป็น **ยอดรายปี** ของงบบุคลากรได้หรือไม่

        🔴 แถวที่มีบทบาทเชิงเวลาอื่น (วงเงินตลอดอายุโครงการ · ยอดผูกพันของปี)
        อยู่ในคอลัมน์หมวดเดียวกันได้ แต่ **ไม่ใช่ยอดรายปี**
        เอาไปกันงบรายไตรมาสจะนับซ้ำกับยอดปี
        """
        return not self.temporal_role

    @property
    def note(self) -> str:
        if not self.temporal_role:
            return ""
        return (f"{ROLE_LABELS.get(self.temporal_role, self.temporal_role)} — "
                "ไม่ใช่ยอดรายปีของงบบุคลากร 🔴 ใช้เป็นฐานแบ่งสี่ไตรมาสไม่ได้ จะนับซ้ำ")


def personnel_candidates(view) -> tuple[PersonnelCandidate, ...]:
    """รายการทั้งหมดในรอบนี้ที่หมวดงบรายจ่ายเป็น **งบบุคลากร**

    คัดจาก ``budget_category`` ที่เครื่องยนต์ resolve ไว้แล้วเท่านั้น
    (คำตัดสินกิ๊ฟ 27 ก.ย. 2569) — ไม่ใช่การจับคำจากชื่อรายการ

    🔴 แถวที่อยู่ในคอลัมน์หมวดเดียวกันแต่มีบทบาทเชิงเวลาอื่น **ไม่ถูกซ่อน**
    แต่ติดป้ายว่าใช้เป็นยอดรายปีไม่ได้ — ซ่อนแล้วผู้ตรวจจะไม่รู้ว่ามีอยู่
    """
    return tuple(
        PersonnelCandidate(
            finding_id=f.finding_id, row_label=f.row_label,
            fiscal_year=f.fiscal_year, declared_unit=f.declared_unit,
            baseline_value=f.baseline_value, current_value=f.current_value,
            section_title=f.section_title, sheet=_sheet_of(f),
            temporal_role=classify_commitment(f.row_label)[0],
        )
        for f in view.findings
        if f.budget_category == CATEGORY_PERSONNEL
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ลำดับ 1 — ยอดผูกพันในชีตเดียวกัน
# ══════════════════════════════════════════════════════════════════════════════
#
# คำตัดสินกิ๊ฟ 27 ก.ย. 2569 — **ลำดับ 1 ดูจากยอดผูกพันในชีตเดียวกัน**
#
# 🔴 เครื่องยนต์ยัง **ไม่มี** บทบาทแถว ``COMMITMENT_SCHEDULE`` /
# ``PROJECT_LIFETIME_CEILING`` — เป็นงาน G1/RC-E ที่ยังไม่ได้ทำ และ
# ``redbook/t1b/*`` ถูกตรึงไว้ ⇒ ชั้นนี้จึงอ่านบทบาทจาก **ป้ายแถว**
# ที่ชั้นเครื่องยนต์ส่งออกมาแล้ว โดยใช้ตัวบ่งชี้ **ตามที่บันทึกไว้จากเอกสารจริง**
# ใน ``docs/FORMATIVE_CASE_NVI_ROOT_CAUSE_AND_PLAN.md`` §2.2
# ไม่ใช่ตัวบ่งชี้ที่คิดขึ้นเอง
#
# ข้อจำกัดที่ต้องบอกผู้ใช้เสมอ: แถวผูกพันที่ตกไปอยู่ในกอง ``UNMAPPED``
# (พบในชีตประกอบของเอกสารจริง) ชั้นนี้อ่าน **ยอด** ไม่ได้ เพราะเครื่องยนต์
# ยังไม่สกัดค่าออกมาให้ — ต้องรอ G1

#: ป้ายที่ขึ้นต้นด้วยคำนี้ = วงเงินตลอดอายุโครงการ **ไม่ใช่ยอดปี**
CEILING_PREFIX = "วงเงินทั้งสิ้น"
#: คำที่บ่งชี้ว่าแถวนี้เกี่ยวกับภาระผูกพัน
COMMITMENT_MARKER = "ผูกพัน"
#: แถวตารางผูกพันรายปี เช่น ``ปี 2570 ผูกพันงบประมาณ``
_YEAR_ROW = re.compile(r"^ปี\s*(\d{4})\b")

#: ยอดผูกพันของปีหนึ่ง — **เสนอเป็นลำดับ 1 ได้**
ROLE_COMMITMENT_YEAR = "COMMITMENT_YEAR"
#: วงเงินตลอดอายุโครงการ — **ห้ามเอาไปรวมเป็นยอดปี จะนับซ้ำ**
ROLE_LIFETIME_CEILING = "LIFETIME_CEILING"
#: มีคำว่าผูกพันแต่ระบุปีไม่ได้ — ต้องให้คนตัดสิน
ROLE_COMMITMENT_UNCLEAR = "COMMITMENT_UNCLEAR"

ROLE_LABELS = {
    ROLE_COMMITMENT_YEAR: "ยอดผูกพันของปี",
    ROLE_LIFETIME_CEILING: "วงเงินตลอดอายุโครงการ",
    ROLE_COMMITMENT_UNCLEAR: "เกี่ยวกับภาระผูกพัน แต่ระบุปีไม่ได้",
}

ROLE_NOTES = {
    ROLE_COMMITMENT_YEAR: "ยอดผูกพันที่ตกในปีนี้ — เสนอให้คงไว้เป็นลำดับ 1",
    ROLE_LIFETIME_CEILING: (
        "เป็นวงเงินตลอดอายุโครงการ ไม่ใช่ยอดของปีใดปีหนึ่ง "
        "🔴 เอาไปรวมกับยอดปีไม่ได้ จะนับซ้ำ"
    ),
    ROLE_COMMITMENT_UNCLEAR: (
        "ป้ายแถวบอกว่าเกี่ยวกับภาระผูกพัน แต่ระบบอ่านไม่ได้ว่าเป็นของปีใด "
        "ระบบจึงไม่เสนอเอง ให้ผู้ตรวจอ่านเอกสารต้นทางแล้วตัดสิน"
    ),
}


def classify_commitment(row_label: object) -> tuple[str, int | None]:
    """อ่านบทบาทของแถวจากป้าย — คืน ``(role, ปีงบประมาณ)``

    คืน ``("", None)`` เมื่อแถวนั้นไม่เกี่ยวกับภาระผูกพัน

    ลำดับการตัดสินสำคัญ: แถว ``ปี xxxx …`` ที่พูดถึงผูกพัน **เฉพาะเจาะจงกว่า**
    ป้ายวงเงินรวม จึงต้องตรวจก่อน

    >>> classify_commitment("ปี 2570 ผูกพันงบประมาณ")
    ('COMMITMENT_YEAR', 2570)
    >>> classify_commitment("วงเงินทั้งสิ้นของโครงการ")
    ('LIFETIME_CEILING', None)
    >>> classify_commitment("ค่าสาธารณูปโภค")
    ('', None)
    """
    text = str(row_label or "").strip()
    if not text:
        return "", None

    m = _YEAR_ROW.match(text)
    if m and COMMITMENT_MARKER in text:
        return ROLE_COMMITMENT_YEAR, int(m.group(1))
    if text.startswith(CEILING_PREFIX):
        return ROLE_LIFETIME_CEILING, None
    if COMMITMENT_MARKER in text:
        return ROLE_COMMITMENT_UNCLEAR, None
    return "", None


@dataclass(frozen=True)
class CommitmentRow:
    """แถวภาระผูกพันหนึ่งแถวที่พบในชีตเดียวกับยอดงบบุคลากร"""

    finding_id: str
    row_label: str
    role: str
    fiscal_year: int | None
    declared_unit: str
    baseline_value: str
    current_value: str
    sheet: str

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def note(self) -> str:
        return ROLE_NOTES.get(self.role, "")

    @property
    def eligible(self) -> bool:
        """เสนอเป็นลำดับ 1 ได้หรือไม่ — เฉพาะยอดผูกพันของปี และต้องมียอดจริง"""
        return self.role == ROLE_COMMITMENT_YEAR and bool(self.current_value)


def commitment_rows(view, *, sheet: str = "") -> tuple[CommitmentRow, ...]:
    """แถวภาระผูกพันในรอบนี้ — จำกัดเฉพาะ ``sheet`` เดียวเมื่อระบุมา

    🔴 คำตัดสินกิ๊ฟ: ดูจากยอดผูกพัน **ในชีตเดียวกัน** กับยอดงบบุคลากร
    จึงต้องส่ง ``sheet`` มาด้วยเสมอเมื่อใช้ประกอบลำดับการกันงบ

    แถวเดียวกันอาจออกมาหลายใบ (เช่นใบที่ไม่มียอด) — เก็บใบที่ **มียอด** ไว้ก่อน
    """
    best: dict[tuple[str, str], CommitmentRow] = {}
    for f in view.findings:
        role, year = classify_commitment(f.row_label)
        if not role:
            continue
        loc_sheet = _sheet_of(f)
        if sheet and loc_sheet != sheet:
            continue
        row = CommitmentRow(
            finding_id=f.finding_id, row_label=f.row_label, role=role,
            fiscal_year=year, declared_unit=f.declared_unit,
            baseline_value=f.baseline_value, current_value=f.current_value,
            sheet=loc_sheet)
        key = (loc_sheet, f.row_label)
        kept = best.get(key)
        if kept is None or (not kept.current_value and row.current_value):
            best[key] = row
    return tuple(best.values())


def priority_1_from_commitments(rows) -> list[tuple[str, str]]:
    """แปลงแถวผูกพันที่ผู้ตรวจเลือก เป็นบรรทัดลำดับ 1

    🔴 บรรทัดลำดับ 1 **ไม่ถูกคำนวณใหม่** — เก็บยอดตามที่เอกสารแสดงเท่านั้น
    """
    out: list[tuple[str, str]] = []
    for r in rows:
        year = f"ปี {r.fiscal_year} · " if r.fiscal_year else ""
        out.append((
            r.row_label or "(ไม่มีป้ายรายการ)",
            f"{year}ยอดตามเอกสาร {r.current_value or '—'} {r.declared_unit} "
            f"· ชีต {r.sheet} · คงไว้ตามเดิม ไม่คำนวณใหม่",
        ))
    return out


__all__ = [
    "UNIT_BAHT", "UNIT_MILLION_BAHT", "CATEGORY_PERSONNEL",
    "QUARTERLY_SERVICE_VERSION", "QUARTERS", "HUNDRED_BAHT", "DIVISOR_BAHT",
    "BAHT_PER_UNIT", "OK", "AMOUNT_UNREADABLE", "AMOUNT_NOT_POSITIVE",
    "UNIT_NOT_CONVERTIBLE", "NOT_DIVISIBLE", "REASON_LABELS", "HOW_TO_FIX",
    "QuarterlySplit", "to_baht", "split_annual", "format_baht",
    "PRIORITY_EXISTING", "PRIORITY_PERSONNEL", "PRIORITY_OTHER",
    "PRIORITY_LABELS", "ReservationLine", "ReservationPlan", "build_plan",
    "PersonnelCandidate", "personnel_candidates",
    "CEILING_PREFIX", "COMMITMENT_MARKER", "ROLE_COMMITMENT_YEAR",
    "ROLE_LIFETIME_CEILING", "ROLE_COMMITMENT_UNCLEAR", "ROLE_LABELS",
    "ROLE_NOTES", "classify_commitment", "CommitmentRow",
    "commitment_rows", "priority_1_from_commitments",
]
