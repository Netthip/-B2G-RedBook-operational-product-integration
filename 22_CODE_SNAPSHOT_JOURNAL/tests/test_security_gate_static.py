# -*- coding: utf-8 -*-
"""Security gate — ตรวจเชิงสถิตจากซอร์ส (ไม่ต้องรันเว็บ)

ตรวจ *สิ่งที่โค้ดเขียนไว้* ไม่ใช่พฤติกรรม — ใช้คู่กับชุด HTTP · ข้อจำกัด: heuristic ตามรูปแบบข้อความ
"""
import re
from pathlib import Path

from redbook import config
from redbook.app import STATIC_DIR

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = (PROJECT_ROOT / "redbook" / "app.py").read_text("utf-8")
HANDLER_SPLIT = re.compile(r"(?=\n    @app\.(?:get|post|put|delete|patch|api_route)\()")


def _handlers(kind: str) -> list[tuple[str, str]]:
    out = []
    for part in HANDLER_SPLIT.split(APP_SRC):
        m = re.match(r'\n    @app\.%s\("([^"]+)"' % kind, part)
        if m:
            out.append((m.group(1), part))
    return out


def _py_files(exclude_prefixes=()):
    for p in (PROJECT_ROOT / "redbook").rglob("*.py"):
        rel = p.relative_to(PROJECT_ROOT).as_posix()
        if "__pycache__" in rel or any(rel.startswith(x) for x in exclude_prefixes):
            continue
        yield rel, p.read_text("utf-8", errors="replace")


def test_every_post_handler_verifies_csrf():
    posts = _handlers("post")
    assert len(posts) >= 20
    missing = [path for path, body in posts if "verify_csrf(" not in body]
    assert not missing, f"POST handler ที่ไม่เรียก verify_csrf: {missing}"


def test_no_get_handler_mutates_state():
    markers = ("save_stream(", "attach_file(", "create_project(", "delete_project(",
               "delete_stored(", "record_", ".seal(", ".freeze(", "write_export(",
               "INSERT ", "UPDATE ", "DELETE FROM")
    offenders = [(path, [m for m in markers if m in body]) for path, body in _handlers("get")
                 if any(m in body for m in markers)]
    assert not offenders, f"GET handler ที่มีคำสั่งเปลี่ยนสถานะ: {offenders}"


def test_jinja_autoescape_is_enabled():
    assert "templates.env.autoescape = True" in APP_SRC
    assert "autoescape = False" not in APP_SRC
    assert "|safe" not in "".join(p.read_text("utf-8") for p in
                                  (PROJECT_ROOT / "redbook" / "templates").rglob("*.html")) \
        or True  # |safe อาจมีใช้โดยเจตนา — รายงานผ่าน test ถัดไปแทน


def test_templates_use_safe_filter_only_on_system_generated_values():
    uses = []
    for p in (PROJECT_ROOT / "redbook" / "templates").rglob("*.html"):
        for i, line in enumerate(p.read_text("utf-8").splitlines(), 1):
            if "|safe" in line or "| safe" in line or "autoescape false" in line.lower():
                uses.append(f"{p.name}:{i}")
    # รายการอนุญาต: ต้องว่าง — ถ้ามีการใช้ |safe ใหม่ ให้เพิ่มพร้อมเหตุผลที่นี่หลังทบทวน
    allowlisted: set[str] = set()
    assert set(uses) <= allowlisted, f"พบ |safe นอกรายการอนุญาต: {uses}"


DYNAMIC_SQL = re.compile(r"execute\(\s*(?:f[\"']|\"[^\"]*\"\s*%|'[^']*'\s*%|[^)]*\.format\()")
#: SQL ที่ประกอบสตริงซึ่งทบทวนแล้วว่าใช้เฉพาะตัวระบุคงที่ (schema migration) — ไม่มีอินพุตผู้ใช้
DYNAMIC_SQL_ALLOWLIST = {
    ("redbook/indicators/registry.py", 'execute(f"PRAGMA table_info({table})"'),
    ("redbook/indicators/registry.py", 'execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}"'),
    ("redbook/indicators/registry.py", 'execute("PRAGMA table_info(%s)" % table'),
    ("redbook/indicators/registry.py", 'execute("SELECT %s FROM ind_runs WHERE id = ?" % col_sql'),
    ("redbook/indicators/registry.py", 'execute("SELECT %s FROM %s WHERE run_id = ?" % (col_sql, table'),
}


def test_dynamic_sql_only_in_allowlisted_schema_code():
    found = set()
    for rel, text in _py_files(exclude_prefixes=()):
        for line in text.splitlines():
            if DYNAMIC_SQL.search(line):
                frag = line.strip()[line.strip().find("execute("):]
                found.add((rel, frag.rstrip("]}),")))
    new = found - DYNAMIC_SQL_ALLOWLIST
    assert not new, f"พบ SQL ประกอบสตริงนอกรายการอนุญาต: {sorted(new)}"


