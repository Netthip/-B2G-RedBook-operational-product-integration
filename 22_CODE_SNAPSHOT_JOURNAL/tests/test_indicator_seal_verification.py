# -*- coding: utf-8 -*-
"""P3-1 (Pass 4) — ผนึกต้องถูก **ตรวจ** ทุกครั้ง ไม่ใช่แค่ "มีแถว seal อยู่"

🔴 คำสั่ง Bo (`5605652708` §"Freeze blocker P3-1") —
*"A stored hash is only evidence; it is not an enforcement gate until verified …
add negative tests that alter each scoring-relevant persisted field/input after sealing
and prove adjudication relocks and export/decision routes are rejected …
no repair-in-place after a mismatch: open a new evaluation run."*

ไฟล์นี้เปลี่ยนข้อมูลจริงในฐานข้อมูล **หลังผนึกแล้ว** ทีละ artifact แล้วพิสูจน์ว่า

1. ``adjudication_unlocked()`` กลับเป็น ``False``
2. รหัสเหตุผลบอกได้ว่า artifact ไหนไม่ตรง
3. เส้นทางตัดสิน / เทียบข้างกัน / รายงาน / ส่งออก ถูกปฏิเสธตามไปด้วย
4. ผนึกซ้ำเพื่อ "ซ่อมทับ" ไม่ได้ — ต้องเปิดรอบประเมินใหม่

🔴 **SYNTHETIC TEST FIXTURE** — เอกสารและ "เฉลย" ทั้งหมดแต่งขึ้นเพื่อทดสอบกลไก
ไม่ใช่เฉลยของงานวิจัย และไม่มีเอกสารจริงเกี่ยวข้อง
"""
import sqlite3

import pytest

import keystage
from redbook.evidence import documents as edocs
from redbook.indicators import keyuniverse as ku
from redbook.indicators import mapping as mp
from redbook.indicators import observe as ob
from redbook.indicators import registry as reg

#: จำนวนหน้าของเอกสารสังเคราะห์ในไฟล์นี้ — ทะเบียนอิสระตรวจเลขหน้าเทียบค่านี้ (P4-4)
SYNTH_PAGES = 9

SHA_OLD = "a" * 64
SHA_NEW = "b" * 64

OLD_TEXTS = ["ร้อยละความสำเร็จของการเบิกจ่าย 90",
             "จำนวนผู้รับบริการ 1000 คน",
             "ตัวชี้วัดที่ถูกตัดออกในฉบับใหม่ 5 เรื่อง"]
NEW_TEXTS = ["ร้อยละความสำเร็จของการเบิกจ่าย 90",
             "จำนวนผู้รับบริการ 1000 คน",
             "ตัวชี้วัดใหม่ของฉบับใหม่ 7 หน่วย"]


def _obs(text, doc, sha, page, occurrence=1):
    return ob.manual_observation(doc, sha, page=page, observed_text=text,
                                 occurrence=occurrence, page_width=595.0)


@pytest.fixture()
def sealed(fresh_db):
    """รอบที่เดินครบทุกขั้นแล้ว — ผนึกครบและตรวจผ่าน"""
    reg.init_schema(fresh_db)
    edocs.init_schema(fresh_db)
    old = [_obs(t, "doc_old", SHA_OLD, i + 1) for i, t in enumerate(OLD_TEXTS)]
    new = [_obs(t, "doc_new", SHA_NEW, i + 1) for i, t in enumerate(NEW_TEXTS)]
    cands = mp.propose(old, new)
    reg.save_run(run_id="sv1", old_document_id="doc_old", new_document_id="doc_new",
                 old_obs=old, new_obs=new, candidates=cands, rules=mp.Rules(),
                 extractor_version=ob.OBSERVE_VERSION, normalize_version="n",
                 text_backend="test", accounted=mp.accounted(old, new, cands),
                 page_inventory={}, old_page_count=SYNTH_PAGES, new_page_count=SYNTH_PAGES, db_path=fresh_db)
    keystage.unlock_adjudication("sv1", fresh_db)
    assert reg.adjudication_unlocked("sv1", fresh_db) is True
    return {"db": fresh_db, "id": "sv1", "old": old, "new": new, "cands": cands}


def _raw(db):
    """ต่อฐานข้อมูลตรง ๆ — ใช้จำลองการแก้ข้อมูลจากนอกเส้นทางปกติ"""
    return sqlite3.connect(db)


