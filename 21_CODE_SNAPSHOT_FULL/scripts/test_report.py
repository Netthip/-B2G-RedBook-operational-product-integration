# -*- coding: utf-8 -*-
"""รายงานผลทดสอบแบบแยกชั้น — unit/synthetic · private real-data · skipped · failed

🔴 คำสั่งกิ๊ฟ (7 ก.ย. 2569 · ข้อ G) — ห้ามนับ skip เป็น pass และห้ามทำให้ยอดรวม
"ผ่านทั้งหมด" ชวนเข้าใจผิด · บนเครื่องที่ไม่มีข้อมูลจริง เทสต์ 7 ไฟล์จะขึ้นเป็น
``SKIPPED: PRIVATE DATASET NOT AVAILABLE`` และรายงานนี้แสดงแยกบรรทัด

การใช้งาน::

    python scripts/test_report.py          # รัน pytest ทั้ง repo แล้วสรุป
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
REPORT = ROOT / ".data" / "test_report.json"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
           "-rs", "--tb=short", "--json-report", f"--json-report-file={REPORT}"]
    has_json = subprocess.run([sys.executable, "-c", "import pytest_jsonreport"],
                              capture_output=True).returncode == 0
    if not has_json:
        # ไม่มีปลั๊กอิน json — ใช้ -rA แล้วนับจากบรรทัดสรุป
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs",
               "--tb=short", "-o", "console_output_style=classic"]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = r.stdout + r.stderr

    from conftest import PRIVATE_DATA_TEST_FILES, PRIVATE_SKIP_REASON  # noqa: E402

    unit_pass = priv_pass = priv_skip = failed = other_skip = 0
    if has_json and REPORT.exists():
        data = json.loads(REPORT.read_text(encoding="utf-8"))
        for t in data.get("tests", []):
            fname = Path(t["nodeid"].split("::")[0]).name
            private = fname in PRIVATE_DATA_TEST_FILES
            if t["outcome"] == "passed":
                if private: priv_pass += 1
                else: unit_pass += 1
            elif t["outcome"] == "skipped":
                if private and PRIVATE_SKIP_REASON in json.dumps(t): priv_skip += 1
                else: other_skip += 1
            elif t["outcome"] in ("failed", "error"):
                failed += 1
    else:
        # นับจากบรรทัด "x passed, y skipped" และบรรทัด SKIPPED
        import re
        m = re.search(r"(\d+) passed", out); total_pass = int(m.group(1)) if m else 0
        m = re.search(r"(\d+) failed", out); failed = int(m.group(1)) if m else 0
        m = re.search(r"(\d+) error", out); failed += int(m.group(1)) if m else 0
        priv_skip = out.count(PRIVATE_SKIP_REASON)
        m = re.search(r"(\d+) skipped", out); other_skip = (int(m.group(1)) if m else 0) - priv_skip
        # แยก private pass ด้วยการรันเฉพาะไฟล์ private (ถ้ามีข้อมูล)
        if priv_skip == 0:
            rp = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                 "-m", "private_data"], cwd=ROOT, capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
            m = re.search(r"(\d+) passed", rp.stdout); priv_pass = int(m.group(1)) if m else 0
        unit_pass = total_pass - priv_pass

    print("=" * 60)
    print("TEST REPORT — แยกชั้นตามคำสั่งกิ๊ฟ ข้อ G")
    print("=" * 60)
    print(f"  unit / synthetic tests ผ่าน          : {unit_pass}")
    print(f"  private real-data integration ผ่าน   : {priv_pass}")
    print(f"  SKIPPED: {PRIVATE_SKIP_REASON:<28}: {priv_skip}")
    print(f"  skipped อื่น                         : {other_skip}")
    print(f"  failed / error                       : {failed}")
    print("-" * 60)
    if priv_skip:
        print("  ⚠ เครื่องนี้ไม่มีชุดข้อมูลจริง — ผล private integration ยังไม่ได้พิสูจน์")
    print("  ❌ มีข้อล้มเหลว" if failed else "  ✅ ไม่มีข้อล้มเหลว (skip ไม่นับเป็นผ่าน)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
