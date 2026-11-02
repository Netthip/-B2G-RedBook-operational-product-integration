# -*- coding: utf-8 -*-
"""กระทบยอดและคำนวณตัวชี้วัดของ M-SET ใหม่จาก frozen raw outputs

**โมดูลนี้เป็น reporting layer เท่านั้น** — ไม่แตะ engine ไม่แตะกฎ ไม่แตะ manifest
และไม่รันการจำแนกใหม่ อ่านผลที่ freeze แล้วมาจัดหมวดและคำนวณตัวหารใหม่

เหตุที่ต้องมี: รายงานรุ่นแรกใช้คำว่า "120/120" ซึ่งปนกันระหว่าง
  - primary mutations (การเปลี่ยนแปลงที่ตั้งใจใส่)  = 108
  - linked impacts (ผลพลอยที่ตามมาจาก primary)      = 12
รวมเป็น expected findings 120 ตำแหน่ง
ตามกติกาที่ล็อกไว้ **linked impact ห้ามนับซ้ำเป็น primary TP**
"""
from collections import Counter, defaultdict

# ชนิดที่คาดหวังให้ "ตรวจพบการเปลี่ยนแปลง"
POSITIVE_TYPES = ("MUT-01", "MUT-02", "MUT-04", "MUT-05", "MUT-06", "MUT-07")
# ชนิดที่คาดหวังให้ "ไม่รายงานความต่างของค่า" — ใช้ตรวจ false positive
NO_OP_CONTROL_TYPES = ("MUT-03",)                    # ไม่เปลี่ยนอะไรเลย
FORMAT_ONLY_CONTROL_TYPES = ("MUT-08", "MUT-09")     # เปลี่ยนรูป ค่าความหมายเท่าเดิม
NEGATIVE_CONTROL_TYPES = NO_OP_CONTROL_TYPES + FORMAT_ONLY_CONTROL_TYPES

TYPE_ROLE = {}
for t in POSITIVE_TYPES:
    TYPE_ROLE[t] = "positive"
for t in NO_OP_CONTROL_TYPES:
    TYPE_ROLE[t] = "no_op_control"
for t in FORMAT_ONLY_CONTROL_TYPES:
    TYPE_ROLE[t] = "format_only_control"

# นิยามศัพท์ที่ใช้ในรายงาน — ต้องไม่ปนกัน
GLOSSARY = {
    "primary mutation":
        "การเปลี่ยนแปลงหนึ่งรายการที่ผู้วิจัยตั้งใจใส่ลงชุดทดสอบ ตามชนิด MUT-01..MUT-09",
    "linked impact":
        "ผลที่ตามมาจาก primary mutation หนึ่งรายการโดยไม่ใช่การเปลี่ยนแปลงเพิ่ม "
        "เช่น เมื่อเพิ่มแถวใหม่ในฝั่ง B แถวเดิมฝั่ง A ยังคงเป็นรายการที่ไม่เปลี่ยนแปลง",
    "negative control":
        "การเปลี่ยนแปลงที่คาดหวังว่าระบบจะ 'ไม่' รายงานความต่างของค่า "
        "ใช้ตรวจการรายงานเกินจริง (false positive)",
    "expected finding":
        "ตำแหน่งเฉลยหนึ่งตำแหน่งที่ระบุว่าระบบควรจำแนกเป็นหมวดใด "
        "หนึ่ง primary mutation อาจมีมากกว่าหนึ่ง expected finding",
    "detected finding":
        "รายการผลตรวจที่ระบบสร้างจริงหนึ่งรายการ",
    "unique atomic finding":
        "หนึ่ง detected finding ที่ผูกกับตำแหน่งเซลล์เฉพาะเจาะจงหนึ่งจุด ไม่ซ้ำกับรายการอื่น",
    "source location":
        "ตำแหน่งเซลล์ต้นทาง (ไฟล์ · ชีต · แถว · คอลัมน์) ที่ finding อ้างถึง",
    "automated test case":
        "กรณีทดสอบใน pytest ซึ่งเป็นคนละมิติกับตำแหน่งเฉลยของ M-SET "
        "ห้ามนำจำนวนมารวมหรือแทนกัน",
}


def split_expectations(expectations):
    """แยกตำแหน่งเฉลยเป็น primary กับ linked impact

    กติกา: MUT-04 (เพิ่มแถว) มีสองตำแหน่ง — ฝั่ง B คือ primary (แถวที่เพิ่มเข้ามา)
    ส่วนฝั่ง A คือ linked impact (แถวเดิมที่ยังไม่เปลี่ยนแปลง)
    ชนิดอื่นมีตำแหน่งเดียวและเป็น primary
    """
    primary, linked = [], []
    for e in expectations:
        if e["type"] == "MUT-04" and e["side"] == "a":
            linked.append(e)
        else:
            primary.append(e)
    return primary, linked


def confusion_matrix(rows):
    """เมทริกซ์ความสับสน: expected → actual → จำนวน"""
    matrix = defaultdict(Counter)
    for e in rows:
        matrix[e["expected"]][e["actual"] or "(ไม่พบ finding)"] += 1
    return {k: dict(v) for k, v in matrix.items()}


