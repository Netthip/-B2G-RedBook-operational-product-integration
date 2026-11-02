# -*- coding: utf-8 -*-
"""provenance ของสคริปต์ reviewpack — ไม่มีเส้นทางส่วนบุคคล · fail ดังเมื่อไม่มีข้อมูล

🔴 คำสั่งกิ๊ฟ (7 ก.ย. 2569 · ข้อ A) — สคริปต์ห้าไฟล์ที่เคย untracked
ถูกเก็บเป็น provenance ของเครื่องมือวิจัย โดยมีเงื่อนไข: sanitize เส้นทาง ·
env var สำหรับราก OneDrive · **ไม่ตั้งต้อง fail พร้อมข้อความ ห้ามข้ามเงียบ** ·
ไม่มียอดเงินจริงฝังในซอร์ส · มี deterministic reproduction check

ชุดนี้ **ไม่แตะไฟล์จริงใด ๆ** — ตรวจซอร์สและพฤติกรรมเมื่อไม่มีข้อมูลเท่านั้น
"""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "reviewpack"
SCRIPTS = ["build_review_v3.py", "_v3_main.py", "_v4_grouped.py",
           "_v4_main.py", "_r2_build.py", "_paths.py", "check_provenance.py"]
PERSONAL_PATH = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+(?!someone\b)[A-Za-z0-9._-]+|OneDrive[\\/]")
MONEY = re.compile(r"\b\d{1,3}(?:[,_]\d{3}){2,}\b|\b\d{7,}\b")


# ══════════════════════════════════════════════════════════════════════════════
#  P1 — ซอร์สสะอาด
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("name", SCRIPTS)
def test_no_personal_absolute_path_in_source(name):
    src = (PACK / name).read_text(encoding="utf-8")
    hits = [m.group(0) for m in PERSONAL_PATH.finditer(src)]
    assert not hits, f"{name}: {hits}"


@pytest.mark.parametrize("name", ["_v4_main.py", "_v4_grouped.py", "_r2_build.py",
                                  "_v3_main.py", "build_review_v3.py"])
def test_no_budget_shaped_number_in_source(name):
    """ยอดเงินจริงต้องไม่อยู่ในซอร์ส — seed/ปี/แฮช ไม่นับ"""
    src = (PACK / name).read_text(encoding="utf-8")
    hits = []
    for line in src.splitlines():
        if re.search(r"seed|sha256|hash|20[0-9]{6}|FF[0-9A-F]{6}", line, re.I):
            continue
        hits += MONEY.findall(line)
    assert not hits, f"{name}: {hits}"


@pytest.mark.parametrize("name", SCRIPTS)
def test_source_parses(name):
    ast.parse((PACK / name).read_text(encoding="utf-8"), filename=name)


def test_aggregate_hash_was_filled_in():
    src = (PACK / "_v4_main.py").read_text(encoding="utf-8")
    m = re.search(r'AGGREGATE_HASH_V131 = "([0-9a-f]{64})"', src)
    assert m, "AGGREGATE_HASH_V131 ต้องเป็น SHA-256 จริง ไม่ใช่ placeholder"


# ══════════════════════════════════════════════════════════════════════════════
#  P2 — ไม่มีข้อมูลต้อง fail ดัง ๆ
# ══════════════════════════════════════════════════════════════════════════════

def _run(script: str, env_root: str | None) -> subprocess.CompletedProcess:
    import os

    env = {k: v for k, v in os.environ.items() if k != "REDBOOK_PRIVATE_DATA_ROOT"}
    if env_root is not None:
        env["REDBOOK_PRIVATE_DATA_ROOT"] = env_root
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([sys.executable, str(PACK / script)], env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          timeout=60)


@pytest.mark.parametrize("script", ["_v3_main.py", "_v4_main.py", "_r2_build.py",
                                    "check_provenance.py"])
def test_missing_private_root_fails_loudly(script):
    r = _run(script, None)
    assert r.returncode == 2, (r.returncode, r.stderr[-400:])
    assert "REDBOOK_PRIVATE_DATA_ROOT" in r.stderr
    assert "PRIVATE DATASET NOT AVAILABLE" in r.stderr


def test_nonexistent_private_root_fails_loudly(tmp_path):
    r = _run("check_provenance.py", str(tmp_path / "does-not-exist"))
    assert r.returncode == 2
    assert "ไม่มีอยู่" in r.stderr


def test_missing_root_produces_no_output_file(tmp_path, monkeypatch):
    """fail ดังแล้วต้อง **ไม่เขียนอะไร** — ครึ่งไฟล์อันตรายกว่าไม่มีไฟล์"""
    before = set(p.name for p in PACK.iterdir())
    _run("_r2_build.py", None)
    after = set(p.name for p in PACK.iterdir())
    assert before == after


# ══════════════════════════════════════════════════════════════════════════════
#  P3 — manifest คือลายนิ้วมือ ไม่ใช่เนื้อหา
# ══════════════════════════════════════════════════════════════════════════════

def test_manifest_exists_and_has_the_four_artifacts():
    m = json.loads((PACK / "PROVENANCE_MANIFEST.json").read_text(encoding="utf-8"))
    assert set(m) == {"frozen_baseline_v1.3.1", "round1_working_v1.3.1",
                      "round1_working_v1.4.0", "round2_working_v1.3.1"}
    for key, entry in m.items():
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), key
        assert entry["size_bytes"] > 0
        assert entry["sheets"] and all(isinstance(v, int) for v in entry["sheets"].values())
        assert entry["baseline"] and entry["produced_by"]


def test_manifest_contains_no_content_fields():
    """ห้ามมีค่าเซลล์ ยอดเงิน หรือคำตอบผู้ตรวจในไฟล์ที่เข้า git"""
    raw = (PACK / "PROVENANCE_MANIFEST.json").read_text(encoding="utf-8")
    # seed ของการสุ่ม (เช่น 20260901) และขนาดไฟล์ไม่ใช่ยอดเงิน — ตัดออกก่อนสแกน
    scan = re.sub(r"seed \d+|\"size_bytes\": \d+", "", raw)
    assert not MONEY.search(scan), "พบตัวเลขทรงยอดเงิน"
    for forbidden in ("verdict", "reason", "amt_a", "amt_b", "confidence", "ยืนยัน"):
        assert forbidden not in raw, forbidden


def test_manifest_frozen_baseline_hash_matches_the_declared_baseline():
    """v1.3.1 pristine baseline ต้องขึ้นต้น 3fe4438b ตามที่บันทึกไว้ตอน freeze (28 ส.ค.)"""
    m = json.loads((PACK / "PROVENANCE_MANIFEST.json").read_text(encoding="utf-8"))
    assert m["frozen_baseline_v1.3.1"]["sha256"].startswith("3fe4438b")


def test_generated_excel_is_gitignored():
    """ไฟล์ที่สคริปต์ผลิต (.xlsx) ต้องถูก ignore ไม่ว่าวางที่ไหนในโครงการ"""
    r = subprocess.run(["git", "check-ignore", "-q",
                        "reviewpack/HUMAN_CHECK_SAMPLE_primary_R2_WORKING_v1.3.1.xlsx"],
                       cwd=REPO, capture_output=True)
    assert r.returncode == 0, "ไฟล์ Excel ที่ผลิตต้องถูก .gitignore กัน"
