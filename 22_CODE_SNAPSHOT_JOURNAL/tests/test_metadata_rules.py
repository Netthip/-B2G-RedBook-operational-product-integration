# -*- coding: utf-8 -*-
"""ทดสอบกฎ M01-M05 และคุณสมบัติการตรวจซ้ำได้ของผลตรวจ"""
from redbook.core.status import MachineStatus
from redbook.rules.finding import assign_ids, result_hash
from redbook.rules.metadata_checks import check_metadata

MODE_YEAR = "year_to_year"
MODE_RED = "before_after_reduction"


def _file(fid, sha, kind="xlsx", year=None, agency=None, doc_kind=None):
    return {"id": fid, "original_name": f"{fid}.xlsx", "sha256": sha, "kind": kind,
            "declared_fiscal_year": year, "declared_agency_code": agency,
            "declared_agency_name": None, "declared_doc_kind": doc_kind}


def _ids(findings):
    return {f["rule_id"] for f in findings}


def test_clean_pair_year_mode_has_no_findings():
    a = _file("A", "a" * 64, year=2569, agency="21016", doc_kind="เอกสารปีงบประมาณ")
    b = _file("B", "b" * 64, year=2570, agency="21016", doc_kind="เอกสารปีงบประมาณ")
    assert check_metadata(MODE_YEAR, a, b) == []


def test_same_file_both_sides_flagged():
    same = "c" * 64
    a = _file("A", same, year=2569, agency="21016")
    b = _file("B", same, year=2570, agency="21016")
    assert "M04" in _ids(check_metadata(MODE_YEAR, a, b))


def test_different_kinds_flagged():
    a = _file("A", "a" * 64, kind="xlsx", year=2569, agency="21016")
    b = _file("B", "b" * 64, kind="pdf", year=2570, agency="21016")
    assert "M05" in _ids(check_metadata(MODE_YEAR, a, b))


def test_year_mode_flags_same_year():
    a = _file("A", "a" * 64, year=2570, agency="21016")
    b = _file("B", "b" * 64, year=2570, agency="21016")
    assert "M01" in _ids(check_metadata(MODE_YEAR, a, b))


def test_year_mode_flags_reversed_sides():
    a = _file("A", "a" * 64, year=2570, agency="21016")
    b = _file("B", "b" * 64, year=2569, agency="21016")
    findings = check_metadata(MODE_YEAR, a, b)
    assert "M01" in _ids(findings)


def test_reduction_mode_flags_different_years():
    a = _file("A", "a" * 64, year=2569, agency="21016", doc_kind="ก่อนปรับลด")
    b = _file("B", "b" * 64, year=2570, agency="21016", doc_kind="หลังปรับลด")
    assert "M01" in _ids(check_metadata(MODE_RED, a, b))


def test_reduction_mode_flags_identical_doc_kind():
    a = _file("A", "a" * 64, year=2570, agency="21016", doc_kind="ก่อนปรับลด")
    b = _file("B", "b" * 64, year=2570, agency="21016", doc_kind="ก่อนปรับลด")
    assert "M03" in _ids(check_metadata(MODE_RED, a, b))


def test_agency_mismatch_and_missing():
    a = _file("A", "a" * 64, year=2569, agency="21016")
    b = _file("B", "b" * 64, year=2570, agency="21017")
    assert "M02" in _ids(check_metadata(MODE_YEAR, a, b))

    a2 = _file("A", "a" * 64, year=2569, agency=None)
    b2 = _file("B", "b" * 64, year=2570, agency="21016")
    assert "M02" in _ids(check_metadata(MODE_YEAR, a2, b2))


def test_missing_year_reported_as_needs_human():
    a = _file("A", "a" * 64, year=None, agency="21016")
    b = _file("B", "b" * 64, year=2570, agency="21016")
    m01 = [f for f in check_metadata(MODE_YEAR, a, b) if f["rule_id"] == "M01"]
    assert m01 and m01[0]["machine_status"] == MachineStatus.NEEDS_HUMAN.value


def test_findings_never_claim_error():
    a = _file("A", "x" * 64, kind="pdf", year=2570, agency="21016", doc_kind="ก่อนปรับลด")
    b = _file("B", "x" * 64, kind="xlsx", year=2568, agency="21099", doc_kind="ก่อนปรับลด")
    allowed = {s.value for s in MachineStatus}
    findings = check_metadata(MODE_RED, a, b)
    assert findings
    for f in findings:
        assert f["machine_status"] in allowed


def test_same_inputs_give_same_result_hash():
    a = _file("A", "a" * 64, year=2570, agency="21016")
    b = _file("B", "b" * 64, year=2570, agency="21017")
    h1 = result_hash(assign_ids("run_1", check_metadata(MODE_YEAR, a, b)))
    h2 = result_hash(assign_ids("run_2", check_metadata(MODE_YEAR, a, b)))
    assert h1 == h2


def test_changed_inputs_change_result_hash():
    a = _file("A", "a" * 64, year=2570, agency="21016")
    b1 = _file("B", "b" * 64, year=2570, agency="21017")
    b2 = _file("B", "b" * 64, year=2570, agency="21018")
    h1 = result_hash(check_metadata(MODE_YEAR, a, b1))
    h2 = result_hash(check_metadata(MODE_YEAR, a, b2))
    assert h1 != h2


def test_finding_codes_are_stable_and_ordered():
    a = _file("A", "z" * 64, kind="pdf", year=2570, agency="21016")
    b = _file("B", "z" * 64, kind="xlsx", year=2570, agency="21099")
    first = assign_ids("run_x", check_metadata(MODE_YEAR, a, b))
    second = assign_ids("run_x", check_metadata(MODE_YEAR, a, b))
    assert [f["finding_code"] for f in first] == [f["finding_code"] for f in second]
    assert [f["id"] for f in first] == [f["id"] for f in second]
    assert first[0]["finding_code"] == "F-0001"
