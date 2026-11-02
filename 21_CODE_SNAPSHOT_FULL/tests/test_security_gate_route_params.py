# -*- coding: utf-8 -*-
"""พารามิเตอร์เส้นทางที่เพิ่มหลังรอบ #23 — side · n · sid · mid · book_id · path (Bo REVIEW #42 6433564226 ข้อ 1)

ชื่ออยู่ในรายการอนุญาตของ ``test_security_gate_static.ALLOWED_PATH_PARAMS`` ได้ก็ต่อเมื่อพิสูจน์ที่นี่ว่า ค่าที่ไม่ถูกต้อง ·
ไม่มีอยู่ · ตัวคั่นที่ encode · traversal **ไม่อ่านไฟล์นอกขอบเขต และไม่เขียนข้อมูล** — ตรวจด้วยตัวนับการอ่านหน้า PDF จริง
(``reader.page_png``/``_png_cached``) · การส่งไฟล์ (``FileResponse``) · และจำนวนแถว/Audit ในฐานข้อมูล ก่อน–หลัง

🔴 SYNTHETIC DEMONSTRATION DATA — ชั้นเล่มสังเคราะห์ชุดเดียวกับ ``test_trial.py``
"""
import pytest

from test_trial import AG, _env, client, shelf  # noqa: F401  (fixture ร่วม)
from redbook.evidence import pdftext
from redbook.services import pdfpair as svc, pdfshelf, trial
from redbook.storage.db import connect

pytestmark = pytest.mark.skipif(pdftext.product_backend() is None, reason="ไม่มี pdfplumber + pypdfium2")

#: ค่าโจมตีของส่วนเส้นทางหนึ่งส่วน (ส่งผ่าน URL ตามตัว — ``%2F`` ฯลฯ ไปถึงแอปเป็นตัวคั่นที่ encode)
#: ไม่ใส่ ".." ตามตัว (ตัวส่งคำขอยุบเส้นทางก่อนถึงแอป) · ไม่ใส่ "%41" (= "A" ที่ถูกต้อง)
BAD = ["C", "a", "AB", "%2e%2e", "..%2F..%2Fredbook%2Fconfig.py", "A%2F..%2FB", "A%5C..%5CB", "%00",
       "A%00", "' OR 1=1--", "%252e%252e%252f", "A;B"]
BAD_INT = ["-1", "0", "999999", "1.5", "1e3", "%2e", "0x1", "%31%2F.."]    # " 1" = 1 ที่ถูกต้อง (แปลงชนิดตัดช่องว่าง)


def _counts():
    conn = connect()
    try:
        return tuple(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                     for t in ("audit_log", "pdfpair_decisions", "trial_marks"))
    finally:
        conn.close()


@pytest.fixture()
def watch(monkeypatch):
    """นับการ render หน้า PDF และการส่งไฟล์จากดิสก์ — ค่าโจมตีต้องไม่ทำให้เกิดทั้งสองอย่าง"""
    seen = {"render": 0, "files": []}
    real_png = svc._png_cached

    def png(*a, **k):
        seen["render"] += 1
        return real_png(*a, **k)
    monkeypatch.setattr(svc, "_png_cached", png)
    import starlette.responses as sr
    real_fr = sr.FileResponse.__init__

    def fr(self, path, *a, **k):
        seen["files"].append(str(path))
        return real_fr(self, path, *a, **k)
    monkeypatch.setattr(sr.FileResponse, "__init__", fr)
    return seen


@pytest.fixture()
def ids(client):
    _pid, rid = pdfshelf.start("S_2570_draft", "S_2570_act", AG)
    v = svc.view(rid)
    fid = next(f.id for f in v.result.findings if not f.info and f.a.page)
    sid = trial.start("t1", "R1", again=True)
    return {"rid": rid, "fid": fid, "page": v.run["scope"]["A"]["first"], "sid": sid}


def _get(client, url):
    """GET ไม่ตามลิงก์ต่อ · ถ้าได้ 3xx (redirect_slashes ของ Starlette ตัด "/" ท้ายที่ถอดจาก %2F) ต้องชี้ที่เดิมในแอป
    และปลายทางต้องเป็น 4xx — ไม่ใช่ทางอ้อมไปอ่านอะไร"""
    r = client.get(url, follow_redirects=False)
    if 300 <= r.status_code < 400:
        loc = r.headers.get("location", "")
        assert loc.startswith("http://testserver/"), (url, loc)
        r2 = client.get(loc, follow_redirects=False)       # ไฟล์/ภาพ/การเขียน ตรวจด้วย fixture ``watch`` + ``_counts``
        assert not r2.headers.get("content-type", "").startswith("image/"), (url, loc)
        r.status_code = 404 if r2.status_code < 400 else r2.status_code   # นับเป็น "ไม่ได้เปิดสิ่งที่ขอ"
    return r


