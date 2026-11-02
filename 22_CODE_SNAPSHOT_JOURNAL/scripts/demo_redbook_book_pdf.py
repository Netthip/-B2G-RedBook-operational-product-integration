# -*- coding: utf-8 -*-
"""เล่มเอกสารงบประมาณ **สังเคราะห์** สำหรับพัฒนาและทดสอบสายเทียบ PDF ↔ PDF (``redbook.pdfbook``)

🔴 **SYNTHETIC DEMONSTRATION DATA** — ชื่อหน่วยงาน ตัวเลข และข้อความแต่งขึ้นทั้งหมด จัดหน้าเลียนแบบ
*โครง* เล่มงบประมาณ (ปก · สารบัญ · ต้นช่วงหน่วยงาน "งบประมาณรายจ่าย … 1. วิสัยทัศน์ 2. พันธกิจ
3. ผลสัมฤทธิ์…" · ตารางสรุปหมวดงบ ล้านบาท 4 ตำแหน่ง · ประจำ/ลงทุน · ประมาณการล่วงหน้า ·
รายละเอียดงบประมาณ บาท · รายการผูกพัน · ตารางเงินนอกงบประมาณท้ายช่วง) · ไม่ได้ลอกเนื้อหาจากเล่มใด
ทุกหน้ามีป้าย "ข้อมูลสังเคราะห์" (ยกเว้นหน้าที่จงใจไม่มีชั้นข้อความ) · ห้ามใช้เป็นหลักฐานงานวิจัย

สถานการณ์

* ``draft_act``  — ร่าง พ.ร.บ. 2570 ↔ พ.ร.บ. 2570 พร้อมความต่างที่ฝังไว้ครบ 9 หัวข้อ (ดู ``SEEDED``)
* ``cross_year`` — พ.ร.บ. 2569 ↔ พ.ร.บ. 2570 (เทียบข้ามปี)

แต่ละเล่มมี 2 หน่วยงาน (ทดสอบการหาช่วงหน้า) · ฉบับ B ของ ``draft_act`` มีหน้าคั่นเพิ่ม 1 หน้า
(เลขหน้าเลื่อน) และหน้าภาพที่ไม่มีชั้นข้อความ 1 หน้า

อยู่นอกแพ็กเกจ ``redbook`` · ใช้ PyMuPDF + ฟอนต์ไทยในเครื่อง (เครื่องมือสร้าง fixture เท่านั้น)
"""
from __future__ import annotations

import copy
from pathlib import Path

import fitz  # PyMuPDF — ใช้ได้ในเครื่องมือสร้าง fixture เท่านั้น

FONT_CANDIDATES = [Path("C:/Windows/Fonts/tahoma.ttf"), Path("C:/Windows/Fonts/leelawad.ttf"),
                   Path("/usr/share/fonts/truetype/tlwg/Garuda.ttf")]
MARK = "ข้อมูลสังเคราะห์ — สาธิตระบบเท่านั้น ไม่ใช่เอกสารงบประมาณจริง"
W, H = 595.0, 842.0
LEFT, RIGHT, TOP, BOTTOM = 40.0, 555.0, 70.0, 790.0
CATS = ("งบบุคลากร", "งบดำเนินงาน", "งบลงทุน", "งบเงินอุดหนุน", "งบรายจ่ายอื่น")
AGENCY_1 = "สำนักงานสาธิตการตรวจงบประมาณ"
AGENCY_2 = "สถาบันสาธิตข้อมูลการคลัง"
MINISTRY = "กระทรวงสาธิต"


def _font() -> str:
    for p in FONT_CANDIDATES:
        if p.exists():
            return str(p)
    raise SystemExit("ไม่พบฟอนต์ไทยในเครื่อง")


def mb(baht: int) -> str:
    """บาท → ล้านบาท 4 ตำแหน่ง (ค่าตัวอย่างเป็นพหุคูณของ 100 บาท จึงไม่ต้องปัด)"""
    return f"{baht / 1_000_000:,.4f}"


def bt(baht: int) -> str:
    return f"{baht:,}"


