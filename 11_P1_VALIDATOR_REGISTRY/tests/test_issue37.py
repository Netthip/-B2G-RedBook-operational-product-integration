"""#37 regression cases — synthetic fixtures only; no operational workbooks."""
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LC = load_module("issue37_leak", "11_P1_VALIDATOR_REGISTRY/leak_check.py")
BR = load_module("issue37_registry", "11_P1_VALIDATOR_REGISTRY/build_registry.py")
DRAW = load_module("issue37_draw", "09_RESEARCH_BRIDGE/tools/final_eval_draw.py")
PATTERNS = [(key, "synthetic", "SYNTHETIC_PRIVATE_TOKEN_") for key in "ABCDEFGH"]


def zip_bytes(name, data):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, data)
    return buffer.getvalue()


@pytest.mark.parametrize("member", ["inner.zip", "embedded.bin"])
def test_nested_archive_is_incomplete_instead_of_false_pass(tmp_path, member):
    inner = zip_bytes("payload.txt", b"SYNTHETIC_PRIVATE_TOKEN_" * 100)
    outer = tmp_path / "outer.zip"
    outer.write_bytes(zip_bytes(member, inner))
    assert LC.run([str(outer)], PATTERNS, "", False, io.StringIO()) == 3


def test_corrupt_nested_office_archive_is_incomplete(tmp_path):
    outer = tmp_path / "outer.zip"
    outer.write_bytes(zip_bytes("embedded.xlsx", b"not a valid archive"))
    assert LC.run([str(outer)], PATTERNS, "", False, io.StringIO()) == 3


def test_single_archive_still_detects_payload_and_accepts_clean_file(tmp_path):
    outer = tmp_path / "outer.zip"
    outer.write_bytes(zip_bytes("payload.txt", b"SYNTHETIC_PRIVATE_TOKEN_"))
    assert LC.run([str(outer)], PATTERNS, "", False, io.StringIO()) == 1
    outer.write_bytes(zip_bytes("payload.txt", b"clean synthetic fixture"))
    assert LC.run([str(outer)], PATTERNS, "", False, io.StringIO()) == 0


@pytest.mark.parametrize("relative,sheets", [
    ("synthetic-review/plain.xlsx", ["Data"]),
    ("plain/mock_case.xlsx", ["Data"]),
    ("plain/SYNTHETIC_case.xlsx", ["Data"]),
    ("plain/schema_case.xlsx", ["README", "P1"]),
    ("plain/instrument.xlsx", ["00_README"]),
])
def test_names_and_sheet_layout_do_not_authorize_public_preview(tmp_path, relative, sheets):
    root = tmp_path / "data"
    path = root / relative
    path.parent.mkdir(parents=True)
    workbook = Workbook()
    workbook.active.title = sheets[0]
    workbook.active["A1"] = "SYNTHETIC TEST FIXTURE"
    for sheet in sheets[1:]:
        workbook.create_sheet(sheet)
    workbook.save(path)
    record = BR.build_record(str(path), str(root), 1)
    BR.annotate([record])
    assert record["read_only_verified"] is True
    assert record["publishable_to_github"] is False
    assert BR.public_preview_rows([record]) == []


def candidate_rows(count=3):
    return [{"unit_id": f"U{i}", "stratum": "S-GOV" if i % 2 else "S-PO",
             "eligible": "true"} for i in range(count)]


@pytest.mark.parametrize("target", [-1, 0, 1, 2, 4])
def test_target_cannot_override_protocol_sample_size(target):
    with pytest.raises(DRAW.DrawStop):
        DRAW.draw(candidate_rows(), "synthetic", target)


def test_protocol_target_selects_three_or_two_and_keeps_order_invariance():
    rows = candidate_rows()
    result = DRAW.draw(rows, "synthetic", 3)
    assert sum(map(len, result["selected"].values())) == 3
    assert DRAW.draw(rows[::-1], "synthetic", 3)["selected"] == result["selected"]
    assert sum(map(len, DRAW.draw(candidate_rows(2), "synthetic", 3)["selected"].values())) == 2
    with pytest.raises(DRAW.DrawStop):
        DRAW.draw(candidate_rows(1), "synthetic", 3)


def test_cli_zero_target_returns_stop(tmp_path):
    protocol = tmp_path / "protocol.txt"
    protocol.write_text("synthetic protocol", encoding="utf-8")
    candidates = tmp_path / "candidates.csv"
    candidates.write_text("unit_id,stratum,eligible\nU1,S-GOV,true\nU2,S-PO,true\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "09_RESEARCH_BRIDGE/tools/final_eval_draw.py"),
                             "--seed-from", str(protocol), "--candidates", str(candidates),
                             "--target", "0"], capture_output=True)
    assert result.returncode == 3
    assert b"STOP:" in result.stdout
    assert b"selected:" not in result.stdout
