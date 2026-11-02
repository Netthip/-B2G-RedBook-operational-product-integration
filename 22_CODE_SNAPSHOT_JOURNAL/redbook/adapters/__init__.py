# -*- coding: utf-8 -*-
"""Adapter แยกตามชนิดเอกสาร — ห้ามใช้ข้ามชนิด

สถานะ: skeleton เท่านั้น · การมี skeleton ยังไม่ถือว่า Phase 2C เริ่มแล้ว
"""
from .base import (
    CanonicalEnvelope, DocumentAdapter, ExtractionStatus,
    LocationKind, SourceLocation, validate_envelope,
)
from .flat_data_table import FlatDataTableAdapter
from .ao_workbook import AOWorkbookAdapter
from .ministry_pdf import MinistryPdfAdapter

__all__ = [
    "CanonicalEnvelope", "DocumentAdapter", "ExtractionStatus",
    "LocationKind", "SourceLocation", "validate_envelope",
    "FlatDataTableAdapter", "AOWorkbookAdapter", "MinistryPdfAdapter",
]
