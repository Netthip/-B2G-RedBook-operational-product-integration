# -*- coding: utf-8 -*-
"""ที่เก็บรอบ "ทดลองตรวจเล่ม" ของผู้ตรวจ (#43) — ตารางแยก เพิ่มอย่างเดียว ไม่แตะตารางเดิม

* ``trial_sessions``  หนึ่งแถวต่อการตรวจหนึ่งเล่มของผู้ตรวจหนึ่งคน · ``locked_at`` = ส่งผลตรวจแล้ว (แก้จุดที่วงไม่ได้)
  · ``run_id`` = รอบเทียบของระบบที่สร้าง **หลังล็อกเท่านั้น** (ผู้ตรวจไม่เห็นผลระบบก่อนวงเสร็จ)
* ``trial_marks``     จุดที่ผู้ตรวจวงบนภาพหน้า — ปากกา (แดง · น้ำตาล · หมุดของหาย) · ตำแหน่งเป็นสัดส่วนของหน้า (0–1) ·
  หัวข้อ (รหัส ก–ญ ตามโปรโตคอล) · หมายเหตุสั้น · ลบ = ทำเครื่องหมาย ``deleted`` (ไม่ลบแถว)
* ``trial_pages``     หน้าที่ผู้ตรวจกด "ตรวจหน้านี้แล้ว"
* ``trial_views``     คู่หน้าที่เปิดเทียบระหว่างตรวจ (ฉบับปัจจุบันหน้า X ↔ ฉบับก่อนหน้า Y · 0 = ไม่ได้เปิดฉบับก่อน)
* ``trial_links``     จุดที่วง ↔ ข้อสังเกตของระบบ + คำตัดสินของผู้ตรวจ (พบตรง · พบบางส่วน · ไม่ใช่จุดเดียวกัน)
* ``trial_extras``    ข้อสังเกตของระบบที่ไม่มีจุดวงคู่ + คำตัดสิน (ต่างจริงแต่ไม่ได้จด · ไม่ใช่ความต่าง · ยังตัดสินไม่ได้)
* ``trial_answers``   แบบสอบถามหลังใช้ (ข้อ → ค่า)

ทุกการเปลี่ยนแปลงลง Audit ในธุรกรรมเดียวกัน
"""
from __future__ import annotations

