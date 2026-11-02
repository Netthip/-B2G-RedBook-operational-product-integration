# -*- coding: utf-8 -*-
"""หลักฐานเชิงเอกสาร — ทะเบียนเอกสารด้วย content hash + ชั้นข้อความของ PDF

งานตามคำสั่งกิ๊ฟ 9 ก.ย. 2569 (`GIFT DECISION — ANSWER-KEY CUSTODIAN +
INDICATOR/PDF TRACEABILITY WORK ORDER` · Gate 1 และ Gate 3)

🔴 **ขอบเขต** — แพ็กเกจนี้ *อ่าน* ชั้นข้อความที่มีอยู่แล้วใน PDF เพื่อชี้ตำแหน่งหลักฐาน
(หน้า · กรอบ) ให้มนุษย์กดเปิดดู · **ไม่ใช่** การเปรียบเทียบ PDF ของสายวิจัย
(Phase 3 ยัง blocked ตาม `RES-D-32`) · ไม่ทำ OCR · ไม่แก้ไฟล์ใด

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
EVIDENCE_VERSION = "evidence-0.1.0"

__all__ = ["EVIDENCE_VERSION"]
