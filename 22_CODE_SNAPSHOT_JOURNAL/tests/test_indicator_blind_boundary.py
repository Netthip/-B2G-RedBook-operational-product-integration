# -*- coding: utf-8 -*-
"""Pass 5 — ขอบเขตของการเปิดผลเครื่อง (P4-1) และไฟล์ส่งออก (P4-2)

🔴 คำสั่ง Bo (`5606392284`)

* **P4-1** — *"every route/view that exposes detector observations, pairs, statuses, basis,
  differences, counts, coverage comparison, or report summaries must return the locked page
  until all seal checks pass … Add route tests proving the report and every detector-output
  URL are inaccessible at 0-of-N, after universe freeze only, after detector seal only, and
  after any seal mismatch."*
* **P4-2** — *"create package → tamper a sealed input → download must be rejected …
  refuse legacy/unbound files … Do not delete prior files."*

ไฟล์นี้สร้างรอบจริงผ่าน pipeline จาก fixture PDF สังเคราะห์ **หนึ่งรอบต่อหนึ่งสภาวะ**
แล้วเรียกทุก URL ที่เปิดผลเครื่องผ่าน TestClient

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
from redbook.indicators import keyuniverse as ku
from redbook.indicators import registry as reg
from redbook.services import evidence as svc
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD

FIX = Path(__file__).parent / "fixtures" / "synthetic_pdf"

STATE_ZERO = "0-of-N"
STATE_UNIVERSE_ONLY = "universe-frozen-only"
STATE_DETECTOR_ONLY = "detector-sealed-only"
STATE_MISMATCH = "seal-mismatch"
STATE_UNLOCKED = "unlocked-control"
LOCKED_STATES = (STATE_ZERO, STATE_UNIVERSE_ONLY, STATE_DETECTOR_ONLY, STATE_MISMATCH)


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


def _tamper_detector(run_id):
    """แทรกคู่ปลอมเข้า ``ind_mappings`` ของรอบนั้น — ตารางนี้ห้ามแก้/ลบ แต่ไม่ห้ามเพิ่ม"""
    conn = sqlite3.connect(config.DB_PATH)
    try:
        conn.execute(
            "INSERT INTO ind_mappings (mapping_id, run_id, old_observation_id, "
            "new_observation_id, proposed_status, human_required, basis_json, "
            "differences_json, alternatives_json, internal_score) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("map_tamper_" + run_id[-6:], run_id, "", "", "NEW_INDICATOR", 0,
             "[]", "[]", "[]", 0.0))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="module")
def runs(client, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("blind")
    old_p, new_p = tmp / "o.pdf", tmp / "n.pdf"
    old_p.write_bytes((FIX / "synthetic_old_fy2569.pdf").read_bytes())
    new_p.write_bytes((FIX / "synthetic_new_fy2570.pdf").read_bytes())
    kw = dict(stage=docs.STAGE_DRAFT_BILL, authority="SYNTHETIC",
              disclosure_class=docs.DISC_SYNTHETIC)
    old = svc.register_pdf(old_p, title="เก่า", fiscal_year=2569, **kw)
    new = svc.register_pdf(new_p, title="ใหม่", fiscal_year=2570, **kw)
    out = {"old": old, "new": new}
    for state in (STATE_ZERO, STATE_UNIVERSE_ONLY, STATE_DETECTOR_ONLY, STATE_MISMATCH,
                  STATE_UNLOCKED):
        rid = svc.run_indicator_pipeline(old.document_id, new.document_id,
                                         label="BLIND-" + state).run_id
        if state == STATE_UNIVERSE_ONLY:
            keystage.build_and_freeze(rid)
        elif state == STATE_DETECTOR_ONLY:
            keystage.ready_for_answers(rid)
        elif state in (STATE_MISMATCH, STATE_UNLOCKED):
            keystage.unlock_adjudication(rid)
            assert reg.adjudication_unlocked(rid) is True
        out[state] = rid
    _tamper_detector(out[STATE_MISMATCH])
    return out


def _detector_refs(run_id):
    """ข้อสังเกตหนึ่งตัวและคู่หนึ่งคู่ของเครื่อง — อ่านจากทะเบียนตรง ๆ (ไม่ผ่าน route)"""
    obs = next(iter(reg.observations(run_id).values()))
    mapping = reg.mappings(run_id)[0]
    return obs, mapping


def _token(client):
    client.get("/")
    return client.cookies.get(CSRF_COOKIE)


def _detector_urls(runs, run_id):
    obs, mapping = _detector_refs(run_id)
    doc = runs["old"].document_id if obs.extra.get("side") == "old" else runs["new"].document_id
    return {
        "report": f"/indicators/runs/{run_id}",
        "verify": f"/indicators/runs/{run_id}/verify",
        "compare": f"/evidence/compare?run={run_id}&map={mapping.mapping_id}",
        "observation": f"/evidence/{doc}?page={obs.page}&obs={obs.observation_id}&run={run_id}",
    }, obs, mapping


# ══════════════════════════════════════════════════════════════════════════════
#  P4-1 — ทุก URL ที่เปิดผลเครื่อง ล็อกในทุกสภาวะที่ยังไม่ผ่าน
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("state", LOCKED_STATES)
def test_every_detector_output_url_is_locked(client, runs, state):
    run_id = runs[state]
    assert reg.adjudication_unlocked(run_id) is False, state
    urls, obs, mapping = _detector_urls(runs, run_id)
    for name, url in urls.items():
        r = client.get(url)
        assert r.status_code == 409, (state, name, r.status_code)
        assert obs.observed_text not in r.text, (state, name)
        assert mapping.proposed_status not in r.text or name == "observation", (state, name)


@pytest.mark.parametrize("state", LOCKED_STATES)
def test_detector_writes_are_locked_before_touching_detector_rows(client, runs, state):
    run_id = runs[state]
    _, mapping = _detector_refs(run_id)
    token = _token(client)
    decide = client.post(f"/indicators/runs/{run_id}/mappings/{mapping.mapping_id}/decide",
                         data={"decision": "ACCEPT", "final_status": "", "reason": "x",
                               "reviewer": "gift", CSRF_FIELD: token})
    assert decide.status_code == 409, state
    package = client.post(f"/indicators/runs/{run_id}/package", data={CSRF_FIELD: token})
    assert package.status_code == 409, state


@pytest.mark.parametrize("state", LOCKED_STATES)
def test_run_list_hides_detector_counts_for_locked_runs(client, runs, state):
    run_id = runs[state]
    html = client.get("/indicators/runs").text
    row = re.search(r"<tr><td class=\"mono\">" + re.escape(run_id) + r"</td>(.*?)</tr>",
                    html, flags=re.S)
    assert row, state
    body = row.group(1)
    assert "ปิดไว้จนกว่าผนึกครบและตรวจผ่าน" in body
    assert f'href="/indicators/runs/{run_id}"' not in body
    assert f"/indicators/runs/{run_id}/keybuild" in body


@pytest.mark.parametrize("state", (STATE_ZERO, STATE_UNIVERSE_ONLY, STATE_DETECTOR_ONLY))
def test_key_build_page_has_no_route_to_detector_output(client, runs, state):
    run_id = runs[state]
    html = client.get(f"/indicators/runs/{run_id}/keybuild").text
    assert f'href="/indicators/runs/{run_id}"' not in html, "ลิงก์รายงานต้องไม่อยู่ในขั้นเฉลย"
    assert f"/indicators/runs/{run_id}/verify" not in html
    assert "/evidence/compare" not in html
    assert "&obs=" not in html and "?obs=" not in html


def test_detector_coverage_is_locked_in_every_state(runs):
    for state in LOCKED_STATES:
        with pytest.raises(reg.KeyStageError):
            svc.detector_coverage(runs[state])


def test_page_evidence_without_detector_observation_stays_open(client, runs):
    """ขั้นเฉลยต้องเปิดหน้าเอกสารได้ — ไม่ชี้ข้อสังเกตของเครื่อง ⇒ ไม่ถูกล็อก"""
    run_id = runs[STATE_ZERO]
    r = client.get(f"/evidence/{runs['old'].document_id}?page=1&run={run_id}")
    assert r.status_code == 200
    assert f'href="/indicators/runs/{run_id}"' not in r.text


def test_mismatch_locked_page_is_opaque_about_the_detector(client, runs):
    """🔴 Pass 6 (Bo `5615776981` P5-1) — เดิมเทสต์นี้ *บังคับ* ให้หน้าล็อกแสดงเหตุผลเฉพาะของเครื่อง
    ("จำนวนคู่ไม่ตรง") ซึ่งคือข้อมูลที่มาจากเครื่องก่อนตรวจผ่าน · ตอนนี้หน้าล็อกบอกได้เพียงว่า
    ผนึกครบแล้วแต่ตรวจไม่ผ่าน และต้องเปิดรอบใหม่ · เหตุผลเฉพาะอยู่ใน log ของเครื่องเท่านั้น
    """
    r = client.get(f"/indicators/runs/{runs[STATE_MISMATCH]}")
    assert r.status_code == 409
    assert svc.BLIND_ALL_SEALED_BUT_FAILED in r.text
    for code, label in ku.REASON_LABELS.items():
        if code.startswith("DETECTOR_"):
            assert label not in r.text and code not in r.text, code


def test_unlocked_control_opens_every_detector_url(client, runs):
    """สภาวะควบคุม — เมื่อผ่านครบจริง ทุก URL ต้องเปิดได้ (ด่านไม่ได้ปิดตายทุกกรณี)"""
    run_id = runs[STATE_UNLOCKED]
    urls, _, _ = _detector_urls(runs, run_id)
    for name, url in urls.items():
        assert client.get(url).status_code == 200, name
    html = client.get("/indicators/runs").text
    assert f'href="/indicators/runs/{run_id}"' in html


# ══════════════════════════════════════════════════════════════════════════════
#  P4-2 — ไฟล์ส่งออกผูกกับรอบ และถูกปฏิเสธเมื่อผนึกไม่ตรง
# ══════════════════════════════════════════════════════════════════════════════

def _make_package(client, run_id):
    token = _token(client)
    w = client.post(f"/indicators/runs/{run_id}/package", data={CSRF_FIELD: token})
    assert w.status_code == 200
    m = re.search(r"/indicators/runs/" + re.escape(run_id)
                  + r"/exports/(indpkg_[A-Za-z0-9_]+\.xlsx)", w.text)
    assert m, "ลิงก์ดาวน์โหลดต้องระบุรอบ"
    return m.group(1)


def test_export_is_rejected_after_a_sealed_input_is_tampered(client, runs, tmp_path_factory):
    """create package → tamper a sealed input → download must be rejected"""
    kw = dict(stage=docs.STAGE_DRAFT_BILL, authority="SYNTHETIC",
              disclosure_class=docs.DISC_SYNTHETIC)
    rid = svc.run_indicator_pipeline(runs["old"].document_id, runs["new"].document_id,
                                     label="BLIND-EXPORT").run_id
    keystage.unlock_adjudication(rid)
    name = _make_package(client, rid)
    url = f"/indicators/runs/{rid}/exports/{name}"
    ok = client.get(url)
    assert ok.status_code == 200 and ok.content[:2] == b"PK"

    _tamper_detector(rid)
    refused = client.get(url)
    assert refused.status_code == 409
    assert reg.EXPORT_REASON_LABELS[reg.EXPORT_SEALS_NOT_VERIFIED] in refused.text
    # ไม่ลบไฟล์เดิม
    assert (config.EXPORT_DIR / name).is_file()
    del kw


def test_export_of_another_run_is_refused(client, runs):
    name = _make_package(client, runs[STATE_UNLOCKED])
    other = runs[STATE_ZERO]
    r = client.get(f"/indicators/runs/{other}/exports/{name}")
    assert r.status_code == 409
    assert reg.EXPORT_REASON_LABELS[reg.EXPORT_RUN_MISMATCH] in r.text


def test_changed_export_file_is_refused(client, runs):
    run_id = runs[STATE_UNLOCKED]
    name = _make_package(client, run_id)
    path = config.EXPORT_DIR / name
    path.write_bytes(path.read_bytes() + b"tamper")
    r = client.get(f"/indicators/runs/{run_id}/exports/{name}")
    assert r.status_code == 409
    assert reg.EXPORT_REASON_LABELS[reg.EXPORT_FILE_CHANGED] in r.text


def test_legacy_unbound_file_is_refused_and_not_deleted(client, runs):
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    legacy = config.EXPORT_DIR / "indpkg_legacy_unbound_test.xlsx"
    legacy.write_bytes(b"PK legacy")
    run_id = runs[STATE_UNLOCKED]
    scoped = client.get(f"/indicators/runs/{run_id}/exports/{legacy.name}")
    assert scoped.status_code == 409
    assert reg.EXPORT_REASON_LABELS[reg.EXPORT_NOT_BOUND] in scoped.text
    assert client.get(f"/indicators/exports/{legacy.name}").status_code == 410
    assert legacy.is_file(), "ห้ามลบไฟล์เดิม"


def test_export_manifest_is_append_only(runs):
    conn = sqlite3.connect(config.DB_PATH)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM ind_export_manifests")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE ind_export_manifests SET file_sha256 = 'x'")
    finally:
        conn.close()
