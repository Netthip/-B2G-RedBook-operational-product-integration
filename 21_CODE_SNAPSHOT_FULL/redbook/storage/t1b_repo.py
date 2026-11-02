# -*- coding: utf-8 -*-
"""ที่เก็บผลของ T1B — **schema แยกจาก T1A โดยสิ้นเชิง**

🔴 คำสั่ง Bo · `BO REVIEW COMPLETE` (Issue #1) · LANE B ข้อ 4 —
*"T1B findings must not be coerced into the T1A finding schema/table"*
และ *"separate T1B persistence schema and repository tests"*

**ทำไมต้องแยกตาราง ไม่ใช่เพิ่มคอลัมน์ในตาราง ``findings`` เดิม**

===========================  ==========================================
สิ่งที่ T1B มีแต่ T1A ไม่มี      สิ่งที่ T1A มีแต่ T1B ไม่มี
===========================  ==========================================
``comparison_axis``           ``severity``
``budget_category``           ``rule_id`` / ``rule_version``
ธงระดับ finding (``flags``)    ``machine_status``
ปีบริบทของตารางหมวดสองฝั่ง       ``confidence`` / ``confidence_basis``
ผลด่านตัวตนหน่วยงานระดับรอบ      ``presentation_only``
===========================  ==========================================

ถ้ายัดลงตารางเดียวกัน คอลัมน์ครึ่งหนึ่งจะว่างเสมอในทุกแถว และ **ที่อันตรายกว่า**
คือรายงานที่นับจากตารางนั้นจะปนผลของสองระเบียบวิธีเข้าด้วยกัน ทั้งที่ T1A
เป็นหลักฐานวิจัยที่ freeze แล้ว ส่วน T1B เป็นผลิตภัณฑ์หลัง freeze

**สิ่งที่ยังไม่ทำตามคำสั่ง** — ยังไม่มีคอลัมน์คำตัดสินสุดท้ายของมนุษย์
และไม่มีคอลัมน์ ``confidence`` เพราะ Bo สั่งให้รอทั้งสองเรื่อง
สถานะ ``READY / REVIEW REQUIRED`` **ไม่ถูกเก็บ** เพราะเป็นค่าที่คำนวณได้

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from .db import connect, session

#: 2 = เพิ่มตาราง ``t1b_decisions`` (คำตัดสินของมนุษย์ · append-only)
#: 3 = สิทธิ์ลบผูกกับ run · ใช้ครั้งเดียว · หมดอายุ (B.3)
T1B_SCHEMA_VERSION = 3

#: 🔴 ทุกตารางขึ้นต้นด้วย ``t1b_`` เพื่อให้เห็นด้วยตาเปล่าว่าเป็นคนละสายงาน
_SCHEMA = """
CREATE TABLE IF NOT EXISTS t1b_runs (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    key_version         TEXT NOT NULL,
    matching_version    TEXT NOT NULL,
    compare_version     TEXT NOT NULL,
    service_version     TEXT NOT NULL,
    identity_reason     TEXT NOT NULL,
    identity_verdict    TEXT NOT NULL,
    identity_blocked    INTEGER NOT NULL,
    automatic_pairs     INTEGER NOT NULL DEFAULT 0,
    total_findings      INTEGER NOT NULL DEFAULT 0,
    requiring_review    INTEGER NOT NULL DEFAULT 0,
    by_type_json        TEXT NOT NULL DEFAULT '{}',
    by_flag_json        TEXT NOT NULL DEFAULT '{}',
    note                TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS t1b_findings (
    id                    TEXT PRIMARY KEY,
    run_id                TEXT NOT NULL REFERENCES t1b_runs(id) ON DELETE CASCADE,
    finding_id            TEXT NOT NULL,
    -- 🔴 ที่มาของ finding_id: 'content' = คงที่ข้ามการรัน · 'position' = ไม่รับประกัน
    -- การผูกคำตัดสินของมนุษย์กลับอัตโนมัติในอนาคต ห้ามทำกับแถวที่เป็น 'position'
    identity_basis        TEXT NOT NULL DEFAULT 'content',
    side                  TEXT NOT NULL DEFAULT '',
    ordinal               INTEGER NOT NULL,
    finding_type          TEXT NOT NULL,
    requires_review       INTEGER NOT NULL DEFAULT 0,
    comparison_axis       TEXT NOT NULL DEFAULT '',
    fiscal_year           INTEGER,
    budget_category       TEXT,
    row_label             TEXT NOT NULL DEFAULT '',
    sheet_role            TEXT NOT NULL DEFAULT '',
    section_title         TEXT NOT NULL DEFAULT '',
    parent_plan           TEXT NOT NULL DEFAULT '',
    declared_unit         TEXT NOT NULL DEFAULT '',
    baseline_value        TEXT NOT NULL DEFAULT '',
    current_value         TEXT NOT NULL DEFAULT '',
    difference            TEXT NOT NULL DEFAULT '',
    baseline_table_year   INTEGER,
    current_table_year    INTEGER,
    baseline_loc_json     TEXT NOT NULL DEFAULT '{}',
    current_loc_json      TEXT NOT NULL DEFAULT '{}',
    flags_json            TEXT NOT NULL DEFAULT '[]',
    detail                TEXT NOT NULL DEFAULT '',
    UNIQUE (run_id, ordinal)
);
CREATE INDEX IF NOT EXISTS idx_t1b_findings_run ON t1b_findings(run_id);
CREATE INDEX IF NOT EXISTS idx_t1b_findings_fid ON t1b_findings(run_id, finding_id);
CREATE INDEX IF NOT EXISTS idx_t1b_findings_type ON t1b_findings(run_id, finding_type);
CREATE INDEX IF NOT EXISTS idx_t1b_findings_review
    ON t1b_findings(run_id, requires_review);

-- ══════════════════════════════════════════════════════════════════════════
--  คำตัดสินของมนุษย์ — **เพิ่มอย่างเดียว แก้ไม่ได้ ลบไม่ได้**
-- ══════════════════════════════════════════════════════════════════════════
--
-- 🔴 ไม่มีคอลัมน์ "สถานะปัจจุบัน" ที่ไหนเลย · สถานะปัจจุบันของ finding หนึ่งใบ
-- คือ ``status_to`` ของแถวที่ ``seq`` มากที่สุดของ ``(run_id, finding_id)`` นั้น
-- เก็บเป็นคอลัมน์เมื่อใด ประวัติกับสถานะจะขัดกันเองได้ทันทีที่เขียนพลาดครั้งเดียว
--
-- 🔴 ``engine_*`` คือค่าที่เครื่องยนต์เสนอ ณ เวลาที่ตัดสิน — **ตรึงไว้**
-- แม้ผู้ใช้จะแก้ค่า (``CONFIRMED_WITH_EDIT``) ค่าเดิมของเครื่องยนต์ต้องยังอ่านได้
-- มิฉะนั้นจะพิสูจน์ไม่ได้ว่ามนุษย์แก้อะไรไปจากที่ระบบเสนอ
CREATE TABLE IF NOT EXISTS t1b_decisions (
    seq                   INTEGER PRIMARY KEY AUTOINCREMENT,
    id                    TEXT NOT NULL UNIQUE,
    run_id                TEXT NOT NULL REFERENCES t1b_runs(id) ON DELETE CASCADE,
    finding_id            TEXT NOT NULL,
    -- 'content' = ผูกคำตัดสินข้ามรอบได้ · 'position' = ผูกไม่ได้
    identity_basis        TEXT NOT NULL,
    -- 1 = ห้ามผูกคำตัดสินนี้กลับอัตโนมัติในรอบใหม่ ต้องให้มนุษย์ยืนยันซ้ำ
    not_rebindable        INTEGER NOT NULL DEFAULT 0,
    status_from           TEXT NOT NULL,
    status_to             TEXT NOT NULL,
    -- ค่าที่เครื่องยนต์เสนอ ณ ขณะตัดสิน — ห้ามเขียนทับตลอดกาล
    engine_finding_type   TEXT NOT NULL DEFAULT '',
    engine_baseline_value TEXT NOT NULL DEFAULT '',
    engine_current_value  TEXT NOT NULL DEFAULT '',
    engine_difference     TEXT NOT NULL DEFAULT '',
    subject_category      TEXT NOT NULL DEFAULT '',
    category_confidence   TEXT NOT NULL DEFAULT '',
    category_evidence_json TEXT NOT NULL DEFAULT '[]',
    -- ค่าที่มนุษย์แก้ — ว่างเสมอ ยกเว้นสถานะ CONFIRMED_WITH_EDIT
    corrected_field       TEXT NOT NULL DEFAULT '',
    corrected_value       TEXT NOT NULL DEFAULT '',
    note                  TEXT NOT NULL DEFAULT '',
    decided_at            TEXT NOT NULL,
    decided_by            TEXT NOT NULL DEFAULT 'local-user',
    key_version           TEXT NOT NULL DEFAULT '',
    matching_version      TEXT NOT NULL DEFAULT '',
    compare_version       TEXT NOT NULL DEFAULT '',
    service_version       TEXT NOT NULL DEFAULT '',
    file_a_sha256         TEXT NOT NULL DEFAULT '',
    file_b_sha256         TEXT NOT NULL DEFAULT '',
    -- ผูกกลับเข้าโซ่แฮชของ audit_log — ตรวจย้อนหลังได้ว่าคำตัดสินนี้อยู่ในโซ่จริง
    audit_seq             INTEGER,
    audit_entry_hash      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_t1b_decisions_run ON t1b_decisions(run_id);
CREATE INDEX IF NOT EXISTS idx_t1b_decisions_latest
    ON t1b_decisions(run_id, finding_id, seq DESC);

-- 🔴 บังคับความเป็น append-only ที่ระดับฐานข้อมูล ไม่ใช่ที่ระดับวินัยของโค้ด
-- ถ้าบังคับแค่ในชั้นบริการ โค้ดใหม่ที่เขียน SQL เองจะข้ามได้เงียบ ๆ
CREATE TRIGGER IF NOT EXISTS t1b_decisions_no_update
BEFORE UPDATE ON t1b_decisions
BEGIN
    SELECT RAISE(ABORT, 't1b_decisions is append-only');
END;

-- 🔴 ทางลบทางเดียวที่ถูกกฎหมาย — การลบทั้งงานตรวจตาม
-- `PROVISIONAL_LOCAL_RETENTION POLICY` ซึ่งกิ๊ฟกำหนดว่าผู้ใช้ต้องลบได้เอง
--
-- ข้อกำหนดสองข้อนี้ชนกันตรง ๆ: "คำตัดสินลบไม่ได้" กับ "ผู้ใช้ต้องลบข้อมูลได้"
-- แก้โดยเปิดช่องแคบ ๆ ที่ **ต้องประกาศเจตนาก่อน** — ใส่โทเคนลงตารางนี้
-- ลบ แล้วเอาโทเคนออก ทั้งหมดในธุรกรรมเดียว · เส้นทางอื่นถูกปฏิเสธเสมอ
-- ทำให้ "ลบได้เมื่อใด" อ่านออกจาก schema ไม่ใช่จากความจำของคนเขียนโค้ด
-- 🔴 schema v3 (กิ๊ฟ 7 ก.ย. ข้อ B.3) — สิทธิ์ลบเป็นแบบ
--   ใช้ครั้งเดียว · ผูกกับ run ที่จะลบ · หมดอายุสั้น · ใช้ได้เฉพาะในธุรกรรม
--   ของ retention-delete · ถูก consume ทันทีหลังใช้ · route/decision service ใช้ไม่ได้
CREATE TABLE IF NOT EXISTS t1b_retention_unlock (
    token       TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL,
    opened_at   TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    consumed_at TEXT,
    reason      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS t1b_schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);
"""

#: trigger กันลบ — สร้างใหม่ทุกครั้งใน :func:`init_t1b_schema` (DROP ก่อน)
#: เพราะ ``CREATE TRIGGER IF NOT EXISTS`` จะไม่แทนที่นิยามเก่าของ v2
_NO_DELETE_TRIGGER = """
CREATE TRIGGER t1b_decisions_no_delete
BEFORE DELETE ON t1b_decisions
WHEN NOT EXISTS (
    SELECT 1 FROM t1b_retention_unlock
    WHERE run_id = OLD.run_id
      AND consumed_at IS NULL
      AND expires_at > strftime('%Y-%m-%d %H:%M:%S', 'now')
)
BEGIN
    SELECT RAISE(ABORT, 't1b_decisions is append-only outside a bound, live retention unlock');
END;
"""

#: 🔴 ตารางของ T1A ที่ชั้นนี้ **ห้ามแตะ** ไม่ว่าอ่านหรือเขียน
T1A_TABLES = frozenset({"findings", "item_matches", "runs", "run_rules"})


def init_t1b_schema(db_path=None) -> None:
    conn = connect(db_path)
    try:
        # migrate v2→v3: ตารางสิทธิ์ลบรุ่นเก่าไม่มี run_id/expires_at — เป็นตาราง
        # ชั่วคราวที่ต้องว่างเสมอนอกธุรกรรม จึงทิ้งแล้วสร้างใหม่ได้โดยไม่เสียข้อมูล
        cols = {r["name"] for r in conn.execute(
            "PRAGMA table_info(t1b_retention_unlock)")}
        if cols and "run_id" not in cols:
            conn.execute("DROP TABLE t1b_retention_unlock")
        conn.executescript(_SCHEMA)
        conn.execute("DROP TRIGGER IF EXISTS t1b_decisions_no_delete")
        conn.executescript(_NO_DELETE_TRIGGER)
        row = conn.execute(
            "SELECT version FROM t1b_schema_migrations WHERE version = ?",
            (T1B_SCHEMA_VERSION,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO t1b_schema_migrations (version, applied_at) "
                "VALUES (?, datetime('now'))", (T1B_SCHEMA_VERSION,))
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def _loc(view) -> str:
    if view is None:
        return "{}"
    return _j({"side": view.side, "sheet": view.sheet, "cell": view.cell,
               "row": view.row, "label": view.label, "value": view.value})


def save_run(view, *, project_id: str = "", note: str = "",
             run_id: str = "", db_path=None) -> str:
    """บันทึกหนึ่งรอบพร้อม finding ทั้งชุด แล้วคืน ``run_id``

    🔴 บันทึก **ทั้งชุด** เสมอ ไม่มีทางเลือกให้บันทึกเฉพาะรายการที่ต้องตรวจ —
    การนับที่หน้าสรุปกับจำนวนแถวในฐานข้อมูลต้องตรงกันเสมอ มิฉะนั้นผู้อ่าน
    จะเข้าใจว่ารายการที่ไม่ปรากฏคือรายการที่ระบบไม่พบ
    """
    rid = run_id or view.summary.run_id or uuid.uuid4().hex
    s = view.summary
    with session(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO t1b_runs (id, project_id, started_at, "
            "finished_at, key_version, matching_version, compare_version, "
            "service_version, identity_reason, identity_verdict, "
            "identity_blocked, automatic_pairs, total_findings, "
            "requiring_review, by_type_json, by_flag_json, note) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, project_id, _now(), _now(), s.key_version, s.matching_version,
             s.compare_version, s.service_version, s.identity_reason,
             s.identity_verdict, int(s.identity_gate_blocked),
             s.automatic_pairs, s.total_findings, s.requiring_review,
             _j(s.by_type), _j(s.by_flag), note))
        conn.execute("DELETE FROM t1b_findings WHERE run_id = ?", (rid,))
        conn.executemany(
            "INSERT INTO t1b_findings (id, run_id, finding_id, identity_basis, "
            "side, ordinal, finding_type, requires_review, comparison_axis, "
            "fiscal_year, budget_category, row_label, sheet_role, "
            "section_title, parent_plan, declared_unit, baseline_value, "
            "current_value, difference, baseline_table_year, "
            "current_table_year, baseline_loc_json, current_loc_json, "
            "flags_json, detail) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (uuid.uuid4().hex, rid, f.finding_id, f.identity_basis, f.side,
                 i, f.finding_type,
                 int(f.requires_human_decision), f.comparison_axis,
                 f.fiscal_year, f.budget_category, f.row_label, f.sheet_role,
                 f.section_title, f.parent_plan, f.declared_unit,
                 f.baseline_value, f.current_value, f.difference,
                 f.baseline_category_table_year, f.current_category_table_year,
                 _loc(f.baseline), _loc(f.current), _j(list(f.flags)), f.detail)
                for i, f in enumerate(view.findings)
            ])
    return rid


def get_run(run_id: str, db_path=None) -> dict | None:
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM t1b_runs WHERE id = ?",
                           (run_id,)).fetchone()
        if row is None:
            return None
        out = dict(row)
        out["by_type"] = json.loads(out.pop("by_type_json") or "{}")
        out["by_flag"] = json.loads(out.pop("by_flag_json") or "{}")
        out["identity_blocked"] = bool(out["identity_blocked"])
        return out
    finally:
        conn.close()


def list_runs(db_path=None, *, limit: int = 50) -> list[dict]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, project_id, started_at, identity_verdict, "
            "total_findings, requiring_review FROM t1b_runs "
            "ORDER BY started_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_findings(run_id: str, db_path=None) -> list[dict]:
    """คืน finding **ตามลำดับที่บันทึกไว้** — ลำดับคือส่วนหนึ่งของหลักฐาน"""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM t1b_findings WHERE run_id = ? ORDER BY ordinal",
            (run_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["flags"] = tuple(json.loads(d.pop("flags_json") or "[]"))
            d["baseline_location"] = json.loads(d.pop("baseline_loc_json") or "{}")
            d["current_location"] = json.loads(d.pop("current_loc_json") or "{}")
            d["requires_review"] = bool(d["requires_review"])
            out.append(d)
        return out
    finally:
        conn.close()


def count_findings(run_id: str, db_path=None) -> int:
    conn = connect(db_path)
    try:
        return int(conn.execute(
            "SELECT COUNT(*) FROM t1b_findings WHERE run_id = ?",
            (run_id,)).fetchone()[0])
    finally:
        conn.close()


def delete_run(run_id: str, db_path=None) -> None:
    """ลบรอบหนึ่งทั้งก้อน — ใช้ตอนผู้ใช้ขอลบข้อมูลของตัวเอง (retention)

    🔴 ต้องเปิดช่องลบก่อน เพราะ ``t1b_decisions`` เป็นตาราง append-only
    ที่ฐานข้อมูลกัน ``DELETE`` ไว้ — ดู :func:`t1b_decisions.retention_unlock`
    """
    from . import t1b_decisions

    # 🔴 เปิดสิทธิ์ · ลบ · consume — ทั้งสามอย่างในธุรกรรมเดียว ล้มที่ใดก็ย้อนทั้งชุด
    with session(db_path) as conn:
        token = t1b_decisions.open_retention_unlock(conn, run_id,
                                                    f"delete_run:{run_id}")
        conn.execute("DELETE FROM t1b_findings WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM t1b_runs WHERE id = ?", (run_id,))
        t1b_decisions.consume_retention_unlock(conn, token)


def delete_runs_for_project(project_id: str, db_path=None) -> int:
    """ลบรอบ T1B ทั้งหมดของงานตรวจหนึ่งงาน คืนจำนวนรอบที่ลบ

    🔴 ``t1b_runs.project_id`` **ไม่ใช่ foreign key** โดยเจตนา (คนละสายงาน
    คนละ schema) จึงไม่มี cascade มาช่วย — ต้องลบตรงนี้เอง
    ``t1b_findings`` มี cascade จาก ``t1b_runs`` อยู่แล้ว
    """
    from . import t1b_decisions

    # 🔴 สิทธิ์ลบผูกกับ run ทีละรอบ · เปิด-ลบ-consume ในธุรกรรมเดียว
    # ล้มที่รอบใดก็ย้อนกลับทั้งชุด ไม่เหลือข้อมูลครึ่งหนึ่ง (B.3)
    with session(db_path) as conn:
        rows = conn.execute("SELECT id FROM t1b_runs WHERE project_id = ?",
                            (project_id,)).fetchall()
        for r in rows:
            token = t1b_decisions.open_retention_unlock(
                conn, r["id"], f"delete_project:{project_id}")
            conn.execute("DELETE FROM t1b_runs WHERE id = ?", (r["id"],))
            t1b_decisions.consume_retention_unlock(conn, token)
    return len(rows)
