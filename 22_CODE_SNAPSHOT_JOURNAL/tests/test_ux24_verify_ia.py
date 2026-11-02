# -*- coding: utf-8 -*-
"""#24 — IA รอบใหม่ "ผู้ช่วยตรวจงบ": Overview 3 คำถาม → รายการ → เทียบ A | B → หลักฐานต้นฉบับ

สิ่งที่ชุดนี้ล็อกไว้ (ตามโจทย์ #24 รอบ verification flow)

* หน้าแรกสั้น — มีแค่ เงิน · ตัวชี้วัดและรายการ · ความต่างระหว่างเอกสาร (+ แถบที่มาเอกสาร)
  ไม่มีตาราง ไม่มีศัพท์เครื่องยนต์ (MATCHED/UNMAPPED/CANDIDATE/confidence/รหัสชนิด)
* ยอดรวมมาจาก *แถวยอดรวมในเอกสาร* เท่านั้น — ระบบไม่บวกผลต่างหลายรายการเอง
* ทุกข้อสังเกตตกอยู่ในรายการเดียวเสมอ (ไม่ทิ้งเงียบ)
* หน้าเทียบ A | B เปิดแถวจริงในไฟล์ที่ใช้ตรวจ — เฉพาะเมื่อ SHA-256 ตรงกับรอบตรวจ
* ไฮไลต์เฉพาะส่วนที่ต่าง (80 → 85 · "และ AI")

🔴 **SYNTHETIC DEMONSTRATION DATA** — ใช้ ``scripts/demo_ao_workbooks.py`` (แต่งขึ้นทั้งหมด)
"""
import os
import re
import stat
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import demo_ao_workbooks as gen  # noqa: E402

from redbook.app import create_app  # noqa: E402
from redbook.services import source_rows  # noqa: E402
from redbook.services import t1b as svc  # noqa: E402
from redbook.services import verify_view as vv  # noqa: E402
from redbook.storage import repository as repo  # noqa: E402
from redbook.storage import files as filestore  # noqa: E402
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD  # noqa: E402

ENGINE_WORDS = ("MATCHED", "UNMAPPED", "CANDIDATE", "confidence", "CONFIDENCE",
                "MATERIAL_DIFF", "AMOUNT_DECREASED", "ROW_ADDED", "INCOMPLETE")


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    return gen.build(tmp_path_factory.mktemp("ia_pair"))


@pytest.fixture(scope="module")
def view(pair):
    return svc.run_from_workbooks(*pair, run_id="IA-VIEW")


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def run(client, pair):
    """เดินเส้นทางจริงผ่าน HTTP: ตั้งงาน → ใส่ไฟล์ → ให้ระบบหาความต่าง"""
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post("/projects/new", follow_redirects=False, data={
        CSRF_FIELD: token, "name": "IA #24 ชุดทดสอบ", "mode": "before_after_reduction",
        "note": "ข้อมูลสังเคราะห์"})
    pid = r.headers["location"].rsplit("/", 1)[-1]
    for side, path in zip("AB", pair):
        with open(path, "rb") as fh:
            client.post(f"/projects/{pid}/upload", data={CSRF_FIELD: token, "side": side},
                        files={"upload": (path.name, fh)})
    r = client.post(f"/projects/{pid}/analyze", follow_redirects=False, data={CSRF_FIELD: token})
    assert r.status_code == 303
    return pid, r.headers["location"].rsplit("/", 1)[-1]


def _main(html: str) -> str:
    m = re.search(r"<main.*?</main>", html, re.S)
    return m.group(0) if m else html


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# ══════════════════════════════════════════════════════════════ ชั้นแสดงผล (ไม่มี HTTP)

def test_every_finding_lands_in_exactly_one_item(view):
    items = vv.group_items(view)
    ids = [f.finding_id for it in items for f in it.findings]
    assert sorted(ids) == sorted(f.finding_id for f in view.findings)


def test_grand_total_comes_from_the_document_total_row_in_baht(view):
    m = vv.build_overview(view).money
    assert m.totals_found == 1 and m.total is not None
    tc = m.total_cell
    # เอกสารพิมพ์ 34.2000 → 33.1001 ล้านบาท ⇒ คูณตรงเป็นบาท ไม่ปัดเศษ
    assert tc.a_baht == Decimal("34200000") and tc.b_baht == Decimal("33100100")
    assert tc.diff_baht == Decimal("-1099900")
    assert m.state == "diff" and "1,099,900 บาท" in m.headline


def test_money_items_are_not_summed_into_a_new_total(view):
    m = vv.build_overview(view).money
    assert all(not it.is_grand_total for it in m.changed)
    # ผลรวมของรายการไม่เท่ายอดรวมของเอกสาร — หน้าจอต้องไม่บวกเอง
    s = sum(c.diff_baht for it in m.changed for c in it.money_cells if c.diff_baht is not None)
    assert s != m.total_cell.diff_baht


