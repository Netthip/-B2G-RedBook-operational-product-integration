# -*- coding: utf-8 -*-
"""ทดลองตรวจเล่มสำหรับผู้ปฏิบัติงาน (#43 · ``services/trial``)

🔴 **SYNTHETIC DEMONSTRATION DATA** — เล่มจาก ``scripts/demo_redbook_book_pdf.py`` · ไม่ใช่ผลประเมิน

ชุดตรวจ

* เล่มทดสอบมาจากไฟล์ตั้งค่าของเครื่อง · เล่มที่ไม่อยู่บนชั้น/หน่วยที่กันไว้ไม่แสดง
* **ไม่มีรอบเทียบก่อนล็อก** (ผู้ตรวจไม่เห็นผลระบบก่อนวงเสร็จ) · ล็อกต้องตรวจครบทุกหน้า · ล็อกแล้วแก้จุดไม่ได้
* ภาพหน้าเปิดได้เฉพาะหน้าของหน่วยงาน · ตำแหน่งนอกหน้า/ปากกาผิด = ไม่รับ
* ระบบเสนอคู่จากตำแหน่ง แต่ไม่นับเป็น "พบ" จนผู้ตรวจยืนยัน · นับตามโปรโตคอล (พบตรง/บางส่วน/พลาด/ยกเพิ่ม)
* สรุปที่ส่งผู้วิจัยมีเฉพาะจำนวน (ไม่มีตำแหน่ง/หมายเหตุของจุดที่วง) · ทุกการเปลี่ยนลง Audit
* เว็บ: CSRF ทุก POST · ไม่มีสคริปต์ฝังในหน้า · ขั้นตอนบอกตามจริงว่าใช้จริงต้องอัปโหลดไฟล์
"""
import json
import re
import shutil
import sys
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
from redbook.services import pdfpair, pdfshelf, trial  # noqa: E402
from redbook.storage import audit, trial_repo  # noqa: E402
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD  # noqa: E402

pytestmark = pytest.mark.skipif(pdftext.product_backend() is None, reason="ไม่มี pdfplumber + pypdfium2")
AG = gen.AGENCY_1


@pytest.fixture(scope="module")
def shelf(tmp_path_factory):
    d = tmp_path_factory.mktemp("trialshelf")
    a, b = gen.build(d / "src", "draft_act")
    (d / "volumes").mkdir()
    vols, reg = [], {"volumes": {}}
    for key, src, stage in (("S_2570_draft", a, "draft"), ("S_2570_act", b, "act")):
        shutil.copy(src, d / "volumes" / f"{key}.pdf")
        vols.append({"key": key, "page": "", "url": "https://bb.go.th/x", "fiscal_year": 2570, "stage": stage,
                     "label": f"สาธิต {stage}"})
        reg["volumes"][key] = {"sha256": sha256_file(d / "volumes" / f"{key}.pdf"), "retrieved_at": "2026-10-23"}
    (d / "manifest.json").write_text(json.dumps({"volumes": vols}, ensure_ascii=False), encoding="utf-8")
    (d / "register.json").write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    books = {"books": [
        {"id": "t1", "title": "เล่ม 1", "agency": AG, "pair": "ร่าง ↔ พ.ร.บ.", "current": "S_2570_act",
         "previous": "S_2570_draft"},
        {"id": "gone", "title": "เล่ม 2", "agency": AG, "pair": "", "current": "NOPE", "previous": "S_2570_draft"},
        {"id": "held", "title": "เล่ม 3", "agency": "สถาบันวิจัยระบบสาธารณสุข", "pair": "", "current": "S_2570_act",
         "previous": "S_2570_draft"}]}
    (d / "trial_books.json").write_text(json.dumps(books, ensure_ascii=False), encoding="utf-8")
    return d


@pytest.fixture(autouse=True)
def _env(shelf, monkeypatch):
    monkeypatch.setenv(pdfshelf.SHELF_ENV, str(shelf))
    monkeypatch.delenv(trial.TRIAL_ENV, raising=False)

    # เล่มสังเคราะห์ไม่มีเลขหน้าในสารบัญ — ใช้ช่วงหน้าที่หาจากเนื้อหา (เฉพาะในเทสต์)
    def toc_scope(v, agency):
        sc = scope.find(reader.page_texts(v.path), agency)
        return sc, list(sc.pages)
    monkeypatch.setattr(pdfshelf, "toc_scope", toc_scope)


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        c.get("/trial")
        yield c