# ══════════════════════════════════════════════════════════════════════════════
#  ข้อมูลหน่วยงาน (ฐาน = ร่าง พ.ร.บ. 2570 ของหน่วยงานที่ 1)
# ══════════════════════════════════════════════════════════════════════════════
def base_agency(fy: int) -> dict:
    y0 = fy - 1
    return {
        "name": AGENCY_1, "fy": fy,
        "offbudget_head": 18_500_000,
        "vision": "เป็นองค์กรหลักในการสนับสนุนการตรวจสอบเอกสารงบประมาณที่ถูกต้อง โปร่งใส และตรวจสอบย้อนกลับได้",
        "missions": ["พัฒนาเครื่องมือตรวจสอบความถูกต้องของเอกสารงบประมาณ",
                     "สนับสนุนการจัดทำเอกสารงบประมาณให้ถูกต้องและทันเวลา",
                     "เผยแพร่ข้อมูลงบประมาณที่ตรวจสอบแล้วต่อสาธารณะ"],
        "outcomes": ["เอกสารงบประมาณมีความถูกต้องและสอดคล้องกันทุกตาราง",
                     "ผู้ปฏิบัติงานตรวจสอบเอกสารได้ครบถ้วนในเวลาที่กำหนด"],
        "targets": [{"text": "เอกสารงบประมาณที่เผยแพร่มีความถูกต้อง",
                     "indicators": [("ร้อยละของเอกสารที่ผ่านการตรวจสอบ", "ร้อยละ", {y0: "90", fy: "95"}),
                                    ("จำนวนหน่วยงานที่ได้รับการสนับสนุน", "หน่วยงาน", {y0: "40", fy: "45"})]}],
        "plans": [
            {"name": "แผนงานบุคลากรภาครัฐ", "children": [
                {"level": "รายการ", "name": "รายการค่าใช้จ่ายบุคลากรภาครัฐ",
                 "cats": {"งบบุคลากร": 42_356_700}, "prior": 41_800_000,
                 "mtef": [43_200_000, 44_100_000, 45_000_000],
                 "objective": "เพื่อเป็นค่าใช้จ่ายบุคลากรของหน่วยงาน",
                 "indicators": [],
                 "items": {"งบบุคลากร": [("1.1 เงินเดือนและค่าจ้างประจำ", 38_356_700, False),
                                         ("1.2 ค่าตอบแทนพนักงานราชการ", 4_000_000, False)]},
                 "commitments": []}]},
            {"name": "แผนงานพื้นฐานด้านการบริหารจัดการงบประมาณ", "children": [
                {"level": "ผลผลิต", "name": "การตรวจสอบเอกสารงบประมาณ",
                 "cats": {"งบดำเนินงาน": 15_480_000, "งบลงทุน": 3_200_000, "งบเงินอุดหนุน": 2_500_000},
                 "prior": 20_100_000, "mtef": [21_800_000, 22_400_000, 23_000_000],
                 "objective": "เพื่อให้เอกสารงบประมาณได้รับการตรวจสอบความถูกต้องก่อนเผยแพร่",
                 "indicators": [("จำนวนเอกสารที่ได้รับการตรวจสอบ", "ฉบับ", {y0: "110", fy: "120"}),
                                ("ร้อยละของข้อสังเกตที่ได้รับการตัดสิน", "ร้อยละ", {y0: "85", fy: "90"})],
                 "items": {"งบดำเนินงาน": [("2.1 ค่าตอบแทน ใช้สอยและวัสดุ", 14_280_000, False),
                                           ("2.2 ค่าสาธารณูปโภค", 1_200_000, False)],
                           "งบลงทุน": [("3.1 ค่าครุภัณฑ์", 3_200_000, False),
                                       ("(1) เครื่องคอมพิวเตอร์สำหรับงานประมวลผล จำนวน 10 เครื่อง", 2_000_000, False),
                                       ("(2) เครื่องพิมพ์ชนิดเลเซอร์ จำนวน 6 เครื่อง", 1_200_000, False)],
                           "งบเงินอุดหนุน": [("4.1 เงินอุดหนุนทั่วไป", 2_500_000, False)]},
                 "commitments": []},
                {"level": "ผลผลิต", "name": "การเผยแพร่ข้อมูลงบประมาณ",
                 "cats": {"งบดำเนินงาน": 6_150_000}, "prior": 5_900_000,
                 "mtef": [6_300_000, 6_450_000, 6_600_000],
                 "objective": "เพื่อเผยแพร่ข้อมูลงบประมาณที่ตรวจสอบแล้วต่อสาธารณะ",
                 "indicators": [("จำนวนชุดข้อมูลที่เผยแพร่", "ชุด", {y0: "24", fy: "30"})],
                 "items": {"งบดำเนินงาน": [("2.1 ค่าตอบแทน ใช้สอยและวัสดุ", 6_150_000, False)]},
                 "commitments": []}]},
            {"name": "แผนงานยุทธศาสตร์พัฒนาระบบตรวจสอบเอกสาร", "children": [
                {"level": "โครงการ", "name": "โครงการพัฒนาระบบตรวจสอบเอกสารงบประมาณดิจิทัล",
                 "cats": {"งบดำเนินงาน": 4_800_000, "งบลงทุน": 25_000_000}, "prior": 18_000_000,
                 "mtef": [30_500_000, 12_000_000, 8_000_000],
                 "objective": "เพื่อพัฒนาระบบที่ช่วยตรวจสอบความสอดคล้องของเอกสารงบประมาณ",
                 "indicators": [("ระบบที่พัฒนาแล้วเสร็จ", "ระบบ", {y0: "1", fy: "2"})],
                 "items": {"งบดำเนินงาน": [("2.1 ค่าตอบแทน ใช้สอยและวัสดุ", 4_800_000, False)],
                           "งบลงทุน": [("3.1 ค่าที่ดินและสิ่งก่อสร้าง", 25_000_000, False),
                                       ("(1) อาคารศูนย์ข้อมูลงบประมาณ 1 หลัง", 25_000_000, False)]},
                 "commitments": [{"item": "(1) อาคารศูนย์ข้อมูลงบประมาณ 1 หลัง", "total": 80_000_000,
                                  "years": {fy - 1: 15_000_000, fy: 25_000_000},
                                  "future": {fy + 1: 40_000_000}}]},
                {"level": "โครงการ", "name": "โครงการพัฒนาศักยภาพผู้ตรวจสอบเอกสาร",
                 "cats": {"งบดำเนินงาน": 2_400_000}, "prior": 2_000_000,
                 "mtef": [2_500_000, 2_500_000, 2_500_000],
                 "objective": "เพื่อพัฒนาทักษะผู้ปฏิบัติงานด้านการตรวจสอบเอกสาร",
                 "indicators": [("จำนวนผู้ผ่านการอบรม", "คน", {y0: "150", fy: "200"})],
                 "items": {"งบดำเนินงาน": [("2.1 ค่าตอบแทน ใช้สอยและวัสดุ", 2_400_000, False)]},
                 "commitments": []}]},
        ],
        "offbudget": {fy - 4: 9_800_000, fy - 3: 11_250_000, fy - 2: 12_900_000, fy - 1: 15_400_000,
                      fy: 18_500_000},
        "plan_total_override": {},     # จงใจให้ยอดแผนงานไม่เท่าผลรวม (ทดสอบตรวจภายในเล่ม)
        "mtef_prior_override": {},     # จงใจให้ปีก่อนในตารางประมาณการไม่ตรงกับเล่มปีก่อน
    }


