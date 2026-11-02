# -*- coding: utf-8 -*-
"""ถ้อยคำตัวเลือกความเห็นของสายเทียบเล่ม PDF (Bo REVIEW #44 6462103585) — semantic parity

ไม่ได้ตรวจแค่ว่า key ไม่เปลี่ยน: ป้าย · "เลือกเมื่อ…" · ผลหลังเลือก ต้องสื่อผลต่อการใช้ผล (``DECISION_USE``) ตรงกัน
และทุกเส้นทางที่แสดงคำตัดสิน (API · หน้าข้อ · หน้ารอบ · preflight · CSV ส่งออก · Audit) ใช้ชุดเดียวกัน ·
ป้ายของสาย T1B (``verify_view.DECISION_CHOICES``) ไม่เปลี่ยน

🔴 SYNTHETIC DEMONSTRATION DATA — ชั้นเล่มสังเคราะห์ชุดเดียวกับ ``test_trial.py``
"""
import pytest

from test_trial import AG, _env, client, shelf  # noqa: F401  (fixture ร่วม)
from redbook.evidence import pdftext
from redbook.services import pdfpair as svc, pdfshelf, verify_view as vv

pytestmark = pytest.mark.skipif(pdftext.product_backend() is None, reason="ไม่มี pdfplumber + pypdfium2")

#: ความหมายที่ตรึงไว้ — เปลี่ยนเมื่อไรต้องผ่าน Bo (ไม่ใช่แก้ให้เทสต์ผ่าน)
FROZEN_USE = {"checked": "usable", "per_document": "usable", "fix": "usable",
              "needs_more": "open", "mismatch": "open", "not_relevant": "excluded"}
T1B_LABELS = {"checked": "รับทราบ — ตรวจแล้ว", "per_document": "เป็นการเปลี่ยนแปลงตามเอกสาร",
              "needs_more": "ต้องตรวจเพิ่มเติม", "mismatch": "ระบบจับคู่ผิด", "not_relevant": "ไม่เกี่ยวข้อง",
              "fix": "ต้องแก้ข้อมูล"}


def test_keys_and_use_are_unchanged_and_t1b_labels_untouched():
    assert [k for k, _l in svc.DECISIONS] and {k for k, _l in svc.DECISIONS} == set(FROZEN_USE)
    assert svc.DECISION_USE == FROZEN_USE
    assert {k: label for k, label, _s in vv.DECISION_CHOICES} == T1B_LABELS
    assert set(svc.DECISION_WHEN) == set(svc.DECISION_AFTER) == set(FROZEN_USE)


def test_wording_says_what_the_choice_does_to_use():
    for k, use in FROZEN_USE.items():
        when, after = svc.DECISION_WHEN[k], svc.DECISION_AFTER[k]
        assert when.startswith("เลือกเมื่อ")
        if use == "open":
            assert "ยังไม่ปิด" in after and "ยังใช้ผลข้อนี้ไม่ได้" in after
            assert "ยังไม่ปิด" in when or "ยังใช้ผลข้อนี้ไม่ได้" in when
        elif use == "excluded":
            assert "ไม่นับ" in when and "รายงานจำนวน" in when and "ไม่นับ" in after
        else:
            assert "ยังไม่ปิด" not in after and "ไม่นับ" not in after
    assert "ต่างจริง" not in svc.DECISION_WHEN["checked"]              # ข้อเตือน/ความสอดคล้องภายในเล่มก็ใช้ได้
    assert "ปกติ" not in svc.DECISION_WHEN["per_document"]              # "ปกติ" อย่างเดียวไม่ใช่หลักฐาน
    assert "ไม่ใช่การยืนยันว่าแก้เอกสารเสร็จ" in svc.DECISION_AFTER["fix"]
    assert "ตรวจด้วยวิธีอื่น" in svc.DECISION_WHEN["mismatch"]          # เงื่อนไขอยู่ใกล้ตัวเลือก ไม่ใช่แค่ใน preflight
    assert "ไม่ใช้กับข้อที่ยากหรือผลที่ระบบผิด" in svc.DECISION_WHEN["not_relevant"]


def test_choices_are_grouped_closed_open_excluded_with_no_default():
    order = {"usable": 0, "open": 1, "excluded": 2}
    seq = [order[FROZEN_USE[k]] for k, _l in svc.DECISIONS]
    assert seq == sorted(seq)


def test_every_path_shows_the_same_wording(client):
    _pid, rid = pdfshelf.start("S_2570_draft", "S_2570_act", AG)
    v = svc.view(rid)
    acts = [f for f in v.result.findings if not f.info]
    h = {"X-CSRF-Token": client.get("/api/csrf").json()["token"]}
    j = client.get(f"/api/pdfpair/runs/{rid}").json()
    assert [(d["key"], d["label"], d["when"], d["after"], d["use"]) for d in j["decisions"]] == \
        [(k, label, svc.DECISION_WHEN[k], svc.DECISION_AFTER[k], FROZEN_USE[k]) for k, label in svc.DECISIONS]
    html = client.get(f"/pdfpair/runs/{rid}/f/{acts[0].id}").text
    assert all(label in html and svc.DECISION_WHEN[k] in html for k, label in svc.DECISIONS)
    for f, choice in zip(acts, ("fix", "mismatch", "not_relevant")):
        r = client.post(f"/api/pdfpair/runs/{rid}/f/{f.id}/decide", json={"choice": choice, "note": "เหตุผลทดสอบ"},
                        headers=h).json()
        assert r["finding"]["decision"]["choice_label"] == svc.DECISION_LABELS[choice]
        assert r["finding"]["decision"]["after"] == svc.DECISION_AFTER[choice]
    for f in acts[3:]:                      # ตัดสินครบ — เหตุผลของสถานะ "ยังไม่ปิด" จึงแสดงใน preflight
        svc.decide(rid, f.id, "checked", "")
    page = client.get(f"/pdfpair/runs/{rid}/f/{acts[0].id}").text
    assert svc.DECISION_AFTER["fix"] in page
    assert svc.DECISION_LABELS["fix"] in client.get(f"/pdfpair/runs/{rid}").text
    pf = svc.preflight(rid)
    reasons = " ".join(pf.use_reasons)
    assert svc.DECISION_LABELS["needs_more"] in reasons and svc.DECISION_LABELS["mismatch"] in reasons
    assert "นอกขอบเขตที่กำหนด" in reasons and "ไม่เกี่ยวข้อง" not in reasons
    csv_text = svc.export_csv(rid)
    csv_text = csv_text if isinstance(csv_text, str) else csv_text[0]
    for choice in ("fix", "mismatch", "not_relevant"):
        assert svc.DECISION_LABELS[choice] in csv_text
    assert svc.USE_LABELS["excluded"] in csv_text and "ไม่เกี่ยวข้อง" not in csv_text
    audit = client.get(f"/api/pdfpair/runs/{rid}/audit").json()["entries"]
    assert any(svc.DECISION_LABELS["fix"] in (e.get("summary") or "") for e in audit)
