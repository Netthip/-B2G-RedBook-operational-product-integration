# -*- coding: utf-8 -*-
"""ขั้นตอนการทำงาน 1–6 ของโต๊ะตรวจคาดแดง — **สถานะที่คำนวณได้ ไม่ใช่ค่าที่เก็บไว้**

เหตุผลที่ต้องมีชั้นนี้ (คำสั่งกิ๊ฟ 23 ก.ย. 2569):
    เดิมผู้ใช้เปิดหน้าใดหน้าหนึ่งแล้วไม่รู้ว่าตัวเองอยู่ตรงไหนของงาน และเหลืออะไร
    ต้องทำ · ทางเข้าบางหน้าไปถึงได้ด้วยการพิมพ์ URL เท่านั้น

🔴 หลักการเดียวกับ :func:`redbook.services.t1b.readiness_of` — **ไม่มี setter**
สถานะของแต่ละขั้นคำนวณจากของจริงทุกครั้งที่เปิดหน้า ถ้าเก็บลงฐานข้อมูล
ค่าที่เก็บกับความจริงจะเพี้ยนจากกันทันทีที่ผู้ใช้ทำอะไรนอกเส้นทางที่คาดไว้

🔴 ชั้นนี้ **ห้าม import fastapi/jinja2** และห้ามเรียกเครื่องยนต์ ``redbook.t1b.*``
โดยตรง — รับค่าที่นับมาแล้วเข้ามาเป็นพารามิเตอร์เท่านั้น
"""
from __future__ import annotations

from dataclasses import dataclass, field

WORKFLOW_SERVICE_VERSION = "redbook-workflow-0.1.0"

# ---------------------------------------------------------------- สถานะของขั้น
#: ทำเสร็จแล้ว
DONE = "DONE"
#: กำลังอยู่ขั้นนี้
CURRENT = "CURRENT"
#: ยังมาไม่ถึง
TODO = "TODO"
#: มาถึงแล้วแต่ทำต่อไม่ได้ เพราะยังติดเงื่อนไขของขั้นก่อนหน้า
BLOCKED = "BLOCKED"

STATE_LABELS = {
    DONE: "เสร็จแล้ว",
    CURRENT: "กำลังทำ",
    TODO: "ยังไม่ถึงขั้นนี้",
    BLOCKED: "ยังทำต่อไม่ได้",
}

# ---------------------------------------------------------------- รหัสของขั้น
STEP_PROJECT = "project"
STEP_UPLOAD = "upload"
STEP_ANALYZE = "analyze"
STEP_REVIEW = "review"
STEP_PREFLIGHT = "preflight"
STEP_EXPORT = "export"

#: ลำดับคงที่ — เลขขั้นบนหน้าจอมาจากตำแหน่งในลิสต์นี้ ห้ามสลับ
STEP_ORDER = (STEP_PROJECT, STEP_UPLOAD, STEP_ANALYZE,
              STEP_REVIEW, STEP_PREFLIGHT, STEP_EXPORT)

#: ชื่อขั้นบนหน้าจอ — ภาษาที่คนทำงบใช้ ไม่ใช่ศัพท์ของระบบ
STEP_LABELS = {
    STEP_PROJECT: "ตั้งงานตรวจ",
    STEP_UPLOAD: "ใส่ไฟล์สองฉบับ",
    STEP_ANALYZE: "ให้ระบบหาความต่าง",
    STEP_REVIEW: "พิจารณาทีละรายการ",
    STEP_PREFLIGHT: "ตรวจก่อนส่งออก",
    STEP_EXPORT: "ส่งออกชุดงาน",
}


@dataclass(frozen=True)
class Step:
    """หนึ่งขั้นบนแถบขั้นตอน"""

    no: int
    code: str
    label: str
    state: str
    #: สิ่งที่ยังค้างของขั้นนี้ — ว่างได้ ถ้าไม่มีอะไรค้าง
    detail: str = ""
    #: ลิงก์ไปหน้าที่ทำขั้นนี้ — ว่าง = ยังกดไม่ได้
    href: str = ""

    @property
    def state_label(self) -> str:
        return STATE_LABELS.get(self.state, self.state)

    @property
    def clickable(self) -> bool:
        return bool(self.href)


