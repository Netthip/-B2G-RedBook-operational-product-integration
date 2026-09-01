# RESEARCH_PRODUCT_BOUNDARY — เส้นแบ่งงานวิจัยกับผลิตภัณฑ์

**จัดทำ:** 1 กันยายน 2569 · **ผู้ร่าง:** Giho
**ประเภทเอกสาร:** `COORDINATION LAYER ONLY — NOT AN AUTHORITY`
**สถานะ:** `DRAFT — PENDING GIFT REVIEW`

---

## 1. หลักการที่ต้องบันทึกไว้

> **The research prototype validates a verification core; it is not the complete operational RedBook workflow.**

---

## 2. สองสายที่ต้องแยกเสมอ

| | **RESEARCH TRACK** | **PRODUCT TRACK** |
|---|---|---|
| คำถามหลัก | *อะไรที่พิสูจน์แล้วด้วยหลักฐาน* | *อะไรที่ผู้ปฏิบัติงานต้องทำได้จริงอย่างปลอดภัย* |
| อยู่ใต้อำนาจ | Evidence Index + `CLAIM_BOUNDARY.md` | operational requirement ที่ Gift ยืนยัน |
| เปลี่ยนได้ไหม | 🔒 freeze แล้ว — เพิ่มแบบ forward-only เท่านั้น | ✅ ออกแบบและพัฒนาต่อได้ |
| ที่เก็บความจริง | repo `redbook-verify-is` · `redbook-verify` | repo นี้ + งานพัฒนาถัดไป |

---

## 3. 🔴 เส้นแบ่งที่แท้จริง — ชั้นข้อมูล ไม่ใช่แค่ "ขอบเขตกว้างกว่า"

นี่คือข้อค้นพบสำคัญที่สุดของการตรวจรอบนี้ และเป็นสิ่งที่ต้องเขียนให้ชัดกว่าคำว่า *"product กว้างกว่า research"*

| | ชั้นข้อมูลที่ใช้ | สถานะหลักฐาน |
|---|---|---|
| **ผลวิจัยที่ freeze แล้วทั้งหมด** | **`T1A` — Official Flat Data Table** (ตารางข้อมูลแบนจากหน้าเผยแพร่ทางการ) | ✅ มีผลครบ |
| **งานปฏิบัติจริงที่ Gift ต้องการ** (Mode A / Mode B · เอกสารคาดแดง) | **`T1B` — Official AO/RedBook Workbook** (workbook หลายชีต · merged cells · formulas · anchor codes) | ⏳ `T1B-E1` **ยังไม่ได้รัน** |

**หลักฐานที่ยืนยันข้อนี้**

- `M-SET` (แหล่งเดียวของ Precision/Recall/F1) นิยามว่าเป็น *สำเนาของ `T1-01`* ⇒ ชั้น `T1A`
- `C-SET` = `T1-01` ↔ `T1-02` ⇒ ชั้น `T1A`
  (ทั้งสองข้อ: `redbook-verify` → `docs/EXPERIMENT_PROTOCOL.md`)
- `T1B-E1` สถานะ **⏳ รอ structural mapping (`RES-Q-02`)**
  (`redbook-verify-is` → `03_dataset_register/RESEARCH_DATASET_REGISTER.md` ตาราง "ความพร้อมของการทดลองหลังแยกชั้นข้อมูล")
- ไฟล์ต้นทาง `T1B` มีทะเบียน provenance ครบแล้ว — Excel 6 ไฟล์ + PDF 4 ฉบับ — **แต่ยังไม่มีผลการทดลอง**

**ข้อบังคับที่ตามมา**

> `T1A` และ `T1B` **ห้ามใช้ mapping หรือตัวหารร่วมกัน** (`RES-D-24`)
> **ห้ามรวมตัวหารหรือคะแนนข้ามชั้น** `T1A` / `T1B` / PDF / controlled (`RES-Q-01`)

### 3.1 สิ่งที่ห้ามเขียนโดยเด็ดขาด อันเนื่องมาจากข้อ 3

| ห้ามเขียน | เพราะ |
|---|---|
| "ระบบตรวจเอกสารคาดแดงได้แม่นยำ …%" | ตัวเลขทุกตัวมาจากชั้น `T1A` ไม่ใช่ชั้นเอกสารคาดแดง |
| "ผลการทดลองยืนยันว่าใช้กับ AO workbook ได้" | `T1B-E1` ยังไม่ได้รัน |
| นำ P/R/F1 ของ `M-SET` มาอ้างกับงาน Mode A / Mode B | ข้ามชั้นข้อมูล ผิด `RES-Q-01` |
| "ระบบพร้อมใช้กับแบบฟอร์มจริงแล้ว" | `AOWorkbookAdapter` มีโครงในโค้ด แต่ไม่มีผลการทดลองรองรับ |

### 3.2 สิ่งที่พูดได้อย่างตรงไปตรงมา

> ระบบมี adapter สามชนิดในโค้ด (`flat_data_table` · `ao_workbook` · `ministry_pdf`)
> โดยมีเพียง `flat_data_table` ที่มีผลการทดลองที่ตรึงแล้วรองรับ
> การขยายไปยังชั้น `T1B` เป็นงานที่ยังไม่ทำ และต้องถือเป็น **การศึกษาใหม่** ถ้าจะนำผลไปเขียนในเล่ม

