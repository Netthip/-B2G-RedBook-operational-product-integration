# -*- coding: utf-8 -*-
"""ทดลองตรวจเล่มสำหรับผู้ปฏิบัติงาน (#43 · ``services/trial``) — นับตามวิธีวัดผลฉบับ 0.2 (ร่าง)

🔴 **SYNTHETIC DEMONSTRATION DATA** — เล่มจาก ``scripts/demo_redbook_book_pdf.py`` · ไม่ใช่ผลประเมิน

ชุดตรวจ (สเปก: repo เล่ม ``04_methodology/MEASUREMENT_METHOD_R3_PDF.md`` หมวด 2–8 และ 13)

* เล่มทดสอบมาจากไฟล์ตั้งค่าของเครื่อง · เล่มที่ไม่อยู่บนชั้น/หน่วยที่กันไว้ไม่แสดง · ชนิดคู่จากปีงบของสองเล่ม
* **ไม่มีรอบเทียบก่อนล็อก** · ล็อก = ใบประกาศก่อนเห็นผล (ไม่บังคับกด "ตรวจหน้านี้แล้ว" ครบทุกหน้า) ·
  ทาง ร1 สร้างแถวตามจำนวนที่ประกาศ · ทาง ร2 ทุกจุดต้องมีหัวข้อ/ส่วน/ต-ล/ระดับ (หมุด + ขอบเขตที่ค้น) ·
  ชุดจุดตรวจซ้ำในธุรกรรมเดียวกับการล็อก · การเปิดดูผลไม่สร้างรอบเทียบ
* ข้อมูลประกอบเสนอคู่และยืนยันคู่ได้ — ความต่างข้ามปีที่ระบบยกเป็นข้อมูลประกอบ นับเป็น **พบ** ไม่ใช่พลาด
* พบตรง/บางส่วน(บ1–บ4)/พลาด(พ1–พ5)/ตัดสินไม่ได้ · หลักฐานชี้ตำแหน่ง · ฐานการวินิจฉัย · หนึ่งต่อหลาย/หลายต่อหนึ่ง ·
  เปลี่ยนคู่ต้องมีเหตุผล (ประวัติ) · ส่วนที่อ่านไม่ได้จับคู่เป็นพบไม่ได้
* ส1–ส4 / นอกส่วนที่ตรวจครบ · บัญชี F = จ + ส1 + ส2 + ส3 + ส4 · ข้อมูลไม่สอดคล้อง = ล้มดัง ๆ (ห้ามรายงาน)
* N = ประเด็นในส่วนที่ตรวจครบและหัวข้อที่ครอบคลุม − ตัดสินไม่ได้ · ร้อยละเฉพาะตัวหาร ≥ 10 · ตัวหาร 0 = คำนวณไม่ได้
* หยุด/ถอนตัว/ล้มเหลว · รอบกติกา 0.1 อ่านได้ (ยังไม่ส่ง = ทำต่อได้) · ฐานข้อมูลรุ่นเก่าได้คอลัมน์ใหม่
* แบบสอบถามตรงแบบ 03 ฉบับ 0.2 และเปิดได้หลังจบการใช้ผล · สรุปเป็นจำนวนเท่านั้น · ทุกการเปลี่ยนลง Audit
* เว็บ: CSRF ทุก POST · ไม่มีสคริปต์ฝังในหน้า · คำชี้แจงเป็นกลาง · ชื่อฉบับ A/B หรือปีก่อน/ปีนี้ตามชนิดคู่
"""
import json
import re
import shutil
import sqlite3
import sys
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

pytest.importorskip("fitz")              # เครื่องมือสร้าง fixture (ไม่ใช่ product path)
import demo_redbook_book_pdf as gen      # noqa: E402

from redbook.app import create_app       # noqa: E402
from redbook.core.hashing import sha256_file  # noqa: E402
from redbook.evidence import pdftext     # noqa: E402
from redbook.pdfbook import reader, scope  # noqa: E402
from redbook.pdfbook import compare as cmp  # noqa: E402
from redbook.services import pdfpair, pdfshelf, trial  # noqa: E402
from redbook.storage import audit, pdfpair_repo, trial_repo  # noqa: E402
from redbook.storage.db import connect   # noqa: E402
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD  # noqa: E402

pytestmark = pytest.mark.skipif(pdftext.product_backend() is None, reason="ไม่มี pdfplumber + pypdfium2")
AG = gen.AGENCY_1
ALL_FULL = {f"part_{c}": "full" for c, _l in trial.PARTS}


def _make_shelf(d, scenario, keys, books):
    srcs = gen.build(d / "src", scenario)
    (d / "volumes").mkdir()
    vols, reg = [], {"volumes": {}}
    for (key, fy, stage), src in zip(keys, srcs):
        shutil.copy(src, d / "volumes" / f"{key}.pdf")
        vols.append({"key": key, "page": "", "url": "https://bb.go.th/x", "fiscal_year": fy, "stage": stage,
                     "label": f"สาธิต {stage}"})
        reg["volumes"][key] = {"sha256": sha256_file(d / "volumes" / f"{key}.pdf"), "retrieved_at": "2026-10-23"}
    (d / "manifest.json").write_text(json.dumps({"volumes": vols}, ensure_ascii=False), encoding="utf-8")
    (d / "register.json").write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    (d / "trial_books.json").write_text(json.dumps({"books": books}, ensure_ascii=False), encoding="utf-8")
    return d


@pytest.fixture(scope="module")
def shelf(tmp_path_factory):
    """ชั้นเล่มปีเดียวกัน (ร่าง ↔ พ.ร.บ. 2570) — ใช้ร่วมกับ test_api_* ของหลังบ้าน/หน้าบ้าน"""
    return _make_shelf(tmp_path_factory.mktemp("trialshelf"), "draft_act",
                       (("S_2570_draft", 2570, "draft"), ("S_2570_act", 2570, "act")), [
        {"id": "t1", "title": "เล่ม 1", "agency": AG, "pair": "ร่าง ↔ พ.ร.บ.", "current": "S_2570_act",
         "previous": "S_2570_draft"},
        {"id": "gone", "title": "เล่ม 2", "agency": AG, "pair": "", "current": "NOPE", "previous": "S_2570_draft"},
        {"id": "held", "title": "เล่ม 3", "agency": "สถาบันวิจัยระบบสาธารณสุข", "pair": "", "current": "S_2570_act",
         "previous": "S_2570_draft"}])


@pytest.fixture(scope="module")
def xshelf(tmp_path_factory):
    """ชั้นเล่มข้ามปี (พ.ร.บ. 2569 ↔ 2570) — แยกชั้นจาก ``shelf`` ไม่ให้รายการเล่มของเทสต์อื่นเปลี่ยน"""
    return _make_shelf(tmp_path_factory.mktemp("trialshelf_x"), "cross_year",
                       (("S_2569_actX", 2569, "act"), ("S_2570_actX", 2570, "act")), [
        {"id": "t2", "title": "เล่มข้ามปี", "agency": AG, "pair": "พ.ร.บ. 2569 ↔ 2570", "current": "S_2570_actX",
         "previous": "S_2569_actX"}])


@pytest.fixture(autouse=True)
def _env(shelf, monkeypatch):
    monkeypatch.setenv(pdfshelf.SHELF_ENV, str(shelf))
    monkeypatch.delenv(trial.TRIAL_ENV, raising=False)

    # เล่มสังเคราะห์ไม่มีเลขหน้าในสารบัญ — ใช้ช่วงหน้าที่หาจากเนื้อหา (เฉพาะในเทสต์)
    def toc_scope(v, agency):
        sc = scope.find(reader.page_texts(v.path), agency)
        return sc, list(sc.pages)
    monkeypatch.setattr(pdfshelf, "toc_scope", toc_scope)


@pytest.fixture()
def cross(_env, xshelf, monkeypatch):
    """ใช้ชั้นเล่มข้ามปีในเทสต์นี้"""
    monkeypatch.setenv(pdfshelf.SHELF_ENV, str(xshelf))


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        c.get("/trial")
        yield c


def _token(client):
    return client.cookies.get(CSRF_COOKIE)


CONSENT = {"c1": "1", "c2": "1", "c3": "1"}
#: สถานะตำแหน่ง (ฉบับ 0.3 — ขั้นแยกหลังผลจับคู่) แทน "หลักฐานชี้ตำแหน่ง" ของฉบับ 0.2
LOC = {"location": "all_sides", "relevant_sides": ["A", "B"]}
LOC_SOME = {"location": "some_sides", "relevant_sides": ["A", "B"]}


def start(book, reviewer="", path="r1", again=False):
    """เริ่มรอบ + ให้ความยินยอม (ขั้นแรกของรอบตามรีวิวโบ 6414605109 ข้อ 4)"""
    sid = trial.start(book, reviewer, again=again, path=path)
    s = trial.session(sid)
    if not s.consented and s.active and not s.legacy:
        trial.give_consent(sid, CONSENT)
    return sid


def web_start(client, tok, **data):
    sid = client.post("/trial/start", data={CSRF_FIELD: tok, **data}, follow_redirects=False).headers["location"]
    sid = sid.split("/trial/s/")[1].split("/")[0].split("?")[0]
    assert client.post(f"/trial/s/{sid}/consent", data={CSRF_FIELD: tok, **CONSENT},
                       follow_redirects=False).status_code == 303
    return sid


def decl(path="r1", **over):
    """ใบประกาศที่กรอกครบ (ค่าตั้งต้นของเทสต์) — ``over`` แทนค่าบางช่อง"""
    d = {"confirm": "1", "made_on": "2026-10-20", "made": "before", "seen": "never", **ALL_FULL}
    if path == "r1":
        d.update({"source": "routine", "t_ก_total": "2", "t_ก_root": "1", "t_ก_red": "1",
                  "t_ช_total": "1", "t_ช_root": "1", "t_ช_red": "0"})
    else:
        d.update({"t_ก_covered": "1"})
    d.update(over)
    return d


def xdecl(path="r1", **over):
    """ใบประกาศของคู่ข้ามปี — ตัดหัวข้อ ก ของค่าตั้งต้นออก (คู่ข้ามปีใช้ ค ช ซ จ เท่านั้น)"""
    return {k: v for k, v in decl(path, **over).items() if not k.startswith("t_ก_")}


def _runs():
    return len(pdfpair_repo.list_runs(limit=1000))


def _fill(sid, m, topic="ก", part="๗", cause="t", level=None, searched=None, xtype=None):
    trial.update_mark(sid, m["id"], topic=topic, part=part, cause=cause, level=level, searched=searched, xtype=xtype)


def _mark_on(sid, f, side="cur", pen="red", **fields):
    """วางจุดกลางกรอบของข้อสังเกต (จำลองผู้ตรวจที่วงตรงจุด) แล้วกรอกรายละเอียดครบ"""
    s = trial.session(sid)
    sd = f.b if side == "cur" else f.a
    w, h = reader.page_size(trial._side_path(s, side), sd.page)
    x0, y0, x1, y1 = sd.bbox
    m = trial.add_mark(sid, side, sd.page, ((x0 + x1) / 2) / w, ((y0 + y1) / 2) / h, pen)
    _fill(sid, m, **fields)
    return m


_probe_cache: dict = {}


def _probe(book):
    """ผลระบบของเล่มจากรอบที่ล็อกแล้วรอบหนึ่ง — ใช้หาตำแหน่งข้อสังเกตในเทสต์ (ผู้ตรวจจริงไม่เห็นก่อนล็อก)"""
    if book not in _probe_cache:
        sid = start(book, "PROBE", path="r2", again=True)
        trial.lock(sid, xdecl("r2", t_ค_covered="1"))                 # ค ใช้ได้ทั้งสองชนิดคู่
        _probe_cache[book] = (sid, pdfpair.view(trial.session(sid).rec["run_id"]))
    return _probe_cache[book]


def _audit_actions(object_id=None, limit=500):
    return [e["action"] for e in audit.entries(limit=limit, object_id=object_id)]


# ── เล่ม · ชนิดคู่ ───────────────────────────────────────────────────────────────
def test_books_from_config_skip_missing_and_protected(xshelf, monkeypatch):
    assert [(b.id, b.pair_kind) for b in trial.books()] == [("t1", "same_year")]
    monkeypatch.setenv(pdfshelf.SHELF_ENV, str(xshelf))
    assert [(b.id, b.pair_kind) for b in trial.books()] == [("t2", "cross_year")]   # ชนิดคู่จากปีงบของสองเล่ม
    assert trial.side_labels({"pair_kind": "same_year"}) == {"prev": "ฉบับ A", "cur": "ฉบับ B"}
    assert trial.side_labels({"pair_kind": "cross_year"}) == {"prev": "ฉบับปีก่อน", "cur": "ฉบับปีนี้"}


# ── ล็อก = ใบประกาศก่อนเห็นผล ─────────────────────────────────────────────────────
def test_r1_lock_is_a_declaration_not_every_page():
    sid = start("t1", "R1", path="r1", again=True)
    s = trial.session(sid)
    assert s.path == "r1" and s.rec["run_id"] == "" and not s.locked and s.protocol == trial.PROTOCOL_VERSION
    runs = _runs()
    with pytest.raises(trial.TrialError, match="ส่งใบประกาศก่อน"):
        trial.result(sid)                                       # ยังไม่ล็อก = ยังไม่มีผลระบบให้ดู
    with pytest.raises(trial.TrialError, match="ติ๊กยืนยัน"):
        trial.lock(sid, {})
    bad = decl()
    del bad["part_๓"]
    with pytest.raises(trial.TrialError, match="ส่วนที่ ๓"):
        trial.lock(sid, bad)
    with pytest.raises(trial.TrialError, match="ต้นเหตุหรือระดับแดงมากกว่า"):
        trial.lock(sid, decl(t_ก_root="5"))
    with pytest.raises(trial.TrialError, match="เว้นว่างทั้งแถว"):
        trial.lock(sid, decl(t_ข_root="1"))
    with pytest.raises(trial.TrialError, match="อย่างน้อย 1 หัวข้อ"):
        trial.lock(sid, decl(t_ก_total="", t_ก_root="", t_ก_red="", t_ช_total="", t_ช_root="", t_ช_red=""))
    with pytest.raises(trial.TrialError, match="อย่างน้อย 1 ส่วน"):
        trial.lock(sid, decl(**{f"part_{c}": "none" for c, _l in trial.PARTS}))
    with pytest.raises(trial.TrialError, match="ทาง ร1 ไม่ใช้การวงจุด"):
        trial.add_mark(sid, "cur", s.pages("cur")[0], .5, .5, "red")
    assert _runs() == runs and trial.session(sid).rec["run_id"] == ""      # ตรวจไม่ผ่าน = ไม่มีรอบเทียบ
    assert not trial.session(sid).done                                      # ไม่ได้กด "ตรวจหน้านี้แล้ว" เลย
    rid = trial.lock(sid, decl(t_ซ_total="0"))
    s = trial.session(sid)
    assert rid and s.locked and s.rec["run_id"] == rid and _runs() == runs + 1
    assert [(m["topic"], m["seq"], m["origin"]) for m in s.rows] == [("ก", 1, "row"), ("ก", 2, "row"), ("ช", 1, "row")]
    d = trial_repo.declaration(sid)
    assert d["body"]["topics"] == {"ก": {"total": 2, "root": 1, "red": 1}, "ช": {"total": 1, "root": 1, "red": 0},
                                   "ซ": {"total": 0, "root": 0, "red": 0}}
    assert d["body"]["parts"] == {c: "full" for c, _l in trial.PARTS} and len(d["hash"]) == 64
    assert s.rec["released_at"] > s.rec["locked_at"]                         # ปล่อยผลหลังรับใบประกาศเสมอ
    with pytest.raises(trial.TrialError, match="ส่งใบประกาศแล้ว"):
        trial.lock(sid, decl())
    acts = _audit_actions(sid)
    assert {"trial_started", "trial_locked", "trial_run_attached"} <= set(acts)


