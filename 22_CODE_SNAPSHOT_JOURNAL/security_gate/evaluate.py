# -*- coding: utf-8 -*-
"""กติกาแปลงผล check → สถานะ control (ประกาศล่วงหน้า · fail-closed)

สถานะ check ที่ runner ส่งเข้ามา

* ``PASS`` / ``FAIL`` — ผลตัดสินของ check นั้น
* ``INCOMPLETE`` — เครื่องมือไม่พร้อม/รันไม่จบ/อ่านผลไม่ได้
* ``RECORDED`` — บันทึกค่าไว้เฉย ๆ ไม่ตัดสิน (ใช้กับข้อ CONDITIONAL ที่ไม่บังคับใน profile นี้)
* ไม่มีใน dict เลย = ไม่ได้รัน

กติกาสถานะ control (ตรงกับคอลัมน์ ``disposition`` ของ matrix)

1. ``applicability == NOT_APPLICABLE`` ⇒ ``NOT_APPLICABLE``
2. ``applicability == CONDITIONAL`` และเงื่อนไข (TLS) ไม่เป็นจริงใน profile ⇒ ``NOT_APPLICABLE``
3. มี check ใด ``FAIL`` ⇒ ``FAIL``
4. มี check ใด ``INCOMPLETE``/ไม่ได้รัน/``RECORDED`` ทั้งที่ต้องตัดสิน ⇒ ``REVIEW``
5. control แบบ ``manual`` ⇒ ``REVIEW`` เสมอ (จนกว่าคนจะลง disposition) — แม้ทุก check PASS
6. ทุก check ``PASS`` ⇒ ``PASS``

🔴 ไม่มีทางใดที่ control จะได้ ``PASS`` โดยที่ check ที่ประกาศไว้ไม่ได้รันครบ
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import TLS_PROFILES
from .matrix import Control, Matrix

CHECK_STATUSES = ("PASS", "FAIL", "INCOMPLETE", "RECORDED")


@dataclass
class CheckResult:
    check_id: str
    status: str
    detail: dict = field(default_factory=dict)
    source: str = ""          # ไฟล์หลักฐานที่ผลนี้มาจาก (relative ใน evidence dir)

    def __post_init__(self):
        if self.status not in CHECK_STATUSES:
            raise ValueError(f"สถานะ check ไม่รู้จัก: {self.status}")


@dataclass
class ControlStatus:
    control_id: str
    status: str
    reason: str
    checks: dict[str, str]    # check_id → สถานะ (หรือ NOT_RUN)
    manual_disposition: dict | None = None


def _condition_met(control: Control, profile: str) -> bool:
    """ข้อ CONDITIONAL ใน matrix รุ่นนี้มีเงื่อนไขเดียวคือ TLS"""
    return profile in TLS_PROFILES


def control_status(control: Control, results: dict[str, CheckResult], profile: str,
                   manual_dispositions: dict[str, dict] | None = None) -> ControlStatus:
    manual_dispositions = manual_dispositions or {}
    per_check = {c: (results[c].status if c in results else "NOT_RUN") for c in control.checks}

    if control.applicability == "NOT_APPLICABLE":
        return ControlStatus(control.control_id, "NOT_APPLICABLE",
                             "ประกาศ NOT_APPLICABLE ใน matrix: " + control.profile_condition,
                             per_check)
    if control.applicability == "CONDITIONAL" and not _condition_met(control, profile):
        return ControlStatus(control.control_id, "NOT_APPLICABLE",
                             f"เงื่อนไขไม่บังคับใน profile {profile}: {control.profile_condition}",
                             per_check)

    statuses = set(per_check.values())
    if "FAIL" in statuses:
        failed = [c for c, s in per_check.items() if s == "FAIL"]
        return ControlStatus(control.control_id, "FAIL",
                             "check ไม่ผ่าน: " + ", ".join(failed), per_check,
                             manual_dispositions.get(control.control_id))
    not_decided = [c for c, s in per_check.items() if s != "PASS"]
    if not_decided:
        return ControlStatus(control.control_id, "REVIEW",
                             "check ไม่ได้รัน/ไม่ครบ/บันทึกอย่างเดียว (ห้ามนับ PASS): "
                             + ", ".join(f"{c}={per_check[c]}" for c in not_decided),
                             per_check, manual_dispositions.get(control.control_id))
    if control.manual:
        disp = manual_dispositions.get(control.control_id)
        # disposition นับก็ต่อเมื่อ **ผู้มีอำนาจรับแล้ว** (accepted_by ไม่ว่าง) และไม่ใช่ REVIEW_REQUIRED
        # — ข้อเสนอของ Giho อย่างเดียวยังไม่พอ (ตามใบ #23: Bo review → Gift accept)
        accepted = bool(disp and disp.get("accepted_by") and
                        disp.get("disposition") in ("FIXED", "ACCEPTED_RISK", "FALSE_POSITIVE"))
        if accepted:
            return ControlStatus(control.control_id, "PASS",
                                 f"ทุก check ผ่าน + disposition {disp['disposition']} "
                                 f"รับโดย {disp['accepted_by']}", per_check, disp)
        return ControlStatus(control.control_id, "REVIEW",
                             "control แบบ manual — ต้องมี disposition ที่ผู้มีอำนาจรับแล้ว"
                             + ((" (เสนอแล้ว: " + str(disp.get("disposition", "?")) + " · ยังไม่มี accepted_by)")
                                if disp else " (ยังไม่มี)"),
                             per_check, disp)
    return ControlStatus(control.control_id, "PASS", "ทุก check ที่ประกาศผ่าน", per_check)


def evaluate(matrix: Matrix, results: dict[str, CheckResult], profile: str,
             manual_dispositions: dict[str, dict] | None = None) -> list[ControlStatus]:
    return [control_status(c, results, profile, manual_dispositions) for c in matrix.controls]


def summarize(statuses: list[ControlStatus]) -> dict:
    counts = {"declared": len(statuses), "PASS": 0, "FAIL": 0, "REVIEW": 0, "NOT_APPLICABLE": 0}
    for s in statuses:
        counts[s.status] += 1
    counts["applicable"] = counts["declared"] - counts["NOT_APPLICABLE"]
    return counts


__all__ = ["CHECK_STATUSES", "CheckResult", "ControlStatus", "control_status", "evaluate",
           "summarize"]
