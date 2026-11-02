# -*- coding: utf-8 -*-
"""คลังเล่มงบประมาณ (#24) — ค้น/กรอง/จับคู่เล่ม และทางเข้าสู่ workflow ตรวจเดิม

ชุดนี้ทดสอบ "พฤติกรรมที่ผู้ใช้เห็น" ตาม pain point ใน #24:
- หาเล่มย้อนหลังได้อย่างน้อย 3 ปี
- การ์ดอ่านปี/หน่วยงาน/ประเภทได้โดยไม่ต้องเปิดไฟล์
- เปิด PDF ทางการได้ (ระบบไม่เก็บสำเนา)
- เลือกเล่มไปเริ่มตรวจได้ และเข้าขั้น 2 ของ workflow เดิม ไม่ใช่เส้นทางใหม่
"""
import json
import re

import pytest
from fastapi.testclient import TestClient

from redbook.app import create_app
from redbook.services import books as B
from redbook.storage import book_links
from redbook.storage import repository as repo
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD


def _raw(id_, year, title, doc_type="expenditure_by_ministry", doc_no="3", volume="2",
         ministries=("กระทรวงการคลัง", "กระทรวงการต่างประเทศ")):
    return {"id": id_, "fiscal_year": year, "title": title, "doc_type": doc_type,
            "doc_type_label": "x", "doc_no": doc_no, "volume": volume,
            "ministries": list(ministries), "posted": "", "publisher": "สำนักงบประมาณ",
            "stage": "", "source_page": f"https://www.bb.go.th/p/{id_}",
            "pdf_url": f"https://www.bb.go.th/download.php?id={id_}", "files": [],
            "stripe_color": "", "retrieved_at": "",
            "link_check": {"status": 206, "is_pdf": True, "checked_at": "2026-10-06T00:00:00"}}


@pytest.fixture()
def small_catalog(tmp_path):
    books = [
        _raw("a70", 2570, "เอกสารงบประมาณ ฉบับที่ ๓ เล่มที่ ๒ ... พ.ศ. ๒๕๗๐ กระทรวงการคลัง"),
        _raw("a69", 2569, "เอกสารงบประมาณ ฉบับที่ ๓ เล่มที่ ๒ ... พ.ศ. ๒๕๖๙ กระทรวงการคลัง"),
        _raw("a68", 2568, "เอกสารงบประมาณ ฉบับที่ ๓ เล่มที่ ๒ ... พ.ศ. ๒๕๖๘ กระทรวงการคลัง"),
        _raw("h70", 2570, "เอกสารงบประมาณ ฉบับที่ ๓ เล่มที่ ๑๑ ... กระทรวงสาธารณสุข",
             volume="11", ministries=("กระทรวงสาธารณสุข",)),
        _raw("h69", 2569, "เอกสารงบประมาณ ฉบับที่ ๓ เล่มที่ ๑๑ ... กระทรวงสาธารณสุข",
             volume="11", ministries=("กระทรวงสาธารณสุข",)),
        _raw("s70", 2570, "งบประมาณโดยสังเขป ประจำปีงบประมาณ พ.ศ. ๒๕๗๐",
             doc_type="budget_in_brief", doc_no="", volume="", ministries=()),
    ]
    p = tmp_path / "cat.json"
    p.write_text(json.dumps({"catalog_version": "t", "years": [2570, 2569, 2568],
                             "books": books}, ensure_ascii=False), encoding="utf-8")
    return B.load(p)


# ══════════════════════════════════════════════════════════════ ค้นและกรอง
def test_search_by_ministry_finds_every_year(small_catalog):
    r = B.search(small_catalog, B.Query(view="cards", q="สาธารณสุข"))
    assert [b.fiscal_year for b in r.books] == [2570, 2569]


