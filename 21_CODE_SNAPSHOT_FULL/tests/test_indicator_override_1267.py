# -*- coding: utf-8 -*-
"""ผู้ตรวจต้อง override สถานะอัตโนมัติ 1/2/6/7 ได้ทุกแถว และแถวเหล่านั้นต้องไม่ถูกซ่อนโดยปริยาย

🔴 Bo · `BO REVIEW — GATE 0–4: CONDITIONAL PASS BEFORE FREEZE` (`5597645315`) ข้อ C —
*"For the answer key, Gift must be able to inspect and confirm every mapping row,
including statuses 1/2/6/7 … add one test proving a reviewer can override each of 1/2/6/7."*

ข้อความตรงกันทุกอักขระ **ไม่พิสูจน์** ว่าเป็นตัวชี้วัดเดียวกัน เมื่อลำดับชั้น/ขั้นเอกสาร/ขอบเขตต่าง
⇒ สถานะที่เครื่องเสนออัตโนมัติทุกตัวต้อง (ก) ปรากฏในหน้าตรวจโดยไม่ต้องกรอง (ข) ถูกคนแก้ได้

🔴 **SYNTHETIC TEST FIXTURE**
"""
from pathlib import Path

import pytest

import keystage

from redbook.evidence import documents as docs
from redbook.evidence import pdftext
from redbook.indicators import mapping as mp
from redbook.indicators import registry as reg
from redbook.services import evidence as svc

FIX = Path(__file__).resolve().parent / "fixtures" / "synthetic_pdf"
pytestmark = pytest.mark.skipif(pdftext.product_backend() is None,
                                reason=pdftext.NO_TEXT_BACKEND)

AUTOMATIC = (mp.SAME_EXACT, mp.SAME_WORDING_VARIANT, mp.NEW_INDICATOR, mp.REMOVED_INDICATOR)
#: สถานะที่คนอาจแก้ให้ — ต่างจากที่เสนอ และมีความหมายในบริบทของแต่ละสถานะ
OVERRIDE_TO = {
    mp.SAME_EXACT: mp.RELATED_NOT_EQUIVALENT,          # ข้อความเดียวกัน แต่อยู่คนละขอบเขต
    mp.SAME_WORDING_VARIANT: mp.DEFINITION_CHANGED,    # สะกดต่างเล็กน้อย แต่นิยามเปลี่ยน
    mp.NEW_INDICATOR: mp.AMBIGUOUS_REVIEW_REQUIRED,    # อาจเป็นของเดิมที่เขียนใหม่ทั้งประโยค
    mp.REMOVED_INDICATOR: mp.AMBIGUOUS_REVIEW_REQUIRED,
}


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    from redbook.storage.db import init_db

    db = tmp_path_factory.mktemp("ovr") / "t.sqlite3"
    init_db(db)
    svc.init_schemas(db)
    old = svc.register_pdf(FIX / "synthetic_old_fy2569.pdf", title="เก่า", stage=docs.STAGE_DRAFT_BILL,
                           fiscal_year=2569, authority="SYNTHETIC",
                           disclosure_class=docs.DISC_SYNTHETIC, db_path=db)
    new = svc.register_pdf(FIX / "synthetic_new_fy2570.pdf", title="ใหม่", stage=docs.STAGE_DRAFT_BILL,
                           fiscal_year=2570, authority="SYNTHETIC",
                           disclosure_class=docs.DISC_SYNTHETIC, db_path=db)
    res = svc.run_indicator_pipeline(old.document_id, new.document_id, label="OVR", db_path=db)
    # 🔴 B4 — ต้องผนึกเฉลย (สังเคราะห์ · ทดสอบกลไก) ก่อนจึงจะตัดสินหลังรันได้
    keystage.unlock_adjudication(res.run_id, db)
    return {"db": db, "run_id": res.run_id}


def _pairs_by_status(run):
    rv = svc.run_view(run["run_id"], run["db"])
    out = {}
    for p in rv.pairs:
        out.setdefault(p.proposed_status, []).append(p)
    return rv, out


def test_automatic_statuses_are_listed_by_default_not_hidden(run):
    """หน้าตรวจ (ไม่กรอง) และชุด XLSX ต้องมีแถว 1/2/6/7 ครบ"""
    rv, by = _pairs_by_status(run)
    for s in AUTOMATIC:
        assert by.get(s), f"ไม่มีตัวอย่างสถานะ {s} ในชุดสังเคราะห์"
    rows = svc.package_rows(rv)
    statuses_in_rows = {r["proposed_status"] for r in rows}
    assert set(AUTOMATIC) <= statuses_in_rows
    assert len(rows) == len(rv.pairs), "ชุดตรวจต้องมีทุกแถว ไม่คัดกรองสถานะอัตโนมัติออก"


@pytest.mark.parametrize("status", AUTOMATIC)
def test_reviewer_can_override_each_automatic_status(run, status):
    db, rid = run["db"], run["run_id"]
    _, by = _pairs_by_status(run)
    p = by[status][0]
    assert p.human_required is False, "1/2/6/7 เป็นข้อเสนออัตโนมัติ (ไม่บังคับคน) — แต่ต้อง override ได้"
    target = OVERRIDE_TO[status]
    d = svc.decide(rid, p.mapping_id, decision=reg.DECISION_REJECT, final_status=target,
                   reason=f"ตรวจแล้ว ไม่ใช่ {status}", reviewer="gift", db_path=db)
    assert d.final_status == target and d.decision == reg.DECISION_REJECT
    # สถานะปัจจุบันของแถวต้องสะท้อนคำตัดสินของคน ไม่ใช่ที่เครื่องเสนอ
    after = svc.pair_view(rid, p.mapping_id, db)
    assert after.current_status == target and after.decision.seq == d.seq
    # และ SAME_* ที่ถูกแก้เป็น non-SAME ต้องไม่ผูก indicator_id ให้เป็นตัวเดียวกัน
    if status in mp.SAME_FAMILY:
        ids = reg.indicator_ids(rid, db)
        assert ids[p.old.observation_id] != ids[p.new.observation_id]


def test_reject_requires_a_different_status_and_a_reason_for_human_statuses(run):
    db, rid = run["db"], run["run_id"]
    _, by = _pairs_by_status(run)
    p = by[mp.SAME_EXACT][0]
    with pytest.raises(reg.DecisionError):
        svc.decide(rid, p.mapping_id, decision=reg.DECISION_REJECT, final_status=mp.SAME_EXACT,
                   reason="x", reviewer="gift", db_path=db)
    with pytest.raises(reg.DecisionError):
        svc.decide(rid, p.mapping_id, decision=reg.DECISION_REJECT,
                   final_status=mp.RELATED_NOT_EQUIVALENT, reason="", reviewer="gift", db_path=db)
