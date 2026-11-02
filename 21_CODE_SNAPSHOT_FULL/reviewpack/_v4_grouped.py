# -*- coding: utf-8 -*-
"""reviewpack v1.4.0 — จัดกลุ่มตามหน่วยงาน/แผนงาน + ผลรวมรายชั้น

ขึ้นรุ่นใหม่เพราะ v1.3.1 = FROZEN INSTRUMENT BASELINE (ห้ามแก้ไฟล์เดิม)
แก้เฉพาะ presentation layer — ไม่แตะ finding · จำนวนเงิน · canonical values · source hashes
คำตอบที่ผู้วิจัยกรอกไว้ 21/21 ต้องย้ายครบทุกรายการ
"""
import hashlib, json, datetime, sys
from pathlib import Path
from collections import OrderedDict
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).parent))
from build_review_v3 import (
    RED_BG, RED_FG, GREEN_BG, GREEN_FG, GREY_BG, GREY_FG,
    YELLOW_BG, YELLOW_FG, HDR_BG, HDR_FG, BAND_BG,
    DIR_DOWN, DIR_UP, DIR_SAME, MATCH_OK, VERDICTS, OPENED,
    sha256, read_source, build_evidence_comparison, copy_sheet_plain,
    force_text_cells, fill, direction_of,
)

VERSION = "reviewpack-1.4.0"
from _paths import human_review_dir

# 🔴 ไม่มีเส้นทางส่วนบุคคลในซอร์ส — ดู _paths.py · ไม่ตั้ง env จะหยุดพร้อมข้อความ
SRC = human_review_dir(1) / "HUMAN_CHECK_SAMPLE_primary_R1_WORKING_v1.3.1.xlsx"
OUT = SRC.with_name("HUMAN_CHECK_SAMPLE_primary_R1_WORKING_v1.4.0.xlsx")
REPORT = SRC.with_name("MIGRATION_REPORT_v1.4.0.md")

AGENCY_BG = "FFDCE6F1"; AGENCY_FG = "FF1F3864"      # แถบหัวหน่วยงาน
PLAN_BG = "FFEDF2F8"; PLAN_FG = "FF2F5496"          # แถบหัวแผนงาน
SUB_BG = "FFF2F2F2"                                  # แถวผลรวมย่อย
TOTAL_BG = "FFD9E2F3"                                # แถวผลรวมใหญ่
THIN = Side(style="thin", color="FFD0D7E2")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

COLS = [
    ("ลำดับ", 6), ("รหัสรายการตรวจ", 13), ("สถานะการจับคู่", 14),
    ("กิจกรรม", 30), ("หมวดรายจ่าย", 13), ("ประเภทรายจ่าย", 20),
    ("ลักษณะรายจ่าย", 13), ("ชื่อรายการ", 22),
    ("จำนวนเงินตามร่าง พ.ร.บ. 2569 (บาท)", 21),
    ("จำนวนเงินตาม พ.ร.บ. 2569 (บาท)", 21),
    ("ผลต่าง (บาท)", 17), ("ทิศทาง", 17),
    ("เปิดหลักฐานฝั่งร่าง", 15), ("เปิดหลักฐานฝั่ง พ.ร.บ.", 15),
    ("คำตัดสินผู้วิจัย", 14), ("เหตุผล/หมายเหตุ", 34), ("สถานะความครบถ้วน", 18),
]
C_A, C_B, C_D, C_DIR = 9, 10, 11, 12          # คอลัมน์เงิน/ผลต่าง/ทิศทาง
C_OA, C_OB, C_V, C_R, C_ST = 13, 14, 15, 16, 17


