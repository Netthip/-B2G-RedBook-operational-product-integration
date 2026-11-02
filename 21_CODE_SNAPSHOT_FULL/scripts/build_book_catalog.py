# -*- coding: utf-8 -*-
"""สร้างทะเบียนเล่มงบประมาณ (book catalog) จากหน้าเผยแพร่ทางการของสำนักงบประมาณ

    python scripts/build_book_catalog.py              # ดึงใหม่ 3 ปีล่าสุด
    python scripts/build_book_catalog.py --no-check   # ไม่ตรวจลิงก์ PDF

ทำไมต้องมี (#24): เว็บต้นทางเรียงเล่มเป็นรายการยาวต่อปี ชื่อเล่มยาว ลิงก์ PDF อยู่ในหน้าย่อย
และต้องเปิดทีละหน้ากว่าจะรู้ว่าเล่มนั้นครอบกระทรวงใด — สคริปต์นี้แปลงหน้าเหล่านั้น
เป็นระเบียนที่มีโครงสร้าง (ปี · ฉบับ · เล่ม · กระทรวง · ประเภท · ลิงก์ทางการ)
ให้หน้า Discovery ค้นและกรองได้

หลักการ
- **เก็บเฉพาะลิงก์ ไม่เก็บสำเนา PDF** — ลิงก์ชี้กลับหน้าทางการเสมอ
- เก็บ ``retrieved_at`` และผลตรวจลิงก์ (สถานะ HTTP · ชนิดไฟล์) ต่อเล่ม
  เพื่อบอกผู้ใช้ตามจริงว่า "ลิงก์ยังเปิดได้ ณ วันที่ตรวจ" ไม่ใช่รับรองตลอดไป
- ตรวจลิงก์ด้วยการขอ 1 KB แรกเท่านั้น (Range) ไม่ดาวน์โหลดทั้งไฟล์
- ข้อมูลทั้งหมดเป็นเอกสารที่เผยแพร่ต่อสาธารณะแล้ว (ขั้นร่าง พ.ร.บ.)

ไฟล์ผลลัพธ์: ``redbook/data/book_catalog.json`` (UTF-8 · เรียงคงที่ · diff อ่านได้)
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT_ROOT / "redbook" / "data" / "book_catalog.json"

BASE = "https://www.bb.go.th/"
# หมวด "เอกสารงบประมาณอิเล็กทรอนิกส์" ต่อปี — อ่านจากเมนูของเว็บทางการ 6 ต.ค. 2569
YEAR_CATEGORIES = {2570: 1538, 2569: 1511, 2568: 1464}
LISTING = "topic3.php?catID={cat}&gid=860&mid=544&page={page}&sort=1"
UA = {"User-Agent": "Mozilla/5.0 (RedBookVerify catalog builder; public pages only)"}

CATALOG_VERSION = "book-catalog-0.1.0"

# ชื่อหน่วยรับงบระดับกระทรวง/กลุ่ม ตามหน้ารวมเล่มของสำนักงบประมาณ — ใช้จับคู่ชื่อในหัวเรื่อง
# เรียงยาวก่อนสั้น เพื่อไม่ให้ "กระทรวงการคลัง" ไปกินชื่อที่ยาวกว่า
MINISTRIES = sorted([
    "งบกลาง", "สำนักนายกรัฐมนตรี", "กระทรวงกลาโหม", "กระทรวงการคลัง",
    "กระทรวงการต่างประเทศ", "กระทรวงการท่องเที่ยวและกีฬา",
    "กระทรวงการพัฒนาสังคมและความมั่นคงของมนุษย์",
    "กระทรวงการอุดมศึกษา วิทยาศาสตร์ วิจัยและนวัตกรรม",
    "กระทรวงเกษตรและสหกรณ์", "กระทรวงคมนาคม",
    "กระทรวงดิจิทัลเพื่อเศรษฐกิจและสังคม",
    "กระทรวงทรัพยากรธรรมชาติและสิ่งแวดล้อม", "กระทรวงพลังงาน",
    "กระทรวงพาณิชย์", "กระทรวงมหาดไทย", "กระทรวงยุติธรรม", "กระทรวงแรงงาน",
    "กระทรวงวัฒนธรรม", "กระทรวงศึกษาธิการ", "กระทรวงสาธารณสุข",
    "กระทรวงอุตสาหกรรม",
    "ส่วนราชการไม่สังกัดสำนักนายกรัฐมนตรี กระทรวง หรือทบวง",
    "จังหวัดและกลุ่มจังหวัด", "รัฐวิสาหกิจ", "หน่วยงานของรัฐสภา",
    "หน่วยงานของศาล", "หน่วยงานขององค์กรอิสระและองค์กรอัยการ",
    "องค์กรปกครองส่วนท้องถิ่น", "หน่วยงานอื่นของรัฐ", "สภากาชาดไทย",
    "ส่วนราชการในพระองค์", "แผนงานบูรณาการ", "แผนงานบุคลากรภาครัฐ",
    "ทุนหมุนเวียน", "แผนงานบริหารจัดการหนี้ภาครัฐ",
    "แผนงานรายจ่ายเพื่อชดใช้เงินคงคลัง",
], key=len, reverse=True)

# ชื่อที่หน้าทางการสะกดต่างจากชื่อมาตรฐาน — แปลงก่อนจับคู่
ALIASES = {
    "กระทรวงพัฒนาสังคมและความมั่นคงของมนุษย์": "กระทรวงการพัฒนาสังคมและความมั่นคงของมนุษย์",
}

# สีคาดปกของเล่ม — ผู้ปฏิบัติงานเรียกเล่มด้วยสีคาด (เช่น "เล่มคาดเหลือง")
# อ่านจากชื่อไฟล์ทางการ เช่น "ฉบับที่ ๔ เล่มคาดเหลือง.pdf"
STRIPE_RE = re.compile(r"คาด(แดง|เหลือง|ม่วง|น้ำเงิน|ชมพู|เขียว|ส้ม|ฟ้า|เทา|น้ำตาล)")

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def _get(url: str, *, range_bytes: int | None = None, timeout: int = 30):
    headers = dict(UA)
    if range_bytes:
        headers["Range"] = f"bytes=0-{range_bytes - 1}"
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


def _decode(raw: bytes) -> str:
    m = re.search(rb'charset=["\']?([A-Za-z0-9_-]+)', raw[:4000])
    enc = (m.group(1).decode().lower() if m else "utf-8")
    if enc in ("tis-620", "tis620", "windows-874", "x-windows-874"):
        enc = "cp874"
    return raw.decode(enc, errors="replace")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def classify(title: str) -> tuple[str, str]:
    """คืน ``(doc_type, doc_type_label)`` — ชนิดเอกสารที่ผู้ใช้กรองได้"""
    t = title
    if re.search(r"[A-Za-z]{4,}", t) and not re.search(r"[ก-ฮ]", t):
        return "english", "ฉบับภาษาอังกฤษ"
    if "ฉบับที่ 3" in t or "ฉบับที่ ๓" in t:
        return "expenditure_by_ministry", "รายจ่ายจำแนกตามกระทรวง (ฉบับที่ 3)"
    if re.search(r"ฉบับที่ [๑1] ", t) or "รายรับรายจ่ายเปรียบเทียบ" in t:
        return "revenue_expenditure", "รายรับรายจ่ายเปรียบเทียบ (ฉบับที่ 1)"
    if re.search(r"ฉบับที่ [๒2] ", t) or "ประมาณการรายรับ" in t:
        return "revenue_estimate", "ประมาณการรายรับ (ฉบับที่ 2)"
    if "โดยสังเขป" in t:
        return "budget_in_brief", "งบประมาณโดยสังเขป"
    if t.startswith("ร่างพระราชบัญญัติ"):
        return "bill", "ร่างพระราชบัญญัติงบประมาณ"
    return "supporting_report", "รายงานประกอบร่าง พ.ร.บ."


def parse_volume(title: str) -> tuple[str, str]:
    """คืน ``(doc_no, volume)`` เช่น ``("3", "3(2)")`` — ว่างถ้าไม่ระบุ"""
    t = title.translate(THAI_DIGITS)
    doc = re.search(r"ฉบับที่\s*(\d+)", t)
    vol = re.search(r"เล่มที่\s*(\d+)\s*(\(\s*\d+\s*\))?", t)
    v = ""
    if vol:
        v = vol.group(1) + (vol.group(2).replace(" ", "") if vol.group(2) else "")
    return (doc.group(1) if doc else ""), v


def parse_ministries(title: str) -> list[str]:
    for alias, canonical in ALIASES.items():
        if canonical not in title:
            title = title.replace(alias, canonical)
    found, rest = [], title
    for name in MINISTRIES:
        if name in rest:
            found.append(name)
            rest = rest.replace(name, " ")
    # รักษาลำดับตามที่ปรากฏในหัวเรื่อง
    return sorted(found, key=lambda n: title.find(n))


def listing_rows(year: int, cat: int) -> list[dict]:
    rows, seen = [], set()
    for page in range(1, 10):
        h = _decode(_get(BASE + LISTING.format(cat=cat, page=page)).read())
        new = 0
        pattern = r'<a[^>]+href="([^"]*topic-detail\.php\?id=\d+[^"]*catID=%d[^"]*)"[^>]*>(.*?)</a>' % cat
        for href, inner in re.findall(pattern, h, re.S):
            href = html.unescape(href)
            if href in seen:
                continue
            seen.add(href)
            new += 1
            text = _text(inner)
            # 🔴 ใช้ [0-9] ไม่ใช่ \d — \d ของ Python จับเลขไทยด้วย ทำให้ "๗๐" ท้ายชื่อหลุดเข้าวันที่
            date = re.search(r"([0-9]{1,2} \S+ [0-9]{4}) \| ([0-9]{2}:[0-9]{2})\s*$", text)
            rows.append({"href": href, "listing_text": text,
                         "posted": date.group(1) if date else ""})
        if not new:
            break
        time.sleep(0.5)
    return rows


def detail(href: str) -> dict:
    url = href if href.startswith("http") else BASE + href
    h = _decode(_get(url).read())
    # ใช้หัวเรื่องจาก og:title ของหน้าเล่มเป็นหลัก (ตรงกับข้อความในหน้ารายการทุกเล่ม ณ 7 ต.ค. 2569)
    title_m = re.search(r'<meta property="og:title" content="([^"]*)"', h)
    files = []
    for f_href, inner in re.findall(r'<a[^>]+href="([^"]*download\.php\?id=\d+[^"]*)"[^>]*>(.*?)</a>', h, re.S):
        files.append({"url": BASE + html.unescape(f_href).lstrip("/"), "label": _text(inner)})
    return {"source_page": url, "page_title": re.sub(r"\s*::\s*Budget Bureau\s*$", "", _text(title_m.group(1))) if title_m else "", "files": files}


def check_link(url: str) -> dict:
    try:
        with _get(url, range_bytes=1024, timeout=30) as r:
            head = r.read(8)
            ctype = r.headers.get("Content-Type", "")
            return {"status": r.status, "content_type": ctype,
                    "is_pdf": head.startswith(b"%PDF") or "pdf" in ctype.lower()}
    except Exception as exc:  # noqa: BLE001 — บันทึกผลตามจริง ไม่ซ่อนข้อผิดพลาด
        return {"status": None, "error": type(exc).__name__, "is_pdf": False}


def build(check: bool) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    books = []
    for year, cat in YEAR_CATEGORIES.items():
        for row in listing_rows(year, cat):
            d = detail(row["href"])
            # หัวเรื่องเต็ม: ใช้ข้อความรายการ ตัดวันที่ท้ายออก
            title = d["page_title"] or re.sub(
                r"\s*[0-9]{1,2} \S+ [0-9]{4} \| [0-9]{2}:[0-9]{2}\s*$", "", row["listing_text"]).strip()
            doc_type, doc_label = classify(title)
            doc_no, volume = parse_volume(title)
            pdf = next((f for f in d["files"] if f["label"].lower().endswith(".pdf")), None) \
                or (d["files"][0] if d["files"] else None)
            entry = {
                "id": f"bb-{year}-{re.search(r'id=(\d+)', row['href']).group(1)}",
                "fiscal_year": year,
                "title": title,
                "doc_type": doc_type,
                "doc_type_label": doc_label,
                "doc_no": doc_no,
                "volume": volume,
                "ministries": parse_ministries(title),
                "stripe_color": next((m.group(1) for f in d["files"]
                                      if (m := STRIPE_RE.search(f["label"]))), ""),
                "posted": row["posted"],
                "publisher": "สำนักงบประมาณ",
                "stage": "ร่าง พ.ร.บ. (เผยแพร่ต่อสาธารณะ)",
                "source_page": d["source_page"],
                "pdf_url": pdf["url"] if pdf else "",
                "files": d["files"],
                "retrieved_at": now,
            }
            if check and entry["pdf_url"]:
                entry["link_check"] = {"checked_at": now, **check_link(entry["pdf_url"])}
            books.append(entry)
            print(f"  {year} {doc_type:<24} {volume:<6} {title[:60]}")
            time.sleep(0.4)
    books.sort(key=lambda b: (-b["fiscal_year"], b["doc_no"] or "9", b["volume"], b["title"]))
    return {"catalog_version": CATALOG_VERSION, "generated_at": now,
            "source": "https://www.bb.go.th/ — เมนู เอกสารงบประมาณอิเล็กทรอนิกส์",
            "years": sorted(YEAR_CATEGORIES, reverse=True),
            "policy": "เก็บเฉพาะลิงก์ทางการ ไม่เก็บสำเนา PDF",
            "books": books}


def main() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-check", action="store_true", help="ไม่ตรวจลิงก์ PDF")
    args = ap.parse_args()
    data = build(check=not args.no_check)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"เขียน {len(data['books'])} เล่ม → {OUT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
