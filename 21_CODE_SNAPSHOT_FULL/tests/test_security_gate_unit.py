# -*- coding: utf-8 -*-
"""Security gate — กลไกของ runner: matrix · กติกาสถานะ (fail-closed) · การกลบ · junit"""
import os
from pathlib import Path

import pytest

from security_gate import DEFAULT_PROFILE
from security_gate.evaluate import CheckResult, control_status, evaluate, summarize
from security_gate.matrix import (MATRIX_COLUMNS, Control, MatrixError, load_matrix,
                                          validate_rows)
from security_gate.redact import has_absolute_path, redact_text
from security_gate.runner import Runner

HEADER = ",".join(MATRIX_COLUMNS)


def _row(cid="SG-X", app="APPLICABLE", cond="", checks="H:a; T:tests/t.py::test_b",
         disp="auto: ..."):
    return f'{cid},1 cat,V1.1.1,1,ctl,{app},{cond},"{checks}",expected,evidence,{disp}'


def _write_matrix(tmp_path, *rows):
    p = tmp_path / "m.csv"
    p.write_text(HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return p


def _ctl(**kw) -> Control:
    base = dict(control_id="SG-X", category="1 cat", asvs_ref="V1.1.1", asvs_level="1",
                control="c", applicability="APPLICABLE", profile_condition="",
                checks=("H:a", "T:tests/t.py::test_b"), expected_result="e",
                evidence_type="ev", disposition="auto: ...")
    base.update(kw)
    return Control(**base)


# ------------------------------------------------------------------ matrix
def test_matrix_loads_and_hashes(tmp_path):
    p = _write_matrix(tmp_path, _row())
    m = load_matrix(p)
    assert len(m.sha256) == 64 and m.controls[0].checks == ("H:a", "T:tests/t.py::test_b")
    assert m.referenced_checks("T") == ["T:tests/t.py::test_b"]


def test_matrix_rejects_wrong_columns(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("control_id,control\nX,y\n", encoding="utf-8")
    with pytest.raises(MatrixError):
        load_matrix(p)


@pytest.mark.parametrize("row,needle", [
    (_row(app="MAYBE"), "applicability"),
    (_row(app="CONDITIONAL", cond=""), "profile_condition"),
    (_row(checks=""), "test_method ว่าง"),
    (_row(checks="Q:unknown"), "รูปแบบไม่ถูกต้อง"),
])
def test_matrix_validation_errors(tmp_path, row, needle):
    p = _write_matrix(tmp_path, row)
    with pytest.raises(MatrixError) as exc:
        load_matrix(p)
    assert needle in str(exc.value)


def test_matrix_duplicate_ids_rejected():
    errs = validate_rows([dict(zip(MATRIX_COLUMNS, _row().split(","))),
                          dict(zip(MATRIX_COLUMNS, _row().split(",")))])
    assert any("ซ้ำ" in e for e in errs)


# ------------------------------------------------------------------ evaluate (fail-closed)
def _res(**kw):
    return {k: CheckResult(k, v) for k, v in kw.items()}


def test_all_pass_gives_pass():
    s = control_status(_ctl(), {"H:a": CheckResult("H:a", "PASS"),
                                "T:tests/t.py::test_b": CheckResult("T:tests/t.py::test_b", "PASS")},
                       DEFAULT_PROFILE)
    assert s.status == "PASS"


def test_missing_check_is_review_never_pass():
    s = control_status(_ctl(), {"H:a": CheckResult("H:a", "PASS")}, DEFAULT_PROFILE)
    assert s.status == "REVIEW" and "NOT_RUN" in s.reason


def test_incomplete_check_is_review():
    s = control_status(_ctl(), {"H:a": CheckResult("H:a", "PASS"),
                                "T:tests/t.py::test_b": CheckResult("T:tests/t.py::test_b", "INCOMPLETE")},
                       DEFAULT_PROFILE)
    assert s.status == "REVIEW"


def test_any_fail_is_fail_even_if_others_incomplete():
    s = control_status(_ctl(), {"H:a": CheckResult("H:a", "FAIL")}, DEFAULT_PROFILE)
    assert s.status == "FAIL"


def test_recorded_only_cannot_pass_an_applicable_control():
    s = control_status(_ctl(checks=("H:x",)), {"H:x": CheckResult("H:x", "RECORDED")}, DEFAULT_PROFILE)
    assert s.status == "REVIEW"


def test_manual_control_is_review_even_when_checks_pass():
    s = control_status(_ctl(disposition="manual: ..."),
                       {"H:a": CheckResult("H:a", "PASS"),
                        "T:tests/t.py::test_b": CheckResult("T:tests/t.py::test_b", "PASS")},
                       DEFAULT_PROFILE)
    assert s.status == "REVIEW"
    s2 = control_status(_ctl(disposition="manual: ..."),
                        {"H:a": CheckResult("H:a", "PASS"),
                         "T:tests/t.py::test_b": CheckResult("T:tests/t.py::test_b", "PASS")},
                        DEFAULT_PROFILE, {"SG-X": {"disposition": "ACCEPTED_RISK", "reason": "r"}})
    assert s2.status == "REVIEW" and s2.manual_disposition["disposition"] == "ACCEPTED_RISK"
    # มี accepted_by (ผู้มีอำนาจรับแล้ว) ⇒ PASS · REVIEW_REQUIRED ⇒ ยัง REVIEW แม้มี accepted_by
    checks = {"H:a": CheckResult("H:a", "PASS"),
              "T:tests/t.py::test_b": CheckResult("T:tests/t.py::test_b", "PASS")}
    s3 = control_status(_ctl(disposition="manual: ..."), checks, DEFAULT_PROFILE,
                        {"SG-X": {"disposition": "FALSE_POSITIVE", "reason": "r", "accepted_by": "Bo"}})
    assert s3.status == "PASS"
    s4 = control_status(_ctl(disposition="manual: ..."), checks, DEFAULT_PROFILE,
                        {"SG-X": {"disposition": "REVIEW_REQUIRED", "reason": "r", "accepted_by": "Bo"}})
    assert s4.status == "REVIEW"
    s5 = control_status(_ctl(disposition="manual: ..."),
                        {"H:a": CheckResult("H:a", "FAIL"), "T:tests/t.py::test_b": CheckResult("T:tests/t.py::test_b", "PASS")},
                        DEFAULT_PROFILE, {"SG-X": {"disposition": "FALSE_POSITIVE", "accepted_by": "Bo"}})
    assert s5.status == "FAIL"     # disposition ไม่ลบล้าง check ที่ FAIL


def test_conditional_is_na_under_loopback_but_evaluated_under_tls():
    c = _ctl(applicability="CONDITIONAL", profile_condition="TLS only", checks=("H:x",))
    assert control_status(c, {}, "LOOPBACK_HTTP").status == "NOT_APPLICABLE"
    assert control_status(c, {}, "NETWORK_TLS").status == "REVIEW"
    assert control_status(c, {"H:x": CheckResult("H:x", "PASS")}, "NETWORK_TLS").status == "PASS"


def test_not_applicable_declared_stays_na_even_if_check_fails():
    c = _ctl(applicability="NOT_APPLICABLE", profile_condition="no auth", checks=("T:tests/t.py::x",))
    assert control_status(c, {"T:tests/t.py::x": CheckResult("T:tests/t.py::x", "FAIL")},
                          DEFAULT_PROFILE).status == "NOT_APPLICABLE"


def test_summary_counts_applicable_excludes_na(tmp_path):
    p = _write_matrix(tmp_path, _row("SG-1"), _row("SG-2", app="NOT_APPLICABLE", cond="n/a"),
                      _row("SG-3", checks="H:a"))
    m = load_matrix(p)
    st = evaluate(m, {"H:a": CheckResult("H:a", "PASS")}, DEFAULT_PROFILE)
    c = summarize(st)
    assert c == {"declared": 3, "PASS": 1, "FAIL": 0, "REVIEW": 1, "NOT_APPLICABLE": 1,
                 "applicable": 2}


def test_check_result_rejects_unknown_status():
    with pytest.raises(ValueError):
        CheckResult("H:a", "MAYBE")


# ------------------------------------------------------------------ redact
@pytest.mark.parametrize("text", [
    r"error at C:\Users\someone\dev\x\app.py line 3",
    "file:///C:/Users/someone/x.txt",
    "/home/someone/project/app.py",
    "/Users/someone/project/app.py",
    r"\\server\share\x.xlsx",
    r'raise RuntimeError("C:\\Users\\someone\\private\\x.sqlite")',   # ซอร์สใน traceback (backslash คู่)
], ids=["win-path", "file-uri", "posix-home", "mac-home", "unc", "doubled-backslash"])
# ids ตั้งเอง — ไม่ให้ pytest ใช้ค่าพารามิเตอร์ (ที่เป็นเส้นทางสมมติ) เป็น nodeid ซึ่งจะโผล่ในหลักฐาน
def test_redact_removes_absolute_paths(text):
    out = redact_text(text)
    assert "someone" not in out and "share" not in out
    assert not has_absolute_path(out)


def test_redact_keeps_relative_paths_and_urls():
    s = "tests/test_web.py::test_x passed · http://127.0.0.1:8600/healthz · redbook/app.py"
    assert redact_text(s) == s


# ------------------------------------------------------------------ evidence writer
def test_evidence_writer_uses_lf_and_redacts(tmp_path):
    """แฮชหลักฐานต้องเท่ากันทุก checkout ⇒ เขียน LF เสมอ แม้บน Windows และกลบเส้นทางก่อนเขียน"""
    from security_gate.runner import _write
    p = tmp_path / "x.txt"
    _write(p, "a\r\nb\nC:\\Users\\someone\\x\n")
    raw = p.read_bytes()
    assert b"\r" not in raw
    assert b"someone" not in raw and b"<path>" in raw


# ------------------------------------------------------------------ junit parsing
def test_junit_parse_maps_classname_to_nodeid(tmp_path):
    x = tmp_path / "j.xml"
    x.write_text('<testsuites><testsuite><testcase classname="tests.test_web" name="test_a"/>'
                 '<testcase classname="tests.test_web" name="test_b[1]"><failure/></testcase>'
                 '<testcase classname="tests.test_web" name="test_c"><skipped/></testcase>'
                 '</testsuite></testsuites>', "utf-8")
    out = Runner._parse_junit(x)
    assert out == {"tests/test_web.py::test_a": "passed", "tests/test_web.py::test_b[1]": "failed",
                   "tests/test_web.py::test_c": "skipped"}


def test_junit_parse_missing_or_broken_is_empty(tmp_path):
    assert Runner._parse_junit(tmp_path / "none.xml") == {}
    b = tmp_path / "b.xml"
    b.write_text("<not xml", "utf-8")
    assert Runner._parse_junit(b) == {}


# ------------------------------------------------------------------ real matrix (ถ้ามี)
def test_declared_matrix_loads_if_available():
    p = os.environ.get("SECURITY_GATE_MATRIX")
    if not p or not Path(p).exists():
        pytest.skip("SECURITY_GATE_MATRIX ไม่ได้ตั้ง — matrix จริงอยู่ใน repo สาธารณะ")
    m = load_matrix(p)
    assert len(m.controls) >= 40
    ids = [c.control_id for c in m.controls]
    assert ids == sorted(ids, key=lambda s: int(s.split("-")[1]))
