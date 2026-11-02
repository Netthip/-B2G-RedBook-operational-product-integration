# -*- coding: utf-8 -*-
"""T1B — การกระทบยอด (roll-up / reconciliation)

ปลดโดย ``BO FINAL PASS`` (2 กันยายน 2569 · ผูกกับ commit ``50a97de``)

**กฎที่บังคับ**

1. 🔒 ``t1b-key-0.1.0`` **ไม่ถูกเปลี่ยน** — โมดูลนี้อ่าน record อย่างเดียว
2. 🔴 หมวดที่ยัง ``resolve`` ไม่ได้ **ห้ามเข้า roll-up อัตโนมัติ**
3. ต้องรักษา **raw provenance** ทุกชั้น — ทุกตัวตั้งย้อนถึง
   ``source_file`` · ``source_hash`` · ชีต · เซลล์ · ค่าดิบ
4. ทุกชุดที่พิจารณาต้องถูก **accounted เสมอ** ห้าม silent-drop

🔴 **ข้อ 4 เคยถูกละเมิดโดยโมดูลนี้เอง** (BO REVIEW · 2 ก.ย. 2569) —
record ที่หน่วยยัง resolve ไม่ได้ถูกคัดออก **ก่อน** ถึงด่านตรวจ ทำให้ค่าหายเงียบ
แล้วชุดนั้นยังคืน ``OK`` · และชุดตัวตั้งที่มาไม่ครบก็ยังคืน ``OK`` ได้
ตั้งแต่ ``0.3.0`` เป็นต้นไป **ไม่มีการคัด record ทิ้งก่อนถึงด่านตรวจอีก**

**กฎผลรวมในโมดูลนี้มาจากการสำรวจแฟ้มจริง 6 แฟ้ม ไม่ได้ตั้งขึ้นเอง**
กฎที่สำรวจแล้ว **ไม่พบว่าเป็นจริง** จะไม่ถูกใส่ไว้ที่นี่ — โดยเฉพาะ
"ผลรวมของแผนงาน ``7.x`` เท่ากับยอดรวมของหน่วยงาน" ซึ่งพบว่าไม่ตรงในหลายปี
เพราะแต่ละชีตครอบคลุมปีไม่เท่ากัน ⇒ **ต้องให้มนุษย์ตัดสิน ห้ามยืนยันอัตโนมัติ**

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from .categories import CATEGORY_TOTAL, CATEGORY_UNRESOLVED
from .keys import KEY_VERSION
from .records import ROW_KIND_VALUE, T1BRecord
from .units import UNIT_UNRESOLVED, comparable_units, quantum_for

ROLLUP_VERSION = "t1b-rollup-0.5.0"

#: หน่วยละเอียดที่สุดที่ ``normalize_amount()`` ปัดให้
QUANTUM = Decimal("0.0001")

# ------------------------------------------------------------------ กฎ
RULE_CATEGORY_TOTAL = "CATEGORY_SUBTOTALS_TO_TOTAL"
RULE_GRAND_SPLIT = "GRAND_TOTAL_SPLITS_BY_FUNDING_SOURCE"
RULE_FUNDING_LINE_SUM = "FUNDING_LINE_SUMS_TO_SHEET_SUBTOTAL"
RULE_CROSS_SHEET_GRAND = "GRAND_TOTAL_AGREES_ACROSS_SHEETS"

STATUS_OK = "OK"
STATUS_MISMATCH = "MISMATCH"
#: ส่วนต่างเล็กพอที่ **อาจ** อธิบายด้วยการปัดทศนิยมได้ — ยังไม่ยืนยัน
#:
#: 🔴 คำตัดสิน Gift (ทาง ข) ให้แยกกองนี้ออกจากยอดที่ผิดจริง
#: 🔴 BO REVIEW (2 ก.ย.) ให้เรียกว่า **candidate** — ระบบยัง **ไม่ได้พิสูจน์**
#: ว่าเกิดจากการปัดจริง เพียงแต่ขนาดของส่วนต่างไม่เกินขอบที่การปัดอธิบายได้
#: การยืนยันเป็นของมนุษย์ · ไม่ใช่ tolerance และไม่กลบเป็น ``OK``
STATUS_ROUNDING_RESIDUE_CANDIDATE = "ROUNDING_RESIDUE_CANDIDATE"
#: ชุดตัวตั้งมาไม่ครบ / ซ้ำ / ไม่มียอดอ้างอิง — **ห้ามสรุปว่าตรง**
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_HUMAN_REVIEW = "HUMAN_REVIEW"

# ป้ายแถวที่ใช้เป็นจุดยึด — พบในแฟ้มจริงทั้ง 6 แฟ้ม
LABEL_GRAND_TOTAL = "รวมทั้งสิ้น"
LABEL_SUBTOTAL_IN = "รวมเงินงบประมาณ"
LABEL_SUBTOTAL_OUT = "รวมเงินนอกงบประมาณ"
LABEL_LINE_IN = "เงินงบประมาณ"
LABEL_LINE_OUT = "เงินนอกงบประมาณ"

FUNDING_PAIRS = (
    (LABEL_SUBTOTAL_IN, LABEL_LINE_IN),
    (LABEL_SUBTOTAL_OUT, LABEL_LINE_OUT),
)


@dataclass(frozen=True)
class Component:
    """หนึ่งตัวตั้ง (หรือยอดอ้างอิง) ของการกระทบยอด

    🔴 ต้องย้อนถึงต้นทางได้จริง — ``source_file`` + ``source_hash`` + ชีต +
    เซลล์ + **ค่าดิบก่อนแปลง** · ไม่ใช่แค่ชีตกับเซลล์
    """

    label: str
    value: Decimal | None
    raw_value: object
    sheet: str
    cell: str | None
    row: int
    source_file: str = ""
    source_hash: str = ""
    declared_unit: str = ""
    #: ข้อความประกาศหน่วยของแถวนั้น เช่น ``"หน่วย : บาท (ทศนิยม 3 ตำแหน่ง)"``
    #: 🔴 ต้องเก็บไว้ เพราะขอบการปัดต้องอิงความละเอียดที่ประกาศจริง ไม่ใช่
    #: ค่าปริยายตามชนิดหน่วย (BO REVIEW · 3 ก.ย.)
    unit_declaration: object = None
    budget_category: str | None = None
    budget_category_raw: object = None
    usable: bool = True
    unusable_reason: str = ""

    @property
    def traceable(self) -> bool:
        """ย้อนกลับต้นทางได้ครบทุกชั้นหรือไม่"""
        return bool(self.source_file and self.source_hash and self.sheet and self.cell)


@dataclass(frozen=True)
class RollupCheck:
    """ผลการกระทบยอดหนึ่งชุด"""

    rule: str
    status: str
    scope: str
    declared: Decimal | None
    computed: Decimal | None
    components: tuple[Component, ...]
    targets: tuple[Component, ...] = ()
    declared_unit: str = ""
    detail: str = ""

    @property
    def target(self) -> Component | None:
        """ยอดอ้างอิง — มีตัวเดียวเมื่อชุดสมบูรณ์"""
        return self.targets[0] if len(self.targets) == 1 else None

    @property
    def difference(self) -> Decimal | None:
        if self.declared is None or self.computed is None:
            return None
        return self.declared - self.computed

    @property
    def rounding_bound(self) -> Decimal:
        """ขอบที่การปัดแบบ round-to-nearest อธิบายได้

        คิด **รายรายการตามหน่วยของตัวมันเอง**::

            bound = (q_target + Σ q_component) ÷ 2

        ทุกตัวถูกปัดมาแล้วตัวละไม่เกิน ``q/2`` ทั้งตัวตั้งและยอดที่ประกาศไว้
        ถ้าทุกตัวละเอียดเท่ากัน สูตรนี้ลดรูปเป็น ``(n+1) × q ÷ 2``

        🔴 BO REVIEW (2 ก.ย.) สองรอบ:
        รอบแรกขอบ ``n × q`` **กว้างเกิน** · รอบสองใช้ ``QUANTUM`` ตายตัวที่
        ``0.0001`` กับทุกหน่วย ทั้งที่ ``บาท`` ประกาศทศนิยม 2 ตำแหน่ง
        ⇒ ยอดหน่วยบาทที่ต่าง ``0.01`` ถูกตัดสินเป็นยอดผิดจริงอย่างไม่เป็นธรรม
        """
        parts = sum(
            (quantum_for(c.declared_unit, c.unit_declaration)
             for c in self.components),
            Decimal(0),
        )
        if self.targets:
            t = self.targets[0]
            head = quantum_for(t.declared_unit, t.unit_declaration)
        else:
            head = quantum_for("")
        return (head + parts) / 2

    @property
    def within_rounding_bound(self) -> bool:
        """ขนาดส่วนต่างไม่เกินขอบที่การปัดอธิบายได้หรือไม่

        🔴 **ไม่ใช่การยืนยันว่าเกิดจากการปัดจริง** — เป็นเพียงเงื่อนไขขนาด
        การยืนยันเป็นของมนุษย์ (สถานะจึงเรียกว่า ``CANDIDATE``)
        """
        diff = self.difference
        return diff is not None and abs(diff) <= self.rounding_bound

    @property
    def requires_human_decision(self) -> bool:
        """ทุกสถานะที่ไม่ใช่ ``OK`` ต้องให้มนุษย์ตัดสิน — ไม่มีข้อยกเว้น"""
        return self.status != STATUS_OK

    @property
    def fully_traceable(self) -> bool:
        return all(c.traceable for c in self.components + self.targets)


@dataclass
class RollupResult:
    checks: list[RollupCheck] = field(default_factory=list)

    def by_rule(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for c in self.checks:
            out.setdefault(c.rule, {})
            out[c.rule][c.status] = out[c.rule].get(c.status, 0) + 1
        return {k: dict(sorted(v.items())) for k, v in sorted(out.items())}

    def _of(self, status: str) -> list[RollupCheck]:
        return [c for c in self.checks if c.status == status]

    def exact_ok(self) -> list[RollupCheck]:
        return self._of(STATUS_OK)

    def mismatches(self) -> list[RollupCheck]:
        """ยอดที่ต่างเกินกว่าการปัดจะอธิบายได้ — **material mismatch**"""
        return self._of(STATUS_MISMATCH)

    def rounding_residue_candidates(self) -> list[RollupCheck]:
        """ยอดที่ต่างในขนาดที่การปัด **อาจ** อธิบายได้ — รอมนุษย์ยืนยัน"""
        return self._of(STATUS_ROUNDING_RESIDUE_CANDIDATE)

    def incomplete(self) -> list[RollupCheck]:
        return self._of(STATUS_INCOMPLETE)

    def needing_human(self) -> list[RollupCheck]:
        return [c for c in self.checks if c.requires_human_decision]

    def summary(self) -> dict[str, object]:
        return {
            "key_version": KEY_VERSION,
            "rollup_version": ROLLUP_VERSION,
            "checks": len(self.checks),
            "by_rule": self.by_rule(),
            "exact_ok": len(self.exact_ok()),
            "material_mismatches": len(self.mismatches()),
            "rounding_residue_candidates": len(self.rounding_residue_candidates()),
            "incomplete": len(self.incomplete()),
            "requiring_human_decision": len(self.needing_human()),
        }


# ------------------------------------------------------------------ ตัวช่วย
def _has_raw_content(raw: object) -> bool:
    """เซลล์นี้มีเนื้อหาอยู่จริงหรือไม่

    🔴 BO REVIEW (3 ก.ย.): ต้องแยก **เซลล์ว่างจริง** (ไม่มียอดให้กระทบ)
    ออกจาก **เซลล์ที่มีเนื้อหาแต่แปลงเป็นตัวเลขไม่ได้** เช่น ``"#VALUE!"``
    ซึ่งอาจเป็นยอดจริงที่อ่านไม่ออก และ **ห้ามหายเงียบ**
    """
    if raw is None:
        return False
    if isinstance(raw, str):
        return bool(raw.strip())
    return True


def _unusable_reason(rec: T1BRecord) -> str:
    """เหตุที่ record นี้เข้าการบวกอัตโนมัติไม่ได้ — คืน ``""`` ถ้าเข้าได้"""
    if rec.row_kind != ROW_KIND_VALUE:
        return f"ไม่ใช่แถวที่มีค่า ({rec.row_kind})"
    if rec.value_decimal is None:
        if _has_raw_content(rec.raw_value):
            # 🔴 มีเนื้อหาในเซลล์แต่แปลงไม่ได้ — อาจเป็นยอดจริงที่อ่านไม่ออก
            return f"ค่าดิบแปลงเป็นตัวเลขไม่ได้ ({rec.raw_value!r})"
        return "เซลล์ว่าง ไม่มีค่าตัวเลข"
    if not rec.is_monetary:
        return f"ไม่ใช่จำนวนเงิน (หน่วย {rec.declared_unit!r})"
    if rec.declared_unit == UNIT_UNRESOLVED:
        return "หน่วยยัง resolve ไม่ได้"
    if not rec.axis_valid:
        # 🔴 BO REVIEW (2 ก.ย.): record ที่ประกาศแกนเทียบผิดเคยถูกบวก
        # และคืน ``OK`` ได้เมื่อยอดบังเอิญตรง ทั้งที่ contract ระบุว่า
        # ต้องให้มนุษย์ตัดสิน · roll-up ไม่เคยถาม ``axis_valid`` เลย
        return (f"แกนเทียบไม่ถูกต้อง (axis={rec.comparison_axis} "
                f"year={rec.fiscal_year} category={rec.budget_category})")
    return ""


def _component(rec: T1BRecord, source_file: str, source_hash: str) -> Component:
    reason = _unusable_reason(rec)
    return Component(
        label=rec.key.row_label_norm,
        value=rec.value_decimal,
        raw_value=rec.raw_value,
        sheet=rec.sheet_name_actual,
        cell=rec.cell_ref,
        row=rec.row_index,
        source_file=source_file,
        source_hash=source_hash,
        declared_unit=rec.declared_unit,
        unit_declaration=rec.raw_unit_cell,
        budget_category=rec.budget_category,
        budget_category_raw=rec.budget_category_raw,
        usable=not reason,
        unusable_reason=reason,
    )


def _units_agree(recs: list[T1BRecord]) -> bool:
    units = {r.declared_unit for r in recs}
    if len(units) <= 1:
        return True
    first = recs[0].declared_unit
    return all(comparable_units(first, u) for u in units)


def _check(
    rule: str,
    scope: str,
    targets: list[T1BRecord],
    parts: list[T1BRecord],
    *,
    source_file: str,
    source_hash: str,
    expected_parts: int | None = None,
    problems: tuple[str, ...] = (),
    detail: str = "",
) -> RollupCheck:
    """สร้างผลการกระทบยอดหนึ่งชุด

    🔴 **ทุก record ที่เกี่ยวข้องถูกส่งเข้ามาที่นี่เสมอ** รวมทั้งตัวที่ใช้บวกไม่ได้
    การคัดทิ้งก่อนถึงจุดนี้คือ silent-drop — ห้ามทำ
    """
    comps = tuple(_component(p, source_file, source_hash) for p in parts)
    tgts = tuple(_component(t, source_file, source_hash) for t in targets)
    declared = targets[0].value_decimal if len(targets) == 1 else None
    unit = targets[0].declared_unit if len(targets) == 1 else ""
    base = dict(
        rule=rule, scope=scope, components=comps, targets=tgts,
        declared=declared, declared_unit=unit,
    )

    issues = list(problems)
    if len(targets) != 1:
        issues.append(
            f"ยอดอ้างอิงต้องมีรายการเดียว แต่พบ {len(targets)} รายการ"
        )
    if not parts:
        issues.append("ไม่พบตัวตั้งเลย")
    elif expected_parts is not None and len(parts) != expected_parts:
        issues.append(
            f"ตัวตั้งต้องมี {expected_parts} รายการ แต่พบ {len(parts)} รายการ"
        )
    if issues:
        return RollupCheck(
            status=STATUS_INCOMPLETE, computed=None,
            detail="ชุดไม่สมบูรณ์ — " + " · ".join(issues), **base,
        )

    everything = parts + targets

    # 🔴 record ที่ใช้บวกไม่ได้ ต้อง **ไม่ถูกทิ้ง** — ทั้งชุดไปหามนุษย์
    unusable = [c for c in comps + tgts if not c.usable]
    if unusable:
        why = " · ".join(sorted({
            f"{c.sheet}!{c.cell} {c.label!r} = {c.raw_value!r} ({c.unusable_reason})"
            for c in unusable
        }))
        return RollupCheck(
            status=STATUS_HUMAN_REVIEW, computed=None,
            detail=f"มีรายการที่บวกอัตโนมัติไม่ได้ในชุดนี้ — {why}", **base,
        )

    unresolved = [r for r in everything if r.budget_category == CATEGORY_UNRESOLVED]
    if unresolved:
        raws = ", ".join(sorted({str(r.budget_category_raw) for r in unresolved}))
        return RollupCheck(
            status=STATUS_HUMAN_REVIEW, computed=None,
            detail=f"มีหมวดที่ยัง resolve ไม่ได้ในชุดนี้ ({raws}) — ห้ามบวกอัตโนมัติ",
            **base,
        )

    if not _units_agree(everything):
        units = ", ".join(sorted({r.declared_unit for r in everything}))
        return RollupCheck(
            status=STATUS_HUMAN_REVIEW, computed=None,
            detail=f"ตัวตั้งอยู่คนละหน่วย ({units}) — ห้ามบวกข้ามหน่วย", **base,
        )

    computed = sum((p.value_decimal for p in parts), Decimal(0))
    diff = declared - computed
    if diff == 0:
        return RollupCheck(
            status=STATUS_OK, computed=computed,
            detail=detail or "ยอดตรงแบบตรงตัว", **base,
        )

    bound = (
        quantum_for(targets[0].declared_unit, targets[0].raw_unit_cell)
        + sum(
            (quantum_for(p.declared_unit, p.raw_unit_cell) for p in parts),
            Decimal(0),
        )
    ) / 2
    if abs(diff) <= bound:
        return RollupCheck(
            status=STATUS_ROUNDING_RESIDUE_CANDIDATE, computed=computed,
            detail=(f"ยอดต่าง {diff} · ขนาดไม่เกินขอบที่การปัดอธิบายได้ "
                    f"({bound} จากตัวตั้ง {len(parts)} รายการ) — "
                    f"**ยังไม่ยืนยันว่าเกิดจากการปัด** รอมนุษย์ตัดสิน"),
            **base,
        )
    return RollupCheck(
        status=STATUS_MISMATCH, computed=computed,
        detail=detail or f"ยอดที่ประกาศไว้ต่างจากผลรวมของตัวตั้ง {diff}",
        **base,
    )


def _dupes(groups: dict[str, list], what: str) -> tuple[str, ...]:
    """รายงานคีย์ที่มี record ซ้ำ — 🔴 ห้าม overwrite เงียบ"""
    return tuple(
        f"{what} {k!r} ซ้ำ {len(v)} รายการ "
        f"({', '.join(str(r.cell_ref) for r in v)})"
        for k, v in sorted(groups.items()) if len(v) > 1
    )


# ------------------------------------------------------------------ กฎแต่ละข้อ
def _category_totals(records, sf, sh) -> list[RollupCheck]:
    # 🔴 BO REVIEW (2 ก.ย.): ตั้งชุดจาก **ฝั่งใดฝั่งหนึ่งที่พบ** แล้วให้ ``_check``
    # ตัดสินว่าอีกฝั่งครบหรือไม่ · เดิม ``continue`` เมื่อขาดฝั่งใดฝั่งหนึ่ง ⇒ หายเงียบ
    #
    # 🔴 BO REVIEW (3 ก.ย.): ตั้งชุดจาก record ที่มีค่า **หรือ** มีเนื้อหาดิบ
    # เซลล์ว่างจริงไม่มียอดให้กระทบ แต่เซลล์ที่มีเนื้อหาแล้วแปลงไม่ได้
    # (เช่น ``"#VALUE!"``) อาจเป็นยอดจริงที่อ่านไม่ออก ⇒ **ห้ามตัดทิ้ง**
    # ให้ ``_check`` เป็นผู้ตัดสินว่าใช้บวกได้หรือไม่
    rows: dict[tuple, dict[str, list[T1BRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in records:
        if (r.row_kind == ROW_KIND_VALUE and r.budget_category is not None
                and (r.value_decimal is not None
                     or _has_raw_content(r.raw_value))):
            rows[(r.sheet_name_actual, r.row_index, r.key)][r.budget_category].append(r)

    out = []
    for (sheet, row, key), cats in rows.items():
        targets = cats.get(CATEGORY_TOTAL, [])
        parts = [r for c, items in cats.items() if c != CATEGORY_TOTAL for r in items]
        problems = _dupes(cats, "หมวด")
        if not targets:
            problems += (f"ไม่พบคอลัมน์ {CATEGORY_TOTAL}",)
        out.append(_check(
            RULE_CATEGORY_TOTAL, f"{sheet} · แถว {row} · {key.row_label_norm}",
            targets, parts, source_file=sf, source_hash=sh, problems=problems,
        ))
    return out


def _sheet_year_groups(records):
    """🔴 **ไม่คัดทิ้ง** record ที่บวกไม่ได้ — ส่งต่อให้ด่านตรวจเห็นเสมอ"""
    groups = defaultdict(list)
    for r in records:
        if r.row_kind == ROW_KIND_VALUE and r.fiscal_year is not None:
            groups[(r.sheet_name_actual, r.fiscal_year)].append(r)
    return groups


def _top_rows(rows) -> dict[str, list[T1BRecord]]:
    top: dict[str, list[T1BRecord]] = defaultdict(list)
    for r in rows:
        if not r.key.hierarchy_path:
            top[r.key.row_label_norm].append(r)
    return top


def _grand_split(records, sf, sh) -> list[RollupCheck]:
    out = []
    for (sheet, year), rows in _sheet_year_groups(records).items():
        top = _top_rows(rows)
        anchors = [LABEL_GRAND_TOTAL, LABEL_SUBTOTAL_IN, LABEL_SUBTOTAL_OUT]
        # 🔴 สิ่งที่บอกว่า "ชีตนี้แยกแหล่งเงิน" คือ **แถวยอดย่อยแหล่งเงิน**
        # ไม่ใช่ ``รวมทั้งสิ้น`` ซึ่งมีอยู่ในชีตแทบทุกชนิดรวมทั้ง ``7.x``
        # ที่ไม่ได้แยกแหล่งเงินเลย — ถ้าใช้ตัวหลังเป็นตัวชี้ จะได้ INCOMPLETE
        # จำนวนมากจากชีตที่กฎนี้ไม่ได้ใช้ตั้งแต่ต้น (ตรวจแฟ้มจริงแล้วได้ 85 รายการ)
        if not any(a in top for a in (LABEL_SUBTOTAL_IN, LABEL_SUBTOTAL_OUT)):
            continue
        targets = top.get(LABEL_GRAND_TOTAL, [])
        parts = [r for k in (LABEL_SUBTOTAL_IN, LABEL_SUBTOTAL_OUT)
                 for r in top.get(k, [])]
        missing = tuple(
            f"ไม่พบแถว {k!r}"
            for k in (LABEL_GRAND_TOTAL, LABEL_SUBTOTAL_IN, LABEL_SUBTOTAL_OUT)
            if k not in top
        )
        out.append(_check(
            RULE_GRAND_SPLIT, f"{sheet} · ปี {year}", targets, parts,
            source_file=sf, source_hash=sh, expected_parts=2,
            problems=missing + _dupes(
                {k: v for k, v in top.items() if k in anchors}, "แถว"
            ),
        ))
    return out


def _funding_line_sums(records, sf, sh) -> list[RollupCheck]:
    out = []
    for (sheet, year), rows in _sheet_year_groups(records).items():
        top = _top_rows(rows)
        for subtotal_label, line_label in FUNDING_PAIRS:
            targets = top.get(subtotal_label, [])
            parts = [
                r for r in rows
                if r.key.hierarchy_path and r.key.row_label_norm == line_label
            ]
            # 🔴 ตั้งชุดเมื่อพบ **ฝั่งใดฝั่งหนึ่ง** — เดิมข้ามเมื่อไม่มียอดย่อย
            # ทำให้ชีตที่มีแถวลูกแต่ยอดย่อยหายไป ไม่มีผลตรวจเลย
            if not targets and not parts:
                continue                   # ชีตนี้ไม่มีโครงสร้างนี้เลย
            problems = _dupes(
                {subtotal_label: targets} if targets else {}, "แถวยอดย่อย"
            )
            if not targets:
                problems += (f"ไม่พบแถว {subtotal_label!r}",)
            out.append(_check(
                RULE_FUNDING_LINE_SUM,
                f"{sheet} · ปี {year} · {subtotal_label}",
                targets, parts, source_file=sf, source_hash=sh,
                problems=problems,
            ))
    return out


def _cross_sheet_grand(records, sf, sh) -> list[RollupCheck]:
    """``รวมทั้งสิ้น`` ของชีตบทบาทหน่วยงานในปีเดียวกันต้องตรงกัน

    🔴 ชีตแผนงาน/โครงการ ``7.x`` **ไม่อยู่ในกฎนี้** เพราะรายงานยอดของแผนตนเอง
    ไม่ใช่ยอดรวมหน่วยงาน — สำรวจแฟ้มจริงแล้วยืนยันว่าเทียบตรง ๆ ไม่ได้
    """
    agency_roles = ("SECTION_04", "SECTION_05")
    grand: dict[int, dict[str, list[T1BRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in records:
        if r.row_kind != ROW_KIND_VALUE or r.fiscal_year is None:
            continue
        if r.key.row_label_norm != LABEL_GRAND_TOTAL or r.key.hierarchy_path:
            continue
        if r.key.sheet_role in agency_roles:
            grand[r.fiscal_year][r.key.sheet_role].append(r)

    out = []
    for year, per_role in sorted(grand.items()):
        if len(per_role) < 2:
            # 🔴 ปีที่มีบทบาทเดียว = **กฎนี้ใช้ไม่ได้** ไม่ใช่ชุดไม่สมบูรณ์
            # สำรวจแฟ้มจริง 6 แฟ้ม (คำสั่ง Bo · 2 ก.ย.): มีทั้งสองบทบาท 8 ปี ·
            # มีเฉพาะบทบาท 4. **4 ปี** · มีเฉพาะบทบาท 5. **22 ปี**
            # ⇒ การมีข้างเดียวเป็นเรื่องปกติของเอกสาร (บทบาท 4. รายงานปีย้อนหลัง
            # บทบาท 5. รายงานปีปัจจุบันและล่วงหน้า) การตั้งเป็น INCOMPLETE
            # จะสร้างรายการปลอม 26 รายการและกลบสัญญาณจริง
            continue
        anchor_role = agency_roles[-1]
        if anchor_role not in per_role:
            anchor_role = sorted(per_role)[0]
        for role in sorted(per_role):
            if role == anchor_role:
                continue
            out.append(_check(
                RULE_CROSS_SHEET_GRAND,
                f"ปี {year} · {role} เทียบ {anchor_role}",
                per_role[anchor_role], per_role[role],
                source_file=sf, source_hash=sh, expected_parts=1,
                problems=_dupes(per_role, "ยอดรวมของบทบาท"),
                detail=f"ยอดรวมหน่วยงานของ {role} ต้องเท่ากับ {anchor_role}",
            ))
    return out


def check_rollups(
    records: list[T1BRecord], *, source_file: str, source_hash: str
) -> RollupResult:
    """กระทบยอดทุกกฎที่พิสูจน์แล้วว่ามีอยู่จริงในแฟ้ม

    รับ record ของ **หนึ่งสมุดงาน** · อ่านอย่างเดียว ไม่แก้ record ใด
    🔴 ``source_file`` และ ``source_hash`` **บังคับ** — ผลที่ย้อนต้นทางไม่ได้
    ใช้เป็นหลักฐานไม่ได้ (BO REVIEW · 2 ก.ย.) · ปกติควรเรียกผ่าน
    :func:`check_rollups_for_envelopes` ซึ่งดึงค่าทั้งสองจาก envelope ให้เอง
    """
    if not source_file or not source_hash:
        raise ValueError(
            "ต้องระบุ source_file และ source_hash — "
            "ผลการกระทบยอดที่ย้อนกลับต้นทางไม่ได้ใช้เป็นหลักฐานไม่ได้"
        )
    result = RollupResult()
    for rule in (_category_totals, _grand_split, _funding_line_sums,
                 _cross_sheet_grand):
        result.checks.extend(rule(records, source_file, source_hash))
    return result


def check_rollups_for_envelopes(envelopes) -> RollupResult:
    """เรียก :func:`check_rollups` จาก envelope — ได้ provenance ต้นทางครบ

    🔴 envelope ทั้งหมดต้องมาจากแฟ้มเดียวกัน · ถ้าปนแฟ้มถือเป็นการใช้ผิดวิธี
    """
    envelopes = list(envelopes)
    if not envelopes:
        return RollupResult()
    # 🔴 ต้องดู **ทั้งชื่อและแฮช** — แฟ้มคนละชื่อที่เนื้อหาเหมือนกันจะมีแฮชเดียวกัน
    # ถ้าดูแฮชอย่างเดียวจะปนได้ แล้วผลทั้งชุดจะระบุชื่อเป็นแฟ้มแรกทั้งหมด
    sources = {(e.source_file.name, e.source_hash) for e in envelopes}
    if len(sources) != 1:
        names = ", ".join(sorted(n for n, _ in sources))
        raise ValueError(
            f"envelope มาจากหลายแฟ้ม ({len(sources)} แฟ้ม: {names}) — "
            "การกระทบยอดต้องทำทีละสมุดงาน"
        )
    first = envelopes[0]
    return check_rollups(
        [e.canonical_record for e in envelopes],
        source_file=first.source_file.name,
        source_hash=first.source_hash,
    )
