# คำสั่งหลักของ Gift — `T1B / FY2570 Operational MVP`

**ออกโดย:** Gift (Principal Investigator + Product Owner) · **วันที่:** 1 กันยายน 2569
**บันทึกโดย:** Giho · **สถานะ:** `MASTER DIRECTIVE — SINGLE SOURCE FOR THIS WORKSTREAM`

> เอกสารนี้เป็น **คำสั่งชุดเดียว** ของงาน `T1B / FY2570 Operational MVP`
> คำสั่งก่อนหน้าที่ขัดกับเอกสารนี้ให้ถือว่าถูกแทน
> **ยังไม่แทน** `CLAIM_BOUNDARY.md` · `EVIDENCE_INDEX.md` · `DECISIONS_LOG.md` ซึ่งยังเป็น authority เดิม

---

## 0. ป้ายกำกับผลงานรอบนี้

> ### `PRODUCT EVIDENCE — POST-FREEZE`

**ห้ามนำผลของ `T1B` รอบนี้ย้อนกลับไปอ้างว่าเป็นผลของ frozen `T1A` evaluation เดิม**

---

## 1. เป้าหมาย

เครื่องมือสำหรับงานจริงปี 2570 บนไฟล์ Excel โครงสร้างจริงของคาดแดง/เล่มฟ้า
**ไม่ใช่ generic diff viewer** — ต้อง

1. อ่าน workbook จริงตามโครงสร้างที่มีอยู่
2. ประกอบ/จำแนกบทบาทของชีตให้ถูก
3. ตรวจความแตกต่างจากร่าง พ.ร.บ. ไปยังฉบับหลังปรับลด
4. ตรวจตัวเลข · ตัวชี้วัด · ชื่อ · รายละเอียด · ผลรวม · ความสัมพันธ์ข้ามชีต · ปีที่เกี่ยวข้อง · สูตร/ค่า residual
5. สร้าง finding ที่มนุษย์ตรวจต่อได้
6. ชี้กลับได้ว่าควรแก้ตรงไหนก่อนนำไฟล์ไปใช้จริง

---

## 2. การระบุบทบาทของชีต

| ใช้ได้ | ห้ามใช้เป็น identity key |
|---|---|
| `A1` + content signature + `document_level` | ชื่อชีต · index ของชีต · prefix ตัวอักษรอย่างเดียว · สีของ tab |

**ห้าม hard-code เลขแถวหัวตาราง** — ต้อง locate ด้วย signature

---

## 3. Defect เดิมเรื่อง `b` / `B` / `บ`

`supporting_sheet_prefixes = ("b","B")` = **defect** · **ห้ามยกมาใช้เป็น logic หลักของ `T1B` ใหม่**

> 🔴 **ไม่ต้อง rename ชีตต้นทางให้เข้ากับโค้ด**
> ระบบต้องอ่านไฟล์จริงได้โดยไม่บังคับผู้ใช้แก้ชื่อชีต
> ชื่อจริงที่ต้องรองรับ: `บุค` · `bบุค` · `Bยุท` · `Sheet7.2` · `Sheet 7.2` · และรูปแบบอื่นตามต้นทาง

---

## 4. Canonical role ภายใน — ภาษาอังกฤษแบบมีความหมาย

| ชื่อไทยที่พบ | canonical role | short code |
|---|---|---|
| แผนบุคลากรภาครัฐ / แผนบุค | `PLAN_PERSONNEL` | `PERS` |
| แผนงานพื้นฐาน / แผนพื้น | `PLAN_FUNDAMENTAL` | `FUND` |
| แผนงานยุทธศาสตร์ / แผนยุทธ | `PLAN_STRATEGIC` | `STRAT` |
| แผนงานบูรณาการ / แผนบู | `PLAN_INTEGRATED` | `INTG` |

> 🔴 **ห้ามใช้ code ตัวเดียวแบบ `B`** — ไม่บอกความหมายและเสี่ยงสับสนกับ `บ` ภาษาไทย

---

## 5. สีใน Excel = document-role cue เท่านั้น

