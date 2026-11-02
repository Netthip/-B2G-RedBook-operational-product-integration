# -*- coding: utf-8 -*-
"""B3 — `accounted()` ต้องเป็น conservation gate จริง · มี mutation tests ที่ทำให้ด่านล้ม

🔴 Bo (`5595832792` B3) — ของเดิม ``closed`` ไม่ล้มเมื่อ candidate มี endpoint id ที่ไม่อยู่
ใน input, มีการนับซ้ำผิดรูป, หรือ mapping shape/status ไม่สอดคล้องกัน ⇒ ยังไม่ใช่ conservation gate

**mutation tests** — จงใจ drop / duplicate / inject unknown / สลับ shape แล้ว **ด่านต้องล้ม**
ทุกครั้ง · ถ้าด่านยังบอกว่า ``closed`` แปลว่าด่านนั้นไม่กัด

🔴 **SYNTHETIC TEST FIXTURE**
"""
import dataclasses

import pytest

from redbook.indicators import mapping as mp
from redbook.indicators import observe as ob

SHA_OLD, SHA_NEW = "a" * 64, "b" * 64


def obs(text, *, doc, sha, occurrence=1):
    return ob.manual_observation(doc, sha, page=1, observed_text=text,
                                 occurrence=occurrence, page_width=595.0)


@pytest.fixture()
def world():
    old = [obs("ตัวชี้วัด ก ร้อยละ 80", doc="doc_old", sha=SHA_OLD, occurrence=1),
           obs("ตัวชี้วัด ข 5 เรื่อง", doc="doc_old", sha=SHA_OLD, occurrence=2),
           obs("ตัวชี้วัด ค : ร้อยละของข้อร้องเรียนที่ได้รับการแก้ไข ร้อยละ 100",
               doc="doc_old", sha=SHA_OLD, occurrence=3)]
    new = [obs("ตัวชี้วัด ก ร้อยละ 80", doc="doc_new", sha=SHA_NEW, occurrence=1),
           obs("ตัวชี้วัด ข 5 เรื่อง", doc="doc_new", sha=SHA_NEW, occurrence=2),
           obs("ตัวชี้วัด ง : จำนวนระบบสารสนเทศที่พัฒนาแล้วเสร็จ 3 ระบบ",
               doc="doc_new", sha=SHA_NEW, occurrence=3)]
    return old, new, mp.propose(old, new)


def gate(world, cands=None):
    old, new, base = world
    return mp.accounted(old, new, base if cands is None else cands)


# ── ฐาน: บัญชีต้องปิดเมื่อไม่มีใครแตะ ────────────────────────────────────────

def test_untouched_result_closes_the_gate(world):
    g = gate(world)
    assert g["closed"] is True and g["failed_checks"] == []
    assert all(g["checks"].values())
    assert g["rows"] == len(world[2])
    assert g["gate_version"] == mp.MAPPING_VERSION


def test_gate_reports_per_status_totals_that_reconcile(world):
    g = gate(world)
    assert sum(v["rows"] for v in g["per_status"].values()) == g["rows"]
    assert sum(v["old"] + v["new"] for v in g["per_status"].values()) == g["endpoints"]


# ── mutation: drop ───────────────────────────────────────────────────────────

def test_dropping_a_row_fails_the_gate(world):
    old, new, cands = world
    g = gate(world, cands[:-1])
    assert g["closed"] is False
    assert "no_missing_ids" in g["failed_checks"]
    assert g["missing_old"] or g["missing_new"]


def test_dropping_everything_fails_loudly(world):
    g = gate(world, [])
    assert g["closed"] is False and "no_missing_ids" in g["failed_checks"]


# ── mutation: duplicate ─────────────────────────────────────────────────────

def test_duplicating_a_non_ambiguous_row_fails_the_gate(world):
    old, new, cands = world
    same = [c for c in cands if c.proposed_status == mp.SAME_EXACT][0]
    dup = dataclasses.replace(same, mapping_id=same.mapping_id + "_copy")
    g = gate(world, list(cands) + [dup])
    assert g["closed"] is False
    assert "duplicate_membership" in g["failed_checks"]
    assert g["duplicate_old"] and g["duplicate_new"]


def test_duplicate_mapping_id_fails_the_gate(world):
    old, new, cands = world
    g = gate(world, list(cands) + [cands[0]])
    assert g["closed"] is False
    assert "unique_mapping_ids" in g["failed_checks"]
    assert g["duplicate_mapping_ids"] == [cands[0].mapping_id]


