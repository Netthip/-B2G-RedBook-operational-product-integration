# -*- coding: utf-8 -*-
"""ด่านกันการเผลออ่านเฉลย (accidental sealed-key ingestion guard) — เครื่องมือของผู้พัฒนาต้องปฏิเสธไฟล์ตามกติกาชื่อเฉลย

🔴 ไม่ใช่ access control · ไม่พิสูจน์ว่าผู้พัฒนาเข้าถึงเฉลยไม่ได้ (Bo `5597645315` ข้อ A)

🔴 คำตัดสินกิ๊ฟ (9 ก.ย. 2569 · Gate 0 ข้อ 2) — *"Confirm Giho cannot access the
sealed key"* · สิ่งที่พิสูจน์ได้ในโค้ดคือ **เครื่องมืออ่านเอกสารทุกทางเข้าปฏิเสธ
ไฟล์ที่มีลักษณะเป็นเฉลย ก่อนแตะเนื้อไฟล์** และไม่มีสวิตช์ปิดด่าน

ชุดนี้ใช้ตัวดัก ``builtins.open`` แบบเดียวกับ ``test_p1_holdout.py`` และมีเทสต์
พิสูจน์ว่าตัวดักทำงานจริง (มิฉะนั้นข้อพิสูจน์ผ่านฟรี)

🔴 **SYNTHETIC TEST FIXTURE** — ไฟล์ล่อทุกไฟล์แต่งขึ้น ไม่มีเฉลยจริงในชุดทดสอบ
"""
import builtins
import inspect

import pytest

from redbook import sealed_key
from redbook.evidence import documents, pdftext

FIX = __import__("pathlib").Path(__file__).resolve().parent / "fixtures" / "synthetic_pdf"


class _OpenWatch:
    """ดักทั้ง ``builtins.open`` และ ``fitz.open`` — PyMuPDF เปิดไฟล์ด้วยโค้ด C
    จึงไม่ผ่าน ``builtins.open`` ถ้าดักแค่ตัวเดียวข้อพิสูจน์จะผ่านฟรี"""

    def __init__(self, monkeypatch):
        self.opened: list[str] = []
        real_open = builtins.open

        def spy(file, *a, **kw):
            self.opened.append(str(file))
            return real_open(file, *a, **kw)

        monkeypatch.setattr(builtins, "open", spy)
        try:
            import fitz
        except Exception:      # noqa: BLE001
            fitz = None
        if fitz is not None:
            real_fitz_open = fitz.open

            def spy_fitz(*a, **kw):
                if a:
                    self.opened.append(str(a[0]))
                return real_fitz_open(*a, **kw)

            monkeypatch.setattr(fitz, "open", spy_fitz)

    def touched(self, path) -> bool:
        return any(str(path) in o for o in self.opened)


@pytest.fixture()
def watch(monkeypatch):
    return _OpenWatch(monkeypatch)


@pytest.fixture()
def decoy(tmp_path):
    """ไฟล์ล่อในโฟลเดอร์ชื่อ SEALED_KEY — เนื้อไฟล์เป็น PDF สังเคราะห์ที่ใช้ได้จริง"""
    d = tmp_path / "SEALED_KEY"
    d.mkdir()
    p = d / "indicators.pdf"
    p.write_bytes((FIX / "synthetic_old_fy2569.pdf").read_bytes())
    return p


@pytest.mark.parametrize("name", [
    "SEALED_KEY/indicators.pdf", "answer_key/x.xlsx", "gold_key/x.pdf",
    "any/ANSWER_KEY_fy2570.xlsx", "any/sealed-key.pdf", "a/GOLD_KEY.json",
])
def test_sealed_paths_are_refused(name):
    assert sealed_key.is_sealed(name), name


@pytest.mark.parametrize("name", [
    "sources/public/ao_workbook/XL_FY2569.xlsx", "keys/monkey.pdf",
    "docs/keyboard_layout.pdf", "turnkey_report.pdf", "synthetic_old_fy2569.pdf",
])
def test_ordinary_paths_are_not_refused(name):
    """คำว่า key ในบริบทอื่นต้องไม่ถูกจับ — ด่านนี้กันเฉลย ไม่ใช่กันทุกอย่างที่มี key"""
    assert not sealed_key.is_sealed(name), name


