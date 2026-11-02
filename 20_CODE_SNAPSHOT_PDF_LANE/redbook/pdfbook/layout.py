# -*- coding: utf-8 -*-
"""จัดคำบนหน้า PDF เป็น "แถว" (ป้าย + ช่องตัวเลข) และหาคอลัมน์ของตารางจากบรรทัดหัวตาราง

* ช่องตัวเลข = คำที่อยู่ **ท้ายบรรทัด** ต่อกันเป็นตัวเลข/ขีด/หน่วย ("บาท") — คำตัวเลขที่อยู่กลางป้าย
  (เช่น "ปี 2570 ตั้งงบประมาณ") ยังเป็นส่วนของป้าย
* ``-`` เดี่ยว = ช่องว่าง · ``-`` ชิดตัวเลข (ห่างไม่เกิน ``NEG_GAP_PT``) = ค่าลบ (เล่มจริงพิมพ์ ``- 8.4496``)
* คอลัมน์ = ช่วงแกน x ของคำหัวตาราง · ตัวเลขเข้าคอลัมน์ที่ช่วงครอบจุดกึ่งกลาง
  ไม่ครอบ = คอลัมน์ที่ใกล้ที่สุดในระยะ ``NEAREST_PT`` · ไกลกว่านั้น = **ไม่เข้าคอลัมน์** (รายงานใน coverage)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from . import profile as P
from .text import DASH_TOKENS, clean, is_number, parse_amount, skeleton, squash

NEG_GAP_PT = 6.0
#: ช่องว่างระหว่างคำที่ถือว่าเป็นคำเดียวกัน — pdfplumber แตกคำไทยกลางคำ (ช่องว่าง ≤ 0 pt)
#: ส่วนช่องว่างจริงในเล่มกว้างราว 2.7 pt
JOIN_GAP_PT = 1.5
_NUM_UNIT = re.compile(r"^(-?\d[\d,]*(?:\.\d+)?)(ล้านบาท|บาท)$")
COL_PAD_PT = 22.0
TEXT_COL_PAD_PT = 8.0     # คอลัมน์ข้อความ (หน่วยนับ) แคบกว่า — กันคำท้ายชื่อตัวชี้วัดหลุดเข้ามา
NEAREST_PT = 60.0
UNIT_WORDS = {"บาท", "ล้านบาท"}


@dataclass(frozen=True)
class Cell:
    raw: str
    value: object          # Decimal | None (None = ขีด/ว่าง)
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass(frozen=True)
class Row:
    page: int
    text: str
    label: str
    cells: tuple
    words: tuple
    x0: float
    y0: float
    x1: float
    y1: float
    label_x0: float
    unit_word: str = ""

    @property
    def bbox(self):
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass(frozen=True)
class Column:
    name: str              # หมวดงบ / ประเภทรายจ่าย / "2570" / "รวม" / "ตัวชี้วัด" / "หน่วยนับ"
    x0: float
    x1: float
    kind: str = "num"      # num | text

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2


def rows_of_page(pt) -> list[Row]:
    """แถวทั้งหมดของหน้า (``PageText``) ตามลำดับบนลงล่าง"""
    by_line: dict[int, list] = {}
    for w in pt.words:
        by_line.setdefault(w.line, []).append(w)
    out: list[Row] = []
    for _ln, ws in sorted(by_line.items(), key=lambda kv: min(w.y0 for w in kv[1])):
        ws = sorted(ws, key=lambda w: w.x0)
        out.append(_row(pt.page, ws))
    return out


def _join(ws) -> str:
    """ต่อคำตามระยะห่างจริง — ชิดกัน = คำเดียวกัน (ไม่เติมช่องว่าง)"""
    if not ws:
        return ""
    out = ws[0].text
    for prev, w in zip(ws, ws[1:]):
        out += ("" if (w.x0 - prev.x1) < JOIN_GAP_PT else " ") + w.text
    return out


def _split_num_unit(ws: list) -> list:
    """คำที่ตัวเลขติดหน่วย ("60,290,000บาท") แยกเป็นสองคำ"""
    out = []
    for w in ws:
        m = _NUM_UNIT.match(clean(w.text))
        if m:
            frac = len(m.group(1)) / max(len(clean(w.text)), 1)
            cut = w.x0 + (w.x1 - w.x0) * frac
            out.append(replace(w, text=m.group(1), x1=cut))
            out.append(replace(w, text=m.group(2), x0=cut + JOIN_GAP_PT + 0.1))
        else:
            out.append(w)
    return out


def _row(page: int, ws: list) -> Row:
    ws = _split_num_unit(ws)
    # หา "หางตัวเลข" จากขวาไปซ้าย
    i = len(ws)
    unit_word = ""
    seen_num = False
    while i > 0:
        t = clean(ws[i - 1].text)
        if is_number(t) or t in DASH_TOKENS:
            seen_num = True
            i -= 1
            continue
        # "ราคาต่อหน่วยต่ำกว่า 1 ล้านบาท 960,000 บาท" — หน่วยที่อยู่หน้าตัวเลขอีกตัวเป็นส่วนของป้าย
        if t in UNIT_WORDS and seen_num and unit_word:
            break
        if t in UNIT_WORDS:
            unit_word = unit_word or t
            i -= 1
            continue
        break
    # "ผูกพันงบประมาณปี 2571 20,000,000 บาท" — ปีที่ตามหลังคำว่า "ปี" เป็นส่วนของป้าย ไม่ใช่ช่องเงิน
    while (i < len(ws) and i > 0 and P.YEAR_TOKEN.fullmatch(clean(ws[i].text))
           and (clean(ws[i - 1].text).endswith("ปี") or clean(ws[i - 1].text).endswith("พ.ศ."))):
        i += 1
    label_ws, tail = ws[:i], ws[i:]
    cells: list[Cell] = []
    j = 0
    while j < len(tail):
        w = tail[j]
        t = clean(w.text)
        if t in UNIT_WORDS:
            j += 1
            continue
        if t in DASH_TOKENS:
            nxt = tail[j + 1] if j + 1 < len(tail) else None
            if nxt is not None and is_number(nxt.text) and (nxt.x0 - w.x1) <= NEG_GAP_PT:
                v = parse_amount(nxt.text)
                cells.append(Cell(f"-{clean(nxt.text)}", -v if v is not None else None,
                                  w.x0, min(w.y0, nxt.y0), nxt.x1, max(w.y1, nxt.y1)))
                j += 2
                continue
            cells.append(Cell(t, None, w.x0, w.y0, w.x1, w.y1))
            j += 1
            continue
        cells.append(Cell(clean(w.text), parse_amount(w.text), w.x0, w.y0, w.x1, w.y1))
        j += 1
    label = clean(_join(label_ws))
    return Row(page=page, text=clean(_join(ws)), label=label,
               cells=tuple(cells), words=tuple(ws),
               x0=min(w.x0 for w in ws), y0=min(w.y0 for w in ws),
               x1=max(w.x1 for w in ws), y1=max(w.y1 for w in ws),
               label_x0=label_ws[0].x0 if label_ws else ws[0].x0, unit_word=unit_word)


# ── หัวตาราง ───────────────────────────────────────────────────────────────────
_NUM_COLUMN_NAMES = (*P.CATEGORIES, *P.ECON_COLUMNS, P.COL_TOTAL)
_TEXT_COLUMN_NAMES = (*P.UNIT_HEADER_CUES,)


def header_columns(row: Row) -> list[Column]:
    """คอลัมน์จากบรรทัดหัวตาราง — คืนรายการว่างถ้าไม่ใช่หัวตาราง

    รวมคำติดกันได้ถึง 3 คำ (หัวตารางบางเล่มแตกคำ "งบ ดำเนินงาน") · ปี = "ปี 2570" หรือ "2570"
    """
    ws = list(row.words)
    cols: list[Column] = []
    used = set()
    for size in (4, 3, 2, 1):
        for k in range(len(ws) - size + 1):
            idx = range(k, k + size)
            if any(i in used for i in idx):
                continue
            chunk = ws[k:k + size]
            s = squash("".join(w.text for w in chunk))
            name, kind = _column_name(s)
            if name:
                cols.append(Column(name, chunk[0].x0, chunk[-1].x1, kind))
                used.update(idx)
    cols.sort(key=lambda c: c.x0)
    nums = [c for c in cols if c.kind == "num"]
    years = [c for c in nums if c.name.isdigit()]
    cats = [c for c in nums if not c.name.isdigit()]
    texts = [c for c in cols if c.kind == "text"]
    if len(years) >= 2 or len(cats) >= 2 or (texts and years):
        return cols
    return []


def _column_name(s: str):
    k = skeleton(s)                     # เทียบแบบตัดสระ/วรรณยุกต์ — เล่มจริงถอด "งบดำเนินงาน" เป็น "งบด าเนินงาน"
    for n in _NUM_COLUMN_NAMES:
        if k == skeleton(n):
            return n, "num"
    for n in _TEXT_COLUMN_NAMES:
        if k == skeleton(n):
            return "หน่วยนับ", "text"
    if s in ("ปี", ):
        return "", ""
    m = P.YEAR_TOKEN.fullmatch(s)
    if m:
        return m.group(1), "num"
    return "", ""


def assign(row: Row, cols: list[Column], nearest: set | None = None):
    """``({ชื่อคอลัมน์: Cell}, [Cell ที่ไม่เข้าคอลัมน์], {ชื่อคอลัมน์ข้อความ: ข้อความ})``

    ``nearest`` (ถ้าส่งมา) = ชื่อคอลัมน์ที่ได้จากการเลือก "คอลัมน์ที่ใกล้ที่สุด" (เซลล์อยู่นอกช่วงหัวตาราง)
    """
    nums = [c for c in cols if c.kind == "num"]
    texts = [c for c in cols if c.kind == "text"]
    got: dict[str, Cell] = {}
    loose: list[Cell] = []
    for cell in row.cells:
        best = None
        for c in nums:
            if c.x0 - COL_PAD_PT <= cell.cx <= c.x1 + COL_PAD_PT:
                if best is None or abs(cell.cx - c.cx) < abs(cell.cx - best.cx):
                    best = c
        by_nearest = False
        if best is None and nums:
            near = min(nums, key=lambda c: abs(cell.cx - c.cx))
            if abs(cell.cx - near.cx) <= NEAREST_PT:
                best, by_nearest = near, True
        if best is None or best.name in got:
            loose.append(cell)
        else:
            got[best.name] = cell
            if by_nearest and nearest is not None:
                nearest.add(best.name)
    text_cols: dict[str, str] = {}
    if texts:
        for c in texts:
            ws = [w for w in row.words
                  if c.x0 - TEXT_COL_PAD_PT <= (w.x0 + w.x1) / 2 <= c.x1 + TEXT_COL_PAD_PT
                  and not is_number(w.text)]
            if ws:
                text_cols[c.name] = clean(_join(ws))
    return got, loose, text_cols


def label_without_text_columns(row: Row, cols: list[Column]) -> str:
    """ป้ายของแถว โดยตัดคำที่อยู่ในคอลัมน์ข้อความ (เช่น หน่วยนับ) ออก"""
    texts = [c for c in cols if c.kind == "text"]
    if not texts:
        return row.label
    first_text_col = min(c.x0 for c in texts) - TEXT_COL_PAD_PT
    keep = [w for w in row.words if (w.x0 + w.x1) / 2 < first_text_col
            and not (is_number(w.text) or clean(w.text) in DASH_TOKENS)]
    return clean(_join(keep))
