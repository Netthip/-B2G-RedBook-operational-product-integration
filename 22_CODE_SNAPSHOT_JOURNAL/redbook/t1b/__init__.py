# -*- coding: utf-8 -*-
"""ชั้น T1B — สมุดงานคาดแดง/เล่มฟ้ารูปแบบจริง (``OFFICIAL_AO_WORKBOOK``)

**สายงานผลิตภัณฑ์ · เกิดหลัง Evidence Index freeze (1 ก.ย. 2569)**
ป้ายกำกับผลงานของชั้นนี้: ``PRODUCT EVIDENCE — POST-FREEZE``
🔴 ห้ามนำผลของชั้นนี้ย้อนกลับไปอ้างว่าเป็นผลของ frozen T1A evaluation

ฐานอำนาจ: ``09_RESEARCH_BRIDGE/GIFT_MASTER_DIRECTIVE_T1B.md`` (Gift · 1 ก.ย. 2569)

ข้อบังคับที่ผูกทั้งแพ็กเกจ
  - ห้ามแตะเส้นทาง T1A ที่ freeze แล้ว (``redbook/t1/`` · ``FlatDataTableAdapter``)
  - ห้ามใช้ mapping หรือตัวหารร่วมกับ T1A (``RES-D-24`` · ``RES-Q-01``)
  - ห้ามใช้ชื่อชีต · index ของชีต · prefix ตัวอักษร · สี tab เป็น identity key

สถานะ: ``t1b-structural-0.1.0`` — ชั้น resolver เท่านั้น ยังไม่มีการเปรียบเทียบ
"""
from .header import (
    align_years,
    locate_header_row,
    parse_year_label,
    resolve_year_columns,
    resolve_year_columns_merged,
    YearTable,
    CategoryColumn,
    CategoryTable,
    find_year_tables,
    find_category_tables,
    PeriodLabel,
    parse_period_label,
    normalize_period_label,
    resolve_period_columns,
)
from .hierarchy import parse_hierarchy
from .categories import (
    CANONICAL_CATEGORIES,
    CATEGORY_INVESTMENT,
    CATEGORY_OPERATING,
    CATEGORY_OTHER_EXPENDITURE,
    CATEGORY_PERSONNEL,
    CATEGORY_SUBSIDY,
    CATEGORY_TOTAL,
    CATEGORY_UNRESOLVED,
    resolve_budget_category,
)
from .rollup import (
    ROLLUP_VERSION,
    STATUS_ROUNDING_RESIDUE_CANDIDATE,
    check_rollups_for_envelopes,
    RollupCheck,
    RollupResult,
    check_rollups,
)
from .compare import COMPARE_VERSION, CompareResult, Finding, Location, compare
from .keys import KEY_FROZEN_ON, KEY_VERSION, T1BKey
from .matching import (
    MATCHING_VERSION,
    SIDE_BASELINE,
    SIDE_CURRENT,
    MatchPair,
    MatchResult,
    SidedRecord,
    YearScope,
    match_records,
    scope_of,
)
from .normalize import (
    fiscal_years_in,
    normalize_label,
    split_leading_number,
    strip_fiscal_years,
)
from .roles import (
    DOCUMENT_LEVEL_AGENCY,
    DOCUMENT_LEVEL_MINISTRY,
    DOCUMENT_LEVEL_UNKNOWN,
    SHEET_CLASS_COVER,
    SHEET_CLASS_MAIN,
    SHEET_CLASS_SUPPORTING,
    SHEET_CLASS_UNKNOWN,
    SECTION_ROLE_PLAN,
    SECTION_ROLE_PROJECT,
    SheetFacts,
    canonical_section,
    classify_sheet,
    split_project_title,
    find_title,
    title_candidates,
    title_evidence,
    TitleCandidate,
    TitleEvidence,
    resolve_document_level,
    resolve_plan_role,
    resolve_sheet_role,
)
from .units import (
    UNIT_BAHT,
    UNIT_MILLION_BAHT,
    UNIT_PERCENT,
    UNIT_UNRESOLVED,
    amounts_equal,
    comparable_units,
    find_sheet_unit_declaration,
    has_row_unit_column,
    is_monetary,
    normalize_amount,
    resolve_declared_unit,
)

STRUCTURAL_VERSION = "t1b-structural-0.2.0"

__all__ = [
    "STRUCTURAL_VERSION",
    "KEY_VERSION",
    "KEY_FROZEN_ON",
    "MATCHING_VERSION",
    "COMPARE_VERSION",
    "MatchPair",
    "SidedRecord",
    "YearScope",
    "scope_of",
    "SIDE_BASELINE",
    "SIDE_CURRENT",
    "MatchResult",
    "match_records",
    "Finding",
    "Location",
    "CompareResult",
    "compare",
    "T1BKey",
    "SheetFacts",
    "normalize_label",
    "split_leading_number",
    "resolve_sheet_role",
    "resolve_document_level",
    "resolve_plan_role",
    "classify_sheet",
    "canonical_section",
    "split_project_title",
    "strip_fiscal_years",
    "fiscal_years_in",
    "SECTION_ROLE_PLAN",
    "SECTION_ROLE_PROJECT",
    "find_title",
    "title_candidates",
    "title_evidence",
    "TitleCandidate",
    "TitleEvidence",
    "DOCUMENT_LEVEL_MINISTRY",
    "DOCUMENT_LEVEL_AGENCY",
    "DOCUMENT_LEVEL_UNKNOWN",
    "SHEET_CLASS_MAIN",
    "SHEET_CLASS_COVER",
    "SHEET_CLASS_SUPPORTING",
    "SHEET_CLASS_UNKNOWN",
    "locate_header_row",
    "parse_year_label",
    "PeriodLabel",
    "parse_period_label",
    "normalize_period_label",
    "resolve_period_columns",
    "resolve_year_columns",
    "resolve_year_columns_merged",
    "YearTable",
    "CategoryTable",
    "find_year_tables",
    "find_category_tables",
    "CANONICAL_CATEGORIES",
    "CATEGORY_UNRESOLVED",
    "resolve_budget_category",
    "CategoryColumn",
    "ROLLUP_VERSION",
    "STATUS_ROUNDING_RESIDUE_CANDIDATE",
    "check_rollups_for_envelopes",
    "RollupCheck",
    "RollupResult",
    "check_rollups",
    "align_years",
    "parse_hierarchy",
    "resolve_declared_unit",
    "normalize_amount",
    "amounts_equal",
    "comparable_units",
    "find_sheet_unit_declaration",
    "has_row_unit_column",
    "is_monetary",
    "UNIT_MILLION_BAHT",
    "UNIT_BAHT",
    "UNIT_PERCENT",
    "UNIT_UNRESOLVED",
]
