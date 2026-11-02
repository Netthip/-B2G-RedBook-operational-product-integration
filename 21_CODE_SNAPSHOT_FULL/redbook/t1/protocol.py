# -*- coding: utf-8 -*-
"""G5 — ตัวรันการทดลองตาม protocol ที่ freeze แล้ว (protocol-1.0.0)

หน้าที่:
  1. อ่าน schema ทั้งสองฝั่ง → สร้าง semantic mapping → **ตรวจ schema conflict ก่อนเสมอ**
  2. ถ้าพบ conflict: สร้าง finding ชนิด `schema_conflict` แล้ว **หยุด**
     ไม่โหลดข้อมูล ไม่จับคู่ ไม่สร้างรายการใหม่/หาย/ยอดเปลี่ยนใด ๆ (คำตัดสิน P1)
  3. ถ้าไม่พบ: โหลดข้อมูล → จับคู่ → จำแนก C1–C7 → สรุป
  4. คำนวณ result_hash จากเนื้อหา finding เท่านั้น (ไม่รวมเวลา ไม่รวมคำตัดสินของมนุษย์)
  5. ตรวจว่าหลักฐานทุก finding ชี้กลับไปยังเซลล์จริงได้ (evidence resolvability)
  6. สุ่มตัวอย่างแบบ stratified สำหรับให้มนุษย์ตรวจ (seed คงที่ตาม P2)
"""
import json
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

import openpyxl

from . import (EXPERIMENT_LABEL_FY2569, SAMPLE_CHECK_LABEL,
               SAMPLE_SIZE_FOR_HUMAN_CHECK, SAMPLING_SEED, frozen_versions)
from ..core.hashing import sha256_text
from .compare import CATEGORY_LABEL, classify, summarize
from .datadict import DATA_SHEET, read_schema
from .loader import load_pair
from .matching import match_records
from .semantic_map import build_mapping, detect_schema_conflicts

STATUS_COMPLETED = "completed"
STATUS_HALTED_SCHEMA_CONFLICT = "halted_schema_conflict"

SCHEMA_CONFLICT_CATEGORY = "SC1"
SCHEMA_CONFLICT_LABEL = "ความหมายของฟิลด์ไม่ตรงกันระหว่างสองไฟล์ (schema conflict)"


@dataclass
class RunResult:
    experiment_label: str
    status: str
    versions: dict = field(default_factory=dict)
    files: dict = field(default_factory=dict)
    schema_report: dict = field(default_factory=dict)
    schema_conflicts: list = field(default_factory=list)
    findings: list = field(default_factory=list)      # list[dict]
    summary: dict = field(default_factory=dict)
    result_hash: str = ""
    duration_ms: int = 0
    halt_reason: str = ""
    record_counts: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _canon_value(v):
    if v is None:
        return "<null>"
    if isinstance(v, float):
        return format(v, ".6f")
    return str(v)


