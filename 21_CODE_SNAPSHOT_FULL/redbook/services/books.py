# -*- coding: utf-8 -*-
"""คลังเล่มงบประมาณ (Book Discovery) — ค้น · กรอง · จัดเรียง · จับคู่เล่มข้ามปี

ที่มา (#24): ผู้ใช้ต้องเปิด PDF ทีละเล่มกว่าจะรู้ว่าเล่มนั้นคืออะไร เพราะเว็บต้นทาง
เรียงเป็นรายการยาวต่อปี ชื่อเล่มยาว (มัธยฐาน 106 ตัวอักษร) และลิงก์ PDF อยู่ในหน้าย่อยของแต่ละเล่ม · โมดูลนี้แปลงทะเบียนเล่ม
(``redbook/data/book_catalog.json`` ที่สร้างจากหน้าเผยแพร่ทางการ) เป็นข้อมูลที่
หน้าจออ่านได้ทันที: **ปี · ฉบับ/เล่ม · หน่วยรับงบในเล่ม · ประเภท · ลิงก์ทางการ**

หลักการ
- อ่านอย่างเดียว ไม่แตะฐานข้อมูล ไม่แตะเครื่องยนต์เปรียบเทียบ
- ไม่เก็บสำเนา PDF — ทุกเล่มชี้กลับลิงก์ทางการ
- ค้นด้วยเลขไทยหรือเลขอารบิกก็ได้ ("เล่ม ๒" = "เล่ม 2") และปีสองหลัก ("70" = 2570)
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..config import PROJECT_ROOT

#: ทะเบียนเล่มที่แอปอ่าน — ``REDBOOK_BOOK_CATALOG`` ชี้ไปไฟล์อื่นได้ (สัญญา #27 หรือ fixture สาธิต)
_DATA = Path(__file__).resolve().parent.parent / "data"
#: ค่าเริ่มต้น: ทะเบียนแหล่งทางการของ #27 ถ้ามีในแพ็กเกจ (``source_registry.json``) ไม่งั้นทะเบียนเดิมของ #24
CATALOG_PATH = Path(os.environ.get("REDBOOK_BOOK_CATALOG")
                    or next((p for p in (_DATA / "source_registry.json", _DATA / "book_catalog.json")
                             if p.is_file()), _DATA / "book_catalog.json"))

#: ภาพปกหน้าแรกที่สร้างด้วย ``scripts/build_book_thumbnails.py`` — อยู่นอก Git เสมอ
#: ไม่มีภาพ = การ์ดใช้ปกจำลองจาก metadata (ไม่ถือเป็นข้อผิดพลาด)
#: แยกจาก DATA_DIR โดยเจตนา — โหมดสาธิตเปลี่ยน DATA_DIR ไป .data_demo แต่ภาพปกเป็นของเล่มทางการชุดเดียวกัน
THUMB_DIR = Path(os.environ.get("REDBOOK_THUMB_DIR", PROJECT_ROOT / ".data" / "book_thumbs")).resolve()

# ═════════════════════════════════════════ สัญญาข้อมูล (#27 source registry 0.1.0 · ร่าง)
# Library UI รับข้อมูลจากสัญญาของ #27 เท่านั้น — ใช้คำศัพท์สถานะของ #27 ตรงตัว
# อ่านแบบ "ไม่เดา": ฟิลด์หาย / UNCHECKED / NOT_LISTED => "ยังไม่มีข้อมูล" ไม่ใช่ "ไม่มี"
# ทะเบียนเดิมของ #24 (book_catalog.json) ไม่เคยค้น Excel => Excel = UNCHECKED ทุกเล่ม
# คู่เอกสาร: อ่านจาก pairs[] ของ #27 · เฉพาะ status MATCHED เท่านั้นที่ UI เสนอเป็นลิงก์
PDF_STATES = {"FOUND": "ok", "BROKEN_LINK": "broken", "NOT_FOUND": "missing", "UNCHECKED": "unchecked"}
#: #27 รอบ 2 — ``excel.source_status`` ห้าค่า (อ่านก่อน ``excel.status`` เดิม) · Bo ACCEPT round 2
#: FOUND = ยืนยันตัวไฟล์แล้ว · UNVERIFIED = มีลิงก์ (มักเป็นหน้าดูไฟล์ภายนอก) แต่ยังไม่ยืนยันตัวไฟล์
EXCEL_SOURCE_STATES = {"FOUND": "ok", "UNVERIFIED": "unverified", "BROKEN_LINK": "broken",
                       "NOT_LISTED": "not_listed", "NOT_FOUND": "missing"}
EXCEL_STATES = {"EXCEL_AVAILABLE": "ok", "BROKEN_LINK": "broken", "NOT_LISTED": "not_listed",
                "UNCHECKED": "unchecked"}
#: รุ่นสัญญาที่ตัวอ่านนี้รู้จัก — #27 เพิ่มรุ่นเมื่อชื่อ/ความหมายฟิลด์เปลี่ยน
SUPPORTED_CONTRACTS = {"source-contract-0.1.0"}
PAIR_MATCHED = "MATCHED"
#: MATCHED = "metadata-confirmed document pair" — ยืนยันจากข้อมูลเล่ม ไม่ได้หมายความว่าเทียบเนื้อหาแล้ว
PAIR_STATUS_LABEL = {"MATCHED": "ยืนยันจากข้อมูลเล่มแล้ว", "REVIEW_REQUIRED": "อาจเกี่ยวข้อง — รอยืนยัน",
                     "CANNOT_DETERMINE": "ยังระบุไม่ได้"}
STAGES = (("draft", "ร่าง พ.ร.บ."), ("act", "พ.ร.บ."))
STAGE_LABEL = dict(STAGES)
STAGE_KEYS = {k for k, _ in STAGES}
EXCEL_EXT = (".xlsx", ".xls", ".xlsm")
FILES = (("pdf", "มี PDF"), ("excel", "มี Excel"))
FILE_KEYS = {k for k, _ in FILES}

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

#: ประเภทที่ผู้ใช้กรองได้ — เรียงตามความถี่การใช้งานของผู้ตรวจ (ฉบับที่ 3 ใช้บ่อยสุด)
#: ``group`` รวมรายงานประกอบหลายชนิดเป็นตัวกรองเดียว เพื่อไม่ให้ตัวเลือกยาวเกินจำเป็น
TYPE_GROUPS = (
    ("by_ministry", "รายจ่ายรายกระทรวง (ฉบับที่ 3)", ("expenditure_by_ministry",)),
    ("bill", "ตัวบท พ.ร.บ. และเอกสารประกอบ", ("bill", "supporting_report", "appropriation_law",
                                                "budget_doc_4", "budget_doc_5", "budget_doc_6",
                                                "budget_doc_7")),
    ("brief", "งบประมาณโดยสังเขป", ("budget_in_brief",)),
    ("revenue", "รายรับ (ฉบับที่ 1–2)", ("revenue_expenditure", "revenue_estimate")),
    ("english", "ฉบับภาษาอังกฤษ", ("english", "en_budget_in_brief", "en_bill", "en_budget_statement")),
)
TYPE_GROUP_OF = {t: key for key, _, types in TYPE_GROUPS for t in types}
TYPE_GROUP_LABEL = {key: label for key, label, _ in TYPE_GROUPS}
#: ป้ายสั้นบนการ์ด — ไม่ซ้ำ "ฉบับที่ N" ที่ปกจำลองบอกแล้ว
TYPE_SHORT = {"by_ministry": "รายจ่ายรายกระทรวง", "bill": "ตัวบท/เอกสารประกอบ",
              "brief": "งบประมาณโดยสังเขป", "revenue": "รายรับ", "english": "ภาษาอังกฤษ"}

SORTS = (
    ("volume", "ลำดับเล่ม"),
    ("newest", "ปีล่าสุดก่อน"),
    ("oldest", "ปีเก่าก่อน"),
    ("az", "ชื่อ ก–ฮ"),
)
SORT_KEYS = {k for k, _ in SORTS}

#: ค่าเริ่มต้น = "ตามเล่ม" (D1 · กิ๊ฟ 7 ต.ค. 2569) — เห็นเล่มเดียวกันข้ามปีในการ์ดเดียว
VIEWS = (("grouped", "ตามเล่ม (เทียบปี)"), ("cards", "รายเล่ม"), ("list", "รายการ"))
DEFAULT_VIEW = "grouped"
VIEW_KEYS = {k for k, _ in VIEWS}

PAGE_SIZE = 24

#: สีคาดปก → ชื่อคลาสสี (ภาษาอังกฤษสำหรับ CSS) · แสดงเฉพาะเมื่อชื่อไฟล์ทางการระบุไว้
STRIPE_CLASS = {
    "แดง": "red", "เหลือง": "yellow", "ม่วง": "purple", "น้ำเงิน": "navy",
    "ชมพู": "pink", "เขียว": "green", "ส้ม": "orange", "ฟ้า": "sky",
}


def norm(text: str) -> str:
    """รูปเทียบสำหรับค้นหา — เลขไทยเป็นอารบิก ตัวพิมพ์เล็ก ช่องว่างเดียว"""
    return re.sub(r"\s+", " ", (text or "").translate(THAI_DIGITS)).strip().lower()


def _clean_title(title: str) -> str:
    """ตัดส่วนที่ซ้ำกับป้ายอื่นบนการ์ดออก — เหลือเฉพาะสิ่งที่บอกว่าเล่มนี้คืออะไร"""
    t = title.translate(THAI_DIGITS)
    t = re.sub(r"^เอกสารงบประมาณ\s*ฉบับที่\s*\d+\s*(เล่มที่\s*\d+\s*(\(\s*\d+\s*\))?)?", "", t)
    t = re.sub(r"งบประมาณรายจ่ายประจำปีงบประมาณ\s*พ\.ศ\.\s*\d{4}", "", t)
    t = re.sub(r"ประจำปีงบประมาณ\s*พ\.ศ\.\s*\d{4}", "", t)
    t = re.sub(r"\s+", " ", t).strip(" -·")
    return t or title


@dataclass(frozen=True)
class Book:
    id: str
    fiscal_year: int
    title: str
    doc_type: str
    doc_type_label: str
    doc_no: str
    volume: str
    ministries: tuple[str, ...]
    posted: str
    publisher: str
    stage: str
    source_page: str
    pdf_url: str
    files: tuple[dict, ...]
    stripe_color: str
    retrieved_at: str
    link_check: dict = field(default_factory=dict, hash=False, compare=False)
    #: ระดับหน่วยงาน (กรม/สำนักงาน) — ทะเบียนปัจจุบันไม่มี รอ #27
    agencies: tuple[str, ...] = ()
    #: ขั้นจากสัญญา #27 (DRAFT/ACT -> draft/act) · ว่าง = อ่านจากข้อความ ``stage``
    stage_key: str = ""
    #: สถานะไฟล์ตามคำศัพท์ #27 · ทะเบียนเดิมไม่เคยค้น Excel => UNCHECKED
    pdf_state: str = ""
    excel_state: str = "UNCHECKED"
    #: ระดับการยืนยันไฟล์ Excel ตาม #27 (เช่น EXTERNAL_VIEWER_PAGE_OPENS_FILE_NOT_VERIFIED)
    excel_verification: str = ""
    #: ``excel.source_status`` (#27 รอบ 2) · ว่าง = ทะเบียนรุ่นก่อน ใช้ ``excel_state``
    excel_source: str = ""
    #: ``excel.review_flags`` ตามที่ #27 รายงาน — แสดงเป็นสถานะ ไม่ตีความเพิ่ม
    excel_flags: tuple[str, ...] = ()
    #: เอกสารสังเคราะห์ (fixture สาธิต · ``"synthetic": true`` ในสัญญา) — ต้องติดป้ายทุกจุดที่แสดง
    synthetic: bool = False
    #: ไม่ว่าง = การ์ดตัวอย่างสถานะบนหน้า /books/states (ไม่ใช่เล่มในทะเบียน · ไม่มีลิงก์ใช้งาน)
    sample_label: str = ""

    # ---------------------------------------------------------- สัญญาข้อมูล
    @property
    def stage_code(self) -> str:
        """``draft`` / ``act`` / ``""`` (ไม่ทราบ) — สัญญา #27 ก่อน แล้วจึงอ่านข้อความขั้นเอกสาร"""
        if self.stage_key in STAGE_KEYS:
            return self.stage_key
        s = self.stage or ""
        if "ร่าง" in s:
            return "draft"
        if "พ.ร.บ." in s or "พระราชบัญญัติ" in s:
            return "act"
        return ""

    @property
    def stage_label(self) -> str:
        return STAGE_LABEL.get(self.stage_code, "ไม่ระบุขั้น")

    @property
    def excel_files(self) -> list[dict]:
        return [f for f in self.files
                if f.get("kind") == "excel" or any((f.get("url") or "").lower().split("?")[0].endswith(e)
                       or e in (f.get("label") or "").lower() for e in EXCEL_EXT)]

    @property
    def pdf_status(self) -> str:
        """``ok`` เปิดได้เมื่อตรวจล่าสุด · ``broken`` เปิดไม่ได้ · ``missing`` ไม่พบ · ``unchecked``"""
        if self.pdf_state in PDF_STATES:
            return PDF_STATES[self.pdf_state]
        if not self.pdf_url:
            return "missing"
        if self.link_ok is None:
            return "unchecked"
        return "ok" if self.link_ok else "broken"

    @property
    def pdf_openable(self) -> bool:
        """กดเปิด PDF ได้จริง — สัญญา #27 ให้ FOUND/UNCHECKED โดยไม่มี url ได้ (ลิงก์ว่าง = รีโหลดหน้าเดิม)"""
        return self.pdf_status in ("ok", "unchecked") and bool(self.pdf_url)

    @property
    def excel_note(self) -> str:
        """คำกำกับความน่าเชื่อถือของลิงก์ Excel — บอกตามระดับที่ #27 ยืนยันได้จริง"""
        if self.excel_verification == "EXTERNAL_VIEWER_PAGE_OPENS_FILE_NOT_VERIFIED":
            return "ลิงก์เปิดหน้าดูไฟล์ภายนอกได้ · ยังไม่ได้ยืนยันตัวไฟล์"
        return ""

    @property
    def excel_openable(self) -> bool:
        """มีลิงก์ให้เปิด — FOUND หรือ UNVERIFIED (ตัวหลังต้องกำกับว่ายังไม่ยืนยันไฟล์)"""
        return self.excel_status in ("ok", "unverified") and bool(self.excel_files)

    @property
    def excel_status(self) -> str:
        """``ok`` · ``unverified`` · ``broken`` · ``not_listed`` · ``missing`` · ``unchecked``
        — ไม่มีค่า "ไม่มี" (หาไม่เจอ ≠ ไม่มี) · ``source_status`` ของ #27 มาก่อนเสมอ"""
        if self.excel_source in EXCEL_SOURCE_STATES:
            return EXCEL_SOURCE_STATES[self.excel_source]
        if self.excel_files and self.excel_state in ("UNCHECKED", "EXCEL_AVAILABLE"):
            return "ok"
        return EXCEL_STATES.get(self.excel_state, "unchecked")

    @property
    def thumb_url(self) -> str:
        if self.sample_label:
            return "" if "nothumb" in self.id else (
                f"/books/thumb/{self.id.split('~')[0]}.jpg"
                if (THUMB_DIR / f"{self.id.split('~')[0]}.jpg").is_file() else "")
        return f"/books/thumb/{self.id}.jpg" if (THUMB_DIR / f"{self.id}.jpg").is_file() else ""

    # ---------------------------------------------------------- ป้ายบนการ์ด
    @property
    def type_group(self) -> str:
        return TYPE_GROUP_OF.get(self.doc_type, "bill")

    @property
    def type_group_label(self) -> str:
        return TYPE_GROUP_LABEL[self.type_group]

    @property
    def type_short(self) -> str:
        return TYPE_SHORT[self.type_group]

    @property
    def headline_short(self) -> str:
        """ชื่อบนการ์ด — เล่มที่รวมหลายหน่วยแสดงสองหน่วยแรก + จำนวนที่เหลือ
        ไม่ตัดกลางชื่อกระทรวงด้วย "…" ซึ่งทำให้อ่านผิดได้ (ดูชื่อครบได้ที่หน้ารายละเอียด)"""
        if self.doc_type == "expenditure_by_ministry" and len(self.ministries) > 2:
            return f"{' · '.join(self.ministries[:2])} และอีก {len(self.ministries) - 2} หน่วย"
        return self.headline

    @property
    def kicker(self) -> str:
        """บรรทัดเล็กเหนือชื่อ — ตำแหน่งของเล่มในชุดเอกสาร"""
        if self.doc_no and self.volume:
            return f"เอกสารงบประมาณ ฉบับที่ {self.doc_no} · เล่มที่ {self.volume}"
        if self.doc_no:
            return f"เอกสารงบประมาณ ฉบับที่ {self.doc_no}"
        return self.doc_type_label

    @property
    def headline(self) -> str:
        """ชื่อที่ผู้ใช้ต้องเห็นก่อน — เล่มรายกระทรวงใช้ชื่อหน่วยรับงบ ไม่ใช่ชื่อเอกสารยาว"""
        if self.doc_type == "expenditure_by_ministry" and self.ministries:
            return " · ".join(self.ministries)
        return _clean_title(self.title)

    @property
    def cover_label(self) -> str:
        """ตัวอักษรบนปกจำลอง — สั้นที่สุดที่ยังแยกเล่มออกจากกันได้"""
        if self.volume:
            return f"เล่ม {self.volume}"
        if self.doc_no:
            return f"ฉบับ {self.doc_no}"
        return {"bill": "ร่าง พ.ร.บ.", "budget_in_brief": "สังเขป",
                "english": "EN"}.get(self.doc_type, "รายงาน")

    @property
    def stripe_class(self) -> str:
        return STRIPE_CLASS.get(self.stripe_color, "")

    @property
    def link_ok(self) -> bool | None:
        """ผลตรวจลิงก์ของทะเบียนเดิม (#24) — สัญญา #27 ไม่มี is_pdf/status จึงอ่านจาก ``pdf_state`` แทน
        (เดิมคืน False ⇒ หน้ารายละเอียดบอก "เปิดไม่ได้" ทั้งที่ #27 ระบุ FOUND)"""
        if self.pdf_state:
            return {"FOUND": True, "BROKEN_LINK": False}.get(self.pdf_state)
        if not self.link_check or "status" not in self.link_check:
            return None
        return bool(self.link_check.get("is_pdf")) and self.link_check.get("status") in (200, 206)

    @property
    def checked_on(self) -> str:
        return (self.link_check.get("checked_at") or "")[:10]

    @property
    def haystack(self) -> str:
        return norm(" ".join([
            self.title, self.headline, self.kicker, self.doc_type_label,
            self.type_group_label, " ".join(self.ministries), str(self.fiscal_year),
            f"เล่ม {self.volume}" if self.volume else "",
            f"คาด{self.stripe_color}" if self.stripe_color else "",
        ]))


