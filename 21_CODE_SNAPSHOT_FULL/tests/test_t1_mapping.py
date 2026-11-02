# -*- coding: utf-8 -*-
"""ทดสอบ G1–G2: canonical schema · semantic mapping · schema conflict"""
import pytest

from conftest_t1 import DEFAULT_DEFS, make_row, write_t1
from redbook.t1.canonical import (CanonicalT1Record, DataQualityHalt,
                                  EvidenceLocation, UNIT_CONFIRMED)
from redbook.t1.datadict import DataDictError, read_schema
from redbook.t1.loader import load_records
from redbook.t1.semantic_map import (DATADICT_TO_CANONICAL, amount_unit_profile,
                                     build_mapping, detect_schema_conflicts)


def test_mapping_uses_datadict_not_physical_column_name(tmp_path):
    """คอลัมน์กายภาพชื่อ objc_5 ต้อง map เข้า canonical เดียวกับ objc"""
    physical = [d[0] for d in DEFAULT_DEFS]
    physical[8] = "objc_5"          # จำลองไฟล์ พ.ร.บ. 2569
    p = write_t1(tmp_path / "b.xlsx", [make_row()], physical_names=physical,
                 extra_blank_column=True)
    schema = read_schema(p, "T-B")
    mapping = build_mapping(schema)

    col = next(c for c in mapping.columns if c.datadict_field == "objc")
    assert col.canonical_field == "objective_category"
    assert col.source_column == "objc_5"
    assert col.physical_name_drift is True
    assert col.datadict_definition == "ชื่องบรายจ่าย"
    assert col.schema_fingerprint  # บันทึก fingerprint ไว้เป็นหลักฐาน
    # คอลัมน์ที่ 14 ที่ไม่มีใน Data Dict ต้องถูกรายงาน ไม่ใช่เงียบหาย
    assert mapping.extra_physical_columns


def test_no_schema_conflict_when_definitions_match(tmp_path):
    a = write_t1(tmp_path / "a.xlsx", [make_row()])
    physical = [d[0] for d in DEFAULT_DEFS]
    physical[8] = "objc_5"
    b = write_t1(tmp_path / "b.xlsx", [make_row()], physical_names=physical)
    assert detect_schema_conflicts(read_schema(a, "A"), read_schema(b, "B")) == []


def test_schema_conflict_detected_when_definition_differs(tmp_path):
    """กรณีจริงของโครงการ: item_name นิยามต่างกันระหว่างปี"""
    a = write_t1(tmp_path / "a.xlsx", [make_row()])
    defs_b = [(n, "รายการ" if n == "item_name" else d) for n, d in DEFAULT_DEFS]
    b = write_t1(tmp_path / "b.xlsx", [make_row()], defs=defs_b)

    conflicts = detect_schema_conflicts(read_schema(a, "A"), read_schema(b, "B"))
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.datadict_field == "item_name"
    assert c.canonical_field == "item_label"
    assert c.definition_a == "ลักษณะรายจ่าย"
    assert c.definition_b == "รายการ"
    assert "ลักษณะรายจ่าย" in c.reason() and "รายการ" in c.reason()


def test_amount_unit_profile_is_confirmed_with_evidence(tmp_path):
    p = write_t1(tmp_path / "a.xlsx", [make_row()])
    profile = amount_unit_profile(build_mapping(read_schema(p, "A")))
    assert profile["declared_unit"] == "บาท"
    assert profile["scale_factor"] == 1.0
    assert profile["unit_confidence"] == UNIT_CONFIRMED
    assert "Data Dict" in profile["evidence"]


def test_loader_produces_six_amount_values_and_evidence(tmp_path):
    p = write_t1(tmp_path / "a.xlsx", [make_row(amount=5920800)])
    schema = read_schema(p, "T1-01")
    recs = load_records(p, build_mapping(schema), schema)
    assert len(recs) == 1
    r = recs[0]
    assert r.amount_stored == 5920800
    assert r.amount_displayed == "5920800"
    assert r.declared_unit == "บาท"
    assert r.scale_factor == 1.0
    assert r.amount_normalized == 5920800
    assert r.unit_confidence == UNIT_CONFIRMED
    assert r.evidence_location.amount_cell == "M2"   # คอลัมน์ที่ 13 แถวที่ 2
    assert r.evidence_location.sha256 == schema.sha256
    assert r.row_ordinal == 1


def test_required_field_empty_halts_instead_of_guessing(tmp_path):
    bad = make_row()
    bad[5] = None                     # plan_name ว่าง
    p = write_t1(tmp_path / "a.xlsx", [bad])
    schema = read_schema(p, "A")
    with pytest.raises(DataQualityHalt) as exc:
        load_records(p, build_mapping(schema), schema)
    assert "plan_name" in str(exc.value)


def test_amount_as_text_with_comma_is_read_not_guessed(tmp_path):
    row = make_row(amount="1,250,000")
    p = write_t1(tmp_path / "a.xlsx", [row])
    schema = read_schema(p, "A")
    r = load_records(p, build_mapping(schema), schema)[0]
    assert r.amount_stored == 1250000
    assert r.amount_displayed == "1,250,000"   # เก็บรูปแบบเดิมไว้เป็นหลักฐาน


def test_unreadable_amount_becomes_none_and_halts(tmp_path):
    row = make_row(amount="ไม่ระบุ")
    p = write_t1(tmp_path / "a.xlsx", [row])
    schema = read_schema(p, "A")
    with pytest.raises(DataQualityHalt):
        load_records(p, build_mapping(schema), schema)


def test_missing_sheets_raise_safe_error(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    p = tmp_path / "empty.xlsx"
    wb.save(p)
    wb.close()
    with pytest.raises(DataDictError):
        read_schema(p, "X")


def test_every_canonical_target_exists_on_record():
    fields = set(CanonicalT1Record().to_dict())
    for canonical in DATADICT_TO_CANONICAL.values():
        assert canonical in fields, canonical


def test_evidence_location_label():
    loc = EvidenceLocation(file_label="T1-01", sheet_name="data", amount_cell="M42")
    assert loc.label() == "T1-01 · data!M42"
