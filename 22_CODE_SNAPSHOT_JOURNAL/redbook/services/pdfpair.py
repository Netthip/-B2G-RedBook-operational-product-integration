# -*- coding: utf-8 -*-
"""ชั้นบริการของสายเทียบเล่ม PDF ↔ PDF — route เรียกที่นี่เท่านั้น (ไม่เรียก ``redbook.pdfbook`` ตรง)

ลำดับงานของหนึ่งรอบ

1. เปิด PDF ฉบับ A/B ที่แนบไว้กับงานตรวจ (ตาราง ``project_source_pdfs``) · ตรวจ SHA-256 ของไฟล์จริง
   ให้ตรงกับที่บันทึกตอนแนบ — ไม่ตรง = ไม่อ่าน
2. หาช่วงหน้าของหน่วยงาน (ชื่อหน่วยงาน หรือช่วงหน้าที่ผู้ใช้กำหนด) → สกัดข้อเท็จจริง → เทียบ
3. บันทึกรอบพร้อมรุ่นตัวสกัด/โปรไฟล์/ช่วงหน้า และรายการ Audit

🔴 ผลเป็น "ข้อสังเกตให้คนตัดสิน" · โปรไฟล์ปรับเทียบกับเล่มสังเคราะห์เท่านั้น (แสดงบนทุกหน้า)
"""
from __future__ import annotations

import copy
import csv
import io
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .. import config, eval_guard, holdout
from ..core.hashing import sha256_file
from ..pdfbook import PDFBOOK_VERSION
from ..pdfbook import compare as cmp
from ..pdfbook import extract as ex
from ..pdfbook import profile as prof
from ..pdfbook import reader, scope as scope_mod
from ..pdfbook.text import fmt
from ..storage import files as filestore, pdfpair_repo, source_pdfs
from . import verify_view as vv

#: ป้ายตัวเลือกของสายเทียบเล่ม PDF (Bo REVIEW #44 6462103585) — key ชุดเดียวกับ ``vv.DECISION_CHOICES`` (ป้าย T1B ไม่เปลี่ยน) ·
#: เรียงเป็นกลุ่ม ปิด → ยังไม่ปิด → ไม่นับ ตาม :data:`DECISION_USE` · ไม่มีค่าเริ่มต้น และไม่เน้นตัวใดเป็นพิเศษ
_PDF_DECISION_LABELS = {
    "checked": "ตรวจแล้ว ไม่ต้องดำเนินการเพิ่ม",
    "per_document": "เปลี่ยนตามเอกสาร",
    "fix": "พบจุดที่ต้องแก้เอกสาร",
    "needs_more": "ต้องตรวจเพิ่มเติม",
    "mismatch": "ระบบจับคู่หรือชี้ตำแหน่งคลาดเคลื่อน",
    "not_relevant": "นอกขอบเขตที่กำหนด",
}
assert set(_PDF_DECISION_LABELS) == {k for k, _l, _s in vv.DECISION_CHOICES}
DECISIONS = tuple((k, _PDF_DECISION_LABELS[k]) for k in _PDF_DECISION_LABELS)
DECISION_LABELS = dict(DECISIONS)
TOPICS = cmp.TOPICS
TOPIC_LABELS = cmp.TOPIC_LABELS
MODE_LABELS = cmp.MODE_LABELS
PROFILE_STATUS_LABEL = prof.PROFILE_STATUS_LABEL
CROP_MARGIN_PT = 110.0


class PairError(ValueError):
    """ข้อความที่ผู้ใช้อ่านได้ — ไม่มี path ภายใน"""


class RunSuperseded(PairError):
    """รอบนี้ถูกแทนด้วยรอบ ``new_run_id`` แล้ว — อ่านได้อย่างเดียว (บันทึกผล/ยืนยันปี/ส่งออกไม่ได้)"""

    def __init__(self, new_run_id: str):
        super().__init__(f"รอบนี้ถูกแทนด้วยรอบ {new_run_id} ที่คำนวณด้วยปีงบที่ยืนยันแล้ว — "
                         "ผลและคำตัดสินเดิมเก็บไว้ดูย้อนหลังได้ แต่บันทึกเพิ่มหรือส่งออกไม่ได้")
        self.new_run_id = new_run_id


_sha_ok: dict = {}       # (ไฟล์, เวลาแก้ไข, ขนาด) → SHA-256 ที่ตรวจแล้ว — ไม่คำนวณซ้ำทุกคำขอภาพหลักฐาน


def _side_file(project_id: str, side: str):
    row = source_pdfs.for_project(project_id).get(side)
    if not row:
        raise PairError(f"ยังไม่ได้แนบ PDF ของฉบับ {side}")
    if holdout.is_holdout(row.get("original_name") or ""):
        raise PairError(holdout.UPLOAD_NOTICE)
    path = filestore.path_for(row["stored_name"])
    if not path.exists():
        raise PairError(f"ไม่พบไฟล์ PDF ของฉบับ {side} ในที่เก็บ")
    st = path.stat()
    k = (str(path), st.st_mtime_ns, st.st_size)
    if _sha_ok.get(k) != row["sha256"]:
        if sha256_file(path) != row["sha256"]:
            raise PairError(f"ไฟล์ PDF ของฉบับ {side} ไม่ตรงกับที่บันทึกไว้ตอนแนบ (SHA-256 ต่างกัน) — ระบบไม่อ่าน")
        _sha_ok[k] = row["sha256"]
    return path, row


def _int(v) -> int:
    try:
        return int(str(v).strip() or 0)
    except ValueError:
        raise PairError("ช่วงหน้าต้องเป็นตัวเลข")


#: หน้าต้นไฟล์ที่อ่านเพื่อหาปีงบ/ขั้นเอกสาร เมื่อกำหนดช่วงหน้าแล้ว
META_FRONT_PAGES = 3


#: ข้อเท็จจริงที่สกัดแล้ว จำตามเนื้อไฟล์ — อ่าน PDF ครั้งเดียวต่อ (ไฟล์ · หน่วยงาน · ช่วงหน้า · ปีที่ยืนยัน · รุ่นตัวสกัด)
FACTS_CACHE_MAX = 32
_facts_mem: "OrderedDict[str, dict]" = OrderedDict()
_facts_lock = threading.Lock()


def _facts_key(sha: str, agency, first, last, range_method, year_override) -> str:
    import hashlib
    from ..pdfbook import thai_repair
    parts = [sha, agency, str(_int(first)), str(_int(last)), range_method or "",
             str(year_override or ""), PDFBOOK_VERSION, prof.PROFILE_VERSION, thai_repair.THAI_REPAIR_VERSION]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


#: ไฟล์เปลี่ยนระหว่างที่ระบบอ่าน — ผลที่ได้อาจปนสองไฟล์ จึงไม่บันทึกและไม่จำ (REVIEW 6359288623)
FILE_CHANGED_MSG = "ไฟล์ PDF เปลี่ยนระหว่างที่ระบบอ่าน — ไม่บันทึกผลรอบนี้ (รอบเดิมไม่ถูกแตะ) ลองใหม่อีกครั้ง"


def _facts(path, agency: str, first, last, range_method: str = "", year_override: int | None = None,
           expect_sha: str = ""):
    """สกัดข้อเท็จจริงของเล่ม — ใช้ผลที่จำไว้ถ้าเคยอ่านไฟล์เดียวกันด้วยค่าเดียวกัน (ผลเหมือนอ่านสด)

    กุญแจ = SHA-256 ของไฟล์ + หน่วยงาน + ช่วงหน้า + วิธีได้ช่วง + ปีที่ยืนยัน + รุ่นตัวสกัด/โปรไฟล์/ตัวซ่อมไทย ⇒
    ไฟล์/รุ่นเปลี่ยน = อ่านใหม่ · จำในหน่วยความจำ + ``<data>/cache/facts`` · ทุกครั้งคืนสำเนาใหม่ (กันแก้ทับกัน)
    · เป็นแค่ข้อเท็จจริงของเล่มเดียว **ไม่ใช่ผลเทียบ** (ไม่มีข้อสังเกตจนกว่าจะเรียก :func:`run`)

    ``expect_sha`` = SHA-256 ที่รอบนี้จะบันทึกคู่กับผล — เนื้อไฟล์ที่อ่านจริงต้องตรงค่านี้ทั้งก่อนและหลังอ่าน
    (กันกรณีไฟล์ถูกแทนระหว่างตรวจ SHA ที่หัวรอบกับตอนอ่านหน้า)"""
    import json
    from dataclasses import asdict
    sha = sha256_file(path)
    if expect_sha and sha != expect_sha:
        raise PairError(FILE_CHANGED_MSG)
    key = _facts_key(sha, agency, first, last, range_method, year_override)
    f = config.DATA_DIR / "cache" / "facts" / f"{key}.json"
    with _facts_lock:
        d = _facts_mem.get(key)
    if d is None:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            with reader.track_reads() as used:   # SHA ของเอกสารที่ตัวอ่านอ่านจริง (แคชคีย์ด้วยเวลา/ขนาด ไม่ใช่เนื้อไฟล์)
                bf, sc, n = _facts_live(path, agency, first, last, range_method, year_override)
            if sha256_file(path) != sha or not used or used != {sha}:
                raise PairError(FILE_CHANGED_MSG)
            d = {"facts": bf.to_dict(), "scope": asdict(sc), "n": n}
            try:
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
        with _facts_lock:
            _facts_mem[key] = d
            while len(_facts_mem) > FACTS_CACHE_MAX:
                _facts_mem.popitem(last=False)
    sd = d["scope"]
    sc = scope_mod.Scope(sd["first"], sd["last"], sd["method"], sd["agency_hint"], tuple(sd["starts_found"]))
    return ex.BookFacts.from_dict(d["facts"]), sc, d["n"]