@dataclass(frozen=True)
class PairRef:
    kind: str           # SAME_YEAR (ร่าง↔พ.ร.บ.) · CROSS_YEAR (ปีต่อปี)
    status: str         # MATCHED · REVIEW_REQUIRED · CANNOT_DETERMINE
    other: "Book | None"
    other_id: str

    @property
    def confirmed(self) -> bool:
        return self.status == PAIR_MATCHED

    @property
    def status_label(self) -> str:
        return PAIR_STATUS_LABEL.get(self.status, "ยังไม่ยืนยัน")


@dataclass
class Catalog:
    version: str
    generated_at: str
    source: str
    years: tuple[int, ...]
    books: tuple[Book, ...]
    #: คู่เอกสารจาก #27 — {kind: SAME_YEAR|CROSS_YEAR, status, a: [ids], b: [ids]}
    pairs: tuple[dict, ...] = ()
    #: True เมื่อไฟล์ประกาศ ``"fixture": {"synthetic": true}`` — หน้าจอต้องติดป้ายข้อมูลสังเคราะห์
    synthetic: bool = False

    def get(self, book_id: str) -> Book | None:
        return next((b for b in self.books if b.id == book_id), None)

    @property
    def ministries(self) -> list[str]:
        """รายชื่อหน่วยรับงบที่มีในคลัง เรียงตามลำดับที่ปรากฏในชุดเอกสาร"""
        seen: list[str] = []
        for b in sorted(self.books, key=_volume_order):
            for m in b.ministries:
                if m not in seen:
                    seen.append(m)
        return seen

    @property
    def summary(self) -> dict:
        """ตัวเลขสรุปทั้งคลัง (ไม่ขึ้นกับตัวกรอง) — แถบสรุปบนหัวหน้าคลัง"""
        bs = self.books
        return {"books": len(bs), "years": len(self.years),
                "draft": sum(b.stage_code == "draft" for b in bs),
                "act": sum(b.stage_code == "act" for b in bs),
                "pdf": sum(b.pdf_status in ("ok", "unchecked") for b in bs),
                "excel": sum(b.excel_status == "ok" for b in bs),
                "excel_unchecked": sum(b.excel_status == "unchecked" for b in bs),
                "excel_unverified": sum(b.excel_status == "unverified" for b in bs),
                "thumbs": sum(bool(b.thumb_url) for b in bs)}

    @property
    def agencies(self) -> list[str]:
        return sorted({a for b in self.books for a in b.agencies})

    def pairs_of(self, book: Book, kind: str) -> list["PairRef"]:
        """คู่ของเล่มนี้ตามที่ #27 ระบุ (ทุกสถานะ) — ไม่มีใน pairs[] = ไม่มีคู่ ไม่เดาจากชื่อ"""
        out = []
        for p in self.pairs:
            if p.get("kind") != kind:
                continue
            a, b = list(p.get("a") or ()), list(p.get("b") or ())
            if book.id in a:
                others = b
            elif book.id in b:
                others = a
            else:
                continue
            for oid in others:
                out.append(PairRef(kind, p.get("status", ""), self.get(oid), oid))
        return out

    def counterpart(self, book: Book) -> Book | None:
        """คู่ ร่าง↔พ.ร.บ. ที่ #27 ยืนยันแล้ว (MATCHED) เท่านั้น"""
        return next((r.other for r in self.pairs_of(book, "SAME_YEAR") if r.confirmed and r.other), None)

    def pending_pairs(self, book: Book) -> list["PairRef"]:
        """คู่ที่ #27 ยังไม่ยืนยัน — แสดงเป็นสถานะ ห้ามเป็นลิงก์/ปุ่มเปรียบเทียบ"""
        return [r for k in ("SAME_YEAR", "CROSS_YEAR") for r in self.pairs_of(book, k) if not r.confirmed]

    def series_key(self, book: Book) -> str:
        """รหัสกลุ่ม "เล่มเดียวกันข้ามปี" จากคู่ CROSS_YEAR ที่ #27 ยืนยัน (MATCHED) เท่านั้น
        ไม่มีคู่ยืนยัน = กลุ่มของตัวเอง — UI ไม่จับคู่เอง (Gift/Bo · #24: consume pairs[] จาก #27 เท่านั้น)"""
        if not hasattr(self, "_series"):
            parent: dict[str, str] = {}

            def find(x: str) -> str:
                while parent.get(x, x) != x:
                    parent[x] = parent.get(parent[x], parent[x])
                    x = parent[x]
                return x
            for p in self.pairs:
                if p.get("kind") == "CROSS_YEAR" and p.get("status") == PAIR_MATCHED:
                    ids = list(p.get("a") or ()) + list(p.get("b") or ())
                    for other in ids[1:]:
                        ra, rb = find(ids[0]), find(other)
                        if ra != rb:
                            parent[max(ra, rb)] = min(ra, rb)
            self._series = {k: find(k) for k in parent}
        return self._series.get(book.id, book.id)

    def confirmed_other_years(self, book: Book) -> list[Book]:
        """เล่มเดียวกันในปีอื่น **ที่ทะเบียน (#27) ยืนยันแล้ว** — ใช้เป็นคู่เปรียบเทียบที่ระบบเสนอได้
        (Gift · #24 UI update ข้อ 8: "comparison CTA ควรเสนอคู่ที่ #27 ยืนยันแล้วเท่านั้น — UI ห้ามเดาคู่เอง")
        ไม่มีบันทึกใน pairs[] = ไม่มีความสัมพันธ์ (ไม่เดาจากชื่อ · คำตัดสิน Bo)"""
        found = {r.other.id: r.other for r in self.pairs_of(book, "CROSS_YEAR")
                 if r.confirmed and r.other}
        return sorted(found.values(), key=lambda b: -b.fiscal_year)


