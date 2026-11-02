# -*- coding: utf-8 -*-
"""ที่เก็บรอบ "ทดลองตรวจเล่ม" ของผู้ตรวจ (#43) — ตารางแยก เพิ่มอย่างเดียว ไม่แตะตารางเดิม

* ``trial_sessions``  หนึ่งแถวต่อการตรวจหนึ่งเล่มของผู้ตรวจหนึ่งคน · ``locked_at`` = รับใบประกาศแล้ว (ล็อก)
  · ``run_id`` = รอบเทียบของระบบที่สร้าง **หลังล็อกเท่านั้น** · ``released_at`` = เวลาที่ผลระบบพร้อมให้ผู้ตรวจเห็น ·
  ``protocol`` ว่าง = รอบที่เริ่มก่อนวิธีวัดผลฉบับ 0.2 (รอบกติกา 0.1) · ``path`` = ทางทำรายการอ้างอิง (ร1/ร2) ·
  ``status`` = หยุด/ถอนตัว (ว่าง = ยังทำอยู่)
* ``trial_marks``     ประเด็นในรายการอ้างอิง — ``origin='mark'`` จุดที่วงบนภาพหน้า (ร2 · ตำแหน่งเป็นสัดส่วนของหน้า 0–1) ·
  ``origin='row'`` แถวของรายการเดิมของผู้ตรวจ (ร1 · สร้างจากใบประกาศตอนล็อก ไม่มีเนื้อหาของประเด็น) ·
  หัวข้อ ก–ญ · ส่วนของเล่ม ๑–๘ · ต/ล · ระดับ · ของที่หาย (ฉบับที่พบ + ขอบเขตที่ค้น) · ลบ = ``deleted`` (ไม่ลบแถว)
* ``trial_declarations`` ใบประกาศจำนวนก่อนเห็นผล (แบบ 02 ส่วนที่ ๑) + แฮช + เวลารับ — หนึ่งใบต่อรอบ แก้ไม่ได้
* ``trial_pages``     หน้าที่ผู้ตรวจกด "ตรวจหน้านี้แล้ว" (ตัวช่วยของผู้ตรวจ ไม่ใช่เงื่อนไขการล็อกตั้งแต่ฉบับ 0.2)
* ``trial_views``     คู่หน้าที่เปิดเทียบระหว่างตรวจ
* ``trial_proposals`` ข้อเสนอคู่ของระบบจากตำแหน่ง (บันทึกครั้งเดียวต่อรอบเทียบ · ข้อเสนอ ≠ คำตัดสิน)
* ``trial_issue_decisions`` / ``trial_issue_links`` ผลการจับคู่ของแต่ละประเด็น (ผล · รหัสเหตุ · หลักฐานชี้ตำแหน่ง ·
  ฐานการวินิจฉัย) + ชุดข้อสังเกตที่จับคู่ (หนึ่งต่อหลาย/หลายต่อหนึ่ง)
* ``trial_finding_groups`` กลุ่ม ส1–ส4 (หรือ "นอกส่วนที่ตรวจครบ") ของข้อสังเกตต้องตรวจที่ไม่ได้จับคู่
* ``trial_history``   ประวัติการเปลี่ยนคู่/การจัดกลุ่ม (ก่อน → หลัง + เหตุผล) — เพิ่มอย่างเดียว
* ``trial_post_notes`` ข้อสังเกตหลังล็อก (ไม่นับในรายการที่ล็อก)
* ``trial_links`` / ``trial_extras`` ผลของรอบกติกา 0.1 — เก็บไว้อ่านย้อนหลัง ไม่เขียนเพิ่ม
* ``trial_answers``   แบบสอบถามหลังใช้ผล (ข้อ → ค่า)

ทุกการเปลี่ยนแปลงลง Audit ในธุรกรรมเดียวกัน · ตารางที่สร้างด้วยรุ่นเก่าได้คอลัมน์ใหม่ด้วย ``ALTER TABLE … ADD COLUMN``
(ค่าเริ่มต้นว่าง — แถวเดิมไม่เปลี่ยน)
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime

from . import audit
from .db import connect
from .repository import now_iso

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trial_sessions (
    id          TEXT PRIMARY KEY,
    book_id     TEXT NOT NULL,
    reviewer    TEXT NOT NULL DEFAULT '',
    book_json   TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    locked_at   TEXT NOT NULL DEFAULT '',
    run_id      TEXT NOT NULL DEFAULT '',
    project_id  TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS trial_marks (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    side        TEXT NOT NULL,
    page        INTEGER NOT NULL,
    fx          REAL NOT NULL,
    fy          REAL NOT NULL,
    pen         TEXT NOT NULL,
    topic       TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    deleted     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS trial_pages (
    session_id  TEXT NOT NULL,
    side        TEXT NOT NULL,
    page        INTEGER NOT NULL,
    done_at     TEXT NOT NULL,
    PRIMARY KEY (session_id, side, page)
);
CREATE TABLE IF NOT EXISTS trial_views (
    session_id  TEXT NOT NULL,
    cur_page    INTEGER NOT NULL,
    prev_page   INTEGER NOT NULL DEFAULT 0,
    viewed_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trial_links (
    session_id  TEXT NOT NULL,
    mark_id     TEXT NOT NULL,
    finding_id  TEXT NOT NULL DEFAULT '',
    proposed    INTEGER NOT NULL DEFAULT 0,
    verdict     TEXT NOT NULL DEFAULT '',
    decided_at  TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (session_id, mark_id)
);
CREATE TABLE IF NOT EXISTS trial_extras (
    session_id  TEXT NOT NULL,
    finding_id  TEXT NOT NULL,
    verdict     TEXT NOT NULL,
    decided_at  TEXT NOT NULL,
    PRIMARY KEY (session_id, finding_id)
);
CREATE TABLE IF NOT EXISTS trial_answers (
    session_id  TEXT NOT NULL,
    item        TEXT NOT NULL,
    value       TEXT NOT NULL,
    answered_at TEXT NOT NULL,
    PRIMARY KEY (session_id, item)
);
CREATE TABLE IF NOT EXISTS trial_declarations (
    session_id  TEXT PRIMARY KEY,
    path        TEXT NOT NULL,
    body_json   TEXT NOT NULL,
    hash        TEXT NOT NULL,
    received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trial_proposals (
    session_id  TEXT NOT NULL,
    mark_id     TEXT NOT NULL,
    finding_id  TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (session_id, mark_id)
);
CREATE TABLE IF NOT EXISTS trial_obs_class (
    session_id  TEXT NOT NULL,
    finding_id  TEXT NOT NULL,
    topic       TEXT NOT NULL DEFAULT '',
    kind        TEXT NOT NULL DEFAULT '',
    info        INTEGER NOT NULL DEFAULT 0,
    level       TEXT NOT NULL,
    reason      TEXT NOT NULL DEFAULT '',
    rule        TEXT NOT NULL DEFAULT '',
    engine      TEXT NOT NULL DEFAULT '',
    saved_at    TEXT NOT NULL,
    PRIMARY KEY (session_id, finding_id)
);
CREATE TABLE IF NOT EXISTS trial_obs_eval (
    session_id       TEXT NOT NULL,
    finding_id       TEXT NOT NULL,
    fidelity         TEXT NOT NULL,
    fidelity_reason  TEXT NOT NULL DEFAULT '',
    dims_json        TEXT NOT NULL DEFAULT '{}',
    assertion        TEXT NOT NULL,
    basis            TEXT NOT NULL DEFAULT '',
    decided_at       TEXT NOT NULL,
    PRIMARY KEY (session_id, finding_id)
);
CREATE TABLE IF NOT EXISTS trial_issue_decisions (
    session_id  TEXT NOT NULL,
    mark_id     TEXT NOT NULL,
    verdict     TEXT NOT NULL,
    reason      TEXT NOT NULL DEFAULT '',
    evidence    TEXT NOT NULL DEFAULT '',
    basis       TEXT NOT NULL DEFAULT '',
    decided_at  TEXT NOT NULL,
    PRIMARY KEY (session_id, mark_id)
);
CREATE TABLE IF NOT EXISTS trial_issue_links (
    session_id  TEXT NOT NULL,
    mark_id     TEXT NOT NULL,
    finding_id  TEXT NOT NULL,
    linked_at   TEXT NOT NULL,
    PRIMARY KEY (session_id, mark_id, finding_id)
);
CREATE TABLE IF NOT EXISTS trial_finding_groups (
    session_id  TEXT NOT NULL,
    finding_id  TEXT NOT NULL,
    grp         TEXT NOT NULL,
    s3_reason   TEXT NOT NULL DEFAULT '',
    basis       TEXT NOT NULL DEFAULT '',
    issue_ref   TEXT NOT NULL DEFAULT '',
    decided_at  TEXT NOT NULL,
    PRIMARY KEY (session_id, finding_id)
);
CREATE TABLE IF NOT EXISTS trial_history (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    before_json TEXT NOT NULL,
    after_json  TEXT NOT NULL,
    reason      TEXT NOT NULL DEFAULT '',
    changed_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trial_post_notes (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    part        TEXT NOT NULL DEFAULT '',
    topic       TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
"""

