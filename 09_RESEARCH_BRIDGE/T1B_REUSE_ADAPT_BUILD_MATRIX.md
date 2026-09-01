# T1B REUSE / ADAPT / BUILD-NEW MATRIX

**จัดทำ:** 1 กันยายน 2569 · **ผู้ตรวจ:** Giho · **ตอบ:** `BRIDGE-001` — First engineering task
**ฐานข้อเท็จจริง:** อ่านโค้ดจริงใน repo `redbook-verify` + ผลสำรวจใน `T1B_STRUCTURAL_MAP.md`
**ประเภทเอกสาร:** `COORDINATION LAYER ONLY — NOT AN AUTHORITY` · `PRODUCT EVIDENCE — POST-FREEZE`

> ทุกช่องอ้าง path จริง · จำนวนบรรทัดจาก `wc -l` · **ยังไม่มีการแก้โค้ดใด ๆ ในรอบนี้**

---

## 0. นิยามป้าย

| ป้าย | ความหมาย |
|---|---|
| ♻️ `REUSE` | ใช้ได้ตามเดิม ไม่ต้องแก้ — ไม่ผูกกับชั้นข้อมูล |
| 🔧 `ADAPT` | โครงใช้ได้ แต่ต้องเพิ่มสาขาของ `T1B` โดย**ไม่แตะเส้นทาง `T1A` ที่ freeze แล้ว** |
| 🆕 `BUILD NEW` | ยังไม่มีของ ต้องเขียนใหม่ |
| ⛔ `DO NOT TOUCH` | frozen หรือถูกห้ามด้วยคำตัดสิน |

---

## 1. Matrix

### 1.1 ชั้น adapter และชนิดข้อมูล

| ส่วน | path | บรรทัด | ป้าย | เหตุผล |
|---|---|---:|---|---|
| สัญญา adapter · `CanonicalEnvelope` · `SourceLocation` · `validate_envelope` | `redbook/adapters/base.py` | 138 | ♻️ `REUSE` | บังคับ `EXCEL_CELL`/`EXCEL_ROW` ให้ `OFFICIAL_AO_WORKBOOK` อยู่แล้ว · กันการปลอมตำแหน่งข้ามชนิดให้ฟรี |
| ทะเบียนชนิดข้อมูล + crosswalk | `redbook/datasets/kinds.py` | ~110 | ♻️ `REUSE` | `OFFICIAL_AO_WORKBOOK` → `T1B` → `AOWorkbookAdapter` ผูกไว้ครบแล้ว |
| **`AOWorkbookAdapter`** | `redbook/adapters/ao_workbook.py` | **40** | 🆕 **`BUILD NEW`** | 🔴 **`inspect()` และ `extract()` `raise NotImplementedError` ทั้งคู่** — เป็น skeleton ล้วน · `supporting_sheet_prefixes` ยังมี defect (ข้อ 7 ของ structural map) |
| `FlatDataTableAdapter` | `redbook/adapters/flat_data_table.py` | 34 | ⛔ `DO NOT TOUCH` | เส้นทาง `T1A` ที่ freeze — ห้ามแก้ ห้ามยืม mapping |
| `MinistryPdfAdapter` | `redbook/adapters/ministry_pdf.py` | 31 | ⛔ `DO NOT TOUCH` | Phase 3 (`RES-D-32`) ยังไม่เริ่ม |

### 1.2 เครื่องยนต์เปรียบเทียบ

