# -*- coding: utf-8 -*-
"""B1 canonical `indicator_id` ข้าม run + B2 effective binding จากคำตัดสินล่าสุด + H1/H2

🔴 Bo (`5595832792` B1 · B2 · H1 · H2 · ยืนยันซ้ำ `5597709987` และ `5598957701`)

**B2 — สี่กรณีที่ Bo สั่งให้มีเทสต์**
1. ``ACCEPT SAME`` → แก้เป็น ``REJECT``/non-SAME ⇒ **ต้องไม่ bound**
2. ``REJECT`` → แก้เป็น ``ACCEPT SAME`` ⇒ bound
3. รับสอง mapping ที่ชน observation เดียวกัน ⇒ **ปฏิเสธ/ส่ง adjudication** ไม่ใช่ last row wins
4. transitive A=B, B=C ⇒ canonical component เดียว

🔴 **SYNTHETIC TEST FIXTURE** — ข้อสังเกตทุกตัวแต่งขึ้น · การกรอก "เฉลย" ในเทสต์นี้เป็นการ
ทดสอบ *กลไก* ด้วยข้อมูลสังเคราะห์ **ไม่ใช่เฉลยของงานวิจัย** และไม่มีเอกสารจริงเกี่ยวข้อง
"""
import dataclasses
import sqlite3

import pytest

from redbook.indicators import identity as idn
from redbook.indicators import mapping as mp
from redbook.indicators import observe as ob
from redbook.indicators import registry as reg

import keystage

#: จำนวนหน้าของเอกสารสังเคราะห์ในไฟล์นี้ — ทะเบียนอิสระตรวจเลขหน้าเทียบค่านี้ (P4-4)
SYNTH_PAGES = 9

SHA_OLD = "a" * 64
SHA_NEW = "b" * 64
SHA_NEWER = "c" * 64


def obs(text, *, doc, sha, page=1, occurrence=1, hint=""):
    """ข้อสังเกตสังเคราะห์ที่มี anchor/identity_key ครบ"""
    return ob.manual_observation(doc, sha, page=page, observed_text=text,
                                 occurrence=occurrence, hint=hint, page_width=595.0)


@pytest.fixture()
def db(fresh_db):
    reg.init_schema(fresh_db)
    return fresh_db


def _save(db, run_id, old_list, new_list, cands):
    reg.save_run(run_id=run_id, old_document_id="doc_old", new_document_id="doc_new",
                 old_obs=old_list, new_obs=new_list, candidates=cands, rules=mp.Rules(),
                 extractor_version=ob.OBSERVE_VERSION, normalize_version="n",
                 text_backend="test", accounted=mp.accounted(old_list, new_list, cands),
                 page_inventory={}, old_page_count=SYNTH_PAGES, new_page_count=SYNTH_PAGES, db_path=db)


def _unlock(db, run_id, mapping_ids=(), by="key-custodian"):
    """เดินขั้นเฉลยสังเคราะห์ให้ครบจนปลดล็อกขั้นตัดสินหลังรัน (B4 · Pass 3)

    🔴 ``mapping_ids`` ไม่ถูกใช้แล้ว — เฉลยไม่ผูกกับคู่ของ detector อีกต่อไป
    (คงพารามิเตอร์ไว้เพื่อให้ผู้เรียกเดิมอ่านง่าย)
    """
    keystage.unlock_adjudication(run_id, db, by=by)


# ══════════════════════════════════════════════════════════════════════════════
#  B1 — canonical id คงที่ข้าม run
# ══════════════════════════════════════════════════════════════════════════════

def test_identity_key_is_stable_across_runs_and_ignores_run_id():
    a = obs("ตัวชี้วัดที่ 1 : ร้อยละของหน่วยงาน ร้อยละ 80", doc="doc_old", sha=SHA_OLD)
    b = obs("ตัวชี้วัดที่ 1 : ร้อยละของหน่วยงาน ร้อยละ 80", doc="doc_other", sha=SHA_OLD)
    assert a.identity_key == b.identity_key, "กุญแจต้องมาจากเนื้อเอกสาร ไม่ใช่ document_id/run"
    c = obs("ตัวชี้วัดที่ 1 : ร้อยละของหน่วยงาน ร้อยละ 80", doc="doc_old", sha=SHA_NEW)
    assert a.identity_key != c.identity_key, "คนละเอกสาร (แฮชต่าง) ต้องคนละกุญแจ"


