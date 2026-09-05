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

---

## `HL-006` — remote สำหรับโค้ด · key stability audit · `RES-D-54`/`SYS-D-33` · FM-12

| | |
|---|---|
| **วันที่** | 1 กันยายน 2569 |
| **ผู้ทำ** | Giho (Claude) |
| **สั่งโดย** | Gift — คำตัดสิน 4 ข้อ |
| **ป้าย** | `EVIDENCE` · `ENGINEERING OBSERVATION` · `RISK` · `DECISION REQUIRED FROM GIFT` |

### ① `Q-03` — สร้าง private remote แล้ว ✅

| repo | URL | visibility |
|---|---|---|
| System SSOT | `github.com/Netthip/redbook-verify` | **PRIVATE** |
| Research SSOT | `github.com/Netthip/redbook-verify-is` | **PRIVATE** |

**ตรวจก่อน push:** ไม่มีไฟล์ข้อมูลอยู่ในประวัติของทั้งสอง repo แม้แต่ commit เดียว
· `.gitignore` ทำงานตามเดิม · ขนาด `.git` = 1.7 MB ต่อ repo

**ตรวจหลัง push**

| รายการ | ผล |
|---|---|
| `redbook-verify` main | ✅ `6dc63d2b…` ตรงกัน |
| `redbook-verify` `t1b/fy2570-mvp` | ✅ ตรงกัน |
| tag `t1-frozen-1.0.0` → commit | ✅ **`49fbb2e0c1d6…`** ตรงกับ Evidence Index |
| tag `phase-0-1-baseline` | ✅ ตรงกัน |
| `redbook-verify-is` main + 4 branch (incident/integration) | ✅ ตรงกันทุก branch |
| tag `is-v3-redbook-baseline` | ✅ ตรงกัน |
| ไฟล์ข้อมูลบน remote | ✅ **ไม่มี** (ตรวจ 121 + 76 รายการ) |

**ไม่ squash ไม่ rewrite history** — push ด้วย `--all` และ `--tags` ตามที่มีจริง

### ② key stability audit — ผ่านหลังแก้ bug จริงสองจุด

> ### ✅ `NO UNRESOLVED COLLISION AFFECTING IDENTITY`

**รอบแรก audit ล้ม** — collision 100 · collapse 1 · supporting/main ชน 19
ตรวจแล้วพบว่าเป็น **bug จริงในโค้ดสองจุด** และเกณฑ์ตรวจของ audit เองผิดสองข้อ

| # | bug จริง | ผลก่อนแก้ |
|---|---|---|
| 1 | `parse_hierarchy` ใช้ **การย่อหน้า** เป็นเงื่อนไขความเป็นลูก แต่แฟ้ม**ระดับกระทรวงไม่ย่อหน้า** | `เงินงบประมาณ` ใต้หัวข้อ `1.` กับ `2.` ได้คีย์เดียวกัน — **100 collision** |
| 2 | `classify_sheet` ใช้ `merged_count` เป็นเกณฑ์ `COVER` | ชีต `bพฐ` ถูกจัดคนละ class ในคนละแฟ้ม |

ผลหลังแก้: collision **0** · collapse **0** · `document_level` **0** · supporting/main **0**
เหลือ **false-split candidate 2 คู่** ที่ต้องให้ Gift ตัดสิน (ไม่ใช่ collision ของ identity)

รายงานเต็ม: `09_RESEARCH_BRIDGE/T1B_KEY_STABILITY_AUDIT.md`

### ③ `RES-D-54` / `SYS-D-33` — บันทึกแล้วแบบ forward-only

> ### `T1B PRODUCT TRACK AUTHORIZED — POST-FREEZE AND ISOLATED FROM FROZEN T1A EVALUATION`

ขอบเขตบังคับ 8 ข้อ ครบตามที่ Gift กำหนด · ผูก test ฝั่งระบบ 6 จุดใน `SYS-D-33`
· **เลขว่างถัดไป `RES-D-55` / `SYS-D-34`**

### ④ `FM-12` — เพิ่มเข้า baseline แล้ว (รวม **12 failure modes**)

regression 5 ข้อ ครบสามแบบที่ Gift กำหนด — เลขข้อเหมือนแต่คนละแผน (ห้าม match)
· เลขข้อต่างแต่แผนเดียวกัน (match ได้) · title ที่ฝังปีงบประมาณ (ตัดปีออกโดยไม่ทำลาย identity)

### commit

| repo | commit |
|---|---|
| `redbook-verify` branch `t1b/fy2570-mvp` | `c50321b` |
| `redbook-verify-is` main | `34092ff` |

**tests: 246 → 251 ผ่านทั้งหมด**

### สิ่งที่ **ไม่ได้แตะ**

`redbook/t1/` · `FlatDataTableAdapter` · `MinistryPdfAdapter` · raw results · Evidence Index
· Chapter 4 · Human Review workbooks · Audit Trail · `docs/` ของ Bo · ไฟล์ต้นทาง `T1B`
· ไฟล์ค้างของสายอื่นใน `reviewpack/` — **ไม่ใช้ `git add -A`**
· **ไม่ squash หรือ rewrite git history เพื่อทำ remote**

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — CODE REMOTE AVAILABLE`

---

## `HL-007` — ทาง (ค) · freeze `t1b-key-0.1.0` · matching + compare

| | |
|---|---|
| **วันที่** | 1 กันยายน 2569 |
| **ผู้ทำ** | Giho (Claude) |
| **สั่งโดย** | Gift (ยืนยันตาม `BO REVIEW COMPLETE`) |
| **commit** | `redbook-verify` branch `t1b/fy2570-mvp` → **`572c2ee`** |

### ① ทาง (ค) — semantics ของเลขลำดับโครงการ

| ข้อกำหนด | สถานะ |
|---|---|
| ใช้ชื่อหลัง `:` เป็น semantic identity เฉพาะ `SECTION_07_PROJECT` | ✅ |
| `project_ordinal_raw` แยกเป็น comparison/provenance ไม่ใช่ identity | ✅ |
| ชื่อตรงแต่เลขลำดับเปลี่ยน → จับคู่ได้ **และออก finding** | ✅ `PROJECT_ORDINAL_CHANGED` |
| **ห้ามใช้ fuzzy similarity เป็น auto-match** | ✅ คีย์ใช้ความเท่ากันตรงตัว · มี test บังคับ |
| ชื่อซ้ำภายใน plan เดียวกัน → `AMBIGUOUS / HUMAN REVIEW` ห้าม collapse | ✅ `_flag_ambiguous_projects()` |

**เพิ่มเติมที่จำเป็นต่อความถูกต้อง:** `parent_plan_norm` เข้า identity —
โครงการชื่อเดียวกันอาจอยู่ใต้คนละแผนงาน และเลขข้อของแผนแม่ก็เปลี่ยนข้ามปี

### ② audit rerun — ผ่านครบ 8 ข้อ

collision **0** · false-split **0** (จาก 2) · collapse **0** · `document_level` **0**
· supporting/main **0** · ambiguous collapse **0** · จับคู่ข้ามเลขลำดับ **2 คู่**

**เงื่อนไข freeze ที่ Gift กำหนด ครบทั้ง 4** ⇒ 🔒 **`t1b-key-0.1.0` FROZEN 2569-09-01**

### ③ `classify_sheet` — `DATASET-BOUNDED HEURISTIC` + fail-safe

ระบุชัดในโค้ดว่าเกณฑ์ `index == 0` ยืนยันกับ **6 แฟ้มปัจจุบันเท่านั้น**
และเพิ่ม fail-safe: หลักฐานไม่พอ → `UNKNOWN` **ไม่เดา**

### ④ `FOCUSED DOCUMENTATION FIX`

แก้ path `.data\review\...` ที่แตกบรรทัดใน `docs/DECISIONS_LOG.md`
🔴 **บันทึกไว้ว่า defect มาจาก commit `397f293` (27 ส.ค.) อยู่บน `main` ก่อนสาย T1B แตก branch**
(merge-base `6dc63d2b`) ⇒ **ไม่ใช่ผลจาก T1B implementation**
แก้เฉพาะตำแหน่งตัดบรรทัด · ไม่เปลี่ยนถ้อยคำ path แฮช หรือเลขรุ่น

### ⑤ matching → compare

| โมดูล | สาระ |
|---|---|
| `redbook/t1b/matching.py` | จับคู่ด้วย `(T1BKey, fiscal_year)` แบบตรงตัว · ปีที่มีข้างเดียวรายงานแยก · record กำกวมเข้าคิวมนุษย์ · **`accounted()` พิสูจน์ว่าไม่มี record หายเงียบ** |
| `redbook/t1b/compare.py` | finding 13 ชนิด · ทุก finding ชี้กลับชีต/เซลล์/ค่าดิบทั้งสองฝั่ง · **ห้ามเทียบข้ามหน่วย** |

**ผลกับไฟล์จริง 3 คู่ — accounting ตรงทุกคู่**

| คู่ | matched | baseline only | current only | human | unmapped | accounting |
|---|---:|---:|---:|---:|---:|---|
| 21011 | 195 | 60 | 50 | 10 | 236 | ✅ 746 = 746 |
| 21016 | 202 | 52 | 54 | 15 | 509 | ✅ ตรง |
| 21000 (กระทรวง) | 115 | 105 | 115 | 25 | 409 | ✅ ตรง |

**🔑 หลักฐานว่าออกแบบถูก**

```
AMOUNT_DECREASED · ปี 2570 · 'รวมทั้งสิ้น' (SECTION_05)
   55.0612 → 53.3934   ผลต่าง −1.6678 ล้านบาท
   baseline Sheet5!E6   ·   current Sheet5!D6
```

ปีเดียวกันแต่ **คนละเซลล์** — ถ้าเทียบตามตำแหน่งจะได้ `E6↔E6` คือ ปี 2570 เทียบ ปี 2571 ⇒ ตัวเลขผิดทั้งฉบับ

### tests: 251 → **274 ผ่านทั้งหมด**

### สิ่งที่ **ไม่ได้แตะ**

`redbook/t1/` · `FlatDataTableAdapter` · `MinistryPdfAdapter` · raw results · Evidence Index
· Chapter 4 · Human Review workbooks · Audit Trail · `docs/` ของ Bo · ไฟล์ต้นทาง `T1B`
· ไฟล์ค้างของสายอื่นใน `reviewpack/` · **ยังไม่เริ่ม roll-up/reconciliation ตามที่สั่ง**

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — MATCHING AND COMPARE COMPLETE`

---

## `HL-008` — 3 review fixes + map layout ชีต `7.x`

| | |
|---|---|
| **วันที่** | 1 กันยายน 2569 |
| **ผู้ทำ** | Giho (Claude) |
| **สั่งโดย** | Gift |
| **commit** | `redbook-verify` branch `t1b/fy2570-mvp` → **`0ba32aa`** |

### ① review fixes ปิดครบ 3 ข้อ