def read_v131(src):
    """อ่านข้อมูลจาก layout ของ v1.3.1 (คนละตำแหน่งคอลัมน์กับ v1.2.0)
    Review: A ลำดับ · B รหัส · D หน่วยงาน · E แผนงาน · F ผลผลิต · G กิจกรรม ·
            H หมวด · I ประเภท · J ลักษณะ · K ชื่อรายการ · L เงินA · M เงินB ·
            P เปิดA · Q เปิดB · R คำตัดสิน · S เหตุผล"""
    import re as _re
    wb = openpyxl.load_workbook(src)
    rv = wb["Review"]
    loc = wb["ตำแหน่งตรวจสอบต้นทาง"]
    ec = wb["Evidence Comparison"] if "Evidence Comparison" in wb.sheetnames else None
    key = {loc.cell(r, 1).value: loc.cell(r, 10).value
           for r in range(5, loc.max_row + 1) if loc.cell(r, 1).value}
    # ลิงก์หลักฐานอยู่ในหน้า Evidence Comparison ของ v1.3.1
    links = {}
    if ec is not None:
        cur = None
        for r in range(1, ec.max_row + 1):
            v = str(ec.cell(r, 1).value or "")
            m = _re.match(r"^(P-\d+)", v)
            if m:
                cur = m.group(1); links[cur] = [None, None]
            elif v.strip() == "เปิดหลักฐาน" and cur:
                for ci, idx in ((2, 0), (3, 1)):
                    cv = str(ec.cell(r, ci).value or "")
                    mm = _re.match(r'=HYPERLINK\("([^"]+)"', cv)
                    if mm: links[cur][idx] = mm.group(1)
    out = []
    for r in range(5, rv.max_row + 1):
        fid = rv.cell(r, 2).value
        if not str(fid or "").startswith("P-"):
            continue
        hl = links.get(fid, [None, None])
        out.append({
            "seq": rv.cell(r, 1).value, "fid": fid,
            "agency": rv.cell(r, 4).value, "plan": rv.cell(r, 5).value,
            "output": rv.cell(r, 6).value, "activity": rv.cell(r, 7).value,
            "cat": rv.cell(r, 8).value, "subcat": rv.cell(r, 9).value,
            "nature": rv.cell(r, 10).value, "item": rv.cell(r, 11).value,
            "amt_a": rv.cell(r, 12).value, "amt_b": rv.cell(r, 13).value,
            "opened_a": rv.cell(r, 16).value, "opened_b": rv.cell(r, 17).value,
            "verdict": rv.cell(r, 18).value, "reason": rv.cell(r, 19).value,
            "canon_key": key.get(fid), "hl_a": hl[0], "hl_b": hl[1],
        })
    return wb, out


def money(c, fmt='#,##0'):
    c.number_format = fmt
    c.alignment = Alignment(horizontal="right", vertical="top")


def paint_direction(ws, r, diff, bold=True):
    """ลงสีตามกติกา RES: ลด=แดง · เพิ่ม=เขียว · เท่ากัน=เทา · คำนวณไม่ได้=เหลือง"""
    if diff is None:
        bg, fg = YELLOW_BG, YELLOW_FG
    elif diff < 0:
        bg, fg = RED_BG, RED_FG
    elif diff > 0:
        bg, fg = GREEN_BG, GREEN_FG
    else:
        bg, fg = GREY_BG, GREY_FG
    for ci in (C_B, C_D, C_DIR):
        fill(ws.cell(r, ci), bg, fg, bold=bold)


