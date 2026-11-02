# -*- coding: utf-8 -*-
"""Rule Catalog - บัญชีกฎตรวจทั้งหมด พร้อมเวอร์ชันและสถานะการพัฒนา

กติกาที่ยึด:
  - กฎแต่ละข้อระบุชัดว่า "สรุปอะไรได้" และ "สรุปอะไรไม่ได้"
  - กฎที่ยังไม่ได้พัฒนา ต้องขึ้นสถานะ planned เพื่อไม่ให้เข้าใจผิดว่าตรวจแล้ว
  - default_machine_status ของทุกกฎ ห้ามเป็น "ผิด" เพราะคำว่าผิดมาจากมนุษย์เท่านั้น
"""
from dataclasses import dataclass, asdict

from .. import RULE_SET_VERSION
from ..core.status import MachineStatus

MODE_YEAR = "year_to_year"
MODE_REDUCTION = "before_after_reduction"
MODE_BOTH = "both"

STATUS_IMPLEMENTED = "implemented"
STATUS_PLANNED = "planned"

MODE_LABEL = {
    MODE_YEAR: "ปีก่อนเทียบปีปัจจุบัน",
    MODE_REDUCTION: "ก่อนเทียบหลังปรับลด",
    MODE_BOTH: "ใช้ได้ทั้งสองโหมด",
}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    description: str
    modes: tuple
    source_types: tuple            # ("xlsx",) หรือ ("pdf",) หรือทั้งสอง
    default_machine_status: str
    default_severity: str          # high | medium | low | info
    presentation_only: bool
    requires_evidence_file: bool   # ต้องมีไฟล์หลักฐานการปรับลดจึงจะสรุปได้
    cannot_conclude: str           # สิ่งที่กฎนี้ไม่สรุปให้
    phase: str
    status: str
    version: str = RULE_SET_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def _r(rule_id, title, description, modes, source_types, machine_status,
       severity, phase, status, presentation_only=False,
       requires_evidence_file=False, cannot_conclude=""):
    return Rule(rule_id=rule_id, title=title, description=description,
                modes=tuple(modes), source_types=tuple(source_types),
                default_machine_status=machine_status.value,
                default_severity=severity, presentation_only=presentation_only,
                requires_evidence_file=requires_evidence_file,
                cannot_conclude=cannot_conclude, phase=phase, status=status)


NOT_A_VERDICT = "ไม่สรุปว่าถูกหรือผิด เป็นข้อสังเกตให้ผู้ตรวจพิจารณา"

