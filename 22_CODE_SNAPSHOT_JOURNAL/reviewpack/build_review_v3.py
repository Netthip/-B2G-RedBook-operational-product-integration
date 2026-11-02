# -*- coding: utf-8 -*-
"""
reviewpack v1.3.0 — presentation layer ใหม่ตามคำสั่งกิ๊ฟ 28 ส.ค. 2569

หลักการ: หนึ่ง canonical item/finding ต่อหนึ่งแถว · ค่าฝั่งร่างกับฝั่ง พ.ร.บ. เคียงกัน
ห้ามแก้: frozen engine · findings · raw values · canonical values · source hashes · คำตอบที่กรอกแล้ว

อ่านข้อมูลจากไฟล์ working copy รุ่นเดิม (read-only) แล้วจัดหน้าใหม่เท่านั้น
"""
import shutil, hashlib, json, datetime, re
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.datavalidation import DataValidation

VERSION = "reviewpack-1.3.0"

# ---------- กติกาสีตามคำสั่งข้อ 5 ----------
RED_BG    = "FFFDE7E9"; RED_FG    = "FF9C0006"   # วงเงินลดลง
GREEN_BG  = "FFE6F4EA"; GREEN_FG  = "FF0B6B2E"   # วงเงินเพิ่มขึ้น
GREY_BG   = "FFF0F1F3"; GREY_FG   = "FF5F6368"   # ไม่เปลี่ยนแปลง
YELLOW_BG = "FFFFF2CC"; YELLOW_FG = "FF7F6000"   # สงวนไว้เฉพาะ uncertain
ORANGE_BG = "FFFFE0B2"; ORANGE_FG = "FF8A4B00"   # schema conflict
HDR_BG    = "FF1F3864"; HDR_FG    = "FFFFFFFF"
BAND_BG   = "FFF2F5FA"

THIN = Side(style="thin", color="FFD0D7E2")
BOX  = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

DIR_DOWN = "▼ ลดลง"; DIR_UP = "▲ เพิ่มขึ้น"; DIR_SAME = "= ไม่เปลี่ยนแปลง"
MATCH_OK = "✓ จับคู่ได้"; MATCH_NO = "✕ จับคู่ไม่ได้"
MATCH_UNSURE = "? ไม่แน่ใจ"; MATCH_SCHEMA = "⚠ Schema conflict"

