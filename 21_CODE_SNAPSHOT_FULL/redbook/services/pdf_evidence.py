# -*- coding: utf-8 -*-
"""#24 — หา "รายการที่กำลังตรวจ" บนหน้า PDF ต้นฉบับ แล้ววาดกรอบเน้นลงบนภาพหน้า (PDF-first visual compare)

ขั้นตอน

1. อ่านชั้นข้อความของ PDF ด้วย **product backend** (``pdftext.get_backend()`` =
   pdfplumber + pypdfium2 · ผ่านด่าน holdout/sealed เดียวกับทุกเส้นทาง) — 🔴 ห้ามใช้ PyMuPDF
   (AGPL · research-only · มีเทสต์ AST บังคับ)
2. หาบรรทัดที่มี **ป้ายรายการ** (จับแบบตัดช่องว่าง และแบบตัดวรรณยุกต์/สระบนล่างเป็นทางสำรอง)
   ให้คะแนนเพิ่มเมื่อบรรทัดเดียวกันมี **ตัวเลขของรายการนั้น** และเมื่อหน้ามีชื่อแผนงาน/โครงการ
3. วาดกรอบ: บรรทัดที่พบ (ทอง) · ตัวเลขที่เปลี่ยน (แดง = A · เขียว = B) · ตัวเลขที่เท่าเดิม (เทา)
   พร้อมเลขกำกับ ①②… ที่ตรงกับคำอธิบายใต้ภาพ · แล้วตัดภาพเฉพาะบริเวณรอบบรรทัด

🔴 **ตำแหน่งบน PDF เป็นผลการค้นหาข้อความ ไม่ใช่การจับคู่ของเครื่องยนต์** — เครื่องยนต์เทียบจาก
สมุดงาน Excel · หน้าจอต้องบอกระดับที่พบเสมอ (พบข้อความ+ตัวเลข / พบเฉพาะข้อความ / ไม่พบ)
และหาไม่พบต้องบอกตรง ๆ ห้ามชี้บรรทัดที่ไม่แน่ใจราวกับว่าแน่ใจ
"""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field

from ..evidence import pdftext

PDF_EVIDENCE_VERSION = "pdf-evidence-0.1.0"

FOUND_FULL = "full"            # พบป้ายรายการ และตัวเลขบนบรรทัดเดียวกัน
FOUND_TEXT = "text_only"       # พบป้ายรายการ แต่ตัวเลขไม่ตรง/ไม่พบ
FOUND_AREA = "area"            # (ฝั่งที่ไม่มีรายการ) พบบริเวณที่ควรเทียบ เช่น หัวข้อแม่
FOUND_NONE = "none"            # ไม่พบ
FOUND_LABELS = {
    FOUND_FULL: "พบข้อความรายการและตัวเลขในบรรทัดเดียวกัน",
    FOUND_TEXT: "พบข้อความรายการ แต่ตัวเลขในบรรทัดไม่ตรงกับค่าที่ระบบใช้เทียบ — ควรตรวจทาน",
    # Bo 8 ต.ค.: บริเวณหัวข้ออีกฝั่ง = บริบทสำหรับค้นต่อ **ไม่ใช่หลักฐานว่ารายการหายแน่นอน**
    FOUND_AREA: "บริเวณหัวข้อที่เกี่ยวข้อง — บริบทสำหรับค้นต่อ ไม่ใช่หลักฐานว่ารายการหาย",
    FOUND_NONE: "ระบบหาตำแหน่งรายการนี้ใน PDF ไม่พบ",
}

ROLE_LINE = "line"
ROLE_CHANGED = "changed"
ROLE_SAME = "same"
ROLE_AREA = "area"

#: ระยะ (point) เหนือ/ใต้บรรทัดที่ตัดภาพให้เห็นบริบท
CROP_MARGIN_PT = 120.0
ZOOM = 1.6

_THAI_MARKS = re.compile(r"[ัิ-ฺ็-๎]")
_WS = re.compile(r"[\s​‌‍﻿]+")
_LEAD_NO = re.compile(r"^\s*[0-9]+(?:\.[0-9]+)*\.?\s*")


def _squash(s: str) -> str:
    return _WS.sub("", s or "")


def _skeleton(s: str) -> str:
    return _THAI_MARKS.sub("", _squash(s))


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float
    role: str
    n: int = 0              # เลขกำกับ (0 = ไม่มี)
    side: str = ""


@dataclass(frozen=True)
class Located:
    found: str
    page: int | None = None
    page_w: float = 0.0
    page_h: float = 0.0
    line_text: str = ""
    boxes: tuple[Box, ...] = ()
    crop: tuple[float, float, float, float] | None = None
    page_count: int = 0

    @property
    def label(self) -> str:
        return FOUND_LABELS[self.found]

    @property
    def ok(self) -> bool:
        return self.page is not None

    def crop_pct(self, b: Box) -> tuple[float, float, float, float]:
        """ตำแหน่งกล่องเป็น % ของภาพที่ตัดแล้ว — สำหรับจุดชี้ (hotspot) ฝั่งหน้าจอ"""
        cx0, cy0, cx1, cy1 = self.crop or (0, 0, self.page_w, self.page_h)
        w, h = (cx1 - cx0) or 1, (cy1 - cy0) or 1
        return (round((b.x0 - cx0) / w * 100, 2), round((b.y0 - cy0) / h * 100, 2),
                round((b.x1 - b.x0) / w * 100, 2), round((b.y1 - b.y0) / h * 100, 2))


