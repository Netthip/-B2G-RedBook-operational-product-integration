# -*- coding: utf-8 -*-
"""เขียนสมุดงาน Human Review รุ่น `review-schema-1.2.0`

หกชีต: วิธีตรวจ · Review · Evidence Preview · ตำแหน่งตรวจสอบต้นทาง ·
Technical Details · ตัวเลือก

ข้อบังคับที่โค้ดนี้ยึด (มีชุดทดสอบกำกับใน `tests/test_reviewpack_v2.py`):
  - ห้าม merge cell ในตารางข้อมูล (merge ได้เฉพาะแถบหัวเรื่องเหนือหัวตาราง)
  - ค่าลำดับชั้นต้องอยู่ครบทุกแถว — sort/filter แล้วบริบทไม่หาย
  - ช่องของผู้วิจัยต้องว่างตอนสร้าง
  - สูตรเดียวที่อนุญาตคือ `=HYPERLINK(...)` ซึ่งเป็นการนำทาง ไม่แก้ค่าผลตรวจ
"""
from pathlib import Path

import openpyxl
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .review_layout_v2 import (BOX, CONFIDENCE_CHOICES, EVIDENCE_OPENED_CHOICES,
                               GROUP_BREAK_FIELDS, GROUP_TOP, HEADER_ROW,
                               HEAD_A_FILL, HEAD_B_FILL, HIERARCHY_GROUP,
                               KEY_ROLES, LEGEND_MATCH, LEGEND_MONEY,
                               MATCHING_NOTE, NO_DATA, REVIEW_COLUMNS,
                               REVIEWER_FIELDS, REVIEW_SCHEMA_VERSION,
                               SCOPE_BANNER, SIDE_A_DOCSTATE, SIDE_A_SHORT,
                               SIDE_A_TITLE, SIDE_B_DOCSTATE, SIDE_B_SHORT,
                               SIDE_B_TITLE, VERDICT_CHOICES, VERDICT_STYLE,
                               hyperlink_formula)

MONEY_FMT = "#,##0"
DIFF_FMT = '"+"#,##0;"-"#,##0;0'

COL_INDEX = {k: i for i, (k, _, _, _) in enumerate(REVIEW_COLUMNS, start=1)}
COL_LETTER = {k: get_column_letter(i) for k, i in COL_INDEX.items()}


