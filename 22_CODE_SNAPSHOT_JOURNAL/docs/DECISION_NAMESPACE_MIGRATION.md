# DECISION_NAMESPACE_MIGRATION — การย้ายรหัสคำตัดสินสู่ namespace ใหม่

**repo นี้:** `redbook-verify` (System Implementation SSOT) · **รหัสใหม่:** `SYS-D-xx` / `SYS-G-xx` / `SYS-Q-xx` / `SYS-F-xx`
**วันที่:** 27 ส.ค. 2569 · **อำนาจ:** คำตัดสินผู้รับผิดชอบงานวิจัย เรื่องการแยก namespace (บันทึกเต็มที่ `redbook-verify-is: RES-D-26`)

## เหตุผล

พบว่ามีงานสองสายดำเนินคู่ขนานในวันเดียวกัน และใช้รหัส `D1`–`D10` กับ `G1`–`G5` ซ้ำกันโดยเป็นคนละคำถาม
การรวมเป็นรายการเดียวจะทำให้อ้างอิงผิด จึงแยก namespace ถาวร

## หลักการ

1. **ไม่แก้ประวัติ** — รหัสเดิมใน commit เก่าคงอยู่ตามเดิม ไม่ rewrite history
2. รหัสเดิมทุกตัวมีสถานะ **`LEGACY AMBIGUOUS ID — DO NOT CITE WITHOUT REPOSITORY NAME`**
3. การอ้างอิงต่อจากนี้ใช้ canonical ID ใหม่เท่านั้น

## ขอบเขตอำนาจของ namespace นี้

`SYS-*` เป็นเจ้าของ: canonical schema ในโค้ด · semantic mapping implementation · parser · composite key implementation · rule engine · database · API/UI · reproducibility · security controls · automated tests · เงื่อนไขทางเทคนิคก่อนรัน

**`SYS-*` ไม่ใช่เจ้าของ:** ขอบเขตการวิจัย · ชุดข้อมูลหลัก/เสริม · คู่เอกสารที่ใช้ทดลอง · หน่วยวิเคราะห์ · atomic finding · gold standard · dev/eval split · metrics · Mutation Protocol · วิธีรายงานผล · ขอบเขตข้อความในบทที่ 1–5 — ทั้งหมดนี้เป็นของ `RES-*` ใน repo `redbook-verify-is`

> ⚠️ **หากคำตัดสินระบบขัดกับระเบียบวิธีที่ล็อกไว้ใน repo เล่ม ระบบต้องหยุดและรายงาน conflict — ห้ามเปลี่ยนวิธีวิจัยตามความสะดวกของโค้ด**

## ตารางย้ายรหัส — คำตัดสิน

| Legacy repository | Legacy ID | Legacy title | New canonical ID | Owner repo | Status | Superseded by | Cross-reference |
|---|---|---|---|---|---|---|---|
| redbook-verify | D-2569-08-26-01 | รับรอง Phase 0–1 เป็นสถานะตั้งต้น | **SYS-D-01** | redbook-verify | active | — | — |
| redbook-verify | D-2569-08-26-02 | สถานะสภาพแวดล้อม | **SYS-D-02** | redbook-verify | active | — | **RES-D-02 (aligned)** |
| redbook-verify | D-2569-08-27-01 | Q5 เกณฑ์ร้อยละ 10% = highlight_only | **SYS-D-03** | redbook-verify | active | — | — |
| redbook-verify | D-2569-08-27-02 | ข้อความเมื่อฐานคำนวณเป็นศูนย์ | **SYS-D-04** | redbook-verify | active | — | — |
| redbook-verify | D-2569-08-27-03 | Q8 ตำแหน่งข้อมูล | **SYS-D-05** | redbook-verify | active | — | `RES: CANONICAL_DATA_DIRECTORY.md` |
| redbook-verify | D-2569-08-27-04 | อ่านไฟล์ read-only + SHA (Phase 2A) | **SYS-D-06** | redbook-verify | active | — | — |
| redbook-verify | D-2569-08-27-05 | secure upload storage (Phase 2C+) | **SYS-D-07** | redbook-verify | active | — | — |
| redbook-verify | D-2569-08-27-06 | ขอบเขต 2 หน่วยงาน | **SYS-D-08** | redbook-verify | active | — | **RES-D-08 (aligned)** |
| redbook-verify | D-2569-08-27-07 | แยก AO/คาดแดง ออกจาก ป.1 | **SYS-D-09** | redbook-verify | active | — | RES-D-24 (T1B) |
| redbook-verify | D-2569-08-27-08 | นิยามคู่เปรียบเทียบก่อน–หลังปรับลด | **SYS-D-10** | redbook-verify | active | — | RES-D-03 |
| redbook-verify | D-2569-08-27-09 | หน่วยเงินเฉพาะที่มีหลักฐาน | **SYS-D-11** | redbook-verify | active | — | RES-Q-04 |
| redbook-verify | D-2569-08-27-10 | matching pipeline 5 ขั้น | **SYS-D-12** | redbook-verify | active | — | RES-Q-03 |
| redbook-verify | D-2569-08-27-11 | ประเด็นที่ห้ามสรุปเอง | **SYS-D-13** | redbook-verify | active | — | RES-D-23 |
| redbook-verify | D-2569-08-27-12 | ยืนยัน D1–D10 ของสายระบบ | **SYS-D-14** | redbook-verify | active | — | ดูตาราง SYS-Q ด้านล่าง |
| redbook-verify | F-2569-08-27-01 | พบ SCHEMA CONFLICT | **SYS-F-01** | redbook-verify | **resolved** | **RES-D-25** | เลือกทางออก ง — T1A-E2 เป็น safe-failure demo |