def _tamper(db, sql, params=(), drop_triggers=()):
    """แก้ข้อมูลแบบ **นอกเส้นทางของแอป** — จำลองไฟล์ฐานข้อมูลที่ถูกแตะจากภายนอก

    🔴 ตารางเหล่านี้เป็น append-only ที่ระดับฐานข้อมูลอยู่แล้ว (trigger ปฏิเสธ
    ``UPDATE``/``DELETE``) · การทดสอบจึงต้อง **ถอด trigger ออกก่อน** ซึ่งก็คือสิ่งที่
    ผู้ที่เข้าถึงไฟล์ฐานข้อมูลได้จะทำ · ประเด็นของเทสต์คือ **ถึงอย่างนั้นการตรวจผนึกก็ยังจับได้**
    """
    conn = _raw(db)
    try:
        for name in drop_triggers:
            conn.execute("DROP TRIGGER IF EXISTS " + name)
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  สภาพปกติ
# ══════════════════════════════════════════════════════════════════════════════

def test_all_three_artifacts_verify_when_nothing_changed(sealed):
    v = reg.seal_verification(sealed["id"], sealed["db"])
    assert v.ok is True and v.reasons == ()
    for check in v.checks:
        assert check.ok is True
        assert len(check.sealed_digest) == 64
        assert check.sealed_digest == check.current_digest


def test_verification_is_the_gate_not_row_existence(sealed):
    """โครงสร้าง — ``adjudication_unlocked`` ต้องเรียกการตรวจ ไม่ใช่เช็กว่ามีแถว"""
    import ast
    import inspect
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(reg.adjudication_unlocked)))
    node = tree.body[0]
    if (node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)):
        node.body = node.body[1:]
    code = ast.unparse(node)
    assert "seal_verification" in code
    assert "is not None" not in code


# ══════════════════════════════════════════════════════════════════════════════
#  mutation — จักรวาล / ทะเบียนอิสระ
# ══════════════════════════════════════════════════════════════════════════════

def test_adding_an_inventory_row_after_sealing_relocks_adjudication(sealed):
    """ทะเบียนอิสระเปลี่ยนหลังตรึง ⇒ จักรวาลไม่ตรงกับที่ตรึงไว้อีก"""
    db, rid = sealed["db"], sealed["id"]
    conn = _raw(db)
    try:
        conn.execute(
            "INSERT INTO ind_source_inventory (run_id, identity_key, side, "
            "document_sha256, page, occurrence, hint, anchor, observed_text, "
            "normalized_text, entered_by, entered_at, audit_seq, audit_entry_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, "f" * 64, "new", SHA_NEW, 9, 1, "", "manual:1", "แทรกภายหลัง",
             "แทรกภายหลัง", "intruder", "2026-09-10T00:00:00+00:00", 0, ""))
        conn.commit()
    finally:
        conn.close()
    check = reg.verify_universe_seal(rid, db)
    assert check.ok is False and ku.R_UNIVERSE_ROWS_DIFFER in check.reasons
    assert reg.adjudication_unlocked(rid, db) is False


def test_retracting_an_inventory_row_after_sealing_relocks_adjudication(sealed):
    db, rid = sealed["db"], sealed["id"]
    victim = reg.source_inventory_rows(rid, db)[0]
    conn = _raw(db)
    try:
        conn.execute(
            "INSERT INTO ind_source_inventory_retractions (run_id, identity_key, "
            "retracted_by, retracted_at, reason, audit_seq, audit_entry_hash) "
            "VALUES (?,?,?,?,?,?,?)",
            (rid, victim.identity_key, "intruder", "2026-09-10T00:00:00+00:00", "", 0, ""))
        conn.commit()
    finally:
        conn.close()
    check = reg.verify_universe_seal(rid, db)
    assert check.ok is False and ku.R_UNIVERSE_ROWS_DIFFER in check.reasons
    assert reg.adjudication_unlocked(rid, db) is False


def test_removing_a_universe_row_after_sealing_relocks_adjudication(sealed):
    db, rid = sealed["db"], sealed["id"]
    victim = reg.key_universe(rid, db)[0]
    _tamper(db, "DELETE FROM ind_key_universe WHERE run_id = ? AND item_id = ?",
            (rid, victim.item_id), drop_triggers=("ind_key_universe_no_delete",))
    check = reg.verify_universe_seal(rid, db)
    assert check.ok is False
    assert ku.R_UNIVERSE_DIGEST_MISMATCH in check.reasons
    assert ku.R_UNIVERSE_COUNT_MISMATCH in check.reasons
    assert reg.adjudication_unlocked(rid, db) is False


