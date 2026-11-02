# -*- coding: utf-8 -*-
"""ทะเบียนเอกสาร — ตัวตนของเอกสารคือ **content hash** ไม่ใช่ชื่อไฟล์

🔴 **คำสั่งกิ๊ฟ (9 ก.ย. 2569 · §3)** — *"never use filename alone as document
identity"* และ *"Do not expose absolute local paths or use file:// links in
shared reports"*

**กติกาที่บังคับในโค้ด**

* ``document_id = "doc_" + sha256(เนื้อไฟล์)[:16]`` — ไฟล์เดียวกันชื่อต่างกัน
  ⇒ document เดียว · ไฟล์ต่างกันชื่อเดียวกัน ⇒ คนละ document
* 🔴 **H1 — `document_id` เป็นเพียง *ฉลาก* ตัวตนที่พิสูจน์คือ `content_sha256` เต็ม**
  (Bo `5595832792` H1) · ทุกจุดที่ *ยืนยันตัวตน* เทียบแฮชเต็มเสมอ · ถ้า id ชนกัน
  (16 hex แรกตรงแต่เนื้อไฟล์ต่าง) ระบบ **ปฏิเสธและรายงาน** :class:`DocumentIdCollision`
  ไม่กลืนเป็นเอกสารเดียวกันเงียบ ๆ
* ขั้นเอกสาร (stage) · ปี · ผู้ออก (authority) · รุ่น เป็นค่าที่ **ผู้ลงทะเบียนประกาศ**
  ระบบไม่เดาจากชื่อไฟล์ · ไม่ประกาศ = ``UNSPECIFIED`` (มองเห็น ไม่ซ่อน)
* ``disclosure_class`` ไม่ประกาศ = ``UNKNOWN`` ⇒ **ถือเป็นเผยแพร่ไม่ได้** (fail closed)
* เส้นทางไฟล์จริงเก็บในคอลัมน์ ``local_path_private`` ของฐานข้อมูลในเครื่องเท่านั้น
  — ไม่มี view/report/export ใดคืนค่านี้ · route ใช้เพื่อเปิดสตรีมไฟล์แล้วทิ้ง
* ชื่อไฟล์ที่ผู้ใช้ส่งมาเก็บเป็น *alias* (ชื่อไฟล์ล้วน ไม่มีเส้นทาง) เพื่อให้คนจำได้
  แต่ **ไม่ใช่ตัวตน** และ **ไม่ออกไปในไฟล์ส่งออก**

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .. import holdout, sealed_key
from ..storage.db import connect
from ..storage.files import sanitize_display_name

DOCUMENTS_VERSION = "evidence-documents-0.2.0"

# ── ขั้นเอกสาร (ประกาศโดยผู้ลงทะเบียน · ไม่เดาจากชื่อไฟล์) ──────────────────
STAGE_BUDGET_REQUEST = "BUDGET_REQUEST"      # คำขอ (ยังไม่เผยแพร่)
STAGE_DRAFT_BILL = "DRAFT_BILL"              # ร่าง พ.ร.บ. (เผยแพร่แล้ว)
STAGE_ENACTED_ACT = "ENACTED_ACT"            # พ.ร.บ. (เผยแพร่แล้ว)
STAGE_AO_REDBOOK = "AO_REDBOOK"              # เอกสารคาดแดง
STAGE_AO_BLUEBOOK = "AO_BLUEBOOK"            # เล่มฟ้า
STAGE_SYNTHETIC_TEST = "SYNTHETIC_TEST"      # fixture สังเคราะห์
STAGE_UNSPECIFIED = "UNSPECIFIED"

STAGES = (STAGE_BUDGET_REQUEST, STAGE_DRAFT_BILL, STAGE_ENACTED_ACT,
          STAGE_AO_REDBOOK, STAGE_AO_BLUEBOOK, STAGE_SYNTHETIC_TEST,
          STAGE_UNSPECIFIED)

STAGE_LABELS = {
    STAGE_BUDGET_REQUEST: "คำขอตั้งงบประมาณ",
    STAGE_DRAFT_BILL: "ร่างพระราชบัญญัติงบประมาณ",
    STAGE_ENACTED_ACT: "พระราชบัญญัติงบประมาณ",
    STAGE_AO_REDBOOK: "เอกสารคาดแดง (AO)",
    STAGE_AO_BLUEBOOK: "เล่มฟ้า",
    STAGE_SYNTHETIC_TEST: "ชุดทดสอบสังเคราะห์",
    STAGE_UNSPECIFIED: "ยังไม่ระบุขั้นเอกสาร",
}

# ── ชั้นการเปิดเผย (fail closed) ────────────────────────────────────────────
DISC_PUBLIC = "PUBLIC_PUBLISHED"
DISC_INTERNAL = "INTERNAL_NOT_PUBLISHED"
DISC_SYNTHETIC = "SYNTHETIC"
DISC_UNKNOWN = "UNKNOWN"
DISCLOSURE_CLASSES = (DISC_PUBLIC, DISC_INTERNAL, DISC_SYNTHETIC, DISC_UNKNOWN)

DISCLOSURE_LABELS = {
    DISC_PUBLIC: "เผยแพร่สาธารณะแล้ว",
    DISC_INTERNAL: "ภายใน — ยังไม่เผยแพร่",
    DISC_SYNTHETIC: "สังเคราะห์ (ไม่ใช่เอกสารจริง)",
    DISC_UNKNOWN: "ไม่ทราบ — ถือว่าเผยแพร่ไม่ได้",
}

#: ชั้นที่อนุญาตให้ *ข้อความจากเอกสาร* ออกไปในไฟล์/รายงานที่แชร์ได้
SHAREABLE_DISCLOSURE = frozenset({DISC_PUBLIC, DISC_SYNTHETIC})

MEDIA_PDF = "application/pdf"
MEDIA_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS evd_documents (
    document_id            TEXT PRIMARY KEY,
    content_sha256         TEXT NOT NULL UNIQUE,
    byte_size              INTEGER NOT NULL,
    media_type             TEXT NOT NULL,
    page_count             INTEGER,
    title                  TEXT NOT NULL DEFAULT '',
    stage                  TEXT NOT NULL DEFAULT 'UNSPECIFIED',
    fiscal_year            INTEGER,
    authority              TEXT NOT NULL DEFAULT '',
    agency_label           TEXT NOT NULL DEFAULT '',
    version_label          TEXT NOT NULL DEFAULT '',
    disclosure_class       TEXT NOT NULL DEFAULT 'UNKNOWN',
    text_layer_status      TEXT NOT NULL DEFAULT 'TEXT_LAYER_NOT_CHECKED_NO_BACKEND',
    text_backend           TEXT NOT NULL DEFAULT '',
    -- 🔴 ส่วนตัว: ไม่มี view/report/export ใดคืนค่านี้
    local_path_private     TEXT NOT NULL,
    registered_at          TEXT NOT NULL,
    registered_by          TEXT NOT NULL DEFAULT '',
    registry_version       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evd_document_aliases (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id    TEXT NOT NULL REFERENCES evd_documents(document_id),
    alias_redacted TEXT NOT NULL,
    seen_at        TEXT NOT NULL
);
"""