## ตารางย้ายรหัส — คำถามออกแบบ D1–D10 (ชนกับสายเล่ม)

> 🔴 รหัส `D1`–`D10` มีอยู่ทั้งสอง repo แต่เป็นคนละคำถามโดยสิ้นเชิง

| Legacy ID (repo นี้) | Legacy title | New canonical ID | สายเล่มใช้เลขเดียวกันสำหรับ |
|---|---|---|---|
| D1 | ชั้นข้อมูล T1–T5 | **SYS-Q-01** | หน่วยของคู่เปรียบเทียบ |
| D2 | สถานะ T2 = development-only | **SYS-Q-02** | การจับคู่ชีต Excel |
| D3 | คู่เปรียบเทียบภายในปี 2569 | **SYS-Q-03** | คีย์จับคู่รายการ |
| D4 | อนุมัติ Y-2 ไม่อนุมัติ Y-1 | **SYS-Q-04** | หน่วยเงินและสเกล |
| D5 | บทบาทชีต `Data Dict` / `data` | **SYS-Q-05** | เกณฑ์ tolerance |
| D6 | หน่วยเงิน `p_total_bud` = บาท | **SYS-Q-06** | หัวข้อคาบเกี่ยวหน้า PDF |
| D7 | คีย์ผสม 9 บทบาทข้อมูล | **SYS-Q-07** | ชีตฐานข้อมูลประกอบ |
| D8 | canonical hierarchy จาก Data Dict | **SYS-Q-08** | การเทียบข้ามรูปแบบ PDF↔Excel |
| D9 | tolerance = 0 บาท (exact) | **SYS-Q-09** | Excel ที่ยังไม่พบ |
| D10 | structure move → คู่รอ Human Review | **SYS-Q-10** | ขอบเขต atomic finding |

## ตารางย้ายรหัส — ประตู G1–G5 (ชนกับสายเล่ม)

| Legacy ID (repo นี้) | Legacy title | New canonical ID | สายเล่มใช้เลขเดียวกันสำหรับ |
|---|---|---|---|
| G1 | Canonical Schema (freeze) | **SYS-G-01** | ขอบเขตหน้าที่ใช้สร้าง gold standard |
| G2 | Semantic Mapping จาก Data Dict | **SYS-G-02** | นิยาม atomic finding |
| G3 | Composite Key และ Matching Pipeline | **SYS-G-03** | ใช้ Excel ช่วยยืนยันการสกัด PDF |
| G4 | หมวดผลตรวจและกฎการจัดหมวด | **SYS-G-04** | จำนวนรอบอ่านย้อน gold standard |
| G5 | Experiment Protocol (ฝั่งระบบ) | **SYS-G-05** | การจัดการรายการที่ยังไม่แน่ใจ |

## ชั้นข้อมูล: การเทียบกับชื่อใหม่ของสายเล่ม

ตาม `RES-D-24` ชั้นข้อมูลถูกแยกใหม่เป็น T1A / T1B / T2

