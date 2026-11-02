# -*- coding: utf-8 -*-
"""JSON API + หน้าบ้าน Svelte ของ "ทดลองตรวจเล่ม" (``/api/trial`` · ``/r/``)

🔴 SYNTHETIC DEMONSTRATION DATA — ใช้ fixture ชั้นเล่มสังเคราะห์ชุดเดียวกับ ``test_trial.py``

* ทุกคำขอที่เปลี่ยนสถานะต้องมีโทเคนในหัว ``X-CSRF-Token`` (double-submit เดิม)
* เดินครบเส้นทางผ่าน JSON: เริ่ม → วง → ตรวจครบ → ส่ง → ยืนยันคู่ → แบบสอบถาม — กติกาเดียวกับหน้าเดิม
* หน้าบ้านที่ build แล้ว: ไม่มีสคริปต์/สไตล์ฝังในหน้า · โหลดเฉพาะไฟล์จากเครื่อง · ทุกเส้นทาง /r/ ได้ index.html
"""
import re

import pytest

from test_trial import AG, PROJECT_ROOT, _env, client, shelf  # noqa: F401  (fixture ร่วม)
from redbook.services import trial
from redbook.web.security import CSRF_COOKIE

APP = PROJECT_ROOT / "redbook" / "static" / "app"


def _hdr(client):
    return {"X-CSRF-Token": client.get("/api/csrf").json()["token"]}


def test_state_changes_need_csrf_header(client):
    assert client.post("/api/trial/start", json={"book_id": "t1"}).status_code in (400, 403)
    assert client.post("/api/trial/start", json={"book_id": "t1"},
                       headers={"X-CSRF-Token": "wrong"}).status_code in (400, 403)
    tok = client.get("/api/csrf").json()["token"]
    assert tok and tok == client.cookies.get(CSRF_COOKIE)


