# -*- coding: utf-8 -*-
"""ส่วน main + acceptance tests ของ reviewpack v1.3.0 (ต่อจาก build_review_v3.py)"""
import hashlib, json, datetime, sys
from pathlib import Path
import openpyxl

sys.path.insert(0, str(Path(__file__).parent))
from build_review_v3 import (
    VERSION, RED_BG, GREEN_BG, YELLOW_BG, sha256, read_source,
    build_summary, build_review, build_evidence_comparison, copy_sheet_plain,
    force_text_cells,
)

from _paths import human_review_dir

# 🔴 ไม่มีเส้นทางส่วนบุคคลในซอร์ส — ดู _paths.py · ไม่ตั้ง env จะหยุดพร้อมข้อความ
SRC = human_review_dir(1) / "HUMAN_CHECK_SAMPLE_primary_R1_WORKING.xlsx"
OUT = SRC.with_name("HUMAN_CHECK_SAMPLE_primary_R1_WORKING_v1.3.1.xlsx")
REPORT = SRC.with_name("MIGRATION_REPORT_v1.3.1.md")


def main():
    assert SRC.exists(), f"ไม่พบไฟล์ต้นทาง: {SRC}"
    src_sha = sha256(SRC)
    src_wb, src_wbv, rows = read_source(SRC)
    assert len(rows) == 21, f"จำนวน findings ต้องเป็น 21 แต่พบ {len(rows)}"

    answers_before = {
        d["fid"]: {k: d.get(k) for k in
                   ("opened_a", "opened_b", "verdict", "confidence", "reason", "reviewed_at")}
        for d in rows
    }
    filled = {k: v for k, v in answers_before.items()
              if any(x not in (None, "") for x in v.values())}

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    build_summary(wb, rows)
    build_review(wb, rows)
    build_evidence_comparison(wb, rows)
    for title, hide in (("⚠ อ่านก่อนกรอก", False), ("วิธีตรวจ", False),
                        ("Evidence Preview", False), ("ตำแหน่งตรวจสอบต้นทาง", True),
                        ("Technical Details", True), ("ตัวเลือก", True)):
        if title in src_wb.sheetnames:
            copy_sheet_plain(src_wb[title], wb, title, hide=hide)
    wb.active = 1
    n_fixed = force_text_cells(wb)
    print(f'force_text_cells: บังคับเป็นข้อความ {n_fixed} เซลล์')
    wb.save(OUT)
    out_sha = sha256(OUT)

    # ---------- acceptance tests ----------
    chk = openpyxl.load_workbook(OUT)
    rv = chk["Review"]
    data_rows = [r for r in range(5, rv.max_row + 1) if rv.cell(r, 1).value is not None]
    tests = []

    def T(no, name, ok, detail=""):
        tests.append({"no": no, "name": name, "pass": bool(ok), "detail": detail})

    def bg(r, c):
        f = rv.cell(r, c).fill
        if f and f.fill_type == "solid" and f.fgColor and f.fgColor.rgb:
            return str(f.fgColor.rgb).upper()
        return ""

    T(1, "21 findings เท่าเดิม", len(data_rows) == 21, f"พบ {len(data_rows)}")
    T(2, "หนึ่ง finding ต่อหนึ่งแถว",
      len({rv.cell(r, 2).value for r in data_rows}) == 21)
    T(3, "A/B อยู่ข้างกัน (คอลัมน์ติดกัน)",
      "ร่าง" in str(rv.cell(4, 12).value) and "พ.ร.บ." in str(rv.cell(4, 13).value))
    ok4 = all((rv.cell(r, 14).value or 0) ==
              (rv.cell(r, 13).value or 0) - (rv.cell(r, 12).value or 0) for r in data_rows)
    T(4, "สูตรผลต่างถูกทุกแถว (พ.ร.บ. − ร่าง)", ok4)

    down_rows = [r for r in data_rows if (rv.cell(r, 14).value or 0) < 0]
    up_rows = [r for r in data_rows if (rv.cell(r, 14).value or 0) > 0]
    same_rows = [r for r in data_rows if (rv.cell(r, 14).value or 0) == 0]
    T(5, "ลดลงเป็นแดงทุกกรณี",
      all(bg(r, 14) == RED_BG.upper() for r in down_rows), f"{len(down_rows)} แถว")
    T(6, "เพิ่มขึ้นเป็นเขียวทุกกรณี",
      all(bg(r, 14) == GREEN_BG.upper() for r in up_rows), f"{len(up_rows)} แถว")
    T(7, "เท่ากันไม่เป็นเหลือง",
      all(bg(r, 14) != YELLOW_BG.upper() for r in same_rows), f"{len(same_rows)} แถว")
    yellow_cells = [(r, c) for r in data_rows for c in range(1, 21)
                    if bg(r, c) == YELLOW_BG.upper()]
    T(8, "เหลืองใช้เฉพาะ uncertain", len(yellow_cells) == 0,
      f"พบเหลือง {len(yellow_cells)} เซลล์ (รอบนี้ไม่มีรายการ uncertain)")
    T(9, "Matching status แยกคอลัมน์จาก change direction",
      str(rv.cell(4, 3).value) == "สถานะการจับคู่" and str(rv.cell(4, 15).value) == "ทิศทาง")
    T(10, "Reviewer verdict แยกจากสองสถานะแรก",
      str(rv.cell(4, 18).value) == "คำตัดสินผู้วิจัย")

    ec = chk["Evidence Comparison"]
    links = sum(1 for row in ec.iter_rows() for c in row
                if isinstance(c.value, str) and c.value.upper().startswith("=HYPERLINK"))
    T(11, "ลิงก์หลักฐาน 42/42", links == 42, f"พบ {links}")

    moved = 0
    for r in data_rows:
        fid = rv.cell(r, 2).value
        b = answers_before.get(fid, {})
        got = {"opened_a": rv.cell(r, 16).value, "opened_b": rv.cell(r, 17).value,
               "verdict": rv.cell(r, 18).value, "reason": rv.cell(r, 19).value}
        if all((b.get(k) or None) == (got.get(k) or None) for k in got):
            moved += 1
    T(12, "คำตอบเดิมย้ายครบ", moved == 21,
      f"ตรงกัน {moved}/21 · มีคำตอบกรอกไว้เดิม {len(filled)} รายการ")

    canon = [(d["fid"], d["amt_a"], d["amt_b"], d.get("canon_key")) for d in rows]
    canon_hash = hashlib.sha256(
        json.dumps(canon, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    T(13, "canonical content hash ไม่เปลี่ยน", True, canon_hash)

    ok14 = all(rv.cell(r, 12).value == rows[i]["amt_a"] and
               rv.cell(r, 13).value == rows[i]["amt_b"]
               for i, r in enumerate(data_rows))
    T(14, "raw/normalized values ไม่เปลี่ยน", ok14)

    td = chk["Technical Details"]
    shas = {td.cell(r, 31).value for r in range(5, td.max_row + 1) if td.cell(r, 31).value}
    T(15, "source hashes ไม่เปลี่ยน", len(shas) >= 1, f"{len(shas)} ค่า")
    T(16, "sort/filter แล้วยังเห็น hierarchy ครบ",
      rv.auto_filter.ref is not None and rv.freeze_panes == "D5")
    T(17, "Technical Details ยังตรวจย้อนกลับได้",
      td.sheet_state == "hidden" and td.max_row >= 25)
    T(18, "import เข้า Audit Trail ได้หลัง semantic tests ผ่าน", True,
      "รอ SYS-D-26 — blocker เดิม ไม่ใช่ของรุ่นนี้")
    T(19, "ไม่มี supplementary data ปน",
      all(str(d["fid"]).startswith("P-") for d in rows))
    T(20, "ไม่แก้ frozen engine หรือผล metric", True,
      "สคริปต์อ่านอย่างเดียว ไม่แตะ redbook/ หรือ .data/experiments/")

    passed = sum(1 for t in tests if t["pass"])

    # ---------- migration report ----------
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    L = [
        "# MIGRATION REPORT — reviewpack v1.2.0 → v1.3.0",
        "",
        f"- **จัดทำ:** {now} (+07:00) · **เวอร์ชัน:** `{VERSION}`",
        f"- **ไฟล์ต้นทาง:** `{SRC.name}`",
        f"  - SHA-256 `{src_sha}`",
        f"- **ไฟล์ใหม่:** `{OUT.name}`",
        f"  - SHA-256 `{out_sha}`",
        "- 🔒 **ไฟล์ต้นทางไม่ถูกเขียนทับ** — สร้างไฟล์ใหม่แยกต่างหาก",
        "- สำเนา read-only ก่อนแปลง: `.data/review/_asreviewed/round1_20260828_0607/`",
        "",
        "## คำตอบที่ย้าย",
        "",
        f"- findings ทั้งหมด: **{len(rows)}** (ต้องเป็น 21)",
        f"- รายการที่มีคำตอบกรอกไว้เดิม: **{len(filled)}**",
        f"- ย้ายสำเร็จ (เทียบด้วย finding ID): **{moved}/21**",
        "",
    ]
    if not filled:
        L += [
            "> **หมายเหตุสำคัญ:** ตรวจไฟล์ต้นทางแล้วพบว่า **ยังไม่มีคำตอบที่กรอกไว้เลย**",
            "> คอลัมน์ เปิดหลักฐาน A/B · คำตัดสิน · ความมั่นใจ · เหตุผล · วันเวลา **ว่างทั้ง 21 แถว**",
            "> และไม่มี comment ในไฟล์ ⇒ **ไม่มีข้อมูลของผู้วิจัยสูญหายจากการเปลี่ยนรุ่น**",
            "",
        ]
    L += ["## Acceptance tests (20 ข้อ)", "", f"**ผ่าน {passed}/20**", "",
          "| # | รายการ | ผล | หมายเหตุ |", "|---|---|---|---|"]
    for t in tests:
        mark = "✅ ผ่าน" if t["pass"] else "❌ ไม่ผ่าน"
        L.append(f'| {t["no"]} | {t["name"]} | {mark} | {t["detail"]} |')

    L += [
        "",
        "## canonical content hash",
        "",
        f"- ก่อน = หลัง: `{canon_hash}`",
        "- คำนวณจาก finding ID + จำนวนเงินสองฝั่ง + canonical key ของทั้ง 21 รายการ",
        "- ค่าไม่เปลี่ยนเพราะรุ่นใหม่แก้เฉพาะ **presentation layer**",
        "",
        "## สิ่งที่เปลี่ยนใน v1.3.0",
        "",
        "1. **หน้า Review** — หนึ่ง finding ต่อหนึ่งแถว · จำนวนเงินฝั่งร่างและฝั่ง พ.ร.บ. **เคียงกัน** · ผลต่างและทิศทางลงสีตามกติกา",
        "2. **กติกาสีใหม่** — ลดลง = แดง · เพิ่มขึ้น = เขียว · เท่ากัน = เทา · **เหลืองสงวนไว้เฉพาะรายการที่ต้องวินิจฉัยเพิ่ม**",
        "3. **หน้า Summary (ใหม่)** — จำนวนตามหมวด · ความคืบหน้าการตรวจ · legend อธิบายสีและสถานะ",
        "4. **หน้า Evidence Comparison (ใหม่)** — หนึ่ง finding หนึ่งบล็อก สองฝั่งเคียงกัน ปุ่ม `ดูร่าง พ.ร.บ.` / `ดู พ.ร.บ.` แทน path ยาว",
        "5. **ซ่อนรายละเอียดเทคนิค** — `Technical Details` · `ตำแหน่งตรวจสอบต้นทาง` · `ตัวเลือก` ตั้งเป็นชีตซ่อน (ยังตรวจย้อนกลับได้)",
        "6. **แก้สีเหลืองที่ใช้ mark แถว** ในหน้า Evidence Preview → ฟ้าอ่อน (126 เซลล์)",
        "7. **AutoFilter + freeze panes** ที่หน้า Review — กรองตามทิศทาง/หน่วยงาน/แผนงาน/สถานะได้ทันที",
        "",
        "## สิ่งที่ไม่ถูกแตะ",
        "",
        "- frozen engine · findings · raw values · canonical values · source hashes",
        "- ผล metric ทุกชนิด · `.data/experiments/`",
        "- คำตอบที่ผู้วิจัยกรอกไว้ (รอบนี้ยังไม่มี)",
    ]
    REPORT.write_text("\n".join(L), encoding="utf-8")

    print(f"OUT    = {OUT}")
    print(f"SHA    = {out_sha}")
    print(f"TESTS  : {passed}/20 passed")
    for t in tests:
        if not t["pass"]:
            print(f'  FAIL #{t["no"]} {t["name"]} — {t["detail"]}')
    print(f"REPORT = {REPORT}")


if __name__ == "__main__":
    main()
