# -*- coding: utf-8 -*-
"""เส้นทางสาธิตครบหนึ่งรอบ — อัปโหลด → วิเคราะห์ → ตัดสิน → Preflight → ส่งออก

ชุดนี้เดินเส้นทางเดียวกับที่ผู้ใช้กดบนหน้าจอทุกขั้น ผ่าน HTTP จริง
(ไม่มีการลัดเข้าไปเรียกชั้นบริการโดยตรง) จึงเป็น smoke test ของทั้งเส้น

🔴 **SYNTHETIC DEMONSTRATION DATA** — คู่สมุดงานที่ใช้มาจาก
``scripts/demo_ao_workbooks.py`` ซึ่งแต่งขึ้นทั้งหมด ไม่มีข้อมูลจากเอกสารจริง
ห้ามรายงานผลจากชุดนี้ว่าเป็นข้อผิดพลาดที่พบในเอกสารราชการ

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import demo_ao_workbooks as gen  # noqa: E402

from redbook.app import create_app  # noqa: E402
from redbook.services import decisions as dec  # noqa: E402
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    return gen.build(tmp_path_factory.mktemp("demo_pair"))


def _token(client):
    client.get("/")
    return client.cookies.get(CSRF_COOKIE)


def test_the_demo_pair_is_readable_and_clearly_marked_synthetic(pair):
    a, b = pair
    assert a.exists() and b.exists()
    assert a.suffix == ".xlsx" and b.suffix == ".xlsx"
    # ชื่อไฟล์ต้องอ่านออกเองว่าเป็นของสาธิต ไม่ใช่เอกสารจริง
    assert "DEMO_SYNTHETIC" in a.name and "DEMO_SYNTHETIC" in b.name


def test_full_walkthrough_upload_to_export(client, pair):
    a, b = pair
    token = _token(client)

    # ── ขั้น 1 ตั้งงานตรวจ ────────────────────────────────────────────────
    r = client.post("/projects/new", follow_redirects=False, data={
        CSRF_FIELD: token, "name": "งานสาธิตในชุดทดสอบ",
        "mode": "before_after_reduction", "note": "ข้อมูลสังเคราะห์"})
    assert r.status_code == 303
    pid = r.headers["location"].rsplit("/", 1)[-1]

    # ── ขั้น 2 ใส่ไฟล์สองฉบับ ─────────────────────────────────────────────
    for side, path in (("A", a), ("B", b)):
        with open(path, "rb") as fh:
            up = client.post(f"/projects/{pid}/upload", follow_redirects=False,
                             data={CSRF_FIELD: token, "side": side},
                             files={"upload": (path.name, fh)})
        assert up.status_code == 303, side

    detail = client.get(f"/projects/{pid}").text
    assert "ให้ระบบหาความต่าง" in detail, "แถบขั้นตอนต้องอยู่บนหน้างานตรวจ"

    # ── ขั้น 3 ให้ระบบหาความต่าง ──────────────────────────────────────────
    run = client.post(f"/projects/{pid}/analyze", follow_redirects=False,
                      data={CSRF_FIELD: token})
    assert run.status_code == 303
    rid = run.headers["location"].rsplit("/", 1)[-1]

    summary = client.get(f"/t1b/runs/{rid}").text
    assert "ยืนยันหน่วยงานเดียวกัน" in summary or "หน่วยงานเดียวกัน" in summary

    # ── ขั้น 4 พิจารณาทีละรายการ ─────────────────────────────────────────
    blocked = client.post(f"/t1b/runs/{rid}/export", data={CSRF_FIELD: token})
    assert blocked.status_code == 409, "ยังตัดสินไม่ครบ ต้องส่งออกไม่ได้"

    from redbook.services import t1b as svc
    view = svc.load_run(rid)
    for f in view.findings:
        d = client.post(f"/t1b/runs/{rid}/findings/{f.finding_id}/decide",
                        follow_redirects=False,
                        data={CSRF_FIELD: token, "status": dec.CONFIRMED,
                              "expected_latest_seq": 0})
        assert d.status_code == 303, f.finding_id

    # ── ขั้น 5 ตรวจก่อนส่งออก ────────────────────────────────────────────
    pre = client.get(f"/t1b/runs/{rid}/preflight").text
    assert "ยังส่งออกไม่ได้" in pre, "ยังเหลือด่านรับทราบรายการที่อ่านไม่ครบ"
    scope = re.search(r'name="scope" value="([0-9a-f]+)"', pre).group(1)
    ack = client.post(f"/t1b/runs/{rid}/preflight/ack", follow_redirects=False,
                      data={CSRF_FIELD: token, "scope": scope,
                            "reviewer": "ผู้ตรวจสาธิต"})
    assert ack.status_code == 303
    assert "ผ่านทุกเงื่อนไขแล้ว" in client.get(f"/t1b/runs/{rid}/preflight").text

    # ── ขั้น 6 ส่งออกชุดงาน ──────────────────────────────────────────────
    out = client.post(f"/t1b/runs/{rid}/export", data={CSRF_FIELD: token})
    assert out.status_code == 200 and "exp_" in out.text

    # ── กลับมาที่แดชบอร์ดแล้วเปิดรอบเดิมได้ ───────────────────────────────
    home = client.get("/").text
    assert rid in home and f"/t1b/runs/{rid}" in home


def test_demo_pair_produces_the_kinds_of_findings_a_reviewer_must_judge(pair):
    """คู่ไฟล์สาธิตต้องครอบคลุมชนิดข้อสังเกตที่ผู้ตรวจต้องตัดสินจริง

    ถ้าคู่ไฟล์สาธิตมีแต่ข้อสังเกตชนิดเดียว หน้าจอสาธิตจะดูง่ายกว่าความจริง
    """
    from redbook.services import t1b as svc

    a, b = pair
    view = svc.run_from_workbooks(a, b, run_id="DEMO-KINDS")
    kinds = {f.finding_type for f in view.findings}
    for needed in ("AMOUNT_INCREASED", "AMOUNT_DECREASED", "ROW_ADDED",
                   "ROW_REMOVED", "UNIT_CHANGED", "INDICATOR_CHANGED",
                   "UNMAPPED_REQUIRES_HUMAN_REVIEW"):
        assert needed in kinds, needed
    assert view.summary.identity_verdict == "COMPARED"
    assert view.reconciliation.balanced