def _guide_sheet(wb, meta):
    ws = wb.create_sheet("วิธีตรวจ", 0)
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 96

    def line(b="", c="", bold=False, size=11, color=None, fill=None):
        ws.append(["", b, c])
        r = ws.max_row
        for col in ("B", "C"):
            cell = ws[col + str(r)]
            cell.font = Font(b=bold, size=size, color=color)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        if fill:
            ws["B" + str(r)].fill = PatternFill("solid", fgColor=fill)
            ws["B" + str(r)].border = BOX
        return r

    line("วิธีตรวจ — Primary Case Review รอบที่ 1", "", bold=True, size=15)
    line("", SCOPE_BANNER + " · 21 รายการ ตรวจทั้งหมด")
    line("", "แบบฟอร์ม " + meta["reviewpack_version"] + " · " + REVIEW_SCHEMA_VERSION
         + " · เวอร์ชันที่ freeze: " + meta["versions"])
    line("", "สิ่งที่กำลังตรวจ: ผลที่ระบบรายงานตรงกับหลักฐานในเอกสารต้นทางหรือไม่ — "
             "ไม่ใช่การตรวจว่างบประมาณถูกหรือผิด และไม่ตัดสินสาเหตุของการเปลี่ยนแปลง")
    line()

    line("ทำทีละแถวในชีต Review", "", bold=True, size=13)
    steps = [
        ("1", "เปิดหลักฐานฝั่ง " + SIDE_A_SHORT + " จากคอลัมน์ “ตำแหน่งหลักฐาน — "
              + SIDE_A_SHORT + "” (กดที่ข้อความเพื่อเปิดไฟล์ต้นทางที่เซลล์นั้น "
              "หรือดูบริบทในชีต Evidence Preview)"),
        ("2", "ตรวจว่าจำนวนเงินฝั่ง " + SIDE_A_SHORT + " ตรงกับที่ฟอร์มแสดง "
              "แล้วเลือก “เปิดแล้ว”"),
        ("3", "เปิดหลักฐานฝั่ง " + SIDE_B_SHORT + " ด้วยวิธีเดียวกัน"),
        ("4", "ตรวจจำนวนเงินฝั่ง " + SIDE_B_SHORT + " แล้วเลือก “เปิดแล้ว”"),
        ("5", "ดูว่าหมวด C1–C7 ที่ระบบให้ (ชีต Technical Details คอลัมน์ "
              "“หมวดผลตรวจ”) สอดคล้องกับหลักฐานหรือไม่ — ทิศทางเงินในชีต Review "
              "คือหมวดเดียวกันในรูปแบบที่อ่านง่าย"),
        ("6", "เลือกคำตัดสินของผู้วิจัย: ยืนยัน / ไม่ยืนยัน / ไม่แน่ใจ"),
        ("7", "เขียนเหตุผลสั้น ๆ เฉพาะรายการที่เลือก “ไม่ยืนยัน” หรือ “ไม่แน่ใจ” "
              "แล้วกรอกวันเวลาที่ตรวจ"),
    ]
    for n, t in steps:
        line(n, t)
    line()

    line("เกณฑ์การเลือกคำตัดสิน", "", bold=True, size=13)
    for v, t in [("ยืนยัน", "ค่าสองฝั่งตรงกับหลักฐาน และหมวดที่ระบบให้สอดคล้องกับค่าที่เห็น"),
                 ("ไม่ยืนยัน", "ค่าไม่ตรงกับหลักฐาน หรือหมวดไม่สอดคล้องกับหลักฐาน"),
                 ("ไม่แน่ใจ", "เปิดหลักฐานแล้วยังสรุปไม่ได้ — ระบุในช่องเหตุผลว่าติดตรงไหน")]:
        fill, font, bold, italic = VERDICT_STYLE[v]
        r = line(v, t, fill=fill)
        ws["B" + str(r)].font = Font(b=bold, i=italic, color=font)
    line()

    line("คำอธิบายสี — ทิศทางของจำนวนเงิน", "", bold=True, size=13)
    for label, fill, font, desc in LEGEND_MONEY:
        r = line(label, desc, fill=fill)
        ws["B" + str(r)].font = Font(b=True, color=font)
    line("", "สีของจำนวนเงินบอก “ทิศทาง” เท่านั้น ไม่ได้บอกว่าเอกสารถูกหรือผิด")
    line()

    line("คำอธิบายสัญลักษณ์ — สถานะการจับคู่", "", bold=True, size=13)
    for label, font, desc in LEGEND_MATCH:
        r = line(label, desc)
        ws["B" + str(r)].font = Font(b=True, color=font)
        ws["B" + str(r)].border = BOX
    line("", MATCHING_NOTE + " · ไม่ใช้คำว่า “ผ่าน/ไม่ผ่าน” กับสถานะการจับคู่")
    line()

    line("สามสถานะที่ต้องไม่ปนกัน", "", bold=True, size=13)
    line("1. สถานะการจับคู่", "ระบบเชื่อมรายการสองฝั่งได้หรือไม่ — แสดงเป็นสัญลักษณ์ "
         "✓ ✕ ? ⚠ บนพื้นขาวมีกรอบ")
    line("2. ทิศทางของจำนวนเงิน", "เงินลด เพิ่ม เท่าเดิม หรือคำนวณไม่ได้ — "
         "แสดงเป็นสีพื้นหลังของเซลล์จำนวนเงิน")
    line("3. คำตัดสินของผู้วิจัย", "กิ๊ฟยืนยัน ไม่ยืนยัน หรือไม่แน่ใจ — "
         "แสดงเป็นสีโทนน้ำเงิน/ม่วงในคอลัมน์คำตัดสิน")
    line()

    line("ข้อควรระวัง", "", bold=True, size=13)
    line("บันทึกงาน", "กด Ctrl+S ทุกครั้งที่กรอกเสร็จ 2–3 รายการ — "
         "Excel ไม่บันทึกให้เองตอนปิดไฟล์")
    line("ไฟล์ต้นทาง", "เปิดแบบอ่านอย่างเดียว ห้ามแก้ไขหรือบันทึกทับ "
         "เพราะ SHA-256 ของไฟล์ต้นทางเป็นหลักฐานของงานวิจัย")
    line("รอบที่ 2", "ยังไม่สร้าง — จะสร้างหลังรอบที่ 1 เสร็จอย่างน้อย 1 วัน "
         "ด้วย seed ใหม่ และไม่แสดงคำตอบรอบแรก")
    line("ระบบ e-Budget", "ชีต “ตำแหน่งตรวจสอบต้นทาง” ช่วยให้ค้นรายการเดียวกันในระบบ "
         "e-Budget ได้เร็วขึ้นเท่านั้น — ระบบนี้ไม่ได้เชื่อมต่อหรือแก้ไข e-Budget "
         "โดยอัตโนมัติ")
    return ws


