# -*- coding: utf-8 -*-
"""backend PDF — สายผลิตภัณฑ์ต้อง **fail-closed** และกรณีข้อความล้นขอบต้องมองเห็น

🔴 Bo · `BO REVIEW COMPLETE — PRE-FREEZE CORRECTIONS PASS 1` (`5598526148` Lane B6.1)
และ `BO REVIEW — PRE-FREEZE CORRECTIONS PASS 1` (`5598957701` P1-1 · P1-2)

* **P1-1** — ``get_backend()``/``product_backend()`` ต้องลอง **เฉพาะ** backend สิทธิ์ผ่อนปรน
  ถ้าใช้ไม่ได้ต้องคืน ``NO_TEXT_BACKEND`` **ห้ามหล่นไปใช้ PyMuPDF** แม้ติดตั้งอยู่ ·
  มี negative test จำลอง permissive พังขณะที่ PyMuPDF ใช้ได้
* **P1-2** — ชุด fixture ที่ **คง** ข้อความล้น/ชนขอบหน้าไว้ · เทสต์ **ไม่บังคับ** ให้สอง
  parser อ่านเท่ากันในกรณีนั้น (ธรรมชาติของ parser ต่างกัน) แต่บังคับว่า
  **ผลปลายทางต้องไม่ถูกยืนยันอัตโนมัติ**

🔴 **SYNTHETIC TEST FIXTURE**
"""
import dataclasses
import json
from pathlib import Path

import pytest

from redbook.evidence import pdftext
from redbook.indicators import mapping as mp
from redbook.indicators import observe as ob

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "synthetic_pdf"
FILES = ("synthetic_old_fy2569.pdf", "synthetic_new_fy2570.pdf")
CLIPPED = ("synthetic_clipped_old.pdf", "synthetic_clipped_new.pdf")
MANIFEST = json.loads((FIX / "MANIFEST.json").read_text(encoding="utf-8"))

#: pdfminer วัด top จาก font bbox · MuPDF วัดจาก glyph ascent ⇒ ต่างกันได้ราว 3 pt
BBOX_TOLERANCE_PT = 4.0


@pytest.fixture(autouse=True)
def _clean_backend_cache():
    """แคชการเลือก backend ต้องไม่ข้ามเทสต์ — มิฉะนั้น negative test จะรั่วไปเทสต์อื่น"""
    pdftext._reset_backend_cache()
    yield
    pdftext._reset_backend_cache()


# ══════════════════════════════════════════════════════════════════════════════
#  P1-1 — สายผลิตภัณฑ์เลือกเฉพาะ backend สิทธิ์ผ่อนปรน · ไม่มี fallback
# ══════════════════════════════════════════════════════════════════════════════

def test_product_backend_is_the_permissive_one():
    b = pdftext.product_backend()
    assert b is not None, pdftext.NO_TEXT_BACKEND
    assert b.name == pdftext.DEFAULT_BACKEND_NAME == "pdfplumber+pypdfium2"
    assert pdftext.PRODUCT_BACKEND is pdftext.PdfplumberPdfiumBackend
    assert pdftext.RESEARCH_BACKEND is pdftext.PyMuPdfBackend
    assert pdftext.get_backend() is b, "get_backend ต้องเป็นทางเข้าเดียวของสายผลิตภัณฑ์"


def test_no_ordered_fallback_list_exists():
    """🔴 การมี "ลำดับ backend" คือกลไกที่ทำให้ PyMuPDF ถูกเลือกเงียบ ๆ — ต้องไม่มีอีก"""
    assert not hasattr(pdftext, "BACKEND_ORDER")
    assert not hasattr(pdftext, "available_backends")


