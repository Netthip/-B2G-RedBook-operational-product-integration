# OPERATIONAL_PRODUCT_VISION — ภาพผลิตภัณฑ์ที่ใช้งานจริง

**จัดทำ:** 1 กันยายน 2569 · **ผู้ร่าง:** Giho จาก requirement ที่ Gift ยืนยัน
**ประเภทเอกสาร:** `COORDINATION LAYER ONLY — NOT AN AUTHORITY`
**สถานะ:** `DRAFT — PENDING GIFT REVIEW`

> 🔴 **ข้อกำกับของ Gift ที่ต้องรักษาไว้ในทุกฉบับต่อจากนี้**
> **ห้ามลด vision นี้เหลือเพียง "โปรแกรมหา diff"**
>
> เป้าหมายไม่ใช่การบอกว่าไฟล์สองไฟล์ต่างกันตรงไหน แต่คือการช่วยให้ผู้ปฏิบัติงานตอบได้ว่า
> **อะไรเปลี่ยน · การเปลี่ยนนั้นตั้งใจหรือไม่ · ยอดและฟิลด์ที่เกี่ยวข้องยังสอดคล้องกันหรือไม่
> · และต้องกลับไปแก้ตรงไหนก่อนส่งหรือเผยแพร่**

---

## 0. เอกสารนี้คือ requirement ไม่ใช่ผลการทดลอง

ทุกข้อในเอกสารนี้เป็น **PRODUCT REQUIREMENT** ที่ยังไม่มีหลักฐานรองรับ เว้นแต่ระบุไว้เป็นอย่างอื่น
**ห้ามนำข้อความในเอกสารนี้ไปอ้างในเล่มว่าเป็นความสามารถที่พิสูจน์แล้ว**

---

## 1. Mode A — Draft / Pre-Bill Workflow

**ใช้กับ:** ปีงบประมาณใหม่ เช่น **FY2571**
**เป้าหมาย:** ไม่ใช่แค่เทียบ Excel สองไฟล์ แต่**ช่วยสร้างและตรวจ "คาดแดง" ตั้งแต่ต้น**

### 1.1 ข้อมูลเข้า

| แหล่ง | บทบาท |
|---|---|
| previous-year baseline | ฐานเปรียบเทียบของปีก่อน |
| current-year e-Budget data | ข้อมูลปีปัจจุบันจากระบบต้นทาง |
| รายงานคาดแดง | องค์ประกอบเอกสารคาดแดง |
| เล่มฟ้า | องค์ประกอบเล่มฟ้า |
| กฎแบบฟอร์มที่อนุมัติแล้ว | ข้อบังคับด้านโครงสร้าง |

### 1.2 สิ่งที่ระบบต้องทำ

1. ประกอบร่างเอกสารคาดแดงปีใหม่จากโครงสร้างต้นทางจริง
2. รักษา layout / template invariant ที่แบบฟอร์มกำหนด
3. **cell-level comparison** — เทียบระดับเซลล์
4. **semantic comparison** — เทียบระดับความหมาย ไม่ใช่แค่ข้อความตรงตัว
5. **indicator / name / detail comparison** — ตัวชี้วัด ชื่อรายการ และรายละเอียด
6. **monetary reconciliation** — ยอดเงินกระทบยอดกันได้
7. **cross-sheet consistency** — ความสอดคล้องข้ามชีต
8. **formatting / layout conformance** — ความถูกต้องของรูปแบบและการจัดหน้า
9. ตรวจพบรายการ/แผนงาน/ตัวชี้วัดที่ **เพิ่มขึ้น ลดลง หรือย้ายตำแหน่ง**
10. **เสนอให้มนุษย์ตัดสิน ไม่เดาแทน** (human decision)
11. **correction target** — ระบุว่าควรกลับไปแก้ข้อมูลตรงใดใน **e-Budget**
12. ส่งออก **validated RedBook artefact**
13. เตรียมทาง **PDF generation / preflight** ในอนาคต