def result_hash(finding_dicts) -> str:
    """แฮชผลตรวจทั้งชุดจาก **เนื้อหา** เท่านั้น — รันซ้ำต้องได้ค่าเดิม

    ไม่รวม: เวลา · ลำดับการรัน · สถานะการพิจารณาของมนุษย์ · คะแนนความคล้ายที่เป็นทศนิยมยาว
    """
    payload = []
    for f in finding_dicts:
        payload.append({
            "cat": f.get("category"),
            "key": [_canon_value(x) for x in (f.get("key") or [])],
            "a": _canon_value(f.get("amount_a")),
            "b": _canon_value(f.get("amount_b")),
            "d": _canon_value(f.get("amount_diff")),
            "lvl": f.get("match_level"),
            "step": f.get("match_step"),
            "ea": _canon_value((f.get("evidence_a") or {}).get("amount_cell")),
            "eb": _canon_value((f.get("evidence_b") or {}).get("amount_cell")),
        })
    payload.sort(key=lambda d: json.dumps(d, ensure_ascii=False, sort_keys=True))
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _schema_conflict_findings(conflicts) -> list:
    """แปลง schema conflict เป็น finding — ไม่มีการเทียบเนื้อหาใด ๆ ตามมา"""
    out = []
    for c in conflicts:
        out.append({
            "category": SCHEMA_CONFLICT_CATEGORY,
            "category_label": SCHEMA_CONFLICT_LABEL,
            "machine_status": "needs_human",
            "match_level": "not_attempted",
            "match_step": 0,
            "key": [c.canonical_field],
            "canonical_field": c.canonical_field,
            "datadict_field": c.datadict_field,
            "field_a": {"file": c.file_label_a, "definition": c.definition_a},
            "field_b": {"file": c.file_label_b, "definition": c.definition_b},
            "reason": c.reason(),
            "action_taken": ("ระบบไม่เริ่มการเปรียบเทียบเนื้อหาระดับรายการ และไม่สร้าง"
                             "รายการเพิ่ม รายการหาย หรือยอดเปลี่ยน เพราะข้อมูลสองฝั่ง"
                             "อยู่คนละระดับความละเอียด"),
            "review_status": "pending",
            "evidence_a": {"sheet_name": "Data Dict", "file_label": c.file_label_a},
            "evidence_b": {"sheet_name": "Data Dict", "file_label": c.file_label_b},
        })
    return out


def run_comparison(path_a, path_b, label_a="A", label_b="B",
                   experiment_label="", agency_filter=None) -> RunResult:
    """รันการเปรียบเทียบหนึ่งคู่ตาม protocol ที่ freeze แล้ว"""
    started = time.perf_counter()
    schema_a = read_schema(path_a, label_a)
    schema_b = read_schema(path_b, label_b)
    mapping_a = build_mapping(schema_a)
    mapping_b = build_mapping(schema_b)

    schema_report = {
        "side_a": {**schema_a.as_dict(), "mapping": mapping_a.as_dict()},
        "side_b": {**schema_b.as_dict(), "mapping": mapping_b.as_dict()},
    }
    files = {
        "a": {"label": label_a, "name": schema_a.file_name, "sha256": schema_a.sha256},
        "b": {"label": label_b, "name": schema_b.file_name, "sha256": schema_b.sha256},
    }

    conflicts = detect_schema_conflicts(schema_a, schema_b)
    if conflicts:
        finding_dicts = _schema_conflict_findings(conflicts)
        duration = int((time.perf_counter() - started) * 1000)
        reason = (f"พบความหมายของฟิลด์ไม่ตรงกัน {len(conflicts)} ฟิลด์ระหว่าง "
                  f"{label_a} และ {label_b} — ระบบหยุดก่อนเปรียบเทียบเนื้อหา")
        return RunResult(
            experiment_label=experiment_label or f"{label_a} เทียบ {label_b}",
            status=STATUS_HALTED_SCHEMA_CONFLICT,
            versions=frozen_versions(), files=files, schema_report=schema_report,
            schema_conflicts=[c.as_dict() for c in conflicts],
            findings=finding_dicts,
            summary={"counts": {SCHEMA_CONFLICT_CATEGORY: len(finding_dicts)},
                     "labels": {SCHEMA_CONFLICT_CATEGORY: SCHEMA_CONFLICT_LABEL},
                     "total_findings": len(finding_dicts),
                     "settled_count": 0,
                     "pending_review_count": len(finding_dicts),
                     "note": "ไม่มีการเปรียบเทียบเนื้อหา จึงไม่มียอดสรุปด้านจำนวนเงิน"},
            result_hash=result_hash(finding_dicts),
            duration_ms=duration, halt_reason=reason,
            record_counts={"a": 0, "b": 0})

    records_a, records_b = load_pair(path_a, mapping_a, schema_a,
                                     path_b, mapping_b, schema_b, agency_filter)
    pairs = match_records(records_a, records_b)
    findings = classify(pairs, records_a, records_b)
    finding_dicts = [f.as_dict() for f in findings]
    duration = int((time.perf_counter() - started) * 1000)

    return RunResult(
        experiment_label=experiment_label or f"{label_a} เทียบ {label_b}",
        status=STATUS_COMPLETED,
        versions=frozen_versions(), files=files, schema_report=schema_report,
        schema_conflicts=[], findings=finding_dicts,
        summary=summarize(findings), result_hash=result_hash(finding_dicts),
        duration_ms=duration,
        record_counts={"a": len(records_a), "b": len(records_b)})


