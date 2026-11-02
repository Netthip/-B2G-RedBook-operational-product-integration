# -*- coding: utf-8 -*-
"""ชั้นเล่ม PDF ในเครื่อง — เลือกเล่ม A/B และหน่วยงาน แล้วเทียบได้ทันที ไม่ต้องหาไฟล์และตัดหน้าเอง

* ระบบ **ไม่ออกอินเทอร์เน็ต** — อ่านเฉพาะโฟลเดอร์ชั้นเล่มที่ดาวน์โหลดไว้แล้วด้วยสคริปต์นอกแพ็กเกจ
  (``scripts/shelf_add.py`` · ``scripts/fetch_dev_volumes.py``) ซึ่งบันทึก URL ทางการ เวลา และ SHA-256 ทุกเล่ม
* โครงโฟลเดอร์: ``manifest.json`` (ชื่อเล่ม ปี ขั้น ลิงก์หน้าเว็บ) + ``register.json`` (SHA-256 ที่ดาวน์โหลด) +
  ``volumes/<key>.pdf`` · ตำแหน่ง = ``REDBOOK_PDF_SHELF`` หรือ ``<data>/pdf_shelf``
* ไฟล์ต้องมี SHA-256 ตรงกับทะเบียน (ไฟล์ถูกเปลี่ยน = ไม่ใช้) · ผูกกับคลังเล่ม (#24) ด้วยรหัสหน้าเว็บของเล่ม
* หาหน้าของหน่วยงานจากสารบัญ (:func:`pdfbook.scope.find_by_toc`) — อ่านเนื้อหาเฉพาะสารบัญต้นเล่ม + แถบเลขหน้า +
  หน้าของหน่วยงานนั้น · **ไม่อ่านเนื้อหาหน้าของหน่วยงานอื่น** · บันทึกหน้าที่อ่านจริงไว้กับรอบเทียบ
* หน่วยงานที่กันไว้ (:data:`PROTECTED_AGENCIES`) ไม่แสดงในรายชื่อ และเลือกไม่ได้
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .. import config, eval_guard, holdout
from ..core.hashing import sha256_file
from ..pdfbook import reader, scope as scope_mod
from ..pdfbook.text import clean, skeleton, squash

SHELF_ENV = "REDBOOK_PDF_SHELF"
#: หน่วยงานที่กันไว้เป็นชุดทดสอบ/หน่วยสงวน — ไม่แสดงและเลือกไม่ได้ (เทียบแบบตัดช่องว่าง/วรรณยุกต์)
PROTECTED_AGENCIES = ("สถาบันวิจัยระบบสาธารณสุข", "สถาบันวัคซีนแห่งชาติ")
STAGE_LABELS = {"draft": "ร่าง พ.ร.บ.", "act": "พ.ร.บ."}


class ShelfError(ValueError):
    pass


@dataclass(frozen=True)
class Volume:
    key: str
    label: str
    fiscal_year: int
    stage: str
    volume_no: str
    path: Path
    sha256: str
    url: str
    page_url: str
    retrieved_at: str
    book_id: str = ""
    book_title: str = ""

    @property
    def stage_label(self) -> str:
        return STAGE_LABELS.get(self.stage, self.stage or "เอกสาร")

    @property
    def title(self) -> str:
        return f"{self.stage_label} {self.fiscal_year} · {self.label}"


def shelf_dir() -> Path:
    return Path(os.environ.get(SHELF_ENV) or (config.DATA_DIR / "pdf_shelf")).resolve()


def shelf_label() -> str:
    """ชื่อชั้นเล่มสำหรับแสดงบนหน้าเว็บ — ไม่แสดงเส้นทางในเครื่อง (นโยบายความเป็นส่วนตัว)"""
    if os.environ.get(SHELF_ENV):
        return f"โฟลเดอร์ตามตัวแปร {SHELF_ENV}"
    return "โฟลเดอร์ข้อมูลของระบบ › pdf_shelf"


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _topic_id(url: str) -> str:
    m = re.search(r"[?&]id=(\d+)", url or "")
    return m.group(1) if m else ""


def _book_match(page_url: str, fy: int) -> tuple[str, str]:
    """เล่มในคลังเล่ม (#24) ที่ตรงกับหน้าเว็บของเล่มนี้ — ไม่พบ = ("", "")"""
    tid = _topic_id(page_url)
    if not tid:
        return "", ""
    try:
        from . import books
        b = books.catalog().get(f"bb-{fy}-{tid}")
    except (OSError, ValueError, KeyError):
        return "", ""
    return (b.id, b.title) if b else ("", "")


def volumes() -> list[Volume]:
    """เล่มบนชั้นที่ใช้ได้ (มีไฟล์ + มีในทะเบียนดาวน์โหลด) เรียงปีใหม่ก่อน"""
    d = shelf_dir()
    man, reg = _read_json(d / "manifest.json"), _read_json(d / "register.json")
    out = []
    for v in man.get("volumes", []):
        key = str(v.get("key", ""))
        r = (reg.get("volumes") or {}).get(key)
        p = d / "volumes" / f"{key}.pdf"
        if not key or not r or not p.exists() or holdout.holdout_reason(p):
            continue
        fy = int(v.get("fiscal_year") or 0)
        m = re.search(r"V(\d+)_", key) or re.search(r"เล่มที่\s*(\d+)", clean(v.get("label", "")))
        bid, btitle = _book_match(v.get("page", ""), fy)
        out.append(Volume(key, clean(v.get("label", "")) or key, fy, str(v.get("stage", "")),
                          m.group(1) if m else "", p, r.get("sha256", ""), v.get("url", ""),
                          v.get("page", ""), r.get("retrieved_at", ""), bid, btitle))
    out.sort(key=lambda x: (-x.fiscal_year, x.volume_no.zfill(4), x.stage != "draft"))
    return out


def get(key: str) -> Volume | None:
    return next((v for v in volumes() if v.key == key), None)


_verified: dict = {}


def verify(v: Volume) -> None:
    """SHA-256 ของไฟล์ต้องตรงกับทะเบียนดาวน์โหลด"""
    st = v.path.stat()
    k = (str(v.path), st.st_mtime_ns, st.st_size)
    if _verified.get(k) != v.sha256:
        got = sha256_file(v.path)
        if not v.sha256 or got != v.sha256:
            raise ShelfError(f"ไฟล์ {v.key} ไม่ตรงกับที่บันทึกตอนดาวน์โหลด (SHA-256 ต่างกัน) — ระบบไม่ใช้")
        _verified[k] = got


def is_protected(name: str) -> bool:
    s, k = squash(name), skeleton(name)
    return any(squash(p) in s or skeleton(p) in k for p in PROTECTED_AGENCIES)


_front_cache: dict = {}
_scope_cache: dict = {}
_warm_lock = threading.Lock()


def _front_file(v: Volume) -> Path:
    from ..pdfbook import PDFBOOK_VERSION
    return shelf_dir() / ".cache" / f"front_{v.sha256[:24]}_{PDFBOOK_VERSION}.json"


def front(v: Volume) -> list[str]:
    """ข้อความหน้าต้นเล่ม (สารบัญ) ของเล่มบนชั้น — อ่านครั้งเดียวต่อไฟล์ (ราว 10 วินาทีต่อเล่ม) แล้วจำไว้
    ในหน่วยความจำ + ไฟล์ ``.cache`` บนชั้นเล่ม · กุญแจ = SHA-256 ของไฟล์ + รุ่นตัวสกัด ⇒ ไฟล์เปลี่ยน/รุ่นเปลี่ยน
    = อ่านใหม่ · ผลเหมือนอ่านสดทุกอักษร"""
    verify(v)
    hit = _front_cache.get(v.sha256)
    if hit is not None:
        return hit
    f = _front_file(v)
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("sha256") == v.sha256:
            _front_cache[v.sha256] = d["front"]
            return d["front"]
    except (OSError, ValueError, KeyError):
        pass
    n = reader.page_count(v.path)
    out = scope_mod.front_lines(v.path, list(range(1, min(scope_mod.FRONT_PAGES, n) + 1)))
    _front_cache[v.sha256] = out
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"sha256": v.sha256, "front": out}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass                      # ชั้นเล่มอ่านอย่างเดียว — จำในหน่วยความจำอย่างเดียว
    return out