def test_no_total_row_says_so_instead_of_summing(view):
    findings = [f for f in view.findings if f.budget_category != "TOTAL"]
    v2 = svc.T1BRunView(summary=view.summary, findings=findings)
    m = vv.build_overview(v2).money
    assert m.total is None
    assert any("ไม่พบแถวยอดรวม" in x for x in m.lines)


def test_changes_are_described_in_reviewer_language(view):
    ov = vv.build_overview(view)
    kinds = {o.kind for o in ov.observations}
    assert {"indicator", "added", "removed"} <= kinds
    for o in ov.observations:
        assert "ผิด" not in o.sentence
    removed = [it for it in ov.items if "removed" in it.kinds]
    assert removed and removed[0].summary.startswith("มีในฉบับ A แต่ไม่พบในฉบับ B")
    assert "1,200,000 บาท" in removed[0].summary


def test_unreadable_rows_are_counted_for_review_not_dropped(view):
    ov = vv.build_overview(view)
    review = vv.items_for(ov, "review")
    assert ov.review_count > 0 and len(review) >= ov.review_count


def test_text_diff_highlights_only_the_changed_part():
    d = vv.diff_text("ประชาชนได้รับบริการไม่น้อยกว่า 80%", "ประชาชนได้รับบริการไม่น้อยกว่า 85%")
    assert d.changes == (("80%", "85%"),)
    assert [s.text for s in d.b if s.changed] == ["85%"]
    d = vv.diff_text("ดำเนินการพัฒนา ระบบฐานข้อมูล", "ดำเนินการพัฒนา ระบบฐานข้อมูลและ AI")
    assert d.changes == (("", "และ AI"),)
    assert not vv.diff_text("ค่า\nใช้จ่าย", "ค่า ใช้จ่าย").changed


def test_fmt_number_never_rounds():
    assert vv.fmt_number(Decimal("100.0000")) == "100"
    assert vv.fmt_number(Decimal("0.0001") * 1_000_000) == "100"
    assert vv.fmt_number(Decimal("12.345")) == "12.345"
    assert vv.fmt_number(Decimal("-1099900.00")) == "-1,099,900"


def test_excerpt_refuses_a_file_with_a_different_hash(pair, tmp_path):
    a, _ = pair
    ex = source_rows.excerpt(a, expected_sha256="0" * 64, sheet="แผนพื้นฐาน", row=5,
                             target_cells=["E5"])
    assert not ex.ok and "SHA-256 ไม่ตรง" in ex.reason
    ok = source_rows.excerpt(a, expected_sha256=source_rows.sha256_file(a),
                             sheet="แผนพื้นฐาน", row=5, target_cells=["E5"])
    assert ok.ok and any(c.target and c.ref == "E5" for r in ok.rows for c in r.cells)


# ══════════════════════════════════════════════════════════════ หน้าเว็บ

def test_overview_is_three_answers_without_tables_or_engine_words(client, run):
    _, rid = run
    main = _main(client.get(f"/t1b/runs/{rid}").text)
    assert main.count('class="vx-answer ') == 3
    assert "<table" not in main
    text = _text(main)
    for w in ENGINE_WORDS:
        assert w not in text, w
    assert "พบยอดรวมต่าง 1,099,900 บาท" in text
    assert "หน่วยงานเดียวกัน" in text
    assert "ไม่ใช่การรับรอง" in text


def test_overview_is_shorter_than_the_old_summary(client, run):
    _, rid = run
    new = _text(_main(client.get(f"/t1b/runs/{rid}").text))
    old = _text(_main(client.get(f"/t1b/runs/{rid}/details").text))
    assert len(new) < len(old) * 0.75


def test_details_page_keeps_the_engine_view(client, run):
    _, rid = run
    body = client.get(f"/t1b/runs/{rid}/details").text
    assert "ตารางกระทบยอด" in body and "ข้อสังเกตแยกตามชนิด" in body


def test_drill_down_money_to_compare_to_source_row(client, run):
    _, rid = run
    money = client.get(f"/t1b/runs/{rid}/money").text
    assert "รายการที่ยอดไม่เท่ากัน" in money and "ไม่บวก" in money
    # รายการแรกของ "รายการที่ยอดไม่เท่ากัน" = ผลต่างมากที่สุด (ไม่ใช่ลิงก์แถวยอดรวมด้านบน)
    link = re.search(rf'vx-item-link" href="(/t1b/runs/{rid}/compare/[0-9a-f]+\?back=money)', money)
    assert link
    link = re.match(r"(.*)", link.group(1))
    cmp_ = client.get(link.group(0)).text
    text = _text(_main(cmp_))
    assert "ลดลง 600,000 บาท" in text
    assert "ภาพจากสมุดงาน Excel ที่ใช้ตรวจ" in cmp_       # ไม่มี PDF ⇒ ภาพจาก Excel เปิดเป็นภาพหลัก
    assert "ยังไม่มี PDF ต้นฉบับของฉบับ A" in cmp_
    assert cmp_.count('class="vx-side vx-side-') == 2
    assert "is-changed vx-cell-a" in cmp_ and "is-changed vx-cell-b" in cmp_