def test_identity_key_requires_a_full_digest():
    with pytest.raises(ValueError):
        idn.observation_key(document_sha256="a" * 16, page=1, anchor="line:0",
                            observed_text="x")


def test_unbound_observation_gets_a_provisional_id_not_a_canonical_one(db):
    o, n = obs("ก 80", doc="doc_old", sha=SHA_OLD), obs("ข 80", doc="doc_new", sha=SHA_NEW)
    _save(db, "r1", [o], [n], mp.propose([o], [n]))
    ids = reg.indicator_ids("r1", db)
    assert all(v.startswith("PROVISIONAL-") for v in ids.values())
    assert not any(idn.is_canonical(v) for v in ids.values())


def test_confirmed_pair_gets_one_canonical_id_that_survives_a_later_run(db):
    text = "ตัวชี้วัดที่ 1 : ร้อยละของหน่วยงานที่ได้รับการอบรม ร้อยละ 80"
    o = obs(text, doc="doc_old", sha=SHA_OLD)
    n = obs(text, doc="doc_new", sha=SHA_NEW)
    cands = mp.propose([o], [n])
    _save(db, "r1", [o], [n], cands)
    mid = cands[0].mapping_id
    _unlock(db, "r1", [mid])
    reg.record_decision(run_id="r1", mapping_id=mid, decision=reg.DECISION_ACCEPT,
                        final_status=mp.SAME_EXACT, reason="", reviewer="gift", db_path=db)
    ids1 = reg.indicator_ids("r1", db)
    canonical = ids1[o.observation_id]
    assert idn.is_canonical(canonical)
    assert ids1[n.observation_id] == canonical

    # รอบใหม่: เอกสารเก่าเดิม + เอกสารที่สามที่ยังไม่มีคำตัดสิน
    n2 = obs(text, doc="doc_newer", sha=SHA_NEWER)
    cands2 = mp.propose([o], [n2])
    _save(db, "r2", [o], [n2], cands2)
    ids2 = reg.indicator_ids("r2", db)
    assert ids2[o.observation_id] == canonical, "🔴 id ต้องคงที่ข้าม run"
    assert ids2[n2.observation_id].startswith("PROVISIONAL-"), "ยังไม่ยืนยัน = ยังไม่ canonical"


def test_transitive_confirmations_collapse_into_one_component(db):
    """B2 ข้อ 4 — A=B (run1) และ B=C (run2) ⇒ canonical เดียวกันทั้งสาม"""
    text = "ตัวชี้วัดร่วม 5 เรื่อง"
    a = obs(text, doc="doc_old", sha=SHA_OLD)
    b = obs(text, doc="doc_new", sha=SHA_NEW)
    c = obs(text, doc="doc_newer", sha=SHA_NEWER)
    c1 = mp.propose([a], [b])
    _save(db, "r1", [a], [b], c1)
    _unlock(db, "r1", [c1[0].mapping_id])
    reg.record_decision(run_id="r1", mapping_id=c1[0].mapping_id,
                        decision=reg.DECISION_ACCEPT, final_status=mp.SAME_EXACT,
                        reason="", reviewer="gift", db_path=db)
    c2 = mp.propose([b], [c])
    _save(db, "r2", [b], [c], c2)
    _unlock(db, "r2", [c2[0].mapping_id])
    reg.record_decision(run_id="r2", mapping_id=c2[0].mapping_id,
                        decision=reg.DECISION_ACCEPT, final_status=mp.SAME_EXACT,
                        reason="", reviewer="gift", db_path=db)

    ids2 = reg.indicator_ids("r2", db)
    ids1 = reg.indicator_ids("r1", db)
    assert idn.is_canonical(ids2[c.observation_id])
    assert ids1[a.observation_id] == ids2[b.observation_id] == ids2[c.observation_id]


