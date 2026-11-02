# -*- coding: utf-8 -*-
"""ทดสอบข้อกำหนดเชิงสถาปัตยกรรม: ฝ่ายตรวจต้องไม่มีตรรกะฝ่ายสร้างไฟล์

เหตุผล: ถ้าเครื่องมือสร้างไฟล์กับเครื่องมือตรวจไฟล์ใช้ตรรกะร่วมกัน
ความผิดพลาดชุดเดียวจะเกิดพร้อมกันทั้งสองฝั่ง และการตรวจจะมองไม่เห็นข้อผิดพลาดนั้น
แพ็กเกจนี้จึงต้องไม่มีโค้ดที่เขียนหรือสร้างไฟล์เอกสาร
"""
import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "redbook"

FORBIDDEN_CALLS = {"save", "save_workbook"}
FORBIDDEN_IMPORTS = {"bis_p1_engine", "p1_features", "p1_sheet4",
                     "synthetic_p1_case_builder", "make_synthetic_bis1010",
                     # เครื่องมือสร้างชุดทดสอบแบบควบคุม — อยู่นอกแพ็กเกจตรวจโดยตั้งใจ
                     "msetgen", "make_mset"}


def _python_files():
    return sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in str(p))


def test_no_workbook_save_calls_anywhere_in_package():
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in FORBIDDEN_CALLS:
                    offenders.append(f"{path.name}:{node.lineno} .{node.func.attr}()")
    assert not offenders, (
        "แพ็กเกจฝ่ายตรวจต้องไม่เรียกคำสั่งบันทึกไฟล์เอกสาร: " + ", ".join(offenders))


def test_does_not_import_document_builder_modules():
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                if n.split(".")[-1] in FORBIDDEN_IMPORTS:
                    offenders.append(f"{path.name}:{node.lineno} {n}")
    assert not offenders, "ห้าม import โมดูลฝั่งสร้างไฟล์: " + ", ".join(offenders)


