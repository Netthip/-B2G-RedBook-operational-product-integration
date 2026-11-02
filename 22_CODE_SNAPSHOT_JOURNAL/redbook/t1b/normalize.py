# -*- coding: utf-8 -*-
"""T1B — การปรับรูปข้อความก่อนเปรียบเทียบ

**แยกขาดจาก `redbook/t1/normalize.py` ของชั้น T1A** ตาม RES-D-24
ห้ามนำกฎของสองชั้นมาใช้แทนกัน

กฎทุกข้อในไฟล์นี้มาจากข้อบกพร่องที่พบในไฟล์จริง ไม่ใช่การเดา —
ดู `09_RESEARCH_BRIDGE/T1B_CANONICAL_KEY_SPEC.md` หัวข้อ "กฎ normalize"
"""
from __future__ import annotations

import re

#: ช่องว่างทุกชนิดรวม newline, tab และ non-breaking space
_WS = re.compile(r"[\s ​]+")

#: เลขนำหน้าแบบ "1." "2.1" "2.1.3" ตามด้วยช่องว่างหรือจบข้อความ
_LEADING_NUMBER = re.compile(r"^(\d+(?:\.\d+)*)\.?\s*")

#: เครื่องหมายนำหน้ารายการย่อย
_LEADING_BULLET = re.compile(r"^[-–—•]\s*")


def normalize_label(value: object) -> str:
    """ปรับรูปป้ายแถวให้เทียบกันได้

    แก้ silent failure ที่พบจริง:
      - ช่องว่างนำหน้าเพิ่มขึ้นระหว่างปี  `'รวมเงินนอกงบประมาณ'` -> `' รวมเงินนอกงบประมาณ'`
      - ช่องว่างท้ายข้อความ               `'- เงินกู้ต่างประเทศ '`
      - จำนวนช่องว่างภายในเปลี่ยน          `'… : การบริหาร'` -> `'… :  การบริหาร'`
      - line break กลางข้อความ            `'…จัดการ\\nเพื่อสนับสนุน…'`

    **ไม่** ตัดเลขนำหน้าออก — เลขนำหน้าเป็นข้อมูลของลำดับชั้น
    ให้ `split_leading_number()` แยกออกไปต่างหาก
    """
    if value is None:
        return ""
    return _WS.sub(" ", str(value)).strip()


_LINE_BREAKS = re.compile(r"\s*[\r\n]+\s*")


def join_line_breaks(value: object) -> str:
    """G3 (#14) — ป้ายเดียวกันที่ถูกตัดบรรทัดในเซลล์ต่างตำแหน่งกัน

    ลบการขึ้นบรรทัดในเซลล์ (และช่องว่างรอบมัน) ก่อน ``normalize_label``
    หลักฐาน: คู่ข้ามปีของแฟ้มพัฒนา — ป้ายเดียวกันขึ้นบรรทัดคนละที่ ⇒
    ``normalize_label`` ได้ช่องว่างฝั่งหนึ่งแต่ไม่ได้อีกฝั่ง ⇒ รายงานเป็นลบ+เพิ่ม

    🔴 ใช้เป็น **ขั้นสำรองของการจับคู่** เท่านั้น ไม่ใช่คีย์ (คีย์ ``t1b-key-0.2.0`` ไม่เปลี่ยน)
    """
    if value is None:
        return ""
    return normalize_label(_LINE_BREAKS.sub("", str(value)))


def split_leading_number(value: object) -> tuple[str | None, str]:
    """แยกเลขนำหน้าออกจากข้อความ

    คืน ``(เลขนำหน้า, ข้อความที่เหลือ)`` — เลขนำหน้าเป็น ``None`` ถ้าไม่มี

    >>> split_leading_number("2.1 การเพิ่มขีดความสามารถ")
    ('2.1', 'การเพิ่มขีดความสามารถ')
    >>> split_leading_number("รวมทั้งสิ้น")
    (None, 'รวมทั้งสิ้น')
    """
    text = normalize_label(value)
    m = _LEADING_NUMBER.match(text)
    if not m:
        return None, text
    return m.group(1), text[m.end():].strip()


#: ปีงบประมาณที่ฝังอยู่ในหัวเรื่อง เช่น "พ.ศ. 2569" · "ปี 2570" · "2569 - 2573"
_FISCAL_YEAR = re.compile(r"(?:พ\.ศ\.\s*|ปี\s*)?\b25\d{2}\b")


def fiscal_years_in(value: object) -> tuple[int, ...]:
    """คืนปีงบประมาณทุกปีที่ปรากฏในข้อความ **เรียงตามที่พบ ไม่ตัดซ้ำผิดลำดับ**

    ใช้กับหัวเรื่องชีตที่ฝังปีไว้ เช่น
    ``"6. สรุปงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. 2570"`` -> ``(2570,)``
    ``"4. เปรียบเทียบ… พ.ศ. 2568 - 2570 จำแนกตาม…"``      -> ``(2568, 2570)``

    🔴 ผู้เรียกต้องตัดสินเองว่าจะใช้เมื่อพบ **ปีเดียว** เท่านั้นหรือไม่ —
    ฟังก์ชันนี้ **ไม่เดา** ว่าปีใดในหลายปีคือปีของตาราง

    >>> fiscal_years_in("สรุปงบประมาณ พ.ศ. 2569")
    (2569,)
    >>> fiscal_years_in("ไม่มีปี")
    ()
    """
    text = normalize_label(value)
    out: list[int] = []
    for m in _FISCAL_YEAR.finditer(text):
        year = int(re.search(r"25\d{2}", m.group(0)).group(0))
        if year not in out:
            out.append(year)
    return tuple(out)


def strip_fiscal_years(value: object) -> str:
    """ตัดเลขปีงบประมาณออกจากข้อความ

    จำเป็นเมื่อนำหัวเรื่องมาใช้เป็นส่วนของคีย์ เพราะหัวเรื่องของบทบาท ``4.``
    และ ``6.`` ฝังปีไว้ (``"สรุปงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. 2569"``)
    ถ้าไม่ตัดออก รายการเดียวกันคนละปีจะไม่มีทางจับคู่กันได้เลย

    >>> strip_fiscal_years("สรุปงบประมาณ พ.ศ. 2569")
    'สรุปงบประมาณ'
    """
    return _WS.sub(" ", _FISCAL_YEAR.sub(" ", normalize_label(value))).strip(" -–—:")


def strip_bullet(value: object) -> str:
    """ตัดเครื่องหมายนำหน้ารายการย่อยออก (`- เงินรายได้` -> `เงินรายได้`)"""
    return _LEADING_BULLET.sub("", normalize_label(value)).strip()


def indent_width(value: object) -> int:
    """จำนวนช่องว่างนำหน้าของข้อความดิบ — ใช้ประกอบการอนุมานลำดับชั้น

    ต้องเรียกกับ **ข้อความดิบ** ก่อน normalize เท่านั้น
    """
    if value is None:
        return 0
    raw = str(value).replace(" ", " ")
    return len(raw) - len(raw.lstrip(" "))
