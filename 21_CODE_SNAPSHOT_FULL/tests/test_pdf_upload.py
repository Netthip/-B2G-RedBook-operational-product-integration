# -*- coding: utf-8 -*-
"""อัปโหลด PDF จากเครื่อง (Bo แนะนำ · กิ๊ฟเลือก 28 ต.ค. 2569) + ด่านกันหน่วยงานในชุดประเมิน (#44 G4)

1. ด่านของ #23 ที่เพิ่ม: โครงสร้าง PDF (เสีย/มีรหัสผ่าน) · จำกัดจำนวนหน้า · ไฟล์ไม่ผ่าน = ไม่มีไฟล์ค้างในที่เก็บ +
   บันทึกเหตุการณ์ · แหล่งที่มาเป็น http(s) เท่านั้น ไม่ดึง · เส้นทางในเครื่องในลิงก์ถูกกลบ
2. ด่านชุดประเมิน: ปฏิเสธทุกทางที่เริ่มรอบ (ชั้นเล่ม · บริการ · หน้าเดิม · API อัปโหลด) และซ่อนจากรายชื่อ ·
   ปลดล็อกได้เฉพาะรุ่นตัวสกัดที่ระบุ · ไม่มีไฟล์รายชื่อ = รายงานว่ายังไม่ตั้งค่า
3. API อัปโหลดของ /r: CSRF ก่อนอ่าน body · อัปโหลด A/B → เริ่มรอบ (ช่วงหน้าจากสารบัญ)

🔴 SYNTHETIC DEMONSTRATION DATA — ชั้นเล่มสังเคราะห์ชุดเดียวกับ ``test_trial.py``
"""
import io
import json

import pytest

from test_trial import AG, _env, client, shelf  # noqa: F401  (fixture ร่วม)
from redbook import config, eval_guard
from redbook.evidence import pdftext
from redbook.pdfbook import reader, scope
from redbook.services import pdf_upload, pdfpair as svc, pdfshelf
from redbook.storage import files as filestore, pdfpair_repo, source_pdfs
from redbook.storage.db import connect
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD

pytestmark = pytest.mark.skipif(pdftext.product_backend() is None, reason="ไม่มี pdfplumber + pypdfium2")


def _book(shelf, key="S_2570_draft"):
    return shelf / "volumes" / f"{key}.pdf"


def _stored_count():
    return len(list(config.UPLOAD_DIR.glob("*")))


def _events(name):
    conn = connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM security_events WHERE event = ?", (name,)).fetchone()[0]
    finally:
        conn.close()


@pytest.fixture()
def toc_stub(monkeypatch):
    """เล่มสังเคราะห์ไม่มีเลขหน้าในสารบัญ — หาช่วงหน้าจากเนื้อหา (เฉพาะในเทสต์ · เหมือน _env ของ test_trial)"""
    def stub(path, _sha, agency):
        sc = scope.find(reader.page_texts(path), agency)
        return sc, list(sc.pages)
    monkeypatch.setattr(pdfshelf, "toc_scope_of_file", stub)


@pytest.fixture()
def guard(tmp_path, monkeypatch):
    p = tmp_path / "eval_guard.json"
    monkeypatch.setenv(eval_guard.GUARD_ENV, str(p))

    def write(agencies, unlocked=""):
        p.write_text(json.dumps({"agencies": agencies, "unlocked_for_pdfbook": unlocked}, ensure_ascii=False),
                     encoding="utf-8")
    return write


# ── 1. ด่านอัปโหลด ─────────────────────────────────────────────────────────────────────────────────
def test_valid_pdf_is_accepted_with_page_count(shelf):
    with open(_book(shelf), "rb") as fh:
        stored, pages = pdf_upload.accept_pdf(fh, "book.pdf")
    assert pages == reader.page_count(_book(shelf)) and stored.kind == "pdf" and len(stored.sha256) == 64
    filestore.delete_stored(stored.stored_name)


