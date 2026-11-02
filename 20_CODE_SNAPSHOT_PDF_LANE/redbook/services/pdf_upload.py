# -*- coding: utf-8 -*-
"""รับ PDF ที่ผู้ใช้เลือกจากเครื่อง — ด่านตาม Security Gate #23 (Bo แนะนำ 28 ต.ค. · กิ๊ฟเลือก "อัปโหลดจากเครื่อง")

ด่านที่มีอยู่แล้วใน :func:`storage.files.save_stream`: ชนิดไฟล์จากเนื้อไฟล์ · จำกัดขนาด · เก็บนอกโฟลเดอร์เว็บด้วยรหัสของ
ระบบ · SHA-256 · ด่าน holdout · ด่านที่เพิ่มที่นี่:

* **โครงสร้าง PDF** — เปิดด้วย PDFium ได้จริง (ไม่เสีย ไม่เข้ารหัส) และมีอย่างน้อย 1 หน้า
* **จำกัดจำนวนหน้า** :data:`MAX_PDF_PAGES` (ปรับด้วย ``REDBOOK_MAX_PDF_PAGES``)
* **ไฟล์เสีย** — ไม่ผ่านด่านใด = ลบสำเนาที่เก็บแล้วทันที + บันทึกเหตุการณ์ความปลอดภัย + ข้อความภาษาคน (ไม่มี path)
* **แหล่งที่มา** — ผู้ใช้ใส่ลิงก์หน้าเว็บทางการที่ดาวน์โหลดมาได้ (http/https เท่านั้น) · ระบบ **เก็บไว้เป็นหลักฐาน
  ไม่ไปดึงเอง** · เส้นทางในเครื่องที่ติดมาในลิงก์ถูกกลบตอนบันทึก (privacy 0.2.2)

🔴 ไม่มีการดึงไฟล์จากลิงก์ (Bo: ระยะถัดไป ต้องมีด่านปลายทาง/redirect/เครือข่ายภายใน)
"""
from __future__ import annotations

import os
import re

from .. import holdout
from ..pdfbook import reader
from ..storage import audit, files as filestore

#: จำนวนหน้าสูงสุดของ PDF ที่รับ — เล่มรวมงบประมาณจริงราว 500–1,400 หน้า
MAX_PDF_PAGES = int(os.environ.get("REDBOOK_MAX_PDF_PAGES", "3000"))
MAX_SOURCE_URL = 1000
_URL = re.compile(r"^https?://[^\s<>\"'`]+$", re.IGNORECASE)


class UploadError(ValueError):
    """ปฏิเสธไฟล์ — ``event`` = รหัสเหตุการณ์ความปลอดภัย · ข้อความอ่านได้ ไม่มี path"""

    def __init__(self, message: str, event: str):
        super().__init__(message)
        self.event = event


def _reject(message: str, event: str, stored=None, **detail):
    if stored is not None:
        filestore.delete_stored(stored.stored_name)
    audit.security_event(event, "warning", {"purpose": "source_pdf", **detail})
    raise UploadError(message, event)


def clean_source_url(url: str) -> str:
    """ลิงก์หน้าเว็บที่ดาวน์โหลดมา (ไม่บังคับ) — ว่าง หรือ http(s) ไม่มีช่องว่าง ไม่เกิน 1,000 ตัวอักษร · ไม่ดึง"""
    url = (url or "").strip()
    if not url:
        return ""
    if len(url) > MAX_SOURCE_URL or not _URL.match(url):
        raise UploadError("ลิงก์แหล่งที่มาต้องขึ้นต้นด้วย https:// หรือ http:// และไม่มีช่องว่าง (ระบบเก็บไว้เป็น"
                          "หลักฐาน ไม่ไปดาวน์โหลดเอง)", "source_url_invalid")
    return url


def check_pdf(path) -> int:
    """จำนวนหน้า — เปิดด้วย PDFium ไม่ได้ (เสีย/เข้ารหัส) หรือไม่มีหน้า หรือหน้าเกินเพดาน = :class:`UploadError`"""
    try:
        pages = reader.page_count(path)
    except holdout.HoldoutViolation:
        raise
    except Exception:  # noqa: BLE001 — pypdfium2 ยก PdfiumError ต่างชนิดกันตามสาเหตุ (เสีย · รหัสผ่าน)
        raise UploadError("เปิดไฟล์ PDF นี้ไม่ได้ (ไฟล์เสีย หรือมีรหัสผ่าน) — ดาวน์โหลดจากเว็บทางการใหม่แล้วลองอีกครั้ง",
                          "pdf_unreadable")
    if pages < 1:
        raise UploadError("ไฟล์ PDF นี้ไม่มีหน้าเอกสาร", "pdf_empty")
    if pages > MAX_PDF_PAGES:
        raise UploadError(f"ไฟล์ PDF นี้มี {pages:,} หน้า เกินที่ระบบรับ ({MAX_PDF_PAGES:,} หน้า)", "pdf_too_many_pages")
    return pages


NOT_PDF_MESSAGE = "ไฟล์นี้ไม่ใช่ PDF ที่อ่านได้ — ช่องนี้รับเฉพาะไฟล์ PDF ของเอกสารต้นฉบับ"
_TYPE_EVENTS = frozenset({"upload_rejected_unknown_type", "upload_rejected_bad_zip", "upload_rejected_not_xlsx",
                          "upload_rejected_no_workbook", "upload_rejected_zip_bomb",
                          "upload_rejected_zip_too_many_members"})


def accept_pdf(stream, filename: str):
    """(StoredFile, จำนวนหน้า) — ผ่านทุกด่านแล้วเท่านั้น · ไม่ผ่าน = ไม่มีไฟล์ค้างในที่เก็บ"""
    if holdout.is_holdout(filename or ""):
        _reject(holdout.UPLOAD_NOTICE, "p1_holdout_upload_blocked")
    try:
        stored = filestore.save_stream(stream, filename)
    except filestore.UploadRejected as e:
        # ด่านชนิดไฟล์รวมพูดถึง Excel — สายนี้รับ PDF อย่างเดียว จึงใช้ข้อความของสาย PDF (event เดิม)
        _reject(NOT_PDF_MESSAGE if e.event in _TYPE_EVENTS else e.user_message, e.event)
    if stored.kind != "pdf":
        _reject("ช่องนี้รับเฉพาะไฟล์ PDF ของเอกสารต้นฉบับ", "upload_not_pdf", stored)
    try:
        pages = check_pdf(filestore.path_for(stored.stored_name))
    except UploadError as e:
        _reject(str(e), e.event, stored)
    return stored, pages


__all__ = ["MAX_PDF_PAGES", "UploadError", "clean_source_url", "check_pdf", "accept_pdf"]
