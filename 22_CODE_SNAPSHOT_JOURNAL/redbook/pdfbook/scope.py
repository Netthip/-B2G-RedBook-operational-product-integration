# -*- coding: utf-8 -*-
"""หาช่วงหน้าของหน่วยงานในเล่ม — ยึด **เนื้อหา** ไม่ยึดเลขหน้าอย่างเดียว

หน้าเริ่มของหน่วยงาน = หน้าที่มีทั้งคำ ``งบประมาณรายจ่าย`` และหัวข้อ ``วิสัยทัศน์``
(โครงต้นช่วงที่บันทึกไว้ในทะเบียนขอบเขตหน้า) · หน้าจบ = หน้าก่อนหน้าเริ่มของหน่วยงานถัดไป
หรือหน้าสุดท้ายของไฟล์ · เทียบชื่อแบบตัดช่องว่าง แล้วแบบตัดวรรณยุกต์เป็นทางสำรอง

ผลบอกเสมอว่าได้ช่วงมาอย่างไร (``method``) เพื่อให้คนตรวจยืนยันได้ · ผู้ใช้ระบุช่วงหน้าเองได้
(``manual``) และระบบบันทึกว่าเป็นช่วงที่คนกำหนด
"""
from __future__ import annotations

from dataclasses import dataclass

from .text import skeleton, squash

METHOD_SINGLE = "single_agency_file"
METHOD_NAME = "agency_name_match"
METHOD_MANUAL = "manual_range"
METHOD_LABELS = {
    METHOD_SINGLE: "ไฟล์นี้มีหน่วยงานเดียว — ใช้ช่วงตั้งแต่หน้าเริ่มของหน่วยงานถึงหน้าสุดท้าย",
    METHOD_NAME: "ค้นชื่อหน่วยงานในหน้าเริ่มของแต่ละหน่วยงาน แล้วจบก่อนหน้าเริ่มของหน่วยงานถัดไป",
    METHOD_MANUAL: "ผู้ใช้กำหนดช่วงหน้าเอง",
}


class ScopeError(ValueError):
    pass


@dataclass(frozen=True)
class Scope:
    first: int
    last: int
    method: str
    agency_hint: str
    starts_found: tuple = ()       # หน้าเริ่มของทุกหน่วยงานที่พบในไฟล์

    @property
    def pages(self) -> list[int]:
        return list(range(self.first, self.last + 1))

    @property
    def method_label(self) -> str:
        return METHOD_LABELS[self.method]


def _is_start(text: str) -> bool:
    s = skeleton(text)
    return skeleton("งบประมาณรายจ่าย") in s and skeleton("วิสัยทัศน์") in s


def agency_starts(texts: list[str]) -> list[int]:
    return [i + 1 for i, t in enumerate(texts) if _is_start(t)]


def find(texts: list[str], agency: str = "", first: int = 0, last: int = 0) -> Scope:
    n = len(texts)
    starts = agency_starts(texts)
    if first or last:
        f, l = int(first or 1), int(last or n)
        if not (1 <= f <= l <= n):
            raise ScopeError(f"ช่วงหน้าไม่ถูกต้อง (ไฟล์มี {n} หน้า)")
        return Scope(f, l, METHOD_MANUAL, agency, tuple(starts))
    if not starts:
        raise ScopeError("ไม่พบหน้าเริ่มของหน่วยงาน (หน้าที่มี 'งบประมาณรายจ่าย' และ 'วิสัยทัศน์') "
                         "— กรุณากำหนดช่วงหน้าเอง")
    if agency:
        key, sk = squash(agency), skeleton(agency)
        hits = [p for p in starts if key in squash(texts[p - 1])] or \
               [p for p in starts if sk in skeleton(texts[p - 1])]
        if not hits:
            raise ScopeError("ไม่พบชื่อหน่วยงานนี้ในหน้าเริ่มของหน่วยงานใด — ตรวจชื่อ หรือกำหนดช่วงหน้าเอง")
        if len(hits) > 1:
            raise ScopeError("พบชื่อหน่วยงานนี้ในหน้าเริ่มมากกว่าหนึ่งแห่ง — กรุณากำหนดช่วงหน้าเอง")
        f = hits[0]
        later = [p for p in starts if p > f]
        return Scope(f, (later[0] - 1) if later else n, METHOD_NAME, agency, tuple(starts))
    if len(starts) == 1:
        return Scope(starts[0], n, METHOD_SINGLE, "", tuple(starts))
    raise ScopeError(f"ไฟล์นี้มีหน่วยงาน {len(starts)} แห่ง — กรุณาระบุชื่อหน่วยงาน หรือกำหนดช่วงหน้าเอง")


