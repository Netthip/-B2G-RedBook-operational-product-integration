# -*- coding: utf-8 -*-
"""สายเทียบเล่ม PDF ↔ PDF (``redbook.pdfbook`` + ``services/pdfpair``)

🔴 **SYNTHETIC DEMONSTRATION DATA** — เล่มจาก ``scripts/demo_redbook_book_pdf.py`` แต่งขึ้นทั้งหมด ·
ผ่านเทสต์ชุดนี้ = ทำงานถูกกับเล่มสังเคราะห์ **ไม่ใช่หลักฐานว่าอ่านเล่มจริงได้** (โปรไฟล์ยังไม่ได้ปรับเทียบ
กับชุดพัฒนาเล่มจริงที่ได้รับอนุญาต)

ชุดตรวจ

* ความต่างที่ฝังไว้ครบทุกหัวข้อถูกพบ (ร่าง ↔ พ.ร.บ.) · ข้ามปี: ข้อที่ต้องตัดสิน = เฉพาะที่ฝังไว้
* ตัวควบคุมเชิงลบ: เล่มที่สอดคล้องกันไม่มีข้อสังเกตภายในเล่ม · วิสัยทัศน์ที่เหมือนกันไม่ถูกรายงาน
* ตัวเลข: ลบแบบ "- 8.4496" · ขีด = ว่าง · ล้านบาท 4 ตำแหน่งไม่ปัด
* ช่วงหน้าหน่วยงาน · หน้าที่ไม่มีชั้นข้อความถูกรายงาน · ไม่มีคำว่า "ผิด"
* เว็บ: เดินเส้นทางจริง · SHA-256 ไม่ตรง = ไม่อ่าน · เปลี่ยนผลต้องมีเหตุผล · Audit
* ขอบเขตสถาปัตยกรรม: ไม่แตะ T1B · ไม่ใช้ PyMuPDF/เครือข่าย · route เรียกผ่านชั้นบริการ
"""
import ast
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

fitz = pytest.importorskip("fitz")       # เครื่องมือสร้าง fixture (ไม่ใช่ product path)
import demo_redbook_book_pdf as gen      # noqa: E402

from redbook.app import create_app       # noqa: E402
from redbook.evidence import pdftext     # noqa: E402
from redbook.pdfbook import compare as cmp, extract as ex, layout, profile as P, reader, scope  # noqa: E402
from redbook.pdfbook.text import fmt, parse_amount  # noqa: E402
from redbook.services import pdfpair as svc  # noqa: E402
from redbook.storage import audit, pdfpair_repo  # noqa: E402
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD  # noqa: E402

pytestmark = pytest.mark.skipif(pdftext.product_backend() is None,
                                reason="ไม่มี pdfplumber + pypdfium2")
AG = gen.AGENCY_1


def _facts(path, agency=AG):
    texts = reader.page_texts(path)
    sc = scope.find(texts, agency)
    fy, stage = ex.detect_meta(texts, sc.first)
    return ex.extract(reader.page_words(path, sc.pages), fiscal_year=fy, stage=stage, agency=agency), sc


@pytest.fixture(scope="module")
def books(tmp_path_factory):
    d = tmp_path_factory.mktemp("pdfbooks")
    return {"draft_act": gen.build(d, "draft_act"), "cross_year": gen.build(d, "cross_year")}


@pytest.fixture(scope="module")
def draft_act(books):
    (fa, sa), (fb, sb) = (_facts(p) for p in books["draft_act"])
    return fa, fb, sa, sb, cmp.compare(fa, fb)


@pytest.fixture(scope="module")
def cross_year(books):
    (fa, _), (fb, _) = (_facts(p) for p in books["cross_year"])
    return fa, fb, cmp.compare(fa, fb)


def _has(res, topic, kind, *words, within=""):
    for f in res.findings:
        text = " ".join([f.subject, f.column, f.a.value, f.b.value, f.note])
        if f.topic == topic and f.kind == kind and (not within or f.within == within) \
                and all(w in text for w in words):
            return f
    return None


# ── ตัวเลขและแถว ─────────────────────────────────────────────────────────────
class _W:
    def __init__(self, text, x0, x1, line=0):
        self.text, self.x0, self.x1, self.y0, self.y1, self.line, self.block = text, x0, x1, 100, 110, line, 0


def test_negative_with_space_and_dash_blank():
    r = layout._row(1, [_W("รายการ", 40, 80), _W("-", 300, 304), _W("8.4496", 306, 340),
                        _W("-", 400, 404), _W("1,234.5000", 450, 500)])
    assert [c.value for c in r.cells] == [Decimal("-8.4496"), None, Decimal("1234.5000")]
    assert r.label == "รายการ"


def test_year_after_pi_stays_in_label():
    r = layout._row(1, [_W("ผูกพันงบประมาณปี", 40, 140), _W("2571", 142, 170),
                        _W("20,000,000", 400, 470), _W("บาท", 480, 500)])
    assert r.label.endswith("2571") and [c.value for c in r.cells] == [Decimal("20000000")]


def test_soft_hyphen_dash_is_blank_cell():
    r = layout._row(1, [_W("รายการ", 40, 80), _W("­", 300, 304), _W("2.0000", 400, 440)])
    assert [c.value for c in r.cells] == [None, Decimal("2.0000")]


def test_format_keeps_printed_precision_never_pads_or_rounds():
    # REVIEW 6340074844 ข้อ 1: ไม่เติมทศนิยมให้ดูละเอียดกว่าที่พิมพ์ และไม่ปัด
    assert fmt(Decimal("1.2"), "ล้านบาท") == "1.2"
    assert fmt(parse_amount("0.1760"), "ล้านบาท") == "0.1760"
    assert fmt(Decimal("1.23456"), "ล้านบาท") == "1.23456"
    assert fmt(Decimal("11.3731") * 1_000_000, "บาท") == "11,373,100"     # ศูนย์จากการคูณไม่ใช่ทศนิยมที่พิมพ์
    assert parse_amount("-") is None


# ── ช่วงหน้า ─────────────────────────────────────────────────────────────────
def test_scope_stops_before_next_agency(books, draft_act):
    _fa, _fb, sa, sb, _r = draft_act
    texts = reader.page_texts(books["draft_act"][0])
    assert sa.method == scope.METHOD_NAME and len(sa.starts_found) == 2
    assert sa.last == sa.starts_found[1] - 1
    assert gen.AGENCY_2 not in "".join(texts[sa.first - 1:sa.last])


def test_scope_errors_are_explicit(books):
    texts = reader.page_texts(books["draft_act"][0])
    with pytest.raises(scope.ScopeError, match="2 แห่ง"):
        scope.find(texts, "")
    with pytest.raises(scope.ScopeError, match="ไม่พบชื่อหน่วยงาน"):
        scope.find(texts, "หน่วยงานที่ไม่มีอยู่จริง")
    assert scope.find(texts, "", 3, 4).method == scope.METHOD_MANUAL


def test_meta_detected(draft_act):
    fa, fb, *_ = draft_act
    assert (fa.fiscal_year, fa.stage, fb.fiscal_year, fb.stage) == (2570, "draft", 2570, "act")


# ── ร่าง ↔ พ.ร.บ.: พบทุกความต่างที่ฝังไว้ ───────────────────────────────────
SEEDED_DRAFT_ACT = [
    ("total", "changed", ("การตรวจสอบเอกสารงบประมาณ", "งบดำเนินงาน", "15.4800", "14.2300")),
    ("items", "not_proposed", ("เครื่องพิมพ์ชนิดเลเซอร์",)),
    ("struct", "renamed_candidate", ("การเผยแพร่ข้อมูลงบประมาณภาครัฐ",)),
    ("ind", "changed", ("จำนวนเอกสารที่ได้รับการตรวจสอบ", "เป้าหมายปี 2570", "120", "100")),
    ("ind", "changed", ("ร้อยละของเอกสารที่ผ่านการตรวจสอบ", "หน่วยนับ", "ร้อยละ", "ระดับ")),
    ("ind", "only_b", ("ความพึงพอใจของผู้ใช้ข้อมูล",)),
    ("text", "changed", ("พันธกิจ", "ข้อ 2.2")),
    ("text", "only_b", ("ข้อ 3.3",)),
    ("commit", "changed", ("อาคารศูนย์ข้อมูล", "วงเงินทั้งสิ้น", "80000000", "75000000")),
    ("commit", "changed", ("ผูกพันงบประมาณปี 2571", "40000000", "35000000")),
    ("mtef", "changed", ("โครงการพัฒนาศักยภาพผู้ตรวจสอบเอกสาร", "ปี 2571", "2.5000", "2.2000")),
    ("econ", "changed", ("การตรวจสอบเอกสารงบประมาณ", "รายจ่ายลงทุน", "3.2000", "2.0000")),
]


@pytest.mark.parametrize("topic,kind,words", SEEDED_DRAFT_ACT)
def test_draft_act_seeded_difference_found(draft_act, topic, kind, words):
    assert _has(draft_act[4], topic, kind, *words), (topic, kind, words)


def test_draft_act_internal_inconsistency_only_in_b(draft_act):
    res = draft_act[4]
    f = _has(res, "consist", "sum_mismatch", "แผนงานยุทธศาสตร์พัฒนาระบบตรวจสอบเอกสาร", within="B")
    assert f and f.b.page and f.b.bbox
    # ตัวควบคุมเชิงลบ: ฉบับ A สอดคล้องกันทุกตาราง
    assert not [x for x in res.findings if x.topic == "consist" and x.within == "A"]


def test_page_without_text_layer_reported(draft_act):
    fb = draft_act[1]
    assert fb.coverage.pages_no_text
    assert _has(draft_act[4], "cover", "unread", "ไม่มีชั้นข้อความ", within="B")


def test_page_shift_keeps_evidence_per_side(draft_act):
    f = _has(draft_act[4], "total", "changed", "การตรวจสอบเอกสารงบประมาณ", "งบดำเนินงาน")
    assert f.b.page == f.a.page + 1            # ฉบับ B มีหน้าคั่นเพิ่ม 1 หน้า


def test_unchanged_vision_not_reported(draft_act):
    assert not [f for f in draft_act[4].findings if f.subject == "วิสัยทัศน์"]


def test_nothing_unread_in_clean_tables(draft_act):
    fa, fb, *_ = draft_act
    assert fa.coverage.unparsed == [] and fb.coverage.unparsed == []


def test_reviewer_language_no_wrong_word(draft_act, cross_year):
    for res in (draft_act[4], cross_year[2]):
        for f in res.findings:
            assert "ผิด" not in f.kind_label + f.note + f.topic_label, f


# ── ข้ามปี ───────────────────────────────────────────────────────────────────
def test_cross_year_mode_and_actionable_set_is_exactly_seeded(cross_year):
    fa, fb, res = cross_year
    assert res.mode == cmp.MODE_CROSS_YEAR and (fa.fiscal_year, fb.fiscal_year) == (2569, 2570)
    act = {(f.topic, f.kind, f.subject.split(" (")[0], f.column) for f in res.findings if not f.info}
    assert act == {
        ("mtef", "same_year_mismatch", "ผลผลิต : การเผยแพร่ข้อมูลงบประมาณ", "ปี 2569"),
        ("mtef", "same_year_mismatch", "แผนงานพื้นฐานด้านการบริหารจัดการงบประมาณ", "ปี 2569"),
        ("mtef", "same_year_mismatch", "รวมทั้งสิ้น", "ปี 2569"),
        ("ind", "same_year_mismatch", "ร้อยละของเอกสารที่ผ่านการตรวจสอบ", "เป้าหมายปี 2569"),
        ("text", "changed", "วิสัยทัศน์", "ข้อความ"),
    }


def test_cross_year_changes_are_information(cross_year):
    res = cross_year[2]
    f = _has(res, "total", "year_change", "การตรวจสอบเอกสารงบประมาณ", "งบดำเนินงาน")
    assert f and f.info and Decimal(f.delta) == Decimal("-0.6000")
    assert _has(res, "struct", "only_b", "โครงการเชื่อมโยงข้อมูลงบประมาณข้ามหน่วยงาน").info


def test_serialisation_roundtrip(draft_act):
    fa, _fb, _sa, _sb, res = draft_act
    assert ex.BookFacts.from_dict(fa.to_dict()).to_dict() == fa.to_dict()
    assert cmp.CompareResult.from_dict(res.to_dict()).to_dict() == res.to_dict()


# ── เว็บ ──────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def web_run(client, books):
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post("/projects/new", follow_redirects=False, data={
        CSRF_FIELD: token, "name": "เทียบเล่ม PDF (สังเคราะห์)", "mode": "before_after_reduction",
        "note": "ข้อมูลสังเคราะห์"})
    pid = r.headers["location"].rsplit("/", 1)[-1]
    for side, path in zip("AB", books["draft_act"]):
        with open(path, "rb") as fh:
            r = client.post(f"/projects/{pid}/source-pdf", follow_redirects=False,
                            data={CSRF_FIELD: token, "side": side, "back": f"/projects/{pid}/pdfpair"},
                            files={"upload": (path.name, fh, "application/pdf")})
        assert r.status_code == 303 and r.headers["location"] == f"/projects/{pid}/pdfpair"
    r = client.post(f"/projects/{pid}/pdfpair", follow_redirects=False,
                    data={CSRF_FIELD: token, "agency": AG})
    assert r.status_code == 303, r.text[:500]
    return pid, r.headers["location"].rsplit("/", 1)[-1], token


def test_web_start_page_lists_topics(client, web_run):
    pid = web_run[0]
    html = client.get(f"/projects/{pid}/pdfpair").text
    for _k, label in cmp.TOPICS:
        assert label in html
    assert "ยังไม่ใช่ผลประเมิน" in html          # ป้ายสถานะโปรไฟล์ (DEV_CALIBRATING)


def test_web_overview_and_evidence(client, web_run):
    _pid, rid, _t = web_run
    html = client.get(f"/pdfpair/runs/{rid}").text
    assert "เหลือ" in html and "ข้อสังเกตที่คนยังต้องตรวจ" in html
    v = svc.view(rid)
    f = next(x for x in v.result.findings if x.topic == "total" and not x.info)
    page = client.get(f"/pdfpair/runs/{rid}/f/{f.id}")
    assert page.status_code == 200 and "ตำแหน่งที่ระบบค้นพบ — รอผู้ตรวจยืนยัน" in page.text
    for side in "AB":
        img = client.get(f"/pdfpair/runs/{rid}/f/{f.id}/{side}.png")
        assert img.status_code == 200 and img.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_web_text_diff_shown(client, web_run):
    rid = web_run[1]
    f = next(x for x in svc.view(rid).result.findings if x.topic == "text" and x.kind == "changed")
    html = client.get(f"/pdfpair/runs/{rid}/f/{f.id}").text
    assert "pp-ins" in html          # ข้อ 2.2 ฉบับ B เพิ่มถ้อยคำ "ครบถ้วน"
    assert "ครบถ้วน" in html


def test_web_decide_and_change_requires_reason(client, web_run):
    _pid, rid, token = web_run
    v = svc.view(rid)
    f = next(x for x in v.result.findings if not x.info)
    before = v.pending
    r = client.post(f"/pdfpair/runs/{rid}/f/{f.id}/decide", follow_redirects=False,
                    data={CSRF_FIELD: token, "choice": "per_document", "note": ""})
    assert r.status_code == 303
    assert svc.view(rid).pending == before - 1
    r = client.post(f"/pdfpair/runs/{rid}/f/{f.id}/decide",
                    data={CSRF_FIELD: token, "choice": "fix", "note": ""})
    assert r.status_code == 400 and "ต้องระบุเหตุผล" in r.text
    acts = [e["action"] for e in audit.entries(limit=50)]
    assert "pdfpair_decision" in acts and "pdfpair_run_completed" in acts


def test_web_export_csv_requires_preflight_then_audits(client, web_run):
    rid = web_run[1]
    pf = svc.preflight(rid)
    # ยังตัดสินไม่ครบ — รวมหน้าที่ไม่มีชั้นข้อความที่ฝังไว้ในเล่มสังเคราะห์ (ต้องให้คนตรวจ)
    assert not pf.ok and {"unread", "decided"} <= {c.key for c in pf.failing}
    assert "files" not in {c.key for c in pf.failing} and "years" not in {c.key for c in pf.failing}
    assert client.get(f"/pdfpair/runs/{rid}/export.csv").status_code == 409   # บังคับที่เซิร์ฟเวอร์
    assert "ยังส่งออกไม่ได้" in client.get(f"/pdfpair/runs/{rid}/export").text
    v = svc.view(rid)
    for f in v.result.findings:
        if not f.info and f.id not in v.decisions:
            svc.decide(rid, f.id, "checked", "")
    assert svc.preflight(rid).ok
    page = client.get(f"/pdfpair/runs/{rid}/preflight").text
    assert "ผ่านครบ" in page and "ไปหน้าส่งออก" in page
    r = client.get(f"/pdfpair/runs/{rid}/export.csv")
    assert r.status_code == 200 and r.content.startswith("﻿".encode("utf-8"))
    assert "ผลการตรวจของคน" in r.content.decode("utf-8")
    import hashlib
    ex_log = [e for e in pdfpair_repo.audit_entries(rid) if e["action"] == "pdfpair_exported"]
    assert ex_log and hashlib.sha256(r.content).hexdigest() in ex_log[-1]["detail_json"]
    audit_page = client.get(f"/pdfpair/runs/{rid}/audit").text
    assert "ส่งออก CSV" in audit_page and "บันทึกผลการตรวจ" in audit_page and "สายโซ่แฮช" in audit_page


def test_sha_mismatch_refuses_to_read(client, web_run, tmp_path):
    pid = web_run[0]
    from redbook.storage import files as filestore, source_pdfs
    row = source_pdfs.for_project(pid)["A"]
    p = filestore.path_for(row["stored_name"])
    import os
    import stat
    original, mode = p.read_bytes(), p.stat().st_mode
    os.chmod(p, mode | stat.S_IWRITE)          # ที่เก็บตั้งไฟล์เป็นอ่านอย่างเดียว
    try:
        p.write_bytes(original + b"\n%tampered")
        with pytest.raises(svc.PairError, match="SHA-256"):
            svc.run(pid, agency=AG)
    finally:
        p.write_bytes(original)
        os.chmod(p, mode)