def test_thai_digits_and_volume_phrase(small_catalog):
    # "เล่ม ๒" ต้องตรงเฉพาะเล่มที่ 2 — ไม่ไปจับทุกเล่มที่มีเลข 2 อยู่ในชื่อ
    r = B.search(small_catalog, B.Query(view="cards", q="เล่ม ๒"))
    assert {b.id for b in r.books} == {"a70", "a69", "a68"}


def test_two_digit_year_token(small_catalog):
    r = B.search(small_catalog, B.Query(view="cards", q="คลัง 69"))
    assert [b.id for b in r.books] == ["a69"]


def test_year_filter_and_counts_reflect_other_filters(small_catalog):
    r = B.search(small_catalog, B.Query(view="cards", year=2568))
    assert [b.id for b in r.books] == ["a68"]
    # ตัวเลขข้างตัวกรองปี = จำนวนที่จะได้ถ้ากดปีนั้น (ภายใต้ตัวกรองอื่นที่ใช้อยู่)
    r = B.search(small_catalog, B.Query(view="cards", type="brief"))
    assert r.year_counts == {2570: 1, 2569: 0, 2568: 0}


def test_unknown_params_fall_back_safely(small_catalog):
    q = B.Query.from_params({"year": "1999", "type": "<script>", "sort": "x", "page": "-3"},
                            small_catalog.years)
    assert (q.year, q.type, q.sort, q.page) == (None, "", "volume", 1)


def test_empty_result(small_catalog):
    r = B.search(small_catalog, B.Query(view="cards", q="ไม่มีคำนี้แน่นอน"))
    assert r.total == 0 and r.books == []


def _with_pairs(cat, *pairs):
    """เติมคู่ที่ "ทะเบียน #27 ยืนยัน" ให้ทะเบียนทดสอบ — UI จัดกลุ่ม/เสนอคู่จากตรงนี้เท่านั้น"""
    from dataclasses import replace as _r
    return _r(cat, pairs=tuple({"kind": "CROSS_YEAR", "status": st, "a": [a], "b": [b]}
                               for a, b, st in pairs))


def test_grouped_view_one_card_per_book(small_catalog):
    # ไม่มีคู่ที่ทะเบียนยืนยัน ⇒ ไม่จัดกลุ่มจากชื่อ (คำตัดสิน Gift/Bo: UI ห้ามจับคู่เอง)
    r = B.search(small_catalog, B.Query(view="grouped"))
    assert r.group_total == 6
    cat = _with_pairs(small_catalog, ("a69", "a70", "MATCHED"), ("a68", "a69", "MATCHED"),
                      ("h69", "h70", "REVIEW_REQUIRED"))
    r = B.search(cat, B.Query(view="grouped"))
    assert r.group_total == 4                      # คลัง 3 ปีรวมกัน · สาธารณสุขยังไม่ยืนยัน = แยก
    finance = next(g for g in r.groups if g.lead.id == "a70")
    assert [b.fiscal_year for b in finance.by_year] == [2570, 2569, 2568]


# ══════════════════════════════════════════════════════════════ ป้ายบนการ์ด
def test_card_labels_do_not_need_the_pdf(small_catalog):
    b = small_catalog.get("a70")
    assert b.cover_label == "เล่ม 2"
    assert b.headline == "กระทรวงการคลัง · กระทรวงการต่างประเทศ"
    assert b.type_short == "รายจ่ายรายกระทรวง"
    assert b.link_ok is True


def test_long_ministry_list_is_summarised_not_cut_mid_name():
    b = B._book(_raw("x", 2570, "t", ministries=("ก", "ข", "ค", "ง")))
    assert b.headline_short == "ก · ข และอีก 2 หน่วย"


# ══════════════════════════════════════════════════════════════ คู่เล่ม
def test_pair_orders_older_year_as_side_a(small_catalog):
    cat = _with_pairs(small_catalog, ("a69", "a70", "MATCHED"))
    p = B.make_pair(cat, "a70", "a69")
    assert (p.a.id, p.b.id, p.mode) == ("a69", "a70", "year_to_year")
    assert p.complete and not p.warnings