| # | สิ่งที่แก้ |
|---|---|
| 1 | `SidedRecord` + `_one_sided()` — record ฝั่งเดียวคงไว้ว่ามาจาก baseline หรือ current |
| 2 | `PROJECT_ORDINAL_CHANGED` มี `baseline_location` + `current_location` + `fiscal_year` แล้ว |
| 3 | `YearScope` + `scope_of()` — ปีที่เทียบได้คิด **รายขอบเขตชีต** ไม่ใช่ union ระดับสมุดงาน |

### ② map `7.x` — 5 ข้อค้นพบ

| # | เรื่อง |
|---|---|
| 1 | ชีตหนึ่งมี**ตารางรายปีหลายชุด** (7.x มีทั้งตารางงบรายจ่ายและตารางรายปี) |
| 2 | **คอลัมน์หน่วยนับไม่คงที่** — บทบาท `5.` ใช้ `B` แต่ `7.x` ใช้ `F` |
| 3 | 🔴 **`Sheet7_1` มี `A1` เป็นหัวบท `7.` แต่แผนจริงอยู่ `A2`** — ถ้าไม่แก้ ข้อมูลแผนบุคลากรภาครัฐไม่ถูกจับคู่ข้ามปีเลย |
| 4 | แถวหัวตารางที่มีป้ายปีเพียงป้ายเดียว (`B3 = ปี 2567`) ต้องรวมเข้ามา |
| 5 | การหาข้อความประกาศหน่วยจับคำ `หน่วย` ลอย ๆ ไปโดน `"…หน่วยงาน"` |

### ③ ผล

| ตัวชี้วัด | ก่อน → หลัง |
|---|---|
| `VALUE` (21016 FY70) | 262 → **434** |
| `UNMAPPED` (21016 FY70) | 272 → **200** |
| `matched` (21016) | 202 → **278** |
| unique keys ต่อไฟล์ | 51–61 → **73–118** (collision ยัง **0**) |
| tests | 278 → **283 passed** |

**`PROJECT_ORDINAL_CHANGED` ยิงจากไฟล์จริงแล้ว — 15 finding ใน 21016**
`Sheet7.4.2` (`โครงการที่ 2`) จับคู่กับ `Sheet7.3.3` (`โครงการที่ 3`)
คนละชื่อชีต คนละเลขข้อ คนละเลขลำดับ แต่เป็นโครงการเดียวกัน

### ④ `t1b-key-0.1.0` — **ไม่ถูกเปลี่ยน**

audit rerun ผ่านครบ 8 ข้อด้วยคีย์เดิม · **ไม่พบหลักฐานว่าคีย์ที่ freeze แล้วไม่พอหรือผิด**
⇒ ไม่เสนอ key version ใหม่

รายงานเต็ม: `09_RESEARCH_BRIDGE/T1B_7X_MAPPING_REPORT.md`

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — 7.X MAPPING COMPLETE`

---

## `HL-009` — แก้ ordinal overcount + map ตารางจำแนกตามงบรายจ่าย

| | |
|---|---|
| **วันที่** | 1 กันยายน 2569 |
| **ผู้ทำ** | Giho (Claude) · **สั่งโดย** Gift |
| **commit** | `redbook-verify` branch `t1b/fy2570-mvp` → **`cbc08b0`** |

### ① `PROJECT_ORDINAL_CHANGED` overcount — **15 → 2**

dedupe เดิมใช้ `T1BKey` เต็ม (มี `row_label_norm`) ⇒ finding หนึ่งใบต่อหนึ่งแถว
แก้เป็น dedupe ที่ตัวโครงการ · ผลตรงกับโครงการที่ถูกเรียงเลขใหม่จริง 2 รายการ

### ② map ตารางจำแนกตามงบรายจ่าย

`find_category_tables()` — หมวดต้องเรียง **แนวนอน** ≥ 2 หมวด
เพื่อไม่จับผิดกับชีต `7.1` ที่มีหมวดเป็น **แถว**

> 🔒 **`T1BKey` ไม่ถูกเปลี่ยน** — `budget_category` เป็น comparison attribute
> เหมือน `fiscal_year` · match signature ขยายเป็น
> `(T1BKey, fiscal_year, budget_category)`

**ผลข้างเคียงที่ดี:** ปลดล็อกชีตบทบาท `6.` ซึ่งเดิม `UNMAPPED` ทั้งชีตเพราะไม่มีป้ายปี

### ③ ผล rerun 6 workbook

| ตัวชี้วัด | ก่อน → หลัง |
|---|---|
| `VALUE` (21016 FY70) | 434 → **556** |
| `UNMAPPED` (21016 FY70) | 200 → **158** |
| `matched` (21016) | 278 → **332** |
| category records | **75 / 120 / 122** |
| `PROJECT_ORDINAL_CHANGED` | 15 → **2** |
| unique keys ต่อไฟล์ | 73–118 → **58–141** (collision ยัง **0**) |
| tests | 283 → **291 passed** |

accounting ตรงทุกคู่ · audit ผ่านครบ 8 ข้อด้วยคีย์ `t1b-key-0.1.0` เดิม

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — BUDGET CATEGORY MAPPING COMPLETE`

---

## `HL-010` — explicit `comparison_axis` + canonical category + unknown fail-safe

| | |
|---|---|
| **วันที่** | 1 กันยายน 2569 |
| **ผู้ทำ** | Giho (Claude) · **ตอบ** `BO REVIEW COMPLETE — CONDITIONAL PASS` |
| **commit** | `redbook-verify` branch `t1b/fy2570-mvp` → **`048419d`** |

### ① `comparison_axis` เป็น explicit แล้ว

```
comparison_axis = FISCAL_YEAR | BUDGET_CATEGORY | UNRESOLVED
match signature = (T1BKey, comparison_axis, fiscal_year, budget_category)
```

บังคับ **XOR** ผ่าน `T1BRecord.axis_valid` — แกนไม่ถูกต้อง ⇒ `UNRESOLVED / HUMAN REVIEW`
🔒 **`T1BKey` ที่ freeze แล้วไม่ถูกเปลี่ยน**

### ② canonical category + raw provenance

โมดูลใหม่ `redbook/t1b/categories.py` — `PERSONNEL` · `OPERATING` · `INVESTMENT`
· `SUBSIDY` · `OTHER_EXPENDITURE` · `TOTAL` · `UNRESOLVED`
เก็บ `budget_category_raw` ไว้เสมอ

### ③ 🔴 fail-safe — bug ที่ Bo จับได้ และยืนยันแล้วว่าเป็นจริง

เดิม `find_category_tables()` เก็บเฉพาะคอลัมน์ที่ resolve สำเร็จ
extractor จึง iterate เฉพาะคอลัมน์นั้น ⇒ **คอลัมน์หมวดใหม่ถูกข้ามโดยไม่สร้าง HUMAN REVIEW**

ยืนยันด้วยกรณีจำลอง — คอลัมน์ `งบชดใช้เงินคงคลัง` ค่า `99.0` **หายเงียบจริง**

แก้เป็น `CategoryColumn` เก็บ **ทุกคอลัมน์ที่มีหัวข้อความ** ตั้งแต่หมวดที่รู้จักคอลัมน์แรก
หมวดที่ resolve ไม่ได้ → `UNRESOLVED` + raw header + `HUMAN REVIEW` · **ห้ามเดาหมวดใกล้เคียง**

### ④ ผล rerun 6 workbook

| ตัวชี้วัด | ค่า |
|---|---|
| unresolved-category | **0 ทุกแฟ้ม** (ทุกหมวดในไฟล์จริงรู้จักหมด) |
| category counts | `PERSONNEL` 28 · `OPERATING` 79 · `INVESTMENT` 64 · `SUBSIDY` 84 · `OTHER_EXPENDITURE` 68 · `TOTAL` 69 |
| matched | 255 / 332 / 115 · accounting **ตรงทุกคู่** |
| `PROJECT_ORDINAL_CHANGED` | **2** สำหรับ 21016 (ตามที่ Bo กำหนด) |
| audit | ผ่านครบ **8 ข้อ** · ปรับ signature ให้รวม `comparison_axis` |
| tests | 291 → **306 passed** |