VERDICTS = ["ยืนยัน", "ไม่ยืนยัน", "ไม่แน่ใจ"]
OPENED = ["เปิดแล้ว", "ยังไม่ได้เปิด"]
# semantic values ตาม SYS-D-26 — ไทยเป็น display label เท่านั้น
VERDICT_SEMANTIC = {"ยืนยัน": "confirmed", "ไม่ยืนยัน": "rejected", "ไม่แน่ใจ": "uncertain"}
LEGACY_SEMANTIC  = {"ถูกต้อง": "confirmed", "ไม่ถูกต้อง": "rejected", "ตัดสินไม่ได้": "uncertain"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_source(src):
    """อ่าน findings จาก working copy เดิม — ไม่แก้ค่าใด ๆ"""
    wb = openpyxl.load_workbook(src)          # เก็บสูตร
    wbv = openpyxl.load_workbook(src, data_only=True)  # เก็บค่า
    rv, tech, loc = wb["Review"], wb["Technical Details"], wb["ตำแหน่งตรวจสอบต้นทาง"]
    tech_by_id = {tech.cell(r, 1).value: r for r in range(5, tech.max_row + 1) if tech.cell(r, 1).value}
    loc_by_id  = {loc.cell(r, 1).value: r for r in range(5, loc.max_row + 1) if loc.cell(r, 1).value}
    rows = []
    for r in range(5, rv.max_row + 1):
        fid = rv.cell(r, 2).value
        if not fid:
            continue
        tr = tech_by_id.get(fid); lr = loc_by_id.get(fid)
        d = {
            "seq": rv.cell(r, 1).value, "fid": fid,
            "match_raw": rv.cell(r, 3).value,
            "agency": rv.cell(r, 4).value, "budget_type": rv.cell(r, 5).value,
            "plan": rv.cell(r, 6).value, "output": rv.cell(r, 7).value,
            "activity": rv.cell(r, 8).value, "cat": rv.cell(r, 9).value,
            "subcat": rv.cell(r, 10).value, "nature": rv.cell(r, 11).value,
            "item": rv.cell(r, 12).value, "unit": rv.cell(r, 13).value,
            "amt_a": rv.cell(r, 14).value, "amt_b": rv.cell(r, 15).value,
            "raw_ok": rv.cell(r, 18).value,
            "loc_a": rv.cell(r, 19).value, "loc_b": rv.cell(r, 20).value,
            "link_a": rv.cell(r, 19).value, "link_b": rv.cell(r, 20).value,
            # คำตอบเดิมของผู้วิจัย (ต้องย้ายครบ — acceptance ข้อ 12)
            "opened_a": rv.cell(r, 21).value, "opened_b": rv.cell(r, 22).value,
            "verdict": rv.cell(r, 23).value, "confidence": rv.cell(r, 24).value,
            "reason": rv.cell(r, 25).value, "reviewed_at": rv.cell(r, 26).value,
        }
        # HYPERLINK จริงอยู่ที่คอลัมน์ S/T (19/20)
        for k, col in (("hl_a", 19), ("hl_b", 20)):
            v = rv.cell(r, col).value
            m = re.match(r'=HYPERLINK\("([^"]+)"\s*,\s*"(.*)"\)\s*$', str(v or ""), re.S)
            d[k] = m.group(1) if m else None
        if tr:
            d.update({
                "finding_id": tech.cell(tr, 2).value, "experiment": tech.cell(tr, 3).value,
                "tier": tech.cell(tr, 4).value, "cat_code": tech.cell(tr, 5).value,
                "cat_mean": tech.cell(tr, 6).value, "rule": tech.cell(tr, 7).value,
                "ruleset": tech.cell(tr, 8).value, "sys_decision": tech.cell(tr, 9).value,
                "match_method": tech.cell(tr, 11).value, "pipeline": tech.cell(tr, 12).value,
                "raw_a": tech.cell(tr, 15).value, "raw_b": tech.cell(tr, 16).value,
                "norm_a": tech.cell(tr, 17).value, "norm_b": tech.cell(tr, 18).value,
                "diff_tech": tech.cell(tr, 19).value, "currency": tech.cell(tr, 20).value,
                "pct": tech.cell(tr, 21).value, "pct_note": tech.cell(tr, 22).value,
                "file_a": tech.cell(tr, 27).value, "sheet_a": tech.cell(tr, 28).value,
                "row_a": tech.cell(tr, 29).value, "cell_a": tech.cell(tr, 30).value,
                "sha_a": tech.cell(tr, 31).value,
                "file_b": tech.cell(tr, 33).value, "sheet_b": tech.cell(tr, 34).value,
                "row_b": tech.cell(tr, 35).value, "cell_b": tech.cell(tr, 36).value,
                "sha_b": tech.cell(tr, 37).value,
            })
        if lr:
            d["canon_key"] = loc.cell(lr, 10).value
            d["side_a_label"] = loc.cell(lr, 11).value
            d["side_b_label"] = loc.cell(lr, 13).value
        rows.append(d)
    return wb, wbv, rows


FORMULA_RE = __import__("re").compile(r"^=[A-Za-z_][A-Za-z0-9_.]*\(")


def force_text_cells(wb):
    """แก้ defect: ข้อความที่ขึ้นต้นด้วย '=' ถูก openpyxl เก็บเป็นสูตร → Excel แสดง #NAME?
    บังคับชนิดเป็นข้อความ โดย**ไม่เปลี่ยนถ้อยคำแม้แต่ตัวอักษรเดียว**
    สูตรจริง (=IF(... =COUNTIF(... =HYPERLINK(...) ไม่ถูกแตะ"""
    fixed = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if isinstance(v, str) and v.startswith("=") and not FORMULA_RE.match(v):
                    c.value = v
                    c.data_type = "s"
                    fixed += 1
    return fixed


def fill(c, bg=None, fg=None, bold=False, size=None):
    if bg: c.fill = PatternFill("solid", fgColor=bg)
    if fg or bold or size:
        f = c.font
        cur = None
        try:
            cur = f.color.rgb if (f.color is not None and isinstance(f.color.rgb, str)) else None
        except Exception:
            cur = None
        c.font = Font(color=fg or cur, bold=bold or bool(f.bold),
                      size=size or f.size, name=f.name)
    return c


def direction_of(a, b):
    """ผลต่าง = พ.ร.บ. − ร่าง พ.ร.บ. (คำสั่งข้อ 4)"""
    if a is None or b is None: return None, None
    d = b - a
    return d, (DIR_DOWN if d < 0 else DIR_UP if d > 0 else DIR_SAME)


def build_summary(wb, rows):
    ws = wb.create_sheet("Summary", 0)
    ws.sheet_view.showGridLines = False
    ws["A1"] = "สรุปภาพรวมการตรวจ — Primary Case Review รอบที่ 1"
    fill(ws["A1"], bold=True, size=15, fg="FF1F3864")
    ws["A2"] = f"{VERSION} · สวรส. และสถาบันวัคซีนแห่งชาติ · คู่ร่าง พ.ร.บ. 2569 ↔ พ.ร.บ. 2569"
    fill(ws["A2"], fg=GREY_FG)
    down = sum(1 for r in rows if (r["amt_b"] or 0) - (r["amt_a"] or 0) < 0)
    up   = sum(1 for r in rows if (r["amt_b"] or 0) - (r["amt_a"] or 0) > 0)
    same = sum(1 for r in rows if (r["amt_b"] or 0) - (r["amt_a"] or 0) == 0)
    n = len(rows)
    items = [
        ("รายการทั้งหมด", n, None, None),
        ("วงเงินลดลง", down, RED_BG, RED_FG),
        ("วงเงินเพิ่มขึ้น", up, GREEN_BG, GREEN_FG),
        ("ไม่เปลี่ยนแปลง", same, GREY_BG, GREY_FG),
        ("จับคู่ไม่ได้ / ไม่แน่ใจ", 0, YELLOW_BG, YELLOW_FG),
    ]
    r0 = 4
    ws.cell(r0, 1, "หมวด"); ws.cell(r0, 2, "จำนวน")
    for c in (1, 2): fill(ws.cell(r0, c), HDR_BG, HDR_FG, bold=True)
    for i, (lab, v, bg, fg) in enumerate(items, 1):
        ws.cell(r0 + i, 1, lab); ws.cell(r0 + i, 2, v)
        if bg:
            fill(ws.cell(r0 + i, 1), bg, fg); fill(ws.cell(r0 + i, 2), bg, fg, bold=True)
    r1 = r0 + len(items) + 2
    ws.cell(r1, 1, "ความคืบหน้าการตรวจ"); fill(ws.cell(r1, 1), bold=True, fg="FF1F3864")
    ws.cell(r1 + 1, 1, "ตรวจแล้ว (มีคำตัดสิน)")
    ws.cell(r1 + 1, 2, f'=COUNTIF(Review!Q5:Q{4+n},"<>")')
    ws.cell(r1 + 2, 1, "ยังไม่ได้ตรวจ")
    ws.cell(r1 + 2, 2, f'=COUNTBLANK(Review!Q5:Q{4+n})')
    ws.cell(r1 + 3, 1, "ยืนยัน");     ws.cell(r1 + 3, 2, f'=COUNTIF(Review!Q5:Q{4+n},"ยืนยัน")')
    ws.cell(r1 + 4, 1, "ไม่ยืนยัน");  ws.cell(r1 + 4, 2, f'=COUNTIF(Review!Q5:Q{4+n},"ไม่ยืนยัน")')
    ws.cell(r1 + 5, 1, "ไม่แน่ใจ");   ws.cell(r1 + 5, 2, f'=COUNTIF(Review!Q5:Q{4+n},"ไม่แน่ใจ")')
    fill(ws.cell(r1 + 5, 1), YELLOW_BG, YELLOW_FG)
    r2 = r1 + 7
    ws.cell(r2, 1, "คำอธิบายสี (legend)"); fill(ws.cell(r2, 1), bold=True, fg="FF1F3864")
    legend = [
        ("▼ ลดลง", "วงเงินตาม พ.ร.บ. ต่ำกว่าร่าง พ.ร.บ.", RED_BG, RED_FG),
        ("▲ เพิ่มขึ้น", "วงเงินตาม พ.ร.บ. สูงกว่าร่าง พ.ร.บ.", GREEN_BG, GREEN_FG),
        ("= ไม่เปลี่ยนแปลง", "วงเงินทั้งสองฝั่งเท่ากัน", GREY_BG, GREY_FG),
        ("สีเหลือง", "สงวนไว้เฉพาะ: ต้องให้มนุษย์ตรวจ · หลักฐานไม่ครบ · จับคู่ไม่แน่ใจ · schema สงสัย · คำนวณไม่ได้", YELLOW_BG, YELLOW_FG),
        ("✕ จับคู่ไม่ได้", "ระบบยังเชื่อมรายการสองฝั่งไม่ได้ — ไม่ได้แปลว่าเอกสารผิด", RED_BG, RED_FG),
    ]
    for i, (a, b, bg, fg) in enumerate(legend, 1):
        fill(ws.cell(r2 + i, 1, a), bg, fg, bold=True)
        ws.cell(r2 + i, 2, b)
    ws.column_dimensions["A"].width = 30; ws.column_dimensions["B"].width = 95
    return ws


REVIEW_COLS = [
    ("ลำดับ", 6), ("รหัสรายการตรวจ", 12), ("สถานะการจับคู่", 15), ("หน่วยงาน", 26),
    ("แผนงาน", 26), ("ผลผลิต/โครงการ", 28), ("กิจกรรม", 28), ("หมวดรายจ่าย", 14),
    ("ประเภทรายจ่าย", 20), ("ลักษณะรายจ่าย", 14), ("ชื่อรายการ", 24),
    ("จำนวนเงินตามร่าง พ.ร.บ. 2569 (บาท)", 22), ("จำนวนเงินตาม พ.ร.บ. 2569 (บาท)", 22),
    ("ผลต่าง (บาท)", 18), ("ทิศทาง", 18),
    ("เปิดหลักฐานฝั่งร่าง", 16), ("เปิดหลักฐานฝั่ง พ.ร.บ.", 16),
    ("คำตัดสินผู้วิจัย", 15), ("เหตุผล/หมายเหตุ", 40), ("สถานะความครบถ้วน", 20),
]


def build_review(wb, rows):
    ws = wb.create_sheet("Review", 1)
    ws.sheet_view.showGridLines = False
    ws["A1"] = "หน้าตรวจหลัก — หนึ่งรายการต่อหนึ่งแถว · ค่าฝั่งร่างและฝั่ง พ.ร.บ. อยู่เคียงกัน"
    fill(ws["A1"], bold=True, size=14, fg="FF1F3864")
    ws["A2"] = ("ผลต่าง = จำนวนเงินตาม พ.ร.บ. − จำนวนเงินตามร่าง พ.ร.บ.  ·  "
                "ค่าติดลบ = วงเงินลดลง (แดง) · ค่าบวก = วงเงินเพิ่มขึ้น (เขียว) · ศูนย์ = ไม่เปลี่ยนแปลง (เทา)")
    fill(ws["A2"], fg=GREY_FG)
    ws["A3"] = "สีเหลืองใช้เฉพาะรายการที่ต้องให้มนุษย์วินิจฉัยเพิ่ม ไม่ได้ใช้บอกว่าเป็นแถวที่เลือก"
    fill(ws["A3"], fg=YELLOW_FG)
    hr = 4
    for i, (name, w) in enumerate(REVIEW_COLS, 1):
        c = ws.cell(hr, i, name)
        fill(c, HDR_BG, HDR_FG, bold=True)
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        c.border = BOX
        ws.column_dimensions[L(i)].width = w
    ws.row_dimensions[hr].height = 44

    for i, d in enumerate(rows):
        r = hr + 1 + i
        diff, direction = direction_of(d["amt_a"], d["amt_b"])
        band = BAND_BG if i % 2 else None
        vals = [
            d["seq"], d["fid"], MATCH_OK, d["agency"], d["plan"], d["output"], d["activity"],
            d["cat"], d["subcat"], d["nature"], d["item"], d["amt_a"], d["amt_b"], diff, direction,
            d["opened_a"], d["opened_b"], d["verdict"], d["reason"], None,
        ]
        for ci, v in enumerate(vals, 1):
            c = ws.cell(r, ci, v)
            c.border = BOX
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if band: fill(c, band)
        # เงิน: comma + เครื่องหมาย +/−
        ws.cell(r, 12).number_format = '#,##0'
        ws.cell(r, 13).number_format = '#,##0'
        ws.cell(r, 14).number_format = '+#,##0;−#,##0;0'
        for ci in (12, 13, 14):
            ws.cell(r, ci).alignment = Alignment(horizontal="right", vertical="top")
        # กติกาสีข้อ 5 — ลงสีเฉพาะ พ.ร.บ. / ผลต่าง / ทิศทาง
        if diff is None:
            for ci in (13, 14, 15): fill(ws.cell(r, ci), YELLOW_BG, YELLOW_FG, bold=True)
        elif diff < 0:
            for ci in (13, 14, 15): fill(ws.cell(r, ci), RED_BG, RED_FG, bold=True)
        elif diff > 0:
            for ci in (13, 14, 15): fill(ws.cell(r, ci), GREEN_BG, GREEN_FG, bold=True)
        else:
            for ci in (13, 14, 15): fill(ws.cell(r, ci), GREY_BG, GREY_FG)
        ws.cell(r, 15).alignment = Alignment(horizontal="center", vertical="center")
        # matching status แยกคอลัมน์ (ข้อ 6)
        fill(ws.cell(r, 3), GREEN_BG, GREEN_FG, bold=True)
        ws.cell(r, 3).alignment = Alignment(horizontal="center", vertical="center")
        # ปุ่มเปิดหลักฐาน — ข้อความสั้นตามข้อ 9 (ลิงก์อยู่ที่ Evidence Comparison)
        ws.cell(r, 20, f'=IF(R{r}="","ยังไม่ได้ตอบ",IF(AND(P{r}="เปิดแล้ว",Q{r}="เปิดแล้ว"),"ครบแล้ว","ตอบแล้ว แต่ยังไม่ได้ยืนยันว่าเปิดหลักฐานครบสองฝั่ง"))')
        fill(ws.cell(r, 20), band)
    n = len(rows)
    ws.freeze_panes = "D5"
    ws.auto_filter.ref = f"A{hr}:T{hr+n}"
    dv_v = DataValidation(type="list", formula1='"' + ",".join(VERDICTS) + '"', allow_blank=True)
    dv_o = DataValidation(type="list", formula1='"' + ",".join(OPENED) + '"', allow_blank=True)
    ws.add_data_validation(dv_v); ws.add_data_validation(dv_o)
    dv_v.add(f"R5:R{4+n}"); dv_o.add(f"P5:P{4+n}"); dv_o.add(f"Q5:Q{4+n}")
    return ws


def build_evidence_comparison(wb, rows):
    """หนึ่ง finding = หนึ่งบล็อก · สองฝั่งเคียงกัน (คำสั่งข้อ 7)"""
    ws = wb.create_sheet("Evidence Comparison", 2)
    ws.sheet_view.showGridLines = False
    ws["A1"] = "เทียบหลักฐานสองฝั่งเคียงกัน — หนึ่งรายการต่อหนึ่งบล็อก"
    fill(ws["A1"], bold=True, size=14, fg="FF1F3864")
    ws["A2"] = "ไฮไลต์เฉพาะ field ที่แตกต่างจริง — ชื่อที่เหมือนกันไม่ลงสี"
    fill(ws["A2"], fg=GREY_FG)
    for col, w in (("A", 20), ("B", 46), ("C", 46), ("D", 20)):
        ws.column_dimensions[col].width = w
    r = 4
    LEVELS = [("แผนงาน", "plan"), ("ผลผลิต/โครงการ", "output"), ("กิจกรรม", "activity"),
              ("หมวดรายจ่าย", "cat"), ("ประเภทรายจ่าย", "subcat"),
              ("ลักษณะรายจ่าย", "nature"), ("ชื่อรายการ", "item")]
    for d in rows:
        diff, direction = direction_of(d["amt_a"], d["amt_b"])
        # หัวบล็อก
        ws.cell(r, 1, f'{d["fid"]}  ·  {d["item"] or ""}')
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        fill(ws.cell(r, 1), "FFEDF1F8", "FF1F3864", bold=True, size=12)
        ws.cell(r, 1).border = BOX
        r += 1
        ws.cell(r, 1, f'หน่วยงาน: {d["agency"] or ""}')
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        fill(ws.cell(r, 1), fg=GREY_FG)
        r += 1
        # หัวตาราง
        for ci, h in enumerate(["ลำดับชั้น", "ร่าง พ.ร.บ. 2569", "พ.ร.บ. 2569", "ผลต่าง"], 1):
            c = ws.cell(r, ci, h); fill(c, HDR_BG, HDR_FG, bold=True); c.border = BOX
            c.alignment = Alignment(horizontal="center")
        r += 1
        # ลำดับชั้น — สองฝั่งเคียงกัน ค่าเดียวกันทั้งคู่ (canonical key เดียว)
        for label, key in LEVELS:
            v = d.get(key)
            ws.cell(r, 1, label); ws.cell(r, 2, v); ws.cell(r, 3, v)
            for ci in (1, 2, 3, 4):
                c = ws.cell(r, ci); c.border = BOX
                c.alignment = Alignment(wrap_text=True, vertical="top")
            fill(ws.cell(r, 1), "FFF7F8F9", bold=True)
            r += 1
        # จำนวนเงิน — แถวชี้ขาด
        ws.cell(r, 1, "จำนวนเงิน (บาท)")
        ws.cell(r, 2, d["amt_a"]); ws.cell(r, 3, d["amt_b"]); ws.cell(r, 4, diff)
        ws.cell(r, 2).number_format = '#,##0'
        ws.cell(r, 3).number_format = '#,##0'
        ws.cell(r, 4).number_format = '+#,##0;−#,##0;0'
        fill(ws.cell(r, 1), "FFF7F8F9", bold=True)
        for ci in (1, 2, 3, 4):
            ws.cell(r, ci).border = BOX
            if ci > 1: ws.cell(r, ci).alignment = Alignment(horizontal="right")
        if diff is None:
            for ci in (3, 4): fill(ws.cell(r, ci), YELLOW_BG, YELLOW_FG, bold=True)
        elif diff < 0:
            for ci in (3, 4): fill(ws.cell(r, ci), RED_BG, RED_FG, bold=True)
        elif diff > 0:
            for ci in (3, 4): fill(ws.cell(r, ci), GREEN_BG, GREEN_FG, bold=True)
        else:
            for ci in (2, 3, 4): fill(ws.cell(r, ci), GREY_BG, GREY_FG)
        r += 1
        # ทิศทาง
        ws.cell(r, 1, "สรุป"); ws.cell(r, 2, direction or "คำนวณไม่ได้")
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        fill(ws.cell(r, 1), "FFF7F8F9", bold=True)
        bg, fg = ((RED_BG, RED_FG) if (diff or 0) < 0 else
                  (GREEN_BG, GREEN_FG) if (diff or 0) > 0 else (GREY_BG, GREY_FG))
        if diff is None: bg, fg = YELLOW_BG, YELLOW_FG
        fill(ws.cell(r, 2), bg, fg, bold=True)
        for ci in (1, 2): ws.cell(r, ci).border = BOX
        r += 1
        # ปุ่มเปิดหลักฐาน — ข้อความสั้นตามข้อ 9
        ws.cell(r, 1, "เปิดหลักฐาน"); fill(ws.cell(r, 1), "FFF7F8F9", bold=True)
        for ci, (hl, txt) in enumerate([(d.get("hl_a"), "ดูร่าง พ.ร.บ."), (d.get("hl_b"), "ดู พ.ร.บ.")], 2):
            if hl:
                ws.cell(r, ci, f'=HYPERLINK("{hl}","{txt}")')
                fill(ws.cell(r, ci), "FFE8F0FE", "FF1A73E8", bold=True)
            else:
                ws.cell(r, ci, "(ไม่มีลิงก์)")
                fill(ws.cell(r, ci), YELLOW_BG, YELLOW_FG)
            ws.cell(r, ci).alignment = Alignment(horizontal="center")
            ws.cell(r, ci).border = BOX
        ws.cell(r, 1).border = BOX
        r += 2
    return ws


def copy_sheet_plain(src_ws, wb, title, hide=False):
    """คัดลอกชีตเดิมไว้เป็นหลักฐาน — ไม่ใส่สีเหลืองที่ใช้ mark แถว"""
    ws = wb.create_sheet(title)
    for row in src_ws.iter_rows():
        for c in row:
            if c.value is None: continue
            nc = ws.cell(c.row, c.column, c.value)
            if c.has_style:
                nc.font = c.font.copy(); nc.border = c.border.copy()
                nc.alignment = c.alignment.copy(); nc.number_format = c.number_format
                f = c.fill
                if f and f.fill_type == "solid" and f.fgColor and f.fgColor.rgb:
                    rgb = f.fgColor.rgb
                    # แทนเหลือง mark-row ด้วยฟ้าอ่อน (สงวนเหลืองไว้ให้ uncertain เท่านั้น)
                    if str(rgb).upper() == "FFFFF2CC":
                        rgb = "FFE8F0FE"
                    nc.fill = PatternFill("solid", fgColor=rgb)
    for k, v in src_ws.column_dimensions.items():
        if v.width: ws.column_dimensions[k].width = v.width
    ws.sheet_view.showGridLines = False
    if hide: ws.sheet_state = "hidden"
    return ws
