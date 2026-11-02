# -*- coding: utf-8 -*-
"""T1B — เครื่องวัดตัวเลขของคู่แฟ้มหนึ่งคู่ (before/after evidence)

รันชั้น extract → match → compare กับคู่แฟ้มหนึ่งคู่ แล้วพิมพ์ **จำนวนนับ**
อย่างเดียว — ไม่พิมพ์ยอดเงิน ไม่พิมพ์ชื่อรายการ ไม่พิมพ์ตำแหน่งเซลล์พร้อมค่า
จึงนำผลไปวางในรายงานที่ commit ได้

    python scripts/t1b_pair_metrics.py <baseline.xlsx> <current.xlsx> [--json out.json]

🔴 **ไม่แก้ไฟล์ต้นทาง** — เปิดอ่านอย่างเดียวผ่าน adapter เดิม
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from redbook.adapters.ao_workbook import AOWorkbookAdapter          # noqa: E402
from redbook.t1b.compare import compare                              # noqa: E402
from redbook.t1b.matching import match_records                       # noqa: E402
from redbook.t1b.records import (                                    # noqa: E402
    AXIS_BUDGET_CATEGORY,
    ROW_KIND_UNMAPPED,
)


def _records(adapter: AOWorkbookAdapter, path: Path):
    return [env.canonical_record for env in adapter.extract(path)]


def collect(baseline: Path, current: Path) -> dict:
    adapter = AOWorkbookAdapter()
    base = _records(adapter, baseline)
    curr = _records(adapter, current)

    m = match_records(base, curr)
    c = compare(m)

    # --- แกนหมวดงบรายจ่ายที่จับคู่ได้ · ปีบริบทของตารางสองฝั่ง ---
    cat_pairs = [p for p in m.matched
                 if p.baseline.comparison_axis == AXIS_BUDGET_CATEGORY]
    cat_year_known = sum(
        1 for p in cat_pairs
        if getattr(p.baseline, "category_table_fiscal_year", None) is not None
        and getattr(p.current, "category_table_fiscal_year", None) is not None
    )
    cat_year_differs = sum(
        1 for p in cat_pairs
        if getattr(p.baseline, "category_table_fiscal_year", None) is not None
        and getattr(p.current, "category_table_fiscal_year", None) is not None
        and p.baseline.category_table_fiscal_year != p.current.category_table_fiscal_year
    )

    unc = Counter()
    for rec in base + curr:
        for u in rec.uncertainty:
            unc[u] += 1

    sheet_class = Counter()
    for side, recs in (("baseline", base), ("current", curr)):
        seen: dict[str, str] = {}
        for rec in recs:
            seen[rec.sheet_name_actual] = rec.sheet_class
        for cls in seen.values():
            sheet_class[f"{side}:{cls}"] += 1

    return {
        "identity": {
            "reason": m.identity.reason if m.identity else None,
            "baseline_agency": list(m.identity.baseline_agency) if m.identity else [],
            "current_agency": list(m.identity.current_agency) if m.identity else [],
        },
        "input_records": {"baseline": len(base), "current": len(curr),
                          "total": len(base) + len(curr)},
        "match": m.summary(),
        "accounting_ok": m.accounted() == len(base) + len(curr),
        "compare": c.summary(),
        "category_axis": {
            "matched_pairs": len(cat_pairs),
            "table_year_known_both_sides": cat_year_known,
            "table_year_differs": cat_year_differs,
        },
        "unmapped_records": {
            "baseline": sum(1 for r in base if r.row_kind == ROW_KIND_UNMAPPED),
            "current": sum(1 for r in curr if r.row_kind == ROW_KIND_UNMAPPED),
        },
        "uncertainty_counts": dict(sorted(unc.items())),
        "sheet_class_counts": dict(sorted(sheet_class.items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline", type=Path)
    ap.add_argument("current", type=Path)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    data = collect(args.baseline, args.current)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