def test_missing_pdf_is_explained(client):
    client.get("/")
    token = client.cookies.get(CSRF_COOKIE)
    r = client.post("/projects/new", follow_redirects=False, data={
        CSRF_FIELD: token, "name": "ไม่มี PDF", "mode": "before_after_reduction", "note": ""})
    pid = r.headers["location"].rsplit("/", 1)[-1]
    r = client.post(f"/projects/{pid}/pdfpair", data={CSRF_FIELD: token, "agency": AG})
    assert r.status_code == 400 and "ยังไม่ได้แนบ PDF ของฉบับ A" in r.text


# ── ขอบเขตสถาปัตยกรรม ────────────────────────────────────────────────────────
def _imports(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            out.add(("." * n.level) + (n.module or ""))
    return out


def test_pdfbook_does_not_touch_t1b_pymupdf_or_network():
    banned = ("t1b", "fitz", "pymupdf", "requests", "httpx", "urllib", "socket")
    for p in (PROJECT_ROOT / "redbook" / "pdfbook").glob("*.py"):
        for imp in _imports(p):
            assert not any(b in imp.lower() for b in banned), (p.name, imp)


def test_routes_go_through_service_layer():
    imps = _imports(PROJECT_ROOT / "redbook" / "web" / "pdfpair_routes.py")
    assert not any("pdfbook" in i for i in imps)


# ── กรณียากตามที่โบขอ (#41) ───────────────────────────────────────────────────
@pytest.fixture(scope="module")
def edge(tmp_path_factory):
    a, b = gen.build(tmp_path_factory.mktemp("pdfedge"), "edge")
    (fa, _), (fb, _) = _facts(a), _facts(b)
    return fa, fb, cmp.compare(fa, fb)


def test_edge_unit_change_is_format_only(edge):
    fa, fb, res = edge
    assert fa.table_units.get("summary") == "ล้านบาท" and fb.table_units.get("summary") == "บาท"
    assert _has(res, "format", "changed", "หน่วยของตาราง", "ล้านบาท", "บาท")
    # ค่าที่เท่ากันหลังแปลงเป็นบาทต้องไม่ถูกยกขึ้น (เช่น ยอดรวมทั้งสิ้น · ผลผลิตที่ไม่ได้แก้)
    assert not _has(res, "total", "changed", "รวมทั้งสิ้น")
    assert not _has(res, "total", "changed", "การตรวจสอบเอกสารงบประมาณ")


def test_edge_year_header_with_buddhist_era_prefix_still_parsed(edge):
    fb = edge[1]
    assert fb.coverage.unparsed == []
    assert {a.column for a in fb.amounts if a.table == "mtef"} >= {"2569", "2570", "2571"}


def test_edge_swapped_money_between_projects_found_but_plan_not(edge):
    res = edge[2]
    assert _has(res, "total", "changed", "โครงการพัฒนาระบบตรวจสอบเอกสารงบประมาณดิจิทัล", "งบดำเนินงาน")
    assert _has(res, "total", "changed", "โครงการพัฒนาศักยภาพผู้ตรวจสอบเอกสาร", "งบดำเนินงาน")
    assert not _has(res, "total", "changed", "แผนงานยุทธศาสตร์พัฒนาระบบตรวจสอบเอกสาร")


def test_edge_child_wrong_parent_right_is_internal_finding(edge):
    res = edge[2]
    assert _has(res, "consist", "sum_mismatch", "แผนงานพื้นฐานด้านการบริหารจัดการงบประมาณ", within="B")
    assert _has(res, "consist", "cross_table_mismatch", "การเผยแพร่ข้อมูลงบประมาณ", within="B")
    assert not [f for f in res.findings if f.topic == "consist" and f.within == "A"]


def test_edge_duplicate_text_items_kept_apart(edge):
    fa, _fb, res = edge
    dups = [i for i in fa.items if i.label == "ค่าจ้างเหมาบริการ"]
    assert len(dups) == 2 and len({i.key for i in dups}) == 2
    hits = [f for f in res.findings if f.topic == "items" and "ค่าจ้างเหมาบริการ" in f.subject]
    assert len(hits) == 1 and (hits[0].a.value, hits[0].b.value) == ("500000", "450000")


def test_edge_numbering_and_agency_title(edge):
    res = edge[2]
    assert _has(res, "format", "changed", "การเผยแพร่ข้อมูลงบประมาณ", "2.2", "2.2.")
    assert _has(res, "format", "changed", "ชื่อหน่วยงาน", "แห่งชาติ")


def test_not_found_note_mentions_unreadable_part():
    a = ex.BookFacts("v", "p", 2570, "draft", "")
    b = ex.BookFacts("v", "p", 2570, "act", "")
    b.coverage.pages_no_text = [9]
    f = cmp.Finding("x", "items", cmp.K_ONLY_A, "รายการ")
    cmp._not_found_vs_unread(a, b, [f])
    assert "ฉบับ B มีส่วนที่ระบบอ่านไม่ได้" in f.note and "ไม่ได้แปลว่าไม่มีแน่นอน" in f.note


# ── ซ่อมข้อความไทยจากชั้นข้อความ PDF ─────────────────────────────────────────
from redbook.pdfbook.thai_repair import repair  # noqa: E402


@pytest.mark.parametrize("raw,fixed", [
    ("ต าแหน่ง", "ตำแหน่ง"),                    # นิคหิตหายเหลือช่องว่าง
    ("น้ํา", "น้ำ"),              # น้ + ํ + า → น้ำ
    ("ดําเนินงาน", "ดำเนินงาน"),
    ("ท่ี", "ที่"),          # วรรณยุกต์มาก่อนสระบน → สลับ
    ("ก้้าว", "ก้าว"),            # วรรณยุกต์ซ้ำ
    ("าน", "ฐาน"),                          # PUA ฐ ไม่มีเชิง
    ("ปา", "ป่า"),                     # PUA ไม้เอกเลื่อนต่ำ
])
def test_thai_repair_cases(raw, fixed):
    assert repair(raw) == fixed
    assert repair(fixed) == fixed                 # ทำซ้ำได้ผลเดิม


@pytest.mark.parametrize("ok", ["งบประมาณรายจ่าย", "ผลสัมฤทธิ์หรือประโยชน์ที่คาดว่าจะได้รับ", "น้ำประปา",
                                "ที่ดินและสิ่งก่อสร้าง", "ค่าตอบแทน ใช้สอยและวัสดุ", "1,234.5678 ล้านบาท"])
def test_thai_repair_leaves_normal_text_alone(ok):
    assert repair(ok) == ok


# ── ชุดพัฒนาเล่มจริง (private · อยู่นอก Git) ──────────────────────────────────
# 🔴 เป็นเทสต์ถดถอยของ *ชุดพัฒนา* ที่ใช้ปรับโปรไฟล์ — ไม่ใช่ผลประเมิน · ค่าคาดหวังมาจากการอ่านผลของระบบ
# เทียบกับภาพหน้าเล่มระหว่างพัฒนา (ไม่ใช่เฉลยอิสระ) · ไม่มีไฟล์ = SKIPPED: PRIVATE DEV SET NOT AVAILABLE
import os  # noqa: E402

_DEV = Path(os.environ.get("REDBOOK_PDFPAIR_DEV_DIR",
                           Path.home() / "dev" / "redbook-verify-data" / "pdfpair_dev" / "extracts"))
_dev = pytest.mark.skipif(not (_DEV / "D1_A_V11_2570_draft.pdf").exists(),
                          reason="PRIVATE DEV SET NOT AVAILABLE")


def _dev_facts(name, fy):
    p = _DEV / f"{name}.pdf"
    n = len(reader.page_texts(p))
    return ex.extract(reader.page_words(p, list(range(1, n + 1))), fiscal_year=fy)


DEV_PAIRS = [("D1_A_V11_2570_draft", "D1_B_V11_2570_act", 2570, 2570),
             ("D2_A_V11_2570_draft", "D2_B_V11_2570_act", 2570, 2570),
             ("D3_A_V12_2570_draft", "D3_B_V12_2570_act", 2570, 2570),
             ("D1x_A_V11_2569_act", "D1x_B_V11_2570_act", 2569, 2570),
             ("D2x_A_V11_2569_act", "D2x_B_V11_2570_act", 2569, 2570),
             ("D3x_A_V12_2569_act", "D3x_B_V12_2570_act", 2569, 2570)]


@pytest.fixture(scope="module")
def dev_results():
    return {pa: (lambda a, b: (a, b, cmp.compare(a, b)))(_dev_facts(pa, fa), _dev_facts(pb, fb))
            for pa, pb, fa, fb in DEV_PAIRS}


@_dev
@pytest.mark.parametrize("pair", [p[0] for p in DEV_PAIRS])
def test_dev_every_row_read_all_sections_found(dev_results, pair):
    a, b, res = dev_results[pair]
    for bf in (a, b):
        assert bf.coverage.unparsed == [] and bf.coverage.pages_no_text == []
        assert {"vision", "mission", "outcome", "years", "mtef", "econ", "summary", "detail",
                "offbudget"} <= set(bf.coverage.sections_found)
    # เล่มที่เผยแพร่แล้วต้องไม่มีข้อสังเกต "ภายในเล่ม" ปลอม
    assert not [f for f in res.findings if f.topic in ("consist",) or f.kind == "sum_mismatch"]


@_dev
def test_dev_draft_act_reductions(dev_results):
    _a, _b, d1 = dev_results["D1_A_V11_2570_draft"]
    f = _has(d1, "total", "changed", "งบประมาณรายจ่ายของหน่วยงาน")
    assert f and Decimal(f.delta) == Decimal("-470800")
    _a, _b, d3 = dev_results["D3_A_V12_2570_draft"]
    f = _has(d3, "total", "changed", "งบประมาณรายจ่ายของหน่วยงาน")
    assert f and Decimal(f.delta) == Decimal("-2103600")
    _a, _b, d2 = dev_results["D2_A_V11_2570_draft"]
    assert d2.findings == []


@_dev
def test_dev_hidden_offpage_text_is_dropped(dev_results):
    a, _b, _res = dev_results["D1_A_V11_2570_draft"]
    assert a.coverage.hidden_words > 0


def test_fiscal_year_ignores_forward_estimate_range():
    # หน่วยงานเล็ก: หัวข้อประมาณการล่วงหน้า 2571 - 2573 อยู่ในหน้าที่ใช้หาปีด้วย — ปีของเล่มต้องเป็น 2570
    page = "ข้อมูลเปรียบเทียบ ปีงบประมาณ พ.ศ. 2568 - 2570 ประมาณการรายจ่ายล่วงหน้า ปีงบประมาณ พ.ศ. 2571 - 2573"
    assert ex.detect_meta([page], 0)[0] == 2570
    assert ex.detect_meta(["ปีงบประมาณ พ.ศ. 2567 - 2569", "ปีงบประมาณ พ.ศ. 2570 - 2572"], 0)[0] == 2569
    assert ex.detect_meta(["ประจำปีงบประมาณ พ.ศ. 2570"], 0)[0] == 2570


def _ch(t, x0, x1, top=100.0):
    return {"text": t, "x0": x0, "x1": x1, "top": top, "bottom": top + 14}


def test_words_from_chars_keeps_marks_in_stream_order():
    # จับจากเล่มจริง: สระบน/วรรณยุกต์กว้าง 0 pt วางเยื้องซ้ายของพยัญชนะ — ต้องเกาะคำเดิมตามลำดับ stream
    chars = [_ch("ท", 172.3, 177.5), _ch("ี", 177.85, 177.85), _ch("่", 177.72, 177.72),
             _ch("ม", 177.45, 182.75), _ch("ี", 183.14, 183.14)]
    assert [w.text for w in reader.words_from_chars(chars)] == ["ที่มี"]


def test_words_from_chars_zero_width_space_is_nikhahit():
    # "ต่ำกว่า" — ฟอนต์ในเล่มเก็บนิคหิตของ ำ เป็นช่องว่างกว้าง 0 pt
    chars = [_ch("ต", 228.2, 233.4), _ch(" ", 233.86, 233.86), _ch("่", 234.4, 234.4),
             _ch("า", 233.3, 236.7), _ch("ก", 236.7, 241.7), _ch("ว", 241.7, 246.0),
             _ch("่", 246.1, 246.1), _ch("า", 245.9, 249.3), _ch(" ", 249.3, 252.3), _ch("1", 253.3, 257.5)]
    ws = reader.words_from_chars(chars)
    assert [ex.clean(w.text) for w in ws] == ["ต่ำกว่า", "1"]


def test_unit_before_another_amount_stays_in_label():
    chars = []
    x = 100.0
    for word in ("ราคาต่อหน่วยต่ำกว่า", "1", "ล้านบาท", "960,000", "บาท"):
        for c in word:
            if c in reader.THAI_MARKS:          # เครื่องหมายกว้าง 0 pt วางบนพยัญชนะ (เหมือนเล่มจริง)
                chars.append(_ch(c, x - 0.3, x - 0.3))
                continue
            chars.append(_ch(c, x, x + 4.0))
            x += 4.0
        x += 6.0
    pt = pdftext.PageText(page=1, width=600, height=800, words=tuple(reader.words_from_chars(chars)),
                          lines=())
    row = layout.rows_of_page(pt)[0]
    assert [c.raw for c in row.cells] == ["960,000"]
    assert row.label.endswith("1 ล้านบาท")


@_dev
def test_dev_thai_text_not_garbled(dev_results):
    import re
    garbled = re.compile(r"\s[\u0e31\u0e34-\u0e3a\u0e47-\u0e4e]|[\u0e48-\u0e4b]{2}"
                         r"|ดาเนิน|จานวน|สาหรับ|สานักงาน|สาเร็จ|ทีมี่")
    a, _b, _res = dev_results["D1_A_V11_2570_draft"]
    labels = [n.label for n in a.nodes.values()] + [i.label for i in a.items] + [t.text for t in a.texts]
    assert not [s for s in labels if garbled.search(s)]
    assert any("ดำเนินงาน" in s for s in labels)


# ── ปีงบของเล่ม: แยกหลักฐานตามบริบท (REVIEW 6340632605) ─────────────────────────
@pytest.mark.parametrize("texts, year, origin, status", [
    # ปีเล่มระบุเดี่ยว + ช่วงประมาณการล่วงหน้า — เดิมได้ 2573
    (["ประจำปีงบประมาณ พ.ศ. 2570 ประมาณการรายจ่ายล่วงหน้า ปีงบประมาณ พ.ศ. 2571 - 2573"], 2570, "stated", "ok"),
    # ปีเล่มระบุเดี่ยว + ช่วงเปรียบเทียบย้อนหลังที่ตรงกัน
    (["ประจำปีงบประมาณ พ.ศ. 2570", "ข้อมูลเปรียบเทียบ ปีงบประมาณ พ.ศ. 2568 - 2570"], 2570, "stated", "ok"),
    # ไม่มีปีเล่มเดี่ยว — ใช้ปลายช่วงเปรียบเทียบ
    (["ปีงบประมาณ พ.ศ. 2568 - 2570 ประมาณการรายจ่ายล่วงหน้า ปีงบประมาณ พ.ศ. 2571 - 2573"],
     2570, "comparison_range", "ok"),
    (["ปีงบประมาณ พ.ศ. 2567 - 2569", "ปีงบประมาณ พ.ศ. 2570 - 2572"], 2569, "comparison_range", "ok"),
    # มีแต่ช่วงประมาณการ — อนุมานได้แต่ต้องบอกว่าไม่แน่ใจ
    (["ประมาณการรายจ่ายล่วงหน้า ปีงบประมาณ พ.ศ. 2571 - 2573"], 2570, "forward_range", "uncertain"),
    # ปีขัดกัน — ไม่เลือกเอง
    (["ประจำปีงบประมาณ พ.ศ. 2570", "ประจำปีงบประมาณ พ.ศ. 2569"], None, "", "conflict"),
    (["ประจำปีงบประมาณ พ.ศ. 2570", "ข้อมูลเปรียบเทียบ ปีงบประมาณ พ.ศ. 2567 - 2569"], None, "", "conflict"),
    # หาปีไม่ได้
    (["งบประมาณรายจ่าย สำนักงานสาธิต"], None, "", "not_found"),
])
def test_fiscal_year_evidence_by_context(texts, year, origin, status):
    y = ex.detect_year(texts, 0)
    assert (y.year, y.origin, y.status) == (year, origin, status)
    assert y.candidates or status == "not_found"
    assert ex.detect_meta(texts, 0)[0] == year


# ── 0.5.1: ปกเล่มจริง (พบจากหน้าด่านก่อนส่งออก · ชุดพัฒนา) ─────────────────────────────────────
@pytest.mark.parametrize("cue", ["ประจ่ำ", "ประจำา"])
def test_year_stated_cue_survives_cover_font_glitches(cue):
    # ภาพพิมพ์ "ประจำปีงบประมาณ พ.ศ. 2569" แต่ชั้นข้อความของฟอนต์ปกได้ไม้เอกเกิน / สระอาเกิน
    y = ex.detect_year([f"งบประมาณรายจ่าย\n{cue}ปีงบประมาณ พ.ศ. 2569"], 0)
    assert (y.year, y.origin, y.status) == (2569, "stated", "ok")
    assert y.evidence[0]["cue"].endswith(cue)                # หลักฐานเก็บข้อความดิบตามที่อ่านได้


@pytest.mark.parametrize("line", ["ผลการดำเนินงานของปีงบประมาณ 2569", "งานค่ำปีงบประมาณ 2569",
                                  "ประจักษ์ปีงบประมาณ 2569"])
def test_year_cue_tolerance_does_not_invent_a_stated_year(line):
    assert ex.detect_year([line], 0).origin == "single_mention"


def test_year_from_agency_comparison_heading_when_cover_has_none():
    # 0.5.2 (กิ๊ฟ): ปกไม่มีปีในชั้นข้อความ — หน้า 2 ของหน่วยงานมีหัวข้อเปรียบเทียบ 3 ปี ปลายช่วง = ปีของเล่ม
    texts = ["ฉบับปรับปรุง ตามพระราชบัญญัติงบประมาณรายจ่าย", "", "", "หน่วยงานสาธิต\nงบประมาณ ปี 2569 ปี 2570",
             "4. เปรียบเทียบงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. 2568 - 2570 จำแนกตามประเภทงบประมาณรายจ่าย",
             "ปีงบประมาณ พ.ศ. 2566 - 2568 (หน่วยงานถัดไป)"]
    assert ex.detect_year(texts, 4).status == "not_found"                 # เดิม: อ่านหน้าเริ่มหน้าเดียว
    y = ex.detect_year(texts, 4, 5)
    assert (y.year, y.origin, y.status) == (2570, "comparison_range", "ok") and y.evidence[0]["page"] == 5


def test_year_pages_never_cross_into_the_next_agency():
    assert ex.year_pages(700, 632, 660) == [1, 2, 3, 632, 633, 634]
    assert ex.year_pages(700, 632, 633) == [1, 2, 3, 632, 633]            # หน่วยงาน 2 หน้า — ไม่อ่านหน้าถัดไป
    assert ex.year_pages(700, 632) == [1, 2, 3, 632]
    assert ex.year_pages(2, 2, 9) == [1, 2]


def _spread_cover(path: Path) -> Path:
    """ปกกางสองหน้าแบบเล่ม 12 จริง: MediaBox 1244 pt (ปกหลัง + สัน + ปกหน้า) · CropBox เปิดเฉพาะปกหน้า ·
    ปกหลังมีปีของเล่มก่อนอยู่ในชั้นข้อความ (คนมองไม่เห็น)"""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=1244, height=836)
    font = gen._font()
    page.insert_text(fitz.Point(100, 120), "ประจำปีงบประมาณ พ.ศ. 2569", fontsize=20, fontname="thai", fontfile=font)
    page.insert_text(fitz.Point(760, 420), "ประจำปีงบประมาณ พ.ศ. 2570", fontsize=20, fontname="thai", fontfile=font)
    page.set_cropbox(fitz.Rect(648, 0, 1224, 836))
    doc.save(str(path))
    return path


