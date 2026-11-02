# -*- coding: utf-8 -*-
"""Web Security Verification Gate (แพ็กเกจระดับบนสุด · เครื่องมือฝั่งผู้พัฒนา — อยู่นอก ``redbook`` โดยเจตนา
เพราะใช้ httpx/socket คุยกับ target บน loopback · ``redbook`` ยังคงกติกา local-first ไม่มีไลบรารีเครือข่าย)

Web Security Verification Gate — ด่านตรวจความปลอดภัยของเว็บที่ทำซ้ำได้ (Issue #23)

ส่วนประกอบ

* :mod:`matrix`      — โหลด/ตรวจรูปแบบ **predeclared matrix** (CSV ที่ประกาศล่วงหน้าใน
                       repo สาธารณะ) — ตัว runner ไม่สร้างหรือแก้ matrix เอง
* :mod:`evaluate`    — กติกาแปลงผล check → สถานะ control ``PASS | FAIL | REVIEW | NOT_APPLICABLE``
                       🔴 check ที่ไม่ได้รัน/รันไม่ครบ ⇒ ``REVIEW`` เสมอ **ห้ามนับ PASS**
* :mod:`http_probes` — ตรวจ header · method · path · CSRF · host กับ target ที่รันจริง
* :mod:`browser_checks` — สคริปต์เดี่ยวสำหรับ Playwright (รันด้วย python ภายนอกได้)
* :mod:`target`      — เปิด target สังเคราะห์บน loopback สำหรับ probe/เบราว์เซอร์/ZAP
* :mod:`runner`      — ตัวประสาน: รันทุกขั้น · เก็บ raw/normalized · manifest · แฮช

🔴 ขอบเขตการอ้าง: ผลของด่านนี้คือ "ประเมินตาม subset ที่ประกาศล่วงหน้าจาก OWASP ASVS v5.0.0"
ไม่ใช่ "ผ่าน ASVS" · ไม่ใช่ penetration test · ไม่ใช่หลักฐานว่า "แฮกไม่ได้"
target ที่สแกนต้องเป็น synthetic/test environment บน loopback ที่ผู้พัฒนาควบคุมเท่านั้น
"""

SECURITY_GATE_VERSION = "security-gate-0.1.0"
ASVS_VERSION = "OWASP ASVS v5.0.0"
#: profile ของการติดตั้งที่ประกาศคู่กับ matrix — ควบคุมว่าข้อ CONDITIONAL ใช้บังคับหรือไม่
PROFILES = ("LOOPBACK_HTTP", "NETWORK_TLS")
DEFAULT_PROFILE = "LOOPBACK_HTTP"
#: profile ที่ทำให้เงื่อนไข TLS ของข้อ CONDITIONAL เป็นจริง
TLS_PROFILES = ("NETWORK_TLS",)

__all__ = ["SECURITY_GATE_VERSION", "ASVS_VERSION", "PROFILES", "DEFAULT_PROFILE",
           "TLS_PROFILES"]
