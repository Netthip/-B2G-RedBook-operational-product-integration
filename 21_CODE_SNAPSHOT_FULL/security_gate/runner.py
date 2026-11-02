# -*- coding: utf-8 -*-
"""Security gate runner — รันทุกขั้นแบบทำซ้ำได้ แล้วเก็บหลักฐานพร้อมแฮช

    python -m security_gate.runner --matrix PATH --out DIR --phase formative|final
        [--profile LOOPBACK_HTTP] [--leak-check PATH] [--pip-audit EXE]
        [--browser-python EXE] [--zap-cmd "..."] [--skip STEP,...]
        [--dispositions PATH]

ขั้น (step) และสิ่งที่เก็บใต้ ``DIR/steps/<step>/``

| step         | เครื่องมือ            | raw                         | normalized           |
|--------------|-----------------------|-----------------------------|----------------------|
| environment  | python/pip            | frozen.txt · platform.json  | —                    |
| pytest       | pytest (ไฟล์ตาม T:)   | junit.xml · stdout.txt      | result.json (T:*)    |
| target       | uvicorn (loopback)    | server_stdout.txt           | target.json          |
| http_probes  | httpx                 | probes.json                 | result.json (H:*)    |
| browser      | playwright/chromium   | result.json · screenshots/  | result.json (B:*)    |
| pip_audit    | pip-audit             | raw.json · stdout.txt       | result.json (D:*)    |
| zap          | ZAP baseline          | report.json/html            | result.json (Z:*)    |
| leak_check   | leak_check.py         | stdout.txt (ไม่มีค่า hit)    | result.json (L:*)    |

ทุก step บันทึก ``command.txt`` (คำสั่งจริง) และ ``meta.json`` (เวลาเริ่ม/จบ UTC · exit code ·
เวอร์ชันเครื่องมือ) · เครื่องมือไม่พร้อม/รันไม่จบ ⇒ check ของ step นั้นเป็น ``INCOMPLETE``
⇒ control ที่พึ่งมันได้ ``REVIEW`` (ไม่ใช่ PASS) ตาม :mod:`evaluate`

ข้อความที่เครื่องมือพิมพ์ถูกกลบเส้นทางเครื่อง (:mod:`redact`) ก่อนเขียน · แฮชทุกไฟล์ใน DIR
ถูกเขียนลง ``HASHES.sha256`` และ ``SECURITY_RUN_MANIFEST.json``

🔴 ``--out`` ต้องอยู่นอก work tree ของ git เพื่อไม่ให้หลักฐานถูก commit ติดมาโดยไม่ตั้งใจ
🔴 target คือ loopback สังเคราะห์ที่ runner เปิดเองเท่านั้น — ไม่มีตัวเลือกให้ชี้ไป URL อื่น
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from . import ASVS_VERSION, DEFAULT_PROFILE, PROFILES, SECURITY_GATE_VERSION
from .evaluate import CheckResult, evaluate, summarize
from .matrix import Matrix, load_matrix
from .redact import redact_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_VERSION = "security-verification-protocol-0.1.0"
STEPS = ("environment", "pytest", "target", "http_probes", "browser", "pip_audit", "zap",
         "leak_check")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _write(path: Path, text: str) -> None:
    """เขียนข้อความหลักฐานด้วย UTF-8 + **LF เสมอ** (T-04)

    🔴 แฮชใน HASHES.sha256 ต้องเท่ากันทุก checkout — ถ้าปล่อยให้ Windows เขียน CRLF
    git (``eol=lf``) จะแปลงเป็น LF ตอน commit ⇒ แฮชที่บันทึกไว้ไม่ตรงกับไฟล์ที่คนอื่นได้
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(redact_text(text).replace("\r\n", "\n"))


def _redact_obj(obj):
    """กลบเส้นทางใน **ค่า** ก่อน serialize — กลบหลัง json.dumps จะกิน escape (\\") แล้ว JSON พัง (T-06)"""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        # กลบ **key** ด้วย — nodeid ของ pytest ที่ parametrize ด้วยสตริงคล้ายเส้นทางเป็น key (T-07)
        return {(redact_text(k) if isinstance(k, str) else k): _redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_redact_obj(v) for v in obj]
    return obj


def _write_json(path: Path, obj) -> None:
    text = json.dumps(_redact_obj(obj), ensure_ascii=False, indent=2, default=str)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _tool_version(cmd: list[str], cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(cwd) if cwd else None)
        return (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr) else "?"
    except Exception as exc:  # noqa: BLE001
        return f"unavailable ({type(exc).__name__})"


