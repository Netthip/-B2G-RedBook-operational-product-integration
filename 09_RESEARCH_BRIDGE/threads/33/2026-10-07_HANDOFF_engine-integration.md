# #33 — รวม #26 + #31 + #32 บน engine lane (combined HEAD เดียว)

**สถานะ:** `READY FOR REVIEW (Bo)` · ไม่ใช่ final evaluation · Giho · 7 ต.ค. 2569
**branch (repo ระบบ):** `int/33-engine-integration` · ฐาน = `t1b/engine-coverage-g` ล่าสุดหลัง #26 ACCEPT
**`final-eval-engine-1.0.0`:** ไม่ถูกแตะ — tag ชี้ที่เดิม และ combined HEAD ไม่อยู่ในประวัติของ tag

## 1. Replay

| ลำดับ | change-set | ผล cherry-pick | tests #31/#32 ที่ขั้นนั้น (บนฐาน #26) |
|---|---|---|---|
| 1 | #31 predeclared tests | สะอาด | 7 failed / 8 passed (ตรงกับที่ประกาศ) |
| 2 | #31 `indicator-role-0.1.0` | สะอาด | 16 passed |
| 3 | #32 predeclared tests | สะอาด | 6 failed / 28 passed (ตรงกับที่ประกาศ) |
| 4 | #32 `indicator-role-0.1.1` | สะอาด | 34 passed |

