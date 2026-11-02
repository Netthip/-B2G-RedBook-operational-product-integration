# -*- coding: utf-8 -*-
"""Library UI (ต่อจาก #24) — แท็บปี/ขั้น · ป้ายไฟล์ · ทางเข้าเปรียบเทียบ · สถานะว่าง/ขาด/เสีย

หลักที่ทดสอบ: UI แสดงตามข้อมูลทะเบียน "ไม่เดา" — ไม่มี พ.ร.บ./Excel/หน่วยงาน = บอกว่าไม่มี
และไม่จับคู่ ร่าง↔พ.ร.บ. เอง (non-goal · คู่มาจากทะเบียน #27 เท่านั้น)
"""
from __future__ import annotations

import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from redbook.app import create_app
from redbook.services import books as B


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REDBOOK_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def _book(**kw) -> B.Book:
    base = B.catalog().books[0]
    return replace(base, **kw)


# ─────────────────────────────────────────────────────────── สัญญาข้อมูล
def test_stage_code_reads_registry_text_without_guessing():
    assert _book(stage="ร่าง พ.ร.บ. (เผยแพร่ต่อสาธารณะ)").stage_code == "draft"
    assert _book(stage="พ.ร.บ. งบประมาณรายจ่าย").stage_code == "act"
    assert _book(stage="").stage_code == ""
    assert _book(stage="").stage_label == "ไม่ระบุขั้น"


def test_file_status_and_excel_detection():
    assert _book(pdf_url="").pdf_status == "missing"
    assert _book(link_check={}).pdf_status == "unchecked"
    assert _book(link_check={"status": 404, "is_pdf": False}).pdf_status == "broken"
    b = _book(files=({"url": "https://x/a.xlsx", "label": "ไฟล์"},))
    assert b.excel_status == "ok" and len(b.excel_files) == 1
    # ไม่พบไฟล์ Excel ในรายการ ≠ "ไม่มี" — ทะเบียนเดิมไม่เคยค้น Excel
    assert _book(files=({"url": "https://x/a.pdf", "label": "PDF"},)).excel_status == "unchecked"
    assert _book(excel_state="NOT_LISTED").excel_status == "not_listed"
    assert _book(excel_state="BROKEN_LINK").excel_status == "broken"
    assert _book(pdf_state="NOT_FOUND").pdf_status == "missing"


def test_current_registry_is_all_draft_pdf_only():
    """ตัวเลขที่หน้าจออ้าง ต้องตรงกับทะเบียนจริง (วัดจากต้นทาง ไม่ใช่ค่าที่เขียนไว้)"""
    sm = B.catalog().summary
    assert sm["books"] == len(B.catalog().books)
    assert sm["draft"] == sm["books"] and sm["act"] == 0
    assert sm["excel"] == 0


# SYNTHETIC TEST FIXTURE — รูปตามสัญญา #27 0.1.0 (ร่าง) ที่เลน #27 แจ้งมา ไม่ใช่ข้อมูลจริง
def _doc(id_, year, stage, **kw):
    d = {"id": id_, "year": year, "stage": stage,
         "stage_label": {"DRAFT": "ร่าง พ.ร.บ.", "ACT": "พ.ร.บ."}[stage],
         "ministry": ["กระทรวงตัวอย่าง"], "agency": None, "doc_type": "expenditure_by_ministry",
         "doc_type_label": "รายจ่ายรายกระทรวง", "book_label": "ฉบับที่ 3 เล่มที่ 4",
         "book_title": "เล่มสังเคราะห์", "source_status": {"source_page_url": "https://example.test/p",
                                                         "verified_date": "2026-10-07"},
         "pdf": {"status": "FOUND", "url": "https://example.test/a.pdf"},
         "excel": {"status": "NOT_LISTED", "urls": []}}
    d.update(kw)
    return d


def _contract(tmp_path):
    raw = {"contract_version": "source-contract-0.1.0", "contract": {"documents": [
        _doc("d70", 2570, "DRAFT"), _doc("a70", 2570, "ACT"),
        _doc("d69", 2569, "DRAFT", excel={"status": "EXCEL_AVAILABLE", "urls": ["https://example.test/x.xlsx"]}),
        _doc("d68", 2568, "DRAFT", excel={"status": "BROKEN_LINK", "urls": []},
             pdf={"status": "BROKEN_LINK", "url": "https://example.test/b.pdf"}),
    ], "pairs": [
        {"kind": "SAME_YEAR", "status": "MATCHED", "a": {"ids": ["d70"]}, "b": {"ids": ["a70"]}},
        {"kind": "CROSS_YEAR", "status": "MATCHED", "a": {"ids": ["d69"]}, "b": {"ids": ["d70"]}},
        {"kind": "CROSS_YEAR", "status": "REVIEW_REQUIRED", "a": {"ids": ["d68"]}, "b": {"ids": ["d69"]}},
    ]}}
    raw["pairs"] = raw["contract"].pop("pairs")          # รูปจริงของ 850d582: pairs[] ระดับบนสุด
    p = tmp_path / "source_registry.json"
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return B.load(p)