def init_schema(db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA)
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path) -> tuple[str, int]:
    """แฮชเนื้อไฟล์แบบสตรีม — เรียกด่านทั้งสองก่อนเปิด"""
    p = Path(path)
    holdout.assert_not_holdout(p)
    sealed_key.assert_not_sealed(p)
    h = hashlib.sha256()
    size = 0
    with open(p, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            h.update(chunk)
    return h.hexdigest(), size


#: ความยาวของส่วนแฮชใน ``document_id`` — ฉลากสำหรับ URL/สายตา ไม่ใช่ข้อพิสูจน์ตัวตน
DOCUMENT_ID_HASH_LEN = 16


def document_id_for(content_sha256: str) -> str:
    """ฉลากของเอกสาร — 🔴 **ไม่ใช่ข้อพิสูจน์ตัวตน** ใช้ ``content_sha256`` เต็มเสมอเมื่อพิสูจน์"""
    if not content_sha256 or len(content_sha256) < 64:
        raise ValueError("document_id ต้องคำนวณจากแฮชเต็ม 64 hex")
    return "doc_" + content_sha256[:DOCUMENT_ID_HASH_LEN]


class DocumentIdCollision(Exception):
    """สองไฟล์ที่เนื้อต่างกันให้ ``document_id`` เดียวกัน (ฉลาก 16 hex ชน) — **ปฏิเสธ**

    🔴 ปฏิเสธแทนที่จะกลืนเป็นเอกสารเดียวกัน เพราะการกลืนแปลว่าหลักฐานสองฉบับถูกอ้างด้วย
    รหัสเดียว ⇒ ผู้ตรวจเปิดผิดฉบับโดยไม่รู้ตัว · ทางแก้คือขยาย ``DOCUMENT_ID_HASH_LEN``
    ซึ่งเป็นการเปลี่ยน schema ที่ต้องประกาศ ไม่ใช่การเดาในโค้ด
    """

    def __init__(self, document_id: str, existing_sha256: str, incoming_sha256: str):
        self.document_id = document_id
        self.existing_sha256 = existing_sha256
        self.incoming_sha256 = incoming_sha256
        super().__init__(
            f"document_id {document_id} ชนกัน — แฮชเต็มต่างกัน "
            f"({existing_sha256[:24]}… vs {incoming_sha256[:24]}…)")


@dataclass(frozen=True)
class DocumentRecord:
    """มุมมองที่แชร์ได้ของเอกสาร — **ไม่มีเส้นทางไฟล์**"""
    document_id: str
    content_sha256: str
    byte_size: int
    media_type: str
    page_count: int | None
    title: str
    stage: str
    fiscal_year: int | None
    authority: str
    agency_label: str
    version_label: str
    disclosure_class: str
    text_layer_status: str
    text_backend: str
    registered_at: str
    registered_by: str
    registry_version: str

    @property
    def stage_label(self) -> str:
        return STAGE_LABELS.get(self.stage, self.stage)

    @property
    def disclosure_label(self) -> str:
        return DISCLOSURE_LABELS.get(self.disclosure_class, self.disclosure_class)

    @property
    def shareable(self) -> bool:
        return self.disclosure_class in SHAREABLE_DISCLOSURE

    @property
    def short_hash(self) -> str:
        return self.content_sha256[:12]

    @property
    def is_pdf(self) -> bool:
        return self.media_type == MEDIA_PDF


_PUBLIC_COLUMNS = (
    "document_id", "content_sha256", "byte_size", "media_type", "page_count",
    "title", "stage", "fiscal_year", "authority", "agency_label", "version_label",
    "disclosure_class", "text_layer_status", "text_backend", "registered_at",
    "registered_by", "registry_version",
)


def _record(row) -> DocumentRecord:
    return DocumentRecord(**{c: row[c] for c in _PUBLIC_COLUMNS})


def _validate(stage: str, disclosure_class: str, media_type: str) -> None:
    if stage not in STAGES:
        raise ValueError(f"ขั้นเอกสารไม่รู้จัก: {stage!r}")
    if disclosure_class not in DISCLOSURE_CLASSES:
        raise ValueError(f"ชั้นการเปิดเผยไม่รู้จัก: {disclosure_class!r}")
    if media_type not in (MEDIA_PDF, MEDIA_XLSX):
        raise ValueError("ชนิดสื่อไม่รองรับ")


def register(path, *, media_type: str, title: str = "", stage: str = STAGE_UNSPECIFIED,
             fiscal_year: int | None = None, authority: str = "",
             agency_label: str = "", version_label: str = "",
             disclosure_class: str = DISC_UNKNOWN, page_count: int | None = None,
             text_layer_status: str = "TEXT_LAYER_NOT_CHECKED_NO_BACKEND",
             text_backend: str = "", registered_by: str = "",
             db_path=None) -> tuple[DocumentRecord, bool]:
    """ลงทะเบียนไฟล์ · คืน ``(record, created)`` — ไฟล์เนื้อเดียวกันคืน record เดิม

    การลงทะเบียนซ้ำ **ไม่เขียนทับ** metadata ที่ประกาศไว้ก่อน (immutable source
    observation) · เพิ่มได้เพียง alias ของชื่อไฟล์
    """
    _validate(stage, disclosure_class, media_type)
    p = Path(path).resolve()
    digest, size = sha256_file(p)
    doc_id = document_id_for(digest)
    # alias = ชื่อไฟล์ล้วน ไม่มีเส้นทาง (แบบเดียวกับ files.original_name) · ไม่ใช่ตัวตน
    alias = sanitize_display_name(p.name)
    now = _now()
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM evd_documents WHERE document_id = ?",
                           (doc_id,)).fetchone()
        created = row is None
        # 🔴 H1 — ฉลากเดียวกันต้องมาจากแฮชเต็มเดียวกันเท่านั้น
        if row is not None and row["content_sha256"] != digest:
            raise DocumentIdCollision(doc_id, row["content_sha256"], digest)
        if created:
            conn.execute(
                "INSERT INTO evd_documents (document_id, content_sha256, byte_size, "
                "media_type, page_count, title, stage, fiscal_year, authority, "
                "agency_label, version_label, disclosure_class, text_layer_status, "
                "text_backend, local_path_private, registered_at, registered_by, "
                "registry_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (doc_id, digest, size, media_type, page_count, title, stage,
                 fiscal_year, authority, agency_label, version_label,
                 disclosure_class, text_layer_status, text_backend, str(p), now,
                 registered_by, DOCUMENTS_VERSION))
        conn.execute(
            "INSERT INTO evd_document_aliases (document_id, alias_redacted, seen_at) "
            "VALUES (?,?,?)", (doc_id, alias, now))
        row = conn.execute("SELECT * FROM evd_documents WHERE document_id = ?",
                           (doc_id,)).fetchone()
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return _record(row), created