def test_reason_is_reported():
    assert sealed_key.sealed_reason("SEALED_KEY/a.pdf") == sealed_key.REASON_DIR
    assert sealed_key.sealed_reason("x/ANSWER_KEY_1.pdf") == sealed_key.REASON_NAME
    with pytest.raises(sealed_key.SealedKeyViolation) as ei:
        sealed_key.assert_not_sealed("SEALED_KEY/a.pdf")
    assert ei.value.reason == sealed_key.REASON_DIR


def test_the_watch_itself_records_reads(tmp_path, watch):
    p = tmp_path / "plain.txt"
    p.write_text("x", encoding="utf-8")
    with open(p, encoding="utf-8") as f:
        f.read()
    assert watch.touched(p), "ตัวดักไม่ทำงาน — เทสต์ที่พึ่งตัวดักจะผ่านฟรี"
    backend = pdftext.get_backend()
    if backend is not None:
        backend.page_count(FIX / "synthetic_new_fy2570.pdf")
        assert watch.touched(FIX / "synthetic_new_fy2570.pdf"), "ตัวดัก fitz.open ไม่ทำงาน"


def test_document_registry_refuses_decoy_before_opening(decoy, watch, fresh_db):
    documents.init_schema(fresh_db)
    with pytest.raises(sealed_key.SealedKeyViolation):
        documents.register(decoy, media_type=documents.MEDIA_PDF, db_path=fresh_db)
    assert not watch.touched(decoy)
    assert documents.list_all(fresh_db) == []


def test_pdf_backend_refuses_decoy_before_opening(decoy, watch):
    backend = pdftext.get_backend()
    if backend is None:
        pytest.skip(pdftext.NO_TEXT_BACKEND)
    for fn in (backend.pages, backend.page_count):
        with pytest.raises(sealed_key.SealedKeyViolation):
            fn(decoy)
    with pytest.raises(sealed_key.SealedKeyViolation):
        backend.render_png(decoy, 1)
    assert not watch.touched(decoy)


def test_workbook_reader_refuses_decoy_too(tmp_path, watch, xlsx_factory):
    """ทางเข้าของสาย T1B (สมุดงาน) ต้องผ่านด่านเดียวกัน"""
    from redbook.services import t1b as svc

    src = xlsx_factory("plain.xlsx")
    d = tmp_path / "answer_key"
    d.mkdir()
    p = d / "book.xlsx"
    p.write_bytes(src.read_bytes())
    with pytest.raises(sealed_key.SealedKeyViolation):
        svc.read_workbook(p)
    assert not watch.touched(p)


def test_guard_has_no_environment_switch():
    src = inspect.getsource(sealed_key)
    assert "os.environ" not in src and "getenv" not in src
    assert sealed_key.SEALED_KEY_GUARD_STATUS == "ACCIDENTAL_SEALED_KEY_INGESTION_GUARD_ENFORCED"
    assert "not access control" in sealed_key.GUARD_IS_NOT


def test_scan_roots_reports_hits_by_name_only(tmp_path):
    (tmp_path / "SEALED_KEY").mkdir()
    (tmp_path / "SEALED_KEY" / "k.pdf").write_bytes(b"%PDF-1.4\n")
    (tmp_path / "ok.pdf").write_bytes(b"%PDF-1.4\n")
    rep = sealed_key.scan_roots([tmp_path, tmp_path / "does-not-exist"])
    assert rep["entries_scanned"] >= 2
    assert {h["name"] for h in rep["hits"]} == {"SEALED_KEY", "k.pdf"}   # โฟลเดอร์ก็เป็นสัญญาณ
    assert rep["roots_missing"] == ["does-not-exist"]
    assert rep["evidence_kind"] == "inventory_only"
    # ไม่มีเส้นทางเต็มในรายงาน
    assert str(tmp_path) not in str(rep)