def test_r2_marks_need_protocol_fields_before_lock_but_not_every_page():
    sid = start("t1", "R2", path="r2", again=True)
    s = trial.session(sid)
    p0 = s.pages("cur")[0]
    red = trial.add_mark(sid, "cur", p0, .3, .3, "red")
    pin = trial.add_mark(sid, "prev", s.pages("prev")[0], .4, .4, "pin")   # ของที่หาย วางบนฉบับที่พบ (ฉบับ A) ได้
    assert red["level"] == "red" and pin["level"] == "" and pin["found_in"] == "prev"
    with pytest.raises(trial.TrialError, match="ไม่ครบ 2 จุด"):
        trial.lock(sid, decl("r2"))
    _fill(sid, red, topic="ช", part="๓", cause="t")
    _fill(sid, pin, topic="ค", part="๗", cause="t")
    with pytest.raises(trial.TrialError, match="ไม่ครบ 1 จุด.*ระดับ.*ขอบเขตที่ค้น"):
        trial.lock(sid, decl("r2"))
    trial.update_mark(sid, pin["id"], level="brown", searched="ส่วน ๗ หน้า 8–12")
    with pytest.raises(trial.TrialError):
        trial.update_mark(sid, red["id"], part="๙")
    trial.lock(sid, decl("r2"))
    body = trial_repo.declaration(sid)["body"]
    assert body["source"] == "web" and body["marks"] == 2 and len(body["marks_hash"]) == 64
    assert body["topics"] == {"ก": {"total": 0, "root": 0, "red": 0}, "ค": {"total": 1, "root": 1, "red": 0},
                              "ช": {"total": 1, "root": 1, "red": 1}}
    assert not trial.session(sid).done                                      # ไม่บังคับกดครบทุกหน้า
    with pytest.raises(trial.TrialError, match="ส่งใบประกาศแล้ว"):
        trial.update_mark(sid, red["id"], topic="ก")
    with pytest.raises(trial.TrialError, match="ส่งใบประกาศแล้ว"):
        trial.add_mark(sid, "cur", p0, .5, .5, "red")


def test_lock_rechecks_the_marks_inside_the_transaction(monkeypatch):
    sid = start("t1", "U2", path="r2", again=True)
    m = trial.add_mark(sid, "cur", trial.session(sid).pages("cur")[0], .2, .2, "red")
    _fill(sid, m)
    real = trial_repo.lock

    def edit_while_locking(sid_, counts, **kw):         # จำลองแก้จุดจากอีกแท็บ หลังชั้นบริการตรวจครบแล้ว
        trial_repo.update_mark(sid_, m["id"], note="แก้จากอีกแท็บ")
        return real(sid_, counts, **kw)
    monkeypatch.setattr(trial_repo, "lock", edit_while_locking)
    runs = _runs()
    with pytest.raises(trial.TrialError, match="จุดที่วงเปลี่ยนระหว่างส่ง"):
        trial.lock(sid, decl("r2"))
    s = trial.session(sid)
    assert not s.locked and s.rec["run_id"] == "" and trial_repo.declaration(sid) is None and _runs() == runs


# ── ข้อมูลประกอบจับคู่ได้ (โบ #43 6361719346) ─────────────────────────────────────────
def test_cross_year_counts_structural_only(cross):
    """คู่ข้ามปี = เฉพาะความต่างเชิงโครงสร้าง (วิธีวัดผล ข้อ 2.9 ฉบับ 0.2.1–0.2.2 · กิ๊ฟอนุมัติ 27 ต.ค.)"""
    _psid, v = _probe("t2")
    fs = v.result.findings
    added = next(f for f in fs if f.topic == "struct" and f.kind == "only_b" and f.b.page and f.b.bbox)
    assert added.info                                          # ตัวเทียบติดข้อมูลประกอบ แต่ 0.2.1 นับเป็นเชิงโครงสร้าง
    yearly = next(f for f in fs if f.kind == "year_change" and f.b.page and f.b.bbox)
    sid = start("t2", "X1", path="r2", again=True)
    s = trial.session(sid)
    assert s.labels == {"prev": "ฉบับปีก่อน", "cur": "ฉบับปีนี้"}
    m = _mark_on(sid, added, topic="ค", part="๗", cause="t", xtype="add")
    with pytest.raises(trial.TrialError, match="เชิงโครงสร้าง"):
        trial.update_mark(sid, m["id"], topic="ก")                # หัวข้อ ก ไม่ใช้กับคู่ข้ามปี
    with pytest.raises(trial.TrialError, match="หัวข้อ ก"):
        trial.lock(sid, decl("r2", t_ก_covered="1"))
    trial.lock(sid, xdecl("r2", t_ค_covered="1"))
    r = trial.result(sid)
    assert r.level[added.id] == "must" and r.level[yearly.id] == "descriptive"
    assert r.proposals[m["id"]] == added.id
    assert yearly.id not in {c.id for c in r.candidates(r.issue_by_id[m["id"]])}   # ไม่ใช่เชิงโครงสร้าง = จับคู่ไม่ได้
    with pytest.raises(trial.TrialError, match="ไม่ใช่ข้อสังเกตต้องตรวจ"):
        trial.decide_finding(sid, yearly.id, "s3", s3_reason="other", basis="enough")
    with pytest.raises(trial.TrialError):
        trial.decide_issue(sid, m["id"], "exact", [yearly.id], **LOC, basis="enough")
    trial.decide_issue(sid, m["id"], "exact", [added.id], **LOC, basis="enough")
    mt = trial.result(sid).metrics
    structural = [f for f in fs if f.kind != "unread" and trial.is_structural(f)]
    descriptive = [f for f in fs if f.kind != "unread" and not trial.is_structural(f)]
    assert mt["A3"]["must_total"] == len(structural) >= 3 and mt["A3"]["matched"] == 1   # ค เพิ่ม · ช เพิ่ม · ซ วิสัยทัศน์
    assert mt["findings"]["descriptive"] == len(descriptive) and mt["findings"]["info"] == 0
    sc = mt["scope"]
    assert sc["pair_kind"] == "cross_year" and sc["label"] == "เฉพาะความต่างเชิงโครงสร้าง" and sc["rule"] == trial.XYEAR_RULE
    assert sum(sc["descriptive_by_kind"].values()) == len(descriptive) and sc["descriptive_by_kind"]["year_change"] >= 1
    assert set(mt["A1"]["by_topic"]) <= set(trial.XYEAR_TOPICS)
    assert mt["A1"]["exact"] == 1 and mt["A1"]["matched_level"] == {"must": 1, "info": 0}
    d = trial.summary(sid)
    assert d["metrics"]["scope"]["rule"] == trial.XYEAR_RULE


def test_cross_year_r1_declaration_only_structural_topics(cross):
    sid = start("t2", "X2", path="r1", again=True)
    with pytest.raises(trial.TrialError, match="หัวข้อ ก"):
        trial.lock(sid, decl())                                          # ค่าตั้งต้นของเทสต์ใช้ ก + ช
    trial.lock(sid, xdecl())
    assert {m["topic"] for m in trial.result(sid).issues} == {"ช"}


def _F(topic, kind, subject="x", column=""):
    return cmp.Finding("id", topic, kind, subject, column=column)


def test_structural_rule_locked_to_pdfbook_labels():
    """กติกา XYEAR_RULE ผูกกับป้าย/ชนิดของตัวเทียบรุ่นนี้ — ตัวเทียบเปลี่ยน = เทสต์นี้ต้องล้ม แล้วประกาศกติการุ่นใหม่"""
    import inspect
    from redbook.pdfbook import PDFBOOK_VERSION
    from redbook.pdfbook import profile as prof
    assert PDFBOOK_VERSION in trial.XYEAR_ENGINES and trial.XYEAR_RULE.endswith(trial.XYEAR_ENGINE)
    assert trial.XYEAR_ENGINES == ("pdfbook-0.5.0", "pdfbook-0.5.1", "pdfbook-0.5.2", "pdfbook-0.5.3")   # เพิ่มรุ่น = ตรวจกติกาก่อน
    src = inspect.getsource(cmp)
    for lit in ('"ชื่อหน่วยงาน (ต้นช่วง)"', 'column="หน่วยนับ"', 'column="รายการผูกพัน"', 'column="ชื่อตัวชี้วัด"'):
        assert lit in src, lit
    assert (prof.SECTION_LABELS[prof.SEC_VISION], prof.SECTION_LABELS[prof.SEC_MISSION]) == ("วิสัยทัศน์", "พันธกิจ")
    yes = [_F("struct", k) for k in ("only_a", "only_b", "renamed_candidate", "moved", "label_variant",
                                       "identity_ambiguous")]
    yes += [_F("ind", k) for k in ("only_a", "only_b", "renamed_candidate", "label_variant", "identity_ambiguous")]
    yes += [_F("ind", "changed", column="หน่วยนับ")]
    yes += [_F("text", k, subject=sub) for k in ("only_a", "only_b", "changed")
            for sub in ("วิสัยทัศน์", "พันธกิจ · กรม")]
    yes += [_F("format", "changed", subject="ชื่อหน่วยงาน (ต้นช่วง)")]
    yes += [_F("commit", k, column="รายการผูกพัน") for k in ("only_a", "only_b")]
    no = [_F("ind", "changed", column="เป้าหมายปี 2569"), _F("ind", "same_year_mismatch"),
          _F("text", "changed", subject="วัตถุประสงค์ · โครงการ"),
          _F("text", "only_b", subject="ผลสัมฤทธิ์หรือประโยชน์ที่คาดว่าจะได้รับ"),
          _F("format", "changed", subject="เลขนำหน้า"), _F("commit", "changed", column="รายการผูกพัน"),
          _F("commit", "only_b", column="2570"), _F("commit", "same_year_mismatch"), _F("commit", "sum_mismatch")]
    # รุ่น 2: หมวดย่อยสถานที่/ระยะเวลาดำเนินการของโครงการ = เชิงพรรณนา (ตัวเทียบออกเป็นคีย์ ไม่มีป้ายไทย)
    assert trial.XYEAR_RULE.startswith("xyear-structural-2 @ ")
    assert {n for n, _c in prof.SUB_TEXT_CUES} == {"objective", "location", "period"}
    assert [cmp._TEXT_SECTION_LABEL.get(k, k) for k in ("objective", "location", "period")] ==         ["วัตถุประสงค์", "location", "period"]
    sub = [_F("text", k, subject=f"{sec} · โครงการ") for k in ("only_a", "only_b", "changed")
           for sec in ("location", "period")]
    assert {trial.classify(f) for f in sub} == {("out", "")}
    no += sub
    for sec in ("สถานที่ดำเนินการ", "ระยะเวลา", "locations", "Location"):                # negative control: ชื่ออื่นยังไม่รู้จัก
        assert trial.classify(_F("text", "changed", subject=f"{sec} · โครงการ"))[0] == "unknown", sec
    # Bo #43 6489882675: ข้อความย่อยไม่กลบกฎโครงสร้างของตัวโครงการ (โครงการเพิ่ม/หาย/เปลี่ยนชื่อ/ย้าย/กำกวม มาพร้อมกัน)
    mixed = [_F("struct", k, subject="โครงการ ก") for k in ("only_a", "only_b", "renamed_candidate", "moved",
                                                              "identity_ambiguous")]
    mixed += [_F("text", k, subject=f"{sec} · โครงการ ก") for k in ("only_a", "only_b", "changed")
              for sec in ("location", "period")]
    got = {(f.topic, f.kind, f.subject.split(" · ")[0]): trial.level_and_reason(f, "cross_year")[0] for f in mixed}
    assert {k: v for k, v in got.items() if k[0] == "struct"} == {k: "must" for k in got if k[0] == "struct"}
    assert {v for k, v in got.items() if k[0] == "text"} == {"descriptive"}
    assert trial.classify(_F("text", "changed", subject="วัตถุประสงค์ · โครงการ ก")) == ("out", "")   # ตัวควบคุม objective
    for sec in ("วิสัยทัศน์", "พันธกิจ"):
        assert trial.level_and_reason(_F("text", "changed", subject=sec), "cross_year")[0] == "must"
    # คู่ปีเดียวกันไม่ถูกกรองตามกฎข้ามปี
    for f in sub + [_F("text", "changed", subject="สถานที่ดำเนินการ · โครงการ")]:
        assert trial.finding_level(f, "same_year") == "must"
    # หัวข้อที่แสดง (ซ) ไม่ได้ใช้ตัดสินว่าเป็นเชิงโครงสร้าง — หัวข้อข้อความของตัวเทียบครอบคลุมหลายหมวดที่ไม่นับ
    assert trial.system_topic(sub[0], "cross_year") == trial.system_topic(_F("text", "changed", subject="วิสัยทัศน์"),
                                                                          "cross_year")
    assert not trial.is_structural(sub[0])
    no += [_F(t, k) for t in ("total", "econ", "items", "mtef", "consist") for k in ("only_a", "only_b", "changed",
                                                                                    "year_change", "sum_mismatch")]
    assert [f for f in yes if not trial.is_structural(f)] == []
    assert [(f.topic, f.kind, f.subject, f.column) for f in no if trial.is_structural(f)] == []
    assert trial.system_topic(_F("format", "changed", subject="ชื่อหน่วยงาน (ต้นช่วง)"), "cross_year") == "ซ"
    assert trial.system_topic(_F("format", "changed", subject="ชื่อหน่วยงาน (ต้นช่วง)"), "same_year") == "ฌ"
    assert [c for c, _l in trial.topic_codes("cross_year")] == ["ค", "จ", "ช", "ซ"]
    assert len(trial.topic_codes("same_year")) == 10
    assert trial.finding_level(_F("struct", "only_b"), "same_year") == "must"
    assert trial.finding_level(_F("total", "changed"), "cross_year") == "descriptive"
    # ปัญหาการอ่าน 3 ชนิด (ไม่พบหัวข้อ ≠ อ่านไม่ได้)
    page_only = cmp.Finding("id", "cover", "unread", "หน้า 3 ไม่มีชั้นข้อความ", a=cmp.Side(page=3))
    row = cmp.Finding("id", "cover", "unread", "x", b=cmp.Side(page=3, bbox=(1, 2, 3, 4)))
    assert [trial.read_problem(f) for f in (page_only, row, _F("cover", "section_missing"), _F("struct", "only_a"))] \
        == ["no_text", "unparsed", "not_found", ""]
    for lit in ('f"หน้า {p} ไม่มีชั้นข้อความ', 'K_SECTION_MISSING, P.SECTION_LABELS[sec], within=side'):
        assert lit in src, lit


