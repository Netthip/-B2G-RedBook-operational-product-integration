# -*- coding: utf-8 -*-
"""ตัวสำรวจโครงสร้างสมุดงานเชิงลึก (Phase 2A) - อ่านอย่างเดียว ไม่ตัดสินใจแทนผู้ใช้

หน้าที่ของโมดูลนี้คือ "รวบรวมหลักฐาน" สำหรับการตัดสินใจ mapping เท่านั้น
ทุกสิ่งที่ตรวจพบ (ปีงบประมาณ ชื่อหน่วยงาน แถวหัวตาราง หน่วยเงิน คอลัมน์รหัส
ร่องรอยลำดับชั้น) มีสถานะเป็น "candidate" พร้อมตำแหน่งอ้างอิงระดับ sheet/cell
ให้ผู้ใช้เป็นผู้ยืนยันก่อนนำไปใช้ตรวจจริงเสมอ

รายการคำสำคัญในไฟล์นี้เป็น heuristic สำหรับชี้จุดให้มนุษย์ดูเท่านั้น
ไม่ใช่ mapping และไม่มีผลตัดสินอัตโนมัติใด — เมื่อพบมากกว่าหนึ่งความเป็นไปได้
โมดูลรายงานทุกความเป็นไปได้ ไม่เลือกให้
"""
import re
from collections import Counter

from openpyxl.utils import get_column_letter

from .excel_reader import (PARSER_NAME, PARSER_VERSION, ExcelReadError,
                           open_readonly_pair)

INVENTORY_VERSION = "inventory-0.1.0"

# ---------------------------------------------------------------------------
# heuristic constants — ใช้ชี้ candidate เท่านั้น ไม่ใช่ mapping
# ---------------------------------------------------------------------------

# คำที่มักปรากฏในแถวหัวตารางของเอกสารงบประมาณไทย (ทั่วไป ไม่ผูกหน่วยงาน)
HEADER_VOCAB = [
    "ลำดับ", "รหัส", "รายการ", "รายละเอียด", "คำชี้แจง", "หมายเหตุ",
    "จำนวน", "หน่วยนับ", "ปริมาณ", "ราคาต่อหน่วย", "ราคา/หน่วย", "อัตรา",
    "งบประมาณ", "วงเงิน", "รวมเงิน", "รวมทั้งสิ้น", "รวมทั้งหมด",
    "เพิ่ม/ลด", "เพิ่มลด", "ผลต่าง", "ร้อยละ", "ปีงบประมาณ",
    "แผนงาน", "ผลผลิต", "โครงการ", "กิจกรรม", "หมวด", "ประเภท", "หน่วยงาน",
    # หน่วยเงินในแถวย่อยของหัวตาราง เช่น "(ล้านบาท)" — พบบ่อยในฟอร์มงบประมาณ
    "ล้านบาท", "บาท",
]

# token ที่มักเป็นส่วนหนึ่งของชื่อหน่วยงานราชการ (ทั่วไป ไม่ระบุหน่วยงานใด)
AGENCY_TOKENS = ["สถาบัน", "สำนักงาน", "กรม", "กระทรวง", "องค์การ", "กองทุน",
                 "ศูนย์", "สภา", "มหาวิทยาลัย", "โรงพยาบาล", "สำนัก"]

UNIT_TOKENS = ["ล้านบาท", "บาท", "หน่วย :", "หน่วย:", "หน่วยเป็น"]

YEAR_RE = re.compile(r"25[4-9]\d")
YEAR_CONTEXT = ["ปีงบประมาณ", "พ.ศ.", "ประจำปี", "ปี "]
TOTAL_ROW_RE = re.compile(r"รวมทั้งสิ้น|รวมทั้งหมด|^\s*รวม")
THAI_DIGIT_RE = re.compile(r"[๐-๙]")
EXCEL_ERRORS = {"#REF!", "#VALUE!", "#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!"}
SHEET_REF_RE = re.compile(r"(?:'([^!']+)'|([A-Za-z_฀-๿][\w.฀-๿]*))!")
EXTERNAL_REF_RE = re.compile(r"\[\d+\]")

# pattern ของข้อความที่ "ดูเหมือนรหัส" — เป็นข้อสังเกต ไม่ใช่คำตัดสิน
CODE_PATTERNS = [
    ("ตัวเลขล้วน", re.compile(r"^\d{2,}$")),
    ("ตัวเลขคั่นจุด", re.compile(r"^\d+(?:\.\d+)+$")),
    ("อักษรผสมตัวเลข", re.compile(r"^[A-Za-z0-9./\-]{3,}$")),
]

