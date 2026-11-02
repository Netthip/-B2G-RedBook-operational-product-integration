# -*- coding: utf-8 -*-
"""ที่เก็บรอบเทียบเล่ม PDF ↔ PDF และคำตัดสินของคน — ตารางแยก เพิ่มอย่างเดียว ไม่แตะตาราง T1B

* ``pdfpair_runs``       หนึ่งแถวต่อหนึ่งรอบเทียบ — เก็บข้อเท็จจริงที่สกัดได้ของสองฉบับ + ผลเทียบเป็น JSON
                         พร้อม SHA-256 ของไฟล์ทั้งสอง · รุ่นตัวสกัด/โปรไฟล์ · ช่วงหน้าที่ใช้
* ``pdfpair_decisions``  คำตัดสินล่าสุดต่อข้อสังเกต · ทุกครั้งที่บันทึกมีรายการ Audit (ธุรกรรมเดียวกัน)
* ``pdfpair_year_confirms``  ปีงบที่ผู้ตรวจยืนยันจากภาพหน้าเอกสาร ต่อฉบับ (เมื่อระบบอ่านปีไม่แน่ชัด)
  · ไม่แก้ผลเทียบที่บันทึกไว้ · มีรายการ Audit
* ``pdfpair_run_links``  รอบเดิม → รอบใหม่ที่คำนวณซ้ำด้วยปีงบที่ยืนยัน · รอบเดิมถูกบล็อก (ไม่ลบ ไม่แก้ผล/คำตัดสินเดิม)
"""
from __future__ import annotations

import json
import uuid