---

## 2. Mode B — Post-Reduction Workflow

**ใช้กับ:** หลังวาระ 2–3 เช่น **FY2570**
**ฐานเปรียบเทียบ:** ร่างที่ผ่านการตรวจรอบแรกแล้ว (validated Draft-Bill baseline)
**เป้าหมาย:** ตรวจผลจากการปรับลด/เพิ่มจริงว่าถูกต้องและครบถ้วน

### 2.1 สิ่งที่ระบบต้องทำ

1. **intentional adjustment detection** — แยกการปรับที่ตั้งใจออกจากความผิดพลาด
2. **reconciliation จากระดับรายการไปยังยอดรวม** — รายการ → ผลผลิต/โครงการ → แผนงาน → ยอดหน่วยงาน
3. **propagation** ไปปีถัดไป และรายการผูกพันที่เกี่ยวข้อง
4. **indicator / detail re-check** — ตรวจตัวชี้วัดและรายละเอียดซ้ำ
5. แยก **corrective edit** ออกจาก **intentional budget adjustment**
6. **formula residue preflight** — ตรวจสูตรตกค้าง
7. **value-only conversion validation** — ตรวจความถูกต้องหลังแปลงเป็นค่าคงที่
8. **final publication artefact validation** — ตรวจชิ้นงานฉบับเผยแพร่

### 2.2 หมวดผลการจำแนกที่ต้องมี

| หมวด | ความหมาย |
|---|---|
| การปรับลด/เพิ่มที่ได้รับอนุมัติ | ตรงกับมติที่ทราบ |
| ผลสืบเนื่องจากการปรับที่อนุมัติ | ยอดที่เปลี่ยนตามอย่างถูกต้อง |
| การแก้เชิงคุณภาพข้อมูล | corrective / data-quality edit |
| ความต่างที่อธิบายไม่ได้ | ต้องยกให้มนุษย์ตัดสิน |
| ตัดสินอัตโนมัติไม่ได้ | ส่งเข้า human review เสมอ |

---

## 3. หน่วยการตรวจของ UI — ไม่ใช่รายการ diff

หน้าจอตรวจสอบต้องตอบคำถามชุดนี้ให้ครบในหนึ่งรายการ:

```
context → baseline → current → difference → dependent checks
        → evidence → machine assessment → human decision → correction target
```

| ต้องแสดง | หมายเหตุ |
|---|---|
| finding ID | ผูกกับหลักฐานได้ |
| ตำแหน่งต้นทาง | ชีต/เซลล์ หรือตำแหน่งเชิงความหมาย |
| ค่า baseline → ค่าปัจจุบัน → ผลต่าง | |
| ทิศทางที่คาดหมาย | เพิ่ม/ลด/ไม่เปลี่ยน |
| ยอดที่ขึ้นต่อกันซึ่งได้รับผล | dependent totals |
| ลิงก์หลักฐาน | evidence pointer |
| การจำแนกของเครื่อง | machine classification |
| **คำตัดสินของมนุษย์ + ระดับความมั่นใจ + หมายเหตุ** | บังคับ |
| **correction target** | ต้องกลับไปแก้ที่ไหน |

**สถานะปลายทางของงานหนึ่งชุด:** `READY` หรือ `REVIEW REQUIRED`

> ⚠️ **ข้อกำกับด้านถ้อยคำบนหน้าจอ:** ห้ามใช้ถ้อยคำที่รับรองความถูกต้องเด็ดขาด
> ระบบเสนอสิ่งที่ตรวจพบ — **มนุษย์เป็นผู้ตัดสิน**

---

## 4. ผลลัพธ์ที่ต้องส่งออกได้

- verified working workbook
- structured finding list
- reconciliation summary
- evidence / audit package
- สถานะ `READY` / `REVIEW REQUIRED` ที่ชัดเจน

---