RULES = [
    # ---------- ตรวจ metadata ก่อนเริ่ม ----------
    _r("M01", "ปีงบประมาณสองฝั่งไม่สอดคล้องกับโหมดที่เลือก",
       "เทียบปีงบประมาณที่ผู้ใช้ระบุกับโหมดตรวจ เช่น โหมดก่อนและหลังปรับลดควรเป็นปีเดียวกัน",
       [MODE_BOTH], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "high",
       "Phase 1", STATUS_IMPLEMENTED,
       cannot_conclude="ระบบไม่ทราบปีจริงในเอกสาร ใช้ค่าที่ผู้ใช้ระบุเท่านั้น"),
    _r("M02", "หน่วยงานสองฝั่งไม่ตรงกัน",
       "เทียบรหัสและชื่อหน่วยงานที่ผู้ใช้ระบุของไฟล์ทั้งสองฝั่ง",
       [MODE_BOTH], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "high",
       "Phase 1", STATUS_IMPLEMENTED,
       cannot_conclude="ไม่ยืนยันว่าหน่วยงานใดถูก เพียงแจ้งว่าการจับคู่ไฟล์อาจผิดฝั่ง"),
    _r("M03", "ประเภทเอกสารสองฝั่งไม่สอดคล้องกับโหมด",
       "เทียบประเภทเอกสารที่ผู้ใช้ระบุ เช่น ฉบับก่อนปรับลดกับฉบับหลังปรับลด",
       [MODE_BOTH], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "medium",
       "Phase 1", STATUS_IMPLEMENTED),
    _r("M04", "ไฟล์สองฝั่งเป็นไฟล์เดียวกัน",
       "ค่า SHA-256 ของไฟล์ A และ B ตรงกันทุกไบต์ การเปรียบเทียบจะไม่พบความแตกต่างใด",
       [MODE_BOTH], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "high",
       "Phase 1", STATUS_IMPLEMENTED),
    _r("M05", "ชนิดไฟล์สองฝั่งต่างกัน",
       "ฝั่งหนึ่งเป็น Excel อีกฝั่งเป็น PDF ระยะนี้ระบบยังไม่เปรียบเทียบข้ามชนิดไฟล์",
       [MODE_BOTH], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "high",
       "Phase 1", STATUS_IMPLEMENTED),

    # ---------- โครงสร้าง Excel ระดับเซลล์ ----------
    _r("X01", "ค่าไม่ตรงกัน",
       "ค่าที่คำนวณได้ของเซลล์ตำแหน่งเดียวกันต่างกัน", [MODE_BOTH], ["xlsx"],
       MachineStatus.DIFF_FOUND, "high", "Phase 2", STATUS_PLANNED,
       cannot_conclude=NOT_A_VERDICT),
    _r("X02", "สูตรไม่ตรงแต่ค่าตรง",
       "สูตรของสองฝั่งต่างกัน แต่ค่าที่คำนวณได้เท่ากัน", [MODE_BOTH], ["xlsx"],
       MachineStatus.NEEDS_HUMAN, "medium", "Phase 2", STATUS_PLANNED),
    _r("X03", "ค่าตรงแต่รูปแบบแสดงผลต่างกัน",
       "ค่าตัวเลขเท่ากัน แต่ number format หรือรูปแบบที่แสดงต่างกัน",
       [MODE_BOTH], ["xlsx"], MachineStatus.DIFF_FOUND, "low", "Phase 2",
       STATUS_PLANNED, presentation_only=True),
    _r("X04", "ข้อความไม่ตรงกัน",
       "ข้อความในเซลล์ตำแหน่งเดียวกันต่างกัน", [MODE_BOTH], ["xlsx"],
       MachineStatus.DIFF_FOUND, "medium", "Phase 2", STATUS_PLANNED),
    _r("X05", "เซลล์หรือแถวหาย",
       "ฝั่งหนึ่งมีข้อมูลในตำแหน่งนั้น อีกฝั่งไม่มี", [MODE_BOTH], ["xlsx"],
       MachineStatus.DIFF_FOUND, "high", "Phase 2", STATUS_PLANNED),
    _r("X06", "ลำดับเปลี่ยน",
       "รายการเดียวกันปรากฏคนละลำดับหรือคนละแถว", [MODE_BOTH], ["xlsx"],
       MachineStatus.DIFF_FOUND, "low", "Phase 2", STATUS_PLANNED),
    _r("X07", "โครงสร้างสมุดงานเปลี่ยน",
       "ชีตเพิ่ม หาย เปลี่ยนชื่อ สลับลำดับ merge cell แถวหรือคอลัมน์ที่ซ่อน "
       "และพื้นที่พิมพ์ต่างกัน",
       [MODE_BOTH], ["xlsx"], MachineStatus.NEEDS_HUMAN, "medium", "Phase 2",
       STATUS_PLANNED),
    _r("X08", "ตัวเลขถูกเก็บเป็นข้อความ",
       "เซลล์ที่ควรเป็นตัวเลขถูกเก็บเป็นข้อความ เสี่ยงทำให้ยอดรวมผิด",
       [MODE_BOTH], ["xlsx"], MachineStatus.NEEDS_HUMAN, "medium", "Phase 2",
       STATUS_PLANNED),

    # ---------- MODE 1 ปีก่อนเทียบปีปัจจุบัน ----------
    _r("Y01", "มีทั้งสองปีและยอดเท่าเดิม", "รายการจับคู่ได้และจำนวนเงินเท่ากัน",
       [MODE_YEAR], ["xlsx", "pdf"], MachineStatus.MATCH, "info", "Phase 2",
       STATUS_PLANNED),
    _r("Y02", "มีทั้งสองปีแต่ยอดเพิ่ม",
       "รายการจับคู่ได้และจำนวนเงินปีปัจจุบันมากกว่าปีก่อน",
       [MODE_YEAR], ["xlsx", "pdf"], MachineStatus.LIKELY_YEAR_CHANGE, "medium",
       "Phase 2", STATUS_PLANNED, cannot_conclude=NOT_A_VERDICT),
    _r("Y03", "มีทั้งสองปีแต่ยอดลด",
       "รายการจับคู่ได้และจำนวนเงินปีปัจจุบันน้อยกว่าปีก่อน",
       [MODE_YEAR], ["xlsx", "pdf"], MachineStatus.LIKELY_YEAR_CHANGE, "medium",
       "Phase 2", STATUS_PLANNED, cannot_conclude=NOT_A_VERDICT),
    _r("Y04", "รายการใหม่ในปีปัจจุบัน", "พบรายการในปีปัจจุบันแต่ไม่พบในปีก่อน",
       [MODE_YEAR], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "high", "Phase 2",
       STATUS_PLANNED,
       cannot_conclude="ไม่สรุปว่าตั้งใหม่โดยไม่ชอบ อาจเป็นรายการเดิมที่เปลี่ยนชื่อ"),
    _r("Y05", "รายการที่มีในปีก่อนแต่หายไปในปีปัจจุบัน",
       "พบรายการในปีก่อนแต่ไม่พบในปีปัจจุบัน",
       [MODE_YEAR], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "high", "Phase 2",
       STATUS_PLANNED,
       cannot_conclude="ไม่สรุปว่าตกหล่น อาจเป็นการยุบรวมหรือเปลี่ยนชื่อรายการ"),
    _r("Y06", "ชื่อเปลี่ยนแต่มีแนวโน้มเป็นรายการเดียวกัน",
       "ระบบเสนอการจับคู่พร้อมคะแนนและเหตุผล ต้องให้มนุษย์ยืนยันก่อนถือเป็นคู่เดียวกัน",
       [MODE_YEAR], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "medium", "Phase 2",
       STATUS_PLANNED, cannot_conclude="ระบบไม่รวมรายการให้อัตโนมัติ"),
    _r("Y07", "รหัสเดิมแต่ชื่อเปลี่ยน", "จับคู่ด้วยรหัสได้ แต่ชื่อรายการต่างกัน",
       [MODE_YEAR], ["xlsx", "pdf"], MachineStatus.DIFF_FOUND, "medium", "Phase 2",
       STATUS_PLANNED),
    _r("Y08", "ชื่อเดิมแต่รหัสเปลี่ยน", "จับคู่ด้วยชื่อได้ แต่รหัสรายการต่างกัน",
       [MODE_YEAR], ["xlsx", "pdf"], MachineStatus.DIFF_FOUND, "medium", "Phase 2",
       STATUS_PLANNED),
    _r("Y09", "ลำดับรายการเปลี่ยน", "รายการเดียวกันอยู่คนละลำดับ",
       [MODE_YEAR], ["xlsx", "pdf"], MachineStatus.DIFF_FOUND, "low", "Phase 2",
       STATUS_PLANNED),
    _r("Y10", "ย้ายแผนงาน ผลผลิต โครงการ หมวด หรือหน่วยงาน",
       "รายการเดียวกันปรากฏใต้โครงสร้างที่ต่างจากปีก่อน",
       [MODE_YEAR], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "high", "Phase 2",
       STATUS_PLANNED),
    _r("Y11", "ยอดรวมระดับบนไม่สัมพันธ์กับรายการย่อย",
       "ผลรวมของรายการย่อยไม่เท่ากับยอดรวมที่ประกาศไว้ในระดับบน",
       [MODE_BOTH], ["xlsx", "pdf"], MachineStatus.DIFF_FOUND, "high", "Phase 2",
       STATUS_PLANNED),
    _r("Y12", "ต่างกันเพราะรูปแบบตัวเลข ไม่ใช่ค่าตัวเลข",
       "ค่าตัวเลขเท่ากันแต่แสดงผลต่างกัน เช่น หน่วยบาทหรือล้านบาท ทศนิยม จุลภาค",
       [MODE_BOTH], ["xlsx", "pdf"], MachineStatus.DIFF_FOUND, "low", "Phase 2",
       STATUS_PLANNED, presentation_only=True),
    _r("Y13", "ข้อความ วงเล็บ เครื่องหมาย หรือบรรทัดที่หายหรือเพิ่ม",
       "ความต่างระดับตัวอักษรและเครื่องหมาย รวมถึงบรรทัดที่หายหรือเพิ่มขึ้น",
       [MODE_BOTH], ["xlsx", "pdf"], MachineStatus.DIFF_FOUND, "medium", "Phase 2",
       STATUS_PLANNED),

    # ---------- MODE 2 ก่อนเทียบหลังปรับลด ----------
    _r("R01", "รายการที่ถูกปรับลด",
       "แสดงยอดก่อนปรับลด ยอดหลังปรับลด ผลต่าง และร้อยละที่ปรับลด",
       [MODE_REDUCTION], ["xlsx", "pdf"], MachineStatus.LIKELY_REDUCTION, "medium",
       "Phase 2", STATUS_PLANNED,
       cannot_conclude="ถ้าไม่มีไฟล์หลักฐานการปรับลด สรุปได้เพียงว่าพบความแตกต่าง"),
    _r("R02", "รายการที่ไม่เปลี่ยนแปลง", "ยอดก่อนและหลังปรับลดเท่ากัน",
       [MODE_REDUCTION], ["xlsx", "pdf"], MachineStatus.MATCH, "info", "Phase 2",
       STATUS_PLANNED),
    _r("R03", "รายการที่เพิ่มขึ้นในฉบับหลังปรับลด",
       "พบยอดหลังปรับลดสูงกว่าฉบับก่อนปรับลด",
       [MODE_REDUCTION], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "high",
       "Phase 2", STATUS_PLANNED),
    _r("R04", "รายการที่หายไปทั้งรายการ", "ไม่พบรายการนี้ในฉบับหลังปรับลด",
       [MODE_REDUCTION], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "high",
       "Phase 2", STATUS_PLANNED,
       cannot_conclude="ไม่สรุปว่าตกหล่น จนกว่าจะมีหลักฐานหรือผู้ตรวจยืนยัน"),
    _r("R05", "ชื่อ รหัส หรือลำดับเปลี่ยนระหว่างสองฉบับ",
       "รายการที่คาดว่าเป็นรายการเดียวกันแต่ตัวระบุเปลี่ยน",
       [MODE_REDUCTION], ["xlsx", "pdf"], MachineStatus.DIFF_FOUND, "medium",
       "Phase 2", STATUS_PLANNED),
    _r("R06", "ยอดรวมหลังปรับลดไม่สัมพันธ์กับรายการย่อย",
       "ผลรวมรายการย่อยของฉบับหลังปรับลดไม่เท่ากับยอดรวมที่ประกาศ",
       [MODE_REDUCTION], ["xlsx", "pdf"], MachineStatus.DIFF_FOUND, "high",
       "Phase 2", STATUS_PLANNED),
    _r("R07", "ระบุในหลักฐานว่าต้องปรับลด แต่ฉบับหลังไม่เปลี่ยน",
       "เทียบรายการปรับลดที่ได้รับอนุมัติกับผลที่ปรากฏจริงในฉบับหลังปรับลด",
       [MODE_REDUCTION], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "high",
       "Phase 2", STATUS_PLANNED, requires_evidence_file=True),
    _r("R08", "เปลี่ยนแปลงจริงแต่ไม่พบในหลักฐานการปรับลด",
       "พบการเปลี่ยนแปลงในฉบับหลัง แต่ไม่มีรายการนี้ในหลักฐานที่อนุมัติ",
       [MODE_REDUCTION], ["xlsx", "pdf"], MachineStatus.NEEDS_HUMAN, "high",
       "Phase 2", STATUS_PLANNED, requires_evidence_file=True),
    _r("R09", "ยอดลดที่อนุมัติกับยอดลดที่ปรากฏจริงต่างกัน",
       "คำนวณส่วนต่างระหว่างยอดลดตามหลักฐานกับยอดลดที่ตรวจพบ",
       [MODE_REDUCTION], ["xlsx", "pdf"], MachineStatus.DIFF_FOUND, "high",
       "Phase 2", STATUS_PLANNED, requires_evidence_file=True),
    _r("R10", "ผลกระทบของการปรับลดต่อยอดรวมระดับบน",
       "สรุปผลรวมการเปลี่ยนแปลงในระดับโครงการ ผลผลิต แผนงาน และหน่วยงาน",
       [MODE_REDUCTION], ["xlsx", "pdf"], MachineStatus.LIKELY_REDUCTION, "info",
       "Phase 2", STATUS_PLANNED),

    # ---------- PDF ----------
    _r("P01", "ข้อความไม่ตรงกัน", "เทียบข้อความระดับตัวอักษร คำ และการเว้นวรรค",
       [MODE_BOTH], ["pdf"], MachineStatus.DIFF_FOUND, "medium", "Phase 3",
       STATUS_PLANNED),
    _r("P02", "ตัวเลขไม่ตรงกัน",
       "เทียบจำนวนเงินหลังปรับให้อยู่รูปเดียวกัน ทั้งจุลภาคและเลขไทยหรืออารบิก",
       [MODE_BOTH], ["pdf"], MachineStatus.DIFF_FOUND, "high", "Phase 3",
       STATUS_PLANNED),
    _r("P03", "โครงสร้างเอกสารต่างกัน",
       "บรรทัดหายหรือเพิ่ม ลำดับบรรทัด หน้าเพิ่มหรือหาย ตารางและเส้นตาราง",
       [MODE_BOTH], ["pdf"], MachineStatus.DIFF_FOUND, "high", "Phase 3",
       STATUS_PLANNED),
    _r("P04", "รูปแบบต่างเล็กน้อย",
       "ต่างที่การจัดวางซึ่งไม่กระทบเนื้อหาและค่าตัวเลข",
       [MODE_BOTH], ["pdf"], MachineStatus.DIFF_FOUND, "low", "Phase 3",
       STATUS_PLANNED, presentation_only=True),
    _r("P05", "รูปแบบต่างอย่างมีสาระ",
       "ข้อความล้นหรือถูกตัดหาย ตำแหน่งตารางเปลี่ยนจนอ่านได้ต่างความหมาย",
       [MODE_BOTH], ["pdf"], MachineStatus.NEEDS_HUMAN, "high", "Phase 3",
       STATUS_PLANNED),
    _r("P06", "วงเล็บและเครื่องหมายวรรคตอนต่างกัน",
       "เทียบวงเล็บเปิดปิดและเครื่องหมายวรรคตอนแบบตรงตัว",
       [MODE_BOTH], ["pdf"], MachineStatus.DIFF_FOUND, "medium", "Phase 3",
       STATUS_PLANNED),
    _r("P07", "เลขไทยกับเลขอารบิกต่างกัน",
       "ค่าตัวเลขเท่ากันแต่ใช้ระบบเลขต่างกัน",
       [MODE_BOTH], ["pdf"], MachineStatus.DIFF_FOUND, "low", "Phase 3",
       STATUS_PLANNED, presentation_only=True),
    _r("P08", "การขึ้นหน้าใหม่และรายการต่อเนื่องข้ามหน้าต่างกัน",
       "ตำแหน่ง page break และรายการที่ต่อเนื่องข้ามหน้า",
       [MODE_BOTH], ["pdf"], MachineStatus.NEEDS_HUMAN, "medium", "Phase 3",
       STATUS_PLANNED),
    _r("P09", "หัวกระดาษ ท้ายกระดาษ หรือเลขหน้าต่างกัน",
       "เทียบ header และ footer รวมถึงเลขหน้า",
       [MODE_BOTH], ["pdf"], MachineStatus.DIFF_FOUND, "low", "Phase 3",
       STATUS_PLANNED),
    _r("P10", "ผลจาก OCR ต้องตรวจทาน",
       "หน้านี้ไม่มี text layer ระบบใช้ OCR ต้องให้มนุษย์ตรวจทานก่อนนำไปอ้างอิง",
       [MODE_BOTH], ["pdf"], MachineStatus.NEEDS_HUMAN, "high", "Phase 3",
       STATUS_PLANNED,
       cannot_conclude="ค่าความเชื่อมั่นต่ำของ OCR ไม่ใช่หลักฐานว่าเอกสารผิด"),
]