# ══════════════════════════════════════════════════════════════════════════════
#  mutation — เฉลย
# ══════════════════════════════════════════════════════════════════════════════

def test_changing_a_key_answer_after_sealing_relocks_adjudication(sealed):
    db, rid = sealed["db"], sealed["id"]
    target = reg.key_universe(rid, db)[0]
    conn = _raw(db)
    try:
        conn.execute(
            "INSERT INTO ind_key_answers (run_id, item_id, key_status, "
            "counterpart_item_id, reason, entered_by, entered_at, audit_seq, "
            "audit_entry_hash) VALUES (?,?,?,?,?,?,?,?,?)",
            (rid, target.item_id, mp.AMBIGUOUS_REVIEW_REQUIRED, "", "แก้หลังผนึก",
             "intruder", "2026-09-10T00:00:00+00:00", 0, ""))
        conn.commit()
    finally:
        conn.close()
    check = reg.verify_key_seal(rid, db)
    assert check.ok is False and ku.R_KEY_DIGEST_MISMATCH in check.reasons
    assert reg.adjudication_unlocked(rid, db) is False


def test_deleting_a_key_answer_after_sealing_relocks_adjudication(sealed):
    db, rid = sealed["db"], sealed["id"]
    target = reg.key_universe(rid, db)[0]
    _tamper(db, "DELETE FROM ind_key_answers WHERE run_id = ? AND item_id = ?",
            (rid, target.item_id), drop_triggers=("ind_key_answers_no_delete",))
    check = reg.verify_key_seal(rid, db)
    assert check.ok is False
    assert ku.R_KEY_COUNT_MISMATCH in check.reasons
    assert ku.R_KEY_COVERAGE_BROKEN in check.reasons
    assert reg.adjudication_unlocked(rid, db) is False


# ══════════════════════════════════════════════════════════════════════════════
#  mutation — ผลลัพธ์ของเครื่อง
# ══════════════════════════════════════════════════════════════════════════════

