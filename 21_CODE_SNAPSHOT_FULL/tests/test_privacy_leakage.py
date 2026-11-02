# -*- coding: utf-8 -*-
"""สัญญาความเป็นส่วนตัว — กันเนื้อหาสมุดงาน เส้นทางไฟล์ และข้อผิดพลาดภายในรั่ว

🔴 คำสั่ง Bo · `BO REVIEW COMPLETE` (Issue #1)

    LANE B ข้อ 1 — *"tests preventing workbook content, absolute user paths,
    and raw internal exceptions from leaking into pages/logs"*
    SECURITY PRIORITY ข้อ 2 · 4

**สิ่งที่ชุดนี้วัด**

===  ================================================  ==========================
 #   สัญญา                                              ขอบเขต
===  ================================================  ==========================
 1   เส้นทางสัมบูรณ์ห้ามปรากฏ                              หน้าเว็บ · ล็อก · manifest
 2   ข้อผิดพลาดภายในดิบ ๆ ห้ามถึงผู้ใช้                     หน้าเว็บ
 3   เนื้อหาสมุดงานห้ามไหลเข้าล็อกหรือแฟ้มที่แชร์             ล็อก · manifest
===  ================================================  ==========================

🔴 ข้อ 3 **ไม่ได้**ห้ามแสดงเนื้อหาบนหน้าจอที่ผู้ตรวจเปิดดูเอง — นั่นคือตัวงาน
สิ่งที่ห้ามคือเนื้อหาไหลไปอยู่ในแฟ้มที่ถูกแนบส่งต่อโดยไม่มีใครตั้งใจ

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานในไฟล์นี้แต่งขึ้นทั้งหมด

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from redbook import config, privacy
from redbook.app import create_app
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
#  ① เครื่องมือกลบเส้นทาง
# ══════════════════════════════════════════════════════════════════════════════


def test_p1_known_anchor_becomes_symbolic_token():
    p = config.DATA_DIR / "uploads" / "ab12cd34.xlsx"
    got = privacy.redact_path(p)
    assert got == "<DATA_DIR>/uploads/ab12cd34.xlsx"
    # 🔴 อ่านชื่อผู้ใช้จากเครื่องตอนรัน ไม่ฝังไว้ในซอร์ส
    # ได้สองอย่างพร้อมกัน — ซอร์สไม่มีชื่อผู้ใช้ และด่านนี้ใช้ได้กับทุกเครื่อง
    assert Path.home().name.lower() not in got.lower()


def test_p2_home_directory_is_redacted():
    p = Path.home() / "Downloads" / "งบ2570.xlsx"
    got = privacy.redact_path(p)
    assert got.startswith("<HOME>/")
    assert privacy.find_absolute_paths(got) == []


def test_p3_unknown_absolute_path_keeps_only_the_leaf():
    got = privacy.redact_path(r"D:\งานลับ\หน่วยงาน ก\แฟ้ม.xlsx")
    assert got == "<path-removed>/แฟ้ม.xlsx"
    assert "งานลับ" not in got


def test_p4_posix_absolute_path_is_redacted_on_windows_too():
    """🔴 manifest ที่สร้างบนเครื่องหนึ่งถูกอ่านบนอีกระบบหนึ่งได้เสมอ

    การกลบจึงต้องตัดสินจาก **รูปแบบข้อความ** ไม่ใช่จากระบบไฟล์ที่กำลังรันอยู่
    """
    got = privacy.redact_path("/home/someone/data/wb.xlsx")
    assert got.startswith("<path-removed>/") or got.startswith("<HOME>/")
    assert "someone" not in got


def test_p5_relative_path_is_left_alone():
    assert privacy.redact_path("docs/report.md") == "docs/report.md"


def test_p6_paths_embedded_in_free_text_are_all_redacted():
    msg = (r"เปิดแฟ้ม C:\Users\someone\a.xlsx ไม่ได้ "
           r"และสำรองที่ \\srv01\share\b.xlsx ก็เสีย")
    got = privacy.redact_text(msg)
    assert privacy.find_absolute_paths(got) == [], got
    assert "someone" not in got
    assert "srv01" not in got


def test_p7_unc_path_is_recognised_as_absolute():
    got = privacy.redact_path(r"\\fileserver\budget\2570\wb.xlsx")
    assert got == "<path-removed>/wb.xlsx"


def test_p8_nested_structures_are_redacted_recursively():
    payload = {
        "run": {"input": str(config.DATA_DIR / "uploads" / "x.xlsx")},
        "notes": [r"อ่านจาก C:\Users\someone\y.xlsx"],
        "count": 12,
    }
    got = privacy.redact_obj(payload)
    assert privacy.find_absolute_paths(json.dumps(got, ensure_ascii=False)) == []
    assert got["count"] == 12, "ค่าที่ไม่ใช่ข้อความต้องไม่ถูกแตะ"


def test_p9_shareable_manifest_also_drops_the_filename():
    """ชื่อแฟ้มที่ผู้ปฏิบัติงานตั้งเองมีชื่อหน่วยงานอยู่ — ถือเป็นเนื้อหาเอกสาร"""
    got = privacy.redact_obj(
        {"original_name": "AO_21011_ สวรส69.xlsx", "size_bytes": 1},
        filenames=True)
    assert got["original_name"] == "<path-removed>.xlsx"
    assert "21011" not in got["original_name"]


def test_p10_assert_shareable_refuses_a_leaking_payload():
    with pytest.raises(ValueError) as err:
        privacy.assert_shareable({"p": r"C:\Users\someone\z.xlsx"}, where="manifest")
    # 🔴 ข้อความ error เองต้องไม่รั่วซ้ำ
    assert "someone" not in str(err.value)
    assert privacy.find_absolute_paths(str(err.value)) == []


def test_p11_assert_shareable_passes_a_clean_payload():
    privacy.assert_shareable({"p": "<DATA_DIR>/uploads/x.xlsx", "n": 3})


def test_p12_anchor_list_follows_config_at_call_time(monkeypatch, tmp_path):
    """🔴 ห้าม cache จุดยึด — ย้ายโฟลเดอร์ข้อมูลแล้วต้องยังกลบได้"""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "moved")
    got = privacy.redact_path(tmp_path / "moved" / "uploads" / "x.xlsx")
    assert got == "<DATA_DIR>/uploads/x.xlsx"


# ══════════════════════════════════════════════════════════════════════════════
#  ② ล็อกของแอป
# ══════════════════════════════════════════════════════════════════════════════


def _app_log_text() -> str:
    p = config.LOG_DIR / "app.log"
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def test_p20_log_formatter_redacts_absolute_paths(tmp_path):
    from redbook.app import RedactingFormatter

    rec = logging.LogRecord(
        "redbook", logging.WARNING, __file__, 1,
        r"เปิด C:\Users\someone\secret\wb.xlsx ไม่สำเร็จ", (), None)
    line = RedactingFormatter("%(message)s").format(rec)
    assert privacy.find_absolute_paths(line) == [], line
    assert "someone" not in line


def test_p21_log_formatter_redacts_traceback_frames():
    """🔴 ``log.exception`` แนบ traceback ที่มีเส้นทางไฟล์ของ *ทุก* เฟรม"""
    from redbook.app import RedactingFormatter

    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        rec = logging.LogRecord("redbook", logging.ERROR, __file__, 1,
                                "unhandled", (), sys.exc_info())
    line = RedactingFormatter("%(message)s").format(rec)
    assert "Traceback" in line, "ต้องยังมี traceback ไว้ให้ผู้ดูแลอ่าน"
    assert privacy.find_absolute_paths(line) == [], line


def test_p22_upload_flow_leaves_no_absolute_path_in_the_log(client, xlsx_factory):
    """เส้นทางทำงานจริงหนึ่งเส้น แล้วอ่านล็อกทั้งไฟล์"""
    before = len(_app_log_text())
    _create_and_upload(client, xlsx_factory)
    after = _app_log_text()[before:]
    assert privacy.find_absolute_paths(after) == [], after[:800]


# ══════════════════════════════════════════════════════════════════════════════
#  ③ หน้าเว็บ
# ══════════════════════════════════════════════════════════════════════════════


def _create_and_upload(client, xlsx_factory):
    """เดินเส้นทางจริงหนึ่งเส้น: สร้างงาน → อัปโหลดสองฝั่ง → precheck

    ตั้งใจตั้ง **ชื่อไฟล์ที่มีชื่อหน่วยงานและปี** เหมือนแฟ้มจริงของผู้ปฏิบัติงาน
    เพื่อให้ทดสอบจับได้ถ้าชื่อนั้นไหลเข้าล็อกพร้อมเส้นทางเต็ม
    """
    client.get("/projects/new")
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post("/projects/new",
                    data={"name": "งานตรวจความเป็นส่วนตัว",
                          "mode": "year_to_year", "note": "", CSRF_FIELD: token},
                    follow_redirects=False)
    pid = r.headers["location"].rsplit("/", 1)[-1]

    for side in ("A", "B"):
        path = xlsx_factory(f"AO_21011_หน่วยงานทดสอบ_{side}.xlsx")
        with open(path, "rb") as fh:
            client.post(f"/projects/{pid}/upload",
                        data={"side": side, "fiscal_year": "2569",
                              "agency_code": "21011",
                              "agency_name": "หน่วยงานทดสอบ",
                              "doc_kind": "เอกสารทดสอบ", CSRF_FIELD: token},
                        files={"upload": (path.name, fh,
                                          "application/vnd.ms-excel")},
                        follow_redirects=False)

    r = client.post(f"/projects/{pid}/precheck", data={CSRF_FIELD: token},
                    follow_redirects=False)
    return pid, r.headers["location"].rsplit("/", 1)[-1]


def test_p30_error_page_has_no_internal_exception_details(client):
    r = client.get("/runs/ไม่มีจริง-9999")
    body = r.text
    for marker in privacy.INTERNAL_ERROR_MARKERS:
        assert marker not in body, f"หน้า error มีร่องรอยภายใน: {marker!r}"
    assert privacy.find_absolute_paths(body) == []


def test_p31_no_page_exposes_an_absolute_path(client, xlsx_factory):
    _, rid = _create_and_upload(client, xlsx_factory)
    for url in ("/", "/projects/new", "/rules", "/audit", "/healthz",
                f"/runs/{rid}", f"/runs/{rid}/review"):
        body = client.get(url).text
        leaks = privacy.find_absolute_paths(body)
        assert leaks == [], f"{url} รั่วเส้นทาง: {leaks[:2]}"


def test_p32_debug_detail_is_off_by_default():
    """🔴 หน้าเว็บของผู้ใช้ต้องไม่เห็นรายละเอียดภายในเป็นค่าเริ่มต้น"""
    assert config.DEBUG_DETAIL is False


@pytest.mark.parametrize("text, leaked", [
    # URL ทางการของสำนักงบประมาณ ไม่ใช่เส้นทางในเครื่อง — "s:" ท้าย "https:" ไม่ใช่ไดรฟ์ S:
    ("ที่มา https://bb.go.th/download.php?id=34185", []),
    ("https://www.bb.go.th/topic-detail.php?id=18879&mid=544", []),
    # เส้นทางในเครื่องยังต้องจับได้เหมือนเดิมทุกแบบ (0.2.1 ไม่ทำให้กลบขาด)
    (r"C:\Users\netthip\x.pdf", [r"C:\Users\netthip\x.pdf"]),
    ("file:///C:/Users/a.pdf", ["C:/Users/a.pdf"]),
    ('path "D:/data/x.xlsx"', ["D:/data/x.xlsx"]),
    (r"(E:\data\a.xlsx)", [r"E:\data\a.xlsx"]),
    ("ไฟล์C:/x/y.pdf", ["C:/x/y.pdf"]),
])
def test_p33_urls_are_not_drive_paths_but_real_paths_still_caught(text, leaked):
    assert privacy.find_absolute_paths(text) == leaked
    if leaked:
        assert leaked[0] not in privacy.redact_text(text)
