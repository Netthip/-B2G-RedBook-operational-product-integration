# -*- coding: utf-8 -*-
"""ด่านกันชุดข้อมูล P1 — พิสูจน์ว่า **ไม่มีการเปิดอ่าน** ไม่ใช่แค่ตกลงกันว่าจะไม่อ่าน

🔴 **คำสั่งกิ๊ฟ (7 ก.ย. 2569)** — *"การอยู่ในโฟลเดอร์ย่อย `P1/` ถือว่าแยกทาง
กายภาพพอใช้ได้ แต่ยังไม่ถือว่าเป็น holdout ที่พิสูจน์แล้วจนกว่าโค้ดจะบังคับไม่ให้แตะ"*

วิธีพิสูจน์ที่ใช้ในชุดนี้ — **ดักที่ระดับระบบไฟล์** ไม่ใช่ที่ระดับ API ของเรา
ครอบ ``builtins.open`` และ ``zipfile.ZipFile`` ไว้ระหว่างการทดสอบ แล้วยืนยันว่า
ไม่มีเส้นทางของไฟล์ล่อปรากฏในรายการที่ถูกเปิดเลย · วิธีนี้จับได้แม้โค้ดจะอ้อม
ไปเรียก openpyxl เองโดยไม่ผ่านด่านของเรา

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import builtins
import json
import zipfile

import openpyxl
import pytest
from fastapi.testclient import TestClient

from redbook import holdout
from redbook.app import create_app
from redbook.services import t1b as svc
from redbook.storage import audit, t1b_repo
from redbook.web.security import CSRF_COOKIE, CSRF_FIELD

DECOY_MARKER = "ยอดที่ห้ามเห็น 987654321"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture()
def decoy(tmp_path):
    """ไฟล์ล่อในโฟลเดอร์ ``P1/`` — ถ้ามีใครเปิด จะจับได้ทั้งจากเส้นทางและเนื้อใน"""
    d = tmp_path / "P1"
    d.mkdir()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"
    ws["A2"] = DECOY_MARKER
    ws["B2"] = 987654321
    path = d / "21011_HSRI_P1_70.xlsx"
    wb.save(path)
    wb.close()
    return path


class _OpenWatch:
    """บันทึกทุกเส้นทางที่ถูกเปิดจริงในช่วงที่ครอบไว้"""

    def __init__(self, monkeypatch):
        self.opened: list[str] = []
        real_open = builtins.open
        real_zip = zipfile.ZipFile.__init__

        def spy_open(file, *a, **kw):
            self.opened.append(str(file))
            return real_open(file, *a, **kw)

        def spy_zip(zself, file, *a, **kw):
            self.opened.append(str(file))
            return real_zip(zself, file, *a, **kw)

        monkeypatch.setattr(builtins, "open", spy_open)
        monkeypatch.setattr(zipfile.ZipFile, "__init__", spy_zip)

    def touched(self, path) -> bool:
        name = str(path)
        return any(name in o for o in self.opened)


@pytest.fixture()
def watch(monkeypatch):
    return _OpenWatch(monkeypatch)


# ══════════════════════════════════════════════════════════════════════════════
#  H1 — กติกาการจำแนก
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("name", [
    "P1/21011_HSRI_P1_70.xlsx",
    "p1/anything.xlsx",
    "data/P1/nested/deep.xlsx",
    "21016_NVI_P1_70_ฉบับปรับลด.xlsx",
    "P1_report.xlsx",
    "something-P1.xlsx",
])
def test_p1_paths_are_held_out(name):
    assert holdout.is_holdout(name), name


@pytest.mark.parametrize("name", [
    "AO_21011_HSRI1_69.xlsx",
    "AO_21016_NVI_70.xlsx",
    "Bis67rdoc001_1_all.xlsx",
    "report_P10_summary.xlsx",
    "P100.xlsx",
])
def test_ordinary_ao_paths_are_not_held_out(name):
    """ด่านต้องไม่กว้างเกินจนบล็อกแฟ้ม AO ปกติ"""
    assert not holdout.is_holdout(name), name


def test_reason_is_reported_so_a_human_can_check_it():
    assert holdout.holdout_reason("P1/x.xlsx") == holdout.REASON_DIR
    assert holdout.holdout_reason("a_P1_b.xlsx") == holdout.REASON_NAME
    assert holdout.holdout_reason("AO_21016_NVI_70.xlsx") is None


def test_partition_returns_both_piles_never_silently_drops():
    kept, skipped = holdout.partition(
        ["AO_a.xlsx", "P1/b.xlsx", "c_P1_d.xlsx", "AO_e.xlsx"])
    assert [p.name for p in kept] == ["AO_a.xlsx", "AO_e.xlsx"]
    assert len(skipped) == 2
    assert all(reason for _, reason in skipped)


# ══════════════════════════════════════════════════════════════════════════════
#  H2 — พิสูจน์ว่าไม่มีการเปิดอ่านจริง
# ══════════════════════════════════════════════════════════════════════════════

def test_the_watch_itself_actually_records_reads(tmp_path, watch):
    """🔴 ต้องมีข้อนี้ — ถ้าตัวดักไม่ทำงาน ข้อถัดไปจะผ่านโดยไม่พิสูจน์อะไรเลย

    เป็นบทเรียนจากรอบก่อนที่ตัวตรวจกับตัวที่ถูกตรวจใช้ตรรกะเดียวกัน
    เทสต์จึงผ่านทั้งที่ข้อมูลยังรั่วอยู่
    """
    ordinary = tmp_path / "ordinary.xlsx"
    wb = openpyxl.Workbook()
    wb.save(ordinary)
    wb.close()
    watch.opened.clear()
    openpyxl.load_workbook(ordinary)
    assert watch.touched(ordinary), "ตัวดักไม่บันทึกการเปิดไฟล์ — ใช้พิสูจน์อะไรไม่ได้"


def test_read_workbook_refuses_and_never_opens_the_decoy(decoy, watch):
    with pytest.raises(holdout.HoldoutViolation):
        svc.read_workbook(decoy)
    assert not watch.touched(decoy), \
        "ด่านต้องอยู่ก่อนบรรทัดแรกที่แตะไฟล์ — พบว่ามีการเปิดจริง"


def test_run_from_workbooks_refuses_before_touching_either_file(decoy, watch,
                                                                tmp_path):
    other = tmp_path / "AO_ok.xlsx"
    wb = openpyxl.Workbook()
    wb.save(other)
    wb.close()
    watch.opened.clear()
    with pytest.raises(holdout.HoldoutViolation):
        svc.run_from_workbooks(decoy, other, run_id="HOLD-1")
    assert not watch.touched(decoy)


def test_inventory_collection_skips_the_decoy_and_says_so(decoy, capsys,
                                                          tmp_path):
    from redbook import inventory_cli

    wb = openpyxl.Workbook()
    wb.save(tmp_path / "AO_real.xlsx")
    wb.close()

    files = inventory_cli._collect_files([str(tmp_path), str(decoy.parent)])
    names = [p.name for p in files]
    assert "AO_real.xlsx" in names
    assert decoy.name not in names
    out = capsys.readouterr().out
    assert "กันไว้" in out, "ต้องประกาศว่ากันอะไรไป ไม่ใช่กรองทิ้งเงียบ ๆ"
    assert holdout.HOLDOUT_STATUS in out


def test_holdout_gate_has_no_environment_switch():
    """ด่านนี้ต้องปิดไม่ได้ด้วยตัวแปรสภาพแวดล้อมหรือค่าตั้ง

    ถ้ามีสวิตช์ปิดได้ ก็พิสูจน์ย้อนหลังไม่ได้ว่าตอนพัฒนาไม่เคยเปิดดู
    """
    import inspect

    src = inspect.getsource(holdout)
    assert "os.environ" not in src and "getenv" not in src
    assert "config." not in src


# ══════════════════════════════════════════════════════════════════════════════
#  H3 — ผ่านหน้าเว็บ
# ══════════════════════════════════════════════════════════════════════════════

def _token(client):
    client.get("/projects/new")
    return client.cookies.get(CSRF_COOKIE)


def test_uploading_a_p1_file_is_refused_with_a_role_explanation(client, decoy):
    token = _token(client)
    r = client.post("/projects/new",
                    data={"name": "งานตรวจ P1", "mode": "year_to_year",
                          "note": "", CSRF_FIELD: token},
                    follow_redirects=False)
    pid = r.headers["location"].rsplit("/", 1)[-1]

    with open(decoy, "rb") as fh:
        r = client.post(f"/projects/{pid}/upload",
                        data={"side": "A", "fiscal_year": "2570",
                              "agency_code": "21011", "agency_name": "ทดสอบ",
                              "doc_kind": "P1", CSRF_FIELD: token},
                        files={"upload": (decoy.name, fh,
                                          "application/octet-stream")},
                        follow_redirects=False)
    assert r.status_code == 400
    assert "คนละบทบาท" in r.text
    assert "AO" in r.text


def test_refused_p1_upload_leaves_no_hash_and_no_finding(client, decoy):
    """ห้ามมีแฮชของไฟล์ล่อ และห้ามปรากฏใน finding หรือ audit ใด ๆ"""
    from redbook.core.hashing import sha256_file

    digest = sha256_file(decoy)

    conn = t1b_repo.connect()
    blob = json.dumps([dict(e) for e in audit.entries(limit=500)],
                      ensure_ascii=False, default=str)
    blob += json.dumps(audit.security_events(limit=500), ensure_ascii=False,
                       default=str)
    assert digest not in blob, "พบแฮชของไฟล์ holdout ใน audit trail"
    assert DECOY_MARKER not in blob
    assert decoy.name not in blob, "ชื่อไฟล์ holdout ไม่ควรถูกบันทึกไว้"

    stored = conn.execute(
        "SELECT COUNT(*) n FROM t1b_findings WHERE row_label LIKE ?",
        (f"%{DECOY_MARKER}%",)).fetchone()["n"]
    assert stored == 0
