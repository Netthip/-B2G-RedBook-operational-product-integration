# CURRENT_STATE — สถานะที่พิสูจน์แล้ว

**ตัดยอด ณ:** 2 กันยายน 2569 · **ผู้ตรวจ:** Giho · **วิธีตรวจ:** เปิดไฟล์จริงในทั้งสอง repo + นับ test จริง
**ประเภทเอกสาร:** `COORDINATION LAYER ONLY — NOT AN AUTHORITY`
**สถานะ:** `DRAFT — PENDING GIFT REVIEW`

> เอกสารนี้บันทึกเฉพาะสิ่งที่**เปิดไฟล์ตรวจแล้ว** ทุกบรรทัดมี pointer
> สิ่งที่ยังไม่ตรวจจะเขียนว่า **ยังไม่ตรวจ** ไม่เขียนว่า "น่าจะ" หรือ "คาดว่า"

---

## 0. แผนที่ authority — ที่อยู่ของความจริง

| ชั้น | ที่อยู่ | หมายเหตุ |
|---|---|---|
| **Research SSOT** | repo `redbook-verify-is` | remote **PRIVATE** `github.com/Netthip/redbook-verify-is` |
| **System SSOT** | repo `redbook-verify` | remote **PRIVATE** `github.com/Netthip/redbook-verify` |
| **ข้อมูลและผลการรัน** | `redbook-verify-data` | อยู่นอก Git ตาม `SYS-D-05` |
| **ชั้นประสานงาน** | repo นี้ (`09_RESEARCH_BRIDGE/`) | ไม่มีอำนาจ |

**จุดอ้างอิง ณ เวลา freeze** (จาก `EVIDENCE_INDEX.md`)

| repo | commit |
|---|---|
| `redbook-verify` | `938d01f59207f5c868a13aea759f7375676af719` |
| `redbook-verify-is` | `9ca028d464d471ec6908e65320023e07304e27c5` |

> **`Q-03` คลี่คลายแล้ว** (คำสั่ง Gift · 1 ก.ย. 2569) — ทั้งสอง repo มี remote **PRIVATE** แล้ว
> โดย **preserve full git history** ไม่ squash และไม่ rewrite
>
> 🔴 **ข้อจำกัดที่ยังอยู่:** สำเนาสำรองมีเฉพาะสิ่งที่ push แล้ว · ข้อมูลและผลการรันใน
> `redbook-verify-data` **ยังอยู่นอก Git ตาม `SYS-D-05`** ⇒ ไม่มีสำเนาสำรองที่ใดเลย

---

## 1. RESEARCH TRACK — สถานะตามชั้น

ป้ายสถานะทั้งหมดต่อไปนี้เป็น**ถ้อยคำที่บังคับ ห้ามย่อ ห้ามแปลง**

| ชั้น | ป้ายสถานะ | ฐานอำนาจ |
|---|---|---|
| ดัชนีหลักฐาน | `EVIDENCE INDEX FROZEN — PRIMARY CASE REVIEW COMPLETE` | `EVIDENCE_INDEX.md` commit `617ceac` (1 ก.ย. 2569) |
| reproducibility ของการรัน | `FORMAL REPRODUCIBILITY VERIFIED UNDER EXACT PARAMETERS — SIX-LAYER RUN EVIDENCE COMPLETE` | `RES-D-43` · `SYS-D-27` |
| บทที่ 4 | `PRIMARY CASE REVIEW COMPLETE — CHAPTER 4 WRITING UNBLOCKED` | `RES-D-52` |
| ข้อบกพร่องเครื่องมือ Human Review | `LIMITED MEASUREMENT RISK — DISCLOSURE REQUIRED` | `RES-D-53` · คู่ `SYS-D-32` |
| การรันเดิมทั้งหมด | `LEGACY EVALUATION OUTPUT — ORIGINAL EXECUTION METADATA INCOMPLETE` | ERRATA `E-06` |
| `FRR-T1-20260828-040044` | `CONTROLLED PARAMETER-DIFFERENCE RUN` (ไม่ใช่ failed run · ห้ามลบ) | `RES-D-44` |

