# -*- coding: utf-8 -*-
"""ตัวเรนเดอร์รายงาน Phase 2A จากผล excel_inventory

รายงานที่ผลิต (ตามชุดส่งมอบ Phase 2B ที่ผู้ใช้กำหนด):
  - FILE_INVENTORY.md            สรุปไฟล์ต่อไฟล์ + SHA-256 ก่อน/หลังอ่าน
  - WORKBOOK_STRUCTURE_REPORT.md โครงสร้างเชิงลึกรายชีต
  - MAPPING_CANDIDATES.md        ทางเลือก mapping พร้อมหลักฐาน — ไม่เลือกให้

คำเตือนสำคัญ: รายงานเหล่านี้มีข้อมูลจริงจากเอกสาร (ตัวอย่างค่า หัวตาราง)
ต้องเก็บเฉพาะในเครื่อง ห้าม commit เข้า git และห้ามวางใน OneDrive
"""

CANDIDATE_MARK = "⬜ รอผู้ใช้ยืนยัน — ระบบไม่เลือกให้"

_WARNING = (
    "> **คำเตือน:** รายงานนี้มีข้อมูลจริงจากเอกสารต้นฉบับ (ตัวอย่างค่า หัวตาราง ชื่อรายการ)\n"
    "> เก็บเฉพาะในเครื่องเท่านั้น **ห้าม commit เข้า git และห้ามวางในโฟลเดอร์ที่ sync ขึ้นคลาวด์**\n"
    "> ทุกค่าที่ระบบตรวจพบมีสถานะเป็น *candidate* ต้องให้ผู้ใช้ยืนยันก่อนใช้ตรวจจริง\n")


def _fmt_loc_list(items, limit=6):
    if not items:
        return "— ไม่พบ"
    lines = [f"  - `{it['sheet']}!{it['ref']}` — {it['text']}" for it in items[:limit]]
    if len(items) > limit:
        lines.append(f"  - … อีก {len(items) - limit} จุด (ดู inventory.json)")
    return "\n".join(lines)


def render_file_inventory(entries, run_meta) -> str:
    """entries: list ของ dict ต่อไฟล์ {file:{...}, inventory:(dict|None), note}"""
    L = ["# FILE_INVENTORY — บัญชีไฟล์ที่สำรวจ (Phase 2A)", "", _WARNING]
    L.append(f"- ตรวจเมื่อ: {run_meta['checked_at']}")
    L.append(f"- เครื่องมือ: {run_meta['tool']} · parser: {run_meta['parser']}")
    L.append(f"- ขอบเขตสแกน: {run_meta['scan_limits']}")
    L.append("")
    for i, e in enumerate(entries, 1):
        f = e["file"]
        L.append(f"## ไฟล์ที่ {i}: {f['name']}")
        L.append("")
        L.append(f"- ขนาด: {f['size_bytes']:,} ไบต์")
        L.append(f"- ชนิดไฟล์จริง (จากเนื้อไฟล์): **{f['kind']}**")
        L.append(f"- SHA-256 ก่อนอ่าน: `{f['sha256_before']}`")
        L.append(f"- SHA-256 หลังอ่าน: `{f['sha256_after']}`")
        same = f["sha256_before"] == f["sha256_after"]
        L.append(f"- ไฟล์ต้นฉบับไม่ถูกแก้ไข: {'✔ ยืนยัน (แฮชตรงกัน)' if same else '❌ แฮชไม่ตรง — ต้องสอบสวน'}")
        inv = e.get("inventory")
        if inv is None:
            L.append(f"- หมายเหตุ: {e.get('note', '')}")
            L.append("")
            continue
        L.append(f"- จำนวนชีต: {len(inv['sheet_names'])} — {', '.join(inv['sheet_names'])}")
        if inv["hidden_sheets"]:
            L.append(f"- ชีตที่ซ่อน: {', '.join(inv['hidden_sheets'])}")
        L.append("")
        L.append("**ปีงบประมาณที่อ่านพบ (candidate — ต้องยืนยัน):**")
        if inv["year_candidates"]:
            for y in inv["year_candidates"][:5]:
                ex = y["examples"][0] if y["examples"] else None
                where = f" · เช่น `{ex['sheet']}!{ex['ref']}` — {ex['text']}" if ex else ""
                L.append(f"  - พ.ศ. {y['year']} (น้ำหนักหลักฐาน {y['weight']}){where}")
        else:
            L.append("  - ไม่พบตัวเลขปีในเขตหัวเอกสาร")
        L.append("")
        L.append("**ชื่อหน่วยงานที่อ่านพบ (candidate — ต้องยืนยัน):**")
        L.append(_fmt_loc_list(inv["agency_candidates"]))
        L.append("")
        L.append("**หน่วยเงินที่พบในเอกสาร (candidate — ต้องยืนยัน):**")
        L.append(_fmt_loc_list(inv["unit_hints"]))
        L.append("")
        unc = [(s["name"], s["uncertainties"]) for s in inv["sheets"]]
        worst = [f"{n}: สูตรไม่มีค่า cache {u['cached_value_missing']}, "
                 f"ค่า error {u['error_values']}"
                 for n, u in unc if u["cached_value_missing"] or u["error_values"]]
        L.append("**จุดที่ parser อ่านไม่ได้/ไม่แน่ใจ:** " +
                 ("; ".join(worst) if worst else "ไม่พบ"))
        L.append("")
    return "\n".join(L)