def _volume_order(b: Book):
    t = b.title.translate(THAI_DIGITS)
    vol = re.match(r"(\d+)(?:\((\d+)\))?", b.volume or "")
    group_rank = [k for k, _, _ in TYPE_GROUPS].index(b.type_group)
    return (group_rank,
            int(b.doc_no) if b.doc_no.isdigit() else 99,
            int(vol.group(1)) if vol else 0,
            int(vol.group(2)) if vol and vol.group(2) else 0,
            t)


def _book(raw: dict) -> Book:
    return Book(
        id=raw["id"], fiscal_year=int(raw["fiscal_year"]), title=raw["title"],
        doc_type=raw["doc_type"], doc_type_label=raw["doc_type_label"],
        doc_no=raw.get("doc_no", ""), volume=raw.get("volume", ""),
        ministries=tuple(raw.get("ministries") or ()), posted=raw.get("posted", ""),
        publisher=raw.get("publisher", ""), stage=raw.get("stage", ""),
        source_page=raw.get("source_page", ""), pdf_url=raw.get("pdf_url", ""),
        files=tuple(raw.get("files") or ()), stripe_color=raw.get("stripe_color", ""),
        retrieved_at=raw.get("retrieved_at", ""), link_check=raw.get("link_check") or {},
        agencies=tuple(raw.get("agencies") or ()),
    )


