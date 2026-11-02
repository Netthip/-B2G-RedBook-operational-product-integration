# -*- coding: utf-8 -*-
"""สกัด "ข้อเท็จจริงของเล่ม" จากช่วงหน้าของหน่วยงาน — ทุกค่ามีหลักฐาน (หน้า + กรอบ + ข้อความดิบ)

สิ่งที่สกัด

* ``amounts``      เงินรายแถว×คอลัมน์ ของตารางสรุป (หมวดงบ) · ประเภทรายจ่าย (ประจำ/ลงทุน) ·
                   ประมาณการรายจ่ายล่วงหน้า (ปี) · เงินนอกงบประมาณ · ยอดหมวดในรายละเอียด · หัวเล่ม
* ``nodes``        แผนงาน / ผลผลิต / โครงการ / กิจกรรม พร้อมแม่ของแต่ละโหนด
* ``items``        รายการในรายละเอียดงบประมาณ (เช่น ครุภัณฑ์ (1) …) + ธง "ไม่เสนอตั้ง"
* ``commitments``  รายการผูกพันข้ามปี — วงเงินทั้งสิ้น · ตั้งงบประมาณรายปี · ผูกพันปีต่อไป
* ``indicators``   ตัวชี้วัด หน่วยนับ ค่าเป้าหมายรายปี (ระดับหน่วยงาน และระดับผลผลิต/โครงการ)
* ``texts``        วิสัยทัศน์ · พันธกิจ · ผลสัมฤทธิ์ · เป้าหมายการให้บริการ · วัตถุประสงค์ของผลผลิต
* ``coverage``     หน้าที่ไม่มีชั้นข้อความ · แถวที่มีตัวเลขแต่จัดเข้าหมวดไม่ได้ · หัวข้อที่ไม่พบ

🔴 แถวที่จัดไม่ได้ต้องอยู่ใน ``coverage`` เสมอ — ห้ามทิ้งเงียบ
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal

from . import PDFBOOK_VERSION
from . import profile as P
from .layout import Column, Row, assign, header_columns, label_without_text_columns, rows_of_page
from .text import DASH_TOKENS
from .thai_repair import repair as _thai_repair
from .text import UNIT_SCALE, clean, exact_key, join_wrapped, label_key, skeleton, squash, strip_number, text_key

TOP_MARGIN_PT = 45.0
BOTTOM_MARGIN_PT = 30.0
_PAGE_NO = re.compile(r"^(?:หน้า\s*)?\(?\d{1,4}\)?$")
_WATERMARK = ("ข้อมูลสังเคราะห์",)

TABLE_UNIT_DEFAULT = {P.SEC_SUMMARY: "ล้านบาท", P.SEC_ECON: "ล้านบาท", P.SEC_MTEF: "ล้านบาท",
                      P.SEC_OFFBUDGET: "ล้านบาท", P.SEC_DETAIL: "บาท", "header": "บาท",
                      P.SEC_YEARS: "ล้านบาท", P.SUB_ACTIVITY: "ล้านบาท", P.SUB_OUTPUT_MTEF: "ล้านบาท"}
#: แถวที่เป็นเพียงข้อมูลกำกับใต้ค่า (ผลการดำเนินงานในวงเล็บ · คำว่า "แผน" ใต้หัวปี) — ไม่ใช่รายการ
_ANNOTATION = re.compile(r"^\(?[\d,.\-–]*\)?\*?$|^\(ผล\)\*?$|^แผน$")


@dataclass
class Evidence:
    page: int
    bbox: tuple
    text: str


#: ที่มาของหน่วย — ``row``/``text_column``/``table_decl`` = มีในเอกสาร · ``profile_default``/``assumed`` = ไม่มี
UNIT_ORIGINS_IN_DOCUMENT = ("row", "text_column", "table_decl")
#: ธงที่ทำให้ข้อสังเกตต้องให้คนยืนยันก่อนใช้ (ยังเทียบให้ แต่ติดคำเตือน)
CONFIRM_FLAGS = ("unit_not_in_document", "column_nearest", "year_from_book_meta",
                 "identity_collision", "identity_ambiguous")
#: ธงที่บอกวิธีตีความ ไม่ต้องยืนยันเพิ่ม (แสดงใน CSV/ข้อมูลระเบียน)
INFO_FLAGS = ("header_two_line", "range_header")


@dataclass
class Amount:
    """ค่าเงินหนึ่งช่อง — ค่า · ความละเอียดที่พิมพ์ · หน่วย · ที่มา แยกกัน (precision ไม่ใช่ความเชื่อมั่น)

    * ``value`` = Decimal ตามที่พิมพ์ (ไม่ปัด ไม่เติมทศนิยม) · ``raw`` = ข้อความดิบในเซลล์
    * ``decimals`` = ทศนิยมที่พิมพ์ · ``scale`` = ตัวคูณเป็นบาท · ``tolerance`` = ครึ่งหนึ่งของหลักสุดท้ายที่พิมพ์
    * ``status`` = ``read`` (อ่านตัวเลขได้) · ``dash`` (พิมพ์ขีด = ไม่มีค่า, ``value`` ว่าง) ·
      ``blank`` (แถวมีอยู่และมีตัวเลขในคอลัมน์อื่น แต่ช่องนี้ไม่มีอะไรพิมพ์ — ``BookFacts.blanks``) ·
      ไม่มีระเบียนเลย = "ไม่พบ" · แถวที่มีตัวเลขแต่จัดไม่ได้อยู่ใน ``coverage.unparsed`` ("อ่านไม่ได้") ·
      ช่องว่างไม่ได้พิสูจน์ว่าเป็นศูนย์ และการไม่มีระเบียนไม่ได้พิสูจน์ว่าช่องว่าง
    """
    table: str            # SEC_* หรือ "header"
    node: str             # กุญแจโหนด ("total" = รวมทั้งสิ้น · "" = ระดับหน่วยงาน)
    column: str           # หมวดงบ · ประเภทรายจ่าย · ปี · "รวม"
    value: str            # Decimal เป็นข้อความ ("" เมื่อ status = dash)
    unit: str
    raw: str
    ev: Evidence
    unit_origin: str = ""                 # row · text_column · table_decl · profile_default · assumed · "" = รอบเก่า
    column_origin: str = ""               # header · header_two_line · range_header · nearest_column · label · book_year
    flags: list = field(default_factory=list)
    status: str = "read"                  # read · dash · blank
    unit_ev: Evidence | None = None       # หลักฐานหน่วย (บรรทัดประกาศหน่วย/แถว) · None = ไม่มีในเอกสาร
    column_ev: Evidence | None = None     # หลักฐานคอลัมน์/ปี (บรรทัดหัวตาราง หรือแถวเดียวกัน)

    @property
    def dec(self) -> Decimal:
        return Decimal(self.value)

    @property
    def decimals(self) -> int:
        t = self.raw.replace(",", "").strip()
        return len(t.split(".", 1)[1]) if "." in t else 0

    @property
    def scale(self) -> Decimal:
        return UNIT_SCALE.get(self.unit, Decimal(1))

    @property
    def tolerance(self) -> Decimal:
        """ครึ่งหนึ่งของหลักสุดท้ายที่พิมพ์ (หน่วยเดียวกับค่า) — ความละเอียดที่พิมพ์ ไม่ใช่ความเชื่อมั่น"""
        return Decimal(5) * Decimal(10) ** -(self.decimals + 1)

    @property
    def rounding_tolerance(self) -> Decimal:
        """เกณฑ์ปัดเศษที่กฎผลรวมใช้กับค่านี้ — ครึ่งหลักสุดท้ายที่พิมพ์ **เฉพาะค่าในหน่วยที่ใหญ่กว่าบาท** (เช่น ล้านบาท)
        ซึ่งกฎ *สมมติ* ว่าแต่ละค่าถูกปัดจากบาทอย่างอิสระ (เอกสารไม่ได้ระบุวิธีปัด) · ค่าหน่วยบาทไม่ได้ปัด = 0 (เคร่งครัด)"""
        return self.tolerance if self.scale > 1 else Decimal(0)

    @property
    def needs_confirmation(self) -> bool:
        return any(f in CONFIRM_FLAGS for f in self.flags)


@dataclass
class Node:
    key: str
    level: str
    label: str
    parent: str
    order: int
    ev: Evidence
    no: str = ""          # เลขนำหน้าตามที่พิมพ์ (เช่น "2.1" · "7.2.1") ของการพบครั้งแรก


@dataclass
class Item:
    key: str
    node: str
    category: str
    label: str
    amount: str | None
    not_proposed: bool
    order: int
    ev: Evidence
    sub: bool = False     # หมวดย่อย (เช่น "3.1 ค่าครุภัณฑ์") — ไม่ใช่รายการ (1) (2)
    no: str = ""          # เลขนำหน้าตามที่พิมพ์ (เช่น "(1)" · "3.1")
    unit_origin: str = ""                 # row = คำหน่วยในแถว · assumed = สมมติเป็นบาท · "" = ไม่มียอด/รอบเก่า
    flags: list = field(default_factory=list)       # ธงของยอดรายการ (ดู ``CONFIRM_FLAGS``)


@dataclass
class Commitment:
    key: str
    node: str
    label: str
    total: str | None = None
    years: dict = field(default_factory=dict)        # ปีที่ตั้งงบประมาณแล้ว/ปีนี้ → บาท
    future: dict = field(default_factory=dict)       # ปีที่ผูกพันต่อไป → บาท
    ev: Evidence | None = None
    lines: list = field(default_factory=list)        # หลักฐานบรรทัดวงเงิน
    parts: dict = field(default_factory=dict)        # แหล่งเงินของวงเงินทั้งสิ้น (เงินงบประมาณ/เงินนอกงบประมาณ)
    line_keys: list = field(default_factory=list)    # ขนานกับ ``lines``: total · year:Y · future:Y · fund:<แหล่งเงิน>
    line_units: list = field(default_factory=list)   # ขนานกับ ``lines``: row (มีคำหน่วยในบรรทัด) · assumed (สมมติบาท)

    def line_of(self, key: str):
        """(หลักฐาน, ที่มาหน่วย) ของบรรทัดที่ให้ค่า ``key`` — รอบเก่าไม่มีข้อมูล = (บรรทัดวงเงินแรก/หลักฐานรายการ, "")"""
        for i, k in enumerate(self.line_keys):
            if k == key and i < len(self.lines):
                return self.lines[i], (self.line_units[i] if i < len(self.line_units) else "")
        return (self.lines[0] if self.lines else self.ev), ""


@dataclass
class Indicator:
    key: str
    scope: str            # "" = ระดับหน่วยงาน · กุญแจโหนด = ระดับผลผลิต/โครงการ
    name: str
    unit: str
    targets: dict         # ปี → ค่า (ข้อความ)
    order: int
    ev: Evidence
    table: str = ""       # ตารางที่พบ (ผลสัมฤทธิ์ · ประมาณการ · เป้าหมายผลผลิต) — ชื่อซ้ำต่างตารางไม่ชนกัน


@dataclass
class TextItem:
    section: str          # SEC_* หรือ "objective"
    scope: str
    no: str
    text: str
    order: int
    ev: Evidence

    @property
    def key(self) -> str:
        return text_key(self.text)


@dataclass
class Coverage:
    pages: list = field(default_factory=list)
    pages_no_text: list = field(default_factory=list)
    unparsed: list = field(default_factory=list)       # Evidence ของแถวที่มีตัวเลขแต่จัดไม่ได้
    sections_found: list = field(default_factory=list)
    repaired_words: int = 0                             # คำที่ตัวซ่อมข้อความไทยแก้ (สระอำ/ลำดับ/PUA)
    hidden_words: int = 0                               # คำที่อยู่นอกขอบหน้า (มองไม่เห็นบนหน้า) — ไม่นำมาใช้


@dataclass
class BookFacts:
    version: str
    profile: str
    fiscal_year: int | None
    stage: str            # draft | act | ""
    agency: str
    amounts: list = field(default_factory=list)
    nodes: dict = field(default_factory=dict)
    items: list = field(default_factory=list)
    commitments: list = field(default_factory=list)
    indicators: list = field(default_factory=list)
    texts: list = field(default_factory=list)
    coverage: Coverage = field(default_factory=Coverage)
    agency_title: str = ""                              # บรรทัดชื่อหน่วยงานต้นช่วง
    numbering: list = field(default_factory=list)       # [{section, node, no, ev}] ทุกครั้งที่พบโหนด
    headers: dict = field(default_factory=dict)         # "section:kind" → ชื่อคอลัมน์ตามลำดับ
    table_units: dict = field(default_factory=dict)     # section → หน่วยที่ประกาศในเล่ม
    row_labels: dict = field(default_factory=dict)      # กุญแจแถวที่ไม่ใช่โหนด (แหล่งเงิน ฯลฯ) → ป้าย
    dashes: list = field(default_factory=list)          # Amount(status="dash") — ช่องที่พิมพ์ขีด
    blanks: list = field(default_factory=list)          # Amount(status="blank") — แถวมีอยู่ แต่ช่องนี้ว่าง
    identity_issues: list = field(default_factory=list)  # [{kind, key, labels, ev, candidates}] ดู resolve_node_keys
    year_origin: str = ""                               # ที่มาของปีงบ (:class:`YearEvidence`)
    year_status: str = ""                               # ok · uncertain · conflict · not_found · "" = รอบเก่า
    year_candidates: list = field(default_factory=list)  # หลักฐานปีทั้งหมดที่พบ
    year_evidence: list = field(default_factory=list)   # หลักฐานต่อ candidate (หน้า·บรรทัด·คำบอก·อ่านตรง/อนุมาน·bbox)
    stage_status: str = ""                              # ok · conflict · not_found · "" = รอบเก่า (:class:`StageEvidence`)
    stage_origin: str = ""                              # title_line (บรรทัดชื่อเอกสาร) · register (ทะเบียนดาวน์โหลด) · ""
    stage_evidence: list = field(default_factory=list)  # [{kind, page, line, cue}] จากข้อความที่มองเห็น

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BookFacts":
        ev = lambda e: Evidence(e["page"], tuple(e["bbox"]), e["text"]) if e else None  # noqa: E731
        bf = cls(d["version"], d["profile"], d.get("fiscal_year"), d.get("stage", ""),
                 d.get("agency", ""))
        bf.agency_title = d.get("agency_title", "")
        bf.numbering = [{**x, "ev": ev(x["ev"])} for x in d.get("numbering", [])]
        bf.headers = d.get("headers", {})
        bf.table_units = d.get("table_units", {})
        bf.row_labels = d.get("row_labels", {})
        bf.year_origin = d.get("year_origin", "")
        bf.year_status = d.get("year_status", "")
        bf.year_candidates = list(d.get("year_candidates", []))
        bf.year_evidence = list(d.get("year_evidence", []))
        bf.stage_status = d.get("stage_status", "")
        bf.stage_origin = d.get("stage_origin", "")
        bf.stage_evidence = list(d.get("stage_evidence", []))
        amt = lambda a: Amount(**{**a, "ev": ev(a["ev"]), "unit_ev": ev(a.get("unit_ev")),  # noqa: E731
                                  "column_ev": ev(a.get("column_ev"))})
        bf.amounts = [amt(a) for a in d["amounts"]]
        bf.dashes = [amt(a) for a in d.get("dashes", [])]
        bf.blanks = [amt(a) for a in d.get("blanks", [])]
        bf.identity_issues = [{**x, "ev": ev(x.get("ev"))} for x in d.get("identity_issues", [])]
        bf.nodes = {k: Node(**{**n, "ev": ev(n["ev"])}) for k, n in d["nodes"].items()}
        bf.items = [Item(**{**i, "ev": ev(i["ev"])}) for i in d["items"]]
        bf.commitments = [Commitment(**{**c, "ev": ev(c["ev"]),
                                        "lines": [ev(x) for x in c.get("lines", [])]})
                          for c in d["commitments"]]
        bf.indicators = [Indicator(**{**i, "ev": ev(i["ev"])}) for i in d["indicators"]]
        bf.texts = [TextItem(**{**t, "ev": ev(t["ev"])}) for t in d["texts"]]
        c = d.get("coverage") or {}
        bf.coverage = Coverage(pages=c.get("pages", []), pages_no_text=c.get("pages_no_text", []),
                               unparsed=[ev(x) for x in c.get("unparsed", [])],
                               sections_found=c.get("sections_found", []),
                               repaired_words=c.get("repaired_words", 0),
                               hidden_words=c.get("hidden_words", 0))
        return bf


# ══════════════════════════════════════════════════════════════════════════════
_LEAD = re.compile(r"^\s*(\(\d+\)|\d+\)|\d+(?:\.\d+)*\.?)")


def lead_no(label: str) -> str:
    """เลขนำหน้าตามที่พิมพ์ — 7.2.1 · 2.2. · (3) · ไม่มีเลขนำหน้า = ข้อความว่าง"""
    m = _LEAD.match(clean(label))
    return m.group(1) if m else ""


def _ev(r: Row) -> Evidence:
    return Evidence(r.page, tuple(round(v, 1) for v in r.bbox), r.text)


def _sk(s: str) -> str:
    return skeleton(s)


def _starts(body: str, cues) -> bool:
    b = _sk(body)
    return any(b.startswith(_sk(c)) for c in cues)


def _contains(body: str, cues) -> bool:
    b = _sk(body)
    return any(_sk(c) in b for c in cues)


_CUES = dict(P.SECTION_CUES)
#: ลำดับการตรวจ — หัวข้อที่ใช้ "ขึ้นต้นด้วย" (สั้น) และ "มีอยู่ในบรรทัด" (ยาว)
#: 🔴 MTEF ต้องตรวจก่อน "เป้าหมายการให้บริการ" — เล่มจริงหัวข้อ 5 = "เป้าหมายการให้บริการหน่วยงาน
#: งบประมาณและประมาณการรายจ่ายล่วงหน้าระยะปานกลาง"
_ORDER = (("starts", P.SEC_VISION), ("starts", P.SEC_MISSION), ("starts", P.SEC_OUTCOME),
          ("contains", P.SEC_YEARS), ("contains", P.SEC_MTEF), ("starts", P.SEC_TARGET),
          ("contains", P.SEC_ECON), ("contains", P.SEC_DETAIL), ("offbudget", P.SEC_OFFBUDGET),
          ("contains", P.SEC_SUMMARY))


def _is_amount_cell(c) -> bool:
    """ช่องที่เป็นจำนวนเงินจริง — เลขปี 25xx ท้ายหัวข้อไม่นับ"""
    return c.value is not None and not P.YEAR_TOKEN.fullmatch((c.raw or "").lstrip("-"))


def section_of(r: Row, in_detail: bool = False) -> str:
    """หัวข้อเนื้อหา — มีเลขข้อนำหน้า (หรือหัวข้อรายละเอียดที่ไม่มีเลข) และไม่มีช่องจำนวนเงิน"""
    if any(_is_amount_cell(c) for c in r.cells):
        return ""
    m = P.HEADING_NO.match(r.text)
    body = m.group(2) if m else r.text
    if in_detail and m:
        if _contains(body, P.SUB_ACTIVITY_CUES):
            return P.SUB_ACTIVITY
        if _contains(body, P.SUB_OUTPUT_MTEF_CUES):
            return P.SUB_OUTPUT_MTEF
        for name, cues in P.SUB_TEXT_CUES:
            if _starts(body, cues):
                return "text:" + name
    if not m:
        # หัวข้อรายละเอียดตามงบรายจ่ายในเล่มจริงไม่มีเลขข้อ
        return P.SEC_DETAIL if _starts(body, _CUES[P.SEC_DETAIL]) else ""
    for how, sec in _ORDER:
        cues = _CUES[sec]
        if how == "starts" and _starts(body, cues):
            return sec
        if how == "contains" and _contains(body, cues):
            return sec
        if how == "offbudget" and (_starts(body, cues[:1]) or _contains(body, cues[1:])):
            return sec
    return ""


def _continues(r: Row, last: dict | None, allow_cells: bool = False) -> bool:
    """บรรทัดนี้เป็นบรรทัดต่อของระเบียนก่อน — หน้าเดียวกัน · ชิดกัน · ไม่ขึ้นต้นด้วยเลขข้อ"""
    if last is None or (r.cells and not allow_cells):
        return False
    ev = last.get("ev")
    if ev is None or ev.page != r.page:
        return False
    if P.HEADING_NO.match(r.text) or P.ITEM_NO.match(r.text):
        return False
    return (r.y0 - last.get("y1", ev.bbox[3])) <= 7.0


def _touch(rec: dict, r: Row) -> None:
    rec["y1"] = r.y1


def level_of(label: str) -> str:
    s = _sk(strip_number(label))
    for lvl, cues in P.LEVEL_CUES:
        for c in cues:
            if s.startswith(_sk(c)):
                return lvl
    return ""


def category_of(label: str) -> str:
    s = _sk(re.sub(r"^[\s\-–•]+", "", strip_number(label)))
    for c in P.CATEGORIES:
        if s.startswith(_sk(c)):
            return c
    return ""


def node_key(level: str, label: str) -> str:
    return f"{level}:{label_key(label)}"


def resolve_node_keys(recs: list[dict]) -> tuple[dict, list]:
    """กุญแจจริงของโหนดทุกครั้งที่พบ — ``(remap {กุญแจชั่วคราว: กุญแจจริง}, ปัญหาระบุตัว)``

    กติกา (ID = เส้นทาง เมื่อจำเป็น)

    1. ฐาน = ``ระดับ:label_key(ชื่อ)`` — ไม่ขึ้นกับลำดับในเล่ม (สลับลำดับ = จับคู่ได้เหมือนเดิม)
    2. ฐานเดียวกันพบใต้ **แม่ต่างกัน** ≥ 2 แบบ = คนละรายการ → ``ฐาน@กุญแจจริงของแม่``
       (ครอบคลุมทั้งชื่อซ้ำต่างแผนงาน และชื่อซ้ำต่างผลผลิต/โครงการในแผนงานเดียวกัน) ·
       "แม่ต่างกัน" ตัดสินด้วย **กุญแจจริงของแม่ (เส้นทางที่ระบุตัวแล้ว)** ไม่ใช่ชื่อแม่ — ลูกชื่อเดียวกันใต้แม่
       ชื่อเดียวกันที่อยู่คนละแผนงานจึงเป็นคนละรายการ (REVIEW 6360210542)
    3. ครั้งที่พบโดยไม่มีแม่ (เช่น ตารางที่ไม่แสดงลำดับชั้น) หรือแม่เองระบุตัวไม่ได้ ของฐานที่แยกตามข้อ 2 แล้ว
       = **กำกวม** → คงกุญแจฐาน และบันทึก ``ambiguous_parent`` (ไม่เดาว่าเป็นของแม่ใด)
    4. กุญแจเดียวกันแต่ชื่อจริง (คงสระ/วรรณยุกต์ · :func:`text.exact_key`) ต่างกัน = รวมเป็นรายการเดียว
       ตามโครงคำ แต่บันทึก ``skeleton_merge`` ให้เห็น
    """
    by_tmp = {r["key"]: r for r in recs}
    base = {r["key"]: node_key(r["level"], r["label"]) for r in recs}
    occ_of: dict[str, list] = {}
    for r in recs:
        occ_of.setdefault(base[r["key"]], []).append(r)
    memo: dict[str, tuple] = {}         # กุญแจชั่วคราว → (กุญแจจริง, กำกวม)
    anchored: dict[str, set] = {}       # ฐาน → กุญแจจริงของแม่ที่ระบุตัวได้ (ทุกครั้งที่พบ)

    def parents_of(b: str, depth: int) -> set:
        if b not in anchored:
            anchored[b] = set()         # กันวนซ้ำ (ข้อมูลที่แม่ชี้กลับมาที่ลูก)
            got = set()
            for r in occ_of[b]:
                if r["parent"] in by_tmp:
                    pk, loose = resolve(r["parent"], depth + 1)
                    if not loose:
                        got.add(pk)
            anchored[b] = got
        return anchored[b]

    def resolve(tmp: str, depth: int = 0) -> tuple:
        if tmp in memo:
            return memo[tmp]
        r, b = by_tmp[tmp], base[tmp]
        out = (b, False)
        if depth < 12 and len(parents_of(b, depth)) > 1:
            if r["parent"] in by_tmp:
                pk, loose = resolve(r["parent"], depth + 1)
                out = (b, True) if loose else (f"{b}@{pk}", False)
            else:
                out = (b, True)
        memo[tmp] = out
        return out
    final = {r["key"]: resolve(r["key"])[0] for r in recs}

    issues: list = []
    for r in recs:
        if not memo[r["key"]][1]:
            continue
        b = base[r["key"]]
        cands = sorted({final[x["key"]] for x in occ_of[b] if not memo[x["key"]][1]})
        issues.append({"kind": "ambiguous_parent", "key": b, "ev": r["ev"],
                       "labels": [clean(strip_number(r["label"]))], "candidates": cands,
                       "note": f"ชื่อนี้พบใต้รายการแม่ {len(anchored[b])} แบบ แต่แถวนี้ไม่ระบุแม่ "
                               "(หรือแม่เองระบุตัวไม่ได้) — ค่าของแถวนี้ไม่ถูกผูกกับรายการใดรายการหนึ่ง"})
    exact: dict[str, dict] = {}
    occ: dict[str, list] = {}
    for r in recs:
        exact.setdefault(final[r["key"]], {}).setdefault(exact_key(r["label"]), r)
        occ.setdefault(final[r["key"]], []).append(r)
    for k, variants in exact.items():
        if len(variants) > 1:
            rs = list(variants.values())
            issues.append({"kind": "skeleton_merge", "key": k, "ev": rs[1]["ev"],
                           "labels": [clean(strip_number(x["label"])) for x in rs],
                           "occurrences": [{"label": clean(strip_number(x["label"])), "ev": x["ev"]}
                                           for x in occ[k]],
                           "candidates": [], "note": "ชื่อเหล่านี้ต่างกันที่สระ/วรรณยุกต์ แต่โครงคำเดียวกัน — "
                                                     "ระบบแยกไม่ได้ว่าเป็นรายการเดียวหรือคนละรายการ · ค่าเงินและ"
                                                     "ผลรวมที่พึ่งพารายการนี้ติดธงต้องให้คนยืนยันทุกข้อ"})
    # ลูกหลานของแถวที่ระบุตัวไม่ได้ / ของรายการที่โครงคำชนกัน: กุญแจของลูกขึ้นกับแม่ จึงอาจรวมคนละรายการ
    # → ส่งต่อปัญหาลงไปทุกชั้น (ตามแถวที่พบจริง ไม่ขึ้นกับลำดับ) — ไม่ทำข้อสังเกตแยก แต่ทุกค่าที่ผูกกับลูกต้องยืนยัน
    coll = {x["key"] for x in issues if x["kind"] == "skeleton_merge"}
    inherited: dict[str, str] = {}
    grew = True
    while grew:
        grew = False
        for r in recs:
            p, t = r["parent"], r["key"]
            if p not in by_tmp or t in inherited or memo[t][1]:
                continue
            kind = ("parent_unidentified" if memo[p][1] or inherited.get(p) == "parent_unidentified" else
                    "parent_collision" if final[p] in coll or inherited.get(p) == "parent_collision" else "")
            if kind:
                inherited[t], grew = kind, True
    for t, kind in inherited.items():
        r = by_tmp[t]
        issues.append({"kind": kind, "key": final[t], "ev": r["ev"], "labels": [clean(strip_number(r["label"]))],
                       "candidates": [], "note": INHERITED_NOTES[kind]})
    return final, issues


#: ปัญหาระบุตัวที่สืบทอดจากรายการแม่ (ไม่ทำข้อสังเกตแยก — ทุกค่าที่ผูกกับรายการนั้นติดธงต้องยืนยัน)
INHERITED_NOTES = {
    "parent_unidentified": "รายการแม่ของแถวนี้ระบุตัวไม่ได้ — ระบบผูกแถวนี้กับรายการชื่อเดียวกัน ซึ่งอาจเป็นคนละรายการ",
    "parent_collision": "รายการแม่ของแถวนี้มีชื่อที่โครงคำชนกัน — ลูกชื่อเดียวกันของแม่คนละรายการอาจถูกรวมเป็นรายการเดียว",
}
#: ชนิดปัญหาระบุตัว → ธงของทุกค่าที่ผูกกับรายการนั้น
ISSUE_FLAGS = {"skeleton_merge": "identity_collision", "parent_collision": "identity_collision",
               "ambiguous_parent": "identity_ambiguous", "parent_unidentified": "identity_ambiguous"}


def node_flags(bf: "BookFacts") -> dict:
    """กุญแจโหนด → ธงระบุตัว — ใช้ติดธงทุกระเบียนที่ผูกกับโหนด (รายการ · รายการผูกพัน · ตัวชี้วัด · ข้อความ · โครงสร้าง)"""
    out: dict[str, list] = {}
    for x in bf.identity_issues:
        fl = ISSUE_FLAGS.get(x.get("kind"))
        if fl and fl not in out.setdefault(x["key"], []):
            out[x["key"]].append(fl)
    return out


def _node_of(key: str) -> str:
    """กุญแจโหนดของระเบียน (แถวแหล่งเงิน ``node|row`` → ``node``)"""
    return key.split("|", 1)[0] if "|" in key and not key.startswith("off:") else key


def mark_identity(bf: "BookFacts") -> None:
    """ส่งต่อปัญหาระบุตัวไปยังทุกระเบียนที่พึ่งพา — ไม่รวมเงียบ ไม่ทิ้ง occurrence

    * โหนดที่โครงคำชนกัน (``skeleton_merge``) หรือลูกหลานของโหนดนั้น → ค่าเงิน/ขีด/ช่องว่าง/ยอดรายการติด
      ``identity_collision``
    * ครั้งที่พบโดยไม่ระบุแม่ (``ambiguous_parent``) หรือลูกหลานของแถวนั้น → ติด ``identity_ambiguous``
    * ช่องเดียวกัน (ตาราง·โหนด·คอลัมน์) มีหลายค่าที่ต่างกัน = **duplicate_cell**: เก็บทุกค่าไว้ใน
      ``amounts`` + ปัญหาระบุตัวที่แสดงทุกค่า + ติด ``identity_collision`` ทุกค่า (ตัวเทียบใช้ได้ค่าเดียว
      จึงต้องให้คนยืนยัน — ไม่ปล่อยให้ค่าหนึ่งหายเงียบ)
    """
    nf = node_flags(bf)
    for a in list(bf.amounts) + list(bf.dashes) + list(bf.blanks) + list(bf.items):
        for flag in nf.get(_node_of(a.node), ()):
            if flag not in a.flags:
                a.flags.append(flag)
    groups: dict[tuple, list] = {}
    for a in bf.amounts:
        groups.setdefault((a.table, a.node, a.column), []).append(a)
    for (table, node, col), xs in groups.items():
        if len({x.dec for x in xs}) <= 1:
            continue
        for x in xs:
            if "identity_collision" not in x.flags:
                x.flags.append("identity_collision")
        bf.identity_issues.append({
            "kind": "duplicate_cell", "key": f"{table}|{node}|{col}", "ev": xs[1].ev,
            "labels": [f"{x.raw} (หน้า {x.ev.page})" for x in xs], "candidates": [],
            "occurrences": [{"label": x.raw, "ev": x.ev} for x in xs],
            "note": f"ช่องเดียวกันพบ {len(xs)} ค่าที่ต่างกัน — อาจเป็นคนละรายการที่ระบบรวมกุญแจ "
                    "ระบบเทียบได้เพียงค่าเดียว ผลที่พึ่งพาช่องนี้ต้องให้คนยืนยัน"})


def _strip_dash(label: str) -> str:
    return re.sub(r"^[\s\-–•]+", "", label)


def _amt(bf: "BookFacts", table: str, node: str, col: str, cell, r: Row, *, unit: str, unit_origin: str,
         unit_ev=None, column_origin: str, column_ev=None) -> None:
    """บันทึกค่าเงินหนึ่งช่องพร้อมที่มา — ขีด = ``bf.dashes`` (status dash) · ตัวเลข = ``bf.amounts``"""
    flags = []
    if unit_origin not in UNIT_ORIGINS_IN_DOCUMENT:
        flags.append("unit_not_in_document")
    flags += {"nearest_column": ["column_nearest"], "book_year": ["year_from_book_meta"],
              "header_two_line": ["header_two_line"], "range_header": ["range_header"]}.get(column_origin, [])
    ev = _ev(r)
    if cell.value is None:
        if clean(cell.raw) in DASH_TOKENS:
            bf.dashes.append(Amount(table, node, col, "", unit, cell.raw, ev, unit_origin, column_origin,
                                    flags, "dash", unit_ev, column_ev or ev))
        return
    bf.amounts.append(Amount(table, node, col, str(cell.value), unit, cell.raw, ev, unit_origin,
                             column_origin, flags, "read", unit_ev, column_ev or ev))


def _detail_amt(bf: "BookFacts", node: str, col: str, cell, r: Row) -> None:
    """ยอดในรายละเอียด — คอลัมน์ได้จากป้ายของแถว (หมวด/แหล่งเงิน/รวม)"""
    unit, uo = _row_unit(r)
    _amt(bf, P.SEC_DETAIL, node, col, cell, r, unit=unit, unit_origin=uo,
         unit_ev=_ev(r) if uo == "row" else None, column_origin="label")


def _row_unit(r: Row) -> tuple:
    """หน่วยของแถว — คำหน่วยในแถว (มีในเอกสาร) หรือ "บาท" ที่สมมติ (ไม่มีในเอกสาร)"""
    return (r.unit_word, "row") if r.unit_word else ("บาท", "assumed")


def _col_origin(st: "_State", col: str, nearest: set) -> str:
    if col in nearest:
        return "nearest_column"
    if "–" in col:
        return "range_header"
    return "header_two_line" if st.header_two_line else "header"


class _State:
    def __init__(self):
        self.section = ""
        self.sub = ""               # ตารางย่อยในรายละเอียด (กิจกรรม · เป้าหมายผลผลิต)
        self.cols: list[Column] = []
        self.pending: tuple | None = None   # (คอลัมน์, page, y1) ของหัวตารางบรรทัดบนที่ยังไม่ครบ
        self.table_kind = ""        # amounts | indicator
        self.unit = ""
        self.unit_origin = ""       # table_decl · profile_default (ของ st.unit)
        self.unit_ev = None
        self.header_ev = None       # บรรทัดหัวตารางที่ใช้อยู่
        self.header_two_line = False
        self.plan = ""
        self.node = ""              # โหนดปัจจุบันในรายละเอียด / ตาราง
        self.group = ""             # หัวกลุ่มของแถวที่ไม่ใช่โหนด (เช่น เป้าหมายการให้บริการในตารางประมาณการ)
        self.off_path: dict = {}    # ตารางเงินนอกงบประมาณ: ความลึกของเลขข้อ → ชื่อ (ใช้ระบุแม่ของ 6.1.1)
        self.category = ""
        self.last = None            # ระเบียนล่าสุดที่ต่อบรรทัดได้ (dict)
        self.last_item: Item | None = None
        self.last_item_y1 = 0.0
        self.commit: Commitment | None = None
        self.in_commit = False
        self.order = 0
        self.title_rows: list = []

    def next_order(self) -> int:
        self.order += 1
        return self.order

    @property
    def table(self) -> str:
        return self.sub or self.section


def _visible(pt):
    """ตัดคำที่อยู่นอกขอบหน้า — เล่มจริงที่ส่งออกจาก Excel มีข้อความของหน้าถัดไปซ่อนอยู่นอกกระดาษ"""
    from dataclasses import replace
    inside = tuple(w for w in pt.words
                   if 0 <= (w.x0 + w.x1) / 2 <= pt.width and 0 <= (w.y0 + w.y1) / 2 <= pt.height)
    return replace(pt, words=inside), len(pt.words) - len(inside)


def visible_text(pt) -> str:
    """ข้อความหน้าเป็นบรรทัด **เฉพาะที่มองเห็นบนกระดาษ** — ใช้หาปีงบ (ข้อความดิบของ PDF รวมข้อความที่ซ่อน
    นอกขอบหน้า ซึ่งคนตรวจมองไม่เห็นและไม่ใช่หลักฐาน)"""
    pt, _hidden = _visible(pt)
    return chr(10).join(r.text for r in rows_of_page(pt))


def extract(pages, *, fiscal_year: int | None = None, stage: str = "",
            agency: str = "") -> BookFacts:
    """``pages`` = รายการ ``PageText`` ของช่วงหน้าหน่วยงาน (ตามลำดับ)"""
    bf = BookFacts(PDFBOOK_VERSION, P.PROFILE_VERSION, fiscal_year, stage, agency)
    st = _State()
    found = set()
    pending_ind: list[dict] = []
    pending_txt: list[dict] = []
    pending_nodes: list[dict] = []

    def add_node(level, label, r, parent=""):
        # กุญแจชั่วคราวต่อระเบียน — คำนวณกุญแจจริงตอนจบ (ชื่อยาวต่อบรรทัดครบแล้ว · ชื่อซ้ำต่างแผนงานแยกกัน)
        rec = {"level": level, "label": label, "parent": parent, "ev": _ev(r),
               "key": f"tmp{len(pending_nodes)}", "order": st.next_order(), "section": st.table}
        pending_nodes.append(rec)
        return rec

    for pt in pages:
        bf.coverage.pages.append(pt.page)
        if not pt.has_text_layer:
            bf.coverage.pages_no_text.append(pt.page)
            continue
        pt, hidden = _visible(pt)
        bf.coverage.hidden_words += hidden
        bf.coverage.repaired_words += sum(1 for w in pt.words if _thai_repair(w.text) != w.text)
        for r in rows_of_page(pt):
            if r.y0 < TOP_MARGIN_PT or r.y1 > pt.height - BOTTOM_MARGIN_PT:
                continue
            if _PAGE_NO.match(squash(r.text)) or any(w in r.text for w in _WATERMARK):
                continue
            _consume(r, st, bf, found, pending_ind, pending_txt, add_node)

    # ── ปิดงาน: คำนวณกุญแจหลังต่อบรรทัดครบ ────────────────────────────────────
    remap, issues = resolve_node_keys(pending_nodes)
    bf.identity_issues.extend(issues)
    for rec in pending_nodes:
        k = remap[rec["key"]]
        parent = remap.get(rec["parent"], rec["parent"])
        bf.numbering.append({"section": rec.get("section", ""), "node": k,
                             "no": lead_no(rec["label"]), "ev": rec["ev"]})
        if k not in bf.nodes:
            bf.nodes[k] = Node(k, rec["level"], strip_number(rec["label"]), parent,
                               rec["order"], rec["ev"], no=lead_no(rec["label"]))
        elif parent and not bf.nodes[k].parent:
            bf.nodes[k].parent = parent

    def rm(key: str) -> str:
        if "|" in key and not key.startswith("off:"):
            head, rest = key.split("|", 1)
            return f"{remap.get(head, head)}|{rest}"
        return remap.get(key, key)
    for a in list(bf.amounts) + list(bf.dashes) + list(bf.blanks):
        a.node = rm(a.node)
    bf.row_labels = {rm(k): v for k, v in bf.row_labels.items()}
    for it in bf.items:
        it.node = remap.get(it.node, it.node)
    for c in bf.commitments:
        if c.key.startswith("node:"):
            c.key = "node:" + remap.get(c.key[5:], c.key[5:])
        c.node = remap.get(c.node, c.node)
    seen_ind: dict = {}
    for rec in pending_ind:
        k = (remap.get(rec["scope"], rec["scope"]), rec.get("table", ""), label_key(rec["name"]))
        if k in seen_ind:
            bf.identity_issues.append({
                "kind": "duplicate_indicator", "key": "|".join(k), "ev": rec["ev"],
                "labels": [clean(seen_ind[k]), clean(rec["name"])],
                "note": "ตัวชี้วัดชื่อเดียวกัน (โครงคำ) ซ้ำในตารางเดียวกัน — ระบบเทียบได้เพียงรายการเดียว"})
        seen_ind[k] = rec["name"]
        bf.indicators.append(Indicator(
            key=label_key(rec["name"]), scope=remap.get(rec["scope"], rec["scope"]),
            name=clean(rec["name"]), unit=clean(rec["unit"]), targets=rec["targets"],
            order=rec["order"], ev=rec["ev"], table=rec.get("table", "")))
    for rec in pending_txt:
        if clean(rec["text"]):
            bf.texts.append(TextItem(rec["section"], remap.get(rec["scope"], rec["scope"]),
                                     rec["no"], clean(rec["text"]), rec["order"], rec["ev"]))
    if not bf.agency_title and st.title_rows:
        bf.agency_title = " ".join(st.title_rows)
    bf.coverage.sections_found = sorted(found)
    mark_identity(bf)
    return bf


def _header(r: Row, st: _State, bf: BookFacts) -> bool:
    """บรรทัดหัวตาราง (รวมหัวตารางสองบรรทัด) — True = ใช้บรรทัดนี้ไปแล้ว"""
    if any(_is_amount_cell(c) for c in r.cells):
        return False
    cols = header_columns(r)
    pend = st.pending if (st.pending and st.pending[1] == r.page
                          and r.y0 - st.pending[2] <= 40) else None
    if cols:
        st.header_two_line = bool(pend)
        if pend:
            have = {c.name for c in cols}
            cols = sorted(cols + [c for c in pend[0] if c.name not in have], key=lambda c: c.x0)
        cols = _range_columns(r, cols)
        st.header_ev = _ev(r)
        if st.sub == P.SUB_ACTIVITY and any(c.kind == "num" and c.name[:4].isdigit() for c in cols):
            st.sub = P.SUB_OUTPUT_MTEF        # หัวข้อตารางเป้าหมาย/ประมาณการแตกบรรทัด — หัวปีบอกชนิดตาราง
        st.cols, st.pending = cols, None
        st.header_y = (r.page, r.y1)
        texty = any(c.kind == "text" for c in cols)
        st.table_kind = "indicator" if (texty and st.section in (P.SEC_OUTCOME, P.SEC_TARGET)) or \
            any(squash(x) in squash(r.text) for x in P.INDICATOR_HEADER_CUES) and texty else "amounts"
        bf.headers.setdefault(f"{st.table}:{st.table_kind}", [c.name for c in cols])
        st.last = None
        return True
    partial = _partial_columns(r)
    if partial:
        hy = getattr(st, "header_y", None)
        if st.cols and hy and hy[0] == r.page and r.y0 - hy[1] <= 30                 and all(c.kind == "text" for c in partial):
            # หัวตารางบรรทัดล่าง (เช่น "หน่วยนับ" อยู่ใต้บรรทัดปี) — รวมเข้าหัวตารางที่ตั้งไว้แล้ว
            have = {c.name for c in st.cols}
            st.cols = sorted(st.cols + [c for c in partial if c.name not in have], key=lambda c: c.x0)
            st.header_two_line = True
            if st.section in (P.SEC_OUTCOME, P.SEC_TARGET):
                st.table_kind = "indicator"
            bf.headers[f"{st.table}:{st.table_kind}"] = [c.name for c in st.cols]
            st.header_y = (r.page, r.y1)
            return True
        st.pending = (partial, r.page, r.y1)
        return True
    return False


def _range_columns(r: Row, cols: list) -> list:
    """คอลัมน์ "เริ่มต้น - ปี 2569" (สะสมตั้งแต่เริ่ม) และ "ปี 2573 - จบ" — ไม่ใช่ปีเดี่ยว"""
    from dataclasses import replace as _rp
    years = [c for c in cols if c.kind == "num" and c.name.isdigit()]
    if not years:
        return cols
    first, last = years[0], years[-1]
    start_x = [w.x0 for w in r.words if _sk(w.text).startswith(_sk("เริ่มต้น"))]
    end_x = [w.x0 for w in r.words if _sk(w.text) == _sk("จบ")]
    out = []
    for c in cols:
        if c is first and start_x and min(start_x) < c.x0:
            c = _rp(c, name=f"เริ่มต้น–{c.name}", x0=min(start_x))
        elif c is last and end_x and max(end_x) > c.x1:
            c = _rp(c, name=f"{c.name}–จบ", x1=max(end_x) + 10)
        out.append(c)
    return out


def _partial_columns(r: Row) -> list:
    """คอลัมน์ที่ยังไม่พอเป็นหัวตาราง (ปีเดียว · หน่วยนับ) — เก็บไว้รวมกับบรรทัดถัดไป"""
    from .layout import Column as _C, _column_name
    out = []
    for w in r.words:
        name, kind = _column_name(squash(w.text))
        if name:
            out.append(_C(name, w.x0, w.x1, kind))
    return out if out and len(out) <= 2 else []


def _consume(r: Row, st: _State, bf: BookFacts, found: set, pending_ind, pending_txt, add_node):
    if _ANNOTATION.match(squash(r.text)):
        return                                   # (478,021) · (-) · แผน — ข้อมูลกำกับใต้ค่า
    if r.text.lstrip().startswith("*") or _sk(r.text).startswith(_sk("หมายเหตุ")):
        return                                   # เชิงอรรถใต้ตาราง
    sec = section_of(r, in_detail=st.section == P.SEC_DETAIL)
    if sec.startswith("text:"):
        # วัตถุประสงค์ / สถานที่ดำเนินการ / ระยะเวลาดำเนินการ ของโครงการ — บรรทัดถัดไปเป็นเนื้อความ
        name = sec[5:]
        body = P.HEADING_NO.match(r.text).group(2)
        rest = re.sub(r"^\s*(?:วัตถุประสงค์|สถานที่ดำเนินการ|ระยะเวลาดำเนินการ)\s*[:：]?\s*", "", clean(body))
        st.sub, st.cols, st.pending = "", [], None
        rec = {"kind": "text", "section": name, "scope": st.node, "no": "", "text": rest,
               "order": st.next_order(), "ev": _ev(r)}
        pending_txt.append(rec)
        _touch(rec, r)
        st.last = rec
        return
    if sec in (P.SUB_ACTIVITY, P.SUB_OUTPUT_MTEF):
        st.sub, st.cols, st.pending, st.table_kind, st.last = sec, [], None, "", None
        st.unit, st.unit_origin, st.unit_ev = TABLE_UNIT_DEFAULT.get(sec, ""), "profile_default", None
        found.add(sec)
        return
    if sec:
        st.section, st.sub, st.cols, st.pending, st.table_kind, st.last = sec, "", [], None, "", None
        st.unit, st.unit_origin, st.unit_ev = TABLE_UNIT_DEFAULT.get(sec, ""), "profile_default", None
        st.in_commit, st.commit, st.group = False, None, ""
        if sec != P.SEC_DETAIL:
            st.node = ""
        found.add(sec)
        return

    m_unit = P.UNIT_DECL.search(r.text)
    if m_unit and not any(_is_amount_cell(c) for c in r.cells):
        st.unit, st.unit_origin, st.unit_ev = m_unit.group(1), "table_decl", _ev(r)
        bf.table_units.setdefault(st.table, st.unit)
        return

    # ต้นช่วงของหน่วยงาน: ชื่อ · ตาราง "งบประมาณ | ปี … | ปี …" · งบประมาณรายจ่าย/เงินนอกงบประมาณ
    if not st.section:
        _head_row(r, st, bf)
        return

    if st.sub and level_of(r.label) and P.HEADING_NO.match(r.text) and not r.cells:
        st.sub, st.cols, st.pending = "", [], None      # หัวข้อผลผลิต/โครงการถัดไป — จบตารางย่อย
    if st.sub in (P.SUB_ACTIVITY, P.SUB_OUTPUT_MTEF) or st.section in (
            P.SEC_SUMMARY, P.SEC_ECON, P.SEC_MTEF, P.SEC_OFFBUDGET, P.SEC_YEARS):
        if _header(r, st, bf):
            return
        if st.section == P.SEC_ECON and not st.cols:
            _econ_list_row(r, st, bf)
            return
        _table_row(r, st, bf, add_node, pending_ind)
        return

    if st.section in (P.SEC_VISION, P.SEC_MISSION, P.SEC_OUTCOME, P.SEC_TARGET):
        if _header(r, st, bf):
            return
        if st.cols and r.cells:
            _indicator_row(r, st, "", pending_ind)
        elif st.cols and st.last is not None and st.last.get("kind") == "ind" and _continues(r, st.last):
            st.last["name"] = join_wrapped(st.last["name"], label_without_text_columns(r, st.cols))
            _touch(st.last, r)
        elif st.cols and not (P.HEADING_NO.match(r.text) or P.ITEM_NO.match(r.text)) and not (
                st.last is not None and st.last.get("kind") == "text" and _continues(r, st.last)):
            return                               # หัวตารางผลสัมฤทธิ์/ค่าเป้าหมายบรรทัดอื่น
        elif _header_words_only(r):
            return                               # หัวตารางบรรทัดบนที่ยังไม่มีปี (ก่อนตั้งคอลัมน์) — ไม่ใช่เนื้อความ
        else:
            _text_row(r, st, st.section, "", pending_txt)
        return

    if st.section == P.SEC_DETAIL:
        if any(c.kind == "text" for c in header_columns(r)) and _header(r, st, bf):
            return                                   # หัวตารางตัวชี้วัดของผลผลิต/โครงการ
        _detail_row(r, st, bf, pending_ind, pending_txt, add_node)
        return


def _head_row(r: Row, st: _State, bf: BookFacts):
    s = _sk(r.label)
    cols = header_columns(r)
    if cols and not any(_is_amount_cell(c) for c in r.cells):
        st.cols, st.header_ev, st.header_two_line = cols, _ev(r), False
        return
    for cue, node in ((P.BUDGET_HEADER_CUE, "budget"), (P.OFFBUDGET_HEADER_CUE, "offbudget")):
        if s.startswith(_sk(cue)) and r.cells:
            unit, uo = _row_unit(r)
            near: set = set()
            got = assign(r, st.cols, near)[0] if st.cols else {}
            by_meta = False
            if not got and r.cells[-1].value is not None:
                got, by_meta = {str(bf.fiscal_year or ""): r.cells[-1]}, True   # ปีจากข้อมูลเล่ม ไม่ใช่หัวตาราง
            for col, c in got.items():
                _amt(bf, "header", node, col, c, r, unit=unit, unit_origin=uo,
                     unit_ev=_ev(r) if uo == "row" else None,
                     column_origin="book_year" if by_meta else _col_origin(st, col, near),
                     column_ev=None if by_meta else st.header_ev)
            return
    if not r.cells:
        if not st.cols and not s.startswith(_sk("หมายเหตุ")):
            st.title_rows.append(r.text)            # กระทรวง · ชื่อหน่วยงาน (ก่อนตารางต้นช่วง)
        return
    bf.coverage.unparsed.append(_ev(r))


def _econ_list_row(r: Row, st: _State, bf: BookFacts):
    """6.1 จำแนกตามลักษณะรายจ่าย แบบรายการ: งบประมาณรายจ่าย / รายจ่ายประจำ / รายจ่ายลงทุน"""
    s = _sk(_strip_dash(r.label))
    col = (P.ECON_RECURRENT if s.startswith(_sk(P.ECON_RECURRENT)) else
           P.ECON_CAPITAL if s.startswith(_sk(P.ECON_CAPITAL)) else
           P.COL_TOTAL if s.startswith(_sk(P.BUDGET_HEADER_CUE)) else "")
    if not col or not r.cells:
        if r.cells:
            bf.coverage.unparsed.append(_ev(r))
        return
    unit, uo = _row_unit(r)
    _amt(bf, P.SEC_ECON, "total", col, r.cells[-1], r, unit=unit, unit_origin=uo,
         unit_ev=_ev(r) if uo == "row" else None, column_origin="label")


def _header_words_only(r: Row) -> bool:
    """บรรทัดที่มี **แต่** คำหัวตาราง (``P.TABLE_HEADER_WORDS``) ไม่มีเลขข้อ ไม่มีตัวเลข — เช่น "ผลสัมฤทธิ์ | ค่าเป้าหมาย"
    บรรทัดบนของหัวตารางสามบรรทัด ซึ่งมาก่อนบรรทัดที่มีปี (แบบทวนระเบียนกับภาพ #42: เคยถูกบันทึกเป็นข้อความผลสัมฤทธิ์)"""
    if r.cells or P.HEADING_NO.match(r.text) or P.ITEM_NO.match(r.text):
        return False
    vocab = {skeleton(x) for x in P.TABLE_HEADER_WORDS}
    words = [skeleton(w.text) for w in r.words if skeleton(w.text)]
    return bool(words) and all(w in vocab for w in words)


def _text_row(r: Row, st: _State, section: str, scope: str, pending_txt):
    m = P.HEADING_NO.match(r.text) or P.ITEM_NO.match(r.text)
    if m and (st.last is None or st.last.get("kind") != "text" or section != P.SEC_VISION
              or "." in m.group(1)):
        rec = {"kind": "text", "section": section, "scope": scope, "no": lead_no(r.text),
               "text": m.group(2), "order": st.next_order(), "ev": _ev(r)}
        pending_txt.append(rec)
        _touch(rec, r)
        st.last = rec
        return
    if st.last is not None and st.last.get("kind") == "text" and \
            (r.page != st.last["ev"].page or _continues(r, st.last)):
        st.last["text"] = join_wrapped(st.last["text"], r.text)
        e = st.last["ev"]
        if e.page == r.page:
            st.last["ev"] = Evidence(e.page, (e.bbox[0], e.bbox[1], max(e.bbox[2], r.x1), r.y1),
                                     e.text + " " + r.text)
        _touch(st.last, r)
        return
    rec = {"kind": "text", "section": section, "scope": scope, "no": "", "text": r.text,
           "order": st.next_order(), "ev": _ev(r)}
    pending_txt.append(rec)
    _touch(rec, r)
    st.last = rec


_IND_PREFIX = re.compile(r"^[\s\-–•]*(?:\d+(?:\.\d+)*\.?\s*)?(?:ตัวชี้วัด\s*[:：]?\s*)?")


def _indicator_row(r: Row, st: _State, scope: str, pending_ind, texts=None, got=None):
    if got is None:
        got, _loose, texts = assign(r, st.cols)
    name = _IND_PREFIX.sub("", label_without_text_columns(r, st.cols))
    # ทุกคอลัมน์ตัวเลขที่มีค่าเก็บไว้ — รวมช่วงปี "เริ่มต้น–2569" (ผลสะสม) และ "2573–จบ" (แบบทวนระเบียนกับภาพ #42:
    # เดิมเก็บเฉพาะปีเดี่ยว ค่าในคอลัมน์ช่วงปีหายเงียบ และถ้าสองฉบับต่างกันที่คอลัมน์นั้นจะไม่มีข้อสังเกต)
    rec = {"kind": "ind", "scope": scope, "name": name, "unit": (texts or {}).get("หน่วยนับ", ""),
           "targets": {k: c.raw for k, c in got.items()},
           "order": st.next_order(), "ev": _ev(r), "table": st.table}
    pending_ind.append(rec)
    _touch(rec, r)
    st.last = rec


def _off_key(st: "_State", label: str) -> str:
    """กุญแจแถวตารางเงินนอกงบประมาณ — ชื่อซ้ำใต้หัวข้อต่างกัน (6.1.1 รายจ่ายประจำ ใต้ภารกิจพื้นฐาน ·
    6.2.1 ใต้ภารกิจเพื่อการพัฒนา) = คนละรายการ → รวมชื่อแม่ตามเลขข้อ (ชั้นที่ 3 ขึ้นไป) · ชั้น 1–2 คงกุญแจเดิม"""
    name = clean(strip_number(label))
    no = lead_no(label)
    depth = len([x for x in no.strip(".()").split(".") if x]) if no else 0
    if depth:
        st.off_path = {d: v for d, v in st.off_path.items() if d < depth}
        st.off_path[depth] = name
    parent = st.off_path.get(depth - 1, "") if depth >= 3 else ""
    return "off:" + (f"{parent} › {name}" if parent else name)


def _table_row(r: Row, st: _State, bf: BookFacts, add_node, pending_ind):
    if not st.cols:
        if r.cells:
            bf.coverage.unparsed.append(_ev(r))
        return
    near: set = set()
    got, loose, texts = assign(r, st.cols, near)
    label = label_without_text_columns(r, st.cols) if any(c.kind == "text" for c in st.cols) else r.label
    nums = [c for c in st.cols if c.kind == "num"]
    if nums and loose:
        left_edge = min(c.x0 for c in nums) - 30.0
        in_label = [c for c in loose if c.x1 < left_edge]
        if in_label:
            loose = [c for c in loose if c not in in_label]
            label = clean(label + " " + " ".join(c.raw for c in in_label))
    if not got:
        if label and st.last is not None and st.last.get("kind") in ("node", "row", "ind") \
                and _continues(r, st.last):
            k = "name" if st.last.get("kind") == "ind" else "label"
            st.last[k] = join_wrapped(st.last[k], label)            # ชื่อยาวต่อบรรทัด
            if st.last.get("kind") == "row" and st.last["key"] == f"grp:{st.group}" and st.group:
                # หัวกลุ่มที่ห่อบรรทัด — กุญแจกลุ่มจากชื่อเต็ม (กลุ่ม 2/4/5 ที่บรรทัดแรกเหมือนกันต้องไม่ชนกัน)
                bf.row_labels.pop(st.last["key"], None)
                st.group = label_key(st.last["label"])
                st.last["key"] = f"grp:{st.group}"
            if st.last.get("kind") == "row":
                bf.row_labels[st.last["key"]] = clean(st.last["label"])
            _touch(st.last, r)
        elif loose:
            bf.coverage.unparsed.append(_ev(r))
        elif label and st.table in (P.SEC_MTEF, P.SUB_OUTPUT_MTEF, P.SEC_YEARS):
            st.group = label_key(label)                           # หัวกลุ่ม (เช่น เป้าหมายการให้บริการ)
            bf.row_labels[f"grp:{st.group}"] = clean(label)
            st.last = {"kind": "row", "key": f"grp:{st.group}", "label": label, "ev": _ev(r)}
            _touch(st.last, r)
        return
    if loose:
        bf.coverage.unparsed.append(_ev(r))
    unit_txt = texts.get("หน่วยนับ", "")
    if unit_txt and _sk(unit_txt) not in {_sk(u) for u in P.MONEY_UNITS}:
        _indicator_row(r, st, st.node if st.sub else "", pending_ind, texts, got)   # แถวตัวชี้วัดในตารางเงิน
        return
    s = _sk(_strip_dash(label))
    lvl = level_of(label)
    if st.section == P.SEC_OFFBUDGET:
        key = _off_key(st, label)
        st.last = None
    elif (any(s.startswith(_sk(c)) for c in P.GRAND_TOTAL_CUES) or not label) and not st.group:
        key = "total" if not st.sub else f"{st.node}|total"
        st.last = None
    elif st.table in (P.SEC_SUMMARY, P.SUB_ACTIVITY) or (lvl and st.table == P.SEC_YEARS):
        if st.sub == P.SUB_ACTIVITY:
            lvl, parent = P.LEVEL_ACTIVITY, st.node
        else:
            lvl = lvl or (P.LEVEL_PLAN if re.match(r"^\d+\.\s", label) else "")
            if not lvl:
                # แถวที่ไม่บอกระดับ ให้เป็นลูกของโหนดก่อนหน้า (เช่น รายการค่าใช้จ่ายบุคลากรภาครัฐ)
                lvl = P.LEVEL_OUTPUT if st.plan else P.LEVEL_PLAN
            parent = st.plan if lvl != P.LEVEL_PLAN else ""
        rec = add_node(lvl, label, r, parent)
        rec["kind"] = "node"
        _touch(rec, r)
        key = rec["key"]
        if lvl == P.LEVEL_PLAN:
            st.plan = key
        st.last = rec
    elif lvl and st.table == P.SEC_MTEF and not st.sub:
        rec = add_node(lvl, label, r, st.plan if lvl != P.LEVEL_PLAN else "")
        rec["kind"] = "node"
        _touch(rec, r)
        key = rec["key"]
        if lvl == P.LEVEL_PLAN:
            st.plan = key
        st.last = rec
    else:
        # แถวแหล่งเงิน/รายการในตาราง (เงินงบประมาณ · เงินนอกงบประมาณ · - เงินรายได้ · - งบดำเนินงาน)
        base = st.node if st.sub else (f"grp:{st.group}" if st.group else "row")
        key = f"{base}|{label_key(_strip_dash(label))}"
        bf.row_labels[key] = clean(label)
        st.last = {"kind": "row", "key": key, "label": label, "ev": _ev(r)}
        _touch(st.last, r)
    if unit_txt:
        unit, uo, uev = unit_txt, "text_column", _ev(r)
    elif st.unit and st.unit_origin == "table_decl":
        unit, uo, uev = st.unit, "table_decl", st.unit_ev
    else:
        unit, uo, uev = (st.unit or TABLE_UNIT_DEFAULT.get(st.table, "")), "profile_default", None
    for col, c in got.items():
        _amt(bf, st.table, key, col, c, r, unit=unit, unit_origin=uo, unit_ev=uev,
             column_origin=_col_origin(st, col, near), column_ev=st.header_ev)
    for c in nums:
        if c.name not in got:
            # แถวมีอยู่ (มีตัวเลขในคอลัมน์อื่น) แต่ช่องนี้ไม่มีอะไรพิมพ์ — ต่างจาก "ไม่พบระเบียน"
            bf.blanks.append(Amount(st.table, key, c.name, "", unit, "", _ev(r), uo, "header", [], "blank",
                                    uev, st.header_ev or _ev(r)))


def _detail_row(r: Row, st: _State, bf: BookFacts, pending_ind, pending_txt, add_node):
    label = r.label
    s = _sk(_strip_dash(strip_number(label)))
    lvl = level_of(label)
    # หัวข้อโหนด (แผนงาน/ผลผลิต/โครงการ/กิจกรรม) — ไม่มีตัวเลขท้ายบรรทัด หรือมียอดรวมของโหนด
    if lvl and (not r.cells or P.HEADING_NO.match(label) or ":" in label or lvl == P.LEVEL_COSTLINE):
        parent = "" if lvl == P.LEVEL_PLAN else (st.plan if lvl in (P.LEVEL_OUTPUT, P.LEVEL_PROJECT)
                                                  else st.node)
        rec = add_node(lvl, label, r, parent)
        rec["kind"] = "node"
        if lvl == P.LEVEL_PLAN:
            st.plan = rec["key"]
            st.node = ""
        else:
            st.node = rec["key"]
        st.category, st.cols, st.pending, st.table_kind, st.in_commit = "", [], None, "", False
        st.commit, st.sub = None, ""
        st.last_item, st.anchor_node = None, rec      # วงเงินผูกพันที่ตามมาเป็นของโหนดนี้
        _touch(rec, r)
        st.last = rec
        if r.cells and r.cells[-1].value is not None:
            _detail_amt(bf, rec["key"], P.COL_TOTAL, r.cells[-1], r)
        return

    if s.startswith(_sk(P.OBJECTIVE_CUE)):
        txt = re.sub(r"^\s*วัตถุประสงค์\s*[:：]?\s*", "", r.text)
        rec = {"kind": "text", "section": "objective", "scope": st.node, "no": "",
               "text": txt, "order": st.next_order(), "ev": _ev(r)}
        pending_txt.append(rec)
        _touch(rec, r)
        st.last = rec
        st.cols, st.table_kind = [], ""
        return

    if st.table_kind == "indicator" and st.cols and not category_of(label):
        if r.cells:
            _indicator_row(r, st, st.node, pending_ind)
        elif st.last is not None and st.last.get("kind") == "ind" and _continues(r, st.last):
            st.last["name"] = join_wrapped(st.last["name"], label_without_text_columns(r, st.cols))
            _touch(st.last, r)
        else:
            st.cols, st.table_kind = [], ""
        return

    # เงินนอกงบประมาณ/เงินงบประมาณ — ของรายการผูกพัน (ถ้าอยู่ในช่วงวงเงิน) หรือของโหนด/หมวด
    fund = (P.FUND_OFFBUDGET if s.startswith(_sk(P.FUND_OFFBUDGET)) else
            P.FUND_BUDGET if s.startswith(_sk(P.FUND_BUDGET)) else "")
    if fund and r.cells and r.cells[-1].value is not None:
        v = str(r.cells[-1].value)
        if st.commit is not None and st.commit.total and st.last_item is not None \
                and st.commit.node == st.node and st.in_commit:
            st.commit.parts[fund] = v
            _commit_line(st.commit, r, f"fund:{fund}")
            return
        col = f"{fund} · {st.category}" if st.category else fund
        _detail_amt(bf, st.node, col, r.cells[-1], r)
        return

    cat = category_of(label)
    if cat and not P.ITEM_NO.match(label):
        st.category, st.in_commit, st.cols, st.table_kind, st.commit = cat, False, [], "", None
        if r.cells and r.cells[-1].value is not None:
            _detail_amt(bf, st.node, cat, r.cells[-1], r)
        st.last = None
        return

    if _sk(P.COMMIT_SECTION_CUE) in s:
        st.in_commit = True
        return

    # บรรทัดวงเงินของรายการผูกพัน
    my = P.COMMIT_YEAR_CUE.search(squash(r.label))
    mf = P.COMMIT_FUTURE_CUE.search(squash(r.label)) if "ผูกพัน" in squash(r.text) else None
    if s.startswith(_sk(P.COMMIT_TOTAL_CUE)) or my or mf:
        cm = _current_commitment(bf, st)
        if cm is None or not r.cells or r.cells[-1].value is None:
            if r.cells:
                bf.coverage.unparsed.append(_ev(r))
            return
        v = str(r.cells[-1].value)
        if s.startswith(_sk(P.COMMIT_TOTAL_CUE)):
            cm.total, lk = v, "total"
        elif my:
            cm.years[my.group(1)], lk = v, f"year:{my.group(1)}"
        else:
            y = mf.group(1) or mf.group(2) or "?"
            cm.future[y], lk = v, f"future:{y}"
        _commit_line(cm, r, lk)
        st.in_commit, st.commit = True, cm
        return

    not_prop = any(_sk(c) in s for c in P.NOT_PROPOSED_CUES)
    leaf = P.ITEM_NO.match(label)
    m_item = leaf or (P.HEADING_NO.match(label) if (st.category or r.cells) else None)
    if m_item and st.node:
        if not leaf:
            st.in_commit = False          # หมวดย่อยใหม่ — จบช่วงรายการผูกพันของหมวดย่อยก่อน
        st.commit = None
        amount = str(r.cells[-1].value) if r.cells and r.cells[-1].value is not None else None
        name = _strip_not_proposed(label)
        key = f"{st.category}|{label_key(name)}"
        dup = sum(1 for x in bf.items if x.node == st.node and x.key.split("#")[0] == key)
        if dup:
            key = f"{key}#{dup + 1}"          # ข้อความซ้ำในหมวดเดียวกัน — แยกตามลำดับที่พบ
        it = Item(key=key, node=st.node, category=st.category,
                  label=strip_number(name), amount=amount, not_proposed=not_prop,
                  order=st.next_order(), ev=_ev(r), sub=not leaf, no=lead_no(label))
        if amount is not None:
            _item_unit(it, r)
        bf.items.append(it)
        st.last_item, st.last_item_y1 = it, r.y1
        st.last = {"kind": "item", "ev": it.ev, "y1": r.y1}
        if st.in_commit and leaf:
            bf.commitments.append(Commitment(key=it.key, node=st.node, label=it.label, ev=it.ev))
        return

    if not_prop and st.last_item is not None:
        st.last_item.not_proposed = True
        return

    # หัวข้อโหนดชื่อยาวหลายบรรทัด และยอดรวมอยู่บรรทัดสุดท้าย
    if st.last is not None and st.last.get("kind") == "node" and r.cells \
            and _continues(r, st.last, allow_cells=True) and r.cells[-1].value is not None:
        st.last["label"] = join_wrapped(st.last["label"], r.label)
        _detail_amt(bf, st.last["key"], P.COL_TOTAL, r.cells[-1], r)
        st.last = None
        return

    # รายการที่ชื่อยาวหลายบรรทัด และจำนวนเงินอยู่บรรทัดสุดท้าย
    if st.last is not None and st.last.get("kind") == "item" and st.last_item is not None \
            and _continues(r, st.last, allow_cells=True):
        it = st.last_item
        it.label = join_wrapped(it.label, _strip_not_proposed(label) if r.cells else r.text)
        if r.cells and it.amount is None and r.cells[-1].value is not None:
            it.amount = str(r.cells[-1].value)
            _item_unit(it, r)
            st.last = None
        else:
            _touch(st.last, r)
        return

    if r.cells:
        bf.coverage.unparsed.append(_ev(r))
        return
    # บรรทัดข้อความต่อ (ชื่อโหนดยาว / วัตถุประสงค์ยาว)
    if st.last is not None and st.last.get("kind") in ("text", "node") and _continues(r, st.last):
        key = "text" if st.last.get("kind") == "text" else "label"
        st.last[key] = join_wrapped(st.last[key], r.text)
        _touch(st.last, r)


def _item_unit(it: Item, r: Row) -> None:
    """ที่มาหน่วยของยอดรายการ (บรรทัดที่ให้ยอด) — ไม่มีคำหน่วยในบรรทัด = สมมติบาท + ธงต้องยืนยัน"""
    _unit, it.unit_origin = _row_unit(r)
    it.flags = ["unit_not_in_document"] if it.unit_origin not in UNIT_ORIGINS_IN_DOCUMENT else []


def _commit_line(cm: Commitment, r: Row, key: str) -> None:
    """บันทึกบรรทัดวงเงินของรายการผูกพัน + ค่าที่บรรทัดนี้ให้ + ที่มาหน่วย (ใช้ชี้องค์ประกอบของผลรวม)"""
    cm.lines.append(_ev(r))
    cm.line_keys.append(key)
    cm.line_units.append(_row_unit(r)[1])


_NP = re.compile(r"\s*[-–]?\s*(?:" + "|".join(re.escape(c) for c in P.NOT_PROPOSED_CUES)
                 + r")\S*\s*$")


def _strip_not_proposed(label: str) -> str:
    return _NP.sub("", clean(label)).strip()


def _current_commitment(bf: BookFacts, st: _State) -> Commitment | None:
    """รายการผูกพันที่บรรทัดวงเงินนี้สังกัด — ถ้ายังไม่มีระเบียน ให้สร้างจากรายการล่าสุด"""
    it = st.last_item
    if it is None:
        node = getattr(st, "anchor_node", None)
        if node is None:
            return None
        key = "node:" + node["key"]
        if bf.commitments and bf.commitments[-1].key == key:
            return bf.commitments[-1]
        cm = Commitment(key=key, node=node["key"], label=strip_number(node["label"]), ev=node["ev"])
        bf.commitments.append(cm)
        return cm
    if bf.commitments and bf.commitments[-1].key == it.key and bf.commitments[-1].node == it.node:
        return bf.commitments[-1]
    cm = Commitment(key=it.key, node=it.node, label=it.label, ev=it.ev)
    bf.commitments.append(cm)
    return cm


@dataclass
class YearEvidence:
    """ปีงบของเล่มพร้อมที่มา — ``status``: ok · uncertain · conflict · not_found

    ``evidence`` = หลักฐานต่อ candidate: ``{kind, year, end, page, line, cue, direct}`` —
    ``direct`` = ปีที่อ่านตรงจากข้อความ (ปีเดี่ยว "ประจำปีงบประมาณ" · ปลายช่วงเปรียบเทียบ) ·
    ``False`` = อนุมาน (ปีเริ่มช่วงประมาณการ − 1 · ปีที่กล่าวถึงในเนื้อหา) · ``bbox`` เติมภายหลังจากหน้าเอกสาร
    """
    year: int | None
    origin: str            # stated · comparison_range · forward_range · single_mention · ""
    status: str
    candidates: tuple = ()
    evidence: tuple = ()


#: คำนำหน้าที่บอกว่าเป็นปีของเล่ม — "งบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. 2570"
_YEAR_STATED_CUE = "ประจำ"
#: คำก่อนหน้าช่วงปีที่บอกว่าเป็นช่วงประมาณการล่วงหน้า (ปีหลังปีของเล่ม)
_YEAR_FORWARD_CUES = ("ล่วงหน้า", "ประมาณการ")


def _cue_key(s: str) -> str:
    """รูปเทียบคำบอกปี (pdfbook-0.5.1) — ฟอนต์บนปกบางเล่มถอด "ประจำ" เป็น "ประจ่ำ" (ไม้เอกเกิน) หรือ "ประจำา"
    (สระอาเกิน) ทั้งที่ภาพพิมพ์ถูก · ตัดสระบน/ล่าง/วรรณยุกต์ (:func:`skeleton`) แล้วยุบ "าา" (ไม่มีในคำไทย) ·
    หลักฐานยังเก็บข้อความดิบตามที่อ่านได้"""
    return skeleton(s).replace("าา", "า")


#: จำนวนหน้าแรกของหน่วยงานที่ใช้หาปี (pdfbook-0.5.2) — หน้า 2 มีหัวข้อ "4. เปรียบเทียบงบประมาณรายจ่ายประจำปีงบประมาณ
#: พ.ศ. Y-2 - Y" ซึ่งปลายช่วงคือปีของเล่ม (เล่ม 2569 มีงบปี 2568 · เล่ม 2570 มีงบปี 2569) — ปกบางเล่มไม่มีปีในชั้นข้อความ
YEAR_AGENCY_PAGES = 3


def year_pages(n_pages: int, scope_first: int, scope_last: int = 0) -> list[int]:
    """หน้าที่ใช้หาปี — หน้าต้นไฟล์ 3 หน้า + หน้าแรกของหน่วยงาน :data:`YEAR_AGENCY_PAGES` หน้า **ไม่เกินหน้าสุดท้ายของ
    หน่วยงาน** (ไม่อ่านหน้าของหน่วยงานอื่น) · ``scope_last`` ว่าง = หน้าเริ่มหน้าเดียว"""
    pages = list(range(1, min(3, n_pages) + 1))
    if scope_first:
        last = min(scope_first + YEAR_AGENCY_PAGES - 1, scope_last or scope_first, n_pages)
        pages += [p for p in range(scope_first, last + 1) if p not in pages]
    return pages


def _year_lines(texts: list[str], scope_first: int, scope_last: int = 0):
    """(หน้า, [บรรทัด]) ของหน้าที่ใช้หาปี (:func:`year_pages`) · คงขอบเขตบรรทัด/หน้า"""
    pages = year_pages(len(texts), scope_first, scope_last)
    for pg in pages:
        lines = [clean(x) for x in re.split(r"[\r\n]+", texts[pg - 1] or "")]
        yield pg, [x for x in lines if x]


def detect_year(texts: list[str], scope_first: int, scope_last: int = 0) -> YearEvidence:
    """ปีงบของเล่มจากหน้าต้นไฟล์ + หน้าเริ่มของหน่วยงาน แยกหลักฐานตามบริบท (ไม่เลือกค่าสูงสุด)

    1. **stated** — "ประจำปีงบประมาณ พ.ศ. Y" (ปีเดี่ยว) · ทุกค่าต้องตรงกัน และตรงกับปลายช่วงเปรียบเทียบ
    2. **comparison_range** — ปลายช่วง "ปีงบประมาณ พ.ศ. A - B" ที่ไม่ใช่ช่วงประมาณการ
    3. **forward_range** — มีแต่ช่วงประมาณการล่วงหน้า → ปีเริ่มช่วง − 1 สถานะ ``uncertain``
    4. **single_mention** — ปีเดี่ยวที่ไม่มีคำว่า "ประจำ" (เช่น "ผลการดำเนินงานของปีงบประมาณ 2569")
       อนุมานได้เฉพาะเมื่อตรงกันทุกค่า สถานะ ``uncertain``

    ขอบเขตคำบอก (REVIEW 6342471856): อ่านคำบอกเฉพาะ **ในบรรทัดเดียวกัน ระหว่างปีก่อนหน้ากับปีนี้** —
    ถ้าปีอยู่ต้นบรรทัด ใช้ส่วนท้ายของบรรทัดก่อนหน้า **ในหน้าเดียวกัน** (หัวข้อที่ห่อบรรทัด) · ไม่ข้ามหน้า ·
    คำบอกที่อยู่หลังปีไม่นับ · เลขไทยและขีดยาว (– —) อ่านได้

    หลักฐานขัดกัน = ``conflict`` ปี ``None`` (ไม่เลือกให้เอง) · ไม่พบ = ``not_found``
    """
    stated, comparison, forward, mention = [], [], [], []
    evs: list[dict] = []
    for pg, lines in _year_lines(texts, scope_first, scope_last):
        for li, line in enumerate(lines):
            prev_end = 0
            for m in P.FISCAL_YEAR.finditer(line):
                cue = line[prev_end:m.start()]
                if not cue.strip() and li > 0:
                    prev = lines[li - 1]
                    last = list(P.FISCAL_YEAR.finditer(prev))
                    cue = prev[last[-1].end():] if last else prev
                prev_end = m.end()
                start, end = int(m.group(1)), int(m.group(2) or m.group(1))
                ev = {"page": pg, "line": line[:200], "cue": cue.strip()[-60:], "year": start, "end": end}
                if not m.group(2):
                    if _cue_key(cue).endswith(_cue_key(_YEAR_STATED_CUE)):
                        stated.append(start)
                        evs.append({**ev, "kind": "stated", "direct": True})
                    else:
                        mention.append(start)
                        evs.append({**ev, "kind": "mention", "direct": False})
                elif any(_cue_key(c) in _cue_key(cue) for c in _YEAR_FORWARD_CUES):
                    forward.append((start, end))
                    evs.append({**ev, "kind": "forward", "direct": False})
                else:
                    comparison.append((start, end))
                    evs.append({**ev, "kind": "comparison", "direct": True})
    # ช่วงที่ไม่มีคำบอก แต่เริ่มต่อจากปีเล่ม/ปลายช่วงอื่นพอดี = ช่วงประมาณการ
    anchors = set(stated) | {e for _, e in comparison}
    moved = [r for r in comparison if r[0] - 1 in anchors]
    forward += moved
    comparison = [r for r in comparison if r not in moved]
    for e in evs:
        if e["kind"] == "comparison" and (e["year"], e["end"]) in moved:
            e["kind"], e["direct"] = "forward", False
            e["cue"] = (e["cue"] + " · ").lstrip(" · ") + "(ต่อจากปีเล่ม = ช่วงประมาณการ)"

    cands = tuple([f"{y} (stated)" for y in stated] + [f"{s}-{e} (comparison)" for s, e in comparison]
                  + [f"{s}-{e} (forward)" for s, e in forward] + [f"{y} (mention)" for y in mention])
    evs_t = tuple(evs)
    ends = {e for _, e in comparison}
    if stated:
        if len(set(stated)) == 1 and (not ends or ends == set(stated)):
            return YearEvidence(stated[0], "stated", "ok", cands, evs_t)
        return YearEvidence(None, "", "conflict", cands, evs_t)
    if ends:
        if len(ends) == 1:
            return YearEvidence(ends.pop(), "comparison_range", "ok", cands, evs_t)
        return YearEvidence(None, "", "conflict", cands, evs_t)
    if forward:
        starts = {s for s, _ in forward}
        if len(starts) == 1:
            return YearEvidence(starts.pop() - 1, "forward_range", "uncertain", cands, evs_t)
        return YearEvidence(None, "", "conflict", cands, evs_t)
    if mention:
        if len(set(mention)) == 1:
            return YearEvidence(mention[0], "single_mention", "uncertain", cands, evs_t)
        return YearEvidence(None, "", "conflict", cands, evs_t)
    return YearEvidence(None, "", "not_found", cands, evs_t)


@dataclass
class StageEvidence:
    """ขั้นเอกสาร (ร่าง พ.ร.บ. / พ.ร.บ.) พร้อมที่มา — ``status``: ok · conflict · not_found

    อ่านจาก **ข้อความที่มองเห็น** ของหน้าต้นไฟล์ + หน้าเริ่มของหน่วยงาน และนับเฉพาะบรรทัดชื่อเอกสาร
    (คำบอกขั้นอยู่บรรทัดเดียวกับ "งบประมาณรายจ่าย") — "จัดตั้งตามพระราชบัญญัติ…" ในเนื้อหาไม่นับ ·
    พบทั้งสองขั้น = ขัดกัน ระบบไม่เลือกให้ · เล่มร่างจริงหน้าปกไม่พิมพ์คำว่า "ร่าง" ⇒ ไม่พบ ≠ เป็นร่าง
    (REVIEW 6360210542: ขั้นเอกสารห้ามใช้เป็นหลักฐานชัดเจนโดยไม่มีคำเตือน)"""
    stage: str             # draft · act · ""
    status: str
    evidence: tuple = ()   # ({kind, page, line, cue}, …)


def detect_stage(texts: list[str], scope_first: int) -> StageEvidence:
    title = skeleton("งบประมาณรายจ่าย")
    ev = []
    for pg, lines in _year_lines(texts, scope_first):
        for line in lines:
            s = skeleton(line)
            if title not in s:
                continue
            # "ร่างพระราชบัญญัติงบประมาณรายจ่าย" มีคำบอกฉบับ พ.ร.บ. อยู่ข้างใน — บรรทัดที่มีคำบอกร่าง = ร่าง
            cue = next((c for c in P.STAGE_DRAFT_CUES if skeleton(c) in s), "")
            kind = "draft" if cue else ""
            if not cue:
                cue = next((c for c in P.STAGE_ACT_CUES if skeleton(c) in s), "")
                kind = "act" if cue else ""
            if kind:
                ev.append({"kind": kind, "page": pg, "line": line[:160], "cue": cue})
    kinds = {e["kind"] for e in ev}
    if len(kinds) == 1:
        return StageEvidence(kinds.pop(), "ok", tuple(ev))
    return StageEvidence("", "conflict" if kinds else "not_found", tuple(ev))


def detect_meta(texts: list[str], scope_first: int) -> tuple[int | None, str]:
    """ปีงบประมาณ (:func:`detect_year`) และขั้นเอกสาร — ไม่พบ = ``None``/``""``

    🔴 ตัวเก่าที่อ่านข้อความดิบ (รวมข้อความที่ซ่อนนอกขอบหน้า) — ชั้นบริการใช้ :func:`detect_year` +
    :func:`detect_stage` กับข้อความที่มองเห็นแทน · คงไว้เพื่อเครื่องมือเดิมเท่านั้น"""
    probe = " ".join(texts[:3] + [texts[scope_first - 1] if scope_first else ""])
    sq = skeleton(probe)
    fy = detect_year(texts, scope_first).year
    stage = ""
    if any(skeleton(c) in sq for c in P.STAGE_DRAFT_CUES):
        stage = "draft"
    elif any(skeleton(c) in sq for c in P.STAGE_ACT_CUES):
        stage = "act"
    return fy, stage
