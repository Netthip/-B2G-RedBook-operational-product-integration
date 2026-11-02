# -*- coding: utf-8 -*-
"""P5-1 (Pass 6) — หน้าก่อนตรวจผ่านต้อง **ไม่มีตัวเลขหรือแฮชใดของเครื่อง** (ทดสอบด้วย sentinel)

🔴 คำสั่ง Bo (`5615776981` P5-1) — *"KEY BUILD may expose documents, page evidence, human
inventory, and an opaque sealed/not-sealed state, but not detector pair counts, observation
counts, detector digests, statuses, or summaries … Add detector-only-state HTML tests that use
unique count/digest sentinels and prove they are absent."*

วิธีทดสอบ
---------
สร้างรอบจริงแล้วเติมแถวหลอกเข้าตารางของเครื่อง **ก่อนผนึกเครื่อง** จนจำนวนคู่ = ``PAIR_SENTINEL``
และจำนวนข้อสังเกต = ``OBS_SENTINEL`` (ตัวเลขที่ไม่น่าจะปรากฏในหน้าโดยบังเอิญ) · ผนึกเครื่อง ⇒
ตัวเลขทั้งสองและแฮชทุกส่วนของผนึกกลายเป็นข้อมูลที่หน้าจอ **เคย** แสดงได้ แล้วตรวจว่าไม่ปรากฏใน
หน้าจัดทำเฉลย · หน้าล็อก · หน้า audit · หน้ารายการรอบ ขณะที่ทะเบียนที่คนกรอกและหน้าเอกสารยังเปิดได้

การค้นตัวเลขใช้ขอบเขตที่ไม่ใช่ตัวอักษร/ตัวเลข — เพื่อไม่ให้ตัวเลขที่บังเอิญอยู่ **ข้างใน** แฮชฐานสิบหก
ของรายการ audit อื่นทำให้เทสต์ล้มโดยไม่มีเหตุ

🔴 **SYNTHETIC TEST FIXTURE** — เอกสารและ "เฉลย" ทั้งหมดแต่งขึ้นเพื่อทดสอบกลไก
"""
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import keystage
from redbook import config
from redbook.app import create_app
from redbook.evidence import documents as docs
from redbook.indicators import registry as reg
from redbook.services import evidence as svc
from redbook.storage import audit

FIX = Path(__file__).parent / "fixtures" / "synthetic_pdf"

PAIR_SENTINEL = 2917
OBS_SENTINEL = 1373


def _absent_number(html: str, n: int) -> bool:
    return re.search(r"(?<![0-9A-Za-z])%d(?![0-9A-Za-z])" % n, html) is None


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


def _pad_detector_tables(run_id):
    """เติมแถวหลอกจนจำนวนคู่/ข้อสังเกตเท่า sentinel — ทำ **ก่อน** ผนึกเครื่อง"""
    conn = sqlite3.connect(config.DB_PATH)
    try:
        n_pairs = conn.execute("SELECT COUNT(*) FROM ind_mappings WHERE run_id = ?",
                               (run_id,)).fetchone()[0]
        n_obs = conn.execute("SELECT COUNT(*) FROM ind_observations WHERE run_id = ?",
                             (run_id,)).fetchone()[0]
        sha = "e" * 64
        for i in range(OBS_SENTINEL - n_obs):
            conn.execute(
                "INSERT INTO ind_observations (observation_id, run_id, side, document_id, "
                "page, line_index, observed_text, normalized_text, x0, y0, x1, y1, "
                "page_width, page_height, location_confidence, source_sha256, "
                "extractor_version, anchor, identity_key, geometry_flags_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("obs_pad_%05d" % i, run_id, "new", "doc_pad", 1, 10000 + i,
                 "pad %d" % i, "pad %d" % i, 0, 0, 1, 1, 595, 842, "EXACT", sha,
                 "pad", "line:%d" % (10000 + i), "", "[]"))
        for i in range(PAIR_SENTINEL - n_pairs):
            conn.execute(
                "INSERT INTO ind_mappings (mapping_id, run_id, old_observation_id, "
                "new_observation_id, proposed_status, human_required, basis_json, "
                "differences_json, alternatives_json, internal_score) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("map_pad_%05d" % i, run_id, "", "obs_pad_%05d" % (i % 10), "NEW_INDICATOR",
                 0, "[]", "[]", "[]", 0.0))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="module")
