# AI_HANDOFF_LOG — บันทึกการส่งต่องานระหว่าง Bo กับ Giho

**ประเภทเอกสาร:** `COORDINATION LAYER ONLY — NOT AN AUTHORITY`

> กติกา: **append-only** · เพิ่มรายการใหม่ต่อท้าย **ห้ามแก้หรือลบรายการเดิม**
> ทุกรายการต้องระบุ: ใครทำ · อ่านอะไร · สร้าง/แก้อะไร · **ไม่ได้แตะอะไร** · อะไรที่ยังไม่ตัดสิน
> ทุก assertion ที่อ้างว่าเป็นผลจริงต้องมี path / commit / test / evidence pointer

---

## `HL-001` — ตั้งชั้นประสานงานและร่างเอกสารสามฉบับ

| | |
|---|---|
| **วันที่** | 1 กันยายน 2569 |
| **ผู้ทำ** | Giho (Claude) |
| **สั่งโดย** | Gift |
| **ป้าย** | `EVIDENCE` · `ENGINEERING OBSERVATION` · `RISK` · `DECISION REQUIRED FROM GIFT` |

### สิ่งที่อ่านเพื่อยืนยันข้อเท็จจริง

| แหล่ง | ใช้ยืนยันอะไร |
|---|---|
| `redbook-verify-is` → `08_evidence_register/EVIDENCE_INDEX.md` | สถานะ freeze · เวอร์ชันที่ตรึง · ผล Human Review · รายการที่ยัง blocked |
| `redbook-verify-is` → `08_evidence_register/EVIDENCE_INDEX_SUPPLEMENT_01_INSTRUMENT_DEFECTS.md` | `LIMITED MEASUREMENT RISK — DISCLOSURE REQUIRED` |
| `redbook-verify-is` → `00_project_control/CLAIM_BOUNDARY.md` | ถ้อยคำที่ห้าม/อนุมัติ · หัวข้อ 9 (forward-only) |
| `redbook-verify-is` → `00_project_control/DECISIONS_LOG.md` | เลขว่างถัดไป `RES-D-54` |
| `redbook-verify-is` → `00_project_control/LANDING_BOUNDARY_REGISTER.md` | `e9360ad` = `INTENTIONALLY NOT LANDED` |
| `redbook-verify-is` → `03_dataset_register/RESEARCH_DATASET_REGISTER.md` · `DATASET_KIND_CROSSWALK.md` | ชั้น `T1A` / `T1B` / `T2` · สถานะ `T1B-E1` |
| `redbook-verify` → `docs/EXPERIMENT_PROTOCOL.md` | นิยาม `M-SET` = สำเนาของ `T1-01` · `C-SET` = `T1-01` ↔ `T1-02` |
| `redbook-verify` → `docs/DECISIONS_LOG.md` | เลขว่างถัดไป `SYS-D-33` |
| repo นี้ → `README.md` · `docs/` สี่ฉบับ | ร่างเดิมของ Bo |

### สิ่งที่รันเอง

| คำสั่ง | ผล |
|---|---|
| `git remote -v` ทั้งสอง repo | **ว่างทั้งคู่ — ไม่มี remote** |
| `pytest --collect-only` ที่ `redbook-verify` | **179 tests collected** ✅ ตรงกับที่ `EVIDENCE_INDEX.md` บันทึกไว้ |
| `gh repo view` repo นี้ | **`visibility: PUBLIC`** · สร้าง 1 ก.ย. 2569 |

### สิ่งที่สร้าง — ทั้งหมดเป็นไฟล์ใหม่ในสำเนาท้องถิ่น ยังไม่ push

```
09_RESEARCH_BRIDGE/
├── README.md
├── CURRENT_STATE.md
├── RESEARCH_PRODUCT_BOUNDARY.md
├── OPERATIONAL_PRODUCT_VISION.md
├── OPEN_QUESTIONS.md
└── AI_HANDOFF_LOG.md
```

### สิ่งที่ **ไม่ได้แตะ** (ตามคำสั่ง Gift)

- ❌ frozen Evidence Index — ไม่เปิดแก้
- ❌ Human Review workbooks รอบที่ 1 และรอบที่ 2 — ไม่เปิดแก้
- ❌ raw results ใน `redbook-verify-data` — อ่านทะเบียนเท่านั้น ไม่แตะไฟล์ผล
- ❌ Chapter 4 — ไม่เปิดแก้
- ❌ production engine — ไม่แก้โค้ดใด ๆ (`pytest --collect-only` ไม่รันและไม่แก้ไข)
- ❌ `docs/` ของ Bo ใน repo นี้ — อ่านอย่างเดียว
- ❌ ไม่มี `git commit` และไม่มี `git push` ในรอบนี้

