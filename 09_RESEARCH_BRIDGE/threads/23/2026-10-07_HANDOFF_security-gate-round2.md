# #23 — HANDOFF รอบ 2: หลังคำตัดสินกิ๊ฟ (6026979007) — ZAP รันแล้ว · F-06 ปิด · READY FOR REVIEW

**ผู้ทำ:** Giho · **วันที่:** 7 ตุลาคม 2569 · **ตอบ:** คำตัดสินกิ๊ฟ `6026979007` + handoff รอบ 1 (`6021776527` · `threads/23/2026-10-07_HANDOFF_security-gate-0.1.0.md`)
**สถานะ:** `READY FOR REVIEW` (Bo) · **รอบ final อ้างอิง = `20261006T231414Z-final`** (แทน `20261006T172344Z-final` ซึ่งเป็น before ของ F-06/F-08)

## 1. สิ่งที่ทำตามคำตัดสิน

| ข้อ | สิ่งที่ทำ | หลักฐาน |
|---|---|---|
| 1 Java + ZAP | Temurin 21 JRE (`21.0.12.1+1`) + **OWASP ZAP 2.17.0** cross-platform · ติดตั้ง**ระดับผู้ใช้**จาก release ทางการ · ตรวจ SHA-256 ตรงกับค่าที่ผู้เผยแพร่ประกาศทั้งสองไฟล์ก่อนแตก · ไม่แตะระบบ/PATH ของเครื่อง | `runs/<final>/steps/zap/meta.json` (รุ่น ZAP/Java · sha256 ของ jar) |
| 1 วิธีสแกน | **Automation Framework**: `spider` (GET-only · ไม่ส่งฟอร์ม · ≤2 นาที) + `passiveScan-wait` + `report` (json/html) — **ไม่มี job activeScan** · target = loopback สังเคราะห์ที่ runner เปิดเอง | `steps/zap/zap_plan.yaml` (สำเนากลบเส้นทาง) · `command.txt` |
| 2 defusedxml | `defusedxml==0.7.1` ลง `.venv` ประเมิน + ตรึงใน `requirements.lock.txt` (หมายเหตุ ASCII อ้างคำตัดสิน) · openpyxl รายงาน `DEFUSEDXML=True` | `steps/environment/frozen.txt` · commit ระบบ (private) |
| 3 push | branch `sec/23-security-gate` ขึ้น remote private แล้ว (9 commit) | — |
| rerun | รันทั้งชุดใหม่ 3 ครั้งจนได้รอบที่ด่าน L ผ่าน (รอบที่ 1–2 ติด tooling T-06/T-07 ของ runner เอง · ไม่เผยแพร่) | `FINDINGS_LOG.md` |

## 2. ผลรอบ final `20261006T231414Z-final` (profile `LOOPBACK_HTTP` · matrix `36b5230a…`)

| ตัวชี้วัด | ค่า | เทียบรอบก่อน (`20261006T172344Z-final`) |
|---|---|---|
| controls ประกาศ / applicable | 51 / 48 | เท่าเดิม |
| PASS / FAIL / REVIEW / N/A | **47 / 0 / 1 / 3** | 46 / 1 / 1 / 3 |
| unresolved FAIL | **0** | 1 (SG-16) |
| REVIEW | SG-50 — ZAP **รันครบแล้ว** แต่เป็น control แบบ manual ⇒ รอ disposition ของคน | SG-50 (INCOMPLETE) |
| ZAP alerts High / Medium / Low / Informational | **0 / 0 / 0 / 2** | — (ไม่ได้รัน) |
| dependency vulns ณ วันที่รัน | 0 · ตรวจได้ **41 จาก 43** (ข้าม pip, packaging) | 0 · 40/42 |
| leak_check ชุดหลักฐาน | ตรวจครบ 0 hit | เท่าเดิม |
| security regression | pytest 233/233 · browser 4/4 | เท่าเดิม |
| integrity | `sha256sum -c HASHES.sha256` ผ่าน · แฮช HASHES ตรง manifest · ไม่มี CR | เท่าเดิม |

### ZAP alerts (ทั้งสองเป็น Informational — ไม่ต้องมี disposition ตามกติกา High/Medium แต่บันทึกให้ครบ)

| plugin | ชื่อ | ครั้ง | การอ่าน |
|---|---|---|---|
| 10112 | Session Management Response Identified | 2 | ZAP เห็นคุกกี้ `redbook_csrf` แล้วเดาว่าเป็น session — ที่จริงเป็นโทเคน CSRF (double-submit) · ไม่มี session ในระบบ (SG-44) |
| 10031 | User Controllable HTML Element Attribute (Potential XSS) | 14 | ค่าจาก query (เช่น ฟิลเตอร์หน้าคิว) ถูกใส่กลับใน attribute ของ input — passive rule แจ้ง "potential" · output encoding เปิดอยู่ (SG-12 PASS · test สะท้อน `<script>` ไม่พบ) · เสนอให้ Bo ยืนยันเป็น `FALSE_POSITIVE`/`ACCEPTED_RISK` ใน disposition ของ SG-50 |

### before → after ที่เพิ่มรอบนี้

| finding | before | after |
|---|---|---|
| F-06 defusedxml | SG-16 FAIL (`20261006T172344Z-final`) | SG-16 **PASS** (`20261006T231414Z-final`) · **FIXED** |
| F-08 ZAP ไม่พร้อม | SG-50 REVIEW/INCOMPLETE | SG-50 REVIEW (รันแล้ว · รอ disposition) · tooling พร้อมถาวร |

## 3. ข้อจำกัดของรอบนี้

- spider GET-only พบ **16 URL** (ไม่ส่งฟอร์มจึงไม่ลึกถึงหน้าหลังการวิเคราะห์) — passive rules ตรวจเฉพาะ response ที่เห็น · ไม่ใช่ coverage ของทุกเส้นทาง · active scan อยู่นอกขอบเขต (ตามเงื่อนไขกิ๊ฟ)
- SG-50 เป็น `manual` โดยประกาศ ⇒ จะเป็น PASS ไม่ได้จนกว่าคนจะลง `dispositions.json` (รูปแบบ `{"SG-50": {"disposition": "...", "reason": "...", "by": "...", "date": "..."}}`) แล้วรันซ้ำ — ขอให้ **Bo เสนอ** และ **Gift ยืนยัน**
- ถ้อยคำยังเท่าเดิม: "ประเมินตาม subset 51 ข้อที่ประกาศล่วงหน้าจาก ASVS v5.0.0" · ไม่อ้าง "ผ่าน ASVS" · ไม่อ้าง "แฮกไม่ได้" · ZAP = baseline/passive บน target สังเคราะห์

## 4. สิ่งที่ขอให้ Bo review (เพิ่มจากรอบ 1)

1. การอ่าน alert 10031/10112 ข้างบน และ disposition ที่ควรลงให้ SG-50
2. การยอมรับ "Automation Framework spider GET-only + passive" ว่าเทียบเท่า baseline ตามเจตนาของใบ (#23 §D) หรือต้องเปิด postForm
3. ยืนยันว่ารอบ `20261006T172344Z-final` ใช้เป็น before ของ F-06/F-08 ได้ และรอบอ้างอิงเป็น `20261006T231414Z-final`