def _render_sheet(sh) -> list:
    L = [f"### ชีต: {sh['name']}", ""]
    L.append(f"- สถานะ: {sh['state']} · ช่วงประกาศ: `{sh['declared_dimension']}` · "
             f"ข้อมูลจริงถึงแถว {sh['observed_last_row']:,} คอลัมน์ {sh['observed_last_col']}")
    L.append(f"- ผสานเซลล์: {sh['merged_count']} ช่วง"
             + (f" (แสดง 50 แรกใน inventory.json)" if sh["merged_count"] > 50 else ""))
    if sh["hidden_rows"] or sh["hidden_cols"]:
        L.append(f"- แถวซ่อน: {len(sh['hidden_rows'])} · คอลัมน์ซ่อน: {len(sh['hidden_cols'])}")
    if sh["print_area"]:
        L.append(f"- พื้นที่พิมพ์: `{sh['print_area']}`")

    hb = sh["header_band"]
    if hb["best_rows"]:
        L.append(f"- **แถบหัวตาราง (candidate):** แถว {hb['best_rows']} "
                 f"(จาก candidate ทั้งหมด {len(hb['candidate_rows'])} แถว) — {CANDIDATE_MARK}")
    else:
        L.append(f"- **แถบหัวตาราง:** {hb['note']}")
    dr = sh["data_range"]
    if dr:
        L.append(f"- **ช่วงข้อมูล (candidate):** แถว {dr['first_data_row']} – "
                 f"{dr['last_data_row']} ({dr['basis']}) — {CANDIDATE_MARK}")
    if sh["total_row_candidates"]:
        rows = ", ".join(f"แถว {t['row']} (`{t['ref']}` {t['text']})"
                         for t in sh["total_row_candidates"][:5])
        L.append(f"- แถวผลรวม (candidate): {rows}")
    if sh["bold_heading_rows"]:
        L.append(f"- แถวหัวข้อตัวหนาไม่มีตัวเลข (ร่องรอยลำดับชั้น): "
                 f"{sh['bold_heading_rows'][:15]}")
    if sh["thai_digit_cells"]:
        L.append(f"- เซลล์ที่มีเลขไทย: {sh['thai_digit_cells']} เซลล์ "
                 f"เช่น {', '.join(sh['thai_digit_examples'])}")

    fm = sh["formulas"]
    if fm["count"]:
        refs = ", ".join(f"{k} ({v})" for k, v in
                         sorted(fm["refs_to_sheets"].items(), key=lambda kv: -kv[1])[:6])
        L.append(f"- สูตร: {fm['count']:,} เซลล์ · อ้างถึงชีต: {refs or '—'}")
        for s in fm["samples"][:3]:
            L.append(f"  - ตัวอย่าง `{s}`")
        if fm["external"]:
            L.append(f"  - ⚠ พบการอ้างอิงไฟล์ภายนอก: {fm['external'][:3]}")

    if sh["columns"]:
        L.append("")
        L.append("| คอลัมน์ | หัวตาราง (จากแถบ candidate) | ตัวเลข | สูตร | ข้อความ "
                 "| เลขเก็บเป็นข้อความ | รูปแบบตัวเลขเด่น | ดูเหมือนรหัส | ค่าไม่ซ้ำ | เยื้อง | ตัวอย่าง |")
        L.append("|---|---|---:|---:|---:|---:|---|---|---|---|---|")
        for c in sh["columns"]:
            code = (f"ใช่ ({c['code_pattern']})" if c["code_like"] else "—")
            indent = (str(c["indent_levels"]) if c["indent_levels"] else "—")
            samples = "; ".join(str(s) for s in c["samples"][:3]) or "—"
            fmt = c["dominant_number_format"] or "—"
            L.append(f"| {c['letter']} | {c['header_text'] or '—'} | {c['n_numeric']:,} "
                     f"| {c['n_formula']:,} | {c['n_text']:,} | {c['n_number_as_text']:,} "
                     f"| `{fmt}` | {code} | {c['distinct_text_values']} | {indent} | {samples} |")

    unc = sh["uncertainties"]
    notes = []
    if unc["cached_value_missing"]:
        notes.append(f"สูตรที่ไม่มีค่าคำนวณไว้ {unc['cached_value_missing']:,} เซลล์ "
                     "(ระบบไม่คำนวณแทน)")
    if unc["error_values"]:
        notes.append(f"ค่า error ของ Excel {unc['error_values']:,} เซลล์")
    if unc["scan_capped_at"]:
        notes.append(f"สแกนถึงแถว {unc['scan_capped_at']:,} จากทั้งหมด {sh['max_row']:,} "
                     "(ปรับได้ด้วย --max-rows)")
    if unc["cols_capped_at"]:
        notes.append(f"สแกนถึงคอลัมน์ที่ {unc['cols_capped_at']} จาก {sh['max_col']}")
    if notes:
        L.append("")
        L.append("**ความไม่แน่นอน:** " + " · ".join(notes))
    L.append("")
    return L


