# -*- coding: utf-8 -*-
"""ชนิดชุดข้อมูลระดับระบบ และ crosswalk กับรหัสวิจัยของ repo เล่ม"""
from .kinds import DatasetKind, DatasetKindSpec, SPECS, spec_for, kinds_for_tier, adapter_for

__all__ = [
    "DatasetKind", "DatasetKindSpec", "SPECS",
    "spec_for", "kinds_for_tier", "adapter_for",
]
