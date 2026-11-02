# -*- coding: utf-8 -*-
"""ทดสอบ G5: การหยุดเมื่อ schema conflict · ตรวจซ้ำได้ · หลักฐานชี้กลับ · การสุ่มแบ่งชั้น"""
from conftest_t1 import DEFAULT_DEFS, make_row, write_t1
from redbook.t1 import SAMPLING_SEED
from redbook.t1.protocol import (SCHEMA_CONFLICT_CATEGORY, STATUS_COMPLETED,
                                 STATUS_HALTED_SCHEMA_CONFLICT, result_hash,
                                 run_comparison, stratified_sample, verify_evidence)


def _pair(tmp_path, rows_a, rows_b, defs_b=None, physical_b=None):
    a = write_t1(tmp_path / "a.xlsx", rows_a)
    b = write_t1(tmp_path / "b.xlsx", rows_b, defs=defs_b, physical_names=physical_b)
    return a, b


# ------------------------------------------------- schema conflict halt
def test_schema_conflict_halts_before_any_content_comparison(tmp_path):
    """คำตัดสิน P1: ต้องหยุด ไม่สร้างรายการเพิ่ม/หาย/ยอดเปลี่ยนใด ๆ"""
    defs_b = [(n, "รายการ" if n == "item_name" else d) for n, d in DEFAULT_DEFS]
    a, b = _pair(tmp_path,
                 [make_row(item="รายการรายจ่ายประจำ", amount=1000)],
                 [make_row(item="ค่าหนังสือเรียน", amount=500)], defs_b=defs_b)

    run = run_comparison(a, b, "A", "B")
    assert run.status == STATUS_HALTED_SCHEMA_CONFLICT
    assert run.record_counts == {"a": 0, "b": 0}          # ไม่โหลดข้อมูลเลย

    cats = {f["category"] for f in run.findings}
    assert cats == {SCHEMA_CONFLICT_CATEGORY}
    assert not any(c in cats for c in ("C1", "C2", "C3", "C4", "C5", "C6", "C7"))

    f = run.findings[0]
    assert f["datadict_field"] == "item_name"
    assert f["field_a"]["definition"] == "ลักษณะรายจ่าย"
    assert f["field_b"]["definition"] == "รายการ"
    assert f["machine_status"] == "needs_human"
    assert f["review_status"] == "pending"
    assert "ไม่เริ่มการเปรียบเทียบเนื้อหาระดับรายการ" in f["action_taken"]
    assert run.halt_reason
    assert run.summary["settled_count"] == 0


def test_no_conflict_runs_content_comparison(tmp_path):
    physical = [d[0] for d in DEFAULT_DEFS]
    physical[8] = "objc_5"                    # ชื่อคอลัมน์ต่าง แต่นิยามตรง
    a, b = _pair(tmp_path, [make_row(amount=1000)], [make_row(amount=900)],
                 physical_b=physical)
    run = run_comparison(a, b, "A", "B")
    assert run.status == STATUS_COMPLETED
    assert run.record_counts == {"a": 1, "b": 1}
    assert run.findings[0]["category"] == "C1"
    assert run.findings[0]["amount_diff"] == -100
    drifts = run.schema_report["side_b"]["mapping"]["physical_name_drifts"]
    assert any("objc_5" in d for d in drifts)


# ------------------------------------------------------ reproducibility
def test_same_inputs_give_same_result_hash(tmp_path):
    a, b = _pair(tmp_path,
                 [make_row(item="ก", amount=1000), make_row(item="ข", amount=200)],
                 [make_row(item="ก", amount=900)])
    r1 = run_comparison(a, b, "A", "B")
    r2 = run_comparison(a, b, "A", "B")
    assert r1.result_hash == r2.result_hash
    assert r1.result_hash


def test_changed_amount_changes_result_hash(tmp_path):
    a, b1 = _pair(tmp_path, [make_row(amount=1000)], [make_row(amount=900)])
    b2 = write_t1(tmp_path / "b2.xlsx", [make_row(amount=800)])
    h1 = run_comparison(a, b1, "A", "B").result_hash
    h2 = run_comparison(a, b2, "A", "B").result_hash
    assert h1 != h2


def test_result_hash_ignores_order_of_findings():
    f1 = {"category": "C1", "key": ["a"], "amount_a": 1, "amount_b": 0,
          "amount_diff": -1, "match_level": "exact", "match_step": 1,
          "evidence_a": {"amount_cell": "M2"}, "evidence_b": {"amount_cell": "M2"}}
    f2 = {"category": "C3", "key": ["b"], "amount_a": 5, "amount_b": 5,
          "amount_diff": 0, "match_level": "exact", "match_step": 1,
          "evidence_a": {"amount_cell": "M3"}, "evidence_b": {"amount_cell": "M3"}}
    assert result_hash([f1, f2]) == result_hash([f2, f1])


# ---------------------------------------------------- evidence check
def test_evidence_points_back_to_real_cells(tmp_path):
    a, b = _pair(tmp_path,
                 [make_row(item="ก", amount=1000), make_row(item="ข", amount=250)],
                 [make_row(item="ก", amount=900), make_row(item="ข", amount=250)])
    run = run_comparison(a, b, "A", "B")
    check = verify_evidence(run, a, b)
    assert check["checked"] > 0
    assert check["mismatched"] == 0
    assert check["resolvable_pct"] == 100.0


# --------------------------------------------------- stratified sample
def test_stratified_sample_covers_every_stratum(tmp_path):
    rows_a = [make_row(item=f"รายการ {i}", amount=1000 + i) for i in range(6)]
    rows_b = [make_row(item="รายการ 0", amount=900),          # C1
              make_row(item="รายการ 1", amount=2000),         # C2
              make_row(item="รายการ 2", amount=1002),         # C3
              make_row(item="รายการ 3", act="กิจกรรม ข", amount=1003),  # C6
              make_row(item="รายการใหม่", amount=77)]         # C4
    a, b = _pair(tmp_path, rows_a, rows_b)
    run = run_comparison(a, b, "A", "B")

    result = stratified_sample([("run1", run)], size=4, seed=SAMPLING_SEED)
    assert result["seed"] == SAMPLING_SEED
    assert result["selected_size"] == 4
    assert result["strata_count"] >= 4
    assert len({i["stratum"]["category"] for i in result["items"]}) == 4
    assert "ไม่ใช่ค่าความแม่นยำของประชากรทั้งหมด" in result["limitation_note"]

    again = stratified_sample([("run1", run)], size=4, seed=SAMPLING_SEED)
    assert [i["finding_index"] for i in again["items"]] == \
           [i["finding_index"] for i in result["items"]]


def test_sample_size_larger_than_population_is_capped(tmp_path):
    a, b = _pair(tmp_path, [make_row(amount=1000)], [make_row(amount=900)])
    run = run_comparison(a, b, "A", "B")
    result = stratified_sample([("r", run)], size=50, seed=SAMPLING_SEED)
    assert result["selected_size"] == len(run.findings)
