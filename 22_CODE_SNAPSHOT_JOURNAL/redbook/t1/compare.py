# -*- coding: utf-8 -*-
"""G4 — หมวดผลตรวจ C1–C7 (freeze: rules-t1-1.0.0)

ตามคำตัดสิน D-2569-08-27-12 ข้อ D3 · D9 · D10:
  - ห้ามเรียกรวมทุก finding ว่า "รายการปรับลด" — ต้องจำแนกตามหลักฐานจริง
  - C1 เรียกได้เพียง "วงเงินลดลง" ในเชิงผลต่างทางตัวเลข ห้ามสรุปสาเหตุ
  - tolerance = 0 บาท · ต่างกัน 1 บาทก็ต้องปรากฏ · **ห้ามซ่อน**
  - การย้ายโครงสร้างเป็น `possible_structure_move` รอ Human Review เสมอ
    ห้ามนับทันทีเป็น "ย้าย 1 รายการ" หรือ "หาย 1 + ใหม่ 1"
"""
from dataclasses import dataclass, field, asdict

from . import RULE_SET_VERSION_T1
from ..core.status import MachineStatus
from ..rules.policy import PCT_NO_BASE_MESSAGE, abs_diff, pct_change
from .matching import (MATCH_AMBIGUOUS, MATCH_EXACT, MATCH_RULE_BASED,
                       MATCH_SUGGESTED, MATCH_UNMATCHED)

# tolerance ที่ freeze แล้วสำหรับ T1 — ศูนย์บาท ห้ามเปลี่ยนโดยไม่ขึ้นเวอร์ชัน
AMOUNT_TOLERANCE_BAHT = 0

C1_AMOUNT_DECREASED = "C1"
C2_AMOUNT_INCREASED = "C2"
C3_AMOUNT_UNCHANGED = "C3"
C4_ITEM_ADDED = "C4"
C5_ITEM_MISSING = "C5"
C6_POSSIBLE_STRUCTURE_MOVE = "C6"
C7_UNRESOLVED = "C7"

CATEGORY_LABEL = {
    C1_AMOUNT_DECREASED: "วงเงินลดลง",
    C2_AMOUNT_INCREASED: "วงเงินเพิ่มขึ้น",
    C3_AMOUNT_UNCHANGED: "วงเงินไม่เปลี่ยนแปลง",
    C4_ITEM_ADDED: "รายการเพิ่ม",
    C5_ITEM_MISSING: "รายการหาย",
    C6_POSSIBLE_STRUCTURE_MOVE: "โครงสร้างเปลี่ยน (รอการยืนยัน)",
    C7_UNRESOLVED: "ยังตีความไม่ได้ ต้อง Human Review",
}

CATEGORY_MACHINE_STATUS = {
    C1_AMOUNT_DECREASED: MachineStatus.DIFF_FOUND.value,
    C2_AMOUNT_INCREASED: MachineStatus.DIFF_FOUND.value,
    C3_AMOUNT_UNCHANGED: MachineStatus.MATCH.value,
    C4_ITEM_ADDED: MachineStatus.NEEDS_HUMAN.value,
    C5_ITEM_MISSING: MachineStatus.NEEDS_HUMAN.value,
    C6_POSSIBLE_STRUCTURE_MOVE: MachineStatus.NEEDS_HUMAN.value,
    C7_UNRESOLVED: MachineStatus.NEEDS_HUMAN.value,
}

# หมวดที่ต้องแยกออกจากยอดสรุปที่ยืนยันแล้วเสมอ (D10)
CATEGORIES_PENDING_REVIEW = (C6_POSSIBLE_STRUCTURE_MOVE, C7_UNRESOLVED)