> 🔴 **ไม่มีชั้นใดแปลว่า `Phase 2C completed`** — ห้ามเขียนคำนี้ (ฐานอำนาจ `RES-D-43`)

### 1.1 เวอร์ชันที่ตรึงแล้ว

| รายการ | ค่า |
|---|---|
| git tag | `t1-frozen-1.0.0` |
| commit ของ tag | `49fbb2e0c1d67dd0edfda8b5e7b419a19e235150` |
| engine · rules · schema | `t1-engine-1.0.0` · `rules-t1-1.0.0` · `cdm-t1-1.0.0` |
| semantic mapping · composite key | `semmap-t1-1.0.0` · `key-t1-1.0.0` |
| protocol ตรวจหลักฐาน | `protocol-1.0.2` |

**การอ้างผลต้องระบุ `49fbb2e` + `protocol-1.0.2` เสมอ — ห้ามอ้าง HEAD**

### 1.2 Human Review — เสร็จครบสองรอบแล้ว

| รอบ | จำนวนที่กรอก | SHA-256 หลังกรอก | เวลาบันทึกเสร็จ |
|---|---|---|---|
| รอบที่ 1 | **21/21 รายการ** | `8134b730db13364d…` | 28 ส.ค. 2569 12:08:49 |
| รอบที่ 2 | **21/21 รายการ** | `fd4f956abc789b40…` | 1 ก.ย. 2569 06:10:59 |

- เครื่องมือ: `v1.3.1 = FROZEN INSTRUMENT BASELINE FOR ROUND 1 DATA COLLECTION` (ถ้อยคำห้ามย่อ)
- seed ต่างกันจริง: รอบ 1 = `20260827` · รอบ 2 = `20260901`
- ค่าที่รายงานได้: **`intra-rater agreement = 21/21 รายการ (100%)`** · รายการที่ต้อง adjudicate = **0**

> 🔴 **ห้ามรายงานค่านี้โดยไม่มีข้อความบังคับสองย่อหน้าของ `CLAIM_BOUNDARY.md` หัวข้อ 9.1 กำกับ**
> และห้ามเรียกว่า inter-rater reliability · ห้ามรายงาน kappa · ห้ามใช้อ้างว่าไม่มี bias
> · ห้ามใช้ตัวเลขจากหน้า `Summary` ของ workbook (สูตรอ้างคอลัมน์ผิด ⇒ `NOT AUTHORITATIVE`)

### 1.3 การทดสอบถดถอย — ตรวจซ้ำวันนี้

| แหล่ง | ค่า |
|---|---|
| `EVIDENCE_INDEX.md` (`E5`) บันทึกไว้ | regression gate **PASS 179 · FAIL 0 · SKIP 0** (commit `cfe791c` → `f3896a2`) |
| Giho นับซ้ำ 1 ก.ย. 2569 | `pytest --collect-only` = **179 tests collected** ✅ ตรงกัน |

---

## 2. ชั้นข้อมูล — จุดที่สำคัญที่สุดต่อสายผลิตภัณฑ์

| ชั้น | dataset kind | adapter | สถานะการทดลอง |
|---|---|---|---|
| **T1A** | `OFFICIAL_FLAT_DATA_TABLE` | `FlatDataTableAdapter` | ✅ **ผลที่ freeze ทั้งหมดอยู่ที่ชั้นนี้** |
| **T1B** | `OFFICIAL_AO_WORKBOOK` | `AOWorkbookAdapter` | ⏳ `T1B-E1` **ยังไม่ได้รัน** — รอ structural mapping (`RES-Q-02`) |
| **T1B** | `OFFICIAL_MINISTRY_PDF` | `MinistryPdfAdapter` | ⏳ `PDF-E1`..`PDF-E3` = Phase 3 ยังไม่เริ่ม |
| **T2** | `UNCONFIRMED_LOCAL_WORKBOOK` | `AOWorkbookAdapter` | ❌ `PROVENANCE UNCONFIRMED — DEVELOPMENT ONLY` |

**ข้อบังคับที่ผูกพันทั้งสองสาย**