#: คอลัมน์ที่เพิ่มในฉบับ 0.2 — ตารางที่สร้างด้วยรุ่นก่อนได้คอลัมน์เหล่านี้ตอนเปิดครั้งแรก (แถวเดิมได้ค่าว่าง) ·
#: เขียนคำสั่ง ALTER เต็มเป็นค่าคงที่ ไม่ประกอบชื่อตาราง/คอลัมน์ตอนรัน (#23 dynamic SQL · Bo #42 6433564226 ข้อ 4)
_ADDED = {
    "trial_sessions": (
        ("protocol", "ALTER TABLE trial_sessions ADD COLUMN protocol TEXT NOT NULL DEFAULT ''"),
        ("trial_version", "ALTER TABLE trial_sessions ADD COLUMN trial_version TEXT NOT NULL DEFAULT ''"),
        ("path", "ALTER TABLE trial_sessions ADD COLUMN path TEXT NOT NULL DEFAULT ''"),
        ("released_at", "ALTER TABLE trial_sessions ADD COLUMN released_at TEXT NOT NULL DEFAULT ''"),
        ("run_error", "ALTER TABLE trial_sessions ADD COLUMN run_error TEXT NOT NULL DEFAULT ''"),
        ("run_failures", "ALTER TABLE trial_sessions ADD COLUMN run_failures INTEGER NOT NULL DEFAULT 0"),
        ("status", "ALTER TABLE trial_sessions ADD COLUMN status TEXT NOT NULL DEFAULT ''"),
        ("status_reason", "ALTER TABLE trial_sessions ADD COLUMN status_reason TEXT NOT NULL DEFAULT ''"),
        ("status_at", "ALTER TABLE trial_sessions ADD COLUMN status_at TEXT NOT NULL DEFAULT ''"),
        ("no_data_use", "ALTER TABLE trial_sessions ADD COLUMN no_data_use INTEGER NOT NULL DEFAULT 0"),
        ("use_done_at", "ALTER TABLE trial_sessions ADD COLUMN use_done_at TEXT NOT NULL DEFAULT ''"),
        ("use_done_reason", "ALTER TABLE trial_sessions ADD COLUMN use_done_reason TEXT NOT NULL DEFAULT ''"),
        ("prior_release", "ALTER TABLE trial_sessions ADD COLUMN prior_release TEXT NOT NULL DEFAULT ''"),
        ("consent_at", "ALTER TABLE trial_sessions ADD COLUMN consent_at TEXT NOT NULL DEFAULT ''"),
        ("use_done_json", "ALTER TABLE trial_sessions ADD COLUMN use_done_json TEXT NOT NULL DEFAULT ''"),
    ),
    "trial_marks": (
        ("origin", "ALTER TABLE trial_marks ADD COLUMN origin TEXT NOT NULL DEFAULT 'mark'"),
        ("level", "ALTER TABLE trial_marks ADD COLUMN level TEXT NOT NULL DEFAULT ''"),
        ("cause", "ALTER TABLE trial_marks ADD COLUMN cause TEXT NOT NULL DEFAULT ''"),
        ("part", "ALTER TABLE trial_marks ADD COLUMN part TEXT NOT NULL DEFAULT ''"),
        ("searched", "ALTER TABLE trial_marks ADD COLUMN searched TEXT NOT NULL DEFAULT ''"),
        ("found_in", "ALTER TABLE trial_marks ADD COLUMN found_in TEXT NOT NULL DEFAULT ''"),
        ("seq", "ALTER TABLE trial_marks ADD COLUMN seq INTEGER NOT NULL DEFAULT 0"),
        ("ref", "ALTER TABLE trial_marks ADD COLUMN ref TEXT NOT NULL DEFAULT ''"),
        ("row_source", "ALTER TABLE trial_marks ADD COLUMN row_source TEXT NOT NULL DEFAULT ''"),
        ("xtype", "ALTER TABLE trial_marks ADD COLUMN xtype TEXT NOT NULL DEFAULT ''"),
    ),
    "trial_finding_groups": (
        ("part", "ALTER TABLE trial_finding_groups ADD COLUMN part TEXT NOT NULL DEFAULT ''"),
        ("note", "ALTER TABLE trial_finding_groups ADD COLUMN note TEXT NOT NULL DEFAULT ''"),
    ),
    "trial_issue_decisions": (
        ("location", "ALTER TABLE trial_issue_decisions ADD COLUMN location TEXT NOT NULL DEFAULT ''"),
        ("relevant_sides", "ALTER TABLE trial_issue_decisions ADD COLUMN relevant_sides TEXT NOT NULL DEFAULT ''"),
        ("search_scope", "ALTER TABLE trial_issue_decisions ADD COLUMN search_scope TEXT NOT NULL DEFAULT ''"),
    ),
}
#: ฟิลด์ของประเด็นที่แก้ได้ (ก่อนล็อกสำหรับจุดที่วง · หลังล็อกสำหรับแถวของ ร1 ยกเว้นหัวข้อ)
MARK_FIELDS = ("topic", "note", "pen", "level", "cause", "part", "searched", "found_in", "ref", "row_source", "side",
               "page", "deleted", "xtype")
