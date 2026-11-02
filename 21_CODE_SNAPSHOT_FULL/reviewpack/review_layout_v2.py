# -*- coding: utf-8 -*-
"""reviewpack v2 — โครงหน้าแบบอ่านตามลำดับเอกสารงบประมาณ (`review-schema-1.2.0`)

**ชั้น presentation / review เท่านั้น** ตามคำสั่งผู้รับผิดชอบ 28 ส.ค. 2569:
อ่านผลการรันที่ freeze แล้วมาจัดหน้าใหม่ให้คนตรวจงบอ่านง่าย —
ไม่แก้ engine · ไม่แก้ rule set · ไม่แก้ผลการจำแนก (finding classification) ·
ไม่แก้ raw/normalized value · ไม่แตะ `result_hash` หรือ SHA-256 ของไฟล์ต้นทาง

สามแกนที่ต้องไม่ปนกัน (ใช้ภาษาภาพคนละชุด):
  1. สถานะการจับคู่     — สัญลักษณ์ + สีตัวอักษร บนพื้นขาวมีกรอบ
  2. ทิศทางของจำนวนเงิน — สีพื้นหลังของเซลล์จำนวนเงิน
  3. คำตัดสินของผู้วิจัย — conditional formatting โทนน้ำเงิน/ม่วง
"""
import hashlib
from pathlib import Path

import openpyxl
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

REVIEW_SCHEMA_VERSION = "review-schema-1.2.0"
# รุ่นของแบบฟอร์มสาย v2 — แยกจาก REVIEWPACK_VERSION ของสาย v1 โดยตั้งใจ
# เพื่อไม่ให้การแก้ชั้น presentation ไปเปลี่ยนป้ายเวอร์ชันของเครื่องมือเดิม
REVIEWPACK_VERSION_V2 = "reviewpack-1.2.0"

# ---------------------------------------------------------------- บทบาทของคีย์
# คีย์ผสม 9 บทบาทตาม D7 · ลำดับตรงกับ finding["key"] ของผลการรันที่ freeze แล้ว
KEY_ROLES = (
    ("agency_code", "หน่วยงาน"),
    ("budget_group", "ประเภทงบประมาณ"),
    ("plan_name", "แผนงาน"),
    ("output_name", "ผลผลิต/โครงการ"),
    ("activity_name", "กิจกรรม"),
    ("objective_category", "หมวดรายจ่าย"),
    ("objective_subcategory", "ประเภทรายจ่าย"),
    ("capital_class", "ลักษณะรายจ่าย"),
    ("item_label", "ชื่อรายการ"),
)

NO_DATA = "—"          # ระดับที่ไม่มีข้อมูลจริง — ไม่เดา ไม่เลื่อนค่าจากระดับอื่นมาใส่

# ---------------------------------------------------------------- แกนที่ 1
MATCH_OK = ("✓ จับคู่ได้", "1E7A34")
MATCH_NO = ("✕ จับคู่ไม่ได้", "B3261E")
MATCH_PENDING = ("? รอตรวจสอบการจับคู่", "8A6100")
MATCH_SCHEMA = ("⚠ Schema ต่างกัน", "C05621")

MATCHING_NOTE = ("สถานะการจับคู่บอกว่าระบบเชื่อมรายการสองฝั่งได้หรือไม่ "
                 "ไม่ได้ตัดสินว่ารายการหรือเอกสารผิด")

# ---------------------------------------------------------------- แกนที่ 2
DIR_DOWN = ("▼ วงเงินลดลง", "FDE7E9", "9C1C13")
DIR_UP = ("▲ วงเงินเพิ่มขึ้น", "E4F4E7", "14632B")
# ใช้ ＝ (fullwidth equals) เพราะสตริงที่ขึ้นต้นด้วย = จะถูก Excel
# ตีความเป็นสูตรแล้วขึ้น #NAME? — ความหมายเดิมคือ "เท่ากัน"
DIR_SAME = ("＝ ไม่เปลี่ยนแปลง", "F0F1F3", "44474C")
DIR_UNKNOWN = ("? ต้องตรวจหลักฐานเพิ่ม", "FFF3CD", "7A5B00")