def prewarm(keys) -> None:
    """เตรียมสารบัญของเล่มที่ระบุไว้ล่วงหน้า (เรียกในเธรดพื้นหลังได้) — เล่มที่ใช้ไม่ได้ข้ามเงียบ"""
    with _warm_lock:
        for k in dict.fromkeys(keys):
            v = get(k)
            if v is None:
                continue
            try:
                front(v)
            except (ShelfError, OSError, ValueError, reader.ReaderUnavailable):
                continue


_agencies_cache: dict = {}
#: บรรทัดสารบัญที่ไม่ใช่หน่วยรับงบ (ภาพรวมกระทรวง/ตารางสรุป)
_NOT_AGENCY = ("กระทรวง", "เปรียบเทียบ", "สรุป", "รวม", "สารบัญ", "หมายเหตุ",
               # บรรทัดต่อของชื่อยาวที่ห่อบรรทัด — เลือกแล้วหาหน้าไม่ได้ จึงไม่แสดง
               "และ", "อันเนื่อง", "ที่", "ของ", "ภายใต้")


def _agency_names(front_lines: list[str]) -> list[str]:
    seen, out = set(), []
    for name, _s, _e, _p in scope_mod.toc_entries(front_lines):
        nm = clean(name).strip(" .…")
        k = squash(nm)
        if (len(k) < 6 or k in seen or nm.startswith("*") or is_protected(nm)
                or not re.search(r"[ก-๙]", nm)
                or any(skeleton(nm).startswith(skeleton(x)) for x in _NOT_AGENCY)):
            continue
        seen.add(k)
        out.append(nm)
    return out