def test_full_review_flow_over_json(client):
    h = _hdr(client)
    meta = client.get("/api/trial/meta").json()
    assert set(meta["pens"]) == {"red", "brown", "pin"} and len(meta["topics"]) == 10
    books = client.get("/api/trial/books").json()["books"]
    assert [b["id"] for b in books] == ["t1"]
    sid = client.post("/api/trial/start", json={"book_id": "t1", "again": True, "reviewer": "J1"}, headers=h).json()["sid"]
    s = client.get(f"/api/trial/s/{sid}").json()
    assert not s["locked"] and s["pages"]["cur"] and s["pages"]["prev"] and s["marks"] == []
    pre = client.get(f"/api/trial/s/{sid}/result")
    assert pre.status_code == 409 and pre.json()["code"] == "not_locked"         # ยังไม่ส่ง = ยังไม่มีผลระบบ
    assert trial.session(sid).rec["run_id"] == ""                                 # ขอผลก่อนล็อกไม่สร้างรอบเทียบ
    gone = client.get("/api/trial/s/tr_nope")
    assert gone.status_code == 404 and gone.json()["code"] == "not_found"
    p0 = s["pages"]["cur"][0]
    bad = client.post(f"/api/trial/s/{sid}/marks", json={"side": "cur", "page": p0, "fx": 3, "fy": .5, "pen": "red"}, headers=h)
    assert bad.status_code == 400 and bad.json()["code"] == "invalid" and "Traceback" not in bad.text
    m = client.post(f"/api/trial/s/{sid}/marks", json={"side": "cur", "page": p0, "fx": .5, "fy": .4, "pen": "red"},
                    headers=h).json()
    assert client.post(f"/api/trial/s/{sid}/marks/{m['id']}", json={"topic": "ช", "note": "ตัวชี้วัดหาย"},
                       headers=h).json()["ok"]
    assert client.post(f"/api/trial/s/{sid}/view", json={"cur": p0, "prev": s["pages"]["prev"][0]}, headers=h).json()["ok"]
    assert client.post(f"/api/trial/s/{sid}/lock", json={"confirm": True}, headers=h).status_code == 400  # ยังไม่ครบหน้า
    for p in s["pages"]["cur"]:
        assert client.post(f"/api/trial/s/{sid}/done", json={"page": p}, headers=h).json()["ok"]
    # กด "ตรวจหน้านี้แล้ว" พลาด → ยกเลิกได้ก่อนส่ง · ยกเลิกซ้ำไม่ error · แล้วส่งไม่ได้จนกดใหม่
    u = client.post(f"/api/trial/s/{sid}/undone", json={"page": p0}, headers=h).json()
    assert u == {"ok": True, "undone": True} and p0 not in client.get(f"/api/trial/s/{sid}").json()["done"]
    assert client.post(f"/api/trial/s/{sid}/undone", json={"page": p0}, headers=h).json()["undone"] is False
    assert client.post(f"/api/trial/s/{sid}/lock", json={"confirm": True}, headers=h).status_code == 400
    assert client.post(f"/api/trial/s/{sid}/done", json={"page": p0}, headers=h).json()["ok"]
    assert client.post(f"/api/trial/s/{sid}/lock", json={}, headers=h).status_code == 400              # ไม่ยืนยัน
    assert client.post(f"/api/trial/s/{sid}/lock", json={"confirm": True}, headers=h).json()["ok"]
    late = client.post(f"/api/trial/s/{sid}/marks", json={"side": "cur", "page": p0, "fx": .5, "fy": .5, "pen": "red"},
                       headers=h)
    assert late.status_code == 409 and late.json()["code"] == "locked"                                 # ล็อกแล้ว
    assert client.post(f"/api/trial/s/{sid}/undone", json={"page": p0}, headers=h).json()["code"] == "locked"
    r = client.get(f"/api/trial/s/{sid}/result").json()
    assert r["session"]["locked"] and len(r["marks"]) == 1 and r["marks"][0]["topic"] == "ช"
    for f in r["extras"] + [c for m_ in r["marks"] for c in m_["candidates"]]:
        assert {"kind_code", "info", "caveats", "parts", "tolerance_text"} <= set(f)    # คำเตือนไปถึงหน้าผล
    assert r["metrics"]["pens"]["red"]["total"] == 1
    r2 = client.post(f"/api/trial/s/{sid}/link/{m['id']}", json={"verdict": "not_same"}, headers=h).json()
    assert r2["marks"][0]["verdict"] == "not_same" and r2["metrics"]["pens"]["red"]["missed"] == 1
    if r2["extras"]:
        fid = r2["extras"][0]["id"]
        r3 = client.post(f"/api/trial/s/{sid}/extra/{fid}", json={"verdict": "not_diff"}, headers=h).json()
        assert r3["metrics"]["extras"]["not_diff"] == 1
    a = client.post(f"/api/trial/s/{sid}/survey", json={"q1_1": "4", "o6_3": "ลื่นดี"}, headers=h).json()
    assert a["answers"]["q1_1"] == "4"
    assert client.post(f"/api/trial/s/{sid}/survey", json={"q1_1": "7"}, headers=h).status_code == 400
    assert trial.session(sid).locked


@pytest.mark.skipif(not (APP / "index.html").exists(), reason="ยังไม่ได้ build หน้าบ้าน (npm run build)")
def test_built_frontend_is_csp_clean_and_served(client):
    html = (APP / "index.html").read_text(encoding="utf-8")
    for tag in re.findall(r"<script[^>]*>", html):
        assert "src=" in tag                                          # ไม่มีสคริปต์ฝังในหน้า
    assert "<style" not in html and " style=" not in html            # ไม่มีสไตล์ฝังในหน้า
    assert not re.search(r"(src|href)=\"(https?:)?//", html)          # ไม่โหลดจากเครื่องอื่น
    for path in ("/r", "/r/s/tr_x", "/r/s/tr_x/result", "/r/p", "/r/p/new", "/r/p/pp_x", "/r/p/pp_x/f/abc123", "/r/p/pp_x/preflight", "/r/p/pp_x/audit"):
        r = client.get(path)
        assert r.status_code == 200 and "/static/app/assets/" in r.text
    js = next((APP / "assets").glob("*.js")).read_text(encoding="utf-8")
    assert "eval(" not in js and "new Function(" not in js


def test_api_routes_go_through_service_layer():
    src = (PROJECT_ROOT / "redbook" / "web" / "api_trial.py").read_text(encoding="utf-8")
    assert "from ..pdfbook" not in src and "trial_repo.add_mark" not in src and "trial_repo.lock" not in src