- `T1A` และ `T1B` **ห้ามใช้ mapping หรือตัวหารร่วมกัน** (`RES-D-24`)
- **ห้ามรวมตัวหารหรือคะแนนข้ามชั้น** `T1A` / `T1B` / PDF / controlled (`RES-Q-01`)
- ไฟล์ T1B มีทะเบียน provenance ครบแล้ว: Excel 6 ไฟล์ (`T1B-X01`..`T1B-X06`) + PDF 4 ฉบับ (`T1B-P01`..`T1B-P04`)
- หน่วยเงินของ T1B = **ล้านบาท ทศนิยม 4 ตำแหน่ง** ตามที่ประกาศในคอลัมน์หน่วยนับ

> 🔴 **ผลที่มีอยู่ทั้งหมด — `M-SET` · `C-SET` · `Y-2` · supplementary · Human Review 21 รายการ — วัดบนชั้น `T1A`**
> `M-SET` นิยามไว้ว่าเป็น *สำเนาของ `T1-01`* และ `C-SET` = `T1-01` ↔ `T1-02`
> (`redbook-verify` → `docs/EXPERIMENT_PROTOCOL.md` หัวข้อ `M-SET` / `C-SET`)
> **ไม่มีผลใดวัดบนชั้น `T1B` ซึ่งเป็นชั้นของเอกสารคาดแดงจริง**

---

## 3. ผลที่มีจริง และข้อกำกับที่ติดมากับผลนั้น

| ชุด | สิ่งที่พูดได้ | สิ่งที่ห้ามพูด |
|---|---|---|
| **M-SET** | แหล่งเดียวของ Precision/Recall/F1 · primary **108** + linked impacts **12** | **ห้ามเขียน `120/120 mutations`** · ห้ามเขียน "แม่นยำ 100%" · ห้ามเขียน "ตรวจข้อผิดพลาดได้ทุกประเภท" (ทดสอบเฉพาะ `MUT-01`–`MUT-09`) |
| **C-SET** | การพรรณนากรณีศึกษาสองหน่วยงาน | **ไม่ใช่การประเมินความถูกต้อง** |
| **Y-2** | `cross-year schema compatibility and safe-failure demonstration` | ห้ามใช้คำนวณ P/R/F1 · ห้ามบอกว่า "ไม่พบความแตกต่าง" |
| **Supplementary** | `SUPPLEMENTARY — NOT PART OF PRIMARY TWO-AGENCY RESULT` | **ห้ามเรียก blind evaluation** (รวมหน่วยงานที่ใช้พัฒนากฎ) · ห้ามรวมคะแนนกับกรณีศึกษาสองหน่วยงาน |
| **evidence location** | ต้องรายงาน **สองชั้นเสมอ**: `protocol-1.0.1` = 180/192 → `protocol-1.0.2` = exact 180 + text-equivalent 12 + unresolved 0 | ห้ามเขียน "evidence location ถูกต้อง 100%" ลอย ๆ |
| **reproducibility** | ต้องอ้างหลักฐาน **6 ชั้น** | ห้ามอ้างจาก `result_hash` ตัวเดียว (= **Semantic Result Hash** เท่านั้น) · **ห้ามเขียน "ทุก field เหมือนกันทั้งหมด"** |
| **ขอบเขตข้อมูล** | `2,987 รหัสหน่วยงาน` / `0.19%` | ห้ามเขียน "2,987 หน่วยงาน" · ค่า `676` = `SUPERSEDED` |

**หลักฐานเชิงประจักษ์ที่ต้องรายงานคู่กันเสมอ:** ในคู่ legacy ↔ FRR — Semantic Result Hash **ตรงกัน**
แต่ Evidence Manifest Hash **ต่างกัน** ⇒ พิสูจน์ว่า hash ตัวเดียวไม่พอ (`RES-D-39`)

---

## 4. PRODUCT TRACK — ของที่มีอยู่จริงในโค้ดวันนี้

ตรวจจาก repo `redbook-verify` (1 ก.ย. 2569)