def test_reader_uses_the_crop_box_people_see(tmp_path):
    p = _spread_cover(tmp_path / "spread.pdf")
    pt = reader.page_words(p, [1])[0]
    assert (round(pt.width), round(pt.height)) == (576, 836) == tuple(round(x) for x in reader.page_size(p, 1))
    vis = ex.visible_text(pt)
    assert "2570" in vis and "2569" not in vis               # ข้อความปกหลังไม่ใช่หลักฐาน
    y = ex.detect_year([vis], 0)
    assert (y.year, y.status) == (2570, "ok")
    w = next(w for w in pt.words if "2570" in w.text)
    assert 760 - 648 <= w.x0 < 576                            # พิกัดเทียบมุม CropBox = ตรงภาพที่ PDFium วาด


def test_fiscal_year_status_roundtrip_and_old_records():
    bf = ex.BookFacts("pdfbook-0.2.0", "p", None, "", "x")
    bf.year_status, bf.year_origin, bf.year_candidates = "conflict", "", ["2570 (stated)", "2569 (stated)"]
    back = ex.BookFacts.from_dict(bf.to_dict())
    assert (back.year_status, back.year_candidates) == ("conflict", ["2570 (stated)", "2569 (stated)"])
    old = bf.to_dict()
    for k in ("year_status", "year_origin", "year_candidates"):
        old.pop(k)
    legacy = ex.BookFacts.from_dict(old)            # รอบเก่าที่ไม่มีฟิลด์ — ไม่ rewrite ไม่พัง
    assert legacy.year_status == "" and legacy.year_candidates == []


def test_run_view_warns_when_year_not_certain():
    a = ex.BookFacts("v", "p", 2570, "draft", "x")
    a.year_status = "ok"
    b = ex.BookFacts("v", "p", None, "act", "x")
    b.year_status, b.year_candidates = "conflict", ["2570 (stated)", "2569 (stated)"]
    v = svc.RunView({"id": "r"}, cmp.compare(a, b), [], {}, a, b)
    w = v.year_warnings
    assert len(w) == 1 and w[0][0] == "B" and "2569" in w[0][1]
    assert "ไม่แน่ใจ" in v.side_label("B") or "ไม่ทราบ" in v.side_label("B")


def test_web_overview_shows_year_warning(client, web_run, monkeypatch):
    _pid, rid, _t = web_run
    real_view = svc.view

    def fake_view(r):
        v = real_view(r)
        v.facts_b.fiscal_year, v.facts_b.year_status = None, "conflict"
        v.facts_b.year_candidates = ["2570 (stated)", "2569 (stated)"]
        return v
    monkeypatch.setattr(svc, "view", fake_view)
    html = client.get(f"/pdfpair/runs/{rid}").text
    assert "ปีงบของฉบับ B" in html and "หลักฐานปีงบขัดกัน" in html and "ไม่ทราบปีงบ" in html
    assert "รูปแบบการเทียบที่ใช้" in html


def test_web_overview_no_year_warning_when_ok(client, web_run):
    _pid, rid, _t = web_run
    assert "ปีงบของฉบับ" not in client.get(f"/pdfpair/runs/{rid}").text


# ── REVIEW 6340074844 ข้อ 1: precision · ข้อ 2: แกนสถานะ · ข้อ 3: identity ─────────────
_E = ex.Evidence(1, (0.0, 0.0, 10.0, 10.0), "x")


def _a(table, node, col, raw, unit="ล้านบาท", **kw):
    v = parse_amount(raw)
    return ex.Amount(table, node, col, "" if v is None else str(v), unit, raw, _E, **kw)


def test_amount_precision_is_separate_from_value_and_unit():
    m = _a("mtef", "n", "2570", "0.1760")
    assert (m.value, m.decimals, m.scale, m.tolerance) == ("0.1760", 4, Decimal(1_000_000), Decimal("0.00005"))
    b = _a("detail", "n", "รวม", "960,000", "บาท")
    assert (b.decimals, b.scale, b.tolerance) == (0, Decimal(1), Decimal("0.5"))
    assert _a("mtef", "n", "2570", "1.5").tolerance == Decimal("0.05")


def _sum_book(raws):
    bf = ex.BookFacts("v", "p", 2570, "draft", "x")
    c1, c2 = P.CATEGORIES[0], P.CATEGORIES[1]
    bf.amounts = [_a(P.SEC_SUMMARY, "total", c1, raws[0]), _a(P.SEC_SUMMARY, "total", c2, raws[1]),
                  _a(P.SEC_SUMMARY, "total", P.COL_TOTAL, raws[2])]
    return [f for f in cmp.compare(bf, bf).findings if f.kind == cmp.K_SUM and f.within == "A"]


def test_sum_tolerance_follows_printed_precision():
    # พิมพ์ 1 ตำแหน่ง: 1.2 + 1.3 ↔ 2.6 คลาดได้จากการปัดแต่ละค่า (≤ 0.05 × 3) — ไม่ใช่ข้อสังเกต
    assert _sum_book(("1.2", "1.3", "2.6")) == []
    # พิมพ์ 4 ตำแหน่ง ส่วนต่างเท่ากัน = เกินเกณฑ์ปัด
    assert len(_sum_book(("1.2000", "1.3000", "2.6000"))) == 1


def test_dash_is_distinct_from_not_found_and_zero():
    a = ex.BookFacts("v", "p", 2570, "draft", "x")
    b = ex.BookFacts("v", "p", 2570, "act", "x")
    a.dashes = [_a(P.SEC_MTEF, "n", "2571", "-", status="dash")]
    b.amounts = [_a(P.SEC_MTEF, "n", "2571", "0.0000"), _a(P.SEC_MTEF, "n", "2572", "1.0000")]
    a.amounts = [_a(P.SEC_MTEF, "n", "2572", "0.0000")]
    fs = cmp.compare(a, b).findings
    dash = [f for f in fs if f.kind == cmp.K_DASH_VS_VALUE]
    assert len(dash) == 1 and dash[0].a.status == "dash" and svc.amount_text(dash[0].a) == "ขีด (–) ไม่มีค่า"
    zero = [f for f in fs if f.column == "ปี 2572"]
    assert zero and zero[0].kind == cmp.K_CHANGED and zero[0].a.value == "0.0000"     # ศูนย์ = ค่า ไม่ใช่ขีด


def test_unit_without_evidence_is_flagged_and_needs_confirmation():
    flags = ["unit_not_in_document"]
    a = ex.BookFacts("v", "p", 2570, "draft", "x")
    b = ex.BookFacts("v", "p", 2570, "act", "x")
    a.amounts = [_a(P.SEC_SUMMARY, "total", P.COL_TOTAL, "5.0000", unit_origin="profile_default", flags=flags)]
    b.amounts = [_a(P.SEC_SUMMARY, "total", P.COL_TOTAL, "4.0000", unit_origin="table_decl")]
    assert a.amounts[0].needs_confirmation and not b.amounts[0].needs_confirmation
    f = [x for x in cmp.compare(a, b).findings if x.kind == cmp.K_CHANGED][0]
    assert f.caveats and "ไม่ได้มาจากเอกสาร" in f.caveats[0]
    assert "ไม่พบในเอกสาร" in svc.unit_note(f.a) and svc.unit_note(f.b).startswith("หน่วยจากบรรทัดประกาศ")


def test_extraction_records_origin_flags_and_dashes():
    from redbook.pdfbook.layout import Cell, Row
    bf = ex.BookFacts("v", "p", 2570, "draft", "x")
    r = Row(1, "x", "x", (), (), 0, 0, 10, 10, 0)
    ex._amt(bf, P.SEC_MTEF, "n", "2571", Cell("-", None, 0, 0, 1, 1), r, unit="ล้านบาท",
            unit_origin="table_decl", column_origin="header")
    ex._amt(bf, P.SEC_MTEF, "n", "2572", Cell("1.5000", Decimal("1.5000"), 0, 0, 1, 1), r, unit="ล้านบาท",
            unit_origin="profile_default", column_origin="nearest_column")
    assert [d.status for d in bf.dashes] == ["dash"] and len(bf.amounts) == 1
    m = bf.amounts[0]
    assert m.status == "read" and set(m.flags) == {"unit_not_in_document", "column_nearest"}
    assert m.unit_ev is None and m.column_ev is not None


def test_old_records_without_new_fields_still_load():
    old_amount = {"table": "mtef", "node": "n", "column": "2570", "value": "1.0", "unit": "ล้านบาท",
                  "raw": "1.0", "ev": {"page": 1, "bbox": [0, 0, 1, 1], "text": "x"}}
    bf = ex.BookFacts("v", "p", 2570, "", "x").to_dict()
    bf["amounts"] = [old_amount]
    for k in ("dashes", "identity_issues"):
        bf.pop(k)
    back = ex.BookFacts.from_dict(bf)
    assert back.amounts[0].unit_origin == "" and back.amounts[0].flags == [] and back.dashes == []
    old_f = {"id": "x", "topic": "total", "kind": "changed", "subject": "s",
             "a": {"value": "1", "raw": "", "unit": "", "page": None, "bbox": None, "text": ""},
             "b": {"value": "2", "raw": "", "unit": "", "page": None, "bbox": None, "text": ""}}
    f = cmp.Finding.from_dict(old_f)
    assert f.caveats == [] and f.a.flags == [] and f.a.status == ""


def test_web_csv_and_finding_page_show_origin_and_caveats(client, web_run, monkeypatch):
    rid = web_run[1]
    head = svc.export_csv(rid).splitlines()[0]
    for col in ("ค่าดิบ A", "ที่มาหน่วย A", "สถานะ B", "ต้องให้คนยืนยัน"):
        assert col in head
    real_view = svc.view

    def fake_view(r):
        v = real_view(r)
        f = next(x for x in v.result.findings if x.topic == "total" and x.a.value and x.b.value)
        f.caveats = ["หน่วยไม่ได้มาจากเอกสาร (ใช้ค่าตั้งต้นของโปรไฟล์)"]
        f.a.unit_origin = "profile_default"
        return v
    monkeypatch.setattr(svc, "view", fake_view)
    v = fake_view(rid)
    f = next(x for x in v.result.findings if x.caveats)
    html = client.get(f"/pdfpair/runs/{rid}/f/{f.id}").text
    assert "ต้องให้คนยืนยันก่อนใช้" in html and "ไม่พบในเอกสาร" in html
    assert "ต้องให้คนยืนยัน:" in client.get(f"/pdfpair/runs/{rid}").text


def _rec(key, level, label, parent=""):
    return {"key": key, "level": level, "label": label, "parent": parent, "ev": _E}


def test_identity_same_name_under_different_plans_and_parents():
    recs = [_rec("p1", P.LEVEL_PLAN, "แผนงานยุทธศาสตร์ ก"), _rec("p2", P.LEVEL_PLAN, "แผนงานยุทธศาสตร์ ข"),
            _rec("o1", P.LEVEL_OUTPUT, "ผลผลิต : บริการวิชาการ", "p1"),
            _rec("o2", P.LEVEL_OUTPUT, "ผลผลิต : บริการวิชาการ", "p2"),
            _rec("o3", P.LEVEL_OUTPUT, "ผลผลิต : งานวิจัย", "p1"),
            # กิจกรรมชื่อเดียวกันใต้ผลผลิตต่างกันในแผนงานเดียวกัน
            _rec("a1", P.LEVEL_ACTIVITY, "กิจกรรม : บริหารจัดการ", "o1"),
            _rec("a2", P.LEVEL_ACTIVITY, "กิจกรรม : บริหารจัดการ", "o3"),
            # ชื่อเดียวกันแม่เดียว (พบซ้ำในหลายตาราง) = รายการเดียว
            _rec("o3b", P.LEVEL_OUTPUT, "ผลผลิต : งานวิจัย", "p1")]
    km, issues = ex.resolve_node_keys(recs)
    assert km["o1"] != km["o2"] and km["o1"].endswith("@" + km["p1"])
    assert km["a1"] != km["a2"] and km["a1"].endswith("@" + km["o1"])
    assert km["o3"] == km["o3b"] and "@" not in km["o3"]
    assert issues == []
    km2, _ = ex.resolve_node_keys(list(reversed(recs)))     # สลับลำดับ = กุญแจเดิม
    assert km2 == km


def test_identity_unparented_occurrence_is_ambiguous_not_guessed():
    recs = [_rec("p1", P.LEVEL_PLAN, "แผนงาน ก"), _rec("p2", P.LEVEL_PLAN, "แผนงาน ข"),
            _rec("o1", P.LEVEL_OUTPUT, "ผลผลิต : บริการ", "p1"), _rec("o2", P.LEVEL_OUTPUT, "ผลผลิต : บริการ", "p2"),
            _rec("o9", P.LEVEL_OUTPUT, "ผลผลิต : บริการ")]
    km, issues = ex.resolve_node_keys(recs)
    assert km["o9"] not in (km["o1"], km["o2"])
    amb = [i for i in issues if i["kind"] == "ambiguous_parent"]
    assert len(amb) == 1 and sorted(amb[0]["candidates"]) == sorted([km["o1"], km["o2"]])


# REVIEW 6360210542: ลูกชื่อเดียวกันใต้แม่ชื่อเดียวกัน แต่แม่อยู่คนละแผนงาน — ต้องตัดสินด้วยเส้นทางของแม่
_NESTED = [_rec("p1", P.LEVEL_PLAN, "แผนงานพื้นฐาน ก"), _rec("p2", P.LEVEL_PLAN, "แผนงานยุทธศาสตร์ ข"),
           _rec("o1", P.LEVEL_OUTPUT, "ผลผลิต : บริการวิชาการ", "p1"),
           _rec("o2", P.LEVEL_OUTPUT, "ผลผลิต : บริการวิชาการ", "p2"),
           _rec("a1", P.LEVEL_ACTIVITY, "กิจกรรม : บริหารจัดการ", "o1"),
           _rec("a2", P.LEVEL_ACTIVITY, "กิจกรรม : บริหารจัดการ", "o2")]


@pytest.mark.parametrize("order", ["forward", "reversed"])
def test_identity_same_child_under_same_named_parents_in_different_plans(order):
    recs = _NESTED if order == "forward" else list(reversed(_NESTED))
    km, issues = ex.resolve_node_keys(recs)
    assert km["o1"] != km["o2"]
    assert km["a1"] != km["a2"]                        # เดิม: แม่ฐานเดียวกัน → ลูกสองตัวรวมเป็นกุญแจเดียว
    assert km["a1"] == f"{ex.node_key(P.LEVEL_ACTIVITY, 'กิจกรรม : บริหารจัดการ')}@{km['o1']}"
    assert km["a2"].endswith("@" + km["o2"]) and issues == []
    assert km == ex.resolve_node_keys(_NESTED)[0]      # สลับลำดับ = กุญแจเดิม


def test_identity_child_of_unidentified_parent_is_ambiguous_not_guessed():
    recs = _NESTED + [_rec("o9", P.LEVEL_OUTPUT, "ผลผลิต : บริการวิชาการ"),           # ตารางที่ไม่แสดงแผนงาน
                      _rec("a9", P.LEVEL_ACTIVITY, "กิจกรรม : บริหารจัดการ", "o9")]
    km, issues = ex.resolve_node_keys(recs)
    assert km["a9"] not in (km["a1"], km["a2"]) and km["o9"] not in (km["o1"], km["o2"])
    amb = {i["labels"][0]: i for i in issues if i["kind"] == "ambiguous_parent"}
    assert set(amb) == {"ผลผลิต : บริการวิชาการ", "กิจกรรม : บริหารจัดการ"}
    assert amb["กิจกรรม : บริหารจัดการ"]["candidates"] == sorted([km["a1"], km["a2"]])


def test_identity_nested_children_keep_both_amounts_and_match_across_books():
    """ระดับ BookFacts: ค่าเงินผูกกับกุญแจจริงแบบเดียวกับ ``extract`` — ลูกทั้งสองเก็บเงินแยกกัน
    ไม่กลายเป็น duplicate_cell · อีกฉบับเรียงกลับด้าน ก็ยังจับคู่ลูกตัวเดียวกัน"""
    def book(recs, k1_raw, k2_raw):
        km, issues = ex.resolve_node_keys(recs)
        bf = ex.BookFacts("v", "p", 2570, "draft", "x")
        for r in recs:
            bf.nodes.setdefault(km[r["key"]], ex.Node(km[r["key"]], r["level"], r["label"],
                                                      km.get(r["parent"], ""), 1, _E))
        bf.identity_issues = issues
        bf.amounts = [_a(P.SEC_SUMMARY, km["a1"], P.COL_TOTAL, k1_raw, unit_origin="table_decl"),
                      _a(P.SEC_SUMMARY, km["a2"], P.COL_TOTAL, k2_raw, unit_origin="table_decl")]
        ex.mark_identity(bf)
        return bf, km
    a, ka = book(_NESTED, "4.0000", "6.0000")
    b, kb = book(list(reversed(_NESTED)), "4.0000", "5.5000")
    assert {x.dec for x in a.amounts} == {Decimal("4.0000"), Decimal("6.0000")}
    assert not [x for x in a.identity_issues if x["kind"] == "duplicate_cell"]
    assert not any(x.flags for x in a.amounts)
    changed = [f for f in cmp.compare(a, b).findings if f.kind == cmp.K_CHANGED and f.topic == "total"]
    assert len(changed) == 1 and (changed[0].a.value, changed[0].b.value) == ("6.0000", "5.5000")