@pytest.mark.parametrize("kind", ["corrupt", "encrypted", "too_many_pages", "not_pdf"])
def test_rejected_files_leave_nothing_stored_and_are_logged(shelf, tmp_path, monkeypatch, kind):
    data = _book(shelf).read_bytes()
    if kind == "corrupt":
        data = b"%PDF-1.7\n" + b"\x00garbage" * 400
    elif kind == "encrypted":
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        data = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    elif kind == "too_many_pages":
        monkeypatch.setattr(pdf_upload, "MAX_PDF_PAGES", 1)
    else:
        data = b"PK\x03\x04 not a pdf" * 50
    event = {"corrupt": "pdf_unreadable", "encrypted": "pdf_unreadable", "too_many_pages": "pdf_too_many_pages"}
    before, ev_before = _stored_count(), _events(event.get(kind, "x"))
    with pytest.raises(pdf_upload.UploadError) as e:
        pdf_upload.accept_pdf(io.BytesIO(data), "x.pdf")
    assert _stored_count() == before                       # ไม่มีไฟล์ค้าง
    assert "\\" not in str(e.value) and "/" not in str(e.value)    # ข้อความไม่มี path
    if kind in event:
        assert e.value.event == event[kind] and _events(event[kind]) == ev_before + 1
    assert "Excel" not in str(e.value)                     # สาย PDF ไม่พูดถึง Excel


@pytest.mark.parametrize("url, ok", [("", True), ("https://www.bb.go.th/topic3.php?gid=860", True),
                                     ("http://bb.go.th/x.pdf", True), ("javascript:alert(1)", False),
                                     ("ftp://x/y.pdf", False), ("https://a b", False), ("file:///C:/x.pdf", False),
                                     ("https://" + "x" * 1000, False)])
def test_source_url_is_recorded_only_never_fetched(url, ok):
    if ok:
        assert pdf_upload.clean_source_url(url) == url
    else:
        with pytest.raises(pdf_upload.UploadError):
            pdf_upload.clean_source_url(url)


# ── 2. ด่านชุดประเมิน ──────────────────────────────────────────────────────────────────────────────
def test_guard_not_configured_is_reported_not_silent(guard):
    st = eval_guard.status()
    assert st["configured"] is False and not eval_guard.is_blocked(AG)


def test_eval_agency_is_refused_everywhere_and_hidden(guard, client, monkeypatch):
    guard([AG])
    assert eval_guard.status() == {"configured": True, "agencies": 1, "unlocked": False,
                                   "pdfbook": eval_guard.status()["pdfbook"]}
    before = _events("eval_agency_blocked")
    with pytest.raises(pdfshelf.ShelfError, match="ชุดประเมิน"):
        pdfshelf.start("S_2570_draft", "S_2570_act", AG)
    with pytest.raises(svc.PairError, match="ชุดประเมิน"):
        svc.run("prj_any", agency=AG)
    h = {"X-CSRF-Token": client.get("/api/csrf").json()["token"]}
    r = client.post("/api/pdfpair/shelf/start", json={"a": "S_2570_draft", "b": "S_2570_act", "agency": AG}, headers=h)
    assert r.status_code == 400 and "ชุดประเมิน" in r.json()["error"]
    monkeypatch.setattr(pdfshelf, "_agency_names", lambda _f: [AG, "สำนักงานสาธิตอื่นที่ไม่เกี่ยว"])
    v = pdfshelf.get("S_2570_act")
    pdfshelf._agencies_cache.pop(v.sha256, None)
    assert pdfshelf.agencies(v) == ["สำนักงานสาธิตอื่นที่ไม่เกี่ยว"]
    pdfshelf._agencies_cache.pop(v.sha256, None)
    assert _events("eval_agency_blocked") >= before + 3
    conn = connect()
    try:
        rows = [r[0] for r in conn.execute("SELECT detail_json FROM security_events WHERE event = 'eval_agency_blocked'")]
    finally:
        conn.close()
    assert not any(AG in r for r in rows)                  # บันทึกไม่ใส่ชื่อหน่วยงาน


