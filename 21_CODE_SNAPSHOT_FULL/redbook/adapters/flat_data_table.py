# -*- coding: utf-8 -*-
"""FlatDataTableAdapter — ตารางข้อมูลแบนทางการ (T1A · OFFICIAL_FLAT_DATA_TABLE)

โครงสร้างที่รับ: 2 ชีต — `Data Dict` (พจนานุกรมและหลักฐาน semantic mapping) + `data`
หน่วยเงิน: บาท · คีย์: composite semantic key ผ่าน Data Dict (ห้ามผูก physical column name)

**สถานะ: skeleton — ยังไม่ implement การสกัด (Phase 2C-1)**
"""
from pathlib import Path
from typing import Any

from ..datasets.kinds import DatasetKind
from .base import CanonicalEnvelope, DocumentAdapter

SHEET_DATA_DICT = "Data Dict"
SHEET_DATA = "data"


class FlatDataTableAdapter(DocumentAdapter):
    dataset_kind = DatasetKind.OFFICIAL_FLAT_DATA_TABLE
    schema_version = "flat-table-schema-0.1.0-skeleton"

    #: ชื่อชีตที่ adapter นี้รู้จัก — ห้ามใช้ชื่อชีตของ AO workbook ที่นี่
    known_sheets = (SHEET_DATA_DICT, SHEET_DATA)

    def inspect(self, path: Path) -> dict[str, Any]:
        raise NotImplementedError(
            "FlatDataTableAdapter.inspect ยังไม่ implement — เริ่มใน Phase 2C-1"
        )

    def extract(self, path: Path) -> list[CanonicalEnvelope]:
        raise NotImplementedError(
            "FlatDataTableAdapter.extract ยังไม่ implement — เริ่มใน Phase 2C-1"
        )