# ══════════════════════════════════════════════════════════════════════════════
#  หาช่วงหน้าจากสารบัญ — อ่านน้อยที่สุด (เล่มรวมทั้งกระทรวง)
# ══════════════════════════════════════════════════════════════════════════════
import re  # noqa: E402

from .text import clean  # noqa: E402

METHOD_TOC = "toc_offset"
METHOD_LABELS[METHOD_TOC] = ("อ่านสารบัญต้นเล่ม + เลขหน้าที่พิมพ์ที่ขอบหน้า แล้วอ่านเฉพาะหน้าของหน่วยงานนี้ "
                             "— ไม่อ่านเนื้อหาหน้าของหน่วยงานอื่น")
FRONT_PAGES = 30
SMALL_FILE_PAGES = 60          # ไฟล์ไม่เกินนี้ (เช่น ไฟล์ที่ตัดเฉพาะหน่วยงานแล้ว) อ่านทั้งไฟล์ได้
_TOC_RANGE = re.compile(r"^\s*(?:\(?\d+\)?\.?)?\s*(.+?)\s+(\d{1,4})\s*(?:ถึง|-|–)\s*(\d{1,4})\s*$")
_TOC_START = re.compile(r"^\s*(?:\(?\d+\)?\.?)?\s*(\D+?)[\s…]+(\d{1,4})\s*$")
_PAGE_NO = re.compile(r"(?<![\d,.])(\d{1,4})(?![\d,.])")


_FFFD_AM = re.compile("\ufffd([\u0e48-\u0e4b]?)\u0e32")
#: ชื่อสองหน่วยงานติดกันในบรรทัดเดียว — "กรมการแพทย์ 277 ถึง 326 (4) กรมควบคุมโรค"
_TOC_GLUED = re.compile(r"\s\d{1,4}\s*(?:ถึง|-|–)\s*\d{1,4}\s*\(?\d+\)?\.?\s*")
#: ฟอนต์สารบัญบางเล่มแปลงรูป "บ" เป็น "บั" — ยืนยันจาก "บั" ที่ตามด้วยสระ/วรรณยุกต์+า (เป็นไปไม่ได้ในคำไทย)
_BO_QUIRK = re.compile("\u0e1a\u0e31(?:[\u0e31-\u0e3a\u0e32\u0e33]|[\u0e48-\u0e4b]\u0e32)")


def toc_clean(name: str, bo_quirk: bool = False) -> str:
    """ซ่อมชื่อในสารบัญที่ตารางแปลงอักษรของฟอนต์ผิด — ใช้ทั้งแสดงผลและค้นหา

    "�า" / "ำา" → "ำ" (ไม่มีในคำไทย) · "บั" → "บ" เฉพาะเล่มที่ยืนยันแล้วว่าฟอนต์เพี้ยนแบบนี้ ·
    ชื่อสองหน่วยงานที่ติดกันในบรรทัดเดียว = ใช้ชื่อหลัง
    """
    t = _FFFD_AM.sub(lambda m: m.group(1) + "\u0e33", clean(name)).replace("\u0e33\u0e32", "\u0e33")
    if bo_quirk:
        t = t.replace("\u0e1a\u0e31", "\u0e1a")
    t = _TOC_GLUED.split(t)[-1]
    return t.strip(" .…")


def front_lines(path, pages: list[int]) -> list[str]:
    """ข้อความหน้าต้นเล่มเป็นบรรทัด — จัดคำจากอักขระตามลำดับ (pdfbook-0.2.0) ไม่ใช้ข้อความเร็วที่สระเพี้ยน"""
    from . import layout, reader
    return [chr(10).join(r.text for r in layout.rows_of_page(pt)) for pt in reader.page_words(path, pages)]


def toc_entries(front: list[str]) -> list[tuple[str, int, int | None, int]]:
    """(ชื่อ, หน้าเริ่มที่พิมพ์, หน้าจบที่พิมพ์หรือ None, หน้า PDF ของสารบัญ) — ชื่อผ่าน :func:`toc_clean` แล้ว"""
    raw = _toc_entries_raw(front)
    quirk = any(_BO_QUIRK.search(clean(e[0])) for e in raw)
    return [(toc_clean(n, quirk), s, e, p) for n, s, e, p in raw]


