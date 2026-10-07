# #26 แผนชั้นแบ่งกอง — ฉบับแก้ครั้งที่ 1 (ตาม REVIEW REVISE ของ Bo)

**ประเภท:** `PLAN ONLY — NO IMPLEMENTATION` · **ผู้ร่าง:** Giho · **วันที่:** 7 ต.ค. 2569
**ตอบ:** REVIEW ของ Bo ใน #26 (REVISE PLAN ก่อน implementation)
**สถานะ:** ยังไม่เขียนโค้ด — รอ Bo ACCEPT/REVISE ฉบับนี้

ส่วนที่ไม่ได้กล่าวถึงในไฟล์นี้ = คงตามตัวใบเดิม (5 กอง · 1 finding = 1 กอง · ผลรวมทุกกอง = จำนวน finding ·
ห้ามใช้ชื่อชีต · `requires_human_decision` เดิมเป็นจริงห้ามลงกอง `UNCHANGED_CONFIRMED` · รายงานก่อน–หลังไม่ตั้งเป้า)

---

## 1. สิ่งที่เปลี่ยนจากแผนเดิม

| # | แผนเดิม | ฉบับแก้ |
|---|---|---|
| R1 | `STRUCTURAL_NOISE` เข้าได้ 2 ทาง: พบโทเคนแม่แบบ **หรือ** หัวรายงานระบุหน่วยงานไม่ตรงตัวตนสมุดงาน | ตัดทางที่สองออก — หัวรายงานระบุหน่วยงานไม่ตรง = **identity conflict** ⇒ `REQUIRES_HUMAN_REVIEW` เสมอ |
| R2 | `YEAR_PRESENT_ON_ONE_SIDE_ONLY` (ชื่อจริงในโค้ด) เสนอลง `OUT_OF_SCOPE_VISIBLE` | ค่าเริ่มต้น = `REQUIRES_HUMAN_REVIEW` · ไม่มีกฎยกเว้นในรุ่นนี้ (จะเพิ่มได้ต่อเมื่อประกาศกฎ+หลักฐานเฉพาะผ่านใบนี้ก่อน) |
| R3 | "ภาระคนตรวจ" = `REQUIRES_HUMAN_REVIEW` + `OUT_OF_SCOPE_VISIBLE` (ตัวเลขเดียว) | รายงาน **สอง metric แยกกันเสมอ** ห้ามเรียกรวมว่า "ภาระคนตรวจ" |

## 2. เงื่อนไข `STRUCTURAL_NOISE` (ฉบับแก้ · ต้องจริงครบทุกข้อ)

1. finding เป็น UNMAPPED
2. พบโทเคนแม่แบบ **ในเนื้อหาเซลล์** อย่างน้อยหนึ่งเซลล์ และเก็บพิกัดเซลล์นั้นเป็นหลักฐานของ finding
3. ไม่มีธงใดใน `REVIEW_FLAGS`
4. ตัวตนหน่วยงานของคู่สมุดงานเป็น `confirmed` (ไม่ใช่ conflict / unverified / ambiguous)
5. ไม่มีสัญญาณหน่วยงานอื่นในหัวรายงานของบล็อกเดียวกัน

ข้อใดไม่จริง ⇒ ไม่ลงกองรบกวน · ถ้าไม่เข้ากองอื่นตามลำดับ ⇒ `REQUIRES_HUMAN_REVIEW`

## 3. ลำดับการตัดสิน (ข้อแรกที่จริงชนะ)

1. ธงใน `REVIEW_FLAGS` · identity ไม่ใช่ `confirmed` · หัวรายงานระบุหน่วยงานอื่น · `YEAR_PRESENT_ON_ONE_SIDE_ONLY` · ป้ายช่วงเวลาเปลี่ยน · กำกวม/เทียบไม่ได้ ⇒ `REQUIRES_HUMAN_REVIEW`
2. ยอด/ตัวชี้วัด/แถว/หน่วย/เลขลำดับเปลี่ยน ⇒ `MATERIAL_CHANGE`
3. UNMAPPED ที่ผ่านเงื่อนไขข้อ 2 ครบ ⇒ `STRUCTURAL_NOISE`
4. คอลัมน์หัวอ่านไม่ออก (`UNSUPPORTED_*`) · ชีตปกที่ยังไม่สกัด ⇒ `OUT_OF_SCOPE_VISIBLE`
5. ไม่เปลี่ยน และ `requires_human_decision` เป็นเท็จ ⇒ `UNCHANGED_CONFIRMED`
6. เหลือ ⇒ `REQUIRES_HUMAN_REVIEW` (fail-closed — ห้ามมี finding ที่ไม่มีกอง)