def test_pdf_found_without_url_is_not_a_link(client):
    b = _book(pdf_state="FOUND", pdf_url="")
    assert b.pdf_status == "ok" and not b.pdf_openable
    assert _book(pdf_state="UNCHECKED").pdf_openable


def test_synthetic_document_flag(tmp_path):
    raw = {"contract_version": "source-contract-0.1.0", "contract": {"documents": [_doc("DEV-ACT-1", 2570, "ACT", synthetic=True,
                                           pdf={"status": "UNCHECKED"})], "pairs": []}}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    b = B.load(p).books[0]
    assert b.synthetic and not b.pdf_openable


def test_same_year_draft_act_warning_is_not_called_reduction(tmp_path):
    cat = _contract(tmp_path)
    pair = B.make_pair(cat, "d70", "a70")
    assert any("ร่าง พ.ร.บ. → พ.ร.บ." in w for w in pair.warnings)
    assert not any("ปรับลด" in w for w in pair.warnings)


def test_contract_loader_reads_27_vocabulary(tmp_path):
    cat = _contract(tmp_path)
    assert cat.years == (2568, 2569, 2570)
    d70, a70, d69, d68 = (cat.get(i) for i in ("d70", "a70", "d69", "d68"))
    assert (d70.stage_code, a70.stage_code) == ("draft", "act")
    assert d70.doc_no == "3" and d70.volume == "4"
    assert d70.excel_status == "not_listed" and d69.excel_status == "ok"
    assert d68.excel_status == "broken" and d68.pdf_status == "broken"
    assert d70.agencies == ()


def test_only_matched_pairs_are_offered(tmp_path):
    cat = _contract(tmp_path)
    d70, a70, d69, d68 = (cat.get(i) for i in ("d70", "a70", "d69", "d68"))
    assert cat.counterpart(d70).id == "a70" and cat.counterpart(a70).id == "d70"   # ย้อนทางได้
    assert [b.id for b in cat.confirmed_other_years(d70)] == ["d69"]
    assert cat.confirmed_other_years(d68) == []                 # REVIEW_REQUIRED ≠ คู่
    pend = cat.pending_pairs(d68)
    assert len(pend) == 1 and pend[0].status_label == "อาจเกี่ยวข้อง — รอยืนยัน"


def test_legacy_catalog_has_no_pairs():
    """ทะเบียนเดิม (#24) ไม่มี pairs[] ⇒ UI ไม่เสนอคู่ใด ๆ แม้ชื่อหน่วยรับงบจะตรงกัน"""
    cat = B.load(B.Path(B.__file__).resolve().parent.parent / "data" / "book_catalog.json")
    assert cat.pairs == ()
    assert all(cat.confirmed_other_years(b) == [] and cat.counterpart(b) is None for b in cat.books)


def test_stage_and_file_filters_count_independently():
    cat = B.catalog()
    r = B.search(cat, B.Query(stage="act"))
    assert r.total == 0 and r.stage_counts["draft"] == len(cat.books)
    r = B.search(cat, B.Query(file="excel"))
    assert r.total == 0 and r.file_counts["pdf"] > 0
    r = B.search(cat, B.Query(year=2570, file="pdf", view="cards"))
    assert r.total == r.year_counts[2570] > 0


def test_query_rejects_unknown_stage_and_file():
    q = B.Query.from_params({"stage": "x", "file": "<b>"}, (2570,))
    assert q.stage == "" and q.file == ""


# ─────────────────────────────────────────────────────────── หน้าจอ
def test_library_has_year_and_stage_tabs(client):
    t = client.get("/books").text
    for y in ("2570", "2569", "2568"):
        assert f'year={y}' in t
    assert 'aria-label="ขั้นของเอกสาร"' in t and "stage=act" in t and "stage=draft" in t
    assert 'class="stat-strip"' in t


def test_card_shows_metadata_badges_and_four_actions(client):
    t = client.get("/books", params={"view": "cards", "year": 2570}).text
    assert 'class="stage-chip s-draft"' in t
    assert "asset official" in t and "Excel ยังไม่ตรวจ" in t
    assert "ไม่มี Excel" not in t                          # ไม่อ้างว่า "ไม่มี" เมื่อยังไม่ได้ตรวจ
    assert "ดูรายละเอียด" in t and "เปิด PDF" in t and "เปรียบเทียบ" in t