def _shelf_without(tmp_path_factory, section: str, mode: str = "drop"):
    """ชั้นเล่มข้ามปีที่ฉบับปีนี้ (2570) ไม่มีหมวด ``section`` — ห่อตัวสร้างเล่มสังเคราะห์เฉพาะตอนสร้าง
    (ไม่แก้สคริปต์สร้างเล่ม) · ``drop`` = ตัดทั้งหัวข้อและข้อความใต้หัวข้อ (หายจริง) ·
    ``garble`` = ข้อความยังอยู่ แต่หัวข้อพิมพ์ไม่ครบจนระบบจำหัวข้อไม่ได้ (มีอยู่แต่สกัดตก)"""
    heads = {"vision": ("1. วิสัยทัศน์",), "mission": ("2. พันธกิจ",)}[section]
    garbled = {"vision": "1. วิสัยทัศ", "mission": "2. พันธกิ"}[section]
    state = {"drop": False, "skip": False}
    orig_build, orig_line, orig_para = gen.build_book, gen.Book.line, gen.Book.para

    def build_book(out, *, fy, **kw):
        state["drop"] = fy == 2570
        try:
            return orig_build(out, fy=fy, **kw)
        finally:
            state["drop"] = False

    def line(self, s, *a, **kw):
        hit = state["drop"] and s in heads
        if hit and mode == "garble":
            return orig_line(self, garbled, *a, **kw)
        state["skip"] = hit
        if not state["skip"]:
            return orig_line(self, s, *a, **kw)

    def para(self, s, *a, **kw):
        if not state["skip"]:
            return orig_para(self, s, *a, **kw)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(gen, "build_book", build_book)
        mp.setattr(gen.Book, "line", line)
        mp.setattr(gen.Book, "para", para)
        bid = {"vision": "xv", "mission": "xm"}[section] + ("g" if mode == "garble" else "")
        return _make_shelf(tmp_path_factory.mktemp(f"trialshelf_{bid}"), "cross_year",
                           ((f"S_2569_{bid}", 2569, "act"), (f"S_2570_{bid}", 2570, "act")), [
            {"id": bid, "title": f"เล่มข้ามปี ไม่มี{section}", "agency": AG, "pair": "พ.ร.บ. 2569 ↔ 2570",
             "current": f"S_2570_{bid}", "previous": f"S_2569_{bid}"}])


@pytest.mark.parametrize("section,bid,label", [("vision", "xv", "วิสัยทัศน์"), ("mission", "xm", "พันธกิจ")])
def test_cross_year_whole_section_missing_still_matchable(section, bid, label, tmp_path_factory, _env, monkeypatch):
    """คู่ข้ามปีที่ฉบับหนึ่งไม่มีหมวดวิสัยทัศน์/พันธกิจทั้งหมวด (คำกิ๊ฟ 28 ต.ค. — ล็อกพฤติกรรม ไม่แตะกติกา):
    section_missing (cover) = เชิงพรรณนา · ข้อความแต่ละข้อของฉบับที่มีหมวดนั้น = only_a เชิงโครงสร้าง ระดับต้องตรวจ ·
    ประเด็น "หายทั้งส่วน" ในหัวข้อ ซ จับคู่กับข้อเหล่านั้นได้และนับเป็นพบ"""
    monkeypatch.setenv(pdfshelf.SHELF_ENV, str(_shelf_without(tmp_path_factory, section)))
    monkeypatch.setattr(pdfshelf, "toc_scope", _toc_scope_by_head)
    _probe_cache.pop(bid, None)
    _check_section_missing_matchable(bid, label)


def _toc_scope_by_head(v, agency):
    """ช่วงหน้าในเทสต์หาจากหน้าที่มี "วิสัยทัศน์" — ฉบับที่ไม่มีหรือสกัดหัวข้อนี้ไม่ได้ใช้หัวหน่วยงานแทน
    (ระบบจริงใช้เลขหน้าในสารบัญ)"""
    texts = reader.page_texts(v.path)
    try:
        sc = scope.find(texts, agency)
    except scope.ScopeError:
        heads = [i + 1 for i, t in enumerate(texts) if "งบประมาณรายจ่าย" in t and "สารบัญ" not in t
                 and any(scope.squash(n) in scope.squash(t) for n in (agency, gen.second_agency(2570)["name"]))]
        first = next(p for p in heads if scope.squash(agency) in scope.squash(texts[p - 1]))
        later = [p for p in heads if p > first]
        sc = scope.find(texts, agency, first, (later[0] - 1) if later else len(texts))
    return sc, list(sc.pages)


def _check_section_missing_matchable(bid, label, judgment="match"):
    """ทั้งสองกรณีระบบออกข้อสังเกตรูปเดียวกัน (แยกเองไม่ได้) แต่ **คำตัดสินที่คาดต่างกัน** (รีวิวโบ 6460469359):
    ``match`` = หายจริง → ประเด็น "หายทั้งส่วน" จับคู่ได้ นับเป็นพบ · ``false_alarm`` = มีอยู่แต่สกัดตก → ไม่มีประเด็น
    (ไม่ได้ต่างจริง) ข้อ only_a เป็นข้ออ้างที่ไม่ถูก ผู้ตรวจดูภาพแล้วจัด ส3 อ่านผิด — ห้ามนับพบเพียงเพราะผูกหลายข้อได้"""
    _psid, v = _probe(bid)
    fs = v.result.findings
    miss = [f for f in fs if f.kind == "section_missing" and f.subject == label]
    assert len(miss) == 1 and miss[0].topic == "cover" and miss[0].within == "B"
    assert not trial.is_structural(miss[0]) and trial.finding_level(miss[0], "cross_year") == "descriptive"
    assert trial.read_problem(miss[0]) == "not_found"                         # ไม่พบหัวข้อ ≠ อ่านไม่ได้
    items = [f for f in fs if f.topic == "text" and f.subject.split(" · ")[0] == label]
    assert items and {f.kind for f in items} == {"only_a"}                   # ทุกข้อของหมวดมีเฉพาะฉบับปีก่อน
    assert all(trial.is_structural(f) and trial.finding_level(f, "cross_year") == "must" for f in items)
    first = next(f for f in items if f.a.page and f.a.bbox)
    sid = start(bid, "W", path="r2", again=True)
    if judgment == "false_alarm":
        trial.lock(sid, xdecl("r2", t_ซ_covered="1"))                         # ตรวจหัวข้อ ซ แล้ว ไม่พบความต่าง
        r = trial.result(sid)
        assert {f.id for f in items} <= {f.id for f in r.unmatched_must}
        for f in items:
            trial.decide_finding(sid, f.id, "s3", s3_reason="misread", basis="opened")
        mt = trial.result(sid).metrics
        assert mt["A1"]["N0"] == 0 and mt["A1"]["exact"] == 0                # ไม่มีประเด็น = ไม่มีพบ
        assert mt["A3"]["s3"] == len(items) and mt["A3"]["matched"] == 0
        assert mt["A3"]["s3_reasons"]["misread"] == len(items)
        return v
    m = _mark_on(sid, first, side="prev", topic="ซ", part="๒", cause="t", xtype="remove")
    trial.lock(sid, xdecl("r2", t_ซ_covered="1"))
    r = trial.result(sid)
    assert r.level[miss[0].id] == "descriptive" and miss[0].id not in r.matchable_ids
    assert r.proposals[m["id"]] == first.id
    assert {f.id for f in items} <= {c.id for c in r.candidates(r.issue_by_id[m["id"]])}
    trial.decide_issue(sid, m["id"], "exact", [f.id for f in items], **LOC, basis="enough")
    mt = trial.result(sid).metrics
    assert (mt["A1"]["exact"], mt["A1"]["missed"], mt["A1"]["N"]) == (1, 0, 1)        # พบ · ประเด็นนับครั้งเดียว
    assert mt["A1"]["by_topic"]["ซ"]["exact"] == 1 and mt["A3"]["matched"] == len(items)
    assert mt["scope"]["descriptive_by_kind"].get("section_missing", 0) >= 1
    assert mt["A4"]["read_problems"]["not_found"] >= 1
    return v


@pytest.mark.parametrize("section,bid,label", [("vision", "xvg", "วิสัยทัศน์"), ("mission", "xmg", "พันธกิจ")])
def test_cross_year_section_present_but_heading_not_extracted(section, bid, label, tmp_path_factory, _env,
                                                               monkeypatch):
    """หมวดมีอยู่ในฉบับปีนี้ แต่หัวข้อพิมพ์ไม่ครบจนระบบจำไม่ได้ (สกัดตก) — ระบบแยกจาก "หายจริง" ไม่ได้:
    ออก "ไม่พบหัวข้อ" + only_a เหมือนกัน · ผู้ตรวจดูภาพแล้วเห็นว่าไม่ได้หาย → ข้อ only_a = ส3 อ่านผิด (ไม่ใช่พบ)"""
    monkeypatch.setenv(pdfshelf.SHELF_ENV, str(_shelf_without(tmp_path_factory, section, "garble")))
    monkeypatch.setattr(pdfshelf, "toc_scope", _toc_scope_by_head)
    _probe_cache.pop(bid, None)
    v = _check_section_missing_matchable(bid, label, "false_alarm")
    psid = _probe(bid)[0]
    texts_b = " ".join(reader.page_texts(trial._side_path(trial.session(psid), "cur")))
    ag = gen.base_agency(2570)
    body = ag["vision"] if section == "vision" else ag["missions"][0]
    assert scope.squash(body[:20]) in scope.squash(texts_b)                    # ข้อความยังอยู่ในเล่ม — สกัดตก ไม่ใช่หาย


def test_unknown_rule_is_review_not_silently_descriptive():
    """รีวิวโบ 6459664149 ข้อ 1: กติกาไม่รู้จัก ≠ ไม่ใช่เชิงโครงสร้าง — ต้องทบทวน · ตัวควบคุมตัวเลขที่รู้จัก = เชิงพรรณนา"""
    unknown = [_F("struct", "brand_new_kind"), _F("brand_new_topic", "changed"),
               _F("text", "changed", subject="หมวดใหม่ที่ไม่เคยมี"), _F("ind", "changed", column="คอลัมน์ใหม่"),
               _F("commit", "only_b", column="")]
    for f in unknown:
        assert trial.classify(f)[0] == "unknown", (f.topic, f.kind)
        lv, why = trial.level_and_reason(f, "cross_year")
        assert lv == "review" and why
        assert trial.finding_level(f, "same_year") in ("must", "info")       # คู่ปีเดียวกันไม่ใช้กติกานี้
    known_numeric = [_F("ind", "changed", column="เป้าหมายปี 2569"), _F("commit", "changed", column="รายการผูกพัน"),
                     _F("commit", "only_b", column="2570"), _F("text", "changed", subject="วัตถุประสงค์ · โครงการ"),
                     _F("total", "year_change")]
    assert [trial.finding_level(f, "cross_year") for f in known_numeric] == ["descriptive"] * len(known_numeric)
    # รุ่นตัวเทียบไม่ตรงกติกา = ทบทวนทุกข้อ แม้ข้อเชิงโครงสร้าง
    assert trial.level_and_reason(_F("struct", "only_a"), "cross_year", engine="pdfbook-9.9.9")[0] == "review"
    assert trial.level_and_reason(_F("struct", "only_a"), "cross_year", engine="")[0] == "review"
    assert trial.level_and_reason(_F("struct", "only_a"), "cross_year", xrule=False)[0] == "must"


def test_engine_mismatch_blocks_completion_and_classification_is_stored(cross, monkeypatch):
    """รุ่นตัวเทียบของผลไม่ตรงกติกา → ทุกข้อ "ต้องทบทวน" สรุปครบไม่ได้ · การจัดประเภทบันทึกครั้งเดียวต่อรอบ ไม่เปลี่ยนตามโค้ดภายหลัง"""
    sid = start("t2", "V1", path="r1", again=True)
    verified = trial.XYEAR_ENGINES
    monkeypatch.setattr(trial, "XYEAR_ENGINES", ("pdfbook-9.9.9",))
    trial.lock(sid, xdecl())
    r = trial.result(sid)
    assert r.of_level("review") and not r.of_level("must") and not r.matchable_ids
    assert not r.complete and "xyear_review_needed" in trial.status_of(r.s, r)["flags"]
    sc = r.metrics["scope"]
    assert sc["engine_ok"] is False and sc["classification_stored"] is True
    assert any("ไม่ตรงกติกา" in k for k in sc["review_by_reason"])
    monkeypatch.setattr(trial, "XYEAR_ENGINES", verified)                       # โค้ดเปลี่ยนภายหลัง
    r2 = trial.result(sid)
    assert r2.of_level("review") and r2.level == r.level                      # ใช้การจัดประเภทที่บันทึกไว้
    stored = trial_repo.obs_class(sid)
    f = next(iter(stored.values()))
    assert set(f) >= {"topic", "kind", "info", "level", "reason", "rule", "engine"}   # ข้อมูลเดิมของตัวเทียบอยู่คู่กัน
    assert "trial_obs_classified" in _audit_actions(sid)


def test_rounds_keep_their_own_protocol_version(cross):
    """รอบเดิมคงรุ่นวิธีวัดผลของตัวเอง — รอบ 0.2 (ก่อนกติกาข้ามปี) ไม่ถูกกรองเชิงโครงสร้างย้อนหลัง"""
    sid = start("t2", "P1", path="r2", again=True)
    conn = connect()
    try:
        conn.execute("UPDATE trial_sessions SET protocol = ? WHERE id = ?", ("pdfpair-protocol-0.2 (ร่าง)", sid))
        conn.commit()
    finally:
        conn.close()
    s = trial.session(sid)
    assert s.protocol == "pdfpair-protocol-0.2 (ร่าง)" and not s.xrule_applies and s.xkind == "same_year"
    assert len(trial.topic_codes(s.xkind)) == 10                              # หัวข้อครบตามที่ประกาศตอนนั้น
    _psid, v = _probe("t2")
    yearly = next(f for f in v.result.findings if f.kind == "year_change" and f.b.page and f.b.bbox)
    _mark_on(sid, yearly, topic="ก", part="๔", cause="t")                    # ไม่ต้องมีชนิดประเด็น
    trial.lock(sid, decl("r2"))
    r = trial.result(sid)
    assert r.level[yearly.id] == "info" and r.metrics["scope"]["rule"] == ""
    assert trial.session(start("t2", "P2", path="r2", again=True)).protocol == trial.PROTOCOL_VERSION


