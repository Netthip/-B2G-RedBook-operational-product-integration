# -*- coding: utf-8 -*-
"""สร้างชุดเอกสาร Human Review จากผลการรันที่ freeze แล้ว

การใช้งาน:
    python -m reviewpack.make_review_package \
        --run LABEL=<ไฟล์ผล.json> [LABEL=<ไฟล์ผล.json> ...] \
        --scope primary|supplementary --sources <โฟลเดอร์ไฟล์ต้นทาง> \
        --outdir <โฟลเดอร์ผลลัพธ์> [--sample <HUMAN_CHECK_SAMPLE.json>]

ผลลัพธ์:
    HUMAN_CHECK_SAMPLE_<scope>.xlsx        แบบฟอร์มกรอกคำตัดสิน (เปิดด้วย Excel)
    HUMAN_CHECK_SAMPLE_<scope>.csv         สำเนาแบบข้อความ
    HUMAN_CHECK_AUDIT_TEMPLATE_<scope>.json  โครงบันทึกผลการตรวจสองรอบ
"""
import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import REVIEWPACK_VERSION

SCOPE_LABEL = {
    "primary": "PRIMARY CASE REVIEW — สวรส. และสถาบันวัคซีนแห่งชาติ",
    "supplementary": ("SUPPLEMENTARY — NOT PART OF PRIMARY TWO-AGENCY RESULT · "
                      "OPTIONAL SUPPLEMENTARY COVERAGE REVIEW — NOT REQUIRED TO "
                      "CLOSE PRIMARY TWO-AGENCY REVIEW"),
}

CATEGORY_LABEL = {
    "C1": "วงเงินลดลง", "C2": "วงเงินเพิ่มขึ้น", "C3": "วงเงินไม่เปลี่ยนแปลง",
    "C4": "รายการเพิ่ม", "C5": "รายการหาย",
    "C6": "โครงสร้างเปลี่ยน (รอการยืนยัน)", "C7": "ยังตีความไม่ได้",
    "SC1": "ความหมายของฟิลด์ไม่ตรงกัน (schema conflict)",
}

COLUMNS = [
    ("sample_id", "รหัสตัวอย่าง", 14),
    ("experiment", "การทดลอง", 26),
    ("dataset_class", "ชั้นข้อมูล", 12),
    ("agency_code", "รหัสหน่วยงาน", 12),
    ("document_a", "เอกสารฝั่ง A", 24),
    ("document_b", "เอกสารฝั่ง B", 24),
    ("finding_category", "หมวดผลตรวจ", 16),
    ("finding_category_label", "ความหมายหมวด", 26),
    ("rule_id", "รหัสกฎ", 12),
    ("matching_method", "วิธีจับคู่", 14),
    ("matching_step", "ขั้น pipeline", 12),
    ("item_label", "ชื่อรายการ", 34),
    ("hierarchy_path", "สายลำดับชั้น", 46),
    ("raw_value_a", "ค่าดิบฝั่ง A", 16),
    ("raw_value_b", "ค่าดิบฝั่ง B", 16),
    ("normalized_value_a", "ค่าที่ระบบใช้ฝั่ง A", 18),
    ("normalized_value_b", "ค่าที่ระบบใช้ฝั่ง B", 18),
    ("difference", "ผลต่าง", 14),
    ("source_location_a", "ตำแหน่งหลักฐาน A", 20),
    ("source_location_b", "ตำแหน่งหลักฐาน B", 20),
    ("system_decision", "คำตัดสินของระบบ", 18),
    ("evidence_opened_a", "เปิดหลักฐาน A แล้ว", 15),
    ("evidence_opened_b", "เปิดหลักฐาน B แล้ว", 15),
    ("reviewer_verdict", "คำตอบผู้วิจัย", 18),
    ("reviewer_confidence", "ความมั่นใจผู้วิจัย", 16),
    ("reviewer_reason", "เหตุผล", 40),
    ("reviewed_at", "วันเวลาที่ตรวจ", 20),
]