def _write_header(ws, meta, n_rows):
    ws.append([SCOPE_BANNER])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(REVIEW_COLUMNS))
    c = ws.cell(row=1, column=1)
    c.font = Font(b=True, size=12, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor="B92F35")
    c.alignment = Alignment(horizontal="center", vertical="center")

    ws.append(["แบบฟอร์ม " + meta["reviewpack_version"] + " · " + REVIEW_SCHEMA_VERSION
               + " · เวอร์ชันที่ freeze: " + meta["versions"]
               + " · สร้างเมื่อ " + meta["generated_at"]
               + " · คำแนะนำอยู่ที่ชีต “วิธีตรวจ”"])
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(REVIEW_COLUMNS))
    ws.cell(row=2, column=1).font = Font(size=9, italic=True)

    legend = ("สถานะการจับคู่: " + " · ".join(l[0] for l in LEGEND_MATCH)
              + "  ( " + MATCHING_NOTE + " )    |    ทิศทางเงิน: "
              + " · ".join(l[0] for l in LEGEND_MONEY))
    ws.append([legend])
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=len(REVIEW_COLUMNS))
    c = ws.cell(row=3, column=1)
    c.font = Font(size=9)
    c.fill = PatternFill("solid", fgColor="F7F8FA")
    c.alignment = Alignment(vertical="center")

    for key, title, width, wrap in REVIEW_COLUMNS:
        ws.cell(row=HEADER_ROW, column=COL_INDEX[key], value=title)
    for key, title, width, wrap in REVIEW_COLUMNS:
        cell = ws.cell(row=HEADER_ROW, column=COL_INDEX[key])
        fill = "F1F3F5"
        if key in ("amount_a", "evidence_a_text", "evidence_opened_a"):
            fill = HEAD_A_FILL
        elif key in ("amount_b", "evidence_b_text", "evidence_opened_b"):
            fill = HEAD_B_FILL
        cell.font = Font(b=True, size=10)
        cell.fill = PatternFill("solid", fgColor=fill)
        cell.alignment = Alignment(wrap_text=True, vertical="center",
                                   horizontal="center")
        cell.border = BOX
        ws.column_dimensions[COL_LETTER[key]].width = width
    ws.row_dimensions[HEADER_ROW].height = 46


