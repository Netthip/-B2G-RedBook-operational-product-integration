# -*- coding: utf-8 -*-
"""AOWorkbookAdapter — สมุดงานคาดแดงรายหน่วยงาน (T1B Excel · OFFICIAL_AO_WORKBOOK)

โครงสร้างที่รับ: workbook หลายชีต · merged cells · formulas · anchor codes
หน่วยเงิน: ตามที่ประกาศในตาราง (พบทั้ง ``บาท`` และ ``ล้านบาท`` ในเล่มเดียวกัน)

**สถานะ:** ``T1B INSPECTION LAYER IMPLEMENTED — EXTRACTION / VERIFICATION
PIPELINE NOT YET COMPLETE``

🔴 **ห้ามใช้ชื่อชีต · index ของชีต · prefix ตัวอักษร · สี tab เป็น identity key**
(คำสั่ง Gift ข้อ 2 · 1 ก.ย. 2569) — บทบาทของชีต resolve จากหัวเรื่องเท่านั้น

🔴 **ห้ามทิ้งค่าดิบหลัง normalize** — ทุก record เก็บ ``raw_label`` · ``raw_value``
และตำแหน่งเซลล์จริงไว้เพื่อ trace กลับ Excel ต้นฉบับ

🔴 **ห้ามเดาโครงสร้างที่ยังไม่ได้ map** — ชีตที่ layout ต่างจากที่ map ไว้
ต้องออกเป็น ``UNMAPPED`` พร้อมเหตุผล ไม่ใช่ตีความมั่ว

🔴 **ป้ายกำกับผลงาน:** ``PRODUCT EVIDENCE — POST-FREEZE``
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..datasets.kinds import DatasetKind
from ..final_holdout import guard_file
from ..t1b import (
    DOCUMENT_LEVEL_UNKNOWN,
    STRUCTURAL_VERSION,
    SheetFacts,
    T1BKey,
    canonical_section,
    classify_sheet,
    find_title,
    is_monetary,
    locate_header_row,
    normalize_amount,
    normalize_label,
    parse_hierarchy,
    parse_year_label,
    resolve_declared_unit,
    resolve_document_level,
    resolve_plan_role,
    resolve_sheet_role,
    fiscal_years_in,
    title_evidence,
    find_category_tables,
    find_year_tables,
    split_leading_number,
    split_project_title,
)
from ..t1b.categories import CATEGORY_UNRESOLVED
from ..t1b.records import (
    AXIS_BUDGET_CATEGORY,
    AXIS_FISCAL_YEAR,
    AXIS_PERIOD_RANGE,
    AXIS_SINGLE_AMOUNT,
    ROW_KIND_STRUCTURAL,
    ROW_KIND_UNMAPPED,
    ROW_KIND_UNSUPPORTED_COLUMN,
    ROW_KIND_UNSUPPORTED_PERIOD,
    ROW_KIND_VALUE,
    UNC_NUMERIC_CELL_NOT_ACCOUNTED,
    UNC_FISCAL_YEAR_FROM_COVER,
    UNC_SINGLE_AMOUNT_KEY_AMBIGUOUS,
    UNC_SINGLE_AMOUNT_YEAR_UNRESOLVED,
    UNC_TRAILING_TEXT_AFTER_UNIT,
    UNC_PARENT_LINK_UNRESOLVED,
    UNC_PARENT_LINK_VIA_LINE_BREAK_JOIN,
    UNC_UNSUPPORTED_PERIOD_LABEL,
    UNC_UNSUPPORTED_VALUE_COLUMN,
    CAT_YEAR_FROM_SECTION_TITLE,
    CAT_YEAR_FROM_WORKBOOK_COVER,
    UNC_AGENCY_CODE_FROM_FILENAME,
    UNC_AGENCY_IDENTITY_UNRESOLVED,
    UNC_CATEGORY_TABLE_YEAR_UNRESOLVED,
    UNC_DOC_STATUS_FROM_FILENAME,
    UNC_SHEET_TITLE_AMBIGUOUS,
    UNC_HEADER_NOT_LOCATED,
    UNC_NO_YEAR_COLUMNS,
    UNC_ROWS_OUTSIDE_YEAR_TABLE,
    UNC_SUPPORTING_LAYOUT_NOT_MAPPED,
    UNC_AMBIGUOUS_PROJECT_TITLE,
    UNC_TABLE_BOUNDARY_AMBIGUOUS,
    UNC_CATEGORY_UNRESOLVED,
    UNC_UNIT_FROM_SHEET_DECLARATION,
    UNC_UNIT_UNRESOLVED,
    T1BRecord,
)
from ..t1b.roles import (
    SECTION_ROLE_PLAN,
    SECTION_ROLE_PROJECT,
    SHEET_CLASS_COVER,
    SHEET_CLASS_MAIN,
)
from ..t1b.supporting import (
    RULE_LINE_BREAK_JOINED,
    SHEET_ROLE_SUPPORTING_DETAIL,
    NameIndex,
    parse_block,
)
from ..t1b.temporal import (
    ROLE_FROM_LABEL,
    ROLE_FROM_PARENT_HEADING,
    classify_amount_role,
    is_bullet,
)
from ..t1b.units import UNIT_UNRESOLVED, find_sheet_unit_declaration, has_row_unit_column
from .base import (
    CanonicalEnvelope,
    DocumentAdapter,
    ExtractionStatus,
    LocationKind,
    SourceLocation,
)

#: จำนวนแถวสูงสุดที่อ่านเพื่อ *สำรวจ* โครงสร้าง — ไม่ใช่การสกัดเนื้อหา
INSPECT_SCAN_ROWS = 24

#: ชีตปกมี layout คนละแบบกับชีตหลัก (ป้ายอยู่คอลัมน์ B · หน่วยอยู่ I/M)
#: จึงยังไม่ map — ออกเป็น UNMAPPED ไม่เดา
UNC_COVER_LAYOUT_NOT_MAPPED = "cover_sheet_layout_not_mapped"

#: คอลัมน์ป้ายแถวของชีตหลัก (ฐาน 0) — ยืนยันกับบทบาท 5. และ 8. แล้ว
MAIN_LABEL_COLUMN = 0
#: คอลัมน์หน่วยนับของชีตหลัก (ฐาน 0)
MAIN_UNIT_COLUMN = 1

_FILENAME_PAT = re.compile(r"^XL_FY(\d{4})_([a-z-]+)_(\d+)_", re.IGNORECASE)


_NUMERIC_TEXT = re.compile(r"^\s*[-+]?\(?[\d,]*\d(?:\.\d+)?\)?\s*$")


def _is_numeric_cell(value: object) -> bool:
    """เซลล์นี้เป็นตัวเลขหรือไม่ — รวมตัวเลขที่เก็บเป็นข้อความ เช่น ``"1,234.50"``

    ใช้กับหลัก fail-visible (G6 · #14) จึงตั้งใจ **กว้างกว่า** ตัวแปลงค่า:
    นับเกินดีกว่านับขาด เพราะนับเกิน = คนเห็นเพิ่ม ส่วนนับขาด = หายเงียบ
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float, Decimal)):
        return True
    return isinstance(value, str) and bool(_NUMERIC_TEXT.match(value))


def _value_region_start(table) -> int:
    """คอลัมน์แรกของ **เขตค่า** — ขวาของคอลัมน์ป้าย และขวาของคอลัมน์หน่วยถ้ามี"""
    left = MAIN_LABEL_COLUMN
    if table.unit_column is not None:
        left = max(left, table.unit_column)
    return left + 1


