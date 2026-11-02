# -*- coding: utf-8 -*-
"""B5 run context ใน evidence route + B4 แยก KEY BUILD/VERIFY ออกจาก POST-RUN ADJUDICATION

🔴 Bo (`5595832792` B4 · B5 · ยืนยันซ้ำ `5597709987`)

* **B5** — `/evidence/{document_id}` ต้องพก **และตรวจ** ``run`` · เดิมไล่หา observation
  ในทุกรอบแล้วหยิบรอบแรกที่พบ ⇒ เอกสาร/ข้อสังเกตเดียวกันที่อยู่หลายรอบอาจแสดง
  ``indicator_id``/binding ของคนละรอบ
* **B4** — ขั้นจัดทำ/ยืนยันเฉลยต้อง **ไม่เห็น** สิ่งที่ detector เสนอ · ขั้นตัดสินหลังรัน
  เปิดได้หลังเฉลยถูกผนึกเท่านั้น

🔴 **SYNTHETIC TEST FIXTURE** — เอกสารสังเคราะห์ทั้งหมด · การกรอก/ผนึก "เฉลย" ในเทสต์นี้
เป็นการทดสอบ *กลไก* ด้วยข้อมูลสังเคราะห์ **ไม่ใช่เฉลยของงานวิจัย**
"""
import dataclasses
import re
from pathlib import Path

import pytest

import keystage
from fastapi.testclient import TestClient

from redbook.app import create_app
from redbook.evidence import documents as docs
from redbook.evidence import pdftext
from redbook.indicators import mapping as mp
from redbook.indicators import registry as reg
from redbook.services import evidence as svc
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD

FIX = Path(__file__).resolve().parent / "fixtures" / "synthetic_pdf"
pytestmark = pytest.mark.skipif(pdftext.product_backend() is None,
                                reason=pdftext.NO_TEXT_BACKEND)


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def two_runs(client, tmp_path_factory):
    """เอกสารเก่าหนึ่งฉบับถูกใช้ใน **สองรอบ** — เงื่อนไขที่ทำให้ B5 มีความหมาย"""
    tmp = tmp_path_factory.mktemp("runctx")
    old_p, new_p, newer_p = tmp / "o.pdf", tmp / "n.pdf", tmp / "n2.pdf"
    old_p.write_bytes((FIX / "synthetic_old_fy2569.pdf").read_bytes())
    new_p.write_bytes((FIX / "synthetic_new_fy2570.pdf").read_bytes())
    newer_p.write_bytes((FIX / "synthetic_new_fy2570.pdf").read_bytes() + b"\n%v2\n")
    reg_kw = dict(stage=docs.STAGE_DRAFT_BILL, authority="SYNTHETIC",
                  disclosure_class=docs.DISC_SYNTHETIC)
    old = svc.register_pdf(old_p, title="เก่า", fiscal_year=2569, **reg_kw)
    new = svc.register_pdf(new_p, title="ใหม่", fiscal_year=2570, **reg_kw)
    newer = svc.register_pdf(newer_p, title="ใหม่กว่า", fiscal_year=2571, **reg_kw)
    r1 = svc.run_indicator_pipeline(old.document_id, new.document_id, label="RUN1")
    r2 = svc.run_indicator_pipeline(old.document_id, newer.document_id, label="RUN2")
    return {"old": old, "new": new, "newer": newer, "r1": r1.run_id, "r2": r2.run_id}


def _obs_of(run_id, doc_id):
    rv = svc.run_view(run_id)
    for p in rv.pairs:
        for side in (p.old, p.new):
            if side and side.document_id == doc_id and side.observation_id:
                return side
    raise AssertionError("ไม่พบข้อสังเกตในรอบที่ระบุ")


def _seal(client, run_id, reviewer="key-custodian"):
    """เดินขั้นเฉลยสังเคราะห์ **ให้ครบทั้งจักรวาล** แล้วผนึกทั้งสอง artifact

    🔴 Pass 3 — เดิมตัวช่วยนี้ผนึกเฉลยเพียงรายการเดียว ซึ่ง Bo ชี้ว่าเป็น freeze blocker
    """
    keystage.unlock_adjudication(run_id, by=reviewer)


# ══════════════════════════════════════════════════════════════════════════════
#  B5 — run context
# ══════════════════════════════════════════════════════════════════════════════