### ข้อค้นพบหลักที่ส่งต่อให้ Bo

`ENGINEERING OBSERVATION` · `EVIDENCE`

> ผลวิจัยที่ freeze แล้วทั้งหมดวัดบนชั้น **`T1A` — Official Flat Data Table**
> ส่วน Mode A / Mode B ที่ Gift ต้องการทำงานบนชั้น **`T1B` — Official AO/RedBook Workbook**
> ซึ่ง `T1B-E1` **ยังไม่ได้รัน** (รอ structural mapping · `RES-Q-02`)
> และมีข้อบังคับว่า `T1A` กับ `T1B` **ห้ามใช้ mapping หรือตัวหารร่วมกัน** (`RES-D-24` · `RES-Q-01`)

**ผลต่อร่างของ Bo:** `docs/CURRENT_STATE.md` ระบุว่า *"structured Excel comparison / matching"*
อยู่ในกลุ่ม *"already demonstrated strongly"* โดยไม่ได้แยกชั้นข้อมูล
ในทางหลักฐานข้อความนี้เป็นจริงเฉพาะชั้น `T1A` — เสนอให้เติมการแยกชั้นเข้าไป

**ยังไม่พบข้อความใดในร่างของ Bo ที่ขัดกับ `CLAIM_BOUNDARY.md` โดยตรง**
ข้อสังเกตข้างต้นเป็นเรื่องความละเอียดของขอบเขต ไม่ใช่การอ้างเกินหลักฐาน

### ความเสี่ยงที่ยกให้ Gift

| | ประเด็น | อยู่ที่ |
|---|---|---|
| 1 | repo เป็น **public** และ consent `R1`–`R4` ยังไม่ปิด | `OPEN_QUESTIONS.md` `Q-01` |
| 2 | ที่อยู่ของ `09_RESEARCH_BRIDGE/` และความซ้ำกับ `docs/` เดิม | `Q-02` |
| 3 | ทั้งสอง SSOT **ไม่มี git remote** — ไม่มีสำเนาสำรอง | `Q-03` |
| 4 | ทะเบียนระบุที่มาของ mutation set ไม่ตรงกัน | `Q-04` |
| 5 | `INC-2569-08-27-01` ยังเปิด — กระทบว่าจะเริ่มพัฒนาได้หรือยัง | `Q-06` |

### สถานะเมื่อจบรายการนี้

> ### `DRAFT COMPLETE — AWAITING GIFT DECISION ON Q-01 AND Q-02 BEFORE PUBLISH`

---

## `HL-002` — Gift ตัดสิน `Q-01` และ `Q-02` · เผยแพร่ชั้นประสานงาน

| | |
|---|---|
| **วันที่** | 1 กันยายน 2569 |
| **ผู้ทำ** | Giho (Claude) ตามคำตัดสินของ Gift |
| **ป้าย** | `DECISION REQUIRED FROM GIFT` → ตัดสินแล้ว |

### คำตัดสินที่ได้รับ

| ข้อ | คำตัดสิน |
|---|---|
| `Q-01` | **`APPROVED FOR PUBLIC PUBLICATION AS DRAFTED`** — push ได้ทั้งหมดตามที่ร่าง Giho ได้แจ้งความเสี่ยงเรื่อง repo เป็น public และ consent `R1`–`R4` ที่ยังไม่ปิดแล้ว และ Gift ยืนยันคำสั่งเดิม |
| `Q-02` | **ทาง (ข)** — `09_RESEARCH_BRIDGE/` อยู่ที่ repo นี้ · **เก็บคู่กับ `docs/` ทั้งสองชุด** |

### สิ่งที่ทำต่อจากคำตัดสิน

1. บันทึกคำตัดสินลง `OPEN_QUESTIONS.md` ในแถวเดิมของ `Q-01` และ `Q-02` (ไม่ลบรายการ)
2. เพิ่มหัวข้อ "ความสัมพันธ์กับ `docs/`" ใน `README.md` — กติกาเวลาสองชุดขัดกัน
3. commit และ push `09_RESEARCH_BRIDGE/` ขึ้น `main`