BY_ID = {r.rule_id: r for r in RULES}


def get(rule_id: str) -> Rule:
    return BY_ID[rule_id]


def for_mode(mode: str):
    return [r for r in RULES if mode in r.modes or MODE_BOTH in r.modes]


def implemented():
    return [r for r in RULES if r.status == STATUS_IMPLEMENTED]


def counts_by_status() -> dict:
    out = {STATUS_IMPLEMENTED: 0, STATUS_PLANNED: 0}
    for r in RULES:
        out[r.status] = out.get(r.status, 0) + 1
    return out


def snapshot(mode: str = None) -> list:
    """ภาพนิ่งของกฎที่ใช้ในการรันหนึ่งครั้ง เก็บลง run_rules เพื่อให้ตรวจซ้ำได้"""
    rules = for_mode(mode) if mode else RULES
    return [{"rule_id": r.rule_id, "rule_version": r.version,
             "enabled": 1 if r.status == STATUS_IMPLEMENTED else 0,
             "params": {}} for r in rules]


# ---------------------------------------------------------------------------
# ขอบเขตกฎตามชนิดชุดข้อมูล (เพิ่ม 27 ส.ค. 2569 — RES-D-24 / adapter boundary)
#
# หมายเหตุสำคัญ: ฟิลด์ `source_types` เดิมแยกได้แค่ระดับ "xlsx / pdf"
# ซึ่ง **ไม่พอ** สำหรับแยก OFFICIAL_FLAT_DATA_TABLE ออกจาก OFFICIAL_AO_WORKBOOK
# เพราะทั้งคู่เป็น xlsx แต่โครงสร้างและกฎ extraction คนละชุดโดยสิ้นเชิง
#
# กฎที่พัฒนาต่อจากนี้ต้องประกาศ dataset kind ที่ใช้ได้ให้ชัด
# และ **ห้ามนำกฎของชนิดหนึ่งไปรันกับอีกชนิดโดยอัตโนมัติ**
# ---------------------------------------------------------------------------

