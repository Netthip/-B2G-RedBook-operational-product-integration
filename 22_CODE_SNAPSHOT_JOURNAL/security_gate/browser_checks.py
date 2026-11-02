# -*- coding: utf-8 -*-
"""Browser-facing security checks (Playwright · Chromium headless) — สคริปต์เดี่ยว

ตั้งใจ **ไม่ import redbook** เพื่อให้รันด้วย python ตัวที่ติดตั้ง playwright ไว้ (อาจไม่ใช่
.venv ของโครงการ) · รับค่าทุกอย่างทาง argument · เขียนผลเป็น JSON ชุดเดียว

    python browser_checks.py --base http://127.0.0.1:PORT --files-dir DIR --out result.json
                             [--attacker-port 8799] [--shots DIR]

checks ที่ออก (ตรงกับ ``B:`` ใน matrix)

* ``B:flow.forms_submit``   — ตั้งงาน → อัปโหลดสองฝั่ง → วิเคราะห์ สำเร็จบนเบราว์เซอร์จริง
* ``B:flow.console_clean``  — console error / pageerror / CSP violation = 0 ตลอด flow
* ``B:cookie.flags``        — คุกกี้ CSRF ที่เบราว์เซอร์เก็บ: httpOnly=true · sameSite=Strict
* ``B:csrf.cross_site_form``— หน้าโจมตีบน origin อื่น (loopback คนละพอร์ต) ส่งฟอร์มมา ⇒ 403

🔴 SYNTHETIC ONLY — ไฟล์ที่อัปโหลดคือคู่สมุดงานสังเคราะห์จาก scripts/demo_ao_workbooks.py
"""
from __future__ import annotations

import argparse
import http.server
import json
import socket
import sys
import threading
import time
from pathlib import Path

