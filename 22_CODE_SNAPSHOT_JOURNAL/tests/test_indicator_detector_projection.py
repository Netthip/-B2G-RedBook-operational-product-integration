# -*- coding: utf-8 -*-
"""P5-2 (Pass 6) — ผนึกเครื่องครอบ **ทุกคอลัมน์** ที่ปลายทางใช้ · mutation แยกตามกลุ่มฟิลด์

🔴 คำสั่ง Bo (`5615776981` P5-2) — *"Define one versioned canonical projection covering all
effective mapping and observation fields consumed downstream … Avoid another partial field list
… Add mutation tests by field family. Each mutation must invalidate the detector seal and block
report, coverage, package, and export. Include an unchanged control that remains open."*

แต่ละกรณีสร้างรอบจริงจากเอกสารสังเคราะห์ **ที่ไม่ซ้ำกับกรณีอื่น** (เติมไบต์ท้ายไฟล์ให้แฮชต่าง)
เพราะแถว ``evd_documents`` ใช้ร่วมกันข้ามรอบ — แก้เอกสารของกรณีหนึ่งต้องไม่ลามไปรอบของกรณีอื่น
การแก้ข้อมูลทำนอกเส้นทางของแอป (ถอด trigger → แก้ → **ใส่ trigger คืน**) เพื่อไม่ทิ้งฐานข้อมูล
ของชุดทดสอบไว้ในสภาพที่ไม่มีด่าน append-only

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
from redbook.indicators import mapping as mp
from redbook.indicators import observe as ob
from redbook.indicators import registry as reg
from redbook.services import evidence as svc
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD

FIX = Path(__file__).parent / "fixtures" / "synthetic_pdf"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


def _token(client):
    client.get("/")
    return client.cookies.get(CSRF_COOKIE)


def _tamper(table, sql, params):
    """แก้ข้อมูลนอกเส้นทางของแอป แล้ว **ใส่ trigger คืน** ทันที"""
    conn = sqlite3.connect(config.DB_PATH)
    try:
        triggers = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' "
                                "AND tbl_name = ?", (table,)).fetchall()
        for name, _ in triggers:
            conn.execute('DROP TRIGGER "%s"' % name)
        conn.execute(sql, params)
        for _, create in triggers:
            conn.execute(create)
        conn.commit()
    finally:
        conn.close()


_CASE_SEQ = [0]


def _fresh_unlocked_run(client, tmp_path_factory, tag):
    """รอบใหม่ที่ผนึกครบและตรวจผ่าน + ชุดส่งออกหนึ่งชุด — เอกสารไม่ซ้ำกับกรณีอื่น"""
    _CASE_SEQ[0] += 1
    tmp = tmp_path_factory.mktemp("proj")
    marker = ("\n%%proj-%s-%d\n" % (tag, _CASE_SEQ[0])).encode("ascii")
    old_p, new_p = tmp / "o.pdf", tmp / "n.pdf"
    old_p.write_bytes((FIX / "synthetic_old_fy2569.pdf").read_bytes() + marker)
    new_p.write_bytes((FIX / "synthetic_new_fy2570.pdf").read_bytes() + marker)
    kw = dict(stage=docs.STAGE_DRAFT_BILL, authority="SYNTHETIC",
              disclosure_class=docs.DISC_SYNTHETIC)
    old = svc.register_pdf(old_p, title="เก่า", fiscal_year=2569, **kw)
    new = svc.register_pdf(new_p, title="ใหม่", fiscal_year=2570, **kw)
    rid = svc.run_indicator_pipeline(old.document_id, new.document_id,
                                     label="PROJ-" + tag).run_id
    keystage.unlock_adjudication(rid)
    assert reg.adjudication_unlocked(rid) is True
    token = _token(client)
    w = client.post(f"/indicators/runs/{rid}/package", data={CSRF_FIELD: token})
    m = re.search(r"/indicators/runs/" + re.escape(rid) + r"/exports/(indpkg_[A-Za-z0-9_]+\.xlsx)",
                  w.text)
    assert m
    return {"run": rid, "old": old, "new": new,
            "export": f"/indicators/runs/{rid}/exports/{m.group(1)}"}


def _assert_everything_blocked(client, world, reason):
    rid = world["run"]
    check = reg.verify_detector_snapshot(rid)
    assert check.ok is False and reason in check.reasons, (reason, check.reasons)
    assert reg.adjudication_unlocked(rid) is False
    assert client.get(f"/indicators/runs/{rid}").status_code == 409          # report
    with pytest.raises(reg.KeyStageError):                                    # coverage
        svc.detector_coverage(rid)
    token = _token(client)
    assert client.post(f"/indicators/runs/{rid}/package",
                       data={CSRF_FIELD: token}).status_code == 409          # package
    assert client.get(world["export"]).status_code == 409                     # export


# ══════════════════════════════════════════════════════════════════════════════
#  mutation แยกตามกลุ่มฟิลด์ — ทุกกรณีผ่าน route จริง
# ══════════════════════════════════════════════════════════════════════════════

FAMILIES = [
    # (ชื่อกรณี, ตาราง, SET clause, เหตุผลที่ต้องได้)
    ("mapping.human_required", "ind_mappings",
     "human_required = 1 - human_required", ku.R_DETECTOR_MAPPINGS_MISMATCH),
    ("mapping.differences_json", "ind_mappings",
     "differences_json = '[{\"field_name\":\"unit\",\"old\":\"a\",\"new\":\"b\"}]'",
     ku.R_DETECTOR_MAPPINGS_MISMATCH),
    ("mapping.alternatives_json", "ind_mappings",
     "alternatives_json = '[\"obs_x\"]'", ku.R_DETECTOR_MAPPINGS_MISMATCH),
    ("observation.geometry", "ind_observations", "x0 = x0 + 1", ku.R_DETECTOR_OBSERVATIONS_MISMATCH),
    ("observation.page_dimensions", "ind_observations", "page_width = page_width + 1",
     ku.R_DETECTOR_OBSERVATIONS_MISMATCH),
    ("observation.location_confidence", "ind_observations",
     "location_confidence = 'PAGE_ONLY'", ku.R_DETECTOR_OBSERVATIONS_MISMATCH),
    ("observation.semantic.unit", "ind_observations", "unit = 'หน่วยที่แก้'",
     ku.R_DETECTOR_OBSERVATIONS_MISMATCH),
    ("observation.semantic.target_text", "ind_observations", "target_text = 'เป้าที่แก้'",
     ku.R_DETECTOR_OBSERVATIONS_MISMATCH),
    ("observation.semantic.method_text", "ind_observations", "method_text = 'วิธีที่แก้'",
     ku.R_DETECTOR_OBSERVATIONS_MISMATCH),
    ("observation.semantic.cues_json", "ind_observations", "cues_json = '[\"x\"]'",
     ku.R_DETECTOR_OBSERVATIONS_MISMATCH),
    ("run.accounted_json", "ind_runs", "accounted_json = '{}'", ku.R_DETECTOR_METADATA_MISMATCH),
    ("run.label", "ind_runs", "label = 'เปลี่ยนป้าย'", ku.R_DETECTOR_METADATA_MISMATCH),
    ("document.disclosure_class", "evd_documents", "disclosure_class = 'INTERNAL'",
     ku.R_DETECTOR_DOCUMENTS_MISMATCH),
    ("document.stage", "evd_documents", "stage = 'ENACTED'", ku.R_DETECTOR_DOCUMENTS_MISMATCH),
    ("document.title", "evd_documents", "title = 'ชื่อที่แก้'", ku.R_DETECTOR_DOCUMENTS_MISMATCH),
]


@pytest.mark.parametrize("name,table,set_clause,reason", FAMILIES,
                         ids=[f[0] for f in FAMILIES])
def test_field_family_mutation_blocks_report_coverage_package_and_export(
        client, tmp_path_factory, name, table, set_clause, reason):
    world = _fresh_unlocked_run(client, tmp_path_factory, name.replace(".", "-"))
    if table == "ind_runs":
        _tamper(table, "UPDATE ind_runs SET %s WHERE id = ?" % set_clause, (world["run"],))
    elif table == "evd_documents":
        _tamper(table, "UPDATE evd_documents SET %s WHERE document_id = ?" % set_clause,
                (world["old"].document_id,))
    else:
        _tamper(table, "UPDATE %s SET %s WHERE run_id = ?" % (table, set_clause),
                (world["run"],))
    _assert_everything_blocked(client, world, reason)


def test_unchanged_control_stays_open(client, tmp_path_factory):
    """กรณีควบคุม — ไม่แก้อะไร ⇒ ทุกเส้นทางยังเปิด (ด่านไม่ได้ปิดตาย)"""
    world = _fresh_unlocked_run(client, tmp_path_factory, "control")
    rid = world["run"]
    assert reg.verify_detector_snapshot(rid).ok is True
    assert client.get(f"/indicators/runs/{rid}").status_code == 200
    assert svc.detector_coverage(rid).inventory_total > 0
    token = _token(client)
    assert client.post(f"/indicators/runs/{rid}/package",
                       data={CSRF_FIELD: token}).status_code == 200
    r = client.get(world["export"])
    assert r.status_code == 200 and r.content[:2] == b"PK"


# ══════════════════════════════════════════════════════════════════════════════
#  projection มาจาก schema จริง — ไม่มีรายการฟิลด์ที่เลือกเอง
# ══════════════════════════════════════════════════════════════════════════════

def test_projection_covers_every_column_except_declared_exclusions(fresh_db):
    reg.init_schema(fresh_db)
    projection = reg.detector_projection_columns(fresh_db)
    conn = sqlite3.connect(fresh_db)
    try:
        for part, (table, cols) in projection.items():
            actual = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]
            excluded = set(ku.DETECTOR_PROJECTION_EXCLUDED.get(table, ()))
            assert set(cols) == set(actual) - excluded, (part, table)
    finally:
        conn.close()
    assert ku.DETECTOR_PROJECTION_EXCLUDED == {"evd_documents": ("local_path_private",)}
    mapping_cols = projection["mappings"][1]
    for must in ("human_required", "differences_json", "alternatives_json", "basis_json",
                 "internal_score", "proposed_status"):
        assert must in mapping_cols, must
    obs_cols = projection["observations"][1]
    for must in ("x0", "y0", "x1", "y1", "page_width", "page_height", "unit", "target_text",
                 "target_value", "baseline_text", "method_text", "period_text", "ordinal",
                 "cues_json", "geometry_flags_json", "location_confidence"):
        assert must in obs_cols, must


def _sealed_fresh(fresh_db):
    reg.init_schema(fresh_db)
    o = [ob.manual_observation("doc_old", "a" * 64, page=1, observed_text="ร้อยละ 90",
                               page_width=595.0)]
    n = [ob.manual_observation("doc_new", "b" * 64, page=1, observed_text="ร้อยละ 90",
                               page_width=595.0)]
    c = mp.propose(o, n)
    reg.save_run(run_id="pj1", old_document_id="doc_old", new_document_id="doc_new",
                 old_obs=o, new_obs=n, candidates=c, rules=mp.Rules(),
                 extractor_version=ob.OBSERVE_VERSION, normalize_version="n",
                 text_backend="test", accounted=mp.accounted(o, n, c), page_inventory={},
                 old_page_count=3, new_page_count=3, db_path=fresh_db)
    keystage.unlock_adjudication("pj1", fresh_db)
    assert reg.adjudication_unlocked("pj1", fresh_db) is True


def test_a_column_added_in_the_future_is_covered_automatically(fresh_db):
    """เพิ่มคอลัมน์ใหม่ในตารางผลเครื่อง ⇒ ผนึกเดิมตรวจไม่ผ่านทันที โดยไม่ต้องแก้โค้ด projection"""
    _sealed_fresh(fresh_db)
    conn = sqlite3.connect(fresh_db)
    try:
        conn.execute("ALTER TABLE ind_mappings ADD COLUMN future_field TEXT DEFAULT 'x'")
        conn.commit()
    finally:
        conn.close()
    check = reg.verify_detector_snapshot("pj1", fresh_db)
    assert check.ok is False and ku.R_DETECTOR_MAPPINGS_MISMATCH in check.reasons
    assert reg.adjudication_unlocked("pj1", fresh_db) is False


def test_protocol_0_2_0_seal_locks_and_is_not_reinterpreted(fresh_db):
    """ผนึก 0.2.0 (รายการฟิลด์ที่เลือกเอง) ต้องล็อก — ไม่ซ่อม ไม่ตีความใหม่"""
    _sealed_fresh(fresh_db)
    conn = sqlite3.connect(fresh_db)
    try:
        conn.execute("DROP TRIGGER ind_detector_snapshots_no_update")
        conn.execute("UPDATE ind_detector_snapshots SET snapshot_protocol = "
                     "'detector-snapshot-0.2.0' WHERE run_id = 'pj1'")
        conn.commit()
    finally:
        conn.close()
    check = reg.verify_detector_snapshot("pj1", fresh_db)
    assert check.ok is False and ku.R_DETECTOR_PROTOCOL_OUTDATED in check.reasons
    with pytest.raises(reg.KeyStageError):
        reg.seal_detector_snapshot("pj1", sealed_by="gift", db_path=fresh_db)


def test_canonical_digest_distinguishes_null_from_empty_and_is_order_free():
    rows = [{"a": 1, "b": None}, {"a": 2, "b": ""}]
    d = ku.canonical_rows_digest("t", ["a", "b"], rows)
    assert d == ku.canonical_rows_digest("t", ["b", "a"], list(reversed(rows)))
    assert d != ku.canonical_rows_digest("t", ["a", "b"], [{"a": 1, "b": ""}, {"a": 2, "b": ""}])
    assert d != ku.canonical_rows_digest("t", ["a", "b"], [{"a": 1.0, "b": None},
                                                           {"a": 2, "b": ""}])