#: ทุกคอลัมน์ใน MARK_FIELDS ตามลำดับ · ไม่ส่งค่า (None) = คงค่าเดิม — SQL คงที่ ค่า bind ทั้งหมด (#23 dynamic SQL)
_UPDATE_MARK_SQL = ("UPDATE trial_marks SET topic = COALESCE(?, topic), note = COALESCE(?, note), "
                    "pen = COALESCE(?, pen), level = COALESCE(?, level), cause = COALESCE(?, cause), "
                    "part = COALESCE(?, part), searched = COALESCE(?, searched), found_in = COALESCE(?, found_in), "
                    "ref = COALESCE(?, ref), row_source = COALESCE(?, row_source), side = COALESCE(?, side), "
                    "page = COALESCE(?, page), deleted = COALESCE(?, deleted), xtype = COALESCE(?, xtype) "
                    "WHERE id = ? AND session_id = ?")


def _migrate(conn) -> None:
    for table, cols in _ADDED.items():
        have = {r["name"] for r in conn.execute("SELECT name FROM pragma_table_info(?)", (table,)).fetchall()}
        for name, stmt in cols:
            if name in have:
                continue
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError as e:     # อีกกระบวนการเพิ่มไปก่อนแล้ว
                if "duplicate column" not in str(e).lower():
                    raise


def init_schema(db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        _migrate(conn)
    finally:
        conn.close()


def _tx(fn, db_path=None):
    init_schema(db_path)
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        out = fn(conn)
        conn.execute("COMMIT")
        return out
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def _rows(sql: str, args=(), db_path=None) -> list[dict]:
    init_schema(db_path)
    conn = connect(db_path)
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def precise_now() -> str:
    """เวลาละเอียดถึงไมโครวินาที — ใช้กับเวลารับใบประกาศ/เวลาปล่อยผล ที่ต้องพิสูจน์ลำดับได้แม้เกิดในวินาทีเดียวกัน"""
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def marks_hash(marks: list) -> str:
    """แฮชของชุดประเด็น (ทุกฟิลด์ที่มีผลต่อการนับ) — ใช้ล็อกและตรวจซ้ำในธุรกรรมเดียวกับการล็อก"""
    keys = ("id", "origin", "side", "page", "fx", "fy", "pen", "topic", "note", "level", "cause", "part",
            "searched", "found_in", "seq", "ref", "xtype")
    body = json.dumps([[m.get(k, "") for k in keys] for m in sorted(marks, key=lambda x: x["id"])],
                      ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _live_marks(conn, sid: str) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM trial_marks WHERE session_id = ? AND deleted = 0",
                                          (sid,)).fetchall()]


def _session_row(conn, sid: str):
    return conn.execute("SELECT * FROM trial_sessions WHERE id = ?", (sid,)).fetchone()