def _token(client):
    return client.cookies.get(CSRF_COOKIE)


def test_books_from_config_skip_missing_and_protected():
    assert [b.id for b in trial.books()] == ["t1"]


def _all_done(sid):
    s = trial.session(sid)
    for p in s.pages("cur"):
        trial.page_done(sid, "cur", p)


def test_no_system_run_before_lock_and_lock_needs_every_page():
    sid = trial.start("t1", "R1", again=True)
    s = trial.session(sid)
    assert s.rec["run_id"] == "" and not s.locked
    with pytest.raises(trial.TrialError, match="ส่งผลตรวจก่อน"):
        trial.result(sid)                                      # ยังไม่ล็อก = ยังไม่มีผลระบบให้ดู
    with pytest.raises(trial.TrialError, match="ตรวจหน้านี้แล้ว"):
        trial.lock(sid)
    assert trial.session(sid).rec["run_id"] == ""
    _all_done(sid)
    rid = trial.lock(sid)
    assert rid and trial.session(sid).locked and trial.session(sid).rec["run_id"] == rid
    with pytest.raises(trial.TrialError, match="ส่งผลตรวจแล้ว"):
        trial.add_mark(sid, "cur", s.pages("cur")[0], 0.5, 0.5, "red")
    acts = [e["action"] for e in audit.entries(limit=200)]
    assert "trial_started" in acts and "trial_locked" in acts and "trial_run_attached" in acts


def test_marks_validated_and_pages_restricted_to_agency():
    sid = trial.start("t1", again=True)
    s = trial.session(sid)
    first, last = s.pages("cur")[0], s.pages("cur")[-1]
    with pytest.raises(trial.TrialError, match="ปากกา"):
        trial.add_mark(sid, "cur", first, 0.5, 0.5, "blue")
    with pytest.raises(trial.TrialError, match="นอกหน้า"):
        trial.add_mark(sid, "cur", last + 1, 0.5, 0.5, "red")
    with pytest.raises(trial.TrialError, match="นอกหน้า"):
        trial.add_mark(sid, "cur", first, 1.4, 0.5, "red")
    assert trial.page_png(sid, "cur", last + 1) is None and trial.page_png(sid, "cur", 1) is None
    assert trial.page_png(sid, "cur", first)[:4] == b"\x89PNG"
    m = trial.add_mark(sid, "cur", first, 0.5, 0.5, "red")
    trial.update_mark(sid, m["id"], topic="ช", note="ตัวชี้วัดหาย")
    with pytest.raises(trial.TrialError):
        trial.update_mark(sid, m["id"], topic="X")
    trial.update_mark(sid, m["id"], delete=True)
    assert trial.session(sid).marks == []                     # ลบแล้วไม่นับ แต่แถวยังอยู่ (Audit)
    assert len(trial_repo.marks(sid, include_deleted=True)) == 1


def _mark_on(sid, f, side="cur"):
    """วางจุดกลางกรอบของข้อสังเกต (จำลองผู้ตรวจที่วงตรงจุด)"""
    s = trial.session(sid)
    sd = f.b if side == "cur" else f.a
    w, h = reader.page_size(trial._side_path(s, side), sd.page)
    x0, y0, x1, y1 = sd.bbox
    return trial.add_mark(sid, side, sd.page, ((x0 + x1) / 2) / w, ((y0 + y1) / 2) / h, "red")


