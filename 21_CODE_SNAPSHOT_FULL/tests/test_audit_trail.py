# -*- coding: utf-8 -*-
"""ทดสอบ Audit Trail: เพิ่มอย่างเดียว สายโซ่แฮชต่อเนื่อง และจับการแก้ย้อนหลังได้"""
import sqlite3

import pytest

from redbook.storage import audit
from redbook.storage.db import connect


def test_chain_is_continuous(fresh_db):
    for i in range(5):
        audit.record("test_action", "thing", f"obj-{i}", {"i": i}, db_path=fresh_db)
    result = audit.verify_chain(fresh_db)
    assert result["ok"] is True
    assert result["checked"] == 5


def test_first_entry_links_to_genesis(fresh_db):
    e = audit.record("first", "thing", "obj", {}, db_path=fresh_db)
    assert e["prev_hash"] == audit.GENESIS


def test_update_and_delete_are_blocked(fresh_db):
    audit.record("a", "t", "o", {}, db_path=fresh_db)
    conn = connect(fresh_db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE audit_log SET actor = 'x'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM audit_log")
    finally:
        conn.close()


def test_tampering_is_detected(fresh_db):
    """แก้เนื้อหาโดยข้าม trigger (ปิด trigger ชั่วคราว) แล้วต้องตรวจจับได้"""
    for i in range(3):
        audit.record("a", "t", f"o{i}", {"i": i}, db_path=fresh_db)
    conn = connect(fresh_db)
    try:
        conn.execute("DROP TRIGGER audit_log_no_update")
        conn.execute("UPDATE audit_log SET detail_json = '{\"i\": 99}' WHERE seq = 2")
    finally:
        conn.close()
    result = audit.verify_chain(fresh_db)
    assert result["ok"] is False
    assert result["broken_at_seq"] == 2


def test_security_events_recorded(fresh_db):
    audit.security_event("upload_rejected_unknown_type", "warning",
                         {"why": "magic mismatch"}, client="127.0.0.1", db_path=fresh_db)
    rows = audit.security_events(db_path=fresh_db)
    assert len(rows) == 1
    assert rows[0]["event"] == "upload_rejected_unknown_type"
