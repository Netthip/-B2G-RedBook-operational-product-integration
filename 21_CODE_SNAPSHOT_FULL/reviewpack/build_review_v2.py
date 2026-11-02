# -*- coding: utf-8 -*-
"""CLI สร้างแบบฟอร์ม Human Review รุ่น `reviewpack-1.2.0` (display/review revision)

    python -m reviewpack.build_review_v2 \
        --run CSET_fy2569=<ไฟล์ผล.json> --sources <โฟลเดอร์ไฟล์ต้นทาง> \
        --outdir <โฟลเดอร์ผลลัพธ์> [--migrate-from <ไฟล์ที่ผู้วิจัยกรอกแล้ว>]

**ไม่ใช่ผลการทดลองใหม่** — เป็นการจัดหน้าใหม่จากผลการรันที่ freeze แล้ว
ไม่แตะ engine · rule set · finding classification · raw value · source hash
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .migrate_answers import (canonical_content_hash, read_old_answers,
                              apply_answers, sha256_file)
from .review_layout_v2 import (KEY_ROLES, REVIEWPACK_VERSION_V2,
                               SourceReader, build_records)
from .review_writer_v2 import REVIEW_SCHEMA_VERSION, write_workbook

OUT_BASENAME = "HUMAN_CHECK_SAMPLE_primary_reviewpack-1.2.0"


def rows_for_hash(records):
    """ทำเรคอร์ดให้อยู่ในรูปที่เทียบแฮชข้ามรุ่นแบบฟอร์มได้"""
    out = []
    for rec in records:
        out.append({
            "sample_id": rec["sample_id"],
            "category": rec["category"],
            "rule_id": rec["rule_id"],
            "match_level": rec["match_level"],
            "match_step": rec["match_step"],
            "agency_code": rec["agency_code"],
            "hierarchy_path": " › ".join(
                str(rec[role]) for role, _ in KEY_ROLES[:-1]),
            "item_label": rec["item_label"],
            "raw_value_a": rec["raw_value_a"],
            "raw_value_b": rec["raw_value_b"],
            "amount_a": rec["amount_a"],
            "amount_b": rec["amount_b"],
            "amount_diff": rec["amount_diff"],
            "source_location_a": ("%s!%s" % (rec["file_a_name"], rec["cell_a"])
                                  if rec["cell_a"] else rec["sheet_a"]),
            "source_location_b": ("%s!%s" % (rec["file_b_name"], rec["cell_b"])
                                  if rec["cell_b"] else rec["sheet_b"]),
            "machine_status": rec["machine_status"],
        })
    return out


def audit_template(records, meta, sample_file_sha):
    return {
        "template_version": meta["reviewpack_version"],
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "scope": "primary",
        "scope_label": "PRIMARY CASE REVIEW — สวรส. และสถาบันวัคซีนแห่งชาติ",
        "frozen_versions": meta["versions"],
        "generated_at": meta["generated_at"],
        "canonical_content_hash": meta["canonical_content_hash"],
        # ค่าที่บันทึกใน Audit Trail ต้องเป็นค่าความหมายภาษาอังกฤษ
        # ส่วนภาษาไทยเป็น display label บนแบบฟอร์มเท่านั้น
        "verdict_semantic_values": ["confirmed", "rejected", "uncertain"],
        "verdict_display_to_semantic": {"ยืนยัน": "confirmed",
                                        "ไม่ยืนยัน": "rejected",
                                        "ไม่แน่ใจ": "uncertain"},
        "verdict_choices_display": ["ยืนยัน", "ไม่ยืนยัน", "ไม่แน่ใจ"],
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
        },
        "rounds": {
            "round_1": {"reviewer": "ผู้วิจัย", "review_round": 1,
                        "sample_seed": 20260827,
                        "sample_file_sha256_blank": sample_file_sha,
                        "sample_file_sha256": "", "started_at": "", "finished_at": "",
                        "audit_chain_verified": None, "records": []},
            "round_2": {"reviewer": "ผู้วิจัย", "review_round": 2,
                        "sample_seed": None, "sample_file_sha256": "",
                        "started_at": "", "finished_at": "",
                        "audit_chain_verified": None, "records": []},
        },
        "record_schema": ["sample_id", "finding_ref", "system_classification",
                          "reviewer_verdict_semantic",
                          "reviewer_verdict", "reviewer_confidence",
                          "reviewer_reason", "reviewed_at",
                          "evidence_opened_a", "evidence_opened_b"],
        "sample_ids": [r["sample_id"] for r in records],
        "sample_findings": {r["sample_id"]: {
            "finding_ref": r["finding_ref"],
            "system_classification": r["category"],
            "rule_id": r["rule_id"],
            "machine_status": r["machine_status"],
        } for r in records},
        "adjudication": [],
        "intra_rater_agreement": None,
    }


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(prog="reviewpack.build_review_v2")
    ap.add_argument("--run", required=True, metavar="LABEL=PATH")
    ap.add_argument("--sources", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--migrate-from", default=None)
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    outdir = Path(args.outdir)
    if "onedrive" in str(outdir.resolve()).lower():
        print("[หยุด] แบบฟอร์มมีข้อมูลผลตรวจ ต้องเก็บนอก OneDrive")
        return 2
    outdir.mkdir(parents=True, exist_ok=True)

    label, run_path = args.run.split("=", 1)
    doc = json.loads(Path(run_path).read_text(encoding="utf-8"))
    run = doc["run"]

    reader = SourceReader(args.sources)
    try:
        records = build_records(run, reader, run_label=label)
        sources = {n: str(reader.path_of(n)) for n in
                   {r["file_a_name"] for r in records} | {r["file_b_name"] for r in records}
                   if reader.path_of(n)}
    finally:
        sources_intact = reader.close_and_verify()
    if not sources_intact:
        print("[หยุด] SHA-256 ของไฟล์ต้นทางเปลี่ยนระหว่างอ่าน")
        return 3

    versions = run.get("versions", {})
    meta = {
        "versions": " · ".join("%s=%s" % (k, v) for k, v in versions.items()),
        "generated_at": datetime.now(timezone.utc).astimezone()
        .isoformat(timespec="seconds"),
        "reviewpack_version": REVIEWPACK_VERSION_V2,
        "canonical_content_hash": canonical_content_hash(rows_for_hash(records)),
    }

    xlsx = outdir / (OUT_BASENAME + ".xlsx")
    if xlsx.exists():
        print("[หยุด] มีไฟล์ %s อยู่แล้ว — ห้ามเขียนทับ" % xlsx.name)
        return 4
    write_workbook(xlsx, records, meta, sources)

    migration = None
    if args.migrate_from:
        old = Path(args.migrate_from)
        answers, notes, touched = read_old_answers(old)
        migration = apply_answers(xlsx, answers, notes)
        migration.update({
            "source_file": str(old),
            "source_file_sha256": sha256_file(old),
            "sample_ids_with_input": touched,
            "answer_cells_found": sum(len(v) for v in answers.values()),
            "note_cells_found": sum(len(v) for v in notes.values()),
        })

    tmpl = outdir / ("HUMAN_CHECK_AUDIT_TEMPLATE_primary_reviewpack-1.2.0.json")
    tmpl.write_text(json.dumps(
        audit_template(records, meta, sha256_file(xlsx)),
        ensure_ascii=False, indent=1), encoding="utf-8")

    report = {
        "reviewpack_version": REVIEWPACK_VERSION_V2,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "generated_at": meta["generated_at"],
        "run_label": label,
        "run_result_hash": run.get("result_hash"),
        "record_count": len(records),
        "canonical_content_hash": meta["canonical_content_hash"],
        "output_xlsx": str(xlsx),
        "output_xlsx_sha256": sha256_file(xlsx),
        "audit_template": str(tmpl),
        "source_files_sha_unchanged": sources_intact,
        "source_files": {n: {"sha256_before": reader.sha_before.get(n),
                             "sha256_after": reader.sha_after.get(n)}
                         for n in reader.sha_before},
        "migration": migration,
    }
    report_path = Path(args.report) if args.report else (
        outdir / "MIGRATION_REPORT_reviewpack-1.2.0.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                           encoding="utf-8")

    print("สร้างแล้ว: %s" % xlsx)
    print("  รายการ: %d · canonical_content_hash: %s"
          % (len(records), meta["canonical_content_hash"][:16] + "…"))
    print("  SHA-256: %s" % report["output_xlsx_sha256"])
    print("  ไฟล์ต้นทาง SHA ไม่เปลี่ยน: %s" % sources_intact)
    if migration:
        print("  ย้ายคำตอบ: %d ช่อง · ย้ายคอมเมนต์: %d รายการ · ย้ายไม่ได้: %d"
              % (migration["answers_moved"], migration["notes_moved"],
                 len(migration["answers_failed"]) + len(migration["notes_failed"])))
    print("  รายงาน: %s" % report_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