def _facts_live(path, agency: str, first, last, range_method: str = "", year_override: int | None = None):
    """``year_override`` = ปีงบที่ผู้ตรวจยืนยันจากภาพหน้าเอกสาร — ใช้แทนปีที่ระบบอ่านได้ทั้งตอนสกัดและเทียบ"""
    try:
        f, l = _int(first), _int(last)
        if f and l:
            # กำหนดช่วงหน้าแล้ว (เล่มรวมทั้งกระทรวง) — อ่านเฉพาะหน้าต้นไฟล์ + ช่วงของหน่วยงาน
            # ไม่อ่านเนื้อหาหน้าของหน่วยงานอื่น
            n = reader.page_count(path)
            texts = reader.page_texts(path, list(range(1, min(META_FRONT_PAGES, n) + 1))
                                      + list(range(f, min(l, n) + 1)))
        else:
            texts = reader.page_texts(path)
        sc = scope_mod.find(texts, agency, f, l)
        if range_method:
            from dataclasses import replace
            sc = replace(sc, method=range_method)
    except scope_mod.ScopeError as e:
        raise PairError(str(e))
    except reader.ReaderUnavailable as e:
        raise PairError(str(e))
    # ปีงบและขั้นเอกสารอ่านจาก **ข้อความที่มองเห็น** ชุดเดียวกับหลักฐานที่แสดง — ปีที่ใช้คำนวณจึงตรงกับหลักฐานเสมอ
    # (เดิมปีที่ใช้มาจากข้อความดิบที่รวมข้อความซ่อนนอกขอบหน้า ขณะที่สถานะ/หลักฐานมาจากข้อความที่มองเห็น)
    vis = year_texts(path, len(texts), sc.first, sc.last)
    ye = ex.detect_year(vis, sc.first, sc.last)
    se = ex.detect_stage(vis, sc.first)
    fy = int(year_override) if year_override else ye.year
    pages = reader.page_words(path, sc.pages)
    bf = ex.extract(pages, fiscal_year=fy, stage=se.stage, agency=agency)
    bf.year_origin, bf.year_status, bf.year_candidates = ye.origin, ye.status, list(ye.candidates)
    bf.year_evidence = _locate_year(path, ye.evidence)
    bf.stage_status, bf.stage_origin = se.status, ("title_line" if se.stage else "")
    bf.stage_evidence = [dict(e) for e in se.evidence]
    if year_override:
        # หลักฐานที่ระบบพบยังเก็บไว้ใน year_candidates · ที่มาของปีที่ใช้ = ผู้ตรวจยืนยัน
        bf.year_origin, bf.year_status = YEAR_CONFIRMED_ORIGIN, YEAR_CONFIRMED
    return bf, sc, len(texts)


def year_texts(path, n_pages: int, scope_first: int, scope_last: int = 0) -> list:
    """ข้อความที่ใช้หาปีงบ — หน้าต้นไฟล์ 3 หน้า + หน้าแรกของหน่วยงาน (:func:`ex.year_pages`) **เฉพาะข้อความที่มองเห็นบนหน้า**
    (เล่มรวมบางเล่มมีข้อความของหน้าอื่นซ่อนนอกขอบกระดาษ — ไม่ใช่หลักฐานที่คนเห็น) · หน้าอื่นเป็นข้อความว่าง"""
    pages = ex.year_pages(n_pages, scope_first, scope_last)
    vis = {pt.page: ex.visible_text(pt) for pt in reader.page_words(path, pages)}
    return [vis.get(i + 1, "") for i in range(n_pages)]


def _locate_year(path, evidence) -> list:
    """เติมกรอบ (bbox) ให้หลักฐานปีแต่ละ candidate จากหน้าที่อ่านอยู่แล้ว — หาไม่พบ = bbox ว่าง (ไม่เดา)"""
    from ..pdfbook.layout import rows_of_page
    from ..pdfbook.text import clean
    out = [dict(e) for e in evidence]
    pages = sorted({e["page"] for e in out})
    if not pages:
        return out
    try:
        rows = {pt.page: rows_of_page(ex._visible(pt)[0]) for pt in reader.page_words(path, pages)}
    except reader.ReaderUnavailable:
        return out
    for e in out:
        want = [str(e["year"])] + ([str(e["end"])] if e.get("end") != e["year"] else [])
        hit = next((r for r in rows.get(e["page"], []) if "ปีงบประมาณ" in clean(r.text)
                    and all(w in clean(r.text) for w in want)), None)
        e["bbox"] = list(hit.bbox) if hit else []
    return out


def _stage_from_register(bf, hint: str) -> None:
    """ขั้นเอกสารจากทะเบียนดาวน์โหลดของชั้นเล่ม (หน้าเว็บที่ดาวน์โหลดระบุขั้นของไฟล์) — ใช้เมื่อข้อความไม่ได้บอก ·
    ข้อความบอกคนละขั้นกับทะเบียน = ขัดกัน ระบบไม่เลือกให้ (ที่มาบันทึกใน ``stage_origin``/``stage_evidence``)"""
    if hint not in ("draft", "act"):
        return
    if bf.stage and bf.stage != hint:
        bf.stage, bf.stage_status = "", "conflict"
        bf.stage_evidence = list(bf.stage_evidence) + [{"kind": hint, "page": 0, "line": "ทะเบียนดาวน์โหลด",
                                                         "cue": "register"}]
    elif not bf.stage:
        bf.stage, bf.stage_status, bf.stage_origin = hint, "ok", "register"


#: ระหว่างล็อกชุดประเมิน ช่วงหน้าที่ผู้ใช้กำหนดเองต้องพิสูจน์ได้ว่าอยู่ในหน่วยงานที่ระบุ (Bo REVIEW #44 6462457757)
RANGE_NEEDS_AGENCY_MSG = ("ระหว่างล็อกชุดประเมิน ช่วงหน้าที่กำหนดเองต้องระบุหน่วยงานด้วย — "
                          "ระบบยืนยันไม่ได้ว่าช่วงหน้านี้อยู่นอกชุดประเมิน จึงไม่เริ่มรอบ")
RANGE_UNVERIFIED_MSG = ("ระหว่างล็อกชุดประเมิน ช่วงหน้าที่กำหนดเองต้องอยู่ในหน้าของหน่วยงานที่ระบุตามสารบัญของเล่ม — "
                        "ยืนยันไม่ได้ จึงไม่เริ่มรอบ (ล้างช่วงหน้าเพื่อให้ระบบหาจากชื่อหน่วยงาน)")


def _guard_manual_range(agency: str, range_method: str, sides: dict) -> None:
    """ช่องข้ามด่านกรณีไม่ระบุหน่วยงาน: ด่านชื่อ (:func:`eval_guard.check`) ดูแค่ชื่อ — ช่วงหน้าที่กำหนดเองชี้ไปหน้าของ
    หน่วยงานในชุดประเมินได้ ระหว่างล็อกจึง (1) ไม่มีชื่อหน่วยงาน = ปฏิเสธ (2) มีชื่อ = ช่วงที่ขอต้องอยู่ในช่วงของหน่วยงาน
    นั้นตามสารบัญของไฟล์ (อ่านเฉพาะสารบัญ) · หาไม่ได้ = ปฏิเสธ · ช่วงที่ได้จากสารบัญหรือจากชื่อโดยระบบ = ผ่าน"""
    if range_method == scope_mod.METHOD_TOC or not eval_guard.locked():
        return
    manual = {s: v for s, v in sides.items() if _int(v[2]) or _int(v[3])}
    if not manual:
        return                                    # ระบบหาช่วงจากชื่อหน่วยงาน (ผ่านด่านชื่อแล้ว)
    if not agency:
        eval_guard.refuse("eval_range_without_agency", "pdfpair.run", RANGE_NEEDS_AGENCY_MSG)
    from . import pdfshelf
    for side, (path, sha, first, last) in manual.items():
        try:
            sc, _read = pdfshelf.toc_scope_of_file(path, sha, agency)
        except Exception:  # noqa: BLE001 — หาสารบัญไม่ได้ด้วยเหตุใดก็ตาม = ยืนยันไม่ได้
            sc = None
        f, l = _int(first) or 1, _int(last) or reader.page_count(path)
        if sc is None or not (sc.first <= f <= l <= sc.last):
            eval_guard.refuse("eval_range_unverified", f"pdfpair.run:{side}", RANGE_UNVERIFIED_MSG)