regression 9 ข้อที่ Bo กำหนด — **ครบทั้งหมด** รวม test end-to-end ที่พิสูจน์ว่า
คอลัมน์หมวดไม่รู้จักไม่หายจริง

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — CATEGORY AXIS / PROVENANCE PATCH COMPLETE`

---

## `HL-011` — ปิด boundary 3 ข้อจาก `BO REVIEW — CONDITIONAL PASS`

**วันที่** 2 กันยายน 2569 · **ผู้ทำ** Giho · **commit** `45d858b` (สาขา `t1b/fy2570-mvp`)

Bo ให้ `CONDITIONAL PASS` และ **ยังไม่ปลด** roll-up / reconciliation
โดยชี้ว่ามีสามจุดที่ `306 passed` รอบก่อน **ยังพิสูจน์ไม่ได้**

🔴 **ตรวจก่อนแก้ทุกข้อ** — ① และ ② เป็นข้อบกพร่องจริง ส่วน ③ ถูกต้องอยู่แล้ว
จึงเป็นการ **เพิ่มการพิสูจน์ ไม่ใช่การแก้** · ห้ามเขียนย้อนหลังว่า ③ เคยเสีย

### ① หัวคอลัมน์ที่ไม่รู้จักซึ่งวางอยู่ **ก่อน** หมวดที่รู้จักคอลัมน์แรก

การแก้ใน `HL-010` เก็บคอลัมน์ *"ตั้งแต่หมวดที่รู้จักคอลัมน์แรกเป็นต้นไป"*
⇒ คอลัมน์ที่อยู่ **ซ้าย** ของหมวดแรกยังหายเงียบอยู่

พิสูจน์ก่อนแก้ — หัวคอลัมน์ `งบชดเชยพิเศษ` ที่ index 1 (ก่อน `งบดำเนินงาน`)
**ไม่ปรากฏในผลลัพธ์เลย** ⇒ ค่าใต้คอลัมน์นั้นหายโดยไม่มี `HUMAN REVIEW`

**แก้:** ยึด **ขอบเขตตาราง** แทนจุดเริ่มที่หมวดแรก
เขตค่า = ทุกคอลัมน์ที่อยู่ **ขวาของคอลัมน์ป้ายรายการ** ข้ามคอลัมน์โครงสร้าง (`หน่วยนับ`)
ยังต้องมีหมวดที่รู้จักอย่างน้อยหนึ่งคอลัมน์จึงนับเป็นตารางชนิดนี้ —
มิฉะนั้นแถวหัวใด ๆ ที่มีข้อความจะกลายเป็นตารางหมวดไปหมด

**ยืนยันกับแฟ้มจริงก่อนเปลี่ยน** — สำรวจ 6 แฟ้ม พบตารางหมวด **19 ตาราง**
สิ่งเดียวที่อยู่ซ้ายของหมวดแรกคือ `'ผลผลิต / โครงการ'` ที่ **คอลัมน์ 0** (คอลัมน์ป้าย)
⇒ ผลของแฟ้มจริง **ไม่เปลี่ยน** และไม่มีรายการปลอมเข้าคิวมนุษย์

### ② หัวคอลัมน์ที่ไม่รู้จักหลายคอลัมน์ถูกบีบเป็น `UNRESOLVED` เดียวกัน

พิสูจน์ก่อนแก้ — `งบชดใช้เงินคงคลัง` (99.0) กับ `งบภารกิจเฉพาะกิจ` (88.0)
ในแถวเดียวกันให้ **ลายเซ็นการจับคู่ที่เท่ากันทุกประการ**

นี่คือจุดที่ Bo กังวลที่สุด และถูกต้อง — ความเสียหายเปลี่ยนจาก *"ข้อมูลหาย"*
เป็น *"ข้อมูลสองชนิดถูกจับคู่ผิด"* ซึ่ง **อันตรายกว่า** เพราะผลลัพธ์ยังดูสมเหตุสมผล

**แก้สองชั้น — ใช้ทั้งสองทางที่ Bo เสนอ ไม่เลือกอย่างใดอย่างหนึ่ง**

1. `_signature()` เพิ่มตัวแยกหัวคอลัมน์ดิบ **เฉพาะกรณี `UNRESOLVED`**
   หมวดที่รู้จักยังเทียบด้วย canonical code เหมือนเดิม จึงไม่กระทบพฤติกรรมเดิม
   เป็นความเท่ากันแบบตรงตัว **ไม่ใช่ fuzzy similarity**
2. `_split()` กัน `UNRESOLVED` ออกจากการจับคู่อัตโนมัติ **โดยตรง**
   และ `T1BRecord.needs_review` บังคับที่ระดับ record ด้วย
   ⇒ ด่านนี้ **ไม่พึ่งธง `uncertainty`** จึงยังกันได้แม้เส้นทางสกัดในอนาคตลืมติดธง

### ③ semantic truth table ของ `axis_valid` — **ตรวจแล้วถูกต้องอยู่ก่อนแล้ว**

ทดสอบครบ 8 กรณีรวมกรณีที่ Bo ยกมา (`FISCAL_YEAR` + `budget_category` โดยไม่มีปี)
ทุกกรณีให้ผลตรงตามที่ควรเป็น **ไม่มีการแก้โค้ด** — เพิ่ม 10 กรณีเป็น regression
เพื่อ **ล็อกพฤติกรรมไว้** ไม่ให้ถอยหลังในอนาคต

### ผลข้างเคียงที่พบระหว่างเขียน test

เหตุผลของ finding `AMBIGUOUS` จะ **ว่างเปล่า** เมื่อ record ไม่มีธง `uncertainty`
⇒ เพิ่ม `_review_reason()` ให้ระบุหัวคอลัมน์ดิบเสมอ · คิวมนุษย์ต้องอ่านรู้เรื่อง

### การตรวจสอบ

| รายการ | ผล |
|---|---|
| tests | 306 → **330 passed** (ใหม่ 24 ข้อ) |
| **พิสูจน์ว่า test กัดจริง** | stash โค้ดที่แก้ออก แล้วรัน test ใหม่ ⇒ **ล้มเหลว 7 ข้อ** |
| แฟ้มจริง 6 แฟ้ม | `UNRESOLVED` = **0** ทุกแฟ้ม |
| หมวด canonical | `SUBSIDY` 84 · `OPERATING` 79 · `TOTAL` 69 · `OTHER_EXPENDITURE` 68 · `INVESTMENT` 64 · `PERSONNEL` 28 — **เท่าเดิมทุกตัว** |
| matched | 255 / 332 / 115 · accounting **ตรงทุกคู่** |
| `PROJECT_ORDINAL_CHANGED` | **2** สำหรับ 21016 |
| key stability audit | ผ่าน **8/8** |
| 🔒 `t1b-key-0.1.0` | **ไม่เปลี่ยน** · matching `0.4.0` → `0.5.0` |

### ไฟล์ที่แก้ (`45d858b`)

| ไฟล์ | สิ่งที่เปลี่ยน |
|---|---|
| `redbook/t1b/header.py` | `_category_columns()` ยึดขอบเขตตาราง + `CATEGORY_LABEL_COLUMN` |
| `redbook/t1b/matching.py` | `_category_discriminator()` · `Signature` · ด่านกัน `UNRESOLVED` ใน `_split()` |
| `redbook/t1b/records.py` | `needs_review` บังคับที่ระดับ record |
| `redbook/t1b/compare.py` | `_review_reason()` — เหตุผลในคิวต้องไม่ว่าง |
| `tests/test_t1b_bo_boundary.py` | **ใหม่** · regression 24 ข้อ |

**ไม่ได้แตะ:** frozen Evidence Index · Human Review workbooks · raw results · Chapter 4 ·
production engine · `FlatDataTableAdapter` · เส้นทาง T1A ทั้งหมด · `T1BKey`

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — BOUNDARY CASES CLOSED`
> ยังไม่เข้า roll-up / reconciliation จนกว่าจะได้ `FINAL PASS`

---

## `HL-012` — detector contract `known ≥ 1` ทุกชั้น + true end-to-end ถึง `Finding`

**วันที่** 2 กันยายน 2569 · **ผู้ทำ** Giho · **commit** `50a97de` (สาขา `t1b/fy2570-mvp`)

Bo ให้ `CONDITIONAL PASS` รอบสอง — รับรองงาน `HL-011` แล้ว แต่ชี้อีกสองจุด
🔴 **ตรวจแล้วเป็นจริงทั้งคู่**

### ① contract ไม่ตรงกันสองชั้นใน `header.py`

`_category_columns()` รับ `known ≥ 1` แต่เส้นทางจริงต้องผ่าน
`_category_header_rows()` ซึ่งบังคับ `MIN_CATEGORY_LABELS = 2`
⇒ ตาราง `unknown | known ×1 | unknown` ถูกตัดทิ้ง **ทั้งตาราง**
ก่อนถึงชั้นที่แก้ไว้ใน `HL-011` และค่าทุกคอลัมน์หายเงียบ

**พิสูจน์ก่อนแก้**

```
หัวตาราง : ['กิจกรรม', 'งบภารกิจเฉพาะกิจ', 'งบลงทุน', 'งบชดใช้เงินคงคลัง']
_category_header_rows() -> []          ← ตัดทิ้งตั้งแต่ชั้นแรก
_category_columns()     -> [(1,'UNRESOLVED'), (2,'INVESTMENT'), (3,'UNRESOLVED')]
find_category_tables()  -> 0 ตาราง     ← ค่า 77.0 / 99.0 หายเงียบ
```

ชั้นล่างทำถูกอยู่แล้ว แต่ไม่เคยถูกเรียก — นี่คือลักษณะเดียวกับ silent failure
ที่ไล่จับมาตลอด เพียงแต่ครั้งนี้เกิดจาก **contract สองชั้นไม่ตรงกันเอง**

**แก้:** `MIN_KNOWN_CATEGORIES = 1` พร้อมตัวกันความสับสนใหม่แทนการนับหมวด

* หมวดที่รู้จักต้องอยู่ใน **เขตค่า** (คอลัมน์ ≥ 1) ไม่ใช่คอลัมน์ป้าย
* เขตค่าต้องมีคอลัมน์หัวข้อความ ≥ `MIN_CATEGORY_HEADER_TEXTS` (2)
* แถวที่เป็นหัวตาราง **รายปี** อยู่แล้ว ตัดออกที่ชั้นนี้เลย เพื่อให้ contract
  เดียวกันไม่ว่าจะเรียกผ่าน adapter หรือเรียกตรง

🔴 **ข้อค้นพบที่เปลี่ยนวิธีแก้** — ทางที่ตรงไปตรงมาที่สุดคือใช้เงื่อนไข
*"แถวหัวตารางต้องไม่มีตัวเลข"* แต่ตรวจแฟ้มจริงก่อนแล้วพบว่า
หัวตาราง **2 ใน 19 แถวมีตัวเลขปนในเขตค่า** (`Sheet7.2` คอลัมน์ 12 = `1`
และ `Sheet7.3.1` คอลัมน์ 12 = `0` ของ FY2570 · 21016)
เงื่อนไขนั้นจะ **ตัดตารางจริงทิ้ง** จึงไม่ใช้ และเขียน test กันไว้ถาวร

**ตรวจหลังแก้:** แฟ้มจริงยังตรวจพบหัวตาราง **19 แถวเท่าเดิม**
การกระจายจำนวนหมวดต่อหัวตารางเท่าเดิม (`5 หมวด` 15 แถว · `6 หมวด` 4 แถว)

### ② ยังไม่มี test เดียวที่ไล่ครบ `extract → match → compare → Finding`

ของเดิมแบ่งพิสูจน์เป็นช่วง — `extract` จบที่ record · การพิสูจน์ finding
เริ่มจาก record ที่สร้างด้วยมือ ⇒ **ไม่มีหลักฐานว่าสายงานทั้งเส้นต่อกันจริง**

เพิ่มสอง test ที่เริ่มจาก workbook จำลองไปจนถึง `Finding` ยืนยันว่า
`77.0` กับ `99.0` ไม่หาย **ไม่สลับกัน** มี cell reference ของตัวเอง
`requires_human_decision` เป็นจริง และไม่หลุดไปอยู่ใน `matched`/`baseline_only`/`current_only`

### การตรวจสอบ

| รายการ | ผล |
|---|---|
| tests | 330 → **340 passed** (ใหม่ 10 ข้อ) |
| **พิสูจน์ว่า test กัดจริง** | เทียบ `45d858b` ⇒ ล้มเหลว **3 ข้อ** · เทียบ `048419d` ⇒ ล้มเหลว **11 ข้อ** |
| หัวตารางในแฟ้มจริง | **19** เท่าเดิม |
| `UNRESOLVED` | **0** ทุกแฟ้ม |
| หมวด canonical | `SUBSIDY` 84 · `OPERATING` 79 · `TOTAL` 69 · `OTHER_EXPENDITURE` 68 · `INVESTMENT` 64 · `PERSONNEL` 28 — เท่าเดิมทุกตัว |
| matched | 255 / 332 / 115 · accounting ตรงทุกคู่ |
| `PROJECT_ORDINAL_CHANGED` | **2** (21016) |
| key stability audit | ผ่าน **8/8** |
| 🔒 `t1b-key-0.1.0` | **ไม่เปลี่ยน** |

### ไฟล์ที่แก้ (`50a97de`)

| ไฟล์ | สิ่งที่เปลี่ยน |
|---|---|
| `redbook/t1b/header.py` | `_is_category_header_row()` · `MIN_KNOWN_CATEGORIES` · `MIN_CATEGORY_HEADER_TEXTS` · ตัดหัวตารางรายปีออก |
| `tests/test_t1b_bo_boundary.py` | +10 ข้อ (detector contract · negative cases · e2e ถึง `Finding`) |

