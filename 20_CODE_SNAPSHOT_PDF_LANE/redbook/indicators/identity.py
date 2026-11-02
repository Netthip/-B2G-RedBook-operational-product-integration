# -*- coding: utf-8 -*-
"""ตัวตนของตัวชี้วัด — **canonical `indicator_id` ที่คงที่ข้าม run / เอกสาร / ปี** (B1)

🔴 คำสั่ง Bo (`5595832792` B1 · ยืนยันซ้ำ `5597709987`) —
*"stable canonical indicator identity across runs/documents/years … ห้ามเรียก provisional
ID ว่า canonical"*

หลักการที่ทำให้ id คงที่ได้ โดยเครื่อง **ไม่ตัดสินความหมายเอง**
------------------------------------------------------------
1. **สมอของข้อสังเกต (`observation_key`) คงที่จากเนื้อหา** — ประกอบจาก
   แฮชเนื้อเอกสารเต็ม + หน้า + สมอในหน้า + ข้อความที่ปรากฏ ⇒ เอกสารเดิมถูกสกัดใน run ใหม่
   ก็ได้กุญแจเดิม (ไม่ผูกกับ ``run_id``) · ใช้แฮช **เต็ม** ไม่ใช่ 16 ตัวแรก (H1)
2. **การรวมเป็นตัวชี้วัดเดียว มาจากคำตัดสินของมนุษย์เท่านั้น** — สร้างกราฟจากคู่ที่คน
   ยืนยันสถานะตระกูล ``SAME_*`` (ล่าสุด) แล้วหา component ด้วย union-find
   ⇒ รองรับ transitive (A=B, B=C ⇒ ตัวเดียวกัน) โดยไม่ต้องให้คนยืนยัน A=C ซ้ำ
3. **canonical id ถูกตรึง (pin) ครั้งแรกที่ component เกิด แล้วใช้ซ้ำตลอด** —
   ถ้าภายหลัง component โตขึ้นหรือรวมกับ component อื่น จะ **ไม่เปลี่ยน id เดิม**
   แต่เลือก id ที่ถูกตรึง *ก่อน* เป็นตัวหลัก และบันทึกที่เหลือเป็น **alias**
   ⇒ id ที่เคยเผยแพร่ไปแล้วยังใช้เปิดกลับได้เสมอ (ไม่มี id ตายกลางทาง)
4. **ยังไม่ถูกยืนยัน = ยังไม่มี canonical id** — คืนรหัสที่ประกาศตัวเองว่าเป็นรหัสชั่วคราว
   (``PROVISIONAL-…``) 🔴 ห้ามเรียกว่า canonical และห้ามใช้อ้างอิงข้ามรอบ

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

IDENTITY_VERSION = "indicator-identity-0.1.0"

CANONICAL_PREFIX = "IND"
PROVISIONAL_PREFIX = "PROVISIONAL"

#: ความยาวของส่วนแฮชใน id — id เป็นเพียง *ฉลาก* ตัวตนที่แท้จริงคือ ``root_key`` เต็ม
_ID_HASH_LEN = 12


def observation_key(*, document_sha256: str, page: int, anchor: str,
                    observed_text: str) -> str:
    """สมอของข้อสังเกตที่คงที่ข้าม run — **ไม่มี ``run_id`` อยู่ในสูตร**

    ``anchor`` = ตัวระบุตำแหน่งในหน้าที่คงที่ (เช่น ``line:12`` ที่ตัวสกัดให้ หรือ
    ``manual:{occurrence}`` ที่คนกรอก) · ใช้ ``document_sha256`` **เต็ม** เพื่อไม่ให้
    เอกสารสองฉบับที่แฮชขึ้นต้นเหมือนกันปนกัน (H1)
    """
    if not document_sha256 or len(document_sha256) < 64:
        raise ValueError("observation_key ต้องใช้แฮชเนื้อเอกสารแบบเต็ม (64 hex)")
    payload = f"{document_sha256}|{int(page)}|{anchor}|{observed_text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_id_for(root_key: str) -> str:
    """ฉลาก canonical จาก ``root_key`` — deterministic และคงที่"""
    return f"{CANONICAL_PREFIX}-" + hashlib.sha256(
        root_key.encode("utf-8")).hexdigest()[:_ID_HASH_LEN].upper()


def provisional_id_for(observation_key_: str) -> str:
    """รหัส **ชั่วคราว** ของข้อสังเกตที่ยังไม่มีคำตัดสินผูกเข้าตัวชี้วัดใด

    🔴 ประกาศตัวเองว่าชั่วคราวในตัวรหัส — ผู้อ่านรายงานจึงแยกออกจาก canonical ได้ด้วยตาเปล่า
    """
    return f"{PROVISIONAL_PREFIX}-" + hashlib.sha256(
        observation_key_.encode("utf-8")).hexdigest()[:_ID_HASH_LEN].upper()


def is_canonical(indicator_id: str) -> bool:
    return bool(indicator_id) and indicator_id.startswith(CANONICAL_PREFIX + "-")


# ── union-find ──────────────────────────────────────────────────────────────

class _UF:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self.parent.setdefault(x, x)

    def find(self, x: str) -> str:
        self.add(x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:      # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # เลือก root แบบ deterministic (กุญแจที่เล็กกว่าเป็น root) เพื่อให้ผลไม่ขึ้นกับลำดับ
        lo, hi = sorted((ra, rb))
        self.parent[hi] = lo


@dataclass(frozen=True)
class Component:
    root_key: str
    members: tuple[str, ...]

    @property
    def size(self) -> int:
        return len(self.members)


@dataclass(frozen=True)
class IdentityConflict:
    """ข้อสังเกตหนึ่งตัวถูกยืนยันว่าเป็น "ตัวเดียวกัน" กับหลายตัวในฝั่งตรงข้ามของ run เดียว

    🔴 Bo (`5595832792` B2 ข้อ 3) — *"รับสอง mapping ที่ชน observation เดียวกัน ⇒
    ปฏิเสธ/ส่ง adjudication ไม่ใช่ last row wins"* · กรณีนี้ **ไม่ผูก** และต้องให้คนตัดสิน
    """
    observation_key: str
    side: str                      # 'old' | 'new'
    partner_keys: tuple[str, ...]
    mapping_ids: tuple[str, ...]


@dataclass(frozen=True)
class Edge:
    """คู่ที่คนยืนยันแล้วว่าเป็นตัวชี้วัดเดียวกัน (สถานะตระกูล ``SAME_*``)"""
    old_key: str
    new_key: str
    mapping_id: str
    decision_seq: int
    run_id: str = ""


@dataclass(frozen=True)
class Resolution:
    """ผลการคำนวณตัวตน — ทั้ง component ที่ผูกได้ และข้อขัดแย้งที่ต้องให้คนตัดสิน"""
    components: tuple[Component, ...]
    conflicts: tuple[IdentityConflict, ...]
    #: observation_key → root_key (เฉพาะที่ผูกได้)
    member_root: dict = field(default_factory=dict)
    #: edge ที่ถูกกันออกเพราะขัดแย้ง
    excluded_edges: tuple[Edge, ...] = ()


def resolve(edges: list[Edge]) -> Resolution:
    """สร้าง component จาก edge ที่คนยืนยัน — กัน one-to-many ออกเป็น conflict ก่อน

    กติกา conflict: **ภายใน run เดียวกัน** ถ้าข้อสังเกตหนึ่งตัวถูกยืนยันคู่กับข้อสังเกต
    ฝั่งตรงข้าม **มากกว่าหนึ่งตัว** ⇒ ทุก edge ที่เกี่ยวกับข้อสังเกตนั้นถูกกันออก และ
    รายงานเป็น :class:`IdentityConflict` · ข้าม run ไม่ถือเป็น conflict เพราะเป็นการยืนยัน
    เอกสารคนละคู่ (transitive ที่ต้องการ)
    """
    by_old: dict[tuple[str, str], list[Edge]] = {}
    by_new: dict[tuple[str, str], list[Edge]] = {}
    for e in edges:
        by_old.setdefault((e.run_id, e.old_key), []).append(e)
        by_new.setdefault((e.run_id, e.new_key), []).append(e)

    conflicts: list[IdentityConflict] = []
    bad_edges: set[tuple[str, str, str]] = set()

    def scan(index, side: str, partner_attr: str) -> None:
        for (_run, key), group in sorted(index.items()):
            partners = sorted({getattr(e, partner_attr) for e in group})
            if len(partners) > 1:
                conflicts.append(IdentityConflict(
                    observation_key=key, side=side, partner_keys=tuple(partners),
                    mapping_ids=tuple(sorted(e.mapping_id for e in group))))
                for e in group:
                    bad_edges.add((e.old_key, e.new_key, e.mapping_id))

    scan(by_old, "old", "new_key")
    scan(by_new, "new", "old_key")

    uf = _UF()
    kept: list[Edge] = []
    excluded: list[Edge] = []
    for e in edges:
        if (e.old_key, e.new_key, e.mapping_id) in bad_edges:
            excluded.append(e)
            continue
        uf.union(e.old_key, e.new_key)
        kept.append(e)

    groups: dict[str, list[str]] = {}
    for key in sorted(uf.parent):
        groups.setdefault(uf.find(key), []).append(key)
    components = tuple(Component(root_key=root, members=tuple(sorted(members)))
                       for root, members in sorted(groups.items()))
    member_root = {m: c.root_key for c in components for m in c.members}
    return Resolution(components=components, conflicts=tuple(conflicts),
                      member_root=member_root, excluded_edges=tuple(excluded))


#: ลำดับของ id ที่ไม่มีบันทึกลำดับการตรึง — จัดไว้ **ท้ายสุด** เสมอ
#: (ค่าบวกที่ใหญ่กว่าจำนวนแถวที่เป็นไปได้จริง · ไม่ใช้ ``inf`` เพราะต้องเทียบกับ ``int``)
NO_ESTABLISH_ORDER = 1 << 62


def pick_canonical(component: Component, pinned: dict[str, str],
                   established_order: dict[str, int] | None = None,
                   ) -> tuple[str, tuple[str, ...]]:
    """เลือก canonical id ของ component และคืน alias ที่ต้องคงไว้

    ``pinned`` = ``observation_key`` (หรือ ``root_key`` เดิม) → canonical id ที่ถูกตรึงไว้แล้ว
    ``established_order`` = คีย์เดียวกัน → ``seq`` ของแถวที่ตรึง (ลำดับ **เวลาจริง**)

    * ถ้ามีสมาชิกที่เคยถูกตรึง ⇒ ใช้ **id ที่ถูกตรึงก่อนสุดตามเวลา** เป็นตัวหลัก ·
      id ที่เหลือกลายเป็น alias (ยังใช้เปิดกลับได้) ⇒ id ที่เคยเผยแพร่ไม่ตาย
    * ถ้าไม่มีเลย ⇒ ตรึงใหม่จาก ``root_key``

    🔴 **Bo (`5600162467` B1)** — เดิมฟังก์ชันนี้ไล่ ``component.members`` ซึ่งเรียงตาม
    *ตัวอักษร* แล้วหยิบตัวแรกที่พบ ⇒ ได้ id ของ root ที่มาก่อนตาม **ลำดับตัวอักษร**
    ไม่ใช่ id ที่ถูกตรึง **ก่อนตามเวลา** ตามที่เอกสารประกาศไว้ · ผู้เรียกจึงต้องส่ง
    ``established_order`` มาด้วยเสมอ · ถ้าไม่ส่ง ทุกตัวจะได้ลำดับ
    :data:`NO_ESTABLISH_ORDER` เท่ากันแล้วตัดสินด้วยลำดับตัวอักษรเป็นทางสำรอง
    (ผลคงที่ แต่ **ไม่** ใช่กติกาที่ประกาศไว้)
    """
    order = established_order or {}
    found: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for idx, member in enumerate(component.members):
        cid = pinned.get(member)
        if not cid or cid in seen:
            continue
        seen.add(cid)
        found.append((int(order.get(member, NO_ESTABLISH_ORDER)), idx, cid))
    if not found:
        return canonical_id_for(component.root_key), ()
    found.sort()
    return found[0][2], tuple(cid for _, _, cid in found[1:])


__all__ = [
    "IDENTITY_VERSION", "CANONICAL_PREFIX", "PROVISIONAL_PREFIX",
    "observation_key", "canonical_id_for", "provisional_id_for", "is_canonical",
    "Component", "IdentityConflict", "Edge", "Resolution", "resolve", "pick_canonical",
    "NO_ESTABLISH_ORDER",
]