def test_removed_item_shows_absence_on_side_b(client, run):
    _, rid = run
    lst = client.get(f"/t1b/runs/{rid}/changes?kind=removed").text
    link = re.search(rf'/t1b/runs/{rid}/compare/[0-9a-f]+\?back=changes', lst)
    assert link
    assert "ไม่พบรายการนี้ในฉบับ B" in client.get(link.group(0)).text


def test_sources_page_shows_hashes_and_two_layers(client, run):
    pid, rid = run
    body = client.get(f"/t1b/runs/{rid}/sources").text
    files = repo.project_files(pid)
    for side in "AB":
        assert files[side]["sha256"] in body
    assert "Source Verification" in body and "Result Verification" in body
    assert "ตรงกัน" in body


def test_replaced_file_is_not_shown_as_evidence(client, run, pair, tmp_path):
    """ไฟล์ที่เก็บถูกแก้หลังตรวจ ⇒ หน้าเทียบต้องไม่แสดงเนื้อไฟล์ใหม่แทนเงียบ ๆ"""
    pid, rid = run
    fr = repo.project_files(pid)["A"]
    path = filestore.path_for(fr["stored_name"])
    original = path.read_bytes()
    mode = path.stat().st_mode
    os.chmod(path, mode | stat.S_IWRITE)   # ไฟล์ที่อัปโหลดถูกตั้งเป็นอ่านอย่างเดียว
    try:
        path.write_bytes(original + b"\0")
        money = client.get(f"/t1b/runs/{rid}/money").text
        link = re.search(rf'/t1b/runs/{rid}/compare/[0-9a-f]+\?back=money', money)
        body = client.get(link.group(0)).text
        assert "SHA-256 ไม่ตรง" in body
        assert "ไฟล์หลักฐานตรงกับไฟล์ที่ใช้ตรวจ" in client.get(f"/t1b/runs/{rid}/sources").text
    finally:
        path.write_bytes(original)
        os.chmod(path, mode)


def test_unknown_item_is_a_clean_404(client, run):
    _, rid = run
    assert client.get(f"/t1b/runs/{rid}/compare/ffffffffffffffff").status_code == 404


# ══════════════════════════════════════════════ คิว · ตรวจก่อนส่งออก · ตัดสินจากหลักฐาน

@pytest.fixture(scope="module")
def run2(client, pair):
    """รอบแยกสำหรับเทสต์ที่บันทึกคำตัดสิน — ไม่กระทบเทสต์ที่อ่านอย่างเดียวข้างบน"""
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post("/projects/new", follow_redirects=False, data={
        CSRF_FIELD: token, "name": "IA #24 ตัดสิน", "mode": "before_after_reduction",
        "note": "ข้อมูลสังเคราะห์"})
    pid = r.headers["location"].rsplit("/", 1)[-1]
    for side, path in zip("AB", pair):
        with open(path, "rb") as fh:
            client.post(f"/projects/{pid}/upload", data={CSRF_FIELD: token, "side": side},
                        files={"upload": (path.name, fh)})
    r = client.post(f"/projects/{pid}/analyze", follow_redirects=False, data={CSRF_FIELD: token})
    return r.headers["location"].rsplit("/", 1)[-1], token


def test_queue_default_is_evidence_rows_and_table_is_still_reachable(client, run):
    _, rid = run
    body = client.get(f"/t1b/runs/{rid}/queue").text
    assert 'class="vx-rows"' in body and "ดูหลักฐาน" in body
    assert f"/t1b/runs/{rid}/queue?view=table" in body
    assert "แถว 5 ↔ แถว 5" in body                 # ตำแหน่งสั้น (ชีต/เซลล์อยู่ใน title/รายละเอียด)
    assert 'class="vx-ctx"' in body                 # แถบบริบทของรอบ
    table = client.get(f"/t1b/runs/{rid}/queue?view=table").text
    assert "เลือกทั้งหมดตามตัวกรอง" in table
    # ลิงก์เดิมที่พกตัวกรองของตารางมายังเปิดตาราง
    assert "เลือกทั้งหมดตามตัวกรอง" in client.get(
        f"/t1b/runs/{rid}/queue?ftype=UNMAPPED_REQUIRES_HUMAN_REVIEW").text


