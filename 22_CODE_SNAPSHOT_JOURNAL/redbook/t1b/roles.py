# -*- coding: utf-8 -*-
"""T1B — การระบุบทบาทของชีตและระดับเอกสาร

🔴 **ห้ามใช้เป็น identity key** (คำสั่ง Gift ข้อ 2 · 1 ก.ย. 2569):
  - ชื่อชีต        — เปลี่ยนทั้งข้ามปีและข้ามหน่วยงาน (`บุค` -> `bบุค`, `Sheet7_2` -> `Sheet 7.2`)
  - index ของชีต   — เลื่อนได้ (21016: `Sheet8` อยู่ index 16 ปี 2569 แต่ index 18 ปี 2570)
  - prefix ตัวอักษรอย่างเดียว — defect เดิม `("b","B")` จับชีต `บุค` (บ ไทย) ไม่ได้
  - สีของ tab      — เป็น visual cue เท่านั้น

✅ **ที่ใช้ได้:** `A1` + content signature + `document_level`
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .normalize import normalize_label, split_leading_number, strip_fiscal_years

# ---------------------------------------------------------------- document level

DOCUMENT_LEVEL_MINISTRY = "ministry"
DOCUMENT_LEVEL_AGENCY = "agency"
DOCUMENT_LEVEL_UNKNOWN = "unknown"

#: 🔴 ต้องใช้ **วลีเฉพาะ** ห้ามจับคำว่า "กระทรวง" ลอย ๆ
#: เพราะชีตปกของแฟ้ม *ระดับหน่วยงาน* ก็เขียนว่า "กระทรวงสาธารณสุข"
#: (พบจริงที่ ``Sheet123!A2`` ของ ``XL_FY2569_draft-bill_21011_HSRI.xlsx``)
#: การจับคำลอย ๆ จะทำให้แฟ้มหน่วยงานทุกแฟ้มถูกระบุเป็นระดับกระทรวง
_MINISTRY_PHRASES = ("การให้บริการกระทรวง", "งบประมาณรายจ่ายของกระทรวง")
_AGENCY_PHRASES = ("การให้บริการหน่วยงาน", "งบประมาณรายจ่ายของหน่วยงาน")

# ---------------------------------------------------------------- plan role

PLAN_PERSONNEL = "PLAN_PERSONNEL"
PLAN_FUNDAMENTAL = "PLAN_FUNDAMENTAL"
PLAN_STRATEGIC = "PLAN_STRATEGIC"
PLAN_INTEGRATED = "PLAN_INTEGRATED"
PLAN_NOT_APPLICABLE = "NOT_APPLICABLE"

#: short code ตามคำสั่ง Gift ข้อ 3 — ห้ามใช้ code ตัวอักษรเดียวแบบ "B"
PLAN_SHORT_CODE = {
    PLAN_PERSONNEL: "PERS",
    PLAN_FUNDAMENTAL: "FUND",
    PLAN_STRATEGIC: "STRAT",
    PLAN_INTEGRATED: "INTG",
    PLAN_NOT_APPLICABLE: "NA",
}

#: คำที่บ่งชี้แผน — เรียงจากยาวไปสั้นเพื่อกันการจับคำสั้นก่อน
_PLAN_MARKERS: tuple[tuple[str, str], ...] = (
    ("บุคลากรภาครัฐ", PLAN_PERSONNEL),
    ("แผนบุค", PLAN_PERSONNEL),
    ("งานพื้นฐาน", PLAN_FUNDAMENTAL),
    ("แผนพื้น", PLAN_FUNDAMENTAL),
    ("ยุทธศาสตร์", PLAN_STRATEGIC),
    ("แผนยุทธ", PLAN_STRATEGIC),
    ("บูรณาการ", PLAN_INTEGRATED),
    ("แผนบู", PLAN_INTEGRATED),
)

# ---------------------------------------------------------------- sheet class

SHEET_CLASS_MAIN = "MAIN"
SHEET_CLASS_COVER = "COVER"
SHEET_CLASS_SUPPORTING = "SUPPORTING"
SHEET_CLASS_UNKNOWN = "UNKNOWN"

#: จำนวนแถวแรกที่ยอมค้นหาข้อความหัวเรื่อง — ``A1`` ว่างได้
#: (``Sheet123`` และ ``ข้อ 1-3`` มี ``A1 = None`` และหัวเรื่องอยู่ที่ ``A2``)
MAX_TITLE_SCAN_ROWS = 4


@dataclass(frozen=True)
class SheetFacts:
    """ข้อเท็จจริงเชิงโครงสร้างของชีตหนึ่ง — อ่านมาแล้วจากไฟล์

    ตั้งใจให้เป็นค่าธรรมดา ไม่ผูกกับ openpyxl เพื่อให้ทดสอบได้โดยไม่ต้องเปิดไฟล์
    """

    name: str
    index: int
    a1: object
    max_row: int
    max_column: int
    merged_count: int
    #: G1 (#14 · ตอบ REVIEW ของ Bo) — ช่วงเซลล์ผสาน ``(แถวฐาน 1, คอลัมน์แรกฐาน 0, คอลัมน์สุดท้ายฐาน 0)``
    #: ใช้ตัดสินว่า "เซลล์ถัดไปทางขวา" ของตัวเลขคือเซลล์ใด เมื่อตัวเลขอยู่ในเซลล์ผสาน
    merged_spans: tuple = ()


@dataclass(frozen=True)
class TitleCandidate:
    """เซลล์ข้อความหนึ่งเซลล์ในหน้าต่างค้นหาหัวเรื่อง — ฐาน 1 ทั้งแถวและคอลัมน์"""

    row: int
    column: int
    value: object

    @property
    def has_section_number(self) -> bool:
        return resolve_sheet_role(self.value) is not None


@dataclass(frozen=True)
class TitleEvidence:
    """หลักฐานการเลือกหัวเรื่อง — เก็บไว้ให้ตรวจย้อนได้ว่าเลือกเพราะอะไร

    🔴 blocker #2 (Bo · 5 กันยายน 2569) — การเลือกหัวเรื่องต้อง **ตรวจสอบได้**
    ไม่ใช่ผลข้างเคียงของลำดับการวนลูป
    """

    chosen: TitleCandidate | None
    candidates: tuple[TitleCandidate, ...]

    @property
    def title(self) -> object:
        return self.chosen.value if self.chosen else None

    @property
    def numbered_candidates(self) -> tuple[TitleCandidate, ...]:
        return tuple(c for c in self.candidates if c.has_section_number)

    @property
    def displaced_numbered(self) -> tuple[TitleCandidate, ...]:
        """ผู้สมัครที่ **มีเลขข้อ** แต่ไม่ถูกเลือก

        ว่างเสมอเมื่อหัวเรื่องที่เลือกมีเลขข้ออยู่แล้ว — ใช้เป็นสัญญาณว่า
        ชีตนี้อาจถูกจัดเป็นชีตประกอบทั้งที่มีโครงสร้างของชีตหลัก
        """
        if self.chosen is not None and self.chosen.has_section_number:
            return ()
        return self.numbered_candidates


def title_candidates(rows: list[list[object]]) -> tuple[TitleCandidate, ...]:
    """เซลล์ข้อความทุกเซลล์ในหน้าต่างค้นหาหัวเรื่อง"""
    out: list[TitleCandidate] = []
    for r, row in enumerate(rows[:MAX_TITLE_SCAN_ROWS], start=1):
        for c, cell in enumerate(row, start=1):
            if isinstance(cell, str) and cell.strip():
                out.append(TitleCandidate(row=r, column=c, value=cell))
    return tuple(out)


def title_evidence(rows: list[list[object]]) -> TitleEvidence:
    """เลือกหัวเรื่องด้วย **คอลัมน์ซ้ายสุดก่อน แล้วจึงแถวบนสุด**

    🔴 **blocker #2 · Shadow Run 21011 รอบที่ 1** (แก้ 5 กันยายน 2569)

    เดิมไล่ **แถวก่อนคอลัมน์** แล้วหยิบข้อความแรกที่เจอ ⇒ เซลล์ธงของเครื่องมือ
    สร้างแฟ้มที่วางอยู่ **คอลัมน์ขวาสุดของแถวเหนือหัวเรื่องจริง** แย่งตำแหน่ง
    หัวเรื่องไปได้ทั้งชีต

    หลักฐานจากแฟ้มจริง ``AO_21011_HSRI_70.xlsx`` ชีต ``Sheet7_1``

    ========  ==============  ======================================
    ตำแหน่ง    เนื้อในเซลล์      ผลเดิม
    ========  ==============  ======================================
    ``N1``     ``"G"``         ถูกเลือกเป็นหัวเรื่อง ⇒ ไม่มีเลขข้อ
    ``A2``     ``"7. …"``      หัวเรื่องจริง — ถูกข้าม
    ========  ==============  ======================================

    ผลต่อเนื่อง: ชีตถูกจัดเป็น ``SUPPORTING`` ⇒ ทั้งชีตกลายเป็น ``UNMAPPED``
    ⇒ แผนงานที่มีสัดส่วนงบมากที่สุดของหน่วยงาน **ไม่เคยถูกเทียบ**
    และแถวของฝั่ง baseline ออกมาเป็น ``ROW_REMOVED`` ทั้งชุด

    🔑 **หลักฐานเชิงโครงสร้าง ไม่ hard-code ข้อความใด** — หัวเรื่องของเอกสาร
    ชุดนี้เป็น *ข้อความนำของคอลัมน์ข้อความซ้ายสุด* เสมอ ส่วนเซลล์ธงของเครื่องมือ
    อยู่ทางขวาของเขตข้อมูล การเรียงลำดับตาม ``(คอลัมน์, แถว)`` จึงแยกสองอย่างนี้
    ออกจากกันได้โดยไม่ต้องรู้จักถ้อยคำใด

    🔴 **ห้ามเลือกด้วย "มีเลขข้อ" อย่างเดียว** — ชีตประกอบที่ซ่อนอยู่ (``mask5``
    ``mask6`` ``mask7_1``) มีข้อความที่มีเลขข้ออยู่ในแถวล่างของบล็อกหัวรายงาน
    ถ้าใช้เกณฑ์นั้นชีตประกอบจะไหลเข้าผลหลักทันที (ดูข้อจำกัด ``B6``)
    """
    candidates = title_candidates(rows)
    if not candidates:
        return TitleEvidence(chosen=None, candidates=())
    chosen = min(candidates, key=lambda c: (c.column, c.row))
    return TitleEvidence(chosen=chosen, candidates=candidates)


def find_title(rows: list[list[object]]) -> object:
    """หาข้อความหัวเรื่องของชีต — ``A1`` ว่างได้

    จริง: ``Sheet123`` และ ``ข้อ 1-3`` มี ``A1 = None``
    โดยข้อความแรกอยู่ที่ ``A2``

    ดูเหตุผลของลำดับการเลือกที่ :func:`title_evidence`
    """
    return title_evidence(rows).title


def resolve_sheet_role(title: object) -> str | None:
    """คืนบทบาทของชีตจากเลขข้อในหัวเรื่อง — **เก็บเลขย่อยไว้ครบ**

    >>> resolve_sheet_role("5. เป้าหมายการให้บริการหน่วยงาน งบประมาณ…")
    'SECTION_05'
    >>> resolve_sheet_role("7.2 แผนงานพื้นฐานด้านการพัฒนา…")
    'SECTION_07_02'
    >>> resolve_sheet_role("ชื่อ-สกุล") is None
    True

    🔴 **ต้องเก็บเลขย่อย** — ในแฟ้มเดียวกันมีชีต ``7.`` · ``7.2`` · ``7.3``
    ถ้าตัดเหลือเลขหลักอย่างเดียวทั้งสามจะกลายเป็นบทบาทเดียวกันและจับคู่ผิด

    คืน ``None`` เมื่อไม่มีเลขข้อ — ผู้เรียกต้องจัดการเอง **ห้ามเดา**
    """
    number, _rest = split_leading_number(title)
    if number is None:
        return None
    parts = number.split(".")
    if not all(p.isdigit() for p in parts):
        return None
    return "SECTION_" + "_".join(f"{int(p):02d}" for p in parts)


#: บทบาทของชีตแผนงานและชีตโครงการ — **เลขข้อถูกยุบทิ้ง** ดูเหตุผลใน ``canonical_section``
SECTION_ROLE_PLAN = "SECTION_07_PLAN"
SECTION_ROLE_PROJECT = "SECTION_07_PROJECT"

#: เลขข้อหลักของกลุ่มชีตแผนงาน/โครงการ
_PLAN_SECTION_HEAD = "7"


#: เลขลำดับโครงการที่นำหน้าชื่อจริง — ``"โครงการที่ 2 : โครงการขับเคลื่อน…"``
_PROJECT_ORDINAL = re.compile(r"^(โครงการที่\s*\d+)\s*[:：]\s*(.+)$")


def split_project_title(title: object) -> tuple[str | None, str]:
    """แยก **เลขลำดับโครงการ** ออกจาก **ชื่อโครงการ**

    คืน ``(ordinal_raw, semantic_name)`` — ``ordinal_raw`` เป็น ``None`` ถ้าไม่มี

    🔴 **เลขลำดับไม่ใช่ identity** (คำตัดสิน Gift · ทาง (ค) · 1 ก.ย. 2569)
    พิสูจน์แล้วจากไฟล์จริงของหน่วยงาน 21016

    * FY2569 ``7.4.2`` = *โครงการที่ **2** : โครงการขับเคลื่อนงานวัคซีนกับองค์กรภาคีเครือข่าย*
    * FY2570 ``7.3.3`` = *โครงการที่ **3** : โครงการขับเคลื่อนงานวัคซีนกับองค์กรภาคีเครือข่าย*

    ชื่อหลัง ``:`` เหมือนกันทุกตัวอักษร ต่างเฉพาะเลขลำดับ
    ⇒ ใช้ชื่อเป็น semantic identity และเก็บเลขลำดับไว้เป็น comparison/provenance

    >>> split_project_title("โครงการที่ 2 : โครงการขับเคลื่อนงานวัคซีน")
    ('โครงการที่ 2', 'โครงการขับเคลื่อนงานวัคซีน')
    >>> split_project_title("แผนงานพื้นฐาน")
    (None, 'แผนงานพื้นฐาน')
    """
    text = normalize_label(title)
    m = _PROJECT_ORDINAL.match(text)
    if not m:
        return None, text
    return m.group(1), m.group(2).strip()


def canonical_section(title: object) -> tuple[str | None, str]:
    """คืน ``(sheet_role ที่ใช้เป็นคีย์, section_title_norm)``

    🔴 **เลขข้อของชีตแผนงาน/โครงการ ใช้เป็นคีย์ไม่ได้ — พิสูจน์แล้วจากไฟล์จริง**

    หน่วยงาน 21016
      * ``7.3`` ปี 2569 = *แผนงานยุทธศาสตร์ส่งเสริมความสัมพันธ์ระหว่างประเทศ*
      * ``7.3`` ปี 2570 = *แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี*
      * ``7.4`` ปี 2569 = *แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี* ← ตรงกับ ``7.3`` ปี 2570

    หน่วยงาน 21011 ก็เกิดอาการเดียวกันที่ ``7.3``

    ⇒ การจับคู่ด้วยเลขข้อจะเทียบ **คนละแผนงาน** เข้าด้วยกันโดยไม่มีสัญญาณผิดพลาดใด
    และจะพลาดคู่ที่เป็นแผนงานเดียวกันแต่ถูกเรียงเลขใหม่

    วิธีที่ใช้แทน: ยุบเลขข้อของกลุ่ม ``7.x`` ทิ้ง แล้วใช้ **ชื่อแผนงาน/โครงการ**
    เป็นตัวระบุ โดยแยกชั้นแผนงาน (``7.x``) ออกจากชั้นโครงการ (``7.x.y``)
    เพื่อไม่ให้จับคู่ข้ามชั้น

    ส่วนชีตโครงสร้างคงที่ (``4.`` ``5.`` ``6.`` ``7.`` ``8.``) ใช้เลขข้อได้ตามเดิม
    และ **ห้าม**นำหัวเรื่องเข้าคีย์ เพราะหัวเรื่องของ ``4.`` และ ``6.`` ฝังปีงบประมาณไว้
    """
    number, rest = split_leading_number(title)
    role = resolve_sheet_role(title)
    if role is None or number is None:
        return None, ""
    parts = number.split(".")
    if parts[0] == _PLAN_SECTION_HEAD and len(parts) >= 2:
        if len(parts) == 2:
            return SECTION_ROLE_PLAN, strip_fiscal_years(rest)
        # ชั้นโครงการ — ตัดเลขลำดับ "โครงการที่ N :" ออกจาก identity
        _ordinal, semantic = split_project_title(rest)
        return SECTION_ROLE_PROJECT, strip_fiscal_years(semantic)
    return role, ""


def resolve_document_level(title: object) -> str:
    """แยกระดับกระทรวงกับระดับหน่วยงานจาก **วลีเฉพาะ** ในหัวเรื่อง

    🔴 บังคับตามคำสั่ง Gift ข้อ 9 — **ห้ามจับคู่ข้ามระดับ**
    เพราะป้ายแถวเหมือนกันทุกตัวอักษรได้ เช่น ``รวมทั้งสิ้น``
    ที่ระดับกระทรวงมีค่า 173,390.171 แต่ระดับหน่วยงานมีค่า 53.2712

    🔴 **ห้ามจับคำว่า "กระทรวง" ลอย ๆ** — ชีตปกของแฟ้มระดับหน่วยงาน
    ก็เขียนชื่อกระทรวงต้นสังกัดไว้ การจับคำลอย ๆ จะระบุระดับผิดทั้งแฟ้ม
    """
    text = normalize_label(title)
    if any(p in text for p in _MINISTRY_PHRASES):
        return DOCUMENT_LEVEL_MINISTRY
    if any(p in text for p in _AGENCY_PHRASES):
        return DOCUMENT_LEVEL_AGENCY
    return DOCUMENT_LEVEL_UNKNOWN


def resolve_plan_role(text: object) -> str:
    """จับแผนงานจากข้อความ — คืน ``NOT_APPLICABLE`` เมื่อไม่พบคำบ่งชี้"""
    value = normalize_label(text)
    for marker, role in _PLAN_MARKERS:
        if marker in value:
            return role
    return PLAN_NOT_APPLICABLE


def classify_sheet(facts: SheetFacts) -> str:
    """จำแนกชีตหลักออกจากชีตฐานข้อมูลประกอบด้วย **ลายเซ็นเนื้อหา**

    🔴 **ห้ามใช้ prefix ตัวอักษร** — วิธีเดิม ``("b","B")`` เป็น defect ที่จับชีต
    ``บุค`` (บ ภาษาไทย · 837 แถว) ไม่ได้ และปล่อยให้ไหลเข้าผลหลักทั้งก้อน

    ลายเซ็นที่ใช้แทน (จากที่วัดได้จริงในไฟล์ทั้ง 6):

    ================  =========================  ==========================
    คุณสมบัติ          ชีตหลัก                     ชีตประกอบ
    ================  =========================  ==========================
    หัวเรื่อง          มีเลขข้อ                    ไม่มีเลขข้อ
    merged cells      มี (1–104 ช่วง)             ``0`` ทุกชีต
    ================  =========================  ==========================

    ``COVER`` = **ชีตแรกของแฟ้ม** ที่ไม่มีเลขข้อ

    ⚠️ **`DATASET-BOUNDED HEURISTIC`** — เกณฑ์ ``index == 0`` ยืนยันแล้วกับ
    ชุดข้อมูล ``T1B`` ปัจจุบัน **6 แฟ้มเท่านั้น** (``Sheet123`` · ``ข้อ 1-3`` ·
    ``ภาพรวม`` อยู่ที่ index 0 ทุกแฟ้ม) · แฟ้มจากหน่วยงานอื่นหรือปีอื่น
    อาจวางชีตปกไว้ตำแหน่งอื่น ⇒ **ต้องทบทวนเกณฑ์นี้ก่อนขยายชุดข้อมูล**

    🔴 **ห้ามใช้จำนวน merged cells เป็นเกณฑ์ของ COVER** — ชีตประกอบบางชีต
    มี merged cell ติดมาบ้าง ทำให้ชีตเดียวกัน (``bพฐ``) ถูกจัดเป็น ``COVER``
    ในแฟ้มหนึ่งแต่เป็น ``SUPPORTING`` ในอีกแฟ้ม (พบใน key stability audit)

    **fail-safe:** ชีตที่ไม่มีเลขข้อ ไม่ใช่ชีตแรก และ **ไม่มีเนื้อหาพอให้ตัดสิน**
    (ไม่มีทั้งหัวเรื่องและแถวข้อมูล) คืน ``UNKNOWN`` — **ห้ามเดา**
    ผู้เรียกต้องยกเป็น ``UNMAPPED`` ให้มนุษย์ตรวจ
    """
    if resolve_sheet_role(facts.a1) is not None:
        return SHEET_CLASS_MAIN
    if facts.index == 0:
        return SHEET_CLASS_COVER
    if not normalize_label(facts.a1) and facts.max_row <= 1:
        # หลักฐานไม่พอให้ตัดสิน — ห้ามเดาว่าเป็นชีตประกอบ
        return SHEET_CLASS_UNKNOWN
    return SHEET_CLASS_SUPPORTING