def run(project_id: str, *, agency: str = "", mode: str = "", a_first="", a_last="",
        b_first="", b_last="", range_method: str = "", pages_read: dict | None = None,
        shelf: dict | None = None, years: dict | None = None, supersedes: dict | None = None,
        stages: dict | None = None) -> str:
    """``range_method`` = วิธีที่ได้ช่วงหน้า (เช่น จากสารบัญ) · ``pages_read`` = หน้าที่อ่านเนื้อหาจริงต่อฉบับ ·
    ``shelf`` = รหัสเล่มบนชั้นเล่มในเครื่อง — บันทึกไว้กับรอบเพื่อตรวจย้อนได้ ·
    ``years`` = ``{side: ปีที่ผู้ตรวจยืนยัน}`` · ``supersedes`` = รอบเดิมที่รอบนี้คำนวณแทน (ดู :func:`rerun`) ·
    ``stages`` = ``{side: ขั้นตามทะเบียนดาวน์โหลด}`` (ชั้นเล่ม) — ใช้เมื่อข้อความไม่บอกขั้น"""
    agency = (agency or "").strip()
    try:                                    # หน่วยงานในชุดประเมินที่ยังไม่ปลดล็อก — ก่อนอ่านไฟล์ใด ๆ (#44 G4)
        eval_guard.check(agency, "pdfpair.run")
    except eval_guard.EvalAgencyBlocked as e:
        raise PairError(str(e))
    pa, ra = _side_file(project_id, "A")
    pb, rb = _side_file(project_id, "B")
    try:
        _guard_manual_range(agency, range_method, {"A": (pa, ra["sha256"], a_first, a_last),
                                                   "B": (pb, rb["sha256"], b_first, b_last)})
    except eval_guard.EvalAgencyBlocked as e:
        raise PairError(str(e))
    years, stages = years or {}, stages or {}
    fa, sa, na = _facts(pa, agency, a_first, a_last, range_method, years.get("A"), expect_sha=ra["sha256"])
    fb, sb, nb = _facts(pb, agency, b_first, b_last, range_method, years.get("B"), expect_sha=rb["sha256"])
    _stage_from_register(fa, stages.get("A", ""))
    _stage_from_register(fb, stages.get("B", ""))
    if mode not in ("", cmp.MODE_SAME_YEAR, cmp.MODE_CROSS_YEAR):
        raise PairError("รูปแบบการเทียบไม่ถูกต้อง")
    result = cmp.compare(fa, fb, mode)
    scope = {s: {"first": sc.first, "last": sc.last, "method": sc.method,
                 "method_label": sc.method_label, "pages_in_file": n,
                 "starts_found": list(sc.starts_found),
                 **({"pages_read": (pages_read or {}).get(s, [])} if pages_read else {}),
                 **({"shelf_volume": (shelf or {}).get(s, "")} if shelf else {}),
                 **({"stage_register": stages[s]} if stages.get(s) else {})}
             for s, sc, n in (("A", sa, na), ("B", sb, nb))}
    from ..pdfbook import thai_repair
    versions = {"pdfbook": PDFBOOK_VERSION, "profile": prof.PROFILE_VERSION,
                "profile_status": prof.PROFILE_STATUS,
                "thai_repair": thai_repair.THAI_REPAIR_VERSION,
                "thai_pua_map": thai_repair.PUA_MAP_STATUS,
                "backend": reader._backend().version}
    return pdfpair_repo.save_run(
        project_id=project_id, mode=result.mode, agency=agency, a_sha256=ra["sha256"],
        b_sha256=rb["sha256"], a_name=ra["original_name"], b_name=rb["original_name"], scope=scope,
        facts_a=fa.to_dict(), facts_b=fb.to_dict(), result=result.to_dict(), versions=versions,
        supersedes=supersedes)


# ── มุมมอง ───────────────────────────────────────────────────────────────────
YEAR_ORIGIN_LABELS = {"stated": "ข้อความ \"ประจำปีงบประมาณ\"",
                      "comparison_range": "ปลายช่วงตารางเปรียบเทียบ",
                      "forward_range": "ช่วงประมาณการล่วงหน้า (ปีเริ่มช่วง − 1)",
                      "single_mention": "ปีที่กล่าวถึงในเนื้อหา",
                      "reviewer_confirmed": "ผู้ตรวจยืนยันจากภาพหน้าเอกสาร (รอบที่คำนวณซ้ำ)"}
YEAR_CONFIRMED, YEAR_CONFIRMED_ORIGIN = "confirmed", "reviewer_confirmed"
STAGE_LABELS = {"draft": "ร่าง พ.ร.บ.", "act": "พ.ร.บ."}
YEAR_EVIDENCE_KINDS = {"stated": "ปีของเล่ม (\"ประจำปีงบประมาณ\")", "comparison": "ช่วงปีเปรียบเทียบ",
                       "forward": "ช่วงประมาณการล่วงหน้า", "mention": "ปีที่กล่าวถึงในเนื้อหา"}
#: สถานะปีที่ถือว่า "รู้แน่" — ระบบอ่านได้ชัด หรือรอบนี้คำนวณด้วยปีที่ผู้ตรวจยืนยันแล้ว
YEAR_SETTLED = ("ok", YEAR_CONFIRMED)
#: ป้ายสถานะปีงบของฉบับ — หน้าเว็บเดิมและ API ใช้ชุดเดียวกัน (เดิมป้ายอยู่ในเทมเพลต และขาด "confirmed" จึงขึ้น
#: "รอบเก่า" ผิดกับรอบที่คำนวณซ้ำด้วยปีที่ยืนยัน)
YEAR_STATUS_LABELS = {"ok": "ชัดเจน", YEAR_CONFIRMED: "ผู้ตรวจยืนยันจากภาพหน้าเอกสาร",
                      "uncertain": "อนุมาน ไม่ได้ระบุตรง ๆ", "conflict": "หลักฐานขัดกัน", "not_found": "หาไม่พบ"}
YEAR_STATUS_STATES = {"ok": "ok", YEAR_CONFIRMED: "ok", "uncertain": "warn", "conflict": "fail", "not_found": "fail"}
YEAR_STATUS_UNKNOWN = "รอบเก่า — ไม่มีข้อมูลที่มา"


def year_status_label(status: str) -> str:
    return YEAR_STATUS_LABELS.get(status or "", YEAR_STATUS_UNKNOWN)


def year_status_state(status: str) -> str:
    """ok · warn · fail — สีป้าย (รอบเก่าที่ไม่มีข้อมูลที่มา = warn)"""
    return YEAR_STATUS_STATES.get(status or "", "warn")

# ── นโยบายการใช้ผล (แยก "ตรวจครบ" ออกจาก "พร้อมใช้อ้างผล") ─────────────────────────────
#: คำตัดสินของผู้ตรวจ → ข้อนั้นใช้อ้างผลได้แค่ไหน · ระบบไม่เปลี่ยนคำตัดสินของคนแทน แค่จัดชั้นการใช้ผล
#:   usable   = ปิดความไม่แน่ใจแล้ว ใช้อ้างได้ (ยืนยันว่าตรวจแล้ว/ตามเอกสาร/ต้องแก้ข้อมูล)
#:   excluded = ไม่นับในผล โดยผู้ตรวจระบุว่าไม่เกี่ยวข้อง — รายงานจำนวนคู่กับผลเสมอ
#:   open     = ยังไม่ปิด — "ต้องตรวจเพิ่มเติม" ยังไม่รู้คำตอบ · "ระบบจับคู่ผิด" = ยังไม่รู้ผลเทียบจริงของแถวนั้น
#:              ⇒ ทั้งรอบ "ตรวจครบ" ได้ แต่ยังไม่ "พร้อมใช้อ้างผล" จนกว่าจะตรวจแถวนั้นด้วยวิธีอื่นแล้วเปลี่ยนคำตัดสินเอง
DECISION_USE = {"checked": "usable", "per_document": "usable", "fix": "usable",
                "not_relevant": "excluded", "needs_more": "open", "mismatch": "open"}
#: "เลือกเมื่อ…" ของแต่ละตัวเลือก (Bo REVIEW #44 6459501871) — ถ้อยคำโดเมนจากนิยามของ :data:`DECISION_USE` ด้านบน ·
#: หน้าเดิมและ API ใช้ชุดเดียวกัน · ไม่เปลี่ยนความหมายหรือผลต่อการใช้ผลของตัวเลือก
DECISION_WHEN = {
    "checked": "เลือกเมื่อทวนหลักฐานแล้ว ยอมรับข้อสังเกตนี้ และไม่ต้องดำเนินการเพิ่ม",
    "per_document": "เลือกเมื่อยืนยันว่าเป็นการเปลี่ยนตามเอกสารหรือขั้นตอนที่เกี่ยวข้อง และไม่ต้องตรวจเพิ่ม",
    "fix": "เลือกเมื่อยืนยันว่ามีข้อมูลที่ต้องแก้ — ระบุฉบับและเหตุผลในหมายเหตุ",
    "needs_more": "เลือกเมื่อยังสรุปไม่ได้ ต้องดูเอกสารอื่นหรือถามผู้เกี่ยวข้อง — ระบุเหตุในหมายเหตุ · ข้อนี้ยังไม่ปิด",
    "mismatch": "เลือกเมื่อระบบนำรายการที่ไม่ใช่คู่เดียวกันมาเทียบ หรือชี้ตำแหน่งที่ไม่ใช่รายการนี้ — "
                "ยังใช้ผลข้อนี้ไม่ได้จนกว่าจะตรวจด้วยวิธีอื่นหรือแก้ปัญหาตามเกณฑ์",
    "not_relevant": "เลือกเมื่อเทียบกับขอบเขตที่ประกาศไว้ก่อนแล้วไม่อยู่ในขอบเขต — ระบุเหตุ · ไม่นับในการใช้ผล "
                    "แต่รายงานจำนวนเสมอ · ไม่ใช้กับข้อที่ยากหรือผลที่ระบบผิด",
}
#: ผลที่แสดงหลังเลือก (Bo: "แสดงผลหลังเลือกชัด") — fix ปิดงานทวน แต่ระบบไม่ได้ติดตามการแก้เอกสารจริง
DECISION_AFTER = {
    "checked": "ปิดข้อนี้แล้ว",
    "per_document": "ปิดข้อนี้แล้ว",
    "fix": "บันทึกความเห็นแล้ว — ไม่ใช่การยืนยันว่าแก้เอกสารเสร็จ",
    "needs_more": "ยังไม่ปิด — ยังใช้ผลข้อนี้ไม่ได้",
    "mismatch": "ยังไม่ปิด — ยังใช้ผลข้อนี้ไม่ได้จนกว่าจะตรวจด้วยวิธีอื่น",
    "not_relevant": "ไม่นับในการใช้ผล — รายงานจำนวนคู่กับผลเสมอ (ไม่ได้ลบออกจากบัญชีข้อสังเกต)",
}
USE_LABELS = {"usable": "ปิดแล้ว — ใช้ผลได้ตามเงื่อนไขของรอบ", "excluded": "ไม่นับ (ผู้ตรวจระบุว่านอกขอบเขตที่กำหนด)",
              "open": "ยังไม่ปิด — ใช้ผลไม่ได้", "pending": "ยังไม่ตัดสิน", "info": "ข้อมูลประกอบ — ไม่ต้องตัดสิน"}
#: สถานะการใช้ผลของทั้งรอบ — "validated" = **ผ่านเงื่อนไขการใช้ผลของรอบ** ไม่ใช่การรับรองความแม่นยำ (REVIEW 6359288623)
USE_STATUS_LABELS = {"in_review": "ยังตรวจไม่ครบ", "review_complete": "ตรวจครบ — ยังไม่ผ่านเงื่อนไขการใช้ผล",
                     "validated": "ผ่านเงื่อนไขการใช้ผลของรอบนี้", "blocked": "รอบนี้ถูกบล็อก"}
