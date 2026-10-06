# EVIDENCE MAP — research claim → metric → artifact → run/version

**รุ่น:** 0.1.0 · **ผูกกับ:** protocol `security-verification-protocol-0.1.0` · matrix `36b5230a…` · gate `security-gate-0.1.0` · ASVS v5.0.0
**รอบที่อ้าง:** final = `20261006T171428Z-final` · formative (before) = `20261006T165937Z-formative`

> 🔴 ข้อกล่าวอ้างทุกข้อด้านล่างต้องยกไปใช้ **ตามถ้อยคำในคอลัมน์ "อ้างได้"** เท่านั้น · ตัวเลขทุกตัวมาจาก `runs/<run_id>/SECURITY_RUN_MANIFEST.json` และ `control_results.json`

| # | research claim (อ้างได้) | metric | artifact | run/version |
|---|---|---|---|---|
| C1 | "เว็บแอปถูกประเมินด้วย **เกณฑ์ที่ประกาศล่วงหน้า** 51 control ที่จัดหมวดและอ้างอิง requirement ของ OWASP ASVS v5.0.0 (subset) ก่อนเห็นผล" | controls declared = 51 · หมวด 12 | `SECURITY_CONTROL_MATRIX.csv` (commit `68ce555`) · `SECURITY_VERIFICATION_PROTOCOL.md` (commit `ed79968`) | matrix `36b5230a…` |
| C2 | "ภายใต้ profile `LOOPBACK_HTTP` มี control ที่ใช้บังคับ N ข้อ · ผล PASS/FAIL/REVIEW/N/A = …" | applicable · PASS · FAIL · REVIEW · N/A | `runs/20261006T171428Z-final/SECURITY_RUN_MANIFEST.json#counts` · `control_results.json` | `20261006T171428Z-final` |
| C3 | "ไม่มี control ที่ถูกนับ PASS จากการตรวจไม่ครบ — check ที่ INCOMPLETE/ไม่ได้รัน ⇒ REVIEW ตามกติกาที่ประกาศ" | จำนวน REVIEW และเหตุผล | `control_results.json#controls[].reason` · กติกาใน protocol §4 · tests `tests/test_security_gate_unit.py` (fail-closed) | `20261006T171428Z-final` · gate 0.1.0 |
| C4 | "finding จากรอบพัฒนาที่นำไปแก้โค้ด 5 รายการ (F-01..F-05) มีผล before/after ตรวจย้อนได้" | before status → after status ต่อ finding | `FINDINGS_LOG.md` · `runs/<formative>/control_results.json` · `runs/20261006T171428Z-final/control_results.json` | `20261006T165937Z-formative` → `20261006T171428Z-final` |
| C5 | "ไม่พบช่องโหว่ที่ประกาศไว้ในฐานข้อมูล ณ วันที่รัน สำหรับแพ็กเกจที่เครื่องมือตรวจได้ (x จาก y)" | vulnerabilities · audited · skipped | `runs/20261006T171428Z-final/steps/pip_audit/raw.json` · `audit_input.txt` · `steps/environment/frozen.txt` | `20261006T171428Z-final` · pip-audit 2.10.1 |
| C6 | "ชุดหลักฐานที่เผยแพร่ผ่านตัวตรวจการรั่ว 8 หมวด + 3 หมวดพื้นฐาน (fail-closed) · 0 hit — โดย 0 hit ไม่ใช่หลักฐานปลอดการเปิดเผย" | L:evidence_leak_check · H:leak.pages | `runs/20261006T171428Z-final/steps/leak_check/stdout.txt` · `steps/http_probes/result.json#H:leak.pages` | `20261006T171428Z-final` · leak-check-0.3.1 |
| C7 | "regression ด้านความปลอดภัยที่ประกาศ (N test) ผ่านทั้งหมดในรอบ final · และ flow บนเบราว์เซอร์จริง (Chromium) ส่งฟอร์มได้ · console/CSP violation = 0 · ฟอร์มข้ามไซต์ถูกปฏิเสธ 403" | pytest passed/failed · B:* | `runs/20261006T171428Z-final/steps/pytest/junit.xml` · `steps/browser/result_raw.json` | `20261006T171428Z-final` |
| C8 | "ZAP baseline (passive) …" | alert H/M/L/I | `runs/20261006T171428Z-final/steps/zap/` | 🔴 **ยังอ้างไม่ได้** — INCOMPLETE (ไม่มี Java/Docker) จนกว่าจะรัน |
| C9 | "ระบบมีมาตรการที่ตรวจแล้ว: CSRF double-submit + origin check · security headers (CSP/nosniff/frame-ancestors/COOP/Referrer-Policy/no-store) · ตรวจชนิดไฟล์จากไบต์จริง + เพดาน zip · กัน formula injection ใน CSV/XLSX · กลบเส้นทางสัมบูรณ์ · ตรวจหัว Host · บันทึก security events" | สถานะ control ของหมวด 2 · 4 · 5 · 6 · 7 · 9 | `control_results.json` | `20261006T171428Z-final` |

## สิ่งที่ **ห้าม** map

- "ผ่าน ASVS" / "ระดับ L1/L2" — ประเมินเพียง subset · ไม่มีการตรวจอิสระจากภายนอก
- ผล formative ใด ๆ เป็นผลประเมิน — ใช้ได้เฉพาะเป็น "before" ของ finding
- ผลของด่านนี้ไปรวมกับ accuracy ของเครื่องยนต์ตรวจเอกสาร หรือกับ P1 Validator
- "ทำซ้ำได้โดยสาธารณะ" — runner อยู่ใน repo ระบบ (private) ⇒ "ทำซ้ำได้โดยผู้มีสิทธิ์เข้าถึง repo ระบบ"