LEGEND_MONEY = [
    (DIR_DOWN[0], DIR_DOWN[1], DIR_DOWN[2],
     "จำนวนเงินฝั่ง พ.ร.บ. ต่ำกว่าฝั่งร่าง — ไม่ได้หมายความว่าเอกสารผิด"),
    (DIR_UP[0], DIR_UP[1], DIR_UP[2],
     "จำนวนเงินฝั่ง พ.ร.บ. สูงกว่าฝั่งร่าง — ไม่ได้หมายความว่าถูกต้องหรือดีกว่า"),
    (DIR_SAME[0], DIR_SAME[1], DIR_SAME[2], "จำนวนเงินสองฝั่งเท่ากัน"),
    (DIR_UNKNOWN[0], DIR_UNKNOWN[1], DIR_UNKNOWN[2],
     "คำนวณไม่ได้หรือข้อมูลไม่ครบ — ต้องตรวจหลักฐานเพิ่ม"),
]

LEGEND_MATCH = [
    (MATCH_OK[0], MATCH_OK[1], "ระบบเชื่อมรายการสองฝั่งเข้าคู่กันได้"),
    (MATCH_NO[0], MATCH_NO[1], "รายการปรากฏเพียงฝั่งเดียว จับคู่ไม่ได้"),
    (MATCH_PENDING[0], MATCH_PENDING[1], "การจับคู่ยังต้องให้คนตรวจสอบ"),
    (MATCH_SCHEMA[0], MATCH_SCHEMA[1], "ความหมายของฟิลด์สองฝั่งไม่ตรงกัน ระบบหยุดก่อนเทียบเนื้อหา"),
]

# ---------------------------------------------------------------- แกนที่ 3
VERDICT_CHOICES = ["ยืนยัน", "ไม่ยืนยัน", "ไม่แน่ใจ"]
CONFIDENCE_CHOICES = ["สูง", "ปานกลาง", "ต่ำ"]
EVIDENCE_OPENED_CHOICES = ["เปิดแล้ว", "ยังไม่ได้เปิด"]
# โทนน้ำเงิน/ม่วง — แยกจากแดง/เขียว/เทา/เหลืองของจำนวนเงิน และจากสัญลักษณ์การจับคู่
VERDICT_STYLE = {
    "ยืนยัน": ("D8E6F7", "1B3A6B", True, False),
    "ไม่ยืนยัน": ("B7C9E4", "102A52", True, False),
    "ไม่แน่ใจ": ("E9E7F4", "3D3A63", False, True),
}

SIDE_A_TITLE = "ร่าง พ.ร.บ. งบประมาณรายจ่าย พ.ศ. 2569"
SIDE_B_TITLE = "พ.ร.บ. งบประมาณรายจ่าย พ.ศ. 2569"
SIDE_A_SHORT = "ร่าง พ.ร.บ. 2569"
SIDE_B_SHORT = "พ.ร.บ. 2569"
SIDE_A_DOCSTATE = "ปีงบประมาณ 2569 · ร่างพระราชบัญญัติ"
SIDE_B_DOCSTATE = "ปีงบประมาณ 2569 · พระราชบัญญัติ (ประกาศใช้)"
HEAD_A_FILL = "E8EEF6"      # เฉดหัวคอลัมน์ฝั่ง A — ไม่ชนกับแดง/เขียวของทิศทางเงิน
HEAD_B_FILL = "EFEAF4"      # เฉดหัวคอลัมน์ฝั่ง B

SCOPE_BANNER = ("PRIMARY CASE REVIEW — สวรส. และสถาบันวัคซีนแห่งชาติ · "
                "คู่ร่าง พ.ร.บ. 2569 ↔ พ.ร.บ. 2569")

