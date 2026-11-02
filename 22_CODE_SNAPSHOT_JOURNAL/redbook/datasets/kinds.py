# -*- coding: utf-8 -*-
"""System Dataset Kinds — ชนิดของชุดข้อมูลในระดับ implementation

กติกาที่ยึด (RES-D-24, SYS namespace):
  - dataset kind อธิบาย **ชนิดไฟล์และโครงสร้าง** ไม่ใช่รหัสวิจัย
  - รหัสวิจัย (T1A / T1B / T2) อยู่ใน research dataset register ของ repo เล่ม
  - ทั้งสองต้องมี crosswalk ระหว่างกัน และ **ห้ามใช้แทนกัน**
  - แต่ละ kind ผูกกับ adapter คนละตัว — ห้ามนำ schema หรือกฎ extraction ข้ามชนิด
"""
from dataclasses import dataclass
from enum import Enum


class DatasetKind(str, Enum):
    """ชนิดชุดข้อมูลในระดับระบบ"""

    OFFICIAL_FLAT_DATA_TABLE = "OFFICIAL_FLAT_DATA_TABLE"
    OFFICIAL_AO_WORKBOOK = "OFFICIAL_AO_WORKBOOK"
    OFFICIAL_MINISTRY_PDF = "OFFICIAL_MINISTRY_PDF"
    UNCONFIRMED_LOCAL_WORKBOOK = "UNCONFIRMED_LOCAL_WORKBOOK"
    CONTROLLED_MUTATION_DATASET = "CONTROLLED_MUTATION_DATASET"
    ARCHIVED_PRIOR_ARTIFACT = "ARCHIVED_PRIOR_ARTIFACT"


@dataclass(frozen=True)
class DatasetKindSpec:
    kind: DatasetKind
    label_th: str
    research_tier: str          # รหัสในทะเบียนวิจัยของ repo เล่ม
    adapter_name: str           # adapter ที่รับผิดชอบ kind นี้เท่านั้น
    canonical_subdir: str       # โฟลเดอร์ย่อยในคลังข้อมูลกลาง
    usable_in_primary_results: bool
    notes: str


SPECS: dict[DatasetKind, DatasetKindSpec] = {
    DatasetKind.OFFICIAL_FLAT_DATA_TABLE: DatasetKindSpec(
        kind=DatasetKind.OFFICIAL_FLAT_DATA_TABLE,
        label_th="ตารางข้อมูลแบนทางการ (Data Dict + data)",
        research_tier="T1A",
        adapter_name="FlatDataTableAdapter",
        canonical_subdir="flat_data_table",
        usable_in_primary_results=True,
        notes="หน่วยเงินบาท · canonical key จาก semantic fields ผ่าน Data Dict",
    ),
    DatasetKind.OFFICIAL_AO_WORKBOOK: DatasetKindSpec(
        kind=DatasetKind.OFFICIAL_AO_WORKBOOK,
        label_th="สมุดงานคาดแดงรายหน่วยงานทางการ",
        research_tier="T1B",
        adapter_name="AOWorkbookAdapter",
        canonical_subdir="ao_workbook",
        usable_in_primary_results=True,
        notes="หลายชีต · merged cells · formulas · anchor codes · หน่วยล้านบาท",
    ),
    DatasetKind.OFFICIAL_MINISTRY_PDF: DatasetKindSpec(
        kind=DatasetKind.OFFICIAL_MINISTRY_PDF,
        label_th="เอกสารคาดแดงเล่มกระทรวง (PDF)",
        research_tier="T1B",
        adapter_name="MinistryPdfAdapter",
        canonical_subdir="ministry_pdf",
        usable_in_primary_results=True,
        notes="ต้องระบุขอบเขตหน้าของหน่วยงานก่อนเปรียบเทียบ · Phase 3 เท่านั้น",
    ),
    DatasetKind.UNCONFIRMED_LOCAL_WORKBOOK: DatasetKindSpec(
        kind=DatasetKind.UNCONFIRMED_LOCAL_WORKBOOK,
        label_th="สมุดงานภายในที่ยังพิสูจน์แหล่งที่มาไม่ได้",
        research_tier="T2",
        adapter_name="AOWorkbookAdapter",
        canonical_subdir="",
        usable_in_primary_results=False,
        notes="development-only · ห้ามเข้าผลหลัก ห้าม commit เข้า Git",
    ),
    DatasetKind.CONTROLLED_MUTATION_DATASET: DatasetKindSpec(
        kind=DatasetKind.CONTROLLED_MUTATION_DATASET,
        label_th="ชุดควบคุมที่ฝังข้อผิดพลาดพร้อม Manifest",
        research_tier="controlled",
        adapter_name="",   # ใช้ adapter ตามชนิดไฟล์ฐานที่นำมาฝัง
        canonical_subdir="",
        usable_in_primary_results=True,
        notes="เฉลยจาก Mutation Manifest · รายงานแยกชั้นจากเอกสารจริง",
    ),
    DatasetKind.ARCHIVED_PRIOR_ARTIFACT: DatasetKindSpec(
        kind=DatasetKind.ARCHIVED_PRIOR_ARTIFACT,
        label_th="ผลงานและผลการทดลองของงานก่อนหน้า",
        research_tier="archive",
        adapter_name="",
        canonical_subdir="",
        usable_in_primary_results=False,
        notes="ห้ามใช้เป็นผลของ RedBook Verify ในทุกกรณี",
    ),
}


def spec_for(kind: DatasetKind) -> DatasetKindSpec:
    return SPECS[kind]


def kinds_for_tier(research_tier: str) -> list[DatasetKind]:
    """คืน dataset kind ทั้งหมดที่ crosswalk กับรหัสวิจัยหนึ่ง"""
    return [k for k, s in SPECS.items() if s.research_tier == research_tier]


def adapter_for(kind: DatasetKind) -> str:
    """คืนชื่อ adapter ที่รับผิดชอบ kind นี้ — ว่างแปลว่ายังไม่ผูก adapter"""
    return SPECS[kind].adapter_name
