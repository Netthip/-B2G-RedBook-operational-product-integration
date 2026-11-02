# -*- coding: utf-8 -*-
"""สกัด *ข้อสังเกตตัวชี้วัด* ระดับหน้า — **โดยไม่ตัดสินความเท่าเทียม** (Gate 1 ข้อ 2)

หนึ่งข้อสังเกต = ข้อความหนึ่งช่วงในหน้าหนึ่งของเอกสารหนึ่ง พร้อม

* ``observed_text`` ตรงตามที่ปรากฏ · ``normalized_text`` รูปมาตรฐาน (คนละคอลัมน์)
* หน้า · กรอบ (bbox หน่วย point) · ``location_confidence``
* ฟิลด์ที่ *อ่านได้จากข้อความ* เมื่อมี: หน่วย · ค่าเป้าหมาย · วิธีคำนวณ · รอบรายงาน
* แฮชของเอกสารต้นทาง · รุ่นของตัวสกัด

**กติกาความระมัดระวัง**

* ตัวสกัดใช้ *คำบ่งชี้* (cue) แบบอนุรักษ์นิยม — พลาดได้ (จะถูกรายงานเป็นช่องว่าง
  ให้คนดู) แต่ต้องไม่แต่งข้อความขึ้นเอง
* หน้าที่ไม่มีชั้นข้อความ ⇒ ไม่มีข้อสังเกตจากเครื่อง และหน้านั้นถูกบันทึกเป็น
  ``TEXT_LAYER_ABSENT`` ในบัญชีหน้า (ดู :func:`page_inventory`) — **ไม่เงียบ**
* ``location_confidence``: ``EXACT_BBOX`` = กรอบจากบรรทัดเดียว ·
  ``LINE_APPROX`` = รวมจากหลายบรรทัด · ``PAGE_ONLY`` = รู้แค่หน้า (กรอกโดยคน)
* **P1-2 · ธงเชิงเรขาคณิต** (Bo `5598957701`) — บรรทัดที่ **ชนหรือล้นขอบหน้า** ถูกติดธง
  ``TEXT_CLIPPED_AT_PAGE_EDGE`` เพราะ parser ต่างชนิดอ่านได้ไม่เท่ากัน (บางตัวตัดคำที่อยู่
  นอกหน้า บางตัวไม่ตัด) 🔴 กติกา **fail-visible**: ห้ามตัดข้อความเงียบแล้วเสนอ mapping เป็น
  ผลปกติ — ข้อสังเกตที่ติดธงนี้ทำให้คู่ของมันต้องให้คนตัดสิน (ดู :mod:`redbook.indicators.mapping`)
* **H2 · สมอของข้อสังเกตที่คนกรอก** — ``anchor`` ต้องแยกแต่ละ occurrence ในหน้าเดียวกัน
  (``manual:{occurrence}``) ⇒ ข้อความเดียวกันที่ปรากฏซ้ำในหน้าเดียวไม่ชน id กัน

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from ..evidence.pdftext import PageText
from . import normalize as nz

OBSERVE_VERSION = "indicator-observe-0.2.0"

LOC_EXACT = "EXACT_BBOX"
LOC_LINE_APPROX = "LINE_APPROX"
LOC_PAGE_ONLY = "PAGE_ONLY"

LOCATION_LABELS = {
    LOC_EXACT: "กรอบตรงตำแหน่ง",
    LOC_LINE_APPROX: "กรอบโดยประมาณ (รวมหลายบรรทัด)",
    LOC_PAGE_ONLY: "รู้เฉพาะหน้า — ต้องให้คนชี้ตำแหน่ง",
}

# ── P1-2 · ธงเชิงเรขาคณิต ────────────────────────────────────────────────────
#: บรรทัดชน/ล้นขอบหน้า ⇒ parser ต่างชนิดอ่านได้ไม่เท่ากัน · ห้ามยืนยันอัตโนมัติ
FLAG_TEXT_CLIPPED = "TEXT_CLIPPED_AT_PAGE_EDGE"
#: ข้อสังเกตที่คนกรอก — ระบุไว้เพื่อให้แยกจากที่เครื่องสกัดได้ในรายงาน
FLAG_MANUAL_ENTRY = "MANUAL_ENTRY"

GEOMETRY_FLAG_LABELS = {
    FLAG_TEXT_CLIPPED: "ข้อความชน/ล้นขอบหน้า — ตัวอ่าน PDF ต่างชนิดอ่านได้ไม่เท่ากัน ต้องให้คนตรวจ",
    FLAG_MANUAL_ENTRY: "ผู้ตรวจกรอกด้วยมือ",
}

#: ระยะจากขอบหน้า (point) ที่ถือว่า "ชนขอบ" — เผื่อไว้เพราะ parser ปัดพิกัดต่างกัน
PAGE_EDGE_TOLERANCE_PT = 1.0


def clipped_at_page_edge(x1: float, page_width: float,
                         tolerance: float = PAGE_EDGE_TOLERANCE_PT) -> bool:
    """บรรทัดนี้ชนหรือล้นขอบขวาของหน้าหรือไม่ — ``page_width <= 0`` = ไม่ทราบ ⇒ ไม่ติดธง"""
    if not page_width or page_width <= 0:
        return False
    return float(x1) >= float(page_width) - float(tolerance)

#: คำบ่งชี้ว่าบรรทัดนี้ *น่าจะ* เป็นตัวชี้วัด — อนุรักษ์นิยม
CUES = ("ตัวชี้วัด", "เชิงปริมาณ", "เชิงคุณภาพ", "ค่าเป้าหมาย", "หน่วยนับ")
#: บรรทัดที่เป็นแค่หัวข้อ (ไม่มีเนื้อความตัวชี้วัด) — จะดึงบรรทัดถัดไปมาต่อ
_HEADER_ONLY = re.compile(
    r"^(ตัวชี้วัด(เชิงปริมาณ|เชิงคุณภาพ)?\s*(ที่\s*\d+)?|เชิงปริมาณ|เชิงคุณภาพ)\s*[:：]?\s*$")
_ORDINAL = re.compile(r"ตัวชี้วัด\s*(?:ที่)?\s*(\d+)")
_TARGET = re.compile(
    r"(?:ค่าเป้าหมาย|เป้าหมาย|ไม่น้อยกว่า|ไม่เกิน|ร้อยละ)\s*[:：]?\s*"
    r"(?:ร้อยละ\s*)?(\d+(?:[.,]\d+)*)\s*([^\s\d()/:,;]{0,12})?")
_PERIOD = re.compile(r"(ปีงบประมาณ\s*(?:พ\.?ศ\.?)?\s*\d{4}|ไตรมาส\s*\d|รายปี|รายเดือน|รายไตรมาส)")
_BASELINE = re.compile(r"(?:ค่าฐาน|ฐาน|ผลปีที่ผ่านมา)\s*[:：]?\s*(\d+(?:[.,]\d+)*)")


@dataclass(frozen=True)
class Observation:
    observation_id: str
    document_id: str
    page: int
    line_index: int
    observed_text: str
    normalized_text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float
    page_height: float
    location_confidence: str
    unit: str
    target_text: str
    target_value: str
    baseline_text: str
    method_text: str
    period_text: str
    ordinal: str
    cues: tuple[str, ...]
    source_sha256: str
    #: สมอในหน้าที่คงที่ข้าม run — ``line:{n}`` (เครื่องสกัด) หรือ ``manual:{occurrence}`` (คนกรอก)
    anchor: str = ""
    #: ธงเชิงเรขาคณิต/ที่มา (P1-2 · H2) — ว่างคือไม่มีข้อสังเกตพิเศษ
    geometry_flags: tuple[str, ...] = ()
    extractor_version: str = OBSERVE_VERSION
    #: ค่าเสริมที่ไม่ได้มาจากเอกสาร — ใช้เฉพาะตอนแสดง
    extra: dict = field(default_factory=dict, compare=False)

    @property
    def bbox(self) -> tuple[float, float, float, float] | None:
        if self.location_confidence == LOC_PAGE_ONLY:
            return None
        return (self.x0, self.y0, self.x1, self.y1)

    @property
    def location_label(self) -> str:
        return LOCATION_LABELS.get(self.location_confidence, self.location_confidence)

    @property
    def flag_labels(self) -> tuple[str, ...]:
        return tuple(GEOMETRY_FLAG_LABELS.get(f, f) for f in self.geometry_flags)

    @property
    def text_clipped(self) -> bool:
        """ข้อความชน/ล้นขอบหน้า ⇒ ห้ามยืนยันคู่ของมันอัตโนมัติ (P1-2)"""
        return FLAG_TEXT_CLIPPED in self.geometry_flags

    @property
    def is_manual(self) -> bool:
        return FLAG_MANUAL_ENTRY in self.geometry_flags

    @property
    def identity_key(self) -> str:
        """กุญแจตัวตนที่คงที่ข้าม run (B1) — ต้องมี ``anchor`` และแฮชเอกสารเต็ม"""
        from .identity import observation_key

        return observation_key(document_sha256=self.source_sha256, page=self.page,
                               anchor=self.anchor or f"line:{self.line_index}",
                               observed_text=self.observed_text)


def _obs_id(document_id: str, page: int, anchor: str, text: str) -> str:
    """id ของข้อสังเกต — ผูกกับ **anchor** ไม่ใช่หมายเลขบรรทัดดิบ

    🔴 H2 — ข้อสังเกตที่คนกรอกเคยใช้ ``line_index=-1`` คงที่ ทำให้ข้อความเดียวกันที่ปรากฏ
    ซ้ำในหน้าเดียว **ชน id กัน** · ตอนนี้ anchor แยกทุก occurrence
    """
    h = hashlib.sha256(f"{document_id}|{page}|{anchor}|{text}".encode("utf-8"))
    return "obs_" + h.hexdigest()[:16]


def _parse_fields(text: str) -> dict:
    norm = nz.normalize(text)
    units = nz.unit_tokens(text)
    m_t = _TARGET.search(norm)
    m_p = _PERIOD.search(norm)
    m_b = _BASELINE.search(norm)
    m_o = _ORDINAL.search(norm)
    return {
        "unit": units[0] if len(units) == 1 else ("|".join(units) if units else ""),
        "target_text": m_t.group(0) if m_t else "",
        "target_value": m_t.group(1).replace(",", "") if m_t else "",
        "baseline_text": m_b.group(0) if m_b else "",
        "method_text": nz.method_span(text),
        "period_text": m_p.group(1) if m_p else "",
        "ordinal": m_o.group(1) if m_o else "",
    }


def _cues_in(norm: str) -> tuple[str, ...]:
    return tuple(c for c in CUES if c in norm)


def observe_page(document_id: str, source_sha256: str, page: PageText) -> list[Observation]:
    """ข้อสังเกตจากหนึ่งหน้า — หน้าไม่มีชั้นข้อความคืน ``[]`` (ผู้เรียกต้องบันทึกเอง)"""
    if not page.has_text_layer:
        return []
    out: list[Observation] = []
    lines = list(page.lines)
    i = 0
    while i < len(lines):
        ln = lines[i]
        norm = nz.normalize(ln.text)
        cues = _cues_in(norm)
        if not cues:
            i += 1
            continue
        text = ln.text
        x0, y0, x1, y1 = ln.bbox
        conf = LOC_EXACT
        consumed = 1
        # หัวข้อเปล่า เช่น "ตัวชี้วัดที่ 3 :" ⇒ ต่อบรรทัดถัดไปหนึ่งบรรทัด
        if _HEADER_ONLY.match(norm) and i + 1 < len(lines):
            nxt = lines[i + 1]
            text = ln.text + " " + nxt.text
            x0, y0 = min(x0, nxt.x0), min(y0, nxt.y0)
            x1, y1 = max(x1, nxt.x1), max(y1, nxt.y1)
            conf = LOC_LINE_APPROX
            consumed = 2
        fields = _parse_fields(text)
        anchor = f"line:{ln.index}"
        flags: list[str] = []
        if clipped_at_page_edge(x1, page.width):
            flags.append(FLAG_TEXT_CLIPPED)
        out.append(Observation(
            observation_id=_obs_id(document_id, page.page, anchor, text),
            document_id=document_id, page=page.page, line_index=ln.index,
            observed_text=text, normalized_text=nz.normalize(text),
            x0=x0, y0=y0, x1=x1, y1=y1,
            page_width=page.width, page_height=page.height,
            location_confidence=conf, cues=cues, source_sha256=source_sha256,
            anchor=anchor, geometry_flags=tuple(flags), **fields))
        i += consumed
    return out


def observe_document(document_id: str, source_sha256: str,
                     pages: list[PageText]) -> list[Observation]:
    out: list[Observation] = []
    for p in pages:
        out.extend(observe_page(document_id, source_sha256, p))
    return out


@dataclass(frozen=True)
class PageInventoryRow:
    page: int
    text_layer: bool
    char_count: int
    observations: int
    #: จำนวนข้อสังเกตในหน้านี้ที่ข้อความชน/ล้นขอบหน้า (P1-2)
    clipped_observations: int = 0

    @property
    def status(self) -> str:
        return "TEXT_LAYER_PRESENT" if self.text_layer else "TEXT_LAYER_ABSENT"


def page_inventory(pages: list[PageText], observations: list[Observation]) -> list[PageInventoryRow]:
    """บัญชีรายหน้า — หน้าที่ไม่มีชั้นข้อความต้องมองเห็น ไม่ใช่หายไปจากรายงาน"""
    count: dict[int, int] = {}
    clipped: dict[int, int] = {}
    for o in observations:
        count[o.page] = count.get(o.page, 0) + 1
        if o.text_clipped:
            clipped[o.page] = clipped.get(o.page, 0) + 1
    return [PageInventoryRow(page=p.page, text_layer=p.has_text_layer,
                             char_count=p.char_count, observations=count.get(p.page, 0),
                             clipped_observations=clipped.get(p.page, 0))
            for p in pages]


def manual_anchor(occurrence: int, *, hint: str = "") -> str:
    """สมอของข้อสังเกตที่คนกรอก — **ต้องแยกแต่ละ occurrence ในหน้าเดียวกัน** (H2)

    ``occurrence`` เริ่มที่ 1 และหมายถึง "รายการที่เท่าไรของหน้านี้ตามที่ผู้ตรวจไล่อ่าน" ·
    ``hint`` เป็นข้อความสั้นที่ผู้ตรวจใช้เล็งตำแหน่ง (เช่น ``ใต้หัวข้อ 7.3``) และเข้าไปในสมอ
    ด้วย เพื่อให้สองคนที่กรอกคนละที่ในหน้าเดียวไม่ได้ id เดียวกันแม้นับ occurrence ตรงกัน
    """
    if int(occurrence) < 1:
        raise ValueError("occurrence ของข้อสังเกตที่คนกรอกต้องเริ่มที่ 1")
    suffix = f":{hint.strip()}" if hint.strip() else ""
    return f"manual:{int(occurrence)}{suffix}"


def manual_observation(document_id: str, source_sha256: str, *, page: int,
                       observed_text: str, occurrence: int = 1, hint: str = "",
                       page_width: float = 0.0, page_height: float = 0.0,
                       note: str = "", reviewer: str = "") -> Observation:
    """ข้อสังเกตที่ **คน** กรอก (เช่น หน้าที่ไม่มีชั้นข้อความ) — ตำแหน่ง = ``PAGE_ONLY``

    🔴 H2 (Bo `5595832792`) — เดิมใช้ ``line_index=-1`` คงที่ ⇒ ข้อความเดียวกันที่ปรากฏ
    ซ้ำในหน้าเดียวกันได้ ``observation_id`` ชนกัน · ตอนนี้ id ผูกกับ
    :func:`manual_anchor` ที่แยกทุก occurrence
    """
    fields = _parse_fields(observed_text)
    anchor = manual_anchor(occurrence, hint=hint)
    return Observation(
        observation_id=_obs_id(document_id, page, anchor, observed_text),
        document_id=document_id, page=page, line_index=-1,
        observed_text=observed_text, normalized_text=nz.normalize(observed_text),
        x0=0.0, y0=0.0, x1=0.0, y1=0.0, page_width=page_width,
        page_height=page_height, location_confidence=LOC_PAGE_ONLY,
        cues=("manual",), source_sha256=source_sha256, anchor=anchor,
        geometry_flags=(FLAG_MANUAL_ENTRY,), extractor_version="manual",
        extra={"note": note, "reviewer": reviewer}, **fields)


__all__ = [
    "OBSERVE_VERSION", "LOC_EXACT", "LOC_LINE_APPROX", "LOC_PAGE_ONLY",
    "LOCATION_LABELS", "CUES", "FLAG_TEXT_CLIPPED", "FLAG_MANUAL_ENTRY",
    "GEOMETRY_FLAG_LABELS", "PAGE_EDGE_TOLERANCE_PT", "clipped_at_page_edge",
    "Observation", "PageInventoryRow", "observe_page", "observe_document",
    "page_inventory", "manual_anchor", "manual_observation",
]