# ---------------------------------------------------------------- คอลัมน์หน้า Review
# (key, หัวคอลัมน์, ความกว้าง, wrap)
REVIEW_COLUMNS = [
    ("order_no", "ลำดับ", 6, False),
    ("sample_id", "รหัสรายการตรวจ", 13, False),
    ("matching_status", "สถานะการจับคู่", 20, True),
    ("agency_display", "หน่วยงาน", 26, True),
    ("budget_group", "ประเภทงบประมาณ", 20, True),
    ("plan_name", "แผนงาน", 26, True),
    ("output_name", "ผลผลิต/โครงการ", 28, True),
    ("activity_name", "กิจกรรม", 28, True),
    ("objective_category", "หมวดรายจ่าย", 16, True),
    ("objective_subcategory", "ประเภทรายจ่าย", 20, True),
    ("capital_class", "ลักษณะรายจ่าย", 14, True),
    ("item_label", "ชื่อรายการ", 24, True),
    ("count_unit", "หน่วยนับ", 10, False),
    ("amount_a", "วงเงินฝั่ง " + SIDE_A_TITLE + " (บาท)", 22, True),
    ("amount_b", "วงเงินฝั่ง " + SIDE_B_TITLE + " (บาท)", 22, True),
    ("amount_diff", "ผลต่าง (บาท)", 16, False),
    ("direction", "ทิศทางการเปลี่ยนแปลง", 20, True),
    ("value_consistency", "ค่าดิบตรงกับค่าที่ระบบใช้", 18, True),
    ("evidence_a_text", "ตำแหน่งหลักฐาน — " + SIDE_A_SHORT, 46, True),
    ("evidence_b_text", "ตำแหน่งหลักฐาน — " + SIDE_B_SHORT, 46, True),
    ("evidence_opened_a", "เปิดหลักฐาน " + SIDE_A_SHORT + " แล้ว", 15, True),
    ("evidence_opened_b", "เปิดหลักฐาน " + SIDE_B_SHORT + " แล้ว", 15, True),
    ("reviewer_verdict", "คำตัดสินของผู้วิจัย", 16, True),
    ("reviewer_confidence", "ความมั่นใจผู้วิจัย", 14, True),
    ("reviewer_reason", "เหตุผล/หมายเหตุ", 40, True),
    ("reviewed_at", "วันเวลาที่ตรวจ", 18, True),
]

# คอลัมน์ลำดับชั้นที่ยุบ/ขยายได้ (outline) — ยุบแล้วยังเห็น หน่วยงาน + ชื่อรายการ
HIERARCHY_GROUP = ("budget_group", "plan_name", "output_name", "activity_name",
                   "objective_category", "objective_subcategory", "capital_class")
# คอลัมน์ที่ใช้ตีเส้นแบ่งกลุ่มเมื่อค่าเปลี่ยน (ค่ายังอยู่ครบทุกแถว ไม่ merge)
GROUP_BREAK_FIELDS = ("agency_code", "plan_name", "output_name", "activity_name")

REVIEWER_FIELDS = ("evidence_opened_a", "evidence_opened_b", "reviewer_verdict",
                   "reviewer_confidence", "reviewer_reason", "reviewed_at")

# หัวคอลัมน์ของช่องผู้วิจัยในรุ่นนี้ — ใช้เป็นปลายทางตอนย้ายคำตอบข้ามรุ่น
V2_REVIEWER_HEADERS = {
    "เปิดหลักฐาน " + SIDE_A_SHORT + " แล้ว": "evidence_opened_a",
    "เปิดหลักฐาน " + SIDE_B_SHORT + " แล้ว": "evidence_opened_b",
    "คำตัดสินของผู้วิจัย": "reviewer_verdict",
    "ความมั่นใจผู้วิจัย": "reviewer_confidence",
    "เหตุผล/หมายเหตุ": "reviewer_reason",
    "วันเวลาที่ตรวจ": "reviewed_at",
}

