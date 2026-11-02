# -*- coding: utf-8 -*-
"""ย้ายคำตอบและคอมเมนต์ของผู้วิจัยจากแบบฟอร์มรุ่นเดิมมายังรุ่นใหม่ ด้วย finding ID

หลักการ:
  - จับคู่ด้วย `รหัสรายการตรวจ` (sample_id) เท่านั้น — ไม่ใช้ลำดับแถว
  - ไม่เขียนทับไฟล์เดิม · ไม่แก้ค่าผลตรวจ · ย้ายเฉพาะสิ่งที่ผู้วิจัยกรอก
  - อ่านทั้ง legacy note และ threaded comment ของ Excel
  - รายงานจำนวนที่ย้ายได้/ย้ายไม่ได้ทุกช่อง — ถ้าย้ายไม่ครบต้องเห็นทันที
"""
import hashlib
import json
import re
import zipfile
from pathlib import Path

import openpyxl

from .review_layout_v2 import V2_REVIEWER_HEADERS

# หัวคอลัมน์ของรุ่นเดิม (1.0.0 / 1.1.0) → ฟิลด์กลาง
OLD_HEADER_MAP = {
    "รหัสตัวอย่าง": "sample_id",
    "รหัสรายการตรวจ": "sample_id",
    "เปิดหลักฐาน A แล้ว": "evidence_opened_a",
    "เปิดหลักฐาน B แล้ว": "evidence_opened_b",
    "คำตอบผู้วิจัย": "reviewer_verdict",
    "คำตัดสินผู้วิจัย": "reviewer_verdict",
    "คำตัดสินของผู้วิจัย": "reviewer_verdict",
    "ความมั่นใจผู้วิจัย": "reviewer_confidence",
    "เหตุผล": "reviewer_reason",
    "เหตุผล/หมายเหตุ": "reviewer_reason",
    "วันเวลาที่ตรวจ": "reviewed_at",
}
# รวมหัวคอลัมน์ของรุ่น 1.2.0 เข้าไปด้วย เพื่อให้ใช้เป็นปลายทางการย้ายได้
OLD_HEADER_MAP.update(V2_REVIEWER_HEADERS)

ANSWER_FIELDS = ("evidence_opened_a", "evidence_opened_b", "reviewer_verdict",
                 "reviewer_confidence", "reviewer_reason", "reviewed_at")

