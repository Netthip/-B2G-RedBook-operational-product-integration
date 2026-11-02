# -*- coding: utf-8 -*-
"""CLI การทดลอง Phase 2C (T1) — รันตาม protocol ที่ freeze แล้ว

คำสั่ง:
  pair    รันเปรียบเทียบหนึ่งคู่ไฟล์ (กรองหน่วยงานได้) + ตรวจหลักฐาน + รันซ้ำพิสูจน์
  score   ให้คะแนน M-SET เทียบ Mutation Manifest (precision / recall / F1)
  sample  สุ่มตัวอย่างแบบแบ่งชั้นจากผลการรันที่บันทึกไว้ เพื่อให้มนุษย์ตรวจ

ผลลัพธ์ทั้งหมดเขียนลงโฟลเดอร์นอก git และนอก OneDrive เท่านั้น
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .t1 import SAMPLE_SIZE_FOR_HUMAN_CHECK, SAMPLING_SEED, frozen_versions
from .report.mset_reconcile import reconcile
from .t1.compare import CATEGORY_LABEL
from .t1.datadict import sha256_of
from .t1.protocol import (STATUS_HALTED_SCHEMA_CONFLICT, run_comparison,
                          stratified_sample, verify_evidence)

EXIT_OK, EXIT_ERROR, EXIT_BAD_ARGS = 0, 1, 2


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _guard_outdir(outdir: Path, allow_onedrive: bool) -> bool:
    if "onedrive" in str(outdir.resolve()).lower() and not allow_onedrive:
        print("[หยุด] โฟลเดอร์ผลลัพธ์อยู่ใน OneDrive — ผลการทดลองต้องเก็บนอกคลาวด์")
        return False
    return True


def _dump(obj, path: Path):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str),
                    encoding="utf-8")


# ---------------------------------------------------------------- pair
def cmd_pair(args) -> int:
    outdir = Path(args.outdir)
    if not _guard_outdir(outdir, args.allow_onedrive):
        return EXIT_BAD_ARGS
    outdir.mkdir(parents=True, exist_ok=True)

    agencies = set(args.agency) if args.agency else None
    run = run_comparison(args.file_a, args.file_b, args.label_a, args.label_b,
                         experiment_label=args.experiment, agency_filter=agencies)

    print(f"[การทดลอง] {run.experiment_label}")
    print(f"  สถานะ: {run.status}")
    for side in ("a", "b"):
        f = run.files[side]
        print(f"  ฝั่ง {side.upper()}: {f['name']}  SHA-256 {f['sha256'][:16]}…")

    if run.status == STATUS_HALTED_SCHEMA_CONFLICT:
        print(f"  🛑 {run.halt_reason}")
        for c in run.schema_conflicts:
            print(f"     ฟิลด์ {c['datadict_field']} → canonical {c['canonical_field']}")
            print(f"       {c['file_label_a']}: {c['definition_a']!r}")
            print(f"       {c['file_label_b']}: {c['definition_b']!r}")
        print("  ระบบไม่เริ่มเปรียบเทียบเนื้อหา และไม่สร้างรายการเพิ่ม/หาย/ยอดเปลี่ยนใด ๆ")
    else:
        print(f"  เรคอร์ด: ฝั่ง A {run.record_counts['a']:,} · ฝั่ง B {run.record_counts['b']:,}")
        counts = run.summary["counts"]
        for cat in sorted(counts):
            if counts[cat]:
                print(f"    {cat} {CATEGORY_LABEL.get(cat, cat)}: {counts[cat]:,}")
        print(f"  ยอดที่สรุปได้ {run.summary['settled_count']:,} · "
              f"รอการยืนยัน {run.summary['pending_review_count']:,}")

    print(f"  result_hash: {run.result_hash}")
    print(f"  เวลา: {run.duration_ms} มิลลิวินาที")

    # --- รันซ้ำเพื่อพิสูจน์ว่าตรวจซ้ำได้ ---
    if args.verify_repeat:
        run2 = run_comparison(args.file_a, args.file_b, args.label_a, args.label_b,
                              experiment_label=args.experiment, agency_filter=agencies)
        same = run2.result_hash == run.result_hash
        print(f"  ตรวจซ้ำ: {'ผ่าน — result_hash เท่าเดิม' if same else '❌ ไม่ผ่าน'}")
        if not same:
            return EXIT_ERROR

    # --- ตรวจว่าหลักฐานชี้กลับได้จริง ---
    evidence = None
    if run.status != STATUS_HALTED_SCHEMA_CONFLICT and args.verify_evidence:
        evidence = verify_evidence(run, args.file_a, args.file_b)
        print(f"  หลักฐานชี้กลับได้: {evidence['resolvable']:,}/{evidence['checked']:,} "
              f"({evidence['resolvable_pct']}%) · ไม่ตรง {evidence['mismatched']}")

    name = args.name or "run"
    _dump({"run": run.as_dict(), "evidence_check": evidence,
           "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")},
          outdir / f"{name}.json")
    print(f"  บันทึก: {outdir / (name + '.json')}")
    return EXIT_OK


# --------------------------------------------------------------- score
def _evidence_rows(ev) -> set:
    """ดึงเลขแถวทั้งหมดจาก evidence (รองรับทั้งแบบเดี่ยวและแบบหลายแถว)"""
    if not isinstance(ev, dict):
        return set()
    if "rows" in ev and isinstance(ev["rows"], list):
        return {r.get("row_number") for r in ev["rows"] if isinstance(r, dict)}
    n = ev.get("row_number")
    return {n} if n else set()


def cmd_score(args) -> int:
    outdir = Path(args.outdir)
    if not _guard_outdir(outdir, args.allow_onedrive):
        return EXIT_BAD_ARGS
    outdir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    run = run_comparison(args.file_a, args.file_b, "MSET-A", "MSET-B",
                         experiment_label=f"M-SET {manifest['variant']}")
    if run.status == STATUS_HALTED_SCHEMA_CONFLICT:
        print("[หยุด] M-SET ทั้งสองฝั่งมี schema conflict — ตรวจการสร้างชุดทดสอบ")
        return EXIT_ERROR

    # ดัชนีจากเลขแถว → finding
    by_a, by_b = defaultdict(list), defaultdict(list)
    for f in run.findings:
        for n in _evidence_rows(f.get("evidence_a")):
            by_a[n].append(f)
        for n in _evidence_rows(f.get("evidence_b")):
            by_b[n].append(f)

    expectations, matched_ids = [], set()
    for m in manifest["mutations"]:
        for exp in m.get("expectations", []):
            table = by_a if exp["side"] == "a" else by_b
            cands = table.get(exp["sheet_row"], [])
            got = cands[0].get("category") if cands else None
            if cands:
                matched_ids.add(id(cands[0]))
            expectations.append({
                "mutation_id": m["mutation_id"], "type": m["type"],
                "side": exp["side"], "sheet_row": exp["sheet_row"],
                "expected": exp["expected_category"], "actual": got,
                "correct": got == exp["expected_category"],
            })

    # precision / recall / F1 ต่อหมวด
    cats = sorted({e["expected"] for e in expectations} |
                  {e["actual"] for e in expectations if e["actual"]})
    metrics = {}
    for c in cats:
        tp = sum(1 for e in expectations if e["expected"] == c and e["actual"] == c)
        fp = sum(1 for e in expectations if e["expected"] != c and e["actual"] == c)
        fn = sum(1 for e in expectations if e["expected"] == c and e["actual"] != c)
        prec = tp / (tp + fp) if (tp + fp) else None
        rec = tp / (tp + fn) if (tp + fn) else None
        f1 = (2 * prec * rec / (prec + rec)) if (prec and rec) else None
        metrics[c] = {"label": CATEGORY_LABEL.get(c, c), "tp": tp, "fp": fp, "fn": fn,
                      "precision": None if prec is None else round(prec, 4),
                      "recall": None if rec is None else round(rec, 4),
                      "f1": None if f1 is None else round(f1, 4)}

    correct = sum(1 for e in expectations if e["correct"])
    by_type = defaultdict(lambda: [0, 0])
    for e in expectations:
        by_type[e["type"]][1] += 1
        if e["correct"]:
            by_type[e["type"]][0] += 1

    print(f"[M-SET {manifest['variant']}] เฉลย {len(expectations)} ตำแหน่ง "
          f"· ถูกต้อง {correct} ({100.0 * correct / len(expectations):.2f}%)")
    for t in sorted(by_type):
        ok, tot = by_type[t]
        print(f"    {t}: {ok}/{tot}")
    print("  หมวด | precision | recall | F1")
    for c in sorted(metrics):
        m = metrics[c]
        def s(v): return "—" if v is None else f"{v:.4f}"
        print(f"    {c} {m['label'][:28]:<28} {s(m['precision'])} {s(m['recall'])} {s(m['f1'])}")

    doc = {
        "manifest_variant": manifest["variant"],
        "manifest_side_a_sha256": manifest["side_a"]["sha256"],
        "manifest_side_b_sha256": manifest["side_b"]["sha256"],
        "versions": frozen_versions(),
        "run_result_hash": run.result_hash,
        "total_expectations": len(expectations),
        "total_correct": correct,
        "accuracy": round(correct / len(expectations), 4) if expectations else None,
        "by_type": {t: {"correct": v[0], "total": v[1]} for t, v in by_type.items()},
        "metrics_by_category": metrics,
        "findings_total": len(run.findings),
        "findings_not_covered_by_manifest": len(run.findings) - len(matched_ids),
        "expectations": expectations,
        "warning": ("ผลชุดนี้มาจากการทดสอบแบบควบคุม ห้ามนำไปปนกับผลตรวจของข้อมูลจริง"),
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    _dump(doc, outdir / f"MSET_SCORE_{manifest['variant']}.json")
    print(f"  บันทึก: {outdir / ('MSET_SCORE_' + manifest['variant'] + '.json')}")
    return EXIT_OK


# ----------------------------------------------------------- reconcile
def _fmt(v, nd=4):
    return "—" if v is None else f"{v:.{nd}f}"


def cmd_reconcile(args) -> int:
    """กระทบยอด M-SET และคำนวณตัวชี้วัดใหม่จาก frozen outputs (ไม่แตะ engine)"""
    outdir = Path(args.outdir)
    if not _guard_outdir(outdir, args.allow_onedrive):
        return EXIT_BAD_ARGS
    outdir.mkdir(parents=True, exist_ok=True)

    score = json.loads(Path(args.score).read_text(encoding="utf-8"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    rec = reconcile(score, manifest)

    # --- ตรวจ SHA-256 ของไฟล์ M-SET ว่าตรงกับที่ manifest บันทึกไว้ ---
    integrity = []
    for side, path in (("side_a", args.file_a), ("side_b", args.file_b)):
        actual = sha256_of(path)
        expected = manifest[side]["sha256"]
        integrity.append({"side": side, "file": Path(path).name,
                          "expected_sha256": expected, "actual_sha256": actual,
                          "match": actual == expected})

    # --- รันซ้ำเพื่อยืนยัน result_hash เดิม และวัดความถูกต้องของตำแหน่งหลักฐาน ---
    rerun = run_comparison(args.file_a, args.file_b, "MSET-A", "MSET-B")
    hash_match = rerun.result_hash == score.get("run_result_hash")
    evidence = verify_evidence(rerun, args.file_a, args.file_b)

    doc = {
        "report_type": "MSET_COUNT_RECONCILIATION",
        "note": ("แก้เฉพาะ reporting layer และการคำนวณตัวชี้วัด "
                 "ไม่ได้แก้ engine กฎ manifest หรือผล evaluation เดิม"),
        "supersedes": Path(args.score).name,
        "frozen_versions": frozen_versions(),
        "manifest_variant": manifest["variant"],
        "integrity": integrity,
        "result_hash_recorded": score.get("run_result_hash"),
        "result_hash_recomputed": rerun.result_hash,
        "result_hash_match": hash_match,
        "evidence_location_check": evidence,
        **rec,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    _dump(doc, outdir / f"MSET_RECONCILED_{manifest['variant']}.json")

    c = rec["counts"]
    print(f"[กระทบยอด M-SET {manifest['variant']}]")
    print(f"  primary mutations        : {c['primary_mutations']}")
    print(f"  linked impacts           : {c['linked_impacts']}")
    print(f"  expected findings รวม     : {c['expected_findings_total']}")
    print(f"  detected findings รวม     : {c['detected_findings_total']}")
    print(f"  finding นอกเฉลย           : {c['findings_not_covered_by_manifest']}")
    print(f"  negative control positions: {c['negative_control_positions']}")
    for side in integrity:
        print(f"  SHA-256 {side['side']}: {'ตรง' if side['match'] else '❌ ไม่ตรง'}")
    print(f"  result_hash เดิม = ที่คำนวณใหม่: {'ตรง' if hash_match else '❌ ไม่ตรง'}")
    print(f"  ตำแหน่งหลักฐานถูกต้อง: {evidence['resolvable']}/{evidence['checked']} "
          f"({evidence['resolvable_pct']}%)")
    a = rec["primary_only"]["averages"]
    print(f"  [primary เท่านั้น {a['positions']} ตำแหน่ง] "
          f"macro P {_fmt(a['macro_precision'])} · R {_fmt(a['macro_recall'])} "
          f"· F1 {_fmt(a['macro_f1'])} | micro F1 {_fmt(a['micro_f1'])}")
    print(f"  บันทึก: {outdir / ('MSET_RECONCILED_' + manifest['variant'] + '.json')}")
    return EXIT_OK


def cmd_verify_hashes(args) -> int:
    """ตรวจว่าผลการรันที่บันทึกไว้ยังคำนวณซ้ำได้ค่าเดิม"""
    rows = []
    for spec in args.run:
        label, path = spec.split("=", 1)
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        run = doc["run"]
        rows.append({"label": label, "file": Path(path).name,
                     "status": run["status"],
                     "result_hash": run["result_hash"],
                     "file_a": run["files"]["a"], "file_b": run["files"]["b"]})
        print(f"[{label}] {run['status']}")
        print(f"  result_hash: {run['result_hash']}")
        for side in ("a", "b"):
            f = run["files"][side]
            actual = sha256_of(Path(args.root) / f["name"]) if args.root else None
            mark = "" if actual is None else (" · ตรง" if actual == f["sha256"] else " · ❌")
            print(f"  ฝั่ง {side.upper()}: {f['name']} {f['sha256'][:16]}…{mark}")
    return EXIT_OK


# -------------------------------------------------------------- sample
def cmd_sample(args) -> int:
    outdir = Path(args.outdir)
    if not _guard_outdir(outdir, args.allow_onedrive):
        return EXIT_BAD_ARGS
    outdir.mkdir(parents=True, exist_ok=True)

    class _Run:
        def __init__(self, findings):
            self.findings = findings

    runs = []
    for spec in args.run:
        label, path = spec.split("=", 1)
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        runs.append((label, _Run(doc["run"]["findings"])))

    result = stratified_sample(runs, size=args.size, seed=args.seed)
    print(f"[{result['label']}]")
    print(f"  seed {result['seed']} · ชั้นข้อมูล {result['strata_count']} ชั้น "
          f"· เลือก {result['selected_size']} จาก {result['population_size']:,} finding")
    print(f"  {result['limitation_note']}")
    _dump(result, outdir / "HUMAN_CHECK_SAMPLE.json")
    print(f"  บันทึก: {outdir / 'HUMAN_CHECK_SAMPLE.json'}")
    return EXIT_OK


def main(argv=None) -> int:
    _utf8()
    ap = argparse.ArgumentParser(prog="redbook.experiment_cli")
    ap.add_argument("--allow-onedrive", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pair")
    p.add_argument("--file-a", required=True)
    p.add_argument("--file-b", required=True)
    p.add_argument("--label-a", default="A")
    p.add_argument("--label-b", default="B")
    p.add_argument("--agency", nargs="*", default=None)
    p.add_argument("--experiment", default="")
    p.add_argument("--name", default="run")
    p.add_argument("--outdir", default=str(config.DATA_DIR / "experiments"))
    p.add_argument("--verify-repeat", action="store_true")
    p.add_argument("--verify-evidence", action="store_true")
    p.set_defaults(func=cmd_pair)

    p = sub.add_parser("score")
    p.add_argument("--file-a", required=True)
    p.add_argument("--file-b", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--outdir", default=str(config.DATA_DIR / "experiments"))
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("reconcile")
    p.add_argument("--score", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--file-a", required=True)
    p.add_argument("--file-b", required=True)
    p.add_argument("--outdir", default=str(config.DATA_DIR / "experiments"))
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("verify-hashes")
    p.add_argument("--run", nargs="+", required=True, metavar="LABEL=PATH")
    p.add_argument("--root", default=None)
    p.set_defaults(func=cmd_verify_hashes)

    p = sub.add_parser("sample")
    p.add_argument("--run", nargs="+", required=True, metavar="LABEL=PATH")
    p.add_argument("--size", type=int, default=SAMPLE_SIZE_FOR_HUMAN_CHECK)
    p.add_argument("--seed", type=int, default=SAMPLING_SEED)
    p.add_argument("--outdir", default=str(config.DATA_DIR / "experiments"))
    p.set_defaults(func=cmd_sample)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
