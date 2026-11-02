# -*- coding: utf-8 -*-
"""JSON API ของสายเทียบเล่ม PDF ↔ PDF (``/api/pdfpair``) — สัญญา ``docs/API_CONTRACT_R.md`` ข้อ 4

🔴 SYNTHETIC DEMONSTRATION DATA — ชั้นเล่มสังเคราะห์ชุดเดียวกับ ``test_trial.py``

* อ่านผ่านชั้นบริการเดียวกับหน้าเดิม — ตัวเลข/สถานะตรงกับ service ทุกช่อง · รุ่นเครื่องมือมากับทุกผล
* ทุก POST ต้องมีโทเคนในหัว · รอบที่ถูกแทนอ่านได้อย่างเดียว (409 ``superseded``)
* ข้อผิดพลาดเป็น JSON ``{error, code}`` ไม่มี stack trace / path
"""
import json

import pytest

from test_trial import AG, _env, client, shelf  # noqa: F401  (fixture ร่วม)
from redbook import privacy
from redbook.services import pdfpair as svc, pdfshelf
from redbook.storage import pdfpair_repo


@pytest.fixture(autouse=True)
def _fresh_runs(monkeypatch):
    """เทสต์ในไฟล์นี้ต้องการรอบใหม่ทุกครั้งที่เรียก ``pdfshelf.start`` — ปิดการกันกดซ้ำ (เทสต์ของมันอยู่ test_pdf_upload.py)"""
    monkeypatch.setattr(pdfshelf, "START_DEDUPE_S", -1.0)


def _h(client):
    return {"X-CSRF-Token": client.get("/api/csrf").json()["token"]}


@pytest.fixture()
def rid():
    return pdfshelf.start("S_2570_draft", "S_2570_act", AG)[1]


def _tamper_year(rid, side, fy, status):
    """จำลองรอบที่ผลถูกคำนวณโดยไม่มีปีของฉบับหนึ่ง (แก้ข้อเท็จจริงที่บันทึกไว้ตรง ๆ เฉพาะในเทสต์)"""
    from redbook.storage.db import connect
    conn = connect()
    try:
        col = f"facts_{side.lower()}_json"
        d = json.loads(conn.execute(f"SELECT {col} FROM pdfpair_runs WHERE id = ?", (rid,)).fetchone()[0])
        d["fiscal_year"], d["year_status"], d["year_origin"] = fy, status, ""
        conn.execute(f"UPDATE pdfpair_runs SET {col} = ? WHERE id = ?", (json.dumps(d, ensure_ascii=False), rid))
    finally:
        conn.close()
    svc.forget_cached_run(rid)          # ระบบไม่แก้รอบที่บันทึกแล้ว — เทสต์ที่แก้แถวตรง ๆ ต้องทิ้งผลที่แยก JSON ไว้


def test_overview_matches_service_and_carries_versions(client, rid):
    j = client.get(f"/api/pdfpair/runs/{rid}").json()
    v = svc.view(rid)
    assert j["counts"] == {"actionable": v.actionable, "pending": v.pending, "info": v.info_count}
    assert j["run"]["versions"] == v.run["versions"] and j["run"]["profile_status_label"]
    assert [g["key"] for g in j["groups"]] == [g.key for g in v.groups]
    assert j["preflight"]["ok"] is False and j["preflight"]["use_status"] == "in_review"
    assert j["preflight"]["use_status_scope"] == svc.USE_STATUS_SCOPE
    assert j["preflight"]["export_url"] == f"/pdfpair/runs/{rid}/export.csv"
    assert {d["key"] for d in j["decisions"]} == set(svc.DECISION_LABELS)
    assert (j["run"]["sides"]["A"]["stage"], j["run"]["sides"]["B"]["stage"]) == ("draft", "act")
    assert j["next_pending_id"] and j["stage_warnings"] == []
    tot = client.get(f"/api/pdfpair/runs/{rid}/findings", params={"topic": "total"}).json()["findings"]
    assert tot and {f["topic"] for f in tot} == {"total"}
    f = tot[0]
    for k in ("caveats", "parts", "tolerance_basis", "kind_label", "use", "use_label", "decision", "evidence"):
        assert k in f
    assert f["a"]["evidence_png"] == f"/pdfpair/runs/{rid}/f/{f['id']}/A.png"
    assert client.get(f"/api/pdfpair/runs/{rid}/findings", params={"topic": "nope"}).status_code == 400


