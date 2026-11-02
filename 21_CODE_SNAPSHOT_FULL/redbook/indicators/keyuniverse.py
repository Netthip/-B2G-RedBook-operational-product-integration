# -*- coding: utf-8 -*-
"""จักรวาลของเฉลย (key universe) — **สร้างจากข้อสังเกตล้วน ไม่แตะผลของ detector** (B4)

🔴 คำสั่ง Bo (`5600162467` §"B4 is not closed") —
*"`key_build_rows(rv)` iterates `rv.pairs` … Pair selection is itself part of the detector
output being evaluated … must not use `rv.pairs`, detector `mapping_id`, detector candidate
cardinality, or detector ordering."*

สิ่งที่โมดูลนี้รับประกัน
-----------------------
1. **รายการของเฉลยมาจากข้อสังเกตในเอกสารเท่านั้น** — หนึ่งข้อสังเกต = หนึ่ง ``UniverseItem``
   ทั้งฝั่งเก่าและฝั่งใหม่ · ไม่มีแนวคิด "คู่" ของเครื่องอยู่ในนี้เลย
2. **ตัวระบุของรายการมาจากตัวตนของข้อสังเกต** (``identity_key`` ซึ่งผูกกับแฮชเอกสาร **เต็ม**)
   ⇒ ไม่ใช่ ``mapping_id`` ของ detector และไม่เปลี่ยนเมื่อ detector เปลี่ยนวิธีจับคู่
3. **ลำดับเป็นกลาง** — เรียงตาม (ฝั่ง, แฮชเอกสาร, หน้า, สมอ, แฮชข้อความ) ⇒ ไม่ใช่ลำดับ
   ที่ detector เสนอ และไม่ขึ้นกับคะแนนใด ๆ
4. **จำนวนรายการมาจากเอกสาร** ไม่ใช่จำนวนคู่ที่เครื่องจับได้ ⇒ เครื่องจับคู่ผิดหรือจับไม่ครบ
   ก็ไม่ทำให้จักรวาลของเฉลยเล็กลง
5. **ด่านครบถ้วน** (:func:`check_coverage`) — ศูนย์ / ไม่ครบ / ซ้ำ / ขาด / เกิน **ผนึกไม่ได้**

ข้อจำกัดที่ประกาศไว้
--------------------
* การจับคู่ในเฉลยเป็น **การจับคู่แบบหนึ่งต่อหนึ่ง** — ถ้าผู้จัดทำเฉลยเห็นว่ารายการหนึ่ง
  สัมพันธ์กับหลายรายการในอีกฝั่ง ต้องตอบ ``AMBIGUOUS_REVIEW_REQUIRED`` **ทั้งสองฝั่ง**
  โดยไม่ระบุคู่ แล้วอธิบายในเหตุผล · โมดูลนี้ **ไม่** รับเฉลยแบบหลายต่อหลาย
* โมดูลนี้ไม่รู้จักความหมายของตัวชี้วัด — ความถูกต้องเชิงเนื้อหาเป็นของผู้จัดทำเฉลย

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field

from . import mapping as mp

KEY_UNIVERSE_VERSION = "key-universe-0.1.0"
#: เวอร์ชันของ *พิธีการ* เฉลย — เปลี่ยนเมื่อความหมายของ digest เปลี่ยน
KEY_PROTOCOL_VERSION = "indicator-key-protocol-0.1.0"
COVERAGE_GATE_VERSION = "key-coverage-gate-0.1.0"

SIDE_OLD = "old"
SIDE_NEW = "new"
SIDES = (SIDE_OLD, SIDE_NEW)
_SIDE_RANK = {SIDE_OLD: 0, SIDE_NEW: 1}

ITEM_PREFIX = "KI"
_ID_HASH_LEN = 12

#: ความยาวของแฮชเนื้อเอกสารแบบเต็ม (H1) — ฉลาก 16 ตัวใช้พิสูจน์ตัวตนไม่ได้
FULL_DIGEST_LEN = 64


class UniverseError(ValueError):
    """สร้างจักรวาลของเฉลยไม่ได้ — ข้อมูลตัวตนไม่ครบพอจะพิสูจน์ได้"""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def item_id_for(side: str, identity_key: str) -> str:
    """ตัวระบุของรายการเฉลย — มาจากตัวตนของข้อสังเกต **ไม่ใช่จาก detector**"""
    if side not in SIDES:
        raise UniverseError("ฝั่งของรายการต้องเป็น old หรือ new")
    if not identity_key or len(identity_key) < FULL_DIGEST_LEN:
        raise UniverseError("รายการเฉลยต้องมีกุญแจตัวตนแบบเต็ม (64 hex) จึงจะพิสูจน์ได้")
    return "%s-%s" % (ITEM_PREFIX, _sha(side + "|" + identity_key)[:_ID_HASH_LEN].upper())


@dataclass(frozen=True)
class UniverseItem:
    """หนึ่งรายการในจักรวาลของเฉลย = หนึ่งข้อสังเกตในเอกสาร"""
    item_id: str
    side: str
    observation_id: str
    identity_key: str
    document_sha256: str          # แฮชเนื้อเอกสาร **เต็ม**
    page: int
    anchor: str
    text_sha256: str

    @property
    def sort_key(self) -> tuple:
        """ลำดับกลาง — ปิดท้ายด้วย ``identity_key`` ซึ่งไม่ซ้ำเสมอ

        🔴 Pass 4 — รายการที่มาจากทะเบียนอิสระ **ไม่มี** ``observation_id``
        (เครื่องอาจสกัดไม่เจอเลย) จึงใช้ตัวนั้นเป็นตัวตัดสินท้ายสุดไม่ได้อีก
        """
        return (_SIDE_RANK[self.side], self.document_sha256, self.page,
                self.anchor, self.text_sha256, self.identity_key)


def build_items(records) -> tuple[UniverseItem, ...]:
    """สร้างรายการทั้งหมดจากข้อสังเกต — ``records`` = ลำดับของ dict

    แต่ละ record ต้องมี ``side`` · ``observation_id`` · ``identity_key`` ·
    ``document_sha256`` (เต็ม) · ``page`` · ``anchor`` · ``observed_text``

    🔴 ไม่มีพารามิเตอร์ใดที่รับผลของ detector และไม่มีทางส่งลำดับของ detector เข้ามาได้
    """
    items: list[UniverseItem] = []
    seen: set[str] = set()
    for r in records:
        side = str(r["side"])
        if side not in SIDES:
            raise UniverseError("ฝั่งของข้อสังเกตไม่ถูกต้อง: " + repr(side))
        doc = str(r["document_sha256"] or "")
        if len(doc) != FULL_DIGEST_LEN:
            raise UniverseError("ต้องใช้แฮชเนื้อเอกสารแบบเต็ม (64 hex) ในจักรวาลของเฉลย")
        identity_key = str(r["identity_key"] or "")
        item_id = item_id_for(side, identity_key)
        if item_id in seen:
            raise UniverseError("รายการเฉลยซ้ำกัน: " + item_id)
        seen.add(item_id)
        items.append(UniverseItem(
            item_id=item_id, side=side, observation_id=str(r.get("observation_id") or ""),
            identity_key=identity_key, document_sha256=doc, page=int(r["page"]),
            anchor=str(r["anchor"] or ""),
            text_sha256=_sha(str(r["observed_text"] or ""))))
    items.sort(key=lambda i: i.sort_key)
    return tuple(items)


def universe_digest(items) -> str:
    """แฮชของจักรวาล — บันทึกในที่สาธารณะได้ (ไม่มีข้อความจากเอกสาร)"""
    lines = ["protocol=" + KEY_PROTOCOL_VERSION, "universe=" + KEY_UNIVERSE_VERSION]
    for i in sorted(items, key=lambda x: x.item_id):
        lines.append("|".join([i.item_id, i.side, i.identity_key, i.document_sha256,
                               str(i.page), i.anchor, i.text_sha256]))
    return _sha("\n".join(lines))


@dataclass(frozen=True)
class KeyAnswer:
    """คำตอบของเฉลยหนึ่งรายการ — ผู้จัดทำเฉลยเป็นผู้ระบุคู่เอง"""
    item_id: str
    key_status: str
    counterpart_item_id: str = ""
    reason: str = ""


CHECK_ANSWERED = "every_item_answered"
CHECK_NO_UNKNOWN = "no_unknown_item"
CHECK_STATUS = "status_recognised"
CHECK_SHAPE = "shape_matches_status"
CHECK_COUNTERPART = "counterpart_exists_and_opposite_side"
CHECK_RECIPROCAL = "pairing_is_reciprocal"
CHECK_ONCE = "counterpart_used_once"
CHECK_REASON = "reason_present_where_required"
CHECK_TOTALS = "coverage_totals_match"

CHECKS = (CHECK_ANSWERED, CHECK_NO_UNKNOWN, CHECK_STATUS, CHECK_SHAPE,
          CHECK_COUNTERPART, CHECK_RECIPROCAL, CHECK_ONCE, CHECK_REASON, CHECK_TOTALS)

CHECK_LABELS = {
    CHECK_ANSWERED: "ทุกรายการในจักรวาลมีคำตอบครบ",
    CHECK_NO_UNKNOWN: "ไม่มีคำตอบของรายการนอกจักรวาล",
    CHECK_STATUS: "สถานะที่ตอบอยู่ในชุดที่ประกาศไว้",
    CHECK_SHAPE: "รูปทรงของคำตอบตรงกับสถานะ (คู่/ฝั่งเดียว)",
    CHECK_COUNTERPART: "คู่ที่อ้างถึงมีอยู่จริงและอยู่คนละฝั่ง",
    CHECK_RECIPROCAL: "การจับคู่ตรงกันทั้งสองทาง",
    CHECK_ONCE: "รายการหนึ่งถูกใช้เป็นคู่ได้ครั้งเดียว",
    CHECK_REASON: "สถานะเชิงความหมายมีเหตุผลกำกับ",
    CHECK_TOTALS: "ยอดคำตอบรายฝั่งเท่ากับยอดของจักรวาล",
}


@dataclass(frozen=True)
class Coverage:
    """ผลของด่านครบถ้วน — ``closed`` เท่านั้นที่ผนึกเฉลยได้"""
    checks: dict = field(default_factory=dict)
    failed_checks: tuple = ()
    missing_items: tuple = ()
    unknown_items: tuple = ()
    shape_violations: tuple = ()
    counterpart_violations: tuple = ()
    reciprocity_violations: tuple = ()
    reuse_violations: tuple = ()
    reason_violations: tuple = ()
    status_violations: tuple = ()
    counts: dict = field(default_factory=dict)
    gate_version: str = COVERAGE_GATE_VERSION

    @property
    def closed(self) -> bool:
        return bool(self.checks) and all(self.checks.values())

    def summary(self) -> str:
        if self.closed:
            return "ครบถ้วน"
        return "ยังไม่ครบ — " + ", ".join(CHECK_LABELS.get(c, c) for c in self.failed_checks)


def _latest(answers) -> dict:
    if isinstance(answers, dict):
        return answers
    out: dict[str, KeyAnswer] = {}
    for a in answers:
        out[a.item_id] = a
    return out


def check_coverage(items, answers) -> Coverage:
    """ตรวจว่าเฉลย **ครบทั้งจักรวาล** และรูปทรงถูกต้องหรือยัง

    ``answers`` = คำตอบที่มีผล (ล่าสุดต่อหนึ่งรายการ) — dict ``item_id -> KeyAnswer``
    หรือลำดับของ :class:`KeyAnswer` (ตัวหลังชนะเมื่อซ้ำ)
    """
    answers = _latest(answers)
    by_id = {i.item_id: i for i in items}
    universe_ids = set(by_id)
    answered_ids = set(answers)

    missing = tuple(sorted(universe_ids - answered_ids))
    unknown = tuple(sorted(answered_ids - universe_ids))

    status_bad: list[str] = []
    shape_bad: list[str] = []
    counterpart_bad: list[str] = []
    reason_bad: list[str] = []
    used: dict[str, list[str]] = {}

    for item_id in sorted(answered_ids & universe_ids):
        a = answers[item_id]
        item = by_id[item_id]
        cp = (a.counterpart_item_id or "").strip()

        if a.key_status not in mp.STATUSES:
            status_bad.append(item_id + ":" + str(a.key_status))
            continue

        if a.key_status in mp.PAIRED_STATUSES and not cp:
            shape_bad.append(item_id + ":" + a.key_status + ":ต้องระบุคู่")
        if a.key_status in mp.NEW_ONLY_STATUSES:
            if item.side != SIDE_NEW:
                shape_bad.append(item_id + ":" + a.key_status + ":ต้องอยู่ฝั่งใหม่")
            if cp:
                shape_bad.append(item_id + ":" + a.key_status + ":ต้องไม่มีคู่")
        if a.key_status in mp.OLD_ONLY_STATUSES:
            if item.side != SIDE_OLD:
                shape_bad.append(item_id + ":" + a.key_status + ":ต้องอยู่ฝั่งเก่า")
            if cp:
                shape_bad.append(item_id + ":" + a.key_status + ":ต้องไม่มีคู่")

        if cp:
            partner = by_id.get(cp)
            if partner is None:
                counterpart_bad.append(item_id + "→" + cp + ":ไม่มีรายการนี้ในจักรวาล")
            elif partner.side == item.side:
                counterpart_bad.append(item_id + "→" + cp + ":อยู่ฝั่งเดียวกัน")
            else:
                used.setdefault(cp, []).append(item_id)

        if a.key_status in mp.HUMAN_REQUIRED and not (a.reason or "").strip():
            reason_bad.append(item_id)

    reciprocity_bad: list[str] = []
    for item_id in sorted(answered_ids & universe_ids):
        a = answers[item_id]
        cp = (a.counterpart_item_id or "").strip()
        if not cp or cp not in by_id:
            continue
        back = answers.get(cp)
        if back is None or (back.counterpart_item_id or "").strip() != item_id:
            reciprocity_bad.append(item_id + "→" + cp)
        elif back.key_status != a.key_status:
            reciprocity_bad.append(item_id + "↔" + cp + ":สถานะไม่ตรงกัน")

    reuse_bad = tuple(sorted(cp + "←" + "+".join(sorted(src))
                             for cp, src in used.items() if len(src) > 1))

    old_total = sum(1 for i in items if i.side == SIDE_OLD)
    new_total = sum(1 for i in items if i.side == SIDE_NEW)
    old_answered = sum(1 for k in answered_ids & universe_ids if by_id[k].side == SIDE_OLD)
    new_answered = sum(1 for k in answered_ids & universe_ids if by_id[k].side == SIDE_NEW)

    checks = {
        CHECK_ANSWERED: (not missing) and bool(universe_ids),
        CHECK_NO_UNKNOWN: not unknown,
        CHECK_STATUS: not status_bad,
        CHECK_SHAPE: not shape_bad,
        CHECK_COUNTERPART: not counterpart_bad,
        CHECK_RECIPROCAL: not reciprocity_bad,
        CHECK_ONCE: not reuse_bad,
        CHECK_REASON: not reason_bad,
        CHECK_TOTALS: (old_answered == old_total and new_answered == new_total
                       and bool(universe_ids)),
    }
    return Coverage(
        checks=checks,
        failed_checks=tuple(c for c in CHECKS if not checks[c]),
        missing_items=missing, unknown_items=unknown,
        shape_violations=tuple(shape_bad), counterpart_violations=tuple(counterpart_bad),
        reciprocity_violations=tuple(reciprocity_bad), reuse_violations=reuse_bad,
        reason_violations=tuple(reason_bad), status_violations=tuple(status_bad),
        counts={"universe": len(universe_ids), "answered": len(answered_ids & universe_ids),
                "old_total": old_total, "new_total": new_total,
                "old_answered": old_answered, "new_answered": new_answered})


def seal_digest(items, answers, *, schema_version, document_hashes,
                universe_manifest_digest: str) -> str:
    """แฮชผนึกของเฉลย — ผูกทุกสิ่งที่ทำให้เฉลย "เป็นเฉลยชุดนี้"

    ผูก: ตัวตนและการจับคู่ของทุกรายการ · สถานะ · เหตุผล (ผูกด้วย **แฮชของเหตุผล**
    เพื่อไม่ให้ข้อความจากเอกสารรั่วผ่านค่าที่บันทึกในที่สาธารณะ) · แฮชเนื้อเอกสาร **เต็ม**
    ทั้งสองฉบับ · เวอร์ชัน schema และ protocol · และ manifest ของจักรวาลที่ถูกตรึงไว้

    🔴 เปลี่ยนสิ่งใดสิ่งหนึ่งข้างต้น ⇒ digest เปลี่ยน ⇒ ผลที่ผนึกไว้ใช้ไม่ได้อีก
    """
    answers = _latest(answers)
    by_id = {i.item_id: i for i in items}
    lines = [
        "protocol=" + KEY_PROTOCOL_VERSION,
        "universe_version=" + KEY_UNIVERSE_VERSION,
        "gate=" + COVERAGE_GATE_VERSION,
        "schema=" + str(schema_version),
        "universe_manifest=" + universe_manifest_digest,
        "documents=" + ",".join(sorted(str(h) for h in document_hashes)),
    ]
    for item_id in sorted(by_id):
        i = by_id[item_id]
        a = answers.get(item_id)
        lines.append("|".join([
            item_id, i.side, i.identity_key, i.document_sha256, str(i.page), i.anchor,
            i.text_sha256,
            (a.key_status if a else ""),
            ((a.counterpart_item_id or "") if a else ""),
            _sha(a.reason or "") if a else "",
        ]))
    return _sha("\n".join(lines))


#: เวอร์ชันของ *พิธีการ* ผนึกผลลัพธ์เครื่อง — ผนึกที่ทำด้วยพิธีการเก่าต้อง **ล็อก** ไม่ใช่ถูกยอมรับเงียบ
#:
#: ``0.1.0`` (Pass 3–4) ผูกเฉพาะ ``ind_mappings`` + ``rules_hash``
#: ``0.2.0`` (Pass 5)   ผูกข้อสังเกต + คู่ + metadata — แต่เป็น **รายการฟิลด์ที่เลือกเอง**
#: ``0.3.0`` (Pass 6)   ผูก **ทุกคอลัมน์** ของตารางผลเครื่อง โดยอ่านรายชื่อคอลัมน์จาก schema จริง
#:                      (Bo `5615776981` P5-2 — *"Avoid another partial field list."*)
DETECTOR_SNAPSHOT_PROTOCOL = "detector-snapshot-0.3.0"

#: ส่วนประกอบของ artifact ผลเครื่อง — ชื่อส่วน → ตารางต้นทาง
DETECTOR_PARTS = (
    ("mappings", "ind_mappings"),          # คู่ · สถานะ · human_required · ความต่าง · ทางเลือก · คะแนน
    ("observations", "ind_observations"),  # ข้อความ · พิกัด · ขนาดหน้า · ฟิลด์เชิงความหมาย · ธง
    ("metadata", "ind_runs"),              # เวอร์ชัน · backend · กฎ · page inventory · บัญชี
    ("documents", "evd_documents"),        # บริบทเอกสารที่หน้าหลักฐาน/รายงาน/package ใช้
)

#: คอลัมน์ที่ **ไม่** เข้า projection — ต้องมีชื่อและเหตุผลเสมอ (มีเทสต์บังคับว่าเป็นชุดนี้เท่านั้น)
DETECTOR_PROJECTION_EXCLUDED = {
    # ที่อยู่ไฟล์ในเครื่อง — เป็นข้อมูลส่วนตัว · ไม่ถูกแสดงหรือส่งออก · เนื้อไฟล์ถูกผูกแล้วด้วย
    # ``content_sha256`` ในส่วนเดียวกัน ⇒ ย้ายไฟล์ไม่ทำให้ผลลัพธ์ที่ส่งมอบเปลี่ยน
    "evd_documents": ("local_path_private",),
}


def _canonical_value(v) -> str:
    """ค่าหนึ่งช่องในรูปที่คงที่ — แยก None ออกจากสตริงว่าง · ทศนิยมใช้ ``repr``"""
    if v is None:
        return "\x00"
    if isinstance(v, bool):
        return "b:" + ("1" if v else "0")
    if isinstance(v, int):
        return "i:" + str(v)
    if isinstance(v, float):
        return "f:" + repr(v)
    if isinstance(v, (bytes, bytearray)):
        return "x:" + hashlib.sha256(bytes(v)).hexdigest()
    text = str(v)
    # ค่ายาวผูกด้วยแฮช — ไม่ให้ข้อความของเอกสารเข้าไปอยู่ในบรรทัดดิบของ digest
    return "s:" + (_sha(text) if len(text) > 64 else text.replace("|", "\\|"))


def canonical_rows_digest(table: str, columns, rows) -> str:
    """แฮชของ **ทุกแถว × ทุกคอลัมน์** ที่ส่งมา — รายชื่อคอลัมน์อยู่ในหัวของ digest

    คอลัมน์เรียงตามชื่อ · แถวเรียงตามข้อความที่ serialize แล้ว ⇒ ไม่ขึ้นกับลำดับที่ query คืน
    เพิ่ม/ลบ/เปลี่ยนชื่อคอลัมน์ ⇒ หัวเปลี่ยน ⇒ digest เปลี่ยน
    """
    cols = sorted(columns)
    body = sorted("|".join(_canonical_value(r[c]) for c in cols) for r in rows)
    head = "table=%s;columns=%s;rows=%d" % (table, ",".join(cols), len(body))
    return _sha("\n".join([head] + body))


def detector_snapshot_digest(*, part_digests: dict, pair_count: int,
                             observation_count: int, schema_version) -> str:
    """แฮชผนึกของ **ผลลัพธ์เครื่องทั้งชุด** — แยกจากเฉลยโดยสิ้นเชิง"""
    lines = [
        "protocol=" + DETECTOR_SNAPSHOT_PROTOCOL,
        "key_protocol=" + KEY_PROTOCOL_VERSION,
        "schema=" + str(schema_version),
        "pairs=" + str(int(pair_count)),
        "observations=" + str(int(observation_count)),
    ]
    for name, _table in DETECTOR_PARTS:
        lines.append(name + "_digest=" + part_digests[name])
    return _sha("\n".join(lines))


# ══════════════════════════════════════════════════════════════════════════════
#  P3-1 — การ **ตรวจ** ผนึก (ไม่ใช่แค่ "มีแถว seal อยู่")
# ══════════════════════════════════════════════════════════════════════════════
#
# 🔴 Bo (`5605652708` §"Freeze blocker P3-1") — *"A stored hash is only evidence;
# it is not an enforcement gate until verified."*
#
# ทุกครั้งที่จะเปิดขั้นตัดสิน ต้อง **คำนวณใหม่จากแถวปัจจุบัน** แล้วเทียบกับค่าที่ผนึกไว้
# เทียบด้วย :func:`hmac.compare_digest` และคืน **รหัสเหตุผล** เมื่อไม่ตรง

ARTIFACT_UNIVERSE = "UNIVERSE"
ARTIFACT_KEY = "KEY"
ARTIFACT_DETECTOR = "DETECTOR_OUTPUT"

R_UNIVERSE_NOT_FROZEN = "UNIVERSE_NOT_FROZEN"
R_UNIVERSE_DIGEST_MISMATCH = "UNIVERSE_DIGEST_MISMATCH"
R_UNIVERSE_ROWS_DIFFER = "UNIVERSE_ROWS_DIFFER_FROM_INDEPENDENT_INVENTORY"
R_UNIVERSE_COUNT_MISMATCH = "UNIVERSE_ITEM_COUNT_MISMATCH"
R_KEY_NOT_SEALED = "KEY_NOT_SEALED"
R_KEY_DIGEST_MISMATCH = "KEY_DIGEST_MISMATCH"
R_KEY_COVERAGE_BROKEN = "KEY_COVERAGE_NO_LONGER_CLOSED"
R_KEY_COUNT_MISMATCH = "KEY_ANSWER_COUNT_MISMATCH"
R_DETECTOR_NOT_SEALED = "DETECTOR_OUTPUT_NOT_SEALED"
R_DETECTOR_DIGEST_MISMATCH = "DETECTOR_OUTPUT_DIGEST_MISMATCH"
R_DETECTOR_COUNT_MISMATCH = "DETECTOR_PAIR_COUNT_MISMATCH"
R_DETECTOR_RULES_MISMATCH = "DETECTOR_RULES_HASH_MISMATCH"
R_DETECTOR_PROTOCOL_OUTDATED = "DETECTOR_SNAPSHOT_PROTOCOL_OUTDATED"
R_DETECTOR_OBSERVATIONS_MISMATCH = "DETECTOR_OBSERVATIONS_DIGEST_MISMATCH"
R_DETECTOR_OBSERVATION_COUNT_MISMATCH = "DETECTOR_OBSERVATION_COUNT_MISMATCH"
R_DETECTOR_METADATA_MISMATCH = "DETECTOR_RUN_METADATA_MISMATCH"
R_DETECTOR_MAPPINGS_MISMATCH = "DETECTOR_MAPPINGS_DIGEST_MISMATCH"
R_DETECTOR_DOCUMENTS_MISMATCH = "DETECTOR_DOCUMENT_CONTEXT_MISMATCH"

REASON_LABELS = {
    R_UNIVERSE_NOT_FROZEN: "ยังไม่ตรึงจักรวาลของเฉลย",
    R_UNIVERSE_DIGEST_MISMATCH: "จักรวาลปัจจุบันไม่ตรงกับแฮชที่ตรึงไว้",
    R_UNIVERSE_ROWS_DIFFER: "จักรวาลที่บันทึกไว้ไม่ตรงกับทะเบียนข้อสังเกตอิสระปัจจุบัน",
    R_UNIVERSE_COUNT_MISMATCH: "จำนวนรายการไม่ตรงกับที่ตรึงไว้",
    R_KEY_NOT_SEALED: "ยังไม่ผนึกเฉลย",
    R_KEY_DIGEST_MISMATCH: "เฉลยปัจจุบันไม่ตรงกับแฮชที่ผนึกไว้",
    R_KEY_COVERAGE_BROKEN: "เฉลยไม่ผ่านด่านความครบถ้วนอีกต่อไป",
    R_KEY_COUNT_MISMATCH: "จำนวนคำตอบไม่ตรงกับที่ผนึกไว้",
    R_DETECTOR_NOT_SEALED: "ยังไม่ผนึกผลลัพธ์ของเครื่อง",
    R_DETECTOR_DIGEST_MISMATCH: "ผลลัพธ์ของเครื่องปัจจุบันไม่ตรงกับแฮชที่ผนึกไว้",
    R_DETECTOR_COUNT_MISMATCH: "จำนวนคู่ที่เครื่องเสนอไม่ตรงกับที่ผนึกไว้",
    R_DETECTOR_RULES_MISMATCH: "เกณฑ์ของเครื่องไม่ตรงกับที่ผนึกไว้",
    R_DETECTOR_PROTOCOL_OUTDATED: "ผนึกผลของเครื่องทำด้วยพิธีการเก่าที่ไม่ครอบข้อสังเกต — ต้องเปิดรอบใหม่",
    R_DETECTOR_OBSERVATIONS_MISMATCH: "ข้อสังเกตที่เครื่องสกัดไม่ตรงกับที่ผนึกไว้",
    R_DETECTOR_OBSERVATION_COUNT_MISMATCH: "จำนวนข้อสังเกตที่เครื่องสกัดไม่ตรงกับที่ผนึกไว้",
    R_DETECTOR_METADATA_MISMATCH: "ค่าตั้ง/เวอร์ชันของเครื่องหรือข้อมูลกำกับของรอบไม่ตรงกับที่ผนึกไว้",
    R_DETECTOR_MAPPINGS_MISMATCH: "คู่ที่เครื่องเสนอไม่ตรงกับที่ผนึกไว้",
    R_DETECTOR_DOCUMENTS_MISMATCH: "ข้อมูลกำกับของเอกสารที่รอบนี้อ้างไม่ตรงกับที่ผนึกไว้",
}


def digests_equal(a: object, b: object) -> bool:
    """เทียบแฮชแบบ constant-time — ค่าว่างถือว่าไม่ตรงเสมอ"""
    sa, sb = str(a or ""), str(b or "")
    if not sa or not sb:
        return False
    return hmac.compare_digest(sa, sb)


@dataclass(frozen=True)
class SealCheck:
    """ผลการตรวจผนึกหนึ่ง artifact — ``ok`` เท่านั้นที่ถือว่าผ่าน"""
    artifact: str
    ok: bool
    reasons: tuple = ()
    sealed_digest: str = ""
    current_digest: str = ""

    @property
    def labels(self) -> tuple:
        return tuple(REASON_LABELS.get(r, r) for r in self.reasons)


@dataclass(frozen=True)
class SealVerification:
    """ผลรวมของการตรวจทั้งสาม artifact — ด่านจริงของขั้นตัดสินหลังรัน"""
    universe: SealCheck
    key: SealCheck
    detector: SealCheck

    @property
    def checks(self) -> tuple:
        return (self.universe, self.key, self.detector)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def reasons(self) -> tuple:
        out: list[str] = []
        for c in self.checks:
            out.extend(c.reasons)
        return tuple(out)

    @property
    def labels(self) -> tuple:
        return tuple(REASON_LABELS.get(r, r) for r in self.reasons)

    def summary(self) -> str:
        if self.ok:
            return "ผนึกครบและตรวจแล้วว่าตรงทุกชั้น"
        return "ยังเปิดขั้นตัดสินไม่ได้ — " + " · ".join(self.labels)


__all__ = [
    "KEY_UNIVERSE_VERSION", "KEY_PROTOCOL_VERSION", "COVERAGE_GATE_VERSION",
    "SIDE_OLD", "SIDE_NEW", "SIDES", "ITEM_PREFIX", "FULL_DIGEST_LEN",
    "UniverseError", "UniverseItem", "KeyAnswer", "Coverage",
    "item_id_for", "build_items", "universe_digest", "check_coverage",
    "seal_digest", "detector_snapshot_digest", "canonical_rows_digest",
    "DETECTOR_SNAPSHOT_PROTOCOL", "DETECTOR_PARTS", "DETECTOR_PROJECTION_EXCLUDED",
    "CHECKS", "CHECK_LABELS", "CHECK_ANSWERED", "CHECK_NO_UNKNOWN", "CHECK_STATUS",
    "CHECK_SHAPE", "CHECK_COUNTERPART", "CHECK_RECIPROCAL", "CHECK_ONCE",
    "CHECK_REASON", "CHECK_TOTALS",
    "SealCheck", "SealVerification", "digests_equal", "REASON_LABELS",
    "ARTIFACT_UNIVERSE", "ARTIFACT_KEY", "ARTIFACT_DETECTOR",
    "R_UNIVERSE_NOT_FROZEN", "R_UNIVERSE_DIGEST_MISMATCH", "R_UNIVERSE_ROWS_DIFFER",
    "R_UNIVERSE_COUNT_MISMATCH", "R_KEY_NOT_SEALED", "R_KEY_DIGEST_MISMATCH",
    "R_KEY_COVERAGE_BROKEN", "R_KEY_COUNT_MISMATCH", "R_DETECTOR_NOT_SEALED",
    "R_DETECTOR_DIGEST_MISMATCH", "R_DETECTOR_COUNT_MISMATCH", "R_DETECTOR_RULES_MISMATCH",
    "R_DETECTOR_PROTOCOL_OUTDATED", "R_DETECTOR_OBSERVATIONS_MISMATCH",
    "R_DETECTOR_OBSERVATION_COUNT_MISMATCH", "R_DETECTOR_METADATA_MISMATCH",
    "R_DETECTOR_MAPPINGS_MISMATCH", "R_DETECTOR_DOCUMENTS_MISMATCH",
]