def _need_open(conn, sid: str, *, unlocked: bool = True) -> None:
    """ตรวจซ้ำในธุรกรรม: รอบยังทำอยู่ (ไม่หยุด/ไม่ถอนตัว) และ (ถ้าระบุ) ยังไม่ล็อก"""
    r = _session_row(conn, sid)
    if r is None:
        raise ValueError("ไม่พบรอบตรวจ")
    if r["status"]:
        raise ValueError("รอบนี้หยุดหรือถอนตัวแล้ว — บันทึกเพิ่มไม่ได้ (ข้อมูลเดิมเก็บไว้ตามเดิม)")
    if unlocked and r["locked_at"]:
        raise ValueError("รอบนี้ส่งใบประกาศแล้ว — แก้รายการที่ล็อกไม่ได้ (ข้อมูลเดิมเก็บไว้ตามเดิม)")


# ── รอบตรวจ ─────────────────────────────────────────────────────────────────
def create_session(book_id: str, reviewer: str, book: dict, *, path: str = "", protocol: str = "",
                   trial_version: str = "", prior_release: str = "", db_path=None) -> str:
    sid = "tr_" + uuid.uuid4().hex[:16]

    def fn(conn):
        conn.execute("INSERT INTO trial_sessions (id, book_id, reviewer, book_json, started_at, path, protocol, "
                     "trial_version, prior_release) VALUES (?,?,?,?,?,?,?,?,?)",
                     (sid, book_id, reviewer[:40], json.dumps(book, ensure_ascii=False), now_iso(), path, protocol,
                      trial_version, prior_release))
        audit.record_in(conn, "trial_started", "trial_session", sid,
                        {"book_id": book_id, "book": book, "path": path, "protocol": protocol,
                         "trial_version": trial_version, "prior_release": prior_release})
    _tx(fn, db_path)
    return sid


def get_session(sid: str, db_path=None) -> dict | None:
    rows = _rows("SELECT * FROM trial_sessions WHERE id = ?", (sid,), db_path)
    if not rows:
        return None
    d = rows[0]
    d["book"] = json.loads(d.pop("book_json"))
    return d


def sessions(db_path=None) -> list[dict]:
    out = _rows("SELECT * FROM trial_sessions ORDER BY started_at DESC", (), db_path)
    for d in out:
        d["book"] = json.loads(d.pop("book_json"))
    return out


def set_path(sid: str, path: str, db_path=None) -> None:
    def fn(conn):
        _need_open(conn, sid)
        if path == "r1" and conn.execute("SELECT COUNT(*) FROM trial_marks WHERE session_id = ? AND deleted = 0",
                                         (sid,)).fetchone()[0]:
            raise ValueError("รอบนี้มีจุดที่วงไว้ — ทาง ร1 ไม่ใช้จุดบนภาพ ลบจุดที่วงก่อน หรือเริ่มรอบใหม่")
        conn.execute("UPDATE trial_sessions SET path = ? WHERE id = ?", (path, sid))
        audit.record_in(conn, "trial_path_set", "trial_session", sid, {"path": path})
    _tx(fn, db_path)