def test_evidence_links_carry_the_run_id(two_runs):
    side = _obs_of(two_runs["r1"], two_runs["old"].document_id)
    assert f"run={two_runs['r1']}" in side.evidence_url
    assert side.run_id == two_runs["r1"]


def test_same_observation_resolves_per_run_not_first_match(two_runs):
    """เอกสารเก่าตัวเดียวกันอยู่สองรอบ — ต้องได้ค่าของรอบที่ระบุ ไม่ใช่รอบแรกที่เจอ"""
    doc = two_runs["old"].document_id
    a = _obs_of(two_runs["r1"], doc)
    v1 = svc.page_view(doc, a.page, a.observation_id, two_runs["r1"])
    v2 = svc.page_view(doc, a.page, a.observation_id, two_runs["r2"])
    assert v1.side.run_id == two_runs["r1"] and v2.side.run_id == two_runs["r2"]
    assert v1.side.run_context_status == "" and v2.side.run_context_status == ""


def test_observation_from_another_run_is_rejected_not_silently_resolved(two_runs):
    """ข้อสังเกตของ ``r2`` ที่อยู่ในเอกสาร "ใหม่กว่า" ต้องเปิดใน ``r1`` ไม่ได้"""
    side = _obs_of(two_runs["r2"], two_runs["newer"].document_id)
    v = svc.page_view(two_runs["newer"].document_id, side.page, side.observation_id,
                      two_runs["r1"])
    assert v.side.run_context_status == svc.RUN_CONTEXT_MISMATCH
    assert v.side.observation_id == "", "ต้องไม่แสดงข้อสังเกตของคนละรอบ"
    assert v.side.indicator_id == ""


def test_missing_run_context_does_not_show_a_run_specific_indicator_id(two_runs):
    side = _obs_of(two_runs["r1"], two_runs["old"].document_id)
    v = svc.page_view(two_runs["old"].document_id, side.page, side.observation_id, "")
    assert v.side.run_context_status == svc.RUN_CONTEXT_MISSING
    assert v.side.indicator_id == ""


def test_unknown_run_id_is_reported_as_mismatch(two_runs):
    side = _obs_of(two_runs["r1"], two_runs["old"].document_id)
    v = svc.page_view(two_runs["old"].document_id, side.page, side.observation_id,
                      "ind_does_not_exist")
    assert v.side.run_context_status == svc.RUN_CONTEXT_MISMATCH


def test_route_refuses_detector_observations_while_the_run_is_locked(client, two_runs):
    """B5 + P4-1 — ลิงก์หลักฐานยังพก run context แต่รอบที่ยังล็อก **เปิดข้อสังเกตของเครื่องไม่ได้**

    🔴 Pass 5 (Bo `5606392284` P4-1) — เดิมเทสต์นี้คาดหวัง 200 ขณะที่ทั้งสองรอบยังไม่ผนึก
    ซึ่งคือทางรั่วที่ Bo ชี้ · กรณีเปิดได้จริงย้ายไปทดสอบหลังผนึกที่ท้ายไฟล์
    """
    side = _obs_of(two_runs["r1"], two_runs["old"].document_id)
    assert f"run={two_runs['r1']}" in side.evidence_url
    for url in (side.evidence_url,
                f"/evidence/{two_runs['old'].document_id}"
                f"?page={side.page}&run={two_runs['r2']}&obs={side.observation_id}",
                f"/evidence/{two_runs['old'].document_id}"
                f"?page=1&run=ind_ghost&obs={side.observation_id}"):
        r = client.get(url)
        assert r.status_code == 409, url
        assert side.observed_text not in r.text


def test_run_id_is_never_leaked_as_a_path(two_runs):
    side = _obs_of(two_runs["r1"], two_runs["old"].document_id)
    assert re.fullmatch(r"/evidence/doc_[0-9a-f]+\?page=\d+&run=[A-Za-z0-9_]+&obs=[A-Za-z0-9_]+",
                        side.evidence_url), side.evidence_url


# ══════════════════════════════════════════════════════════════════════════════
#  B4 — KEY BUILD/VERIFY แยกจาก POST-RUN ADJUDICATION
# ══════════════════════════════════════════════════════════════════════════════

