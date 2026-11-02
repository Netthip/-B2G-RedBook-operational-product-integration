# -*- coding: utf-8 -*-
"""T1B — การเปรียบเทียบและสร้าง finding

รับผลจาก ``matching.match_records()`` แล้วออก finding ที่มนุษย์ตรวจต่อได้

**กติกาที่บังคับ**

1. เทียบจำนวนเงินหลัง ``normalize_amount`` ตามทศนิยมที่เอกสารประกาศ
   — เศษ floating-point ต้องไม่กลายเป็น finding
2. **ห้ามเทียบข้ามหน่วย** — ``บาท`` กับ ``ล้านบาท`` ต่างกันล้านเท่า ·
   ``ร้อยละ`` ไม่ใช่จำนวนเงิน ⇒ ออก ``NOT_COMPARABLE``
3. **เลขลำดับโครงการเปลี่ยนต้องออก finding** แม้จับคู่กันได้
   (คำตัดสิน Gift · ทาง (ค) · 1 ก.ย. 2569)
4. ทุก finding ต้องชี้กลับไฟล์/ชีต/เซลล์จริงได้ทั้งสองฝั่ง
5. **ระบบไม่ตัดสินแทนมนุษย์** — finding บอกว่า *อะไรเปลี่ยน* และ *ต้องดูตรงไหน*
   ส่วนคำตัดสินว่าเป็นการปรับที่ตั้งใจหรือไม่ เป็นของผู้ตรวจ

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .categories import CATEGORY_UNRESOLVED
from .keys import KEY_VERSION, T1BKey
from .matching import (
    SIDE_BASELINE,
    SIDE_CURRENT,
    VERDICT_CANNOT_DETERMINE,
    IdentityCheck,
    MatchPair,
    MatchResult,
    SidedRecord,
)
from .normalize import normalize_label
from .records import (
    AXIS_BUDGET_CATEGORY,
    AXIS_SINGLE_AMOUNT,
    ROW_KIND_UNSUPPORTED_COLUMN,
    ROW_KIND_UNSUPPORTED_PERIOD,
    UNC_PERIOD_LABEL_CHANGED,
    T1BRecord,
)
from .units import UNIT_UNRESOLVED, comparable_units

COMPARE_VERSION = "t1b-compare-0.9.0"

# ---------------------------------------------------------------- ชนิดของ finding
F_AMOUNT_INCREASED = "AMOUNT_INCREASED"
F_AMOUNT_DECREASED = "AMOUNT_DECREASED"
F_AMOUNT_UNCHANGED = "AMOUNT_UNCHANGED"
F_INDICATOR_CHANGED = "INDICATOR_CHANGED"
F_INDICATOR_UNCHANGED = "INDICATOR_UNCHANGED"
F_ROW_ADDED = "ROW_ADDED"
F_ROW_REMOVED = "ROW_REMOVED"
F_UNIT_CHANGED = "UNIT_CHANGED"
F_NOT_COMPARABLE = "NOT_COMPARABLE"
F_PROJECT_ORDINAL_CHANGED = "PROJECT_ORDINAL_CHANGED"
F_YEAR_ONLY_ONE_SIDE = "YEAR_PRESENT_ON_ONE_SIDE_ONLY"
F_AMBIGUOUS = "AMBIGUOUS_REQUIRES_HUMAN_REVIEW"
F_UNMAPPED = "UNMAPPED_REQUIRES_HUMAN_REVIEW"
#: G6 (#14) — เซลล์ตัวเลขใต้หัวคอลัมน์ที่อ่านไม่ออก · เดิมหายเงียบ
F_UNSUPPORTED_PERIOD = "UNSUPPORTED_PERIOD_LABEL_REQUIRES_REVIEW"
#: G5 (#14) — แถวเดียวกันแต่ป้ายช่วงเวลาไม่ตรงกันสองฝั่ง · ไม่จับคู่อัตโนมัติ
F_PERIOD_LABEL_CHANGED = "PERIOD_LABEL_CHANGED_REQUIRES_REVIEW"
#: invariant (#14) — คอลัมน์ไม่มีหัวในตารางจำแนกตามงบรายจ่าย · เดิมหายเงียบ
F_UNSUPPORTED_COLUMN = "UNSUPPORTED_VALUE_COLUMN_REQUIRES_REVIEW"

#: finding ที่ **ต้อง**ให้มนุษย์ตัดสินเสมอ
MUST_REVIEW = frozenset({
    F_NOT_COMPARABLE, F_UNIT_CHANGED, F_AMBIGUOUS, F_UNMAPPED,
    F_ROW_ADDED, F_ROW_REMOVED, F_PROJECT_ORDINAL_CHANGED,
    F_UNSUPPORTED_PERIOD, F_PERIOD_LABEL_CHANGED, F_UNSUPPORTED_COLUMN,
})

# ------------------------------------------------------------------ ธงของ finding
#: 🔴 **blocker #1** — ตารางแกนหมวดของสองฝั่งเป็นคนละปีงบประมาณ
#: finding ยังออกตามปกติ **ห้ามกรองทิ้ง** แต่ต้องติดป้ายให้ผู้อ่านเห็นทันที
#: ว่ากำลังเทียบยอดคนละปี (เกณฑ์หยุดทันทีข้อ 6 ของ Shadow Run รอบที่ 1)
FLAG_CATEGORY_TABLE_YEAR_DIFFERS = "CATEGORY_TABLE_YEAR_DIFFERS"
#: ปีบริบทของตารางแกนหมวดอ่านไม่ได้อย่างน้อยหนึ่งฝั่ง
FLAG_CATEGORY_TABLE_YEAR_UNKNOWN = "CATEGORY_TABLE_YEAR_UNKNOWN"

#: ธงที่ **บังคับ** ให้ finding เข้าคิวมนุษย์ ไม่ว่าชนิดของ finding จะเป็นอะไร
#: G1 (#14) — แถวค่าเดี่ยวของสองฝั่งมาจากเอกสารคนละปี / อ่านปีไม่ได้
FLAG_SINGLE_AMOUNT_YEAR_DIFFERS = "SINGLE_AMOUNT_DOCUMENT_YEAR_DIFFERS"
FLAG_SINGLE_AMOUNT_YEAR_UNKNOWN = "SINGLE_AMOUNT_DOCUMENT_YEAR_UNKNOWN"

#: G3 (#14) — จับคู่ได้หลังลบการขึ้นบรรทัดในป้ายเท่านั้น · ให้คนยืนยันว่าเป็นรายการเดียวกัน
FLAG_LABEL_MATCHED_AFTER_JOINING_LINE_BREAKS = "LABEL_MATCHED_AFTER_JOINING_LINE_BREAKS"

REVIEW_FLAGS = frozenset({
    FLAG_LABEL_MATCHED_AFTER_JOINING_LINE_BREAKS,
    FLAG_CATEGORY_TABLE_YEAR_DIFFERS,
    FLAG_CATEGORY_TABLE_YEAR_UNKNOWN,
    FLAG_SINGLE_AMOUNT_YEAR_DIFFERS,
    FLAG_SINGLE_AMOUNT_YEAR_UNKNOWN,
})


@dataclass(frozen=True)
class Location:
    """ตำแหน่งหลักฐานฝั่งเดียว — ชี้กลับ Excel จริงได้"""

    sheet: str
    cell: str | None
    row: int
    raw_value: object
    raw_label: object

    @classmethod
    def of(cls, rec: T1BRecord) -> "Location":
        return cls(sheet=rec.sheet_name_actual, cell=rec.cell_ref,
                   row=rec.row_index, raw_value=rec.raw_value,
                   raw_label=rec.raw_label)


@dataclass(frozen=True)
class Finding:
    """หนึ่งข้อค้นพบที่ผู้ตรวจต้องดู"""

    finding_type: str
    key: T1BKey
    fiscal_year: int | None = None
    baseline_value: Decimal | None = None
    current_value: Decimal | None = None
    difference: Decimal | None = None
    declared_unit: str = ""
    baseline_unit: str | None = None
    current_unit: str | None = None
    comparison_axis: str = ""
    budget_category: str | None = None
    budget_category_raw: object = None
    #: ปีบริบทของ **ตารางจำแนกตามงบรายจ่าย** ทั้งสองฝั่ง — blocker #1
    #: 🔴 ไม่ใช่ ``fiscal_year`` · record แกนหมวดมี ``fiscal_year = None`` เสมอ
    #: ตาม XOR ของ ``axis_valid`` ฟิลด์คู่นี้จึงเป็นทางเดียวที่ผู้อ่านจะรู้ว่า
    #: finding นี้เทียบยอดของปีใดกับปีใด
    baseline_category_table_year: int | None = None
    current_category_table_year: int | None = None
    #: G5 (#14) — ป้ายช่วงเวลาของแกน ``PERIOD_RANGE`` (หลัง normalize)
    period_label: str | None = None
    #: G1/RC-E (#14) — บทบาทเชิงเวลาของยอด (ฝั่งตั้งต้น ถ้ามี ไม่งั้นฝั่งปัจจุบัน)
    amount_role: str = ""
    baseline_location: Location | None = None
    current_location: Location | None = None
    detail: str = ""
    #: ธงเพิ่มเติมที่ไม่ขึ้นกับชนิดของ finding — ดู ``REVIEW_FLAGS``
    flags: tuple[str, ...] = ()

    @property
    def requires_human_decision(self) -> bool:
        """ระบบเสนอ — มนุษย์ตัดสิน

        🔴 blocker #1 — ธงใน ``REVIEW_FLAGS`` บังคับให้ต้องตรวจ **แม้ชนิดของ
        finding จะเป็น ``AMOUNT_*`` ที่ปกติไม่ต้องตรวจ** เพราะยอดที่ดูสมเหตุสมผล
        แต่มาจากคนละปี อันตรายกว่าค่าที่ผิดอย่างเห็นได้ชัด
        """
        return (
            self.finding_type in MUST_REVIEW
            or bool(REVIEW_FLAGS.intersection(self.flags))
        )


@dataclass
class CompareResult:
    findings: list[Finding] = field(default_factory=list)
    #: 🔴 blocker #3 — ผลด่านตัวตนหน่วยงานของรอบนี้ ต้องรายงานคู่กับ finding เสมอ
    #: ``verified = False`` **ไม่เท่ากับ** ผ่าน · ดู ``matching.IdentityCheck``
    identity: "IdentityCheck | None" = None
    #: จำนวนคู่ที่ระบบจับได้ **เอง** — ตัวเลขที่ Bo สั่งให้เห็นได้ที่ระดับ
    #: การเปรียบเทียบ เพื่อพิสูจน์ว่าเมื่อด่านไม่ผ่านแล้วเป็น ``0`` จริง
    automatic_pairs: int = 0

    @property
    def verdict(self) -> str:
        """ผลระดับการเปรียบเทียบ — ค่าเริ่มต้นอยู่ข้าง **ปฏิเสธ** เสมอ"""
        return self.identity.verdict if self.identity else VERDICT_CANNOT_DETERMINE

    def by_type(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.finding_type] = out.get(f.finding_type, 0) + 1
        return dict(sorted(out.items()))

    def requiring_review(self) -> list[Finding]:
        return [f for f in self.findings if f.requires_human_decision]

    def by_flag(self) -> dict[str, int]:
        """จำนวน finding ต่อธง — 🔴 ต้องรายงานคู่กับ ``by_type`` เสมอ"""
        out: dict[str, int] = {}
        for f in self.findings:
            for flag in f.flags:
                out[flag] = out.get(flag, 0) + 1
        return dict(sorted(out.items()))

    def summary(self) -> dict[str, object]:
        return {
            "key_version": KEY_VERSION,
            "compare_version": COMPARE_VERSION,
            "total_findings": len(self.findings),
            "by_type": self.by_type(),
            "by_flag": self.by_flag(),
            "requiring_human_decision": len(self.requiring_review()),
            "identity_reason": self.identity.reason if self.identity else None,
            "identity_verified": bool(self.identity and self.identity.verified),
            "identity_conflict": bool(self.identity and self.identity.conflict),
            "identity_verdict": self.verdict,
            "identity_gate_blocked": bool(
                self.identity.blocked if self.identity else True
            ),
            "automatic_pairs": self.automatic_pairs,
        }


def _category_year_flags(
    base: T1BRecord | None, curr: T1BRecord | None
) -> tuple[tuple[str, ...], str]:
    """ธงเรื่องปีบริบทของตารางแกนหมวด + ข้อความอธิบายที่ต่อท้าย ``detail``

    🔴 **blocker #1** — ใช้เฉพาะกับ record ที่แกนเทียบเป็น ``BUDGET_CATEGORY``
    record แกนปีมี ``fiscal_year`` อยู่แล้วและมีด่านปีของตัวเองที่ชั้นจับคู่
    """
    sides = [r for r in (base, curr) if r is not None]
    if sides and all(r.comparison_axis == AXIS_SINGLE_AMOUNT for r in sides):
        # G1 (#14) — แถวค่าเดี่ยวผูกกับปีของเอกสาร · คนละปี = คนละยอด
        years = [r.category_table_fiscal_year for r in sides]
        if any(y is None for y in years):
            return (FLAG_SINGLE_AMOUNT_YEAR_UNKNOWN,), (
                " · 🔴 อ่านปีของเอกสารไม่ได้อย่างน้อยหนึ่งฝั่ง — ห้ามสรุปว่าเทียบปีเดียวกัน")
        if len(set(years)) > 1 and base is not None and curr is not None:
            return (FLAG_SINGLE_AMOUNT_YEAR_DIFFERS,), (
                f" · 🔴 แถวค่าเดี่ยวมาจากเอกสารคนละปี — ฉบับตั้งต้นปี "
                f"{base.category_table_fiscal_year} ฉบับปัจจุบันปี "
                f"{curr.category_table_fiscal_year}")
        return (), ""
    if not sides or not all(r.comparison_axis == AXIS_BUDGET_CATEGORY for r in sides):
        return (), ""

    years = [r.category_table_fiscal_year for r in sides]
    if any(y is None for y in years):
        return (FLAG_CATEGORY_TABLE_YEAR_UNKNOWN,), (
            " · 🔴 ปีบริบทของตารางจำแนกตามงบรายจ่ายอ่านไม่ได้อย่างน้อยหนึ่งฝั่ง "
            "— ห้ามสรุปว่าเทียบปีเดียวกัน"
        )
    if len(set(years)) > 1 and base is not None and curr is not None:
        return (FLAG_CATEGORY_TABLE_YEAR_DIFFERS,), (
            f" · 🔴 ตารางจำแนกตามงบรายจ่ายคนละปีงบประมาณ — "
            f"ฉบับตั้งต้นปี {base.category_table_fiscal_year} "
            f"ฉบับปัจจุบันปี {curr.category_table_fiscal_year} "
            f"(ที่มาของปี: {base.category_table_year_source} / "
            f"{curr.category_table_year_source})"
        )
    return (), ""


def _one_sided(finding_type: str, sided: SidedRecord, detail: str) -> Finding:
    """สร้าง finding ของ record ที่มีอยู่ฝั่งเดียว โดย**คงไว้ว่ามาจากฝั่งใด**"""
    rec = sided.record
    location = Location.of(rec)
    is_base = sided.side == SIDE_BASELINE
    flags, note = _category_year_flags(rec if is_base else None, None if is_base else rec)
    return Finding(
        finding_type=finding_type, key=rec.key, fiscal_year=rec.fiscal_year,
        baseline_category_table_year=rec.category_table_fiscal_year if is_base else None,
        current_category_table_year=None if is_base else rec.category_table_fiscal_year,
        flags=flags,
        comparison_axis=rec.comparison_axis, budget_category=rec.budget_category,
        budget_category_raw=rec.budget_category_raw, declared_unit=rec.declared_unit,
        period_label=rec.period_label, amount_role=rec.amount_role,
        baseline_value=rec.value_decimal if is_base else None,
        current_value=None if is_base else rec.value_decimal,
        baseline_unit=rec.declared_unit if is_base else None,
        current_unit=None if is_base else rec.declared_unit,
        baseline_location=location if is_base else None,
        current_location=None if is_base else location,
        detail=f"[{sided.side}] {detail}{note}",
    )


def _compare_pair(pair: MatchPair) -> Finding:
    base, curr = pair.baseline, pair.current
    # 🔴 blocker #1 — ธงปีบริบทต้องติดกับ finding **ทุกทาง** ของฟังก์ชันนี้
    # ไม่ใช่เฉพาะทางที่เทียบค่าได้สำเร็จ
    cat_flags, cat_note = _category_year_flags(base, curr)
    if pair.via:
        # G3 (#14) — ต้องเห็นป้ายดิบสองฝั่งพร้อมกัน
        cat_flags = cat_flags + (FLAG_LABEL_MATCHED_AFTER_JOINING_LINE_BREAKS,)
        cat_note = cat_note + (
            f" · 🔴 จับคู่ได้หลังลบการขึ้นบรรทัดในป้ายเท่านั้น — ฉบับตั้งต้น "
            f"{base.raw_label!r} · ฉบับปัจจุบัน {curr.raw_label!r}")
    year_fields = dict(
        baseline_category_table_year=base.category_table_fiscal_year,
        current_category_table_year=curr.category_table_fiscal_year,
        flags=cat_flags,
    )

    if not comparable_units(base.declared_unit, curr.declared_unit):
        ftype = (
            F_UNIT_CHANGED
            if UNIT_UNRESOLVED not in (base.declared_unit, curr.declared_unit)
            else F_NOT_COMPARABLE
        )
        detail = (
            f"หน่วยนับต่างกัน — ฉบับตั้งต้น {base.declared_unit!r} "
            f"ฉบับปัจจุบัน {curr.declared_unit!r} · ห้ามเทียบค่าโดยตรง"
        )
        return Finding(
            finding_type=ftype, key=pair.key, fiscal_year=pair.fiscal_year,
            baseline_unit=base.declared_unit, current_unit=curr.declared_unit,
            baseline_location=Location.of(base), current_location=Location.of(curr),
            detail=detail + cat_note, **year_fields,
        )

    a, b = base.value_decimal, curr.value_decimal
    if a is None or b is None:
        return Finding(
            finding_type=F_NOT_COMPARABLE, key=pair.key, fiscal_year=pair.fiscal_year,
            declared_unit=base.declared_unit,
            baseline_location=Location.of(base), current_location=Location.of(curr),
            detail="ค่าฝั่งใดฝั่งหนึ่งแปลงเป็นตัวเลขไม่ได้ — ต้องให้มนุษย์ตรวจ" + cat_note,
            **year_fields,
        )

    diff = b - a
    if base.is_monetary:
        if diff > 0:
            ftype = F_AMOUNT_INCREASED
        elif diff < 0:
            ftype = F_AMOUNT_DECREASED
        else:
            ftype = F_AMOUNT_UNCHANGED
    else:
        ftype = F_INDICATOR_UNCHANGED if diff == 0 else F_INDICATOR_CHANGED

    return Finding(
        finding_type=ftype, key=pair.key, fiscal_year=pair.fiscal_year,
        comparison_axis=base.comparison_axis,
        budget_category=base.budget_category,
        budget_category_raw=base.budget_category_raw,
        period_label=base.period_label,
        amount_role=base.amount_role or curr.amount_role,
        baseline_value=a, current_value=b, difference=diff,
        declared_unit=base.declared_unit,
        baseline_unit=base.declared_unit, current_unit=curr.declared_unit,
        baseline_location=Location.of(base), current_location=Location.of(curr),
        detail=cat_note.lstrip(" ·").strip(), **year_fields,
    )


def _ordinal_findings(matched: list[MatchPair]) -> list[Finding]:
    """ออก finding เมื่อ **เลขลำดับโครงการเปลี่ยน** แม้จับคู่กันได้

    🔴 บังคับตามคำตัดสิน Gift ทาง (ค) — จับคู่ได้ แต่ต้องไม่กลบข้อเท็จจริง
    ว่าเลขลำดับเปลี่ยน
    """
    # 🔴 dedupe ที่ **ตัวโครงการ** ไม่ใช่ที่แถว — เลขลำดับเป็นคุณสมบัติของ
    # ทั้งชีตโครงการ ถ้า dedupe ด้วย T1BKey เต็ม (ซึ่งมี row_label) จะได้
    # finding ซ้ำหนึ่งใบต่อหนึ่งแถวที่จับคู่ได้ (พบจริง 15 ใบสำหรับ 2 โครงการ)
    seen: dict[tuple[str, str, str], MatchPair] = {}
    for pair in matched:
        if pair.baseline.project_ordinal_raw == pair.current.project_ordinal_raw:
            continue
        identity = (
            pair.key.sheet_role,
            pair.key.section_title_norm,
            pair.key.parent_plan_norm,
        )
        seen.setdefault(identity, pair)

    out = []
    for _identity, pair in seen.items():
        key = pair.key
        a = pair.baseline.project_ordinal_raw
        b = pair.current.project_ordinal_raw
        out.append(Finding(
            finding_type=F_PROJECT_ORDINAL_CHANGED, key=key,
            fiscal_year=pair.fiscal_year,
            # 🔴 review fix (Bo) — ต้องชี้กลับชีต/แถวจริงทั้งสองฝั่ง
            # ตำแหน่งที่ชี้เป็น **แถวตัวแทน** ของโครงการ เพราะเลขลำดับเป็น
            # คุณสมบัติของทั้งชีตโครงการ ไม่ใช่ของแถวใดแถวหนึ่ง
            baseline_location=Location.of(pair.baseline),
            current_location=Location.of(pair.current),
            detail=(
                f"ชื่อโครงการตรงกันแต่เลขลำดับเปลี่ยน — "
                f"ฉบับตั้งต้น {a!r} ({pair.baseline.sheet_name_actual}) "
                f"ฉบับปัจจุบัน {b!r} ({pair.current.sheet_name_actual}) · "
                f"จับคู่ด้วยชื่อโครงการตามคำตัดสินทาง (ค) · "
                f"หนึ่ง finding ต่อหนึ่งโครงการ ตำแหน่งที่ชี้เป็นแถวตัวแทน"
            ),
        ))
    return out


def _review_reason(rec: T1BRecord) -> str:
    """เหตุผลที่ต้องให้มนุษย์ตรวจ — **ห้ามว่าง** มิฉะนั้นคิวอ่านไม่รู้เรื่อง"""
    markers = [m for m in rec.uncertainty if m]
    if rec.budget_category == CATEGORY_UNRESOLVED:
        raw = normalize_label(rec.budget_category_raw)
        markers.append(f"หมวดงบรายจ่ายที่ยัง resolve ไม่ได้: {raw!r}")
    return ", ".join(dict.fromkeys(markers)) or "ไม่ระบุเหตุผล"


def _other_side(side: str) -> str:
    return SIDE_CURRENT if side == SIDE_BASELINE else SIDE_BASELINE


def _period_label_peers(needs_human) -> dict:
    """(คีย์, ฝั่ง) -> ป้ายช่วงเวลาดิบของ record ที่ป้ายไม่ตรงกัน — ให้คนเห็นสองฝั่งพร้อมกัน"""
    out: dict = {}
    for sided in needs_human:
        rec = sided.record
        if UNC_PERIOD_LABEL_CHANGED in rec.uncertainty:
            labels = out.setdefault((rec.key, sided.side), [])
            raw = str(rec.fiscal_year_label)
            if raw not in labels:
                labels.append(raw)
    return {k: tuple(v) for k, v in out.items()}


def compare(result: MatchResult) -> CompareResult:
    """สร้าง finding จากผลการจับคู่

    ทุกกลุ่มของ ``MatchResult`` ต้องกลายเป็น finding — ไม่มีอะไรหายเงียบ
    """
    out = CompareResult(
        identity=result.identity, automatic_pairs=len(result.matched)
    )

    for pair in result.matched:
        out.findings.append(_compare_pair(pair))

    out.findings.extend(_ordinal_findings(result.matched))

    for rec in result.baseline_only:
        out.findings.append(Finding(
            finding_type=F_ROW_REMOVED, key=rec.key, fiscal_year=rec.fiscal_year,
            period_label=rec.period_label, amount_role=rec.amount_role,
            comparison_axis=rec.comparison_axis,
            budget_category=rec.budget_category,
            budget_category_raw=rec.budget_category_raw,
            baseline_value=rec.value_decimal, declared_unit=rec.declared_unit,
            baseline_unit=rec.declared_unit, baseline_location=Location.of(rec),
            baseline_category_table_year=rec.category_table_fiscal_year,
            detail="มีในฉบับตั้งต้นแต่ไม่พบในฉบับปัจจุบัน",
        ))

    for rec in result.current_only:
        out.findings.append(Finding(
            finding_type=F_ROW_ADDED, key=rec.key, fiscal_year=rec.fiscal_year,
            period_label=rec.period_label, amount_role=rec.amount_role,
            comparison_axis=rec.comparison_axis,
            budget_category=rec.budget_category,
            budget_category_raw=rec.budget_category_raw,
            current_value=rec.value_decimal, declared_unit=rec.declared_unit,
            current_unit=rec.declared_unit, current_location=Location.of(rec),
            current_category_table_year=rec.category_table_fiscal_year,
            detail="พบในฉบับปัจจุบันแต่ไม่มีในฉบับตั้งต้น",
        ))

    # 🔴 review fix (Bo) — record ฝั่งเดียวต้องคงไว้ว่ามาจากฝั่งใด
    # 🔴 blocker #3 · fail-closed — เมื่อด่านตัวตนหน่วยงาน **ไม่ผ่านด้วยเหตุใดก็ตาม**
    # ทุก record เข้าคิวมนุษย์ และเหตุผลต้องบอกตรง ๆ ว่าถูกกันเพราะอะไร
    # ห้ามให้ผู้อ่านเห็นเหตุผลว่างเปล่า และห้ามให้ ``ยืนยันไม่ได้`` เงียบกว่า ``ขัดแย้ง``
    identity_note = result.identity.note if result.identity is not None else ""
    period_peers = _period_label_peers(result.needs_human)
    for sided in result.needs_human:
        rec = sided.record
        if (rec.row_kind == ROW_KIND_UNSUPPORTED_PERIOD
                and not (result.identity and result.identity.blocked)):
            # G6 (#14) — ชนิดเฉพาะ ไม่ปนกับ AMBIGUOUS ทั่วไป
            out.findings.append(_one_sided(
                F_UNSUPPORTED_PERIOD, sided,
                f"หัวคอลัมน์อ่านไม่ออก แต่เซลล์มีตัวเลข — หัวคอลัมน์ดิบ "
                f"{rec.raw_header_label!r} · ระบบไม่ตีความค่านี้ ต้องให้คนตรวจ",
            ))
            continue
        if (rec.row_kind == ROW_KIND_UNSUPPORTED_COLUMN
                and not (result.identity and result.identity.blocked)):
            out.findings.append(_one_sided(
                F_UNSUPPORTED_COLUMN, sided,
                f"คอลัมน์ไม่มีหัวในตารางจำแนกตามงบรายจ่าย แต่เซลล์มีตัวเลข — "
                f"หัวคอลัมน์ดิบ {rec.raw_header_label!r} · ระบบไม่ตีความค่านี้",
            ))
            continue
        if (UNC_PERIOD_LABEL_CHANGED in rec.uncertainty
                and not (result.identity and result.identity.blocked)):
            other = period_peers.get((rec.key, _other_side(sided.side)), ())
            out.findings.append(_one_sided(
                F_PERIOD_LABEL_CHANGED, sided,
                f"ป้ายช่วงเวลาไม่ตรงกันสองฝั่ง — ฝั่งนี้ {rec.fiscal_year_label!r} · "
                f"อีกฝั่ง {list(other)!r} · 🔴 ไม่จับคู่เพราะคนละช่วงเวลาคือคนละความหมาย",
            ))
            continue
        # 🔴 **ต่อกัน ไม่ใช่แทนที่** — เหตุผลรายรายการเป็น provenance ของ record นั้น
        # ถ้าเอาเหตุผลของด่านมาทับ ผู้ตรวจจะไม่รู้ว่านอกจากเรื่องตัวตนหน่วยงานแล้ว
        # รายการนี้ยังมีความกำกวมอะไรของตัวเองอีก
        parts = [p for p in (identity_note, _review_reason(sided.record)) if p]
        out.findings.append(_one_sided(
            F_AMBIGUOUS, sided, f"ระบบตีความไม่ได้ — {' · '.join(parts)}",
        ))

    for sided in result.unmapped:
        out.findings.append(_one_sided(
            F_UNMAPPED, sided,
            f"ชีตยังไม่ map — {', '.join(sided.record.uncertainty)}",
        ))

    # 🔴 review fix (Bo) — ปีที่มีข้างเดียวคิด **รายขอบเขตชีต** ไม่ใช่ union ทั้งสมุดงาน
    for scope in result.scopes_with_year_gap():
        role, title, parent = scope.scope
        for year in scope.baseline_only:
            out.findings.append(Finding(
                finding_type=F_YEAR_ONLY_ONE_SIDE,
                key=T1BKey(agency_code="", document_level="", sheet_role=role,
                           section_title_norm=title, parent_plan_norm=parent),
                fiscal_year=year,
                detail=(f"ปี {year} มีเฉพาะในฉบับตั้งต้น ที่ขอบเขต {scope.label} "
                        f"— ไม่นำมาเทียบ"),
            ))
        for year in scope.current_only:
            out.findings.append(Finding(
                finding_type=F_YEAR_ONLY_ONE_SIDE,
                key=T1BKey(agency_code="", document_level="", sheet_role=role,
                           section_title_norm=title, parent_plan_norm=parent),
                fiscal_year=year,
                detail=(f"ปี {year} มีเฉพาะในฉบับปัจจุบัน ที่ขอบเขต {scope.label} "
                        f"— ไม่นำมาเทียบ"),
            ))

    return out
