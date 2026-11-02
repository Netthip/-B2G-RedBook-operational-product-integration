# -*- coding: utf-8 -*-
"""G2 (ส่วนที่ 1) — อ่านชีต Data Dict และหัวตารางจริง พร้อมคำนวณ schema fingerprint

โมดูลนี้อ่านอย่างเดียว ไม่ตีความ ไม่ตัดสิน — หน้าที่เดียวคือคืน "ข้อเท็จจริงของ schema"
ให้ชั้น semantic_map นำไปเทียบ
"""
import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

import openpyxl

DATA_DICT_SHEET = "Data Dict"
DATA_SHEET = "data"


class DataDictError(Exception):
    """อ่านโครงสร้างไฟล์ไม่ได้ — ข้อความปลอดภัยพอจะแสดงให้ผู้ใช้เห็น"""


@dataclass
class FieldDefinition:
    ordinal: int          # ลำดับตามที่ Data Dict ระบุ (1-based)
    field_name: str       # ชื่อฟิลด์ตาม Data Dict
    definition: str       # นิยามภาษาไทยตาม Data Dict

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkbookSchema:
    """ภาพรวม schema ของไฟล์หนึ่งไฟล์"""

    file_label: str = ""
    file_name: str = ""
    sha256: str = ""
    data_dict: list = field(default_factory=list)      # list[FieldDefinition]
    physical_columns: list = field(default_factory=list)  # ชื่อคอลัมน์จริงตามลำดับ
    data_row_count: int = 0

    # --- fingerprint ---
    def data_dict_fingerprint(self) -> str:
        payload = [[f.field_name, f.definition] for f in self.data_dict]
        return _sha16(json.dumps(payload, ensure_ascii=False))

    def physical_fingerprint(self) -> str:
        return _sha16("|".join(self.physical_columns))

    def definitions_by_name(self) -> dict:
        return {f.field_name: f.definition for f in self.data_dict}

    def as_dict(self) -> dict:
        return {
            "file_label": self.file_label,
            "file_name": self.file_name,
            "sha256": self.sha256,
            "data_dict": [f.as_dict() for f in self.data_dict],
            "physical_columns": list(self.physical_columns),
            "data_row_count": self.data_row_count,
            "data_dict_fingerprint": self.data_dict_fingerprint(),
            "physical_fingerprint": self.physical_fingerprint(),
        }


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _clean(value) -> str:
    return "" if value is None else str(value).strip()


def sha256_of(path) -> str:
    h = hashlib.sha256()
    with open(Path(path), "rb") as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_schema(path, file_label: str = "", count_rows: bool = True) -> WorkbookSchema:
    """อ่าน Data Dict + หัวตารางของไฟล์ T1 หนึ่งไฟล์ (อ่านอย่างเดียว)"""
    p = Path(path)
    fh = open(p, "rb")
    try:
        wb = openpyxl.load_workbook(fh, data_only=True, read_only=True)
    except Exception:
        fh.close()
        raise DataDictError("เปิดไฟล์นี้ไม่ได้ ไฟล์อาจเสียหายหรือมีรหัสผ่าน")

    try:
        if DATA_DICT_SHEET not in wb.sheetnames:
            raise DataDictError(f"ไม่พบชีต {DATA_DICT_SHEET!r} ในไฟล์นี้")
        if DATA_SHEET not in wb.sheetnames:
            raise DataDictError(f"ไม่พบชีต {DATA_SHEET!r} ในไฟล์นี้")

        definitions = []
        for row in wb[DATA_DICT_SHEET].iter_rows(min_row=2, values_only=True):
            if not row:
                continue
            ordinal, name, meaning = (list(row) + [None, None, None])[:3]
            name = _clean(name)
            if not name:
                continue
            try:
                ordinal = int(ordinal)
            except (TypeError, ValueError):
                ordinal = len(definitions) + 1
            definitions.append(FieldDefinition(ordinal, name, _clean(meaning)))

        if not definitions:
            raise DataDictError("ชีต Data Dict ไม่มีรายการฟิลด์ที่อ่านได้")

        rows = wb[DATA_SHEET].iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            raise DataDictError("ชีต data ว่างเปล่า")
        physical = [_clean(c) for c in header]

        n_rows = 0
        if count_rows:
            for r in rows:
                if r and any(v is not None for v in r):
                    n_rows += 1

        return WorkbookSchema(
            file_label=file_label or p.stem,
            file_name=p.name,
            sha256=sha256_of(p),
            data_dict=definitions,
            physical_columns=physical,
            data_row_count=n_rows,
        )
    finally:
        wb.close()
        fh.close()