| สี | ความหมาย |
|---|---|
| 🟨 เหลือง | `DRAFT` — ร่างชั่วคราว / อยู่ระหว่างประกอบ / ยังไม่ final |
| 🟦 ฟ้า | `BLUEBOOK` — เล่มฟ้า |
| 🟥 แดง | `REDBOOK` — คาดแดง / ฉบับจริง |
| ⬜ ขาว | `SOURCE` / `REFERENCE` — ไฟล์ต้นทาง / เอกสารอ้างอิง |

**เหตุผล:** ห้ามใช้ฟ้าเป็นสี Draft เพราะฟ้าหมายถึงเล่มฟ้าอยู่แล้ว · แดงสงวนให้คาดแดง
· Draft ใช้เหลืองเพื่อสื่อว่ายังต้องตรวจ

> 🔴 **สีเป็น visual cue เท่านั้น** — internal identity ยัง resolve จาก `A1` + content signature + canonical role

---

## 6. `Q-06` — ✅ อนุญาตให้เริ่ม `T1B` implementation

**อนุญาตให้พัฒนา `T1B`-specific path** — `AOWorkbookAdapter` · `sheet_role_resolver` ·
`header_locator` · `year_column_resolver` · `unit_resolver` · `decimal_normalizer` ·
`supporting_sheet_classifier` · `hierarchy_parser` · `t1b_canonical` · `roll_up_model` ·
`correction_target` · tests ของ `T1B`

### เงื่อนไขที่ยังบังคับเต็ม

| # | ห้าม |
|---|---|
| 1 | แก้ frozen `T1A` evaluation path |
| 2 | แก้ `FlatDataTableAdapter` |
| 3 | เปลี่ยน frozen `T1A` canonical / schema / rules / version |
| 4 | แก้ raw results เดิม |
| 5 | แก้ Evidence Index เดิม |
| 6 | ใช้ mapping / denominator ร่วมกับ `T1A` |
| 7 | import เข้า Audit Trail (ยัง blocked ตาม `RES-D-41` / `SYS-D-26`) |
| 8 | implement candidate rules ที่ยังห้าม (`RES-D-51`) |
| 9 | Phase 3 PDF / ZAP ที่ยัง blocked ยังคง blocked |

---

## 7. ✅ ผลการตรวจ verbatim ของ `INC-2569-08-27-01` — Giho · 1 ก.ย. 2569

Gift สั่งว่า *"ถ้า `INC-2569-08-27-01` มีข้อความ verbatim ที่ห้ามแม้แต่การสร้าง `T1B` path ใหม่
ให้หยุดเฉพาะจุดที่ขัดนั้น แล้วคัดข้อความจริงกลับมาให้กิ๊ฟตัดสิน"*

**อ่านครบทั้ง 11 เอกสารในโฟลเดอร์ incident + `DECISIONS_LOG.md` แล้ว**

### 7.1 ข้อความห้ามที่พบจริง — ยกมาตรงตัว

**① `RES-D-32`** (`DECISIONS_LOG.md`)

> **เงื่อนไขก่อนเริ่ม:** ปิดการสอบสวน `INC-2569-08-27-01` · ปิดรายงานสถานะสอง repo (ฉบับแก้ forward-only) ·
> ยืนยันสถานะ Phase 2C แล้วเท่านั้น — **ระหว่างนี้ห้ามแก้โค้ด deployment**

**② `00_INCIDENT_RECORD.md` §9.4** — กติกาที่ยังบังคับใช้เต็มระหว่าง incident เปิด

> - **ห้าม `git add -A`** — ใช้ `git add <path>` ระบุไฟล์เสมอ
> - ห้าม merge `incident/*` หรือ `integration/*` เอง · ห้ามลบ worktree ที่เป็นหลักฐาน
> - ห้ามแก้ frozen engine · findings · raw values · canonical values · source hashes ·
>   คำตอบที่ผู้วิจัยกรอกแล้ว · ไฟล์ที่ประกาศ freeze แล้ว
> - **ห้ามเติมผล Human Review หรือผลบทที่ 4 ล่วงหน้าในเอกสารใด**

**③ `OWNERSHIP_AND_FORWARD_FIX_PLAN.md` ขั้นที่ 1** — `| **ห้าม** | แตะไฟล์โค้ดใด ๆ · แตะ tag |`