def test_unlock_only_for_the_frozen_pdfbook_version(guard):
    from redbook.pdfbook import PDFBOOK_VERSION
    guard([AG], unlocked="pdfbook-0.0.0")
    assert eval_guard.is_blocked(AG)                        # รุ่นอื่น = ยังปิด
    guard([AG], unlocked=PDFBOOK_VERSION)
    assert not eval_guard.is_blocked(AG) and eval_guard.status()["unlocked"] is True


# ── 3. API อัปโหลดของ /r ────────────────────────────────────────────────────────────────────────────
def _post_file(client, path, side, pid="", token=None, source_url=""):
    h = {"X-CSRF-Token": token} if token is not None else {}
    data = {"side": side, **({"project_id": pid} if pid else {}), **({"source_url": source_url} if source_url else {})}
    with open(path, "rb") as fh:
        return client.post("/api/pdfpair/uploads", data=data, files={"file": (path.name, fh, "application/pdf")},
                           headers=h)


def test_upload_needs_csrf_before_anything_is_stored(client, shelf):
    before = _stored_count()
    for tok in (None, "not-the-cookie"):
        r = _post_file(client, _book(shelf), "A", token=tok)
        assert (r.status_code, r.json()["code"]) == (403, "csrf")
    assert _stored_count() == before


def test_upload_both_editions_then_run_from_the_toc(client, shelf, toc_stub, guard):
    tok = client.get("/api/csrf").json()["token"]
    url = "https://www.bb.go.th/download.php?f=C%3A%5CUsers%5Czqcanary%5Ca.pdf"
    a = _post_file(client, _book(shelf, "S_2570_draft"), "A", token=tok, source_url=url).json()
    assert a["side"] == "A" and a["pages"] > 0 and a["sides_ready"] == ["A"] and isinstance(a["agencies"], list)
    pid = a["project_id"]
    b = _post_file(client, _book(shelf, "S_2570_act"), "B", pid=pid, token=tok).json()
    assert b["project_id"] == pid and b["sides_ready"] == ["A", "B"]
    kept = source_pdfs.for_project(pid)["A"]["source_url"]
    assert "zqcanary" not in kept and kept.startswith("https://www.bb.go.th/download.php?f=")
    guard([AG])
    r = client.post(f"/api/pdfpair/uploads/{pid}/run", json={"agency": AG}, headers={"X-CSRF-Token": tok})
    assert r.status_code == 400 and "ชุดประเมิน" in r.json()["error"]          # ชุดประเมิน = ปฏิเสธ
    guard([])
    r = client.post(f"/api/pdfpair/uploads/{pid}/run", json={"agency": AG}, headers={"X-CSRF-Token": tok})
    assert r.status_code == 200, r.text
    v = svc.view(r.json()["rid"])
    assert v is not None and v.run["project_id"] == pid and v.run["scope"]["A"]["pages_read"]


def test_upload_run_requires_both_sides(client, shelf):
    tok = client.get("/api/csrf").json()["token"]
    pid = _post_file(client, _book(shelf), "A", token=tok).json()["project_id"]
    r = client.post(f"/api/pdfpair/uploads/{pid}/run", json={"agency": AG}, headers={"X-CSRF-Token": tok})
    assert r.status_code == 400 and "ทั้งฉบับ A และฉบับ B" in r.json()["error"]


