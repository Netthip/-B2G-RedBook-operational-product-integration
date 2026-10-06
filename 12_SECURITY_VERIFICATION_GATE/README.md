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
| `runs/<run_id>/` | หลักฐานต่อรอบ (manifest · summary · control_results · steps/* · HASHES) ที่ผ่าน leak_check แล้ว | ต่อรอบ |

## วิธีอ่านผลหนึ่งรอบ

1. `runs/<run_id>/SECURITY_RUN_MANIFEST.json` — `phase` (formative/final) · `profile` · `matrix.sha256` ต้องตรงกับไฟล์ CSV ใน commit ที่อ้าง · เวอร์ชันเครื่องมือ · exit code ทุก step
2. `SECURITY_RESULT_SUMMARY.md` — ตัวชี้วัด 9 ข้อ + สถานะราย control พร้อมเหตุผล
3. `control_results.json` — สถานะราย check (machine-readable)
4. `steps/<step>/` — raw ของเครื่องมือ + `command.txt` + `meta.json`
5. `HASHES.sha256` — แฮชทุกไฟล์ในรอบ · manifest เก็บแฮชของไฟล์แฮชอีกชั้น

## สิ่งที่หมวดนี้ไม่ใช่

- ไม่ใช่ penetration test · ไม่รับรองว่า "แฮกไม่ได้" · ไม่ใช่หลักฐานว่าผ่าน ASVS ทั้งฉบับ
- ไม่มีการสแกนเชิงรุกต่อระบบ/โดเมนใดนอกจาก target สังเคราะห์บน loopback ที่ runner เปิดเอง
- ไม่เปลี่ยนผลวิจัยที่ freeze แล้ว (ทะเบียนตัวชี้วัด · T1 frozen evaluation · Evidence Index)