def per_category_metrics(rows):
    """Precision / Recall / F1 ต่อหมวด คำนวณจากตำแหน่งที่ส่งเข้ามาเท่านั้น"""
    cats = sorted({e["expected"] for e in rows} |
                  {e["actual"] for e in rows if e["actual"]})
    out = {}
    for c in cats:
        tp = sum(1 for e in rows if e["expected"] == c and e["actual"] == c)
        fp = sum(1 for e in rows if e["expected"] != c and e["actual"] == c)
        fn = sum(1 for e in rows if e["expected"] == c and e["actual"] != c)
        support = sum(1 for e in rows if e["expected"] == c)
        prec = tp / (tp + fp) if (tp + fp) else None
        rec = tp / (tp + fn) if (tp + fn) else None
        f1 = (2 * prec * rec / (prec + rec)) if (prec and rec) else (
            0.0 if (prec is not None and rec is not None) else None)
        out[c] = {"support": support, "tp": tp, "fp": fp, "fn": fn,
                  "precision": prec, "recall": rec, "f1": f1}
    return out


def averages(metrics, rows):
    """macro = เฉลี่ยเท่ากันทุกหมวดที่มี support · micro = รวมทุกตำแหน่ง"""
    scored = [m for c, m in metrics.items() if m["support"] > 0]
    def _mean(key):
        vals = [m[key] for m in scored if m[key] is not None]
        return sum(vals) / len(vals) if vals else None

    tp = sum(m["tp"] for m in metrics.values())
    fp = sum(m["fp"] for m in metrics.values())
    fn = sum(m["fn"] for m in metrics.values())
    micro_p = tp / (tp + fp) if (tp + fp) else None
    micro_r = tp / (tp + fn) if (tp + fn) else None
    micro_f1 = (2 * micro_p * micro_r / (micro_p + micro_r)) if (micro_p and micro_r) else None
    correct = sum(1 for e in rows if e["correct"])
    return {
        "macro_precision": _mean("precision"),
        "macro_recall": _mean("recall"),
        "macro_f1": _mean("f1"),
        "micro_precision": micro_p,
        "micro_recall": micro_r,
        "micro_f1": micro_f1,
        "accuracy": correct / len(rows) if rows else None,
        "positions": len(rows),
        "correct": correct,
    }


def per_type_table(expectations, manifest):
    """ตารางกระทบยอดต่อชนิด MUT-01..MUT-09"""
    primary, linked = split_expectations(expectations)
    by_type_primary = defaultdict(list)
    by_type_linked = defaultdict(list)
    for e in primary:
        by_type_primary[e["type"]].append(e)
    for e in linked:
        by_type_linked[e["type"]].append(e)

    types_meta = manifest.get("mutation_types", {})
    rows = []
    for t in sorted(set(by_type_primary) | set(by_type_linked)):
        p, li = by_type_primary[t], by_type_linked[t]
        allpos = p + li
        tp = sum(1 for e in p if e["correct"])
        fn = len(p) - tp
        # false positive ของชนิดนี้: ตำแหน่งของชนิดอื่นที่ระบบตอบเป็นหมวดของชนิดนี้
        expected_cat = p[0]["expected"] if p else None
        fp = sum(1 for e in primary
                 if e["type"] != t and e["actual"] == expected_cat) if expected_cat else 0
        rows.append({
            "type": t,
            "role": TYPE_ROLE.get(t, "-"),
            "description": types_meta.get(t, {}).get("description", ""),
            "primary_mutations": len(p),
            "linked_impacts": len(li),
            "negative_controls": len(p) if TYPE_ROLE.get(t) in
                                 ("no_op_control", "format_only_control") else 0,
            "expected_findings": len(allpos),
            "detected_findings": sum(1 for e in allpos if e["actual"]),
            "tp": tp, "fp": fp, "fn": fn,
        })
    return rows


def reconcile(score_doc, manifest) -> dict:
    """คำนวณตัวชี้วัดใหม่ทุกระดับจากผลที่ freeze แล้ว"""
    expectations = score_doc["expectations"]
    primary, linked = split_expectations(expectations)

    m_primary = per_category_metrics(primary)
    m_all = per_category_metrics(expectations)
    neg_rows = [e for e in primary if TYPE_ROLE.get(e["type"]) in
                ("no_op_control", "format_only_control")]
    pos_rows = [e for e in primary if TYPE_ROLE.get(e["type"]) == "positive"]

    return {
        "counts": {
            "primary_mutations": len(primary),
            "linked_impacts": len(linked),
            "expected_findings_total": len(expectations),
            "detected_findings_total": score_doc.get("findings_total"),
            "findings_not_covered_by_manifest":
                score_doc.get("findings_not_covered_by_manifest"),
            "negative_control_positions": len(neg_rows),
            "positive_mutation_positions": len(pos_rows),
            "manifest_primary_mutations": len(manifest.get("mutations", [])),
        },
        "primary_only": {
            "per_category": m_primary,
            "averages": averages(m_primary, primary),
            "confusion_matrix": confusion_matrix(primary),
        },
        "including_linked": {
            "per_category": m_all,
            "averages": averages(m_all, expectations),
            "confusion_matrix": confusion_matrix(expectations),
        },
        "negative_controls": {
            "positions": len(neg_rows),
            "correct": sum(1 for e in neg_rows if e["correct"]),
            "false_positive_rate": (
                sum(1 for e in neg_rows if not e["correct"]) / len(neg_rows)
                if neg_rows else None),
        },
        "per_type": per_type_table(expectations, manifest),
        "glossary": GLOSSARY,
    }