def test_proposals_need_reviewer_confirmation_and_counts_follow_protocol():
    # เตรียมคำตอบของระบบจากรอบที่ล็อกแล้วรอบหนึ่ง เพื่อรู้ตำแหน่งข้อสังเกต (ผู้ตรวจจริงไม่เห็นก่อนล็อก)
    probe = trial.start("t1", again=True)
    _all_done(probe)
    v = pdfpair.view(trial.lock(probe))
    f1, f2 = [f for f in v.result.findings if not f.info and f.b.page and f.b.bbox
              and f.b.page in trial.session(probe).pages("cur")][:2]
    sid = trial.start("t1", "R2", again=True)
    m1 = _mark_on(sid, f1)
    m2 = trial.add_mark(sid, "cur", trial.session(sid).pages("cur")[0], 0.02, 0.98, "brown")  # มุมหน้า ไม่มีข้อใด
    pin = trial.add_mark(sid, "cur", trial.session(sid).pages("cur")[0], 0.5, 0.02, "pin")
    _all_done(sid)
    trial.lock(sid)
    r = trial.result(sid)
    assert r.links[m1["id"]]["finding_id"] == f1.id and r.links[m1["id"]]["verdict"] == ""
    assert r.links[m2["id"]]["finding_id"] == ""
    m = r.metrics
    assert m["pens"]["red"] == {"total": 1, "exact": 0, "partial": 0, "missed": 0, "pending": 1}  # เสนอ ≠ พบ
    assert f1.id not in {f.id for f in r.unlinked_findings}    # ข้อที่เสนอคู่แล้วไม่นับซ้ำเป็นยกเพิ่ม
    trial.decide_link(sid, m1["id"], "exact")
    trial.decide_link(sid, m2["id"], "not_same")
    with pytest.raises(trial.TrialError, match="เลือกข้อสังเกต"):
        trial.decide_link(sid, pin["id"], "exact")              # ไม่มีข้อเสนอ ต้องเลือกเอง
    trial.decide_link(sid, pin["id"], "partial", f2.id)          # ผู้ตรวจจับคู่เอง
    r = trial.result(sid)
    m = r.metrics
    assert m["pens"]["red"]["exact"] == 1 and m["pens"]["brown"]["missed"] == 1 and m["pens"]["pin"]["partial"] == 1
    extras = r.unlinked_findings
    assert f1.id not in {f.id for f in extras} and f2.id not in {f.id for f in extras}
    assert m["extras"]["pending"] == len(extras) and not r.complete
    for f in extras:
        trial.decide_extra(sid, f.id, "not_diff")
    with pytest.raises(trial.TrialError):
        trial.decide_extra(sid, f1.id, "not_diff")                # จับคู่แล้ว ไม่ใช่ข้อยกเพิ่ม
    r = trial.result(sid)
    assert r.complete and r.metrics["extras"]["not_diff"] == len(extras)
    assert all(not f.info for f in r.unlinked_findings)          # ข้อมูลประกอบไม่นับเป็นยกเพิ่ม


def test_summary_is_counts_only_and_audited():
    sid = trial.start("t1", "R3", again=True)
    m = trial.add_mark(sid, "cur", trial.session(sid).pages("cur")[0], 0.3, 0.3, "red")
    trial.update_mark(sid, m["id"], note="ข้อความลับของผู้ตรวจ")
    _all_done(sid)
    trial.lock(sid)
    trial.save_answers(sid, {"q1_1": "4", "o6_3": "ขั้นตอนเลือกหน้าเข้าใจง่าย"})
    with pytest.raises(trial.TrialError, match="1–5"):
        trial.save_answers(sid, {"q1_1": "9"})
    data = trial.summary_bytes(sid)
    body = data.decode("utf-8")
    assert "ข้อความลับของผู้ตรวจ" not in body and '"fx"' not in body and m["id"] not in body
    d = json.loads(body)
    assert d["metrics"]["pens"]["red"]["total"] == 1 and d["answers"]["q1_1"] == "4"
    assert d["book"]["current_sha256"] and d["system"]["pdfbook"]
    import hashlib
    ex = [e for e in audit.entries(limit=50) if e["action"] == "trial_summary_exported" and e["object_id"] == sid]
    assert ex and hashlib.sha256(data).hexdigest() in ex[0]["detail_json"]