**ไม่ได้แตะ:** frozen Evidence Index · Human Review workbooks · raw results · Chapter 4 ·
production engine · `FlatDataTableAdapter` · เส้นทาง T1A ทั้งหมด · `T1BKey`

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — DETECTOR CONTRACT + TRUE E2E COMPLETE`
> ยังไม่เข้า roll-up / reconciliation จนกว่าจะได้ `FINAL PASS`

---

## `HL-013` — 🟢 `BO FINAL PASS` · ปลด roll-up / reconciliation

**วันที่** 2 กันยายน 2569 · **บันทึกโดย** Giho ตามคำสั่งของ Bo ที่ Gift ถ่ายทอด
**ประเภท** บันทึกคำตัดสินของ gate — **ไม่ใช่**คำตัดสินระดับทะเบียน

> ### สถานะที่ได้รับ (ถ้อยคำที่บังคับ ห้ามย่อ ห้ามแปลง)
>
> ```
> CATEGORY AXIS / PROVENANCE — FINAL PASS
> DETECTOR CONTRACT — FINAL PASS
> TRUE END-TO-END PROVENANCE — FINAL PASS
> ROLL-UP / RECONCILIATION — UNBLOCKED
> ```

### จุดอ้างอิงที่คำตัดสินผูกไว้ — **ตรวจแล้วตรงทั้งคู่**

| repo | commit ที่ Bo อ้าง | ตรวจจริง |
|---|---|---|
| `redbook-verify` (System SSOT) | `50a97de2fc57aacf1ceceb95c3eb8562172bba2c` | ✅ ตรงกับ `HEAD` ของ `t1b/fy2570-mvp` |
| repo สะพาน | `d0d49ae` | ✅ ตรงกับ `HEAD` ของ `main` |

### ข้อจำกัดที่ผูกกับคำตัดสินนี้ — บังคับตลอดขั้น roll-up / reconciliation

1. รักษา `t1b-key-0.1.0` ไว้ · **ห้ามเปลี่ยนโครงสร้างคีย์**
2. `UNRESOLVED` **ห้ามเข้า** automated match หรือ automated roll-up
3. ต้องรักษา **raw provenance** และ **HUMAN REVIEW** ทุกชั้น
4. ค่าทุก record ต้องถูก **accounted เสมอ** · ห้าม silent-drop
5. ใช้ผล **6 workbook รอบนี้เป็น regression baseline**
6. ยังไม่แตะ frozen Evidence Index · raw results · Human Review workbooks ·
   Chapter 4 · production engine — นอกขอบเขต roll-up / reconciliation

### `regression baseline` ที่ข้อ 5 อ้างถึง (ตรึงไว้ ณ `50a97de`)

| ตัวชี้วัด | ค่าฐาน |
|---|---|
| หัวตารางหมวดที่ตรวจพบในแฟ้มจริง | **19** |
| `UNRESOLVED` | **0** ทุกแฟ้ม |
| หมวด canonical | `SUBSIDY` 84 · `OPERATING` 79 · `TOTAL` 69 · `OTHER_EXPENDITURE` 68 · `INVESTMENT` 64 · `PERSONNEL` 28 |
| matched (21011 / 21016 / 21000) | **255 / 332 / 115** |
| accounting | ตรงทุกคู่ — **972 · 1404 · 894** |
| `PROJECT_ORDINAL_CHANGED` | **2** (21016) |
| key stability audit | **8/8** |
| ชุดทดสอบ | **340 passed** |

### 🔴 ข้อจำกัดของหลักฐานที่ Bo บันทึกไว้เอง — ห้ามตัดทิ้ง

> repo ไม่มี remote CI status/workflow สำหรับ commit นี้ ดังนั้น **`340 passed`
> เป็นหลักฐานการรันในเครื่องของ Giho** แต่การตรวจโค้ดและ regression definitions
> ตรงตาม gate ที่กำหนดครบแล้ว

⇒ เวลาอ้างผลชุดนี้ต้องเขียนว่า **"ผลการรันในเครื่องผู้พัฒนา"** ไม่ใช่ *"CI ผ่าน"*

### 🔴 ช่องว่างของ audit trail ที่ต้องบันทึกไว้

`BO REVIEW — CONDITIONAL PASS` สองรอบ (รอบ boundary 3 ข้อ และรอบ detector 2 ข้อ)
**ไม่ได้ถูกโพสต์ลง `BRIDGE-001`** — Gift ถ่ายทอดผ่านการสนทนาโดยตรง
สาระของทั้งสองรอบสรุปไว้ที่ `HL-011` และ `HL-012` แล้ว แต่ **ถ้อยคำต้นฉบับยังไม่มีในระบบ**
⇒ ผู้อ่านย้อนหลังจะเห็นเกณฑ์ที่ `FINAL PASS` อ้างถึงไม่ครบ · รอ Gift ตัดสินว่าจะเติมย้อนหลังหรือไม่

### หมายเหตุเรื่องเลขทะเบียน

คำตัดสินนี้เป็น **gate ของสายตรวจสอบ (Bo)** จึงบันทึกไว้ที่ชั้นสะพานและ `BRIDGE-001`
**ไม่กิน** `RES-D-55` / `SYS-D-34` ซึ่งยังว่างอยู่
ถ้า Gift ต้องการยกระดับเป็นคำตัดสินระดับทะเบียน ให้ออกเลขคู่ถัดไปได้

### สถานะเมื่อจบรายการนี้

> ### `ROLL-UP / RECONCILIATION — UNBLOCKED`

---

## `HL-014` — roll-up / reconciliation ชุดแรก จากกฎที่พิสูจน์ได้ในแฟ้มจริง

**วันที่** 2 กันยายน 2569 · **ผู้ทำ** Giho · **commit** `3d9d5ad` (สาขา `t1b/fy2570-mvp`)

งานแรกหลัง `BO FINAL PASS` · **สำรวจแฟ้มจริงก่อนออกแบบ ไม่ตั้งกฎขึ้นเอง**

### กฎที่สำรวจแล้วพบว่า **เป็นจริง** — ใส่ไว้ในโมดูล

| กฎ | ผลกับแฟ้มจริง |
|---|---|
| `CATEGORY_SUBTOTALS_TO_TOTAL` — หมวดย่อยรวมกัน = คอลัมน์ `รวม` | **69/69 ตรง** |
| `GRAND_TOTAL_SPLITS_BY_FUNDING_SOURCE` — `รวมทั้งสิ้น` = ในงบ + นอกงบ | **30/30 ตรง** |
| `FUNDING_LINE_SUMS_TO_SHEET_SUBTOTAL` — `รวมเงินงบประมาณ` = ผลรวมแถวลูกทุกข้อ | **59/60 ตรง** |
| `GRAND_TOTAL_AGREES_ACROSS_SHEETS` — `รวมทั้งสิ้น` บทบาท 4. = บทบาท 5. | **8/8 ตรง** |

### 🔴 กฎที่สำรวจแล้ว **ไม่เป็นจริง** — จงใจไม่ใส่

**① "ผลรวมของแผนงาน `7.x` = ยอดรวมของหน่วยงาน"**

ตรวจแล้วไม่ตรงในหลายปี ตัวอย่างจริง

```
21011 FY2569  ปี 2569 ✅ ตรง : บทบาท5=58.4401  ผลรวมแผน 3 แผน=58.4401
21011 FY2569  ปี 2568 🔴 ต่าง : บทบาท5=53.2712  ผลรวมแผน 2 แผน=39.6026  ต่าง=13.6686
```

ปีที่ตรงมี **3 แผน** ปีที่ไม่ตรงมี **2 แผน** ⇒ อธิบายได้ด้วย
**แต่ละชีตครอบคลุมปีไม่เท่ากัน** ซึ่งเป็นเรื่องเดียวกับ review fix เรื่อง
"ปีที่เทียบได้คิดรายขอบเขตชีต ไม่ใช่ union ระดับสมุดงาน"
⇒ **ห้ามยืนยันอัตโนมัติ** ต้องให้มนุษย์ตัดสิน

**② "แถวลูกรวมกัน = แถวพ่อ" ในชีตบทบาท 5.**

เปิดดูโครงสร้างจริงแล้วพบว่า **แถวที่มีเลขข้อเป็นแถวโครงสร้าง ไม่มีค่าเงิน**
เงินอยู่ที่แถวลูก `เงินงบประมาณ` / `เงินนอกงบประมาณ` ⇒ ไม่มีความสัมพันธ์นี้ให้ตรวจ

🔴 **บันทึกความผิดพลาดของตัวสำรวจเองไว้ด้วย** — รอบแรกหาพ่อด้วย `row_label_norm`
อย่างเดียว แต่ป้ายอย่าง `เงินงบประมาณ` ซ้ำได้หลายแถวในชีตเดียวกัน จึงรายงานว่า
"ไม่ตรง 80 คู่" ซึ่ง **เป็นหลักฐานว่าตัวสำรวจผิด ไม่ใช่หลักฐานเรื่องข้อมูล**
เป็นความผิดพลาดชนิดเดียวกับ `parse_hierarchy` ที่เคยชนกัน 100 จุด

### ข้อจำกัดจาก `BO FINAL PASS` ที่บังคับด้วย test

* `UNRESOLVED` **ห้ามเข้า roll-up อัตโนมัติ** — ทั้งชุดไป `HUMAN_REVIEW`
  และ `computed` เป็น `None` (ไม่มีตัวเลขที่ระบบสรุปเอง) **แม้เลขจะบวกลงตัวก็ตาม**
* ห้ามบวกข้ามหน่วย · ห้ามบวกข้ามปี · หน่วยที่ยัง resolve ไม่ได้ไม่เข้าผลรวม
* ตัวตั้งทุกตัวชี้กลับเซลล์จริงได้ (`sheet` + `cell` + `row` + raw header)
* 🔒 `t1b-key-0.1.0` ไม่เปลี่ยน — โมดูลนี้อ่านอย่างเดียว

### 🔴 จุดที่ต้องให้ Gift ตัดสิน — เศษการปัดทศนิยม

พบ **1 กรณีจาก 167** ในแฟ้มจริง

```
XL_FY2569_draft-bill_21000_MOPH-summary.xlsx · ข้อ 5 · ปี 2572
รวมเงินงบประมาณ ที่ประกาศไว้ = 178,099.8550
แถวลูก 6 แถวรวมได้           = 178,099.8551
ส่วนต่าง                      = -0.0001
```

ตัวตั้งทั้ง 6 แถวชี้กลับเซลล์จริงได้ครบ (`G11` `G16` `G29` `G35` `G39` `G43`)

**ตอนนี้ทำแบบระมัดระวังที่สุดไว้ก่อน:** สถานะยังเป็น `MISMATCH` และยังขึ้นให้มนุษย์เห็น
มีเพียง **คำอธิบายประกอบ** `within_residue_bound` ว่าอธิบายด้วยการปัดทศนิยมได้
🔴 **ไม่ใช่การยกเว้น ไม่ได้กลบเป็น `OK`** — การจะถือว่าเศษระดับนี้ยอมรับได้หรือไม่
เป็นคำตัดสินของ Gift · โครงสร้างเดิมของระบบ **ไม่มีแนวคิด tolerance อยู่เลย**
ทุกค่าปัดที่ 4 ตำแหน่งแล้วเทียบแบบตรงตัว

### การตรวจสอบ

| รายการ | ผล |
|---|---|
| tests | 340 → **358 passed** (ใหม่ 18 ข้อ) |
| การกระทบยอดในแฟ้มจริง | **167** · ตรง **166** · ไม่ตรง **1** |
| regression baseline ตาม `BO FINAL PASS` ข้อ 5 | **ไม่เปลี่ยน** — `UNRESOLVED` 0 · หมวด canonical เท่าเดิม · matched 255/332/115 · accounting ตรงทุกคู่ · `ORDINAL` 2 · audit 8/8 |
| 🔒 `t1b-key-0.1.0` | ไม่เปลี่ยน |

### ไฟล์ (`3d9d5ad`)

| ไฟล์ | สิ่งที่เปลี่ยน |
|---|---|
| `redbook/t1b/rollup.py` | **ใหม่** · 4 กฎ + `RollupCheck`/`RollupResult` + ด่านความปลอดภัย |
| `redbook/t1b/__init__.py` | export `check_rollups` · `RollupCheck` · `RollupResult` |
| `tests/test_t1b_rollup.py` | **ใหม่** · 18 ข้อ รวม baseline ของแฟ้มจริง |

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — ROLL-UP RULE SET v0.1.0`
> รอคำตัดสินของ Gift เรื่องเศษการปัด ก่อนตรึงกฎเป็นชุดสุดท้าย

