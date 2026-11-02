# -*- coding: utf-8 -*-
"""ส่งออกรายการที่ยืนยัน — latest-only · snapshot · BOM · กันสูตรทั้ง CSV/XLSX ·
แยกหน่วย · ชีตสรุป (กิ๊ฟ ข้อ E)

🔴 **SYNTHETIC TEST FIXTURE** — สมุดงานทุกไฟล์ในชุดนี้แต่งขึ้นทั้งหมด
**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import json
import re

import openpyxl
import pytest

from redbook.services import decisions as dec
from redbook.services import export as ex
from redbook.services import t1b as svc
from redbook.storage import t1b_decisions as drepo, t1b_repo
from redbook.storage.db import init_db
from t1b_synth import build_workbook, records

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"
RID = "EX-1"
INJECT = "=HYPERLINK(\"http://evil\",\"x\")"


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "e.sqlite3"
    init_db(p)
    t1b_repo.init_t1b_schema(p)
    return p


@pytest.fixture()
def run(tmp_path, db):
    base = records(build_workbook(tmp_path, filename="a.xlsx", agency="สถาบันทดสอบ",
                                  cover_year=2569, section_title=TITLE))
    curr = records(build_workbook(tmp_path, filename="b.xlsx", agency="สถาบันทดสอบ",
                                  cover_year=2570, section_title=TITLE, invest=12.0))
    view = svc.run_from_records(base, curr, run_id=RID)
    t1b_repo.save_run(view, run_id=RID, db_path=db)
    return view


def _rec(view, f, status, db, **kw):
    seq = drepo.latest_seq_for(RID, f.finding_id, db_path=db)
    return dec.record(view, f, status, expected_latest_seq=seq, db_path=db, **kw)


def _amounts(view):
    return [f for f in view.findings if f.finding_type.startswith("AMOUNT_")]


# ── latest-only ───────────────────────────────────────────────────────────
def test_exports_only_confirmed_and_confirmed_with_edit(db, run):
    a, b, c, d = run.findings[:4]
    _rec(run, a, dec.CONFIRMED, db)
    _rec(run, b, dec.CONFIRMED_WITH_EDIT, db, note="แก้", corrected_value="5")
    _rec(run, c, dec.UNRESOLVED, db, note="x")
    _rec(run, d, dec.DISMISSED, db, note="x")
    bundle = ex.build(run, db_path=db)
    ids = {r["finding_id"] for r in bundle.rows}
    assert ids == {a.finding_id, b.finding_id}
    assert bundle.excluded["by_status"][dec.UNRESOLVED] == 1
    assert bundle.excluded["by_status"][dec.DISMISSED] == 1


def test_confirmed_then_dismissed_is_not_exported(db, run):
    f = run.findings[0]
    _rec(run, f, dec.CONFIRMED, db)
    _rec(run, f, dec.DISMISSED, db, note="เปลี่ยนใจหลังตรวจต้นฉบับ")
    assert ex.build(run, db_path=db).count == 0


def test_confirmed_uses_engine_value_edit_uses_corrected(db, run):
    a, b = _amounts(run)[0], run.findings[1]
    _rec(run, a, dec.CONFIRMED, db)
    _rec(run, b, dec.CONFIRMED_WITH_EDIT, db, note="ต้นฉบับต่าง", corrected_value="9.99")
    rows = {r["finding_id"]: r for r in ex.build(run, db_path=db).rows}
    assert rows[a.finding_id]["confirmed_value"] == a.current_value
    assert rows[a.finding_id]["edit_reason"] == ""
    assert rows[b.finding_id]["confirmed_value"] == "9.99"
    assert rows[b.finding_id]["engine_current_value"] == b.current_value
    assert rows[b.finding_id]["edit_reason"] == "ต้นฉบับต่าง"


def test_snapshot_is_frozen_with_cutoff(db, run):
    _rec(run, run.findings[0], dec.CONFIRMED, db)
    b = ex.build(run, db_path=db)
    s = b.snapshot
    assert s["export_id"].startswith("exp_") and s["run_id"] == RID
    assert s["decision_cutoff_seq"] == drepo.latest_seq_for(RID, run.findings[0].finding_id, db_path=db)
    assert s["row_count"] == 1 and "compare=" in s["engine_versions"]
    assert s["title"] == ex.EXPORT_TITLE and s["disclaimer"] == ex.EXPORT_DISCLAIMER


def test_snapshot_stamps_current_privacy_version(db, run):
    """#6 ข้อ 1 — การส่งออกต้องประทับรุ่นนโยบายกลบข้อมูลที่ใช้ **ตอนสร้าง**"""
    from redbook import privacy
    _rec(run, run.findings[0], dec.CONFIRMED, db)
    s = ex.build(run, db_path=db).snapshot
    assert s["privacy_version"] == privacy.PRIVACY_VERSION
    assert s["privacy_version"] != "t1b-privacy-0.1.0"
    flat = [c for row in ex._header_rows(s) for c in row]
    assert f"privacy={privacy.PRIVACY_VERSION}" in flat


