# -*- coding: utf-8 -*-
"""คลังไฟล์ที่อัปโหลด — รับไฟล์อย่างระมัดระวังและเก็บด้วยชื่อที่ระบบสร้างเอง

มาตรการที่ใช้ (ผูกกับ Phase 5 — Security Verification):
  - ตรวจชนิดไฟล์จาก "เนื้อไฟล์จริง" (magic bytes + โครงสร้างภายใน) ไม่เชื่อนามสกุล
    และไม่เชื่อ Content-Type ที่เบราว์เซอร์ส่งมา
  - จำกัดขนาดระหว่างสตรีม ตัดทันทีที่เกิน ไม่รอจนอ่านครบ
  - ชื่อไฟล์ภายในสร้างใหม่ทั้งหมด (uuid4 + นามสกุลตามชนิดที่ตรวจได้)
    ชื่อเดิมของผู้ใช้ถูกเก็บเป็น "ข้อความ" ในฐานข้อมูลเท่านั้น ไม่เคยนำไปประกอบ path
  - ตรวจซ้ำอีกชั้นว่า path ปลายทางอยู่ใต้ UPLOAD_DIR จริง (กัน path traversal)
  - เขียนลงโฟลเดอร์ชั่วคราวก่อน แล้วจึงย้าย — ล้มเหลวเมื่อใดลบไฟล์ชั่วคราวทันที
"""
import os
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .. import config
from ..core.hashing import sha256_file
from ..final_holdout import SealedFinalHoldout, check_hash, guard_path

# ลายเซ็นเริ่มต้นไฟล์
_MAGIC_ZIP = b"PK\x03\x04"
_MAGIC_PDF = b"%PDF-"

# ไฟล์ที่ต้องมีจริงในถุง zip ของ xlsx
_XLSX_REQUIRED = ("[Content_Types].xml",)
_XLSX_WORKBOOK_HINTS = ("xl/workbook.xml", "xl/workbook.bin")

# กัน zip bomb: ขนาดหลังคลายบีบอัดรวม และอัตราขยายสูงสุด
MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_EXPANSION_RATIO = 250
#: จำนวนสมาชิกสูงสุดในถุง zip — สมุดงานจริงมีไม่กี่ร้อย · ASVS V5.2.3 ต้องการเพดานจำนวนไฟล์
#: ก่อนคลาย (Security Gate #23 · F-03)
MAX_ZIP_MEMBERS = 5000


