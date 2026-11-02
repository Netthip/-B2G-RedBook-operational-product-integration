# -*- coding: utf-8 -*-
"""ที่เก็บทะเบียนตัวชี้วัด — ข้อสังเกตและคู่ที่เสนอ **แก้ไม่ได้** · คำตัดสิน **เพิ่มอย่างเดียว**

ตาราง (ขึ้นต้น ``ind_`` ให้เห็นว่าเป็นคนละสายกับ T1A/T1B)

* ``ind_runs`` — หนึ่งรอบ = เอกสารเก่าหนึ่ง + ใหม่หนึ่ง + รุ่นตัวสกัด/กติกา + แฮชกติกา
* ``ind_observations`` — *immutable source observations* (trigger กัน UPDATE/DELETE)
* ``ind_mappings`` — คู่ที่เครื่องเสนอ (immutable) · ``internal_score`` อยู่ที่นี่
  และ **ไม่ถูกส่งออก** ผ่าน view ของหน้าตรวจเฉลย
* ``ind_decisions`` — คำตัดสินของผู้ตรวจ (append-only · ผูก audit) —
  สถานะปัจจุบัน = คำตัดสินล่าสุด ไม่มีคอลัมน์สถานะที่เขียนทับได้
* ``ind_canonical_ids`` — **ตรึง (pin)** canonical id ครั้งแรกที่ component เกิด (append-only)
  ⇒ id ที่เผยแพร่ไปแล้วไม่เปลี่ยนเมื่อ component โตขึ้นหรือรวมกัน (B1)
* ``ind_identity_aliases`` — id เดิมที่ถูกรวมเข้ากับ id หลัก (append-only) ⇒ ไม่มี id ตายกลางทาง

🔴 **B2 — binding เป็นผลที่ *คำนวณจากคำตัดสินล่าสุด* ไม่ใช่แถวที่เขียนสะสม**
(Bo `5595832792` B2) · ตาราง ``ind_bindings`` เดิมถูกลดบทบาทเป็น *ประวัติ* เท่านั้น
ผู้อ่านทุกคนต้องเรียก :func:`effective_bindings` / :func:`indicator_ids` ซึ่ง derive จาก
``ind_decisions`` ล่าสุดเสมอ ⇒ ยอมรับ ``SAME_*`` แล้วภายหลังแก้เป็นอย่างอื่น **binding สิ้นผลทันที**

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from ..evidence import documents as edocs
from ..storage import audit
from ..storage.db import connect
from . import identity as idn
from . import keyuniverse as ku
from . import mapping as mp
from . import sourceinventory as si
from .observe import Observation

REGISTRY_VERSION = "indicator-registry-0.2.0"

#: 1 = schema แรก (Pass 1) · 2 = B1/B2 — canonical identity pin + observation identity key
#: 3 = B4 (Pass 3) — จักรวาลของเฉลยที่เป็นกลาง + คำตอบรายรายการ + snapshot ของ detector
#: 4 = P3-2 (Pass 4) — ทะเบียนข้อสังเกต **อิสระ** ที่ไม่ได้มาจากรอบของ detector
#: 5 = Pass 5 — จำนวนหน้าระดับรอบ · ผนึกเครื่องครอบข้อสังเกต+metadata · manifest ไฟล์ส่งออก
IND_SCHEMA_VERSION = 5

# ── คำตัดสินของผู้ตรวจ ───────────────────────────────────────────────────────
DECISION_ACCEPT = "ACCEPT"        # รับสถานะที่เสนอ (หรือระบุสถานะสุดท้ายเอง)
DECISION_REJECT = "REJECT"        # ไม่รับ — ต้องระบุสถานะสุดท้ายที่ถูกต้อง
DECISION_AMBIGUOUS = "AMBIGUOUS"  # ยังตัดสินไม่ได้ — คงเป็น AMBIGUOUS_REVIEW_REQUIRED
DECISIONS = (DECISION_ACCEPT, DECISION_REJECT, DECISION_AMBIGUOUS)
DECISION_LABELS = {
    DECISION_ACCEPT: "ยอมรับ",
    DECISION_REJECT: "ไม่ยอมรับ (ระบุสถานะที่ถูกต้อง)",
    DECISION_AMBIGUOUS: "ยังตัดสินไม่ได้",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ind_runs (
    id                  TEXT PRIMARY KEY,
    created_at          TEXT NOT NULL,
    old_document_id     TEXT NOT NULL,
    new_document_id     TEXT NOT NULL,
    extractor_version   TEXT NOT NULL,
    normalize_version   TEXT NOT NULL,
    mapping_version     TEXT NOT NULL,
    rules_json          TEXT NOT NULL,
    rules_hash          TEXT NOT NULL,
    text_backend        TEXT NOT NULL,
    n_old               INTEGER NOT NULL,
    n_new               INTEGER NOT NULL,
    n_pairs             INTEGER NOT NULL,
    accounted_json      TEXT NOT NULL,
    page_inventory_json TEXT NOT NULL DEFAULT '{}',
    note                TEXT NOT NULL DEFAULT '',
    label               TEXT NOT NULL DEFAULT '',
    -- v4: แฮชเนื้อเอกสารเต็มของทั้งสองฝั่ง (ทะเบียนอิสระผูกกับค่านี้)
    old_document_sha256 TEXT NOT NULL DEFAULT '',
    new_document_sha256 TEXT NOT NULL DEFAULT '',
    -- v5: จำนวนหน้าจริงของเอกสารทั้งสองฝั่ง
    old_page_count      INTEGER NOT NULL DEFAULT 0,
    new_page_count      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ind_observations (
    observation_id      TEXT NOT NULL,
    run_id              TEXT NOT NULL REFERENCES ind_runs(id),
    side                TEXT NOT NULL,
    document_id         TEXT NOT NULL,
    page                INTEGER NOT NULL,
    line_index          INTEGER NOT NULL,
    observed_text       TEXT NOT NULL,
    normalized_text     TEXT NOT NULL,
    x0 REAL NOT NULL, y0 REAL NOT NULL, x1 REAL NOT NULL, y1 REAL NOT NULL,
    page_width          REAL NOT NULL,
    page_height         REAL NOT NULL,
    location_confidence TEXT NOT NULL,
    unit                TEXT NOT NULL DEFAULT '',
    target_text         TEXT NOT NULL DEFAULT '',
    target_value        TEXT NOT NULL DEFAULT '',
    baseline_text       TEXT NOT NULL DEFAULT '',
    method_text         TEXT NOT NULL DEFAULT '',
    period_text         TEXT NOT NULL DEFAULT '',
    ordinal             TEXT NOT NULL DEFAULT '',
    cues_json           TEXT NOT NULL DEFAULT '[]',
    source_sha256       TEXT NOT NULL,
    extractor_version   TEXT NOT NULL,
    -- B1: สมอที่คงที่ข้าม run · identity_key = sha256(full_doc_hash|page|anchor|text)
    anchor              TEXT NOT NULL DEFAULT '',
    identity_key        TEXT NOT NULL DEFAULT '',
    -- P1-2/H2: ธงเชิงเรขาคณิต/ที่มา
    geometry_flags_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (run_id, observation_id)
);
CREATE TRIGGER IF NOT EXISTS ind_observations_no_update
BEFORE UPDATE ON ind_observations
BEGIN SELECT RAISE(ABORT, 'ind_observations is immutable'); END;
CREATE TRIGGER IF NOT EXISTS ind_observations_no_delete
BEFORE DELETE ON ind_observations
BEGIN SELECT RAISE(ABORT, 'ind_observations is immutable'); END;

CREATE TABLE IF NOT EXISTS ind_mappings (
    mapping_id          TEXT NOT NULL,
    run_id              TEXT NOT NULL REFERENCES ind_runs(id),
    old_observation_id  TEXT NOT NULL DEFAULT '',
    new_observation_id  TEXT NOT NULL DEFAULT '',
    proposed_status     TEXT NOT NULL,
    human_required      INTEGER NOT NULL,
    basis_json          TEXT NOT NULL DEFAULT '[]',
    differences_json    TEXT NOT NULL DEFAULT '[]',
    alternatives_json   TEXT NOT NULL DEFAULT '[]',
    -- 🔴 คะแนนภายในของเครื่อง — ห้ามส่งออกไปหน้าตรวจเฉลย
    internal_score      REAL NOT NULL,
    PRIMARY KEY (run_id, mapping_id)
);
CREATE TRIGGER IF NOT EXISTS ind_mappings_no_update
BEFORE UPDATE ON ind_mappings
BEGIN SELECT RAISE(ABORT, 'ind_mappings is immutable'); END;
CREATE TRIGGER IF NOT EXISTS ind_mappings_no_delete
BEFORE DELETE ON ind_mappings
BEGIN SELECT RAISE(ABORT, 'ind_mappings is immutable'); END;

CREATE TABLE IF NOT EXISTS ind_decisions (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    mapping_id      TEXT NOT NULL,
    decision        TEXT NOT NULL,
    final_status    TEXT NOT NULL,
    reason          TEXT NOT NULL DEFAULT '',
    reviewer        TEXT NOT NULL,
    decided_at      TEXT NOT NULL,
    audit_seq       INTEGER NOT NULL,
    audit_entry_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS ind_decisions_no_update
BEFORE UPDATE ON ind_decisions
BEGIN SELECT RAISE(ABORT, 'ind_decisions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_decisions_no_delete
BEFORE DELETE ON ind_decisions
BEGIN SELECT RAISE(ABORT, 'ind_decisions is append-only'); END;

CREATE TABLE IF NOT EXISTS ind_bindings (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    indicator_id    TEXT NOT NULL,
    observation_id  TEXT NOT NULL,
    via_mapping_id  TEXT NOT NULL,
    decision_seq    INTEGER NOT NULL,
    bound_at        TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS ind_bindings_no_update
BEFORE UPDATE ON ind_bindings
BEGIN SELECT RAISE(ABORT, 'ind_bindings is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_bindings_no_delete
BEFORE DELETE ON ind_bindings
BEGIN SELECT RAISE(ABORT, 'ind_bindings is append-only'); END;

-- B1 · canonical id ที่ถูกตรึง — ผูกกับ *root_key* ของ component ไม่ผูกกับ run
CREATE TABLE IF NOT EXISTS ind_canonical_ids (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_id    TEXT NOT NULL,
    root_key        TEXT NOT NULL UNIQUE,
    established_at  TEXT NOT NULL,
    established_run TEXT NOT NULL DEFAULT '',
    identity_version TEXT NOT NULL DEFAULT ''
);
CREATE TRIGGER IF NOT EXISTS ind_canonical_ids_no_update
BEFORE UPDATE ON ind_canonical_ids
BEGIN SELECT RAISE(ABORT, 'ind_canonical_ids is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_canonical_ids_no_delete
BEFORE DELETE ON ind_canonical_ids
BEGIN SELECT RAISE(ABORT, 'ind_canonical_ids is append-only'); END;

-- B1 · id เดิมที่ถูกรวมเข้ากับ id หลัก — เปิดกลับได้เสมอ ไม่มี id ตายกลางทาง
CREATE TABLE IF NOT EXISTS ind_identity_aliases (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    alias_id       TEXT NOT NULL,
    canonical_id   TEXT NOT NULL,
    merged_at      TEXT NOT NULL,
    merged_run     TEXT NOT NULL DEFAULT ''
);
CREATE TRIGGER IF NOT EXISTS ind_identity_aliases_no_update
BEFORE UPDATE ON ind_identity_aliases
BEGIN SELECT RAISE(ABORT, 'ind_identity_aliases is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_identity_aliases_no_delete
BEFORE DELETE ON ind_identity_aliases
BEGIN SELECT RAISE(ABORT, 'ind_identity_aliases is append-only'); END;

-- B4 · ขั้น KEY BUILD/VERIFY — **แยกจาก** ind_decisions ซึ่งเป็น POST-RUN ADJUDICATION
-- 🔴 แถวในตารางนี้ต้องถูกกรอกโดยไม่เห็นผลของ detector (หน้า keybuild ไม่ส่ง proposed status)
CREATE TABLE IF NOT EXISTS ind_key_entries (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    mapping_id      TEXT NOT NULL,
    key_status      TEXT NOT NULL,
    reason          TEXT NOT NULL DEFAULT '',
    entered_by      TEXT NOT NULL,
    entered_at      TEXT NOT NULL,
    audit_seq       INTEGER NOT NULL,
    audit_entry_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS ind_key_entries_no_update
BEFORE UPDATE ON ind_key_entries
BEGIN SELECT RAISE(ABORT, 'ind_key_entries is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_key_entries_no_delete
BEFORE DELETE ON ind_key_entries
BEGIN SELECT RAISE(ABORT, 'ind_key_entries is append-only'); END;

-- B4 · การผนึกเฉลย — ปลดล็อกขั้น adjudication · append-only
CREATE TABLE IF NOT EXISTS ind_key_seals (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    sealed_at       TEXT NOT NULL,
    sealed_by       TEXT NOT NULL,
    entries_count   INTEGER NOT NULL,
    key_digest      TEXT NOT NULL,
    note            TEXT NOT NULL DEFAULT '',
    audit_seq       INTEGER NOT NULL,
    audit_entry_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS ind_key_seals_no_update
BEFORE UPDATE ON ind_key_seals
BEGIN SELECT RAISE(ABORT, 'ind_key_seals is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_key_seals_no_delete
BEFORE DELETE ON ind_key_seals
BEGIN SELECT RAISE(ABORT, 'ind_key_seals is append-only'); END;

-- ── B4 (PASS 3) · จักรวาลของเฉลย — สร้างจาก **ข้อสังเกตล้วน** ไม่ใช่จากคู่ของ detector
-- 🔴 Bo (`5600162467`) — "must not use rv.pairs, detector mapping_id, detector candidate
-- cardinality, or detector ordering" ⇒ ตารางนี้ไม่มีคอลัมน์ใดที่มาจาก detector เลย
CREATE TABLE IF NOT EXISTS ind_key_universe (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    item_id         TEXT NOT NULL,
    side            TEXT NOT NULL,
    observation_id  TEXT NOT NULL,
    identity_key    TEXT NOT NULL,
    document_sha256 TEXT NOT NULL,
    page            INTEGER NOT NULL,
    anchor          TEXT NOT NULL DEFAULT '',
    text_sha256     TEXT NOT NULL,
    built_at        TEXT NOT NULL,
    UNIQUE(run_id, item_id)
);
CREATE TRIGGER IF NOT EXISTS ind_key_universe_no_update
BEFORE UPDATE ON ind_key_universe
BEGIN SELECT RAISE(ABORT, 'ind_key_universe is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_key_universe_no_delete
BEFORE DELETE ON ind_key_universe
BEGIN SELECT RAISE(ABORT, 'ind_key_universe is append-only'); END;

-- การตรึงจักรวาล — ต้องเกิด **ก่อน** บันทึกคำตอบของเฉลยเสมอ
CREATE TABLE IF NOT EXISTS ind_key_universe_seals (
    seq              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL UNIQUE,
    frozen_at        TEXT NOT NULL,
    frozen_by        TEXT NOT NULL,
    item_count       INTEGER NOT NULL,
    universe_digest  TEXT NOT NULL,
    protocol_version TEXT NOT NULL DEFAULT '',
    audit_seq        INTEGER NOT NULL,
    audit_entry_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS ind_key_universe_seals_no_update
BEFORE UPDATE ON ind_key_universe_seals
BEGIN SELECT RAISE(ABORT, 'ind_key_universe_seals is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_key_universe_seals_no_delete
BEFORE DELETE ON ind_key_universe_seals
BEGIN SELECT RAISE(ABORT, 'ind_key_universe_seals is append-only'); END;

-- คำตอบของเฉลย — ผูกกับ **รายการในจักรวาล** ไม่ใช่กับ mapping ของ detector
CREATE TABLE IF NOT EXISTS ind_key_answers (
    seq                 INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT NOT NULL,
    item_id             TEXT NOT NULL,
    key_status          TEXT NOT NULL,
    counterpart_item_id TEXT NOT NULL DEFAULT '',
    reason              TEXT NOT NULL DEFAULT '',
    entered_by          TEXT NOT NULL,
    entered_at          TEXT NOT NULL,
    audit_seq           INTEGER NOT NULL,
    audit_entry_hash    TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS ind_key_answers_no_update
BEFORE UPDATE ON ind_key_answers
BEGIN SELECT RAISE(ABORT, 'ind_key_answers is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_key_answers_no_delete
BEFORE DELETE ON ind_key_answers
BEGIN SELECT RAISE(ABORT, 'ind_key_answers is append-only'); END;

-- การผนึก **ผลลัพธ์ของ detector** — artifact คนละชิ้นกับเฉลย
CREATE TABLE IF NOT EXISTS ind_detector_snapshots (
    seq              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL UNIQUE,
    sealed_at        TEXT NOT NULL,
    sealed_by        TEXT NOT NULL,
    pair_count       INTEGER NOT NULL,
    snapshot_digest  TEXT NOT NULL,
    rules_hash       TEXT NOT NULL DEFAULT '',
    note             TEXT NOT NULL DEFAULT '',
    audit_seq        INTEGER NOT NULL,
    audit_entry_hash TEXT NOT NULL,
    -- v5 (P4-3): พิธีการ + ส่วนประกอบของผนึก
    snapshot_protocol   TEXT NOT NULL DEFAULT '',
    observation_count   INTEGER NOT NULL DEFAULT -1,
    mappings_digest     TEXT NOT NULL DEFAULT '',
    observations_digest TEXT NOT NULL DEFAULT '',
    metadata_digest     TEXT NOT NULL DEFAULT '',
    documents_digest    TEXT NOT NULL DEFAULT ''
);
CREATE TRIGGER IF NOT EXISTS ind_detector_snapshots_no_update
BEFORE UPDATE ON ind_detector_snapshots
BEGIN SELECT RAISE(ABORT, 'ind_detector_snapshots is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_detector_snapshots_no_delete
BEFORE DELETE ON ind_detector_snapshots
BEGIN SELECT RAISE(ABORT, 'ind_detector_snapshots is append-only'); END;

-- ── P3-2 (PASS 4) · ทะเบียนข้อสังเกต **อิสระ** — คนอ่านเอกสารแล้วกรอกเอง
-- 🔴 Bo (`5605652708`) — จักรวาลที่สร้างจาก ind_observations ยังพึ่งการ *สกัด* ของเครื่อง
-- ตัวชี้วัดที่เครื่องสกัดไม่เจอต้องยังอยู่ในเฉลยและถูกนับเป็น miss ได้
CREATE TABLE IF NOT EXISTS ind_source_inventory (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    identity_key    TEXT NOT NULL,
    side            TEXT NOT NULL,
    document_sha256 TEXT NOT NULL,
    page            INTEGER NOT NULL,
    occurrence      INTEGER NOT NULL DEFAULT 1,
    hint            TEXT NOT NULL DEFAULT '',
    anchor          TEXT NOT NULL,
    observed_text   TEXT NOT NULL,
    normalized_text TEXT NOT NULL DEFAULT '',
    entered_by      TEXT NOT NULL,
    entered_at      TEXT NOT NULL,
    audit_seq       INTEGER NOT NULL,
    audit_entry_hash TEXT NOT NULL,
    UNIQUE(run_id, identity_key)
);
CREATE TRIGGER IF NOT EXISTS ind_source_inventory_no_update
BEFORE UPDATE ON ind_source_inventory
BEGIN SELECT RAISE(ABORT, 'ind_source_inventory is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_source_inventory_no_delete
BEFORE DELETE ON ind_source_inventory
BEGIN SELECT RAISE(ABORT, 'ind_source_inventory is append-only'); END;

-- ถอนรายการที่กรอกผิด — ก่อนตรึงเท่านั้น · แถวเดิมยังอยู่ในประวัติ
CREATE TABLE IF NOT EXISTS ind_source_inventory_retractions (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    identity_key    TEXT NOT NULL,
    retracted_by    TEXT NOT NULL,
    retracted_at    TEXT NOT NULL,
    reason          TEXT NOT NULL DEFAULT '',
    audit_seq       INTEGER NOT NULL,
    audit_entry_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS ind_source_inventory_retractions_no_update
BEFORE UPDATE ON ind_source_inventory_retractions
BEGIN SELECT RAISE(ABORT, 'ind_source_inventory_retractions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_source_inventory_retractions_no_delete
BEFORE DELETE ON ind_source_inventory_retractions
BEGIN SELECT RAISE(ABORT, 'ind_source_inventory_retractions is append-only'); END;

-- ── P4-2 (PASS 5) · ไฟล์ส่งออกทุกไฟล์ผูกกับรอบและ digest ของผนึกสามชั้น ณ ตอนสร้าง
-- ดาวน์โหลดได้ก็ต่อเมื่อ **ตรวจผนึกใหม่ผ่าน** และ digest ปัจจุบันยังตรงกับที่บันทึกไว้
CREATE TABLE IF NOT EXISTS ind_export_manifests (
    seq              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name        TEXT NOT NULL UNIQUE,
    package_id       TEXT NOT NULL,
    run_id           TEXT NOT NULL,
    file_sha256      TEXT NOT NULL,
    universe_digest  TEXT NOT NULL,
    key_digest       TEXT NOT NULL,
    detector_digest  TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    audit_seq        INTEGER NOT NULL,
    audit_entry_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS ind_export_manifests_no_update
BEFORE UPDATE ON ind_export_manifests
BEGIN SELECT RAISE(ABORT, 'ind_export_manifests is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ind_export_manifests_no_delete
BEFORE DELETE ON ind_export_manifests
BEGIN SELECT RAISE(ABORT, 'ind_export_manifests is append-only'); END;

CREATE TABLE IF NOT EXISTS ind_schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""

#: คอลัมน์ที่เพิ่มใน schema v2/v4 — ใช้ migrate ฐานข้อมูลเดิมโดยไม่ทำลายข้อมูล
#:
#: 🔴 v4 — แฮชเนื้อเอกสาร **เต็ม** ของทั้งสองฝั่งถูกบันทึกไว้ตั้งแต่ตอนสร้างรอบ
#: เพื่อให้ทะเบียนข้อสังเกตอิสระผูกกับเอกสารได้โดย **ไม่ต้องอ่าน** ``ind_observations``
#: แถวเก่าที่ไม่มีค่านี้จะกรอกทะเบียนอิสระไม่ได้ และระบบจะบอกเหตุผลตรง ๆ (ไม่เดาให้)
_V2_COLUMNS = (
    ("ind_observations", "anchor", "TEXT NOT NULL DEFAULT ''"),
    ("ind_observations", "identity_key", "TEXT NOT NULL DEFAULT ''"),
    ("ind_observations", "geometry_flags_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("ind_runs", "old_document_sha256", "TEXT NOT NULL DEFAULT ''"),
    ("ind_runs", "new_document_sha256", "TEXT NOT NULL DEFAULT ''"),
    # v5 — จำนวนหน้าจริงของเอกสาร (ใช้ตรวจเลขหน้าในทะเบียนอิสระ · P4-4)
    ("ind_runs", "old_page_count", "INTEGER NOT NULL DEFAULT 0"),
    ("ind_runs", "new_page_count", "INTEGER NOT NULL DEFAULT 0"),
    # v5 — ผนึกเครื่องแยกส่วนประกอบ เพื่อบอกได้ว่า *ส่วนไหน* ไม่ตรง (P4-3)
    ("ind_detector_snapshots", "snapshot_protocol", "TEXT NOT NULL DEFAULT ''"),
    ("ind_detector_snapshots", "observation_count", "INTEGER NOT NULL DEFAULT -1"),
    ("ind_detector_snapshots", "mappings_digest", "TEXT NOT NULL DEFAULT ''"),
    ("ind_detector_snapshots", "observations_digest", "TEXT NOT NULL DEFAULT ''"),
    ("ind_detector_snapshots", "metadata_digest", "TEXT NOT NULL DEFAULT ''"),
    # v5 / Pass 6 — บริบทเอกสาร (P5-2)
    ("ind_detector_snapshots", "documents_digest", "TEXT NOT NULL DEFAULT ''"),
)


def init_schema(db_path=None) -> None:
    """สร้าง/อัปเกรด schema — **migration แบบเพิ่มคอลัมน์** ไม่ลบข้อมูลเดิม

    ฐานข้อมูลที่สร้างด้วย schema v1 (ก่อน B1/B2) จะได้คอลัมน์ ``anchor`` /
    ``identity_key`` / ``geometry_flags_json`` เป็นค่าว่าง — แถวเก่าเหล่านั้นจึง
    **ไม่มี canonical identity** และถูกรายงานเป็นรหัสชั่วคราวตามเดิม (ไม่เดาให้)
    """
    # 🔴 v4 — ทะเบียนตัวชี้วัดอ่านแฮชเนื้อเอกสารจากทะเบียนเอกสาร จึงต้องมั่นใจว่า
    # schema ฝั่งนั้นถูกสร้างแล้ว มิฉะนั้นฐานข้อมูลใหม่จะล้มด้วย "no such table"
    edocs.init_schema(db_path)
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        existing = {row["name"] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for table, column, decl in _V2_COLUMNS:
            if table not in existing:
                continue
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        # 🔴 index ต้องสร้าง **หลัง** migration เสมอ — ฐานข้อมูล v1 ยังไม่มีคอลัมน์นี้
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ind_obs_identity "
                     "ON ind_observations(identity_key)")
        conn.execute("INSERT OR IGNORE INTO ind_schema_version (version, applied_at) "
                     "VALUES (?, ?)", (IND_SCHEMA_VERSION, _now()))
    finally:
        conn.close()


def schema_version(db_path=None) -> int:
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT MAX(version) AS v FROM ind_schema_version").fetchone()
        return int(row["v"] or 0)
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def provisional_indicator_id(identity_key: str) -> str:
    """รหัส **ชั่วคราว** ของข้อสังเกตที่ยังไม่มีคำตัดสินผูกเข้าตัวชี้วัดใด

    🔴 B1 — ประกาศตัวเองว่าชั่วคราวในตัวรหัส (``PROVISIONAL-…``) ห้ามเรียกว่า canonical
    และห้ามใช้อ้างอิงข้ามรอบ · เดิมใช้คำนำหน้า ``IND-`` เหมือน canonical จึงแยกไม่ออก
    """
    return idn.provisional_id_for(identity_key)


# ── เขียนรอบ ───────────────────────────────────────────────────────────────

def _document_sha256(document_id: str, obs: list, db_path=None) -> str:
    """แฮชเนื้อเอกสาร **เต็ม** ของฉบับหนึ่ง — ทะเบียนเอกสารเป็นแหล่งอ้างอิงหลัก

    🔴 แฮชนี้เป็นสมบัติของ *ตัวไฟล์* ไม่ใช่ผลของ detector · ใช้ค่าจากทะเบียนเอกสารก่อน
    (ที่นั่นคำนวณจากไบต์ของไฟล์ตอนขึ้นทะเบียน) · ถ้าเอกสารยังไม่อยู่ในทะเบียน
    (เกิดได้เฉพาะในชุดทดสอบที่ประกอบข้อสังเกตขึ้นเอง) จึงถอยไปใช้ค่าที่ติดมากับข้อสังเกต
    """
    rec = edocs.get(document_id, db_path)
    if rec is not None and len(rec.content_sha256 or "") == si.FULL_DIGEST_LEN:
        return rec.content_sha256
    for o in obs:
        if len(getattr(o, "source_sha256", "") or "") == si.FULL_DIGEST_LEN:
            return o.source_sha256
    return ""


def _document_page_count(document_id: str, explicit: int | None, db_path=None) -> int:
    """จำนวนหน้าจริงของเอกสาร — ทะเบียนเอกสารเป็นแหล่งหลัก (นับจากไฟล์ตอนขึ้นทะเบียน)

    🔴 ไม่อนุมานจากหน้าสุดท้ายที่เครื่องสกัดได้ เพราะหน้าที่เครื่องไม่เห็นอะไรเลยคือ
    ที่ที่ตัวชี้วัดตกหล่นซ่อนอยู่ · ไม่ทราบ ⇒ ``0`` แล้วทะเบียนอิสระจะปฏิเสธแบบเห็นชัด
    """
    rec = edocs.get(document_id, db_path)
    if rec is not None and rec.page_count and int(rec.page_count) > 0:
        return int(rec.page_count)
    if explicit is not None and int(explicit) > 0:
        return int(explicit)
    return 0


def save_run(*, run_id: str, old_document_id: str, new_document_id: str,
             old_obs: list[Observation], new_obs: list[Observation],
             candidates: list[mp.Candidate], rules: mp.Rules,
             extractor_version: str, normalize_version: str, text_backend: str,
             accounted: dict, page_inventory: dict, note: str = "",
             label: str = "", old_page_count: int | None = None,
             new_page_count: int | None = None, db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        old_sha = _document_sha256(old_document_id, old_obs, db_path)
        new_sha = _document_sha256(new_document_id, new_obs, db_path)
        old_pages = _document_page_count(old_document_id, old_page_count, db_path)
        new_pages = _document_page_count(new_document_id, new_page_count, db_path)
        conn.execute(
            "INSERT INTO ind_runs (id, created_at, old_document_id, new_document_id, "
            "extractor_version, normalize_version, mapping_version, rules_json, "
            "rules_hash, text_backend, n_old, n_new, n_pairs, accounted_json, "
            "page_inventory_json, note, label, old_document_sha256, "
            "new_document_sha256, old_page_count, new_page_count) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, _now(), old_document_id, new_document_id, extractor_version,
             normalize_version, rules.version, rules.as_json(), rules.rules_hash,
             text_backend, len(old_obs), len(new_obs), len(candidates),
             json.dumps(accounted, ensure_ascii=False),
             json.dumps(page_inventory, ensure_ascii=False), note, label,
             old_sha, new_sha, old_pages, new_pages))
        for side, obs in (("old", old_obs), ("new", new_obs)):
            for o in obs:
                conn.execute(
                    "INSERT INTO ind_observations (observation_id, run_id, side, "
                    "document_id, page, line_index, observed_text, normalized_text, "
                    "x0, y0, x1, y1, page_width, page_height, location_confidence, "
                    "unit, target_text, target_value, baseline_text, method_text, "
                    "period_text, ordinal, cues_json, source_sha256, extractor_version, "
                    "anchor, identity_key, geometry_flags_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (o.observation_id, run_id, side, o.document_id, o.page,
                     o.line_index, o.observed_text, o.normalized_text, o.x0, o.y0,
                     o.x1, o.y1, o.page_width, o.page_height, o.location_confidence,
                     o.unit, o.target_text, o.target_value, o.baseline_text,
                     o.method_text, o.period_text, o.ordinal,
                     json.dumps(list(o.cues), ensure_ascii=False), o.source_sha256,
                     o.extractor_version, o.anchor, o.identity_key,
                     json.dumps(list(o.geometry_flags), ensure_ascii=False)))
        for c in candidates:
            conn.execute(
                "INSERT INTO ind_mappings (mapping_id, run_id, old_observation_id, "
                "new_observation_id, proposed_status, human_required, basis_json, "
                "differences_json, alternatives_json, internal_score) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (c.mapping_id, run_id, c.old_observation_id, c.new_observation_id,
                 c.proposed_status, int(c.human_required),
                 json.dumps(list(c.basis), ensure_ascii=False),
                 json.dumps([d.__dict__ for d in c.differences], ensure_ascii=False),
                 json.dumps(list(c.alternatives), ensure_ascii=False),
                 c.internal_score))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


# ── อ่าน ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RunRow:
    id: str
    created_at: str
    old_document_id: str
    new_document_id: str
    extractor_version: str
    normalize_version: str
    mapping_version: str
    rules_json: str
    rules_hash: str
    text_backend: str
    n_old: int
    n_new: int
    n_pairs: int
    accounted: dict
    page_inventory: dict
    note: str
    label: str
    old_document_sha256: str = ""
    new_document_sha256: str = ""
    old_page_count: int = 0
    new_page_count: int = 0
    rules_json_raw: str = ""
    page_inventory_json: str = ""


def get_run(run_id: str, db_path=None) -> RunRow | None:
    conn = connect(db_path)
    try:
        r = conn.execute("SELECT * FROM ind_runs WHERE id = ?", (run_id,)).fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    return RunRow(id=r["id"], created_at=r["created_at"],
                  old_document_id=r["old_document_id"],
                  new_document_id=r["new_document_id"],
                  extractor_version=r["extractor_version"],
                  normalize_version=r["normalize_version"],
                  mapping_version=r["mapping_version"], rules_json=r["rules_json"],
                  rules_hash=r["rules_hash"], text_backend=r["text_backend"],
                  n_old=r["n_old"], n_new=r["n_new"], n_pairs=r["n_pairs"],
                  accounted=json.loads(r["accounted_json"]),
                  page_inventory=json.loads(r["page_inventory_json"] or "{}"),
                  note=r["note"], label=r["label"],
                  old_document_sha256=(r["old_document_sha256"]
                                       if "old_document_sha256" in r.keys() else ""),
                  new_document_sha256=(r["new_document_sha256"]
                                       if "new_document_sha256" in r.keys() else ""),
                  old_page_count=(r["old_page_count"] if "old_page_count" in r.keys() else 0),
                  new_page_count=(r["new_page_count"] if "new_page_count" in r.keys() else 0),
                  rules_json_raw=r["rules_json"] or "",
                  page_inventory_json=r["page_inventory_json"] or "")


def list_runs(db_path=None) -> list[RunRow]:
    conn = connect(db_path)
    try:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM ind_runs ORDER BY created_at DESC, id").fetchall()]
    finally:
        conn.close()
    return [x for x in (get_run(i, db_path) for i in ids) if x]


def observations(run_id: str, db_path=None) -> dict[str, Observation]:
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM ind_observations WHERE run_id = ? "
                            "ORDER BY side, page, line_index", (run_id,)).fetchall()
    finally:
        conn.close()
    out: dict[str, Observation] = {}
    for r in rows:
        out[r["observation_id"]] = Observation(
            observation_id=r["observation_id"], document_id=r["document_id"],
            page=r["page"], line_index=r["line_index"],
            observed_text=r["observed_text"], normalized_text=r["normalized_text"],
            x0=r["x0"], y0=r["y0"], x1=r["x1"], y1=r["y1"],
            page_width=r["page_width"], page_height=r["page_height"],
            location_confidence=r["location_confidence"], unit=r["unit"],
            target_text=r["target_text"], target_value=r["target_value"],
            baseline_text=r["baseline_text"], method_text=r["method_text"],
            period_text=r["period_text"], ordinal=r["ordinal"],
            cues=tuple(json.loads(r["cues_json"])), source_sha256=r["source_sha256"],
            anchor=(r["anchor"] if "anchor" in r.keys() else ""),
            geometry_flags=tuple(json.loads(
                r["geometry_flags_json"] if "geometry_flags_json" in r.keys() else "[]")),
            extractor_version=r["extractor_version"], extra={"side": r["side"]})
    return out


def mappings(run_id: str, *, with_internal_score: bool = False,
             db_path=None) -> list[mp.Candidate]:
    """คู่ที่เครื่องเสนอ — ค่าเริ่มต้น **ไม่คืนคะแนนภายใน** (ใส่ ``0.0`` แทน)

    🔴 ค่าเริ่มต้นเข้าข้างความปลอดภัย: ผู้เรียกที่ต้องการคะแนนจริง (เช่น
    สคริปต์ของผู้พัฒนา) ต้องขอด้วย ``with_internal_score=True`` อย่างชัดเจน
    """
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM ind_mappings WHERE run_id = ? "
                            "ORDER BY mapping_id", (run_id,)).fetchall()
    finally:
        conn.close()
    out: list[mp.Candidate] = []
    for r in rows:
        out.append(mp.Candidate(
            mapping_id=r["mapping_id"], old_observation_id=r["old_observation_id"],
            new_observation_id=r["new_observation_id"],
            proposed_status=r["proposed_status"],
            human_required=bool(r["human_required"]),
            basis=tuple(json.loads(r["basis_json"])),
            differences=tuple(mp.Difference(**d) for d in json.loads(r["differences_json"])),
            internal_score=(float(r["internal_score"]) if with_internal_score else 0.0),
            alternatives=tuple(json.loads(r["alternatives_json"]))))
    return out


# ── คำตัดสิน ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DecisionRow:
    seq: int
    run_id: str
    mapping_id: str
    decision: str
    final_status: str
    reason: str
    reviewer: str
    decided_at: str
    audit_seq: int
    audit_entry_hash: str

    @property
    def decision_label(self) -> str:
        return DECISION_LABELS.get(self.decision, self.decision)


class DecisionError(ValueError):
    pass


def record_decision(*, run_id: str, mapping_id: str, decision: str,
                    final_status: str, reason: str, reviewer: str,
                    db_path=None) -> DecisionRow:
    """บันทึกคำตัดสินหนึ่งแถว + audit ในธุรกรรมเดียว + ผูก indicator_id ถ้าเป็น SAME_*

    กติกา (มีเทสต์)
    * ``reviewer`` ว่างไม่ได้ — คำตัดสินต้องมีเจ้าของ
    * ``REJECT`` ต้องระบุ ``final_status`` ที่ถูกต้อง และต้องต่างจากที่เสนอ
    * ``AMBIGUOUS`` ⇒ ``final_status`` = ``AMBIGUOUS_REVIEW_REQUIRED`` เสมอ
    * สถานะสุดท้ายในตระกูล ``HUMAN_REQUIRED`` **ต้องมีเหตุผล**
    """
    if decision not in DECISIONS:
        raise DecisionError("คำตัดสินไม่รู้จัก")
    if not reviewer.strip():
        raise DecisionError("ต้องระบุชื่อผู้ตรวจ")
    # 🔴 B4 — คำตัดสินหลังรัน (adjudication) ต้องเกิด **หลัง** เฉลยถูกผนึกเท่านั้น
    # มิฉะนั้นผู้ตัดสินจะเห็นสิ่งที่ detector เสนอก่อนเฉลยถูกตรึง = เฉลยถูกชี้นำ
    if not adjudication_unlocked(run_id, db_path):
        raise DecisionError(
            "ยังเปิดขั้นตัดสินหลังรันไม่ได้ — เฉลยของรอบนี้ยังไม่ถูกผนึก "
            "(ขั้น KEY BUILD/VERIFY ต้องเสร็จและผนึกก่อน)")
    conn = connect(db_path)
    try:
        m = conn.execute("SELECT * FROM ind_mappings WHERE run_id = ? AND mapping_id = ?",
                         (run_id, mapping_id)).fetchone()
        if m is None:
            raise DecisionError("ไม่พบคู่ที่ระบุ")
        proposed = m["proposed_status"]
        if decision == DECISION_ACCEPT:
            final = final_status or proposed
        elif decision == DECISION_REJECT:
            final = final_status
            if not final:
                raise DecisionError("ไม่ยอมรับต้องระบุสถานะที่ถูกต้อง")
            if final == proposed:
                raise DecisionError("สถานะที่ระบุเท่ากับที่เสนอ — ให้ใช้ 'ยอมรับ' แทน")
        else:
            final = mp.AMBIGUOUS_REVIEW_REQUIRED
        if final not in mp.STATUSES:
            raise DecisionError("สถานะสุดท้ายไม่รู้จัก")
        if final in mp.HUMAN_REQUIRED and not reason.strip():
            raise DecisionError("สถานะนี้ต้องมีเหตุผลประกอบ")
        now = _now()
        conn.execute("BEGIN IMMEDIATE")
        entry = audit.record_in(conn, "indicator_mapping_decided", "ind_mapping",
                                mapping_id, {
                                    "run_id": run_id, "decision": decision,
                                    "proposed_status": proposed,
                                    "final_status": final, "reviewer": reviewer,
                                    "registry_version": REGISTRY_VERSION},
                                actor=reviewer)
        cur = conn.execute(
            "INSERT INTO ind_decisions (run_id, mapping_id, decision, final_status, "
            "reason, reviewer, decided_at, audit_seq, audit_entry_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (run_id, mapping_id, decision, final, reason, reviewer, now,
             entry["seq"], entry["entry_hash"]))
        seq = int(cur.lastrowid)
        # 🔴 B2 — **ไม่เขียน binding ตรงนี้อีกแล้ว** · binding ที่มีผลคำนวณจากคำตัดสิน
        # ล่าสุดเสมอ (:func:`effective_bindings`) มิฉะนั้นการแก้คำตัดสินภายหลังจะไม่ถอน
        # binding เดิม และแถวที่เขียนสะสมไว้จะกลายเป็น "last row wins" ที่ Bo ทักไว้
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:      # noqa: BLE001
            pass
        raise
    finally:
        conn.close()
    return DecisionRow(seq=seq, run_id=run_id, mapping_id=mapping_id,
                       decision=decision, final_status=final, reason=reason,
                       reviewer=reviewer, decided_at=now, audit_seq=entry["seq"],
                       audit_entry_hash=entry["entry_hash"])


def decisions(run_id: str, db_path=None) -> list[DecisionRow]:
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM ind_decisions WHERE run_id = ? ORDER BY seq",
                            (run_id,)).fetchall()
    finally:
        conn.close()
    return [DecisionRow(seq=r["seq"], run_id=r["run_id"], mapping_id=r["mapping_id"],
                        decision=r["decision"], final_status=r["final_status"],
                        reason=r["reason"], reviewer=r["reviewer"],
                        decided_at=r["decided_at"], audit_seq=r["audit_seq"],
                        audit_entry_hash=r["audit_entry_hash"]) for r in rows]


def latest_decisions(run_id: str, db_path=None) -> dict[str, DecisionRow]:
    out: dict[str, DecisionRow] = {}
    for d in decisions(run_id, db_path):
        out[d.mapping_id] = d          # ลำดับ seq ⇒ ตัวหลังทับตัวหน้า = ล่าสุด
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  B1 / B2 — ตัวตนที่คำนวณจากคำตัดสินล่าสุด
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class IdentityView:
    """ผลการคำนวณตัวตนของหนึ่งรอบ (หรือหลายรอบ) — **derived เสมอ ไม่ใช่แถวที่เขียนไว้**"""
    #: observation_id → indicator_id (canonical เมื่อผูกแล้ว · ``PROVISIONAL-…`` เมื่อยังไม่ผูก)
    ids: dict
    #: observation_id → identity_key (สมอที่คงที่ข้าม run)
    keys: dict
    #: component ที่ผูกได้ (root_key → canonical_id)
    canonical_by_root: dict
    #: ข้อขัดแย้งที่ต้องให้คนตัดสิน — **ไม่ผูก** จนกว่าจะแก้
    conflicts: tuple
    #: id เดิมที่ถูกรวมเข้ากับ id หลัก (alias → canonical)
    aliases: dict

    def is_canonical(self, observation_id: str) -> bool:
        return idn.is_canonical(self.ids.get(observation_id, ""))


def _identity_keys(run_ids, db_path=None) -> tuple[dict, dict]:
    """observation_id → identity_key และ identity_key → observation_id (ของ run ที่ระบุ)"""
    conn = connect(db_path)
    try:
        placeholders = ",".join("?" for _ in run_ids)
        rows = conn.execute(
            f"SELECT run_id, observation_id, identity_key FROM ind_observations "
            f"WHERE run_id IN ({placeholders})", tuple(run_ids)).fetchall()
    finally:
        conn.close()
    by_obs = {r["observation_id"]: (r["identity_key"] or "") for r in rows}
    by_key: dict[str, list[str]] = {}
    for r in rows:
        if r["identity_key"]:
            by_key.setdefault(r["identity_key"], []).append(r["observation_id"])
    return by_obs, by_key


def confirmed_same_edges(run_ids, db_path=None) -> list:
    """edge ที่ **คนยืนยันล่าสุด** ว่าเป็นตัวชี้วัดเดียวกัน — input ของการคำนวณตัวตน

    ใช้ ``final_status`` ของคำตัดสิน **ล่าสุด** ต่อ mapping เท่านั้น ⇒ ถ้าภายหลังแก้เป็น
    non-SAME edge นั้นหายไปเอง (B2)
    """
    edges = []
    keys, _ = _identity_keys(run_ids, db_path)
    conn = connect(db_path)
    try:
        for run_id in run_ids:
            latest = latest_decisions(run_id, db_path)
            if not latest:
                continue
            rows = conn.execute(
                "SELECT mapping_id, old_observation_id, new_observation_id "
                "FROM ind_mappings WHERE run_id = ?", (run_id,)).fetchall()
            pairs = {r["mapping_id"]: (r["old_observation_id"], r["new_observation_id"])
                     for r in rows}
            for mapping_id, d in sorted(latest.items()):
                if d.final_status not in mp.SAME_FAMILY:
                    continue
                old_obs, new_obs = pairs.get(mapping_id, ("", ""))
                ko, kn = keys.get(old_obs, ""), keys.get(new_obs, "")
                if not ko or not kn:
                    # แถวจาก schema เก่าที่ไม่มี identity_key ⇒ ผูกข้าม run ไม่ได้ (ไม่เดา)
                    continue
                edges.append(idn.Edge(old_key=ko, new_key=kn, mapping_id=mapping_id,
                                      decision_seq=d.seq, run_id=run_id))
    finally:
        conn.close()
    return edges


def _pinned_ids(db_path=None) -> tuple[dict, dict, dict]:
    """root_key → canonical_id · alias → canonical · root_key → ``seq`` ที่ตรึงจริง

    🔴 **Bo (`5600162467` B1)** — ค่าที่สามคือลำดับ **เวลา** ที่แถวถูกตรึง
    ถ้าไม่ส่งค่านี้ต่อไปให้ :func:`identity.pick_canonical` การเลือก id หลักจะกลาย
    เป็นการเรียงตามตัวอักษรของ ``root_key`` ซึ่ง **ไม่ใช่** กติกาที่ประกาศไว้
    """
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT seq, canonical_id, root_key FROM ind_canonical_ids "
                            "ORDER BY seq").fetchall()
        arows = conn.execute("SELECT alias_id, canonical_id FROM ind_identity_aliases "
                             "ORDER BY seq").fetchall()
    finally:
        conn.close()
    return ({r["root_key"]: r["canonical_id"] for r in rows},
            {r["alias_id"]: r["canonical_id"] for r in arows},
            {r["root_key"]: int(r["seq"]) for r in rows})


def _pin(canonical_id: str, root_key: str, run_id: str, db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT OR IGNORE INTO ind_canonical_ids (canonical_id, root_key, "
                     "established_at, established_run, identity_version) VALUES (?,?,?,?,?)",
                     (canonical_id, root_key, _now(), run_id, idn.IDENTITY_VERSION))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def _record_alias(alias_id: str, canonical_id: str, run_id: str, db_path=None) -> None:
    if alias_id == canonical_id:
        return
    conn = connect(db_path)
    try:
        exists = conn.execute("SELECT 1 FROM ind_identity_aliases WHERE alias_id = ? "
                              "AND canonical_id = ?", (alias_id, canonical_id)).fetchone()
        if exists:
            return
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO ind_identity_aliases (alias_id, canonical_id, merged_at, "
                     "merged_run) VALUES (?,?,?,?)", (alias_id, canonical_id, _now(), run_id))
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:      # noqa: BLE001
            pass
        raise
    finally:
        conn.close()


def resolve_identity(run_id: str, *, scope_runs=None, db_path=None) -> IdentityView:
    """คำนวณตัวตนของข้อสังเกตใน ``run_id`` — canonical เมื่อมีคำตัดสินผูก · มิฉะนั้นชั่วคราว

    ``scope_runs`` = รอบทั้งหมดที่นำคำตัดสินมาประกอบ (ค่าปริยาย = **ทุกรอบ**) ⇒ ตัวชี้วัด
    ที่ถูกยืนยันในรอบก่อนยังคง id เดิมเมื่อโผล่ในรอบใหม่ (B1 — คงที่ข้าม run/เอกสาร/ปี)
    """
    all_runs = [r.id for r in list_runs(db_path)] if scope_runs is None else list(scope_runs)
    if run_id not in all_runs:
        all_runs = list(all_runs) + [run_id]
    edges = confirmed_same_edges(all_runs, db_path)
    res = idn.resolve(edges)

    pinned_roots, aliases, pin_order = _pinned_ids(db_path)
    # pinned ต่อ *สมาชิก*: สมาชิกที่เคยเป็น root ของ component เดิม
    pinned_members = dict(pinned_roots)
    canonical_by_root: dict[str, str] = {}
    for comp in res.components:
        # 🔴 B1 — ส่ง **ลำดับเวลาที่ตรึงจริง** เข้าไป มิฉะนั้นจะได้ id ตามลำดับตัวอักษร
        canonical, extra = idn.pick_canonical(comp, pinned_members, pin_order)
        if comp.root_key not in pinned_roots:
            _pin(canonical, comp.root_key, run_id, db_path)
        for alias in extra:
            _record_alias(alias, canonical, run_id, db_path)
        canonical_by_root[comp.root_key] = canonical

    keys, _ = _identity_keys([run_id], db_path)
    ids: dict[str, str] = {}
    for obs_id in observations(run_id, db_path):
        key = keys.get(obs_id, "")
        root = res.member_root.get(key) if key else None
        if root and root in canonical_by_root:
            ids[obs_id] = canonical_by_root[root]
        elif key:
            ids[obs_id] = provisional_indicator_id(key)
        else:
            # schema เก่าไม่มี identity_key ⇒ ยังคงเป็นรหัสชั่วคราวจาก observation_id
            ids[obs_id] = idn.provisional_id_for(obs_id)
    _, aliases, _ = _pinned_ids(db_path)
    return IdentityView(ids=ids, keys=keys, canonical_by_root=canonical_by_root,
                        conflicts=res.conflicts, aliases=aliases)


def indicator_ids(run_id: str, db_path=None) -> dict[str, str]:
    """observation_id → indicator_id — **derived จากคำตัดสินล่าสุด** (B1/B2)

    canonical (``IND-…``) เมื่อคนยืนยัน ``SAME_*`` แล้ว · มิฉะนั้น ``PROVISIONAL-…``
    """
    return resolve_identity(run_id, db_path=db_path).ids


def identity_conflicts(run_id: str, db_path=None) -> tuple:
    """ข้อขัดแย้งเรื่องตัวตนที่ต้องให้คนตัดสิน — ``one-to-many`` ที่ถูกยืนยันในรอบเดียวกัน"""
    return resolve_identity(run_id, db_path=db_path).conflicts


def effective_bindings(run_id: str, db_path=None) -> dict:
    """canonical_id → รายชื่อ observation_id ที่ถูกผูกอยู่ **ตามคำตัดสินล่าสุด**"""
    view = resolve_identity(run_id, db_path=db_path)
    out: dict[str, list[str]] = {}
    for obs_id, ind_id in sorted(view.ids.items()):
        if idn.is_canonical(ind_id):
            out.setdefault(ind_id, []).append(obs_id)
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  B4 — KEY BUILD / VERIFY (แยกจาก POST-RUN ADJUDICATION)
# ══════════════════════════════════════════════════════════════════════════════
#
# 🔴 Bo (`5595832792` B4) — Gate 4 เดิมให้ผู้ตรวจเห็น *สถานะที่ detector เสนอ* ระหว่าง
# "ยืนยันเฉลย" ซึ่งทำให้เฉลยถูกชี้นำ · จึงต้องแยกเป็นสอง artifact
#
#   KEY BUILD / VERIFY      → ``ind_key_entries`` · หน้า ``/keybuild`` **ไม่มี** proposed
#                             status / basis / score ของ detector
#   POST-RUN ADJUDICATION   → ``ind_decisions`` · หน้า ``/verify`` แสดง proposed status ได้
#                             **แต่เปิดได้ก็ต่อเมื่อเฉลยของรอบนั้นถูกผนึกแล้ว**
#
# 🔴 รอบนี้ยังไม่มีเฉลยจริงของงานวิจัย — โค้ดนี้คือ *กลไกการแยก* ที่ต้องมีก่อน
# การผนึกเป็นการกระทำของ Gift (custodian) เท่านั้น


@dataclass(frozen=True)
class KeyEntry:
    seq: int
    run_id: str
    mapping_id: str
    key_status: str
    reason: str
    entered_by: str
    entered_at: str
    audit_seq: int


@dataclass(frozen=True)
class KeySeal:
    seq: int
    run_id: str
    sealed_at: str
    sealed_by: str
    entries_count: int
    key_digest: str
    note: str


class KeyStageError(ValueError):
    """ทำผิดลำดับของขั้นเฉลย — เช่น กรอกเฉลยหลังผนึก หรือเปิด adjudication ก่อนผนึก"""


def record_key_entry(*, run_id: str, mapping_id: str, key_status: str, reason: str,
                     entered_by: str, db_path=None) -> KeyEntry:
    """🔴 **เลิกใช้แล้ว (Pass 3)** — เฉลยผูกกับ *คู่ของ detector* ไม่ได้

    Bo (`5600162467`) — การเลือกคู่เป็นส่วนหนึ่งของผลลัพธ์ที่กำลังถูกประเมิน
    การให้ผู้จัดทำเฉลยกรอกทีละ ``mapping_id`` จึงยัดรูปทรงของ detector เข้าไปในเฉลย
    ⇒ ใช้ :func:`record_key_answer` ที่ผูกกับ **รายการในจักรวาลของเฉลย** แทน
    """
    raise KeyStageError(
        "เลิกใช้แล้ว — เฉลยต้องผูกกับรายการในจักรวาลของเฉลย (record_key_answer) "
        "ไม่ใช่กับคู่ที่ detector เสนอ")


def _record_key_entry_legacy(*, run_id: str, mapping_id: str, key_status: str, reason: str,
                             entered_by: str, db_path=None) -> KeyEntry:
    """เก็บไว้เพื่ออ่านประวัติ/ทดสอบ schema เดิมเท่านั้น — ไม่ใช่เส้นทางของผลิตภัณฑ์"""
    if key_status not in mp.STATUSES:
        raise KeyStageError("สถานะเฉลยไม่รู้จัก")
    if not entered_by.strip():
        raise KeyStageError("ต้องระบุผู้จัดทำ/ผู้ยืนยันเฉลย")
    if key_status in mp.HUMAN_REQUIRED and not reason.strip():
        raise KeyStageError("สถานะนี้ต้องมีเหตุผลประกอบ")
    if key_seal(run_id, db_path) is not None:
        raise KeyStageError("เฉลยของรอบนี้ถูกผนึกแล้ว — แก้ไม่ได้ ต้องเปิดรอบประเมินใหม่")
    conn = connect(db_path)
    try:
        exists = conn.execute("SELECT 1 FROM ind_mappings WHERE run_id = ? AND mapping_id = ?",
                              (run_id, mapping_id)).fetchone()
        if exists is None:
            raise KeyStageError("ไม่พบคู่ที่ระบุในรอบนี้")
        now = _now()
        conn.execute("BEGIN IMMEDIATE")
        entry = audit.record_in(conn, "indicator_key_entry_recorded", "ind_key_entry",
                                mapping_id, {"run_id": run_id, "key_status": key_status,
                                             "entered_by": entered_by,
                                             "registry_version": REGISTRY_VERSION},
                                actor=entered_by)
        cur = conn.execute(
            "INSERT INTO ind_key_entries (run_id, mapping_id, key_status, reason, "
            "entered_by, entered_at, audit_seq, audit_entry_hash) VALUES (?,?,?,?,?,?,?,?)",
            (run_id, mapping_id, key_status, reason, entered_by, now,
             entry["seq"], entry["entry_hash"]))
        seq = int(cur.lastrowid)
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:      # noqa: BLE001
            pass
        raise
    finally:
        conn.close()
    return KeyEntry(seq=seq, run_id=run_id, mapping_id=mapping_id, key_status=key_status,
                    reason=reason, entered_by=entered_by, entered_at=now,
                    audit_seq=entry["seq"])


def key_entries(run_id: str, db_path=None) -> list[KeyEntry]:
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM ind_key_entries WHERE run_id = ? ORDER BY seq",
                            (run_id,)).fetchall()
    finally:
        conn.close()
    return [KeyEntry(seq=r["seq"], run_id=r["run_id"], mapping_id=r["mapping_id"],
                     key_status=r["key_status"], reason=r["reason"],
                     entered_by=r["entered_by"], entered_at=r["entered_at"],
                     audit_seq=r["audit_seq"]) for r in rows]


def latest_key_entries(run_id: str, db_path=None) -> dict:
    out: dict[str, KeyEntry] = {}
    for e in key_entries(run_id, db_path):
        out[e.mapping_id] = e
    return out


def key_digest(run_id: str, db_path=None) -> str:
    """แฮชผนึกของเฉลย ณ ขณะนี้ — บันทึกได้ในที่สาธารณะ (เนื้อเฉลยห้าม)

    🔴 Pass 3 — ผูก **ตัวตน+การจับคู่+สถานะ+แฮชเหตุผล+แฮชเอกสารเต็ม+เวอร์ชัน+manifest
    ของจักรวาล** ตามที่ Bo กำหนด · เดิมผูกเฉพาะ ``mapping_id=status`` ซึ่งเปลี่ยนคู่
    หรือเปลี่ยนเอกสารแล้ว digest ไม่ขยับ
    """
    items = key_universe(run_id, db_path)
    answers = latest_key_answers(run_id, db_path)
    seal = universe_seal(run_id, db_path)
    return ku.seal_digest(
        items, answers, schema_version=IND_SCHEMA_VERSION,
        document_hashes={i.document_sha256 for i in items},
        universe_manifest_digest=(seal.universe_digest if seal else ku.universe_digest(items)))


def key_seal(run_id: str, db_path=None) -> KeySeal | None:
    conn = connect(db_path)
    try:
        r = conn.execute("SELECT * FROM ind_key_seals WHERE run_id = ? ORDER BY seq DESC "
                         "LIMIT 1", (run_id,)).fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    return KeySeal(seq=r["seq"], run_id=r["run_id"], sealed_at=r["sealed_at"],
                   sealed_by=r["sealed_by"], entries_count=r["entries_count"],
                   key_digest=r["key_digest"], note=r["note"])


def seal_key(run_id: str, *, sealed_by: str, note: str = "", db_path=None) -> KeySeal:
    """ผนึกเฉลยของรอบ — **การกระทำของ custodian เท่านั้น** · ปลดล็อกขั้น adjudication"""
    if not sealed_by.strip():
        raise KeyStageError("ต้องระบุผู้ผนึกเฉลย")
    if key_seal(run_id, db_path) is not None:
        raise KeyStageError("เฉลยของรอบนี้ถูกผนึกไปแล้ว")
    useal = universe_seal(run_id, db_path)
    if useal is None:
        raise KeyStageError("ต้องตรึงจักรวาลของเฉลยก่อนจึงจะผนึกได้")
    if detector_snapshot(run_id, db_path) is None:
        raise KeyStageError("ต้องผนึกผลลัพธ์ของเครื่องก่อนจึงจะผนึกเฉลยได้")
    coverage = key_coverage(run_id, db_path)
    if not coverage.closed:
        raise KeyStageError("เฉลยยังไม่ครบตามด่านความครบถ้วน — " + coverage.summary())
    latest = latest_key_answers(run_id, db_path)
    digest = key_digest(run_id, db_path)
    now = _now()
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        entry = audit.record_in(conn, "indicator_key_sealed", "ind_run", run_id,
                                {"entries_count": len(latest), "key_digest": digest,
                                 "sealed_by": sealed_by,
                                 "registry_version": REGISTRY_VERSION}, actor=sealed_by)
        cur = conn.execute(
            "INSERT INTO ind_key_seals (run_id, sealed_at, sealed_by, entries_count, "
            "key_digest, note, audit_seq, audit_entry_hash) VALUES (?,?,?,?,?,?,?,?)",
            (run_id, now, sealed_by, len(latest), digest, note,
             entry["seq"], entry["entry_hash"]))
        seq = int(cur.lastrowid)
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:      # noqa: BLE001
            pass
        raise
    finally:
        conn.close()
    return KeySeal(seq=seq, run_id=run_id, sealed_at=now, sealed_by=sealed_by,
                   entries_count=len(latest), key_digest=digest, note=note)


def adjudication_unlocked(run_id: str, db_path=None) -> bool:
    """ขั้น POST-RUN ADJUDICATION เปิดได้หรือยัง — ต้องผนึก **ครบทั้งสอง artifact** (B4)

    🔴 Bo (`5600162467` ข้อ 4) — *"post-run adjudication opens only after both artifacts
    are sealed."* · 🔴 Bo (`5605652708` P3-1) — *"A stored hash is only evidence; it is
    not an enforcement gate until verified."*

    ตั้งแต่ Pass 4 จึง **คำนวณใหม่แล้วเทียบ** ทั้งสาม artifact ทุกครั้ง ไม่ใช่เช็กว่ามีแถว
    ⇒ ข้อมูลที่เปลี่ยนหลังผนึกทำให้ **ล็อกกลับทันที** และต้องเปิดรอบประเมินใหม่ ห้ามซ่อมทับ
    """
    return seal_verification(run_id, db_path).ok


# ══════════════════════════════════════════════════════════════════════════════
#  B4 (PASS 3) — จักรวาลของเฉลยที่เป็นกลาง · ด่านครบถ้วน · snapshot ของ detector
# ══════════════════════════════════════════════════════════════════════════════
#
# 🔴 Bo (`5600162467`) พบว่า Pass 2 ยังผิด: `key_build_rows(rv)` ไล่ `rv.pairs` ⇒ แม้ตัด
# สถานะ/เหตุผล/คะแนนออกแล้ว **การจับคู่ · จำนวนคู่ · ลำดับ** ก็ยังเป็นผลของ detector
# ที่กำลังถูกประเมิน ⇒ เฉลยถูกชี้นำได้ · Pass 3 จึงตัดสายนั้นทิ้งทั้งเส้น
#
#   จักรวาลของเฉลย  ← `ind_observations` เท่านั้น (ข้อสังเกตในเอกสาร)
#   คำตอบของเฉลย    ← ผู้จัดทำเฉลยเป็นผู้จับคู่เอง ผูกกับ `item_id` ของจักรวาล
#   snapshot ของ detector ← artifact คนละชิ้น ผนึกแยก
#
# ลำดับที่บังคับ: สร้างจักรวาล → **ตรึงจักรวาล** → กรอกคำตอบให้ครบ → ผนึกเฉลย
#                 + ผนึก snapshot ของ detector → จึงเปิดขั้นตัดสินหลังรันได้


@dataclass(frozen=True)
class UniverseSeal:
    seq: int
    run_id: str
    frozen_at: str
    frozen_by: str
    item_count: int
    universe_digest: str
    protocol_version: str


@dataclass(frozen=True)
class DetectorSnapshot:
    seq: int
    run_id: str
    sealed_at: str
    sealed_by: str
    pair_count: int
    snapshot_digest: str
    rules_hash: str
    note: str
    snapshot_protocol: str = ""
    observation_count: int = -1
    mappings_digest: str = ""
    observations_digest: str = ""
    metadata_digest: str = ""
    documents_digest: str = ""


@dataclass(frozen=True)
class KeyAnswerRow:
    seq: int
    run_id: str
    item_id: str
    key_status: str
    counterpart_item_id: str
    reason: str
    entered_by: str
    entered_at: str
    audit_seq: int


def _universe_records(run_id: str, db_path=None) -> list[dict]:
    """🔴 **เลิกใช้เป็นต้นทางของจักรวาลแล้ว (Pass 4)** — อ่านจาก ``ind_observations``

    Bo (`5605652708` P3-2) — ข้อสังเกตเหล่านี้ถูกบันทึกโดย pipeline เดียวกับ detector
    ⇒ ตัวชี้วัดที่เครื่องสกัดตกหล่นจะไม่มีวันเข้าจักรวาล · จักรวาลจึงย้ายไปตั้งต้นที่
    :func:`_universe_records_from_inventory` แทน · ฟังก์ชันนี้เหลือไว้ให้
    :func:`detector_coverage` ใช้อ่าน "สิ่งที่เครื่องสกัดได้" เพื่อนำไป **เทียบ** เท่านั้น
    """
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT side, observation_id, identity_key, source_sha256, page, anchor, "
            "observed_text FROM ind_observations WHERE run_id = ? "
            "ORDER BY side, page, line_index", (run_id,)).fetchall()
    finally:
        conn.close()
    return [{"side": r["side"], "observation_id": r["observation_id"],
             "identity_key": (r["identity_key"] or ""),
             "document_sha256": r["source_sha256"], "page": r["page"],
             "anchor": (r["anchor"] if "anchor" in r.keys() else ""),
             "observed_text": r["observed_text"]} for r in rows]


def key_universe(run_id: str, db_path=None) -> tuple:
    """รายการทั้งหมดของจักรวาลที่บันทึกไว้ — เรียงตามลำดับกลาง"""
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM ind_key_universe WHERE run_id = ? ORDER BY seq",
                            (run_id,)).fetchall()
    finally:
        conn.close()
    items = [ku.UniverseItem(
        item_id=r["item_id"], side=r["side"], observation_id=r["observation_id"],
        identity_key=r["identity_key"], document_sha256=r["document_sha256"],
        page=r["page"], anchor=r["anchor"], text_sha256=r["text_sha256"]) for r in rows]
    items.sort(key=lambda i: i.sort_key)
    return tuple(items)


def universe_seal(run_id: str, db_path=None) -> "UniverseSeal | None":
    conn = connect(db_path)
    try:
        r = conn.execute("SELECT * FROM ind_key_universe_seals WHERE run_id = ?",
                         (run_id,)).fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    return UniverseSeal(seq=r["seq"], run_id=r["run_id"], frozen_at=r["frozen_at"],
                        frozen_by=r["frozen_by"], item_count=r["item_count"],
                        universe_digest=r["universe_digest"],
                        protocol_version=r["protocol_version"])


def build_key_universe(run_id: str, *, built_by: str, db_path=None) -> tuple:
    """สร้างจักรวาลของเฉลยจากข้อสังเกตของรอบนี้ — เรียกซ้ำได้จนกว่าจะตรึง"""
    if not built_by.strip():
        raise KeyStageError("ต้องระบุผู้จัดทำจักรวาลของเฉลย")
    if universe_seal(run_id, db_path) is not None:
        raise KeyStageError("จักรวาลของเฉลยรอบนี้ถูกตรึงแล้ว — สร้างใหม่ไม่ได้")
    records = _universe_records_from_inventory(run_id, db_path)
    if not records:
        raise KeyStageError(
            "ทะเบียนข้อสังเกตอิสระของรอบนี้ยังว่าง — ต้องให้ผู้ดูแลอ่านเอกสารแล้วกรอกรายการก่อน "
            "(จักรวาลของเฉลยไม่ดึงจากสิ่งที่เครื่องสกัดได้อีกต่อไป)")
    try:
        items = ku.build_items(records)
    except ku.UniverseError as e:
        raise KeyStageError(str(e)) from None
    now = _now()
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        audit.record_in(conn, "indicator_key_universe_built", "ind_run", run_id,
                        {"item_count": len(items),
                         "universe_digest": ku.universe_digest(items),
                         "universe_version": ku.KEY_UNIVERSE_VERSION,
                         "built_by": built_by}, actor=built_by)
        for i in items:
            conn.execute(
                "INSERT OR IGNORE INTO ind_key_universe (run_id, item_id, side, "
                "observation_id, identity_key, document_sha256, page, anchor, "
                "text_sha256, built_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, i.item_id, i.side, i.observation_id, i.identity_key,
                 i.document_sha256, i.page, i.anchor, i.text_sha256, now))
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:      # noqa: BLE001
            pass
        raise
    finally:
        conn.close()
    return key_universe(run_id, db_path)


def freeze_key_universe(run_id: str, *, frozen_by: str, db_path=None) -> UniverseSeal:
    """ตรึงจักรวาล — หลังจากนี้จึงกรอกคำตอบของเฉลยได้ และเพิ่ม/ลดรายการไม่ได้อีก"""
    if not frozen_by.strip():
        raise KeyStageError("ต้องระบุผู้ตรึงจักรวาลของเฉลย")
    if universe_seal(run_id, db_path) is not None:
        raise KeyStageError("จักรวาลของเฉลยรอบนี้ถูกตรึงไปแล้ว")
    items = key_universe(run_id, db_path)
    if not items:
        raise KeyStageError("ยังไม่มีจักรวาลของเฉลยให้ตรึง")
    digest = ku.universe_digest(items)
    now = _now()
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        entry = audit.record_in(conn, "indicator_key_universe_frozen", "ind_run", run_id,
                                {"item_count": len(items), "universe_digest": digest,
                                 "protocol_version": ku.KEY_PROTOCOL_VERSION,
                                 "frozen_by": frozen_by}, actor=frozen_by)
        cur = conn.execute(
            "INSERT INTO ind_key_universe_seals (run_id, frozen_at, frozen_by, "
            "item_count, universe_digest, protocol_version, audit_seq, audit_entry_hash) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (run_id, now, frozen_by, len(items), digest, ku.KEY_PROTOCOL_VERSION,
             entry["seq"], entry["entry_hash"]))
        seq = int(cur.lastrowid)
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:      # noqa: BLE001
            pass
        raise
    finally:
        conn.close()
    return UniverseSeal(seq=seq, run_id=run_id, frozen_at=now, frozen_by=frozen_by,
                        item_count=len(items), universe_digest=digest,
                        protocol_version=ku.KEY_PROTOCOL_VERSION)


def record_key_answer(*, run_id: str, item_id: str, key_status: str,
                      counterpart_item_id: str = "", reason: str = "",
                      entered_by: str, db_path=None) -> KeyAnswerRow:
    """บันทึกคำตอบของเฉลยหนึ่งรายการ — ผูกกับ **รายการในจักรวาล** ไม่ใช่คู่ของ detector"""
    if not entered_by.strip():
        raise KeyStageError("ต้องระบุผู้จัดทำ/ผู้ยืนยันเฉลย")
    if key_status not in mp.STATUSES:
        raise KeyStageError("สถานะเฉลยไม่รู้จัก")
    if key_status in mp.HUMAN_REQUIRED and not reason.strip():
        raise KeyStageError("สถานะนี้ต้องมีเหตุผลประกอบ")
    if universe_seal(run_id, db_path) is None:
        raise KeyStageError("ต้องตรึงจักรวาลของเฉลยก่อนจึงจะกรอกคำตอบได้")
    # 🔴 ลำดับที่ Bo กำหนด — ผนึกผลของเครื่อง **ก่อน** ทำเฉลย ⇒ แก้เครื่องหลังเห็นเฉลยไม่ได้
    if detector_snapshot(run_id, db_path) is None:
        raise KeyStageError("ต้องผนึกผลลัพธ์ของเครื่องก่อนจึงจะกรอกคำตอบของเฉลยได้")
    if key_seal(run_id, db_path) is not None:
        raise KeyStageError("เฉลยของรอบนี้ถูกผนึกแล้ว — แก้ไม่ได้ ต้องเปิดรอบประเมินใหม่")
    items = {i.item_id: i for i in key_universe(run_id, db_path)}
    if item_id not in items:
        raise KeyStageError("ไม่พบรายการนี้ในจักรวาลของเฉลย")
    counterpart = (counterpart_item_id or "").strip()
    if counterpart:
        if counterpart not in items:
            raise KeyStageError("คู่ที่ระบุไม่อยู่ในจักรวาลของเฉลย")
        if items[counterpart].side == items[item_id].side:
            raise KeyStageError("คู่ที่ระบุอยู่ฝั่งเดียวกัน — จับคู่ไม่ได้")
    now = _now()
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        entry = audit.record_in(conn, "indicator_key_answer_recorded", "ind_key_item",
                                item_id, {"run_id": run_id, "key_status": key_status,
                                          "paired": bool(counterpart),
                                          "entered_by": entered_by,
                                          "protocol_version": ku.KEY_PROTOCOL_VERSION},
                                actor=entered_by)
        cur = conn.execute(
            "INSERT INTO ind_key_answers (run_id, item_id, key_status, "
            "counterpart_item_id, reason, entered_by, entered_at, audit_seq, "
            "audit_entry_hash) VALUES (?,?,?,?,?,?,?,?,?)",
            (run_id, item_id, key_status, counterpart, reason, entered_by, now,
             entry["seq"], entry["entry_hash"]))
        seq = int(cur.lastrowid)
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:      # noqa: BLE001
            pass
        raise
    finally:
        conn.close()
    return KeyAnswerRow(seq=seq, run_id=run_id, item_id=item_id, key_status=key_status,
                        counterpart_item_id=counterpart, reason=reason,
                        entered_by=entered_by, entered_at=now, audit_seq=entry["seq"])


def key_answers(run_id: str, db_path=None) -> list:
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM ind_key_answers WHERE run_id = ? ORDER BY seq",
                            (run_id,)).fetchall()
    finally:
        conn.close()
    return [KeyAnswerRow(seq=r["seq"], run_id=r["run_id"], item_id=r["item_id"],
                         key_status=r["key_status"],
                         counterpart_item_id=r["counterpart_item_id"],
                         reason=r["reason"], entered_by=r["entered_by"],
                         entered_at=r["entered_at"], audit_seq=r["audit_seq"])
            for r in rows]


def latest_key_answers(run_id: str, db_path=None) -> dict:
    """คำตอบ **ที่มีผล** ต่อหนึ่งรายการ = แถวล่าสุด (ประวัติเดิมยังอยู่ครบ)"""
    out: dict = {}
    for a in key_answers(run_id, db_path):
        out[a.item_id] = ku.KeyAnswer(item_id=a.item_id, key_status=a.key_status,
                                      counterpart_item_id=a.counterpart_item_id,
                                      reason=a.reason)
    return out


def key_coverage(run_id: str, db_path=None) -> ku.Coverage:
    """ด่านความครบถ้วนของเฉลยเทียบกับจักรวาลที่ตรึงไว้"""
    return ku.check_coverage(key_universe(run_id, db_path),
                             latest_key_answers(run_id, db_path))


def detector_projection_columns(db_path=None) -> dict:
    """ส่วน → (ตาราง, รายชื่อคอลัมน์ที่เข้า projection) — อ่านจาก **schema จริง** ทุกครั้ง

    🔴 Bo (`5615776981` P5-2) — *"Avoid another partial field list."* ⇒ ไม่มีรายการฟิลด์
    ที่เขียนเองในโค้ดอีก · คอลัมน์ที่เพิ่มในอนาคตถูกครอบอัตโนมัติ · ข้อยกเว้นต้องอยู่ใน
    :data:`keyuniverse.DETECTOR_PROJECTION_EXCLUDED` พร้อมเหตุผลเท่านั้น
    """
    conn = connect(db_path)
    try:
        out = {}
        for part, table in ku.DETECTOR_PARTS:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(%s)" % table)]
            skip = set(ku.DETECTOR_PROJECTION_EXCLUDED.get(table, ()))
            out[part] = (table, tuple(c for c in cols if c not in skip))
    finally:
        conn.close()
    return out


def _detector_facts(run_id: str, db_path=None) -> dict:
    """ส่วนประกอบทั้งหมดของผลลัพธ์เครื่อง ณ ขณะนี้ — **ทุกคอลัมน์** ของทุกแถวที่เกี่ยวข้อง

    🔴 Bo (`5606392284` P4-3 · `5615776981` P5-2) — ทุกฟิลด์ที่รายงาน/หน้าหลักฐาน/package/
    การเทียบใช้ ต้องอยู่ใน artifact ที่ผนึก · ส่วนประกอบ:
    คู่ (``ind_mappings``) · ข้อสังเกต (``ind_observations``) · ข้อมูลกำกับของรอบ (``ind_runs``) ·
    บริบทของสองเอกสารที่รอบนั้นอ้าง (``evd_documents``)
    """
    run = get_run(run_id, db_path)
    if run is None:
        raise KeyStageError("ไม่พบรอบที่ระบุ")
    projection = detector_projection_columns(db_path)
    conn = connect(db_path)
    try:
        parts = {}
        counts = {}
        for part, (table, cols) in projection.items():
            col_sql = ", ".join('"%s"' % c for c in cols)
            if table == "ind_runs":
                rows = conn.execute("SELECT %s FROM ind_runs WHERE id = ?" % col_sql,
                                    (run_id,)).fetchall()
            elif table == "evd_documents":
                rows = conn.execute(
                    "SELECT %s FROM evd_documents WHERE document_id IN (?, ?)" % col_sql,
                    (run.old_document_id, run.new_document_id)).fetchall()
            else:
                rows = conn.execute("SELECT %s FROM %s WHERE run_id = ?" % (col_sql, table),
                                    (run_id,)).fetchall()
            parts[part] = ku.canonical_rows_digest(table, cols, rows)
            counts[part] = len(rows)
    finally:
        conn.close()
    digest = ku.detector_snapshot_digest(
        part_digests=parts, pair_count=counts["mappings"],
        observation_count=counts["observations"], schema_version=IND_SCHEMA_VERSION)
    return {"pair_count": counts["mappings"], "observation_count": counts["observations"],
            "document_rows": counts["documents"],
            "mappings_digest": parts["mappings"],
            "observations_digest": parts["observations"],
            "metadata_digest": parts["metadata"],
            "documents_digest": parts["documents"], "digest": digest,
            "rules_hash": run.rules_hash, "protocol": ku.DETECTOR_SNAPSHOT_PROTOCOL}


def detector_snapshot_preview(run_id: str, db_path=None) -> tuple:
    """(จำนวนคู่, digest) ของผลลัพธ์ detector ณ ขณะนี้ — ใช้แสดง/ตรวจก่อนผนึก"""
    facts = _detector_facts(run_id, db_path)
    return facts["pair_count"], facts["digest"]


def detector_snapshot(run_id: str, db_path=None) -> "DetectorSnapshot | None":
    conn = connect(db_path)
    try:
        r = conn.execute("SELECT * FROM ind_detector_snapshots WHERE run_id = ?",
                         (run_id,)).fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    keys = r.keys()
    return DetectorSnapshot(seq=r["seq"], run_id=r["run_id"], sealed_at=r["sealed_at"],
                            sealed_by=r["sealed_by"], pair_count=r["pair_count"],
                            snapshot_digest=r["snapshot_digest"],
                            rules_hash=r["rules_hash"], note=r["note"],
                            snapshot_protocol=(r["snapshot_protocol"]
                                               if "snapshot_protocol" in keys else ""),
                            observation_count=(r["observation_count"]
                                               if "observation_count" in keys else -1),
                            mappings_digest=(r["mappings_digest"]
                                             if "mappings_digest" in keys else ""),
                            observations_digest=(r["observations_digest"]
                                                 if "observations_digest" in keys else ""),
                            metadata_digest=(r["metadata_digest"]
                                             if "metadata_digest" in keys else ""),
                            documents_digest=(r["documents_digest"]
                                              if "documents_digest" in keys else ""))


def seal_detector_snapshot(run_id: str, *, sealed_by: str, note: str = "",
                           db_path=None) -> DetectorSnapshot:
    """ผนึกผลลัพธ์ของ detector — artifact คนละชิ้นกับเฉลย

    🔴 ผนึกแล้วเปลี่ยนวิธีจับคู่/จำนวนคู่ไม่ได้อีกโดยไม่ถูกจับได้ เพราะ digest ผูกทั้งสองอย่าง
    """
    if not sealed_by.strip():
        raise KeyStageError("ต้องระบุผู้ผนึกผลลัพธ์ของเครื่อง")
    if detector_snapshot(run_id, db_path) is not None:
        raise KeyStageError("ผลลัพธ์ของเครื่องรอบนี้ถูกผนึกไปแล้ว")
    # 🔴 ลำดับที่ Bo กำหนด — ตรึงทะเบียนอิสระ **ก่อน** ผนึกผลของเครื่องเสมอ
    if universe_seal(run_id, db_path) is None:
        raise KeyStageError("ต้องตรึงจักรวาลของเฉลย (ทะเบียนอิสระ) ก่อนผนึกผลลัพธ์ของเครื่อง")
    run = get_run(run_id, db_path)
    if run is None:
        raise KeyStageError("ไม่พบรอบที่ระบุ")
    facts = _detector_facts(run_id, db_path)
    count, digest = facts["pair_count"], facts["digest"]
    now = _now()
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        entry = audit.record_in(conn, "indicator_detector_snapshot_sealed", "ind_run",
                                run_id, {"pair_count": count,
                                         "observation_count": facts["observation_count"],
                                         "snapshot_digest": digest,
                                         "snapshot_protocol": facts["protocol"],
                                         "rules_hash": run.rules_hash,
                                         "sealed_by": sealed_by}, actor=sealed_by)
        cur = conn.execute(
            "INSERT INTO ind_detector_snapshots (run_id, sealed_at, sealed_by, "
            "pair_count, snapshot_digest, rules_hash, note, audit_seq, audit_entry_hash, "
            "snapshot_protocol, observation_count, mappings_digest, observations_digest, "
            "metadata_digest, documents_digest) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, now, sealed_by, count, digest, run.rules_hash, note,
             entry["seq"], entry["entry_hash"], facts["protocol"],
             facts["observation_count"], facts["mappings_digest"],
             facts["observations_digest"], facts["metadata_digest"],
             facts["documents_digest"]))
        seq = int(cur.lastrowid)
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:      # noqa: BLE001
            pass
        raise
    finally:
        conn.close()
    return DetectorSnapshot(seq=seq, run_id=run_id, sealed_at=now, sealed_by=sealed_by,
                            pair_count=count, snapshot_digest=digest,
                            rules_hash=run.rules_hash, note=note,
                            snapshot_protocol=facts["protocol"],
                            observation_count=facts["observation_count"],
                            mappings_digest=facts["mappings_digest"],
                            observations_digest=facts["observations_digest"],
                            metadata_digest=facts["metadata_digest"],
                            documents_digest=facts["documents_digest"])


# ══════════════════════════════════════════════════════════════════════════════
#  P3-2 (PASS 4) — ทะเบียนข้อสังเกต **อิสระ** ของผู้ดูแล
# ══════════════════════════════════════════════════════════════════════════════
#
# 🔴 Bo (`5605652708`) — จักรวาลของเฉลยที่สร้างจาก `ind_observations` ยังพึ่ง **การสกัด**
# ของ detector · ตัวชี้วัดที่เครื่องสกัดไม่เจอจะไม่มีวันเข้าจักรวาล ⇒ recall สูงเกินจริง
#
# ตั้งแต่ Pass 4 จักรวาลของเฉลยตั้งต้นจากตารางนี้ ซึ่ง **คนกรอกจากการอ่านเอกสารเอง**


@dataclass(frozen=True)
class SourceRow:
    seq: int
    run_id: str
    identity_key: str
    side: str
    document_sha256: str
    page: int
    occurrence: int
    hint: str
    anchor: str
    observed_text: str
    entered_by: str
    entered_at: str


def _run_document_hashes(run_id: str, db_path=None) -> dict:
    """ฝั่ง → แฮชเนื้อเอกสาร **เต็ม** จากทะเบียนเอกสาร (ไม่ใช่จากผลของ detector)"""
    run = get_run(run_id, db_path)
    if run is None:
        raise KeyStageError("ไม่พบรอบที่ระบุ")
    out = {ku.SIDE_OLD: run.old_document_sha256 or "",
           ku.SIDE_NEW: run.new_document_sha256 or ""}
    for side, sha in out.items():
        if len(sha) != si.FULL_DIGEST_LEN:
            raise KeyStageError(
                "รอบนี้ไม่มีแฮชเนื้อเอกสารแบบเต็มของฝั่ง " + side +
                " — กรอกทะเบียนข้อสังเกตอิสระไม่ได้ ต้องเปิดรอบใหม่")
    return out


def record_source_item(*, run_id: str, side: str, page: object, observed_text: str,
                       occurrence: object = 1, hint: str = "", entered_by: str,
                       db_path=None) -> SourceRow:
    """กรอกหนึ่งรายการเข้าทะเบียนข้อสังเกตอิสระ — **คนอ่านเอกสารแล้วกรอกเอง**

    🔴 ไม่มีพารามิเตอร์ใดรับข้อมูลจาก ``ind_observations`` หรือ ``ind_mappings``
    แฮชเอกสารมาจาก **ทะเบียนเอกสาร** ของรอบนั้น ผู้กรอกจึงระบุเองไม่ได้
    """
    if universe_seal(run_id, db_path) is not None:
        raise KeyStageError("ตรึงจักรวาลของเฉลยแล้ว — เพิ่มรายการในทะเบียนอิสระไม่ได้อีก")
    hashes = _run_document_hashes(run_id, db_path)
    if side not in hashes:
        raise KeyStageError("ฝั่งของรายการต้องเป็น old หรือ new")
    run = get_run(run_id, db_path)
    pages = run.old_page_count if side == ku.SIDE_OLD else run.new_page_count
    try:
        item = si.make_item(side=side, document_sha256=hashes[side], page=page,
                            observed_text=observed_text, occurrence=occurrence,
                            hint=hint, entered_by=entered_by, page_count=pages)
    except si.InventoryError as e:
        raise KeyStageError(str(e)) from None
    # 🔴 P4-4 — ห้ามมีสองรายการที่ชี้ตำแหน่งเดียวกันทั้งห้าองค์ประกอบ (ต่างกันแค่จุดอ้างอิงสั้น)
    # มิฉะนั้นข้อสังเกตหนึ่งตัวของเครื่องจะถูกนับตอบได้สองรายการ
    for existing in source_inventory(run_id, db_path):
        if existing.match_key == item.match_key:
            raise KeyStageError(
                "มีรายการที่ข้อความเดียวกันและลำดับที่ปรากฏเดียวกันในหน้านี้อยู่แล้ว — "
                "ถ้าเป็นการปรากฏอีกครั้ง ให้เพิ่มลำดับที่ปรากฏ")
    now = _now()
    conn = connect(db_path)
    try:
        dup = conn.execute("SELECT 1 FROM ind_source_inventory WHERE run_id = ? AND "
                           "identity_key = ?", (run_id, item.identity_key)).fetchone()
        if dup is not None:
            raise KeyStageError(
                "รายการนี้อยู่ในทะเบียนแล้ว — ถ้าเป็นตัวชี้วัดคนละตัวในหน้าเดียวกัน "
                "ให้เพิ่มลำดับที่ปรากฏ (occurrence) หรือระบุจุดอ้างอิงสั้น ๆ")
        conn.execute("BEGIN IMMEDIATE")
        entry = audit.record_in(conn, "indicator_source_item_recorded", "ind_source_item",
                                item.identity_key,
                                {"run_id": run_id, "side": side, "page": item.page,
                                 "occurrence": item.occurrence,
                                 "inventory_version": si.SOURCE_INVENTORY_VERSION,
                                 "entered_by": item.entered_by}, actor=item.entered_by)
        cur = conn.execute(
            "INSERT INTO ind_source_inventory (run_id, identity_key, side, "
            "document_sha256, page, occurrence, hint, anchor, observed_text, "
            "normalized_text, entered_by, entered_at, audit_seq, audit_entry_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, item.identity_key, item.side, item.document_sha256, item.page,
             item.occurrence, item.hint, item.anchor, item.observed_text,
             item.normalized_text, item.entered_by, now,
             entry["seq"], entry["entry_hash"]))
        seq = int(cur.lastrowid)
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:      # noqa: BLE001
            pass
        raise
    finally:
        conn.close()
    return SourceRow(seq=seq, run_id=run_id, identity_key=item.identity_key,
                     side=item.side, document_sha256=item.document_sha256,
                     page=item.page, occurrence=item.occurrence, hint=item.hint,
                     anchor=item.anchor, observed_text=item.observed_text,
                     entered_by=item.entered_by, entered_at=now)


def retract_source_item(*, run_id: str, identity_key: str, retracted_by: str,
                        reason: str = "", db_path=None) -> None:
    """ถอนรายการที่กรอกผิด — **ก่อนตรึงเท่านั้น** · แถวเดิมยังอยู่ในประวัติ"""
    if not retracted_by.strip():
        raise KeyStageError("ต้องระบุผู้ถอนรายการ")
    if universe_seal(run_id, db_path) is not None:
        raise KeyStageError("ตรึงจักรวาลของเฉลยแล้ว — ถอนรายการไม่ได้อีก")
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT 1 FROM ind_source_inventory WHERE run_id = ? AND "
                           "identity_key = ?", (run_id, identity_key)).fetchone()
        if row is None:
            raise KeyStageError("ไม่พบรายการนี้ในทะเบียนอิสระ")
        conn.execute("BEGIN IMMEDIATE")
        entry = audit.record_in(conn, "indicator_source_item_retracted",
                                "ind_source_item", identity_key,
                                {"run_id": run_id, "retracted_by": retracted_by},
                                actor=retracted_by)
        conn.execute(
            "INSERT INTO ind_source_inventory_retractions (run_id, identity_key, "
            "retracted_by, retracted_at, reason, audit_seq, audit_entry_hash) "
            "VALUES (?,?,?,?,?,?,?)",
            (run_id, identity_key, retracted_by, _now(), reason,
             entry["seq"], entry["entry_hash"]))
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:      # noqa: BLE001
            pass
        raise
    finally:
        conn.close()


def source_inventory_rows(run_id: str, db_path=None) -> list:
    """แถวที่ **มีผล** ของทะเบียนอิสระ (ตัดรายการที่ถูกถอนออกแล้ว)"""
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM ind_source_inventory WHERE run_id = ? "
                            "ORDER BY seq", (run_id,)).fetchall()
        gone = {r["identity_key"] for r in conn.execute(
            "SELECT identity_key FROM ind_source_inventory_retractions WHERE run_id = ?",
            (run_id,)).fetchall()}
    finally:
        conn.close()
    return [SourceRow(seq=r["seq"], run_id=r["run_id"], identity_key=r["identity_key"],
                      side=r["side"], document_sha256=r["document_sha256"],
                      page=r["page"], occurrence=r["occurrence"], hint=r["hint"],
                      anchor=r["anchor"], observed_text=r["observed_text"],
                      entered_by=r["entered_by"], entered_at=r["entered_at"])
            for r in rows if r["identity_key"] not in gone]


def source_inventory(run_id: str, db_path=None) -> tuple:
    """ทะเบียนอิสระที่มีผล ในรูป :class:`sourceinventory.SourceItem`"""
    return tuple(si.SourceItem(side=r.side, document_sha256=r.document_sha256,
                               page=r.page, occurrence=r.occurrence, hint=r.hint,
                               observed_text=r.observed_text, entered_by=r.entered_by)
                 for r in source_inventory_rows(run_id, db_path))


def _universe_records_from_inventory(run_id: str, db_path=None) -> list:
    """ข้อมูลตั้งต้นของจักรวาล — มาจาก **ทะเบียนอิสระ** ไม่ใช่ ``ind_observations``"""
    return [{"side": i.side, "observation_id": "", "identity_key": i.identity_key,
             "document_sha256": i.document_sha256, "page": i.page, "anchor": i.anchor,
             "observed_text": i.observed_text}
            for i in source_inventory(run_id, db_path)]


# ══════════════════════════════════════════════════════════════════════════════
#  P3-1 (PASS 4) — ตรวจผนึกจริงทุกครั้งก่อนเปิดขั้นตัดสิน
# ══════════════════════════════════════════════════════════════════════════════
#
# 🔴 Bo (`5605652708`) — *"A stored hash is only evidence; it is not an enforcement gate
# until verified."* · เดิม `adjudication_unlocked()` เช็กเพียงว่า **มีแถว seal อยู่**


def verify_universe_seal(run_id: str, db_path=None) -> ku.SealCheck:
    """คำนวณจักรวาลใหม่ทั้งจากแถวที่บันทึกไว้และจากทะเบียนอิสระ แล้วเทียบกับค่าที่ตรึง"""
    seal = universe_seal(run_id, db_path)
    if seal is None:
        return ku.SealCheck(artifact=ku.ARTIFACT_UNIVERSE, ok=False,
                            reasons=(ku.R_UNIVERSE_NOT_FROZEN,))
    stored_items = key_universe(run_id, db_path)
    stored_digest = ku.universe_digest(stored_items)
    reasons: list[str] = []
    if len(stored_items) != int(seal.item_count):
        reasons.append(ku.R_UNIVERSE_COUNT_MISMATCH)
    if not ku.digests_equal(stored_digest, seal.universe_digest):
        reasons.append(ku.R_UNIVERSE_DIGEST_MISMATCH)
    try:
        rebuilt = ku.build_items(_universe_records_from_inventory(run_id, db_path))
        inventory_digest = ku.universe_digest(rebuilt)
    except ku.UniverseError:
        inventory_digest = ""
    if not ku.digests_equal(inventory_digest, seal.universe_digest):
        reasons.append(ku.R_UNIVERSE_ROWS_DIFFER)
    return ku.SealCheck(artifact=ku.ARTIFACT_UNIVERSE, ok=not reasons,
                        reasons=tuple(reasons), sealed_digest=seal.universe_digest,
                        current_digest=stored_digest)


def verify_key_seal(run_id: str, db_path=None) -> ku.SealCheck:
    """คำนวณแฮชเฉลยใหม่จากคำตอบที่มีผล ณ ขณะนี้ แล้วเทียบกับค่าที่ผนึก"""
    seal = key_seal(run_id, db_path)
    if seal is None:
        return ku.SealCheck(artifact=ku.ARTIFACT_KEY, ok=False,
                            reasons=(ku.R_KEY_NOT_SEALED,))
    current = key_digest(run_id, db_path)
    reasons: list[str] = []
    if len(latest_key_answers(run_id, db_path)) != int(seal.entries_count):
        reasons.append(ku.R_KEY_COUNT_MISMATCH)
    if not ku.digests_equal(current, seal.key_digest):
        reasons.append(ku.R_KEY_DIGEST_MISMATCH)
    if not key_coverage(run_id, db_path).closed:
        reasons.append(ku.R_KEY_COVERAGE_BROKEN)
    return ku.SealCheck(artifact=ku.ARTIFACT_KEY, ok=not reasons, reasons=tuple(reasons),
                        sealed_digest=seal.key_digest, current_digest=current)


def verify_detector_snapshot(run_id: str, db_path=None) -> ku.SealCheck:
    """คำนวณแฮชผลลัพธ์ของเครื่องใหม่จากแถวปัจจุบัน แล้วเทียบกับค่าที่ผนึก"""
    snap = detector_snapshot(run_id, db_path)
    if snap is None:
        return ku.SealCheck(artifact=ku.ARTIFACT_DETECTOR, ok=False,
                            reasons=(ku.R_DETECTOR_NOT_SEALED,))
    facts = _detector_facts(run_id, db_path)
    digest = facts["digest"]
    reasons: list[str] = []
    # 🔴 P4-3 — ผนึกที่ทำด้วยพิธีการเก่า (ไม่ครอบข้อสังเกต) ต้องล็อก ไม่ใช่ยอมรับเงียบ
    if snap.snapshot_protocol != ku.DETECTOR_SNAPSHOT_PROTOCOL:
        reasons.append(ku.R_DETECTOR_PROTOCOL_OUTDATED)
    if facts["pair_count"] != int(snap.pair_count):
        reasons.append(ku.R_DETECTOR_COUNT_MISMATCH)
    if facts["observation_count"] != int(snap.observation_count):
        reasons.append(ku.R_DETECTOR_OBSERVATION_COUNT_MISMATCH)
    if str(facts["rules_hash"]) != str(snap.rules_hash):
        reasons.append(ku.R_DETECTOR_RULES_MISMATCH)
    if not ku.digests_equal(facts["mappings_digest"], snap.mappings_digest):
        reasons.append(ku.R_DETECTOR_MAPPINGS_MISMATCH)
    if not ku.digests_equal(facts["observations_digest"], snap.observations_digest):
        reasons.append(ku.R_DETECTOR_OBSERVATIONS_MISMATCH)
    if not ku.digests_equal(facts["metadata_digest"], snap.metadata_digest):
        reasons.append(ku.R_DETECTOR_METADATA_MISMATCH)
    if not ku.digests_equal(facts["documents_digest"], snap.documents_digest):
        reasons.append(ku.R_DETECTOR_DOCUMENTS_MISMATCH)
    if not ku.digests_equal(digest, snap.snapshot_digest):
        reasons.append(ku.R_DETECTOR_DIGEST_MISMATCH)
    return ku.SealCheck(artifact=ku.ARTIFACT_DETECTOR, ok=not reasons,
                        reasons=tuple(reasons), sealed_digest=snap.snapshot_digest,
                        current_digest=digest)


def seal_verification(run_id: str, db_path=None) -> ku.SealVerification:
    """ด่านจริงของขั้นตัดสินหลังรัน — ต้องผ่านครบทั้งสาม artifact"""
    return ku.SealVerification(universe=verify_universe_seal(run_id, db_path),
                               key=verify_key_seal(run_id, db_path),
                               detector=verify_detector_snapshot(run_id, db_path))


def detector_coverage(run_id: str, db_path=None):
    """เทียบทะเบียนอิสระกับข้อสังเกตที่เครื่องสกัดได้ — **เปิดหลังผนึกครบและตรวจผ่านเท่านั้น**

    🔴 นี่คือจุดที่ตัวชี้วัดซึ่งเครื่องสกัดตกหล่นถูกมองเห็น · ไม่ใช่คะแนนและไม่ใช่ผลประเมิน
    """
    verification = seal_verification(run_id, db_path)
    if not verification.ok:
        raise KeyStageError("เทียบความครอบคลุมยังไม่ได้ — " + verification.summary())
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT side, observation_id, source_sha256, page, line_index, observed_text "
            "FROM ind_observations WHERE run_id = ? "
            "ORDER BY side, page, line_index, observation_id", (run_id,)).fetchall()
    finally:
        conn.close()
    # ลำดับที่ปรากฏถูกกำหนดใหม่ใน ``si.detector_occurrences`` อีกชั้น — ไม่พึ่ง ORDER BY นี้อย่างเดียว
    observations = [{"side": r["side"], "observation_id": r["observation_id"],
                     "document_sha256": r["source_sha256"], "page": r["page"],
                     "line_index": r["line_index"],
                     "observed_text": r["observed_text"]} for r in rows]
    return si.coverage(source_inventory(run_id, db_path), observations)


# ══════════════════════════════════════════════════════════════════════════════
#  P4-2 (PASS 5) — ไฟล์ส่งออกผูกกับรอบและผนึก
# ══════════════════════════════════════════════════════════════════════════════
#
# 🔴 Bo (`5606392284` P4-2) — เดิม route ดาวน์โหลดตรวจเพียงชื่อไฟล์และการมีอยู่ของไฟล์
# ⇒ ชุดที่สร้างตอนผนึกยังถูกต้อง ดาวน์โหลดได้ต่อไปแม้ภายหลังผนึกไม่ตรงแล้ว

EXPORT_NOT_BOUND = "EXPORT_NOT_BOUND_TO_RUN"
EXPORT_RUN_MISMATCH = "EXPORT_BELONGS_TO_ANOTHER_RUN"
EXPORT_SEALS_NOT_VERIFIED = "EXPORT_SEALS_NOT_VERIFIED"
EXPORT_SEAL_DIGEST_CHANGED = "EXPORT_SEAL_DIGEST_CHANGED_SINCE_EXPORT"
EXPORT_FILE_CHANGED = "EXPORT_FILE_CHANGED_SINCE_EXPORT"
EXPORT_FILE_MISSING = "EXPORT_FILE_MISSING"

EXPORT_REASON_LABELS = {
    EXPORT_NOT_BOUND: "ไฟล์นี้ไม่มีบันทึกผูกกับรอบประเมิน (ไฟล์เก่าหรือไม่ได้สร้างผ่านระบบ) — ดาวน์โหลดไม่ได้",
    EXPORT_RUN_MISMATCH: "ไฟล์นี้เป็นของรอบประเมินอื่น",
    EXPORT_SEALS_NOT_VERIFIED: "ผนึกของรอบนี้ตรวจไม่ผ่านแล้ว — ดาวน์โหลดไม่ได้",
    EXPORT_SEAL_DIGEST_CHANGED: "แฮชผนึกปัจจุบันไม่ตรงกับตอนที่สร้างไฟล์",
    EXPORT_FILE_CHANGED: "เนื้อไฟล์ไม่ตรงกับตอนที่สร้าง",
    EXPORT_FILE_MISSING: "ไม่พบไฟล์",
}


@dataclass(frozen=True)
class ExportManifest:
    file_name: str
    package_id: str
    run_id: str
    file_sha256: str
    universe_digest: str
    key_digest: str
    detector_digest: str
    created_at: str


def record_export(*, run_id: str, package_id: str, files, db_path=None) -> None:
    """บันทึกไฟล์ส่งออกของรอบ พร้อม digest ของผนึกสามชั้นที่ **ตรวจผ่าน ณ ตอนนี้**

    ``files`` = ลำดับของ ``(file_name, file_sha256)``
    """
    verification = seal_verification(run_id, db_path)
    if not verification.ok:
        raise KeyStageError("บันทึกไฟล์ส่งออกไม่ได้ — " + verification.summary())
    now = _now()
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        for name, sha in files:
            entry = audit.record_in(conn, "indicator_export_bound", "ind_export", name,
                                    {"run_id": run_id, "package_id": package_id,
                                     "file_sha256": sha,
                                     "universe_digest": verification.universe.sealed_digest,
                                     "key_digest": verification.key.sealed_digest,
                                     "detector_digest": verification.detector.sealed_digest})
            conn.execute(
                "INSERT INTO ind_export_manifests (file_name, package_id, run_id, "
                "file_sha256, universe_digest, key_digest, detector_digest, created_at, "
                "audit_seq, audit_entry_hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (name, package_id, run_id, sha, verification.universe.sealed_digest,
                 verification.key.sealed_digest, verification.detector.sealed_digest,
                 now, entry["seq"], entry["entry_hash"]))
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:      # noqa: BLE001
            pass
        raise
    finally:
        conn.close()


def export_manifest(file_name: str, db_path=None) -> "ExportManifest | None":
    conn = connect(db_path)
    try:
        r = conn.execute("SELECT * FROM ind_export_manifests WHERE file_name = ?",
                         (file_name,)).fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    return ExportManifest(file_name=r["file_name"], package_id=r["package_id"],
                          run_id=r["run_id"], file_sha256=r["file_sha256"],
                          universe_digest=r["universe_digest"], key_digest=r["key_digest"],
                          detector_digest=r["detector_digest"], created_at=r["created_at"])


def verify_export(run_id: str, file_name: str, current_file_sha256: str,
                  db_path=None) -> tuple:
    """ตรวจก่อนส่งไฟล์ — คืน ``(ok, reasons)``

    ต้องผ่านครบ: มีบันทึกผูก · เป็นของรอบนี้ · ผนึกตรวจผ่าน **ณ ตอนนี้** ·
    digest ของผนึกยังตรงกับตอนสร้างไฟล์ · เนื้อไฟล์ยังตรงกับตอนสร้าง
    """
    m = export_manifest(file_name, db_path)
    if m is None:
        return False, (EXPORT_NOT_BOUND,)
    if m.run_id != run_id:
        return False, (EXPORT_RUN_MISMATCH,)
    reasons: list[str] = []
    verification = seal_verification(run_id, db_path)
    if not verification.ok:
        reasons.append(EXPORT_SEALS_NOT_VERIFIED)
    if not (ku.digests_equal(verification.universe.current_digest, m.universe_digest)
            and ku.digests_equal(verification.key.current_digest, m.key_digest)
            and ku.digests_equal(verification.detector.current_digest, m.detector_digest)):
        reasons.append(EXPORT_SEAL_DIGEST_CHANGED)
    if not current_file_sha256:
        reasons.append(EXPORT_FILE_MISSING)
    elif not ku.digests_equal(current_file_sha256, m.file_sha256):
        reasons.append(EXPORT_FILE_CHANGED)
    return (not reasons), tuple(reasons)


def resolve_alias(indicator_id: str, db_path=None) -> str:
    """แปลง id เดิมที่ถูกรวมแล้วให้เป็น id หลัก — id ที่เผยแพร่ไปแล้วต้องเปิดกลับได้เสมอ"""
    _, aliases, _ = _pinned_ids(db_path)
    seen = set()
    current = indicator_id
    while current in aliases and current not in seen:
        seen.add(current)
        current = aliases[current]
    return current


__all__ = [
    "REGISTRY_VERSION", "DECISIONS", "DECISION_LABELS", "DECISION_ACCEPT",
    "DECISION_REJECT", "DECISION_AMBIGUOUS", "RunRow", "DecisionRow",
    "DecisionError", "IdentityView", "IND_SCHEMA_VERSION", "init_schema",
    "schema_version", "provisional_indicator_id", "save_run",
    "get_run", "list_runs", "observations", "mappings", "record_decision",
    "decisions", "latest_decisions", "indicator_ids", "resolve_identity",
    "identity_conflicts", "effective_bindings", "confirmed_same_edges", "resolve_alias",
    "KeyEntry", "KeySeal", "KeyStageError", "key_entries",
    "latest_key_entries", "key_digest", "key_seal", "seal_key", "adjudication_unlocked",
    "UniverseSeal", "DetectorSnapshot", "KeyAnswerRow",
    "build_key_universe", "key_universe", "universe_seal", "freeze_key_universe",
    "record_key_answer", "key_answers", "latest_key_answers", "key_coverage",
    "detector_snapshot", "seal_detector_snapshot", "detector_snapshot_preview",
    "SourceRow", "record_source_item", "retract_source_item", "source_inventory",
    "source_inventory_rows", "detector_coverage",
    "verify_universe_seal", "verify_key_seal", "verify_detector_snapshot",
    "seal_verification", "ExportManifest", "record_export", "export_manifest",
    "detector_projection_columns",
    "verify_export", "EXPORT_REASON_LABELS", "EXPORT_NOT_BOUND", "EXPORT_RUN_MISMATCH",
    "EXPORT_SEALS_NOT_VERIFIED", "EXPORT_SEAL_DIGEST_CHANGED", "EXPORT_FILE_CHANGED",
    "EXPORT_FILE_MISSING",
]