def second_agency(fy: int) -> dict:
    a = {
        "name": AGENCY_2, "fy": fy, "offbudget_head": 2_000_000,
        "vision": "เป็นแหล่งข้อมูลการคลังสาธิตที่เชื่อถือได้",
        "missions": ["รวบรวมข้อมูลการคลังสาธิต"], "outcomes": ["มีข้อมูลการคลังสาธิตที่ครบถ้วน"],
        "targets": [], "offbudget": {fy - 1: 1_500_000, fy: 2_000_000},
        "plans": [{"name": "แผนงานพื้นฐานด้านข้อมูลการคลัง", "children": [
            {"level": "ผลผลิต", "name": "ข้อมูลการคลังสาธิต", "cats": {"งบดำเนินงาน": 9_000_000},
             "prior": 8_500_000, "mtef": [9_200_000, 9_400_000, 9_600_000],
             "objective": "เพื่อรวบรวมข้อมูล", "indicators": [],
             "items": {"งบดำเนินงาน": [("2.1 ค่าตอบแทน ใช้สอยและวัสดุ", 9_000_000, False)]},
             "commitments": []}]}],
        "plan_total_override": {}, "mtef_prior_override": {},
    }
    return a


def _child(ag, name):
    for p in ag["plans"]:
        for c in p["children"]:
            if c["name"] == name:
                return c
    raise KeyError(name)


# ══════════════════════════════════════════════════════════════════════════════
#  ความต่างที่ฝังไว้ (ร่าง 2570 → พ.ร.บ. 2570)
# ══════════════════════════════════════════════════════════════════════════════
SEEDED = [
    # (หัวข้อ, ชนิด, คำบอกสั้น)
    ("total", "changed", "ผลผลิตการตรวจสอบเอกสาร: งบดำเนินงานลด 1,250,000 บาท"),
    ("items", "not_proposed", "เครื่องพิมพ์ชนิดเลเซอร์: ร่างเสนอตั้ง 1,200,000 → พ.ร.บ. ไม่เสนอตั้ง"),
    ("struct", "renamed_candidate", "ผลผลิตการเผยแพร่ข้อมูลงบประมาณ → การเผยแพร่ข้อมูลงบประมาณภาครัฐ"),
    ("ind", "changed", "จำนวนเอกสารที่ได้รับการตรวจสอบ เป้าหมายปี 2570: 120 → 100"),
    ("ind", "changed", "ร้อยละของเอกสารที่ผ่านการตรวจสอบ หน่วยนับ: ร้อยละ → ระดับ"),
    ("ind", "only_b", "ตัวชี้วัดใหม่: ความพึงพอใจของผู้ใช้ข้อมูล"),
    ("text", "changed", "พันธกิจข้อ 2.2 ถ้อยคำเปลี่ยน"),
    ("text", "only_b", "ผลสัมฤทธิ์ข้อ 3.3 เพิ่มใหม่"),
    ("commit", "changed", "อาคารศูนย์ข้อมูล: วงเงินทั้งสิ้น 80 → 75 ล้านบาท และผูกพันปี 2571 ลดลง"),
    ("mtef", "changed", "โครงการพัฒนาศักยภาพ: ประมาณการปี 2571 2,500,000 → 2,200,000"),
    ("consist", "sum_mismatch", "ฉบับ B: ยอดแผนงานยุทธศาสตร์ในตารางสรุปไม่เท่าผลรวมโครงการ"),
    ("econ", "changed", "รายจ่ายประจำ/ลงทุนเปลี่ยนตามการปรับลด"),
    ("cover", "unread", "ฉบับ B: หน้าภาพที่ไม่มีชั้นข้อความ 1 หน้า"),
]


def act_from_draft(draft: dict) -> dict:
    a = copy.deepcopy(draft)
    c = _child(a, "การตรวจสอบเอกสารงบประมาณ")
    c["cats"]["งบดำเนินงาน"] -= 1_250_000
    c["items"]["งบดำเนินงาน"][0] = ("2.1 ค่าตอบแทน ใช้สอยและวัสดุ", 14_280_000 - 1_250_000, False)
    c["cats"]["งบลงทุน"] -= 1_200_000
    c["items"]["งบลงทุน"] = [("3.1 ค่าครุภัณฑ์", 2_000_000, False),
                             ("(1) เครื่องคอมพิวเตอร์สำหรับงานประมวลผล จำนวน 10 เครื่อง", 2_000_000, False),
                             ("(2) เครื่องพิมพ์ชนิดเลเซอร์ จำนวน 6 เครื่อง", None, True)]
    c["indicators"][0] = ("จำนวนเอกสารที่ได้รับการตรวจสอบ", "ฉบับ", {2569: "110", 2570: "100"})
    c["mtef"] = [20_300_000, 22_400_000, 23_000_000]
    d = _child(a, "การเผยแพร่ข้อมูลงบประมาณ")
    d["name"] = "การเผยแพร่ข้อมูลงบประมาณภาครัฐ"
    a["targets"][0]["indicators"][0] = ("ร้อยละของเอกสารที่ผ่านการตรวจสอบ", "ระดับ", {2569: "90", 2570: "95"})
    a["targets"][0]["indicators"].append(("ความพึงพอใจของผู้ใช้ข้อมูล", "ร้อยละ", {2569: "80", 2570: "85"}))
    a["missions"][1] = "สนับสนุนการจัดทำเอกสารงบประมาณให้ถูกต้อง ครบถ้วน และทันเวลา"
    a["outcomes"].append("ข้อมูลงบประมาณที่เผยแพร่ตรวจสอบย้อนกลับได้ถึงหน้าเอกสาร")
    p = _child(a, "โครงการพัฒนาระบบตรวจสอบเอกสารงบประมาณดิจิทัล")
    p["commitments"][0] = {"item": "(1) อาคารศูนย์ข้อมูลงบประมาณ 1 หลัง", "total": 75_000_000,
                           "years": {2569: 15_000_000, 2570: 25_000_000}, "future": {2571: 35_000_000}}
    q = _child(a, "โครงการพัฒนาศักยภาพผู้ตรวจสอบเอกสาร")
    q["mtef"] = [2_200_000, 2_500_000, 2_500_000]
    a["plan_total_override"] = {"แผนงานยุทธศาสตร์พัฒนาระบบตรวจสอบเอกสาร": 32_300_000}
    return a