def lock(sid: str, counts: dict, *, declaration: dict | None = None, rows=(), expect_marks_hash: str | None = None,
         protocol: str = "", path: str = "", require_pages=None, db_path=None) -> str:
    """ล็อกรอบ (รับใบประกาศ) — ตรวจซ้ำ **ในธุรกรรมเดียวกับการล็อก**: ยังไม่ล็อก · ยังทำอยู่ ·
    ชุดจุดที่วงยังเป็นชุดเดียวกับที่ชั้นบริการตรวจ (``expect_marks_hash``) · (รอบกติกา 0.1) หน้าครบ ``require_pages``

    ``declaration`` = ใบประกาศ (บันทึกพร้อมแฮชและเวลารับ) · ``rows`` = แถวของรายการเดิม (ร1) ที่สร้างพร้อมการล็อก ·
    ``protocol``/``path`` = ฉบับวิธีวัดผลและทางที่ใช้นับรอบนี้ (รอบที่เริ่มก่อนฉบับ 0.2 ได้ค่านี้ตอนล็อก) · คืนเวลารับ"""
    out = {}

    def fn(conn):
        _need_open(conn, sid)
        if expect_marks_hash is not None and marks_hash(_live_marks(conn, sid)) != expect_marks_hash:
            raise ValueError("จุดที่วงเปลี่ยนระหว่างส่ง (เช่น แก้จากอีกแท็บ) — ตรวจรายการอีกครั้งแล้วส่งใหม่")
        if require_pages is not None:
            done = {x["page"] for x in conn.execute("SELECT page FROM trial_pages WHERE session_id = ? AND side = 'cur'",
                                                    (sid,)).fetchall()}
            missing = [p for p in require_pages if int(p) not in done]
            if missing:
                raise ValueError(f"ยังไม่ได้กด \"ตรวจหน้านี้แล้ว\" อีก {len(missing)} หน้า")
        at = precise_now()
        detail = dict(counts)
        if declaration is not None:
            body = json.dumps(declaration, ensure_ascii=False, sort_keys=True)
            h = hashlib.sha256(body.encode("utf-8")).hexdigest()
            conn.execute("INSERT INTO trial_declarations (session_id, path, body_json, hash, received_at) "
                         "VALUES (?,?,?,?,?)", (sid, declaration.get("path", ""), body, h, at))
            detail["declaration_hash"] = h
        for row in rows:
            mid = "mk_" + uuid.uuid4().hex[:12]
            conn.execute("INSERT INTO trial_marks (id, session_id, side, page, fx, fy, pen, topic, created_at, origin, "
                         "seq) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (mid, sid, "", 0, 0.0, 0.0, "", row["topic"], at, "row", int(row["seq"])))
        if rows:
            detail["rows_created"] = len(rows)
        # ค่าว่าง = คงค่าเดิม (SQL คงที่ · ค่า bind ทั้งหมด)
        conn.execute("UPDATE trial_sessions SET locked_at = ?, protocol = COALESCE(?, protocol), "
                     "path = COALESCE(?, path) WHERE id = ?", (at, protocol or None, path or None, sid))
        audit.record_in(conn, "trial_locked", "trial_session", sid, detail)
        out["at"] = at
    _tx(fn, db_path)
    return out["at"]


def declaration(sid: str, db_path=None) -> dict | None:
    rows = _rows("SELECT * FROM trial_declarations WHERE session_id = ?", (sid,), db_path)
    if not rows:
        return None
    d = rows[0]
    return {"body": json.loads(d["body_json"]), "hash": d["hash"], "received_at": d["received_at"], "path": d["path"]}


def attach_run(sid: str, project_id: str, run_id: str, db_path=None) -> bool:
    """ผูกรอบเทียบกับรอบตรวจ — ครั้งเดียวต่อรอบ (มีอยู่แล้ว = False ไม่ทับ) · เวลาปล่อยผล = ตอนผูกสำเร็จ"""
    out = {"ok": False}

    def fn(conn):
        n = conn.execute("UPDATE trial_sessions SET run_id = ?, project_id = ?, released_at = ?, run_error = '' "
                         "WHERE id = ? AND run_id = '' AND locked_at != ''",
                         (run_id, project_id, precise_now(), sid)).rowcount
        audit.record_in(conn, "trial_run_attached" if n else "trial_run_orphaned", "trial_session", sid,
                        {"run_id": run_id})
        out["ok"] = bool(n)
    _tx(fn, db_path)
    return out["ok"]


def run_failed(sid: str, message: str, db_path=None) -> None:
    def fn(conn):
        conn.execute("UPDATE trial_sessions SET run_error = ?, run_failures = run_failures + 1 WHERE id = ?",
                     (message[:300], sid))
        audit.record_in(conn, "trial_run_failed", "trial_session", sid, {"error": message[:300]})
    _tx(fn, db_path)


def set_status(sid: str, status: str, reason: str, no_data_use: bool = False, db_path=None) -> None:
    def fn(conn):
        r = _session_row(conn, sid)
        if r is None:
            raise ValueError("ไม่พบรอบตรวจ")
        if r["status"]:
            raise ValueError("รอบนี้หยุดหรือถอนตัวไปแล้ว")
        conn.execute("UPDATE trial_sessions SET status = ?, status_reason = ?, status_at = ?, no_data_use = ? "
                     "WHERE id = ?", (status, reason[:300], now_iso(), 1 if no_data_use else 0, sid))
        audit.record_in(conn, "trial_status_set", "trial_session", sid,
                        {"status": status, "no_data_use": bool(no_data_use), "has_reason": bool(reason)})
    _tx(fn, db_path)


def finish_use(sid: str, reason: str, complete: bool, snapshot: dict | None = None, db_path=None) -> None:
    """จบการใช้ผล — เก็บหลักฐานการกด + งานที่ทำถึงตอนนั้น (``snapshot``) ไม่ใช่หลักฐานว่าใช้ครบ"""
    def fn(conn):
        _need_open(conn, sid, unlocked=False)
        conn.execute("UPDATE trial_sessions SET use_done_at = ?, use_done_reason = ?, use_done_json = ? WHERE id = ?",
                     (now_iso(), reason[:300], json.dumps(snapshot or {}, ensure_ascii=False), sid))
        audit.record_in(conn, "trial_use_finished", "trial_session", sid, {"complete": complete,
                                                                          "has_reason": bool(reason),
                                                                          "snapshot": snapshot or {}})
    _tx(fn, db_path)


def give_consent(sid: str, db_path=None) -> None:
    """ความยินยอม (ติ๊ก ไม่ลงชื่อ) — ก่อนเริ่มทำรายการ/เก็บข้อมูลใด ๆ ในรอบ · กดซ้ำไม่เปลี่ยนเวลาเดิม"""
    def fn(conn):
        _need_open(conn, sid)
        r = _session_row(conn, sid)
        if r["consent_at"]:
            return
        conn.execute("UPDATE trial_sessions SET consent_at = ? WHERE id = ?", (precise_now(), sid))
        audit.record_in(conn, "trial_consent_given", "trial_session", sid, {"items": 3})
    _tx(fn, db_path)


# ── ประเด็น (จุดที่วง / แถวของรายการเดิม) ─────────────────────────────────────────
def add_mark(sid: str, side: str, page: int, fx: float, fy: float, pen: str, *, level: str = "", db_path=None) -> dict:
    mid = "mk_" + uuid.uuid4().hex[:12]
    rec = {"id": mid, "session_id": sid, "side": side, "page": int(page), "fx": float(fx), "fy": float(fy),
           "pen": pen, "topic": "", "note": "", "deleted": 0, "origin": "mark", "level": level, "cause": "",
           "part": "", "searched": "", "found_in": side if pen == "pin" else "", "seq": 0, "ref": ""}

    def fn(conn):
        _need_open(conn, sid)
        conn.execute("INSERT INTO trial_marks (id, session_id, side, page, fx, fy, pen, created_at, origin, level, "
                     "found_in) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (mid, sid, side, int(page), fx, fy, pen, now_iso(), "mark", level, rec["found_in"]))
        audit.record_in(conn, "trial_mark_added", "trial_mark", f"{sid}/{mid}",
                        {"side": side, "page": int(page), "fx": fx, "fy": fy, "pen": pen, "level": level})
    _tx(fn, db_path)
    return rec


def update_mark(sid: str, mid: str, *, after_lock: bool = False, db_path=None, **fields) -> None:
    """แก้ฟิลด์ของประเด็น — ก่อนล็อกเท่านั้น ยกเว้น ``after_lock=True`` (แถวของ ร1 ที่ผู้ตรวจกรอกลักษณะหลังล็อก ·
    ชั้นบริการคุมว่าแก้ได้เฉพาะแถว ร1 และไม่แก้หัวข้อ) · ตรวจสถานะซ้ำในธุรกรรม"""
    args, detail = [], {}
    for col in MARK_FIELDS:
        v = fields.get(col)
        args.append(None if v is None else int(v) if col in ("deleted", "page") else str(v)[:300])
        if v is not None:
            detail[col] = v

    def fn(conn):
        _need_open(conn, sid, unlocked=not after_lock)
        row = conn.execute("SELECT origin FROM trial_marks WHERE id = ? AND session_id = ?", (mid, sid)).fetchone()
        if row is None:
            raise ValueError("ไม่พบประเด็นที่ระบุ")
        if after_lock and row["origin"] != "row":
            raise ValueError("จุดที่วงล็อกแล้ว — แก้ไม่ได้")
        conn.execute(_UPDATE_MARK_SQL, (*args, mid, sid))
        audit.record_in(conn, "trial_mark_updated", "trial_mark", f"{sid}/{mid}", detail)
    if detail:
        _tx(fn, db_path)


def marks(sid: str, include_deleted: bool = False, db_path=None) -> list[dict]:
    q = "SELECT * FROM trial_marks WHERE session_id = ?" + ("" if include_deleted else " AND deleted = 0")
    return _rows(q + " ORDER BY created_at, rowid", (sid,), db_path)


def page_done(sid: str, side: str, page: int, db_path=None) -> None:
    def fn(conn):
        _need_open(conn, sid)
        conn.execute("INSERT OR IGNORE INTO trial_pages (session_id, side, page, done_at) VALUES (?,?,?,?)",
                     (sid, side, int(page), now_iso()))
        audit.record_in(conn, "trial_page_done", "trial_session", f"{sid}/page/{side}/{page}", {})
    _tx(fn, db_path)


def page_undone(sid: str, side: str, page: int, db_path=None) -> bool:
    """ยกเลิก "ตรวจหน้านี้แล้ว" — **ก่อนส่งผลเท่านั้น** (ตรวจซ้ำในธุรกรรม) · ไม่มีแถว = ไม่ทำอะไร (กดซ้ำได้) ·
    ลบแถว + Audit (เวลาที่เคยกดเดิม) ในธุรกรรมเดียวกัน · คืน True เมื่อยกเลิกจริง"""
    out = {"undone": False}

    def fn(conn):
        r = conn.execute("SELECT locked_at, status FROM trial_sessions WHERE id = ?", (sid,)).fetchone()
        if r is None or r["locked_at"] or r["status"]:
            raise ValueError("ส่งผลตรวจแล้ว — ยกเลิกหน้าที่ตรวจไม่ได้ (ผลเดิมเก็บไว้ตามเดิม)")
        row = conn.execute("SELECT done_at FROM trial_pages WHERE session_id = ? AND side = ? AND page = ?",
                           (sid, side, int(page))).fetchone()
        if row is None:
            return
        conn.execute("DELETE FROM trial_pages WHERE session_id = ? AND side = ? AND page = ?", (sid, side, int(page)))
        audit.record_in(conn, "trial_page_undone", "trial_session", f"{sid}/page/{side}/{page}",
                        {"side": side, "page": int(page), "done_at": row["done_at"]})
        out["undone"] = True
    _tx(fn, db_path)
    return out["undone"]


def log_view(sid: str, cur_page: int, prev_page: int, db_path=None) -> None:
    """บันทึกคู่หน้าที่เปิดเทียบ — คู่เดิมซ้ำติดกันไม่บันทึกซ้ำ"""
    def fn(conn):
        last = conn.execute("SELECT cur_page, prev_page FROM trial_views WHERE session_id = ? "
                            "ORDER BY rowid DESC LIMIT 1", (sid,)).fetchone()
        if last and (last["cur_page"], last["prev_page"]) == (int(cur_page), int(prev_page)):
            return
        conn.execute("INSERT INTO trial_views (session_id, cur_page, prev_page, viewed_at) VALUES (?,?,?,?)",
                     (sid, int(cur_page), int(prev_page), now_iso()))
        audit.record_in(conn, "trial_page_viewed", "trial_session", sid,
                        {"cur_page": int(cur_page), "prev_page": int(prev_page)})
    _tx(fn, db_path)


def views(sid: str, db_path=None) -> list[dict]:
    return _rows("SELECT cur_page, prev_page, viewed_at FROM trial_views WHERE session_id = ? ORDER BY rowid",
                 (sid,), db_path)


def pages_done(sid: str, db_path=None) -> set:
    return {(r["side"], r["page"]) for r in _rows("SELECT side, page FROM trial_pages WHERE session_id = ?",
                                                   (sid,), db_path)}


# ── จับคู่กับผลระบบ (หลังล็อก) ─────────────────────────────────────────────────
def save_proposals(sid: str, proposals: dict, db_path=None) -> None:
    """``proposals`` = {mark_id: finding_id หรือ ""} — บันทึกครั้งเดียวต่อรอบ (ข้อเสนอของระบบ ยังไม่ใช่คำตัดสิน)"""
    def fn(conn):
        for mid, fid in proposals.items():
            conn.execute("INSERT OR IGNORE INTO trial_proposals (session_id, mark_id, finding_id) VALUES (?,?,?)",
                         (sid, mid, fid))
        audit.record_in(conn, "trial_links_proposed", "trial_session", sid, {"proposals": proposals})
    _tx(fn, db_path)


def save_obs_class(sid: str, rows: list, db_path=None) -> bool:
    """การจัดประเภทข้อสังเกตเพื่อประเมิน (คู่กับข้อมูลเดิมของตัวเทียบ) — บันทึก**ครั้งเดียว**ต่อรอบตอนผูกรอบเทียบ ·
    ตรวจย้อนหลังได้ และไม่เปลี่ยนตามโค้ดรุ่นหลัง · มีอยู่แล้ว = ไม่ทับ (False)"""
    out = {"ok": False}

    def fn(conn):
        if conn.execute("SELECT 1 FROM trial_obs_class WHERE session_id = ? LIMIT 1", (sid,)).fetchone():
            return
        now = precise_now()
        for r in rows:
            conn.execute("INSERT INTO trial_obs_class (session_id, finding_id, topic, kind, info, level, reason, rule, "
                         "engine, saved_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (sid, r["finding_id"], r["topic"], r["kind"], 1 if r["info"] else 0, r["level"],
                          r.get("reason", ""), r.get("rule", ""), r.get("engine", ""), now))
        audit.record_in(conn, "trial_obs_classified", "trial_session", sid,
                        {"n": len(rows), "rule": rows[0].get("rule", "") if rows else "",
                         "engine": rows[0].get("engine", "") if rows else ""})
        out["ok"] = True
    _tx(fn, db_path)
    return out["ok"]


def obs_class(sid: str, db_path=None) -> dict:
    return {r["finding_id"]: {k: r[k] for k in ("topic", "kind", "info", "level", "reason", "rule", "engine")}
            for r in _rows("SELECT * FROM trial_obs_class WHERE session_id = ?", (sid,), db_path)}


def proposals(sid: str, db_path=None) -> dict:
    return {r["mark_id"]: r["finding_id"] for r in _rows("SELECT * FROM trial_proposals WHERE session_id = ?",
                                                         (sid,), db_path)}


def _issue_state(conn, sid: str, mid: str) -> dict | None:
    d = conn.execute("SELECT verdict, reason, evidence, basis, location, relevant_sides, search_scope "
                     "FROM trial_issue_decisions "
                     "WHERE session_id = ? AND mark_id = ?", (sid, mid)).fetchone()
    links_ = sorted(r["finding_id"] for r in conn.execute(
        "SELECT finding_id FROM trial_issue_links WHERE session_id = ? AND mark_id = ?", (sid, mid)).fetchall())
    if d is None and not links_:
        return None
    return {**(dict(d) if d else {}), "links": links_}


def decide_issue(sid: str, mid: str, decision: dict, links_: list, reason: str, db_path=None) -> None:
    """ผลการจับคู่ของประเด็น — แทนสถานะเดิมทั้งชุด (ผล · รหัสเหตุ · หลักฐาน · ฐาน · ชุดข้อสังเกต) +
    ประวัติ ก่อน → หลัง + เหตุผล ในธุรกรรมเดียวกัน"""
    def fn(conn):
        _need_open(conn, sid, unlocked=False)
        before = _issue_state(conn, sid, mid)
        at = now_iso()
        conn.execute("INSERT OR REPLACE INTO trial_issue_decisions (session_id, mark_id, verdict, reason, evidence, "
                     "basis, location, relevant_sides, search_scope, decided_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (sid, mid, decision["verdict"], decision.get("reason", ""), decision.get("evidence", ""),
                      decision.get("basis", ""), decision.get("location", ""), decision.get("relevant_sides", ""),
                      decision.get("search_scope", "")[:200], at))
        conn.execute("DELETE FROM trial_issue_links WHERE session_id = ? AND mark_id = ?", (sid, mid))
        for fid in dict.fromkeys(links_):
            conn.execute("INSERT INTO trial_issue_links (session_id, mark_id, finding_id, linked_at) VALUES (?,?,?,?)",
                         (sid, mid, fid, at))
        after = _issue_state(conn, sid, mid)
        conn.execute("INSERT INTO trial_history (session_id, target_kind, target_id, before_json, after_json, reason, "
                     "changed_at) VALUES (?,?,?,?,?,?,?)",
                     (sid, "issue", mid, json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False),
                      reason[:300], at))
        audit.record_in(conn, "trial_issue_decided", "trial_mark", f"{sid}/{mid}",
                        {"before": before, "after": after, "has_reason": bool(reason)})
    _tx(fn, db_path)


