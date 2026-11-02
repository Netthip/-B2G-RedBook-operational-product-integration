# -*- coding: utf-8 -*-
"""ตัวชี้เส้นทางร่วมของสคริปต์ reviewpack — **ไม่มีเส้นทางส่วนบุคคลในซอร์ส**

🔴 คำสั่งกิ๊ฟ (7 ก.ย. 2569 · provenance maintenance)

* ทรัพยากร **ภายใน repository** คิดจาก ``__file__``
* ราก **ข้อมูลส่วนตัว/OneDrive** อ่านจากตัวแปรสภาพแวดล้อม
  ``REDBOOK_PRIVATE_DATA_ROOT`` — ถ้าไม่ตั้ง **ต้องหยุดพร้อมข้อความชัดเจน**
  ห้ามเปลี่ยนเป็นข้ามเงียบ ๆ เพราะสคริปต์เหล่านี้ผลิตเครื่องมือวิจัยที่ freeze แล้ว
  การ "ผลิตไม่ได้แต่ไม่บอก" อันตรายกว่าการหยุด

การตั้งค่า (PowerShell)::

    $env:REDBOOK_PRIVATE_DATA_ROOT = "<โฟลเดอร์ Red Vertify Project บน OneDrive>"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

#: รากของ repository — ``reviewpack/`` อยู่ใต้รากหนึ่งชั้น
REPO_ROOT = Path(__file__).resolve().parents[1]
#: พื้นที่ข้อมูล runtime ใน repository (อยู่ใน ``.gitignore``)
DATA_DIR = REPO_ROOT / ".data"

PRIVATE_ROOT_ENV = "REDBOOK_PRIVATE_DATA_ROOT"

#: ข้อความหยุดมาตรฐาน — ชุดทดสอบตรวจว่าข้อความนี้ปรากฏจริงเมื่อไม่ตั้งค่า
MISSING_MESSAGE = (
    f"[หยุด] ไม่ได้ตั้งตัวแปรสภาพแวดล้อม {PRIVATE_ROOT_ENV}\n"
    "       สคริปต์นี้ต้องอ่าน/เขียนไฟล์ในพื้นที่ข้อมูลส่วนตัว (OneDrive) "
    "ซึ่งไม่อยู่ใน repository โดยเจตนา\n"
    f"       ตั้งค่าด้วย  $env:{PRIVATE_ROOT_ENV} = \"<โฟลเดอร์ Red Vertify Project>\"\n"
    "       PRIVATE DATASET NOT AVAILABLE — ไม่ได้ผลิตไฟล์ใด"
)


class PrivateRootMissing(SystemExit):
    """ยกเมื่อไม่มีราก OneDrive — สืบทอด ``SystemExit`` เพื่อให้สคริปต์หยุดทันที"""

    def __init__(self):
        print(MISSING_MESSAGE, file=sys.stderr)
        super().__init__(2)


def private_root() -> Path:
    """โฟลเดอร์ Red Vertify Project บน OneDrive — **fail ดัง ๆ** ถ้าไม่ตั้ง"""
    raw = os.environ.get(PRIVATE_ROOT_ENV, "").strip()
    if not raw:
        raise PrivateRootMissing()
    p = Path(raw)
    if not p.is_dir():
        print(f"[หยุด] {PRIVATE_ROOT_ENV} ชี้ไปยังโฟลเดอร์ที่ไม่มีอยู่", file=sys.stderr)
        raise SystemExit(2)
    return p


def human_review_dir(round_no: int) -> Path:
    """``04_HUMAN_REVIEW/Round<n>`` ในพื้นที่ส่วนตัว"""
    return private_root() / "04_HUMAN_REVIEW" / f"Round{round_no}"


def frozen_baseline_v131() -> Path:
    """สำเนา pristine ของ frozen instrument baseline v1.3.1 — อยู่ใน ``.data`` นอก git"""
    return (DATA_DIR / "review" / "_baseline" / "round1_v1.3.1"
            / "HUMAN_CHECK_SAMPLE_primary_R1_v1.3.1_PRISTINE_BASELINE.xlsx")


__all__ = ["REPO_ROOT", "DATA_DIR", "PRIVATE_ROOT_ENV", "MISSING_MESSAGE",
           "PrivateRootMissing", "private_root", "human_review_dir",
           "frozen_baseline_v131"]
