# -*- coding: utf-8 -*-
"""B4 (Pass 3) — จักรวาลของเฉลยที่เป็นกลาง · ด่านครบถ้วน · การผนึกสอง artifact

🔴 คำสั่ง Bo (`5600162467`)

* เฉลยต้อง **ไม่** สร้างจากแถวคู่ของ detector (``rv.pairs`` · ``mapping_id`` ·
  จำนวนคู่ · ลำดับของ detector)
* ผนึกได้ต่อเมื่อครอบคลุม **ทั้งจักรวาล** — ศูนย์ / ไม่ครบ / ซ้ำ / ขาด / เกิน ต้องผนึกไม่ได้
* ``seal digest`` ต้องผูกตัวตน+การจับคู่+สถานะ+เหตุผล+แฮชเอกสารเต็ม+เวอร์ชัน+manifest
* snapshot ของ detector เป็น artifact แยก · ขั้นตัดสินหลังรันเปิดเมื่อผนึกครบทั้งสอง

**negative tests ห้าชุดที่ Bo ระบุ** — ดูหัวข้อ ``NEGATIVE`` ด้านล่าง

🔴 **SYNTHETIC TEST FIXTURE** — ข้อสังเกตทุกตัวแต่งขึ้น · "เฉลย" ในไฟล์นี้เป็นการทดสอบ
*กลไก* ด้วยข้อมูลสังเคราะห์ **ไม่ใช่เฉลยของงานวิจัย** และไม่มีเอกสารจริงเกี่ยวข้อง
"""
import ast
import inspect
import textwrap

import pytest

import keystage
from redbook.indicators import keyuniverse as ku
from redbook.indicators import mapping as mp
from redbook.indicators import observe as ob
from redbook.indicators import registry as reg
from redbook.evidence import documents as edocs
from redbook.services import evidence as svc

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