def build_grouped_review(wb, rows):
    ws = wb.create_sheet("Review", 1)
    ws.sheet_view.showGridLines = False
    ws["A1"] = "หน้าตรวจหลัก — แยกตามหน่วยงานและแผนงาน พร้อมผลรวมรายชั้น"
    fill(ws["A1"], bold=True, size=14, fg="FF1F3864")
    ws["A2"] = ("ผลต่าง = จำนวนเงินตาม พ.ร.บ. − จำนวนเงินตามร่าง พ.ร.บ.  ·  "
                "ค่าติดลบ = วงเงินลดลง (แดง) · ค่าบวก = วงเงินเพิ่มขึ้น (เขียว) · ศูนย์ = ไม่เปลี่ยนแปลง (เทา)")
    fill(ws["A2"], fg=GREY_FG)
    ws["A3"] = "สีเหลืองสงวนไว้เฉพาะรายการที่ต้องวินิจฉัยเพิ่ม · แถวผลรวมคำนวณด้วยสูตร ปรับตามค่าจริงเสมอ"
    fill(ws["A3"], fg=YELLOW_FG)

    hr = 4
    for i, (name, w) in enumerate(COLS, 1):
        c = ws.cell(hr, i, name)
        fill(c, HDR_BG, HDR_FG, bold=True)
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        c.border = BOX
        ws.column_dimensions[L(i)].width = w
    ws.row_dimensions[hr].height = 44

    # จัดกลุ่ม หน่วยงาน → แผนงาน → ผลผลิต/โครงการ (คงลำดับเดิมของข้อมูล)
    tree = OrderedDict()
    for d in rows:
        tree.setdefault(d["agency"], OrderedDict()).setdefault(d["plan"], []).append(d)

    r = hr + 1
    agency_total_rows = []
    for agency, plans in tree.items():
        n_ag = sum(len(v) for v in plans.values())
        ag_start = r
        # ── แถบหัวหน่วยงาน ──
        ws.cell(r, 1, f"■  {agency}")
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        fill(ws.cell(r, 1), AGENCY_BG, AGENCY_FG, bold=True, size=12)
        ws.cell(r, 1).alignment = Alignment(vertical="center")
        ws.cell(r, C_ST, f"{n_ag} รายการ")
        for ci in range(1, len(COLS) + 1):
            ws.cell(r, ci).border = BOX
            if ci > 8:
                fill(ws.cell(r, ci), AGENCY_BG, AGENCY_FG, bold=True)
        ws.row_dimensions[r].height = 22
        r += 1

        plan_total_rows = []
        for plan, items in plans.items():
            # ── แถบหัวแผนงาน ──
            ws.cell(r, 1, f"    ▸ {plan}")
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
            fill(ws.cell(r, 1), PLAN_BG, PLAN_FG, bold=True)
            ws.cell(r, C_ST, f"{len(items)} รายการ")
            for ci in range(1, len(COLS) + 1):
                ws.cell(r, ci).border = BOX
                if ci > 8:
                    fill(ws.cell(r, ci), PLAN_BG, PLAN_FG, bold=True)
            r += 1

            first_item = r
            for i, d in enumerate(items):
                diff, direction = direction_of(d["amt_a"], d["amt_b"])
                band = BAND_BG if i % 2 else None
                vals = [d["seq"], d["fid"], MATCH_OK, d["activity"], d["cat"], d["subcat"],
                        d["nature"], d["item"], d["amt_a"], d["amt_b"], diff, direction,
                        d["opened_a"], d["opened_b"], d["verdict"], d["reason"], None]
                for ci, v in enumerate(vals, 1):
                    c = ws.cell(r, ci, v)
                    c.border = BOX
                    c.alignment = Alignment(wrap_text=True, vertical="top")
                    if band:
                        fill(c, band)
                money(ws.cell(r, C_A)); money(ws.cell(r, C_B))
                money(ws.cell(r, C_D), '+#,##0;−#,##0;0')
                paint_direction(ws, r, diff)
                ws.cell(r, C_DIR).alignment = Alignment(horizontal="center", vertical="center")
                fill(ws.cell(r, 3), GREEN_BG, GREEN_FG, bold=True)
                ws.cell(r, 3).alignment = Alignment(horizontal="center", vertical="center")
                ws.cell(r, C_ST, f'=IF({L(C_V)}{r}="","ยังไม่ได้ตอบ",'
                                 f'IF(AND({L(C_OA)}{r}="เปิดแล้ว",{L(C_OB)}{r}="เปิดแล้ว"),'
                                 f'"ครบแล้ว","ตอบแล้ว แต่ยังไม่ได้ยืนยันว่าเปิดหลักฐานครบสองฝั่ง"))')
                fill(ws.cell(r, C_ST), band)
                r += 1
            last_item = r - 1

            # ── ผลรวมแผนงาน ──
            ws.cell(r, 1, "        รวมแผนงาน")
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
            fill(ws.cell(r, 1), SUB_BG, bold=True)
            ws.cell(r, 1).alignment = Alignment(horizontal="right", vertical="center")
            for ci, col in ((C_A, C_A), (C_B, C_B), (C_D, C_D)):
                ws.cell(r, ci, f"=SUM({L(col)}{first_item}:{L(col)}{last_item})")
            money(ws.cell(r, C_A)); money(ws.cell(r, C_B))
            money(ws.cell(r, C_D), '+#,##0;−#,##0;0')
            pdiff = sum((x["amt_b"] or 0) - (x["amt_a"] or 0) for x in items)
            ws.cell(r, C_DIR, DIR_DOWN if pdiff < 0 else DIR_UP if pdiff > 0 else DIR_SAME)
            ws.cell(r, C_DIR).alignment = Alignment(horizontal="center", vertical="center")
            for ci in range(1, len(COLS) + 1):
                ws.cell(r, ci).border = BOX
                if ci not in (C_A, C_B, C_D, C_DIR):
                    fill(ws.cell(r, ci), SUB_BG)
            paint_direction(ws, r, pdiff)
            plan_total_rows.append(r)
            r += 1

        # ── ผลรวมหน่วยงาน ──
        ws.cell(r, 1, f"    รวม {agency}")
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        fill(ws.cell(r, 1), TOTAL_BG, AGENCY_FG, bold=True, size=11)
        ws.cell(r, 1).alignment = Alignment(horizontal="right", vertical="center")
        for col in (C_A, C_B, C_D):
            ws.cell(r, col, "=" + "+".join(f"{L(col)}{x}" for x in plan_total_rows))
        money(ws.cell(r, C_A)); money(ws.cell(r, C_B))
        money(ws.cell(r, C_D), '+#,##0;−#,##0;0')
        adiff = sum((x["amt_b"] or 0) - (x["amt_a"] or 0)
                    for pl in plans for x in plans[pl])
        ws.cell(r, C_DIR, DIR_DOWN if adiff < 0 else DIR_UP if adiff > 0 else DIR_SAME)
        ws.cell(r, C_DIR).alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(r, C_ST, f"{n_ag} รายการ")
        for ci in range(1, len(COLS) + 1):
            ws.cell(r, ci).border = BOX
            if ci not in (C_A, C_B, C_D, C_DIR):
                fill(ws.cell(r, ci), TOTAL_BG, AGENCY_FG, bold=True)
        paint_direction(ws, r, adiff)
        ws.row_dimensions[r].height = 20
        agency_total_rows.append(r)
        r += 2   # เว้นบรรทัดคั่นระหว่างหน่วยงาน

    # ── ผลรวมทั้งสองหน่วยงาน ──
    ws.cell(r, 1, "รวมทั้งสองหน่วยงาน")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    fill(ws.cell(r, 1), HDR_BG, HDR_FG, bold=True, size=12)
    ws.cell(r, 1).alignment = Alignment(horizontal="right", vertical="center")
    for col in (C_A, C_B, C_D):
        ws.cell(r, col, "=" + "+".join(f"{L(col)}{x}" for x in agency_total_rows))
    money(ws.cell(r, C_A)); money(ws.cell(r, C_B))
    money(ws.cell(r, C_D), '+#,##0;−#,##0;0')
    gdiff = sum((d["amt_b"] or 0) - (d["amt_a"] or 0) for d in rows)
    ws.cell(r, C_DIR, DIR_DOWN if gdiff < 0 else DIR_UP if gdiff > 0 else DIR_SAME)
    ws.cell(r, C_DIR).alignment = Alignment(horizontal="center", vertical="center")
    ws.cell(r, C_ST, f"{len(rows)} รายการ")
    for ci in range(1, len(COLS) + 1):
        ws.cell(r, ci).border = BOX
        fill(ws.cell(r, ci), HDR_BG, HDR_FG, bold=True)
    ws.row_dimensions[r].height = 22
    grand_row = r

    ws.freeze_panes = "A5"
    dv_v = DataValidation(type="list", formula1='"' + ",".join(VERDICTS) + '"', allow_blank=True)
    dv_o = DataValidation(type="list", formula1='"' + ",".join(OPENED) + '"', allow_blank=True)
    ws.add_data_validation(dv_v); ws.add_data_validation(dv_o)
    dv_v.add(f"{L(C_V)}5:{L(C_V)}{grand_row}")
    dv_o.add(f"{L(C_OA)}5:{L(C_OA)}{grand_row}")
    dv_o.add(f"{L(C_OB)}5:{L(C_OB)}{grand_row}")
    return ws, tree


