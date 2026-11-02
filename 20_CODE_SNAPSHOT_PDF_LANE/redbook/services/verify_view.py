# -*- coding: utf-8 -*-
"""#24 — มุมมอง "ผู้ช่วยตรวจงบ" ของหนึ่งรอบตรวจ T1B (ชั้นแสดงผลเท่านั้น)

หน้าที่ของโมดูลนี้คือ **จัดกลุ่มและเรียบเรียง** ข้อสังเกตที่เครื่องยนต์ออกมาแล้ว
ให้ตอบสามคำถามของคนตรวจงบได้เร็ว — เงินตรงไหม · อะไรเปลี่ยน · A กับ B ต่างตรงไหน

กติกาที่บังคับ

1. 🔴 **ไม่มีกฎตรวจใหม่ ไม่คำนวณผลตรวจใหม่** — ทุกตัวเลขมาจาก ``FindingView``
   ที่เครื่องยนต์ (``redbook/t1b`` · ตรึงไว้) ออกให้แล้ว · โมดูลนี้แค่จัดกลุ่ม
   แปลงหน่วยเพื่ออ่าน (ล้านบาท → บาท · คูณตรง ไม่ปัดเศษ) และไฮไลต์ข้อความที่ต่าง
2. 🔴 **ไม่บวกผลต่างของหลายรายการเป็นยอดรวมเอง** — เอกสารมีรายการซ้อนหลายชั้น
   และหลายปี การบวกเองนับซ้ำได้ ยอดรวมที่แสดงต้องมาจาก *แถวยอดรวมในเอกสาร*
   เท่านั้น (หมวด ``TOTAL`` ที่ป้ายขึ้นต้นด้วย "รวม") ไม่พบ = บอกว่าไม่พบ
3. 🔴 **ห้ามทิ้งเงียบ** — แถวที่เครื่องยนต์อ่าน/เทียบไม่ได้ยังถูกนับเป็น
   "ควรตรวจทาน" เสมอ และทุกกลุ่มย้อนกลับถึงข้อสังเกตทุกใบได้
4. ไม่ใช้คำว่า "ผิด" — ระบบบอกว่า *อะไรเปลี่ยน* และ *หลักฐานอยู่ตรงไหน*
   คำตัดสินเป็นของผู้ตรวจ (ศัพท์ของเครื่องยนต์อยู่หน้า "รายละเอียดการตรวจสอบ")

**หน่วยของการนับ** บนหน้าจอคือ "รายการ" = *แถวหนึ่งแถวในเอกสาร*
(หนึ่งแถวมีได้หลายช่องปี/หมวด ซึ่งเครื่องยนต์ออกเป็นข้อสังเกตแยกใบ)
ตัวเลข "ใบข้อสังเกต" ยังอยู่ครบที่หน้ารายละเอียดการตรวจสอบ
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from ..t1b.categories import (
    CATEGORY_INVESTMENT,
    CATEGORY_OPERATING,
    CATEGORY_OTHER_EXPENDITURE,
    CATEGORY_PERSONNEL,
    CATEGORY_SUBSIDY,
    CATEGORY_TOTAL,
)
from ..t1b.compare import (
    F_AMOUNT_DECREASED,
    F_AMOUNT_INCREASED,
    F_INDICATOR_CHANGED,
    F_PROJECT_ORDINAL_CHANGED,
    F_ROW_ADDED,
    F_ROW_REMOVED,
    F_UNIT_CHANGED,
    F_AMOUNT_UNCHANGED,
    F_INDICATOR_UNCHANGED,
    F_YEAR_ONLY_ONE_SIDE,
)
from . import amounts as _fmt
from .t1b import FindingView, T1BRunView

VIEW_VERSION = "verify-view-0.1.0"

# ---------------------------------------------------------------- ชนิดการเปลี่ยน
K_MONEY = "money"            # จำนวนเงินเปลี่ยน
K_INDICATOR = "indicator"    # ค่าตัวชี้วัดเปลี่ยน
K_ADDED = "added"            # รายการใหม่ (มีเฉพาะฉบับ B)
K_REMOVED = "removed"        # ไม่พบในฉบับ B (มีเฉพาะฉบับ A)
K_TEXT = "text"              # ข้อความในแถวถูกแก้ (ระบบยังจับคู่แถวได้)
K_UNIT = "unit"              # หน่วยนับเปลี่ยน
K_ORDINAL = "ordinal"        # เลขลำดับโครงการเปลี่ยน
K_REVIEW = "review"          # ระบบอ่าน/เทียบเองไม่ได้ — ควรตรวจทาน

#: ลำดับและถ้อยคำบนหน้าจอ — ภาษาคนตรวจงบ ไม่ใช่รหัสของเครื่องยนต์
KIND_LABELS = {
    K_MONEY: "จำนวนเงินเปลี่ยน",
    K_INDICATOR: "ค่าตัวชี้วัดเปลี่ยน",
    K_ADDED: "รายการใหม่",
    K_REMOVED: "ไม่พบในฉบับ B",
    K_TEXT: "ข้อความเปลี่ยน",
    K_UNIT: "หน่วยนับเปลี่ยน",
    K_ORDINAL: "เลขลำดับโครงการเปลี่ยน",
    K_REVIEW: "ควรตรวจทาน",
}
#: ชนิดที่นับเป็น "ความต่างระหว่างเอกสาร" (ส่วนที่ 3) — ``K_REVIEW`` แยกไว้ต่างหาก
#: เพราะไม่ได้แปลว่าเอกสารต่าง แปลว่า *ระบบยังบอกไม่ได้*
CHANGE_KINDS = (K_MONEY, K_INDICATOR, K_ADDED, K_REMOVED, K_TEXT, K_UNIT, K_ORDINAL)
#: ชนิดที่อยู่ในส่วน "ตัวชี้วัดและรายการ" (ส่วนที่ 2) — เงินมีส่วนของตัวเองแล้ว
OBSERVATION_KINDS = (K_INDICATOR, K_ADDED, K_REMOVED, K_TEXT, K_UNIT, K_ORDINAL)

_TYPE_TO_KIND = {
    F_AMOUNT_INCREASED: K_MONEY,
    F_AMOUNT_DECREASED: K_MONEY,
    F_INDICATOR_CHANGED: K_INDICATOR,
    F_ROW_ADDED: K_ADDED,
    F_ROW_REMOVED: K_REMOVED,
    F_UNIT_CHANGED: K_UNIT,
    F_PROJECT_ORDINAL_CHANGED: K_ORDINAL,
}
#: ชนิดที่แปลว่า "ค่าเท่าเดิม" — ไม่ใช่ความต่าง และไม่ใช่สิ่งที่ต้องตรวจทาน
_UNCHANGED_TYPES = frozenset({F_AMOUNT_UNCHANGED, F_INDICATOR_UNCHANGED})

CATEGORY_TH = {
    CATEGORY_PERSONNEL: "งบบุคลากร",
    CATEGORY_OPERATING: "งบดำเนินงาน",
    CATEGORY_INVESTMENT: "งบลงทุน",
    CATEGORY_SUBSIDY: "งบเงินอุดหนุน",
    CATEGORY_OTHER_EXPENDITURE: "งบรายจ่ายอื่น",
    CATEGORY_TOTAL: "รวม",
}

#: หน่วยเงินที่แปลงเป็นบาทได้ด้วยการคูณตรง — หน่วยอื่นแสดงตามที่เอกสารพิมพ์
_BAHT_SCALE = {"บาท": Decimal(1), "ล้านบาท": Decimal(1_000_000)}


# ══════════════════════════════════════════════════════════════════════════════
#  ตัวเลข
# ══════════════════════════════════════════════════════════════════════════════

def parse_amount(text: str) -> Decimal | None:
    """ตัวเลขที่ ``FindingView`` จัดรูปแบบไว้ (``"12,000,000.00"``) → ``Decimal``"""
    if not text:
        return None
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def unit_scale(unit: str) -> Decimal | None:
    return _BAHT_SCALE.get((unit or "").replace(" ", ""))


def fmt_number(value: Decimal | None) -> str:
    """คั่นหลักพัน · **ไม่ปัดเศษ** — ตัดเฉพาะศูนย์ท้ายทศนิยมที่ไม่มีความหมาย"""
    if value is None:
        return "—"
    v = value.normalize() if value != value.to_integral_value() else value.quantize(Decimal(1))
    s = format(abs(v), ",f")
    return ("-" if v < 0 else "") + s


def fmt_baht(value: Decimal | None) -> str:
    """ค่าที่ **แปลงเป็นบาทเพื่อสรุป** — ใช้กับยอดสรุปที่ติดป้ายเท่านั้น"""
    return "—" if value is None else _fmt.format_amount(value, _fmt.UNIT_BAHT)


def amt(value, unit) -> str:
    """ค่าตามหน่วยของเอกสาร — มาตรฐานเดียวกับทุกหน้า (ล้านบาท = 4 ตำแหน่งเสมอ)"""
    return _fmt.format_amount(value, unit)


def number_variants(value, unit) -> tuple[str, ...]:
    """รูปแบบที่ตัวเลขนี้อาจถูกพิมพ์ใน PDF — ตามหน่วยเอกสาร · ไม่มีจุลภาค · แปลงบาท↔ล้านบาท"""
    d = _fmt.to_decimal(value)
    if d is None:
        return ()
    out = {_fmt.format_number(d, unit), _fmt.format_number(d, ""), format(d.normalize(), "f")}
    u = _fmt.norm_unit(unit)
    if u == _fmt.UNIT_BAHT:
        out.add(_fmt.format_number(d / 1_000_000, _fmt.UNIT_MILLION))
    elif u == _fmt.UNIT_MILLION:
        out.add(_fmt.format_number(d * 1_000_000, _fmt.UNIT_BAHT))
    return tuple(sorted(x for x in out if x))


def norm_unit_is_baht(unit) -> bool:
    return _fmt.norm_unit(unit) == _fmt.UNIT_BAHT


@dataclass(frozen=True)
class Change:
    period: str
    a: str
    b: str
    unit: str
    delta: str
    #: ผลต่างตัวเลขจริง (บาท ถ้าแปลงได้) — ใช้เรียง/เทียบ ห้ามใช้สตริงด้านบน
    delta_value: Decimal | None


def direction_word(diff: Decimal | None) -> str:
    if diff is None:
        return ""
    if diff > 0:
        return "เพิ่มขึ้น"
    if diff < 0:
        return "ลดลง"
    return "เท่าเดิม"


# ══════════════════════════════════════════════════════════════════════════════
#  ไฮไลต์ข้อความที่ต่าง
# ══════════════════════════════════════════════════════════════════════════════

#: ตัวเลข (รวมเลขไทย ทศนิยม คั่นหลัก และ %) เป็นหนึ่งโทเค็น · คำละตินเป็นหนึ่งโทเค็น
#: ช่องว่างเป็นหนึ่งโทเค็น · อักษรไทยแยกทีละตัว (ไม่มีช่องว่างระหว่างคำให้ตัด)
_TOKEN = re.compile(r"[0-9๐-๙]+(?:[.,][0-9๐-๙]+)*%?|[A-Za-z]+|\s+|.", re.S)


@dataclass(frozen=True)
class Segment:
    text: str
    changed: bool


@dataclass(frozen=True)
class TextDiff:
    a: tuple[Segment, ...]
    b: tuple[Segment, ...]
    #: สรุปสั้น ๆ ของจุดที่เปลี่ยน — ``(เดิม, ใหม่)`` ค่าว่างฝั่งใด = เพิ่ม/ตัดออก
    changes: tuple[tuple[str, str], ...]

    @property
    def changed(self) -> bool:
        return bool(self.changes)


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def text_differs(a: str, b: str) -> bool:
    """ข้อความต่างกันจริงหรือไม่ — ต่างแค่ช่องว่าง/การขึ้นบรรทัด ไม่นับ"""
    return _squash(a) != _squash(b)


def diff_text(a: str, b: str) -> TextDiff:
    """ไฮไลต์เฉพาะส่วนที่ต่าง เช่น ``80%`` → ``85%`` หรือ ``และ AI`` ที่เพิ่มเข้ามา"""
    a, b = a or "", b or ""
    ta, tb = _TOKEN.findall(a), _TOKEN.findall(b)
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    seg_a: list[Segment] = []
    seg_b: list[Segment] = []
    changes: list[tuple[str, str]] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        xa, xb = "".join(ta[i1:i2]), "".join(tb[j1:j2])
        if op == "equal":
            seg_a.append(Segment(xa, False))
            seg_b.append(Segment(xb, False))
            continue
        # ต่างแค่ช่องว่าง = ไม่ไฮไลต์ (ไม่ใช่การแก้ข้อความที่ผู้ตรวจต้องสนใจ)
        real = _squash(xa) != _squash(xb)
        if xa:
            seg_a.append(Segment(xa, real))
        if xb:
            seg_b.append(Segment(xb, real))
        if real:
            changes.append((xa.strip(), xb.strip()))
    return TextDiff(_merge(seg_a), _merge(seg_b), tuple(changes))


def _merge(segs: list[Segment]) -> tuple[Segment, ...]:
    out: list[Segment] = []
    for s in segs:
        if out and out[-1].changed == s.changed:
            out[-1] = Segment(out[-1].text + s.text, s.changed)
        else:
            out.append(s)
    return tuple(out)


# ══════════════════════════════════════════════════════════════════════════════
#  จัดกลุ่มข้อสังเกตเป็น "รายการ" (หนึ่งแถวของเอกสาร)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Cell:
    """หนึ่งช่องที่นำมาเทียบในแถว (หนึ่งปี หรือหนึ่งหมวดงบรายจ่าย)"""

    f: FindingView
    period: str
    a: Decimal | None
    b: Decimal | None
    diff: Decimal | None
    #: ค่าเป็นบาท (เฉพาะหน่วยเงินที่แปลงได้) — ``None`` = แปลงไม่ได้/ไม่ใช่เงิน
    a_baht: Decimal | None
    b_baht: Decimal | None
    diff_baht: Decimal | None
    kind: str          # K_* หรือ "" = เท่าเดิม
    #: ปีนี้มีเฉพาะฉบับเดียว (นอกช่วงปีที่เทียบได้) — ``"A"``/``"B"`` · ว่าง = อยู่ในช่วงเทียบ
    only_side: str = ""

    @property
    def changed(self) -> bool:
        return bool(self.kind)


@dataclass
class Item:
    key: tuple
    findings: list[FindingView] = field(default_factory=list)
    cells: list[Cell] = field(default_factory=list)
    kinds: set[str] = field(default_factory=set)
    review_reasons: list[str] = field(default_factory=list)
    #: หัวข้อแม่ในเอกสาร (เช่น กิจกรรม/ผลผลิต) — ว่าง = เอกสารไม่มีหรือหาไม่พบ
    heading: str = ""
    #: ชื่อที่ตั้งให้ข้อสังเกตระดับขอบเขต (ไม่ผูกกับแถว) เช่น "ปี 2568 มีเฉพาะฉบับ A"
    override_title: str = ""

    # ------------------------------------------------------------- บริบทในโครงสร้างงบ
    @property
    def group_crumbs(self) -> tuple[str, ...]:
        """ระดับแผนงาน/โครงการ (จากเครื่องยนต์) — ไม่มีหัวเรื่องชีต = ใช้ชื่อชีต"""
        f = self.first
        loc = self.b_loc or self.a_loc
        top = [x for x in (f.parent_plan, f.section_title) if x]
        if not top and loc is not None:
            top = [f"ชีต {loc.sheet}"]
        return tuple(top)

    @property
    def crumbs(self) -> tuple[str, ...]:
        """เส้นทางเต็ม แผนงาน › โครงการ › กิจกรรม › รายการ — เฉพาะระดับที่มีจริง"""
        return (*self.group_crumbs, *((self.heading,) if self.heading else ()), self.title)

    #: ลำดับที่เครื่องยนต์พบรายการนี้ครั้งแรก (ตามลำดับชีตในเอกสาร)
    order: int = 0

    @property
    def doc_order(self) -> tuple:
        """เรียงตามลำดับในเอกสาร: ชีตตามที่พบก่อน แล้วตามเลขแถว"""
        loc = self.b_loc or self.a_loc
        return (loc.row if loc else 0, self.order)

    @property
    def rows_text(self) -> str:
        """ตำแหน่งแบบสั้น ``แถว 7 ↔ แถว 7`` (ชื่อชีต/เซลล์อยู่ในรายละเอียดทางเทคนิค)"""
        a, b = self.a_loc, self.b_loc
        if a and b:
            return f"แถว {a.row} ↔ แถว {b.row}"
        if a:
            return f"A แถว {a.row}"
        if b:
            return f"B แถว {b.row}"
        return ""

    # ------------------------------------------------------------- ตัวตนของแถว
    @property
    def first(self) -> FindingView:
        return self.findings[0]

    @property
    def id(self) -> str:
        """ลิงก์ของรายการ = ``finding_id`` ใบแรก (คงที่ตามที่เครื่องยนต์รับประกัน)"""
        return self.first.finding_id

    @property
    def a_loc(self):
        return next((f.baseline for f in self.findings if f.baseline), None)

    @property
    def b_loc(self):
        return next((f.current for f in self.findings if f.current), None)

    @property
    def label_a(self) -> str:
        loc = self.a_loc
        return (loc.label if loc and loc.label else "") or ("" if loc is None else self.first.row_label)

    @property
    def label_b(self) -> str:
        loc = self.b_loc
        return (loc.label if loc and loc.label else "") or ("" if loc is None else self.first.row_label)

    @property
    def title(self) -> str:
        if self.override_title:
            return self.override_title
        return (self.label_b or self.label_a or self.first.row_label or "(แถวไม่มีชื่อ)").strip()

    @property
    def context(self) -> str:
        f = self.first
        parts = [f.parent_plan, f.section_title]
        return " · ".join(p for p in parts if p)

    @property
    def unit(self) -> str:
        return self.first.declared_unit

    @property
    def label_diff(self) -> TextDiff:
        return diff_text(self.label_a, self.label_b)

    # ------------------------------------------------------------- สถานะ
    @property
    def changed(self) -> bool:
        return bool(self.kinds & set(CHANGE_KINDS))

    @property
    def needs_review(self) -> bool:
        return K_REVIEW in self.kinds

    @property
    def is_money(self) -> bool:
        return any(c.a_baht is not None or c.b_baht is not None for c in self.cells)

    @property
    def is_grand_total(self) -> bool:
        """แถวยอดรวมทั้งเอกสาร — มีช่องหมวด ``TOTAL`` และป้ายขึ้นต้นด้วย "รวม" """
        return (any(c.f.budget_category == CATEGORY_TOTAL for c in self.cells)
                and _squash(self.first.row_label).startswith("รวม"))

    @property
    def total_cell(self) -> Cell | None:
        return next((c for c in self.cells if c.f.budget_category == CATEGORY_TOTAL), None)

    @property
    def money_cells(self) -> list[Cell]:
        return [c for c in self.cells if c.kind == K_MONEY]

    @property
    def max_abs_diff_baht(self) -> Decimal:
        vals = [abs(c.diff_baht) for c in self.money_cells if c.diff_baht is not None]
        return max(vals) if vals else Decimal(0)

    @property
    def kind_labels(self) -> list[str]:
        return [KIND_LABELS[k] for k in KIND_LABELS if k in self.kinds]

    def _amounts(self, side: str) -> str:
        """ยอดของฝั่งที่มีรายการ เช่น `` (ปี 2570: 1,200,000 บาท)`` — หน่วยตามเอกสาร · ไม่ใช่เงิน = ว่าง"""
        vals = [(c.period, c.a if side == "a" else c.b) for c in self.cells
                if (c.a_baht if side == "a" else c.b_baht) is not None]
        if not vals:
            return ""
        return " (" + " · ".join(f"{p + ': ' if p else ''}{amt(v, self.unit)}" for p, v in vals) + ")"

    @property
    def changes(self) -> list["Change"]:
        """ช่องที่ค่าเปลี่ยน — ค่าตามหน่วยเอกสาร (มาตรฐานเดียวทั้งระบบ) + ผลต่างที่แปลงเป็นบาทเพื่อสรุป"""
        out = []
        for c in self.cells:
            if c.kind not in (K_MONEY, K_INDICATOR) or c.a is None or c.b is None:
                continue
            delta = ""
            if c.diff_baht is not None:
                delta = f"{direction_word(c.diff_baht)} {fmt_number(abs(c.diff_baht))} บาท"
            elif c.diff is not None:
                delta = f"{direction_word(c.diff)} {_fmt.format_number(abs(c.diff), self.unit)}"
            out.append(Change(c.period, _fmt.format_number(c.a, self.unit),
                              _fmt.format_number(c.b, self.unit), self.unit, delta,
                              c.diff_baht if c.diff_baht is not None else c.diff))
        return out

    @property
    def summary(self) -> str:
        """หนึ่งประโยคที่บอกว่าแถวนี้เปลี่ยนอย่างไร — ใช้ในรายการและหัวหน้าเทียบ"""
        if K_REMOVED in self.kinds:
            return "มีในฉบับ A แต่ไม่พบในฉบับ B" + self._amounts("a")
        if K_ADDED in self.kinds:
            return "ไม่มีในฉบับ A แต่พบในฉบับ B" + self._amounts("b")
        bits = []
        for ch in self.changes:
            if norm_unit_is_baht(self.unit) and ch.delta:
                bits.append(f"{ch.period + ' ' if ch.period else ''}{ch.delta}")
            else:
                bits.append(f"{ch.period + ' ' if ch.period else ''}{ch.a} → {ch.b}"
                            f"{(' ' + ch.unit) if ch.unit else ''}"
                            f"{(' (' + ch.delta + ')') if ch.delta and ch.delta.endswith('บาท') else ''}")
        if K_TEXT in self.kinds:
            bits.append("ข้อความในแถวถูกแก้")
        if K_UNIT in self.kinds:
            bits.append("หน่วยนับเปลี่ยน")
        if K_ORDINAL in self.kinds:
            bits.append("เลขลำดับโครงการเปลี่ยน")
        if not bits and self.needs_review:
            unread = item_unread(self)
            if unread:
                return "ยังยืนยันไม่ได้: " + unread[0].missing[0]
            return self.review_reasons[0] if self.review_reasons else "ระบบเทียบเองไม่ได้"
        return " · ".join(bits) if bits else "เท่าเดิม"


def _period_of(f: FindingView) -> str:
    if f.fiscal_year is not None:
        return f"ปี {f.fiscal_year}"
    if f.budget_category:
        return CATEGORY_TH.get(f.budget_category, f.budget_category)
    return ""


def _cell(f: FindingView) -> Cell:
    a, b = parse_amount(f.baseline_value), parse_amount(f.current_value)
    diff = parse_amount(f.difference)
    if diff is None and a is not None and b is not None:
        diff = b - a
    scale = unit_scale(f.declared_unit)
    is_money_type = f.finding_type in (F_AMOUNT_INCREASED, F_AMOUNT_DECREASED,
                                       F_AMOUNT_UNCHANGED, F_ROW_ADDED, F_ROW_REMOVED)
    if scale is not None and is_money_type:
        a_b = a * scale if a is not None else None
        b_b = b * scale if b is not None else None
        d_b = diff * scale if diff is not None else None
    else:
        a_b = b_b = d_b = None
    return Cell(f=f, period=_period_of(f), a=a, b=b, diff=diff,
                a_baht=a_b, b_baht=b_b, diff_baht=d_b,
                kind=_TYPE_TO_KIND.get(f.finding_type, "")
                if f.finding_type not in _UNCHANGED_TYPES else "")


def _row_key(f: FindingView) -> tuple:
    a, b = f.baseline, f.current
    if a is None and b is None:
        return ("none", f.finding_id)
    return (a.sheet if a else None, a.row if a else None,
            b.sheet if b else None, b.row if b else None)


def group_items(view: T1BRunView) -> list[Item]:
    """จัดข้อสังเกตทุกใบเป็นรายการตามแถวจริงของเอกสาร — **ทุกใบอยู่ในรายการเดียวเสมอ**"""
    items: dict[tuple, Item] = {}
    for f in view.findings:
        key = _row_key(f)
        it = items.get(key)
        if it is None:
            it = items[key] = Item(key=key, order=len(items))
        it.findings.append(f)
        c = _cell(f)
        it.cells.append(c)
        if c.kind:
            it.kinds.add(c.kind)
        elif f.finding_type not in _UNCHANGED_TYPES:
            it.kinds.add(K_REVIEW)
            if f.type_label not in it.review_reasons:
                it.review_reasons.append(f.type_label)
        for label in f.flag_labels:
            it.kinds.add(K_REVIEW)
            if label not in it.review_reasons:
                it.review_reasons.append(label)
    _fold_one_sided_years(items)
    for it in items.values():
        if it.a_loc is not None and it.b_loc is not None and text_differs(it.label_a, it.label_b):
            it.kinds.add(K_TEXT)
    out = list(items.values())
    _link_headings(out)
    return out


def one_sided_years(view_or_findings) -> dict[int, str]:
    """ปีที่มีเฉพาะฉบับเดียว ``{ปี: "A"|"B"}`` — จากข้อสังเกต ``YEAR_PRESENT_ON_ONE_SIDE_ONLY`` ของเครื่องยนต์

    เทียบข้ามปี (เล่ม 2569 มีคอลัมน์ 2568|2569 · เล่ม 2570 มี 2569|2570) ⇒ ปีที่เทียบได้มีแค่ปีที่ซ้อนกัน
    """
    findings = getattr(view_or_findings, "findings", view_or_findings)
    out: dict[int, str] = {}
    for f in findings:
        if f.finding_type == F_YEAR_ONLY_ONE_SIDE and f.fiscal_year is not None:
            out[f.fiscal_year] = "A" if "ฉบับตั้งต้น" in (f.detail or "") else "B"
    return out


def _fold_one_sided_years(items: dict) -> None:
    """ช่องของปีที่มีเฉพาะฉบับเดียว **ไม่ใช่รายการหาย/รายการใหม่** — ย้ายไปอยู่กับแถวจริงของรายการนั้น

    เครื่องยนต์ออก ``ROW_REMOVED``/``ROW_ADDED`` ต่อช่อง ⇒ ถ้าไม่จัดใหม่ ทุกแถวของเล่มข้ามปีจะดูเหมือน
    "หาย" (ปี 2568) และ "ใหม่" (ปี 2570) ทั้งที่แถวยังอยู่ครบ · 🔴 ไม่แก้ข้อสังเกต แค่จัดกลุ่มบนหน้าจอ
    ช่องที่ย้ายแล้วติดป้าย ``only_side`` และไม่นับเป็นความต่าง (ยังต้องให้คนยืนยันเหมือนทุกใบ)
    """
    all_f = [f for it in items.values() for f in it.findings]
    years = one_sided_years(all_f)
    if not years:
        return
    by_loc: dict[tuple, Item] = {}
    for it in items.values():
        if it.a_loc is not None and it.b_loc is not None:
            by_loc[("A", it.a_loc.sheet, it.a_loc.row)] = it
            by_loc[("B", it.b_loc.sheet, it.b_loc.row)] = it
    for key in list(items):
        it = items[key]
        movable = [c for c in it.cells if c.f.fiscal_year in years
                   and c.f.finding_type in (F_ROW_REMOVED, F_ROW_ADDED)
                   and years[c.f.fiscal_year] == ("A" if c.f.finding_type == F_ROW_REMOVED else "B")]
        if not movable:
            continue
        side = years[movable[0].f.fiscal_year]
        loc = it.a_loc if side == "A" else it.b_loc
        target = by_loc.get((side, loc.sheet, loc.row)) if loc is not None else None
        for c in movable:
            moved = Cell(**{**c.__dict__, "kind": "", "only_side": side,
                            "period": f"{c.period} · มีเฉพาะฉบับ {side}"})
            if target is not None and target is not it:
                target.findings.append(c.f)
                target.cells.append(moved)
                it.findings.remove(c.f)
                it.cells.remove(c)
            else:
                it.cells[it.cells.index(c)] = moved
        if target is not None and target is not it and not it.findings:
            del items[key]
            continue
        # คำนวณชนิดของรายการใหม่จากช่องที่เหลือ
        it.kinds = {c.kind for c in it.cells if c.kind} | ({K_REVIEW} if it.review_reasons else set())
        if not it.kinds and all(c.only_side for c in it.cells):
            it.kinds = {K_REVIEW}
            it.review_reasons.append("มีเฉพาะปีที่อยู่นอกช่วงเทียบ — เทียบกับอีกฉบับไม่ได้")
    for it in items.values():
        if it.a_loc is None and it.b_loc is None and it.first.finding_type == F_YEAR_ONLY_ONE_SIDE:
            y, sd = it.first.fiscal_year, years.get(it.first.fiscal_year, "")
            it.override_title = f"ปี {y} มีเฉพาะฉบับ {sd} — อยู่นอกช่วงปีที่เทียบได้"
            it.review_reasons = ["ปีนี้มีในฉบับเดียว จึงเทียบกับอีกฉบับไม่ได้ (ไม่ใช่รายการหาย)"]


def year_scope(view) -> str:
    """ข้อความบอกช่วงปีที่เทียบได้ — ว่าง = ทุกปีมีในทั้งสองฉบับ"""
    years = one_sided_years(view)
    if not years:
        return ""
    a = sorted(y for y, s in years.items() if s == "A")
    b = sorted(y for y, s in years.items() if s == "B")
    bits = []
    if a:
        bits.append("ปี " + ", ".join(map(str, a)) + " มีเฉพาะฉบับ A")
    if b:
        bits.append("ปี " + ", ".join(map(str, b)) + " มีเฉพาะฉบับ B")
    return "เทียบได้เฉพาะปีที่มีในทั้งสองฉบับ · " + " · ".join(bits)


#: เลขข้อนำหน้าป้าย เช่น ``1.`` · ``1.2`` · ``2.1.3``
_LEAD_NO = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)*)\.?\s")


def _lead_no(label: str) -> str:
    m = _LEAD_NO.match(label or "")
    return m.group(1) if m else ""


def _link_headings(items: list["Item"]) -> None:
    """หัวข้อแม่ของแต่ละแถว = แถว **ในชีตเดียวกันของเอกสารเดียวกัน** ที่เลขข้อเป็นส่วนนำของเลขข้อแถวนี้

    (``1.2 ค่าสาธารณูปโภค`` → ``1. งบดำเนินงาน``) — อ่านจากเลขข้อที่พิมพ์ในเอกสาร
    เหมือนที่ชั้นลำดับชั้นของเครื่องยนต์ทำ · 🔴 ไม่พบแถวแม่ในเอกสาร = ไม่ใส่ (ห้ามสร้างเอง)
    """
    index: dict[tuple, str] = {}
    for it in items:
        loc = it.b_loc or it.a_loc
        no = _lead_no(it.title)
        if loc is not None and no:
            index.setdefault((loc.sheet, no), it.title)
    for it in items:
        loc = it.b_loc or it.a_loc
        no = _lead_no(it.title)
        if loc is None or "." not in no:
            continue
        parent = no.rsplit(".", 1)[0]
        it.heading = index.get((loc.sheet, parent), "")


# ══════════════════════════════════════════════════════════════════════════════
#  ภาพรวม 3 เรื่อง
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MoneyOverview:
    #: ``same`` ตรงกัน · ``diff`` พบความแตกต่าง · ``review`` ควรตรวจทาน · ``blocked`` ยังเทียบไม่ได้
    state: str
    headline: str
    lines: tuple[str, ...]
    total: Item | None
    total_cell: Cell | None
    totals_found: int
    changed: tuple[Item, ...]          # รายการ (ไม่รวมแถวยอดรวม) ที่จำนวนเงินเปลี่ยน
    added: tuple[Item, ...]            # รายการใหม่ที่มีจำนวนเงิน
    removed: tuple[Item, ...]          # รายการที่หายไปที่มีจำนวนเงิน
    review: tuple[Item, ...]           # รายการเงินที่ระบบเทียบเองไม่ได้


@dataclass(frozen=True)
class Observation:
    kind: str
    label: str
    count: int
    sentence: str


@dataclass(frozen=True)
class Overview:
    blocked: bool
    money: MoneyOverview
    observations: tuple[Observation, ...]
    observation_total: int
    differences: int
    review_count: int
    items: tuple[Item, ...]

    def by_id(self, item_id: str) -> Item | None:
        for it in self.items:
            if it.id == item_id or any(f.finding_id == item_id for f in it.findings):
                return it
        return None


def _money(items: list[Item], blocked: bool) -> MoneyOverview:
    totals = [it for it in items if it.is_grand_total]
    rest = [it for it in items if not it.is_grand_total]
    changed = tuple(sorted((it for it in rest if K_MONEY in it.kinds),
                           key=lambda it: it.max_abs_diff_baht, reverse=True))
    added = tuple(it for it in rest if K_ADDED in it.kinds and it.is_money)
    removed = tuple(it for it in rest if K_REMOVED in it.kinds and it.is_money)
    # แถวเงินที่ระบบเทียบเองไม่ได้ = มีหลักฐานทั้งสองฉบับ (แถวที่อ่านไม่ได้ฝั่งเดียว
    # เช่น หัวตาราง "หน่วย : บาท" ไม่ใช่ยอดเงิน — ไปอยู่ในกอง "ควรตรวจทาน" รวม)
    review = tuple(it for it in items if it.needs_review and K_MONEY not in it.kinds
                   and it.a_loc is not None and it.b_loc is not None
                   and (it.is_money or unit_scale(it.unit) is not None))
    total = totals[0] if len(totals) == 1 else None
    tc = total.total_cell if total else None
    lines: list[str] = []
    n = len(changed)
    if n:
        lines.append(f"พบ {n} รายการที่ยอดไม่เท่ากัน")
    if added or removed:
        bits = []
        if added:
            bits.append(f"รายการใหม่ {len(added)}")
        if removed:
            bits.append(f"ไม่พบในฉบับ B {len(removed)}")
        lines.append("รายการที่มีจำนวนเงิน: " + " · ".join(bits) + " รายการ")
    if review:
        lines.append(f"ควรตรวจทาน {len(review)} รายการ (ระบบเทียบจำนวนเงินเองไม่ได้)")

    if blocked:
        return MoneyOverview("blocked", "ยังเทียบยอดเงินไม่ได้",
                             ("ยังยืนยันไม่ได้ว่าสองฉบับเป็นหน่วยงานเดียวกัน — ดูที่มาเอกสาร",),
                             total, tc, len(totals), changed, added, removed, review)
    if tc is not None and tc.diff_baht is not None:
        if tc.diff_baht == 0:
            head = "ยอดรวมตรงกัน"
            state = "same" if not (n or added or removed) else "diff"
            if state == "diff":
                lines.insert(0, "ยอดรวมเท่ากัน แต่ยอดภายในมีการเปลี่ยน")
        elif (tc.f.baseline_category_table_year and tc.f.current_category_table_year
              and tc.f.baseline_category_table_year != tc.f.current_category_table_year):
            # เทียบข้ามปี — ตารางสรุปของสองเล่มเป็นคนละปีงบ ⇒ เป็นการเปลี่ยนแปลงปีต่อปี ไม่ใช่ยอดคลาดเคลื่อน
            ya, yb = tc.f.baseline_category_table_year, tc.f.current_category_table_year
            head = (f"ยอดรวมปี {yb} {direction_word(tc.diff_baht)}จากปี {ya} "
                    f"{fmt_number(abs(tc.diff_baht))} บาท")
            state = "diff"
            lines.insert(0, "ตารางสรุปของสองเล่มเป็นคนละปีงบประมาณ — เป็นการเปลี่ยนแปลงปีต่อปี "
                            "ไม่ใช่ยอดที่คลาดเคลื่อน")
        else:
            head = f"พบยอดรวมต่าง {fmt_number(abs(tc.diff_baht))} บาท"
            state = "diff"
            unit = total.unit
            lines.insert(0, f"ยอดรวมทั้งสิ้น{direction_word(tc.diff_baht)}จาก "
                            f"{_fmt.format_number(tc.a, unit)} เป็น {amt(tc.b, unit)}")
        return MoneyOverview(state, head, tuple(lines), total, tc, len(totals),
                             changed, added, removed, review)
    # ไม่มีแถวยอดรวมเดียวที่เทียบได้ — ไม่บวกเอง บอกตรง ๆ
    if total is not None and tc is not None:
        note = "แถวยอดรวมทั้งสิ้นเทียบเองไม่ได้ — ควรตรวจทาน"
    elif len(totals) > 1:
        note = f"พบแถวยอดรวม {len(totals)} แถว ระบบไม่เลือกแถวใดแถวหนึ่งแทนผู้ตรวจ"
    else:
        note = "ไม่พบแถวยอดรวมทั้งสิ้นที่เทียบได้ทั้งสองฉบับ"
    if not (n or added or removed or review):
        head, state = "ไม่พบรายการที่ยอดเปลี่ยน", "same"
    elif n or added or removed:
        head, state = f"พบ {n + len(added) + len(removed)} รายการที่ยอดไม่เท่ากัน", "diff"
    else:
        head, state = "ควรตรวจทานยอดเงิน", "review"
    return MoneyOverview(state, head, (note, *lines), total, tc, len(totals),
                         changed, added, removed, review)


_SENTENCE = {
    K_INDICATOR: "ค่าตัวชี้วัดเปลี่ยน {n} รายการ",
    K_ADDED: "พบรายการใหม่ในฉบับ B {n} รายการ",
    K_REMOVED: "พบรายการที่ไม่ปรากฏในฉบับ B {n} รายการ",
    K_TEXT: "พบข้อความที่มีการแก้ไข {n} จุด",
    K_UNIT: "หน่วยนับเปลี่ยน {n} รายการ",
    K_ORDINAL: "เลขลำดับโครงการเปลี่ยน {n} รายการ",
}


def build_overview(view: T1BRunView) -> Overview:
    items = group_items(view)
    blocked = view.summary.identity_gate_blocked
    obs = []
    for k in OBSERVATION_KINDS:
        n = sum(1 for it in items if k in it.kinds)
        if n:
            obs.append(Observation(k, KIND_LABELS[k], n, _SENTENCE[k].format(n=n)))
    return Overview(
        blocked=blocked,
        money=_money(items, blocked),
        observations=tuple(obs),
        observation_total=sum(1 for it in items if it.kinds & set(OBSERVATION_KINDS)),
        differences=sum(1 for it in items if it.changed),
        review_count=sum(1 for it in items if it.needs_review and not it.changed),
        items=tuple(items),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  รายการตามมุมมอง (เงิน · ข้อสังเกต · ความต่างทั้งหมด)
# ══════════════════════════════════════════════════════════════════════════════

LENSES = {
    "money": "เงิน",
    "changes": "ตัวชี้วัดและรายการ",
    "differences": "ความต่างระหว่างเอกสาร",
}


def items_for(ov: Overview, lens: str, kind: str = "") -> list[Item]:
    """รายการของแต่ละมุมมอง · ``kind`` กรองเพิ่ม (เช่น ``added``) — ไม่รู้จัก = ไม่กรอง"""
    if lens == "money":
        out = [*ov.money.changed, *ov.money.removed, *ov.money.added, *ov.money.review]
    elif lens == "changes":
        out = [it for it in ov.items if it.kinds & set(OBSERVATION_KINDS)]
    elif lens == "review":
        out = [it for it in ov.items if it.needs_review]
    else:
        out = [it for it in ov.items if it.changed]
    if kind in KIND_LABELS:
        out = [it for it in out if kind in it.kinds]
    return out


def kind_counts(items: list[Item]) -> list[tuple[str, str, int]]:
    return [(k, KIND_LABELS[k], n) for k in KIND_LABELS
            if (n := sum(1 for it in items if k in it.kinds))]


# ══════════════════════════════════════════════════════════════════════════════
#  Source Verification — A และ B คือเอกสารที่ถูกต้องหรือไม่
# ══════════════════════════════════════════════════════════════════════════════

CHECK_OK = "ok"          # ผ่าน — มีหลักฐานในระบบ
CHECK_WARN = "warn"      # ควรตรวจทาน — มีข้อมูลแต่ไม่สอดคล้องกับที่คาด
CHECK_FAIL = "fail"      # ไม่ผ่าน — ระบบหยุดการเทียบอัตโนมัติ
CHECK_MANUAL = "manual"  # ระบบตรวจเองไม่ได้ — ผู้ตรวจต้องยืนยัน

CHECK_LABELS = {
    CHECK_OK: "ผ่าน",
    CHECK_WARN: "ควรตรวจทาน",
    CHECK_FAIL: "ไม่ผ่าน",
    CHECK_MANUAL: "ให้ผู้ตรวจยืนยัน",
}


@dataclass(frozen=True)
class SourceCheck:
    name: str
    state: str
    text: str

    @property
    def state_label(self) -> str:
        return CHECK_LABELS[self.state]


@dataclass(frozen=True)
class SourceSide:
    side: str
    #: เอกสารอ้างอิงจากคลังเล่ม (ทะเบียนแหล่งทางการ) — ไม่มี = งานนี้ไม่ได้เลือกจากคลัง
    title: str = ""
    fiscal_year: int | None = None
    stage: str = ""
    ministries: tuple[str, ...] = ()
    source_url: str = ""
    source_page: str = ""
    retrieved_at: str = ""
    linked_at: str = ""
    book_id: str = ""
    synthetic: bool = False
    #: สมุดงานที่ใช้ตรวจจริง
    file_name: str = ""
    uploaded_at: str = ""
    run_sha256: str = ""
    stored_sha256: str = ""
    #: ประเภทเอกสาร/ปีงบที่ผู้ใช้ประกาศตอนใส่ไฟล์ — ใช้เมื่องานไม่ได้เริ่มจากคลังเล่ม (ไม่เดา)
    declared_kind: str = ""
    declared_year: int | None = None

    @property
    def has_book(self) -> bool:
        return bool(self.book_id)

    @property
    def file_matches_run(self) -> bool:
        return bool(self.run_sha256) and self.run_sha256 == self.stored_sha256


@dataclass(frozen=True)
class SourceVerification:
    a: SourceSide
    b: SourceSide
    checks: tuple[SourceCheck, ...]

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.state == CHECK_FAIL)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.state == CHECK_OK)

    @property
    def to_confirm(self) -> int:
        return sum(1 for c in self.checks if c.state in (CHECK_WARN, CHECK_MANUAL))

    @property
    def headline(self) -> str:
        if self.failed:
            return "ยังยืนยันไม่ได้ว่าเป็นเอกสารคู่ที่ถูกต้อง"
        bits = [f"ผ่าน {self.passed} ข้อ"]
        if self.to_confirm:
            bits.append(f"ให้ผู้ตรวจยืนยัน {self.to_confirm} ข้อ")
        return " · ".join(bits)


def source_verification(*, summary, a: SourceSide, b: SourceSide,
                        a_stage_code: str = "", b_stage_code: str = "") -> SourceVerification:
    """ตรวจที่มาเอกสาร — ใช้เฉพาะข้อมูลที่ระบบมีจริง ไม่มี = บอกว่าให้ผู้ตรวจยืนยัน"""
    checks: list[SourceCheck] = []
    # 1) หน่วยงานเดียวกัน — ด่านของเครื่องยนต์ อ่านจากชีตปกในแฟ้ม (fail-closed)
    if summary.identity_gate_blocked:
        checks.append(SourceCheck("หน่วยงานเดียวกัน", CHECK_FAIL,
                                  f"{summary.identity_verdict_label} — ระบบจึงไม่เทียบอัตโนมัติ"))
    else:
        checks.append(SourceCheck("หน่วยงานเดียวกัน", CHECK_OK,
                                  "ยืนยันจากชื่อหน่วยงานในหน้าปกของสมุดงานทั้งสองฉบับ"))
    # 2) ปีงบประมาณ — จากทะเบียนเอกสารที่ผู้ใช้เลือก
    if a.fiscal_year and b.fiscal_year:
        draft_act = a_stage_code == "draft" and b_stage_code == "act"
        if draft_act:
            ok = a.fiscal_year == b.fiscal_year
            text = (f"ร่าง พ.ร.บ. และ พ.ร.บ. ปีงบประมาณ {a.fiscal_year} เดียวกัน" if ok else
                    f"ร่าง ปี {a.fiscal_year} กับ พ.ร.บ. ปี {b.fiscal_year} — คู่ร่าง↔พ.ร.บ. ควรเป็นปีเดียวกัน")
        elif b.fiscal_year == a.fiscal_year + 1:
            ok, text = True, f"เทียบปี {a.fiscal_year} กับปีถัดไป {b.fiscal_year}"
        elif b.fiscal_year == a.fiscal_year:
            ok, text = True, f"ปีงบประมาณ {a.fiscal_year} ทั้งสองฉบับ"
        else:
            ok, text = False, f"ฉบับ A ปี {a.fiscal_year} · ฉบับ B ปี {b.fiscal_year} — ไม่ใช่ปีเดียวกันหรือปีถัดกัน"
        checks.append(SourceCheck("ปีงบประมาณ", CHECK_OK if ok else CHECK_WARN,
                                  text + " (ตามทะเบียนแหล่งทางการ)"))
    else:
        checks.append(SourceCheck("ปีงบประมาณ", CHECK_MANUAL,
                                  "งานนี้ไม่ได้เลือกเอกสารจากคลังเล่มครบสองฝั่ง ระบบจึงไม่มีปีจากทะเบียนให้ตรวจ"))
    # 3) ประเภทเอกสาร/ฉบับ
    if a.stage and b.stage:
        checks.append(SourceCheck("ประเภทเอกสารและฉบับ", CHECK_OK,
                                  f"ฉบับ A = {a.stage} · ฉบับ B = {b.stage} (ตามทะเบียนแหล่งทางการ)"))
    else:
        checks.append(SourceCheck("ประเภทเอกสารและฉบับ", CHECK_MANUAL,
                                  "ไม่มีข้อมูลขั้นเอกสารจากทะเบียนครบสองฝั่ง — ผู้ตรวจยืนยันจากหน้าปกเอง"))
    # 4) ไฟล์ที่เปิดเป็นหลักฐานคือไฟล์ที่ใช้ตรวจจริง
    if a.file_matches_run and b.file_matches_run:
        checks.append(SourceCheck("ไฟล์หลักฐานตรงกับไฟล์ที่ใช้ตรวจ", CHECK_OK,
                                  "ลายนิ้วมือไฟล์ (SHA-256) ทั้งสองฝั่งตรงกับที่บันทึกตอนตรวจ"))
    else:
        checks.append(SourceCheck("ไฟล์หลักฐานตรงกับไฟล์ที่ใช้ตรวจ", CHECK_WARN,
                                  "ไฟล์ที่เก็บอยู่ไม่ตรง/ไม่พบ หรือไม่มีบันทึกลายนิ้วมือของรอบนี้ — เปิดแถวต้นฉบับไม่ได้"))
    # 5) สมุดงานที่ใส่ = เอกสารอ้างอิงที่เลือก — ระบบยังไม่ได้เทียบเนื้อ Excel กับ PDF
    if a.has_book or b.has_book:
        checks.append(SourceCheck("สมุดงานที่ใส่ตรงกับเอกสารอ้างอิง", CHECK_MANUAL,
                                  "ระบบยังไม่ได้เทียบเนื้อในสมุดงานกับ PDF ต้นทาง — เปิด PDF แล้วยืนยันเอง"))
    return SourceVerification(a=a, b=b, checks=tuple(checks))


# ══════════════════════════════════════════════════════════════════════════════
#  เหตุผลที่ยกเป็นข้อสังเกต · "ระบบอ่านไม่ครบ" บอกว่าขาดอะไร
# ══════════════════════════════════════════════════════════════════════════════

#: รหัสความไม่แน่นอนของเครื่องยนต์ → ภาษาคน (ไม่รู้จัก = ข้อความทั่วไป ไม่เดา)
UNREAD_REASONS = {
    "cover_sheet_layout_not_mapped":
        "แถวนี้อยู่ในหน้าปก (ชื่อหน่วยงาน/ปี/หมายเหตุ) — ระบบไม่ได้เทียบเป็นรายการงบ",
    "supporting_sheet_layout_not_mapped": "อยู่ในชีตรายละเอียดประกอบที่ระบบยังไม่รู้จักรูปแบบ",
    "rows_outside_year_table_not_mapped": "อยู่นอกตารางปีงบประมาณ (เช่น หัวเรื่องชีต หรือบรรทัดประกาศหน่วย)",
    "header_row_not_located": "หาแถวหัวตารางไม่พบ จึงไม่รู้ว่าแต่ละคอลัมน์เป็นของปีใด",
    "no_year_columns_in_header": "หัวตารางไม่มีคอลัมน์ปีงบประมาณ",
    "numeric_cell_not_accounted_by_any_table": "มีตัวเลขที่ไม่อยู่ในตารางใดที่ระบบรู้จัก",
    "table_boundary_ambiguous": "ขอบเขตของตารางไม่ชัด",
    "budget_category_unresolved": "อ่านหมวดงบรายจ่ายของค่านี้ไม่ได้",
    "declared_unit_unresolved": "อ่านหน่วยนับไม่ได้",
    "parent_link_unresolved": "หาหัวข้อแม่ของแถวนี้ไม่ได้",
    "sheet_title_selection_ambiguous": "หัวเรื่องชีตกำกวม",
    "invalid_comparison_axis": "ไม่รู้ว่าค่าในแถวนี้เป็นของปีหรือหมวดใด",
    "single_amount_fiscal_year_unresolved": "อ่านปีงบประมาณของยอดนี้ไม่ได้",
    "single_amount_key_ambiguous": "มีหลายแถวชื่อเดียวกันจนแยกไม่ออก",
    "category_table_fiscal_year_unresolved": "อ่านปีของตารางจำแนกตามงบรายจ่ายไม่ได้",
    "ambiguous_project_title_within_plan": "ชื่อโครงการซ้ำกันในแผนงานเดียวกัน",
}
_CODE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+")
_NUM = re.compile(r"-?[0-9][0-9,]*(?:\.[0-9]+)?")


@dataclass(frozen=True)
class Unread:
    """แถวที่ระบบอ่านไม่ครบ — บอกว่าอ่านอะไรได้ และอะไรที่ยังยืนยันไม่ได้"""

    side: str
    read_text: str
    read_numbers: tuple[str, ...]
    missing: tuple[str, ...]


def _unread_of(f: FindingView) -> Unread | None:
    if not f.finding_type.startswith("UNMAPPED"):
        return None
    loc = f.baseline or f.current
    side = "A" if f.baseline else "B"
    raw = (loc.value if loc else "") or ""
    codes = [c for c in _CODE.findall(f.detail or "")
             if c not in ("baseline", "current")]
    missing = tuple(dict.fromkeys(UNREAD_REASONS.get(c, "") for c in codes if UNREAD_REASONS.get(c)))
    nums = tuple(n for n in _NUM.findall(raw) if any(ch.isdigit() for ch in n))
    return Unread(side=side, read_text=(loc.label if loc else "") or f.row_label,
                  read_numbers=nums,
                  missing=missing or ("ระบบยังตีความโครงสร้างของแถวนี้ไม่ได้",))


def item_unread(it: "Item") -> list[Unread]:
    return [u for f in it.findings if (u := _unread_of(f))]


_REASON = {
    K_MONEY: "จำนวนเงินของสองฉบับไม่เท่ากัน",
    K_ADDED: "พบรายการใหม่ในฉบับ B (ไม่มีรายการที่จับคู่ได้ในฉบับ A)",
    K_REMOVED: "พบรายการนี้ในฉบับ A แต่ยังไม่พบรายการที่จับคู่ได้ในฉบับ B",
    K_INDICATOR: "ค่าตัวชี้วัดของสองฉบับไม่เท่ากัน",
    K_TEXT: "ข้อความในแถวถูกแก้ ทั้งที่ระบบยังจับคู่เป็นรายการเดียวกัน",
    K_UNIT: "หน่วยนับของสองฉบับไม่เหมือนกัน ระบบจึงไม่เทียบตัวเลขให้",
    K_ORDINAL: "เลขลำดับโครงการเปลี่ยน",
}
#: ลำดับ "ประเภทประเด็น" หลักของรายการ — ใช้ตั้งป้ายและเรียงคิว
PRIMARY_ORDER = (K_MONEY, K_REMOVED, K_ADDED, K_INDICATOR, K_TEXT, K_UNIT, K_ORDINAL, K_REVIEW)


def primary_kind(it: "Item") -> str:
    return next((k for k in PRIMARY_ORDER if k in it.kinds), "")


def issue_label(it: "Item") -> str:
    k = primary_kind(it)
    if k == K_REVIEW:
        return "ระบบอ่านข้อมูลส่วนนี้ไม่ครบ" if item_unread(it) else "ควรตรวจทาน"
    return KIND_LABELS.get(k, "เท่าเดิม")


def issue_reasons(it: "Item") -> list[str]:
    """เหตุผลที่ระบบยกรายการนี้ขึ้นมา — ภาษาคน ทีละข้อ"""
    out = [_REASON[k] for k in PRIMARY_ORDER if k in it.kinds and k in _REASON]
    for u in item_unread(it):
        out.append(f"ฉบับ {u.side}: ระบบอ่านแถวนี้ไม่ครบ — " + " · ".join(u.missing))
    for r in it.review_reasons:
        if not r.startswith("ระบบอ่านแถวนี้ไม่ครบ"):
            out.append(f"ควรตรวจทาน: {r}")
    details = {f.detail for f in it.findings
               if f.detail and not f.finding_type.startswith("UNMAPPED")
               and f.finding_type not in (F_ROW_ADDED, F_ROW_REMOVED)}
    # ข้อความจากเครื่องยนต์อาจมีรหัสภายใน (เช่น ``workbook_cover``) — ตัดวงเล็บที่เป็นรหัสออก
    # ข้อความเต็มยังอยู่ในหน้ารายละเอียดทางเทคนิคของข้อสังเกต
    out.extend(sorted({_strip_codes(d) for d in details}))
    return out or ["ค่าเท่าเดิม — แสดงไว้ให้ผู้ตรวจยืนยัน"]


def _strip_codes(text: str) -> str:
    t = re.sub(r"\s*\([^()]*[a-z]+_[a-z_]+[^()]*\)", "", text or "")
    return t.replace("🔴", "").strip()


def where(loc) -> str:
    """ตำแหน่งในสมุดงาน — ชีต · แถว (ไฟล์ Excel ไม่มีเลขหน้า)"""
    if loc is None:
        return ""
    return f"ชีต {loc.sheet} · แถว {loc.row}" if loc.row and loc.row > 0 else f"ชีต {loc.sheet}"


# ══════════════════════════════════════════════════════════════════════════════
#  คำตัดสินของผู้ตรวจ — ปุ่มภาษาคน 6 แบบ บนสถานะเดิม 4 แบบ (คำตัดสินกิ๊ฟ 7 ต.ค.)
# ══════════════════════════════════════════════════════════════════════════════
#
# 🔴 ไม่เพิ่มสถานะใน schema · ไม่แตะไฟล์ส่งออก — เหตุผลที่เลือกถูกบันทึกนำหน้า
#    หมายเหตุ ``[ป้าย]`` จึงอยู่ใน Audit Trail และไฟล์ส่งออกครบ

from . import decisions as _dec  # noqa: E402

DECISION_CHOICES = (
    ("checked", "รับทราบ — ตรวจแล้ว", _dec.DISMISSED),
    ("per_document", "เป็นการเปลี่ยนแปลงตามเอกสาร", _dec.DISMISSED),
    ("needs_more", "ต้องตรวจเพิ่มเติม", _dec.UNRESOLVED),
    ("mismatch", "ระบบจับคู่ผิด", _dec.DISMISSED),
    ("not_relevant", "ไม่เกี่ยวข้อง", _dec.DISMISSED),
    ("fix", "ต้องแก้ข้อมูล", _dec.CONFIRMED),
)
DECISION_BY_KEY = {k: (label, status) for k, label, status in DECISION_CHOICES}


def decision_note(choice: str, note: str) -> str:
    label = DECISION_BY_KEY[choice][0]
    note = (note or "").strip()
    return f"[{label}] {note}".strip()


def choice_of_note(note: str) -> str:
    """ป้ายเหตุผลที่บันทึกไว้หน้าหมายเหตุ (ถ้ามี) — ใช้แสดงสถานะในคิว"""
    m = re.match(r"^\[([^\]]+)\]", note or "")
    return m.group(1) if m and m.group(1) in {c[1] for c in DECISION_CHOICES} else ""


@dataclass(frozen=True)
class ItemState:
    pending: int
    total: int
    label: str
    #: ``todo`` ○ ยังไม่ตรวจ · ``done`` ✓ ตรวจแล้ว · ``more`` ! ต้องตรวจเพิ่ม
    mark: str = "todo"

    @property
    def done(self) -> bool:
        return self.pending == 0

    @property
    def icon(self) -> str:
        return {"todo": "○", "done": "✓", "more": "!"}[self.mark]

    @property
    def short(self) -> str:
        return {"todo": "ยังไม่ตรวจ", "done": "ตรวจแล้ว", "more": "ต้องตรวจเพิ่ม"}[self.mark] + (
            f" {self.total - self.pending}/{self.total}" if 0 < self.pending < self.total else "")


def item_state(it: "Item", ann: dict) -> ItemState:
    sts = [ann[f.finding_id] for f in it.findings if f.finding_id in ann]
    pending = sum(1 for a in sts if a.status == _dec.PENDING)
    total = len(it.findings)
    if pending == total:
        label = "ยังไม่ตรวจ"
    elif pending:
        label = f"ตรวจแล้ว {total - pending}/{total}"
    else:
        labels = {a.status_label for a in sts}
        label = "ตรวจแล้ว · " + (labels.pop() if len(labels) == 1 else "หลายคำตัดสิน")
    if any(a.status == _dec.UNRESOLVED for a in sts):
        mark = "more"
    elif pending == 0:
        mark = "done"
    else:
        mark = "todo"
    return ItemState(pending, total, label, mark)


def queue_items(ov: Overview, ann: dict, *, state: str = "", kind: str = "") -> list["Item"]:
    """คิว = ทุกรายการ (รวมรายการที่ค่าเท่าเดิม ซึ่งยังต้องมีคนยืนยัน) เรียงตามประเภทประเด็น"""
    order = {k: i for i, k in enumerate(PRIMARY_ORDER)}
    out = list(ov.items)
    if state == "pending":
        out = [it for it in out if not item_state(it, ann).done]
    elif state == "done":
        out = [it for it in out if item_state(it, ann).done]
    if kind in KIND_LABELS:
        out = [it for it in out if kind in it.kinds]
    elif kind == "same":
        out = [it for it in out if not it.kinds]
    return sorted(out, key=lambda it: (order.get(primary_kind(it), len(order)),
                                       -it.max_abs_diff_baht))


# ══════════════════════════════════════════════════════════════════════════════
#  คิวแบบ compact — กลุ่มตามโครงสร้างงบจริง + แถบบริบทของรอบ (requirement 7 ต.ค. รอบ 3)
# ══════════════════════════════════════════════════════════════════════════════

#: ตัวกรองแบบรวมกลุ่มบนหัวคิว — เงิน · ตัวชี้วัด · รายการ (เพิ่ม/หาย/ข้อความ/หน่วย/ลำดับ)
QUEUE_FILTERS = (
    ("money", "เงิน", {K_MONEY}),
    ("indicator", "ตัวชี้วัด", {K_INDICATOR}),
    ("items", "รายการ", {K_ADDED, K_REMOVED, K_TEXT, K_UNIT, K_ORDINAL}),
    ("review", "ควรตรวจทาน", {K_REVIEW}),
)


@dataclass(frozen=True)
class QueueGroup:
    key: str
    crumbs: tuple[str, ...]
    items: tuple["Item", ...]
    #: กลุ่มพับไว้ตั้งแต่ต้น (แถวที่อ่านไม่ครบ · ค่าเท่าเดิม)
    collapsed: bool = False
    note: str = ""


def _match_filter(it: "Item", key: str) -> bool:
    if not key:
        return True
    if key == "same":
        return not it.kinds
    for k, _label, kinds in QUEUE_FILTERS:
        if k == key:
            return bool(it.kinds & kinds)
    return True


def queue_filter_counts(ov: Overview) -> list[tuple[str, str, int]]:
    out = []
    for k, label, kinds in QUEUE_FILTERS:
        n = sum(1 for it in ov.items if it.kinds & kinds)
        if n:
            out.append((k, label, n))
    return out


def queue_groups(ov: Overview, ann: dict, *, state: str = "", flt: str = "") -> list[QueueGroup]:
    """จัดคิวเป็นกลุ่มตามแผนงาน/โครงการ เรียงตามลำดับในเอกสาร

    แถวที่ระบบอ่านไม่ครบ (หน้าปก/หัวตาราง) และแถวที่ค่าเท่าเดิม แยกเป็นกลุ่มพับไว้ท้ายคิว
    — ยังอยู่ครบ (ห้ามทิ้งเงียบ) แต่ไม่แย่งพื้นที่จากรายการที่เปลี่ยนจริง
    """
    rows = [it for it in ov.items if _match_filter(it, flt)]
    if state == "pending":
        rows = [it for it in rows if not item_state(it, ann).done]
    elif state == "done":
        rows = [it for it in rows if item_state(it, ann).done]
    unread = [it for it in rows if item_unread(it) and not it.changed]
    same = [it for it in rows if not it.kinds]
    scope = [it for it in rows if it.override_title]          # ปีที่มีฉบับเดียว (เทียบข้ามปี)
    main = [it for it in rows if it not in unread and it not in same and it not in scope]
    groups: dict[tuple, list] = {}
    for it in sorted(main, key=lambda x: x.order):      # กลุ่มเรียงตามที่พบในเอกสาร
        groups.setdefault(it.group_crumbs, []).append(it)
    out = [QueueGroup("|".join(k), k, tuple(sorted(v, key=lambda x: x.doc_order)))
           for k, v in groups.items()]
    if scope:
        out.append(QueueGroup("scope", ("ช่วงปีที่เทียบไม่ได้ (ปีที่มีในฉบับเดียว)",),
                              tuple(sorted(scope, key=lambda x: x.order)), collapsed=True,
                              note="ไม่ใช่รายการหาย/รายการใหม่ — ยืนยันว่ารับทราบช่วงปีที่เทียบ"))
    if same:
        out.append(QueueGroup("same", ("ค่าเท่าเดิม — รอผู้ตรวจยืนยัน",),
                              tuple(sorted(same, key=lambda x: x.order)), collapsed=flt != "same"))
    if unread:
        out.append(QueueGroup("unread", ("แถวที่ระบบอ่านไม่ครบ (หน้าปก · หัวตาราง · บรรทัดหน่วย)",),
                              tuple(sorted(unread, key=lambda x: x.order)),
                              collapsed=flt != "review",
                              note="แต่ละแถวบอกว่าระบบอ่านอะไรได้และขาดอะไร"))
    return out


@dataclass(frozen=True)
class RunContext:
    """บริบทของรอบตรวจสำหรับแถบด้านบน — ทุกค่ามาจากทะเบียน/ไฟล์ ไม่มี = ว่าง (ไม่เดา)"""

    agency: str
    ministry: str
    year_a: int | None
    year_b: int | None
    label_a: str
    label_b: str
    synthetic: bool
    #: ช่วงปีที่เทียบได้ (เทียบข้ามปี) — ว่าง = ทุกปีมีในทั้งสองฉบับ
    scope: str = ""

    @property
    def years(self) -> str:
        if self.year_a and self.year_b:
            return (f"ปีงบประมาณ {self.year_a}" if self.year_a == self.year_b
                    else f"ปี {self.year_a} ↔ ปี {self.year_b}")
        return ""


def run_context(sv: "SourceVerification", wb_a: dict, wb_b: dict, *, scope: str = "") -> RunContext:
    """ป้าย A/B = ขั้นเอกสาร + ปีงบ · ลำดับที่มา: ทะเบียนเล่ม → ที่ผู้ใช้ประกาศตอนใส่ไฟล์ → หน้าปกแฟ้ม"""
    a, b = sv.a, sv.b
    year_a = a.fiscal_year or a.declared_year or wb_a.get("year")
    year_b = b.fiscal_year or b.declared_year or wb_b.get("year")

    def label(src, year):
        kind = src.stage or src.declared_kind or "ฉบับ " + src.side
        return f"{kind} ปี {year}" if year else kind

    agency = wb_a.get("agency") or wb_b.get("agency") or ""
    if wb_a.get("agency") and wb_b.get("agency") and wb_a["agency"] != wb_b["agency"]:
        agency = f"{wb_a['agency']} / {wb_b['agency']}"
    ministry = ", ".join(a.ministries or b.ministries)
    return RunContext(agency=agency, ministry=ministry if ministry != agency else "",
                      year_a=year_a, year_b=year_b,
                      label_a=label(a, year_a), label_b=label(b, year_b),
                      synthetic=a.synthetic or b.synthetic, scope=scope)


__all__ = [
    "VIEW_VERSION", "KIND_LABELS", "LENSES", "Item", "Cell", "Overview",
    "MoneyOverview", "TextDiff", "Segment", "build_overview", "group_items",
    "items_for", "kind_counts", "diff_text", "text_differs", "fmt_number",
    "fmt_baht", "direction_word", "parse_amount", "unit_scale",
    "SourceSide", "SourceCheck", "SourceVerification", "source_verification",
    "Unread", "item_unread", "issue_label", "issue_reasons", "primary_kind", "where",
    "DECISION_CHOICES", "decision_note", "choice_of_note", "item_state", "queue_items",
    "QUEUE_FILTERS", "QueueGroup", "queue_groups", "queue_filter_counts", "RunContext",
    "run_context", "amt", "Change",
]
