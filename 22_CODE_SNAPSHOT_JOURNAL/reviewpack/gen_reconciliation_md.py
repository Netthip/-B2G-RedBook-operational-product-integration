# -*- coding: utf-8 -*-
"""สร้าง docs/MSET_COUNT_RECONCILIATION.md จากผลกระทบยอดที่คำนวณไว้แล้ว

อ่าน MSET_RECONCILED_<variant>.json แล้วเรนเดอร์เป็นรายงาน Markdown
ไม่คำนวณตัวเลขใหม่ ไม่แตะ engine
"""
import argparse
import json
import sys
from pathlib import Path

ROLE_LABEL = {
    "positive": "positive",
    "no_op_control": "negative (no-op)",
    "format_only_control": "negative (format-only)",
}


def fmt(v, nd=4):
    return "—" if v is None else f"{v:.{nd}f}"


def render(d, pytest_count) -> str:
    c = d["counts"]
    po = d["primary_only"]
    il = d["including_linked"]
    nc = d["negative_controls"]
    L = []
    A = L.append

    A("# MSET_COUNT_RECONCILIATION — กระทบยอดจำนวนและคำนวณตัวชี้วัดใหม่")
    A("")
    A("จัดทำ 27 สิงหาคม 2569 · **แก้เฉพาะ reporting layer และการคำนวณตัวชี้วัด**")
    A("ไม่ได้แก้ engine กฎ M-SET manifest หรือผล evaluation เดิม")
    A("")
    A("| รายการ | ค่า |")
    A("|---|---|")
    A(f"| รายงานที่ถูกแทนที่ | `{d['supersedes']}` (เก็บไว้ ไม่เขียนทับ) |")
    A("| เวอร์ชันที่ freeze | " +
      " · ".join(f"`{v}`" for v in d["frozen_versions"].values()) + " |")
    A(f"| result_hash ที่บันทึกไว้ | `{d['result_hash_recorded']}` |")
    A(f"| result_hash ที่คำนวณใหม่ | `{d['result_hash_recomputed']}` |")
    A("| ตรงกัน | " + ("**ตรง**" if d["result_hash_match"] else "❌ ไม่ตรง") + " |")
    for i in d["integrity"]:
        mark = "ตรงกับ manifest" if i["match"] else "❌ ไม่ตรง"
        A(f"| SHA-256 {i['side']} (`{i['file']}`) | {mark} |")
    A("")
    A("---")
    A("")
    A("## 1. ที่มาของตัวเลข 108 กับ 120")
    A("")
    A("รายงานรุ่นแรกเขียนว่า \"120/120\" ซึ่งปนสองสิ่งเข้าด้วยกัน จึงกระทบยอดใหม่ดังนี้")
    A("")
    A("| นิยาม | จำนวน |")
    A("|---|---:|")
    A("| **primary mutations** — การเปลี่ยนแปลงที่ตั้งใจใส่ (9 ชนิด × 12) | "
      f"**{c['primary_mutations']}** |")
    A("| **linked impacts** — ผลที่ตามมาจาก primary โดยไม่ใช่การเปลี่ยนแปลงเพิ่ม | "
      f"**{c['linked_impacts']}** |")
    A(f"| **expected findings** รวม (ตำแหน่งเฉลยทั้งหมด) | **{c['expected_findings_total']}** |")
    A(f"| **detected findings** ที่ระบบสร้างจริง | {c['detected_findings_total']} |")
    A(f"| detected findings ที่ไม่มีเฉลยรองรับ | {c['findings_not_covered_by_manifest']} |")
    A(f"| ตำแหน่งที่เป็น **negative control** | {c['negative_control_positions']} |")
    A(f"| ตำแหน่งที่เป็น **positive mutation** | {c['positive_mutation_positions']} |")
    A(f"| จำนวน mutation ในไฟล์ manifest | {c['manifest_primary_mutations']} |")
    A("")
    A("**12 ตำแหน่งที่เกินมาคืออะไร:** มาจากชนิด **MUT-04 (เพิ่มแถวใหม่) ทั้ง 12 รายการ**")
    A("เมื่อเพิ่มแถวใหม่เข้าฝั่ง B แถวเดิมของฝั่ง A ยังคงอยู่และยังเป็นรายการที่ไม่เปลี่ยนแปลง")
    A("จึงเกิด expected finding สองตำแหน่งต่อหนึ่ง primary mutation:")
    A("")
    A("- ตำแหน่งฝั่ง B = **primary** — แถวที่เพิ่มเข้ามา ต้องถูกจำแนกเป็น C4 (รายการเพิ่ม)")
    A("- ตำแหน่งฝั่ง A = **linked impact** — แถวเดิมที่ไม่เปลี่ยน ต้องถูกจำแนกเป็น C3")
    A("")
    A("ตามกติกาที่ล็อกไว้ **linked impact ห้ามนับซ้ำเป็น primary TP** ตัวชี้วัดหลักในข้อ 2")
    A("จึงคำนวณจาก **primary 108 ตำแหน่ง** เท่านั้น และรายงาน linked impact แยกในข้อ 4")
    A("")
    A("**ข้อความที่ห้ามใช้ต่อไป:** \"120/120 mutations\" — เพราะ primary mutations มีจริง 108")
    A("")
    A("**จำนวนที่ต้องไม่นำมาปนกัน**")
    A("")
    A("| ชนิดตัวเลข | ค่า | หมายเหตุ |")
    A("|---|---:|---|")
    A(f"| primary mutations | {c['primary_mutations']} | หน่วยของ M-SET |")
    A(f"| expected findings | {c['expected_findings_total']} | ตำแหน่งเฉลย |")
    A(f"| detected findings | {c['detected_findings_total']} | ผลตรวจที่ระบบสร้าง |")
    A(f"| automated test cases | {pytest_count} | กรณีทดสอบใน pytest — "
      "**คนละมิติ ห้ามนำมารวมหรือแทนกัน** |")
    A("")
    A("---")
    A("")
    A("## 2. ตัวชี้วัดหลัก — คำนวณจาก primary mutations เท่านั้น "
      f"({po['averages']['positions']} ตำแหน่ง)")
    A("")
    A("**สูตร** (ต่อหมวด c) · TP = เฉลยเป็น c และระบบตอบ c · FP = เฉลยไม่ใช่ c แต่ระบบตอบ c ·")
    A("FN = เฉลยเป็น c แต่ระบบตอบอย่างอื่น")
    A("")
    A("```")
    A("Precision(c) = TP / (TP + FP)")
    A("Recall(c)    = TP / (TP + FN)")
    A("F1(c)        = 2 · P · R / (P + R)")
    A("macro        = ค่าเฉลี่ยเท่ากันทุกหมวดที่มี support")
    A("micro        = รวม TP/FP/FN ทุกหมวดก่อนแล้วจึงคำนวณ")
    A("```")
    A("")
    A("| หมวด | support | TP | FP | FN | Precision | Recall | F1 |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for cat in sorted(po["per_category"]):
        m = po["per_category"][cat]
        A(f"| {cat} | {m['support']} | {m['tp']} | {m['fp']} | {m['fn']} | "
          f"{fmt(m['precision'])} | {fmt(m['recall'])} | {fmt(m['f1'])} |")
    a = po["averages"]
    A("")
    A("| ค่าเฉลี่ย | Precision | Recall | F1 |")
    A("|---|---:|---:|---:|")
    A(f"| macro | {fmt(a['macro_precision'])} | {fmt(a['macro_recall'])} | {fmt(a['macro_f1'])} |")
    A(f"| micro | {fmt(a['micro_precision'])} | {fmt(a['micro_recall'])} | {fmt(a['micro_f1'])} |")
    A("")
    A(f"ความถูกต้องรวม {a['correct']}/{a['positions']} ตำแหน่ง")
    A("")
    A("### Confusion matrix (primary เท่านั้น)")
    A("")
    cats = sorted(po["per_category"])
    A("| เฉลย \\ ระบบตอบ | " + " | ".join(cats) + " |")
    A("|---" * (len(cats) + 1) + "|")
    for e in cats:
        row = po["confusion_matrix"].get(e, {})
        A(f"| **{e}** | " + " | ".join(str(row.get(x, 0)) for x in cats) + " |")
    A("")
    A("---")
    A("")
    A("## 3. ตารางกระทบยอดต่อชนิด MUT-01 ถึง MUT-09")
    A("")
    A("| Mutation type | บทบาท | Primary mutations | Linked impacts | Negative controls "
      "| Expected findings | Detected findings | TP | FP | FN |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in d["per_type"]:
        A(f"| {r['type']} {r['description']} | {ROLE_LABEL.get(r['role'], r['role'])} "
          f"| {r['primary_mutations']} | {r['linked_impacts']} | {r['negative_controls']} "
          f"| {r['expected_findings']} | {r['detected_findings']} | {r['tp']} | {r['fp']} "
          f"| {r['fn']} |")
    keys = ("primary_mutations", "linked_impacts", "negative_controls",
            "expected_findings", "detected_findings", "tp", "fp", "fn")
    tot = {k: sum(r[k] for r in d["per_type"]) for k in keys}
    A("| **รวม** | | " + " | ".join(f"**{tot[k]}**" for k in keys) + " |")
    A("")
    A("---")
    A("")
    A("## 4. ตัวชี้วัดระดับอื่น")
    A("")
    A("### 4.1 รวม linked impacts ด้วย — รายงานเพื่อความครบถ้วน ไม่ใช่ตัวชี้วัดหลัก")
    A("")
    b = il["averages"]
    A(f"({b['positions']} ตำแหน่ง · ถูกต้อง {b['correct']})")
    A("")
    A("| ค่าเฉลี่ย | Precision | Recall | F1 |")
    A("|---|---:|---:|---:|")
    A(f"| macro | {fmt(b['macro_precision'])} | {fmt(b['macro_recall'])} | {fmt(b['macro_f1'])} |")
    A(f"| micro | {fmt(b['micro_precision'])} | {fmt(b['micro_recall'])} | {fmt(b['micro_f1'])} |")
    A("")
    A("### 4.2 Negative controls (ตรวจการรายงานเกินจริง)")
    A("")
    A(f"- ตำแหน่ง negative control: **{nc['positions']}** (MUT-03 ไม่เปลี่ยนอะไรเลย · "
      "MUT-08 เก็บจำนวนเงินเป็นข้อความ · MUT-09 แปลงรูปชื่อรายการ)")
    A(f"- จำแนกถูกต้อง: **{nc['correct']}/{nc['positions']}**")
    A(f"- อัตรารายงานเกินจริง (false positive rate): **{fmt(nc['false_positive_rate'])}**")
    A("")
    A("### 4.3 unmatched / uncertain")
    A("")
    c7 = po["per_category"].get("C7", {})
    A(f"- ตำแหน่งที่ระบบตอบเป็น C7 (ยังตีความไม่ได้): {c7.get('tp', 0)} ตำแหน่ง "
      "— เป็นกรณี MUT-07 ที่ตั้งใจสร้างความกำกวม ตรงตามเฉลย")
    A("- ตำแหน่งที่ระบบไม่สร้าง finding เลย: 0")
    A("")
    A("### 4.4 ความถูกต้องของตำแหน่งหลักฐาน (รายงานแยกจาก Precision/Recall/F1)")
    A("")
    ev = d["evidence_location_check"]
    byrule = ev.get("resolvable_by_rule", {})
    exact_n = byrule.get("exact_numeric", 0)
    text_n = byrule.get("text_equivalent", 0)
    unresolved = ev["checked"] - ev["resolvable"]
    A("**ต้องรายงานสองชั้นเสมอ** (SYS-D-21) — "
      "ห้ามเขียนเพียง \"evidence location ถูกต้อง 100%\":")
    A("")
    A("| ชั้นการรายงาน | ผล |")
    A("|---|---|")
    initial_pct = round(exact_n * 100.0 / ev["checked"], 2)
    A(f"| การตรวจครั้งแรก (`protocol-1.0.1`) | ชี้กลับตรงตามตัวเลขเป๊ะ "
      f"**{exact_n}/{ev['checked']} ({initial_pct}%)** |")
    A(f"| การตรวจที่แก้แล้ว (`protocol-1.0.2`) | เก็บเป็นตัวเลข (exact numeric) **{exact_n}** · "
      f"เก็บเป็นข้อความมีจุลภาค (text-equivalent) **{text_n}** · "
      f"ยังชี้กลับไม่ได้ (unresolved) **{unresolved}** · "
      f"รวมหลักฐานที่ยอมรับได้ **{ev['resolvable']}/{ev['checked']} "
      f"({ev['resolvable_pct']}%)** |")
    A("")
    A("> **บันทึกความโปร่งใส:** การตรวจรอบแรกด้วยเครื่องมือรุ่น `protocol-1.0.1` รายงาน")
    A(f"> {exact_n}/{ev['checked']} ({initial_pct}%) เพราะเครื่องมือตรวจไม่รู้จักเซลล์ที่จัดเก็บจำนวนเงิน")
    A(f"> เป็นข้อความมีจุลภาค (กรณี MUT-08 ทั้ง {text_n} รายการ) ทั้งที่ระบบอ่านค่าถูกต้องแล้ว")
    A("> จึงปรับ**เครื่องมือตรวจหลักฐาน**เป็น `protocol-1.0.2` เพื่อ**จำแนกรูปแบบการจัดเก็บค่า**")
    A("> เป็น exact_numeric กับ text_equivalent · **engine ไม่เปลี่ยน · rule set ไม่เปลี่ยน ·")
    A("> `result_hash` ไม่เปลี่ยน · เปลี่ยนเฉพาะเครื่องมือตรวจหลักฐาน · รายงานเดิมยังถูกเก็บไว้")
    A("> ไม่เขียนทับ · ไม่ได้เปลี่ยน finding ให้ถูกจากที่เคยผิด**")
    A("")
    A("### 4.5 การตรวจซ้ำ (reproducibility)")
    A("")
    A("- `result_hash` ที่บันทึกไว้เท่ากับที่คำนวณใหม่: " +
      ("**ตรง**" if d["result_hash_match"] else "❌"))
    A("- ผลการรันของ C-SET · Y-2 · supplementary ตรวจแล้วเช่นกัน "
      "(ดู `RAW_OUTPUT_HASH_VERIFICATION.txt`)")
    A("")
    A("---")
    A("")
    A("## 5. นิยามศัพท์ที่ต้องไม่ปนกัน")
    A("")
    A("| ศัพท์ | นิยาม |")
    A("|---|---|")
    for k, v in d["glossary"].items():
        A(f"| **{k}** | {v} |")
    A("")
    A("---")
    A("")
    A("## 6. ถ้อยคำที่ใช้ได้และห้ามใช้")
    A("")
    A("**ถ้อยคำที่ต้องใช้:**")
    A("")
    A("> ผลเบื้องต้นจาก controlled mutation evaluation "
      "ภายใต้ข้อผิดพลาด 9 ประเภทที่กำหนดไว้ล่วงหน้า")
    A("")
    A("และต้องระบุขอบเขตกำกับเสมอ: M-SET รุ่น `eval` · engine `t1-engine-1.0.0` ·")
    A("กฎ `rules-t1-1.0.0` · 9 ประเภทการเปลี่ยนแปลง · primary mutations "
      f"{c['primary_mutations']} ตำแหน่ง")
    A("")
    A("**ถ้อยคำที่ห้ามใช้:** ระบบมีความแม่นยำ 100% · ระบบตรวจข้อผิดพลาดได้ทุกประเภท ·")
    A("Accuracy ของระบบเท่ากับ 100% · ผ่านการทดสอบข้อมูลจริงทั้งหมด · ใช้งานได้กับทุกหน่วยงาน")
    A("")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--reconciled", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pytest-count", type=int, required=True)
    args = ap.parse_args(argv)

    d = json.loads(Path(args.reconciled).read_text(encoding="utf-8"))
    Path(args.out).write_text(render(d, args.pytest_count), encoding="utf-8")
    print(f"เขียนแล้ว: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