@dataclass(frozen=True)
class Number:
    """ตัวเลขหนึ่งค่าที่ต้องหาในบรรทัด — หลายรูปแบบการพิมพ์ (บาท/ล้านบาท/ไม่มีจุลภาค)"""

    variants: tuple[str, ...]
    changed: bool
    n: int
    #: หัวคอลัมน์ (ปี เช่น ``2570`` หรือหมวด เช่น ``งบลงทุน``) — ใช้เลือกคอลัมน์ให้ถูก
    #: เมื่อค่าเดียวกันอยู่หลายคอลัมน์ · ว่าง = เลือกจากซ้ายไปขวา
    column: str = ""


_PAGES: dict[str, list] = {}


def pages_of(path, sha256: str) -> list:
    """ข้อความทุกหน้า (แคชตาม SHA-256 — ไฟล์ที่เก็บแล้วไม่เปลี่ยน)"""
    if sha256 in _PAGES:
        return _PAGES[sha256]
    backend = pdftext.get_backend()
    if backend is None:
        raise RuntimeError("NO_TEXT_BACKEND")
    pages = backend.pages(path)
    _PAGES[sha256] = pages
    return pages


def _label_keys(label: str) -> list[tuple[str, str]]:
    base = (label or "").strip()
    keys = [base, _LEAD_NO.sub("", base)]
    out = []
    for k in keys:
        k = k.strip()
        if len(_squash(k)) >= 3:
            out.append((_squash(k), _skeleton(k)))
        if len(_squash(k)) > 28:                       # ป้ายยาวอาจขึ้นบรรทัดใหม่ใน PDF
            out.append((_squash(k)[:28], _skeleton(k)[:24]))
    return out


def _line_matches(text: str, keys) -> bool:
    sq, sk = _squash(text), _skeleton(text)
    return any(k_sq and (k_sq in sq or (k_sk and k_sk in sk)) for k_sq, k_sk in keys)


def _band_words(page, line, pad: float = 3.0):
    return [w for w in page.words if w.y1 >= line.y0 - pad and w.y0 <= line.y1 + pad]


def _crop_for(page, y0: float, y1: float, *, above: float = CROP_MARGIN_PT,
              below: float = CROP_MARGIN_PT):
    return (0.0, max(0.0, y0 - above), float(page.width), min(float(page.height), y1 + below))


def _column_x(pg, line, column: str) -> float | None:
    """ตำแหน่งกลางของหัวคอลัมน์ (คำที่อยู่เหนือบรรทัด เช่น ``2570`` · ``งบลงทุน``) — ไม่พบ = None"""
    key = _squash(column)
    cands = [w for w in pg.words if _squash(w.text) == key and w.y1 <= line.y0]
    if not cands:
        return None
    w = max(cands, key=lambda x: x.y1)            # หัวคอลัมน์ที่ใกล้บรรทัดที่สุด
    return (w.x0 + w.x1) / 2


def _match_numbers(pg, line, band, numbers):
    """จับตัวเลขในบรรทัด — คำหนึ่งใช้ได้ครั้งเดียว · มีปีของคอลัมน์ = เลือกคำที่ใกล้หัวคอลัมน์นั้น"""
    used, hits = set(), []
    for num in numbers:
        vs = {_squash(v) for v in num.variants if v}
        cands = [w for w in band if _squash(w.text) in vs and id(w) not in used]
        if not cands:
            continue
        col = _column_x(pg, line, num.column) if num.column else None
        if col is not None:
            w = min(cands, key=lambda x: abs((x.x0 + x.x1) / 2 - col))
        else:
            w = min(cands, key=lambda x: x.x0)
        used.add(id(w))
        hits.append((w, num))
    return hits


