# -*- coding: utf-8 -*-
"""เพิ่มเล่ม PDF ลงชั้นเล่มในเครื่อง — ดาวน์โหลดจากเว็บสำนักงบประมาณ (นอกระบบ · ระบบเองไม่ออกอินเทอร์เน็ต)

    # จากคลังเล่ม (#24) — ใช้ปี ลิงก์หน้าเว็บ และลิงก์ดาวน์โหลดที่ทะเบียนบันทึกไว้
    python scripts/shelf_add.py --book bb-2570-18879

    # จากลิงก์ดาวน์โหลดโดยตรง
    python scripts/shelf_add.py https://bb.go.th/download.php?id=34806 --fy 2570 --stage act \\
        --label "ฉบับที่ 3 เล่มที่ 11 (พ.ร.บ.)" [--page https://bb.go.th/topic-detail.php?id=19190] [--key V11_2570_act]

    # ดูเล่มบนชั้น
    python scripts/shelf_add.py --list

ชั้นเล่ม = ``REDBOOK_PDF_SHELF`` หรือ ``<data>/pdf_shelf`` (``--shelf`` ระบุเองได้) · เขียน ``manifest.json`` +
``register.json`` (URL ต้นทาง/ปลายทาง · เวลา · ขนาด · SHA-256) + ``volumes/<key>.pdf`` ·
ดาวน์โหลดผ่าน allowlist เดียวกับชุดพัฒนา (bb.go.th + bbstore.bb.go.th · https · ตรวจ redirect ทุกทอด · ``%PDF``)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_dev_volumes as fdv  # noqa: E402


def _key(label: str, fy: int, stage: str) -> str:
    m = re.search(r"เล่มที่\s*(\d+)", label)
    return f"V{m.group(1) if m else 'X'}_{fy}_{stage}"


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="เพิ่มเล่ม PDF ลงชั้นเล่มในเครื่อง")
    ap.add_argument("url", nargs="?", help="ลิงก์ดาวน์โหลด (download.php?id=…)")
    ap.add_argument("--book", help="รหัสเล่มในคลังเล่ม เช่น bb-2570-18879")
    ap.add_argument("--fy", type=int)
    ap.add_argument("--stage", choices=("draft", "act"))
    ap.add_argument("--label", default="")
    ap.add_argument("--page", default="", help="ลิงก์หน้าเว็บของเล่ม (topic-detail.php?id=…) — ใช้ผูกกับคลังเล่ม")
    ap.add_argument("--key", default="")
    ap.add_argument("--shelf", default="")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)

    import os
    if a.shelf:
        os.environ["REDBOOK_PDF_SHELF"] = a.shelf
    from redbook.services import pdfshelf
    shelf = pdfshelf.shelf_dir()
    if a.list:
        for v in pdfshelf.volumes():
            print(f"{v.key}\t{v.title}\t{v.sha256[:12]}\t{v.book_id or '-'}")
        return 0

    url, fy, stage, label, page = a.url, a.fy, a.stage, a.label, a.page
    if a.book:
        from redbook.services import books
        b = books.catalog().get(a.book)
        if b is None:
            print(f"ไม่พบเล่ม {a.book} ในคลังเล่ม", file=sys.stderr)
            return 2
        url = url or b.pdf_url
        fy = fy or b.fiscal_year
        stage = stage or ("draft" if "ร่าง" in (b.stage or "") else "act" if "พ.ร.บ" in (b.stage or "") else "")
        if not label:
            label = f"ฉบับที่ {b.doc_no} เล่มที่ {b.volume}" if b.volume else b.title
        page = page or b.source_page
    if not url or not fy or stage not in ("draft", "act"):
        print("ต้องมีลิงก์ดาวน์โหลด ปี (--fy) และขั้น (--stage draft|act) — หรือใช้ --book", file=sys.stderr)
        return 2
    key = a.key or _key(label, fy, stage)
    shelf.mkdir(parents=True, exist_ok=True)
    manp, regp = shelf / "manifest.json", shelf / "register.json"
    man = json.loads(manp.read_text(encoding="utf-8")) if manp.exists() else {"volumes": [], "agencies": []}
    reg = json.loads(regp.read_text(encoding="utf-8")) if regp.exists() else {"volumes": {}, "extracts": {}}
    vol = {"key": key, "page": page, "url": url, "fiscal_year": fy, "stage": stage, "label": label or key}
    man["volumes"] = [v for v in man.get("volumes", []) if v.get("key") != key] + [vol]
    one = {"volumes": [vol], "agencies": []}
    try:
        fdv.download(one, shelf, reg)
    finally:
        manp.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
        regp.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ชั้นเล่ม] {shelf} · {key} · SHA-256 {reg['volumes'].get(key, {}).get('sha256', '?')[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