def test_product_ingress_never_falls_back_to_pymupdf(monkeypatch):
    """**negative test ของ P1-1** — permissive พัง + PyMuPDF ใช้ได้ ⇒ ต้องได้ NO_TEXT_BACKEND"""
    if pdftext.research_backend() is None:
        pytest.skip("ต้องติดตั้ง requirements-research-pymupdf.txt เพื่อจำลองกรณีนี้")

    class BrokenPermissive:
        name = "pdfplumber+pypdfium2"

        def __init__(self):
            raise ImportError("จำลอง: ไม่มี pdfplumber ในเครื่องนี้")

    monkeypatch.setattr(pdftext, "PRODUCT_BACKEND", BrokenPermissive)
    pdftext._reset_backend_cache()

    assert pdftext.research_backend() is not None, "PyMuPDF ต้องยังใช้ได้ในสถานการณ์จำลองนี้"
    assert pdftext.product_backend() is None, "🔴 สายผลิตภัณฑ์ต้องไม่หล่นไปใช้ PyMuPDF"
    assert pdftext.get_backend() is None
    assert pdftext.backend_name() == pdftext.NO_TEXT_BACKEND
    assert pdftext.backend_unavailable_reason() == "ImportError"

    report = pdftext.backend_report()
    assert report["backend"] == pdftext.NO_TEXT_BACKEND
    assert report["fallback_allowed"] is False
    assert "pymupdf" not in json.dumps(report).lower()


