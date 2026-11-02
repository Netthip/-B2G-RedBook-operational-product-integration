# -*- coding: utf-8 -*-
"""route หลักฐาน PDF เก่า/ใหม่ + หน้าตรวจยืนยัน — การกดเปิด · เทียบข้างกัน · ความเป็นส่วนตัว

🔴 คำสั่งกิ๊ฟ (9 ก.ย. 2569 · §3 และ Gate 3) —
  * click Old/New evidence → เปิดหน้าที่บันทึกไว้ · เทียบข้างกัน · แสดงหน้า/ขั้น/แฮช/ข้อความ
  * ไม่มี absolute path · ไม่มี ``file://`` · ไม่มี raw exception · ไม่มีเนื้อหาที่ยัง
    ไม่เผยแพร่ใน URL/ล็อก · route ``/evidence/{document_id}?page=n`` ผ่านทะเบียน
  * กรณี: ย้ายหน้า · เลขหน้าเปลี่ยน · ไม่มีชั้นข้อความ · ข้อความซ้ำ · ไฟล์ต้นทางหาย
  * หน้าตรวจเฉลยห้ามมีคะแนนของเครื่อง

🔴 **SYNTHETIC TEST FIXTURE**
"""
import re
from pathlib import Path

import pytest

import keystage
from fastapi.testclient import TestClient

from redbook import config
from redbook.app import create_app
from redbook.evidence import documents as docs
from redbook.evidence import pdftext
from redbook.indicators import mapping as mp
from redbook.services import evidence as svc
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD

FIX = Path(__file__).resolve().parent / "fixtures" / "synthetic_pdf"
pytestmark = pytest.mark.skipif(pdftext.product_backend() is None,
                                reason=pdftext.NO_TEXT_BACKEND)

#: ข้อความ "ภายใน" สมมติ — ใช้ตรวจว่าไม่รั่วไป URL/ล็อก/ไฟล์ส่งออก
INTERNAL_MARK = "ตัวชี้วัดที่ 8 : จำนวนคู่มือที่จัดทำ 3 ฉบับ"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def world(client, tmp_path_factory):
    """ลงทะเบียนสำเนาสังเคราะห์ในโฟลเดอร์ชั่วคราว (ชื่อโฟลเดอร์มีคำที่ห้ามรั่ว)"""
    tmp = tmp_path_factory.mktemp("evroutes_โฟลเดอร์ลับ")
    old_p, new_p = tmp / "old.pdf", tmp / "new.pdf"
    old_p.write_bytes((FIX / "synthetic_old_fy2569.pdf").read_bytes())
    new_p.write_bytes((FIX / "synthetic_new_fy2570.pdf").read_bytes())
    old = svc.register_pdf(old_p, title="เก่า (สังเคราะห์)", stage=docs.STAGE_DRAFT_BILL,
                           fiscal_year=2569, authority="SYNTHETIC",
                           disclosure_class=docs.DISC_SYNTHETIC)
    new = svc.register_pdf(new_p, title="ใหม่ (สังเคราะห์)", stage=docs.STAGE_DRAFT_BILL,
                           fiscal_year=2570, authority="SYNTHETIC",
                           disclosure_class=docs.DISC_SYNTHETIC)
    res = svc.run_indicator_pipeline(old.document_id, new.document_id, label="ROUTES")
    # 🔴 B4 — ขั้นตัดสินหลังรันเปิดได้หลังเฉลยถูกผนึก · ที่นี่กรอก/ผนึกด้วย **ข้อมูลสังเคราะห์**
    # เพื่อทดสอบ *กลไก* เท่านั้น ไม่ใช่เฉลยของงานวิจัย
    keystage.unlock_adjudication(res.run_id)
    rv = svc.run_view(res.run_id)
    return {"tmp": tmp, "old": old, "new": new, "run_id": res.run_id, "rv": rv,
            "old_path": old_p, "new_path": new_p}