#: ขอบเขตของสถานะ — แสดงคู่กับสถานะทุกที่ที่แสดง (หน้าเว็บ · API · Audit การส่งออก)
USE_STATUS_SCOPE = ("“ผ่านเงื่อนไขการใช้ผล” หมายถึงทุกข้อที่ต้องตรวจในรอบนี้ถูกตัดสินและปิดแล้วเท่านั้น — "
                    "ไม่ได้รับรองความแม่นยำของระบบ และไม่ได้รับรองว่าระบบอ่านได้ครบทั้งเอกสาร · "
                    "ข้อที่ไม่นับและข้อที่ยังไม่ปิดรายงานคู่กับผลเสมอ (ไม่ตัดออกจากตัวหาร)")


def side_label_of(side: str, stage: str, stage_status: str, fiscal_year, year_status: str,
                  confirmed_year=None) -> str:
    """ป้ายของฉบับ (ขั้นเอกสาร + ปีงบ) — หน้ารอบ · หน้ารายการรอบ · API ใช้ตัวเดียวกัน"""
    text = {"draft": "ร่าง พ.ร.บ.", "act": "พ.ร.บ."}.get(stage, "เอกสาร")
    if stage_status == "conflict":
        text = "เอกสาร (ขั้นเอกสารขัดกัน)"
    if year_status == YEAR_CONFIRMED:
        fy = f" ปี {fiscal_year} (ผู้ตรวจยืนยัน)"
    elif confirmed_year and year_status != "ok":
        fy = f" ปี {confirmed_year} (ผู้ตรวจยืนยัน)"
    elif fiscal_year:
        fy = f" ปี {fiscal_year}" + (" (ไม่แน่ใจ)" if year_status == "uncertain" else "")
    else:
        fy = " · ไม่ทราบปีงบ" if year_status in ("conflict", "not_found") else ""
    return f"ฉบับ {side} · {text}{fy}"


@dataclass
class TopicGroup:
    key: str
    label: str
    findings: list = field(default_factory=list)
    info: list = field(default_factory=list)
    decided: int = 0

    @property
    def total(self) -> int:
        return len(self.findings)

    @property
    def pending(self) -> int:
        return self.total - self.decided


@dataclass
class RunView:
    run: dict
    result: cmp.CompareResult
    groups: list
    decisions: dict
    facts_a: ex.BookFacts
    facts_b: ex.BookFacts
    year_confirms: dict = field(default_factory=dict)   # {side: {year, note, confirmed_at}}
    superseded_by: str = ""      # รอบใหม่ที่แทนรอบนี้ (รอบนี้ถูกบล็อก)
    supersedes: str = ""         # รอบเดิมที่รอบนี้คำนวณแทน

    @property
    def rid(self) -> str:
        return self.run["id"]

    @property
    def pending(self) -> int:
        return sum(g.pending for g in self.groups)

    @property
    def actionable(self) -> int:
        return sum(g.total for g in self.groups)

    @property
    def item_changes(self) -> list:
        """การเปลี่ยนแปลงระดับรายการ (ชั้นล่างสุดที่ระบบอ่านได้) — ต้นทางของผลที่ไล่ไปถึงยอดรวม"""
        out = [f for f in self.result.findings if f.topic == "items" and not f.info and not f.within]
        return sorted(out, key=lambda f: (f.a.page or f.b.page or 0))

    @property
    def info_count(self) -> int:
        return sum(len(g.info) for g in self.groups)

    def finding(self, fid: str):
        for f in self.result.findings:
            if f.id == fid:
                return f
        return None

    def side_label(self, side: str) -> str:
        bf = self.facts_a if side == "A" else self.facts_b
        conf = self.year_confirms.get(side)
        return side_label_of(side, bf.stage, bf.stage_status, bf.fiscal_year, bf.year_status,
                             conf["year"] if conf else None)

    @property
    def year_warnings(self) -> list:
        """[(ฉบับ, ข้อความ)] เมื่อปีงบของฉบับใดไม่แน่ใจ/ขัดกัน/หาไม่พบ — โหมดที่เลือกเองไม่กลบคำเตือนนี้"""
        out = []
        for side, bf in (("A", self.facts_a), ("B", self.facts_b)):
            found = " · ".join(bf.year_candidates) or "ไม่มี"
            if bf.year_status == "conflict":
                out.append((side, f"หลักฐานปีงบขัดกัน ระบบไม่เลือกปีให้ — ที่พบ: {found}"))
            elif bf.year_status == "not_found":
                out.append((side, "ไม่พบปีงบในหน้าต้นไฟล์และหน้าเริ่มของหน่วยงาน"))
            elif bf.year_status == "uncertain":
                out.append((side, f"ปีงบ {bf.fiscal_year} อนุมานจาก{YEAR_ORIGIN_LABELS.get(bf.year_origin, bf.year_origin)}"
                                  f" ไม่ได้ระบุตรง ๆ — ที่พบ: {found}"))
            elif bf.year_status == "":
                out.append((side, "รอบเทียบนี้สร้างก่อนระบบบันทึกที่มาของปีงบ — ตรวจปีจากภาพหน้าเอกสาร"))
            conf = self.year_confirms.get(side)
            if conf and out and out[-1][0] == side:
                out[-1] = (side, out[-1][1] + f" · ผู้ตรวจยืนยันแล้วว่าเป็นปี {conf['year']}")
        return out

    @property
    def stage_warnings(self) -> list:
        """[(ฉบับ, ข้อความ)] เมื่อขั้นเอกสาร (ร่าง พ.ร.บ./พ.ร.บ.) ไม่ได้ยืนยันจากบรรทัดชื่อเอกสาร — ป้ายคู่ฉบับ
        (เช่น "ร่าง พ.ร.บ. ↔ พ.ร.บ." ของโหมดปีเดียวกัน) จึงไม่ใช่ข้อเท็จจริงที่อ่านได้จากเอกสาร (ไม่บล็อกการส่งออก)"""
        out = []
        for side, bf in (("A", self.facts_a), ("B", self.facts_b)):
            if bf.stage_status == "conflict":
                found = " · ".join(f"{STAGE_LABELS.get(e['kind'], e['kind'])} ({'ทะเบียน' if e.get('cue') == 'register' else 'หน้า ' + str(e['page'])})"
                                   for e in bf.stage_evidence)
                out.append((side, f"หลักฐานขั้นเอกสารขัดกัน ระบบไม่ระบุขั้นให้ — ที่พบ: {found}"))
            elif bf.stage_status == "not_found":
                out.append((side, "ไม่พบคำบอกขั้นเอกสาร (ร่าง พ.ร.บ./พ.ร.บ.) บนบรรทัดชื่อเอกสาร — เล่มร่างมักไม่พิมพ์คำว่า "
                                  "\"ร่าง\" บนปก · ป้ายคู่ฉบับไม่ได้ยืนยันจากเอกสาร ตรวจจากปก/ทะเบียนเล่ม"))
            elif bf.stage_origin == "register":
                out.append((side, f"ขั้นเอกสาร \"{STAGE_LABELS.get(bf.stage, bf.stage)}\" มาจากทะเบียนดาวน์โหลด "
                                  "(หน้าเว็บที่ดาวน์โหลดไฟล์) — ข้อความในเล่มไม่ได้ระบุขั้น"))
        return out

    def year_of(self, side: str) -> int | None:
        """ปีงบที่รู้แน่ — ผู้ตรวจยืนยันจากภาพหน้า (มาก่อน) หรือระบบอ่านได้ชัด (None = ยังไม่รู้)"""
        bf = self.facts_a if side == "A" else self.facts_b
        conf = self.year_confirms.get(side)
        if conf:
            return int(conf["year"])
        return bf.fiscal_year if bf.year_status in YEAR_SETTLED and bf.fiscal_year else None

    def year_confirmable(self, side: str) -> bool:
        """ฟอร์มยืนยันปีของฉบับนี้ใช้ได้ไหม — ระบบอ่านปีไม่แน่ชัด และรอบนี้ยังไม่ถูกแทน"""
        bf = self.facts_a if side == "A" else self.facts_b
        return bf.year_status not in YEAR_SETTLED and not self.superseded_by

    def used_year(self, side: str) -> int | None:
        """ปีงบที่ผลเทียบที่บันทึกไว้ **ใช้คำนวณจริง** (อาจเป็นปีที่อนุมาน/ไม่มีปี)"""
        return (self.facts_a if side == "A" else self.facts_b).fiscal_year

    @property
    def year_mismatch(self) -> list:
        """ฉบับที่ปีที่รู้แน่ต่างจากปีที่ใช้คำนวณ (รวมกรณีเดิมไม่มีปี) — ผลที่บันทึกไว้ใช้ไม่ได้ ต้องคำนวณซ้ำ"""
        return [s for s in ("A", "B") if self.year_of(s) is not None and self.year_of(s) != self.used_year(s)]

    @property
    def mode_for_years(self) -> str:
        ya, yb = self.year_of("A"), self.year_of("B")
        if ya is None or yb is None:
            return ""
        return cmp.MODE_SAME_YEAR if ya == yb else cmp.MODE_CROSS_YEAR

    @property
    def needs_rerun(self) -> bool:
        """ต้องคำนวณซ้ำ: ปีที่ใช้ต่างจากปีที่รู้แน่ หรือรูปแบบการเทียบไม่ตรงกับปี (แม้โหมดเดิมจะตรงก็ตาม)"""
        return bool(self.year_mismatch) or bool(self.mode_for_years and self.mode_for_years != self.result.mode)

    def use_of(self, f) -> str:
        if f.info:
            return "info"
        d = self.decisions.get(f.id)
        return DECISION_USE.get(d["choice"], "open") if d else "pending"

    @property
    def use_counts(self) -> dict:
        out = {"usable": 0, "excluded": 0, "open": 0, "pending": 0}
        for f in self.result.findings:
            u = self.use_of(f)
            if u in out:
                out[u] += 1
        return out