_BOOK_LABEL = re.compile(r"ฉบับที่\s*(\d+)(?:\s*เล่มที่\s*(\S+))?")


def _contract_book(d: dict) -> Book:
    """เอกสารหนึ่งรายการจาก ``contract.documents[]`` ของ #27 (0.1.0 · ร่าง — ชื่อฟิลด์อาจเปลี่ยน)"""
    label = (d.get("book_label") or "").translate(THAI_DIGITS)
    m = _BOOK_LABEL.search(label)
    pdf = d.get("pdf") or {}
    excel = d.get("excel") or {}
    src = d.get("source_status") or {}
    files = [{"url": pdf["url"], "label": "PDF", "kind": "pdf"}] if pdf.get("url") else []
    urls = excel.get("urls") or []
    files += [{"url": u, "kind": "excel",
               "label": f"Excel {i}/{len(urls)}" if len(urls) > 1 else "Excel"}
              for i, u in enumerate(urls, 1)]
    stage = (d.get("stage") or "").upper()
    return Book(
        id=d["id"], fiscal_year=int(d["year"]), title=d.get("book_title") or label,
        doc_type=d.get("doc_type") or "", doc_type_label=d.get("doc_type_label") or "",
        doc_no=m.group(1) if m else "", volume=(m.group(2) or "") if m else "",
        ministries=tuple(d.get("ministry") or ()), posted="", publisher="สำนักงบประมาณ",
        stage=d.get("stage_label") or "", source_page=src.get("source_page_url") or "",
        pdf_url=pdf.get("url") or "", files=tuple(files), stripe_color="",
        retrieved_at=src.get("verified_date") or "",
        link_check={"checked_at": src.get("verified_date") or ""},
        agencies=tuple(a for a in [d.get("agency")] if a),
        stage_key={"DRAFT": "draft", "ACT": "act"}.get(stage, ""),
        pdf_state=pdf.get("status") or "UNCHECKED",
        excel_state=excel.get("status") or "UNCHECKED",
        excel_verification=excel.get("verification_level") or "",
        excel_source=excel.get("source_status") or "",
        excel_flags=tuple(str(f) for f in (excel.get("review_flags") or ())),
        synthetic=bool(d.get("synthetic")),
    )


