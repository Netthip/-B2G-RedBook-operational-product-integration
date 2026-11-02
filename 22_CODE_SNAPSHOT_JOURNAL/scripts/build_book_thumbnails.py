# -*- coding: utf-8 -*-
"""สร้างภาพปก (หน้าแรก) ของเล่มงบประมาณในทะเบียน — เก็บในเครื่องเท่านั้น

    python scripts/build_book_thumbnails.py            # ทำเฉพาะเล่มที่ยังไม่มีภาพ
    python scripts/build_book_thumbnails.py --force    # ทำใหม่ทั้งหมด
    python scripts/build_book_thumbnails.py --limit 5  # ลองเฉพาะ 5 เล่มแรก
    REDBOOK_BOOK_CATALOG=<source_registry.json> python scripts/build_book_thumbnails.py --no-download
        # ใช้ภาพเดิมซ้ำเมื่อ PDF ต้นทาง (url) ตรงกัน — รหัสเล่มของ #27 ต่างจากทะเบียนเดิม แต่ไฟล์ทางการชุดเดียวกัน

ทำไมต้องมี: ผู้ใช้แยกเล่มด้วยหน้าปกได้เร็วกว่าอ่านชื่อยาว (โจทย์ Library UI — "ใช้ภาพปก
เป็นส่วนสำคัญของ UI เพื่อลด text wall") แต่หน้าเผยแพร่ทางการไม่มีภาพปกแยกให้

หลักการ (กิ๊ฟอนุญาตในแชต 7 ต.ค. 2569 · "อนุญาต เก็บเฉพาะในเครื่อง")
- ดาวน์โหลด PDF ทางการทีละไฟล์ลงโฟลเดอร์ชั่วคราว → วาดหน้าแรกเป็น JPEG เล็ก → **ลบ PDF ทันที**
- ภาพปกอยู่ใต้ ``DATA_DIR/book_thumbs/`` (``.data/`` ถูก ignore) — **ห้าม commit / ห้ามขึ้น repo**
  จนกว่าจะผ่าน leak_check ตามเงื่อนไขเดียวกับภาพหน้าจอ (D5 #24)
- เว้นจังหวะระหว่างคำขอ ไม่ยิงเว็บทางการถี่
- บันทึก ``manifest.json`` (แหล่ง · เวลา · ขนาด · sha256 ของ PDF ที่ใช้วาด) เพื่อย้อนตรวจได้
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from redbook.services import books as book_service  # noqa: E402
from redbook.services.books import THUMB_DIR  # noqa: E402  (REDBOOK_THUMB_DIR)

UA = {"User-Agent": "Mozilla/5.0 (RedBookVerify thumbnail builder; public documents only)"}
WIDTH = 320          # px — การ์ดแสดงราว 96–140 px · หน้ารายละเอียดราว 200 px (รองรับจอ 2x)
PAUSE_S = 1.0


def render_first_page(pdf_path: Path, out_path: Path) -> tuple[int, int]:
    import fitz  # PyMuPDF — ใช้เฉพาะสคริปต์นี้ ไม่ใช่ dependency ของแอป

    with fitz.open(pdf_path) as doc:
        page = doc[0]
        zoom = WIDTH / page.rect.width
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        out_path.write_bytes(pix.tobytes("jpg", jpg_quality=78))
        return pix.width, pix.height


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-download", action="store_true",
                    help="ไม่ดาวน์โหลด — ทำเฉพาะเล่มที่มีภาพเดิมจาก PDF url เดียวกัน")
    args = ap.parse_args()

    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = THUMB_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    books = list(book_service.load().books)
    # ภาพเดิมจัดตามรหัสเล่ม — ย้อนหาได้จาก url ของ PDF ที่ใช้วาด (manifest)
    by_url = {m["source_pdf"]: k for k, m in manifest.items()
              if "error" not in m and (THUMB_DIR / f"{k}.jpg").is_file()}
    reused = 0
    if args.limit:
        books = books[: args.limit]
    done = skipped = failed = 0
    with tempfile.TemporaryDirectory(prefix="rbv-thumb-") as tmp:
        for i, b in enumerate(books, 1):
            out = THUMB_DIR / f"{b.id}.jpg"
            if out.exists() and not args.force:
                skipped += 1
                continue
            src_id = by_url.get(b.pdf_url)
            if src_id and src_id != b.id:
                out.write_bytes((THUMB_DIR / f"{src_id}.jpg").read_bytes())
                manifest[b.id] = dict(manifest[src_id], reused_from=src_id)
                reused += 1
                continue
            if args.no_download or not b.pdf_url:
                skipped += 1
                continue
            pdf = Path(tmp) / "src.pdf"
            try:
                req = urllib.request.Request(b.pdf_url, headers=UA)
                with urllib.request.urlopen(req, timeout=120) as resp, pdf.open("wb") as fh:
                    while chunk := resp.read(1 << 16):
                        fh.write(chunk)
                digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
                w, h = render_first_page(pdf, out)
                manifest[b.id] = {
                    "source_pdf": b.pdf_url, "pdf_bytes": pdf.stat().st_size,
                    "pdf_sha256": digest, "width": w, "height": h,
                    "rendered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                done += 1
                print(f"[{i}/{len(books)}] {b.id} ok {w}x{h}")
            except Exception as e:  # เล่มที่วาดไม่ได้ → การ์ดใช้ปกจำลองจาก metadata แทน
                failed += 1
                manifest[b.id] = {"source_pdf": b.pdf_url, "error": f"{type(e).__name__}: {e}"[:300]}
                print(f"[{i}/{len(books)}] {b.id} FAILED {type(e).__name__}")
            finally:
                pdf.unlink(missing_ok=True)   # ไม่เก็บสำเนา PDF
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True),
                                     encoding="utf-8")
            time.sleep(PAUSE_S)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True),
                             encoding="utf-8")
    print(f"done={done} reused={reused} skipped={skipped} failed={failed} dir={THUMB_DIR}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