## 5. 🔴 เงื่อนไขทางวิศวกรรมที่ต้องผ่านก่อน — ข้อสังเกตจาก Giho

`ENGINEERING OBSERVATION`

Mode A และ Mode B ทั้งคู่ทำงานบนชั้นข้อมูล **`T1B` — Official AO/RedBook Workbook**
ซึ่ง **ยังไม่มีผลการทดลองที่ตรึงแล้ว** (`T1B-E1` = ⏳ รอ structural mapping · `RES-Q-02`)
ในขณะที่ core ที่ freeze แล้วทั้งหมดทำงานบนชั้น **`T1A`** ซึ่งเป็นตารางข้อมูลแบน

**ความต่างเชิงโครงสร้างที่ต้องข้ามให้ได้ก่อน**

| `T1A` (ที่ core รองรับแล้ว) | `T1B` (ที่งานจริงต้องใช้) |
|---|---|
| ตารางแบน หนึ่งชีตข้อมูล | workbook หลายชีต |
| ไม่มี merged cells | **merged cells** |
| ไม่มีสูตร | **formulas** ที่ต้องตรวจและอาจต้องแปลงเป็นค่า |
| คีย์ตรงไปตรงมา | **anchor codes** และโครงสร้างเฉพาะแบบฟอร์ม |
| หน่วยตามตารางข้อมูล | **ล้านบาท ทศนิยม 4 ตำแหน่ง** ตามคอลัมน์หน่วยนับ |

**ลำดับงานที่ Giho เสนอ** (เป็นข้อเสนอ ไม่ใช่คำตัดสิน — รอ Gift)

1. `structural mapping` ของ `T1B` — ให้ `AOWorkbookAdapter` อ่านแบบฟอร์มจริงได้อย่างกำหนดผลได้แน่นอน
2. `cross-sheet` / `roll-up` model — นิยามความสัมพันธ์ รายการ → ผลผลิต → แผนงาน → ยอดหน่วยงาน
3. `formula residue` + `value-only` preflight
4. layer การจำแนก intentional vs corrective
5. ขยาย review UI ให้มี `correction target`
6. evidence packaging ของสายผลิตภัณฑ์ (แยกจาก Evidence Index ของงานวิจัย)

**ข้อบังคับ:** งานทั้ง 6 ข้อเกิดหลัง Evidence Index freeze (1 ก.ย. 2569)
⇒ เป็น **product evidence** ห้ามเขียนย้อนกลับว่าเป็นผลการทดลองที่เกิดก่อน freeze

---

## 6. สิ่งที่ยังไม่รวมในรอบใกล้นี้

| ไม่รวม | เหตุผล |
|---|---|
| การเขียนกลับเข้า e-Budget อัตโนมัติ (write-back / API) | ระบบชี้ **correction target** ให้มนุษย์ไปแก้เอง |
| PDF workflow เต็มรูปแบบ | Phase 3 · ยังไม่เริ่ม (`RES-D-32`) |
| OCR เป็นกลไกตรวจสอบหลัก | OCR กู้ข้อความที่มองเห็นได้ แต่ไม่ตรวจโครงสร้าง สูตร ความสัมพันธ์ข้ามชีต และการกระทบยอด |
| candidate validation rules ใน `RES-D-51` | **ห้าม implement** จนกว่าจะมีคำตัดสินใหม่ |

---

## 7. ความสัมพันธ์กับงาน B2G เดิม

repo `Netthip/b2g-thai-pdf-repair` ยังคงเป็นสาย PDF repair / QA evidence
แนวคิดที่นำมาใช้ซ้ำได้: baseline locking · issue registry · human review · reproducible QA · evidence packaging
โดยจัดวางเป็น **ความสามารถตรวจชิ้นงานปลายทาง** ไม่ใช่ตัวแทนของการตรวจ spreadsheet

---

## 8. ปลายทางระยะยาว

```
source data → build → structured verification → human review
            → correction → final workbook → PDF/publication QA → evidence package
```