def test_cross_year_issue_type_keeps_numeric_issues_out_of_the_denominator(cross):
    """รีวิวโบ 6459664149 ข้อ 2: ตัวชี้วัดชื่อเดิมแต่ค่าเป้าหมายเปลี่ยน · รายการผูกพันเดิมแต่ช่องเงินหาย = ไม่ใช่เชิงโครงสร้าง
    (ไม่เข้า N₀) · เพิ่ม/หายทั้งรายการ = เข้า · ระบุชนิดหลังเห็นผล = ตัดออกจากตัวหารไม่ได้"""
    sid = start("t2", "X3", path="r1", again=True)
    trial.lock(sid, xdecl(**{"t_ช_total": "2", "t_ช_root": "1", "t_ช_red": "0",
                            "t_จ_total": "2", "t_จ_root": "1", "t_จ_red": "0", "t_ค_total": "1", "t_ค_root": "1",
                            "t_ค_red": "1"}))
    rows = trial.result(sid).issues
    by = {}
    for m in rows:
        by.setdefault(m["topic"], []).append(m)
    ind_target, ind_new = by["ช"]
    commit_money, commit_gone = by["จ"]
    (plan_added,) = by["ค"]
    with pytest.raises(trial.TrialError, match="ใช้กับหัวข้อ ช ไม่ได้"):
        trial.update_row(sid, ind_target["id"], xtype="move")
    common = dict(part="๗", cause="t", level="brown", row_source="transcribed")
    for i, (m, xt) in enumerate(((ind_target, "numeric"), (ind_new, "add"), (commit_money, "numeric"),
                                 (commit_gone, "remove"), (plan_added, "add"))):
        trial.update_row(sid, m["id"], ref=str(i + 1), xtype=xt, **common)
    r = trial.result(sid)
    assert not r.in_scope(r.issue_by_id[ind_target["id"]]) and not r.in_scope(r.issue_by_id[commit_money["id"]])
    assert r.in_scope(r.issue_by_id[ind_new["id"]]) and r.in_scope(r.issue_by_id[plan_added["id"]])
    fid = r.matchable[0].id
    for m in (ind_new, commit_gone, plan_added):
        trial.decide_issue(sid, m["id"], "missed", reason="p3", basis="opened")
    for m in (ind_target, commit_money):
        trial.decide_issue(sid, m["id"], "missed", reason="p3", basis="opened")
    mt = trial.result(sid).metrics
    assert mt["A1"]["N0"] == 3 and mt["scope"]["excluded_numeric_issues"] == 2        # ตัวหารที่คาด
    assert mt["A1"]["out_of_scope"]["issues"] == 2
    # ระบุ "ไม่ใช่เชิงโครงสร้าง" หลังเห็นผล → ยังอยู่ใน N₀ (กันลดตัวหารหลังเห็นผล)
    trial.update_row(sid, ind_new["id"], xtype="numeric", row_source="post:xtype")
    mt = trial.result(sid).metrics
    assert mt["A1"]["N0"] == 3 and mt["A1"]["post_result"]["xtype"] == 1
    assert fid                                                                  # มีข้อสังเกตให้จับคู่ได้ในรอบนี้


def test_issue_type_is_cross_year_only():
    sid = start("t1", "X4", path="r2", again=True)
    must, _u = _same_year_targets()
    m = _mark_on(sid, must[0])
    with pytest.raises(trial.TrialError, match="คู่ข้ามปีเท่านั้น"):
        trial.update_mark(sid, m["id"], xtype="add")
    assert trial.mark_gaps(trial.session(sid).circles[0], trial.session(sid).xkind) == []


def test_matching_across_pages_without_a_proposal():
    """ย้ายหน้า (วิธีวัดผล หมวด 5): จับคู่กับข้อสังเกตต่างหน้าที่ระบบไม่ได้เสนอได้ · นับเป็นพบ (รีวิวโบ 6460469359)"""
    must, _unread = _same_year_targets()
    f1 = must[0]
    other = next(f for f in must if f.b.page and f.b.page != f1.b.page)
    sid = start("t1", "XP", path="r2", again=True)
    m = _mark_on(sid, f1)
    trial.lock(sid, decl("r2"))
    r = trial.result(sid)
    assert r.proposals[m["id"]] == f1.id and r.proposals[m["id"]] != other.id
    assert other.id in {c.id for c in r.candidates(r.issue_by_id[m["id"]])}  # อยู่ในรายการให้เลือกเอง
    trial.decide_issue(sid, m["id"], "exact", [other.id], **LOC, basis="opened")
    r = trial.result(sid)
    assert r.links[m["id"]] == [other.id] and int(m["page"]) != other.b.page
    mt = r.metrics
    assert mt["A1"]["exact"] == 1 and mt["A3"]["matched"] == 1


# ── ฉบับ 0.3 ร่าง ๒ ต่อรอบ (Bo ACCEPT #36 6460469107 · RESULT_SCHEMA_R3_0.3) ─────────────────────────────
def test_v03_location_is_a_separate_step_and_b4_is_gone():
    """0.3: ผลจับคู่ตัดสินจากเนื้อหา · ตำแหน่งเป็นขั้นแยก 6 สถานะ · บ4 ไม่มีแล้ว · ฝั่งเดียวต้องมีขอบเขตค้น (AC-12)"""
    must, _unread = _same_year_targets()
    f1 = must[0]
    sid = start("t1", "V3a", path="r2", again=True)
    assert trial.session(sid).v03 and trial.session(sid).protocol == trial.PROTOCOL_VERSION
    m = _mark_on(sid, f1)
    trial.lock(sid, decl("r2"))
    with pytest.raises(trial.TrialError, match="บ1–บ3"):
        trial.decide_issue(sid, m["id"], "partial", [f1.id], reason="b4", basis="enough",
                           location="adjacent", relevant_sides=["A", "B"])
    with pytest.raises(trial.TrialError, match="สถานะตำแหน่ง"):
        trial.decide_issue(sid, m["id"], "exact", [f1.id], basis="enough")
    with pytest.raises(trial.TrialError, match="ขอบเขตที่ค้น"):
        trial.decide_issue(sid, m["id"], "exact", [f1.id], basis="enough", location="all_sides", relevant_sides=["B"])
    with pytest.raises(trial.TrialError, match="ถูกบางฝั่ง"):
        trial.decide_issue(sid, m["id"], "exact", [f1.id], basis="enough", location="some_sides",
                           relevant_sides=["B"], search_scope="ส่วน ๗")
    trial.decide_issue(sid, m["id"], "exact", [f1.id], basis="enough", location="adjacent", relevant_sides=["A", "B"])
    d = trial.result(sid).decisions[m["id"]]
    assert (d["location"], d["relevant_sides"], d["evidence"]) == ("adjacent", "A,B", "")
    v = trial.result(sid).metrics["v03"]
    assert v["counts"]["location"]["adjacent"]["exact"] == 1                  # ใกล้เคียง = บ4 เดิม อยู่ที่ตำแหน่ง
    assert v["issues"]["H1"]["num"] == 1 and v["issues"]["H1"]["den"] == 1    # พบตรง แม้ตำแหน่งไม่ถูกทุกฝั่ง
    assert v["location"]["H2"]["num"] == 0 and v["location"]["all_over_P"]["den"] == 1


def test_v03_h1_uses_n0_and_a3_has_fidelity_and_assertion_for_every_finding_in_u():
    must, _unread = _same_year_targets()
    f1, f2, f3 = must[0], must[1], must[2]
    sid = start("t1", "V3b", path="r1", again=True)
    trial.lock(sid, decl(t_ก_total="2", t_ก_root="1", t_ก_red="1"))
    rows = trial.result(sid).issues
    for i, m in enumerate(rows):
        trial.update_row(sid, m["id"], part="๗", cause="t", level="red", ref=str(i + 1), row_source="transcribed")
    a, b, c = rows
    trial.decide_issue(sid, a["id"], "exact", [f1.id], basis="enough", location="all_sides", relevant_sides=["A", "B"])
    trial.decide_issue(sid, b["id"], "undecidable", basis="cannot")
    trial.decide_issue(sid, c["id"], "missed", reason="p3", basis="opened")
    r = trial.result(sid)
    u_must = [f.id for f in r.unmatched_must]
    for fid in u_must:
        g = "s1" if fid == f2.id else ("s3" if fid == f3.id else "s4")
        trial.decide_finding(sid, fid, g, s3_reason="misread" if g == "s3" else "", basis="opened")
    r = trial.result(sid)
    assert not r.complete                                                       # A3 ยังไม่ครบทุกข้อใน U
    with pytest.raises(trial.TrialError, match="มิติ"):
        trial.decide_obs(sid, f1.id, "full", basis="enough", dims={"real": "ok"})
    with pytest.raises(trial.TrialError, match="เหตุ"):
        trial.decide_obs(sid, f1.id, "none", basis="enough", assertion_undecidable=True)
    dims_ok = {d: "ok" for d in trial.DIMS}
    with pytest.raises(trial.TrialError, match="N/A ต้องระบุเหตุ"):
        trial.decide_obs(sid, f1.id, "full", basis="enough", dims={**dims_ok, "direction": "na"})
    trial.decide_obs(sid, f1.id, "full", basis="enough", dims={**dims_ok, "direction": "na", "direction_na": "ข้อความ"})
    # อ่านค่าตรง แต่ข้อสรุปไม่ถูก (เช่น จับคู่รายการข้ามฉบับผิด) ต้องเห็นได้
    trial.decide_obs(sid, f3.id, "full", basis="opened", dims={**dims_ok, "item_match": "wrong", "real": "wrong"})
    for fid in r.u_ids:
        if fid not in (f1.id, f3.id):
            trial.decide_obs(sid, fid, "undecidable", basis="cannot", assertion_undecidable=True)
    with pytest.raises(trial.TrialError, match="ต้องระบุเหตุผล"):
        trial.decide_obs(sid, f1.id, "partial", fidelity_reason="rounding", basis="enough", dims=dims_ok)
    r = trial.result(sid)
    assert r.complete and set(r.obs_eval) == set(r.u_ids)
    v = r.metrics["v03"]
    assert (v["issues"]["N0"], v["issues"]["N"], v["issues"]["exact"]) == (3, 2, 1)
    assert v["issues"]["H1"]["text"] == "1/3" and v["issues"]["supplement"]["text"] == "1/2"   # H1 ÷ N₀
    assert v["obs"]["F"] == len(r.u_ids) and v["obs"]["crosstab"]["full"]["none"] == 1
    assert v["obs"]["read_ok_assertion_wrong"] == 1
    assert v["obs"]["crosstab_by_group"]["matched"]["full"]["full"] == 1
    assert v["obs"]["A3_fidelity"]["den"] == 2 and v["obs"]["A3_assertion"]["num"] == 1
    assert "trial_obs_evaluated" in _audit_actions(f"{sid}/{f1.id}")


def test_v02_rounds_keep_0_2_rules_after_upgrade():
    """รอบเดิมคงรุ่นของตัวเอง: รอบ 0.2.2 ยังใช้หลักฐานชี้ตำแหน่ง/บ4 และไม่มี A3-อ/A3-ข"""
    must, _unread = _same_year_targets()
    sid = start("t1", "V2k", path="r2", again=True)
    conn = connect()
    try:
        conn.execute("UPDATE trial_sessions SET protocol = ? WHERE id = ?", ("pdfpair-protocol-0.2.2 (ร่าง)", sid))
        conn.commit()
    finally:
        conn.close()
    assert not trial.session(sid).v03
    m = _mark_on(sid, must[0])
    trial.lock(sid, decl("r2"))
    trial.decide_issue(sid, m["id"], "partial", [must[0].id], reason="b4", evidence="all", basis="enough")
    r = trial.result(sid)
    assert "v03" not in r.metrics and r.metrics["A1"]["partial_reasons"]["b4"] == 1
    with pytest.raises(trial.TrialError, match="ฉบับ 0.2"):
        trial.decide_obs(sid, must[0].id, "full", basis="enough", dims={"real": "ok"})
    assert trial.summary(sid)["protocol"] == "pdfpair-protocol-0.2.2 (ร่าง)"


def test_v03_survey_is_form_08_items_five_to_one():
    sid = start("t1", "V3s", path="r1", again=True)
    s = trial.session(sid)
    items = [k for _g, it in trial.likert_items(s) for k, _t in it]
    assert len(items) == 13 and len(trial.LIKERT_ITEMS_V03) == 5
    assert "ไม่รบกวนการตรวจ" in dict(trial.LIKERT_ITEMS_V03[0][1])["q2_2"]     # เชิงบวกทุกข้อ (แบบ 08)
    assert list(trial.LIKERT_SCALE_V03) == ["5", "4", "3", "2", "1"]


# ── ตัวอย่างคำนวณ: ข้อมูลสังเคราะห์เล็ก ๆ → จำนวนที่คาด (รีวิวโบ 6417479593 ข้อ 2) ─────────────────
def test_worked_example_counts():
    """ทาง ร1 · ส่วน ๗ ตรวจครบ · 5 ประเด็นที่ล็อก (ก 4 · ช 1) · ข้อสังเกต fA fB
    แถว 1, 2 → fA (สองประเด็นต่อข้อสังเกตเดียว) · แถว 3 → fB บางส่วน · แถว 4 พลาด และจัด ต/ล หลังเห็นผล · แถว 5 ตัดสินไม่ได้"""
    must, _unread = _same_year_targets()
    fa, fb = must[0], must[1]
    sid = start("t1", "W1", path="r1", again=True)
    trial.lock(sid, decl(t_ก_total="4", t_ก_root="2", t_ก_red="2"))
    rows = trial.result(sid).issues
    assert len(rows) == 5
    for i, m in enumerate(rows):
        trial.update_row(sid, m["id"], part="๗", cause="t" if i % 2 == 0 else "l", level="red" if i < 2 else "brown",
                         ref=str(i + 1), row_source="post:cause" if i == 3 else "transcribed")
    r1, r2, r3, r4, r5 = rows
    trial.decide_issue(sid, r1["id"], "exact", [fa.id], **LOC, basis="enough")
    trial.decide_issue(sid, r2["id"], "exact", [fa.id], **LOC, basis="enough")
    trial.decide_issue(sid, r3["id"], "partial", [fb.id], reason="b3", **LOC, basis="enough")
    trial.decide_issue(sid, r4["id"], "missed", reason="p1", basis="cannot")
    trial.decide_issue(sid, r5["id"], "undecidable", basis="cannot")
    m = trial.result(sid).metrics
    a1, led = m["A1"], m["A3"]
    assert (a1["N0"], a1["undecidable"], a1["N"]) == (5, 1, 4)                # N = N0 − ตัดสินไม่ได้
    assert (a1["exact"], a1["partial"], a1["missed"]) == (2, 1, 1)
    assert a1["strict"]["text"] == "2 จาก 4" and a1["with_partial"]["text"] == "3 จาก 4"
    assert a1["post_result"] == {"part": 0, "cause": 1, "level": 0, "xtype": 0}           # แถว 4 ยังนับใน N0/N หลัก
    assert a1["scope_locked_only"]["N0"] == 5
    assert a1["by_cause"]["t"]["N0"] == 3 and a1["by_cause"]["l"]["N0"] == 1  # แถว 4 (ล) ไม่อยู่ใน by_cause
    assert a1["by_level"]["brown"]["N0"] == 3
    assert led["matched"] == 2                                                # fA นับครั้งเดียว + fB


