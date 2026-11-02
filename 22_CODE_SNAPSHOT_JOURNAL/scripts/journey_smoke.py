# -*- coding: utf-8 -*-
"""เดินสามเส้นทางผู้ใช้ของ #24 บนเบราว์เซอร์จริง แล้วเก็บภาพทุกขั้น (public-safe)

    python scripts/demo_launch.py --reset                 # หน้าต่างที่หนึ่ง
    python scripts/journey_smoke.py                       # หน้าต่างที่สอง
    python scripts/journey_smoke.py --base http://127.0.0.1:8624 --out .data_demo/journeys

Journey A — หาเล่ม:   หน้าแรก → ค้นหา → กรองปี → การ์ด → รายละเอียดเล่ม → ลิงก์ PDF ทางการ
Journey B — เอาไปตรวจ: รายละเอียดเล่ม → ใช้เล่มนี้ → เลือกอีกฉบับ (จากคลังเล่ม) → เริ่มตรวจ → ขั้น 2
Journey C — ตรวจงาน:  ใส่คู่ไฟล์สาธิต → หาความต่าง → สรุป → รายการ + หลักฐาน → ตัดสิน
                       → ตัดสินที่เหลือ → ด่านก่อนส่งออก → ส่งออก

ภาพที่ได้ใช้ข้อมูลสองชนิดเท่านั้น: **ทะเบียนเล่มที่เผยแพร่ต่อสาธารณะแล้ว** (ลิงก์ทางการ)
และ **คู่สมุดงานสังเคราะห์ 100%** — ไม่มีข้อมูลภายใน จึงใช้ทำสไลด์ได้
🔴 ผลตรวจในภาพเป็นผลจากไฟล์ที่แต่งขึ้น ห้ามรายงานว่าเป็นข้อผิดพลาดของเล่มจริง

สคริปต์ **ไม่กด** ลิงก์ PDF ภายนอก (ไม่ดาวน์โหลด) — ตรวจเพียงว่าลิงก์ชี้ไปเว็บไซต์ทางการ
และเปิดในแท็บใหม่ · คืน exit code ไม่ใช่ศูนย์เมื่อขั้นใดไม่เป็นตามที่ควร
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIEWPORT = {"width": 1440, "height": 900}
OFFICIAL = "https://www.bb.go.th/"

_failures: list[str] = []
_n = 0


def _ok(cond: bool, what: str) -> None:
    print(f"  [{'ผ่าน' if cond else 'ไม่ผ่าน'}] {what}")
    if not cond:
        _failures.append(what)


def _expect(page, needle: str, where: str) -> None:
    _ok(needle in page.content(), f"{where}: พบ {needle!r}")


def _shot(page, out: Path, name: str) -> None:
    global _n
    _n += 1
    out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out / f"{_n:02d}_{name}.png"), full_page=True)


def _go(page, url):
    page.goto(url, wait_until="networkidle")


def _click(page, selector):
    page.click(selector)
    page.wait_for_load_state("networkidle")


def journey_a(page, base, out):
    print("Journey A · หาเล่มของปีหนึ่งและหน่วยงานหนึ่ง แล้วเปิด PDF")
    _go(page, base)
    _expect(page, "หาเล่มงบประมาณ", "หน้าแรกเริ่มด้วยช่องค้นหาเล่ม")
    _shot(page, out, "A1_home")
    page.fill("#home-q", "สาธารณสุข")
    _click(page, "form[role=search] button[type=submit]")
    _ok("/books" in page.url, "ค้นจากหน้าแรกแล้วไปหน้าคลังเล่ม")
    # D1: ค่าเริ่มต้น = มุมมองตามเล่ม — หนึ่งการ์ด หลายแถวปี
    _ok(page.locator(".year-lines li").count() >= 3, "เห็นเล่มสาธารณสุขอย่างน้อย 3 ปีในการ์ดเดียว")
    _ok(page.locator(".data-source").count() == 1, "แถบที่มาของข้อมูลโหมดสาธิต (D4) อยู่บนหน้าจอ")
    _shot(page, out, "A2_search_results")
    _click(page, ".year-rail a.yr:has-text('2569')")   # Library UI: แถบปีด้านซ้าย
    # ทะเบียน #27 มีทั้ง ร่าง และ พ.ร.บ. — เลือกขั้นร่างให้เหลือเล่มเดียวได้ทั้งสองทะเบียน
    if page.locator(".stage-tabs a.tab:has-text('ร่าง')").count():
        _click(page, ".stage-tabs a.tab:has-text('ร่าง')")
    _ok(page.locator(".book-card").count() == 1, "กรองปี 2569 · ร่าง เหลือเล่มเดียว")
    _shot(page, out, "A3_filtered_2569")
    _click(page, ".book-card .book-title a")
    _expect(page, "เล่มเดียวกันในปีอื่น", "หน้ารายละเอียดเล่ม")
    pdf = page.locator(".book-hero a.btn:has-text('เปิด PDF')")
    href = pdf.get_attribute("href") or ""
    _ok(href.startswith(OFFICIAL), "ปุ่มเปิด PDF ชี้ไปเว็บไซต์ทางการ")
    _ok(pdf.get_attribute("target") == "_blank", "PDF เปิดในแท็บใหม่ ไม่ทิ้งงานที่ทำอยู่")
    _shot(page, out, "A4_book_detail")
    return page.url


def journey_b(page, base, out, detail_url):
    print("Journey B · เลือกเอกสารสองฉบับเพื่อนำไปตรวจเปรียบเทียบ")
    _go(page, detail_url)
    _click(page, "a.btn:has-text('ตั้งงานตรวจโดยอ้างอิงเล่มนี้')")
    _expect(page, "เลือกอีกฉบับ", "หน้าเริ่มตรวจรอฉบับที่สอง")
    _expect(page, "เอกสารสาธารณะ", "ช่องเล่มระบุว่าเป็นเอกสารสาธารณะ (D4)")
    # #24: แนะนำเฉพาะคู่ที่ #27 ยืนยัน (MATCHED) · ไม่มีคู่ยืนยัน (ทะเบียนเดิม) = เลือกเองจากคลัง
    _shot(page, out, "B1_start_one_book")
    if page.locator(".suggest a.card").count():
        _expect(page, "ทะเบียนแหล่งทางการยืนยันแล้ว", "คำแนะนำมาจากคู่ที่ #27 ยืนยัน")
        _click(page, ".suggest a.card:has-text('2570')")
    else:
        _expect(page, "ยังไม่มีคู่ที่ทะเบียนแหล่งทางการยืนยัน", "ไม่แนะนำคู่ที่เดาจากชื่อ")
        _click(page, ".note a:has-text('คลังเล่ม')")
        _ok("pick=" in page.url, "เข้าคลังเล่มในโหมดเลือกฉบับที่สอง")
        _go(page, page.url + "&q=สาธารณสุข")
        _click(page, ".year-lines li:has-text('2570') a.btn:has-text('เลือก')")
    _expect(page, "ตั้งงานตรวจ", "เลือกครบสองฉบับแล้วเห็นฟอร์มตั้งงาน")
    a_year = page.locator(".slot.filled").first.inner_text()
    _ok("2569" in a_year, "ฉบับปีเก่าถูกจัดเป็นฝั่ง A อัตโนมัติ")
    _shot(page, out, "B2_start_pair")
    _click(page, "form[action='/verify/start'] button[type=submit]")
    _ok("/projects/" in page.url, "เริ่มตรวจแล้วเข้าหน้างานตรวจเดิม (ขั้น 2)")
    _expect(page, "เล่มอ้างอิงของงานนี้", "หน้างานตรวจแสดงเล่มอ้างอิง")
    _ok(page.locator(".step.current .name").inner_text().strip() == "ใส่ไฟล์สองฉบับ",
        "แถบขั้นตอนชี้ขั้น 2")
    _shot(page, out, "B3_project_step2")
    return page.url


def journey_c(page, base, out, project_url):
    print("Journey C · ดู finding เปิดหลักฐาน ตัดสิน แล้วไปถึง preflight และส่งออก")
    _go(page, project_url)
    if not page.locator("form[action$='/demo-files']").count():
        _failures.append("ไม่พบปุ่มใส่คู่ไฟล์สาธิต — เปิดเซิร์ฟเวอร์ด้วย scripts/demo_launch.py")
        return
    _click(page, "form[action$='/demo-files'] button[type=submit]")
    _shot(page, out, "C1_files_ready")
    _click(page, "form[action$='/analyze'] button[type=submit]")
    rid = page.url.rstrip("/").rsplit("/", 1)[-1]
    _expect(page, "ผลตรวจเทียบเอกสาร", "สรุปผล (IA #24: เงิน · ตัวชี้วัดและรายการ · ความต่าง)")
    _shot(page, out, "C2_summary")

    _go(page, f"{base}/t1b/runs/{rid}/queue?view=table")
    _shot(page, out, "C3_findings_queue")
    _click(page, "table a.btn:has-text('ดู')")
    _expect(page, "บันทึกคำตัดสิน", "หน้ารายการมีฟอร์มตัดสิน")
    _shot(page, out, "C4_finding_evidence")
    page.select_option("#status", index=0)
    _click(page, "form[action*='/decide'] button[type=submit]")
    _shot(page, out, "C5_after_decision")

    _go(page, f"{base}/t1b/runs/{rid}/preflight")
    _expect(page, "ยังส่งออกไม่ได้", "ด่านกันไว้ก่อนตัดสินครบ")
    _shot(page, out, "C6_preflight_blocked")

    _go(page, f"{base}/t1b/runs/{rid}/queue?view=table")
    _click(page, "button[value='all_filtered']")
    _click(page, "form button[type=submit]")
    _go(page, f"{base}/t1b/runs/{rid}/preflight")
    if page.locator("form[action$='/preflight/ack']").count():
        page.fill("input[name=reviewer]", "ผู้ตรวจสาธิต")
        page.fill("textarea[name=note]", "รับทราบรายการที่ระบบอ่านไม่ครบ (ข้อมูลสังเคราะห์)")
        _click(page, "form[action$='/preflight/ack'] button[type=submit]")
    _expect(page, "ผ่านทุกเงื่อนไขแล้ว", "ด่านผ่านหลังตัดสินครบ")
    _shot(page, out, "C7_preflight_pass")

    _go(page, f"{base}/t1b/runs/{rid}/export")
    _click(page, "form[action$='/export'] button[type=submit]")
    _expect(page, "ไฟล์ที่สร้างแล้ว", "ส่งออกสำเร็จ")
    _shot(page, out, "C8_export_done")


def extra_states(page, base, out):
    print("สถานะประกอบ · ว่าง · ผิดพลาด · มุมมองตามเล่ม · จอแคบ")
    _go(page, f"{base}/books?q=ไม่มีเล่มนี้")
    _expect(page, "ไม่พบเล่มที่ตรงกับคำค้นนี้", "สถานะไม่พบผล")
    _shot(page, out, "S1_empty")
    _go(page, f"{base}/books/not-a-book")
    _shot(page, out, "S2_not_found")
    _go(page, f"{base}/books?view=grouped&type=by_ministry")
    _shot(page, out, "S3_grouped_view")
    _go(page, f"{base}/books?view=list&year=2570")
    _shot(page, out, "S4_list_view")
    page.set_viewport_size({"width": 390, "height": 844})
    _go(page, f"{base}/books?year=2570")
    over = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    _ok(not over, "จอโทรศัพท์ไม่มีแถบเลื่อนแนวนอน")
    _shot(page, out, "S5_mobile_books")
    page.set_viewport_size(VIEWPORT)


def main() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8600")
    ap.add_argument("--out", default=str(PROJECT_ROOT / ".data_demo" / "journeys"))
    args = ap.parse_args()
    out = Path(args.out)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, locale="th-TH")
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        try:
            detail = journey_a(page, args.base, out)
            project = journey_b(page, args.base, out, detail)
            journey_c(page, args.base, out, project)
            extra_states(page, args.base, out)
        finally:
            context.close()
            browser.close()
    # หน้า 404 ที่ตั้งใจเปิดจะมีข้อความ error ของการโหลดหน้า — ไม่นับ
    errors = [e for e in errors if "404" not in e]
    if errors:
        _failures.append("เบราว์เซอร์รายงานข้อผิดพลาด: " + " | ".join(errors[:5]))
    print("=" * 60)
    if _failures:
        print(f" ไม่ผ่าน {len(_failures)} ข้อ")
        for f in _failures:
            print("  -", f)
        sys.exit(1)
    print(f" ผ่านครบทั้งสามเส้นทาง · ภาพอยู่ที่ {out}")


if __name__ == "__main__":
    main()
