# -*- coding: utf-8 -*-
"""ตรวจศัพท์ต้องห้ามและขอบเขตข้อกล่าวอ้าง — `D1-R` หมวด 6.1

🔴 คำสั่ง Bo · `BO REVIEW COMPLETE` (Issue #1) · LANE D —
*"Proceed without Gift on: … citation/numbering/terminology audit plan"*

เอกสาร `LANE_D1R_THESIS_RESEARCH_CROSSWALK.md` หมวด 6.1 เขียนไว้เองว่า
*"ทำเป็น checklist ก่อนส่งทุกครั้ง **ไม่ใช่ครั้งเดียวจบ**"* — checklist ที่ต้อง
grep ด้วยมือทุกครั้งคือ checklist ที่จะถูกข้าม เครื่องมือนี้จึงทำให้มันรันได้

**อ่านอย่างเดียว** — ไม่แก้ไฟล์ใด ไม่เขียนอะไรลงดิสก์

    python claim_terminology_audit.py <ไดเรกทอรีหรือไฟล์> [...]
    python claim_terminology_audit.py --self-test

ออก ``0`` เมื่อไม่พบข้อละเมิด · ออก ``1`` เมื่อพบ

---

🔴 **ข้อจำกัดที่ต้องอ่านก่อนเชื่อผลลัพธ์**

เครื่องมือนี้ **แยกไม่ออก** ระหว่าง *การใช้ถ้อยคำต้องห้าม* กับ *การเขียนกฎที่ห้าม
ถ้อยคำนั้น* — ประโยคว่า "ห้ามเขียนว่า แม่นยำ 100%" มีคำต้องห้ามอยู่ในตัวมันเอง

จึงยกเว้นบรรทัดที่มี **เครื่องหมายห้ามอย่างชัดแจ้ง** (ดู :data:`EXEMPT_MARKERS`)
และ **รายงานจำนวนบรรทัดที่ยกเว้นทุกครั้ง** เพื่อไม่ให้ใครอ่านผล "0 ข้อละเมิด"
แล้วสรุปว่าเอกสารสะอาด ⇒ **ผลของเครื่องมือนี้ไม่ใช่การรับรอง** ยังต้องมีคนอ่าน

**สายงาน:** เครื่องมือของสะพานวิจัย · ไม่แตะเล่ม ไม่แตะ frozen Evidence Index
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

AUDIT_VERSION = "claim-terminology-audit-0.1.0"

#: บรรทัดที่มีคำเหล่านี้ถือว่าเป็น **การประกาศกฎ** ไม่ใช่การใช้งาน
EXEMPT_MARKERS = (
    "❌", "audit-allow", "ห้ามใช้", "ห้ามเขียน", "ห้ามเรียก", "ห้ามอ้าง",
    "ห้ามรายงาน", "ห้ามพูด", "ต้องไม่ปรากฏ", "คำต้องห้าม",
)

#: การยกเว้น **ทั้งบล็อก** — สำหรับตารางบัญชีคำต้องห้ามซึ่งจำเป็นต้องพิมพ์คำนั้นจริง
#:
#: 🔴 ตั้งใจให้เป็นการกระทำที่ **จงใจและเห็นได้ในไฟล์** ไม่ใช่การเดาของเครื่องมือ —
#: ใครเปิดไฟล์ก็เห็นว่าช่วงนี้ถูกยกเว้นและเพราะอะไร
BLOCK_BEGIN = "<!-- audit-allow-begin"
BLOCK_END = "<!-- audit-allow-end"

#: ส่วนขยายไฟล์ที่ตรวจ — ตรวจเฉพาะข้อความ ไม่แตะไบนารี
TEXT_SUFFIXES = {".md", ".txt", ".rst", ".html"}

#: ไดเรกทอรีที่ข้ามเสมอ
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


class Rule:
    """หนึ่งกฎ = รูปแบบที่ห้าม + เหตุผล + สิ่งที่ให้ใช้แทน"""

    def __init__(self, rule_id: str, pattern: str, reason: str, instead: str,
                 *, flags: int = 0):
        self.rule_id = rule_id
        self.regex = re.compile(pattern, flags | re.IGNORECASE)
        self.reason = reason
        self.instead = instead


#: กฎทั้งหมดมาจาก `D1-R` หมวด 6.1 และจากข้อกำกับที่ประกาศไว้ในโครงการ
#: 🔴 เพิ่มกฎได้ **ห้ามลบกฎ** โดยไม่มีคำตัดสินอ้างอิง
RULES: list[Rule] = [
    Rule("T-01", r"120\s*/\s*120\s*mutations?",
         "จำนวนนี้รวม linked impact เข้ากับ primary",
         "primary 108 + linked impacts 12 (รายงานแยก)"),
    Rule("T-02", r"(แม่นยำ|ความแม่นยำ)\s*(ร้อยละ\s*)?100|accuracy\s*(of\s*)?100\s*%",
         "ข้อกล่าวอ้างเกินจริง และ accuracy ดิบไร้ความหมายเมื่อ true negative ท่วม",
         "precision / recall / F1 ของ M-SET ตามที่ Evidence Index รองรับ"),
    Rule("T-03", r"inter[\s\-]?rater|\bkappa\b",
         "ผู้ตรวจรายเดียว ไม่มีความสอดคล้องระหว่างผู้ตรวจ",
         "intra-rater agreement"),
    Rule("T-04", r"2,?987\s*หน่วยงาน",
         "ค่าที่ผูกพันคือจำนวน **รหัส** หน่วยงาน ไม่ใช่จำนวนหน่วยงาน",
         "2,987 รหัสหน่วยงาน"),
    Rule("T-05", r"ทุก\s*field\s*เหมือนกันทั้งหมด|ทุกฟิลด์เหมือนกันทั้งหมด",
         "hash ที่ตรงคือ Semantic Result Hash ไม่ใช่ทุกฟิลด์",
         "Semantic Result Hash ตรงกัน (ระบุชั้นที่ตรงและชั้นที่ต่าง)"),
    Rule("T-06", r"CI\s*(ผ่าน|เขียว|pass)",
         "ทั้งสอง repo ไม่มี CI เลย",
         "ผลการรันในเครื่องผู้พัฒนา"),
    Rule("T-07", r"ประหยัดเวลา\s*(ได้)?\s*(ร้อยละ|\d)",
         "ตัวเลขประหยัดเวลาถูกห้ามทุกกรณีตามคำตัดสินเดิม",
         "❌ ห้ามใช้ทุกกรณี — ไม่มีคำแทน"),
    Rule("T-08", r"ตรวจได้ทุก(ประเภท|ชนิด|กรณี)",
         "ทดสอบเฉพาะชุดที่ประกาศไว้",
         "ระบุชุดที่ทดสอบจริง เช่น MUT-01–MUT-09"),
    Rule("T-09", r"\b676\b",
         "เลขนี้ถูกประกาศเป็น SUPERSEDED และจองไว้ถาวร",
         "SUPERSEDED — ห้ามใช้ซ้ำ"),
    Rule("T-10", r"blind\s*evaluation",
         "ยังไม่มีการประเมินแบบปิดตาเกิดขึ้นจริง · โปรโตคอลยังเป็นร่าง",
         "ระบุว่าเป็นโปรโตคอลที่ร่างไว้ หรือใช้ป้าย SUPPLEMENTARY ตามบริบท"),
    Rule("T-11", r"(รับรอง|certif\w*)\s*(ความถูกต้อง|correctness)",
         "ระบบเสนอข้อสังเกต ไม่รับรองความถูกต้องของเอกสาร",
         "ระบบเสนอข้อสังเกต ผู้ตรวจเป็นผู้ตัดสิน"),
]

#: 🔴 คำของ **สายผลิตภัณฑ์หลัง freeze** ที่ห้ามไหลเข้าบทงานวิจัย (`D1-R` หมวด 5)
#: ตรวจเฉพาะเมื่อสั่ง ``--research-scope`` เพราะในเอกสารสายผลิตภัณฑ์ใช้ได้ตามปกติ
PRODUCT_LEAK_RULES: list[Rule] = [
    Rule("P-01", r"\b445\s*(ข้อ|tests?)", "จำนวนชุดทดสอบซอฟต์แวร์หลัง freeze",
         "ไม่นำเข้าบทงานวิจัย — ถ้าจำเป็นต้องเป็น supplement ที่ติดป้ายแยก"),
    Rule("P-02", r"T1B-SR-\d+", "PRODUCT SHADOW-RUN EVIDENCE",
         "ไม่นำเข้าบทงานวิจัย"),
    Rule("P-03", r"t1b-(key|matching|compare|rollup|service|scoring)-\d",
         "เวอร์ชันของเครื่องยนต์สายผลิตภัณฑ์", "ไม่นำเข้าบทงานวิจัย"),
]


class Finding:
    def __init__(self, path: Path, line_no: int, rule: Rule, text: str):
        self.path, self.line_no, self.rule, self.text = path, line_no, rule, text

    def render(self, root: Path) -> str:
        try:
            where = self.path.relative_to(root)
        except ValueError:
            where = self.path.name          # 🔴 ไม่พิมพ์เส้นทางสัมบูรณ์
        snippet = self.text.strip()[:110]
        return (f"{where}:{self.line_no}  [{self.rule.rule_id}] {snippet}\n"
                f"      เหตุผล: {self.rule.reason}\n"
                f"      ใช้แทน: {self.rule.instead}")


def _is_exempt(line: str) -> bool:
    return any(m in line for m in EXEMPT_MARKERS)


def audit_text(text: str, path: Path, rules: list[Rule]):
    """คืน (รายการข้อละเมิด, จำนวนบรรทัดที่ยกเว้น)"""
    findings: list[Finding] = []
    exempted = 0
    in_fence = False
    in_block = False
    for i, raw in enumerate(text.splitlines(), start=1):
        line = unicodedata.normalize("NFC", raw)
        if BLOCK_BEGIN in line:
            in_block = True
            continue
        if BLOCK_END in line:
            in_block = False
            continue
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        hit = [r for r in rules if r.regex.search(line)]
        if not hit:
            continue
        if in_block or _is_exempt(line):
            exempted += 1
            continue
        findings.extend(Finding(path, i, r, line) for r in hit)
    return findings, exempted


def iter_files(targets: list[Path]):
    for t in targets:
        if t.is_file():
            if t.suffix.lower() in TEXT_SUFFIXES:
                yield t
            continue
        for p in sorted(t.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            yield p


def run(targets: list[Path], *, research_scope: bool) -> int:
    rules = RULES + (PRODUCT_LEAK_RULES if research_scope else [])
    root = targets[0] if targets[0].is_dir() else targets[0].parent

    all_findings: list[Finding] = []
    exempted_total = 0
    scanned = 0
    for path in iter_files(targets):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        scanned += 1
        f, e = audit_text(text, path, rules)
        all_findings.extend(f)
        exempted_total += e

    print(f"{AUDIT_VERSION} · กฎที่ใช้ {len(rules)} ข้อ"
          f"{' (รวมกฎกันหลักฐานผลิตภัณฑ์รั่ว)' if research_scope else ''}")
    print(f"ตรวจ {scanned} ไฟล์")
    for f in all_findings:
        print(f.render(root))
    print(f"\nข้อละเมิด {len(all_findings)} จุด · "
          f"บรรทัดที่ยกเว้นเพราะเป็นการประกาศกฎ {exempted_total} บรรทัด")
    print("🔴 ผลนี้ไม่ใช่การรับรอง — เครื่องมือแยก 'ใช้คำต้องห้าม' "
          "ออกจาก 'เขียนกฎที่ห้ามคำนั้น' ไม่ได้ ยังต้องมีคนอ่าน")
    return 1 if all_findings else 0


# ------------------------------------------------------------------ self-test
_CASES = [
    ("ระบบมีความแม่นยำ 100% ในทุกกรณี", ["T-02"]),
    ("ระบบตรวจได้ทุกประเภทของข้อผิดพลาด", ["T-08"]),
    ("🔴 ห้ามเขียนว่า แม่นยำ 100%", []),                 # ประกาศกฎ ⇒ ยกเว้น
    ("❌ ประหยัดเวลา ร้อยละ 40", []),
    ("รายงานผล 120/120 mutations", ["T-01"]),
    ("ตรวจกับ 2,987 หน่วยงาน", ["T-04"]),
    ("ใช้ค่า 2,987 รหัสหน่วยงาน", []),
    ("คำนวณ inter-rater reliability ด้วย kappa", ["T-03"]),
    ("ผล CI ผ่านทั้งหมด", ["T-06"]),
    ("ระบบรับรองความถูกต้องของเอกสาร", ["T-11"]),
    ("ระบบเสนอข้อสังเกต ผู้ตรวจเป็นผู้ตัดสิน", []),
    ("ชุดทดสอบ 445 ข้อ", []),                            # ไม่อยู่ในขอบเขตวิจัย
]

_RESEARCH_CASES = [
    ("ชุดทดสอบ 445 ข้อ", ["P-01"]),
    ("อ้างผลจาก T1B-SR-21011-02", ["P-02"]),
    ("ใช้ t1b-key-0.2.0", ["P-03"]),
]


def self_test() -> int:
    failed = 0
    for text, expected in _CASES:
        got, _ = audit_text(text, Path("x.md"), RULES)
        ids = sorted({f.rule.rule_id for f in got})
        if ids != sorted(expected):
            failed += 1
            print(f"FAIL  {text!r}\n      คาด {sorted(expected)} ได้ {ids}")
    for text, expected in _RESEARCH_CASES:
        got, _ = audit_text(text, Path("x.md"), RULES + PRODUCT_LEAK_RULES)
        ids = sorted({f.rule.rule_id for f in got})
        if not set(expected) <= set(ids):
            failed += 1
            print(f"FAIL  {text!r}\n      คาดอย่างน้อย {expected} ได้ {ids}")
    total = len(_CASES) + len(_RESEARCH_CASES)
    print(f"self-test: ผ่าน {total - failed}/{total}")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("targets", nargs="*", type=Path)
    ap.add_argument("--research-scope", action="store_true",
                    help="เพิ่มกฎกันหลักฐานสายผลิตภัณฑ์รั่วเข้าบทงานวิจัย")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.targets:
        ap.error("ต้องระบุไฟล์หรือไดเรกทอรีที่จะตรวจ")
    return run(args.targets, research_scope=args.research_scope)


if __name__ == "__main__":
    sys.exit(main())
