# -*- coding: utf-8 -*-
"""ค่าตั้งระบบ — รวมไว้ที่เดียว ย้ายโฟลเดอร์ข้อมูลได้โดยแก้ตัวแปรเดียว

ตำแหน่งเก็บข้อมูลรันจริง (uploads / ฐานข้อมูล / ล็อก) ตั้งใจให้อยู่ "นอก OneDrive"
เพราะไฟล์ที่อัปโหลดเป็นเอกสารราชการจริง การวางไว้ในโฟลเดอร์ที่ sync ขึ้นคลาวด์
เท่ากับส่งข้อมูลออกนอกเครื่อง ซึ่งขัดกับข้อกำหนด local-first
ผู้ใช้เปลี่ยนได้ด้วย environment variable REDBOOK_DATA_DIR
"""
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent

# --- ตำแหน่งข้อมูล runtime ของแอป ------------------------------------------
# (uploads / ฐานข้อมูล / ล็อก / exports) — ของระบบเอง ไม่ใช่คลังข้อมูลวิจัย
DATA_DIR = Path(os.environ.get("REDBOOK_DATA_DIR", PROJECT_ROOT / ".data")).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
TEMP_DIR = DATA_DIR / "tmp"
LOG_DIR = DATA_DIR / "logs"
EXPORT_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "redbook.sqlite3"

# --- คลังข้อมูลวิจัยกลาง (canonical data root) ------------------------------
# ตั้งค่าด้วย environment variable REDBOOK_DATA_ROOT เท่านั้น
# ห้าม hard-code absolute path ลง business logic — ทุกโมดูลต้องอ่านจากที่นี่
# โครงสร้างมาตรฐานภายใต้ root นี้กำหนดโดย repo เล่ม (RES: CANONICAL_DATA_DIRECTORY.md)
DATA_ROOT_ENV = "REDBOOK_DATA_ROOT"
_data_root_raw = os.environ.get(DATA_ROOT_ENV, "")
DATA_ROOT = Path(_data_root_raw).resolve() if _data_root_raw else None

# โฟลเดอร์ย่อยมาตรฐานของคลังกลาง — แยกตามชนิดเอกสาร ห้ามปนกัน
DATA_ROOT_SUBDIRS = {
    "flat_data_table": "sources/public/flat_data_table",   # OFFICIAL_FLAT_DATA_TABLE
    "ao_workbook": "sources/public/ao_workbook",           # OFFICIAL_AO_WORKBOOK
    "ministry_pdf": "sources/public/ministry_pdf",         # OFFICIAL_MINISTRY_PDF
    "inventory": "inventory",
    "experiments_development": "experiments/development",
    "experiments_evaluation": "experiments/evaluation",
    "experiments_mutation": "experiments/mutation",
    "experiments_demonstration": "experiments/demonstration",
    "gold_standard": "gold_standard",
    "reports": "reports",
    "runtime": "runtime",
    "temporary": "temporary",
}


def data_root_path(key: str) -> Path:
    """คืน path ของโฟลเดอร์ย่อยในคลังข้อมูลกลาง

    ยกข้อผิดพลาดถ้ายังไม่ตั้ง REDBOOK_DATA_ROOT — เพื่อไม่ให้โค้ดเดาตำแหน่งเอง
    """
    if DATA_ROOT is None:
        raise RuntimeError(
            f"ยังไม่ได้ตั้ง environment variable {DATA_ROOT_ENV} "
            "— ระบบไม่เดาตำแหน่งคลังข้อมูลวิจัยเอง"
        )
    if key not in DATA_ROOT_SUBDIRS:
        raise KeyError(f"ไม่รู้จักโฟลเดอร์ย่อย '{key}' ของคลังข้อมูลกลาง")
    return DATA_ROOT / DATA_ROOT_SUBDIRS[key]

# --- ข้อจำกัดไฟล์อัปโหลด ---------------------------------------------------
MAX_UPLOAD_BYTES = int(os.environ.get("REDBOOK_MAX_UPLOAD_MB", "80")) * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024

# ชนิดไฟล์ที่รับ: ตรวจจาก magic bytes จริง ไม่เชื่อนามสกุลและไม่เชื่อ content-type
ALLOWED_KINDS = {
    "xlsx": {"ext": ".xlsx", "label": "Excel (.xlsx/.xlsm)"},
    "pdf": {"ext": ".pdf", "label": "PDF (.pdf)"},
}

# --- เครือข่าย -------------------------------------------------------------
# ผูกกับ loopback เท่านั้น เครื่องอื่นในวงแลนเรียกไม่ได้
BIND_HOST = os.environ.get("REDBOOK_HOST", "127.0.0.1")
BIND_PORT = int(os.environ.get("REDBOOK_PORT", "8600"))

# โหมดสาธิต (#24) — ตั้งโดย ``scripts/demo_launch.py`` เท่านั้น
# เปิดปุ่ม "ใส่คู่ไฟล์สาธิตสังเคราะห์" ในหน้างานตรวจ · งานจริงไม่มีปุ่มนี้
DEMO_MODE = os.environ.get("REDBOOK_DEMO") == "1"
# 🔴 หัว Host ที่ยอมรับ (กัน DNS rebinding — Security Gate #23 · F-01)
# เว็บแอปบน loopback ถูกโจมตีได้ด้วยโดเมนของผู้โจมตีที่ resolve มาที่ 127.0.0.1 แล้วให้
# เบราว์เซอร์ของผู้ใช้อ่าน response ข้ามไซต์ — การตรวจหัว Host กับรายการอนุญาตคือด่านกัน
# ตั้งเพิ่มได้ด้วย REDBOOK_ALLOWED_HOSTS (คั่นด้วย ,) · เทียบโดยไม่สนพอร์ต
ALLOWED_HOSTS = frozenset(
    h.strip().lower() for h in
    (os.environ.get("REDBOOK_ALLOWED_HOSTS", "") + ",127.0.0.1,localhost,[::1]," + BIND_HOST).split(",")
    if h.strip())

# --- โหมดพัฒนา -------------------------------------------------------------
# ค่าเริ่มต้นเป็น False เสมอ: หน้าเว็บผู้ใช้จะไม่เห็น stack trace หรือ path ภายใน
DEBUG_DETAIL = os.environ.get("REDBOOK_DEBUG_DETAIL", "0") == "1"


def ensure_dirs() -> None:
    """สร้างโฟลเดอร์ข้อมูลที่จำเป็น (เรียกตอนแอปเริ่มทำงานและตอนรันเทสต์)"""
    for d in (DATA_DIR, UPLOAD_DIR, TEMP_DIR, LOG_DIR, EXPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)