@dataclass(frozen=True)
class Workflow:
    """แถบขั้นตอนทั้งเส้นของงานหนึ่งชิ้น"""

    steps: tuple[Step, ...] = field(default_factory=tuple)

    @property
    def current(self) -> Step | None:
        for s in self.steps:
            if s.state in (CURRENT, BLOCKED):
                return s
        return None

    @property
    def done_count(self) -> int:
        return sum(1 for s in self.steps if s.state == DONE)

    @property
    def outstanding(self) -> tuple[Step, ...]:
        """ขั้นที่ยังมีงานค้างและอธิบายได้ว่าค้างอะไร"""
        return tuple(s for s in self.steps
                     if s.state in (CURRENT, BLOCKED) and s.detail)


def _state(index: int, current_index: int, done_through: int,
           blocked: bool) -> str:
    if index <= done_through:
        return DONE
    if index == current_index:
        return BLOCKED if blocked else CURRENT
    return TODO


def build(*, current: str, project_id: str = "", run_id: str = "",
          files_ready: bool = False, analyzed: bool = False,
          pending: int = 0, total_findings: int = 0,
          preflight_ok: bool | None = None, preflight_blocking: int = 0,
          exported: bool = False) -> Workflow:
    """ประกอบแถบขั้นตอนจากข้อเท็จจริงที่ผู้เรียกนับมาแล้ว

    ``current``           รหัสขั้นที่หน้านี้อยู่
    ``files_ready``       อัปโหลดครบทั้งฝั่ง A และ B แล้วหรือยัง
    ``analyzed``          มีรอบตรวจของงานนี้แล้วหรือยัง
    ``pending``           จำนวนรายการที่ยังไม่ได้ตัดสิน
    ``preflight_ok``      ``None`` = ยังไม่ได้ตรวจ (ยังไม่ถึงขั้น)
    ``exported``          สร้างไฟล์ส่งออกแล้วหรือยัง
    """
    done_through = 0                      # ขั้นที่ 1 ถือว่าเสร็จเมื่อมีงานตรวจแล้ว
    if project_id or run_id:
        done_through = 1
    if files_ready or analyzed:
        done_through = 2
    if analyzed:
        done_through = 3
    if analyzed and pending == 0 and total_findings:
        done_through = 4
    if preflight_ok:
        done_through = 5
    if exported:
        done_through = 6

    current_index = STEP_ORDER.index(current) + 1 if current in STEP_ORDER else 0
    if current_index <= done_through:
        current_index = min(done_through + 1, len(STEP_ORDER))

    run_base = f"/t1b/runs/{run_id}" if run_id else ""
    details = {
        STEP_UPLOAD: "" if files_ready or analyzed else "ยังใส่ไฟล์ไม่ครบสองฉบับ",
        STEP_ANALYZE: "" if analyzed else "ยังไม่ได้ให้ระบบหาความต่าง",
        STEP_REVIEW: (f"เหลือ {pending} รายการที่ยังไม่ได้ตัดสิน"
                      if analyzed and pending else ""),
        STEP_PREFLIGHT: (f"ติดเงื่อนไข {preflight_blocking} ข้อ"
                         if preflight_blocking else ""),
        STEP_EXPORT: "" if exported else "ยังไม่ได้สร้างไฟล์ส่งออก",
    }
    hrefs = {
        STEP_PROJECT: f"/projects/{project_id}" if project_id else "/projects/new",
        STEP_UPLOAD: f"/projects/{project_id}" if project_id else "",
        STEP_ANALYZE: run_base or (f"/projects/{project_id}" if project_id else ""),
        STEP_REVIEW: f"{run_base}/queue" if run_base else "",
        STEP_PREFLIGHT: f"{run_base}/preflight" if run_base else "",
        STEP_EXPORT: f"{run_base}/export" if run_base else "",
    }

    steps = []
    for index, code in enumerate(STEP_ORDER, start=1):
        blocked = (index == current_index
                   and code == STEP_EXPORT and preflight_ok is False)
        steps.append(Step(
            no=index, code=code, label=STEP_LABELS[code],
            state=_state(index, current_index, done_through, blocked),
            detail=details.get(code, ""), href=hrefs.get(code, ""),
        ))
    return Workflow(steps=tuple(steps))


__all__ = [
    "WORKFLOW_SERVICE_VERSION", "DONE", "CURRENT", "TODO", "BLOCKED",
    "STATE_LABELS", "STEP_ORDER", "STEP_LABELS", "Step", "Workflow", "build",
    "STEP_PROJECT", "STEP_UPLOAD", "STEP_ANALYZE", "STEP_REVIEW",
    "STEP_PREFLIGHT", "STEP_EXPORT",
]