def test_list_integrity_without_own_copy():
    sid = start("t1", "I1", path="r1", again=True)
    trial.lock(sid, decl())
    r = trial.result(sid)
    assert "list_integrity_unverifiable" in trial.status_of(r.s, r)["flags"]
    assert trial.summary(sid)["declaration"]["list_integrity"] == "not_verifiable"
    sid2 = start("t1", "I2", path="r1", again=True)
    trial.lock(sid2, decl(own_copy="2026-10-20 sha256:ab12"))
    r2 = trial.result(sid2)
    assert "list_integrity_unverifiable" not in trial.status_of(r2.s, r2)["flags"]
    assert trial.summary(sid2)["declaration"]["list_integrity"] == "declared_by_reviewer_not_verified"


# ── กติกาการจับคู่ (หมวด 5) ──────────────────────────────────────────────────────────
def _same_year_targets():
    _psid, v = _probe("t1")
    s = trial.session(_psid)
    must = [f for f in v.result.findings if not f.info and f.kind != "unread" and f.b.page and f.b.bbox
            and f.b.page in s.pages("cur")]
    unread = next(f for f in v.result.findings if f.kind == "unread")
    return must, unread


def test_matching_rules_codes_evidence_basis_many_to_many_and_history():
    must, unread = _same_year_targets()
    f1, f2 = must[0], must[1]
    sid = start("t1", "M1", path="r2", again=True)
    p0 = trial.session(sid).pages("cur")[0]
    m1 = _mark_on(sid, f1)
    m2 = trial.add_mark(sid, "cur", p0, 0.02, 0.98, "brown")                  # มุมหน้า ไม่มีข้อใด
    _fill(sid, m2, topic="ฌ", part="๖", cause="l")
    m3 = _mark_on(sid, f1, pen="brown", topic="ญ", part="๗", cause="l")       # สองประเด็น ↔ ข้อสังเกตเดียว
    trial.lock(sid, decl("r2"))
    r = trial.result(sid)
    assert r.proposals[m1["id"]] == f1.id and r.proposals[m2["id"]] == ""
    assert r.metrics["A1"]["pending"] == 3 and r.metrics["A1"]["exact"] == 0
    with pytest.raises(trial.TrialError, match="บ1–บ3"):
        trial.decide_issue(sid, m1["id"], "partial", [f1.id], **LOC, basis="enough")
    with pytest.raises(trial.TrialError, match="สถานะตำแหน่ง"):
        trial.decide_issue(sid, m1["id"], "partial", [f1.id], reason="b1", basis="enough")
    with pytest.raises(trial.TrialError, match="ฐานการวินิจฉัย"):
        trial.decide_issue(sid, m1["id"], "exact", [f1.id], **LOC)
    with pytest.raises(trial.TrialError, match="อย่างน้อย 1 ข้อ"):
        trial.decide_issue(sid, m1["id"], "exact", [], **LOC, basis="enough")
    with pytest.raises(trial.TrialError, match="อ่านหรือสกัดไม่ได้"):
        trial.decide_issue(sid, m2["id"], "exact", [unread.id], **LOC, basis="enough")
    trial.decide_issue(sid, m1["id"], "exact", [f1.id, f2.id], **LOC, basis="enough")   # หนึ่งต่อหลาย
    trial.decide_issue(sid, m3["id"], "exact", [f1.id], **LOC_SOME, basis="opened")
    with pytest.raises(trial.TrialError, match="พ1–พ5"):
        trial.decide_issue(sid, m2["id"], "missed", basis="opened")
    trial.decide_issue(sid, m2["id"], "missed", reason="p3", basis="opened")
    m = trial.result(sid).metrics
    assert (m["A1"]["exact"], m["A1"]["missed"], m["A1"]["pending"], m["A1"]["N"]) == (2, 1, 0, 3)
    assert m["A1"]["missed_reasons"]["p3"] == 1 and m["v03"]["counts"]["location"]["all_sides"]["exact"] == 1 and m["v03"]["counts"]["location"]["some_sides"]["exact"] == 1
    assert m["A3"]["matched"] == 2                                             # f1 นับครั้งเดียว + f2
    assert m["B1_basis"]["enough"] == 1 and m["B1_basis"]["opened"] == 2
    with pytest.raises(trial.TrialError, match="ต้องระบุเหตุผล"):
        trial.decide_issue(sid, m1["id"], "partial", [f1.id], reason="b3", **LOC, basis="enough")
    trial.decide_issue(sid, m1["id"], "partial", [f1.id], reason="b3", **LOC, basis="enough",
                       change_reason="ระบบยกเฉพาะยอดรวม ไม่ครบประเด็น")
    r = trial.result(sid)
    hist = r.history("issue", m1["id"])
    assert len(hist) == 2 and hist[0]["before"] is None and hist[1]["reason"].startswith("ระบบยกเฉพาะ")
    assert hist[1]["before"]["links"] == sorted([f1.id, f2.id]) and hist[1]["after"]["links"] == [f1.id]
    assert r.metrics["A1"]["partial_reasons"]["b3"] == 1 and r.metrics["A3"]["matched"] == 1
    trial.decide_issue(sid, m1["id"], "partial", [f1.id], reason="b3", **LOC, basis="enough")   # เท่าเดิม = ไม่บันทึกซ้ำ
    assert len(trial.result(sid).history("issue", m1["id"])) == 2
    assert "trial_issue_decided" in _audit_actions(f"{sid}/{m1['id']}")


# ── ข้อสังเกตที่ไม่ได้จับคู่ + บัญชี (หมวด 6–7) ──────────────────────────────────────────
def test_unmatched_groups_and_ledger_closes_only_when_all_placed():
    must, _unread = _same_year_targets()
    f1 = must[0]
    sid = start("t1", "L1", path="r2", again=True)
    m1 = _mark_on(sid, f1)
    trial.lock(sid, decl("r2", part_๘="partial"))
    trial.decide_issue(sid, m1["id"], "exact", [f1.id], **LOC, basis="enough")
    r = trial.result(sid)
    um = r.unmatched_must
    assert f1.id not in {f.id for f in um} and len(um) >= 5
    with pytest.raises(trial.TrialError, match="จับคู่กับประเด็นแล้ว"):
        trial.decide_finding(sid, f1.id, "s1", basis="enough")
    with pytest.raises(trial.TrialError, match="ส3"):
        trial.decide_finding(sid, um[0].id, "s3", basis="enough")
    with pytest.raises(trial.TrialError, match="ฐานการวินิจฉัย"):
        trial.decide_finding(sid, um[0].id, "s1")
    led = r.metrics["A3"]
    assert not led["closed"] and led["pending"] == len(um)
    assert led["false_alarm"]["text"] == "ยังตัดสินไม่ครบ"                       # บัญชียังไม่ปิด = ไม่รายงานสัดส่วน
    trial.decide_finding(sid, um[0].id, "s1", basis="enough")
    trial.decide_finding(sid, um[1].id, "s2", basis="opened", issue_ref=m1["id"])
    trial.decide_finding(sid, um[2].id, "s3", s3_reason="rounding", basis="opened")
    trial.decide_finding(sid, um[3].id, "s4", basis="cannot")
    with pytest.raises(trial.TrialError, match="ตรวจบางส่วนหรือไม่ได้ตรวจ"):
        trial.decide_finding(sid, um[4].id, "outside", part="๗", note="x")    # ส่วนที่ประกาศว่าตรวจครบ อ้างไม่ได้
    with pytest.raises(trial.TrialError, match="เหตุ"):
        trial.decide_finding(sid, um[4].id, "outside", part="๘")
    for f in um[4:]:
        trial.decide_finding(sid, f.id, "outside", part="๘", note="อยู่ในตารางเงินนอกงบที่ตรวจไม่ครบ")
    r = trial.result(sid)
    assert not r.complete                                                      # 0.3: ยังไม่ประเมิน A3 ของข้อใน U
    for fid in r.u_ids:
        trial.decide_obs(sid, fid, "undecidable", basis="cannot", assertion_undecidable=True)
    r = trial.result(sid)
    led = r.metrics["A3"]
    assert led["closed"] and led["pending"] == 0 and r.complete
    assert led["F"] == led["matched"] + led["s1"] + led["s2"] + led["s3"] + led["s4"] == 5
    assert led["outside"] == len(um) - 4 and led["s3_reasons"]["rounding"] == 1
    assert led["outside_by_part"] == {"๘": len(um) - 4}
    assert led["false_alarm"]["text"] == "1 จาก 4"                                # F − ส4 = 4
    assert led["real_difference"] is None          # ระงับจนกว่าจะนิยามความถูกของข้อสังเกต (รีวิวโบ 6417479593 ข้อ 1)
    assert led["system_extra_confirmed"] == 2
    with pytest.raises(trial.TrialError, match="ต้องระบุเหตุผล"):
        trial.decide_finding(sid, um[0].id, "s3", s3_reason="misread", basis="enough")
    trial.decide_finding(sid, um[0].id, "s3", s3_reason="misread", basis="enough", change_reason="ดูภาพอีกครั้ง")
    # ข้อที่จัดกลุ่มไว้แล้วถูกจับคู่ภายหลัง → ย้ายไป จ (ไม่นับซ้ำ) · กลุ่มเดิมรายงานเป็น "ถูกแทน"
    trial.decide_issue(sid, m1["id"], "exact", [f1.id, um[0].id], **LOC, basis="enough",
                       change_reason="ข้อนี้คือประเด็นเดียวกัน")
    led = trial.result(sid).metrics["A3"]
    assert led["matched"] == 2 and led["s3"] == 1 and led["superseded_groups"] == 1 and led["F"] == 5


def test_ledger_inconsistency_fails_loudly(client):
    must, _unread = _same_year_targets()
    sid = start("t1", "L2", path="r2", again=True)
    m1 = _mark_on(sid, must[0])
    trial.lock(sid, decl("r2"))
    trial.decide_issue(sid, m1["id"], "exact", [must[0].id], **LOC, basis="enough")
    conn = connect()
    try:                                               # ข้อมูลเสีย: กลุ่ม ส ของข้อสังเกตที่ไม่มีในรอบนี้
        conn.execute("INSERT INTO trial_finding_groups (session_id, finding_id, grp, decided_at) VALUES (?,?,?,?)",
                     (sid, "no_such_finding", "s1", "2026-10-26"))
    finally:
        conn.close()
    with pytest.raises(trial.LedgerError, match="บัญชีข้อสังเกตไม่ปิด"):
        trial.result(sid).metrics
    with pytest.raises(trial.LedgerError):
        trial.summary(sid)
    r = client.get(f"/trial/s/{sid}/summary.json")
    assert r.status_code == 409 and "บัญชีข้อสังเกตไม่ปิด" in r.text
    assert client.get(f"/trial/s/{sid}/dashboard").status_code == 409
    j = client.get(f"/api/trial/s/{sid}/result")
    assert j.status_code == 409 and j.json()["code"] == "conflict"
    assert not [e for e in audit.entries(limit=50, object_id=sid) if e["action"] == "trial_summary_exported"]


def test_r2_scope_comes_from_declaration_and_page_ticks_never_change_counts():
    """ทาง ร2: ขอบเขต/N/F มาจากใบประกาศก่อนเห็นผล (เหมือน ร1) · กด/ยกเลิก "ตรวจหน้านี้แล้ว" ไม่เปลี่ยนผลนับ"""
    must, _unread = _same_year_targets()
    f1 = must[0]
    out = {}
    for name, ticks in (("none", False), ("ticked", True)):
        sid = start("t1", f"T{name}", path="r2", again=True)
        s = trial.session(sid)
        a = _mark_on(sid, f1, part="๗")
        b = _mark_on(sid, must[1], pen="brown", topic="ค", part="๖", cause="l")   # ส่วนที่ประกาศว่าตรวจบางส่วน
        if ticks:
            for p in s.pages("cur"):
                trial.page_done(sid, "cur", p)
            for p in s.pages("prev")[:2]:
                trial.page_done(sid, "prev", p)
            trial.page_undone(sid, "cur", s.pages("cur")[0])
        trial.lock(sid, decl("r2", part_๖="partial"))
        trial.decide_issue(sid, a["id"], "exact", [f1.id], **LOC, basis="enough")
        trial.decide_issue(sid, b["id"], "exact", [must[1].id], **LOC, basis="enough")
        r = trial.result(sid)
        assert r.in_scope(r.issue_by_id[a["id"]]) and not r.in_scope(r.issue_by_id[b["id"]])
        out[name] = r.metrics
        assert bool(trial.session(sid).done) is ticks
    assert out["none"] == out["ticked"]                                       # ติ๊กหน้าไม่มีผลต่อตัวเลขใด
    m = out["none"]
    assert (m["A1"]["N0"], m["A1"]["N"], m["A1"]["out_of_scope"]["issues"]) == (1, 1, 1)
    assert m["A3"]["matched"] == 1 and m["A3"]["outside_linked"] == 1         # จับคู่จากส่วนที่ตรวจบางส่วน = นอก F


