# -*- coding: utf-8 -*-
"""MinistryPdfAdapter — เอกสารคาดแดงเล่มกระทรวง (T1B PDF · OFFICIAL_MINISTRY_PDF)

โครงสร้างที่รับ: PDF เล่มกระทรวง หลายหน่วยงานในไฟล์เดียว
ต้องระบุ **ขอบเขตหน้าของหน่วยงาน** ก่อนเปรียบเทียบเสมอ (RES-Q-06)

**สถานะ: skeleton — Phase 2C อนุญาตเพียงลงทะเบียนไฟล์ ยืนยันขอบเขตหน้า
เตรียม interface และเก็บ metadata/source hash เท่านั้น
ห้าม implement หรืออ้างผล text extraction / OCR / PDF comparison จนเริ่ม Phase 3**
"""
from pathlib import Path
from typing import Any

from ..datasets.kinds import DatasetKind
from .base import CanonicalEnvelope, DocumentAdapter


class MinistryPdfAdapter(DocumentAdapter):
    dataset_kind = DatasetKind.OFFICIAL_MINISTRY_PDF
    schema_version = "ministry-pdf-schema-0.1.0-skeleton"

    def inspect(self, path: Path) -> dict[str, Any]:
        raise NotImplementedError(
            "MinistryPdfAdapter.inspect ยังไม่ implement — Phase 3 เท่านั้น"
        )

    def extract(self, path: Path) -> list[CanonicalEnvelope]:
        raise NotImplementedError(
            "MinistryPdfAdapter.extract ยังไม่ implement — "
            "ห้ามสกัดข้อความหรือ OCR จนกว่าจะเริ่ม Phase 3 อย่างเป็นทางการ"
        )
