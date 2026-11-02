# -*- coding: utf-8 -*-
"""#24 — เปิดแถวจริงในสมุดงานต้นฉบับ (หลักฐานชั้น Result Verification)

หน้าเทียบ A | B ต้องให้ผู้ตรวจเห็นว่า "ระบบเอาความต่างมาจากไหน" ด้วยตาตัวเอง
โมดูลนี้อ่านแถวรอบ ๆ เซลล์ที่เครื่องยนต์ชี้ จาก **ไฟล์ที่ใช้ตรวจรอบนั้นจริง**
แล้วคืนเป็นตารางเล็ก ๆ ที่ไฮไลต์เซลล์เป้าหมาย

กติกา

1. 🔴 อ่านผ่าน ``excel_reader._open`` เท่านั้น — ผ่านด่าน ``guard_file`` (#21)
   เหมือนทุกเส้นทางที่อ่านสมุดงาน
2. 🔴 ไฟล์ที่เก็บอยู่ต้องมี SHA-256 **ตรงกับ** ไฟล์ที่รอบตรวจนั้นใช้ (บันทึกใน Audit Trail)
   ไม่ตรง/ไม่พบ = ไม่แสดงเนื้อไฟล์ และบอกเหตุผล ห้ามแสดงไฟล์อื่นแทนเงียบ ๆ
3. แสดงค่าที่ Excel คำนวณไว้ (cached value) ตามที่เปิดในโปรแกรม ไม่ตีความเพิ่ม
4. ข้อความผ่าน ``privacy.redact_text`` เหมือนข้อความอื่นบนหน้าจอ
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl.utils import column_index_from_string, get_column_letter

from .. import privacy
from . import amounts
from ..readers import excel_reader

#: แถวก่อน/หลังแถวเป้าหมายที่แสดง — พอให้เห็นหัวข้อแม่และแถวข้างเคียง
CONTEXT_ROWS = 3
MAX_COLS = 12

_CELL = re.compile(r"^([A-Z]{1,3})([0-9]+)$")


@dataclass(frozen=True)
class XCell:
    ref: str
    text: str
    target: bool
    numeric: bool
    #: ค่าดิบตามที่อ่านจากไฟล์ (ก่อนจัดรูปแบบตามมาตรฐาน) — แสดงในรายละเอียดทางเทคนิค
    raw: str = ""


@dataclass(frozen=True)
class XRow:
    row: int
    cells: tuple[XCell, ...]
    target: bool


@dataclass(frozen=True)
class Excerpt:
    ok: bool
    reason: str = ""
    sheet: str = ""
    columns: tuple[str, ...] = ()
    rows: tuple[XRow, ...] = ()
    file_name: str = ""
    sha256: str = ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _display(value) -> tuple[str, bool]:
    if value is None:
        return "", False
    if isinstance(value, bool):
        return str(value), False
    if isinstance(value, (int, float, Decimal)):
        d = Decimal(str(value))
        s = format(d, ",f")
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s, True
    if isinstance(value, (datetime, date)):
        return value.isoformat(), False
    return privacy.redact_text(str(value)).strip(), False


def excerpt(path: Path | None, *, expected_sha256: str, sheet: str, row: int,
            target_cells: list[str], file_name: str = "", unit: str = "") -> Excerpt:
    """อ่านแถว ``row ± CONTEXT_ROWS`` ของชีต ``sheet`` — ไฮไลต์ ``target_cells``"""
    if path is None or not Path(path).exists():
        return Excerpt(False, "ไม่พบไฟล์ที่ใช้ตรวจในเครื่องแล้ว (อาจถูกลบตามนโยบายเก็บไฟล์)")
    actual = sha256_file(Path(path))
    if not expected_sha256:
        return Excerpt(False, "ไม่มีบันทึกลายนิ้วมือไฟล์ของรอบตรวจนี้ จึงยืนยันไม่ได้ว่าเป็นไฟล์เดียวกัน",
                       file_name=file_name, sha256=actual)
    if actual != expected_sha256:
        return Excerpt(False, "ไฟล์ที่เก็บอยู่ตอนนี้ไม่ใช่ไฟล์ที่ใช้ตรวจรอบนี้ (SHA-256 ไม่ตรง) — ไม่แสดงเนื้อไฟล์",
                       file_name=file_name, sha256=actual)
    if row is None or row < 1:
        return Excerpt(False, "ข้อสังเกตนี้ไม่ได้ผูกกับแถวใดในไฟล์", file_name=file_name, sha256=actual)
    try:
        wb, fh = excel_reader._open(Path(path), data_only=True)
    except excel_reader.ExcelReadError as e:
        return Excerpt(False, str(e), file_name=file_name, sha256=actual)
    try:
        if sheet not in wb.sheetnames:
            return Excerpt(False, "ไม่พบชีตที่ระบุในไฟล์", file_name=file_name, sha256=actual)
        ws = wb[sheet]
        lo = max(1, row - CONTEXT_ROWS)
        hi = min(ws.max_row or row, row + CONTEXT_ROWS)
        targets = set()
        for ref in target_cells:
            m = _CELL.match(ref or "")
            if m:
                targets.add((m.group(1), int(m.group(2))))
        target_cols = [column_index_from_string(c) for c, _ in targets]
        n_cols = min(ws.max_column or 1, MAX_COLS)
        n_cols = max([n_cols, *[c for c in target_cols if c <= 40]])
        grid = []
        last_used = 1
        for r in range(lo, hi + 1):
            cells = []
            for c in range(1, n_cols + 1):
                letter = get_column_letter(c)
                value = ws.cell(row=r, column=c).value
                raw, numeric = _display(value)
                text = raw
                # คอลัมน์ค่าที่ระบบเทียบ = ตารางเดียวกัน หน่วยเดียวกัน ⇒ มาตรฐานเดียวกับทุกหน้า
                if numeric and c in target_cols and unit:
                    text = amounts.format_number(value, unit)
                if text:
                    last_used = max(last_used, c)
                cells.append(XCell(f"{letter}{r}", text, (letter, r) in targets, numeric,
                                   raw=("" if value is None else str(value))))
            grid.append((r, cells))
        width = max([last_used, *target_cols]) if target_cols else last_used
        rows = tuple(XRow(r, tuple(cells[:width]), r == row) for r, cells in grid)
        cols = tuple(get_column_letter(c) for c in range(1, width + 1))
        return Excerpt(True, sheet=sheet, columns=cols, rows=rows,
                       file_name=file_name, sha256=actual)
    finally:
        wb.close()
        fh.close()


# ══════════════════════════════════════════════════════════════════════════════
#  บริบทของสมุดงาน (หน่วยงาน · ปีบนปก) — สำหรับแถบบริบทของคิว/หลักฐาน (#24)
# ══════════════════════════════════════════════════════════════════════════════

_CTX_CACHE: dict[str, dict] = {}


def workbook_context(path: Path | None, sha256: str) -> dict:
    """ชื่อหน่วยงานและปีที่ **เครื่องยนต์อ่านได้จากหน้าปกของแฟ้ม** — อ่านไม่ได้ = ค่าว่าง

    🔴 ไม่เดาจากชื่อไฟล์ · อ่านผ่าน ``t1b.read_workbook`` (ผ่านด่าน holdout/sealed เดียวกับตอนตรวจ)
    แคชตาม SHA-256 เพราะไฟล์ที่ใช้ตรวจแล้วไม่เปลี่ยน
    """
    if path is None or not sha256 or not Path(path).exists():
        return {"agency": "", "year": None}
    if sha256 in _CTX_CACHE:
        return _CTX_CACHE[sha256]
    from . import t1b as t1b_service
    try:
        records = t1b_service.read_workbook(path)
    except Exception:  # noqa: BLE001 — แถบบริบทต้องไม่ทำให้หน้าล้ม
        return {"agency": "", "year": None}
    agency = next((str(r.agency_name).strip() for r in records
                   if getattr(r, "agency_name", None)), "")
    years = [r.category_table_fiscal_year for r in records
             if getattr(r, "category_table_year_source", "") == "workbook_cover"
             and r.category_table_fiscal_year]
    ctx = {"agency": privacy.redact_text(agency), "year": years[0] if years else None}
    _CTX_CACHE[sha256] = ctx
    return ctx