---

## `HL-015` — คำตัดสิน Gift ทาง (ข) · แยก `ROUNDING_RESIDUE` เป็นชนิดของตัวเอง

**วันที่** 2 กันยายน 2569 · **ผู้ทำ** Giho · **commit** `94e138d` (สาขา `t1b/fy2570-mvp`)

### คำตัดสิน

Giho เสนอสามทางสำหรับเศษการปัด `-0.0001` ที่พบ **1 กรณีจาก 167** ในแฟ้มกระทรวง
**Gift เลือกทาง (ข)** — แยกเป็นชนิดใหม่ `ROUNDING_RESIDUE`

| ทาง | ผล |
|---|---|
| (ก) คง `MISMATCH` ไว้ตามเดิม | เสียงดัง ยอดที่ต่างจริงกับเศษปัดปนกัน |
| **(ข) แยกเป็นชนิดใหม่** ✅ | ยังเห็นครบ แต่แยกจากยอดที่ผิดจริง |
| (ค) ยอมรับเป็น `OK` ในขอบเศษ | **ไม่เลือก** — จะเป็นการตั้ง tolerance ครั้งแรกของระบบ |

🔴 **ทางที่เลือกไม่ใช่การตั้ง tolerance** — ระบบยังเทียบแบบตรงตัวที่ทศนิยม
4 ตำแหน่งทุกจุดเหมือนเดิม สิ่งที่เพิ่มคือ **ป้ายกำกับ** ให้คิวมนุษย์อ่านง่ายขึ้น
`requires_human_decision` ของกองนี้ **ยังเป็น `True`** ⇒ ไม่มีอะไรหลุดออกจากคิว

### สิ่งที่เปลี่ยน

* `STATUS_ROUNDING_RESIDUE` เมื่อ `|ส่วนต่าง| ≤ QUANTUM × จำนวนตัวตั้ง`
* `RollupResult.mismatches()` คืนเฉพาะ **ยอดที่ผิดจริง**
* `RollupResult.rounding_residues()` เป็นกองใหม่
* `detail` ระบุส่วนต่าง จำนวนตัวตั้ง ขอบเศษ และคำว่า **"ยังต้องให้มนุษย์ยืนยัน"**

### ผลกับแฟ้มจริง — จำนวนการตรวจไม่เปลี่ยน

```
ตรวจ 167 · ยอดที่ผิดจริง 0 · เศษการปัด 1 · เข้าคิวมนุษย์ 1
```

เดิมรายงานว่า **"ไม่ตรง 1"** ซึ่งอ่านแล้วเหมือนแฟ้มจริงมีข้อผิดพลาดทางบัญชี
ถ้อยคำใหม่แยกสองเรื่องนี้ออกจากกันชัดเจน — สำคัญเวลาเขียนลงเล่ม

| รายการ | ผล |
|---|---|
| tests | **358 passed** (จำนวนเท่าเดิม · ปรับ assertion ให้ตรงคำตัดสิน) |
| `rollup` | `0.1.0` → **`0.2.0`** |
| 🔒 `t1b-key-0.1.0` | ไม่เปลี่ยน |

---

## `HL-016` — rollup `0.3.0` · ปิด silent-drop ที่เหลือ + provenance ถึงแฟ้มต้นทาง

**วันที่** 2 กันยายน 2569 · **ผู้ทำ** Giho · **commit** `8cb7a26` (สาขา `t1b/fy2570-mvp`)

Bo ให้ `CONDITIONAL PASS` ชี้สามจุด · **ตรวจแล้วเป็นจริงทั้งหมด**

### 🔴 ① `UNIT_UNRESOLVED` ถูกทิ้งก่อนถึงด่านตรวจ — และ test ของ Giho ล็อกบั๊กไว้เอง

`_sheet_year_groups()` เรียก `_usable()` คัด record ออก **ก่อน** `_check()` จะเห็น

```
subtotal = 3 · ลูกปกติ = 3 · ลูกหน่วยไม่ทราบ = 500
⇒ ระบบทิ้ง 500 เงียบ แล้วคืน OK
```

🔴 **ความผิดพลาดที่ต้องบันทึกไว้ให้ชัด** — `test_unresolved_unit_records_never_enter_a_sum`
ที่ Giho เขียนเองใน `HL-014` **ยืนยันพฤติกรรมผิดนั้นว่าถูกต้อง** คือเขียน test
ล็อกบั๊กเป็นสเปก ทำให้ `358 passed` ไม่ได้แปลว่าไม่มี silent-drop
นี่คือข้อจำกัดของการนับ test ที่ต้องระวังตลอดโครงการ

**แก้:** ไม่มีการคัด record ทิ้งก่อนถึงด่านตรวจอีก · ชุดที่มีรายการบวกไม่ได้
เป็น `HUMAN_REVIEW` · `computed=None` · ค่าที่บวกไม่ได้ยังอยู่ใน provenance ครบ

### 🔴 ② ชุดตัวตั้งมาไม่ครบยังได้ `OK`

| กรณี | เดิม | ตอนนี้ |
|---|---|---|
| grand split ขาด `รวมเงินนอกงบประมาณ` | `OK` | `INCOMPLETE` |
| subtotal ไม่มีแถวลูกเลย | `continue` เงียบ **ไม่มีผลตรวจ** | `INCOMPLETE` หนึ่งรายการ |
| หมวด/ป้ายซ้ำในชุดเดียวกัน | dict ทับเงียบ **ค่าแรกหาย** | `INCOMPLETE` · ค่าอยู่ครบ |

🔑 **ตัวชี้ว่ากฎ grand-split ใช้ได้ = แถวยอดย่อยแหล่งเงิน ไม่ใช่ `รวมทั้งสิ้น`** —
ถ้าใช้ตัวหลังจะได้ `INCOMPLETE` ปลอมจากชีต `7.x` ที่ไม่ได้แยกแหล่งเงินเลย
**วัดจริงแล้วได้ 85 รายการ** จึงต้องยึดแถวยอดย่อยเป็นตัวชี้

### 🟠 ③ ถ้อยคำมั่นใจเกินหลักฐาน

* ขอบเดิม `n × q` **กว้างกว่าที่การปัดอธิบายได้** → ใช้ `(n+1) × q ÷ 2`
  (`n=6`: `0.0006` → **`0.00035`**)
* `ROUNDING_RESIDUE` → **`ROUNDING_RESIDUE_CANDIDATE`** — ระบบยัง **ไม่ได้พิสูจน์**
  ว่าเกิดจากการปัด เพียงแต่ขนาดส่วนต่างไม่เกินขอบ · การยืนยันเป็นของมนุษย์
* `requires_human_decision` = **ทุกสถานะที่ไม่ใช่ `OK`**

### Provenance ถึงแฟ้มต้นทาง

`Component` เพิ่ม `source_file` · `source_hash` · `raw_value` · `declared_unit` ·
`usable`/`unusable_reason` + property `traceable`
เพิ่ม `check_rollups_for_envelopes()` ที่ดึง `source_hash` จริงจาก envelope
และ **ปฏิเสธการปนแฟ้ม**

### การตรวจสอบ

🔴 **ผลทั้งหมดเป็นการรันในเครื่องผู้พัฒนา — repo ไม่มี CI · ห้ามเขียนว่า "CI ผ่าน"**

| รายการ | ผล |
|---|---|
| ชุดทดสอบ | 358 → **371 passed** (ชุด rollup 18 → 31) |
| **พิสูจน์ว่ากัดโค้ดก่อนแก้** | ข้อกำหนดใหม่ 6 ข้อ vs `94e138d` ⇒ **ล้มเหลว 6/6** · vs `0.3.0` ⇒ ผ่าน 6/6 |
| แฟ้มจริง 6 แฟ้ม | ตรวจ **167** · exact OK **166** · material mismatch **0** · rounding-residue candidate **1** · incomplete **0** · ย้อนต้นทางครบทุกชุด |
| baseline สาย T1B | **ไม่เปลี่ยน** — matched 255/332/115 · accounting ตรงทุกคู่ · `ORDINAL` 2 · audit 8/8 |
| 🔒 `t1b-key-0.1.0` | ไม่เปลี่ยน |

### 🔴 ถ้อยคำที่ต้องใช้เวลารายงานผล roll-up

> ตรวจ 167 ชุด: exact OK 166 · ส่วนต่างที่เหลือ 1 รายการจัดเป็น
> **rounding-residue candidate รอมนุษย์ยืนยัน** · material mismatch 0

