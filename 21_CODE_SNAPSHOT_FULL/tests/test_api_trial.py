# -*- coding: utf-8 -*-
"""JSON API + หน้าบ้าน Svelte ของ "ทดลองตรวจเล่ม" (``/api/trial`` · ``/r/``) — วิธีวัดผลฉบับ 0.2

🔴 SYNTHETIC DEMONSTRATION DATA — ใช้ fixture ชั้นเล่มสังเคราะห์ชุดเดียวกับ ``test_trial.py``

* ทุกคำขอที่เปลี่ยนสถานะต้องมีโทเคนในหัว ``X-CSRF-Token`` (double-submit เดิม)
* เดินครบเส้นทางผ่าน JSON: เริ่ม → วง (ร2) → ใบประกาศ (ล็อก) → จับคู่ → จัดกลุ่ม → จบการใช้ผล → แบบสอบถาม
  — กติกาเดียวกับหน้าเดิม · ป้ายทุกชุดมาจาก ``/api/trial/meta``
* หน้าบ้านที่ build แล้ว: ไม่มีสคริปต์/สไตล์ฝังในหน้า · โหลดเฉพาะไฟล์จากเครื่อง · ทุกเส้นทาง /r/ ได้ index.html
"""
import re

import pytest

from test_trial import AG, CONSENT, PROJECT_ROOT, _env, client, decl, shelf  # noqa: F401  (fixture ร่วม)
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


def test_meta_carries_every_code_and_label_of_protocol_0_2(client):
    meta = client.get("/api/trial/meta").json()
    assert set(meta["pens"]) == {"red", "brown", "pin"} and len(meta["topics"]) == 10 and len(meta["parts"]) == 8
    assert set(meta["verdicts"]) == {"exact", "partial", "missed", "undecidable"}
    assert list(meta["partial_reasons"]) == ["b1", "b2", "b3", "b4"]
    assert list(meta["miss_reasons"]) == ["p1", "p2", "p3", "p4", "p5"]
    assert list(meta["groups"]) == ["s1", "s2", "s3", "s4", "outside"] and set(meta["paths"]) == {"r1", "r2"}
    assert [i["key"] for g in meta["likert"] for i in g["items"]] == [f"q2_{i}" for i in range(1, 14)]
    assert len(meta["steps"]) == 6 and len(meta["open"]) == 4 and len(meta["consent"]) == 3
    assert meta["versions"]["trial"] == "trial-0.3.0" and "0.3" in meta["versions"]["protocol"]
    assert meta["level_definition"] and set(meta["finding_levels"]) == {"must", "info", "unread", "descriptive", "review"}
    labels = " ".join(str(v) for k in ("miss_reasons", "s3_reasons", "groups", "verdicts") for v in meta[k].values())
    assert "ผิด" not in labels                                               # ป้ายของระบบไม่ใช้คำว่า "ผิด"