# คำตอบรุ่นเก่ากว่า (reviewpack-1.0.0) → คำตอบปัจจุบัน
VERDICT_ALIASES = {
    "ถูกต้อง": "ยืนยัน",
    "ไม่ถูกต้อง": "ไม่ยืนยัน",
    "ตัดสินไม่ได้": "ไม่แน่ใจ",
}


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for b in iter(lambda: fp.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _find_header_row(ws, max_scan=12):
    for r in range(1, min(max_scan, ws.max_row) + 1):
        titles = [c.value for c in ws[r] if c.value]
        mapped = {OLD_HEADER_MAP[t] for t in titles if t in OLD_HEADER_MAP}
        if "sample_id" in mapped and len(mapped) >= 2:
            return r
    return None


def read_threaded_comments(path):
    """อ่าน threaded comment (คอมเมนต์แบบใหม่ของ Excel) ที่ openpyxl ไม่คืนให้"""
    out = {}
    try:
        with zipfile.ZipFile(path) as z:
            parts = [n for n in z.namelist() if "threadedComment" in n and n.endswith(".xml")]
            for part in parts:
                xml = z.read(part).decode("utf-8", "replace")
                for m in re.finditer(r'<threadedComment[^>]*\bref="([A-Z]+\d+)"[^>]*>'
                                     r'(.*?)</threadedComment>', xml, re.S):
                    ref, body = m.group(1), m.group(2)
                    texts = re.findall(r"<text>(.*?)</text>", body, re.S)
                    if texts:
                        clean = [re.sub(r"<[^>]+>", "", t).strip() for t in texts]
                        out.setdefault(ref, []).extend(t for t in clean if t)
    except (zipfile.BadZipFile, KeyError, OSError):
        pass
    return out


def read_old_answers(path, sheet_candidates=("review", "Review")):
    """คืน (answers, notes, report_rows) จากแบบฟอร์มที่ผู้วิจัยกรอกแล้ว"""
    wb = openpyxl.load_workbook(path)
    ws = None
    for name in sheet_candidates:
        if name in wb.sheetnames:
            ws = wb[name]
            break
    if ws is None:
        wb.close()
        return {}, {}, []

    hr = _find_header_row(ws)
    if hr is None:
        wb.close()
        return {}, {}, []

    cols = {}
    for c in ws[hr]:
        field = OLD_HEADER_MAP.get(c.value)
        if field:
            cols[field] = c.column
    if "sample_id" not in cols:
        wb.close()
        return {}, {}, []

    threaded = read_threaded_comments(path)
    answers, notes = {}, {}
    for r in range(hr + 1, ws.max_row + 1):
        sid = ws.cell(row=r, column=cols["sample_id"]).value
        if not sid:
            continue
        row_answers = {}
        for field in ANSWER_FIELDS:
            if field not in cols:
                continue
            v = ws.cell(row=r, column=cols[field]).value
            if v not in (None, ""):
                v = VERDICT_ALIASES.get(str(v).strip(), v) if field == "reviewer_verdict" else v
                row_answers[field] = v
        if row_answers:
            answers[sid] = row_answers

        row_notes = []
        for c in ws[r]:
            if c.comment is not None and c.comment.text.strip():
                row_notes.append({"cell": c.coordinate, "kind": "note",
                                  "text": c.comment.text.strip()})
            for t in threaded.get(c.coordinate, []):
                row_notes.append({"cell": c.coordinate, "kind": "threaded", "text": t})
        if row_notes:
            notes[sid] = row_notes
    wb.close()
    return answers, notes, sorted(set(list(answers) + list(notes)))


def apply_answers(new_path, answers, notes, sheet="Review",
                  header_title="รหัสรายการตรวจ", note_column="reviewer_reason",
                  note_header="เหตุผล/หมายเหตุ"):
    """เขียนคำตอบ/คอมเมนต์ที่ย้ายมาลงไฟล์รุ่นใหม่ ตาม sample_id — คืนรายงานการย้าย"""
    from openpyxl.comments import Comment

    wb = openpyxl.load_workbook(new_path)
    ws = wb[sheet]
    hr = _find_header_row(ws)
    titles = {c.value: c.column for c in ws[hr] if c.value}
    col_sid = titles[header_title]
    field_cols = {}
    for title, field in OLD_HEADER_MAP.items():
        if title in titles:
            field_cols[field] = titles[title]

    rows = {}
    for r in range(hr + 1, ws.max_row + 1):
        sid = ws.cell(row=r, column=col_sid).value
        if sid:
            rows[sid] = r

    report = {"answers_moved": 0, "answers_failed": [], "notes_moved": 0,
              "notes_failed": [], "sample_ids_matched": [], "sample_ids_missing": []}

    for sid, vals in answers.items():
        if sid not in rows:
            report["sample_ids_missing"].append(sid)
            report["answers_failed"].append({"sample_id": sid, "reason": "ไม่พบ sample_id ในไฟล์ใหม่"})
            continue
        report["sample_ids_matched"].append(sid)
        for field, v in vals.items():
            if field not in field_cols:
                report["answers_failed"].append(
                    {"sample_id": sid, "field": field, "reason": "ไม่มีคอลัมน์ปลายทาง"})
                continue
            ws.cell(row=rows[sid], column=field_cols[field], value=v)
            report["answers_moved"] += 1

    for sid, items in notes.items():
        if sid not in rows:
            report["notes_failed"].append({"sample_id": sid, "reason": "ไม่พบ sample_id"})
            continue
        target = ws.cell(row=rows[sid], column=field_cols.get(note_column,
                                                             titles[note_header]))
        merged = "\n".join("[%s · %s] %s" % (i["cell"], i["kind"], i["text"])
                           for i in items)
        existing = target.comment.text if target.comment else ""
        target.comment = Comment(
            (existing + "\n" if existing else "")
            + "คอมเมนต์ที่ย้ายมาจากแบบฟอร์มรุ่นก่อน:\n" + merged, "reviewpack migration")
        report["notes_moved"] += len(items)

    wb.save(new_path)
    wb.close()
    return report


def canonical_content_hash(rows):
    """แฮชเนื้อหาหลักที่ต้องไม่เปลี่ยนข้ามรุ่นแบบฟอร์ม

    ครอบเฉพาะเนื้อหาการประเมิน — ไม่ครอบรูปแบบการแสดงผล ลำดับคอลัมน์ หรือสี
    """
    def norm(v):
        if v is None or v == "":
            return None
        if isinstance(v, bool):
            return str(v)
        if isinstance(v, (int, float)):
            return str(int(v)) if float(v).is_integer() else repr(float(v))
        return str(v).strip()

    payload = []
    for row in sorted(rows, key=lambda r: r["sample_id"]):
        payload.append([norm(row.get(k)) for k in (
            "sample_id", "category", "rule_id", "match_level", "match_step",
            "agency_code", "hierarchy_path", "item_label",
            "raw_value_a", "raw_value_b", "amount_a", "amount_b", "amount_diff",
            "source_location_a", "source_location_b", "machine_status")])
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
