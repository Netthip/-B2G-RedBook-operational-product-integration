# -*- coding: utf-8 -*-
"""คำตัดสินของมนุษย์ — schema · migration · กติกา · โซ่ audit

🔴 **คำตัดสินกิ๊ฟ (7 ก.ย. 2569)** — สี่สถานะ · append-only ·
`CONFIRMED` ไม่บังคับเหตุผล · อีกสามสถานะบังคับ ·
`identity_basis = position` ตัดสินได้แต่ต้องติดธง `not_rebindable` ·
ค่าที่เครื่องยนต์เสนอต้องเหลืออยู่เสมอแม้มนุษย์จะแก้

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
def _rec(view, f, status, db, **kw):
    """บันทึกโดยอ่าน seq ล่าสุดก่อนเสมอ — ชุดนี้ไม่ได้ทดสอบเรื่อง stale"""
    seq = drepo.latest_seq_for(view.summary.run_id, f.finding_id, db_path=db)
    return dec.record(view, f, status, expected_latest_seq=seq, db_path=db, **kw)


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "d.sqlite3"
    init_db(p)
    t1b_repo.init_t1b_schema(p)
    return p


@pytest.fixture()
def run(tmp_path, db):
    base = records(build_workbook(tmp_path, filename="a.xlsx",
                                  agency="สถาบันทดสอบ", cover_year=2569,
                                  section_title=TITLE))
    curr = records(build_workbook(tmp_path, filename="b.xlsx",
                                  agency="สถาบันทดสอบ", cover_year=2570,
                                  section_title=TITLE, invest=12.0))
    view = svc.run_from_records(base, curr, run_id="DEC-1")
    t1b_repo.save_run(view, run_id="DEC-1", db_path=db)
    return view


def _amount_finding(view):
    return next(f for f in view.findings if f.finding_type.startswith("AMOUNT_"))


# ══════════════════════════════════════════════════════════════════════════════
#  S1 — schema และ migration
# ══════════════════════════════════════════════════════════════════════════════

def test_migration_creates_the_table_on_an_existing_database(tmp_path):
    """ฐานข้อมูลเดิมที่ยังไม่มีตารางนี้ ต้องได้ตารางเพิ่มโดยไม่เสียข้อมูลเดิม"""
    p = tmp_path / "old.sqlite3"
    init_db(p)
    conn = connect(p)
    try:
        conn.execute("DROP TABLE IF EXISTS t1b_decisions")
    finally:
        conn.close()

    t1b_repo.init_t1b_schema(p)
    conn = connect(p)
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(t1b_decisions)")}
        version = conn.execute(
            "SELECT MAX(version) v FROM t1b_schema_migrations").fetchone()["v"]
    finally:
        conn.close()
    assert version == t1b_repo.T1B_SCHEMA_VERSION == 3
    for required in ("status_from", "status_to", "engine_baseline_value",
                     "engine_current_value", "corrected_value", "note",
                     "decided_at", "audit_seq", "audit_entry_hash",
                     "file_a_sha256", "not_rebindable", "subject_category"):
        assert required in cols, required


def test_table_has_no_current_status_column(db):
    """สถานะปัจจุบันต้องคำนวณจากประวัติ — เก็บเป็นคอลัมน์เมื่อใดก็ขัดกันเองได้"""
    conn = connect(db)
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(t1b_decisions)")}
    finally:
        conn.close()
    assert "current_status" not in cols
    assert "status" not in cols


def test_rows_cannot_be_updated(db, run):
    d = _rec(run, _amount_finding(run), dec.CONFIRMED, db)
    conn = connect(db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE t1b_decisions SET note = 'x' WHERE id = ?",
                         (d.id,))
    finally:
        conn.close()


def test_rows_cannot_be_deleted_outside_the_retention_path(db, run):
    _rec(run, _amount_finding(run), dec.CONFIRMED, db)
    conn = connect(db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM t1b_decisions")
    finally:
        conn.close()


def test_retention_path_can_delete_and_closes_the_door_again(db, run):
    _rec(run, _amount_finding(run), dec.CONFIRMED, db)
    t1b_repo.delete_run("DEC-1", db_path=db)
    assert drepo.list_for_run("DEC-1", db_path=db) == []

    conn = connect(db)
    try:
        assert conn.execute(
            "SELECT COUNT(*) n FROM t1b_retention_unlock").fetchone()["n"] == 0
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  S2 — กติกาของสถานะ
# ══════════════════════════════════════════════════════════════════════════════

def test_confirmed_does_not_require_a_note():
    assert dec.validate(dec.CONFIRMED) == ("", "")


@pytest.mark.parametrize("status", [dec.UNRESOLVED, dec.DISMISSED])
def test_these_statuses_require_a_note(status):
    with pytest.raises(dec.DecisionError, match="เหตุผล"):
        dec.validate(status)
    assert dec.validate(status, note="มีเหตุผล")[0] == "มีเหตุผล"


def test_confirmed_with_edit_requires_both_a_note_and_a_value():
    with pytest.raises(dec.DecisionError, match="เหตุผล"):
        dec.validate(dec.CONFIRMED_WITH_EDIT, corrected_value="9")
    with pytest.raises(dec.DecisionError, match="ค่าที่แก้ไข"):
        dec.validate(dec.CONFIRMED_WITH_EDIT, note="เหตุผล")
    assert dec.validate(dec.CONFIRMED_WITH_EDIT, note="เหตุผล",
                        corrected_value="9") == ("เหตุผล", "9")


def test_a_corrected_value_without_the_edit_status_is_refused():
    """🔴 กันการแก้ค่าแบบเงียบ ๆ — ค่าที่แก้ต้องมาคู่กับสถานะที่ประกาศว่าแก้"""
    with pytest.raises(dec.DecisionError):
        dec.validate(dec.CONFIRMED, corrected_value="9")


def test_unknown_status_is_refused():
    with pytest.raises(dec.DecisionError):
        dec.validate("CORRECTED", note="x")


def test_status_names_avoid_the_word_corrected():
    """ชื่อ ``CORRECTED`` ถูกปฏิเสธเพราะอ่านได้ว่าไปแก้ e-Budgeting แล้ว"""
    assert "CORRECTED" not in dec.DECIDABLE
    assert dec.CONFIRMED_WITH_EDIT == "CONFIRMED_WITH_EDIT"
    assert dec.STATUS_LABELS[dec.CONFIRMED_WITH_EDIT] == "ยืนยันโดยแก้ไขข้อเสนอ"
    assert dec.STATUS_LABELS[dec.CONFIRMED] == "ยืนยันว่าเป็นจุดที่ต้องแก้"
    assert dec.STATUS_LABELS[dec.UNRESOLVED] == "ยังตัดสินไม่ได้"
    assert dec.STATUS_LABELS[dec.DISMISSED] == "ไม่ใช่ประเด็นที่ต้องแก้"


def test_disclaimer_says_e_budgeting_is_untouched():
    assert "ยังไม่ได้แก้ไขข้อมูลใน e-Budgeting" in dec.E_BUDGETING_DISCLAIMER


# ══════════════════════════════════════════════════════════════════════════════
#  S3 — สถานะปัจจุบันมาจากประวัติ
# ══════════════════════════════════════════════════════════════════════════════

def test_a_finding_with_no_decision_is_pending(db, run):
    f = _amount_finding(run)
    assert dec.current_status(
        drepo.list_for_finding("DEC-1", f.finding_id, db_path=db)) == dec.PENDING


def test_latest_decision_wins_and_history_is_kept(db, run):
    f = _amount_finding(run)
    _rec(run, f, dec.UNRESOLVED, db, note="ยังไม่มีหลักฐาน")
    # B.2: การกลับจากสถานะที่ตัดสินแล้วต้องมีเหตุผล แม้ปลายทางเป็น CONFIRMED
    _rec(run, f, dec.CONFIRMED, db, note="เจอหลักฐานแล้ว")
    _rec(run, f, dec.DISMISSED, db, note="ตรวจกับต้นฉบับแล้วไม่ใช่ประเด็น")

    history = drepo.list_for_finding("DEC-1", f.finding_id, db_path=db)
    assert [d.status_to for d in history] == [dec.UNRESOLVED, dec.CONFIRMED,
                                              dec.DISMISSED]
    assert [d.status_from for d in history] == [dec.PENDING, dec.UNRESOLVED,
                                                dec.CONFIRMED]
    assert dec.current_status(history) == dec.DISMISSED
    assert drepo.latest_by_finding("DEC-1", db_path=db)[
        f.finding_id].status_to == dec.DISMISSED


def test_engine_values_survive_a_human_edit(db, run):
    """🔴 ข้อสำคัญที่สุด — แก้แล้วต้องยังพิสูจน์ได้ว่าระบบเสนออะไรไว้เดิม"""
    f = _amount_finding(run)
    d = _rec(run, f, dec.CONFIRMED_WITH_EDIT, db, note="ยอดในเอกสารต้นฉบับต่างจากที่ระบบอ่านได้",
                   corrected_value="123")
    assert d.corrected_value == "123"
    assert d.engine_current_value == f.current_value
    assert d.engine_baseline_value == f.baseline_value
    assert d.engine_finding_type == f.finding_type
    assert d.engine_current_value != d.corrected_value


def test_counts_by_status_ignore_superseded_decisions(db, run):
    a, b = run.findings[0], run.findings[1]
    _rec(run, a, dec.CONFIRMED, db)
    _rec(run, a, dec.DISMISSED, db, note="เปลี่ยนใจหลังตรวจซ้ำ")
    _rec(run, b, dec.CONFIRMED, db)
    assert drepo.count_by_status("DEC-1", db_path=db) == {
        dec.DISMISSED: 1, dec.CONFIRMED: 1}


# ══════════════════════════════════════════════════════════════════════════════
#  S4 — id ที่ผูกกลับไม่ได้
# ══════════════════════════════════════════════════════════════════════════════

def test_position_based_findings_are_flagged_not_rebindable(db, run):
    f = _amount_finding(run)
    forced = type(f)(**{**f.__dict__, "identity_basis": svc.BASIS_POSITION})
    d = _rec(run, forced, dec.CONFIRMED, db)
    assert d.not_rebindable is True
    assert d.identity_basis == svc.BASIS_POSITION


def test_content_based_findings_are_rebindable(db, run):
    f = next(x for x in run.findings if x.identity_basis == svc.BASIS_CONTENT)
    d = _rec(run, f, dec.CONFIRMED, db)
    assert d.not_rebindable is False


# ══════════════════════════════════════════════════════════════════════════════
#  S5 — โซ่ audit
# ══════════════════════════════════════════════════════════════════════════════

def test_every_decision_lands_in_the_audit_chain(db, run):
    f = _amount_finding(run)
    d = _rec(run, f, dec.CONFIRMED, db)
    assert d.audit_seq and d.audit_entry_hash
    assert drepo.verify_audit_links("DEC-1", db_path=db)["ok"]
    assert audit.verify_chain(db_path=db)["ok"]


def test_audit_detail_carries_no_budget_content(db, run):
    """audit ลบไม่ได้ตลอดกาล — ห้ามมียอดเงิน ชื่อรายการ หรือเหตุผลที่พิมพ์เอง"""
    f = _amount_finding(run)
    secret_note = "ยอดจริงคือ 987654321 ตามเอกสารต้นฉบับ"
    _rec(run, f, dec.CONFIRMED_WITH_EDIT, db, note=secret_note,
               corrected_value="987654321")
    blob = "".join(e["detail_json"] for e in audit.entries(limit=200, db_path=db))
    assert "987654321" not in blob
    assert secret_note not in blob
    assert "value_edited_by_human" in blob


def test_broken_audit_link_is_reported_not_hidden(db, run):
    d = _rec(run, _amount_finding(run), dec.CONFIRMED, db)
    conn = connect(db)
    try:
        conn.execute("INSERT INTO t1b_decisions "
                     "(id, run_id, finding_id, identity_basis, status_from, "
                     " status_to, decided_at, audit_seq, audit_entry_hash) "
                     "VALUES (?,?,?,?,?,?,?,?,?)",
                     ("dec_broken", "DEC-1", "zzz", "content", "PENDING",
                      "CONFIRMED", "2026-09-07T00:00:00+00:00", 999999, "ff"))
    finally:
        conn.close()
    report = drepo.verify_audit_links("DEC-1", db_path=db)
    assert not report["ok"]
    assert "dec_broken" in report["broken"]
    assert d.id not in report["broken"]