### 7.2 การวินิจฉัย

| ข้อ | ห้ามสร้าง `T1B` path ใหม่หรือไม่ | เหตุผล |
|---|---|---|
| ① | ❌ **ไม่ห้าม** | คำในเอกสารคือ **"โค้ด deployment"** ไม่ใช่โค้ดทั้งหมด · `RES-D-31` ระบุขอบเขต deployment ไว้ชัด = private cloud · health check · TLS · backup/restore · ZAP — `T1B` adapter ไม่อยู่ในขอบเขตนั้น |
| ② | ❌ **ไม่ห้าม** | ห้ามแก้ **frozen** engine และของที่ freeze แล้ว — การสร้างไฟล์ใหม่ในเส้นทาง `T1B` ไม่แตะของเดิม · ข้อ `git add -A` ยังบังคับและจะปฏิบัติตาม |
| ③ | ❌ **ไม่ห้าม** | เป็นข้อห้าม **เฉพาะขอบเขตของงานขั้นที่ 1** (สร้าง `docs/COMMIT_ERRATA.md`) ไม่ใช่ข้อห้ามทั่วไป |

> ### ✅ สรุป: `NO VERBATIM PROHIBITION FOUND AGAINST CREATING A NEW T1B PATH`
> ไม่มีจุดใดต้องหยุดตามเงื่อนไขของ Gift ข้อ 5

### 7.3 ⚠️ สิ่งที่ต้องแจ้ง — ไม่ใช่ข้อห้าม แต่ควรมีคำตัดสินรองรับ

`RES-D-32` กำหนด **ลำดับงาน 10 ขั้น** ไว้ว่า
① ปิด Phase 2C และ Human Review ② พัฒนา Phase 3 PDF Comparator ③ Review/Reporting workflow
④ เตรียม portable deployment ⑤ ติดตั้ง private cloud ⑥ ทดสอบ local เทียบ private cloud
⑦ ทดสอบความปลอดภัย ⑧ ปรับเล่มตามผลจริง ⑨ Pilot Extension ⑩ Office LAN

**งาน `T1B` / FY2570 Operational MVP ไม่ปรากฏในลำดับนี้เลย** เพราะตอนออก `RES-D-32` (27 ส.ค.)
ยังไม่มีสายงานผลิตภัณฑ์แยก

⇒ ไม่ได้ขัดคำสั่งใด แต่เป็น **สายงานใหม่ที่อยู่นอกลำดับที่เคยตัดสินไว้**
เสนอให้ออกคำตัดสินที่เลขว่างถัดไป **`RES-D-54`** (คู่ `SYS-D-33`) รับรองสายงานนี้และความสัมพันธ์กับ `RES-D-32`
— รวมกับ `Q-07` · **Giho ไม่ออกเลขเอง**

---

## 8. `Q-08` — synthetic fixture สำหรับสูตร

ชุด public `T1B` เป็น value-only (`formulas = 0` ทั้ง 6 ไฟล์)
⇒ **อนุญาตให้สร้าง synthetic fixture แยก** สำหรับ formula residue · cached/formula mismatch
· value-only conversion · post-conversion reconciliation

> ต้องติดป้าย **`SYNTHETIC TEST FIXTURE`** ให้ชัด
> **ห้ามรายงานผลจาก synthetic fixture ว่าเป็นข้อผิดพลาดที่พบใน workbook จริง**

---

## 9. `Q-09` — canonical matching key ของ `T1B`

- ✅ `T1B` ใช้ key ใหม่ **แยกจาก `T1A`**
- ✅ เพิ่มมิติ **`document_level`** แยกระดับกระทรวง / ระดับหน่วยงาน — **ห้ามจับคู่ข้ามระดับ**
- ✅ `year_column` และ `declared_unit` = **attribute ที่ต้อง resolve/compare ไม่ใช่ identity key โดยอัตโนมัติ**

**ก่อน freeze key ใหม่ ต้องส่งกลับ 6 อย่าง** — ① exact key schema ② field ที่เป็น identity
③ field ที่เป็น comparison attribute ④ field ที่เป็น provenance/location
⑤ ตัวอย่างจากไฟล์จริง 3–5 ตัวอย่าง ⑥ ตัวอย่างคู่ที่ไม่ควรจับกันแม้ข้อความใกล้กัน