def test_unread_row_says_what_was_read_and_what_is_missing(client, run):
    _, rid = run
    lst = client.get(f"/t1b/runs/{rid}/review").text
    links = re.findall(rf'vx-item-link" href="(/t1b/runs/{rid}/compare/[0-9a-f]+\?back=review)', lst)
    bodies = [_text(client.get(u).text) for u in links]
    unread = [b for b in bodies if "ระบบอ่านแถวนี้ไม่ครบ —" in b]
    assert unread, "ต้องมีแถวที่ระบบอ่านไม่ครบในชุดสาธิต (หน้าปก/หัวตาราง)"
    body = unread[0]
    assert "ระบบอ่านได้" in body and "ยังยืนยันไม่ได้" in body
    assert "หน้าปก" in body or "นอกตารางปีงบประมาณ" in body
    # แถวที่อ่านไม่ครบไม่ใช่ "รายการหาย" — ห้ามบอกว่าไม่พบในอีกฉบับ และห้ามขีดฆ่าเป็นข้อความที่ตัดออก
    assert "ไม่ได้แปลว่าไม่มีในฉบับ" in body
    assert "ไม่พบรายการนี้ในฉบับ" not in body and "ข้อความที่เปลี่ยน" not in body
    assert "cover_sheet_layout_not_mapped" not in body.split("รายละเอียดทางเทคนิค")[0]


def test_preflight_lists_people_work_and_opens_the_same_evidence(client, run2):
    rid, _ = run2
    body = client.get(f"/t1b/runs/{rid}/preflight").text
    assert "เรื่องที่คนยังต้องตรวจ" in body and "ทางแก้" in body
    assert "ตารางกระทบยอดข้อสังเกต" in body             # ยังอยู่ (พับไว้)
    links = re.findall(rf'/t1b/runs/{rid}/compare/[0-9a-f]+\?back=preflight', body)
    assert links
    assert "ผลการตรวจของคุณ" in client.get(links[0]).text


def test_decide_from_evidence_maps_to_existing_status_and_returns_to_preflight(client, run2):
    from redbook.services import review as review_service
    rid, token = run2
    before = client.get(f"/t1b/runs/{rid}/preflight").text
    n_before = len(set(re.findall(rf'/t1b/runs/{rid}/compare/([0-9a-f]+)\?back=preflight', before)))
    fid = re.search(rf'/t1b/runs/{rid}/compare/([0-9a-f]+)\?back=preflight', before).group(1)
    r = client.post(f"/t1b/runs/{rid}/compare/{fid}/decide", follow_redirects=False,
                    data={CSRF_FIELD: token, "choice": "per_document", "note": "", "back": "preflight"})
    assert r.status_code == 303 and r.headers["location"].endswith("/preflight?decided=1")
    view = svc.load_run(rid)
    ann = review_service.annotate(view, review_service.status_map(rid))
    it = vv.build_overview(view).by_id(fid)
    for f in it.findings:
        assert ann[f.finding_id].status == "DISMISSED"
    after = client.get(f"/t1b/runs/{rid}/preflight").text
    n_after = len(set(re.findall(rf'/t1b/runs/{rid}/compare/([0-9a-f]+)\?back=preflight', after)))
    assert n_after == n_before - 1
    # เปลี่ยนคำตัดสินเดิมโดยไม่เขียนเหตุผล = ไม่บันทึก
    r = client.post(f"/t1b/runs/{rid}/compare/{fid}/decide",
                    data={CSRF_FIELD: token, "choice": "fix", "note": "", "back": "queue"})
    assert r.status_code == 400 and "ต้องเขียนเหตุผล" in r.text


def test_decision_note_carries_the_human_reason():
    assert vv.decision_note("mismatch", "") == "[ระบบจับคู่ผิด]"
    assert vv.decision_note("fix", "ยอดไม่ตรงหน้า 3") == "[ต้องแก้ข้อมูล] ยอดไม่ตรงหน้า 3"
    assert vv.choice_of_note("[ต้องตรวจเพิ่มเติม] x") == "ต้องตรวจเพิ่มเติม"
    statuses = {s for _, _, s in vv.DECISION_CHOICES}
    assert statuses <= {"CONFIRMED", "UNRESOLVED", "DISMISSED"}   # ไม่มีสถานะใหม่ใน schema


# ══════════════════════════════════════════════ มาตรฐานหน่วย/ทศนิยม (shared formatter)

from redbook.services import amounts  # noqa: E402


@pytest.mark.parametrize("raw, want", [
    ("7.4", "7.4000"), (Decimal("17.6"), "17.6000"), (9.2, "9.2000"), ("34.2", "34.2000"),
    ("7.4001", "7.4001"), (16.5, "16.5000"), ("33.4001", "33.4001"), ("1,234.5", "1,234.5000"),
])
def test_million_baht_always_four_places(raw, want):
    assert amounts.format_number(raw, "ล้านบาท") == want
    assert amounts.format_amount(raw, "ล้านบาท") == f"{want} ล้านบาท"


def test_baht_stays_baht_and_nothing_is_rounded():
    assert amounts.format_amount(7400100, "บาท") == "7,400,100 บาท"
    assert amounts.format_number("16,500,000.00", "บาท") == "16,500,000"
    assert amounts.format_number("12.5", "บาท") == "12.50"
    assert amounts.format_number("1.23456", "ล้านบาท") == "1.23456"     # เติมศูนย์ได้ ปัดไม่ได้
    assert amounts.to_baht("7.4001", "ล้านบาท") == Decimal("7400100")


