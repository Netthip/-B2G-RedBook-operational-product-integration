# -*- coding: utf-8 -*-
"""แปลงชีต `data` ของไฟล์ T1 เป็น CanonicalT1Record ตาม semantic mapping

อ่านอย่างเดียวเสมอ · ไม่เดาค่า · ฟิลด์บังคับที่ว่างจะโยน DataQualityHalt
พร้อมตำแหน่งเซลล์ที่เป็นต้นเหตุ
"""
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from .canonical import (CanonicalT1Record, DataQualityHalt, EvidenceLocation,
                        UNIT_CONFIRMED)
from .datadict import DATA_SHEET, DataDictError
from .semantic_map import amount_unit_profile

# แถวแรกของชีต data เป็นแถวหัวตาราง แถวข้อมูลจึงเริ่มที่ 2
FIRST_DATA_ROW = 2


def _to_int_amount(value):
    """แปลงค่าจำนวนเงินเป็นจำนวนเต็ม — คืน None ถ้าแปลงไม่ได้ (ไม่เดา)"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if float(value).is_integer() else None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        f = float(text)
    except ValueError:
        return None
    return int(f) if f.is_integer() else None


def load_records(path, mapping, schema, agency_filter=None) -> list:
    """อ่านทุกแถวของชีต data แล้วแปลงเป็น CanonicalT1Record

    agency_filter: เซตของ agency_code ที่ต้องการ (None = ทุกหน่วยงาน)
    """
    col_index = mapping.canonical_to_index()
    unit = amount_unit_profile(mapping)
    amount_col = col_index.get("amount_stored")
    if amount_col is None:
        raise DataDictError("mapping ไม่มีฟิลด์จำนวนเงิน จึงอ่านข้อมูลไม่ได้")
    amount_letter = get_column_letter(amount_col + 1)
    agency_col = col_index.get("agency_code")

    p = Path(path)
    fh = open(p, "rb")
    wb = openpyxl.load_workbook(fh, data_only=True, read_only=True)
    try:
        ws = wb[DATA_SHEET]
        records = []
        row_number = 1  # แถวหัวตาราง
        for raw_row in ws.iter_rows(min_row=FIRST_DATA_ROW, values_only=True):
            row_number += 1
            if not raw_row or all(v is None for v in raw_row):
                continue
            if agency_filter is not None and agency_col is not None:
                code = raw_row[agency_col] if agency_col < len(raw_row) else None
                code_text = "" if code is None else str(code).strip()
                if code_text not in agency_filter:
                    continue

            rec = CanonicalT1Record(
                evidence_location=EvidenceLocation(
                    file_label=schema.file_label, file_name=schema.file_name,
                    sha256=schema.sha256, sheet_name=DATA_SHEET,
                    row_number=row_number,
                    amount_cell=f"{amount_letter}{row_number}"),
                row_ordinal=row_number - FIRST_DATA_ROW + 1,
            )
            for canonical, idx in col_index.items():
                value = raw_row[idx] if idx < len(raw_row) else None
                if canonical == "amount_stored":
                    continue
                setattr(rec, canonical, None if value is None else str(value).strip())
                rec.raw_values[canonical] = value

            stored_raw = raw_row[amount_col] if amount_col < len(raw_row) else None
            rec.raw_values["amount_stored"] = stored_raw
            rec.amount_stored = _to_int_amount(stored_raw)
            rec.amount_displayed = "" if stored_raw is None else str(stored_raw)
            rec.declared_unit = unit["declared_unit"]
            rec.scale_factor = unit["scale_factor"]
            rec.unit_confidence = unit["unit_confidence"]
            if rec.amount_stored is not None and rec.unit_confidence == UNIT_CONFIRMED:
                rec.amount_normalized = int(rec.amount_stored * rec.scale_factor)

            rec.validate()
            records.append(rec)
        return records
    finally:
        wb.close()
        fh.close()


def load_pair(path_a, mapping_a, schema_a, path_b, mapping_b, schema_b,
              agency_filter=None):
    """อ่านทั้งสองฝั่งด้วยเงื่อนไขเดียวกัน — ใช้ในการทดลองทุกครั้ง"""
    a = load_records(path_a, mapping_a, schema_a, agency_filter)
    b = load_records(path_b, mapping_b, schema_b, agency_filter)
    return a, b