def test_finding_and_decide_need_csrf_and_record_audit(client, rid):
    f = next(x for x in svc.view(rid).result.findings if not x.info)
    j = client.get(f"/api/pdfpair/runs/{rid}/f/{f.id}").json()
    assert j["finding"]["id"] == f.id and j["writable"] and set(j["diff"]) == {"a", "b"}
    n = len(pdfpair_repo.audit_entries(rid))
    bad = client.post(f"/api/pdfpair/runs/{rid}/f/{f.id}/decide", json={"choice": "checked"})
    assert bad.status_code == 403 and bad.json()["code"] == "csrf"
    assert f.id not in svc.view(rid).decisions and len(pdfpair_repo.audit_entries(rid)) == n
    h = _h(client)
    ok = client.post(f"/api/pdfpair/runs/{rid}/f/{f.id}/decide", json={"choice": "checked"}, headers=h)
    assert ok.status_code == 200 and ok.json()["finding"]["decision"]["choice"] == "checked"
    assert ok.json()["finding"]["use"] == "usable" and ok.json()["next_pending_id"] != f.id
    assert pdfpair_repo.audit_entries(rid)[-1]["action"] == "pdfpair_decision"
    change = client.post(f"/api/pdfpair/runs/{rid}/f/{f.id}/decide", json={"choice": "fix"}, headers=h)
    assert change.status_code == 400 and change.json()["code"] == "invalid" and "เหตุผล" in change.json()["error"]
    assert client.get(f"/api/pdfpair/runs/{rid}/f/nope").json()["code"] == "not_found"


def test_preflight_year_and_rerun_over_json(client, rid):
    _tamper_year(rid, "B", None, "not_found")
    pf = client.get(f"/api/pdfpair/runs/{rid}/preflight").json()
    yc = next(c for c in pf["checks"] if c["key"] == "years")
    assert not yc["ok"] and yc["action"]["code"] == "confirm_year"
    assert pf["years"]["B"]["known"] is None and 1 in pf["years"]["B"]["pages_allowed"]
    h = _h(client)
    unseen = client.post(f"/api/pdfpair/runs/{rid}/year", json={"side": "B", "year": "2570"}, headers=h)
    assert unseen.status_code == 400 and "ภาพหน้า" in unseen.json()["error"]
    r = client.post(f"/api/pdfpair/runs/{rid}/year",
                    json={"side": "B", "year": "2570", "note": "หน้าเริ่มหน่วยงาน", "seen": True}, headers=h)
    assert r.status_code == 200 and r.json()["needs_rerun"]
    assert next(c for c in r.json()["checks"] if c["key"] == "years")["action"]["code"] == "rerun"
    new = client.post(f"/api/pdfpair/runs/{rid}/rerun", json={}, headers=h).json()["rid"]
    again = client.post(f"/api/pdfpair/runs/{rid}/rerun", json={}, headers=h)
    assert again.status_code == 409 and again.json()["code"] == "superseded" and new in again.json()["error"]
    f = next(x for x in svc.view(rid).result.findings if not x.info)
    blocked = client.post(f"/api/pdfpair/runs/{rid}/f/{f.id}/decide", json={"choice": "checked"}, headers=h)
    assert blocked.status_code == 409 and blocked.json()["code"] == "superseded"
    assert f.id not in svc.view(rid).decisions
    assert client.get(f"/api/pdfpair/runs/{new}").json()["run"]["supersedes"] == rid
    assert client.get(f"/api/pdfpair/runs/{rid}").json()["run"]["superseded_by"] == new
    # รอบที่ถูกแทนไม่ชวนให้กดคำนวณซ้ำ — ทุกปุ่มพาไปรอบใหม่ (ตรวจบนเบราว์เซอร์จริงพบว่าเดิมยังมีปุ่ม POST)
    old_pf = client.get(f"/api/pdfpair/runs/{rid}/preflight").json()
    acts = {c["key"]: c["action"] for c in old_pf["checks"] if not c["ok"]}
    assert acts["years"]["code"] == acts["superseded"]["code"] == "open_run" and acts["years"]["run_id"] == new
    assert all(a is None or a["code"] != "rerun" for a in acts.values())
    nothing = client.post(f"/api/pdfpair/runs/{new}/rerun", json={}, headers=h)
    assert nothing.status_code == 409 and nothing.json()["code"] == "conflict"


