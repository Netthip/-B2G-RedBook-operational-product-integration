# -*- coding: utf-8 -*-
"""G3 (ส่วนที่ 2) — คีย์ผสม 9 บทบาท และ pipeline การจับคู่ 5 ขั้น

freeze: key-t1-1.0.0 · ตาม D-2569-08-27-10 และ D-2569-08-27-12 ข้อ D7

ข้อบังคับที่โค้ดรับประกัน:
  - คีย์สร้างจาก **บทบาทข้อมูล (canonical field)** เท่านั้น ไม่แตะชื่อคอลัมน์กายภาพ
  - `row_ordinal` ไม่ปรากฏในคีย์เลย — ห้ามใช้ลำดับแถวเป็น identity ข้ามไฟล์
  - ขั้นที่ 3–4 คืนผลเป็น `suggested` เสมอ ระบบไม่รวมรายการให้อัตโนมัติ
  - ชื่อซ้ำใน parent เดียวกัน → `ambiguous` ส่ง Human Review
"""
from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher

from . import COMPOSITE_KEY_VERSION
from .normalize import normalize_for_key, normalize_name

# คีย์ผสม 9 บทบาทตามลำดับที่อนุมัติ
COMPOSITE_KEY_ROLES = (
    "agency_code",            # 1 agency
    "budget_group",           # 2 budget group
    "plan_name",              # 3 plan
    "output_name",            # 4 output
    "activity_name",          # 5 activity
    "objective_category",     # 6 objective category
    "objective_subcategory",  # 7 objective subcategory
    "capital_class",          # 8 capital / non-capital class
    "item_label",             # 9 item name
)

# บทบาทที่ประกอบเป็น parent path (8 ตัวแรก)
PARENT_ROLES = COMPOSITE_KEY_ROLES[:-1]

MATCH_EXACT = "exact"
MATCH_RULE_BASED = "rule_based"
MATCH_SUGGESTED = "suggested"
MATCH_AMBIGUOUS = "ambiguous"
MATCH_UNMATCHED = "unmatched"

# เกณฑ์ความคล้ายขั้นต่ำของขั้นที่ 4 — ต่ำกว่านี้ไม่เสนอเลย
FUZZY_MIN_RATIO = 0.85

# ขั้นที่ 3 ยอมให้สายลำดับชั้นต่างกันได้ไม่เกินกี่บทบาท จึงจะยังถือว่าอาจเป็นรายการเดียวกัน
# ตั้งไว้ที่ 1 เพราะการย้ายจริงมักเปลี่ยนชั้นเดียว ส่วนการต่างกันหลายชั้นแปลว่าคนละรายการ
MAX_PARENT_DIFF_ROLES = 1


def composite_key(record) -> tuple:
    """คีย์ผสม 9 บทบาท — ใช้ค่าที่ผ่านการปรับรูปแล้ว"""
    parts = []
    for role in COMPOSITE_KEY_ROLES:
        value = getattr(record, role, None)
        if role == "item_label":
            parts.append(normalize_name(value)["comparable"])
        else:
            parts.append(normalize_for_key(value))
    return tuple(parts)


def parent_path(record) -> tuple:
    return tuple(normalize_for_key(getattr(record, role, None)) for role in PARENT_ROLES)


def item_comparable(record) -> str:
    return normalize_name(getattr(record, "item_label", None))["comparable"]


@dataclass
class MatchPair:
    """ผลการจับคู่หนึ่งคู่ พร้อมหลักฐานครบตามที่กำหนด"""

    match_level: str
    key: tuple = ()
    a_index: int = None          # ตำแหน่งใน list ฝั่ง A
    b_index: int = None
    score: float = None
    score_basis: str = ""
    step: int = 0                # ขั้นของ pipeline ที่ทำให้จับคู่ได้
    evidence_a: dict = field(default_factory=dict)
    evidence_b: dict = field(default_factory=dict)
    note: str = ""
    key_version: str = COMPOSITE_KEY_VERSION

    def as_dict(self) -> dict:
        d = asdict(self)
        d["key"] = list(self.key)
        return d


def _evidence(record) -> dict:
    loc = getattr(record, "evidence_location", None)
    return loc.as_dict() if loc is not None else {}


def _index_by(records, keyfunc):
    out = {}
    for i, r in enumerate(records):
        out.setdefault(keyfunc(r), []).append(i)
    return out