DANGEROUS = re.compile(r"\beval\(|\bexec\(|os\.system\(|subprocess\.|shell=True|\bpickle\b|"
                       r"yaml\.load\(|\bmarshal\b|__import__\(")


def test_no_dangerous_dynamic_execution():
    hits = [(rel, i) for rel, text in _py_files(exclude_prefixes=())
            for i, line in enumerate(text.splitlines(), 1)
            if DANGEROUS.search(line) and not line.strip().startswith("#")]
    assert not hits, f"พบการเรียกใช้ที่อันตรายใน redbook/: {hits}"


ALLOWED_PATH_PARAMS = {"pid", "rid", "fid", "document_id", "page_no", "run_id", "mapping_id",
                       "file_id", "name"}


def test_route_path_params_are_system_ids_only():
    params = set(re.findall(r'@app\.(?:get|post)\("[^"]*\{(\w+)\}', APP_SRC))
    assert params, "ไม่พบพารามิเตอร์เส้นทางเลย — รูปแบบ regex อาจล้าสมัย"
    assert params <= ALLOWED_PATH_PARAMS, f"พารามิเตอร์เส้นทางนอกรายการ: {params - ALLOWED_PATH_PARAMS}"


def test_upload_dir_is_outside_static_and_not_mounted():
    static = STATIC_DIR.resolve()
    for d in (config.UPLOAD_DIR, config.TEMP_DIR, config.EXPORT_DIR):
        assert static not in d.resolve().parents and d.resolve() != static
    mounts = re.findall(r"app\.mount\(\s*\"([^\"]+)\"", APP_SRC)
    assert mounts == ["/static"], mounts
    assert "StaticFiles(directory=str(STATIC_DIR))" in APP_SRC


TAG_RE = re.compile(r"<[a-zA-Z][^<>]*>")
ATTR_RE = re.compile(r"""([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*("[^"]*"|'[^']*'|[^\s"'>]+)""")


def test_no_unquoted_attribute_interpolation_in_templates():
    """attribute context ปลอดภัยด้วย autoescape ก็ต่อเมื่อค่าอยู่ **ในเครื่องหมายคำพูด** —
    ``value={{ x }}`` (ไม่มี quote) ให้ผู้ใช้เติม attribute ใหม่ด้วยช่องว่างได้แม้ escape แล้ว"""
    offenders = []
    for p in (PROJECT_ROOT / "redbook" / "templates").rglob("*.html"):
        text = p.read_text("utf-8")
        for m in TAG_RE.finditer(text):
            tag = m.group(0)
            if "{{" not in tag:
                continue
            for a in ATTR_RE.finditer(tag):
                value = a.group(2)
                if "{{" in value and value[0] not in "\"'":
                    offenders.append(f"{p.name}: {a.group(0)[:60]}")
    assert not offenders, f"attribute ที่ไม่มี quote รอบค่าจาก template: {offenders}"


def test_no_event_handler_or_javascript_url_built_from_templates():
    """ไม่มี on*= หรือ href=javascript: ใน template เลย — จึงไม่มีจุดที่ค่าผู้ใช้จะถูกใส่ใน handler context"""
    offenders = []
    for p in (PROJECT_ROOT / "redbook" / "templates").rglob("*.html"):
        for i, line in enumerate(p.read_text("utf-8").splitlines(), 1):
            if re.search(r"\son[a-z]+\s*=", line, re.I) or re.search(r"javascript:", line, re.I):
                offenders.append(f"{p.name}:{i}")
    assert not offenders, offenders


EXTERNAL = re.compile(r"(?:src|href|url)\s*[=(]\s*[\"']?\s*(https?:)?//", re.I)


def test_templates_reference_no_external_resources():
    hits = []
    for p in list((PROJECT_ROOT / "redbook" / "templates").rglob("*.html")) + \
            list((PROJECT_ROOT / "redbook" / "static").rglob("*.css")):
        for i, line in enumerate(p.read_text("utf-8").splitlines(), 1):
            if EXTERNAL.search(line):
                hits.append(f"{p.name}:{i}")
    assert not hits, f"อ้างทรัพยากรภายนอก: {hits}"


def test_no_authentication_or_session_mechanism_exists():
    """เงื่อนไข NOT_APPLICABLE ของ V6/V7 ต้องยังเป็นจริง — ถ้าข้อนี้ล้ม แปลว่า matrix ต้องขึ้นรุ่นใหม่"""
    joined = "\n".join(text for _, text in _py_files(exclude_prefixes=()))
    assert "SessionMiddleware" not in joined
    assert not re.search(r"def\s+(login|logout|authenticate)\b", joined)
    cookies = re.findall(r"set_cookie\(\s*(\w+)", joined)
    assert set(cookies) <= {"CSRF_COOKIE"}, f"มีคุกกี้นอกจาก CSRF: {cookies}"
