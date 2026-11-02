# -*- coding: utf-8 -*-
"""GET /api/books — คลังเล่มสำหรับหน้าแรกของ /r: อ่านอย่างเดียว · ไม่มี path ในเครื่อง · เปิดได้บนเซิร์ฟเวอร์สาย PDF"""
import re

from fastapi.testclient import TestClient

from test_trial import client, shelf  # noqa: F401  (fixture ร่วม)


def test_books_list_comes_from_the_catalog_without_local_paths(client):
    r = client.get("/api/books")
    assert r.status_code == 200
    d = r.json()
    assert d["years"] and d["books"]
    b = d["books"][0]
    for k in ("id", "fiscal_year", "headline", "stage", "stage_label", "type_group", "source_page", "pdf_url"):
        assert k in b
    text = r.text
    assert not re.search(r"[A-Za-z]:\\\\|/Users/|/home/|\\.data", text)       # ไม่หลุด path ในเครื่อง
    assert all(x["source_page"] == "" or x["source_page"].startswith(("http://", "https://")) for x in d["books"])


def test_books_list_is_get_only(client):
    assert client.post("/api/books").status_code in (403, 405)


def test_lane_server_serves_the_book_list():
    from redbook.pdf_lane_app import create_lane_app
    c = TestClient(create_lane_app(guard=False), base_url="http://127.0.0.1:8645")
    assert c.get("/api/books").status_code == 200
    assert c.get("/books").status_code == 404                                  # หน้า Jinja เดิมยังอยู่เฉพาะแอปเต็ม