def test_canonical_id_is_pinned_and_old_ids_resolve_after_a_merge(db):
    """component สองก้อนที่รวมกันภายหลัง ⇒ id เดิมยังเปิดกลับได้ผ่าน alias"""
    a = obs("ตัวชี้วัด ก 1 เรื่อง", doc="doc_old", sha=SHA_OLD)
    b = obs("ตัวชี้วัด ก 1 เรื่อง", doc="doc_new", sha=SHA_NEW)
    c = obs("ตัวชี้วัด ก 1 เรื่อง", doc="doc_newer", sha=SHA_NEWER)
    d = obs("ตัวชี้วัด ก 1 เรื่อง", doc="doc_4", sha="d" * 64)
    c1 = mp.propose([a], [b])
    _save(db, "r1", [a], [b], c1)
    _unlock(db, "r1", [c1[0].mapping_id])
    reg.record_decision(run_id="r1", mapping_id=c1[0].mapping_id,
                        decision=reg.DECISION_ACCEPT, final_status=mp.SAME_EXACT,
                        reason="", reviewer="gift", db_path=db)
    first = reg.indicator_ids("r1", db)[a.observation_id]

    c2 = mp.propose([c], [d])
    _save(db, "r2", [c], [d], c2)
    _unlock(db, "r2", [c2[0].mapping_id])
    reg.record_decision(run_id="r2", mapping_id=c2[0].mapping_id,
                        decision=reg.DECISION_ACCEPT, final_status=mp.SAME_EXACT,
                        reason="", reviewer="gift", db_path=db)
    second = reg.indicator_ids("r2", db)[c.observation_id]
    assert first != second, "สอง component แยกกันต้องคนละ id"

    # รวมสองก้อนด้วยคำตัดสินใหม่ (b = c)
    c3 = mp.propose([b], [c])
    _save(db, "r3", [b], [c], c3)
    _unlock(db, "r3", [c3[0].mapping_id])
    reg.record_decision(run_id="r3", mapping_id=c3[0].mapping_id,
                        decision=reg.DECISION_ACCEPT, final_status=mp.SAME_EXACT,
                        reason="", reviewer="gift", db_path=db)
    merged = reg.indicator_ids("r3", db)[b.observation_id]
    assert merged == first, "ต้องใช้ id ที่ถูกตรึง **ก่อนตามเวลา** ไม่ใช่สร้างใหม่"
    other = second
    assert reg.resolve_alias(other, db) == merged, "id เดิมต้องยังเปิดกลับได้"
    assert reg.indicator_ids("r1", db)[a.observation_id] == merged