VERDICT_CHOICES = ["ยืนยัน", "ไม่ยืนยัน", "ไม่แน่ใจ"]
CONFIDENCE_CHOICES = ["สูง", "ปานกลาง", "ต่ำ"]
EVIDENCE_OPENED_CHOICES = ["เปิดแล้ว", "ยังไม่ได้เปิด"]

# คอลัมน์ที่ผู้วิจัยกรอก (ต้องว่างตอนสร้างไฟล์ — ห้ามมีคำตอบล่วงหน้า)
REVIEWER_FIELDS = ("evidence_opened_a", "evidence_opened_b", "reviewer_verdict",
                   "reviewer_confidence", "reviewer_reason", "reviewed_at")


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for b in iter(lambda: fp.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class _CellReader:
    """อ่านค่าดิบจากไฟล์ต้นทางแบบอ่านอย่างเดียว (เปิดครั้งเดียวต่อไฟล์)"""

    def __init__(self, sources_dir):
        self.dir = Path(sources_dir) if sources_dir else None
        self._cache = {}

    def read(self, file_name, cell_ref):
        if not (self.dir and file_name and cell_ref):
            return None
        if file_name not in self._cache:
            matches = list(self.dir.rglob(file_name))
            if not matches:
                self._cache[file_name] = None
            else:
                fh = open(matches[0], "rb")
                wb = openpyxl.load_workbook(fh, data_only=True, read_only=False)
                self._cache[file_name] = (wb, fh)
        entry = self._cache[file_name]
        if entry is None:
            return None
        wb, _ = entry
        try:
            return wb["data"][cell_ref].value
        except Exception:
            return None

    def close(self):
        for entry in self._cache.values():
            if entry:
                wb, fh = entry
                wb.close()
                fh.close()


def _hierarchy(key):
    parts = [p for p in (key or []) if p]
    return " › ".join(str(p) for p in parts[:-1]) if len(parts) > 1 else ""


def build_rows(runs, reader, scope, sample_index=None):
    """runs: list ของ (label, run_dict) · sample_index: {(label, index)} ถ้าจำกัดเฉพาะตัวอย่าง"""
    rows = []
    n = 0
    for label, run in runs:
        files = run.get("files", {})
        name_a = files.get("a", {}).get("name", "")
        name_b = files.get("b", {}).get("name", "")
        for i, f in enumerate(run.get("findings", [])):
            if sample_index is not None and (label, i) not in sample_index:
                continue
            n += 1
            ev_a = f.get("evidence_a") or {}
            ev_b = f.get("evidence_b") or {}
            cell_a, cell_b = ev_a.get("amount_cell"), ev_b.get("amount_cell")
            key = f.get("key") or []
            cat = f.get("category", "")
            rows.append({
                "sample_id": f"{'P' if scope == 'primary' else 'S'}-{n:03d}",
                "experiment": label,
                "dataset_class": "T1 (สาธารณะ)",
                "agency_code": key[0] if key else "",
                "document_a": name_a,
                "document_b": name_b,
                "finding_category": cat,
                "finding_category_label": CATEGORY_LABEL.get(cat, f.get("category_label", "")),
                "rule_id": f"T1-{cat}" if cat else "",
                "matching_method": f.get("match_level", ""),
                "matching_step": f.get("match_step", ""),
                "item_label": key[-1] if key else "",
                "hierarchy_path": _hierarchy(key),
                "raw_value_a": reader.read(name_a, cell_a),
                "raw_value_b": reader.read(name_b, cell_b),
                "normalized_value_a": f.get("amount_a"),
                "normalized_value_b": f.get("amount_b"),
                "difference": f.get("amount_diff"),
                "source_location_a": f"{name_a}!{cell_a}" if cell_a else
                                     (ev_a.get("sheet_name") or ""),
                "source_location_b": f"{name_b}!{cell_b}" if cell_b else
                                     (ev_b.get("sheet_name") or ""),
                "system_decision": f.get("machine_status", ""),
                "evidence_opened_a": "",
                "evidence_opened_b": "",
                "reviewer_verdict": "",
                "reviewer_confidence": "",
                "reviewer_reason": "",
                "reviewed_at": "",
                # ใช้ใน audit template เท่านั้น (ไม่แสดงในแบบฟอร์ม)
                "finding_ref": f"{label}#{i}",
            })
    return rows


# 🔴 เส้นทางในหมายเหตุคิดตอนรันจากที่อยู่ของไฟล์นี้ ไม่ใช่เขียนตายตัว
# ผู้ตรวจยังเห็นเส้นทางจริงบนเครื่องตัวเองเหมือนเดิม แต่ซอร์สไม่มีชื่อผู้ใช้ติดขึ้น git
_PUBLIC_SOURCES = (Path(__file__).resolve().parents[1]
                   / ".data" / "public_sources" / "fy2569")

SOURCES_NOTE = {
    "primary": (f"ไฟล์หลักฐานทั้งสองฝั่งอยู่ที่  {_PUBLIC_SOURCES}\\ "
                "(เปิดแบบอ่านอย่างเดียว — ห้ามแก้ไขหรือบันทึกทับ)"),
    "supplementary": (f"ไฟล์หลักฐานอยู่ที่  {_PUBLIC_SOURCES}\\ "
                      "และ fy2570\\ (เฉพาะรายการ Y2_schema_conflict) "
                      "(เปิดแบบอ่านอย่างเดียว — ห้ามแก้ไขหรือบันทึกทับ)"),
}

GUIDE_STEPS = [
    "1. เปิดไฟล์หลักฐานฝั่ง A ตามคอลัมน์ \"ตำแหน่งหลักฐาน A\" "
    "(รูปแบบ ชื่อไฟล์!เซลล์ เช่น draft_ร่างพรบ_2569.xlsx!M4972 = ชีต data เซลล์ M4972)",
    "2. ตรวจว่าค่าในเซลล์ฝั่ง A ตรงกับ \"ค่าดิบฝั่ง A\" หรือไม่ "
    "แล้วเลือก \"เปิดแล้ว\" ในช่อง \"เปิดหลักฐาน A แล้ว\"",
    "3. เปิดไฟล์หลักฐานฝั่ง B ตามคอลัมน์ \"ตำแหน่งหลักฐาน B\"",
    "4. ตรวจว่าค่าในเซลล์ฝั่ง B ตรงกับ \"ค่าดิบฝั่ง B\" หรือไม่ "
    "แล้วเลือก \"เปิดแล้ว\" ในช่อง \"เปิดหลักฐาน B แล้ว\"",
    "5. ดูว่าหมวดผลตรวจ C1–C7 ที่ระบบให้ (คอลัมน์ \"หมวดผลตรวจ\" และ \"ความหมายหมวด\") "
    "สอดคล้องกับค่าที่เห็นจากหลักฐานหรือไม่",
    "6. เลือกคำตอบในช่อง \"คำตอบผู้วิจัย\": ยืนยัน / ไม่ยืนยัน / ไม่แน่ใจ "
    "(เซลล์มีรายการให้เลือก)",
    "7. เขียน \"เหตุผล\" สั้น ๆ เฉพาะรายการที่เลือก \"ไม่ยืนยัน\" หรือ \"ไม่แน่ใจ\" "
    "แล้วกรอก \"วันเวลาที่ตรวจ\" เช่น 28/08/2569 14:30",
]

GUIDE_CRITERIA = [
    "ยืนยัน = ค่าฝั่ง A และฝั่ง B ตรงกับหลักฐาน และหมวดที่ระบบให้สอดคล้องกับค่าที่เห็น",
    "ไม่ยืนยัน = ค่าไม่ตรงกับหลักฐาน หรือหมวดไม่สอดคล้องกับหลักฐาน",
    "ไม่แน่ใจ = เปิดหลักฐานแล้วยังสรุปไม่ได้ — ระบุในช่องเหตุผลว่าติดตรงไหน",
]


def _write_guide_sheet(wb, scope):
    """แผ่นแรกของไฟล์ = คำแนะนำวิธีตรวจสำหรับผู้วิจัย (ไม่ต้องอ่าน JSON หรือค้นเซลล์เอง)"""
    ws = wb.create_sheet("วิธีตรวจ", 0)
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 118

    def put(text, *, bold=False, size=11, color=None, fill=None, wrap=True):
        ws.append([text])
        c = ws.cell(row=ws.max_row, column=1)
        c.font = Font(b=bold, size=size, color=color)
        c.alignment = Alignment(wrap_text=wrap, vertical="top")
        if fill:
            c.fill = PatternFill("solid", fgColor=fill)

    if scope == "primary":
        put("วิธีตรวจ — Primary Case Review รอบที่ 1 (สวรส. และสถาบันวัคซีนแห่งชาติ · 21 รายการ ตรวจทั้งหมด)",
            bold=True, size=13)
    else:
        put("วิธีตรวจ — Supplementary Coverage Review (งานเสริม · 40 รายการ)",
            bold=True, size=13)
        put("สถานะ: OPTIONAL SUPPLEMENTARY COVERAGE REVIEW — NOT REQUIRED TO CLOSE "
            "PRIMARY TWO-AGENCY REVIEW", bold=True, color="9C2B2E", fill="FDECEA")
        put("ชุดนี้ตรวจหลัง Primary Case Review เสร็จ (หรือหลัง Phase 3) ได้ · "
            "ห้ามรวมผลกับชุด Primary และห้ามใช้อ้างความแม่นยำของประชากรทั้งกระทรวง")
    put("สิ่งที่กำลังตรวจ: ผลที่ระบบรายงานตรงกับหลักฐานในเอกสารต้นทางหรือไม่ — "
        "ไม่ใช่การตรวจว่างบประมาณถูกหรือผิด และไม่ตัดสินสาเหตุของการเปลี่ยนแปลง")
    put("")
    put("ทำทีละแถวในแผ่น \"review\" ตามลำดับจากบนลงล่าง ห้ามข้ามแถว:", bold=True)
    for s in GUIDE_STEPS:
        put(s)
    put("")
    put("เกณฑ์การเลือกคำตอบ:", bold=True)
    for s in GUIDE_CRITERIA:
        put(s)
    if scope == "supplementary":
        put("รายการหมวด SC1 (schema conflict) ไม่มีจำนวนเงินให้เทียบ — ตรวจว่านิยามฟิลด์ใน "
            "ชีต Data Dict ของไฟล์ทั้งสองฝั่งต่างกันจริงตามที่ระบบรายงาน")
    put("")
    put(SOURCES_NOTE[scope], bold=True)
    put("")
    put("ข้อกำหนดของรอบการตรวจ:", bold=True)
    put("รอบที่ 1 — ตรวจตามลำดับแถวที่ปรากฏในไฟล์นี้ · ห้ามดูคำตอบใด ๆ ล่วงหน้า · "
        "ไฟล์นี้ไม่มีและไม่แสดงผลการตรวจรอบที่ 2")
    put("รอบที่ 2 — จะได้รับไฟล์ใหม่ที่สลับลำดับรายการ หลังรอบที่ 1 เสร็จอย่างน้อย 1 วัน · "
        "ยังไม่ต้องทำอะไรในตอนนี้")


def write_xlsx(path, rows, scope, meta):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "review"

    banner = SCOPE_LABEL[scope]
    ws.append([banner])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(COLUMNS))
    c = ws.cell(row=1, column=1)
    c.font = Font(b=True, size=12, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor="B92F35" if scope == "primary" else "5B6470")
    c.alignment = Alignment(horizontal="center", vertical="center")

    ws.append([f"เวอร์ชันที่ freeze: {meta['versions']}  ·  "
               f"สร้างเมื่อ {meta['generated_at']}  ·  {REVIEWPACK_VERSION}"])
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(COLUMNS))
    ws.cell(row=2, column=1).font = Font(size=9, italic=True)

    ws.append(["คำแนะนำวิธีตรวจอยู่ที่แผ่น \"วิธีตรวจ\" (แผ่นแรกของไฟล์)"])
    ws.cell(row=3, column=1).font = Font(size=9, b=True)
    header = [th for _, th, _ in COLUMNS]
    ws.append(header)
    hrow = ws.max_row
    for j in range(1, len(COLUMNS) + 1):
        cell = ws.cell(row=hrow, column=j)
        cell.font = Font(b=True)
        cell.fill = PatternFill("solid", fgColor="F1F3F5")
        cell.alignment = Alignment(wrap_text=True, vertical="center")

    for r in rows:
        ws.append([r[key] for key, _, _ in COLUMNS])

    for j, (_, _, width) in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(j)].width = width
    ws.freeze_panes = ws.cell(row=hrow + 1, column=1)

    # dropdown ตัวเลือกในช่องที่ผู้วิจัยกรอก ให้กรอกได้ตรงกันทุกแถว
    if rows:
        first, last = hrow + 1, hrow + len(rows)
        col = {key: get_column_letter(j) for j, (key, _, _) in enumerate(COLUMNS, start=1)}

        def add_dv(choices, keys):
            dv = DataValidation(type="list", formula1='"' + ",".join(choices) + '"',
                                allow_blank=True)
            dv.error = "กรุณาเลือกจากรายการ: " + " / ".join(choices)
            dv.prompt = " / ".join(choices)
            ws.add_data_validation(dv)
            for k in keys:
                dv.add(f"{col[k]}{first}:{col[k]}{last}")

        add_dv(VERDICT_CHOICES, ["reviewer_verdict"])
        add_dv(CONFIDENCE_CHOICES, ["reviewer_confidence"])
        add_dv(EVIDENCE_OPENED_CHOICES, ["evidence_opened_a", "evidence_opened_b"])

    _write_guide_sheet(wb, scope)

    # แถบตัวเลือกสำหรับกรอก (สำรองกรณีเปิดด้วยโปรแกรมที่ไม่แสดง dropdown)
    ws2 = wb.create_sheet("ตัวเลือก")
    ws2.append(["คำตอบผู้วิจัย", "ความมั่นใจ", "เปิดหลักฐานแล้ว"])
    for i in range(max(len(VERDICT_CHOICES), len(CONFIDENCE_CHOICES),
                       len(EVIDENCE_OPENED_CHOICES))):
        ws2.append([VERDICT_CHOICES[i] if i < len(VERDICT_CHOICES) else "",
                    CONFIDENCE_CHOICES[i] if i < len(CONFIDENCE_CHOICES) else "",
                    EVIDENCE_OPENED_CHOICES[i] if i < len(EVIDENCE_OPENED_CHOICES) else ""])
    ws2.column_dimensions["A"].width = 22
    ws2.column_dimensions["B"].width = 18
    ws2.column_dimensions["C"].width = 18

    wb.save(path)
    wb.close()


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow([th for _, th, _ in COLUMNS])
        for r in rows:
            w.writerow([r[key] for key, _, _ in COLUMNS])


