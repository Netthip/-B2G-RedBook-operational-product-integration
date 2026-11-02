# -*- coding: utf-8 -*-
"""ตัวอ่านไฟล์ Excel - อ่านอย่างเดียวเท่านั้น

ข้อบังคับของโมดูลนี้ (ฝั่ง "ตรวจ" ไม่ใช่ฝั่ง "สร้าง"):
  - เปิดไฟล์ผ่าน file handle โหมด rb และไม่มีการเรียก save() ที่ใดเลย
  - ไม่แปลความหมายคอลัมน์เอง ไม่เดาว่าคอลัมน์ไหนคือจำนวนเงิน
    หน้าที่ของ Phase 1 คือรายงาน "โครงสร้างที่อ่านได้" เพื่อให้ผู้ใช้กำหนด mapping เอง
  - openpyxl อ่านค่าที่ Excel คำนวณไว้ล่วงหน้า (cached value) ได้ก็ต่อเมื่อไฟล์เคยถูก
    เปิดและบันทึกด้วย Excel มาก่อน ถ้าไม่มี cache ระบบจะรายงานว่าอ่านค่าไม่ได้
    แทนที่จะเดาค่าเอง
"""
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from ..final_holdout import guard_file

PARSER_NAME = "openpyxl"
PARSER_VERSION = openpyxl.__version__
EXTRACTION_TEXT_LAYER = "openpyxl_cached_value"
EXTRACTION_FORMULA = "openpyxl_formula"


class ExcelReadError(Exception):
    """อ่านไฟล์ไม่ได้ - ข้อความในนี้ปลอดภัยพอจะแสดงให้ผู้ใช้เห็น"""


def parser_versions() -> dict:
    return {"excel": f"{PARSER_NAME}/{PARSER_VERSION}"}


def _open(path: Path, data_only: bool):
    guard_file(path)          # #21 — ชุดประเมินสุดท้ายที่ปิดผนึก ห้ามอ่าน
    fh = open(Path(path), "rb")
    try:
        wb = openpyxl.load_workbook(fh, data_only=data_only, keep_vba=False,
                                    read_only=False)
    except Exception:
        fh.close()
        raise ExcelReadError("เปิดไฟล์ Excel นี้ไม่ได้ ไฟล์อาจเสียหายหรือมีรหัสผ่าน")
    return wb, fh


def open_readonly_pair(path):
    """เปิดสมุดงานคู่ (แบบเห็นสูตร, แบบเห็นค่า cache) โหมดอ่านอย่างเดียวทั้งคู่

    ผู้เรียกรับผิดชอบปิดทั้งสี่ handle เอง — ใช้ใน excel_inventory
    """
    wb_f, fh_f = _open(path, data_only=False)
    try:
        wb_v, fh_v = _open(path, data_only=True)
    except ExcelReadError:
        wb_f.close()
        fh_f.close()
        raise
    return wb_f, fh_f, wb_v, fh_v


def _looks_like_number_text(value) -> bool:
    if not isinstance(value, str):
        return False
    s = value.strip().replace(",", "")
    if not s:
        return False
    if s.startswith("-"):
        s = s[1:]
    return s.replace(".", "", 1).isdigit()


