# -*- coding: utf-8 -*-
"""กฎ M01-M05 - ตรวจ metadata ก่อนเริ่มเปรียบเทียบ

จุดประสงค์คือดักการจับคู่ไฟล์ผิดฝั่งตั้งแต่ต้น เช่น หยิบไฟล์คนละหน่วยงาน
หรือคนละปีมาเทียบกัน ซึ่งจะทำให้ผลตรวจทั้งชุดไม่มีความหมาย

ข้อมูลที่ใช้คือ "ค่าที่ผู้ใช้ระบุตอนอัปโหลด" เท่านั้น ระบบยังไม่อ่านปีหรือหน่วยงาน
จากในเอกสาร เพราะยังไม่มี mapping ที่ผู้ใช้อนุมัติ (ไม่เดา)
"""
from .catalog import MODE_REDUCTION, MODE_YEAR
from .finding import make_finding
from ..core.status import MachineStatus


def _loc(file_row) -> dict:
    if not file_row:
        return {}
    return {"source_file": file_row["original_name"],
            "source_file_id": file_row["id"],
            "source_type": file_row["kind"],
            "extraction_method": "user_declared_metadata"}


def check_metadata(mode: str, file_a: dict, file_b: dict, file_ref: dict = None) -> list:
    """คืนรายการข้อสังเกตระดับ metadata (อาจว่างได้ถ้าทุกอย่างสอดคล้อง)"""
    out = []
    if not file_a or not file_b:
        return out

    la, lb = _loc(file_a), _loc(file_b)
    ya, yb = file_a.get("declared_fiscal_year"), file_b.get("declared_fiscal_year")
    aa, ab = file_a.get("declared_agency_code"), file_b.get("declared_agency_code")
    ka, kb = file_a.get("declared_doc_kind"), file_b.get("declared_doc_kind")

    # ---- M04: ไฟล์เดียวกันทั้งสองฝั่ง ----
    if file_a["sha256"] == file_b["sha256"]:
        out.append(make_finding(
            "M04",
            "ไฟล์ฝั่ง A และฝั่ง B มีค่า SHA-256 ตรงกัน จึงเป็นไฟล์เดียวกัน "
            "การเปรียบเทียบจะไม่พบความแตกต่างใด",
            value_a=file_a["sha256"][:16], value_b=file_b["sha256"][:16],
            loc_a=la, loc_b=lb, sort_key="0-M04"))

    # ---- M05: ชนิดไฟล์ต่างกัน ----
    if file_a["kind"] != file_b["kind"]:
        out.append(make_finding(
            "M05",
            f"ฝั่ง A เป็น {file_a['kind'].upper()} แต่ฝั่ง B เป็น {file_b['kind'].upper()} "
            "ระยะนี้ระบบยังไม่เปรียบเทียบข้ามชนิดไฟล์",
            value_a=file_a["kind"], value_b=file_b["kind"],
            loc_a=la, loc_b=lb, sort_key="0-M05"))

    # ---- M01: ปีงบประมาณ ----
    if ya is None or yb is None:
        out.append(make_finding(
            "M01",
            "ยังไม่ได้ระบุปีงบประมาณของไฟล์อย่างน้อยหนึ่งฝั่ง ระบบจึงตรวจความสอดคล้อง"
            "ของปีให้ไม่ได้",
            value_a=ya, value_b=yb, loc_a=la, loc_b=lb,
            machine_status=MachineStatus.NEEDS_HUMAN.value, severity="medium",
            sort_key="1-M01"))
    elif mode == MODE_YEAR:
        if ya == yb:
            out.append(make_finding(
                "M01",
                f"โหมดปีก่อนเทียบปีปัจจุบัน แต่ทั้งสองฝั่งระบุปี {ya} เท่ากัน "
                "โปรดตรวจว่าหยิบไฟล์ถูกฝั่งหรือไม่",
                value_a=ya, value_b=yb, loc_a=la, loc_b=lb, sort_key="1-M01"))
        elif yb < ya:
            out.append(make_finding(
                "M01",
                f"ฝั่ง A ระบุปี {ya} ซึ่งใหม่กว่าฝั่ง B ที่ระบุปี {yb} "
                "โดยปกติฝั่ง A ควรเป็นปีก่อนและฝั่ง B เป็นปีปัจจุบัน",
                value_a=ya, value_b=yb, diff_value=float(yb - ya), unit="ปี",
                loc_a=la, loc_b=lb, sort_key="1-M01"))
        elif yb - ya > 1:
            out.append(make_finding(
                "M01",
                f"ปีของสองฝั่งห่างกัน {yb - ya} ปี ({ya} เทียบ {yb}) "
                "โปรดยืนยันว่าตั้งใจเทียบข้ามปีเช่นนี้",
                value_a=ya, value_b=yb, diff_value=float(yb - ya), unit="ปี",
                loc_a=la, loc_b=lb, severity="medium", sort_key="1-M01"))
    elif mode == MODE_REDUCTION and ya != yb:
        out.append(make_finding(
            "M01",
            f"โหมดก่อนเทียบหลังปรับลด ควรเป็นปีงบประมาณเดียวกัน แต่ระบุ {ya} และ {yb}",
            value_a=ya, value_b=yb, loc_a=la, loc_b=lb, sort_key="1-M01"))

    # ---- M02: หน่วยงาน ----
    if aa and ab and aa.strip() != ab.strip():
        out.append(make_finding(
            "M02",
            f"รหัสหน่วยงานสองฝั่งไม่ตรงกัน ({aa} เทียบ {ab}) "
            "โปรดตรวจว่าหยิบไฟล์ของหน่วยงานเดียวกันหรือไม่",
            value_a=aa, value_b=ab, loc_a=la, loc_b=lb, sort_key="1-M02"))
    elif not aa or not ab:
        out.append(make_finding(
            "M02",
            "ยังไม่ได้ระบุรหัสหน่วยงานอย่างน้อยหนึ่งฝั่ง ระบบจึงตรวจให้ไม่ได้ว่า"
            "เป็นหน่วยงานเดียวกัน",
            value_a=aa, value_b=ab, loc_a=la, loc_b=lb, severity="medium",
            sort_key="2-M02"))

    # ---- M03: ประเภทเอกสาร ----
    if mode == MODE_REDUCTION and ka and kb and ka.strip() == kb.strip():
        out.append(make_finding(
            "M03",
            f"ทั้งสองฝั่งระบุประเภทเอกสารเหมือนกันว่า {ka} "
            "โหมดนี้คาดว่าฝั่งหนึ่งเป็นฉบับก่อนปรับลดและอีกฝั่งเป็นฉบับหลังปรับลด",
            value_a=ka, value_b=kb, loc_a=la, loc_b=lb, sort_key="2-M03"))

    return out