def fy_from(prev: dict, fy: int) -> dict:
    """เล่มปีถัดไป (ข้ามปี) จากเล่มปีก่อน — งบปีก่อน = ยอดของปีก่อน · ปีนี้เปลี่ยนบางรายการ"""
    a = copy.deepcopy(prev)
    a["fy"] = fy
    for p in a["plans"]:
        for c in p["children"]:
            c["prior"] = sum(v for v in c["cats"].values())
            c["indicators"] = [(n, u, {fy - 1: t.get(fy - 1), fy: t.get(fy - 1)})
                               for n, u, t in c["indicators"]]
    c = _child(a, "การตรวจสอบเอกสารงบประมาณ")
    c["cats"]["งบดำเนินงาน"] -= 600_000
    c["items"]["งบดำเนินงาน"][0] = ("2.1 ค่าตอบแทน ใช้สอยและวัสดุ", 14_280_000 - 600_000, False)
    c["indicators"] = [("จำนวนเอกสารที่ได้รับการตรวจสอบ", "ฉบับ", {fy - 1: "120", fy: "130"}),
                       ("ร้อยละของข้อสังเกตที่ได้รับการตัดสิน", "ร้อยละ", {fy - 1: "90", fy: "92"})]
    d = _child(a, "การเผยแพร่ข้อมูลงบประมาณ")
    d["cats"]["งบดำเนินงาน"] += 350_000
    d["items"]["งบดำเนินงาน"][0] = ("2.1 ค่าตอบแทน ใช้สอยและวัสดุ", 6_150_000 + 350_000, False)
    # โครงการใหม่ปีนี้
    a["plans"][2]["children"].append({
        "level": "โครงการ", "name": "โครงการเชื่อมโยงข้อมูลงบประมาณข้ามหน่วยงาน",
        "cats": {"งบดำเนินงาน": 3_000_000}, "prior": 0, "mtef": [3_000_000, 3_000_000, 3_000_000],
        "objective": "เพื่อเชื่อมโยงข้อมูลงบประมาณระหว่างหน่วยงาน",
        "indicators": [("จำนวนหน่วยงานที่เชื่อมโยงข้อมูล", "หน่วยงาน", {fy: "10"})],
        "items": {"งบดำเนินงาน": [("2.1 ค่าตอบแทน ใช้สอยและวัสดุ", 3_000_000, False)]},
        "commitments": []})
    p = _child(a, "โครงการพัฒนาระบบตรวจสอบเอกสารงบประมาณดิจิทัล")
    p["commitments"] = [{"item": "(1) อาคารศูนย์ข้อมูลงบประมาณ 1 หลัง", "total": 80_000_000,
                         "years": {fy - 2: 15_000_000, fy - 1: 25_000_000, fy: 40_000_000}, "future": {}}]
    p["cats"]["งบลงทุน"] = 40_000_000
    p["items"]["งบลงทุน"] = [("3.1 ค่าที่ดินและสิ่งก่อสร้าง", 40_000_000, False),
                             ("(1) อาคารศูนย์ข้อมูลงบประมาณ 1 หลัง", 40_000_000, False)]
    p["mtef"] = [12_000_000, 8_000_000, 6_000_000]
    a["vision"] = ("เป็นองค์กรหลักในการสนับสนุนการตรวจสอบเอกสารงบประมาณที่ถูกต้อง โปร่งใส "
                   "ตรวจสอบย้อนกลับได้ และเปิดเผยต่อสาธารณะ")
    # ปีเดียวกันต้องตรงกับเล่มปีก่อน · ตัดปีเก่าสุดออก · เพิ่มปีใหม่
    a["offbudget"] = {k: v for k, v in prev["offbudget"].items() if k > min(prev["offbudget"])}
    a["offbudget"][fy] = 21_000_000
    a["offbudget_head"] = 21_000_000
    # ปีก่อนในตารางประมาณการของเล่มนี้ ไม่ตรงกับงบปีก่อนของเล่มปีก่อน (จงใจ)
    a["mtef_prior_override"] = {"การเผยแพร่ข้อมูลงบประมาณ": 6_200_000}
    a["targets"][0]["indicators"] = [("ร้อยละของเอกสารที่ผ่านการตรวจสอบ", "ร้อยละ", {fy - 1: "93", fy: "97"}),
                                     ("จำนวนหน่วยงานที่ได้รับการสนับสนุน", "หน่วยงาน", {fy - 1: "45", fy: "50"})]
    return a


