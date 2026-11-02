# -*- coding: utf-8 -*-
"""ทดสอบ Mapping Profile: ภาชนะการตัดสินใจของผู้ใช้ พร้อมกติกาที่ห้ามละเมิด"""
import pytest

from redbook.rules.mapping_model import (ColumnMapping, Evidence, MappingProfile,
                                         MatchingStep, SheetMapping,
                                         METHOD_FUZZY_NAME, METHOD_NORMALIZED_NAME,
                                         METHOD_OFFICIAL_CODE)


def _profile(**over):
    base = MappingProfile(
        profile_id="p1",
        agency_label="หน่วยงานทดสอบ",
        doc_kind="คาดแดง",
        fiscal_years=[2569, 2570],
        sheet_mappings=[SheetMapping(
            sheet_name="รายละเอียด", role="source_detail",
            header_rows=[4, 5], data_start_row=6, data_end_row=100,
            columns=[
                ColumnMapping(column_letter="B", role="item_code"),
                ColumnMapping(column_letter="E", role="amount",
                              declared_unit="ล้านบาท", scale_to_baht=1_000_000,
                              evidence=[Evidence(sheet="รายละเอียด", ref="F2",
                                                 description="หน่วย : ล้านบาท")]),
            ])],
        matching_ladder=[
            MatchingStep(priority=1, method=METHOD_OFFICIAL_CODE,
                         fields=["item_code"]),
            MatchingStep(priority=2, method=METHOD_NORMALIZED_NAME,
                         fields=["item_name"], suggest_only=True),
        ],
        thresholds={"pct_highlight": 10, "role": "highlight_only"},
    )
    for k, v in over.items():
        setattr(base, k, v)
    return base


def test_valid_profile_passes():
    assert _profile().validate() == []


def test_round_trip_json_and_stable_hash():
    p = _profile()
    h1 = p.content_hash()
    p2 = MappingProfile.from_json(p.to_json())
    assert p2.sheet_mappings[0].columns[1].evidence[0].ref == "F2"
    assert p2.content_hash() == h1
    # ข้อมูลผู้อนุมัติไม่กระทบแฮชเนื้อหา mapping
    p2.approved_by = "ผู้ตรวจ"
    p2.approved_at = "2569-09-01"
    assert p2.content_hash() == h1
    assert p2.is_approved() and not p.is_approved()


def test_fuzzy_must_be_suggest_only():
    p = _profile(matching_ladder=[
        MatchingStep(priority=1, method=METHOD_FUZZY_NAME,
                     fields=["item_name"], suggest_only=False)])
    problems = p.validate()
    assert any("suggest_only" in x for x in problems)


def test_row_order_identity_is_forbidden():
    p = _profile(matching_ladder=[
        MatchingStep(priority=1, method="row_order", fields=["item_sequence"])])
    problems = p.validate()
    assert any("ห้ามใช้ row_order" in x for x in problems)


def test_scale_requires_evidence():
    p = _profile()
    p.sheet_mappings[0].columns[1].evidence = []
    problems = p.validate()
    assert any("ไม่มีหลักฐาน" in x for x in problems)


def test_threshold_must_be_highlight_only():
    p = _profile(thresholds={"pct_highlight": 10})
    problems = p.validate()
    assert any("highlight_only" in x for x in problems)
