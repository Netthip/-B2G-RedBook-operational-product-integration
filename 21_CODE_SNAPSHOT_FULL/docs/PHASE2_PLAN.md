# Phase 2 — แผนดำเนินการและขอบเขตที่ผู้ใช้กำหนด

จัดทำ: 27 สิงหาคม 2569 · อ้างอิงข้อกำหนดของผู้รับผิดชอบงานวิจัย (กิ๊ฟ) เมื่อ 26 ส.ค. 2569
สถานะตั้งต้น: Phase 0–1 ได้รับการรับรองแล้ว — ตรึงไว้ที่ git tag **`phase-0-1-baseline`**
(commit `a0750ab`) ห้ามแก้ผลย้อนหลัง

---

## 1. ขอบเขตข้อมูลของงานวิจัยฉบับเต็ม (ห้ามออกแบบแคบกว่านี้)

| มิติ | ขอบเขต |
|---|---|
| หน่วยงาน | 2 หน่วยงาน: **สวรส.** และ **สถาบันวัคซีนแห่งชาติ** |
| ปีงบประมาณ | 2568, 2569, 2570 |
| คู่เปรียบเทียบข้ามปี | 2568–2569 และ 2569–2570 |
| เปรียบเทียบปรับลด | ฉบับก่อน–หลังปรับลด |

**ผลต่อการออกแบบ:** ห้าม hard-code ปีหรือหน่วยงานใดในโค้ด — ทุกการตีความโครงสร้าง
อยู่ใน **Mapping Profile** (`redbook/rules/mapping_model.py`) ที่ผูกกับ
(หน่วยงาน × ประเภทเอกสาร × ช่วงปี) หนึ่งบริบท และสร้างได้หลายโปรไฟล์
ชุดไฟล์แรกที่จะได้รับ (หน่วยงานเดียว) ใช้สร้างและยืนยัน mapping ชุดแรกเท่านั้น
ไม่ใช่ขอบเขตทั้งหมดของระบบ

ชุดไฟล์ขั้นต่ำสำหรับเริ่ม Phase 2 (กิ๊ฟจะแจ้งโฟลเดอร์แยกต่างหาก):
คาดแดง 2569 (.xlsx) · คาดแดง 2570 (.xlsx) · ฉบับก่อนปรับลด · ฉบับหลังปรับลด ·
ตาราง/เอกสารรายการปรับลดที่อนุมัติ (ถ้ามี)

---

## 2. ลำดับการทำงาน (ทำข้ามขั้นไม่ได้)

### Phase 2A — Read-only File Inventory ✅ กลไกพร้อมแล้ว (รอไฟล์)

เครื่องมือ: `redbook/inventory_cli.py` + `redbook/readers/excel_inventory.py`

```
.venv\Scripts\python.exe -m redbook.inventory_cli "<โฟลเดอร์ที่กิ๊ฟแจ้ง>"
```

พฤติกรรมที่รับประกันโดยโค้ดและชุดทดสอบ:

- อ่านไฟล์ต้นฉบับ**อย่างเดียว ไม่คัดลอก ไม่แก้ไข** — พิสูจน์ด้วย SHA-256 ก่อน/หลังอ่าน
  ถ้าแฮชไม่ตรง โปรแกรมหยุดทันที
- รายงานต่อไฟล์ครบตามข้อกำหนด: ชื่อไฟล์ · SHA-256 · ประเภทไฟล์จริง ·
  ปีงบประมาณที่อ่านพบ (candidate) · ชื่อหน่วยงานที่อ่านพบ (candidate) · รายชื่อชีต ·
  hidden sheets · used range · merged cells · แถวหัวตาราง candidate ·
  แถวเริ่ม/สิ้นสุดข้อมูล candidate · ชื่อและตำแหน่งคอลัมน์ · หน่วยเงินพร้อมตำแหน่งหลักฐาน ·
  สูตรและความเชื่อมโยงระหว่างชีต · ตัวอย่างรหัส/ชื่อรายการ/ร่องรอยลำดับชั้น ·
  ความแตกต่างโครงสร้างระหว่างสองไฟล์ · จุดที่ parser อ่านไม่ได้หรือไม่แน่ใจ