**ห้ามเขียนว่า "ยอดที่ผิดจริง 0"** — รายการนั้นยังไม่ได้รับคำตัดสินจากมนุษย์
(`HL-014`/`HL-015` เคยใช้ถ้อยคำนั้น · แก้ที่นี่)

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — ROLLUP 0.3.0 SILENT-DROP CLOSED`

---

## `HL-017` — rollup `0.4.0` · axis contract · applicability สองด้าน · ขอบตามหน่วย

**วันที่** 2 กันยายน 2569 · **ผู้ทำ** Giho · **commit** `4104229` (สาขา `t1b/fy2570-mvp`)

Bo ชี้สี่จุด · **ตรวจแล้วเป็นจริงทั้งหมด**

### 🔴 ① `comparison_axis` ผิดยังได้ `OK`

`_unusable_reason()` ไม่เคยถาม `rec.axis_valid` ⇒ record ที่ประกาศแกนผิด
แต่ยอดบังเอิญตรง ถูกบวกและคืน `OK`

🔴 **จุดที่น่ากังวลคือชั้นล่างรู้อยู่แล้ว** — record นั้นมี `needs_review = True`
ตั้งแต่ `HL-010` แต่ roll-up มีตัวตัดสินของตัวเองที่ไม่ได้ถามชั้นนั้น
เป็นรูปแบบเดียวกับ `HL-012` (ชั้นล่างทำถูกแต่ไม่ถูกเรียก)

### 🔴 ② applicability ตรวจด้านเดียว

| กรณี | เดิม | ตอนนี้ |
|---|---|---|
| มีแถวลูกแต่ไม่มียอดย่อย | ข้ามทั้งชุด | `INCOMPLETE` |
| มีหมวดย่อยแต่ไม่มี `TOTAL` | ข้าม | `INCOMPLETE` |
| มี `TOTAL` แต่ไม่มีหมวดย่อย | ข้าม | `INCOMPLETE` |

**cross-sheet — สำรวจก่อนตั้งกฎตามคำสั่ง Bo**

| กรณี | จำนวนปีในแฟ้มจริง 6 แฟ้ม |
|---|---:|
| มีทั้งบทบาท 4. และ 5. | **8** |
| มีเฉพาะบทบาท 4. | **4** |
| มีเฉพาะบทบาท 5. | **22** |

⇒ การมีข้างเดียวเป็น **เรื่องปกติของเอกสาร** (บทบาท 4. รายงานปีย้อนหลัง ·
บทบาท 5. รายงานปีปัจจุบันและล่วงหน้า) จึงเป็น **not applicable ไม่ใช่ `INCOMPLETE`**
ถ้าตั้งเป็น `INCOMPLETE` จะสร้างรายการปลอม **26 รายการ** และกลบสัญญาณจริง

🔴 **ข้อจำกัดที่รายงานไว้ไม่กลบ** — ตั้งชุดหมวดจาก record ที่ **มีค่า** เท่านั้น
เพราะเซลล์หัวตารางถัดไปถูกติดป้ายหมวดโดยไม่มีค่า พบในแฟ้มจริง **30 รายการ / 15 แถว**
เป็นข้อจำกัดของ **ชั้นสกัด** ไม่ใช่ roll-up · ถ้านับเป็นชุดจะได้ `HUMAN_REVIEW` ปลอม 15 รายการ

### 🟠 ③ `QUANTUM` ตายตัว `0.0001` กับทุกหน่วย

`units.py` ประกาศ `ล้านบาท` = 4 ตำแหน่ง · `บาท` = **2 ตำแหน่ง**
⇒ ยอดหน่วยบาทที่ต่าง `0.01` (หนึ่งหน่วยละเอียดของบาท) ถูกตัดสินเป็น
**material mismatch** อย่างไม่เป็นธรรม

แก้: `units.quantum_for(unit)` · ขอบ = `(q_target + Σ q_component) ÷ 2`
ลดรูปเป็น `(n+1) × q ÷ 2` เมื่อทุกตัวละเอียดเท่ากัน

### 🟠 ④ test ที่ไม่ได้ทดสอบสิ่งที่ชื่ออ้าง

`test_every_non_ok_status_requires_a_human_decision()` เทียบแค่ว่าสตริง `!= "OK"`
⇒ **ผ่านแม้ property `requires_human_decision` จะพังและคืน `False`**
แก้: สร้างผลจริงของทั้งสี่สถานะ ตรวจทั้ง property และการปรากฏใน `needing_human()`
พร้อมตรวจฝั่ง `OK` ว่าต้อง **ไม่** อยู่ในคิว

### Provenance contract

* `check_rollups()` **บังคับ** `source_file`/`source_hash`
* ปฏิเสธแฟ้มปนด้วย **`(source_file, source_hash)`** ไม่ใช่แฮชอย่างเดียว —
  แฟ้มคนละชื่อเนื้อหาเดียวกันมีแฮชเท่ากัน จะปนได้แล้วผลทั้งชุดระบุชื่อเป็นแฟ้มแรก

### การตรวจสอบ

🔴 **ผลทั้งหมดเป็นการรันในเครื่องผู้พัฒนา — repo ไม่มี CI**

| รายการ | ผล |
|---|---|
| ชุดทดสอบ | 371 → **382 passed** (ชุด rollup 31 → 42) |
| **พิสูจน์ว่ากัดโค้ดก่อนแก้** | ข้อกำหนดใหม่ 7 ข้อ vs `8cb7a26` ⇒ **ล้มเหลว 7/7** · vs `0.4.0` ⇒ ผ่าน 7/7 |
| แฟ้มจริง 6 แฟ้ม | **167** · exact OK **166** · candidate **1** · material **0** · incomplete **0** · ย้อนต้นทางครบ |
| baseline สาย T1B | ไม่เปลี่ยน — matched 255/332/115 · accounting ตรงทุกคู่ · `ORDINAL` 2 · audit 8/8 |
| 🔒 `t1b-key-0.1.0` | ไม่เปลี่ยน |

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — ROLLUP 0.4.0 AXIS & APPLICABILITY CLOSED`

---

## `HL-018` — rollup `0.5.0` · raw ที่แปลงไม่ได้ห้ามหาย + ขอบตามที่ประกาศจริง

**วันที่** 3 กันยายน 2569 · **ผู้ทำ** Giho · **commit** `f8201ea` (สาขา `t1b/fy2570-mvp`)

### 📛 ข้อกำหนดเรื่องชื่อ — บังคับตั้งแต่บัดนี้

🔴 **ห้ามใช้คำว่า `R2` เดี่ยว ๆ** — ชนกับ Human Review Round 2 ของสาย T1A
ชื่อทางการของรอบรันเงาสาย T1B คือ **`T1B-SR-21011-02`**
(T1B Shadow Re-run หน่วยงาน 21011 ครั้งที่ 2) · **ไม่ใช่** Human Review Round 2
และ **ไม่รันคู่ขนานกับ T1A ใด ๆ**

### 🔴 ① ค่า raw มีอยู่แต่แปลงตัวเลขไม่ได้ → หายจาก roll-up หมวด

```
OPERATING  raw="#VALUE!"  value=None     ← ถูกตัดก่อนถึงด่านตรวจ
INVESTMENT 3
TOTAL      3              ⇒ คืน OK
```

**แก้ตามเส้นแบ่งที่ Bo วาง — ใช้ `raw_value` เป็นตัวแยก**

| กรณี | ผล |
|---|---|
| `raw_value` = `None` หรือว่างจริง | ไม่มียอดให้กระทบ · ไม่นับเป็นตัวตั้ง |
| `raw_value` มีเนื้อหาแต่ normalize ไม่ได้ | `HUMAN_REVIEW` · `computed=None` · เก็บ raw ครบ |

### 🟠 ② ขอบการปัดไม่ใช้ทศนิยมที่ประกาศเฉพาะเซลล์/ชีต

`normalize_amount()` เคารพข้อความ `"ทศนิยม N ตำแหน่ง"` ผ่าน `declared_places()`
แต่ `quantum_for(unit)` ใช้ค่าปริยายตามชนิดหน่วยอย่างเดียว

แก้: `quantum_for(unit, declaration)` delegate ไป `declared_places()` **ตัวเดียวกัน**
`Component` เก็บ `unit_declaration` จาก `raw_unit_cell` ของแต่ละ record
⇒ ขอบการปัดกับการปัดจริงอิงกติกาเดียวกันเสมอ

### 🔴 ข้อเท็จจริงที่ขัดกับสมมติฐานในคำสั่ง

คำสั่งระบุให้แยกจาก **"30 เซลล์ว่างจริง"** — ตรวจแฟ้มจริงแล้ว
**ทั้ง 30 เซลล์มีข้อความ ไม่มีเซลล์ว่างแม้แต่เซลล์เดียว**

```
G13 raw='งบประมาณ'      I13 raw='ประมาณการรายจ่ายล่วงหน้า**'
```

เป็น **แถวหัวของตารางถัดไป** ที่ **ชั้นสกัด** ดึงเข้ามาในช่วงข้อมูลของตารางหมวด

⇒ เมื่อกติกาใหม่ให้ record ที่มีเนื้อหาดิบเข้าสู่ด่านตรวจ ระบบจึงเริ่มมองเห็น
ข้อบกพร่องนี้ · **จำนวนการตรวจ 167 → 182 · incomplete 0 → 15**
ทั้ง 15 เป็นแถวเดียวกันหมด (ป้าย `ตัวชี้วัด/ แหล่งเงิน`)

🔑 **นี่คือระบบทำงานถูกต้อง ไม่ใช่ regression** — แต่ไม่ตรงกับเกณฑ์ตัวเลข
`167/166/1/0/0` เพราะเกณฑ์นั้นตั้งบนสมมติฐานที่ไม่ตรงกับข้อมูล
การแก้รากอยู่ที่ **ชั้นสกัด** (ขอบเขตแถวข้อมูลของตารางหมวด) ซึ่งอยู่นอกขอบเขต
งานรอบนี้ตามลำดับที่ Bo วางไว้ — **รอคำตัดสิน**

มี regression ล็อกไว้ว่าชุดไม่สมบูรณ์ทั้ง 15 ต้องเป็น **ข้อบกพร่องเดียวกัน**
ถ้ามีชนิดใหม่ปนเข้ามา test จะล้มทันที — กันไม่ให้เลข 15 กลายเป็นตัวเลขที่ไม่มีใครดู

### การตรวจสอบ

🔴 **ผลทั้งหมดเป็นการรันในเครื่องผู้พัฒนา — repo ไม่มี CI**

| รายการ | ผล |
|---|---|
| ชุดทดสอบ | 382 → **396 passed** (ชุด rollup 42 → 56) |
| **พิสูจน์ว่ากัดโค้ดก่อนแก้** | ชุด rollup ใหม่ vs `4104229` ⇒ **ล้มเหลว 13 ข้อ** (12 เชิงพฤติกรรม + 1 เลขเวอร์ชัน) |
| แฟ้มจริง 6 แฟ้ม | **182** · exact OK **166** · material **0** · candidate **1** · incomplete **15** · `HUMAN_REVIEW` **0** |
| baseline สาย T1B | ไม่เปลี่ยน — matched 255/332/115 · accounting ตรงทุกคู่ · `ORDINAL` 2 · audit 8/8 |
| 🔒 `t1b-key-0.1.0` | ไม่เปลี่ยน |

### ลำดับงานที่ Bo วางไว้ — อยู่ที่ข้อ 1