def test_act_tab_explains_missing_data(client):
    t = client.get("/books", params={"stage": "act"}).text
    assert "ยังไม่มีเล่มขั้น พ.ร.บ. ในทะเบียน" in t
    assert "ไม่สร้างหรือเดาคู่เอง" in t


def test_excel_filter_explains_missing_data(client):
    t = client.get("/books", params={"file": "excel"}).text
    assert "ยังไม่มีเล่มที่ทะเบียนยืนยันว่ามี Excel" in t and "ไม่ได้แปลว่าไม่มี" in t


def test_agency_filter_disabled_with_reason_when_registry_has_none(client):
    t = client.get("/books").text
    assert 'id="agency" disabled' in t and "ยังไม่มีข้อมูลระดับหน่วยงาน" in t


def test_compare_entry_states(client):
    b = B.catalog().books[0]
    t = client.get("/books/compare", params={"a": b.id}).text
    assert "ร่าง พ.ร.บ. → พ.ร.บ." in t and "ยังไม่มีคู่ที่ยืนยันจากข้อมูลเล่ม" in t
    assert "ยังไม่มีคู่ปีที่ทะเบียนยืนยัน" in t
    assert f"/books/compare?a={b.id}&amp;b=" not in t       # ไม่เสนอคู่ที่เดาเอง
    assert client.get("/books/compare").status_code == 200       # ยังไม่เลือกเล่ม = สถานะว่าง (#24 P3)
    assert client.get("/books/compare", params={"a": "nope"}).status_code == 404
    assert client.get("/books/compare", params={"a": b.id, "b": b.id}).status_code == 400


def test_detail_shows_stage_pair_and_related(client):
    b = next(x for x in B.catalog().books if x.ministries)
    t = client.get(f"/books/{b.id}").text
    assert 'class="stage-pair"' in t
    assert "/books/compare?a=" in t and "ตั้งงานตรวจโดยอ้างอิงเล่มนี้" in t
    # คำตัดสิน Bo: ไม่มีความสัมพันธ์ที่เดาจากชื่อ (ช่วยค้นหา / หน่วยรับงบเดียวกัน) บนหน้ารายละเอียด
    assert "maybe-related" not in t and "ช่วยค้นหาเอกสารปีอื่น" not in t
    assert "ที่ระบุหน่วยรับงบเดียวกัน" not in t


