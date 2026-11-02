# -*- coding: utf-8 -*-
"""ด่านของคำตัดสิน — stale · กติกาเปลี่ยนสถานะ · สิทธิ์ลบ · audit linkage

🔴 **คำสั่งกิ๊ฟ (7 ก.ย. 2569 · ข้อ B.1–B.4)** — ล็อก schema ก่อนทำ UI

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานทุกไฟล์ในชุดนี้แต่งขึ้นทั้งหมด

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import sqlite3

import pytest

from redbook.services import decisions as dec
from redbook.services import t1b as svc
from redbook.storage import audit, t1b_decisions as drepo, t1b_repo
from redbook.storage.db import connect, init_db
from t1b_synth import build_workbook, records

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "g.sqlite3"
    init_db(p)
    t1b_repo.init_t1b_schema(p)
    return p


def _make_run(tmp_path, db, run_id, invest=12.0):
    base = records(build_workbook(tmp_path, filename=f"{run_id}_a.xlsx",
                                  agency="สถาบันทดสอบ", cover_year=2569,
                                  section_title=TITLE))
    curr = records(build_workbook(tmp_path, filename=f"{run_id}_b.xlsx",
                                  agency="สถาบันทดสอบ", cover_year=2570,
                                  section_title=TITLE, invest=invest))
    view = svc.run_from_records(base, curr, run_id=run_id)
    t1b_repo.save_run(view, run_id=run_id, db_path=db)
    return view


@pytest.fixture()
def run(tmp_path, db):
    return _make_run(tmp_path, db, "G-1")


def _amt(view):
    return next(f for f in view.findings if f.finding_type.startswith("AMOUNT_"))


def _seq(run_id, f, db):
    return drepo.latest_seq_for(run_id, f.finding_id, db_path=db)


# ══════════════════════════════════════════════════════════════════════════════
#  B.1 — คำตัดสินค้าง (stale) ต้องถูกปฏิเสธ
# ══════════════════════════════════════════════════════════════════════════════

def test_first_decision_expects_seq_zero(db, run):
    f = _amt(run)
    d = dec.record(run, f, dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    assert d.seq >= 1


def test_two_tabs_second_one_is_stale(db, run):
    """แท็บ A และ B โหลดตอน seq=0 · A บันทึกก่อน · B ต้องถูกปฏิเสธ"""
    f = _amt(run)
    seen_by_both = _seq("G-1", f, db)                  # 0
    dec.record(run, f, dec.CONFIRMED, expected_latest_seq=seen_by_both, db_path=db)
    with pytest.raises(dec.StaleDecisionError) as e:
        dec.record(run, f, dec.DISMISSED, note="ไม่ใช่ประเด็น",
                   expected_latest_seq=seen_by_both, db_path=db)
    assert e.value.expected == 0 and e.value.actual >= 1
    assert "โหลดสถานะล่าสุด" in str(e.value)
    assert len(drepo.list_for_finding("G-1", f.finding_id, db_path=db)) == 1


def test_stale_rejection_writes_nothing_to_audit(db, run):
    """ปฏิเสธแล้วต้องไม่มีร่องรอยครึ่ง ๆ — ทั้งคำตัดสินและ audit"""
    f = _amt(run)
    dec.record(run, f, dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    n_audit = len(audit.entries(limit=500, db_path=db))
    with pytest.raises(dec.StaleDecisionError):
        dec.record(run, f, dec.UNRESOLVED, note="x", expected_latest_seq=0,
                   db_path=db)
    assert len(audit.entries(limit=500, db_path=db)) == n_audit


def test_after_reload_the_decision_goes_through(db, run):
    f = _amt(run)
    dec.record(run, f, dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    fresh = _seq("G-1", f, db)
    d = dec.record(run, f, dec.DISMISSED, note="ตรวจซ้ำแล้วไม่ใช่ประเด็น",
                   expected_latest_seq=fresh, db_path=db)
    assert d.status_from == dec.CONFIRMED and d.status_to == dec.DISMISSED


def test_status_from_always_equals_the_real_latest(db, run):
    """ห้ามสร้างคำตัดสินจาก status_from ที่ไม่ตรงกับแถวล่าสุด"""
    f = _amt(run)
    dec.record(run, f, dec.UNRESOLVED, note="a", expected_latest_seq=0, db_path=db)
    dec.record(run, f, dec.CONFIRMED, note="b", expected_latest_seq=_seq("G-1", f, db),
               db_path=db)
    hist = drepo.list_for_finding("G-1", f.finding_id, db_path=db)
    for prev, cur in zip(hist, hist[1:]):
        assert cur.status_from == prev.status_to


# ══════════════════════════════════════════════════════════════════════════════
#  B.2 — กติกาการเปลี่ยนสถานะ
# ══════════════════════════════════════════════════════════════════════════════

def test_reversing_a_decision_requires_a_note_even_to_confirmed(db, run):
    f = _amt(run)
    dec.record(run, f, dec.DISMISSED, note="ไม่ใช่ประเด็น", expected_latest_seq=0,
               db_path=db)
    with pytest.raises(dec.DecisionError, match="กลับคำตัดสินเดิม"):
        dec.record(run, f, dec.CONFIRMED, expected_latest_seq=_seq("G-1", f, db),
                   db_path=db)
    d = dec.record(run, f, dec.CONFIRMED, note="พบหลักฐานเพิ่ม",
                   expected_latest_seq=_seq("G-1", f, db), db_path=db)
    assert d.status_to == dec.CONFIRMED


def test_repeating_the_same_decision_creates_no_row(db, run):
    f = _amt(run)
    dec.record(run, f, dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    with pytest.raises(dec.NoChangeDecision):
        dec.record(run, f, dec.CONFIRMED, expected_latest_seq=_seq("G-1", f, db),
                   db_path=db)
    assert len(drepo.list_for_finding("G-1", f.finding_id, db_path=db)) == 1


def test_same_status_with_a_new_note_is_a_new_row(db, run):
    f = _amt(run)
    dec.record(run, f, dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    d = dec.record(run, f, dec.CONFIRMED, note="เพิ่มหมายเหตุ",
                   expected_latest_seq=_seq("G-1", f, db), db_path=db)
    assert d.seq > 1 and d.note == "เพิ่มหมายเหตุ"


def test_engine_values_are_frozen_across_every_version(db, run):
    f = _amt(run)
    dec.record(run, f, dec.UNRESOLVED, note="a", expected_latest_seq=0, db_path=db)
    dec.record(run, f, dec.CONFIRMED_WITH_EDIT, note="b", corrected_value="99",
               expected_latest_seq=_seq("G-1", f, db), db_path=db)
    dec.record(run, f, dec.DISMISSED, note="c",
               expected_latest_seq=_seq("G-1", f, db), db_path=db)
    hist = drepo.list_for_finding("G-1", f.finding_id, db_path=db)
    engines = {(d.engine_finding_type, d.engine_baseline_value,
                d.engine_current_value, d.engine_difference) for d in hist}
    assert len(engines) == 1
    assert engines.pop()[2] == f.current_value


def test_a_rerun_with_different_engine_values_is_refused_not_overwritten(db, run):
    f = _amt(run)
    dec.record(run, f, dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    changed = type(f)(**{**f.__dict__, "current_value": "777.0000"})
    with pytest.raises(dec.DecisionError, match="รันใหม่ทับ"):
        dec.record(run, changed, dec.DISMISSED, note="x",
                   expected_latest_seq=_seq("G-1", f, db), db_path=db)


def test_confirmed_with_edit_needs_field_value_and_note(db, run):
    f = _amt(run)
    d = dec.record(run, f, dec.CONFIRMED_WITH_EDIT, note="แก้ตามต้นฉบับ",
                   corrected_value="12.50", expected_latest_seq=0, db_path=db)
    assert d.corrected_field == "current_value"
    assert d.corrected_value == "12.50" and d.note


@pytest.mark.parametrize("status", [dec.CONFIRMED, dec.UNRESOLVED, dec.DISMISSED])
def test_other_statuses_never_store_a_corrected_value(db, run, status):
    f = _amt(run)
    d = dec.record(run, f, status, note="เหตุผล", expected_latest_seq=0,
                   db_path=db)
    assert d.corrected_field == "" and d.corrected_value == ""


# ══════════════════════════════════════════════════════════════════════════════
#  B.3 — สิทธิ์ลบ: ใช้ครั้งเดียว · ผูก run · หมดอายุ · เฉพาะธุรกรรม retention
# ══════════════════════════════════════════════════════════════════════════════

def test_schema_is_version_3_with_bound_unlock(db):
    conn = connect(db)
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(t1b_retention_unlock)")}
        v = conn.execute("SELECT MAX(version) v FROM t1b_schema_migrations").fetchone()["v"]
    finally:
        conn.close()
    assert v == 3
    assert {"run_id", "expires_at", "consumed_at"} <= cols


def test_direct_delete_is_refused(db, run):
    dec.record(run, _amt(run), dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    conn = connect(db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM t1b_decisions")
    finally:
        conn.close()


def test_unlock_for_another_run_does_not_open_this_one(tmp_path, db, run):
    other = _make_run(tmp_path, db, "G-2", invest=13.0)
    dec.record(run, _amt(run), dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    conn = connect(db)
    try:
        conn.execute("BEGIN")
        drepo.open_retention_unlock(conn, "G-2", "test")       # ผูกกับ G-2
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM t1b_decisions WHERE run_id = 'G-1'")
        conn.execute("ROLLBACK")
    finally:
        conn.close()
    assert other.summary.run_id == "G-2"
    assert drepo.stale_unlocks(db_path=db) == 0, "ROLLBACK ต้องพาโทเคนหายไปด้วย"


def test_consumed_unlock_cannot_be_reused(db, run):
    dec.record(run, _amt(run), dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    conn = connect(db)
    try:
        conn.execute("BEGIN")
        token = drepo.open_retention_unlock(conn, "G-1", "test")
        drepo.consume_retention_unlock(conn, token)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM t1b_decisions WHERE run_id = 'G-1'")
        conn.execute("ROLLBACK")
    finally:
        conn.close()


def test_expired_unlock_does_not_open(db, run):
    dec.record(run, _amt(run), dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    conn = connect(db)
    try:
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO t1b_retention_unlock "
            "(token, run_id, opened_at, expires_at, consumed_at, reason) VALUES "
            "('old', 'G-1', '2000-01-01 00:00:00', '2000-01-01 00:01:00', NULL, 'x')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM t1b_decisions WHERE run_id = 'G-1'")
        conn.execute("ROLLBACK")
    finally:
        conn.close()


def test_retention_delete_path_works_and_leaves_no_unlock(db, run):
    dec.record(run, _amt(run), dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    t1b_repo.delete_run("G-1", db_path=db)
    assert drepo.list_for_run("G-1", db_path=db) == []
    assert drepo.stale_unlocks(db_path=db) == 0


def test_failed_retention_delete_rolls_back_everything(db, run, monkeypatch):
    """ล้มกลางทาง ⇒ ไม่เหลือข้อมูลครึ่งหนึ่ง และไม่เหลือสิทธิ์ค้าง"""
    dec.record(run, _amt(run), dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    real = drepo.consume_retention_unlock

    def boom(conn, token):
        real(conn, token)
        raise RuntimeError("จำลองความล้มเหลวหลังลบ")

    monkeypatch.setattr(drepo, "consume_retention_unlock", boom)
    with pytest.raises(RuntimeError):
        t1b_repo.delete_run("G-1", db_path=db)
    assert t1b_repo.get_run("G-1", db_path=db) is not None
    assert len(drepo.list_for_run("G-1", db_path=db)) == 1
    assert drepo.stale_unlocks(db_path=db) == 0


# ══════════════════════════════════════════════════════════════════════════════
#  B.4 — audit linkage
# ══════════════════════════════════════════════════════════════════════════════

def test_decision_and_audit_are_one_transaction(db, run, monkeypatch):
    """ถ้าเขียนคำตัดสินล้มหลัง audit เขียนแล้ว audit ต้องไม่เหลือค้าง"""
    f = _amt(run)
    n_before = len(audit.entries(limit=500, db_path=db))
    real = drepo.audit.record_in

    def poisoned(conn, *a, **k):
        out = real(conn, *a, **k)
        conn.execute("INSERT INTO t1b_decisions (id) VALUES (NULL)")  # ล้มแน่
        return out

    monkeypatch.setattr(drepo.audit, "record_in", poisoned)
    with pytest.raises(sqlite3.IntegrityError):
        dec.record(run, f, dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    assert len(audit.entries(limit=500, db_path=db)) == n_before
    assert drepo.list_for_finding("G-1", f.finding_id, db_path=db) == []


def test_audit_failure_means_no_decision(db, run, monkeypatch):
    f = _amt(run)

    def refuse(*a, **k):
        raise RuntimeError("audit ล้ม")

    monkeypatch.setattr(drepo.audit, "record_in", refuse)
    with pytest.raises(RuntimeError):
        dec.record(run, f, dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    assert drepo.list_for_finding("G-1", f.finding_id, db_path=db) == []


def test_audit_seq_forged_from_another_run_is_detected(tmp_path, db, run):
    other = _make_run(tmp_path, db, "G-2", invest=13.0)
    d_other = dec.record(other, _amt(other), dec.CONFIRMED, expected_latest_seq=0,
                         db_path=db)
    conn = connect(db)
    try:
        conn.execute(
            "INSERT INTO t1b_decisions (id, run_id, finding_id, identity_basis, "
            " status_from, status_to, decided_at, audit_seq, audit_entry_hash) "
            "VALUES ('forged', 'G-1', ?, 'content', 'PENDING', 'CONFIRMED', "
            " '2026-09-07T00:00:00+00:00', ?, ?)",
            (_amt(run).finding_id, d_other.audit_seq, d_other.audit_entry_hash))
    finally:
        conn.close()
    rep = drepo.verify_audit_links("G-1", db_path=db)
    assert not rep["ok"]
    assert rep["reasons"]["forged"] in ("audit_belongs_to_other_object",
                                        "audit_belongs_to_other_run")


def _drop_audit_guards(db):
    conn = connect(db)
    try:
        conn.execute("DROP TRIGGER IF EXISTS audit_log_no_update")
        conn.execute("DROP TRIGGER IF EXISTS audit_log_no_delete")
    finally:
        conn.close()


def test_chain_detects_an_edit(db, run):
    dec.record(run, _amt(run), dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    assert audit.verify_chain(db_path=db)["ok"]
    _drop_audit_guards(db)
    conn = connect(db)
    try:
        conn.execute("UPDATE audit_log SET detail_json = '{}' WHERE seq = 1")
    finally:
        conn.close()
    assert not audit.verify_chain(db_path=db)["ok"]


def test_chain_detects_a_deletion(db, run):
    f = _amt(run)
    dec.record(run, f, dec.UNRESOLVED, note="a", expected_latest_seq=0, db_path=db)
    dec.record(run, f, dec.CONFIRMED, note="b", expected_latest_seq=_seq("G-1", f, db),
               db_path=db)
    _drop_audit_guards(db)
    conn = connect(db)
    try:
        conn.execute("DELETE FROM audit_log WHERE seq = 1")
    finally:
        conn.close()
    assert not audit.verify_chain(db_path=db)["ok"]


def test_chain_detects_a_reorder(db, run):
    f = _amt(run)
    dec.record(run, f, dec.UNRESOLVED, note="a", expected_latest_seq=0, db_path=db)
    dec.record(run, f, dec.CONFIRMED, note="b", expected_latest_seq=_seq("G-1", f, db),
               db_path=db)
    _drop_audit_guards(db)
    conn = connect(db)
    try:
        a = dict(conn.execute("SELECT * FROM audit_log WHERE seq = 1").fetchone())
        b = dict(conn.execute("SELECT * FROM audit_log WHERE seq = 2").fetchone())
        for src, dst in ((b, 1), (a, 2)):
            conn.execute(
                "UPDATE audit_log SET ts=?, action=?, object_id=?, detail_json=?, "
                "prev_hash=?, entry_hash=? WHERE seq=?",
                (src["ts"], src["action"], src["object_id"], src["detail_json"],
                 src["prev_hash"], src["entry_hash"], dst))
    finally:
        conn.close()
    assert not audit.verify_chain(db_path=db)["ok"]


def test_healthy_run_verifies_on_all_three_layers(db, run):
    f = _amt(run)
    dec.record(run, f, dec.CONFIRMED, expected_latest_seq=0, db_path=db)
    rep = drepo.verify_audit_links("G-1", db_path=db)
    assert rep["ok"] and rep["total"] == 1
    assert audit.verify_chain(db_path=db)["ok"]
