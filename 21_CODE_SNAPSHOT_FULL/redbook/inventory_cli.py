# -*- coding: utf-8 -*-
"""Phase 2A CLI — สำรวจไฟล์จริงแบบอ่านอย่างเดียว แล้วผลิตรายงานสำหรับยืนยัน mapping

การใช้งาน (จากโฟลเดอร์โครงการ):
    .venv\\Scripts\\python.exe -m redbook.inventory_cli "<ไฟล์หรือโฟลเดอร์>" [...]
        [--outdir <โฟลเดอร์ผลลัพธ์>] [--max-rows 4000] [--max-cols 60]

พฤติกรรมที่รับประกัน:
  - อ่านไฟล์ต้นฉบับอย่างเดียว ไม่คัดลอก ไม่แก้ไข — พิสูจน์ด้วย SHA-256 ก่อน/หลังอ่าน
    ถ้าแฮชไม่ตรงกัน โปรแกรมหยุดทันทีด้วยรหัสผิดพลาด
  - ผลลัพธ์ (มีข้อมูลจริง) เขียนลงโฟลเดอร์ที่กำหนดเท่านั้น ค่าเริ่มต้นคือ
    .data/inventory/<เวลา> ในโครงการ ซึ่ง .gitignore กันไว้แล้ว
  - ปฏิเสธ outdir ที่อยู่ใน OneDrive เว้นแต่ระบุ --allow-onedrive อย่างชัดแจ้ง
  - ไฟล์ PDF จะถูกบันทึกใน FILE_INVENTORY (ชื่อ/ขนาด/SHA-256/ชนิดจริง) เท่านั้น
    การอ่านเนื้อหา PDF เป็นงาน Phase 3 — ไม่ทำในเครื่องมือนี้
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import APP_NAME, holdout
from .core.hashing import sha256_file
from .readers import excel_inventory
from .readers.excel_reader import ExcelReadError
from .report import inventory_report
from .storage.files import UploadRejected, detect_kind
from . import config

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BAD_ARGS = 2


def _use_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _collect_files(inputs) -> list:
    out = []
    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            for pattern in ("*.xlsx", "*.xlsm", "*.pdf"):
                out.extend(sorted(p.glob(pattern)))
        elif p.is_file():
            out.append(p)
        else:
            print(f"[ข้าม] ไม่พบ: {raw}")
    seen, files = set(), []
    for p in out:
        rp = p.resolve()
        if rp not in seen and not p.name.startswith("~$"):
            seen.add(rp)
            files.append(p)

    # 🔴 ด่านชุดข้อมูลกันไว้ — กันที่นี่ **ก่อน** ทุกจุดที่จะเปิดอ่านไฟล์
    # และ **ประกาศออกมา** ว่ากันอะไรไปบ้าง ห้ามกรองทิ้งเงียบ ๆ
    files, skipped = holdout.partition(files)
    for path, reason in skipped:
        print(f"[กันไว้] {path.name} — ชุดข้อมูล P1 holdout ({reason})")
    if skipped:
        print(f"[กันไว้] รวม {len(skipped)} ไฟล์ · สถานะด่าน "
              f"{holdout.HOLDOUT_STATUS}")
    return files


def _guard_outdir(outdir: Path, allow_onedrive: bool) -> bool:
    if "onedrive" in str(outdir.resolve()).lower() and not allow_onedrive:
        print("[หยุด] โฟลเดอร์ผลลัพธ์อยู่ใน OneDrive — รายงานมีข้อมูลจริง "
              "ห้ามวางในโฟลเดอร์ที่ sync ขึ้นคลาวด์")
        print("       ถ้าตั้งใจจริงให้ระบุ --allow-onedrive (ไม่แนะนำ)")
        return False
    return True


def run_inventory(paths, outdir: Path, max_rows: int, max_cols: int) -> int:
    entries = []
    xlsx_invs = []
    for p in paths:
        size = p.stat().st_size
        sha_before = sha256_file(p)
        try:
            kind = detect_kind(p)
        except UploadRejected as e:
            kind = "unknown"
            note = e.user_message
        else:
            note = ""
        inv = None
        if kind == "xlsx":
            try:
                inv = excel_inventory.inventory_workbook(
                    p, max_scan_rows=max_rows, max_cols=max_cols)
            except ExcelReadError as e:
                note = str(e)
        elif kind == "pdf":
            note = "ไฟล์ PDF — บันทึกไว้ในบัญชีเท่านั้น การอ่านเนื้อหาเป็นงาน Phase 3"
        sha_after = sha256_file(p)
        if sha_after != sha_before:
            print(f"[หยุด] SHA-256 ของ {p.name} เปลี่ยนระหว่างอ่าน — "
                  "ไฟล์ถูกโปรแกรมอื่นแก้ไข หรือมีความผิดปกติ ต้องสอบสวนก่อน")
            return EXIT_ERROR
        entry = {"file": {"name": p.name, "size_bytes": size, "kind": kind,
                          "sha256_before": sha_before, "sha256_after": sha_after},
                 "inventory": inv, "note": note}
        entries.append(entry)
        if inv is not None:
            xlsx_invs.append(entry)
        status = "อ่านสำเร็จ" if inv else (note or kind)
        print(f"[ไฟล์] {p.name} — {kind} — {status} — SHA ก่อน=หลัง ✔")

    comparison = None
    if len(xlsx_invs) == 2:
        comparison = excel_inventory.compare_structures(
            xlsx_invs[0]["inventory"], xlsx_invs[1]["inventory"])
        print(f"[เทียบ] โครงสร้าง {xlsx_invs[0]['file']['name']} ↔ "
              f"{xlsx_invs[1]['file']['name']}")
    elif len(xlsx_invs) > 2:
        print("[หมายเหตุ] มีไฟล์ Excel มากกว่า 2 ไฟล์ — รายงานโครงสร้างรายไฟล์ครบทุกไฟล์ "
              "แต่ยังเทียบข้ามไฟล์อัตโนมัติเฉพาะกรณี 2 ไฟล์ (รันทีละคู่เพื่อเทียบ)")

    run_meta = {
        "tool": f"{APP_NAME} · {excel_inventory.INVENTORY_VERSION}",
        "parser": f"openpyxl (ดูเวอร์ชันใน inventory.json)",
        "checked_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "scan_limits": {"max_rows": max_rows, "max_cols": max_cols},
    }

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "FILE_INVENTORY.md").write_text(
        inventory_report.render_file_inventory(entries, run_meta), encoding="utf-8")
    (outdir / "WORKBOOK_STRUCTURE_REPORT.md").write_text(
        inventory_report.render_workbook_structure(entries, run_meta), encoding="utf-8")
    (outdir / "MAPPING_CANDIDATES.md").write_text(
        inventory_report.render_mapping_candidates(entries, comparison, run_meta),
        encoding="utf-8")
    (outdir / "inventory.json").write_text(
        json.dumps({"run": run_meta, "entries": entries, "comparison": comparison},
                   ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    print("")
    print(f"[ผลลัพธ์] {outdir}")
    for name in ("FILE_INVENTORY.md", "WORKBOOK_STRUCTURE_REPORT.md",
                 "MAPPING_CANDIDATES.md", "inventory.json"):
        print(f"  - {name}")
    print("")
    print("[เตือน] รายงานมีข้อมูลจริงจากเอกสาร — เก็บในเครื่องเท่านั้น "
          "ห้าม commit เข้า git และห้ามวางใน OneDrive")
    print("[ถัดไป] ตรวจ MAPPING_CANDIDATES.md แล้วยืนยันทางเลือกก่อนเริ่ม Phase 2C")
    return EXIT_OK


def main(argv=None) -> int:
    _use_utf8_console()
    ap = argparse.ArgumentParser(
        prog="redbook.inventory_cli",
        description="Phase 2A — สำรวจโครงสร้างไฟล์จริงแบบอ่านอย่างเดียว (ไม่เดา mapping)")
    ap.add_argument("inputs", nargs="+", help="ไฟล์ .xlsx/.xlsm/.pdf หรือโฟลเดอร์")
    ap.add_argument("--outdir", default=None,
                    help="โฟลเดอร์เก็บรายงาน (ค่าเริ่มต้น: .data/inventory/<เวลา>)")
    ap.add_argument("--max-rows", type=int, default=4000,
                    help="จำนวนแถวสูงสุดที่สแกนต่อชีต (ค่าเริ่มต้น 4000)")
    ap.add_argument("--max-cols", type=int, default=60,
                    help="จำนวนคอลัมน์สูงสุดที่สแกนต่อชีต (ค่าเริ่มต้น 60)")
    ap.add_argument("--allow-onedrive", action="store_true",
                    help="ยอมให้เขียนรายงานลงโฟลเดอร์ใน OneDrive (ไม่แนะนำ)")
    args = ap.parse_args(argv)

    files = _collect_files(args.inputs)
    if not files:
        print("[หยุด] ไม่พบไฟล์ที่จะสำรวจ")
        return EXIT_BAD_ARGS

    if args.outdir:
        outdir = Path(args.outdir)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        outdir = config.DATA_DIR / "inventory" / f"inv_{stamp}"
    if not _guard_outdir(outdir, args.allow_onedrive):
        return EXIT_BAD_ARGS

    return run_inventory(files, outdir, args.max_rows, args.max_cols)


if __name__ == "__main__":
    sys.exit(main())
