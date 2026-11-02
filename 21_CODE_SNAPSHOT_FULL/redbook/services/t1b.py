# -*- coding: utf-8 -*-
"""สัญญาชั้นบริการและ projection ของ T1B

🔴 คำสั่ง Bo · `BO REVIEW COMPLETE` (Issue #1) · LANE B ข้อ 3 · 6

**หลักการที่ยืนยันแล้วและถูกบังคับที่นี่**

1. เว็บแอปเดิม **ยังไม่ได้เชื่อม**กับเครื่องยนต์ T1B — การเชื่อมต้องผ่านชั้นนี้
2. finding ของ T1B **ห้ามถูกยัด**ลง schema/ตารางของ T1A · โครงสร้างต่างกันโดยเนื้อแท้
   (T1B มี ``comparison_axis`` · ``budget_category`` · ธงระดับ finding ·
   ผลด่านตัวตนหน่วยงานระดับการเปรียบเทียบ ซึ่ง T1A ไม่มีเลย)
3. ``READY / REVIEW REQUIRED`` เป็น **สถานะที่คำนวณได้** ไม่ใช่ปุ่ม —
   ที่นี่จึงมีแต่ฟังก์ชันคำนวณ **ไม่มี setter ไม่มีการเก็บค่าลงฐานข้อมูล**
4. กันข้อมูลรั่วมาก่อนการออกแบบหน้าตา — ทุก projection ผ่าน :mod:`redbook.privacy`

**สิ่งที่ยังไม่ทำในชั้นนี้ตามคำสั่ง**

* enum คำตัดสินสุดท้ายของมนุษย์
* ความหมายของ confidence ที่จะใช้ตอนปล่อยของ
* หน้าผลกระทบข้ามชีต (ต้องรอ A-10) · หน้า formula/preflight (ต้องรอ A-11)
* การส่งออกหลักฐาน (ต้องปิดเรื่อง CSV/formula-injection ก่อน)

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from .. import privacy
from ..core.hashing import sha256_text
from ..t1b.compare import (
    F_AMBIGUOUS,
    F_AMOUNT_DECREASED,
    F_AMOUNT_INCREASED,
    F_AMOUNT_UNCHANGED,
    F_INDICATOR_CHANGED,
    F_INDICATOR_UNCHANGED,
    F_NOT_COMPARABLE,
    F_PROJECT_ORDINAL_CHANGED,
    F_ROW_ADDED,
    F_ROW_REMOVED,
    F_UNIT_CHANGED,
    F_UNMAPPED,
    F_YEAR_ONLY_ONE_SIDE,
    FLAG_CATEGORY_TABLE_YEAR_DIFFERS,
    FLAG_CATEGORY_TABLE_YEAR_UNKNOWN,
    COMPARE_VERSION,
    CompareResult,
    Finding,
    compare,
)
from ..t1b.keys import KEY_VERSION
from ..t1b.matching import (
    MATCHING_VERSION,
    VERDICT_CANNOT_DETERMINE,
    VERDICT_COMPARED,
    VERDICT_REVIEW_REQUIRED,
    match_records,
)

SERVICE_VERSION = "t1b-service-0.1.0"

# ------------------------------------------------------------- สถานะที่คำนวณได้
#: ไม่มีอะไรค้างให้คนตัดสิน
READY = "READY"
#: มีรายการที่คนต้องตัดสิน — หรือด่านตัวตนหน่วยงานชี้ว่าคู่นี้ผิดฝาผิดตัว
REVIEW_REQUIRED = "REVIEW_REQUIRED"
#: หลักฐานไม่พอจะสรุปอะไรได้เลย — **ไม่ใช่** "ผ่าน" และ **ไม่ใช่** "ไม่ผ่าน"
CANNOT_DETERMINE = "CANNOT_DETERMINE"

READINESS_LABELS = {
    READY: "ไม่มีรายการค้างให้ตรวจ",
    REVIEW_REQUIRED: "ต้องให้ผู้ตรวจตัดสิน",
    CANNOT_DETERMINE: "ยังสรุปไม่ได้ — หลักฐานไม่พอ",
}

TYPE_LABELS = {
    F_AMOUNT_INCREASED: "ยอดเพิ่มขึ้น",
    F_AMOUNT_DECREASED: "ยอดลดลง",
    F_AMOUNT_UNCHANGED: "ยอดเท่าเดิม",
    F_INDICATOR_CHANGED: "ตัวชี้วัดเปลี่ยน",
    F_INDICATOR_UNCHANGED: "ตัวชี้วัดเท่าเดิม",
    F_ROW_ADDED: "มีเพิ่มในฉบับปัจจุบัน",
    F_ROW_REMOVED: "ไม่พบในฉบับปัจจุบัน",
    F_UNIT_CHANGED: "หน่วยนับเปลี่ยน",
    F_NOT_COMPARABLE: "เทียบกันไม่ได้",
    F_PROJECT_ORDINAL_CHANGED: "เลขลำดับโครงการเปลี่ยน",
    F_YEAR_ONLY_ONE_SIDE: "ปีนี้มีข้างเดียว",
    F_AMBIGUOUS: "ระบบตีความไม่ได้",
    # 🔴 ป้ายบนหน้าจอต้องเป็นภาษาที่คนทำงบอ่านออก (กิ๊ฟ 23 ก.ย. 2569)
    # ข้อความอธิบายในชั้นเครื่องยนต์ยังใช้คำเดิม — แก้ไม่ได้ในรอบนี้
    # เพราะ ``redbook/t1b/*`` ถูกตรึงไว้ (ยกไปเป็นข้อเสนอรอบ G1–G6)
    F_UNMAPPED: "ระบบอ่านแถวนี้ไม่ครบ",
}

FLAG_LABELS = {
    FLAG_CATEGORY_TABLE_YEAR_DIFFERS: "ตารางหมวดคนละปีงบประมาณ",
    FLAG_CATEGORY_TABLE_YEAR_UNKNOWN: "ปีบริบทของตารางหมวดอ่านไม่ได้",
}

VERDICT_LABELS = {
    VERDICT_COMPARED: "ยืนยันหน่วยงานเดียวกันจากเนื้อในแฟ้ม",
    VERDICT_REVIEW_REQUIRED: "ต้องให้ผู้ตรวจตัดสินก่อน — หลักฐานชี้ว่าอาจคนละหน่วยงาน",
    VERDICT_CANNOT_DETERMINE: "ยืนยันตัวตนหน่วยงานไม่ได้ — ไม่มีการเทียบอัตโนมัติ",
}

#: 🔴 ฟิลด์ที่ประกอบเป็น **ตัวตนของ finding** — ใช้ทำ ``finding_id`` ที่คงที่
#:
#: ต้องคำนวณจาก *เนื้อหา* ไม่ใช่ลำดับการรัน มิฉะนั้นรันซ้ำแล้วเลขเลื่อน
#: และคำตัดสินของมนุษย์จะผูกกลับเข้ากับประเด็นเดิมไม่ได้
#: (หลักการเดียวกับ ``finding_key`` ของ T1A แต่ **คนละ schema คนละตาราง**)
_ID_FIELDS = (
    "finding_type", "fiscal_year", "comparison_axis", "budget_category",
)

# ------------------------------------------------------------ ฝั่งที่มาของ finding
SIDE_PAIR = "pair"          # จับคู่ได้ — มีหลักฐานสองฝั่ง
SIDE_BASELINE_ONLY = "baseline"
SIDE_CURRENT_ONLY = "current"
SIDE_NONE = "none"          # ไม่ผูกกับเซลล์ใด เช่น ``YEAR_PRESENT_ON_ONE_SIDE_ONLY``

SIDE_LABELS = {
    SIDE_PAIR: "มีหลักฐานทั้งสองฉบับ",
    SIDE_BASELINE_ONLY: "พบเฉพาะฉบับตั้งต้น",
    SIDE_CURRENT_ONLY: "พบเฉพาะฉบับปัจจุบัน",
    SIDE_NONE: "เป็นข้อสังเกตระดับขอบเขต ไม่ผูกกับเซลล์",
}

#: ที่มาของ ``finding_id`` — บอกตรง ๆ ว่า id ใบนี้เชื่อถือข้ามการรันได้แค่ไหน
#:
#: ``content``  = คำนวณจากเนื้อหาล้วน ⇒ **คงที่ข้ามการรัน** ผูกคำตัดสินกลับได้
#: ``position`` = เนื้อหาชนกับใบอื่นจนแยกไม่ออก ⇒ ต้องเติมลำดับที่พบเข้าไป
#:               ⇒ **ไม่รับประกันว่าคงที่ข้ามการรัน**
#:
#: 🔴 การผูกคำตัดสินของมนุษย์กลับอัตโนมัติในอนาคต **ห้าม**ทำกับใบที่เป็น
#: ``position`` — ต้องให้คนยืนยันเอง ดีกว่าผูกผิดใบเงียบ ๆ
BASIS_CONTENT = "content"
BASIS_POSITION = "position"


# ══════════════════════════════════════════════════════════════════════════════
#  projection
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class LocationView:
    """ตำแหน่งหลักฐานฝั่งเดียวที่พร้อมแสดงผล — **ไม่มีเส้นทางไฟล์**"""

    side: str
    sheet: str
    cell: str
    row: int
    label: str
    value: str

    @property
    def where(self) -> str:
        parts = [self.sheet]
        if self.cell:
            parts.append(self.cell)
        elif self.row >= 0:
            parts.append(f"แถว {self.row}")
        return " · ".join(p for p in parts if p)


@dataclass(frozen=True)
class FindingView:
    """finding หนึ่งใบในรูปที่หน้าเว็บใช้ได้ทันที

    🔴 **ไม่ใช่** แถวของตาราง ``findings`` ของ T1A — ไม่มี ``severity`` ·
    ``rule_id`` · ``machine_status`` · ``confidence`` และมีฟิลด์ที่ T1A ไม่มี
    """

    finding_id: str
    #: ที่มาของ :attr:`finding_id` — ``content`` หรือ ``position`` ดู ``BASIS_*``
    identity_basis: str
    #: ฝั่งที่มีหลักฐาน — ``pair`` · ``baseline`` · ``current`` · ``none``
    side: str
    finding_type: str
    type_label: str
    requires_human_decision: bool
    flags: tuple[str, ...]
    flag_labels: tuple[str, ...]
    comparison_axis: str
    fiscal_year: int | None
    budget_category: str | None
    row_label: str
    sheet_role: str
    section_title: str
    parent_plan: str
    declared_unit: str
    baseline_value: str
    current_value: str
    difference: str
    baseline_category_table_year: int | None
    current_category_table_year: int | None
    baseline: LocationView | None
    current: LocationView | None
    detail: str

    @property
    def side_label(self) -> str:
        return SIDE_LABELS.get(self.side, self.side)

    @property
    def id_is_stable(self) -> bool:
        """id ใบนี้ผูกคำตัดสินข้ามการรันได้หรือไม่"""
        return self.identity_basis == BASIS_CONTENT

    @property
    def search_text(self) -> str:
        """ข้อความที่ช่องค้นหาจะมองเห็น — รวมไว้ที่เดียว เพื่อให้ค้นได้ตรงกับที่ตาเห็น"""
        parts = [self.row_label, self.section_title, self.parent_plan,
                 self.type_label, self.finding_type, self.detail,
                 self.budget_category or "", self.sheet_role]
        for loc in (self.baseline, self.current):
            if loc is not None:
                parts.extend([loc.sheet, loc.label])
        return " ".join(p for p in parts if p)


@dataclass(frozen=True)
class RunSummaryView:
    """สรุปหนึ่งรอบการตรวจ — ตัวเลขล้วน ไม่มีเนื้อหาเอกสาร"""

    run_id: str
    readiness: str
    readiness_label: str
    identity_verdict: str
    identity_verdict_label: str
    identity_gate_blocked: bool
    identity_reason: str
    automatic_pairs: int
    total_findings: int
    requiring_review: int
    by_type: dict[str, int]
    by_flag: dict[str, int]
    key_version: str = KEY_VERSION
    matching_version: str = MATCHING_VERSION
    compare_version: str = COMPARE_VERSION
    service_version: str = SERVICE_VERSION

    @property
    def by_type_labelled(self) -> list[tuple[str, str, int]]:
        return [(t, TYPE_LABELS.get(t, t), n) for t, n in self.by_type.items()]

    @property
    def by_flag_labelled(self) -> list[tuple[str, str, int]]:
        return [(f, FLAG_LABELS.get(f, f), n) for f, n in self.by_flag.items()]


@dataclass(frozen=True)
class ReconcileRow:
    """หนึ่งแถวของตารางกระทบยอด — **หน่วยเป็น "ข้อสังเกต" ทั้งแถว**"""

    side: str
    side_label: str
    automatic: int
    review: int

    @property
    def total(self) -> int:
        return self.automatic + self.review


@dataclass(frozen=True)
class Reconciliation:
    """ตารางกระทบยอดของหนึ่งรอบ — ทำให้ตัวเลขบนหน้าจอ **บวกกลับได้**

    🔴 เหตุที่ต้องมี — หน้าสรุปเคยวางเลขสามตัวเรียงกันโดยไม่บอกฐาน
    ``ข้อสังเกตทั้งหมด`` · ``ต้องให้ผู้ตรวจตัดสิน`` · ``คู่ที่ระบบจับได้เอง``
    ผู้อ่านย่อมบวกสองตัวหลังแล้วคาดว่าจะได้ตัวแรก **ซึ่งไม่จริง**
    เพราะ ``คู่ที่ระบบจับได้เอง`` มีหน่วยเป็น **คู่** ไม่ใช่ข้อสังเกต
    และคู่ที่จับได้ก็ยังตกไปอยู่ในกองที่ต้องให้คนตัดสินได้

    ที่นี่จึงแบ่งข้อสังเกตทั้งหมดด้วยสองแกนที่ **ครอบคลุมและไม่ทับกัน**
    แกนหนึ่งคือฝั่งที่มีหลักฐาน อีกแกนคือระบบสรุปได้เองหรือไม่
    ผลรวมของทุกช่องต้องเท่ากับ ``total_findings`` เสมอ
    """

    rows: tuple[ReconcileRow, ...]
    #: จำนวน **คู่** ที่ชั้นจับคู่จับได้ — 🔴 คนละหน่วยกับทุกช่องในตาราง
    automatic_pairs: int
    #: ยอดที่หน้าสรุปประกาศไว้ ใช้ตรวจว่าตารางนี้คิดจากชุดเต็มจริงหรือไม่
    declared_total: int

    @property
    def total_automatic(self) -> int:
        return sum(r.automatic for r in self.rows)

    @property
    def total_review(self) -> int:
        return sum(r.review for r in self.rows)

    @property
    def total(self) -> int:
        return sum(r.total for r in self.rows)

    @property
    def pair_findings(self) -> int:
        """ข้อสังเกตที่มีหลักฐานสองฝั่ง — **ไม่จำเป็นต้องเท่ากับจำนวนคู่**"""
        return sum(r.total for r in self.rows if r.side == SIDE_PAIR)

    @property
    def extra_findings_from_pairs(self) -> int:
        """หนึ่งคู่ออกได้มากกว่าหนึ่งใบ เช่นเมื่อเลขลำดับโครงการเปลี่ยนด้วย

        ค่าติดลบเป็นไปได้ในทางทฤษฎีถ้าอนาคตมีคู่ที่ไม่ออก finding เลย
        จึงไม่บังคับให้เป็นบวก แต่ต้องแสดงให้เห็นเสมอ
        """
        return self.pair_findings - self.automatic_pairs

    @property
    def balanced(self) -> bool:
        """ตารางนี้คิดจากชุดเต็มหรือไม่ — ถ้าไม่ ห้ามหน้าจอแสดงเป็นตารางกระทบยอด"""
        return self.total == self.declared_total


def reconcile(view: "T1BRunView") -> Reconciliation:
    """สร้างตารางกระทบยอดจาก **ตัวข้อสังเกตเอง** ไม่ใช่จากตัวเลขสรุปที่เก็บไว้

    คิดจากของจริงทุกครั้ง เพื่อให้ตารางนี้จับได้เองเมื่อยอดสรุปกับชุดข้อสังเกต
    ไม่ตรงกัน แทนที่จะทำให้ตรงกันโดยไม่มีหลักฐาน
    """
    buckets: dict[str, list[int]] = {}
    for f in view.findings:
        cell = buckets.setdefault(f.side, [0, 0])
        cell[1 if f.requires_human_decision else 0] += 1

    order = (SIDE_PAIR, SIDE_BASELINE_ONLY, SIDE_CURRENT_ONLY, SIDE_NONE)
    seen = [s for s in order if s in buckets]
    seen += [s for s in sorted(buckets) if s not in order]
    return Reconciliation(
        rows=tuple(
            ReconcileRow(side=s, side_label=SIDE_LABELS.get(s, s),
                         automatic=buckets[s][0], review=buckets[s][1])
            for s in seen
        ),
        automatic_pairs=view.summary.automatic_pairs,
        declared_total=view.summary.total_findings,
    )


@dataclass(frozen=True)
class T1BRunView:
    """ผลของหนึ่งรอบทั้งก้อนในรูป projection"""

    summary: RunSummaryView
    findings: tuple[FindingView, ...] = ()

    def by_id(self, finding_id: str) -> FindingView | None:
        for f in self.findings:
            if f.finding_id == finding_id:
                return f
        return None

    @property
    def reconciliation(self) -> Reconciliation:
        return reconcile(self)


@dataclass(frozen=True)
class QueuePage:
    """หนึ่งหน้าของคิว พร้อมข้อมูลที่หน้าเว็บต้องใช้เดินหน้า/ถอยหลัง"""

    items: tuple[FindingView, ...]
    page: int
    per_page: int
    total: int
    query: str = ""
    flags: tuple[str, ...] = ()
    types: tuple[str, ...] = ()
    only_review: bool = False

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.per_page))

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def first_index(self) -> int:
        return 0 if not self.total else (self.page - 1) * self.per_page + 1

    @property
    def last_index(self) -> int:
        return min(self.page * self.per_page, self.total)


# ══════════════════════════════════════════════════════════════════════════════
#  การคำนวณสถานะ
# ══════════════════════════════════════════════════════════════════════════════


def readiness_of(*, identity_verdict: str, requiring_review: int) -> str:
    """สถานะความพร้อมของรอบนี้ — **ฟังก์ชันบริสุทธิ์** ไม่มี setter คู่กัน

    🔴 คำสั่ง Bo: *"`READY / REVIEW REQUIRED` is computed state, not a button"*
    จึงจงใจไม่มีทางเก็บค่านี้ลงฐานข้อมูลหรือให้ผู้ใช้กดเปลี่ยน — ถ้าเก็บได้
    ค่าที่เก็บกับความจริงจะเพี้ยนจากกันทันทีที่กฎเปลี่ยนหรือรันใหม่

    ลำดับความสำคัญ: ตัดสินไม่ได้ ▸ ต้องตรวจ ▸ ไม่มีอะไรค้าง
    """
    if identity_verdict == VERDICT_CANNOT_DETERMINE:
        return CANNOT_DETERMINE
    if identity_verdict == VERDICT_REVIEW_REQUIRED or requiring_review > 0:
        return REVIEW_REQUIRED
    return READY


# ══════════════════════════════════════════════════════════════════════════════
#  การแปลงเป็น projection
# ══════════════════════════════════════════════════════════════════════════════


def _text(value) -> str:
    """ข้อความที่ปลอดภัยต่อการแสดงผล — ตัดอักขระควบคุมและกลบเส้นทางไฟล์"""
    if value is None:
        return ""
    s = "".join(
        ch for ch in str(value)
        if ch in "\t\n" or unicodedata.category(ch)[0] != "C"
    ).strip()
    return privacy.redact_text(s)


def _amount(value: Decimal | None) -> str:
    """จำนวนเงินสำหรับแสดงผล — คั่นหลักพัน **คงทศนิยมตามที่เอกสารประกาศ**

    🔴 ห้ามปัดเศษที่ชั้นแสดงผล · ตัวเลขที่ผู้ตรวจเห็นต้องเป็นตัวเลขเดียวกับที่
    เครื่องยนต์ใช้ตัดสิน มิฉะนั้นผู้ตรวจจะเถียงกับหน้าจอแทนที่จะตรวจเอกสาร
    """
    if value is None:
        return ""
    # ``,f`` บังคับรูปแบบทศนิยมตรึง ⇒ ``Decimal("1E+3")`` แสดงเป็น ``1,000``
    # ไม่ใช่ ``1E+3`` ที่ผู้ตรวจอ่านไม่ออก และยังคงทศนิยมท้ายไว้ครบตามที่ประกาศ
    return format(value, ",f")


def side_of(f: Finding) -> str:
    """ฝั่งที่มีหลักฐาน — เป็น **คุณสมบัติเชิงเนื้อหา** ไม่ใช่ตำแหน่ง

    🔴 จำเป็นต่อความเป็นเอกลักษณ์ของ ``finding_id`` — แถวเดียวกันที่ระบบตีความ
    ไม่ได้จะออกเป็น finding **สองใบ** ใบหนึ่งจากฉบับตั้งต้น อีกใบจากฉบับปัจจุบัน
    ถ้าไม่นับฝั่ง สองใบนี้จะได้ id เดียวกัน ⇒ คำตัดสินของผู้ตรวจผูกผิดใบ
    """
    has_b = f.baseline_location is not None
    has_c = f.current_location is not None
    if has_b and has_c:
        return SIDE_PAIR
    if has_b:
        return SIDE_BASELINE_ONLY
    if has_c:
        return SIDE_CURRENT_ONLY
    return SIDE_NONE


def finding_id_of(f: Finding) -> str:
    """ตัวระบุ finding ที่คำนวณจากเนื้อหา — คงที่ข้ามการรันซ้ำ

    🔴 ใช้ ``T1BKey`` ทั้งใบเป็นแกน เพราะคีย์คือ *ตัวตนของรายการ* อยู่แล้ว
    บวกด้วยมิติที่นำมาเทียบ ชนิดของ finding และ **ฝั่งที่มีหลักฐาน**
    · **ไม่ใช้** ตำแหน่งเซลล์ เพราะเซลล์ขยับได้โดยที่รายการยังเป็นรายการเดิม

    ค่าที่คืนอาจ **ชนกันได้** เมื่อสองรายการแยกจากกันด้วยเนื้อหาไม่ได้จริง ๆ
    การทำให้ไม่ซ้ำเป็นหน้าที่ของ :func:`project_run` ซึ่งจะรายงานด้วยว่า
    ใบไหนต้องพึ่งลำดับ (ดู ``BASIS_POSITION``)
    """
    key = f.key
    parts = [
        KEY_VERSION,
        key.agency_code, key.agency_identity, key.document_level,
        key.sheet_role, key.section_title_norm, key.parent_plan_norm,
        key.plan_role, "›".join(key.hierarchy_path), key.row_label_norm,
        side_of(f),
    ]
    parts.extend(str(getattr(f, name) or "") for name in _ID_FIELDS)
    return sha256_text("¦".join(parts))[:16]


def _location(loc, side: str) -> LocationView | None:
    if loc is None:
        return None
    return LocationView(
        side=side,
        sheet=_text(loc.sheet),
        cell=_text(loc.cell),
        row=loc.row,
        label=_text(loc.raw_label),
        value=_text(loc.raw_value),
    )


def project_finding(f: Finding, *, finding_id: str = "",
                    identity_basis: str = BASIS_CONTENT) -> FindingView:
    """แปลง :class:`~redbook.t1b.compare.Finding` เป็น projection ที่แสดงผลได้

    ``finding_id`` / ``identity_basis`` ส่งเข้ามาจาก :func:`project_run` ซึ่งเป็น
    ที่เดียวที่มองเห็นทั้งชุดจึงรู้ว่ามีการชนกันหรือไม่ · เรียกเดี่ยว ๆ ได้เช่นกัน
    """
    return FindingView(
        finding_id=finding_id or finding_id_of(f),
        identity_basis=identity_basis,
        side=side_of(f),
        finding_type=f.finding_type,
        type_label=TYPE_LABELS.get(f.finding_type, f.finding_type),
        requires_human_decision=f.requires_human_decision,
        flags=tuple(f.flags),
        flag_labels=tuple(FLAG_LABELS.get(x, x) for x in f.flags),
        comparison_axis=f.comparison_axis,
        fiscal_year=f.fiscal_year,
        budget_category=f.budget_category,
        row_label=_text(f.key.row_label_norm),
        sheet_role=_text(f.key.sheet_role),
        section_title=_text(f.key.section_title_norm),
        parent_plan=_text(f.key.parent_plan_norm),
        declared_unit=_text(f.declared_unit),
        baseline_value=_amount(f.baseline_value),
        current_value=_amount(f.current_value),
        difference=_amount(f.difference),
        baseline_category_table_year=f.baseline_category_table_year,
        current_category_table_year=f.current_category_table_year,
        baseline=_location(f.baseline_location, "baseline"),
        current=_location(f.current_location, "current"),
        detail=_text(f.detail),
    )


def _project_all(findings) -> list[FindingView]:
    """แปลงทั้งชุด พร้อม **รับประกันว่า id ไม่ซ้ำภายในรอบเดียวกัน**

    🔴 id ที่ซ้ำอันตรายกว่าที่เห็น — ปุ่มก่อนหน้า/ถัดไปจะวนกลับไปใบแรกเสมอ
    และคำตัดสินของผู้ตรวจจะไปลงใบผิด

    ใบที่ชนกันจะได้ลำดับที่พบต่อท้าย และถูกติดป้าย ``BASIS_POSITION`` เพื่อบอก
    ตรง ๆ ว่า id ชุดนี้ **ไม่รับประกันว่าคงที่ข้ามการรัน** — ดีกว่าเงียบแล้วให้
    คนเข้าใจผิดว่าผูกคำตัดสินกลับได้
    """
    bases = [finding_id_of(f) for f in findings]
    counts: dict[str, int] = {}
    for b in bases:
        counts[b] = counts.get(b, 0) + 1

    seen: dict[str, int] = {}
    out: list[FindingView] = []
    for f, base in zip(findings, bases):
        if counts[base] == 1:
            out.append(project_finding(f, finding_id=base,
                                       identity_basis=BASIS_CONTENT))
            continue
        n = seen.get(base, 0) + 1
        seen[base] = n
        out.append(project_finding(f, finding_id=f"{base}-{n}",
                                   identity_basis=BASIS_POSITION))
    return out


def project_run(result: CompareResult, *, run_id: str) -> T1BRunView:
    """แปลงผลการเปรียบเทียบทั้งก้อนเป็น projection

    🔴 **ห้ามกรอง finding ทิ้งที่ชั้นนี้** — ชั้นแสดงผลมีสิทธิ์ *ซ่อนชั่วคราว*
    ด้วยตัวกรองที่ผู้ใช้เลือกเอง แต่ตัวเลขสรุปต้องมาจากชุดเต็มเสมอ
    """
    findings = tuple(_project_all(result.findings))
    s = result.summary()
    verdict = str(s["identity_verdict"])
    requiring = int(s["requiring_human_decision"])
    readiness = readiness_of(identity_verdict=verdict, requiring_review=requiring)
    summary = RunSummaryView(
        run_id=run_id,
        readiness=readiness,
        readiness_label=READINESS_LABELS[readiness],
        identity_verdict=verdict,
        identity_verdict_label=VERDICT_LABELS.get(verdict, verdict),
        identity_gate_blocked=bool(s["identity_gate_blocked"]),
        identity_reason=str(s["identity_reason"] or ""),
        automatic_pairs=int(s["automatic_pairs"]),
        total_findings=int(s["total_findings"]),
        requiring_review=requiring,
        by_type=dict(result.by_type()),
        by_flag=dict(result.by_flag()),
    )
    return T1BRunView(summary=summary, findings=findings)


# ══════════════════════════════════════════════════════════════════════════════
#  คิว — ค้นหา · ตัวกรอง · แบ่งหน้า · เดินหน้าถอยหลัง
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_PER_PAGE = 50
MAX_PER_PAGE = 200


def _normalize_query(q: str) -> str:
    return unicodedata.normalize("NFC", (q or "").strip()).casefold()


def filter_findings(
    view: T1BRunView, *, query: str = "", flags=(), types=(),
    only_review: bool = False,
) -> tuple[FindingView, ...]:
    """คัดกรองตามเงื่อนไขที่ผู้ใช้เลือก — **ไม่แตะตัวเลขสรุป**

    ค้นหาเป็นการจับคำแบบ **มีอยู่จริงในข้อความ** ทุกคำต้องพบครบ (AND)
    🔴 ไม่ใช้ fuzzy similarity — เหตุผลเดียวกับที่ชั้นจับคู่ไม่ใช้
    ผู้ใช้ต้องอธิบายผลการค้นหาได้ว่าทำไมแถวนี้ขึ้นมา
    """
    want_flags = frozenset(flags or ())
    want_types = frozenset(types or ())
    terms = [t for t in _normalize_query(query).split() if t]

    out = []
    for f in view.findings:
        if only_review and not f.requires_human_decision:
            continue
        if want_types and f.finding_type not in want_types:
            continue
        if want_flags and not want_flags.intersection(f.flags):
            continue
        if terms:
            hay = unicodedata.normalize("NFC", f.search_text).casefold()
            if not all(t in hay for t in terms):
                continue
        out.append(f)
    return tuple(out)


def queue_page(
    view: T1BRunView, *, page: int = 1, per_page: int = DEFAULT_PER_PAGE,
    query: str = "", flags=(), types=(), only_review: bool = False,
) -> QueuePage:
    """หนึ่งหน้าของคิว — หน้าที่เกินช่วงถูกดึงกลับเข้าช่วงเสมอ ไม่ยกข้อผิดพลาด"""
    per_page = max(1, min(int(per_page or DEFAULT_PER_PAGE), MAX_PER_PAGE))
    matched = filter_findings(view, query=query, flags=flags, types=types,
                              only_review=only_review)
    total = len(matched)
    pages = max(1, -(-total // per_page))
    page = max(1, min(int(page or 1), pages))
    start = (page - 1) * per_page
    return QueuePage(
        items=matched[start:start + per_page],
        page=page, per_page=per_page, total=total,
        query=query or "", flags=tuple(flags or ()), types=tuple(types or ()),
        only_review=only_review,
    )


#: อักขระที่ไม่ต้องเข้ารหัสตาม RFC 3986 (unreserved)
_UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)


def _percent_encode(value: str) -> str:
    """เข้ารหัสค่าหนึ่งช่องของ query string ตาม RFC 3986

    🔴 เขียนเองแทนการเรียก ``urllib.parse`` เพราะกติกาสถาปัตยกรรมของโปรเจกต์นี้
    **ห้ามนำเข้าไลบรารีเครือข่ายทั้งตระกูลเข้ามาในแพ็กเกจ** (local-first)
    ฟังก์ชันนี้แปลงข้อความล้วน ไม่แตะเครือข่ายใด ๆ

    ใช้ ``%20`` แทนช่องว่าง ไม่ใช่ ``+`` — ถอดกลับได้เหมือนกันทั้งสองแบบ
    แต่ ``%20`` ไม่กำกวมเมื่อค่าจริงมีเครื่องหมายบวกอยู่
    """
    out = []
    for byte in str(value).encode("utf-8"):
        ch = chr(byte)
        out.append(ch if ch in _UNRESERVED else f"%{byte:02X}")
    return "".join(out)


def filter_query(*, query: str = "", flags=(), types=(),
                 only_review: bool = False, per_page: int | None = None,
                 page: int | None = None) -> str:
    """สร้าง query string ของสถานะคิวปัจจุบัน — **ประกอบที่นี่ ไม่ใช่ในเทมเพลต**

    🔴 เคยประกอบด้วย Jinja macro แล้วพบว่า macro มองไม่เห็นตัวแปรบางตัวจาก
    context ทำให้ลิงก์ออกมาเป็น ``per_page=`` ที่ไม่มีค่า — ผู้ใช้กดแล้วขนาดหน้า
    เด้งกลับค่าเริ่มต้นโดยไม่มีอะไรบอก · ย้ายมาไว้ที่นี่จึงทดสอบตรง ๆ ได้

    ค่าที่เท่ากับค่าเริ่มต้นจะถูกละไว้ เพื่อให้ URL สั้นและอ่านออก
    """
    pairs: list[tuple[str, str]] = []
    if query:
        pairs.append(("q", query))
    for f in flags or ():
        pairs.append(("flag", f))
    for t in types or ():
        pairs.append(("ftype", t))
    if only_review:
        pairs.append(("only_review", "1"))
    if per_page is not None and int(per_page) != DEFAULT_PER_PAGE:
        pairs.append(("per_page", str(int(per_page))))
    if page is not None:
        pairs.append(("page", str(int(page))))
    return "&".join(f"{k}={_percent_encode(v)}" for k, v in pairs)


@dataclass(frozen=True)
class FindingDetail:
    """หนึ่ง finding พร้อมเพื่อนบ้านใน **คิวที่กรองอยู่ขณะนั้น**

    🔴 ปุ่มก่อนหน้า/ถัดไปต้องเดินตามคิวที่ผู้ใช้เห็น ไม่ใช่ชุดเต็ม
    มิฉะนั้นกดถัดไปแล้วหลุดออกนอกตัวกรองโดยไม่มีอะไรบอก
    """

    finding: FindingView
    position: int
    total: int
    prev_id: str = ""
    next_id: str = ""


def finding_detail(
    view: T1BRunView, finding_id: str, *, query: str = "", flags=(), types=(),
    only_review: bool = False,
) -> FindingDetail | None:
    matched = filter_findings(view, query=query, flags=flags, types=types,
                              only_review=only_review)
    ids = [f.finding_id for f in matched]
    if finding_id not in ids:
        found = view.by_id(finding_id)
        if found is None:
            return None
        # อยู่ในชุดเต็มแต่ไม่อยู่ในตัวกรองปัจจุบัน — แสดงได้ แต่ไม่มีเพื่อนบ้าน
        return FindingDetail(finding=found, position=0, total=len(matched))
    i = ids.index(finding_id)
    return FindingDetail(
        finding=matched[i],
        position=i + 1,
        total=len(matched),
        prev_id=ids[i - 1] if i > 0 else "",
        next_id=ids[i + 1] if i + 1 < len(ids) else "",
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ทางเข้าเดียวจากเว็บ
# ══════════════════════════════════════════════════════════════════════════════


def _location_from_row(data: dict) -> LocationView | None:
    """🔴 ทุกช่องต้องผ่าน :func:`_text` เหมือนเส้นทาง live ทุกประการ

    ตำแหน่งหลักฐานถูกลืมง่ายที่สุดเพราะซ้อนอยู่ใน JSON — และเป็นช่องที่มีทั้ง
    ชื่อชีต ป้ายแถว และค่าดิบจากสมุดงานของผู้ใช้ครบทุกอย่าง
    """
    if not data:
        return None
    return LocationView(
        side=_text(data.get("side")), sheet=_text(data.get("sheet")),
        cell=_text(data.get("cell")), row=int(data.get("row", -1)),
        label=_text(data.get("label")), value=_text(data.get("value")),
    )


def view_from_storage(run_row: dict, finding_rows) -> T1BRunView:
    """ประกอบ projection กลับจากแถวที่เก็บไว้ — **ฟังก์ชันบริสุทธิ์**

    🔴 ``readiness`` ถูก **คำนวณใหม่** ที่นี่ ไม่ได้อ่านจากฐานข้อมูล
    (ฐานข้อมูลไม่มีคอลัมน์นั้นโดยเจตนา) ⇒ หน้าจอที่เปิดวันนี้จะสะท้อนกติกา
    ของวันนี้เสมอ ไม่ใช่กติกาของวันที่บันทึก
    """
    verdict = str(run_row["identity_verdict"])
    requiring = int(run_row["requiring_review"])
    readiness = readiness_of(identity_verdict=verdict, requiring_review=requiring)
    summary = RunSummaryView(
        run_id=str(run_row["id"]),
        readiness=readiness,
        readiness_label=READINESS_LABELS[readiness],
        identity_verdict=verdict,
        identity_verdict_label=VERDICT_LABELS.get(verdict, verdict),
        identity_gate_blocked=bool(run_row["identity_blocked"]),
        identity_reason=_text(run_row["identity_reason"]),
        automatic_pairs=int(run_row["automatic_pairs"]),
        total_findings=int(run_row["total_findings"]),
        requiring_review=requiring,
        by_type=dict(run_row.get("by_type") or {}),
        by_flag=dict(run_row.get("by_flag") or {}),
        key_version=str(run_row["key_version"]),
        matching_version=str(run_row["matching_version"]),
        compare_version=str(run_row["compare_version"]),
        service_version=str(run_row["service_version"]),
    )
    findings = tuple(
        FindingView(
            finding_id=_text(r["finding_id"]),
            identity_basis=_text(r["identity_basis"]),
            side=_text(r["side"]),
            finding_type=_text(r["finding_type"]),
            type_label=TYPE_LABELS.get(r["finding_type"], _text(r["finding_type"])),
            requires_human_decision=bool(r["requires_review"]),
            flags=tuple(_text(x) for x in r["flags"]),
            flag_labels=tuple(FLAG_LABELS.get(x, _text(x)) for x in r["flags"]),
            comparison_axis=_text(r["comparison_axis"]),
            fiscal_year=r["fiscal_year"],
            budget_category=_text(r["budget_category"]) or None,
            row_label=_text(r["row_label"]),
            sheet_role=_text(r["sheet_role"]),
            section_title=_text(r["section_title"]),
            parent_plan=_text(r["parent_plan"]),
            declared_unit=_text(r["declared_unit"]),
            baseline_value=_text(r["baseline_value"]),
            current_value=_text(r["current_value"]),
            difference=_text(r["difference"]),
            baseline_category_table_year=r["baseline_table_year"],
            current_category_table_year=r["current_table_year"],
            baseline=_location_from_row(r["baseline_location"]),
            current=_location_from_row(r["current_location"]),
            detail=_text(r["detail"]),
        )
        for r in finding_rows
    )
    return T1BRunView(summary=summary, findings=findings)


def load_run(run_id: str, *, db_path=None) -> T1BRunView | None:
    """อ่านรอบหนึ่งจากที่เก็บแล้วคืน projection — ทางเข้าเดียวที่ route ใช้"""
    from ..storage import t1b_repo

    row = t1b_repo.get_run(run_id, db_path)
    if row is None:
        return None
    return view_from_storage(row, t1b_repo.list_findings(run_id, db_path))


def run_from_records(baseline, current, *, run_id: str) -> T1BRunView:
    """เดินเครื่องยนต์ครบสามชั้นจาก record สองฝั่ง แล้วคืน projection

    ทางเข้านี้ **ไม่รับเส้นทางไฟล์** โดยเจตนา — ทดสอบได้ด้วย fixture สังเคราะห์
    ล้วน ๆ และไม่มีทางเผลอเปิดแฟ้มจริงระหว่างเทสต์ ·
    ถ้าต้องอ่านจากไฟล์จริงให้ใช้ :func:`run_from_workbooks`
    """
    return project_run(compare(match_records(baseline, current)), run_id=run_id)


# ══════════════════════════════════════════════════════════════════════════════
#  จำแนกไฟล์ก่อนเทียบ — แยก "ไฟล์ผิดประเภท" ออกจาก "แถวใน AO ที่ยังจับคู่ไม่ได้"
# ══════════════════════════════════════════════════════════════════════════════

#: อ่านแฟ้มไม่ได้เลย — เสียหาย เปิดไม่ออก หรือเป็นชนิดที่ยังไม่รองรับ
CLS_NOT_READABLE = "WORKBOOK_NOT_READABLE"
#: เปิดได้ แต่ **ไม่พบหลักฐานว่าเป็นแฟ้ม AO** — ไม่ควรสร้างข้อสังเกตตามปกติ
CLS_UNSUPPORTED = "UNSUPPORTED_WORKBOOK"
#: เปิดได้ มีเค้าของ AO แต่หลักฐานไม่พอจะตัดสิน — ต้องให้คนบอกว่าเป็นแฟ้มอะไร
CLS_NEEDS_CLASSIFICATION = "NEEDS_FILE_CLASSIFICATION"
#: เป็นแฟ้ม AO — แถวที่จับคู่ไม่ได้ในนี้จึงใช้ ``UNMAPPED`` ได้อย่างถูกความหมาย
CLS_AO = "AO_WORKBOOK"

CLASSIFICATION_LABELS = {
    CLS_NOT_READABLE: "อ่านแฟ้มไม่ได้",
    CLS_UNSUPPORTED: "ไม่ใช่แฟ้มคาดแดง AO",
    CLS_NEEDS_CLASSIFICATION: "ยังตัดสินไม่ได้ว่าเป็นแฟ้มอะไร",
    CLS_AO: "เป็นแฟ้มคาดแดง AO",
}


@dataclass(frozen=True)
class WorkbookClassification:
    """ผลการจำแนกหนึ่งแฟ้ม พร้อมตัวนับที่ใช้ตัดสิน — **อธิบายเหตุผลได้เสมอ**"""

    code: str
    mapped_rows: int
    unmapped_rows: int
    ao_signals: tuple[str, ...]

    @property
    def label(self) -> str:
        return CLASSIFICATION_LABELS.get(self.code, self.code)

    @property
    def usable(self) -> bool:
        return self.code == CLS_AO


def classify_workbook(records) -> WorkbookClassification:
    """ตัดสินว่าแฟ้มนี้เป็นแฟ้ม AO หรือไม่ **จากสัญญาณที่เครื่องยนต์ผลิตอยู่แล้ว**

    🔴 คำสั่งกิ๊ฟ (7 ก.ย.) — เดิมแฟ้มอะไรก็รับหมดแล้วออกมาเป็น ``UNMAPPED``
    ทั้งก้อน ผู้ใช้จึงอ่านได้ว่า *"เป็นข้อมูล AO ที่ระบบตรวจแล้ว"*
    ทั้งที่จริงอาจเป็นไฟล์ผิดประเภท · ``UNMAPPED`` ต้องแปลว่า
    **"แถวหนึ่งในแฟ้ม AO ที่ยังจับคู่ไม่ได้"** เท่านั้น ห้ามใช้ปนกับไฟล์ผิดประเภท

    เกณฑ์ — เรียงจากหลักฐานแข็งไปอ่อน

    ``mapped_rows > 0``
        อะแดปเตอร์ตีความโครงสร้าง AO ได้จริงอย่างน้อยหนึ่งแถว ⇒ :data:`CLS_AO`
    ``mapped_rows == 0`` แต่มีสัญญาณ AO
        เช่นมีชีตที่จำแนกเป็นชีตหลัก หรืออ่านบทบาทของชีตออก
        ⇒ :data:`CLS_NEEDS_CLASSIFICATION` — **ห้ามเดาไปทางใดทางหนึ่ง**
    ``mapped_rows == 0`` และไม่มีสัญญาณเลย
        ⇒ :data:`CLS_UNSUPPORTED`

    เกณฑ์นี้อยู่ที่ **ชั้นบริการ** ไม่ใช่ในอะแดปเตอร์ เพราะเป็นนโยบายของ
    ผลิตภัณฑ์ว่าจะรับแฟ้มแบบใดมาเทียบ ไม่ใช่ข้อเท็จจริงเรื่องการอ่านไฟล์
    อะแดปเตอร์ยังคงหน้าที่เดิมคือ **ประกาศความไม่แน่ใจ ไม่ปฏิเสธ**
    """
    from ..t1b.records import ROW_KIND_STRUCTURAL, ROW_KIND_VALUE
    from ..t1b.roles import SHEET_CLASS_MAIN

    mapped = unmapped = 0
    signals: set[str] = set()
    for rec in records:
        if rec.row_kind in (ROW_KIND_VALUE, ROW_KIND_STRUCTURAL):
            mapped += 1
        else:
            unmapped += 1
        if getattr(rec, "sheet_class", "") == SHEET_CLASS_MAIN:
            signals.add("main_sheet_detected")
        if rec.key.sheet_role:
            signals.add("sheet_role_resolved")
        if rec.key.section_title_norm:
            signals.add("section_title_present")

    if mapped:
        code = CLS_AO
    elif signals:
        code = CLS_NEEDS_CLASSIFICATION
    else:
        code = CLS_UNSUPPORTED
    return WorkbookClassification(code=code, mapped_rows=mapped,
                                  unmapped_rows=unmapped,
                                  ao_signals=tuple(sorted(signals)))


# ══════════════════════════════════════════════════════════════════════════════
#  ทางเข้าเดียวจากเว็บสำหรับการเปิดไฟล์
# ══════════════════════════════════════════════════════════════════════════════


class WorkbookRejected(Exception):
    """แฟ้มนี้ใช้เทียบไม่ได้ — พร้อม **ข้อความที่แสดงต่อผู้ใช้ได้เลย**

    🔴 เก็บข้อความสองชั้นแยกกันโดยเจตนา

    * :attr:`user_message` — ผู้ใช้เห็น · ไม่มีเส้นทางไฟล์ ไม่มีชื่อคลาสข้อยกเว้น
    * :attr:`detail` — ลงล็อกเท่านั้น · ผ่านการกลบเส้นทางแล้ว

    เพราะข้อความจาก ``openpyxl`` มักมีเส้นทางไฟล์เต็มติดมาด้วย

    :attr:`code` เป็นรหัสคงที่สำหรับล็อกและชุดทดสอบ — ห้ามแปลเป็นภาษาไทย
    """

    #: รหัสประจำสาเหตุ — คลาสลูกกำหนดทับ
    code = CLS_NOT_READABLE

    def __init__(self, user_message: str, detail: str = "",
                 classification: "WorkbookClassification | None" = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = privacy.redact_text(detail)
        self.classification = classification


class WorkbookNotReadable(WorkbookRejected):
    """เปิดแฟ้มไม่ได้เลย — เสียหาย ชนิดไม่รองรับ หรืออ่านแล้วไม่ได้อะไรเลย"""

    code = CLS_NOT_READABLE


class UnsupportedWorkbook(WorkbookRejected):
    """เปิดได้ แต่ไม่พบหลักฐานว่าเป็นแฟ้ม AO — **ห้ามสร้างข้อสังเกตตามปกติ**"""

    code = CLS_UNSUPPORTED


class WorkbookNeedsClassification(WorkbookRejected):
    """มีเค้าของ AO แต่หลักฐานไม่พอ — ต้องให้คนบอกว่าเป็นแฟ้มอะไรก่อน"""

    code = CLS_NEEDS_CLASSIFICATION


#: นามสกุลที่ชั้นนี้อ่านได้จริง — 🔴 PDF **ยังไม่รองรับ** ต้องบอกผู้ใช้ตรง ๆ
READABLE_SUFFIXES = (".xlsx", ".xlsm")


def read_workbook(path) -> list:
    """อ่านสมุดงานหนึ่งแฟ้มเป็น record — **ทางเดียวที่ route ใช้เปิดไฟล์**

    🔴 route ไม่เรียก adapter เอง เพื่อให้การแปลงข้อผิดพลาดเป็นข้อความที่ปลอดภัย
    เกิดขึ้นที่เดียว ไม่ต้องหวังว่าทุก route จะจำได้

    ยกเป็นคลาสลูกของ :class:`WorkbookRejected` เมื่อแฟ้มใช้เทียบไม่ได้ —
    แต่ละสาเหตุมี :attr:`~WorkbookRejected.code` ของตัวเอง
    """
    from pathlib import Path

    from ..adapters.ao_workbook import AOWorkbookAdapter
    from ..holdout import assert_not_holdout
    from ..sealed_key import assert_not_sealed

    p = Path(path)
    # 🔴 ด่านกันชุดกันข้อมูล P1 — ต้องอยู่ **ก่อน** ทุกบรรทัดที่แตะไฟล์
    assert_not_holdout(p)
    # 🔴 ด่านกันการเผลออ่านเฉลย (accidental sealed-key ingestion guard · ไม่ใช่ access control)
    # — Bo รับเป็น approved lane exception (`5597645315` ข้อ 8) · ก่อนแตะไฟล์เช่นกัน
    assert_not_sealed(p)

    if p.suffix.lower() not in READABLE_SUFFIXES:
        raise WorkbookNotReadable(
            "ระบบยังเปรียบเทียบได้เฉพาะไฟล์ Excel (.xlsx/.xlsm) — "
            "ไฟล์ PDF ยังไม่รองรับในขั้นนี้",
            f"unsupported suffix {p.suffix!r}")
    try:
        records = [e.canonical_record for e in AOWorkbookAdapter().extract(p)]
    except Exception as exc:                       # noqa: BLE001 — ต้องกันทุกชนิด
        raise WorkbookNotReadable(
            "เปิดไฟล์นี้เป็นสมุดงานคาดแดงไม่สำเร็จ "
            "โปรดตรวจว่าเป็นแฟ้ม AO ที่ยังไม่เสียหาย",
            f"{type(exc).__name__}: {exc}") from exc

    if not records:
        raise WorkbookNotReadable(
            "อ่านไฟล์ได้ แต่ไม่พบรายการใดในสมุดงาน "
            "โปรดตรวจว่าเป็นแฟ้ม AO ที่ถูกต้อง",
            "adapter returned zero records")

    cls = classify_workbook(records)
    if cls.code == CLS_UNSUPPORTED:
        raise UnsupportedWorkbook(
            "ไฟล์นี้เปิดได้ แต่ไม่พบโครงสร้างของเอกสารคาดแดง AO เลย "
            "ระบบจึงไม่นำมาเปรียบเทียบ เพื่อไม่ให้เข้าใจผิดว่าตรวจแล้วไม่พบอะไร "
            "โปรดตรวจว่าเลือกไฟล์ถูกแฟ้ม",
            f"{cls.code} mapped={cls.mapped_rows} unmapped={cls.unmapped_rows}",
            cls)
    if cls.code == CLS_NEEDS_CLASSIFICATION:
        raise WorkbookNeedsClassification(
            "ไฟล์นี้พอมีเค้าของเอกสารคาดแดง แต่ยังไม่มีแถวใดที่ระบบตีความได้ "
            "จึงยังตัดสินไม่ได้ว่าเป็นแฟ้ม AO หรือแฟ้มชนิดอื่น "
            "โปรดยืนยันว่าเป็นแฟ้มอะไร หรือเลือกไฟล์ฉบับเต็ม",
            f"{cls.code} signals={','.join(cls.ao_signals)} "
            f"unmapped={cls.unmapped_rows}",
            cls)
    return records


def run_from_workbooks(baseline_path, current_path, *, run_id: str) -> T1BRunView:
    """อ่านสมุดงานสองแฟ้มแล้วเดินเครื่องยนต์ครบสามชั้น

    ``baseline_path`` = ฉบับตั้งต้น (ก่อนปรับลด) · ``current_path`` = ฉบับที่นำมาตรวจ

    🔴 ยกเป็น :class:`WorkbookNotReadable` เมื่ออ่านไม่ได้ — ผู้เรียกต้องจับ
    และแสดง :attr:`~WorkbookNotReadable.user_message` เท่านั้น
    **ห้ามแสดงข้อความดิบของข้อยกเว้นต้นทาง**
    """
    baseline = read_workbook(baseline_path)
    current = read_workbook(current_path)
    return run_from_records(baseline, current, run_id=run_id)


__all__ = [
    "SERVICE_VERSION", "READY", "REVIEW_REQUIRED", "CANNOT_DETERMINE",
    "READINESS_LABELS", "TYPE_LABELS", "FLAG_LABELS", "VERDICT_LABELS",
    "SIDE_PAIR", "SIDE_BASELINE_ONLY", "SIDE_CURRENT_ONLY", "SIDE_NONE",
    "SIDE_LABELS", "BASIS_CONTENT", "BASIS_POSITION",
    "LocationView", "FindingView", "RunSummaryView", "T1BRunView", "QueuePage",
    "ReconcileRow", "Reconciliation", "reconcile",
    "FindingDetail", "readiness_of", "finding_id_of", "side_of",
    "project_finding",
    "project_run", "filter_findings", "queue_page", "finding_detail",
    "filter_query",
    "view_from_storage", "load_run", "run_from_records",
    "run_from_workbooks", "read_workbook",
    "WorkbookRejected", "WorkbookNotReadable", "UnsupportedWorkbook",
    "WorkbookNeedsClassification",
    "classify_workbook", "WorkbookClassification", "CLASSIFICATION_LABELS",
    "CLS_AO", "CLS_UNSUPPORTED", "CLS_NEEDS_CLASSIFICATION", "CLS_NOT_READABLE",
    "READABLE_SUFFIXES", "DEFAULT_PER_PAGE", "MAX_PER_PAGE",
]