### ขอบเขตของคำอนุญาต

คำอนุญาตครอบคลุม **เฉพาะเนื้อหาที่ร่างไว้ ณ 1 ก.ย. 2569** — เนื้อหาใหม่ต้องพิจารณาแยกรายครั้ง
โดยเฉพาะไฟล์ข้อมูล · เนื้อหาจากสภาพแวดล้อมของหน่วยงาน (`RES-D-29` ห้ามอยู่แล้ว) · หลักฐานที่ยังไม่เผยแพร่

### สิ่งที่ยัง **ไม่ได้แตะ** เหมือนเดิม

frozen Evidence Index · Human Review workbooks · raw results · Chapter 4 · production engine · `docs/` ของ Bo

### รายการที่ยังค้าง

`Q-03` (ไม่มี git remote) · `Q-04` (ที่มา mutation set) · `Q-05` (Mode A/B เข้าเล่มหรือไม่)
· `Q-06` (`INC-2569-08-27-01`) · `Q-07` (คำตัดสินรับรองกรอบสามฝ่าย)

### สถานะเมื่อจบรายการนี้

> ### `COORDINATION LAYER PUBLISHED — Q-03 TO Q-07 STILL OPEN`

---

## `HL-003` — ส่งงาน `BRIDGE-001` ให้ Bo · structural map + reuse matrix

| | |
|---|---|
| **วันที่** | 1 กันยายน 2569 |
| **ผู้ทำ** | Giho (Claude) |
| **สั่งโดย** | Bo ผ่าน issue `BRIDGE-001` — First engineering task |
| **ป้าย** | `ENGINEERING OBSERVATION` · `EVIDENCE` · `RISK` · `DECISION REQUIRED FROM GIFT` |

### สิ่งที่รันเอง — อ่านอย่างเดียวทั้งหมด

| คำสั่ง | ผล |
|---|---|
| สำรวจ workbook 6 ไฟล์ด้วย `openpyxl` (`data_only` ทั้งสองโหมด) | ได้ชีต · merged · formula · unit · dims ครบทุกชีต |
| เทียบชื่อชีตข้ามปีรายหน่วยงาน | พบชื่อและลำดับไม่คงที่ |
| ดึงหัวตารางชีตบทบาท `5.` ทั้ง 6 ไฟล์ | พบคอลัมน์ปีเลื่อนหนึ่งปี |
| ตรวจทศนิยมของค่าที่เก็บจริง | พบ 8 เซลล์เกิน 4 ตำแหน่งใน 16 แถวที่สุ่ม |
| `wc -l` โมดูลใน `redbook/` | ได้ขนาดจริงทุกโมดูลที่ลงใน matrix |

**ไม่มีการเขียนทับ ไม่มีการ save ไฟล์ต้นทาง ไม่มีการแก้โค้ดแม้บรรทัดเดียว**
สคริปต์สำรวจอยู่ใน scratchpad ของ session **ไม่ได้ commit เข้า repo**

### สิ่งที่สร้าง

| ไฟล์ | เนื้อหา |
|---|---|
| `T1B_STRUCTURAL_MAP.md` | โครงสร้างจริง 11 หัวข้อ + silent failure 3 แบบ + คีย์ที่เสนอ |
| `T1B_REUSE_ADAPT_BUILD_MATRIX.md` | matrix 4 กลุ่ม · `REUSE` 9 · `ADAPT` 10 · `BUILD NEW` 10 · `DO NOT TOUCH` 7 |
| `OPEN_QUESTIONS.md` | เพิ่ม `Q-08` · `Q-09` |

### ข้อค้นพบที่ต้องแจ้ง

1. 🔴 **ชื่อชีตและตำแหน่งชีตใช้เป็นคีย์ไม่ได้** — 21016 มี 17 ชีตปี 2569 แต่ 19 ชีตปี 2570 · ชื่อเปลี่ยนทั้งข้ามปีและข้ามหน่วยงาน
2. ✅ **`A1` ใช้ยึดบทบาทชีตได้** — เลขข้อคงที่ทั้ง 6 ไฟล์
3. 🔴 **SILENT FAILURE #1** คอลัมน์ปีเลื่อนหนึ่งปี (`ปี 2568..2572` → `ปี 2569..2573`)
4. 🔴 **SILENT FAILURE #2** หน่วยอยู่ระดับแถว — `ล้านบาท` ปนกับ `ร้อยละ` ในชีตเดียว
5. 🔴 **SILENT FAILURE #3** ค่าที่เก็บมีเศษ float เกินทศนิยมที่ประกาศ
6. ⚠️ **defect ใน skeleton** — `supporting_sheet_prefixes = ("b","B")` จับ `บุค` (บ ไทย · 837 แถว) ไม่ได้
7. **`AOWorkbookAdapter` = skeleton ล้วน** `inspect()`/`extract()` `raise NotImplementedError`