def agencies(v: Volume) -> list[str]:
    """รายชื่อหน่วยงานจากสารบัญต้นเล่ม (อ่านเฉพาะหน้าต้นเล่ม) — ไม่รวมหน่วยที่กันไว้และหน่วยในชุดประเมินที่ยังไม่ปลดล็อก"""
    if v.sha256 not in _agencies_cache:
        _agencies_cache[v.sha256] = _agency_names(front(v))
    return [x for x in _agencies_cache[v.sha256] if not eval_guard.is_blocked(x)]


# ── PDF ที่ผู้ใช้อัปโหลดเอง (ไม่อยู่บนชั้นเล่ม) — อ่านสารบัญแบบเดียวกับชั้นเล่ม ไม่อ่านหน้าของหน่วยงานอื่น ──────────
def front_of_file(path, sha256: str) -> list[str]:
    """ข้อความหน้าต้นเล่มของไฟล์ที่อัปโหลด — จำไว้ด้วย SHA-256 (ในหน่วยความจำ)"""
    from ..pdfbook import PDFBOOK_VERSION
    k = ("upload", sha256, PDFBOOK_VERSION)
    if k not in _front_cache:
        n = reader.page_count(path)
        _front_cache[k] = scope_mod.front_lines(path, list(range(1, min(scope_mod.FRONT_PAGES, n) + 1)))
    return _front_cache[k]


def agencies_of_file(path, sha256: str) -> list[str]:
    try:
        names = _agency_names(front_of_file(path, sha256))
    except (OSError, ValueError, reader.ReaderUnavailable):
        return []
    return [x for x in names if not eval_guard.is_blocked(x)]


def toc_scope_of_file(path, sha256: str, agency: str):
    """(Scope, หน้าที่อ่านเนื้อหาจริง) ของหน่วยงานในไฟล์ที่อัปโหลด — ช่วงหน้าจากสารบัญ"""
    try:
        return scope_mod.find_by_toc(path, agency, front=front_of_file(path, sha256))
    except scope_mod.ScopeError as e:
        raise ShelfError(str(e))


def suggest_b(a: Volume, shelf: list[Volume] | None = None) -> list[tuple[Volume, str]]:
    """เล่ม B ที่ควรเทียบกับเล่ม A — เล่มเดียวกันอีกขั้นของปีเดียวกันก่อน แล้วจึงเล่มเดียวกันของปีก่อน/ปีถัดไป"""
    shelf = shelf if shelf is not None else volumes()
    same = [(v, "ปีเดียวกัน · ร่าง พ.ร.บ. ↔ พ.ร.บ.") for v in shelf
            if v.key != a.key and v.fiscal_year == a.fiscal_year and v.volume_no == a.volume_no
            and v.stage != a.stage]
    cross = [(v, "ข้ามปี · พ.ร.บ. ปีก่อน ↔ ปีนี้") for v in shelf
             if v.key != a.key and abs(v.fiscal_year - a.fiscal_year) == 1 and v.volume_no == a.volume_no]
    cross.sort(key=lambda t: (t[0].stage != "act", -t[0].fiscal_year))
    return same + cross


def toc_scope(v: Volume, agency: str):
    """(Scope, หน้าที่อ่านเนื้อหาจริง) ของหน่วยงานในเล่ม"""
    k = (v.sha256, agency)
    if k in _scope_cache:
        return _scope_cache[k]
    try:
        out = scope_mod.find_by_toc(v.path, agency, front=front(v))
    except scope_mod.ScopeError as e:
        raise ShelfError(f"{v.title}: {e}")
    _scope_cache[k] = out
    return out