class UploadRejected(Exception):
    """ปฏิเสธไฟล์ พร้อมข้อความที่ปลอดภัยพอจะแสดงให้ผู้ใช้เห็น"""

    def __init__(self, user_message: str, event: str, detail: dict = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.event = event
        self.detail = detail or {}


@dataclass
class StoredFile:
    file_id: str
    stored_name: str
    path: Path
    kind: str
    size_bytes: int
    sha256: str
    original_name: str


def sanitize_display_name(name: str) -> str:
    """ทำชื่อไฟล์ของผู้ใช้ให้ปลอดภัยสำหรับ "แสดงผล" เท่านั้น

    ตัดส่วนที่เป็น path ทิ้งทั้งหมด ทั้งเครื่องหมายทับหน้าและทับหลัง และตัดอักขระควบคุมออก
    ค่าที่ได้ยังคงไม่ถูกนำไปใช้เป็นชื่อไฟล์จริงในดิสก์
    """
    if not name:
        return "(ไม่มีชื่อไฟล์)"
    base = str(name).replace("\\", "/").split("/")[-1]
    base = "".join(ch for ch in base if ch.isprintable() and ch not in '\r\n\t')
    base = base.strip().strip(".")
    return base[:180] or "(ไม่มีชื่อไฟล์)"


def detect_kind(path: Path) -> str:
    """ตรวจชนิดไฟล์จากเนื้อไฟล์จริง — คืน 'xlsx' | 'pdf' หรือโยน UploadRejected"""
    guard_path(path)          # #21 — ไม่อ่านแม้แต่หัวไฟล์ในโฟลเดอร์ปิดผนึก
    with open(path, "rb") as fp:
        head = fp.read(8)

    if head.startswith(_MAGIC_PDF):
        return "pdf"

    if head.startswith(_MAGIC_ZIP):
        try:
            with zipfile.ZipFile(path) as zf:
                infos = zf.infolist()
                names = set(zf.namelist())
                total = sum(i.file_size for i in infos)
                packed = sum(i.compress_size for i in infos) or 1
            if len(infos) > MAX_ZIP_MEMBERS:
                raise UploadRejected(
                    "ไฟล์นี้มีจำนวนส่วนประกอบภายในมากผิดปกติ ระบบไม่รับไว้เพื่อความปลอดภัย",
                    "upload_rejected_zip_too_many_members",
                    {"members": len(infos), "limit": MAX_ZIP_MEMBERS})
            if total > MAX_UNCOMPRESSED_BYTES or (total / packed) > MAX_EXPANSION_RATIO:
                raise UploadRejected(
                    "ไฟล์นี้มีอัตราการบีบอัดผิดปกติ ระบบไม่รับไว้เพื่อความปลอดภัย",
                    "upload_rejected_zip_bomb",
                    {"uncompressed": total, "packed": packed})
            if not all(n in names for n in _XLSX_REQUIRED):
                raise UploadRejected(
                    "ไฟล์นี้เป็นไฟล์บีบอัดแต่ไม่ใช่สมุดงาน Excel",
                    "upload_rejected_not_xlsx", {})
            if not any(n in names for n in _XLSX_WORKBOOK_HINTS):
                raise UploadRejected(
                    "ไม่พบส่วนสมุดงานภายในไฟล์ Excel นี้",
                    "upload_rejected_no_workbook", {})
            return "xlsx"
        except zipfile.BadZipFile:
            raise UploadRejected(
                "ไฟล์เสียหายหรือไม่ใช่ไฟล์ Excel ที่อ่านได้",
                "upload_rejected_bad_zip", {})

    raise UploadRejected(
        "ระบบรับเฉพาะไฟล์ Excel (.xlsx/.xlsm) และ PDF เท่านั้น",
        "upload_rejected_unknown_type", {})


def _assert_inside(path: Path, parent: Path) -> None:
    """ยืนยันว่า path อยู่ใต้ parent จริง — กัน path traversal ทุกรูปแบบ"""
    rp, rparent = path.resolve(), parent.resolve()
    if not str(rp).startswith(str(rparent) + os.sep):
        raise UploadRejected("ตำแหน่งจัดเก็บไฟล์ไม่ถูกต้อง",
                             "path_traversal_blocked", {})


def save_stream(stream, original_name: str,
                max_bytes: int = None) -> StoredFile:
    """รับสตรีมไฟล์ → ตรวจขนาด → ตรวจชนิดจริง → เก็บด้วยชื่อภายในใหม่"""
    config.ensure_dirs()
    limit = max_bytes or config.MAX_UPLOAD_BYTES
    display_name = sanitize_display_name(original_name)

    tmp_path = config.TEMP_DIR / f"upload_{uuid.uuid4().hex}.part"
    _assert_inside(tmp_path, config.TEMP_DIR)

    size = 0
    try:
        with open(tmp_path, "wb") as out:
            while True:
                chunk = stream.read(config.UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise UploadRejected(
                        f"ไฟล์ใหญ่เกินที่ระบบรับได้ (สูงสุด {limit // (1024*1024)} MB)",
                        "upload_rejected_too_large",
                        {"limit_bytes": limit})
                out.write(chunk)

        if size == 0:
            raise UploadRejected("ไฟล์ว่าง ไม่มีเนื้อหาให้ตรวจ",
                                 "upload_rejected_empty", {})

        # #21 — ไฟล์ที่ตรงกับชุดประเมินสุดท้าย ห้ามรับเข้าระบบแม้มาทางการอัปโหลด
        try:
            check_hash(sha256_file(tmp_path), "upload")
        except SealedFinalHoldout as exc:
            raise UploadRejected(str(exc), "upload_rejected_sealed_final_holdout",
                                 {"guard_code": exc.code}) from None
        kind = detect_kind(tmp_path)
        ext = config.ALLOWED_KINDS[kind]["ext"]
        file_id = uuid.uuid4().hex
        stored_name = f"{file_id}{ext}"
        final_path = config.UPLOAD_DIR / stored_name
        _assert_inside(final_path, config.UPLOAD_DIR)

        digest = sha256_file(tmp_path)
        os.replace(tmp_path, final_path)
        try:
            os.chmod(final_path, 0o444)   # อ่านอย่างเดียว: ระบบตรวจไม่แก้ไฟล์ต้นฉบับ
        except OSError:
            pass

        return StoredFile(file_id=file_id, stored_name=stored_name, path=final_path,
                          kind=kind, size_bytes=size, sha256=digest,
                          original_name=display_name)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def path_for(stored_name: str) -> Path:
    """หา path ของไฟล์ที่เก็บไว้ โดยยอมรับเฉพาะชื่อภายในที่ระบบสร้างเอง"""
    name = str(stored_name)
    if "/" in name or "\\" in name or ".." in name:
        raise UploadRejected("ชื่อไฟล์ภายในไม่ถูกต้อง", "path_traversal_blocked",
                             {"stored_name": name[:80]})
    p = config.UPLOAD_DIR / name
    _assert_inside(p, config.UPLOAD_DIR)
    return p


def delete_stored(stored_name: str) -> bool:
    """ลบไฟล์ที่ผู้ใช้อัปโหลดหนึ่งไฟล์ — คืน ``True`` ถ้ามีไฟล์ให้ลบจริง

    🔴 ใช้ :func:`path_for` เป็นตัวตรวจเส้นทาง เพื่อให้การลบผ่านด่านเดียวกับ
    การอ่าน — ชื่อที่ออกนอก ``UPLOAD_DIR`` จะถูกปฏิเสธก่อนถึงบรรทัดที่ลบ

    ไม่ยกข้อยกเว้นเมื่อไม่พบไฟล์ เพราะการลบซ้ำต้องได้ผลเหมือนเดิม
    (ผู้ใช้กดปุ่มลบสองครั้งได้)
    """
    path = path_for(stored_name)
    try:
        # 🔴 ไฟล์ที่เก็บไว้ถูกตั้งเป็นอ่านอย่างเดียว (0o444) ตอนบันทึก เพื่อกัน
        # ไม่ให้ระบบตรวจแก้ไฟล์ต้นฉบับ · บน Windows ไฟล์อ่านอย่างเดียวลบไม่ได้
        # จึงต้องคืนสิทธิ์เขียนเฉพาะไฟล์นี้ ทันทีก่อนลบ
        os.chmod(path, 0o666)
    except FileNotFoundError:
        return False
    except OSError:
        pass                      # บางระบบไฟล์ไม่รองรับ chmod — ลองลบต่อไป
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def purge_temp(older_than_seconds: int = 3600) -> int:
    """ลบไฟล์ชั่วคราวที่ค้าง — เรียกตอนแอปเริ่มทำงาน"""
    import time
    config.ensure_dirs()
    now, removed = time.time(), 0
    for p in config.TEMP_DIR.glob("upload_*.part"):
        try:
            if now - p.stat().st_mtime > older_than_seconds:
                p.unlink()
                removed += 1
        except OSError:
            pass
    return removed
