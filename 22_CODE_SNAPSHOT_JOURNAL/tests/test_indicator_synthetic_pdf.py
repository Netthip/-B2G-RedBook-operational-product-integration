# -*- coding: utf-8 -*-
"""สายงานเต็ม PDF สังเคราะห์ → ข้อสังเกต → คู่ที่เสนอ → ที่เก็บ → คำตัดสิน (Gate 1–2 · 4)

🔴 **SYNTHETIC TEST FIXTURE** — ``tests/fixtures/synthetic_pdf`` · คาดหมายใน
``MANIFEST.json`` ใช้กับเทสต์นี้เท่านั้น **ไม่ใช่เฉลยของการประเมิน**
"""
import json
import sqlite3
from pathlib import Path

import pytest

import keystage

from redbook.evidence import documents as docs
from redbook.evidence import pdftext
from redbook.indicators import mapping as mp
from redbook.indicators import registry as reg
from redbook.services import evidence as svc

FIX = Path(__file__).resolve().parent / "fixtures" / "synthetic_pdf"
OLD, NEW = FIX / "synthetic_old_fy2569.pdf", FIX / "synthetic_new_fy2570.pdf"
MANIFEST = json.loads((FIX / "MANIFEST.json").read_text(encoding="utf-8"))

pytestmark = pytest.mark.skipif(pdftext.product_backend() is None,
                                reason=pdftext.NO_TEXT_BACKEND)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    from redbook.storage.db import init_db

    db = tmp_path_factory.mktemp("ind") / "t.sqlite3"
    init_db(db)
    svc.init_schemas(db)
    old = svc.register_pdf(OLD, title="เก่า", stage=docs.STAGE_DRAFT_BILL, fiscal_year=2569,
                           authority="SYNTHETIC", disclosure_class=docs.DISC_SYNTHETIC, db_path=db)
    new = svc.register_pdf(NEW, title="ใหม่", stage=docs.STAGE_DRAFT_BILL, fiscal_year=2570,
                           authority="SYNTHETIC", disclosure_class=docs.DISC_SYNTHETIC, db_path=db)
    res = svc.run_indicator_pipeline(old.document_id, new.document_id, label="TEST", db_path=db)
    return {"db": db, "old": old, "new": new, "res": res}


def _pairs(run):
    return svc.run_view(run["res"].run_id, run["db"]).pairs


def _find(run, status, needle):
    for p in _pairs(run):
        if p.proposed_status == status and needle in ((p.old.observed_text if p.old else "")
                                                       + (p.new.observed_text if p.new else "")):
            return p
    raise AssertionError(f"ไม่พบ {status} ที่มี {needle!r}")


def test_fixture_hashes_match_manifest():
    for name, meta in MANIFEST["files"].items():
        assert docs.sha256_file(FIX / name)[0] == meta["sha256"], name


def test_every_status_the_machine_may_propose_appears_once_each(run):
    by = run["res"].by_status
    assert by[mp.SAME_EXACT] == 1 and by[mp.SAME_WORDING_VARIANT] == 1
    assert by[mp.SAME_CONCEPT_REPHRASED] == 1 and by[mp.DEFINITION_CHANGED] == 1
    assert by[mp.REMOVED_INDICATOR] == 1 and by[mp.NEW_INDICATOR] == 1
    assert by[mp.AMBIGUOUS_REVIEW_REQUIRED] == 3      # ซ้ำ 2 + คล้ายไม่พอ 1
    assert mp.RELATED_NOT_EQUIVALENT not in by
    assert run["res"].accounted["closed"] is True


def test_moved_indicator_keeps_same_exact_with_page_change(run):
    p = _find(run, mp.SAME_EXACT, "ตัวชี้วัดที่ 1")
    assert (p.old.page, p.new.page) == (2, 3)
    assert p.old.bbox and p.new.bbox and not p.old.location_review_required


def test_definition_change_shows_method_difference(run):
    p = _find(run, mp.DEFINITION_CHANGED, "ตัวชี้วัดที่ 4")
    fields = {d["field"] for d in p.differences}
    assert "method_text" in fields
    assert p.human_required


def test_missing_text_layer_page_is_flagged_not_silent(run):
    inv = svc.run_view(run["res"].run_id, run["db"]).run.page_inventory
    assert inv["old"]["pages_without_text_layer"] == [4]
    assert inv["new"]["pages_without_text_layer"] == []
    assert run["old"].text_layer_status == pdftext.TEXT_LAYER_PARTIAL


