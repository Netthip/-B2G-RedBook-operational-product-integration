# -*- coding: utf-8 -*-
"""privacy 0.2.2 — ตอบ Bo REVIEW 6358440451 (ต่อจาก 0.2.1 ที่ไม่ให้ "https:" นับเป็นไดรฟ์)

1. เส้นทางที่ **ติดหลังตัวอักษร/ตัวเลขโดยไม่มีตัวคั่น** ต้องถูกกลบ (เขตแดนของ 0.2.1 ปล่อยหลุด)
2. **ตัวตรวจเป็นอิสระจากตัวกลบ** — ทุกเทสต์ตรวจด้วยสตริงนกขมิ้น (ชื่อผู้ใช้/ชื่อไฟล์ปลอม) ที่ต้องหายไป
   ไม่ใช้ ``find_absolute_paths`` (regex ตัวเดียวกับตัวกลบ) เป็นหลักฐานอย่างเดียว
3. เส้นทาง/ชื่อใน **query ของ URL** (ดิบ + เข้ารหัส %) และใน **Audit** ตรวจแยกจากการที่ URL ทางการผ่านได้
4. รูปแบบที่รองรับ/ไม่รองรับประกาศไว้ใน :data:`privacy.SUPPORTED_FORMS` · :data:`privacy.UNSUPPORTED_FORMS`
"""
import getpass
import io
import json

import pytest

from test_trial import AG, _env, shelf  # noqa: F401  (fixture ร่วม: ชั้นเล่มสังเคราะห์)
from redbook import privacy
from redbook.storage import files as filestore, repository as repo, source_pdfs
from redbook.storage.db import connect

USER = "zqcanaryuser"           # นกขมิ้น: ห้ามเหลือในผลกลบ (ตรวจด้วย `in` ไม่ใช่ regex ของตัวกลบ)
FILE = "zqsecretfile"


def _gone(out: str) -> bool:
    return USER not in out and FILE not in out


GLUED = [rf"fileC:\Users\{USER}\{FILE}.pdf", f"errC:/Users/{USER}/{FILE}.pdf", rf"x1C:\Users\{USER}\{FILE}",
         rf"_D:\Users\{USER}\{FILE}.xlsx", rf"อ่านC:\Users\{USER}\{FILE}.pdf", rf"path=C:\Users\{USER}\{FILE}.pdf&x=1"]
QUERY = [rf"https://www.bb.go.th/download.php?f=C:\Users\{USER}\{FILE}.pdf",
         f"https://www.bb.go.th/x?p=/Users/{USER}/{FILE}.pdf",
         f"https://www.bb.go.th/x?f=C%3A%5CUsers%5C{USER}%5C{FILE}.pdf",
         f"https://www.bb.go.th/x?f=c%3a%5cUsers%5c{USER}%5c{FILE}.pdf",
         f"https://www.bb.go.th/x?f=C%3A%2FUsers%2F{USER}%2F{FILE}.pdf",
         f"https://www.bb.go.th/x?p=%2FUsers%2F{USER}%2F{FILE}.pdf",
         f"https://www.bb.go.th/x#C:/Users/{USER}/{FILE}.pdf",
         f"file:///C:/Users/{USER}/{FILE}.pdf",
         json.dumps({"p": rf"C:\Users\{USER}\{FILE}.pdf"})]


@pytest.mark.parametrize("raw", GLUED + QUERY)
def test_paths_glued_to_text_or_in_url_queries_leave_no_canary(raw):
    out = privacy.redact_text(raw)
    assert _gone(out), out
    assert privacy.PATH_REMOVED in out
    assert privacy.redact_text(out) == out                      # กลบซ้ำได้ผลเดิม


@pytest.mark.parametrize("url", ["https://www.bb.go.th/download.php?bookid=123&f=dl",
                                 "https://bbstore.bb.go.th/files/2570/vol11.pdf",
                                 "http://www.bb.go.th/topic3.php?gid=860&mid=545", "s3://bucket/key.pdf",
                                 "ftp://files.example/pub/a.pdf"])
def test_official_urls_are_untouched(url):
    assert privacy.redact_text(url) == url


@pytest.mark.parametrize("text", ["เวลา 10:30 น.", "อัตราส่วน 3:4", "ข้อ 2.1/3", "ปี 2569/2570", "a:b", "ratio:1/2"])
def test_ordinary_text_is_untouched(text):
    assert privacy.redact_text(text) == text