def test_merge_keeps_the_chronologically_first_id_even_when_sort_order_disagrees(db):
    """🔴 B1 (Bo `5600162467`) — ลำดับ **เวลา** ต้องชนะลำดับ **ตัวอักษร**

    จัดฉากให้ root key ของ component ที่ถูกตรึง *ทีหลัง* มาก่อนตามลำดับตัวอักษร
    โค้ดเดิมไล่ ``component.members`` ที่เรียงตามตัวอักษรแล้วหยิบตัวแรกที่มี pin
    ⇒ จะได้ id ของก้อนที่ตรึงทีหลัง ซึ่งขัดกับกติกาที่ประกาศไว้
    """
    text = "ตัวชี้วัด ก 1 เรื่อง"
    pool = [obs(text, doc="doc_%s" % c, sha=c * 64) for c in "0123456789abcdef"]
    pool.sort(key=lambda o: o.identity_key)
    # ก้อนที่จะตรึง **ทีหลัง** ได้ root ที่มาก่อนตามตัวอักษร
    late_a, late_b = pool[0], pool[1]
    early_a, early_b = pool[-2], pool[-1]
    assert min(early_a.identity_key, early_b.identity_key) >         min(late_a.identity_key, late_b.identity_key)

    c1 = mp.propose([early_a], [early_b])
    _save(db, "e1", [early_a], [early_b], c1)
    _unlock(db, "e1")
    reg.record_decision(run_id="e1", mapping_id=c1[0].mapping_id,
                        decision=reg.DECISION_ACCEPT, final_status=mp.SAME_EXACT,
                        reason="", reviewer="gift", db_path=db)
    first = reg.indicator_ids("e1", db)[early_a.observation_id]

    c2 = mp.propose([late_a], [late_b])
    _save(db, "e2", [late_a], [late_b], c2)
    _unlock(db, "e2")
    reg.record_decision(run_id="e2", mapping_id=c2[0].mapping_id,
                        decision=reg.DECISION_ACCEPT, final_status=mp.SAME_EXACT,
                        reason="", reviewer="gift", db_path=db)
    second = reg.indicator_ids("e2", db)[late_a.observation_id]
    assert first != second

    c3 = mp.propose([early_b], [late_a])
    _save(db, "e3", [early_b], [late_a], c3)
    _unlock(db, "e3")
    reg.record_decision(run_id="e3", mapping_id=c3[0].mapping_id,
                        decision=reg.DECISION_ACCEPT, final_status=mp.SAME_EXACT,
                        reason="", reviewer="gift", db_path=db)

    merged = reg.indicator_ids("e3", db)[early_b.observation_id]
    assert merged == first, "id ที่ถูกตรึงก่อนตามเวลาต้องเป็นตัวหลัก"
    assert reg.resolve_alias(second, db) == merged, "id ที่ตรึงทีหลังต้องกลายเป็น alias"


def test_pick_canonical_uses_establishment_order_not_member_order():
    """ระดับฟังก์ชัน — ``established_order`` เป็นตัวชี้ขาด"""
    comp = idn.Component(root_key="aaa", members=("aaa", "zzz"))
    pinned = {"aaa": "IND-LATER", "zzz": "IND-EARLIER"}
    order = {"aaa": 2, "zzz": 1}
    canonical, aliases = idn.pick_canonical(comp, pinned, order)
    assert canonical == "IND-EARLIER"
    assert aliases == ("IND-LATER",)


# ══════════════════════════════════════════════════════════════════════════════
#  B2 — binding derive จากคำตัดสินล่าสุด
# ══════════════════════════════════════════════════════════════════════════════

def test_accept_same_then_reject_removes_the_binding(db):
    """B2 ข้อ 1 — ยอมรับ SAME แล้วภายหลังแก้เป็น non-SAME ⇒ **ต้องไม่ bound**"""
    text = "ตัวชี้วัดที่ 3 : จำนวนรายงาน 5 เรื่อง"
    o, n = obs(text, doc="doc_old", sha=SHA_OLD), obs(text, doc="doc_new", sha=SHA_NEW)
    cands = mp.propose([o], [n])
    mid = cands[0].mapping_id
    _save(db, "r1", [o], [n], cands)
    _unlock(db, "r1", [mid])

    reg.record_decision(run_id="r1", mapping_id=mid, decision=reg.DECISION_ACCEPT,
                        final_status=mp.SAME_EXACT, reason="", reviewer="gift", db_path=db)
    bound = reg.indicator_ids("r1", db)
    assert bound[o.observation_id] == bound[n.observation_id]
    assert reg.effective_bindings("r1", db)

    reg.record_decision(run_id="r1", mapping_id=mid, decision=reg.DECISION_REJECT,
                        final_status=mp.RELATED_NOT_EQUIVALENT,
                        reason="ตรวจแล้วคนละตัวชี้วัด", reviewer="gift", db_path=db)
    after = reg.indicator_ids("r1", db)
    assert after[o.observation_id] != after[n.observation_id], "🔴 binding ต้องสิ้นผลทันที"
    assert all(v.startswith("PROVISIONAL-") for v in after.values())
    assert reg.effective_bindings("r1", db) == {}
    # ประวัติยังครบ — สิ้นผลไม่ใช่การลบ
    assert len([d for d in reg.decisions("r1", db) if d.mapping_id == mid]) == 2


