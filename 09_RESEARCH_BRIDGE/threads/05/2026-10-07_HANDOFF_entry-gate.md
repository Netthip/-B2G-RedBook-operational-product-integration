# HANDOFF — #5 Evaluation Contract · ด่านทางเข้าการประเมิน + §9 forward status

**Giho → Bo** · 7 ตุลาคม 2569 · ตอบ `[REVIEW / DECISION] Bo → Giho — #5 Evaluation Contract`

## ทำตามคำตัดสินอย่างไร

| ข้อบังคับของ Bo | ทำอย่างไร | หลักฐาน |
|---|---|---|
| ไม่ย้าย posture เข้า `score()` | `scoring_v2.score()` **ไม่แตะเลย** · ยังรับรหัสสังเคราะห์ได้ | เทสต์ `test_score_itself_is_unchanged_and_still_generic` |
| final evaluation ต้องผ่าน posture validation ก่อน `score()` | โมดูลใหม่ `redbook/t1b_eval/entry_gate.py` · `evaluate()` = ทางเข้าเดียว · ตรวจก่อน ผ่านแล้วจึงเรียก `score()` | `01_pass.json` |
| undeclared type ⇒ block | `UNDECLARED_TYPE` (ไม่อยู่ในบัญชี หรือยังไม่ประกาศ) + `POSTURE_TABLE_NOT_READY` (ตารางมีชนิดไม่ประกาศ) | `02_…json` |
| stratum mismatch ⇒ block | `STRATUM_MISMATCH` — **รวมกรณีปล่อยค่าตั้งต้น `PRIMARY` ของ `GoldDefect` ไว้กับชนิด `EXPLORATORY`** (ไม่เชื่อค่าตั้งต้น) | `03_…json` |
| negative-control misuse ⇒ block | `NEGATIVE_CONTROL_MISUSE` — ชนิด `MUST_NOT_REPORT` อยู่ในเฉลย | `04_…json` |
| ห้ามเปลี่ยน posture หลังเห็นผลโดยไม่มี version ใหม่ | `POSTURE_VERSION_DRIFT` เมื่อรุ่นที่ manifest ผูกไว้ ≠ รุ่นที่โหลด · และบันทึก SHA-256 ของเนื้อตาราง (แก้ท่าทีโดยไม่ขึ้นรุ่น ⇒ แฮชเปลี่ยน) | `05_…json` · เทสต์ fingerprint |
| gate result ลง manifest/evidence | `GateRecord` → `manifest["posture_gate"]` ทั้งผ่านและไม่ผ่าน (ไม่ผ่าน = แนบมากับ `EvaluationBlocked.record`) | ไฟล์ JSON ทั้ง 5 |
| ห้าม bypass เงียบ | `evaluate()` ไม่มีพารามิเตอร์ข้ามด่าน และ **ไม่รับ `expected_referral_types` จากผู้เรียก** · เทสต์ AST ยืนยันว่าไม่มีโค้ดผลิตภัณฑ์อื่น import `scoring_v2` · เทสต์ยืนยันว่า `score()` ไม่ถูกเรียกเมื่อ block | `test_violation_blocks_scoring` · `test_no_product_code_calls_…` |

ด่านรายงาน **ทุกข้อที่ผิด** ไม่หยุดที่ข้อแรก

## เอกสาร

`LANE_C_BLIND_EVALUATION_PROTOCOL.md` §9 — เพิ่มกล่อง **FORWARD STATUS 7 ต.ค.** ต่อท้าย
ตารางเดิม 6 ก.ย. **คงไว้ไม่แก้** · กล่องระบุ: รุ่นปัจจุบัน (schema 0.2.0 · posture 0.2.0 · gate 0.1.0)
พร้อมวันที่เกิดของแต่ละรุ่น · source-of-truth ของท่าที · evaluation-entry gate ·
referral measurement ที่ S-06/T-02 ทำให้วัดได้ · และเขียนชัดว่า ณ 6 ก.ย. ยังไม่มีสิ่งเหล่านี้

🔴 กล่องนี้ **ไม่เปลี่ยนข้อใดใน checklist เป็น "ผ่าน"** · ข้อ 1 ยัง 🟠 ไม่ตรึง (รอ Bo) · ข้อ 2–3 human-owned คงเดิม

## สิ่งที่ยังไม่ได้ทำ / ข้อจำกัด

* commit ระบบ `47bb3df` อยู่ branch `eval/5-entry-gate` (repo private) **ยังไม่ push · ยังไม่ merge**
* ด่านตรวจเฉพาะ **เฉลย** · `finding_type` ของ detector output ไม่ถูกบังคับให้อยู่ในบัญชี (ชนิดผิดถูกนับเป็น `LOCTYPE_AUTO`/`FP` ตามสเปกอยู่แล้ว)
* ยังไม่มีการประเมินจริงใด ๆ · ตัวเลข referral ในหลักฐานเป็นข้อมูลสังเคราะห์เพื่อพิสูจน์กลไกเท่านั้น
* tests 1266 passed + 4 skipped ในเครื่องผู้พัฒนา · **ไม่มี CI**

## ขอจาก Bo

ตรวจ gate + §9 forward status + หลักฐาน แล้วพิจารณาปิด #5
