# สถาปัตยกรรมและ Canonical Data Model — RedBook Verify

## 1. ภาพรวม

```
                   ผู้ใช้ (ผู้ตรวจ) — เบราว์เซอร์บนเครื่องเดียวกัน
                                    │  http://127.0.0.1:8600
                                    ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  FastAPI + Jinja2 (server-rendered)                              │
  │  SecurityMiddleware: CSP · nosniff · DENY frame · no-store       │
  │  verify_csrf(): double-submit cookie + ตรวจ Origin ทุก POST      │
  └──────────────────────────────────────────────────────────────────┘
        │                │                │                  │
        ▼                ▼                ▼                  ▼
  ┌───────────┐   ┌──────────────┐  ┌────────────┐   ┌──────────────┐
  │ storage/  │   │  readers/    │  │  rules/    │   │  storage/    │
  │ files.py  │   │  (อ่านเท่านั้น)│  │  catalog   │   │  audit.py    │
  │ ตรวจชนิด   │──▶│ excel_reader │─▶│ + กฎแต่ละข้อ│──▶│ append-only  │
  │ จริง+SHA256│   │ pdf_reader*  │  │ + finding  │   │ + hash chain │
  └───────────┘   └──────────────┘  └────────────┘   └──────────────┘
        │                                  │                  │
        └──────────────────┬───────────────┴──────────────────┘
                           ▼
                  SQLite (.data/redbook.sqlite3)
   projects · files · runs · run_rules · findings · item_matches
   audit_log (append-only) · security_events

   * pdf_reader = Phase 3 ยังไม่มี
```

## 2. การแยกฝ่ายสร้างออกจากฝ่ายตรวจ (หลักการข้อ 6)

เหตุผล: ถ้าเครื่องมือที่ **สร้าง** เอกสารกับเครื่องมือที่ **ตรวจ** เอกสารใช้ตรรกะชุดเดียวกัน
ความเข้าใจผิดชุดเดียวจะเกิดพร้อมกันทั้งสองฝั่ง แล้วการตรวจจะ "ผ่าน" ทั้งที่เอกสารผิด

วิธีบังคับในโครงการนี้:

1. แพ็กเกจ `redbook` **ไม่มีโค้ดสร้างหรือแก้ไฟล์เอกสารเลย** — ทดสอบด้วย AST ว่าไม่มีการเรียก `.save()`
2. **ห้าม import** โมดูลฝั่งสร้างของโครงการเดิม (`bis_p1_engine`, `p1_features`, `p1_sheet4`,
   `synthetic_p1_case_builder`, `make_synthetic_bis1010`)
3. ตรรกะจากของเดิมที่จะนำมาใช้ (เช่น `FormulaEvaluator`) จะถูก **คัดลอกมาเป็นไฟล์ใหม่พร้อมชุดทดสอบของตัวเอง**
   ไม่ใช่ import ข้ามโครงการ — ทำให้ผลการทดลองเดิมของ IS ไม่ถูกกระทบ
4. ชั้น `readers/` เปิดไฟล์ได้เฉพาะโหมดอ่าน — ทดสอบด้วย AST เช่นกัน

## 3. Canonical Data Model

โมเดลกลางอยู่ที่ `redbook/core/canonical.py` เวอร์ชัน `cdm-0.1.0`

### 3.1 `CanonicalItem` — หนึ่งรายการงบประมาณ

| กลุ่ม | ฟิลด์ |
|---|---|
| ตัวระบุเอกสาร | `document_id`, `document_version`, `fiscal_year` |
| โครงสร้างงบประมาณ | `agency_code`, `agency_name`, `plan_code`, `plan_name`, `output_or_project_code`, `output_or_project_name`, `category_code`, `category_name` |
| ตัวรายการ | `item_code`, `item_sequence`, `item_name`, `amount`, `unit` |
| ตำแหน่งต้นทาง | `location` (SourceLocation), `field_locations` (รายฟิลด์) |
| ค่าตามที่ปรากฏจริง | `raw_values` — ข้อความก่อน normalize ใช้แยก "ค่าต่าง" ออกจาก "รูปแบบต่าง" |
| เหตุผลที่เป็น null | `nulls` |
| เวอร์ชัน | `extraction_method`, `extraction_confidence`, `rule_version` |

### 3.2 `SourceLocation` — ตำแหน่งย้อนกลับ

`source_file`, `source_file_id`, `source_type`, `sheet_name`, `cell_reference`,
`row_number`, `column_letter`, `page_number`, `table_number`, `line_number`,
`bounding_box`, `extraction_method`, `extraction_confidence`

Excel ใช้ `sheet_name` + `cell_reference` · PDF ใช้ `page_number` + `table_number` +
`line_number` + `bounding_box` · ฟิลด์ที่ไม่ใช้กับชนิดนั้นเป็น `None`

### 3.3 กติกา "ห้ามเดา"

ฟิลด์ที่เอกสารไม่มีต้องตั้งผ่าน `set_null(field, reason)` เท่านั้น ซึ่ง:

- โยน `KeyError` ถ้าชื่อฟิลด์ไม่มีจริง (กันพิมพ์ผิดแล้วเงียบ)
- โยน `ValueError` ถ้าไม่ระบุเหตุผล

เหตุผลมาตรฐาน: `NULL_NOT_IN_DOCUMENT`, `NULL_NOT_MAPPED`, `NULL_UNREADABLE`,
`NULL_AMBIGUOUS`, `NULL_NOT_APPLICABLE`

## 4. สถานะผลตรวจ