def _pair(world, status, needle):
    for p in world["rv"].pairs:
        text = (p.old.observed_text if p.old else "") + (p.new.observed_text if p.new else "")
        if p.proposed_status == status and needle in text:
            return p
    raise AssertionError(needle)


def _assert_clean(html: str, world, where: str):
    assert str(world["tmp"]) not in html, where
    assert "โฟลเดอร์ลับ" not in html, where
    assert "file://" not in html, where
    assert not re.search(r"[A-Za-z]:\\Users", html), where
    assert "Traceback" not in html and "sqlite3." not in html, where


# ── การกดเปิดหลักฐาน ─────────────────────────────────────────────────────────

def test_report_links_old_and_new_evidence_through_registry_routes(client, world):
    r = client.get(f"/indicators/runs/{world['run_id']}")
    assert r.status_code == 200
    html = r.text
    _assert_clean(html, world, "report")
    assert f"/evidence/{world['old'].document_id}?page=" in html
    assert f"/evidence/{world['new'].document_id}?page=" in html
    assert f"run={world['run_id']}" in html, "B5 — ลิงก์หลักฐานต้องพก run context"
    assert "/evidence/compare?run=" in html
    assert svc.MANDATORY_NOTICE in html
    assert "SYNTHETIC TEST FIXTURE" in html


def test_old_evidence_opens_recorded_page_with_hash_stage_text_and_bbox(client, world):
    p = _pair(world, mp.SAME_EXACT, "ตัวชี้วัดที่ 1")
    assert (p.old.page, p.new.page) == (2, 3)          # ย้ายหน้า
    r = client.get(p.old.evidence_url)
    assert r.status_code == 200
    html = r.text
    _assert_clean(html, world, "old evidence")
    assert world["old"].content_sha256 in html
    assert "DRAFT_BILL" in html and "หน้า <b>2</b>" in html
    assert "ตัวชี้วัดที่ 1" in html and "EXACT_BBOX" in html
    assert f"/evidence/{world['old'].document_id}/file#page=2" in html
    img = re.search(r'src="(/evidence/[^"]+/page/2\.png\?hl=[0-9.,]+)"', html)
    assert img, "ต้องมีภาพหน้าพร้อมกรอบเน้น"
    png = client.get(img.group(1))
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_new_evidence_page_number_changed_is_reflected(client, world):
    p = _pair(world, mp.SAME_EXACT, "ตัวชี้วัดที่ 1")
    r = client.get(p.new.evidence_url)
    assert r.status_code == 200 and "หน้า <b>3</b>" in r.text
    assert f"/evidence/{world['new'].document_id}/file#page=3" in r.text


def test_file_route_streams_pdf_inline_named_by_document_id(client, world):
    r = client.get(f"/evidence/{world['old'].document_id}/file")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    cd = r.headers.get("content-disposition", "")
    assert "inline" in cd and world["old"].document_id in cd
    assert "old.pdf" not in cd and str(world["tmp"]) not in cd
    assert r.content[:5] == b"%PDF-"


def test_side_by_side_compare_shows_both_pages_and_no_score(client, world):
    p = _pair(world, mp.DEFINITION_CHANGED, "ตัวชี้วัดที่ 4")
    r = client.get(p.compare_url)
    assert r.status_code == 200
    html = r.text
    _assert_clean(html, world, "compare")
    assert html.count("evidence-img") == 2
    assert world["old"].content_sha256 in html and world["new"].content_sha256 in html
    assert "นับจากโครงการทั้งหมด" in html and "นับจากโครงการที่ได้รับจัดสรร" in html
    assert "DEFINITION_CHANGED" in html and "ต้องให้คนยืนยัน" in html
    for token in ("internal_score", "trigram_dice", "dice=", "0.7", "0.8", "0.9"):
        assert token not in html, token


