# -*- coding: utf-8 -*-
"""Audit Trail แบบเพิ่มอย่างเดียวและมีสายโซ่แฮช

ทำไมต้องมีสายโซ่แฮช: เอกสารงบประมาณเป็นหลักฐานที่ต้องอธิบายย้อนหลังได้
ถ้ามีใครแก้บันทึกย้อนหลัง แฮชของรายการถัดไปจะไม่ตรงทันที และ verify_chain()
จะชี้ได้ว่าผิดที่ลำดับใด (ตรวจได้โดยไม่ต้องเชื่อระบบ)
"""
from datetime import datetime, timezone

from .db import connect, jdump
from ..core.hashing import sha256_text

GENESIS = "0" * 64


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _entry_hash(prev_hash, ts, actor, action, object_type, object_id, detail_json) -> str:
    payload = "|".join([prev_hash, ts, actor, action, object_type, object_id, detail_json])
    return sha256_text(payload)


def record_in(conn, action: str, object_type: str, object_id: str,
              detail: dict = None, actor: str = "local-user") -> dict:
    """บันทึกลง Audit Trail **บน connection ที่เปิดอยู่แล้ว** — ไม่ BEGIN/COMMIT เอง

    🔴 มีไว้ให้ผู้เรียกที่ต้องเขียน audit กับข้อมูลอื่น **ในธุรกรรมเดียวกัน**
    (คำตัดสินของมนุษย์ · การลบตามนโยบายเก็บรักษา) — ถ้า audit เขียนไม่สำเร็จ
    ข้อมูลนั้นต้องไม่เกิด และกลับกัน · ผู้เรียกเป็นผู้ COMMIT/ROLLBACK
    """
    detail_json = jdump(detail or {})
    ts = _now()
    row = conn.execute(
        "SELECT entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
    prev_hash = row["entry_hash"] if row else GENESIS
    entry_hash = _entry_hash(prev_hash, ts, actor, action, object_type,
                             object_id, detail_json)
    cur = conn.execute(
        "INSERT INTO audit_log (ts, actor, action, object_type, object_id, "
        "detail_json, prev_hash, entry_hash) VALUES (?,?,?,?,?,?,?,?)",
        (ts, actor, action, object_type, object_id, detail_json,
         prev_hash, entry_hash))
    return {"seq": cur.lastrowid, "ts": ts, "actor": actor, "action": action,
            "object_type": object_type, "object_id": object_id,
            "detail": detail or {}, "prev_hash": prev_hash,
            "entry_hash": entry_hash}


def record(action: str, object_type: str, object_id: str,
           detail: dict = None, actor: str = "local-user", db_path=None) -> dict:
    """บันทึกเหตุการณ์หนึ่งรายการลง Audit Trail แล้วคืนรายการที่บันทึก"""
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        out = record_in(conn, action, object_type, object_id, detail, actor)
        conn.execute("COMMIT")
        return out
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def verify_chain(db_path=None) -> dict:
    """ตรวจความต่อเนื่องของสายโซ่ — ใช้เป็นหลักฐานว่าบันทึกไม่ถูกแก้ย้อนหลัง"""
    conn = connect(db_path)
    try:
        prev = GENESIS
        count = 0
        for r in conn.execute("SELECT * FROM audit_log ORDER BY seq ASC"):
            expect = _entry_hash(prev, r["ts"], r["actor"], r["action"],
                                 r["object_type"], r["object_id"], r["detail_json"])
            if r["prev_hash"] != prev or r["entry_hash"] != expect:
                return {"ok": False, "checked": count, "broken_at_seq": r["seq"]}
            prev = r["entry_hash"]
            count += 1
        return {"ok": True, "checked": count, "broken_at_seq": None, "head": prev}
    finally:
        conn.close()


def entries(limit: int = 200, offset: int = 0, object_id: str = None, db_path=None):
    conn = connect(db_path)
    try:
        if object_id:
            sql = ("SELECT * FROM audit_log WHERE object_id = ? "
                   "ORDER BY seq DESC LIMIT ? OFFSET ?")
            rows = conn.execute(sql, (object_id, limit, offset)).fetchall()
        else:
            sql = "SELECT * FROM audit_log ORDER BY seq DESC LIMIT ? OFFSET ?"
            rows = conn.execute(sql, (limit, offset)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def security_event(event: str, severity: str = "info", detail: dict = None,
                   client: str = None, db_path=None) -> None:
    """บันทึกเหตุการณ์ด้านความปลอดภัย (ไฟล์ถูกปฏิเสธ ขนาดเกิน ชนิดไม่ตรง ฯลฯ)"""
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO security_events (ts, event, severity, detail_json, client) "
            "VALUES (?,?,?,?,?)",
            (_now(), event, severity, jdump(detail or {}), client))
    finally:
        conn.close()


def security_events(limit: int = 200, db_path=None):
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM security_events ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
