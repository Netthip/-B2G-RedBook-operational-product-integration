# -*- coding: utf-8 -*-
"""Security gate — การอัปโหลดที่ผิดรูป/เป็นอันตราย (SYNTHETIC FIXTURES เท่านั้น)"""
import io
import socket
import threading
import zipfile

import pytest
from fastapi.testclient import TestClient

from redbook.app import create_app
from redbook.readers import excel_reader
from redbook.storage import files as filestore
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD

XLSX_MARKERS = {
    "[Content_Types].xml": b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
    "xl/workbook.xml": b'<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets/></workbook>',
}


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


def _project(client):
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post("/projects/new", data={"name": "upload gate", "mode": "before_after_reduction",
                                           CSRF_FIELD: token}, follow_redirects=False)
    return r.headers["location"].rsplit("/", 1)[-1], token


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_declared_content_type_is_ignored(client, xlsx_factory):
    pid, token = _project(client)
    path = xlsx_factory("real.xlsx")
    with open(path, "rb") as fh:   # ไฟล์จริงเป็น xlsx แต่ประกาศว่าเป็น PDF — ระบบต้องดูไบต์
        r = client.post(f"/projects/{pid}/upload", data={"side": "A", CSRF_FIELD: token},
                        files={"upload": ("real.pdf", fh, "application/pdf")},
                        follow_redirects=False)
    assert r.status_code == 303
    with io.BytesIO(b"just text, not a workbook") as fh:   # ข้อความล้วนประกาศว่าเป็น xlsx
        r = client.post(f"/projects/{pid}/upload", data={"side": "B", CSRF_FIELD: token},
                        files={"upload": ("fake.xlsx", fh,
                                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 400
    assert "Traceback" not in r.text


def test_zip_bomb_ratio_is_rejected():
    members = dict(XLSX_MARKERS)
    members["xl/worksheets/sheet1.xml"] = b"\x00" * (4 * 1024 * 1024)   # บีบอัดได้หลายพันเท่า
    data = _zip_bytes(members)
    with pytest.raises(filestore.UploadRejected) as exc:
        filestore.save_stream(io.BytesIO(data), "bomb.xlsx")
    assert exc.value.event == "upload_rejected_zip_bomb"


def test_zip_with_too_many_members_is_rejected():
    members = dict(XLSX_MARKERS)
    for i in range(filestore.MAX_ZIP_MEMBERS + 50):
        members[f"xl/media/m{i}.bin"] = b"x"
    data = _zip_bytes(members)
    with pytest.raises(filestore.UploadRejected) as exc:
        filestore.save_stream(io.BytesIO(data), "many.xlsx")
    assert exc.value.event == "upload_rejected_zip_too_many_members"


def test_corrupt_zip_is_rejected_safely(client):
    pid, token = _project(client)
    corrupt = b"PK\x03\x04" + b"\x00" * 64 + b"garbage" * 100
    with pytest.raises(filestore.UploadRejected) as exc:
        filestore.save_stream(io.BytesIO(corrupt), "broken.xlsx")
    assert exc.value.event in ("upload_rejected_bad_zip", "upload_rejected_not_xlsx")
    r = client.post(f"/projects/{pid}/upload", data={"side": "A", CSRF_FIELD: token},
                    files={"upload": ("broken.xlsx", io.BytesIO(corrupt), "application/octet-stream")})
    assert r.status_code == 400
    assert "Traceback" not in r.text and "BadZipFile" not in r.text


def test_xlsx_with_external_entity_does_not_fetch_or_crash(xlsx_factory, tmp_path):
    """XXE: สมุดงานที่ฝัง DOCTYPE/entity ภายนอก ต้องไม่ทำให้เรียกออกเครือข่าย และต้องล้มแบบจัดการได้"""
    # ตัวดักฟัง — ถ้า parser ไปดึง entity จะมีการเชื่อมต่อเข้ามา
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(0.2)
    port = srv.getsockname()[1]
    connected = []

    def listen():
        try:
            conn, _ = srv.accept()
            connected.append(True)
            conn.close()
        except OSError:
            pass

    t = threading.Thread(target=listen, daemon=True)
    t.start()

    good = xlsx_factory("good.xlsx")
    evil = tmp_path / "xxe.xlsx"
    with zipfile.ZipFile(good) as zin, zipfile.ZipFile(evil, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "xl/sharedStrings.xml":
                data = data.replace(
                    b"?>",
                    f'?><!DOCTYPE x [<!ENTITY xxe SYSTEM "http://127.0.0.1:{port}/secret">]>'.encode(),
                    1)
                data = data.replace(b"<t>", b"<t>&xxe;", 1)
            zout.writestr(item, data)

    try:
        excel_reader.read_structure(evil)
    except excel_reader.ExcelReadError:
        pass           # ล้มแบบจัดการได้ = ยอมรับ
    t.join(timeout=1.0)
    srv.close()
    assert not connected, "parser พยายามดึง external entity ออกเครือข่าย"