#: รอบที่บันทึกแล้ว **ไม่ถูกแก้** (คำตัดสิน · ปีที่ยืนยัน · ลิงก์รอบใหม่ อยู่ตารางของตัวเอง) — เก็บส่วนที่แยก JSON แล้ว
#: (ผลเทียบ + ข้อเท็จจริงสองฉบับ ราว 4 MB ต่อรอบ 300 ข้อ) ไว้ในหน่วยความจำ ไม่ต้องแยก ~1.2 MB ใหม่ทุกคำขอ/ทุกภาพ ·
#: ส่วนที่เปลี่ยนได้อ่านจากฐานข้อมูลใหม่ทุกครั้ง (:func:`pdfpair_repo.run_state`) และรอบที่ไม่มีในฐานข้อมูลแล้ว
#: ไม่ถูกเสิร์ฟจากที่นี่ · แก้แถวรอบตรง ๆ (เทสต์/เครื่องมือ) ต้องเรียก :func:`forget_cached_run`
RUN_CACHE_MAX = 12
BRIEF_CACHE_MAX = 512
_run_mem: "OrderedDict[tuple, tuple]" = OrderedDict()
_brief_mem: "OrderedDict[tuple, dict]" = OrderedDict()
_run_lock = threading.Lock()


def _run_key(rid: str) -> tuple:
    return (str(config.DB_PATH), rid)


def _remember(mem: OrderedDict, key: tuple, value, cap: int) -> None:
    with _run_lock:
        mem[key] = value
        mem.move_to_end(key)
        while len(mem) > cap:
            mem.popitem(last=False)


def _parsed_run(rid: str):
    """(แถวรอบที่ไม่มี JSON ก้อนใหญ่, CompareResult, BookFacts A, BookFacts B) — วัตถุใช้ร่วมกันข้ามคำขอ ห้ามแก้"""
    key = _run_key(rid)
    with _run_lock:
        hit = _run_mem.get(key)
        if hit is not None:
            _run_mem.move_to_end(key)
            return hit
    r = pdfpair_repo.get_run(rid)
    if r is None:
        return None
    hit = (r, cmp.CompareResult.from_dict(r.pop("result")),
           ex.BookFacts.from_dict(r.pop("facts_a")), ex.BookFacts.from_dict(r.pop("facts_b")))
    _remember(_run_mem, key, hit, RUN_CACHE_MAX)
    return hit


def forget_cached_run(rid: str) -> None:
    """ทิ้งผลที่แยก JSON ไว้ของรอบ ``rid`` — ทางปกติของระบบไม่แก้รอบที่บันทึกแล้ว ใช้เมื่อแก้แถวในฐานข้อมูลตรง ๆ"""
    with _run_lock:
        _run_mem.pop(_run_key(rid), None)
        _brief_mem.pop(_run_key(rid), None)


def clear_run_cache() -> None:
    with _run_lock:
        _run_mem.clear()
        _brief_mem.clear()


def view(rid: str) -> RunView | None:
    st = pdfpair_repo.run_state(rid)
    if st is None:
        forget_cached_run(rid)
        return None
    parsed = _parsed_run(rid)
    if parsed is None:
        return None
    r, res, facts_a, facts_b = parsed
    decs = st["decisions"]
    groups = []
    for key, label in TOPICS:
        g = TopicGroup(key, label)
        for f in res.findings:
            if f.topic != key:
                continue
            (g.info if f.info else g.findings).append(f)
            if not f.info and f.id in decs:
                g.decided += 1
        if g.findings or g.info:
            groups.append(g)
    # สำเนาชั้นบนต่อคำขอ — ผู้เรียกที่ตั้งค่าช่องของข้อเท็จจริง/แถวรอบ (เช่น เทสต์จำลองปี) ไม่รั่วเข้าแคชที่ใช้ร่วมกัน
    return RunView(dict(r), res, groups, decs, copy.copy(facts_a), copy.copy(facts_b), st["year_confirms"],
                   st["superseded_by"], st["supersedes"])


def _briefs(run_ids: list) -> dict:
    """ส่วนที่ไม่เปลี่ยนของรอบสำหรับหน้ารายการ (รหัสข้อที่ต้องตรวจ + ขั้น/ปีที่อ่านได้) — เก็บไว้ต่อรอบ"""
    out, missing = {}, []
    with _run_lock:
        for rid in run_ids:
            hit = _brief_mem.get(_run_key(rid))
            if hit is None:
                missing.append(rid)
            else:
                out[rid] = hit
    for rid, b in pdfpair_repo.run_briefs(missing).items():
        _remember(_brief_mem, _run_key(rid), b, BRIEF_CACHE_MAX)
        out[rid] = b
    return out


def run_list(limit: int = 50) -> list[dict]:
    """รอบล่าสุด + ป้าย/ไฟล์ของสองฉบับ + จำนวนข้อที่ต้องตรวจ/ยังไม่ตัดสิน — ไม่แยก JSON ทั้งรอบ ·
    นับแบบเดียวกับ :class:`RunView` (``actionable`` = ข้อที่ไม่ใช่ข้อมูลประกอบ · ``pending`` = ในนั้นที่ยังไม่ตัดสิน)"""
    rows = pdfpair_repo.list_runs(limit=limit)
    ids = [r["id"] for r in rows]
    briefs, state = _briefs(ids), pdfpair_repo.list_state(ids)
    out = []
    for r in rows:
        b, st = briefs.get(r["id"]), state[r["id"]]
        if b is None:                       # ถูกลบระหว่างสองคำสั่ง
            continue
        sides = {s: {"label": side_label_of(s, b["facts"][s]["stage"] or "", b["facts"][s]["stage_status"] or "",
                                            b["facts"][s]["fiscal_year"], b["facts"][s]["year_status"] or "",
                                            st["years"].get(s)),
                     "file": r[f"{s.lower()}_name"]} for s in ("A", "B")}
        out.append({**r, "sides": sides, "superseded_by": st["superseded_by"],
                    "counts": {"actionable": len(b["actionable"]),
                               "pending": len(b["actionable"] - st["decided"])}})
    return out


def _blocked(v: "RunView") -> None:
    if v.superseded_by:
        raise RunSuperseded(v.superseded_by)


def decide(rid: str, fid: str, choice: str, note: str) -> None:
    v = view(rid)
    if v is None or v.finding(fid) is None:
        raise PairError("ไม่พบข้อสังเกตที่ระบุ")
    _blocked(v)
    if choice not in DECISION_LABELS:
        raise PairError("กรุณาเลือกผลการตรวจ")
    prev = v.decisions.get(fid)
    if prev and prev["choice"] != choice and not (note or "").strip():
        raise PairError("เปลี่ยนผลการตรวจเดิม ต้องระบุเหตุผลในหมายเหตุ")
    # ตรวจซ้ำในธุรกรรมเขียน — คำขอพร้อมกัน (สองแท็บ · คำนวณซ้ำ) อาจเปลี่ยนสถานะหลังการตรวจข้างบน
    try:
        pdfpair_repo.decide(rid, fid, choice, (note or "").strip())
    except pdfpair_repo.SupersededError as e:
        raise RunSuperseded(e.new_run_id)
    except pdfpair_repo.NoteRequired:
        raise PairError("เปลี่ยนผลการตรวจเดิม ต้องระบุเหตุผลในหมายเหตุ")


UNIT_ORIGIN_LABELS = {"row": "หน่วยพิมพ์ในแถว", "text_column": "หน่วยจากคอลัมน์หน่วยนับ",
                      "table_decl": "หน่วยจากบรรทัดประกาศหน่วยของตาราง",
                      "profile_default": "หน่วยตามค่าตั้งต้นของโปรไฟล์ — ไม่พบในเอกสาร",
                      "assumed": "สมมติเป็นบาท — ไม่พบหน่วยในเอกสาร"}


def unit_note(side) -> str:
    """ที่มาของหน่วย — ใช้แสดงคู่กับค่า เพื่อไม่ให้หน่วยที่ไม่มีหลักฐานดูเหมือนอ่านตรงจากเอกสาร"""
    return UNIT_ORIGIN_LABELS.get(getattr(side, "unit_origin", ""), "")


def raw_note(side) -> str:
    """ข้อความดิบในเซลล์ — แสดงเฉพาะเมื่อต่างจากค่าที่แสดง (เช่น ขีด · ลบมีช่องว่าง · หน่วยติดตัวเลข)"""
    from decimal import Decimal, InvalidOperation
    raw = (getattr(side, "raw", "") or "").strip()
    if not raw:
        return ""
    try:
        shown = fmt(Decimal(side.value), side.unit) if side.value else ""
    except InvalidOperation:
        shown = side.value
    return "" if raw == shown else f"พิมพ์ว่า “{raw}”"


def amount_text(side, unit: str = "") -> str:
    from decimal import Decimal, InvalidOperation
    if getattr(side, "status", "") == "dash":
        return "ขีด (–) ไม่มีค่า"
    if getattr(side, "status", "") == "blank":
        return "ช่องว่าง (มีแถว ไม่มีตัวเลข)"
    if not side.value:
        return "—"
    try:
        return fmt(Decimal(side.value), side.unit or unit) + (f" {side.unit or unit}" if (side.unit or unit) else "")
    except InvalidOperation:
        return side.value


ROUNDING_POLICY = cmp.ROUNDING_POLICY
#: ป้ายธงต้องยืนยัน — ชั้นเว็บ/API อ่านผ่านชั้นบริการ (route ไม่ import ``redbook.pdfbook`` ตรง)
CAVEAT_LABELS = cmp.CAVEAT_LABELS


