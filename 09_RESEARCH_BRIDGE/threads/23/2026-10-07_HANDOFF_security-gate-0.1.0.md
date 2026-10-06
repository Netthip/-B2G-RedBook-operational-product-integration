# #23 — HANDOFF: Web Security Verification Gate 0.1.0 (รอบแรก) — READY FOR REVIEW

**ผู้ทำ:** Giho · **วันที่:** 7 ตุลาคม 2569 · **ตอบ:** ตัวใบ #23 (ลำดับทำงาน 1–11) · **สถานะ:** `READY FOR REVIEW` (Bo) · ค้าง 2 ข้อที่ต้องให้ Gift ตัดสิน
**ป้าย:** `PRODUCT EVIDENCE — POST-FREEZE` · `SYNTHETIC ONLY` · ไม่แตะ evaluator/tag ที่ freeze

> ถ้อยคำที่อ้างได้/ห้ามอ้าง อยู่ที่หัว [`SECURITY_VERIFICATION_PROTOCOL.md`](../../../12_SECURITY_VERIFICATION_GATE/SECURITY_VERIFICATION_PROTOCOL.md) — รายงานนี้ใช้ถ้อยคำชุดนั้นเท่านั้น

---

## 1. สิ่งที่ทำ (ตามลำดับในใบ)

