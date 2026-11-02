# -*- coding: utf-8 -*-
"""ตรวจว่า artifact ของ Human Review ยังเป็นไฟล์เดิมที่ freeze ไว้หรือไม่

🔴 คำสั่งกิ๊ฟ (7 ก.ย. 2569 · ข้อ A.7) — *deterministic reproduction check
เท่าที่ทำได้ เช่น hash/schema/จำนวนแถว โดยไม่ commit output จริง*

สิ่งที่อยู่ใน git คือ **ลายนิ้วมือ** ของแต่ละไฟล์เท่านั้น — SHA-256 · ขนาด ·
ชื่อชีต · จำนวนแถวต่อชีต · ไม่มีเนื้อในเอกสาร ไม่มียอดเงิน ไม่มีคำตอบของผู้ตรวจ

การใช้งาน::

    python reviewpack/check_provenance.py            # ตรวจเทียบ manifest
    python reviewpack/check_provenance.py --write    # สร้าง/ปรับ manifest ใหม่ (ระวัง)

รหัสออก: ``0`` ตรงทุกไฟล์ · ``1`` มีไฟล์ไม่ตรง · ``2`` ไม่มีพื้นที่ข้อมูลส่วนตัว
(``PRIVATE DATASET NOT AVAILABLE`` — **ไม่ใช่การผ่าน** ต้องรายงานแยกเสมอ)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _paths import (DATA_DIR, PRIVATE_ROOT_ENV, PrivateRootMissing,  # noqa: E402
                    frozen_baseline_v131, human_review_dir)

MANIFEST = Path(__file__).with_name("PROVENANCE_MANIFEST.json")

#: artifact ที่ติดตาม — key · ไฟล์ · สคริปต์ที่ผลิต · baseline ที่สัมพันธ์
ARTIFACTS = {
    "frozen_baseline_v1.3.1": {
        "path": frozen_baseline_v131,
        "produced_by": "_v3_main.py (สำเนา pristine ที่เก็บแยกไว้)",
        "baseline": "v1.3.1 · FROZEN INSTRUMENT BASELINE FOR ROUND 1",
    },
    "round1_working_v1.3.1": {
        "path": lambda: human_review_dir(1)
        / "HUMAN_CHECK_SAMPLE_primary_R1_WORKING_v1.3.1.xlsx",
        "produced_by": "_v3_main.py",
        "baseline": "v1.3.1 · ไฟล์ที่ผู้ตรวจกรอกจริงรอบที่ 1",
    },
    "round1_working_v1.4.0": {
        "path": lambda: human_review_dir(1)
        / "HUMAN_CHECK_SAMPLE_primary_R1_WORKING_v1.4.0.xlsx",
        "produced_by": "_v4_main.py (ผ่าน _v4_grouped.py)",
        "baseline": "v1.4.0 · presentation layer ใหม่ · ย้ายคำตอบ 21/21 จาก v1.3.1",
    },
    "round2_working_v1.3.1": {
        "path": lambda: human_review_dir(2)
        / "HUMAN_CHECK_SAMPLE_primary_R2_WORKING_v1.3.1.xlsx",
        "produced_by": "_r2_build.py",
        "baseline": "v1.3.1 · แบบฟอร์มรอบที่ 2 · seed 20260901 · ไม่มีคำตอบรอบ 1",
    },
}


def fingerprint(path: Path) -> dict:
    """ลายนิ้วมือของไฟล์ — **ไม่อ่านค่าในเซลล์ใด** นอกจากจำนวนแถว"""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        sheets = {ws.title: ws.max_row for ws in wb.worksheets}
    finally:
        wb.close()
    return {
        "filename": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
        "sheets": sheets,
    }


def collect() -> dict:
    out = {}
    for key, spec in ARTIFACTS.items():
        p = spec["path"]()
        if not p.exists():
            out[key] = {"missing": True, "filename": p.name}
            continue
        out[key] = {**fingerprint(p), "produced_by": spec["produced_by"],
                    "baseline": spec["baseline"]}
    return out


def compare(expected: dict, actual: dict) -> list[str]:
    problems = []
    for key, exp in expected.items():
        act = actual.get(key)
        if act is None or act.get("missing"):
            problems.append(f"{key}: ไม่พบไฟล์ {exp.get('filename')}")
            continue
        for field in ("sha256", "size_bytes", "sheets"):
            if exp.get(field) != act.get(field):
                problems.append(f"{key}: {field} ไม่ตรง")
    return problems


def main(argv: list[str]) -> int:
    try:
        actual = collect()
    except PrivateRootMissing:
        return 2                                   # ข้อความพิมพ์ไปแล้วใน _paths

    if "--write" in argv:
        MANIFEST.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        print(f"[เขียน] {MANIFEST.name} · {len(actual)} artifact")
        return 0

    if not MANIFEST.exists():
        print(f"[หยุด] ไม่พบ {MANIFEST.name} — รันด้วย --write ก่อน")
        return 1
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems = compare(expected, actual)
    for key in expected:
        mark = "✓" if not any(pr.startswith(key) for pr in problems) else "✗"
        print(f"  {mark} {key:26s} {expected[key].get('filename')}")
    if problems:
        print("\n[ไม่ตรง]")
        for pr in problems:
            print("  -", pr)
        return 1
    print(f"\n[ตรง] artifact ทั้ง {len(expected)} ไฟล์เหมือนที่ freeze ไว้ทุกไบต์")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))