def world(client, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("blindness")
    old_p, new_p = tmp / "o.pdf", tmp / "n.pdf"
    old_p.write_bytes((FIX / "synthetic_old_fy2569.pdf").read_bytes() + b"\n%blind-p6\n")
    new_p.write_bytes((FIX / "synthetic_new_fy2570.pdf").read_bytes() + b"\n%blind-p6\n")
    kw = dict(stage=docs.STAGE_DRAFT_BILL, authority="SYNTHETIC",
              disclosure_class=docs.DISC_SYNTHETIC)
    old = svc.register_pdf(old_p, title="เก่า-P6", fiscal_year=2569, **kw)
    new = svc.register_pdf(new_p, title="ใหม่-P6", fiscal_year=2570, **kw)
    rid = svc.run_indicator_pipeline(old.document_id, new.document_id,
                                     label="BLINDNESS-P6").run_id
    keystage.build_and_freeze(rid)
    _pad_detector_tables(rid)
    keystage.seal_detector(rid)
    snap = reg.detector_snapshot(rid)
    assert snap.pair_count == PAIR_SENTINEL and snap.observation_count == OBS_SENTINEL
    assert reg.adjudication_unlocked(rid) is False
    digests = [snap.snapshot_digest, snap.mappings_digest, snap.observations_digest,
               snap.metadata_digest, snap.documents_digest]
    inventory_text = reg.source_inventory_rows(rid)[0].observed_text
    return {"run": rid, "old": old, "new": new, "digests": digests,
            "inventory_text": inventory_text}


def _assert_blind(html: str, world, where: str):
    assert _absent_number(html, PAIR_SENTINEL), (where, "pair count")
    assert _absent_number(html, OBS_SENTINEL), (where, "observation count")
    for d in world["digests"]:
        for fragment in (d, d[:16], d[:12]):
            assert fragment not in html, (where, "digest", fragment)


def test_key_build_page_shows_only_an_opaque_detector_state(client, world):
    html = client.get(f"/indicators/runs/{world['run']}/keybuild").text
    _assert_blind(html, world, "keybuild")
    assert svc.BLIND_DETECTOR_SEALED in html
    assert "ไม่แสดงรายละเอียดของชั้นนี้" in html


def test_key_build_page_still_shows_human_inventory_and_page_evidence(client, world):
    html = client.get(f"/indicators/runs/{world['run']}/keybuild").text
    assert world["inventory_text"] in html, "ทะเบียนที่คนกรอกต้องยังเห็นได้"
    page = client.get(f"/evidence/{world['old'].document_id}?page=1&run={world['run']}")
    assert page.status_code == 200
    _assert_blind(page.text, world, "page evidence")


def test_locked_pages_are_blind(client, world):
    for url in (f"/indicators/runs/{world['run']}",
                f"/indicators/runs/{world['run']}/verify"):
        r = client.get(url)
        assert r.status_code == 409
        _assert_blind(r.text, world, url)


def test_run_list_is_blind(client, world):
    _assert_blind(client.get("/indicators/runs").text, world, "run list")


def test_audit_page_redacts_detector_fields_of_this_run(client, world):
    html = client.get("/audit").text
    _assert_blind(html, world, "audit")
    redacted = svc.redact_audit_entries(audit.entries(limit=300, object_id=world["run"]))
    sealed = [e for e in redacted if e["action"] == "indicator_detector_snapshot_sealed"]
    completed = [e for e in redacted if e["action"] == "indicator_run_completed"]
    assert sealed and completed
    for e in sealed + completed:
        assert svc.AUDIT_REDACTED in e["detail_json"]
        assert '"by_status"' not in e["detail_json"] or "SAME_EXACT" not in e["detail_json"]


def test_audit_chain_is_untouched_by_redaction(world):
    """ปิดบังตอนแสดงเท่านั้น — ข้อมูลที่บันทึกไว้และ hash chain ไม่เปลี่ยน"""
    raw = audit.entries(limit=300, object_id=world["run"])
    assert any(str(PAIR_SENTINEL) in e["detail_json"] for e in raw)
    assert audit.verify_chain()["ok"] is True


def test_blind_view_model_has_no_detector_fields(world):
    """ระดับ view model — ไม่มีวัตถุผนึกของเครื่อง จำนวน หรือแฮชใด ๆ ส่งเข้าหน้า"""
    kv = svc.key_universe_view(world["run"])
    assert not hasattr(kv, "detector_seal")
    assert kv.detector_sealed is True
    det = [r for r in kv.blind.rows if r.artifact == "DETECTOR_OUTPUT"][0]
    assert det.ok is None and det.reasons == () and det.digest_prefix == ""
    blob = repr(kv.blind) + repr(kv.detector_sealed)
    for d in world["digests"]:
        assert d not in blob and d[:16] not in blob


def test_after_full_verification_the_audit_details_become_visible(world):
    """กรณีควบคุม — ผนึกเฉลยครบแล้วตรวจผ่าน ⇒ ปิดบังไม่ทำงานอีก (ไม่ได้ซ่อนตลอดไป)

    ต้องอยู่ท้ายไฟล์ เพราะเปลี่ยนสภาวะของรอบจากล็อกเป็นเปิด
    """
    keystage.answer_all(world["run"])
    reg.seal_key(world["run"], sealed_by="gift", note=keystage.SYNTHETIC_NOTE)
    assert reg.adjudication_unlocked(world["run"]) is True
    shown = svc.redact_audit_entries(audit.entries(limit=300, object_id=world["run"]))
    sealed = [e for e in shown if e["action"] == "indicator_detector_snapshot_sealed"][0]
    assert svc.AUDIT_REDACTED not in sealed["detail_json"]
    assert str(PAIR_SENTINEL) in sealed["detail_json"]