def test_payload_carries_what_the_old_pages_show(client, rid):
    """ฟิลด์ที่หน้าเดิมแสดง ส่งจากเซิร์ฟเวอร์ครบ — หน้าบ้านไม่ต้องเขียนกฎ/ป้ายซ้ำ (คำขอของหน้าบ้าน 26 ต.ค.)"""
    from redbook.pdfbook.compare import Side
    from redbook.web.api_common import side_json
    v = svc.view(rid)
    j = client.get(f"/api/pdfpair/runs/{rid}").json()
    for s, bf in (("A", v.facts_a), ("B", v.facts_b)):
        side = j["run"]["sides"][s]
        assert side["pages_in_file"] == v.run["scope"][s]["pages_in_file"] and side["pages_in_file"] > 0
        assert side["coverage"] == {"sections_found": len(bf.coverage.sections_found),
                                    "repaired_words": bf.coverage.repaired_words,
                                    "pages_no_text": list(bf.coverage.pages_no_text)}
    assert j["item_change_ids"] == [f.id for f in v.item_changes] and j["rounding_policy"] == svc.ROUNDING_POLICY
    assert j["preflight"]["failing_checks"] == [{"key": c.key, "label": c.label} for c in svc.preflight(rid).failing]
    # ค่าที่ฝั่งไม่มีหน่วยของตัวเอง ใช้หน่วยของข้อสังเกต (เหมือน amount_text(f.a, f.unit) ของหน้าเดิม) · ข้อความดิบ
    bare = Side(value="5", raw="5 ", status="read")
    sj = side_json(bare, None, "บาท")
    assert sj["amount_text"] == svc.amount_text(bare, "บาท") and "บาท" in sj["amount_text"]
    assert sj["raw_note"] == svc.raw_note(bare)
    summed = next(f for f in v.result.findings if f.parts)
    fj = client.get(f"/api/pdfpair/runs/{rid}/f/{summed.id}").json()
    assert fj["rounding_policy"] == svc.ROUNDING_POLICY and "raw_note" in fj["finding"]["a"]


def test_year_status_labels_come_from_service_and_confirmed_is_not_an_old_run(client, rid):
    pf = client.get(f"/api/pdfpair/runs/{rid}/preflight").json()
    for s in "AB":
        y = pf["years"][s]
        assert (y["status_label"], y["status_state"], y["confirmable"]) == ("ชัดเจน", "ok", False)
        assert y["evidence"] and all(e["kind_label"] for e in y["evidence"])
    _tamper_year(rid, "B", None, "not_found")
    y = client.get(f"/api/pdfpair/runs/{rid}/preflight").json()["years"]["B"]
    assert (y["status_label"], y["status_state"], y["confirmable"]) == ("หาไม่พบ", "fail", True)
    svc.confirm_year(rid, "B", "2570", "หน้าเริ่มหน่วยงาน", True)
    new = svc.rerun(rid)
    # บั๊กหน้าเดิม: ป้ายในเทมเพลตไม่มี "confirmed" ⇒ รอบที่คำนวณซ้ำด้วยปีที่ยืนยันขึ้น "รอบเก่า — ไม่มีข้อมูลที่มา"
    ny = client.get(f"/api/pdfpair/runs/{new}/preflight").json()["years"]["B"]
    assert (ny["status"], ny["status_label"], ny["status_state"], ny["confirmable"]) == \
        ("confirmed", svc.YEAR_STATUS_LABELS["confirmed"], "ok", False)
    html = client.get(f"/pdfpair/runs/{new}/preflight").text
    assert svc.YEAR_STATUS_LABELS["confirmed"] in html and svc.YEAR_STATUS_UNKNOWN not in html
    assert client.get(f"/api/pdfpair/runs/{rid}/preflight").json()["years"]["B"]["confirmable"] is False   # ถูกแทนแล้ว