def test_url_scheme_still_survives_next_to_a_redacted_path():
    out = privacy.redact_text(rf"https://www.bb.go.th/x?f=C:\Users\{USER}\a.pdf")
    assert out.startswith("https://www.bb.go.th/x?f=") and _gone(out)


def test_supported_and_unsupported_forms_are_declared_and_honest():
    assert len(privacy.SUPPORTED_FORMS) >= 5 and len(privacy.UNSUPPORTED_FORMS) >= 3
    assert privacy.PRIVACY_VERSION == "t1b-privacy-0.2.2"
    # ประกาศว่าไม่รองรับ = ไม่รองรับจริง (ถ้าวันหนึ่งรองรับ ต้องย้ายในประกาศด้วย)
    double = f"https://x.example/?f=C%253A%255CUsers%255C{USER}"
    assert USER in privacy.redact_text(double)
    assert any("%253A" in f for f in privacy.UNSUPPORTED_FORMS)


def test_source_url_with_a_local_path_never_reaches_the_audit_or_the_table(tmp_path):
    """Audit แก้ย้อนหลังไม่ได้ — URL ที่แนบเส้นทางในเครื่องมาใน query ต้องถูกกลบก่อนเขียน · URL ทางการคงอยู่"""
    pid = repo.create_project("privacy 0.2.2", "before_after_reduction", "ข้อมูลสังเคราะห์")
    pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n" \
          b"trailer<</Root 1 0 R>>\n%%EOF\n"
    stored = filestore.save_stream(io.BytesIO(pdf), "x.pdf")
    if stored.kind != "pdf":
        pytest.skip("ตัวเก็บไฟล์ไม่รับ PDF สังเคราะห์ขนาดเล็ก")
    conn = connect()
    try:
        before = conn.execute("SELECT COALESCE(MAX(seq), 0) FROM audit_log").fetchone()[0]
    finally:
        conn.close()
    url = f"https://www.bb.go.th/download.php?bookid=9&f=C%3A%5CUsers%5C{USER}%5C{FILE}.pdf&g=/home/{USER}/x"
    source_pdfs.link(pid, "A", stored, origin=source_pdfs.ORIGIN_OFFICIAL, source_url=url, retrieved_at="2026-10-27")
    conn = connect()
    try:
        rows = [r[0] for r in conn.execute("SELECT detail_json FROM audit_log WHERE seq > ?", (before,))]
        kept = conn.execute("SELECT source_url FROM project_source_pdfs WHERE project_id = ?", (pid,)).fetchone()[0]
    finally:
        conn.close()
    assert rows and all(_gone(r) for r in rows) and _gone(kept)
    assert kept.startswith("https://www.bb.go.th/download.php?bookid=9&f=")
    assert any("www.bb.go.th/download.php?bookid=9" in r for r in rows)


def test_audit_written_by_a_shelf_run_holds_no_local_path_or_username():
    """ทั้งรอบเทียบจากชั้นเล่ม (สังเคราะห์): Audit ที่เกิดขึ้นในรอบนั้นไม่มีชื่อผู้ใช้ของเครื่องหรือเส้นทางชั้นเล่ม
    — ตรวจด้วยค่าจริงของเครื่อง (อิสระจาก regex)"""
    from redbook.services import pdfshelf
    conn = connect()
    try:
        before = conn.execute("SELECT COALESCE(MAX(seq), 0) FROM audit_log").fetchone()[0]
    finally:
        conn.close()
    pdfshelf._once_slots.clear()             # รอบใหม่จริง (ไม่ใช่รอบที่กันกดซ้ำจำไว้จากเทสต์อื่น)
    pdfshelf.start("S_2570_draft", "S_2570_act", AG)
    conn = connect()
    try:
        text = "\n".join(r[0] for r in conn.execute("SELECT detail_json || ' ' || object_id FROM audit_log "
                                                    "WHERE seq > ?", (before,)))
    finally:
        conn.close()
    assert text
    user = getpass.getuser()
    d = str(pdfshelf.shelf_dir())
    assert user.lower() not in text.lower()
    assert d not in text and d.replace("\\", "/") not in text and d.replace("\\", "\\\\") not in text