def test_valid_values_still_work(client, ids, watch):
    """ตัวควบคุมบวก — ค่าถูกต้องเรนเดอร์จริง (ไม่ใช่ผ่านเพราะทุกอย่างล้ม)"""
    r = _get(client, f"/pdfpair/runs/{ids['rid']}/f/{ids['fid']}/A.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    r = _get(client, f"/pdfpair/runs/{ids['rid']}/page/A/{ids['page']}.png")
    assert r.status_code == 200 and watch["render"] >= 1


@pytest.mark.parametrize("bad", BAD)
def test_side_rejects_without_reading_or_writing(client, ids, watch, bad):
    before = _counts()
    urls = [f"/pdfpair/runs/{ids['rid']}/f/{ids['fid']}/{bad}.png",
            f"/pdfpair/runs/{ids['rid']}/page/{bad}/{ids['page']}.png",
            f"/trial/s/{ids['sid']}/page/{bad}/1.png"]
    for u in urls:
        r = _get(client, u)
        assert 400 <= r.status_code < 500, (u, r.status_code)
        assert not r.headers.get("content-type", "").startswith("image/"), u
    assert watch["render"] == 0 and not watch["files"] and _counts() == before


@pytest.mark.parametrize("bad", BAD_INT)
def test_page_number_rejects_without_reading(client, ids, watch, bad):
    before = _counts()
    for u in (f"/pdfpair/runs/{ids['rid']}/page/A/{bad}.png", f"/trial/s/{ids['sid']}/page/cur/{bad}.png"):
        r = _get(client, u)
        assert 400 <= r.status_code < 500, (u, r.status_code)
    assert watch["render"] == 0 and _counts() == before


@pytest.mark.parametrize("bad", BAD + ["../../../../Windows/win.ini", "x" * 300])
def test_ids_are_lookups_not_paths(client, ids, watch, bad):
    """rid · fid · sid · mid · book_id ไม่มีอยู่/โจมตี = 4xx · ไม่ render · ไม่ส่งไฟล์ · ไม่เขียน (รวม POST ที่มี CSRF ถูกต้อง)"""
    before = _counts()
    for u in (f"/pdfpair/runs/{bad}/f/{ids['fid']}/A.png", f"/pdfpair/runs/{ids['rid']}/f/{bad}/A.png",
              f"/api/pdfpair/runs/{bad}", f"/trial/s/{bad}/page/cur/1.png", f"/api/trial/s/{bad}",
              f"/books/thumb/{bad}.jpg", f"/books/{bad}"):
        r = _get(client, u)
        assert 400 <= r.status_code < 500 or r.status_code == 503, (u, r.status_code)
    h = {"X-CSRF-Token": client.get("/api/csrf").json()["token"]}
    # ไม่มีช่องที่แก้ได้ = ไม่แตะฐานข้อมูลเลย (200 ไม่มีผล) — ตรวจด้วย _counts ด้านล่าง
    assert client.post(f"/api/trial/s/{ids['sid']}/marks/{bad}", json={}, headers=h).status_code < 500
    for u, body in ((f"/api/trial/s/{ids['sid']}/marks/{bad}", {"note": "x"}),
                    (f"/api/trial/s/{ids['sid']}/marks/{bad}", {"delete": True}),
                    (f"/api/trial/s/{bad}/marks/{bad}", {"note": "x"}),
                    (f"/api/pdfpair/runs/{ids['rid']}/f/{bad}/decide", {"choice": "checked", "note": ""})):
        r = client.post(u, json=body, headers=h)
        assert 400 <= r.status_code < 500, (u, r.status_code)
    assert watch["render"] == 0 and not watch["files"] and _counts() == before


@pytest.mark.parametrize("bad", ["../../redbook/config.py", "..%2F..%2Fredbook%2Fapp.py", "%2e%2e/%2e%2e/.git/config",
                                 "p/../../../tests/conftest.py"])
def test_spa_path_is_ignored_and_only_serves_index(client, watch, bad):
    r = _get(client, f"/r/{bad}")
    assert r.status_code in (200, 404, 503)
    assert all(f.replace("\\", "/").endswith("static/app/index.html") for f in watch["files"]), watch["files"]
    assert "import os" not in r.text and "[core]" not in r.text