def test_audit_and_runs_list(client, rid):
    j = client.get(f"/api/pdfpair/runs/{rid}/audit").json()
    assert [e["seq"] for e in j["entries"]] == [e["seq"] for e in pdfpair_repo.audit_entries(rid)]
    assert j["entries"][0]["action_label"] == "สร้างรอบเทียบ" and j["entries"][0]["summary"] and j["chain"]["ok"]
    assert rid in [r["id"] for r in client.get("/api/pdfpair/runs").json()["runs"]]


def test_shelf_listing_and_start(client):
    j = client.get("/api/pdfpair/shelf", params={"a": "S_2570_draft"}).json()
    assert {v["key"] for v in j["volumes"]} == {"S_2570_draft", "S_2570_act"} and j["a"]["key"] == "S_2570_draft"
    assert j["suggest"][0]["key"] == "S_2570_act"
    assert privacy.find_absolute_paths(json.dumps(j, ensure_ascii=False)) == []     # ไม่เปิดเผยเส้นทางในเครื่อง
    h = _h(client)
    held = client.post("/api/pdfpair/shelf/start", headers=h,
                       json={"a": "S_2570_draft", "b": "S_2570_act", "agency": "สถาบันวิจัยระบบสาธารณสุข"})
    assert held.status_code == 400 and "กันไว้" in held.json()["error"]
    ok = client.post("/api/pdfpair/shelf/start", json={"a": "S_2570_draft", "b": "S_2570_act", "agency": AG},
                     headers=h)
    assert ok.status_code == 200 and svc.view(ok.json()["rid"]) is not None


def _capped(headers: list, chunks: list) -> tuple:
    """เรียก ``_body_capped`` ด้วย receive ที่นับว่าแอปดึง body ไปกี่ชิ้น (ควบคุมสิ่งที่มาถึงได้แน่นอน)"""
    import asyncio
    from starlette.requests import Request
    from redbook.web import api_common
    pulled = []

    async def receive():
        i = len(pulled)
        pulled.append(i)
        return {"type": "http.request", "body": chunks[i] if i < len(chunks) else b"",
                "more_body": i + 1 < len(chunks)}
    req = Request({"type": "http", "method": "POST", "path": "/api/x", "headers": headers}, receive)
    try:
        return asyncio.run(api_common._body_capped(req)), len(pulled)
    except api_common.ApiError as e:
        return (e.status, e.code), len(pulled)


