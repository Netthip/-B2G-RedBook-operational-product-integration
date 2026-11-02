# -*- coding: utf-8 -*-
"""ทดสอบหลักการหลัก: เครื่องไม่ตัดสินว่าผิด และห้ามเดาค่าที่ไม่มีในเอกสาร"""
import pytest

from redbook.core.canonical import (CanonicalDocument, CanonicalItem,
                                    NULL_NOT_IN_DOCUMENT, NULL_NOT_MAPPED)
from redbook.core.status import (COLOR_BLUE, COLOR_GRAY, COLOR_GREEN, COLOR_RED,
                                 COLOR_YELLOW, MachineStatus, ReviewStatus,
                                 effective_status, status_color)
from redbook.rules import catalog


def test_machine_status_has_no_error_verdict():
    """สถานะที่ระบบตั้งเองได้ ต้องไม่มีค่าที่แปลว่า 'ผิด'"""
    values = {s.value for s in MachineStatus}
    assert "confirmed_error" not in values
    assert not any("error" in v for v in values)


def test_no_rule_defaults_to_a_verdict():
    """กฎทุกข้อในบัญชี ต้องมีสถานะเริ่มต้นอยู่ในกลุ่มที่เครื่องตั้งได้เท่านั้น"""
    allowed = {s.value for s in MachineStatus}
    for r in catalog.RULES:
        assert r.default_machine_status in allowed, r.rule_id


def test_review_decision_overrides_machine_status():
    assert effective_status(MachineStatus.DIFF_FOUND,
                            ReviewStatus.PENDING) == MachineStatus.DIFF_FOUND
    assert effective_status(MachineStatus.DIFF_FOUND,
                            ReviewStatus.CONFIRMED_ERROR) == ReviewStatus.CONFIRMED_ERROR


@pytest.mark.parametrize("machine,review,pres,expected", [
    (MachineStatus.MATCH, ReviewStatus.PENDING, False, COLOR_GREEN),
    (MachineStatus.DIFF_FOUND, ReviewStatus.PENDING, False, COLOR_YELLOW),
    (MachineStatus.NEEDS_HUMAN, ReviewStatus.PENDING, False, COLOR_YELLOW),
    (MachineStatus.LIKELY_YEAR_CHANGE, ReviewStatus.PENDING, False, COLOR_BLUE),
    (MachineStatus.LIKELY_REDUCTION, ReviewStatus.PENDING, False, COLOR_BLUE),
    (MachineStatus.DIFF_FOUND, ReviewStatus.PENDING, True, COLOR_GRAY),
    (MachineStatus.DIFF_FOUND, ReviewStatus.CONFIRMED_ERROR, False, COLOR_RED),
    (MachineStatus.DIFF_FOUND, ReviewStatus.CONFIRMED_VALID_CHANGE, True, COLOR_GREEN),
])
def test_status_colors(machine, review, pres, expected):
    assert status_color(machine, review, pres) == expected


def test_set_null_requires_reason():
    item = CanonicalItem(document_id="D1")
    item.set_null("amount", NULL_NOT_MAPPED)
    assert item.amount is None
    assert item.null_reason("amount") == NULL_NOT_MAPPED

    with pytest.raises(ValueError):
        item.set_null("unit", "")
    with pytest.raises(KeyError):
        item.set_null("field_that_does_not_exist", NULL_NOT_IN_DOCUMENT)


def test_document_set_null_guards():
    doc = CanonicalDocument(document_id="D1")
    doc.set_null("fiscal_year", NULL_NOT_IN_DOCUMENT)
    assert doc.fiscal_year is None
    assert doc.nulls["fiscal_year"] == NULL_NOT_IN_DOCUMENT
    with pytest.raises(KeyError):
        doc.set_null("nope", NULL_NOT_IN_DOCUMENT)
