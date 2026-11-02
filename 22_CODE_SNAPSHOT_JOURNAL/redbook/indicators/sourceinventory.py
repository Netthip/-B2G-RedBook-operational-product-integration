# -*- coding: utf-8 -*-
"""ทะเบียนข้อสังเกตอิสระของผู้ดูแล — **ไม่ได้ป้อนจากรอบของ detector** (P3-2)

🔴 คำสั่ง Bo (`5605652708` §"Freeze blocker P3-2") —
*"`_universe_records()` reads `ind_observations` for the detector run … This removes dependence
on detector pairing, but not on detector observation extraction … if the detector fails to
extract a real indicator, that item never enters `ind_observations`, never appears in
`ind_key_universe`, and cannot be marked missing in the answer key."*

สิ่งที่โมดูลนี้เปลี่ยน
---------------------
จักรวาลของเฉลยเลิกตั้งต้นจาก "สิ่งที่เครื่องสกัดได้" แล้วเปลี่ยนเป็น **"สิ่งที่คนอ่านเจอในเอกสาร"**

* ผู้ดูแล/กิ๊ฟกรอกทีละรายการจากการอ่านหน้าเอกสารเอง — หน้า · ลำดับที่ปรากฏในหน้า · ข้อความ
* รายการผูกกับ **แฮชเนื้อเอกสารเต็ม** + หน้า + สมอที่คนระบุ ⇒ อยู่ได้แม้ ``ind_observations``
  ไม่มีบรรทัดนั้นเลย ⇒ ตัวชี้วัดที่เครื่องสกัดตกหล่น **ยังอยู่ในจักรวาลของเฉลยและถูกนับเป็น miss**
* โมดูลนี้ **ไม่ import** ``registry`` และไม่รู้จัก ``ind_mappings`` / ``ind_observations``

กติกาเทียบกับข้อสังเกตของเครื่อง
--------------------------------
สมอของสองฝ่ายคนละรูปโดยธรรมชาติ — เครื่องใช้ ``line:{index}`` ส่วนคนใช้ ``manual:{n}``
⇒ **เทียบด้วย ``identity_key`` ตรง ๆ ไม่ได้** · กติกาที่ใช้คือ

    (ฝั่ง, แฮชเอกสารเต็ม, หน้า, ข้อความรูปมาตรฐาน, ลำดับที่ปรากฏ)

**นิยามของ "ลำดับที่ปรากฏ" (occurrence)** — ตั้งแต่ ``source-inventory-0.2.0``
หมายถึง **ครั้งที่เท่าไรที่ข้อความเดียวกัน (หลังทำรูปมาตรฐาน) ปรากฏในหน้านั้น นับจากบนลงล่าง**
ข้อความที่ปรากฏครั้งเดียวในหน้า = 1 เสมอ · ฝั่งเครื่องนับด้วยนิยามเดียวกันจาก
``(line_index, observation_id)`` อย่างชัดเจน **ไม่พึ่งลำดับที่ฐานข้อมูลคืนมา**
🔴 Bo (`5606392284` P4-4) — เดิมโค้ดค้นด้วย ``match_key[:4]`` แล้ว ``pop(0)`` ⇒ รายการที่คนระบุ
occurrence 2 กินข้อสังเกตตัวที่ 1 ของเครื่องแล้วถูกนับว่าตรง · ตอนนี้ต้องตรงทั้งห้าองค์ประกอบ

🔴 ``NO_MATCH`` แปลว่า **"เครื่องไม่ได้ให้ข้อสังเกตที่เทียบเท่ากัน"** เท่านั้น
จะเป็นการสกัดตกหล่นจริง หรือเป็นเพราะเครื่องตัดบรรทัดต่างจากที่คนอ่าน **เป็นคำตัดสินของคน**
โมดูลนี้ไม่สรุปแทน และไม่ปัดกรณีที่เทียบไม่ได้ทิ้ง

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from . import identity as idn
from . import normalize as nz
from . import observe as ob

SOURCE_INVENTORY_VERSION = "source-inventory-0.2.0"

SIDE_OLD = "old"
SIDE_NEW = "new"
SIDES = (SIDE_OLD, SIDE_NEW)

#: ความยาวของแฮชเนื้อเอกสารแบบเต็ม — ฉลาก 16 ตัวใช้พิสูจน์ตัวตนไม่ได้ (H1)
FULL_DIGEST_LEN = 64

#: ผลการเทียบรายการของคนกับข้อสังเกตของเครื่อง
MATCH_EXACT = "MATCH_EXACT"                 # ข้อความตรงกันทุกอักขระ
MATCH_NORMALIZED = "MATCH_NORMALIZED"       # ตรงกันหลังทำรูปมาตรฐาน
NO_MATCH = "NO_MATCH"                       # เครื่องไม่มีข้อสังเกตที่เทียบเท่า

MATCH_LABELS = {
    MATCH_EXACT: "เครื่องสกัดได้ ข้อความตรงกันทุกอักขระ",
    MATCH_NORMALIZED: "เครื่องสกัดได้ ต่างเฉพาะรูปแบบตัวอักษร",
    NO_MATCH: "เครื่องไม่ได้ให้ข้อสังเกตที่เทียบเท่ากัน — ต้องให้คนตัดสินว่าสกัดตกหล่นหรือตัดบรรทัดต่างกัน",
}


class InventoryError(ValueError):
    """กรอกทะเบียนข้อสังเกตอิสระไม่ได้ — ข้อมูลไม่พอจะพิสูจน์ตำแหน่งได้"""


@dataclass(frozen=True)
class SourceItem:
    """หนึ่งรายการที่ **คน** อ่านเจอในเอกสาร"""
    side: str
    document_sha256: str          # แฮชเนื้อเอกสาร **เต็ม**
    page: int
    occurrence: int
    hint: str
    observed_text: str
    entered_by: str = ""

    @property
    def anchor(self) -> str:
        return ob.manual_anchor(self.occurrence, hint=self.hint)

    @property
    def normalized_text(self) -> str:
        return nz.normalize(self.observed_text)

    @property
    def identity_key(self) -> str:
        return idn.observation_key(document_sha256=self.document_sha256, page=self.page,
                                  anchor=self.anchor, observed_text=self.observed_text)

    @property
    def match_key(self) -> tuple:
        """กุญแจที่ใช้เทียบกับข้อสังเกตของเครื่อง — **ไม่ใช่** ``identity_key``"""
        return (self.side, self.document_sha256, int(self.page),
                self.normalized_text, int(self.occurrence))


def make_item(*, side: str, document_sha256: str, page: object, observed_text: str,
              occurrence: object = 1, hint: str = "", entered_by: str = "",
              page_count: object = None) -> SourceItem:
    """ตรวจความครบถ้วนของรายการที่คนกรอก แล้วคืน :class:`SourceItem`

    🔴 Bo (`5606392284` P4-4) — ``page_count`` = จำนวนหน้าจริงของเอกสารจากทะเบียนเอกสาร ·
    ไม่ทราบจำนวนหน้า ⇒ **ปฏิเสธ** (ไม่ปล่อยให้เลขหน้าที่ตรวจไม่ได้ถูกผนึกเป็นเฉลย)
    """
    if side not in SIDES:
        raise InventoryError("ฝั่งของรายการต้องเป็น old หรือ new")
    doc = str(document_sha256 or "")
    if len(doc) != FULL_DIGEST_LEN:
        raise InventoryError("ต้องใช้แฮชเนื้อเอกสารแบบเต็ม (64 hex) จึงจะพิสูจน์ตัวตนได้")
    try:
        page_no = int(page)
    except (TypeError, ValueError):
        raise InventoryError("เลขหน้าต้องเป็นจำนวนเต็ม") from None
    if page_no < 1:
        raise InventoryError("เลขหน้าต้องเริ่มที่ 1")
    try:
        pages = int(page_count) if page_count is not None else 0
    except (TypeError, ValueError):
        pages = 0
    if pages < 1:
        raise InventoryError("ไม่ทราบจำนวนหน้าของเอกสาร — ตรวจเลขหน้าไม่ได้ จึงกรอกทะเบียนอิสระไม่ได้")
    if page_no > pages:
        raise InventoryError("เลขหน้า %d เกินจำนวนหน้าของเอกสาร (%d หน้า)" % (page_no, pages))
    try:
        occ = int(occurrence)
    except (TypeError, ValueError):
        raise InventoryError("ลำดับที่ปรากฏในหน้าต้องเป็นจำนวนเต็ม") from None
    if occ < 1:
        raise InventoryError("ลำดับที่ปรากฏในหน้าต้องเริ่มที่ 1")
    text = str(observed_text or "").strip()
    if not text:
        raise InventoryError("ต้องระบุข้อความของตัวชี้วัดตามที่ปรากฏในเอกสาร")
    if not str(entered_by or "").strip():
        raise InventoryError("ต้องระบุผู้กรอกทะเบียนข้อสังเกต")
    return SourceItem(side=side, document_sha256=doc, page=page_no, occurrence=occ,
                      hint=str(hint or "").strip(), observed_text=text,
                      entered_by=str(entered_by).strip())


def inventory_digest(items) -> str:
    """แฮชของทะเบียนอิสระ — ไม่มีข้อความจากเอกสารในค่าที่ได้"""
    lines = ["inventory=" + SOURCE_INVENTORY_VERSION]
    for i in sorted(items, key=lambda x: x.identity_key):
        lines.append("|".join([i.side, i.document_sha256, str(i.page), i.anchor,
                               hashlib.sha256(i.observed_text.encode("utf-8")).hexdigest()]))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Match:
    """ผลเทียบรายการหนึ่งของทะเบียนอิสระกับข้อสังเกตของเครื่อง"""
    identity_key: str
    side: str
    page: int
    status: str
    observation_id: str = ""

    @property
    def missed(self) -> bool:
        return self.status == NO_MATCH

    @property
    def label(self) -> str:
        return MATCH_LABELS.get(self.status, self.status)


def detector_occurrences(observations) -> dict:
    """ลำดับที่ปรากฏของข้อสังเกตฝั่งเครื่อง — ``match_key -> (observation_id, observed_text)``

    นับภายในกลุ่ม (ฝั่ง, แฮชเอกสาร, หน้า, ข้อความรูปมาตรฐาน) โดยเรียงด้วย
    ``(line_index, observation_id)`` **ในฟังก์ชันนี้เอง** — ผลจึงไม่ขึ้นกับลำดับที่ส่งเข้ามา
    """
    groups: dict[tuple, list] = {}
    for o in observations:
        text = str(o["observed_text"] or "")
        key = (str(o["side"]), str(o["document_sha256"] or ""), int(o["page"]),
               nz.normalize(text))
        groups.setdefault(key, []).append(
            (int(o["line_index"]), str(o["observation_id"]), text))
    out: dict[tuple, tuple] = {}
    for key, members in groups.items():
        members.sort(key=lambda m: (m[0], m[1]))
        for n, (_line, obs_id, text) in enumerate(members, start=1):
            out[key + (n,)] = (obs_id, text)
    return out


def match_against_observations(items, observations) -> tuple:
    """เทียบทะเบียนอิสระกับข้อสังเกตที่เครื่องสกัดได้ — **occurrence ต้องตรงตัว**

    ``observations`` = ลำดับของ dict ที่มี ``side`` · ``observation_id`` ·
    ``document_sha256`` · ``page`` · ``line_index`` · ``observed_text``

    ข้อสังเกตของเครื่องหนึ่งตัวตอบรายการของคนได้ครั้งเดียว · รายการของคนที่ไม่มี
    ข้อสังเกตในตำแหน่ง **เดียวกันทั้งห้าองค์ประกอบ** ⇒ ``NO_MATCH``
    """
    detector = detector_occurrences(observations)
    used: set = set()
    out: list[Match] = []
    for item in sorted(items, key=lambda x: (x.side, x.page, x.occurrence, x.identity_key)):
        hit = detector.get(item.match_key)
        if hit is not None and item.match_key not in used:
            used.add(item.match_key)
            obs_id, obs_text = hit
            status = MATCH_EXACT if obs_text == item.observed_text else MATCH_NORMALIZED
            out.append(Match(identity_key=item.identity_key, side=item.side,
                             page=item.page, status=status, observation_id=obs_id))
        else:
            out.append(Match(identity_key=item.identity_key, side=item.side,
                             page=item.page, status=NO_MATCH))
    return tuple(out)


@dataclass(frozen=True)
class CoverageReport:
    """ความครอบคลุมของ **การสกัด** ของเครื่องเทียบกับทะเบียนอิสระ

    🔴 ไม่ใช่คะแนนความแม่นยำ และไม่ใช่ผลการประเมิน — เป็นการแสดงว่ารายการใดที่คนเห็น
    แล้วเครื่องไม่ได้ให้ข้อสังเกตที่เทียบเท่ากัน · การตีความเป็นของคน
    """
    matches: tuple
    inventory_total: int
    matched: int
    missed: int
    missed_keys: tuple
    version: str = SOURCE_INVENTORY_VERSION


def coverage(items, observations) -> CoverageReport:
    matches = match_against_observations(items, observations)
    missed = tuple(m.identity_key for m in matches if m.missed)
    return CoverageReport(matches=matches, inventory_total=len(matches),
                          matched=len(matches) - len(missed), missed=len(missed),
                          missed_keys=missed)


__all__ = [
    "SOURCE_INVENTORY_VERSION", "SIDE_OLD", "SIDE_NEW", "SIDES", "FULL_DIGEST_LEN",
    "MATCH_EXACT", "MATCH_NORMALIZED", "NO_MATCH", "MATCH_LABELS",
    "InventoryError", "SourceItem", "Match", "CoverageReport",
    "make_item", "inventory_digest", "match_against_observations", "coverage",
    "detector_occurrences",
]