def test_compare_is_numeric_not_string():
    assert amounts.same_value("7.4", "7.4000")
    assert amounts.same_value(Decimal("7.4"), 7.4)
    assert not amounts.same_value("7.4", "7.4001")


def test_compare_page_uses_four_places_and_highlights_only_real_changes(client, run):
    _, rid = run
    money = client.get(f"/t1b/runs/{rid}/money").text
    total = re.search(rf'/t1b/runs/{rid}/compare/[0-9a-f]+\?back=money', money).group(0)
    body = client.get(total).text
    for v in ("7.4000", "7.4001", "17.6000", "16.5000", "9.2000", "34.2000", "33.1001"):
        assert v in body, v
    # งบเงินอุดหนุน 9.2 = 9.2 ⇒ ไม่อยู่ในรายการ "ค่าที่เปลี่ยน" (ต่างกันแค่รูปแบบไม่นับ)
    changes = re.search(r'<ol class="vx-ev-changes">.*?</ol>', body, re.S).group(0)
    assert "งบลงทุน" in changes and "งบเงินอุดหนุน" not in changes
    assert "ลดลง 1.1000 ล้านบาท · คิดเป็น 1,100,000 บาท" in _text(changes)
    # แถวต้นฉบับ: ค่าจาก Excel (float 7.4) แสดงตามมาตรฐานเดียวกัน
    excerpt = body.split("ภาพจากสมุดงาน Excel ที่ใช้ตรวจ", 1)[1]
    assert "7.4000" in excerpt and "17.6000" in excerpt
    assert 'title="ค่าดิบในไฟล์: 7.4"' in excerpt          # ค่าดิบยังเปิดดูได้


def test_legacy_pages_use_the_same_standard(client, run):
    _, rid = run
    table = client.get(f"/t1b/runs/{rid}/queue?view=table&per_page=200").text
    assert "7.4001" in table and "7.4000" in table


# ══════════════════════════════════════════════ คิวแบบ compact + บริบท (ชุดสาธิตโครงสร้างครบชั้น)

import demo_ao_workbooks_rich as rich  # noqa: E402


def _make_rich_run(client, tmp, scenario):
    a, b = rich.build(tmp, scenario)
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post("/projects/new", follow_redirects=False, data={
        CSRF_FIELD: token, "name": f"IA #24 {scenario} (สังเคราะห์)", "mode": "before_after_reduction",
        "note": "ข้อมูลสังเคราะห์"})
    pid = r.headers["location"].rsplit("/", 1)[-1]
    for side, path in zip("AB", (a, b)):
        with open(path, "rb") as fh:
            client.post(f"/projects/{pid}/upload",
                        data={CSRF_FIELD: token, "side": side, **rich.declared(scenario, side)},
                        files={"upload": (path.name, fh)})
    r = client.post(f"/projects/{pid}/analyze", follow_redirects=False, data={CSRF_FIELD: token})
    return r.headers["location"].rsplit("/", 1)[-1]


@pytest.fixture(scope="module")
def rich_run(client, tmp_path_factory):
    """ร่าง พ.ร.บ. 2570 ↔ พ.ร.บ. 2570 (ปีเดียวกัน)"""
    return _make_rich_run(client, tmp_path_factory.mktemp("rich"), "draft_act")


@pytest.fixture(scope="module")
def cross_run(client, tmp_path_factory):
    """พ.ร.บ. 2569 ↔ พ.ร.บ. 2570 (ข้ามปี · ปีที่ซ้อนกัน = 2569)"""
    return _make_rich_run(client, tmp_path_factory.mktemp("cross"), "cross_year")


def test_rich_demo_is_marked_synthetic():
    assert "สาธิต" in rich.MINISTRY and "สาธิต" in rich.AGENCY and "(สาธิต)" in rich.PLAN_TITLE


def test_queue_context_bar_shows_agency_years_and_ab(client, rich_run):
    body = _text(client.get(f"/t1b/runs/{rich_run}/queue").text)
    assert rich.AGENCY in body                         # อ่านจากหน้าปกของแฟ้ม
    assert "ปีงบประมาณ 2570" in body
    assert "ร่าง พ.ร.บ. ปี 2570" in body and "พ.ร.บ. ปี 2570" in body   # ขั้นเอกสารจากที่ผู้ใช้ประกาศ
    assert "ฉบับ A ปี" not in body


def test_queue_groups_by_plan_and_project_with_activity_heading(client, rich_run):
    body = client.get(f"/t1b/runs/{rich_run}/queue").text
    text = _text(body)
    assert "แผนงานพื้นฐานด้านการพัฒนาระบบบริการสุขภาพ (สาธิต) › โครงการพัฒนาระบบข้อมูลสุขภาพดิจิทัล (สาธิต)" in text
    assert "ภายใต้ 1. กิจกรรม : พัฒนาฐานข้อมูลผู้รับบริการ" in text
    assert "ภายใต้ 1. ผลผลิต : ประชาชนได้รับบริการสุขภาพปฐมภูมิที่มีคุณภาพ" in text
    # แถวหน้าปก/หัวตาราง แยกไว้ในกลุ่มที่พับไว้ ไม่ปนกับรายการที่เปลี่ยนจริง
    assert re.search(r'<details class="vx-group">\s*<summary><span class="vx-group-crumbs"><b>แถวที่ระบบอ่านไม่ครบ', body)
    # รายการที่เปลี่ยนเงินอ่านความต่างได้จากคิวเลย
    assert "ลดลง 400,000 บาท" in text and "33.0000 → 32.7000" in text