def test_key_item_rows_contain_no_detector_output(two_runs):
    """แถวของขั้นเฉลยต้องมาจากข้อสังเกต ไม่ใช่จากคู่ของเครื่อง (Bo `5600162467`)"""
    run_id = two_runs["r1"]
    keystage.enter_inventory_mirroring_observations(run_id)
    reg.build_key_universe(run_id, built_by="key-custodian")
    kv = svc.key_universe_view(run_id)
    rv = svc.run_view(run_id)
    assert kv.rows, "ต้องมีรายการในจักรวาล"
    assert len(kv.rows) != len(rv.pairs), "จำนวนแถวต้องไม่สะท้อนจำนวนคู่ของเครื่อง"
    mapping_ids = {p.mapping_id for p in rv.pairs}
    for r in kv.rows:
        fields = {f.name for f in dataclasses.fields(r)}
        for forbidden in svc.KEY_BUILD_FORBIDDEN_FIELDS:
            assert forbidden not in fields, forbidden
        assert r.item_id not in mapping_ids
        blob = str(dataclasses.asdict(r))
        for status in mp.STATUSES:
            if r.key_status != status:
                assert status not in blob, f"เห็นสถานะที่เครื่องเสนอในขั้นเฉลย: {status}"


def test_key_build_page_hides_proposed_status(client, two_runs):
    r = client.get(f"/indicators/runs/{two_runs['r1']}/keybuild")
    assert r.status_code == 200
    html = r.text
    assert "KEY BUILD" in html
    # 🔴 ตรวจจริง: ตัดบล็อก <select> (ตัวเลือกที่ผู้จัดทำเฉลยต้องเลือกเอง) ออกก่อน
    # แล้วส่วนที่เหลือของหน้าต้องไม่มีชื่อสถานะใดเลย ⇒ ไม่มีสิ่งที่ detector เสนอรั่วออกมา
    body = re.sub(r"<select.*?</select>", "", html, flags=re.S)
    for status in mp.STATUSES:
        assert status not in body, f"ขั้นเฉลยเห็นสถานะ {status} ที่ไม่ควรเห็น"
    for token in ("internal_score", "trigram_dice", "เหตุผลที่เครื่องอ่านได้",
                  "ต้องให้คนยืนยัน", "ความต่างของ"):
        assert token not in body


def test_adjudication_is_locked_until_the_key_is_sealed(client, two_runs):
    run_id = two_runs["r2"]
    assert svc.adjudication_unlocked(run_id) is False
    assert svc.stage_of(run_id) == svc.STAGE_KEY_BUILD
    locked = client.get(f"/indicators/runs/{run_id}/verify")
    assert locked.status_code == 409 and svc.ADJUDICATION_LOCKED in locked.text
    pair = svc.run_view(run_id).pairs[0]
    cmp_locked = client.get(pair.compare_url)
    assert cmp_locked.status_code == 409
    token = client.cookies.get(CSRF_COOKIE)
    pkg = client.post(f"/indicators/runs/{run_id}/package", data={CSRF_FIELD: token})
    assert pkg.status_code == 409


def test_decision_before_sealing_is_refused_at_the_service_layer(two_runs):
    rv = svc.run_view(two_runs["r2"])
    with pytest.raises(svc.DecisionError):
        svc.decide(two_runs["r2"], rv.pairs[0].mapping_id, decision="ACCEPT",
                   final_status=mp.SAME_EXACT, reason="", reviewer="gift")


def test_sealing_unlocks_adjudication_and_freezes_the_key(client, two_runs):
    run_id = two_runs["r2"]
    _seal(client, run_id)
    assert svc.adjudication_unlocked(run_id) is True
    assert svc.stage_of(run_id) == svc.STAGE_ADJUDICATION
    assert client.get(f"/indicators/runs/{run_id}/verify").status_code == 200
    rv = svc.run_view(run_id)
    kv = svc.key_universe_view(run_id)
    assert rv.key_seal is not None and rv.detector_seal is not None
    assert rv.key_seal.entries_count == len(kv.rows), "ต้องผนึกครบทั้งจักรวาล"
    assert len(rv.key_seal.key_digest) == 64
    # เฉลยที่ผนึกแล้วแก้ไม่ได้
    with pytest.raises(svc.KeyStageError):
        svc.record_key_answer(run_id, kv.rows[0].item_id, key_status=mp.SAME_EXACT,
                              entered_by="gift")
    with pytest.raises(svc.KeyStageError):
        svc.seal_key(run_id, sealed_by="gift")


