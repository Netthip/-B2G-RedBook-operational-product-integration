# -*- coding: utf-8 -*-
"""เปิดโหมดสาธิตด้วยคำสั่งเดียว — สร้างไฟล์สังเคราะห์ ตั้งงานตรวจ แล้วเปิดเว็บ

    python scripts/demo_launch.py

สิ่งที่สคริปต์นี้ทำ

1. ชี้โฟลเดอร์ข้อมูลไปที่ ``.data_demo/`` — **แยกจากข้อมูลงานจริงใน ``.data/``**
   งานสาธิตจึงไม่ปนกับงานจริงของผู้ใช้ และลบทิ้งทั้งก้อนได้โดยไม่กระทบอะไร
2. สร้างคู่สมุดงาน AO **สังเคราะห์ 100%** (``scripts/demo_ao_workbooks.py``)
3. ตั้งงานตรวจหนึ่งงาน แล้วใส่ไฟล์ทั้งสองฝั่งผ่าน **เส้นทางเก็บไฟล์จริง**
   ของผลิตภัณฑ์ (ตรวจชนิดไฟล์จากไบต์จริง · คิดแฮช · บันทึก Audit Trail)
4. เปิดเว็บที่ ``127.0.0.1`` แล้วบอก URL ที่ต้องเปิด

จากนั้นผู้ใช้เดินเองครบทั้งหกขั้นบนหน้าจอ: ให้ระบบหาความต่าง → พิจารณา
ทีละรายการ → ตรวจก่อนส่งออก → ส่งออกชุดงาน

🔴 **SYNTHETIC DEMONSTRATION DATA** — ผลตรวจที่ได้จากโหมดนี้เป็นผลจากไฟล์
ที่แต่งขึ้นทั้งหมด ห้ามรายงานว่าเป็นข้อผิดพลาดที่พบในเอกสารจริง
และห้ามใช้เป็นหลักฐานงานวิจัย

ตัวเลือก
    ``--reset``      ล้างโฟลเดอร์สาธิตทิ้งก่อนเริ่มใหม่
    ``--no-serve``   เตรียมข้อมูลอย่างเดียว ไม่เปิดเว็บ (ใช้ตอนทดสอบ)
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_DATA_DIR = PROJECT_ROOT / ".data_demo"

PROJECT_NAME = "งานสาธิต — เทียบฉบับก่อนและหลังปรับลด (ข้อมูลสังเคราะห์)"
PROJECT_NOTE = ("ข้อมูลสาธิตที่แต่งขึ้นทั้งหมด ไม่ใช่เอกสารจริง "
                "ใช้สำหรับเดินเส้นทางการทำงานให้ครบหนึ่งรอบ")
PROJECT_MODE = "before_after_reduction"


def _utf8_console() -> None:
    """คอนโซล Windows ภาษาไทยใช้ code page 874 ซึ่งพิมพ์อักขระบางตัวไม่ได้"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _seed(files_dir: Path) -> tuple[str, Path, Path]:
    """สร้างไฟล์สาธิตและงานตรวจหนึ่งงาน — คืน ``(project_id, ไฟล์ A, ไฟล์ B)``"""
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    import demo_ao_workbooks as gen
    from redbook import config
    from redbook.storage import files as filestore
    from redbook.storage import repository as repo
    from redbook.storage import t1b_preflight, t1b_repo
    from redbook.storage.db import init_db

    config.ensure_dirs()
    init_db()
    t1b_repo.init_t1b_schema()
    t1b_preflight.init_preflight_schema()

    # งานสาธิตมีได้งานเดียว — เปิดซ้ำแล้วต้องเจอของเดิม ไม่ใช่กองงานซ้ำ ๆ
    for row in repo.list_projects():
        if row["name"] == PROJECT_NAME:
            pf = repo.project_files(row["id"])
            if pf.get("A") and pf.get("B"):
                return row["id"], files_dir, files_dir

    path_a, path_b = gen.build(files_dir)
    pid = repo.create_project(PROJECT_NAME, PROJECT_MODE, PROJECT_NOTE)
    for side, path in (("A", path_a), ("B", path_b)):
        with open(path, "rb") as fh:
            stored = filestore.save_stream(fh, path.name)
        repo.attach_file(pid, side, stored, {
            "fiscal_year": 2569 if side == "A" else 2570,
            "agency_name": gen.AGENCY,
            "doc_kind": "ข้อมูลสาธิต (สังเคราะห์)",
        })
    return pid, path_a, path_b


def main() -> None:
    parser = argparse.ArgumentParser(description="เปิดโหมดสาธิตของ RedBook Verify")
    parser.add_argument("--reset", action="store_true",
                        help="ล้างโฟลเดอร์ข้อมูลสาธิตทิ้งก่อนเริ่มใหม่")
    parser.add_argument("--no-serve", action="store_true",
                        help="เตรียมข้อมูลอย่างเดียว ไม่เปิดเว็บ")
    args = parser.parse_args()

    _utf8_console()

    if args.reset and DEMO_DATA_DIR.exists():
        shutil.rmtree(DEMO_DATA_DIR, ignore_errors=True)

    # 🔴 ต้องตั้งก่อน import แพ็กเกจ redbook — ``config`` อ่านค่านี้ตอน import
    # ถ้าตั้งช้ากว่านั้น โหมดสาธิตจะไปเขียนทับฐานข้อมูลของงานจริง
    os.environ["REDBOOK_DATA_DIR"] = str(DEMO_DATA_DIR)
    os.environ["REDBOOK_DEMO"] = "1"

    pid, path_a, path_b = _seed(DEMO_DATA_DIR / "demo_files")

    from redbook import config

    url = f"http://{config.BIND_HOST}:{config.BIND_PORT}"
    print("=" * 66)
    print(" RedBook Verify — โหมดสาธิต (ข้อมูลสังเคราะห์ 100%)")
    print("=" * 66)
    print(f" เปิดที่      : {url}/projects/{pid}")
    print(f" โฟลเดอร์ข้อมูล: {config.DATA_DIR}")
    print(f" ไฟล์ฝั่ง A    : {Path(path_a).name}")
    print(f" ไฟล์ฝั่ง B    : {Path(path_b).name}")
    print("-" * 66)
    print(" ขั้นต่อไปบนหน้าจอ: กด “ให้ระบบหาความต่าง” แล้วเดินตามแถบขั้นตอน 1–6")
    print(" ข้อมูลสาธิตแยกจากงานจริงใน .data/ — ลบ .data_demo/ ทิ้งได้ทุกเมื่อ")
    print("=" * 66)

    if args.no_serve:
        return

    import uvicorn

    from redbook.web.launch import uvicorn_options

    uvicorn.run("redbook.app:app", host=config.BIND_HOST, port=config.BIND_PORT,
                **uvicorn_options())


if __name__ == "__main__":
    main()
