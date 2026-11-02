# -*- coding: utf-8 -*-
"""หมวดจุดตรวจสอบ — *สิ่งที่เปลี่ยนคืออะไร* แยกจาก *เกิดอะไรขึ้น*

🔴 **คำตัดสินกิ๊ฟ (7 ก.ย. 2569)** — สองมิตินี้ต้องแยกกันเด็ดขาด

``finding_type``
    เกิดอะไรขึ้น — ``AMOUNT_DECREASED`` · ``ROW_ADDED`` · ``UNIT_CHANGED``
``subject_category``
    สิ่งที่เปลี่ยนคืออะไร — จำนวนเงิน ตัวชี้วัด ผลลัพธ์ โครงการ หรือกิจกรรม

🔴 **ห้าม map แบบเหมารวม** — กิ๊ฟไม่อนุมัติการโยน ``ROW_ADDED`` ·
``ROW_REMOVED`` · ``PROJECT_ORDINAL_CHANGED`` เข้าโครงการ/กิจกรรมทั้งก้อน
ต้องดู **บทบาทเชิงความหมาย ป้ายแถว และบริบท** ของแถวนั้นจริง ๆ

ตัวอย่างที่กิ๊ฟให้ไว้ และเป็นเคสทดสอบในชุดนี้

============================================  =========================
สถานการณ์                                      หมวดที่ต้องได้
============================================  =========================
``ROW_REMOVED`` + บทบาทเป็นกิจกรรม               ``ACTIVITY``
``ROW_REMOVED`` + บทบาทเป็นตัวชี้วัด              ``INDICATOR``
``UNIT_CHANGED`` ของค่าเป้าหมาย                  ``OUTCOME``
หลักฐานไม่พอ                                    ``OTHER_OR_UNCLASSIFIED``
============================================  =========================

🔴 **ห้ามเดาหมวดเพื่อให้ครบ** — จัดไม่ได้ต้องอยู่หมวดที่หกพร้อมเหตุผลที่อ่านออก
ทุกผลจึงพก :attr:`~SubjectClassification.evidence` และ
:attr:`~SubjectClassification.confidence` ติดตัวเสมอ เพื่อให้ผู้ตรวจเถียงกลับได้

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ── หมวด ───────────────────────────────────────────────────────────────────
CAT_AMOUNT = "AMOUNT"
CAT_INDICATOR = "INDICATOR"
CAT_OUTCOME = "OUTCOME"
CAT_PROJECT = "PROJECT"
CAT_ACTIVITY = "ACTIVITY"
CAT_OTHER = "OTHER_OR_UNCLASSIFIED"

CATEGORY_ORDER = (CAT_AMOUNT, CAT_INDICATOR, CAT_OUTCOME, CAT_PROJECT,
                  CAT_ACTIVITY, CAT_OTHER)

CATEGORY_LABELS = {
    CAT_AMOUNT: "จำนวนเงิน",
    CAT_INDICATOR: "ตัวชี้วัด",
    CAT_OUTCOME: "ผลลัพธ์/ค่าเป้าหมาย",
    CAT_PROJECT: "ชื่อโครงการ",
    CAT_ACTIVITY: "ชื่อกิจกรรม",
    CAT_OTHER: "อื่น ๆ/ยังจัดหมวดไม่ได้",
}

# ── ระดับความมั่นใจ ─────────────────────────────────────────────────────────
CONF_HIGH = "HIGH"        # หลักฐานตรงตัว เช่นชนิด finding บอกเองว่าเป็นอะไร
CONF_MEDIUM = "MEDIUM"    # อนุมานจากป้ายแถวหรือบทบาทของชีต
CONF_LOW = "LOW"          # ใช้กับหมวดที่หกเท่านั้น — แปลว่ายังไม่รู้

CONFIDENCE_LABELS = {
    CONF_HIGH: "สูง — หลักฐานตรงตัว",
    CONF_MEDIUM: "ปานกลาง — อนุมานจากป้ายหรือบทบาท",
    CONF_LOW: "ต่ำ — หลักฐานไม่พอ",
}

# ── คำที่บ่งบทบาทเชิงความหมายของแถว ────────────────────────────────────────
# 🔴 เรียงจากเฉพาะเจาะจงไปกว้าง · "ตัวชี้วัด" ต้องมาก่อน "เป้าหมาย"
# เพราะข้อความจริงมักเขียนว่า "ตัวชี้วัดเชิงปริมาณ : เป้าหมาย …"
_ROLE_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (CAT_INDICATOR, ("ตัวชี้วัด", "ตัวชี้วัดเชิงปริมาณ", "ตัวชี้วัดเชิงคุณภาพ",
                     "kpi")),
    (CAT_OUTCOME, ("ค่าเป้าหมาย", "เป้าหมายการให้บริการ", "ผลลัพธ์",
                   "ผลสัมฤทธิ์", "เป้าหมาย")),
    (CAT_PROJECT, ("โครงการที่", "ชื่อโครงการ", "โครงการ")),
    (CAT_ACTIVITY, ("กิจกรรมที่", "ชื่อกิจกรรม", "กิจกรรม", "ผลผลิต",
                    "ผลผลิตที่")),
)

#: ชีต "5. เป้าหมายการให้บริการหน่วยงาน" — บทบาทเชิงโครงสร้างที่บอกผลลัพธ์
_OUTCOME_SHEET_ROLES = ("SECTION_05",)
#: กลุ่มชีตแผนงาน/โครงการ
_PROJECT_SHEET_ROLES = ("SECTION_07_PROJECT",)

_AMOUNT_TYPES = ("AMOUNT_INCREASED", "AMOUNT_DECREASED", "AMOUNT_UNCHANGED")
_INDICATOR_TYPES = ("INDICATOR_CHANGED", "INDICATOR_UNCHANGED")
#: ชนิดที่พูดถึง **การเทียบ** ไม่ใช่พูดถึงตัวสิ่งที่เปลี่ยน ⇒ ห้ามเดาหมวดจากมัน
_COMPARISON_TYPES = ("NOT_COMPARABLE", "AMBIGUOUS_REQUIRES_HUMAN_REVIEW",
                     "UNMAPPED_REQUIRES_HUMAN_REVIEW",
                     "YEAR_PRESENT_ON_ONE_SIDE_ONLY")

_WS = re.compile(r"\s+")


def _norm(text) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFC", str(text or ""))).strip().lower()


@dataclass(frozen=True)
class SubjectClassification:
    """ผลการจัดหมวดหนึ่งใบ — **อธิบายที่มาได้เสมอ**"""

    category: str
    confidence: str
    #: กฎที่ยิงและค่าที่ใช้ตัดสิน เช่น ``"row_label~ตัวชี้วัด"``
    evidence: tuple[str, ...]
    #: เหตุผลที่จัดไม่ได้ — ว่างเมื่อจัดได้
    reason: str = ""

    @property
    def label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category)

    @property
    def confidence_label(self) -> str:
        return CONFIDENCE_LABELS.get(self.confidence, self.confidence)

    @property
    def classified(self) -> bool:
        return self.category != CAT_OTHER


def _role_from_text(*texts) -> tuple[str, str] | None:
    """หาบทบาทเชิงความหมายจากข้อความ — คืน ``(หมวด, หลักฐาน)``"""
    for raw in texts:
        text = _norm(raw)
        if not text:
            continue
        for category, words in _ROLE_WORDS:
            for word in words:
                if word.lower() in text:
                    return category, f"พบคำ “{word}” ในข้อความของแถว"
    return None


def classify_subject(finding) -> SubjectClassification:
    """จัดหมวดว่า **สิ่งที่เปลี่ยน** ในข้อสังเกตใบนี้คืออะไร

    รับ :class:`~redbook.services.t1b.FindingView` (หรืออะไรก็ตามที่มีฟิลด์
    ชุดเดียวกัน) — ไม่แตะตัวเครื่องยนต์ เป็นนโยบายของผลิตภัณฑ์ล้วน

    ลำดับการตัดสิน — เรียงตาม **ความแข็งของหลักฐาน** ไม่ใช่ความสะดวก

    1. ชนิด ``AMOUNT_*`` ⇒ สิ่งที่เปลี่ยนคือ *ยอดเงิน* เอง ⇒ :data:`CAT_AMOUNT`
       (ป้ายแถวบอกว่ายอดของ *อะไร* ซึ่งเป็นบริบท ไม่ใช่ตัวสิ่งที่เปลี่ยน)
    2. ชนิด ``INDICATOR_*`` ⇒ :data:`CAT_INDICATOR`
    3. ชนิดที่พูดถึงการเทียบ (``NOT_COMPARABLE`` ``UNMAPPED`` ฯลฯ)
       ⇒ :data:`CAT_OTHER` **ทันที** ไม่ต้องดูป้าย — เพราะยังไม่รู้ด้วยซ้ำ
       ว่าแถวนั้นคืออะไร การเดาจากป้ายตรงนี้คือการเดาเพื่อให้ครบ
    4. ที่เหลือ (``ROW_ADDED`` ``ROW_REMOVED`` ``UNIT_CHANGED``
       ``PROJECT_ORDINAL_CHANGED``) ⇒ ดูป้ายแถวและหัวข้อ แล้วจึงดูบทบาทของชีต
    5. ไม่เข้าเกณฑ์ใด ⇒ :data:`CAT_OTHER` พร้อมเหตุผล
    """
    ftype = str(getattr(finding, "finding_type", "") or "")
    row_label = getattr(finding, "row_label", "") or ""
    section_title = getattr(finding, "section_title", "") or ""
    parent_plan = getattr(finding, "parent_plan", "") or ""
    sheet_role = str(getattr(finding, "sheet_role", "") or "")

    if ftype in _AMOUNT_TYPES:
        return SubjectClassification(
            CAT_AMOUNT, CONF_HIGH,
            (f"finding_type={ftype} — สิ่งที่เปลี่ยนคือยอดเงินโดยตรง",))

    if ftype in _INDICATOR_TYPES:
        return SubjectClassification(
            CAT_INDICATOR, CONF_HIGH, (f"finding_type={ftype}",))

    if ftype in _COMPARISON_TYPES:
        return SubjectClassification(
            CAT_OTHER, CONF_LOW, (f"finding_type={ftype}",),
            "ข้อสังเกตชนิดนี้บอกว่า *เทียบไม่ได้หรือยังตีความไม่ได้* "
            "จึงยังไม่ทราบว่าสิ่งที่เปลี่ยนคืออะไร — การจัดหมวดจากป้ายแถว "
            "ตรงนี้จะเป็นการเดาเพื่อให้ครบ")

    hit = _role_from_text(row_label, section_title, parent_plan)
    if hit is not None:
        category, why = hit
        return SubjectClassification(category, CONF_MEDIUM,
                                     (f"finding_type={ftype}", why))

    if sheet_role in _OUTCOME_SHEET_ROLES:
        return SubjectClassification(
            CAT_OUTCOME, CONF_MEDIUM,
            (f"finding_type={ftype}",
             f"sheet_role={sheet_role} — ชีตเป้าหมายการให้บริการหน่วยงาน"))
    if sheet_role in _PROJECT_SHEET_ROLES:
        return SubjectClassification(
            CAT_PROJECT, CONF_MEDIUM,
            (f"finding_type={ftype}", f"sheet_role={sheet_role} — ชีตโครงการ"))

    return SubjectClassification(
        CAT_OTHER, CONF_LOW,
        tuple(x for x in (f"finding_type={ftype}",
                          f"row_label={row_label[:40]}" if row_label else "",
                          f"sheet_role={sheet_role}" if sheet_role else "")
              if x),
        "ไม่พบคำหรือบทบาทที่บอกได้ว่าแถวนี้เป็นตัวชี้วัด ผลลัพธ์ โครงการ "
        "หรือกิจกรรม และไม่ใช่ข้อสังเกตเรื่องยอดเงิน")


__all__ = [
    "CAT_AMOUNT", "CAT_INDICATOR", "CAT_OUTCOME", "CAT_PROJECT",
    "CAT_ACTIVITY", "CAT_OTHER", "CATEGORY_ORDER", "CATEGORY_LABELS",
    "CONF_HIGH", "CONF_MEDIUM", "CONF_LOW", "CONFIDENCE_LABELS",
    "SubjectClassification", "classify_subject",
]