def _column_index(cell_ref: str) -> int:
    """``"K12"`` -> ดัชนีคอลัมน์ฐาน 0 (คู่กลับของ :func:`_column_letter`)"""
    n = 0
    for ch in cell_ref:
        if not ch.isalpha():
            break
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def _column_letter(index0: int) -> str:
    from openpyxl.utils import get_column_letter

    return get_column_letter(index0 + 1)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


#: หัวเรื่องของชีตที่เป็น "หัวบท 7." ล้วน — แผนงานจริงอยู่แถวถัดไป
_PLAN_TITLE_SCAN_ROWS = 4


def _plan_title_override(rows: list[list[object]], title: object) -> object:
    """คืนหัวเรื่องที่เป็น **แผนงานจริง** เมื่อ ``A1`` เป็นหัวบท ``7.`` ล้วน

    🔴 พบจริงที่ชีต ``Sheet7_1`` — ``A1`` = *"7. รายละเอียดงบประมาณจำแนกตาม
    แผนงาน และ ผลผลิต/โครงการ"* (หัวบท) แต่ ``A2`` = *"7.1 แผนงานบุคลากรภาครัฐ"*
    ซึ่งเป็นแผนงานที่ชีตนี้บรรจุข้อมูลอยู่จริง

    ถ้าไม่แก้ ชีตนี้จะได้บทบาท ``SECTION_07`` (หัวบท) แทนที่จะเป็นแผนงาน
    ⇒ ข้อมูลแผนบุคลากรภาครัฐจะไม่ถูกจับคู่กับแผนเดียวกันของอีกปี
    """
    number, _rest = split_leading_number(title)
    if number != "7":
        return title
    for row in rows[1:_PLAN_TITLE_SCAN_ROWS]:
        for cell in row:
            if not isinstance(cell, str) or not cell.strip():
                continue
            candidate, _ = split_leading_number(cell)
            if candidate and candidate.startswith("7.") and candidate.count(".") == 1:
                return cell
    return title


def _category_table_year(section_title_raw: object, ctx_year: int | None):
    """ปีบริบทของตารางจำแนกตามงบรายจ่าย + ที่มาของปีนั้น

    🔴 **blocker #1 · Shadow Run 21011 รอบที่ 1** (แก้ 5 กันยายน 2569)

    ตารางแกนหมวดถูกบังคับให้ ``fiscal_year = None`` (XOR ของ ``axis_valid``)
    แต่ในแฟ้มจริงตารางผูกกับปีของเอกสารเสมอ — หัวเรื่องชีตบทบาท ``6.`` ระบุปีไว้ตรง ๆ
    ⇒ ถ้าไม่เก็บปีบริบทไว้ finding จะเทียบยอดปีหนึ่งกับอีกปีหนึ่งโดยช่องปีว่าง
    ปนอยู่ในไฟล์เดียวกับ finding ที่เทียบปีเดียวกัน (เกณฑ์หยุดทันทีข้อ 6)

    ลำดับหลักฐาน — **เนื้อในเอกสารก่อน แล้วจึงระดับแฟ้ม**

    1. หัวเรื่องชีตที่ระบุปี **เพียงปีเดียว** ⇒ ``section_title``
       (หลายปี เช่นบทบาท ``4.`` ที่เขียน ``2568 - 2570`` **ไม่ใช้** — ห้ามเดา)
    2. ปีของเอกสารจากชีตปก ⇒ ``workbook_cover``
    3. ไม่มีเลย ⇒ ``(None, "")`` ผู้เรียกต้องติดธงให้มนุษย์ตรวจ
    """
    years = fiscal_years_in(section_title_raw)
    if len(years) == 1:
        return years[0], CAT_YEAR_FROM_SECTION_TITLE
    if ctx_year is not None:
        return ctx_year, CAT_YEAR_FROM_WORKBOOK_COVER
    return None, ""