- **ทุกค่าเป็น candidate** — เมื่อพบมากกว่าหนึ่งความเป็นไปได้ รายงานทุกความเป็นไปได้
  ไม่เลือกแทนผู้ใช้
- ผลลัพธ์เขียนลง `.data/inventory/` (นอก git นอก OneDrive) และ CLI
  **ปฏิเสธ outdir ที่อยู่ใน OneDrive** เว้นแต่สั่งข้ามอย่างชัดแจ้ง
- ไฟล์ PDF: บันทึกเฉพาะบัญชี (ชื่อ/ขนาด/SHA-256/ชนิดจริง) — ไม่อ่านเนื้อหา (Phase 3)

### Phase 2B — Mapping Confirmation Package (ทำเมื่อได้ไฟล์)

ส่งมอบ 6 รายการ แล้ว**หยุดรอกิ๊ฟยืนยัน**:

1. `FILE_INVENTORY.md` (CLI สร้างให้)
2. `WORKBOOK_STRUCTURE_REPORT.md` (CLI สร้างให้)
3. `MAPPING_CANDIDATES.md` (CLI สร้างร่างให้ — ทางเลือกพร้อมหลักฐาน sheet/row/cell)
4. `MAPPING_DECISION_FORM.md` — แบบยืนยันการตัดสินใจ (จะจัดทำเป็น Word ให้กรอกจริง)
5. `UNRESOLVED_QUESTIONS.md` — ข้อที่ระบบไม่แน่ใจ/ตอบเองไม่ได้
6. หลักฐานภาพหรือ cell references ที่ตรวจย้อนกลับได้

### Phase 2C — Excel Comparator Implementation (หลังยืนยัน mapping เท่านั้น)

- canonical extraction ตาม Mapping Profile ที่ approved
- exact matching → rule-based matching → suggested matching (รอ Human Review)
- year-to-year comparison · before/after reduction comparison
- subtotal/total reconciliation
- evidence mapping ถึง sheet/row/cell
- automated tests + reproducibility test + export ผลตรวจจริง

---

## 3. กรอบคำตอบเบื้องต้นที่กิ๊ฟให้ไว้ (บังคับใช้ใน 2C)

| ข้อ | กรอบที่ต้องเคารพ | จุดที่บังคับในโค้ดแล้ว |
|---|---|---|
| Q1 | ห้าม assume ว่ารหัสใดคงที่ข้ามปี · เสนอบันไดคีย์ 5 ขั้น · fuzzy = เสนอเท่านั้น · **ห้ามใช้ลำดับแถวเป็นตัวระบุข้ามปี** · ทุก match เก็บ วิธี/คีย์/confidence/หลักฐาน A,B/สถานะ/เหตุผลมนุษย์ | `mapping_model.validate()` ปฏิเสธ `row_order` และบังคับ `suggest_only` สำหรับ normalized/fuzzy · ตาราง `item_matches` มีครบทุกช่องอยู่แล้ว |
| Q2 | ห้ามตอบจาก validator เดิม · ห้ามถือว่า Sheet4/Sheet5 เหมือนกันทุกไฟล์ · ทำ sheet-role proposal จาก workbook จริง พร้อมหลักฐานสูตร | inventory สร้าง sheet-role proposal จากทิศทางการอ้างสูตรจริง (`refs_to_sheets`) |
| Q3 | อ่านหน่วยจากหัวเอกสาร/หัวตาราง/หมายเหตุ/รูปแบบตัวเลข · รายงานแยก stored / displayed / number format / declared unit / normalized · **ห้าม normalize จนกว่ายืนยัน** | inventory รายงาน unit hints พร้อมตำแหน่ง + number format ต่อคอลัมน์ · `ColumnMapping.scale_to_baht` ต้องมี evidence จึงผ่าน validate |
| Q5 | ±10% **ไม่ใช่เกณฑ์ถูกผิด** · เป็นได้แค่ตัวกรองจัดลำดับ/ระดับความสำคัญ/ค่าที่ผู้ใช้ตั้งต่องาน · ห้ามซ่อนผลต่าง <10% · ห้ามเรียก >10% ว่า error | `MappingProfile.thresholds` บังคับ `role: "highlight_only"` · comparator ใน 2C ต้องรายงาน amount A/B, ผลต่างสัมบูรณ์, ร้อยละ (เมื่อฐานเหมาะสม), ตำแหน่งหลักฐานทั้งสองฝั่ง ทุกจุดในขอบเขตกฎ |