def build_summary(wb, rows, tree):
    ws = wb.create_sheet("Summary", 0)
    ws.sheet_view.showGridLines = False
    ws["A1"] = "สรุปผลรายหน่วยงานและรายแผนงาน — Primary Case Review รอบที่ 1"
    fill(ws["A1"], bold=True, size=15, fg="FF1F3864")
    ws["A2"] = f"{VERSION} · คู่ร่าง พ.ร.บ. 2569 ↔ พ.ร.บ. 2569 · {len(rows)} รายการ"
    fill(ws["A2"], fg=GREY_FG)
    for col, w in (("A", 46), ("B", 8), ("C", 18), ("D", 18), ("E", 16), ("F", 17)):
        ws.column_dimensions[col].width = w

    r = 4
    for h, ci in (("หน่วยงาน / แผนงาน", 1), ("รายการ", 2),
                  ("ร่าง พ.ร.บ. 2569 (บาท)", 3), ("พ.ร.บ. 2569 (บาท)", 4),
                  ("ผลต่าง (บาท)", 5), ("ทิศทาง", 6)):
        c = ws.cell(r, ci, h)
        fill(c, HDR_BG, HDR_FG, bold=True)
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
        c.border = BOX
    ws.row_dimensions[r].height = 32
    r += 1

    def put(row, label, n, a, b, style_bg, style_fg, bold, indent=0):
        ws.cell(row, 1, ("    " * indent) + label)
        ws.cell(row, 2, n)
        ws.cell(row, 3, a); ws.cell(row, 4, b); ws.cell(row, 5, b - a)
        d = b - a
        ws.cell(row, 6, DIR_DOWN if d < 0 else DIR_UP if d > 0 else DIR_SAME)
        for ci in range(1, 7):
            ws.cell(row, ci).border = BOX
            fill(ws.cell(row, ci), style_bg, style_fg, bold=bold)
        ws.cell(row, 2).alignment = Alignment(horizontal="center")
        for ci in (3, 4, 5):
            ws.cell(row, ci).number_format = '#,##0' if ci < 5 else '+#,##0;−#,##0;0'
            ws.cell(row, ci).alignment = Alignment(horizontal="right")
        ws.cell(row, 6).alignment = Alignment(horizontal="center")
        if d < 0:
            for ci in (4, 5, 6): fill(ws.cell(row, ci), RED_BG, RED_FG, bold=True)
        elif d > 0:
            for ci in (4, 5, 6): fill(ws.cell(row, ci), GREEN_BG, GREEN_FG, bold=True)

    for agency, plans in tree.items():
        items_all = [x for pl in plans for x in plans[pl]]
        put(r, agency, len(items_all),
            sum(x["amt_a"] for x in items_all), sum(x["amt_b"] for x in items_all),
            AGENCY_BG, AGENCY_FG, True)
        r += 1
        for plan, items in plans.items():
            put(r, plan, len(items),
                sum(x["amt_a"] for x in items), sum(x["amt_b"] for x in items),
                "FFFFFFFF", None, False, indent=1)
            r += 1
        r += 1

    put(r, "รวมทั้งสองหน่วยงาน", len(rows),
        sum(x["amt_a"] for x in rows), sum(x["amt_b"] for x in rows),
        TOTAL_BG, AGENCY_FG, True)
    grand = r
    r += 3

    # ── ความคืบหน้าการตรวจ ──
    ws.cell(r, 1, "ความคืบหน้าการตรวจ"); fill(ws.cell(r, 1), bold=True, size=12, fg="FF1F3864")
    r += 1
    rv_last = 4 + 1 + sum(1 + len(pl) + 1 for ag in tree.values() for pl in [ag]) + 200
    prog = [("กรอกแล้ว (มีคำตัดสิน)", f'=COUNTA(Review!{L(C_V)}5:{L(C_V)}{rv_last})-COUNTBLANK(Review!{L(C_V)}5:{L(C_V)}{rv_last})*0'),
            ("ยืนยัน", f'=COUNTIF(Review!{L(C_V)}5:{L(C_V)}{rv_last},"ยืนยัน")'),
            ("ไม่ยืนยัน", f'=COUNTIF(Review!{L(C_V)}5:{L(C_V)}{rv_last},"ไม่ยืนยัน")'),
            ("ไม่แน่ใจ", f'=COUNTIF(Review!{L(C_V)}5:{L(C_V)}{rv_last},"ไม่แน่ใจ")')]
    for lab, f in prog:
        ws.cell(r, 1, lab); ws.cell(r, 2, f)
        ws.cell(r, 2).alignment = Alignment(horizontal="center")
        for ci in (1, 2): ws.cell(r, ci).border = BOX
        if lab == "ไม่แน่ใจ":
            for ci in (1, 2): fill(ws.cell(r, ci), YELLOW_BG, YELLOW_FG)
        r += 1
    r += 2

    ws.cell(r, 1, "คำอธิบายสี"); fill(ws.cell(r, 1), bold=True, size=12, fg="FF1F3864")
    r += 1
    for lab, desc, bg, fg in (
            (DIR_DOWN, "วงเงินตาม พ.ร.บ. ต่ำกว่าร่าง พ.ร.บ.", RED_BG, RED_FG),
            (DIR_UP, "วงเงินตาม พ.ร.บ. สูงกว่าร่าง พ.ร.บ.", GREEN_BG, GREEN_FG),
            (DIR_SAME, "วงเงินทั้งสองฝั่งเท่ากัน", GREY_BG, GREY_FG),
            ("สีเหลือง", "สงวนไว้เฉพาะรายการที่ต้องวินิจฉัยเพิ่ม", YELLOW_BG, YELLOW_FG)):
        fill(ws.cell(r, 1, lab), bg, fg, bold=True)
        ws.cell(r, 3, desc)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
        r += 1
    return ws, grand