# ── N · ขอบเขต · ใบประกาศ (หมวด 2, 7) ───────────────────────────────────────────────
def test_denominator_scope_rows_and_declaration_check():
    sid = start("t1", "N1", path="r1", again=True)
    parts = {f"part_{c}": "partial" for c, _l in trial.PARTS}
    parts["part_๗"] = "full"
    trial.lock(sid, decl(**parts, t_ก_total="3", t_ก_root="1", t_ก_red="2"))
    r = trial.result(sid)
    ga, gb, gc, ch = r.issues
    with pytest.raises(trial.TrialError, match="ส่วนของเล่มไม่ถูกต้อง"):
        trial.update_row(sid, ga["id"], part="9")
    trial.update_row(sid, ga["id"], part="๗", cause="t", level="red", side="cur",
                     page=str(trial.session(sid).pages("cur")[0]))
    gaps = trial.result(sid).gaps(trial.result(sid).issue_by_id[ga["id"]])
    assert "ข้อที่ในรายการที่ล็อก" in gaps and "ที่มาของลักษณะแถว" in gaps   # ต้องอ้างกลับรายการที่ล็อก + บอกที่มา
    with pytest.raises(trial.TrialError, match="ที่มาของลักษณะแถว"):
        trial.update_row(sid, ga["id"], row_source="guess")
    trial.update_row(sid, ga["id"], ref="12", row_source="transcribed")
    with pytest.raises(trial.TrialError, match="ที่มาของลักษณะแถว"):
        trial.update_row(sid, gb["id"], row_source="post:topic")
    trial.update_row(sid, gb["id"], part="๗", cause="t", level="red", ref="13", row_source="post:part,cause")
    trial.update_row(sid, gc["id"], part="๖", cause="l", level="brown", ref="14", row_source="transcribed")
    trial.update_row(sid, ch["id"], part="๗", cause="t", level="brown", found_in="prev", ref="15",
                     row_source="transcribed")
    r = trial.result(sid)
    assert "ขอบเขตที่ค้นในอีกฉบับ" in r.gaps(r.issue_by_id[ch["id"]])        # ของที่หายต้องจดขอบเขตที่ค้น
    trial.update_row(sid, ch["id"], searched="ส่วน ๗ ทั้งหมด")
    fid = r.matchable[0].id
    trial.decide_issue(sid, ga["id"], "exact", [fid], **LOC, basis="enough")
    trial.decide_issue(sid, gb["id"], "missed", reason="p1", basis="cannot")
    trial.decide_issue(sid, gc["id"], "exact", [fid], **LOC, basis="enough")
    trial.decide_issue(sid, ch["id"], "undecidable", basis="cannot")
    r = trial.result(sid)
    a1 = r.metrics["A1"]
    assert (a1["issues"], a1["undecidable"], a1["N"], a1["exact"], a1["missed"]) == (3, 1, 2, 1, 1)
    assert a1["N0"] == 3                                                       # N0 = ที่ล็อกในขอบเขตทั้งหมด (รีวิว 6409928179 ข้อ 3)
    # ตัวประเด็นมาจากรายการที่ล็อก → อยู่ในผลรวมหลัก · แยกเฉพาะมิติที่จัดใหม่ (รีวิวโบ 6417479593 ข้อ 3)
    assert a1["post_result"] == {"part": 1, "cause": 1, "level": 0, "xtype": 0} and a1["scope_locked_only"]["N0"] == 2
    assert a1["strict"]["text"] == "1 จาก 2" and a1["out_of_scope"]["issues"] == 1
    assert a1["by_cause"]["t"]["N"] == 1                                       # gb จัด ต/ล หลังเห็นผล → ไม่อยู่ในแถวต้นเหตุ
    assert a1["by_level"]["red"]["N"] == 2 and a1["by_level"]["red"]["exact"] == 1 and set(a1["by_topic"]) == {"ก", "ช"}
    assert r.metrics["A4"]["missed_unread"] == 1 and r.metrics["A4"]["parts"] == {"full": 1, "partial": 7, "none": 0}
    assert r.declaration_check == [{"topic": "ก", "declared_root": 1, "rows_root": 2, "declared_red": 2,
                                    "rows_red": 2}]                             # ไม่ปรับให้ตรงเงียบ ๆ
    assert "declaration_mismatch" in trial.status_of(r.s, r)["flags"]
    assert trial._rate(0, 0)["text"] == "คำนวณไม่ได้" and trial._rate(7, 10)["pct"] == 70.0
    assert trial._rate(3, 9)["pct"] is None


# ── สรุปเฉพาะจำนวน · ลำดับเวลา · เหตุคัดออก ─────────────────────────────────────────
def test_summary_is_counts_only_with_timeline_and_exclusions():
    sid = start("t1", "S1", path="r2", again=True)
    s = trial.session(sid)
    m = trial.add_mark(sid, "cur", s.pages("cur")[0], .3, .3, "pin")
    trial.update_mark(sid, m["id"], topic="ซ", part="๒", cause="t", level="red", searched="ค้นส่วน ๒ หน้าลับ 7",
                      note="ข้อความลับของผู้ตรวจ")
    trial.lock(sid, decl("r2", made="after"))
    trial.decide_issue(sid, m["id"], "missed", reason="p3", basis="opened")
    trial.finish_use(sid, "ทดลองจบก่อนครบ")
    trial.save_answers(sid, {"q2_1": "4", "k1": "self", "o3_1": "ลื่นดี"})
    data = trial.summary_bytes(sid)
    body = data.decode("utf-8")
    for secret in ("ข้อความลับของผู้ตรวจ", "ค้นส่วน ๒ หน้าลับ 7", "ทดลองจบก่อนครบ", m["id"], '"fx"'):
        assert secret not in body
    d = json.loads(body)
    assert d["protocol"] == trial.PROTOCOL_VERSION and d["trial_version"] == "trial-0.3.0" and d["path"] == "r2"
    assert d["declaration"]["topics"]["ซ"] == {"total": 1, "root": 1, "red": 1} and d["declaration"]["made"] == "after"
    assert d["status"]["excluded_main"] and "list_after_results" in d["status"]["exclusions"]
    assert d["timeline"]["declared_at"] < d["timeline"]["released_at"]
    assert d["use"]["done"] and not d["use"]["complete_at_finish"]
    assert d["use"]["at_finish"] == {"complete": False, "issues_total": 1, "issues_done": 1,
                                     "findings_to_place": d["use"]["at_finish"]["findings_to_place"], "findings_placed": 0}
    assert d["survey"]["consent_given"] and d["timeline"]["consent_at"] < d["timeline"]["declared_at"]
    assert d["survey"]["likert"]["q2_1"] == "4" and d["survey"]["steps"]["k1"] == "self"
    assert d["metrics"]["A1"]["missed"] == 1 and d["book"]["current_sha256"]
    import hashlib
    ex = [e for e in audit.entries(limit=50) if e["action"] == "trial_summary_exported" and e["object_id"] == sid]
    assert ex and hashlib.sha256(data).hexdigest() in ex[0]["detail_json"]


# ── แบบสอบถาม (แบบ 03 ฉบับ 0.2) ────────────────────────────────────────────────────
def test_survey_matches_form_03_and_opens_only_after_results_used():
    keys = [k for _g, items in trial.LIKERT_ITEMS for k, _t in items]
    assert keys == [f"q2_{i}" for i in range(1, 14)]
    texts = [t for _g, items in trial.LIKERT_ITEMS for _k, t in items]
    assert texts[0].startswith("๒.๑ ") and texts[-1].startswith("๒.๑๓ ") and "ไม่ใช่คำตัดสินว่าผิด" in texts[6]
    assert [g for g, _i in trial.LIKERT_ITEMS] == ["ประโยชน์", "ความเข้าใจหลักฐาน", "ภาระงาน", "การพึ่งพาระบบ",
                                                    "ความต้องการใช้ต่อ"]
    assert [t[:2] for _k, t in trial.STEPS] == ["ข๑", "ข๒", "ข๓", "ข๔", "ข๕", "ข๖"]
    assert [t[:3] for _k, t in trial.OPEN_ITEMS] == ["๓.๑", "๓.๒", "๓.๓", "๓.๔"]
    assert len(trial.CONSENT_ITEMS) == 3 and len(trial.GENERAL_ITEMS) == 2
    ok = {"q2_5": "2"}
    sid = start("t1", "Q1", path="r1", again=True)
    with pytest.raises(trial.TrialError, match="หลังส่งใบประกาศ"):
        trial.save_answers(sid, ok)
    trial.lock(sid, decl())
    with pytest.raises(trial.TrialError, match="หลังใช้ผล"):
        trial.save_answers(sid, ok)
    with pytest.raises(trial.TrialError, match="ระบุเหตุ"):
        trial.finish_use(sid)
    trial.finish_use(sid, "ทดสอบ")
    assert trial.survey_state(trial.session(sid)) == "open"
    with pytest.raises(trial.TrialError, match="ยังไม่ได้ตอบ"):
        trial.save_answers(sid, {})
    with pytest.raises(trial.TrialError, match="1–5"):
        trial.save_answers(sid, {**ok, "q2_1": "9"})
    with pytest.raises(trial.TrialError, match="ขั้นตอน"):
        trial.save_answers(sid, {**ok, "k2": "maybe"})
    with pytest.raises(trial.TrialError, match="ข้อมูลทั่วไป"):
        trial.save_answers(sid, {**ok, "g4_1": "20"})
    trial.save_answers(sid, {**ok, "k6": "helped", "g4_1": "3to10", "o3_3": "ระวังข้อที่ระบบอ่านไม่ได้"})
    a = trial_repo.answers(sid)
    assert a["q2_5"] == "2" and a["k6"] == "helped" and a["g4_1"] == "3to10" and "c3" not in a


# ── สถานะ: หยุด · ถอนตัว · ล้มเหลว (หมวด 8) ───────────────────────────────────────────
def test_stop_and_withdraw_freeze_the_round():
    sid = start("t1", "W1", path="r2", again=True)
    with pytest.raises(trial.TrialError, match="ระบุเหตุ"):
        trial.set_status(sid, "stopped")
    trial.set_status(sid, "stopped", "ไฟล์ไม่ตรงทะเบียน")
    with pytest.raises(trial.TrialError, match="หยุดหรือถอนตัว"):
        trial.add_mark(sid, "cur", trial.session(sid).pages("cur")[0], .5, .5, "red")
    with pytest.raises(trial.TrialError, match="หยุดหรือถอนตัว"):
        trial.lock(sid, decl("r2"))
    assert trial.status_of(trial.session(sid))["run"] == "stopped"
    assert start("t1", "W1") != sid                                      # รอบที่หยุดไม่ถูกพากลับไปทำต่อ
    sid2 = start("t1", "W2", path="r1", again=True)
    trial.lock(sid2, decl())
    trial.set_status(sid2, "withdrawn", no_data_use=True)
    d = trial.summary(sid2)
    assert "metrics" not in d and "survey" not in d and "declaration" not in d and d["status"]["no_data_use"]
    assert d["status"]["reviewer"] == "withdrawn"
    with pytest.raises(trial.TrialError, match="หยุดหรือถอนตัว"):
        trial.decide_issue(sid2, trial.session(sid2).rows[0]["id"], "undecidable", basis="cannot")


def test_run_failure_is_recorded_retry_runs_once_and_viewing_never_creates_a_run(client, monkeypatch):
    sid = start("t1", "F1", path="r1", again=True)
    real = pdfshelf.start

    def broken(*a, **k):
        raise pdfshelf.ShelfError("ไฟล์ถูกเปิดค้าง (จำลอง)")
    monkeypatch.setattr(pdfshelf, "start", broken)
    runs = _runs()
    assert trial.lock(sid, decl()) == ""
    s = trial.session(sid)
    assert s.locked and s.rec["run_id"] == "" and "เปิดค้าง" in s.rec["run_error"] and s.rec["run_failures"] == 1
    assert trial.status_of(s)["run"] == "failed"
    with pytest.raises(trial.TrialError, match="ลองเทียบอีกครั้ง"):
        trial.result(sid)
    page = client.get(f"/trial/s/{sid}/result")
    assert page.status_code == 409 and "ลองเทียบอีกครั้ง" in page.text and f"/trial/s/{sid}/run" in page.text
    assert client.get(f"/api/trial/s/{sid}/result").json()["code"] == "conflict"
    assert _runs() == runs                                                     # เปิดดูผลไม่สร้างรอบเทียบ
    monkeypatch.setattr(pdfshelf, "start", real)
    out, barrier = [], threading.Barrier(2)

    def go():
        barrier.wait()
        out.append(trial.retry_run(sid))
    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    # สองแท็บกดพร้อมกัน = เทียบครั้งเดียว · ชั้นเก็บเล่มอาจใช้รอบเทียบที่จำไว้ของคู่เดียวกัน (dedupe) จึงเพิ่มได้ 0 หรือ 1
    assert len(set(out)) == 1 and out[0] and _runs() - runs in (0, 1)
    s = trial.session(sid)
    assert s.rec["run_id"] == out[0] and s.rec["run_error"] == ""
    assert "run_failures" in trial.status_of(s)["flags"] and trial.status_of(s)["run"] == "ok"
    assert "trial_run_failed" in _audit_actions(sid)


# ── รอบกติกา 0.1 ───────────────────────────────────────────────────────────────────
def _legacy_session(locked: bool):
    """รอบที่สร้างก่อนฉบับ 0.2 (protocol ว่าง) — จำลองด้วยชั้นที่เก็บโดยตรง"""
    b = trial.get_book("t1")
    s0 = trial.session(start("t1", "TMP", path="r2", again=True))
    sid = trial_repo.create_session("t1", "G", {k: v for k, v in s0.book.items() if k != "pair_kind"})
    m = trial_repo.add_mark(sid, "cur", s0.pages("cur")[0], .5, .5, "red", level="")
    trial_repo.update_mark(sid, m["id"], topic="ช", level="")
    if locked:
        trial_repo.lock(sid, {"marks": {"red": 1}})
        pid, rid = pdfshelf.start(b.previous, b.current, b.agency)
        trial_repo.attach_run(sid, pid, rid)
        f = next(x for x in pdfpair.view(rid).result.findings if not x.info)
        conn = connect()
        try:
            conn.execute("INSERT INTO trial_links (session_id, mark_id, finding_id, proposed, verdict, decided_at) "
                         "VALUES (?,?,?,1,'exact','2026-10-25')", (sid, m["id"], f.id))
        finally:
            conn.close()
    return sid, m


def test_legacy_rounds_stay_0_1_both_sent_and_unsent(client):
    # ASK-GIFT ทาง ก (26 ต.ค.): รอบ 0.1 อ่าน/นับตามรุ่นเดิม · งาน 0.2 = รอบใหม่ (ไม่เปลี่ยนรุ่นอัตโนมัติ)
    sid, m = _legacy_session(locked=True)
    s = trial.session(sid)
    assert s.read_only_legacy and s.protocol == trial.LEGACY_PROTOCOL
    r = trial.result(sid)
    assert r.legacy and r.metrics["pens"]["red"]["exact"] == 1
    with pytest.raises(trial.TrialError, match="กติกา 0.1"):
        trial.decide_issue(sid, m["id"], "exact", ["x"], **LOC, basis="enough")
    assert trial.summary(sid)["protocol"] == trial.LEGACY_PROTOCOL
    page = client.get(f"/trial/s/{sid}/result")
    assert page.status_code == 200 and "รอบกติกา 0.1" in page.text and "อ่านได้อย่างเดียว" in page.text
    assert client.get(f"/api/trial/s/{sid}/result").json()["legacy"] is True
    sid2, m2 = _legacy_session(locked=False)
    s2 = trial.session(sid2)
    assert s2.legacy and not s2.locked and s2.protocol == trial.LEGACY_PROTOCOL
    for call in (lambda: trial.add_mark(sid2, "cur", s2.pages("cur")[0], .5, .5, "red"),
                 lambda: trial.update_mark(sid2, m2["id"], topic="ก"),
                 lambda: trial.lock(sid2, decl("r2")), lambda: trial.give_consent(sid2, CONSENT)):
        with pytest.raises(trial.TrialError, match="กติกา 0.1"):
            call()
    fresh = trial.start("t1", "G")
    assert fresh not in (sid, sid2) and trial.session(fresh).protocol == trial.PROTOCOL_VERSION
    assert trial_repo.get_session(sid2)["protocol"] == "" and len(trial_repo.marks(sid2)) == 1   # รอบเดิมไม่ถูกแตะ
    html = client.get(f"/trial/s/{sid2}").text
    assert "รอบกติกา 0.1 — อ่านได้อย่างเดียว" in html and "ใบประกาศก่อนเห็นผล" not in html


