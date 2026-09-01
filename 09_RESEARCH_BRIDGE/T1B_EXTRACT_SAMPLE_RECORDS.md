# T1B EXTRACT — ตัวอย่าง canonical records จากไฟล์จริง

**ตอบ:** คำสั่ง Gift ข้อ C (1 กันยายน 2569) · **ผู้จัดทำ:** Giho
**สถานะ:** `T1B INSPECTION LAYER IMPLEMENTED — EXTRACTION / VERIFICATION PIPELINE NOT YET COMPLETE`
**ป้ายกำกับ:** `PRODUCT EVIDENCE — POST-FREEZE`

> 🔴 **ยังห้ามเรียกว่า** `T1B-E1 complete` · `operational verifier complete`
> · `RedBook system complete` · หรือผลของ frozen `T1A` study

---

## 1. จำนวน record ต่อไฟล์

| ไฟล์ | total | `VALUE` | `STRUCTURAL` | `UNMAPPED` | ต้องมนุษย์ตรวจ |
|---|---:|---:|---:|---:|---:|
| `XL_FY2569_draft-bill_21000_MOPH-summary.xlsx` | 441 | 223 | 7 | 211 | 221 |
| `XL_FY2569_draft-bill_21011_HSRI.xlsx` | 374 | 251 | 4 | 119 | 119 |
| `XL_FY2569_draft-bill_21016_NVI.xlsx` | 496 | 254 | 5 | 237 | 242 |
| `XL_FY2570_draft-bill_21000_MOPH-summary.xlsx` | 443 | 238 | 7 | 198 | 213 |
| `XL_FY2570_draft-bill_21011_HSRI.xlsx` | 372 | 251 | 4 | 117 | 127 |
| `XL_FY2570_draft-bill_21016_NVI.xlsx` | 538 | 262 | 4 | 272 | 282 |

**`UNMAPPED` สูงเป็นเรื่องที่ตั้งใจ** — เป็นชีตที่ layout ยังไม่ map
(ชีตปก · ชีตประกอบ · ชีตแผนงาน/โครงการ) ระบบ**บันทึกไว้ครบไม่ทิ้งเงียบ**
และติดเหตุผลกำกับทุกรายการ ตาม invariant ข้อ 1–2 และ 8

---

## 2. จำนวน record ต่อ sheet role

| ไฟล์ | `04` | `04_02` | `05` | `06` | `07` | `07_PLAN` | `07_PROJECT` | `08` | ไม่มีบทบาท |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FY2569 · 21000 | 27 | 79 | 182 | 71 | 48 | 0 | 0 | 0 | 34 |
| FY2569 · 21011 | 15 | 0 | 48 | 15 | 36 | 62 | 0 | 156 | 42 |
| FY2569 · 21016 | 18 | 0 | 48 | 19 | 37 | 85 | 62 | 156 | 71 |
| FY2570 · 21000 | 23 | 74 | 197 | 68 | 48 | 0 | 0 | 0 | 33 |
| FY2570 · 21011 | 15 | 0 | 48 | 15 | 36 | 64 | 0 | 156 | 38 |
| FY2570 · 21016 | 21 | 0 | 53 | 20 | 36 | 85 | 92 | 156 | 75 |

แฟ้มระดับกระทรวงไม่มีบทบาท `08` และไม่มีชีตแผนงาน/โครงการ — ตรงกับโครงสร้างจริงของเอกสาร

---

## 3. ตัวอย่าง canonical records

ทุกตัวอย่างแยกสามกลุ่มตาม `T1B_CANONICAL_KEY_SPEC.md` —
**IDENTITY** (เข้าคีย์) · **COMPARISON** (นำมาเทียบ) · **PROVENANCE** (ชี้หลักฐาน ห้ามใช้จับคู่)

### S1 · แถวจำนวนเงิน — `monetary row`

| กลุ่ม | ค่า |
|---|---|
| IDENTITY | `21011` · `agency` · `SECTION_05` · `NOT_APPLICABLE` · `()` · `"รวมทั้งสิ้น"` |
| COMPARISON | `fiscal_year=2569` · `"ปี 2569"` · `ล้านบาท` · **monetary** · `Decimal("58.4401")` |
| PROVENANCE | `Sheet5` idx 2 · `MAIN` · cell `D6` · row 6 · header 5 · raw `58.4401` · unit cell `"ล้านบาท"` · `สถาบันวิจัยระบบสาธารณสุข` |
| สถานะ | `ok` · ไม่ต้องมนุษย์ตรวจ |

### S2 · แถวตัวชี้วัด — `indicator row`