| ลำดับ | งาน | ผล |
|---|---|---|
| 1 | inventory controls จาก #6 | CSRF double-submit+origin · security headers · privacy 0.2.0 · csv_safe · ตรวจชนิดไฟล์จากไบต์ · zip bomb · leak-check 0.3.1 · CVE scan 02 · browser smoke — ทั้งหมดถูกจัดเข้า matrix (reuse ไม่สร้างซ้ำ) |
| 2–3 | เลือก + version ASVS subset · เขียน predeclared matrix | **51 control · 12 หมวด** อ้าง requirement ASVS v5.0.0 ราย ID · 46 APPLICABLE · 2 CONDITIONAL(TLS) · 1 NOT_APPLICABLE(auth) · 2 project-specific (DNS rebinding · leak-check) · commit `ed79968` + `68ce555` (LF) **ก่อน** รอบ final |
| 4 | reproducible runner | แพ็กเกจ `security_gate/` (ระดับบนสุด · แยกจาก `redbook` เพื่อคงกติกา local-first) · 8 step · เก็บ command/exit/UTC/version/raw/normalized/hash · INCOMPLETE ⇒ REVIEW · `--out` ต้องอยู่นอก git · target = loopback สังเคราะห์ที่ runner เปิดเอง (ไม่มีตัวเลือกชี้ URL อื่น) |
| 5 | regression tests ใหม่ | 6 ไฟล์ `tests/test_security_gate_*.py` = **48 test** (web/static/upload/export/logging/unit) ครอบ 8 กรณีในหมวด C ของใบ + กลไก fail-closed ของ runner |
| 6–7 | รัน synthetic · ZAP | รอบ formative `20261006T165937Z-formative` รันครบทุก step ยกเว้น ZAP (INCOMPLETE — เครื่องไม่มี Java/Docker) |
| 8–9 | triage · แก้ · rerun | finding ที่แก้โค้ด **5** (F-01..F-05) · ค้างคำตัดสิน 2 (F-06 defusedxml · F-08 ZAP) · tooling 3 (F-07 · T-01 · T-02) · รอบ final `20261006T172344Z-final` |
| 10 | research evidence package | `12_SECURITY_VERIFICATION_GATE/` — PROTOCOL · MATRIX.csv · FINDINGS_LOG · EVIDENCE_MAP · `runs/<run_id>/` (manifest · summary · control_results · steps/* · HASHES) |
| 11 | ส่ง Bo | รายงานนี้ |

## 2. ผลรอบ final `20261006T172344Z-final` (profile `LOOPBACK_HTTP` · matrix `36b5230a…`)

| ตัวชี้วัด (ตามใบ) | ค่า |
|---|---|
| 1. controls ที่ประกาศ | **51** |
| 2. applicable | **48** |
| 3. PASS / FAIL / REVIEW / N/A | **46 / 1 / 1 / 3** |
| 4. unresolved FAIL (High/Medium) | 1 (SG-16 · Low · REVIEW_REQUIRED) — ไม่มี High/Medium ค้าง · FAIL เดียวคือ defusedxml ยังไม่ติดตั้ง (รอคำตัดสิน) |
| 5. data-leakage findings | leak_check บนชุดหลักฐาน = PASS (ตรวจครบ 0 hit) · เส้นทางสัมบูรณ์ในหน้าเว็บ = 0 หน้า (ตรวจ 10 หน้า) |
| 6. dependency vulnerabilities ณ วันที่รัน | 0 · ตรวจได้ 40 จาก 42 (ข้าม pip · packaging — รายการข้ามที่ runner พิมพ์มี pdfminer.six ติดมาเพราะเทียบชื่อ `.`↔`-` ผิด (T-03 แก้แล้ว)) · pip-audit 2.10.1 |
| 7. browser/security regression | pytest 233 passed · 0 failed · browser 4 check PASS ทั้ง 4 (forms_submit · console_clean · cookie.flags · csrf.cross_site_form) |
| 8. ZAP alerts H/M/L/I | **INCOMPLETE** — ไม่มี Java/Docker บนเครื่อง ⇒ SG-50 = REVIEW (ไม่นับ PASS) |
| 9. before → after | F-01..F-05: FAIL (formative) → PASS (final) · ดู `FINDINGS_LOG.md` |

### before → after (จาก control_results ของสองรอบ)

| finding | control | formative | final |
|---|---|---|---|
| F-01 Host header ไม่ตรวจ (DNS rebinding) · Medium | SG-43 | FAIL (Host: evil.example ⇒ 200) | PASS |
| F-02 หน้า 500 ไม่มี security headers · Low | SG-39 | FAIL | PASS |
| F-03 ไม่จำกัดจำนวนสมาชิก zip · Low | SG-20 | FAIL | PASS |
| F-04 meta referrer ≠ หัว HTTP · Low | SG-29 | FAIL | PASS |
| F-05 `Server: uvicorn` · Informational | SG-42 | FAIL | PASS |
| F-06 ไม่มี defusedxml · Low | SG-16 | FAIL | FAIL (รอคำตัดสิน) |
| F-07 ตัวกลบของ gate พลาด backslash คู่ (tooling) | SG-27 | FAIL (leak_check 3 hit จากสตริงสมมติ) | PASS |
| T-01 test รับ 410 ของเส้นทางเดิม | SG-01 | FAIL (spec) | PASS |

## 3. สิ่งที่พบ (นอกเหนือจาก finding)

- **ด่าน fail-closed ทำงานจริง:** รอบ formative ขั้น L บล็อกหลักฐานที่มีรูปแบบเส้นทางเครื่อง (แม้เป็นสตริงสมมติ) ⇒ ไฟล์ดิบ 2 ไฟล์ของรอบนั้นถูก **กันไว้ไม่เผยแพร่** พร้อมแฮชใน `runs/…/PUBLICATION_NOTE.md`
- **ฟอร์มข้ามไซต์บนเบราว์เซอร์จริง** (หน้าโจมตีบน loopback คนละพอร์ต) ได้ 403 — ยืนยัน SameSite=Strict + double-submit ในสภาพแวดล้อมจริง ไม่ใช่แค่ TestClient
- การแยก `security_gate` ออกจาก `redbook` เป็นผลจาก test สถาปัตยกรรมเดิม (`test_no_outbound_network_libraries`) — กติกา local-first ของผลิตภัณฑ์ยังเข้มเท่าเดิม

## 4. tests/scans ที่รันจริง (บนเครื่องผู้พัฒนา · ไม่มี CI)

- ชุดเต็ม repo ระบบ (branch `sec/23-security-gate`): **1566 passed · 5 skipped** (baseline ก่อนเริ่ม 1463 passed · 4 skipped)
- รอบ formative + final ของ gate (8 step) · pip-audit 2.10.1 ใน venv แยกนอกโครงการ (ไม่แตะ `.venv`) · Playwright 1.60 + Chromium 148.0.7778.96
- leak_check 0.3.1 ครบ A–H + Z1–Z3 ต่อ: matrix/protocol (0 hit) · runs ที่เผยแพร่ (0 hit) · รายงานนี้ (0 hit)

## 5. ข้อจำกัด

- ประเมิน **subset** 51 ข้อ — ไม่ใช่ ASVS ทั้งฉบับ · ไม่มี L1/L2 claim · ไม่มีการตรวจอิสระจากภายนอก
- ZAP ยังไม่ได้รัน ⇒ ตัวชี้วัดข้อ 8 อ้างไม่ได้ · ตัวชี้วัดข้อ 6 คือ "ไม่พบที่ประกาศไว้ ณ วันที่รัน · ตรวจได้ x จาก y"
- check แบบ static เป็น heuristic · http probe ตรวจชุด URL ที่ประกาศ ไม่ใช่ crawl
- runner ทำซ้ำได้โดย **ผู้มีสิทธิ์เข้าถึง repo ระบบ** (private) · manifest บันทึกเพียงลายนิ้วมือของ commit
- matrix ของรอบ formative แฮชต่างจาก final เพราะ line ending (CRLF→LF) — เนื้อหาเดียวกัน บันทึกใน FINDINGS_LOG

## 6. สิ่งที่ยังค้าง

| # | เรื่อง | รอใคร |
|---|---|---|
| 1 | ติดตั้ง Java + OWASP ZAP (ระดับผู้ใช้) เพื่อรัน baseline · หรือเลื่อน | **Gift** (ASK-GIFT แยก) |
| 2 | ติดตั้ง `defusedxml` ลง `.venv` ประเมิน + ตรึงใน lock (F-06) | **Gift** (คำสั่งเดิมของ Bo: ไม่แตะ `.venv`) |
| 3 | push branch `sec/23-security-gate` ของ repo ระบบ (ตอนนี้ commit local) | Gift |
| 4 | SG-50 disposition หลัง ZAP รัน | Giho → Bo |

## 7. สิ่งที่ขอให้ Bo review

1. matrix: applicability/expected_result ของ 51 ข้อ — มีข้อใดที่ควร APPLICABLE แต่ประกาศ CONDITIONAL/N/A หรือกลับกัน
2. severity ของ F-01 (Medium) และ disposition FIXED ของ F-01..F-05 — หลักฐาน before/after พอหรือไม่
3. ถ้อยคำใน EVIDENCE_MAP C1–C9 ว่าอ้างในบทวิจัยได้จริงภายใต้ CLAIM_BOUNDARY
4. การตีความ "INCOMPLETE ⇒ REVIEW" ว่าเพียงพอสำหรับเงื่อนไข "ไม่มีผลที่ถูกนับ PASS จากการตรวจไม่ครบ" ใน Gate ของใบ