แยกสองแกนโดยตั้งใจ — เพื่อให้ "คำว่าผิด" มาจากมนุษย์เท่านั้น

| แกน | ค่า |
|---|---|
| `MachineStatus` (ระบบตั้งเอง) | `match` ตรงกัน · `diff_found` พบความแตกต่าง · `likely_year_change` คาดว่าเป็นการเปลี่ยนแปลงตามปี · `likely_reduction` คาดว่าเกี่ยวข้องกับการปรับลด · `needs_human` ต้องให้มนุษย์ตรวจสอบ |
| `ReviewStatus` (มนุษย์ตั้ง) | `pending` · `confirmed_error` ยืนยันว่าเป็นข้อผิดพลาด · `confirmed_valid_change` ยืนยันว่าเป็นการเปลี่ยนแปลงที่ถูกต้อง · `exempted` ยกเว้น |

สีตามข้อกำหนดหน้าจอ:

| สี | ใช้เมื่อ |
|---|---|
| เขียว | `match` หรือ `confirmed_valid_change` |
| แดง | `confirmed_error` เท่านั้น |
| เหลือง | `diff_found` / `needs_human` ที่ยังไม่มีคนพิจารณา |
| น้ำเงิน | `likely_year_change` / `likely_reduction` |
| เทา | ความต่างด้านการแสดงผลที่ไม่กระทบค่า (`presentation_only`) และรายการที่ถูกยกเว้น |

## 5. การจับคู่รายการ (Phase 2)

ตาราง `item_matches` เตรียมไว้แล้ว มี `match_level` 4 ค่า:

| ระดับ | ความหมาย | ต้องมี `score_basis` |
|---|---|---|
| `exact` | รหัสและข้อมูลระบุตรงกันทั้งหมด | ไม่ต้อง |
| `rule_based` | จับคู่จากรหัส ชื่อ ลำดับ และโครงสร้างตามกฎที่เขียนไว้ | ต้องมี (ระบุว่ากฎข้อใดทำให้จับคู่) |
| `suggested` | ระบบเสนอว่าน่าจะเป็นรายการเดียวกัน | **ต้องมีเสมอ** พร้อม `score` และผู้ใช้ต้องยืนยัน |
| `unmatched` | จับคู่ไม่ได้ | — |

**ข้อบังคับ:** ระบบไม่รวมรายการที่ระดับ `suggested` ให้เองโดยอัตโนมัติ
ต้องมี `confirmed_by` / `confirm_result` จากมนุษย์ก่อนเสมอ

## 6. การตรวจซ้ำได้ (Reproducibility)

ทุก run บันทึก: `engine_version`, `rule_set_version`, `canonical_model_version`,
`parser_versions_json`, `config_json`, `config_hash`, `started_at`, `finished_at`,
`duration_ms`, `items_checked`, `result_hash` + SHA-256 ของไฟล์ทุกฝั่ง
และภาพนิ่งของกฎที่ใช้ในตาราง `run_rules`

`result_hash` คำนวณจาก **เนื้อหาของ finding เท่านั้น** (finding_key, กฎ, ค่า A/B, ผลต่าง,
สถานะจากระบบ, ตำแหน่ง) โดยเรียงลำดับให้คงที่ ไม่รวม `run_id` เวลา หรือคำตัดสินของมนุษย์
→ ไฟล์คู่เดิม + กฎเวอร์ชันเดิม + engine เวอร์ชันเดิม = `result_hash` ค่าเดิม

`finding_key` คำนวณจากเนื้อหาเช่นกัน ทำให้ผูกคำตัดสินของมนุษย์กลับเข้ากับประเด็นเดิม
ได้แม้จะรันใหม่คนละรอบ

## 7. หน้าจอ (สถานะการพัฒนา)

| # | หน้าจอตามข้อกำหนด | เส้นทาง | สถานะ |
|---|---|---|---|
| 1 | Dashboard โครงการตรวจ | `/` | ทำแล้ว |
| 2 | สร้างงานตรวจใหม่ | `/projects/new` | ทำแล้ว |
| 3 | เลือกโหมด | อยู่ในหน้าสร้างงานตรวจ | ทำแล้ว |
| 4 | อัปโหลดและจับคู่ไฟล์ | `/projects/{id}` | ทำแล้ว (A / B / REF) |
| 5 | ตรวจ metadata ก่อนเริ่ม | `/projects/{id}` + `/projects/{id}/precheck` | ทำแล้ว (กฎ M01–M05) |
| 6 | Processing status | ยังไม่มีหน้าแยก (การตรวจ metadata เสร็จในหลักมิลลิวินาที) | Phase 2 |
| 7 | Summary ผลตรวจ | `/runs/{id}` | ทำแล้ว |
| 8 | Compare View ซ้าย–ขวา | `/runs/{id}/compare` | ทำแล้วระดับโครงสร้างสมุดงาน · ระดับเซลล์ = Phase 2 |
| 9 | รายการข้อแตกต่างพร้อมตัวกรอง | `/runs/{id}` | ทำแล้ว (กรองตามสถานะ/ผลพิจารณา/ระดับ/กฎ) |
| 10 | Evidence View | `/findings/{id}` และ `/files/{id}/structure` | ทำแล้วเท่าที่มีข้อมูล · ระดับเซลล์ = Phase 2 |
| 11 | Human Review Queue | `/runs/{id}/review` | ทำแล้ว |
| 12 | Audit Trail | `/audit` | ทำแล้ว + ตรวจสายโซ่แฮช |
| 13 | Export รายงาน | — | Phase 4 |
| 14 | Rule Version / Rule Catalog | `/rules` | ทำแล้ว |