def test_key_answer_requires_owner_and_reason_for_human_statuses(two_runs):
    run_id = two_runs["r1"]
    items = keystage.ready_for_answers(run_id)
    iid = items[0].item_id
    with pytest.raises(svc.KeyStageError):
        svc.record_key_answer(run_id, iid, key_status=mp.SAME_CONCEPT_REPHRASED,
                              reason="", entered_by="gift")
    with pytest.raises(svc.KeyStageError):
        svc.record_key_answer(run_id, iid, key_status=mp.SAME_EXACT, reason="",
                              entered_by="")
    with pytest.raises(svc.KeyStageError):
        svc.record_key_answer(run_id, "KI-GHOST000000", key_status=mp.SAME_EXACT,
                              reason="", entered_by="gift")


def test_key_answer_route_records_and_audits(client, two_runs):
    from redbook.storage import audit

    run_id = two_runs["r1"]
    items = keystage.ready_for_answers(run_id)
    iid = items[0].item_id
    token = client.cookies.get(CSRF_COOKIE)
    bad = client.post(f"/indicators/runs/{run_id}/keybuild/answer",
                      data={"item_id": iid, "key_status": mp.REMOVED_INDICATOR,
                            "entered_by": "gift"})
    assert bad.status_code == 403, "ต้องมี CSRF"
    ok = client.post(f"/indicators/runs/{run_id}/keybuild/answer",
                     data={"item_id": iid, "key_status": mp.REMOVED_INDICATOR,
                           "reason": "", "entered_by": "gift", CSRF_FIELD: token},
                     follow_redirects=False)
    assert ok.status_code == 303
    assert any(e["action"] == "indicator_key_answer_recorded"
               for e in audit.entries(limit=50))
    assert audit.verify_chain()["ok"] is True
    page = client.get(f"/indicators/runs/{run_id}/keybuild")
    assert iid in page.text


def test_locked_page_points_at_the_key_build_stage(client, two_runs):
    run_id = two_runs["r1"]      # ยังไม่ผนึก
    r = client.get(f"/indicators/runs/{run_id}/verify")
    assert r.status_code == 409
    assert f"/indicators/runs/{run_id}/keybuild" in r.text
    assert "เฉลย" in r.text


def test_package_is_labelled_post_run_adjudication(client, two_runs, tmp_path):
    run_id = two_runs["r2"]      # ผนึกแล้วในเทสต์ก่อนหน้า
    if not svc.adjudication_unlocked(run_id):
        _seal(client, run_id)
    rv = svc.run_view(run_id)
    files = svc.write_package(rv, tmp_path / "out")
    import openpyxl
    wb = openpyxl.load_workbook(files.xlsx_path, read_only=True)
    blob = "\n".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows()
                     for c in row if c.value is not None)
    assert "POST-RUN ADJUDICATION" in blob
    assert "ห้ามใช้สร้างหรือยืนยันเฉลยที่ปิดผนึก" in blob


def test_run_view_reports_identity_conflicts_and_clipped_counts(two_runs):
    rv = svc.run_view(two_runs["r1"])
    assert isinstance(rv.identity_conflicts, tuple)
    assert isinstance(rv.clipped_pairs, int)


def test_run_context_opens_after_sealing_and_other_runs_stay_locked(client, two_runs):
    """หลังผนึก r2 ครบ (เทสต์ก่อนหน้า) — ข้อสังเกตของ r2 เปิดได้ · r1 ที่ยังไม่ผนึกยังล็อก

    ข้อสังเกตเดียวกันของเอกสารเก่ามีอยู่ในทั้งสองรอบ ⇒ ต้องเปิดได้ **ในบริบทของ r2 เท่านั้น**
    """
    if not svc.adjudication_unlocked(two_runs["r2"]):
        _seal(client, two_runs["r2"])
    side = _obs_of(two_runs["r1"], two_runs["old"].document_id)
    as_r2 = client.get(f"/evidence/{two_runs['old'].document_id}"
                       f"?page={side.page}&run={two_runs['r2']}&obs={side.observation_id}")
    assert as_r2.status_code == 200 and two_runs["r2"] in as_r2.text
    assert svc.RUN_CONTEXT_MISMATCH not in as_r2.text
    as_r1 = client.get(side.evidence_url)
    assert as_r1.status_code == 409 and side.observed_text not in as_r1.text
