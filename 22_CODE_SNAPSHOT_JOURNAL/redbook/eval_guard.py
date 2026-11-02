# -*- coding: utf-8 -*-
"""ด่านกันหน่วยงานในชุดประเมิน (5 หน่วยงาน) จนกว่าจะตรึงรุ่น — #44 ด่าน G4 · กิ๊ฟสั่ง 28 ต.ค. 2569

ทำไมบังคับในโค้ด: ผลประเมินเสียทันทีถ้าระบบเคยถูกเปิด/ปรับด้วยเล่มของหน่วยงานในชุดประเมินก่อนตรึง และพิสูจน์ย้อนหลัง
ไม่ได้ — ข้อตกลงระหว่างคนไม่ทิ้งหลักฐาน (หลักเดียวกับ :mod:`redbook.holdout`) · การเปิดให้อัปโหลด PDF เองทำให้ช่องนี้
เปิดได้ง่ายขึ้น จึงต้องมาพร้อมกัน

**รายชื่ออยู่นอก repository** — ไฟล์ JSON ส่วนตัว (ไม่ขึ้น Git ไม่ขึ้น Issue)::

    {"agencies": ["ชื่อหน่วยงาน 1", "…"], "unlocked_for_pdfbook": ""}

ตำแหน่ง: ``REDBOOK_EVAL_GUARD`` หรือ ``~/.redbook/eval_guard.json`` (ร่วมกันทุกเซิร์ฟเวอร์ในเครื่อง)

* หน่วยงานในรายชื่อ = **ปฏิเสธ** การเริ่มรอบเทียบทุกทาง (ชั้นเล่ม · หน้าเดิม · API · สายทดลองที่เรียก ``pdfpair.run``)
  และ **ไม่แสดง** ในรายชื่อหน่วยงานให้เลือก
* เปิดได้เฉพาะเมื่อ ``unlocked_for_pdfbook`` = รุ่นตัวสกัดที่กำลังรัน (ตั้งหลังตรึงรุ่นแล้วเท่านั้น) — รุ่นเปลี่ยน = ปิดเองอีกครั้ง
* ไม่มีไฟล์ / อ่านไม่ได้ = ด่าน **ยังไม่ได้ตั้งค่า** — :func:`status` รายงานไว้ให้ตรวจ (G4 ต้องเห็น ``configured``)
* ทุกครั้งที่ปฏิเสธ บันทึกเหตุการณ์ความปลอดภัยโดยไม่ใส่ชื่อหน่วยงาน
"""
from __future__ import annotations

import json
import os
from pathlib import Path

GUARD_ENV = "REDBOOK_EVAL_GUARD"
BLOCKED_MESSAGE = ("หน่วยงานนี้อยู่ในชุดประเมิน — ระบบไม่เปิดเล่มของหน่วยงานนี้จนกว่าจะตรึงรุ่นเครื่องมือ "
                   "(กันผลประเมินเสีย)")


class EvalAgencyBlocked(ValueError):
    pass


def guard_path() -> Path:
    return Path(os.environ.get(GUARD_ENV) or (Path.home() / ".redbook" / "eval_guard.json"))


def _load() -> dict | None:
    try:
        d = json.loads(guard_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or not isinstance(d.get("agencies"), list):
        return None
    return d


def _key(name: str) -> str:
    from .pdfbook.text import skeleton
    return skeleton(name or "")


def _unlocked(d: dict) -> bool:
    from .pdfbook import PDFBOOK_VERSION
    return bool(d.get("unlocked_for_pdfbook")) and d.get("unlocked_for_pdfbook") == PDFBOOK_VERSION


def is_blocked(name: str) -> bool:
    """ชื่อหน่วยงานตรงกับรายชื่อชุดประเมิน (เทียบแบบตัดวรรณยุกต์/ช่องว่าง · ชื่อหนึ่งอยู่ในอีกชื่อ) และยังไม่ปลดล็อก"""
    d = _load()
    if not d or _unlocked(d):
        return False
    k = _key(name)
    if len(k) < 4:
        return False
    return any((e := _key(x)) and len(e) >= 4 and (e in k or k in e) for x in d["agencies"] if isinstance(x, str))


def check(name: str, where: str) -> None:
    """ปฏิเสธ + บันทึกเหตุการณ์ (ไม่ใส่ชื่อ) ถ้าหน่วยงานอยู่ในชุดประเมินที่ยังไม่ปลดล็อก"""
    if is_blocked(name):
        try:
            from .storage import audit
            audit.security_event("eval_agency_blocked", "warning", {"where": where})
        except Exception:  # noqa: BLE001 — บันทึกล้มต้องไม่ทำให้การปฏิเสธล้ม
            pass
        raise EvalAgencyBlocked(BLOCKED_MESSAGE)


def locked() -> bool:
    """มีรายชื่อชุดประเมินและยังไม่ปลดล็อก — ระหว่างนี้รอบที่ยืนยันไม่ได้ว่าอยู่นอกชุดประเมินต้องถูกปฏิเสธ"""
    d = _load()
    return bool(d) and not _unlocked(d) and any(isinstance(x, str) and x.strip() for x in d["agencies"])


def refuse(event: str, where: str, message: str) -> None:
    """บันทึกเหตุการณ์ (ไม่ใส่ชื่อ/ช่วงหน้า) แล้วปฏิเสธ"""
    try:
        from .storage import audit
        audit.security_event(event, "warning", {"where": where})
    except Exception:  # noqa: BLE001
        pass
    raise EvalAgencyBlocked(message)


def status() -> dict:
    """สถานะด่าน (ไม่เปิดเผยรายชื่อ) — สำหรับ ``/api/lane`` และหลักฐาน G4"""
    from .pdfbook import PDFBOOK_VERSION
    d = _load()
    if d is None:
        return {"configured": False, "agencies": 0, "unlocked": False, "pdfbook": PDFBOOK_VERSION}
    return {"configured": True, "agencies": sum(1 for x in d["agencies"] if isinstance(x, str) and x.strip()),
            "unlocked": _unlocked(d), "pdfbook": PDFBOOK_VERSION}


__all__ = ["GUARD_ENV", "BLOCKED_MESSAGE", "EvalAgencyBlocked", "guard_path", "is_blocked", "check", "locked", "refuse",
           "status"]
