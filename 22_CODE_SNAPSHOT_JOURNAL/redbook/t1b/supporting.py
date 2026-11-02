# -*- coding: utf-8 -*-
"""T1B — ผูกบล็อกของชีตประกอบกับบริบทของชีตหลักด้วย **ชื่อ** (G2 · #14)

ชีตประกอบ (รายละเอียดงบประมาณจำแนกตามงบรายจ่าย) แบ่งเป็นบล็อก แต่ละบล็อกขึ้นต้นด้วย
``ผลผลิต : …`` · ``โครงการ : …`` · หรือ ``รายการบุคลากรภาครัฐ``

🔴 **ผูกด้วยชื่อ ไม่ใช่เลขข้อ ไม่ใช่ชื่อชีต ไม่ใช่ลำดับชีต** (หลักเดียวกับ FM-12)
🔴 **ผูกได้ต่อเมื่อพบคู่ที่ตรงกันหนึ่งเดียวเท่านั้น** — ไม่พบหรือพบหลายแห่ง
   ⇒ record ยังออก แต่ติดธงว่าผูกไม่สำเร็จ · **ห้ามยุบรวมเงียบ ๆ**

ที่ค้นหาคู่: ป้ายหัวข้อที่มีเลขข้อสามระดับขึ้นไป (เช่น ``7.3.2``) ในชีตหลักที่มีบทบาท
แผนงาน/โครงการ (ตัดสินจากบทบาท ไม่ใช่ชื่อชีต)

กฎการเทียบชื่อมีสองขั้น และบันทึกเสมอว่าใช้ขั้นใด

1. ``exact`` — ชื่อหลัง ``normalize_label`` ตรงกันทุกตัวอักษร
2. ``line_break_joined`` — ใช้เมื่อขั้นแรกไม่พบเท่านั้น: ลบการขึ้นบรรทัดในเซลล์ก่อนเทียบ
   หลักฐาน (G3): หัวเรื่องโครงการในชีตหลักถูกตัดบรรทัดกลางวลีภาษาไทย ซึ่ง
   ``normalize_label`` แปลงเป็นช่องว่าง ทำให้ชื่อเดียวกันไม่ตรงกัน
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .normalize import normalize_label, split_leading_number

KIND_OUTPUT = "ผลผลิต"
KIND_PROJECT = "โครงการ"
KIND_PERSONNEL = "บุคลากรภาครัฐ"
PERSONNEL_BLOCK_PREFIX = "รายการบุคลากรภาครัฐ"

#: บทบาทชีตในคีย์ของ record ชีตประกอบ — แยกจากบทบาทของชีตหลัก จึงไม่ชนคีย์กัน
SHEET_ROLE_SUPPORTING_DETAIL = "SUPPORTING_DETAIL"

RULE_EXACT = "exact"
RULE_LINE_BREAK_JOINED = "line_break_joined"

_BLOCK = re.compile(r"^(ผลผลิต|โครงการ)\s*[:：]\s*(.+)$", re.S)
_KIND_PREFIX = re.compile(r"^(ผลผลิต|โครงการ|แผนงาน)(?:ที่\s*\d+)?\s*[:：]\s*")
_LINE_BREAKS = re.compile(r"\s*[\r\n]+\s*")


@dataclass(frozen=True)
class Block:
    kind: str
    raw: object
    #: ชื่อที่ใช้เป็นส่วนของคีย์ — ``normalize_label`` แบบเดิม
    name: str


@dataclass(frozen=True)
class Binding:
    bound: bool
    sheet_role: str = ""
    section_title: str = ""
    rule: str = ""
    candidates: int = 0


def _strip(text: str) -> str:
    _num, rest = split_leading_number(text)
    return _KIND_PREFIX.sub("", rest).strip()


def _names(raw: object) -> tuple[str, str]:
    """(ชื่อแบบ exact, ชื่อแบบลบการขึ้นบรรทัด)"""
    text = raw if isinstance(raw, str) else ""
    exact = _strip(normalize_label(text))
    joined = _strip(normalize_label(_LINE_BREAKS.sub("", text)))
    return exact, joined


def parse_block(raw: object) -> Block | None:
    """แถวนี้เป็นหัวบล็อกของชีตประกอบหรือไม่"""
    if not isinstance(raw, str):
        return None
    text = normalize_label(raw)
    if text.startswith(PERSONNEL_BLOCK_PREFIX):
        return Block(KIND_PERSONNEL, raw, PERSONNEL_BLOCK_PREFIX)
    m = _BLOCK.match(text)
    if not m:
        return None
    return Block(m.group(1), raw, normalize_label(m.group(2)))


def _kind_of(text: str) -> str:
    _num, rest = split_leading_number(text)
    for kind in (KIND_OUTPUT, KIND_PROJECT):
        if rest.startswith(kind):
            return kind
    return ""


class NameIndex:
    """ดัชนีชื่อจากหัวข้อในชีตหลัก -> บริบท (บทบาทชีต, หัวเรื่องชีต)

    🔴 #19 — เก็บเป็น **รายการของ occurrence** ไม่ใช่ set ของบริบท
    หัวข้อชื่อเดียวกันสองแห่งใต้บริบทเดียวกันคือผู้สมัครสองราย ⇒ ต้องผูกไม่สำเร็จ
    (เดิม set ยุบเหลือหนึ่งแล้วผูกสำเร็จผิดกติกา)
    """

    def __init__(self) -> None:
        self._exact: dict[tuple[str, str], list[tuple[str, str]]] = {}
        self._joined: dict[tuple[str, str], list[tuple[str, str]]] = {}
        self._plan_titles: list[tuple[str, str]] = []

    def add_heading(self, raw_label: object, sheet_role: str, section_title: str) -> None:
        if not isinstance(raw_label, str):
            return
        text = normalize_label(raw_label)
        number, _rest = split_leading_number(text)
        kind = _kind_of(text)
        if not number or number.count(".") < 2 or not kind:
            return
        exact, joined = _names(raw_label)
        ctx = (sheet_role, section_title)
        self._exact.setdefault((kind, exact), []).append(ctx)
        self._joined.setdefault((kind, joined), []).append(ctx)

    def add_sheet_title(self, sheet_role: str, section_title: str) -> None:
        if section_title:
            self._plan_titles.append((sheet_role, section_title))

    def bind(self, block: Block) -> Binding:
        if block.kind == KIND_PERSONNEL:
            hits = [c for c in self._plan_titles if KIND_PERSONNEL in c[1]]
            return _result(hits, RULE_EXACT)
        exact, joined = _names(block.raw)
        hits = self._exact.get((block.kind, exact), [])
        if hits:
            return _result(hits, RULE_EXACT)
        hits = self._joined.get((block.kind, joined), [])
        return _result(hits, RULE_LINE_BREAK_JOINED)


def _result(hits: list, rule: str) -> Binding:
    if len(hits) == 1:
        (role, title), = hits
        return Binding(True, role, title, rule, 1)
    return Binding(False, rule="" if not hits else rule, candidates=len(hits))


__all__ = [
    "Block", "Binding", "NameIndex", "parse_block",
    "KIND_OUTPUT", "KIND_PROJECT", "KIND_PERSONNEL", "SHEET_ROLE_SUPPORTING_DETAIL",
    "RULE_EXACT", "RULE_LINE_BREAK_JOINED",
]