def test_old_upload_page_uses_the_same_gates(client, shelf):
    client.get("/")
    tok = client.cookies.get(CSRF_COOKIE)
    r = client.post("/projects/new", follow_redirects=False,
                    data={CSRF_FIELD: tok, "name": "อัปโหลดเสีย", "mode": "before_after_reduction"})
    pid = r.headers["location"].rsplit("/", 1)[-1]
    before = _stored_count()
    r = client.post(f"/projects/{pid}/source-pdf", follow_redirects=False,
                    data={CSRF_FIELD: tok, "side": "A"},
                    files={"upload": ("bad.pdf", io.BytesIO(b"%PDF-1.7\n" + b"\x00" * 3000), "application/pdf")})
    assert r.status_code == 400 and _stored_count() == before and source_pdfs.for_project(pid) == {}


# ── 4. กันสร้างรอบซ้ำ (รอบ 2 U2: สองรอบห่าง 1 วินาที ความเห็นแยกสองรอบ) ─────────────────────────────────
def _run_count():
    conn = connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM pdfpair_runs").fetchone()[0]
    finally:
        conn.close()


def test_same_start_twice_returns_the_same_run(client):
    first = pdfshelf.start("S_2570_draft", "S_2570_act", AG)
    n = _run_count()
    assert pdfshelf.start("S_2570_draft", "S_2570_act", AG) == first and _run_count() == n
    h = {"X-CSRF-Token": client.get("/api/csrf").json()["token"]}
    r = client.post("/api/pdfpair/shelf/start", json={"a": "S_2570_draft", "b": "S_2570_act", "agency": AG}, headers=h)
    assert r.json()["rid"] == first[1] and _run_count() == n                  # ผ่าน API ก็ได้รอบเดิม


def test_double_click_at_the_same_moment_makes_one_run(client, monkeypatch):
    import threading
    real, gate = pdfshelf._start, threading.Barrier(2)

    def slow(*a, **k):                    # ให้คำขอที่สองมาถึงระหว่างที่คำขอแรกยังสร้างอยู่แน่นอน
        gate.wait(timeout=10)
        return real(*a, **k)
    monkeypatch.setattr(pdfshelf, "_start", slow)
    monkeypatch.setattr(pdfshelf, "_once_slots", {})
    n, out = _run_count(), []
    t = threading.Thread(target=lambda: out.append(pdfshelf.start("S_2570_draft", "S_2570_act", AG)))
    t.start()
    gate.wait(timeout=10)                 # คำขอแรกเข้า _start แล้ว
    out.append(pdfshelf.start("S_2570_draft", "S_2570_act", AG))
    t.join(30)
    assert len(out) == 2 and out[0] == out[1] and _run_count() == n + 1


def test_new_run_when_window_passed_old_run_gone_or_other_agency(client, monkeypatch):
    pid, rid = pdfshelf.start("S_2570_draft", "S_2570_act", AG)
    conn = connect()
    try:
        conn.execute("DELETE FROM pdfpair_runs WHERE id = ?", (rid,))
        conn.commit()
    finally:
        conn.close()
    assert pdfshelf.start("S_2570_draft", "S_2570_act", AG)[1] != rid          # รอบเดิมหายไป = สร้างใหม่
    again = pdfshelf.start("S_2570_draft", "S_2570_act", AG)
    monkeypatch.setattr(pdfshelf, "START_DEDUPE_S", -1.0)   # นาฬิกา Windows ละเอียด ~15 ms
    assert pdfshelf.start("S_2570_draft", "S_2570_act", AG) != again          # พ้นช่วงเวลา = สร้างใหม่


def test_failed_start_is_not_remembered(client, monkeypatch):
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise pdfshelf.ShelfError("ล้มกลางทาง")
    monkeypatch.setattr(pdfshelf, "_start", boom)
    monkeypatch.setattr(pdfshelf, "_once_slots", {})
    for _ in range(2):
        with pytest.raises(pdfshelf.ShelfError):
            pdfshelf.start("S_2570_draft", "S_2570_act", AG)
    assert len(calls) == 2