def get_by_sha256(content_sha256: str, db_path=None) -> DocumentRecord | None:
    """ค้นเอกสารด้วย **แฮชเต็ม** — ทางเดียวที่ถือว่าเป็นการพิสูจน์ตัวตน (H1)"""
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM evd_documents WHERE content_sha256 = ?",
                           (content_sha256,)).fetchone()
    finally:
        conn.close()
    return _record(row) if row else None


def verify_identity(document_id: str, content_sha256: str, db_path=None) -> bool:
    """ยืนยันว่า ``document_id`` นี้คือเอกสารที่มีแฮชเต็มตามที่อ้าง — เทียบเต็มเสมอ"""
    rec = get(document_id, db_path)
    return bool(rec) and rec.content_sha256 == content_sha256


def get(document_id: str, db_path=None) -> DocumentRecord | None:
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM evd_documents WHERE document_id = ?",
                           (document_id,)).fetchone()
    finally:
        conn.close()
    return _record(row) if row else None


def aliases(document_id: str, db_path=None) -> list[str]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT alias_redacted FROM evd_document_aliases WHERE document_id = ? "
            "ORDER BY seq", (document_id,)).fetchall()
    finally:
        conn.close()
    seen: list[str] = []
    for r in rows:
        if r["alias_redacted"] not in seen:
            seen.append(r["alias_redacted"])
    return seen