- **conflict: ไม่มี** (#26 แตะ `redbook/services/review_buckets.py` + tests · #31/#32 แตะ `redbook/t1b/*` + adapter — ไฟล์ไม่ซ้อนกัน)
- **ไม่ replay** commit ศึกษา #30 (หลักฐานอยู่ใน branch/รายงานเดิม)
- cherry-pick ใช้ `-x` ⇒ ทุก commit อ้างต้นทางได้

## 2. Gates บน combined HEAD เดียว

| gate | ผล |
|---|---|
| full suite | **1545 passed · 4 skipped** (ฐาน #26 = 1511 passed · 4 skipped · +34 = tests #31 16 + #32 18 · ไม่มีการถดถอย) — **รันในเครื่องผู้พัฒนา ไม่มี CI** |
| #26 review-bucket + revalidation safety + #31 + #32 | 82 passed |
| review-layer conservation (#26 `check_invariants` · fail-closed) บนผล engine ที่รวมแล้ว | formative คู่ของ #26 ✓ · 18 คู่ของ 36 สมุดงาน ✓ · **invariant error 0** |
| mandatory set ก่อนชั้นแบ่งกอง = ที่ชั้นแบ่งกองแทน | ✓ ทุกคู่ (`mandatory_review_findings` = จำนวน `requires_human_decision` ของ engine พอดี) |
| ชั้นแบ่งกองไม่แก้/ไม่ทิ้ง finding ของ engine | ✓ แฮชรายการ finding ก่อน = หลังสร้างแผน ทุกคู่ |
| advisory นับแยก | ✓ (formative คู่ของ #26: 0 · 36 สมุดงาน: 432) |

**รุ่นบน combined HEAD:** `ao-workbook-schema-0.4.1-t1b-structural-0.2.0` · `indicator-role-0.1.1` · `t1b-review-buckets-0.1.0` · `t1b-compare-0.9.0`

## 3. ตรวจการถดถอยข้ามฟีเจอร์ (formative คู่ของ #26)

| | ผล |
|---|---|
| record ฝั่งฐาน / ฝั่งปัจจุบัน | 1,231 / 1,231 → 1,231 / 1,231 (คงเดิม) |
| finding_id ที่มีทั้งก่อนและหลัง | **1,769 ใบ — ชนิด กอง หน่วยตัดสิน เหตุผล ลายนิ้วมือการรวมหน่วย และเซลล์หลักฐาน ตรงกันทุกใบ** |
| finding_id ที่หายไป | 50 ใบ — `AMBIGUOUS` ทั้งหมด (record 25 แถวต่อฝั่งที่เดิมอ่านหน่วยไม่ได้) |
| finding_id ที่เพิ่มมา | 25 ใบ — `INDICATOR_UNCHANGED` 15 · `NOT_COMPARABLE` 10 (record ชุดเดียวกันหลัง #31 อ่านหน่วยได้) |
| id ที่พึ่งลำดับ | 646 → 636 (หายไป 12 · เพิ่มมา 2 · อยู่ในชุดที่เปลี่ยนเท่านั้น) |
| หน่วยตัดสินหลายใบ | 30 หน่วย ครอบ 270 ใบ — **เหมือนเดิมทุกหน่วย** |
| marker ของ #31/#32 บนคู่นี้ | `unit_literal_from_unit_column` 50 · `unit_internal_space_normalized` 0 |

`NOT_COMPARABLE` 10 ใบที่เพิ่ม: หน่วยตรงกันสองฝั่งแต่ค่าแปลงเป็นตัวเลขไม่ได้ ⇒ คนตรวจ (fail-closed เดิมของ compare)

⇒ **การเปลี่ยนทั้งหมดอยู่ในขอบเขต #31** ไม่พบการเคลื่อนของ id ที่พึ่งลำดับ หลักฐานการรวมหน่วย หรือความหมายหน่วยนอกชุดนี้

## 4. Integration baseline (ใหม่) — ไม่แทนตัวเลขที่ #26 อ้างไว้

### formative คู่ของ #26

| ตัวชี้วัด #26 | #26 ที่ ACCEPT (รุ่น formative เดิม) | **integration baseline** (combined HEAD) |
|---|---:|---:|
| finding ทั้งหมด | 1,819 | **1,794** |
| mandatory review findings | 1,204 | **1,164** |
| mandatory review units | 964 | **924** |
| scope-visible unresolved findings | 146 | 146 |
| advisory review findings | 0 | 0 |
| กอง REVIEW / MATERIAL / UNCHANGED | 1,204 / 98 / 517 | 1,164 / 98 / 532 |

- 1,204 → 1,164 = −50 `AMBIGUOUS` + 10 `NOT_COMPARABLE` · 964 → 924 = ส่วนต่างเดียวกัน (ทั้ง 40 เป็นหน่วยเดี่ยว)
- 🔴 ข้ออ้างของ #26 "mandatory review units 1,204 → 964" คงไว้ **สำหรับรุ่น formative ที่ ACCEPT เท่านั้น** ·
  ตัวเลขชุดใหม่เป็น baseline ของ combined HEAD · **ห้ามนำมาต่อกันเป็นการลดภาระ** — การเปลี่ยน 1,204 → 1,164 มาจาก #31 เปลี่ยนการสกัดต้นน้ำ ไม่ใช่ชั้นแบ่งกอง

### 36 สมุดงานของ #27/#30 (18 คู่ · ร่าง 2569 → ร่าง 2570 · ชุดพัฒนา)

| | ฐาน #26 | combined HEAD |
|---|---:|---:|
| finding ทั้งหมด | 27,093 | 26,683 |
| mandatory review findings (= engine `requires_human`) | 22,837 | 22,165 |
| mandatory review units | 22,321 | 21,649 |
| scope-visible / advisory | 767 / 432 | 767 / 432 |
| กอง REVIEW / MATERIAL / UNCHANGED | 23,269 / 1,496 / 2,328 | 22,597 / 1,626 / 2,460 |

ชุดนี้ไม่ใช่ formative set ของ #26 ⇒ ใช้เป็น baseline ตรวจ conservation เท่านั้น **ไม่ใช้อ้างการลดภาระ**

## 5. ข้อจำกัด

- formative = คู่เดียวของ #26 + 36 สมุดงานจาก 2 กระทรวง · ไม่ใช่ final evaluation · ไม่ใช่ทุกกระทรวง
- `ReviewLedger` ของ #26 ยังเป็น in-memory (ข้อจำกัดเดิมของ #26)
- G-I3/G-I4 ยังไม่แก้ (defer) ⇒ `ROW_ADDED`/`ROW_REMOVED` ของตัวชี้วัดยังสูง
- ไฟล์หลักฐานนอก git (SHA-256 16 หลักแรก): layer 36 ฐาน `c168a9c2759ca5ef` · รวม `9c98d9fc9ff3be67` ·
  metrics คู่ #26 ฐาน `c455b0a46f0b5a86` · รวม `8a09855d9e2542fe` · แผนราย id ฐาน `c06b4d7095dd032f` · รวม `f00f345c6955e042`
- ไม่ได้เข้าถึงไฟล์ผู้สมัคร / Data Table / ไฟล์ใหม่ใด ๆ · สคริปต์ metrics ของ #26 ใช้ฉบับเดิมไม่แก้ (ตรวจแฮชไฟล์ขาเข้าก่อนรัน)

## 6. หมายเหตุถึง #32 (ไม่ block)

ตัวเลข `16 / 23,721` ใน #32 ใช้ตัวหารคนละชุดกับ finding ทั้งหมด (26,683):
**23,721 = จำนวน "ลายนิ้วมือ finding" ที่ไม่ซ้ำ** (คีย์ × ปีงบประมาณ × ป้ายช่วงเวลา × หมวดงบ ต่อคู่หน่วยงาน) ·
finding หลายใบที่ลายนิ้วมือเดียวกัน (เช่น `AMBIGUOUS` สองฝั่ง) นับเป็นหนึ่ง ⇒ ถ้านำไปเขียนในงานวิจัยต้องระบุนิยามนี้

## 7. ขอ Bo

1. ACCEPT combined HEAD เป็น engine lane ใหม่ (ปลายทาง: fast-forward `t1b/engine-coverage-g` ไปที่ combined HEAD หรือคงเป็น branch แยก)
2. รับ integration baseline ตาม §4 แทนการเทียบกับ 1,204/964 ตรง ๆ
