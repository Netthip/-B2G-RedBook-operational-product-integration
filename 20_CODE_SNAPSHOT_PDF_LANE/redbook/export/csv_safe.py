# -*- coding: utf-8 -*-
"""การเขียน CSV ที่กัน **formula injection** และกันเส้นทางไฟล์รั่ว

🔴 คำสั่ง Bo · `BO REVIEW COMPLETE` (Issue #1) · SECURITY PRIORITY ข้อ 3 —
*"CSV/formula-injection protection **before any evidence export**"*

**ปัญหาที่กันอยู่**

ไฟล์ CSV ที่ระบบสร้าง ผู้ตรวจจะเปิดด้วย Excel หรือ LibreOffice เสมอ
เซลล์ที่ขึ้นต้นด้วย ``=`` ``+`` ``-`` ``@`` (และแท็บ/ขึ้นบรรทัดใหม่) ถูกโปรแกรม
ตารางตีความเป็น **สูตร** ⇒ เนื้อหาที่มาจากเอกสารของผู้ใช้กลายเป็นคำสั่งที่รันบน
เครื่องผู้ตรวจ · สูตรอย่าง ``=HYPERLINK`` หรือ ``=WEBSERVICE`` ส่งข้อมูลออกนอก
เครื่องได้ ซึ่งขัดกับข้อกำหนด local-first ของระบบนี้โดยตรง

🔴 **ความเสี่ยงนี้ไม่ใช่เรื่องสมมติสำหรับระบบนี้** — ป้ายแถวและหัวคอลัมน์ทั้งหมด
มาจากสมุดงานของหน่วยงาน ระบบไม่ได้เป็นผู้แต่งข้อความเหล่านั้นเอง

**สิ่งที่โมดูลนี้ทำ**

1. เติม ``'`` นำหน้าเซลล์ที่ขึ้นต้นด้วยอักขระเสี่ยง — Excel และ LibreOffice
   จะแสดงเป็นข้อความและ **ไม่คำนวณ**
2. กลบเส้นทางไฟล์สัมบูรณ์ทุกเซลล์ผ่าน :mod:`redbook.privacy`
3. **รายงานจำนวนเซลล์ที่ถูกแก้** — ไฟล์ที่ส่งออกจึงไม่เท่ากับข้อมูลดิบ
   🔴 ผู้อ่านต้องรู้ข้อนี้ ห้ามให้เข้าใจว่าเป็นสำเนาตรงตัว
4. ปฏิเสธการเขียนถ้ายังมีเส้นทางสัมบูรณ์หลงเหลือ (:func:`privacy.assert_shareable`)

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from .. import privacy

CSV_SAFE_VERSION = "csv-safe-0.1.0"

#: อักขระที่ทำให้โปรแกรมตารางตีความเซลล์เป็นสูตร
#:
#: ``=`` ``+`` ``@``   — จุดเริ่มสูตรโดยตรง
#: ``-``               — เป็นได้ทั้งเลขติดลบและสูตร ⇒ ต้องกันไว้ด้วย
#: แท็บ / CR / LF      — ใช้แหกโครงสร้างแถวและคอลัมน์
RISKY_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")

#: อักขระที่ต้องถูกตัดทิ้งเสมอ — 🔴 ทำให้แถว/คอลัมน์เพี้ยนได้แม้ไม่ได้อยู่ต้นเซลล์
CONTROL_CHARS = ("\r", "\n", "\x00")

#: เครื่องหมายนำหน้าที่ทำให้โปรแกรมตารางถือว่าเป็นข้อความ
TEXT_MARKER = "'"


@dataclass(frozen=True)
class ExportReport:
    """สิ่งที่เกิดขึ้นจริงตอนเขียน — ต้องรายงานคู่กับไฟล์เสมอ"""

    rows: int = 0
    cells: int = 0
    #: เซลล์ที่ถูกเติมเครื่องหมายนำหน้าเพราะขึ้นต้นด้วยอักขระเสี่ยง
    neutralized: int = 0
    #: เซลล์ที่ถูกกลบเส้นทางไฟล์
    redacted: int = 0
    #: เซลล์ที่มีอักขระควบคุมถูกตัดออก
    stripped: int = 0
    version: str = CSV_SAFE_VERSION

    @property
    def modified(self) -> int:
        return self.neutralized + self.redacted + self.stripped

    def note(self) -> str:
        """ข้อความที่ต้องแสดงคู่กับไฟล์ — 🔴 ห้ามส่งไฟล์ออกโดยไม่มีข้อความนี้"""
        if not self.modified:
            return (f"ส่งออก {self.rows} แถว · {self.cells} เซลล์ "
                    f"— ไม่มีเซลล์ใดถูกแก้")
        return (
            f"ส่งออก {self.rows} แถว · {self.cells} เซลล์ · "
            f"ถูกแก้ {self.modified} เซลล์ "
            f"(กันสูตร {self.neutralized} · กลบเส้นทาง {self.redacted} · "
            f"ตัดอักขระควบคุม {self.stripped}) "
            f"🔴 ไฟล์นี้จึง **ไม่ใช่สำเนาตรงตัว** ของข้อมูลในระบบ"
        )


def neutralize(value) -> tuple[str, bool, bool, bool]:
    """คืน ``(ข้อความที่ปลอดภัย, กันสูตรแล้ว, กลบเส้นทางแล้ว, ตัดอักขระควบคุมแล้ว)``"""
    text = "" if value is None else str(value)

    redacted_text = privacy.redact_text(text)
    was_redacted = redacted_text != text
    text = redacted_text

    stripped = text
    for ch in CONTROL_CHARS:
        stripped = stripped.replace(ch, " ")
    was_stripped = stripped != text
    text = stripped

    was_neutralized = False
    # 🔴 ตรวจจากค่าที่ **ตัดช่องว่างนำหน้าออกแล้ว**
    #
    # ลำดับสำคัญมาก: ขั้นก่อนหน้าเปลี่ยนอักขระควบคุมเป็นช่องว่าง ⇒ ``"\\r=1+1"``
    # กลายเป็น ``" =1+1"`` ซึ่งไม่ขึ้นต้นด้วยอักขระเสี่ยงอีกแล้ว ถ้าตรวจจากค่าดิบ
    # เซลล์นี้จะรอดด่านไป ทั้งที่โปรแกรมตารางบางตัวตัดช่องว่างก่อนตีความ
    if text.lstrip().startswith(RISKY_PREFIXES):
        # เติมนำหน้า **ไม่ใช่ลบอักขระทิ้ง** — ค่าที่ผู้ตรวจเห็นต้องยังเป็นค่าเดิม
        # มิฉะนั้นยอด "-1,500" จะกลายเป็น "1,500" ซึ่งอันตรายกว่าสูตรที่รัน
        text = TEXT_MARKER + text
        was_neutralized = True

    return text, was_neutralized, was_redacted, was_stripped


def rows_to_text(header, rows) -> tuple[str, ExportReport]:
    """แปลงเป็นข้อความ CSV ที่ปลอดภัย — ไม่แตะระบบไฟล์

    แยกจากการเขียนไฟล์โดยเจตนา เพื่อให้ทดสอบได้โดยไม่ต้องสร้างไฟล์จริง
    และเพื่อให้ตรวจเนื้อหาได้ก่อนตัดสินใจเขียน
    """
    buf = io.StringIO()
    # 🔴 ``\r\n`` ตาม RFC 4180 · ``QUOTE_ALL`` ทำให้เซลล์ที่มีตัวคั่นหรือ
    # เครื่องหมายคำพูดไม่แหกโครงสร้างแถว
    writer = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_ALL)

    n_rows = n_cells = n_neutral = n_redact = n_strip = 0
    for raw_row in ([header] if header is not None else []) + list(rows):
        safe_row = []
        for cell in raw_row:
            text, neutral, redact, strip = neutralize(cell)
            safe_row.append(text)
            n_cells += 1
            n_neutral += int(neutral)
            n_redact += int(redact)
            n_strip += int(strip)
        writer.writerow(safe_row)
        n_rows += 1

    report = ExportReport(rows=n_rows, cells=n_cells, neutralized=n_neutral,
                          redacted=n_redact, stripped=n_strip)
    return buf.getvalue(), report


def write_csv(path, header, rows) -> ExportReport:
    """เขียนไฟล์ CSV ที่ปลอดภัย แล้วคืนรายงานว่าแก้อะไรไปบ้าง

    🔴 ตรวจซ้ำด้วย :func:`privacy.assert_shareable` **ก่อน**เขียนเสมอ —
    ถ้ายังมีเส้นทางสัมบูรณ์หลงเหลือ จะยกข้อผิดพลาดและ **ไม่สร้างไฟล์**
    ล้มดัง ๆ ดีกว่าปล่อยไฟล์ที่มีชื่อบัญชีผู้ใช้ออกไปเงียบ ๆ

    เขียนด้วย ``utf-8-sig`` เพราะ Excel บนวินโดวส์อ่านภาษาไทยจาก UTF-8 ที่ไม่มี
    BOM เป็นอักขระเพี้ยน — ผู้ตรวจจะเห็นไฟล์เสียแล้วเข้าใจว่าข้อมูลเสีย
    """
    text, report = rows_to_text(header, rows)
    privacy.assert_shareable(text, where="CSV ที่จะส่งออก")

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8-sig", newline="")
    return report


__all__ = [
    "CSV_SAFE_VERSION", "RISKY_PREFIXES", "CONTROL_CHARS", "TEXT_MARKER",
    "ExportReport", "neutralize", "rows_to_text", "write_csv",
]
