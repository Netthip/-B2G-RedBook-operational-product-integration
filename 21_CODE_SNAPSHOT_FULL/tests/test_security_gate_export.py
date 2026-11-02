# -*- coding: utf-8 -*-
"""Security gate — ไฟล์ส่งออก: formula injection ใน XLSX และการเสิร์ฟเป็น attachment"""
import importlib

import pytest
from fastapi.testclient import TestClient

from redbook import config
from redbook.app import create_app
from redbook.export import csv_safe


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


@pytest.mark.parametrize("payload", ["=1+1", "+cmd|' /C calc'!A0", "-2+3", "@SUM(A1)",
                                     "\t=HYPERLINK(\"http://x\")", "=WEBSERVICE(\"http://x\")"])
def test_xlsx_cells_are_text_typed_never_formula(tmp_path, payload):
    import openpyxl
    text, neutral, _, _ = csv_safe.neutralize(payload)
    assert neutral and text.startswith("'")
    write_xlsx = importlib.import_module("exporters.xlsx_writer").write_xlsx
    path = tmp_path / "x.xlsx"
    write_xlsx(path, [("S", [[("s", text, False), ("s", payload, False), ("n", 1, False)]])])
    wb = openpyxl.load_workbook(path)
    ws = wb["S"]
    # แม้ผู้เรียกลืม neutralize (คอลัมน์ 2) ตัวเขียนก็ยังบังคับชนิดเป็นข้อความ ไม่ใช่สูตร
    assert ws.cell(1, 1).data_type == "s" and ws.cell(1, 2).data_type == "s"
    assert ws.cell(1, 2).value == payload
    assert ws.cell(1, 2).number_format == "@"
    wb.close()


def test_export_download_has_attachment_disposition_with_system_name(client):
    config.ensure_dirs()
    name = "exp_gate_test_000.csv"
    (config.EXPORT_DIR / name).write_text("a,b\n1,2\n", encoding="utf-8")
    r = client.get(f"/t1b/exports/{name}")
    assert r.status_code == 200
    cd = r.headers.get("content-disposition", "")
    assert cd.startswith("attachment"), cd
    assert name in cd
    assert r.headers.get("x-content-type-options") == "nosniff"
    # ชื่อที่ไม่ได้มาจากระบบ (ไม่ขึ้นต้น exp_) ถูกปฏิเสธแม้ไฟล์มีอยู่จริง
    (config.EXPORT_DIR / "user_supplied.csv").write_text("x\n", encoding="utf-8")
    r = client.get("/t1b/exports/user_supplied.csv")
    assert r.status_code == 400