def test_uploaded_run_dedupes_until_a_file_changes(client, shelf, toc_stub, guard):
    tok = client.get("/api/csrf").json()["token"]
    h = {"X-CSRF-Token": tok}
    pid = _post_file(client, _book(shelf, "S_2570_draft"), "A", token=tok).json()["project_id"]
    _post_file(client, _book(shelf, "S_2570_act"), "B", pid=pid, token=tok)
    r1 = client.post(f"/api/pdfpair/uploads/{pid}/run", json={"agency": AG}, headers=h).json()["rid"]
    r2 = client.post(f"/api/pdfpair/uploads/{pid}/run", json={"agency": AG}, headers=h).json()["rid"]
    assert r1 == r2
    _post_file(client, _book(shelf, "S_2570_draft"), "B", pid=pid, token=tok)   # เปลี่ยนไฟล์ฉบับ B
    r3 = client.post(f"/api/pdfpair/uploads/{pid}/run", json={"agency": AG}, headers=h)
    assert r3.status_code == 200 and r3.json()["rid"] != r1


@pytest.mark.parametrize("data", [b"x", b"PK\x03\x04" + b"\x00" * 64, b"<html>not a pdf</html>"])
def test_non_pdf_upload_says_pdf_not_excel(client, data):
    tok = client.get("/api/csrf").json()["token"]
    r = client.post("/api/pdfpair/uploads", data={"side": "A"}, files={"file": ("x.pdf", io.BytesIO(data), "application/pdf")},
                    headers={"X-CSRF-Token": tok})
    assert r.status_code == 400 and r.json()["error"] == pdf_upload.NOT_PDF_MESSAGE


# ── 5. ช่องข้ามด่าน: ช่วงหน้าที่กำหนดเอง (Bo REVIEW #44 6462457757) ────────────────────────────────────
@pytest.fixture()
def manual_pid(client, shelf):
    tok = client.get("/api/csrf").json()["token"]
    pid = _post_file(client, _book(shelf, "S_2570_draft"), "A", token=tok).json()["project_id"]
    _post_file(client, _book(shelf, "S_2570_act"), "B", pid=pid, token=tok)
    return pid


def _range(shelf, key, agency):
    sc = scope.find(reader.page_texts(_book(shelf, key)), agency)
    return str(sc.first), str(sc.last)


def _manual(pid, shelf, agency_for_range, agency=""):
    (af, al), (bf, bl) = _range(shelf, "S_2570_draft", agency_for_range), _range(shelf, "S_2570_act", agency_for_range)
    return svc.run(pid, agency=agency, a_first=af, a_last=al, b_first=bf, b_last=bl)


def test_manual_range_without_agency_is_refused_while_locked(manual_pid, shelf, guard):
    import demo_redbook_book_pdf as gen
    guard([AG])
    before = _events("eval_range_without_agency")
    for target in (AG, gen.AGENCY_2):              # ปฏิเสธทั้งช่วงของหน่วยในชุดประเมินและหน่วยอื่น — ยืนยันไม่ได้
        with pytest.raises(svc.PairError, match="ต้องระบุหน่วยงาน"):
            _manual(manual_pid, shelf, target)
    assert _events("eval_range_without_agency") == before + 2


def test_manual_range_pointing_at_eval_pages_under_another_name_is_refused(manual_pid, shelf, toc_stub, guard):
    import demo_redbook_book_pdf as gen
    guard([AG])
    with pytest.raises(svc.PairError, match="ตามสารบัญ"):
        _manual(manual_pid, shelf, AG, agency=gen.AGENCY_2)          # ชื่อผ่านด่าน แต่ช่วงหน้าเป็นของ AG
    assert _events("eval_range_unverified") >= 1


def test_manual_range_inside_an_allowed_agency_runs(manual_pid, shelf, toc_stub, guard):
    import demo_redbook_book_pdf as gen
    guard([AG])
    rid = _manual(manual_pid, shelf, gen.AGENCY_2, agency=gen.AGENCY_2)  # ชุดพัฒนาที่อนุญาต
    assert svc.view(rid).run["agency"] == gen.AGENCY_2


