# -*- coding: utf-8 -*-
"""ผูกงานตรวจกับเล่มงบประมาณที่ผู้ใช้เลือกจากคลังเล่ม (#24)

ตารางแยกแบบ **เพิ่มอย่างเดียว** — ไม่แก้ตาราง ``projects`` เดิม งานตรวจที่ตั้งแบบเดิม
(ไม่ได้เลือกเล่ม) จึงทำงานเหมือนเดิมทุกประการ

เก็บแค่รหัสเล่ม + ลิงก์ทางการ ณ ตอนเลือก (snapshot) เพื่อให้ตรวจย้อนได้ว่า
งานนี้อ้างอิงเล่มไหน แม้ทะเบียนเล่มจะถูกสร้างใหม่ภายหลัง · ไม่เก็บสำเนา PDF
"""
from __future__ import annotations

from . import audit
from .db import connect
from .repository import now_iso

_SCHEMA = """
CREATE TABLE IF NOT EXISTS project_books (
    project_id   TEXT NOT NULL,
    side         TEXT NOT NULL CHECK (side IN ('A','B')),
    book_id      TEXT NOT NULL,
    fiscal_year  INTEGER,
    title        TEXT NOT NULL,
    pdf_url      TEXT NOT NULL,
    source_page  TEXT NOT NULL,
    linked_at    TEXT NOT NULL,
    PRIMARY KEY (project_id, side)
);
"""


def init_schema(db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA)
    finally:
        conn.close()


def link(project_id: str, side: str, book, db_path=None) -> None:
    if side not in ("A", "B"):
        raise ValueError("ฝั่งไม่ถูกต้อง")
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO project_books "
            "(project_id, side, book_id, fiscal_year, title, pdf_url, source_page, linked_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (project_id, side, book.id, book.fiscal_year, book.title[:500],
             book.pdf_url, book.source_page, now_iso()))
    finally:
        conn.close()
    audit.record("project_book_linked", "project", project_id,
                 {"side": side, "book_id": book.id, "fiscal_year": book.fiscal_year},
                 db_path=db_path)


def for_project(project_id: str, db_path=None) -> dict:
    """คืน ``{"A": row, "B": row}`` — งานที่ไม่ได้เลือกเล่มคืนดิกต์ว่าง"""
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM project_books WHERE project_id = ?",
                            (project_id,)).fetchall()
        return {r["side"]: dict(r) for r in rows}
    finally:
        conn.close()


def delete_for_project(project_id: str, db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.execute("DELETE FROM project_books WHERE project_id = ?", (project_id,))
    finally:
        conn.close()