def issue_decisions(sid: str, db_path=None) -> dict:
    return {r["mark_id"]: {k: r[k] for k in ("verdict", "reason", "evidence", "basis", "location", "relevant_sides",
                                             "search_scope", "decided_at")}
            for r in _rows("SELECT * FROM trial_issue_decisions WHERE session_id = ?", (sid,), db_path)}


def _obs_state(conn, sid: str, fid: str) -> dict | None:
    r = conn.execute("SELECT fidelity, fidelity_reason, dims_json, assertion, basis FROM trial_obs_eval "
                     "WHERE session_id = ? AND finding_id = ?", (sid, fid)).fetchone()
    if r is None:
        return None
    d = dict(r)
    d["dims"] = json.loads(d.pop("dims_json") or "{}")
    return d


def decide_obs(sid: str, fid: str, ev: dict, reason: str, db_path=None) -> None:
    """A3-อ/A3-ข ของข้อสังเกตใน U (ฉบับ 0.3) — แทนค่าเดิมทั้งชุด + ประวัติ ในธุรกรรมเดียวกัน"""
    def fn(conn):
        _need_open(conn, sid, unlocked=False)
        before = _obs_state(conn, sid, fid)
        at = now_iso()
        conn.execute("INSERT OR REPLACE INTO trial_obs_eval (session_id, finding_id, fidelity, fidelity_reason, dims_json, "
                     "assertion, basis, decided_at) VALUES (?,?,?,?,?,?,?,?)",
                     (sid, fid, ev["fidelity"], ev.get("fidelity_reason", ""),
                      json.dumps(ev.get("dims", {}), ensure_ascii=False, sort_keys=True), ev["assertion"],
                      ev.get("basis", ""), at))
        after = _obs_state(conn, sid, fid)
        conn.execute("INSERT INTO trial_history (session_id, target_kind, target_id, before_json, after_json, reason, "
                     "changed_at) VALUES (?,?,?,?,?,?,?)",
                     (sid, "obs", fid, json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False),
                      reason[:300], at))
        audit.record_in(conn, "trial_obs_evaluated", "trial_finding", f"{sid}/{fid}",
                        {"before": before, "after": after, "has_reason": bool(reason)})
    _tx(fn, db_path)