def test_duplicate_wording_yields_two_ambiguous_rows_with_alternatives(run):
    rows = [p for p in _pairs(run) if p.proposed_status == mp.AMBIGUOUS_REVIEW_REQUIRED
            and "ตัวชี้วัดที่ 7" in p.old.observed_text]
    assert len(rows) == 2 and sorted(r.new.page for r in rows) == [4, 5]
    assert all(r.alternatives for r in rows)


def test_observations_and_mappings_are_immutable(run):
    conn = sqlite3.connect(run["db"])
    try:
        for table in ("ind_observations", "ind_mappings"):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(f"UPDATE {table} SET run_id = 'x'")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(f"DELETE FROM {table}")
    finally:
        conn.close()


def _seal_synthetic_key(rid, db):
    """ผนึกเฉลย **สังเคราะห์** เพื่อทดสอบกลไก B4 — ไม่ใช่เฉลยของงานวิจัย"""
    keystage.unlock_adjudication(rid, db)


def test_adjudication_is_blocked_before_the_key_is_sealed(run):
    """B4 — ตัดสินหลังรันก่อนผนึกเฉลยไม่ได้"""
    db, rid = run["db"], run["res"].run_id
    if reg.key_seal(rid, db) is None:
        p = _pairs(run)[0]
        with pytest.raises(reg.DecisionError):
            svc.decide(rid, p.mapping_id, decision="ACCEPT", final_status="",
                       reason="x", reviewer="gift", db_path=db)


def test_decision_flow_and_indicator_binding(run):
    db, rid = run["db"], run["res"].run_id
    _seal_synthetic_key(rid, db)
    p = _find(run, mp.SAME_CONCEPT_REPHRASED, "ตัวชี้วัดที่ 3")
    # ยังไม่ผูก: สองฝั่งมี indicator_id คนละตัว
    ids = reg.indicator_ids(rid, db)
    assert ids[p.old.observation_id] != ids[p.new.observation_id]
    with pytest.raises(reg.DecisionError):       # สถานะ 3 ต้องมีเหตุผล
        svc.decide(rid, p.mapping_id, decision="ACCEPT", final_status="", reason="",
                   reviewer="gift", db_path=db)
    with pytest.raises(reg.DecisionError):       # ต้องมีผู้ตรวจ
        svc.decide(rid, p.mapping_id, decision="ACCEPT", final_status="", reason="ตรวจแล้ว",
                   reviewer="", db_path=db)
    d = svc.decide(rid, p.mapping_id, decision="ACCEPT", final_status="", reason="ตรวจแล้ว",
                   reviewer="gift", db_path=db)
    assert d.final_status == mp.SAME_CONCEPT_REPHRASED and d.audit_seq > 0
    ids = reg.indicator_ids(rid, db)
    assert ids[p.old.observation_id] == ids[p.new.observation_id]
    # REJECT ต้องระบุสถานะที่ต่างจากที่เสนอ
    q = _find(run, mp.AMBIGUOUS_REVIEW_REQUIRED, "ตัวชี้วัดที่ 5")
    with pytest.raises(reg.DecisionError):
        svc.decide(rid, q.mapping_id, decision="REJECT", final_status=mp.AMBIGUOUS_REVIEW_REQUIRED,
                   reason="x", reviewer="gift", db_path=db)
    d2 = svc.decide(rid, q.mapping_id, decision="REJECT", final_status=mp.RELATED_NOT_EQUIVALENT,
                    reason="คนละตัวชี้วัด — หน่วยและสิ่งที่นับต่างกัน", reviewer="gift", db_path=db)
    assert d2.final_status == mp.RELATED_NOT_EQUIVALENT
    # คำตัดสินล่าสุดชนะ · ประวัติยังอยู่ครบ
    d3 = svc.decide(rid, q.mapping_id, decision="AMBIGUOUS", final_status="", reason="ขอดูเพิ่ม",
                    reviewer="gift", db_path=db)
    assert reg.latest_decisions(rid, db)[q.mapping_id].seq == d3.seq
    assert len([x for x in reg.decisions(rid, db) if x.mapping_id == q.mapping_id]) == 2
    conn = sqlite3.connect(db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM ind_decisions")
    finally:
        conn.close()


def test_internal_score_is_not_exposed_by_default(run):
    db, rid = run["db"], run["res"].run_id
    assert all(c.internal_score == 0.0 for c in reg.mappings(rid, db_path=db))
    real = reg.mappings(rid, with_internal_score=True, db_path=db)
    assert any(c.internal_score > 0 for c in real)
    for p in _pairs(run):
        assert not hasattr(p, "internal_score")
        for b in p.basis:
            assert "=" not in b and "dice" not in b, b
