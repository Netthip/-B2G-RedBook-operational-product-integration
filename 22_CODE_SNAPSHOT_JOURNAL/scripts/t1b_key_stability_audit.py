# -*- coding: utf-8 -*-
"""T1B KEY STABILITY / COLLISION AUDIT

ตรวจ 6 ข้อตามคำสั่ง Gift (1 กันยายน 2569) ก่อนอนุญาตให้ freeze ``t1b-key-0.1.0``

1. canonical key เดียวกันเกิด collision กับคนละแผนงานหรือไม่
2. แผนงานเดียวกันต่างปีถูก split เพราะการสะกด/spacing/punctuation หรือไม่
3. การ normalize ปีงบประมาณออกทำให้ชื่อที่ต่างความหมาย collapse กันหรือไม่
4. 21011 / 21016 ที่ใช้เลขข้อไม่ตรงกันจับ semantic plan เดียวกันได้หรือไม่
5. document_level ต่างกันต้องไม่ชนกัน
6. supporting-plan กับ main-plan ต้องไม่เกิด false match
7. ชื่อโครงการซ้ำภายในแผนงานเดียวกันต้องถูกติดธง ``AMBIGUOUS`` **ห้าม collapse อัตโนมัติ**

🔴 **ห้ามใช้ fuzzy similarity เป็น auto-match** — ค่า similarity ในรายงานนี้
ใช้เพื่อ**ชี้ candidate ให้มนุษย์ดู**เท่านั้น การจับคู่จริงใช้ความเท่ากันแบบตรงตัวของคีย์

🔴 อ่านอย่างเดียว ไม่แก้ไฟล์ต้นทางใด · ผลเป็น ``PRODUCT EVIDENCE — POST-FREEZE``

การใช้งาน::

    python scripts/t1b_key_stability_audit.py [SOURCE_DIR]
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redbook import holdout
from redbook.adapters.ao_workbook import AOWorkbookAdapter  # noqa: E402
from redbook.t1b import SECTION_ROLE_PLAN, SECTION_ROLE_PROJECT  # noqa: E402
from redbook.t1b.keys import (  # noqa: E402
    KEY_FROZEN_ON,
    KEY_VERSION,
    PREVIOUS_KEY_FROZEN_ON,
    PREVIOUS_KEY_VERSION,
)
from redbook.t1b.records import ROW_KIND_UNMAPPED  # noqa: E402

# 🔴 คิดจากที่อยู่ของไฟล์นี้ ไม่ใช่เส้นทางตายตัวที่มีชื่อผู้ใช้
_FALLBACK_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "redbook-verify-data" / "sources" / "public" / "ao_workbook"
)
DEFAULT_SOURCE = Path(
    os.environ.get("REDBOOK_T1B_SOURCE_DIR", str(_FALLBACK_SOURCE))
)

#: ความคล้ายที่ถือว่า "อาจเป็นรายการเดียวกันที่ถูกแยกโดยไม่ตั้งใจ"
FALSE_SPLIT_THRESHOLD = 0.86

PLAN_ROLES = (SECTION_ROLE_PLAN, SECTION_ROLE_PROJECT)


def load(source: Path):
    adapter = AOWorkbookAdapter()
    out = {}
    # 🔴 ด่านชุดข้อมูลกันไว้ (P1) — ต้องคัดออกก่อนเรียก adapter
    paths, skipped = holdout.partition(sorted(source.glob("*.xlsx")))
    for path, reason in skipped:
        print(f"[กันไว้] {path.name} — P1 holdout ({reason})")
    for path in paths:
        out[path.name] = [e.canonical_record for e in adapter.extract(path)]
    return out


def fy_of(name: str) -> int:
    return int(name.split("_")[1][2:])


def agency_of(name: str) -> str:
    return name.split("_")[3].split(".")[0]


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def check_1_collisions(by_file):
    """คีย์เดียวกันชี้ไปคนละแผนงาน/คนละเซลล์ ภายในไฟล์เดียวกันหรือไม่"""
    findings = []
    for name, records in by_file.items():
        seen: dict[tuple, tuple] = {}
        for rec in records:
            if rec.row_kind == ROW_KIND_UNMAPPED:
                continue
            # ลายเซ็นต้องรวมทุกมิติที่ใช้เทียบ ให้ตรงกับ matching
            sig = (rec.key, rec.comparison_axis, rec.fiscal_year, rec.budget_category)
            prev = seen.get(sig)
            if prev and prev[0] != rec.cell_ref:
                findings.append((name, rec.key.row_label_norm[:40], prev[0], rec.cell_ref))
            seen[sig] = (rec.cell_ref, rec)
    return findings


def check_2_false_splits(by_file):
    """แผนงานเดียวกันต่างปีถูกแยกเพราะสะกด/ช่องว่าง/เครื่องหมายหรือไม่"""
    per_agency = defaultdict(lambda: defaultdict(set))
    for name, records in by_file.items():
        ag, fy = agency_of(name), fy_of(name)
        for rec in records:
            if rec.key.sheet_role in PLAN_ROLES and rec.key.section_title_norm:
                per_agency[ag][fy].add((rec.key.sheet_role, rec.key.section_title_norm))

    candidates = []
    for ag, by_year in per_agency.items():
        years = sorted(by_year)
        if len(years) < 2:
            continue
        a, b = by_year[years[0]], by_year[years[1]]
        for role_a, title_a in sorted(a - b):
            for role_b, title_b in sorted(b - a):
                if role_a != role_b:
                    continue
                ratio = similarity(title_a, title_b)
                if ratio >= FALSE_SPLIT_THRESHOLD:
                    candidates.append((ag, role_a, title_a, title_b, round(ratio, 4)))
    return candidates


def check_3_year_normalization_collapse(by_file):
    """การตัดเลขปีออกทำให้หัวเรื่องที่ต่างความหมาย collapse กันหรือไม่"""
    # 🔴 ต้องเทียบ **ภายในไฟล์เดียวกัน** — ข้ามปีชื่อเดียวกันคนละเลขข้อคือผลที่ตั้งใจ
    collapsed = defaultdict(set)
    for name, records in by_file.items():
        for rec in records:
            if rec.key.sheet_role in PLAN_ROLES and rec.key.section_title_norm:
                collapsed[(name, rec.key.section_title_norm)].add(str(rec.section_title_raw))
    return {k: v for k, v in collapsed.items() if len(v) > 1}


def check_4_cross_agency_semantic_match(by_file):
    """หน่วยงานที่ใช้เลขข้อไม่ตรงกัน จับ semantic plan เดียวกันได้หรือไม่"""
    index = defaultdict(list)   # title -> [(agency, fy, role, section_number_raw)]
    for name, records in by_file.items():
        ag, fy = agency_of(name), fy_of(name)
        for rec in records:
            if rec.key.sheet_role in PLAN_ROLES and rec.key.section_title_norm:
                num = str(rec.section_title_raw).split()[0] if rec.section_title_raw else "?"
                entry = (ag, fy, rec.key.sheet_role, num)
                if entry not in index[rec.key.section_title_norm]:
                    index[rec.key.section_title_norm].append(entry)
    matched = {
        title: entries
        for title, entries in index.items()
        if len({e[3] for e in entries}) > 1     # เลขข้อไม่ตรงกันแต่ชื่อเดียวกัน
    }
    return matched


def check_7_ambiguous_project_titles(by_file):
    """ชื่อโครงการซ้ำภายในแผนเดียวกัน — ต้องถูกติดธง ไม่ใช่ collapse เงียบ ๆ"""
    from redbook.t1b.records import UNC_AMBIGUOUS_PROJECT_TITLE

    per_file = {}
    for name, records in by_file.items():
        sheets_per_title = defaultdict(set)
        flagged = set()
        for rec in records:
            if rec.key.sheet_role != SECTION_ROLE_PROJECT or not rec.key.section_title_norm:
                continue
            sig = (rec.key.parent_plan_norm, rec.key.section_title_norm)
            sheets_per_title[sig].add(rec.sheet_name_actual)
            if UNC_AMBIGUOUS_PROJECT_TITLE in rec.uncertainty:
                flagged.add(sig)
        duplicates = {sig for sig, sheets in sheets_per_title.items() if len(sheets) > 1}
        if duplicates or flagged:
            per_file[name] = {"duplicates": duplicates, "flagged": flagged}
    return per_file


def check_8_ordinal_not_in_identity(by_file):
    """เลขลำดับโครงการต้องไม่อยู่ในคีย์ — คู่ที่ชื่อตรงแต่เลขต่างต้องจับกันได้"""
    index = defaultdict(set)
    for name, records in by_file.items():
        fy = fy_of(name)
        for rec in records:
            if rec.key.sheet_role != SECTION_ROLE_PROJECT or not rec.key.section_title_norm:
                continue
            index[(agency_of(name), rec.key.parent_plan_norm, rec.key.section_title_norm)].add(
                (fy, rec.project_ordinal_raw)
            )
    return {
        k: sorted(v) for k, v in index.items()
        if len({o for _fy, o in v}) > 1     # เลขลำดับต่างกันแต่คีย์เดียวกัน
    }


def check_5_document_level_separation(by_file):
    """คีย์ของระดับกระทรวงกับระดับหน่วยงานต้องไม่ชนกัน"""
    ministry, agency = set(), set()
    for name, records in by_file.items():
        for rec in records:
            if rec.row_kind == ROW_KIND_UNMAPPED:
                continue
            bucket = ministry if rec.key.document_level == "ministry" else agency
            bucket.add(rec.key)
    return ministry & agency


def check_6_supporting_vs_main(by_file):
    """คีย์ของชีตประกอบต้องไม่ชนกับคีย์ของชีตหลัก"""
    # นับเฉพาะ record ที่ใช้จับคู่ได้จริง — UNMAPPED ไม่เข้าการจับคู่อยู่แล้ว
    supporting, main = set(), set()
    for name, records in by_file.items():
        for rec in records:
            if rec.row_kind == ROW_KIND_UNMAPPED:
                continue
            target = supporting if rec.sheet_class == "SUPPORTING" else main
            target.add(rec.key)
    return supporting & main


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not source.exists():
        print(f"ไม่พบคลังข้อมูลที่ {source}")
        return 2

    by_file = load(source)

    print("# T1B KEY STABILITY / COLLISION AUDIT\n")
    # 🔴 รายงานต้องบอกเองว่าตรวจคีย์เวอร์ชันใด — ห้ามให้ผู้อ่านเดา
    print(f"**คีย์ที่ตรวจ:** `{KEY_VERSION}` (ตรึง {KEY_FROZEN_ON}) · "
          f"**เวอร์ชันก่อนหน้า:** `{PREVIOUS_KEY_VERSION}` "
          f"(ตรึง {PREVIOUS_KEY_FROZEN_ON})\n")
    print(f"**คลังข้อมูล:** `{source.name}` · {len(by_file)} แฟ้ม\n")
    print("## unique keys ต่อไฟล์\n")
    print("| ไฟล์ | records | unique keys | UNMAPPED | ambiguous |")
    print("|---|---:|---:|---:|---:|")
    for name, records in by_file.items():
        usable = [r for r in records if r.row_kind != ROW_KIND_UNMAPPED]
        ambiguous = sum(1 for r in records if r.needs_review)
        print(f"| `{name}` | {len(records)} | {len({r.key for r in usable})} | "
              f"{sum(1 for r in records if r.row_kind == ROW_KIND_UNMAPPED)} | {ambiguous} |")

    c1 = check_1_collisions(by_file)
    c2 = check_2_false_splits(by_file)
    c3 = check_3_year_normalization_collapse(by_file)
    c4 = check_4_cross_agency_semantic_match(by_file)
    c5 = check_5_document_level_separation(by_file)
    c6 = check_6_supporting_vs_main(by_file)
    c7 = check_7_ambiguous_project_titles(by_file)
    c8 = check_8_ordinal_not_in_identity(by_file)

    print("\n## ผลตรวจ 6 ข้อ\n")
    print("| # | เกณฑ์ | ผล | จำนวน |")
    print("|---|---|---|---:|")
    print(f"| 1 | คีย์ชนกันภายในไฟล์ | {'✅ ไม่พบ' if not c1 else '🔴 พบ'} | {len(c1)} |")
    print(f"| 2 | false-split candidates | {'✅ ไม่พบ' if not c2 else '⚠️ พบ'} | {len(c2)} |")
    print(f"| 3 | normalize ปี ทำให้ collapse | {'✅ ไม่พบ' if not c3 else '🔴 พบ'} | {len(c3)} |")
    print(f"| 4 | จับ plan เดียวกันข้ามเลขข้อ | {'✅ จับได้' if c4 else '⚠️ ไม่พบคู่'} | {len(c4)} |")
    print(f"| 5 | ระดับเอกสารชนกัน | {'✅ ไม่ชน' if not c5 else '🔴 ชน'} | {len(c5)} |")
    print(f"| 6 | supporting ชนกับ main | {'✅ ไม่ชน' if not c6 else '🔴 ชน'} | {len(c6)} |")
    unflagged = any(v["duplicates"] - v["flagged"] for v in c7.values())
    print(f"| 7 | ชื่อโครงการซ้ำใน plan ถูก collapse เงียบ | "
          f"{'🔴 พบ' if unflagged else '✅ ไม่พบ'} | "
          f"{sum(len(v['duplicates'] - v['flagged']) for v in c7.values())} |")
    print(f"| 8 | จับคู่โครงการข้ามเลขลำดับได้ | "
          f"{'✅ จับได้' if c8 else '⚠️ ไม่พบคู่'} | {len(c8)} |")

    if c1:
        print("\n### 🔴 collision รายการ\n")
        for item in c1[:10]:
            print(f"- `{item[0]}` · {item[1]!r} · {item[2]} vs {item[3]}")
    if c2:
        print("\n### ⚠️ false-split candidates\n")
        for ag, role, ta, tb, ratio in c2:
            print(f"- {ag} · {role} · similarity={ratio}\n  - FY แรก: {ta!r}\n  - FY หลัง: {tb!r}")
    if c3:
        print("\n### 🔴 หัวเรื่องต่างกันแต่ normalize แล้วเท่ากัน\n")
        for (ag, norm), raws in list(c3.items())[:10]:
            print(f"- {ag} · norm={norm!r}")
            for r in sorted(raws):
                print(f"    - raw: {r!r}")

    print("\n### ตัวอย่างคู่ที่ **จับกันได้** (เลขข้อต่างกันแต่แผนเดียวกัน)\n")
    shown = 0
    for title, entries in c4.items():
        nums = sorted({(e[1], e[3]) for e in entries})
        print(f"- {title[:56]!r}")
        for fy, num in nums:
            print(f"    - FY{fy} เลขข้อ `{num}`")
        shown += 1
        if shown >= 5:
            break

    print("\n### ตัวอย่างคู่ที่ **ต้องไม่จับกัน**\n")
    per_agency = defaultdict(lambda: defaultdict(dict))
    for name, records in by_file.items():
        ag, fy = agency_of(name), fy_of(name)
        for rec in records:
            if rec.key.sheet_role in PLAN_ROLES and rec.section_title_raw:
                num = str(rec.section_title_raw).split()[0]
                per_agency[ag][num][fy] = rec.key.section_title_norm
    rejected = 0
    for ag, by_num in sorted(per_agency.items()):
        for num, by_year in sorted(by_num.items()):
            if len(by_year) < 2:
                continue
            titles = list(by_year.values())
            if titles[0] != titles[-1]:
                years = sorted(by_year)
                print(f"- {ag} · เลขข้อเดียวกัน `{num}` แต่คนละแผนงาน ⇒ **ห้าม match**")
                for fy in years:
                    print(f"    - FY{fy}: {by_year[fy][:52]!r}")
                rejected += 1
                if rejected >= 5:
                    break
        if rejected >= 5:
            break

    blocking = bool(c1) or bool(c3) or bool(c5) or bool(c6) or unflagged
    print(f"\n## สรุป\n")
    if blocking:
        print("> ### 🔴 `AUDIT FAILED — UNRESOLVED COLLISION AFFECTING IDENTITY`")
    else:
        print("> ### ✅ `NO UNRESOLVED COLLISION AFFECTING IDENTITY`")
        if c2:
            print(f">\n> มี false-split candidate {len(c2)} คู่ที่ต้องให้มนุษย์ตัดสิน "
                  "— ไม่ใช่ collision ของ identity")
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