def test_identity_skeleton_collision_is_visible():
    recs = [_rec("i1", P.LEVEL_OUTPUT, "ผลผลิต : ค่าเช่าอาคาร"), _rec("i2", P.LEVEL_OUTPUT, "ผลผลิต : ค่าเช้าอาคาร")]
    km, issues = ex.resolve_node_keys(recs)
    assert km["i1"] == km["i2"]                                   # โครงคำเดียวกัน
    sk = [i for i in issues if i["kind"] == "skeleton_merge"]
    assert len(sk) == 1 and len(sk[0]["labels"]) == 2


def test_cross_book_match_by_skeleton_with_different_marks_is_flagged():
    def book(label):
        bf = ex.BookFacts("v", "p", 2570, "", "x")
        k = ex.node_key(P.LEVEL_OUTPUT, label)
        bf.nodes = {k: ex.Node(k, P.LEVEL_OUTPUT, label, "", 1, _E)}
        return bf, k
    a, ka = book("ค่าเช่าอาคาร")
    b, kb = book("ค่าเช้าอาคาร")
    assert ka == kb
    fs = [f for f in cmp.compare(a, b).findings if f.kind == cmp.K_LABEL_VARIANT]
    assert len(fs) == 1 and not fs[0].info
    same, _ = book("ค่าเช่าอาคาร")
    assert not [f for f in cmp.compare(a, same).findings if f.kind == cmp.K_LABEL_VARIANT]


def test_identity_issues_become_findings():
    bf = ex.BookFacts("v", "p", 2570, "", "x")
    bf.identity_issues = [{"kind": "duplicate_indicator", "key": "k", "ev": _E, "labels": ["ก", "ก"], "note": "n"}]
    fs = [f for f in cmp.compare(bf, ex.BookFacts("v", "p", 2570, "", "x")).findings if f.kind == cmp.K_IDENTITY]
    assert len(fs) == 1 and fs[0].within == "A" and not fs[0].info


@_dev
def test_dev_units_all_from_document_and_dashes_kept(dev_results):
    for pa, (a, b, _res) in dev_results.items():
        for bf in (a, b):
            assert bf.amounts and all(m.unit_origin in ex.UNIT_ORIGINS_IN_DOCUMENT for m in bf.amounts), pa
            assert not [m for m in bf.amounts if m.needs_confirmation], pa
            assert all(d.status == "dash" and d.value == "" for d in bf.dashes)
    assert sum(len(a.dashes) for a, _b, _r in dev_results.values()) > 0


# ── หน้าจอตรวจไล่ทีละข้อ (pdfpair.js / pdfpair.css) ────────────────────────────────
_STATIC = PROJECT_ROOT / "redbook" / "static"


def test_ux_assets_are_local_and_keep_no_browser_storage():
    js = (_STATIC / "pdfpair.js").read_text(encoding="utf-8")
    css = (_STATIC / "pdfpair.css").read_text(encoding="utf-8")
    for bad in ("http://", "https://", "localStorage", "sessionStorage", "indexedDB", "eval(", "innerHTML = res"):
        assert bad not in js, bad
    assert "http" not in css and "@import" not in css
    assert "prefers-reduced-motion" in css                # ผู้ตั้งค่าลดการเคลื่อนไหวไม่เห็นภาพเคลื่อนไหว
    assert "credentials: \"same-origin\"" in js


def test_ux_pages_load_assets_and_keep_plain_links(client, web_run):
    _pid, rid, _t = web_run
    html = client.get(f"/pdfpair/runs/{rid}").text
    assert '/static/pdfpair.js' in html and '/static/pdfpair.css' in html
    fid = svc.view(rid).result.findings[1].id
    page = client.get(f"/pdfpair/runs/{rid}/f/{fid}").text
    assert "data-pp-prev" in page and "data-pp-next" in page and 'class="pp-keys"' in page
    # ไม่มี JS ก็ยังทำงานได้: ปุ่มเป็นลิงก์จริง ฟอร์มส่งแบบ POST ปกติ
    assert f'href="/pdfpair/runs/{rid}/f/' in page and 'method="post"' in page
    for name in ("pdfpair.js", "pdfpair.css"):
        r = client.get(f"/static/{name}")
        assert r.status_code == 200
    csp = client.get(f"/pdfpair/runs/{rid}").headers["content-security-policy"]
    assert "script-src 'self'" in csp and "connect-src 'self'" in csp


def test_evidence_png_rendered_once_then_cached(client, web_run, monkeypatch):
    _pid, rid, _t = web_run
    svc.clear_png_cache()
    calls = []
    real = svc.reader.render_png

    def counting(*a, **kw):
        calls.append(a)
        return real(*a, **kw)
    monkeypatch.setattr(svc.reader, "render_png", counting)
    f = next(x for x in svc.view(rid).result.findings if x.a.page)
    first = client.get(f"/pdfpair/runs/{rid}/f/{f.id}/A.png")
    again = client.get(f"/pdfpair/runs/{rid}/f/{f.id}/A.png")
    assert first.status_code == again.status_code == 200 and first.content == again.content
    assert len(calls) == 1
    assert first.headers["cache-control"] == "no-store"    # ความปลอดภัยเดิม: เบราว์เซอร์ไม่เก็บภาพ


def test_png_cache_key_includes_file_hash_and_is_bounded(monkeypatch):
    svc.clear_png_cache()
    monkeypatch.setattr(svc, "PNG_CACHE_MAX_BYTES", 10)
    made = []

    def mk(tag):
        def f():
            made.append(tag)
            return b"x" * 6
        return f
    svc._png_cached(("sha1", 1), mk("a"))
    svc._png_cached(("sha2", 1), mk("b"))          # ไฟล์ต่างกัน = วาดใหม่ · เกินขนาด = ทิ้งของเก่าสุด
    svc._png_cached(("sha1", 1), mk("c"))
    assert made == ["a", "b", "c"]
    svc.clear_png_cache()


# ── เมนูรู้สาย · Preflight · Audit ของรอบ (สายเทียบเล่ม PDF) ─────────────────────────
def test_nav_points_to_this_pdfpair_run_not_excel_runs(client, web_run):
    pid, rid, _t = web_run
    html = client.get(f"/pdfpair/runs/{rid}").text
    for path in (f"/pdfpair/runs/{rid}/preflight", f"/pdfpair/runs/{rid}/export",
                 f"/pdfpair/runs/{rid}/audit", f"/projects/{pid}/pdfpair"):
        assert f'href="{path}"' in html, path
    assert 'href="/preflight"' not in html and 'href="/t1b/runs"' not in html
    home = client.get("/").text                     # หน้าอื่นของระบบ: เมนูเดิม (สาย Excel)
    assert 'href="/preflight"' in home and 'href="/export"' in home and 'href="/audit"' in home


def _uncertain_view(monkeypatch, sides, year=None):
    real_view = svc.view

    def fake(r):
        v = real_view(r)
        for side in sides:
            bf = v.facts_a if side == "A" else v.facts_b
            bf.year_status, bf.year_origin, bf.fiscal_year = "conflict", "", year
            bf.year_candidates = ["2570 (stated)", "2569 (stated)"]
        return v
    monkeypatch.setattr(svc, "view", fake)


def test_preflight_blocks_until_reviewer_confirms_year(client, web_run, monkeypatch):
    _pid, rid, token = web_run
    _uncertain_view(monkeypatch, ["B"])
    yc = next(c for c in svc.preflight(rid).checks if c.key == "years")
    assert not yc.ok and "ฉบับ B" in yc.detail
    # ยังไม่ติ๊กว่าดูภาพแล้ว / ปีไม่ใช่ พ.ศ. = ไม่รับ
    r = client.post(f"/pdfpair/runs/{rid}/year", data={CSRF_FIELD: token, "side": "B", "year": "2570"})
    assert r.status_code == 400 and "ดูปีงบจากภาพหน้าเอกสาร" in r.text
    r = client.post(f"/pdfpair/runs/{rid}/year", data={CSRF_FIELD: token, "side": "B", "year": "2027", "seen": "1"})
    assert r.status_code == 400 and "พ.ศ." in r.text
    r = client.post(f"/pdfpair/runs/{rid}/year", follow_redirects=False,
                    data={CSRF_FIELD: token, "side": "B", "year": "2570", "seen": "1", "note": "หน้าเริ่มหน่วยงาน"})
    assert r.status_code == 303
    yc = next(c for c in svc.preflight(rid).checks if c.key == "years")
    # ผลที่บันทึกไว้คำนวณโดยไม่มีปี (ฉบับ B) — ยืนยันแล้วยังส่งออกไม่ได้ ต้องคำนวณซ้ำเป็นรอบใหม่ (REVIEW 6356606678)
    assert not yc.ok and yc.action_post and yc.action_href.endswith("/rerun") and "ไม่มีปี" in yc.detail
    log = [e for e in pdfpair_repo.audit_entries(rid) if e["action"] == "pdfpair_year_confirmed"]
    assert log and '"year": 2570' in log[-1]["detail_json"] and "conflict" in log[-1]["detail_json"]
    assert "ผู้ตรวจยืนยัน" in svc.view(rid).side_label("B")


def test_preflight_flags_mode_that_contradicts_confirmed_years(client, web_run, monkeypatch):
    _pid, rid, _t = web_run
    _uncertain_view(monkeypatch, ["B"])
    svc.confirm_year(rid, "B", "2571", "ดูหน้าเริ่มหน่วยงานอีกครั้ง", True)      # ปีต่างจากฉบับ A แต่รอบนี้เทียบแบบปีเดียวกัน
    yc = next(c for c in svc.preflight(rid).checks if c.key == "years")
    assert not yc.ok and "สร้างรอบใหม่" in yc.action_label and "ข้ามปี" in yc.detail
    with pytest.raises(svc.PairError):
        svc.export_csv_checked(rid)
    with pytest.raises(svc.PairError, match="ต้องระบุเหตุผล"):       # เปลี่ยนปีที่ยืนยันไว้ ต้องมีเหตุผล
        svc.confirm_year(rid, "B", "2570", "", True)
    svc.confirm_year(rid, "B", "2570", "แก้ปีที่ยืนยัน", True)


def test_run_audit_lists_only_this_run(client, web_run):
    _pid, rid, _t = web_run
    es = pdfpair_repo.audit_entries(rid)
    assert es and all(e["object_id"] == rid or e["object_id"].startswith(rid + "/") for e in es)
    assert es[0]["action"] == "pdfpair_run_completed"
    assert [e["seq"] for e in es] == sorted(e["seq"] for e in es)


# ── ชั้นเล่มในเครื่อง (เลือกเล่ม A/B + หน่วยงาน) ─────────────────────────────────────
from redbook.services import pdfshelf  # noqa: E402


def test_toc_clean_repairs_font_mapping_only_where_proven():
    sc = scope
    assert sc.toc_clean("สำานักงานปลัดกระทรวงสาธารณสุข") == "สำนักงานปลัดกระทรวงสาธารณสุข"
    assert sc.toc_clean("ส�านักงานต�ารวจแห่งชาติ") == "สำนักงานตำรวจแห่งชาติ"
    assert sc.toc_clean("ส�านักงานคณะกรรมการอ้อยและน�้าตาลทราย") == "สำนักงานคณะกรรมการอ้อยและน้ำตาลทราย"
    # "บั" → "บ" เฉพาะเมื่อเล่มนั้นยืนยันว่าฟอนต์เพี้ยน (มี "บั" ที่ตามด้วยสระ/วรรณยุกต์+า)
    assert sc.toc_clean("โรงพยาบัาลบั้านแพ้ว", bo_quirk=True) == "โรงพยาบาลบ้านแพ้ว"
    assert sc.toc_clean("สำนักงานราชบัณฑิตยสภา") == "สำนักงานราชบัณฑิตยสภา"          # ไม่มีหลักฐาน = ไม่แตะ
    entries = sc.toc_entries(["(1) กรมการแพทย์ 277 ถึง 326 (4) กรมควบัคุมโรค 327 ถึง 357\n"
                              "(13) โรงพยาบัาลบั้านแพ้ว 647 ถึง 653"])
    assert [e[0] for e in entries] == ["กรมควบคุมโรค", "โรงพยาบาลบ้านแพ้ว"]


def _shelf(tmp_path, books, sha=None):
    d = tmp_path / "shelf"
    (d / "volumes").mkdir(parents=True)
    a, b = books["draft_act"]
    import shutil
    from redbook.core.hashing import sha256_file
    vols, reg = [], {"volumes": {}, "extracts": {}}
    for key, src, fy, stage in (("V11_2570_draft", a, 2570, "draft"), ("V11_2570_act", b, 2570, "act"),
                                ("V11_2569_act", a, 2569, "act"), ("V12_2570_act", b, 2570, "act")):
        shutil.copy(src, d / "volumes" / f"{key}.pdf")
        vols.append({"key": key, "page": "", "url": f"https://bb.go.th/download.php?id={len(vols)}",
                     "fiscal_year": fy, "stage": stage, "label": f"ฉบับที่ 3 เล่มที่ {key[1:3]}"})
        reg["volumes"][key] = {"sha256": sha or sha256_file(d / "volumes" / f"{key}.pdf"),
                               "retrieved_at": "2026-10-23T00:00:00+07:00"}
    import json
    (d / "manifest.json").write_text(json.dumps({"volumes": vols}, ensure_ascii=False), encoding="utf-8")
    (d / "register.json").write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    return d


def test_shelf_lists_volumes_and_suggests_counterpart(tmp_path, books, monkeypatch):
    monkeypatch.setenv(pdfshelf.SHELF_ENV, str(_shelf(tmp_path, books)))
    vs = pdfshelf.volumes()
    assert [v.key for v in vs][:2] == ["V11_2570_draft", "V11_2570_act"] and vs[-1].fiscal_year == 2569
    a = pdfshelf.get("V11_2570_draft")
    sug = [(v.key, why) for v, why in pdfshelf.suggest_b(a)]
    assert sug[0][0] == "V11_2570_act" and "ปีเดียวกัน" in sug[0][1]          # เล่มเดียวกันอีกขั้นก่อน
    assert ("V11_2569_act", sug[1][1]) == sug[1] and "ข้ามปี" in sug[1][1]
    assert "V12_2570_act" not in [k for k, _w in sug]                         # คนละเล่ม ไม่แนะนำ


def test_shelf_refuses_changed_file_and_protected_agency(tmp_path, books, monkeypatch):
    monkeypatch.setenv(pdfshelf.SHELF_ENV, str(_shelf(tmp_path, books, sha="0" * 64)))
    with pytest.raises(pdfshelf.ShelfError, match="SHA-256"):
        pdfshelf.verify(pdfshelf.get("V11_2570_draft"))
    with pytest.raises(pdfshelf.ShelfError, match="กันไว้"):
        pdfshelf.start("V11_2570_draft", "V11_2570_act", "สถาบันวิจัยระบบสาธารณสุข (สวรส.)")
    assert pdfshelf.is_protected("สถาบันวัคซีนแห่งชาติ (องค์การมหาชน)")


def test_shelf_page_without_volumes_explains_how_to_add(client, tmp_path, monkeypatch):
    monkeypatch.setenv(pdfshelf.SHELF_ENV, str(tmp_path / "empty"))
    html = client.get("/pdfpair/shelf").text
    assert "ยังไม่มีเล่มบนชั้นเล่ม" in html and "shelf_add.py" in html and "ไม่ออกอินเทอร์เน็ต" in html
    from redbook import privacy
    assert privacy.find_absolute_paths(html) == []                          # ไม่เปิดเผยเส้นทางในเครื่อง


def test_dashboard_counts_pdfs_and_pdfpair_runs(client, web_run):
    pid, _rid, _t = web_run
    html = client.get("/").text
    i = html.index(f'/projects/{pid}"')
    row = html[i:html.index("</tr>", i)]
    nums = [int(x) for x in __import__("re").findall(r'<td class="num">(\d+)</td>', row)]
    assert nums[:1] == [2] and nums[1] >= 1                                   # PDF 2 ไฟล์ · รอบเทียบ ≥ 1


@_dev
def test_dev_shelf_run_equals_extract_run_and_reads_only_agency_pages(tmp_path, monkeypatch):
    shelf = _DEV.parent                                 # pdfpair_dev (manifest + register + volumes)
    monkeypatch.setenv(pdfshelf.SHELF_ENV, str(shelf))
    names = pdfshelf.agencies(pdfshelf.get("V11_2570_draft"))
    assert "สถาบันรับรองคุณภาพสถานพยาบาล (องค์การมหาชน)" in names
    assert not [n for n in names if pdfshelf.is_protected(n)]
    from redbook.storage import repository as repo, source_pdfs
    _pid, rid = pdfshelf.start("V11_2570_draft", "V11_2570_act", "สถาบันรับรองคุณภาพสถานพยาบาล (องค์การมหาชน)")
    run = pdfpair_repo.get_run(rid)
    sa = run["scope"]["A"]
    assert (sa["first"], sa["last"], sa["method"]) == (655, 683, scope.METHOD_TOC)
    assert set(sa["pages_read"]) == set(range(1, 31)) | set(range(655, 684))   # สารบัญ + หน้าของหน่วยงานเท่านั้น
    shelf_kinds = sorted((x["kind"], x["delta"]) for x in run["result"]["findings"] if x["topic"] == "items")
    a, b = _dev_facts("D1_A_V11_2570_draft", 2570), _dev_facts("D1_B_V11_2570_act", 2570)
    ext_kinds = sorted((f.kind, f.delta) for f in cmp.compare(a, b).findings if f.topic == "items")
    assert shelf_kinds == ext_kinds


# ── REVIEW 6356606678: ปีที่ยืนยัน → รอบใหม่ · ตรวจครบ ≠ พร้อมใช้ · CSV ตรงไบต์ · ทุก route ผ่านด่าน ──────
import csv as _csv  # noqa: E402
import hashlib  # noqa: E402
import io as _io  # noqa: E402
import json  # noqa: E402