def _hierarchy_styles(ws, r, rec, prev):
    """visual hierarchy — แผนงานเข้มสุด ผลผลิตรอง กิจกรรมพื้นอ่อน รายการอ่านง่าย"""
    levels = [
        ("plan_name", "DDE3EC", True),
        ("output_name", "E8ECF2", True),
        ("activity_name", "F2F4F7", False),
    ]
    for key, fill, bold in levels:
        cell = ws.cell(row=r, column=COL_INDEX[key])
        cell.fill = PatternFill("solid", fgColor=fill)
        cell.font = Font(b=bold, size=10)
    ws.cell(row=r, column=COL_INDEX["item_label"]).font = Font(size=11, b=True)
    ws.cell(row=r, column=COL_INDEX["agency_display"]).font = Font(b=True, size=10)

    # เส้นแบ่งกลุ่มเมื่อระดับบนเปลี่ยน — ค่ายังอยู่ครบทุกแถว ไม่ merge
    if prev is not None and any(rec[f] != prev[f] for f in GROUP_BREAK_FIELDS):
        for col in range(1, len(REVIEW_COLUMNS) + 1):
            cur = ws.cell(row=r, column=col).border
            ws.cell(row=r, column=col).border = Border(
                left=cur.left, right=cur.right, bottom=cur.bottom, top=GROUP_TOP)