def _toc_entries_raw(front: list[str]) -> list[tuple[str, int, int | None, int]]:
    ranged, starts = [], []
    for idx, t in enumerate(front, 1):
        for line in (t or "").splitlines():
            s = clean(line)
            if re.search(r"\d[.,]\d", s):
                continue                      # บรรทัดที่มีตัวเลขทศนิยม/จุลภาค = ตารางเงิน ไม่ใช่สารบัญ
            m = _TOC_RANGE.match(s)
            if m and int(m.group(2)) <= int(m.group(3)):
                ranged.append((m.group(1), int(m.group(2)), int(m.group(3)), idx))
                continue
            m = _TOC_START.match(s)
            if m and len(squash(m.group(1))) >= 6:
                starts.append((m.group(1), int(m.group(2)), None, idx))
    # สารบัญแบบ "เริ่ม ถึง จบ" มีก่อน — ใช้แบบมีแต่หน้าเริ่มเมื่อไม่มีแบบช่วงเลย
    return ranged or starts


def _printed_no(margin: str) -> int | None:
    nums = [int(x) for x in _PAGE_NO.findall(clean(margin))]
    return nums[-1] if nums else None


def find_by_toc(path, agency: str, front: list[str] | None = None) -> tuple[Scope, list[int]]:
    """ช่วงหน้าของ ``agency`` จากสารบัญ — คืน (Scope, หน้าที่อ่านเนื้อหาจริง)

    1. อ่านเนื้อหาเฉพาะ ``FRONT_PAGES`` หน้าแรก (ปก/สารบัญ) · 2. หาชื่อหน่วยงานในสารบัญ → หน้าที่พิมพ์ ·
    3. อ่าน **เฉพาะแถบขอบหน้า** ของหน้าทดลองเพื่อหาเลขหน้าที่พิมพ์ → offset · 4. ยืนยันหน้าเริ่มด้วยเนื้อหา
    (ชื่อหน่วยงาน + วิสัยทัศน์) — ไม่ผ่าน = ``ScopeError`` (ไม่ถอยไปอ่านทั้งเล่ม)
    """
    from . import reader
    if not agency:
        raise ScopeError("เล่มรวมต้องระบุชื่อหน่วยงาน")
    n = reader.page_count(path)
    front_no = list(range(1, min(FRONT_PAGES, n) + 1))
    if front is None:
        front = front_lines(path, front_no)     # ``front`` ส่งมาได้ (ข้อความหน้าต้นเล่มที่อ่านไว้แล้ว · ผลเหมือนกัน)
    key, sk = squash(agency), skeleton(agency)
    entries = toc_entries(front)
    # ชื่อตรงทั้งชื่อก่อน — "กรมการแพทย์" ต้องไม่ไปได้ "กรมการแพทย์แผนไทยและการแพทย์ทางเลือก"
    hits = ([e for e in entries if squash(e[0]) == key] or [e for e in entries if skeleton(e[0]) == sk]
            or [e for e in entries if key in squash(e[0])] or [e for e in entries if sk in skeleton(e[0])])
    if not hits:
        raise ScopeError("ไม่พบชื่อหน่วยงานนี้ในสารบัญต้นเล่ม — กรุณากำหนดช่วงหน้าเอง")
    name, p_start, p_end, _toc_page = hits[0]
    if p_end is None:
        later = sorted(e[1] for e in entries if e[1] > p_start)
        if not later:
            raise ScopeError("สารบัญไม่บอกหน้าจบของหน่วยงานนี้ — กรุณากำหนดช่วงหน้าเอง")
        p_end = later[0] - 1
    # offset จากเลขหน้าที่พิมพ์ที่ขอบหน้า (ลองหน้า PDF = เลขที่พิมพ์ ± เล็กน้อย)
    offset = None
    for probe in [p_start + k for k in (0, 3, 7, 10, 14, 17, 20, 25, 30, -5, -10)]:
        if 1 <= probe <= n:
            q = _printed_no(reader.margin_texts(path, [probe]).get(probe, ""))
            if q is not None:
                offset = probe - q
                break
    if offset is None:
        raise ScopeError("อ่านเลขหน้าที่พิมพ์ไม่ได้ — กรุณากำหนดช่วงหน้าเอง")
    first, last = p_start + offset, p_end + offset
    if not (1 <= first <= last <= n):
        raise ScopeError("ช่วงหน้าที่คำนวณจากสารบัญอยู่นอกไฟล์ — กรุณากำหนดช่วงหน้าเอง")
    head = reader.page_texts(path, [first])[first - 1]
    if not ((key in squash(head) or sk in skeleton(head)) and skeleton("วิสัยทัศน์") in skeleton(head)):
        raise ScopeError("หน้าเริ่มที่คำนวณจากสารบัญไม่มีชื่อหน่วยงานและหัวข้อวิสัยทัศน์ — กรุณากำหนดช่วงหน้าเอง")
    return Scope(first, last, METHOD_TOC, agency), front_no + list(range(first, last + 1))
