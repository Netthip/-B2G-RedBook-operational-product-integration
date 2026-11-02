# -*- coding: utf-8 -*-
"""ตรวจการเข้าถึง (accessibility) ขั้นพื้นฐานของหน้าหลักใน #24 — ไม่ต้องติดตั้งอะไรเพิ่ม

    python scripts/a11y_check.py --base http://127.0.0.1:8600

ตรวจได้ (อัตโนมัติ บนเบราว์เซอร์จริง):
  K1 ปุ่ม Tab ครั้งแรกไปที่ลิงก์ "ข้ามไปเนื้อหา"
  K2 ทุกจุดที่ Tab ไปถึง มีกรอบโฟกัสมองเห็นได้ (outline หรือ box-shadow)
  K3 กด Tab ไล่ได้จนถึงปุ่มหลักของหน้า โดยไม่ติดค้าง (ไม่มี keyboard trap)
  F1 ช่องกรอก/ตัวเลือกทุกช่องมีชื่อที่อ่านได้ (label / aria-label)
  F2 ลิงก์และปุ่มทุกตัวมีข้อความหรือ aria-label
  D1 ``<html lang="th">`` · D2 มี h1 หนึ่งตัว · D3 หัวข้อไม่ข้ามระดับ (เช่น h1 → h3)
  L1 ลิงก์ที่เปิดแท็บใหม่มี rel="noopener" และบอกผู้ใช้ (↗ หรือ aria-label)

ตัวเลือก ``--axe <axe.min.js>``: รัน axe-core (กฎ WCAG 2.x A/AA ที่ตรวจอัตโนมัติได้)
ซ้ำบนทุกหน้า — ไฟล์ axe ไม่อยู่ใน repo (เครื่องมือฝั่งผู้พัฒนา ติดตั้งด้วย npm)
ฉีดด้วย DevTools protocol จึงไม่ต้องผ่อน CSP ของแอป

🔴 นี่ **ไม่ใช่** การตรวจตาม WCAG ครบชุด — ไม่ตรวจคอนทราสต์ที่เรนเดอร์จริง
ลำดับการอ่านของโปรแกรมอ่านหน้าจอ ฯลฯ · ห้ามอ้างว่า "ผ่าน WCAG"
"""
from __future__ import annotations

import argparse
import sys

PAGES = {
    "หน้าแรก": ("/", "form[role=search] button[type=submit]"),
    "คลังเล่ม": ("/books", "form[role=search] button[type=submit]"),
    "คลังเล่ม-รายเล่ม": ("/books?view=cards&year=2570", "form[role=search] button[type=submit]"),
    "รายละเอียดเล่ม": ("/books/bb-2570-18879", "a.btn[href^='/verify/start']"),
    "ตั้งงานตรวจ": ("/verify/start?a=bb-2570-18879&b=bb-2569-17724",
                    "form[action='/verify/start'] button[type=submit]"),
}
MAX_TABS = 120

JS_STATIC = r"""
() => {
  const out = [];
  // innerText ว่างเมื่ออยู่ใน <details> ที่พับไว้ — ใช้ textContent สำรอง (ชื่อที่โปรแกรมอ่านหน้าจอได้รับไม่เปลี่ยน)
  const name = el => (el.getAttribute('aria-label') || el.innerText || el.textContent || el.value || el.title || '').trim();
  if (document.documentElement.lang !== 'th') out.push('D1 html lang ไม่ใช่ th');
  const h1 = document.querySelectorAll('h1').length;
  if (h1 !== 1) out.push(`D2 มี h1 ${h1} ตัว`);
  let prev = 0;
  for (const h of document.querySelectorAll('main h1, main h2, main h3, main h4')) {
    const lv = +h.tagName[1];
    if (prev && lv > prev + 1) out.push(`D3 หัวข้อข้ามระดับ h${prev}→h${lv}: ${h.innerText.slice(0,30)}`);
    prev = lv;
  }
  for (const el of document.querySelectorAll('input:not([type=hidden]), select, textarea')) {
    const id = el.id;
    const lab = (id && document.querySelector(`label[for="${id}"]`)) || el.closest('label');
    if (!lab && !el.getAttribute('aria-label')) out.push(`F1 ช่องไม่มีชื่อ: ${el.name}`);
  }
  for (const el of document.querySelectorAll('a[href], button')) {
    if (!name(el)) out.push(`F2 ไม่มีข้อความ: ${el.outerHTML.slice(0,60)}`);
  }
  for (const a of document.querySelectorAll('a[target=_blank]')) {
    if (!/noopener/.test(a.rel)) out.push(`L1 ไม่มี noopener: ${a.href}`);
    if (!/↗|หน้าต่างใหม่|แท็บใหม่/.test(name(a))) out.push(`L1 ไม่บอกว่าเปิดแท็บใหม่: ${name(a).slice(0,30)}`);
  }
  return out;
}
"""