def _review_sheet(wb, records, meta, sources):
    ws = wb.create_sheet("Review")
    _write_header(ws, meta, len(records))

    first = HEADER_ROW + 1
    prev = None
    for i, rec in enumerate(records):
        r = first + i
        for key, title, width, wrap in REVIEW_COLUMNS:
            col = COL_INDEX[key]
            value = rec.get(key, "")
            cell = ws.cell(row=r, column=col)
            if key in ("evidence_a_text", "evidence_b_text"):
                side = "a" if key.endswith("a_text") else "b"
                path = sources.get(rec["file_%s_name" % side])
                sheet = rec["sheet_%s" % side]
                ref = rec["cell_%s" % side]
                if path and ref:
                    cell.value = hyperlink_formula(path, sheet, ref, value)
                    cell.font = Font(color="0F4C81", underline="single", size=10)
                else:
                    cell.value = value
            else:
                cell.value = value
            cell.alignment = Alignment(wrap_text=wrap, vertical="top",
                                       horizontal="center" if key in
                                       ("order_no", "count_unit") else "left")
            cell.border = BOX

        # ---- แกนที่ 1: สถานะการจับคู่ (สัญลักษณ์ + สีตัวอักษร บนพื้นขาว มีกรอบ)
        mc = ws.cell(row=r, column=COL_INDEX["matching_status"])
        mc.font = Font(b=True, color=rec["matching_color"], size=10)
        mc.fill = PatternFill("solid", fgColor="FFFFFF")
        mc.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")

        _hierarchy_styles(ws, r, rec, prev)

        # ---- แกนที่ 2: ทิศทางของจำนวนเงิน (สีพื้นหลังของเซลล์เงิน)
        fill = PatternFill("solid", fgColor=rec["direction_fill"])
        for key in ("amount_a", "amount_b", "amount_diff"):
            cell = ws.cell(row=r, column=COL_INDEX[key])
            cell.number_format = DIFF_FMT if key == "amount_diff" else MONEY_FMT
            cell.alignment = Alignment(horizontal="right", vertical="top")
        changed_side = {"▲": "amount_b", "▼": "amount_b"}.get(rec["direction"][0])
        targets = ["amount_diff", "direction"]
        if changed_side:
            targets.append(changed_side)
        if rec["direction"].startswith("?"):
            targets += ["amount_a", "amount_b"]
        for key in targets:
            ws.cell(row=r, column=COL_INDEX[key]).fill = fill
        dcell = ws.cell(row=r, column=COL_INDEX["direction"])
        dcell.font = Font(b=True, color=rec["direction_font"], size=10)
        dcell.alignment = Alignment(wrap_text=True, vertical="center",
                                    horizontal="center")

        # ---- ธงเตือนเมื่อค่าดิบไม่ตรงกับค่าที่ระบบใช้
        vc = ws.cell(row=r, column=COL_INDEX["value_consistency"])
        vc.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        if rec["value_consistency"].startswith("⚠"):
            vc.font = Font(b=True, color="7A5B00", size=10)
            vc.fill = PatternFill("solid", fgColor="FFF3CD")
            if rec["value_consistency_note"]:
                from openpyxl.comments import Comment
                vc.comment = Comment(rec["value_consistency_note"], "RedBook Verify")
        else:
            vc.font = Font(color="6B7280", size=10)

        longest = max((len(str(rec.get(k, ""))) / max(w, 1)
                       for k, _, w, wrap in REVIEW_COLUMNS if wrap), default=1)
        ws.row_dimensions[r].height = max(34, min(120, 15 * (int(longest) + 1)))
        prev = rec

    last = first + len(records) - 1
    ws.freeze_panes = ws.cell(row=first, column=COL_INDEX["count_unit"])
    ws.auto_filter.ref = ("A%d:%s%d" % (HEADER_ROW,
                                        get_column_letter(len(REVIEW_COLUMNS)), last))

    for key in HIERARCHY_GROUP:      # ยุบ/ขยายกลุ่มลำดับชั้นได้
        dim = ws.column_dimensions[COL_LETTER[key]]
        dim.outlineLevel = 1
        dim.collapsed = False
    ws.sheet_properties.outlinePr.summaryRight = False

    # ---- dropdown ของช่องที่ผู้วิจัยกรอก
    def add_dv(choices, keys):
        dv = DataValidation(type="list", formula1='"' + ",".join(choices) + '"',
                            allow_blank=True, showDropDown=False)
        dv.error = "กรุณาเลือกจากรายการ: " + " / ".join(choices)
        dv.prompt = " / ".join(choices)
        ws.add_data_validation(dv)
        for k in keys:
            dv.add("%s%d:%s%d" % (COL_LETTER[k], first, COL_LETTER[k], last))

    add_dv(VERDICT_CHOICES, ["reviewer_verdict"])
    add_dv(CONFIDENCE_CHOICES, ["reviewer_confidence"])
    add_dv(EVIDENCE_OPENED_CHOICES, ["evidence_opened_a", "evidence_opened_b"])

    # ---- แกนที่ 3: คำตัดสินของผู้วิจัย = conditional formatting โทนน้ำเงิน/ม่วง
    vcol = COL_LETTER["reviewer_verdict"]
    rng = "%s%d:%s%d" % (vcol, first, vcol, last)
    for verdict, (fill, font, bold, italic) in VERDICT_STYLE.items():
        ws.conditional_formatting.add(rng, FormulaRule(
            formula=['EXACT($%s%d,"%s")' % (vcol, first, verdict)],
            fill=PatternFill(start_color=fill, end_color=fill, fill_type="solid"),
            font=Font(b=bold, i=italic, color=font), stopIfTrue=False))
    return ws