#: กันสร้างรอบซ้ำ (รอบ 2 U2 28 ต.ค.: รอบเดียวกันถูกสร้างสองครั้งห่าง 1 วินาที ความเห็นแยกสองรอบ) — คำขอเดียวกันที่มา
#: ระหว่างกำลังสร้าง หรือภายใน ``START_DEDUPE_S`` วินาทีหลังสร้างเสร็จ ได้รอบเดิม · เฉพาะในโปรเซสนี้ (เซิร์ฟเวอร์ worker เดียว) ·
#: รอบเดิมถูกลบ/ถูกแทนแล้ว = สร้างใหม่ · ล้มกลางทาง = ไม่จำ คำขอถัดไปสร้างใหม่
START_DEDUPE_S = float(os.environ.get("REDBOOK_START_DEDUPE_S", "15"))
_once_lock = threading.Lock()
_once_slots: dict = {}            # key → [Lock, (ผล, เวลาเสร็จ) | None]


def _run_alive(rid: str) -> bool:
    from ..storage import pdfpair_repo
    st = pdfpair_repo.run_state(rid)
    return st is not None and not st["superseded_by"]


def _once(key, make, rid_of):
    now = time.monotonic()
    with _once_lock:
        for k in [k for k, (lk, last) in _once_slots.items()
                  if last and now - last[1] > START_DEDUPE_S and not lk.locked()]:
            del _once_slots[k]
        slot = _once_slots.setdefault(key, [threading.Lock(), None])
    with slot[0]:
        last = slot[1]
        if last and time.monotonic() - last[1] <= START_DEDUPE_S and _run_alive(rid_of(last[0])):
            return last[0]
        slot[1] = None
        out = make()
        slot[1] = (out, time.monotonic())
        return out


def _admit(agency: str, where: str) -> None:
    """ด่านหน่วยงาน (กันไว้ · ชุดประเมิน) — เรียกก่อน :func:`_once` เสมอ เพื่อไม่ให้รอบที่จำไว้ข้ามด่านที่เพิ่งล็อก"""
    agency = clean(agency)
    if not agency:
        raise ShelfError("กรุณาเลือกหน่วยงาน")
    if is_protected(agency):
        raise ShelfError("หน่วยงานนี้กันไว้ ไม่ใช้ในงานเทียบเล่ม")
    try:
        eval_guard.check(agency, where)
    except eval_guard.EvalAgencyBlocked as e:
        raise ShelfError(str(e))


def start(a_key: str, b_key: str, agency: str, expect_sha: dict | None = None) -> tuple[str, str]:
    """:func:`_start` ที่กันกดซ้ำ — คู่เล่ม + หน่วยงาน + SHA ที่คาดเดิม → ``(project_id, run_id)`` เดิม"""
    _admit(agency, "pdfshelf.start")            # ด่านทุกครั้ง — ก่อนคืนรอบเดิมจากความจำด้วย
    key = ("shelf", a_key, b_key, clean(agency), tuple(sorted((expect_sha or {}).items())))
    return _once(key, lambda: _start(a_key, b_key, agency, expect_sha), lambda r: r[1])