from . import audit
from .db import connect
from .repository import now_iso

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pdfpair_runs (
    id            TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    mode          TEXT NOT NULL,
    agency        TEXT NOT NULL DEFAULT '',
    a_sha256      TEXT NOT NULL,
    b_sha256      TEXT NOT NULL,
    a_name        TEXT NOT NULL DEFAULT '',
    b_name        TEXT NOT NULL DEFAULT '',
    scope_json    TEXT NOT NULL,
    facts_a_json  TEXT NOT NULL,
    facts_b_json  TEXT NOT NULL,
    result_json   TEXT NOT NULL,
    versions_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pdfpair_decisions (
    run_id      TEXT NOT NULL,
    finding_id  TEXT NOT NULL,
    choice      TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    decided_at  TEXT NOT NULL,
    PRIMARY KEY (run_id, finding_id)
);
CREATE TABLE IF NOT EXISTS pdfpair_year_confirms (
    run_id       TEXT NOT NULL,
    side         TEXT NOT NULL,
    year         INTEGER NOT NULL,
    note         TEXT NOT NULL DEFAULT '',
    confirmed_at TEXT NOT NULL,
    PRIMARY KEY (run_id, side)
);
CREATE TABLE IF NOT EXISTS pdfpair_run_links (
    old_run_id  TEXT PRIMARY KEY,
    new_run_id  TEXT NOT NULL,
    reason      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""


class SupersededError(ValueError):
    """รอบเดิมถูกแทนไปแล้ว (เช่น กดคำนวณซ้ำพร้อมกัน) — รอบที่คำนวณครั้งนี้ถูก ROLLBACK ไม่ถูกบันทึก"""

    def __init__(self, new_run_id: str):
        super().__init__("รอบเดิมถูกแทนไปแล้ว")
        self.new_run_id = new_run_id


class NoteRequired(ValueError):
    """เปลี่ยนคำตัดสิน/ปีที่ยืนยันไว้โดยไม่ระบุเหตุผล — ``previous`` = ค่าที่บันทึกอยู่ตอนตรวจในธุรกรรม"""

    def __init__(self, previous: dict):
        super().__init__("เปลี่ยนค่าที่บันทึกไว้ต้องระบุเหตุผล")
        self.previous = previous


def _refuse_if_superseded(conn, rid: str) -> None:
    """ตรวจในธุรกรรมเขียนที่เปิดอยู่ — คำขอทำงานพร้อมกันได้ (threadpool) การคำนวณซ้ำที่ commit หลังผู้เรียกตรวจ
    สถานะรอบไปแล้วจึงยังถูกจับที่นี่ · รอบที่ถูกแทน = เขียนเพิ่มไม่ได้"""
    hit = conn.execute("SELECT new_run_id FROM pdfpair_run_links WHERE old_run_id = ?", (rid,)).fetchone()
    if hit:
        raise SupersededError(hit["new_run_id"])


def init_schema(db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA)
    finally:
        conn.close()


def save_run(*, project_id: str, mode: str, agency: str, a_sha256: str, b_sha256: str,
             a_name: str, b_name: str, scope: dict, facts_a: dict, facts_b: dict, result: dict,
             versions: dict, supersedes: dict | None = None, db_path=None) -> str:
    """``supersedes`` = ``{"run_id", "reason", "years"}`` เมื่อรอบนี้คำนวณซ้ำแทนรอบเดิม — บันทึกลิงก์ +
    Audit ทั้งสองรอบในธุรกรรมเดียวกับการบันทึกรอบใหม่ (รอบเดิมไม่ถูกแก้)"""
    init_schema(db_path)
    rid = "pp_" + uuid.uuid4().hex[:16]
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO pdfpair_runs (id, project_id, created_at, mode, agency, a_sha256, b_sha256, "
            "a_name, b_name, scope_json, facts_a_json, facts_b_json, result_json, versions_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, project_id, now_iso(), mode, agency[:300], a_sha256, b_sha256, a_name[:300],
             b_name[:300], json.dumps(scope, ensure_ascii=False),
             json.dumps(facts_a, ensure_ascii=False), json.dumps(facts_b, ensure_ascii=False),
             json.dumps(result, ensure_ascii=False), json.dumps(versions, ensure_ascii=False)))
        audit.record_in(conn, "pdfpair_run_completed", "pdfpair_run", rid,
                        {"project_id": project_id, "mode": mode, "a_sha256": a_sha256,
                         "b_sha256": b_sha256, "findings": len(result.get("findings", [])),
                         "scope": scope, "versions": versions,
                         **({"supersedes": supersedes["run_id"]} if supersedes else {})})
        if supersedes:
            old = supersedes["run_id"]
            hit = conn.execute("SELECT new_run_id FROM pdfpair_run_links WHERE old_run_id = ?", (old,)).fetchone()
            if hit:
                raise SupersededError(hit["new_run_id"])
            conn.execute("INSERT INTO pdfpair_run_links (old_run_id, new_run_id, reason, created_at) "
                         "VALUES (?,?,?,?)", (old, rid, supersedes["reason"], now_iso()))
            audit.record_in(conn, "pdfpair_run_superseded", "pdfpair_run", old,
                            {"new_run_id": rid, "reason": supersedes["reason"],
                             "years": supersedes.get("years", {})})
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return rid


def get_run(rid: str, db_path=None) -> dict | None:
    init_schema(db_path)
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM pdfpair_runs WHERE id = ?", (rid,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    d = dict(row)
    for k in ("scope_json", "facts_a_json", "facts_b_json", "result_json", "versions_json"):
        d[k[:-5]] = json.loads(d.pop(k))
    return d


def run_state(rid: str, db_path=None) -> dict | None:
    """ส่วนที่เปลี่ยนได้ของรอบ (คำตัดสิน · ปีที่ยืนยัน · รอบใหม่ที่แทน · รอบเดิมที่แทน) — การเชื่อมต่อเดียวและ snapshot
    เดียวกัน · ``None`` = ไม่มีรอบนี้ในฐานข้อมูล (ผู้เรียกห้ามใช้ผลที่แยก JSON เก็บไว้ของรอบนี้)"""
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.execute("BEGIN")
        try:
            if conn.execute("SELECT 1 FROM pdfpair_runs WHERE id = ?", (rid,)).fetchone() is None:
                return None
            decs = {r["finding_id"]: dict(r) for r in
                    conn.execute("SELECT * FROM pdfpair_decisions WHERE run_id = ?", (rid,))}
            years = {r["side"]: dict(r) for r in
                     conn.execute("SELECT * FROM pdfpair_year_confirms WHERE run_id = ?", (rid,))}
            new = conn.execute("SELECT new_run_id FROM pdfpair_run_links WHERE old_run_id = ?", (rid,)).fetchone()
            old = conn.execute("SELECT old_run_id FROM pdfpair_run_links WHERE new_run_id = ?", (rid,)).fetchone()
        finally:
            conn.execute("COMMIT")
        return {"decisions": decs, "year_confirms": years, "superseded_by": new["new_run_id"] if new else "",
                "supersedes": old["old_run_id"] if old else ""}
    finally:
        conn.close()


#: รายการรหัสรอบผูกเป็นพารามิเตอร์เดียว (JSON array) — SQL เป็นข้อความคงที่ ไม่ประกอบด้วยสตริง (Security Gate #23 static)
_IDS = "(SELECT value FROM json_each(?))"
_BRIEF_SQL = ("SELECT id, " + ", ".join(f"json_extract(facts_{s}_json, '$.{k}') AS {s}_{k}"
                                        for s in ("a", "b") for k in ("stage", "stage_status", "fiscal_year",
                                                                       "year_status"))
              + " FROM pdfpair_runs WHERE id IN " + _IDS)
_BRIEF_IDS_SQL = ("SELECT r.id AS rid, json_extract(je.value, '$.id') AS fid FROM pdfpair_runs r, "
                  "json_each(r.result_json, '$.findings') je WHERE r.id IN " + _IDS
                  + " AND NOT coalesce(json_extract(je.value, '$.info'), 0)")


def run_briefs(run_ids: list, db_path=None) -> dict:
    """ส่วนที่ไม่เปลี่ยนของหลายรอบสำหรับหน้ารายการรอบ — ``{rid: {"actionable": frozenset(รหัสข้อที่ต้องตรวจ),
    "facts": {"A"|"B": {stage, stage_status, fiscal_year, year_status}}}}`` · ใช้ JSON ของ SQLite ดึงเฉพาะช่องที่ใช้
    ไม่แยก JSON ข้อเท็จจริงทั้งก้อน (~450 KB ต่อฉบับ)"""
    if not run_ids:
        return {}
    keys = ("stage", "stage_status", "fiscal_year", "year_status")
    ids = json.dumps(list(run_ids))
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        out = {r["id"]: {"actionable": set(),
                         "facts": {s.upper(): {k: r[f"{s}_{k}"] for k in keys} for s in ("a", "b")}}
               for r in conn.execute(_BRIEF_SQL, (ids,))}
        for r in conn.execute(_BRIEF_IDS_SQL, (ids,)):
            out[r["rid"]]["actionable"].add(r["fid"])
    finally:
        conn.close()
    for b in out.values():
        b["actionable"] = frozenset(b["actionable"])
    return out


def list_state(run_ids: list, db_path=None) -> dict:
    """ส่วนที่เปลี่ยนได้ของหลายรอบในการเชื่อมต่อเดียว (หน้ารายการรอบ) —
    ``{rid: {"decided": set(รหัสข้อที่ตัดสินแล้ว), "years": {side: ปีที่ยืนยัน}, "superseded_by": รหัสรอบใหม่}}``"""
    out = {rid: {"decided": set(), "years": {}, "superseded_by": ""} for rid in run_ids}
    if not run_ids:
        return out
    ids = (json.dumps(list(run_ids)),)
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.execute("BEGIN")
        try:
            for r in conn.execute("SELECT run_id, finding_id FROM pdfpair_decisions WHERE run_id IN " + _IDS, ids):
                out[r["run_id"]]["decided"].add(r["finding_id"])
            for r in conn.execute("SELECT run_id, side, year FROM pdfpair_year_confirms WHERE run_id IN " + _IDS, ids):
                out[r["run_id"]]["years"][r["side"]] = r["year"]
            for r in conn.execute("SELECT old_run_id, new_run_id FROM pdfpair_run_links WHERE old_run_id IN " + _IDS,
                                  ids):
                out[r["old_run_id"]]["superseded_by"] = r["new_run_id"]
        finally:
            conn.execute("COMMIT")
    finally:
        conn.close()
    return out


def list_runs(project_id: str = "", limit: int = 50, db_path=None) -> list[dict]:
    init_schema(db_path)
    conn = connect(db_path)
    try:
        q = ("SELECT id, project_id, created_at, mode, agency, a_name, b_name FROM pdfpair_runs "
             + ("WHERE project_id = ? " if project_id else "") + "ORDER BY created_at DESC LIMIT ?")
        rows = conn.execute(q, ((project_id, limit) if project_id else (limit,))).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def decisions(rid: str, db_path=None) -> dict:
    init_schema(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM pdfpair_decisions WHERE run_id = ?", (rid,)).fetchall()
        return {r["finding_id"]: dict(r) for r in rows}
    finally:
        conn.close()


def decide(rid: str, finding_id: str, choice: str, note: str, db_path=None) -> None:
    """บันทึกคำตัดสิน + Audit ในธุรกรรมเดียว · ตรวจซ้ำในธุรกรรม: รอบยังไม่ถูกแทน (:class:`SupersededError`) ·
    เปลี่ยนคำตัดสินเดิมต้องมีหมายเหตุ (:class:`NoteRequired`) — สองแท็บกดพร้อมกันก็ไม่หลุดกติกา"""
    init_schema(db_path)
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        _refuse_if_superseded(conn, rid)
        prev = conn.execute("SELECT choice, note FROM pdfpair_decisions WHERE run_id = ? AND "
                            "finding_id = ?", (rid, finding_id)).fetchone()
        if prev and prev["choice"] != choice and not note.strip():
            raise NoteRequired(dict(prev))
        conn.execute("INSERT OR REPLACE INTO pdfpair_decisions (run_id, finding_id, choice, note, "
                     "decided_at) VALUES (?,?,?,?,?)", (rid, finding_id, choice, note[:2000], now_iso()))
        audit.record_in(conn, "pdfpair_decision", "pdfpair_finding", f"{rid}/{finding_id}",
                        {"choice": choice, "note": note[:2000],
                         "previous": dict(prev) if prev else None})
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def confirm_year(rid: str, side: str, year: int, note: str, detected: dict, db_path=None) -> None:
    """ผู้ตรวจยืนยันปีงบของฉบับ ``side`` จากภาพหน้าเอกสาร — บันทึก + Audit ในธุรกรรมเดียวกัน · ตรวจซ้ำในธุรกรรม
    เหมือน :func:`decide` (รอบยังไม่ถูกแทน · เปลี่ยนปีที่ยืนยันไว้ต้องมีหมายเหตุ)"""
    init_schema(db_path)
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        _refuse_if_superseded(conn, rid)
        prev = conn.execute("SELECT year, note FROM pdfpair_year_confirms WHERE run_id = ? AND side = ?",
                            (rid, side)).fetchone()
        if prev and int(prev["year"]) != int(year) and not note.strip():
            raise NoteRequired(dict(prev))
        conn.execute("INSERT OR REPLACE INTO pdfpair_year_confirms (run_id, side, year, note, confirmed_at) "
                     "VALUES (?,?,?,?,?)", (rid, side, int(year), note[:2000], now_iso()))
        audit.record_in(conn, "pdfpair_year_confirmed", "pdfpair_run", f"{rid}/year/{side}",
                        {"year": int(year), "note": note[:2000], "detected": detected,
                         "previous": dict(prev) if prev else None})
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def year_confirms(rid: str, db_path=None) -> dict:
    init_schema(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM pdfpair_year_confirms WHERE run_id = ?", (rid,)).fetchall()
        return {r["side"]: dict(r) for r in rows}
    finally:
        conn.close()


def superseded_by(rid: str, db_path=None) -> str:
    """รหัสรอบใหม่ที่แทนรอบนี้ ("" = ยังไม่ถูกแทน)"""
    init_schema(db_path)
    conn = connect(db_path)
    try:
        r = conn.execute("SELECT new_run_id FROM pdfpair_run_links WHERE old_run_id = ?", (rid,)).fetchone()
        return r["new_run_id"] if r else ""
    finally:
        conn.close()


def supersedes(rid: str, db_path=None) -> str:
    """รหัสรอบเดิมที่รอบนี้แทน ("" = รอบนี้ไม่ได้แทนรอบใด)"""
    init_schema(db_path)
    conn = connect(db_path)
    try:
        r = conn.execute("SELECT old_run_id FROM pdfpair_run_links WHERE new_run_id = ?", (rid,)).fetchone()
        return r["old_run_id"] if r else ""
    finally:
        conn.close()


def record_export(rid: str, sha256: str, rows: int, db_path=None, **extra) -> None:
    """Audit การส่งออก — ตรวจในธุรกรรมว่ารอบยังไม่ถูกแทน (คำนวณซ้ำที่ commit หลังด่านก่อนส่งออก = ไม่บันทึก
    ผู้เรียกต้องไม่ส่งไฟล์)"""
    init_schema(db_path)
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        _refuse_if_superseded(conn, rid)
        audit.record_in(conn, "pdfpair_exported", "pdfpair_run", rid, {"sha256": sha256, "rows": rows, **extra})
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def audit_entries(rid: str, db_path=None) -> list[dict]:
    """รายการ Audit ของรอบนี้ (ตัวรอบ · คำตัดสินทุกข้อ · การยืนยันปี · การส่งออก) เรียงตามเวลา"""
    conn = connect(db_path)
    try:
        # ไม่ใช้ LIKE — รหัสรอบมี "_" ซึ่งเป็นอักขระตัวแทนของ LIKE
        rows = conn.execute("SELECT * FROM audit_log WHERE object_id = ? OR substr(object_id, 1, ?) = ? "
                            "ORDER BY seq ASC", (rid, len(rid) + 1, rid + "/")).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


__all__ = ["SupersededError", "NoteRequired", "init_schema", "save_run", "get_run", "run_state", "run_briefs",
           "list_state", "list_runs", "decisions", "decide", "confirm_year", "year_confirms", "superseded_by",
           "supersedes", "record_export", "audit_entries"]
