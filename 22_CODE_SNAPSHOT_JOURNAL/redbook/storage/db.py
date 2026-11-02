# -*- coding: utf-8 -*-
"""ชั้นฐานข้อมูล SQLite — local-first ไฟล์เดียว ไม่มีบริการภายนอก

หมายเหตุการออกแบบ:
  - ตาราง audit_log ถูกล็อกด้วย trigger ไม่ให้ UPDATE/DELETE ได้จากทุกเส้นทาง
  - ทุก run เก็บเวอร์ชัน engine/rule-set/parser + config hash เพื่อให้ตรวจซ้ำได้
  - findings มี finding_key ที่คำนวณจากเนื้อหา ไม่ใช่ลำดับการรัน
    ทำให้รันซ้ำแล้วผูกคำตัดสินของมนุษย์กลับเข้ากับประเด็นเดิมได้
"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .. import config

SCHEMA_VERSION = 1

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    mode        TEXT NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL,
    created_by  TEXT,
    status      TEXT NOT NULL DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS files (
    id                    TEXT PRIMARY KEY,
    project_id            TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    side                  TEXT NOT NULL,
    original_name         TEXT NOT NULL,
    stored_name           TEXT NOT NULL,
    kind                  TEXT NOT NULL,
    size_bytes            INTEGER NOT NULL,
    sha256                TEXT NOT NULL,
    uploaded_at           TEXT NOT NULL,
    declared_fiscal_year  INTEGER,
    declared_agency_code  TEXT,
    declared_agency_name  TEXT,
    declared_doc_kind     TEXT,
    UNIQUE (project_id, side)
);

CREATE TABLE IF NOT EXISTS runs (
    id                       TEXT PRIMARY KEY,
    project_id               TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    mode                     TEXT NOT NULL,
    file_a_id                TEXT REFERENCES files(id),
    file_b_id                TEXT REFERENCES files(id),
    ref_file_id              TEXT REFERENCES files(id),
    engine_version           TEXT NOT NULL,
    rule_set_version         TEXT NOT NULL,
    canonical_model_version  TEXT NOT NULL,
    parser_versions_json     TEXT NOT NULL DEFAULT '{}',
    config_json              TEXT NOT NULL DEFAULT '{}',
    config_hash              TEXT NOT NULL DEFAULT '',
    started_at               TEXT NOT NULL,
    finished_at              TEXT,
    duration_ms              INTEGER,
    status                   TEXT NOT NULL DEFAULT 'running',
    items_checked            INTEGER NOT NULL DEFAULT 0,
    result_hash              TEXT
);

CREATE TABLE IF NOT EXISTS run_rules (
    run_id       TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    rule_id      TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    enabled      INTEGER NOT NULL DEFAULT 1,
    params_json  TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (run_id, rule_id)
);

CREATE TABLE IF NOT EXISTS findings (
    id                 TEXT PRIMARY KEY,
    run_id             TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    finding_code       TEXT NOT NULL,
    finding_key        TEXT NOT NULL,
    check_type         TEXT NOT NULL,
    severity           TEXT NOT NULL,
    rule_id            TEXT NOT NULL,
    rule_version       TEXT NOT NULL,
    reason             TEXT NOT NULL,
    value_a            TEXT,
    value_b            TEXT,
    diff_value         REAL,
    diff_pct           REAL,
    unit               TEXT,
    loc_a_json         TEXT NOT NULL DEFAULT '{}',
    loc_b_json         TEXT NOT NULL DEFAULT '{}',
    machine_status     TEXT NOT NULL,
    presentation_only  INTEGER NOT NULL DEFAULT 0,
    confidence         REAL,
    confidence_basis   TEXT,
    review_status      TEXT NOT NULL DEFAULT 'pending',
    reviewed_by        TEXT,
    reviewed_at        TEXT,
    review_note        TEXT,
    evidence_json      TEXT NOT NULL DEFAULT '{}',
    sort_key           TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_findings_run ON findings(run_id);
CREATE INDEX IF NOT EXISTS idx_findings_key ON findings(finding_key);
CREATE INDEX IF NOT EXISTS idx_findings_review ON findings(run_id, review_status);

CREATE TABLE IF NOT EXISTS item_matches (
    id             TEXT PRIMARY KEY,
    run_id         TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    match_level    TEXT NOT NULL,
    score          REAL,
    score_basis    TEXT,
    a_ref_json     TEXT NOT NULL DEFAULT '{}',
    b_ref_json     TEXT NOT NULL DEFAULT '{}',
    confirmed_by   TEXT,
    confirmed_at   TEXT,
    confirm_result TEXT
);
CREATE INDEX IF NOT EXISTS idx_matches_run ON item_matches(run_id);

CREATE TABLE IF NOT EXISTS audit_log (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    actor        TEXT NOT NULL,
    action       TEXT NOT NULL,
    object_type  TEXT NOT NULL,
    object_id    TEXT NOT NULL,
    detail_json  TEXT NOT NULL DEFAULT '{}',
    prev_hash    TEXT NOT NULL,
    entry_hash   TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;

CREATE TABLE IF NOT EXISTS security_events (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    event       TEXT NOT NULL,
    severity    TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    client      TEXT
);
"""


def connect(db_path=None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        row = conn.execute(
            "SELECT version FROM schema_migrations WHERE version = ?",
            (SCHEMA_VERSION,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) "
                "VALUES (?, datetime('now'))", (SCHEMA_VERSION,))
    finally:
        conn.close()


@contextmanager
def session(db_path=None):
    conn = connect(db_path)
    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


def jdump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def jload(text):
    if not text:
        return {}
    return json.loads(text)