def test_web_flow_csrf_and_honest_steps(client):
    html = client.get("/trial").text
    assert "อัปโหลดไฟล์ PDF" in html and "เตรียมเล่มไว้ให้แล้ว" in html
    assert "ระบบยังไม่เทียบจนกว่าคุณจะส่ง" in html and "เล่ม 1" in html and "เล่ม 3" not in html
    tok = _token(client)
    r = client.post("/trial/start", data={CSRF_FIELD: tok, "book_id": "t1", "reviewer": "R9", "again": "1"}, follow_redirects=False)
    assert r.status_code == 303
    sid = r.headers["location"].rsplit("/", 1)[-1]
    page = client.get(f"/trial/s/{sid}").text
    assert "คำชี้แจงก่อนตรวจ" in page and "ตัวชี้วัด วิสัยทัศน์ พันธกิจ" in page
    # ไม่มีสคริปต์ฝังในหน้า (CSP) — มีแต่ข้อมูล JSON
    for tag in re.findall(r"<script[^>]*>", page):
        assert "src=" in tag or 'type="application/json"' in tag
    pg = trial.session(sid).pages("cur")[0]
    assert client.post(f"/trial/s/{sid}/marks", data={"side": "cur", "page_no": pg, "fx": .5, "fy": .5,
                                                       "pen": "red"}).status_code in (400, 403)
    r = client.post(f"/trial/s/{sid}/marks", data={CSRF_FIELD: tok, "side": "cur", "page_no": pg, "fx": .5,
                                                    "fy": .5, "pen": "red"})
    assert r.status_code == 200 and r.json()["pen"] == "red"
    r = client.post(f"/trial/s/{sid}/marks", data={CSRF_FIELD: tok, "side": "cur", "page_no": pg, "fx": 5,
                                                    "fy": .5, "pen": "red"})
    assert r.status_code == 400 and "error" in r.json()
    assert client.get(f"/trial/s/{sid}/page/cur/{pg}.png").content[:4] == b"\x89PNG"
    assert client.get(f"/trial/s/{sid}/page/cur/1.png").status_code == 404
    assert client.get(f"/trial/s/{sid}/result").status_code == 409          # ยังไม่ส่ง = ยังไม่มีผลระบบ
    r = client.post(f"/trial/s/{sid}/lock", data={CSRF_FIELD: tok, "confirm": "1"})
    assert r.status_code == 400 and "ตรวจหน้านี้แล้ว" in r.text
    for p in trial.session(sid).pages("cur"):
        assert client.post(f"/trial/s/{sid}/done", data={CSRF_FIELD: tok, "side": "cur", "page_no": p},
                           follow_redirects=False).status_code == 303
    assert client.post(f"/trial/s/{sid}/lock", data={CSRF_FIELD: tok}).status_code == 400   # ไม่ติ๊กยืนยัน
    r = client.post(f"/trial/s/{sid}/lock", data={CSRF_FIELD: tok, "confirm": "1"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("/result")
    res = client.get(f"/trial/s/{sid}/result").text
    assert "จุดที่คุณวง (1 จุด)" in res and "ข้อที่ระบบยกเพิ่ม" in res
    survey = client.get(f"/trial/s/{sid}/survey").text
    assert "ขั้นตอนไหนยาก หรืออยากให้ปรับอะไร" in survey and 'name="q6_1"' in survey
    r = client.post(f"/trial/s/{sid}/survey", data={CSRF_FIELD: tok, "q6_1": "5"}, follow_redirects=False)
    assert r.status_code == 303 and trial_repo.answers(sid)["q6_1"] == "5"
    dash = client.get(f"/trial/s/{sid}/dashboard").text
    assert "จุดสำคัญ (แดง) ที่ระบบจับได้" in dash and "ไม่ใช่ร้อยละความแม่นยำ" in dash
    for word in ("ประหยัดเวลา", "แม่นยำ 100", "ผิด"):
        assert word not in re.sub(r"<[^>]+>", " ", dash).replace("ไม่ใช่ร้อยละความแม่นยำ", "")
    j = client.get(f"/trial/s/{sid}/summary.json")
    assert j.status_code == 200 and j.json()["session"] == sid


def test_trial_routes_use_service_layer_only():
    src = (PROJECT_ROOT / "redbook" / "web" / "trial_routes.py").read_text(encoding="utf-8")
    assert "pdfbook" not in src and "trial_repo.add_mark" not in src


def test_review_opens_both_editions_side_by_side_by_default(client):
    tok = _token(client)
    r = client.post("/trial/start", data={CSRF_FIELD: tok, "book_id": "t1", "again": "1"}, follow_redirects=False)
    sid = r.headers["location"].rsplit("/", 1)[-1]
    html = client.get(f"/trial/s/{sid}").text
    assert 'data-side="prev"' in html and 'data-side="cur"' in html and "is-two" in html
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
    sid = client.post("/trial/start", data={CSRF_FIELD: tok, "book_id": "t1", "again": "1"},
                      follow_redirects=False).headers["location"].rsplit("/", 1)[-1]
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
    for p in s.pages("cur"):
        trial.page_done(sid, "cur", p)
    trial.lock(sid)
    n = len(trial_repo.views(sid))
    client.get(f"/trial/s/{sid}")                                     # หลังส่งผล ไม่บันทึกเพิ่ม
    assert len(trial_repo.views(sid)) == n
    assert trial.summary(sid)["views"]["page_pairs_opened"] == 2


def test_start_returns_to_existing_work_instead_of_blank_round():
    sid = trial.start("t1", "G", again=True)
    trial.add_mark(sid, "cur", trial.session(sid).pages("cur")[0], 0.4, 0.4, "red")
    assert trial.start("t1") == sid                     # กดเริ่มซ้ำ = กลับไปรอบที่มีงาน ไม่เปิดรอบว่าง
    assert trial.book_status()["t1"]["sid"] in {sid} | {s["id"] for s in trial_repo.sessions() if s["locked_at"]}
    fresh = trial.start("t1", again=True)                # ขอเริ่มใหม่เอง = รอบใหม่ · รอบเดิมยังอยู่
    assert fresh != sid and len(trial_repo.marks(sid)) == 1
    assert trial.current_session("t1")["id"] != fresh     # รอบว่างไม่บังงานเดิม


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


def _page_log(sid, p):
    from redbook.storage.db import connect
    conn = connect()
    try:
        return [r["action"] for r in conn.execute("SELECT action FROM audit_log WHERE object_id = ? ORDER BY seq",
                                                  (f"{sid}/page/cur/{p}",)).fetchall()]
    finally:
        conn.close()


def test_page_done_can_be_undone_before_lock_only():
    # กิ๊ฟถาม (26 ต.ค.): กด "ตรวจหน้านี้แล้ว" พลาดต้องย้อนได้ — "ตรวจหน้านี้แล้ว" = ดูหน้านี้ครบ ไม่ใช่ "ถูกต้อง"
    sid = trial.start("t1", "U1", again=True)
    p = trial.session(sid).pages("cur")[0]
    trial.page_done(sid, "cur", p)
    assert trial.page_undone(sid, "cur", p) is True and ("cur", p) not in trial.session(sid).done
    assert trial.page_undone(sid, "cur", p) is False                        # กดซ้ำได้ ไม่ error
    assert _page_log(sid, p) == ["trial_page_done", "trial_page_undone"]    # ย้อนดูได้ว่าเคยกดแล้วยกเลิก
    with pytest.raises(trial.TrialError, match="หน้าไม่ถูกต้อง"):
        trial.page_undone(sid, "cur", 99999)
    _all_done(sid)
    trial.lock(sid)
    with pytest.raises(trial.TrialError, match="ส่งผลตรวจแล้ว"):
        trial.page_undone(sid, "cur", p)
    assert ("cur", p) in trial.session(sid).done
    with pytest.raises(ValueError, match="ส่งผลตรวจแล้ว"):                  # ชั้นที่เก็บก็ไม่ยอม (ตรวจในธุรกรรม)
        trial_repo.page_undone(sid, "cur", p)


def test_lock_rechecks_every_page_inside_the_transaction(monkeypatch):
    sid = trial.start("t1", "U2", again=True)
    _all_done(sid)
    p = trial.session(sid).pages("cur")[0]
    real = trial_repo.lock

    def undo_while_locking(sid_, counts, **kw):         # จำลองกด "ยกเลิก" แทรกหลังชั้นบริการตรวจครบแล้ว
        trial_repo.page_undone(sid_, "cur", p)
        return real(sid_, counts, **kw)
    monkeypatch.setattr(trial_repo, "lock", undo_while_locking)
    with pytest.raises(trial.TrialError, match="ยังไม่ได้กด"):
        trial.lock(sid)
    s = trial.session(sid)
    assert not s.locked and s.rec["run_id"] == ""                       # ไม่ล็อก ไม่มีผลระบบ
