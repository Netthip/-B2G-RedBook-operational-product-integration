# -*- coding: utf-8 -*-
"""T1B — การจับคู่ record ระหว่างสองสมุดงาน

🔒 ใช้คีย์ ``t1b-key-0.2.0`` ที่ freeze แล้ว (5 ก.ย. 2569 · เดิม ``0.1.0``)

**กติกาที่บังคับ**

1. จับคู่ด้วย **ความเท่ากันแบบตรงตัว** ของ ``(T1BKey, fiscal_year)``
   🔴 **ห้ามใช้ fuzzy similarity เป็น auto-match** (คำตัดสิน Gift · 1 ก.ย. 2569)
2. ปีที่มีเพียงข้างเดียวต้อง **รายงานแยก ห้ามนำมาเทียบ** — และต้องคิด
   **รายขอบเขตชีต ไม่ใช่ union ระดับสมุดงาน** (review fix · Bo)
3. record ที่มีความกำกวมแบบ blocking **ห้ามจับคู่อัตโนมัติ** — ส่งเข้าคิวมนุษย์
   รวมถึงหมวดงบรายจ่ายที่ยัง resolve ไม่ได้ ซึ่งกันไว้ที่ชั้นจับคู่โดยตรง
4. record ``UNMAPPED`` ไม่เข้าการจับคู่ แต่ **ต้องถูกนับไว้ ห้ามหายเงียบ**
5. ทุก record ที่ไม่ได้จับคู่ต้อง **รู้ว่ามาจากฝั่งใด** (baseline หรือ current)
6. 🔴 **ตัวตนหน่วยงานต้องถูกยืนยันจากเนื้อในแฟ้มก่อนจับคู่** (blocker #3)
   ด่านนี้เป็น **fail-closed** — เปิดทางให้จับคู่อัตโนมัติเฉพาะเมื่อ *ยืนยันได้*
   ว่าเป็นหน่วยงานเดียวกัน สถานะอื่นทุกค่าปฏิเสธหมด (BO REVIEW · Issue #1)

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from .categories import CATEGORY_UNRESOLVED
from .keys import KEY_VERSION, T1BKey
from .normalize import join_line_breaks, normalize_label

from .records import (
    AXIS_PERIOD_RANGE,
    ROW_KIND_STRUCTURAL,
    ROW_KIND_UNMAPPED,
    ROW_KIND_VALUE,
    UNC_PERIOD_LABEL_CHANGED,
    T1BRecord,
)

MATCHING_VERSION = "t1b-matching-0.9.0"

SIDE_BASELINE = "baseline"
SIDE_CURRENT = "current"

#: ขอบเขตของการเทียบปี — หนึ่งชีตเชิงความหมาย
ScopeKey = tuple[str, str, str]


def scope_of(rec: T1BRecord) -> ScopeKey:
    """ขอบเขตที่ใช้คิด "ปีที่เทียบได้" — **ระดับชีต ไม่ใช่ระดับสมุดงาน**

    🔴 review fix (Bo): เดิมคิด union ทั้งสมุดงาน ทำให้รายงานว่าปี 2568
    เทียบได้ทั้งที่ชีตบทบาท ``5.`` ของแฟ้ม FY2570 ไม่มีปี 2568 เลย
    (ปีนั้นมาจากชีตบทบาท ``8.`` ซึ่งเริ่มต้นคนละปี)
    """
    return (rec.key.sheet_role, rec.key.section_title_norm, rec.key.parent_plan_norm)


#: เหตุผลของ :class:`IdentityCheck` — ค่าเดียวเสมอ ห้ามผสม
IDENTITY_OK = "agency_identity_confirmed_from_content"
IDENTITY_CONFLICT = "agency_identity_conflict_between_workbooks"
IDENTITY_UNVERIFIED = "agency_identity_not_readable_from_content"
IDENTITY_AMBIGUOUS = "more_than_one_agency_identity_on_one_side"

# ------------------------------------------------------ ผลระดับ "การเปรียบเทียบ"
#: ด่านผ่าน — การเปรียบเทียบอัตโนมัติเกิดขึ้นจริง
VERDICT_COMPARED = "COMPARED"
#: มีหลักฐาน **ชี้ชัด** ว่าคู่นี้ผิดฝาผิดตัว — ให้มนุษย์ตัดสิน
VERDICT_REVIEW_REQUIRED = "REVIEW_REQUIRED"
#: หลักฐาน **ไม่พอ** จะตัดสินได้เลย — ไม่ใช่ "ผ่าน" และไม่ใช่ "ไม่ผ่าน"
VERDICT_CANNOT_DETERMINE = "CANNOT_DETERMINE"

#: 🔴 **เปิดทางเดียว** — เหตุผลที่อนุญาตให้จับคู่อัตโนมัติได้
#:
#: ประกาศเป็นชุด *ที่อนุญาต* ไม่ใช่ชุด *ที่ห้าม* โดยเจตนา เพื่อให้เหตุผลใหม่
#: ที่ยังไม่มีในวันนี้ตกไปทาง **ปฏิเสธ** โดยอัตโนมัติ (fail-closed)
IDENTITY_MAY_MATCH = frozenset({IDENTITY_OK})

#: แผนที่เหตุผล → ผลระดับการเปรียบเทียบ · ค่าที่ไม่อยู่ในแผนที่ = ตัดสินไม่ได้
_IDENTITY_VERDICT = {
    IDENTITY_OK: VERDICT_COMPARED,
    IDENTITY_CONFLICT: VERDICT_REVIEW_REQUIRED,
    IDENTITY_UNVERIFIED: VERDICT_CANNOT_DETERMINE,
    IDENTITY_AMBIGUOUS: VERDICT_CANNOT_DETERMINE,
}


@dataclass(frozen=True)
class IdentityCheck:
    """ด่านตรวจว่าสองแฟ้มเป็นหน่วยงานเดียวกันจริง — **จากเนื้อในแฟ้ม**

    🔴 **blocker #3 · Shadow Run 21011 รอบที่ 1** (แก้ 5 กันยายน 2569)

    ``agency_code`` อ่านจาก **ชื่อไฟล์** ตามรูปแบบ ``XL_FY####_<status>_#####_``
    เท่านั้น · ชื่อแฟ้มจริงของหน่วยงานไม่ตรงรูปแบบนี้ ⇒ ``agency_code`` ว่าง
    **ทั้งสองฝั่ง** ⇒ คีย์ยังเท่ากัน ⇒ จับคู่ได้ตามปกติ **โดยไม่มีการยืนยันใด**
    ว่าเป็นหน่วยงานเดียวกัน

    ชั้นนี้ตรวจจาก :attr:`T1BKey.agency_identity` ซึ่งอ่านจากชีตปกในแฟ้ม
    แล้วออกผล **สี่เหตุผล** — ยืนยันได้ · ขัดแย้ง · ยืนยันไม่ได้ ·
    มีตัวตนมากกว่าหนึ่งค่าในฝั่งเดียว (ดู ``IDENTITY_*``)

    🔴 **BO REVIEW (Issue #1) — fail-closed**

        *"In an operational verifier, unverified identity must not be
        equivalent to permission to compare."*

    เดิม ``IDENTITY_UNVERIFIED`` ไม่หยุดการจับคู่ ⇒ สองแฟ้มที่อ่านตัวตนไม่ได้
    **ทั้งคู่** จะมีคีย์เท่ากันแล้วถูกจับคู่อัตโนมัติ ออกเป็นยอดเพิ่ม/ยอดลด
    ของหน่วยงานที่ยังไม่เคยพิสูจน์ว่าเป็นหน่วยงานเดียวกัน · ถ้าอ่านไม่ได้
    เพียงฝั่งเดียว ระบบก็สรุปเองว่าทุกแถว "ถูกลบ" และ "ถูกเพิ่ม"

    ตอนนี้ :attr:`may_match` เปิดให้เฉพาะ ``IDENTITY_OK`` เท่านั้น
    """

    baseline_agency: tuple[str, ...]
    current_agency: tuple[str, ...]
    reason: str
    #: จำนวน record ขาเข้าสองฝั่ง — ให้ด่านเองพิสูจน์ได้ว่าไม่มีอะไรหายตอนปฏิเสธ
    baseline_records: int = 0
    current_records: int = 0

    @property
    def conflict(self) -> bool:
        """🔴 คนละหน่วยงานแน่ชัด — ห้ามจับคู่อัตโนมัติ"""
        return self.reason == IDENTITY_CONFLICT

    @property
    def verified(self) -> bool:
        return self.reason == IDENTITY_OK

    @property
    def may_match(self) -> bool:
        """🔴 ด่านนี้อนุญาตให้จับคู่อัตโนมัติหรือไม่ — **ทางผ่านมีทางเดียว**"""
        return self.reason in IDENTITY_MAY_MATCH

    @property
    def blocked(self) -> bool:
        """ตรงข้ามกับ :attr:`may_match` — เขียนไว้ให้ผู้เรียกอ่านง่ายที่จุดใช้งาน"""
        return not self.may_match

    @property
    def verdict(self) -> str:
        """ผลระดับการเปรียบเทียบ — ``COMPARED`` · ``REVIEW_REQUIRED``
        · ``CANNOT_DETERMINE``

        เหตุผลที่ไม่รู้จักคืน ``CANNOT_DETERMINE`` เสมอ ห้ามคืน ``COMPARED``
        """
        return _IDENTITY_VERDICT.get(self.reason, VERDICT_CANNOT_DETERMINE)

    @property
    def label(self) -> str:
        b = " · ".join(self.baseline_agency) or "(อ่านไม่ได้)"
        c = " · ".join(self.current_agency) or "(อ่านไม่ได้)"
        return f"ฉบับตั้งต้น {b} · ฉบับปัจจุบัน {c}"

    @property
    def note(self) -> str:
        """เหตุผลที่ถูกกัน สำหรับแสดงต่อผู้ตรวจ — ว่างเมื่อด่านผ่าน

        🔴 ห้ามคืนค่าว่างเมื่อถูกกัน ผู้อ่านต้องรู้เสมอว่าถูกกันเพราะอะไร
        """
        if self.may_match:
            return ""
        if self.reason == IDENTITY_CONFLICT:
            head = "🔴 คนละหน่วยงานตามเนื้อในแฟ้ม"
        elif self.reason == IDENTITY_AMBIGUOUS:
            head = "🔴 ตัวตนหน่วยงานในแฟ้มเดียวมีมากกว่าหนึ่งค่า"
        elif self.reason == IDENTITY_UNVERIFIED:
            head = "🔴 ยืนยันตัวตนหน่วยงานจากเนื้อในแฟ้มไม่ได้"
        else:
            head = f"🔴 ด่านตัวตนหน่วยงานไม่ผ่าน ({self.reason})"
        return (f"{head} — {self.label} · ห้ามเทียบอัตโนมัติ "
                f"(ผลระดับการเปรียบเทียบ: {self.verdict})")


def _agency_identities(records: list[T1BRecord]) -> tuple[str, ...]:
    return tuple(sorted({r.key.agency_identity for r in records if r.key.agency_identity}))


def check_identity(
    baseline: list[T1BRecord], current: list[T1BRecord]
) -> IdentityCheck:
    """ตรวจตัวตนหน่วยงานของสองฝั่ง **ก่อน** การจับคู่ใด ๆ

    🔴 ``ยืนยันไม่ได้`` **ไม่เท่ากับ** ``ผ่าน`` — ต้องรายงานแยกเสมอ
    และตั้งแต่ BO REVIEW (Issue #1) ต้อง **ห้ามจับคู่อัตโนมัติ** ด้วย
    """
    b = _agency_identities(baseline)
    c = _agency_identities(current)
    nb, nc = len(baseline), len(current)
    if len(b) > 1 or len(c) > 1:
        return IdentityCheck(b, c, IDENTITY_AMBIGUOUS, nb, nc)
    if not b or not c:
        return IdentityCheck(b, c, IDENTITY_UNVERIFIED, nb, nc)
    if b != c:
        return IdentityCheck(b, c, IDENTITY_CONFLICT, nb, nc)
    return IdentityCheck(b, c, IDENTITY_OK, nb, nc)


@dataclass(frozen=True)
class SidedRecord:
    """record พร้อมข้อมูลว่ามาจากฝั่งใด — กัน provenance หายตอนรายงาน"""

    side: str
    record: T1BRecord


@dataclass(frozen=True)
class MatchPair:
    """คู่ที่จับกันได้ — คีย์เดียวกันและปีเดียวกัน"""

    key: T1BKey
    fiscal_year: int | None
    baseline: T1BRecord
    current: T1BRecord
    #: ``""`` = จับคู่ด้วยลายเซ็นเต็มตามปกติ · ``line_break_joined`` = ขั้นสำรอง G3
    via: str = ""


@dataclass(frozen=True)
class YearScope:
    """ปีที่เทียบได้และปีที่มีข้างเดียว — **ของขอบเขตชีตหนึ่ง**"""

    scope: ScopeKey
    comparable: tuple[int, ...]
    baseline_only: tuple[int, ...]
    current_only: tuple[int, ...]

    @property
    def label(self) -> str:
        role, title, parent = self.scope
        parts = [role or "(no role)"]
        if title:
            parts.append(title)
        if parent:
            parts.append(f"ใต้ {parent}")
        return " · ".join(parts)


@dataclass
class MatchResult:
    """ผลการจับคู่ — ทุก record ต้องอยู่ในกลุ่มใดกลุ่มหนึ่งเสมอ"""

    matched: list[MatchPair] = field(default_factory=list)
    baseline_only: list[T1BRecord] = field(default_factory=list)
    current_only: list[T1BRecord] = field(default_factory=list)
    needs_human: list[SidedRecord] = field(default_factory=list)
    unmapped: list[SidedRecord] = field(default_factory=list)
    year_scopes: list[YearScope] = field(default_factory=list)
    #: 🔴 blocker #3 — ผลการตรวจตัวตนหน่วยงานจากเนื้อในแฟ้ม
    #: ``None`` ได้เฉพาะเมื่อสร้าง ``MatchResult`` เปล่าเพื่อทดสอบ
    identity: IdentityCheck | None = None

    def accounted(self) -> int:
        """จำนวน record ที่ถูกจัดกลุ่มแล้ว — ใช้พิสูจน์ว่าไม่มีอะไรหายเงียบ"""
        return (
            len(self.matched) * 2
            + len(self.baseline_only)
            + len(self.current_only)
            + len(self.needs_human)
            + len(self.unmapped)
        )

    def scopes_with_year_gap(self) -> list[YearScope]:
        """ขอบเขตที่มีปีอยู่เพียงข้างเดียว — ต้องรายงาน ห้ามเทียบ"""
        return [s for s in self.year_scopes if s.baseline_only or s.current_only]

    def summary(self) -> dict[str, object]:
        return {
            "key_version": KEY_VERSION,
            "matching_version": MATCHING_VERSION,
            "matched": len(self.matched),
            "baseline_only": len(self.baseline_only),
            "current_only": len(self.current_only),
            "needs_human": len(self.needs_human),
            "unmapped": len(self.unmapped),
            "year_scopes": len(self.year_scopes),
            "scopes_with_year_gap": len(self.scopes_with_year_gap()),
            "accounted": self.accounted(),
            "identity_reason": self.identity.reason if self.identity else None,
            "identity_verified": bool(self.identity and self.identity.verified),
            "identity_conflict": bool(self.identity and self.identity.conflict),
            "identity_verdict": self.identity_verdict,
            "identity_gate_blocked": self.identity_gate_blocked,
        }

    @property
    def identity_verdict(self) -> str:
        """ผลระดับการเปรียบเทียบของรอบนี้

        🔴 ``MatchResult`` ที่ยังไม่ผ่านด่าน (``identity is None``) นับเป็น
        ``CANNOT_DETERMINE`` — ค่าเริ่มต้นต้องอยู่ข้าง **ปฏิเสธ** เสมอ
        """
        return self.identity.verdict if self.identity else VERDICT_CANNOT_DETERMINE

    @property
    def identity_gate_blocked(self) -> bool:
        return self.identity.blocked if self.identity else True


Signature = tuple[T1BKey, str, int | None, str | None, str, str | None]


def _category_discriminator(rec: T1BRecord) -> str:
    """ตัวแยกคอลัมน์หมวดที่ resolve **ไม่ได้** ออกจากกัน

    🔴 BO REVIEW (2 ก.ย.): หัวคอลัมน์ที่ไม่รู้จักตั้งแต่สองคอลัมน์ขึ้นไปในแถวเดียวกัน
    จะได้ canonical เป็น ``UNRESOLVED`` เหมือนกันหมด ⇒ ลายเซ็นชนกัน และอาจถูก
    จับคู่ข้ามชนิดกัน ซึ่ง **อันตรายกว่าข้อมูลหาย** เพราะกลายเป็นข้อมูลผิดที่ดูถูกต้อง

    ใช้หัวคอลัมน์ดิบที่ normalize แล้วเป็นตัวแยก **เฉพาะกรณี ``UNRESOLVED``**
    หมวดที่รู้จักยังเทียบด้วย canonical code เหมือนเดิม จึงไม่กระทบพฤติกรรมเดิม
    การเทียบเป็นความเท่ากันแบบตรงตัว **ไม่ใช่ fuzzy similarity**
    """
    if rec.budget_category != CATEGORY_UNRESOLVED:
        return ""
    return normalize_label(rec.budget_category_raw)


def _signature(rec: T1BRecord) -> Signature:
    """ลายเซ็นการจับคู่ = คีย์ + **แกนเทียบ** + มิติที่นำมาเทียบ + ตัวแยกหมวดดิบ

    🔴 ``T1BKey`` ที่ freeze แล้ว **ไม่ถูกเปลี่ยน** — ``comparison_axis`` ·
    ``fiscal_year`` · ``budget_category`` เป็น comparison attribute ที่อยู่นอกคีย์
    แต่ต้องตรงกันจึงจะถือว่าเป็นค่าคู่เดียวกัน

    การใส่ ``comparison_axis`` ไว้ในลายเซ็นทำให้ **แกนต่างกันจับคู่กันไม่ได้**
    อย่างชัดแจ้ง แทนที่จะพึ่ง invariant ที่ซ่อนอยู่ว่าอีกฟิลด์เป็น ``None``
    """
    return (
        rec.key,
        rec.comparison_axis,
        rec.fiscal_year,
        rec.budget_category,
        _category_discriminator(rec),
        # G5 (#14) — ช่วงเวลาจับคู่ได้เฉพาะป้ายที่ตรงกันทุกตัวอักษรหลัง normalize
        rec.period_label,
    )


def _split(records: list[T1BRecord], side: str):
    usable: list[T1BRecord] = []
    human: list[SidedRecord] = []
    unmapped: list[SidedRecord] = []
    for rec in records:
        if rec.row_kind == ROW_KIND_UNMAPPED:
            unmapped.append(SidedRecord(side, rec))
        elif rec.budget_category == CATEGORY_UNRESOLVED:
            # 🔴 BO REVIEW (2 ก.ย.) — หมวดที่ยัง resolve ไม่ได้ **ห้ามจับคู่อัตโนมัติ**
            # จนกว่ามนุษย์จะตัดสิน · ด่านนี้ไม่พึ่งเครื่องหมาย uncertainty
            # เพื่อให้ยังกันได้แม้เส้นทางสกัดในอนาคตลืมติดธง
            human.append(SidedRecord(side, rec))
        elif rec.needs_review:
            # 🔴 กำกวมแบบ blocking — ห้ามจับคู่อัตโนมัติ
            human.append(SidedRecord(side, rec))
        elif rec.row_kind in (ROW_KIND_VALUE, ROW_KIND_STRUCTURAL):
            usable.append(rec)
        else:
            human.append(SidedRecord(side, rec))
    return usable, human, unmapped


def _year_scopes(
    base_usable: list[T1BRecord], curr_usable: list[T1BRecord]
) -> tuple[list[YearScope], dict[ScopeKey, set[int]]]:
    """คิดปีที่เทียบได้ **แยกตามขอบเขตชีต**"""
    base_years: dict[ScopeKey, set[int]] = {}
    curr_years: dict[ScopeKey, set[int]] = {}
    for rec in base_usable:
        if rec.fiscal_year is not None:
            base_years.setdefault(scope_of(rec), set()).add(rec.fiscal_year)
    for rec in curr_usable:
        if rec.fiscal_year is not None:
            curr_years.setdefault(scope_of(rec), set()).add(rec.fiscal_year)

    scopes: list[YearScope] = []
    comparable: dict[ScopeKey, set[int]] = {}
    for scope in sorted(set(base_years) | set(curr_years)):
        a = base_years.get(scope, set())
        b = curr_years.get(scope, set())
        shared = a & b
        comparable[scope] = shared
        scopes.append(YearScope(
            scope=scope,
            comparable=tuple(sorted(shared)),
            baseline_only=tuple(sorted(a - b)),
            current_only=tuple(sorted(b - a)),
        ))
    return scopes, comparable


def match_records(
    baseline: list[T1BRecord], current: list[T1BRecord]
) -> MatchResult:
    """จับคู่ record ของสองสมุดงาน

    ``baseline`` = ฉบับตั้งต้น (เช่น ร่าง พ.ร.บ.) · ``current`` = ฉบับที่นำมาตรวจ

    ทุก record ขาเข้าจะถูกจัดลงกลุ่มใดกลุ่มหนึ่งเสมอ — พิสูจน์ได้ด้วย
    ``result.accounted()`` เทียบกับจำนวน record ขาเข้ารวม
    """
    result = MatchResult()
    result.identity = check_identity(baseline, current)

    if result.identity.blocked:
        # 🔴 blocker #3 · fail-closed ตาม BO REVIEW (Issue #1)
        #
        # ตราบใดที่ยัง **พิสูจน์ไม่ได้** ว่าสองแฟ้มเป็นหน่วยงานเดียวกัน
        # ระบบต้องไม่ตัดสินอะไรอัตโนมัติเลย — ไม่ใช่แค่ไม่จับคู่ แต่ต้องไม่
        # สรุปด้วยว่าแถว "หาย" หรือ "เพิ่ม" เพราะข้อสรุปนั้นก็ตั้งอยู่บน
        # สมมติฐานว่าสองแฟ้มเทียบกันได้ ซึ่งยังไม่มีหลักฐานรองรับ
        #
        # ทุก record จึงเข้าคิวมนุษย์ทั้งหมด โดยยัง accounted ครบ (invariant ข้อ 4)
        # และยังรู้ว่ามาจากฝั่งใด (invariant ข้อ 5)
        result.needs_human = (
            [SidedRecord(SIDE_BASELINE, r) for r in baseline]
            + [SidedRecord(SIDE_CURRENT, r) for r in current]
        )
        return result

    base_usable, base_human, base_unmapped = _split(baseline, SIDE_BASELINE)
    curr_usable, curr_human, curr_unmapped = _split(current, SIDE_CURRENT)

    result.needs_human = base_human + curr_human
    result.unmapped = base_unmapped + curr_unmapped

    result.year_scopes, comparable = _year_scopes(base_usable, curr_usable)

    index: dict[Signature, list[T1BRecord]] = {}
    for rec in curr_usable:
        index.setdefault(_signature(rec), []).append(rec)

    consumed: set[int] = set()
    for rec in base_usable:
        year = rec.fiscal_year
        if year is not None and year not in comparable.get(scope_of(rec), set()):
            # 🔴 ปีนี้ไม่มีในขอบเขตชีตเดียวกันของอีกฝั่ง — ห้ามเทียบ
            result.baseline_only.append(rec)
            continue
        bucket = index.get(_signature(rec))
        if not bucket:
            result.baseline_only.append(rec)
            continue
        partner = bucket.pop(0)
        consumed.add(id(partner))
        result.matched.append(
            MatchPair(key=rec.key, fiscal_year=year, baseline=rec, current=partner)
        )

    for rec in curr_usable:
        if id(rec) not in consumed:
            result.current_only.append(rec)

    _match_line_break_variants(result)
    _route_period_label_changes(result)
    return result


VIA_LINE_BREAK_JOINED = "line_break_joined"


def _has_line_break(raw: object) -> bool:
    return isinstance(raw, str) and ("\n" in raw or "\r" in raw)


def _match_line_break_variants(result: MatchResult) -> None:
    """G3 (#14) — ขั้นสำรอง: ป้ายที่ต่างกันเฉพาะตำแหน่งการขึ้นบรรทัดในเซลล์

    ทำกับ record ที่ **ยังไม่ถูกจับคู่** เท่านั้น · ลายเซ็นเหมือนเดิมทุกส่วน
    ยกเว้นป้ายแถวที่ลบการขึ้นบรรทัดแล้ว · 🔴 จับคู่เฉพาะกลุ่มที่มี **หนึ่งต่อหนึ่ง**
    พอดี (กลุ่มที่มีหลายรายการ ปล่อยไว้ตามเดิม) · คู่ที่ได้ติด ``via`` ให้ชั้น
    เปรียบเทียบติดธงที่ต้องให้คนตรวจ
    """
    def alt(rec: T1BRecord):
        k = rec.key
        return (k.agency_code, k.agency_identity, k.document_level, k.sheet_role,
                k.section_title_norm, k.parent_plan_norm, k.plan_role,
                # ส่วนที่สองของ path ของแถวลูกคือป้ายที่ normalize แล้ว (มีช่องว่าง
                # จากการขึ้นบรรทัดติดมา) ⇒ ใช้เฉพาะเลขหัวข้อแม่ ส่วนป้ายเทียบแบบลบการขึ้นบรรทัด
                k.hierarchy_path[:1], join_line_breaks(rec.raw_label),
                rec.comparison_axis, rec.fiscal_year, rec.budget_category,
                _category_discriminator(rec), rec.period_label)

    def eligible(rec: T1BRecord) -> bool:
        # ต้องมีป้ายดิบเป็นข้อความที่ไม่ว่าง — ไม่งั้นป้ายว่างสองฝั่งจะ "ตรงกัน" ผิด ๆ
        return isinstance(rec.raw_label, str) and bool(join_line_breaks(rec.raw_label))

    base: dict[tuple, list[T1BRecord]] = {}
    for rec in result.baseline_only:
        if eligible(rec):
            base.setdefault(alt(rec), []).append(rec)
    curr: dict[tuple, list[T1BRecord]] = {}
    for rec in result.current_only:
        if eligible(rec):
            curr.setdefault(alt(rec), []).append(rec)

    paired: set[int] = set()
    for sig, b in base.items():
        c = curr.get(sig, [])
        if len(b) != 1 or len(c) != 1 or b[0].key == c[0].key:
            continue
        if not (_has_line_break(b[0].raw_label) or _has_line_break(c[0].raw_label)):
            continue                     # ขั้นนี้มีไว้เฉพาะกรณีขึ้นบรรทัดตามหลักฐาน
        result.matched.append(MatchPair(key=b[0].key, fiscal_year=b[0].fiscal_year,
                                        baseline=b[0], current=c[0],
                                        via=VIA_LINE_BREAK_JOINED))
        paired.update((id(b[0]), id(c[0])))
    if paired:
        result.baseline_only = [r for r in result.baseline_only if id(r) not in paired]
        result.current_only = [r for r in result.current_only if id(r) not in paired]


def _route_period_label_changes(result: MatchResult) -> None:
    """G5 (#14) — แถวเดียวกันแต่ป้ายช่วงเวลาไม่ตรงกัน ⇒ คิวมนุษย์ ไม่ใช่ เพิ่ม/ลบ

    🔴 ห้ามจับคู่เพียงเพราะปีเริ่มต้นตรงกัน (คำตัดสินกิ๊ฟ 8 ก.ย. 2569 ข้อ 2)
    แต่ก็ห้ามรายงานว่าแถวถูกเพิ่ม/ลบ เพราะแถวยังอยู่ — เปลี่ยนแค่ป้ายคอลัมน์
    record ทั้งสองฝั่งออกเป็น ``PERIOD_LABEL_CHANGED_REQUIRES_REVIEW``
    พร้อมป้ายดิบของตัวเอง (ชั้นเปรียบเทียบจับคู่ป้ายสองฝั่งให้คนเห็นพร้อมกัน)

    เกณฑ์ "แถวเดียวกัน" = ``T1BKey`` เดียวกันเท่านั้น — ไม่มีเงื่อนไขอื่น
    """
    def periods(recs):
        out: dict[T1BKey, list[T1BRecord]] = {}
        for r in recs:
            if r.comparison_axis == AXIS_PERIOD_RANGE and r.row_kind == ROW_KIND_VALUE:
                out.setdefault(r.key, []).append(r)
        return out

    base, curr = periods(result.baseline_only), periods(result.current_only)
    keys = base.keys() & curr.keys()
    if not keys:
        return
    moved: set[int] = set()
    for key in sorted(keys, key=repr):
        for side, recs in ((SIDE_BASELINE, base[key]), (SIDE_CURRENT, curr[key])):
            for r in recs:
                moved.add(id(r))
                result.needs_human.append(SidedRecord(side, replace(
                    r, uncertainty=tuple(r.uncertainty) + (UNC_PERIOD_LABEL_CHANGED,)
                )))
    result.baseline_only = [r for r in result.baseline_only if id(r) not in moved]
    result.current_only = [r for r in result.current_only if id(r) not in moved]