def _fresh_run(pid, **kw):
    return svc.run(pid, agency=AG, **kw)


def _tamper(rid, mode=None, **sides):
    """จำลองรอบที่ผลถูกคำนวณด้วยปีอื่น/ไม่มีปี — แก้ข้อเท็จจริงที่บันทึกไว้ตรง ๆ (เฉพาะในเทสต์)"""
    from redbook.storage.db import connect
    conn = connect()
    try:
        r = conn.execute("SELECT * FROM pdfpair_runs WHERE id = ?", (rid,)).fetchone()
        for side, (fy, status) in sides.items():
            col = f"facts_{side.lower()}_json"
            d = json.loads(r[col])
            d["fiscal_year"], d["year_status"] = fy, status
            d["year_origin"] = "" if status in ("conflict", "not_found") else "forward_range"
            conn.execute(f"UPDATE pdfpair_runs SET {col} = ? WHERE id = ?",
                         (json.dumps(d, ensure_ascii=False), rid))
        if mode:
            res = json.loads(r["result_json"])
            res["mode"] = mode
            conn.execute("UPDATE pdfpair_runs SET mode = ?, result_json = ? WHERE id = ?",
                         (mode, json.dumps(res, ensure_ascii=False), rid))
    finally:
        conn.close()


def _decide_all(rid, choice="checked", note=""):
    v = svc.view(rid)
    for f in v.result.findings:
        if not f.info and f.id not in v.decisions:
            svc.decide(rid, f.id, choice, note)


def test_unknown_year_confirmed_same_year_creates_new_run_and_blocks_old(client, web_run):
    pid, _rid, token = web_run
    old = _fresh_run(pid)
    _tamper(old, B=(None, "not_found"))
    _decide_all(old)
    before = svc.view(old)
    old_decisions = dict(before.decisions)
    assert before.needs_rerun is False and svc.preflight(old).use_status == "in_review"
    svc.confirm_year(old, "B", "2570", "หน้าเริ่มหน่วยงาน", True)
    v = svc.view(old)
    assert v.year_mismatch == ["B"] and v.mode_for_years == cmp.MODE_SAME_YEAR == v.result.mode
    yc = next(c for c in svc.preflight(old).checks if c.key == "years")
    assert not yc.ok and yc.action_post            # โหมดเดิมตรง แต่ผลคำนวณโดยไม่มีปี = ยังใช้ไม่ได้
    assert client.get(f"/pdfpair/runs/{old}/export.csv").status_code == 409
    r = client.post(f"/pdfpair/runs/{old}/rerun", data={CSRF_FIELD: token}, follow_redirects=False)
    assert r.status_code == 303
    new = r.headers["location"].split("/")[3]
    nv = svc.view(new)
    assert nv.facts_b.fiscal_year == 2570 and nv.facts_b.year_status == "confirmed"
    assert nv.facts_b.year_origin == "reviewer_confirmed" and nv.supersedes == old and not nv.needs_rerun
    assert nv.decisions == {}                       # ไม่คัดลอกคำตัดสินเดิมมาทับ
    # รอบเดิม: บล็อก แต่ผลและคำตัดสินเดิมอยู่ครบ
    ov = svc.view(old)
    assert ov.superseded_by == new and ov.decisions == old_decisions
    assert ov.facts_b.fiscal_year is None and svc.preflight(old).use_status == "blocked"
    f = next(x for x in ov.result.findings if not x.info)
    with pytest.raises(svc.PairError, match="ถูกแทน"):
        svc.decide(old, f.id, "fix", "เปลี่ยน")
    with pytest.raises(svc.PairError, match="ถูกแทน"):
        svc.confirm_year(old, "A", "2570", "x", True)
    with pytest.raises(svc.PairError):
        svc.rerun(old)                              # แทนซ้ำไม่ได้
    yc_old = next(c for c in svc.preflight(old).checks if c.key == "years")
    assert not yc_old.action_post and new in yc_old.action_href     # ไม่เสนอปุ่มคำนวณซ้ำบนรอบที่ถูกแทน
    assert "/rerun" not in client.get(f"/pdfpair/runs/{old}/preflight").text
    assert client.get(f"/pdfpair/runs/{old}/export.csv").status_code == 409
    assert "รอบนี้ถูกบล็อก" in client.get(f"/pdfpair/runs/{old}").text
    assert "คำนวณแทน" in client.get(f"/pdfpair/runs/{new}").text
    # Audit เชื่อมสองรอบ
    sup = [e for e in pdfpair_repo.audit_entries(old) if e["action"] == "pdfpair_run_superseded"]
    assert sup and new in sup[0]["detail_json"] and "ไม่มีปี→2570" in sup[0]["detail_json"]
    made = [e for e in pdfpair_repo.audit_entries(new) if e["action"] == "pdfpair_run_completed"]
    assert made and f'"supersedes": "{old}"' in made[0]["detail_json"]


def test_both_years_change_but_still_cross_year_still_requires_rerun(client, web_run):
    pid = web_run[0]
    old = _fresh_run(pid)
    _tamper(old, mode=cmp.MODE_CROSS_YEAR, A=(2568, "uncertain"), B=(2569, "uncertain"))
    svc.confirm_year(old, "A", "2569", "หน้า 1 ประจำปีงบประมาณ", True)
    svc.confirm_year(old, "B", "2570", "หน้า 1 ประจำปีงบประมาณ", True)
    v = svc.view(old)
    assert v.mode_for_years == v.result.mode == cmp.MODE_CROSS_YEAR      # โหมดเหมือนเดิม…
    assert v.year_mismatch == ["A", "B"] and v.needs_rerun               # …แต่ปีที่ใช้คำนวณไม่ตรง
    assert not next(c for c in svc.preflight(old).checks if c.key == "years").ok
    new = svc.rerun(old)
    nv = svc.view(new)
    assert (nv.facts_a.fiscal_year, nv.facts_b.fiscal_year) == (2569, 2570)
    assert nv.result.mode == cmp.MODE_CROSS_YEAR and not nv.needs_rerun
    assert next(c for c in svc.preflight(new).checks if c.key == "years").ok


def test_confirmed_year_equal_to_used_year_needs_no_rerun(client, web_run):
    pid = web_run[0]
    rid = _fresh_run(pid)
    _tamper(rid, B=(2570, "uncertain"))
    svc.confirm_year(rid, "B", "2570", "", True)          # ตรงกับปีที่ใช้คำนวณ — ไม่ต้องมีเหตุผล
    assert not svc.view(rid).needs_rerun
    assert next(c for c in svc.preflight(rid).checks if c.key == "years").ok
    with pytest.raises(svc.PairError, match="ไม่ต้องคำนวณซ้ำ"):
        svc.rerun(rid)
    with pytest.raises(svc.PairError, match="ต้องระบุหน้า"):   # ต่างจากที่ระบบอ่าน ต้องมีเหตุผล
        svc.confirm_year(rid, "A", "2571", "", True)


def test_review_complete_is_not_validated_for_use(client, web_run):
    pid = web_run[0]
    rid = _fresh_run(pid)
    _decide_all(rid)
    pf = svc.preflight(rid)
    assert pf.ok and pf.use_status == "validated" and not pf.use_reasons
    v = svc.view(rid)
    act = [f for f in v.result.findings if not f.info]
    svc.decide(rid, act[0].id, "needs_more", "ยังไม่แน่ใจ ต้องดูเล่มจริง")
    svc.decide(rid, act[1].id, "not_relevant", "หน้าว่าง")
    pf = svc.preflight(rid)
    assert pf.ok and pf.use_status == "review_complete"       # ส่งออกได้ แต่ยังไม่พร้อมใช้อ้างผล
    assert any("ยังไม่ปิด" in r for r in pf.use_reasons) and any("ไม่นับ 1 ข้อ" in r for r in pf.use_reasons)
    assert svc.view(rid).decisions[act[0].id]["choice"] == "needs_more"     # ระบบไม่เปลี่ยนคำตัดสินแทน
    data = svc.export_csv_checked(rid)
    rows = list(_csv.reader(_io.StringIO(data.decode("utf-8-sig"), newline="")))
    use = {r[0]: r[-1] for r in rows[1:]}
    assert use[act[0].id] == svc.USE_LABELS["open"] and use[act[1].id] == svc.USE_LABELS["excluded"]
    assert use[act[2].id] == svc.USE_LABELS["usable"]
    log = [e for e in pdfpair_repo.audit_entries(rid) if e["action"] == "pdfpair_exported"]
    assert '"use_status": "review_complete"' in log[-1]["detail_json"]
    html = client.get(f"/pdfpair/runs/{rid}/export").text
    assert svc.USE_STATUS_LABELS["review_complete"] in html and "รุ่นเครื่องมือ" in html and "pdfbook" in html
    svc.decide(rid, act[0].id, "mismatch", "ระบบจับคู่แถวผิด")
    assert svc.preflight(rid).use_status == "review_complete"
    svc.decide(rid, act[0].id, "checked", "ดูเล่มจริงแล้ว")
    svc.decide(rid, act[1].id, "checked", "ดูอีกครั้ง")
    assert svc.preflight(rid).use_status == "validated"


def test_csv_audit_counts_records_and_hashes_downloaded_bytes(client, web_run):
    pid = web_run[0]
    rid = _fresh_run(pid)
    _decide_all(rid, note='บรรทัดแรก\nบรรทัดที่สอง, มีจุลภาค "และอัญประกาศ"\r\nบรรทัดสาม')
    r = client.get(f"/pdfpair/runs/{rid}/export.csv")
    assert r.status_code == 200 and r.content.startswith(b"\xef\xbb\xbf")
    n = len(svc.view(rid).result.findings)
    assert r.content.count(b"\n") - 1 > n                     # นับ newline จะคลาด
    assert svc.csv_records(r.content) == n
    d = json.loads([e for e in pdfpair_repo.audit_entries(rid)
                    if e["action"] == "pdfpair_exported"][-1]["detail_json"])
    assert d["rows"] == n and d["sha256"] == hashlib.sha256(r.content).hexdigest()
    assert d["bytes"] == len(r.content) and d["encoding"] == "utf-8-sig" and d["versions"]["pdfbook"]


def test_pdfpair_routes_all_gated(client, web_run):
    pid, _rid, token = web_run
    rid = _fresh_run(pid)
    # CSRF: ทุก POST ที่เปลี่ยนสถานะ
    for path, data in ((f"/pdfpair/runs/{rid}/year", {"side": "B", "year": "2570", "seen": "1"}),
                       (f"/pdfpair/runs/{rid}/rerun", {})):
        assert client.post(path, data=data).status_code in (400, 403)
    # ส่งออกมีทางเดียว = export.csv ซึ่งผ่าน preflight ฝั่งเซิร์ฟเวอร์
    assert client.get(f"/pdfpair/runs/{rid}/export.csv").status_code == 409
    src = (PROJECT_ROOT / "redbook" / "web" / "pdfpair_routes.py").read_text(encoding="utf-8")
    assert src.count("svc.export_csv(") == 0 and src.count("svc.export_csv_checked(") == 1
    # ภาพหน้าดูปีงบ: เฉพาะหน้าที่รอบนี้อ่าน
    sc = svc.view(rid).run["scope"]["B"]
    ok = client.get(f"/pdfpair/runs/{rid}/page/B/{sc['first']}.png")
    assert ok.status_code == 200 and ok.content[:4] == b"\x89PNG"
    assert client.get(f"/pdfpair/runs/{rid}/page/B/{sc['pages_in_file'] + 5}.png").status_code == 404
    html = client.get(f"/pdfpair/runs/{rid}/preflight").text
    assert f"/pdfpair/runs/{rid}/page/A/1.png" in html and "ปีที่ใช้คำนวณผลนี้" in html
    # ยืนยันปีผ่านเว็บ: เปลี่ยนปีที่ยืนยันไว้โดยไม่มีเหตุผล = ไม่รับ
    _tamper(rid, B=(None, "conflict"))
    assert client.post(f"/pdfpair/runs/{rid}/year", follow_redirects=False,
                       data={CSRF_FIELD: token, "side": "B", "year": "2570", "seen": "1"}).status_code == 303
    r = client.post(f"/pdfpair/runs/{rid}/year",
                    data={CSRF_FIELD: token, "side": "B", "year": "2571", "seen": "1"})
    assert r.status_code == 400 and "ต้องระบุเหตุผล" in r.text


# ── #42 · REVIEW 6359288623: คำนวณซ้ำล้มกลางทาง / กดซ้ำ / ไฟล์เปลี่ยนระหว่างรอบ · ความหมายของ validated ──
def _needs_rerun_run(pid):
    rid = _fresh_run(pid)
    _tamper(rid, B=(None, "not_found"))
    svc.confirm_year(rid, "B", "2570", "หน้าเริ่มหน่วยงาน", True)
    assert svc.view(rid).needs_rerun
    return rid


def _superseded_logs(rid):
    return [e for e in pdfpair_repo.audit_entries(rid) if e["action"] == "pdfpair_run_superseded"]


def test_rerun_failing_midway_never_blocks_old_run(client, web_run, monkeypatch):
    pid = web_run[0]
    old = _needs_rerun_run(pid)
    n = len(pdfpair_repo.list_runs(pid, limit=500))

    def boom(*_a, **_k):
        raise RuntimeError("จำลองล้มระหว่างเทียบ")
    monkeypatch.setattr(cmp, "compare", boom)
    with pytest.raises(RuntimeError):
        svc.rerun(old)
    monkeypatch.undo()
    real_record_in = audit.record_in

    def fail_link(conn, action, *a, **k):          # ล้มตอนบันทึกลิงก์ — หลังบันทึกรอบใหม่ไปแล้วในธุรกรรมเดียวกัน
        if action == "pdfpair_run_superseded":
            raise RuntimeError("จำลองล้มตอนบันทึกลิงก์")
        return real_record_in(conn, action, *a, **k)
    monkeypatch.setattr(audit, "record_in", fail_link)
    with pytest.raises(RuntimeError):
        svc.rerun(old)
    monkeypatch.undo()
    v = svc.view(old)
    assert v.superseded_by == "" and v.needs_rerun and not _superseded_logs(old)
    assert len(pdfpair_repo.list_runs(pid, limit=500)) == n                   # ไม่มีรอบครึ่ง ๆ ค้าง
    assert next(c for c in svc.preflight(old).checks if c.key == "years").action_post
    new = svc.rerun(old)                                                     # ลองใหม่ได้ตามปกติ
    assert svc.view(old).superseded_by == new and len(_superseded_logs(old)) == 1


def test_rerun_double_post_makes_exactly_one_new_run(client, web_run):
    pid, _rid, token = web_run
    old = _needs_rerun_run(pid)
    n = len(pdfpair_repo.list_runs(pid, limit=500))
    r1 = client.post(f"/pdfpair/runs/{old}/rerun", data={CSRF_FIELD: token}, follow_redirects=False)
    r2 = client.post(f"/pdfpair/runs/{old}/rerun", data={CSRF_FIELD: token}, follow_redirects=False)
    new = r1.headers["location"].split("/")[3]
    assert r1.status_code == 303 and r2.status_code == 409 and new in r2.text
    assert len(pdfpair_repo.list_runs(pid, limit=500)) == n + 1 and len(_superseded_logs(old)) == 1