def test_reject_then_accept_same_creates_the_binding(db):
    """B2 ข้อ 2"""
    text = "ตัวชี้วัดที่ 4 : ร้อยละของโครงการ ร้อยละ 85"
    o, n = obs(text, doc="doc_old", sha=SHA_OLD), obs(text, doc="doc_new", sha=SHA_NEW)
    cands = mp.propose([o], [n])
    mid = cands[0].mapping_id
    _save(db, "r1", [o], [n], cands)
    _unlock(db, "r1", [mid])
    reg.record_decision(run_id="r1", mapping_id=mid, decision=reg.DECISION_REJECT,
                        final_status=mp.DEFINITION_CHANGED, reason="ตัวหารต่าง",
                        reviewer="gift", db_path=db)
    assert reg.effective_bindings("r1", db) == {}
    reg.record_decision(run_id="r1", mapping_id=mid, decision=reg.DECISION_ACCEPT,
                        final_status=mp.SAME_CONCEPT_REPHRASED, reason="ตรวจซ้ำแล้วตัวเดียวกัน",
                        reviewer="gift", db_path=db)
    ids = reg.indicator_ids("r1", db)
    assert ids[o.observation_id] == ids[n.observation_id]
    assert idn.is_canonical(ids[o.observation_id])


def test_two_confirmed_mappings_sharing_one_observation_go_to_adjudication(db):
    """B2 ข้อ 3 — one-to-many ที่ถูกยืนยัน ⇒ **ไม่ผูก** และรายงานเป็น conflict"""
    text = "ตัวชี้วัดที่ 7 : จำนวนกิจกรรม 12 ครั้ง"
    o = obs(text, doc="doc_old", sha=SHA_OLD)
    n1 = obs(text, doc="doc_new", sha=SHA_NEW, page=4)
    n2 = obs(text, doc="doc_new", sha=SHA_NEW, page=5)
    cands = mp.propose([o], [n1, n2])
    assert {c.proposed_status for c in cands} == {mp.AMBIGUOUS_REVIEW_REQUIRED}
    _save(db, "r1", [o], [n1, n2], cands)
    mids = [c.mapping_id for c in cands]
    _unlock(db, "r1", mids)
    for mid in mids:
        reg.record_decision(run_id="r1", mapping_id=mid, decision=reg.DECISION_REJECT,
                            final_status=mp.SAME_EXACT, reason="ผู้ตรวจเลือกทั้งคู่ (จำลอง)",
                            reviewer="gift", db_path=db)
    conflicts = reg.identity_conflicts("r1", db)
    assert conflicts, "🔴 ต้องรายงานเป็นข้อขัดแย้ง ไม่ใช่ปล่อยให้แถวสุดท้ายชนะ"
    assert reg.effective_bindings("r1", db) == {}
    ids = reg.indicator_ids("r1", db)
    assert all(v.startswith("PROVISIONAL-") for v in ids.values())


def test_bindings_table_is_no_longer_the_source_of_truth(db):
    """แถวใน ``ind_bindings`` ที่ค้างอยู่ต้องไม่ทำให้ id กลายเป็น canonical เอง"""
    o, n = obs("ก 1", doc="doc_old", sha=SHA_OLD), obs("ข 1", doc="doc_new", sha=SHA_NEW)
    _save(db, "r1", [o], [n], mp.propose([o], [n]))
    conn = sqlite3.connect(db)
    try:
        conn.execute("INSERT INTO ind_bindings (run_id, indicator_id, observation_id, "
                     "via_mapping_id, decision_seq, bound_at) VALUES (?,?,?,?,?,?)",
                     ("r1", "IND-DEADBEEF", o.observation_id, "m", 1, "now"))
        conn.commit()
    finally:
        conn.close()
    assert reg.indicator_ids("r1", db)[o.observation_id].startswith("PROVISIONAL-")


