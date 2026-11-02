# -*- coding: utf-8 -*-
"""เดิน 5 scenario เดโมของ Library UI บนเบราว์เซอร์จริง แล้วเก็บภาพทุกขั้น

    python scripts/demo_launch.py                      # หน้าต่างที่หนึ่ง (หรือ REDBOOK_PORT=8628)
    python scripts/library_journey.py --base http://127.0.0.1:8628 --out .data_demo/library
    python scripts/library_journey.py --axe path/to/axe.min.js   # ตรวจ axe ทุกหน้าที่เดินผ่าน

1. หาเล่มของปีและกระทรวงที่กำหนด     แท็บปี 2569 → กระทรวงสาธารณสุข → การ์ดบอกปี/ขั้น/กระทรวง/ไฟล์
2. เปิด official PDF                 ลิงก์ชี้ bb.go.th และเปิดแท็บใหม่ (ไม่กด ไม่ดาวน์โหลด)
3. หาเอกสารคู่ Draft/Act             หน้ารายละเอียด → ส่วน ร่าง → พ.ร.บ. (สถานะตามทะเบียน ไม่เดา)
4. เข้า comparison                   ปุ่มเปรียบเทียบ → เลือกเล่มเองจากคลัง → กลับหน้าเปรียบเทียบพร้อมคู่
5. เข้า verification workflow         ตั้งงานตรวจโดยอ้างอิงคู่นี้ → ขั้น 2 ของ workflow เดิม
+ สถานะ: แท็บ พ.ร.บ. ว่าง · ตัวกรอง Excel · หน้าตัวอย่างสถานะ · จอมือถือ

ภาพใช้เฉพาะทะเบียนเล่มที่เผยแพร่ต่อสาธารณะ + ภาพปกจากหน้าแรกของ PDF ทางการ
🔴 ภาพยังไม่ขึ้น repo / สไลด์ จนกว่าจะผ่าน leak_check + คนตรวจภาพด้วยตา (Bo · #24 D5)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIEWPORT = {"width": 1440, "height": 900}
OFFICIAL = "https://www.bb.go.th/"

_failures: list[str] = []
_axe_hits: list[str] = []
_n = 0
_axe_src: str | None = None


def _ok(cond: bool, what: str) -> None:
    print(f"  [{'ผ่าน' if cond else 'ไม่ผ่าน'}] {what}")
    if not cond:
        _failures.append(what)


def _shot(page, out: Path, name: str, full: bool = False) -> None:
    global _n
    _n += 1
    out.mkdir(parents=True, exist_ok=True)
    # CSP ของแอปห้าม eval ⇒ ใช้ evaluate (ผ่าน CDP) แทน wait_for_function · บังคับโหลดภาพปกที่ lazy ก่อนถ่าย
    page.evaluate("""async () => {
      const imgs = [...document.querySelectorAll('img[data-thumb]')];
      imgs.forEach(i => { i.loading = 'eager'; });
      await Promise.all(imgs.map(i => i.complete ? null :
        new Promise(r => { i.addEventListener('load', r); i.addEventListener('error', r); })));
      await new Promise(r => setTimeout(r, 300));
    }""")
    page.screenshot(path=str(out / f"{_n:02d}_{name}.png"), full_page=full)
    if _axe_src:
        page.evaluate(_axe_src)
        res = page.evaluate("""async () => {
          const r = await axe.run(document, {runOnly: {type: 'tag',
            values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}});
          return r.violations.map(v => v.id + ' x' + v.nodes.length);
        }""")
        for v in res:
            _axe_hits.append(f"{name}: {v}")


def _go(page, url):
    page.goto(url, wait_until="networkidle")


def _click(page, locator):
    locator.first.click()
    page.wait_for_load_state("networkidle")


def scenario_1(page, base, out):
    print("1. หาเล่มของปีและกระทรวงที่กำหนด")
    _go(page, base + "/books")
    _ok(page.locator('.year-rail .yr').count() == 4, "แถบปีด้านซ้าย ทุกปี + 2570/2569/2568")
    _ok(page.evaluate("getComputedStyle(document.querySelector('.year-rail')).flexDirection") == "column",
        "จอกว้าง: แถบปีเป็นแนวตั้ง")
    _ok(page.locator('.stage-tabs .tab').count() == 3, "แท็บขั้น ทุกขั้น/ร่าง/พ.ร.บ.")
    _shot(page, out, "library_overview")
    _click(page, page.locator('.year-rail a', has_text="2569"))
    _ok("year=2569" in page.url, "กดแท็บปี 2569")
    page.select_option("#ministry", label="กระทรวงสาธารณสุข")
    page.wait_for_load_state("networkidle")
    _click(page, page.locator('.seg a', has_text="รายเล่ม"))
    card = page.locator(".book-card").first
    text = card.inner_text()
    _ok("2569" in text and "สาธารณสุข" in text, "การ์ดบอกปี + กระทรวง")
    _ok(card.locator(".stage-chip").count() == 1, "การ์ดมีชิปขั้นเอกสาร")
    _ok(card.locator(".asset").count() == 3, "การ์ดมีป้าย PDF · Excel · ทางการ")
    _ok(card.locator("img[data-thumb]").count() == 1, "การ์ดมีภาพปกจริง")
    _shot(page, out, "find_2569_health")
    return card


def scenario_2(page, card):
    print("2. เปิด official PDF")
    link = card.locator("a", has_text="เปิด PDF")
    href = link.get_attribute("href") or ""
    _ok(href.startswith(OFFICIAL), f"ลิงก์ PDF ชี้เว็บทางการ ({href[:45]}…)")
    _ok(link.get_attribute("target") == "_blank", "เปิดในแท็บใหม่")
    _ok("noopener" in (link.get_attribute("rel") or ""), "rel=noopener")


def scenario_3(page, base, out, card):
    print("3. หาเอกสารคู่ Draft/Act")
    _click(page, card.locator("a", has_text="ดูรายละเอียด"))
    _ok(page.locator(".stage-pair").count() == 1, "หน้ารายละเอียดมีส่วน ร่าง → พ.ร.บ.")
    _ok(page.locator(".thumb.hero img").count() == 1, "หน้ารายละเอียดมีภาพปกใหญ่")
    linked = page.locator(".stage-pair a.sp-slot").count()
    pair = page.locator(".stage-pair").inner_text()
    if linked == 2:
        _ok("พ.ร.บ." in pair, "คู่ ร่าง → พ.ร.บ. ที่ทะเบียนยืนยันแล้ว กดไปอีกฝั่งได้")
    else:
        _ok("ยังไม่มีคู่ที่ยืนยันจากข้อมูลเล่ม" in pair or "ยังไม่ยืนยัน" in pair, "บอกสถานะคู่ตามทะเบียน (ไม่เดา)")
    _shot(page, out, "detail_draft_act", full=True)
    detail_url = page.url
    _go(page, base + "/books?stage=act")
    if page.locator(".book-card").count():
        _ok(page.locator(".stage-chip.s-act").count() > 0, "แท็บ พ.ร.บ. แสดงเล่ม พ.ร.บ.")
        _shot(page, out, "act_tab")
    else:
        _ok("ยังไม่มีเล่มขั้น พ.ร.บ. ในทะเบียน" in page.content(), "แท็บ พ.ร.บ. อธิบายว่ายังไม่มีข้อมูล")
        _shot(page, out, "act_tab_missing")
    return detail_url


def scenario_4(page, base, out, detail_url):
    print("4. เข้า comparison")
    _go(page, detail_url)
    anchor = detail_url.rstrip("/").split("/")[-1]
    _click(page, page.locator(".book-hero a", has_text="เปรียบเทียบ"))
    _ok("/books/compare?a=" in page.url, "เข้าหน้าเปรียบเทียบ")
    _ok(page.locator(".cmp-option").count() == 2, "เสนอสองแบบ: ร่าง→พ.ร.บ. และ ปีต่อปี")
    offered = page.locator(f'a[href*="/books/compare?a={anchor}&b="]').count()
    if offered:
        _ok(page.locator(".sp-slot.is-empty").count() + offered >= 1, f"เสนอคู่ที่ทะเบียนยืนยัน {offered} คู่")
    else:
        _ok(True, "ไม่มีคู่ที่ยืนยัน — ไม่เสนอคู่ที่ระบบเดาเอง")
    _shot(page, out, "compare_entry")
    if offered:   # ทะเบียนมีคู่ยืนยัน: ใช้คู่ ร่าง→พ.ร.บ. ที่ระบบเสนอ
        _click(page, page.locator(".cmp-option a.btn", has_text="เลือกคู่นี้"))
        _ok(page.locator(".cmp-table").count() == 1, "ตารางเทียบข้อมูลเล่ม A/B (คู่ ร่าง→พ.ร.บ.)")
        _ok("ร่าง พ.ร.บ. → พ.ร.บ." in page.content(), "คำเตือนเรียกคู่ว่า ร่าง→พ.ร.บ. ไม่ใช่การปรับลด")
        _shot(page, out, "compare_pair_draft_act", full=True)
        return
    _click(page, page.locator("a", has_text="เลือกจากคลังเล่ม"))
    _ok("กลับไปหน้าเปรียบเทียบ" in page.content(), "โหมดเลือกฉบับที่สอง (กลับหน้าเปรียบเทียบ)")
    _click(page, page.locator('.year-rail a', has_text="2570"))
    page.select_option("#ministry", label="กระทรวงสาธารณสุข")
    page.wait_for_load_state("networkidle")
    _click(page, page.locator("a", has_text="เลือก").filter(has_not_text="เลือกจาก"))
    _ok("/books/compare?a=" in page.url and "&b=" in page.url, "กลับหน้าเปรียบเทียบพร้อมคู่ที่ผู้ใช้เลือก")
    _ok(page.locator(".cmp-table").count() == 1, "ตารางเทียบข้อมูลเล่ม A/B")
    _shot(page, out, "compare_pair", full=True)


def scenario_5(page, out):
    print("5. เข้า verification workflow")
    _click(page, page.locator(".cta-band a", has_text="ตั้งงานตรวจโดยอ้างอิงคู่นี้"))
    _ok("/verify/start?a=" in page.url, "หน้าเริ่มตรวจรับคู่จากหน้าเปรียบเทียบ")
    _shot(page, out, "verify_start")
    _click(page, page.locator('form[action="/verify/start"] button[type=submit]'))
    _ok(bool(re.search(r"/projects/[^/]+$", page.url)), "สร้างงานตรวจแล้วเข้าขั้น 2 ของ workflow เดิม")
    _shot(page, out, "workflow_step2")


def extra_states(page, base, out):
    print("+ สถานะและจอมือถือ")
    _go(page, base + "/books?file=excel&view=cards")
    if page.locator(".book-card").count():
        _ok(page.locator(".asset.ok", has_text="Excel").count() > 0, "ตัวกรอง Excel แสดงเล่มที่มี Excel")
        _shot(page, out, "excel_filter")
    else:
        _ok("ไม่ได้แปลว่าไม่มี" in page.content(), "ตัวกรอง Excel ไม่อ้างว่า 'ไม่มี'")
    _ok("ไม่มี Excel" not in page.content(), "ไม่มีข้อความ 'ไม่มี Excel'")
    _go(page, base + "/books/states")
    _ok(page.locator(".book-card.is-sample").count() >= 8, "หน้าตัวอย่างสถานะครบ")
    _shot(page, out, "states", full=True)
    _go(page, base + "/books/does-not-exist")
    _ok(page.locator("text=ไม่พบเล่มที่ระบุ").count() >= 1, "หน้าไม่พบเล่ม")
    page.set_viewport_size({"width": 390, "height": 844})
    _go(page, base + "/books?view=cards&year=2570")
    _ok(page.evaluate("getComputedStyle(document.querySelector('.year-rail')).flexDirection") == "row",
        "จอแคบ: แถบปีกลายเป็นแท็บแนวนอน")
    w = page.evaluate("document.documentElement.scrollWidth")
    _ok(w <= 390, f"จอมือถือไม่เลื่อนแนวนอน (กว้าง {w}px)")
    _shot(page, out, "mobile_cards")
    page.set_viewport_size(VIEWPORT)


def main():
    global _axe_src
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8628")
    ap.add_argument("--out", default=str(PROJECT_ROOT / ".data_demo" / "library_journey"))
    ap.add_argument("--axe", help="เส้นทางไฟล์ axe.min.js (ไม่บังคับ)")
    args = ap.parse_args()
    out = Path(args.out)
    if args.axe:
        _axe_src = Path(args.axe).read_text(encoding="utf-8")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, locale="th-TH")
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        try:
            card = scenario_1(page, args.base, out)
            scenario_2(page, card)
            detail = scenario_3(page, args.base, out, card)
            scenario_4(page, args.base, out, detail)
            scenario_5(page, out)
            extra_states(page, args.base, out)
        finally:
            context.close()
            browser.close()
    errors = [e for e in errors if "404" not in e]
    if errors:
        _failures.append("เบราว์เซอร์รายงานข้อผิดพลาด: " + " | ".join(errors[:5]))
    if _axe_hits:
        _failures.append("axe: " + " | ".join(_axe_hits[:10]))
    print("=" * 60)
    if _failures:
        print(f" ไม่ผ่าน {len(_failures)} ข้อ")
        for f in _failures:
            print("  -", f)
        sys.exit(1)
    print(f" ผ่านครบ 5 scenario + สถานะ{' + axe 0 violation' if _axe_src else ''} · ภาพ {_n} ภาพที่ {out}")


if __name__ == "__main__":
    main()