def test_required_columns_present():
    keys = {k for k, _ in ex.COLUMNS}
    for k in ("subject_category", "category_confidence", "category_evidence",
              "needs_human_rebind", "ebudget_status", "baseline_location",
              "current_location", "engine_difference", "confirmed_value",
              "decision_status", "decision_note", "audit_seq", "file_a_sha256"):
        assert k in keys, k


def test_ebudget_status_defaults_to_not_done(db, run):
    _rec(run, run.findings[0], dec.CONFIRMED, db)
    assert ex.build(run, db_path=db).rows[0]["ebudget_status"] == "ยังไม่ได้ดำเนินการ"


# ── ไฟล์ ──────────────────────────────────────────────────────────────────
@pytest.fixture()
def written(db, run, tmp_path):
    a = _amounts(run)[0]
    b = run.findings[1]
    _rec(run, a, dec.CONFIRMED, db, note=INJECT)              # ข้อความผู้ใช้เป็นสูตร
    _rec(run, b, dec.CONFIRMED_WITH_EDIT, db, note="+ต้นฉบับ", corrected_value="-7")
    bundle = ex.build(run, db_path=db)
    files = ex.write(bundle, tmp_path / "out")
    return bundle, files


def test_csv_has_bom_title_disclaimer_and_neutralized_formula(written):
    _, files = written
    raw = files.csv_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert ex.EXPORT_TITLE in text and ex.EXPORT_DISCLAIMER in text
    assert INJECT not in text.replace("'" + INJECT, "")      # ต้องถูกเติมเครื่องหมายนำหน้า
    assert "'=HYPERLINK" in text or "’=HYPERLINK" in text or "'" in text


def test_xlsx_neutralizes_formula_and_forces_text(written):
    _, files = written
    wb = openpyxl.load_workbook(files.xlsx_path)
    ws = wb["รายการที่ยืนยัน"]
    found = False
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str) and "HYPERLINK" in c.value:
                found = True
                assert not c.value.startswith("="), "สูตรต้องถูกกัน"
                assert c.data_type == "s"
    assert found
    assert files.xlsx_neutralized >= 2                        # "=HYPERLINK…" และ "+ต้นฉบับ"/"-7"
    assert "สรุป" in wb.sheetnames
    wb.close()


def test_xlsx_summary_sheet_has_required_blocks(written):
    bundle, files = written
    wb = openpyxl.load_workbook(files.xlsx_path)
    text = "\n".join(str(c.value) for r in wb["สรุป"].iter_rows() for c in r if c.value is not None)
    wb.close()
    for needle in ("จำนวนรายการตามหมวดจุดตรวจสอบ", "จำนวนตามสถานะคำตัดสิน",
                   "ยอดเงิน แยกตาม (หมวดงบรายจ่าย | หน่วย)", "ยอดเพิ่ม", "ยอดลด", "ยอดสุทธิ",
                   "not_rebindable", "OTHER_OR_UNCLASSIFIED ที่ไม่ได้ส่งออก",
                   ex.EXPORT_DISCLAIMER):
        assert needle in text, needle