# ---------------------------------------------------------------------------
# ตรวจว่าหลักฐานชี้กลับไปยังเซลล์จริงได้
# ---------------------------------------------------------------------------

def verify_evidence(run: RunResult, path_a, path_b) -> dict:
    """เปิดไฟล์ต้นทางกลับไปตรวจว่าเซลล์ที่ finding อ้างถึงมีค่าตามที่รายงานจริง

    ตรวจได้ 100% ของ finding ที่มีตำแหน่งเซลล์ — เป็นการวัดความถูกต้องของหลักฐาน
    โดยไม่ต้องมีเฉลย
    """
    caches = {}

    def cell_value(path, cell_ref):
        key = str(path)
        if key not in caches:
            fh = open(Path(path), "rb")
            wb = openpyxl.load_workbook(fh, data_only=True, read_only=False)
            caches[key] = (wb, fh)
        wb, _ = caches[key]
        return wb[DATA_SHEET][cell_ref].value

    def _verdict(actual, expected):
        """คืน (ผลการเทียบ, กฎที่ใช้) — แยกให้เห็นว่าเซลล์เก็บเป็นตัวเลขหรือข้อความ

        เซลล์ที่จัดเก็บจำนวนเงินเป็นข้อความมีจุลภาค (เช่น "5,357,900") ถือว่า
        ชี้กลับได้ถูกต้อง แต่รายงานแยกเป็น text_equivalent เพื่อความโปร่งใส
        """
        if isinstance(actual, (int, float)) and not isinstance(actual, bool):
            return (int(actual) == int(expected), "exact_numeric")
        if isinstance(actual, str):
            cleaned = actual.strip().replace(",", "").replace(" ", "")
            try:
                return (int(float(cleaned)) == int(expected), "text_equivalent")
            except ValueError:
                return (False, "unparsable_text")
        return (False, "no_value")

    checked = ok = mismatched = skipped = 0
    by_rule = {"exact_numeric": 0, "text_equivalent": 0}
    problems = []
    try:
        for f in run.findings:
            for side, path, amount_key in (("a", path_a, "amount_a"),
                                           ("b", path_b, "amount_b")):
                ev = f.get(f"evidence_{side}") or {}
                ref = ev.get("amount_cell")
                expected = f.get(amount_key)
                if not ref or expected is None:
                    skipped += 1
                    continue
                checked += 1
                actual = cell_value(path, ref)
                same, rule = _verdict(actual, expected)
                if same:
                    ok += 1
                    by_rule[rule] = by_rule.get(rule, 0) + 1
                else:
                    mismatched += 1
                    if len(problems) < 20:
                        problems.append({"cell": ref, "side": side, "rule": rule,
                                         "expected": expected, "actual": actual})
    finally:
        for wb, fh in caches.values():
            wb.close()
            fh.close()

    return {"checked": checked, "resolvable": ok, "mismatched": mismatched,
            "skipped_no_cell_or_amount": skipped,
            "resolvable_pct": round(100.0 * ok / checked, 2) if checked else None,
            "resolvable_by_rule": by_rule,
            "problems": problems}


# ---------------------------------------------------------------------------
# สุ่มตัวอย่างแบบ stratified สำหรับให้มนุษย์ตรวจ (P3)
# ---------------------------------------------------------------------------

STRATA_FIELDS = ("category", "match_level", "match_step")


def _stratum_of(finding, run_label) -> tuple:
    ev = finding.get("evidence_a") or finding.get("evidence_b") or {}
    agency = (finding.get("key") or ["-"])[0]
    return (finding.get("category"), finding.get("match_level"),
            finding.get("match_step"), agency, run_label)