def edge_pair() -> tuple[dict, dict]:
    """กรณียากตามที่โบขอ (#41) — ร่าง ↔ พ.ร.บ. 2570 ที่ต่างกันเฉพาะจุดเหล่านี้

    E1 ตารางสรุปฉบับ B พิมพ์หน่วยบาท (A = ล้านบาท) — ค่าเท่ากัน ⇒ ไม่มีข้อสังเกตเงิน มีเฉพาะเรื่องหน่วย
    E2 หัวคอลัมน์ปีของตารางประมาณการฉบับ B พิมพ์ "พ.ศ. 2570" — ต้องอ่านได้เหมือนเดิม
    E3 งบดำเนินงานของสองโครงการสลับกัน — ยอดแผนงานเท่าเดิม แต่ทั้งสองโครงการต้องถูกยกขึ้น
    E4 ฉบับ B พิมพ์งบดำเนินงานของผลผลิตหนึ่งในตารางสรุปคลาด แต่ยอดแผนงาน/ยอดรวมแถวยังถูก
    E5 ข้อความซ้ำในหมวดเดียวกัน ("ค่าจ้างเหมาบริการ" 2 รายการ) — ฉบับ B เปลี่ยนเฉพาะรายการที่สอง
    E6 เลขนำหน้าในตารางสรุปฉบับ B มีจุดท้าย ("2.2.")
    E7 ชื่อหน่วยงานต้นช่วงฉบับ B ต่างจาก A
    """
    a = base_agency(2570)
    for ag in (a,):
        c = _child(ag, "การตรวจสอบเอกสารงบประมาณ")
        c["items"]["งบดำเนินงาน"] = [("2.1 ค่าตอบแทน ใช้สอยและวัสดุ", 14_280_000, False),
                                     ("(1) ค่าจ้างเหมาบริการ", 1_000_000, False),
                                     ("(2) ค่าจ้างเหมาบริการ", 500_000, False),
                                     ("2.2 ค่าสาธารณูปโภค", 1_200_000, False)]
    b = copy.deepcopy(a)
    b["summary_unit"] = "บาท"
    b["year_prefix"] = "พ.ศ."
    p1 = _child(b, "โครงการพัฒนาระบบตรวจสอบเอกสารงบประมาณดิจิทัล")
    p2 = _child(b, "โครงการพัฒนาศักยภาพผู้ตรวจสอบเอกสาร")
    v1, v2 = p1["cats"]["งบดำเนินงาน"], p2["cats"]["งบดำเนินงาน"]
    p1["cats"]["งบดำเนินงาน"], p2["cats"]["งบดำเนินงาน"] = v2, v1
    p1["items"]["งบดำเนินงาน"] = [("2.1 ค่าตอบแทน ใช้สอยและวัสดุ", v2, False)]
    p2["items"]["งบดำเนินงาน"] = [("2.1 ค่าตอบแทน ใช้สอยและวัสดุ", v1, False)]
    p1["mtef"], p2["mtef"] = list(p1["mtef"]), list(p2["mtef"])
    b["child_print_override"] = {"การเผยแพร่ข้อมูลงบประมาณ": {"งบดำเนินงาน": 6_250_000}}
    c = _child(b, "การตรวจสอบเอกสารงบประมาณ")
    c["items"]["งบดำเนินงาน"][2] = ("(2) ค่าจ้างเหมาบริการ", 450_000, False)
    b["numbering_override"] = {"การเผยแพร่ข้อมูลงบประมาณ": "2.2."}
    b["title"] = "สำนักงานสาธิตการตรวจงบประมาณแห่งชาติ"
    return a, b


CROSS_YEAR_SEEDED = [
    ("total", "year_change", "งบปี 2570 เทียบปี 2569 รายผลผลิต/โครงการ"),
    ("struct", "only_b", "โครงการเชื่อมโยงข้อมูลงบประมาณข้ามหน่วยงาน (ใหม่ปี 2570)"),
    ("mtef", "same_year_mismatch", "การเผยแพร่ข้อมูลงบประมาณ: ปี 2569 ในเล่ม 2570 ≠ งบในเล่ม 2569"),
    ("ind", "same_year_mismatch", "ร้อยละของเอกสารที่ผ่านการตรวจสอบ เป้าหมายปี 2569: 95 → 93"),
    ("text", "changed", "วิสัยทัศน์ถ้อยคำเปลี่ยน"),
]


# ══════════════════════════════════════════════════════════════════════════════
#  วาดหน้า
# ══════════════════════════════════════════════════════════════════════════════
class Book:
    def __init__(self, font: str):
        self.font = font
        self.f = fitz.Font(fontfile=font)
        self.doc = fitz.open()
        self.page = None
        self.y = TOP
        self.n = 0
        self.repeat = None       # หัวตารางที่ต้องวาดซ้ำเมื่อขึ้นหน้าใหม่

    def new_page(self, mark=True):
        self.n += 1
        self.page = self.doc.new_page(width=W, height=H)
        if mark:
            self.text(LEFT, 36, MARK, 8)
            self.right(RIGHT, 820, f"หน้า {self.n}", 8)
        self.y = TOP
        if self.repeat:
            self.repeat()

    def text(self, x, y, s, size=10.0):
        self.page.insert_text(fitz.Point(x, y), s, fontsize=size, fontname="thai",
                              fontfile=self.font)

    def width(self, s, size):
        return self.f.text_length(s, fontsize=size)

    def right(self, xr, y, s, size=10.0):
        self.text(xr - self.width(s, size), y, s, size)

    def need(self, h):
        if self.y + h > BOTTOM:
            self.new_page()

    def line(self, s, x=LEFT, size=10.0, gap=15.0):
        self.need(gap)
        self.text(x, self.y, s, size)
        self.y += gap

    def para(self, s, x=LEFT, size=10.0, width=RIGHT - LEFT):
        """ตัดบรรทัดตามความกว้าง (ข้อความไทยไม่มีช่องว่าง — ตัดตามอักขระ)"""
        cur = ""
        for ch in s:
            if self.width(cur + ch, size) > width - (x - LEFT):
                self.line(cur, x, size)
                cur = ""
            cur += ch
        if cur:
            self.line(cur, x, size)

    def amount_line(self, label, amount: str, x=LEFT, size=10.0, unit="บาท"):
        self.need(15)
        self.text(x, self.y, label, size)
        if amount:
            self.right(RIGHT - 30, self.y, amount, size)
            self.text(RIGHT - 25, self.y, unit, size)
        self.y += 15

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(path))
        self.doc.close()


