# -*- coding: utf-8 -*-
"""บันทึกผลทดสอบของสายเทียบเล่ม PDF ผูกกับ commit จริง — ตอบ REVIEW 6340074844 ข้อ 4

พิมพ์ (และเขียนไฟล์ถ้าระบุ ``--out``) : commit · สถานะ worktree (สะอาด/มีไฟล์ค้าง พร้อมรายชื่อ) · รุ่นตัวสกัด/โปรไฟล์ ·
คำสั่งที่รันจริง · จำนวน passed/failed/skipped · เหตุผลที่ข้ามแต่ละข้อ · เวลา

    python scripts/pdfpair_test_record.py                       # ชุดเต็ม
    python scripts/pdfpair_test_record.py --tests tests/test_pdfpair.py --out <ไฟล์.json>

ไม่ออกอินเทอร์เน็ต · ไม่อ่านข้อมูลชุดพัฒนาเอง (เทสต์ private ข้ามเองเมื่อไม่มีไฟล์ และเหตุผลจะอยู่ในบันทึก)
🔴 รายชื่อไฟล์ค้างใน worktree อาจมีชื่อที่ไม่ควรเผยแพร่ — ตรวจก่อนนำไปลงที่สาธารณะ
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def record(tests: list[str]) -> dict:
    sys.path.insert(0, str(ROOT))
    from redbook.pdfbook import PDFBOOK_VERSION, profile, thai_repair
    cmd = [sys.executable, "-m", "pytest", "-q", "-rsfE", "-p", "no:cacheprovider", *tests]
    started = dt.datetime.now().astimezone()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    out = p.stdout + p.stderr
    counts = {k: int(v) for v, k in re.findall(r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed)", out)}
    # ชื่อเทสต์ที่ล้ม/error — บันทึกไว้เสมอ (ข้อที่ล้มแบบสุ่มต้องระบุได้จากบันทึก ไม่ต้องรันใหม่เดา)
    failures = [ln.strip() for ln in out.splitlines() if ln.startswith(("FAILED ", "ERROR "))]
    skips = [{"count": int(n), "where": w.strip(), "reason": r.strip()}
             for n, w, r in re.findall(r"SKIPPED \[(\d+)\] ([^:]+?\.py(?::\d+)?): (.+)", out)]   # ข้ามทั้งไฟล์ = ไม่มีเลขบรรทัด
    dirty = [x for x in _git("status", "--porcelain").splitlines() if x.strip()]
    return {
        "commit": _git("rev-parse", "HEAD"), "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "worktree_clean": not dirty, "worktree_changes": dirty,
        "versions": {"pdfbook": PDFBOOK_VERSION, "profile": profile.PROFILE_VERSION,
                     "profile_status": profile.PROFILE_STATUS, "thai_repair": thai_repair.THAI_REPAIR_VERSION},
        "command": " ".join(["python", "-m", "pytest", "-q", "-rsfE", "-p", "no:cacheprovider", *tests]),
        "exit_code": p.returncode, "counts": counts, "failures": failures, "skipped": skips,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tests", nargs="*", default=[], help="เส้นทางเทสต์ (ว่าง = ชุดเต็ม)")
    ap.add_argument("--out", help="เขียนบันทึกเป็น JSON ที่ไฟล์นี้ด้วย")
    a = ap.parse_args()
    rec = record(a.tests)
    text = json.dumps(rec, ensure_ascii=False, indent=2)
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    return 0 if rec["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