def test_missing_text_layer_page_opens_and_is_marked_location_review_required(client, world):
    r = client.get(f"/evidence/{world['old'].document_id}?page=4")
    assert r.status_code == 200
    assert svc.LOCATION_REVIEW_REQUIRED in r.text
    assert "TEXT_LAYER_PARTIAL" in r.text
    assert "หน้า 4 — LOCATION_REVIEW_REQUIRED" in client.get(f"/indicators/runs/{world['run_id']}").text


def test_duplicate_wording_gives_two_rows_each_with_own_new_page(client, world):
    rows = [p for p in world["rv"].pairs if p.proposed_status == mp.AMBIGUOUS_REVIEW_REQUIRED
            and "ตัวชี้วัดที่ 7" in p.old.observed_text]
    assert sorted(p.new.page for p in rows) == [4, 5]
    html = client.get(f"/indicators/runs/{world['run_id']}/verify?status=AMBIGUOUS_REVIEW_REQUIRED").text
    assert html.count("ตัวชี้วัดที่ 7 : จำนวนกิจกรรมเผยแพร่ความรู้") >= 4


def test_unknown_or_malformed_document_ids_fail_closed(client, world):
    assert client.get("/evidence/doc_0000000000000000?page=1").status_code == 404
    assert client.get("/evidence/../etc/passwd").status_code in (400, 404)
    assert client.get("/evidence/doc_%2e%2e?page=1").status_code in (400, 404)
    assert client.get(f"/evidence/{world['old'].document_id}/page/2.png?hl=abc").status_code == 400
    assert client.get(f"/evidence/{world['old'].document_id}/page/99.png").status_code == 404


def test_evidence_page_without_run_context_hides_run_specific_id(client, world):
    """B5 + P4-1 — ชี้ข้อสังเกตโดยไม่ระบุรอบ ⇒ ตรวจผนึกไม่ได้ ⇒ **ล็อก** และไม่เปิดข้อสังเกตนั้น

    🔴 Pass 5 (Bo `5606392284` P4-1) เปลี่ยนจาก "200 + ป้าย RUN_CONTEXT_MISSING" เป็น 409
    เพราะหน้าเดิมยังแสดงข้อความและกรอบที่เครื่องสกัดได้ แม้จะซ่อนรหัสตัวชี้วัดแล้ว
    """
    p = _pair(world, mp.SAME_EXACT, "ตัวชี้วัดที่ 1")
    bare = client.get(f"/evidence/{world['old'].document_id}?page={p.old.page}"
                      f"&obs={p.old.observation_id}")
    assert bare.status_code == 409 and svc.RUN_CONTEXT_MISSING in bare.text
    assert p.old.observed_text not in bare.text
    assert p.old.indicator_id not in bare.text
    # หน้าเอกสาร (ไม่ชี้ข้อสังเกต) ยังเปิดได้ — ขั้นเฉลยต้องใช้
    page_only = client.get(f"/evidence/{world['old'].document_id}?page={p.old.page}")
    assert page_only.status_code == 200


def test_unavailable_source_is_reported_not_crashed(client, world, tmp_path):
    p = tmp_path / "gone.pdf"
    p.write_bytes((FIX / "synthetic_new_fy2570.pdf").read_bytes() + b"\n%gone\n")   # ต่างจากทุกไฟล์
    rec = svc.register_pdf(p, title="หาย", stage=docs.STAGE_DRAFT_BILL, fiscal_year=2570,
                           authority="SYNTHETIC", disclosure_class=docs.DISC_SYNTHETIC)
    p.unlink()
    page = client.get(f"/evidence/{rec.document_id}?page=1")
    assert page.status_code == 200 and svc.SOURCE_UNAVAILABLE in page.text
    assert client.get(f"/evidence/{rec.document_id}/file").status_code == 404
    assert client.get(f"/evidence/{rec.document_id}/page/1.png").status_code == 404
    _assert_clean(page.text, world, "unavailable")
    assert str(tmp_path) not in page.text


# ── ความเป็นส่วนตัว: URL · ล็อก · ไฟล์ส่งออก ─────────────────────────────────