def test_no_parent_heading_is_invented(client, rich_run):
    from redbook.services import t1b as _svc
    ov = vv.build_overview(_svc.load_run(rich_run))
    for it in ov.items:
        if it.heading:
            no = it.title.split(" ", 1)[0].rstrip(".")
            assert it.heading.split(" ", 1)[0].rstrip(".") == no.rsplit(".", 1)[0]
    top = [it for it in ov.items if it.title.startswith("1. ")]
    assert top and all(not it.heading for it in top)


# ══════════════════════════════════════════════ หลักฐานแบบ PDF-first (ภาพหน้า PDF จริง · สังเคราะห์)

import demo_pdf_rich  # noqa: E402
from redbook.storage import source_pdfs  # noqa: E402

pytestmark_pdf = pytest.mark.skipif(
    __import__("redbook.evidence.pdftext", fromlist=["x"]).get_backend() is None,
    reason="ไม่มี product PDF backend")


@pytest.fixture(scope="module")
def rich_pdfs(tmp_path_factory):
    return demo_pdf_rich.build(tmp_path_factory.mktemp("rich_pdf"), "draft_act")


def _pid_of(run_id):
    from redbook.storage import t1b_repo
    return t1b_repo.get_run(run_id)["project_id"]


def _attach(client, run_id, side, path):
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    with open(path, "rb") as fh:
        return client.post(f"/projects/{_pid_of(run_id)}/source-pdf", follow_redirects=False,
                           data={CSRF_FIELD: token, "side": side, "back": f"/t1b/runs/{run_id}/queue"},
                           files={"upload": (path.name, fh, "application/pdf")})


def _item_link(client, run_id, title):
    q = client.get(f"/t1b/runs/{run_id}/queue").text
    for m in re.finditer(r'<li class="vx-row[^"]*" id="it-([0-9a-f]+)">(.*?)</li>', q, re.S):
        if title in m.group(2):
            return f"/t1b/runs/{run_id}/compare/{m.group(1)}?back=queue"
    raise AssertionError(title)


@pytestmark_pdf
def test_attach_source_pdf_and_see_both_pages(client, rich_run, rich_pdfs):
    a, b = rich_pdfs
    assert _attach(client, rich_run, "A", a).status_code == 303
    assert _attach(client, rich_run, "B", b).status_code == 303
    assert set(source_pdfs.for_project(_pid_of(rich_run))) == {"A", "B"}
    body = client.get(_item_link(client, rich_run, "1.2 งบลงทุน")).text
    text = _text(body)
    assert "PDF หน้า 2" in text and "PDF หน้า 3" in text        # B มีหน้าคำนำเพิ่ม ⇒ คนละหน้า
    assert "พบข้อความรายการและตัวเลขในบรรทัดเดียวกัน" in text
    assert body.count('class="vx-hot"') >= 2                    # จุดชี้บนภาพทั้งสองฝั่ง
    assert "ลดลง 400,000 บาท" in text
    img = re.search(r'src="(/t1b/runs/[^"]+/pdf/A\.png)"', body).group(1)
    r = client.get(img)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content.startswith(b"\x89PNG")
    assert client.get(img + "?full=1").status_code == 200


@pytestmark_pdf
def test_million_baht_summary_is_found_in_pdf_with_four_places(client, rich_run, rich_pdfs):
    money = client.get(f"/t1b/runs/{rich_run}/money").text
    total = re.search(rf'/t1b/runs/{rich_run}/compare/[0-9a-f]+\?back=money', money).group(0)
    text = _text(client.get(total).text)
    assert "PDF หน้า 4" in text and "PDF หน้า 5" in text
    assert "33.0000 ล้านบาท" in text and "32.7000 ล้านบาท" in text
    assert "คิดเป็น 300,000 บาท" in text
    changes = _text(re.search(r'<ol class="vx-ev-changes">.*?</ol>', client.get(total).text, re.S).group(0))
    assert "งบบุคลากร" not in changes                     # 3.4001 = 3.4001 ไม่ใช่ความต่าง


@pytestmark_pdf
def test_removed_item_shows_the_searched_area_on_the_other_side(client, rich_run, rich_pdfs):
    body = client.get(_item_link(client, rich_run, "2.2 ค่าจัดทำคู่มือ")).text
    text = _text(body)
    assert "บริเวณที่ระบบค้นหาในฉบับ B" in text and "ยังไม่พบรายการที่จับคู่ได้" in text
    assert re.search(r'src="/t1b/runs/[^"]+/pdf/B\.png"', body)