def test_declared_ambiguity_may_repeat_an_observation(world):
    """ความคลุมเครือที่ประกาศรูปไว้ (one-to-many) ยังต้องผ่าน — ด่านไม่ห้ามทุกการซ้ำ"""
    o = obs("ตัวชี้วัดซ้ำ 12 ครั้ง", doc="doc_old", sha=SHA_OLD)
    n1 = obs("ตัวชี้วัดซ้ำ 12 ครั้ง", doc="doc_new", sha=SHA_NEW, occurrence=1)
    n2 = obs("ตัวชี้วัดซ้ำ 12 ครั้ง", doc="doc_new", sha=SHA_NEW, occurrence=2)
    cands = mp.propose([o], [n1, n2])
    assert {c.proposed_status for c in cands} == {mp.AMBIGUOUS_REVIEW_REQUIRED}
    assert mp.accounted([o], [n1, n2], cands)["closed"] is True


# ── mutation: inject unknown ────────────────────────────────────────────────

def test_injecting_an_unknown_endpoint_fails_the_gate(world):
    old, new, cands = world
    ghost = dataclasses.replace(cands[0], mapping_id="ghost",
                                old_observation_id="obs_does_not_exist")
    g = gate(world, list(cands) + [ghost])
    assert g["closed"] is False
    assert "unknown_ids" in g["failed_checks"]
    assert g["unknown_old"] == ["obs_does_not_exist"]


def test_unknown_status_fails_the_gate(world):
    old, new, cands = world
    bad = dataclasses.replace(cands[0], proposed_status="MADE_UP_STATUS")
    g = gate(world, [bad] + list(cands[1:]))
    assert g["closed"] is False and "known_statuses" in g["failed_checks"]


# ── mutation: สลับ shape ────────────────────────────────────────────────────

def test_new_indicator_with_an_old_side_fails_the_gate(world):
    old, new, cands = world
    row = [c for c in cands if c.proposed_status == mp.NEW_INDICATOR][0]
    bad = dataclasses.replace(row, old_observation_id=old[0].observation_id)
    g = gate(world, [bad if c is row else c for c in cands])
    assert g["closed"] is False and "row_shapes" in g["failed_checks"]
    assert g["shape_violations"][0]["reason"] == "new_indicator_must_not_have_old_side"


def test_removed_indicator_with_a_new_side_fails_the_gate(world):
    old, new, cands = world
    row = [c for c in cands if c.proposed_status == mp.REMOVED_INDICATOR][0]
    bad = dataclasses.replace(row, new_observation_id=new[0].observation_id)
    g = gate(world, [bad if c is row else c for c in cands])
    assert g["closed"] is False
    assert g["shape_violations"][0]["reason"] == "removed_indicator_must_not_have_new_side"


def test_paired_status_missing_one_side_fails_the_gate(world):
    old, new, cands = world
    row = [c for c in cands if c.proposed_status == mp.SAME_EXACT][0]
    bad = dataclasses.replace(row, new_observation_id="")
    g = gate(world, [bad if c is row else c for c in cands])
    assert g["closed"] is False
    assert g["shape_violations"][0]["reason"] == "paired_status_requires_both_sides"


def test_row_without_any_endpoint_fails_the_gate(world):
    old, new, cands = world
    bad = dataclasses.replace(cands[0], mapping_id="empty", old_observation_id="",
                              new_observation_id="")
    g = gate(world, list(cands) + [bad])
    assert g["closed"] is False and "row_shapes" in g["failed_checks"]


# ── ด่านต้องกัดจริง ──────────────────────────────────────────────────────────

def test_every_mutation_family_is_detected(world):
    """สรุปรวม — ทุกตระกูลการกลายพันธุ์ต้องทำให้ ``closed`` เป็นเท็จ"""
    old, new, cands = world
    same = [c for c in cands if c.proposed_status == mp.SAME_EXACT][0]
    mutations = {
        "drop": cands[:-1],
        "duplicate": list(cands) + [dataclasses.replace(same, mapping_id=same.mapping_id + "_x")],
        "unknown": list(cands) + [dataclasses.replace(cands[0], mapping_id="g",
                                                      new_observation_id="nope")],
        "shape": [dataclasses.replace(c, old_observation_id=old[0].observation_id)
                  if c.proposed_status == mp.NEW_INDICATOR else c for c in cands],
    }
    for name, mutated in mutations.items():
        assert mp.accounted(old, new, mutated)["closed"] is False, name
