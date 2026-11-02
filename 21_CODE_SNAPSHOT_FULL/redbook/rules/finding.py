# -*- coding: utf-8 -*-
"""ตัวสร้างผลตรวจหนึ่งประเด็น (finding) ให้มีรูปแบบเดียวกันทั้งระบบ

ทุก finding ต้องมีครบตามข้อกำหนดรายงาน: รหัส ประเภท ระดับความสำคัญ ค่า A ค่า B
ผลต่าง หน่วย ตำแหน่ง A ตำแหน่ง B กฎที่ใช้ เหตุผล confidence สถานะ ผู้ยืนยัน
วันเวลา หมายเหตุ และหลักฐานประกอบ

finding_key คำนวณจาก "เนื้อหา" ไม่ใช่ลำดับการรัน จึงคงที่เมื่อรันซ้ำด้วยไฟล์เดิม
และกฎเวอร์ชันเดิม ทำให้ผูกคำตัดสินของมนุษย์ข้ามการรันได้
"""
import json

from . import catalog
from ..core.hashing import sha256_text

# ตัวคั่นสำหรับต่อสตริงก่อนแฮช ใช้อักขระ ASCII unit separator ซึ่งไม่ปรากฏในข้อมูลจริง
# ป้องกันไม่ให้ค่าคนละช่องต่อกันแล้วได้แฮชชนกัน
SEP = chr(31)

# เครื่องหมายแทน "ไม่มีค่า" ในการคำนวณแฮช แยกจากข้อความว่างที่เอกสารมีจริง
NULL_MARK = "<null>"

_SEV_ORDER = {"high": 1, "medium": 2, "low": 3, "info": 4}

_LOC_KEYS = ("source_file_id", "source_type", "sheet_name", "cell_reference",
             "row_number", "column_letter", "page_number", "table_number",
             "line_number")


def _canon(value) -> str:
    if value is None:
        return NULL_MARK
    if isinstance(value, float):
        # ตรึงรูปแบบทศนิยมให้คงที่ ไม่ให้ผลแฮชเปลี่ยนตามวิธีพิมพ์ค่า
        return format(value, ".6f")
    return str(value)


def _loc_canon(loc: dict) -> str:
    if not loc:
        return ""
    return "|".join(f"{k}={_canon(loc.get(k))}" for k in _LOC_KEYS)


def make_finding(rule_id: str, reason: str, *, check_type: str = None,
                 severity: str = None, machine_status: str = None,
                 value_a=None, value_b=None, diff_value=None, diff_pct=None,
                 unit: str = None, loc_a: dict = None, loc_b: dict = None,
                 confidence: float = None, confidence_basis: str = None,
                 presentation_only: bool = None, evidence: dict = None,
                 sort_key: str = "") -> dict:
    """สร้าง finding หนึ่งรายการ โดยดึงค่าเริ่มต้นจาก Rule Catalog"""
    rule = catalog.get(rule_id)
    loc_a = loc_a or {}
    loc_b = loc_b or {}

    if confidence is not None and not confidence_basis:
        raise ValueError("ถ้าระบุ confidence ต้องระบุที่มาของคะแนนด้วย")

    key_payload = SEP.join([
        rule_id, rule.version,
        check_type or rule.title,
        _loc_canon(loc_a), _loc_canon(loc_b),
        _canon(value_a), _canon(value_b),
    ])
    finding_key = sha256_text(key_payload)
    severity_value = severity or rule.default_severity

    return {
        "id": "",                       # เติมตอนบันทึก (ผูกกับ run_id)
        "finding_code": "",             # เติมตอนบันทึก (เรียงตาม sort_key)
        "finding_key": finding_key,
        "check_type": check_type or rule.title,
        "severity": severity_value,
        "rule_id": rule_id,
        "rule_version": rule.version,
        "reason": reason,
        "value_a": None if value_a is None else str(value_a),
        "value_b": None if value_b is None else str(value_b),
        "diff_value": diff_value,
        "diff_pct": diff_pct,
        "unit": unit,
        "loc_a": loc_a,
        "loc_b": loc_b,
        "machine_status": machine_status or rule.default_machine_status,
        "presentation_only": (rule.presentation_only if presentation_only is None
                              else presentation_only),
        "confidence": confidence,
        "confidence_basis": confidence_basis,
        "evidence": evidence or {},
        "sort_key": sort_key or f"{_SEV_ORDER.get(severity_value, 9)}-{rule_id}",
    }


def assign_ids(run_id: str, findings: list) -> list:
    """เรียงลำดับให้คงที่ แล้วออกรหัสอ่านง่าย F-0001 ตามลำดับนั้น"""
    ordered = sorted(findings, key=lambda f: (f["sort_key"], f["finding_key"]))
    for i, f in enumerate(ordered, start=1):
        f["finding_code"] = f"F-{i:04d}"
        f["id"] = sha256_text(SEP.join([run_id, f["finding_key"]]))[:32]
    return ordered


def result_hash(findings: list) -> str:
    """แฮชผลตรวจทั้งชุด ใช้พิสูจน์ว่ารันซ้ำด้วยไฟล์และกฎเดิมแล้วได้ผลเดิม

    คิดจากเนื้อหาของ finding เท่านั้น ไม่รวม run_id เวลา หรือคำตัดสินของมนุษย์
    """
    payload = [
        {"k": f["finding_key"], "rule": f["rule_id"], "rv": f["rule_version"],
         "a": f.get("value_a"), "b": f.get("value_b"),
         "d": _canon(f.get("diff_value")), "st": f["machine_status"],
         "la": _loc_canon(f.get("loc_a")), "lb": _loc_canon(f.get("loc_b"))}
        for f in findings
    ]
    payload.sort(key=lambda d: d["k"])
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))