def obs_evals(sid: str, db_path=None) -> dict:
    out = {}
    for r in _rows("SELECT * FROM trial_obs_eval WHERE session_id = ?", (sid,), db_path):
        out[r["finding_id"]] = {"fidelity": r["fidelity"], "fidelity_reason": r["fidelity_reason"],
                                "dims": json.loads(r["dims_json"] or "{}"), "assertion": r["assertion"],
                                "basis": r["basis"], "decided_at": r["decided_at"]}
    return out


def issue_links(sid: str, db_path=None) -> dict:
    out: dict = {}
    for r in _rows("SELECT mark_id, finding_id FROM trial_issue_links WHERE session_id = ? ORDER BY linked_at, rowid",
                   (sid,), db_path):
        out.setdefault(r["mark_id"], []).append(r["finding_id"])
    return out


def decide_finding(sid: str, fid: str, group: dict, reason: str, db_path=None) -> None:
    """กลุ่มของข้อสังเกตต้องตรวจที่ไม่ได้จับคู่ (ส1–ส4 / นอกส่วนที่ตรวจครบ) + ประวัติ ในธุรกรรมเดียวกัน"""
    def fn(conn):
        _need_open(conn, sid, unlocked=False)
        row = conn.execute("SELECT grp, s3_reason, basis, issue_ref, part, note FROM trial_finding_groups "
                           "WHERE session_id = ? AND finding_id = ?", (sid, fid)).fetchone()
        before = dict(row) if row else None
        at = now_iso()
        after = {k: group.get(k, "") for k in ("grp", "s3_reason", "basis", "issue_ref", "part", "note")}
        conn.execute("INSERT OR REPLACE INTO trial_finding_groups (session_id, finding_id, grp, s3_reason, basis, "
                     "issue_ref, part, note, decided_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (sid, fid, after["grp"], after["s3_reason"], after["basis"], after["issue_ref"], after["part"],
                      after["note"], at))
        conn.execute("INSERT INTO trial_history (session_id, target_kind, target_id, before_json, after_json, reason, "
                     "changed_at) VALUES (?,?,?,?,?,?,?)",
                     (sid, "finding", fid, json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False),
                      reason[:300], at))
        audit.record_in(conn, "trial_finding_grouped", "trial_session", f"{sid}/finding/{fid}",
                        {"before": before, "after": after, "has_reason": bool(reason)})
    _tx(fn, db_path)


