# -*- coding: utf-8 -*-
"""ทดลองตรวจเล่มสำหรับผู้ปฏิบัติงาน (#43) — นับตามวิธีวัดผลฉบับ 0.2 (ร่าง · ยังไม่ตรึง)

สเปก: repo เล่ม ``04_methodology/MEASUREMENT_METHOD_R3_PDF.md`` หมวด 2–8 และ 13 · คำขอของโบ #43
``6359289065`` และ ``6361719346``

ลำดับ (ห้ามสลับ — กันผลระบบชี้นำรายการอ้างอิง):

1. เลือกเล่ม + ทางทำรายการอ้างอิง — **ร1** ใช้รายการเดิมที่ผู้ตรวจเก็บเอง (ทางหลัก) · **ร2** วงจุดบนภาพหน้า (ทางเลือก)
2. ส่ง **ใบประกาศก่อนเห็นผล** (แบบ 02 ส่วนที่ ๑: วันที่จัดทำ · ที่มา · ฉบับที่ใช้ · ทำก่อนเห็นผลหรือไม่ · เคยเห็นผล
   ระบบของคู่นี้หรือไม่ · ความครอบคลุมรายส่วน ๑–๘ · จำนวนประเด็นรายหัวข้อ ก–ญ / ต้นเหตุ / แดง) = **ล็อก** —
   ไม่บังคับกด "ตรวจหน้านี้แล้ว" ครบทุกหน้า · **ระบบเพิ่งเทียบตอนนี้** ครั้งเดียวต่อรอบ
3. จับคู่ประเด็น ↔ ข้อสังเกตทุกระดับ (ต้องตรวจ · ข้อมูลประกอบ) — ระบบเสนอจากตำแหน่ง ผู้ตรวจยืนยันเอง ·
   หนึ่งต่อหลาย/หลายต่อหนึ่ง · พบตรง / พบบางส่วน (บ1–บ4) / พลาด (พ1–พ5) / ตัดสินไม่ได้ · หลักฐานชี้ตำแหน่ง ·
   ฐานการวินิจฉัย · เปลี่ยนคู่ต้องมีเหตุผล (เก็บประวัติ)
4. จัดข้อสังเกตต้องตรวจที่ไม่ได้จับคู่ — ส1–ส4 หรือ "นอกส่วนที่ตรวจครบ" · บัญชี ``F = จ + ส1 + ส2 + ส3 + ส4`` ต้องปิด
   (ข้อมูลไม่สอดคล้อง = :class:`LedgerError` ห้ามรายงาน)
5. จบการใช้ผล → แบบสอบถามหลังใช้ผล (แบบ 03 ฉบับ 0.2) → แดชบอร์ด → สรุปเฉพาะจำนวน

🔴 ระบบไม่ตัดสินแทนผู้ตรวจ · ด้าน A (ความถูกต้อง) กับด้าน B (ประโยชน์) รายงานแยกกัน ไม่มีคะแนนรวม · ไม่วัดเวลา ·
รอบที่เริ่มก่อนฉบับ 0.2 (``protocol`` ว่าง) = "รอบกติกา 0.1" อ่าน/นับตามรุ่นเดิมเท่านั้น ทั้งที่ส่งแล้วและยังไม่ส่ง
(ASK-GIFT ทาง ก · 26 ต.ค. 2569) — ไม่เปลี่ยนรุ่นอัตโนมัติ · งานตามฉบับ 0.2 = เริ่มรอบใหม่ ·
ความยินยอมก่อนเริ่มทำรายการ (ไม่ใช่ก่อนส่งแบบสอบถาม)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import threading
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ..pdfbook import PDFBOOK_VERSION, profile as prof, reader
from ..pdfbook import compare as cmp
from ..storage import trial_repo
from . import pdfpair, pdfshelf
from . import trial_aggregate as agg

TRIAL_ENV = "REDBOOK_TRIAL_BOOKS"
TRIAL_VERSION = "trial-0.3.0"
PROTOCOL_VERSION = "pdfpair-protocol-0.3 (ร่าง ๒)"
LEGACY_PROTOCOL = "pdfpair-protocol-0.1 (ร่าง)"
PAGE_ZOOM = 1.5

PATHS = {"r1": "ร1 — ใช้รายการเดิมของฉัน (ทางหลัก)", "r2": "ร2 — วงจุดบนภาพหน้าเอกสาร (ทางเลือก)"}
PENS = {"red": "ปากกาแดง — สำคัญ", "brown": "ปากกาน้ำตาล — สำคัญน้อยกว่า", "pin": "หมุด — ของที่หายไป"}
LEVELS = {"red": "แดง — สำคัญ", "brown": "น้ำตาล — สำคัญน้อยกว่า"}
CAUSES = {"t": "ต — ต้นเหตุ", "l": "ล — ผลที่ตามมา"}
#: หัวข้อในขอบเขต (วิธีวัดผล ข้อ 2.2)
TOPIC_CODES = (("ก", "ยอดรวมและวงเงินตามหมวดงบรายจ่าย"), ("ข", "รายจ่ายประจำและรายจ่ายลงทุน"),
               ("ค", "แผนงาน ผลผลิต/โครงการ กิจกรรม (เพิ่ม หาย ชื่อเปลี่ยน ย้ายแผน)"),
               ("ง", "รายการที่เสนอตั้ง / ไม่เสนอตั้ง"), ("จ", "วงเงินรวมโครงการและรายการผูกพันข้ามปี"),
               ("ฉ", "ประมาณการรายจ่ายล่วงหน้า (MTEF)"), ("ช", "ตัวชี้วัด ค่าเป้าหมาย และหน่วยนับ"),
               ("ซ", "ชื่อหน่วยงาน วิสัยทัศน์ พันธกิจ ผลสัมฤทธิ์ วัตถุประสงค์"),
               ("ฌ", "เลขนำหน้า วงเล็บ จุด หัวตาราง และหน่วยของตาราง"),
               ("ญ", "ความสอดคล้องภายในเล่ม (ยอดรวม ↔ รายการย่อย ↔ ตารางอื่น)"))
TOPIC_LABELS = dict(TOPIC_CODES)
#: ส่วนของเล่ม (วิธีวัดผล ข้อ 2.2)
PARTS = (("๑", "ส่วนต้น: ชื่อหน่วยงาน · งบประมาณรายจ่าย / เงินนอกงบประมาณ (ตารางต้นช่วง)"),
         ("๒", "วิสัยทัศน์ · พันธกิจ"), ("๓", "ผลสัมฤทธิ์หรือประโยชน์ที่คาดว่าจะได้รับ + ตัวชี้วัด"),
         ("๔", "ตารางเปรียบเทียบงบประมาณรายจ่ายรายปี"), ("๕", "เป้าหมายการให้บริการ + ประมาณการรายจ่ายล่วงหน้า"),
         ("๖", "ตารางสรุปตามแผนงาน/ผลผลิต และงบรายจ่าย · รายจ่ายประจำ/ลงทุน"),
         ("๗", "รายละเอียดงบประมาณ: ผลผลิต/โครงการ · วัตถุประสงค์ · ตัวชี้วัด · กิจกรรม · รายการ · ผูกพัน"),
         ("๘", "เงินนอกงบประมาณ"))
PART_LABELS = dict(PARTS)
COVERAGE = {"full": "ตรวจครบ", "partial": "ตรวจบางส่วน", "none": "ไม่ได้ตรวจ"}
SOURCES = {"routine": "จากงานตรวจเล่มตามปกติ", "form01": "จัดทำด้วยแบบ ๐๑", "web": "วงจุดในหน้าผู้ตรวจ"}
MADE = {"before": "จัดทำรายการนี้ก่อนเห็นผลของระบบสำหรับคู่นี้", "after": "จัดทำหลังเห็นผลของระบบ หรือไม่แน่ใจ"}
SEEN = {"never": "ไม่เคยเห็นผลของระบบกับคู่นี้", "seen": "เคยเห็นผลของระบบหรือการสาธิตกับคู่นี้มาก่อน"}
VERDICTS = {"exact": "พบตรง", "partial": "พบบางส่วน", "missed": "พลาด", "undecidable": "ตัดสินไม่ได้"}
PARTIAL_REASONS = {"b1": "บ1 ค่าไม่ตรง", "b2": "บ2 ทิศทางหรือชนิดความต่างไม่ตรง",
                   "b3": "บ3 ครอบคลุมเพียงบางส่วนของประเด็น", "b4": "บ4 ตำแหน่งใกล้เคียง (คอลัมน์/บรรทัดติดกัน)"}
MISS_REASONS = {"p1": "พ1 ระบบอ่านหรือสกัดไม่สำเร็จจนพลาด (มีหลักฐาน)", "p2": "พ2 ระบบจับคู่คนละรายการ", "p3": "พ3 ระบบไม่ได้ยก",
                "p4": "พ4 ระบบแสดงข้อความหรือค่าเพี้ยน", "p5": "พ5 ไม่ทราบ"}
EVIDENCE = {"all": "หลักฐานชี้ตำแหน่งถูกทุกฉบับที่เกี่ยวข้อง", "some": "ถูกบางฉบับ", "none": "ไม่ถูก"}
BASIS = {"enough": "หลักฐานในระบบพอ", "opened": "ต้องเปิดเอกสารต้นฉบับ", "cannot": "วินิจฉัยไม่ได้"}
GROUPS = {"s1": "ส1 ต่างจริงแต่ไม่อยู่ในรายการ", "s2": "ส2 ผลที่ตามมาของประเด็นที่มีในรายการ",
          "s3": "ส3 ไม่ใช่ความต่าง", "s4": "ส4 ตัดสินไม่ได้", "outside": "อยู่นอกส่วนที่ตรวจครบ (นับจำนวนเท่านั้น)"}
S_GROUPS = ("s1", "s2", "s3", "s4")
S3_REASONS = {"misread": "ระบบอ่านค่าหรือข้อความไม่ตรงกับภาพ", "mismatch": "ระบบจับคู่คนละรายการ",
              "rounding": "ปัดเศษ", "other": "อื่น ๆ"}
FINDING_LEVELS = {"must": "ต้องตรวจ", "info": "ข้อมูลประกอบ", "unread": "ระบบอ่านหรือสกัดไม่ได้",
                  "descriptive": "คู่ข้ามปี: ไม่ใช่ความต่างเชิงโครงสร้าง (นับจำนวนเชิงพรรณนาเท่านั้น)",
                  "review": "คู่ข้ามปี: กติกาไม่รู้จักชนิด/ป้ายนี้ หรือรุ่นตัวเทียบไม่ตรงกติกา — ต้องทบทวน (ยังสรุปผลไม่ได้)"}
#: นิยามระดับของข้อสังเกตที่ระบบรุ่นนี้ใช้ — ต้องประกาศในเอกสารความสามารถของรุ่นที่ตรึง (วิธีวัดผล ข้อ 2.8)
LEVEL_DEFINITION = ("ระบบอ่านหรือสกัดไม่ได้ = หน้าที่ไม่มีชั้นข้อความ หรือบรรทัดที่มีตัวเลขแต่ระบบจัดเข้าตารางไม่ได้ "
                    "(kind unread · ไม่จับคู่ ไม่เข้า F) · ระบบไม่พบหัวข้อ (section_missing) ≠ อ่านไม่ได้ — "
                    "ต้องตรวจว่าหายจริงหรือสกัดตก · ระดับตามกติกาชนิดคู่ · "
                    "ข้อมูลประกอบ = ข้อที่ตัวเทียบติดป้ายข้อมูลประกอบ (info) เช่น การเปลี่ยนแปลงระหว่างปีของคู่ข้ามปี · "
                    "ต้องตรวจ = ข้ออื่นทั้งหมด · ข้อมูลประกอบไม่เท่ากับนอกขอบเขต — จับคู่กับประเด็นได้เหมือนข้อต้องตรวจ · "
                    "คู่ข้ามปี: ข้อเชิงโครงสร้างตามกติกา XYEAR_RULE = ต้องตรวจ (แม้ตัวเทียบติดข้อมูลประกอบ) · "
                    "ข้ออื่น = เชิงพรรณนา ไม่จับคู่ ไม่จัด ส1–ส4 ไม่นับใน F")
STATUSES = {"stopped": "หยุดรอบนี้", "withdrawn": "ถอนตัว"}
# ── ฉบับ 0.3 ร่าง ๒ (Bo ACCEPT #36 6460469107 · schema RESULT_SCHEMA_R3_0.3) ─────────────────────────────
#: พบบางส่วน 0.3 = บ1–บ3 (บ4 ย้ายไปเป็นสถานะตำแหน่ง "ใกล้เคียง")
PARTIAL_REASONS_V03 = {k: v for k, v in PARTIAL_REASONS.items() if k != "b4"}
#: สถานะตำแหน่ง 6 กลุ่ม ไม่ทับกัน ตัดสินตามลำดับ (เลือกข้อแรกที่เข้า)
LOCATIONS = {"undecidable": "ตัดสินไม่ได้ — มีกรอบแต่ยืนยันจากภาพไม่ได้ (เหตุที่การตัดสิน)",
             "no_box": "ไม่มีกรอบบนฝั่งที่เกี่ยวข้อง (เหตุที่ระบบ)",
             "all_sides": "ถูกทุกฝั่งที่เกี่ยวข้อง",
             "some_sides": "ถูกบางฝั่ง (เฉพาะประเด็นที่มี 2 ฝั่ง)",
             "adjacent": "ใกล้เคียง — กรอบอยู่คอลัมน์/บรรทัดติดกันของรายการเดียวกัน",
             "wrong": "ไม่ถูก"}
FIDELITY = {"full": "ตรงครบ", "partial": "ตรงบางส่วน", "none": "ไม่ตรง", "undecidable": "ตัดสินไม่ได้"}
FIDELITY_REASONS = {"misread": "อ่านผิด", "unit": "หน่วยหรือสเกลผิด", "rounding": "ปัดเศษ", "year": "ปีผิด"}
ASSERTION = {"full": "ถูกครบ", "partial": "ถูกบางส่วน", "none": "ไม่ถูก", "undecidable": "ตัดสินไม่ได้"}
DIM_VALUES = {"ok": "ถูก", "wrong": "ไม่ถูก", "na": "ไม่ใช้ (N/A — ระบุเหตุ)"}
DIMS = {"real": "มีความต่าง/ความไม่สอดคล้อง/ความกำกวมจริง", "kind": "ชนิด (เปลี่ยน/เพิ่ม/หาย/ย้าย)",
        "direction": "ทิศทาง (เพิ่ม/ลด)", "unit": "หน่วย", "year": "ปี", "item_match": "การจับคู่รายการข้ามฉบับ",
        "items_used": "รายการที่นำมาคำนวณ"}
#: ชนิดข้อสังเกต (ความหมายของ A3-ข) จากชนิดของตัวเทียบ
OBS_KINDS = {"value_change": "เปลี่ยนค่า/ข้อความระหว่างสองฉบับ", "add_remove_move_rename": "เพิ่ม/หาย/ย้าย/เปลี่ยนชื่อ",
             "consistency": "ความไม่สอดคล้องภายในเล่ม", "identity_warning": "คำเตือนจับคู่รายการไม่แน่ชัด",
             "unreadable": "อ่านไม่ได้"}
_OBS_KIND_OF = {cmp.K_CHANGED: "value_change", cmp.K_YEAR_CHANGE: "value_change",
                cmp.K_SAME_YEAR_DIFF: "value_change", cmp.K_DASH_VS_VALUE: "value_change",
                cmp.K_BLANK_VS_VALUE: "value_change", cmp.K_NOT_PROPOSED: "value_change",
                cmp.K_ONLY_A: "add_remove_move_rename", cmp.K_ONLY_B: "add_remove_move_rename",
                cmp.K_RENAMED: "add_remove_move_rename", cmp.K_MOVED: "add_remove_move_rename",
                cmp.K_SECTION_MISSING: "add_remove_move_rename",
                cmp.K_SUM: "consistency", cmp.K_CROSS_TABLE: "consistency",
                cmp.K_LABEL_VARIANT: "identity_warning", cmp.K_IDENTITY: "identity_warning",
                cmp.K_UNREAD: "unreadable"}
DIMS_BY_OBS_KIND = {"value_change": ("real", "kind", "direction", "unit", "year", "item_match"),
                    "add_remove_move_rename": ("real", "kind", "item_match", "year"),
                    "consistency": ("real", "unit", "year", "items_used"),
                    "identity_warning": ("real",), "unreadable": ("real",)}


def obs_kind(f) -> str:
    return _OBS_KIND_OF.get(f.kind, "value_change")


#: ปัญหาการอ่านของระบบ แยก 3 ชนิด (รีวิวโบผ่านกิ๊ฟ 28 ต.ค.: ไม่พบหัวข้อ ≠ อ่านไม่ได้) ·
#: พ1 ใช้เมื่อมีหลักฐานว่าการอ่าน/สกัดไม่สำเร็จเป็นเหตุให้พลาด — ไม่ใช้กับหัวข้อที่หายจริงโดยอัตโนมัติ
READ_PROBLEMS = {"no_text": "หน้าไม่มีชั้นข้อความ (ระบบไม่ใช้ OCR)",
                 "unparsed": "มีตัวเลขแต่ระบบสกัดหรือจัดเข้าตาราง/หมวดไม่ได้",
                 "not_found": "ระบบไม่พบหัวข้อ — ต้องตรวจว่าหายจริงหรือสกัดตก"}
P1_HINT = ("ใช้ พ1 เมื่อมีหลักฐานว่าระบบอ่านหรือสกัดไม่สำเร็จจนพลาด (หน้าไม่มีชั้นข้อความ · บรรทัดที่สกัดไม่ได้) · "
           "หัวข้อที่ระบบไม่พบต้องดูภาพก่อนว่าหายจริงหรือสกัดตก — หายจริงไม่ใช่ พ1")


def read_problem(f) -> str:
    """ชนิดปัญหาการอ่านของข้อสังเกต ("" = ไม่ใช่) — ผูกกับชนิดของ pdfbook-0.5.0–0.5.3 (เทสต์ล็อก)"""
    if f.kind == cmp.K_SECTION_MISSING:
        return "not_found"
    if f.kind == cmp.K_UNREAD:
        return "unparsed" if (f.a.bbox or f.b.bbox) else "no_text"
    return ""
#: ที่มาของลักษณะแถว ร1 ที่กรอกหลังล็อก (รีวิวโบ 6414605109 ข้อ 2)
ROW_SOURCES = {"transcribed": "ทุกลักษณะถอดจากรายการที่ล็อกไว้ (ต้นฉบับก่อนเห็นผล)",
               "post_result": "มีลักษณะที่จัดใหม่หลังเห็นผล (เลือกมิติ)"}
#: มิติที่อาจจัดใหม่หลังเห็นผล — ตัวประเด็นยังมาจากรายการที่ล็อก (นับในผลรวมหลัก) แยกเฉพาะมิตินั้น
#: (รีวิวโบ 6417479593: แยก provenance ของตัวประเด็นกับของหมวด/ต-ล/ระดับ)
POST_DIMS = {"part": "ส่วนของเล่ม", "cause": "ต/ล", "level": "ระดับ", "xtype": "ชนิดประเด็น (คู่ข้ามปี)"}


def post_dims(m: dict) -> set:
    """มิติของแถว ร1 ที่จัดใหม่หลังเห็นผล — ``row_source`` = ``transcribed`` · ``post:part,level`` · (``post_result`` เดิม = ทุกมิติ)"""
    src = m.get("row_source") or ""
    if src == "post_result":
        return set(POST_DIMS)
    return {d for d in src[5:].split(",") if d in POST_DIMS} if src.startswith("post:") else set()


def valid_row_source(src: str) -> bool:
    if src == "transcribed":
        return True
    dims = src[5:].split(",") if src.startswith("post:") else []
    return bool(dims) and all(d in POST_DIMS for d in dims) and len(set(dims)) == len(dims)
# ── คู่ข้ามปี: นับเฉพาะความต่างเชิงโครงสร้าง (วิธีวัดผล ข้อ 2.9 ฉบับ 0.2.1–0.2.2 · กิ๊ฟอนุมัติ 27 ต.ค. 2569) ──
#: กติกาแยกข้อเชิงโครงสร้าง — ผูกกับป้ายและชนิดของตัวเทียบรุ่นนี้ (เทสต์ล็อก) · ต้องประกาศพร้อมรุ่นก่อนเปิดผลชุดประเมิน
XYEAR_ENGINE = "pdfbook-0.5.3"
XYEAR_RULE = f"xyear-structural-2 @ {XYEAR_ENGINE}"
#: รุ่นตัวเทียบที่ตรวจแล้วว่ากติกาใช้ได้ — 0.5.1/0.5.2 แก้เฉพาะการหาปีงบและตัวอ่าน (CropBox · pin) · 0.5.3 แก้เฉพาะ scope
#: (สารบัญสองคอลัมน์ · offset · ถอยไปหาจากชื่อหน่วยงาน) — ไม่แตะ compare/profile
#: (ชนิด · หัวข้อ · ป้ายหมวด · subject/column ที่กติกาอ้าง เหมือน 0.5.0 — เทสต์ล็อก) · รุ่นนอกนี้ = ต้องทบทวนทุกข้อ
XYEAR_ENGINES = ("pdfbook-0.5.0", "pdfbook-0.5.1", "pdfbook-0.5.2", XYEAR_ENGINE)
#: รอบที่สร้างก่อนกติกาคู่ข้ามปี (ฉบับ 0.2 ก่อน 0.2.1) — นับตามที่ประกาศตอนนั้น (ไม่กรองเชิงโครงสร้าง)
PRE_XYEAR_PROTOCOLS = ("pdfpair-protocol-0.2 (ร่าง)",)
XYEAR_TOPICS = ("ค", "ช", "ซ", "จ")
XYEAR_SCOPE_LABEL = "เฉพาะความต่างเชิงโครงสร้าง"
KIND_LABELS = cmp.KIND_LABELS
#: ชนิดที่ระบบไม่แน่ใจว่าเป็นรายการเดียวกัน — นับเป็นเชิงโครงสร้าง ผู้ตรวจตัดสิน ส1/ส3 (คำกิ๊ฟ 27 ต.ค.)
_XYEAR_IDENTITY = {cmp.K_LABEL_VARIANT, cmp.K_IDENTITY}
_XYEAR_PRESENCE = {cmp.K_ONLY_A, cmp.K_ONLY_B, cmp.K_RENAMED}
_XYEAR_TEXT_SECTIONS = (prof.SECTION_LABELS[prof.SEC_VISION], prof.SECTION_LABELS[prof.SEC_MISSION])
_XYEAR_AGENCY_SUBJECT = "ชื่อหน่วยงาน (ต้นช่วง)"       # ข้อชื่อหน่วยงานของตัวเทียบ (หัวข้อ format) → ซ
_XYEAR_IND_UNIT_COLUMN = "หน่วยนับ"
_XYEAR_COMMIT_ITEM_COLUMN = "รายการผูกพัน"            # ทั้งรายการผูกพันเพิ่ม/หาย (ไม่ใช่ช่องยอดรายปีว่างฝั่งเดียว)


#: ชนิด/หัวข้อ/ชื่อหมวดข้อความที่กติการู้จัก (pdfbook-0.5.0–0.5.3) — นอกนี้ = ไม่รู้จัก → ต้องทบทวน ไม่ตกเป็นเชิงพรรณนาเงียบ ๆ
_XYEAR_KNOWN_KINDS = frozenset(cmp.KIND_LABELS)
_XYEAR_KNOWN_TOPICS = frozenset(t for t, _l in cmp.TOPICS)
#: รุ่น 2 (กิ๊ฟเลือกทาง ก 29 ต.ค. · #43 6489606410): หมวดย่อยของโครงการ "สถานที่ดำเนินการ"/"ระยะเวลาดำเนินการ" = รู้จักแต่
#: ไม่ใช่เชิงโครงสร้าง (เหมือนวัตถุประสงค์) · ตัวเทียบรุ่นนี้ออกชื่อหมวดเป็นคีย์ ``location``/``period`` (ไม่มีป้ายไทย — เทสต์ล็อก) ·
#: รอบที่บันทึกการจัดประเภทแล้วใช้ค่าที่บันทึก ไม่เปลี่ยนย้อนหลัง
_XYEAR_PROJECT_SUBTEXTS = frozenset({"location", "period"})
_XYEAR_KNOWN_TEXT_SECTIONS = frozenset(prof.SECTION_LABELS.values()) | {"วัตถุประสงค์"} | _XYEAR_PROJECT_SUBTEXTS
_XYEAR_IND_TARGET_PREFIX = "เป้าหมาย"


def classify(f) -> tuple[str, str]:
    """กติกาคู่ข้ามปีต่อข้อสังเกต → (``structural`` | ``out`` | ``unknown``, เหตุ) ·
    ``out`` = รู้จักและไม่ใช่เชิงโครงสร้าง (เชิงพรรณนา) · ``unknown`` = กติกาไม่รู้จัก → ต้องทบทวน (รีวิวโบ 6459664149 ข้อ 1)"""
    k, t = f.kind, f.topic
    if t not in _XYEAR_KNOWN_TOPICS or k not in _XYEAR_KNOWN_KINDS:
        return "unknown", f"ชนิด/หัวข้อที่กติกาไม่รู้จัก ({t}/{k})"
    if t == cmp.T_STRUCT:
        return ("structural", "") if k in _XYEAR_PRESENCE | _XYEAR_IDENTITY | {cmp.K_MOVED} else ("out", "")
    if t == cmp.T_IND:
        if k in _XYEAR_PRESENCE | _XYEAR_IDENTITY:
            return "structural", ""
        if k == cmp.K_CHANGED:
            if f.column == _XYEAR_IND_UNIT_COLUMN:
                return "structural", ""
            if f.column.startswith(_XYEAR_IND_TARGET_PREFIX):
                return "out", ""
            return "unknown", f"ช่องของตัวชี้วัดที่กติกาไม่รู้จัก ({f.column})"
        return "out", ""
    if t == cmp.T_TEXT:
        sec = f.subject.split(" · ")[0]
        if sec not in _XYEAR_KNOWN_TEXT_SECTIONS:
            return "unknown", f"ชื่อหมวดข้อความที่กติกาไม่รู้จัก ({sec[:40]})"
        if sec in _XYEAR_TEXT_SECTIONS and k in _XYEAR_PRESENCE | _XYEAR_IDENTITY | {cmp.K_CHANGED}:
            return "structural", ""
        return "out", ""
    if t == cmp.T_FORMAT:
        return ("structural", "") if k == cmp.K_CHANGED and f.subject == _XYEAR_AGENCY_SUBJECT else ("out", "")
    if t == cmp.T_COMMIT:
        if k in _XYEAR_IDENTITY:
            return "structural", ""
        if k in (cmp.K_ONLY_A, cmp.K_ONLY_B):
            if f.column == _XYEAR_COMMIT_ITEM_COLUMN:
                return "structural", ""
            return ("out", "") if f.column else ("unknown", "รายการผูกพันที่ไม่ระบุช่อง")
        return "out", ""
    return "out", ""


def is_structural(f) -> bool:
    """ข้อสังเกตของคู่ข้ามปีที่นับเป็นความต่างเชิงโครงสร้าง (ค ช ซ จ)"""
    return classify(f)[0] == "structural"


#: ป้ายหัวข้อของคู่ข้ามปี (วิธีวัดผล ข้อ 2.9 ฉบับ 0.2.1) — แทนป้ายเต็มของคู่ปีเดียวกัน
XYEAR_TOPIC_LABELS = {"ค": "แผนงาน ผลผลิต/โครงการ กิจกรรม ที่เพิ่ม หาย เปลี่ยนชื่อ หรือย้ายแผน",
                      "ช": "ตัวชี้วัดและหน่วยนับที่เพิ่ม หาย หรือเปลี่ยนชื่อ (ไม่นับค่าเป้าหมาย)",
                      "ซ": "ชื่อหน่วยงาน วิสัยทัศน์ พันธกิจ ที่เปลี่ยน",
                      "จ": "รายการผูกพันข้ามปีที่เพิ่มหรือหาย (ไม่นับวงเงินและยอดรายปี)"}


#: ชนิดประเด็นของคู่ข้ามปี (รีวิวโบ 6459664149 ข้อ 2) — หัวข้อผ่านอย่างเดียวไม่พอ ต้องบอกว่าเป็นความต่างเชิงโครงสร้างแบบใด
XTYPES = {"add": "เพิ่มทั้งรายการ", "remove": "หายทั้งรายการ", "rename": "เปลี่ยนชื่อ", "move": "ย้ายแผน/สังกัด",
          "unit": "หน่วยนับเปลี่ยน", "text": "ถ้อยคำเปลี่ยน",
          "numeric": "ไม่ใช่เชิงโครงสร้าง — ค่า/วงเงิน/เป้าหมาย (ไม่นับในตัวหาร)"}
XTYPE_BY_TOPIC = {"ค": ("add", "remove", "rename", "move", "numeric"),
                  "ช": ("add", "remove", "rename", "unit", "numeric"),
                  "ซ": ("text", "add", "remove", "numeric"),
                  "จ": ("add", "remove", "numeric")}


def xtype_gap(m: dict, kind: str) -> list[str]:
    """คู่ข้ามปี: ต้องระบุชนิดประเด็นที่ใช้ได้กับหัวข้อ"""
    if kind != "cross_year":
        return []
    return [] if m.get("xtype") in XTYPE_BY_TOPIC.get(m.get("topic") or "", ()) else ["ชนิดประเด็น (คู่ข้ามปี)"]


def topic_codes(kind: str) -> tuple:
    """หัวข้อที่ใช้กับชนิดคู่ — คู่ข้ามปี = ค ช ซ จ เท่านั้น (ป้ายตามขอบเขตเชิงโครงสร้าง)"""
    if kind == "cross_year":
        return tuple((c, XYEAR_TOPIC_LABELS[c]) for c, _l in TOPIC_CODES if c in XYEAR_TOPICS)
    return TOPIC_CODES


def system_topic(f, kind: str = "same_year") -> str:
    """รหัสหัวข้อของข้อสังเกต · คู่ข้ามปี: ชื่อหน่วยงาน (ตัวเทียบจัดไว้ ฌ) → ซ"""
    if kind == "cross_year" and f.topic == cmp.T_FORMAT and f.subject == _XYEAR_AGENCY_SUBJECT:
        return "ซ"
    return SYSTEM_TOPIC_CODE.get(f.topic, "")


#: หัวข้อของตัวเทียบ → รหัสหัวข้อของวิธีวัดผล — ใช้เรียงข้อเสนอและแสดงเท่านั้น ไม่ใช้นับ
SYSTEM_TOPIC_CODE = {cmp.T_TOTAL: "ก", cmp.T_ECON: "ข", cmp.T_STRUCT: "ค", cmp.T_ITEMS: "ง", cmp.T_COMMIT: "จ",
                     cmp.T_MTEF: "ฉ", cmp.T_IND: "ช", cmp.T_TEXT: "ซ", cmp.T_FORMAT: "ฌ", cmp.T_CONSIST: "ญ"}

# ── แบบสอบถามหลังใช้ผล = แบบ 03 ฉบับ 0.2 (ถ้อยคำตามแบบ Word) ─────────────────────────
CONSENT_ITEMS = (("c1", "อ่านคำชี้แจงแล้ว"), ("c2", "ยินยอมตอบโดยสมัครใจ"), ("c3", "ทราบว่าถอนตัวได้ด้วยรหัสผู้ตอบ"))
STEPS = (("k1", "ข๑ เปิดคู่เอกสารและผลของระบบ"), ("k2", "ข๒ หาภาพหลักฐานของข้อสังเกตในฉบับทั้งสอง"),
         ("k3", "ข๓ จับคู่ประเด็นในรายการของท่านกับข้อสังเกตของระบบ"), ("k4", "ข๔ ตัดสินข้อสังเกตที่ไม่อยู่ในรายการของท่าน"),
         ("k5", "ข๕ แยกข้อที่ระบบอ่านไม่ได้ออกจากข้อที่ระบบไม่พบ"), ("k6", "ข๖ กรอกและส่งใบสรุปจำนวน"))
STEP_CHOICES = {"self": "ทำได้เอง", "helped": "ทำได้เมื่อมีคนช่วย", "cannot": "ทำไม่ได้", "skipped": "ไม่ได้ทำ"}
#: 1–5 = ไม่เห็นด้วยอย่างยิ่ง … เห็นด้วยอย่างยิ่ง · ข้อเชิงลบรายงานตามถ้อยคำเดิม (ไม่กลับคะแนน)
LIKERT_ITEMS = (
    ("ประโยชน์", (("q2_1", "๒.๑ รายการข้อสังเกตช่วยให้ฉันเห็นจุดที่ต่างซึ่งอาจพลาดเมื่อตรวจด้วยตา"),
                  ("q2_2", "๒.๒ ระบบยกสิ่งที่ไม่ใช่ความต่างจริงขึ้นมามากจนรบกวน"),
                  ("q2_3", "๒.๓ การแยกหัวข้อของข้อสังเกตตรงกับวิธีที่ฉันตรวจเล่ม"))),
    ("ความเข้าใจหลักฐาน", (("q2_4", "๒.๔ ภาพหน้าเอกสารทั้งสองฉบับพร้อมกรอบเน้น ทำให้ฉันยืนยันได้ว่าความต่างมีจริง"),
                           ("q2_5", "๒.๕ ฉันยังต้องเปิดเล่มเองเกือบทุกข้อ เพราะหลักฐานในระบบไม่พอ"),
                           ("q2_6", "๒.๖ ฉันแยกได้ว่าข้อใด \"ระบบไม่พบ\" และข้อใด \"ระบบอ่านไม่ได้\""),
                           ("q2_7", "๒.๗ ฉันเข้าใจว่าข้อสังเกตของระบบเป็นจุดที่ต่าง ไม่ใช่คำตัดสินว่าผิด"))),
    ("ภาระงาน", (("q2_8", "๒.๘ การนำไฟล์เข้าและอ่านผลเพิ่มภาระมากกว่าที่ช่วยลด"),
                 ("q2_9", "๒.๙ จำนวนข้อสังเกตที่ต้องตัดสินอยู่ในระดับที่ทำได้จริง"))),
    ("การพึ่งพาระบบ", (("q2_10", "๒.๑๐ มีบางข้อที่ฉันยอมรับผลของระบบโดยไม่ได้เปิดดูหลักฐาน"),
                       ("q2_11", "๒.๑๑ หากระบบไม่ได้ยกจุดใดขึ้นมา ฉันยังเห็นว่าต้องตรวจจุดนั้นด้วยตนเอง"))),
    ("ความต้องการใช้ต่อ", (("q2_12", "๒.๑๒ หากมีระบบนี้ ฉันจะใช้ประกอบการตรวจเล่มของตนเองหรือของผู้อื่น"),
                           ("q2_13", "๒.๑๓ ระบบนี้น่าจะเป็นประโยชน์ต่อผู้ปฏิบัติงานในตำแหน่งเดียวกับฉัน"))),
)
#: แบบ 03 ฉบับ 0.3 ร่าง ๒ ส่วนที่ ๒ = ข้อคำถามชุดเดียวกับแบบ 08 (เชิงบวกทุกข้อ · 5 ด้าน · ๕ มากที่สุด … ๑ น้อยที่สุด)
LIKERT_ITEMS_V03 = (
    ("ด้านประโยชน์ของรายการจุดต่าง", (
        ("q2_1", "๒.๑ รายการข้อสังเกตช่วยให้เห็นจุดที่ต่างซึ่งอาจพลาดเมื่อตรวจด้วยตา"),
        ("q2_2", "๒.๒ ข้อสังเกตที่ระบบแสดงส่วนใหญ่เป็นความต่างจริง ไม่รบกวนการตรวจ"),
        ("q2_3", "๒.๓ การแยกหัวข้อของข้อสังเกตสอดคล้องกับวิธีการตรวจเล่มในการปฏิบัติงาน"))),
    ("ด้านความเข้าใจหลักฐาน", (
        ("q2_4", "๒.๔ ภาพหน้าเอกสารทั้งสองฉบับพร้อมกรอบเน้น ช่วยยืนยันได้ว่าความต่างมีอยู่จริง"),
        ("q2_5", "๒.๕ หลักฐานในระบบเพียงพอต่อการวินิจฉัยโดยไม่ต้องเปิดเล่มเอกสารเอง"),
        ("q2_6", "๒.๖ แยกได้ชัดเจนว่าข้อใดระบบไม่พบ และข้อใดระบบอ่านไม่ได้"),
        ("q2_7", "๒.๗ เข้าใจได้ว่าข้อสังเกตของระบบเป็นจุดที่ต่าง ไม่ใช่คำตัดสินว่าเอกสารผิด"))),
    ("ด้านภาระงาน", (
        ("q2_8", "๒.๘ การนำไฟล์เข้าและการอ่านผลทำได้ง่าย ไม่เพิ่มภาระงาน"),
        ("q2_9", "๒.๙ จำนวนข้อสังเกตที่ต้องวินิจฉัยอยู่ในระดับที่ทำได้จริง"))),
    ("ด้านการใช้ระบบอย่างรอบคอบ", (
        ("q2_10", "๒.๑๐ เปิดดูหลักฐานก่อนยอมรับผลของระบบทุกครั้ง"),
        ("q2_11", "๒.๑๑ จุดที่ระบบไม่ได้แสดงขึ้นมา ยังเห็นว่าต้องตรวจด้วยตนเอง"))),
    ("ด้านความเหมาะสมต่อการนำไปใช้", (
        ("q2_12", "๒.๑๒ จะใช้ระบบนี้ประกอบการตรวจเล่มเอกสารงบประมาณในการปฏิบัติงาน"),
        ("q2_13", "๒.๑๓ ระบบนี้เหมาะสมต่อการใช้งานของผู้ปฏิบัติงานในตำแหน่งเดียวกัน"))),
)
LIKERT_SCALE_V03 = {"5": "มากที่สุด", "4": "มาก", "3": "ปานกลาง", "2": "น้อย", "1": "น้อยที่สุด"}


def likert_items(s) -> tuple:
    """ข้อคำถามส่วนที่ ๒ ตามรุ่นวิธีวัดผลของรอบ (0.3 = แบบ 08 · 0.2 = แบบ 03 ฉบับ 0.2)"""
    return LIKERT_ITEMS_V03 if s.v03 else LIKERT_ITEMS


OPEN_ITEMS = (("o3_1", "๓.๑ ขั้นตอนใดยาก หรืออยากให้ปรับอะไร"),
              ("o3_2", "๓.๒ ประเด็นที่ระบบพลาดและท่านเห็นว่าสำคัญที่สุด (ลักษณะทั่วไป ไม่ต้องระบุตัวเลขจริง)"),
              ("o3_3", "๓.๓ สิ่งที่ระบบอาจทำให้ผู้ใช้สรุปผิด หรือควรระวัง"),
              ("o3_4", "๓.๔ ข้อเสนอแนะอื่น"))
GENERAL_ITEMS = (("g4_1", "ประสบการณ์ตรวจเล่มเอกสารงบประมาณ",
                  {"lt3": "น้อยกว่า ๓ ปี", "3to10": "๓–๑๐ ปี", "gt10": "มากกว่า ๑๐ ปี"}),
                 ("g4_2", "เคยใช้คำสั่งเทียบเอกสารของโปรแกรมสำนักงานมาก่อน", {"no": "ไม่เคย", "yes": "เคย"}))
#: ข้อของรอบกติกา 0.1 (แสดงคำตอบเดิมแบบอ่านอย่างเดียว)
LEGACY_LINK_VERDICTS = {"exact": "พบตรง", "partial": "พบบางส่วน", "not_same": "ระบบไม่ได้ยกจุดนี้"}
LEGACY_EXTRA_VERDICTS = {"real_unnoted": "ต่างจริง แต่ไม่ได้วง", "not_diff": "ไม่ใช่ความต่าง", "undecided": "ยังตัดสินไม่ได้"}
#: ระยะที่ยอมให้จุดที่วงห่างจากกรอบของข้อสังเกต (pt) — ใช้เสนอคู่เท่านั้น คนยืนยันเสมอ
MATCH_X_PT, MATCH_Y_PT = 40.0, 14.0
MAX_ROWS_PER_TOPIC, MAX_ROWS = 500, 2000


class TrialError(ValueError):
    pass


class LedgerError(TrialError):
    """บัญชีข้อสังเกตต้องตรวจไม่ปิดเพราะข้อมูลไม่สอดคล้อง (ไม่ใช่เพราะยังจัดไม่ครบ) — ห้ามรายงาน ต้องหาต้นเหตุก่อน"""


@dataclass(frozen=True)
class TrialBook:
    id: str
    title: str
    agency: str
    pair: str               # ป้ายคู่ เช่น "ร่าง พ.ร.บ. ↔ พ.ร.บ."
    current: str            # รหัสเล่มบนชั้น (ฉบับ B / ฉบับปีนี้)
    previous: str           # รหัสเล่มบนชั้น (ฉบับ A / ฉบับปีก่อน)
    pair_kind: str = "same_year"     # same_year · cross_year (จากปีงบของสองเล่มบนชั้น)


def books_file() -> Path:
    return Path(os.environ.get(TRIAL_ENV) or (pdfshelf.shelf_dir() / "trial_books.json"))


def books() -> list[TrialBook]:
    """เล่มทดสอบที่ใช้ได้ (ไฟล์ตั้งค่าของเครื่องนี้) — เล่มที่ไม่อยู่บนชั้น/หน่วยงานที่กันไว้ = ไม่แสดง"""
    try:
        raw = json.loads(books_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    have = {v.key: v for v in pdfshelf.volumes()}
    out = []
    for b in raw.get("books", []):
        cur, prev = str(b.get("current", "")), str(b.get("previous", ""))
        if not (b.get("id") and b.get("agency") and cur in have and prev in have) \
                or pdfshelf.is_protected(str(b.get("agency", ""))):
            continue
        kind = "same_year" if have[cur].fiscal_year == have[prev].fiscal_year else "cross_year"
        out.append(TrialBook(str(b["id"]), str(b.get("title", "")), str(b["agency"]), str(b.get("pair", "")),
                             cur, prev, kind))
    return out


def get_book(book_id: str) -> TrialBook | None:
    return next((b for b in books() if b.id == book_id), None)


def pair_kind(book: dict) -> str:
    if book.get("pair_kind") in ("same_year", "cross_year"):
        return book["pair_kind"]
    return "same_year" if book["cur"].get("fiscal_year") == book["prev"].get("fiscal_year") else "cross_year"


def side_labels(book: dict) -> dict:
    """ชื่อฉบับตามชนิดคู่ (วิธีวัดผล ข้อ 2.1) — ปีเดียวกัน = ฉบับ A/B · ข้ามปี = ฉบับปีก่อน/ปีนี้"""
    if pair_kind(book) == "cross_year":
        return {"prev": "ฉบับปีก่อน", "cur": "ฉบับปีนี้"}
    return {"prev": "ฉบับ A", "cur": "ฉบับ B"}


PAIR_KIND_LABELS = {"same_year": "ปีเดียวกัน (ฉบับ A = ประกอบร่าง พ.ร.บ. · ฉบับ B = ตาม พ.ร.บ.)",
                    "cross_year": "ข้ามปี (ฉบับปีก่อน · ฉบับปีนี้)"}


def _work(s: dict) -> int:
    return len(trial_repo.marks(s["id"])) + len(trial_repo.pages_done(s["id"]))


def _rank(s: dict) -> tuple:
    """รอบที่ควรพากลับไป: กำลังทำและมีงานแล้ว > ส่งผลแล้ว > รอบว่าง > หยุด/ถอนตัว · เท่ากัน = ใหม่กว่า"""
    if s.get("status") or not s.get("protocol"):          # หยุด/ถอนตัว หรือรอบกติกา 0.1 (อ่านอย่างเดียว)
        level = -1
    else:
        level = 1 if s["locked_at"] else (2 if _work(s) else 0)
    return (level, s["started_at"])


def current_session(book_id: str, reviewer: str = "") -> dict | None:
    """รอบของเล่มนี้ที่ควรพากลับไป — ระบุรหัสผู้ตรวจแล้ว ไม่พาไปรอบของรหัสอื่น (รอบที่ไม่ได้ใส่รหัสใช้ร่วมได้)"""
    who = (reviewer or "").strip()
    ss = [s for s in trial_repo.sessions() if s["book_id"] == book_id
          and (not who or not s["reviewer"] or s["reviewer"] == who)]
    return max(ss, key=_rank) if ss else None


def _state(s: dict) -> str:
    return s["status"] or ("locked" if s["locked_at"] else "draft")


def book_status() -> dict:
    """book_id → รอบที่ควรพากลับไป (``draft`` · ``locked`` · ``stopped`` · ``withdrawn``) — รอบว่างที่เปิดทีหลังไม่บังงานเดิม"""
    out: dict = {}
    for bid in {s["book_id"] for s in trial_repo.sessions()}:
        s = current_session(bid)
        out[bid] = {"sid": s["id"], "state": "legacy" if not s["protocol"] else _state(s), "legacy": not s["protocol"]}
    return out


def _released(s: dict) -> bool:
    return bool(s.get("released_at") or (not s.get("protocol") and s.get("locked_at") and s.get("run_id")))


# ── เริ่มตรวจ ──────────────────────────────────────────────────────────────────
def start(book_id: str, reviewer: str = "", again: bool = False, path: str = "r1") -> str:
    """เริ่มตรวจ — ถ้าเล่มนี้มีรอบที่ทำอยู่แล้ว **พากลับไปรอบเดิม** (ไม่สร้างรอบว่างทับงานเดิม) ·
    ``again=True`` = ผู้ตรวจขอเริ่มรอบใหม่เอง (รอบเดิมยังเก็บไว้) · รอบใหม่ของเล่มที่เคยเปิดผลระบบบนเครื่องนี้แล้ว
    ถูกบันทึกไว้ (``prior_release``) ให้รายงาน"""
    b = get_book(book_id)
    if b is None:
        raise TrialError("ไม่พบเล่มทดสอบที่เลือก")
    if path not in PATHS:
        raise TrialError("เลือกทางทำรายการอ้างอิง (ร1 หรือ ร2)")
    if not again:
        cur = current_session(book_id, reviewer)
        if cur is not None and not cur["status"] and cur["protocol"]:
            return cur["id"]
    sides = {}
    for side, key in (("cur", b.current), ("prev", b.previous)):
        v = pdfshelf.get(key)
        sc, _read = pdfshelf.toc_scope(v, b.agency)
        sides[side] = {"key": key, "title": v.title, "fiscal_year": v.fiscal_year, "stage": v.stage,
                       "sha256": v.sha256, "first": sc.first, "last": sc.last}
    rec = {"id": b.id, "title": b.title, "agency": b.agency, "pair": b.pair, "pair_kind": b.pair_kind, **sides}
    prior = ",".join(s["id"] for s in trial_repo.sessions() if s["book_id"] == book_id and _released(s))
    sid = trial_repo.create_session(b.id, (reviewer or "").strip(), rec, path=path, protocol=PROTOCOL_VERSION,
                                    trial_version=TRIAL_VERSION, prior_release=prior)
    warm(rec)
    return sid


def warm(book: dict, background: bool = True) -> None:
    """อ่านข้อเท็จจริงของสองเล่มเตรียมไว้ระหว่างที่ผู้ตรวจทำรายการ — **ไม่เทียบ ไม่มีข้อสังเกต** (ยังไม่มีผลระบบก่อนล็อก)
    พอส่งใบประกาศ เหลือแค่เทียบ (เสี้ยววินาที) · ใช้ค่าเดียวกับ :func:`pdfshelf.start` จึงตรงกับที่จำไว้"""
    from ..pdfbook import scope as scope_mod

    def job():
        for side in ("prev", "cur"):
            sd = book[side]
            v = pdfshelf.get(sd["key"])
            if v is None:
                continue
            try:
                pdfpair._facts(v.path, book["agency"], str(sd["first"]), str(sd["last"]), scope_mod.METHOD_TOC)
            except (pdfpair.PairError, OSError, ValueError, reader.ReaderUnavailable):
                continue
    if background:
        threading.Thread(target=job, daemon=True).start()
    else:
        job()


@dataclass
class Session:
    rec: dict
    marks: list              # ประเด็นทั้งหมดที่ไม่ถูกลบ (จุดที่วง + แถวของ ร1)
    done: set

    @property
    def sid(self) -> str:
        return self.rec["id"]

    @property
    def book(self) -> dict:
        return self.rec["book"]

    @property
    def locked(self) -> bool:
        return bool(self.rec["locked_at"])

    @property
    def legacy(self) -> bool:
        """รอบที่เริ่มก่อนวิธีวัดผลฉบับ 0.2 (รอบกติกา 0.1)"""
        return not self.rec.get("protocol")

    @property
    def read_only_legacy(self) -> bool:
        """รอบกติกา 0.1 — อ่าน/นับตามรุ่นเดิมเท่านั้น (ส่งแล้วหรือยังไม่ส่ง) · ไม่เปลี่ยนรุ่นอัตโนมัติ"""
        return self.legacy

    @property
    def consented(self) -> bool:
        return bool(self.rec.get("consent_at"))

    @property
    def protocol(self) -> str:
        """รุ่นวิธีวัดผลที่**บันทึกไว้กับรอบ** (รอบเดิมคงรุ่นของตัวเอง — รีวิวโบ 6460469359)"""
        return LEGACY_PROTOCOL if self.read_only_legacy else (self.rec.get("protocol") or PROTOCOL_VERSION)

    @property
    def xrule_applies(self) -> bool:
        """กติกาคู่ข้ามปีเชิงโครงสร้างใช้กับรอบนี้ (รอบที่สร้างก่อน 0.2.1 นับตามที่ประกาศตอนนั้น)"""
        return self.protocol not in PRE_XYEAR_PROTOCOLS

    @property
    def v03(self) -> bool:
        """รอบตามวิธีวัดผลฉบับ 0.3 (ตำแหน่งแยกขั้น · A3-อ/A3-ข · H1 = พบตรง ÷ N₀ · แบบสอบถาม 0.3)"""
        return self.protocol.startswith("pdfpair-protocol-0.3")

    @property
    def xkind(self) -> str:
        """ชนิดคู่สำหรับกติกาหัวข้อ/ชนิดประเด็น — รอบก่อน 0.2.1 ใช้หัวข้อครบ ก–ญ ตามที่ประกาศตอนนั้น"""
        return self.pair_kind if self.xrule_applies else "same_year"

    @property
    def path(self) -> str:
        return self.rec.get("path") or ("r2" if self.legacy else "r1")

    @property
    def status(self) -> str:
        return self.rec.get("status") or ""

    @property
    def active(self) -> bool:
        return not self.status

    @property
    def labels(self) -> dict:
        return side_labels(self.book)

    @property
    def pair_kind(self) -> str:
        return pair_kind(self.book)

    @property
    def circles(self) -> list:
        return [m for m in self.marks if (m.get("origin") or "mark") == "mark"]

    @property
    def rows(self) -> list:
        return [m for m in self.marks if m.get("origin") == "row"]

    def pages(self, side: str) -> list[int]:
        s = self.book[side]
        return list(range(int(s["first"]), int(s["last"]) + 1))

    def pending_pages(self, side: str = "cur") -> list[int]:
        return [p for p in self.pages(side) if (side, p) not in self.done]

    def done_pages(self, side: str) -> list[int]:
        return sorted(p for sd, p in self.done if sd == side)

    def counts(self) -> dict:
        c = {k: 0 for k in PENS}
        for m in self.circles:
            c[m["pen"]] = c.get(m["pen"], 0) + 1
        return c


def session(sid: str) -> Session | None:
    r = trial_repo.get_session(sid)
    if r is None:
        return None
    return Session(r, trial_repo.marks(sid), trial_repo.pages_done(sid))


LEGACY_READ_ONLY = "รอบกติกา 0.1 อ่าน/นับตามรุ่นเดิมเท่านั้น — งานตามฉบับ 0.2 ให้เริ่มรอบใหม่จากหน้าเลือกเล่ม"
NEED_CONSENT = "ติ๊กคำชี้แจงและความยินยอมครบ 3 ข้อก่อนเริ่มทำรายการ"


def _need(sid: str, unlocked: bool = True, active: bool = True, consent: bool = True) -> Session:
    """รอบตรวจ — ``active`` = จะบันทึก: ต้องไม่ใช่รอบกติกา 0.1 · ไม่หยุด/ถอนตัว · ให้ความยินยอมแล้ว (``consent``)"""
    s = session(sid)
    if s is None:
        raise TrialError("ไม่พบรอบตรวจ")
    if active and s.legacy:
        raise TrialError(LEGACY_READ_ONLY)
    if active and consent and s.active and not s.consented:
        raise TrialError(NEED_CONSENT)
    if active and not s.active:
        raise TrialError("รอบนี้หยุดหรือถอนตัวแล้ว — บันทึกเพิ่มไม่ได้ (ข้อมูลเดิมเก็บไว้ตามเดิม)")
    if unlocked and s.locked:
        raise TrialError("ส่งใบประกาศแล้ว — แก้รายการที่ล็อกไม่ได้ (ข้อมูลเดิมเก็บไว้ตามเดิม)")
    return s


def _repo(fn, *args, **kw):
    """เรียกชั้นที่เก็บ — ข้อผิดพลาดจากการตรวจซ้ำในธุรกรรม (ValueError) = ข้อความที่ผู้ใช้อ่านได้"""
    try:
        return fn(*args, **kw)
    except TrialError:
        raise
    except ValueError as e:
        raise TrialError(str(e))


def _side_path(s: Session, side: str) -> Path:
    if side not in ("cur", "prev"):
        raise TrialError("ฉบับไม่ถูกต้อง")
    v = pdfshelf.get(s.book[side]["key"])
    if v is None:
        raise TrialError("ไม่พบเล่มบนชั้นเล่มของเครื่องนี้")
    pdfshelf.verify(v)
    if v.sha256 != s.book[side]["sha256"]:
        raise TrialError("เล่มบนชั้นไม่ใช่ไฟล์เดียวกับตอนเริ่มตรวจ (SHA-256 ต่างกัน)")
    return v.path


def page_png(sid: str, side: str, page: int) -> bytes | None:
    """ภาพทั้งหน้า — เปิดได้เฉพาะหน้าของหน่วยงานในเล่มนั้น (ไม่เปิดหน้าของหน่วยงานอื่น)"""
    s = _need(sid, unlocked=False, active=False)
    if side not in ("cur", "prev") or page not in s.pages(side):
        return None
    path = _side_path(s, side)
    return pdfpair._png_cached((s.book[side]["sha256"], page, None, True, PAGE_ZOOM),
                               lambda: reader.render_png(path, page, zoom=PAGE_ZOOM))


def set_path(sid: str, path: str) -> None:
    """เปลี่ยนทางทำรายการอ้างอิงก่อนล็อก — ไปทาง ร1 ได้เมื่อไม่มีจุดที่วงค้าง"""
    _need(sid)
    if path not in PATHS:
        raise TrialError("เลือกทางทำรายการอ้างอิง (ร1 หรือ ร2)")
    _repo(trial_repo.set_path, sid, path)


def give_consent(sid: str, form: dict) -> None:
    """ความยินยอม (แบบ 03 หน้าแรก · ติ๊ก ไม่ลงชื่อ) — **ก่อนเริ่มทำรายการหรือเก็บข้อมูลใด ๆ** ในรอบนี้
    (รีวิวโบ 6414605109 ข้อ 4) · ถอนตัวได้ทุกเมื่อ"""
    _need(sid, unlocked=False, consent=False)
    if not all(str(form.get(k, "") or "").strip() in ("1", "true", "True", "on") for k, _t in CONSENT_ITEMS):
        raise TrialError(NEED_CONSENT)
    _repo(trial_repo.give_consent, sid)


# ── จุดที่วง (ร2) · แถวของรายการเดิม (ร1) ─────────────────────────────────────────
def add_mark(sid: str, side: str, page, fx, fy, pen: str) -> dict:
    s = _need(sid)
    if s.path != "r2":
        raise TrialError("ทาง ร1 ไม่ใช้การวงจุดบนภาพ — เปลี่ยนเป็นทาง ร2 ก่อนถ้าจะวง")
    if pen not in PENS:
        raise TrialError("เลือกปากกาก่อน")
    try:
        page, fx, fy = int(page), float(fx), float(fy)
    except (TypeError, ValueError):
        raise TrialError("ตำแหน่งไม่ถูกต้อง")
    if side not in ("cur", "prev") or page not in s.pages(side) or not (0 <= fx <= 1 and 0 <= fy <= 1):
        raise TrialError("ตำแหน่งอยู่นอกหน้าของหน่วยงาน")
    return _repo(trial_repo.add_mark, sid, side, page, round(fx, 5), round(fy, 5), pen,
                 level=pen if pen in LEVELS else "")


def _check_fields(*, topic=None, part=None, cause=None, level=None, pen=None, found_in=None,
                  kind: str = "same_year") -> None:
    if topic and topic not in dict(topic_codes(kind)):
        raise TrialError("หัวข้อไม่ถูกต้อง" if topic not in TOPIC_LABELS
                         else f"คู่ข้ามปีนับเฉพาะความต่างเชิงโครงสร้าง — ใช้หัวข้อ {' '.join(XYEAR_TOPICS)} เท่านั้น")
    if part and part not in PART_LABELS:
        raise TrialError("ส่วนของเล่มไม่ถูกต้อง")
    if cause and cause not in CAUSES:
        raise TrialError("ต/ล ไม่ถูกต้อง")
    if level and level not in LEVELS:
        raise TrialError("ระดับไม่ถูกต้อง")
    if pen is not None and pen not in PENS:
        raise TrialError("ปากกาไม่ถูกต้อง")
    if found_in and found_in not in ("cur", "prev"):
        raise TrialError("ฉบับที่พบไม่ถูกต้อง")


def _xtype_value(s, topic: str, xtype, current: str):
    """ค่าชนิดประเด็นที่จะบันทึก (None = ไม่แก้) · คู่ข้ามปีเท่านั้น · ต้องใช้ได้กับหัวข้อ ·
    เปลี่ยนหัวข้อจนชนิดเดิมใช้ไม่ได้ = ล้างชนิด"""
    allowed = XTYPE_BY_TOPIC.get(topic, ())
    if xtype is None:
        return "" if current and current not in allowed else None
    xt = str(xtype).strip()
    if xt and s.xkind != "cross_year":
        raise TrialError("ชนิดประเด็นใช้กับคู่ข้ามปีเท่านั้น")
    if xt and xt not in allowed:
        raise TrialError(f"ชนิดประเด็นนี้ใช้กับหัวข้อ {topic or '—'} ไม่ได้")
    return xt


def _clean(v, n: int = 200):
    return None if v is None else str(v).strip()[:n]


def update_mark(sid: str, mid: str, *, topic=None, note=None, pen=None, level=None, cause=None, part=None,
                searched=None, delete: bool = False, xtype=None) -> None:
    """แก้จุดที่วง (ร2) ก่อนล็อก — ปากกาแดง/น้ำตาล = ระดับตามปากกา · หมุด = ต้องเลือกระดับเอง + ขอบเขตที่ค้นในอีกฉบับ"""
    s = _need(sid)
    m = next((x for x in s.circles if x["id"] == mid), None)
    if m is None:
        raise TrialError("ไม่พบจุดที่ระบุ")
    _check_fields(topic=topic, part=part, cause=cause, level=level, pen=pen, kind=s.xkind)
    fields = {"topic": _clean(topic, 4), "note": _clean(note), "part": _clean(part, 4), "cause": _clean(cause, 4),
              "searched": _clean(searched), "deleted": 1 if delete else None,
              "xtype": _xtype_value(s, topic or m.get("topic") or "", xtype, m.get("xtype") or "")}
    if pen is not None:
        fields["pen"] = pen
        fields["found_in"] = m["side"] if pen == "pin" else ""
        if pen in LEVELS:
            fields["level"] = pen
    if level is not None and (pen or m["pen"]) == "pin":
        fields["level"] = level
    _repo(trial_repo.update_mark, sid, mid, **fields)


def update_row(sid: str, mid: str, *, part=None, cause=None, level=None, found_in=None, searched=None, side=None,
               page=None, ref=None, note=None, row_source=None, xtype=None) -> None:
    """ลักษณะของแถวในรายการเดิม (ร1) — กรอกหลังล็อก · ต้องอ้าง "ข้อที่" ในรายการที่ล็อกไว้ (``ref``) และบอกที่มา
    (``row_source``): ถอดจากรายการที่ล็อก หรือ **จัดประเภทใหม่หลังเห็นผล** (ติดป้าย · รายงานแยก — รีวิวโบ 6414605109 ข้อ 2) ·
    หัวข้อแก้ไม่ได้ (มาจากใบประกาศ) · ทุกการแก้ลง Audit (ค่าก่อน/หลัง)"""
    s = _need(sid, unlocked=False)
    if not s.locked or s.read_only_legacy:
        raise TrialError("แถวของรายการเดิมมีหลังส่งใบประกาศเท่านั้น")
    m = next((x for x in s.rows if x["id"] == mid), None)
    if m is None:
        raise TrialError("ไม่พบแถวที่ระบุ")
    _check_fields(part=part, cause=cause, level=level, found_in=found_in)
    xt = _xtype_value(s, m.get("topic") or "", xtype, m.get("xtype") or "")
    if row_source and not valid_row_source(row_source):
        raise TrialError("ที่มาของลักษณะแถวไม่ถูกต้อง")
    if side and side not in ("cur", "prev"):
        raise TrialError("ฉบับไม่ถูกต้อง")
    pg = None
    if page is not None and str(page).strip() != "":
        try:
            pg = int(page)
        except (TypeError, ValueError):
            raise TrialError("เลขหน้าไม่ถูกต้อง")
        if pg and (side or m["side"]) and pg not in s.pages(side or m["side"]):
            raise TrialError("หน้านี้อยู่นอกช่วงหน้าของหน่วยงาน")
    elif page is not None:
        pg = 0
    _repo(trial_repo.update_mark, sid, mid, after_lock=True, part=_clean(part, 4), cause=_clean(cause, 4),
          level=_clean(level, 8), found_in=_clean(found_in, 8), searched=_clean(searched), side=_clean(side, 8),
          page=pg, ref=_clean(ref, 40), note=_clean(note), row_source=_clean(row_source, 40), xtype=xt)


def page_done(sid: str, side: str, page) -> None:
    """ตัวช่วยของผู้ตรวจ: "ตรวจหน้านี้แล้ว" = ดูหน้านี้ครบ (ไม่ใช่ "ถูกต้อง") — ไม่ใช่เงื่อนไขการล็อกตั้งแต่ฉบับ 0.2"""
    s = _need(sid)
    try:
        page = int(page)
    except (TypeError, ValueError):
        raise TrialError("หน้าไม่ถูกต้อง")
    if side not in ("cur", "prev") or page not in s.pages(side):
        raise TrialError("หน้าไม่ถูกต้อง")
    _repo(trial_repo.page_done, sid, side, page)


def page_undone(sid: str, side: str, page) -> bool:
    """ยกเลิก "ตรวจหน้านี้แล้ว" (กดพลาด) — ก่อนส่งเท่านั้น · คืน True เมื่อยกเลิกจริง (ยังไม่เคยกด = False ไม่ error)"""
    s = _need(sid)
    try:
        page = int(page)
    except (TypeError, ValueError):
        raise TrialError("หน้าไม่ถูกต้อง")
    if side not in ("cur", "prev") or page not in s.pages(side):
        raise TrialError("หน้าไม่ถูกต้อง")
    return _repo(trial_repo.page_undone, sid, side, page)


def log_view(sid: str, cur_page, prev_page=0) -> None:
    """บันทึกคู่หน้าที่ผู้ตรวจเปิดเทียบ (ระหว่างทำรายการเท่านั้น · หลังส่ง/หยุด ไม่บันทึก)"""
    s = _need(sid, unlocked=False, active=False)
    if s.locked or not s.active or s.legacy:
        return
    try:
        cur_page, prev_page = int(cur_page), int(prev_page or 0)
    except (TypeError, ValueError):
        raise TrialError("หน้าไม่ถูกต้อง")
    if cur_page not in s.pages("cur") or (prev_page and prev_page not in s.pages("prev")):
        raise TrialError("หน้าไม่ถูกต้อง")
    trial_repo.log_view(sid, cur_page, prev_page)


# ── ใบประกาศก่อนเห็นผล = ล็อก ────────────────────────────────────────────────────
def mark_gaps(m: dict, kind: str = "same_year") -> list[str]:
    """ฟิลด์ที่จุดที่วง (ร2) ยังขาดก่อนล็อก — ทุกจุดต้องมีหัวข้อ ส่วนของเล่ม ต/ล ระดับ · หมุดต้องมีขอบเขตที่ค้นในอีกฉบับ ·
    คู่ข้ามปีต้องมีชนิดประเด็น"""
    out = []
    if not m.get("topic"):
        out.append("หัวข้อ")
    if not m.get("part"):
        out.append("ส่วนของเล่ม")
    if not m.get("cause"):
        out.append("ต/ล")
    if m.get("level") not in LEVELS:
        out.append("ระดับ")
    if m.get("pen") == "pin" and not (m.get("searched") or "").strip():
        out.append("ขอบเขตที่ค้นในอีกฉบับ")
    return out + xtype_gap(m, kind)


def declaration_defaults(s: Session) -> dict:
    lab = s.labels
    return {"made_on": dt.date.today().isoformat(), "source": "web" if s.path == "r2" else "routine",
            "edition_first": f"{lab['prev']} · {s.book['prev']['title']}",
            "edition_second": f"{lab['cur']} · {s.book['cur']['title']}",
            "topics_marked": sorted({m["topic"] for m in s.circles if m.get("topic")}) if s.path == "r2" else []}


def _count(v, label: str) -> int | None:
    v = str(v if v is not None else "").strip()
    if v == "":
        return None
    if not re.fullmatch(r"\d{1,4}", v):
        raise TrialError(f"{label} ต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป")
    return int(v)


def _validate_declaration(s: Session, form: dict) -> tuple[dict, list, str | None]:
    """ตรวจใบประกาศ (แบบ 02 ส่วนที่ ๑) → (ใบประกาศ, แถวที่ต้องสร้าง (ร1), แฮชชุดจุดที่ต้องยังเหมือนเดิม (ร2))"""
    g = lambda k: str(form.get(k, "") or "").strip()       # noqa: E731
    if g("confirm") not in ("1", "true", "True", "on"):
        raise TrialError("ติ๊กยืนยันก่อนส่ง — ส่งแล้วแก้รายการและใบประกาศไม่ได้")
    made_on = g("made_on")
    try:
        dt.date.fromisoformat(made_on)
    except ValueError:
        raise TrialError("ระบุวันที่จัดทำรายการอ้างอิง (ปี-เดือน-วัน)")
    source = "web" if s.path == "r2" else g("source")
    if source not in SOURCES or (s.path == "r1" and source == "web"):
        raise TrialError("ระบุที่มาของรายการ")
    made, seen = g("made"), g("seen")
    if made not in MADE:
        raise TrialError("ระบุว่าจัดทำรายการก่อนหรือหลังเห็นผลของระบบ")
    if seen not in SEEN:
        raise TrialError("ระบุว่าเคยเห็นผลของระบบกับคู่นี้มาก่อนหรือไม่")
    if seen == "seen" and not g("seen_note"):
        raise TrialError("เคยเห็นผลมาก่อน — ระบุสั้น ๆ ว่าเห็นอะไร")
    parts = {}
    for code, _label in PARTS:
        st = g(f"part_{code}")
        if st not in COVERAGE:
            raise TrialError(f"ระบุความครอบคลุมของส่วนที่ {code} (ตรวจครบ / บางส่วน / ไม่ได้ตรวจ)")
        parts[code] = st
    if all(v == "none" for v in parts.values()):
        raise TrialError("ต้องมีส่วนของเล่มที่ตรวจอย่างน้อย 1 ส่วน")
    first = g("edition_first")[:160] or declaration_defaults(s)["edition_first"]
    second = g("edition_second")[:160] or declaration_defaults(s)["edition_second"]
    topics: dict = {}
    rows, expect = [], None
    allowed = dict(topic_codes(s.xkind))
    stray = sorted({c for c, _l in TOPIC_CODES if c not in allowed
                    for f in ("total", "root", "red", "covered") if str(form.get(f"t_{c}_{f}") or "").strip()})
    if stray:                      # คู่ข้ามปี: ห้ามกรอกหัวข้อนอก ค ช ซ จ แล้วทิ้งเงียบ ๆ
        raise TrialError(f"คู่ข้ามปีนับเฉพาะความต่างเชิงโครงสร้าง — หัวข้อ {' '.join(stray)} ไม่ใช้กับคู่นี้ "
                         f"(ใช้ {' '.join(XYEAR_TOPICS)} เท่านั้น)")
    if s.path == "r1":
        for code, _label in topic_codes(s.xkind):
            total = _count(form.get(f"t_{code}_total"), f"หัวข้อ {code} ประเด็นทั้งหมด")
            root = _count(form.get(f"t_{code}_root"), f"หัวข้อ {code} ต้นเหตุ")
            red = _count(form.get(f"t_{code}_red"), f"หัวข้อ {code} ระดับแดง")
            if total is None:
                if root is not None or red is not None:
                    raise TrialError(f"หัวข้อ {code}: ใส่จำนวนต้นเหตุ/แดงแล้ว ต้องใส่ประเด็นทั้งหมดด้วย "
                                     "(หัวข้อที่รายการไม่ครอบคลุมให้เว้นว่างทั้งแถว)")
                continue
            root, red = root or 0, red or 0
            if root > total or red > total:
                raise TrialError(f"หัวข้อ {code}: ต้นเหตุหรือระดับแดงมากกว่าประเด็นทั้งหมดไม่ได้")
            if total > MAX_ROWS_PER_TOPIC:
                raise TrialError(f"หัวข้อ {code}: จำนวนประเด็นมากเกินกว่าที่หน้าทดลองรับได้ ({MAX_ROWS_PER_TOPIC})")
            topics[code] = {"total": total, "root": root, "red": red}
            rows += [{"topic": code, "seq": k} for k in range(1, total + 1)]
        if not topics:
            raise TrialError("ใส่จำนวนประเด็นอย่างน้อย 1 หัวข้อ (หัวข้อที่ตรวจแล้วไม่พบความต่างใส่ 0)")
        if len(rows) > MAX_ROWS:
            raise TrialError(f"จำนวนประเด็นรวมมากเกินกว่าที่หน้าทดลองรับได้ ({MAX_ROWS})")
    else:
        gaps = [(m, mark_gaps(m, s.xkind)) for m in s.circles]
        gaps = [(m, x) for m, x in gaps if x]
        if gaps:
            lab = s.labels
            eg = " · ".join(f"{lab[m['side']]} หน้า {m['page']} ({', '.join(x)})" for m, x in gaps[:4])
            raise TrialError(f"ยังกรอกรายละเอียดจุดที่วงไม่ครบ {len(gaps)} จุด — {eg}{' …' if len(gaps) > 4 else ''}")
        marked = {m["topic"] for m in s.circles}
        for code, _label in topic_codes(s.xkind):
            mine = [m for m in s.circles if m["topic"] == code]
            if code in marked or g(f"t_{code}_covered") in ("1", "true", "True", "on"):
                topics[code] = {"total": len(mine), "root": sum(1 for m in mine if m["cause"] == "t"),
                                "red": sum(1 for m in mine if m["level"] == "red")}
        if not topics:
            raise TrialError("ระบุหัวข้อที่รายการครอบคลุมอย่างน้อย 1 หัวข้อ (ตรวจแล้วไม่พบความต่างก็ติ๊กได้)")
        expect = trial_repo.marks_hash(s.circles)
    decl = {"path": s.path, "protocol": s.protocol, "trial_version": TRIAL_VERSION, "made_on": made_on,
            "source": source, "editions": {"first": first, "second": second}, "made": made, "seen": seen,
            "seen_note": g("seen_note")[:200] if seen == "seen" else "", "parts": parts, "topics": topics,
            # สำเนาลงวันที่/แฮชของรายการฉบับล็อกที่ผู้ตรวจเก็บไว้เอง (ไม่ส่งเนื้อหา — รีวิวโบ 6409928179 ข้อ 1)
            "own_copy": g("own_copy")[:120]}
    if expect is not None:
        decl["marks_hash"], decl["marks"] = expect, len(s.circles)
    return decl, rows, expect


def lock(sid: str, form: dict | None = None) -> str:
    """ส่งใบประกาศ = ล็อก (แก้รายการ/ใบประกาศไม่ได้) → ระบบเทียบ → เสนอคู่ · คืน run_id
    (ระบบเทียบไม่สำเร็จ = คืน "" และบันทึกเหตุไว้กับรอบ ให้กด "ลองเทียบอีกครั้ง" — ใบประกาศยังอยู่)"""
    s = _need(sid)
    decl, rows, expect = _validate_declaration(s, form or {})
    counts = {"path": s.path, "issues": len(rows) if s.path == "r1" else len(s.circles),
              "topics": {k: v["total"] for k, v in decl["topics"].items()}, "pages_done": len(s.done)}
    _repo(trial_repo.lock, sid, counts, declaration=decl, rows=rows, expect_marks_hash=expect,
          protocol=s.protocol, path=s.path)
    try:
        return ensure_run(sid)
    except TrialError:
        return ""


_run_locks: dict = {}
_run_guard = threading.Lock()


def _run_lock(sid: str) -> threading.Lock:
    with _run_guard:
        return _run_locks.setdefault(sid, threading.Lock())


def ensure_run(sid: str) -> str:
    """รอบเทียบของระบบ — **ครั้งเดียวต่อรอบตรวจ** (กันกดซ้ำ/หลายแท็บด้วยล็อกต่อรอบ + ผูกได้ครั้งเดียวในฐานข้อมูล) ·
    เรียกจากคำขอที่เปลี่ยนสถานะเท่านั้น (ส่งใบประกาศ / ลองเทียบอีกครั้ง) — การเปิดดูผลไม่สร้างรอบเทียบ ·
    ล้มเหลว = บันทึกเหตุ (สถานะการรัน "ล้มเหลว") แล้วแจ้ง"""
    with _run_lock(sid):
        s = _need(sid, unlocked=False, active=False)
        if not s.locked:
            raise TrialError("ต้องส่งใบประกาศก่อน ระบบจึงเทียบให้ดู")
        if s.rec["run_id"]:
            return s.rec["run_id"]
        if not s.active:
            raise TrialError("รอบนี้หยุดหรือถอนตัวแล้ว — ระบบไม่เทียบ")
        try:
            # ระบบเทียบกับไฟล์เดียวกับที่ผู้ตรวจใช้เท่านั้น (SHA-256 ที่บันทึกตอนเริ่มตรวจ) — เล่มบนชั้นเปลี่ยน = ไม่เทียบ
            for side in ("prev", "cur"):
                _side_path(s, side)
            pid, rid = pdfshelf.start(s.book["prev"]["key"], s.book["cur"]["key"], s.book["agency"],
                                      expect_sha={"A": s.book["prev"]["sha256"], "B": s.book["cur"]["sha256"]})
        except (TrialError, pdfshelf.ShelfError, pdfpair.PairError, OSError, reader.ReaderUnavailable) as e:
            trial_repo.run_failed(sid, str(e))
            raise TrialError(f"ระบบเทียบไม่สำเร็จ — {e}")
        except Exception:
            trial_repo.run_failed(sid, "ข้อผิดพลาดภายในระบบระหว่างเทียบ")
            raise
        if not trial_repo.attach_run(sid, pid, rid):
            return trial_repo.get_session(sid)["run_id"]
        v = pdfpair.view(rid)
        rows = classify_run(s, v)
        trial_repo.save_obs_class(sid, rows)
        levels = {r["finding_id"]: r["level"] for r in rows}
        trial_repo.save_proposals(sid, {m["id"]: propose(m, v, s, levels) for m in s.circles})
        return rid


def retry_run(sid: str) -> str:
    _need(sid, unlocked=False)
    return ensure_run(sid)


def level_and_reason(f, kind: str = "same_year", *, xrule: bool = True, engine: str = XYEAR_ENGINE) -> tuple[str, str]:
    """ระดับของข้อสังเกต + เหตุ · คู่ข้ามปี (กติกาใช้กับรอบนี้): ตัวเทียบรุ่นไม่ตรงกติกา = ต้องทบทวนทุกข้อ ·
    กติกาไม่รู้จัก = ต้องทบทวน · ไม่ใช่เชิงโครงสร้าง = เชิงพรรณนา"""
    if f.kind == cmp.K_UNREAD:
        return "unread", ""
    if kind == "cross_year" and xrule:
        if engine not in XYEAR_ENGINES:
            return "review", f"รุ่นตัวเทียบของผล ({engine or 'ไม่ทราบ'}) ไม่ตรงกติกา ({XYEAR_RULE})"
        cls, why = classify(f)
        return {"structural": "must", "out": "descriptive", "unknown": "review"}[cls], why
    return ("info" if f.info else "must"), ""


def finding_level(f, kind: str = "same_year", *, xrule: bool = True, engine: str = XYEAR_ENGINE) -> str:
    """ระดับของข้อสังเกตตามรุ่นนี้ (:data:`LEVEL_DEFINITION`) · คู่ข้ามปีใช้ :func:`classify`"""
    return level_and_reason(f, kind, xrule=xrule, engine=engine)[0]


def _run_engine(v) -> str:
    return str(((v.run or {}).get("versions") or {}).get("pdfbook", ""))


def classify_run(s, v) -> list:
    """แถวการจัดประเภทต่อข้อสังเกต (ข้อมูลเดิมของตัวเทียบ + การจัดประเภทเพื่อประเมิน) — บันทึกครั้งเดียวต่อรอบ"""
    eng = _run_engine(v)
    out = []
    for f in v.result.findings:
        lv, why = level_and_reason(f, s.pair_kind, xrule=s.xrule_applies, engine=eng)
        out.append({"finding_id": f.id, "topic": f.topic, "kind": f.kind, "info": bool(f.info), "level": lv,
                    "reason": why, "rule": XYEAR_RULE if s.pair_kind == "cross_year" and s.xrule_applies else "",
                    "engine": eng})
    return out


def _pt(s: Session, m: dict) -> tuple[float, float]:
    w, h = reader.page_size(_side_path(s, m["side"]), int(m["page"]))
    return m["fx"] * w, m["fy"] * h


def propose(m: dict, v, s: Session, levels: dict | None = None) -> str:
    """ข้อสังเกตที่อยู่ใกล้จุดที่วงที่สุดบนหน้าเดียวกัน ("" = ไม่มี) — ข้อเสนอเท่านั้น · ทุกระดับที่จับคู่ได้
    (ต้องตรวจ · ข้อมูลประกอบ) · ระยะเท่ากัน = ข้อต้องตรวจก่อน"""
    x, y = _pt(s, m)
    best, key = "", None
    if levels is None:
        levels = {f.id: finding_level(f, s.pair_kind, xrule=s.xrule_applies, engine=_run_engine(v))
                  for f in v.result.findings}
    for f in v.result.findings:
        if levels.get(f.id) not in ("must", "info"):
            continue
        sd = f.b if m["side"] == "cur" else f.a
        if sd.page != m["page"] or not sd.bbox:
            continue
        x0, y0, x1, y1 = sd.bbox
        if x0 - MATCH_X_PT <= x <= x1 + MATCH_X_PT and y0 - MATCH_Y_PT <= y <= y1 + MATCH_Y_PT:
            k = (abs(y - (y0 + y1) / 2) + (0 if x0 <= x <= x1 else 5), 1 if f.info else 0)
            if key is None or k < key:
                best, key = f.id, k
    return best


# ── ผล (ฉบับ 0.2) ──────────────────────────────────────────────────────────────
def _rate(num: int, den: int, ready: bool = True) -> dict:
    """ค่าที่รายงาน — ตัวตั้ง/ตัวหารเสมอ · ร้อยละเฉพาะเมื่อตัวหาร ≥ 10 · ตัวหารเป็นศูนย์ = "คำนวณไม่ได้" (วิธีวัดผล หมวด 7)"""
    if not ready:
        return {"num": num, "den": den, "pct": None, "text": "ยังตัดสินไม่ครบ"}
    if den <= 0:
        return {"num": num, "den": den, "pct": None, "text": "คำนวณไม่ได้"}
    pct = round(100 * num / den, 1) if den >= 10 else None
    return {"num": num, "den": den, "pct": pct, "text": f"{num} จาก {den}" + (f" ({pct}%)" if pct is not None else "")}


def decision_gaps(d: dict | None, links_: list, matchable: set, v03: bool = False) -> list[str]:
    """สิ่งที่คำตัดสินของประเด็นยังขาด ([] = ครบ)"""
    if not d:
        return ["ผลการจับคู่"]
    out = []
    v = d.get("verdict")
    if v in ("exact", "partial"):
        if not links_ or any(fid not in matchable for fid in links_):
            out.append("ข้อสังเกตที่จับคู่")
        if v03:
            sides = [x for x in (d.get("relevant_sides") or "").split(",") if x]
            if agg.location_errors(d.get("location") or "", sides, d.get("search_scope") or ""):
                out.append("สถานะตำแหน่ง (A2)")
        elif d.get("evidence") not in EVIDENCE:
            out.append("หลักฐานชี้ตำแหน่ง")
    if v == "partial" and d.get("reason") not in (PARTIAL_REASONS_V03 if v03 else PARTIAL_REASONS):
        out.append("รหัสเหตุ บ")
    if v == "missed" and d.get("reason") not in MISS_REASONS:
        out.append("รหัสเหตุ พ")
    if d.get("basis") not in BASIS:
        out.append("ฐานการวินิจฉัย")
    return out


def row_gaps(m: dict) -> list[str]:
    """ลักษณะของแถว ร1 ที่ยังไม่ได้กรอก (ต้องใช้คำนวณ N และอัตราแยกต้นเหตุ/ระดับ)"""
    out = []
    if not m.get("part"):
        out.append("ส่วนของเล่ม")
    if not m.get("cause"):
        out.append("ต/ล")
    if m.get("level") not in LEVELS:
        out.append("ระดับ")
    if m.get("found_in") and not (m.get("searched") or "").strip():
        out.append("ขอบเขตที่ค้นในอีกฉบับ")
    if not (m.get("ref") or "").strip():
        out.append("ข้อที่ในรายการที่ล็อก")
    if not valid_row_source(m.get("row_source") or "") and m.get("row_source") != "post_result":
        out.append("ที่มาของลักษณะแถว")
    return out


def group_gaps(g: dict | None) -> list[str]:
    if not g or g.get("grp") not in GROUPS:
        return ["กลุ่ม"]
    out = []
    if g["grp"] == "s3" and g.get("s3_reason") not in S3_REASONS:
        out.append("เหตุของ ส3")
    if g["grp"] in S_GROUPS and g.get("basis") not in BASIS:
        out.append("ฐานการวินิจฉัย")
    if g["grp"] == "outside" and (not g.get("part") or not (g.get("note") or "").strip()):
        out.append("ส่วนที่ไม่ได้ตรวจครบ + เหตุ")
    return out


class Result:
    """ผลของรอบที่ล็อกแล้ว (ฉบับ 0.2) — คำนวณจากรอบเทียบที่ผูกไว้ + ใบประกาศ + คำตัดสินของผู้ตรวจ"""

    legacy = False

    def __init__(self, s: Session, view, decl: dict, decisions: dict, links_: dict, proposals: dict, groups: dict,
                 answers: dict, notes: list, hist: list):
        self.s, self.view, self.decl = s, view, decl
        self.decisions, self.links, self.proposals, self.groups = decisions, links_, proposals, groups
        self.answers, self.notes, self.history_rows = answers, notes, hist
        self.findings = view.result.findings
        self.by_id = {f.id: f for f in self.findings}
        self.engine = _run_engine(view)
        stored = trial_repo.obs_class(s.sid)
        self.class_stored = bool(stored)
        self.level, self.level_reason = {}, {}
        for f in self.findings:
            if f.id in stored:
                lv, why = stored[f.id]["level"], stored[f.id]["reason"]
            else:
                lv, why = level_and_reason(f, s.pair_kind, xrule=s.xrule_applies, engine=self.engine)
            self.level[f.id], self.level_reason[f.id] = lv, why
        self.matchable_ids = {fid for fid, lv in self.level.items() if lv in ("must", "info")}
        self.obs_eval = trial_repo.obs_evals(s.sid) if s.v03 else {}
        self.issues = list(s.rows if s.path == "r1" else s.circles)
        self.issue_by_id = {m["id"]: m for m in self.issues}
        body = decl["body"]
        self.full_parts = {p for p, st in body["parts"].items() if st == "full"}
        self.covered = set(body["topics"])
        self._metrics = None

    # ── ข้อสังเกต ──
    def finding(self, fid: str):
        return self.by_id.get(fid) if fid else None

    def of_level(self, level: str) -> list:
        return [f for f in self.findings if self.level[f.id] == level]

    def read_problem_ids(self, kind: str) -> list:
        return [f.id for f in self.findings if read_problem(f) == kind]

    @property
    def matchable(self) -> list:
        return [f for f in self.findings if f.id in self.matchable_ids]

    @property
    def found_links(self) -> dict:
        """finding_id → [ประเด็น] ของประเด็นที่ผู้ตรวจยืนยันว่าพบ (ตรง/บางส่วน)"""
        out: dict = {}
        for mid, fids in self.links.items():
            d = self.decisions.get(mid)
            if mid in self.issue_by_id and d and d["verdict"] in ("exact", "partial"):
                for fid in fids:
                    out.setdefault(fid, []).append(mid)
        return out

    @property
    def unmatched_must(self) -> list:
        fl = self.found_links
        return [f for f in self.of_level("must") if f.id not in fl]

    # ── ประเด็น ──
    def in_full_part(self, m: dict) -> bool:
        return m.get("part") in self.full_parts

    def xyear_numeric(self, m: dict) -> bool:
        """ประเด็นคู่ข้ามปีที่ผู้ตรวจระบุว่าไม่ใช่เชิงโครงสร้าง (ค่า/วงเงิน/เป้าหมาย) — ออกจาก N₀ เป็นรายการเชิงพรรณนา ·
        ระบุหลังเห็นผล (ร1) = ตัดออกไม่ได้ (กันการลดตัวหารหลังเห็นผล)"""
        return (self.s.pair_kind == "cross_year" and self.s.xrule_applies and m.get("xtype") == "numeric"
                and "xtype" not in post_dims(m))

    def in_scope(self, m: dict) -> bool:
        """อยู่ในตัวหาร N — ส่วนของเล่มที่ประกาศว่าตรวจครบ และหัวข้อที่รายการครอบคลุม ·
        คู่ข้ามปี: ไม่ใช่ประเด็นตัวเลขที่ผู้ตรวจระบุก่อนเห็นผล"""
        return self.in_full_part(m) and m.get("topic") in self.covered and not self.xyear_numeric(m)

    def gaps(self, m: dict) -> list[str]:
        out = (row_gaps(m) if m.get("origin") == "row" else []) + xtype_gap(m, self.s.xkind)
        return out + decision_gaps(self.decisions.get(m["id"]), self.links.get(m["id"], []), self.matchable_ids,
                                   self.s.v03)

    def verdict_of(self, m: dict) -> str:
        """ผลที่นับได้ ("pending" = ยังตัดสิน/กรอกไม่ครบ ไม่นับเป็นพบหรือพลาด)"""
        return "pending" if self.gaps(m) else self.decisions[m["id"]]["verdict"]

    def history(self, kind: str, target: str) -> list:
        return [h for h in self.history_rows if h["target_kind"] == kind and h["target_id"] == target]

    def candidates(self, m: dict) -> list:
        """ข้อสังเกตที่เลือกจับคู่เองได้ (ทุกข้อที่จับคู่ได้ ไม่จำกัดจำนวน) — หน้าใกล้ในฉบับเดียวกันก่อน แล้วหัวข้อเดียวกัน
        (ย้ายหน้าได้ — เลือกข้อจากหน้าอื่นได้เสมอ)"""
        side, other = ("b", "a") if m.get("side") == "cur" else ("a", "b")
        page = int(m.get("page") or 0)

        def key(f):
            p = getattr(f, side).page if m.get("side") else None
            near = p is not None and page and abs(p - page) <= 1
            same_topic = system_topic(f, self.s.pair_kind) == m.get("topic")
            return (0 if near else (1 if same_topic else 2), abs((p or getattr(f, other).page or 0) - page),
                    1 if f.info else 0)
        return sorted(self.matchable, key=key)

    # ── การนับ (วิธีวัดผล หมวด 7) ──
    def _a1(self, issues: list) -> dict:
        c = {"issues": len(issues), "exact": 0, "partial": 0, "missed": 0, "undecidable": 0, "pending": 0}
        for m in issues:
            c[self.verdict_of(m)] += 1
        n = c["issues"] - c["undecidable"]
        ready = c["pending"] == 0
        c["N0"] = c["issues"]            # ประเด็นที่ล็อกทั้งหมดในขอบเขต = พบตรง + บางส่วน + พลาด + ตัดสินไม่ได้ (+ ยังไม่ครบ)
        c["N"] = n
        c["strict"] = _rate(c["exact"], n, ready)
        c["with_partial"] = _rate(c["exact"] + c["partial"], n, ready)
        return c

    def buckets(self) -> dict:
        """ข้อต้องตรวจแต่ละข้ออยู่ถังเดียว: จ (จับคู่ในส่วนที่ตรวจครบ) · ส1–ส4 · นอกส่วนที่ตรวจครบ · ยังไม่จัด"""
        fl = self.found_links
        b = {k: [] for k in ("matched", *S_GROUPS, "outside", "outside_linked", "pending")}
        for fid in (f.id for f in self.of_level("must")):
            mids = fl.get(fid)
            if mids:
                b["matched" if any(self.in_full_part(self.issue_by_id[x]) for x in mids) else "outside_linked"].append(fid)
                continue
            g = self.groups.get(fid)
            b["pending" if group_gaps(g) else g["grp"]].append(fid)
        return b

    @property
    def u_ids(self) -> list:
        """U = F = ข้อต้องตรวจในส่วนที่ตรวจครบ ภายในขอบเขตของคู่ (จ + ส1–ส4) — จักรวาลของ A3-อ/A3-ข"""
        b = self.buckets()
        return b["matched"] + [fid for g in S_GROUPS for fid in b[g]]

    def obs_evaluable(self, fid: str) -> bool:
        """ประเมิน A3 ได้ = ข้อต้องตรวจที่ไม่ได้อยู่นอกส่วนที่ตรวจครบ (ประเมินก่อนจัดกลุ่มเสร็จได้)"""
        if self.level.get(fid) != "must":
            return False
        b = self.buckets()
        return fid not in b["outside"] and fid not in b["outside_linked"]

    def _ledger(self) -> dict:
        """บัญชีข้อสังเกตต้องตรวจ — แต่ละข้ออยู่ในกลุ่มเดียวเท่านั้น · ข้อมูลไม่สอดคล้อง = :class:`LedgerError`"""
        for mid, fids in self.links.items():
            for fid in fids:
                if fid not in self.by_id:
                    raise LedgerError(f"บัญชีข้อสังเกตไม่ปิด: ประเด็น {mid} จับคู่กับข้อสังเกต {fid} ที่ไม่มีในรอบเทียบนี้ "
                                      "— ห้ามรายงาน ต้องหาต้นเหตุก่อน")
                if fid not in self.matchable_ids:
                    raise LedgerError(f"บัญชีข้อสังเกตไม่ปิด: ข้อสังเกต {fid} อยู่ในส่วนที่ระบบอ่านไม่ได้ "
                                      "หรือไม่ใช่เชิงโครงสร้างของคู่ข้ามปี แต่ถูกจับคู่เป็นพบ — ห้ามรายงาน")
        for fid in self.groups:
            if fid not in self.by_id or self.level[fid] != "must":
                raise LedgerError(f"บัญชีข้อสังเกตไม่ปิด: กลุ่ม ส ของข้อสังเกต {fid} ที่ไม่ใช่ข้อต้องตรวจของรอบนี้ "
                                  "— ห้ามรายงาน ต้องหาต้นเหตุก่อน")
        must = [f.id for f in self.of_level("must")]
        fl = self.found_links
        b = self.buckets()
        placed = [fid for v in b.values() for fid in v]
        if len(placed) != len(must) or set(placed) != set(must):
            raise LedgerError("บัญชีข้อสังเกตไม่ปิด: มีข้อสังเกตที่ถูกนับซ้ำหรือตกหล่น — ห้ามรายงาน ต้องหาต้นเหตุก่อน")
        n = {k: len(v) for k, v in b.items()}
        f_total = n["matched"] + sum(n[k] for k in S_GROUPS)
        if f_total != len(must) - n["outside"] - n["outside_linked"] - n["pending"]:
            raise LedgerError("บัญชีข้อสังเกตไม่ปิด: F ≠ จ + ส1 + ส2 + ส3 + ส4 — ห้ามรายงาน ต้องหาต้นเหตุก่อน")
        closed = n["pending"] == 0
        s3 = Counter(self.groups[fid]["s3_reason"] for fid in b["s3"])
        return {"F": f_total, "matched": n["matched"], **{k: n[k] for k in S_GROUPS},
                "s3_reasons": {k: s3.get(k, 0) for k in S3_REASONS}, "pending": n["pending"], "closed": closed,
                "outside": n["outside"] + n["outside_linked"], "outside_linked": n["outside_linked"],
                "must_total": len(must), "superseded_groups": sum(1 for fid in self.groups if fid in fl),
                "false_alarm": _rate(n["s3"], f_total - n["s4"], closed),
                # สัดส่วน "ความต่างจริง" ระงับไว้ — สูตรเดิมนับข้อที่จับคู่แบบบางส่วน/จับคู่ผิดเป็นถูก
                # รอนิยามแยกความถูกของข้อสังเกตจากการจับคู่ (รีวิวโบ 6409928179 ข้อ 2 · 6417479593) — แสดงเฉพาะบัญชีจำนวน
                "real_difference": None,
                "outside_by_part": dict(Counter(self.groups[fid].get("part", "") for fid in b["outside"])),
                "system_extra_confirmed": n["s1"] + n["s2"]}

    @property
    def metrics(self) -> dict:
        if self._metrics is None:
            self._metrics = self._calc()
        return self._metrics

    def _calc(self) -> dict:
        ledger = self._ledger()
        scope = [m for m in self.issues if self.in_scope(m)]
        out_scope = [m for m in self.issues if not self.in_scope(m)]
        a1 = self._a1(scope)
        reasons_b = Counter(self.decisions[m["id"]]["reason"] for m in scope if self.verdict_of(m) == "partial")
        reasons_p = Counter(self.decisions[m["id"]]["reason"] for m in scope if self.verdict_of(m) == "missed")
        a1["partial_reasons"] = {k: reasons_b.get(k, 0) for k in PARTIAL_REASONS}
        a1["missed_reasons"] = {k: reasons_p.get(k, 0) for k in MISS_REASONS}
        found = [m for m in scope if self.verdict_of(m) in ("exact", "partial")]
        lvl = Counter("must" if any(self.level.get(fid) == "must" for fid in self.links.get(m["id"], [])) else "info"
                      for m in found)
        a1["matched_level"] = {"must": lvl.get("must", 0), "info": lvl.get("info", 0)}
        ev = Counter(self.decisions[m["id"]]["evidence"] for m in found)
        a2 = {k: ev.get(k, 0) for k in EVIDENCE}
        a2["found"] = len(found)
        a2["rate"] = _rate(a2["all"], len(found), a1["pending"] == 0)
        decided = [m for m in self.issues if self.verdict_of(m) != "pending"]
        basis = Counter(self.decisions[m["id"]]["basis"] for m in decided)
        for fid, g in self.groups.items():
            if fid not in self.found_links and not group_gaps(g) and g["grp"] in S_GROUPS:
                basis[g["basis"]] += 1
        b1 = {k: basis.get(k, 0) for k in BASIS}
        b1["total"] = sum(b1.values())
        parts = Counter(self.decl["body"]["parts"].values())
        info = self.of_level("info")
        fl = self.found_links
        cov = (self.view.facts_a.coverage, self.view.facts_b.coverage)
        return {
            "A1": {**a1, "by_cause": {k: self._a1([m for m in scope if m.get("cause") == k and "cause" not in post_dims(m)])
                                      for k in CAUSES},
                   "by_level": {k: self._a1([m for m in scope if m.get("level") == k and "level" not in post_dims(m)])
                                for k in LEVELS},
                   "by_topic": {k: self._a1([m for m in scope if m.get("topic") == k])
                                for k, _l in topic_codes(self.s.xkind) if k in self.covered},
                   "out_of_scope": {k: v for k, v in self._a1(out_scope).items() if k not in ("strict", "with_partial")},
                   # ร1: ตัวประเด็นมาจากรายการที่ล็อก จึงอยู่ในผลรวมหลักเสมอ · มิติที่จัดใหม่หลังเห็นผลแยกออกเฉพาะมิตินั้น
                   # (ต/ล → ไม่อยู่ใน by_cause · ระดับ → ไม่อยู่ใน by_level · ส่วน → ขอบเขตอิงการจัดหลังเห็นผล รายงานแยก)
                   "post_result": {d: sum(1 for m in scope if d in post_dims(m)) for d in POST_DIMS},
                   "scope_locked_only": self._a1([m for m in scope if "part" not in post_dims(m)])},
            "A2": a2,
            "A3": ledger,
            "A4": {"parts": {k: parts.get(k, 0) for k in COVERAGE}, "topics_covered": sorted(self.covered),
                   "unread_pages": {"prev": sorted(cov[0].pages_no_text), "cur": sorted(cov[1].pages_no_text)},
                   "unread_findings": len(self.of_level("unread")),
                   "read_problems": {k: sum(1 for f in self.findings if read_problem(f) == k) for k in READ_PROBLEMS},
                   "missed_unread": a1["missed_reasons"]["p1"],
                   "info_findings": len(info), "info_matched": sum(1 for f in info if f.id in fl),
                   "must_outside": ledger["outside"]},
            "B1_basis": b1,
            "findings": {"total": len(self.findings), **{k: len(self.of_level(k)) for k in FINDING_LEVELS}},
            # คู่ข้ามปี: กติกาแยก + ข้อที่ไม่ใช่เชิงโครงสร้างรายงานเป็นจำนวนแยกตามชนิดเท่านั้น (ไม่จัด ส ไม่เข้า F)
            "scope": ({"pair_kind": "cross_year", "label": XYEAR_SCOPE_LABEL, "rule": XYEAR_RULE,
                       "engine": self.engine, "engine_ok": self.engine in XYEAR_ENGINES,
                       "classification_stored": self.class_stored,
                       "descriptive_by_kind": dict(sorted(Counter(f.kind for f in self.of_level("descriptive")).items())),
                       "review_by_reason": dict(sorted(Counter(self.level_reason[f.id]
                                                                for f in self.of_level("review")).items())),
                       "excluded_numeric_issues": sum(1 for m in self.issues if self.xyear_numeric(m))}
                      if self.s.pair_kind == "cross_year" and self.s.xrule_applies
                      else {"pair_kind": self.s.pair_kind, "rule": ""}),
            # ข้อมูลเดิมของตัวเทียบ × การจัดประเภทเพื่อประเมิน (ตรวจย้อนหลังได้ · รีวิวโบ 6459664149 ข้อ 4)
            "classification": {f"{k}|{lv}": n for (k, lv), n in sorted(Counter(
                (f.kind, self.level[f.id]) for f in self.findings).items())},
            "post_lock_notes": len(self.notes),
            **({"v03": self._calc_v03(scope, ledger)} if self.s.v03 else {}),
        }

    def _calc_v03(self, scope: list, ledger: dict) -> dict:
        """ตัวนับตามวิธีวัดผล 0.3 ร่าง ๒ — นับจำนวนก่อน แล้วจึงสัดส่วน (ผ่าน :mod:`trial_aggregate`) ·
        ยังตัดสินไม่ครบ = ส่งจำนวน ไม่ส่งสัดส่วน"""
        c = Counter(self.verdict_of(m) for m in scope)
        miss = Counter(self.decisions[m["id"]]["reason"] for m in scope if self.verdict_of(m) == "missed")
        counts = {"N0": len(scope), "undecidable": c["undecidable"], "exact": c["exact"], "partial": c["partial"],
                  "miss": {k: miss.get(k, 0) for k in agg.MISS_CODES}}
        loc: dict = {st: {"exact": 0, "partial": 0} for st in agg.LOCATION_STATUSES}
        for m in scope:
            v = self.verdict_of(m)
            if v in ("exact", "partial"):
                st = self.decisions[m["id"]].get("location") or ""
                if st in loc:
                    loc[st][v] += 1
        u = self.u_ids
        groups = {"matched": ledger["matched"], **{g: ledger[g] for g in S_GROUPS}}
        grp_of = {fid: g for g, ids in self.buckets().items() for fid in ids}
        ct = {a: {b: 0 for b in agg.JUDGE4} for a in agg.JUDGE4}
        by_g = {g: {a: {b: 0 for b in agg.JUDGE4} for a in agg.JUDGE4} for g in agg.GROUPS}
        for fid in u:
            e = self.obs_eval.get(fid)
            if e:
                ct[e["fidelity"]][e["assertion"]] += 1
                by_g[grp_of[fid]][e["fidelity"]][e["assertion"]] += 1
        obs_counts = {"F": ledger["F"], "groups": groups, "s3_reasons": ledger["s3_reasons"], "crosstab": ct,
                      "crosstab_by_group": by_g}
        ready_issues = c["pending"] == 0
        ready_loc = ready_issues and sum(v["exact"] + v["partial"] for v in loc.values()) == c["exact"] + c["partial"]
        ready_obs = ledger["closed"] and all(fid in self.obs_eval for fid in u)
        return {"counts": {"issues": counts, "location": loc, "obs": obs_counts},
                "pending": {"issues": c["pending"], "location": (c["exact"] + c["partial"]) - sum(
                    v["exact"] + v["partial"] for v in loc.values()),
                    "obs": sum(1 for fid in u if fid not in self.obs_eval) + ledger["pending"]},
                "issues": agg.issues(counts) if ready_issues else None,
                "location": agg.location(loc, c["exact"] + c["partial"]) if ready_loc else None,
                "obs": agg.observations(obs_counts) if ready_obs else None}

    @property
    def declaration_check(self) -> list:
        """ร1: จำนวนในแถวที่กรอกแล้ว เทียบกับใบประกาศรายหัวข้อ — ไม่ตรง = รายงาน (ไม่ปรับให้ตรงเงียบ ๆ)"""
        if self.s.path != "r1":
            return []
        out = []
        for code, d in self.decl["body"]["topics"].items():
            rows = [m for m in self.issues if m["topic"] == code]
            filled = all(m.get("cause") and m.get("level") in LEVELS for m in rows)
            root = sum(1 for m in rows if m.get("cause") == "t")
            red = sum(1 for m in rows if m.get("level") == "red")
            if filled and (root != d["root"] or red != d["red"]):
                out.append({"topic": code, "declared_root": d["root"], "rows_root": root,
                            "declared_red": d["red"], "rows_red": red})
        return out

    @property
    def complete(self) -> bool:
        """ครบ = ทุกประเด็นตัดสินแล้ว · ทุกข้อต้องตรวจจัดกลุ่มแล้ว · **ไม่มีข้อที่ต้องทบทวนกติกา** (สรุปครบไม่ได้)"""
        return (not any(self.gaps(m) for m in self.issues)
                and not any(group_gaps(self.groups.get(f.id)) for f in self.unmatched_must)
                and not self.of_level("review")
                and not (self.s.v03 and any(fid not in self.obs_eval for fid in self.u_ids)))


class LegacyResult:
    """รอบกติกา 0.1 ที่ส่งผลแล้ว — อ่านได้อย่างเดียว · นับตามฉบับ 0.1 (ไม่ใช้ในผลฉบับ 0.2)"""

    legacy = True

    def __init__(self, s: Session, view, links_: dict, extras: dict, answers: dict):
        self.s, self.view, self.links, self.extras, self.answers = s, view, links_, extras, answers

    def finding(self, fid: str):
        return self.view.finding(fid) if fid else None

    @property
    def actionable(self) -> list:
        return [f for f in self.view.result.findings if not f.info]

    @property
    def linked_ids(self) -> set:
        return {ln["finding_id"] for ln in self.links.values()
                if ln["finding_id"] and ln["verdict"] in ("exact", "partial", "")}

    @property
    def unlinked_findings(self) -> list:
        return [f for f in self.actionable if f.id not in self.linked_ids]

    @property
    def metrics(self) -> dict:
        per = {p: {"total": 0, "exact": 0, "partial": 0, "missed": 0, "pending": 0} for p in PENS}
        for m in self.s.circles:
            c = per[m["pen"]]
            c["total"] += 1
            ln = self.links.get(m["id"]) or {}
            v = ln.get("verdict", "")
            if v in ("exact", "partial") and ln.get("finding_id"):
                c[v] += 1
            elif v == "not_same":
                c["missed"] += 1
            else:
                c["pending"] += 1
        ext = {k: 0 for k in LEGACY_EXTRA_VERDICTS}
        ext["pending"] = 0
        for f in self.unlinked_findings:
            ext[self.extras.get(f.id, "pending")] += 1
        return {"pens": per, "extras": ext, "info": len(self.view.result.findings) - len(self.actionable),
                "actionable": len(self.actionable),
                "unread": sum(1 for f in self.actionable if f.kind == cmp.K_UNREAD)}

    @property
    def complete(self) -> bool:
        m = self.metrics
        return all(c["pending"] == 0 for c in m["pens"].values()) and m["extras"]["pending"] == 0


def result(sid: str):
    """ผลของรอบที่ล็อกแล้ว — **ไม่สร้างรอบเทียบ** (สร้างตอนส่งใบประกาศ/ลองเทียบอีกครั้งเท่านั้น)"""
    s = _need(sid, unlocked=False, active=False)
    if not s.locked:
        raise TrialError("ต้องส่งใบประกาศก่อน ระบบจึงเทียบให้ดู")
    rid = s.rec["run_id"]
    if not rid:
        raise TrialError("ระบบยังเทียบไม่สำเร็จ" + (f" ({s.rec['run_error']})" if s.rec.get("run_error") else "")
                         + " — กด \"ลองเทียบอีกครั้ง\"")
    v = pdfpair.view(rid)
    if v is None:
        raise TrialError("ไม่พบรอบเทียบของรอบตรวจนี้")
    if s.read_only_legacy:
        return LegacyResult(s, v, trial_repo.links(sid), trial_repo.extras(sid), trial_repo.answers(sid))
    decl = trial_repo.declaration(sid)
    if decl is None:
        raise TrialError("ไม่พบใบประกาศของรอบนี้")
    return Result(s, v, decl, trial_repo.issue_decisions(sid), trial_repo.issue_links(sid), trial_repo.proposals(sid),
                  trial_repo.finding_groups(sid), trial_repo.answers(sid), trial_repo.post_notes(sid),
                  trial_repo.history(sid))


def _need_result(sid: str) -> Result:
    r = result(sid)
    if r.legacy:
        raise TrialError("รอบกติกา 0.1 อ่านได้อย่างเดียว — ถ้าจะนับตามฉบับ 0.2 ให้เริ่มรอบใหม่")
    if not r.s.active:
        raise TrialError("รอบนี้หยุดหรือถอนตัวแล้ว — บันทึกเพิ่มไม่ได้ (ข้อมูลเดิมเก็บไว้ตามเดิม)")
    return r


def decide_issue(sid: str, mid: str, verdict: str, finding_ids=(), *, reason: str = "", evidence: str = "",
                 basis: str = "", change_reason: str = "", location: str = "", relevant_sides=(),
                 search_scope: str = "") -> None:
    """ผลการจับคู่ของประเด็น (วิธีวัดผล หมวด 5) — พบตรง/พบบางส่วนต้องเลือกข้อสังเกตอย่างน้อย 1 ข้อ (ต้องตรวจหรือ
    ข้อมูลประกอบ · หลายข้อได้) + หลักฐานชี้ตำแหน่ง · บางส่วน = บ1–บ4 · พลาด = พ1–พ5 · ทุกผลต้องมีฐานการวินิจฉัย ·
    เปลี่ยนผลเดิมต้องมีเหตุผล (เก็บประวัติ)"""
    r = _need_result(sid)
    m = r.issue_by_id.get(mid)
    if m is None:
        raise TrialError("ไม่พบประเด็นที่ระบุ")
    if verdict not in VERDICTS:
        raise TrialError("เลือกผลการจับคู่")
    fids = [str(x) for x in dict.fromkeys(finding_ids or []) if str(x)]
    if verdict in ("exact", "partial"):
        if not fids:
            raise TrialError("เลือกข้อสังเกตของระบบที่ตรงกับประเด็นนี้อย่างน้อย 1 ข้อ")
        bad = [f for f in fids if f not in r.matchable_ids]
        if bad:
            raise TrialError("ข้อสังเกตที่เลือกจับคู่ไม่ได้ (ไม่มีในรอบนี้ · เป็นส่วนที่ระบบอ่านหรือสกัดไม่ได้ · "
                             "หรือไม่ใช่เชิงโครงสร้างของคู่ข้ามปี) — " + P1_HINT)
        if r.s.v03:                      # 0.3: ตำแหน่งเป็นขั้นแยก ตัดสินหลังผลจับคู่ (ไม่ใช่เงื่อนไขของพบตรง)
            sides = [x for x in (relevant_sides or []) if x]
            bad_loc = agg.location_errors(location, sides, search_scope)
            if bad_loc:
                raise TrialError("สถานะตำแหน่ง (A2) ยังไม่ครบ: " + " · ".join(bad_loc))
            evidence = ""
        elif evidence not in EVIDENCE:
            raise TrialError("เลือกหลักฐานชี้ตำแหน่ง (ถูกทุกฉบับ / ถูกบางฉบับ / ไม่ถูก)")
    else:
        fids, evidence = [], ""
    if not (r.s.v03 and verdict in ("exact", "partial")):
        location, relevant_sides, search_scope = "", (), ""
    if verdict == "partial" and reason not in (PARTIAL_REASONS_V03 if r.s.v03 else PARTIAL_REASONS):
        raise TrialError("พบบางส่วน — เลือกรหัสเหตุ " + ("บ1–บ3 (ตำแหน่งใกล้เคียงบันทึกที่สถานะตำแหน่ง)"
                                                          if r.s.v03 else "บ1–บ4"))
    if verdict == "missed" and reason not in MISS_REASONS:
        raise TrialError("พลาด — เลือกรหัสเหตุ พ1–พ5")
    if verdict in ("exact", "undecidable"):
        reason = ""
    if basis not in BASIS:
        raise TrialError("เลือกฐานการวินิจฉัย (หลักฐานในระบบพอ / ต้องเปิดเอกสาร / วินิจฉัยไม่ได้)")
    new = {"verdict": verdict, "reason": reason, "evidence": evidence, "basis": basis, "location": location,
           "relevant_sides": ",".join(x for x in (relevant_sides or []) if x),
           "search_scope": (search_scope or "").strip()[:200]}
    prev = r.decisions.get(mid)
    changed = prev is not None and ({k: prev.get(k, "") for k in new} != new
                                    or sorted(r.links.get(mid, [])) != sorted(fids))
    if changed and not (change_reason or "").strip():
        raise TrialError("เปลี่ยนคู่หรือผลเดิม ต้องระบุเหตุผล (เก็บไว้ในประวัติ)")
    if prev is not None and not changed:
        return
    _repo(trial_repo.decide_issue, sid, mid, new, fids, (change_reason or "").strip())


def decide_obs(sid: str, fid: str, fidelity: str, *, fidelity_reason: str = "", dims: dict | None = None,
               assertion_undecidable: bool = False, basis: str = "", change_reason: str = "") -> None:
    """A3-อ ความตรงของสิ่งที่อ่านได้ + A3-ข ความถูกของข้อสรุปที่ข้อสังเกตอ้าง (ฉบับ 0.3) — ทุกข้อใน U ·
    ตัดสินจากภาพหน้าเอกสาร · มิติที่ไม่ใช้ = N/A พร้อมเหตุ (ไม่ตัดออกจาก U และไม่ถือว่าไม่ถูก) ·
    คำเตือนจับคู่ไม่แน่ชัด ≠ "คนละรายการแน่นอน" · เปลี่ยนค่าเดิมต้องมีเหตุผล"""
    r = _need_result(sid)
    if not r.s.v03:
        raise TrialError("รอบนี้นับตามฉบับ 0.2 — ไม่มีการประเมิน A3-อ/A3-ข")
    f = r.by_id.get(fid)
    if f is None or not r.obs_evaluable(fid):
        raise TrialError("ประเมินได้เฉพาะข้อสังเกตต้องตรวจในส่วนที่ตรวจครบ (U)")
    if fidelity not in FIDELITY:
        raise TrialError("เลือกความตรงของสิ่งที่อ่านได้ (A3-อ)")
    if fidelity in ("partial", "none"):
        if fidelity_reason not in FIDELITY_REASONS:
            raise TrialError("ความตรงไม่ครบ — เลือกเหตุ (อ่านผิด · หน่วยหรือสเกลผิด · ปัดเศษ · ปีผิด)")
    else:
        fidelity_reason = ""
    if basis not in BASIS:
        raise TrialError("เลือกฐานการวินิจฉัย")
    want = DIMS_BY_OBS_KIND[obs_kind(f)]
    clean: dict = {}
    if not assertion_undecidable:
        dims = dims or {}
        for d in want:
            v = str(dims.get(d, "") or "")
            if v not in DIM_VALUES:
                raise TrialError(f"A3-ข: ตัดสินมิติ \"{DIMS[d]}\" (ถูก / ไม่ถูก / N/A)")
            clean[d] = v
            if v == "na":
                why = str(dims.get(f"{d}_na", "") or "").strip()
                if not why:
                    raise TrialError(f"A3-ข: มิติ \"{DIMS[d]}\" เป็น N/A ต้องระบุเหตุ")
                clean[f"{d}_na"] = why[:120]
    assertion = agg.assertion_from_dims({d: clean[d] for d in want}, assertion_undecidable) \
        if not assertion_undecidable else "undecidable"
    new = {"fidelity": fidelity, "fidelity_reason": fidelity_reason, "dims": clean, "assertion": assertion,
           "basis": basis}
    prev = r.obs_eval.get(fid)
    if prev is not None and {k: prev.get(k) for k in new} == new:
        return
    if prev is not None and not (change_reason or "").strip():
        raise TrialError("เปลี่ยนผลประเมินเดิม ต้องระบุเหตุผล (เก็บไว้ในประวัติ)")
    _repo(trial_repo.decide_obs, sid, fid, new, (change_reason or "").strip())


def decide_finding(sid: str, fid: str, group: str, *, s3_reason: str = "", basis: str = "", issue_ref: str = "",
                   change_reason: str = "", part: str = "", note: str = "") -> None:
    """กลุ่มของข้อสังเกตต้องตรวจที่ไม่ได้จับคู่ (วิธีวัดผล หมวด 6) — ส1–ส4 ตัดสินจากภาพหน้าเอกสาร (ต้องมีฐานการวินิจฉัย ·
    ส3 ต้องมีเหตุ) · "นอกส่วนที่ตรวจครบ" = นับจำนวนเท่านั้น · เปลี่ยนกลุ่มเดิมต้องมีเหตุผล"""
    r = _need_result(sid)
    if fid not in {f.id for f in r.unmatched_must}:
        raise TrialError("ข้อนี้จับคู่กับประเด็นแล้ว หรือไม่ใช่ข้อสังเกตต้องตรวจของรอบนี้")
    if group not in GROUPS:
        raise TrialError("เลือกกลุ่มของข้อสังเกต")
    if group == "s3" and s3_reason not in S3_REASONS:
        raise TrialError("ส3 ไม่ใช่ความต่าง — เลือกเหตุ")
    if group != "s3":
        s3_reason = ""
    if group in S_GROUPS:
        if basis not in BASIS:
            raise TrialError("เลือกฐานการวินิจฉัย (หลักฐานในระบบพอ / ต้องเปิดเอกสาร / วินิจฉัยไม่ได้)")
    else:
        basis = ""
    if group != "s2" or issue_ref not in r.issue_by_id:
        issue_ref = ""
    if group == "outside":
        # อ้างความครอบคลุมที่ล็อกไว้ก่อนเห็นผล + เหตุรายข้อ — ห้ามปรับส่วนที่ถือว่าตรวจครบตามผลระบบ (รีวิวโบ 6414605109 ข้อ 3)
        cov = r.decl["body"]["parts"]
        if part not in PART_LABELS or cov.get(part) == "full":
            raise TrialError("นอกส่วนที่ตรวจครบ — เลือกส่วนของเล่มที่ใบประกาศระบุว่าตรวจบางส่วนหรือไม่ได้ตรวจ")
        if not (note or "").strip():
            raise TrialError("นอกส่วนที่ตรวจครบ — ระบุเหตุสั้น ๆ ของข้อนี้")
    else:
        part, note = "", ""
    new = {"grp": group, "s3_reason": s3_reason, "basis": basis, "issue_ref": issue_ref, "part": part,
           "note": (note or "").strip()[:200]}
    prev = r.groups.get(fid)
    changed = prev is not None and {k: prev.get(k, "") for k in new} != new
    if changed and not (change_reason or "").strip():
        raise TrialError("เปลี่ยนกลุ่มเดิม ต้องระบุเหตุผล (เก็บไว้ในประวัติ)")
    if prev is not None and not changed:
        return
    _repo(trial_repo.decide_finding, sid, fid, new, (change_reason or "").strip())


def add_post_note(sid: str, part: str = "", topic: str = "", note: str = "") -> None:
    """ข้อสังเกตหลังล็อก — ประเด็นที่เห็นเพิ่มหลังส่งใบประกาศ **ไม่เพิ่มเข้ารายการที่ล็อก** (นับจำนวนแยก)"""
    _need_result(sid)
    _check_fields(topic=topic, part=part, kind=session(sid).xkind)
    if not (note or "").strip() and not part and not topic:
        raise TrialError("ระบุส่วนของเล่ม หัวข้อ หรือลักษณะสั้น ๆ ของข้อสังเกต")
    _repo(trial_repo.add_post_note, sid, part or "", topic or "", (note or "").strip()[:300])


def finish_use(sid: str, reason: str = "") -> None:
    """จบการใช้ผล (เปิดแบบสอบถาม) — ยังจัดไม่ครบต้องระบุเหตุ (สถานะ "ไม่ครบ") · บันทึกงานที่ทำถึงตอนนั้น
    (การกดเป็นหลักฐานการกด ไม่ใช่หลักฐานว่าใช้ครบ — รีวิวโบ 6414605109 ข้อ 4)"""
    r = _need_result(sid)
    done = r.complete
    if not done and not (reason or "").strip():
        raise TrialError("ยังจับคู่หรือจัดกลุ่มไม่ครบ — ระบุเหตุที่จบการใช้ผลก่อนครบ")
    snap = {"complete": done, "issues_total": len(r.issues),
            "issues_done": sum(1 for m in r.issues if not r.gaps(m)),
            "findings_to_place": len(r.unmatched_must),
            "findings_placed": sum(1 for f in r.unmatched_must if not group_gaps(r.groups.get(f.id)))}
    _repo(trial_repo.finish_use, sid, "" if done else reason.strip(), done, snap)


def set_status(sid: str, status: str, reason: str = "", no_data_use: bool = False) -> None:
    """หยุดรอบนี้ (ระบุเหตุ) หรือถอนตัว (เลือกได้ว่าไม่ให้ใช้ข้อมูลที่ทำไว้) — หลังจากนี้บันทึกเพิ่มไม่ได้"""
    if session(sid) is None:
        raise TrialError("ไม่พบรอบตรวจ")
    if status not in STATUSES:
        raise TrialError("เลือกสถานะ")
    if status == "stopped" and not (reason or "").strip():
        raise TrialError("หยุดรอบนี้ — ระบุเหตุ")
    _repo(trial_repo.set_status, sid, status, (reason or "").strip(), bool(no_data_use) and status == "withdrawn")


def survey_state(s: Session) -> str:
    """``open`` · ``not_locked`` · ``no_run`` · ``in_use`` (ยังไม่จบการใช้ผล) · ``closed`` (หยุด/ถอนตัว) · ``legacy``"""
    if s.read_only_legacy:
        return "legacy"
    if not s.active:
        return "closed"
    if not s.locked:
        return "not_locked"
    if not s.rec["run_id"]:
        return "no_run"
    return "open" if s.rec.get("use_done_at") else "in_use"


SURVEY_STATE_TEXT = {"not_locked": "แบบสอบถามเปิดได้หลังส่งใบประกาศและได้ใช้ผลของระบบแล้ว",
                     "no_run": "ระบบยังเทียบไม่สำเร็จ — ยังไม่มีผลให้ใช้",
                     "in_use": "แบบสอบถามเปิดได้หลังใช้ผลของระบบแล้ว — จับคู่และจัดกลุ่มให้ครบ หรือกด \"จบการใช้ผล\" ก่อน",
                     "closed": "รอบนี้หยุดหรือถอนตัวแล้ว", "legacy": "รอบกติกา 0.1 — คำตอบเดิมอ่านได้อย่างเดียว"}


def save_answers(sid: str, form: dict) -> None:
    """แบบสอบถามหลังใช้ผล (แบบ 03 ฉบับ 0.2) — เปิดได้หลังจบการใช้ผล · ความยินยอมให้ไว้ก่อนเริ่มรอบแล้ว"""
    s = _need(sid, unlocked=False)
    st = survey_state(s)
    if st != "open":
        raise TrialError(SURVEY_STATE_TEXT[st])
    get = lambda k: str(form.get(k, "") or "").strip()     # noqa: E731
    vals = {}
    for k, _t in STEPS:
        if get(k):
            if get(k) not in STEP_CHOICES:
                raise TrialError("คำตอบขั้นตอนไม่ถูกต้อง")
            vals[k] = get(k)
    for _g, items in likert_items(s):
        for k, _t in items:
            if get(k):
                if get(k) not in ("1", "2", "3", "4", "5"):
                    raise TrialError("คำตอบต้องเป็น 1–5")
                vals[k] = get(k)
    for k, _t in OPEN_ITEMS:
        if get(k):
            vals[k] = get(k)[:2000]
    for k, _t, choices in GENERAL_ITEMS:
        if get(k):
            if get(k) not in choices:
                raise TrialError("ข้อมูลทั่วไปไม่ถูกต้อง")
            vals[k] = get(k)
    if not vals:
        raise TrialError("ยังไม่ได้ตอบข้อใด")
    _repo(trial_repo.answer, sid, vals)


# ── สถานะ · สรุป ─────────────────────────────────────────────────────────────────
def _when(v: str):
    try:
        return dt.datetime.fromisoformat(v) if v else None
    except ValueError:
        return None


def status_of(s: Session, r=None) -> dict:
    """สถานะที่ต้องรายงาน (วิธีวัดผล หมวด 8) — การรัน · ผู้ตรวจ · เหตุคัดออกจากผลหลัก · ธงที่ต้องรายงาน"""
    if s.status == "stopped":
        run = "stopped"
    elif s.rec["run_id"]:
        run = "ok"
    elif s.rec.get("run_error"):
        run = "failed"
    else:
        run = "pending" if s.locked else "not_started"
    if s.status:
        reviewer = s.status
    elif r is not None and not r.legacy and r.complete and s.rec.get("use_done_at"):
        reviewer = "complete"
    else:
        reviewer = "in_progress"
    decl = trial_repo.declaration(s.sid) if s.locked and not s.read_only_legacy else None
    exclusions, flags = [], []
    if s.read_only_legacy:
        exclusions.append("legacy_protocol")
    if decl and decl["body"].get("made") == "after":
        exclusions.append("list_after_results")
    locked_at, released = _when(s.rec["locked_at"]), _when(s.rec.get("released_at", ""))
    if locked_at and released and not released > locked_at:
        exclusions.append("order")
    if decl and decl["body"].get("seen") == "seen":
        flags.append("seen_before")
    if decl and not decl["body"].get("own_copy"):
        flags.append("list_integrity_unverifiable")
    if r is not None and not r.legacy and r.of_level("review"):
        flags.append("xyear_review_needed")
    if s.rec.get("prior_release"):
        flags.append("prior_release_on_machine")
    if s.rec.get("run_failures"):
        flags.append("run_failures")
    if r is not None and not r.legacy:
        if r.metrics["A4"]["unread_pages"]["prev"] or r.metrics["A4"]["unread_pages"]["cur"]:
            flags.append("scope_incomplete")
        if r.declaration_check:
            flags.append("declaration_mismatch")
    return {"run": run, "run_failures": int(s.rec.get("run_failures") or 0), "reviewer": reviewer,
            "excluded_main": bool(exclusions), "exclusions": exclusions, "flags": flags,
            "no_data_use": bool(s.rec.get("no_data_use"))}


STATUS_TEXT = {"run": {"ok": "สำเร็จ", "failed": "ล้มเหลว (ข้อผิดพลาดของระบบ)", "stopped": "หยุด",
                       "pending": "ยังไม่ได้เทียบ", "not_started": "ยังไม่ส่งใบประกาศ"},
               "reviewer": {"complete": "เข้าร่วมครบ", "in_progress": "กำลังทำ", "withdrawn": "ถอนตัว",
                            "stopped": "หยุดรอบนี้"},
               "exclusions": {"legacy_protocol": "รอบกติกา 0.1", "list_after_results": "รายการทำหลังเห็นผล/ไม่แน่ใจ",
                              "order": "ลำดับขั้นผิด (ปล่อยผลก่อนรับใบประกาศ)"},
               "flags": {"seen_before": "ผู้ตรวจเคยเห็นผลของระบบกับคู่นี้มาก่อน",
                         "prior_release_on_machine": "มีรอบก่อนหน้าของเล่มนี้ที่เปิดผลแล้วบนเครื่องนี้",
                         "run_failures": "เคยเทียบไม่สำเร็จ", "scope_incomplete": "ระบบอ่านขอบเขตได้ไม่ครบ (มีหน้าที่อ่านไม่ได้)",
                         "declaration_mismatch": "จำนวนต้นเหตุ/แดงในแถวไม่ตรงกับใบประกาศ",
                         "xyear_review_needed": "คู่ข้ามปี: มีข้อสังเกตที่กติกาไม่รู้จัก หรือรุ่นตัวเทียบไม่ตรงกติกา — "
                                                "ต้องทบทวนก่อน สรุปผลครบไม่ได้",
                         "list_integrity_unverifiable": "ไม่มีหลักฐานเนื้อหารายการฉบับล็อก — ตรวจความคงเดิมไม่ได้ "
                                                        "(จำนวนที่ตรงกันใช้แทนหลักฐานไม่ได้)"}}


def summary(sid: str) -> dict:
    """สรุปที่ส่งให้ผู้ศึกษา — **จำนวนเท่านั้น** (ไม่มีตำแหน่ง หมายเหตุ เลขอ้างอิงของผู้ตรวจ หรือข้อความเหตุผล) +
    คำตอบแบบสอบถาม (แบบ 03) · ถอนตัวและไม่ให้ใช้ข้อมูล = มีเฉพาะสถานะ · บัญชีไม่ปิดเพราะข้อมูลไม่สอดคล้อง = ส่งออกไม่ได้"""
    s = _need(sid, unlocked=False, active=False)
    if not s.locked:
        raise TrialError("ต้องส่งใบประกาศก่อน ระบบจึงเทียบให้ดู")
    b = s.book
    base = {"trial_version": s.rec.get("trial_version") or ("trial-0.1.0" if s.read_only_legacy else TRIAL_VERSION),
            "protocol": s.protocol, "session": sid, "reviewer_code": s.rec["reviewer"], "path": s.path,
            "pair_kind": s.pair_kind, "edition_labels": s.labels}
    if s.rec.get("no_data_use"):
        return {**base, "status": status_of(s), "note": "ผู้ตรวจถอนตัวและขอไม่ให้ใช้ข้อมูล — ไม่มีจำนวนหรือคำตอบ"}
    r = result(sid)
    vs = trial_repo.views(sid)
    out = {**base,
           "views": {"page_pairs_opened": len({(v["cur_page"], v["prev_page"]) for v in vs}),
                     "with_previous": sum(1 for v in vs if v["prev_page"]), "events": len(vs)},
           "book": {"title": b["title"], "agency": b["agency"], "pair": b["pair"],
                    "current_sha256": b["cur"]["sha256"], "previous_sha256": b["prev"]["sha256"]},
           "system": {"run_id": r.view.rid, "versions": r.view.run["versions"], "pdfbook": PDFBOOK_VERSION,
                      "profile": prof.PROFILE_VERSION, "profile_status": prof.PROFILE_STATUS},
           "timeline": {"started_at": s.rec["started_at"], "declared_at": s.rec["locked_at"],
                        "released_at": s.rec.get("released_at", ""), "use_done_at": s.rec.get("use_done_at", ""),
                        "consent_at": s.rec.get("consent_at", "")},
           "locked_at": s.rec["locked_at"], "complete": r.complete, "metrics": r.metrics,
           "status": status_of(s, r)}
    if r.legacy:
        out["answers"] = r.answers
        return out
    body = r.decl["body"]
    out["declaration"] = {"hash": r.decl["hash"], "received_at": r.decl["received_at"], "made_on": body["made_on"],
                          "source": body["source"], "made": body["made"], "seen": body["seen"],
                          "editions": body["editions"], "parts": body["parts"], "topics": body["topics"]}
    out["declaration_check"] = r.declaration_check
    snap = json.loads(s.rec["use_done_json"]) if s.rec.get("use_done_json") else {}
    out["use"] = {"done": bool(s.rec.get("use_done_at")), "complete_at_finish": not s.rec.get("use_done_reason"),
                  "at_finish": snap}
    out["declaration"]["own_copy_recorded"] = bool(body.get("own_copy"))
    # สำเนา/แฮชเป็นการประกาศของผู้ตรวจ ระบบไม่ได้ตรวจเนื้อหา · ไม่มี = ตรวจความคงเดิมของรายการไม่ได้ (รีวิวโบ 6417479593)
    out["declaration"]["list_integrity"] = ("declared_by_reviewer_not_verified" if body.get("own_copy")
                                            else "not_verifiable")
    a = r.answers
    out["survey"] = {"consent_given": bool(s.rec.get("consent_at")),
                     "steps": {k: a.get(k, "") for k, _t in STEPS},
                     "likert": {k: a.get(k, "") for _g, items in likert_items(s) for k, _t in items},
                     "likert_groups": {g: [k for k, _t in items] for g, items in likert_items(s)},
                     "open": {k: a.get(k, "") for k, _t in OPEN_ITEMS},
                     "general": {k: a.get(k, "") for k, _t, _c in GENERAL_ITEMS}}
    return out


def summary_bytes(sid: str) -> bytes:
    data = json.dumps(summary(sid), ensure_ascii=False, indent=2).encode("utf-8")
    from ..storage import audit
    audit.record("trial_summary_exported", "trial_session", sid,
                 {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    return data


__all__ = ["TrialError", "LedgerError", "TrialBook", "books", "get_book", "book_status", "start", "session",
           "page_png", "set_path", "add_mark", "update_mark", "update_row", "page_done", "page_undone", "log_view",
           "declaration_defaults", "mark_gaps", "lock", "ensure_run", "retry_run", "finding_level", "result",
           "decide_issue", "decide_finding", "add_post_note", "finish_use", "set_status", "survey_state",
           "save_answers", "give_consent", "status_of", "summary", "summary_bytes", "side_labels", "PATHS", "PENS", "LEVELS",
           "CAUSES", "TOPIC_CODES", "TOPIC_LABELS", "PARTS", "PART_LABELS", "COVERAGE", "SOURCES", "MADE", "SEEN",
           "VERDICTS", "PARTIAL_REASONS", "MISS_REASONS", "EVIDENCE", "BASIS", "GROUPS", "S3_REASONS",
           "FINDING_LEVELS", "LEVEL_DEFINITION", "XYEAR_RULE", "XYEAR_TOPICS", "XYEAR_SCOPE_LABEL", "KIND_LABELS",
           "is_structural", "classify", "level_and_reason", "XTYPES", "XTYPE_BY_TOPIC", "XYEAR_ENGINE", "XYEAR_ENGINES", "topic_codes", "system_topic", "READ_PROBLEMS", "P1_HINT", "read_problem", "STATUSES", "ROW_SOURCES", "POST_DIMS", "CONSENT_ITEMS", "STEPS", "STEP_CHOICES",
           "LIKERT_ITEMS", "OPEN_ITEMS", "GENERAL_ITEMS", "LIKERT_ITEMS_V03", "LIKERT_SCALE_V03", "likert_items",
           "PARTIAL_REASONS_V03", "LOCATIONS", "FIDELITY", "FIDELITY_REASONS", "ASSERTION", "DIM_VALUES",
           "DIMS", "OBS_KINDS", "DIMS_BY_OBS_KIND", "obs_kind", "decide_obs"]
