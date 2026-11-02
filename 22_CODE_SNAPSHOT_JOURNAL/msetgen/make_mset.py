# -*- coding: utf-8 -*-
"""สร้างชุดทดสอบแบบควบคุม M-SET พร้อม Mutation Manifest (เฉลย)

การใช้งาน:
    python -m msetgen.make_mset --base <ไฟล์ T1 ต้นแบบ> --variant eval --outdir <โฟลเดอร์>

ผลลัพธ์ 3 ไฟล์:
    MSET_<variant>_MUTATED_sideA_base.xlsx      ฝั่ง A (ไม่ถูกดัดแปลง)
    MSET_<variant>_MUTATED_sideB_applied.xlsx   ฝั่ง B (ใส่การเปลี่ยนแปลงที่ทราบเฉลย)
    MUTATION_MANIFEST_<variant>.json            เฉลยพร้อม SHA-256 ของทั้งสองไฟล์

ชนิดการเปลี่ยนแปลง MUT-01 ถึง MUT-09 อย่างน้อยชนิดละ 10 รายการ (P5)
"""
import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

from . import MSET_GENERATOR_VERSION, MUTATED_MARKER

DATA_DICT_SHEET = "Data Dict"
DATA_SHEET = "data"

# หน่วยงานกรณีศึกษา — กันออกจาก M-SET เพื่อไม่ให้ปนกับชุดกรณีศึกษา
EXCLUDED_AGENCY_CODES = {"21011", "21016"}

MUTATIONS = {
    "MUT-01": ("ลดจำนวนเงิน", "C1"),
    "MUT-02": ("เพิ่มจำนวนเงิน", "C2"),
    "MUT-03": ("ไม่เปลี่ยนแปลง (กลุ่มควบคุม)", "C3"),
    "MUT-04": ("เพิ่มแถวใหม่", "C4"),
    "MUT-05": ("ลบแถวออก", "C5"),
    "MUT-06": ("ย้ายสายลำดับชั้น", "C6"),
    "MUT-07": ("ทำให้คีย์ซ้ำจนกำกวม", "C7"),
    "MUT-08": ("เก็บจำนวนเงินเป็นข้อความ (ค่าเท่าเดิม)", "C3"),
    "MUT-09": ("แปลงรูปชื่อรายการโดยค่าความหมายเท่าเดิม", "C3"),
}

PER_TYPE_DEFAULT = 12   # > 10 ตามเงื่อนไข P5


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _read_base(path):
    fh = open(path, "rb")
    wb = openpyxl.load_workbook(fh, data_only=True, read_only=True)
    dd = [list(r) for r in wb[DATA_DICT_SHEET].iter_rows(values_only=True)]
    it = wb[DATA_SHEET].iter_rows(values_only=True)
    header = list(next(it))
    rows = [list(r) for r in it if r and any(v is not None for v in r)]
    wb.close()
    fh.close()
    return dd, header, rows


def _write_workbook(path, data_dict_rows, header, rows):
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = DATA_DICT_SHEET
    for r in data_dict_rows:
        ws1.append(r)
    ws2 = wb.create_sheet(DATA_SHEET)
    ws2.append(header)
    for r in rows:
        ws2.append(r)
    wb.save(path)
    wb.close()