def tolerance_text(f) -> str:
    """เกณฑ์ปัดเศษของกฎผลรวม ("" = ไม่ใช่กฎผลรวม) — อยู่ในเกณฑ์ไม่ได้แปลว่าตรงเป๊ะ"""
    from decimal import Decimal, InvalidOperation
    if not getattr(f, "tolerance", ""):
        return ""
    try:
        t = Decimal(f.tolerance)
    except InvalidOperation:
        return f.tolerance
    if not t:
        return "กฎเคร่งครัด (0)"
    basis = cmp.TOLERANCE_BASIS_LABELS.get(getattr(f, "tolerance_basis", "") or "assumed_independent_rounding", "")
    return f"±{fmt(t, f.unit)} {f.unit}".strip() + (f" ({basis})" if basis else "")


def part_flags(p: dict) -> str:
    return " · ".join(cmp.CAVEAT_LABELS[x] for x in p.get("flags", []) if x in cmp.CAVEAT_LABELS)


def parts_text(f) -> str:
    return " | ".join(f"{p['label']} = {p.get('raw') or p.get('value')} {p.get('unit', '')} (หน้า {p.get('page')})"
                      + (f" [{part_flags(p)}]" if part_flags(p) else "") for p in getattr(f, "parts", []))


def delta_text(f) -> str:
    from decimal import Decimal, InvalidOperation
    if not f.delta:
        return ""
    try:
        d = Decimal(f.delta)
    except InvalidOperation:
        return f.delta
    sign = "+" if d > 0 else ""
    return f"{sign}{fmt(d, f.unit)}" + (f" {f.unit}" if f.unit else "")


def text_diff(a: str, b: str) -> tuple[list, list]:
    """ส่วนที่ต่างของข้อความสองฉบับ — ``[(ชนิด, ข้อความ)]`` ชนิด = same | del | ins"""
    sm = SequenceMatcher(None, a or "", b or "", autojunk=False)
    da, db = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            da.append(("same", a[i1:i2]))
            db.append(("same", b[j1:j2]))
        else:
            if i2 > i1:
                da.append(("del", a[i1:i2]))
            if j2 > j1:
                db.append(("ins", b[j1:j2]))
    return da, db


#: ภาพหลักฐานที่วาดแล้ว (ในหน่วยความจำของเครื่องนี้เท่านั้น · ไม่เขียนลงดิสก์) — ระบบตั้ง
#: ``Cache-Control: no-store`` ทุกคำตอบ เบราว์เซอร์จึงไม่เก็บภาพ · กุญแจรวม SHA-256 ของไฟล์ ⇒
#: แนบ PDF ใหม่แล้วไม่ได้ภาพเก่า · จำกัดขนาดรวม เก่าสุดออกก่อน
PNG_CACHE_MAX_BYTES = 96 * 1024 * 1024
_png_cache: "OrderedDict[tuple, bytes]" = OrderedDict()
_png_cache_bytes = 0
_png_lock = threading.Lock()


def _png_cached(key: tuple, make) -> bytes:
    global _png_cache_bytes
    with _png_lock:
        hit = _png_cache.get(key)
        if hit is not None:
            _png_cache.move_to_end(key)
            return hit
    png = make()
    with _png_lock:
        if key not in _png_cache:
            _png_cache[key] = png
            _png_cache_bytes += len(png)
            while _png_cache_bytes > PNG_CACHE_MAX_BYTES and len(_png_cache) > 1:
                _k, old = _png_cache.popitem(last=False)
                _png_cache_bytes -= len(old)
    return png


def clear_png_cache() -> None:
    global _png_cache_bytes
    with _png_lock:
        _png_cache.clear()
        _png_cache_bytes = 0


def evidence_png(rid: str, fid: str, side: str, full: bool = False) -> bytes | None:
    v = view(rid)
    if v is None or side not in ("A", "B"):
        return None
    f = v.finding(fid)
    if f is None:
        return None
    s = f.a if side == "A" else f.b
    if not s.page:
        return None
    path, row = _side_file(v.run["project_id"], side)
    if row["sha256"] != v.run[f"{side.lower()}_sha256"]:
        raise PairError("PDF ที่แนบอยู่ตอนนี้ไม่ใช่ไฟล์เดียวกับที่ใช้ในรอบเทียบนี้ — เปิดหลักฐานไม่ได้")
    zoom = 1.6

    def make() -> bytes:
        png = reader.render_png(path, s.page, highlight=tuple(s.bbox) if s.bbox else None, zoom=zoom)
        return png if (full or not s.bbox) else _crop(png, s.bbox, zoom)
    key = (row["sha256"], s.page, tuple(s.bbox) if s.bbox else None, bool(full or not s.bbox), zoom)
    return _png_cached(key, make)


_size_mem: dict = {}      # (SHA-256 ของไฟล์, หน้า) → (กว้าง, สูง)


def page_size_of(v: "RunView", side: str, page: int) -> list | None:
    """[กว้าง, สูง] เป็น pt ของหน้า ``page`` ฉบับ ``side`` — กรอบ CropBox แบบเดียวกับพิกัด bbox ของตัวอ่านและภาพที่วาด
    (หน้าบ้านใช้เลื่อนภาพทั้งหน้าไปที่กรอบ) · ไฟล์ไม่ตรงรอบ/ไม่มีหน้า = ``None``"""
    if side not in ("A", "B") or not page:
        return None
    try:
        path, row = _side_file(v.run["project_id"], side)
    except PairError:
        return None
    if row["sha256"] != v.run[f"{side.lower()}_sha256"]:
        return None
    key = (row["sha256"], int(page))
    if key not in _size_mem:
        try:
            _size_mem[key] = [round(x, 2) for x in reader.page_size(path, int(page))]
        except (IndexError, ValueError, reader.ReaderUnavailable):
            return None
    return list(_size_mem[key])


def page_png(rid: str, side: str, page: int) -> bytes | None:
    """ภาพทั้งหน้าไว้ให้ผู้ตรวจดูปีงบก่อนยืนยัน — เปิดได้เฉพาะหน้าที่รอบนี้อ่านอยู่แล้ว
    (หน้าต้นไฟล์ที่ใช้หาปี + ช่วงหน้าของหน่วยงาน) ไม่เปิดหน้าของหน่วยงานอื่น"""
    v = view(rid)
    if v is None or side not in ("A", "B"):
        return None
    sc = v.run["scope"][side]
    allowed = set(range(1, min(META_FRONT_PAGES, sc.get("pages_in_file") or META_FRONT_PAGES) + 1))         | set(range(int(sc["first"]), int(sc["last"]) + 1))
    if page not in allowed:
        return None
    path, row = _side_file(v.run["project_id"], side)
    if row["sha256"] != v.run[f"{side.lower()}_sha256"]:
        raise PairError("PDF ที่แนบอยู่ตอนนี้ไม่ใช่ไฟล์เดียวกับที่ใช้ในรอบเทียบนี้ — เปิดภาพไม่ได้")
    return _png_cached((row["sha256"], page, None, True, 1.2),
                       lambda: reader.render_png(path, page, zoom=1.2))


def _crop(png: bytes, bbox, zoom: float) -> bytes:
    from PIL import Image
    from ..evidence.pdftext import _encode_png
    img = Image.open(io.BytesIO(png)).convert("RGB")
    y0 = max(0, int((bbox[1] - CROP_MARGIN_PT) * zoom))
    y1 = min(img.height, int((bbox[3] + CROP_MARGIN_PT) * zoom))
    img = img.crop((0, y0, img.width, y1))
    return _encode_png(img.tobytes(), img.width, img.height)


# ── ด่านก่อนส่งออก (Preflight) ──────────────────────────────────────────────────
@dataclass
class Check:
    key: str
    label: str
    ok: bool
    detail: str
    action_label: str = ""
    action_href: str = ""
    action_post: bool = False     # ปุ่มเป็นฟอร์ม POST (มี CSRF) ไม่ใช่ลิงก์


@dataclass
class Preflight:
    checks: list
    use_status: str = "in_review"     # in_review · review_complete · validated · blocked
    use_reasons: list = field(default_factory=list)
    use_counts: dict = field(default_factory=dict)    # usable · excluded · open · pending (ข้อที่ต้องตรวจทั้งหมด)
    actionable: int = 0

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def failing(self) -> list:
        return [c for c in self.checks if not c.ok]

    @property
    def use_breakdown(self) -> str:
        """ตัวหารเต็มของรอบ — ทุกข้อที่ต้องตรวจอยู่ในหมวดใดหมวดหนึ่งเสมอ (ข้อที่ไม่นับไม่หายจากตัวหาร)"""
        u = self.use_counts
        return (f"ข้อที่ต้องตรวจ {self.actionable} ข้อ = ปิดแล้ว {u.get('usable', 0)} · ไม่นับ {u.get('excluded', 0)} · "
                f"ยังไม่ปิด {u.get('open', 0)} · ยังไม่ตัดสิน {u.get('pending', 0)}")