| ชั้นใน repo นี้ | ชั้นใหม่ที่บังคับใช้ | หมายเหตุ |
|---|---|---|
| T1 — PUBLIC PRIMARY (Excel Data Table แบน) | **T1A** | ไฟล์ 3 รายการใน `.data/public_sources/` |
| *(ไม่มีในสายนี้)* | **T1B** | Excel AO workbook + PDF เล่มกระทรวง — อยู่ที่ `redbook-verify-data/sources/public/` |
| T2 — INTERNAL AO/REDBOOK | **T2** | ชื่อและความหมายตรงกัน |
| T3 — P1 SUPPLEMENTARY | *(นอกขอบเขตเล่ม v3.0)* | — |
| T4 — UNCLASSIFIED | *(ใช้สถานะ "ยังไม่ยืนยัน")* | — |
| T5 — ARCHIVE / PRIOR ARTIFACT | *(ตรงกับ `RES: ARCHIVE_BOUNDARY.md`)* | — |

> 🔴 **`T1` ของ repo นี้ = `T1A` เท่านั้น ไม่รวม `T1B`**

## กติกาการอ้างอิงต่อจากนี้

- ✅ `SYS-D-14` · `SYS-Q-07` · `SYS-G-01` · `RES-D-25`
- ❌ `D7` เดี่ยว ๆ (กำกวม) · `G1` เดี่ยว ๆ (กำกวม) · `D-2569-08-27-12` (legacy)

## ส่วนเพิ่มที่ 1 — 27 ส.ค. 2569 (รอบค่ำ): รายการ legacy ที่บันทึกหลังจัดทำตารางข้างต้น

> เพิ่มรายการอย่างเดียว ไม่แก้ตารางเดิม · บันทึกโดยจีโฮ ตามคำสั่งของกิ๊ฟ (คำสั่งชุดสภาพแวดล้อม/แนวทางขยายระบบ)
> การจับเลขเป็นงานทะเบียนเชิงกลไก (เรียงต่อจาก SYS-D-14 / SYS-F-01) — **ไม่ใช่การรับรองเนื้อหา**
> เนื้อหาของทั้ง 4 รายการอยู่ในขอบเขตการตรวจสอบของ `INC-2569-08-27-01` (repo เล่ม)

| Legacy repository | Legacy ID | Legacy title | New canonical ID | Status |
|---|---|---|---|---|
| redbook-verify | D-2569-08-27-13 | P1–P6 (ล็อกแล้ว) และอนุญาตเริ่ม Phase 2C | **SYS-D-15** | mapped · เนื้อหารอผลตรวจสอบ incident |
| redbook-verify | D-2569-08-27-14 | สถานะ Phase 2C และการกระทบยอดรายงาน | **SYS-D-16** | mapped · เช่นเดียวกัน |
| redbook-verify | F-2569-08-27-02 | บันทึกการ freeze และผลการรัน Phase 2C | **SYS-F-02** | mapped · เช่นเดียวกัน |
| redbook-verify | F-2569-08-27-03 | ผลการกระทบยอดและการแก้เครื่องมือตรวจหลักฐาน | **SYS-F-03** | mapped · เช่นเดียวกัน |

คำตัดสินใหม่ตั้งแต่ 27 ส.ค. 2569 รอบค่ำเป็นต้นไป เขียนด้วยรหัส canonical โดยตรงใน `docs/DECISIONS_LOG.md`
เริ่มที่ **SYS-D-17** (ชุดสภาพแวดล้อมสามระยะ) — ดูทะเบียนกลางภาคผนวก ก ใน repo เล่ม

## ส่วนเพิ่มที่ 2 — 28 ส.ค. 2569: ผังเลข `SYS-D-*` ปัจจุบัน (RES-D-47 ข้อ ①)

> เพิ่มรายการอย่างเดียว ไม่แก้ตารางเดิม · ทะเบียนกลางฉบับเต็ม: `redbook-verify-is`
> `00_project_control/CROSS_REPO_DECISION_REGISTER.md` **ภาคผนวก ข** (commit `a09a44b`)

| เลข | เรื่อง | mirror ของสายเล่ม | สถานะ |
|---|---|---|---|
| SYS-D-01..16 | ตามตารางย้ายรหัสด้านบนและส่วนเพิ่มที่ 1 | — | active |
| SYS-D-17..20 | สภาพแวดล้อมสามระยะ · แยก data store · portable deployment · roles | RES-D-27 · RES-D-29 · RES-D-31/32 · RES-D-27 | active |
| SYS-D-21 | รับรองการกระทบยอด · อนุญาต Human Review รอบ 1 · reviewpack-1.1.0 | — | active · **ถ้อยคำสถานะถูกแทนโดย SYS-D-27** |
| **SYS-D-22 · SYS-D-23 · SYS-D-24** | 🔒 **จองไว้** ให้ร่างของสาย incident (คู่ `RES-D-34`–`RES-D-36`) | — | **ร่างยังไม่อนุมัติ · ห้ามใช้เลขกับเรื่องอื่น** |
| SYS-D-25 | `result_hash` = Semantic Result Hash + หลักฐาน 6 ชั้น | **RES-D-39** | active |
| SYS-D-26 | semantic values · tests 12 ข้อ · evidence-open · เงื่อนไข import 7 ข้อ | **RES-D-33 ข้อ 4–6 · RES-D-41** | active · **blocking การ import** |
| SYS-D-27 | สถานะ reproducibility และสถานะภาพรวม | **RES-D-43 · RES-D-44** | active |
| SYS-D-28 | รับรอง `397f293` คงบน main | **RES-D-37** | active |
| SYS-D-29 | `reviewpack-1.2.0` (display/review revision) | — | active · **บันทึกครั้งแรกเป็น SYS-D-22 ใน `49e50a0` แก้เป็น SYS-D-29 ที่ `c66cb02` แบบ forward-only** |