| ส่วน | path | บรรทัด | ป้าย | เหตุผล |
|---|---|---:|---|---|
| Canonical schema `T1` | `redbook/t1/canonical.py` | 123 | ⛔ `DO NOT TOUCH` | `cdm-t1-1.0.0` frozen · `T1B` ต้องมี canonical ของตัวเอง |
| อ่านชีต `data` → record | `redbook/t1/loader.py` | 109 | ⛔ `DO NOT TOUCH` | ผูกกับชีต `data` ของ flat table โดยเฉพาะ |
| `Data Dict` + schema fingerprint | `redbook/t1/datadict.py` | 139 | ⛔ `DO NOT TOUCH` | `T1B` ไม่มี `Data Dict` — ต้องใช้ `A1` role anchor แทน |
| Semantic mapping | `redbook/t1/semantic_map.py` | 179 | ⛔ `DO NOT TOUCH` | `semmap-t1-1.0.0` frozen |
| **การปรับรูปข้อความ** | `redbook/t1/normalize.py` | **74** | ♻️ `REUSE` | การ normalize ข้อความไทยไม่ผูกชั้นข้อมูล — ใช้กับ `row_label` ของ `T1B` ได้ตรง ๆ |
| **pipeline จับคู่ 5 ขั้น + คีย์ 9 บทบาท** | `redbook/t1/matching.py` | **248** | 🔧 `ADAPT` | **แนวคิดใช้ซ้ำได้ · ตัวคีย์ใช้ไม่ได้** — `T1B` ต้องคีย์ตามข้อ 9 ของ structural map · ห้ามแก้เส้นทางเดิม ให้เพิ่มสาขาใหม่ |
| **หมวดผลตรวจ `C1`–`C7`** | `redbook/t1/compare.py` | **206** | 🔧 `ADAPT` | หมวด 7 ชนิด (ลด/เพิ่ม/ไม่เปลี่ยน/เพิ่มแถว/ลบแถว/ย้าย parent/ambiguous) ตรงกับที่ Mode B ต้องการอยู่แล้ว · ต้องเพิ่มมิติ **ปี** และ **หน่วย** เข้าไป |
| ตัวรัน protocol `G5` | `redbook/t1/protocol.py` | 344 | 🔧 `ADAPT` | โครง gate `G1`–`G5` ใช้ซ้ำได้กับ `T1B-E1` แต่ต้องเป็น protocol คนละสาย ห้ามปนเลขรุ่นกับ `protocol-1.0.x` ของ `T1A` |

### 1.3 กฎ ผลตรวจ และหลักฐาน

| ส่วน | path | บรรทัด | ป้าย | เหตุผล |
|---|---|---:|---|---|
| โครง `Finding` | `redbook/rules/finding.py` | 117 | ♻️ `REUSE` | โครงสร้าง finding ไม่ผูกชั้นข้อมูล |
| catalog ของกฎ | `redbook/rules/catalog.py` | 322 | 🔧 `ADAPT` | เพิ่มกฎของ `T1B` เป็นชุดแยก — 🔴 **ห้าม implement กฎใน `RES-D-51`** |
| `mapping_model` | `redbook/rules/mapping_model.py` | 176 | 🔧 `ADAPT` | ใช้เป็นที่เก็บ structural map ของ `T1B` ได้ |
| ตรวจ metadata | `redbook/rules/metadata_checks.py` | 112 | 🔧 `ADAPT` | เพิ่มการตรวจหน่วยที่ประกาศและป้ายปี |
| policy | `redbook/rules/policy.py` | 57 | ♻️ `REUSE` | |
| **แฮชไฟล์ + สายโซ่แฮช** | `redbook/core/hashing.py` | **25** | ♻️ `REUSE` | deterministic source identity — ใช้ได้ทันที |
| **สถานะผลตรวจ (เครื่องบอก vs มนุษย์ตัดสิน)** | `redbook/core/status.py` | **81** | ♻️ `REUSE` | เป็นแกนของ human-in-the-loop ที่ Mode A/B ต้องการพอดี |
| canonical กลาง Excel↔PDF | `redbook/core/canonical.py` | 140 | 🔧 `ADAPT` | |

### 1.4 การเก็บ รายงาน และหน้าจอ