@pytestmark_pdf
def test_panel_mode_is_a_fragment_and_decision_returns_to_queue(client, rich_run):
    link = _item_link(client, rich_run, "1.3 งบเงินอุดหนุน")
    frag = client.get(link + "&panel=1")
    assert frag.status_code == 200
    assert "<html" not in frag.text and 'class="vx-panel"' in frag.text
    assert 'name="ret" value="list"' in frag.text
    fid = re.search(r"/compare/([0-9a-f]+)", link).group(1)
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post(f"/t1b/runs/{rich_run}/compare/{fid}/decide", follow_redirects=False,
                    data={CSRF_FIELD: token, "choice": "checked", "back": "queue", "ret": "list"})
    assert r.status_code == 303 and f"/queue?decided=1#it-{fid}" in r.headers["location"]


def test_source_pdf_slot_rejects_non_pdf(client, rich_run, pair):
    r = _attach(client, rich_run, "A", pair[0])          # สมุดงาน xlsx
    assert r.status_code == 400


def test_queue_and_preflight_load_the_popup_script(client, rich_run):
    assert "/static/verify.js" in client.get(f"/t1b/runs/{rich_run}/queue").text
    assert "/static/verify.js" in client.get(f"/t1b/runs/{rich_run}/preflight").text


def test_fetch_tool_only_takes_allowlisted_hosts_and_links_official_pdf(rich_pdfs, tmp_path):
    """เครื่องมือดึง PDF (นอกแพ็กเกจ) — ทดสอบกับเซิร์ฟเวอร์ในเครื่อง + PDF สังเคราะห์เท่านั้น"""
    import http.server
    import threading
    from types import SimpleNamespace

    import fetch_source_pdfs as fetch
    from redbook.storage import book_links

    a, _ = rich_pdfs
    pid = repo.create_project("fetch-test (สังเคราะห์)", "before_after_reduction", "")
    handler = type("H", (http.server.SimpleHTTPRequestHandler,), {
        "log_message": lambda *x: None})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                          lambda *x: handler(*x, directory=str(a.parent)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_port}/{a.name}"
        book_links.link(pid, "A", SimpleNamespace(id="DEV-X", fiscal_year=2569, title="สาธิต",
                                                  pdf_url=url, source_page=url))
        book_links.link(pid, "B", SimpleNamespace(id="DEV-Y", fiscal_year=2570, title="สาธิต",
                                                  pdf_url="https://example.invalid/x.pdf",
                                                  source_page=""))
        res = fetch.run([pid], hosts={"127.0.0.1"}, allow_http_local=True, log=lambda *_: None)
        assert res == {"linked": 1, "skipped": 0, "failed": 1}    # B ไม่อยู่ใน allowlist
        row = source_pdfs.for_project(pid)["A"]
        assert row["origin"] == "official" and row["source_url"] == url and row["retrieved_at"]
        res2 = fetch.run([pid], hosts={"127.0.0.1"}, allow_http_local=True, log=lambda *_: None)
        assert res2["skipped"] == 1                                # มีแล้ว ไม่ดึงซ้ำ
        # ค่าเริ่มต้นไม่ยอม http และไม่ยอมโฮสต์อื่นนอกจากเว็บสำนักงบประมาณ
        assert not fetch._allowed(url, set(fetch.DEFAULT_HOSTS), False)
        assert fetch._allowed("https://www.bb.go.th/x.pdf", set(fetch.DEFAULT_HOSTS), False)
    finally:
        srv.shutdown()


# ══════════════════════════════════════════════ Bo 8 ต.ค. — redirect · Audit · ชุดพัฒนาที่อนุญาต · ป้าย

def _serve(directory, routes):
    """เซิร์ฟเวอร์ในเครื่อง: ``routes`` = {path: ("redirect", url) | ("file", name)}"""
    import http.server
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            kind, val = routes.get(self.path, ("404", ""))
            if kind == "redirect":
                self.send_response(302)
                self.send_header("Location", val.replace("{port}", str(self.server.server_port)))
                self.end_headers()
            elif kind == "file":
                data = (directory / val).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_fetch_refuses_redirect_out_of_allowlist_and_follows_internal(rich_pdfs):
    import fetch_source_pdfs as fetch
    a, _ = rich_pdfs
    srv = _serve(a.parent, {
        "/out": ("redirect", "http://example.invalid/evil.pdf"),          # ออกนอกโฮสต์
        "/in": ("redirect", "http://127.0.0.1:{port}/" + a.name),         # ภายในโฮสต์ที่อนุญาต
        "/" + a.name: ("file", a.name),
    })
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        with pytest.raises(fetch.RedirectRefused):
            fetch.fetch_one(base + "/out", max_bytes=10_000_000, hosts={"127.0.0.1"},
                            allow_http_local=True)
        data, final = fetch.fetch_one(base + "/in", max_bytes=10_000_000, hosts={"127.0.0.1"},
                                      allow_http_local=True)
        assert data.startswith(b"%PDF") and final.endswith("/" + a.name)
        # ค่าเริ่มต้น (https + bb.go.th เท่านั้น) ไม่ยอม URL ต้นทางนี้ตั้งแต่แรก
        with pytest.raises(fetch.RedirectRefused):
            fetch.fetch_one(base + "/" + a.name, max_bytes=10_000_000)
    finally:
        srv.shutdown()


