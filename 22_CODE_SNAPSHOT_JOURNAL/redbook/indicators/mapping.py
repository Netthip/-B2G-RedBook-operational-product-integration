# -*- coding: utf-8 -*-
"""การจับคู่ตัวชี้วัดเก่า↔ใหม่ — 8 สถานะ · เครื่อง **เสนอ** มนุษย์ **ตัดสิน**

🔴 **คำสั่งกิ๊ฟ (9 ก.ย. 2569 · §2)** — สถานะที่ต้องแยกจากกัน

======  ============================  ===========================================
 #      สถานะ                          ความหมาย
======  ============================  ===========================================
 1      ``SAME_EXACT``                 ตัวเดียวกัน ข้อความตรงกันทุกอักขระ
 2      ``SAME_WORDING_VARIANT``       ต่างเฉพาะสะกด/ช่องว่าง/เครื่องหมาย
 3      ``SAME_CONCEPT_REPHRASED``     นิยาม/วิธีวัดเดิม แต่เขียนต่างออกไป
 4      ``RELATED_NOT_EQUIVALENT``     เรื่องใกล้กัน แต่ไม่ใช่ตัวชี้วัดเดียวกัน
 5      ``DEFINITION_CHANGED``         ชื่อคล้ายเดิม แต่ตัวหาร/หน่วย/วิธี/ขอบเขตเปลี่ยน
 6      ``NEW_INDICATOR``              มีเฉพาะฉบับใหม่
 7      ``REMOVED_INDICATOR``          มีเฉพาะฉบับเก่า
 8      ``AMBIGUOUS_REVIEW_REQUIRED``  เครื่องตัดสินไม่ได้ / คู่แข่งหลายตัว / ข้อความซ้ำ
======  ============================  ===========================================

**กติกาที่บังคับในโค้ด (มีเทสต์)**

* สถานะ **3 · 4 · 5 · 8 ต้องมีมนุษย์ยืนยัน** (``human_required=True`` เสมอ)
* เครื่อง **ไม่เสนอ** ``RELATED_NOT_EQUIVALENT`` — เป็นทางเลือกของผู้ตรวจเท่านั้น
* ความคล้ายสูงแต่ **ตัวเลข/หน่วย/วิธีคำนวณต่าง** ⇒ ห้ามเป็น ``SAME_*``
  (เสนอ ``DEFINITION_CHANGED`` ให้คนดู)
* ข้อความ **ซ้ำกันเอง** ในฉบับเดียว (one-to-many) ⇒ ``AMBIGUOUS_REVIEW_REQUIRED``
  ไม่ใช่ ``SAME_EXACT``
* การจับคู่เป็น **global phase** — ผลไม่ขึ้นกับลำดับที่อ่านข้อสังเกต
  (บทเรียนจาก `t1b-scoring-3layer-0.2.0`)
* คะแนนความคล้ายเก็บเป็น ``internal_score`` — **ห้ามแสดงในหน้าตรวจเฉลย**
* 🔴 **P1-2 fail-visible** (Bo `5598957701`) — ถ้าข้างใดข้างหนึ่งมีธง
  ``TEXT_CLIPPED_AT_PAGE_EDGE`` (ข้อความชน/ล้นขอบหน้า) **ห้ามเสนอสถานะอัตโนมัติใด ๆ**
  ต้องเป็น ``AMBIGUOUS_REVIEW_REQUIRED`` เสมอ เพราะตัวอ่าน PDF ต่างชนิดอ่านบรรทัดนั้นได้
  ไม่เท่ากัน ⇒ ข้อความที่เห็นอาจไม่ครบ · ห้ามตัดเงียบแล้วเสนอ mapping เป็นผลปกติ

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from . import normalize as nz
from .observe import Observation

MAPPING_VERSION = "indicator-mapping-0.2.0"

SAME_EXACT = "SAME_EXACT"
SAME_WORDING_VARIANT = "SAME_WORDING_VARIANT"
SAME_CONCEPT_REPHRASED = "SAME_CONCEPT_REPHRASED"
RELATED_NOT_EQUIVALENT = "RELATED_NOT_EQUIVALENT"
DEFINITION_CHANGED = "DEFINITION_CHANGED"
NEW_INDICATOR = "NEW_INDICATOR"
REMOVED_INDICATOR = "REMOVED_INDICATOR"
AMBIGUOUS_REVIEW_REQUIRED = "AMBIGUOUS_REVIEW_REQUIRED"

STATUSES = (SAME_EXACT, SAME_WORDING_VARIANT, SAME_CONCEPT_REPHRASED,
            RELATED_NOT_EQUIVALENT, DEFINITION_CHANGED, NEW_INDICATOR,
            REMOVED_INDICATOR, AMBIGUOUS_REVIEW_REQUIRED)

STATUS_LABELS = {
    SAME_EXACT: "ตัวเดียวกัน ข้อความตรงกัน",
    SAME_WORDING_VARIANT: "ตัวเดียวกัน ต่างเฉพาะการสะกด/ช่องว่าง/เครื่องหมาย",
    SAME_CONCEPT_REPHRASED: "ตัวเดียวกัน แต่เขียนต่างออกไป",
    RELATED_NOT_EQUIVALENT: "เรื่องใกล้กัน แต่ไม่ใช่ตัวชี้วัดเดียวกัน",
    DEFINITION_CHANGED: "ชื่อคล้ายเดิม แต่นิยาม/ตัวหาร/หน่วย/วิธี/ขอบเขตเปลี่ยน",
    NEW_INDICATOR: "ตัวชี้วัดใหม่ (มีเฉพาะฉบับใหม่)",
    REMOVED_INDICATOR: "ตัวชี้วัดถูกตัดออก (มีเฉพาะฉบับเก่า)",
    AMBIGUOUS_REVIEW_REQUIRED: "คลุมเครือ — ต้องให้คนตัดสิน",
}

#: สถานะที่ **ต้อง** มีมนุษย์ยืนยัน (คำสั่งกิ๊ฟ)
HUMAN_REQUIRED = frozenset({SAME_CONCEPT_REPHRASED, RELATED_NOT_EQUIVALENT,
                            DEFINITION_CHANGED, AMBIGUOUS_REVIEW_REQUIRED})
#: สถานะที่เครื่องเสนอได้ — ``RELATED_NOT_EQUIVALENT`` ไม่อยู่ในชุดนี้โดยเจตนา
MACHINE_MAY_PROPOSE = frozenset({SAME_EXACT, SAME_WORDING_VARIANT,
                                 SAME_CONCEPT_REPHRASED, DEFINITION_CHANGED,
                                 NEW_INDICATOR, REMOVED_INDICATOR,
                                 AMBIGUOUS_REVIEW_REQUIRED})
#: สถานะที่ถือว่า "ตัวเดียวกัน" — ใช้ผูก indicator_id หลังมนุษย์ยืนยัน
SAME_FAMILY = frozenset({SAME_EXACT, SAME_WORDING_VARIANT, SAME_CONCEPT_REPHRASED})

#: สถานะที่ต้องมีข้อสังเกตทั้งสองฝั่ง (คู่) — ใช้ตรวจรูปทรงในบัญชี (B3)
PAIRED_STATUSES = frozenset({SAME_EXACT, SAME_WORDING_VARIANT, SAME_CONCEPT_REPHRASED,
                             RELATED_NOT_EQUIVALENT, DEFINITION_CHANGED})
#: สถานะที่มีได้ฝั่งเดียว
NEW_ONLY_STATUSES = frozenset({NEW_INDICATOR})
OLD_ONLY_STATUSES = frozenset({REMOVED_INDICATOR})
#: สถานะที่อนุญาตให้ข้อสังเกตหนึ่งตัวปรากฏได้หลายแถว (ความคลุมเครือที่ประกาศรูปไว้)
MULTI_ROW_ALLOWED = frozenset({AMBIGUOUS_REVIEW_REQUIRED})

#: เหตุผลที่บังคับให้ต้องให้คนตัดสิน แม้ข้อความจะตรงกัน (P1-2)
BASIS_CLIPPED = "text_clipped_at_page_edge"


@dataclass(frozen=True)
class Rules:
    """เกณฑ์ที่ตรึงต่อรอบ — เก็บ hash ลง run เพื่อให้ตรวจซ้ำได้"""
    version: str = MAPPING_VERSION
    #: ความคล้ายขั้นต่ำที่จะ *เสนอ* ว่าเป็นตัวเดียวกันแต่เขียนต่าง (ยังต้องให้คนยืนยัน)
    rephrase_min: float = 0.75
    #: ความคล้ายขั้นต่ำที่จะ *เสนอ* เป็นคู่คลุมเครือ
    ambiguous_min: float = 0.50
    #: ถ้าคู่แข่งอันดับสองใกล้อันดับหนึ่งไม่เกินค่านี้ ⇒ คลุมเครือ
    tie_margin: float = 0.05

    def as_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True)

    @property
    def rules_hash(self) -> str:
        return hashlib.sha256(self.as_json().encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Difference:
    field_name: str
    old: str
    new: str


@dataclass(frozen=True)
class Candidate:
    mapping_id: str
    old_observation_id: str          # ว่างเมื่อ NEW_INDICATOR
    new_observation_id: str          # ว่างเมื่อ REMOVED_INDICATOR
    proposed_status: str
    human_required: bool
    basis: tuple[str, ...]           # เหตุผลที่เครื่องอ่านได้ — ไม่ใช่คะแนน
    differences: tuple[Difference, ...]
    internal_score: float            # 🔴 ห้ามแสดงในหน้าตรวจเฉลย
    alternatives: tuple[str, ...] = field(default_factory=tuple)  # obs id คู่แข่ง

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.proposed_status, self.proposed_status)


def _mid(old_id: str, new_id: str, rules: Rules) -> str:
    h = hashlib.sha256(f"{old_id}|{new_id}|{rules.version}".encode("utf-8"))
    return "map_" + h.hexdigest()[:16]


def differences(a: Observation, b: Observation) -> tuple[Difference, ...]:
    out: list[Difference] = []
    for name in ("unit", "target_value", "method_text", "period_text", "baseline_text"):
        va, vb = getattr(a, name), getattr(b, name)
        if va != vb:
            out.append(Difference(name, va, vb))
    na, nb = nz.numeric_tokens(a.observed_text), nz.numeric_tokens(b.observed_text)
    if na != nb:
        out.append(Difference("numeric_tokens", " ".join(na), " ".join(nb)))
    return tuple(out)


def _definition_changed(diffs: tuple[Difference, ...]) -> bool:
    """ตัวหาร/หน่วย/วิธี/ตัวเลข/รอบ ต่าง ⇒ เป็นสัญญาณนิยามเปลี่ยน ห้ามเป็น SAME_*"""
    return any(d.field_name in ("unit", "target_value", "method_text",
                                "numeric_tokens", "period_text") for d in diffs)


def _same_family_group(items: list[Observation], key) -> dict[str, list[Observation]]:
    g: dict[str, list[Observation]] = {}
    for o in items:
        g.setdefault(key(o), []).append(o)
    return g


def propose(old: list[Observation], new: list[Observation],
            rules: Rules = Rules()) -> list[Candidate]:
    """เสนอคู่แบบ global — เฟส 1 ตรงตัว · เฟส 2 รูปมาตรฐานเท่ากัน · เฟส 3 คล้ายเชิงอักขระ

    ทุกข้อสังเกตต้องถูกบัญชี (accounted) — เก่าที่ไม่มีคู่ = ``REMOVED`` ·
    ใหม่ที่ไม่มีคู่ = ``NEW`` · ข้อความซ้ำในฉบับเดียวกัน = ``AMBIGUOUS`` ทั้งกลุ่ม
    """
    old_sorted = sorted(old, key=lambda o: o.observation_id)
    new_sorted = sorted(new, key=lambda o: o.observation_id)
    out: list[Candidate] = []
    used_old: set[str] = set()
    used_new: set[str] = set()

    def emit(o: Observation | None, n: Observation | None, status: str,
             basis: list[str], score: float, alts=()) -> None:
        oid = o.observation_id if o else ""
        nid = n.observation_id if n else ""
        diffs = differences(o, n) if (o and n) else ()
        # 🔴 P1-2 — ข้อความชน/ล้นขอบหน้า ⇒ ไม่มีสถานะอัตโนมัติใดน่าเชื่อถือ
        if (o is not None and o.text_clipped) or (n is not None and n.text_clipped):
            if status != AMBIGUOUS_REVIEW_REQUIRED:
                basis = list(basis) + [BASIS_CLIPPED]
                status = AMBIGUOUS_REVIEW_REQUIRED
            elif BASIS_CLIPPED not in basis:
                basis = list(basis) + [BASIS_CLIPPED]
        out.append(Candidate(
            mapping_id=_mid(oid, nid, rules), old_observation_id=oid,
            new_observation_id=nid, proposed_status=status,
            human_required=(status in HUMAN_REQUIRED), basis=tuple(basis),
            differences=diffs, internal_score=round(score, 4),
            alternatives=tuple(alts)))
        if o:
            used_old.add(oid)
        if n:
            used_new.add(nid)

    # ── เฟส 1 · 2: ตรงตัว / รูปมาตรฐานเท่ากัน — ทำทั้งชุดก่อนเฟสถัดไป ──────
    for phase, keyfn, status, why in (
            (1, lambda o: o.observed_text, SAME_EXACT, "exact_text_equal"),
            (2, lambda o: nz.variant_key(o.observed_text), SAME_WORDING_VARIANT, "normalized_text_equal")):
        g_old = _same_family_group([o for o in old_sorted if o.observation_id not in used_old], keyfn)
        g_new = _same_family_group([n for n in new_sorted if n.observation_id not in used_new], keyfn)
        for k in sorted(set(g_old) & set(g_new)):
            os_, ns_ = g_old[k], g_new[k]
            if len(os_) == 1 and len(ns_) == 1:
                emit(os_[0], ns_[0], status, [why], 1.0)
            else:
                # ข้อความซ้ำในฉบับเดียวกัน ⇒ คนต้องเลือกเอง ห้ามเครื่องจับให้
                alts_o = [x.observation_id for x in os_]
                alts_n = [x.observation_id for x in ns_]
                for o in os_:
                    for n in ns_:
                        emit(o, n, AMBIGUOUS_REVIEW_REQUIRED,
                             [why, f"one_to_many:old={len(os_)},new={len(ns_)}"],
                             1.0, alts=[a for a in alts_o + alts_n
                                        if a not in (o.observation_id, n.observation_id)])

    # ── เฟส 3: คล้ายเชิงอักขระ — global greedy ตาม (คะแนน, id) ให้ผลไม่ขึ้นกับลำดับ ──
    rem_old = [o for o in old_sorted if o.observation_id not in used_old]
    rem_new = [n for n in new_sorted if n.observation_id not in used_new]
    tri_old = {o.observation_id: nz.trigrams(o.normalized_text) for o in rem_old}
    tri_new = {n.observation_id: nz.trigrams(n.normalized_text) for n in rem_new}
    scored: list[tuple[float, str, str]] = []
    for o in rem_old:
        for n in rem_new:
            s = nz.dice(tri_old[o.observation_id], tri_new[n.observation_id])
            if s >= rules.ambiguous_min:
                scored.append((s, o.observation_id, n.observation_id))
    scored.sort(key=lambda t: (-t[0], t[1], t[2]))
    by_old: dict[str, list[tuple[float, str]]] = {}
    by_new: dict[str, list[tuple[float, str]]] = {}
    for s, oid, nid in scored:
        by_old.setdefault(oid, []).append((s, nid))
        by_new.setdefault(nid, []).append((s, oid))
    obs_old = {o.observation_id: o for o in rem_old}
    obs_new = {n.observation_id: n for n in rem_new}
    for s, oid, nid in scored:
        if oid in used_old or nid in used_new:
            continue
        o, n = obs_old[oid], obs_new[nid]
        # คู่แข่งที่ยังว่างและคะแนนใกล้กัน ⇒ คลุมเครือ
        rivals_o = [x for sc, x in by_old[oid] if x != nid and x not in used_new
                    and s - sc <= rules.tie_margin]
        rivals_n = [x for sc, x in by_new[nid] if x != oid and x not in used_old
                    and s - sc <= rules.tie_margin]
        basis = [f"trigram_dice={s:.3f}"]
        diffs = differences(o, n)
        if rivals_o or rivals_n:
            emit(o, n, AMBIGUOUS_REVIEW_REQUIRED, basis + ["competing_candidates"],
                 s, alts=rivals_o + rivals_n)
            continue
        if s >= rules.rephrase_min:
            if _definition_changed(diffs):
                emit(o, n, DEFINITION_CHANGED,
                     basis + [f"{d.field_name}_differs" for d in diffs], s)
            else:
                emit(o, n, SAME_CONCEPT_REPHRASED, basis + ["fields_agree"], s)
        else:
            emit(o, n, AMBIGUOUS_REVIEW_REQUIRED, basis + ["below_rephrase_threshold"], s)

    # ── บัญชีที่เหลือ: ทุกข้อสังเกตต้องมีแถว ─────────────────────────────
    for o in old_sorted:
        if o.observation_id not in used_old:
            emit(o, None, REMOVED_INDICATOR, ["no_candidate_in_new"], 0.0)
    for n in new_sorted:
        if n.observation_id not in used_new:
            emit(None, n, NEW_INDICATOR, ["no_candidate_in_old"], 0.0)
    return out


def accounted(old: list[Observation], new: list[Observation],
              candidates: list[Candidate]) -> dict:
    """**Conservation gate** — บัญชีต้องปิดจริง ไม่ใช่แค่ "ไม่ขาดอย่างน้อยหนึ่งครั้ง" (B3)

    🔴 Bo (`5595832792` B3) — ของเดิม ``closed`` ไม่ล้มเมื่อแถวอ้าง id ที่ไม่มีใน input,
    เมื่อมีการนับซ้ำผิดรูป, หรือเมื่อรูปทรงของแถวไม่ตรงกับสถานะ ⇒ ยังไม่ใช่ conservation gate

    ด่านนี้ตรวจจากยอด **input ที่เป็นอิสระจากตัวแถว** เจ็ดข้อ

    ==  ===============================================================================
     1  ``unknown_old`` / ``unknown_new`` — แถวอ้าง id ที่ไม่มีในชุด input ⇒ ต้องเป็น 0
     2  ``missing_old`` / ``missing_new`` — id ใน input ที่ไม่มีแถวใดพูดถึง ⇒ ต้องเป็น 0
     3  ``duplicate_membership`` — id ที่ปรากฏหลายแถว **นอก** สถานะที่ประกาศรูปไว้
        (``AMBIGUOUS_REVIEW_REQUIRED``) ⇒ ต้องเป็น 0
     4  ``shape_violations`` — ``NEW_INDICATOR`` ต้องไม่มีฝั่งเก่า · ``REMOVED_INDICATOR``
        ต้องไม่มีฝั่งใหม่ · สถานะคู่ต้องมีสองฝั่ง · ทุกแถวต้องมีอย่างน้อยหนึ่งฝั่ง
     5  ``unknown_status`` — สถานะนอกบัญชีแปดสถานะ ⇒ ต้องเป็น 0
     6  ``duplicate_mapping_ids`` — ``mapping_id`` ซ้ำ ⇒ ต้องเป็น 0 (มิฉะนั้นบัญชีปิดแบบหลอก)
     7  ``per_status`` — ยอดรายสถานะต้องรวมได้เท่ายอดแถวทั้งหมด และยอดฝั่งรายสถานะ
        ต้องรวมได้เท่ายอด endpoint ทั้งหมดที่แถวอ้าง
    ==  ===============================================================================

    ``closed`` เป็นจริง **ก็ต่อเมื่อผ่านทุกข้อ** — ตัวเลขอื่นในผลลัพธ์มีไว้ให้อ่านว่าพังตรงไหน
    """
    old_ids = {o.observation_id for o in old}
    new_ids = {n.observation_id for n in new}

    unknown_old: list[str] = []
    unknown_new: list[str] = []
    seen_o: dict[str, int] = {}
    seen_n: dict[str, int] = {}
    shape: list[dict] = []
    unknown_status: list[str] = []
    per_status: dict[str, dict] = {}
    mapping_id_counts: dict[str, int] = {}
    endpoints = 0

    for c in candidates:
        mapping_id_counts[c.mapping_id] = mapping_id_counts.get(c.mapping_id, 0) + 1
        if c.proposed_status not in STATUSES:
            unknown_status.append(c.mapping_id)
        row = per_status.setdefault(c.proposed_status, {"rows": 0, "old": 0, "new": 0})
        row["rows"] += 1
        if c.old_observation_id:
            endpoints += 1
            row["old"] += 1
            seen_o[c.old_observation_id] = seen_o.get(c.old_observation_id, 0) + 1
            if c.old_observation_id not in old_ids:
                unknown_old.append(c.old_observation_id)
        if c.new_observation_id:
            endpoints += 1
            row["new"] += 1
            seen_n[c.new_observation_id] = seen_n.get(c.new_observation_id, 0) + 1
            if c.new_observation_id not in new_ids:
                unknown_new.append(c.new_observation_id)

        has_old, has_new = bool(c.old_observation_id), bool(c.new_observation_id)
        why = ""
        if not has_old and not has_new:
            why = "row_without_any_endpoint"
        elif c.proposed_status in NEW_ONLY_STATUSES and has_old:
            why = "new_indicator_must_not_have_old_side"
        elif c.proposed_status in OLD_ONLY_STATUSES and has_new:
            why = "removed_indicator_must_not_have_new_side"
        elif c.proposed_status in PAIRED_STATUSES and not (has_old and has_new):
            why = "paired_status_requires_both_sides"
        if why:
            shape.append({"mapping_id": c.mapping_id, "status": c.proposed_status,
                          "reason": why})

    dup_o = sorted(k for k, v in seen_o.items()
                   if v > 1 and not _all_rows_multi_allowed(candidates, k, "old"))
    dup_n = sorted(k for k, v in seen_n.items()
                   if v > 1 and not _all_rows_multi_allowed(candidates, k, "new"))
    dup_ids = sorted(k for k, v in mapping_id_counts.items() if v > 1)
    miss_o = sorted(old_ids - set(seen_o))
    miss_n = sorted(new_ids - set(seen_n))

    status_rows_total = sum(v["rows"] for v in per_status.values())
    status_endpoints_total = sum(v["old"] + v["new"] for v in per_status.values())
    totals_reconcile = (status_rows_total == len(candidates)
                        and status_endpoints_total == endpoints)

    checks = {
        "unknown_ids": not unknown_old and not unknown_new,
        "no_missing_ids": not miss_o and not miss_n,
        "duplicate_membership": not dup_o and not dup_n,
        "row_shapes": not shape,
        "known_statuses": not unknown_status,
        "unique_mapping_ids": not dup_ids,
        "totals_reconcile": totals_reconcile,
    }
    return {
        "old": len(old), "new": len(new), "rows": len(candidates),
        "old_accounted": len(seen_o), "new_accounted": len(seen_n),
        "endpoints": endpoints,
        "missing_old": miss_o, "missing_new": miss_n,
        "unknown_old": sorted(set(unknown_old)), "unknown_new": sorted(set(unknown_new)),
        "duplicate_old": dup_o, "duplicate_new": dup_n,
        "duplicate_mapping_ids": dup_ids,
        "shape_violations": shape, "unknown_status": sorted(set(unknown_status)),
        "per_status": {k: per_status[k] for k in sorted(per_status)},
        "checks": checks,
        "failed_checks": sorted(k for k, ok in checks.items() if not ok),
        "gate_version": MAPPING_VERSION,
        "closed": all(checks.values()),
    }


def _all_rows_multi_allowed(candidates, observation_id: str, side: str) -> bool:
    """ทุกแถวที่อ้าง id นี้อยู่ในสถานะที่ประกาศว่าซ้ำได้หรือไม่ (ความคลุมเครือที่ประกาศรูปไว้)"""
    attr = "old_observation_id" if side == "old" else "new_observation_id"
    rows = [c for c in candidates if getattr(c, attr) == observation_id]
    return bool(rows) and all(c.proposed_status in MULTI_ROW_ALLOWED for c in rows)


__all__ = [
    "MAPPING_VERSION", "STATUSES", "STATUS_LABELS", "HUMAN_REQUIRED",
    "MACHINE_MAY_PROPOSE", "SAME_FAMILY", "PAIRED_STATUSES", "NEW_ONLY_STATUSES",
    "OLD_ONLY_STATUSES", "MULTI_ROW_ALLOWED", "BASIS_CLIPPED",
    "SAME_EXACT", "SAME_WORDING_VARIANT",
    "SAME_CONCEPT_REPHRASED", "RELATED_NOT_EQUIVALENT", "DEFINITION_CHANGED",
    "NEW_INDICATOR", "REMOVED_INDICATOR", "AMBIGUOUS_REVIEW_REQUIRED",
    "Rules", "Difference", "Candidate", "differences", "propose", "accounted",
]