TOP_ROWS = 15          # เขตหัวเอกสาร: ใช้หา ปี/หน่วยงาน/หน่วยเงิน
HEADER_SCAN_ROWS = 40  # เขตค้นหาแถวหัวตาราง
MAX_BAND_HEIGHT = 3
MAX_CODE_SET = 2000


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _trunc(value, n=60) -> str:
    s = str(value)
    return s if len(s) <= n else s[: n - 1] + "…"


def _looks_like_code(samples) -> tuple:
    """คืน (bool, ชื่อ pattern ที่พบ) — ตัดสินจากสัดส่วนตัวอย่างที่เข้า pattern"""
    if not samples:
        return False, None
    hits = Counter()
    for s in samples:
        text = str(s).strip()
        for name, rx in CODE_PATTERNS:
            if rx.match(text):
                if name == "อักษรผสมตัวเลข":
                    digits = sum(ch.isdigit() for ch in text)
                    if digits / max(len(text), 1) < 0.4:
                        continue
                hits[name] += 1
                break
    total_hits = sum(hits.values())
    if total_hits / len(samples) >= 0.6:
        return True, hits.most_common(1)[0][0]
    return False, None


def _scan_sheet(ws_f, ws_v, max_scan_rows, max_cols, sample_n):
    max_row = ws_f.max_row or 0
    max_col_real = ws_f.max_column or 0
    ncols = min(max_col_real, max_cols)
    scan_to = min(max_row, max_scan_rows)

    cols = [{
        "letter": get_column_letter(c), "index": c,
        "n_numeric": 0, "n_formula": 0, "n_text": 0, "n_number_as_text": 0,
        "formats": Counter(), "samples": [], "indent_levels": Counter(),
        "code_set": set(), "code_overflow": False,
    } for c in range(1, ncols + 1)]

    header_row_hits = {}      # row -> {letter: matched_word}
    row_texts = {}            # row(<=HEADER_SCAN_ROWS) -> {letter: text}
    rows_with_numeric = set()
    top_texts = []            # (row, ref, text) ในเขตหัวเอกสาร
    year_numeric = []         # (row, ref, value) เลขปี พ.ศ. ที่เก็บเป็นตัวเลข
    total_rows = []
    bold_heading_rows = []
    thai_digit_cells = 0
    thai_digit_examples = []
    cached_missing = 0
    error_values = 0
    observed_last_row = 0
    observed_last_col = 0
    formulas = {"count": 0, "samples": [], "refs_to_sheets": Counter(), "external": []}

    if ncols:
        rows_f = ws_f.iter_rows(min_row=1, max_row=scan_to, max_col=ncols)
        rows_v = ws_v.iter_rows(min_row=1, max_row=scan_to, max_col=ncols)
        for row_f, row_v in zip(rows_f, rows_v):
            r = row_f[0].row
            row_has_numeric = False
            row_has_bold_text = False
            row_header_hits = {}
            for cf, cv in zip(row_f, row_v):
                v = cf.value
                if v is None:
                    continue
                cidx = cf.column
                col = cols[cidx - 1]
                letter = col["letter"]
                ref = f"{letter}{r}"
                observed_last_row = max(observed_last_row, r)
                observed_last_col = max(observed_last_col, cidx)

                is_formula = isinstance(v, str) and v.startswith("=")
                is_numeric = isinstance(v, (int, float)) and not isinstance(v, bool)

                if is_formula:
                    col["n_formula"] += 1
                    formulas["count"] += 1
                    if len(formulas["samples"]) < 5:
                        formulas["samples"].append(f"{ref}: {_trunc(v, 90)}")
                    for m in SHEET_REF_RE.finditer(v):
                        target = m.group(1) or m.group(2)
                        if target:
                            formulas["refs_to_sheets"][target] += 1
                    if EXTERNAL_REF_RE.search(v) and len(formulas["external"]) < 5:
                        formulas["external"].append(f"{ref}: {_trunc(v, 90)}")
                    cached = cv.value
                    if cached is None:
                        cached_missing += 1
                    elif isinstance(cached, (int, float)) and not isinstance(cached, bool):
                        row_has_numeric = True
                        col["formats"][cf.number_format] += 1
                        if len(col["samples"]) < sample_n:
                            col["samples"].append(f"(สูตร) {_trunc(cached)}")
                    elif isinstance(cached, str) and cached in EXCEL_ERRORS:
                        error_values += 1
                elif is_numeric:
                    col["n_numeric"] += 1
                    row_has_numeric = True
                    col["formats"][cf.number_format] += 1
                    if len(col["samples"]) < sample_n:
                        col["samples"].append(_trunc(v))
                    if r <= HEADER_SCAN_ROWS and isinstance(v, int) and 2540 <= v <= 2599:
                        year_numeric.append((r, ref, v))
                else:
                    text = str(v).strip()
                    if not text:
                        continue
                    col["n_text"] += 1
                    if re.fullmatch(r"-?[\d,]+(?:\.\d+)?", text.replace(" ", "")):
                        col["n_number_as_text"] += 1
                    if len(col["samples"]) < sample_n:
                        col["samples"].append(_trunc(text))
                    if len(col["code_set"]) < MAX_CODE_SET:
                        col["code_set"].add(text)
                    else:
                        col["code_overflow"] = True
                    if THAI_DIGIT_RE.search(text):
                        thai_digit_cells += 1
                        if len(thai_digit_examples) < 3:
                            thai_digit_examples.append(f"{ref}: {_trunc(text, 40)}")
                    try:
                        indent = int(cf.alignment.indent or 0)
                    except (TypeError, ValueError):
                        indent = 0
                    if indent > 0:
                        col["indent_levels"][indent] += 1
                    if cf.font is not None and cf.font.b:
                        row_has_bold_text = True
                    if r <= TOP_ROWS and len(text) >= 4:
                        top_texts.append((r, ref, _trunc(text, 120)))
                    if r <= HEADER_SCAN_ROWS:
                        row_texts.setdefault(r, {})[letter] = _trunc(text, 80)
                        norm = _norm(text)
                        for kw in HEADER_VOCAB:
                            if _norm(kw) in norm:
                                row_header_hits[letter] = kw
                                break
                    if TOTAL_ROW_RE.search(text) and len(total_rows) < 15:
                        total_rows.append({"row": r, "ref": ref, "text": _trunc(text, 80)})

            if row_has_numeric:
                rows_with_numeric.add(r)
            if len(row_header_hits) >= 2:
                header_row_hits[r] = row_header_hits
            if row_has_bold_text and not row_has_numeric and len(bold_heading_rows) < 20:
                bold_heading_rows.append(r)

    # --- เลือกแถบหัวตาราง (band) จากแถว candidate ที่ติดกัน ---
    band = None
    candidate_rows = sorted(header_row_hits)
    if candidate_rows:
        groups, cur = [], [candidate_rows[0]]
        for r in candidate_rows[1:]:
            if r == cur[-1] + 1 and len(cur) < MAX_BAND_HEIGHT:
                cur.append(r)
            else:
                groups.append(cur)
                cur = [r]
        groups.append(cur)
        band = max(groups, key=lambda g: sum(len(header_row_hits[r]) for r in g))

    header_band = {
        "candidate_rows": [{"row": r, "hits": len(header_row_hits[r]),
                            "matched": header_row_hits[r]} for r in candidate_rows],
        "best_rows": band,
        "note": ("" if band else
                 "ไม่พบแถวหัวตารางที่เข้าเกณฑ์ (คำสำคัญ ≥ 2 คอลัมน์) — ต้องให้ผู้ใช้ระบุเอง"),
    }

    # --- ช่วงข้อมูล candidate (หลังแถบหัวตาราง) ---
    data_range = None
    if band:
        band_end = band[-1]
        first_data = next((r for r in sorted(rows_with_numeric) if r > band_end), None)
        data_range = {
            "first_data_row": first_data,
            "last_data_row": observed_last_row or None,
            "basis": ("แถวแรกหลังแถบหัวตารางที่พบค่าตัวเลข และแถวสุดท้ายที่พบข้อมูล "
                      "— เป็น candidate ต้องยืนยัน"),
        }

    # --- header text ต่อคอลัมน์ จากแถบหัวตาราง ---
    for col in cols:
        if band:
            parts = [row_texts.get(r, {}).get(col["letter"]) for r in band]
            col["header_text"] = " / ".join(p for p in parts if p) or None
        else:
            col["header_text"] = None
        below = max(col["n_numeric"] + col["n_text"] + col["n_formula"], 0)
        col["code_like"], col["code_pattern"] = _looks_like_code(
            sorted(col["code_set"])[:10]) if col["n_text"] else (False, None)
        col["distinct_text_values"] = (f">{MAX_CODE_SET}" if col["code_overflow"]
                                       else len(col["code_set"]))
        col["formats_top"] = dict(col["formats"].most_common(3))
        col["dominant_number_format"] = (col["formats"].most_common(1)[0][0]
                                         if col["formats"] else None)
        col["indent_levels"] = dict(col["indent_levels"])
        col["code_values"] = (sorted(col["code_set"]) if col["code_like"]
                              and not col["code_overflow"] else None)
        del col["code_set"], col["formats"], col["code_overflow"]
        col["_below"] = below

    used_cols = [c for c in cols if c["_below"] > 0 or c["header_text"]]
    for c in used_cols:
        del c["_below"]

    formulas["refs_to_sheets"] = dict(formulas["refs_to_sheets"])

    return {
        "name": ws_f.title,
        "state": ws_f.sheet_state,
        "declared_dimension": ws_f.calculate_dimension(),
        "max_row": max_row,
        "max_col": max_col_real,
        "observed_last_row": observed_last_row,
        "observed_last_col": observed_last_col,
        "merged_count": len(ws_f.merged_cells.ranges),
        "merged_ranges": sorted(str(x) for x in ws_f.merged_cells.ranges)[:50],
        "hidden_rows": sorted(r for r, d in ws_f.row_dimensions.items() if d.hidden)[:50],
        "hidden_cols": sorted(c for c, d in ws_f.column_dimensions.items() if d.hidden)[:50],
        "freeze_panes": ws_f.freeze_panes,
        "print_area": ws_f.print_area,
        "header_band": header_band,
        "data_range": data_range,
        "total_row_candidates": total_rows,
        "bold_heading_rows": bold_heading_rows,
        "columns": used_cols,
        "formulas": formulas,
        "top_texts": [{"row": r, "ref": ref, "text": t} for r, ref, t in top_texts[:40]],
        "year_numeric_cells": [{"row": r, "ref": ref, "value": v}
                               for r, ref, v in year_numeric[:20]],
        "thai_digit_cells": thai_digit_cells,
        "thai_digit_examples": thai_digit_examples,
        "uncertainties": {
            "cached_value_missing": cached_missing,
            "error_values": error_values,
            "scan_capped_at": scan_to if max_row > scan_to else None,
            "cols_capped_at": ncols if max_col_real > ncols else None,
        },
    }