import json
import uuid

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
"""


def init_schema(db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA)
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


# ── รอบตรวจ ─────────────────────────────────────────────────────────────────
def create_session(book_id: str, reviewer: str, book: dict, db_path=None) -> str:
    sid = "tr_" + uuid.uuid4().hex[:16]

    def fn(conn):
        conn.execute("INSERT INTO trial_sessions (id, book_id, reviewer, book_json, started_at) VALUES (?,?,?,?,?)",
                     (sid, book_id, reviewer[:40], json.dumps(book, ensure_ascii=False), now_iso()))
        audit.record_in(conn, "trial_started", "trial_session", sid, {"book_id": book_id, "book": book})
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


def lock(sid: str, counts: dict, require_pages=None, db_path=None) -> None:
    """``require_pages`` = หน้าของฉบับปัจจุบันที่ต้องกด "ตรวจหน้านี้แล้ว" ครบ — ตรวจซ้ำในธุรกรรมเดียวกับการล็อก
    (กันกด "ยกเลิก" แทรกระหว่างที่ชั้นบริการตรวจกับตอนล็อก)"""
    def fn(conn):
        r = conn.execute("SELECT locked_at FROM trial_sessions WHERE id = ?", (sid,)).fetchone()
        if r is None or r["locked_at"]:
            raise ValueError("รอบนี้ส่งผลตรวจไปแล้ว")
        if require_pages is not None:
            done = {x["page"] for x in conn.execute("SELECT page FROM trial_pages WHERE session_id = ? AND side = 'cur'",
                                                    (sid,)).fetchall()}
            missing = [p for p in require_pages if int(p) not in done]
            if missing:
                raise ValueError(f"ยังไม่ได้กด \"ตรวจหน้านี้แล้ว\" อีก {len(missing)} หน้า")
        conn.execute("UPDATE trial_sessions SET locked_at = ? WHERE id = ?", (now_iso(), sid))
        audit.record_in(conn, "trial_locked", "trial_session", sid, counts)
    _tx(fn, db_path)


def attach_run(sid: str, project_id: str, run_id: str, db_path=None) -> None:
    def fn(conn):
        conn.execute("UPDATE trial_sessions SET run_id = ?, project_id = ? WHERE id = ? AND run_id = ''",
                     (run_id, project_id, sid))
        audit.record_in(conn, "trial_run_attached", "trial_session", sid, {"run_id": run_id})
    _tx(fn, db_path)


# ── จุดที่วง ────────────────────────────────────────────────────────────────
def add_mark(sid: str, side: str, page: int, fx: float, fy: float, pen: str, db_path=None) -> dict:
    mid = "mk_" + uuid.uuid4().hex[:12]
    rec = {"id": mid, "session_id": sid, "side": side, "page": int(page), "fx": float(fx), "fy": float(fy),
           "pen": pen, "topic": "", "note": "", "deleted": 0}

    def fn(conn):
        conn.execute("INSERT INTO trial_marks (id, session_id, side, page, fx, fy, pen, created_at) "
                     "VALUES (?,?,?,?,?,?,?,?)", (mid, sid, side, int(page), fx, fy, pen, now_iso()))
        audit.record_in(conn, "trial_mark_added", "trial_mark", f"{sid}/{mid}",
                        {"side": side, "page": int(page), "fx": fx, "fy": fy, "pen": pen})
    _tx(fn, db_path)
    return rec


def update_mark(sid: str, mid: str, *, topic=None, note=None, pen=None, deleted=None, db_path=None) -> None:
    sets, args, detail = [], [], {}
    for col, v in (("topic", topic), ("note", note), ("pen", pen), ("deleted", deleted)):
        if v is not None:
            sets.append(f"{col} = ?")
            args.append(int(v) if col == "deleted" else str(v)[:300])
            detail[col] = v

    def fn(conn):
        n = conn.execute(f"UPDATE trial_marks SET {', '.join(sets)} WHERE id = ? AND session_id = ?",
                         (*args, mid, sid)).rowcount
        if not n:
            raise ValueError("ไม่พบจุดที่ระบุ")
        audit.record_in(conn, "trial_mark_updated", "trial_mark", f"{sid}/{mid}", detail)
    if sets:
        _tx(fn, db_path)


def marks(sid: str, include_deleted: bool = False, db_path=None) -> list[dict]:
    q = "SELECT * FROM trial_marks WHERE session_id = ?" + ("" if include_deleted else " AND deleted = 0")
    return _rows(q + " ORDER BY created_at", (sid,), db_path)


def page_done(sid: str, side: str, page: int, db_path=None) -> None:
    def fn(conn):
        conn.execute("INSERT OR IGNORE INTO trial_pages (session_id, side, page, done_at) VALUES (?,?,?,?)",
                     (sid, side, int(page), now_iso()))
        audit.record_in(conn, "trial_page_done", "trial_session", f"{sid}/page/{side}/{page}", {})
    _tx(fn, db_path)


def page_undone(sid: str, side: str, page: int, db_path=None) -> bool:
    """ยกเลิก "ตรวจหน้านี้แล้ว" — **ก่อนส่งผลเท่านั้น** (ตรวจซ้ำในธุรกรรม) · ไม่มีแถว = ไม่ทำอะไร (กดซ้ำได้) ·
    ลบแถว + Audit (เวลาที่เคยกดเดิม) ในธุรกรรมเดียวกัน · คืน True เมื่อยกเลิกจริง"""
    out = {"undone": False}

    def fn(conn):
        r = conn.execute("SELECT locked_at FROM trial_sessions WHERE id = ?", (sid,)).fetchone()
        if r is None or r["locked_at"]:
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
def propose_links(sid: str, proposals: dict, db_path=None) -> None:
    """``proposals`` = {mark_id: finding_id หรือ ""} — บันทึกครั้งเดียวต่อรอบ (ข้อเสนอของระบบ ยังไม่ใช่คำตัดสิน)"""
    def fn(conn):
        for mid, fid in proposals.items():
            conn.execute("INSERT OR IGNORE INTO trial_links (session_id, mark_id, finding_id, proposed) "
                         "VALUES (?,?,?,1)", (sid, mid, fid))
        audit.record_in(conn, "trial_links_proposed", "trial_session", sid, {"proposals": proposals})
    _tx(fn, db_path)


def decide_link(sid: str, mid: str, finding_id: str, verdict: str, db_path=None) -> None:
    def fn(conn):
        prev = conn.execute("SELECT finding_id, verdict FROM trial_links WHERE session_id = ? AND mark_id = ?",
                            (sid, mid)).fetchone()
        conn.execute("INSERT OR REPLACE INTO trial_links (session_id, mark_id, finding_id, proposed, verdict, "
                     "decided_at) VALUES (?,?,?,?,?,?)",
                     (sid, mid, finding_id, 0 if prev is None else 1, verdict, now_iso()))
        audit.record_in(conn, "trial_link_decided", "trial_mark", f"{sid}/{mid}",
                        {"finding_id": finding_id, "verdict": verdict, "previous": dict(prev) if prev else None})
    _tx(fn, db_path)


def links(sid: str, db_path=None) -> dict:
    return {r["mark_id"]: r for r in _rows("SELECT * FROM trial_links WHERE session_id = ?", (sid,), db_path)}


def decide_extra(sid: str, fid: str, verdict: str, db_path=None) -> None:
    def fn(conn):
        conn.execute("INSERT OR REPLACE INTO trial_extras (session_id, finding_id, verdict, decided_at) "
                     "VALUES (?,?,?,?)", (sid, fid, verdict, now_iso()))
        audit.record_in(conn, "trial_extra_decided", "trial_session", f"{sid}/extra/{fid}", {"verdict": verdict})
    _tx(fn, db_path)


def extras(sid: str, db_path=None) -> dict:
    return {r["finding_id"]: r["verdict"] for r in _rows("SELECT * FROM trial_extras WHERE session_id = ?",
                                                         (sid,), db_path)}


def answer(sid: str, values: dict, db_path=None) -> None:
    def fn(conn):
        for k, v in values.items():
            conn.execute("INSERT OR REPLACE INTO trial_answers (session_id, item, value, answered_at) "
                         "VALUES (?,?,?,?)", (sid, k, str(v)[:2000], now_iso()))
        audit.record_in(conn, "trial_answered", "trial_session", sid, {"items": sorted(values)})
    _tx(fn, db_path)


def answers(sid: str, db_path=None) -> dict:
    return {r["item"]: r["value"] for r in _rows("SELECT * FROM trial_answers WHERE session_id = ?", (sid,), db_path)}


__all__ = ["init_schema", "create_session", "get_session", "sessions", "lock", "attach_run", "add_mark",
           "update_mark", "marks", "page_done", "pages_done", "log_view", "views", "propose_links", "decide_link", "links",
           "decide_extra", "extras", "answer", "answers"]