def test_urls_carry_only_ids_pages_and_numbers(world):
    for p in world["rv"].pairs:
        for u in filter(None, [p.compare_url, p.old and p.old.evidence_url,
                               p.new and p.new.evidence_url, p.old and p.old.image_url,
                               p.new and p.new.image_url, p.old and p.old.open_url]):
            assert re.fullmatch(r"/[A-Za-z0-9_/.?=&,#\-]+", u), u
            assert "file://" not in u and not re.search(r"[฀-๿]", u), u


def test_log_has_no_document_text_or_paths(client, world):
    """ล็อกต้องไม่มี **ข้อความที่สกัดจากเอกสาร** และไม่มีเส้นทางของไฟล์

    🔴 (#28 · Bo #23 รอบ 3) เดิมตรวจด้วยคำกว้าง "ตัวชี้วัดที่" ซึ่งชนกับข้อความ 404 ของแอปเอง
    ("ไม่พบรอบทะเบียนตัวชี้วัดที่ระบุ") เมื่อรันร่วมกับชุดทดสอบอื่นในโปรเซสเดียว ⇒ false positive
    ตอนนี้ตรวจแบบ taint: เอาบรรทัดที่ backend สกัดได้จริงจาก PDF สังเคราะห์ทั้งสองฉบับ
    (ยาว ≥ 8 ตัวอักษร) มาเทียบกับล็อก — ถ้าบรรทัดใดโผล่ แปลว่าเนื้อหาเอกสารไหลลงล็อกจริง
    """
    from redbook.evidence import pdftext
    log_path = config.LOG_DIR / "app.log"
    text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert str(world["tmp"]) not in text and "โฟลเดอร์ลับ" not in text
    backend = pdftext.get_backend()
    tainted = {ln.text.strip() for p in (world["old_path"], world["new_path"])
               for page in backend.pages(p) for ln in page.lines if len(ln.text.strip()) >= 8}
    assert tainted, "fixture ต้องมีข้อความให้ใช้เป็น taint"
    leaked = sorted(t for t in tainted if t in text)
    assert not leaked, f"ข้อความจากเอกสารไหลลงล็อก: {leaked[:3]}"
    assert world["run_id"] in text, "ล็อกต้องมี id/ตัวเลขของรอบ (ไม่ใช่ว่างเปล่า)"


def test_verification_package_has_no_scores_paths_or_unpublished_text(client, world, tmp_path):
    # ทำสำเนา 'ภายใน' ที่ยังไม่เผยแพร่ ให้แน่ใจว่าตัวยึดถูกใช้แทนข้อความ
    p = tmp_path / "internal.pdf"
    p.write_bytes((FIX / "synthetic_new_fy2570.pdf").read_bytes() + b"\n%internal\n")
    internal = svc.register_pdf(p, title="ภายใน", stage=docs.STAGE_BUDGET_REQUEST,
                                fiscal_year=2570, authority="SYNTHETIC",
                                disclosure_class=docs.DISC_INTERNAL)
    res = svc.run_indicator_pipeline(world["old"].document_id, internal.document_id, label="INT")
    keystage.unlock_adjudication(res.run_id)
    rv = svc.run_view(res.run_id)
    files = svc.write_package(rv, tmp_path / "out")
    import openpyxl
    wb = openpyxl.load_workbook(files.xlsx_path, read_only=True)
    cells = [str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None]
    blob = "\n".join(cells)
    assert svc.UNPUBLISHED_PLACEHOLDER in blob
    assert "ตัวชี้วัดที่ 8 : ร้อยละของระบบ" not in blob, "ข้อความจากเอกสารภายในต้องไม่ออกในไฟล์"
    assert "ตัวชี้วัดที่ 1" in blob, "ข้อความจากเอกสารสังเคราะห์/สาธารณะออกได้"
    for token in ("internal_score", "trigram_dice", "file://", str(tmp_path), "โฟลเดอร์ลับ"):
        assert token not in blob, token
    assert svc.MANDATORY_NOTICE in blob and svc.PACKAGE_NOTICE in blob
    assert "/evidence/compare?run=" in blob
    snap = (files.snapshot_path).read_text(encoding="utf-8")
    assert '"scores_included": false' in snap


