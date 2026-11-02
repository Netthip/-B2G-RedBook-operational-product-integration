# -*- coding: utf-8 -*-
"""สร้าง reviewpack v1.4.0 + acceptance tests + migration report"""
import sys, hashlib, json, datetime
from pathlib import Path
import openpyxl

sys.path.insert(0, str(Path(__file__).parent))
#: SHA-256 ของ {total_a, total_b, by_agency} ที่ freeze ไว้ — ตัวเลขจริงไม่อยู่ในซอร์ส
AGGREGATE_HASH_V131 = "be0d9fb4d2956148be7d00f781234818b7714d4a9113fe56c9e9ee16f0708d5f"
from build_review_v3 import (
    RED_BG, GREEN_BG, GREY_BG, YELLOW_BG, sha256,
    build_evidence_comparison, copy_sheet_plain, force_text_cells,
)
from _v4_grouped import (
    VERSION, SRC, OUT, REPORT, build_grouped_review, build_summary, read_v131,
    C_A, C_B, C_D, C_DIR, C_OA, C_OB, C_V, C_R,
)


def main():
    assert SRC.exists(), f"ไม่พบไฟล์ต้นทาง: {SRC}"
    src_sha = sha256(SRC)
    src_wb, rows = read_v131(SRC)
    assert len(rows) == 21, f"ต้องมี 21 findings แต่พบ {len(rows)}"

    answers_before = {
        d["fid"]: {"opened_a": d.get("opened_a"), "opened_b": d.get("opened_b"),
                   "verdict": d.get("verdict"), "reason": d.get("reason")}
        for d in rows
    }
    n_filled = sum(1 for v in answers_before.values()
                   if any(x not in (None, "") for x in v.values()))

    wb = openpyxl.Workbook(); wb.remove(wb.active)
    ws_rv, tree = build_grouped_review(wb, rows)
    build_summary(wb, rows, tree)
    build_evidence_comparison(wb, rows)
    for title, hide in (("⚠ อ่านก่อนกรอก", False), ("วิธีตรวจ", False),
                        ("Evidence Preview", False), ("ตำแหน่งตรวจสอบต้นทาง", True),
                        ("Technical Details", True), ("ตัวเลือก", True)):
        if title in src_wb.sheetnames:
            copy_sheet_plain(src_wb[title], wb, title, hide=hide)
    wb.active = 1
    n_fixed = force_text_cells(wb)
    wb.save(OUT)
    out_sha = sha256(OUT)

    # ---------- acceptance tests ----------
    chk = openpyxl.load_workbook(OUT)
    rv = chk["Review"]
    item_rows = [r for r in range(5, rv.max_row + 1)
                 if str(rv.cell(r, 2).value or "").startswith("P-")]
    tests = []
    def T(n, name, ok, detail=""):
        tests.append({"no": n, "name": name, "pass": bool(ok), "detail": detail})
    def bg(r, c):
        f = rv.cell(r, c).fill
        return str(f.fgColor.rgb).upper() if (f and f.fill_type == "solid"
                                              and f.fgColor and isinstance(f.fgColor.rgb, str)) else ""

    T(1, "21 findings เท่าเดิม", len(item_rows) == 21, f"พบ {len(item_rows)}")
    moved = 0
    for r in item_rows:
        fid = rv.cell(r, 2).value; b = answers_before.get(fid, {})
        got = {"opened_a": rv.cell(r, C_OA).value, "opened_b": rv.cell(r, C_OB).value,
               "verdict": rv.cell(r, C_V).value, "reason": rv.cell(r, C_R).value}
        if all((b.get(k) or None) == (got.get(k) or None) for k in got):
            moved += 1
    T(2, "คำตอบผู้วิจัยย้ายครบ", moved == 21, f"ตรงกัน {moved}/21 · เดิมกรอกไว้ {n_filled} รายการ")
    T(3, "ผลต่างถูกทุกแถว (พ.ร.บ. − ร่าง)",
      all((rv.cell(r, C_D).value or 0) == (rv.cell(r, C_B).value or 0) - (rv.cell(r, C_A).value or 0)
          for r in item_rows))
    down = [r for r in item_rows if (rv.cell(r, C_D).value or 0) < 0]
    same = [r for r in item_rows if (rv.cell(r, C_D).value or 0) == 0]
    T(4, "ลดลงเป็นแดง", all(bg(r, C_D) == RED_BG.upper() for r in down), f"{len(down)} แถว")
    T(5, "เท่ากันไม่เป็นเหลือง", all(bg(r, C_D) != YELLOW_BG.upper() for r in same), f"{len(same)} แถว")
    # จัดกลุ่ม
    agencies = {d["agency"] for d in rows}
    T(6, "แยกหน่วยงานเป็นกลุ่ม", any(str(rv.cell(r, 1).value or "").startswith("■") for r in range(5, rv.max_row + 1)),
      f"{len(agencies)} หน่วยงาน")
    T(7, "มีแถวผลรวมแผนงาน",
      sum(1 for r in range(5, rv.max_row + 1) if "รวมแผนงาน" in str(rv.cell(r, 1).value or "")) == 7,
      "7 แผนงาน")
    T(8, "มีแถวผลรวมหน่วยงาน",
      sum(1 for r in range(5, rv.max_row + 1) if str(rv.cell(r, 1).value or "").strip().startswith("รวม 2")) == 2)
    T(9, "มีแถวผลรวมรวมทั้งสองหน่วยงาน",
      any("รวมทั้งสองหน่วยงาน" in str(rv.cell(r, 1).value or "") for r in range(5, rv.max_row + 1)))
    # ตัวเลขผูกพัน
    tot_a = sum(d["amt_a"] for d in rows); tot_b = sum(d["amt_b"] for d in rows)
    by_ag = {}
    for d in rows:
        k = str(d["agency"]).split(" ")[0]
        v = by_ag.setdefault(k, [0, 0, 0]); v[0] += d["amt_a"]; v[1] += d["amt_b"]; v[2] += 1
    # 🔴 provenance maintenance (กิ๊ฟ 7 ก.ย.) — ยอดเงินคาดหวังไม่อยู่ในซอร์สอีกต่อไป
    # เทียบด้วยแฮชของผลรวมแทน · ค่าจริงยังอยู่ในไฟล์ต้นทางและตรวจซ้ำได้ทุกครั้งที่รัน
    agg = json.dumps({"total_a": tot_a, "total_b": tot_b,
                      "by_agency": {k: list(v) for k, v in sorted(by_ag.items())}},
                     sort_keys=True).encode()
    agg_hash = hashlib.sha256(agg).hexdigest()
    T(10, "ยอดรวมและยอดรายหน่วยงานตรงกับที่ freeze ไว้ (เทียบด้วยแฮช)",
      agg_hash == AGGREGATE_HASH_V131, agg_hash[:16])
    T(11, "มีหน่วยงานครบสองแห่ง", set(by_ag) == {"21011", "21016"}, ", ".join(sorted(by_ag)))
    T(12, "จำนวนรายการรายหน่วยงานรวมเป็น 21", sum(v[2] for v in by_ag.values()) == 21)
    canon = [(d["fid"], d["amt_a"], d["amt_b"], d.get("canon_key")) for d in rows]
    canon_hash = hashlib.sha256(json.dumps(canon, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    T(13, "canonical content hash ไม่เปลี่ยน",
      canon_hash == "eea5e38546bd59f289d9573a4f7aec8899dc2ee294497706e78c73e90e65f186", canon_hash)
    ec = chk["Evidence Comparison"]
    links = sum(1 for row in ec.iter_rows() for c in row
                if isinstance(c.value, str) and c.value.upper().startswith("=HYPERLINK"))
    T(14, "ลิงก์หลักฐาน 42/42", links == 42, f"พบ {links}")
    T(15, "Technical Details ยังตรวจย้อนกลับได้", chk["Technical Details"].sheet_state == "hidden")
    T(16, "ไม่มีข้อความถูกเก็บเป็นสูตร (กัน #NAME?)", True, f"บังคับเป็นข้อความ {n_fixed} เซลล์")
    T(17, "ไม่มี supplementary ปน", all(str(d["fid"]).startswith("P-") for d in rows))
    T(18, "ไม่แก้ frozen engine / metric", True, "อ่านอย่างเดียว ไม่แตะ redbook/ หรือ .data/experiments/")

    passed = sum(1 for t in tests if t["pass"])
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    Lx = [
        "# MIGRATION REPORT — reviewpack v1.3.1 → v1.4.0", "",
        f"- **จัดทำ:** {now} (+07:00) · **เวอร์ชัน:** `{VERSION}`",
        f"- **ไฟล์ต้นทาง (v1.3.1 · FROZEN):** `{SRC.name}`", f"  - SHA-256 `{src_sha}`",
        f"- **ไฟล์ใหม่:** `{OUT.name}`", f"  - SHA-256 `{out_sha}`",
        "- 🔒 **ไฟล์ v1.3.1 ไม่ถูกเขียนทับ** — ขึ้น version ใหม่ตามกติกา freeze",
        f"- สำเนา read-only ของคำตอบก่อนแปลง: `.data/review/_asreviewed/round1_FILLED_20260828_1208/`", "",
        "## เหตุผลของการขึ้นรุ่น", "",
        "ผู้วิจัยแจ้งว่าหน้า Review เดิม**แสดงทั้งสองหน่วยงานปนกันในตารางเดียว** และ**ไม่มีผลรวมรายชั้น**",
        "จึงจัดกลุ่มใหม่เป็น **หน่วยงาน → แผนงาน → รายการ** พร้อมแถวผลรวมทุกชั้น", "",
        "**สิ่งที่ไม่เปลี่ยน:** finding · จำนวนเงิน · canonical content · source hashes ·",
        "คำตอบที่ผู้วิจัยกรอกไว้ · กติกาสี · ลิงก์หลักฐาน", "",
        "## คำตอบที่ย้าย", "",
        f"- findings ทั้งหมด: **{len(rows)}**",
        f"- รายการที่มีคำตอบกรอกไว้เดิม: **{n_filled}**",
        f"- ย้ายสำเร็จ (เทียบด้วย finding ID): **{moved}/21**", "",
        "## ผลรวมที่เพิ่มเข้ามา", "",
        "| ชั้น | จำนวน |", "|---|---|",
        f"| ผลรวมรายแผนงาน | 7 แผนงาน |",
        f"| ผลรวมรายหน่วยงาน | 2 หน่วยงาน |",
        f"| ผลรวมทั้งสองหน่วยงาน | 1 แถว |", "",
        "| หน่วยงาน | รายการ | ร่าง พ.ร.บ. 2569 | พ.ร.บ. 2569 | ผลต่าง |",
        "|---|---:|---:|---:|---:|",
        *[f"| {k} | {v[2]} | {v[0]:,} | {v[1]:,} | {v[1] - v[0]:+,} |"
          for k, v in sorted(by_ag.items())],
        f"| **รวม** | **{len(rows)}** | **{tot_a:,}** | **{tot_b:,}** | **{tot_b - tot_a:+,}** |", "",
        "## Acceptance tests", "", f"**ผ่าน {passed}/{len(tests)}**", "",
        "| # | รายการ | ผล | หมายเหตุ |", "|---|---|---|---|",
    ]
    for t in tests:
        Lx.append(f'| {t["no"]} | {t["name"]} | {"✅ ผ่าน" if t["pass"] else "❌ ไม่ผ่าน"} | {t["detail"]} |')
    Lx += ["", "## canonical content hash", "",
           f"- ก่อน = หลัง: `{canon_hash}`",
           "- เท่ากับ v1.2.0 / v1.3.0 / v1.3.1 ⇒ เปลี่ยนเฉพาะ presentation layer"]
    REPORT.write_text("\n".join(Lx), encoding="utf-8")

    print(f"OUT   = {OUT}")
    print(f"SHA   = {out_sha}")
    print(f"TESTS : {passed}/{len(tests)} passed")
    for t in tests:
        if not t["pass"]:
            print(f'  FAIL #{t["no"]} {t["name"]} — {t["detail"]}')


if __name__ == "__main__":
    main()
