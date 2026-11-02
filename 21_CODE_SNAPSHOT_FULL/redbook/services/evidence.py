# -*- coding: utf-8 -*-
"""ชั้นบริการ — หลักฐาน PDF เก่า/ใหม่ + ทะเบียนตัวชี้วัด + ชุดตรวจเฉลยของกิ๊ฟ

route ห้าม import ``redbook.evidence.*`` / ``redbook.indicators.*`` ตรง ๆ
(เทสต์บังคับ · แบบเดียวกับ ``services/t1b.py``) · ชั้นนี้ห้าม import fastapi/jinja2

**สิ่งที่ชั้นนี้รับประกัน (มีเทสต์)**

* ไม่มี view/dict ใดที่ส่งไป template มีเส้นทางไฟล์จริง — เอกสารถูกอ้างด้วย
  ``document_id`` เท่านั้น และ URL ทุกตัวเป็น **route ภายในแอป** (ไม่มี ``file://``)
* URL ไม่มีข้อความจากเอกสาร — มีเฉพาะ id · หน้า · กรอบตัวเลข
* หน้าตรวจเฉลย/ชุดตรวจ **ไม่มีคะแนนของเครื่อง** (``internal_score`` และค่าตัวเลข
  ใน basis ถูกถอดออกก่อนส่งให้ view)
* ข้อความจากเอกสารที่ **ยังไม่เผยแพร่** ไม่ออกไปในไฟล์ส่งออก (แทนด้วยตัวยึด)

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .. import privacy
from ..evidence import documents as docs
from ..evidence import pdftext
from ..export import csv_safe
from ..indicators import keyuniverse as ku
from ..indicators import mapping as mp
from ..indicators import normalize as nz
from ..indicators import observe as ob
from ..indicators import registry as reg
from ..indicators import sourceinventory as sinv
from ..storage import audit

log = logging.getLogger("redbook")

EVIDENCE_SERVICE_VERSION = "evidence-service-0.2.0"

#: สถานะตำแหน่งที่ต้องให้คนชี้ (คำสั่งกิ๊ฟ §3)
LOCATION_REVIEW_REQUIRED = "LOCATION_REVIEW_REQUIRED"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
#: B5 — เปิดหลักฐานโดยไม่ระบุรอบ ⇒ ไม่แสดง indicator id ที่ผูกกับรอบ
RUN_CONTEXT_MISSING = "RUN_CONTEXT_MISSING"
#: B5 — ข้อสังเกตที่อ้างไม่ได้อยู่ในรอบ/เอกสารที่ระบุ
RUN_CONTEXT_MISMATCH = "RUN_CONTEXT_MISMATCH"
#: B4 — ขั้นตัดสินหลังรันยังไม่เปิด เพราะเฉลยยังไม่ถูกผนึก
ADJUDICATION_LOCKED = "ADJUDICATION_LOCKED_KEY_OR_DETECTOR_NOT_SEALED"

STAGE_KEY_BUILD = "KEY_BUILD_VERIFY"
STAGE_ADJUDICATION = "POST_RUN_ADJUDICATION"
STAGE_LABELS_TH = {
    STAGE_KEY_BUILD: "ขั้นจัดทำ/ยืนยันเฉลย (ไม่แสดงผลของเครื่อง)",
    STAGE_ADJUDICATION: "ขั้นตัดสินหลังรัน (แสดงสิ่งที่เครื่องเสนอได้)",
}

#: ตัวยึดแทนข้อความจากเอกสารที่เผยแพร่ไม่ได้ — ใช้ในไฟล์ส่งออกเท่านั้น
UNPUBLISHED_PLACEHOLDER = "[ข้อความจากเอกสารที่ยังไม่เผยแพร่ — เปิดดูได้ในระบบเท่านั้น]"

MANDATORY_NOTICE = "ระบบเสนอสิ่งที่ตรวจพบ ผู้ปฏิบัติงานเป็นผู้ตัดสิน"
PACKAGE_TITLE = "ชุดตัดสินหลังรัน — การจับคู่ตัวชี้วัด (POST-RUN ADJUDICATION PACKAGE)"
PACKAGE_NOTICE = ("ชุดนี้ไม่มีคะแนนของเครื่องโดยเจตนา — ผู้ตรวจตัดสินจากข้อความและหลักฐาน "
                  "ทั้งสองฉบับเท่านั้น · 🔴 ชุดนี้เป็น POST-RUN ADJUDICATION "
                  "ห้ามใช้สร้างหรือยืนยันเฉลยที่ปิดผนึก (ใช้หน้า KEY BUILD/VERIFY แทน)")
KEY_BUILD_TITLE = "ชุดจัดทำ/ยืนยันเฉลย (KEY BUILD / VERIFY) — ไม่มีผลของเครื่อง"
KEY_BUILD_NOTICE = ("หน้านี้ไม่แสดงสถานะที่เครื่องเสนอ เหตุผลของเครื่อง หรือคะแนนใด ๆ "
                    "ผู้จัดทำเฉลยตัดสินจากข้อความและหลักฐานสองฝั่งเท่านั้น")

_SCORE_BASIS = re.compile(r"^(trigram_dice)=.*$")
_BASIS_PUBLIC = {
    "exact_text_equal": "ข้อความตรงกันทุกอักขระ",
    "normalized_text_equal": "ตรงกันหลังตัดช่องว่าง/เครื่องหมาย/เลขไทย",
    "trigram_dice": "ข้อความคล้ายกันเชิงอักขระ",
    "fields_agree": "หน่วย/ค่าเป้าหมาย/วิธี/รอบ ไม่ต่างกัน",
    "competing_candidates": "มีคู่แข่งหลายตัว",
    "below_rephrase_threshold": "คล้ายไม่พอที่จะเสนอว่าเป็นตัวเดียวกัน",
    "no_candidate_in_new": "ไม่พบข้อความใกล้เคียงในฉบับใหม่",
    "no_candidate_in_old": "ไม่พบข้อความใกล้เคียงในฉบับเก่า",
    "unit_differs": "หน่วยต่างกัน",
    "target_value_differs": "ค่าเป้าหมายต่างกัน",
    "method_text_differs": "วิธีคำนวณ/ตัวหาร/ขอบเขตต่างกัน",
    "period_text_differs": "รอบรายงานต่างกัน",
    "baseline_text_differs": "ค่าฐานต่างกัน",
    "numeric_tokens_differs": "ตัวเลขในข้อความต่างกัน",
}

DIFF_LABELS = {
    "unit": "หน่วย", "target_value": "ค่าเป้าหมาย", "method_text": "วิธีคำนวณ/ตัวหาร",
    "period_text": "รอบรายงาน", "baseline_text": "ค่าฐาน", "numeric_tokens": "ตัวเลขในข้อความ",
}


def public_basis(basis) -> tuple[str, ...]:
    """ถอดค่าตัวเลขออกจาก basis — เหลือเฉพาะ *ชนิด* ของเหตุผล"""
    out: list[str] = []
    for b in basis:
        key = _SCORE_BASIS.sub(r"\1", b)
        if key.startswith("one_to_many"):
            out.append("ข้อความซ้ำกันในฉบับเดียวกัน (จับให้อัตโนมัติไม่ได้)")
            continue
        out.append(_BASIS_PUBLIC.get(key, key))
    return tuple(out)


# ── URL builders — route ภายในเท่านั้น ─────────────────────────────────────

def evidence_url(document_id: str, page: int, observation_id: str = "",
                 run_id: str = "") -> str:
    """B5 — ลิงก์หลักฐานต้องพก **run context** ไปด้วยเสมอเมื่อชี้ข้อสังเกตของรอบใด

    เดิมเป็น ``?page=&obs=`` แล้วชั้นบริการไล่หา observation ในทุกรอบและหยิบรอบแรกที่เจอ
    ⇒ เอกสาร/ข้อสังเกตเดียวกันที่อยู่หลายรอบอาจแสดง ``indicator_id``/binding ของคนละรอบ
    """
    u = f"/evidence/{document_id}?page={int(page)}"
    if run_id:
        u += f"&run={run_id}"
    return u + (f"&obs={observation_id}" if observation_id else "")


def file_url(document_id: str, page: int) -> str:
    return f"/evidence/{document_id}/file#page={int(page)}"


def compare_url(run_id: str, mapping_id: str) -> str:
    return f"/evidence/compare?run={run_id}&map={mapping_id}"


def page_image_url(document_id: str, page: int, bbox=None) -> str:
    u = f"/evidence/{document_id}/page/{int(page)}.png"
    if bbox:
        u += "?hl=" + ",".join(f"{float(v):.1f}" for v in bbox)
    return u


# ── ลงทะเบียนเอกสาร ─────────────────────────────────────────────────────────

def register_pdf(path, *, title: str, stage: str, fiscal_year: int | None,
                 authority: str, agency_label: str = "", version_label: str = "",
                 disclosure_class: str, registered_by: str = "",
                 db_path=None) -> docs.DocumentRecord:
    """ลงทะเบียน PDF ด้วย content hash — ตรวจชั้นข้อความถ้ามี backend"""
    backend = pdftext.product_backend()
    page_count = None
    tl_status = pdftext.TEXT_LAYER_NOT_CHECKED
    backend_name = pdftext.NO_TEXT_BACKEND
    if backend is not None:
        pages = backend.pages(path)
        page_count = len(pages)
        tl_status = pdftext.text_layer_status(pages)
        backend_name = f"{backend.name} {backend.version}"
    rec, created = docs.register(
        path, media_type=docs.MEDIA_PDF, title=title, stage=stage,
        fiscal_year=fiscal_year, authority=authority, agency_label=agency_label,
        version_label=version_label, disclosure_class=disclosure_class,
        page_count=page_count, text_layer_status=tl_status,
        text_backend=backend_name, registered_by=registered_by, db_path=db_path)
    if created:
        audit.record("evidence_document_registered", "evd_document", rec.document_id, {
            "content_sha256": rec.content_sha256, "byte_size": rec.byte_size,
            "page_count": rec.page_count, "stage": rec.stage,
            "fiscal_year": rec.fiscal_year, "disclosure_class": rec.disclosure_class,
            "text_layer_status": rec.text_layer_status}, db_path=db_path)
    return rec


# ── รันทะเบียนตัวชี้วัด ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    n_old: int
    n_new: int
    n_pairs: int
    accounted: dict
    by_status: dict
    text_backend: str


def run_indicator_pipeline(old_document_id: str, new_document_id: str, *,
                           note: str = "", label: str = "",
                           rules: mp.Rules = mp.Rules(), db_path=None) -> PipelineResult:
    old_doc = docs.get(old_document_id, db_path)
    new_doc = docs.get(new_document_id, db_path)
    if old_doc is None or new_doc is None:
        raise ValueError("ไม่พบเอกสารที่ระบุในทะเบียน")
    if old_doc.document_id == new_doc.document_id:
        raise ValueError("เอกสารเก่าและใหม่เป็นไฟล์เดียวกัน (content hash เท่ากัน)")
    backend = pdftext.product_backend()
    if backend is None:
        # 🔴 P1-1 — fail-closed: ไม่หันไปใช้ backend วิจัย แม้ติดตั้งอยู่
        raise RuntimeError(pdftext.NO_TEXT_BACKEND)
    backend_evidence = pdftext.backend_report(mode=pdftext.MODE_PRODUCT)
    inventory: dict = {"backend": backend_evidence}
    sides: dict[str, list[ob.Observation]] = {}
    for side, d in (("old", old_doc), ("new", new_doc)):
        p = docs.open_path_private(d.document_id, db_path=db_path)
        pages = backend.pages(p)
        obs = ob.observe_document(d.document_id, d.content_sha256, pages)
        inv = ob.page_inventory(pages, obs)
        inventory[side] = {
            "pages": len(inv),
            "pages_without_text_layer": [r.page for r in inv if not r.text_layer],
            "observations": len(obs),
        }
        sides[side] = obs
    cands = mp.propose(sides["old"], sides["new"], rules)
    acc = mp.accounted(sides["old"], sides["new"], cands)
    run_id = "ind_" + uuid.uuid4().hex[:16]
    reg.save_run(run_id=run_id, old_document_id=old_doc.document_id,
                 new_document_id=new_doc.document_id, old_obs=sides["old"],
                 new_obs=sides["new"], candidates=cands, rules=rules,
                 extractor_version=ob.OBSERVE_VERSION,
                 normalize_version=nz.NORMALIZE_VERSION,
                 text_backend=f"{backend.name} {backend.version}", accounted=acc,
                 page_inventory=inventory, note=note, label=label, db_path=db_path)
    by_status: dict[str, int] = {}
    for c in cands:
        by_status[c.proposed_status] = by_status.get(c.proposed_status, 0) + 1
    # 🔴 ล็อกเฉพาะตัวเลขและ id — ไม่มีข้อความจากเอกสาร
    log.info("indicator_run run_id=%s old=%s new=%s n_old=%d n_new=%d pairs=%d closed=%s",
             run_id, old_doc.document_id, new_doc.document_id, len(sides["old"]),
             len(sides["new"]), len(cands), acc["closed"])
    audit.record("indicator_run_completed", "ind_run", run_id, {
        "old_document_id": old_doc.document_id, "new_document_id": new_doc.document_id,
        "n_old": len(sides["old"]), "n_new": len(sides["new"]), "n_pairs": len(cands),
        "by_status": by_status, "rules_hash": rules.rules_hash,
        "mapping_version": rules.version, "extractor_version": ob.OBSERVE_VERSION,
        "accounted_closed": acc["closed"], "accounted_failed_checks": acc["failed_checks"],
        "backend": backend_evidence}, db_path=db_path)
    return PipelineResult(run_id=run_id, n_old=len(sides["old"]), n_new=len(sides["new"]),
                          n_pairs=len(cands), accounted=acc, by_status=by_status,
                          text_backend=f"{backend.name} {backend.version}")


# ── มุมมอง ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SideView:
    """หนึ่งฝั่งของหลักฐาน — ไม่มีเส้นทางไฟล์"""
    document_id: str
    title: str
    stage: str
    stage_label: str
    fiscal_year: int | None
    version_label: str
    short_hash: str
    content_sha256: str
    disclosure_class: str
    disclosure_label: str
    shareable: bool
    page: int
    page_count: int | None
    observation_id: str
    observed_text: str
    normalized_text: str
    location_confidence: str
    location_label: str
    location_review_required: bool
    bbox: tuple | None
    unit: str
    target_text: str
    method_text: str
    period_text: str
    baseline_text: str
    indicator_id: str
    evidence_url: str
    open_url: str
    image_url: str
    source_status: str          # "" = ใช้ได้ · SOURCE_UNAVAILABLE:<reason>
    text_layer_status: str
    #: B5 — รอบที่ใช้ตีความ indicator id ของฝั่งนี้ ("" = ไม่ได้ระบุ)
    run_id: str = ""
    #: B5 — "" = ปกติ · RUN_CONTEXT_MISSING · RUN_CONTEXT_MISMATCH
    run_context_status: str = ""
    #: P1-2 — ธงเชิงเรขาคณิต/ที่มาของข้อสังเกต
    flags: tuple = ()
    flag_labels: tuple = ()

    @property
    def text_clipped(self) -> bool:
        return "TEXT_CLIPPED_AT_PAGE_EDGE" in self.flags


def _source_status(document_id: str, db_path=None) -> str:
    try:
        docs.open_path_private(document_id, db_path=db_path)
        return ""
    except docs.SourceUnavailable as e:
        return f"{SOURCE_UNAVAILABLE}:{e.reason}"


def _side(doc: docs.DocumentRecord, o: ob.Observation | None, page: int,
          indicator_id: str, db_path=None, *, run_id: str = "",
          run_context_status: str = "") -> SideView:
    loc = o.location_confidence if o else ob.LOC_PAGE_ONLY
    bbox = o.bbox if o else None
    review = (o is None) or (bbox is None) or (loc == ob.LOC_PAGE_ONLY)
    return SideView(
        document_id=doc.document_id, title=doc.title, stage=doc.stage,
        stage_label=doc.stage_label, fiscal_year=doc.fiscal_year,
        version_label=doc.version_label, short_hash=doc.short_hash,
        content_sha256=doc.content_sha256, disclosure_class=doc.disclosure_class,
        disclosure_label=doc.disclosure_label, shareable=doc.shareable,
        page=page, page_count=doc.page_count,
        observation_id=o.observation_id if o else "",
        observed_text=o.observed_text if o else "",
        normalized_text=o.normalized_text if o else "",
        location_confidence=loc, location_label=ob.LOCATION_LABELS.get(loc, loc),
        location_review_required=review, bbox=bbox,
        unit=o.unit if o else "", target_text=o.target_text if o else "",
        method_text=o.method_text if o else "", period_text=o.period_text if o else "",
        baseline_text=o.baseline_text if o else "", indicator_id=indicator_id,
        evidence_url=evidence_url(doc.document_id, page,
                                  o.observation_id if o else "", run_id),
        open_url=file_url(doc.document_id, page),
        image_url=page_image_url(doc.document_id, page, bbox),
        source_status=_source_status(doc.document_id, db_path),
        text_layer_status=doc.text_layer_status, run_id=run_id,
        run_context_status=run_context_status,
        flags=(tuple(o.geometry_flags) if o else ()),
        flag_labels=(tuple(o.flag_labels) if o else ()))


@dataclass(frozen=True)
class PageView:
    doc: docs.DocumentRecord
    aliases: tuple[str, ...]
    side: SideView
    can_render: bool
    backend: str


def page_view(document_id: str, page: int, observation_id: str = "",
              run_id: str = "", db_path=None) -> PageView | None:
    """B5 — ต้องระบุ ``run_id`` เมื่อชี้ข้อสังเกต มิฉะนั้นไม่แสดง indicator id ของรอบใด"""
    doc = docs.get(document_id, db_path)
    if doc is None:
        return None
    if page < 1 or (doc.page_count and page > doc.page_count):
        page = max(1, min(page, doc.page_count or 1))
    o = None
    ind = ""
    status = ""
    if observation_id:
        if not run_id:
            status = RUN_CONTEXT_MISSING
        else:
            o, ind, status = _find_observation(observation_id, document_id, run_id, db_path)
            if o is not None:
                page = o.page
    return PageView(doc=doc, aliases=tuple(docs.aliases(document_id, db_path)),
                    side=_side(doc, o, page, ind, db_path, run_id=run_id,
                               run_context_status=status),
                    can_render=pdftext.product_backend() is not None,
                    backend=pdftext.backend_name())


def _find_observation(observation_id: str, document_id: str, run_id: str,
                      db_path=None) -> tuple[ob.Observation | None, str, str]:
    """หา observation **ภายในรอบที่ระบุเท่านั้น** และต้องอยู่ในเอกสารที่ระบุ (B5)

    🔴 ไม่ไล่หาทุกรอบแล้วหยิบตัวแรกอีกต่อไป — ข้อสังเกตเดียวกันอยู่ได้หลายรอบ และ
    ``indicator_id``/binding ของแต่ละรอบมาจากคำตัดสินคนละชุด
    """
    if reg.get_run(run_id, db_path) is None:
        return None, "", RUN_CONTEXT_MISMATCH
    o = reg.observations(run_id, db_path).get(observation_id)
    if o is None or o.document_id != document_id:
        return None, "", RUN_CONTEXT_MISMATCH
    return o, reg.indicator_ids(run_id, db_path).get(observation_id, ""), ""


@dataclass(frozen=True)
class PairView:
    run_id: str
    mapping_id: str
    proposed_status: str
    proposed_label: str
    human_required: bool
    basis: tuple[str, ...]
    differences: tuple[dict, ...]
    alternatives: tuple[str, ...]
    old: SideView | None
    new: SideView | None
    decision: reg.DecisionRow | None
    current_status: str
    current_label: str
    compare_url: str
    indicator_id: str
    #: P1-2 — ฝั่งใดฝั่งหนึ่งมีข้อความชน/ล้นขอบหน้า ⇒ ห้ามยืนยันอัตโนมัติ
    clipped: bool = False

    @property
    def decided(self) -> bool:
        return self.decision is not None


def _pair(run: reg.RunRow, c: mp.Candidate, obs: dict, ids: dict, latest: dict,
          doc_cache: dict, db_path=None) -> PairView:
    def doc_of(did):
        if did not in doc_cache:
            doc_cache[did] = docs.get(did, db_path)
        return doc_cache[did]

    old = new = None
    if c.old_observation_id:
        o = obs.get(c.old_observation_id)
        old = _side(doc_of(run.old_document_id), o, o.page if o else 1,
                    ids.get(c.old_observation_id, ""), db_path, run_id=run.id)
    if c.new_observation_id:
        n = obs.get(c.new_observation_id)
        new = _side(doc_of(run.new_document_id), n, n.page if n else 1,
                    ids.get(c.new_observation_id, ""), db_path, run_id=run.id)
    d = latest.get(c.mapping_id)
    cur = d.final_status if d else c.proposed_status
    ind = (old.indicator_id if old else "") or (new.indicator_id if new else "")
    return PairView(
        run_id=run.id, mapping_id=c.mapping_id, proposed_status=c.proposed_status,
        proposed_label=c.status_label, human_required=c.human_required,
        clipped=bool((old and old.text_clipped) or (new and new.text_clipped)),
        basis=public_basis(c.basis),
        differences=tuple({"field": x.field_name,
                           "label": DIFF_LABELS.get(x.field_name, x.field_name),
                           "old": x.old, "new": x.new} for x in c.differences),
        alternatives=c.alternatives, old=old, new=new, decision=d,
        current_status=cur, current_label=mp.STATUS_LABELS.get(cur, cur),
        compare_url=compare_url(run.id, c.mapping_id), indicator_id=ind)


_STATUS_ORDER = {s: i for i, s in enumerate((
    mp.AMBIGUOUS_REVIEW_REQUIRED, mp.DEFINITION_CHANGED, mp.SAME_CONCEPT_REPHRASED,
    mp.RELATED_NOT_EQUIVALENT, mp.REMOVED_INDICATOR, mp.NEW_INDICATOR,
    mp.SAME_WORDING_VARIANT, mp.SAME_EXACT))}


@dataclass(frozen=True)
class RunView:
    run: reg.RunRow
    old_doc: docs.DocumentRecord
    new_doc: docs.DocumentRecord
    pairs: tuple[PairView, ...]
    by_proposed: dict
    by_current: dict
    pending_human: int
    decided: int
    #: B4 — เฉลยของรอบนี้ถูกผนึกหรือยัง
    key_seal: object = None
    #: B4 (Pass 3) — ผลลัพธ์ของ detector ถูกผนึกหรือยัง · ต้องผนึกทั้งคู่จึงเปิด adjudication
    detector_seal: object = None
    #: B2 — ข้อขัดแย้งเรื่องตัวตนที่ต้องให้คนตัดสิน (one-to-many ที่ถูกยืนยัน)
    identity_conflicts: tuple = ()
    #: P1-2 — จำนวนคู่ที่มีข้อความชน/ล้นขอบหน้า
    clipped_pairs: int = 0
    statuses: tuple = mp.STATUSES
    status_labels: dict = field(default_factory=lambda: dict(mp.STATUS_LABELS))
    human_required: frozenset = mp.HUMAN_REQUIRED


def run_view(run_id: str, db_path=None) -> RunView | None:
    run = reg.get_run(run_id, db_path)
    if run is None:
        return None
    obs = reg.observations(run_id, db_path)
    identity = reg.resolve_identity(run_id, db_path=db_path)
    ids = identity.ids
    latest = reg.latest_decisions(run_id, db_path)
    cache: dict = {}
    pairs = [_pair(run, c, obs, ids, latest, cache, db_path)
             for c in reg.mappings(run_id, db_path=db_path)]
    pairs.sort(key=lambda p: (0 if p.human_required and not p.decided else 1,
                              _STATUS_ORDER.get(p.proposed_status, 99),
                              (p.old.page if p.old else 0), (p.new.page if p.new else 0),
                              p.mapping_id))
    by_p: dict[str, int] = {s: 0 for s in mp.STATUSES}
    by_c: dict[str, int] = {s: 0 for s in mp.STATUSES}
    for p in pairs:
        by_p[p.proposed_status] += 1
        by_c[p.current_status] += 1
    return RunView(run=run, old_doc=cache.get(run.old_document_id) or docs.get(run.old_document_id, db_path),
                   new_doc=cache.get(run.new_document_id) or docs.get(run.new_document_id, db_path),
                   pairs=tuple(pairs), by_proposed=by_p, by_current=by_c,
                   pending_human=sum(1 for p in pairs if p.human_required and not p.decided),
                   decided=sum(1 for p in pairs if p.decided),
                   key_seal=reg.key_seal(run_id, db_path),
                   detector_seal=reg.detector_snapshot(run_id, db_path),
                   identity_conflicts=identity.conflicts,
                   clipped_pairs=sum(1 for p in pairs if p.clipped))


def pair_view(run_id: str, mapping_id: str, db_path=None) -> PairView | None:
    rv = run_view(run_id, db_path)
    if rv is None:
        return None
    for p in rv.pairs:
        if p.mapping_id == mapping_id:
            return p
    return None


def decide(run_id: str, mapping_id: str, *, decision: str, final_status: str,
           reason: str, reviewer: str, db_path=None) -> reg.DecisionRow:
    return reg.record_decision(run_id=run_id, mapping_id=mapping_id,
                               decision=decision, final_status=final_status,
                               reason=reason, reviewer=reviewer, db_path=db_path)


# ── ชุดตรวจของกิ๊ฟ (XLSX · ไม่มีคะแนน) ─────────────────────────────────────

PACKAGE_COLUMNS = (
    ("mapping_id", "mapping_id"),
    ("indicator_id", "indicator_id (ชั่วคราวจนกว่าจะยืนยัน)"),
    ("proposed_status", "สถานะที่เครื่องเสนอ"),
    ("proposed_label", "ความหมาย"),
    ("human_required", "ต้องให้คนยืนยัน"),
    ("basis", "เหตุผลที่เครื่องอ่านได้ (ไม่ใช่คะแนน)"),
    ("old_text", "ข้อความฉบับเก่า (ตรงตามที่ปรากฏ)"),
    ("new_text", "ข้อความฉบับใหม่ (ตรงตามที่ปรากฏ)"),
    ("old_stage", "ขั้นเอกสาร เก่า"),
    ("old_year", "ปี เก่า"),
    ("old_page", "หน้า เก่า"),
    ("old_location", "ตำแหน่ง เก่า"),
    ("old_hash", "แฮชเอกสาร เก่า"),
    ("new_stage", "ขั้นเอกสาร ใหม่"),
    ("new_year", "ปี ใหม่"),
    ("new_page", "หน้า ใหม่"),
    ("new_location", "ตำแหน่ง ใหม่"),
    ("new_hash", "แฮชเอกสาร ใหม่"),
    ("differences", "ความต่างของ นิยาม/หน่วย/วิธี/รอบ"),
    ("old_link", "เปิดหลักฐานเก่า (route ในระบบ)"),
    ("new_link", "เปิดหลักฐานใหม่ (route ในระบบ)"),
    ("compare_link", "เปิดเทียบข้างกัน (route ในระบบ)"),
    ("decision", "คำตัดสิน (ยอมรับ / ไม่ยอมรับ / ยังตัดสินไม่ได้)"),
    ("final_status", "สถานะที่ถูกต้อง (ถ้าไม่ยอมรับ)"),
    ("note", "หมายเหตุผู้ตรวจ"),
    ("reviewer", "ผู้ตรวจ"),
    ("decided_at", "เวลาที่ตัดสิน"),
)


def _txt(side: SideView | None) -> str:
    if side is None:
        return ""
    if not side.shareable:
        return UNPUBLISHED_PLACEHOLDER
    return side.observed_text


def _loc(side: SideView | None) -> str:
    if side is None:
        return ""
    if side.location_review_required:
        return LOCATION_REVIEW_REQUIRED
    return f"{side.location_confidence} {tuple(round(v, 1) for v in side.bbox)}"


def package_rows(rv: RunView) -> list[dict]:
    rows: list[dict] = []
    for p in rv.pairs:
        d = p.decision
        rows.append({
            "mapping_id": p.mapping_id, "indicator_id": p.indicator_id,
            "proposed_status": p.proposed_status, "proposed_label": p.proposed_label,
            "human_required": "ใช่" if p.human_required else "ไม่บังคับ",
            "basis": " · ".join(p.basis),
            "old_text": _txt(p.old), "new_text": _txt(p.new),
            "old_stage": p.old.stage_label if p.old else "",
            "old_year": p.old.fiscal_year if p.old else "",
            "old_page": p.old.page if p.old else "",
            "old_location": _loc(p.old), "old_hash": p.old.short_hash if p.old else "",
            "new_stage": p.new.stage_label if p.new else "",
            "new_year": p.new.fiscal_year if p.new else "",
            "new_page": p.new.page if p.new else "",
            "new_location": _loc(p.new), "new_hash": p.new.short_hash if p.new else "",
            "differences": "; ".join(f"{x['label']}: {x['old'] or '—'} → {x['new'] or '—'}"
                                     for x in p.differences),
            "old_link": p.old.evidence_url if p.old else "",
            "new_link": p.new.evidence_url if p.new else "",
            "compare_link": p.compare_url,
            "decision": d.decision_label if d else "",
            "final_status": d.final_status if d else "",
            "note": d.reason if d else "", "reviewer": d.reviewer if d else "",
            "decided_at": d.decided_at if d else "",
        })
    return rows


@dataclass(frozen=True)
class PackageFiles:
    package_id: str
    xlsx_path: Path
    snapshot_path: Path
    rows: int
    neutralized: int
    run_id: str = ""

    @property
    def xlsx_url(self) -> str:
        """ลิงก์ดาวน์โหลดแบบ **ระบุรอบ** — ตรวจผนึกใหม่ทุกครั้งก่อนส่งไฟล์ (P4-2)"""
        return export_url(self.run_id, self.xlsx_path.name)


def write_package(rv: RunView, out_dir, *, prepared_by: str = "",
                  db_path=None) -> PackageFiles:
    """เขียนชุด **ตัดสินหลังรัน** เป็น XLSX + snapshot — ตรวจก่อนเขียนว่าไม่มีเส้นทาง/คะแนน

    🔴 B4 — ชุดนี้แสดงสถานะที่เครื่องเสนอ จึงสร้างได้ **หลังเฉลยถูกผนึกแล้ว** เท่านั้น
    """
    if not adjudication_unlocked(rv.run.id, db_path):
        raise StageLockedError(ADJUDICATION_LOCKED)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pid = "indpkg_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:6]
    rows = package_rows(rv)
    neutralized = 0

    def cell(value, bold=False):
        nonlocal neutralized
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return ("n", value, bold)
        text, was_neutral, _, _ = csv_safe.neutralize(value)
        neutralized += int(was_neutral)
        return ("s", text, bold)

    head = [
        [cell(PACKAGE_TITLE, True)],
        [cell(MANDATORY_NOTICE)],
        [cell(PACKAGE_NOTICE)],
        [cell(f"run_id: {rv.run.id}"), cell(f"mapping rules: {rv.run.mapping_version} ({rv.run.rules_hash})")],
        [cell(f"เอกสารเก่า: {rv.old_doc.document_id} · {rv.old_doc.stage_label} · ปี {rv.old_doc.fiscal_year or '—'} · sha256 {rv.old_doc.content_sha256}")],
        [cell(f"เอกสารใหม่: {rv.new_doc.document_id} · {rv.new_doc.stage_label} · ปี {rv.new_doc.fiscal_year or '—'} · sha256 {rv.new_doc.content_sha256}")],
        [cell("ลิงก์ในชุดนี้เป็น route ของระบบบนเครื่องผู้ตรวจ — เปิดผ่านแอปเท่านั้น ไม่ใช่ลิงก์ไฟล์ในเครื่อง")],
        [],
        [cell(h, True) for _, h in PACKAGE_COLUMNS],
    ]
    body = [[cell(r[k]) for k, _ in PACKAGE_COLUMNS] for r in rows]
    readme = [
        [cell("วิธีใช้ชุดตรวจ", True)],
        [cell("1. เปิดลิงก์หลักฐานเก่า/ใหม่ หรือลิงก์เทียบข้างกัน จากในระบบ (คอลัมน์ลิงก์)")],
        [cell("2. เทียบข้อความสองฉบับตามที่ปรากฏ และความต่างของ นิยาม/หน่วย/วิธี/รอบ")],
        [cell("3. กรอกคำตัดสิน: ยอมรับ · ไม่ยอมรับ (ระบุสถานะที่ถูกต้อง) · ยังตัดสินไม่ได้")],
        [cell("4. สถานะ SAME_CONCEPT_REPHRASED · RELATED_NOT_EQUIVALENT · DEFINITION_CHANGED · AMBIGUOUS_REVIEW_REQUIRED ต้องมีเหตุผล")],
        [cell("5. ตำแหน่ง LOCATION_REVIEW_REQUIRED = ระบบชี้ได้เฉพาะหน้า ผู้ตรวจต้องชี้ตำแหน่งเอง")],
        [],
        [cell("สถานะทั้ง 8", True)],
    ] + [[cell(s), cell(mp.STATUS_LABELS[s]), cell("ต้องให้คนยืนยัน" if s in mp.HUMAN_REQUIRED else "")]
         for s in mp.STATUSES]
    summary = [[cell("จำนวนคู่ตามสถานะที่เครื่องเสนอ", True)]] + \
        [[cell(f"{s} — {mp.STATUS_LABELS[s]}"), cell(n)] for s, n in rv.by_proposed.items()] + \
        [[], [cell("รอคนยืนยัน"), cell(rv.pending_human)], [cell("ตัดสินแล้ว"), cell(rv.decided)],
         [cell("บัญชีปิด (ทุกข้อสังเกตมีแถว)"), cell("ใช่" if rv.run.accounted.get("closed") else "ไม่")]]
    sheets = [("ชุดตรวจ", head + body), ("วิธีใช้", readme), ("สรุป", summary)]

    all_text = "\n".join(str(c[1]) for _, rs in sheets for row in rs for c in row)
    privacy.assert_shareable(all_text, where="Gift Verification Package")
    for token in ("internal_score", "trigram_dice=", "file://"):
        if token in all_text:
            raise ValueError(f"ชุดตรวจมีสิ่งต้องห้าม: {token}")

    xlsx_path = out / f"{pid}.xlsx"
    import importlib
    importlib.import_module("exporters.xlsx_writer").write_xlsx(xlsx_path, sheets)
    snap = out / f"{pid}_snapshot.json"
    snap.write_text(json.dumps({
        "package_id": pid, "run_id": rv.run.id, "prepared_by": prepared_by,
        "rows": len(rows), "by_proposed": rv.by_proposed,
        "old_document_id": rv.old_doc.document_id, "new_document_id": rv.new_doc.document_id,
        "old_sha256": rv.old_doc.content_sha256, "new_sha256": rv.new_doc.content_sha256,
        "mapping_version": rv.run.mapping_version, "rules_hash": rv.run.rules_hash,
        "extractor_version": rv.run.extractor_version, "service_version": EVIDENCE_SERVICE_VERSION,
        "scores_included": False, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    # 🔴 P4-2 — ผูกทุกไฟล์กับรอบและ digest ของผนึกสามชั้นที่ตรวจผ่าน ณ ตอนนี้
    # ถ้าผูกไม่สำเร็จ ไฟล์ที่เขียนแล้วดาวน์โหลดไม่ได้อยู่ดี (ไม่มี manifest = ปฏิเสธ)
    reg.record_export(run_id=rv.run.id, package_id=pid,
                      files=[(xlsx_path.name, _file_sha256(xlsx_path)),
                             (snap.name, _file_sha256(snap))], db_path=db_path)
    return PackageFiles(package_id=pid, xlsx_path=xlsx_path, snapshot_path=snap,
                        rows=len(rows), neutralized=neutralized, run_id=rv.run.id)


# ══════════════════════════════════════════════════════════════════════════════
#  B4 — KEY BUILD / VERIFY (ไม่มีผลของ detector) แยกจาก POST-RUN ADJUDICATION
# ══════════════════════════════════════════════════════════════════════════════

#: ฟิลด์ที่ **ห้าม** ปรากฏในขั้นจัดทำ/ยืนยันเฉลย เพราะเป็นสิ่งที่ detector เสนอ
KEY_BUILD_FORBIDDEN_FIELDS = ("proposed_status", "proposed_label", "basis",
                              "differences", "alternatives", "internal_score",
                              "current_status", "human_required", "mapping_id",
                              "pair_count", "detector_order")


@dataclass(frozen=True)
class KeyItemRow:
    """หนึ่งรายการของขั้นจัดทำเฉลย — **หนึ่งข้อสังเกตในเอกสาร** ไม่ใช่หนึ่งคู่ของเครื่อง

    🔴 Bo (`5600162467`) — แถวของขั้นเฉลยต้องไม่มาจาก ``rv.pairs`` · ไม่มี ``mapping_id``
    ของ detector · ไม่สะท้อนจำนวนคู่หรือลำดับที่ detector เสนอ
    """
    item_id: str
    run_id: str
    side: str
    side_label: str
    text: str
    stage_label: str
    fiscal_year: object
    page: object
    short_hash: str
    evidence_url: str
    location_review: bool
    clipped: bool
    key_status: str
    key_status_label: str
    counterpart_item_id: str
    key_reason: str
    key_entered_by: str


@dataclass(frozen=True)
class KeyUniverseView:
    """สภาพของขั้นจัดทำ/ยืนยันเฉลยทั้งรอบ — ประกอบขึ้นโดย **ไม่เรียก** ``run_view``"""
    run: reg.RunRow
    old_doc: object
    new_doc: object
    rows: tuple
    old_rows: tuple
    new_rows: tuple
    universe_seal: object
    key_seal: object
    #: 🔴 P5-1 — สถานะแบบ opaque เท่านั้น (ผนึกแล้ว/ยังไม่ผนึก) · ไม่มีจำนวน/แฮช/เหตุผลของเครื่อง
    detector_sealed: bool
    coverage: object
    answered: int
    statuses: tuple
    status_labels: dict
    human_required: frozenset
    check_labels: dict
    #: P3-2 — ทะเบียนข้อสังเกตอิสระที่คนกรอกเอง (ขั้นก่อนสร้างจักรวาล)
    inventory: tuple = ()
    #: P5-1 — ผลตรวจผนึกที่ **ทำความสะอาดแล้ว** (ดู :class:`BlindVerification`)
    blind: object = None


_SIDE_LABELS = {ku.SIDE_OLD: "ฉบับเก่า", ku.SIDE_NEW: "ฉบับใหม่"}


def key_universe_view(run_id: str, db_path=None) -> "KeyUniverseView | None":
    """สร้าง view ของขั้นเฉลยจาก **จักรวาลของเฉลย** เท่านั้น

    🔴 ฟังก์ชันนี้ไม่เรียก ``reg.mappings`` / ``run_view`` / ``pair_view`` —
    มีเทสต์สถาปัตยกรรมบังคับไว้ (``test_architecture_separation``)
    """
    run = reg.get_run(run_id, db_path)
    if run is None:
        return None
    items = reg.key_universe(run_id, db_path)
    answers = reg.latest_key_answers(run_id, db_path)
    # 🔴 P3-2 — ข้อความที่แสดงต้องเป็นสิ่งที่ **คนกรอก** ไม่ใช่สิ่งที่เครื่องสกัดได้
    inv = {r.identity_key: r for r in reg.source_inventory_rows(run_id, db_path)}
    old_doc = docs.get(run.old_document_id, db_path)
    new_doc = docs.get(run.new_document_id, db_path)
    rows: list[KeyItemRow] = []
    for i in items:
        doc = old_doc if i.side == ku.SIDE_OLD else new_doc
        src = inv.get(i.identity_key)
        a = answers.get(i.item_id)
        status = a.key_status if a else ""
        rows.append(KeyItemRow(
            item_id=i.item_id, run_id=run_id, side=i.side,
            side_label=_SIDE_LABELS.get(i.side, i.side),
            text=(src.observed_text if src else ""),
            stage_label=(doc.stage_label if doc else ""),
            fiscal_year=(doc.fiscal_year if doc else None),
            page=i.page, short_hash=(doc.short_hash if doc else ""),
            # ชี้ไปที่ **หน้า** ของเอกสาร — ไม่ผูกกับข้อสังเกตของเครื่อง เพราะเครื่องอาจไม่มี
            evidence_url=evidence_url(doc.document_id if doc else "", i.page, "", run_id),
            location_review=True,
            clipped=False,
            key_status=status,
            key_status_label=mp.STATUS_LABELS.get(status, ""),
            counterpart_item_id=(a.counterpart_item_id if a else ""),
            key_reason=(a.reason if a else ""),
            key_entered_by=""))
    return KeyUniverseView(
        run=run, old_doc=old_doc, new_doc=new_doc, rows=tuple(rows),
        old_rows=tuple(r for r in rows if r.side == ku.SIDE_OLD),
        new_rows=tuple(r for r in rows if r.side == ku.SIDE_NEW),
        universe_seal=reg.universe_seal(run_id, db_path),
        key_seal=reg.key_seal(run_id, db_path),
        detector_sealed=(reg.detector_snapshot(run_id, db_path) is not None),
        coverage=reg.key_coverage(run_id, db_path), answered=len(answers),
        statuses=mp.STATUSES, status_labels=dict(mp.STATUS_LABELS),
        human_required=mp.HUMAN_REQUIRED, check_labels=dict(ku.CHECK_LABELS),
        inventory=tuple(reg.source_inventory_rows(run_id, db_path)),
        blind=blind_verification(run_id, db_path))


def record_source_item(run_id: str, *, side: str, page, observed_text: str,
                       occurrence=1, hint: str = "", entered_by: str, db_path=None):
    """กรอกหนึ่งรายการเข้าทะเบียนข้อสังเกต **อิสระ** (P3-2)"""
    return reg.record_source_item(run_id=run_id, side=side, page=page,
                                  observed_text=observed_text, occurrence=occurrence,
                                  hint=hint, entered_by=entered_by, db_path=db_path)


def retract_source_item(run_id: str, identity_key: str, *, retracted_by: str,
                        reason: str = "", db_path=None):
    return reg.retract_source_item(run_id=run_id, identity_key=identity_key,
                                   retracted_by=retracted_by, reason=reason,
                                   db_path=db_path)


def source_inventory(run_id: str, db_path=None):
    return reg.source_inventory_rows(run_id, db_path)


def seal_verification(run_id: str, db_path=None):
    """ผลการ **ตรวจ** ผนึกสาม artifact — ด่านจริงของขั้นตัดสินหลังรัน (P3-1)"""
    return reg.seal_verification(run_id, db_path)


def detector_coverage(run_id: str, db_path=None):
    """ความครอบคลุมของการสกัดเทียบกับทะเบียนอิสระ — เปิดหลังผนึกครบและตรวจผ่านเท่านั้น"""
    return reg.detector_coverage(run_id, db_path)


def inventory_error() -> type:
    return sinv.InventoryError


# ══════════════════════════════════════════════════════════════════════════════
#  P4-1 / P4-2 (PASS 5) — ขอบเขตของการเปิดผลเครื่อง และไฟล์ส่งออก
# ══════════════════════════════════════════════════════════════════════════════

EXPORT_PREFIX = "indpkg_"


def _file_sha256(path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def export_url(run_id: str, name: str) -> str:
    return f"/indicators/runs/{run_id}/exports/{name}"


def export_name_ok(name: str) -> bool:
    return (bool(name) and name.startswith(EXPORT_PREFIX) and "/" not in name
            and "\\" not in name and ".." not in name and len(name) <= 120)


@dataclass(frozen=True)
class ExportCheck:
    ok: bool
    reasons: tuple
    path: object = None

    @property
    def labels(self) -> tuple:
        return tuple(reg.EXPORT_REASON_LABELS.get(r, r) for r in self.reasons)


def check_export(run_id: str, name: str, export_dir, db_path=None) -> ExportCheck:
    """ตรวจก่อนส่งไฟล์ส่งออก — manifest · รอบ · ผนึกตรวจผ่าน ณ ตอนนี้ · digest · เนื้อไฟล์

    🔴 Bo (`5606392284` P4-2) — ไฟล์ที่ไม่มีบันทึกผูก (ไฟล์เก่า) **ปฏิเสธ** · ไม่ลบไฟล์เดิม
    """
    if not export_name_ok(name):
        return ExportCheck(ok=False, reasons=(reg.EXPORT_NOT_BOUND,))
    base = Path(export_dir).resolve()
    path = (base / name).resolve()
    if base not in path.parents:
        return ExportCheck(ok=False, reasons=(reg.EXPORT_NOT_BOUND,))
    sha = _file_sha256(path) if path.is_file() else ""
    ok, reasons = reg.verify_export(run_id, name, sha, db_path)
    return ExportCheck(ok=ok, reasons=reasons, path=(path if ok else None))


def detector_output_allowed(run_id: str, db_path=None) -> bool:
    """P4-1 — เปิดข้อสังเกต/คู่/สถานะ/จำนวน/สรุปของเครื่องได้หรือยัง

    ด่านเดียวกับขั้นตัดสินหลังรัน — ผนึกครบสามชั้น **และตรวจแล้วว่ายังตรง** ·
    ทุก route ที่เปิดผลเครื่องต้องผ่านฟังก์ชันนี้ (มีเทสต์ route บังคับ)
    """
    return adjudication_unlocked(run_id, db_path)


@dataclass(frozen=True)
class RunListRow:
    """แถวของหน้ารายการรอบ — จำนวนของเครื่องเป็น ``None`` จนกว่าตรวจผนึกผ่าน"""
    id: str
    label: str
    old_document_id: str
    new_document_id: str
    created_at: str
    unlocked: bool
    n_old: object = None
    n_new: object = None
    n_pairs: object = None


def run_row(run_id: str, db_path=None):
    """ข้อมูลกำกับของรอบ **โดยไม่ประกอบผลเครื่อง** — ใช้ตัดสินว่าจะล็อกหรือไม่"""
    return reg.get_run(run_id, db_path) if run_id else None


def runs_overview(db_path=None) -> list:
    """รายการรอบ — 🔴 P4-1 ไม่เปิดจำนวนข้อสังเกต/คู่ของเครื่องก่อนตรวจผนึกผ่าน"""
    out = []
    for r in reg.list_runs(db_path):
        unlocked = adjudication_unlocked(r.id, db_path)
        out.append(RunListRow(
            id=r.id, label=r.label, old_document_id=r.old_document_id,
            new_document_id=r.new_document_id, created_at=r.created_at, unlocked=unlocked,
            n_old=(r.n_old if unlocked else None), n_new=(r.n_new if unlocked else None),
            n_pairs=(r.n_pairs if unlocked else None)))
    return out



# ══════════════════════════════════════════════════════════════════════════════
#  P5-1 (PASS 6) — สิ่งที่หน้าก่อนตรวจผ่านเห็นได้เกี่ยวกับผลของเครื่อง: **ผนึกแล้ว/ยังไม่ผนึก เท่านั้น**
# ══════════════════════════════════════════════════════════════════════════════
#
# 🔴 Bo (`5615776981` P5-1) — *"KEY BUILD may expose documents, page evidence, human inventory,
# and an opaque sealed/not-sealed state, but not detector pair counts, observation counts,
# detector digests, statuses, or summaries."* · ใช้ view นี้ทั้งหน้าจัดทำเฉลยและหน้าล็อก

BLIND_DETECTOR_SEALED = "ผนึกแล้ว"
BLIND_DETECTOR_NOT_SEALED = "ยังไม่ผนึก"
BLIND_ALL_SEALED_BUT_FAILED = ("ผนึกครบทั้งสามชั้นแล้ว แต่การตรวจผนึกไม่ผ่าน — มีข้อมูลเปลี่ยนหลังผนึก "
                               "ต้องเปิดรอบประเมินใหม่ ห้ามซ่อมทับ")


@dataclass(frozen=True)
class BlindSealRow:
    """หนึ่งชั้นของผลตรวจผนึกที่หน้าก่อนตรวจผ่านแสดงได้

    ชั้นที่เป็นของคน (จักรวาล · เฉลย) แสดงผลและเหตุผลได้ · ชั้นของเครื่องแสดงได้เพียง
    ``sealed`` — ``ok`` เป็น ``None`` และไม่มีเหตุผล/แฮชใด ๆ
    """
    artifact: str
    label: str
    sealed: bool
    ok: object = None
    reasons: tuple = ()
    digest_prefix: str = ""

    @property
    def state_label(self) -> str:
        if self.ok is None:
            return BLIND_DETECTOR_SEALED if self.sealed else BLIND_DETECTOR_NOT_SEALED
        if not self.sealed:
            return "ยังไม่ผนึก"
        return "ตรวจผ่าน" if self.ok else "ตรวจไม่ผ่าน"


@dataclass(frozen=True)
class BlindVerification:
    rows: tuple
    all_sealed: bool
    ok: bool

    @property
    def summary(self) -> str:
        if self.ok:
            return "ผนึกครบและตรวจแล้วว่าตรงทุกชั้น"
        if self.all_sealed:
            return BLIND_ALL_SEALED_BUT_FAILED
        return "ยังผนึกไม่ครบ"


def blind_verification(run_id: str, db_path=None) -> BlindVerification:
    """ผลตรวจผนึกที่ **ไม่มีข้อมูลที่มาจากเครื่อง** — ใช้ได้ก่อนตรวจผ่านครบ

    เหตุผลเฉพาะของชั้นเครื่องบันทึกลง log ของเครื่องนี้เท่านั้น (สำหรับผู้ดูแล) ไม่ขึ้นหน้าจอ
    """
    v = reg.seal_verification(run_id, db_path)
    detector_sealed = reg.detector_snapshot(run_id, db_path) is not None
    universe_sealed = ku.R_UNIVERSE_NOT_FROZEN not in v.universe.reasons
    key_sealed = ku.R_KEY_NOT_SEALED not in v.key.reasons
    rows = (
        BlindSealRow(artifact=ku.ARTIFACT_UNIVERSE, label="จักรวาลของเฉลย (ทะเบียนอิสระ)",
                     sealed=universe_sealed, ok=v.universe.ok,
                     reasons=(() if v.universe.ok else v.universe.labels),
                     digest_prefix=(v.universe.sealed_digest[:16] if v.universe.ok else "")),
        BlindSealRow(artifact=ku.ARTIFACT_KEY, label="เฉลยของรอบนี้",
                     sealed=key_sealed, ok=v.key.ok,
                     reasons=(() if v.key.ok else v.key.labels),
                     digest_prefix=(v.key.sealed_digest[:16] if v.key.ok else "")),
        BlindSealRow(artifact=ku.ARTIFACT_DETECTOR, label="ผลลัพธ์ของเครื่อง",
                     sealed=detector_sealed, ok=None),
    )
    if detector_sealed and not v.detector.ok:
        log.warning("detector_seal_verification_failed run_id=%s reasons=%s",
                    run_id, ",".join(v.detector.reasons))
    return BlindVerification(rows=rows, all_sealed=(universe_sealed and key_sealed
                                                     and detector_sealed), ok=v.ok)


#: คีย์ใน ``detail_json`` ของ audit ที่เป็น **ผลของเครื่อง** — ปิดบังในหน้าจอจนกว่ารอบนั้นตรวจผ่าน
DETECTOR_AUDIT_KEYS = frozenset({
    "n_old", "n_new", "n_pairs", "by_status", "accounted_closed", "accounted_failed_checks",
    "pair_count", "observation_count", "snapshot_digest", "detector_digest",
    "mappings_digest", "observations_digest", "metadata_digest", "documents_digest",
})
AUDIT_REDACTED = "[ซ่อนจนกว่ารอบนี้ผนึกครบและตรวจผ่าน]"


def redact_audit_entries(entries, db_path=None) -> list:
    """สำเนาของรายการ audit สำหรับ **แสดงผล** — ปิดบังฟิลด์ผลเครื่องของรอบที่ยังไม่ตรวจผ่าน

    🔴 ไม่แก้ audit chain · แฮชของแต่ละรายการคำนวณจากข้อมูลเดิมที่บันทึกไว้ครบ ·
    รายการที่ระบุรอบไม่ได้แต่มีคีย์ผลเครื่อง ⇒ ปิดบังไว้ก่อน (ตรวจไม่ได้ = ไม่เปิด)
    """
    cache: dict = {}

    def unlocked(run_id: str) -> bool:
        if run_id not in cache:
            cache[run_id] = bool(run_id) and adjudication_unlocked(run_id, db_path)
        return cache[run_id]

    out = []
    for e in entries:
        e = dict(e)
        if str(e.get("action", "")).startswith("indicator_"):
            try:
                detail = json.loads(e.get("detail_json") or "{}")
            except ValueError:
                detail = {}
            if isinstance(detail, dict) and DETECTOR_AUDIT_KEYS.intersection(detail):
                run_id = (e.get("object_id") if e.get("object_type") == "ind_run"
                          else str(detail.get("run_id") or ""))
                if not unlocked(run_id):
                    for k in DETECTOR_AUDIT_KEYS.intersection(detail):
                        detail[k] = AUDIT_REDACTED
                    e["detail_json"] = json.dumps(detail, ensure_ascii=False, sort_keys=True)
                    e["redacted"] = True
        out.append(e)
    return out



def build_key_universe(run_id: str, *, built_by: str, db_path=None):
    return reg.build_key_universe(run_id, built_by=built_by, db_path=db_path)


def freeze_key_universe(run_id: str, *, frozen_by: str, db_path=None):
    return reg.freeze_key_universe(run_id, frozen_by=frozen_by, db_path=db_path)


def record_key_answer(run_id: str, item_id: str, *, key_status: str,
                      counterpart_item_id: str = "", reason: str = "",
                      entered_by: str, db_path=None):
    """บันทึกคำตอบของเฉลย — ขั้นนี้ไม่เห็นผลของ detector"""
    return reg.record_key_answer(run_id=run_id, item_id=item_id, key_status=key_status,
                                 counterpart_item_id=counterpart_item_id, reason=reason,
                                 entered_by=entered_by, db_path=db_path)


def key_coverage(run_id: str, db_path=None):
    return reg.key_coverage(run_id, db_path)


def seal_detector_snapshot(run_id: str, *, sealed_by: str, note: str = "", db_path=None):
    """ผนึกผลลัพธ์ของ detector — artifact คนละชิ้นกับเฉลย"""
    return reg.seal_detector_snapshot(run_id, sealed_by=sealed_by, note=note,
                                      db_path=db_path)


def detector_snapshot(run_id: str, db_path=None):
    return reg.detector_snapshot(run_id, db_path)


def record_key_entry(*args, **kwargs):
    """🔴 **เลิกใช้แล้ว (Pass 3)** — เฉลยผูกกับคู่ของ detector ไม่ได้

    ใช้ :func:`record_key_answer` ที่ผูกกับรายการในจักรวาลของเฉลยแทน
    """
    raise reg.KeyStageError(
        "เลิกใช้แล้ว — เฉลยต้องผูกกับรายการในจักรวาลของเฉลย (record_key_answer)")


def seal_key(run_id: str, *, sealed_by: str, note: str = "", db_path=None):
    """ผนึกเฉลยของรอบ — การกระทำของ custodian · ปลดล็อกขั้นตัดสินหลังรัน"""
    return reg.seal_key(run_id, sealed_by=sealed_by, note=note, db_path=db_path)


def adjudication_unlocked(run_id: str, db_path=None) -> bool:
    return reg.adjudication_unlocked(run_id, db_path)


def stage_of(run_id: str, db_path=None) -> str:
    """ขั้นปัจจุบันของรอบ — ``KEY_BUILD_VERIFY`` จนกว่าเฉลยจะถูกผนึก"""
    return STAGE_ADJUDICATION if adjudication_unlocked(run_id, db_path) else STAGE_KEY_BUILD


def open_document_path_for_streaming(document_id: str, db_path=None) -> Path:
    """สำหรับ route ส่งไฟล์เท่านั้น — ผู้เรียกห้ามนำ path ไปแสดง/ล็อก"""
    return docs.open_path_private(document_id, db_path=db_path)


def render_page_png(document_id: str, page: int, highlight=None, db_path=None) -> bytes:
    backend = pdftext.product_backend()
    if backend is None:
        raise RuntimeError(pdftext.NO_TEXT_BACKEND)
    p = docs.open_path_private(document_id, db_path=db_path)
    return backend.render_png(p, page, highlight=highlight)


def parse_highlight(raw: str) -> tuple[float, float, float, float] | None:
    if not raw:
        return None
    parts = raw.split(",")
    if len(parts) != 4:
        raise ValueError("hl ต้องมีตัวเลข 4 ค่า")
    vals = tuple(float(x) for x in parts)
    if any(v < 0 or v > 20000 for v in vals) or vals[0] > vals[2] or vals[1] > vals[3]:
        raise ValueError("hl ไม่ถูกต้อง")
    return vals


__all__ = [
    "EVIDENCE_SERVICE_VERSION", "LOCATION_REVIEW_REQUIRED", "SOURCE_UNAVAILABLE",
    "UNPUBLISHED_PLACEHOLDER", "MANDATORY_NOTICE", "PACKAGE_TITLE", "PACKAGE_NOTICE",
    "PACKAGE_COLUMNS", "public_basis", "evidence_url", "file_url", "compare_url",
    "page_image_url", "register_pdf", "PipelineResult", "run_indicator_pipeline",
    "SideView", "PageView", "page_view", "PairView", "RunView", "run_view",
    "pair_view", "decide", "package_rows", "PackageFiles", "write_package",
    "open_document_path_for_streaming", "render_page_png", "parse_highlight",
]


# ── ตัวช่วยสำหรับ route (route ห้าม import โมดูลชั้นล่างตรง ๆ) ────────────────

SourceUnavailable = docs.SourceUnavailable
DecisionError = reg.DecisionError
KeyStageError = reg.KeyStageError
DocumentIdCollision = docs.DocumentIdCollision


class StageLockedError(RuntimeError):
    """เรียกสิ่งที่อยู่ในขั้นถัดไปก่อนเวลา — เช่น สร้างชุดตัดสินก่อนเฉลยถูกผนึก (B4)"""


def init_schemas(db_path=None) -> None:
    docs.init_schema(db_path)
    reg.init_schema(db_path)


def can_render() -> bool:
    """วาดภาพหน้าได้หรือไม่ — ถามเฉพาะ backend ของผลิตภัณฑ์ (P1-1 · ไม่มี fallback)"""
    return pdftext.product_backend() is not None


def list_runs(db_path=None):
    return reg.list_runs(db_path)


def decision_choices() -> tuple[tuple[str, str], ...]:
    return tuple((d, reg.DECISION_LABELS[d]) for d in reg.DECISIONS)


def statuses() -> tuple[str, ...]:
    return mp.STATUSES


def status_labels() -> dict:
    return dict(mp.STATUS_LABELS)


def is_synthetic(rv: RunView) -> bool:
    return (rv.old_doc.disclosure_class == docs.DISC_SYNTHETIC
            or rv.new_doc.disclosure_class == docs.DISC_SYNTHETIC)


__all__ += ["SourceUnavailable", "DecisionError", "KeyStageError", "DocumentIdCollision",
            "StageLockedError", "init_schemas", "can_render", "list_runs",
            "decision_choices", "statuses", "status_labels", "is_synthetic",
            "KeyItemRow", "KeyUniverseView", "KEY_BUILD_FORBIDDEN_FIELDS",
            "key_universe_view", "build_key_universe", "freeze_key_universe",
            "record_key_answer", "key_coverage", "seal_detector_snapshot",
            "detector_snapshot", "record_key_entry", "record_source_item",
            "retract_source_item", "source_inventory", "seal_verification",
            "detector_coverage", "ExportCheck", "check_export", "export_url",
            "export_name_ok", "detector_output_allowed", "RunListRow", "runs_overview",
            "BlindSealRow", "BlindVerification", "blind_verification",
            "DETECTOR_AUDIT_KEYS", "AUDIT_REDACTED", "redact_audit_entries", "run_row",
            "seal_key", "adjudication_unlocked", "stage_of",
            "STAGE_KEY_BUILD", "STAGE_ADJUDICATION", "STAGE_LABELS_TH",
            "KEY_BUILD_TITLE", "KEY_BUILD_NOTICE", "RUN_CONTEXT_MISSING",
            "RUN_CONTEXT_MISMATCH", "ADJUDICATION_LOCKED", "backend_evidence"]


def backend_evidence() -> dict:
    """หลักฐาน backend/mode ที่ต้องบันทึกคู่กับผลการรัน (B6.1 ข้อ 4)"""
    return pdftext.backend_report(mode=pdftext.MODE_PRODUCT)
