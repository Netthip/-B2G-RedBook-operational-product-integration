# -*- coding: utf-8 -*-
"""ชั้นเข้าถึงข้อมูล - รวมคำสั่ง SQL ไว้ที่เดียว

ทุกคำสั่งใช้ parameter binding เสมอ ไม่มีการต่อสตริง SQL จากค่าที่ผู้ใช้กรอก
(ป้องกัน SQL injection ตาม OWASP A03)
"""
import uuid
from datetime import datetime, timezone

from . import audit
from .db import connect, jdump, jload

MODES = ("year_to_year", "before_after_reduction")
SIDES = ("A", "B", "REF")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


# ---------------------------------------------------------------- projects
def create_project(name: str, mode: str, note: str = "",
                   created_by: str = "local-user", db_path=None) -> str:
    if mode not in MODES:
        raise ValueError("โหมดตรวจไม่ถูกต้อง")
    name = (name or "").strip()
    if not name:
        raise ValueError("ต้องระบุชื่องานตรวจ")
    pid = new_id("prj")
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO projects (id, name, mode, note, created_at, created_by, status) "
            "VALUES (?,?,?,?,?,?,'draft')",
            (pid, name[:200], mode, (note or "")[:2000], now_iso(), created_by))
    finally:
        conn.close()
    audit.record("project_created", "project", pid,
                 {"name": name[:200], "mode": mode}, actor=created_by, db_path=db_path)
    return pid


def get_project(project_id: str, db_path=None):
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_projects(limit: int = 100, db_path=None):
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT p.*, "
            "(SELECT COUNT(*) FROM files f WHERE f.project_id = p.id) AS file_count, "
            "(SELECT COUNT(*) FROM runs r WHERE r.project_id = p.id) AS run_count "
            "FROM projects p ORDER BY p.created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def set_project_status(project_id: str, status: str, db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.execute("UPDATE projects SET status = ? WHERE id = ?", (status, project_id))
    finally:
        conn.close()


# ------------------------------------------------------------------- files
def attach_file(project_id: str, side: str, stored, declared: dict = None,
                actor: str = "local-user", db_path=None) -> str:
    """ผูกไฟล์ที่เก็บแล้ว (StoredFile) เข้ากับงานตรวจ ฝั่ง A/B/REF"""
    if side not in SIDES:
        raise ValueError("ฝั่งไฟล์ไม่ถูกต้อง")
    d = declared or {}
    conn = connect(db_path)
    try:
        conn.execute("DELETE FROM files WHERE project_id = ? AND side = ?",
                     (project_id, side))
        conn.execute(
            "INSERT INTO files (id, project_id, side, original_name, stored_name, kind, "
            "size_bytes, sha256, uploaded_at, declared_fiscal_year, declared_agency_code, "
            "declared_agency_name, declared_doc_kind) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stored.file_id, project_id, side, stored.original_name, stored.stored_name,
             stored.kind, stored.size_bytes, stored.sha256, now_iso(),
             d.get("fiscal_year"), d.get("agency_code"), d.get("agency_name"),
             d.get("doc_kind")))
    finally:
        conn.close()
    audit.record("file_uploaded", "file", stored.file_id,
                 {"project_id": project_id, "side": side,
                  "original_name": stored.original_name, "kind": stored.kind,
                  "size_bytes": stored.size_bytes, "sha256": stored.sha256,
                  "declared": d},
                 actor=actor, db_path=db_path)
    return stored.file_id


def project_files(project_id: str, db_path=None) -> dict:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM files WHERE project_id = ? ORDER BY side", (project_id,)).fetchall()
        return {r["side"]: dict(r) for r in rows}
    finally:
        conn.close()