def test_fetch_refuses_real_books_without_approved_dev_set():
    """#22 — ลิงก์จริงต้องอยู่ในชุดพัฒนาที่ได้รับอนุญาต · ปฏิเสธก่อนแตะเครือข่าย"""
    from types import SimpleNamespace

    import fetch_source_pdfs as fetch
    from redbook.storage import book_links
    pid = repo.create_project("gate-test (สังเคราะห์)", "before_after_reduction", "")
    book_links.link(pid, "A", SimpleNamespace(id="bb-0000-00000", fiscal_year=2570, title="x",
                                              pdf_url="https://www.bb.go.th/download.php?id=0",
                                              source_page=""))
    calls = []
    orig = fetch.fetch_one
    fetch.fetch_one = lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(AssertionError)
    try:
        res = fetch.run([pid], hosts=set(fetch.DEFAULT_HOSTS), log=lambda *_: None)
        assert res.get("refused") == 1 and res["linked"] == 0 and calls == []
    finally:
        fetch.fetch_one = orig


def test_audit_keeps_url_and_time_for_every_attach(rich_pdfs):
    import json as _json
    from types import SimpleNamespace

    from redbook.storage import audit
    a, b = rich_pdfs
    pid = repo.create_project("audit-test (สังเคราะห์)", "before_after_reduction", "")
    for path, url, when in ((a, "https://www.bb.go.th/1.pdf", "2026-10-08T09:00:00+07:00"),
                            (b, "https://www.bb.go.th/2.pdf", "2026-10-08T10:00:00+07:00")):
        stored = SimpleNamespace(stored_name="x.pdf", original_name=path.name, kind="pdf",
                                 sha256=source_rows.sha256_file(path), size_bytes=path.stat().st_size)
        source_pdfs.link(pid, "A", stored, origin="official", source_url=url, retrieved_at=when)
    rows = [_json.loads(e["detail_json"]) for e in audit.entries(object_id=pid)
            if e["action"] == "project_source_pdf_linked"]
    got = {(r["source_url"], r["retrieved_at"]) for r in rows}
    # แนบแทนที่ฝั่งเดิมแล้ว ประวัติของไฟล์แรกยังอยู่ใน Audit
    assert got == {("https://www.bb.go.th/1.pdf", "2026-10-08T09:00:00+07:00"),
                   ("https://www.bb.go.th/2.pdf", "2026-10-08T10:00:00+07:00")}


@pytestmark_pdf
def test_located_position_is_labelled_pending_human_confirmation(client, rich_run, rich_pdfs):
    _attach(client, rich_run, "A", rich_pdfs[0])
    _attach(client, rich_run, "B", rich_pdfs[1])
    text = _text(client.get(_item_link(client, rich_run, "1.1 งบดำเนินงาน")).text)
    assert "ตำแหน่งที่ระบบค้นพบ — รอผู้ตรวจยืนยัน" in text
    gone = _text(client.get(_item_link(client, rich_run, "2.2 ค่าจัดทำคู่มือ")).text)
    assert "ไม่ใช่หลักฐานว่ารายการหายแน่นอน" in gone



# ══════════════════════════════════════════════ เทียบข้ามปี — ปีที่มีฉบับเดียวไม่ใช่ "รายการหาย"

def test_cross_year_rows_are_not_shown_as_removed_or_new(client, cross_run):
    from redbook.services import t1b as _svc
    ov = vv.build_overview(_svc.load_run(cross_run))
    removed = [it.title for it in ov.items if "removed" in it.kinds]
    added = [it.title for it in ov.items if "added" in it.kinds]
    assert removed == []                                       # ทุกแถวยังอยู่ — แค่ปี 2568 อยู่นอกช่วงเทียบ
    assert added == ["2.2 ค่าเช่าระบบคลาวด์สำหรับฐานข้อมูล"]   # รายการใหม่จริงของเล่ม 2570
    ids = sorted(f.finding_id for it in ov.items for f in it.findings)
    assert ids == sorted(f.finding_id for f in _svc.load_run(cross_run).findings)   # ไม่ทิ้งใบใด


def test_cross_year_context_and_headline_say_year_over_year(client, cross_run):
    text = _text(client.get(f"/t1b/runs/{cross_run}").text)
    assert "เทียบได้เฉพาะปีที่มีในทั้งสองฉบับ" in text and "ปี 2568 มีเฉพาะฉบับ A" in text
    assert "ยอดรวมปี 2570 เพิ่มขึ้นจากปี 2569" in text
    assert "พ.ร.บ. ปี 2569" in text and "พ.ร.บ. ปี 2570" in text