| ส่วน | path | บรรทัด | ป้าย | เหตุผล |
|---|---|---:|---|---|
| repository · db · files | `redbook/storage/` | 620 | ♻️ `REUSE` | |
| **audit trail** | `redbook/storage/audit.py` | **108** | ⛔ `DO NOT TOUCH` **ชั่วคราว** | 🔴 การ import เข้า Audit Trail ยัง **BLOCKED** จนครบ 7 เงื่อนไข (`RES-D-41` · `SYS-D-26`) |
| รายงาน inventory | `redbook/report/inventory_report.py` | 338 | 🔧 `ADAPT` | |
| `mset_reconcile` | `redbook/report/mset_reconcile.py` | 203 | ⛔ `DO NOT TOUCH` | ผูกกับ `M-SET` ที่ freeze |
| เว็บ UI | `redbook/web/` · `templates/` · `static/` | — | 🔧 `ADAPT` | ต้องเพิ่ม `correction target` และคอลัมน์ยอดที่ขึ้นต่อกัน · **ยังไม่ได้ตรวจรายละเอียดในรอบนี้** |
| สร้าง workbook ให้มนุษย์ตรวจ | `reviewpack/` | — | ♻️ `REUSE` แนวคิด · 🔧 `ADAPT` schema | schema ปัจจุบัน `v1.3.1` ผูกกับ finding ของ `T1A` · ⛔ **ห้ามแก้ workbook รอบ 1/2 ที่มีคำตอบแล้ว** |
| ชุดทดสอบ | `tests/` 17 ไฟล์ | **179 tests** | ♻️ `REUSE` + 🆕 เพิ่มชุด `T1B` | มี `test_adapter_isolation.py` · `test_architecture_separation.py` · `test_t1a_and_t1b_are_never_the_same_kind` กันการปนชั้นให้อยู่แล้ว |

---

## 2. สิ่งที่ต้อง `BUILD NEW` ทั้งหมด — เรียงตามลำดับที่เสนอ

| # | สิ่งที่ต้องสร้าง | แก้ silent failure ข้อใด |
|---|---|---|
| 1 | **`sheet_role` resolver** จาก `A1` + การแยก `document_level` (กระทรวง/หน่วยงาน) | ชื่อ/ตำแหน่งชีตไม่คงที่ |
| 2 | **`header_locator`** หาแถวหัวตารางด้วยลายเซ็น ไม่ใช่เลขแถวตายตัว | แถวหัวตารางอยู่คนละแถว (3 กับ 5) |
| 3 | **`year_column_resolver`** จับคู่คอลัมน์ด้วยป้าย `ปี 25xx` | 🔴 **#1 คอลัมน์ปีเลื่อน** |
| 4 | **`unit_resolver`** ระดับแถว (`ล้านบาท` / `บาท` / `ร้อยละ`) | 🔴 **#2 หน่วยปน** |
| 5 | **`decimal_normalizer`** แปลงเป็น `Decimal` + quantize ตามทศนิยมที่ประกาศ | 🔴 **#3 เศษ float** |
| 6 | **`supporting_sheet_classifier`** ด้วยลายเซ็นเนื้อหา แทนตัวอักษรนำ | defect `บุค` (บ ไทย) |
| 7 | `hierarchy_parser` จากเลขนำหน้า + ช่องว่างนำหน้าใน `A` | คีย์ระดับแถว |
| 8 | `t1b_canonical` schema แยกจาก `cdm-t1-1.0.0` | ห้ามปนชั้น |
| 9 | `roll_up_model` รายการ → ผลผลิต → แผนงาน → ยอดหน่วยงาน | requirement ของ Mode B |
| 10 | `correction_target` mapper ชี้กลับไปยัง e-Budget | requirement ของ Mode A/B |

---

## 3. สถาปัตยกรรมที่เสนอ