1. ✅ **ปิดสอง boundary ของ roll-up และส่งให้ Bo ตรวจ** ← จบแล้ว หยุดตรงนี้
2. ⬜ สาม blocker จาก Shadow Run ครั้งแรก
3. ⬜ ตรึง commit ใหม่ (`t1b-key-0.2.0` + key-stability audit)
4. ⬜ รัน `T1B-SR-21011-02`
5. ⬜ รอ Bo ตรวจ ก่อนแตะ 21016

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — ROLLUP 0.5.0 RAW & DECLARED-PRECISION CLOSED`

---

## `HL-019` — blocker #4 · ขอบเขตตารางหมวดต้องหยุดก่อนบล็อกหัวของตารางถัดไป

**วันที่** 3 กันยายน 2569 · **ผู้ทำ** Giho · **commit** `95229e9` (สาขา `t1b/fy2570-mvp`)
**คำตัดสิน Bo:** `EXTRACTION OVERLAP P0` — แก้รากก่อน **และ** บันทึกเป็น blocker ตัวที่ 4

### 🔴 แก้บันทึกเดิมของ Bo (ตามที่ Bo สั่งเอง)

ไม่ใช่ **"30 เซลล์ว่าง"** แต่เป็น **30 เซลล์ที่มีข้อความจากหัวตารางถัดไป**
ซึ่งก่อ **15 roll-up checks ปลอม**

### ต้นเหตุ

`find_category_tables()` ตัดขอบเขตที่ **แถวป้ายปี** ของตารางถัดไปอย่างเดียว
แต่บล็อกหัวของตารางนั้นเริ่มก่อนหน้านั้นหนึ่งแถว (แถวหัวคอลัมน์)
⇒ แถวหัวคอลัมน์ตกเป็น **แถวข้อมูลของตารางหมวด**

🔑 **โมดูลเดียวกันเคยขัดแย้งกันเอง** — `_find_unit_column()` มองหาคอลัมน์หน่วยนับ
ที่ `header_row - 1` และ `header_row - 2` อยู่แล้ว คือถือว่าแถวเหล่านั้นเป็นของบล็อกหัว
แต่ตัวกำหนดขอบเขตไม่ได้ใช้กติกาเดียวกัน · **เป็นรูปแบบเดิมซ้ำรอบที่สี่**
(ดู `HL-012` · `HL-016` · `HL-017`)

### การแก้ — หลักฐานเชิงโครงสร้าง ไม่ hard-code ข้อความใด

| ส่วน | หน้าที่ |
|---|---|
| `_is_caption_row()` | แถวข้อความล้วนที่ไม่มีตัวเลข = แถวหัวคอลัมน์ |
| `_header_block_start()` | ไล่ขึ้นจากแถวป้ายปีผ่านแถวหัวคอลัมน์ต่อเนื่อง หยุดที่แถวข้อมูล/แถวว่าง/`floor_row` |
| `YearTable.block_start` | เก็บแถวแรกของบล็อกหัวไว้ให้ตรวจสอบได้ |

ทั้ง `find_year_tables()` และ `find_category_tables()` ใช้ `block_start` เป็นขอบ

🔴 **ห้ามข้ามเงียบเมื่อขอบเขตแข่งกัน** — เดิม `continue` เมื่อไม่เหลือแถวข้อมูล
⇒ ทั้งตารางหายโดยไม่มีร่องรอย · ตอนนี้ `CategoryTable.boundary_ambiguous`
และ adapter ส่งแถวนั้นเข้าคิวมนุษย์ด้วย `UNC_TABLE_BOUNDARY_AMBIGUOUS`

### ผลกับแฟ้มจริง

| ตัวชี้วัด | ผล |
|---|---|
| roll-up | **167** · exact OK **166** · material **0** · candidate **1** · incomplete **0** ✅ |
| ตารางหมวด | **19** เท่าเดิม ✅ |
| `PROJECT_ORDINAL_CHANGED` | **2** ✅ · audit **8/8** ✅ |
| record หมวดที่ไม่มีค่า | 30 → **0** ✅ |
| 🔒 `t1b-key-0.1.0` | ไม่เปลี่ยน ✅ |

### 🔴 `matched` ขยับ — ต้องรายงานตรง ๆ

```
matched   255/332/115 → 253/324/115
unmapped  156/301     → 164/323
```

**เทียบ record ก่อน/หลังแบบเซลล์ต่อเซลล์:**

* หายไป **30 รายการ · ทุกตัวมี `value=None`**
* **ค่าจริงหายศูนย์รายการ**
* ทั้ง 30 **ยังถูกนับครบเป็น `UNMAPPED` พร้อม `raw_label`** — ตรงตามที่ Bo สั่งว่า
  ห้ามทำให้หายเพื่อคืนตัวเลขเดิม
* accounting ยังตรงทุกคู่ (972/972 · 1404/1404 · 894/894)

`matched` ลดลง **10 คู่** เพราะ record ปลอมเหล่านั้นเคย **จับคู่กันเอง** ข้ามปีงบประมาณ
(ป้ายแถวและหมวดเหมือนกัน ค่าเป็น `None` ทั้งคู่)
⇒ เป็นการ **ลบ false match** ไม่ใช่การสูญเสียข้อมูล

### การตรวจสอบ

🔴 **ผลทั้งหมดเป็นการรันในเครื่องผู้พัฒนา — repo ไม่มี CI**

| รายการ | ผล |
|---|---|
| ชุดทดสอบ | 396 → **416 passed** · ไฟล์ใหม่ `test_t1b_table_boundary.py` **20 ข้อ** |
| **พิสูจน์ว่ากัด `f8201ea` โดยตรง** | ใช้เฉพาะ public API ⇒ **ล้มเหลว 4/5 ข้อ** |

ข้อที่ไม่ล้มคือ *"body ไม่ซ้อนกัน"* — ผ่านบนโค้ดเก่าด้วย เพราะโค้ดเก่า **ไม่มีแนวคิด
บล็อกหัว** การซ้อนจึงมองไม่เห็นเมื่อวัดด้วย `header_row` · เป็น invariant สำหรับ
**กันการถอยหลัง** ไม่ใช่ตัวชี้ข้อบกพร่องเดิม — บันทึกไว้ไม่อ้างเกินจริง

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — CATEGORY TABLE RANGE OVERLAP CLOSED`
> ยังไม่เริ่มข้อ 2 · ยังไม่รัน `T1B-SR-21011-02` · ไม่แตะ 21016

---

## `HL-020` — ปิดสาม blocker ที่เหลือ + `t1b-key-0.2.0` + `T1B-SR-21011-02`

**วันที่** 5 กันยายน 2569 · **ผู้ทำ** Giho · **commit ระบบ** `bb399a0` (สาขา `t1b/fy2570-mvp`)
**คำสั่ง Bo:** ลำดับงานข้อ 1–5 ของ `BO REVIEW COMPLETE — NEXT DIRECTIVE`

### 🔴 การตีความที่ต้องให้ Bo ยืนยัน

คำว่า **"สาม blocker ที่เหลือจาก Shadow Run ครั้งแรก"** ไม่เคยถูกไล่เป็นรายข้อ
ในกระทู้ · Giho ตีความตาม **ตาราง `D` (ลำดับความสำคัญ) ของ
`docs/T1B_SHADOW_RUN_21011_R1_LIMITATIONS.md` ลำดับ 1–3** ซึ่งสอดคล้องกับที่
Bo นับ blocker ขอบเขตตารางหมวดเป็น **ตัวที่ 4**

| ที่นี่ | ลำดับใน D | ข้อจำกัดเดิม | สาระ |
|---|---|---|---|
| `BLOCKER_A` | 1 | `B2` | ติดป้ายปีให้ finding แกน `BUDGET_CATEGORY` |
| `BLOCKER_B` | 2 | `B1` | หัวเรื่องชีตต้องไม่ถูกเซลล์ธงแย่ง |
| `BLOCKER_C` | 3 | `B3` | ยืนยันหน่วยงานจากเนื้อในแฟ้ม ไม่ใช่ชื่อไฟล์ |

ลำดับ 4–6 ของตาราง `D` (map ชีตปก · แยกชั้น `UNMAPPED` · เปิด cross-sheet)
**ยังไม่ทำ** — ดูหัวข้อ "ที่ยังไม่ทำ" ท้ายรายการนี้

---

### `BLOCKER_A` — ปีบริบทของตารางแกนหมวด (เกณฑ์หยุดทันทีข้อ 6)

ตารางแกนหมวดถูกบังคับให้ `fiscal_year = None` ตาม XOR ของ `axis_valid`
แต่ตารางในแฟ้มจริง **ผูกกับปีของเอกสาร** ⇒ finding เทียบยอดปีหนึ่งกับอีกปีหนึ่ง
โดยช่องปีว่าง ปนอยู่ในไฟล์เดียวกับ finding ที่เทียบปีเดียวกัน

**การแก้ — ติดป้าย ไม่ใช่ตัดออก**

| ส่วน | หน้าที่ |
|---|---|
| `category_table_fiscal_year` | ปีบริบทของตาราง — **comparison context ไม่ใช่ identity** |
| `category_table_year_source` | `section_title` หรือ `workbook_cover` — 🔴 ต้องบอกที่มาเสมอ |
| `FLAG_CATEGORY_TABLE_YEAR_DIFFERS` | สองฝั่งคนละปี ⇒ บังคับเข้าคิวมนุษย์ |
| `FLAG_CATEGORY_TABLE_YEAR_UNKNOWN` | อ่านปีไม่ได้อย่างน้อยหนึ่งฝั่ง ⇒ บังคับเข้าคิวมนุษย์ |
| `UNC_CATEGORY_TABLE_YEAR_UNRESOLVED` | ไม่มีปีบริบทเลย ⇒ `needs_review` ที่ชั้น record |

ลำดับหลักฐาน: หัวเรื่องชีตที่ระบุ **ปีเดียว** → ปีของเอกสารจากชีตปก → ไม่มี (ติดธง)
🔴 หัวเรื่องที่ระบุหลายปี เช่น `"พ.ศ. 2568 - 2570"` **ไม่ใช้** — ห้ามเดาว่าปีใดคือปีของตาราง

🔴 **`axis_valid` ไม่ถูกแก้** — ฟิลด์ใหม่แยกจาก `fiscal_year` จึงไม่ทำให้ XOR เสีย
🔴 **ไม่มี finding ใดถูกกรองทิ้ง** — จำนวน finding รวมเท่าเดิม เปลี่ยนแค่ธงและคิว

---

### `BLOCKER_B` — หัวเรื่องชีตถูกเซลล์ธงแย่ง

`find_title()` ไล่ **แถวก่อนคอลัมน์** แล้วหยิบข้อความแรกที่เจอ
⇒ เซลล์ธงของเครื่องมือสร้างแฟ้มที่วางอยู่ **คอลัมน์ขวาสุดของแถวเหนือหัวเรื่องจริง**
แย่งตำแหน่งไป ⇒ ไม่มีเลขข้อ ⇒ ชีตเป็น `SUPPORTING` ⇒ ทั้งชีตเป็น `UNMAPPED`

**หลักฐานจากแฟ้มจริง** `AO_21011_HSRI_70.xlsx` ชีต `Sheet7_1`
`N1` = ข้อความหนึ่งอักขระ (ถูกเลือก) · `A2` = หัวเรื่องจริงที่มีเลขข้อ (ถูกข้าม)