def _start(a_key: str, b_key: str, agency: str, expect_sha: dict | None = None) -> tuple[str, str]:
    """สร้างงานตรวจ + แนบเล่มทั้งสองจากชั้น + เทียบเฉพาะหน้าของหน่วยงาน → (project_id, run_id)

    สำเนาที่แนบต้องมี SHA-256 ตรงทะเบียนดาวน์โหลด (และตรง ``expect_sha`` ``{"A": …, "B": …}`` ถ้าระบุ —
    เช่น ไฟล์ที่ผู้ตรวจวงไว้ในรอบทดลอง) **ก่อน** สร้างงานตรวจ — ไฟล์เปลี่ยนระหว่างทาง = ไม่สร้างอะไรเลย"""
    from ..storage import files as filestore, repository as repo, source_pdfs
    from . import pdfpair
    agency = clean(agency)
    if not agency:
        raise ShelfError("กรุณาเลือกหน่วยงาน")
    if is_protected(agency):
        raise ShelfError("หน่วยงานนี้กันไว้ ไม่ใช้ในงานเทียบเล่ม")
    try:                                  # ก่อนอ่านหน้าใด ๆ ของหน่วยงาน (#44 G4)
        eval_guard.check(agency, "pdfshelf.start")
    except eval_guard.EvalAgencyBlocked as e:
        raise ShelfError(str(e))
    a, b = get(a_key), get(b_key)
    if a is None or b is None:
        raise ShelfError("กรุณาเลือกเล่ม A และเล่ม B จากชั้นเล่ม")
    if a.key == b.key:
        raise ShelfError("เล่ม A และเล่ม B ต้องเป็นคนละเล่ม")
    (sa, read_a), (sb, read_b) = toc_scope(a, agency), toc_scope(b, agency)
    stored = {}
    for side, v in (("A", a), ("B", b)):
        verify(v)                 # สารบัญอาจมาจากแคช — ตรวจไฟล์จริงกับทะเบียนอีกครั้งก่อนคัดลอก
        with open(v.path, "rb") as fh:
            st = filestore.save_stream(fh, v.path.name)
        want = (expect_sha or {}).get(side) or v.sha256
        if st.sha256 != v.sha256 or st.sha256 != want:
            for x in [*stored.values(), st]:
                filestore.delete_stored(x.stored_name)
            raise ShelfError(f"ไฟล์ {v.key} เปลี่ยนระหว่างคัดลอก หรือไม่ใช่ไฟล์เดียวกับที่ใช้ตรวจ (SHA-256 ต่างกัน) — "
                             "ไม่เริ่มรอบเทียบ")
        stored[side] = st
    cross = a.fiscal_year != b.fiscal_year
    name = f"{agency} · {a.stage_label} {a.fiscal_year} ↔ {b.stage_label} {b.fiscal_year}"
    pid = repo.create_project(name[:200], "year_to_year" if cross else "before_after_reduction",
                              f"จากชั้นเล่มในเครื่อง: {a.key} ↔ {b.key}")
    for side, v in (("A", a), ("B", b)):
        source_pdfs.link(pid, side, stored[side], origin=source_pdfs.ORIGIN_OFFICIAL,
                         source_url=v.url, retrieved_at=v.retrieved_at)
    rid = pdfpair.run(pid, agency=agency, a_first=str(sa.first), a_last=str(sa.last),
                      b_first=str(sb.first), b_last=str(sb.last), range_method=scope_mod.METHOD_TOC,
                      pages_read={"A": sorted(set(read_a)), "B": sorted(set(read_b))},
                      shelf={"A": a.key, "B": b.key}, stages={"A": a.stage, "B": b.stage})
    return pid, rid


def start_uploaded(project_id: str, agency: str) -> str:
    """:func:`_start_uploaded` ที่กันกดซ้ำ — ไฟล์สองฉบับ (SHA-256) + หน่วยงานเดิม → ``run_id`` เดิม ·
    อัปโหลดไฟล์ใหม่แทน = SHA เปลี่ยน = รอบใหม่"""
    from ..storage import source_pdfs
    _admit(agency, "pdfshelf.start_uploaded")
    sides = source_pdfs.for_project(project_id)
    key = ("upload", project_id, clean(agency), *(sides.get(s, {}).get("sha256", "") for s in ("A", "B")))
    return _once(key, lambda: _start_uploaded(project_id, agency), lambda r: r)


def _start_uploaded(project_id: str, agency: str) -> str:
    """เทียบ PDF ที่ผู้ใช้อัปโหลดเองทั้งสองฉบับของงานตรวจ — ช่วงหน้าจากสารบัญแบบเดียวกับชั้นเล่ม (อ่านเฉพาะสารบัญ +
    หน้าของหน่วยงานที่เลือก) · หน่วยที่กันไว้/หน่วยในชุดประเมินที่ยังไม่ปลดล็อก = ปฏิเสธก่อนอ่านหน้าใด ๆ → run_id"""
    from . import pdfpair
    agency = clean(agency)
    if not agency:
        raise ShelfError("กรุณาเลือกหน่วยงาน")
    if is_protected(agency):
        raise ShelfError("หน่วยงานนี้กันไว้ ไม่ใช้ในงานเทียบเล่ม")
    try:
        eval_guard.check(agency, "pdfshelf.start_uploaded")
    except eval_guard.EvalAgencyBlocked as e:
        raise ShelfError(str(e))
    scopes = {}
    for side in ("A", "B"):
        path, row = pdfpair._side_file(project_id, side)
        scopes[side] = toc_scope_of_file(path, row["sha256"], agency)
    (sa, read_a), (sb, read_b) = scopes["A"], scopes["B"]
    return pdfpair.run(project_id, agency=agency, a_first=str(sa.first), a_last=str(sa.last),
                       b_first=str(sb.first), b_last=str(sb.last), range_method=scope_mod.METHOD_TOC,
                       pages_read={"A": sorted(set(read_a)), "B": sorted(set(read_b))})


__all__ = ["start_uploaded", "ShelfError", "Volume", "PROTECTED_AGENCIES", "shelf_dir", "volumes", "get", "verify", "front", "prewarm",
           "agencies", "suggest_b", "toc_scope", "start", "is_protected", "front_of_file", "agencies_of_file",
           "toc_scope_of_file"]