| ส่วน | ที่อยู่ | สถานะที่ยืนยันได้ |
|---|---|---|
| T1 engine | `redbook/t1/` — `loader` `normalize` `canonical` `matching` `compare` `semantic_map` `datadict` `protocol` | frozen ที่ `t1-frozen-1.0.0` |
| adapters | `redbook/adapters/` — `flat_data_table` `ao_workbook` `ministry_pdf` `base` | มีโครงครบสามชนิด · **มีเพียง `flat_data_table` ที่มีผลการทดลองรองรับ** |
| web UI | `redbook/web/` · `redbook/templates/` · `redbook/static/` | มีอยู่จริง · **ยังไม่ตรวจ**ในรอบนี้ว่าครอบคลุมแค่ไหน |
| review package | `reviewpack/` | ใช้สร้าง workbook ให้มนุษย์ตรวจ · schema ที่ acceptance test ชี้ = `v1.3.1` |
| storage · report · rules | `redbook/storage/` `redbook/report/` `redbook/rules/` | มีอยู่จริง · **ยังไม่ตรวจ**รายละเอียดในรอบนี้ |
| ชุดทดสอบ | `tests/` | **358 tests** (สาย T1B เพิ่ม 179 ข้อจากฐาน 179) |
| **สายงานผลิตภัณฑ์ T1B** | `redbook/t1b/` — `normalize` `roles` `header` `units` `hierarchy` `keys` `records` `categories` `matching` `compare` | 🔒 คีย์ `t1b-key-0.1.0` · matching `0.5.0` · compare `0.4.0` · rollup `0.1.0` · อนุญาตโดย `RES-D-54`/`SYS-D-33` |
| **gate ของสาย T1B** | `BRIDGE-001` · `AI_HANDOFF_LOG.md` `HL-013` | 🟢 `ROLL-UP / RECONCILIATION — UNBLOCKED` (`BO FINAL PASS` · 2 ก.ย. 2569 · ผูกกับ `50a97de`) |

---

## 5. สิ่งที่ยัง BLOCKED — การ freeze ไม่ได้ปลดข้อใดเลย

| รายการ | เหตุผล | ฐานอำนาจ |
|---|---|---|
| **import คำตอบเข้าฐานข้อมูล / Audit Trail** | ยังไม่ครบ **7 เงื่อนไข** | `RES-D-41` · `SYS-D-26` |
| **Phase 3 (PDF Comparator)** | ตามลำดับงาน | `RES-D-32` |
| **การประเมินความปลอดภัย (ZAP)** | ทำหลัง Phase 3 | — |
| **`INC-2569-08-27-01`** | 🔴 **ยังเปิดอยู่ ไม่มีคำตัดสินใดสั่งปิด** | `EVIDENCE_INDEX.md` |
| **candidate validation rules** | **ห้าม implement** | `RES-D-51` |
| **`e9360ad`** | `INTENTIONALLY NOT LANDED` — ห้ามนำเข้า main | `LANDING_BOUNDARY_REGISTER.md` |

**สิ่งที่ Evidence Index ที่ freeze แล้ว *ไม่* ครอบคลุม:** หลักฐานฝั่ง PDF (Phase 3) · ผลด้านความปลอดภัย (ZAP)
· Pilot Extension · ชุด supplementary ที่ยังไม่ตรวจโดยมนุษย์

---

## 6. เลขทะเบียนที่ว่างถัดไป

| namespace | เลขว่างถัดไป |
|---|---|
| สายเล่ม | **`RES-D-55`** |
| สายระบบ | **`SYS-D-34`** |

เลขที่ถูกจอง/ยกเลิกถาวรแล้ว **ห้ามนำกลับมาใช้ซ้ำ**: `RES-D-34`–`RES-D-36` · `SYS-D-22`–`SYS-D-24` = `SUPERSEDED`

`RES-D-54` / `SYS-D-33` **ถูกใช้แล้ว** โดยคำตัดสินอนุญาตสายงานผลิตภัณฑ์ T1B (1 ก.ย. 2569)

---

## 7. สิ่งที่ห้ามแตะในรอบนี้ (คำสั่ง Gift 1 ก.ย. 2569)

frozen Evidence Index · Human Review workbooks · raw results · Chapter 4 · production engine

**รอบนี้ไม่มีไฟล์ใดในรายการข้างต้นถูกแก้ไข** — ดู `AI_HANDOFF_LOG.md` รายการ `HL-001`
