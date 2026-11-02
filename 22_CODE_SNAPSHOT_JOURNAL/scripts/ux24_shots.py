# -*- coding: utf-8 -*-
"""#24 — ภาพ 8 ภาพสำหรับตรวจด้วยตา + axe-core + เช็กจอแคบ บนสถานะเดโมที่ล้างแล้ว (งานตรวจเดียว)

    python scripts/build_dev_pair_fixture.py
    (เปิด demo_launch.py --reset โดยตั้ง REDBOOK_BOOK_CATALOG=.data_demo/dev_pair_fixture.json · REDBOOK_PORT=8632)
    python scripts/ux24_shots.py --base http://127.0.0.1:8632 --out <โฟลเดอร์นอก repo> [--axe path/to/axe.min.js]

1 หน้าคลัง · 2 แท็บปี/ขั้น · 3 การ์ด · 4 รายละเอียดเล่ม · 5 คู่ ร่าง ↔ พ.ร.บ. · 6 ภาพรวมผลเปรียบเทียบ
7 ข้อสังเกต + หลักฐาน · 8 Preflight
🔴 ภาพใช้ DEV fixture (เล่ม พ.ร.บ./คู่ สังเคราะห์ มีป้าย DEV ทุกหน้า) + สมุดงานสังเคราะห์ของโหมดสาธิต
   ยังไม่ขึ้น repo / ไม่เผยแพร่ จนกว่าจะผ่าน leak gate + คนตรวจภาพด้วยตา (#24 D5)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: ชุดรหัสต่อทะเบียน — real = ทะเบียนแหล่งทางการของ #27 (ภาพ Library/รายละเอียด/ความพร้อมเอกสาร ตามคำตัดสิน Bo)
#: dev = DEV fixture (พ.ร.บ./คู่ สังเคราะห์) · ส่วนผลตรวจ/เปรียบเทียบเนื้อหา/preflight ใช้สมุดงานสังเคราะห์ทั้งสองแบบ
IDS = {"dev": {"anchor": "bb-2570-18879", "act": "DEV-ACT-bb-2570-18879",
               "unpaired": ("bb-2570-18878", "bb-2569-17723")},
       "real": {"anchor": "bb-18879", "act": "bb-19190", "unpaired": ("bb-18878", "bb-17724")}}
ANCHOR = ACT = ""
UNPAIRED: tuple = ()
DEV = True
WIDTHS = (1440, 1280, 820)
_fail: list[str] = []
_axe: str | None = None


def _ok(cond, what):
    print(f"  [{'ผ่าน' if cond else 'ไม่ผ่าน'}] {what}")
    if not cond:
        _fail.append(what)


def _check(page, label):
    """axe-core (ถ้ามี) + ไม่มีแถบเลื่อนแนวนอนทุกความกว้าง"""
    if _axe:
        page.evaluate(_axe)          # ฉีดผ่าน DevTools — ไม่ต้องลด CSP ของแอป
        v = page.evaluate("async () => (await axe.run(document, {resultTypes:['violations']}))"
                          ".violations.map(x => x.id + ':' + x.nodes.length)")
        _ok(not v, f"axe {label}: {v or 'ไม่มี violation'}")
    for w in WIDTHS:
        page.set_viewport_size({"width": w, "height": 900})
        over = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        _ok(not over, f"{label} กว้าง {w}px ไม่เลื่อนแนวนอน")
    page.set_viewport_size({"width": 1440, "height": 900})


def _shot(page, out, n, name, full=False):
    p = out / f"{n:02d}_{name}.png"
    page.screenshot(path=str(p), full_page=full)
    print(f"  [ภาพ] {p.name}")


def run(page, base, out):
    go = lambda url: page.goto(base + url, wait_until="networkidle")
    go("/books")
    _ok(page.locator(".dev-fixture").count() == (1 if DEV else 0),
        "ป้าย DEV อยู่บนหน้าจอ" if DEV else "ทะเบียนจริงไม่มีป้าย DEV")
    _shot(page, out, 1, "library_home")
    _check(page, "คลังเล่ม")

    go("/books?year=2570&stage=act&view=cards")
    _ok(page.locator(".book-card").count() >= 1, "แท็บ 2570 · พ.ร.บ. มีเล่ม")
    if DEV:
        _ok(page.locator(".book-card .dev-chip").count() == page.locator(".book-card").count(),
            "ทุกการ์ด พ.ร.บ. ใน fixture มีป้าย DEV")
    _shot(page, out, 2, "year_stage_filter")

    go("/books?year=2570&view=cards")
    page.evaluate("document.querySelector('.book-grid')?.scrollIntoView(); window.scrollBy(0,-90)")
    _shot(page, out, 3, "document_cards")

    go(f"/books/{ANCHOR}")
    _ok(page.locator(".stage-pair a.sp-slot").count() == 2, "หน้ารายละเอียดเห็นคู่ ร่าง → พ.ร.บ. ที่ทะเบียนยืนยัน")
    _shot(page, out, 4, "book_detail", full=True)
    _check(page, "รายละเอียดเล่ม")

    go(f"/books/compare?a={ANCHOR}&b={ACT}")
    _ok(page.locator(".pair-status.is-confirmed").count() == 1, "คู่ MATCHED ขึ้นว่ายืนยันโดยทะเบียน")
    _ok(page.locator(".world-a").count() == 1 and page.locator(".world-b").count() == 1,
        "แยก A ความสมบูรณ์ชุดเอกสาร / B ความต่างเนื้อหา")
    _ok(page.locator(".world-b .pm-val").first.inner_text().strip() == "—",
        "B ยังไม่มีตัวเลขก่อนตั้งงานตรวจ (ไม่แต่งผล)")
    _shot(page, out, 5, "draft_act_pair", full=True)
    _check(page, "เปรียบเทียบคู่")

    go(f"/books/compare?a={UNPAIRED[0]}&b={UNPAIRED[1]}")
    _ok(page.locator(".pair-status.is-user").count() == 1, "คู่ที่ทะเบียนไม่ยืนยัน → ยังยืนยันคู่เอกสารไม่ได้")

    # ── เข้า workflow เดิม: ตั้งงานตรวจจากคู่ → ขั้น 2 → ไฟล์สาธิต → วิเคราะห์
    go(f"/books/compare?a={ANCHOR}&b={ACT}")
    page.click("a.btn:has-text('ตั้งงานตรวจโดยอ้างอิงคู่นี้')")
    page.wait_for_load_state("networkidle")
    page.click("form[action='/verify/start'] button[type=submit]")
    page.wait_for_load_state("networkidle")
    _ok("/projects/" in page.url, "ตั้งงานตรวจแล้วเข้าหน้างานตรวจเดิม")
    _ok(page.locator(".step.current .name").inner_text().strip() == "ใส่ไฟล์สองฉบับ", "stepper เดิมชี้ขั้น 2")
    page.click("form[action$='/demo-files'] button[type=submit]")
    page.wait_for_load_state("networkidle")
    page.click("form[action$='/analyze'] button[type=submit]")
    page.wait_for_load_state("networkidle")
    rid = page.url.rstrip("/").rsplit("/", 1)[-1]
    total = page.locator(".ov-card .ov-n").all_inner_texts()
    _ok(len(total) == 6, "ภาพรวมผลเปรียบเทียบมีการ์ด 6 กลุ่ม")
    page.evaluate("document.querySelector('.ref-strip').scrollIntoView(); window.scrollBy(0,-70)")
    _shot(page, out, 6, "comparison_overview")
    _check(page, "สรุปรอบตรวจ")

    go(f"/t1b/runs/{rid}/queue")
    page.click("table a.btn:has-text('ดู')")
    page.wait_for_load_state("networkidle")
    _shot(page, out, 7, "finding_evidence", full=True)

    go(f"/t1b/runs/{rid}/preflight")
    _shot(page, out, 8, "preflight", full=True)


def main() -> int:
    global _axe  # noqa: PLW0603
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8632")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--axe", type=Path)
    ap.add_argument("--registry", choices=sorted(IDS), default="dev")
    a = ap.parse_args()
    global ANCHOR, ACT, UNPAIRED, DEV
    ANCHOR, ACT, UNPAIRED = IDS[a.registry]["anchor"], IDS[a.registry]["act"], IDS[a.registry]["unpaired"]
    DEV = a.registry == "dev"
    a.out.mkdir(parents=True, exist_ok=True)
    _axe = a.axe.read_text(encoding="utf-8") if a.axe else None
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch()
        page = br.new_page(viewport={"width": 1440, "height": 900}, locale="th-TH")
        try:
            run(page, a.base.rstrip("/"), a.out)
        finally:
            br.close()
    print("=" * 60)
    print(" ผ่านครบ" if not _fail else f" ไม่ผ่าน {len(_fail)} ข้อ")
    for f in _fail:
        print("  -", f)
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
