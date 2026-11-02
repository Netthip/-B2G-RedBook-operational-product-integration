# -*- coding: utf-8 -*-
"""T1B — สัญญาชั้นบริการ · projection · คิว · และที่เก็บที่แยกจาก T1A

🔴 คำสั่ง Bo · `BO REVIEW COMPLETE` (Issue #1) · LANE B ข้อ 3 · 4 · 6

ใช้ **fixture สังเคราะห์ที่เผยแพร่ได้** ทั้งหมด — ไม่มีการเปิดแฟ้มจริงในไฟล์นี้
(`publication-safe synthetic fixtures` ตามคำสั่ง)

🔴 **SYNTHETIC TEST FIXTURE** — ห้ามรายงานผลจากชุดนี้ว่าเป็นข้อผิดพลาดในเอกสารจริง

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import inspect
import json

import pytest

from redbook import privacy
from redbook.services import t1b as svc
from redbook.storage import t1b_repo
from redbook.t1b.compare import (
    FLAG_CATEGORY_TABLE_YEAR_DIFFERS,
    F_AMOUNT_INCREASED,
    F_ROW_ADDED,
    compare,
)
from redbook.t1b.matching import (
    VERDICT_CANNOT_DETERMINE,
    VERDICT_COMPARED,
    VERDICT_REVIEW_REQUIRED,
    match_records,
)
from t1b_synth import build_workbook, records

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"


@pytest.fixture()
def same_agency_view(tmp_path):
    """สองแฟ้มของหน่วยงานเดียวกัน ยอดต่างกัน ⇒ ผ่านด่านและมี finding จริง"""
    base = records(build_workbook(
        tmp_path, filename="a.xlsx", agency="สถาบันทดสอบ", cover_year=2569,
        section_title=TITLE))
    curr = records(build_workbook(
        tmp_path, filename="b.xlsx", agency="สถาบันทดสอบ", cover_year=2570,
        section_title=TITLE, invest=12.0))
    return svc.run_from_records(base, curr, run_id="RUN-TEST-1")


@pytest.fixture()
def blocked_view(tmp_path):
    """สองแฟ้มที่อ่านตัวตนหน่วยงานไม่ได้ ⇒ ด่านปฏิเสธ"""
    base = records(build_workbook(
        tmp_path, filename="x.xlsx", agency=None, cover_year=2570,
        section_title=TITLE))
    curr = records(build_workbook(
        tmp_path, filename="y.xlsx", agency=None, cover_year=2570,
        section_title=TITLE, invest=12.0))
    return svc.run_from_records(base, curr, run_id="RUN-TEST-2")


# ══════════════════════════════════════════════════════════════════════════════
#  S1 — ขอบของชั้นบริการ
# ══════════════════════════════════════════════════════════════════════════════


def test_s1_service_layer_does_not_import_the_web_framework():
    """🔴 ชั้นบริการต้องทดสอบได้โดยไม่ต้องยกเว็บ และเปลี่ยนเฟรมเวิร์กได้"""
    src = inspect.getsource(svc)
    for banned in ("fastapi", "starlette", "jinja2", "Request", "Response"):
        assert banned not in src, f"ชั้นบริการ import/อ้าง {banned!r}"


def test_s2_projection_carries_no_engine_objects(same_agency_view):
    """projection ต้องเป็นค่าที่แสดงผลได้ทันที ไม่ใช่ object ของเครื่องยนต์"""
    f = same_agency_view.findings[0]
    for value in (f.baseline_value, f.current_value, f.difference,
                  f.row_label, f.detail):
        assert isinstance(value, str)
    assert isinstance(f.flags, tuple)
    assert not hasattr(f, "key"), "🔴 T1BKey ดิบห้ามหลุดออกจากชั้นบริการ"


def test_s3_projection_has_no_absolute_paths(same_agency_view, blocked_view):
    for view in (same_agency_view, blocked_view):
        blob = json.dumps(
            [f.__dict__ for f in view.findings] + [view.summary.__dict__],
            ensure_ascii=False, default=str)
        assert privacy.find_absolute_paths(blob) == []


def test_s4_t1b_projection_is_not_the_t1a_finding_shape(same_agency_view):
    """🔴 finding ของ T1B **ห้าม**ถูกยัดลงรูปของ T1A"""
    f = same_agency_view.findings[0]
    for t1a_only in ("severity", "rule_id", "rule_version", "machine_status",
                     "confidence", "presentation_only", "review_status"):
        assert not hasattr(f, t1a_only), (
            f"{t1a_only!r} เป็นฟิลด์ของ T1A — ห้ามโผล่ในรูปของ T1B")
    for t1b_only in ("comparison_axis", "budget_category", "flags",
                     "baseline_category_table_year"):
        assert hasattr(f, t1b_only)


# ══════════════════════════════════════════════════════════════════════════════
#  S2 — READY / REVIEW REQUIRED เป็นค่าที่คำนวณได้ ไม่ใช่ปุ่ม
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("verdict,pending,expected", [
    (VERDICT_COMPARED, 0, svc.READY),
    (VERDICT_COMPARED, 1, svc.REVIEW_REQUIRED),
    (VERDICT_REVIEW_REQUIRED, 0, svc.REVIEW_REQUIRED),
    (VERDICT_REVIEW_REQUIRED, 5, svc.REVIEW_REQUIRED),
    (VERDICT_CANNOT_DETERMINE, 0, svc.CANNOT_DETERMINE),
    (VERDICT_CANNOT_DETERMINE, 9, svc.CANNOT_DETERMINE),
])
def test_s10_readiness_truth_table(verdict, pending, expected):
    assert svc.readiness_of(
        identity_verdict=verdict, requiring_review=pending) == expected


def test_s11_readiness_cannot_be_set_by_hand(same_agency_view):
    """🔴 *"computed state, not a button"* — ต้องไม่มีทางตั้งค่านี้ด้วยมือ"""
    with pytest.raises(Exception):
        same_agency_view.summary.readiness = svc.READY

    public = [n for n in dir(svc) if "readiness" in n.lower()]
    assert sorted(public) == ["READINESS_LABELS", "readiness_of"], public

    sig = inspect.signature(svc.readiness_of)
    assert set(sig.parameters) == {"identity_verdict", "requiring_review"}, (
        "🔴 ฟังก์ชันคำนวณต้องไม่รับ view หรือ connection — จะกลายเป็น setter ทันที")


def test_s12_readiness_is_not_persisted():
    """ค่าที่คำนวณได้ห้ามถูกเก็บ — เก็บเมื่อไรก็เพี้ยนจากความจริงเมื่อนั้น"""
    schema = inspect.getsource(t1b_repo)
    assert "readiness" not in schema.lower()


def test_s13_blocked_run_is_cannot_determine(blocked_view):
    s = blocked_view.summary
    assert s.identity_verdict == VERDICT_CANNOT_DETERMINE
    assert s.readiness == svc.CANNOT_DETERMINE
    assert s.automatic_pairs == 0
    assert s.identity_gate_blocked is True
    assert "ยืนยัน" in s.identity_verdict_label


def test_s14_healthy_run_is_review_required_when_work_remains(same_agency_view):
    s = same_agency_view.summary
    assert s.identity_verdict == VERDICT_COMPARED
    assert s.automatic_pairs > 0
    assert s.readiness in (svc.READY, svc.REVIEW_REQUIRED)
    assert (s.readiness == svc.REVIEW_REQUIRED) == (s.requiring_review > 0)


# ══════════════════════════════════════════════════════════════════════════════
#  S3 — finding_id ที่คงที่
# ══════════════════════════════════════════════════════════════════════════════


def test_s20_finding_id_is_stable_across_reruns(tmp_path):
    """รันซ้ำด้วยข้อมูลเดิม ⇒ id เดิมทุกใบ · คำตัดสินของคนจึงผูกกลับได้"""
    def run():
        base = records(build_workbook(
            tmp_path / "r1", filename="a.xlsx", agency="ก", cover_year=2569,
            section_title=TITLE))
        curr = records(build_workbook(
            tmp_path / "r2", filename="b.xlsx", agency="ก", cover_year=2570,
            section_title=TITLE, invest=12.0))
        return svc.run_from_records(base, curr, run_id="X")

    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    a = [f.finding_id for f in run().findings]
    b = [f.finding_id for f in run().findings]
    assert a == b and a


def test_s21_finding_ids_are_unique_within_a_run(same_agency_view, blocked_view):
    """🔴 id ซ้ำ ⇒ คำตัดสินผูกผิดใบ และปุ่มถัดไปวนกลับใบแรกตลอด"""
    for view in (same_agency_view, blocked_view):
        ids = [f.finding_id for f in view.findings]
        assert len(ids) == len(set(ids)), f"id ซ้ำ {len(ids) - len(set(ids))} ใบ"


def test_s22_the_two_sides_of_one_row_are_different_findings(same_agency_view):
    """แถวเดียวกันที่ตีความไม่ได้ ออกเป็นสองใบ ฝั่งละใบ — ต้องแยก id ออกจากกัน

    🔴 นี่คือสาเหตุการชนกันที่พบจริงตอนเขียนชั้นนี้: ``T1BKey`` ทั้งสองใบเท่ากัน
    เพราะเป็นแถวเดียวกัน สิ่งที่ต่างคือ *ฝั่งที่มีหลักฐาน* ซึ่งเป็นเนื้อหา ไม่ใช่ตำแหน่ง
    """
    by_side = {}
    for f in same_agency_view.findings:
        by_side.setdefault(f.side, []).append(f)
    assert svc.SIDE_BASELINE_ONLY in by_side and svc.SIDE_CURRENT_ONLY in by_side

    pairs = {(f.row_label, f.finding_type) for f in by_side[svc.SIDE_BASELINE_ONLY]} \
        & {(f.row_label, f.finding_type) for f in by_side[svc.SIDE_CURRENT_ONLY]}
    assert pairs, "ชุดทดสอบนี้ต้องมีแถวที่ปรากฏทั้งสองฝั่ง มิฉะนั้นไม่ได้วัดอะไร"


def test_s23_identity_basis_is_reported_honestly(same_agency_view):
    """id ที่ต้องพึ่งลำดับต้องถูกติดป้ายไว้ ห้ามเงียบ"""
    for f in same_agency_view.findings:
        assert f.identity_basis in (svc.BASIS_CONTENT, svc.BASIS_POSITION)
        assert f.id_is_stable == (f.identity_basis == svc.BASIS_CONTENT)
        if f.identity_basis == svc.BASIS_POSITION:
            assert "-" in f.finding_id


def test_s24_colliding_findings_get_position_basis_not_a_duplicate_id():
    """สร้างการชนกันโดยตรง แล้วยืนยันว่า id ไม่ซ้ำและถูกติดป้ายตามจริง"""
    from redbook.t1b.compare import CompareResult, Finding
    from redbook.t1b.keys import T1BKey

    key = T1BKey(agency_code="21011", document_level="agency",
                 sheet_role="SECTION_05", agency_identity="ก",
                 row_label_norm="รวมทั้งสิ้น")
    twin = Finding(finding_type=F_ROW_ADDED, key=key, fiscal_year=2570)
    result = CompareResult(findings=[twin, twin])

    view = svc.project_run(result, run_id="DUP")
    ids = [f.finding_id for f in view.findings]
    assert len(set(ids)) == 2, ids
    assert all(f.identity_basis == svc.BASIS_POSITION for f in view.findings)
    assert ids == [f"{ids[0].rsplit('-', 1)[0]}-1",
                   f"{ids[0].rsplit('-', 1)[0]}-2"]


# ══════════════════════════════════════════════════════════════════════════════
#  S4 — คิว: ค้นหา · ตัวกรอง · แบ่งหน้า · ก่อนหน้า/ถัดไป
# ══════════════════════════════════════════════════════════════════════════════


def test_s30_queue_paginates_without_losing_or_duplicating(same_agency_view):
    total = len(same_agency_view.findings)
    seen = []
    page = 1
    while True:
        p = svc.queue_page(same_agency_view, page=page, per_page=2)
        seen.extend(f.finding_id for f in p.items)
        if not p.has_next:
            break
        page += 1
    assert len(seen) == total
    assert len(set(seen)) == total, "🔴 แบ่งหน้าแล้วมีรายการซ้ำ"


def test_s31_out_of_range_page_is_clamped_not_an_error(same_agency_view):
    p = svc.queue_page(same_agency_view, page=9999, per_page=2)
    assert p.page == p.pages
    assert p.items, "หน้าสุดท้ายต้องมีรายการ ไม่ใช่หน้าว่าง"
    p0 = svc.queue_page(same_agency_view, page=0, per_page=2)
    assert p0.page == 1


def test_s32_per_page_is_bounded(same_agency_view):
    assert svc.queue_page(same_agency_view, per_page=10 ** 6).per_page == svc.MAX_PER_PAGE
    assert svc.queue_page(same_agency_view, per_page=0).per_page >= 1


def test_s33_only_review_filter_matches_the_summary_count(same_agency_view):
    p = svc.queue_page(same_agency_view, only_review=True, per_page=svc.MAX_PER_PAGE)
    assert p.total == same_agency_view.summary.requiring_review
    assert all(f.requires_human_decision for f in p.items)


def test_s34_type_filter_matches_the_summary_breakdown(same_agency_view):
    for ftype, n in same_agency_view.summary.by_type.items():
        p = svc.queue_page(same_agency_view, types=(ftype,),
                           per_page=svc.MAX_PER_PAGE)
        assert p.total == n, f"ตัวกรองชนิด {ftype} ได้ {p.total} ควรเป็น {n}"


def test_s35_flag_filter_matches_the_summary_breakdown(same_agency_view):
    for flag, n in same_agency_view.summary.by_flag.items():
        p = svc.queue_page(same_agency_view, flags=(flag,),
                           per_page=svc.MAX_PER_PAGE)
        assert p.total == n


def test_s36_search_requires_every_term_and_is_not_fuzzy(same_agency_view):
    """🔴 ค้นหาแบบตรงตัว ทุกคำต้องพบครบ — ผู้ใช้ต้องอธิบายผลได้"""
    target = same_agency_view.findings[0]
    p = svc.queue_page(same_agency_view, query=target.type_label,
                       per_page=svc.MAX_PER_PAGE)
    assert target.finding_id in [f.finding_id for f in p.items]

    p2 = svc.queue_page(same_agency_view,
                        query=f"{target.type_label} คำที่ไม่มีทางพบเลยจริง ๆ")
    assert p2.total == 0, "คำที่ไม่พบต้องตัดผลออก ไม่ใช่จับคล้าย ๆ"


def test_s37_search_ignores_surrounding_whitespace_and_case(same_agency_view):
    a = svc.queue_page(same_agency_view, query="  ROW  ", per_page=svc.MAX_PER_PAGE)
    b = svc.queue_page(same_agency_view, query="row", per_page=svc.MAX_PER_PAGE)
    assert a.total == b.total


def test_s38_filters_never_change_the_summary_numbers(same_agency_view):
    before = dict(same_agency_view.summary.by_type)
    svc.queue_page(same_agency_view, only_review=True, query="x")
    assert same_agency_view.summary.by_type == before
    assert same_agency_view.summary.total_findings == len(same_agency_view.findings)


def test_s40_prev_next_walk_the_filtered_queue(same_agency_view):
    p = svc.queue_page(same_agency_view, only_review=True,
                       per_page=svc.MAX_PER_PAGE)
    if p.total < 2:
        pytest.skip("ต้องมีอย่างน้อยสองรายการในคิวจึงจะทดสอบการเดินได้")
    ids = [f.finding_id for f in p.items]

    first = svc.finding_detail(same_agency_view, ids[0], only_review=True)
    assert first.prev_id == "" and first.next_id == ids[1]
    assert first.position == 1 and first.total == p.total

    last = svc.finding_detail(same_agency_view, ids[-1], only_review=True)
    assert last.next_id == "" and last.prev_id == ids[-2]


def test_s41_detail_outside_the_current_filter_has_no_neighbours(
        same_agency_view):
    """🔴 กดถัดไปแล้วต้องไม่หลุดออกนอกตัวกรองโดยไม่มีอะไรบอก"""
    outside = [f for f in same_agency_view.findings
               if not f.requires_human_decision]
    if not outside:
        pytest.skip("รอบนี้ไม่มีรายการที่อยู่นอกคิวตรวจ")
    d = svc.finding_detail(same_agency_view, outside[0].finding_id,
                           only_review=True)
    assert d is not None and d.position == 0
    assert d.prev_id == "" and d.next_id == ""


def test_s42_unknown_finding_id_returns_none(same_agency_view):
    assert svc.finding_detail(same_agency_view, "ไม่มีจริง") is None


# ══════════════════════════════════════════════════════════════════════════════
#  S6 — query string ของสถานะคิว
# ══════════════════════════════════════════════════════════════════════════════


def test_s45_filter_query_keeps_every_active_filter():
    """🔴 ลิงก์ต้องพาสถานะคิวไปครบ มิฉะนั้นกดแล้วเห็นรายการชุดอื่นเงียบ ๆ

    เคยประกอบด้วย Jinja macro แล้ว macro มองไม่เห็นตัวแปรบางตัวจาก context
    ทำให้ออกมาเป็น ``per_page=`` ที่ไม่มีค่า · ย้ายมาไว้ที่ชั้นบริการจึงทดสอบได้
    """
    qs = svc.filter_query(query="งบ ลงทุน", flags=("F1",), types=("T1", "T2"),
                          only_review=True, per_page=3, page=2)
    from urllib.parse import parse_qs

    got = parse_qs(qs)
    assert got["q"] == ["งบ ลงทุน"]
    assert got["flag"] == ["F1"]
    assert got["ftype"] == ["T1", "T2"]
    assert got["only_review"] == ["1"]
    assert got["per_page"] == ["3"]
    assert got["page"] == ["2"]


def test_s46_filter_query_omits_defaults_and_empties():
    assert svc.filter_query() == ""
    assert svc.filter_query(per_page=svc.DEFAULT_PER_PAGE) == ""
    assert "page=" not in svc.filter_query(query="x")


def test_s47_filter_query_escapes_special_characters():
    qs = svc.filter_query(query="a&b=c d")
    assert "&b=" not in qs.replace("q=a%26b%3Dc+d", "")
    from urllib.parse import parse_qs

    assert parse_qs(qs)["q"] == ["a&b=c d"]


# ══════════════════════════════════════════════════════════════════════════════
#  S5 — ที่เก็บที่แยกจาก T1A
# ══════════════════════════════════════════════════════════════════════════════


def test_s50_t1b_tables_are_separate_from_t1a(fresh_db):
    t1b_repo.init_t1b_schema(fresh_db)
    from redbook.storage.db import connect

    conn = connect(fresh_db)
    try:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        conn.close()
    assert {"t1b_runs", "t1b_findings"} <= names
    assert not (t1b_repo.T1A_TABLES & {"t1b_runs", "t1b_findings"})


def test_s51_t1b_repo_never_touches_t1a_tables():
    """🔴 ตรวจที่ระดับซอร์ส — ห้ามมี SQL ที่อ้างตารางของ T1A เลยแม้แต่บรรทัดเดียว"""
    src = inspect.getsource(t1b_repo)
    body = src.split("T1A_TABLES", 1)[0] + src.split("T1A_TABLES", 1)[1].split("\n", 2)[2]
    for table in ("FROM findings", "INTO findings", "UPDATE findings",
                  "FROM runs", "INTO runs", "UPDATE runs", "item_matches"):
        assert table not in body, f"ที่เก็บของ T1B อ้างตารางของ T1A: {table!r}"


def test_s52_save_and_read_back_preserves_every_finding(
        fresh_db, same_agency_view):
    t1b_repo.init_t1b_schema(fresh_db)
    rid = t1b_repo.save_run(same_agency_view, db_path=fresh_db)

    assert t1b_repo.count_findings(rid, fresh_db) == len(same_agency_view.findings)
    run = t1b_repo.get_run(rid, fresh_db)
    assert run["total_findings"] == same_agency_view.summary.total_findings
    assert run["identity_verdict"] == same_agency_view.summary.identity_verdict
    assert run["by_type"] == same_agency_view.summary.by_type


def test_s53_read_back_keeps_order_and_identity(fresh_db, same_agency_view):
    t1b_repo.init_t1b_schema(fresh_db)
    rid = t1b_repo.save_run(same_agency_view, db_path=fresh_db)
    rows = t1b_repo.list_findings(rid, fresh_db)
    assert [r["finding_id"] for r in rows] == \
           [f.finding_id for f in same_agency_view.findings]
    assert [r["ordinal"] for r in rows] == list(range(len(rows)))


def test_s54_saving_twice_replaces_and_does_not_duplicate(
        fresh_db, same_agency_view):
    t1b_repo.init_t1b_schema(fresh_db)
    rid = t1b_repo.save_run(same_agency_view, run_id="FIXED", db_path=fresh_db)
    t1b_repo.save_run(same_agency_view, run_id="FIXED", db_path=fresh_db)
    assert rid == "FIXED"
    assert t1b_repo.count_findings("FIXED", fresh_db) == \
           len(same_agency_view.findings)


def test_s55_blocked_run_is_stored_with_zero_automatic_pairs(
        fresh_db, blocked_view):
    t1b_repo.init_t1b_schema(fresh_db)
    rid = t1b_repo.save_run(blocked_view, db_path=fresh_db)
    run = t1b_repo.get_run(rid, fresh_db)
    assert run["automatic_pairs"] == 0
    assert run["identity_blocked"] is True
    assert run["identity_verdict"] == VERDICT_CANNOT_DETERMINE
    # 🔴 ยังต้องเก็บ finding ครบ — ห้ามหายไปเพราะด่านไม่ผ่าน
    assert t1b_repo.count_findings(rid, fresh_db) == len(blocked_view.findings)


def test_s56_delete_run_removes_both_tables(fresh_db, same_agency_view):
    t1b_repo.init_t1b_schema(fresh_db)
    rid = t1b_repo.save_run(same_agency_view, db_path=fresh_db)
    t1b_repo.delete_run(rid, fresh_db)
    assert t1b_repo.get_run(rid, fresh_db) is None
    assert t1b_repo.count_findings(rid, fresh_db) == 0


def test_s57_stored_rows_have_no_absolute_paths(fresh_db, same_agency_view):
    t1b_repo.init_t1b_schema(fresh_db)
    rid = t1b_repo.save_run(same_agency_view, db_path=fresh_db)
    blob = json.dumps(t1b_repo.list_findings(rid, fresh_db),
                      ensure_ascii=False, default=str)
    assert privacy.find_absolute_paths(blob) == []