HEADER_ROW = 4
THIN = Side(style="thin", color="B7BDC6")
GROUP_TOP = Side(style="medium", color="8A93A0")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for b in iter(lambda: fp.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ============================================================ อ่านไฟล์ต้นทาง
class SourceReader:
    """อ่านค่าดิบและบริบทรอบข้างจากไฟล์ต้นทาง — อ่านอย่างเดียว + ตรวจ SHA ก่อน/หลัง"""

    SRC_COLS = ["min", "min_name", "agc", "agc_name", "group_budget", "plan_name",
                "output_name", "act_name", "objc", "objc_8", "cap_ncap",
                "item_name", "p_total_bud"]

    def __init__(self, sources_dir):
        self.dir = Path(sources_dir)
        self._cache = {}
        self._paths = {}
        self.sha_before = {}
        self.sha_after = {}

    def path_of(self, file_name):
        """คืน path แบบสัมบูรณ์เสมอ

        ต้องเป็น absolute เพราะ Excel ตีความ path สัมพัทธ์ใน HYPERLINK เทียบกับ
        ที่ตั้งของ workbook เอง ไม่ใช่ที่ตั้งของโครงการ — path สัมพัทธ์จึงทำให้
        ลิงก์หลักฐานเสียทันทีที่ไฟล์แบบฟอร์มอยู่คนละโฟลเดอร์กับโครงการ
        """
        if file_name not in self._paths:
            matches = [p for p in self.dir.rglob(file_name) if p.is_file()]
            self._paths[file_name] = matches[0].resolve() if matches else None
        return self._paths[file_name]

    def _open(self, file_name):
        if file_name not in self._cache:
            path = self.path_of(file_name)
            if path is None:
                self._cache[file_name] = None
            else:
                self.sha_before[file_name] = sha256_file(path)
                fh = open(path, "rb")
                wb = openpyxl.load_workbook(fh, read_only=True, data_only=True)
                self._cache[file_name] = (wb, fh, path)
        return self._cache[file_name]

    def rows(self, file_name, row_numbers):
        """คืน {row_number: [ค่า 13 คอลัมน์]} — วนไฟล์รอบเดียวต่อการเรียกหนึ่งครั้ง"""
        entry = self._open(file_name)
        wanted = {int(r) for r in row_numbers if r}
        if entry is None or not wanted:
            return {}
        wb = entry[0]
        ws = wb["data"]
        out = {}
        for i, row in enumerate(ws.iter_rows(min_row=1, max_row=max(wanted),
                                             max_col=13, values_only=True), start=1):
            if i in wanted:
                out[i] = list(row)
        return out

    def close_and_verify(self):
        """ปิดไฟล์แล้วตรวจว่า SHA-256 ไม่เปลี่ยน — พิสูจน์ว่าอ่านอย่างเดียวจริง"""
        for name, entry in self._cache.items():
            if entry:
                wb, fh, path = entry
                wb.close()
                fh.close()
                self.sha_after[name] = sha256_file(path)
        return all(v == self.sha_after.get(k) for k, v in self.sha_before.items())


# ============================================================ ตรรกะสามแกน
def matching_status(finding):
    """แกนที่ 1 — ระบบเชื่อมรายการสองฝั่งได้หรือไม่ (ไม่ตัดสินถูก/ผิดของเอกสาร)"""
    cat = finding.get("category", "")
    if cat == "SC1":
        return MATCH_SCHEMA
    if cat in ("C4", "C5"):
        return MATCH_NO
    if cat in ("C6", "C7") or finding.get("machine_status") == "needs_human":
        return MATCH_PENDING
    return MATCH_OK


def change_direction(amount_a, amount_b):
    """แกนที่ 2 — ทิศทางของจำนวนเงินเท่านั้น ไม่ตัดสินความถูกต้อง"""
    if amount_a is None or amount_b is None:
        return DIR_UNKNOWN
    if amount_b < amount_a:
        return DIR_DOWN
    if amount_b > amount_a:
        return DIR_UP
    return DIR_SAME


def value_consistency(raw, used):
    """คืน (ตรงกันหรือไม่, ข้อความอธิบายการแปลงค่า) — ไม่แก้ค่าใด ๆ"""
    if raw is None and used is None:
        return True, ""
    if raw is None or used is None:
        return False, "มีค่าเพียงฝั่งเดียว — ต้องเปิดหลักฐานยืนยัน"
    if isinstance(raw, str):
        cleaned = raw.replace(",", "").strip()
        try:
            if float(cleaned) == float(used):
                return False, ("เซลล์จัดเก็บจำนวนเงินเป็นข้อความที่มีจุลภาค "
                               "(text-equivalent) ระบบตัดจุลภาคแล้วเทียบเป็นตัวเลข "
                               "ค่าตัวเลขเท่ากัน")
        except ValueError:
            pass
        return False, "ค่าในเซลล์เป็นข้อความที่แปลงเป็นตัวเลขไม่ได้ — ต้องตรวจหลักฐาน"
    same = float(raw) == float(used)
    return same, ("" if same else
                  "ค่าดิบในเซลล์ไม่เท่ากับค่าที่ระบบนำไปเปรียบเทียบ — ต้องตรวจหลักฐาน")


# ============================================================ สร้างเรคอร์ด
def build_records(run, reader, run_label="CSET_fy2569"):
    findings = run.get("findings", [])
    files = run.get("files", {})
    name_a = files.get("a", {}).get("name", "")
    name_b = files.get("b", {}).get("name", "")

    def ctx_rows(findings_side, key):
        wanted = set()
        for f in findings:
            rn = (f.get(key) or {}).get("row_number")
            if rn:
                wanted.update({rn - 1, rn, rn + 1})
        return wanted

    rows_a = reader.rows(name_a, ctx_rows(findings, "evidence_a"))
    rows_b = reader.rows(name_b, ctx_rows(findings, "evidence_b"))

    records = []
    for i, f in enumerate(findings):
        key = list(f.get("key") or [])
        key += [None] * (len(KEY_ROLES) - len(key))
        roles = {role: (key[j] if key[j] not in (None, "") else NO_DATA)
                 for j, (role, _) in enumerate(KEY_ROLES)}

        ev_a = f.get("evidence_a") or {}
        ev_b = f.get("evidence_b") or {}
        src_a = rows_a.get(ev_a.get("row_number"))
        src_b = rows_b.get(ev_b.get("row_number"))
        raw_a = src_a[12] if src_a else None
        raw_b = src_b[12] if src_b else None
        agency_name = ((src_a[3] if src_a else None) or (src_b[3] if src_b else None)
                       or NO_DATA)

        ok_a, note_a = value_consistency(raw_a, f.get("amount_a"))
        ok_b, note_b = value_consistency(raw_b, f.get("amount_b"))
        notes = " · ".join(n for n in (note_a, note_b) if n)

        mstat = matching_status(f)
        direction = change_direction(f.get("amount_a"), f.get("amount_b"))

        rec = {
            "order_no": i + 1,
            "sample_id": "P-%03d" % (i + 1),
            "finding_ref": "%s#%d" % (run_label, i),
            "run_label": run_label,
            "dataset_class": "T1 (สาธารณะ)",
            "matching_status": mstat[0],
            "matching_color": mstat[1],
            "agency_code": roles["agency_code"],
            "agency_name": agency_name,
            "agency_display": (roles["agency_code"] + " " + agency_name).strip(),
            "budget_group": roles["budget_group"],
            "plan_name": roles["plan_name"],
            "output_name": roles["output_name"],
            "activity_name": roles["activity_name"],
            "objective_category": roles["objective_category"],
            "objective_subcategory": roles["objective_subcategory"],
            "capital_class": roles["capital_class"],
            "item_label": roles["item_label"],
            "count_unit": NO_DATA,     # ชุดข้อมูล T1 ไม่มีฟิลด์หน่วยนับ — ไม่เดา
            "amount_a": f.get("amount_a"),
            "amount_b": f.get("amount_b"),
            "amount_diff": f.get("amount_diff"),
            "direction": direction[0],
            "direction_fill": direction[1],
            "direction_font": direction[2],
            "value_consistency": ("ตรงกัน" if (ok_a and ok_b) else "⚠ ต่างกัน"),
            "value_consistency_note": notes,
            "raw_value_a": raw_a,
            "raw_value_b": raw_b,
            "unit": f.get("unit", ""),
            "pct_change": f.get("pct_change"),
            "pct_note": f.get("pct_note", ""),
            "category": f.get("category", ""),
            "category_label": f.get("category_label", ""),
            "rule_id": ("T1-" + f["category"]) if f.get("category") else "",
            "rule_set_version": f.get("rule_set_version", ""),
            "machine_status": f.get("machine_status", ""),
            "review_status": f.get("review_status", ""),
            "match_level": f.get("match_level", ""),
            "match_step": f.get("match_step", ""),
            "match_score": f.get("match_score"),
            "match_basis": f.get("match_basis", ""),
            "system_reason": f.get("reason", ""),
            "file_a_label": ev_a.get("file_label", ""),
            "file_a_name": ev_a.get("file_name", name_a),
            "file_a_sha256": ev_a.get("sha256", ""),
            "sheet_a": ev_a.get("sheet_name", ""),
            "row_a": ev_a.get("row_number"),
            "cell_a": ev_a.get("amount_cell", ""),
            "file_b_label": ev_b.get("file_label", ""),
            "file_b_name": ev_b.get("file_name", name_b),
            "file_b_sha256": ev_b.get("sha256", ""),
            "sheet_b": ev_b.get("sheet_name", ""),
            "row_b": ev_b.get("row_number"),
            "cell_b": ev_b.get("amount_cell", ""),
            "context_a": {r: rows_a.get(r) for r in
                          (ev_a.get("row_number", 0) - 1, ev_a.get("row_number"),
                           (ev_a.get("row_number") or 0) + 1) if r in rows_a},
            "context_b": {r: rows_b.get(r) for r in
                          (ev_b.get("row_number", 0) - 1, ev_b.get("row_number"),
                           (ev_b.get("row_number") or 0) + 1) if r in rows_b},
        }
        for field in REVIEWER_FIELDS:
            rec[field] = ""          # ช่องของผู้วิจัยต้องว่างเสมอตอนสร้าง
        rec["evidence_a_text"] = evidence_text(rec, "a")
        rec["evidence_b_text"] = evidence_text(rec, "b")
        records.append(rec)
    return records


def evidence_text(rec, side):
    """ข้อความหลักฐานที่อ่านแล้วเข้าใจทันที — ไม่ใช่แค่ `M5045`"""
    if side == "a":
        doc, cell, sheet, row = SIDE_A_SHORT, rec["cell_a"], rec["sheet_a"], rec["row_a"]
    else:
        doc, cell, sheet, row = SIDE_B_SHORT, rec["cell_b"], rec["sheet_b"], rec["row_b"]
    if not cell:
        return doc + " — ไม่มีรายการฝั่งนี้ " + NO_DATA
    return ("%s — %s — กิจกรรม %s — รายการ %s — ชีต %s แถว %s เซลล์ %s"
            % (doc, rec["agency_name"], rec["activity_name"], rec["item_label"],
               sheet, row, cell))


def hyperlink_formula(path, sheet, cell, display):
    """สูตรนำทางอย่างเดียว — ไม่คำนวณและไม่แก้ค่าผลตรวจใด ๆ"""
    safe_display = str(display).replace('"', "'")
    return '=HYPERLINK("[%s]%s!%s","%s")' % (path, sheet, cell, safe_display)
