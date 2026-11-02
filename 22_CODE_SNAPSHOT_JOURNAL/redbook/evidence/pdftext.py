# -*- coding: utf-8 -*-
"""ชั้นข้อความของ PDF — อ่านคำพร้อมกรอบ (bounding box) ทีละหน้า และวาดหน้าเป็นภาพ

**หลักการ**

1. **backend เป็นของเสริม** — ถ้าไม่มีไลบรารีอ่าน PDF ในเครื่อง ระบบต้อง *บอกตรง ๆ*
   ว่าอ่านชั้นข้อความไม่ได้ (``NO_TEXT_BACKEND``) ไม่ใช่รายงานว่า "ไม่พบตัวชี้วัด"
   ซึ่งอ่านจากปลายทางแล้วแยกไม่ออกจาก "ตรวจแล้วไม่มี"
   · **backend ของสายผลิตภัณฑ์ = `pdfplumber` (pdfminer.six · MIT) + `pypdfium2` (BSD-3/Apache-2.0)
   เท่านั้น** (`PRODUCT_BACKEND`) · 🔴 **ไม่มี fallback อัตโนมัติ** — ถ้า backend นี้ใช้ไม่ได้
   ``product_backend()`` คืน ``None`` และระบบรายงาน ``NO_TEXT_BACKEND`` (fail-closed ตาม
   Bo `5598957701` ข้อ P1-1 · `5598526148` Lane B6.1)
   · `PyMuPDF` (AGPL/commercial) เรียกได้ **เฉพาะ** ``research_backend()`` ซึ่งเป็น
   explicit research/dev path สำหรับเทสต์เทียบผล — route/ชั้นบริการของผลิตภัณฑ์เรียกไม่ได้
   (มีเทสต์บังคับ) · **ห้ามใส่ PyMuPDF ในชุด dependency ปริยาย**
2. **ไม่ OCR** — หน้าที่ไม่มีชั้นข้อความรายงานเป็น ``TEXT_LAYER_ABSENT`` และทุกตำแหน่ง
   ในหน้านั้นเป็น ``LOCATION_REVIEW_REQUIRED`` (คำสั่งกิ๊ฟ §3)
3. **ไม่แก้ไฟล์** — ไม่มีคำสั่งบันทึกใด ๆ · การวาดกรอบเน้นทำบนสำเนาในหน่วยความจำ
   แล้วส่งออกเป็น PNG เท่านั้น (เทสต์สถาปัตยกรรมกัน ``.save()`` ทั้งแพ็กเกจ)
4. ด่าน :mod:`redbook.holdout` และ :mod:`redbook.sealed_key` ถูกเรียก **ก่อน**
   บรรทัดแรกที่แตะไฟล์

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import holdout, sealed_key

PDFTEXT_VERSION = "pdftext-0.2.0"

TEXT_LAYER_PRESENT = "TEXT_LAYER_PRESENT"
TEXT_LAYER_ABSENT = "TEXT_LAYER_ABSENT"
TEXT_LAYER_PARTIAL = "TEXT_LAYER_PARTIAL"
TEXT_LAYER_NOT_CHECKED = "TEXT_LAYER_NOT_CHECKED_NO_BACKEND"

NO_TEXT_BACKEND = "NO_TEXT_BACKEND"

#: จำนวนอักขระขั้นต่ำที่ถือว่าหน้านั้น "มีชั้นข้อความ" — กันหน้าที่มีแค่เลขหน้า
MIN_CHARS_FOR_TEXT_LAYER = 8


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block: int
    line: int


@dataclass(frozen=True)
class Line:
    """หนึ่งบรรทัดตามที่ backend จัดกลุ่มให้ — กรอบคือ union ของคำในบรรทัด"""
    index: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass(frozen=True)
class PageText:
    page: int                      # 1-based
    width: float
    height: float
    words: tuple[Word, ...]
    lines: tuple[Line, ...]

    @property
    def char_count(self) -> int:
        return sum(len(w.text) for w in self.words)

    @property
    def has_text_layer(self) -> bool:
        return self.char_count >= MIN_CHARS_FOR_TEXT_LAYER


def _guards(path) -> Path:
    p = Path(path)
    holdout.assert_not_holdout(p)
    sealed_key.assert_not_sealed(p)
    return p


def _lines_from_words(words: list[Word]) -> tuple[Line, ...]:
    groups: dict[tuple[int, int], list[Word]] = {}
    for w in words:
        groups.setdefault((w.block, w.line), []).append(w)
    lines: list[Line] = []
    for idx, key in enumerate(sorted(groups, key=lambda k: (
            min(x.y0 for x in groups[k]), min(x.x0 for x in groups[k])))):
        ws = sorted(groups[key], key=lambda x: x.x0)
        lines.append(Line(
            index=idx, text=" ".join(x.text for x in ws),
            x0=min(x.x0 for x in ws), y0=min(x.y0 for x in ws),
            x1=max(x.x1 for x in ws), y1=max(x.y1 for x in ws)))
    return tuple(lines)



def _encode_png(rgb: bytes, width: int, height: int) -> bytes:
    """เข้ารหัส PNG (RGB 8 บิต · ไม่มี filter) ในหน่วยความจำ — ไม่พึ่งคำสั่งบันทึกไฟล์ของไลบรารีใด"""
    import struct
    import zlib

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    stride = width * 3
    raw = b"".join(b"\x00" + rgb[y * stride:(y + 1) * stride] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))

class PdfplumberPdfiumBackend:
    """backend ปริยาย (สิทธิ์ผ่อนปรน) — pdfplumber/pdfminer.six อ่านคำ+กรอบ · pypdfium2 วาดหน้า

    * พิกัด: pdfplumber ให้ ``top/bottom`` วัดจากขอบบนของหน้า (หน่วย point) เหมือน PyMuPDF
    * การจัดบรรทัด: pdfminer ไม่ให้เลข block/line เหมือน PyMuPDF จึงจัดกลุ่มคำด้วย
      ``top`` ที่ห่างกันไม่เกิน ``LINE_TOLERANCE_PT`` — ผลบรรทัดต้องเทียบเท่า PyMuPDF
      บน fixture (มีเทสต์ equivalence)
    * กรอบเน้นวาดด้วย Pillow บนภาพที่ pypdfium2 วาด — ไม่มีคำสั่งบันทึกไฟล์ใด
    """

    name = "pdfplumber+pypdfium2"
    LINE_TOLERANCE_PT = 3.0

    def __init__(self):
        import pdfplumber                       # noqa: F401
        import pypdfium2                        # noqa: F401
        from importlib.metadata import version as _v
        self._plumber = pdfplumber
        self._pdfium = pypdfium2
        self.version = (f"pdfplumber {_v('pdfplumber')} · pdfminer.six {_v('pdfminer.six')} "
                        f"· pypdfium2 {_v('pypdfium2')}")

    def page_count(self, path) -> int:
        p = _guards(path)
        with self._plumber.open(str(p)) as pdf:
            return len(pdf.pages)

    def _words(self, page) -> list[Word]:
        raw = page.extract_words(use_text_flow=True, keep_blank_chars=False)
        # จัดกลุ่มเป็นบรรทัดด้วย top (คำที่ top ต่างกันไม่เกิน tolerance = บรรทัดเดียวกัน)
        raw.sort(key=lambda w: (float(w["top"]), float(w["x0"])))
        words: list[Word] = []
        line_no, last_top = -1, None
        for w in raw:
            top = float(w["top"])
            if last_top is None or abs(top - last_top) > self.LINE_TOLERANCE_PT:
                line_no += 1
                last_top = top
            words.append(Word(text=w["text"], x0=float(w["x0"]), y0=top,
                              x1=float(w["x1"]), y1=float(w["bottom"]),
                              block=0, line=line_no))
        return words

    def pages(self, path) -> list[PageText]:
        p = _guards(path)
        out: list[PageText] = []
        with self._plumber.open(str(p)) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                words = self._words(page)
                out.append(PageText(
                    page=i, width=float(page.width), height=float(page.height),
                    words=tuple(words), lines=_lines_from_words(words)))
        return out

    def render_png(self, path, page: int, *, highlight=None, zoom: float = 1.6) -> bytes:
        """วาดหน้า ``page`` (1-based) เป็น PNG ด้วย pypdfium2 · กรอบเน้นวาดทับด้วย Pillow

        PNG ถูกเข้ารหัสเองจากไบต์ RGB (:func:`_encode_png`) — **ไม่เรียก** ``Image.save``
        เพราะแพ็กเกจฝ่ายตรวจห้ามมีคำสั่งบันทึกไฟล์ (เทสต์สถาปัตยกรรม) และภาพนี้อยู่ใน
        หน่วยความจำเท่านั้น
        """
        from PIL import Image, ImageDraw

        p = _guards(path)
        pdf = self._pdfium.PdfDocument(str(p))
        try:
            if page < 1 or page > len(pdf):
                raise ValueError("page out of range")
            pg = pdf[page - 1]
            img = pg.render(scale=zoom).to_pil().convert("RGBA")
            if highlight is not None:
                x0, y0, x1, y1 = highlight
                pad = 2.0
                box = (max(0, (x0 - pad) * zoom), max(0, (y0 - pad) * zoom),
                       min(img.width, (x1 + pad) * zoom), min(img.height, (y1 + pad) * zoom))
                overlay = img.copy()
                ImageDraw.Draw(overlay).rectangle(box, fill=(255, 217, 77, 255))
                img = Image.blend(img, overlay, 0.32)
                ImageDraw.Draw(img).rectangle(box, outline=(224, 71, 76, 255), width=2)
            rgb = img.convert("RGB")
            return _encode_png(rgb.tobytes(), rgb.width, rgb.height)
        finally:
            pdf.close()


class PyMuPdfBackend:
    """backend เสริมสำหรับเทียบผล (PyMuPDF · AGPL/commercial) — **ไม่ใช่ค่าปริยาย**

    ติดตั้งผ่าน ``requirements-research-pymupdf.txt`` เท่านั้น · ใช้ใน equivalence test
    และการเทียบผลในสภาพแวดล้อมพัฒนา · ห้ามใช้ในการตรึงเวอร์ชันผลิตภัณฑ์จนกว่าจะปิด
    `LICENSE REVIEW REQUIRED`
    """

    name = "pymupdf"

    def __init__(self):
        import fitz  # noqa: F401  (PyMuPDF)
        self._fitz = fitz
        self.version = getattr(fitz, "VersionBind", "?")

    def page_count(self, path) -> int:
        p = _guards(path)
        with self._fitz.open(str(p)) as doc:
            return int(doc.page_count)

    def pages(self, path) -> list[PageText]:
        p = _guards(path)
        out: list[PageText] = []
        with self._fitz.open(str(p)) as doc:
            for i, page in enumerate(doc, 1):
                words = [Word(text=w[4], x0=float(w[0]), y0=float(w[1]),
                              x1=float(w[2]), y1=float(w[3]),
                              block=int(w[5]), line=int(w[6]))
                         for w in page.get_text("words")]
                rect = page.rect
                out.append(PageText(
                    page=i, width=float(rect.width), height=float(rect.height),
                    words=tuple(words), lines=_lines_from_words(words)))
        return out

    def render_png(self, path, page: int, *, highlight=None, zoom: float = 1.6) -> bytes:
        """วาดหน้า ``page`` (1-based) เป็น PNG · ``highlight`` = (x0,y0,x1,y1) หน่วย point

        การวาดกรอบทำบนวัตถุหน้าในหน่วยความจำแล้วทิ้ง — ไฟล์ต้นฉบับไม่ถูกแตะ
        """
        p = _guards(path)
        fitz = self._fitz
        with fitz.open(str(p)) as doc:
            if page < 1 or page > doc.page_count:
                raise ValueError("page out of range")
            pg = doc[page - 1]
            if highlight is not None:
                x0, y0, x1, y1 = highlight
                pad = 2.0
                rect = fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad) & pg.rect
                shape = pg.new_shape()
                shape.draw_rect(rect)
                shape.finish(color=(0.88, 0.28, 0.30), fill=(1.0, 0.85, 0.30),
                             fill_opacity=0.32, width=1.6)
                shape.commit()
            pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            return pix.tobytes("png")


_BACKEND_CACHE: dict = {}

#: 🔴 backend เดียวของสายผลิตภัณฑ์ — **ไม่ใช่รายการลำดับ** เพราะการมีลำดับสำรองคือ
#: ตัวที่ทำให้ PyMuPDF ถูกเลือกโดยปริยายเมื่อตัวแรกพัง (ข้อบกพร่อง P1-1 ที่ Bo ชี้)
PRODUCT_BACKEND: type = PdfplumberPdfiumBackend
#: backend ที่เรียกได้เฉพาะ explicit research/dev path (เทสต์เทียบผล) — ห้ามใช้ในผลิตภัณฑ์
RESEARCH_BACKEND: type = PyMuPdfBackend

DEFAULT_BACKEND_NAME = PdfplumberPdfiumBackend.name
RESEARCH_BACKEND_NAME = PyMuPdfBackend.name

MODE_PRODUCT = "PRODUCT_PERMISSIVE_ONLY"
MODE_RESEARCH = "RESEARCH_EXPLICIT"

#: เหตุผลที่ product backend ใช้ไม่ได้ — เก็บไว้ให้รายงานได้ว่า *ทำไม* ไม่ใช่แค่ว่าไม่มี
_UNAVAILABLE_REASON = "backend_unavailable_reason"


def product_backend():
    """backend ของสายผลิตภัณฑ์ — คืน ``None`` เมื่อใช้ไม่ได้ · **ไม่มี fallback**

    🔴 กติกา (Bo `5598957701` P1-1) — ถ้า ``PRODUCT_BACKEND`` สร้างไม่สำเร็จ ต้องคืน
    ``None`` แล้วให้ผู้เรียกรายงาน ``NO_TEXT_BACKEND`` **ห้าม** หันไปใช้ PyMuPDF แม้จะ
    ติดตั้งอยู่ในเครื่อง เพราะ PyMuPDF เป็น AGPL/commercial ที่ยังไม่ผ่าน license clearance
    ⇒ การเงียบ ๆ เปลี่ยน backend คือการเปลี่ยนสัญญาอนุญาตของผลิตภัณฑ์โดยไม่มีใครรู้
    """
    if "product" in _BACKEND_CACHE:
        return _BACKEND_CACHE["product"]
    try:
        backend = PRODUCT_BACKEND()
    except Exception as e:       # noqa: BLE001 — ไม่มีไลบรารี/พังตอน init = ไม่มี backend
        backend = None
        _BACKEND_CACHE[_UNAVAILABLE_REASON] = f"{type(e).__name__}"
    _BACKEND_CACHE["product"] = backend
    return backend


def research_backend():
    """backend สำหรับเทียบผลในสภาพแวดล้อมพัฒนา — **ต้องเรียกโดยเจตนา**

    ใช้ได้เฉพาะเทสต์ equivalence และเครื่องมือสร้าง fixture · route/ชั้นบริการของผลิตภัณฑ์
    ห้ามเรียก (เทสต์บังคับด้วย AST) · คืน ``None`` ถ้าไม่ได้ติดตั้ง extra วิจัย
    """
    if "research" in _BACKEND_CACHE:
        return _BACKEND_CACHE["research"]
    try:
        backend = RESEARCH_BACKEND()
    except Exception:            # noqa: BLE001
        backend = None
    _BACKEND_CACHE["research"] = backend
    return backend


def get_backend():
    """ทางเข้าเดียวของสายผลิตภัณฑ์ — alias ของ :func:`product_backend`

    คงชื่อเดิมไว้เพื่อไม่ให้ผู้เรียกเดิมเปลี่ยนพฤติกรรมโดยไม่รู้ตัว · ความหมายเปลี่ยนแล้ว:
    **ไม่หา backend สำรองอีก**
    """
    return product_backend()


def backend_unavailable_reason() -> str:
    """ชนิดข้อผิดพลาดตอนสร้าง product backend (ถ้ามี) — ใช้รายงาน ไม่ใช่ข้อความผู้ใช้"""
    return str(_BACKEND_CACHE.get(_UNAVAILABLE_REASON, ""))


def backend_name() -> str:
    b = product_backend()
    return b.name if b is not None else NO_TEXT_BACKEND


def backend_report(*, mode: str = MODE_PRODUCT) -> dict:
    """สิ่งที่ต้องบันทึกลง run/manifest (Bo `5598526148` Lane B6.1 ข้อ 4)"""
    b = product_backend() if mode == MODE_PRODUCT else research_backend()
    return {
        "mode": mode,
        "backend": (b.name if b is not None else NO_TEXT_BACKEND),
        "backend_version": (getattr(b, "version", "") if b is not None else ""),
        "product_backend_declared": PRODUCT_BACKEND.name,
        "fallback_allowed": False,
        "unavailable_reason": backend_unavailable_reason() if b is None else "",
    }


def _reset_backend_cache() -> None:
    """ใช้ในเทสต์เท่านั้น — ล้างแคชการเลือก backend"""
    _BACKEND_CACHE.clear()


def text_layer_status(pages: list[PageText] | None) -> str:
    if pages is None:
        return TEXT_LAYER_NOT_CHECKED
    if not pages:
        return TEXT_LAYER_ABSENT
    flags = [p.has_text_layer for p in pages]
    if all(flags):
        return TEXT_LAYER_PRESENT
    if not any(flags):
        return TEXT_LAYER_ABSENT
    return TEXT_LAYER_PARTIAL


__all__ = [
    "PDFTEXT_VERSION", "TEXT_LAYER_PRESENT", "TEXT_LAYER_ABSENT",
    "TEXT_LAYER_PARTIAL", "TEXT_LAYER_NOT_CHECKED", "NO_TEXT_BACKEND",
    "MIN_CHARS_FOR_TEXT_LAYER", "Word", "Line", "PageText", "PdfplumberPdfiumBackend",
    "PyMuPdfBackend", "PRODUCT_BACKEND", "RESEARCH_BACKEND", "DEFAULT_BACKEND_NAME",
    "RESEARCH_BACKEND_NAME", "MODE_PRODUCT", "MODE_RESEARCH", "product_backend",
    "research_backend", "get_backend", "backend_name", "backend_report",
    "backend_unavailable_reason", "text_layer_status",
]
