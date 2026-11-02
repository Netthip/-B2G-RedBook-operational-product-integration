# -*- coding: utf-8 -*-
"""ทดลองตรวจเล่มสำหรับผู้ปฏิบัติงาน (#43) — วงจุดต่างบนภาพหน้าเหมือนตรวจบนกระดาษ แล้วเทียบกับระบบ

ลำดับ (กันเห็นผลระบบก่อน):

1. เลือกเล่มทดสอบ (รายการจากไฟล์ตั้งค่า ``trial_books.json`` บนชั้นเล่มของเครื่องนั้น — ใช้จริงต้องอัปโหลดเอง)
2. อ่านคำชี้แจง → วงจุดบนภาพหน้าฉบับปัจจุบัน (เปิดฉบับก่อนเทียบได้) ด้วยปากกา
   แดง = สำคัญ · น้ำตาล = สังเกตเห็นแต่สำคัญน้อยกว่า · หมุด = ของที่หายไป · กด "ตรวจหน้านี้แล้ว" ทีละหน้า
3. ส่งผลตรวจ = ล็อก (แก้จุดไม่ได้) → **ระบบเพิ่งเทียบตอนนี้** (ไม่มีรอบเทียบก่อนล็อก)
4. ระบบเสนอคู่ จุดที่วง ↔ ข้อสังเกต จากหน้า/ตำแหน่ง · ผู้ตรวจยืนยันทีละคู่ตามวิธีนับของโปรโตคอล
   (พบตรง · พบบางส่วน · ไม่ใช่จุดเดียวกัน) และจัดข้อที่ระบบยกเพิ่ม (ต่างจริงแต่ไม่ได้จด · ไม่ใช่ความต่าง · ยังตัดสินไม่ได้)
5. แบบสอบถามหน้าเดียว → แดชบอร์ด → ส่งออกสรุปเฉพาะจำนวน

🔴 ระบบไม่ตัดสินแทนผู้ตรวจ — การจับคู่เป็นข้อเสนอเท่านั้น · ข้อมูลประกอบของระบบไม่นับเป็นแจ้งเกิน ·
ความพึงพอใจใช้ประกอบเท่านั้น ไม่แทนผลการตรวจจับ · ไม่อ้างเรื่องประหยัดเวลา
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from ..pdfbook import PDFBOOK_VERSION, profile as prof, reader
from ..pdfbook import compare as cmp
from ..storage import trial_repo
from . import pdfpair, pdfshelf

TRIAL_ENV = "REDBOOK_TRIAL_BOOKS"
TRIAL_VERSION = "trial-0.1.0"
PROTOCOL_VERSION = "pdfpair-protocol-0.1 (ร่าง)"
PAGE_ZOOM = 1.5

PENS = {"red": "ปากกาแดง — สำคัญ", "brown": "ปากกาน้ำตาล — สังเกตเห็น สำคัญน้อยกว่า", "pin": "หมุด — ของที่หายไป"}
SIDES = {"cur": "ฉบับปัจจุบัน", "prev": "ฉบับก่อน"}
#: หัวข้อตามโปรโตคอล (รหัส ก–ญ)
TOPIC_CODES = (("ก", "ยอดรวม/หมวดงบ"), ("ข", "ประจำ/ลงทุน"), ("ค", "แผนงาน ผลผลิต โครงการ กิจกรรม"),
               ("ง", "รายการเสนอตั้ง"), ("จ", "วงเงินโครงการ/ผูกพัน"), ("ฉ", "ประมาณการล่วงหน้า"),
               ("ช", "ตัวชี้วัด/เป้าหมาย/หน่วยนับ"), ("ซ", "วิสัยทัศน์ พันธกิจ ผลสัมฤทธิ์"),
               ("ฌ", "เลขข้อ หัวตาราง หน่วยตาราง"), ("ญ", "ความสอดคล้องภายในเล่ม"))
TOPIC_LABELS = dict(TOPIC_CODES)
LINK_VERDICTS = {"exact": "พบตรง", "partial": "พบบางส่วน", "not_same": "ระบบไม่ได้ยกจุดนี้"}
EXTRA_VERDICTS = {"real_unnoted": "ต่างจริง แต่ฉันไม่ได้วง", "not_diff": "ไม่ใช่ความต่าง",
                  "undecided": "ยังตัดสินไม่ได้"}
#: แบบสอบถามหลังใช้ (ตามฉบับเอกสาร 03_ + ข้อเรื่องขั้นตอนของหน้าทดลอง) · 1–5 = ไม่เห็นด้วยอย่างยิ่ง … เห็นด้วยอย่างยิ่ง
LIKERT_ITEMS = (
    ("ประโยชน์", (("q1_1", "รายการข้อสังเกตช่วยให้ฉันเห็นจุดที่ต่างซึ่งอาจพลาดเมื่อตรวจด้วยตา"),
                  ("q1_2", "ระบบยกสิ่งที่ไม่ใช่ความต่างจริงขึ้นมามากจนรบกวน"),
                  ("q1_3", "การแยกหัวข้อ (เงิน ตัวชี้วัด ข้อความ รูปแบบ) ตรงกับวิธีที่ฉันตรวจ"))),
    ("ความเข้าใจหลักฐาน", (("q2_1", "ภาพหน้า PDF ฉบับ A | B พร้อมกรอบเน้น ทำให้ฉันยืนยันได้ว่าความต่างมีอยู่จริง"),
                           ("q2_2", "ฉันยังต้องเปิดเล่มเองเกือบทุกข้อ เพราะหลักฐานในระบบไม่พอ"),
                           ("q2_3", "ฉันแยกได้ว่าข้อใด \"ระบบไม่พบ\" และข้อใด \"ระบบอ่านไม่ได้\""))),
    ("ภาระงาน", (("q3_1", "การนำไฟล์เข้าและอ่านผลเพิ่มภาระมากกว่าที่ช่วยลด"),
                 ("q3_2", "จำนวนข้อสังเกตที่ต้องตัดสินอยู่ในระดับที่ทำได้จริง"))),
    ("ความต้องการใช้ต่อ", (("q4_1", "หากมีระบบนี้ ฉันจะใช้ประกอบการตรวจเล่มของตนเองหรือของผู้อื่น"),
                           ("q4_2", "ระบบนี้น่าจะเป็นประโยชน์ต่อผู้ปฏิบัติงานในตำแหน่งเดียวกับฉัน"))),
    ("ขั้นตอนของหน้าทดลอง", (("q6_1", "ขั้นตอนในหน้าทดลองเข้าใจได้โดยไม่ต้องมีคนอธิบาย"),
                             ("q6_2", "การวงจุดบนภาพหน้าใกล้เคียงกับการตรวจบนกระดาษที่ฉันทำอยู่"))),
)
OPEN_ITEMS = (("o5_1", "ประเด็นที่ระบบพลาดและท่านเห็นว่าสำคัญที่สุด (ลักษณะทั่วไป)"),
              ("o5_2", "สิ่งที่ระบบอาจทำให้ผู้ใช้สรุปผิด หรือควรระวัง"),
              ("o6_3", "ขั้นตอนไหนยาก หรืออยากให้ปรับอะไร"),
              ("o5_3", "ข้อเสนอแนะอื่น"))
#: ระยะที่ยอมให้จุดที่วงห่างจากกรอบของข้อสังเกต (pt) — ใช้เสนอคู่เท่านั้น คนยืนยันเสมอ
MATCH_X_PT, MATCH_Y_PT = 40.0, 14.0


class TrialError(ValueError):
    pass


@dataclass(frozen=True)
class TrialBook:
    id: str
    title: str
    agency: str
    pair: str               # ป้ายคู่ เช่น "ร่าง พ.ร.บ. ↔ พ.ร.บ."
    current: str            # รหัสเล่มบนชั้น (ฉบับที่ตรวจเป็นหลัก = B)
    previous: str           # รหัสเล่มบนชั้น (ฉบับที่เปิดเทียบได้ = A)


def books_file() -> Path:
    return Path(os.environ.get(TRIAL_ENV) or (pdfshelf.shelf_dir() / "trial_books.json"))


def books() -> list[TrialBook]:
    """เล่มทดสอบที่ใช้ได้ (ไฟล์ตั้งค่าของเครื่องนี้) — เล่มที่ไม่อยู่บนชั้น/หน่วยงานที่กันไว้ = ไม่แสดง"""
    try:
        raw = json.loads(books_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    have = {v.key for v in pdfshelf.volumes()}
    out = []
    for b in raw.get("books", []):
        tb = TrialBook(str(b.get("id", "")), str(b.get("title", "")), str(b.get("agency", "")),
                       str(b.get("pair", "")), str(b.get("current", "")), str(b.get("previous", "")))
        if tb.id and tb.agency and tb.current in have and tb.previous in have \
                and not pdfshelf.is_protected(tb.agency):
            out.append(tb)
    return out


def get_book(book_id: str) -> TrialBook | None:
    return next((b for b in books() if b.id == book_id), None)


def _rank(s: dict) -> tuple:
    """รอบที่ควรพากลับไป: กำลังทำและมีงานแล้ว (จุด/หน้าที่ตรวจ) > ส่งผลแล้ว > รอบว่าง · เท่ากัน = ใหม่กว่า"""
    work = len(trial_repo.marks(s["id"])) + len(trial_repo.pages_done(s["id"]))
    level = 1 if s["locked_at"] else (2 if work else 0)
    return (level, s["started_at"])


def current_session(book_id: str) -> dict | None:
    ss = [s for s in trial_repo.sessions() if s["book_id"] == book_id]
    return max(ss, key=_rank) if ss else None


def book_status() -> dict:
    """book_id → รอบที่ควรพากลับไป (``draft`` กำลังตรวจ · ``locked`` ส่งผลแล้ว) — รอบว่างที่เปิดทีหลังไม่บังงานเดิม"""
    out: dict = {}
    for bid in {s["book_id"] for s in trial_repo.sessions()}:
        s = current_session(bid)
        out[bid] = {"sid": s["id"], "state": "locked" if s["locked_at"] else "draft"}
    return out


# ── เริ่มตรวจ ──────────────────────────────────────────────────────────────────
def start(book_id: str, reviewer: str = "", again: bool = False) -> str:
    """เริ่มตรวจ — ถ้าเล่มนี้มีรอบอยู่แล้ว **พากลับไปรอบเดิม** (ไม่สร้างรอบว่างทับงานเดิม) ·
    ``again=True`` = ผู้ตรวจขอเริ่มรอบใหม่เอง (รอบเดิมยังเก็บไว้)"""
    b = get_book(book_id)
    if b is None:
        raise TrialError("ไม่พบเล่มทดสอบที่เลือก")
    if not again:
        cur = current_session(book_id)
        if cur is not None:
            return cur["id"]
    sides = {}
    for side, key in (("cur", b.current), ("prev", b.previous)):
        v = pdfshelf.get(key)
        sc, _read = pdfshelf.toc_scope(v, b.agency)
        sides[side] = {"key": key, "title": v.title, "fiscal_year": v.fiscal_year, "stage": v.stage,
                       "sha256": v.sha256, "first": sc.first, "last": sc.last}
    rec = {"id": b.id, "title": b.title, "agency": b.agency, "pair": b.pair, **sides}
    sid = trial_repo.create_session(b.id, (reviewer or "").strip(), rec)
    warm(rec)
    return sid


def warm(book: dict, background: bool = True) -> None:
    """อ่านข้อเท็จจริงของสองเล่มเตรียมไว้ระหว่างที่ผู้ตรวจวง — **ไม่เทียบ ไม่มีข้อสังเกต** (ยังไม่มีผลระบบก่อนล็อก)
    พอส่งผล เหลือแค่เทียบ (เสี้ยววินาที) · ใช้ค่าเดียวกับ :func:`pdfshelf.start` จึงตรงกับที่จำไว้"""
    from ..pdfbook import scope as scope_mod

    def job():
        for side in ("prev", "cur"):
            sd = book[side]
            v = pdfshelf.get(sd["key"])
            if v is None:
                continue
            try:
                pdfpair._facts(v.path, book["agency"], str(sd["first"]), str(sd["last"]), scope_mod.METHOD_TOC)
            except (pdfpair.PairError, OSError, ValueError, reader.ReaderUnavailable):
                continue
    if background:
        import threading
        threading.Thread(target=job, daemon=True).start()
    else:
        job()


@dataclass
class Session:
    rec: dict
    marks: list
    done: set

    @property
    def sid(self) -> str:
        return self.rec["id"]

    @property
    def book(self) -> dict:
        return self.rec["book"]

    @property
    def locked(self) -> bool:
        return bool(self.rec["locked_at"])

    def pages(self, side: str) -> list[int]:
        s = self.book[side]
        return list(range(int(s["first"]), int(s["last"]) + 1))

    @property
    def pending_pages(self) -> list[int]:
        return [p for p in self.pages("cur") if ("cur", p) not in self.done]

    def counts(self) -> dict:
        c = {k: 0 for k in PENS}
        for m in self.marks:
            c[m["pen"]] = c.get(m["pen"], 0) + 1
        return c


def session(sid: str) -> Session | None:
    r = trial_repo.get_session(sid)
    if r is None:
        return None
    return Session(r, trial_repo.marks(sid), trial_repo.pages_done(sid))


def _need(sid: str, unlocked: bool = True) -> Session:
    s = session(sid)
    if s is None:
        raise TrialError("ไม่พบรอบตรวจ")
    if unlocked and s.locked:
        raise TrialError("ส่งผลตรวจแล้ว — แก้จุดที่วงไม่ได้ (ผลเดิมเก็บไว้ตามเดิม)")
    return s


def _side_path(s: Session, side: str) -> Path:
    if side not in SIDES:
        raise TrialError("ฉบับไม่ถูกต้อง")
    v = pdfshelf.get(s.book[side]["key"])
    if v is None:
        raise TrialError("ไม่พบเล่มบนชั้นเล่มของเครื่องนี้")
    pdfshelf.verify(v)
    if v.sha256 != s.book[side]["sha256"]:
        raise TrialError("เล่มบนชั้นไม่ใช่ไฟล์เดียวกับตอนเริ่มตรวจ (SHA-256 ต่างกัน)")
    return v.path


def page_png(sid: str, side: str, page: int) -> bytes | None:
    """ภาพทั้งหน้า — เปิดได้เฉพาะหน้าของหน่วยงานในเล่มนั้น (ไม่เปิดหน้าของหน่วยงานอื่น)"""
    s = _need(sid, unlocked=False)
    if side not in SIDES or page not in s.pages(side):
        return None
    path = _side_path(s, side)
    return pdfpair._png_cached((s.book[side]["sha256"], page, None, True, PAGE_ZOOM),
                               lambda: reader.render_png(path, page, zoom=PAGE_ZOOM))


# ── วงจุด ─────────────────────────────────────────────────────────────────────
def add_mark(sid: str, side: str, page, fx, fy, pen: str) -> dict:
    s = _need(sid)
    if pen not in PENS:
        raise TrialError("เลือกปากกาก่อน")
    try:
        page, fx, fy = int(page), float(fx), float(fy)
    except (TypeError, ValueError):
        raise TrialError("ตำแหน่งไม่ถูกต้อง")
    if side not in SIDES or page not in s.pages(side) or not (0 <= fx <= 1 and 0 <= fy <= 1):
        raise TrialError("ตำแหน่งอยู่นอกหน้าของหน่วยงาน")
    return trial_repo.add_mark(sid, side, page, round(fx, 5), round(fy, 5), pen)


def update_mark(sid: str, mid: str, *, topic=None, note=None, pen=None, delete: bool = False) -> None:
    _need(sid)
    if topic is not None and topic and topic not in TOPIC_LABELS:
        raise TrialError("หัวข้อไม่ถูกต้อง")
    if pen is not None and pen not in PENS:
        raise TrialError("ปากกาไม่ถูกต้อง")
    trial_repo.update_mark(sid, mid, topic=topic, note=(note or "").strip() if note is not None else None,
                           pen=pen, deleted=1 if delete else None)


def page_done(sid: str, side: str, page) -> None:
    s = _need(sid)
    page = int(page)
    if side not in SIDES or page not in s.pages(side):
        raise TrialError("หน้าไม่ถูกต้อง")
    trial_repo.page_done(sid, side, page)


def page_undone(sid: str, side: str, page) -> bool:
    """ยกเลิก "ตรวจหน้านี้แล้ว" (กดพลาด) — ก่อนส่งผลเท่านั้น · "ตรวจหน้านี้แล้ว" = ดูหน้านี้ครบ ไม่ใช่ "ถูกต้อง" ·
    คืน True เมื่อยกเลิกจริง (ยังไม่เคยกด = False ไม่ error)"""
    s = _need(sid)
    try:
        page = int(page)
    except (TypeError, ValueError):
        raise TrialError("หน้าไม่ถูกต้อง")
    if side not in SIDES or page not in s.pages(side):
        raise TrialError("หน้าไม่ถูกต้อง")
    try:
        return trial_repo.page_undone(sid, side, page)
    except TrialError:
        raise
    except ValueError as e:                  # ล็อกแทรกระหว่างทาง — ชั้นที่เก็บตรวจซ้ำในธุรกรรม
        raise TrialError(str(e))


def log_view(sid: str, cur_page, prev_page=0) -> None:
    """บันทึกคู่หน้าที่ผู้ตรวจเปิดเทียบ (ระหว่างตรวจเท่านั้น · หลังส่งผลไม่บันทึก)"""
    s = _need(sid, unlocked=False)
    if s.locked:
        return
    try:
        cur_page, prev_page = int(cur_page), int(prev_page or 0)
    except (TypeError, ValueError):
        raise TrialError("หน้าไม่ถูกต้อง")
    if cur_page not in s.pages("cur") or (prev_page and prev_page not in s.pages("prev")):
        raise TrialError("หน้าไม่ถูกต้อง")
    trial_repo.log_view(sid, cur_page, prev_page)


# ── ล็อก → ระบบเทียบ → เสนอคู่ ─────────────────────────────────────────────────
def lock(sid: str) -> str:
    """ส่งผลตรวจ: ต้องกด "ตรวจหน้านี้แล้ว" ครบทุกหน้าของฉบับปัจจุบัน → ล็อก → ระบบเทียบ → เสนอคู่ → คืน run_id"""
    s = _need(sid)
    if s.pending_pages:
        raise TrialError(f"ยังไม่ได้กด \"ตรวจหน้านี้แล้ว\" อีก {len(s.pending_pages)} หน้า "
                         f"(หน้า {', '.join(map(str, s.pending_pages[:6]))}{' …' if len(s.pending_pages) > 6 else ''})")
    try:
        trial_repo.lock(sid, {"marks": s.counts(), "pages_done": len(s.done),
                              "marks_hash": _marks_hash(s.marks)}, require_pages=s.pages("cur"))
    except TrialError:
        raise
    except ValueError as e:                  # ยกเลิกหน้า/ล็อกซ้ำแทรกระหว่างทาง — ตรวจซ้ำในธุรกรรมเดียวกับการล็อก
        raise TrialError(str(e))
    return ensure_run(sid)


def _marks_hash(marks: list) -> str:
    body = json.dumps([[m["id"], m["side"], m["page"], m["fx"], m["fy"], m["pen"], m["topic"], m["note"]]
                       for m in marks], ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def ensure_run(sid: str) -> str:
    s = _need(sid, unlocked=False)
    if not s.locked:
        raise TrialError("ต้องส่งผลตรวจก่อน ระบบจึงเทียบให้ดู")
    if s.rec["run_id"]:
        return s.rec["run_id"]
    # ระบบเทียบกับไฟล์เดียวกับที่ผู้ตรวจวงไว้เท่านั้น (SHA-256 ที่บันทึกตอนเริ่มตรวจ) — เล่มบนชั้นเปลี่ยน = ไม่เทียบ
    for side in ("prev", "cur"):
        _side_path(s, side)
    pid, rid = pdfshelf.start(s.book["prev"]["key"], s.book["cur"]["key"], s.book["agency"],
                              expect_sha={"A": s.book["prev"]["sha256"], "B": s.book["cur"]["sha256"]})
    trial_repo.attach_run(sid, pid, rid)
    v = pdfpair.view(rid)
    trial_repo.propose_links(sid, {m["id"]: propose(m, v, s) for m in s.marks})
    return rid


def _pt(s: Session, m: dict) -> tuple[float, float]:
    w, h = reader.page_size(_side_path(s, m["side"]), int(m["page"]))
    return m["fx"] * w, m["fy"] * h


def propose(m: dict, v, s: Session) -> str:
    """ข้อสังเกตที่อยู่ใกล้จุดที่วงที่สุดบนหน้าเดียวกัน ("" = ไม่มี) — ข้อเสนอเท่านั้น"""
    x, y = _pt(s, m)
    best, dist = "", None
    for f in v.result.findings:
        if f.info:
            continue
        sd = f.b if m["side"] == "cur" else f.a
        if sd.page != m["page"] or not sd.bbox:
            continue
        x0, y0, x1, y1 = sd.bbox
        if x0 - MATCH_X_PT <= x <= x1 + MATCH_X_PT and y0 - MATCH_Y_PT <= y <= y1 + MATCH_Y_PT:
            d = abs(y - (y0 + y1) / 2) + (0 if x0 <= x <= x1 else 5)
            if dist is None or d < dist:
                best, dist = f.id, d
    return best


# ── ผล ─────────────────────────────────────────────────────────────────────────
@dataclass
class Result:
    s: Session
    view: object                 # pdfpair.RunView
    links: dict
    extras: dict
    answers: dict

    @property
    def actionable(self) -> list:
        return [f for f in self.view.result.findings if not f.info]

    def finding(self, fid: str):
        return self.view.finding(fid) if fid else None

    @property
    def linked_ids(self) -> set:
        # ยืนยันว่าพบ หรือระบบเสนอคู่ไว้และยังไม่ถูกปฏิเสธ — ไม่นับซ้ำเป็น "ระบบยกเพิ่ม"
        return {l["finding_id"] for l in self.links.values()
                if l["finding_id"] and l["verdict"] in ("exact", "partial", "")}

    @property
    def unlinked_findings(self) -> list:
        return [f for f in self.actionable if f.id not in self.linked_ids]

    @property
    def metrics(self) -> dict:
        """นับตามโปรโตคอล ข้อ ๕ — แยกตามปากกา · ข้อที่ยังไม่ยืนยันนับเป็น "รอยืนยัน" ไม่นับเป็นพบ"""
        per = {p: {"total": 0, "exact": 0, "partial": 0, "missed": 0, "pending": 0} for p in PENS}
        for m in self.s.marks:
            c = per[m["pen"]]
            c["total"] += 1
            ln = self.links.get(m["id"]) or {}
            v = ln.get("verdict", "")
            if v in ("exact", "partial") and ln.get("finding_id"):
                c[v] += 1
            elif v == "not_same":
                c["missed"] += 1          # ผู้ตรวจยืนยันว่าระบบไม่ได้ยกจุดนี้ (โปรโตคอล: พลาด)
            else:
                c["pending"] += 1         # ยังไม่ยืนยัน — ไม่นับเป็นพบหรือพลาด
        ext = {k: 0 for k in EXTRA_VERDICTS}
        ext["pending"] = 0
        for f in self.unlinked_findings:
            ext[self.extras.get(f.id, "pending")] += 1
        unread = sum(1 for f in self.actionable if f.kind == cmp.K_UNREAD)
        return {"pens": per, "extras": ext, "info": len(self.view.result.findings) - len(self.actionable),
                "actionable": len(self.actionable), "unread": unread}

    @property
    def complete(self) -> bool:
        m = self.metrics
        return all(c["pending"] == 0 for c in m["pens"].values()) and m["extras"]["pending"] == 0


def result(sid: str) -> Result:
    s = _need(sid, unlocked=False)
    rid = ensure_run(sid)
    return Result(session(sid), pdfpair.view(rid), trial_repo.links(sid), trial_repo.extras(sid),
                  trial_repo.answers(sid))


def decide_link(sid: str, mid: str, verdict: str, finding_id: str = "") -> None:
    r = result(sid)
    if verdict not in LINK_VERDICTS:
        raise TrialError("เลือกผลการยืนยัน")
    if mid not in {m["id"] for m in r.s.marks}:
        raise TrialError("ไม่พบจุดที่ระบุ")
    fid = finding_id or (r.links.get(mid) or {}).get("finding_id", "")
    if verdict != "not_same" and (not fid or r.finding(fid) is None or r.finding(fid).info):
        raise TrialError("เลือกข้อสังเกตของระบบที่ตรงกับจุดนี้ก่อน")
    trial_repo.decide_link(sid, mid, fid if verdict != "not_same" else "", verdict)


def decide_extra(sid: str, fid: str, verdict: str) -> None:
    r = result(sid)
    if verdict not in EXTRA_VERDICTS:
        raise TrialError("เลือกผลของข้อนี้")
    if fid not in {f.id for f in r.unlinked_findings}:
        raise TrialError("ข้อนี้จับคู่กับจุดที่วงแล้ว หรือไม่ใช่ข้อที่ต้องตัดสิน")
    trial_repo.decide_extra(sid, fid, verdict)


def candidates(r: Result, m: dict, limit: int = 12) -> list:
    """ข้อสังเกตที่ผู้ตรวจเลือกจับคู่เองได้ — หน้าเดียวกันก่อน แล้วหน้าใกล้"""
    side, other = ("b", "a") if m["side"] == "cur" else ("a", "b")

    def where(f):
        # ข้อ "มีเฉพาะอีกฉบับ" ไม่มีตำแหน่งในฉบับนี้ — ใช้หน้าของอีกฉบับ (เลขหน้าอาจไม่ตรงกัน จึงเรียงไว้หลัง)
        p = getattr(f, side).page
        return (0, abs(p - m["page"])) if p else (1, abs((getattr(f, other).page or 0) - m["page"]))
    return sorted(r.actionable, key=where)[:limit]


def save_answers(sid: str, form: dict) -> None:
    _need(sid, unlocked=False)
    vals = {}
    for _g, items in LIKERT_ITEMS:
        for k, _t in items:
            v = str(form.get(k, "")).strip()
            if v:
                if v not in ("1", "2", "3", "4", "5"):
                    raise TrialError("คำตอบต้องเป็น 1–5")
                vals[k] = v
    for k, _t in OPEN_ITEMS:
        if str(form.get(k, "")).strip():
            vals[k] = str(form[k]).strip()[:2000]
    if not vals:
        raise TrialError("ยังไม่ได้ตอบข้อใด")
    trial_repo.answer(sid, vals)


def summary(sid: str) -> dict:
    """สรุปที่ส่งให้ผู้วิจัย — **จำนวนเท่านั้น** (ไม่มีตำแหน่ง/หมายเหตุของจุดที่วง) + คำตอบแบบสอบถาม"""
    r = result(sid)
    b = r.s.book
    vs = trial_repo.views(sid)
    return {"trial_version": TRIAL_VERSION, "protocol": PROTOCOL_VERSION, "session": sid,
            "views": {"page_pairs_opened": len({(v["cur_page"], v["prev_page"]) for v in vs}),
                      "with_previous": sum(1 for v in vs if v["prev_page"]), "events": len(vs)},
            "reviewer_code": r.s.rec["reviewer"], "book": {"title": b["title"], "agency": b["agency"], "pair": b["pair"],
                                                           "current_sha256": b["cur"]["sha256"],
                                                           "previous_sha256": b["prev"]["sha256"]},
            "system": {"run_id": r.view.rid, "versions": r.view.run["versions"], "pdfbook": PDFBOOK_VERSION,
                       "profile": prof.PROFILE_VERSION, "profile_status": prof.PROFILE_STATUS},
            "locked_at": r.s.rec["locked_at"], "complete": r.complete, "metrics": r.metrics,
            "answers": r.answers}


def summary_bytes(sid: str) -> bytes:
    data = json.dumps(summary(sid), ensure_ascii=False, indent=2).encode("utf-8")
    from ..storage import audit
    audit.record("trial_summary_exported", "trial_session", sid,
                 {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    return data


__all__ = ["TrialError", "TrialBook", "books", "get_book", "book_status", "start", "session", "page_png",
           "add_mark", "update_mark", "page_done", "page_undone", "log_view", "lock", "ensure_run", "result", "decide_link", "decide_extra",
           "candidates", "save_answers", "summary", "summary_bytes", "PENS", "SIDES", "TOPIC_CODES",
           "TOPIC_LABELS", "LINK_VERDICTS", "EXTRA_VERDICTS", "LIKERT_ITEMS", "OPEN_ITEMS"]
