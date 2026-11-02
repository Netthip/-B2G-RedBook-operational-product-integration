# -*- coding: utf-8 -*-
"""#24 ภาพรวมการเปรียบเทียบ + DEV fixture — regression

หลัก: UI แสดงคู่ตามทะเบียน #27 เท่านั้น (MATCHED) · ข้อมูลสังเคราะห์ต้องมีป้ายทุกหน้า
· A ความสมบูรณ์ชุดเอกสาร แยกจาก B ความต่างเนื้อหา · ไม่มีตัวเลขเนื้อหาก่อนตั้งงานตรวจ
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from redbook.app import create_app
from redbook.services import books as B

ROOT = Path(__file__).resolve().parent.parent
ANCHOR = "bb-2570-18879"
ACT = f"DEV-ACT-{ANCHOR}"


def _fixture_module():
    spec = importlib.util.spec_from_file_location("dev_fixture", ROOT / "scripts" / "build_dev_pair_fixture.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def real_client(tmp_path, monkeypatch):
    monkeypatch.setenv("REDBOOK_DATA_DIR", str(tmp_path))
    B.catalog.cache_clear()
    yield TestClient(create_app())
    B.catalog.cache_clear()


@pytest.fixture()
def dev_client(tmp_path, monkeypatch):
    path = tmp_path / "dev_pair_fixture.json"
    path.write_text(json.dumps(_fixture_module().build(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("REDBOOK_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(B, "CATALOG_PATH", path)
    B.catalog.cache_clear()
    yield TestClient(create_app())
    B.catalog.cache_clear()


# ─────────────────────────────────────────────────────────── fixture
def test_fixture_is_declared_synthetic_and_carries_no_urls_for_fake_books():
    data = _fixture_module().build()
    assert data["fixture"]["synthetic"] is True
    fake = [d for d in data["contract"]["documents"] if d["id"].startswith("DEV-")]
    assert fake and all(d["synthetic"] and d["stage"] == "ACT" for d in fake)
    assert all(not d["pdf"]["url"] and not d["excel"]["urls"] and not d["source_status"]["source_page_url"]
               for d in fake), "เล่มสังเคราะห์ต้องไม่ชี้ลิงก์ทางการ"
    assert {p["status"] for p in data["pairs"]} == {"MATCHED", "REVIEW_REQUIRED", "CANNOT_DETERMINE"}


def test_no_dev_banner_on_real_registry(real_client):
    assert "dev-fixture" not in real_client.get("/books").text


def test_dev_banner_on_every_page(dev_client):
    for url in ("/books", f"/books/{ANCHOR}", f"/verify/start?a={ANCHOR}"):
        assert 'class="dev-fixture"' in dev_client.get(url).text, url


# ─────────────────────────────────────────────────────────── หน้าเปรียบเทียบ
def test_confirmed_pair_shows_registry_confirmation_and_two_worlds(dev_client):
    html = dev_client.get(f"/books/compare?a={ANCHOR}&b={ACT}").text
    assert "pair-status is-confirmed" in html
    assert 'id="world-a"' in html and 'id="world-b"' in html
    assert html.index('id="world-a"') < html.index('id="world-b"')
    # B ยังไม่มีผล — ไม่แต่งตัวเลขก่อนตั้งงานตรวจ
    assert re.findall(r'class="pm-val"[^>]*>([^<]*)<', html) == ["—"] * 6
    assert "DEV · ข้อมูลสังเคราะห์" in html
    assert f"/verify/start?a={ANCHOR}&amp;b={ACT}" in html


def test_user_chosen_pair_says_cannot_confirm(dev_client):
    html = dev_client.get("/books/compare?a=bb-2570-18878&b=bb-2569-17723").text  # REVIEW_REQUIRED
    assert "pair-status is-user" in html and "ยังยืนยันคู่เอกสารไม่ได้" in html


def test_status_never_relies_on_color_alone(dev_client):
    html = dev_client.get(f"/books/compare?a={ANCHOR}&b={ACT}").text
    for m in re.finditer(r'<span class="st st-(\w+)"><span class="st-mark"[^>]*>(.)</span>([^<]+)</span>', html):
        assert m.group(2) in "✓?!" and m.group(3).strip()
    assert "ไม่ได้แปลว่าไม่มีเอกสาร" in html


# ─────────────────────────────────────────────────────────── ตั้งงานตรวจ
def test_start_suggests_only_registry_confirmed_pairs(real_client):
    """ทะเบียนจริงยังไม่มี pairs[] ⇒ ห้ามแนะนำคู่จากชื่อหน่วยรับงบ (pair_key = การเดา)"""
    html = real_client.get(f"/verify/start?a={ANCHOR}").text
    assert "คู่ที่แนะนำ" not in html
    assert "ยังไม่มีคู่ที่ทะเบียนแหล่งทางการยืนยัน" in html


def test_start_suggests_matched_counterpart_from_registry(dev_client):
    html = dev_client.get(f"/verify/start?a={ANCHOR}").text
    assert "คู่ที่แนะนำ — ทะเบียนแหล่งทางการยืนยันแล้ว" in html
    assert f"b={ACT}" in html and "b=bb-2569-17724" in html


def test_start_labels_synthetic_side_and_no_empty_pdf_link(dev_client):
    html = dev_client.get(f"/verify/start?a={ANCHOR}&b={ACT}").text
    assert html.count("เอกสารสาธารณะ</span>") == 1          # เฉพาะฝั่ง ร่าง (ทะเบียนสาธารณะ)
    assert "DEV · ข้อมูลสังเคราะห์" in html
    assert 'href=""' not in html
    assert "PDF: ยังไม่พบลิงก์" in html
    assert html.count('class="stage-chip s-draft"') >= 1 and html.count('class="stage-chip s-act"') >= 1


# ─────────────────────────────────────────────────────────── สถานะว่าง / แถบเอกสาร
def test_compare_without_book_is_an_empty_state_not_an_error(real_client):
    r = real_client.get("/books/compare")
    assert r.status_code == 200 and "ยังไม่ได้เลือกเล่มที่จะเปรียบเทียบ" in r.text
    assert "รหัสอ้างอิงเหตุการณ์" not in r.text
    r = real_client.get("/books/compare?a=not-a-book")
    assert r.status_code == 404 and "ไม่พบเล่มที่ระบุในคลัง" in r.text


def test_project_refs_label_synthetic_book_and_show_stage(dev_client):
    page = dev_client.get(f"/verify/start?a={ANCHOR}&b={ACT}").text
    token = re.search(r'name="csrf_token" value="([^"]+)"', page) or re.search(r'value="([^"]{20,})"', page)
    r = dev_client.post("/verify/start", data={"a": ANCHOR, "b": ACT, "name": "ทดสอบ",
                                               "csrf_token": token.group(1)}, follow_redirects=True)
    assert "/projects/" in str(r.url)
    assert 'class="ref-strip"' in r.text
    assert "DEV · ข้อมูลสังเคราะห์" in r.text and r.text.count("เอกสารสาธารณะ</span>") == 1
    assert 'class="stage-chip s-act"' in r.text and 'href=""' not in r.text


# ─────────────────────────────────────────────────────────── เงื่อนไข Bo ก่อน merge
def test_matched_pair_is_worded_as_metadata_confirmed_only(dev_client):
    html = dev_client.get(f"/books/compare?a={ANCHOR}&b={ACT}").text
    assert "metadata-confirmed" in html and "ยังไม่ได้เทียบเนื้อหา" in html


def test_draft_act_pair_never_shows_reduction_label(dev_client):
    """ร่าง → พ.ร.บ. ไม่ใช่การปรับลด — เปลี่ยนเฉพาะคำบนจอ โหมดใน workflow คงเดิม"""
    html = dev_client.get(f"/verify/start?a={ANCHOR}&b={ACT}").text
    assert "ก่อนเทียบหลังปรับลด" not in html and "ตรวจความแตกต่างระหว่างร่างและ พ.ร.บ." in html
    token = re.search(r'name="csrf_token" value="([^"]+)"', html) or re.search(r'value="([^"]{20,})"', html)
    r = dev_client.post("/verify/start", data={"a": ANCHOR, "b": ACT, "name": "ทดสอบ",
                                               "csrf_token": token.group(1)}, follow_redirects=True)
    assert "ก่อนเทียบหลังปรับลด" not in r.text and "ฝั่ง A - ฉบับก่อนปรับลด" not in r.text
    assert "ตรวจความแตกต่างระหว่างร่างและ พ.ร.บ." in r.text and "ฝั่ง A - ร่าง พ.ร.บ." in r.text
    from redbook.storage import repository as repo
    pid = str(r.url).rstrip("/").rsplit("/", 1)[-1]
    assert repo.get_project(pid)["mode"] == "before_after_reduction"                 # workflow เดิม
    home = dev_client.get("/").text
    row = next(chunk for chunk in home.split("<tr>") if f"/projects/{pid}" in chunk)
    assert "ก่อนเทียบหลังปรับลด" not in row and "ตรวจความแตกต่างระหว่างร่างและ พ.ร.บ." in row


def test_same_year_same_stage_keeps_original_label():
    from redbook.app import mode_display
    from types import SimpleNamespace as N
    d = N(fiscal_year=2570, stage_code="draft")
    assert mode_display("before_after_reduction", d, d) == "ก่อนเทียบหลังปรับลด"
    assert mode_display("before_after_reduction", d, N(fiscal_year=2570, stage_code="act"))         == "ตรวจความแตกต่างระหว่างร่างและ พ.ร.บ."


# ─────────────────────────────────────────────────────────── #27 รอบ 2: excel.source_status
@pytest.mark.parametrize("src, want", [("FOUND", "ok"), ("UNVERIFIED", "unverified"),
                                       ("BROKEN_LINK", "broken"), ("NOT_LISTED", "not_listed"),
                                       ("NOT_FOUND", "missing")])
def test_excel_source_status_wins_over_legacy_status(src, want):
    d = {"id": "x", "year": 2570, "stage": "DRAFT", "book_label": "ฉบับที่ 3 เล่มที่ 1",
         "pdf": {"url": "https://www.bb.go.th/x", "status": "FOUND"},
         "excel": {"status": "EXCEL_AVAILABLE", "source_status": src,
                   "urls": ["https://drive.google.com/file/d/x/view"] if src in ("FOUND", "UNVERIFIED") else [],
                   "review_flags": ["SOME_FLAG"]}}
    b = B._contract_book(d)
    assert b.excel_status == want and b.excel_flags == ("SOME_FLAG",)
    assert b.excel_openable == (want in ("ok", "unverified"))


def test_unverified_excel_is_not_counted_as_having_excel():
    d = {"id": "x", "year": 2570, "stage": "DRAFT", "book_label": "",
         "excel": {"status": "EXCEL_AVAILABLE", "source_status": "UNVERIFIED", "urls": ["https://x/y"]}}
    cat = B.Catalog(version="t", generated_at="", source="", years=(2570,), books=(B._contract_book(d),))
    assert cat.summary["excel"] == 0 and cat.summary["excel_unverified"] == 1


@pytest.mark.parametrize("first, second", [(ANCHOR, ACT), (ACT, ANCHOR)])
def test_same_year_pair_puts_draft_on_side_a_from_either_start(dev_client, first, second):
    """เริ่มจากเล่ม พ.ร.บ. ต้องได้ A = ร่าง · B = พ.ร.บ. เหมือนเริ่มจากร่าง (ป้ายไม่กลับเป็นปรับลด)"""
    from redbook.app import is_draft_act, mode_display
    p = B.make_pair(B.catalog(), first, second)
    assert (p.a.id, p.b.id) == (ANCHOR, ACT) and is_draft_act(p.a, p.b)
    assert p.mode == "before_after_reduction"                                    # workflow เดิม
    assert mode_display(p.mode, p.a, p.b) == "ตรวจความแตกต่างระหว่างร่างและ พ.ร.บ."
    html = dev_client.get(f"/verify/start?a={first}&b={second}").text
    assert "ก่อนเทียบหลังปรับลด" not in html