def build(base_path, variant, outdir, per_type=PER_TYPE_DEFAULT, seed=None):
    base_path = Path(base_path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    # seed ผูกกับ variant เพื่อให้ dev กับ eval ไม่ได้ชุดเดียวกันโดยเด็ดขาด
    rng = random.Random(seed if seed is not None else f"msetgen::{variant}")

    dd_rows, header, all_rows = _read_base(base_path)
    idx = {name: i for i, name in enumerate(str(h).strip() for h in header)}
    agc_i = idx["agc"]
    amount_i = idx["p_total_bud"]
    item_i = idx["item_name"]
    act_i = idx["act_name"]

    pool = [r for r in all_rows
            if str(r[agc_i]).strip() not in EXCLUDED_AGENCY_CODES
            and isinstance(r[amount_i], (int, float))]
    need = per_type * len(MUTATIONS)
    if len(pool) < need + 20:
        raise SystemExit(f"แถวต้นแบบไม่พอ: ต้องการอย่างน้อย {need + 20} พบ {len(pool)}")

    rng.shuffle(pool)
    selected = pool[:need]

    side_a = [list(r) for r in selected]
    side_b = [list(r) for r in selected]
    manifest = []
    appended = []   # (entry, row object) สำหรับหาเลขแถวฝั่ง B หลังจัดเรียงเสร็จ

    cursor = 0
    for mut_id in sorted(MUTATIONS):
        desc, expected = MUTATIONS[mut_id]
        for n in range(per_type):
            i = cursor
            cursor += 1
            row_b = side_b[i]
            row_a = side_a[i]
            entry = {
                "mutation_id": f"{mut_id}#{n + 1:02d}",
                "type": mut_id,
                "description": desc,
                "expected_category": expected,
                "side_a_row_index": i,
                "agency_code": str(row_a[agc_i]).strip(),
                "item_name_before": str(row_a[item_i]),
                "amount_before": row_a[amount_i],
            }

            if mut_id == "MUT-01":
                row_b[amount_i] = int(row_a[amount_i]) - 100
                entry["amount_after"] = row_b[amount_i]
            elif mut_id == "MUT-02":
                row_b[amount_i] = int(row_a[amount_i]) + 250
                entry["amount_after"] = row_b[amount_i]
            elif mut_id == "MUT-03":
                entry["amount_after"] = row_b[amount_i]
            elif mut_id == "MUT-04":
                clone = list(row_a)
                clone[item_i] = f"{row_a[item_i]} (รายการเพิ่มเพื่อการทดสอบ {n + 1})"
                clone[amount_i] = int(row_a[amount_i])
                side_b.append(clone)
                appended.append((entry, clone))
                entry["added_item_name"] = clone[item_i]
                entry["note"] = "แถวนี้มีเฉพาะฝั่ง B"
            elif mut_id == "MUT-05":
                entry["note"] = "แถวนี้ถูกลบออกจากฝั่ง B"
                side_b[i] = None
            elif mut_id == "MUT-06":
                row_b[act_i] = f"{row_a[act_i]} (ย้ายกิจกรรมเพื่อการทดสอบ)"
                entry["activity_before"] = str(row_a[act_i])
                entry["activity_after"] = row_b[act_i]
            elif mut_id == "MUT-07":
                twin = list(row_a)
                twin[amount_i] = int(row_a[amount_i]) + 1
                side_b.append(twin)
                appended.append((entry, twin))
                entry["note"] = "ฝั่ง B มีสองแถวที่คีย์เหมือนกันทุกช่อง"
            elif mut_id == "MUT-08":
                row_b[amount_i] = f"{int(row_a[amount_i]):,}"
                entry["amount_after"] = row_b[amount_i]
                entry["note"] = "ค่าเท่าเดิมแต่จัดเก็บเป็นข้อความมีจุลภาค"
            elif mut_id == "MUT-09":
                row_b[item_i] = f"{n + 1}) {str(row_a[item_i])}  ".replace(" ", "  ", 1)
                entry["item_name_after"] = row_b[item_i]
                entry["note"] = "เพิ่มเลขหัวข้อและช่องว่างซ้ำ ค่าความหมายเท่าเดิม"

            manifest.append(entry)

    side_b = [r for r in side_b if r is not None]

    # เลขแถวจริงในชีต (แถวหัวตาราง = 1 ข้อมูลเริ่มแถวที่ 2) + เฉลยรายตำแหน่ง
    for e in manifest:
        a_row = e["side_a_row_index"] + 2
        e["side_a_sheet_row"] = a_row
        # MUT-04 เพิ่มแถวใหม่ แถวเดิมฝั่ง A จึงยังเป็นรายการที่ไม่เปลี่ยนแปลง
        first = "C3" if e["type"] == "MUT-04" else MUTATIONS[e["type"]][1]
        e["expectations"] = [{"side": "a", "sheet_row": a_row,
                              "expected_category": first}]
    b_pos = {id(r): i for i, r in enumerate(side_b)}
    for entry, row_obj in appended:
        b_row = b_pos[id(row_obj)] + 2
        entry["side_b_sheet_row"] = b_row
        if entry["type"] == "MUT-04":
            entry["expectations"].append({"side": "b", "sheet_row": b_row,
                                          "expected_category": "C4"})

    stamp = variant.lower()
    path_a = outdir / f"MSET_{stamp}_{MUTATED_MARKER}_sideA_base.xlsx"
    path_b = outdir / f"MSET_{stamp}_{MUTATED_MARKER}_sideB_applied.xlsx"
    _write_workbook(path_a, dd_rows, header, side_a)
    _write_workbook(path_b, dd_rows, header, side_b)

    doc = {
        "generator_version": MSET_GENERATOR_VERSION,
        "variant": variant,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "base_file": base_path.name,
        "base_sha256": _sha256(base_path),
        "per_type": per_type,
        "mutation_types": {k: {"description": v[0], "expected_category": v[1]}
                           for k, v in MUTATIONS.items()},
        "excluded_agency_codes": sorted(EXCLUDED_AGENCY_CODES),
        "side_a": {"file": path_a.name, "rows": len(side_a), "sha256": _sha256(path_a)},
        "side_b": {"file": path_b.name, "rows": len(side_b), "sha256": _sha256(path_b)},
        "warning": ("ชุดนี้เป็นการทดสอบแบบควบคุม ไม่ใช่ข้อมูลจริง "
                    "ห้ามนำผลไปปนกับผลตรวจของข้อมูลจริงในรายงานใด ๆ"),
        "mutations": manifest,
    }
    manifest_path = outdir / f"MUTATION_MANIFEST_{stamp}.json"
    manifest_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    return path_a, path_b, manifest_path, doc


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="msetgen.make_mset")
    ap.add_argument("--base", required=True)
    ap.add_argument("--variant", required=True, choices=["dev", "eval"])
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--per-type", type=int, default=PER_TYPE_DEFAULT)
    args = ap.parse_args(argv)

    a, b, m, doc = build(args.base, args.variant, args.outdir, args.per_type)
    print(f"[M-SET {args.variant}] สร้างแล้ว {len(doc['mutations'])} การเปลี่ยนแปลง "
          f"({args.per_type} ต่อชนิด × {len(MUTATIONS)} ชนิด)")
    for p in (a, b, m):
        print("  -", p.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