def read_structure(path, max_scan_rows: int = 0) -> dict:
    """อ่านโครงสร้างสมุดงานแบบไม่ตีความหมาย

    max_scan_rows = 0 หมายถึงสแกนทุกแถวเท่าที่ไฟล์ระบุ
    """
    wb_f, fh_f = _open(path, data_only=False)
    try:
        wb_v, fh_v = _open(path, data_only=True)
    except ExcelReadError:
        wb_f.close()
        fh_f.close()
        raise

    try:
        sheets = []
        totals = {"cells_with_value": 0, "numeric": 0, "formula": 0,
                  "text": 0, "number_stored_as_text": 0, "percent_format": 0,
                  "cached_value_missing": 0}

        for name in wb_f.sheetnames:
            ws_f = wb_f[name]
            ws_v = wb_v[name] if name in wb_v.sheetnames else None
            max_row = ws_f.max_row or 0
            max_col = ws_f.max_column or 0
            scan_to = max_row if not max_scan_rows else min(max_row, max_scan_rows)

            counts = {"cells_with_value": 0, "numeric": 0, "formula": 0, "text": 0,
                      "number_stored_as_text": 0, "percent_format": 0,
                      "cached_value_missing": 0}

            for row in ws_f.iter_rows(min_row=1, max_row=scan_to, max_col=max_col):
                for cell in row:
                    v = cell.value
                    if v is None:
                        continue
                    counts["cells_with_value"] += 1
                    if isinstance(v, str) and v.startswith("="):
                        counts["formula"] += 1
                        cached = ws_v[cell.coordinate].value if ws_v is not None else None
                        if cached is None:
                            counts["cached_value_missing"] += 1
                    elif isinstance(v, (int, float)) and not isinstance(v, bool):
                        counts["numeric"] += 1
                    else:
                        counts["text"] += 1
                        if _looks_like_number_text(v):
                            counts["number_stored_as_text"] += 1
                    fmt = cell.number_format
                    if isinstance(fmt, str) and "%" in fmt:
                        counts["percent_format"] += 1

            for k in totals:
                totals[k] += counts[k]

            sheets.append({
                "name": name,
                "index": wb_f.sheetnames.index(name),
                "state": ws_f.sheet_state,                 # visible / hidden / veryHidden
                "dimension": ws_f.calculate_dimension(),
                "max_row": max_row,
                "max_col": max_col,
                "max_col_letter": get_column_letter(max_col) if max_col else "",
                "merged_ranges": sorted(str(r) for r in ws_f.merged_cells.ranges),
                "hidden_rows": sorted(r for r, d in ws_f.row_dimensions.items() if d.hidden),
                "hidden_cols": sorted(c for c, d in ws_f.column_dimensions.items() if d.hidden),
                "freeze_panes": ws_f.freeze_panes,
                "print_area": ws_f.print_area,
                "counts": counts,
            })

        return {
            "parser": f"{PARSER_NAME}/{PARSER_VERSION}",
            "sheet_count": len(sheets),
            "sheet_names": list(wb_f.sheetnames),
            "sheets": sheets,
            "totals": totals,
        }
    finally:
        wb_v.close()
        fh_v.close()
        wb_f.close()
        fh_f.close()


def read_cells(path, sheet_name: str, max_rows: int = 200, max_cols: int = 40) -> dict:
    """อ่านเนื้อเซลล์ช่วงต้นของชีตหนึ่ง สำหรับหน้า Evidence View และการกำหนด mapping

    คืนทั้งค่าที่คำนวณได้ สูตร รูปแบบตัวเลข และข้อความที่แสดง โดยแยกกันชัดเจน
    ไม่ตีความว่าค่าไหนคืออะไร
    """
    wb_f, fh_f = _open(path, data_only=False)
    wb_v, fh_v = _open(path, data_only=True)
    try:
        if sheet_name not in wb_f.sheetnames:
            raise ExcelReadError("ไม่พบชีตที่ระบุในไฟล์นี้")
        ws_f = wb_f[sheet_name]
        ws_v = wb_v[sheet_name]
        rows = []
        n_rows = min(ws_f.max_row or 0, max_rows)
        n_cols = min(ws_f.max_column or 0, max_cols)
        for r in range(1, n_rows + 1):
            cells = []
            for c in range(1, n_cols + 1):
                cf = ws_f.cell(row=r, column=c)
                cv = ws_v.cell(row=r, column=c)
                raw = cf.value
                is_formula = isinstance(raw, str) and raw.startswith("=")
                cells.append({
                    "ref": f"{get_column_letter(c)}{r}",
                    "column_letter": get_column_letter(c),
                    "row": r,
                    "formula": raw if is_formula else None,
                    "value": cv.value,
                    "value_available": not (is_formula and cv.value is None),
                    "number_format": cf.number_format,
                    "is_text": isinstance(raw, str) and not is_formula,
                })
            rows.append(cells)
        return {"sheet_name": sheet_name, "rows": rows,
                "row_count": n_rows, "col_count": n_cols,
                "truncated": (ws_f.max_row or 0) > n_rows or (ws_f.max_column or 0) > n_cols,
                "parser": f"{PARSER_NAME}/{PARSER_VERSION}"}
    finally:
        wb_v.close()
        fh_v.close()
        wb_f.close()
        fh_f.close()
