# 12 — Web Security Verification Gate (Issue #23)

> หมวดนี้คือ **หลักฐานด้านความปลอดภัย/ความเป็นส่วนตัวของเว็บแอป** RedBook Verify สำหรับอ้างในบทวิจัย
> แยกจากผลความสามารถของเครื่องยนต์ตรวจเอกสาร (T1A/T1B) และแยกจาก P1 Validator โดยสิ้นเชิง — **ห้ามรวมคะแนน**
>
> 🔴 ถ้อยคำที่อ้างได้/ห้ามอ้าง อยู่ที่หัว [`SECURITY_VERIFICATION_PROTOCOL.md`](SECURITY_VERIFICATION_PROTOCOL.md) — อ่านก่อนเขียนอะไรในเล่ม

## สารบัญ

| ไฟล์ | คือ | สถานะ |
|---|---|---|
| [`SECURITY_VERIFICATION_PROTOCOL.md`](SECURITY_VERIFICATION_PROTOCOL.md) | กติกาทั้งหมด: มาตรฐานอ้างอิง · profile · สถานะ fail-closed · ขั้นตอน runner · formative/final · ถ้อยคำ | `PREDECLARED — PENDING BO REVIEW` |
| [`SECURITY_CONTROL_MATRIX.csv`](SECURITY_CONTROL_MATRIX.csv) | **predeclared matrix** 51 control · 12 หมวด · อ้าง ASVS v5.0.0 ราย requirement · check id ที่ runner ใช้ | `v0.1.0` |
| [`EVIDENCE_MAP.md`](EVIDENCE_MAP.md) | research claim → metric → artifact → run/version | เติมหลังรอบ final |
| [`FINDINGS_LOG.md`](FINDINGS_LOG.md) | finding ที่ทำให้แก้โค้ด · before/after · disposition | สะสม |
| [`dispositions.json`](dispositions.json) | disposition ของ control แบบ manual (SG-50) · runner อ่านอย่างเดียว · นับเมื่อ `accepted_by` ไม่ว่าง | Bo รับแล้ว (`6030358199`) |
| `runs/<run_id>/` | หลักฐานต่อรอบ (manifest · summary · control_results · steps/* · HASHES) ที่ผ่าน leak_check แล้ว — **รอบอ้างอิงปัจจุบัน `20261007T034045Z-final` (closeout · matrix 0.1.2)** · รอบอื่นมี `SUPERSEDED.md`/`HASH_NOTE.md` กำกับ | ต่อรอบ |

## วิธีอ่านผลหนึ่งรอบ

1. `runs/<run_id>/SECURITY_RUN_MANIFEST.json` — `phase` (formative/final) · `profile` · `matrix.sha256` ต้องตรงกับไฟล์ CSV ใน commit ที่อ้าง · เวอร์ชันเครื่องมือ · exit code ทุก step
2. `SECURITY_RESULT_SUMMARY.md` — ตัวชี้วัด 9 ข้อ + สถานะราย control พร้อมเหตุผล
3. `control_results.json` — สถานะราย check (machine-readable)
4. `steps/<step>/` — raw ของเครื่องมือ + `command.txt` + `meta.json`
5. `HASHES.sha256` — แฮชทุกไฟล์ในรอบ · manifest เก็บแฮชของไฟล์แฮชอีกชั้น

## ความสัมพันธ์กับเอกสารเลนเดิม (forward status · 7 ต.ค. 2569)

ตารางในเอกสารเลนเดิมคือ **ประวัติ** — ไม่ได้แก้ย้อนหลัง (ไฟล์เหล่านั้นมี leak-check hit เดิมหมวด D ที่รอคำตัดสินแยกใน #25 จึงไม่แตะในรอบนี้)

| เอกสารเดิม | รายการ | สถานะเดิม | สถานะจริงตอนนี้ |
|---|---|---|---|
| `09_RESEARCH_BRIDGE/LANES_BACKLOG.md` | C-08 dependency/secret scan · C-09 OWASP ZAP | `READY` · `BLOCKED-GIFT` | ย้ายเข้า gate นี้ — C-08 = SG-48/SG-49 (รันแล้ว) · C-09 = SG-50 (ใบ #23 ปลด **เฉพาะ baseline/passive ต่อ target สังเคราะห์บน loopback** · ยัง INCOMPLETE จนกว่าจะติดตั้ง Java/ZAP) |
| `09_RESEARCH_BRIDGE/LANE_D1P_PRODUCT_EXTENSION_CROSSWALK.md` | S-1..S-6 | หลายสถานะ | จัดเข้า matrix 51 control · ผลราย control ที่ `runs/<run_id>/` |
| `09_RESEARCH_BRIDGE/LANE_D1R_THESIS_RESEARCH_CROSSWALK.md` | `O-R7` ประเมินความปลอดภัยของเว็บแอป | `NOT YET MEASURED` | มีเครื่องมือวัดและผลรอบ final แล้ว (ดู `EVIDENCE_MAP.md`) · ยังไม่อยู่ใน Evidence Index ที่ freeze · ZAP ส่วนเดียวยัง INCOMPLETE |

active scan · Phase 3 PDF · Audit Trail import **ยัง BLOCKED ตามเดิม** — ใบ #23 ไม่ได้ปลด

## สิ่งที่หมวดนี้ไม่ใช่

- ไม่ใช่ penetration test · ไม่รับรองว่า "แฮกไม่ได้" · ไม่ใช่หลักฐานว่าผ่าน ASVS ทั้งฉบับ
- ไม่มีการสแกนเชิงรุกต่อระบบ/โดเมนใดนอกจาก target สังเคราะห์บน loopback ที่ runner เปิดเอง
- ไม่เปลี่ยนผลวิจัยที่ freeze แล้ว (ทะเบียนตัวชี้วัด · T1 frozen evaluation · Evidence Index)