def load(path: Path | None = None) -> Catalog:
    data = json.loads(Path(path or CATALOG_PATH).read_text(encoding="utf-8"))
    synthetic = bool((data.get("fixture") or {}).get("synthetic"))
    if "contract" in data:                      # ทะเบียนแหล่งทางการของ #27
        c = data["contract"]
        # รูปข้อมูลตัดสินจาก contract_version เท่านั้น (registry_version เปลี่ยนได้โดยฟิลด์ไม่เปลี่ยน)
        # รุ่นที่ไม่รู้จัก ⇒ หยุด ไม่เดาความหมายฟิลด์ — หน้าคลังแสดงหน้าโหลดทะเบียนไม่สำเร็จ
        shape = data.get("contract_version") or c.get("version") or ""
        if shape not in SUPPORTED_CONTRACTS:
            raise ValueError(f"unsupported source contract: {shape or 'missing'}")
        books = tuple(_contract_book(d) for d in c.get("documents", []))
        return Catalog(
            version=data.get("registry_version") or shape,
            generated_at=data.get("retrieved_at") or data.get("generated_at", ""),
            source=c.get("source") or "ทะเบียนแหล่งทางการ (#27)",
            years=tuple(sorted({b.fiscal_year for b in books})),
            books=books,
            pairs=tuple({"kind": p.get("kind"), "status": p.get("status"),
                         "a": (p.get("a") or {}).get("ids") or [],
                         "b": (p.get("b") or {}).get("ids") or []}
                        for p in data.get("pairs", c.get("pairs", []))),   # #27: pairs[] อยู่ระดับบนสุด
            synthetic=synthetic,
        )
    return Catalog(
        version=data.get("catalog_version", ""), generated_at=data.get("generated_at", ""),
        source=data.get("source", ""), years=tuple(data.get("years") or ()),
        books=tuple(_book(r) for r in data.get("books", [])),
        synthetic=synthetic,
    )