**การแก้** เรียงผู้สมัครตาม **`(คอลัมน์, แถว)`** แทน `(แถว, คอลัมน์)` —
หัวเรื่องของเอกสารชุดนี้เป็นข้อความนำของ **คอลัมน์ข้อความซ้ายสุด** เสมอ
ส่วนเซลล์ธงอยู่ทางขวาของเขตข้อมูล · **ไม่ hard-code ถ้อยคำใด**
(ทดสอบด้วยธงหลายแบบ รวมอักขระที่ระบบไม่เคยรู้จัก)

🔴 **ห้ามแก้ด้วยกติกา "เลือกตัวที่มีเลขข้อ"** — ชีตประกอบที่ซ่อนอยู่ (`mask5` `mask6`)
มีบล็อกหัวรายงานที่คอลัมน์ A แล้วตามด้วยข้อความที่มีเลขข้อ
กติกานั้นจะทำให้ชีตประกอบไหลเข้าผลหลักทันที (ข้อจำกัด `B6`) —
มี regression ล็อกไว้แล้ว

**fail-safe** ชีตที่ไม่ใช่ชีตหลักแต่มีผู้สมัครที่มีเลขข้อถูกข้าม ได้เครื่องหมาย
`UNC_SHEET_TITLE_AMBIGUOUS` เพิ่ม — **ไม่เพิ่มจำนวนคิว** เพราะ record เหล่านั้น
เข้าคิวอยู่แล้วด้วย `supporting_sheet_layout_not_mapped` · เพิ่มแค่ **เหตุผล**

---

### `BLOCKER_C` — ตัวตนหน่วยงานจากเนื้อในแฟ้ม ⇒ `t1b-key-0.2.0`

`agency_code` อ่านจากชื่อไฟล์ตามรูปแบบ `XL_FY####_<status>_#####_` เท่านั้น
ชื่อแฟ้มจริงไม่ตรงรูปแบบ ⇒ ว่างสองฝั่ง ⇒ คีย์เท่ากัน ⇒ จับคู่ข้ามหน่วยงานได้เงียบ ๆ

**การแก้สองชั้น**

1. **เชิงโครงสร้าง** — `T1BKey.agency_identity` (ชื่อหน่วยงานจากชีตปก) ⇒ `t1b-key-0.2.0`
2. **ด่านที่ชั้นจับคู่** — `matching.check_identity()` ให้ผล **สามสถานะ**
   ยืนยันได้ / ขัดแย้ง / **ยืนยันไม่ได้** (🔴 ยืนยันไม่ได้ ≠ ผ่าน)

เมื่อขัดแย้ง: **ไม่จับคู่แม้แต่คู่เดียว** · ทุก record เข้าคิวมนุษย์พร้อมเหตุผลตรง ๆ
· `accounted()` ยังครบ

**ขนาดของช่องโหว่ที่ปิดไป (วัดจากแฟ้มจริง 21011 vs 21016 · FY2570)**
คีย์ `VALUE` ที่ชนกันเมื่อ `agency_code` ว่างสองฝั่ง: **54 → 0**

---

### `T1B-SR-21011-02` — ผลการรัน

🔴 **ไม่ใช่ Human Review Round 2 ของสาย T1A** · ห้ามใช้คำว่า `R2` เดี่ยว ๆ

* คู่แฟ้ม **เดียวกับรอบที่ 1** (ปีเอกสาร 2569 vs 2570 · หน่วยงาน 21011)
* ตรึงระบบด้วย `git archive bb399a0` แตกลง scratch directory แล้วรันจากที่นั่น
  — ไม่แตะ working tree · ไม่ checkout · เทียบไฟล์ `redbook/**` **56 ไฟล์ ตรงทุกไฟล์**
* ทำสำเนาก่อนรัน · รันบนสำเนาเท่านั้น · SHA-256 ต้นฉบับและสำเนา **เท่าเดิมก่อน/หลัง**
* รายงานเต็ม (`RUN_MANIFEST.json` · `FINDINGS.csv`) เก็บ **นอก git** ที่
  `redbook-verify-data\T1B_SHADOW_RUN_21011_02\`

| ตัวชี้วัด | ที่ `95229e9` (ก่อนแก้ · คู่เดียวกัน) | `T1B-SR-21011-02` (`bb399a0`) |
|---|---:|---:|
| record ขาเข้า | 1,752 | **1,779** |
| `accounted` | 1,752 / 1,752 | **1,779 / 1,779** ✅ |
| matched | 234 | **258** |
| `ROW_REMOVED` | 312 | **288** |
| `ROW_ADDED` | 127 | **134** |
| `UNMAPPED` | 818 | **809** |
| `needs_human` (record) | 27 | **32** |
| finding รวม | 1,537 | **1,537** |
| ต้องให้มนุษย์ตัดสิน | 1,286 | **1,299** |
| `CATEGORY_TABLE_YEAR_DIFFERS` | — (ไม่มีกลไก) | **34** |
| ด่านตัวตนหน่วยงาน | — (ไม่มีด่าน) | **ยืนยันจากเนื้อในแฟ้ม** |
| roll-up (รายแฟ้ม) | — | **30/30 exact OK · material 0 · incomplete 0** ทั้งสองฝั่ง |

**หลักฐานรายชีตของ `BLOCKER_B`** — ชีต `Sheet7_1` ของแฟ้ม current

| รายการ | ก่อน | หลัง |
|---|---:|---:|
| `sheet_class` | `SUPPORTING` | **`MAIN`** |
| record ชนิด `VALUE` | 0 | **35** |
| record ชนิด `UNMAPPED` | 15 | **6** |
| `ROW_REMOVED` ที่ชี้ชีตนี้ฝั่ง baseline | 72 | **48** |
| `ROW_ADDED` ที่ชี้ชีตนี้ | 0 | **7** |

🔴 **ห้ามเขียนว่า "ลบ false positive 72 ใบ"** — สิ่งที่เกิดขึ้นคือชีตทั้งชีต
**กลับเข้ามาอยู่ในการเทียบ** · จับคู่ได้ **24 คู่** · ที่เหลือ **48 แถวยังรายงานว่าหายไป**
ซึ่งตรวจแล้วมีเหตุจริง: ฝั่ง baseline มี 75 ค่า แต่ฝั่ง current มี 35 ค่า
และปีในชีตนี้เหลื่อมกัน (baseline 2568–2572 · current 2569–2573)
⇒ 14 แถวเป็นปี 2568 ที่ไม่มีในฝั่ง current · ที่เหลือคือแถวที่ชุดข้อมูลย่อลง
**เป็นเรื่องที่คนต้องตัดสิน ไม่ใช่ผลข้างเคียงของข้อบกพร่องหัวเรื่องอีกต่อไป**

---

### invariant ของชุดข้อมูลสาธารณะ 6 แฟ้ม — **ไม่ถอยหลังแม้แต่ตัวเดียว**

| ตัวชี้วัด | ค่าที่ Bo ยืนยันไว้ | ผลที่ `bb399a0` |
|---|---|---|
| matched | `253 / 324 / 115` | **`253 / 324 / 115`** ✅ |
| accounting | 972/972 · 1404/1404 · 894/894 | **ตรงทุกคู่** ✅ |
| `PROJECT_ORDINAL_CHANGED` | 2 | **2** ✅ |
| roll-up 6 แฟ้ม | 167 · exact OK 166 · material 0 · candidate 1 · incomplete 0 | **เท่าเดิมทุกตัว** ✅ |
| key stability audit | 8/8 | **8/8** ✅ |

🔑 **รายงาน key stability audit ของ `t1b-key-0.2.0` เหมือนของ `t1b-key-0.1.0`
ที่ `95229e9` ทุกบรรทัด** (พิสูจน์ด้วย `diff`) ⇒ การเพิ่มฟิลด์ identity
ไม่กระทบพฤติกรรมของข้อมูลหน่วยงานเดียวกันเลย

**ตัวเลขใหม่ที่เพิ่มเข้ามา:** `CATEGORY_TABLE_YEAR_DIFFERS` = 34 (21011) · 46 (21016)
· 0 (21000 — แฟ้มระดับกระทรวงไม่มีตารางแกนหมวด)

---

### การตรวจสอบ

🔴 **ผลทั้งหมดเป็นการรันในเครื่องผู้พัฒนา — repo ไม่มี CI**

| รายการ | ผล |
|---|---|
| ชุดทดสอบ | 416 → **445 passed** · ไฟล์ใหม่ `test_t1b_shadow_blockers.py` **29 ข้อ** |
| **พิสูจน์ว่ากัด `95229e9`** | ข้อกำหนดเชิงพฤติกรรม 5 ข้อ ใช้ **เฉพาะ public API** ⇒ **ล้มเหลว 4/5** |

```
ก่อนแก้ 95229e9                                  หลังแก้ bb399a0
FAIL  หัวเรื่องถูกเซลล์ธงแย่ง                      PASS
FAIL  ชีตหลักที่ถูกแย่ง = SUPPORTING              PASS
FAIL  finding แกนหมวดคนละปี 3/3 ไม่ต้องให้คนตรวจ   PASS
FAIL  คู่ข้ามหน่วยงาน (สังเคราะห์) จับคู่ได้ 3 คู่   PASS
PASS  คู่ข้ามหน่วยงาน (แฟ้มจริง) ไม่จับคู่          PASS   <-- ผ่านบนโค้ดเก่าด้วย
```

🔴 **ข้อที่ 5 ไม่อ้างเกินจริง** — ผ่านบนโค้ดเก่าเพราะแฟ้มในคลังถูก *ตั้งชื่อใหม่*
ให้ตรงรูปแบบ `XL_FY...` จึงมี `agency_code` อยู่แล้ว · เมื่อจำลองสภาพชื่อแฟ้มจริง
(รหัสว่างสองฝั่ง) โค้ดเก่ามีคีย์ชนกัน **54 คีย์** — นั่นคือหลักฐานจริงของข้อนี้

### ที่ยังไม่ทำ

* ลำดับ 4 ของตาราง `D` — map ชีตปก และตารางจำแนกตามลักษณะรายจ่าย (หน่วย **บาท**)
* ลำดับ 5 — แยกชั้น `UNMAPPED` ตามเหตุผลก่อนส่งเข้าคิวมนุษย์
  (รอบนี้เพิ่ม **เหตุผล** ให้แล้วแต่ยังไม่ได้ **จัดชั้น** คิว)
* ลำดับ 6 — เปิด cross-sheet reconciliation
* ข้อจำกัด `B6` (บทบาทชีตรั่วเข้าชีต mask) · `B9` (ไม่เทียบกับ PDF) ·
  `B10` (แถว/คอลัมน์ซ่อน · merged cell) — ยังเปิดอยู่ทั้งหมด
* หน่วยงาน 21016 · UI · finding/evidence export · FY2571 builder —
  **ไม่แตะตามคำสั่ง Bo ข้อ 6**

### สถานะเมื่อจบรายการนี้

> ### `HANDOFF READY FOR BO — THREE SHADOW-RUN BLOCKERS CLOSED · t1b-key-0.2.0 · T1B-SR-21011-02 COMPLETE`