def _zap_version(cmd: list[str], cwd: Path, jar_name: str) -> str:
    """ZAP พิมพ์บรรทัด log ปนกับรุ่น — เลือกบรรทัดที่เป็นรุ่น ไม่งั้นอ่านจากชื่อ jar"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=str(cwd))
        for line in (r.stdout + "\n" + r.stderr).splitlines():
            if re.match(r"^\s*(OWASP\s+)?ZAP\b", line) or re.match(r"^\s*\d+\.\d+\.\d+\s*$", line):
                return line.strip()
    except Exception:  # noqa: BLE001
        pass
    m = re.search(r"zap-(\d+\.\d+\.\d+)\.jar", jar_name)
    return f"ZAP {m.group(1)} (from jar name)" if m else "unknown"


class Step:
    def __init__(self, runner: "Runner", name: str):
        self.runner, self.name = runner, name
        self.dir = runner.out / "steps" / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta = {"step": name, "started_utc": _utc(), "status": "RUNNING"}
        self.checks: dict[str, CheckResult] = {}

    def run_cmd(self, cmd: list[str], *, cwd: Path | None = None, env: dict | None = None,
                timeout: int = 1800, stdout_name: str = "stdout.txt") -> subprocess.CompletedProcess:
        _write(self.dir / "command.txt", " ".join(shlex.quote(c) for c in cmd))
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=str(cwd or PROJECT_ROOT), env=env, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            self.meta["timeout"] = True
            r = subprocess.CompletedProcess(cmd, returncode=-1,
                                            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                                            stderr="TIMEOUT")
        self.meta["exit_code"] = r.returncode
        self.meta["duration_s"] = round(time.time() - t0, 2)
        _write(self.dir / stdout_name, (r.stdout or "") + ("\n--- stderr ---\n" + r.stderr if r.stderr else ""))
        return r

    def incomplete(self, check_ids: list[str], reason: str) -> None:
        for cid in check_ids:
            self.checks[cid] = CheckResult(cid, "INCOMPLETE", {"reason": reason},
                                           f"steps/{self.name}/")
        self.meta["status"] = "INCOMPLETE"
        self.meta["reason"] = reason

    def finish(self, status: str | None = None) -> None:
        self.meta["finished_utc"] = _utc()
        if status:
            self.meta["status"] = status
        elif self.meta["status"] == "RUNNING":
            self.meta["status"] = "DONE"
        _write_json(self.dir / "meta.json", self.meta)
        _write_json(self.dir / "result.json",
                    {cid: {"status": c.status, "detail": c.detail, "source": c.source}
                     for cid, c in self.checks.items()})
        self.runner.steps_meta[self.name] = self.meta
        self.runner.checks.update(self.checks)


class Runner:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.out).resolve()
        self.matrix: Matrix = load_matrix(args.matrix)
        self.profile = args.profile
        self.phase = args.phase
        self.skip = set(filter(None, (args.skip or "").split(",")))
        self.checks: dict[str, CheckResult] = {}
        self.steps_meta: dict[str, dict] = {}
        self.target_proc: subprocess.Popen | None = None
        self.target_url = ""
        self.target_data = Path(tempfile.mkdtemp(prefix="secgate_target_"))
        self.python = sys.executable

    # ------------------------------------------------------------- steps
    def step_environment(self):
        st = Step(self, "environment")
        r = st.run_cmd([self.python, "-m", "pip", "freeze", "--all"], stdout_name="frozen.txt")
        st.meta["frozen_lines"] = len([ln for ln in (r.stdout or "").splitlines() if "==" in ln])
        _write_json(st.dir / "platform.json", {
            "python": sys.version.split()[0], "implementation": platform.python_implementation(),
            "os": platform.system(), "os_release": platform.release(),
            "machine": platform.machine(), "security_gate": SECURITY_GATE_VERSION,
            "asvs": ASVS_VERSION, "protocol": PROTOCOL_VERSION,
        })
        # D:inventory — frozen + lock file
        lock = PROJECT_ROOT / "requirements.lock.txt"
        frozen = {ln.split("==")[0].lower() for ln in (r.stdout or "").splitlines() if "==" in ln}
        locked = set()
        if lock.exists():
            locked = {ln.split("==")[0].strip().lower() for ln in lock.read_text("utf-8").splitlines()
                      if "==" in ln and not ln.startswith("#")}
        st.checks["D:inventory"] = CheckResult(
            "D:inventory", "PASS" if (r.returncode == 0 and frozen and lock.exists()) else "FAIL",
            {"frozen_count": len(frozen), "lock_file_present": lock.exists(),
             "locked_count": len(locked), "in_lock_not_installed": sorted(locked - frozen)[:50],
             "installed_not_in_lock": sorted(frozen - locked)[:50]}, "steps/environment/frozen.txt")
        st.checks["D:defusedxml_present"] = CheckResult(
            "D:defusedxml_present", "PASS" if "defusedxml" in frozen else "FAIL",
            {"installed": "defusedxml" in frozen,
             "note": "openpyxl ใช้ defusedxml อัตโนมัติเมื่อติดตั้ง — ไม่มี = parser มาตรฐาน"},
            "steps/environment/frozen.txt")
        st.finish()

    def step_pytest(self):
        st = Step(self, "pytest")
        t_checks = self.matrix.referenced_checks("T")
        files = sorted({c.split(":", 1)[1].split("::")[0] for c in t_checks})
        if "pytest" in self.skip:
            st.incomplete(t_checks, "skipped by --skip")
            st.finish()
            return
        junit = st.dir / "junit.xml"
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        r = st.run_cmd([self.python, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        f"--junitxml={junit}", *files], env=env, timeout=1800)
        st.meta["pytest_version"] = _tool_version([self.python, "-m", "pytest", "--version"])
        outcomes = self._parse_junit(junit)
        if not outcomes:
            st.incomplete(t_checks, "junit.xml ว่าง/อ่านไม่ได้")
            st.finish()
            return
        _write_json(st.dir / "outcomes.json", outcomes)
        per_file: dict[str, list[str]] = {}
        for nodeid, outcome in outcomes.items():
            per_file.setdefault(nodeid.split("::")[0], []).append(outcome)
        for cid in t_checks:
            ref = cid.split(":", 1)[1]
            if "::" in ref:
                base_name = ref
                matched = {n: o for n, o in outcomes.items()
                           if n == base_name or n.startswith(base_name + "[")}
                if not matched:
                    st.checks[cid] = CheckResult(cid, "INCOMPLETE", {"reason": "test not collected"},
                                                 "steps/pytest/junit.xml")
                    continue
                status = "PASS" if all(o == "passed" for o in matched.values()) else "FAIL"
                st.checks[cid] = CheckResult(cid, status, {"outcomes": matched}, "steps/pytest/junit.xml")
            else:
                outs = per_file.get(ref, [])
                if not outs:
                    st.checks[cid] = CheckResult(cid, "INCOMPLETE", {"reason": "file not collected"},
                                                 "steps/pytest/junit.xml")
                    continue
                skipped = [o for o in outs if o == "skipped"]
                status = "PASS" if all(o == "passed" for o in outs) else (
                    "INCOMPLETE" if all(o in ("passed", "skipped") for o in outs) else "FAIL")
                st.checks[cid] = CheckResult(cid, status, {"tests": len(outs), "skipped": len(skipped),
                                                           "failed": sum(o not in ("passed", "skipped") for o in outs)},
                                             "steps/pytest/junit.xml")
        st.meta["summary"] = {"tests": len(outcomes),
                              "passed": sum(o == "passed" for o in outcomes.values()),
                              "failed": sum(o == "failed" for o in outcomes.values()),
                              "error": sum(o == "error" for o in outcomes.values()),
                              "skipped": sum(o == "skipped" for o in outcomes.values())}
        # กลบเส้นทางใน junit ด้วย (ข้อความ failure มีเส้นทางได้)
        if junit.exists():
            _write(junit, junit.read_text("utf-8", errors="replace"))
        st.finish()

    @staticmethod
    def _parse_junit(path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            return {}
        out: dict[str, str] = {}
        for tc in root.iter("testcase"):
            classname = tc.get("classname", "")
            name = tc.get("name", "")
            file_ = classname.replace(".", "/") + ".py"
            nodeid = f"{file_}::{name}"
            outcome = "passed"
            for child in tc:
                if child.tag in ("failure", "error", "skipped"):
                    outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[child.tag]
            out[nodeid] = outcome
        return out

    def step_target(self) -> bool:
        st = Step(self, "target")
        port = _free_port()
        self.target_url = f"http://127.0.0.1:{port}"
        cmd = [self.python, "-m", "security_gate.target", "--data-dir",
               str(self.target_data), "--port", str(port)]
        _write(st.dir / "command.txt", " ".join(shlex.quote(c) for c in cmd))
        log_path = st.dir / "server_stdout.txt"
        self._target_log = open(log_path, "w", encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        self.target_proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), env=env,
                                            stdout=self._target_log, stderr=subprocess.STDOUT)
        import httpx
        ok = False
        for _ in range(120):
            time.sleep(0.5)
            if self.target_proc.poll() is not None:
                break
            try:
                if httpx.get(self.target_url + "/healthz", timeout=2).status_code == 200:
                    ok = True
                    break
            except Exception:  # noqa: BLE001
                continue
        info = {}
        info_path = self.target_data / "TARGET_INFO.json"
        if info_path.exists():
            info = json.loads(info_path.read_text("utf-8"))
        _write_json(st.dir / "target.json", {"url": self.target_url, "bind": "127.0.0.1",
                                              "synthetic": True, "ready": ok, **info})
        st.meta["ready"] = ok
        st.finish("DONE" if ok else "INCOMPLETE")
        return ok

    def stop_target(self):
        if self.target_proc and self.target_proc.poll() is None:
            self.target_proc.terminate()
            try:
                self.target_proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.target_proc.kill()
        if getattr(self, "_target_log", None):
            self._target_log.close()
            p = self.out / "steps" / "target" / "server_stdout.txt"
            if p.exists():
                _write(p, p.read_text("utf-8", errors="replace"))

    def step_http_probes(self, target_ok: bool):
        st = Step(self, "http_probes")
        h_checks = self.matrix.referenced_checks("H")
        if "http_probes" in self.skip or not target_ok:
            st.incomplete(h_checks, "target not ready" if not target_ok else "skipped by --skip")
            st.finish()
            return
        from .http_probes import run_probes
        import httpx
        st.meta["httpx_version"] = httpx.__version__
        _write(st.dir / "command.txt", f"security_gate.http_probes.run_probes({self.target_url})")
        results, log = run_probes(self.target_url)
        _write_json(st.dir / "probes.json", log.to_dict())
        for cid, res in results.items():
            res.source = "steps/http_probes/probes.json"
            st.checks[cid] = res
        for cid in h_checks:
            if cid not in st.checks:
                st.checks[cid] = CheckResult(cid, "INCOMPLETE", {"reason": "probe not implemented"},
                                             "steps/http_probes/")
        st.finish()

    def step_browser(self, target_ok: bool):
        st = Step(self, "browser")
        b_checks = self.matrix.referenced_checks("B")
        if "browser" in self.skip or not target_ok:
            st.incomplete(b_checks, "target not ready" if not target_ok else "skipped by --skip")
            st.finish()
            return
        py = self.args.browser_python or self.python
        script = Path(__file__).with_name("browser_checks.py")
        out_json = st.dir / "result_raw.json"
        # 🔴 ภาพหน้าจอ **ไม่เก็บในชุดหลักฐาน** (T-05): ไฟล์ไบนารีทำให้ leak_check (ซึ่งถอดไบต์เป็น
        # ข้อความ) เจอรูปแบบปลอมแบบสุ่ม ⇒ ด่าน L ล้มโดยไม่มีสาระ · หลักฐานของขั้นนี้คือ
        # result_raw.json · ภาพถูกเขียนไว้ในโฟลเดอร์ชั่วคราวของ target แล้วลบพร้อมกัน
        shots = self.target_data / "screenshots"
        r = st.run_cmd([py, str(script), "--base", self.target_url, "--files-dir",
                        str(self.target_data / "synthetic_files"), "--out", str(out_json),
                        "--shots", str(shots)], timeout=600)
        st.meta["screenshots_retained"] = False
        if not out_json.exists():
            st.incomplete(b_checks, f"browser script produced no result (exit {r.returncode})")
            st.finish()
            return
        raw = json.loads(out_json.read_text("utf-8"))
        _write_json(out_json, raw)   # กลบเส้นทาง
        st.meta["versions"] = raw.get("versions", {})
        for cid, res in raw.get("checks", {}).items():
            st.checks[cid] = CheckResult(cid, res["status"], res.get("detail", {}),
                                         "steps/browser/result_raw.json")
        for cid in b_checks:
            if cid not in st.checks:
                st.checks[cid] = CheckResult(cid, "INCOMPLETE", {"reason": "not produced"},
                                             "steps/browser/")
        st.finish()

    def step_pip_audit(self):
        st = Step(self, "pip_audit")
        exe = self.args.pip_audit
        if "pip_audit" in self.skip or not exe or not Path(exe).exists():
            st.incomplete(["D:pip_audit"], "pip-audit not available (--pip-audit)")
            st.finish()
            return
        frozen = self.out / "steps" / "environment" / "frozen.txt"
        # pip freeze --all รวม pip/setuptools — ให้ pip-audit ตรวจรายการติดตั้งจริงของ venv ของแอป
        req = st.dir / "audit_input.txt"
        lines = [ln for ln in frozen.read_text("utf-8").splitlines()
                 if "==" in ln and not ln.startswith(("-e", "#"))]
        with open(req, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        raw = st.dir / "raw.json"
        st.meta["tool_version"] = _tool_version([exe, "--version"])
        r = st.run_cmd([exe, "-r", str(req), "--no-deps", "-f", "json", "-o", str(raw),
                        "--progress-spinner", "off"], timeout=900)
        if not raw.exists():
            st.incomplete(["D:pip_audit"], f"no json output (exit {r.returncode})")
            st.finish()
            return
        data = json.loads(raw.read_text("utf-8"))
        _write_json(raw, data)        # เขียนซ้ำเป็น LF + กลบเส้นทาง (เครื่องมือเขียน CRLF บน Windows)
        deps = data.get("dependencies", data if isinstance(data, list) else [])
        vulns = [(d.get("name"), d.get("version"), v.get("id"))
                 for d in deps for v in d.get("vulns", [])]
        input_names = {ln.split("==")[0].strip().lower() for ln in lines}
        audited = [d for d in deps if not d.get("skip_reason")]
        def _norm(n: str) -> str:
            # ชื่อแพ็กเกจตาม PEP 503: `_` `.` `-` เทียบเท่ากัน (T-03)
            return n.lower().replace("_", "-").replace(".", "-")

        audited_names = {_norm(str(d.get("name", ""))) for d in audited}
        # เครื่องมือข้ามบางรายการโดยไม่รายงาน skip_reason (เช่น pip/packaging) — นับจากส่วนต่าง
        skipped = sorted({_norm(n) for n in input_names} - audited_names)
        skipped += [d.get("name") for d in deps if d.get("skip_reason")]
        status = "PASS" if (not vulns and r.returncode == 0 and audited) else (
            "FAIL" if vulns else "INCOMPLETE")
        st.checks["D:pip_audit"] = CheckResult(
            "D:pip_audit", status,
            {"input_packages": len(lines), "audited": len(audited), "skipped": skipped,
             "vulnerabilities": vulns, "exit_code": r.returncode,
             "wording": "ไม่พบช่องโหว่ที่ประกาศไว้ในฐานข้อมูล ณ วันที่รัน (เฉพาะรายการที่ตรวจได้)"},
            "steps/pip_audit/raw.json")
        st.finish()

    # แผน Automation Framework ของ ZAP = เนื้อหาเดียวกับ "baseline scan" (spider + passive rules)
    # 🔴 ไม่มี job activeScan โดยเจตนา · spider ไม่ส่งฟอร์ม (GET-only) · target = loopback สังเคราะห์
    ZAP_PLAN = """env:
  contexts:
    - name: redbook-synthetic
      urls: ['{target}']
      includePaths: ['{target}.*']
  parameters:
    failOnError: true
    failOnWarning: false
    progressToStdout: true
