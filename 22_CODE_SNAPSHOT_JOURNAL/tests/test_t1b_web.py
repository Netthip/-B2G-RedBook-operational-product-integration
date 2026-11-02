# -*- coding: utf-8 -*-
"""T1B — หน้าสรุป · คิว · รายละเอียด (Lane B ข้อ 5 · 6)

🔴 คำสั่ง Bo · `BO REVIEW COMPLETE` (Issue #1) · LANE B ข้อ 5-6 —
*"T1B run-summary, queue, and finding-detail routes/templates using synthetic
fixtures"* และ *"search, pagination, flag filters, and previous/next navigation"*

ข้อมูลทั้งหมดในไฟล์นี้เป็น **fixture สังเคราะห์ที่เผยแพร่ได้** ไม่มีการเปิดแฟ้มจริง

🔴 **SYNTHETIC TEST FIXTURE** — ห้ามรายงานผลจากชุดนี้ว่าเป็นข้อผิดพลาดในเอกสารจริง

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import html
import inspect
import re

import pytest
from fastapi.testclient import TestClient

from redbook import privacy
from redbook.app import create_app
from redbook.services import t1b as svc
from redbook.storage import t1b_repo
from t1b_synth import build_workbook, records

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def healthy_run(tmp_path_factory):
    """รอบที่ผ่านด่าน — บันทึกลงที่เก็บจริงเพื่อให้ route อ่านได้"""
    tmp = tmp_path_factory.mktemp("t1b_web_ok")
    base = records(build_workbook(
        tmp, filename="a.xlsx", agency="สถาบันทดสอบ", cover_year=2569,
        section_title=TITLE))
    curr = records(build_workbook(
        tmp, filename="b.xlsx", agency="สถาบันทดสอบ", cover_year=2570,
        section_title=TITLE, invest=12.0))
    view = svc.run_from_records(base, curr, run_id="WEB-OK")
    t1b_repo.init_t1b_schema()
    t1b_repo.save_run(view, run_id="WEB-OK")
    return view


@pytest.fixture(scope="module")
def blocked_run(tmp_path_factory):
    """รอบที่ด่านปฏิเสธ — หน้าจอต้องบอกตรง ๆ ว่าไม่มีการเทียบอัตโนมัติ"""
    tmp = tmp_path_factory.mktemp("t1b_web_blocked")
    base = records(build_workbook(
        tmp, filename="x.xlsx", agency=None, cover_year=2570,
        section_title=TITLE))
    curr = records(build_workbook(
        tmp, filename="y.xlsx", agency=None, cover_year=2570,
        section_title=TITLE, invest=12.0))
    view = svc.run_from_records(base, curr, run_id="WEB-BLOCKED")
    t1b_repo.init_t1b_schema()
    t1b_repo.save_run(view, run_id="WEB-BLOCKED")
    return view


# ══════════════════════════════════════════════════════════════════════════════
#  W1 — ขอบของสถาปัตยกรรม
# ══════════════════════════════════════════════════════════════════════════════


def test_w1_routes_never_import_the_engine_directly():
    """🔴 *"the service layer must sit between web routes and redbook/t1b/*"*"""
    import redbook.app as appmod

    src = inspect.getsource(appmod)
    banned = re.findall(r"^\s*from \.t1b[. ]|^\s*from redbook\.t1b[. ]|"
                        r"^\s*import redbook\.t1b", src, re.M)
    assert banned == [], f"app.py import เครื่องยนต์ T1B ตรง ๆ: {banned}"
    assert "from .services import t1b as t1b_service" in src


# ══════════════════════════════════════════════════════════════════════════════
#  W2 — หน้าสรุป
# ══════════════════════════════════════════════════════════════════════════════


def test_w10_run_summary_renders_counts_and_versions(client, healthy_run):
    # IA #24: ตัวเลขใบข้อสังเกต/รุ่นเครื่องยนต์ย้ายไปหน้า "รายละเอียดการตรวจสอบ"
    r = client.get("/t1b/runs/WEB-OK/details")
    assert r.status_code == 200
    body = r.text
    s = healthy_run.summary
    assert str(s.total_findings) in body
    assert s.key_version in body and s.matching_version in body
    assert s.readiness_label in body


def test_w11_summary_states_the_product_boundary(client, healthy_run):
    """🔴 หน้าจอต้องบอกเองว่านี่ไม่ใช่ผลการประเมินเชิงวิจัยและไม่ใช่การรับรอง"""
    body = client.get("/t1b/runs/WEB-OK").text
    assert "ผู้ตรวจ" in body
    assert "ไม่ใช่การรับรอง" in body or "ไม่ใช่ผลการประเมินเชิงวิจัย" in body


def test_w12_summary_says_readiness_is_computed_not_a_button(client, healthy_run):
    body = client.get("/t1b/runs/WEB-OK/details").text
    assert "ไม่ใช่ปุ่ม" in body
    assert "<button" not in body.split("สถานะความพร้อม")[-1][:400]


def test_w13_blocked_run_page_says_no_automatic_comparison(client, blocked_run):
    # หน้าแรกบอกเป็นภาษาคน · รหัสเหตุผลของด่านอยู่หน้ารายละเอียดการตรวจสอบ
    body = client.get("/t1b/runs/WEB-BLOCKED").text
    assert "ยังยืนยันไม่ได้ว่าสองฉบับเป็นหน่วยงานเดียวกัน" in body
    assert "ไม่มีรายการใดหายไป" in body
    details = client.get("/t1b/runs/WEB-BLOCKED/details").text
    assert "ด่านตัวตนหน่วยงานไม่ผ่าน" in details
    assert "ไม่มีรายการใดหายไป" in details
    assert blocked_run.summary.identity_reason in details


def test_w14_unknown_run_is_a_clean_404(client):
    r = client.get("/t1b/runs/ไม่มีจริง")
    assert r.status_code == 404
    for marker in privacy.INTERNAL_ERROR_MARKERS:
        assert marker not in r.text


# ══════════════════════════════════════════════════════════════════════════════
#  W3 — คิว: ค้นหา · ตัวกรอง · แบ่งหน้า
# ══════════════════════════════════════════════════════════════════════════════


def test_w20_queue_lists_findings(client, healthy_run):
    r = client.get("/t1b/runs/WEB-OK/queue")
    assert r.status_code == 200
    assert str(healthy_run.summary.total_findings) in r.text


def test_w21_only_review_filter_narrows_the_list(client, healthy_run):
    all_page = client.get("/t1b/runs/WEB-OK/queue?per_page=200").text
    only = client.get("/t1b/runs/WEB-OK/queue?only_review=1&per_page=200").text
    n_all = all_page.count('class="btn small"')
    n_only = only.count('class="btn small"')
    assert n_only <= n_all


def test_w22_type_filter_is_honoured(client, healthy_run):
    ftype = next(iter(healthy_run.summary.by_type))
    r = client.get(f"/t1b/runs/WEB-OK/queue?ftype={ftype}&per_page=200")
    assert r.status_code == 200
    expected = svc.queue_page(healthy_run, types=(ftype,),
                              per_page=svc.MAX_PER_PAGE)
    assert str(expected.total) in r.text


def test_w23_pagination_links_carry_the_filters(client, healthy_run):
    r = client.get("/t1b/runs/WEB-OK/queue?per_page=2&only_review=1")
    assert r.status_code == 200
    if "หน้าถัดไป" in r.text:
        link = re.search(r'href="([^"]*queue\?[^"]*page=2[^"]*)"', r.text)
        assert link, "ลิงก์หน้าถัดไปต้องมี page=2"
        assert "only_review=1" in html.unescape(link.group(1)), (
            "🔴 กดหน้าถัดไปแล้วตัวกรองต้องไม่หลุด")


def test_w23b_pagination_links_keep_the_page_size(client, healthy_run):
    """🔴 ข้อบกพร่องที่เจอตอนกดจริงในเบราว์เซอร์

    ลิงก์ "หน้าถัดไป" เดิมไม่พา ``per_page`` ไปด้วย ⇒ กดครั้งเดียวแล้วขนาดหน้า
    เด้งกลับค่าเริ่มต้น (50) ผู้ใช้จึงเห็นรายการชุดอื่นทั้งหน้าโดยไม่มีอะไรบอก
    และเลขหน้าที่แสดงก็ไม่ตรงกับที่กดไป
    """
    r = client.get("/t1b/runs/WEB-OK/queue?per_page=2")
    assert r.status_code == 200
    if "หน้าถัดไป" not in r.text:
        pytest.skip("รอบนี้มีรายการน้อยเกินกว่าจะมีหน้าที่สอง")
    raw = re.search(r'href="([^"]*queue\?[^"]*page=2[^"]*)"', r.text).group(1)
    # href ถูก escape เป็น &amp; ตามมาตรฐาน HTML — เบราว์เซอร์ถอดให้เองก่อนเรียก
    link = html.unescape(raw)
    assert "per_page=2" in link, f"ลิงก์ทิ้งขนาดหน้า: {link}"

    nxt = client.get(link)
    assert nxt.status_code == 200
    assert "หน้า 2/" in nxt.text


def test_w23c_detail_opened_from_page_2_returns_to_page_2(client, healthy_run):
    """🔴 `BO REVIEW` (consolidated) หัวข้อ B — UX follow-up

    เดิม ``qs_here`` เก็บ filter และ per_page แต่ **ไม่เก็บ page**
    ⇒ กดดูรายการจากหน้า 2 แล้วกด "กลับไปที่คิว" จะเด้งไปหน้า 1
    ผู้ตรวจต้องไล่หาตำแหน่งเดิมเองทุกครั้ง
    """
    queue2 = client.get("/t1b/runs/WEB-OK/queue?per_page=2&page=2")
    assert queue2.status_code == 200
    if "หน้า 2/" not in queue2.text:
        pytest.skip("รอบนี้มีรายการน้อยเกินกว่าจะมีหน้าที่สอง")

    detail_href = html.unescape(
        re.search(r'href="([^"]*/findings/[^"]+)"', queue2.text).group(1))
    assert "page=2" in detail_href, f"ลิงก์ดูรายการทิ้งเลขหน้า: {detail_href}"

    detail = client.get(detail_href)
    assert detail.status_code == 200

    back = html.unescape(
        re.search(r'href="([^"]*queue\?[^"]*)"', detail.text).group(1))
    assert "page=2" in back and "per_page=2" in back, back
    assert "หน้า 2/" in client.get(back).text, "กลับมาแล้วต้องอยู่หน้าเดิม"


def test_w24_out_of_range_page_does_not_error(client, healthy_run):
    assert client.get("/t1b/runs/WEB-OK/queue?page=9999").status_code == 200
    assert client.get("/t1b/runs/WEB-OK/queue?page=0").status_code == 200


def test_w25_search_with_no_match_shows_an_explanatory_empty_state(
        client, healthy_run):
    r = client.get("/t1b/runs/WEB-OK/queue?q=คำที่ไม่มีทางพบเลยจริงจริง")
    assert r.status_code == 200
    assert "ไม่มีรายการที่ตรงกับตัวกรอง" in r.text
    assert "ล้างตัวกรอง" in r.text


def test_w26_search_input_is_escaped_not_executed(client, healthy_run):
    """🔴 คำค้นของผู้ใช้ต้องถูก escape ก่อนสะท้อนกลับ"""
    r = client.get("/t1b/runs/WEB-OK/queue?q=%3Cscript%3Ealert(1)%3C/script%3E")
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text
    assert "&lt;script&gt;" in r.text


# ══════════════════════════════════════════════════════════════════════════════
#  W4 — หน้ารายละเอียดและการเดินหน้าถอยหลัง
# ══════════════════════════════════════════════════════════════════════════════


def test_w30_detail_shows_locations_and_reason(client, healthy_run):
    f = healthy_run.findings[0]
    r = client.get(f"/t1b/runs/WEB-OK/findings/{f.finding_id}")
    assert r.status_code == 200
    assert f.type_label in r.text
    assert f.finding_id in r.text


def test_w31_detail_declares_the_id_stability_honestly(client, healthy_run):
    for f in healthy_run.findings:
        body = client.get(f"/t1b/runs/WEB-OK/findings/{f.finding_id}").text
        if f.id_is_stable:
            assert "คงที่เมื่อรันซ้ำ" in body
        else:
            assert "ไม่รับประกันว่าคงที่เมื่อรันซ้ำ" in body


def test_w32_detail_has_decision_controls_with_mandatory_wording(client, healthy_run):
    """เดิม: Bo สั่งให้ยังไม่ทำปุ่มคำตัดสิน · กิ๊ฟอนุมัติ 7 ก.ย. (ข้อ D)
    ด่านนี้จึงกลับด้าน — ต้องมีปุ่ม สี่สถานะ และข้อความบังคับ"""
    from redbook.services import decisions as dec
    body = client.get(
        f"/t1b/runs/WEB-OK/findings/{healthy_run.findings[0].finding_id}").text
    assert "ระบบเสนอสิ่งที่ตรวจพบ ผู้ปฏิบัติงานเป็นผู้ตัดสิน" in body
    assert dec.E_BUDGETING_DISCLAIMER in body
    for code in dec.DECIDABLE:
        assert f'value="{code}"' in body
    assert 'name="expected_latest_seq"' in body


def test_w33_prev_next_walk_the_queue(client, healthy_run):
    ids = [f.finding_id for f in healthy_run.findings]
    if len(ids) < 3:
        pytest.skip("ต้องมีอย่างน้อยสามรายการจึงจะเดินได้ครบ")

    first = client.get(f"/t1b/runs/WEB-OK/findings/{ids[0]}").text
    assert "รายการก่อนหน้า" not in first
    assert ids[1] in first

    mid = client.get(f"/t1b/runs/WEB-OK/findings/{ids[1]}").text
    assert ids[0] in mid and ids[2] in mid

    last = client.get(f"/t1b/runs/WEB-OK/findings/{ids[-1]}").text
    assert "รายการถัดไป" not in last


def test_w34_detail_outside_the_filter_says_so(client, healthy_run):
    outside = [f for f in healthy_run.findings if not f.requires_human_decision]
    if not outside:
        pytest.skip("รอบนี้ไม่มีรายการที่อยู่นอกคิวตรวจ")
    body = client.get(
        f"/t1b/runs/WEB-OK/findings/{outside[0].finding_id}?only_review=1").text
    assert "อยู่นอกตัวกรองที่เปิดอยู่" in body


def test_w35_unknown_finding_is_a_clean_404(client, healthy_run):
    r = client.get("/t1b/runs/WEB-OK/findings/ไม่มีจริง")
    assert r.status_code == 404
    for marker in privacy.INTERNAL_ERROR_MARKERS:
        assert marker not in r.text


# ══════════════════════════════════════════════════════════════════════════════
#  W5 — ความเป็นส่วนตัวของทุกหน้า T1B
# ══════════════════════════════════════════════════════════════════════════════


def test_w40_no_t1b_page_exposes_an_absolute_path(client, healthy_run,
                                                  blocked_run):
    urls = ["/t1b/runs", "/t1b/runs/WEB-OK", "/t1b/runs/WEB-OK/queue",
            "/t1b/runs/WEB-BLOCKED", "/t1b/runs/WEB-BLOCKED/queue"]
    urls += [f"/t1b/runs/WEB-OK/findings/{f.finding_id}"
             for f in healthy_run.findings[:5]]
    for url in urls:
        body = client.get(url).text
        leaks = privacy.find_absolute_paths(body)
        assert leaks == [], f"{url} รั่วเส้นทาง: {leaks[:2]}"


def test_w41_t1b_pages_keep_the_security_headers(client, healthy_run):
    r = client.get("/t1b/runs/WEB-OK")
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_w42_t1b_templates_have_no_inline_styles():
    """🔴 ข้อบกพร่องที่เจอจาก console ของเบราว์เซอร์จริง

    CSP ของระบบเป็น ``style-src 'self'`` โดยไม่มี ``'unsafe-inline'``
    ⇒ ``style="..."`` ในเทมเพลตถูกบล็อก **เงียบ ๆ** — หน้าจอยังขึ้น แต่การจัดวาง
    ที่เขียนไว้ไม่ทำงานเลย และเบราว์เซอร์รายงานเป็น error ทุกครั้งที่โหลดหน้า
    """
    from pathlib import Path

    tdir = Path(__file__).resolve().parents[1] / "redbook" / "templates"
    offenders = [p.name for p in sorted(tdir.glob("t1b_*.html"))
                 if 'style="' in p.read_text(encoding="utf-8")]
    assert offenders == [], f"เทมเพลต T1B มี inline style ที่ CSP บล็อก: {offenders}"


def _disallowed_scripts(html: str) -> list[str]:
    """แท็ก ``<script>`` ที่ CSP ``script-src 'self'`` ไม่ยอม — inline (ไม่มี src) หรือ src นอกระบบ

    อนุญาตเฉพาะ ``src="/static/…"`` (ไฟล์จากเซิร์ฟเวอร์เดียวกัน)
    """
    out = []
    for tag in re.findall(r"<script\b[^>]*>", html, re.I):
        m = re.search(r"""\bsrc\s*=\s*["']([^"']*)["']""", tag, re.I)
        if not m or not m.group(1).startswith("/static/"):
            out.append(tag)
    return out


@pytest.mark.parametrize("html, flagged", [
    ('<script>alert(1)</script>', True),                                   # inline
    ('<script type="module">import x from "/static/a.js"</script>', True),  # inline module
    ('<SCRIPT>alert(1)</SCRIPT>', True),                                   # ตัวพิมพ์ใหญ่
    ('<script src="https://cdn.example.com/x.js"></script>', True),        # ภายนอก
    ('<script src="//cdn.example.com/x.js"></script>', True),              # ภายนอกไม่ระบุ scheme
    ('<script src="/static/verify.js" defer></script>', False),            # ไฟล์ระบบเดียวกัน
])
def test_w43b_script_rule_still_catches_inline_and_external(html, flagged):
    """Bo 8 ต.ค.: ผ่อนให้ไฟล์ JS ของระบบได้ — แต่ inline และสคริปต์ภายนอกต้องยังถูกจับ"""
    assert bool(_disallowed_scripts(html)) is flagged


def test_w43_t1b_pages_report_no_csp_violating_markup(client, healthy_run):
    """ตรวจที่ผลลัพธ์จริงด้วย ไม่ใช่แค่ที่ซอร์สของเทมเพลต"""
    urls = ["/t1b/runs", "/t1b/runs/WEB-OK", "/t1b/runs/WEB-OK/queue",
            f"/t1b/runs/WEB-OK/findings/{healthy_run.findings[0].finding_id}"]
    for url in urls:
        body = client.get(url).text
        after_header = body.split("</header>", 1)[-1]
        assert 'style="' not in after_header, f"{url} มี inline style"
        # CSP = script-src 'self' ⇒ ห้าม inline script · ไฟล์สคริปต์จากโดเมนเดียวกัน (src="/static/…") ใช้ได้
        # (#24 PDF-first: verify.js วางจุดชี้บนภาพ PDF + เปิดหลักฐานแบบหน้าต่างซ้อน — ปรับเทสต์ให้ตรงเจตนาเดิม
        #  "inline script" แทนการห้ามแท็ก <script ทุกแบบ · แจ้ง Bo ใน handoff)
        bad = _disallowed_scripts(after_header)
        assert not bad, f"{url} มี inline script หรือสคริปต์จากภายนอก: {bad}"