def locate(path, sha256: str, *, label: str, numbers: list[Number],
           context: list[str] = (), side: str = "") -> Located:
    """หาบรรทัดของรายการ ``label`` — คะแนน: ป้าย 3 · ตัวเลขที่พบ 2/ค่า · ชื่อแผนงาน/โครงการในหน้า 1"""
    pages = pages_of(path, sha256)
    keys = _label_keys(label)
    ctx = [_squash(c) for c in context if c and len(_squash(c)) >= 6]
    best = None
    for pg in pages:
        page_sq = _squash(" ".join(l.text for l in pg.lines))
        ctx_hit = sum(1 for c in ctx if c[:30] in page_sq)
        for idx, line in enumerate(pg.lines):
            text = line.text
            nxt = pg.lines[idx + 1].text if idx + 1 < len(pg.lines) else ""
            if not (_line_matches(text, keys) or _line_matches(text + nxt, keys[:1])):
                continue
            band = _band_words(pg, line)
            hits = _match_numbers(pg, line, band, numbers)
            score = 3 + 2 * len(hits) + ctx_hit
            if best is None or score > best[0]:
                best = (score, pg, line, hits)
    if best is None:
        return Located(FOUND_NONE, page_count=len(pages))
    _, pg, line, hits = best
    boxes = [Box(line.x0, line.y0, line.x1, line.y1, ROLE_LINE, 0, side)]
    for w, num in hits:
        boxes.append(Box(w.x0, w.y0, w.x1, w.y1, ROLE_CHANGED if num.changed else ROLE_SAME,
                         num.n, side))
    # "พบครบ" = ตัวเลขทุกค่าที่เปลี่ยนอยู่ในบรรทัดนี้ (หรือรายการไม่มีตัวเลขให้หา)
    changed = [n for n in numbers if n.changed] or list(numbers)
    hit = {id(num) for _, num in hits}
    found = FOUND_FULL if all(id(n) in hit for n in changed) else FOUND_TEXT
    return Located(found, pg.page, float(pg.width), float(pg.height), line.text,
                   tuple(boxes), _crop_for(pg, line.y0, line.y1), len(pages))


def locate_area(path, sha256: str, *, anchors: list[str], side: str = "") -> Located:
    """ฝั่งที่ไม่มีรายการ — ชี้บริเวณที่ควรอยู่ (หัวข้อแม่/ชื่อโครงการ) ให้คนดูว่าไม่มีจริง"""
    pages = pages_of(path, sha256)
    for anchor in anchors:
        keys = _label_keys(anchor)
        if not keys:
            continue
        for pg in pages:
            for line in pg.lines:
                if _line_matches(line.text, keys):
                    box = Box(line.x0, line.y0, float(pg.width) - line.x0, line.y1 + 160,
                              ROLE_AREA, 0, side)
                    return Located(FOUND_AREA, pg.page, float(pg.width), float(pg.height),
                                   line.text, (box,),
                                   _crop_for(pg, line.y0, line.y1, above=40, below=220),
                                   len(pages))
    return Located(FOUND_NONE, page_count=len(pages))


# ══════════════════════════════════════════════════════════════════════════════
#  วาดภาพ
# ══════════════════════════════════════════════════════════════════════════════

_COLORS = {
    (ROLE_CHANGED, "A"): ((180, 35, 50), (253, 226, 228)),
    (ROLE_CHANGED, "B"): ((15, 123, 74), (221, 243, 230)),
    (ROLE_SAME, ""): ((85, 96, 112), None),
    (ROLE_LINE, ""): ((176, 141, 62), (248, 242, 227)),
    (ROLE_AREA, ""): ((31, 91, 216), None),
}
_RENDER: dict[str, bytes] = {}


def _color(box: Box):
    return _COLORS.get((box.role, box.side)) or _COLORS.get((box.role, "")) or ((0, 0, 0), None)


def render(path, sha256: str, loc: Located, *, full_page: bool = False) -> bytes:
    """ภาพหน้า PDF (ตัดเฉพาะบริเวณ หรือทั้งหน้า) พร้อมกรอบเน้นและเลขกำกับ — PNG ในหน่วยความจำ"""
    key = hashlib.sha256(repr((sha256, loc.page, loc.boxes, loc.crop, full_page)).encode()).hexdigest()
    if key in _RENDER:
        return _RENDER[key]
    from PIL import Image, ImageDraw, ImageFont

    backend = pdftext.get_backend()
    png = backend.render_png(path, loc.page, zoom=ZOOM)
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(over)
    s = ZOOM
    for b in sorted(loc.boxes, key=lambda x: x.role != ROLE_LINE):   # บรรทัดก่อน ตัวเลขทับ
        outline, fill = _color(b)
        rect = (b.x0 * s - 3, b.y0 * s - 3, b.x1 * s + 3, b.y1 * s + 3)
        if fill:
            draw.rectangle(rect, fill=fill + (60,))
        draw.rectangle(rect, outline=outline + (255,), width=3 if b.role != ROLE_LINE else 2)
    img = Image.alpha_composite(img, over)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:                                   # Pillow รุ่นเก่า
        font = ImageFont.load_default()
    for b in loc.boxes:
        if not b.n:
            continue
        outline, _ = _color(b)
        cx, cy, r = b.x1 * s + 14, b.y0 * s - 2, 12
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=outline + (255,))
        draw.text((cx, cy), str(b.n), fill=(255, 255, 255, 255), font=font, anchor="mm")
    if not full_page and loc.crop:
        x0, y0, x1, y1 = loc.crop
        img = img.crop((int(x0 * s), int(y0 * s), int(x1 * s), int(y1 * s)))
    rgb = img.convert("RGB")
    out = pdftext._encode_png(rgb.tobytes(), rgb.width, rgb.height)
    if len(_RENDER) > 64:
        _RENDER.clear()
    _RENDER[key] = out
    return out


__all__ = ["PDF_EVIDENCE_VERSION", "FOUND_FULL", "FOUND_TEXT", "FOUND_AREA", "FOUND_NONE",
           "FOUND_LABELS", "Box", "Located", "Number", "locate", "locate_area", "render",
           "pages_of"]