JS_FOCUS = r"""
() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const cs = getComputedStyle(el);
  const visible = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) ||
                  (cs.boxShadow && cs.boxShadow !== 'none');
  return {tag: el.tagName, text: (el.innerText || el.getAttribute('aria-label') || el.name || '').trim().slice(0,40),
          cls: el.className, visible};
}
"""


def run_axe(page, axe_src):
    page.evaluate(axe_src)
    res = page.evaluate("""async () => {
      const r = await axe.run(document, {runOnly: {type: 'tag',
        values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice']}});
      return r.violations.map(v => `AXE ${v.impact} ${v.id} ×${v.nodes.length}: ` +
        v.nodes.slice(0, 2).map(n => n.target.join(' ')).join(' | '));
    }""")
    return res


def check(page, base, title, path, target, axe_src=None):
    problems = []
    page.goto(base + path, wait_until="networkidle")
    problems += page.evaluate(JS_STATIC)
    if axe_src:
        problems += run_axe(page, axe_src)
        page.goto(base + path, wait_until="networkidle")
    page.keyboard.press("Tab")
    first = page.evaluate(JS_FOCUS)
    if not first or "skip-link" not in (first.get("cls") or ""):
        problems.append(f"K1 Tab แรกไม่ใช่ลิงก์ข้ามไปเนื้อหา ({first})")
    reached = False
    target_el = page.locator(target).first
    for _ in range(MAX_TABS):
        f = page.evaluate(JS_FOCUS)
        if f and not f["visible"]:
            problems.append(f"K2 ไม่เห็นกรอบโฟกัส: {f['tag']} {f['text']}")
        if target_el.count() and target_el.evaluate("el => el === document.activeElement"):
            reached = True
            break
        page.keyboard.press("Tab")
    if not reached:
        problems.append(f"K3 กด Tab {MAX_TABS} ครั้งยังไม่ถึงปุ่มหลัก ({target})")
    tabs = _ + 1
    print(f"{'ผ่าน' if not problems else 'ไม่ผ่าน':<7} {title:<16} Tab ถึงปุ่มหลักใน {tabs} ครั้ง")
    for p in dict.fromkeys(problems):
        print("        -", p)
    return problems


def main():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8600")
    ap.add_argument("--book", help="รหัสเล่มสำหรับหน้ารายละเอียด/ตั้งงานตรวจ (ค่าเริ่มต้นของทะเบียนเดิม)")
    ap.add_argument("--book-b", help="รหัสเล่มฉบับที่สองสำหรับหน้าตั้งงานตรวจ")
    ap.add_argument("--axe", help="เส้นทางไฟล์ axe.min.js (ไม่บังคับ)")
    ap.add_argument("--run", help="รหัสรอบตรวจ T1B — ตรวจหน้าขั้น 3–6 ของรอบนั้นด้วย")
    args = ap.parse_args()
    axe_src = open(args.axe, encoding="utf-8").read() if args.axe else None
    from playwright.sync_api import sync_playwright
    total = []
    pages = dict(PAGES)
    if args.book:   # ทะเบียนอื่น (เช่นสัญญา #27) ใช้รหัสเล่มต่างจากทะเบียนเดิม
        pages["รายละเอียดเล่ม"] = (f"/books/{args.book}", pages["รายละเอียดเล่ม"][1])
        pages["ตั้งงานตรวจ"] = (f"/verify/start?a={args.book}&b={args.book_b or args.book}",
                               pages["ตั้งงานตรวจ"][1])
    if args.run:
        base_run = f"/t1b/runs/{args.run}"
        first_btn = "#main a, #main button"
        pages.update({"สรุปรอบตรวจ": (base_run, first_btn),
                      "คิวพิจารณา": (base_run + "/queue", first_btn),
                      "ตรวจก่อนส่งออก": (base_run + "/preflight", first_btn),
                      "ส่งออก": (base_run + "/export", first_btn)})
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1440, "height": 900})
        for title, (path, target) in pages.items():
            total += check(page, args.base, title, path, target, axe_src)
        b.close()
    print("=" * 60)
    print(f" พบประเด็น {len(total)} ข้อ" if total else " ผ่านทุกข้อที่ตรวจ (ไม่ใช่การรับรอง WCAG)")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