def finding_groups(sid: str, db_path=None) -> dict:
    return {r["finding_id"]: {k: r[k] for k in ("grp", "s3_reason", "basis", "issue_ref", "part", "note", "decided_at")}
            for r in _rows("SELECT * FROM trial_finding_groups WHERE session_id = ?", (sid,), db_path)}


def history(sid: str, db_path=None) -> list[dict]:
    out = _rows("SELECT * FROM trial_history WHERE session_id = ? ORDER BY seq", (sid,), db_path)
    for d in out:
        d["before"], d["after"] = json.loads(d.pop("before_json")), json.loads(d.pop("after_json"))
    return out


def add_post_note(sid: str, part: str, topic: str, note: str, db_path=None) -> str:
    nid = "pn_" + uuid.uuid4().hex[:12]

    def fn(conn):
        _need_open(conn, sid, unlocked=False)
        conn.execute("INSERT INTO trial_post_notes (id, session_id, part, topic, note, created_at) VALUES (?,?,?,?,?,?)",
                     (nid, sid, part, topic, note[:300], now_iso()))
        audit.record_in(conn, "trial_post_note_added", "trial_session", f"{sid}/note/{nid}",
                        {"part": part, "topic": topic})
    _tx(fn, db_path)
    return nid


def post_notes(sid: str, db_path=None) -> list[dict]:
    return _rows("SELECT * FROM trial_post_notes WHERE session_id = ? ORDER BY created_at, rowid", (sid,), db_path)


# ── รอบกติกา 0.1 (อ่านอย่างเดียว) ─────────────────────────────────────────────────
def links(sid: str, db_path=None) -> dict:
    return {r["mark_id"]: r for r in _rows("SELECT * FROM trial_links WHERE session_id = ?", (sid,), db_path)}


def extras(sid: str, db_path=None) -> dict:
    return {r["finding_id"]: r["verdict"] for r in _rows("SELECT * FROM trial_extras WHERE session_id = ?",
                                                         (sid,), db_path)}


# ── แบบสอบถาม ────────────────────────────────────────────────────────────────
def answer(sid: str, values: dict, db_path=None) -> None:
    def fn(conn):
        _need_open(conn, sid, unlocked=False)
        for k, v in values.items():
            conn.execute("INSERT OR REPLACE INTO trial_answers (session_id, item, value, answered_at) "
                         "VALUES (?,?,?,?)", (sid, k, str(v)[:2000], now_iso()))
        audit.record_in(conn, "trial_answered", "trial_session", sid, {"items": sorted(values)})
    _tx(fn, db_path)


def answers(sid: str, db_path=None) -> dict:
    return {r["item"]: r["value"] for r in _rows("SELECT * FROM trial_answers WHERE session_id = ?", (sid,), db_path)}


__all__ = ["init_schema", "precise_now", "marks_hash", "create_session", "get_session", "sessions", "set_path", "lock",
           "declaration", "attach_run", "run_failed", "set_status", "finish_use", "give_consent", "add_mark", "update_mark", "marks",
           "page_done", "page_undone", "pages_done", "log_view", "views", "save_proposals", "proposals", "save_obs_class", "obs_class", "decide_obs", "obs_evals",
           "decide_issue", "issue_decisions", "issue_links", "decide_finding", "finding_groups", "history",
           "add_post_note", "post_notes", "links", "extras", "answer", "answers", "MARK_FIELDS"]