ATTACK_HTML = """<!doctype html><html><body>
<form id="f" method="post" action="{target}/projects/new">
<input name="name" value="cross-site probe"><input name="mode" value="before_after_reduction">
<input name="csrf_token" value="not-the-cookie"></form>
<script>document.getElementById('f').submit();</script></body></html>"""


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _AttackerServer(threading.Thread):
    def __init__(self, port: int, target: str):
        super().__init__(daemon=True)
        html = ATTACK_HTML.format(target=target).encode("utf-8")

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)

            def log_message(self, *a):  # เงียบ
                return

        self.httpd = http.server.HTTPServer(("127.0.0.1", port), H)

    def run(self):
        self.httpd.serve_forever()

    def stop(self):
        self.httpd.shutdown()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--files-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shots", default="")
    ap.add_argument("--attacker-port", type=int, default=0)
    args = ap.parse_args(argv)

    base = args.base.rstrip("/")
    files = Path(args.files_dir)
    a = files / "DEMO_SYNTHETIC_A_before_reduction.xlsx"
    b = files / "DEMO_SYNTHETIC_B_after_reduction.xlsx"
    result = {"tool": "playwright", "checks": {}, "steps": [], "errors": [],
              "csp_violations": [], "versions": {}}

    def check(cid, status, **detail):
        result["checks"]["B:" + cid] = {"status": status, "detail": detail}

    if not (a.exists() and b.exists()):
        for cid in ("flow.forms_submit", "flow.console_clean", "cookie.flags",
                    "csrf.cross_site_form"):
            check(cid, "INCOMPLETE", reason="synthetic demo files not found")
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
        return 2

    try:
        from importlib.metadata import version as _pkg_version

        from playwright.sync_api import sync_playwright
        try:
            result["versions"]["playwright"] = _pkg_version("playwright")
        except Exception:  # noqa: BLE001
            result["versions"]["playwright"] = "?"
    except Exception as exc:  # noqa: BLE001
        for cid in ("flow.forms_submit", "flow.console_clean", "cookie.flags",
                    "csrf.cross_site_form"):
            check(cid, "INCOMPLETE", reason=f"playwright unavailable: {type(exc).__name__}")
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
        return 2

    shots = Path(args.shots) if args.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    def shot(page, name):
        if shots:
            page.screenshot(path=str(shots / f"{name}.png"), full_page=True)

    attacker_port = args.attacker_port or _free_port()
    attacker = _AttackerServer(attacker_port, base)
    attacker.start()

    errors: list[str] = []
    violations: list[str] = []
    flow_ok = False
    cookie_detail: dict = {}
    cross_status = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            result["versions"]["chromium"] = browser.version
            ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="th-TH")
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)[:200]))
            page.on("console", lambda m: errors.append("console: " + m.text[:200])
                    if m.type == "error" else None)
            page.add_init_script(
                "document.addEventListener('securitypolicyviolation', e => {"
                " window.__cspv = (window.__cspv||[]);"
                " window.__cspv.push(e.violatedDirective + ' ' + e.blockedURI); });")

            def collect_csp():
                try:
                    v = page.evaluate("window.__cspv || []")
                    violations.extend(x for x in v if x not in violations)
                except Exception:  # noqa: BLE001
                    pass

            # ---- flow
            page.goto(base + "/", wait_until="networkidle")
            shot(page, "01_dashboard")
            collect_csp()
            page.goto(base + "/projects/new", wait_until="networkidle")
            page.fill("input[name=name]", "งานตรวจความปลอดภัย (ข้อมูลสังเคราะห์)")
            page.check("input[name=mode][value=before_after_reduction]")
            page.click("form[action='/projects/new'] button[type=submit]")
            page.wait_for_load_state("networkidle")
            project_url = page.url
            result["steps"].append({"step": "create_project",
                                    "ok": "/projects/" in project_url and "new" not in project_url})
            collect_csp()
            for side, path, year in (("A", a, "2569"), ("B", b, "2570")):
                page.goto(project_url, wait_until="networkidle")
                page.set_input_files(f"#file-{side}", str(path))
                page.fill(f"#year-{side}", year)
                page.click(f"form:has(#file-{side}) button[type=submit]")
                page.wait_for_load_state("networkidle")
                result["steps"].append({"step": f"upload_{side}",
                                        "ok": "ไม่สามารถดำเนินการได้" not in page.content()})
            page.goto(project_url, wait_until="networkidle")
            shot(page, "02_files_ready")
            analyze = page.locator("form[action$='/analyze'] button[type=submit]")
            if analyze.count():
                analyze.first.click()
                page.wait_for_load_state("networkidle")
                result["steps"].append({"step": "analyze", "ok": "/t1b/runs/" in page.url
                                        or "/runs/" in page.url})
                shot(page, "03_run_summary")
            else:
                result["steps"].append({"step": "analyze", "ok": False,
                                        "reason": "analyze button not found"})
            collect_csp()
            flow_ok = all(s.get("ok") for s in result["steps"])

            # ---- cookie flags ตามที่เบราว์เซอร์เก็บ
            for c in ctx.cookies():
                if c.get("name") == "redbook_csrf":
                    cookie_detail = {"httpOnly": c.get("httpOnly"), "sameSite": c.get("sameSite"),
                                     "secure": c.get("secure"), "path": c.get("path")}

            # ---- cross-site form จาก origin อื่น (loopback คนละพอร์ต)
            statuses: list[int] = []
            page2 = ctx.new_page()
            page2.on("response", lambda r: statuses.append(r.status)
                     if r.url.startswith(base + "/projects/new") and r.request.method == "POST"
                     else None)
            page2.goto(f"http://127.0.0.1:{attacker_port}/attack.html")
            try:
                page2.wait_for_load_state("networkidle", timeout=10000)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
            cross_status = statuses[-1] if statuses else None
            shot(page2, "04_cross_site_result")
            ctx.close()
            browser.close()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"driver: {type(exc).__name__}: {str(exc)[:200]}")
        result["driver_exception"] = f"{type(exc).__name__}"
    finally:
        attacker.stop()

    result["errors"] = errors
    result["csp_violations"] = violations
    if "driver_exception" in result:
        for cid in ("flow.forms_submit", "flow.console_clean", "cookie.flags",
                    "csrf.cross_site_form"):
            check(cid, "INCOMPLETE", reason=result["driver_exception"])
    else:
        check("flow.forms_submit", "PASS" if flow_ok else "FAIL", steps=result["steps"])
        check("flow.console_clean", "PASS" if not errors and not violations else "FAIL",
              console_errors=len(errors), csp_violations=len(violations))
        check("cookie.flags",
              "PASS" if cookie_detail.get("httpOnly") is True
              and str(cookie_detail.get("sameSite", "")).lower() == "strict" else "FAIL",
              **cookie_detail)
        check("csrf.cross_site_form", "PASS" if cross_status == 403 else
              ("INCOMPLETE" if cross_status is None else "FAIL"),
              post_status=cross_status, attacker_origin=f"http://127.0.0.1:{attacker_port}")
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    return 0 if all(c["status"] == "PASS" for c in result["checks"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