def _workbook_candidates(sheets) -> dict:
    """สกัด candidate ระดับสมุดงาน (ปี/หน่วยงาน/หน่วยเงิน) จากเขตหัวเอกสารทุกชีต"""
    years = {}
    agencies = []
    units = []
    for sh in sheets:
        for item in sh["top_texts"]:
            text = item["text"]
            loc = {"sheet": sh["name"], "ref": item["ref"], "text": text}
            for m in YEAR_RE.finditer(text):
                y = int(m.group(0))
                weight = 2 if any(c in text for c in YEAR_CONTEXT) else 1
                slot = years.setdefault(y, {"weight": 0, "examples": []})
                slot["weight"] += weight
                if len(slot["examples"]) < 5:
                    slot["examples"].append(loc)
            if any(tok in text for tok in AGENCY_TOKENS) and len(text) >= 6:
                if len(agencies) < 10 and all(a["text"] != text for a in agencies):
                    agencies.append(loc)
            if any(tok in text for tok in UNIT_TOKENS):
                if len(units) < 10 and all(u["ref"] != item["ref"] or
                                           u["sheet"] != sh["name"] for u in units):
                    units.append(loc)
        for yc in sh["year_numeric_cells"]:
            slot = years.setdefault(yc["value"], {"weight": 0, "examples": []})
            slot["weight"] += 1
            if len(slot["examples"]) < 5:
                slot["examples"].append({"sheet": sh["name"], "ref": yc["ref"],
                                         "text": f"(ตัวเลข) {yc['value']}"})
    year_list = [{"year": y, "weight": d["weight"], "examples": d["examples"]}
                 for y, d in sorted(years.items(), key=lambda kv: -kv[1]["weight"])]
    return {"year_candidates": year_list[:8],
            "agency_candidates": agencies,
            "unit_hints": units}