def test_money_is_grouped_by_category_and_unit_never_merged(db, run, tmp_path):
    for f in _amounts(run):
        _rec(run, f, dec.CONFIRMED, db)
    bundle = ex.build(run, db_path=db)
    groups = bundle.summary["money_by_group"]
    assert groups, "ต้องมีกลุ่มยอดเงินอย่างน้อยหนึ่งกลุ่ม"
    for key, g in groups.items():
        assert " | " in key                                  # (หมวด | หน่วย)
        assert g["rows"] + g["unparsed"] >= 1


def test_forbidden_phrases_never_appear(written):
    _, files = written
    text = files.csv_path.read_text(encoding="utf-8-sig")
    for phrase in ex.FORBIDDEN_PHRASES:
        assert phrase not in text
    snap = json.loads((files.csv_path.parent / f"{files.export_id}_snapshot.json").read_text(encoding="utf-8"))
    assert snap["row_count"] == 2


def test_export_page_and_download_route(db, run, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from redbook import config
    from redbook.app import create_app
    from redbook.web.security import CSRF_COOKIE, CSRF_FIELD

    # ใช้ฐานข้อมูลของแอป (ค่าเริ่มต้น) — สร้างรอบใหม่ในนั้น
    t1b_repo.init_t1b_schema()
    view = svc.run_from_records(
        records(build_workbook(tmp_path, filename="wa.xlsx", agency="สถาบันทดสอบ",
                               cover_year=2569, section_title=TITLE)),
        records(build_workbook(tmp_path, filename="wb.xlsx", agency="สถาบันทดสอบ",
                               cover_year=2570, section_title=TITLE, invest=12.0)),
        run_id="EX-WEB")
    t1b_repo.save_run(view, run_id="EX-WEB")
    # 🔴 ด่านตรวจก่อนส่งออก (กิ๊ฟ 23 ก.ย. 2569) — รอบที่ยังตัดสินไม่ครบ
    # ส่งออกไม่ได้ · เส้นทางนี้จึงต้องตัดสินให้ครบก่อนเหมือนผู้ใช้จริง
    for f in view.findings:
        dec.record(view, f, dec.CONFIRMED, expected_latest_seq=0)
    with TestClient(create_app()) as client:
        client.get("/")
        token = client.cookies.get(CSRF_COOKIE)
        body = client.get("/t1b/runs/EX-WEB/export").text
        assert ex.EXPORT_DISCLAIMER in body

        # ด่านที่เหลือ — รับทราบรายการที่เครื่องยนต์อ่านไม่ครบ ผ่านหน้าจอจริง
        pre = client.get("/t1b/runs/EX-WEB/preflight").text
        scope = re.search(r'name="scope" value="([0-9a-f]+)"', pre).group(1)
        ack = client.post("/t1b/runs/EX-WEB/preflight/ack",
                          data={CSRF_FIELD: token, "scope": scope,
                                "reviewer": "ผู้ตรวจทดสอบ"},
                          follow_redirects=False)
        assert ack.status_code == 303

        r = client.post("/t1b/runs/EX-WEB/export", data={CSRF_FIELD: token})
        assert r.status_code == 200 and "exp_" in r.text
        name = [p.name for p in config.EXPORT_DIR.glob("exp_*_confirmed_for_ebudgeting.csv")][-1]
        d = client.get(f"/t1b/exports/{name}")
        assert d.status_code == 200 and d.content.startswith(b"\xef\xbb\xbf")
        assert client.get("/t1b/exports/../secret.csv").status_code in (400, 404)
        assert client.get("/t1b/exports/not_exp.csv").status_code == 400
