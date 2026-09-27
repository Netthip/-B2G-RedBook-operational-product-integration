"""ตรวจร่างคอมเมนต์ตาม COMMENT_PROTOCOL.md ก่อนโพสต์.

ใช้:  python comment_lint.py ร่าง.md
exit 0 = ผ่าน · 1 = มีข้อผิด (ต้องแก้) · คำเตือนไม่ทำให้ fail
"""
import re
import sys
from pathlib import Path

KINDS = ("HANDOFF", "REVIEW", "ASK-GIFT", "CLAIM", "FINDING", "ACK")
VISIBLE_LIMIT = 1200
TOTAL_LIMIT = 3000

HEADER_RE = re.compile(r"^\*\*\[(?P<kind>[A-Z-]+)\]\*\*\s+\S.*→.*·\s*ตอบ\s+\S", re.M)
DETAILS_RE = re.compile(r"<details>.*?</details>", re.S)
LOCAL_PATH_RE = re.compile(r"[A-Za-z]:[\\/](?:Users|dev)[\\/]|/Users/|OneDrive[\\/]", re.I)


def lint(text: str) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    m = HEADER_RE.search(text.split("\n", 3)[0] if text else "")
    if not m:
        errors.append("บรรทัดแรกต้องเป็น  **[ชนิด]** ผู้ส่ง → ผู้รับ · ตอบ <id|เปิดเรื่อง>")
    elif m["kind"] not in KINDS:
        errors.append(f"ชนิด '{m['kind']}' ไม่อยู่ในรายการ {', '.join(KINDS)}")
    kind = m["kind"] if m else None

    if kind != "ACK":
        if "**สรุป:**" not in text:
            errors.append("ขาดบรรทัด **สรุป:**")
        if not re.search(r"\*\*ขอจาก [^*]+:\*\*", text):
            errors.append("ขาดบรรทัด **ขอจาก <ผู้รับ>:** (ถ้าไม่มี ให้เขียน 'ไม่มี — แจ้งเพื่อทราบ')")
        if kind in ("HANDOFF", "REVIEW", "FINDING") and "**หลักฐาน:**" not in text:
            errors.append(f"{kind} ต้องมีบรรทัด **หลักฐาน:**")
    if kind == "REVIEW" and not re.search(r"\*\*สรุป:\*\*\s*(ACCEPT|REVISE|REJECT)", text):
        errors.append("REVIEW: สรุปต้องขึ้นต้นด้วย ACCEPT / REVISE / REJECT")
    if kind == "ASK-GIFT" and not re.search(r"^\s*[-*]?\s*\(?[กขค]\)?[.)\s]", text, re.M):
        warnings.append("ASK-GIFT: ควรเขียนเป็นตัวเลือก ก / ข / ค")

    visible = DETAILS_RE.sub("", text).strip()
    if len(visible) > VISIBLE_LIMIT:
        errors.append(f"ส่วนที่มองเห็นยาว {len(visible):,} ตัวอักษร (เกิน {VISIBLE_LIMIT:,}) — ย้ายลง <details> หรือไฟล์")
    if len(text) > TOTAL_LIMIT:
        errors.append(f"ทั้งคอมเมนต์ยาว {len(text):,} ตัวอักษร (เกิน {TOTAL_LIMIT:,}) — ย้ายรายละเอียดไป threads/<ใบ>/...md")
    if visible.count("\n|") > 6:
        warnings.append("ตารางนอก <details> ยาวเกิน 6 แถว — พิจารณาย้ายลงไฟล์")
    if re.search(r"/blob/main/", text):
        warnings.append("ลิงก์ /blob/main/ — ใช้ permalink ของ commit แทน")
    for hit in LOCAL_PATH_RE.findall(text):
        errors.append(f"พบ path ในเครื่อง '{hit}' — repo นี้ PUBLIC")
    return errors, warnings


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    errors, warnings = lint(text)
    for w in warnings:
        print(f"เตือน  {w}")
    for e in errors:
        print(f"ผิด    {e}")
    visible = len(DETAILS_RE.sub("", text).strip())
    print(f"{'ผ่าน' if not errors else 'ไม่ผ่าน'} · มองเห็น {visible:,}/{VISIBLE_LIMIT:,} · ทั้งหมด {len(text):,}/{TOTAL_LIMIT:,}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