def inventory_workbook(path, max_scan_rows=4000, max_cols=60, sample_n=3) -> dict:
    """สำรวจสมุดงานหนึ่งไฟล์แบบอ่านอย่างเดียว คืนโครงสร้างหลักฐานทั้งหมด

    ไม่แก้ไฟล์ ไม่ตัดสินใจ mapping — ผู้เรียกควรคำนวณ SHA-256 ก่อน/หลัง
    เพื่อยืนยันว่าไฟล์ต้นฉบับไม่ถูกเปลี่ยน (inventory_cli ทำให้อยู่แล้ว)
    """
    wb_f, fh_f, wb_v, fh_v = open_readonly_pair(path)
    try:
        sheets = []
        for name in wb_f.sheetnames:
            ws_f = wb_f[name]
            if name not in wb_v.sheetnames:
                raise ExcelReadError("โครงสร้างชีตของไฟล์ไม่สอดคล้องระหว่างการอ่านสองรอบ")
            sheets.append(_scan_sheet(ws_f, wb_v[name], max_scan_rows, max_cols, sample_n))

        try:
            defined_names = sorted(wb_f.defined_names.keys())[:30]
        except Exception:
            defined_names = []

        wb_level = _workbook_candidates(sheets)
        external = sorted({s for sh in sheets for s in sh["formulas"]["external"]})[:10]
        return {
            "inventory_version": INVENTORY_VERSION,
            "parser": f"{PARSER_NAME}/{PARSER_VERSION}",
            "scan_limits": {"max_scan_rows": max_scan_rows, "max_cols": max_cols},
            "sheet_names": list(wb_f.sheetnames),
            "hidden_sheets": [s["name"] for s in sheets if s["state"] != "visible"],
            "defined_names": defined_names,
            "external_refs": external,
            **wb_level,
            "sheets": sheets,
        }
    finally:
        wb_v.close()
        fh_v.close()
        wb_f.close()
        fh_f.close()