```
       ไฟล์ T1B (baseline)          ไฟล์ T1B (ฉบับหลังปรับ)
              │                              │
              ├────────  hashing.py  ♻️ ─────┤      deterministic identity
              ▼                              ▼
        AOWorkbookAdapter.inspect()  🆕   (sheet_role · header · unit · year)
              │                              │
              ▼                              ▼
        AOWorkbookAdapter.extract()  🆕 ──► t1b_canonical  🆕
                             │
                             ▼
              normalize.py ♻️  +  matching.py 🔧  (คีย์ T1B)
                             │
                             ▼
                     compare.py 🔧  ──► C1–C7 + มิติปี + มิติหน่วย
                             │
                             ▼
                   roll_up_model 🆕  ──► การกระทบยอดตามลำดับชั้น
                             │
                             ▼
              finding.py ♻️  +  status.py ♻️  +  correction_target 🆕
                             │
                             ▼
                      web UI 🔧   ──►  human decision
                             │
                             ▼
                   evidence package (แยกจาก Evidence Index ของงานวิจัย)
```

---

## 4. สรุปเชิงปริมาณ

| ป้าย | จำนวนรายการ | ความหมาย |
|---|---:|---|
| ♻️ `REUSE` | 9 | ใช้ได้ทันที — โดยเฉพาะ `base.py` · `kinds.py` · `hashing.py` · `status.py` · `normalize.py` · `finding.py` |
| 🔧 `ADAPT` | 10 | ต้องเพิ่มสาขา `T1B` โดยไม่แตะเส้นทาง `T1A` |
| 🆕 `BUILD NEW` | 10 | งานเขียนใหม่ทั้งหมด |
| ⛔ `DO NOT TOUCH` | 7 | frozen หรือถูกห้ามด้วยคำตัดสิน |

> **ข้อสรุปที่สำคัญที่สุด:** โครงสร้างพื้นฐาน (adapter contract · dataset kind · hashing · status ·
> finding · การแยกชั้นที่บังคับด้วย test) **มีครบและออกแบบมารองรับ `T1B` ไว้แล้ว**
> สิ่งที่ขาดคือ **ตัวสกัดของ `T1B` เอง** ซึ่งยังเป็น skeleton เปล่า
> ⇒ งานนี้คือ **การเติมชั้นที่ออกแบบไว้แล้วให้เต็ม ไม่ใช่การรื้อสถาปัตยกรรม**

---

## 5. สิ่งที่ **ยังไม่ทำ** และเหตุผล

| ยังไม่ทำ | เหตุผล |
|---|---|
| ไม่ได้แก้โค้ดแม้บรรทัดเดียว | Bo ขอ matrix ก่อน coding · และ `Q-06` (`INC-2569-08-27-01` ยังเปิด) ยังไม่มีคำตอบ |
| ไม่ได้ตรวจ `redbook/web/` ละเอียด | รอบนี้เน้นชั้นข้อมูล — ต้องตรวจก่อนประเมินงาน UI จริง |
| ไม่ได้ตัด scope 7 วัน | Bo เสนอให้ตัดร่วมกันหลังเห็น matrix |
| ไม่ได้รัน `T1B-E1` | ยังไม่มี adapter ที่สกัดได้ |

---

## 6. `DECISION REQUIRED FROM GIFT`

| # | เรื่อง | ทำไมต้องกิ๊ฟตัดสิน |
|---|---|---|
| 1 | `Q-06` — `INC-2569-08-27-01` ยังเปิด · การเขียน `AOWorkbookAdapter` นับเป็นการแก้ engine ที่ติดข้อห้ามหรือไม่ | **บล็อกการเริ่มเขียนโค้ดทั้งหมด** |
| 2 | คีย์ผสมของ `T1B` ตามข้อ 9 ของ structural map | กระทบ `RES-Q-03` ที่วางไว้เดิม |
| 3 | `Q-08` — ไฟล์ทำงานที่ยังมีสูตร ใช้ไฟล์ใดทดสอบ formula-residue preflight | ชุด `T1B` สาธารณะเป็น value-only ทั้งหมด |
| 4 | `Q-05` — ผล `T1B` จะเข้าเล่มเป็น study ใหม่หรือเป็น product track อย่างเดียว | กระทบขอบเขตงานวิจัย |