def test_rerun_concurrent_clicks_one_wins_and_loser_is_rolled_back(web_run, monkeypatch):
    import threading
    pid = web_run[0]
    old = _needs_rerun_run(pid)
    n = len(pdfpair_repo.list_runs(pid, limit=500))
    gate, real = threading.Barrier(2, timeout=60), cmp.compare

    def both_past_the_check(*a, **k):              # ทั้งสองคำขอผ่านด่าน "ยังไม่ถูกแทน" ก่อนใครบันทึก
        gate.wait()
        return real(*a, **k)
    monkeypatch.setattr(cmp, "compare", both_past_the_check)
    out = []

    def click():
        try:
            out.append(("ok", svc.rerun(old)))
        except svc.PairError as e:
            out.append(("err", str(e)))
    ts = [threading.Thread(target=click) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(120)
    won = [x for k, x in out if k == "ok"]
    lost = [x for k, x in out if k == "err"]
    assert len(won) == 1 and len(lost) == 1 and won[0] in lost[0]           # คนช้ากว่าได้รหัสรอบที่ชนะ
    assert svc.view(old).superseded_by == won[0] and len(_superseded_logs(old)) == 1
    assert len(pdfpair_repo.list_runs(pid, limit=500)) == n + 1             # รอบของคนช้ากว่าถูก ROLLBACK


def test_file_replaced_while_reading_is_never_saved(web_run, monkeypatch):
    import shutil
    from redbook import config
    from redbook.storage import files as filestore, source_pdfs
    pid = web_run[0]
    old = _needs_rerun_run(pid)
    n = len(pdfpair_repo.list_runs(pid, limit=500))
    path = filestore.path_for(source_pdfs.for_project(pid)["B"]["stored_name"])
    original = path.read_bytes()
    svc._facts_mem.clear()                                    # บังคับอ่านสด (ไม่ใช้ผลที่จำไว้)
    shutil.rmtree(config.DATA_DIR / "cache" / "facts", ignore_errors=True)
    real, swapped = reader.page_words, []

    def swap_after_first_read(p, *a, **k):
        res = real(p, *a, **k)
        if not swapped and Path(p) == path:
            swapped.append(1)
            os.chmod(path, 0o666)
            path.write_bytes(original + b"\n% replaced while reading\n")
        return res
    monkeypatch.setattr(reader, "page_words", swap_after_first_read)
    try:
        with pytest.raises(svc.PairError, match="เปลี่ยนระหว่างที่ระบบอ่าน"):
            svc.rerun(old)
    finally:
        os.chmod(path, 0o666)
        path.write_bytes(original)
        os.chmod(path, 0o444)
    assert swapped and svc.view(old).superseded_by == "" and not _superseded_logs(old)
    assert len(pdfpair_repo.list_runs(pid, limit=500)) == n
    # ไฟล์ที่ต่างจากที่บันทึกตั้งแต่ก่อนอ่าน = ปฏิเสธก่อนอ่าน (ตรวจซ้ำในตัวอ่าน ไม่พึ่งแคช SHA ของหัวรอบ)
    with pytest.raises(svc.PairError, match="เปลี่ยนระหว่างที่ระบบอ่าน"):
        svc._facts(path, AG, "1", "2", expect_sha="0" * 64)


def test_same_size_same_time_replacement_is_not_read_from_the_old_cached_document(books, tmp_path):
    """แคชเอกสารของตัวอ่านคีย์ด้วยเวลาแก้ไข/ขนาด — ไฟล์ที่ถูกแทนด้วยเนื้อใหม่ขนาดเดิมและเวลาเดิม (คัดลอกแบบคงเวลา)
    จะได้เอกสารเก่ากลับมา · ตัวสกัดต้องเห็นจาก SHA ของไบต์ที่เอกสารในแคชเปิดมา และไม่บันทึกผล"""
    import shutil
    from redbook.core.hashing import sha256_file
    p = tmp_path / "same_stat.pdf"
    shutil.copy(books["draft_act"][0], p)
    reader.page_words(p, [1])                                    # เอกสารเข้าแคชของตัวอ่าน
    assert reader.doc_sha(p) == sha256_file(p)
    st = os.stat(p)
    data = bytearray(p.read_bytes())
    nl = data.index(b"\n")                                       # บรรทัดที่สองของ PDF = คอมเมนต์ไบนารี (แก้แล้วยังเป็น PDF ที่ถูกต้อง)
    if data[nl + 1:nl + 2] != b"%" or data[nl + 2] in (10, 13):
        pytest.skip("ไฟล์สังเคราะห์ไม่มีบรรทัดคอมเมนต์ไบนารี")
    data[nl + 2] ^= 0x01
    os.chmod(p, 0o666)
    p.write_bytes(bytes(data))
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert os.stat(p).st_size == st.st_size and os.stat(p).st_mtime_ns == st.st_mtime_ns
    assert reader.doc_sha(p) not in (None, sha256_file(p))      # แคชยังถือเอกสารเก่า — ตัวตรวจต้องเห็นความต่าง
    with pytest.raises(svc.PairError, match="เปลี่ยนระหว่างที่ระบบอ่าน"):
        svc._facts(p, AG, "", "", expect_sha=sha256_file(p))


def test_reader_cache_evicts_beyond_four_and_keeps_sha_per_document(books, tmp_path):
    """เปิดเกิน 4 เล่ม = ตัดเล่มเก่าสุด (ทางนี้เทสต์ปกติไม่ผ่าน) · ทุกเล่มที่ยังอยู่ในแคชจำ SHA ของไบต์ตัวเองถูกต้อง"""
    import shutil
    from redbook.core.hashing import sha256_file
    reader.close_all()
    paths = []
    for i in range(6):
        p = tmp_path / f"evict_{i}.pdf"
        shutil.copy(books["draft_act"][i % 2], p)
        with open(p, "ab") as fh:
            fh.write(f"\n% copy {i}\n".encode())                 # เนื้อไฟล์ต่างกันทุกเล่ม
        reader.page_words(p, [1])
        paths.append(p)
    assert len(reader._open_docs) == reader._OPEN_MAX
    assert [reader.doc_sha(p) for p in paths[:2]] == [None, None]        # สองเล่มแรกถูกตัดออก
    assert all(reader.doc_sha(p) == sha256_file(p) for p in paths[2:])
    reader.close_all()
    assert len(reader._open_docs) == 0


def _copies(books, tmp_path, n, tag):
    import shutil
    out = []
    for i in range(n):
        p = tmp_path / f"{tag}_{i}.pdf"
        shutil.copy(books["draft_act"][i % 2], p)
        with open(p, "ab") as fh:
            fh.write(f"\n% {tag} {i}\n".encode())
        out.append(p)
    return out


def test_eviction_while_another_thread_reads_never_closes_its_document(books, tmp_path, monkeypatch):
    """Bo REVIEW 6409941573 ข้อ 1 — ลำดับสองเธรดแบบกำหนดได้: A ปักเอกสารแล้วหยุดกลางการอ่านหน้า · B เปิดอีก 4 เล่ม
    จนเอกสารของ A ถูกตัดออกจากแคช · เอกสารของ A ต้องยังไม่ถูกปิดจน A อ่านเสร็จ แล้วถูกปิดครั้งเดียว · SHA ที่ A
    บันทึกเป็นของเอกสารที่อ่านจริง (แม้ไม่อยู่ในแคชแล้ว)"""
    import threading
    from redbook.core.hashing import sha256_file
    reader.close_all()
    a, *others = _copies(books, tmp_path, 1 + reader._OPEN_MAX, "race")
    inside, resume = threading.Event(), threading.Event()
    closed, real_close, real_words = [], reader._close, reader.words_from_chars
    monkeypatch.setattr(reader, "_close", lambda d: (closed.append(d), real_close(d)))

    def paused_words(chars, *k):
        if threading.current_thread().name == "A" and not inside.is_set():
            inside.set()
            assert resume.wait(10)                               # A หยุดกลางการอ่าน (ถือเอกสารอยู่)
        return real_words(chars, *k)
    monkeypatch.setattr(reader, "words_from_chars", paused_words)
    out = {}

    def run_a():
        with reader.track_reads() as used:
            out["pts"] = reader.page_words(a, [1, 2])
        out["used"] = used
    t = threading.Thread(target=run_a, name="A")
    t.start()
    assert inside.wait(10)
    doc_a = next(d for d in reader._open_docs.values() if d.refs == 1)
    for p in others:                                             # B: ดันเอกสารของ A ออกจากแคช
        reader.page_words(p, [1])
    assert doc_a.evicted and not doc_a.closed and doc_a not in closed
    assert reader.doc_sha(a) is None                             # ไม่อยู่ในแคชแล้ว
    reader.close_all()                                           # ปิดทั้งหมดก็ปิดเอกสารที่ถูกปักไม่ได้
    assert not doc_a.closed
    resume.set()
    t.join(10)
    assert [pt.page for pt in out["pts"]] == [1, 2] and out["pts"][1].words   # A อ่านครบจากเอกสารที่ยังเปิดอยู่
    assert doc_a.closed and closed.count(doc_a) == 1             # ปิดเมื่อผู้ปักคนสุดท้ายเสร็จ · ครั้งเดียว
    assert out["used"] == {sha256_file(a)}


def test_track_reads_binds_the_sha_to_the_documents_actually_read(books, tmp_path):
    from redbook.core.hashing import sha256_file
    reader.close_all()
    a, b = _copies(books, tmp_path, 2, "track")
    with reader.track_reads() as outer:
        reader.page_words(a, [1])
        with reader.track_reads() as inner:
            reader.page_words(b, [1])
    assert outer == {sha256_file(a), sha256_file(b)} and inner == {sha256_file(b)}
    with reader.track_reads() as none:
        pass
    assert none == set()
    reader.close_all()


def test_shelf_start_refuses_copy_that_differs_from_expected_file(tmp_path, books, monkeypatch):
    # รอบทดลอง: ระบบต้องเทียบกับไฟล์ที่ผู้ตรวจวงไว้ (SHA ที่บันทึกตอนเริ่ม) ไม่ใช่ไฟล์ที่วางแทนบนชั้นภายหลัง
    monkeypatch.setenv(pdfshelf.SHELF_ENV, str(_shelf(tmp_path, books)))
    monkeypatch.setattr(pdfshelf, "toc_scope", lambda v, ag: (scope.Scope(1, 2, scope.METHOD_TOC, ag, ()), [1, 2]))
    from redbook.storage import repository as repo
    n = len(repo.list_projects())
    with pytest.raises(pdfshelf.ShelfError, match="ไม่ใช่ไฟล์เดียวกับที่ใช้ตรวจ"):
        pdfshelf.start("V11_2570_draft", "V11_2570_act", AG, expect_sha={"B": "0" * 64})
    assert len(repo.list_projects()) == n                    # ไม่สร้างงานตรวจค้าง


def test_validated_means_run_conditions_met_and_denominator_is_kept(client, web_run):
    pid = web_run[0]
    rid = _fresh_run(pid)
    _decide_all(rid)
    act = [f for f in svc.view(rid).result.findings if not f.info]
    svc.decide(rid, act[0].id, "not_relevant", "หน้าว่าง")
    svc.decide(rid, act[1].id, "needs_more", "ยังไม่แน่ใจ")
    pf = svc.preflight(rid)
    assert pf.use_status == "review_complete"
    assert sum(pf.use_counts.values()) == pf.actionable == len(act)           # ทุกข้ออยู่ในตัวหาร
    assert (pf.use_counts["excluded"], pf.use_counts["open"]) == (1, 1)
    assert f"ข้อที่ต้องตรวจ {len(act)} ข้อ" in pf.use_breakdown and "ไม่นับ 1" in pf.use_breakdown
    assert "ความแม่นยำ" in svc.USE_STATUS_SCOPE and "ทั้งเอกสาร" in svc.USE_STATUS_SCOPE
    assert "พร้อมใช้อ้างผล" not in " ".join(svc.USE_STATUS_LABELS.values())
    assert svc.USE_STATUS_LABELS["validated"].startswith("ผ่านเงื่อนไขการใช้ผล")
    svc.export_csv_checked(rid)
    d = json.loads([e for e in pdfpair_repo.audit_entries(rid)
                    if e["action"] == "pdfpair_exported"][-1]["detail_json"])
    assert d["use_counts"] == pf.use_counts and d["actionable"] == len(act)
    for page in ("preflight", "export"):
        html = client.get(f"/pdfpair/runs/{rid}/{page}").text
        assert svc.USE_STATUS_SCOPE in html and pf.use_breakdown in html
    audit_html = client.get(f"/pdfpair/runs/{rid}/audit").text
    assert pf.use_breakdown in audit_html


# ── #42 · REVIEW 6351061023: ธงลูกในผลรวม · collision · ช่องว่าง · rounding ──────────────
def _plan_book(kids, parent_raw="12.0000", parent_flags=None):
    """แผนงาน 1 แผน + ผลผลิตลูก (ป้าย, ค่า, ธง) ในตารางสรุป คอลัมน์ "รวม" """
    bf = ex.BookFacts("v", "p", 2570, "draft", "x")
    plan = ex.node_key(P.LEVEL_PLAN, "แผนงานพื้นฐาน")
    bf.nodes[plan] = ex.Node(plan, P.LEVEL_PLAN, "แผนงานพื้นฐาน", "", 0, _E)
    bf.amounts.append(_a(P.SEC_SUMMARY, plan, P.COL_TOTAL, parent_raw, unit_origin="table_decl",
                         flags=list(parent_flags or [])))
    for i, (label, raw, flags) in enumerate(kids):
        k = ex.node_key(P.LEVEL_OUTPUT, label)
        bf.nodes[k] = ex.Node(k, P.LEVEL_OUTPUT, label, plan, i + 1, _E)
        bf.amounts.append(_a(P.SEC_SUMMARY, k, P.COL_TOTAL, raw, flags=list(flags)))
    return bf


def test_sum_finding_carries_child_flags_and_parts(client, web_run, monkeypatch):
    bf = _plan_book([("ผลผลิต : บริการ", "5.0000", ["unit_not_in_document"]),
                     ("ผลผลิต : วิจัย", "6.0000", ["column_nearest"])])          # แม่ 12 ≠ 11
    f = next(x for x in cmp.compare(bf, bf).findings if x.kind == cmp.K_SUM and x.within == "A")
    assert not f.a.flags                                       # ยอดแม่ชัด…
    assert len(f.parts) == 2 and {p["value"] for p in f.parts} == {"5.0000", "6.0000"}
    assert all(p["page"] == 1 and p["bbox"] for p in f.parts)  # ชี้องค์ประกอบได้
    assert any("องค์ประกอบของผลรวม 1 ค่า" in c and "ไม่ได้มาจากเอกสาร" in c for c in f.caveats)
    assert any("นอกแนวหัวคอลัมน์" in c and "วิจัย" in c for c in f.caveats)   # …แต่ลูกมีธง = ต้องยืนยัน
    assert "ส่วนต่าง" in f.note and "เกณฑ์ปัดเศษ ±" in f.note and Decimal(f.tolerance) == Decimal("0.00015")
    # CSV + หน้าเว็บ + preflight เห็นคำเตือนเดียวกัน
    rid = web_run[1]
    real_view = svc.view

    def fake(r):
        v = real_view(r)
        v.result.findings.append(f)
        return v
    monkeypatch.setattr(svc, "view", fake)
    rows = list(_csv.reader(_io.StringIO(svc.export_csv(rid).lstrip("﻿"))))
    head, row = rows[0], next(x for x in rows if x[0] == f.id)
    assert "องค์ประกอบของผลรวม" in row[head.index("ต้องให้คนยืนยัน")]
    assert "5.0000" in row[head.index("องค์ประกอบที่ใช้คำนวณ")] and row[head.index("เกณฑ์ปัดเศษ")].startswith("±")
    html = client.get(f"/pdfpair/runs/{rid}/f/{f.id}").text
    assert "องค์ประกอบที่ใช้คำนวณ 2 ค่า" in html and "ต้องให้คนยืนยันก่อนใช้" in html


def test_sum_within_rounding_is_not_reported_as_exact_and_strict_rules_stay_strict():
    assert "≠ ตรงเป๊ะ" in cmp.ROUNDING_POLICY
    ok = _plan_book([("ผลผลิต : ก", "5.0000", []), ("ผลผลิต : ข", "7.00004", [])])     # ส่วนต่าง < เกณฑ์
    assert not [x for x in cmp.compare(ok, ok).findings if x.kind == cmp.K_SUM]
    # ค่าบาทจำนวนเต็ม (ผลรวมรายการผูกพัน) = เกณฑ์ 0 — ส่วนต่าง 1 บาทต้องขึ้น และบอกว่าเป็นกฎเคร่งครัด
    bf = ex.BookFacts("v", "p", 2570, "draft", "x")
    bf.commitments = [ex.Commitment("c", "", "อาคาร", total="1001", years={"2570": "500"},
                                    future={"2571": "500"}, ev=_E)]
    f = next(x for x in cmp.compare(bf, bf).findings if x.kind == cmp.K_SUM and x.within == "A")
    assert "กฎเคร่งครัด (เกณฑ์ 0)" in f.note and f.delta == "1"


def test_rounding_tolerance_is_a_declared_assumption_and_baht_tables_stay_strict():
    # REVIEW 6360210542: เกณฑ์ปัดเศษต้องบอกเงื่อนไขที่ใช้ — เอกสารไม่ได้ระบุวิธีปัด จึงเป็นสมมติฐานของกฎ
    assert "สมมติฐานของกฎ" in cmp.ROUNDING_POLICY and "≠ ตรงเป๊ะ" in cmp.ROUNDING_POLICY
    assert "**" not in cmp.ROUNDING_POLICY and "**" not in svc.USE_STATUS_SCOPE    # ข้อความแสดงบนหน้าเว็บ/CSV ตรง ๆ
    assert _a("summary", "n", "รวม", "4", "บาท").rounding_tolerance == 0          # บาท = ไม่ได้ปัด
    assert _a("summary", "n", "รวม", "4.0000").rounding_tolerance == Decimal("0.00005")
    # ตารางหน่วยบาท: 1 + 2 ↔ 4 คลาด 1 บาท ต้องขึ้น (เดิม 0.5 ต่อค่า × 3 ค่า = 1.5 บาท กลบไว้)
    bf = ex.BookFacts("v", "p", 2570, "draft", "x")
    c1, c2 = P.CATEGORIES[0], P.CATEGORIES[1]
    bf.amounts = [_a(P.SEC_SUMMARY, "total", c1, "1", "บาท"), _a(P.SEC_SUMMARY, "total", c2, "2", "บาท"),
                  _a(P.SEC_SUMMARY, "total", P.COL_TOTAL, "4", "บาท")]
    fs = [f for f in cmp.compare(bf, bf).findings if f.kind == cmp.K_SUM and f.within == "A"]
    assert len(fs) == 1 and fs[0].tolerance_basis == "strict" and Decimal(fs[0].tolerance) == 0
    # ตารางล้านบาท: เกณฑ์มาจากสมมติฐาน — บอกที่มาในหมายเหตุ · CSV/หน้าเว็บ (tolerance_text)
    m = _sum_book(("1.2000", "1.3000", "2.6000"))[0]
    assert m.tolerance_basis == "assumed_independent_rounding" and "สมมติฐานของกฎ" in m.note
    assert svc.tolerance_text(m).startswith("±") and "สมมติฐานของกฎ" in svc.tolerance_text(m)


def _collision_book(order):
    """สองผลผลิตชื่อต่างที่สระ/วรรณยุกต์ (โครงคำเดียวกัน) มีเงินทั้งคู่ — สลับลำดับได้"""
    plan = _rec("p", P.LEVEL_PLAN, "แผนงานพื้นฐาน")
    o = {"เช่า": _rec("o1", P.LEVEL_OUTPUT, "ผลผลิต : ค่าเช่าอาคาร", "p"),
         "เช้า": _rec("o2", P.LEVEL_OUTPUT, "ผลผลิต : ค่าเช้าอาคาร", "p")}
    money = {"o1": "5.0000", "o2": "7.0000"}
    recs = [plan] + [o[x] for x in order]
    km, issues = ex.resolve_node_keys(recs)
    bf = ex.BookFacts("v", "p", 2570, "draft", "x")
    bf.identity_issues = issues
    for r in recs:
        k = km[r["key"]]
        bf.nodes.setdefault(k, ex.Node(k, r["level"], r["label"], km.get(r["parent"], ""), 0, _E))
    bf.amounts = [_a(P.SEC_SUMMARY, km["p"], P.COL_TOTAL, "12.0000", unit_origin="table_decl")]
    for t in [o[x]["key"] for x in order]:
        bf.amounts.append(_a(P.SEC_SUMMARY, km[t], P.COL_TOTAL, money[t], unit_origin="table_decl"))
    ex.mark_identity(bf)
    return bf, km


@pytest.mark.parametrize("order", [("เช่า", "เช้า"), ("เช้า", "เช่า")])
def test_skeleton_collision_keeps_every_occurrence_and_blocks_inferred_use(order):
    bf, km = _collision_book(order)
    assert km["o1"] == km["o2"]                              # ระบบแยกไม่ได้ด้วยโครงคำ
    # อนุรักษ์: ทั้งสองค่ายังอยู่ ไม่หายเงียบ และมองเห็นเป็นปัญหาระบุตัว
    vals = sorted(a.value for a in bf.amounts if a.node == km["o1"])
    assert vals == ["5.0000", "7.0000"]
    kinds = {x["kind"] for x in bf.identity_issues}
    assert {"skeleton_merge", "duplicate_cell"} <= kinds
    sk = next(x for x in bf.identity_issues if x["kind"] == "skeleton_merge")
    assert len(sk["occurrences"]) == 2
    dup = next(x for x in bf.identity_issues if x["kind"] == "duplicate_cell")
    assert any("5.0000" in s for s in dup["labels"]) and any("7.0000" in s for s in dup["labels"])
    assert all("identity_collision" in a.flags for a in bf.amounts if a.node == km["o1"])
    # ผลที่พึ่งพา collision (ผลรวมของแผนงาน · เทียบข้ามเล่ม) ต้องติดคำเตือน — ใช้สรุปไม่ได้จนคนยืนยัน
    other, _ = _collision_book(tuple(reversed(order)))
    res = cmp.compare(bf, other)
    ident = [f for f in res.findings if f.kind == cmp.K_IDENTITY]
    assert len(ident) >= 4 and all(not f.info for f in ident)
    dep = [f for f in res.findings if f.parts and any(p["flags"] for p in f.parts)]
    dep += [f for f in res.findings if "identity_collision" in f.a.flags + f.b.flags]
    assert all(f.caveats for f in dep)
    bf_sum = [f for f in cmp.compare(bf, bf).findings if f.kind == cmp.K_SUM]
    assert all(any("ระบุตัวไม่แน่ชัด" in c for c in f.caveats) for f in bf_sum)


def test_same_values_in_repeated_tables_are_not_a_collision():
    bf = _plan_book([("ผลผลิต : บริการ", "5.0000", []), ("ผลผลิต : วิจัย", "7.0000", [])])
    k = ex.node_key(P.LEVEL_OUTPUT, "ผลผลิต : บริการ")
    bf.amounts.append(_a(P.SEC_SUMMARY, k, P.COL_TOTAL, "5.0000"))      # ค่าเดิมพบซ้ำ = ไม่ใช่ปัญหา
    ex.mark_identity(bf)
    assert not bf.identity_issues and not any(a.flags for a in bf.amounts)


def test_blank_cell_is_distinct_from_no_record_and_from_zero():
    a = ex.BookFacts("v", "p", 2570, "draft", "x")
    b = ex.BookFacts("v", "p", 2570, "act", "x")
    k = ex.node_key(P.LEVEL_OUTPUT, "ผลผลิต : บริการ")
    for bf in (a, b):
        bf.nodes[k] = ex.Node(k, P.LEVEL_OUTPUT, "ผลผลิต : บริการ", "", 1, _E)
    c1, c2, c3 = P.CATEGORIES[:3]
    a.amounts = [_a(P.SEC_SUMMARY, k, c1, "1.0000"), _a(P.SEC_SUMMARY, k, c2, "2.0000"),
                 _a(P.SEC_SUMMARY, k, c3, "0.0000")]
    b.amounts = [_a(P.SEC_SUMMARY, k, c1, "1.0000")]
    b.blanks = [_a(P.SEC_SUMMARY, k, c2, "", status="blank")]       # แถวมี แต่ช่อง c2 ว่าง · c3 ไม่มีระเบียน
    fs = {f.column: f for f in cmp.compare(a, b).findings if f.topic == cmp.T_TOTAL}
    blank, missing = fs[c2], fs[c3]
    assert blank.kind == cmp.K_BLANK_VS_VALUE and blank.b.status == "blank" and blank.b.page == 1
    assert "ไม่ได้แปลว่าเป็นศูนย์" in blank.note and svc.amount_text(blank.b).startswith("ช่องว่าง")
    assert missing.kind == cmp.K_ONLY_A and missing.b.status == "" and missing.a.value == "0.0000"
    # บันทึก/โหลดกลับ: ช่องว่างไม่หาย · รอบเก่าที่ไม่มีฟิลด์ blanks โหลดได้
    assert ex.BookFacts.from_dict(b.to_dict()).blanks[0].status == "blank"
    d = b.to_dict()
    d.pop("blanks")
    assert ex.BookFacts.from_dict(d).blanks == []


def test_extract_records_blank_cells_in_table_rows():
    from redbook.pdfbook.layout import Cell, Column, Row
    st = ex._State()
    st.section, st.table_kind = P.SEC_SUMMARY, "amounts"
    st.cols = [Column(P.CATEGORIES[0], 300, 340), Column(P.CATEGORIES[1], 360, 400)]
    bf = ex.BookFacts("v", "p", 2570, "draft", "x")
    r = Row(1, "ผลผลิต : บริการ 1.0000", "ผลผลิต : บริการ",
            (Cell("1.0000", Decimal("1.0000"), 310, 70, 335, 80),), (), 60, 70, 335, 80, 60)
    pending: list = []

    def add_node(level, label, row, parent=""):
        rec = {"level": level, "label": label, "parent": parent, "ev": ex._ev(row), "key": f"tmp{len(pending)}"}
        pending.append(rec)
        return rec
    ex._table_row(r, st, bf, add_node, [])
    assert [m.column for m in bf.amounts] == [P.CATEGORIES[0]]
    assert [(m.column, m.status, m.value) for m in bf.blanks] == [(P.CATEGORIES[1], "blank", "")]


def test_offbudget_same_name_under_different_headings_kept_apart():
    st = ex._State()
    keys = [ex._off_key(st, label) for label in ("6.1 ภารกิจพื้นฐาน", "6.1.1 รายจ่ายประจำ",
                                                 "6.2 ภารกิจเพื่อการพัฒนา", "6.2.1 รายจ่ายประจำ", "7. คงเหลือ")]
    assert keys[1] != keys[3] and keys[1] == "off:ภารกิจพื้นฐาน › รายจ่ายประจำ"
    assert keys[3] == "off:ภารกิจเพื่อการพัฒนา › รายจ่ายประจำ"
    assert keys[0] == "off:ภารกิจพื้นฐาน" and keys[4] == "off:คงเหลือ"      # ชั้น 1–2 คงกุญแจเดิม


# ── #42 · REVIEW 6342471856: ขอบเขตคำบอกปี · หลักฐานต่อ candidate · negative controls ─────────
FWD_PAGE = "ประมาณการรายจ่ายล่วงหน้าระยะปานกลาง\nตารางที่ 3"
CMP_PAGE = "ข้อมูลเปรียบเทียบ\nปีงบประมาณ พ.ศ. 2568 - 2570"


@pytest.mark.parametrize("texts", [
    [FWD_PAGE, CMP_PAGE],                                 # หน้าประมาณการมาก่อนหน้าเปรียบเทียบ
    [CMP_PAGE, FWD_PAGE],                                 # สลับลำดับหน้า
    ["ประมาณการรายจ่ายล่วงหน้า\n\n" + CMP_PAGE],            # คำบอกอยู่คนละหัวข้อ (มีบรรทัดอื่นคั่น)
])
def test_forward_cue_does_not_leak_across_pages_or_sections(texts):
    y = ex.detect_year(texts, 0)
    assert (y.year, y.origin, y.status) == (2570, "comparison_range", "ok")
    assert [e["kind"] for e in y.evidence] == ["comparison"]


def test_forward_cue_on_wrapped_heading_line_still_counts():
    y = ex.detect_year(["ประมาณการรายจ่ายล่วงหน้า\nปีงบประมาณ พ.ศ. 2571 - 2573"], 0)
    assert (y.year, y.origin, y.status) == (2570, "forward_range", "uncertain")


def test_cue_after_the_year_or_in_another_clause_is_ignored():
    # คำบอกที่อยู่ "หลัง" ปี ไม่นับ · คำบอกของช่วงก่อนหน้าในบรรทัดเดียวกันไม่ไหลมาช่วงถัดไป
    y = ex.detect_year(["ปีงบประมาณ พ.ศ. 2568 - 2570 (ไม่ใช่ประมาณการ)"], 0)
    assert (y.year, y.origin) == (2570, "comparison_range")
    y = ex.detect_year(["ประมาณการล่วงหน้า ปีงบประมาณ 2571 - 2573 และเปรียบเทียบ ปีงบประมาณ 2568 - 2570"], 0)
    kinds = {(e["year"], e["kind"]) for e in y.evidence}
    assert kinds == {(2571, "forward"), (2568, "comparison")} and y.year == 2570


def test_year_evidence_per_candidate_direct_vs_inferred():
    y = ex.detect_year(["หน้าปก", "งบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. 2570",
                        "ประมาณการรายจ่ายล่วงหน้า ปีงบประมาณ พ.ศ. 2571 - 2573\nผลการดำเนินงานของปีงบประมาณ 2569"], 0)
    by = {e["kind"]: e for e in y.evidence}
    assert by["stated"]["page"] == 2 and by["stated"]["direct"] and by["stated"]["cue"].endswith("ประจำ")
    assert by["forward"]["page"] == 3 and not by["forward"]["direct"] and "ล่วงหน้า" in by["forward"]["cue"]
    assert by["mention"]["year"] == 2569 and not by["mention"]["direct"]
    assert all(e["line"] for e in y.evidence)
    bf = ex.BookFacts("v", "p", 2570, "", "x")
    bf.year_evidence = [dict(e, bbox=[1, 2, 3, 4]) for e in y.evidence]
    assert ex.BookFacts.from_dict(bf.to_dict()).year_evidence == bf.year_evidence


@pytest.mark.parametrize("line", ["ประจำปีงบประมาณ พ.ศ. ๒๕๗๐",                  # เลขไทย
                                  "ข้อมูล ปีงบประมาณ พ.ศ. 2568 – 2570",            # ขีด en
                                  "ข้อมูล ปีงบประมาณ พ.ศ. ๒๕๖๘ — ๒๕๗๐"])           # เลขไทย + ขีด em
def test_year_thai_digits_and_long_dashes(line):
    y = ex.detect_year([line], 0)
    assert y.year == 2570 and y.status == "ok"


def test_year_evidence_located_on_page(books):
    path = books["draft_act"][0]
    fa = svc._facts(path, AG, "", "")[0]
    assert fa.year_evidence and all(e["bbox"] for e in fa.year_evidence if e["kind"] in ("stated", "comparison"))


# negative controls ของตัวจัดอักขระ (ช่องว่าง 0 pt ที่ไม่ใช่นิคหิต · เครื่องหมายข้ามคำ · ตัวเลข)
def _word_texts(spec):
    """spec = [(ข้อความ, กว้าง)] ต่อกันในบรรทัดเดียว — กว้าง 0 = เครื่องหมาย/ช่องว่าง 0 pt"""
    chars, x = [], 100.0
    for t, w in spec:
        chars.append(_ch(t, x, x + w))
        x += w
    return [w.text for w in reader.words_from_chars(chars)]


def test_zero_width_space_before_sara_aa_is_nikhahit():
    assert _word_texts([("ท", 4), (" ", 0), ("า", 4)]) == ["ท" + reader.NIKHAHIT + "า"]


@pytest.mark.parametrize("spec, want", [
    ([("ก", 4), (" ", 0), ("ข", 4)], ["ก", "ข"]),                    # ระหว่างพยัญชนะ — ไม่ใช่นิคหิต
    ([("ก", 4), (" ", 0), ("1", 4)], ["ก", "1"]),                    # ก่อนตัวเลข
    ([("1", 4), (" ", 0), ("2", 4)], ["1", "2"]),                    # ระหว่างตัวเลข
    ([("ก", 4), (" ", 0.8), ("า", 4)], ["ก", "า"]),                  # กว้างเกินเกณฑ์ = ช่องว่างจริง
])
def test_zero_width_space_negative_controls(spec, want):
    assert _word_texts(spec) == want and not any(reader.NIKHAHIT in w for w in _word_texts(spec))


def test_marks_do_not_jump_to_another_line_or_word():
    chars = [_ch("ก", 100, 104, top=100.0), _ch("่", 103.7, 103.7, top=130.0), _ch("ข", 110, 114, top=130.0)]
    ws = {w.text for w in reader.words_from_chars(chars)}
    assert "ก" in ws and "ก่" not in ws                   # เครื่องหมายบรรทัดถัดไปไม่เกาะคำบรรทัดบน
    chars = [_ch("ก", 100, 104), _ch(" ", 104, 108), _ch("้", 107.7, 107.7), _ch("ข", 108, 112)]
    ws = [w.text for w in reader.words_from_chars(chars)]
    assert ws[0] == "ก"                                   # หลังช่องว่างจริง เครื่องหมายไม่ย้อนไปคำก่อน


def test_year_ignores_text_hidden_off_the_page():
    from redbook.evidence.pdftext import PageText, Word
    seen = [Word(t, x, 100, x + 30, 112, 0, 0) for t, x in (("ปีงบประมาณ", 60), ("พ.ศ.", 95), ("2568", 130),
                                                                ("-", 165), ("2570", 175))]
    hidden = [Word(t, x, 300, x + 30, 312, 0, 1) for t, x in (("ประจำปีงบประมาณ", 700), ("พ.ศ.", 740), ("2569", 775))]
    pt = PageText(1, 595, 842, tuple(seen + hidden), ())
    assert "2569" not in ex.visible_text(pt) and "2570" in ex.visible_text(pt)
    y = ex.detect_year([ex.visible_text(pt)], 0)
    assert (y.year, y.status) == (2570, "ok")                    # ถ้านับข้อความซ่อน = ขัดกัน (2569 vs 2570)
    raw = ex.detect_year(["ปีงบประมาณ พ.ศ. 2568 - 2570\nประจำปีงบประมาณ พ.ศ. 2569"], 0)
    assert raw.status == "conflict"


# ── #42 · REVIEW 6360210542: ธงขององค์ประกอบถึงทุกกฎผลรวม/ผูกพัน/ข้ามตาราง (ตารางความครอบคลุม) ─────────
_PLAN_K = ex.node_key(P.LEVEL_PLAN, "แผนงานพื้นฐาน")
_O1 = ex.node_key(P.LEVEL_OUTPUT, "ผลผลิต : บริการ")
_O2 = ex.node_key(P.LEVEL_OUTPUT, "ผลผลิต : วิจัย")


def _bk(amounts=(), items=(), commitments=()):
    bf = ex.BookFacts("v", "p", 2570, "draft", "x")
    bf.nodes[_PLAN_K] = ex.Node(_PLAN_K, P.LEVEL_PLAN, "แผนงานพื้นฐาน", "", 0, _E)
    bf.nodes[_O1] = ex.Node(_O1, P.LEVEL_OUTPUT, "ผลผลิต : บริการ", _PLAN_K, 1, _E)
    bf.nodes[_O2] = ex.Node(_O2, P.LEVEL_OUTPUT, "ผลผลิต : วิจัย", _PLAN_K, 2, _E)
    bf.amounts, bf.items, bf.commitments = list(amounts), list(items), list(commitments)
    ex.mark_identity(bf)
    return bf


def _cm(total, years, future=None, fund=None, assumed=()):
    """รายการผูกพันพร้อมบรรทัดหลักฐานต่อค่า · ``assumed`` = กุญแจบรรทัดที่ไม่มีคำหน่วย (สมมติบาท)"""
    c = ex.Commitment(key="งบลงทุน|อาคาร", node=_O1, label="อาคาร 1 หลัง", total=total, years=dict(years),
                      future=dict(future or {}), ev=_E, parts=dict(fund or {}))
    keys = ["total"] + [f"year:{y}" for y in c.years] + [f"future:{y}" for y in c.future] \
        + [f"fund:{k}" for k in c.parts]
    for i, k in enumerate(keys):
        c.lines.append(ex.Evidence(1, (0.0, 20.0 + 12 * i, 10.0, 30.0 + 12 * i), k))
        c.line_keys.append(k)
        c.line_units.append("assumed" if k in assumed else "row")
    return c


def _it(label, amount, flags):
    return ex.Item(key=f"{P.CATEGORIES[1]}|{label}", node=_O1, category=P.CATEGORIES[1], label=label,
                   amount=amount, not_proposed=False, order=1, ev=_E,
                   unit_origin="assumed" if flags else "row", flags=list(flags))


_T = dict(unit_origin="table_decl")
#: กฎภายในเล่มทุกข้อของ ``compare._internal`` → (เล่มที่องค์ประกอบหนึ่งค่ามีธง ``fl``, ชนิดข้อสังเกต, ป้ายองค์ประกอบที่มีธง)
COVERAGE = {
    "1 หมวดงบในแถว = รวม": lambda fl: (_bk([
        _a(P.SEC_SUMMARY, "total", P.CATEGORIES[0], "1.0000", **_T),
        _a(P.SEC_SUMMARY, "total", P.CATEGORIES[1], "2.0000", flags=fl, **_T),
        _a(P.SEC_SUMMARY, "total", P.COL_TOTAL, "4.0000", **_T)]), cmp.K_SUM, P.CATEGORIES[1]),
    "2 ลูกรวม = แม่ · ตารางสรุป": lambda fl: (_bk([
        _a(P.SEC_SUMMARY, _PLAN_K, P.COL_TOTAL, "12.0000", **_T),
        _a(P.SEC_SUMMARY, _O1, P.COL_TOTAL, "5.0000", flags=fl, **_T),
        _a(P.SEC_SUMMARY, _O2, P.COL_TOTAL, "6.0000", **_T)]), cmp.K_SUM, "บริการ"),
    "2 ลูกรวม = แม่ · ประจำ/ลงทุน": lambda fl: (_bk([
        _a(P.SEC_ECON, _PLAN_K, P.ECON_COLUMNS[0], "12.0000", **_T),
        _a(P.SEC_ECON, _O1, P.ECON_COLUMNS[0], "5.0000", flags=fl, **_T),
        _a(P.SEC_ECON, _O2, P.ECON_COLUMNS[0], "6.0000", **_T)]), cmp.K_SUM, "บริการ"),
    "2 ลูกรวม = แม่ · ประมาณการ": lambda fl: (_bk([
        _a(P.SEC_MTEF, _PLAN_K, "2571", "12.0000", **_T),
        _a(P.SEC_MTEF, _O1, "2571", "5.0000", flags=fl, **_T),
        _a(P.SEC_MTEF, _O2, "2571", "6.0000", **_T)]), cmp.K_SUM, "บริการ"),
    "3 ประจำ + ลงทุน = รวม": lambda fl: (_bk([
        _a(P.SEC_ECON, "total", P.ECON_COLUMNS[0], "1.0000", **_T),
        _a(P.SEC_ECON, "total", P.ECON_COLUMNS[1], "2.0000", flags=fl, **_T),
        _a(P.SEC_ECON, "total", P.COL_TOTAL, "4.0000", **_T)]), cmp.K_SUM, P.ECON_COLUMNS[1]),
    "4 ข้ามตาราง: สรุป ↔ ประจำ/ลงทุน": lambda fl: (_bk([
        _a(P.SEC_SUMMARY, "total", P.COL_TOTAL, "10.0000", **_T),
        _a(P.SEC_ECON, "total", P.COL_TOTAL, "9.0000", flags=fl, **_T)]), cmp.K_CROSS_TABLE, "ประจำ/ลงทุน"),
    "5 รายละเอียด ↔ ตารางสรุป": lambda fl: (_bk([
        _a(P.SEC_SUMMARY, _O1, P.CATEGORIES[1], "4.0000", **_T),
        _a(P.SEC_DETAIL, _O1, P.CATEGORIES[1], "5,000,000", "บาท", flags=fl, unit_origin="row")]),
        cmp.K_CROSS_TABLE, "รายละเอียด"),
    "6 ยอดหมวด = ผลรวมรายการที่พิมพ์": lambda fl: (_bk(
        [_a(P.SEC_DETAIL, _O1, P.CATEGORIES[1], "10,000,000", "บาท", unit_origin="row")],
        items=[_it("ค่าตอบแทน", "4000000", fl), _it("ค่าใช้สอย", "5000000", [])]), cmp.K_SUM, "ค่าตอบแทน"),
    "7 ผูกพัน: วงเงินทั้งสิ้น = ผลรวมรายปี": lambda fl: (_bk(commitments=[_cm(
        "80000000", {"2569": "15000000", "2570": "25000000"}, {"2571": "30000000"},
        assumed=("year:2570",) if fl else ())]), cmp.K_SUM, "ปี 2570 ตั้งงบประมาณ"),
    "7 ผูกพัน: วงเงินทั้งสิ้น = แหล่งเงิน": lambda fl: (_bk(commitments=[_cm(
        "80000000", {"2569": "30000000", "2570": "40000000"},
        fund={P.FUND_BUDGET: "70000000", P.FUND_OFFBUDGET: "5000000"},
        assumed=(f"fund:{P.FUND_OFFBUDGET}",) if fl else ())]), cmp.K_SUM, P.FUND_OFFBUDGET),
    "7 ผูกพัน: เงินงบประมาณ = ผลรวมรายปี": lambda fl: (_bk(commitments=[_cm(
        "80000000", {"2569": "30000000", "2570": "40000000"}, fund={P.FUND_BUDGET: "80000000"},
        assumed=("year:2569",) if fl else ())]), cmp.K_SUM, "ปี 2569 ตั้งงบประมาณ"),
}


@pytest.mark.parametrize("rule", list(COVERAGE))
def test_component_flag_reaches_every_internal_rule(rule):
    bf, kind, flagged = COVERAGE[rule](["unit_not_in_document"])
    fs = [f for f in cmp.compare(bf, bf).findings if f.within == "A" and f.kind == kind]
    assert len(fs) == 1, [(f.kind, f.column) for f in cmp.compare(bf, bf).findings if f.within == "A"]
    f = fs[0]
    assert f.parts and all(p.get("page") for p in f.parts)                     # ชี้องค์ประกอบได้ทุกค่า
    hit = [p for p in f.parts if flagged in p["label"]]
    assert hit and all("unit_not_in_document" in p["flags"] for p in hit)
    assert any(cmp.CAVEAT_LABELS["unit_not_in_document"] in c for c in f.caveats)
    # ตัวควบคุม: องค์ประกอบเดียวกันไม่มีธง = ไม่มีคำเตือน (คำเตือนมาจากธงจริง ไม่ได้ติดทุกข้อ)
    bf0, _k, _l = COVERAGE[rule]([])
    f0 = [x for x in cmp.compare(bf0, bf0).findings if x.within == "A" and x.kind == kind]
    assert len(f0) == 1 and f0[0].caveats == []


def test_identity_flags_reach_every_record_hanging_off_the_node():
    """รายการแม่ระบุตัวไม่ได้ → ข้อเทียบสองฉบับของรายการ · รายการผูกพัน · ตัวชี้วัด · ข้อความ · โครงสร้าง ติดคำเตือน"""
    def book(amount, total, target, text, extra_node=False):
        bf = _bk(items=[_it("ค่าตอบแทน", amount, [])], commitments=[_cm(total, {"2570": total})])
        bf.indicators = [ex.Indicator("ร้อยละผู้ใช้บริการ", _O1, "ร้อยละผู้ใช้บริการ", "ร้อยละ", {"2570": target},
                                      1, _E)]
        bf.texts = [ex.TextItem("objective", _O1, "", text, 1, _E)]
        if extra_node:
            k = ex.node_key(P.LEVEL_ACTIVITY, "กิจกรรม : สนับสนุน")
            bf.nodes[k] = ex.Node(k, P.LEVEL_ACTIVITY, "กิจกรรม : สนับสนุน", _O1, 3, _E)
            bf.identity_issues.append({"kind": "parent_unidentified", "key": k, "ev": _E, "labels": ["x"],
                                       "candidates": [], "note": ex.INHERITED_NOTES["parent_unidentified"]})
        return bf
    a = book("4000000", "10000000", "80", "เพื่อให้บริการประชาชน", extra_node=True)
    a.identity_issues.append({"kind": "parent_unidentified", "key": _O1, "ev": _E, "labels": ["ผลผลิต : บริการ"],
                              "candidates": [], "note": ex.INHERITED_NOTES["parent_unidentified"]})
    ex.mark_identity(a)
    b = book("4500000", "12000000", "85", "เพื่อให้บริการประชาชนอย่างทั่วถึง")
    fs = cmp.compare(a, b).findings
    label = cmp.CAVEAT_LABELS["identity_ambiguous"]
    for topic in (cmp.T_ITEMS, cmp.T_COMMIT, cmp.T_IND, cmp.T_TEXT, cmp.T_STRUCT):
        got = [f for f in fs if f.topic == topic and f.kind != cmp.K_IDENTITY and not f.within]
        assert got and all(label in f.caveats for f in got), topic
    # ปัญหาที่สืบทอดจากแม่ไม่ทำข้อแยก (ต้นเหตุมีข้อของตัวเอง) แต่ค่าที่ผูกกับรายการนั้นติดธง
    assert not [f for f in fs if f.kind == cmp.K_IDENTITY]
    assert all("identity_ambiguous" in i.flags for i in a.items)
    assert [f for f in cmp.compare(b, b).findings if f.caveats] == []


def test_inherited_identity_problem_flows_down_from_unidentified_parent():
    recs = _NESTED + [_rec("o9", P.LEVEL_OUTPUT, "ผลผลิต : บริการวิชาการ"),
                      _rec("k9", P.LEVEL_ACTIVITY, "กิจกรรม : ประชาสัมพันธ์", "o9")]     # ชื่อลูกไม่ซ้ำที่อื่น
    km, issues = ex.resolve_node_keys(recs)
    inh = [i for i in issues if i["kind"] == "parent_unidentified"]
    assert [i["key"] for i in inh] == [km["k9"]]                 # ไม่ได้แยกกุญแจ แต่ติดปัญหาสืบทอด
    assert km == ex.resolve_node_keys(list(reversed(recs)))[0]
    coll = [_rec("p1", P.LEVEL_PLAN, "แผนงาน ก"), _rec("x1", P.LEVEL_OUTPUT, "ผลผลิต : ค่าเช่าอาคาร", "p1"),
            _rec("x2", P.LEVEL_OUTPUT, "ผลผลิต : ค่าเช้าอาคาร", "p1"), _rec("c1", P.LEVEL_ACTIVITY, "กิจกรรม : ดูแล", "x2")]
    _km, issues = ex.resolve_node_keys(coll)
    assert {i["kind"] for i in issues} == {"skeleton_merge", "parent_collision"}


# ── #42 · REVIEW 6360210542: ขั้นเอกสารจากบรรทัดชื่อเอกสารที่มองเห็น · ปีที่ใช้คำนวณ = ปีจากหลักฐานที่แสดง ──
def test_stage_only_from_title_lines_and_conflict_is_not_resolved():
    act = ex.detect_stage(["เอกสารงบประมาณ ฉบับปรับปรุงตามพระราชบัญญัติงบประมาณรายจ่าย ประจำปีงบประมาณ พ.ศ. 2570"], 0)
    assert (act.stage, act.status) == ("act", "ok") and act.evidence[0]["page"] == 1
    draft = ex.detect_stage(["ร่างพระราชบัญญัติงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. 2570"], 0)
    assert (draft.stage, draft.status) == ("draft", "ok")       # คำบอก พ.ร.บ. ที่อยู่ในวลีร่าง ไม่นับเป็นฉบับ พ.ร.บ.
    body = ex.detect_stage(["งบประมาณรายจ่าย ประจำปีงบประมาณ พ.ศ. 2570\nจัดตั้งตามพระราชบัญญัติองค์การมหาชน"], 0)
    assert (body.stage, body.status) == ("", "not_found")       # คำบอกในเนื้อหา ไม่ใช่บรรทัดชื่อเอกสาร
    both = ex.detect_stage(["ร่างพระราชบัญญัติงบประมาณรายจ่าย", "", "ฉบับปรับปรุงตามพระราชบัญญัติงบประมาณรายจ่าย"], 0)
    assert (both.stage, both.status) == ("", "conflict") and len(both.evidence) == 2


def test_year_and_stage_used_come_from_the_visible_evidence(books, monkeypatch):
    def raw_text_reader(*_a, **_k):
        raise AssertionError("ห้ามหาปี/ขั้นเอกสารจากข้อความดิบ (รวมข้อความซ่อนนอกขอบหน้า)")
    monkeypatch.setattr(ex, "detect_meta", raw_text_reader)
    for path, stage in zip(books["draft_act"], ("draft", "act")):
        bf, sc, n = svc._facts_live(path, AG, "", "")
        vis = svc.year_texts(path, n, sc.first)
        ye, se = ex.detect_year(vis, sc.first), ex.detect_stage(vis, sc.first)
        assert (bf.fiscal_year, bf.year_status) == (ye.year, ye.status) and bf.fiscal_year == 2570
        assert (bf.stage, bf.stage_status, bf.stage_origin) == (stage, "ok", "title_line") == (se.stage, se.status,
                                                                                            "title_line")
        assert bf.stage_evidence and all(e["kind"] == stage for e in bf.stage_evidence)


def test_register_stage_used_only_when_text_is_silent_and_warnings_reach_the_pages(client, web_run):
    silent = ex.BookFacts("v", "p", 2570, "", "x")
    silent.stage_status = "not_found"
    svc._stage_from_register(silent, "draft")
    assert (silent.stage, silent.stage_status, silent.stage_origin) == ("draft", "ok", "register")
    said = ex.BookFacts("v", "p", 2570, "act", "x")
    said.stage_status, said.stage_origin = "ok", "title_line"
    svc._stage_from_register(said, "draft")                       # ข้อความบอก พ.ร.บ. · ทะเบียนบอกร่าง
    assert (said.stage, said.stage_status) == ("", "conflict") and said.stage_evidence[-1]["cue"] == "register"
    none = ex.BookFacts("v", "p", 2570, "", "x")
    none.stage_status = "not_found"
    v = svc.RunView({"id": "x"}, cmp.CompareResult(cmp.MODE_SAME_YEAR, 2570, 2570, []), [], {}, silent, said)
    w = dict(v.stage_warnings)
    assert "ทะเบียนดาวน์โหลด" in w["A"] and "ขัดกัน" in w["B"] and "ขัดกัน" in v.side_label("B")
    v2 = svc.RunView({"id": "x"}, cmp.CompareResult(cmp.MODE_SAME_YEAR, 2570, 2570, []), [], {}, none, none)
    assert all("ไม่ได้ยืนยันจากเอกสาร" in m for _s, m in v2.stage_warnings)
    # เล่มสังเคราะห์ที่ปกบอกขั้นชัด: ไม่มีคำเตือน · Audit การส่งออกบันทึกขั้น/สถานะ/ที่มาของทั้งสองฉบับ
    rid = _fresh_run(web_run[0])
    assert svc.view(rid).stage_warnings == []
    _decide_all(rid)
    svc.export_csv_checked(rid)
    d = json.loads([e for e in pdfpair_repo.audit_entries(rid)
                    if e["action"] == "pdfpair_exported"][-1]["detail_json"])
    assert d["stages"] == {"A": {"stage": "draft", "status": "ok", "origin": "title_line"},
                           "B": {"stage": "act", "status": "ok", "origin": "title_line"}}


# ── #42 · สองกรณีจากแบบทวนระเบียนกับภาพ (ชุดพัฒนา) — ทำซ้ำด้วยหน้าสังเคราะห์ ───────────────────────────
def _synthetic_page(rows, page=1):
    """หน้าสังเคราะห์จากตำแหน่งคำ ``[(y, [(ข้อความ, x0), …]), …]`` — วางเลียนแบบผังหน้าจริงของชุดพัฒนา"""
    from redbook.evidence.pdftext import PageText, Word
    words = []
    for i, (y, ws) in enumerate(rows):
        for text, x in ws:
            words.append(Word(text, x, y, x + 5.5 * len(text), y + 10, 0, i))
    return PageText(page, 595, 842, tuple(words), ())


_OUTCOME_HEADING = (120, [("3.", 81), ("ผลสัมฤทธิ์หรือประโยชน์ที่คาดว่าจะได้รับจากการใช้จ่ายงบประมาณ", 95)])


def test_case_a_top_header_line_of_outcome_table_is_not_outcome_text():
    """D2_A/D3x ข้อ 5: "ผลสัมฤทธิ์ | ค่าเป้าหมาย" บรรทัดบนของหัวตารางสามบรรทัด เคยถูกบันทึกเป็นข้อความผลสัมฤทธิ์"""
    pt = _synthetic_page([
        _OUTCOME_HEADING,
        (150, [("ผลสัมฤทธิ์", 180), ("ค่าเป้าหมาย", 420)]),
        (160, [("หน่วยนับ", 336)]),
        (170, [("หรือประโยชน์ที่คาดว่าจะได้รับ", 145), ("ปี", 400), ("2569", 414), ("ปี", 470), ("2570", 484)]),
        (191, [("(1)", 81), ("ผลสัมฤทธิ์", 98), (":", 150), ("ประชาชนได้รับบริการด้านสุขภาพ", 158),
               ("ร้อยละ", 336), ("85", 412), ("88", 482)])])
    bf = ex.extract([pt], fiscal_year=2570)
    assert not [t for t in bf.texts if "ค่าเป้าหมาย" in t.text]                 # หัวตารางไม่ใช่เนื้อความ
    ind = [i for i in bf.indicators if "ประชาชนได้รับบริการ" in i.name]
    assert len(ind) == 1 and ind[0].targets == {"2569": "85", "2570": "88"} and ind[0].unit == "ร้อยละ"
    # ตัวควบคุม: เนื้อความผลสัมฤทธิ์จริงที่มีคำหัวตารางปนอยู่ ยังเป็นข้อความตามเดิม
    body = _synthetic_page([_OUTCOME_HEADING, (150, [("(1)", 81), ("ผลสัมฤทธิ์ค่าเป้าหมายของประชาชนดีขึ้น", 98)])])
    assert [t.text for t in ex.extract([body], fiscal_year=2570).texts] == ["ผลสัมฤทธิ์ค่าเป้าหมายของประชาชนดีขึ้น"]


def _range_table_book(start_value):
    return ex.extract([_synthetic_page([
        _OUTCOME_HEADING,
        (150, [("ตัวชี้วัด/", 60), ("เริ่มต้น", 262), ("-", 296), ("ปี", 302), ("2569", 314), ("ปี", 372), ("2570", 384),
               ("ปี", 430), ("2571", 442), ("ปี", 488), ("2572", 500), ("ปี", 540), ("2573", 552), ("-", 578),
               ("จบ", 584)]),
        (160, [("หน่วยนับ", 228)]),
        (183, [("เชิงปริมาณ", 60), (":", 116), ("เพิ่มประสิทธิภาพในการทำงาน", 122), ("ร้อยละ", 228),
               (start_value, 300), ("-", 388), ("-", 446), ("-", 504), ("15", 562)])])], fiscal_year=2570)


def test_case_b_indicator_values_in_year_range_columns_are_kept_and_compared():
    """D1_A ข้อ 4: ค่า "30" ใต้คอลัมน์ "เริ่มต้น – ปี 2569" (และค่าใต้ "ปี 2573 – จบ") หายเงียบ — เก็บแค่ปีเดี่ยว"""
    a = _range_table_book("30")
    ind = [i for i in a.indicators if "เพิ่มประสิทธิภาพ" in i.name]
    assert len(ind) == 1
    assert ind[0].targets == {"เริ่มต้น–2569": "30", "2570": "-", "2571": "-", "2572": "-", "2573–จบ": "15"}
    # สองฉบับต่างกันเฉพาะคอลัมน์ช่วงปี — ต้องมีข้อสังเกต (เดิมไม่มีข้อใดเลย = พลาดเงียบ)
    b = _range_table_book("40")
    got = [f for f in cmp.compare(a, b).findings if f.topic == cmp.T_IND and f.kind == cmp.K_CHANGED]
    assert [(f.column, f.a.value, f.b.value) for f in got] == [("ค่าช่วงปี เริ่มต้น–2569", "30", "40")]
    assert not [f for f in cmp.compare(a, _range_table_book("30")).findings if f.topic == cmp.T_IND]


def test_reader_does_not_hold_pdf_files_open(books, tmp_path):
    """ตัวอ่านจำเอกสารที่เปิดไว้เพื่อความเร็ว แต่ต้องไม่ถือไฟล์บนดิสก์ — Windows ลบ/แทนที่ไฟล์ที่ถูกเปิดค้างไม่ได้"""
    import os
    import shutil
    import stat
    p = tmp_path / "copy.pdf"
    shutil.copy(books["draft_act"][0], p)
    first = reader.page_words(p, [1])
    assert first and reader.page_words(p, [1])[0].words == first[0].words      # ครั้งที่สองใช้เอกสารที่จำไว้
    os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
    p.unlink()                                     # ไม่ PermissionError ขณะตัวอ่านยังจำเอกสารนี้อยู่
    assert not p.exists()