---

## 4. Verification core ที่ใช้ร่วมกันได้จริง

ความสามารถต่อไปนี้เป็นของ core ไม่ผูกกับชั้นข้อมูลใดชั้นหนึ่ง จึงนำไปต่อยอดฝั่งผลิตภัณฑ์ได้
โดย **ไม่ต้อง**อ้างว่าเป็นผลการทดลอง:

- deterministic source identity (SHA-256 + manifest)
- canonical data model + normalization
- structured matching และ composite key
- semantic / field-level change detection
- numeric reconciliation
- evidence traceability (finding → source location)
- human-in-the-loop review workflow
- regression testing (**179 tests**)
- reproducible evidence packaging (หลักฐาน 6 ชั้น)

> ⚠️ การนำ core ไปใช้กับชั้นข้อมูลใหม่ **ไม่ทำให้ผลของชั้นเดิมโอนตามไปด้วย**

---

## 5. กฎเวลา — งานหลัง freeze ห้ามเขียนย้อนกลับ

```
   Evidence Index freeze
   1 ก.ย. 2569 · commit 617ceac
            │
  ──────────┼──────────────────────────────►  เวลา
   ก่อนหน้า │  หลังจากนี้
            │
  ผลวิจัย   │  งานพัฒนาผลิตภัณฑ์
  ที่อ้างได้ │  = product evidence / backlog
            │  ❌ ไม่ใช่ผลการทดลองที่เกิดก่อน freeze
```

| สถานการณ์ | ต้องทำอย่างไร |
|---|---|
| พบข้อบกพร่องใหม่ระหว่างพัฒนาผลิตภัณฑ์ | บันทึกเป็น **product evidence / backlog** |
| อยากนำสิ่งที่พัฒนาหลัง freeze ไปเขียนในเล่ม | ต้องตั้งเป็น **study / phase / evidence ใหม่** ที่ระบุวันที่ชัดเจน |
| ต้องเพิ่มหลักฐานเข้าดัชนีที่ freeze แล้ว | **ห้ามแก้รายการเดิม** — เพิ่มแบบ forward-only supplement เท่านั้น |
| ตัวเลขในเล่มขัดกับผลจากผลิตภัณฑ์รุ่นใหม่ | **ไม่แก้ตัวเลขในเล่ม** — รายงานเป็นผลของคนละรุ่น/คนละชั้นข้อมูล |

---

## 6. สิ่งที่ห้ามแตะจากฝั่งผลิตภัณฑ์

| ห้ามแตะ | ที่อยู่ |
|---|---|
| Evidence Index ที่ freeze แล้ว | `redbook-verify-is` → `08_evidence_register/EVIDENCE_INDEX.md` (`617ceac`) |
| รายงาน Human Review สองรอบ | `redbook-verify-is` → `08_evidence_register/HUMAN_REVIEW_R1_R2_REPORT.md` (`4ae0e1f`) |
| workbook รอบที่ 1 และรอบที่ 2 ที่มีคำตอบแล้ว | `04_HUMAN_REVIEW/Round1/` · `04_HUMAN_REVIEW/Round2/` |
| raw results | `redbook-verify-data` (นอก Git) |
| production engine ที่ frozen | `redbook/t1/` ที่ tag `t1-frozen-1.0.0` (`49fbb2e`) |
| commit `e9360ad` | `INTENTIONALLY NOT LANDED` — `LANDING_BOUNDARY_REGISTER.md` |

**การแก้ engine ยังติด `INC-2569-08-27-01` ซึ่งยังเปิดอยู่**

---

## 7. กติกาการเผยแพร่ของ repo สาธารณะนี้

repo นี้เป็น **public** — ก่อนนำสิ่งใดเข้ามาต้องผ่านสามข้อ:

1. **แหล่งที่มาเผยแพร่ได้** — ข้อมูลสาธารณะ (`bb.go.th`) · synthetic fixtures · หรือของที่ Gift อนุมัติแล้ว
2. **ไม่มีไฟล์จากสภาพแวดล้อมของหน่วยงาน (tenant)** ตาม `RES-D-29`
3. **ไม่มี personal path · credential · บันทึกภายในที่ยังไม่เผยแพร่**

> 🔴 **การมีอยู่ในกระบวนการทำงานไม่ใช่เหตุผลให้เผยแพร่ได้**
> ⚠️ **ยังมีรายการค้าง:** ความยินยอมเผยแพร่ `R1`–`R4` ยังไม่ปิด — ดู `OPEN_QUESTIONS.md` ข้อ `Q-01`

---

## 8. ถ้อยคำที่ใช้เรียกแต่ละส่วน

| ส่วน | เรียกว่า |
|---|---|
| ขอบเขตที่พิสูจน์แล้วในงานวิจัย | `research-validated verification core` (บนชั้น `T1A`) |
| ตัวตรวจ FY2570 ที่จะใช้จริง | `operational MVP` |
| ความสามารถ FY2571+ | `future operational workflow` |

**ห้ามใช้ถ้อยคำที่ทำให้เข้าใจว่าเล่มได้พิสูจน์ทุกความสามารถใน product vision แล้ว**
