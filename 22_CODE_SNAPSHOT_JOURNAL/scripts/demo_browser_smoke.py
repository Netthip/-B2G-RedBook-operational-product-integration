# -*- coding: utf-8 -*-
"""Browser smoke test — เดินครบทั้งหกขั้นบนหน้าจอจริง แล้วเก็บภาพทุกขั้น

    python scripts/demo_launch.py            # หน้าต่างที่หนึ่ง — เปิดเซิร์ฟเวอร์
    python scripts/demo_browser_smoke.py     # หน้าต่างที่สอง — เดินและเก็บภาพ

ต่างจาก ``tests/test_demo_walkthrough.py`` ตรงที่ชุดนี้ขับ **เบราว์เซอร์จริง**
จึงจับสิ่งที่ชุดทดสอบระดับ HTTP จับไม่ได้ เช่น ปุ่มที่ถูกปิด · CSP บล็อกสไตล์ ·
หน้าจอที่พังเฉพาะตอน render จริง

🔴 **SYNTHETIC DEMONSTRATION DATA** — ทุกภาพที่ได้มาจากคู่ไฟล์สังเคราะห์
ห้ามรายงานผลจากภาพเหล่านี้ว่าเป็นข้อผิดพลาดที่พบในเอกสารจริง

คืน exit code ไม่ใช่ศูนย์เมื่อขั้นใดขั้นหนึ่งไม่เป็นไปตามที่ควรเป็น
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_DATA_DIR = PROJECT_ROOT / ".data_demo"
FILES_DIR = DEMO_DATA_DIR / "demo_files"
SHOTS_DIR = DEMO_DATA_DIR / "screenshots"

BASE = "http://127.0.0.1:8600"
VIEWPORT = {"width": 1440, "height": 900}

_step = 0
_failures: list[str] = []


def _utf8_console() -> None:
    """คอนโซล Windows ภาษาไทยใช้ code page 874 ซึ่งพิมพ์อักขระบางตัวไม่ได้"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _shot(page, name: str) -> Path:
    global _step
    _step += 1
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SHOTS_DIR / f"{_step:02d}_{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  [ภาพ] {path.name}")
    return path


def _expect(page, needle: str, where: str) -> None:
    if needle not in page.content():
        _failures.append(f"{where}: ไม่พบข้อความ {needle!r}")
        print(f"  [ไม่ผ่าน] {where}: ไม่พบ {needle!r}")
    else:
        print(f"  [ผ่าน] {where}: พบ {needle!r}")


