# -*- coding: utf-8 -*-
"""ตัวช่วยของชุดทดสอบ — เดินขั้นประเมินให้ครบจนปลดล็อกขั้นตัดสินหลังรัน

ลำดับที่ระบบบังคับตั้งแต่ **Pass 4** (Bo `5605652708`)

    กรอกทะเบียนข้อสังเกตอิสระ → ตรึงจักรวาล → ผนึกผลลัพธ์ของเครื่อง
        → ตอบเฉลยให้ครบ → ผนึกเฉลย → ขั้นตัดสินหลังรันจึงเปิด

🔴 **ข้อจำกัดของตัวช่วยนี้ที่ต้องอ่านก่อนใช้**
:func:`enter_inventory_mirroring_observations` จำลอง "ผู้ดูแลที่บังเอิญอ่านเจอพอดีกับ
สิ่งที่เครื่องสกัดได้" โดยอ่านข้อความจาก ``ind_observations`` มากรอกเป็นทะเบียนอิสระ ·
ทำเช่นนี้ได้เฉพาะในเทสต์ที่ **ไม่ได้ทดสอบเรื่องความครอบคลุม** เพื่อไม่ต้องพิมพ์ข้อความ
ของ fixture ซ้ำในทุกไฟล์ · เทสต์ที่ทดสอบว่าเครื่อง **สกัดตกหล่น** ต้องกรอกทะเบียนเอง
ด้วย :func:`redbook.indicators.registry.record_source_item` ตรง ๆ

🔴 เฉลยทั้งหมดในชุดทดสอบเป็น **ข้อมูลสังเคราะห์เพื่อพิสูจน์กลไก** ไม่ใช่เฉลยของงานวิจัย
"""
from __future__ import annotations

from redbook.indicators import keyuniverse as ku
from redbook.indicators import mapping as mp
from redbook.indicators import normalize as nz
from redbook.indicators import registry as reg

SYNTHETIC_NOTE = "SYNTHETIC MECHANISM TEST — ไม่ใช่เฉลยของงานวิจัย"


def enter_inventory_mirroring_observations(run_id, db_path=None, *,
                                           by="key-custodian") -> int:
    """กรอกทะเบียนอิสระให้ตรงกับสิ่งที่เครื่องสกัดได้ — ดูข้อจำกัดในหัวไฟล์"""
    if reg.source_inventory_rows(run_id, db_path):
        return 0
    obs = reg.observations(run_id, db_path)
    ordered = sorted(obs.values(),
                     key=lambda o: (o.extra.get("side", ""), o.page, o.line_index,
                                    o.observation_id))
    # นิยามของ occurrence (source-inventory-0.2.0) = ครั้งที่เท่าไรที่ **ข้อความเดียวกัน**
    # ปรากฏในหน้านั้น — ข้อความที่ปรากฏครั้งเดียว = 1 เสมอ
    seen: dict[tuple, int] = {}
    n = 0
    for o in ordered:
        side = o.extra.get("side", "")
        group = (side, o.page, nz.normalize(o.observed_text))
        occurrence = seen.get(group, 0) + 1
        seen[group] = occurrence
        reg.record_source_item(run_id=run_id, side=side, page=o.page,
                               observed_text=o.observed_text, occurrence=occurrence,
                               entered_by=by, db_path=db_path)
        n += 1
    return n


def build_and_freeze(run_id, db_path=None, *, by="key-custodian"):
    """กรอกทะเบียนอิสระ (ถ้ายังว่าง) → สร้างจักรวาล → ตรึง"""
    if reg.universe_seal(run_id, db_path) is not None:
        return reg.key_universe(run_id, db_path)
    enter_inventory_mirroring_observations(run_id, db_path, by=by)
    reg.build_key_universe(run_id, built_by=by, db_path=db_path)
    reg.freeze_key_universe(run_id, frozen_by=by, db_path=db_path)
    return reg.key_universe(run_id, db_path)


def seal_detector(run_id, db_path=None, *, by="key-custodian"):
    if reg.detector_snapshot(run_id, db_path) is None:
        reg.seal_detector_snapshot(run_id, sealed_by=by, note=SYNTHETIC_NOTE,
                                   db_path=db_path)
    return reg.detector_snapshot(run_id, db_path)


def ready_for_answers(run_id, db_path=None, *, by="key-custodian"):
    """เดินถึงขั้นที่กรอกคำตอบของเฉลยได้ — ตรึงจักรวาลแล้วและผนึกผลของเครื่องแล้ว"""
    items = build_and_freeze(run_id, db_path, by=by)
    seal_detector(run_id, db_path, by=by)
    return items


def pairing_by_identical_text(run_id, db_path=None) -> dict:
    """คู่ที่ชุดทดสอบกำหนดเอง — ``item_id -> item_id`` (สองทาง)

    กติกาของชุดทดสอบล้วน: ข้อความในทะเบียนอิสระที่ทำรูปมาตรฐานแล้วตรงกัน ⇒ เป็นคู่กัน
    **ไม่ได้เรียก detector**
    """
    items = reg.key_universe(run_id, db_path)
    inv = {r.identity_key: r for r in reg.source_inventory_rows(run_id, db_path)}

    def norm(item):
        row = inv.get(item.identity_key)
        return nz.normalize(row.observed_text) if row else ""

    buckets: dict[str, list] = {}
    for i in items:
        if i.side == ku.SIDE_NEW:
            buckets.setdefault(norm(i), []).append(i)
    pairs: dict[str, str] = {}
    for i in items:
        if i.side != ku.SIDE_OLD:
            continue
        bucket = buckets.get(norm(i))
        if bucket:
            partner = bucket.pop(0)
            pairs[i.item_id] = partner.item_id
            pairs[partner.item_id] = i.item_id
    return pairs


def answer_all(run_id, db_path=None, *, by="key-custodian") -> int:
    """ตอบเฉลยให้ครบทุกรายการในจักรวาล — คืนจำนวนรายการที่ตอบ"""
    items = reg.key_universe(run_id, db_path)
    pairs = pairing_by_identical_text(run_id, db_path)
    n = 0
    for i in items:
        cp = pairs.get(i.item_id, "")
        if cp:
            status = mp.SAME_EXACT
        elif i.side == ku.SIDE_OLD:
            status = mp.REMOVED_INDICATOR
        else:
            status = mp.NEW_INDICATOR
        reg.record_key_answer(run_id=run_id, item_id=i.item_id, key_status=status,
                              counterpart_item_id=cp, reason="", entered_by=by,
                              db_path=db_path)
        n += 1
    return n


def unlock_adjudication(run_id, db_path=None, *, by="key-custodian"):
    """เดินครบทุกขั้นจนขั้นตัดสินหลังรันเปิด"""
    ready_for_answers(run_id, db_path, by=by)
    if reg.key_seal(run_id, db_path) is None:
        answer_all(run_id, db_path, by=by)
        reg.seal_key(run_id, sealed_by=by, note=SYNTHETIC_NOTE, db_path=db_path)
    return reg.key_seal(run_id, db_path)