def render_workbook_structure(entries, run_meta) -> str:
    L = ["# WORKBOOK_STRUCTURE_REPORT — โครงสร้างสมุดงานเชิงลึก (Phase 2A)", "", _WARNING]
    L.append(f"- ตรวจเมื่อ: {run_meta['checked_at']} · {run_meta['tool']}")
    L.append("")
    for e in entries:
        if not e.get("inventory"):
            continue
        L.append(f"## {e['file']['name']}")
        L.append("")
        inv = e["inventory"]
        if inv["defined_names"]:
            L.append(f"- defined names: {', '.join(inv['defined_names'][:15])}")
        if inv["external_refs"]:
            L.append(f"- ⚠ อ้างอิงไฟล์ภายนอก: {inv['external_refs']}")
        L.append("")
        for sh in inv["sheets"]:
            L.extend(_render_sheet(sh))
    return "\n".join(L)


def _sheet_role_evidence(inv) -> list:
    """สรุปหลักฐานบทบาทชีตจากทิศทางการอ้างสูตร — เสนอ ไม่ตัดสิน"""
    referenced_by = {}
    for sh in inv["sheets"]:
        for target, n in sh["formulas"]["refs_to_sheets"].items():
            referenced_by.setdefault(target, []).append((sh["name"], n))
    out = []
    for sh in inv["sheets"]:
        refs_out = sh["formulas"]["refs_to_sheets"]
        refs_in = referenced_by.get(sh["name"], [])
        hints = []
        if refs_out:
            hints.append("มีสูตรอ้างชีตอื่น → มีลักษณะชีตสรุป/รวมยอด")
        if refs_in:
            src = ", ".join(f"{n} ({c} สูตร)" for n, c in refs_in[:4])
            hints.append(f"ถูกอ้างโดย: {src} → มีลักษณะชีตข้อมูลต้นทาง")
        if not sh["columns"]:
            hints.append("ไม่พบตารางข้อมูล → อาจเป็นชีตประกอบ/หน้าปก")
        out.append({"name": sh["name"], "hints": hints,
                    "header_found": bool(sh["header_band"]["best_rows"]),
                    "n_data_rows": (sh["observed_last_row"] or 0)})
    return out