def preflight(rid: str, v: "RunView | None" = None) -> Preflight | None:
    """ด่านก่อนส่งออกของรอบเทียบเล่ม — **ระบบบังคับฝั่งเซิร์ฟเวอร์** (ส่งออก CSV ไม่ได้ถ้าไม่ผ่าน) ·
    ``v`` = มุมมองของรอบนี้ที่ผู้เรียกเพิ่งอ่าน (ประเมินบน snapshot เดียวกัน ไม่อ่านซ้ำ)

    1. PDF ที่แนบยังเป็นไฟล์เดียวกับรอบนี้ (SHA-256) — หลักฐาน A/B ที่ผู้ตรวจดูต้องมาจากไฟล์ที่ใช้เทียบ
    2. ปีงบของทั้งสองฉบับ: ระบบอ่านได้แน่ชัด หรือผู้ตรวจยืนยันจากภาพหน้าแล้ว และรูปแบบการเทียบของรอบ
       ตรงกับปีนั้น — ปีผิดทำให้การปรับลดจริงกลายเป็น "ข้อมูลประกอบ" ที่ไม่มีใครตัดสิน
    3. ข้อที่ระบบอ่านไม่ได้ (หน้าไม่มีชั้นข้อความ · แถวที่จัดไม่ได้) ตัดสินครบ
    4. ข้อที่ติด "ต้องให้คนยืนยัน" ตัดสินครบ
    5. ตัดสินครบทุกข้อที่ต้องตรวจ
    """
    v = v if v is not None and v.rid == rid else view(rid)
    if v is None:
        return None
    base = f"/pdfpair/runs/{rid}"
    checks: list[Check] = []
    if v.superseded_by:
        checks.append(Check("superseded", "รอบนี้ยังเป็นผลปัจจุบัน", False,
                            "ถูกแทนด้วยรอบที่คำนวณด้วยปีงบที่ยืนยันแล้ว — ผลและคำตัดสินเดิมเก็บไว้ดูย้อนหลัง",
                            "ไปรอบใหม่", f"/pdfpair/runs/{v.superseded_by}"))

    bad_files = []
    for side in ("A", "B"):
        try:
            _p, row = _side_file(v.run["project_id"], side)
            if row["sha256"] != v.run[f"{side.lower()}_sha256"]:
                bad_files.append(side)
        except PairError:
            bad_files.append(side)
    checks.append(Check("files", "PDF ที่แนบเป็นไฟล์เดียวกับที่ใช้เทียบในรอบนี้", not bad_files,
                        "ตรงทั้งสองฉบับ (SHA-256)" if not bad_files else
                        f"ฉบับ {' และ '.join(bad_files)} ถูกเปลี่ยนหรือหายไป — หลักฐานที่เปิดดูจะไม่ใช่ไฟล์ที่ใช้เทียบ",
                        "ไปหน้าแนบ PDF", f"/projects/{v.run['project_id']}/pdfpair"))

    ya, yb = v.year_of("A"), v.year_of("B")
    unknown = [s for s, y in (("A", ya), ("B", yb)) if y is None]
    if unknown:
        checks.append(Check("years", "ผลคำนวณด้วยปีงบที่รู้แน่ของทั้งสองฉบับ", False,
                            f"ฉบับ {' และ '.join(unknown)} ระบบอ่านปีไม่แน่ชัด — ดูปีจากภาพหน้าเอกสารแล้วยืนยัน",
                            "ยืนยันปีงบ", f"{base}/preflight#years"))
    elif v.needs_rerun:
        # ปีที่ยืนยันต่างจากปีที่ใช้คำนวณ (แม้โหมดยังเหมือนเดิม) — ผลที่บันทึกไว้ใช้ไม่ได้ ต้องคำนวณซ้ำเป็นรอบใหม่
        used = " · ".join(f"{s} {v.used_year(s) or 'ไม่มีปี'}" for s in ("A", "B"))
        want = v.mode_for_years
        if v.superseded_by:
            # รอบนี้ถูกแทนแล้ว — ไม่เสนอปุ่มคำนวณซ้ำอีก (กดได้ก็ถูกปฏิเสธ แต่ไม่ควรชวนให้ส่ง POST ซ้ำ)
            checks.append(Check("years", "ผลคำนวณด้วยปีงบที่รู้แน่ของทั้งสองฉบับ", False,
                                f"ผลนี้คำนวณด้วยปี {used} — คำนวณใหม่ด้วยปีที่ยืนยันแล้วเป็นรอบ {v.superseded_by}",
                                "ไปรอบใหม่", f"/pdfpair/runs/{v.superseded_by}/preflight"))
        else:
            checks.append(Check("years", "ผลคำนวณด้วยปีงบที่รู้แน่ของทั้งสองฉบับ", False,
                                f"ผลนี้คำนวณด้วยปี {used} แต่ปีที่รู้แน่คือ A {ya} · B {yb} "
                                f"(ต้องเทียบแบบ {MODE_LABELS[want]}) — สร้างรอบใหม่ที่คำนวณด้วยปีที่ยืนยัน "
                                "รอบนี้จะถูกบล็อกแต่เก็บผลและคำตัดสินเดิมไว้",
                                "สร้างรอบใหม่ด้วยปีที่ยืนยัน", f"{base}/rerun", action_post=True))
    else:
        how = " (ผู้ตรวจยืนยัน)" if (v.year_confirms or v.supersedes) else ""
        checks.append(Check("years", "ผลคำนวณด้วยปีงบที่รู้แน่ของทั้งสองฉบับ", True,
                            f"ปี {ya} ↔ {yb} · เทียบแบบ {MODE_LABELS[v.result.mode]}{how}"))

    pending = [f for f in v.result.findings if not f.info and f.id not in v.decisions]
    unread = [f for f in pending if f.kind == cmp.K_UNREAD]
    checks.append(Check("unread", "ข้อที่ระบบอ่านไม่ได้ได้รับการตรวจแล้ว", not unread,
                        "ไม่มีข้อค้าง" if not unread else f"เหลือ {len(unread)} ข้อ (หน้าไม่มีชั้นข้อความ/แถวที่จัดไม่ได้)",
                        "เปิดข้อแรกที่ค้าง", f"{base}/f/{unread[0].id}" if unread else ""))
    cav = [f for f in pending if f.caveats]
    checks.append(Check("caveats", "ข้อที่ต้องให้คนยืนยันได้รับการตรวจแล้ว", not cav,
                        "ไม่มีข้อค้าง" if not cav else f"เหลือ {len(cav)} ข้อ (หน่วย/คอลัมน์/ปีไม่ได้มาจากเอกสารตรง ๆ)",
                        "เปิดข้อแรกที่ค้าง", f"{base}/f/{cav[0].id}" if cav else ""))
    checks.append(Check("decided", "ตัดสินครบทุกข้อที่ต้องตรวจ", not pending,
                        f"ครบ {v.actionable} ข้อ" if not pending else f"เหลือ {len(pending)} จาก {v.actionable} ข้อ",
                        "เปิดข้อแรกที่ค้าง", f"{base}/f/{pending[0].id}" if pending else ""))
    uc = v.use_counts
    pf = Preflight(checks, use_counts=dict(uc), actionable=v.actionable)
    if v.superseded_by:
        pf.use_status = "blocked"
    elif not pf.ok:
        pf.use_status = "in_review"
    elif uc["open"]:
        pf.use_status = "review_complete"
        pf.use_reasons = [f"{uc['open']} ข้อยังไม่ปิด (\"{DECISION_LABELS['needs_more']}\" หรือ "
                          f"\"{DECISION_LABELS['mismatch']}\") — ผู้ตรวจต้องตรวจแถวนั้นด้วยวิธีอื่นแล้วเปลี่ยนคำตัดสินเอง"]
    else:
        pf.use_status = "validated"
    if uc["excluded"]:
        pf.use_reasons.append(f"ไม่นับ {uc['excluded']} ข้อ (ผู้ตรวจระบุว่านอกขอบเขตที่กำหนด) — รายงานจำนวนนี้คู่กับผลเสมอ")
    return pf


def rerun(rid: str) -> str:
    """คำนวณรอบใหม่ด้วยปีงบที่ผู้ตรวจยืนยัน — ช่วงหน้า/ไฟล์เดิม · บันทึกลิงก์รอบเดิม→ใหม่ + Audit ·
    รอบเดิมถูกบล็อก ผลและคำตัดสินเดิมไม่ถูกแก้หรือคัดลอกทับ (ผู้ตรวจตัดสินรอบใหม่เอง)"""
    v = view(rid)
    if v is None:
        raise PairError("ไม่พบรอบเทียบ")
    _blocked(v)
    if not v.needs_rerun:
        raise PairError("ปีงบที่ใช้คำนวณตรงกับปีที่รู้แน่แล้ว ไม่ต้องคำนวณซ้ำ")
    ya, yb = v.year_of("A"), v.year_of("B")
    if ya is None or yb is None:
        raise PairError("ยืนยันปีงบของทั้งสองฉบับก่อน")
    for side in ("A", "B"):
        _p, row = _side_file(v.run["project_id"], side)
        if row["sha256"] != v.run[f"{side.lower()}_sha256"]:
            raise PairError(f"PDF ฉบับ {side} ที่แนบอยู่ไม่ใช่ไฟล์ของรอบนี้ — คำนวณซ้ำไม่ได้ เริ่มรอบเทียบใหม่แทน")
    sc = v.run["scope"]
    pages_read = {s: sc[s]["pages_read"] for s in ("A", "B") if "pages_read" in sc[s]}
    shelf = {s: sc[s]["shelf_volume"] for s in ("A", "B") if "shelf_volume" in sc[s]}
    stages = {s: sc[s]["stage_register"] for s in ("A", "B") if sc[s].get("stage_register")}
    from ..pdfbook import scope as _scope
    method = sc["A"].get("method", "") if sc["A"].get("method") == _scope.METHOD_TOC else ""
    reason = ("ปีที่ยืนยันต่างจากปีที่ใช้คำนวณ: " + " · ".join(
        f"{s} {v.used_year(s) or 'ไม่มีปี'}→{v.year_of(s)}" for s in v.year_mismatch)) if v.year_mismatch \
        else f"รูปแบบการเทียบไม่ตรงกับปี: {v.result.mode}→{v.mode_for_years}"
    # รอบใหม่ + ลิงก์ + Audit บันทึกในธุรกรรมเดียว (``save_run``) — ล้มกลางทาง/ไฟล์เปลี่ยน = ไม่มีอะไรถูกบันทึก
    # รอบเดิมจึงไม่ถูกบล็อกโดยไม่มีรอบใหม่ที่สมบูรณ์ · กดซ้ำพร้อมกัน = คนช้ากว่าได้ ``SupersededError``
    try:
        return run(v.run["project_id"], agency=v.run["agency"], mode=v.mode_for_years,
                   a_first=str(sc["A"]["first"]), a_last=str(sc["A"]["last"]),
                   b_first=str(sc["B"]["first"]), b_last=str(sc["B"]["last"]), range_method=method,
                   pages_read=pages_read or None, shelf=shelf or None, years={"A": ya, "B": yb},
                   supersedes={"run_id": rid, "reason": reason, "years": {"A": ya, "B": yb},
                               "used": {"A": v.used_year("A"), "B": v.used_year("B")}},
                   stages=stages or None)
    except pdfpair_repo.SupersededError as e:
        raise PairError(f"รอบนี้ถูกแทนด้วยรอบ {e.new_run_id} ไปแล้ว (มีการกดคำนวณซ้ำพร้อมกัน) — "
                        "ผลที่คำนวณครั้งนี้ไม่ถูกบันทึก เปิดรอบใหม่นั้นแทน")


