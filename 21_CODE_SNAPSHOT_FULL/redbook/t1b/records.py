# -*- coding: utf-8 -*-
"""T1B — โครงสร้าง canonical record

🔴 **ห้ามทิ้งค่าดิบหลัง normalize** (คำสั่ง Gift · 1 ก.ย. 2569 ข้อ A)
ทุก record เก็บทั้ง ``raw_label`` / ``raw_value`` และตำแหน่งเซลล์จริง
เพื่อให้ trace finding กลับไปยัง Excel ต้นฉบับได้เสมอ

การแบ่งฟิลด์เป็นสามกลุ่มตาม ``T1B_CANONICAL_KEY_SPEC.md``

=================  ==========================================================
กลุ่ม               ใช้ทำอะไร
=================  ==========================================================
IDENTITY           ระบุตัวตนของรายการ — เข้า ``T1BKey``
COMPARISON         สิ่งที่นำมาเทียบ — **ห้าม**อยู่ในคีย์
PROVENANCE         ชี้หลักฐานกลับไฟล์ต้นทาง — **ห้าม**ใช้จับคู่
=================  ==========================================================
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .categories import CATEGORY_UNRESOLVED
from .keys import T1BKey

#: ชนิดของ record
ROW_KIND_VALUE = "VALUE"            # เซลล์ค่าหนึ่งช่อง (แถว × ปี)
ROW_KIND_STRUCTURAL = "STRUCTURAL"  # แถวหัวข้อ/ป้าย ไม่มีค่าตัวเลข
ROW_KIND_UNMAPPED = "UNMAPPED"      # อ่านได้แต่ยังตีความโครงสร้างไม่ได้
#: G6 (#14) — เซลล์ตัวเลขในเขตค่าของตารางรายปี ที่หัวคอลัมน์อ่านไม่ออก
#: 🔴 หนึ่ง record ต่อ (แถว × คอลัมน์) · ห้ามคืนค่าว่าง (เดิมหายเงียบ)
ROW_KIND_UNSUPPORTED_PERIOD = "UNSUPPORTED_PERIOD"
#: invariant (#14) — เซลล์ตัวเลขในเขตค่าของ **ตารางจำแนกตามงบรายจ่าย** ที่คอลัมน์
#: ไม่มีหัว/หัวว่าง · แยกจาก ``UNSUPPORTED_PERIOD`` เพราะแกนของตารางไม่ใช่เวลา
ROW_KIND_UNSUPPORTED_COLUMN = "UNSUPPORTED_COLUMN"

#: แกนที่ใช้เทียบค่า — **ต้องระบุชัด ห้ามอนุมานจากฟิลด์ที่ว่าง**
#: (BO REVIEW · 1 กันยายน 2569)
AXIS_FISCAL_YEAR = "FISCAL_YEAR"
AXIS_BUDGET_CATEGORY = "BUDGET_CATEGORY"
#: G5 (#14) — คอลัมน์ช่วงเวลา (เปิดหัว · เปิดท้าย · ช่วงปี) · แยกจากแกนปีเดิม
#: 🔴 จับคู่ได้เฉพาะเมื่อ :attr:`T1BRecord.period_label` ตรงกันทุกตัวอักษร
AXIS_PERIOD_RANGE = "PERIOD_RANGE"
#: G1 (#14) — แถว "ป้าย + ค่าเดี่ยว + หน่วย" นอกตารางใด ๆ · ไม่มีแกนปี/หมวด
#: ปีบริบทอยู่ที่ ``category_table_fiscal_year`` (ที่มา ``workbook_cover``) เหมือนตารางแกนหมวด
#: 🔴 roll-up รายปีจึงไม่หยิบ record แกนนี้ไปรวม — กันนับวงเงินตลอดอายุโครงการซ้ำกับยอดปี
AXIS_SINGLE_AMOUNT = "SINGLE_AMOUNT"
AXIS_UNRESOLVED = "UNRESOLVED"

#: ที่มาของปีบริบทของตารางจำแนกตามงบรายจ่าย — ดู ``category_table_year_source``
CAT_YEAR_FROM_SECTION_TITLE = "section_title"
CAT_YEAR_FROM_WORKBOOK_COVER = "workbook_cover"

#: เครื่องหมายความไม่แน่นอน — ต้องปรากฏใน ``uncertainty`` ของ envelope ด้วย
UNC_AGENCY_CODE_FROM_FILENAME = "agency_code_from_filename"
UNC_DOC_STATUS_FROM_FILENAME = "document_status_from_filename"
UNC_HEADER_NOT_LOCATED = "header_row_not_located"
UNC_UNIT_UNRESOLVED = "declared_unit_unresolved"
UNC_SUPPORTING_LAYOUT_NOT_MAPPED = "supporting_sheet_layout_not_mapped"
UNC_NO_YEAR_COLUMNS = "no_year_columns_in_header"
#: แถวที่อยู่นอกตารางรายปีใด ๆ เช่น ตารางจำแนกตามงบรายจ่ายในชีต 7.x
#: 🔴 ยังไม่ map — ต้องบันทึกไว้ ห้ามทิ้งเงียบ
UNC_ROWS_OUTSIDE_YEAR_TABLE = "rows_outside_year_table_not_mapped"
UNC_UNIT_FROM_SHEET_DECLARATION = "unit_from_sheet_level_declaration"
#: แกนเทียบไม่ถูกต้อง — มีทั้งปีและหมวด หรือไม่มีทั้งคู่
UNC_AXIS_INVALID = "invalid_comparison_axis"
#: หัวคอลัมน์หมวดงบรายจ่ายที่ resolve ไม่ได้ — 🔴 ห้ามเดา ห้ามข้าม
UNC_CATEGORY_UNRESOLVED = "budget_category_unresolved"
#: ขอบเขตตารางแข่งกันจนตัดสินไม่ได้ — 🔴 ห้ามเดาว่าแถวเป็นของตารางใด
#: (blocker #4 · คำสั่ง Bo · 3 กันยายน 2569)
UNC_TABLE_BOUNDARY_AMBIGUOUS = "table_boundary_ambiguous"
#: ชื่อโครงการซ้ำภายในแผนงานเดียวกัน — 🔴 ห้าม collapse อัตโนมัติ
#: (คำตัดสิน Gift · ทาง (ค) · 1 ก.ย. 2569)
UNC_AMBIGUOUS_PROJECT_TITLE = "ambiguous_project_title_within_plan"
#: หัวเรื่องชีตถูกเลือกทั้งที่มีผู้สมัครอีกตัวที่ **มีเลขข้อ** — 🔴 ชีตนี้อาจ
#: เป็นชีตหลักที่หลุดจากการตรวจ (blocker #2 · Shadow Run 21011 รอบที่ 1)
UNC_SHEET_TITLE_AMBIGUOUS = "sheet_title_selection_ambiguous"
#: ตารางจำแนกตามงบรายจ่ายไม่มีปีบริบท — 🔴 ห้ามเทียบข้ามแฟ้มโดยไม่ติดป้ายปี
#: (blocker #1 · Shadow Run 21011 รอบที่ 1 · เกณฑ์หยุดทันทีข้อ 6)
UNC_CATEGORY_TABLE_YEAR_UNRESOLVED = "category_table_fiscal_year_unresolved"
#: ตัวตนหน่วยงานอ่านจากเนื้อในแฟ้มไม่ได้ — จัดการที่ **ชั้นจับคู่** ไม่ใช่รายรายการ
#: (blocker #3 · Shadow Run 21011 รอบที่ 1)
UNC_AGENCY_IDENTITY_UNRESOLVED = "agency_identity_not_in_workbook_content"
#: G6 (#14) — หัวคอลัมน์ในเขตค่าอ่านไม่ออก แต่มีตัวเลข · ต้องให้คนตรวจ
UNC_UNSUPPORTED_PERIOD_LABEL = "UNSUPPORTED_PERIOD_LABEL_REQUIRES_REVIEW"
#: G5 (#14) — ป้ายช่วงเวลาของแถวเดียวกันไม่ตรงกันสองฝั่ง ⇒ ไม่จับคู่อัตโนมัติ
#: 🔴 ห้ามจับคู่เพียงเพราะปีเริ่มต้นตรงกัน (คำตัดสินกิ๊ฟ 8 ก.ย. 2569 ข้อ 2)
UNC_PERIOD_LABEL_CHANGED = "PERIOD_LABEL_CHANGED_REQUIRES_REVIEW"
#: invariant (#14) — คอลัมน์ในตารางจำแนกตามงบรายจ่ายที่ไม่มีหัวแต่มีตัวเลข
UNC_UNSUPPORTED_VALUE_COLUMN = "UNSUPPORTED_VALUE_COLUMN_REQUIRES_REVIEW"
#: invariant (#14) — ตาข่ายนิรภัย: เซลล์ตัวเลขที่ไม่มี record ใดครอบหลังสกัดทุกตาราง
#: (เช่น ตัวเลขในแถวหัวตาราง) ⇒ บันทึกทั้งแถวเป็น UNMAPPED · 🔴 ห้ามหายเงียบ
UNC_NUMERIC_CELL_NOT_ACCOUNTED = "numeric_cell_not_accounted_by_any_table"
#: G1 (#14) — ปีบริบทของแถวค่าเดี่ยวมาจากปีของเอกสาร (ชีตปก) · บันทึกให้ตรวจย้อนได้ ไม่ blocking
UNC_FISCAL_YEAR_FROM_COVER = "fiscal_year_from_workbook_cover"
#: G1 — อ่านปีของเอกสารไม่ได้ ⇒ ห้ามเทียบข้ามแฟ้มโดยไม่รู้ว่าเป็นยอดปีใด
UNC_SINGLE_AMOUNT_YEAR_UNRESOLVED = "single_amount_fiscal_year_unresolved"
#: G1 — แถวค่าเดี่ยวสองแถวขึ้นไปในชีตเดียวได้คีย์เดียวกัน ⇒ ห้ามจับคู่อัตโนมัติ
UNC_SINGLE_AMOUNT_KEY_AMBIGUOUS = "single_amount_key_ambiguous"
#: G1 — มีข้อความต่อท้ายหลังเซลล์หน่วย (เช่น โทเคนแม่แบบ) · บันทึกไว้ ไม่ blocking
UNC_TRAILING_TEXT_AFTER_UNIT = "trailing_text_after_unit"
#: G2 (#14) — บล็อกชีตประกอบผูกกับบริบทของชีตหลักด้วยชื่อไม่สำเร็จ (ไม่พบ/พบหลายแห่ง)
#: 🔴 record ยังออก แต่ห้ามจับคู่อัตโนมัติ · ห้ามยุบรวมเงียบ
UNC_PARENT_LINK_UNRESOLVED = "parent_link_unresolved"
#: G2/G3 (#14) — ผูกได้หลังลบการขึ้นบรรทัดในเซลล์เท่านั้น · บันทึกไว้ ไม่ blocking
UNC_PARENT_LINK_VIA_LINE_BREAK_JOIN = "parent_link_matched_after_joining_line_breaks"

#: เครื่องหมายที่ **บังคับ** ให้ต้องมีมนุษย์ตรวจ
#:
#: ``UNC_UNIT_FROM_SHEET_DECLARATION`` **ไม่อยู่ในชุดนี้** เพราะเป็นการ resolve
#: ที่สำเร็จ เพียงแต่มาจากการประกาศระดับชีตแทนคอลัมน์รายแถว —
#: บันทึกไว้ให้ตรวจย้อนได้ ไม่ใช่ความกำกวม
#:
#: ``UNC_AGENCY_CODE_FROM_FILENAME`` และ ``UNC_DOC_STATUS_FROM_FILENAME``
#: ก็ไม่อยู่ในชุดนี้ เพราะเป็นข้อจำกัดระดับไฟล์ที่ติดกับ **ทุก** record เท่ากัน
#: ถ้านับเป็นเหตุให้ต้องตรวจ ทุก record จะเข้าคิวหมดจนคิวไม่มีความหมาย
#: ``UNC_AGENCY_IDENTITY_UNRESOLVED`` ก็ไม่อยู่ในชุดนี้ด้วยเหตุผลเดียวกัน —
#: เป็นเงื่อนไข **ระดับแฟ้ม** ที่ต้องออกเป็นสัญญาณเดียวที่ชั้นจับคู่
#: (``matching.identity_conflict``) ไม่ใช่ธงรายรายการ 1,752 ใบ
BLOCKING_UNCERTAINTY = frozenset({
    UNC_SHEET_TITLE_AMBIGUOUS,
    UNC_CATEGORY_TABLE_YEAR_UNRESOLVED,
    UNC_UNIT_UNRESOLVED,
    UNC_HEADER_NOT_LOCATED,
    UNC_NO_YEAR_COLUMNS,
    UNC_SUPPORTING_LAYOUT_NOT_MAPPED,
    UNC_AMBIGUOUS_PROJECT_TITLE,
    UNC_ROWS_OUTSIDE_YEAR_TABLE,
    UNC_TABLE_BOUNDARY_AMBIGUOUS,
    UNC_AXIS_INVALID,
    UNC_CATEGORY_UNRESOLVED,
    UNC_UNSUPPORTED_PERIOD_LABEL,
    UNC_PERIOD_LABEL_CHANGED,
    UNC_UNSUPPORTED_VALUE_COLUMN,
    UNC_NUMERIC_CELL_NOT_ACCOUNTED,
    UNC_SINGLE_AMOUNT_YEAR_UNRESOLVED,
    UNC_SINGLE_AMOUNT_KEY_AMBIGUOUS,
    UNC_PARENT_LINK_UNRESOLVED,
})


@dataclass(frozen=True)
class T1BRecord:
    """หนึ่งรายการที่สกัดจากสมุดงาน T1B"""

    # ---------------- IDENTITY ----------------
    key: T1BKey
    row_kind: str = ROW_KIND_VALUE

    # ---------------- COMPARISON ----------------
    fiscal_year: int | None = None
    fiscal_year_label: str | None = None     # ป้ายดิบ เช่น "ปี 2568"
    #: แกนที่ใช้เทียบ — ``FISCAL_YEAR`` หรือ ``BUDGET_CATEGORY``
    #: 🔴 ระบุชัดเสมอ ห้ามอนุมานจากฟิลด์ที่ว่าง (BO REVIEW)
    comparison_axis: str = AXIS_UNRESOLVED
    #: หมวดงบรายจ่ายแบบ canonical เช่น ``SUBSIDY``
    #: 🔴 เป็น **comparison attribute** เหมือน ``fiscal_year`` ไม่ใช่ identity
    budget_category: str | None = None
    #: ปีบริบทของ **ตารางจำแนกตามงบรายจ่าย** — blocker #1
    #:
    #: ตารางแกนหมวดถูกบังคับให้ ``fiscal_year = None`` ตาม truth table ของ
    #: :attr:`axis_valid` แต่ตารางในแฟ้มจริง **ผูกกับปีของเอกสาร** เสมอ
    #: ⇒ เมื่อจับคู่สองแฟ้มที่คนละปี finding จะเทียบยอดคนละปีโดยช่องปีว่าง
    #: (เกณฑ์หยุดทันทีข้อ 6 · ``B2`` ของ Shadow Run รอบที่ 1)
    #:
    #: 🔴 ฟิลด์นี้เป็น **comparison context ไม่ใช่ identity และไม่ใช่ ``fiscal_year``**
    #: จึงไม่ทำให้ XOR ของ :attr:`axis_valid` เสีย และไม่แตะคีย์ที่ freeze แล้ว
    category_table_fiscal_year: int | None = None
    #: ที่มาของ :attr:`category_table_fiscal_year` — ``section_title`` (หัวเรื่องชีต)
    #: หรือ ``workbook_cover`` (ปีของเอกสารจากชีตปก) · ว่าง = ไม่มีปีบริบท
    #: 🔴 ต้องรายงานที่มาเสมอ ห้ามให้ผู้อ่านเดาว่าปีมาจากไหน
    category_table_year_source: str = ""
    #: G5 (#14) — ป้ายช่วงเวลาหลัง normalization อนุรักษนิยม (แกน ``PERIOD_RANGE``)
    #: 🔴 comparison attribute ไม่ใช่ identity · ป้ายดิบอยู่ที่ ``fiscal_year_label``
    period_label: str | None = None
    #: G1/RC-E (#14) — บทบาทเชิงเวลาของยอด เช่น ``PROJECT_LIFETIME_CEILING``
    #: ว่าง = ยอดทั่วไป · ดู ``redbook.t1b.temporal``
    amount_role: str = ""
    #: ที่มาของ ``amount_role`` — ``label`` หรือ ``parent_heading``
    amount_role_source: str = ""
    declared_unit: str = ""
    is_monetary: bool = False
    value_decimal: Decimal | None = None

    # ---------------- PROVENANCE (ห้ามใช้จับคู่) ----------------
    raw_label: object = None                 # ข้อความดิบก่อน normalize
    raw_value: object = None                 # ค่าดิบก่อนแปลงเป็น Decimal
    raw_unit_cell: object = None             # เนื้อในเซลล์หน่วยนับตามจริง
    budget_category_raw: object = None       # หัวคอลัมน์หมวดดิบ เช่น "งบเงินอุดหนุน"
                                             # 🔴 ห้ามทิ้ง — provenance
    section_title_raw: object = None         # หัวเรื่องชีตดิบก่อน normalize
                                             # 🔴 ห้ามทิ้ง — คำสั่ง Gift 1 ก.ย. 2569
    project_ordinal_raw: str | None = None   # "โครงการที่ 2" — comparison/provenance
                                             # 🔴 ไม่ใช่ identity (ทาง (ค))
    sheet_name_actual: str = ""              # ชื่อชีตจริง — provenance เท่านั้น
    sheet_index_actual: int = -1
    sheet_class: str = ""                    # MAIN / COVER / SUPPORTING
    cell_ref: str | None = None              # เช่น "C6"
    raw_header_label: object = None          # G6 — หัวคอลัมน์ดิบของเซลล์ค่า
    row_index: int = -1
    header_row: int | None = None
    agency_name: str | None = None           # ชื่อจากชีตปก — อยู่ในไฟล์จริง
    uncertainty: tuple[str, ...] = field(default_factory=tuple)

    @property
    def axis_valid(self) -> bool:
        """แกนเทียบถูกต้องหรือไม่ — บังคับ **XOR** ระหว่างปีกับหมวดงบรายจ่าย

        🔴 BO REVIEW: กติกานี้เคยเป็น implicit invariant
        ตอนนี้ encode ไว้ใน record contract แล้ว

        * ``FISCAL_YEAR``     → ต้องมี ``fiscal_year`` และ ``budget_category is None``
        * ``BUDGET_CATEGORY`` → ต้องมี ``budget_category`` และ ``fiscal_year is None``
        * อย่างอื่น → ไม่ถูกต้อง ⇒ ``UNRESOLVED / HUMAN REVIEW`` **ห้ามเดา**

        ตรวจเฉพาะ record ที่มีค่า — แถวโครงสร้างและแถวที่ยังไม่ map ไม่เข้าเกณฑ์นี้
        """
        if self.row_kind != ROW_KIND_VALUE:
            return True
        if self.comparison_axis == AXIS_FISCAL_YEAR:
            return self.fiscal_year is not None and self.budget_category is None
        if self.comparison_axis == AXIS_BUDGET_CATEGORY:
            return self.budget_category is not None and self.fiscal_year is None
        if self.comparison_axis == AXIS_SINGLE_AMOUNT:
            return (self.fiscal_year is None and self.budget_category is None
                    and not self.period_label)
        if self.comparison_axis == AXIS_PERIOD_RANGE:
            return (bool(self.period_label) and self.fiscal_year is None
                    and self.budget_category is None)
        return False

    @property
    def needs_review(self) -> bool:
        """รายการนี้ต้องให้มนุษย์ตรวจหรือไม่

        เกณฑ์: ตีความโครงสร้างไม่ได้ · หรือมีเครื่องหมายความกำกวมที่ blocking
        **ไม่นับ**ข้อจำกัดระดับไฟล์ที่ติดกับทุก record เท่ากัน
        """
        if self.row_kind in (ROW_KIND_UNMAPPED, ROW_KIND_UNSUPPORTED_PERIOD,
                             ROW_KIND_UNSUPPORTED_COLUMN):
            return True
        if not self.axis_valid:
            return True
        if self.budget_category == CATEGORY_UNRESOLVED:
            # 🔴 BO REVIEW (2 ก.ย.) — ไม่พึ่งเครื่องหมาย uncertainty เพียงอย่างเดียว
            # หมวดที่ยัง resolve ไม่ได้ **ต้อง** ให้มนุษย์ตัดสินเสมอ
            return True
        return bool(BLOCKING_UNCERTAINTY.intersection(self.uncertainty))