@lru_cache(maxsize=1)
def catalog() -> Catalog:
    """ทะเบียนเล่มของแอป — อ่านครั้งเดียวต่อโปรเซส (ไฟล์เปลี่ยนเมื่อรันตัวสร้างใหม่เท่านั้น)"""
    return load()


# ═══════════════════════════════════════════════════════════════ ค้นและกรอง
@dataclass
class Query:
    q: str = ""
    year: int | None = None
    ministry: str = ""
    type: str = ""
    sort: str = "volume"
    view: str = DEFAULT_VIEW
    page: int = 1
    stage: str = ""            # "" = ทุกขั้น · draft · act
    agency: str = ""
    file: str = ""             # "" · pdf · excel — มีไฟล์ชนิดนี้ที่เปิดได้

    @classmethod
    def from_params(cls, params, years: tuple[int, ...]) -> "Query":
        def _int(v):
            try:
                return int(str(v).translate(THAI_DIGITS))
            except (TypeError, ValueError):
                return None
        year = _int(params.get("year"))
        typ = params.get("type") or ""
        sort = params.get("sort") or "volume"
        return cls(
            q=(params.get("q") or "").strip()[:120],
            year=year if year in years else None,
            ministry=(params.get("ministry") or "").strip()[:200],
            type=typ if typ in TYPE_GROUP_LABEL else "",
            sort=sort if sort in SORT_KEYS else "volume",
            view=params.get("view") if params.get("view") in VIEW_KEYS else DEFAULT_VIEW,
            page=max(1, _int(params.get("page")) or 1),
            stage=params.get("stage") if params.get("stage") in STAGE_KEYS else "",
            agency=(params.get("agency") or "").strip()[:200],
            file=params.get("file") if params.get("file") in FILE_KEYS else "",
        )

    @property
    def active(self) -> bool:
        return bool(self.q or self.year or self.ministry or self.type or self.stage
                    or self.agency or self.file)

    def params(self, **override) -> dict:
        """พารามิเตอร์สำหรับสร้างลิงก์ — ตัดค่าว่างทิ้งเพื่อให้ URL อ่านได้"""
        p = {"q": self.q, "year": self.year or "", "ministry": self.ministry,
             "type": self.type, "sort": "" if self.sort == "volume" else self.sort,
             "view": "" if self.view == DEFAULT_VIEW else self.view,
             "stage": self.stage, "agency": self.agency, "file": self.file}
        p.update(override)
        return {k: v for k, v in p.items() if v not in ("", None)}


def _match_token(token: str, book: Book, hay: str) -> bool:
    # ปีสองหลัก "70" → 2570 · ปีสี่หลักเทียบตรง
    if re.fullmatch(r"[6-9]\d", token):
        return book.fiscal_year % 100 == int(token) or token in hay
    return token in hay


@dataclass
class Group:
    """เล่มเดียวกันหลายปี — ใช้ในมุมมอง "ตามเล่ม" """
    lead: Book                 # ปีล่าสุดของกลุ่ม ใช้เป็นชื่อการ์ด
    by_year: list[Book]        # เรียงปีใหม่ → เก่า


