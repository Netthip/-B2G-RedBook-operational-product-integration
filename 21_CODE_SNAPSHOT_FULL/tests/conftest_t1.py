# -*- coding: utf-8 -*-
"""ตัวช่วยสร้างไฟล์ทดสอบรูปแบบ T1 — ใช้ในชุดทดสอบเท่านั้น

ไฟล์ที่สร้างอยู่ในโฟลเดอร์ชั่วคราวของ pytest ไม่เข้าคลังไฟล์ของระบบ
และไม่ปรากฏในผลตรวจใด
"""
import openpyxl

DEFAULT_DEFS = [
    ("min", "รหัสกระทรวง แบ่งหน่วยงานตามมาตรา"),
    ("min_name", "ชื่อกระทรวง แบ่งหน่วยงานตามมาตรา"),
    ("agc", "รหัสกรม แบ่งหน่วยงานตามมาตรา"),
    ("agc_name", "ชื่อกรม แบ่งหน่วยงานตามมาตรา"),
    ("group_budget", "กลุ่มงบประมาณ"),
    ("plan_name", "ชื่อแผนงาน"),
    ("output_name", "ชื่อผลผลิต/โครงการ"),
    ("act_name", "ชื่อกิจกรรม"),
    ("objc", "ชื่องบรายจ่าย"),
    ("objc_8", "ชื่อหมวดรายจ่ายหลัก"),
    ("cap_ncap", "จำแนกรายจ่ายประจำ-ลงทุน"),
    ("item_name", "ลักษณะรายจ่าย"),
    ("p_total_bud", "งบประมาณ"),
]


def make_row(agc="21011", plan="แผนงานทดสอบ", output="ผลผลิตทดสอบ",
             act="กิจกรรมทดสอบ", objc="งบดำเนินงาน", objc8="ค่าตอบแทน",
             cap="รายจ่ายประจำ", item="รายการรายจ่ายประจำ", amount=1000):
    return ["21000", "กระทรวงทดสอบ", agc, f"หน่วยงาน {agc}",
            "งบประมาณรายจ่ายของหน่วยรับงบประมาณ", plan, output, act,
            objc, objc8, cap, item, amount]


def write_t1(path, rows, defs=None, physical_names=None, extra_blank_column=False):
    """สร้างไฟล์รูปแบบ T1 หนึ่งไฟล์

    defs: รายการ (ชื่อฟิลด์, นิยาม) สำหรับชีต Data Dict
    physical_names: ชื่อคอลัมน์จริงในแถวหัว (ใช้จำลอง physical_name_drift)
    """
    defs = defs or DEFAULT_DEFS
    header = list(physical_names or [d[0] for d in defs])
    if extra_blank_column:
        header = header + [""]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data Dict"
    ws.append(["LIST", "FIELD", "DESCRIPTION"])
    for i, (name, desc) in enumerate(defs, start=1):
        ws.append([i, name, desc])

    ws2 = wb.create_sheet("data")
    ws2.append(header)
    for r in rows:
        row = list(r)
        if extra_blank_column:
            row = row + [None]
        ws2.append(row)
    wb.save(path)
    wb.close()
    return path
