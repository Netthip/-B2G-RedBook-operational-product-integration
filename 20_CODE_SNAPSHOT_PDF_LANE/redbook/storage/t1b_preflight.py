# -*- coding: utf-8 -*-
"""ที่เก็บ "การรับทราบรายการที่ระบบอ่านไม่ครบ" ก่อนส่งออก

เหตุผล (คำสั่งกิ๊ฟ 23 ก.ย. 2569):
    รายการชนิด ``UNMAPPED`` แปลว่า **เครื่องยนต์อ่านแถวนั้นไม่ครบ** ไม่ใช่
    "ตรวจแล้วไม่พบความต่าง" · ถ้าปล่อยให้ส่งออกได้เงียบ ๆ ผู้รับไฟล์จะเข้าใจว่า
    ชุดที่ส่งไปครอบคลุมทั้งแฟ้ม ซึ่งไม่จริง

🔴 การรับทราบ **ผูกกับชุดรายการที่รับทราบ** ไม่ใช่ผูกกับรอบเฉย ๆ
``scope_hash`` คือแฮชของรหัสรายการ ``UNMAPPED`` ทั้งชุด ณ เวลาที่กดรับทราบ
ถ้าชุดนั้นเปลี่ยน (รันใหม่ · เพิ่ม/ลดรายการ) แฮชจะไม่ตรง ⇒ การรับทราบเดิม
**ใช้ไม่ได้อีก** ต้องอ่านและรับทราบใหม่ — กันการรับทราบครั้งเดียวแล้วใช้ตลอดไป

🔴 ตารางนี้ **ไม่เก็บเนื้อหาเอกสาร** เก็บแต่รหัสรายการ จำนวน และผู้รับทราบ
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..core.hashing import sha256_text
from .db import connect

PREFLIGHT_STORAGE_VERSION = "t1b-preflight-storage-0.1.0"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS t1b_unmapped_ack (
    run_id           TEXT NOT NULL,
    scope_hash       TEXT NOT NULL,
    unmapped_count   INTEGER NOT NULL,
    acknowledged_by  TEXT NOT NULL,
    note             TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL,
    PRIMARY KEY (run_id, scope_hash)
);
"""


def init_preflight_schema(db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA)
    finally:
        conn.close()


def scope_hash(finding_ids) -> str:
    """แฮชของชุดรายการที่ต้องรับทราบ — เรียงก่อนเสมอเพื่อให้ค่าคงที่

    ชุดว่างมีแฮชของตัวเองเช่นกัน ผู้เรียกจึงไม่ต้องแยกกรณี "ไม่มีรายการ"
    ด้วยเงื่อนไขพิเศษ
    """
    return sha256_text("\n".join(sorted(str(x) for x in finding_ids)))


def acknowledge(run_id: str, ids, *, who: str = "", note: str = "",
                db_path=None) -> str:
    """บันทึกการรับทราบชุดรายการที่ระบุ — คืน ``scope_hash`` ที่บันทึกไว้"""
    ids = list(ids)
    digest = scope_hash(ids)
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO t1b_unmapped_ack "
            "(run_id, scope_hash, unmapped_count, acknowledged_by, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, digest, len(ids), (who or "").strip()[:120] or "ไม่ระบุชื่อผู้ตรวจ",
             (note or "").strip()[:500],
             datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")))
    finally:
        conn.close()
    return digest


def get_ack(run_id: str, digest: str, db_path=None) -> dict | None:
    """คืนแถวการรับทราบที่ตรงกับชุดปัจจุบันเท่านั้น — ไม่ตรง = ยังไม่รับทราบ"""
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT run_id, scope_hash, unmapped_count, acknowledged_by, note, "
            "created_at FROM t1b_unmapped_ack WHERE run_id = ? AND scope_hash = ?",
            (run_id, digest)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_for_run(run_id: str, db_path=None) -> list[dict]:
    """ประวัติการรับทราบทั้งหมดของรอบนี้ — ใช้ในหน้า Audit"""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT run_id, scope_hash, unmapped_count, acknowledged_by, note, "
            "created_at FROM t1b_unmapped_ack WHERE run_id = ? "
            "ORDER BY created_at DESC", (run_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


__all__ = ["PREFLIGHT_STORAGE_VERSION", "init_preflight_schema", "scope_hash",
           "acknowledge", "get_ack", "list_for_run"]
