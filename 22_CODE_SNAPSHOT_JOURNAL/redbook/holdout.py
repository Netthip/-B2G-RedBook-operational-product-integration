# -*- coding: utf-8 -*-
"""ด่านกันชุดข้อมูลกันไว้ (holdout) — บังคับด้วยโค้ด ไม่ใช่ด้วยวินัย

🔴 **คำสั่งกิ๊ฟ (7 ก.ย. 2569)** — การย้าย P1 ไปไว้ในโฟลเดอร์ย่อยถือว่า
*แยกทางกายภาพพอใช้ได้* แต่ **ยังไม่ถือว่าเป็น holdout ที่พิสูจน์แล้ว
จนกว่าโค้ดจะบังคับไม่ให้แตะ*

ทำไมต้องบังคับ ไม่ใช่แค่ตกลงกัน
------------------------------
P1 เป็นชุดข้อมูลที่จะใช้ **ประเมิน** ระบบในภายหลัง ถ้าระหว่างพัฒนามีจังหวะใด
ที่โค้ดเผลออ่านมัน ผลประเมินนั้นก็เสียทันทีและ **พิสูจน์ย้อนกลับไม่ได้ว่าไม่เคยเห็น**
ข้อตกลงระหว่างคนไม่ทิ้งหลักฐาน ส่วนด่านในโค้ดพร้อมชุดทดสอบทิ้งหลักฐานไว้

ขอบเขต
------
โมดูลนี้ **ไม่ย้าย ไม่ลบ ไม่เปลี่ยนชื่อไฟล์ใด ๆ** ของผู้ใช้ ทำหน้าที่เดียวคือ
*ปฏิเสธที่จะเปิดอ่าน* และรายงานเหตุผลออกมาให้ตรวจได้

เปิดใช้เมื่อใด
-------------
P1 เปิดใช้ได้เฉพาะขั้นการประเมินภายหลัง **เมื่อกิ๊ฟอนุมัติเป็นลายลักษณ์อักษร**
ไม่มีสวิตช์ในโค้ดหรือตัวแปรสภาพแวดล้อมที่ปิดด่านนี้ได้ — การเปิดใช้ต้องแก้ที่
โมดูลนี้อย่างจงใจ พร้อมอ้างอิงคำอนุมัติ

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import re
from pathlib import Path

#: สถานะปัจจุบันของด่าน — เปลี่ยนได้ด้วยการแก้โค้ดโดยจงใจเท่านั้น
HOLDOUT_STATUS = "P1_HOLDOUT_ENFORCED"

#: ชื่อโฟลเดอร์ที่ถือเป็นเขตกันไว้ — เทียบแบบไม่สนตัวพิมพ์
HOLDOUT_DIR_NAMES = frozenset({"p1", "holdout", "_holdout"})

#: ``P1`` ที่ยืนเป็นคำของตัวเองในชื่อไฟล์ — ไม่จับ ``P10`` หรือ ``HSRI1``
HOLDOUT_NAME_TOKEN = re.compile(r"(?:^|[_\-\s.])P1(?:[_\-\s.]|$)", re.IGNORECASE)

REASON_DIR = "holdout_directory"
REASON_NAME = "p1_filename_token"


class HoldoutViolation(Exception):
    """มีโค้ดพยายามเปิดไฟล์ในเขตกันไว้ — **ยกทันที ห้ามคืนค่าว่างเงียบ ๆ**

    ยกเป็นข้อยกเว้นแทนการข้ามเงียบ เพราะการข้ามเงียบทำให้ผลลัพธ์ที่ขาดหายไป
    ดูเหมือนผลลัพธ์ที่ตรวจแล้วไม่พบอะไร ซึ่งอ่านไม่ออกจากปลายทาง
    """

    def __init__(self, path, reason: str):
        self.reason = reason
        self.filename = Path(path).name
        super().__init__(
            f"ไฟล์นี้อยู่ในชุดข้อมูลที่กันไว้ (P1 holdout) ระบบจึงไม่เปิดอ่าน "
            f"— เหตุผล {reason}")


def holdout_reason(path) -> str | None:
    """คืนเหตุผลที่ไฟล์นี้ถูกกันไว้ หรือ ``None`` ถ้าใช้ได้ตามปกติ

    ตรวจสองชั้นอิสระกัน ชั้นใดชั้นหนึ่งเข้าข่ายก็พอ — เพราะไฟล์ P1 หลุดออกจาก
    โฟลเดอร์ได้ และไฟล์ในโฟลเดอร์ก็อาจถูกตั้งชื่อใหม่ได้
    """
    p = Path(path)
    for part in p.parts[:-1]:
        if part.strip().casefold() in HOLDOUT_DIR_NAMES:
            return REASON_DIR
    if HOLDOUT_NAME_TOKEN.search(p.name):
        return REASON_NAME
    return None


def is_holdout(path) -> bool:
    return holdout_reason(path) is not None


def assert_not_holdout(path) -> None:
    """ด่านที่ต้องเรียก **ก่อน** บรรทัดแรกที่แตะเนื้อไฟล์"""
    reason = holdout_reason(path)
    if reason is not None:
        raise HoldoutViolation(path, reason)


def partition(paths) -> tuple[list[Path], list[tuple[Path, str]]]:
    """แยกรายชื่อไฟล์เป็น (ที่ใช้ได้, ที่กันไว้พร้อมเหตุผล)

    🔴 คืน **ทั้งสองกอง** เสมอ — เครื่องมือที่เรียกต้องรายงานกองที่ถูกกันด้วย
    ไม่ใช่กรองทิ้งเงียบ ๆ มิฉะนั้นผู้อ่านรายงานจะไม่รู้ว่ามีไฟล์ถูกข้ามไป
    """
    kept: list[Path] = []
    skipped: list[tuple[Path, str]] = []
    for raw in paths:
        p = Path(raw)
        reason = holdout_reason(p)
        if reason is None:
            kept.append(p)
        else:
            skipped.append((p, reason))
    return kept, skipped


#: ข้อความมาตรฐานเมื่อผู้ใช้อัปโหลดไฟล์ P1 เข้ามาเอง
UPLOAD_NOTICE = (
    "ไฟล์นี้มีลักษณะเป็นเอกสาร P1 ซึ่งเป็นคนละบทบาทกับเอกสารคาดแดง AO "
    "ระบบจึงไม่นำมาใช้ในการเปรียบเทียบ AO เก่า–ใหม่ "
    "P1 ถูกกันไว้เป็นชุดข้อมูลสำหรับการประเมินภายหลัง"
)

__all__ = [
    "HOLDOUT_STATUS", "HOLDOUT_DIR_NAMES", "HOLDOUT_NAME_TOKEN",
    "REASON_DIR", "REASON_NAME", "HoldoutViolation",
    "holdout_reason", "is_holdout", "assert_not_holdout", "partition",
    "UPLOAD_NOTICE",
]