def render_mapping_candidates(entries, comparison, run_meta) -> str:
    L = ["# MAPPING_CANDIDATES — ทางเลือก mapping พร้อมหลักฐาน (ยังไม่มีผลใช้บังคับ)",
         "", _WARNING,
         "เอกสารนี้ **เสนอทางเลือกจากหลักฐานที่อ่านได้จริงเท่านั้น** "
         "การยืนยันทำใน MAPPING_DECISION_FORM · เมื่อพบมากกว่าหนึ่งความเป็นไปได้ "
         "ระบบแสดงทุกความเป็นไปได้และไม่เลือกให้", ""]
    L.append(f"- ตรวจเมื่อ: {run_meta['checked_at']} · {run_meta['tool']}")
    L.append("")

    xls = [e for e in entries if e.get("inventory")]

    L.append("## 1. บทบาทของชีต (sheet-role proposal · Q2)")
    L.append("")
    for e in xls:
        L.append(f"### {e['file']['name']}")
        L.append("")
        L.append("| ชีต | หลักฐานที่พบ | พบหัวตาราง | แถวข้อมูลที่พบ | บทบาทที่เสนอ |")
        L.append("|---|---|---|---:|---|")
        for row in _sheet_role_evidence(e["inventory"]):
            hints = "<br>".join(row["hints"]) or "—"
            L.append(f"| {row['name']} | {hints} | {'มี' if row['header_found'] else 'ไม่พบ'} "
                     f"| {row['n_data_rows']:,} | {CANDIDATE_MARK} |")
        L.append("")

    L.append("## 2. แถวหัวตารางและช่วงข้อมูล (Q2)")
    L.append("")
    for e in xls:
        for sh in e["inventory"]["sheets"]:
            hb, dr = sh["header_band"], sh["data_range"]
            if not (hb["best_rows"] or dr):
                continue
            L.append(f"- `{e['file']['name']}` · ชีต **{sh['name']}** — "
                     f"แถบหัวตาราง: {hb['best_rows'] or 'ไม่พบ'} · "
                     f"ข้อมูล: {dr['first_data_row'] if dr else '?'}–"
                     f"{dr['last_data_row'] if dr else '?'} · "
                     f"แถวผลรวม: {[t['row'] for t in sh['total_row_candidates'][:5]] or '—'} "
                     f"— {CANDIDATE_MARK}")
    L.append("")

    L.append("## 3. คอลัมน์จำนวนเงินและหน่วย (Q3)")
    L.append("")
    L.append("คอลัมน์ที่ตัวเลขเด่น (จำนวนเซลล์ตัวเลข+สูตร ≥ 5) พร้อมรูปแบบตัวเลข — "
             "**ระบบยังไม่ normalize จนกว่าจะยืนยัน stored/declared unit/scale:**")
    L.append("")
    for e in xls:
        inv = e["inventory"]
        for sh in inv["sheets"]:
            money_cols = [c for c in sh["columns"]
                          if (c["n_numeric"] + c["n_formula"]) >= 5]
            if not money_cols:
                continue
            cols_txt = ", ".join(
                f"{c['letter']} ({c['header_text'] or 'ไม่มีหัว'} · `{c['dominant_number_format'] or '?'}`)"
                for c in money_cols[:10])
            L.append(f"- `{e['file']['name']}` · **{sh['name']}**: {cols_txt}")
        if inv["unit_hints"]:
            L.append(f"  - หน่วยที่ประกาศในเอกสาร: " +
                     "; ".join(f"`{u['sheet']}!{u['ref']}` — {u['text']}"
                               for u in inv["unit_hints"][:4]))
        L.append(f"  - {CANDIDATE_MARK}")
    L.append("")

    L.append("## 4. คีย์จับคู่รายการข้ามไฟล์ (Q1)")
    L.append("")
    L.append("คอลัมน์ที่ค่ามีลักษณะเป็นรหัส พร้อมสถิติความไม่ซ้ำ — "
             "ห้ามใช้เลขแถวเป็นตัวระบุข้ามปี:")
    L.append("")
    for e in xls:
        for sh in e["inventory"]["sheets"]:
            code_cols = [c for c in sh["columns"] if c["code_like"]]
            for c in code_cols:
                L.append(f"- `{e['file']['name']}` · **{sh['name']}** คอลัมน์ {c['letter']} "
                         f"({c['header_text'] or 'ไม่มีหัว'}) — pattern: {c['code_pattern']} · "
                         f"ค่าไม่ซ้ำ {c['distinct_text_values']} จากข้อความ {c['n_text']:,} เซลล์")
    if comparison:
        L.append("")
        L.append("**ความคาบเกี่ยวของค่ารหัสระหว่างไฟล์ (หลักฐานสำหรับเลือกคีย์):**")
        for cs in comparison.get("common_sheets", []):
            for ov in cs.get("code_column_overlap", []):
                L.append(f"- ชีต **{cs['name']}** คอลัมน์ {ov['letter']}: "
                         f"ค่าไม่ซ้ำ A={ov['distinct_a']} · B={ov['distinct_b']} · "
                         f"พบร่วมกัน {ov['shared']} ({ov['containment_pct']}%)")
    L.append(f"- {CANDIDATE_MARK}")
    L.append("")

    L.append("## 5. ร่องรอยลำดับชั้นโครงสร้าง (Q4)")
    L.append("")
    found_any = False
    for e in xls:
        for sh in e["inventory"]["sheets"]:
            traces = []
            for c in sh["columns"]:
                if c["indent_levels"]:
                    traces.append(f"คอลัมน์ {c['letter']} มีการเยื้องหลายระดับ "
                                  f"{c['indent_levels']}")
                if c["code_like"] and c["code_pattern"] == "ตัวเลขคั่นจุด":
                    traces.append(f"คอลัมน์ {c['letter']} รหัสแบบจุดคั่น "
                                  "(อาจสื่อชั้นแม่ลูก)")
            if sh["bold_heading_rows"]:
                traces.append(f"แถวหัวข้อตัวหนา {len(sh['bold_heading_rows'])} แถว")
            if traces:
                found_any = True
                L.append(f"- `{e['file']['name']}` · **{sh['name']}**: " + " · ".join(traces))
    if not found_any:
        L.append("- ไม่พบร่องรอยลำดับชั้นอัตโนมัติ — ต้องให้ผู้ใช้ชี้")
    L.append(f"- {CANDIDATE_MARK}")
    L.append("")

    if comparison:
        L.append("## 6. ความแตกต่างโครงสร้างระหว่างไฟล์ (สำหรับสองไฟล์แรกที่เทียบ)")
        L.append("")
        L.append(f"- ชีตที่มีเฉพาะไฟล์ A: {comparison['sheets_only_a'] or '— ไม่มี'}")
        L.append(f"- ชีตที่มีเฉพาะไฟล์ B: {comparison['sheets_only_b'] or '— ไม่มี'}")
        L.append(f"- ลำดับชีตตรงกัน: {'ใช่' if comparison['sheet_order_same'] else 'ไม่'}")
        for cs in comparison["common_sheets"]:
            if cs["header_diffs"]:
                L.append(f"- ชีต **{cs['name']}** หัวตารางต่างกัน {len(cs['header_diffs'])} คอลัมน์:")
                for d in cs["header_diffs"][:10]:
                    L.append(f"  - คอลัมน์ {d['letter']}: A=`{d['a'] or '—'}` | B=`{d['b'] or '—'}`")
        L.append("")

    L.append("## 7. จุดที่ระบบไม่แน่ใจ / อ่านไม่ได้ (ยกไป UNRESOLVED_QUESTIONS)")
    L.append("")
    for e in xls:
        for sh in e["inventory"]["sheets"]:
            unc = sh["uncertainties"]
            items = []
            if not sh["header_band"]["best_rows"]:
                items.append("ไม่พบแถวหัวตาราง")
            if unc["cached_value_missing"]:
                items.append(f"สูตรไม่มีค่า cache {unc['cached_value_missing']:,} เซลล์")
            if unc["error_values"]:
                items.append(f"ค่า error {unc['error_values']:,} เซลล์")
            if unc["scan_capped_at"]:
                items.append(f"สแกนไม่ครบ (ถึงแถว {unc['scan_capped_at']:,})")
            if items:
                L.append(f"- `{e['file']['name']}` · **{sh['name']}**: " + " · ".join(items))
    L.append("")
    return "\n".join(L)