คำถามฉบับเต็ม Q1–Q8 พร้อมโครงการตัดสินใจ: [QUESTIONS_Q1_Q8.md](QUESTIONS_Q1_Q8.md)

**อัปเดต 27 ส.ค. 2569:** กิ๊ฟรับรองงานเตรียม Phase 2A + Q1–Q8 และล็อกคำตัดสิน 5 ข้อ
(Q5 · ข้อความฐานศูนย์ · Q8 · read-only+SHA ใน 2A · secure upload storage ใน 2C)
— ดูรายละเอียดและการบังคับใช้ใน [DECISIONS_LOG.md](DECISIONS_LOG.md) ·
Q1–Q4, Q6, Q7 ยังไม่ยืนยัน: Q6 ให้เสนอ tolerance จากหลักฐานจริงแต่ห้ามเปิดใช้ ·
Q7 ให้เสนอผลทั้งสามแบบเชิงจำนวน (ย้ายหนึ่งรายการ / หาย+ใหม่ / คู่รอ Human Review)

---

## 4. ข้อห้ามของ Phase 2 (จากข้อกำหนด 26 ส.ค. 2569)

1. ห้ามแก้ไฟล์ต้นฉบับ
2. ห้ามนำ `AGENCY_MAP` เดิมมาใช้
3. ห้าม hard-code ชื่อชีต แถว คอลัมน์ หรือหน่วย โดยไม่มี configuration และหลักฐาน
4. ห้ามใช้เลขแถวเป็น primary identity ข้ามปี
5. ห้ามเรียกความแตกต่างระหว่างปีว่า "ข้อผิดพลาด"
6. ห้ามถือว่ารายการปรับลดทุกจุดถูกต้องโดยไม่ตรวจความสัมพันธ์ของยอด
7. ห้ามสร้างข้อมูลตัวอย่างปนในผลตรวจจริง
8. ห้ามใช้ผลทดลองจาก P1 Validator หรือ CASE A/CASE B เป็นผลของ RedBook Verify
9. ห้ามแก้ validator v0.3.0 หรือหลักฐานเดิม
10. ห้ามบันทึกไฟล์อัปโหลดหรือฐานข้อมูล runtime ลง OneDrive
11. ห้าม commit เอกสารราชการหรือฐานข้อมูล runtime เข้า git
12. ห้ามเริ่ม PDF comparator ใน Phase 2
13. ห้ามกล่าวว่า Phase 2 สำเร็จจนกว่าจะผ่านไฟล์จริงและมีหลักฐานย้อนกลับ

หมายเหตุการตีความข้อ 3: รายการคำสำคัญใน `excel_inventory.py` เป็น heuristic
สำหรับ "ชี้จุดให้มนุษย์ดู" (สร้าง candidate) เท่านั้น ไม่มีผลตัดสิน — mapping จริง
อยู่ใน Mapping Profile ที่ผู้ใช้ยืนยันพร้อมหลักฐานเสมอ

---

## 5. สิ่งที่เพิ่มระหว่างรอไฟล์ (ไม่ผูกกับโครงสร้างหน่วยงาน)

| สิ่งที่เพิ่ม | ไฟล์ | ทดสอบ |
|---|---|---|
| กลไก inventory แบบ read-only | `redbook/readers/excel_inventory.py` | `tests/test_inventory.py` |
| ตัวเรนเดอร์รายงาน 2A | `redbook/report/inventory_report.py` | ผ่าน CLI e2e test |
| CLI สำรวจไฟล์ | `redbook/inventory_cli.py` | e2e + OneDrive guard + PDF handling |
| โครงสร้าง Mapping Profile | `redbook/rules/mapping_model.py` | `tests/test_mapping_model.py` |
| เอกสารสถานะสภาพแวดล้อม | `docs/ENVIRONMENT.md` | — |
| คำถาม Q1–Q8 ฉบับเต็ม | `docs/QUESTIONS_Q1_Q8.md` | — |

ไม่มีการแตะ Phase 3 (PDF/OCR) ตามข้อห้าม