def confirm_year(rid: str, side: str, year: str, note: str, seen: bool) -> None:
    v = view(rid)
    if v is None:
        raise PairError("ไม่พบรอบเทียบ")
    _blocked(v)
    if side not in ("A", "B"):
        raise PairError("ฉบับไม่ถูกต้อง")
    if not seen:
        raise PairError("กรุณาดูปีงบจากภาพหน้าเอกสารก่อน แล้วติ๊กยืนยัน")
    try:
        y = int(str(year).strip())
    except ValueError:
        raise PairError("ปีงบต้องเป็นตัวเลข พ.ศ. 4 หลัก")
    if not 2500 <= y <= 2700:
        raise PairError("ปีงบต้องเป็น พ.ศ. (เช่น 2570)")
    bf = v.facts_a if side == "A" else v.facts_b
    note = (note or "").strip()
    prev = v.year_confirms.get(side)
    if prev and int(prev["year"]) != y and not note:
        raise PairError(f"เปลี่ยนปีที่ยืนยันไว้ (ปี {prev['year']}) ต้องระบุเหตุผลในหมายเหตุ")
    if bf.fiscal_year and bf.fiscal_year != y and not note:
        raise PairError(f"ปีที่ยืนยันต่างจากที่ระบบอ่านได้ (ปี {bf.fiscal_year}) ต้องระบุหน้า/ข้อความที่ใช้ยืนยันในหมายเหตุ")
    try:                                    # ตรวจซ้ำในธุรกรรมเขียน (เหมือน decide)
        pdfpair_repo.confirm_year(rid, side, y, note, {
            "fiscal_year": bf.fiscal_year, "year_status": bf.year_status,
            "year_origin": bf.year_origin, "candidates": bf.year_candidates})
    except pdfpair_repo.SupersededError as e:
        raise RunSuperseded(e.new_run_id)
    except pdfpair_repo.NoteRequired as e:
        raise PairError(f"เปลี่ยนปีที่ยืนยันไว้ (ปี {e.previous['year']}) ต้องระบุเหตุผลในหมายเหตุ")


#: ป้ายเหตุการณ์ Audit ของสายเทียบเล่ม (หน้าเว็บเดิม + API ใช้ชุดเดียวกัน)
AUDIT_ACTION_LABELS = {"pdfpair_run_completed": "สร้างรอบเทียบ", "pdfpair_decision": "บันทึกผลการตรวจ",
                       "pdfpair_year_confirmed": "ยืนยันปีงบ", "pdfpair_exported": "ส่งออก CSV",
                       "pdfpair_run_superseded": "ถูกแทนด้วยรอบใหม่"}


def audit_summary(e: dict) -> str:
    """สรุปเหตุการณ์ Audit ของรอบเป็นภาษาคน — ข้อมูลเต็ม (JSON) ยังแสดงคู่กันเสมอ"""
    import json
    try:
        d = json.loads(e.get("detail_json") or "{}")
    except ValueError:
        return ""
    act = e.get("action")
    if act == "pdfpair_run_completed":
        return ((f"คำนวณแทนรอบ {d['supersedes']} · " if d.get("supersedes") else "")
                + f"ข้อสังเกต {d.get('findings', '?')} ข้อ · SHA-256 A {str(d.get('a_sha256', ''))[:12]}… "
                f"B {str(d.get('b_sha256', ''))[:12]}… · ตัวสกัด {d.get('versions', {}).get('pdfbook', '')}")
    if act == "pdfpair_decision":
        prev = d.get("previous") or {}
        s = DECISION_LABELS.get(d.get("choice", ""), d.get("choice", ""))
        if prev:
            s += f" (เดิม: {DECISION_LABELS.get(prev.get('choice', ''), prev.get('choice', ''))})"
        return s + (f" · หมายเหตุ: {d['note']}" if d.get("note") else "")
    if act == "pdfpair_year_confirmed":
        det = d.get("detected") or {}
        return (f"ยืนยันปี {d.get('year')} · ระบบอ่านได้ {det.get('fiscal_year') or '—'} ({det.get('year_status') or '—'})"
                + (f" · หมายเหตุ: {d['note']}" if d.get("note") else ""))
    if act == "pdfpair_exported":
        s = f"{d.get('rows', '?')} แถวข้อมูล · SHA-256 ของไฟล์ที่ดาวน์โหลด {str(d.get('sha256', ''))[:16]}…"
        if d.get("use_status"):
            s += f" · {USE_STATUS_LABELS.get(d['use_status'], d['use_status'])}"
        if d.get("use_counts"):
            s += " · " + Preflight([], use_counts=d["use_counts"], actionable=d.get("actionable", 0)).use_breakdown
        return s
    if act == "pdfpair_run_superseded":
        return f"ถูกแทนด้วยรอบ {d.get('new_run_id', '')} · {d.get('reason', '')}"
    return ""


CSV_ENCODING = "utf-8"


def csv_records(data: bytes) -> int:
    """จำนวนระเบียนข้อมูลในไฟล์ CSV ที่ส่งออก (ไม่นับหัวตาราง) — นับด้วย CSV parser
    หมายเหตุหลายบรรทัดในช่องเดียวจึงนับเป็นหนึ่งระเบียน"""
    text = data.decode(CSV_ENCODING)
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"), newline="")))
    return max(0, len(rows) - 1)


def export_csv_checked(rid: str) -> bytes:
    """ส่งออก CSV หลังผ่านด่าน — ไม่ผ่าน = ``PairError`` · คืน **ไบต์ที่ส่งให้เบราว์เซอร์จริง** (รวม BOM)
    และบันทึก Audit ด้วย SHA-256 ของไบต์ชุดนั้น + จำนวนระเบียน + สถานะการใช้ผล + รุ่นเครื่องมือ"""
    import hashlib
    v = view(rid)                           # ด่าน + ไฟล์ + Audit มาจาก snapshot เดียวกัน
    pf = preflight(rid, v) if v is not None else None
    if pf is None:
        raise PairError("ไม่พบรอบเทียบ")
    if not pf.ok:
        raise PairError("ยังไม่ผ่านด่านก่อนส่งออก: " + " · ".join(c.label for c in pf.failing))
    data = export_csv(rid, v).encode(CSV_ENCODING)
    try:                                    # รอบถูกแทนหลังผ่านด่าน (คำนวณซ้ำพร้อมกัน) = ไม่บันทึก ไม่ส่งไฟล์
        pdfpair_repo.record_export(rid, hashlib.sha256(data).hexdigest(), csv_records(data),
                                   bytes=len(data), encoding="utf-8-sig", use_status=pf.use_status,
                                   use_counts=pf.use_counts, actionable=pf.actionable,
                                   stages={s: {"stage": bf.stage, "status": bf.stage_status,
                                               "origin": bf.stage_origin}
                                           for s, bf in (("A", v.facts_a), ("B", v.facts_b))},
                                   versions=v.run["versions"])
    except pdfpair_repo.SupersededError as e:
        raise RunSuperseded(e.new_run_id)
    return data


def export_csv(rid: str, v: "RunView | None" = None) -> str:
    v = v if v is not None and v.rid == rid else view(rid)
    if v is None:
        raise PairError("ไม่พบรอบเทียบ")
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["รหัส", "หัวข้อ", "ประเภท", "ข้อมูลประกอบ", "ภายในฉบับ", "รายการ", "ช่อง",
                "ค่าใน A", "ค่าดิบ A", "หน่วย A", "ที่มาหน่วย A", "สถานะ A", "หน้า A",
                "ค่าใน B", "ค่าดิบ B", "หน่วย B", "ที่มาหน่วย B", "สถานะ B", "หน้า B",
                "ผลต่าง (B−A)", "ต้องให้คนยืนยัน", "หมายเหตุระบบ", "องค์ประกอบที่ใช้คำนวณ", "เกณฑ์ปัดเศษ",
                "ผลการตรวจของคน", "หมายเหตุผู้ตรวจ", "เวลาที่ตัดสิน", "การใช้ผล"])
    for f in v.result.findings:
        d = v.decisions.get(f.id) or {}
        w.writerow([f.id, f.topic_label, f.kind_label, "ใช่" if f.info else "", f.within, f.subject,
                    f.column,
                    f.a.value, f.a.raw, f.a.unit, f.a.unit_origin, f.a.status, f.a.page or "",
                    f.b.value, f.b.raw, f.b.unit, f.b.unit_origin, f.b.status, f.b.page or "",
                    f.delta, " · ".join(f.caveats), f.note, parts_text(f), tolerance_text(f),
                    DECISION_LABELS.get(d.get("choice", ""), ""), d.get("note", ""),
                    d.get("decided_at", ""), USE_LABELS[v.use_of(f)]])
    return "﻿" + out.getvalue()


__all__ = ["PairError", "RunSuperseded", "run", "rerun", "page_png", "view", "run_list", "side_label_of",
           "forget_cached_run", "clear_run_cache", "csv_records", "DECISION_USE", "DECISION_WHEN", "DECISION_AFTER", "page_size_of",
           "USE_LABELS",
           "USE_STATUS_LABELS", "decide", "evidence_png", "export_csv", "export_csv_checked",
           "preflight", "confirm_year", "audit_summary", "Preflight", "Check", "text_diff",
           "amount_text", "delta_text", "unit_note", "raw_note", "UNIT_ORIGIN_LABELS", "DECISIONS", "DECISION_LABELS", "TOPICS", "MODE_LABELS",
           "PROFILE_STATUS_LABEL"]