def test_consent_comes_before_any_activity(client):
    sid = trial.start("t1", "C1", path="r2", again=True)
    s = trial.session(sid)
    for call in (lambda: trial.add_mark(sid, "cur", s.pages("cur")[0], .5, .5, "red"),
                 lambda: trial.page_done(sid, "cur", s.pages("cur")[0]), lambda: trial.lock(sid, decl("r2"))):
        with pytest.raises(trial.TrialError, match="ความยินยอม"):
            call()
    with pytest.raises(trial.TrialError, match="ความยินยอม"):
        trial.give_consent(sid, {"c1": "1", "c2": "1"})
    html = client.get(f"/trial/s/{sid}").text
    assert 'action="/trial/s/' + sid + '/consent"' in html and "ใบประกาศก่อนเห็นผล" not in html
    trial.give_consent(sid, CONSENT)
    at = trial.session(sid).rec["consent_at"]
    trial.give_consent(sid, CONSENT)                                      # กดซ้ำไม่เปลี่ยนเวลาเดิม
    assert trial.session(sid).rec["consent_at"] == at
    trial.add_mark(sid, "cur", s.pages("cur")[0], .5, .5, "red")
    assert "trial_consent_given" in _audit_actions(sid)


def test_old_database_gets_the_new_columns_without_touching_rows(fresh_db):
    old = sqlite3.connect(fresh_db)
    old.executescript("""
        CREATE TABLE trial_sessions (id TEXT PRIMARY KEY, book_id TEXT NOT NULL, reviewer TEXT NOT NULL DEFAULT '',
            book_json TEXT NOT NULL, started_at TEXT NOT NULL, locked_at TEXT NOT NULL DEFAULT '',
            run_id TEXT NOT NULL DEFAULT '', project_id TEXT NOT NULL DEFAULT '');
        CREATE TABLE trial_marks (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, side TEXT NOT NULL,
            page INTEGER NOT NULL, fx REAL NOT NULL, fy REAL NOT NULL, pen TEXT NOT NULL,
            topic TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            deleted INTEGER NOT NULL DEFAULT 0);
        INSERT INTO trial_sessions (id, book_id, book_json, started_at) VALUES ('tr_old', 't1', '{}', '2026-10-24');
        INSERT INTO trial_marks (id, session_id, side, page, fx, fy, pen, created_at)
            VALUES ('mk_old', 'tr_old', 'cur', 3, .5, .5, 'red', '2026-10-24');
    """)
    old.commit()
    old.close()
    trial_repo.init_schema(fresh_db)
    s = trial_repo.get_session("tr_old", db_path=fresh_db)
    assert s["protocol"] == "" and s["path"] == "" and s["status"] == "" and s["run_failures"] == 0
    mk = trial_repo.marks("tr_old", db_path=fresh_db)[0]
    assert mk["origin"] == "mark" and mk["level"] == "" and mk["pen"] == "red" and mk["page"] == 3
    trial_repo.init_schema(fresh_db)                                           # เปิดซ้ำได้ ไม่ error


# ── ปิดทุกทางที่เปิดผลก่อนล็อก ────────────────────────────────────────────────────────
def test_every_path_to_results_is_closed_before_lock(client):
    tok = _token(client)
    sid = web_start(client, tok, book_id="t1", again="1", path="r2", reviewer="LK")
    runs = _runs()
    html = client.get(f"/trial/s/{sid}").text
    assert "/pdfpair/runs/" not in html and f"/trial/s/{sid}/result" not in html
    data = json.loads(html.split('id="tr-data">')[1].split("</script>")[0])
    assert data["preload"] and all(u.startswith(f"/trial/s/{sid}/page/") for u in data["preload"])
    for path in ("result", "dashboard", "summary.json"):
        assert client.get(f"/trial/s/{sid}/{path}").status_code == 409
    sv = client.get(f"/trial/s/{sid}/survey")
    assert sv.status_code == 200 and "หลังส่งใบประกาศ" in sv.text and 'name="q2_1"' not in sv.text
    api = client.get(f"/api/trial/s/{sid}/result")
    assert api.status_code == 409 and api.json()["code"] == "not_locked"
    body = client.get(f"/api/trial/s/{sid}").text
    assert "finding" not in body and "metrics" not in body and "verdict" not in body
    assert _runs() == runs and trial.session(sid).rec["run_id"] == ""
    for r in (client.get(f"/trial/s/{sid}"), client.get(f"/api/trial/s/{sid}")):
        assert r.headers["cache-control"] == "no-store"                       # ปุ่มย้อนกลับไม่ได้หน้าจากแคช
    assert "pageshow" in (PROJECT_ROOT / "redbook" / "static" / "trial.js").read_text(encoding="utf-8")
    # เล่มที่เคยเปิดผลระบบบนเครื่องนี้แล้ว: รอบใหม่ถูกบันทึกไว้ให้รายงาน
    done = start("t1", "LK2", path="r1", again=True)
    trial.lock(done, decl())
    again = start("t1", "LK2", path="r1", again=True)
    assert done in trial.session(again).rec["prior_release"].split(",")
    assert "prior_release_on_machine" in trial.status_of(trial.session(again))["flags"]
    # รหัสผู้ตรวจอื่นไม่ถูกพาไปรอบของรหัสนี้
    assert start("t1", "LK3") not in (done, again)


