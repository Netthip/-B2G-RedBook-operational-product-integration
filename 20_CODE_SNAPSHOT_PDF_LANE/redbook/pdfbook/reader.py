# -*- coding: utf-8 -*-
"""อ่านชั้นข้อความ PDF สำหรับสายเทียบเล่ม — ผ่าน **product backend** และด่าน holdout/sealed เสมอ

* ``page_texts`` — ข้อความทั้งเล่มแบบเร็ว (pypdfium2) ใช้หาช่วงหน้าของหน่วยงาน
* ``page_words`` — คำพร้อมกรอบ (pdfplumber) เฉพาะหน้าที่อยู่ในช่วง — เล่มจริงหลายร้อยหน้า
  จึงไม่ต้องจัดคำทุกหน้า

🔴 ไม่ OCR · ไม่มี fallback ไป PyMuPDF · backend ใช้ไม่ได้ = ``ReaderUnavailable`` (บอกตรง ๆ)
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path

from ..evidence import pdftext


class ReaderUnavailable(RuntimeError):
    pass


def _backend():
    b = pdftext.product_backend()
    if b is None:
        raise ReaderUnavailable(pdftext.backend_unavailable_reason()
                                or "เครื่องนี้ไม่มีตัวอ่านชั้นข้อความ PDF (pdfplumber + pypdfium2)")
    return b


#: PDFium (pypdfium2) ใช้จากหลายเธรดพร้อมกันไม่ได้ — เธรดเตรียมเล่มเบื้องหลัง + คำขอวาดภาพเคยชนกันจนได้ 500
#: ทุกการเรียก PDFium ในโมดูลนี้จึงผ่านกุญแจเดียว (ทีละงาน · งานละเสี้ยววินาที)
_PDFIUM = threading.RLock()


def _one_at_a_time(fn):
    import functools

    @functools.wraps(fn)
    def run(*a, **k):
        with _PDFIUM:
            return fn(*a, **k)
    return run


def _guard(path) -> Path:
    return pdftext._guards(path)          # ด่าน holdout + sealed ก่อนแตะไฟล์ (บรรทัดแรก)


@_one_at_a_time
def page_count(path) -> int:
    """จำนวนหน้า — นับด้วย PDFium (ไม่ไล่สร้างทุกหน้าแบบ pdfplumber ซึ่งใช้ ~1 วินาทีกับเล่มรวม 1,300 หน้า)"""
    p = _guard(path)
    import pypdfium2
    doc = pypdfium2.PdfDocument(str(p))
    try:
        return len(doc)
    finally:
        doc.close()


#: เอกสาร pdfplumber ที่เปิดค้างไว้ (ล่าสุดไม่เกิน 4 เล่ม) — กุญแจรวมเวลาแก้ไข/ขนาดไฟล์ ⇒ ไฟล์เปลี่ยน = เปิดใหม่
_OPEN_MAX = 4
_open_docs: "OrderedDict[tuple, _Doc]" = OrderedDict()
_open_lock = threading.Lock()
_reads = threading.local()


class _Doc:
    """เอกสารในแคช + จำนวนผู้อ่านที่ปักไว้ (Bo REVIEW 6409941573 ข้อ 1) — ตัดออกจากแคชได้เสมอ แต่ **ปิดจริงเมื่อไม่มีใคร
    ปักแล้ว** · ปัก/ถอดภายใต้ ``_open_lock`` ตัวเดียวกับการตัดออก จึงไม่มีช่วงที่ผู้อ่านได้เอกสารที่ถูกปิดแล้ว"""
    __slots__ = ("pdf", "lock", "sha", "refs", "evicted", "closed")

    def __init__(self, pdf, sha: str):
        self.pdf, self.lock, self.sha = pdf, threading.Lock(), sha
        self.refs, self.evicted, self.closed = 0, False, False


def _close(doc: _Doc) -> None:
    doc.closed = True
    try:
        doc.pdf.close()
    except Exception:  # noqa: BLE001
        pass


def _evict_locked(key) -> list:
    """ตัดออกจากแคช (ถือ ``_open_lock`` อยู่) — คืนเอกสารที่ปิดได้ทันที (ไม่มีผู้ปัก) ให้ผู้เรียกปิดนอกกุญแจ"""
    doc = _open_docs.pop(key)
    doc.evicted = True
    return [doc] if doc.refs == 0 else []


@contextmanager
def _pinned(p: Path):
    """ปักเอกสารของไฟล์ไว้ตลอดช่วงอ่าน — เปิดครั้งเดียวแล้วใช้ซ้ำ (รายการหน้าของเล่มรวมสร้างครั้งเดียว ~0.7 วินาที)

    เปิดจาก **สำเนาไบต์ในหน่วยความจำ** ไม่ถือไฟล์บนดิสก์ — บน Windows ไฟล์ที่ถูกเปิดค้างลบ/แทนที่ไม่ได้
    (ปุ่มลบไฟล์ของ ``storage.files.delete`` · ``shelf_add.py`` แทนที่เล่ม) · ไม่เกิน 4 เล่ม (เล่มรวม ~5–13 MB) ·
    ``sha`` = ของไบต์ที่เปิดจริง — กุญแจแคชเป็นเวลาแก้ไข/ขนาด จึงต้องยืนยันเนื้อไฟล์แยก (:func:`track_reads`)"""
    import hashlib
    import io
    st = p.stat()
    key = (str(p), st.st_mtime_ns, st.st_size)
    to_close: list = []
    with _open_lock:
        doc = _open_docs.get(key)
        if doc is not None:
            _open_docs.move_to_end(key)
        else:
            data = p.read_bytes()
            pdf = _backend()._plumber.open(io.BytesIO(data))
            _ = pdf.pages                               # สร้างรายการหน้าครั้งเดียว
            doc = _open_docs[key] = _Doc(pdf, hashlib.sha256(data).hexdigest())
        doc.refs += 1                                   # ปักก่อนปล่อยกุญแจ — การตัดออกหลังจากนี้ปิดไม่ได้
        while len(_open_docs) > _OPEN_MAX:
            to_close += _evict_locked(next(iter(_open_docs)))
    for d in to_close:
        _close(d)
    try:
        yield doc
    finally:
        with _open_lock:
            doc.refs -= 1
            last = doc.evicted and doc.refs == 0 and not doc.closed
        if last:
            _close(doc)


@contextmanager
def track_reads():
    """ชุด SHA-256 ของเอกสารที่ :func:`page_words` **อ่านจริง** ในเธรดนี้ระหว่างบล็อก — ผูกหลักฐาน SHA กับเอกสารที่อ่าน
    ไม่ใช่กับสถานะแคชตอนตรวจ (เอกสารอาจถูกตัดออกจากแคชระหว่างนั้น)"""
    stack = getattr(_reads, "stack", None)
    if stack is None:
        stack = _reads.stack = []
    got: set = set()
    stack.append(got)
    try:
        yield got
    finally:
        stack.remove(got)


def doc_sha(path) -> str | None:
    """SHA-256 ของไบต์ที่เอกสารในแคชของไฟล์นี้ (สถานะไฟล์ปัจจุบัน) เปิดมา — ``None`` = ไม่อยู่ในแคช

    ไฟล์ที่ถูกแทนด้วยขนาดและเวลาแก้ไขเดิม (เช่น คัดลอกแบบคงเวลา) ได้กุญแจแคชเดิม → ได้เอกสารเก่า · ค่านี้จะไม่ตรงกับ
    SHA ของไฟล์ใหม่ (#42) · การยืนยันผลใช้ :func:`track_reads` (เอกสารที่อ่านจริง) ไม่ใช่ค่านี้"""
    p = _guard(path)
    st = p.stat()
    with _open_lock:
        doc = _open_docs.get((str(p), st.st_mtime_ns, st.st_size))
    return doc.sha if doc else None


def close_all() -> None:
    """ตัดทุกเล่มออกจากแคช — เล่มที่กำลังมีผู้อ่านปิดเมื่ออ่านเสร็จ"""
    to_close: list = []
    with _open_lock:
        while _open_docs:
            to_close += _evict_locked(next(iter(_open_docs)))
    for d in to_close:
        _close(d)


@_one_at_a_time
def page_size(path, page: int) -> tuple[float, float]:
    """(กว้าง, สูง) ของหน้าเป็น pt — ใช้แปลงตำแหน่งที่ผู้ตรวจคลิกบนภาพ (สัดส่วน) เป็นพิกัดหน้า"""
    p = _guard(path)
    import pypdfium2
    doc = pypdfium2.PdfDocument(str(p))
    try:
        w, h = doc[page - 1].get_size()
        return float(w), float(h)
    finally:
        doc.close()


@_one_at_a_time
def page_texts(path, pages: list[int] | None = None) -> list[str]:
    """ข้อความดิบ (index 0 = หน้า 1) — ``pages`` = อ่านเฉพาะหน้าที่ระบุ หน้าอื่นคืนข้อความว่าง

    🔴 ใช้ ``pages`` เสมอกับเล่มรวมทั้งกระทรวง เพื่อไม่ให้ระบบอ่านเนื้อหาหน้าของหน่วยงานอื่น
    (รวมหน่วยที่กันไว้) — ดู :func:`redbook.pdfbook.scope.find_by_toc`
    """
    p = _guard(path)
    import pypdfium2
    doc = pypdfium2.PdfDocument(str(p))
    try:
        want = None if pages is None else {int(x) for x in pages}
        out = []
        for i in range(len(doc)):
            if want is not None and (i + 1) not in want:
                out.append("")
                continue
            page = doc[i]
            tp = page.get_textpage()
            try:
                out.append(tp.get_text_range() or "")
            finally:
                tp.close()
                page.close()
        return out
    finally:
        doc.close()


@_one_at_a_time
def margin_texts(path, pages: list[int], band_pt: float = 72.0) -> dict[int, str]:
    """ข้อความเฉพาะแถบขอบบนและขอบล่างของหน้า (เลขหน้าที่พิมพ์) — ไม่อ่านเนื้อหากลางหน้า"""
    p = _guard(path)
    import pypdfium2
    doc = pypdfium2.PdfDocument(str(p))
    try:
        out = {}
        for no in pages:
            if no < 1 or no > len(doc):
                continue
            page = doc[no - 1]
            w, h = page.get_size()
            tp = page.get_textpage()
            try:
                bottom = tp.get_text_bounded(left=0, bottom=0, right=w, top=band_pt) or ""
                top = tp.get_text_bounded(left=0, bottom=h - band_pt, right=w, top=h) or ""
                out[no] = (top + "\n" + bottom).strip()
            finally:
                tp.close()
                page.close()
        return out
    finally:
        doc.close()


#: สระบน/ล่าง วรรณยุกต์ การันต์ นิคหิต — กว้าง 0 pt และวางซ้อนบนพยัญชนะ
THAI_MARKS = frozenset(chr(c) for c in (0x0E31, *range(0x0E34, 0x0E3B), *range(0x0E47, 0x0E4F)))
NIKHAHIT = "ํ"
SARA_AA = "า"
#: ช่องว่างระหว่างอักขระที่ถือว่าขึ้นคำใหม่ (เท่าค่าตั้งต้นของ pdfplumber)
WORD_GAP_PT = 3.0
#: "ช่องว่าง" กว้างไม่ถึงค่านี้ระหว่างอักษรไทย = รูปนิคหิตของ ำ ที่ฟอนต์ในเล่มเข้ารหัสเป็น U+0020
ZERO_WIDTH_PT = 0.5


def _is_thai(ch: str) -> bool:
    return "฀" <= ch <= "๿"


def words_from_chars(chars, line_tol: float = 3.0) -> list:
    """จัดอักขระเป็นคำ **ตามลำดับ content stream** — แทน ``extract_words`` ของ pdfplumber

    pdfplumber จัดกลุ่มด้วยตำแหน่ง สระบน/วรรณยุกต์ที่กว้าง 0 pt และวางเยื้องซ้ายของพยัญชนะ
    จึงหลุดไปอยู่คำอื่นหรือหาย ("ที่มี" → "ทีมี่" · "ต่ำกว่า" → "ากว่") · ที่นี่เครื่องหมายเกาะคำปัจจุบันเสมอ
    และช่องว่างกว้าง 0 pt ระหว่างอักษรไทยแปลงกลับเป็นนิคหิต (ซ่อมเป็น ำ ใน :mod:`thai_repair`)
    """
    from ..evidence.pdftext import Word

    raw: list[dict] = []
    cur: dict | None = None

    def flush():
        nonlocal cur
        if cur is not None and cur["text"].strip():
            raw.append(cur)
        cur = None

    for i, c in enumerate(chars):
        t = c.get("text") or ""
        if not t:
            continue
        x0, x1 = float(c["x0"]), float(c["x1"])
        top, bottom = float(c["top"]), float(c["bottom"])
        if t.isspace():
            j = i + 1          # อักขระถัดไปที่ไม่ใช่เครื่องหมาย (เล่มจริง: ต + ช่องว่าง 0 pt + ่ + า)
            while j < len(chars) and (chars[j].get("text") or "") in THAI_MARKS:
                j += 1
            nxt = chars[j].get("text", "") if j < len(chars) else ""
            # เฉพาะรูป ำ ในเล่ม: [พยัญชนะ(+วรรณยุกต์)] + ช่องว่าง 0 pt + "า" — ช่องว่างกว้าง 0 ที่อื่น
            # (ระหว่างพยัญชนะ · ก่อนตัวเลข · ระหว่างตัวเลข) ไม่ใช่นิคหิต (negative controls ใน tests)
            if (x1 - x0) < ZERO_WIDTH_PT and cur is not None and _is_thai(cur["text"][-1:]) \
                    and nxt[:1] == SARA_AA:
                cur["text"] += NIKHAHIT
                continue
            flush()
            continue
        if t in THAI_MARKS and cur is not None and abs(top - cur["top"]) <= line_tol:
            cur["text"] += t
            continue
        if cur is not None and (abs(top - cur["top"]) > line_tol
                                or x0 > cur["lx1"] + WORD_GAP_PT or x1 < cur["lx0"] - WORD_GAP_PT):
            flush()
        if cur is None:
            cur = {"text": t, "x0": x0, "x1": x1, "top": top, "bottom": bottom, "lx0": x0, "lx1": x1}
        else:
            cur["text"] += t
            cur["x0"], cur["x1"] = min(cur["x0"], x0), max(cur["x1"], x1)
            cur["bottom"] = max(cur["bottom"], bottom)
            cur["lx0"], cur["lx1"] = x0, x1
    flush()

    raw.sort(key=lambda w: (w["top"], w["x0"]))
    words, line_no, last_top = [], -1, None
    for w in raw:
        if last_top is None or abs(w["top"] - last_top) > line_tol:
            line_no += 1
            last_top = w["top"]
        words.append(Word(text=w["text"], x0=w["x0"], y0=w["top"], x1=w["x1"], y1=w["bottom"],
                          block=0, line=line_no))
    return words


def crop_frame(page) -> tuple[float, float, float, float]:
    """(x0, top, x1, bottom) ของ CropBox ในพิกัดของ pdfplumber (มุมซ้ายบนของ MediaBox) — ส่วนของหน้าที่คนเห็น
    และที่ PDFium วาด · ไม่มี CropBox / เกินขอบ = ตัดด้วย MediaBox (pdfbook-0.5.1)

    เล่มจริงบางเล่มเป็นปกกางสองหน้า (MediaBox 1244 pt = ปกหลัง + สัน + ปกหน้า) แต่ CropBox เปิดเฉพาะปกหน้า —
    ข้อความบนปกหลัง (เช่น ปีงบของเล่มปีก่อน) อยู่ในชั้นข้อความแต่คนมองไม่เห็น"""
    mx0, mtop, mx1, mbottom = (float(x) for x in page.mediabox)
    box = getattr(page, "cropbox", None) or page.mediabox
    x0, top, x1, bottom = (float(x) for x in box)
    x0, top, x1, bottom = max(x0, mx0), max(top, mtop), min(x1, mx1), min(bottom, mbottom)
    if x1 - x0 < 1 or bottom - top < 1:
        return mx0, mtop, mx1, mbottom
    return x0, top, x1, bottom


def page_words(path, pages: list[int]) -> list:
    """``PageText`` ของหน้าที่ระบุ (1-based) ตามลำดับ — โครงสร้างเดียวกับ :mod:`pdftext`

    พิกัดคำเทียบมุมซ้ายบนของ **CropBox** และ ``width``/``height`` = ขนาด CropBox (:func:`crop_frame`) —
    ตรงกับภาพที่ :func:`render_png` วาดและขนาดหน้าของ :func:`page_size` · คำที่อยู่นอกกรอบจึงถูกตัดโดย
    ``extract._visible`` เหมือนข้อความนอกขอบกระดาษ · หน้าที่ CropBox = MediaBox ได้ผลเดิมทุกไบต์"""
    from dataclasses import replace
    p = _guard(path)
    b = _backend()
    want = sorted(set(int(x) for x in pages))
    out = []
    with _pinned(p) as doc, doc.lock:
        for stack in getattr(_reads, "stack", ()):
            stack.add(doc.sha)                          # เอกสารที่อ่านจริง (track_reads)
        n = len(doc.pdf.pages)
        for no in want:
            if no < 1 or no > n:
                continue
            page = doc.pdf.pages[no - 1]
            fx0, ftop, fx1, fbottom = crop_frame(page)
            words = words_from_chars(page.chars, b.LINE_TOLERANCE_PT)
            if fx0 or ftop:
                words = [replace(w, x0=w.x0 - fx0, x1=w.x1 - fx0, y0=w.y0 - ftop, y1=w.y1 - ftop) for w in words]
            out.append(pdftext.PageText(page=no, width=fx1 - fx0, height=fbottom - ftop, words=tuple(words),
                                        lines=pdftext._lines_from_words(words)))
            page.flush_cache()                          # ไม่เก็บอักขระของหน้าไว้ในหน่วยความจำ
    return out


@_one_at_a_time
def render_png(path, page: int, *, highlight=None, zoom: float = 1.6) -> bytes:
    return _backend().render_png(path, page, highlight=highlight, zoom=zoom)