# ══════════════════════════════════════════════════════════════════════════════
#  H2 — ตัวตนของข้อสังเกตที่คนกรอก
# ══════════════════════════════════════════════════════════════════════════════

def test_same_text_twice_on_one_page_gets_distinct_manual_ids():
    """🔴 H1/H2 ของ Bo — เดิม ``line_index=-1`` ทำให้ชนกัน"""
    text = "ตัวชี้วัดที่ 8 : จำนวนคู่มือที่จัดทำ 3 ฉบับ"
    a = obs(text, doc="doc_old", sha=SHA_OLD, page=4, occurrence=1)
    b = obs(text, doc="doc_old", sha=SHA_OLD, page=4, occurrence=2)
    assert a.observation_id != b.observation_id
    assert a.identity_key != b.identity_key
    assert a.anchor == "manual:1" and b.anchor == "manual:2"
    assert a.is_manual and ob.FLAG_MANUAL_ENTRY in a.geometry_flags


def test_manual_anchor_hint_separates_two_reviewers_on_the_same_occurrence():
    a = obs("ตัวชี้วัด ก", doc="d", sha=SHA_OLD, page=2, occurrence=1, hint="ใต้หัวข้อ 7.3")
    b = obs("ตัวชี้วัด ก", doc="d", sha=SHA_OLD, page=2, occurrence=1, hint="ใต้หัวข้อ 7.4")
    assert a.observation_id != b.observation_id


def test_manual_occurrence_must_start_at_one():
    with pytest.raises(ValueError):
        ob.manual_anchor(0)


def test_manual_observations_persist_and_reload_with_anchor(db):
    text = "ตัวชี้วัดที่ 8 : จำนวนคู่มือ 3 ฉบับ"
    a = obs(text, doc="doc_old", sha=SHA_OLD, page=4, occurrence=1)
    b = obs(text, doc="doc_old", sha=SHA_OLD, page=4, occurrence=2)
    n = obs("อื่น", doc="doc_new", sha=SHA_NEW)
    _save(db, "r1", [a, b], [n], mp.propose([a, b], [n]))
    loaded = reg.observations("r1", db)
    assert {loaded[a.observation_id].anchor, loaded[b.observation_id].anchor} == {
        "manual:1", "manual:2"}
    assert loaded[a.observation_id].is_manual


# ══════════════════════════════════════════════════════════════════════════════
#  migration
# ══════════════════════════════════════════════════════════════════════════════

def test_schema_version_is_recorded(db):
    assert reg.schema_version(db) == reg.IND_SCHEMA_VERSION == 5


def test_rows_without_identity_key_stay_provisional_and_are_not_guessed(db):
    """แถวจาก schema v1 ไม่มี ``identity_key`` ⇒ ผูกข้าม run ไม่ได้ · ระบบไม่เดาให้"""
    o = obs("ก 1", doc="doc_old", sha=SHA_OLD)
    n = obs("ก 1", doc="doc_new", sha=SHA_NEW)
    cands = mp.propose([o], [n])
    _save(db, "r1", [o], [n], cands)
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA writable_schema=ON")
        conn.execute("DROP TRIGGER ind_observations_no_update")
        conn.execute("UPDATE ind_observations SET identity_key = '' WHERE run_id='r1'")
        conn.commit()
    finally:
        conn.close()
    # 🔴 แถวที่ไม่มีกุญแจตัวตน **สร้างจักรวาลของเฉลยไม่ได้** — ต้องล้มแบบเห็นชัด
    # ไม่ใช่สร้างจักรวาลที่พิสูจน์ตัวตนไม่ได้แล้วเดินต่อ
    with pytest.raises(reg.KeyStageError):
        reg.build_key_universe("r1", built_by="key-custodian", db_path=db)
    # ⇒ ขั้นตัดสินหลังรันยังปิดอยู่ · id ของแถวเหล่านี้ยังเป็นรหัสชั่วคราว
    assert reg.adjudication_unlocked("r1", db) is False
    ids = reg.indicator_ids("r1", db)
    assert all(v.startswith("PROVISIONAL-") for v in ids.values())