| กลุ่ม | ค่า |
|---|---|
| IDENTITY | `21011` · `agency` · `SECTION_05` · hierarchy `("2", "ตัวชี้วัดเชิงคุณภาพ : การบริหารจัดการภายใต้ โครงการเสริมสร้าง…")` |
| COMPARISON | `fiscal_year=2568` · `ร้อยละ` · **ไม่ใช่จำนวนเงิน** · `Decimal("100.00")` |
| PROVENANCE | `Sheet5` · cell `C13` · row 13 · raw `'100'` (ข้อความ) · unit cell `"ร้อยละ"` |
| สถานะ | `ok` |

> 🔴 `is_monetary = False` ⇒ ค่านี้จะ**ไม่ถูกนำไปกระทบยอดเงิน**

### S3 · แถวหัวข้อ — `hierarchy / parent row`

| กลุ่ม | ค่า |
|---|---|
| IDENTITY | `SECTION_05` · hierarchy `("1",)` · `"1. เพื่อเป็นค่าใช้จ่ายในการดำเนินการภาครัฐ"` |
| COMPARISON | `fiscal_year=None` · ไม่มีค่า |
| PROVENANCE | `Sheet5` · cell `A9` · row 9 · `row_kind = STRUCTURAL` |

### S4 · ลูกใต้หัวข้อ — ป้ายซ้ำแต่คนละ parent

`" เงินงบประมาณ"` ปรากฏสองครั้งในชีตเดียว โดยแยกด้วย `hierarchy_path`

| แถว | hierarchy_path | ปี 2568 |
|---:|---|---:|
| 10 | `("1", "เงินงบประมาณ")` | `38.1527` |
| 15 | `("2", "เงินงบประมาณ")` | `15.1185` |

### S5 · แถวชีตแผนบุคลากร — `supporting-plan row`

| กลุ่ม | ค่า |
|---|---|
| IDENTITY | `21011` · `agency` · ไม่มีบทบาท · `"รายการบุคลากรภาครัฐ"` |
| COMPARISON | `บาท` · **monetary** · `value_decimal = None` (ยังไม่แปลง เพราะ layout ยังไม่ map) |
| PROVENANCE | ชีต `บุค` idx 5 · `SUPPORTING` · row 2 · raw ทั้งแถวเก็บไว้ครบ 12 ช่อง รวมค่า `39567000` |
| สถานะ | `partial` · **ต้องมนุษย์ตรวจ** · `uncertainty = ('supporting_sheet_layout_not_mapped',)` |

> ชีตนี้คือชีตที่ defect เดิม `("b","B")` จับไม่ได้ — ตอนนี้ถูกบันทึกครบและติดธงไว้

### S6 · ค่าปีล่วงหน้า — `future-year value`

| กลุ่ม | ค่า |
|---|---|
| IDENTITY | เหมือน S1 ทุกฟิลด์ (`"รวมทั้งสิ้น"`) |
| COMPARISON | `fiscal_year=2572` · `"ปี 2572"` · `ล้านบาท` · `Decimal("45.7097")` |
| PROVENANCE | `Sheet5` · cell `G6` · row 6 |

> คีย์เดียวกับ S1 ต่างกันที่ `fiscal_year` เท่านั้น
> ⇒ **พิสูจน์ว่าปีเป็น comparison attribute ไม่ใช่ identity** ตามที่ Gift กำหนด
> และเป็นฐานของการตรวจ propagation ไปปีถัดไป/รายการผูกพัน

### S7 · หน่วยนับผิดปกติ — `declared unit anomaly`

| กลุ่ม | ค่า |
|---|---|
| IDENTITY | `21011` · `SECTION_05` · hierarchy `("2", "ตัวชี้วัดเชิงคุณภาพ : …")` |
| COMPARISON | `fiscal_year=2569` · **`declared_unit = UNRESOLVED`** · `is_monetary = False` |
| PROVENANCE | `Sheet5` · cell `C13` · row 13 · **`raw_unit_cell = '100'`** ← ควรเป็น `"ร้อยละ"` |
| สถานะ | `unconfirmed` · **ต้องมนุษย์ตรวจ** · `uncertainty = ('declared_unit_unresolved',)` |

> 🔴 เป็น **data defect ของไฟล์ต้นทางเอง** ระบบ**รายงาน ไม่ซ่อม ไม่เดา**

### S8 · หน่วยระดับชีต + เศษ float — `SECTION_08`

| กลุ่ม | ค่า |
|---|---|
| IDENTITY | `21011` · `SECTION_08` · hierarchy `("2",)` · `"2. รายได้ประเภทเงินนอกงบประมาณ"` |
| COMPARISON | `fiscal_year=2569` · `ล้านบาท` · `Decimal("937.5201")` |
| PROVENANCE | `Sheet8` · cell `D6` · row 6 · header 3 · **raw `937.5201000000001`** · unit cell `"หน่วย : ล้านบาท (ทศนิยม 4 ตำแหน่ง)"` |
| สถานะ | `unconfirmed` · `uncertainty = ('unit_from_sheet_level_declaration',)` · ไม่ต้องมนุษย์ตรวจ |