### สิ่งที่ **ไม่ได้แตะ**

frozen Evidence Index · Human Review workbooks · raw results · Chapter 4 · production engine
· `docs/` ของ Bo · ไฟล์ต้นทาง `T1B` (อ่านอย่างเดียว) · Audit Trail (ยัง BLOCKED ตาม `RES-D-41`)

### `DECISION REQUIRED FROM GIFT`

`Q-06` (incident boundary — **บล็อกการเริ่มเขียนโค้ด**) · `Q-08` (ไฟล์ทดสอบ preflight)
· `Q-09` (คีย์ผสม `T1B`) · `Q-05` (ผล `T1B` เข้าเล่มหรือไม่)

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — CODING BLOCKED PENDING Q-06`

---

## `HL-004` — คำสั่งหลักของ Gift · ตรวจ incident · เผยแพร่ข้อมูล · implementation รอบแรก

| | |
|---|---|
| **วันที่** | 1 กันยายน 2569 |
| **ผู้ทำ** | Giho (Claude) |
| **สั่งโดย** | Gift — คำสั่งหลัก 14 ข้อ |
| **ป้าย** | `EVIDENCE` · `ENGINEERING OBSERVATION` · `RISK` · `DECISION REQUIRED FROM GIFT` |

### ① ตรวจ verbatim ของ `INC-2569-08-27-01` (คำสั่งข้อ 5)

อ่านครบ 11 เอกสารในโฟลเดอร์ incident + `DECISIONS_LOG.md`
ยกข้อความห้ามที่พบมาไว้ใน `GIFT_MASTER_DIRECTIVE_T1B.md` หัวข้อ 7 ครบทุกฉบับ

> ### ✅ `NO VERBATIM PROHIBITION FOUND AGAINST CREATING A NEW T1B PATH`

ข้อความจริงคือ **"ห้ามแก้โค้ด deployment"** ซึ่ง `RES-D-31` นิยามขอบเขต deployment
ไว้ชัดว่าเป็น private cloud · health check · TLS · backup/restore · ZAP
— `T1B` adapter ไม่อยู่ในขอบเขตนั้น

⚠️ **สิ่งที่ต้องแจ้ง:** ลำดับงาน 10 ขั้นของ `RES-D-32` **ไม่มีงาน `T1B` / FY2570 MVP อยู่เลย**
เพราะตอนออกคำตัดสิน (27 ส.ค.) ยังไม่มีสายงานผลิตภัณฑ์แยก
⇒ ไม่ขัดคำสั่งใด แต่เป็นสายงานใหม่นอกลำดับที่เคยตัดสิน — เสนอออก `RES-D-54` / `SYS-D-33` รับรอง

### ② เอกสารที่สร้าง

| ไฟล์ | เนื้อหา |
|---|---|
| `09_RESEARCH_BRIDGE/GIFT_MASTER_DIRECTIVE_T1B.md` | คำสั่งหลัก 14 ข้อ + ผลตรวจ incident |
| `09_RESEARCH_BRIDGE/T1B_CANONICAL_KEY_SPEC.md` | ตอบ `Q-09` ครบ 6 รายการ + failure mode ที่พบเพิ่ม |
| `10_T1B_DATASET/DATASET_REGISTER.md` | ทะเบียน 7 ฟิลด์ตามคำสั่งข้อ 10 |
| `10_T1B_DATASET/ao_workbook/*.xlsx` | ไฟล์จริง 6 ไฟล์ · แฮชตรงกับต้นทางทั้งหมด |

### ③ โค้ด — repo `redbook-verify` branch `t1b/fy2570-mvp` commit `8103268`

| ไฟล์ | หน้าที่ |
|---|---|
| `redbook/t1b/normalize.py` | ปรับรูปป้ายแถว · ยุบช่องว่าง · แยกเลขนำหน้า |
| `redbook/t1b/roles.py` | `sheet_role` · `document_level` · `plan_role` · `classify_sheet` |
| `redbook/t1b/header.py` | `locate_header_row` · `align_years` ด้วยป้ายปี |
| `redbook/t1b/units.py` | หน่วยระดับแถว · `Decimal` normalization |
| `redbook/t1b/hierarchy.py` | แยกป้ายซ้ำใต้หัวข้อต่างกัน |
| `redbook/t1b/keys.py` | `T1BKey` · ห้ามจับคู่ข้ามระดับเอกสาร |
| `redbook/adapters/ao_workbook.py` | `inspect()` implement แล้ว · `extract()` ยังไม่ |
| `tests/test_t1b_failure_modes.py` | 24 tests · failure mode 11 ข้อ |
| `tests/test_t1b_adapter_inspect.py` | 8 tests · รวมการตรวจกับไฟล์จริง |

**tests: 179 → 211 ผ่านทั้งหมด**

### ④ ข้อค้นพบระหว่าง implement

| # | เรื่อง |
|---|---|
| 1 | 🔴 **หัวเรื่องไม่ได้อยู่ที่ `A1` เสมอ** — ชีตปกของทุกแฟ้มมี `A1 = None` และหัวเรื่องอยู่ที่ `A2` |
| 2 | 🔴 **ต้องเก็บเลขย่อยของบทบาท** — ในแฟ้มเดียวมีชีต `7.` · `7.2` · `7.3` ถ้าตัดเหลือ `SECTION_07` ทั้งสามจะกลายเป็นบทบาทเดียวกัน |
| 3 | 🔴 **ห้ามจับคำว่า "กระทรวง" ลอย ๆ เพื่อระบุระดับเอกสาร** — ชีตปกของแฟ้ม*ระดับหน่วยงาน*เขียนว่า `กระทรวงสาธารณสุข` (ต้นสังกัด) การจับคำลอย ๆ จะระบุแฟ้มหน่วยงานทุกแฟ้มเป็นระดับกระทรวง |
| 4 | ✅ พิสูจน์กับไฟล์จริงแล้วว่า `Sheet7_2 (2)` (FY2569) กับ `Sheet 7.2` (FY2570) — ชื่อต่างกันสิ้นเชิง — ได้ `SECTION_07_03` + `PLAN_STRATEGIC` ตรงกัน |

### ⑤ สิ่งที่ **ไม่ได้แตะ**

`redbook/t1/` ทั้งหมด · `FlatDataTableAdapter` · frozen canonical/schema/rules/version
· raw results · Evidence Index · Chapter 4 · Human Review workbooks · Audit Trail
· `docs/` ของ Bo · ไฟล์ต้นทาง `T1B` (มี test ตรวจแฮชก่อน/หลัง `inspect()`)
· ไฟล์ค้างของสายอื่นใน `reviewpack/` — **ไม่ใช้ `git add -A`** ตามกติกา incident

### ⑥ ข้อยกเว้นเดียวที่ต้องรายงาน

แก้ `tests/test_adapter_isolation.py` **หนึ่งข้อ** — เดิมบังคับว่า `AOWorkbookAdapter`
ต้องมี `supporting_sheet_prefixes` ซึ่งคำสั่ง Gift ข้อ 3 ระบุว่าเป็น defect
ตรวจแล้วว่าไฟล์นี้ **ไม่อยู่ใน tag `t1-frozen-1.0.0`** (เพิ่มหลัง freeze ที่ `ba39589`)
จึงไม่ใช่การแตะ frozen path

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — CRITICAL PATH 1-2 COMPLETE`

---

## `HL-005` — `AOWorkbookAdapter.extract()` + invariant tests กับไฟล์จริง

| | |
|---|---|
| **วันที่** | 1 กันยายน 2569 |
| **ผู้ทำ** | Giho (Claude) |
| **สั่งโดย** | Gift — คำสั่ง A · B · C |
| **ป้าย** | `ENGINEERING OBSERVATION` · `EVIDENCE` · `RISK` · `DECISION REQUIRED FROM GIFT` |

### สถานะที่ใช้

> ### `T1B INSPECTION LAYER IMPLEMENTED — EXTRACTION / VERIFICATION PIPELINE NOT YET COMPLETE`

**ยังห้ามเรียกว่า** `T1B-E1 complete` · `operational verifier complete`
· `RedBook system complete` · หรือผลของ frozen `T1A` study

### โค้ด — `redbook-verify` branch `t1b/fy2570-mvp` commit `7eb7b46`

`redbook/t1b/records.py` ใหม่ · `redbook/adapters/ao_workbook.py` implement `extract()`
· `tests/test_t1b_extract.py` ใหม่ · ปรับ test ล้าสมัย 2 ข้อ

**tests: 211 → 246 ผ่านทั้งหมด**

### 🔴 bug ที่พบจากไฟล์จริงระหว่างทำ และแก้แล้ว

| # | อาการ | ผลกระทบก่อนแก้ |
|---|---|---|
| 1 | **หัวตารางสองแถว** ของบทบาท `8.` (`B3` กับ `C4..G4`) | อ่านได้ปี 2567 ปีเดียว · record ถูกติดป้ายปีผิดทั้งหมด · ค่าอีกห้าปี**หายเงียบ** — **26 → 156 record** |
| 2 | ชีตที่ไม่มีคอลัมน์หน่วยรายแถว | หน่วยเป็น `UNRESOLVED` ทั้งชีต · แก้ด้วยการประกาศระดับชีต **แต่ห้ามใช้กับชีตที่มีคอลัมน์หน่วยจริง** มิฉะนั้นจะกลบ defect ของแถวที่หน่วยผิด |
| 3 | `agency_name` ถูกเขียนทับโดยชีตหลัง | แฟ้ม 21016 ได้ชื่อหน่วยงานเป็น *"โครงการ : โครงการพัฒนาบุคลากร…"* ⇒ provenance ของทุก record ในแฟ้มผิด |
| 4 | `raw_unit_cell` ชี้คอลัมน์ `B` ที่เป็น**ค่าเงิน** | ผู้ตรวจย้อนกลับเห็นตัวเลข `820.1643` แทนข้อความประกาศหน่วย |

ทุกข้อมี regression test กำกับแล้ว

### 🔴 silent failure ใหม่ — `FM-12` เลขข้อชีตแผนงานเปลี่ยนความหมายระหว่างปี

| | FY2569 | FY2570 |
|---|---|---|
| 21016 `7.3` | แผนงานยุทธศาสตร์**ส่งเสริมความสัมพันธ์ระหว่างประเทศ** | แผนงานยุทธศาสตร์**เสริมสร้างให้คนมีสุขภาวะที่ดี** |
| 21016 `7.4` | แผนงานยุทธศาสตร์**เสริมสร้างให้คนมีสุขภาวะที่ดี** | แผนงาน**บูรณาการรัฐบาลดิจิทัล** |

หน่วยงาน 21011 เกิดอาการเดียวกันที่ `7.3`

⇒ จับคู่ด้วยเลขข้อจะเทียบ **คนละแผนงาน** เข้าด้วยกันโดยไม่มีสัญญาณผิดพลาดใด
และจะพลาดคู่ที่เป็นแผนงานเดียวกันแต่ถูกเรียงเลขใหม่

**วิธีแก้:** ยุบเลขข้อของกลุ่ม `7.x` ทิ้ง ใช้ **ชื่อแผนงาน/โครงการ** เป็นตัวระบุ
โดยแยกชั้นแผนงาน (`SECTION_07_PLAN`) จากชั้นโครงการ (`SECTION_07_PROJECT`)
⇒ เพิ่มฟิลด์ **`section_title_norm`** เข้า `T1BKey` · **รอ Gift อนุมัติก่อน freeze**

### เอกสารที่สร้าง

`09_RESEARCH_BRIDGE/T1B_EXTRACT_SAMPLE_RECORDS.md` — จำนวน record ต่อไฟล์/ต่อบทบาท
+ ตัวอย่าง canonical record 9 รายการครบทุกประเภทที่ Gift ขอ + ผลตรวจกับ key spec

### สิ่งที่ **ไม่ได้แตะ**

`redbook/t1/` · `FlatDataTableAdapter` · `MinistryPdfAdapter` · raw results
· Evidence Index · Chapter 4 · Human Review workbooks · Audit Trail · `docs/` ของ Bo
· ไฟล์ต้นทาง `T1B` (มี test ตรวจแฮชก่อน/หลัง `extract()`)
· ไฟล์ค้างของสายอื่นใน `reviewpack/` — **ไม่ใช้ `git add -A`**

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — EXTRACT MILESTONE COMPLETE`