def get_file(file_id: str, db_path=None):
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# -------------------------------------------------------------------- runs
def create_run(project_id: str, mode: str, files: dict, versions: dict,
               config_obj: dict, config_hash: str, db_path=None) -> str:
    rid = new_id("run")
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO runs (id, project_id, mode, file_a_id, file_b_id, ref_file_id, "
            "engine_version, rule_set_version, canonical_model_version, "
            "parser_versions_json, config_json, config_hash, started_at, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'running')",
            (rid, project_id, mode,
             files.get("A", {}).get("id"), files.get("B", {}).get("id"),
             files.get("REF", {}).get("id"),
             versions["engine_version"], versions["rule_set_version"],
             versions["canonical_model_version"], jdump(versions.get("parsers", {})),
             jdump(config_obj), config_hash, now_iso()))
    finally:
        conn.close()
    return rid


def save_run_rules(run_id: str, snapshot_rows: list, db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO run_rules (run_id, rule_id, rule_version, enabled, "
            "params_json) VALUES (?,?,?,?,?)",
            [(run_id, r["rule_id"], r["rule_version"], r["enabled"], jdump(r["params"]))
             for r in snapshot_rows])
    finally:
        conn.close()


def finish_run(run_id: str, status: str, duration_ms: int, items_checked: int,
               result_hash: str, db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.execute(
            "UPDATE runs SET status = ?, finished_at = ?, duration_ms = ?, "
            "items_checked = ?, result_hash = ? WHERE id = ?",
            (status, now_iso(), duration_ms, items_checked, result_hash, run_id))
    finally:
        conn.close()


def get_run(run_id: str, db_path=None):
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_runs(project_id: str, db_path=None):
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM runs WHERE project_id = ? ORDER BY started_at DESC",
            (project_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def run_rules(run_id: str, db_path=None):
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM run_rules WHERE run_id = ? ORDER BY rule_id", (run_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------- findings
def insert_findings(run_id: str, findings: list, db_path=None) -> None:
    conn = connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO findings (id, run_id, finding_code, finding_key, check_type, "
            "severity, rule_id, rule_version, reason, value_a, value_b, diff_value, "
            "diff_pct, unit, loc_a_json, loc_b_json, machine_status, presentation_only, "
            "confidence, confidence_basis, evidence_json, sort_key) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(f["id"], run_id, f["finding_code"], f["finding_key"], f["check_type"],
              f["severity"], f["rule_id"], f["rule_version"], f["reason"],
              f.get("value_a"), f.get("value_b"), f.get("diff_value"), f.get("diff_pct"),
              f.get("unit"), jdump(f.get("loc_a", {})), jdump(f.get("loc_b", {})),
              f["machine_status"], 1 if f.get("presentation_only") else 0,
              f.get("confidence"), f.get("confidence_basis"),
              jdump(f.get("evidence", {})), f.get("sort_key", ""))
             for f in findings])
    finally:
        conn.close()


def list_findings(run_id: str, machine_status: str = None, review_status: str = None,
                  severity: str = None, rule_id: str = None, limit: int = 1000,
                  offset: int = 0, db_path=None):
    sql = "SELECT * FROM findings WHERE run_id = ?"
    params = [run_id]
    if machine_status:
        sql += " AND machine_status = ?"
        params.append(machine_status)
    if review_status:
        sql += " AND review_status = ?"
        params.append(review_status)
    if severity:
        sql += " AND severity = ?"
        params.append(severity)
    if rule_id:
        sql += " AND rule_id = ?"
        params.append(rule_id)
    sql += " ORDER BY sort_key, finding_code LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    conn = connect(db_path)
    try:
        rows = conn.execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["loc_a"] = jload(d.pop("loc_a_json"))
            d["loc_b"] = jload(d.pop("loc_b_json"))
            d["evidence"] = jload(d.pop("evidence_json"))
            out.append(d)
        return out
    finally:
        conn.close()


def get_finding(finding_id: str, db_path=None):
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["loc_a"] = jload(d.pop("loc_a_json"))
        d["loc_b"] = jload(d.pop("loc_b_json"))
        d["evidence"] = jload(d.pop("evidence_json"))
        return d
    finally:
        conn.close()


def summarize_findings(run_id: str, db_path=None) -> dict:
    conn = connect(db_path)
    try:
        by_machine = {r["machine_status"]: r["n"] for r in conn.execute(
            "SELECT machine_status, COUNT(*) n FROM findings WHERE run_id = ? "
            "GROUP BY machine_status", (run_id,))}
        by_review = {r["review_status"]: r["n"] for r in conn.execute(
            "SELECT review_status, COUNT(*) n FROM findings WHERE run_id = ? "
            "GROUP BY review_status", (run_id,))}
        by_rule = {r["rule_id"]: r["n"] for r in conn.execute(
            "SELECT rule_id, COUNT(*) n FROM findings WHERE run_id = ? "
            "GROUP BY rule_id", (run_id,))}
        total = conn.execute("SELECT COUNT(*) n FROM findings WHERE run_id = ?",
                             (run_id,)).fetchone()["n"]
        return {"total": total, "by_machine_status": by_machine,
                "by_review_status": by_review, "by_rule": by_rule}
    finally:
        conn.close()


def decide_finding(finding_id: str, review_status: str, note: str,
                   reviewer: str, db_path=None) -> bool:
    """บันทึกคำตัดสินของมนุษย์ - ต้องมีเหตุผลเสมอ และลง Audit Trail ทุกครั้ง"""
    if not (note or "").strip():
        raise ValueError("ต้องระบุเหตุผลประกอบการตัดสิน")
    before = get_finding(finding_id, db_path=db_path)
    if not before:
        return False
    conn = connect(db_path)
    try:
        conn.execute(
            "UPDATE findings SET review_status = ?, review_note = ?, reviewed_by = ?, "
            "reviewed_at = ? WHERE id = ?",
            (review_status, note.strip()[:2000], reviewer, now_iso(), finding_id))
    finally:
        conn.close()
    audit.record("finding_reviewed", "finding", finding_id,
                 {"run_id": before["run_id"], "finding_code": before["finding_code"],
                  "rule_id": before["rule_id"],
                  "from": before["review_status"], "to": review_status,
                  "note": note.strip()[:2000]},
                 actor=reviewer, db_path=db_path)
    return True


# ══════════════════════════════════════════════════════════════════════════════
#  การลบตาม `PROVISIONAL_LOCAL_RETENTION POLICY`
# ══════════════════════════════════════════════════════════════════════════════


def project_deletion_preview(project_id: str, db_path=None) -> dict:
    """สรุปว่าถ้ากดลบแล้วจะหายอะไรไปบ้าง — **อ่านอย่างเดียว ไม่ลบอะไร**

    หน้าจอยืนยันต้องแสดงตัวเลขชุดนี้ให้ผู้ใช้เห็นก่อนกดยืนยัน
    """
    from . import t1b_repo

    conn = connect(db_path)
    try:
        files = [dict(r) for r in conn.execute(
            "SELECT side, original_name, sha256, size_bytes FROM files "
            "WHERE project_id = ? ORDER BY side", (project_id,))]
        runs = conn.execute(
            "SELECT COUNT(*) n FROM runs WHERE project_id = ?",
            (project_id,)).fetchone()["n"]
        findings = conn.execute(
            "SELECT COUNT(*) n FROM findings f JOIN runs r ON r.id = f.run_id "
            "WHERE r.project_id = ?", (project_id,)).fetchone()["n"]
    finally:
        conn.close()

    t1b_runs = [r for r in t1b_repo.list_runs(db_path, limit=10000)
                if r["project_id"] == project_id]
    return {
        "files": files,
        "t1a_runs": runs,
        "t1a_findings": findings,
        "t1b_runs": len(t1b_runs),
        "t1b_findings": sum(int(r["total_findings"]) for r in t1b_runs),
    }


def delete_project(project_id: str, db_path=None) -> dict:
    """ลบงานตรวจหนึ่งงานพร้อมไฟล์ต้นฉบับ แล้วคืนสรุปสิ่งที่ลบไป

    🔴 `PROVISIONAL_LOCAL_RETENTION POLICY` (คำตัดสินกิ๊ฟ 7 ก.ย. 2569) —
    หลังลบต้องเหลือเพียง **metadata ใน Audit Trail** ที่ไม่มีเนื้อหางบประมาณ
    ได้แก่ ผลสำเร็จ/ไม่สำเร็จ · เวลา · ตัวระบุ project/run · รุ่น (B.3)
    ชื่อรายการ ยอดเงิน ตำแหน่งหลักฐาน หมายเหตุ และค่าที่ผู้ตรวจแก้
    **ต้องหายไปทั้งหมด**

    ลำดับ — **ฐานข้อมูลก่อน ไฟล์ทีหลัง** และฐานข้อมูลเป็นธุรกรรมเดียว

    1. ในธุรกรรมเดียว: เปิดสิทธิ์ลบผูกกับแต่ละรอบ T1B → ลบรอบ (cascade ไปคำตัดสิน
       และข้อสังเกต) → consume สิทธิ์ → ลบงานตรวจ (cascade ไปไฟล์/รอบ T1A)
       → บันทึก audit "สำเร็จ" · ล้มที่ใดก็ **ย้อนกลับทั้งชุด** ไม่เหลือครึ่งหนึ่ง
    2. ค่อยลบไฟล์บนดิสก์ — ระบบไฟล์ไม่มีธุรกรรม จึงทำหลังจากฐานข้อมูลยืนยันแล้ว
       ไฟล์ที่ลบไม่ได้จะถูกรายงาน ไม่ทำให้การลบฐานข้อมูลถูกย้อนกลับ

    ถ้าธุรกรรมล้ม จะบันทึก audit "ไม่สำเร็จ" ในธุรกรรมใหม่แล้วยกข้อผิดพลาดต่อ
    """
    from . import files as filestore
    from . import t1b_decisions, t1b_repo
    from .db import session

    project = get_project(project_id, db_path)
    if not project:
        return {"deleted": False}

    preview = project_deletion_preview(project_id, db_path)
    conn = connect(db_path)
    try:
        stored = [r["stored_name"] for r in conn.execute(
            "SELECT stored_name FROM files WHERE project_id = ?", (project_id,))]
        run_ids = [r["id"] for r in conn.execute(
            "SELECT id FROM t1b_runs WHERE project_id = ?", (project_id,))]
    finally:
        conn.close()

    meta = {
        "retention_policy": "PROVISIONAL_LOCAL_RETENTION",
        "t1b_schema_version": t1b_repo.T1B_SCHEMA_VERSION,
        "project_id": project_id,
        "t1b_run_ids": run_ids,
        "file_hashes": [f["sha256"] for f in preview["files"]],
        "counts": {"files": len(preview["files"]),
                   "t1a_runs": preview["t1a_runs"],
                   "t1a_findings": preview["t1a_findings"],
                   "t1b_runs": preview["t1b_runs"],
                   "t1b_findings": preview["t1b_findings"]},
    }

    try:
        with session(db_path) as conn:
            for rid in run_ids:
                token = t1b_decisions.open_retention_unlock(
                    conn, rid, f"delete_project:{project_id}")
                conn.execute("DELETE FROM t1b_runs WHERE id = ?", (rid,))
                t1b_decisions.consume_retention_unlock(conn, token)
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            audit.record_in(conn, "project_deleted", "project", project_id,
                            {**meta, "outcome": "success"})
    except Exception as exc:
        audit.record("project_delete_failed", "project", project_id,
                     {**meta, "outcome": "failure",
                      "error_type": type(exc).__name__}, db_path=db_path)
        raise

    removed_files, failed_files = 0, 0
    for name in stored:
        try:
            if filestore.delete_stored(name):
                removed_files += 1
        except (filestore.UploadRejected, OSError):
            failed_files += 1

    return {"deleted": True, "removed_files": removed_files,
            "failed_files": failed_files,
            "t1b_runs_removed": len(run_ids), **preview}
