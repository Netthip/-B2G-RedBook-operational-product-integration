# -*- coding: utf-8 -*-
"""ดึง PDF ต้นฉบับจากลิงก์ทางการในทะเบียนเล่ม แล้วผูกเป็นภาพหลักฐานของงานตรวจ (#24)

    python scripts/fetch_source_pdfs.py --project prj_xxx            # งานเดียว
    python scripts/fetch_source_pdfs.py --all                         # ทุกงานที่ผูกเล่มไว้

ทำไมอยู่นอกแพ็กเกจ ``redbook``
    ระบบเป็น local-first — เทสต์สถาปัตยกรรมห้ามไลบรารีเครือข่ายในแพ็กเกจ เครื่องมือนี้จึงอยู่ใน
    ``scripts/`` แบบเดียวกับ ``build_book_catalog.py`` และส่งไฟล์เข้าระบบผ่าน
    ``files.save_stream`` (ด่าน sealed-hash · ตรวจชนิดไฟล์จากไบต์จริง) + ``source_pdfs.link``
    (บันทึก Audit พร้อม URL และเวลาที่ดึง)

กติกา
    * ดึงเฉพาะ URL ที่ผูกไว้กับงานตรวจ (``project_books.pdf_url``) — ไม่ค้น ไม่เดาลิงก์
    * โฮสต์ต้องอยู่ใน allowlist (ค่าเริ่มต้น = เว็บสำนักงบประมาณ ``www.bb.go.th`` · https เท่านั้น)
    * ขนาดไม่เกิน ``REDBOOK_MAX_UPLOAD_MB`` · ต้องขึ้นต้นด้วย ``%PDF`` · ฝั่งที่มี PDF แล้วข้าม
      (เว้น ``--force``) · ดึงไม่ได้ = รายงานแล้วข้าม ผู้ใช้แนบเองได้ที่หน้าหลักฐาน

🔴 **เส้นแบ่งการประเมิน (#22 · คำตัดสิน Bo 8 ต.ค. 2569)** — **ยังไม่อนุมัติ**ให้เปิดหรือดาวน์โหลด
เล่ม candidate ไม่ว่าโดยเครื่องมือหรือโดยคน · บังคับด้วยโค้ด: ลิงก์ทางการจะถูกดึงก็ต่อเมื่อรหัสเล่มอยู่ใน
**ชุดพัฒนาที่ได้รับอนุญาต** (``--approved-dev-set`` ไฟล์ JSON รายการ book_id ที่แยกจากชุดประเมินแล้ว)
ไม่ระบุ = ปฏิเสธทุกเล่ม · เทสต์ใช้เซิร์ฟเวอร์ภายในเครื่อง + PDF สังเคราะห์เท่านั้น

🔴 **redirect ทุกทอดต้องผ่าน allowlist** (Bo 8 ต.ค.) — ตัวจัดการ redirect ตรวจ URL ปลายทางของ
ทุกทอด และตรวจ URL สุดท้ายซ้ำ · ออกนอกโฮสต์ที่อนุญาตหรือลดเป็น http = หยุดทันที ไม่ดาวน์โหลด
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HOSTS = ("www.bb.go.th", "bb.go.th")
TIMEOUT_S = 60


def _allowed(url: str, hosts: set[str], allow_http_local: bool) -> bool:
    u = urlparse(url or "")
    if u.hostname not in hosts:
        return False
    if u.scheme == "https":
        return True
    return allow_http_local and u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost")


class RedirectRefused(Exception):
    """redirect พาออกนอก allowlist (โฮสต์อื่น / ลดเป็น http)"""


MAX_REDIRECTS = 5


def _opener(hosts: set[str], allow_http_local: bool):
    """opener ที่ตรวจ **ทุกทอด** ของ redirect ก่อนตามไป"""

    class _Checked(urllib.request.HTTPRedirectHandler):
        max_redirections = MAX_REDIRECTS

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not _allowed(newurl, hosts, allow_http_local):
                raise RedirectRefused(f"redirect ไปยังปลายทางที่ไม่อยู่ใน allowlist ({code})")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    return urllib.request.build_opener(_Checked)


def fetch_one(url: str, *, max_bytes: int, hosts: set[str] = frozenset(DEFAULT_HOSTS),
              allow_http_local: bool = False) -> tuple[bytes, str]:
    """ดาวน์โหลด — คืน ``(ไบต์, URL สุดท้ายหลัง redirect)`` · ทุกทอดต้องผ่าน allowlist"""
    if not _allowed(url, hosts, allow_http_local):
        raise RedirectRefused("URL ต้นทางไม่อยู่ใน allowlist")
    req = urllib.request.Request(url, headers={"User-Agent": "RedBookVerify-local/0.1 (evidence fetch)"})
    with _opener(hosts, allow_http_local).open(req, timeout=TIMEOUT_S) as resp:  # noqa: S310
        final_url = resp.geturl()
        if not _allowed(final_url, hosts, allow_http_local):          # ตรวจซ้ำที่ปลายทางสุดท้าย
            raise RedirectRefused("ปลายทางสุดท้ายไม่อยู่ใน allowlist")
        data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("ไฟล์ใหญ่เกินที่ระบบรับได้")
    if not data.startswith(b"%PDF"):
        raise ValueError("ปลายทางไม่ใช่ไฟล์ PDF")
    return data, final_url


def _is_local(url: str) -> bool:
    return urlparse(url or "").hostname in ("127.0.0.1", "localhost")


def run(project_ids: list[str] | None, *, hosts: set[str], force: bool = False,
        allow_http_local: bool = False, approved_ids: set[str] | None = None, log=print) -> dict:
    """คืน ``{"linked": n, "skipped": n, "failed": n}`` · ``project_ids=None`` = ทุกงานที่ผูกเล่ม"""
    sys.path.insert(0, str(ROOT))
    from redbook import config
    from redbook.storage import book_links, source_pdfs
    from redbook.storage import files as filestore
    from redbook.storage import repository as repo
    from redbook.storage.db import init_db

    config.ensure_dirs()
    init_db()
    book_links.init_schema()
    source_pdfs.init_schema()
    if project_ids is None:
        project_ids = [p["id"] for p in repo.list_projects()]
    out = {"linked": 0, "skipped": 0, "failed": 0}
    for pid in project_ids:
        refs = book_links.for_project(pid)
        have = source_pdfs.for_project(pid)
        for side in ("A", "B"):
            ref = refs.get(side)
            if not ref or not ref.get("pdf_url"):
                continue
            if side in have and not force:
                out["skipped"] += 1
                continue
            url = ref["pdf_url"]
            if not _allowed(url, hosts, allow_http_local):
                log(f"[ข้าม] {pid} ฝั่ง {side}: โฮสต์ไม่อยู่ใน allowlist")
                out["failed"] += 1
                continue
            # 🔴 #22 — ลิงก์จริงดึงได้เฉพาะเล่มในชุดพัฒนาที่ได้รับอนุญาต (แยกจากชุดประเมิน)
            if not _is_local(url) and ref.get("book_id") not in (approved_ids or set()):
                log(f"[ปฏิเสธ] {pid} ฝั่ง {side}: เล่มนี้ไม่อยู่ในชุดพัฒนาที่ได้รับอนุญาต (#22)")
                out["refused"] = out.get("refused", 0) + 1
                continue
            try:
                data, final_url = fetch_one(url, max_bytes=config.MAX_UPLOAD_BYTES, hosts=hosts,
                                            allow_http_local=allow_http_local)
                name = Path(urlparse(url).path).name or f"{ref.get('book_id', side)}.pdf"
                if not name.lower().endswith(".pdf"):
                    name += ".pdf"
                stored = filestore.save_stream(io.BytesIO(data), name)
                source_pdfs.link(pid, side, stored, origin=source_pdfs.ORIGIN_OFFICIAL,
                                 source_url=final_url,
                                 retrieved_at=datetime.now(timezone.utc).astimezone()
                                 .isoformat(timespec="seconds"))
                log(f"[ผูกแล้ว] {pid} ฝั่ง {side}: {stored.size_bytes:,} ไบต์ · sha256 {stored.sha256[:12]}…")
                out["linked"] += 1
            except Exception as e:  # noqa: BLE001 — รายงานแล้วไปต่อ ผู้ใช้แนบเองได้
                log(f"[ไม่สำเร็จ] {pid} ฝั่ง {side}: {type(e).__name__}: {e}")
                out["failed"] += 1
    return out


def main() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="ดึง PDF ต้นฉบับจากลิงก์ทางการในทะเบียนเล่ม")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--project", action="append", help="รหัสงานตรวจ (ระบุซ้ำได้)")
    g.add_argument("--all", action="store_true", help="ทุกงานที่ผูกเล่มไว้")
    ap.add_argument("--data-dir", help="โฟลเดอร์ข้อมูลของระบบ (ค่าเริ่มต้นตาม REDBOOK_DATA_DIR)")
    ap.add_argument("--force", action="store_true", help="ดึงใหม่แม้ฝั่งนั้นมี PDF แล้ว")
    ap.add_argument("--approved-dev-set", help="ไฟล์ JSON รายการ book_id ของชุดพัฒนาที่ได้รับอนุญาต "
                                                "(แยกจากชุดประเมินแล้ว) · ไม่ระบุ = ไม่ดึงเล่มจริงเลย")
    args = ap.parse_args()
    if args.data_dir:
        os.environ["REDBOOK_DATA_DIR"] = args.data_dir
    approved: set[str] = set()
    if args.approved_dev_set:
        import json
        approved = set(json.loads(Path(args.approved_dev_set).read_text(encoding="utf-8")))
    res = run(None if args.all else args.project, hosts=set(DEFAULT_HOSTS), force=args.force,
              approved_ids=approved)
    print(f"สรุป: ผูกแล้ว {res['linked']} · ข้าม {res['skipped']} · ไม่สำเร็จ {res['failed']}"
          f" · ปฏิเสธ (ไม่อยู่ในชุดพัฒนาที่อนุญาต) {res.get('refused', 0)}")


if __name__ == "__main__":
    main()