def _evidence_preview_sheet(wb, records):
    ws = wb.create_sheet("Evidence Preview")
    ws.sheet_view.showGridLines = False
    headers = ["บริบท", "ฝั่ง/สถานะเอกสาร", "หน่วยงาน", "แผนงาน", "ผลผลิต/โครงการ",
               "กิจกรรม", "หมวดรายจ่าย", "ประเภทรายจ่าย", "ลักษณะรายจ่าย",
               "ชื่อรายการ", "จำนวนเงิน (บาท)", "ไฟล์", "ชีต", "แถว", "เซลล์",
               "SHA-256 ของไฟล์ต้นทาง"]
    widths = [12, 30, 26, 26, 28, 28, 16, 20, 14, 24, 18, 26, 8, 8, 10, 68]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.append(["บริบทหลักฐานที่คัดจากไฟล์สาธารณะ — แถวที่อ้างถึงพร้อมแถวก่อนหน้า/ถัดไป "
               "· ใช้เมื่อเปิดไฟล์ต้นทางโดยตรงไม่สะดวก"])
    ws.cell(row=1, column=1).font = Font(b=True, size=12)
    ws.append(["ข้อมูลนี้คัดลอกมาแสดงเพื่อการตรวจเท่านั้น "
               "ค่าทั้งหมดตรงกับไฟล์ต้นทางตามที่ระบุ SHA-256 ในคอลัมน์สุดท้าย"])
    ws.cell(row=2, column=1).font = Font(size=9, italic=True)

    for rec in records:
        ws.append([])
        ws.append(["%s  ·  %s  ·  %s" % (rec["sample_id"], rec["item_label"],
                                         rec["matching_status"])])
        tr = ws.max_row
        ws.cell(row=tr, column=1).font = Font(b=True, size=11, color="1F3864")
        ws.cell(row=tr, column=1).fill = PatternFill("solid", fgColor="EDF1F8")

        ws.append(headers)
        hr = ws.max_row
        for j in range(1, len(headers) + 1):
            cell = ws.cell(row=hr, column=j)
            cell.font = Font(b=True, size=9)
            cell.fill = PatternFill("solid", fgColor="F1F3F5")
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            cell.border = BOX

        for side, ctx, docstate, fname, sha, sheet, target in (
                ("a", rec["context_a"], SIDE_A_DOCSTATE, rec["file_a_name"],
                 rec["file_a_sha256"], rec["sheet_a"], rec["row_a"]),
                ("b", rec["context_b"], SIDE_B_DOCSTATE, rec["file_b_name"],
                 rec["file_b_sha256"], rec["sheet_b"], rec["row_b"])):
            for rn in sorted(ctx):
                vals = ctx[rn]
                is_target = (rn == target)
                label = ("► รายการนี้" if is_target
                         else ("ก่อนหน้า" if rn < (target or 0) else "ถัดไป"))
                cell_ref = ("M%d" % rn)
                ws.append([label, docstate, "%s %s" % (vals[2], vals[3]), vals[5],
                           vals[6], vals[7], vals[8], vals[9], vals[10], vals[11],
                           vals[12], fname, sheet, rn, cell_ref,
                           sha if is_target else ""])
                r = ws.max_row
                for j in range(1, len(headers) + 1):
                    c = ws.cell(row=r, column=j)
                    c.border = BOX
                    c.alignment = Alignment(wrap_text=True, vertical="top")
                    c.font = Font(size=9)
                ws.cell(row=r, column=11).number_format = MONEY_FMT
                ws.cell(row=r, column=11).alignment = Alignment(horizontal="right")
                if is_target:
                    for j in (6, 10, 11):        # กิจกรรม · ชื่อรายการ · จำนวนเงิน
                        c = ws.cell(row=r, column=j)
                        c.fill = PatternFill("solid", fgColor="FFF2CC")
                        c.font = Font(b=True, size=9)
                    ws.cell(row=r, column=1).font = Font(b=True, size=9, color="B45309")
                ws.row_dimensions[r].height = 30
    return ws