def _code_only(fn) -> str:
    """โค้ดที่ทำงานจริงของฟังก์ชัน — ตัด docstring และคอมเมนต์ออก

    🔴 บทเรียนเดิม: ด่านสถาปัตยกรรมที่ค้นสตริงดิบจะล้มเพราะ *ข้อความอธิบาย* ที่บอกว่า
    "ห้ามเรียกสิ่งนี้" มีชื่อสิ่งนั้นอยู่ในตัวเอง
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    node = tree.body[0]
    if (node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)):
        node.body = node.body[1:]
    return ast.unparse(node)


@pytest.fixture()
def run(fresh_db):
    reg.init_schema(fresh_db)
    edocs.init_schema(fresh_db)
    old = [_obs(t, "doc_old", SHA_OLD, i + 1) for i, t in enumerate(OLD_TEXTS)]
    new = [_obs(t, "doc_new", SHA_NEW, i + 1) for i, t in enumerate(NEW_TEXTS)]
    cands = mp.propose(old, new)
    reg.save_run(run_id="ru1", old_document_id="doc_old", new_document_id="doc_new",
                 old_obs=old, new_obs=new, candidates=cands, rules=mp.Rules(),
                 extractor_version=ob.OBSERVE_VERSION, normalize_version="n",
                 text_backend="test", accounted=mp.accounted(old, new, cands),
                 page_inventory={}, old_page_count=SYNTH_PAGES, new_page_count=SYNTH_PAGES, db_path=fresh_db)
    return {"db": fresh_db, "id": "ru1", "old": old, "new": new, "cands": cands}


# ══════════════════════════════════════════════════════════════════════════════
#  จักรวาลมาจากข้อสังเกต ไม่ใช่จากคู่ของ detector
# ══════════════════════════════════════════════════════════════════════════════

def test_universe_size_matches_observations_not_detector_pairs(run):
    keystage.enter_inventory_mirroring_observations(run["id"], run["db"])
    items = reg.build_key_universe(run["id"], built_by="k", db_path=run["db"])
    assert len(items) == len(run["old"]) + len(run["new"]) == 6
    assert len(items) != len(run["cands"]), "จำนวนรายการต้องไม่เท่ากับจำนวนคู่ของเครื่อง"


def test_universe_item_ids_are_derived_from_observation_identity(run):
    keystage.enter_inventory_mirroring_observations(run["id"], run["db"])
    items = reg.build_key_universe(run["id"], built_by="k", db_path=run["db"])
    for i in items:
        assert i.item_id == ku.item_id_for(i.side, i.identity_key)
        assert i.item_id.startswith("KI-")
    mapping_ids = {c.mapping_id for c in run["cands"]}
    assert not ({i.item_id for i in items} & mapping_ids)


def test_universe_order_is_neutral_not_detector_order(run):
    keystage.enter_inventory_mirroring_observations(run["id"], run["db"])
    items = reg.build_key_universe(run["id"], built_by="k", db_path=run["db"])
    assert list(items) == sorted(items, key=lambda i: i.sort_key)


def test_key_universe_service_path_never_touches_detector_output():
    """ด่านสถาปัตยกรรม — เส้นทางขั้นเฉลยต้องไม่อ้าง mapping/pair/run_view"""
    src = _code_only(svc.key_universe_view)
    for forbidden in ("run_view", "mappings", "pairs", "mapping_id"):
        assert forbidden not in src, forbidden
    reg_src = (_code_only(reg.build_key_universe)
               + _code_only(reg._universe_records_from_inventory))
    assert "ind_mappings" not in reg_src and "mapping_id" not in reg_src
    # 🔴 Pass 4 — จักรวาลต้องไม่ตั้งต้นจากสิ่งที่เครื่องสกัดได้
    assert "ind_observations" not in reg_src
    assert "_universe_records(" not in _code_only(reg.build_key_universe)


def test_the_old_detector_coupled_writer_is_refused(run):
    with pytest.raises(reg.KeyStageError):
        reg.record_key_entry(run_id=run["id"], mapping_id=run["cands"][0].mapping_id,
                             key_status=mp.SAME_EXACT, reason="", entered_by="k",
                             db_path=run["db"])
    with pytest.raises(reg.KeyStageError):
        svc.record_key_entry(run["id"], "map_x", key_status=mp.SAME_EXACT, reason="",
                             entered_by="k")


# ══════════════════════════════════════════════════════════════════════════════
#  ลำดับที่บังคับ
# ══════════════════════════════════════════════════════════════════════════════

def test_answers_are_refused_before_the_universe_is_frozen(run):
    keystage.enter_inventory_mirroring_observations(run["id"], run["db"])
    items = reg.build_key_universe(run["id"], built_by="k", db_path=run["db"])
    with pytest.raises(reg.KeyStageError):
        reg.record_key_answer(run_id=run["id"], item_id=items[0].item_id,
                              key_status=mp.REMOVED_INDICATOR, entered_by="k",
                              db_path=run["db"])


def test_universe_cannot_be_rebuilt_after_freezing(run):
    keystage.build_and_freeze(run["id"], run["db"])
    with pytest.raises(reg.KeyStageError):
        reg.build_key_universe(run["id"], built_by="k", db_path=run["db"])


def test_answer_outside_the_universe_is_refused(run):
    keystage.ready_for_answers(run["id"], run["db"])
    with pytest.raises(reg.KeyStageError):
        reg.record_key_answer(run_id=run["id"], item_id="KI-DOESNOTEXIST",
                              key_status=mp.NEW_INDICATOR, entered_by="k",
                              db_path=run["db"])


def test_counterpart_on_the_same_side_is_refused(run):
    items = keystage.ready_for_answers(run["id"], run["db"])
    olds = [i for i in items if i.side == ku.SIDE_OLD]
    with pytest.raises(reg.KeyStageError):
        reg.record_key_answer(run_id=run["id"], item_id=olds[0].item_id,
                              key_status=mp.SAME_EXACT,
                              counterpart_item_id=olds[1].item_id, entered_by="k",
                              db_path=run["db"])


# ══════════════════════════════════════════════════════════════════════════════
#  NEGATIVE — ห้าชุดที่ Bo สั่ง
# ══════════════════════════════════════════════════════════════════════════════

def test_negative_1_changing_detector_pairing_leaves_key_rows_untouched(run):
    """(1) เปลี่ยนการจับคู่ของ detector แล้วแถวของขั้นเฉลยต้องไม่ขยับ"""
    before = keystage.ready_for_answers(run["id"], run["db"])
    before_digest = ku.universe_digest(before)
    before_rows = svc.key_universe_view(run["id"], run["db"]).rows

    # รอบที่สองใช้ข้อสังเกต **ชุดเดียวกัน** แต่เกณฑ์ต่างออกไป ⇒ เครื่องจับคู่ต่างออกไปจริง
    loose = mp.Rules(rephrase_min=0.05, ambiguous_min=0.01)
    cands2 = mp.propose(run["old"], run["new"], loose)
    assert {(c.old_observation_id, c.new_observation_id) for c in cands2} !=         {(c.old_observation_id, c.new_observation_id) for c in run["cands"]}
    reg.save_run(run_id="ru2", old_document_id="doc_old", new_document_id="doc_new",
                 old_obs=run["old"], new_obs=run["new"], candidates=cands2,
                 rules=loose, extractor_version=ob.OBSERVE_VERSION,
                 normalize_version="n", text_backend="test",
                 accounted=mp.accounted(run["old"], run["new"], cands2),
                 page_inventory={}, old_page_count=SYNTH_PAGES, new_page_count=SYNTH_PAGES, db_path=run["db"])
    # ผู้ดูแลกรอกทะเบียนอิสระของรอบที่สองด้วยรายการชุดเดิม (เอกสารสองฉบับเดิม)
    keystage.enter_inventory_mirroring_observations("ru2", run["db"])
    after = reg.build_key_universe("ru2", built_by="k", db_path=run["db"])

    assert ku.universe_digest(after) == before_digest, \
        "จักรวาลของเฉลยต้องไม่เปลี่ยนตามวิธีจับคู่ของเครื่อง"
    after_rows = svc.key_universe_view("ru2", run["db"]).rows
    assert [r.item_id for r in after_rows] == [r.item_id for r in before_rows]


def test_negative_2_zero_and_partial_coverage_cannot_seal(run):
    """(2) 0-of-N และ 1-of-N ผนึกไม่ได้"""
    items = keystage.ready_for_answers(run["id"], run["db"])
    with pytest.raises(reg.KeyStageError):
        reg.seal_key(run["id"], sealed_by="gift", db_path=run["db"])

    target = next(i for i in items if i.side == ku.SIDE_OLD)
    reg.record_key_answer(run_id=run["id"], item_id=target.item_id,
                          key_status=mp.REMOVED_INDICATOR, entered_by="k",
                          db_path=run["db"])
    cov = reg.key_coverage(run["id"], run["db"])
    assert cov.closed is False and ku.CHECK_ANSWERED in cov.failed_checks
    with pytest.raises(reg.KeyStageError):
        reg.seal_key(run["id"], sealed_by="gift", db_path=run["db"])
    assert reg.adjudication_unlocked(run["id"], run["db"]) is False


def test_negative_3_missing_duplicate_and_extra_items_cannot_seal(run):
    """(3) ขาด / ซ้ำ (ใช้คู่เดียวกันสองครั้ง) / เกิน — ผนึกไม่ได้ทั้งสามแบบ"""
    items = keystage.ready_for_answers(run["id"], run["db"])
    olds = [i for i in items if i.side == ku.SIDE_OLD]
    news = [i for i in items if i.side == ku.SIDE_NEW]

    # ซ้ำ — สองรายการฝั่งเก่าอ้างคู่ฝั่งใหม่ตัวเดียวกัน
    answers = {}
    for o in olds[:2]:
        answers[o.item_id] = ku.KeyAnswer(o.item_id, mp.SAME_EXACT, news[0].item_id)
    answers[news[0].item_id] = ku.KeyAnswer(news[0].item_id, mp.SAME_EXACT,
                                            olds[0].item_id)
    cov = ku.check_coverage(items, answers)
    assert ku.CHECK_ONCE in cov.failed_checks and cov.reuse_violations

    # ขาด — ตอบไม่ครบ
    cov2 = ku.check_coverage(items, {olds[0].item_id: ku.KeyAnswer(
        olds[0].item_id, mp.REMOVED_INDICATOR)})
    assert ku.CHECK_ANSWERED in cov2.failed_checks and cov2.missing_items

    # เกิน — มีคำตอบของรายการนอกจักรวาล
    full = {i.item_id: ku.KeyAnswer(
        i.item_id, mp.REMOVED_INDICATOR if i.side == ku.SIDE_OLD else mp.NEW_INDICATOR)
        for i in items}
    full["KI-OUTSIDE0000"] = ku.KeyAnswer("KI-OUTSIDE0000", mp.NEW_INDICATOR)
    cov3 = ku.check_coverage(items, full)
    assert ku.CHECK_NO_UNKNOWN in cov3.failed_checks and cov3.unknown_items


def test_negative_3b_one_sided_pairing_is_not_accepted(run):
    """การจับคู่ที่ตรงทางเดียวต้องไม่ผ่านด่าน"""
    items = keystage.ready_for_answers(run["id"], run["db"])
    olds = [i for i in items if i.side == ku.SIDE_OLD]
    news = [i for i in items if i.side == ku.SIDE_NEW]
    answers = {i.item_id: ku.KeyAnswer(
        i.item_id, mp.REMOVED_INDICATOR if i.side == ku.SIDE_OLD else mp.NEW_INDICATOR)
        for i in items}
    answers[olds[0].item_id] = ku.KeyAnswer(olds[0].item_id, mp.SAME_EXACT,
                                            news[0].item_id)
    cov = ku.check_coverage(items, answers)
    assert ku.CHECK_RECIPROCAL in cov.failed_checks


def test_negative_4_changing_any_sealed_field_invalidates_the_digest(run):
    """(4) เปลี่ยนฟิลด์ใดของเฉลยหรือของ manifest ⇒ digest เปลี่ยน"""
    items = keystage.ready_for_answers(run["id"], run["db"])
    keystage.answer_all(run["id"], run["db"])
    answers = reg.latest_key_answers(run["id"], run["db"])
    manifest = reg.universe_seal(run["id"], run["db"]).universe_digest
    hashes = {i.document_sha256 for i in items}

    def digest(a=answers, its=items, sv=reg.IND_SCHEMA_VERSION, dh=hashes, m=manifest):
        return ku.seal_digest(its, a, schema_version=sv, document_hashes=dh,
                              universe_manifest_digest=m)

    base = digest()
    target = next(iter(answers))

    changed_status = dict(answers)
    changed_status[target] = ku.KeyAnswer(
        target, mp.AMBIGUOUS_REVIEW_REQUIRED,
        answers[target].counterpart_item_id, "เปลี่ยนสถานะ")
    assert digest(changed_status) != base, "เปลี่ยนสถานะแล้ว digest ต้องเปลี่ยน"

    changed_reason = dict(answers)
    changed_reason[target] = ku.KeyAnswer(target, answers[target].key_status,
                                          answers[target].counterpart_item_id,
                                          "เหตุผลใหม่")
    assert digest(changed_reason) != base, "เปลี่ยนเหตุผลแล้ว digest ต้องเปลี่ยน"

    paired = next((k for k, v in answers.items() if v.counterpart_item_id), None)
    assert paired is not None
    changed_pair = dict(answers)
    changed_pair[paired] = ku.KeyAnswer(paired, answers[paired].key_status, "")
    assert digest(changed_pair) != base, "เปลี่ยนการจับคู่แล้ว digest ต้องเปลี่ยน"

    assert digest(dh={"f" * 64}) != base, "เปลี่ยนแฮชเอกสารแล้ว digest ต้องเปลี่ยน"
    assert digest(sv=99) != base, "เปลี่ยนเวอร์ชัน schema แล้ว digest ต้องเปลี่ยน"
    assert digest(m="0" * 64) != base, "เปลี่ยน manifest แล้ว digest ต้องเปลี่ยน"


def test_negative_5_complete_key_plus_detector_seal_unlocks_adjudication(run):
    """(5) เฉลยครบ + snapshot ของเครื่องถูกผนึก ⇒ จึงเปิดขั้นตัดสินหลังรัน"""
    keystage.build_and_freeze(run["id"], run["db"])
    # ลำดับที่ Bo กำหนด — ผนึกผลของเครื่องก่อน จึงตอบเฉลยได้
    with pytest.raises(reg.KeyStageError):
        keystage.answer_all(run["id"], run["db"])
    keystage.seal_detector(run["id"], run["db"])
    keystage.answer_all(run["id"], run["db"])
    assert reg.key_coverage(run["id"], run["db"]).closed is True
    assert reg.adjudication_unlocked(run["id"], run["db"]) is False, \
        "ผนึกผลของเครื่องอย่างเดียวยังไม่พอ — ต้องผนึกเฉลยด้วย"

    reg.seal_key(run["id"], sealed_by="gift", note=keystage.SYNTHETIC_NOTE,
                 db_path=run["db"])
    assert reg.adjudication_unlocked(run["id"], run["db"]) is True

    seal = reg.key_seal(run["id"], run["db"])
    assert seal.entries_count == 6 and len(seal.key_digest) == 64


# ══════════════════════════════════════════════════════════════════════════════
#  snapshot ของ detector
# ══════════════════════════════════════════════════════════════════════════════

def test_detector_snapshot_digest_changes_when_pairing_changes(run):
    _, d1 = reg.detector_snapshot_preview(run["id"], run["db"])
    loose = mp.Rules(rephrase_min=0.05, ambiguous_min=0.01)
    cands2 = mp.propose(run["old"], run["new"], loose)
    reg.save_run(run_id="ru3", old_document_id="doc_old", new_document_id="doc_new",
                 old_obs=run["old"], new_obs=run["new"], candidates=cands2,
                 rules=loose, extractor_version=ob.OBSERVE_VERSION,
                 normalize_version="n", text_backend="test",
                 accounted=mp.accounted(run["old"], run["new"], cands2),
                 page_inventory={}, old_page_count=SYNTH_PAGES, new_page_count=SYNTH_PAGES, db_path=run["db"])
    _, d2 = reg.detector_snapshot_preview("ru3", run["db"])
    assert d1 != d2


def test_detector_snapshot_cannot_be_sealed_twice(run):
    keystage.build_and_freeze(run["id"], run["db"])
    reg.seal_detector_snapshot(run["id"], sealed_by="gift", db_path=run["db"])
    with pytest.raises(reg.KeyStageError):
        reg.seal_detector_snapshot(run["id"], sealed_by="gift", db_path=run["db"])


def test_answers_are_refused_after_the_key_is_sealed(run):
    items = keystage.ready_for_answers(run["id"], run["db"])
    keystage.answer_all(run["id"], run["db"])
    reg.seal_key(run["id"], sealed_by="gift", db_path=run["db"])
    with pytest.raises(reg.KeyStageError):
        reg.record_key_answer(run_id=run["id"], item_id=items[0].item_id,
                              key_status=mp.AMBIGUOUS_REVIEW_REQUIRED,
                              reason="แก้ทีหลัง", entered_by="k", db_path=run["db"])


def test_history_of_answers_is_append_only_and_latest_wins(run):
    items = keystage.ready_for_answers(run["id"], run["db"])
    target = next(i for i in items if i.side == ku.SIDE_OLD)
    reg.record_key_answer(run_id=run["id"], item_id=target.item_id,
                          key_status=mp.REMOVED_INDICATOR, entered_by="k",
                          db_path=run["db"])
    reg.record_key_answer(run_id=run["id"], item_id=target.item_id,
                          key_status=mp.AMBIGUOUS_REVIEW_REQUIRED,
                          reason="ทบทวนใหม่", entered_by="k", db_path=run["db"])
    rows = [a for a in reg.key_answers(run["id"], run["db"])
            if a.item_id == target.item_id]
    assert len(rows) == 2, "ประวัติต้องอยู่ครบ"
    latest = reg.latest_key_answers(run["id"], run["db"])[target.item_id]
    assert latest.key_status == mp.AMBIGUOUS_REVIEW_REQUIRED


def test_reason_is_required_for_semantic_statuses(run):
    items = keystage.ready_for_answers(run["id"], run["db"])
    target = next(i for i in items if i.side == ku.SIDE_OLD)
    with pytest.raises(reg.KeyStageError):
        reg.record_key_answer(run_id=run["id"], item_id=target.item_id,
                              key_status=mp.DEFINITION_CHANGED, reason="",
                              entered_by="k", db_path=run["db"])


def test_shape_rules_reject_new_indicator_on_the_old_side(run):
    items = keystage.ready_for_answers(run["id"], run["db"])
    answers = {i.item_id: ku.KeyAnswer(
        i.item_id, mp.REMOVED_INDICATOR if i.side == ku.SIDE_OLD else mp.NEW_INDICATOR)
        for i in items}
    bad = next(i for i in items if i.side == ku.SIDE_OLD)
    answers[bad.item_id] = ku.KeyAnswer(bad.item_id, mp.NEW_INDICATOR)
    cov = ku.check_coverage(items, answers)
    assert ku.CHECK_SHAPE in cov.failed_checks


def test_empty_universe_cannot_be_frozen_or_sealed(fresh_db):
    reg.init_schema(fresh_db)
    edocs.init_schema(fresh_db)
    with pytest.raises(reg.KeyStageError):
        reg.freeze_key_universe("ghost", frozen_by="k", db_path=fresh_db)
    assert ku.check_coverage((), {}).closed is False


# ══════════════════════════════════════════════════════════════════════════════
#  P3-2 — ตัวชี้วัดที่ **เครื่องสกัดตกหล่น** ต้องยังอยู่ในเฉลยและถูกนับเป็น miss
# ══════════════════════════════════════════════════════════════════════════════

MISSED_TEXT = "ตัวชี้วัดที่เครื่องอ่านไม่เจอ ร้อยละ 42 ของหน่วยรับงบ"


def _enter(run, side, page, text, occurrence=1, by="gift"):
    return reg.record_source_item(run_id=run["id"], side=side, page=page,
                                  observed_text=text, occurrence=occurrence,
                                  entered_by=by, db_path=run["db"])


def test_detector_missed_indicator_stays_in_the_key_universe(run):
    """🔴 Bo (`5605652708` P3-2) — รายการที่คนเห็นแต่เครื่องไม่เห็น ต้องอยู่ในจักรวาล

    ผู้ดูแลกรอกทะเบียนอิสระเอง โดยรวมตัวชี้วัดหนึ่งตัวที่ **ไม่มี** ใน ``ind_observations``
    ของรอบนี้เลย · รายการนั้นต้องเข้าจักรวาล ต้องถูกบังคับให้มีคำตอบ และต้องถูกนับเป็น
    ``NO_MATCH`` ในการเทียบความครอบคลุม
    """
    for i, t in enumerate(OLD_TEXTS):
        _enter(run, ku.SIDE_OLD, i + 1, t)
    for i, t in enumerate(NEW_TEXTS):
        _enter(run, ku.SIDE_NEW, i + 1, t)
    # ตัวที่เครื่องสกัดตกหล่น — คนอ่านเจอบนหน้า 2 ของฉบับใหม่
    missed = _enter(run, ku.SIDE_NEW, 2, MISSED_TEXT)

    items = reg.build_key_universe(run["id"], built_by="gift", db_path=run["db"])
    ids = {i.identity_key for i in items}
    assert missed.identity_key in ids, "ตัวชี้วัดที่เครื่องสกัดตกหล่นต้องอยู่ในจักรวาล"
    assert len(items) == len(OLD_TEXTS) + len(NEW_TEXTS) + 1

    obs_texts = {o.observed_text for o in reg.observations(run["id"], run["db"]).values()}
    assert MISSED_TEXT not in obs_texts, "fixture ต้องไม่มีข้อความนี้ในฝั่งเครื่อง"

    # ด่านครบถ้วนบังคับให้ต้องตอบรายการนั้นด้วย
    reg.freeze_key_universe(run["id"], frozen_by="gift", db_path=run["db"])
    keystage.seal_detector(run["id"], run["db"])
    missed_item = next(i for i in items if i.identity_key == missed.identity_key)
    for i in items:
        if i.item_id == missed_item.item_id:
            continue
        reg.record_key_answer(
            run_id=run["id"], item_id=i.item_id,
            key_status=(mp.REMOVED_INDICATOR if i.side == ku.SIDE_OLD
                        else mp.NEW_INDICATOR),
            entered_by="gift", db_path=run["db"])
    cov = reg.key_coverage(run["id"], run["db"])
    assert cov.closed is False and missed_item.item_id in cov.missing_items

    reg.record_key_answer(run_id=run["id"], item_id=missed_item.item_id,
                          key_status=mp.NEW_INDICATOR, entered_by="gift",
                          db_path=run["db"])
    assert reg.key_coverage(run["id"], run["db"]).closed is True
    reg.seal_key(run["id"], sealed_by="gift", db_path=run["db"])
    assert reg.adjudication_unlocked(run["id"], run["db"]) is True

    coverage = reg.detector_coverage(run["id"], run["db"])
    assert coverage.inventory_total == len(items)
    assert coverage.missed == 1, "ต้องนับเป็น miss หนึ่งรายการ"
    assert missed.identity_key in coverage.missed_keys


def test_detector_coverage_is_refused_before_everything_is_sealed(run):
    keystage.build_and_freeze(run["id"], run["db"])
    with pytest.raises(reg.KeyStageError):
        reg.detector_coverage(run["id"], run["db"])


def test_inventory_is_refused_after_the_universe_is_frozen(run):
    keystage.build_and_freeze(run["id"], run["db"])
    with pytest.raises(reg.KeyStageError):
        _enter(run, ku.SIDE_NEW, 1, "สายเกินไป ร้อยละ 1")
    with pytest.raises(reg.KeyStageError):
        reg.retract_source_item(run_id=run["id"],
                                identity_key=reg.source_inventory_rows(
                                    run["id"], run["db"])[0].identity_key,
                                retracted_by="gift", db_path=run["db"])


def test_duplicate_inventory_entry_is_refused_and_occurrence_separates_them(run):
    _enter(run, ku.SIDE_OLD, 1, OLD_TEXTS[0])
    with pytest.raises(reg.KeyStageError):
        _enter(run, ku.SIDE_OLD, 1, OLD_TEXTS[0])
    second = _enter(run, ku.SIDE_OLD, 1, OLD_TEXTS[0], occurrence=2)
    keys = {r.identity_key for r in reg.source_inventory_rows(run["id"], run["db"])}
    assert second.identity_key in keys and len(keys) == 2


def test_retracted_inventory_rows_leave_the_universe_but_stay_in_history(run):
    a = _enter(run, ku.SIDE_OLD, 1, OLD_TEXTS[0])
    b = _enter(run, ku.SIDE_NEW, 1, NEW_TEXTS[0])
    reg.retract_source_item(run_id=run["id"], identity_key=b.identity_key,
                            retracted_by="gift", reason="กรอกผิดหน้า", db_path=run["db"])
    effective = {r.identity_key for r in reg.source_inventory_rows(run["id"], run["db"])}
    assert effective == {a.identity_key}
    items = reg.build_key_universe(run["id"], built_by="gift", db_path=run["db"])
    assert len(items) == 1


def test_inventory_requires_a_run_with_full_document_hashes(fresh_db):
    reg.init_schema(fresh_db)
    edocs.init_schema(fresh_db)
    with pytest.raises(reg.KeyStageError):
        reg.record_source_item(run_id="ghost", side=ku.SIDE_OLD, page=1,
                               observed_text="x", entered_by="gift", db_path=fresh_db)


# ══════════════════════════════════════════════════════════════════════════════
#  P4-4 (Pass 5) — occurrence ต้องตรงตัว · เลขหน้าต้องอยู่ในเอกสาร
# ══════════════════════════════════════════════════════════════════════════════

from redbook.indicators import sourceinventory as si  # noqa: E402


def test_human_occurrence_2_does_not_consume_detector_occurrence_1():
    """🔴 Bo (`5606392284` P4-4) regression — คนมีเฉพาะครั้งที่ 2 · เครื่องมีเฉพาะครั้งที่ 1 ⇒ NO_MATCH"""
    text = "ร้อยละของหน่วยงานที่ผ่านเกณฑ์ 80"
    human = si.make_item(side="old", document_sha256=SHA_OLD, page=2, observed_text=text,
                         occurrence=2, entered_by="gift", page_count=SYNTH_PAGES)
    detector = [{"side": "old", "observation_id": "o1", "document_sha256": SHA_OLD,
                 "page": 2, "line_index": 7, "observed_text": text}]
    [m] = si.match_against_observations([human], detector)
    assert m.status == si.NO_MATCH


def test_detector_occurrence_order_is_explicit_not_input_order():
    """ลำดับที่ปรากฏของเครื่องมาจาก line_index — สลับลำดับข้อมูลเข้าแล้วผลต้องเท่าเดิม"""
    text = "จำนวนโครงการที่แล้วเสร็จ 12"
    detector = [
        {"side": "new", "observation_id": "late", "document_sha256": SHA_NEW, "page": 3,
         "line_index": 20, "observed_text": text},
        {"side": "new", "observation_id": "early", "document_sha256": SHA_NEW, "page": 3,
         "line_index": 4, "observed_text": text},
    ]
    first = si.make_item(side="new", document_sha256=SHA_NEW, page=3, observed_text=text,
                         occurrence=1, entered_by="gift", page_count=SYNTH_PAGES)
    second = si.make_item(side="new", document_sha256=SHA_NEW, page=3, observed_text=text,
                          occurrence=2, entered_by="gift", page_count=SYNTH_PAGES)
    for order in (detector, list(reversed(detector))):
        got = {m.identity_key: m.observation_id
               for m in si.match_against_observations([second, first], order)}
        assert got[first.identity_key] == "early"
        assert got[second.identity_key] == "late"


def test_end_to_end_occurrence_mismatch_is_counted_as_a_miss(run):
    """ทะเบียนมีเฉพาะครั้งที่ 2 ของข้อความที่เครื่องสกัดเจอครั้งเดียว ⇒ ถูกนับ miss ในรอบจริง"""
    for i, t in enumerate(OLD_TEXTS):
        _enter(run, ku.SIDE_OLD, i + 1, t, occurrence=(2 if i == 0 else 1))
    for i, t in enumerate(NEW_TEXTS):
        _enter(run, ku.SIDE_NEW, i + 1, t)
    keystage.ready_for_answers(run["id"], run["db"])
    keystage.answer_all(run["id"], run["db"])
    reg.seal_key(run["id"], sealed_by="gift", db_path=run["db"])
    cov = reg.detector_coverage(run["id"], run["db"])
    assert cov.missed == 1
    assert cov.matched == len(OLD_TEXTS) + len(NEW_TEXTS) - 1


@pytest.mark.parametrize("page,ok", [(0, False), (1, True), (SYNTH_PAGES, True),
                                     (SYNTH_PAGES + 1, False)])
def test_source_item_page_boundaries(run, page, ok):
    """หน้า 0 · หน้าแรก · หน้าสุดท้าย · หน้าสุดท้าย+1"""
    if ok:
        row = _enter(run, ku.SIDE_OLD, page, "ขอบเขตหน้า ร้อยละ 1")
        assert row.page == page
    else:
        with pytest.raises(reg.KeyStageError):
            _enter(run, ku.SIDE_OLD, page, "ขอบเขตหน้า ร้อยละ 1")


def test_source_item_is_refused_when_the_page_count_is_unknown(fresh_db):
    reg.init_schema(fresh_db)
    o = _obs(OLD_TEXTS[0], "doc_old", SHA_OLD, 1)
    n = _obs(NEW_TEXTS[0], "doc_new", SHA_NEW, 1)
    cands = mp.propose([o], [n])
    reg.save_run(run_id="nopages", old_document_id="doc_old", new_document_id="doc_new",
                 old_obs=[o], new_obs=[n], candidates=cands, rules=mp.Rules(),
                 extractor_version=ob.OBSERVE_VERSION, normalize_version="n",
                 text_backend="test", accounted=mp.accounted([o], [n], cands),
                 page_inventory={}, db_path=fresh_db)       # ไม่ระบุจำนวนหน้า
    with pytest.raises(reg.KeyStageError):
        reg.record_source_item(run_id="nopages", side=ku.SIDE_OLD, page=1,
                               observed_text=OLD_TEXTS[0], entered_by="gift",
                               db_path=fresh_db)


def test_same_text_and_occurrence_with_a_different_hint_is_refused(run):
    """สองรายการที่ชี้ตำแหน่งเดียวกันทั้งห้าองค์ประกอบ ⇒ ปฏิเสธ (ไม่ให้นับข้อสังเกตเดียวสองครั้ง)"""
    reg.record_source_item(run_id=run["id"], side=ku.SIDE_OLD, page=1,
                           observed_text=OLD_TEXTS[0], hint="ใต้หัวข้อ 1",
                           entered_by="gift", db_path=run["db"])
    with pytest.raises(reg.KeyStageError):
        reg.record_source_item(run_id=run["id"], side=ku.SIDE_OLD, page=1,
                               observed_text=OLD_TEXTS[0], hint="ใต้หัวข้อ 2",
                               entered_by="gift", db_path=run["db"])