def test_manual_range_refused_when_toc_cannot_confirm(manual_pid, shelf, guard, monkeypatch):
    import demo_redbook_book_pdf as gen

    def no_toc(*_a):
        raise pdfshelf.ShelfError("ไม่พบสารบัญ")
    monkeypatch.setattr(pdfshelf, "toc_scope_of_file", no_toc)
    guard([AG])
    with pytest.raises(svc.PairError, match="ตามสารบัญ"):
        _manual(manual_pid, shelf, gen.AGENCY_2, agency=gen.AGENCY_2)


def test_manual_range_without_agency_still_works_when_not_locked(manual_pid, shelf, guard):
    import demo_redbook_book_pdf as gen
    rid = _manual(manual_pid, shelf, gen.AGENCY_2)                 # ไม่มีไฟล์รายชื่อ = ไม่ล็อก (รายงานใน /api/lane)
    assert svc.view(rid) is not None
    from redbook.pdfbook import PDFBOOK_VERSION
    guard([AG], unlocked=PDFBOOK_VERSION)                           # ปลดล็อกแล้ว
    assert svc.view(_manual(manual_pid, shelf, AG)) is not None


def test_remembered_run_never_skips_a_guard_locked_afterwards(client, guard):
    """รอบที่จำไว้ (กันกดซ้ำ) ต้องไม่ข้ามด่าน — ล็อกรายชื่อหลังสร้างรอบ แล้วกดซ้ำภายในช่วงเวลา = ปฏิเสธ"""
    pdfshelf.start("S_2570_draft", "S_2570_act", AG)
    guard([AG])
    with pytest.raises(pdfshelf.ShelfError, match="ชุดประเมิน"):
        pdfshelf.start("S_2570_draft", "S_2570_act", AG)


# ── 6. pdfbook-0.5.3: สารบัญใช้ไม่ได้ → ช่วงหน้าจากชื่อหน่วยงานบนหน้าเริ่ม (หน้าบ้านทดสอบอัปโหลด 29 ต.ค.) ─────────────
def test_toc_failure_falls_back_to_the_agency_start_page_and_records_the_method(client, shelf, guard, monkeypatch):
    def no_toc(*_a):
        raise pdfshelf.ShelfError("สารบัญใช้ไม่ได้")
    monkeypatch.setattr(pdfshelf, "toc_scope_of_file", no_toc)
    tok = client.get("/api/csrf").json()["token"]
    pid = _post_file(client, _book(shelf, "S_2570_draft"), "A", token=tok).json()["project_id"]
    _post_file(client, _book(shelf, "S_2570_act"), "B", pid=pid, token=tok)
    guard([])                                               # รายชื่อว่าง = ไม่ล็อก · ตอนล็อกอยู่ในเทสต์ถัดไป
    rid = client.post(f"/api/pdfpair/uploads/{pid}/run", json={"agency": AG}, headers={"X-CSRF-Token": tok}).json()["rid"]
    sc = svc.view(rid).run["scope"]
    want = scope.find(reader.page_texts(_book(shelf, "S_2570_draft")), AG)
    assert (sc["A"]["first"], sc["A"]["last"], sc["A"]["method"]) == (want.first, want.last, scope.METHOD_NAME)
    assert sc["A"]["pages_read"] == list(range(1, reader.page_count(_book(shelf, "S_2570_draft")) + 1))  # ตามจริง


