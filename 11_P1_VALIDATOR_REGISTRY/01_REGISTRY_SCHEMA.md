# 01 — Dataset Registry Schema (ข้อเสนอ v0.1)

**สถานะ:** `PROPOSED — NOT APPROVED` · 6 กันยายน 2569 · ฉบับ sanitized

## 1. หลักการออกแบบ 6 ข้อ

| # | หลัก | ผลต่อ schema |
|---|---|---|
| 1 | **ชื่อไฟล์ไม่ใช่ identity** | ทุก identity มีคู่ `*_from_content` (ใช้จริง) กับ `*_from_filename` (ประกาศไว้เฉย ๆ) + ฟิลด์ตัดสิน `identity_agreement` |
| 2 | **ทุกค่าที่ดึงมาต้องชี้กลับได้** | `content_field_evidence` เก็บ `{sheet, cell, raw}` รายฟิลด์ |
| 3 | **แยก "ตัวไฟล์" ออกจาก "ข้อมูลในไฟล์"** | `content_hash` (ไบต์) กับ `semantic_content_hash` (ค่าที่อ่านได้) เป็นคนละฟิลด์ |
| 4 | **สคริปต์ไม่ตัดสินบทบาทวิจัยแทนมนุษย์** | `data_role` / `ground_truth_status` / `contamination` ออกมาเป็น `UNASSIGNED` เสมอ |
| 5 | **แยกมุมมองภายใน/สาธารณะที่ต้นทาง** | `sensitivity` + `disclosure_class` + สร้าง `registry.public.csv` แยกไฟล์ |
| 6 | **อัตลักษณ์จริงไม่อยู่ในโค้ด** | ตารางชื่อ→รหัส และรูปแบบคำต้องห้าม อ่านจากไฟล์ local นอก repo |

## 2. ฟิลด์

### 2.1 อัตลักษณ์และความคงสภาพของไฟล์

`record_id` · `registry_schema_version` · `observed_at_utc` · `source_path` 🔒 ·
`file_name` · `file_size_bytes` · `file_mtime_utc` · `content_hash` (`sha256:file-bytes`) ·
`semantic_content_hash` · `semantic_hash_cell_count` · `read_only_verified`

> 🔴 **ขอบเขตของ `semantic_content_hash`** — ครอบเฉพาะ ชื่อชีต + พิกัดเซลล์ + ค่าที่อ่านได้แบบ values-only
> **ไม่ครอบ** สูตร · รูปแบบ · merged cells · แถว/คอลัมน์ที่ซ่อน · metadata
> ⇒ **ห้ามใช้อ้างว่า "ทำซ้ำได้ค่าเดิม"** — เป็นแฮชเชิงความหมาย ไม่ใช่ reproducibility hash

### 2.2 อัตลักษณ์จากเนื้อไฟล์ (authoritative)

`fiscal_year_from_content` · `ministry_code_from_content` · `agency_code_from_content` ·
`agency_name_from_content` · `agency_code_resolution` · `operating_unit_from_content` ·
`workflow_stage_from_content` · `workflow_stage_label_raw` · `content_field_evidence`

`agency_code_resolution` ∈ `from_content_literal` | `from_name_lookup` | `from_operating_unit_prefix` | `unresolved`
— ถ้าเป็น `from_name_lookup` แปลว่าเนื้อไฟล์ให้มาแต่ชื่อ ไม่ให้รหัส ⇒ ต้องระบุในเล่มว่าเป็นการ resolve ไม่ใช่การอ่านตรง

`workflow_stage_from_content` ∈ `req_operating_unit` | `req_ministry` | `bb_officer` | `null`
(สามขั้นแรกคือขั้นก่อนประกาศใช้ทั้งหมด)

### 2.3 อัตลักษณ์จากชื่อไฟล์ (declared เท่านั้น)

`fiscal_year_from_filename` · `agency_code_from_filename` · `identity_agreement` ∈
`match` | `mismatch` | `partial_match` | `undetermined` · `identity_agreement_detail`

### 2.4 ความสัมพันธ์ระหว่างไฟล์

| ฟิลด์ | ความหมาย |
|---|---|
| `duplicate_of` | ไบต์ตรงกันทุกประการ |
| `variant_of` | ข้อมูลตรงกัน แต่ไบต์ต่าง |
| `declared_identity_key` | `agency \| fiscal_year \| schema_version` |
| `identity_collision` | key เดียวกันแต่ `semantic_content_hash` ต่าง ⇒ มีมากกว่าหนึ่งไฟล์อ้างตัวเป็นสิ่งเดียวกัน |
| `derived_from` · `supersedes` · `superseded_by` | สายเลือดของไฟล์ (กรอกมือ) |