@dataclass
class T1Finding:
    category: str
    category_label: str
    machine_status: str
    match_level: str
    match_step: int
    key: tuple = ()
    amount_a: int = None
    amount_b: int = None
    amount_diff: int = None
    pct_change: float = None
    pct_note: str = ""
    unit: str = "บาท"
    evidence_a: dict = field(default_factory=dict)
    evidence_b: dict = field(default_factory=dict)
    match_score: float = None
    match_basis: str = ""
    reason: str = ""
    review_status: str = "pending"
    rule_set_version: str = RULE_SET_VERSION_T1

    def as_dict(self) -> dict:
        d = asdict(self)
        d["key"] = list(self.key)
        return d


def _amount(records, index):
    if index is None:
        return None
    rec = records[index]
    return rec.amount_normalized if rec.amount_normalized is not None else rec.amount_stored


def classify(pairs, records_a, records_b) -> list:
    """แปลงผลการจับคู่เป็น finding ตามหมวด C1–C7

    ทุกคู่และทุกเรคอร์ดที่ไม่จับคู่ได้ ต้องออกมาเป็น finding เสมอ — ไม่มีอะไรหายไป
    """
    findings = []
    for p in pairs:
        a_val = _amount(records_a, p.a_index)
        b_val = _amount(records_b, p.b_index)

        # ---- คู่ที่ระบบตีความไม่ได้ ----
        if p.match_level == MATCH_AMBIGUOUS:
            findings.append(T1Finding(
                category=C7_UNRESOLVED, category_label=CATEGORY_LABEL[C7_UNRESOLVED],
                machine_status=CATEGORY_MACHINE_STATUS[C7_UNRESOLVED],
                match_level=p.match_level, match_step=p.step, key=p.key,
                amount_a=a_val, amount_b=b_val,
                evidence_a=p.evidence_a, evidence_b=p.evidence_b,
                match_basis=p.score_basis,
                reason="พบความกำกวมในการจับคู่ ระบบไม่เลือกคู่ให้ ส่งให้ผู้ตรวจพิจารณา"))
            continue

        # ---- ไม่จับคู่ได้เลย ----
        if p.match_level == MATCH_UNMATCHED:
            if p.a_index is not None:
                findings.append(T1Finding(
                    category=C5_ITEM_MISSING, category_label=CATEGORY_LABEL[C5_ITEM_MISSING],
                    machine_status=CATEGORY_MACHINE_STATUS[C5_ITEM_MISSING],
                    match_level=p.match_level, match_step=p.step, key=p.key,
                    amount_a=a_val, evidence_a=p.evidence_a,
                    match_basis=p.score_basis,
                    reason="พบรายการนี้ในฝั่ง A แต่ไม่พบคู่ในฝั่ง B"))
            else:
                findings.append(T1Finding(
                    category=C4_ITEM_ADDED, category_label=CATEGORY_LABEL[C4_ITEM_ADDED],
                    machine_status=CATEGORY_MACHINE_STATUS[C4_ITEM_ADDED],
                    match_level=p.match_level, match_step=p.step, key=p.key,
                    amount_b=b_val, evidence_b=p.evidence_b,
                    match_basis=p.score_basis,
                    reason="พบรายการนี้ในฝั่ง B แต่ไม่พบคู่ในฝั่ง A"))
            continue

        # ---- คู่ที่จับได้จากขั้นที่ 3 หรือ 4 = ยังไม่ยืนยัน ----
        if p.match_level == MATCH_SUGGESTED:
            findings.append(T1Finding(
                category=C6_POSSIBLE_STRUCTURE_MOVE,
                category_label=CATEGORY_LABEL[C6_POSSIBLE_STRUCTURE_MOVE],
                machine_status=CATEGORY_MACHINE_STATUS[C6_POSSIBLE_STRUCTURE_MOVE],
                match_level=p.match_level, match_step=p.step, key=p.key,
                amount_a=a_val, amount_b=b_val, amount_diff=abs_diff(a_val, b_val),
                evidence_a=p.evidence_a, evidence_b=p.evidence_b,
                match_score=p.score, match_basis=p.score_basis,
                reason=("ระบบเสนอว่าอาจเป็นรายการเดียวกันที่ย้ายสายลำดับชั้นหรือเปลี่ยนชื่อ "
                        "ยังไม่นับเป็นการย้าย และยังไม่นับเป็นรายการหายหรือรายการใหม่ "
                        "จนกว่าผู้ตรวจจะยืนยัน")))
            continue

        # ---- คู่ที่จับได้แน่นอน (ขั้นที่ 1–2) → เทียบจำนวนเงิน ----
        if a_val is None or b_val is None:
            findings.append(T1Finding(
                category=C7_UNRESOLVED, category_label=CATEGORY_LABEL[C7_UNRESOLVED],
                machine_status=CATEGORY_MACHINE_STATUS[C7_UNRESOLVED],
                match_level=p.match_level, match_step=p.step, key=p.key,
                amount_a=a_val, amount_b=b_val,
                evidence_a=p.evidence_a, evidence_b=p.evidence_b,
                match_basis=p.score_basis,
                reason="จับคู่ได้แต่มีฝั่งที่อ่านจำนวนเงินไม่ได้ ระบบไม่เดาค่าแทน"))
            continue

        diff = int(b_val) - int(a_val)
        pct, note = pct_change(a_val, b_val)
        if abs(diff) <= AMOUNT_TOLERANCE_BAHT:
            cat, reason = C3_AMOUNT_UNCHANGED, "จำนวนเงินสองฝั่งเท่ากันทุกบาท"
        elif diff < 0:
            cat = C1_AMOUNT_DECREASED
            reason = ("จำนวนเงินฝั่ง B ต่ำกว่าฝั่ง A — เป็นผลต่างทางตัวเลขเท่านั้น "
                      "ระบบไม่สรุปสาเหตุของการเปลี่ยนแปลง")
        else:
            cat = C2_AMOUNT_INCREASED
            reason = ("จำนวนเงินฝั่ง B สูงกว่าฝั่ง A — เป็นผลต่างทางตัวเลขเท่านั้น "
                      "ระบบไม่สรุปสาเหตุของการเปลี่ยนแปลง")

        findings.append(T1Finding(
            category=cat, category_label=CATEGORY_LABEL[cat],
            machine_status=CATEGORY_MACHINE_STATUS[cat],
            match_level=p.match_level, match_step=p.step, key=p.key,
            amount_a=int(a_val), amount_b=int(b_val), amount_diff=diff,
            pct_change=pct, pct_note=note or "",
            evidence_a=p.evidence_a, evidence_b=p.evidence_b,
            match_score=p.score, match_basis=p.score_basis, reason=reason))
    return findings