---

## 10. ข้อมูล `T1B` — เผยแพร่สาธารณะได้

> Gift ยืนยัน: *"ชุดข้อมูล `T1B` ที่ใช้ในงานวิจัย/การพัฒนารอบนี้สามารถเผยแพร่เป็นสาธารณะได้"*

นำขึ้นพื้นที่ที่ Bo และ Giho เข้าถึงร่วมกันได้ เพื่อใช้ทำ structural mapping · test fixture
· adapter validation · reproducible product evidence

**ต้องบันทึกครบ 7 ฟิลด์:** source · filename · SHA-256 · fiscal year · document level
· dataset kind · provenance pointer

---

## 11. Critical path 7 วัน — ยังไม่กระจาย feature ยังไม่โฟกัส UI สวย

| # | งาน | # | งาน |
|---:|---|---:|---|
| 1 | `T1B` structural resolver | 9 | amount comparison |
| 2 | `AOWorkbookAdapter.inspect()` | 10 | indicator/name/detail comparison |
| 3 | `AOWorkbookAdapter.extract()` | 11 | hierarchical roll-up / reconciliation |
| 4 | `T1B` canonical representation | 12 | cross-sheet consistency |
| 5 | matching key | 13 | formula/value preflight |
| 6 | year alignment จากป้ายปี | 14 | finding + evidence |
| 7 | unit resolution ระดับแถว | 15 | human review |
| 8 | Decimal normalization | 16 | readiness gate |

**เป้าหมายสุดท้ายของ MVP:** ระบบตอบได้ว่า **`READY`** หรือ **`REVIEW REQUIRED`** พร้อมรายการ
อะไรเปลี่ยน · เปลี่ยนตรงไหน · คาดว่าเป็น adjustment ที่ตั้งใจหรือไม่ · กระทบยอดใดต่อ
· ต้องตรวจ/แก้จุดใดก่อนส่งระบบ

---

## 12. สิ่งที่ห้ามลดรูป

> 🔴 **ห้ามทำ `T1B` MVP ให้เหลือเพียง `Excel diff viewer`**

งานจริงต้องตรวจ semantic role · amount · indicator · hierarchy · year propagation · unit
· cross-sheet consistency · human decision — และต้องตอบ **"ต้องทำอะไรต่อ"** ไม่ใช่แค่ "สองค่าต่างกัน"

---

## 13. งานถัดไป — **tests ก่อน implementation**

ทำใน **branch/path แยกของ `T1B`** และเริ่มจาก unit tests ของ silent failure ที่พบจริง 8 ข้อ

| # | failure mode | ต้องพิสูจน์ว่า |
|---:|---|---|
| 1 | sheet name เปลี่ยนแต่ `A1` role เดิม | ต้องจับคู่ได้ |
| 2 | sheet index เลื่อน | ต้องไม่กระทบ matching |
| 3 | `บุค` ภาษาไทย | ต้อง classify ได้ |
| 4 | year column เลื่อน | ต้องจับด้วยป้ายปี ไม่ใช่ column letter |
| 5 | `บาท` / `ล้านบาท` / `ร้อยละ` | ห้ามตีความเป็นชนิดเดียวกัน |
| 6 | float residue เช่น `937.5201000000001` | ต้อง normalize เป็นค่าที่เอกสารประกาศ |
| 7 | document level ต่างกัน | ห้ามจับคู่ |
| 8 | header row อยู่คนละตำแหน่ง | ต้อง locate ด้วย signature |

**เมื่อ test baseline ครบ 8 ข้อแล้วจึงเริ่มเติม implementation**

---

## 14. Handoff

เมื่อรอบ implementation แรกพร้อมให้ Bo ตรวจ → โพสต์ใน `BRIDGE-001` ด้วย marker
**`HANDOFF READY FOR BO`** พร้อม commit · files changed · tests added · tests passed/failed
· known limitations · สิ่งที่ไม่ได้แตะ · decision ที่ยังต้องการจาก Gift

Bo ตอบกลับด้วย **`BO REVIEW COMPLETE`**