def test_full_review_flow_over_json(client):
    h = _hdr(client)
    books = client.get("/api/trial/books").json()["books"]
    assert [b["id"] for b in books] == ["t1"] and books[0]["pair_kind"] == "same_year"
    sid = client.post("/api/trial/start", json={"book_id": "t1", "again": True, "reviewer": "J1", "path": "r2"},
                      headers=h).json()["sid"]
    s = client.get(f"/api/trial/s/{sid}").json()
    assert not s["consented"]
    early = client.post(f"/api/trial/s/{sid}/marks", json={"side": "cur", "page": s["pages"]["cur"][0], "fx": .5,
                                                            "fy": .5, "pen": "red"}, headers=h)
    assert early.status_code == 400 and "ความยินยอม" in early.json()["error"]         # ยินยอมก่อนเริ่มกิจกรรม
    s = client.post(f"/api/trial/s/{sid}/consent", json={"c1": True, "c2": True, "c3": True}, headers=h).json()
    assert s["consented"] and not s["locked"] and s["path"] == "r2" and s["labels"] == {"prev": "ฉบับ A", "cur": "ฉบับ B"}
    assert s["marks"] == [] and s["done"] == {"cur": [], "prev": []} and s["defaults"]["source"] == "web"
    pre = client.get(f"/api/trial/s/{sid}/result")
    assert pre.status_code == 409 and pre.json()["code"] == "not_locked"         # ยังไม่ส่ง = ยังไม่มีผลระบบ
    assert trial.session(sid).rec["run_id"] == ""                                 # ขอผลก่อนล็อกไม่สร้างรอบเทียบ
    gone = client.get("/api/trial/s/tr_nope")
    assert gone.status_code == 404 and gone.json()["code"] == "not_found"
    p0, q0 = s["pages"]["cur"][0], s["pages"]["prev"][0]
    bad = client.post(f"/api/trial/s/{sid}/marks", json={"side": "cur", "page": p0, "fx": 3, "fy": .5, "pen": "red"}, headers=h)
    assert bad.status_code == 400 and bad.json()["code"] == "invalid" and "Traceback" not in bad.text
    m = client.post(f"/api/trial/s/{sid}/marks", json={"side": "prev", "page": q0, "fx": .5, "fy": .4, "pen": "pin"},
                    headers=h).json()
    assert m["side"] == "prev" and m["found_in"] == "prev"                       # หมุดของที่หายวางในฉบับ A ได้
    lk = client.post(f"/api/trial/s/{sid}/lock", json={**decl("r2"), "confirm": True}, headers=h)
    assert lk.status_code == 400 and "ไม่ครบ 1 จุด" in lk.json()["error"]
    assert client.get(f"/api/trial/s/{sid}").json()["gaps"][m["id"]]
    assert client.post(f"/api/trial/s/{sid}/marks/{m['id']}", json={"topic": "ค", "part": "๗", "cause": "t",
                                                                     "level": "brown", "searched": "ส่วน ๗"},
                       headers=h).json()["ok"]
    assert client.post(f"/api/trial/s/{sid}/view", json={"cur": p0, "prev": q0}, headers=h).json()["ok"]
    # "ตรวจหน้านี้แล้ว" เป็นตัวช่วย (ทั้งสองฉบับ) ยกเลิกได้ก่อนส่ง — ไม่ใช่เงื่อนไขการส่ง
    assert client.post(f"/api/trial/s/{sid}/done", json={"page": q0, "side": "prev"}, headers=h).json()["ok"]
    u = client.post(f"/api/trial/s/{sid}/undone", json={"page": q0, "side": "prev"}, headers=h).json()
    assert u == {"ok": True, "undone": True}
    assert client.post(f"/api/trial/s/{sid}/undone", json={"page": q0, "side": "prev"}, headers=h).json()["undone"] is False
    assert client.post(f"/api/trial/s/{sid}/lock", json={**decl("r2"), "confirm": False}, headers=h).status_code == 400
    ok = client.post(f"/api/trial/s/{sid}/lock", json={**decl("r2"), "confirm": True}, headers=h).json()
    assert ok == {"ok": True, "run": True, "run_error": ""}
    late = client.post(f"/api/trial/s/{sid}/marks", json={"side": "cur", "page": p0, "fx": .5, "fy": .5, "pen": "red"},
                       headers=h)
    assert late.status_code == 409 and late.json()["code"] == "locked"
    assert client.post(f"/api/trial/s/{sid}/undone", json={"page": p0}, headers=h).json()["code"] == "locked"
    r = client.get(f"/api/trial/s/{sid}/result").json()
    assert not r["legacy"] and r["session"]["locked"] and len(r["issues"]) == 1 and r["issues"][0]["topic"] == "ค"
    assert r["declaration"]["parts"]["๗"] == "full" and r["status"]["run"] == "ok"
    for f in r["findings"].values():
        assert {"kind_code", "info", "caveats", "parts", "tolerance_text", "level"} <= set(f)   # คำเตือนไปถึงหน้าผล
    assert set(r["metrics"]) >= {"A1", "A2", "A3", "A4", "B1_basis"}
    issue = r["issues"][0]
    bad = client.post(f"/api/trial/s/{sid}/issue/{issue['id']}", json={"verdict": "missed", "basis": "opened"}, headers=h)
    assert bad.status_code == 400 and "พ1–พ5" in bad.json()["error"]
    r2 = client.post(f"/api/trial/s/{sid}/issue/{issue['id']}", json={"verdict": "missed", "reason": "p3",
                                                                       "basis": "opened"}, headers=h).json()
    assert r2["issues"][0]["decision"]["verdict"] == "missed" and r2["metrics"]["A1"]["missed"] == 1
    fid = r2["unmatched"][0]["id"]
    assert r2["metrics"]["A1"]["N0"] == 1
    r3 = client.post(f"/api/trial/s/{sid}/finding/{fid}", json={"group": "s3", "s3_reason": "rounding",
                                                                "basis": "opened"}, headers=h).json()
    assert r3["metrics"]["A3"]["s3"] == 1 and next(u for u in r3["unmatched"] if u["id"] == fid)["group"]["grp"] == "s3"
    # 0.3: A3-อ/A3-ข ผ่าน JSON · ข้อนอก U ประเมินไม่ได้ · มิติ N/A ต้องมีเหตุ
    assert r3["session"]["v03"] and fid in r3["u_ids"] and r3["findings"][fid]["obs_kind"]
    dims = {d: "ok" for d in client.get("/api/trial/meta").json()["dims_by_obs_kind"][r3["findings"][fid]["obs_kind"]]}
    bad = client.post(f"/api/trial/s/{sid}/obs/{fid}", json={"fidelity": "full", "basis": "opened",
                                                            "dims": {**dims, "real": "na"}}, headers=h)
    assert bad.status_code == 400 and "N/A" in bad.json()["error"]
    r4 = client.post(f"/api/trial/s/{sid}/obs/{fid}", json={"fidelity": "none", "fidelity_reason": "rounding",
                                                           "basis": "opened", "dims": {**dims, "real": "wrong"}},
                     headers=h).json()
    assert r4["obs_eval"][fid]["assertion"] == "none" and r4["obs_eval"][fid]["fidelity"] == "none"
    assert r4["metrics"]["v03"]["counts"]["obs"]["crosstab"]["none"]["none"] == 1
    assert client.post(f"/api/trial/s/{sid}/survey", json={"c1": True, "c2": True, "c3": True, "q2_1": "4"},
                       headers=h).status_code == 400                             # ยังไม่จบการใช้ผล
    assert client.post(f"/api/trial/s/{sid}/finish", json={}, headers=h).status_code == 400
    fin = client.post(f"/api/trial/s/{sid}/finish", json={"reason": "ทดสอบ API"}, headers=h).json()
    assert fin["survey_state"] == "open"
    a = client.post(f"/api/trial/s/{sid}/survey", json={"c1": True, "c2": True, "c3": True, "q2_1": "4",
                                                        "k3": "self", "o3_1": "ลื่นดี"}, headers=h).json()
    assert a["answers"]["q2_1"] == "4" and a["answers"]["k3"] == "self"
    assert client.post(f"/api/trial/s/{sid}/survey", json={"c1": True, "c2": True, "c3": True, "q2_1": "7"},
                       headers=h).status_code == 400
    st = client.post(f"/api/trial/s/{sid}/status", json={"status": "withdrawn"}, headers=h)
    assert st.status_code == 400                                                 # ต้องยืนยัน
    assert client.post(f"/api/trial/s/{sid}/status", json={"status": "withdrawn", "confirm": True},
                       headers=h).json()["status"] == "withdrawn"
    assert client.post(f"/api/trial/s/{sid}/note", json={"note": "x"}, headers=h).json()["code"] == "locked"