@dataclass
class Result:
    books: list[Book]
    total: int
    page: int
    pages: int
    year_counts: dict[int, int]
    type_counts: dict[str, int]
    groups: list[Group] = field(default_factory=list)
    group_total: int = 0
    stage_counts: dict[str, int] = field(default_factory=dict)
    file_counts: dict[str, int] = field(default_factory=dict)


VOLUME_PHRASE = re.compile(r"เล่ม(?:ที่)?\s*(\d+(?:\(\d+\))?)")


def state_samples(cat: Catalog) -> list[Book]:
    """การ์ดตัวอย่างสถานะ — เล่มจริงหนึ่งเล่มเป็นฐาน เปลี่ยนเฉพาะสถานะที่จะสาธิต
    ทุกใบมี ``sample_label`` ⇒ เทมเพลตปิดลิงก์และติดป้าย "ตัวอย่างสถานะ" เสมอ"""
    from dataclasses import replace

    base = next((b for b in cat.books if b.doc_type == "expenditure_by_ministry"
                 and len(b.ministries) == 1), cat.books[0] if cat.books else None)
    if base is None:
        return []
    xls = {"url": "#", "label": "ตัวอย่าง.xlsx"}
    return [
        replace(base, id=f"{base.id}~ok", sample_label="PDF พบ · Excel ยังไม่ได้ตรวจ (สภาพทะเบียนเดิม)"),
        replace(base, id=f"{base.id}~xls", files=base.files + (xls,), excel_state="EXCEL_AVAILABLE",
                sample_label="PDF พบ · Excel พบ (EXCEL_AVAILABLE)"),
        replace(base, id=f"{base.id}~xlsbroken", excel_state="BROKEN_LINK",
                sample_label="ลิงก์ Excel เปิดไม่ได้ (BROKEN_LINK)"),
        replace(base, id=f"{base.id}~xlsnl", excel_state="NOT_LISTED",
                sample_label="Excel ไม่อยู่ในส่วนที่ค้น (NOT_LISTED)"),
        replace(base, id=f"{base.id}~act", stage="พ.ร.บ.", stage_key="act",
                sample_label="ขั้น พ.ร.บ."),
        replace(base, id=f"{base.id}~broken", pdf_state="BROKEN_LINK",
                sample_label="ลิงก์ PDF เปิดไม่ได้ (BROKEN_LINK)"),
        replace(base, id=f"{base.id}~missing", pdf_url="", files=(), pdf_state="NOT_FOUND",
                sample_label="ไม่พบ PDF (NOT_FOUND)"),
        replace(base, id=f"nothumb~{base.id}", sample_label="ยังไม่มีภาพปก — ใช้ปกจำลองจากข้อมูลเล่ม"),
    ]


def _has_file(b: Book, kind: str) -> bool:
    if kind == "pdf":
        return b.pdf_status in ("ok", "unchecked")
    if kind == "excel":
        return b.excel_status == "ok"
    return True


