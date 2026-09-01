# T1B DATASET REGISTER — ชุดข้อมูลสาธารณะสำหรับงาน FY2570 Operational MVP

**เผยแพร่ตามคำสั่ง:** `GIFT_MASTER_DIRECTIVE_T1B.md` ข้อ 10 (Gift · 1 กันยายน 2569)
**บันทึกโดย:** Giho · **ป้ายกำกับ:** `PRODUCT EVIDENCE — POST-FREEZE`

> Gift ยืนยันว่า *"ชุดข้อมูล `T1B` ที่ใช้ในงานวิจัย/การพัฒนารอบนี้สามารถเผยแพร่เป็นสาธารณะได้"*
> วางไว้ที่นี่เพื่อให้ **Bo และ Giho อ่านชุดเดียวกัน** สำหรับ structural mapping · test fixture
> · adapter validation · reproducible product evidence

---

## 1. ทะเบียน — ครบ 7 ฟิลด์ตามคำสั่ง

| # | filename | SHA-256 | fiscal year | document level | dataset kind | ขนาด (B) | ชีต |
|---|---|---|---:|---|---|---:|---:|
| `T1B-X03` | `ao_workbook/XL_FY2569_draft-bill_21000_MOPH-summary.xlsx` | `86389b113614c09f2a40d2d3ae34204dd563ca9b2b529b1e28e53086ee068c5f` | 2569 | **ministry** | `OFFICIAL_AO_WORKBOOK` | 49,319 | 6 |
| `T1B-X01` | `ao_workbook/XL_FY2569_draft-bill_21011_HSRI.xlsx` | `e98cda10e21eafde848f421bc127b0db5d35912a273377c3b9ad9592ad535e88` | 2569 | **agency** | `OFFICIAL_AO_WORKBOOK` | 154,574 | 11 |
| `T1B-X02` | `ao_workbook/XL_FY2569_draft-bill_21016_NVI.xlsx` | `4ac0823d6dd1d0bf8648f026c59eb555347bfb321205c9453c1c4e4396fee251` | 2569 | **agency** | `OFFICIAL_AO_WORKBOOK` | 266,325 | 17 |
| `T1B-X06` | `ao_workbook/XL_FY2570_draft-bill_21000_MOPH-summary.xlsx` | `8c7440705362fbfcb02ed07b8f88a95f9ad7f598471fee78050ad368a46da7e7` | 2570 | **ministry** | `OFFICIAL_AO_WORKBOOK` | 53,139 | 6 |
| `T1B-X04` | `ao_workbook/XL_FY2570_draft-bill_21011_HSRI.xlsx` | `23d6c96e2afacc8cb765c30dba0b6b27a91f59791c199a878190ae228d67758a` | 2570 | **agency** | `OFFICIAL_AO_WORKBOOK` | 50,766 | 11 |
| `T1B-X05` | `ao_workbook/XL_FY2570_draft-bill_21016_NVI.xlsx` | `23d5714b0af800ccfdc98ad216eaf8c940bd7cfa97ef8b046abbb9153b9f24ae` | 2570 | **agency** | `OFFICIAL_AO_WORKBOOK` | 82,384 | 19 |

**source / provenance pointer** (ใช้ร่วมกันทั้ง 6 รายการ)

| ฟิลด์ | ค่า |
|---|---|
| `publisher` | สำนักงบประมาณ |
| `official_landing_page` | `bb.go.th` |
| `storage_provider` | Google Drive |
| `source_status` | `official-linked public source` |
| `provenance_pointer` | `redbook-verify-is` → `03_dataset_register/RESEARCH_DATASET_REGISTER.md` กลุ่ม 1 (`X-01`..`X-06`) · หลักฐาน `M-2569-08-27-09` |
| `document_status` | `draft_bill` (ร่าง พ.ร.บ.) ทั้ง 6 รายการ |
| `หน่วยงาน` | `21000` = สรุปกระทรวง · `21011` = สวรส. · `21016` = สวช. |

**ยืนยันความถูกต้องของสำเนา:** เทียบ SHA-256 ของไฟล์ในโฟลเดอร์นี้กับต้นทาง
`redbook-verify-data/sources/public/ao_workbook/` แล้ว **ตรงกันทั้ง 6 ไฟล์**

---

## 2. สิ่งที่ **ไม่ได้** เผยแพร่ในรอบนี้ และเหตุผล

| ชุด | เหตุผล |
|---|---|
| `T1B-P01`..`T1B-P04` (PDF เล่มกระทรวง 4 ฉบับ · รวม ~24 MB) | **Phase 3 ยัง blocked** (`RES-D-32`) · ยังไม่ใช้ในงานรอบนี้ · ลงทะเบียนไว้แล้วใน research register |
| ชั้น `T2` (ไฟล์ของผู้วิจัย 22 รายการ) | 🔴 `PROVENANCE UNCONFIRMED — DEVELOPMENT ONLY` · **ห้าม commit** (`RES-D-15` · `RES-D-29`) |
| ชั้น `T1A` (ตารางข้อมูลแบน 3 ไฟล์) | เป็นชั้นของงานวิจัยที่ freeze แล้ว · ไม่ใช่ขอบเขตของ product track |
| ผลการรัน / raw results | อยู่นอก Git ตาม `SYS-D-05` |

---

## 3. ข้อบังคับเมื่อใช้ชุดข้อมูลนี้

| # | ข้อบังคับ | ฐานอำนาจ |
|---|---|---|
| 1 | **ห้ามใช้ mapping หรือตัวหารร่วมกับ `T1A`** | `RES-D-24` |
| 2 | **ห้ามรวมตัวหารหรือคะแนนข้ามชั้น** `T1A` / `T1B` / PDF / controlled | `RES-Q-01` |
| 3 | **ห้ามจับคู่ข้ามระดับเอกสาร** (`ministry` ↔ `agency`) | `GIFT_MASTER_DIRECTIVE_T1B.md` ข้อ 9 |
| 4 | ผลที่ได้จากชุดนี้ = **`PRODUCT EVIDENCE — POST-FREEZE`** ห้ามอ้างเป็นผลของ frozen `T1A` | `GIFT_MASTER_DIRECTIVE_T1B.md` ข้อ 0 |
| 5 | ไฟล์ทั้ง 6 เป็น **value-only** (`formulas = 0`) — การทดสอบ formula residue ต้องใช้ `SYNTHETIC TEST FIXTURE` | `GIFT_MASTER_DIRECTIVE_T1B.md` ข้อ 8 |

---

## 4. หมายเหตุการอ่านไฟล์

ผลสำรวจโครงสร้างของทั้ง 6 ไฟล์อยู่ที่ `09_RESEARCH_BRIDGE/T1B_STRUCTURAL_MAP.md`

**เตือนก่อนเขียนโค้ดอ่านไฟล์เหล่านี้:** ชื่อชีตและ index ของชีต **ใช้เป็นคีย์ไม่ได้**
· คอลัมน์ปีเลื่อนหนึ่งปีระหว่างไฟล์ FY2569 กับ FY2570
· หน่วยเงินอยู่ระดับแถว · ค่าที่เก็บมีเศษ floating-point เกินทศนิยมที่ประกาศ