**เลขว่างถัดไป: `SYS-D-30`** (ไม่ใช่ 22 — ดูแถวที่จองไว้)

> ⚠️ **บทเรียนจากการชนเลขรอบ 28 ส.ค.:** `SYS-D-22` ถูกใช้ซ้ำโดยไม่ตั้งใจเพราะผู้เขียนไม่ทราบว่าเลขถูกจองไว้
> ในทะเบียนกลางของ **อีก repo หนึ่ง** · แก้แล้วแบบ forward-only ไม่ amend ·
> **ก่อนใช้เลข `SYS-D-*` ใหม่ ให้ตรวจตารางนี้และทะเบียนกลางเสมอ**

---

## ส่วนเพิ่มที่ 3 — ปรับผังเลขตาม `SYS-D-30` / `RES-D-49` (28 ส.ค. 2569 ช่วงบ่าย)

> **เพิ่มอย่างเดียว ไม่แก้ตารางเดิม** · **ตารางนี้แทนบรรทัด "เลขว่างถัดไป: `SYS-D-30`" ด้านบน**

| เลข | เรื่อง | mirror ของสายเล่ม | สถานะ |
|---|---|---|---|
| **SYS-D-22 · SYS-D-23 · SYS-D-24** | ร่างของสาย incident (คู่ `RES-D-34`–`RES-D-36`) | — | 🔒 **`SUPERSEDED` · จองถาวร ห้ามใช้กับเรื่องใดอีก** (RES-D-49 ③–④) |
| **SYS-D-30** | mirror คำตัดสิน Research Decision Gate — ค่าผูกพัน `2,987 รหัสหน่วยงาน`/`0.19%` · สถานะร่างที่ถูกแทน · instrument baseline `v1.3.1` | **RES-D-49** | active · **กระทบถ้อยคำในเล่ม** |
| ร่าง **SYS-D-31** | residual ของร่าง `SYS-D-23` — รายการที่การรันเดิมไม่มี + กฎ `RECONSTRUCTED AFTER EXECUTION` | ร่าง **RES-D-50** | 🔖 **จองเลข · รอกิ๊ฟอนุมัติ** |

### **เลขว่างถัดไป: `SYS-D-32`**

(ไม่ใช่ 22/23/24 = จองถาวร · ไม่ใช่ 30 = ใช้แล้ว · ไม่ใช่ 31 = จองรออนุมัติ)

**ก่อนใช้เลขใหม่ ให้ตรวจทะเบียนกลาง** `redbook-verify-is/00_project_control/CROSS_REPO_DECISION_REGISTER.md`
**ภาคผนวก ค.3** เสมอ — ผังนี้เป็นสำเนาฝั่งระบบ ทะเบียนกลางเป็นฉบับผูกพัน

### ปรับผังเลข — `SYS-D-31` อนุมัติแล้ว (28 ส.ค. 2569)

`SYS-D-31` เปลี่ยนจาก **จองรออนุมัติ** เป็น ✅ **`APPROVED / ACTIVE`** (mirror ของ `RES-D-50`) ·
provenance/evidence-governance decision · **ใช้เลขที่จองไว้ ไม่ออกเลขใหม่**

**เลขว่างจริงถัดไปคงเดิม: `SYS-D-32`** · ไม่มีเลขในสถานะ "จองรออนุมัติ" เหลืออยู่แล้ว

### ปรับผังเลข — `SYS-D-32` ใช้แล้ว (1 ก.ย. 2569)

`SYS-D-32` = mirror ของ `RES-D-53` (ผล audit labeling defect = ระดับ B · `KNOWN INSTRUMENT DEFECTS`)

**เลขว่างถัดไป: `SYS-D-33`**
