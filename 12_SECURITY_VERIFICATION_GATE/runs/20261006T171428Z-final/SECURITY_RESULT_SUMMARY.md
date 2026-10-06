# SECURITY RESULT SUMMARY — FINAL · run 20261006T171428Z-final

**profile:** `LOOPBACK_HTTP` · **matrix sha256:** `36b5230acb22e4fe…` · **protocol:** `security-verification-protocol-0.1.0` · **gate:** `security-gate-0.1.0` · **เริ่ม (UTC):** 2026-10-06T17:14:28+00:00

## ตัวชี้วัด

| ตัวชี้วัด | ค่า |
|---|---|
| controls ที่ประกาศ | 51 |
| applicable | 48 |
| PASS / FAIL / REVIEW / N/A | 46 / 1 / 1 / 3 |
| dependency vulnerabilities (pip-audit) | 0 · audited 40 · skipped 3 |
| data-leakage (leak_check on evidence) | PASS |
| data-leakage (absolute paths in pages) | PASS · 0 หน้า |
| security regression tests | passed 233 · failed 0 · error 0 · skipped 0 |
| browser checks | cookie.flags=PASS · csrf.cross_site_form=PASS · flow.console_clean=PASS · flow.forms_submit=PASS |
| ZAP baseline | INCOMPLETE — ZAP not configured/available (--zap-cmd) |
| unresolved FAIL controls | 1 |

## สถานะราย control

### 1 access-control

| control | ASVS | สถานะ | เหตุผล |
|---|---|---|---|
| SG-01 | V8.2.2 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-02 | V5.3.2 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-03 | V13.4.1 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-04 | V13.4.3 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-05 | V13.4.5 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-06 | V8.2.2 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |

### 2 csrf

| control | ASVS | สถานะ | เหตุผล |
|---|---|---|---|
| SG-07 | V3.5.1 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-08 | V3.5.1 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-09 | V3.5.3 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-10 | V3.3.2; V3.3.4 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-11 | V3.3.1; V3.3.3 (L1) | **NOT_APPLICABLE** | เงื่อนไขไม่บังคับใน profile LOOPBACK_HTTP: ใช้เมื่อเสิร์ฟผ่าน TLS · profile LOOPBACK_HTTP (127.0.0.1 ไม่มี TLS) ⇒ NOT_APPLICABLE · บันทึกค่าที่พบไว้เป็นข้อมูล |

### 3 injection

| control | ASVS | สถานะ | เหตุผล |
|---|---|---|---|
| SG-12 | V1.2.1 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-13 | V1.2.4 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-14 | V1.2.5; V1.3.2 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-15 | V2.2.1; V2.2.2 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-16 | V1.5.1 (L1) | **FAIL** | check ไม่ผ่าน: D:defusedxml_present |
| SG-17 | V1.2.10 (L3) | **PASS** | ทุก check ที่ประกาศผ่าน |

### 4 file-upload

| control | ASVS | สถานะ | เหตุผล |
|---|---|---|---|
| SG-18 | V5.2.1 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-19 | V5.2.2 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-20 | V5.2.3 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-21 | V5.3.2 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-22 | V5.4.1; V5.4.2 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-23 | V5.3.1 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |

### 5 data-leakage

| control | ASVS | สถานะ | เหตุผล |
|---|---|---|---|
| SG-24 | V13.4.2 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-25 | V14.3.2 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-26 | V14.2.4 (project privacy policy t1b-privacy-0.2.0) (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-27 | project (leak-check-0.3.x fail-closed) (L-) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-28 | V14.2.1 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-29 | V3.4.5 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |

### 6 headers

| control | ASVS | สถานะ | เหตุผล |
|---|---|---|---|
| SG-30 | V3.4.3 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-31 | V3.4.4 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-32 | V3.4.6 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-33 | V3.4.8 (L3) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-34 | V3.4.1 (L1) | **NOT_APPLICABLE** | เงื่อนไขไม่บังคับใน profile LOOPBACK_HTTP: ใช้เมื่อเสิร์ฟผ่าน TLS · profile LOOPBACK_HTTP ⇒ NOT_APPLICABLE · บันทึกค่าที่พบ |
| SG-35 | V3.4.2 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-36 | V3.6.1; V13.2.4 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-37 | V3.2.1 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-38 | V4.1.1 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |

### 7 error-handling

| control | ASVS | สถานะ | เหตุผล |
|---|---|---|---|
| SG-39 | V16.3.3 (project: no internals on error page) (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-40 | V4.1.4 (L3) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-41 | V13.4.4 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-42 | V13.4.6 (L3) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-43 | project (DNS rebinding) · ใกล้เคียง V4.1.3 (L-) | **PASS** | ทุก check ที่ประกาศผ่าน |

### 8 session-auth

| control | ASVS | สถานะ | เหตุผล |
|---|---|---|---|
| SG-44 | V6; V7 (L-) | **NOT_APPLICABLE** | ประกาศ NOT_APPLICABLE ใน matrix: ระบบเป็นเครื่องมือผู้ปฏิบัติคนเดียวบน loopback ไม่มี authentication/session · ถ้าเพิ่ม auth หรือเปิดสู่เครือข่าย ⇒ ต้องประกาศ matrix รุ่นใหม่ก่อนประเมิน |

### 9 logging

| control | ASVS | สถานะ | เหตุผล |
|---|---|---|---|
| SG-45 | V16.3.3 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-46 | V16.2.5 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-47 | V16.2.1; V16.2.2 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |

### 10 dependencies

| control | ASVS | สถานะ | เหตุผล |
|---|---|---|---|
| SG-48 | V15.2.1 (L1) | **PASS** | ทุก check ที่ประกาศผ่าน |
| SG-49 | V15.1.2 (L2) | **PASS** | ทุก check ที่ประกาศผ่าน |

### 11 dast

| control | ASVS | สถานะ | เหตุผล |
|---|---|---|---|
| SG-50 | ZAP Baseline (passive) · ไม่ใช่ข้อ ASVS (L-) | **REVIEW** | check ไม่ได้รัน/ไม่ครบ/บันทึกอย่างเดียว (ห้ามนับ PASS): Z:zap_baseline=INCOMPLETE |

### 12 browser-regression

| control | ASVS | สถานะ | เหตุผล |
|---|---|---|---|
| SG-51 | project (browser-facing regression) (L-) | **PASS** | ทุก check ที่ประกาศผ่าน |

## ขอบเขตการอ้าง

- ประเมินตาม subset ที่ประกาศล่วงหน้าจาก OWASP ASVS v5.0.0 — ไม่ใช่ 'ผ่าน ASVS'
- ไม่ใช่ penetration test · ไม่รับรองว่า 'แฮกไม่ได้'
- ผล CVE = ฐานข้อมูล ณ วันที่รัน เฉพาะรายการที่เครื่องมือตรวจได้
- control ที่ check ไม่ครบ = REVIEW ไม่ใช่ PASS
- phase = final: ผลประเมินตาม matrix ที่ประกาศไว้ก่อนรัน