def test_readers_open_files_read_only():
    """ทุกคำสั่ง open() ในชั้นตัวอ่านต้องเป็นโหมดอ่านเท่านั้น"""
    offenders = []
    for path in sorted((PACKAGE / "readers").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open":
                mode = None
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = kw.value.value
                if mode is None or any(ch in str(mode) for ch in ("w", "a", "x", "+")):
                    offenders.append(f"{path.name}:{node.lineno} mode={mode!r}")
    assert not offenders, "ตัวอ่านไฟล์ต้องเปิดไฟล์แบบอ่านอย่างเดียว: " + ", ".join(offenders)


def test_no_outbound_network_libraries():
    """ระบบต้อง local-first: ห้ามมีไลบรารีเรียกออกอินเทอร์เน็ตในแพ็กเกจ"""
    banned = {"requests", "httpx", "urllib", "urllib3", "socket", "smtplib", "ftplib"}
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                if n.split(".")[0] in banned:
                    offenders.append(f"{path.name}:{node.lineno} {n}")
    assert not offenders, "ห้ามใช้ไลบรารีเครือข่ายในแพ็กเกจ: " + ", ".join(offenders)


# ══════════════════════════════════════════════════════════════════════════════
#  B4 (Pass 3) — ขั้นจัดทำเฉลยต้องไม่กินผลลัพธ์ของ detector
# ══════════════════════════════════════════════════════════════════════════════
#
# 🔴 Bo (`5600162467`) — การเลือกคู่เป็นส่วนหนึ่งของผลลัพธ์ที่กำลังถูกประเมิน ⇒ ถ้าหน้า
# จัดทำเฉลยยังอ่านคู่ที่เครื่องเสนอ (แม้จะซ่อนสถานะแล้ว) เฉลยก็ยังถูกชี้นำได้

#: handler ของขั้นเฉลยใน ``redbook/app.py`` — ห้ามเรียกสิ่งที่ประกอบผลของ detector
_KEYBUILD_HANDLERS = {"_keybuild_page", "indicator_keybuild",
                      "indicator_source_item", "indicator_source_retract",
                      "indicator_key_universe_build", "indicator_key_universe_freeze",
                      "indicator_key_answer", "indicator_key_seal"}
#: ชื่อที่แปลว่า "กำลังอ่านผลของ detector"
_DETECTOR_NAMES = {"run_view", "pair_view", "mappings", "key_build_rows"}


def _function_nodes(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def test_key_build_handlers_never_read_detector_output():
    app_py = PACKAGE / "app.py"
    tree = ast.parse(app_py.read_text(encoding="utf-8"), filename=str(app_py))
    seen = set()
    offenders = []
    for node in _function_nodes(tree):
        if node.name not in _KEYBUILD_HANDLERS:
            continue
        seen.add(node.name)
        for inner in ast.walk(node):
            if isinstance(inner, ast.Attribute) and inner.attr in _DETECTOR_NAMES:
                offenders.append(f"{node.name} → {inner.attr}")
            elif isinstance(inner, ast.Name) and inner.id in _DETECTOR_NAMES:
                offenders.append(f"{node.name} → {inner.id}")
    missing = _KEYBUILD_HANDLERS - seen
    assert not missing, f"ไม่พบ handler ของขั้นเฉลย: {sorted(missing)}"
    assert not offenders, offenders


def test_key_universe_module_does_not_import_the_detector():
    src = (PACKAGE / "indicators" / "keyuniverse.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
    # ใช้ ``mapping`` ได้เฉพาะเพื่ออ่าน *ชุดสถานะ* ที่ประกาศไว้ — ไม่ใช่เพื่อเรียกตัวจับคู่
    assert "registry" not in imported and "observe" not in imported
    # 🔴 ค้น "mp.propose(" ไม่ใช่ "propose" เปล่า ๆ เพราะชื่อฟิลด์ proposed_status
    # มีคำนั้นอยู่ในตัว — ด่านที่ค้นสตริงหยาบเกินไปจะล้มด้วยเหตุที่ไม่ใช่ข้อผิดพลาดจริง
    assert "mp.propose(" not in src, "โมดูลจักรวาลของเฉลยต้องไม่เรียกตัวเสนอคู่"


def _strip_docstrings(tree):
    """ตัด docstring ทุกระดับออกจาก AST — คอมเมนต์หายไปเองตอน ``ast.unparse``"""
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(body, list) and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    return ast.fix_missing_locations(tree)


def test_source_inventory_module_does_not_import_the_detector_registry():
    """P3-2 — ทะเบียนอิสระต้องไม่รู้จักทะเบียนของ detector เลย"""
    path = PACKAGE / "indicators" / "sourceinventory.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
    assert "registry" not in imported and "mapping" not in imported
    # 🔴 ค้นเฉพาะ **โค้ดที่ทำงานจริง** — ข้อความอธิบายที่บอกว่า "ไม่รู้จัก ind_mappings"
    # มีชื่อนั้นอยู่ในตัวเอง ด่านที่ค้นสตริงดิบจะล้มด้วยเหตุที่ไม่ใช่ข้อผิดพลาดจริง
    code = ast.unparse(_strip_docstrings(tree))
    for forbidden in ("ind_mappings", "ind_observations", "propose", "mapping_id"):
        assert forbidden not in code, forbidden


def test_every_handler_that_builds_detector_output_checks_the_seal_gate_first():
    """P4-1 (Pass 5) — handler ใดใน ``app.py`` ที่ประกอบผลของเครื่อง (``run_view`` /
    ``pair_view``) ต้องเรียก ``detector_output_allowed`` **ก่อน** บรรทัดที่ประกอบนั้น

    🔴 Bo (`5606392284` P4-1) — เดิม ``/indicators/runs/{id}`` ประกอบรายงานโดยไม่ตรวจ
    และ ``decide`` ประกอบคู่ก่อนแล้วค่อยให้ชั้นบริการปฏิเสธ (หน้า error แสดงคู่ได้)
    """
    app_py = PACKAGE / "app.py"
    tree = ast.parse(app_py.read_text(encoding="utf-8"), filename=str(app_py))
    builders = {"run_view", "pair_view"}
    offenders = []
    for node in _function_nodes(tree):
        if node.name == "create_app":
            continue
        first_gate = None
        first_build = None
        for inner in ast.walk(node):
            if isinstance(inner, ast.Attribute):
                if inner.attr == "detector_output_allowed":
                    first_gate = min(first_gate or inner.lineno, inner.lineno)
                elif inner.attr in builders:
                    first_build = min(first_build or inner.lineno, inner.lineno)
        if first_build is not None and (first_gate is None or first_gate > first_build):
            offenders.append(f"{node.name}:{first_build}")
    assert not offenders, offenders