def search(cat: Catalog, query: Query) -> Result:
    text = norm(query.q)
    # "เล่ม 2" / "เล่มที่ ๒" เป็นวลีเดียว — ถ้าแยกคำ เลข "2" จะไปจับทุกเล่มที่มีเลข 2
    volumes = VOLUME_PHRASE.findall(text)
    tokens = [t for t in VOLUME_PHRASE.sub(" ", text).split(" ") if t]

    def base_match(b: Book) -> bool:
        if query.ministry and query.ministry not in b.ministries:
            return False
        if query.agency and query.agency not in b.agencies:
            return False
        if volumes and not any(b.volume == v or b.volume.startswith(v + "(")
                               for v in volumes):
            return False
        hay = b.haystack
        return all(_match_token(t, b, hay) for t in tokens)

    pool = [b for b in cat.books if base_match(b)]

    # ตัวเลขข้างตัวกรองแต่ละมิติ นับจากผลที่ผ่าน "ตัวกรองมิติอื่น" แล้ว — ผู้ใช้เห็นก่อนกดว่าจะเหลือกี่เล่ม
    checks = {
        "year": lambda b: not query.year or b.fiscal_year == query.year,
        "type": lambda b: not query.type or b.type_group == query.type,
        "stage": lambda b: not query.stage or b.stage_code == query.stage,
        "file": lambda b: _has_file(b, query.file),
    }

    def passing(*skip: str) -> list[Book]:
        return [b for b in pool if all(f(b) for k, f in checks.items() if k not in skip)]

    by_year, by_type, by_stage, by_file = (passing("year"), passing("type"),
                                           passing("stage"), passing("file"))
    year_counts = {y: sum(1 for b in by_year if b.fiscal_year == y) for y in cat.years}
    type_counts = {k: sum(1 for b in by_type if b.type_group == k) for k, _, _ in TYPE_GROUPS}
    stage_counts = {k: sum(1 for b in by_stage if b.stage_code == k) for k, _ in STAGES}
    file_counts = {k: sum(1 for b in by_file if _has_file(b, k)) for k, _ in FILES}

    hits = passing()

    if query.sort == "newest":
        hits.sort(key=lambda b: (-b.fiscal_year, _volume_order(b)))
    elif query.sort == "oldest":
        hits.sort(key=lambda b: (b.fiscal_year, _volume_order(b)))
    elif query.sort == "az":
        hits.sort(key=lambda b: (norm(b.headline), -b.fiscal_year))
    else:  # volume — เล่มเดียวกันของสามปีอยู่ติดกัน เทียบข้ามปีได้ด้วยสายตา
        hits.sort(key=lambda b: (_volume_order(b)[:4], b.ministries, -b.fiscal_year))

    total = len(hits)
    if query.view == "grouped":
        groups = group_by_book(hits, cat)
        pages = max(1, -(-len(groups) // PAGE_SIZE))
        page = min(query.page, pages)
        start = (page - 1) * PAGE_SIZE
        return Result([], total, page, pages, year_counts, type_counts,
                      groups[start:start + PAGE_SIZE], len(groups), stage_counts, file_counts)
    pages = max(1, -(-total // PAGE_SIZE))
    page = min(query.page, pages)
    start = (page - 1) * PAGE_SIZE
    return Result(hits[start:start + PAGE_SIZE], total, page, pages, year_counts, type_counts,
                  stage_counts=stage_counts, file_counts=file_counts)


def group_by_book(books: list[Book], cat: Catalog | None = None) -> list[Group]:
    """รวมเล่มที่ #27 ยืนยันว่าเป็นเล่มเดียวกันข้ามปีเป็นกลุ่มเดียว โดยคงลำดับตามเล่มแรกที่พบ
    ไม่มีทะเบียน/ไม่มีคู่ยืนยัน = หนึ่งเล่มหนึ่งกลุ่ม (ไม่จัดกลุ่มจากชื่อ)"""
    order: list[str] = []
    members: dict[str, list[Book]] = {}
    for b in books:
        key = cat.series_key(b) if cat else b.id
        if key not in members:
            order.append(key)
            members[key] = []
        members[key].append(b)
    out = []
    for key in order:
        group = sorted(members[key], key=lambda b: -b.fiscal_year)
        out.append(Group(group[0], group))
    return out


# ═══════════════════════════════════════════════════════════ คู่เล่มสำหรับตรวจ
@dataclass
class Pair:
    a: Book | None
    b: Book | None
    error: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return bool(self.a and self.b and not self.error)

    @property
    def mode(self) -> str:
        """โหมดของงานตรวจที่มีอยู่แล้ว — ไม่สร้างโหมดใหม่"""
        if self.a and self.b and self.a.fiscal_year != self.b.fiscal_year:
            return "year_to_year"
        return "before_after_reduction"

    @property
    def suggested_name(self) -> str:
        if not (self.a and self.b):
            return ""
        what = self.b.headline if len(self.b.headline) <= 70 else self.b.kicker
        if self.a.fiscal_year != self.b.fiscal_year:
            return f"{what} · ปี {self.a.fiscal_year} เทียบ {self.b.fiscal_year}"
        return f"{what} · ปี {self.b.fiscal_year}"


def make_pair(cat: Catalog, a_id: str, b_id: str) -> Pair:
    """จัดคู่จากรหัสเล่มสองรหัส — ปีเก่าเป็นฝั่ง A เสมอ ผู้ใช้จึงไม่ต้องคิดว่าฝั่งไหนเป็นฝั่งไหน"""
    a = cat.get(a_id) if a_id else None
    b = cat.get(b_id) if b_id else None
    if (a_id and not a) or (b_id and not b):
        return Pair(a, b, error="ไม่พบเล่มที่เลือกในคลัง — ลิงก์อาจมาจากทะเบียนเล่มรุ่นเก่า")
    if a and b and a.id == b.id:
        return Pair(a, None, error="เลือกเล่มเดียวกันทั้งสองฝั่ง — โปรดเลือกอีกฉบับหนึ่ง")
    if a and b and b.fiscal_year < a.fiscal_year:
        a, b = b, a
    # ปีเดียวกัน: ร่าง พ.ร.บ. เป็นฝั่ง A เสมอ ไม่ว่าผู้ใช้เริ่มจากเล่มไหน (ไม่งั้นป้าย ร่าง→พ.ร.บ. ไม่ขึ้น)
    if a and b and a.fiscal_year == b.fiscal_year and a.stage_code == "act" and b.stage_code == "draft":
        a, b = b, a
    pair = Pair(a, b)
    if a and b:
        confirmed = (b in cat.confirmed_other_years(a)) or (cat.counterpart(a) == b)
        if not confirmed:
            # ไม่ตัดสินเองว่า "ไม่ใช่เล่มเดียวกัน" — บอกเพียงว่าทะเบียนยังไม่ยืนยันคู่นี้
            pair.warnings.append(
                "ทะเบียนแหล่งทางการยังไม่ยืนยันว่าสองเล่มนี้เป็นคู่กัน — "
                "ตรวจได้ แต่ความต่างที่พบอาจมาจากการเลือกเล่มคนละชุด")
        if a.fiscal_year == b.fiscal_year:
            if {a.stage_code, b.stage_code} == {"draft", "act"}:
                # ร่าง→พ.ร.บ. ไม่ใช่ "การปรับลด" — บอกตามจริงว่าใช้โหมดงานตรวจเดิมแบบก่อน/หลัง (mode ไม่เปลี่ยน)
                pair.warnings.append(
                    "คู่ ร่าง พ.ร.บ. → พ.ร.บ. ปีเดียวกัน — ตั้งเป็นงาน “ตรวจความแตกต่างระหว่างร่างและ พ.ร.บ.”")
            else:
                pair.warnings.append(
                    "สองเล่มเป็นปีงบประมาณเดียวกัน — ระบบจะตั้งเป็นงาน “ก่อนเทียบหลังปรับลด”")
    return pair


__all__ = ["Book", "Catalog", "FILES", "PairRef", "Group", "Pair", "Query", "Result", "SORTS", "STAGES",
           "THUMB_DIR", "TYPE_GROUPS", "VIEWS",
           "PAGE_SIZE", "catalog", "load", "make_pair", "norm", "search"]
