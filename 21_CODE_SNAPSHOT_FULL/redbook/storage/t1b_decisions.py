# -*- coding: utf-8 -*-
"""ที่เก็บคำตัดสินของมนุษย์ — **เพิ่มอย่างเดียว** และผูกกับโซ่แฮชของ Audit Trail

ตาราง ``t1b_decisions`` มี trigger กัน ``UPDATE`` และ ``DELETE`` ไว้ที่ระดับ
ฐานข้อมูล (ดู :mod:`redbook.storage.t1b_repo`) ⇒ โค้ดที่เขียน SQL เองก็ข้ามไม่ได้

ทางลบทางเดียวที่ถูกกฎหมายคือการลบทั้งงานตรวจตาม
`PROVISIONAL_LOCAL_RETENTION POLICY` ซึ่งต้องเปิดช่องด้วย
:func:`retention_unlock` อย่างจงใจก่อน

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from . import audit
from .db import connect

_COLUMNS = (
    "id", "run_id", "finding_id", "identity_basis", "not_rebindable",
    "status_from", "status_to", "engine_finding_type", "engine_baseline_value",
    "engine_current_value", "engine_difference", "subject_category",
    "category_confidence", "category_evidence_json", "corrected_field",
    "corrected_value", "note", "decided_at", "decided_by", "key_version",
    "matching_version", "compare_version", "service_version",
    "file_a_sha256", "file_b_sha256", "audit_seq", "audit_entry_hash",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _view(row):
    from ..services.decisions import DecisionView

    return DecisionView(
        seq=int(row["seq"]), id=row["id"], run_id=row["run_id"],
        finding_id=row["finding_id"], identity_basis=row["identity_basis"],
        not_rebindable=bool(row["not_rebindable"]),
        status_from=row["status_from"], status_to=row["status_to"],
        engine_finding_type=row["engine_finding_type"],
        engine_baseline_value=row["engine_baseline_value"],
        engine_current_value=row["engine_current_value"],
        engine_difference=row["engine_difference"],
        subject_category=row["subject_category"],
        category_confidence=row["category_confidence"],
        category_evidence=tuple(json.loads(row["category_evidence_json"] or "[]")),
        corrected_field=row["corrected_field"],
        corrected_value=row["corrected_value"], note=row["note"],
        decided_at=row["decided_at"], decided_by=row["decided_by"],
        audit_seq=row["audit_seq"], audit_entry_hash=row["audit_entry_hash"],
    )


def _file_hashes(run_id: str, db_path=None) -> tuple[str, str]:
    """แฮชของไฟล์สองฝั่งที่รอบนี้ใช้ — ผูกคำตัดสินกลับไปหา *ไฟล์ตัวจริง*

    ค้นจาก ``t1b_runs.project_id`` ไปยังตาราง ``files`` (อ่านอย่างเดียว) ·
    ถ้ารอบนั้นไม่ได้ผูกกับงานตรวจใด จะคืนค่าว่าง — **ไม่เดา ไม่ปล่อยผ่านเงียบ**
    ผู้อ่านรายงานจะเห็นช่องว่างและรู้ว่าตามกลับไม่ได้
    """
    conn = connect(db_path)
    try:
        run = conn.execute("SELECT project_id FROM t1b_runs WHERE id = ?",
                           (run_id,)).fetchone()
        if run is None or not run["project_id"]:
            return "", ""
        rows = conn.execute(
            "SELECT side, sha256 FROM files WHERE project_id = ?",
            (run["project_id"],)).fetchall()
    finally:
        conn.close()
    by_side = {r["side"]: r["sha256"] for r in rows}
    return by_side.get("A", ""), by_side.get("B", "")


def latest_seq_for(run_id: str, finding_id: str, db_path=None) -> int:
    """``seq`` ของคำตัดสินล่าสุดของ finding — ``0`` เมื่อยังไม่เคยตัดสิน

    ใช้เป็นค่า ``expected_latest_seq`` ในการกันคำตัดสินค้าง (stale) — ผู้เรียก
    อ่านค่านี้ตอนแสดงหน้าจอ แล้วส่งกลับมาตอนบันทึก
    """
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT MAX(seq) AS top FROM t1b_decisions "
            "WHERE run_id = ? AND finding_id = ?", (run_id, finding_id)).fetchone()
        return int(row["top"] or 0)
    finally:
        conn.close()


def append(data: dict, *, expected_latest_seq: int, db_path=None):
    """เพิ่มคำตัดสินหนึ่งแถว แล้วคืน :class:`DecisionView`

    🔴 **audit และคำตัดสินอยู่ในธุรกรรมเดียวกัน** (กิ๊ฟ ข้อ B.4) — ถ้า audit
    เขียนไม่สำเร็จ คำตัดสินต้องไม่เกิด และถ้าคำตัดสินเขียนไม่สำเร็จ audit
    ต้องไม่เหลือค้าง · ใช้ :func:`audit.record_in` บน connection เดียวกัน

    🔴 **กันคำตัดสินค้าง** (B.1) — ตรวจ ``expected_latest_seq`` **ภายในธุรกรรม
    เดียวกับการเขียน** ไม่ใช่ก่อนหน้า มิฉะนั้นสองแท็บที่กดพร้อมกันจะผ่านทั้งคู่
    """
    from ..services.decisions import StaleDecisionError

    row = dict(data)
    row["category_evidence_json"] = json.dumps(
        list(data.get("category_evidence") or []), ensure_ascii=False)
    row.pop("category_evidence", None)
    row.setdefault("decided_at", _now())
    sha_a, sha_b = _file_hashes(data["run_id"], db_path)
    row.setdefault("file_a_sha256", sha_a)
    row.setdefault("file_b_sha256", sha_b)

    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")      # 🔴 ล็อกเขียนตั้งแต่ต้น กันสองแท็บชนกัน
        top = conn.execute(
            "SELECT MAX(seq) AS top FROM t1b_decisions "
            "WHERE run_id = ? AND finding_id = ?",
            (row["run_id"], row["finding_id"])).fetchone()["top"] or 0
        if int(top) != int(expected_latest_seq):
            raise StaleDecisionError(expected=int(expected_latest_seq),
                                     actual=int(top))

        entry = audit.record_in(
            conn, "t1b_decision_recorded", "t1b_finding", row["finding_id"],
            {
                "run_id": row["run_id"],
                "status_from": row["status_from"],
                "status_to": row["status_to"],
                "engine_finding_type": row["engine_finding_type"],
                "subject_category": row["subject_category"],
                "category_confidence": row["category_confidence"],
                "identity_basis": row["identity_basis"],
                "not_rebindable": row["not_rebindable"],
                "value_edited_by_human": int(bool(row.get("corrected_value"))),
                "note_present": int(bool(row.get("note"))),
                "key_version": row.get("key_version", ""),
                "compare_version": row.get("compare_version", ""),
                "supersedes_seq": int(top),
            },
            actor=row.get("decided_by", "local-user"))
        row["audit_seq"] = entry["seq"]
        row["audit_entry_hash"] = entry["entry_hash"]
        for col in _COLUMNS:
            row.setdefault(col, "")
        placeholders = ", ".join("?" for _ in _COLUMNS)
        conn.execute(
            f"INSERT INTO t1b_decisions ({', '.join(_COLUMNS)}) "
            f"VALUES ({placeholders})",
            tuple(row[c] for c in _COLUMNS))
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:                      # noqa: BLE001
            pass
        raise
    finally:
        conn.close()
    return get(row["id"], db_path=db_path)


def get(decision_id: str, db_path=None):
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM t1b_decisions WHERE id = ?",
                           (decision_id,)).fetchone()
        return _view(row) if row else None
    finally:
        conn.close()


def list_for_finding(run_id: str, finding_id: str, db_path=None) -> list:
    """ประวัติทั้งหมดของ finding หนึ่งใบ **เรียงตามเวลาที่เกิดจริง**"""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM t1b_decisions WHERE run_id = ? AND finding_id = ? "
            "ORDER BY seq", (run_id, finding_id)).fetchall()
        return [_view(r) for r in rows]
    finally:
        conn.close()


def list_for_run(run_id: str, db_path=None) -> list:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM t1b_decisions WHERE run_id = ? ORDER BY seq",
            (run_id,)).fetchall()
        return [_view(r) for r in rows]
    finally:
        conn.close()


def latest_by_finding(run_id: str, db_path=None) -> dict:
    """สถานะปัจจุบันของทุก finding ในรอบ — ``{finding_id: DecisionView}``

    ใช้แถวที่ ``seq`` มากที่สุดของแต่ละ ``finding_id`` · finding ที่ไม่มีแถวเลย
    จะไม่ปรากฏใน dict นี้ ⇒ ผู้เรียกต้องตีความว่าเป็น ``PENDING``
    """
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.* FROM t1b_decisions d "
            "JOIN (SELECT finding_id, MAX(seq) AS top FROM t1b_decisions "
            "      WHERE run_id = ? GROUP BY finding_id) m "
            "  ON d.finding_id = m.finding_id AND d.seq = m.top "
            "WHERE d.run_id = ?", (run_id, run_id)).fetchall()
        return {r["finding_id"]: _view(r) for r in rows}
    finally:
        conn.close()


def count_by_status(run_id: str, db_path=None) -> dict:
    """นับ finding ตามสถานะปัจจุบัน — ไม่นับ ``PENDING`` (ไม่มีแถว)"""
    out: dict[str, int] = {}
    for d in latest_by_finding(run_id, db_path).values():
        out[d.status_to] = out.get(d.status_to, 0) + 1
    return out


def verify_audit_links(run_id: str, db_path=None) -> dict:
    """ตรวจว่าทุกคำตัดสินชี้กลับไปยังรายการ audit ที่ **มีอยู่จริง · แฮชตรง ·
    เป็นของ finding และ run เดียวกัน**

    🔴 (กิ๊ฟ B.4) ตรวจสามชั้น — ชั้นเดียวไม่พอ

    1. แถว audit ต้องมีอยู่ (``audit_seq`` ไม่ลอย)
    2. ``entry_hash`` ต้องตรงกับที่คำตัดสินจดไว้
    3. ``object_id`` ของ audit ต้องเป็น finding ใบเดียวกัน และ ``run_id``
       ในรายละเอียดต้องเป็นรอบเดียวกัน — กันการ **ปลอมเป็น seq ของรอบอื่น**
    """
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.id, d.finding_id, d.audit_seq, d.audit_entry_hash, "
            "       a.entry_hash, a.object_id, a.action, a.detail_json "
            "FROM t1b_decisions d "
            "LEFT JOIN audit_log a ON a.seq = d.audit_seq "
            "WHERE d.run_id = ?", (run_id,)).fetchall()
    finally:
        conn.close()

    broken = []
    for r in rows:
        if r["entry_hash"] is None:
            broken.append((r["id"], "audit_missing"))
        elif r["entry_hash"] != r["audit_entry_hash"]:
            broken.append((r["id"], "hash_mismatch"))
        elif (r["object_id"] != r["finding_id"]
              or r["action"] != "t1b_decision_recorded"):
            broken.append((r["id"], "audit_belongs_to_other_object"))
        else:
            try:
                detail = json.loads(r["detail_json"] or "{}")
            except ValueError:
                detail = {}
            if detail.get("run_id") != run_id:
                broken.append((r["id"], "audit_belongs_to_other_run"))
    return {"total": len(rows), "broken": [b[0] for b in broken],
            "reasons": dict(broken), "ok": not broken}


#: อายุของสิทธิ์ลบ — สั้นพอให้ใช้ได้เฉพาะภายในธุรกรรมที่เปิดมัน
RETENTION_UNLOCK_SECONDS = 60


def open_retention_unlock(conn, run_id: str, reason: str) -> str:
    """เปิดสิทธิ์ลบ **หนึ่งรอบ** บน connection ที่อยู่ในธุรกรรมแล้ว · คืนโทเคน

    🔴 (กิ๊ฟ B.3) สิทธิ์นี้ผูกกับ ``run_id`` ใช้ครั้งเดียว และหมดอายุใน
    :data:`RETENTION_UNLOCK_SECONDS` · ต้องเรียกภายในธุรกรรมเดียวกับ ``DELETE``
    แล้ว :func:`consume_retention_unlock` ก่อน COMMIT — ถ้าธุรกรรมย้อนกลับ
    โทเคนก็หายไปพร้อมกัน ไม่เหลือสิทธิ์ค้าง
    """
    token = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO t1b_retention_unlock "
        "(token, run_id, opened_at, expires_at, consumed_at, reason) VALUES "
        "(?, ?, strftime('%Y-%m-%d %H:%M:%S','now'), "
        " strftime('%Y-%m-%d %H:%M:%S','now', ?), NULL, ?)",
        (token, run_id, f"+{RETENTION_UNLOCK_SECONDS} seconds", reason[:200]))
    return token


def consume_retention_unlock(conn, token: str) -> None:
    """ปิดสิทธิ์ทันทีหลังใช้ — ลบแถวทิ้ง ไม่ใช่แค่ทำเครื่องหมาย

    ลบทิ้งดีกว่าทำเครื่องหมาย เพราะตารางนี้ต้อง **ว่างเสมอ** นอกธุรกรรม
    การมีแถวค้างแม้จะ consumed แล้ว ก็เป็นสัญญาณว่ามีบางอย่างผิดปกติ
    """
    conn.execute("DELETE FROM t1b_retention_unlock WHERE token = ?", (token,))


def stale_unlocks(db_path=None) -> int:
    """จำนวนสิทธิ์ที่ค้างอยู่ — **ต้องเป็น 0 เสมอ** นอกธุรกรรม · ใช้ในเทสต์และรายงาน"""
    conn = connect(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) n FROM t1b_retention_unlock").fetchone()["n"]
    finally:
        conn.close()


__all__ = [
    "append", "get", "latest_seq_for", "list_for_finding", "list_for_run",
    "latest_by_finding", "count_by_status", "verify_audit_links",
    "open_retention_unlock", "consume_retention_unlock", "stale_unlocks",
    "RETENTION_UNLOCK_SECONDS",
]