def test_r1_rows_over_json(client):
    h = _hdr(client)
    sid = client.post("/api/trial/start", json={"book_id": "t1", "again": True, "path": "r1"}, headers=h).json()["sid"]
    client.post(f"/api/trial/s/{sid}/consent", json=CONSENT, headers=h)
    assert client.post(f"/api/trial/s/{sid}/marks", json={"side": "cur", "page": 3, "fx": .5, "fy": .5, "pen": "red"},
                       headers=h).status_code == 400                             # ทาง ร1 ไม่วงจุด
    assert client.post(f"/api/trial/s/{sid}/lock", json={**decl("r1"), "t_ก_total": 2, "confirm": True},
                       headers=h).json()["run"]
    r = client.get(f"/api/trial/s/{sid}/result").json()
    assert [(i["topic"], i["seq"], i["origin"]) for i in r["issues"]] == [("ก", 1, "row"), ("ก", 2, "row"), ("ช", 1, "row")]
    row = r["issues"][0]
    assert "ส่วนของเล่ม" in row["gaps"]
    r = client.post(f"/api/trial/s/{sid}/row/{row['id']}", json={"part": "๗", "cause": "t", "level": "red",
                                                                  "ref": "3", "row_source": "transcribed"},
                    headers=h).json()
    assert r["issues"][0]["part"] == "๗" and "ส่วนของเล่ม" not in r["issues"][0]["gaps"]
    assert r["issues"][0]["row_source"] == "transcribed" and "ที่มาของลักษณะแถว" not in r["issues"][0]["gaps"]


@pytest.mark.skipif(not (APP / "index.html").exists(), reason="ยังไม่ได้ build หน้าบ้าน (npm run build)")
def test_built_frontend_is_csp_clean_and_served(client):
    html = (APP / "index.html").read_text(encoding="utf-8")
    for tag in re.findall(r"<script[^>]*>", html):
        assert "src=" in tag                                          # ไม่มีสคริปต์ฝังในหน้า
    assert "<style" not in html and " style=" not in html            # ไม่มีสไตล์ฝังในหน้า
    assert not re.search(r"(src|href)=\"(https?:)?//", html)          # ไม่โหลดจากเครื่องอื่น
    for path in ("/r", "/r/s/tr_x", "/r/s/tr_x/result"):
        r = client.get(path)
        assert r.status_code == 200 and "/static/app/assets/" in r.text
    js = next((APP / "assets").glob("*.js")).read_text(encoding="utf-8")
    assert "eval(" not in js and "new Function(" not in js


def test_api_routes_go_through_service_layer():
    src = (PROJECT_ROOT / "redbook" / "web" / "api_trial.py").read_text(encoding="utf-8")
    assert "from ..pdfbook" not in src and "trial_repo.add_mark" not in src and "trial_repo.lock" not in src