# ── หน้าเว็บ ─────────────────────────────────────────────────────────────────────────
def test_web_flow_neutral_text_csrf_and_forms(client):
    html = client.get("/trial").text
    assert "อัปโหลดไฟล์ PDF" in html and "เตรียมเล่มไว้ให้แล้ว" in html and "ไม่ต้องกด" in html
    assert "ระบบยังไม่เทียบจนกว่าท่านจะส่ง" in html and "เล่ม 1" in html
    assert "เล่ม 2" not in html and "เล่ม 3" not in html                     # เล่มที่ไม่อยู่บนชั้น/หน่วยที่กันไว้
    assert 'name="path" value="r1" checked' in html and 'value="r2"' in html
    tok = _token(client)
    sid = web_start(client, tok, book_id="t1", reviewer="R9", again="1", path="r2")
    page = client.get(f"/trial/s/{sid}").text
    text = re.sub(r"<[^>]+>", " ", page)
    assert "คำชี้แจงก่อนตรวจ" in page and "ฉบับ A" in page and "ฉบับ B" in page
    assert "ปีปัจจุบันต้องถูกต้องเป็นหลัก" not in text and "รบกวนดู" not in text and "ฉบับปัจจุบัน" not in text
    assert "ใบประกาศก่อนเห็นผล" in page and "ไม่ต้องกด" in text
    for tag in re.findall(r"<script[^>]*>", page):                            # ไม่มีสคริปต์ฝังในหน้า (CSP)
        assert "src=" in tag or 'type="application/json"' in tag
    pg = trial.session(sid).pages("cur")[0]
    assert client.post(f"/trial/s/{sid}/marks", data={"side": "cur", "page_no": pg, "fx": .5, "fy": .5,
                                                       "pen": "red"}).status_code in (400, 403)
    m = client.post(f"/trial/s/{sid}/marks", data={CSRF_FIELD: tok, "side": "prev", "page_no": trial.session(sid).pages("prev")[0],
                                                    "fx": .5, "fy": .5, "pen": "pin"}).json()
    assert m["pen"] == "pin" and m["side"] == "prev"
    assert client.post(f"/trial/s/{sid}/marks/{m['id']}", data={CSRF_FIELD: tok, "topic": "ค", "part": "๗", "cause": "t",
                                                                 "level": "red", "searched": "ส่วน ๗"}).json()["ok"]
    assert client.post(f"/trial/s/{sid}/marks", data={CSRF_FIELD: tok, "side": "cur", "page_no": pg, "fx": 5,
                                                       "fy": .5, "pen": "red"}).status_code == 400
    assert client.get(f"/trial/s/{sid}/page/cur/{pg}.png").content[:4] == b"\x89PNG"
    assert client.get(f"/trial/s/{sid}/page/cur/1.png").status_code == 404
    bad = client.post(f"/trial/s/{sid}/lock", data={CSRF_FIELD: tok, **decl("r2", confirm="")})
    assert bad.status_code == 400 and "ติ๊กยืนยัน" in bad.text
    r = client.post(f"/trial/s/{sid}/lock", data={CSRF_FIELD: tok, **decl("r2")}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("/result")
    res = client.get(f"/trial/s/{sid}/result").text
    assert "ประเด็นในรายการของท่าน (1)" in res and "ข้อสังเกตต้องตรวจที่ไม่ได้จับคู่" in res
    assert "ข้อมูลประกอบ" in res and "ฐานการวินิจฉัย" in res and "จบการใช้ผล" in res
    assert client.post(f"/trial/s/{sid}/issue/{m['id']}", data={CSRF_FIELD: tok, "verdict": "missed", "reason_p": "p3",
                                                                 "basis": "opened"},
                       follow_redirects=False).status_code == 303
    um = trial.result(sid).unmatched_must
    assert client.post(f"/trial/s/{sid}/finding/{um[0].id}", data={CSRF_FIELD: tok, "group": "s1"}).status_code == 400
    assert client.post(f"/trial/s/{sid}/finding/{um[0].id}", data={CSRF_FIELD: tok, "group": "s1", "basis": "enough"},
                       follow_redirects=False).status_code == 303
    assert client.post(f"/trial/s/{sid}/note", data={CSRF_FIELD: tok, "part": "๗", "note": "เห็นเพิ่ม"},
                       follow_redirects=False).status_code == 303
    assert client.post(f"/trial/s/{sid}/finish", data={CSRF_FIELD: tok}).status_code == 400   # ยังไม่ครบ ต้องมีเหตุ
    assert client.post(f"/trial/s/{sid}/finish", data={CSRF_FIELD: tok, "reason": "ทดสอบหน้าเว็บ"},
                       follow_redirects=False).status_code == 303
    survey = client.get(f"/trial/s/{sid}/survey").text
    assert 'name="q2_13"' in survey and 'name="k6"' in survey and 'name="o3_4"' in survey and 'name="c1"' not in survey
    assert "ให้ความยินยอมไว้แล้วก่อนเริ่มรอบ" in survey
    assert "๒.๗ เข้าใจได้ว่าข้อสังเกตของระบบเป็นจุดที่ต่าง" in survey
    r = client.post(f"/trial/s/{sid}/survey", data={CSRF_FIELD: tok, "q2_9": "5"},
                    follow_redirects=False)
    assert r.status_code == 303 and trial_repo.answers(sid)["q2_9"] == "5"
    dash = client.get(f"/trial/s/{sid}/dashboard").text
    assert "อัตราการพบแบบเข้ม" in dash and "ด้าน B" in dash and "ไม่ใช่ความแม่นยำของระบบ" in dash and "N0 = " in dash
    plain = re.sub(r"<[^>]+>", " ", dash)
    for word in ("ประหยัดเวลา", "แม่นยำ 100", "ผิด", "100%", "recall", "Accuracy"):
        assert word not in plain
    j = client.get(f"/trial/s/{sid}/summary.json")
    assert j.status_code == 200 and j.json()["session"] == sid


def test_cross_year_pages_name_editions_previous_and_this_year(client, cross):
    tok = _token(client)
    home = client.get("/trial").text
    assert "ข้ามปี · ฉบับปีก่อน ↔ ฉบับปีนี้" in home
    sid = web_start(client, tok, book_id="t2", again="1", path="r1")
    xp = client.get(f"/trial/s/{sid}").text
    assert "ฉบับปีก่อน" in xp and "ฉบับปีนี้" in xp and "ตัวเลขของปีเดียวกันที่ปรากฏในทั้งสองเล่ม" in xp
    assert "ฉบับ A" not in re.sub(r"<[^>]+>", " ", xp)


def test_trial_routes_use_service_layer_only():
    src = (PROJECT_ROOT / "redbook" / "web" / "trial_routes.py").read_text(encoding="utf-8")
    assert "pdfbook" not in src and "trial_repo.add_mark" not in src and "trial_repo.lock" not in src


def test_review_opens_both_editions_side_by_side_by_default(client):
    tok = _token(client)
    sid = web_start(client, tok, book_id="t1", again="1", path="r2")
    html = client.get(f"/trial/s/{sid}").text
    assert 'data-side="prev"' in html and 'data-side="cur"' in html and "is-two" in html
    assert html.count('data-donebox=') == 2                                   # ตัวช่วยตรวจหน้ามีทั้งสองฉบับเท่ากัน
    one = client.get(f"/trial/s/{sid}?prev=0").text
    assert 'data-side="prev"' not in one and "วางสองฉบับข้างกัน" in one
    assert "/page/cur/" in html.split('id="tr-data"')[1]          # ภาพหน้าถัดไปโหลดเตรียมไว้


def test_shelf_front_cache_matches_live_read(shelf, monkeypatch):
    v = pdfshelf.get("S_2570_act")
    pdfshelf._front_cache.clear()
    live = scope.front_lines(v.path, list(range(1, min(scope.FRONT_PAGES, reader.page_count(v.path)) + 1)))
    assert pdfshelf.front(v) == live                               # อ่านครั้งแรก = เท่าอ่านสด
    assert pdfshelf._front_file(v).exists()
    pdfshelf._front_cache.clear()
    monkeypatch.setattr(scope, "front_lines", lambda *a, **k: pytest.fail("ควรใช้ไฟล์ที่จำไว้"))
    assert pdfshelf.front(v) == live                               # ครั้งต่อไปจากไฟล์ ไม่อ่านซ้ำ
    pdfshelf.prewarm(["S_2570_act", "NOPE"])                       # เล่มที่ไม่มีข้ามเงียบ


def test_page_pairs_viewed_are_logged_while_reviewing(client):
    tok = _token(client)
    sid = web_start(client, tok, book_id="t1", again="1")
    s = trial.session(sid)
    c0, p0 = s.pages("cur")[0], s.pages("prev")[-1]
    client.get(f"/trial/s/{sid}")                                     # เปิดหน้าแรก = บันทึกคู่หน้าแรก
    assert client.post(f"/trial/s/{sid}/view", data={"cur": c0, "prev_page": p0}).status_code in (400, 403)
    assert client.post(f"/trial/s/{sid}/view", data={CSRF_FIELD: tok, "cur": c0, "prev_page": p0}).json()["ok"]
    client.post(f"/trial/s/{sid}/view", data={CSRF_FIELD: tok, "cur": c0, "prev_page": p0})   # ซ้ำติดกัน = ไม่บันทึก
    assert client.post(f"/trial/s/{sid}/view", data={CSRF_FIELD: tok, "cur": 1, "prev_page": 0}).status_code == 400
    vs = trial_repo.views(sid)
    assert [(v["cur_page"], v["prev_page"]) for v in vs][-1] == (c0, p0) and len(vs) == 2
    assert any(e["action"] == "trial_page_viewed" and e["object_id"] == sid for e in audit.entries(limit=50))
    trial.lock(sid, decl())
    n = len(trial_repo.views(sid))
    client.get(f"/trial/s/{sid}")                                     # หลังส่ง ไม่บันทึกเพิ่ม
    assert len(trial_repo.views(sid)) == n
    assert trial.summary(sid)["views"]["page_pairs_opened"] == 2


def test_start_returns_to_existing_work_instead_of_blank_round():
    sid = start("t1", "G9", again=True, path="r2")
    trial.add_mark(sid, "cur", trial.session(sid).pages("cur")[0], 0.4, 0.4, "red")
    assert start("t1", "G9") == sid                # กดเริ่มซ้ำ = กลับไปรอบที่มีงาน ไม่เปิดรอบว่าง
    fresh = start("t1", "G9", again=True)           # ขอเริ่มใหม่เอง = รอบใหม่ · รอบเดิมยังอยู่
    assert fresh != sid and len(trial_repo.marks(sid)) == 1
    assert trial.current_session("t1", "G9")["id"] == sid  # รอบว่างไม่บังงานเดิม


def test_book_facts_are_read_once_and_reused_identically(monkeypatch):
    v = pdfshelf.get("S_2570_act")
    sc, _ = pdfshelf.toc_scope(v, AG)
    args = (v.path, AG, str(sc.first), str(sc.last), scope.METHOD_TOC)
    pdfpair._facts_mem.clear()
    first = pdfpair._facts(*args)
    monkeypatch.setattr(pdfpair, "_facts_live", lambda *a, **k: pytest.fail("ควรใช้ผลที่จำไว้"))
    again = pdfpair._facts(*args)
    assert again[0].to_dict() == first[0].to_dict() and again[1] == first[1] and again[0] is not first[0]
    pdfpair._facts_mem.clear()                                    # จากไฟล์บนดิสก์ก็ได้ผลเดิม
    assert pdfpair._facts(*args)[0].to_dict() == first[0].to_dict()


def _page_log(sid, side, p):
    conn = connect()
    try:
        return [r["action"] for r in conn.execute("SELECT action FROM audit_log WHERE object_id = ? ORDER BY seq",
                                                  (f"{sid}/page/{side}/{p}",)).fetchall()]
    finally:
        conn.close()


def test_page_checked_is_optional_on_both_editions_and_undoable_before_lock(client):
    # กิ๊ฟถาม (26 ต.ค.): กด "ตรวจหน้านี้แล้ว" พลาดต้องย้อนได้ — "ตรวจหน้านี้แล้ว" = ดูหน้านี้ครบ ไม่ใช่ "ถูกต้อง"
    sid = start("t1", "U1", again=True, path="r2")
    s = trial.session(sid)
    p, q = s.pages("cur")[0], s.pages("prev")[0]
    trial.page_done(sid, "cur", p)
    trial.page_done(sid, "prev", q)
    assert trial.session(sid).done == {("cur", p), ("prev", q)}
    assert trial.page_undone(sid, "cur", p) is True and ("cur", p) not in trial.session(sid).done
    assert trial.page_undone(sid, "cur", p) is False                        # กดซ้ำได้ ไม่ error
    assert _page_log(sid, "cur", p) == ["trial_page_done", "trial_page_undone"]
    with pytest.raises(trial.TrialError, match="หน้าไม่ถูกต้อง"):
        trial.page_undone(sid, "cur", 99999)
    tok = _token(client)
    r = client.post(f"/trial/s/{sid}/undone", data={CSRF_FIELD: tok, "side": "prev", "page_no": q, "cur": p},
                    follow_redirects=False)
    assert r.status_code == 303 and ("prev", q) not in trial.session(sid).done
    trial.lock(sid, decl("r2"))                                             # ไม่ต้องกดครบทุกหน้า
    with pytest.raises(trial.TrialError, match="ส่งใบประกาศแล้ว"):
        trial.page_done(sid, "cur", p)
    with pytest.raises(ValueError, match="ส่งผลตรวจแล้ว"):                  # ชั้นที่เก็บก็ไม่ยอม (ตรวจในธุรกรรม)
        trial_repo.page_undone(sid, "cur", p)


def test_web_row_post_result_dimensions(client):
    tok = _token(client)
    sid = start("t1", "D1", path="r1", again=True)
    trial.lock(sid, decl())
    mid = trial.result(sid).issues[0]["id"]
    r = client.post(f"/trial/s/{sid}/row/{mid}", data={CSRF_FIELD: tok, "row_source": "post_result",
                                                      "post_dim": ["level", "part"]}, follow_redirects=False)
    assert r.status_code == 303
    m = trial.result(sid).issue_by_id[mid]
    assert trial.post_dims(m) == {"level", "part"}
    page = client.get(f"/trial/s/{sid}/result").text
    assert "จัดใหม่หลังเห็นผล: ระดับ · ส่วนของเล่ม" in page or "จัดใหม่หลังเห็นผล: ส่วนของเล่ม · ระดับ" in page


def test_web_forms_record_v03_location_and_a3(client):
    tok = _token(client)
    must, _unread = _same_year_targets()
    sid = start("t1", "W3", path="r2", again=True)
    m = _mark_on(sid, must[0])
    trial.lock(sid, decl("r2"))
    page = client.get(f"/trial/s/{sid}/result").text
    assert 'name="location"' in page and 'name="relevant_side"' in page and "บ4" not in page.split("เหตุของพบบางส่วน")[1][:400]
    bad = client.post(f"/trial/s/{sid}/issue/{m['id']}", data={CSRF_FIELD: tok, "verdict": "exact",
                                                               "finding_ids": must[0].id, "basis": "enough",
                                                               "location": "all_sides", "relevant_side": "B"})
    assert bad.status_code == 400 and "ขอบเขตที่ค้น" in bad.text
    ok = client.post(f"/trial/s/{sid}/issue/{m['id']}", data={CSRF_FIELD: tok, "verdict": "exact",
                                                              "finding_ids": must[0].id, "basis": "enough",
                                                              "location": "wrong", "relevant_side": ["A", "B"]},
                     follow_redirects=False)
    assert ok.status_code == 303 and trial.result(sid).decisions[m["id"]]["location"] == "wrong"
    page = client.get(f"/trial/s/{sid}/result").text
    assert f'id="o-{must[0].id}"' in page and "A3-อ" in page and "H1 อัตราการพบหลัก" in page
    fid = must[0].id
    dims = {f"dim_{d}": "ok" for d in trial.DIMS_BY_OBS_KIND[trial.obs_kind(must[0])]}
    r = client.post(f"/trial/s/{sid}/obs/{fid}", data={CSRF_FIELD: tok, "fidelity": "full", "basis": "enough", **dims},
                    follow_redirects=False)
    assert r.status_code == 303 and trial.result(sid).obs_eval[fid]["assertion"] == "full"



def test_v03_dashboard_hides_old_a2_card_and_marks_old_rates_as_supplementary(client):
    """Bo #43 6540982695: รอบ 0.3 ใช้ H2 · ซ่อนการ์ด A2 เดิม · อัตราการพบเดิม = ผลเสริม ไม่แข่ง H1 ·
    ข้อสังเกตที่จับคู่แล้วยังบอกเลขหน้า · รอบ 0.2 ยังแสดงการ์ดเดิม (ไม่ลบผลย้อนหลัง)"""
    tok = _token(client)
    must, _unread = _same_year_targets()
    sid = start("t1", "W4", path="r2", again=True)
    m = _mark_on(sid, must[0])
    trial.lock(sid, decl("r2"))
    plain = lambda html: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    pending = plain(client.get(f"/trial/s/{sid}/dashboard").text)                 # ตัดสินไม่ครบ
    assert "H2 ตำแหน่งถูกทุกฝั่ง" in pending and "หลักฐานชี้ตำแหน่งถูกทุกฉบับ (A2)" not in pending
    assert "ผลเสริม — อัตราการพบแบบเข้ม (พบตรง ÷ N)" in pending and "ยังไม่ครบ" in pending
    assert "0.0%" not in pending
    dash = client.get(f"/trial/s/{sid}/dashboard").text
    strict = dash[:dash.index("ผลเสริม — อัตราการพบแบบเข้ม")]
    assert strict.rsplit('class="tr-metric', 1)[1].startswith('"') and "tr-bar-fill" not in dash.split("ผลเสริม —")[1][:600]
    r = client.post(f"/trial/s/{sid}/issue/{m['id']}", data={CSRF_FIELD: tok, "verdict": "exact", "finding_ids": must[0].id,
                                                            "basis": "enough", "location": "all_sides",
                                                            "relevant_side": ["A", "B"]}, follow_redirects=False)
    assert r.status_code == 303
    page = client.get(f"/trial/s/{sid}/result").text
    linked = re.search(rf'value="{must[0].id}" checked>([^<]*)', page).group(1)
    assert linked.strip().startswith(f"หน้า {must[0].b.page} ·")
    done = plain(client.get(f"/trial/s/{sid}/dashboard").text)
    assert "H2 ตำแหน่งถูกทุกฝั่ง ในประเด็นที่พบและตัดสินตำแหน่งได้ 1/1" in done
    assert "หลักฐานชี้ตำแหน่งถูกทุกฉบับ (A2)" not in done
    old = start("t1", "W5", path="r2", again=True)                                 # รอบตามวิธีวัดผลเดิม
    trial.lock(old, decl("r2"))
    with connect() as conn:
        conn.execute("UPDATE trial_sessions SET protocol = ? WHERE id = ?", ("pdfpair-protocol-0.2.2", old))
    assert not trial.session(old).v03
    od = plain(client.get(f"/trial/s/{old}/dashboard").text)
    assert "หลักฐานชี้ตำแหน่งถูกทุกฉบับ (A2)" in od and "ผลเสริม —" not in od and "H2 ตำแหน่ง" not in od


# ── #23 dynamic SQL: ชั้นที่เก็บของหน้าผู้ตรวจใช้ SQL คงที่ (Bo #42 6433564226 ข้อ 4) ─────────────────────
_TRIAL_FILES = ("redbook/storage/trial_repo.py", "redbook/services/trial.py", "redbook/services/trial_aggregate.py",
                "redbook/web/trial_routes.py")
_DYNAMIC_SQL = re.compile(r"execute(?:many|script)?\(\s*(?:f[\"']|\"[^\"]*\"\s*[%+]|'[^']*'\s*[%+]|[^)]*\.format\()")


def test_trial_sql_is_constant_text():
    """ไม่มี execute ที่ประกอบสตริง (f-string · % · .format · +) ในไฟล์สายผู้ตรวจ — ไม่พึ่งรายการยกเว้น"""
    hits = [(rel, i, line.strip()) for rel in _TRIAL_FILES
            for i, line in enumerate((PROJECT_ROOT / rel).read_text("utf-8").splitlines(), 1)
            if _DYNAMIC_SQL.search(line)]
    assert not hits, hits
    assert _DYNAMIC_SQL.search('conn.execute(f"UPDATE t SET {x} = ?")')            # negative control ของ regex
    assert _DYNAMIC_SQL.search("conn.execute(\"SELECT %s FROM t\" % col)")
    assert _DYNAMIC_SQL.search('conn.execute("UPDATE t SET " + col + " = ?")')
    assert not _DYNAMIC_SQL.search('conn.execute("UPDATE t SET n = n + 1 WHERE id = ?", (i,))')


def test_trial_constant_sql_covers_exactly_the_declared_columns():
    cols = re.findall(r"(\w+) = COALESCE\(\?, (\w+)\)", trial_repo._UPDATE_MARK_SQL)
    assert [a for a, b in cols] == [b for a, b in cols] == list(trial_repo.MARK_FIELDS)
    assert trial_repo._UPDATE_MARK_SQL.count("?") == len(trial_repo.MARK_FIELDS) + 2
    for table, added in trial_repo._ADDED.items():
        for name, stmt in added:
            assert re.fullmatch(rf"ALTER TABLE {table} ADD COLUMN {name} (TEXT|INTEGER) NOT NULL DEFAULT ('[a-z]*'|0)",
                                stmt), stmt


def test_update_mark_binds_values_and_ignores_unknown_fields():
    """adversarial: ค่าแบบ SQL ถูกเก็บเป็นข้อความ · ชื่อฟิลด์นอก MARK_FIELDS ไม่ถูกใช้ · ฟิลด์ที่ไม่ส่ง = คงค่าเดิม ·
    แถวอื่น/รอบอื่นไม่เปลี่ยน"""
    s0 = trial.session(start("t1", "TMP", path="r2", again=True))
    book = {k: v for k, v in s0.book.items() if k != "pair_kind"}
    sid, other = (trial_repo.create_session("t1", "G", book) for _ in range(2))
    m = trial_repo.add_mark(sid, "cur", 3, .5, .5, "red", level="must")
    keep = trial_repo.add_mark(sid, "cur", 3, .2, .2, "red", level="must")
    foreign = trial_repo.add_mark(other, "cur", 3, .2, .2, "red", level="must")
    payload = "x', deleted = 1, session_id = 'zz' --"
    trial_repo.update_mark(sid, m["id"], topic=payload, note="n1", **{"id": "mk_evil", "session_id": other,
                                                                     "topic = 'p', note": "q", "fx": 9})
    got = {r["id"]: r for r in trial_repo.marks(sid, include_deleted=True)}
    assert set(got) == {m["id"], keep["id"]}
    r = got[m["id"]]
    assert (r["topic"], r["note"], r["deleted"], r["session_id"], r["fx"], r["level"], r["page"]) == \
        (payload, "n1", 0, sid, .5, "must", 3)
    assert got[keep["id"]]["topic"] == "" and got[keep["id"]]["note"] == ""
    assert trial_repo.marks(other)[0]["topic"] == "" and trial_repo.marks(other)[0]["id"] == foreign["id"]
    trial_repo.update_mark(sid, m["id"], level="", page=4)                          # ค่าว่าง ≠ ไม่ส่ง
    r = {x["id"]: x for x in trial_repo.marks(sid)}[m["id"]]
    assert (r["level"], r["page"], r["topic"]) == ("", 4, payload)
    with pytest.raises(ValueError):                                                 # รหัสของอีกรอบ = ไม่พบ
        trial_repo.update_mark(sid, foreign["id"], topic="t")


def test_lock_keeps_protocol_and_path_when_not_given():
    s0 = trial.session(start("t1", "TMP", path="r2", again=True))
    book = {k: v for k, v in s0.book.items() if k != "pair_kind"}
    a = trial_repo.create_session("t1", "G", book, path="r1", protocol="p-old")
    trial_repo.lock(a, {"marks": {}})
    assert (trial_repo.get_session(a)["path"], trial_repo.get_session(a)["protocol"]) == ("r1", "p-old")
    b = trial_repo.create_session("t1", "G", book, path="r1", protocol="p-old")
    trial_repo.lock(b, {"marks": {}}, protocol="p-new", path="r2")
    rec = trial_repo.get_session(b)
    assert (rec["path"], rec["protocol"]) == ("r2", "p-new") and rec["locked_at"]
