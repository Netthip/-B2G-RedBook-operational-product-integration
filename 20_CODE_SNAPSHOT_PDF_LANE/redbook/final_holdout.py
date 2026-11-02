# -*- coding: utf-8 -*-
"""ด่านกันเปิดชุดประเมินสุดท้าย (Issue #21 · คำสั่ง Gift 6 ต.ค. 2569)

ชุดประเมินสุดท้ายของ #14 ต้องไม่ถูกระบบหรือผู้พัฒนาเอนจินเปิดก่อนถึงขั้นประเมิน
โมดูลนี้ทำให้ข้อนั้นเป็น **ด่านในโค้ดที่ทดสอบได้** แทนการหวังว่าจะไม่มีใครเปิด

สองชั้น
=======

1. **ชั้นเส้นทาง** — เส้นทางที่มีโฟลเดอร์ชื่อ :data:`SEALED_DIRNAME` อยู่ที่ระดับใดก็ตาม
   (ตรวจหลัง resolve ลิงก์แล้ว) ⇒ ปฏิเสธ **ก่อนอ่านไบต์แรก**
2. **ชั้นแฮช** — SHA-256 ของไฟล์ที่ปิดผนึก อยู่ใน manifest **นอก repo** ⇒ ไฟล์ใดที่แฮชตรง
   ถูกปฏิเสธแม้จะถูกคัดลอก เปลี่ยนชื่อ หรืออัปโหลดผ่านเว็บ

เปิดได้เฉพาะเมื่อมี **unlock record** (ตั้งผ่าน env :data:`UNLOCK_ENV`) ที่ระบุแฮชของไฟล์นั้น
ทุกครั้งที่เปิดผ่าน unlock จะถูกบันทึกต่อท้าย access log

🔴 fail-closed — manifest เสีย/อ่านไม่ได้ · มีโฟลเดอร์ปิดผนึกแต่ไม่มี manifest · unlock เสีย
⇒ ปฏิเสธ ไม่ใช่ปล่อยผ่าน

🔴 **ข้อจำกัดที่ต้องพูดตรง ๆ** — ด่านนี้กันเฉพาะเส้นทางที่อ่านไฟล์ผ่านโค้ดของระบบ
(AO adapter · ตัวอ่าน Excel · การอัปโหลด · การตรวจชนิดไฟล์) **ไม่กันคนหรือโปรแกรมอื่น**
ที่เปิดไฟล์ตรง ๆ · ส่วนนั้นยังเป็นกติกาการดูแลเฉลย (#11) และหลักฐานแฮช
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

GUARD_VERSION = "final-holdout-guard-0.1.1"
SEALED_DIRNAME = "FINAL_HOLDOUT_SEALED"
MANIFEST_ENV = "REDBOOK_SEALED_MANIFEST"
UNLOCK_ENV = "REDBOOK_FINAL_HOLDOUT_UNLOCK"
DATA_ROOT_ENV = "REDBOOK_DATA_ROOT"
MANIFEST_NAME = "FINAL_HOLDOUT_SEALED.manifest.json"
ACCESS_LOG_NAME = "FINAL_HOLDOUT_ACCESS.log"


class SealedFinalHoldout(PermissionError):
    """ถูกขอให้อ่านไฟล์ที่ปิดผนึกไว้สำหรับการประเมินสุดท้าย"""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


# ------------------------------------------------------------------ ตำแหน่ง
def _data_root() -> Path | None:
    raw = os.environ.get(DATA_ROOT_ENV, "")
    return Path(raw).resolve() if raw else None


def manifest_path() -> Path | None:
    raw = os.environ.get(MANIFEST_ENV, "")
    if raw:
        return Path(raw)
    root = _data_root()
    return root / MANIFEST_NAME if root else None


def sealed_dir() -> Path | None:
    root = _data_root()
    return root / SEALED_DIRNAME if root else None


# ------------------------------------------------------------------ ชั้นเส้นทาง
def is_sealed_path(path) -> bool:
    """เส้นทางนี้อยู่ใต้โฟลเดอร์ปิดผนึกหรือไม่ — ไม่อ่านไฟล์ (resolve ลิงก์อย่างเดียว)"""
    p = Path(path)
    candidates = [p]
    try:
        candidates.append(p.resolve())
    except OSError:
        pass
    return any(part.casefold() == SEALED_DIRNAME.casefold()
               for c in candidates for part in c.parts)


# ------------------------------------------------------------------ manifest / unlock
def _load_json(path: Path, what: str, code: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        raise SealedFinalHoldout(f"{what} อ่านไม่ได้ — ปฏิเสธไว้ก่อน (fail-closed)", code) from None
    if not isinstance(data, dict):
        raise SealedFinalHoldout(f"{what} รูปแบบไม่ถูกต้อง — ปฏิเสธไว้ก่อน", code)
    return data


def _hashes(data: dict, what: str, code: str) -> frozenset[str]:
    raw = data.get("sealed_sha256")
    if not isinstance(raw, list) or not all(
            isinstance(h, str) and len(h) == 64 for h in raw):
        raise SealedFinalHoldout(f"{what} ไม่มีรายการแฮชที่ถูกต้อง — ปฏิเสธไว้ก่อน", code)
    return frozenset(h.lower() for h in raw)


def sealed_hashes() -> frozenset[str]:
    """แฮชที่ปิดผนึก · ยังไม่มีการปิดผนึกเลย ⇒ เซตว่าง

    🔴 REVIEW ของ Bo (#21): แยก "ยังไม่ตั้งค่า" ออกจาก "ระบุ manifest ชัดแต่ไฟล์หาย" —
    ระบุผ่าน env แล้วไฟล์ไม่มี ⇒ ปฏิเสธ (เดิมคืนเซตว่าง ⇒ สำเนานอกโฟลเดอร์ปิดผนึกหลุด)
    """
    explicit = os.environ.get(MANIFEST_ENV, "")
    if explicit and not Path(explicit).exists():
        raise SealedFinalHoldout(
            "ระบุ manifest ชุดประเมินไว้แต่ไม่พบไฟล์ — ปฏิเสธไว้ก่อน (fail-closed)",
            "sealed_manifest_missing")
    mp = manifest_path()
    if mp is not None and mp.exists():
        return _hashes(_load_json(mp, "manifest ชุดประเมิน", "sealed_manifest_unreadable"),
                       "manifest ชุดประเมิน", "sealed_manifest_unreadable")
    sd = sealed_dir()
    if sd is not None and sd.exists():
        raise SealedFinalHoldout(
            "มีโฟลเดอร์ปิดผนึกแต่ไม่พบ manifest — ปฏิเสธทุกการอ่านที่ผ่านด่านจนกว่าจะมี manifest",
            "sealed_manifest_missing")
    return frozenset()


def _unlock() -> tuple[dict, frozenset[str]] | None:
    raw = os.environ.get(UNLOCK_ENV, "")
    if not raw:
        return None
    data = _load_json(Path(raw), "unlock record", "unlock_unreadable")
    for field in ("unlock_id", "approved_by", "engine_ref"):
        if not str(data.get(field, "")).strip():
            raise SealedFinalHoldout(f"unlock record ขาดฟิลด์ {field} — ปฏิเสธ", "unlock_incomplete")
    return data, _hashes(data, "unlock record", "unlock_unreadable")


def _log_access(sha: str, where: str, unlock: dict) -> None:
    mp = manifest_path()
    target = (mp.parent if mp is not None else Path.cwd()) / ACCESS_LOG_NAME
    entry = {"at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "guard_version": GUARD_VERSION, "sha256": sha, "where": where,
             "unlock_id": unlock.get("unlock_id"), "engine_ref": unlock.get("engine_ref")}
    try:
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        raise SealedFinalHoldout("บันทึก access log ไม่ได้ — ไม่เปิดไฟล์โดยไม่มีร่องรอย",
                                 "access_log_unwritable") from None


# ------------------------------------------------------------------ API
def guard_path(path) -> None:
    """ชั้นเส้นทาง — เรียกได้ก่อนแตะไฟล์ใด ๆ · ไม่มี unlock ⇒ ปฏิเสธโดยไม่อ่าน"""
    if is_sealed_path(path) and _unlock() is None:
        raise SealedFinalHoldout(
            "ไฟล์นี้อยู่ในโฟลเดอร์ชุดประเมินสุดท้ายที่ปิดผนึก — ระบบไม่อ่านจนกว่าจะมี unlock",
            "sealed_path")


def check_hash(sha: str, where: str = "") -> None:
    """ชั้นแฮช — ไฟล์ที่แฮชตรงกับชุดที่ปิดผนึก ⇒ ปฏิเสธ เว้นแต่ unlock ระบุแฮชนี้"""
    sha = sha.lower()
    if sha not in sealed_hashes():
        return
    unlock = _unlock()
    if unlock is None or sha not in unlock[1]:
        raise SealedFinalHoldout(
            "ไฟล์นี้ตรงกับไฟล์ในชุดประเมินสุดท้ายที่ปิดผนึก — ระบบไม่อ่าน", "sealed_hash")
    _log_access(sha, where, unlock[0])


def sha256_of(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def guard_file(path) -> str:
    """ทั้งสองชั้น · คืน SHA-256 ของไฟล์เมื่อผ่าน

    ไฟล์ใต้โฟลเดอร์ปิดผนึก: ไม่มี unlock ⇒ ปฏิเสธก่อนอ่าน · มี unlock ⇒ แฮชต้องอยู่ใน unlock
    """
    guard_path(path)
    sha = sha256_of(path)
    if is_sealed_path(path):
        unlock = _unlock()
        if unlock is None or sha not in unlock[1]:
            raise SealedFinalHoldout("unlock ไม่ได้ระบุไฟล์นี้ — ปฏิเสธ", "unlock_mismatch")
        _log_access(sha, Path(path).name, unlock[0])
        return sha
    check_hash(sha, Path(path).name)
    return sha


__all__ = [
    "GUARD_VERSION", "SEALED_DIRNAME", "MANIFEST_ENV", "UNLOCK_ENV",
    "SealedFinalHoldout", "is_sealed_path", "sealed_hashes", "guard_path",
    "check_hash", "guard_file", "sha256_of", "manifest_path", "sealed_dir",
]