def _header_map(sheet_inv) -> dict:
    return {c["letter"]: (c.get("header_text") or "") for c in sheet_inv["columns"]}


def compare_structures(inv_a: dict, inv_b: dict) -> dict:
    """เทียบโครงสร้างสองสมุดงาน (เชิงโครงสร้างล้วน ไม่เทียบค่ารายการ)"""
    names_a, names_b = inv_a["sheet_names"], inv_b["sheet_names"]
    common = [n for n in names_a if n in names_b]
    out = {
        "sheets_only_a": [n for n in names_a if n not in names_b],
        "sheets_only_b": [n for n in names_b if n not in names_a],
        "sheet_order_same": names_a == names_b,
        "common_sheets": [],
    }
    by_a = {s["name"]: s for s in inv_a["sheets"]}
    by_b = {s["name"]: s for s in inv_b["sheets"]}
    for name in common:
        sa, sb = by_a[name], by_b[name]
        ha, hb = _header_map(sa), _header_map(sb)
        letters = sorted(set(ha) | set(hb))
        changed = [{"letter": L, "a": ha.get(L) or None, "b": hb.get(L) or None}
                   for L in letters if (ha.get(L) or "") != (hb.get(L) or "")][:40]
        code_overlap = []
        cb_map = {c["letter"]: c for c in sb["columns"]}
        for ca in sa["columns"]:
            cb = cb_map.get(ca["letter"])
            if not (cb and ca.get("code_values") and cb.get("code_values")):
                continue
            set_a, set_b = set(ca["code_values"]), set(cb["code_values"])
            inter = len(set_a & set_b)
            denom = min(len(set_a), len(set_b)) or 1
            code_overlap.append({
                "letter": ca["letter"],
                "distinct_a": len(set_a), "distinct_b": len(set_b),
                "shared": inter,
                "containment_pct": round(100.0 * inter / denom, 1),
            })
        out["common_sheets"].append({
            "name": name,
            "range_a": sa["declared_dimension"], "range_b": sb["declared_dimension"],
            "observed_rows_a": sa["observed_last_row"],
            "observed_rows_b": sb["observed_last_row"],
            "header_band_a": (sa["header_band"]["best_rows"] or None),
            "header_band_b": (sb["header_band"]["best_rows"] or None),
            "header_diffs": changed,
            "code_column_overlap": code_overlap,
        })
    return out
