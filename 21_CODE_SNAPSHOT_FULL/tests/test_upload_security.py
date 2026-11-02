# -*- coding: utf-8 -*-
"""ทดสอบมาตรการรับไฟล์ (OWASP: unrestricted file upload, path traversal)"""
import io

import pytest

from redbook import config
from redbook.storage import files as filestore


def test_detects_real_type_not_extension(xlsx_factory):
    """ไฟล์ PDF ที่ตั้งชื่อเป็น .xlsx ต้องถูกตรวจว่าเป็น pdf ไม่ใช่ xlsx"""
    stored = filestore.save_stream(io.BytesIO(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"),
                                   "หลอกว่าเป็นเอกเซล.xlsx")
    assert stored.kind == "pdf"
    assert stored.stored_name.endswith(".pdf")
    stored.path.chmod(0o666)
    stored.path.unlink()


def test_rejects_disguised_executable():
    with pytest.raises(filestore.UploadRejected) as exc:
        filestore.save_stream(io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00"), "payload.xlsx")
    assert exc.value.event == "upload_rejected_unknown_type"


def test_rejects_html_masquerading_as_pdf():
    """ไฟล์ HTML ที่มีสคริปต์ ต้องถูกปฏิเสธตั้งแต่ชั้นรับไฟล์"""
    payload = b"<html><script>alert(document.cookie)</script></html>"
    with pytest.raises(filestore.UploadRejected):
        filestore.save_stream(io.BytesIO(payload), "report.pdf")


def test_rejects_zip_that_is_not_xlsx():
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "not a workbook")
    buf.seek(0)
    with pytest.raises(filestore.UploadRejected) as exc:
        filestore.save_stream(buf, "book.xlsx")
    assert exc.value.event == "upload_rejected_not_xlsx"


def test_rejects_empty_file():
    with pytest.raises(filestore.UploadRejected) as exc:
        filestore.save_stream(io.BytesIO(b""), "empty.xlsx")
    assert exc.value.event == "upload_rejected_empty"


def test_enforces_size_limit():
    with pytest.raises(filestore.UploadRejected) as exc:
        filestore.save_stream(io.BytesIO(b"%PDF-" + b"A" * 5000), "big.pdf",
                              max_bytes=1024)
    assert exc.value.event == "upload_rejected_too_large"


def test_accepts_real_xlsx_and_renames_internally(xlsx_factory):
    path = xlsx_factory("รายงานงบประมาณ ปี 2570.xlsx")
    with open(path, "rb") as fh:
        stored = filestore.save_stream(fh, "../../../etc/รายงาน.xlsx")
    assert stored.kind == "xlsx"
    # ชื่อภายในต้องไม่มีร่องรอยของชื่อเดิม และต้องอยู่ใต้ UPLOAD_DIR
    assert stored.stored_name.endswith(".xlsx")
    assert "รายงาน" not in stored.stored_name
    assert stored.path.parent == config.UPLOAD_DIR
    # ชื่อที่แสดงผลต้องถูกตัดส่วน path ออกแล้ว
    assert stored.original_name == "รายงาน.xlsx"
    assert len(stored.sha256) == 64
    stored.path.chmod(0o666)
    stored.path.unlink()


@pytest.mark.parametrize("bad", ["../secret.xlsx", "a/b.xlsx", "a\\b.xlsx", "..\\x.pdf"])
def test_path_for_blocks_traversal(bad):
    with pytest.raises(filestore.UploadRejected) as exc:
        filestore.path_for(bad)
    assert exc.value.event == "path_traversal_blocked"


def test_sanitize_display_name_strips_control_chars():
    assert filestore.sanitize_display_name("a\r\nb.xlsx") == "ab.xlsx"
    assert filestore.sanitize_display_name("") == "(ไม่มีชื่อไฟล์)"
    assert filestore.sanitize_display_name("C:\\temp\\x.pdf") == "x.pdf"