def stratified_sample(runs, size=SAMPLE_SIZE_FOR_HUMAN_CHECK, seed=SAMPLING_SEED) -> dict:
    """สุ่มตัวอย่าง finding แบบแบ่งชั้น ให้ครอบคลุมทุกชั้นที่มีจริง

    runs: list ของ (ป้ายการทดลอง, RunResult)
    ชั้นใดมีจำนวนน้อยกว่าโควตา จะถูกเลือกครบทั้งชั้นก่อน แล้วจึงกระจายที่เหลือ
    """
    rng = random.Random(seed)
    buckets = defaultdict(list)
    for run_label, run in runs:
        for i, f in enumerate(run.findings):
            buckets[_stratum_of(f, run_label)].append((run_label, i, f))

    strata = sorted(buckets.keys(), key=lambda k: tuple(str(x) for x in k))
    for k in strata:
        buckets[k].sort(key=lambda t: json.dumps(t[2], ensure_ascii=False, sort_keys=True))
        rng.shuffle(buckets[k])
    # สลับลำดับชั้นด้วย seed เดียวกัน เพื่อไม่ให้ตัวอย่างเอนไปทางชั้นที่ชื่อขึ้นต้นก่อน
    # (ยังทำซ้ำได้เพราะ seed คงที่)
    rng.shuffle(strata)

    selected, remaining = [], size

    def _take_covering(dimension_index):
        """หยิบหนึ่งรายการต่อหนึ่งค่าของมิติที่ระบุ เพื่อรับประกันความครอบคลุม"""
        nonlocal remaining
        seen = set()
        for k in strata:
            if remaining <= 0:
                return
            if k[dimension_index] in seen or not buckets[k]:
                continue
            seen.add(k[dimension_index])
            selected.append((k, buckets[k].pop()))
            remaining -= 1

    # รอบที่ 1: ครบทุกหมวดผล · รอบที่ 2: ครบทุกการทดลอง (ปี/สถานะเอกสาร)
    # · รอบที่ 3: ครบทุกวิธีจับคู่
    _take_covering(0)   # category
    _take_covering(4)   # run label
    _take_covering(1)   # match level
    # รอบที่ 2 เป็นต้นไป: วนแจกทีละชั้นจนครบจำนวนหรือของหมด
    while remaining > 0 and any(buckets[k] for k in strata):
        progressed = False
        for k in strata:
            if remaining <= 0:
                break
            if buckets[k]:
                selected.append((k, buckets[k].pop()))
                remaining -= 1
                progressed = True
        if not progressed:
            break

    items = []
    for stratum, (run_label, index, f) in selected:
        items.append({
            "run_label": run_label,
            "finding_index": index,
            "stratum": {"category": stratum[0], "match_level": stratum[1],
                        "match_step": stratum[2], "agency_code": stratum[3],
                        "run": stratum[4]},
            "category_label": CATEGORY_LABEL.get(f.get("category"),
                                                 f.get("category_label", "")),
            "key": f.get("key"),
            "amount_a": f.get("amount_a"), "amount_b": f.get("amount_b"),
            "amount_diff": f.get("amount_diff"),
            "evidence_a": f.get("evidence_a"), "evidence_b": f.get("evidence_b"),
        })

    total = sum(len(v) for v in buckets.values()) + len(items)
    return {
        "label": SAMPLE_CHECK_LABEL,
        "seed": seed,
        "requested_size": size,
        "selected_size": len(items),
        "strata_count": len(strata),
        "population_size": total,
        "coverage_note": (
            "สุ่มแบบแบ่งชั้นตามหมวดผล วิธีจับคู่ ขั้นของ pipeline หน่วยงาน และการทดลอง "
            "ชั้นที่มีจำนวนน้อยถูกเลือกครบก่อน"),
        "limitation_note": (
            "ผลจากตัวอย่างชุดนี้ใช้ประเมินความสอดคล้องของผลระบบกับหลักฐานเท่านั้น "
            "ไม่ใช่ค่าความแม่นยำของประชากรทั้งหมด และมีข้อจำกัดด้านขนาดตัวอย่าง"),
        "items": items,
    }


EXPERIMENT_LABELS = {"fy2569_pair": EXPERIMENT_LABEL_FY2569}