def _source_lookup_sheet(wb, records):
    ws = wb.create_sheet("ตำแหน่งตรวจสอบต้นทาง")
    ws.append(["ตำแหน่งสำหรับตรวจสอบต้นทาง — ใช้ค้นรายการเดียวกันในระบบ e-Budget"])
    ws.cell(row=1, column=1).font = Font(b=True, size=12)
    ws.append(["ระบบนี้ช่วยระบุตำแหน่งและหลักฐานสำหรับให้มนุษย์ตรวจสอบเท่านั้น "
               "— ไม่ได้เชื่อมต่อหรือแก้ไขระบบ e-Budget โดยอัตโนมัติ"])
    ws.cell(row=2, column=1).font = Font(size=10, b=True, color="B45309")
    ws.append([])

    headers = ["รหัสรายการตรวจ", "หน่วยงาน", "แผนงาน", "ผลผลิต/โครงการ", "กิจกรรม",
               "หมวดรายจ่าย", "ประเภทรายจ่าย", "ลักษณะรายจ่าย", "ชื่อรายการ",
               "canonical key (9 บทบาท ตามที่มีจริง)", "ปี/สถานะเอกสาร ฝั่ง A",
               "ตำแหน่งในไฟล์เผยแพร่ ฝั่ง A", "ปี/สถานะเอกสาร ฝั่ง B",
               "ตำแหน่งในไฟล์เผยแพร่ ฝั่ง B"]
    widths = [14, 26, 26, 28, 28, 16, 20, 14, 24, 70, 30, 34, 30, 34]
    ws.append(headers)
    hr = ws.max_row
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
        cell = ws.cell(row=hr, column=i)
        cell.font = Font(b=True, size=10)
        cell.fill = PatternFill("solid", fgColor="F1F3F5")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = BOX

    for rec in records:
        ws.append([
            rec["sample_id"], rec["agency_display"], rec["plan_name"],
            rec["output_name"], rec["activity_name"], rec["objective_category"],
            rec["objective_subcategory"], rec["capital_class"], rec["item_label"],
            " › ".join(str(rec[role]) for role, _ in KEY_ROLES),
            SIDE_A_DOCSTATE,
            "%s · ชีต %s แถว %s เซลล์ %s" % (rec["file_a_name"], rec["sheet_a"],
                                             rec["row_a"], rec["cell_a"]),
            SIDE_B_DOCSTATE,
            "%s · ชีต %s แถว %s เซลล์ %s" % (rec["file_b_name"], rec["sheet_b"],
                                             rec["row_b"], rec["cell_b"]),
        ])
        r = ws.max_row
        for j in range(1, len(headers) + 1):
            c = ws.cell(row=r, column=j)
            c.border = BOX
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.font = Font(size=10)
        ws.row_dimensions[r].height = 42
    ws.freeze_panes = ws.cell(row=hr + 1, column=2)
    ws.auto_filter.ref = "A%d:%s%d" % (hr, get_column_letter(len(headers)), ws.max_row)
    return ws


TECH_COLUMNS = [
    ("sample_id", "รหัสรายการตรวจ", 14),
    ("finding_ref", "finding ID (อ้างผลการรัน)", 22),
    ("run_label", "การทดลอง", 18),
    ("dataset_class", "ชั้นข้อมูล", 14),
    ("category", "หมวดผลตรวจ", 12),
    ("category_label", "ความหมายหมวด", 24),
    ("rule_id", "รหัสกฎ", 12),
    ("rule_set_version", "rule set version", 18),
    ("machine_status", "คำตัดสินของระบบ", 16),
    ("review_status", "สถานะการตรวจ", 14),
    ("match_level", "วิธีจับคู่", 12),
    ("match_step", "ขั้น pipeline", 12),
    ("match_score", "คะแนนการจับคู่", 14),
    ("match_basis", "เกณฑ์การจับคู่", 34),
    ("raw_value_a", "ค่าดิบฝั่ง A (จากเซลล์)", 20),
    ("raw_value_b", "ค่าดิบฝั่ง B (จากเซลล์)", 20),
    ("amount_a", "ค่าที่ระบบใช้ฝั่ง A", 20),
    ("amount_b", "ค่าที่ระบบใช้ฝั่ง B", 20),
    ("amount_diff", "ผลต่าง", 16),
    ("unit", "หน่วยเงิน", 10),
    ("pct_change", "ร้อยละการเปลี่ยนแปลง", 18),
    ("pct_note", "หมายเหตุร้อยละ", 30),
    ("value_consistency", "ค่าดิบตรงกับค่าที่ระบบใช้", 18),
    ("value_consistency_note", "เหตุผลการแปลงค่า", 46),
    ("system_reason", "เหตุผลของระบบ", 46),
    ("file_a_label", "ไฟล์ A (label)", 12),
    ("file_a_name", "ไฟล์ A", 26),
    ("sheet_a", "ชีต A", 10),
    ("row_a", "แถว A", 9),
    ("cell_a", "เซลล์ A", 10),
    ("file_a_sha256", "SHA-256 ไฟล์ A", 68),
    ("file_b_label", "ไฟล์ B (label)", 12),
    ("file_b_name", "ไฟล์ B", 26),
    ("sheet_b", "ชีต B", 10),
    ("row_b", "แถว B", 9),
    ("cell_b", "เซลล์ B", 10),
    ("file_b_sha256", "SHA-256 ไฟล์ B", 68),
]