> ค่าดิบ `937.5201000000001` **ยังถูกเก็บไว้** คู่กับค่า `Decimal` ที่ปัดแล้ว
> ⇒ trace กลับเซลล์จริงได้ และพิสูจน์ได้ว่าไม่ได้แก้ข้อมูลต้นทาง

### S9 · ชีตแผนงานที่จับคู่ด้วยชื่อ ไม่ใช่เลขข้อ

| กลุ่ม | ค่า |
|---|---|
| IDENTITY | `21016` · `agency` · **`SECTION_07_PLAN`** · section_title `"แผนงานยุทธศาสตร์เสริมสร้างให้คนมีสุขภาวะที่ดี"` · `PLAN_STRATEGIC` |
| PROVENANCE | ชีต **`Sheet7.3.1`** (FY2570) — ปี 2569 แผนเดียวกันนี้อยู่ที่ `Sheet7.4.1` เลขข้อ `7.4` |
| สถานะ | `partial` · **ต้องมนุษย์ตรวจ** · `uncertainty = ('header_row_not_located',)` |

> 🔴 เลขข้อ `7.3` ปี 2569 = *ส่งเสริมความสัมพันธ์ระหว่างประเทศ*
> แต่ `7.3` ปี 2570 = *เสริมสร้างให้คนมีสุขภาวะที่ดี* — **คนละแผนงาน**
> จึงยุบเลขข้อทิ้งแล้วใช้ชื่อแผนงานเป็นตัวระบุ

---

## 4. ตรวจกับ `T1B_CANONICAL_KEY_SPEC.md` — แยกสามกลุ่มจริงหรือไม่

| ข้อกำหนด | ผลตรวจ | หลักฐาน |
|---|---|---|
| identity ไม่มี `fiscal_year` | ✅ | S1 กับ S6 มีคีย์เดียวกันทุกฟิลด์ ต่างเฉพาะปี |
| identity ไม่มี `declared_unit` | ✅ | S7 หน่วยเปลี่ยนเป็น `UNRESOLVED` แต่คีย์ยังเท่าเดิม ⇒ รายงานเป็น finding ไม่ใช่ "ลบแถว+เพิ่มแถว" |
| identity ไม่มีชื่อ/ตำแหน่งชีต | ✅ | S9 ชีต `Sheet7.4.1` กับ `Sheet7.3.1` ให้คีย์เดียวกัน |
| `document_level` อยู่ในคีย์ | ✅ | `รวมทั้งสิ้น` ระดับกระทรวงกับระดับหน่วยงานไม่จับคู่กัน (test `test_fm07`) |
| `hierarchy_path` แยกป้ายซ้ำ | ✅ | S4 |
| provenance ไม่ถูกใช้จับคู่ | ✅ | `sheet_name_actual` · `sheet_index_actual` · `cell_ref` อยู่นอก `T1BKey` ทั้งหมด |
| ไม่ทิ้งค่าดิบ | ✅ | S8 เก็บทั้ง `937.5201000000001` และ `Decimal("937.5201")` |
| normalize ไม่แรงเกินไป | ✅ | test `test_reg_normalization_does_not_collapse_distinct_rows` — ไม่มีคีย์ซ้ำที่ชี้คนละเซลล์ |

**ข้อเสนอแก้ key spec:** เพิ่มฟิลด์ **`section_title_norm`** เข้า identity
(ใช้เฉพาะชีตแผนงาน/โครงการ · ตัดเลขปีออกก่อนเสมอ) — **รอ Gift อนุมัติก่อน freeze**

---

## 5. ข้อจำกัดที่ทราบ

| # | ข้อจำกัด |
|---|---|
| 1 | ชีตแผนงาน/โครงการ (`SECTION_07_PLAN` · `SECTION_07_PROJECT`) ยังหาแถวหัวตารางไม่พบ ⇒ ยังเป็น `UNMAPPED` ยังไม่ได้ค่ารายปี |
| 2 | ชีตปก (`COVER`) layout คนละแบบ (ป้ายอยู่คอลัมน์ `B` · หน่วยอยู่ `I`/`M`) ⇒ ยังไม่ map |
| 3 | ชีตประกอบ (`SUPPORTING`) เก็บครบทุกแถวแต่ยังไม่แยกคอลัมน์ค่า/หน่วย |
| 4 | `agency_code` และ `document_status` อ่านจาก**ชื่อไฟล์** ไม่มีในเนื้อไฟล์ — ติดธงไว้ทุก record |
| 5 | `hierarchy_parser` รองรับสองระดับ ยังไม่รองรับหัวข้อย่อยซ้อนหลายชั้น |
| 6 | ยังไม่ถอดความหมาย `anchor_code` |
| 7 | ยังไม่มี matching · compare · roll-up · finding · human review · readiness gate |