### 2.5 สถานะการคำนวณ — ฟิลด์ที่ค้นพบว่าจำเป็น

`formula_cell_count` · `formula_cached_value_count` ·
`formula_cache_state` ∈ `no_formulas` | `no_cached_values` | `partially_cached` | `fully_cached`

**เหตุผล:** ไฟล์ export ดิบมัก **ไม่มีค่า cache ของสูตร** (เครื่องมือต้องคำนวณเอง) ส่วนไฟล์ที่เคยเปิด
ด้วย Excel แล้ว save จะมีค่าครบ — **กฎเดียวกันให้ผลคนละแบบระหว่างสองสถานะ**
สัดส่วนที่พบจริง: `no_cached_values` 17 · `fully_cached` 11 · `partially_cached` 7 · `no_formulas` 15 (จาก 50)
⇒ ถ้าไม่แยกฟิลด์นี้ จะเอาไฟล์คนละสถานะมาเทียบคะแนนกันโดยไม่รู้ตัว

### 2.6 บทบาทวิจัย (สคริปต์ไม่กรอกให้)

`data_role` ∈ `development` | `holdout_retrospective` | `mutation_known_error` |
`prospective` | `provenance_anomaly_specimen` | `tooling_output` | `research_instrument` |
`excluded` | `UNASSIGNED` · `role_rationale` · `in_research_scope` ·
`contamination` ∈ `clean` | `mapping_donor` | `agency_adjacent` | `rule_tuned_on` | `unassigned` ·
`contamination_evidence`

### 2.7 ground truth

`none` | `derived_unverified` | `cross_vintage_reference` | `external_public_corroborated` |
`synthetic_known_by_construction` | `human_confirmed` | `disputed`
+ `ground_truth_source` · `answer_key_ref` (ต้องเป็น `null` ตลอดช่วง blind)

### 2.8 🔑 การเปิดเผย — `disclosure_class`

ตัวแบ่งคือ **ขั้นของเอกสาร** ไม่ใช่แหล่งที่มา คำถามที่ถูกคือ *"ประชาชนทราบตัวเลขนี้แล้วหรือยัง"*

| ค่า | ความหมาย | เผยแพร่ |
|---|---|---|
| `enacted_public` | ยอดที่ประกาศเป็น พ.ร.บ. แล้ว | ✅ ต้องมี URL แหล่งเผยแพร่ + SHA-256 + ระบุปี |
| `draft_public` | ร่าง พ.ร.บ. ที่เผยแพร่แล้ว | ✅ ต้องกำกับคำว่า "ร่าง" ทุกครั้ง · ห้ามเสนอเป็นยอดสุดท้าย |
| `internal_prepublication` | ขั้นคำขอ/ระหว่างพิจารณา | ❌ ประชาชนยังไม่ทราบ |
| `ao_pending_publication` | เล่ม AO/คาดแดง ที่ยังไม่ขึ้นเว็บ | ❌ สถานะจะเปลี่ยนเมื่อเผยแพร่แล้ว |

**กฎผลต่าง (derived difference) — จุดที่พลาดง่ายที่สุด**

> ผลต่างระหว่างสองรอบของยอดเดียวกัน **เผยแพร่ได้ก็ต่อเมื่อปลายทางทั้งสองข้างเผยแพร่แล้ว**
>
> | คู่ | เผยแพร่ | เหตุผล |
> |---|---|---|
> | ร่าง พ.ร.บ. → พ.ร.บ. ประกาศใช้ (ปีเดียวกัน) | ✅ | ทั้งสองฉบับเผยแพร่ ใครก็คำนวณเองได้ |
> | คำขอ → พ.ร.บ. | ❌ | ปลายทางข้างหนึ่งยังไม่เผยแพร่ · **เปิดผลต่างเท่ากับเปิดยอดคำขอโดยปริยาย** |
>
> กฎข้อหลังนี้เป็นการรั่วไหลแบบ *อนุมานย้อนกลับ* ซึ่งการตรวจแบบดูคำต้องห้ามอย่างเดียวจับไม่ได้

ฟิลด์ประกอบ: `sensitivity` · `publishable` · `seal_status` ∈ `open` | `sealed` ·
`sealed_at` · `unseal_events[]` (append-only: ใคร/เมื่อไร/เหตุผล)

## 3. ผลรันทะเบียนร่าง

