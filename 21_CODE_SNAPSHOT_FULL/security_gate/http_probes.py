# -*- coding: utf-8 -*-
"""HTTP probes — ตรวจ header · cookie · method · path · CSRF · host กับ target ที่รันอยู่จริง

ทุก probe เป็นคำขอแบบ **passive/บันทึกผล** ต่อ target บน loopback ที่ runner เปิดเอง
(ข้อมูลสังเคราะห์) · ไม่มีการเดา credential · ไม่มี payload ที่ตั้งใจทำลาย · ไม่ยิงซ้ำจำนวนมาก

ผลลัพธ์คือ ``dict[check_id, CheckResult]`` ที่ ``check_id`` ตรงกับคอลัมน์ ``test_method``
(คำนำหน้า ``H:``) ของ matrix · ทุก check เก็บหลักฐานต่อคำขอ (URL · method · status · header
ที่เกี่ยว) เพื่อให้ตรวจย้อนได้โดยไม่ต้องรันใหม่
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

from .evaluate import CheckResult

#: หน้า HTML สาธารณะที่ไม่ต้องมีรหัสงาน
PUBLIC_HTML_PATHS = ("/", "/queue", "/preflight", "/export", "/t1b/runs", "/indicators/runs",
                     "/rules", "/audit", "/projects/new")
JSON_PATHS = ("/healthz",)
STATIC_PATHS = ("/static/app.css", "/static/favicon.svg")
NOT_FOUND_PATHS = ("/nope", "/projects/doesnotexist", "/runs/doesnotexist",
                   "/t1b/runs/doesnotexist", "/files/doesnotexist/structure",
                   "/indicators/runs/doesnotexist")
SOURCE_CONTROL_PATHS = ("/.git/HEAD", "/.git/config", "/app.py", "/redbook/app.py",
                        "/requirements.txt", "/.env", "/run_local.py", "/config.py")
DIR_LISTING_PATHS = ("/static", "/static/")
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
TRAVERSAL_PATHS = ("/static/..%2f..%2fapp.py", "/static/../../redbook/app.py",
                   "/static/..%5c..%5capp.py", "/t1b/exports/..%5c..%5cx",
                   "/t1b/exports/%2e%2e/x", "/t1b/exports/exp_..%2f..%2fx",
                   "/indicators/exports/..%2fx", "/indicators/runs/x/exports/..%2fx",
                   "/evidence/..%2f..%2fx/file")
UNUSED_METHODS = ("TRACE", "PUT", "PATCH", "DELETE", "OPTIONS")
METHOD_TARGETS = ("/", "/projects/new", "/healthz")

CSP_REQUIRED = ("default-src 'none'", "object-src 'none'", "base-uri 'none'",
                "frame-ancestors 'none'")
REFERRER_OK = {"same-origin", "strict-origin", "no-referrer", "strict-origin-when-cross-origin"}

#: รูปแบบที่ **ห้าม** ปรากฏใน body ของหน้าข้อผิดพลาด
UNSAFE_BODY_PATTERNS = (
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r'File "[^"]+", line \d+'),
    re.compile(r"site-packages"),
    re.compile(r"sqlite3\."),
    re.compile(r"\b[A-Za-z]+(?:Error|Exception)\b:"),
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:\\"),
    re.compile(r"/(?:home|Users)/"),
    re.compile(r"REDBOOK_[A-Z_]+"),
    re.compile(r"\.venv"),
)
#: รูปแบบเส้นทางสัมบูรณ์ในหน้า 200 (ข้อ leak.pages)
ABS_PATH_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:\\[^\s<\"']+"),
    re.compile(r"\\\\[^\s<\"']+\\[^\s<\"']+"),
    re.compile(r"/(?:home|Users)/[^\s<\"']+"),
)
META_REFERRER = re.compile(r'<meta\s+name="referrer"\s+content="([^"]+)"', re.I)
PROJECT_LINK = re.compile(r'href="/projects/([0-9a-f]{8,})"')


@dataclass
class Probe:
    method: str
    path: str
    status: int
    headers: dict
    body_excerpt: str = ""
    note: str = ""


@dataclass
class ProbeLog:
    base_url: str
    probes: list[Probe] = field(default_factory=list)

    def add(self, r: httpx.Response, note: str = "", keep_body: int = 0) -> Probe:
        keep = {k.lower(): v for k, v in r.headers.items()
                if k.lower() in ("content-type", "content-security-policy", "x-frame-options",
                                 "x-content-type-options", "referrer-policy", "cache-control",
                                 "server", "set-cookie", "content-disposition", "allow",
                                 "cross-origin-opener-policy", "cross-origin-resource-policy",
                                 "permissions-policy", "strict-transport-security",
                                 "access-control-allow-origin", "content-length")}
        p = Probe(r.request.method, str(r.request.url.raw_path, "ascii", "replace")
                  if hasattr(r.request.url, "raw_path") else str(r.request.url),
                  r.status_code, keep, r.text[:keep_body] if keep_body else "", note)
        self.probes.append(p)
        return p

    def to_dict(self) -> dict:
        return {"base_url": self.base_url,
                "probes": [{"method": p.method, "path": p.path, "status": p.status,
                            "headers": p.headers, "note": p.note} for p in self.probes]}


def _html(r: httpx.Response) -> bool:
    return r.headers.get("content-type", "").startswith("text/html")


def run_probes(base_url: str, timeout: float = 15.0) -> tuple[dict[str, CheckResult], ProbeLog]:
    log = ProbeLog(base_url=base_url)
    out: dict[str, CheckResult] = {}
    client = httpx.Client(base_url=base_url, timeout=timeout, follow_redirects=False)
    responses: list[tuple[str, httpx.Response]] = []

    def get(path, **kw):
        r = client.get(path, **kw)
        responses.append((path, r))
        log.add(r)
        return r

    # ---- ครั้งแรก: หน้าแรกเพื่อรับคุกกี้ CSRF
    first = get("/")
    cookie_header = first.headers.get("set-cookie", "")
    csrf_cookie = client.cookies.get("redbook_csrf")

    # ---- หน้า HTML สาธารณะ + ตามลิงก์งานตรวจ (ข้อมูลสังเคราะห์) อีกชั้นหนึ่ง
    html_pages = [first]
    for path in PUBLIC_HTML_PATHS[1:]:
        html_pages.append(get(path))
    for pid in PROJECT_LINK.findall(first.text)[:2]:
        html_pages.append(get(f"/projects/{pid}"))
    json_pages = [get(p) for p in JSON_PATHS]
    static_pages = [get(p) for p in STATIC_PATHS]
    not_found = [get(p) for p in NOT_FOUND_PATHS]
    all_resp = [r for _, r in responses]

    # ---- CSP
    bad = [(p, r.status_code) for p, r in responses
           if not all(d in r.headers.get("content-security-policy", "") for d in CSP_REQUIRED)]
    out["H:headers.csp"] = CheckResult("H:headers.csp", "FAIL" if bad else "PASS",
                                       {"required": list(CSP_REQUIRED), "missing_on": bad,
                                        "checked": len(responses)})
    # ---- nosniff
    bad = [(p, r.status_code) for p, r in responses
           if r.headers.get("x-content-type-options", "").lower() != "nosniff"]
    out["H:headers.nosniff"] = CheckResult("H:headers.nosniff", "FAIL" if bad else "PASS",
                                           {"missing_on": bad, "checked": len(responses)})
    # ---- frame
    bad = [str(r.request.url.path) for r in html_pages
           if "frame-ancestors 'none'" not in r.headers.get("content-security-policy", "")
           or r.headers.get("x-frame-options", "").upper() != "DENY"]
    out["H:headers.frame"] = CheckResult("H:headers.frame", "FAIL" if bad else "PASS",
                                         {"missing_on": bad, "checked": len(html_pages)})
    # ---- COOP
    bad = [str(r.request.url.path) for r in html_pages
           if r.headers.get("cross-origin-opener-policy", "") not in
           ("same-origin", "same-origin-allow-popups")]
    out["H:headers.coop"] = CheckResult("H:headers.coop", "FAIL" if bad else "PASS",
                                        {"missing_on": bad, "checked": len(html_pages)})
    # ---- Cache-Control no-store
    bad = [(p, r.status_code) for p, r in responses
           if "no-store" not in r.headers.get("cache-control", "").lower()]
    out["H:headers.cache"] = CheckResult("H:headers.cache", "FAIL" if bad else "PASS",
                                         {"missing_on": bad, "checked": len(responses)})
    # ---- Referrer-Policy + meta สอดคล้อง
    ref_bad, meta_mismatch = [], []
    for r in html_pages:
        hdr = r.headers.get("referrer-policy", "").lower()
        if hdr not in REFERRER_OK:
            ref_bad.append((str(r.request.url.path), hdr))
        m = META_REFERRER.search(r.text)
        if m and m.group(1).lower() != hdr:
            meta_mismatch.append((str(r.request.url.path), hdr, m.group(1)))
    out["H:headers.referrer"] = CheckResult(
        "H:headers.referrer", "FAIL" if (ref_bad or meta_mismatch) else "PASS",
        {"header_not_restrictive": ref_bad, "meta_mismatch": meta_mismatch,
         "note": "meta referrer ที่ต่างจากหัว HTTP ทำให้เบราว์เซอร์ใช้นโยบายของ meta — "
                 "ต้องสอดคล้องกันจึงจะอ้างได้ว่านโยบายที่ประกาศคือนโยบายที่ใช้จริง"})
    # ---- CORS: ไม่มี ACAO แม้ส่ง Origin ภายนอก
    r_cors = client.get("/", headers={"Origin": "https://evil.example"})
    log.add(r_cors, "Origin: https://evil.example")
    acao = [str(r.request.url.path) for r in all_resp + [r_cors]
            if "access-control-allow-origin" in r.headers]
    out["H:headers.cors"] = CheckResult("H:headers.cors", "FAIL" if acao else "PASS",
                                        {"acao_present_on": acao})
    # ---- Content-Type
    bad = []
    for p, r in responses:
        ct = r.headers.get("content-type", "")
        if r.status_code != 204 and r.content and not ct:
            bad.append((p, "no content-type"))
        elif ct.startswith("text/") and "charset=" not in ct.lower():
            bad.append((p, ct))
    for r in json_pages:
        if not r.headers.get("content-type", "").startswith("application/json"):
            bad.append((str(r.request.url.path), r.headers.get("content-type", "")))
    out["H:headers.content_type"] = CheckResult("H:headers.content_type",
                                                "FAIL" if bad else "PASS", {"bad": bad})
    # ---- Server header (ไม่เปิดเผยผลิตภัณฑ์/รุ่น)
    servers = sorted({r.headers.get("server", "") for r in all_resp})
    disclosing = [s for s in servers if s]
    out["H:headers.server"] = CheckResult("H:headers.server", "FAIL" if disclosing else "PASS",
                                          {"server_values": servers})
    # ---- HSTS (บันทึกอย่างเดียว — บังคับเฉพาะ profile TLS)
    out["H:headers.hsts_recorded"] = CheckResult(
        "H:headers.hsts_recorded", "RECORDED",
        {"present_on_first_page": "strict-transport-security" in first.headers,
         "value": first.headers.get("strict-transport-security", "")})
    # ---- Cookie flags
    low = cookie_header.lower()
    flags = {"httponly": "httponly" in low, "samesite_strict": "samesite=strict" in low,
             "path_root": "path=/" in low, "secure": "secure" in low.split(";") or "; secure" in low,
             "host_prefix": cookie_header.strip().startswith("__Host-")}
    out["H:cookie.flags"] = CheckResult(
        "H:cookie.flags",
        "PASS" if (flags["httponly"] and flags["samesite_strict"] and flags["path_root"]) else "FAIL",
        {"set_cookie_attributes_only": re.sub(r"=[^;]*", "=<redacted>", cookie_header, count=1),
         **flags})
    out["H:cookie.secure_recorded"] = CheckResult("H:cookie.secure_recorded", "RECORDED",
                                                  {"secure": flags["secure"],
                                                   "host_prefix": flags["host_prefix"]})
    # ---- methods
    bad, trace_echo = [], []
    for path in METHOD_TARGETS:
        for m in UNUSED_METHODS:
            r = client.request(m, path, headers={"X-Probe-Echo": "zapline-9f1"})
            log.add(r, "unused method")
            if r.status_code not in (404, 405) or not _safe_body(r.text):
                bad.append((m, path, r.status_code))
            if m == "TRACE" and "zapline-9f1" in r.text:
                trace_echo.append(path)
            if r.headers.get("x-content-type-options", "").lower() != "nosniff":
                bad.append((m, path, "missing security headers"))
    out["H:methods.blocked"] = CheckResult("H:methods.blocked",
                                           "FAIL" if (bad or trace_echo) else "PASS",
                                           {"bad": bad, "trace_echo": trace_echo,
                                            "methods": list(UNUSED_METHODS)})
    # ---- paths
    def _paths_check(check_id, paths, ok):
        bad = []
        for p in paths:
            r = client.get(p)
            log.add(r, check_id)
            if not ok(r):
                bad.append((p, r.status_code))
        out[check_id] = CheckResult(check_id, "FAIL" if bad else "PASS",
                                    {"paths": list(paths), "bad": bad})

    _paths_check("H:paths.traversal", TRAVERSAL_PATHS,
                 lambda r: r.status_code in (400, 404) and _safe_body(r.text))
    _paths_check("H:paths.sourcecontrol", SOURCE_CONTROL_PATHS,
                 lambda r: r.status_code == 404)
    _paths_check("H:paths.dirlisting", DIR_LISTING_PATHS,
                 lambda r: r.status_code != 200 or "app.css" not in r.text)
    _paths_check("H:paths.docs", DOCS_PATHS, lambda r: r.status_code == 404)

    # ---- error bodies ปลอดภัย
    unsafe = []
    err_resps = list(not_found)
    r_mal = client.post("/projects/new", content=b"\xff\xfe\x00garbage",
                        headers={"Content-Type": "multipart/form-data; boundary=zz"})
    log.add(r_mal, "malformed multipart")
    err_resps.append(r_mal)
    r_json = client.post("/projects/new", json={"a": 1})
    log.add(r_json, "json body to form route")
    err_resps.append(r_json)
    r_long = client.get("/projects/" + "a" * 3000)
    log.add(r_long, "very long id")
    err_resps.append(r_long)
    for r in err_resps:
        if r.status_code >= 500 or not _safe_body(r.text):
            unsafe.append((str(r.request.url.path)[:60], r.status_code,
                           _unsafe_reasons(r.text)))
    out["H:error.safe"] = CheckResult("H:error.safe", "FAIL" if unsafe else "PASS",
                                      {"checked": len(err_resps), "unsafe": unsafe})

    # ---- CSRF
    r_no = client.post("/projects/new", data={"name": "probe", "mode": "before_after_reduction"})
    log.add(r_no, "no token")
    out["H:csrf.no_token"] = CheckResult("H:csrf.no_token",
                                         "PASS" if r_no.status_code == 403 else "FAIL",
                                         {"status": r_no.status_code})
    cross = []
    for hdr in ({"Origin": "https://evil.example"}, {"Referer": "https://evil.example/x"}):
        r = client.post("/projects/new", data={"name": "probe", "mode": "before_after_reduction",
                                                "csrf_token": csrf_cookie or ""}, headers=hdr)
        log.add(r, "cross-site " + next(iter(hdr)))
        cross.append((next(iter(hdr)), r.status_code))
    json_ok = r_json.status_code in (400, 403, 415, 422)
    out["H:csrf.cross_origin"] = CheckResult(
        "H:csrf.cross_origin",
        "PASS" if all(s == 403 for _, s in cross) and json_ok else "FAIL",
        {"cross": cross, "json_body_status": r_json.status_code})

    # ---- Host header allowlist (DNS rebinding)
    r_host = client.get("/", headers={"Host": "evil.example"})
    log.add(r_host, "Host: evil.example")
    r_host_port = client.get("/", headers={"Host": "evil.example:8600"})
    log.add(r_host_port, "Host: evil.example:8600")
    ok = all(r.status_code in (400, 403, 421) and _safe_body(r.text) for r in (r_host, r_host_port))
    out["H:host.allowlist"] = CheckResult("H:host.allowlist", "PASS" if ok else "FAIL",
                                          {"evil_host_status": r_host.status_code,
                                           "evil_host_port_status": r_host_port.status_code})

    # ---- leak.pages: หน้า 200 ไม่มีเส้นทางสัมบูรณ์
    leaks = []
    for r in html_pages + json_pages:
        if r.status_code == 200:
            for pat in ABS_PATH_PATTERNS:
                if pat.search(r.text):
                    leaks.append((str(r.request.url.path), pat.pattern[:30]))
                    break
    out["H:leak.pages"] = CheckResult("H:leak.pages", "FAIL" if leaks else "PASS",
                                      {"pages_checked": len(html_pages) + len(json_pages),
                                       "leaks": leaks})

    # ---- healthz minimal
    hz = json_pages[0]
    try:
        keys = sorted(hz.json().keys())
    except Exception:  # noqa: BLE001
        keys = ["<not json>"]
    extra = [k for k in keys if k not in ("status", "app", "version")]
    out["H:healthz.minimal"] = CheckResult("H:healthz.minimal", "FAIL" if extra else "PASS",
                                           {"keys": keys, "extra": extra})
    client.close()
    return out, log


def _unsafe_reasons(text: str) -> list[str]:
    return [p.pattern[:40] for p in UNSAFE_BODY_PATTERNS if p.search(text)]


def _safe_body(text: str) -> bool:
    return not _unsafe_reasons(text)


__all__ = ["run_probes", "ProbeLog", "Probe", "UNSAFE_BODY_PATTERNS", "CSP_REQUIRED"]
