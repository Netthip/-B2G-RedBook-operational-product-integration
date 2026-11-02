# -*- coding: utf-8 -*-
"""PDF ต้นฉบับของฉบับ A/B ที่ใช้เป็น "ภาพหลักฐาน" ในหน้าเทียบ (#24 · PDF-first visual compare)

ตารางแยกแบบเพิ่มอย่างเดียว — ไม่แก้ตาราง ``files`` (สมุดงาน Excel ที่เครื่องยนต์ใช้ตรวจยังเป็น
ไฟล์หลักของฝั่งนั้นเหมือนเดิม) · หนึ่งฝั่งมี PDF ได้หนึ่งไฟล์ แนบใหม่ = แทนที่ (บันทึก Audit ทุกครั้ง)

ที่มาของไฟล์ (``origin``)

* ``upload``   — ผู้ใช้แนบเอง
* ``official`` — เครื่องมือ ``scripts/fetch_source_pdfs.py`` ดึงจากลิงก์ทางการในทะเบียนเล่ม
  🔴 แพ็กเกจ ``redbook`` ห้ามมีโค้ดเครือข่าย (local-first) — การดึงจึงอยู่นอกแพ็กเกจเสมอ
  แล้วส่งไฟล์เข้ามาทางฟังก์ชัน :func:`link` นี้ พร้อม URL และเวลาที่ดึง

🔴 PDF นี้เป็น **หลักฐานให้คนดู** ไม่ได้ป้อนเข้าเครื่องยนต์ · ไม่เปลี่ยนผลตรวจ
"""
from __future__ import annotations

from .. import privacy
from . import audit
from .db import connect
from .repository import now_iso

ORIGIN_UPLOAD = "upload"
ORIGIN_OFFICIAL = "official"
ORIGIN_LABELS = {ORIGIN_UPLOAD: "ผู้ใช้แนบเอง", ORIGIN_OFFICIAL: "ดึงจากลิงก์ทางการ"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS project_source_pdfs (
    project_id    TEXT NOT NULL,
    side          TEXT NOT NULL CHECK (side IN ('A','B')),
    stored_name   TEXT NOT NULL,
    original_name TEXT NOT NULL,
    sha256        TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    origin        TEXT NOT NULL CHECK (origin IN ('upload','official')),
    source_url    TEXT NOT NULL DEFAULT '',
    retrieved_at  TEXT NOT NULL DEFAULT '',
    linked_at     TEXT NOT NULL,
    PRIMARY KEY (project_id, side)
);
"""


def init_schema(db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA)
    finally:
        conn.close()


def link(project_id: str, side: str, stored, *, origin: str = ORIGIN_UPLOAD,
         source_url: str = "", retrieved_at: str = "", db_path=None) -> None:
    """ผูก PDF (``StoredFile`` จาก ``files.save_stream``) กับฝั่งของงานตรวจ"""
    if side not in ("A", "B"):
        raise ValueError("ฝั่งไม่ถูกต้อง")
    if origin not in ORIGIN_LABELS:
        raise ValueError("ที่มาของไฟล์ไม่ถูกต้อง")
    if stored.kind != "pdf":
        raise ValueError("ไฟล์นี้ไม่ใช่ PDF")
    # เส้นทางในเครื่องที่ติดมาใน URL (query/fragment · ดิบหรือเข้ารหัส %) ถูกกลบก่อนเก็บ — Audit แก้ย้อนหลังไม่ได้
    # (privacy 0.2.2 · Bo REVIEW 6358440451) · URL ทางการผ่านได้ตามเดิม
    source_url = privacy.redact_text(source_url or "")
    init_schema(db_path)
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO project_source_pdfs (project_id, side, stored_name, "
            "original_name, sha256, size_bytes, origin, source_url, retrieved_at, linked_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (project_id, side, stored.stored_name, stored.original_name[:300], stored.sha256,
             int(stored.size_bytes), origin, (source_url or "")[:1000],
             retrieved_at or "", now_iso()))
    finally:
        conn.close()
    audit.record("project_source_pdf_linked", "project", project_id,
                 # Bo 8 ต.ค.: เก็บ URL และเวลาที่ดึงจริงในทุกรายการ Audit — แนบใหม่แทนไฟล์เดิม
                 # แล้วประวัติที่มาของไฟล์เดิมยังอยู่ (ตาราง project_source_pdfs เก็บแค่ล่าสุด)
                 {"side": side, "origin": origin, "sha256": stored.sha256,
                  "size_bytes": int(stored.size_bytes), "source_url": (source_url or "")[:1000],
                  "retrieved_at": retrieved_at or ""}, db_path=db_path)


def for_project(project_id: str, db_path=None) -> dict:
    """``{"A": row, "B": row}`` — ไม่มี = ดิกต์ว่าง"""
    init_schema(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM project_source_pdfs WHERE project_id = ?",
                            (project_id,)).fetchall()
        return {r["side"]: dict(r) for r in rows}
    finally:
        conn.close()


__all__ = ["ORIGIN_UPLOAD", "ORIGIN_OFFICIAL", "ORIGIN_LABELS", "init_schema", "link",
           "for_project"]
