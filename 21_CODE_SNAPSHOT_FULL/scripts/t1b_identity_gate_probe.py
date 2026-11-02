# -*- coding: utf-8 -*-
"""T1B — probe ก่อน/หลัง ของด่านตัวตนหน่วยงานแบบ fail-closed

🔴 สคริปต์นี้เขียนด้วย **API ที่มีอยู่แล้วตั้งแต่ ``bb399a0``** เท่านั้น
จึงรันได้ทั้งบน commit ก่อนแก้และหลังแก้ ⇒ ใช้เป็นหลักฐาน before/after ได้จริง
(ไฟล์ทดสอบ ``tests/test_t1b_identity_gate.py`` import ค่าคงที่ตัวใหม่
จึง *collect ไม่ผ่าน* บน ``bb399a0`` ซึ่งไม่ใช่หลักฐานเชิงพฤติกรรม)

    python scripts/t1b_identity_gate_probe.py

ออก ``0`` เมื่อผ่านทุกฉาก · ออก ``1`` เมื่อมีฉากใดละเมิดสัญญา fail-closed

สัญญาที่ probe นี้วัด — เมื่อ **ยังพิสูจน์ไม่ได้** ว่าสองแฟ้มเป็นหน่วยงานเดียวกัน

1. ห้ามมีคู่ที่จับอัตโนมัติแม้แต่คู่เดียว
2. ห้ามสรุปเองว่าแถวถูกเพิ่ม/ถูกลบ (``ROW_ADDED`` / ``ROW_REMOVED``)
3. ห้ามสรุปเองว่ายอดเพิ่ม/ลด (``AMOUNT_*``)
4. ทุก record ต้องยังถูกนับครบ และรู้ว่ามาจากฝั่งใด

🔴 **SYNTHETIC** — สมุดงานในสคริปต์นี้แต่งขึ้นทั้งหมด ห้ามรายงานผลว่าเป็น
ข้อผิดพลาดที่พบในเอกสารจริง

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("REDBOOK_DATA_DIR", tempfile.mkdtemp(prefix="probe_"))

from redbook.adapters.ao_workbook import AOWorkbookAdapter          # noqa: E402
from redbook.t1b.compare import compare                              # noqa: E402
from redbook.t1b.matching import (                                   # noqa: E402
    SIDE_BASELINE,
    SIDE_CURRENT,
    match_records,
)

TITLE = "6. สรุปงบประมาณประจำปีงบประมาณ พ.ศ. 2570"


def _build(tmp: Path, *, filename, agency, invest=10.0):
    import openpyxl

    wb = openpyxl.Workbook()
    first = wb.active

    def category(ws):
        ws["A1"] = TITLE
        ws["E2"] = "หน่วย : ล้านบาท"
        ws["A3"] = "รายการ"
        ws["C3"], ws["D3"], ws["E3"] = "งบลงทุน", "งบเงินอุดหนุน", "รวม"
        ws["A4"] = "รวมทั้งสิ้น"
        ws["C4"], ws["D4"], ws["E4"] = invest, 5.0, invest + 5.0

    if agency is None:
        first.title = "หมวด"
        category(first)
    else:
        first.title = "ปก"
        first["A2"] = "กระทรวงทดสอบ"
        first["A3"] = agency
        first["A5"] = "ปี 2570"
        category(wb.create_sheet("หมวด"))
    path = tmp / filename
    wb.save(path)
    wb.close()
    return [e.canonical_record for e in AOWorkbookAdapter().extract(path)]


def _refused(base, curr) -> list[str]:
    """คืนรายการข้อละเมิดสัญญา fail-closed — ว่าง = ผ่าน"""
    m = match_records(base, curr)
    c = compare(m)
    types = c.by_type()
    bad = []
    if m.matched:
        bad.append(f"จับคู่อัตโนมัติ {len(m.matched)} คู่")
    for t in ("ROW_ADDED", "ROW_REMOVED"):
        if types.get(t):
            bad.append(f"{t} {types[t]} ใบ")
    amounts = sum(v for k, v in types.items() if k.startswith("AMOUNT_"))
    if amounts:
        bad.append(f"AMOUNT_* {amounts} ใบ")
    if m.accounted() != len(base) + len(curr):
        bad.append(f"accounted {m.accounted()} ≠ {len(base) + len(curr)}")
    sides = [sr.side for sr in m.needs_human]
    if sides.count(SIDE_BASELINE) != len(base) or sides.count(SIDE_CURRENT) != len(curr):
        bad.append("provenance สองฝั่งไม่ครบในคิวมนุษย์")
    return bad


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="probe_wb_"))
    blind_a = _build(tmp, filename="blind_a.xlsx", agency=None)
    blind_b = _build(tmp, filename="blind_b.xlsx", agency=None, invest=12.0)
    named_a = _build(tmp, filename="named_a.xlsx", agency="หน่วยงาน ก")
    named_b = _build(tmp, filename="named_b.xlsx", agency="หน่วยงาน ข")
    same_a = _build(tmp, filename="same_a.xlsx", agency="หน่วยงานเดียวกัน")
    same_b = _build(tmp, filename="same_b.xlsx", agency="หน่วยงานเดียวกัน", invest=12.0)

    failures = 0

    for name, base, curr in (
        ("S1 ตัวตนว่างทั้งสองฝั่ง", blind_a, blind_b),
        ("S2 ตัวตนว่างฝั่งเดียว", blind_a, named_a),
        ("S2b ตัวตนว่างอีกฝั่ง", named_a, blind_a),
        ("S3 ชื่อหน่วยงานขัดแย้งกัน", named_a, named_b),
    ):
        bad = _refused(base, curr)
        if bad:
            failures += 1
            print(f"FAIL  {name} — ยังตัดสินอัตโนมัติ: {'; '.join(bad)}")
        else:
            print(f"ok    {name} — ปฏิเสธการจับคู่อัตโนมัติครบตามสัญญา")

    m = match_records(same_a, same_b)
    if m.matched and m.accounted() == len(same_a) + len(same_b):
        print(f"ok    S4 หน่วยงานเดียวกัน — ยังจับคู่ได้ {len(m.matched)} คู่")
    else:
        failures += 1
        print("FAIL  S4 หน่วยงานเดียวกัน — ด่านปิดงานที่ควรผ่าน")

    print(f"\nสรุป: ละเมิดสัญญา {failures} ฉาก")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