def test_adding_a_detector_pair_after_sealing_relocks_adjudication(sealed):
    db, rid = sealed["db"], sealed["id"]
    conn = _raw(db)
    try:
        conn.execute(
            "INSERT INTO ind_mappings (mapping_id, run_id, old_observation_id, "
            "new_observation_id, proposed_status, human_required, basis_json, "
            "differences_json, alternatives_json, internal_score) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("map_injected", rid, "", "", mp.NEW_INDICATOR, 0, "[]", "[]", "[]", 0.0))
        conn.commit()
    finally:
        conn.close()
    check = reg.verify_detector_snapshot(rid, db)
    assert check.ok is False
    assert ku.R_DETECTOR_COUNT_MISMATCH in check.reasons
    assert ku.R_DETECTOR_DIGEST_MISMATCH in check.reasons
    assert reg.adjudication_unlocked(rid, db) is False


def test_changing_the_rules_hash_after_sealing_relocks_adjudication(sealed):
    db, rid = sealed["db"], sealed["id"]
    conn = _raw(db)
    try:
        conn.execute("UPDATE ind_runs SET rules_hash = ? WHERE id = ?",
                     ("0" * 16, rid))
        conn.commit()
    finally:
        conn.close()
    check = reg.verify_detector_snapshot(rid, db)
    assert check.ok is False
    assert ku.R_DETECTOR_RULES_MISMATCH in check.reasons
    assert reg.adjudication_unlocked(rid, db) is False


# ══════════════════════════════════════════════════════════════════════════════
#  ผลกระทบต่อเส้นทางที่ถูกล็อก
# ══════════════════════════════════════════════════════════════════════════════

def test_decision_writes_are_refused_after_a_seal_mismatch(sealed):
    db, rid = sealed["db"], sealed["id"]
    mid = sealed["cands"][0].mapping_id
    reg.record_decision(run_id=rid, mapping_id=mid, decision=reg.DECISION_ACCEPT,
                        final_status=mp.SAME_EXACT, reason="", reviewer="gift",
                        db_path=db)          # ก่อน mutation ทำได้ปกติ

    conn = _raw(db)
    try:
        conn.execute("UPDATE ind_runs SET rules_hash = ? WHERE id = ?", ("0" * 16, rid))
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(reg.DecisionError):
        reg.record_decision(run_id=rid, mapping_id=mid, decision=reg.DECISION_ACCEPT,
                            final_status=mp.SAME_EXACT, reason="", reviewer="gift",
                            db_path=db)


def test_detector_coverage_is_refused_after_a_seal_mismatch(sealed):
    db, rid = sealed["db"], sealed["id"]
    assert reg.detector_coverage(rid, db).inventory_total > 0
    conn = _raw(db)
    try:
        conn.execute("UPDATE ind_runs SET rules_hash = ? WHERE id = ?", ("0" * 16, rid))
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(reg.KeyStageError):
        reg.detector_coverage(rid, db)


# ══════════════════════════════════════════════════════════════════════════════
#  ห้ามซ่อมทับที่เดิม
# ══════════════════════════════════════════════════════════════════════════════

def test_no_repair_in_place_after_a_mismatch(sealed):
    """เมื่อไม่ตรงแล้ว ต้องเปิดรอบใหม่ — ผนึกซ้ำหรือแก้เฉลยทับไม่ได้"""
    db, rid = sealed["db"], sealed["id"]
    conn = _raw(db)
    try:
        conn.execute("UPDATE ind_runs SET rules_hash = ? WHERE id = ?", ("0" * 16, rid))
        conn.commit()
    finally:
        conn.close()
    assert reg.adjudication_unlocked(rid, db) is False

    with pytest.raises(reg.KeyStageError):
        reg.seal_detector_snapshot(rid, sealed_by="gift", db_path=db)
    with pytest.raises(reg.KeyStageError):
        reg.seal_key(rid, sealed_by="gift", db_path=db)
    with pytest.raises(reg.KeyStageError):
        reg.freeze_key_universe(rid, frozen_by="gift", db_path=db)
    with pytest.raises(reg.KeyStageError):
        reg.record_key_answer(run_id=rid, item_id=reg.key_universe(rid, db)[0].item_id,
                              key_status=mp.SAME_EXACT, entered_by="gift", db_path=db)
    with pytest.raises(reg.KeyStageError):
        reg.record_source_item(run_id=rid, side="new", page=1, observed_text="ใหม่",
                               entered_by="gift", db_path=db)


def test_reason_codes_are_human_readable(sealed):
    v = reg.seal_verification(sealed["id"], sealed["db"])
    assert v.summary() == "ผนึกครบและตรวจแล้วว่าตรงทุกชั้น"
    for code, label in ku.REASON_LABELS.items():
        assert label and label != code


def test_append_only_triggers_refuse_tampering_through_the_normal_connection(sealed):
    """ชั้นแรกของการป้องกันยังอยู่ — ตารางผนึกลบ/แก้ไม่ได้ผ่านการต่อฐานข้อมูลปกติ"""
    db, rid = sealed["db"], sealed["id"]
    target = reg.key_universe(rid, db)[0]
    conn = _raw(db)
    try:
        for sql, params in (
            ("DELETE FROM ind_key_answers WHERE run_id = ?", (rid,)),
            ("DELETE FROM ind_key_universe WHERE run_id = ?", (rid,)),
            ("DELETE FROM ind_source_inventory WHERE run_id = ?", (rid,)),
            ("UPDATE ind_key_seals SET key_digest = 'x' WHERE run_id = ?", (rid,)),
            ("UPDATE ind_detector_snapshots SET pair_count = 0 WHERE run_id = ?", (rid,)),
            ("UPDATE ind_key_universe SET page = 99 WHERE item_id = ?",
             (target.item_id,)),
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(sql, params)
    finally:
        conn.close()
    assert reg.adjudication_unlocked(rid, db) is True


# ══════════════════════════════════════════════════════════════════════════════
#  P4-3 (Pass 5) — ผนึกเครื่องต้องครอบ **ข้อสังเกตที่สกัด** และ metadata ของรอบ
# ══════════════════════════════════════════════════════════════════════════════
#
# 🔴 Bo (`5606392284` P4-3) — *"Changing an observation after sealing can change
# matched/missed results without invalidating the detector snapshot."*


def _assert_detector_relocked(db, rid, *reasons):
    check = reg.verify_detector_snapshot(rid, db)
    assert check.ok is False
    for r in reasons:
        assert r in check.reasons, (r, check.reasons)
    assert reg.adjudication_unlocked(rid, db) is False
    with pytest.raises(reg.KeyStageError):
        reg.detector_coverage(rid, db)


def test_inserted_detector_observation_relocks(sealed):
    db, rid = sealed["db"], sealed["id"]
    extra = _obs("ข้อสังเกตที่แทรกหลังผนึก ร้อยละ 3", "doc_new", SHA_NEW, 5)
    conn = _raw(db)
    try:
        conn.execute(
            "INSERT INTO ind_observations (observation_id, run_id, side, document_id, page, "
            "line_index, observed_text, normalized_text, x0, y0, x1, y1, page_width, "
            "page_height, location_confidence, source_sha256, extractor_version, anchor, "
            "identity_key, geometry_flags_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (extra.observation_id, rid, "new", "doc_new", 5, 0, extra.observed_text,
             extra.normalized_text, 0, 0, 1, 1, 595, 842, extra.location_confidence,
             SHA_NEW, "manual", extra.anchor, extra.identity_key, "[]"))
        conn.commit()
    finally:
        conn.close()
    _assert_detector_relocked(db, rid, ku.R_DETECTOR_OBSERVATIONS_MISMATCH,
                              ku.R_DETECTOR_OBSERVATION_COUNT_MISMATCH)


def test_removed_detector_observation_relocks(sealed):
    db, rid = sealed["db"], sealed["id"]
    victim = next(iter(reg.observations(rid, db)))
    _tamper(db, "DELETE FROM ind_observations WHERE run_id = ? AND observation_id = ?",
            (rid, victim), drop_triggers=("ind_observations_no_delete",))
    _assert_detector_relocked(db, rid, ku.R_DETECTOR_OBSERVATIONS_MISMATCH,
                              ku.R_DETECTOR_OBSERVATION_COUNT_MISMATCH)


def test_changed_detector_observation_text_relocks(sealed):
    db, rid = sealed["db"], sealed["id"]
    victim = next(iter(reg.observations(rid, db)))
    _tamper(db, "UPDATE ind_observations SET observed_text = observed_text || ' แก้' "
                "WHERE run_id = ? AND observation_id = ?", (rid, victim),
            drop_triggers=("ind_observations_no_update",))
    _assert_detector_relocked(db, rid, ku.R_DETECTOR_OBSERVATIONS_MISMATCH)


def test_changed_detector_observation_geometry_flags_relock(sealed):
    db, rid = sealed["db"], sealed["id"]
    victim = next(iter(reg.observations(rid, db)))
    _tamper(db, "UPDATE ind_observations SET geometry_flags_json = '[\"TEXT_CLIPPED_AT_PAGE_EDGE\"]' "
                "WHERE run_id = ? AND observation_id = ?", (rid, victim),
            drop_triggers=("ind_observations_no_update",))
    _assert_detector_relocked(db, rid, ku.R_DETECTOR_OBSERVATIONS_MISMATCH)


@pytest.mark.parametrize("column,value", [
    ("extractor_version", "indicator-observe-9.9.9"),
    ("normalize_version", "indicator-normalize-9.9.9"),
    ("text_backend", "SOMETHING_ELSE 1.0"),
    ("mapping_version", "indicator-mapping-9.9.9"),
    ("old_page_count", 99),
    ("page_inventory_json", '{"tampered": true}'),
])
def test_changed_run_metadata_relocks(sealed, column, value):
    db, rid = sealed["db"], sealed["id"]
    _tamper(db, "UPDATE ind_runs SET " + column + " = ? WHERE id = ?", (value, rid))
    _assert_detector_relocked(db, rid, ku.R_DETECTOR_METADATA_MISMATCH)


def test_seal_made_with_the_old_protocol_is_not_accepted(sealed):
    """ผนึกของ Pass 3–4 (ไม่ครอบข้อสังเกต) ต้องล็อก ไม่ใช่ถูกยอมรับเงียบ"""
    db, rid = sealed["db"], sealed["id"]
    _tamper(db, "UPDATE ind_detector_snapshots SET snapshot_protocol = '' WHERE run_id = ?",
            (rid,), drop_triggers=("ind_detector_snapshots_no_update",))
    _assert_detector_relocked(db, rid, ku.R_DETECTOR_PROTOCOL_OUTDATED)


def test_detector_seal_records_every_component(sealed):
    snap = reg.detector_snapshot(sealed["id"], sealed["db"])
    assert snap.snapshot_protocol == ku.DETECTOR_SNAPSHOT_PROTOCOL
    assert snap.observation_count == len(sealed["old"]) + len(sealed["new"])
    for d in (snap.mappings_digest, snap.observations_digest, snap.metadata_digest,
              snap.snapshot_digest):
        assert len(d) == 64