#: dataset kind ที่กฎกลุ่มต่าง ๆ ใช้ได้ — คีย์เป็นสตริงเพื่อไม่ผูก import วน
DATASET_KIND_SOURCE_TYPES = {
    "OFFICIAL_FLAT_DATA_TABLE": ("xlsx",),
    "OFFICIAL_AO_WORKBOOK": ("xlsx",),
    "UNCONFIRMED_LOCAL_WORKBOOK": ("xlsx",),
    "OFFICIAL_MINISTRY_PDF": ("pdf",),
}

#: กฎที่ยังไม่ประกาศ dataset kind อย่างชัดเจน — ต้องถือว่า "ยังไม่ผูกชนิด"
#: และห้ามนำไปรันข้ามชนิดโดยอนุมานจาก source_types เพียงอย่างเดียว
RULES_WITHOUT_DATASET_KIND_SCOPE = tuple(r.rule_id for r in RULES)


def source_types_for_dataset_kind(kind_name: str) -> tuple:
    """คืน source_types ที่สอดคล้องกับ dataset kind หนึ่ง"""
    if kind_name not in DATASET_KIND_SOURCE_TYPES:
        raise KeyError(f"ไม่รู้จัก dataset kind '{kind_name}' ในบัญชีกฎ")
    return DATASET_KIND_SOURCE_TYPES[kind_name]


def candidate_rules_for_dataset_kind(kind_name: str) -> list:
    """กฎที่ **อาจ** ใช้กับ dataset kind นี้ได้ตามชนิดไฟล์

    ⚠️ นี่เป็นเพียงตัวกรองเบื้องต้นตามชนิดไฟล์ — **ไม่ใช่การอนุมัติให้ใช้**
    กฎที่จะรันจริงกับ dataset kind หนึ่งต้องผ่านการประกาศขอบเขตอย่างชัดเจน
    ในเวอร์ชันกฎที่พัฒนาสำหรับชนิดนั้นโดยเฉพาะ
    """
    st = source_types_for_dataset_kind(kind_name)
    return [r for r in RULES if any(t in r.source_types for t in st)]
