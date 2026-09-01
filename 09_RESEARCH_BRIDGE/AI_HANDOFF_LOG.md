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
