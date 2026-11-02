# -*- coding: utf-8 -*-
"""ด่านกันการ *เผลอ* อ่านเฉลย (accidental sealed-key ingestion guard) — บังคับด้วยโค้ด ไม่ใช่ด้วยวินัย

🔴 **ถ้อยคำที่ถูกต้อง (Bo · `5597645315` ข้อ A):** โมดูลนี้ **ไม่ใช่ access control** และ
**ไม่พิสูจน์ว่าผู้พัฒนาเข้าถึงเฉลยไม่ได้** — เป็นด่านตามกติกาชื่อไฟล์/โฟลเดอร์ที่ผู้พัฒนา
ควบคุมเอง เลี่ยงได้ด้วยการเปลี่ยนชื่อไฟล์หรือแก้โค้ด · ข้อกล่าวอ้างที่พิสูจน์ได้มีข้อเดียว:
*"แอปปฏิเสธ path ที่ตรงกับกติกาชื่อเฉลยที่ประกาศไว้ ก่อนเปิดไฟล์"* · การแยกบทบาทจริง
ต้องอยู่ **นอก repo และนอกเครื่อง/บัญชีที่ผู้พัฒนาเข้าถึง** (กิ๊ฟเป็น custodian เลือกและควบคุม
ตำแหน่งเฉลย · เฉลยห้ามเข้ามาในรากที่ Giho เข้าถึงก่อน unblind ที่ได้รับอนุญาต) · ด่านนี้เป็น
**defense in depth** เท่านั้น

🔴 **คำตัดสินกิ๊ฟ (9 ก.ย. 2569 · `GIFT DECISION — ANSWER-KEY CUSTODIAN`)**

    "This does not mean the detector developer may see the key while developing
    or tuning the detector. The required separation is temporal and
    access-controlled."

ทำไมต้องมีด่านนี้ในโค้ด
---------------------
ผู้พัฒนา detector (Giho) เป็นคนเขียนโมดูลที่เปิดอ่านเอกสารทุกตัวในระบบนี้
ถ้าเฉลยถูกวางไว้ในโฟลเดอร์ใดที่เครื่องมือของผู้พัฒนาเดินผ่าน — inventory ·
registry · pipeline — ก็มีโอกาสที่เฉลยจะถูก "เห็น" โดยไม่ตั้งใจ และ
**พิสูจน์ย้อนกลับไม่ได้ว่าไม่เคยเห็น** · ด่านนี้ทำหน้าที่เดียวคือ *ปฏิเสธที่จะ
เปิดอ่าน* ไฟล์ที่มีลักษณะเป็นเฉลย และรายงานเหตุผลออกมาให้ตรวจได้

สิ่งที่ด่านนี้ **ไม่ใช่**
----------------------
* ไม่ใช่ access control · ไม่ใช่การพิสูจน์ว่าผู้พัฒนาเข้าถึงเฉลยไม่ได้
* ไม่ใช่หลักฐานว่าเฉลยถูกเก็บอยู่ที่ไหน — ตำแหน่งเฉลยเป็นคำตัดสินของกิ๊ฟ
  (custodian) และ **ต้องอยู่นอก** `REDBOOK_DATA_DIR` / `REDBOOK_DATA_ROOT`
  นอก repo ทุกตัวที่ผู้พัฒนา clone ไว้ และนอกเครื่อง/บัญชีที่ session ของผู้พัฒนาเข้าถึง
* ไม่ใช่การเข้ารหัส — เป็นเพียงชั้นที่ทำให้ *เครื่องมือของผู้พัฒนา* ปฏิเสธเอง
* ไม่มีสวิตช์ปิดด้วย env/config — การปลดต้องแก้โมดูลนี้อย่างจงใจพร้อมอ้าง
  คำอนุมัติ (เช่นเดียวกับ :mod:`redbook.holdout`)

ใช้คู่กับ :mod:`redbook.holdout` — ทั้งสองด่านถูกเรียก **ก่อนบรรทัดแรกที่แตะเนื้อไฟล์**

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import re
from pathlib import Path

#: สถานะปัจจุบันของด่าน — เปลี่ยนได้ด้วยการแก้โค้ดโดยจงใจเท่านั้น
SEALED_KEY_GUARD_STATUS = "ACCIDENTAL_SEALED_KEY_INGESTION_GUARD_ENFORCED"
SEALED_KEY_GUARD_VERSION = "sealed-key-ingestion-guard-0.1.1"
#: ถ้อยคำบังคับเวลาอ้างถึงด่านนี้ในเอกสาร/handoff
GUARD_CLAIM = ("The application rejects paths matching the declared sealed-key naming "
               "convention before opening them.")
GUARD_IS_NOT = "not access control; does not prove developer non-access to the key"

#: ชื่อโฟลเดอร์ที่ถือเป็นเขตเฉลย — เทียบแบบไม่สนตัวพิมพ์
SEALED_DIR_NAMES = frozenset({
    "sealed_key", "sealed-key", "sealedkey", "answer_key", "answer-key",
    "answerkey", "_sealed", "key_custodian", "gold_key",
})

#: โทเคนในชื่อไฟล์ที่ถือว่าเป็นเฉลย — ยืนเป็นคำของตัวเอง ไม่จับคำอื่นที่บังเอิญมี key
SEALED_NAME_TOKEN = re.compile(
    r"(?:^|[_\-\s.])(?:ANSWER[_\-]?KEY|SEALED[_\-]?KEY|GOLD[_\-]?KEY)(?:[_\-\s.]|$)",
    re.IGNORECASE)

REASON_DIR = "sealed_key_directory"
REASON_NAME = "sealed_key_filename_token"


class SealedKeyViolation(Exception):
    """มีโค้ดพยายามเปิดไฟล์ที่มีลักษณะเป็นเฉลย — **ยกทันที ห้ามคืนค่าว่างเงียบ ๆ**"""

    def __init__(self, path, reason: str):
        self.reason = reason
        self.filename = Path(path).name
        super().__init__(
            "ไฟล์นี้มีลักษณะเป็นเฉลยที่ปิดผนึก (sealed answer key) "
            f"เครื่องมือของผู้พัฒนา detector จึงไม่เปิดอ่าน — เหตุผล {reason}")


def sealed_reason(path) -> str | None:
    """คืนเหตุผลที่ไฟล์นี้ถูกกัน หรือ ``None`` ถ้าใช้ได้ตามปกติ"""
    p = Path(path)
    for part in p.parts[:-1]:
        if part.strip().casefold() in SEALED_DIR_NAMES:
            return REASON_DIR
    if SEALED_NAME_TOKEN.search(p.name):
        return REASON_NAME
    return None


def is_sealed(path) -> bool:
    return sealed_reason(path) is not None


def assert_not_sealed(path) -> None:
    """ด่านที่ต้องเรียก **ก่อน** บรรทัดแรกที่แตะเนื้อไฟล์"""
    reason = sealed_reason(path)
    if reason is not None:
        raise SealedKeyViolation(path, reason)


def scan_roots(roots) -> dict:
    """ไล่ดู **ชื่อ** ไฟล์/โฟลเดอร์ใต้ root ที่กำหนด ว่ามีสิ่งที่เข้าข่ายกติกาชื่อเฉลยหรือไม่

    🔴 **inventory evidence เท่านั้น** — ไม่พิสูจน์ว่าไม่มีเฉลย และไม่พิสูจน์ว่าผู้พัฒนา
    เข้าถึงเฉลยไม่ได้ (Bo · `5597645315` ข้อ A) · **ไม่เปิดอ่านเนื้อไฟล์ใด** และคืนเฉพาะ
    จำนวนกับชื่อไฟล์ (ไม่มีเส้นทางเต็ม) — "ไม่พบ" = ไม่พบตามกติกาชื่อ ณ เวลาสแกน
    """
    hits: list[dict] = []
    scanned = 0
    missing: list[str] = []
    for raw in roots:
        root = Path(raw)
        if not root.is_dir():
            missing.append(root.name)
            continue
        for p in root.rglob("*"):
            if any(part in {".git", ".venv", "__pycache__"} for part in p.parts):
                continue
            scanned += 1
            reason = sealed_reason(p)
            if reason is not None:
                hits.append({"name": p.name, "reason": reason})
    return {"guard_version": SEALED_KEY_GUARD_VERSION, "evidence_kind": "inventory_only",
            "claim": GUARD_CLAIM, "is_not": GUARD_IS_NOT, "entries_scanned": scanned,
            "hits": hits, "roots_missing": missing}


__all__ = [
    "SEALED_KEY_GUARD_STATUS", "SEALED_KEY_GUARD_VERSION", "GUARD_CLAIM", "GUARD_IS_NOT",
    "SEALED_DIR_NAMES",
    "SEALED_NAME_TOKEN", "REASON_DIR", "REASON_NAME", "SealedKeyViolation",
    "sealed_reason", "is_sealed", "assert_not_sealed", "scan_roots",
]