class AOWorkbookAdapter(DocumentAdapter):
    dataset_kind = DatasetKind.OFFICIAL_AO_WORKBOOK
    schema_version = f"ao-workbook-schema-0.3.0-{STRUCTURAL_VERSION}"

    def accepts(self, kind: DatasetKind) -> bool:
        # รับได้ทั้งไฟล์ทางการและไฟล์ภายในที่ยังไม่ยืนยัน provenance
        # แต่ผลของไฟล์ภายในห้ามเข้าผลหลัก (บังคับที่ชั้นรายงาน ไม่ใช่ที่นี่)
        return kind in (
            DatasetKind.OFFICIAL_AO_WORKBOOK,
            DatasetKind.UNCONFIRMED_LOCAL_WORKBOOK,
        )

    # ------------------------------------------------------------------ inspect
    def inspect(self, path: Path) -> dict[str, Any]:
        """สำรวจโครงสร้างไฟล์แบบ **อ่านอย่างเดียว** — ยังไม่สกัดเนื้อหา

        ไม่เขียน ไม่ save ไม่แก้ไฟล์ต้นทาง

        คืน dict ที่รายงานทั้ง **สิ่งที่ใช้เป็นคีย์ได้** (``sheet_role`` ·
        ``document_level``) และ **สิ่งที่ห้ามใช้เป็นคีย์แต่บันทึกไว้อ้างอิง**
        (``name_actual`` · ``index_actual``) เพื่อให้ตรวจย้อนได้ว่าไม่ได้นำมาจับคู่
        """
        import openpyxl

        guard_file(path)          # #21 — ชุดประเมินสุดท้ายที่ปิดผนึก ห้ามอ่าน
        wb = openpyxl.load_workbook(path, data_only=True, read_only=False)
        try:
            sheets: list[dict[str, Any]] = []
            document_level = None

            for index, ws in enumerate(wb.worksheets):
                rows = [
                    [c.value for c in row]
                    for row in ws.iter_rows(
                        min_row=1, max_row=min(ws.max_row or 1, INSPECT_SCAN_ROWS)
                    )
                ]
                title = _plan_title_override(rows, find_title(rows))
                facts = self._sheet_facts(ws, index, title)
                role, section_title = canonical_section(title)
                level = resolve_document_level(title)
                if document_level is None and level != DOCUMENT_LEVEL_UNKNOWN:
                    document_level = level

                tables = find_year_tables(rows)
                header_row = tables[0].header_row if tables else None
                year_columns: dict[int, int] = {}
                units: list[str] = []
                for table in tables:
                    year_columns.update(table.year_columns)
                    col = table.unit_column
                    if col is None:
                        unit = resolve_declared_unit(table.unit_declaration)
                        if unit != UNIT_UNRESOLVED and unit not in units:
                            units.append(unit)
                        continue
                    for row in rows[table.first_data_row - 1: table.last_data_row]:
                        if len(row) > col:
                            unit = resolve_declared_unit(row[col])
                            if unit != UNIT_UNRESOLVED and unit not in units:
                                units.append(unit)

                sheets.append({
                    # --- ใช้เป็นคีย์ได้ ---
                    "sheet_role": role,
                    "section_title": section_title,
                    "plan_role": resolve_plan_role(title),
                    "document_level": level,
                    "sheet_class": classify_sheet(facts),
                    # --- attribute ที่ต้อง resolve ก่อนเทียบ ---
                    "header_row": header_row,
                    "year_table_count": len(tables),
                    "year_columns": year_columns,
                    "declared_units": units,
                    # --- provenance / location · ห้ามใช้จับคู่ ---
                    "name_actual": facts.name,
                    "index_actual": facts.index,
                    "dims": f"{facts.max_row}x{facts.max_column}",
                    "merged_count": facts.merged_count,
                })

            return {
                "adapter": type(self).__name__,
                "schema_version": self.schema_version,
                "dataset_kind": self.dataset_kind.value,
                "source_file": path.name,
                "document_level": document_level or DOCUMENT_LEVEL_UNKNOWN,
                "sheet_count": len(sheets),
                "sheets": sheets,
            }
        finally:
            wb.close()

    # ------------------------------------------------------------------ extract
    def extract(self, path: Path) -> list[CanonicalEnvelope]:
        """สกัดสมุดงานเป็น canonical envelope — หนึ่ง envelope ต่อหนึ่งหน่วยหลักฐาน

        * แถวค่าในชีตหลัก → หนึ่ง envelope **ต่อหนึ่ง (แถว × ปี)** ชี้ตำแหน่งระดับเซลล์
        * แถวหัวข้อ/ป้าย → หนึ่ง envelope ต่อแถว (``STRUCTURAL``)
        * ชีตที่ layout ยังไม่ map → หนึ่ง envelope ต่อแถวที่มีเนื้อหา (``UNMAPPED``)
          **ไม่ทิ้งเงียบ** ตาม invariant ข้อ 1–2 ของ Gift
        """
        import openpyxl

        guard_file(path)          # #21 — ชุดประเมินสุดท้ายที่ปิดผนึก ห้ามอ่าน
        wb = openpyxl.load_workbook(path, data_only=True, read_only=False)
        try:
            source_hash = _sha256(path)
            ctx = self._workbook_context(wb, path)

            # ---- รอบที่ 1 — อ่านโครงสร้างทุกชีต และสร้างแผนที่แผนงานแม่ ----
            sheets: list[dict[str, Any]] = []
            plan_titles: dict[str, str] = {}      # เลขข้อแผนงาน -> ชื่อแผนงาน
            for index, ws in enumerate(wb.worksheets):
                rows = [[c.value for c in row] for row in ws.iter_rows()]
                evidence = title_evidence(rows[:INSPECT_SCAN_ROWS])
                title = _plan_title_override(rows, evidence.title)
                number, rest = split_leading_number(title)
                role, section_title = canonical_section(title)
                ordinal = split_project_title(rest)[0] if rest else None
                sheets.append({
                    "rows": rows, "title": title, "number": number,
                    "facts": self._sheet_facts(ws, index, title),
                    "role": role, "section_title": section_title,
                    "ordinal": ordinal, "plan_role": resolve_plan_role(title),
                    # 🔴 blocker #2 — เก็บหลักฐานว่ามีผู้สมัครหัวเรื่องที่มีเลขข้อ
                    # แต่ไม่ถูกเลือก · ห้ามทิ้ง ต้องใช้ตัดสินที่ชั้นสกัด
                    "title_displaced_numbered": bool(evidence.displaced_numbered),
                })
                if role == SECTION_ROLE_PLAN and number:
                    plan_titles[number] = section_title

            # ---- G2 (#14) — ดัชนีชื่อหัวข้อของชีตหลักบทบาทแผนงาน/โครงการ ----
            # ใช้ผูกบล็อกของชีตประกอบด้วยชื่อ · ตัดสินจากบทบาท ไม่ใช่ชื่อชีต
            names = NameIndex()
            for sheet in sheets:
                if classify_sheet(sheet["facts"]) != SHEET_CLASS_MAIN:
                    continue
                if sheet["role"] not in (SECTION_ROLE_PLAN, SECTION_ROLE_PROJECT):
                    continue
                names.add_sheet_title(sheet["role"], sheet["section_title"])
                for row in sheet["rows"]:
                    label = next((c for c in row if isinstance(c, str) and c.strip()), None)
                    names.add_heading(label, sheet["role"], sheet["section_title"])

            # ---- รอบที่ 2 — สกัด ----
            records: list[T1BRecord] = []
            for sheet in sheets:
                facts = sheet["facts"]
                sheet_class = classify_sheet(facts)
                parent_plan = ""
                if sheet["role"] == SECTION_ROLE_PROJECT and sheet["number"]:
                    # โครงการ 7.3.2 มีแผนแม่คือ 7.3 — ผูกด้วย **ชื่อ** ไม่ใช่เลขข้อ
                    parent_plan = plan_titles.get(
                        ".".join(sheet["number"].split(".")[:2]), ""
                    )
                meta = dict(
                    ctx=ctx, sheet_role=sheet["role"], section_title=sheet["section_title"],
                    section_title_raw=sheet["title"], parent_plan=parent_plan,
                    project_ordinal=sheet["ordinal"], plan_role=sheet["plan_role"],
                    facts=facts, sheet_class=sheet_class,
                )
                if sheet_class == SHEET_CLASS_MAIN:
                    records.extend(self._extract_main_sheet(sheet["rows"], **meta))
                else:
                    reasons = [
                        UNC_COVER_LAYOUT_NOT_MAPPED if sheet_class == SHEET_CLASS_COVER
                        else UNC_SUPPORTING_LAYOUT_NOT_MAPPED
                    ]
                    # 🔴 blocker #2 fail-safe — ชีตที่ **ไม่ใช่ชีตหลัก** แต่ในหน้าต่าง
                    # หัวเรื่องมีผู้สมัครที่มีเลขข้ออยู่ ต้องบอกเหตุผลนี้ไว้ด้วย
                    # เพราะเป็นรูปแบบเดียวกับที่ทำให้ชีตหลักทั้งชีตหลุดจากการตรวจ
                    # ห้ามให้ผู้อ่านเห็นแค่ "ยังไม่ map" โดยไม่รู้ว่ามีโครงสร้างที่อ่านได้
                    if sheet["title_displaced_numbered"]:
                        reasons.append(UNC_SHEET_TITLE_AMBIGUOUS)
                    if sheet_class == SHEET_CLASS_COVER:
                        records.extend(
                            self._extract_unmapped_sheet(
                                sheet["rows"], reason=tuple(reasons), **meta
                            )
                        )
                    else:
                        records.extend(self._extract_supporting_sheet(
                            sheet["rows"], names=names, reasons=tuple(reasons), **meta
                        ))

            records = self._flag_ambiguous_projects(records)
            records = self._flag_colliding_single_amounts(records)
            return [self._to_envelope(rec, path, source_hash, ctx) for rec in records]
        finally:
            wb.close()

    @staticmethod
    def _flag_colliding_single_amounts(records: list[T1BRecord]) -> list[T1BRecord]:
        """G1/G2 (#14) — คีย์ของแถวค่าเดี่ยวต้องไม่ซ้ำกัน **ทั้งสมุดงาน**

        ตรวจในชีตเดียวทำไว้แล้วที่ชั้นสกัด · ชั้นนี้กันกรณีบล็อกชื่อเดียวกัน
        อยู่คนละชีตประกอบ ⇒ ติดธง blocking ทุกรายการในกลุ่ม ไม่ collapse
        """
        counts: dict[T1BKey, int] = {}
        for rec in records:
            if rec.comparison_axis == AXIS_SINGLE_AMOUNT and rec.row_kind == ROW_KIND_VALUE:
                counts[rec.key] = counts.get(rec.key, 0) + 1
        out = []
        for rec in records:
            if (rec.comparison_axis == AXIS_SINGLE_AMOUNT and counts.get(rec.key, 0) > 1
                    and UNC_SINGLE_AMOUNT_KEY_AMBIGUOUS not in rec.uncertainty):
                rec = replace(rec, uncertainty=rec.uncertainty
                              + (UNC_SINGLE_AMOUNT_KEY_AMBIGUOUS,))
            out.append(rec)
        return out

    def _extract_supporting_sheet(
        self, rows, *, names, reasons, ctx, sheet_role, section_title,
        section_title_raw, parent_plan, project_ordinal, plan_role, facts, sheet_class,
    ) -> list[T1BRecord]:
        """G2 (#14) — ชีตประกอบ: แบ่งบล็อกตามหัว ``ผลผลิต :`` / ``โครงการ :`` /
        ``รายการบุคลากรภาครัฐ`` แล้วผูกกับชีตหลักด้วยชื่อ

        * แถวในบล็อกที่เข้าลายเซ็น G1 ⇒ ``SINGLE_AMOUNT`` (คีย์ = บทบาท
          ``SUPPORTING_DETAIL`` · ชื่อบล็อก · บริบทที่ผูกได้ · ลำดับชั้น · ป้าย)
        * แถวที่ไม่เข้า ⇒ ``UNMAPPED`` ตามเดิม แต่มีชื่อบล็อกในคีย์ให้คนตรวจเห็นบริบท
        * ผูกไม่ได้ ⇒ ติด ``parent_link_unresolved`` (blocking) ทุก record ของบล็อก
        * ไม่พบหัวบล็อกเลย ⇒ พฤติกรรมเดิมทุกประการ
        """
        common = dict(ctx=ctx, project_ordinal=project_ordinal, plan_role=plan_role,
                      facts=facts, sheet_class=sheet_class)
        numbered = [(i, row) for i, row in enumerate(rows, start=1)
                    if any(c is not None for c in row)]
        starts = []
        for position, (index, row) in enumerate(numbered):
            label = next((c for c in row if isinstance(c, str) and c.strip()), None)
            block = parse_block(label)
            if block is not None:
                starts.append((position, block))
        if not starts:
            return self._extract_unmapped_sheet(
                rows, reason=reasons, ctx=ctx, sheet_role=sheet_role,
                section_title=section_title, section_title_raw=section_title_raw,
                parent_plan=parent_plan, project_ordinal=project_ordinal,
                plan_role=plan_role, facts=facts, sheet_class=sheet_class)

        records: list[T1BRecord] = []
        head = numbered[:starts[0][0]]
        if head:
            records.extend(self._unmapped_rows(
                head, reason=reasons, sheet_role=sheet_role,
                section_title=section_title, section_title_raw=section_title_raw,
                parent_plan=parent_plan, **common))
        for n, (position, block) in enumerate(starts):
            end = starts[n + 1][0] if n + 1 < len(starts) else len(numbered)
            block_rows = numbered[position:end]
            binding = names.bind(block)
            extra: tuple[str, ...] = ()
            if not binding.bound:
                extra = (UNC_PARENT_LINK_UNRESOLVED,)
            elif binding.rule == RULE_LINE_BREAK_JOINED:
                extra = (UNC_PARENT_LINK_VIA_LINE_BREAK_JOIN,)
            passthrough = dict(
                sheet_role=SHEET_ROLE_SUPPORTING_DETAIL,
                section_title=f"{block.kind} : {block.name}",
                section_title_raw=block.raw,
                parent_plan=binding.section_title if binding.bound else "",
                **common)
            singles, rest = self._single_amount_rows(block_rows, **passthrough)
            records.extend(replace(r, uncertainty=r.uncertainty + extra) for r in singles)
            if rest:
                records.extend(self._unmapped_rows(
                    rest, reason=(UNC_SUPPORTING_LAYOUT_NOT_MAPPED,) + extra,
                    **passthrough))
        records.extend(self._unaccounted_numeric_rows(
            rows, records, sheet_role=sheet_role, section_title=section_title,
            section_title_raw=section_title_raw, parent_plan=parent_plan, **common))
        return records

    @staticmethod
    def _flag_ambiguous_projects(records: list[T1BRecord]) -> list[T1BRecord]:
        """ติดธงเมื่อ **ชื่อโครงการซ้ำภายในแผนงานเดียวกัน**

        🔴 คำตัดสิน Gift (ทาง (ค) · 1 ก.ย. 2569):
        *"ถ้าชื่อ semantic ซ้ำภายใน plan เดียวกัน ให้เป็น AMBIGUOUS / HUMAN REVIEW
        ห้าม collapse อัตโนมัติ"*

        การซ้ำหมายถึงชื่อเดียวกันมาจาก **คนละชีต** ในแฟ้มเดียวกัน —
        ไม่ใช่หลาย record จากชีตเดียวกันซึ่งเป็นเรื่องปกติ
        """
        sheets_per_title: dict[tuple[str, str], set[str]] = {}
        for rec in records:
            if rec.key.sheet_role != SECTION_ROLE_PROJECT or not rec.key.section_title_norm:
                continue
            sig = (rec.key.parent_plan_norm, rec.key.section_title_norm)
            sheets_per_title.setdefault(sig, set()).add(rec.sheet_name_actual)

        ambiguous = {sig for sig, names in sheets_per_title.items() if len(names) > 1}
        if not ambiguous:
            return records

        out: list[T1BRecord] = []
        for rec in records:
            sig = (rec.key.parent_plan_norm, rec.key.section_title_norm)
            if rec.key.sheet_role == SECTION_ROLE_PROJECT and sig in ambiguous:
                rec = replace(
                    rec,
                    uncertainty=tuple(rec.uncertainty) + (UNC_AMBIGUOUS_PROJECT_TITLE,),
                )
            out.append(rec)
        return out

    # -------------------------------------------------------------- ตัวช่วยภายใน
    @staticmethod
    def _sheet_facts(ws, index: int, title: object) -> SheetFacts:
        return SheetFacts(
            name=ws.title,
            index=index,
            a1=title,
            max_row=ws.max_row or 0,
            max_column=ws.max_column or 0,
            merged_count=len(ws.merged_cells.ranges),
            merged_spans=tuple(
                (r, m.min_col - 1, m.max_col - 1)
                for m in ws.merged_cells.ranges
                for r in range(m.min_row, m.max_row + 1)
            ),
        )

    def _workbook_context(self, wb, path: Path) -> dict[str, Any]:
        """บริบทระดับสมุดงาน — แยกสิ่งที่อ่านได้จากไฟล์ ออกจากสิ่งที่เดาจากชื่อไฟล์

        🔴 ``agency_code`` และ ``document_status`` **ไม่มีอยู่ในเนื้อไฟล์**
        จึงอ่านจากชื่อไฟล์และติดเครื่องหมายความไม่แน่นอนไว้เสมอ
        ส่วน ``agency_name`` และปีงบประมาณ **อ่านได้จากชีตปกจริง**
        """
        uncertainty: list[str] = []
        agency_code = None
        document_status = None
        m = _FILENAME_PAT.match(path.name)
        if m:
            document_status = m.group(2).replace("-", "_")
            agency_code = m.group(3)
            uncertainty.append(UNC_AGENCY_CODE_FROM_FILENAME)
            uncertainty.append(UNC_DOC_STATUS_FROM_FILENAME)

        agency_name = None
        ministry_name = None
        fiscal_year = None
        document_level = DOCUMENT_LEVEL_UNKNOWN

        for index, ws in enumerate(wb.worksheets):
            rows = [
                [c.value for c in row]
                for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row or 1, INSPECT_SCAN_ROWS))
            ]
            title = find_title(rows[:INSPECT_SCAN_ROWS])
            level = resolve_document_level(title)
            if document_level == DOCUMENT_LEVEL_UNKNOWN and level != DOCUMENT_LEVEL_UNKNOWN:
                document_level = level

            facts = self._sheet_facts(ws, index, title)
            if classify_sheet(facts) != SHEET_CLASS_COVER:
                continue
            # ชีตปก: A2 = ชื่อกระทรวง · A3 = ชื่อหน่วยงาน (ไม่มีในแฟ้มระดับกระทรวง)
            col_a = [r[0] if r else None for r in rows]
            texts = [normalize_label(v) for v in col_a[:4] if isinstance(v, str) and v.strip()]
            # 🔴 ชีตปก **แรก** เท่านั้นที่ให้ชื่อหน่วยงาน
            # ถ้าปล่อยให้ชีตหลังเขียนทับ ชื่อหน่วยงานจะกลายเป็นชื่อโครงการของชีตท้าย ๆ
            if texts and agency_name is None:
                ministry_name = texts[0]
                agency_name = texts[1] if len(texts) > 1 else texts[0]
            years = [
                y for row in rows for y in (parse_year_label(c) for c in row) if y is not None
            ]
            if years:
                fiscal_year = max(years)

        # 🔴 blocker #3 — ตัวตนหน่วยงานต้องมาจาก **เนื้อในแฟ้ม**
        # ``agency_code`` มาจากชื่อไฟล์ซึ่งแฟ้มจริงส่วนใหญ่ไม่ตรงรูปแบบ
        # ⇒ ค่าว่างทั้งสองฝั่ง ⇒ คีย์เท่ากัน ⇒ จับคู่ข้ามหน่วยงานได้โดยไม่มีสัญญาณ
        agency_identity = normalize_label(agency_name)
        if not agency_identity:
            uncertainty.append(UNC_AGENCY_IDENTITY_UNRESOLVED)

        return {
            "agency_code": agency_code,
            "agency_identity": agency_identity,
            "agency_name": agency_name,
            "ministry_name": ministry_name,
            "document_level": document_level,
            "document_status": document_status,
            "fiscal_year": fiscal_year,
            "uncertainty": tuple(uncertainty),
        }

    def _build_key(self, ctx, sheet_role, section_title, parent_plan, plan_role,
                   hierarchy_path, row_label) -> T1BKey:
        return T1BKey(
            agency_code=ctx["agency_code"] or "",
            agency_identity=ctx["agency_identity"],
            document_level=ctx["document_level"],
            sheet_role=sheet_role or "",
            section_title_norm=section_title,
            parent_plan_norm=parent_plan,
            plan_role=plan_role,
            hierarchy_path=hierarchy_path,
            row_label_norm=row_label,
        )

    def _extract_main_sheet(
        self, rows, *, ctx, sheet_role, section_title, section_title_raw, parent_plan,
        project_ordinal, plan_role, facts, sheet_class,
    ) -> list[T1BRecord]:
        passthrough = dict(
            ctx=ctx, sheet_role=sheet_role, section_title=section_title,
            section_title_raw=section_title_raw, parent_plan=parent_plan,
            project_ordinal=project_ordinal, plan_role=plan_role,
            facts=facts, sheet_class=sheet_class,
        )
        year_tables = find_year_tables(rows)
        covered: set[int] = set()
        for table in year_tables:
            covered.update(range(table.header_row, table.last_data_row + 1))
        category_tables = find_category_tables(rows, covered)

        if not year_tables and not category_tables:
            # G1 (#14) — ชีตหลักที่ไม่มีตารางเลย ยังมีแถวค่าเดี่ยวได้
            numbered = [
                (index, row) for index, row in enumerate(rows, start=1)
                if any(c is not None for c in row)
            ]
            singles, rest = self._single_amount_rows(numbered, **passthrough)
            out = singles + self._unmapped_rows(
                rest, reason=UNC_NO_YEAR_COLUMNS, **passthrough)
            return out + self._unaccounted_numeric_rows(rows, out, **passthrough)

        records: list[T1BRecord] = []
        for table in year_tables:
            records.extend(self._extract_year_table(rows, table, **passthrough))
        for table in category_tables:
            if table.boundary_ambiguous:
                # 🔴 ขอบเขตตัดสินไม่ได้ — ห้ามสกัดค่า ห้ามข้ามเงียบ
                records.extend(self._boundary_ambiguous_rows(
                    rows, table, **passthrough
                ))
                covered.add(table.header_row)
                continue
            records.extend(self._extract_category_table(rows, table, **passthrough))
            covered.update(range(table.header_row, table.last_data_row + 1))

        # 🔴 แถวที่ไม่อยู่ในตารางรายปีใดเลย ต้องไม่หายเงียบ
        leftover = [
            (index, row) for index, row in enumerate(rows, start=1)
            if index not in covered and any(c is not None for c in row)
        ]
        if leftover:
            # G1 (#14) — แถว "ป้าย + ค่าเดี่ยว + หน่วย" ออกเป็น record ที่เทียบได้
            # แถวที่ไม่เข้าลายเซ็น คง UNMAPPED ตามเดิม
            singles, rest = self._single_amount_rows(leftover, **passthrough)
            records.extend(singles)
            if rest:
                records.extend(self._unmapped_rows(
                    rest, reason=UNC_ROWS_OUTSIDE_YEAR_TABLE, **passthrough
                ))
        records.extend(self._unaccounted_numeric_rows(rows, records, **passthrough))
        return records

    def _single_amount_rows(
        self, numbered_rows, *, ctx, sheet_role, section_title, section_title_raw,
        parent_plan, project_ordinal, plan_role, facts, sheet_class,
    ) -> tuple[list[T1BRecord], list[tuple[int, list[object]]]]:
        """G1 (#14) — ตัวสกัดแถว "ป้าย + ค่าเดี่ยว + หน่วย"

        ลายเซ็นเชิงโครงสร้าง (🔴 ไม่ใช้ชื่อชีต ตำแหน่งเซลล์ หรือยอด):

        1. ตัวเลข **หนึ่งช่องเท่านั้น** ในแถว
        2. **เซลล์ถัดไปทางขวา** ของตัวเลขเป็นหน่วยที่ระบบรู้จัก — ถ้าตัวเลขอยู่ใน
           เซลล์ผสาน "ถัดไป" คือเซลล์แรกหลังช่วงผสานนั้น (ตามที่ตาเห็นบนหน้ากระดาษ)
           🔴 ไม่ข้ามเซลล์ว่างที่ไม่ได้ผสาน (REVIEW ของ Bo · #14 — รุ่นก่อนข้ามได้ 3 คอลัมน์
           โดยไม่มีข้อกำหนดรองรับ)
        3. ข้อความป้าย **หนึ่งช่องเท่านั้น** ทางซ้ายของตัวเลข

        ไม่เข้าลายเซ็น ⇒ คืนกลับใน ``rest`` ให้ผู้เรียกบันทึกเป็น UNMAPPED ตามเดิม

        ลำดับชั้นคิดจากป้ายของ **ทุกแถว** ที่ส่งเข้ามา (รวมแถวหัวข้อที่ไม่มีค่า)
        เพื่อให้ ``- เงินงบประมาณ`` ใต้หัวข้อต่างกันได้คีย์ต่างกัน ·
        คีย์ยังชนกันในชีตเดียว ⇒ ติดธง blocking ทั้งกลุ่ม ห้ามจับคู่อัตโนมัติ
        """
        labels = [
            next((c for c in row if isinstance(c, str) and c.strip()), None)
            for _index, row in numbered_rows
        ]
        hierarchy = parse_hierarchy(labels)
        heading_roles: dict[str, str] = {}
        for label, path in zip(labels, hierarchy):
            if len(path) == 1:
                heading_roles[path[0]] = classify_amount_role(label)

        merged_end = {(r, first): last for r, first, last in facts.merged_spans}
        year = ctx["fiscal_year"]
        singles: list[T1BRecord] = []
        rest: list[tuple[int, list[object]]] = []
        for position, (row_index, row) in enumerate(numbered_rows):
            nums = [i for i, v in enumerate(row) if _is_numeric_cell(v)]
            if len(nums) != 1:
                rest.append((row_index, row))
                continue
            col = nums[0]
            unit_col = merged_end.get((row_index, col), col) + 1
            unit_cell = row[unit_col] if unit_col < len(row) else None
            unit = (resolve_declared_unit(unit_cell) if isinstance(unit_cell, str)
                    else UNIT_UNRESOLVED)
            left_texts = [i for i in range(col)
                          if isinstance(row[i], str) and row[i].strip()]
            if unit == UNIT_UNRESOLVED or len(left_texts) != 1:
                rest.append((row_index, row))
                continue
            raw_label = row[left_texts[0]]
            path = hierarchy[position]
            role = classify_amount_role(raw_label)
            role_source = ROLE_FROM_LABEL if role else ""
            if not role and is_bullet(raw_label) and len(path) == 2:
                role = heading_roles.get(path[0], "")
                role_source = ROLE_FROM_PARENT_HEADING if role else ""
            unc = [UNC_FISCAL_YEAR_FROM_COVER]
            if year is None:
                unc.append(UNC_SINGLE_AMOUNT_YEAR_UNRESOLVED)
            if any(isinstance(v, str) and v.strip() for v in row[unit_col + 1:]):
                unc.append(UNC_TRAILING_TEXT_AFTER_UNIT)
            singles.append(T1BRecord(
                key=self._build_key(ctx, sheet_role, section_title, parent_plan,
                                    plan_role, path, normalize_label(raw_label)),
                row_kind=ROW_KIND_VALUE,
                comparison_axis=AXIS_SINGLE_AMOUNT,
                category_table_fiscal_year=year,
                category_table_year_source=(
                    CAT_YEAR_FROM_WORKBOOK_COVER if year is not None else ""),
                amount_role=role,
                amount_role_source=role_source,
                declared_unit=unit,
                is_monetary=is_monetary(unit),
                value_decimal=normalize_amount(row[col], unit, unit_cell),
                raw_label=raw_label,
                raw_value=row[col],
                raw_unit_cell=unit_cell,
                section_title_raw=section_title_raw,
                project_ordinal_raw=project_ordinal,
                sheet_name_actual=facts.name,
                sheet_index_actual=facts.index,
                sheet_class=sheet_class,
                cell_ref=f"{_column_letter(col)}{row_index}",
                row_index=row_index,
                agency_name=ctx["agency_name"],
                uncertainty=tuple(unc),
            ))

        counts: dict[T1BKey, int] = {}
        for rec in singles:
            counts[rec.key] = counts.get(rec.key, 0) + 1
        singles = [
            replace(rec, uncertainty=rec.uncertainty + (UNC_SINGLE_AMOUNT_KEY_AMBIGUOUS,))
            if counts[rec.key] > 1 else rec
            for rec in singles
        ]
        return singles, rest

    def _unaccounted_numeric_rows(self, rows, records, **passthrough) -> list[T1BRecord]:
        """invariant (#14) — ตาข่ายนิรภัยของชีตหลัก

        หลังสกัดทุกตารางแล้ว เซลล์ตัวเลขใดที่ยังไม่มี record ครอบ (ระดับเซลล์
        หรือ UNMAPPED ระดับแถว) ⇒ บันทึกทั้งแถวเป็น ``UNMAPPED`` พร้อมเหตุผล
        พบจริง: ตัวเลขที่อยู่ในแถวหัวตาราง

        🔴 ไม่ตีความ ไม่เดาว่าเป็นของตารางใด — แค่ทำให้มองเห็น
        """
        cells: set[tuple[int, int]] = set()
        unmapped_rows: set[int] = set()
        for rec in records:
            if rec.row_kind == ROW_KIND_UNMAPPED:
                unmapped_rows.add(rec.row_index)
            elif rec.cell_ref and rec.row_kind != ROW_KIND_STRUCTURAL:
                cells.add((rec.row_index, _column_index(rec.cell_ref)))
        missing: list[tuple[int, list[object]]] = []
        for index, row in enumerate(rows, start=1):
            if index in unmapped_rows:
                continue
            if any(_is_numeric_cell(v) and (index, col) not in cells
                   for col, v in enumerate(row)):
                missing.append((index, row))
        if not missing:
            return []
        return self._unmapped_rows(
            missing, reason=UNC_NUMERIC_CELL_NOT_ACCOUNTED, **passthrough)

    def _extract_year_table(
        self, rows, table, *, ctx, sheet_role, section_title, section_title_raw,
        parent_plan, project_ordinal, plan_role, facts, sheet_class,
    ) -> list[T1BRecord]:
        """สกัดตารางรายปีหนึ่งชุด"""
        body = rows[table.first_data_row - 1: table.last_data_row]
        raw_labels = [r[MAIN_LABEL_COLUMN] if r else None for r in body]
        hierarchy = parse_hierarchy(raw_labels)

        unit_column = table.unit_column
        sheet_unit = (
            UNIT_UNRESOLVED if unit_column is not None
            else resolve_declared_unit(table.unit_declaration)
        )

        records: list[T1BRecord] = []
        for offset, row in enumerate(body):
            raw_label = raw_labels[offset]
            label = normalize_label(raw_label)
            if not label:
                continue
            row_index = table.first_data_row + offset

            unit_source: list[str] = []
            if unit_column is not None:
                raw_unit = row[unit_column] if len(row) > unit_column else None
                unit = resolve_declared_unit(raw_unit)
                declaration = raw_unit
            elif sheet_unit != UNIT_UNRESOLVED:
                # ชีตไม่มีคอลัมน์หน่วย — คอลัมน์ค่าไม่ใช่หน่วย จึงต้องบันทึก
                # ข้อความประกาศหน่วยเป็น raw_unit_cell ไม่ใช่ค่าเงิน
                raw_unit = table.unit_declaration
                unit, declaration = sheet_unit, table.unit_declaration
                unit_source.append(UNC_UNIT_FROM_SHEET_DECLARATION)
            else:
                raw_unit = None
                unit, declaration = UNIT_UNRESOLVED, None

            common = dict(
                key=self._build_key(ctx, sheet_role, section_title, parent_plan,
                                    plan_role, hierarchy[offset], label),
                raw_label=raw_label, raw_unit_cell=raw_unit,
                section_title_raw=section_title_raw, project_ordinal_raw=project_ordinal,
                sheet_name_actual=facts.name, sheet_index_actual=facts.index,
                sheet_class=sheet_class, row_index=row_index,
                header_row=table.header_row,
                agency_name=ctx["agency_name"], declared_unit=unit,
                is_monetary=is_monetary(unit),
            )

            emitted = False
            for year, col in sorted(table.year_columns.items()):
                raw_value = row[col] if len(row) > col else None
                if raw_value is None:
                    continue
                unc: list[str] = list(unit_source)
                if unit == UNIT_UNRESOLVED:
                    unc.append(UNC_UNIT_UNRESOLVED)
                records.append(T1BRecord(
                    row_kind=ROW_KIND_VALUE,
                    comparison_axis=AXIS_FISCAL_YEAR,
                    fiscal_year=year,
                    fiscal_year_label=f"ปี {year}",
                    value_decimal=normalize_amount(raw_value, unit, declaration),
                    raw_value=raw_value,
                    cell_ref=f"{_column_letter(col)}{row_index}",
                    uncertainty=tuple(unc),
                    **common,
                ))
                emitted = True

            # G5 (#14) — คอลัมน์ช่วงเวลา เข้าแกนใหม่ ไม่ปนกับปีเดี่ยว
            for col, period in sorted(table.period_columns.items()):
                raw_value = row[col] if len(row) > col else None
                if raw_value is None:
                    continue
                unc = list(unit_source)
                if unit == UNIT_UNRESOLVED:
                    unc.append(UNC_UNIT_UNRESOLVED)
                records.append(T1BRecord(
                    row_kind=ROW_KIND_VALUE,
                    comparison_axis=AXIS_PERIOD_RANGE,
                    period_label=period.norm,
                    fiscal_year_label=period.raw,
                    value_decimal=normalize_amount(raw_value, unit, declaration),
                    raw_value=raw_value,
                    cell_ref=f"{_column_letter(col)}{row_index}",
                    raw_header_label=period.raw,
                    uncertainty=tuple(unc),
                    **common,
                ))
                emitted = True

            if not emitted:
                records.append(T1BRecord(
                    row_kind=ROW_KIND_STRUCTURAL,
                    comparison_axis=AXIS_FISCAL_YEAR,
                    cell_ref=f"{_column_letter(MAIN_LABEL_COLUMN)}{row_index}",
                    **common,
                ))

        records.extend(self._unsupported_value_columns(
            body, table, hierarchy, raw_labels, ctx=ctx, sheet_role=sheet_role,
            section_title=section_title, section_title_raw=section_title_raw,
            parent_plan=parent_plan, project_ordinal=project_ordinal,
            plan_role=plan_role, facts=facts, sheet_class=sheet_class,
        ))
        return records

    def _unsupported_value_columns(
        self, body, table, hierarchy, raw_labels, *, ctx, sheet_role, section_title,
        section_title_raw, parent_plan, project_ordinal, plan_role, facts, sheet_class,
    ) -> list[T1BRecord]:
        """G6 (#14) — **fail-visible** สำหรับคอลัมน์ค่าที่หัวคอลัมน์อ่านไม่ออก

        หลังสกัดคอลัมน์ปีและช่วงเวลาแล้ว สแกนคอลัมน์ที่เหลือในเขตค่า ·
        คอลัมน์ใดมีเซลล์ตัวเลขในแถวข้อมูล ⇒ หนึ่ง record ต่อ (แถว × คอลัมน์)
        พร้อมหัวคอลัมน์ดิบและตำแหน่งเซลล์ · 🔴 **ห้ามคืนค่าว่าง**

        ไม่ตีความค่า (ไม่ normalize) เพราะไม่รู้ว่าคอลัมน์นั้นหมายถึงอะไร
        """
        handled = set(table.year_columns.values()) | set(table.period_columns)
        if table.unit_column is not None:
            handled.add(table.unit_column)
        start = _value_region_start(table)
        width = max((len(r) for r in body), default=0)
        records: list[T1BRecord] = []
        for col in range(start, width):
            if col in handled:
                continue
            cells = [
                (offset, row[col]) for offset, row in enumerate(body)
                if len(row) > col and _is_numeric_cell(row[col])
            ]
            for offset, raw_value in cells:
                row_index = table.first_data_row + offset
                raw_label = raw_labels[offset]
                records.append(T1BRecord(
                    key=self._build_key(ctx, sheet_role, section_title, parent_plan,
                                        plan_role, hierarchy[offset],
                                        normalize_label(raw_label)),
                    row_kind=ROW_KIND_UNSUPPORTED_PERIOD,
                    raw_label=raw_label,
                    raw_value=raw_value,
                    raw_header_label=table.header_texts.get(col),
                    section_title_raw=section_title_raw,
                    project_ordinal_raw=project_ordinal,
                    sheet_name_actual=facts.name,
                    sheet_index_actual=facts.index,
                    sheet_class=sheet_class,
                    cell_ref=f"{_column_letter(col)}{row_index}",
                    row_index=row_index,
                    header_row=table.header_row,
                    agency_name=ctx["agency_name"],
                    uncertainty=(UNC_UNSUPPORTED_PERIOD_LABEL,),
                ))
        return records

    def _boundary_ambiguous_rows(
        self, rows, table, **passthrough
    ) -> list[T1BRecord]:
        """ตารางที่ขอบเขตแข่งกันจนตัดสินไม่ได้ — ขึ้นคิวมนุษย์ ไม่สกัดค่า

        🔴 blocker #4 (Bo · 3 ก.ย. 2569): เดิม ``find_category_tables()``
        ``continue`` เงียบเมื่อไม่เหลือแถวข้อมูล ⇒ ทั้งตารางหายไปโดยไม่มีร่องรอย
        ห้ามเดาว่าแถวเป็นของตารางใด · เก็บ raw กับตำแหน่งไว้ให้มนุษย์ตัดสิน
        """
        index = table.header_row
        if index > len(rows):
            return []
        return self._unmapped_rows(
            [(index, rows[index - 1])],
            reason=UNC_TABLE_BOUNDARY_AMBIGUOUS,
            header_row=table.header_row,
            **passthrough,
        )

    def _extract_category_table(
        self, rows, table, *, ctx, sheet_role, section_title, section_title_raw,
        parent_plan, project_ordinal, plan_role, facts, sheet_class,
    ) -> list[T1BRecord]:
        """สกัดตารางที่จำแนกตาม **ประเภทงบรายจ่าย** ไม่ใช่ปีงบประมาณ

        🔴 ``budget_category`` เป็น **comparison attribute** เหมือน ``fiscal_year``
        — อยู่นอก ``T1BKey`` ที่ freeze แล้ว จึงไม่กระทบคีย์
        """
        body = rows[table.first_data_row - 1: table.last_data_row]
        raw_labels = [r[MAIN_LABEL_COLUMN] if r else None for r in body]
        hierarchy = parse_hierarchy(raw_labels)

        unit = resolve_declared_unit(table.unit_declaration)
        declaration = table.unit_declaration
        unc_list = list(
            (UNC_UNIT_FROM_SHEET_DECLARATION,) if unit != UNIT_UNRESOLVED
            else (UNC_UNIT_UNRESOLVED,)
        )

        # 🔴 blocker #1 — ปีบริบทของตาราง ติดไปกับทุก record ของตารางนี้
        table_year, table_year_source = _category_table_year(
            section_title_raw, ctx["fiscal_year"]
        )
        if table_year is None:
            unc_list.append(UNC_CATEGORY_TABLE_YEAR_UNRESOLVED)
        unc_base = tuple(unc_list)

        records: list[T1BRecord] = []
        for offset, row in enumerate(body):
            raw_label = raw_labels[offset]
            label = normalize_label(raw_label)
            if not label:
                continue
            row_index = table.first_data_row + offset

            common = dict(
                key=self._build_key(ctx, sheet_role, section_title, parent_plan,
                                    plan_role, hierarchy[offset], label),
                raw_label=raw_label, raw_unit_cell=declaration,
                section_title_raw=section_title_raw, project_ordinal_raw=project_ordinal,
                sheet_name_actual=facts.name, sheet_index_actual=facts.index,
                sheet_class=sheet_class, row_index=row_index,
                header_row=table.header_row,
                agency_name=ctx["agency_name"], declared_unit=unit,
                is_monetary=is_monetary(unit),
                category_table_fiscal_year=table_year,
                category_table_year_source=table_year_source,
            )

            emitted = False
            for column in table.columns:
                col = column.index
                raw_value = row[col] if len(row) > col else None
                if raw_value is None:
                    continue
                unc = list(unc_base)
                if column.canonical == CATEGORY_UNRESOLVED:
                    # 🔴 BO REVIEW — หัวคอลัมน์ที่ไม่รู้จักต้อง **ไม่หายเงียบ**
                    # เก็บค่าไว้ ติดธง และส่งเข้าคิวมนุษย์ · ห้ามเดาหมวดใกล้เคียง
                    unc.append(UNC_CATEGORY_UNRESOLVED)
                records.append(T1BRecord(
                    row_kind=ROW_KIND_VALUE,
                    comparison_axis=AXIS_BUDGET_CATEGORY,
                    budget_category=column.canonical,
                    budget_category_raw=column.raw_header,
                    value_decimal=normalize_amount(raw_value, unit, declaration),
                    raw_value=raw_value,
                    cell_ref=f"{_column_letter(col)}{row_index}",
                    uncertainty=tuple(unc),
                    **common,
                ))
                emitted = True

            if not emitted:
                records.append(T1BRecord(
                    row_kind=ROW_KIND_STRUCTURAL,
                    comparison_axis=AXIS_BUDGET_CATEGORY,
                    cell_ref=f"{_column_letter(MAIN_LABEL_COLUMN)}{row_index}",
                    **common,
                ))

        # invariant (#14) — คอลัมน์ในเขตค่าที่ไม่มีหัว แต่มีตัวเลข ⇒ มองเห็น ไม่หายเงียบ
        handled = {c.index for c in table.columns}
        header = rows[table.header_row - 1] if table.header_row <= len(rows) else []
        width = max((len(r) for r in body), default=0)
        for col in range(MAIN_LABEL_COLUMN + 1, width):
            if col in handled:
                continue
            for offset, row in enumerate(body):
                if len(row) <= col or not _is_numeric_cell(row[col]):
                    continue
                row_index = table.first_data_row + offset
                raw_label = raw_labels[offset]
                records.append(T1BRecord(
                    key=self._build_key(ctx, sheet_role, section_title, parent_plan,
                                        plan_role, hierarchy[offset],
                                        normalize_label(raw_label)),
                    row_kind=ROW_KIND_UNSUPPORTED_COLUMN,
                    raw_label=raw_label,
                    raw_value=row[col],
                    raw_header_label=header[col] if len(header) > col else None,
                    section_title_raw=section_title_raw,
                    project_ordinal_raw=project_ordinal,
                    sheet_name_actual=facts.name,
                    sheet_index_actual=facts.index,
                    sheet_class=sheet_class,
                    cell_ref=f"{_column_letter(col)}{row_index}",
                    row_index=row_index,
                    header_row=table.header_row,
                    agency_name=ctx["agency_name"],
                    uncertainty=(UNC_UNSUPPORTED_VALUE_COLUMN,),
                ))
        return records

    def _extract_unmapped_sheet(
        self, rows, *, ctx, sheet_role, section_title, section_title_raw, parent_plan,
        project_ordinal, plan_role, facts, sheet_class, reason,
        header_row: int | None = None,
    ) -> list[T1BRecord]:
        """ชีตที่ layout ยังไม่ map — บันทึกทุกแถวที่มีเนื้อหา **ห้ามทิ้งเงียบ**

        ค่าที่พบเก็บเป็น ``raw_value`` เท่านั้น ไม่ normalize
        เพราะยังไม่รู้ว่าคอลัมน์ใดคือค่าและคอลัมน์ใดคือหน่วย
        """
        numbered = [
            (index, row) for index, row in enumerate(rows, start=1)
            if any(c is not None for c in row)
        ]
        return self._unmapped_rows(
            numbered, reason=reason, ctx=ctx, sheet_role=sheet_role,
            section_title=section_title, section_title_raw=section_title_raw,
            parent_plan=parent_plan, project_ordinal=project_ordinal,
            plan_role=plan_role, facts=facts, sheet_class=sheet_class,
            header_row=header_row,
        )

    def _unmapped_rows(
        self, numbered_rows, *, reason, ctx, sheet_role, section_title,
        section_title_raw, parent_plan, project_ordinal, plan_role, facts,
        sheet_class, header_row: int | None = None,
    ) -> list[T1BRecord]:
        """บันทึกแถวที่ยังตีความไม่ได้ — **ห้ามทิ้งเงียบ**

        ``reason`` รับได้ทั้งเครื่องหมายเดียวและหลายเครื่องหมาย —
        🔴 ชีตหนึ่งอาจไม่ถูก map ด้วย **มากกว่าหนึ่งเหตุผล** และผู้ตรวจต้องเห็นครบ
        (blocker #2 · ชีตประกอบที่มีผู้สมัครหัวเรื่องที่มีเลขข้อ)
        """
        reasons = (reason,) if isinstance(reason, str) else tuple(reason)
        records: list[T1BRecord] = []
        for row_index, row in numbered_rows:
            raw_label = next((c for c in row if isinstance(c, str) and c.strip()), None)
            unit = next(
                (u for u in (resolve_declared_unit(c) for c in row) if u != UNIT_UNRESOLVED),
                UNIT_UNRESOLVED,
            )
            records.append(T1BRecord(
                key=self._build_key(ctx, sheet_role, section_title, parent_plan,
                                    plan_role, (), normalize_label(raw_label)),
                row_kind=ROW_KIND_UNMAPPED,
                declared_unit=unit,
                is_monetary=is_monetary(unit),
                raw_label=raw_label,
                raw_value=tuple(row),
                section_title_raw=section_title_raw,
                project_ordinal_raw=project_ordinal,
                sheet_name_actual=facts.name,
                sheet_index_actual=facts.index,
                sheet_class=sheet_class,
                row_index=row_index,
                header_row=header_row,
                agency_name=ctx["agency_name"],
                uncertainty=reasons,
            ))
        return records

    def _to_envelope(
        self, rec: T1BRecord, path: Path, source_hash: str, ctx
    ) -> CanonicalEnvelope:
        if rec.row_kind == ROW_KIND_VALUE and rec.cell_ref:
            location = SourceLocation(
                location_kind=LocationKind.EXCEL_CELL,
                sheet=rec.sheet_name_actual, cell=rec.cell_ref, row=rec.row_index,
            )
        else:
            location = SourceLocation(
                location_kind=LocationKind.EXCEL_ROW,
                sheet=rec.sheet_name_actual, row=rec.row_index,
            )

        if rec.row_kind == ROW_KIND_UNMAPPED:
            status = ExtractionStatus.PARTIAL
        elif rec.uncertainty:
            status = ExtractionStatus.UNCONFIRMED
        else:
            status = ExtractionStatus.OK

        return CanonicalEnvelope(
            source_file=path,
            source_hash=source_hash,
            dataset_kind=self.dataset_kind,
            agency=rec.agency_name,
            fiscal_year=rec.fiscal_year or ctx["fiscal_year"],
            document_status=ctx["document_status"],
            canonical_record=rec,
            source_location=location,
            declared_unit=rec.declared_unit or None,
            schema_version=self.schema_version,
            extraction_status=status,
            uncertainty=list(rec.uncertainty) + list(ctx["uncertainty"]),
            adapter_name=type(self).__name__,
        )


def summarize(envelopes: list[CanonicalEnvelope]) -> dict[str, Any]:
    """สรุปจำนวน record เพื่อพิสูจน์ว่า **ไม่มีชีตหรือแถวใดหายเงียบ**"""
    by_kind: dict[str, int] = {}
    by_sheet: dict[str, int] = {}
    by_role: dict[str, int] = {}
    unresolved = 0
    for env in envelopes:
        rec = env.canonical_record
        by_kind[rec.row_kind] = by_kind.get(rec.row_kind, 0) + 1
        by_sheet[rec.sheet_name_actual] = by_sheet.get(rec.sheet_name_actual, 0) + 1
        role = rec.key.sheet_role or "(no role)"
        by_role[role] = by_role.get(role, 0) + 1
        if rec.needs_review:
            unresolved += 1
    return {
        "total": len(envelopes),
        "by_row_kind": by_kind,
        "by_sheet_name": by_sheet,
        "by_sheet_role": by_role,
        "needs_review": unresolved,
    }