| ตัวเลข | ค่า |
|---|---|
| ไฟล์ที่ลงทะเบียน | 50 |
| `content_hash` ไม่ซ้ำ | 40 |
| `semantic_content_hash` ไม่ซ้ำ | 40 |
| `identity_agreement = mismatch` | 2 |
| `identity_collision` (กลุ่ม) | 3 |
| `variant_of` (ข้อมูลตรง ไบต์ต่าง) | 0 |

### สิ่งที่ทะเบียนตรวจพบ

**(ก) ชื่อไฟล์ ≠ ป้ายในเนื้อไฟล์** — 2 ระเบียน: ชื่อไฟล์ประกาศรหัสหน่วยงานหนึ่ง
แต่เนื้อไฟล์เขียนชื่อหน่วยงานอีกแห่ง

**(ข) ป้ายเดียวกัน สกุลเดียวกัน แต่ข้อมูลคนละชุด** — 3 กลุ่ม

| กลุ่ม | ต่างกันตรงไหน (ตรวจระดับเซลล์แล้ว) |
|---|---|
| ไฟล์ผลลัพธ์ปีเดียวกัน 2 ชุด | ต่างกัน **1 เซลล์** — ที่เหลือคือค่า cache ของสูตร |
| ไฟล์นำเข้าปีเดียวกัน 2 ชุด | export เดียวกันคนละสถานะการคำนวณ (`partially_cached` มี cache ค้างเป็น 0 vs `fully_cached`) |
| ไฟล์ผลลัพธ์อีกคู่ | รูปแบบเดียวกับข้างบน (`no_cached_values` vs `fully_cached`) |

**(ค) ป้ายในเนื้อไฟล์เองก็ผิด — กฎชื่อไฟล์จับไม่ได้** — 1 ระเบียน
ชื่อไฟล์ตรงกับป้าย แต่ตัวเลขทั้งไฟล์เป็นของอีกหน่วยงาน ยืนยันด้วยการเทียบยอดรายแผนงานแล้วบวกได้พอดี
⇒ ต้องมีกฎอีกชั้นที่เทียบ **ป้าย vs ข้อมูล** ไม่ใช่แค่ **ชื่อไฟล์ vs ป้าย**

**(ง) หัวรายงานรุ่นเก่าไม่ประกาศตัวตนในรูปแบบที่เครื่องอ่านได้** — 1 ระเบียนได้ `unresolved`
⇒ ต้องให้มนุษย์รับรองตัวตนก่อนใช้ และบันทึกผู้รับรอง

## 4. กฎที่เสนอเพิ่ม (candidate rules — ยังไม่ implement)

| รหัส | เงื่อนไข | ระดับ | ตัวอย่างจริงที่มี |
|---|---|---|---|
| `PRV-001` | ชื่อไฟล์ ≠ ป้ายในเนื้อไฟล์ | WARNING: provenance mismatch | 2 |
| `PRV-002` | ป้ายในไฟล์ ≠ ลายเซ็นข้อมูล | WARNING: declared identity vs data | 1 |
| `PRV-003` | `identity_collision = true` | WARNING: duplicate identity, divergent data | 3 กลุ่ม |
| `PRV-004` | `formula_cache_state ∈ {no_cached_values, partially_cached}` | INFO: uncomputed workbook | 24 |
| `DIS-001` | ผลต่างที่ปลายทางข้างหนึ่งเป็น `internal_prepublication` | BLOCK: derived disclosure | — |

`PRV-*` เป็นข้อสังเกตเชิง provenance ไม่ใช่คำตัดสินว่าไฟล์ผิด — ถ้อยคำต้องคงแนวเดิม
("ข้อสังเกต / ควรตรวจสอบ") และ **ห้ามแก้ไฟล์อัตโนมัติ**

## 5. ข้อจำกัดของทะเบียนฉบับนี้

1. `PRV-002` ยังไม่มีนิยามเชิงปริมาณ — ยืนยันด้วยการเทียบยอดด้วยมือ 1 กรณี ยังไม่เป็นกฎ
2. ตารางชื่อ→รหัสเป็นพจนานุกรมที่ผู้วิจัยตั้งเอง 5 รายการ ไม่ใช่ทะเบียนราชการ
3. ทะเบียนครอบเฉพาะชุดที่ลงทะเบียนแล้ว ยังไม่รวมชุดปฏิบัติงานที่ยังหาไม่พบ
4. `semantic_content_hash` อ่านแบบ values-only ⇒ ไฟล์ที่ไม่มี cache จะให้แฮชที่ "ขาดค่าสูตร"
   ไฟล์เดียวกันเปิดด้วย Excel แล้ว save จะได้แฮชใหม่ — **เป็นพฤติกรรมที่ตั้งใจ ไม่ใช่บั๊ก**
