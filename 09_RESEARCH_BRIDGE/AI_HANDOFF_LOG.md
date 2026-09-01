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