def _technical_sheet(wb, records, meta):
    ws = wb.create_sheet("Technical Details")
    ws.append(["ฟิลด์ทางเทคนิคทั้งหมด — เก็บไว้เพื่อการตรวจสอบย้อนกลับ ห้ามลบ"])
    ws.cell(row=1, column=1).font = Font(b=True, size=12)
    ws.append(["เวอร์ชันที่ freeze: " + meta["versions"] + " · แบบฟอร์ม "
               + meta["reviewpack_version"] + " · " + REVIEW_SCHEMA_VERSION
               + " · ค่าทุกค่าคัดจากผลการรันที่ freeze แล้ว ไม่มีการคำนวณใหม่"])
    ws.cell(row=2, column=1).font = Font(size=9, italic=True)
    ws.append([])

    ws.append([t for _, t, _ in TECH_COLUMNS])
    hr = ws.max_row
    for i, (key, title, w) in enumerate(TECH_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
        cell = ws.cell(row=hr, column=i)
        cell.font = Font(b=True, size=9)
        cell.fill = PatternFill("solid", fgColor="F1F3F5")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = BOX

    for rec in records:
        ws.append([rec.get(k) for k, _, _ in TECH_COLUMNS])
        r = ws.max_row
        for i in range(1, len(TECH_COLUMNS) + 1):
            c = ws.cell(row=r, column=i)
            c.border = BOX
            c.font = Font(size=9)
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = ws.cell(row=hr + 1, column=2)
    ws.auto_filter.ref = "A%d:%s%d" % (hr, get_column_letter(len(TECH_COLUMNS)),
                                       ws.max_row)
    return ws


def _choices_sheet(wb):
    ws = wb.create_sheet("ตัวเลือก")
    ws.append(["คำตัดสินของผู้วิจัย", "ความมั่นใจ", "เปิดหลักฐานแล้ว"])
    for i in range(max(len(VERDICT_CHOICES), len(CONFIDENCE_CHOICES),
                       len(EVIDENCE_OPENED_CHOICES))):
        ws.append([VERDICT_CHOICES[i] if i < len(VERDICT_CHOICES) else "",
                   CONFIDENCE_CHOICES[i] if i < len(CONFIDENCE_CHOICES) else "",
                   EVIDENCE_OPENED_CHOICES[i] if i < len(EVIDENCE_OPENED_CHOICES) else ""])
    for col, w in (("A", 22), ("B", 18), ("C", 18)):
        ws.column_dimensions[col].width = w
    return ws


def write_workbook(path, records, meta, sources):
    """สร้างสมุดงานรุ่น 1.2.0 — `sources` = {ชื่อไฟล์: path เต็ม} สำหรับ hyperlink"""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    _guide_sheet(wb, meta)
    _review_sheet(wb, records, meta, sources)
    _evidence_preview_sheet(wb, records)
    _source_lookup_sheet(wb, records)
    _technical_sheet(wb, records, meta)
    _choices_sheet(wb)
    wb.active = 1
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    wb.close()
    return path