def test_name_scope_runs_while_the_eval_guard_is_locked(client, shelf, guard, monkeypatch):
    """ช่วงที่ระบบหาเองจากชื่อหน่วยงาน ไม่ใช่ช่วงที่ผู้ใช้กรอก — ด่านช่วงหน้าไม่ปฏิเสธ (ชื่อผ่านด่านชื่อแล้ว)"""
    import demo_redbook_book_pdf as gen
    monkeypatch.setattr(pdfshelf, "toc_scope_of_file", lambda *_a: (_ for _ in ()).throw(pdfshelf.ShelfError("x")))
    tok = client.get("/api/csrf").json()["token"]
    pid = _post_file(client, _book(shelf, "S_2570_draft"), "A", token=tok).json()["project_id"]
    _post_file(client, _book(shelf, "S_2570_act"), "B", pid=pid, token=tok)
    guard([AG])
    r = client.post(f"/api/pdfpair/uploads/{pid}/run", json={"agency": gen.AGENCY_2}, headers={"X-CSRF-Token": tok})
    assert r.status_code == 200, r.text
    assert svc.view(r.json()["rid"]).run["scope"]["B"]["method"] == scope.METHOD_NAME


def test_when_neither_toc_nor_name_works_the_message_names_the_file_not_a_dead_end(client, shelf, monkeypatch):
    monkeypatch.setattr(pdfshelf, "toc_scope_of_file", lambda *_a: (_ for _ in ()).throw(pdfshelf.ShelfError("ไม่พบ")))
    tok = client.get("/api/csrf").json()["token"]
    pid = _post_file(client, _book(shelf, "S_2570_draft"), "A", token=tok).json()["project_id"]
    _post_file(client, _book(shelf, "S_2570_act"), "B", pid=pid, token=tok)
    r = client.post(f"/api/pdfpair/uploads/{pid}/run", json={"agency": "หน่วยงานที่ไม่มีในเล่มนี้เลย"},
                    headers={"X-CSRF-Token": tok})
    err = r.json()["error"]
    assert r.status_code == 400 and "ฉบับ A" in err and "กำหนดช่วงหน้าเอง" not in err


# ── เลขหน้าที่พิมพ์ (หน้าบ้าน 30 ต.ค.: ผู้ปฏิบัติงานอ้างเลขบนหัวกระดาษ ไม่ใช่เลขหน้า PDF) ──────────────────────
def test_printed_offset_reaches_the_api_only_for_toc_ranges_and_changes_no_result(client, shelf, guard, monkeypatch):
    import hashlib
    draft = hashlib.sha256(_book(shelf, "S_2570_draft").read_bytes()).hexdigest()

    def stub(path, sha, agency):
        sc = scope.find(reader.page_texts(path), agency)
        if sha == draft:
            sc = scope.Scope(sc.first, sc.last, scope.METHOD_TOC, agency, printed_offset=7)
        return sc, list(sc.pages)
    monkeypatch.setattr(pdfshelf, "toc_scope_of_file", stub)
    tok = client.get("/api/csrf").json()["token"]
    pid = _post_file(client, _book(shelf, "S_2570_draft"), "A", token=tok).json()["project_id"]
    _post_file(client, _book(shelf, "S_2570_act"), "B", pid=pid, token=tok)
    guard([])
    rid = client.post(f"/api/pdfpair/uploads/{pid}/run", json={"agency": AG}, headers={"X-CSRF-Token": tok}).json()["rid"]
    sides = client.get(f"/api/pdfpair/runs/{rid}").json()["run"]["sides"]
    a_ofs, b_ofs = sides["A"]["printed_offset"], sides["B"]["printed_offset"]
    assert (a_ofs, b_ofs) == (7, None)                    # ช่วงจากสารบัญ = ค่า · วิธีอื่น = null ไม่เดา
    sc = svc.view(rid).run["scope"]
    plain = svc.run(pid, agency=AG, a_first=str(sc["A"]["first"]), a_last=str(sc["A"]["last"]),
                    b_first=str(sc["B"]["first"]), b_last=str(sc["B"]["last"]),
                    range_method={s: sc[s]["method"] for s in ("A", "B")})
    assert pdfpair_repo.get_run(plain)["result"] == pdfpair_repo.get_run(rid)["result"]   # แสดงผลเท่านั้น
    assert client.get(f"/api/pdfpair/runs/{plain}").json()["run"]["sides"]["A"]["printed_offset"] is None