def run(page) -> str:
    a = FILES_DIR / "DEMO_SYNTHETIC_A_before_reduction.xlsx"
    b = FILES_DIR / "DEMO_SYNTHETIC_B_after_reduction.xlsx"
    if not (a.exists() and b.exists()):
        raise SystemExit("ยังไม่มีไฟล์สาธิต — รัน python scripts/demo_launch.py ก่อน")

    print("ขั้น 0 · แดชบอร์ด")
    page.goto(BASE, wait_until="networkidle")
    for label in ("งานตรวจ", "รอบตรวจ", "คิวพิจารณา", "Preflight", "ส่งออก",
                  "Audit", "บัญชีกฎ"):
        _expect(page, label, "เมนูซ้าย")
    _shot(page, "dashboard")

    print("ขั้น 1 · ตั้งงานตรวจ")
    page.goto(f"{BASE}/projects/new", wait_until="networkidle")
    page.fill("input[name=name]", "งานสาธิต — เดินครบหนึ่งรอบจากเบราว์เซอร์")
    page.check("input[name=mode][value=before_after_reduction]")
    _shot(page, "new_project")
    page.click("form[action='/projects/new'] button[type=submit]")
    page.wait_for_load_state("networkidle")
    project_url = page.url
    _expect(page, "ใส่ไฟล์สองฉบับ", "แถบขั้นตอนบนหน้างานตรวจ")

    print("ขั้น 2 · ใส่ไฟล์สองฉบับ")
    for side, path, year in (("A", a, "2569"), ("B", b, "2570")):
        page.goto(project_url, wait_until="networkidle")
        page.set_input_files(f"#file-{side}", str(path))
        page.fill(f"#year-{side}", year)
        page.fill(f"#kind-{side}",
                  "ฉบับก่อนปรับลด" if side == "A" else "ฉบับหลังปรับลด")
        page.click(f"form:has(#file-{side}) button[type=submit]")
        page.wait_for_load_state("networkidle")
    page.goto(project_url, wait_until="networkidle")
    _shot(page, "files_ready")

    print("ขั้น 3 · ให้ระบบหาความต่าง")
    page.click("form[action$='/analyze'] button[type=submit]")
    page.wait_for_load_state("networkidle")
    run_url = page.url
    rid = run_url.rstrip("/").rsplit("/", 1)[-1]
    _expect(page, "ผลตรวจเทียบเอกสาร", "หน้าสรุปรอบตรวจ")
    _shot(page, "run_summary")

    print("ขั้น 3.5 · ด่านต้องกันการส่งออกไว้ก่อน")
    page.goto(f"{BASE}/t1b/runs/{rid}/export", wait_until="networkidle")
    disabled = page.locator("button[type=submit][disabled]").count()
    if not disabled:
        _failures.append("หน้าส่งออก: ปุ่มควรถูกปิดขณะที่ด่านยังไม่ผ่าน")
    else:
        print("  [ผ่าน] ปุ่มส่งออกถูกปิดไว้")
    _shot(page, "export_blocked")

    page.goto(f"{BASE}/t1b/runs/{rid}/preflight", wait_until="networkidle")
    _expect(page, "ยังส่งออกไม่ได้", "หน้าตรวจก่อนส่งออก")
    _expect(page, "ทางแก้", "หน้าตรวจก่อนส่งออก")
    _shot(page, "preflight_blocked")

    print("ขั้น 4 · พิจารณารายการ")
    page.goto(f"{BASE}/t1b/runs/{rid}/queue?view=table", wait_until="networkidle")
    _expect(page, "พิจารณารายการ", "หน้าคิว")
    _shot(page, "queue")
    page.click("button[value='all_filtered']")
    page.wait_for_load_state("networkidle")
    _shot(page, "bulk_confirm")
    page.click("form button[type=submit]")
    page.wait_for_load_state("networkidle")
    _shot(page, "bulk_result")

    print("ขั้น 5 · ตรวจก่อนส่งออก + รับทราบรายการที่ระบบอ่านไม่ครบ")
    page.goto(f"{BASE}/t1b/runs/{rid}/preflight", wait_until="networkidle")
    _expect(page, "รับทราบรายการที่ระบบอ่านไม่ครบ", "หน้าตรวจก่อนส่งออก")
    page.fill("input[name=reviewer]", "ผู้ตรวจสาธิต")
    page.fill("textarea[name=note]",
              "อ่านรายการที่ระบบยังตีความไม่ได้แล้ว และรับทราบว่าชุดส่งออกไม่ครอบคลุมส่วนนี้")
    _shot(page, "preflight_ack_form")
    page.click("form[action$='/preflight/ack'] button[type=submit]")
    page.wait_for_load_state("networkidle")
    _expect(page, "ผ่านทุกเงื่อนไขแล้ว", "หน้าตรวจก่อนส่งออกหลังรับทราบ")
    _shot(page, "preflight_pass")

    print("ขั้น 6 · ส่งออกชุดงาน")
    page.goto(f"{BASE}/t1b/runs/{rid}/export", wait_until="networkidle")
    if page.locator("button[type=submit][disabled]").count():
        _failures.append("หน้าส่งออก: ปุ่มยังถูกปิดทั้งที่ด่านผ่านแล้ว")
    _shot(page, "export_ready")
    page.click("form[action$='/export'] button[type=submit]")
    page.wait_for_load_state("networkidle")
    _expect(page, "ไฟล์ที่สร้างแล้ว", "หน้าส่งออกหลังสร้างไฟล์")
    _shot(page, "export_done")

    print("ขั้น 7 · Audit และการกลับเข้ารอบเดิมจากแดชบอร์ด")
    page.goto(f"{BASE}/t1b/runs/{rid}/audit", wait_until="networkidle")
    _shot(page, "audit")
    page.goto(BASE, wait_until="networkidle")
    _expect(page, rid, "แดชบอร์ดต้องเห็นรอบตรวจเดิม")
    _expect(page, "ขั้นต่อไป", "แดชบอร์ดต้องบอกขั้นต่อไป")
    _shot(page, "dashboard_with_run")

    print("ขั้น 8 · จอแคบ")
    page.set_viewport_size({"width": 430, "height": 900})
    page.goto(BASE, wait_until="networkidle")
    _shot(page, "dashboard_narrow")
    page.set_viewport_size(VIEWPORT)
    return rid


def main() -> None:
    _utf8_console()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport=VIEWPORT, locale="th-TH")
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text)
                if m.type == "error" else None)
        try:
            rid = run(page)
        finally:
            context.close()
            browser.close()

    if errors:
        _failures.append("เบราว์เซอร์รายงานข้อผิดพลาด: " + " | ".join(errors[:5]))

    print()
    print("=" * 66)
    if _failures:
        print(f" ไม่ผ่าน {len(_failures)} ข้อ")
        for f in _failures:
            print("  -", f)
        print("=" * 66)
        sys.exit(1)
    print(f" ผ่านครบทุกขั้น · รอบตรวจ {rid} · ภาพอยู่ที่ {SHOTS_DIR}")
    print("=" * 66)


if __name__ == "__main__":
    main()
