# CROSS_REPO_DECISION_REGISTER — POINTER (read-only)

> ⚠️ **ไฟล์นี้เป็น pointer เท่านั้น ไม่ใช่ทะเบียนกลาง**
> **ห้ามสร้างทะเบียนกลางฉบับที่สองใน repo นี้** และห้ามแก้เนื้อหาทะเบียนจากที่นี่

## ทะเบียนกลางตัวจริงอยู่ที่

| ฟิลด์ | ค่า |
|---|---|
| repo | `redbook-verify-is` (Research Protocol SSOT) |
| ไฟล์ | `00_project_control/CROSS_REPO_DECISION_REGISTER.md` |
| commit hash ที่อ้างอิง | `a09a44be3c3cd1b45e83d6ace9eddf57101ab39c` |
| วันที่บันทึก pointer | 28 ส.ค. 2569 — ทะเบียนกลางเพิ่ม **ภาคผนวก ข**: RES-D-33..48 · SYS-D-25..28 · ตารางเลขที่จองไว้ (SYS-D-22..24) · หมายเหตุ C-5/C-6 |
| ปรับปรุงก่อนหน้า | 27 ส.ค. 2569 `415c54f` (ภาคผนวก ก: RES-D-27..32 · SYS-D-15..20 · SYS-F-02/03) |

## วิธีใช้

1. อ่านทะเบียนกลางจาก repo เล่มที่ commit ข้างต้น
2. หากทะเบียนกลางถูกแก้ ให้อัปเดต commit hash ในไฟล์นี้ **อย่างเดียว** — ห้ามคัดลอกเนื้อหามาไว้ที่นี่
3. การอ้างอิงคำตัดสินข้าม repo ให้ใช้ canonical ID (`SYS-*` / `RES-*`) ตาม `DECISION_NAMESPACE_MIGRATION.md`

## หลัก Single Source of Truth ที่เกี่ยวกับ repo นี้

| หัวข้อ | SSOT |
|---|---|
| System implementation · schema ในโค้ด · parser · rule engine · API/UI · security controls | **repo นี้** |
| Research protocol · metrics · gold standard · mutation protocol · ขอบเขตการวิจัย | repo เล่ม |
| ไฟล์ข้อมูลวิจัย | data directory นอก Git (ดู `RES: CANONICAL_DATA_DIRECTORY.md`) |
| Runtime result และหลักฐานเครื่อง | data directory นอก Git |
| Result manifest และ hash ที่ใช้อ้างในเล่ม (หลัง freeze) | repo เล่ม |

## คำตัดสินของ repo เล่มที่บังคับใช้กับงานใน repo นี้โดยตรง

| canonical ID | สาระ | ผลต่อ repo นี้ |
|---|---|---|
| **RES-D-24** | แยกชั้นข้อมูลเป็น T1A / T1B / T2 | `T1` ของ repo นี้ = `T1A` เท่านั้น |
| **RES-D-25** | T1A-E2 = schema safe-failure demonstration | ต้อง implement พฤติกรรม 10 ขั้น + acceptance criteria AC-1..AC-6 |
| **RES-Q-01** | ตัวหารแยกตามชั้นข้อมูล | ห้ามรวมคะแนนข้าม T1A / T1B / PDF / controlled |
| **RES-Q-10** | นิยาม atomic finding + schema-level finding | ใช้เป็นข้อกำหนดของ finding model และ deduplication key |
| **RES-D-22** | dev/eval mutation split | evaluation set ต้อง freeze ก่อนรัน engine |
| **RES-D-23** | สถานะ discovery evidence | ตัวเลขที่ค้นพบก่อน freeze ห้ามเข้าบทที่ 4 |

---

## ปรับปรุง pointer — 28 ส.ค. 2569 ช่วงบ่าย (`RES-D-49` / `SYS-D-30`)

**ทะเบียนกลางเพิ่ม ภาคผนวก ค:** ปรับสถานะเลขจอง `RES-D-34/35/36` (+ `SYS-D-22/23/24`) เป็น
**`SUPERSEDED`** · ลงทะเบียน `RES-D-49` / `SYS-D-30` และร่าง `RES-D-50` / `SYS-D-31` ·
ผังเลขว่างถัดไป **`RES-D-51`** / **`SYS-D-32`** · แก้หมายเหตุ **C-6** ที่ล้าสมัย
(RES-D-47 ②–⑥ **ทำครบแล้ว**) · เพิ่ม **C-7** ค่าผูกพัน · **C-8** การตรวจย้อนกลับของ errata E-SET

### คำตัดสินของ repo เล่มที่บังคับใช้กับงานใน repo นี้โดยตรง (เพิ่ม)

| canonical ID | สาระ | ผลต่อ repo นี้ |
|---|---|---|
| **RES-D-49 ②** | ค่าผูกพัน **`2,987 รหัสหน่วยงาน`** · **`0.19%`** | 🔴 ห้ามเขียน `676 หน่วยงาน` · `0.46%` · **และห้ามเขียน "2,987 หน่วยงาน"** (คนละหน่วยนับ) ในเอกสาร UI หรือ docs ใดของ repo นี้ |
| **RES-D-49 ⑤** | `v1.3.1 = FROZEN INSTRUMENT BASELINE FOR ROUND 1 DATA COLLECTION` | 🔴 ห้ามระบุว่า `v1.3.0` ยังเป็น baseline หรือ Review Workbook ยังรอ freeze · **ถ้อยคำต้องมีคำว่า `INSTRUMENT`** |
| **RES-D-49 ③–④** | ร่าง `RES-D-34/35/36` + `SYS-D-22/23/24` = `SUPERSEDED` | เลขจองถาวร · ห้ามใช้กับเรื่องใดอีก · ดู `DECISION_NAMESPACE_MIGRATION.md` ส่วนเพิ่มที่ 3 |

### ทะเบียนใหม่ที่ต้องเปิดก่อนลงมือ

| ไฟล์ (repo เล่ม) | เปิดเมื่อ |
|---|---|
| `00_project_control/LANDING_BOUNDARY_REGISTER.md` | **ก่อน merge หรือ cherry-pick อะไรเข้า main** — มีรายการ commit ที่ตัดสินแล้วว่า **ห้ามนำเข้า** (`e9360ad`) |
| `00_project_control/CLAIM_BOUNDARY.md` **หัวข้อ 6** | ก่อนเขียนข้อกล่าวอ้างใดที่จะเข้าเล่มหรือขึ้นหน้าจอ |