def _child_total(c):
    return sum(c["cats"].values())


def _node_rows(ag):
    """(ระดับ, ป้าย, ค่าต่อหมวด, ยอดรวม, ลูก?) ตามลำดับตาราง — แผนงาน/ผลผลิต/โครงการ"""
    rows = []
    for i, p in enumerate(ag["plans"], 1):
        cats = {k: 0 for k in CATS}
        for c in p["children"]:
            for k, v in c["cats"].items():
                cats[k] += v
        tot = ag["plan_total_override"].get(p["name"], sum(cats.values()))
        rows.append(("plan", f"{i}. {p['name']}", cats, tot, p))
        for j, c in enumerate(p["children"], 1):
            pref = "" if c["level"] == "รายการ" else f"{c['level']} : "
            rows.append(("child", f"{i}.{j} {pref}{c['name']}", c["cats"], _child_total(c), c))
    return rows


def _grand(ag):
    cats = {k: 0 for k in CATS}
    for p in ag["plans"]:
        for c in p["children"]:
            for k, v in c["cats"].items():
                cats[k] += v
    return cats, sum(cats.values())


def draw_agency(bk: Book, ag: dict, no: int, *, extra_blank_page=False, no_text_page=False):
    fy = ag["fy"]
    bk.new_page()
    bk.line(f"{no}. {ag.get('title', ag['name'])}", size=13, gap=22)
    _cats, grand = _grand(ag)
    bk.amount_line("งบประมาณรายจ่าย", bt(grand))
    bk.amount_line("เงินนอกงบประมาณ", bt(ag["offbudget_head"]))
    bk.y += 6
    bk.line("1. วิสัยทัศน์", size=11, gap=17)
    bk.para(ag["vision"], x=LEFT + 15)
    bk.line("2. พันธกิจ", size=11, gap=17)
    for i, m in enumerate(ag["missions"], 1):
        bk.para(f"2.{i} {m}", x=LEFT + 15)
    bk.line("3. ผลสัมฤทธิ์หรือประโยชน์ที่คาดว่าจะได้รับ", size=11, gap=17)
    for i, m in enumerate(ag["outcomes"], 1):
        bk.para(f"3.{i} {m}", x=LEFT + 15)
    if ag["targets"]:
        bk.line("4. เป้าหมายการให้บริการหน่วยงาน", size=11, gap=17)
        for i, t in enumerate(ag["targets"], 1):
            bk.para(f"4.{i} {t['text']}", x=LEFT + 15)
            _indicator_table(bk, t["indicators"], fy)
    if extra_blank_page:
        bk.new_page()
        bk.line("หน้าคั่นเพื่อแสดงรายละเอียดเพิ่มเติม (สาธิต)", size=10)
    # ── 5. ตารางสรุป ──
    bk.new_page()
    bk.line(f"5. สรุปงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. {fy}", size=11, gap=17)
    bk.line("5.1 จำแนกตามแผนงาน ผลผลิต/โครงการ และงบรายจ่าย", size=10, gap=15)
    in_baht = ag.get("summary_unit") == "บาท"
    money = bt if in_baht else mb
    bk.right(RIGHT, bk.y, "(หน่วย : บาท)" if in_baht else "(หน่วย : ล้านบาท)", 8)
    bk.y += 13
    xs = (262, 320, 376, 438, 500, RIGHT)
    heads = (*CATS, "รวม")

    def head():
        bk.text(LEFT, bk.y, "แผนงาน/ผลผลิต/โครงการ", 8)
        for h, x in zip(heads, xs):
            bk.right(x, bk.y, h, 8)
        bk.y += 14

    head()
    bk.repeat = head
    cats, grand = _grand(ag)
    _row(bk, "รวมทั้งสิ้น", [cats[k] for k in CATS] + [grand], xs, money=money)
    for kind, label, cats_, tot, obj in _node_rows(ag):
        printed = {**cats_, **ag.get("child_print_override", {}).get(obj["name"], {})}
        vals = [printed.get(k, 0) for k in CATS] + [tot]
        pre = ag.get("numbering_override", {}).get(obj["name"])
        if pre:
            label = pre + " " + label.split(" ", 1)[1]
        _row(bk, label, vals, xs, indent=0 if kind == "plan" else 10, money=money)
    bk.repeat = None
    bk.y += 8
    # ── 5.2 ประจำ/ลงทุน ──
    bk.need(60)
    bk.line("5.2 จำแนกตามประเภทรายจ่าย", size=10, gap=15)
    bk.right(RIGHT, bk.y, "(หน่วย : ล้านบาท)", 8)
    bk.y += 13
    xs2 = (400, 478, RIGHT)

    def head2():
        bk.text(LEFT, bk.y, "แผนงาน/ผลผลิต/โครงการ", 8)
        for h, x in zip(("รายจ่ายประจำ", "รายจ่ายลงทุน", "รวม"), xs2):
            bk.right(x, bk.y, h, 8)
        bk.y += 14

    head2()
    bk.repeat = head2
    inv = cats["งบลงทุน"]
    _row(bk, "รวมทั้งสิ้น", [grand - inv, inv, grand], xs2)
    for kind, label, cats_, tot, _obj in _node_rows(ag):
        i_ = cats_.get("งบลงทุน", 0)
        _row(bk, label, [tot - i_, i_, tot], xs2, indent=0 if kind == "plan" else 10)
    bk.repeat = None
    # ── 6. ประมาณการล่วงหน้า ──
    bk.new_page()
    bk.line("6. งบประมาณรายจ่ายและประมาณการรายจ่ายล่วงหน้า จำแนกตามแผนงานและผลผลิต/โครงการ",
            size=10, gap=17)
    bk.right(RIGHT, bk.y, "(หน่วย : ล้านบาท)", 8)
    bk.y += 13
    years = [fy - 1, fy, fy + 1, fy + 2, fy + 3]
    xs3 = (300, 365, 430, 492, RIGHT)

    def head3():
        bk.text(LEFT, bk.y, "แผนงาน/ผลผลิต/โครงการ", 8)
        for y_, x in zip(years, xs3):
            bk.right(x, bk.y, f"{ag.get('year_prefix', 'ปี')} {y_}", 8)
        bk.y += 14

    head3()
    bk.repeat = head3
    tot_years = [0] * 5
    rows = []
    for kind, label, cats_, tot, obj in _node_rows(ag):
        if kind == "plan":
            ch = obj["children"]
            vals = [sum(ag["mtef_prior_override"].get(c["name"], c["prior"]) for c in ch),
                    tot if not ag["plan_total_override"] else sum(_child_total(c) for c in ch),
                    *[sum(c["mtef"][k] for c in ch) for k in range(3)]]
        else:
            vals = [ag["mtef_prior_override"].get(obj["name"], obj["prior"]), tot, *obj["mtef"]]
        rows.append((kind, label, vals))
        if kind == "plan":
            tot_years = [a + b for a, b in zip(tot_years, vals)]
    _row(bk, "รวมทั้งสิ้น", tot_years, xs3)
    for kind, label, vals in rows:
        _row(bk, label, vals, xs3, indent=0 if kind == "plan" else 10)
    bk.repeat = None
    bk.y += 4
    bk.line(f"หมายเหตุ ปี {fy + 1}–{fy + 3} เป็นประมาณการรายจ่ายล่วงหน้า", size=8, gap=13)
    # ── 7. รายละเอียด ──
    bk.new_page()
    bk.line("7. รายละเอียดงบประมาณจำแนกตามแผนงาน", size=11, gap=18)
    for i, p in enumerate(ag["plans"], 1):
        bk.need(40)
        bk.line(f"7.{i} {p['name']}", size=10.5, gap=16)
        for j, c in enumerate(p["children"], 1):
            bk.need(60)
            pref = "" if c["level"] == "รายการ" else f"{c['level']} : "
            bk.amount_line(f"7.{i}.{j} {pref}{c['name']}", bt(_child_total(c)), x=LEFT + 8, size=10)
            bk.para(f"วัตถุประสงค์ : {c['objective']}", x=LEFT + 18, size=9.5)
            if c["indicators"]:
                _indicator_table(bk, c["indicators"], fy, x=LEFT + 18)
            for k, cat in enumerate(CATS, 1):
                if cat not in c["cats"]:
                    continue
                bk.amount_line(f"{k}. {cat}", bt(c["cats"][cat]), x=LEFT + 18, size=9.5)
                for label, amount, notp in c["items"].get(cat, []):
                    is_leaf = label.startswith("(")
                    commits = [cm for cm in c["commitments"] if cm["item"] == label]
                    if commits:
                        bk.line("รายการผูกพันข้ามปี", x=LEFT + 40, size=9, gap=13)
                    txt = label + (" - ไม่เสนอตั้งงบประมาณ" if notp else "")
                    bk.amount_line(txt, bt(amount) if amount else "", x=LEFT + (40 if is_leaf else 30),
                                   size=9)
                    for cm in commits:
                        bk.amount_line("วงเงินทั้งสิ้น", bt(cm["total"]), x=LEFT + 55, size=9)
                        for y_, v in sorted(cm["years"].items()):
                            bk.amount_line(f"ปี {y_} ตั้งงบประมาณ", bt(v), x=LEFT + 55, size=9)
                        for y_, v in sorted(cm["future"].items()):
                            bk.amount_line(f"ผูกพันงบประมาณปี {y_}", bt(v), x=LEFT + 55, size=9)
            bk.y += 4
    if no_text_page:
        bk.n += 1
        pg = bk.doc.new_page(width=W, height=H)
        pg.draw_rect(fitz.Rect(80, 120, 515, 700), color=(0.6, 0.6, 0.6), fill=(0.92, 0.92, 0.92))
        pg.draw_line(fitz.Point(80, 120), fitz.Point(515, 700), color=(0.5, 0.5, 0.5))
        bk.page = pg
    # ── 8. เงินนอกงบประมาณ ──
    bk.new_page()
    bk.line("8. เงินนอกงบประมาณ", size=11, gap=17)
    bk.right(RIGHT, bk.y, "(หน่วย : ล้านบาท)", 8)
    bk.y += 13
    ys = sorted(ag["offbudget"])
    xs4 = tuple(RIGHT - 62 * (len(ys) - 1 - k) for k in range(len(ys)))
    bk.text(LEFT, bk.y, "รายการ", 8)
    for y_, x in zip(ys, xs4):
        bk.right(x, bk.y, f"ปี {y_}", 8)
    bk.y += 14
    _row(bk, "เงินนอกงบประมาณสะสมคงเหลือ", [ag["offbudget"][y_] for y_ in ys], xs4)