def test_pair_rejects_same_book_and_unknown_ids(small_catalog):
    assert B.make_pair(small_catalog, "a70", "a70").error
    assert B.make_pair(small_catalog, "a70", "nope").error


def test_pair_warns_when_books_are_not_the_same_volume(small_catalog):
    # ไม่ตัดสินเองว่า "ไม่ใช่เล่มเดียวกัน" — บอกว่าทะเบียนยังไม่ยืนยัน (ชื่อตรงกันก็ยังเตือน)
    for a, b in (("a69", "h70"), ("a69", "a70")):
        p = B.make_pair(small_catalog, a, b)
        assert p.complete and any("ยังไม่ยืนยัน" in w for w in p.warnings)


def test_no_name_guessed_relations_left():
    """คำตัดสิน Bo: ความสัมพันธ์มาจาก pairs[] ของ #27 เท่านั้น — ตัวช่วยเดาจากชื่อถูกถอดออก"""
    for name in ("same_book_other_years", "same_ministry_same_year"):
        assert not hasattr(B.Catalog, name), name
    assert not hasattr(B.Book, "pair_key")


# ══════════════════════════════════════════════════════════════ ทะเบียนจริง
def test_real_catalog_covers_three_years_with_official_links():
    cat = B.load()
    assert len(cat.years) >= 3
    assert {b.fiscal_year for b in cat.books} >= set(cat.years)
    ids = [b.id for b in cat.books]
    assert len(ids) == len(set(ids))
    for b in cat.books:
        # ลิงก์ทางการเท่านั้น — ไม่มีลิงก์ภายในหรือสำเนาในเครื่อง
        assert b.pdf_url.startswith("https://www.bb.go.th/"), b.id
        assert b.source_page.startswith("https://www.bb.go.th/"), b.id
    # เล่มรายกระทรวงทุกเล่มต้องอ่านชื่อหน่วยรับงบออก ไม่เช่นนั้นการ์ดจะว่าง
    assert all(b.ministries for b in cat.books if b.doc_type == "expenditure_by_ministry")


# ══════════════════════════════════════════════════════════════ หน้าเว็บ
@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


def _csrf(client, path="/"):
    client.get(path)
    return client.cookies.get(CSRF_COOKIE)


def _health_pair():
    cat = B.catalog()
    b70 = B.search(cat, B.Query(view="cards", q="สาธารณสุข", year=2570, type="by_ministry")).books[0]
    b69 = next(x for x in B.search(cat, B.Query(view="cards", q="สาธารณสุข", year=2569,
                                                  type="by_ministry")).books if x.ministries == b70.ministries)
    return b70, b69