def match_records(records_a, records_b) -> list:
    """เดิน pipeline 5 ขั้น คืนรายการ MatchPair ครบทุกเรคอร์ดทั้งสองฝั่ง

    เรคอร์ดที่จับคู่ไม่ได้จะปรากฏเป็น MatchPair ระดับ `unmatched` โดยมี index
    เพียงฝั่งเดียว — ไม่มีเรคอร์ดใดหายไปจากผลลัพธ์
    """
    pairs = []
    used_a, used_b = set(), set()

    # ---- ขั้นที่ 1: exact composite key ----
    idx_a = _index_by(records_a, composite_key)
    idx_b = _index_by(records_b, composite_key)
    for key, a_list in idx_a.items():
        b_list = idx_b.get(key)
        if not b_list:
            continue
        if len(a_list) > 1 or len(b_list) > 1:
            # ---- ขั้นที่ 5: คีย์ซ้ำใน parent เดียวกัน → ambiguous ----
            pairs.append(MatchPair(
                match_level=MATCH_AMBIGUOUS, key=key, step=5,
                score_basis=(f"คีย์นี้ปรากฏซ้ำ — ฝั่ง A {len(a_list)} แถว · "
                             f"ฝั่ง B {len(b_list)} แถว"),
                evidence_a={"rows": [_evidence(records_a[i]) for i in a_list]},
                evidence_b={"rows": [_evidence(records_b[i]) for i in b_list]},
                note="ชื่อซ้ำภายใต้สายลำดับชั้นเดียวกัน ระบบไม่เลือกคู่ให้ ส่ง Human Review"))
            used_a.update(a_list)
            used_b.update(b_list)
            continue
        ai, bi = a_list[0], b_list[0]
        pairs.append(MatchPair(
            match_level=MATCH_EXACT, key=key, a_index=ai, b_index=bi, step=1,
            score=1.0, score_basis="คีย์ผสม 9 บทบาทตรงกันทุกช่องหลังปรับรูป",
            evidence_a=_evidence(records_a[ai]), evidence_b=_evidence(records_b[bi])))
        used_a.add(ai)
        used_b.add(bi)

    # ---- ขั้นที่ 2: ชื่อรายการตรงกัน + parent path ตรงกัน ----
    # (ในทางปฏิบัติซ้อนกับขั้นที่ 1 สำหรับ T1 แต่คงไว้เพื่อรองรับชุดข้อมูลอื่น)
    rest_a = [i for i in range(len(records_a)) if i not in used_a]
    rest_b = [i for i in range(len(records_b)) if i not in used_b]
    idx2_b = {}
    for i in rest_b:
        idx2_b.setdefault((parent_path(records_b[i]), item_comparable(records_b[i])),
                          []).append(i)
    for ai in list(rest_a):
        if ai in used_a:
            continue
        k = (parent_path(records_a[ai]), item_comparable(records_a[ai]))
        cands = [i for i in idx2_b.get(k, []) if i not in used_b]
        if len(cands) == 1:
            bi = cands[0]
            pairs.append(MatchPair(
                match_level=MATCH_RULE_BASED, key=composite_key(records_a[ai]),
                a_index=ai, b_index=bi, step=2, score=1.0,
                score_basis="ชื่อรายการและสายลำดับชั้นเหนือระดับรายการตรงกัน",
                evidence_a=_evidence(records_a[ai]), evidence_b=_evidence(records_b[bi])))
            used_a.add(ai)
            used_b.add(bi)

    # ---- ขั้นที่ 3: ชื่อเดิม และสายลำดับชั้น "ต่างเพียงเล็กน้อย" → suggested ----
    # ข้อบังคับ: ต้องต่างกันไม่เกิน MAX_PARENT_DIFF_ROLES บทบาท มิฉะนั้นไม่ถือเป็นคู่
    # (ชื่อรายการในชุดข้อมูลนี้อาจเป็นค่าประเภทที่ซ้ำกันมาก การเทียบชื่ออย่างเดียว
    #  จะจับคู่ผิดข้ามหน่วยงานได้)
    rest_a = [i for i in range(len(records_a)) if i not in used_a]
    rest_b = [i for i in range(len(records_b)) if i not in used_b]
    idx3_b = {}
    for i in rest_b:
        idx3_b.setdefault(item_comparable(records_b[i]), []).append(i)
    for ai in list(rest_a):
        if ai in used_a:
            continue
        name = item_comparable(records_a[ai])
        pa = parent_path(records_a[ai])
        scored = []
        for bi in idx3_b.get(name, []):
            if bi in used_b:
                continue
            pb = parent_path(records_b[bi])
            diff = [PARENT_ROLES[k] for k in range(len(PARENT_ROLES)) if pa[k] != pb[k]]
            if len(diff) <= MAX_PARENT_DIFF_ROLES:
                scored.append((len(diff), bi, diff))
        if not scored:
            continue
        scored.sort(key=lambda t: (t[0], t[1]))
        best_distance = scored[0][0]
        closest = [t for t in scored if t[0] == best_distance]
        if len(closest) == 1:
            _, bi, changed = closest[0]
            pairs.append(MatchPair(
                match_level=MATCH_SUGGESTED, key=composite_key(records_a[ai]),
                a_index=ai, b_index=bi, step=3, score=0.9,
                score_basis=("ชื่อรายการตรงกันและสายลำดับชั้นต่างกันเพียง "
                             f"{best_distance} บทบาท: " + ", ".join(changed)),
                evidence_a=_evidence(records_a[ai]), evidence_b=_evidence(records_b[bi]),
                note="ระบบไม่รวมรายการให้อัตโนมัติ ต้องให้มนุษย์ยืนยันก่อน"))
            used_a.add(ai)
            used_b.add(bi)
        else:
            pairs.append(MatchPair(
                match_level=MATCH_AMBIGUOUS, key=composite_key(records_a[ai]),
                a_index=ai, step=5,
                score_basis=(f"ชื่อรายการนี้ใกล้เคียงกับฝั่ง B {len(closest)} แถวเท่ากัน "
                             f"(ต่างกัน {best_distance} บทบาทเท่ากันทุกแถว)"),
                evidence_a=_evidence(records_a[ai]),
                evidence_b={"rows": [_evidence(records_b[t[1]]) for t in closest]},
                note="ระบบไม่เลือกคู่ให้ ส่ง Human Review"))
            used_a.add(ai)

    # ---- ขั้นที่ 4: ความคล้ายของชื่อภายใต้ parent เดียวกัน → suggested เท่านั้น ----
    rest_a = [i for i in range(len(records_a)) if i not in used_a]
    rest_b = [i for i in range(len(records_b)) if i not in used_b]
    for ai in list(rest_a):
        if ai in used_a:
            continue
        pa, na = parent_path(records_a[ai]), item_comparable(records_a[ai])
        best, best_ratio = None, 0.0
        for bi in rest_b:
            if bi in used_b or parent_path(records_b[bi]) != pa:
                continue
            ratio = SequenceMatcher(None, na, item_comparable(records_b[bi])).ratio()
            if ratio > best_ratio:
                best, best_ratio = bi, ratio
        if best is not None and best_ratio >= FUZZY_MIN_RATIO:
            pairs.append(MatchPair(
                match_level=MATCH_SUGGESTED, key=composite_key(records_a[ai]),
                a_index=ai, b_index=best, step=4, score=round(best_ratio, 4),
                score_basis=(f"ความคล้ายของชื่อรายการภายใต้สายลำดับชั้นเดียวกัน "
                             f"= {best_ratio:.4f} (เกณฑ์ขั้นต่ำ {FUZZY_MIN_RATIO})"),
                evidence_a=_evidence(records_a[ai]), evidence_b=_evidence(records_b[best]),
                note="ผลจากการเทียบความคล้าย ต้องให้มนุษย์ยืนยันเท่านั้น"))
            used_a.add(ai)
            used_b.add(best)

    # ---- เรคอร์ดที่เหลือ = unmatched ----
    for ai in range(len(records_a)):
        if ai not in used_a:
            pairs.append(MatchPair(
                match_level=MATCH_UNMATCHED, key=composite_key(records_a[ai]),
                a_index=ai, step=0, score_basis="ไม่พบคู่ในฝั่ง B ทุกขั้นของ pipeline",
                evidence_a=_evidence(records_a[ai])))
    for bi in range(len(records_b)):
        if bi not in used_b:
            pairs.append(MatchPair(
                match_level=MATCH_UNMATCHED, key=composite_key(records_b[bi]),
                b_index=bi, step=0, score_basis="ไม่พบคู่ในฝั่ง A ทุกขั้นของ pipeline",
                evidence_b=_evidence(records_b[bi])))
    return pairs