def _row(bk: Book, label, vals, xs, indent=0, size=8.5, money=None):
    money = money or mb
    bk.need(14)
    lbl = label
    maxw = xs[0] - 60 - LEFT - indent
    rest = ""
    while bk.width(lbl, size) > maxw:
        rest = lbl[-1] + rest
        lbl = lbl[:-1]
    bk.text(LEFT + indent, bk.y, lbl, size)
    for v, x in zip(vals, xs):
        bk.right(x, bk.y, money(v) if v else "-", size)
    bk.y += 13
    if rest:
        bk.text(LEFT + indent + 8, bk.y, rest, size)
        bk.y += 13


def _indicator_table(bk: Book, inds, fy, x=LEFT + 15):
    years = sorted({y for _n, _u, t in inds for y in t})
    xs = tuple(RIGHT - 55 * (len(years) - 1 - k) for k in range(len(years)))
    ux = xs[0] - 85

    def head():
        bk.text(x, bk.y, "ตัวชี้วัด", 8.5)
        bk.text(ux, bk.y, "หน่วยนับ", 8.5)
        for y_, xx in zip(years, xs):
            bk.right(xx, bk.y, f"ปี {y_}", 8.5)
        bk.y += 13

    bk.need(30)
    head()
    for name, unit, t in inds:
        bk.need(13)
        bk.text(x + 6, bk.y, name, 8.5)
        bk.text(ux, bk.y, unit, 8.5)
        for y_, xx in zip(years, xs):
            v = t.get(y_)
            bk.right(xx, bk.y, v if v else "-", 8.5)
        bk.y += 13
    bk.y += 4