def write_audit_template(path, rows, scope, meta):
    doc = {
        "template_version": REVIEWPACK_VERSION,
        "scope": scope,
        "scope_label": SCOPE_LABEL[scope],
        "frozen_versions": meta["versions"],
        "generated_at": meta["generated_at"],
        "verdict_choices": VERDICT_CHOICES,
        "instructions": {
            "round_1": {"review_round": 1, "seed": 20260827,
                        "note": "ตรวจตามลำดับที่ปรากฏในไฟล์ · ห้ามดูคำตอบใด ๆ ล่วงหน้า"},
            "round_2": {"review_round": 2, "seed": "ระบุค่าใหม่ที่ไม่ใช่ 20260827",
                        "note": "สร้างไฟล์ใหม่สลับลำดับด้วย seed ใหม่ · ห่างจากรอบแรก"
                                "อย่างน้อย 1 วัน · ห้ามแสดงคำตอบรอบแรก · "
                                "ห้ามเปลี่ยนค่าหลักฐานหรือ system classification"},
            "before_import": "สร้างสำเนา read-only ของไฟล์ที่ผู้วิจัยกรอกแล้ว "
                             "คำนวณ SHA-256 บันทึกลง sample_file_sha256 ของรอบนั้น "
                             "แล้วจึง import คำตอบและตรวจ audit chain",
            "after_round_2": "คำนวณ intra-rater agreement แล้ว adjudicate รายการที่ต่างกัน",
        },
        "rounds": {
            "round_1": {"reviewer": "ผู้วิจัย", "review_round": 1,
                        "sample_seed": 20260827, "sample_file_sha256": "",
                        "started_at": "", "finished_at": "",
                        "audit_chain_verified": None, "records": []},
            "round_2": {"reviewer": "ผู้วิจัย", "review_round": 2,
                        "sample_seed": None, "sample_file_sha256": "",
                        "started_at": "", "finished_at": "",
                        "audit_chain_verified": None, "records": []},
        },
        "record_schema": ["sample_id", "finding_ref", "system_classification",
                          "reviewer_verdict", "reviewer_confidence", "reviewer_reason",
                          "reviewed_at", "evidence_opened_a", "evidence_opened_b"],
        "sample_ids": [r["sample_id"] for r in rows],
        "sample_findings": {r["sample_id"]: {
            "finding_ref": r["finding_ref"],
            "system_classification": r["finding_category"],
        } for r in rows},
        "adjudication": [],
        "intra_rater_agreement": None,
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(prog="reviewpack.make_review_package")
    ap.add_argument("--run", nargs="+", required=True, metavar="LABEL=PATH")
    ap.add_argument("--scope", required=True, choices=["primary", "supplementary"])
    ap.add_argument("--sources", default=None)
    ap.add_argument("--sample", default=None)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args(argv)

    outdir = Path(args.outdir)
    if "onedrive" in str(outdir.resolve()).lower():
        print("[หยุด] แบบฟอร์มมีข้อมูลผลตรวจ ต้องเก็บนอก OneDrive")
        return 2
    outdir.mkdir(parents=True, exist_ok=True)

    runs, versions = [], {}
    for spec in args.run:
        label, path = spec.split("=", 1)
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        runs.append((label, doc["run"]))
        versions = doc["run"].get("versions", versions)

    sample_index = None
    if args.sample:
        s = json.loads(Path(args.sample).read_text(encoding="utf-8"))
        sample_index = {(i["run_label"], i["finding_index"]) for i in s["items"]}

    meta = {"versions": " · ".join(f"{k}={v}" for k, v in versions.items()),
            "generated_at": datetime.now(timezone.utc).astimezone()
            .isoformat(timespec="seconds")}

    reader = _CellReader(args.sources)
    try:
        rows = build_rows(runs, reader, args.scope, sample_index)
    finally:
        reader.close()

    xlsx = outdir / f"HUMAN_CHECK_SAMPLE_{args.scope}.xlsx"
    csvf = outdir / f"HUMAN_CHECK_SAMPLE_{args.scope}.csv"
    tmpl = outdir / f"HUMAN_CHECK_AUDIT_TEMPLATE_{args.scope}.json"
    write_xlsx(xlsx, rows, args.scope, meta)
    write_csv(csvf, rows)
    write_audit_template(tmpl, rows, args.scope, meta)

    print(f"[{SCOPE_LABEL[args.scope]}]")
    print(f"  รายการที่ต้องตรวจ: {len(rows)}")
    for p in (xlsx, csvf, tmpl):
        print(f"  - {p.name}  (SHA-256 {_sha256(p)[:16]}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