def list_all(db_path=None) -> list[DocumentRecord]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM evd_documents ORDER BY registered_at, document_id").fetchall()
    finally:
        conn.close()
    return [_record(r) for r in rows]


class SourceUnavailable(Exception):
    """เอกสารลงทะเบียนไว้ แต่ไฟล์ต้นทางไม่อยู่ที่เดิมแล้ว หรือเนื้อไม่ตรงแฮชที่ลงทะเบียน"""

    def __init__(self, document_id: str, reason: str):
        self.document_id = document_id
        self.reason = reason
        super().__init__(f"{document_id}: {reason}")


REASON_MISSING = "source_file_missing"
REASON_HASH_MISMATCH = "source_hash_mismatch"


def open_path_private(document_id: str, *, verify_hash: bool = True,
                      db_path=None) -> Path:
    """เส้นทางไฟล์จริง — **ใช้เฉพาะเพื่อเปิดสตรีม/อ่านชั้นข้อความ แล้วทิ้งทันที**

    🔴 ห้ามส่งค่าที่คืนจากฟังก์ชันนี้ไปยัง template · log · export · URL ใด ๆ
    ตรวจแฮชซ้ำก่อนใช้ เพราะไฟล์ในโฟลเดอร์ผู้ใช้ถูกแทนที่ได้โดยระบบไม่รู้
    """
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT local_path_private, content_sha256 FROM evd_documents "
            "WHERE document_id = ?", (document_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise SourceUnavailable(document_id, "not_registered")
    p = Path(row["local_path_private"])
    if not p.is_file():
        raise SourceUnavailable(document_id, REASON_MISSING)
    if verify_hash:
        digest, _ = sha256_file(p)
        if digest != row["content_sha256"]:
            raise SourceUnavailable(document_id, REASON_HASH_MISMATCH)
    return p


__all__ = [
    "DOCUMENTS_VERSION", "STAGES", "STAGE_LABELS", "STAGE_BUDGET_REQUEST",
    "STAGE_DRAFT_BILL", "STAGE_ENACTED_ACT", "STAGE_AO_REDBOOK",
    "STAGE_AO_BLUEBOOK", "STAGE_SYNTHETIC_TEST", "STAGE_UNSPECIFIED",
    "DISCLOSURE_CLASSES", "DISCLOSURE_LABELS", "DISC_PUBLIC", "DISC_INTERNAL",
    "DISC_SYNTHETIC", "DISC_UNKNOWN", "SHAREABLE_DISCLOSURE", "MEDIA_PDF",
    "MEDIA_XLSX", "DocumentRecord", "SourceUnavailable", "DocumentIdCollision",
    "DOCUMENT_ID_HASH_LEN", "REASON_MISSING",
    "REASON_HASH_MISMATCH", "init_schema", "sha256_file", "document_id_for",
    "register", "get", "get_by_sha256", "verify_identity", "aliases", "list_all",
    "open_path_private",
]