ข้อ 1 อยู่บนสุดเพื่อให้ identity conflict และธงบังคับตรวจ **ชนะทุกกฎลดภาระ**

## 4. Metric ที่รายงาน (ก่อน–หลัง · จำนวนนับเท่านั้น · ไม่ตั้งเป้า)

| ชื่อ | นิยาม |
|---|---|
| `mandatory_decision_burden` | จำนวนใน `REQUIRES_HUMAN_REVIEW` |
| `visible_unresolved_burden` | `REQUIRES_HUMAN_REVIEW` + `OUT_OF_SCOPE_VISIBLE` |
| ต่อกอง | จำนวนทั้ง 5 กอง + ผลรวม = จำนวน finding |

ข้อความรายงานทุกแห่งต้องมีทั้งสองชื่อคู่กัน — ห้ามมีคำว่า "ภาระคนตรวจ" ลอย ๆ ตัวเลขเดียว

## 5. Synthetic negative cases (เทสต์ที่จะเขียนเมื่ออนุมัติ)

| รหัส | อินพุตสังเคราะห์ | ต้องได้ |
|---|---|---|
| N1 | UNMAPPED + โทเคนแม่แบบในเซลล์ + identity **conflict** | `REQUIRES_HUMAN_REVIEW` (ไม่ใช่รบกวน) |
| N2 | UNMAPPED + หัวรายงานระบุหน่วยงานอื่น · **ไม่มี**โทเคนแม่แบบ | `REQUIRES_HUMAN_REVIEW` |
| N3 | UNMAPPED + โทเคนแม่แบบ + หัวรายงานระบุหน่วยงานอื่น | `REQUIRES_HUMAN_REVIEW` (identity ชนะ) |
| N4 | UNMAPPED + โทเคนแม่แบบ + identity `unverified` / `ambiguous` | `REQUIRES_HUMAN_REVIEW` ทั้งสองกรณี |
| N5 | UNMAPPED + โทเคนแม่แบบ + มีธงใน `REVIEW_FLAGS` | `REQUIRES_HUMAN_REVIEW` |
| N6 | `YEAR_PRESENT_ON_ONE_SIDE_ONLY` ไม่มีธงอื่น | `REQUIRES_HUMAN_REVIEW` (ไม่ใช่ `OUT_OF_SCOPE_VISIBLE`) |
| N7 | `YEAR_PRESENT_ON_ONE_SIDE_ONLY` บนชีตปกที่ยังไม่สกัด | `REQUIRES_HUMAN_REVIEW` (ข้อ 1 ชนะข้อ 4) |
| N8 | ชีตชื่อแม่แบบ แต่เนื้อหาเป็นข้อมูลจริงของหน่วยงานเดียวกัน ไม่มีโทเคน | ไม่ใช่รบกวน |
| N9 | ชีตชื่อปกติ + โทเคนแม่แบบ + identity confirmed + ไม่มีธง | `STRUCTURAL_NOISE` พร้อมพิกัดเซลล์หลักฐาน (กรณีบวกคุมคู่กับ N8) |
| N10 | กองรบกวนที่ไม่มีพิกัดเซลล์หลักฐาน | เทสต์ล้ม (invariant) |
| N11 | finding ใดก็ได้ที่ `requires_human_decision` เดิมเป็นจริง | ไม่ลง `UNCHANGED_CONFIRMED` (property) |
| N12 | รายงาน metric | มีทั้ง `mandatory_decision_burden` และ `visible_unresolved_burden` · ไม่มี metric รวมชื่อเดียว |

**Mutation ที่ต้องทำให้เทสต์ล้ม:**
- M1 ใช้ชื่อชีตเป็นเกณฑ์กองรบกวน ⇒ N8 หรือ N9 ล้ม
- M2 คืนทาง "หัวรายงานหน่วยงานไม่ตรง ⇒ รบกวน" ⇒ N2/N3 ล้ม
- M3 ย้าย `YEAR_PRESENT_ON_ONE_SIDE_ONLY` ไป `OUT_OF_SCOPE_VISIBLE` ⇒ N6 ล้ม
- M4 สลับลำดับให้ข้อ 4 มาก่อนข้อ 1 ⇒ N7 ล้ม
- M5 รวม metric เป็นตัวเดียว ⇒ N12 ล้ม

**Property (ทุกชุดสุ่ม):** ทุก finding อยู่ในกองเดียว · ผลรวมทุกกอง = จำนวน finding

## 6. ขอบเขตที่ไม่เปลี่ยน

ไม่แตะ UI (#24) · engine · key · finding type · `requires_human_decision` · ชุดประเมินสุดท้าย · scoring ·
evaluator ที่ตรึงแล้ว — งานอยู่ในโมดูลใหม่ชั้นบริการ + เทสต์เท่านั้น
