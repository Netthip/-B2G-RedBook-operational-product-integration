# -*- coding: utf-8 -*-
"""ส่งออกรายการที่ผู้ตรวจยืนยัน — `.csv` + `.xlsx` พร้อมชีตสรุป

🔴 **คำสั่งกิ๊ฟ (7 ก.ย. 2569 · ข้อ E)**

* ส่งออกเฉพาะ **สถานะล่าสุด** ที่เป็น ``CONFIRMED`` / ``CONFIRMED_WITH_EDIT``
  เคย confirmed แต่ล่าสุด dismissed ⇒ **ไม่ออก** (ใช้ latest decision ต่อ finding)
* freeze snapshot: export ID · เวลา · run ID · รุ่นเครื่องยนต์ · decision cutoff
  (seq สูงสุด ณ ขณะสร้าง) · จำนวนรายการ
* CSV = UTF-8 BOM + กันสูตร · **XLSX ก็ต้องกันสูตรด้วย** ไม่ใช่เฉพาะ CSV
  ``=`` ``+`` ``-`` ``@`` จากข้อความผู้ใช้ต้องไม่ถูก Excel ตีความเป็นสูตร
* แยกบาทกับล้านบาท · ห้ามรวมเงินนอกงบประมาณกับงบประมาณรายจ่าย —
  ยอดรวมทุกตัว **จัดกลุ่มตาม (หมวดงบ, หน่วย)** เสมอ ไม่มีการรวมข้ามกลุ่ม
* ข้อความบังคับ: “การส่งออกนี้ยังไม่ได้แก้ไขข้อมูลใน e-Budgeting”
* ห้ามใช้คำว่า “แก้ไขแล้ว” หรือ “นำเข้า e-Budgeting แล้ว”

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .. import privacy
from ..export import csv_safe
from . import amounts, categories, decisions
from .t1b import T1BRunView

EXPORT_SERVICE_VERSION = "t1b-export-0.1.0"

EXPORT_TITLE = "รายการที่ผู้ตรวจยืนยันสำหรับนำไปตรวจและแก้ไขใน e-Budgeting"
EXPORT_DISCLAIMER = "การส่งออกนี้ยังไม่ได้แก้ไขข้อมูลใน e-Budgeting"
#: ค่าเริ่มต้นของสถานะการนำไปแก้ — ผู้ปฏิบัติงานเป็นผู้ปรับเองนอกระบบ
EBUDGET_STATUS_DEFAULT = "ยังไม่ได้ดำเนินการ"

#: คำต้องห้ามในไฟล์ส่งออก — มีเทสต์กัน
FORBIDDEN_PHRASES = ("แก้ไขแล้ว", "นำเข้า e-Budgeting แล้ว")

#: (key, หัวคอลัมน์) — ลำดับนี้คือลำดับในไฟล์
COLUMNS = (
    ("finding_id", "finding_id"),
    ("subject_category", "หมวดจุดตรวจสอบ"),
    ("category_confidence", "ระดับความมั่นใจ"),
    ("category_evidence", "หลักฐานที่ใช้จัดหมวด"),
    ("finding_type", "ชนิดข้อสังเกต"),
    ("agency", "หน่วยงาน"),
    ("fiscal_year", "ปีงบประมาณ"),
    ("parent_plan", "แผนงาน"),
    ("section_title", "โครงการ/หัวเรื่องชีต"),
    ("row_label", "รายการ"),
    ("budget_category", "หมวดงบรายจ่าย"),
    ("declared_unit", "หน่วย"),
    ("baseline_location", "ตำแหน่ง ฉบับตั้งต้น"),
    ("current_location", "ตำแหน่ง ฉบับปัจจุบัน"),
    ("engine_baseline_value", "ค่าฉบับตั้งต้น (engine)"),
    ("engine_current_value", "ค่าฉบับปัจจุบัน (engine)"),
    ("engine_difference", "ผลต่าง (engine)"),
    ("confirmed_value", "ค่าที่ผู้ตรวจยืนยัน/แก้ไข"),
    ("edit_reason", "เหตุผลที่แก้ไข"),
    ("decision_status", "สถานะคำตัดสิน"),
    ("decision_note", "หมายเหตุผู้ตรวจ"),
    ("decided_at", "ตัดสินเมื่อ"),
    ("needs_human_rebind", "ต้องผูกกลับด้วยมนุษย์หรือไม่"),
    ("ebudget_status", "สถานะการนำไปแก้ e-Budgeting"),
    ("run_id", "run_id"),
    ("decision_seq", "decision_seq"),
    ("audit_seq", "audit_seq"),
    ("engine_versions", "รุ่นเครื่องยนต์"),
    ("file_a_sha256", "แฮชไฟล์ A"),
    ("file_b_sha256", "แฮชไฟล์ B"),
)


def _dec(text) -> Decimal | None:
    try:
        return Decimal(str(text).replace(",", "").strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None


def _loc(loc) -> str:
    if loc is None:
        return ""
    return f"{loc.sheet}!{loc.cell}" if loc.cell else f"{loc.sheet} แถว {loc.row}"


@dataclass(frozen=True)
class ExportBundle:
    snapshot: dict
    rows: tuple[dict, ...]
    summary: dict
    excluded: dict

    @property
    def count(self) -> int:
        return len(self.rows)


def build(view: T1BRunView, *, agency: str = "", db_path=None) -> ExportBundle:
    """ประกอบชุดส่งออกจาก **คำตัดสินล่าสุดต่อ finding** เท่านั้น — ไม่เขียนไฟล์"""
    from ..storage import t1b_decisions as repo

    latest = repo.latest_by_finding(view.summary.run_id, db_path=db_path)
    all_decisions = repo.list_for_run(view.summary.run_id, db_path=db_path)
    cutoff = max((d.seq for d in all_decisions), default=0)
    s = view.summary
    versions = (f"key={s.key_version}; matching={s.matching_version}; "
                f"compare={s.compare_version}; service={s.service_version}; "
                f"decisions={decisions.DECISION_SERVICE_VERSION}; "
                f"export={EXPORT_SERVICE_VERSION}")

    rows: list[dict] = []
    by_cat: dict[str, int] = {c: 0 for c in categories.CATEGORY_ORDER}
    by_status: dict[str, int] = {decisions.CONFIRMED: 0,
                                 decisions.CONFIRMED_WITH_EDIT: 0}
    # ยอดเพิ่ม/ลด/สุทธิ **แยกตาม (หมวดงบ, หน่วย)** — ไม่มีการรวมข้ามกลุ่ม
    money: dict[tuple[str, str], dict] = {}
    unparsed = 0
    not_rebindable = 0
    other_exported = other_not_exported = 0
    excluded_status: dict[str, int] = {}

    for f in view.findings:
        d = latest.get(f.finding_id)
        subject = categories.classify_subject(f)
        if d is None or d.status_to not in decisions.EXPORTABLE:
            key = d.status_to if d else decisions.PENDING
            excluded_status[key] = excluded_status.get(key, 0) + 1
            if subject.category == categories.CAT_OTHER:
                other_not_exported += 1
            continue

        if subject.category == categories.CAT_OTHER:
            other_exported += 1
        by_cat[subject.category] += 1
        by_status[d.status_to] += 1
        not_rebindable += int(d.not_rebindable)

        if d.status_to == decisions.CONFIRMED_WITH_EDIT:
            confirmed_value = d.corrected_value
            edit_reason = d.note
        else:
            confirmed_value = d.engine_current_value
            edit_reason = ""

        # เงิน — เฉพาะชนิด AMOUNT_* และค่าที่แปลงเป็นตัวเลขได้เท่านั้น
        if f.finding_type.startswith("AMOUNT_"):
            base = _dec(d.engine_baseline_value)
            cur = _dec(confirmed_value)
            gkey = (f.budget_category or "(ไม่ระบุหมวด)",
                    f.declared_unit or "(ไม่ระบุหน่วย)")
            g = money.setdefault(gkey, {"increase": Decimal(0), "decrease": Decimal(0),
                                        "net": Decimal(0), "rows": 0, "unparsed": 0})
            if base is None or cur is None:
                g["unparsed"] += 1
                unparsed += 1
            else:
                diff = cur - base
                g["rows"] += 1
                g["net"] += diff
                if diff > 0:
                    g["increase"] += diff
                elif diff < 0:
                    g["decrease"] += -diff

        rows.append({
            "finding_id": f.finding_id,
            "subject_category": f"{subject.category} — {subject.label}",
            "category_confidence": f"{subject.confidence} — {subject.confidence_label}",
            "category_evidence": " | ".join(subject.evidence),
            "finding_type": f"{f.finding_type} — {f.type_label}",
            "agency": agency,
            "fiscal_year": "" if f.fiscal_year is None else str(f.fiscal_year),
            "parent_plan": f.parent_plan,
            "section_title": f.section_title,
            "row_label": f.row_label,
            "budget_category": f.budget_category or "",
            "declared_unit": f.declared_unit,
            "baseline_location": _loc(f.baseline),
            "current_location": _loc(f.current),
            # มาตรฐานหน่วย/ทศนิยมเดียวกับทุกหน้า (#24) — ค่าที่ตรึงในคำตัดสินไม่ถูกแก้ แค่เขียนออกตามมาตรฐาน
            "engine_baseline_value": amounts.format_number(d.engine_baseline_value, f.declared_unit),
            "engine_current_value": amounts.format_number(d.engine_current_value, f.declared_unit),
            "engine_difference": amounts.format_number(d.engine_difference, f.declared_unit),
            # ค่าที่ผู้ตรวจพิมพ์แก้เอง = เขียนตามที่พิมพ์ (ห้ามจัดรูปแบบแทนผู้ใช้)
            "confirmed_value": (confirmed_value if d.status_to == decisions.CONFIRMED_WITH_EDIT
                                else amounts.format_number(confirmed_value, f.declared_unit)),
            "edit_reason": edit_reason,
            "decision_status": f"{d.status_to} — {d.status_label}",
            "decision_note": d.note,
            "decided_at": d.decided_at,
            "needs_human_rebind": "ใช่" if d.not_rebindable else "ไม่",
            "ebudget_status": EBUDGET_STATUS_DEFAULT,
            "run_id": d.run_id,
            "decision_seq": str(d.seq),
            "audit_seq": str(d.audit_seq or ""),
            "engine_versions": versions,
            "file_a_sha256": getattr(d, "file_a_sha256", "") or "",
            "file_b_sha256": getattr(d, "file_b_sha256", "") or "",
        })

    snapshot = {
        "export_id": f"exp_{uuid.uuid4().hex[:12]}",
        "exported_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "run_id": s.run_id,
        "engine_versions": versions,
        "privacy_version": privacy.PRIVACY_VERSION,
        "decision_cutoff_seq": cutoff,
        "row_count": len(rows),
        "title": EXPORT_TITLE,
        "disclaimer": EXPORT_DISCLAIMER,
    }
    summary = {
        "by_category": by_cat,
        "by_status": by_status,
        "money_by_group": {f"{k[0]} | {k[1]}": {kk: (str(vv) if isinstance(vv, Decimal) else vv)
                                               for kk, vv in v.items()}
                           for k, v in money.items()},
        "unparsed_amounts": unparsed,
        "not_rebindable": not_rebindable,
        "other_exported": other_exported,
        "other_not_exported": other_not_exported,
    }
    return ExportBundle(snapshot=snapshot, rows=tuple(rows), summary=summary,
                        excluded={"by_status": excluded_status})


# ══════════════════════════════════════════════════════════════════════════════
#  เขียนไฟล์
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExportFiles:
    export_id: str
    csv_path: Path
    xlsx_path: Path
    csv_report: object
    xlsx_neutralized: int


def _header_rows(snapshot: dict) -> list[list[str]]:
    return [
        [EXPORT_TITLE],
        [EXPORT_DISCLAIMER],
        [f"export_id={snapshot['export_id']}", f"exported_at={snapshot['exported_at']}",
         f"run_id={snapshot['run_id']}", f"decision_cutoff_seq={snapshot['decision_cutoff_seq']}",
         f"rows={snapshot['row_count']}"],
        [snapshot["engine_versions"], f"privacy={snapshot['privacy_version']}"],
        [],
    ]


def write(bundle: ExportBundle, out_dir) -> ExportFiles:
    """เขียน ``.csv`` และ ``.xlsx`` ลง ``out_dir`` — ทั้งสองไฟล์ผ่านการกันสูตร"""
    import openpyxl
    from openpyxl.styles import Font

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    eid = bundle.snapshot["export_id"]
    header = [h for _, h in COLUMNS]
    body = [[r[k] for k, _ in COLUMNS] for r in bundle.rows]

    # ── CSV ──────────────────────────────────────────────────────────────────
    csv_path = out / f"{eid}_confirmed_for_ebudgeting.csv"
    csv_rows = _header_rows(bundle.snapshot) + [header] + body
    csv_report = csv_safe.write_csv(csv_path, None, csv_rows)

    # ── XLSX — กันสูตรทุกเซลล์ข้อความ · ตัวเขียนจริงอยู่นอก redbook/ (exporters/) ─
    neutralized = 0

    def cell(value, bold=False):
        nonlocal neutralized
        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            return ("n", float(value) if isinstance(value, Decimal) else value, bold)
        text, was_neutral, _, _ = csv_safe.neutralize(value)
        neutralized += int(was_neutral)
        return ("s", text, bold)

    main_rows = []
    for i, line in enumerate(_header_rows(bundle.snapshot)):
        main_rows.append([cell(v, bold=(i == 0)) for v in line])
    main_rows.append([cell(h, bold=True) for h in header])
    main_rows += [[cell(v) for v in row] for row in body]

    sm = [[cell(EXPORT_TITLE, True)], [cell(EXPORT_DISCLAIMER)], [],
          [cell("จำนวนรายการตามหมวดจุดตรวจสอบ", True)]]
    sm += [[cell(f"{k} — {categories.CATEGORY_LABELS.get(k, k)}"), cell(n)]
           for k, n in bundle.summary["by_category"].items()]
    sm += [[], [cell("จำนวนตามสถานะคำตัดสิน (เฉพาะที่ส่งออก)", True)]]
    sm += [[cell(f"{k} — {decisions.STATUS_LABELS.get(k, k)}"), cell(n)]
           for k, n in bundle.summary["by_status"].items()]
    sm += [[], [cell("ยอดเงิน แยกตาม (หมวดงบรายจ่าย | หน่วย) — ไม่รวมข้ามกลุ่ม", True)],
           [cell(h, True) for h in ("กลุ่ม", "รายการ", "ยอดเพิ่ม", "ยอดลด", "ยอดสุทธิ", "แปลงตัวเลขไม่ได้")]]
    for g, v in bundle.summary["money_by_group"].items():
        sm.append([cell(g), cell(v["rows"]), cell(Decimal(v["increase"])),
                   cell(Decimal(v["decrease"])), cell(Decimal(v["net"])), cell(v["unparsed"])])
    if not bundle.summary["money_by_group"]:
        sm.append([cell("(ไม่มีรายการชนิดยอดเงินที่ส่งออก)")])
    sm += [[],
           [cell("รายการที่ต้องผูกกลับด้วยมนุษย์ (not_rebindable)"), cell(bundle.summary["not_rebindable"])],
           [cell("OTHER_OR_UNCLASSIFIED ที่ส่งออก (สถานะยืนยัน)"), cell(bundle.summary["other_exported"])],
           [cell("OTHER_OR_UNCLASSIFIED ที่ไม่ได้ส่งออก"), cell(bundle.summary["other_not_exported"])],
           [cell("ยอดที่แปลงเป็นตัวเลขไม่ได้ (ไม่รวมในผลรวม)"), cell(bundle.summary["unparsed_amounts"])],
           [], [cell("ไม่ได้ส่งออก แยกตามสถานะล่าสุด", True)]]
    sm += [[cell(f"{k} — {decisions.STATUS_LABELS.get(k, k)}"), cell(n)]
           for k, n in bundle.excluded["by_status"].items()]
    sheets = [("รายการที่ยืนยัน", main_rows), ("สรุป", sm)]

    # ── ตรวจก่อนเขียน: ไม่มีเส้นทาง/ชื่อผู้ใช้ และไม่มีคำต้องห้าม ─────────
    all_text = chr(10).join(str(c[1]) for _, rows in sheets for row in rows for c in row)
    privacy.assert_shareable(all_text, where="XLSX ที่จะส่งออก")
    for phrase in FORBIDDEN_PHRASES:
        if phrase in all_text:
            raise ValueError(f"ไฟล์ส่งออกมีคำต้องห้าม: {phrase}")

    xlsx_path = out / f"{eid}_confirmed_for_ebudgeting.xlsx"
    # 🔴 ตัวเขียนอยู่นอกแพ็กเกจตรวจโดยตั้งใจ (ดู exporters/__init__.py) · import ตอนใช้
    import importlib
    importlib.import_module("exporters.xlsx_writer").write_xlsx(xlsx_path, sheets)

    (out / f"{eid}_snapshot.json").write_text(
        json.dumps({**bundle.snapshot, "summary": bundle.summary,
                    "excluded": bundle.excluded}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return ExportFiles(export_id=eid, csv_path=csv_path, xlsx_path=xlsx_path,
                       csv_report=csv_report, xlsx_neutralized=neutralized)


__all__ = [
    "EXPORT_SERVICE_VERSION", "EXPORT_TITLE", "EXPORT_DISCLAIMER",
    "EBUDGET_STATUS_DEFAULT", "FORBIDDEN_PHRASES", "COLUMNS",
    "ExportBundle", "ExportFiles", "build", "write",
]