jobs:
  - type: passiveScan-config
    parameters:
      maxAlertsPerRule: 10
      scanOnlyInScope: true
  - type: spider
    parameters:
      context: redbook-synthetic
      url: "{target}"
      maxDuration: 2
      maxDepth: 5
      postForm: false
      parseComments: true
      parseRobotsTxt: false
      parseSitemapXml: false
  - type: passiveScan-wait
    parameters:
      maxDuration: 5
  - type: report
    parameters:
      template: traditional-json
      reportDir: "{out}"
      reportFile: report
      reportTitle: "RedBook Verify Security Gate - ZAP baseline (passive) - synthetic loopback target"
  - type: report
    parameters:
      template: traditional-html
      reportDir: "{out}"
      reportFile: report
      reportTitle: "RedBook Verify Security Gate - ZAP baseline (passive) - synthetic loopback target"
"""

    def step_zap(self, target_ok: bool):
        st = Step(self, "zap")
        zap_home = self.args.zap_home
        zap_cmd = self.args.zap_cmd
        if "zap" in self.skip or not (zap_cmd or zap_home):
            st.incomplete(["Z:zap_baseline"], "ZAP not configured/available (--zap-home or --zap-cmd)")
            st.finish()
            return
        if not target_ok:
            st.incomplete(["Z:zap_baseline"], "target not ready")
            st.finish()
            return
        report_json = st.dir / "report.json"
        env = dict(os.environ)
        if self.args.java_home:
            env["JAVA_HOME"] = self.args.java_home
            env["PATH"] = str(Path(self.args.java_home) / "bin") + os.pathsep + env.get("PATH", "")
        if zap_home:
            jars = sorted(Path(zap_home).glob("zap-*.jar"))
            if not jars:
                st.incomplete(["Z:zap_baseline"], "zap-*.jar not found under --zap-home")
                st.finish()
                return
            java = str(Path(self.args.java_home) / "bin" / "java") if self.args.java_home else "java"
            session_dir = self.target_data / "zap_home"
            session_dir.mkdir(parents=True, exist_ok=True)
            # แผนจริงต้องมีเส้นทางดิบ (ZAP อ่าน) ⇒ เขียนในโฟลเดอร์ชั่วคราว · สำเนาที่กลบแล้วเก็บเป็นหลักฐาน
            plan_text = (self.ZAP_PLAN.replace("{target}", self.target_url)
                         .replace("{out}", str(st.dir).replace("\\", "/")))
            plan = session_dir / "zap_plan.yaml"
            with open(plan, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(plan_text)
            _write(st.dir / "zap_plan.yaml", plan_text)
            # เรียก jar ตรง (zap.bat สะท้อนคำสั่ง batch ปนออกมา และอ้าง jar แบบ relative)
            st.meta["tool_version"] = _zap_version([java, "-jar", jars[-1].name, "-version"],
                                                   Path(zap_home), jars[-1].name)
            st.meta["java_version"] = _tool_version([java, "-version"])
            st.meta["zap_jar_sha256"] = _sha256(jars[-1])
            st.meta["scan_type"] = "Automation Framework: spider (GET-only) + passive rules · no activeScan"
            cmd = [java, "-Xmx1024m", "-jar", jars[-1].name, "-cmd", "-dir", str(session_dir),
                   "-autorun", str(plan), "-silent"]
        else:
            cmd = [c.replace("{target}", self.target_url).replace("{out}", str(st.dir))
                   for c in shlex.split(zap_cmd)]
        # zap.bat อ้าง jar แบบ relative ⇒ ต้องรันจากโฟลเดอร์ของ ZAP เอง
        r = st.run_cmd(cmd, env=env, timeout=3600, cwd=Path(zap_home) if zap_home else None)
        if not report_json.exists():
            st.incomplete(["Z:zap_baseline"], f"no report.json (exit {r.returncode})")
            st.finish()
            return
        data = json.loads(report_json.read_text("utf-8"))
        _write_json(report_json, data)                       # LF + กลบเส้นทาง
        html = st.dir / "report.html"
        if html.exists():
            _write(html, html.read_text("utf-8", errors="replace"))
        counts = {"High": 0, "Medium": 0, "Low": 0, "Informational": 0}
        alerts = []
        for site in data.get("site", []):
            for a in site.get("alerts", []):
                risk = a.get("riskdesc", "").split(" ")[0]
                counts[risk] = counts.get(risk, 0) + 1
                alerts.append({"name": a.get("name"), "risk": risk, "pluginid": a.get("pluginid"),
                               "count": a.get("count")})
        st.checks["Z:zap_baseline"] = CheckResult(
            "Z:zap_baseline", "PASS" if counts["High"] == 0 and counts["Medium"] == 0 else "FAIL",
            {"counts": counts, "alerts": alerts, "exit_code": r.returncode,
             "scan_type": "baseline/passive", "target": "synthetic loopback"},
            "steps/zap/report.json")
        st.finish()

    def step_leak_check(self):
        st = Step(self, "leak_check")
        exe = self.args.leak_check
        if "leak_check" in self.skip or not exe or not Path(exe).exists():
            st.incomplete(["L:evidence_leak_check"], "leak_check.py not provided (--leak-check)")
            st.finish()
            return
        st.meta["tool_version"] = _tool_version([self.python, exe, "--version"]) \
            if "--version" in Path(exe).read_text("utf-8", errors="ignore") else "see stdout header"
        # เขียนไฟล์ผลที่มีอยู่ตอนนี้ก่อน เพื่อให้ตัวตรวจเห็นหลักฐานทุกชิ้นที่จะเผยแพร่
        self._write_outputs(partial=True)
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        r = st.run_cmd([self.python, exe, str(self.out)], env=env, timeout=900)
        status = {0: "PASS", 1: "FAIL", 3: "INCOMPLETE"}.get(r.returncode, "INCOMPLETE")
        st.checks["L:evidence_leak_check"] = CheckResult(
            "L:evidence_leak_check", status,
            {"exit_code": r.returncode, "scanned": str(self.out.name),
             "meaning": {0: "ตรวจครบ 0 hit", 1: "พบ hit", 3: "ตรวจไม่ครบ (fail-closed)"}.get(
                 r.returncode, "ไม่ทราบ"),
             "caveat": "0 hit ≠ ปลอดการเปิดเผย (fingerprint/การประกอบข้อมูลตัวตรวจมองไม่เห็น)"},
            "steps/leak_check/stdout.txt")
        st.finish()

    # ------------------------------------------------------------- outputs
    def _git_fingerprint(self) -> dict:
        def git(*a):
            try:
                return subprocess.run(["git", *a], cwd=str(PROJECT_ROOT), capture_output=True,
                                      text=True, timeout=30).stdout.strip()
            except Exception:  # noqa: BLE001
                return ""
        commit = git("rev-parse", "HEAD")
        return {
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            # 🔴 ไม่เผย commit hash ของ repo private ลงชุดหลักฐานสาธารณะ — ใช้ลายนิ้วมือแทน
            "commit_fingerprint": hashlib.sha256(commit.encode()).hexdigest()[:16] if commit else "",
            "dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
        }

    def _write_outputs(self, partial: bool = False) -> dict:
        statuses = evaluate(self.matrix, self.checks, self.profile, self._dispositions())
        counts = summarize(statuses)
        control_rows = [{"control_id": s.control_id, "status": s.status, "reason": s.reason,
                         "checks": s.checks, "manual_disposition": s.manual_disposition}
                        for s in statuses]
        _write_json(self.out / "control_results.json", {"phase": self.phase, "profile": self.profile,
                                                        "counts": counts, "controls": control_rows})
        manifest = {
            "run_id": self.run_id, "phase": self.phase, "profile": self.profile,
            "started_utc": self.started, "finished_utc": _utc() if not partial else None,
            "security_gate_version": SECURITY_GATE_VERSION, "protocol_version": PROTOCOL_VERSION,
            "asvs_reference": ASVS_VERSION,
            "matrix": {"path_basename": self.matrix.path.name, "sha256": self.matrix.sha256,
                       "controls": len(self.matrix.controls)},
            "target": {"type": "synthetic loopback (runner-managed)", "url": self.target_url,
                       "active_attack": False},
            "system_repo": self._git_fingerprint(),
            "tools": self._tool_versions(),
            "steps": self.steps_meta,
            "counts": counts,
            "checks": {cid: c.status for cid, c in sorted(self.checks.items())},
            "claim_boundary": [
                "ประเมินตาม subset ที่ประกาศล่วงหน้าจาก OWASP ASVS v5.0.0 — ไม่ใช่ 'ผ่าน ASVS'",
                "ไม่ใช่ penetration test · ไม่รับรองว่า 'แฮกไม่ได้'",
                "ผล CVE = ฐานข้อมูล ณ วันที่รัน เฉพาะรายการที่เครื่องมือตรวจได้",
                "control ที่ check ไม่ครบ = REVIEW ไม่ใช่ PASS",
                f"phase = {self.phase}: " + ("ผล formative ห้ามอ้างเป็นผลประเมินสุดท้าย"
                                             if self.phase == "formative" else
                                             "ผลประเมินตาม matrix ที่ประกาศไว้ก่อนรัน"),
            ],
        }
        _write_json(self.out / "SECURITY_RUN_MANIFEST.json", manifest)
        self._write_summary(statuses, counts, manifest)
        if not partial:
            # HASHES ครอบทุกไฟล์ **ยกเว้น** manifest (ซึ่งถูกเขียนซ้ำหลังคำนวณแฮช จึงอยู่ในรายการไม่ได้)
            # และตัว HASHES เอง · manifest บันทึกแฮชของ HASHES แทน ⇒ ตรวจย้อนได้สองชั้น:
            # ``sha256sum -c HASHES.sha256`` แล้วเทียบ sha256(HASHES.sha256) กับค่าใน manifest
            excluded = {"HASHES.sha256", "SECURITY_RUN_MANIFEST.json"}
            hashes = []
            for p in sorted(self.out.rglob("*")):
                if p.is_file() and p.name not in excluded:
                    hashes.append(f"{_sha256(p)}  {p.relative_to(self.out).as_posix()}")
            with open(self.out / "HASHES.sha256", "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(hashes) + "\n")
            manifest["evidence_files"] = len(hashes)
            manifest["hashes_excluded"] = sorted(excluded)
            manifest["hashes_sha256_of_HASHES_file"] = _sha256(self.out / "HASHES.sha256")
            _write_json(self.out / "SECURITY_RUN_MANIFEST.json", manifest)
        return manifest

    def _dispositions(self) -> dict:
        p = self.args.dispositions
        if p and Path(p).exists():
            return json.loads(Path(p).read_text("utf-8"))
        return {}

    def _tool_versions(self) -> dict:
        return {
            "python": sys.version.split()[0],
            "pytest": self.steps_meta.get("pytest", {}).get("pytest_version", ""),
            "httpx": self.steps_meta.get("http_probes", {}).get("httpx_version", ""),
            "playwright": self.steps_meta.get("browser", {}).get("versions", {}).get("playwright", ""),
            "chromium": self.steps_meta.get("browser", {}).get("versions", {}).get("chromium", ""),
            "pip_audit": self.steps_meta.get("pip_audit", {}).get("tool_version", ""),
            "leak_check": self.steps_meta.get("leak_check", {}).get("tool_version", ""),
            "zap": self.steps_meta.get("zap", {}).get("tool_version", ""),
        }

    def _write_summary(self, statuses, counts, manifest):
        by_cat: dict[str, list] = {}
        ctl = self.matrix.by_id()
        for s in statuses:
            by_cat.setdefault(ctl[s.control_id].category, []).append(s)
        lines = [f"# SECURITY RESULT SUMMARY — {self.phase.upper()} · run {self.run_id}", "",
                 f"**profile:** `{self.profile}` · **matrix sha256:** `{self.matrix.sha256[:16]}…` · "
                 f"**protocol:** `{PROTOCOL_VERSION}` · **gate:** `{SECURITY_GATE_VERSION}` · "
                 f"**เริ่ม (UTC):** {self.started}", ""]
        if self.phase == "formative":
            lines += ["> 🔴 **FORMATIVE** — ผลรอบพัฒนา ใช้เพื่อหาและแก้ · **ห้ามอ้างเป็นผลประเมินสุดท้าย**", ""]
        lines += ["## ตัวชี้วัด", "", "| ตัวชี้วัด | ค่า |", "|---|---|",
                  f"| controls ที่ประกาศ | {counts['declared']} |",
                  f"| applicable | {counts['applicable']} |",
                  f"| PASS / FAIL / REVIEW / N/A | {counts['PASS']} / {counts['FAIL']} / {counts['REVIEW']} / {counts['NOT_APPLICABLE']} |"]
        pa = self.checks.get("D:pip_audit")
        lines.append(f"| dependency vulnerabilities (pip-audit) | "
                     f"{len(pa.detail.get('vulnerabilities', [])) if pa and pa.status != 'INCOMPLETE' else 'INCOMPLETE'}"
                     f" · audited {pa.detail.get('audited', '?') if pa else '?'} · skipped {len(pa.detail.get('skipped', [])) if pa else '?'} |")
        lk = self.checks.get("L:evidence_leak_check")
        lines.append(f"| data-leakage (leak_check on evidence) | {lk.status if lk else 'NOT_RUN'} |")
        hl = self.checks.get("H:leak.pages")
        lines.append(f"| data-leakage (absolute paths in pages) | {hl.status if hl else 'NOT_RUN'} · {len(hl.detail.get('leaks', [])) if hl else '?'} หน้า |")
        pt = self.steps_meta.get("pytest", {}).get("summary", {})
        lines.append(f"| security regression tests | passed {pt.get('passed', '?')} · failed {pt.get('failed', '?')} · error {pt.get('error', '?')} · skipped {pt.get('skipped', '?')} |")
        bz = [c for c in self.checks if c.startswith("B:")]
        lines.append(f"| browser checks | " + " · ".join(f"{c[2:]}={self.checks[c].status}" for c in sorted(bz)) + " |")
        z = self.checks.get("Z:zap_baseline")
        if z and z.status != "INCOMPLETE":
            c = z.detail.get("counts", {})
            lines.append(f"| ZAP baseline alerts H/M/L/I | {c.get('High', 0)}/{c.get('Medium', 0)}/{c.get('Low', 0)}/{c.get('Informational', 0)} |")
        else:
            lines.append(f"| ZAP baseline | INCOMPLETE — {z.detail.get('reason', '') if z else 'not run'} |")
        unresolved = [s for s in statuses if s.status == "FAIL"]
        lines.append(f"| unresolved FAIL controls | {len(unresolved)} |")
        lines += ["", "## สถานะราย control", ""]
        for cat in sorted(by_cat, key=lambda k: int(k.split(" ")[0])):
            lines += [f"### {cat}", "", "| control | ASVS | สถานะ | เหตุผล |", "|---|---|---|---|"]
            for s in by_cat[cat]:
                c = ctl[s.control_id]
                lines.append(f"| {s.control_id} | {c.asvs_ref} (L{c.asvs_level}) | **{s.status}** | {s.reason} |")
            lines.append("")
        lines += ["## ขอบเขตการอ้าง", ""] + [f"- {b}" for b in manifest["claim_boundary"]] + [""]
        _write(self.out / "SECURITY_RESULT_SUMMARY.md", "\n".join(lines))

    # ------------------------------------------------------------- main
    def run(self) -> int:
        self.started = _utc()
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{self.phase}"
        self.out.mkdir(parents=True, exist_ok=True)
        _write_json(self.out / "RUN_START.json", {"run_id": self.run_id, "phase": self.phase,
                                                   "profile": self.profile,
                                                   "matrix_sha256": self.matrix.sha256,
                                                   "started_utc": self.started})
        target_ok = False
        try:
            self.step_environment()
            self.step_pytest()
            target_ok = self.step_target() if "target" not in self.skip else False
            self.step_http_probes(target_ok)
            self.step_browser(target_ok)
            self.step_zap(target_ok)
        finally:
            self.stop_target()
        self.step_pip_audit()
        self.step_leak_check()
        manifest = self._write_outputs()
        shutil.rmtree(self.target_data, ignore_errors=True)
        c = manifest["counts"]
        print(f"[security-gate] {self.phase} · declared {c['declared']} · applicable {c['applicable']} · "
              f"PASS {c['PASS']} · FAIL {c['FAIL']} · REVIEW {c['REVIEW']} · N/A {c['NOT_APPLICABLE']}")
        print(f"[security-gate] evidence: {self.out}")
        return 0 if c["FAIL"] == 0 else 1


def _inside_git_worktree(path: Path) -> bool:
    for parent in [path] + list(path.parents):
        if (parent / ".git").exists():
            return True
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="RedBook Verify — Web Security Verification Gate runner")
    ap.add_argument("--matrix", required=True, help="SECURITY_CONTROL_MATRIX.csv (predeclared)")
    ap.add_argument("--out", required=True, help="โฟลเดอร์หลักฐาน (ต้องอยู่นอก git work tree)")
    ap.add_argument("--phase", choices=("formative", "final"), required=True)
    ap.add_argument("--profile", choices=PROFILES, default=DEFAULT_PROFILE)
    ap.add_argument("--leak-check", default="", help="path ของ leak_check.py (repo สาธารณะ)")
    ap.add_argument("--pip-audit", default="", help="path ของ pip-audit executable (venv แยก)")
    ap.add_argument("--browser-python", default="", help="python ที่มี playwright + chromium")
    ap.add_argument("--zap-home", default="",
                    help="โฟลเดอร์ ZAP (cross-platform package) — runner สร้างแผน Automation Framework "
                         "spider GET-only + passive แล้วเรียก zap.bat -cmd -autorun เอง")
    ap.add_argument("--java-home", default="", help="JAVA_HOME สำหรับ ZAP (JRE 17+)")
    ap.add_argument("--zap-cmd", default="",
                    help="ทางเลือก: คำสั่ง ZAP เอง · ใช้ {target} และ {out} ได้ · ต้องเขียน {out}/report.json")
    ap.add_argument("--dispositions", default="", help="json ของ disposition ที่คนตัดสิน")
    ap.add_argument("--skip", default="", help="step ที่จะข้าม (คั่นด้วย ,) — ถูกบันทึกเป็น INCOMPLETE")
    ap.add_argument("--allow-in-worktree", action="store_true")
    args = ap.parse_args(argv)
    out = Path(args.out).resolve()
    if _inside_git_worktree(out) and not args.allow_in_worktree:
        print("🔴 --out อยู่ใน git work tree — ย้ายไปนอก repo (หรือใส่ --allow-in-worktree เฉพาะทดสอบ)")
        return 2
    return Runner(args).run()


if __name__ == "__main__":
    sys.exit(main())