def test_home_leads_with_book_search(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'action="/books"' in r.text and "ค้นหาเล่ม" in r.text


def test_books_page_filters_and_links_to_official_pdf(client):
    r = client.get("/books", params={"year": 2569, "type": "by_ministry"})
    assert r.status_code == 200
    assert re.search(r'class="yr on[^"]*"[^>]*aria-current="page">2569 ', r.text)   # แท็บปีที่เลือก
    assert re.search(r'href="https://www\.bb\.go\.th/download\.php\?id=\d+"[^>]*target="_blank"', r.text)
    assert 'rel="noopener noreferrer"' in r.text


def test_books_page_escapes_query(client):
    r = client.get("/books", params={"q": "<script>alert(1)</script>"})
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text


def test_list_and_grouped_views_render(client):
    assert "book-list" in client.get("/books", params={"view": "list"}).text
    assert "year-lines" in client.get("/books", params={"view": "grouped"}).text


def test_book_detail_and_not_found(client):
    b70, b69 = _health_pair()
    r = client.get(f"/books/{b70.id}")
    assert r.status_code == 200
    assert b70.pdf_url in r.text
    # ทะเบียนเดิมไม่มี pairs[] ⇒ ไม่สร้างความสัมพันธ์ใดจากชื่อ (คำตัดสิน Bo · integration #24)
    assert f'href="/books/{b69.id}"' not in r.text
    assert f"/books/compare?a={b70.id}&amp;b={b69.id}" not in r.text
    cmp = client.get("/books/compare", params={"a": b70.id, "b": b69.id})   # ผู้ใช้เลือกคู่เอง
    assert cmp.status_code == 200
    assert f"/verify/start?a={b69.id}&amp;b={b70.id}" in cmp.text  # แล้วเข้างานตรวจเดิม (ปีเก่า = A)
    assert client.get("/books/does-not-exist").status_code == 404


def test_verify_start_states(client):
    b70, b69 = _health_pair()
    one = client.get("/verify/start", params={"a": b70.id})
    assert one.status_code == 200 and "เลือกอีกฉบับ" in one.text
    both = client.get("/verify/start", params={"a": b70.id, "b": b69.id})
    assert both.status_code == 200 and 'action="/verify/start"' in both.text
    assert client.get("/verify/start", params={"a": "nope"}).status_code == 400


def test_start_verification_creates_project_and_enters_step_two(client):
    b70, b69 = _health_pair()
    token = _csrf(client, f"/verify/start?a={b70.id}&b={b69.id}")
    r = client.post("/verify/start", data={"a": b70.id, "b": b69.id, "name": "",
                                           CSRF_FIELD: token}, follow_redirects=False)
    assert r.status_code == 303
    pid = r.headers["location"].rsplit("/", 1)[-1]
    project = repo.get_project(pid)
    assert project["mode"] == "year_to_year"           # โหมดเดิมของระบบ ไม่สร้างใหม่
    refs = book_links.for_project(pid)
    assert refs["A"]["fiscal_year"] == 2569 and refs["B"]["fiscal_year"] == 2570
    page = client.get(f"/projects/{pid}").text
    assert "เล่มอ้างอิงของงานนี้" in page and b70.pdf_url in page
    assert 'value="2569"' in page                      # ปีของฝั่ง A กรอกให้แล้ว


def test_start_verification_requires_csrf(client):
    b70, b69 = _health_pair()
    _csrf(client)
    r = client.post("/verify/start", data={"a": b70.id, "b": b69.id})
    assert r.status_code == 403


def test_demo_files_route_is_closed_outside_demo_mode(client):
    token = _csrf(client)
    pid = repo.create_project("t", "year_to_year")
    r = client.post(f"/projects/{pid}/demo-files", data={CSRF_FIELD: token})
    assert r.status_code == 404


# ══════════════════════════════════════════════ คำตัดสินกิ๊ฟ 7 ต.ค. 2569 (D1 · D3 · D4)
def test_default_view_is_grouped_by_book(client):
    r = client.get("/books")
    assert "year-lines" in r.text                       # D1
    assert "book-list" not in r.text
    assert 'view=cards' in r.text and 'view=list' in r.text


def test_cta_wording_does_not_imply_pdf_reading(client):
    b70, _ = _health_pair()
    page = client.get(f"/books/{b70.id}").text
    assert "ตั้งงานตรวจโดยอ้างอิงเล่มนี้" in page        # D3
    assert "ใช้เล่มนี้ในการตรวจ" not in page
    cards = client.get("/books", params={"view": "cards"}).text
    assert "ใช้เล่มนี้ในการตรวจ" not in cards
    assert "/books/compare?a=" in cards                  # การ์ดพาไปทางเข้าเปรียบเทียบ → งานตรวจ


def test_source_labels(client):
    b70, b69 = _health_pair()
    page = client.get("/verify/start", params={"a": b70.id, "b": b69.id}).text
    assert "เอกสารสาธารณะ" in page                      # D4 ทุกโหมด
    assert "data-source" not in client.get("/").text     # แถบสังเคราะห์เฉพาะโหมดสาธิต