def test_thumbnail_route_only_serves_registry_ids(client, monkeypatch, tmp_path):
    b = B.catalog().books[0]
    monkeypatch.setattr(B, "THUMB_DIR", tmp_path)
    assert client.get(f"/books/thumb/{b.id}.jpg").status_code == 404     # ยังไม่มีภาพ
    (tmp_path / f"{b.id}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    r = client.get(f"/books/thumb/{b.id}.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert client.get("/books/thumb/..%2F..%2Fsecret.jpg").status_code == 404
    assert client.get("/books/thumb/nope.jpg").status_code == 404


def test_states_page_labels_every_sample_and_has_no_live_links(client):
    t = client.get("/books/states").text
    samples = B.state_samples(B.catalog())
    assert t.count("ตัวอย่างสถานะ ·") == len(samples) >= 6
    for s in samples:
        assert f'href="/books/{s.id}"' not in t


def test_catalog_failure_shows_error_page(client, monkeypatch):
    def boom():
        raise OSError("gone")
    monkeypatch.setattr(B, "catalog", boom)
    r = client.get("/books")
    assert r.status_code == 503 and "โหลดทะเบียนเล่มไม่สำเร็จ" in r.text


def test_pick_from_compare_returns_to_compare(client):
    shown = B.search(B.catalog(), B.Query(view="cards")).books
    a, b = shown[0], shown[1]
    t = client.get("/books", params={"pick": f"{a.id}~cmp", "view": "cards"}).text
    assert f"/books/compare?a={a.id}&amp;b={b.id}" in t and "กลับไปหน้าเปรียบเทียบ" in t
    t = client.get("/books", params={"pick": a.id, "view": "cards"}).text   # #24 เดิมไม่เปลี่ยน
    assert f"/verify/start?a={a.id}&amp;b={b.id}" in t


def test_synthetic_flag_and_catalog_env(tmp_path, monkeypatch):
    raw = json.loads(B.CATALOG_PATH.read_text(encoding="utf-8"))
    assert B.load().synthetic is False                     # ทะเบียนจริง
    raw["fixture"] = {"synthetic": True}
    p = tmp_path / "fx.json"
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    assert B.load(p).synthetic is True
    c = _contract(tmp_path)
    assert c.synthetic is False
    import importlib
    monkeypatch.setenv("REDBOOK_BOOK_CATALOG", str(p))
    mod = importlib.reload(B)
    try:
        assert mod.CATALOG_PATH == p
    finally:
        monkeypatch.delenv("REDBOOK_BOOK_CATALOG")
        importlib.reload(B)


def test_contract_found_pdf_is_not_reported_broken(tmp_path, client, monkeypatch):
    cat = _contract(tmp_path)
    d70 = cat.get("d70")
    assert d70.link_ok is True and d70.pdf_status == "ok"
    assert cat.get("d68").link_ok is False
    assert _book(pdf_state="UNCHECKED").link_ok is None
    monkeypatch.setattr(B, "catalog", lambda: cat)
    t = client.get("/books/d70").text
    assert "เปิดไม่ได้เมื่อตรวจ" not in t and "พบ PDF" in t


def test_synthetic_card_has_no_official_badge(tmp_path, client, monkeypatch):
    raw = {"contract_version": "source-contract-0.1.0", "contract": {"documents": [_doc("DEV-ACT-1", 2570, "ACT", synthetic=True,
                                           pdf={"status": "UNCHECKED"})], "pairs": []}}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    cat = B.load(p)
    monkeypatch.setattr(B, "catalog", lambda: cat)
    t = client.get("/books", params={"view": "cards"}).text
    assert "DEV · ข้อมูลสังเคราะห์" in t and "ไม่ใช่เอกสารทางการ" in t
    assert "asset official" not in t
    d = client.get("/books/DEV-ACT-1").text
    assert "ข้อมูลสังเคราะห์สำหรับสาธิต" in d and "PDF เปิดจากเว็บไซต์" not in d


def test_contract_excel_urls_without_extension_and_types(tmp_path, client, monkeypatch):
    """ทะเบียนจริงของ #27: ลิงก์ Excel เป็นหน้า Google Drive (ไม่มีนามสกุล) · บางเล่มมีหลายไฟล์"""
    drive = ["https://drive.example.test/file/d/a/view", "https://drive.example.test/file/d/b/view"]
    raw = {"contract_version": "source-contract-0.1.0", "contract": {"documents": [
        _doc("x1", 2570, "DRAFT", excel={"status": "EXCEL_AVAILABLE", "urls": drive[:1],
                                         "verification_level": "EXTERNAL_VIEWER_PAGE_OPENS_FILE_NOT_VERIFIED"}),
        _doc("x2", 2570, "DRAFT", excel={"status": "EXCEL_AVAILABLE", "urls": drive}),
        _doc("x3", 2570, "ACT", doc_type="appropriation_law", book_label="ตัวบท พ.ร.บ."),
        _doc("x4", 2570, "DRAFT", doc_type="en_bill", book_label="Budget Bill"),
    ]}, "pairs": []}
    p = tmp_path / "x.json"
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    cat = B.load(p)
    x1, x2, x3, x4 = (cat.get(i) for i in ("x1", "x2", "x3", "x4"))
    assert [f["url"] for f in x1.excel_files] == drive[:1] and len(x2.excel_files) == 2
    assert "ยังไม่ได้ยืนยันตัวไฟล์" in x1.excel_note
    assert x3.type_group == "bill" and x4.type_group == "english"
    monkeypatch.setattr(B, "catalog", lambda: cat)
    t = client.get("/books", params={"view": "cards"}).text
    assert f'href="{drive[0]}"' in t                       # ไฟล์เดียว → เปิดตรง
    assert 'href="/books/x2#files"' in t                   # หลายไฟล์ → ไปเลือกที่หน้ารายละเอียด
    d = client.get("/books/x1").text
    assert "เปิด Excel ทางการ" not in d and "ยังไม่ได้ยืนยันตัวไฟล์" in d


def test_unknown_contract_version_fails_closed(tmp_path, client, monkeypatch):
    for ver in ("source-contract-0.2.0", None):
        raw = {"contract": {"documents": [_doc("z", 2570, "DRAFT")]}, "pairs": []}
        if ver:
            raw["contract_version"] = ver
        p = tmp_path / "v.json"
        p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(ValueError):
            B.load(p)
    monkeypatch.setattr(B, "catalog", lambda: B.load(p))
    r = client.get("/books")
    assert r.status_code == 503 and "โหลดทะเบียนเล่มไม่สำเร็จ" in r.text