def summarize(findings) -> dict:
    """สรุปจำนวนตามหมวด พร้อมแยกยอดที่ยังรอการยืนยันออกจากยอดที่สรุปได้"""
    counts = {c: 0 for c in CATEGORY_LABEL}
    for f in findings:
        counts[f.category] = counts.get(f.category, 0) + 1
    pending = sum(counts[c] for c in CATEGORIES_PENDING_REVIEW)
    settled = sum(v for k, v in counts.items() if k not in CATEGORIES_PENDING_REVIEW)
    total_decrease = sum(f.amount_diff for f in findings
                         if f.category == C1_AMOUNT_DECREASED and f.amount_diff is not None)
    total_increase = sum(f.amount_diff for f in findings
                         if f.category == C2_AMOUNT_INCREASED and f.amount_diff is not None)
    return {
        "counts": counts,
        "labels": dict(CATEGORY_LABEL),
        "total_findings": len(findings),
        "settled_count": settled,
        "pending_review_count": pending,
        "sum_amount_decreased": total_decrease,
        "sum_amount_increased": total_increase,
        "tolerance_baht": AMOUNT_TOLERANCE_BAHT,
        "rule_set_version": RULE_SET_VERSION_T1,
        "note": ("ยอดในหมวดที่รอการยืนยัน (C6, C7) แยกออกจากยอดที่สรุปได้แล้ว "
                 "และห้ามนำไปรวมกันก่อนผู้ตรวจยืนยัน"),
        "pct_no_base_message": PCT_NO_BASE_MESSAGE,
    }
