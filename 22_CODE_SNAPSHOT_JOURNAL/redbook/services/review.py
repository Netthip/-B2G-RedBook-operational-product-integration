# -*- coding: utf-8 -*-
"""คิวตรวจและคำตัดสินแบบกลุ่ม — ชั้นบริการเหนือ :mod:`decisions` และ :mod:`categories`

🔴 **คำสั่งกิ๊ฟ (7 ก.ย. 2569 · ข้อ D)**

* pagination ฝั่ง server · กรองตามหมวด/ชนิด/สถานะคำตัดสิน/ต้องให้คนตรวจ · ค้นหา
* เลือกเฉพาะรายการในหน้าปัจจุบัน · "เลือกทั้งหมดตามตัวกรอง" เป็นคำสั่งแยกพร้อม
  **จำนวนที่แน่นอน** ก่อนยืนยัน
* bulk ได้เฉพาะ ``CONFIRMED`` และ ``DISMISSED`` (บังคับเหตุผล) —
  **ห้าม** bulk ``CONFIRMED_WITH_EDIT`` / ``UNRESOLVED`` เพราะต้องพิจารณารายละเอียด
* ทุกรายการใน bulk สร้างคำตัดสินและ audit **แยกราย finding** ไม่ใช่ก้อนเดียว
* stale conflict บางรายการ ⇒ รายงานสำเร็จ/ไม่สำเร็จแยกชัด **ห้ามบอกว่าสำเร็จทั้งหมด**
* ห้ามมี "ยืนยันทั้งหมด 1,577 รายการ" คลิกเดียวโดยไม่มีการเลือกหรือทบทวน

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from . import categories, decisions
from .t1b import (DEFAULT_PER_PAGE, MAX_PER_PAGE, FindingView, T1BRunView,
                  _percent_encode)

REVIEW_SERVICE_VERSION = "t1b-review-0.1.0"

#: สถานะที่กรองได้ในคิว — รวม ``PENDING`` ซึ่งไม่มีแถวในตาราง
QUEUE_STATUSES = (decisions.PENDING, decisions.CONFIRMED,
                  decisions.CONFIRMED_WITH_EDIT, decisions.UNRESOLVED,
                  decisions.DISMISSED)

#: สถานะที่อนุญาตให้ตัดสินเป็นกลุ่ม — อีกสองสถานะต้องทีละรายการ
BULK_ALLOWED = (decisions.CONFIRMED, decisions.DISMISSED)

#: เพดานจำนวนต่อหนึ่งคำสั่งกลุ่ม — กันคลิกเดียวกวาดทั้งรอบโดยไม่ทบทวน
BULK_MAX = 500

#: ชนิดที่เครื่องยนต์ **ตรวจพบความเปลี่ยนแปลงจริง** — ไม่รวม *เท่าเดิม*
#: และไม่รวมชนิดระดับการเทียบ (เทียบไม่ได้/ตีความไม่ได้/ยัง map ไม่ได้)
#: ซึ่งยังไม่ได้บอกว่ามีอะไรเปลี่ยน
CHANGE_DETECTED_TYPES = frozenset({
    "AMOUNT_INCREASED", "AMOUNT_DECREASED", "INDICATOR_CHANGED",
    "ROW_ADDED", "ROW_REMOVED", "UNIT_CHANGED", "PROJECT_ORDINAL_CHANGED",
})


@dataclass(frozen=True)
class Annotation:
    """สิ่งที่คิวต้องรู้เพิ่มจาก :class:`FindingView` — สถานะ · seq ล่าสุด · หมวด"""

    status: str
    latest_seq: int
    subject: categories.SubjectClassification
    latest: object = None          # DecisionView ล่าสุด หรือ None

    @property
    def status_label(self) -> str:
        return decisions.STATUS_LABELS.get(self.status, self.status)


def status_map(run_id: str, db_path=None) -> dict:
    """``{finding_id: DecisionView ล่าสุด}`` — finding ที่ไม่มีคือ ``PENDING``"""
    from ..storage import t1b_decisions as repo

    return repo.latest_by_finding(run_id, db_path=db_path)


def annotate(view: T1BRunView, smap: dict) -> dict:
    """คำนวณ :class:`Annotation` ให้ทุก finding ในรอบ — **ฟังก์ชันบริสุทธิ์**"""
    out = {}
    for f in view.findings:
        latest = smap.get(f.finding_id)
        out[f.finding_id] = Annotation(
            status=latest.status_to if latest else decisions.PENDING,
            latest_seq=latest.seq if latest else 0,
            subject=categories.classify_subject(f),
            latest=latest,
        )
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  ตัวกรองและหน้า
# ══════════════════════════════════════════════════════════════════════════════

def _norm(q: str) -> str:
    return unicodedata.normalize("NFC", (q or "").strip()).casefold()


def filter_findings(view: T1BRunView, ann: dict, *, query: str = "",
                    flags=(), types=(), only_review: bool = False,
                    categories_: tuple = (), statuses: tuple = ()
                    ) -> tuple[FindingView, ...]:
    """คัดกรองตามทุกแกนที่กิ๊ฟกำหนด — ค้นหาแบบ **ทุกคำต้องพบครบ** ไม่ fuzzy"""
    want_flags = frozenset(flags or ())
    want_types = frozenset(types or ())
    want_cats = frozenset(categories_ or ())
    want_status = frozenset(statuses or ())
    terms = [t for t in _norm(query).split() if t]

    out = []
    for f in view.findings:
        a = ann[f.finding_id]
        if only_review and not f.requires_human_decision:
            continue
        if want_types and f.finding_type not in want_types:
            continue
        if want_flags and not want_flags.intersection(f.flags):
            continue
        if want_cats and a.subject.category not in want_cats:
            continue
        if want_status and a.status not in want_status:
            continue
        if terms:
            hay = unicodedata.normalize("NFC", f.search_text).casefold()
            if not all(t in hay for t in terms):
                continue
        out.append(f)
    return tuple(out)


@dataclass(frozen=True)
class ReviewPage:
    items: tuple[FindingView, ...]
    page: int
    per_page: int
    total: int
    query: str = ""
    flags: tuple = ()
    types: tuple = ()
    only_review: bool = False
    categories_: tuple = ()
    statuses: tuple = ()

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


def review_page(view: T1BRunView, ann: dict, *, page: int = 1,
                per_page: int = DEFAULT_PER_PAGE, **filters) -> ReviewPage:
    per_page = max(1, min(int(per_page or DEFAULT_PER_PAGE), MAX_PER_PAGE))
    matched = filter_findings(view, ann, **filters)
    total = len(matched)
    pages = max(1, -(-total // per_page))
    page = max(1, min(int(page or 1), pages))
    start = (page - 1) * per_page
    return ReviewPage(items=matched[start:start + per_page], page=page,
                      per_page=per_page, total=total,
                      query=filters.get("query", ""),
                      flags=tuple(filters.get("flags") or ()),
                      types=tuple(filters.get("types") or ()),
                      only_review=bool(filters.get("only_review")),
                      categories_=tuple(filters.get("categories_") or ()),
                      statuses=tuple(filters.get("statuses") or ()))


# ══════════════════════════════════════════════════════════════════════════════
#  ตัวนับบนหน้าคิว — แปดตัวตามที่กิ๊ฟกำหนด
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class QueueCounts:
    total: int
    change_detected: int
    requiring_review: int
    confirmed: int
    confirmed_with_edit: int
    unresolved: int
    dismissed: int
    pending: int
    by_category: dict = field(default_factory=dict)

    @property
    def decided(self) -> int:
        return self.confirmed + self.confirmed_with_edit + self.unresolved + self.dismissed

    @property
    def balanced(self) -> bool:
        """สี่สถานะ + รอตัดสิน ต้องรวมเท่ากับทั้งหมดเสมอ"""
        return self.decided + self.pending == self.total


def counts(view: T1BRunView, ann: dict) -> QueueCounts:
    st = {s: 0 for s in QUEUE_STATUSES}
    by_cat = {c: 0 for c in categories.CATEGORY_ORDER}
    changed = review = 0
    for f in view.findings:
        a = ann[f.finding_id]
        st[a.status] = st.get(a.status, 0) + 1
        by_cat[a.subject.category] = by_cat.get(a.subject.category, 0) + 1
        changed += int(f.finding_type in CHANGE_DETECTED_TYPES)
        review += int(f.requires_human_decision)
    return QueueCounts(
        total=len(view.findings), change_detected=changed,
        requiring_review=review,
        confirmed=st[decisions.CONFIRMED],
        confirmed_with_edit=st[decisions.CONFIRMED_WITH_EDIT],
        unresolved=st[decisions.UNRESOLVED],
        dismissed=st[decisions.DISMISSED],
        pending=st[decisions.PENDING],
        by_category=by_cat,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  คำตัดสินแบบกลุ่ม
# ══════════════════════════════════════════════════════════════════════════════

class BulkNotAllowed(decisions.DecisionError):
    """สถานะนี้ต้องตัดสินทีละรายการ"""


@dataclass(frozen=True)
class BulkOutcome:
    finding_id: str
    ok: bool
    reason: str = ""
    seq: int = 0


@dataclass(frozen=True)
class BulkResult:
    status: str
    requested: int
    outcomes: tuple[BulkOutcome, ...]

    @property
    def succeeded(self) -> tuple[BulkOutcome, ...]:
        return tuple(o for o in self.outcomes if o.ok)

    @property
    def failed(self) -> tuple[BulkOutcome, ...]:
        return tuple(o for o in self.outcomes if not o.ok)

    @property
    def all_ok(self) -> bool:
        return not self.failed and self.requested == len(self.succeeded)


def validate_bulk(status: str, note: str, n: int) -> str:
    if status not in BULK_ALLOWED:
        raise BulkNotAllowed(
            f"สถานะ “{decisions.STATUS_LABELS.get(status, status)}” "
            "ต้องตัดสินทีละรายการ เพราะต้องพิจารณารายละเอียดของแต่ละใบ")
    if n <= 0:
        raise decisions.DecisionError("ยังไม่ได้เลือกรายการใด")
    if n > BULK_MAX:
        raise decisions.DecisionError(
            f"เลือกได้ไม่เกิน {BULK_MAX} รายการต่อครั้ง — แบ่งเป็นหลายรอบเพื่อให้ทบทวนได้")
    note = (note or "").strip()
    if status == decisions.DISMISSED and not note:
        raise decisions.DecisionError(
            "การตัดสินเป็นกลุ่มว่า “ไม่ใช่ประเด็นที่ต้องแก้” ต้องระบุเหตุผลร่วม")
    return note


def bulk_decide(view: T1BRunView, finding_ids, status: str, *, note: str = "",
                expected_seqs: dict, decided_by: str = "local-user",
                db_path=None) -> BulkResult:
    """ตัดสินหลายรายการ — **หนึ่งคำตัดสิน หนึ่ง audit ต่อหนึ่ง finding**

    ``expected_seqs`` — ``{finding_id: seq ที่หน้าจอเห็น}`` · รายการที่ไม่มีค่า
    ถือว่า ``0`` ซึ่งจะชนกับ stale guard ถ้าใครตัดสินไปก่อน — **ตั้งใจ**

    ไม่หยุดเมื่อบางรายการล้ม — ทำต่อจนครบ แล้วรายงานสำเร็จ/ไม่สำเร็จแยกราย
    รายการ · ห้ามรายงานว่าสำเร็จทั้งหมดถ้ามีแม้หนึ่งรายการล้ม
    """
    ids = list(dict.fromkeys(str(x) for x in finding_ids if x))
    note = validate_bulk(status, note, len(ids))
    outcomes = []
    for fid in ids:
        f = view.by_id(fid)
        if f is None:
            outcomes.append(BulkOutcome(fid, False, "ไม่พบรายการนี้ในรอบ"))
            continue
        try:
            d = decisions.record(
                view, f, status, note=note,
                expected_latest_seq=int(expected_seqs.get(fid, 0)),
                decided_by=decided_by, db_path=db_path)
            outcomes.append(BulkOutcome(fid, True, seq=d.seq))
        except decisions.StaleDecisionError as e:
            outcomes.append(BulkOutcome(fid, False, f"stale: {e}"))
        except decisions.NoChangeDecision:
            outcomes.append(BulkOutcome(fid, False, "สถานะเดิมอยู่แล้ว ไม่บันทึกซ้ำ"))
        except decisions.DecisionError as e:
            outcomes.append(BulkOutcome(fid, False, str(e)))
    return BulkResult(status=status, requested=len(ids), outcomes=tuple(outcomes))


def query_string(*, query: str = "", flags=(), types=(), only_review=False,
                 categories_=(), statuses=(), page: int = 1,
                 per_page: int = DEFAULT_PER_PAGE) -> str:
    """query string ของคิว — ประกอบที่ชั้นบริการ ไม่ใช่ใน Jinja"""
    parts = []
    if query:
        parts.append("q=" + _percent_encode(query))
    parts += ["ftype=" + _percent_encode(x) for x in types or ()]
    parts += ["flag=" + _percent_encode(x) for x in flags or ()]
    parts += ["cat=" + _percent_encode(x) for x in categories_ or ()]
    parts += ["status=" + _percent_encode(x) for x in statuses or ()]
    if only_review:
        parts.append("only_review=1")
    parts.append(f"page={max(1, int(page or 1))}")
    parts.append(f"per_page={int(per_page or DEFAULT_PER_PAGE)}")
    return "&".join(parts)


__all__ = [
    "REVIEW_SERVICE_VERSION", "query_string", "QUEUE_STATUSES", "BULK_ALLOWED", "BULK_MAX",
    "CHANGE_DETECTED_TYPES", "Annotation", "status_map", "annotate",
    "filter_findings", "ReviewPage", "review_page", "QueueCounts", "counts",
    "BulkNotAllowed", "BulkOutcome", "BulkResult", "validate_bulk",
    "bulk_decide",
]
