# -*- coding: utf-8 -*-
"""สร้างแบบฟอร์ม Human Review Round 2 จาก frozen instrument baseline v1.3.1

หลักการ (RES-G-04 · คำสั่งผู้รับผิดชอบ 1 ก.ย. 2569):
- ใช้ instrument structure/meaning ของ v1.3.1 (frozen baseline) ไม่ใช้ v1.4.0
- seed ใหม่ที่ไม่ใช่ 20260827 · shuffle ลำดับใหม่
- ไม่มีคำตอบ/ความมั่นใจ/เหตุผล/สถานะเปิดหลักฐานจาก Round 1 ให้เห็น
- finding ID เดิมครบ 21 · evidence สองฝั่งเดิม · classification/canonical เดิม
- wording/decision semantics เดิม · ไม่เพิ่มหรือลดข้อมูลที่มีผลต่อการตัดสิน
- ไม่ import คำตอบจาก Round 1
"""
import sys, random, hashlib, json
from pathlib import Path
import openpyxl

sys.path.insert(0, str(Path(__file__).parent))
from build_review_v3 import (
    sha256, build_review, build_summary, build_evidence_comparison,
    copy_sheet_plain, force_text_cells,
)
from _v4_grouped import read_v131

SEED = 20260901                                   # seed ใหม่ · ไม่ใช่ 20260827
ROUND = 2

from _paths import frozen_baseline_v131, human_review_dir

# 🔴 ไม่มีเส้นทางส่วนบุคคลในซอร์ส — ดู _paths.py · ไม่ตั้ง env จะหยุดพร้อมข้อความ
BASE = frozen_baseline_v131()
OUTDIR = human_review_dir(ROUND)
OUT = OUTDIR / "HUMAN_CHECK_SAMPLE_primary_R2_WORKING_v1.3.1.xlsx"

RESPONSE_FIELDS = ("opened_a", "opened_b", "verdict", "reason", "confidence", "reviewed_at")


def main():
    assert BASE.exists(), f"ไม่พบ frozen baseline: {BASE}"
    base_sha = sha256(BASE)
    src_wb, rows = read_v131(BASE)
    assert len(rows) == 21, f"ต้องมี 21 findings แต่พบ {len(rows)}"

    # ลำดับเดิมของ Round 1 (ไว้พิสูจน์ว่าสลับแล้วจริง)
    order_r1 = [d["fid"] for d in rows]

    # ---- บังคับล้าง response fields ทุกช่อง (กันคำตอบรั่วเด็ดขาด) ----
    for d in rows:
        for k in RESPONSE_FIELDS:
            d[k] = None
        d.setdefault("unit", None)

    # ---- shuffle ด้วย seed ใหม่ ----
    rnd = random.Random(SEED)
    shuffled = rows[:]
    rnd.shuffle(shuffled)
    for i, d in enumerate(shuffled, 1):
        d["seq"] = i                       # ลำดับใหม่ 1..21
    order_r2 = [d["fid"] for d in shuffled]

    # ---- สร้างไฟล์ด้วย generator เดียวกับ v1.3.1 (โครงสร้าง/ถ้อยคำเดิม) ----
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    build_summary(wb, shuffled)
    build_review(wb, shuffled)
    build_evidence_comparison(wb, shuffled)
    for title, hide in (("⚠ อ่านก่อนกรอก", False), ("วิธีตรวจ", False),
                        ("Evidence Preview", False), ("ตำแหน่งตรวจสอบต้นทาง", True),
                        ("Technical Details", True), ("ตัวเลือก", True)):
        if title in src_wb.sheetnames:
            copy_sheet_plain(src_wb[title], wb, title, hide=hide)
    wb.active = 1
    force_text_cells(wb)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    out_sha = sha256(OUT)

    # ---------- validation 8 ข้อ ----------
    chk = openpyxl.load_workbook(OUT)
    rv = chk["Review"]
    item_rows = [r for r in range(5, rv.max_row + 1)
                 if str(rv.cell(r, 2).value or "").startswith("P-")]
    fids = [rv.cell(r, 2).value for r in item_rows]

    res = []
    def V(no, name, ok, detail=""):
        res.append({"no": no, "name": name, "pass": bool(ok), "detail": detail})

    V(1, "21 finding IDs ครบและไม่ซ้ำ",
      len(fids) == 21 and len(set(fids)) == 21, f"{len(fids)} รายการ · ไม่ซ้ำ {len(set(fids))}")

    same_pos = sum(1 for a, b in zip(order_r1, order_r2) if a == b)
    V(2, "ลำดับต่างจาก Round 1",
      order_r2 != order_r1, f"ตำแหน่งที่ตรงกับรอบ 1 = {same_pos}/21")

    filled = 0
    for r in item_rows:
        if any(rv.cell(r, c).value not in (None, "") for c in (16, 17, 18, 19)):
            filled += 1
    V(3, "response fields = กรอกแล้ว 0/21 รายการ", filled == 0, f"กรอกแล้ว {filled}/21 รายการ")

    # หาคำตอบรอบ 1 รั่วทั้งไฟล์ (ทุกชีต)
    r1_tokens = {"ยืนยัน", "ไม่ยืนยัน", "ไม่แน่ใจ", "เปิดแล้ว", "ยังไม่ได้เปิด"}
    leak = []
    for ws in chk.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.strip() in r1_tokens:
                    if ws.title in ("ตัวเลือก",) or ws.sheet_state != "visible":
                        continue          # ชีตรายการตัวเลือก/ซ่อน = ค่าที่ต้องมีอยู่แล้ว
                    if ws.title == "Review" and c.row < 5:
                        continue          # หัวตาราง
                    leak.append(f"{ws.title}!{c.coordinate}")
    V(4, "ไม่มี Round 1 answers รั่วเข้ามา", len(leak) == 0,
      f"พบ {len(leak)} เซลล์" + (f" ({leak[:3]})" if leak else ""))

    canon = sorted((d["fid"], d["amt_a"], d["amt_b"], d.get("canon_key")) for d in shuffled)
    canon_hash = hashlib.sha256(json.dumps(canon, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    V(5, "canonical content เท่ากับ Round 1 instrument",
      canon_hash == "eea5e38546bd59f289d9573a4f7aec8899dc2ee294497706e78c73e90e65f186", canon_hash)

    ec = chk["Evidence Comparison"]
    links = sum(1 for row in ec.iter_rows() for c in row
                if isinstance(c.value, str) and c.value.upper().startswith("=HYPERLINK"))
    V(6, "evidence links ครบตามกติกา", links == 42, f"{links}/42 ลิงก์")

    V(7, "SHA-256 ของไฟล์ Round 2 ก่อนเริ่มกรอก", True, out_sha)
    V(8, "seed ที่ใช้", SEED != 20260827, f"{SEED} (Round 1 ใช้ 20260827)")

    passed = sum(1 for t in res if t["pass"])
    print(f"BASE (frozen v1.3.1) = {base_sha}")
    print(f"OUT  = {OUT}")
    print(f"SHA  = {out_sha}")
    print(f"SEED = {SEED}")
    print(f"\nลำดับ Round 1: {' '.join(x[-3:] for x in order_r1)}")
    print(f"ลำดับ Round 2: {' '.join(x[-3:] for x in order_r2)}")
    print(f"\nVALIDATION {passed}/8")
    for t in res:
        print(f"  {'✅' if t['pass'] else '❌'} {t['no']}. {t['name']}  —  {t['detail']}")


if __name__ == "__main__":
    main()
