# -*- coding: utf-8 -*-
"""เปิด target สังเคราะห์สำหรับ security gate — loopback เท่านั้น

    python -m security_gate.target --data-dir DIR --port PORT

* ตั้ง ``REDBOOK_DATA_DIR`` ไป DIR **ก่อน import redbook** (config อ่านตอน import)
* สร้างคู่สมุดงานสังเคราะห์ด้วย ``scripts/demo_ao_workbooks.py`` และตั้งงานตรวจหนึ่งงาน
  ผ่านเส้นทางเก็บไฟล์จริงของผลิตภัณฑ์ (เหมือน ``scripts/demo_launch.py``)
* เปิด uvicorn ด้วยตัวเลือกเดียวกับ ``run_local.py`` (:func:`redbook.web.launch.uvicorn_options`)
  เพื่อให้สิ่งที่สแกนคือสิ่งที่ผู้ใช้เปิดจริง

🔴 bind ที่ 127.0.0.1 เท่านั้น — ไม่มีตัวเลือกให้ bind อย่างอื่น · SYNTHETIC ONLY
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--seed-only", action="store_true")
    args = ap.parse_args(argv)

    data_dir = Path(args.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["REDBOOK_DATA_DIR"] = str(data_dir)
    os.environ["REDBOOK_HOST"] = "127.0.0.1"
    os.environ["REDBOOK_PORT"] = str(args.port)
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

    import demo_ao_workbooks as gen  # noqa: E402
    from redbook import config  # noqa: E402
    from redbook.storage import files as filestore  # noqa: E402
    from redbook.storage import repository as repo  # noqa: E402
    from redbook.storage import t1b_preflight, t1b_repo  # noqa: E402
    from redbook.storage.db import init_db  # noqa: E402

    config.ensure_dirs()
    init_db()
    t1b_repo.init_t1b_schema()
    t1b_preflight.init_preflight_schema()

    files_dir = data_dir / "synthetic_files"
    files_dir.mkdir(parents=True, exist_ok=True)
    path_a, path_b = gen.build(files_dir)
    pid = repo.create_project("SECURITY GATE — target สังเคราะห์", "before_after_reduction",
                              "ข้อมูลสังเคราะห์ 100% สำหรับการตรวจความปลอดภัยเท่านั้น")
    for side, path in (("A", path_a), ("B", path_b)):
        with open(path, "rb") as fh:
            stored = filestore.save_stream(fh, path.name)
        repo.attach_file(pid, side, stored, {"fiscal_year": 2569 if side == "A" else 2570,
                                             "agency_name": gen.AGENCY,
                                             "doc_kind": "ข้อมูลสาธิต (สังเคราะห์)"})
    (data_dir / "TARGET_INFO.json").write_text(
        f'{{"project_id": "{pid}", "files_dir": "synthetic_files", "synthetic": true}}', "utf-8")
    if args.seed_only:
        return 0

    import uvicorn  # noqa: E402
    from redbook.web.launch import uvicorn_options  # noqa: E402

    uvicorn.run("redbook.app:app", host="127.0.0.1", port=args.port, **uvicorn_options())
    return 0


if __name__ == "__main__":
    sys.exit(main())