def test_body_limit_is_enforced_while_receiving_not_after():
    """Bo REVIEW 6409941573 ข้อ 2 — ไม่สะสม body เกินเพดานในหน่วยความจำ"""
    from redbook.web.api_common import MAX_BODY
    k16 = b"x" * (16 * 1024)
    # แจ้งความยาวเกิน = ปฏิเสธโดยไม่ดึง body เลย
    assert _capped([(b"content-length", str(MAX_BODY + 1).encode())], [k16] * 5) == ((413, "too_large"), 0)
    # ไม่แจ้งความยาว (chunked) = หยุดที่ชิ้นที่ทำให้เกิน (ชิ้นที่ 5 ของ 16 KB) ไม่ดึงชิ้นที่เหลือ
    assert _capped([], [k16] * 40) == ((413, "too_large"), MAX_BODY // len(k16) + 1)
    # แจ้งความยาวต่ำกว่าความจริง ก็ยังถูกนับระหว่างรับ
    assert _capped([(b"content-length", b"10")], [k16] * 40)[0] == (413, "too_large")
    # พอดีเพดาน = รับ
    body, n = _capped([], [k16] * 4)
    assert len(body) == MAX_BODY and n == 4


def test_oversized_json_writes_nothing_over_the_real_route(client, rid):
    from redbook.storage import audit
    fid = next(f.id for f in svc.view(rid).result.findings if not f.info)
    h = {**_h(client), "Content-Type": "application/json"}
    rows = audit.verify_chain()["checked"]
    for body in (b'{"choice": "checked", "note": "' + b"x" * (70 * 1024) + b'"}',
                 iter([b'{"choice": "checked", "note": "'] + [b"x" * 8192] * 12 + [b'"}'])):
        r = client.post(f"/api/pdfpair/runs/{rid}/f/{fid}/decide", content=body, headers=h)
        assert (r.status_code, r.json()["code"]) == (413, "too_large")
    assert audit.verify_chain()["checked"] == rows and fid not in svc.view(rid).decisions


def test_errors_are_json_without_internals(client, monkeypatch):
    r = client.get("/api/pdfpair/runs/pp_nope")
    assert r.status_code == 404 and r.json()["code"] == "not_found"
    h = _h(client)
    big = client.post("/api/pdfpair/shelf/start", content=b"{" + b" " * (70 * 1024) + b"}",
                      headers={**h, "Content-Type": "application/json"})
    assert big.status_code == 413 and big.json()["code"] == "too_large"

    def boom(_rid):
        raise RuntimeError(r"C:\Users\someone\secret\file.pdf exploded")
    monkeypatch.setattr(svc, "view", boom)
    r = client.get("/api/pdfpair/runs/pp_x")
    assert r.status_code == 500 and r.json()["code"] == "server" and r.json()["error_id"]
    assert "secret" not in r.text and "Traceback" not in r.text


def test_decision_choices_carry_when_text_from_the_service(client, rid):
    """Bo REVIEW #44 6459501871 — "เลือกเมื่อ…" ใต้ตัวเลือกแต่ละข้อมาจาก service (หน้าบ้านไม่ใส่ถ้อยคำเอง) · หน้าเดิมแสดงชุดเดียวกัน"""
    got = client.get(f"/api/pdfpair/runs/{rid}").json()["decisions"]
    assert [d["key"] for d in got] == [k for k, _l in svc.DECISIONS]
    assert all(d["when"] == svc.DECISION_WHEN[d["key"]] and d["when"].startswith("เลือกเมื่อ") for d in got)
    assert set(svc.DECISION_WHEN) == {k for k, _l in svc.DECISIONS}
    fid = next(f.id for f in svc.view(rid).result.findings if not f.info)
    html = client.get(f"/pdfpair/runs/{rid}/f/{fid}").text
    assert all(svc.DECISION_WHEN[k] in html for k, _l in svc.DECISIONS)


def test_single_finding_carries_page_size_in_the_crop_frame(client, rid):
    from redbook.pdfbook import reader
    v = svc.view(rid)
    f = next(x for x in v.result.findings if x.a.page and x.b.page)
    j = client.get(f"/api/pdfpair/runs/{rid}/f/{f.id}").json()["finding"]
    for s, side in (("a", f.a), ("b", f.b)):
        path, _row = svc._side_file(v.run["project_id"], s.upper())
        assert j[s]["page_size"] == [round(x, 2) for x in reader.page_size(path, side.page)]
    nopage = next((x for x in v.result.findings if not x.a.page), None)
    if nopage is not None:
        assert client.get(f"/api/pdfpair/runs/{rid}/f/{nopage.id}").json()["finding"]["a"]["page_size"] is None