def build_book(out: Path, *, fy: int, stage: str, agencies, extra_blank_page=False,
               no_text_page=False) -> Path:
    bk = Book(_font())
    bk.new_page()
    bk.line("เอกสารงบประมาณ ฉบับที่ 3 (สาธิต)", size=16, gap=28)
    bk.line(f"งบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. {fy}", size=14, gap=24)
    bk.line(stage, size=12, gap=20)
    bk.line(MINISTRY, size=12, gap=20)
    bk.new_page()
    bk.line("สารบัญ", size=13, gap=22)
    for i, ag in enumerate(agencies, 1):
        bk.line(f"({i}) {ag['name']}", size=10)
    for i, ag in enumerate(agencies, 1):
        draw_agency(bk, ag, i, extra_blank_page=extra_blank_page and i == 1,
                    no_text_page=no_text_page and i == 1)
    bk.save(out)
    return out


STAGE_DRAFT = "ร่างพระราชบัญญัติงบประมาณรายจ่ายประจำปีงบประมาณ (สาธิต)"
STAGE_ACT = "ฉบับปรับปรุงตามพระราชบัญญัติงบประมาณรายจ่ายประจำปีงบประมาณ (สาธิต)"


def build(out_dir, scenario: str = "draft_act") -> tuple[Path, Path]:
    out = Path(out_dir)
    if scenario == "draft_act":
        d = base_agency(2570)
        a = build_book(out / "synthetic_book_2570_draft.pdf", fy=2570, stage=STAGE_DRAFT,
                       agencies=[d, second_agency(2570)])
        b = build_book(out / "synthetic_book_2570_act.pdf", fy=2570, stage=STAGE_ACT,
                       agencies=[act_from_draft(d), second_agency(2570)],
                       extra_blank_page=True, no_text_page=True)
        return a, b
    if scenario == "cross_year":
        prev = base_agency(2569)
        prev["targets"][0]["indicators"] = [
            ("ร้อยละของเอกสารที่ผ่านการตรวจสอบ", "ร้อยละ", {2568: "90", 2569: "95"}),
            ("จำนวนหน่วยงานที่ได้รับการสนับสนุน", "หน่วยงาน", {2568: "40", 2569: "45"})]
        for p in prev["plans"]:
            for c in p["children"]:
                for cm in c["commitments"]:
                    cm["years"] = {2568: 15_000_000, 2569: 25_000_000}
                    cm["future"] = {2570: 40_000_000}
        a = build_book(out / "synthetic_book_2569_act.pdf", fy=2569, stage=STAGE_ACT,
                       agencies=[prev, second_agency(2569)])
        b = build_book(out / "synthetic_book_2570_act_cross.pdf", fy=2570, stage=STAGE_ACT,
                       agencies=[fy_from(prev, 2570), second_agency(2570)])
        return a, b
    if scenario == "edge":
        a_ag, b_ag = edge_pair()
        a = build_book(out / "synthetic_book_2570_edge_a.pdf", fy=2570, stage=STAGE_DRAFT,
                       agencies=[a_ag, second_agency(2570)])
        b = build_book(out / "synthetic_book_2570_edge_b.pdf", fy=2570, stage=STAGE_ACT,
                       agencies=[b_ag, second_agency(2570)])
        return a, b
    raise SystemExit(f"ไม่รู้จักสถานการณ์ {scenario}")


if __name__ == "__main__":
    import sys
    sc = sys.argv[2] if len(sys.argv) > 2 else "draft_act"
    a, b = build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".data_demo/books"), sc)
    print(f"สร้างเล่มสังเคราะห์ ({sc}) A: {a.name} · B: {b.name}")