def test_service_layer_uses_product_resolution_only():
    """ชั้นบริการต้องไม่เรียก ``research_backend`` — ตรวจด้วย AST ไม่ใช่ค้นข้อความ"""
    import ast

    src = (ROOT / "redbook" / "services" / "evidence.py").read_text(encoding="utf-8")
    calls = [n for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    names = {n.func.attr for n in calls}
    assert "research_backend" not in names
    assert "product_backend" in names


def test_backend_report_is_recorded_in_run_evidence():
    """B6.1 ข้อ 4 — run/manifest ต้องบอกได้ว่าใช้ backend ใดและโหมดใด"""
    r = pdftext.backend_report(mode=pdftext.MODE_PRODUCT)
    assert r["mode"] == pdftext.MODE_PRODUCT
    assert r["product_backend_declared"] == "pdfplumber+pypdfium2"
    assert set(r) >= {"mode", "backend", "backend_version", "fallback_allowed",
                      "product_backend_declared", "unavailable_reason"}


def test_pymupdf_is_not_a_default_dependency():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    pkgs = [ln.split("==")[0].split(">")[0].strip()
            for ln in req.splitlines() if ln and not ln.startswith("#")]
    assert "pymupdf" not in pkgs
    assert "pdfplumber==" in req and "pypdfium2==" in req, "backend ปริยายต้องตรึงเวอร์ชัน"
    extra = (ROOT / "requirements-research-pymupdf.txt").read_text(encoding="utf-8")
    assert "pymupdf==" in extra and "LICENSE REVIEW REQUIRED" in extra
    # ตรวจ **บรรทัดแพ็กเกจ** เท่านั้น — คอมเมนต์ในหัวไฟล์พูดถึง PyMuPDF ได้ (และควรพูด)
    lock_pkgs = [ln.split("==")[0].strip().lower()
                 for ln in (ROOT / "requirements.lock.txt").read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.startswith("#")]
    assert "pymupdf" not in lock_pkgs, "ชุดที่ตรึงไว้สำหรับ freeze ต้องไม่มี PyMuPDF"


# ══════════════════════════════════════════════════════════════════════════════
#  backend ปริยายตามลำพัง
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("name", FILES)
def test_permissive_backend_reads_fixture_alone(name):
    b = pdftext.product_backend()
    assert b is not None
    pages = b.pages(FIX / name)
    exp = MANIFEST["expectations_for_unit_tests_only"]
    side = "old" if "old" in name else "new"
    assert [p.page for p in pages if not p.has_text_layer] == exp["pages_without_text_layer"][side]
    texts = "\n".join(l.text for p in pages for l in p.lines)
    for needle in ("ตัวชี้วัดที่ 1", "ตัวชี้วัดที่ 7"):
        assert needle in texts
    for p in pages:
        for l in p.lines:
            assert l.x1 <= p.width, (name, p.page, l.text[:30], l.x1)
    png = b.render_png(FIX / name, 2, highlight=(56, 120, 300, 140))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert b.page_count(FIX / name) == len(pages)


def test_render_png_is_decodable_and_has_expected_size():
    from io import BytesIO

    from PIL import Image

    b = pdftext.product_backend()
    im = Image.open(BytesIO(b.render_png(FIX / FILES[0], 1)))
    assert im.size == (952, 1348) and im.mode == "RGB"      # A4 @ zoom 1.6


# ══════════════════════════════════════════════════════════════════════════════
#  เทียบผลกับ PyMuPDF (เฉพาะเมื่อติดตั้ง extra วิจัย · explicit research path)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def both():
    a, b = pdftext.product_backend(), pdftext.research_backend()
    if a is None or b is None:
        pytest.skip("ต้องมีทั้งสอง backend (ติดตั้ง requirements-research-pymupdf.txt) จึงเทียบได้")
    return a, b


@pytest.mark.parametrize("name", FILES)
def test_line_texts_are_identical_across_backends(both, name):
    a, b = both
    pa, pb = a.pages(FIX / name), b.pages(FIX / name)
    assert len(pa) == len(pb)
    for x, y in zip(pa, pb):
        assert x.has_text_layer == y.has_text_layer, (name, x.page)
        assert [l.text for l in x.lines] == [l.text for l in y.lines], (name, x.page)
        assert (round(x.width), round(x.height)) == (round(y.width), round(y.height))


@pytest.mark.parametrize("name", FILES)
def test_line_bboxes_agree_within_tolerance(both, name):
    a, b = both
    for x, y in zip(a.pages(FIX / name), b.pages(FIX / name)):
        for la, lb in zip(x.lines, y.lines):
            for va, vb in zip(la.bbox, lb.bbox):
                assert abs(va - vb) <= BBOX_TOLERANCE_PT, (name, x.page, la.text[:30])


def test_rendered_page_sizes_agree(both):
    from io import BytesIO

    from PIL import Image

    a, b = both
    assert (Image.open(BytesIO(a.render_png(FIX / FILES[0], 2))).size
            == Image.open(BytesIO(b.render_png(FIX / FILES[0], 2))).size)


def _observe(backend, name, doc_id):
    pages = backend.pages(FIX / name)
    return ob.observe_document(doc_id, "a" * 64, pages)


def test_indicator_statuses_do_not_depend_on_backend(both):
    """สถานะที่เสนอทั้งชุดต้องไม่ขึ้นกับ backend — มิฉะนั้น freeze ผูกกับไลบรารีโดยไม่รู้ตัว"""
    results = []
    for backend in both:
        old = _observe(backend, FILES[0], "doc_old")
        new = _observe(backend, FILES[1], "doc_new")
        by_text = {o.observation_id: o.observed_text for o in old + new}
        results.append(sorted(
            (c.proposed_status, by_text.get(c.old_observation_id, ""),
             by_text.get(c.new_observation_id, ""))
            for c in mp.propose(old, new)))
    assert results[0] == results[1]


# ══════════════════════════════════════════════════════════════════════════════
#  P1-2 — ข้อความล้น/ชนขอบหน้า: ต่างกันได้ แต่ต้องไม่ถูกยืนยันอัตโนมัติ
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("name", CLIPPED)
def test_clipped_fixture_still_contains_the_overflowing_line(name):
    """🔴 fixture ขอบเขตนี้ **ห้าม** ถูกแก้ให้บรรทัดสั้นลง — เป็นกรณีที่เปิดเผยความต่างของ parser"""
    b = pdftext.product_backend()
    pages = b.pages(FIX / name)
    over = [l for p in pages for l in p.lines if l.x1 > p.width]
    assert over, "fixture ขอบเขตต้องมีบรรทัดที่ล้นขอบหน้าอย่างน้อยหนึ่งบรรทัด"
    assert any("ตัวชี้วัดที่ 9" in l.text for l in over)


def test_backends_may_disagree_on_clipped_lines_and_that_is_recorded(both):
    """ไม่บังคับให้สอง parser อ่านเท่ากันตรงบรรทัดที่ล้นขอบ — บังคับให้ **ติดธง** แทน"""
    a, b = both
    pa = a.pages(FIX / CLIPPED[0])[1]
    pb = b.pages(FIX / CLIPPED[0])[1]
    clipped_a = [l for l in pa.lines if l.x1 >= pa.width - ob.PAGE_EDGE_TOLERANCE_PT]
    clipped_b = [l for l in pb.lines if l.x1 >= pb.width - ob.PAGE_EDGE_TOLERANCE_PT]
    assert clipped_a and clipped_b, "ทั้งสอง backend ต้องมองเห็นว่าบรรทัดนี้ชนขอบ"
    # ความกว้างที่รายงานต่างกันได้ (นี่คือเหตุผลที่ต้องติดธง)
    assert round(clipped_a[0].x1) != round(clipped_b[0].x1)


def test_clipped_observations_are_flagged_and_never_auto_confirmed():
    """**หัวใจของ P1-2** — คู่ที่มีข้อความชนขอบต้องเป็น AMBIGUOUS เสมอ ห้ามเสนอสถานะอัตโนมัติ"""
    b = pdftext.product_backend()
    old = _observe(b, CLIPPED[0], "doc_clip_old")
    new = _observe(b, CLIPPED[1], "doc_clip_new")
    clipped_old = [o for o in old if o.text_clipped]
    assert clipped_old, "ต้องมีข้อสังเกตที่ติดธงข้อความชนขอบ"
    assert all("ตัวชี้วัดที่ 9" in o.observed_text for o in clipped_old)
    assert ob.FLAG_TEXT_CLIPPED in clipped_old[0].geometry_flags

    cands = mp.propose(old, new)
    by_text = {o.observation_id: o.observed_text for o in old + new}
    for c in cands:
        text = by_text.get(c.old_observation_id, "") + by_text.get(c.new_observation_id, "")
        if "ตัวชี้วัดที่ 9" in text:
            assert c.proposed_status == mp.AMBIGUOUS_REVIEW_REQUIRED, c
            assert c.human_required is True
            assert mp.BASIS_CLIPPED in c.basis
        if "ตัวชี้วัดที่ 10" in text:
            # บรรทัดที่ไม่ล้นขอบยังทำงานตามปกติ — ธงต้องไม่ลามไปทั้งเอกสาร
            assert c.proposed_status == mp.SAME_EXACT


def test_unclipped_line_in_the_same_document_is_unaffected():
    b = pdftext.product_backend()
    old = _observe(b, CLIPPED[0], "doc_clip_old")
    normal = [o for o in old if "ตัวชี้วัดที่ 10" in o.observed_text]
    assert normal and not normal[0].text_clipped


def test_page_inventory_counts_clipped_observations():
    b = pdftext.product_backend()
    pages = b.pages(FIX / CLIPPED[0])
    obs = ob.observe_document("doc_clip_old", "a" * 64, pages)
    inv = ob.page_inventory(pages, obs)
    assert sum(r.clipped_observations for r in inv) >= 1


def test_clipping_flag_survives_a_manually_supplied_geometry():
    """ธงมาจากเรขาคณิต ไม่ใช่จากข้อความ — ข้อความสั้นแต่กรอบชนขอบก็ต้องติดธง"""
    assert ob.clipped_at_page_edge(595.0, 595.0) is True
    assert ob.clipped_at_page_edge(594.5, 595.0) is True     # ภายใน tolerance
    assert ob.clipped_at_page_edge(500.0, 595.0) is False
    assert ob.clipped_at_page_edge(500.0, 0.0) is False       # ไม่ทราบความกว้าง ⇒ ไม่เดา


def test_fixture_hashes_match_manifest():
    from redbook.evidence import documents as docs

    for name, meta in MANIFEST["files"].items():
        assert docs.sha256_file(FIX / name)[0] == meta["sha256"], name