def test_verify_page_and_package_route_work_and_hide_scores(client, world):
    r = client.get(f"/indicators/runs/{world['run_id']}/verify")
    assert r.status_code == 200
    _assert_clean(r.text, world, "verify")
    assert svc.PACKAGE_NOTICE in r.text
    for token in ("internal_score", "trigram_dice", "dice="):
        assert token not in r.text
    token = client.cookies.get(CSRF_COOKIE)
    w = client.post(f"/indicators/runs/{world['run_id']}/package", data={CSRF_FIELD: token})
    assert w.status_code == 200 and "indpkg_" in w.text
    # 🔴 P4-2 — ลิงก์ดาวน์โหลดต้องระบุรอบ และตรวจผนึกใหม่ทุกครั้งก่อนส่งไฟล์
    m = re.search(r"/indicators/runs/([A-Za-z0-9_]+)/exports/(indpkg_[A-Za-z0-9_]+\.xlsx)",
                  w.text)
    assert m and m.group(1) == world["run_id"]
    name = m.group(2)
    d = client.get(f"/indicators/runs/{world['run_id']}/exports/{name}")
    assert d.status_code == 200 and d.content[:2] == b"PK"
    # route เดิมที่ไม่มีบริบทของรอบ ปฏิเสธเสมอ แม้ไฟล์จะผูกกับรอบแล้ว
    assert client.get(f"/indicators/exports/{name}").status_code == 410
    assert client.get("/indicators/exports/../app.log").status_code in (400, 404, 410)
    assert client.get(f"/indicators/runs/{world['run_id']}/exports/..%2Fapp.log"
                      ).status_code in (400, 404)


def test_decision_via_route_requires_csrf_and_records_audit(client, world):
    p = _pair(world, mp.SAME_CONCEPT_REPHRASED, "ตัวชี้วัดที่ 3")
    url = f"/indicators/runs/{world['run_id']}/mappings/{p.mapping_id}/decide"
    bad = client.post(url, data={"decision": "ACCEPT", "reason": "x", "reviewer": "gift"})
    assert bad.status_code == 403
    token = client.cookies.get(CSRF_COOKIE)
    missing_reason = client.post(url, data={"decision": "ACCEPT", "reason": "", "reviewer": "gift",
                                            CSRF_FIELD: token})
    assert missing_reason.status_code == 400 and "เหตุผล" in missing_reason.text
    ok = client.post(url, data={"decision": "ACCEPT", "reason": "ตรวจแล้ว ตัวเดียวกัน",
                                "reviewer": "gift", CSRF_FIELD: token}, follow_redirects=False)
    assert ok.status_code == 303
    page = client.get(p.compare_url).text
    assert "ตัดสินโดย gift" in page and "SAME_CONCEPT_REPHRASED" in page
    from redbook.storage import audit
    assert any(e["action"] == "indicator_mapping_decided" for e in audit.entries(limit=50))
    assert audit.verify_chain()["ok"] is True


def test_routes_do_not_import_evidence_or_indicator_packages_directly():
    """route ต้องผ่านชั้นบริการ — ตรวจด้วย AST ไม่ใช่ค้นข้อความ"""
    import ast

    src = (Path(__file__).resolve().parent.parent / "redbook" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            names = [a.name for a in node.names]
            if mod.endswith("evidence") and "documents" in names or mod.endswith("indicators"):
                bad.append(mod)
            if "evidence." in mod + "." and not mod.endswith("services"):
                if mod.split(".")[-1] in ("documents", "pdftext"):
                    bad.append(mod)
        if isinstance(node, ast.Import):
            for a in node.names:
                if "redbook.evidence" in a.name or "redbook.indicators" in a.name:
                    bad.append(a.name)
    assert not bad, bad
