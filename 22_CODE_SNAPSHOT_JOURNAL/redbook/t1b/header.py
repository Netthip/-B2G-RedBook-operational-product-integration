# -*- coding: utf-8 -*-
"""T1B — การหาแถวหัวตารางและการจับคู่คอลัมน์ปี

🔴 **ห้าม hard-code เลขแถวหัวตาราง** (คำสั่ง Gift ข้อ 2)
ในไฟล์จริง แถวหัวตารางของบทบาทเดียวกันอยู่คนละแถว —
ระดับกระทรวงอยู่แถว 3 · ระดับหน่วยงานอยู่แถว 5

🔴 **ห้ามจับคู่คอลัมน์ด้วยตัวอักษรคอลัมน์** — silent failure #1
คอลัมน์ ``C`` ของไฟล์ปี 2569 คือ ``ปี 2568`` แต่คอลัมน์ ``C`` ของไฟล์ปี 2570 คือ ``ปี 2569``
การเทียบตามตำแหน่งจะเทียบคนละปีงบประมาณโดยไม่มีสัญญาณผิดพลาดใด ๆ
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .categories import CATEGORY_UNRESOLVED, is_known_category, resolve_budget_category
from .normalize import normalize_label

#: ป้ายปีในหัวตาราง เช่น "ปี 2568" — รองรับช่องว่างแปรผัน
_YEAR_LABEL = re.compile(r"^ปี\s*(\d{4})$")

#: คำที่ยืนยันว่าเป็นแถวหัวตาราง
_HEADER_MARKERS = ("หน่วยนับ", "ตัวชี้วัด")

#: จำนวนแถวสูงสุดที่ยอมค้นหาหัวตาราง — หัวตารางจริงพบที่แถว 2–5
MAX_HEADER_SCAN_ROWS = 12


def parse_year_label(value: object) -> int | None:
    """แปลงป้าย ``"ปี 2568"`` เป็น ``2568`` — คืน ``None`` ถ้าไม่ใช่ป้ายปี"""
    m = _YEAR_LABEL.match(normalize_label(value))
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- ป้ายช่วงเวลา (G5 · #14)

PERIOD_YEAR = "YEAR"              # ปีเดี่ยว — เข้าแกน FISCAL_YEAR เดิม
PERIOD_OPEN_START = "OPEN_START"  # เริ่มต้น - ปี 2569
PERIOD_OPEN_END = "OPEN_END"      # ปี 2573 - จบ
PERIOD_RANGE = "RANGE"            # ปี 2571 - 2573

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_DASHES = re.compile(r"\s*[-‐‑‒–—―−]\s*")
_SPACES = re.compile(r"\s+")
_Y = r"(?:ปี\s*|พ\.ศ\.\s*)?(2[56]\d\d)"
_PERIOD_PATTERNS = (
    (PERIOD_YEAR, re.compile(r"^(?:ปี\s*|พ\.ศ\.\s*)(2[56]\d\d)$")),
    (PERIOD_YEAR, re.compile(r"^(2[56]\d\d)$")),
    (PERIOD_OPEN_START, re.compile(r"^เริ่มต้น(?:-|\s*ถึง\s*)" + _Y + r"$")),
    (PERIOD_OPEN_END, re.compile(r"^" + _Y + r"(?:-|\s*ถึง\s*)จบ$")),
    (PERIOD_OPEN_END, re.compile(r"^" + _Y + r"\s*เป็นต้นไป$")),
    (PERIOD_RANGE, re.compile(r"^" + _Y + r"(?:-|\s*ถึง\s*)" + _Y + r"$")),
)


@dataclass(frozen=True)
class PeriodLabel:
    """ป้ายหัวคอลัมน์ที่เป็นช่วงเวลา — เก็บป้ายดิบไว้เสมอ"""

    kind: str
    start_year: int | None
    end_year: int | None
    raw: object
    #: ป้ายหลัง normalization แบบอนุรักษนิยม — **ตัวเดียวที่ใช้จับคู่ช่วงเวลา**
    norm: str


def normalize_period_label(value: object) -> str:
    """normalization แบบอนุรักษนิยม (คำตัดสินกิ๊ฟ 8 ก.ย. 2569 ข้อ 2)

    ตัดช่องว่างหัวท้าย · ยุบช่องว่างซ้ำ · Unicode NFC · ขีดทุกชนิดเป็น ``-``
    (ไม่เหลือช่องว่างรอบขีด) — ``ปี 2573 - จบ`` ≡ ``ปี 2573–จบ``

    🔴 **ไม่แปลงตัวเลขไทย** และไม่แตะส่วนอื่นของป้าย — ป้ายที่ต่างจากนี้
    ถือว่าต่าง และต้องให้คนตัดสิน
    """
    text = unicodedata.normalize("NFC", normalize_label(value))
    text = _DASHES.sub("-", text)
    return _SPACES.sub(" ", text).strip()


def parse_period_label(value: object) -> PeriodLabel | None:
    """แปลงป้ายหัวคอลัมน์เป็นช่วงเวลา — คืน ``None`` ถ้าไม่ใช่ป้ายช่วงเวลา

    รับเฉพาะ **ข้อความ** · เซลล์ตัวเลข (เช่น ``2570`` ที่เป็นค่า) ไม่ใช่ป้าย
    ป้ายที่ต้อง **ไม่** parse: ``ปี`` · ``ปีที่ 3`` · ``2570 บาท``
    """
    if not isinstance(value, str):
        return None
    norm = normalize_period_label(value)
    probe = norm.translate(_THAI_DIGITS)
    for kind, pattern in _PERIOD_PATTERNS:
        m = pattern.match(probe)
        if not m:
            continue
        years = [int(g) for g in m.groups()]
        if kind == PERIOD_YEAR:
            return PeriodLabel(kind, years[0], years[0], value, norm)
        if kind == PERIOD_OPEN_START:
            return PeriodLabel(kind, None, years[0], value, norm)
        if kind == PERIOD_OPEN_END:
            return PeriodLabel(kind, years[0], None, value, norm)
        if years[0] >= years[1]:
            return None               # ช่วงกลับด้าน/ปีเดียวซ้ำ — ไม่เดา
        return PeriodLabel(kind, years[0], years[1], value, norm)
    return None


def resolve_period_columns(header_row: list[object]) -> dict[int, PeriodLabel]:
    """คอลัมน์ที่เป็น **ช่วงเวลา** (ไม่ใช่ปีเดี่ยว) -> ป้าย · ดัชนีคอลัมน์ฐาน 0"""
    out: dict[int, PeriodLabel] = {}
    for idx, cell in enumerate(header_row):
        label = parse_period_label(cell)
        if label is not None and label.kind != PERIOD_YEAR:
            out[idx] = label
    return out


def locate_header_row(rows: list[list[object]]) -> int | None:
    """หาแถวหัวตารางด้วย **ลายเซ็น** ไม่ใช่เลขแถวตายตัว

    ``rows`` คือค่าของเซลล์เรียงตามแถว โดย ``rows[0]`` = แถวที่ 1 ของชีต
    คืน **เลขแถวฐาน 1** ของแถวหัวตาราง หรือ ``None`` เมื่อหาไม่พบ

    ลายเซ็นที่ยอมรับ: แถวที่มีป้ายปีอย่างน้อยหนึ่งช่อง **หรือ** มีคำว่า
    ``หน่วยนับ`` / ``ตัวชี้วัด``
    """
    for offset, row in enumerate(rows[:MAX_HEADER_SCAN_ROWS]):
        has_year = any(parse_year_label(c) is not None for c in row)
        has_marker = any(normalize_label(c) in _HEADER_MARKERS for c in row)
        if has_year or has_marker:
            return offset + 1
    return None


def resolve_year_columns(header_row: list[object]) -> dict[int, int]:
    """จับคู่ **ปีงบประมาณ -> ดัชนีคอลัมน์ฐาน 0** จากป้ายในแถวหัวตาราง

    >>> resolve_year_columns(["ตัวชี้วัด", "หน่วยนับ", "ปี 2568", "ปี 2569"])
    {2568: 2, 2569: 3}

    คอลัมน์ที่ไม่ใช่ป้ายปีจะไม่ปรากฏในผล — ผู้เรียกต้องไม่สมมติว่าคอลัมน์ใด
    เป็นปีจากตำแหน่ง
    """
    out: dict[int, int] = {}
    for idx, cell in enumerate(header_row):
        year = parse_year_label(cell)
        if year is not None and year not in out:
            out[year] = idx
    return out


#: จำนวนแถวหัวตารางสูงสุดที่ยอมรวมเข้าด้วยกัน
MAX_HEADER_SPAN = 3


def resolve_year_columns_merged(
    rows: list[list[object]], header_row: int, max_span: int = MAX_HEADER_SPAN
) -> dict[int, int]:
    """รวมป้ายปีจากหัวตาราง **หลายแถวติดกัน**

    🔴 หัวตารางของบทบาท ``8.`` กระจายอยู่ **สองแถว** — พบจริงที่
    ``XL_FY2569_draft-bill_21011_HSRI.xlsx`` ชีต ``Sheet8``
    โดย ``B3 = "ปี 2567"`` แต่ ``C4..G4 = "ปี 2568".."ปี 2572"``

    ถ้าอ่านแถวเดียวจะได้ปีเดียว แล้ว **ค่าอีกห้าปีจะหายเงียบ**
    และค่าที่เหลือจะถูกติดป้ายปีผิดทั้งหมด

    ``header_row`` เป็นเลขแถวฐาน 1 · คืน ``{ปีงบประมาณ: ดัชนีคอลัมน์ฐาน 0}``
    ปีที่พบก่อนมีสิทธิ์เหนือกว่า (แถวบนชนะแถวล่าง) เพื่อไม่ให้ทับกันเอง
    """
    merged: dict[int, int] = {}
    for offset in range(max_span):
        index = header_row - 1 + offset
        if index >= len(rows):
            break
        row = rows[index]
        if offset > 0 and not any(parse_year_label(c) is not None for c in row):
            break
        for year, col in resolve_year_columns(row).items():
            merged.setdefault(year, col)
    return merged


def align_years(
    baseline_header: list[object], current_header: list[object]
) -> dict[int, tuple[int, int]]:
    """จับคู่คอลัมน์ของสองไฟล์ **ตามปี** ไม่ใช่ตามตำแหน่ง

    คืน ``{ปีงบประมาณ: (คอลัมน์ในไฟล์ baseline, คอลัมน์ในไฟล์ current)}``
    เฉพาะปีที่ **มีอยู่ทั้งสองไฟล์** — ปีที่มีข้างเดียวถูกตัดออกจากการเทียบ
    และต้องรายงานแยกโดยผู้เรียก

    ตัวอย่างจริง: ไฟล์ปี 2569 มีป้าย 2568–2572 · ไฟล์ปี 2570 มีป้าย 2569–2573
    ⇒ ปีที่เทียบได้จริงมีเพียง 2569–2572
    """
    base = resolve_year_columns(baseline_header)
    curr = resolve_year_columns(current_header)
    return {y: (base[y], curr[y]) for y in sorted(base.keys() & curr.keys())}


def years_only_in(
    header_a: list[object], header_b: list[object]
) -> list[int]:
    """ปีที่ปรากฏใน ``header_a`` แต่ไม่มีใน ``header_b`` — ต้องรายงาน ห้ามเทียบ"""
    return sorted(resolve_year_columns(header_a).keys() - resolve_year_columns(header_b).keys())


# ---------------------------------------------------------------- ตารางหลายชุดต่อชีต

#: คำที่ระบุคอลัมน์หน่วยนับ
UNIT_HEADER_MARKER = "หน่วยนับ"

#: จำนวนป้ายปีขั้นต่ำที่ถือว่าเป็นแถวหัวตารางของตารางรายปี
MIN_YEAR_LABELS = 2


@dataclass(frozen=True)
class YearTable:
    """ตารางรายปีหนึ่งชุดในชีต — ชีตหนึ่งมีได้หลายชุด

    พบจริงในชีตบทบาท ``7.x`` ที่มีทั้งตารางจำแนกตาม **งบรายจ่าย**
    และตารางจำแนกตาม **ปีงบประมาณ** อยู่ในชีตเดียวกัน
    """

    header_row: int                  # แถวที่มีป้ายปี (ฐาน 1)
    block_start: int                 # แถวแรกของ **บล็อกหัวตาราง** (ฐาน 1)
    first_data_row: int              # แถวข้อมูลแรก (ฐาน 1)
    last_data_row: int               # แถวข้อมูลสุดท้าย (ฐาน 1 · รวมแถวนี้)
    year_columns: dict[int, int]     # ปี -> ดัชนีคอลัมน์ฐาน 0
    unit_column: int | None          # คอลัมน์หน่วยนับรายแถว ถ้ามี
    unit_declaration: object         # ข้อความประกาศหน่วยระดับตาราง ถ้ามี
    #: G5 (#14) — คอลัมน์ที่หัวเป็น **ช่วงเวลา** (เปิดหัว · เปิดท้าย · ช่วงปี)
    #: ดัชนีคอลัมน์ฐาน 0 -> ป้าย · 🔴 ไม่เข้าแกนปีเดิม
    period_columns: dict = field(default_factory=dict)
    #: G6 (#14) — ข้อความหัวคอลัมน์ดิบของบล็อกหัวตาราง (ฐาน 0 -> ข้อความ)
    #: ใช้ชี้ให้คนเห็นว่าคอลัมน์ที่อ่านไม่ออกมีหัวว่าอะไร
    header_texts: dict = field(default_factory=dict)


def _year_header_rows(rows: list[list[object]]) -> list[int]:
    """แถวที่มีป้ายปีตั้งแต่ ``MIN_YEAR_LABELS`` ป้ายขึ้นไป (ฐาน 1)"""
    out = []
    for index, row in enumerate(rows):
        n = sum(1 for c in row if parse_year_label(c) is not None)
        if n >= MIN_YEAR_LABELS:
            out.append(index + 1)
    return out


def _find_unit_column(rows: list[list[object]], header_row: int) -> int | None:
    """หาคอลัมน์หน่วยนับจากแถวหัวตารางหรือแถวเหนือขึ้นไปหนึ่งแถว

    🔴 คอลัมน์หน่วยนับ **ไม่คงที่** — บทบาท ``5.`` ใช้คอลัมน์ ``B``
    แต่บทบาท ``7.x`` ใช้คอลัมน์ ``F`` ⇒ ห้าม hard-code
    """
    for candidate in (header_row - 1, header_row - 2):
        if candidate < 0 or candidate >= len(rows):
            continue
        for col, cell in enumerate(rows[candidate]):
            if normalize_label(cell) == UNIT_HEADER_MARKER:
                return col
    return None


#: รูปแบบการประกาศหน่วยระดับตาราง เช่น "หน่วย : ล้านบาท (ทศนิยม 4 ตำแหน่ง)"
_UNIT_DECLARATION = re.compile(r"หน่วย\s*[:：]")


def _find_unit_declaration(rows: list[list[object]], header_row: int) -> object:
    """หาข้อความประกาศหน่วยที่อยู่เหนือแถวหัวตารางที่ใกล้ที่สุด

    🔴 ต้องใช้รูปแบบ ``หน่วย :`` เท่านั้น — จับคำว่า ``หน่วย`` ลอย ๆ จะไปโดน
    ``"เป้าหมายการให้บริการหน่วยงาน"`` แล้วได้ข้อความที่ไม่ใช่หน่วยนับ
    """
    for index in range(header_row - 2, -1, -1):
        for cell in rows[index]:
            if isinstance(cell, str) and _UNIT_DECLARATION.search(cell):
                return cell
    return None


def _is_caption_row(row: list[object]) -> bool:
    """แถวนี้เป็น **แถวหัวคอลัมน์** หรือไม่ — ข้อความล้วน ไม่มีค่าตัวเลข

    ใช้หลักฐานเชิงโครงสร้างเท่านั้น: มีข้อความอย่างน้อยหนึ่งช่องในเขตค่า
    และ **ไม่มีตัวเลขเลย** ในทั้งแถว · แถวข้อมูลของตารางเหล่านี้มีตัวเลขเสมอ

    🔴 ห้าม hard-code ข้อความหัวคอลัมน์ใด ๆ (คำสั่ง Bo · 3 ก.ย. 2569)
    """
    region = row[CATEGORY_LABEL_COLUMN + 1:]
    if any(isinstance(c, (int, float)) and not isinstance(c, bool) for c in row):
        return False
    return any(isinstance(c, str) and normalize_label(c) for c in region)


def _header_block_start(rows: list[list[object]], header_row: int,
                        floor_row: int = 0) -> int:
    """แถวแรกของ **บล็อกหัวตาราง** ที่ลงท้ายด้วย ``header_row``

    ไล่ขึ้นจากแถวป้ายปี ผ่านแถวหัวคอลัมน์ที่ต่อเนื่องกัน หยุดเมื่อเจอ
    แถวที่มีตัวเลข (แถวข้อมูล) · แถวว่าง (ตัวคั่น) · หรือถึง ``floor_row``

    🔴 blocker #4 (Bo · 3 ก.ย. 2569): เดิมตัดขอบเขตที่ **แถวป้ายปี** อย่างเดียว
    ทำให้แถวหัวคอลัมน์ที่อยู่เหนือมันตกเป็น **แถวข้อมูลของตารางก่อนหน้า**
    ⇒ ข้อความหัวคอลัมน์ถูกอ่านเป็นค่าของหมวดงบรายจ่าย เกิดรายการปลอม

    หลักฐานว่าแถวนั้นเป็นของบล็อกหัวจริง: ``_find_unit_column()`` มองหา
    คอลัมน์หน่วยนับที่ ``header_row - 1`` และ ``header_row - 2`` อยู่แล้ว
    ⇒ ตัวตรวจสองที่ในโมดูลนี้เคยขัดแย้งกันเอง รอบนี้ใช้กติกาเดียวกัน
    """
    start = header_row
    index = header_row - 1                    # ฐาน 0 ของแถวเหนือขึ้นไป
    while index - 1 >= floor_row and index - 1 < len(rows):
        above = rows[index - 1]
        if not _is_caption_row(above):
            break
        start = index
        index -= 1
    return start


def find_year_tables(rows: list[list[object]]) -> list[YearTable]:
    """หาตารางรายปี **ทุกชุด** ในชีตเดียว

    รวมแถวหัวตารางที่ติดกันเข้าด้วยกัน (บทบาท ``8.`` กระจายป้ายปีสองแถว)
    และตัดขอบเขตข้อมูลของแต่ละตารางที่แถวหัวตารางของตารางถัดไป
    """
    header_rows = _year_header_rows(rows)
    if not header_rows:
        return []

    # รวมแถวหัวตารางที่ติดกัน — ถือแถวแรกของกลุ่มเป็นจุดเริ่ม
    groups: list[list[int]] = []
    for row in header_rows:
        if groups and row == groups[-1][-1] + 1:
            groups[-1].append(row)
        else:
            groups.append([row])

    tables: list[YearTable] = []
    prev_end = 0
    for gi, group in enumerate(groups):
        start, end = group[0], group[-1]
        # 🔴 แถวเหนือขึ้นไปอาจมีป้ายปี **เพียงป้ายเดียว** จึงไม่ถูกนับเป็นแถวหัวตาราง
        # (บทบาท 8. มี B3 = "ปี 2567" อยู่เหนือแถวที่มีป้ายปีห้าป้าย)
        # ถ้าไม่รวมเข้ามา ค่าของปีนั้นจะหายเงียบทั้งคอลัมน์
        above = start - 1
        if above >= 1 and any(parse_year_label(c) is not None for c in rows[above - 1]):
            if not (gi > 0 and above <= groups[gi - 1][-1]):
                start = above
                group = [above] + group
        merged: dict[int, int] = {}
        for row in group:
            for year, col in resolve_year_columns(rows[row - 1]).items():
                merged.setdefault(year, col)
        year_cols = set(merged.values())
        periods: dict[int, PeriodLabel] = {}
        for row in group:
            for col, label in resolve_period_columns(rows[row - 1]).items():
                if col not in year_cols:
                    periods.setdefault(col, label)
        block_start = _header_block_start(rows, start, floor_row=prev_end)
        texts: dict[int, str] = {}
        for row in range(block_start, end + 1):
            for col, cell in enumerate(rows[row - 1]):
                t = normalize_label(cell) if isinstance(cell, str) else ""
                if t:
                    texts[col] = f"{texts[col]} / {t}" if col in texts else t
        first_data = end + 1
        if gi + 1 < len(groups):
            nxt = _header_block_start(rows, groups[gi + 1][0], floor_row=end)
            last_data = nxt - 1
        else:
            last_data = len(rows)
        prev_end = end
        if first_data > last_data:
            continue
        tables.append(YearTable(
            header_row=start,
            block_start=block_start,
            first_data_row=first_data,
            last_data_row=last_data,
            year_columns=merged,
            unit_column=_find_unit_column(rows, start),
            unit_declaration=_find_unit_declaration(rows, start),
            period_columns=periods,
            header_texts=texts,
        ))
    return tables


# ------------------------------------------------- ตารางจำแนกตามงบรายจ่าย

#: คอลัมน์ป้ายรายการของตารางจำแนกตามงบรายจ่าย — ขอบซ้ายของ **เขตค่า**
#:
#: ตรงกับ ``MAIN_LABEL_COLUMN`` ที่ adapter ใช้อ่านป้ายแถวของตารางชนิดนี้
#: จึงไม่ใช่ข้อสมมติใหม่ แต่เป็นข้อสมมติเดิมที่เขียนให้ชัดขึ้น
CATEGORY_LABEL_COLUMN = 0

#: หัวคอลัมน์หมวดที่รู้จักขั้นต่ำในเขตค่า — **หนึ่งหมวดก็พอ**
#:
#: 🔴 BO REVIEW (2 ก.ย.): เดิมเป็น ``2`` ซึ่งขัดกับ contract ของ
#: ``_category_columns()`` ที่รับ ``known >= 1`` ⇒ ตารางที่มีหมวดที่รู้จัก
#: เพียงหมวดเดียวขนาบด้วยหมวดที่ไม่รู้จัก **ถูกตัดทิ้งทั้งตาราง** ก่อนถึงชั้นนั้น
#: และค่าทุกคอลัมน์หายเงียบ
MIN_KNOWN_CATEGORIES = 1

#: จำนวนคอลัมน์ที่มีหัวข้อความขั้นต่ำในเขตค่า ที่ถือว่าแถวนั้นเป็น **แถวหัวตาราง**
#:
#: เป็นตัวกันความสับสนแทนการนับหมวดที่รู้จัก — แถวข้อมูลที่ป้ายบังเอิญเป็น
#: ``รวม`` มีคอลัมน์ข้อความในเขตค่าไม่ถึงเกณฑ์ จึงไม่ถูกจับเป็นหัวตาราง
#: แฟ้มจริงทั้ง 6 แฟ้มมีคอลัมน์ข้อความในเขตค่า **5-6 คอลัมน์** ทุกหัวตาราง
MIN_CATEGORY_HEADER_TEXTS = 2


@dataclass(frozen=True)
class CategoryColumn:
    """หนึ่งคอลัมน์ค่าในตารางจำแนกตามงบรายจ่าย

    🔴 เก็บ **ทั้ง** canonical code และข้อความหัวคอลัมน์ดิบ
    คอลัมน์ที่ resolve ไม่ได้ยังต้องอยู่ในรายการนี้ (canonical = ``UNRESOLVED``)
    เพื่อไม่ให้ค่าของคอลัมน์นั้นหายเงียบ
    """

    index: int
    canonical: str
    raw_header: object


@dataclass(frozen=True)
class CategoryTable:
    """ตารางที่จำแนกตาม **ประเภทงบรายจ่าย** ไม่ใช่ปีงบประมาณ

    พบจริงในชีตบทบาท ``6.`` และชีตแผนงาน/โครงการ ``7.x``
    โดยหัวตารางวางหมวดงบรายจ่ายเป็น **คอลัมน์**
    """

    header_row: int
    first_data_row: int
    last_data_row: int
    columns: tuple[CategoryColumn, ...]
    unit_declaration: object
    #: ขอบเขตแข่งกับตารางถัดไปจนไม่เหลือแถวข้อมูล — 🔴 ต้องให้มนุษย์ตัดสิน
    #: ห้ามข้ามเงียบ (blocker #4 · Bo · 3 ก.ย. 2569)
    boundary_ambiguous: bool = False

    @property
    def unresolved_columns(self) -> tuple[CategoryColumn, ...]:
        return tuple(c for c in self.columns if c.canonical == CATEGORY_UNRESOLVED)


def _is_category_header_row(row: list[object]) -> bool:
    """แถวนี้เป็น **แถวหัว** ของตารางจำแนกตามงบรายจ่ายหรือไม่

    พิจารณาเฉพาะ **เขตค่า** (คอลัมน์ขวาของคอลัมน์ป้าย) เพราะคอลัมน์ป้ายเก็บ
    ชื่อแถว ไม่ใช่หัวคอลัมน์ — แถวข้อมูลที่ป้ายเป็น ``รวม`` จึงไม่ถูกเข้าใจผิด

    🔴 **ห้ามใช้ 'ไม่มีตัวเลขในแถว' เป็นเงื่อนไข** — ตรวจแฟ้มจริงแล้วพบว่า
    หัวตาราง 2 ใน 19 แถวมีตัวเลขปนอยู่ในเขตค่า (``Sheet7.2`` และ
    ``Sheet7.3.1`` ของ FY2570 · 21016) การใช้เงื่อนไขนั้นจะตัดตารางจริงทิ้ง
    """
    region = row[CATEGORY_LABEL_COLUMN + 1:]
    known = {
        normalize_label(c) for c in region
        if isinstance(c, str) and is_known_category(c)
    }
    if len(known) < MIN_KNOWN_CATEGORIES:
        return False
    texts = [c for c in region if isinstance(c, str) and normalize_label(c)]
    return len(texts) >= MIN_CATEGORY_HEADER_TEXTS


def _category_header_rows(rows: list[list[object]]) -> list[int]:
    """แถวหัวของตารางจำแนกตามงบรายจ่ายทั้งหมดในชีต (ฐาน 1)

    แถวที่เป็นหัวตาราง **รายปี** อยู่แล้ว ไม่ใช่หัวตารางหมวด — ตัดออกตรงนี้
    เพื่อให้ contract เดียวกันไม่ว่าจะเรียกผ่าน adapter หรือเรียกตรง
    """
    year_rows = set(_year_header_rows(rows))
    return [
        index + 1 for index, row in enumerate(rows)
        if index + 1 not in year_rows and _is_category_header_row(row)
    ]


def _category_columns(
    header: list[object], unit_column: int | None = None
) -> tuple[CategoryColumn, ...]:
    """เก็บ **ทุกคอลัมน์ค่าในเขตตาราง** ไม่ใช่เฉพาะคอลัมน์ที่ resolve ได้

    🔴 BO REVIEW (1 ก.ย.): เดิมเก็บเฉพาะคอลัมน์ที่ resolve สำเร็จ ⇒ คอลัมน์หมวดใหม่
    หรือหมวดที่สะกดต่างไป **ถูกข้ามโดยไม่สร้าง HUMAN REVIEW** และค่าหายเงียบ

    🔴 BO REVIEW (2 ก.ย.): การแก้รอบแรกยังเริ่มนับที่ **หมวดที่รู้จักคอลัมน์แรก**
    ⇒ หัวคอลัมน์ที่ไม่รู้จักซึ่งวางอยู่ **ก่อน** หมวดที่รู้จักตัวแรกยังหายเงียบอยู่
    รอบนี้จึงยึด **ขอบเขตตาราง** แทน: เขตค่าคือทุกคอลัมน์ที่อยู่ขวาของคอลัมน์
    ป้ายรายการ โดยข้ามคอลัมน์โครงสร้าง (หน่วยนับ) ซึ่งไม่ใช่คอลัมน์ค่า

    ยังต้องมีหมวดที่รู้จักอย่างน้อยหนึ่งคอลัมน์จึงจะถือว่าเป็นตารางชนิดนี้ —
    มิฉะนั้นแถวหัวใด ๆ ที่มีข้อความจะกลายเป็นตารางหมวดไปหมด
    """
    if not any(isinstance(c, str) and is_known_category(c) for c in header):
        return ()

    seen: set[str] = set()
    out: list[CategoryColumn] = []
    for index in range(CATEGORY_LABEL_COLUMN + 1, len(header)):
        if index == unit_column:
            continue                      # คอลัมน์โครงสร้าง ไม่ใช่คอลัมน์ค่า
        cell = header[index]
        if not isinstance(cell, str) or not normalize_label(cell):
            continue
        if normalize_label(cell) == UNIT_HEADER_MARKER:
            continue
        canonical = resolve_budget_category(cell)
        if canonical != CATEGORY_UNRESOLVED and canonical in seen:
            continue
        if canonical != CATEGORY_UNRESOLVED:
            seen.add(canonical)
        out.append(CategoryColumn(index=index, canonical=canonical, raw_header=cell))
    return tuple(out)


def find_category_tables(
    rows: list[list[object]], exclude_rows: set[int] | None = None
) -> list[CategoryTable]:
    """หาตารางจำแนกตามงบรายจ่ายทุกชุดในชีต

    ``exclude_rows`` = แถวที่ตารางรายปีจองไว้แล้ว — กันการนับซ้ำ

    🔴 ต้องเป็นหมวดที่วางเรียง **ตามแนวนอน** ตั้งแต่สองหมวดขึ้นไป
    ชีตบทบาท ``7.1`` มีหมวดงบรายจ่ายเป็น **แถว** (``- งบบุคลากร`` ฯลฯ)
    ซึ่งไม่ใช่ตารางชนิดนี้ และต้องไม่ถูกจับผิด
    """
    exclude = exclude_rows or set()
    header_rows = [r for r in _category_header_rows(rows) if r not in exclude]
    if not header_rows:
        return []

    year_rows = set(_year_header_rows(rows))
    tables: list[CategoryTable] = []
    for position, header in enumerate(header_rows):
        columns = _category_columns(
            rows[header - 1], unit_column=_find_unit_column(rows, header)
        )
        # 🔴 blocker #4 — ขอบเขตต้องหยุดก่อน **บล็อกหัว** ของตารางถัดไป
        # ไม่ใช่ก่อนแถวป้ายปี มิฉะนั้นแถวหัวคอลัมน์จะกลายเป็นแถวข้อมูลของตารางนี้
        limits = [
            _header_block_start(rows, r, floor_row=header)
            for r in header_rows[position + 1:] if r > header
        ]
        limits += [
            _header_block_start(rows, r, floor_row=header)
            for r in sorted(year_rows) if r > header
        ]
        last = (min(limits) - 1) if limits else len(rows)
        if not columns:
            continue          # ไม่ใช่ตารางชนิดนี้ตั้งแต่ต้น
        declaration = _find_unit_declaration(rows, header)
        if header + 1 > last:
            # 🔴 ขอบเขตแข่งกับตารางถัดไปจนไม่เหลือแถวข้อมูล
            # เดิม ``continue`` เงียบ ⇒ ทั้งตารางหายโดยไม่มีร่องรอย
            tables.append(CategoryTable(
                header_row=header, first_data_row=header + 1,
                last_data_row=header, columns=columns,
                unit_declaration=declaration, boundary_ambiguous=True,
            ))
            continue
        tables.append(CategoryTable(
            header_row=header,
            first_data_row=header + 1,
            last_data_row=last,
            columns=columns,
            unit_declaration=declaration,
        ))
    return tables
