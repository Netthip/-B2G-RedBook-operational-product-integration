# HANDOFF — #29 รวมด่านเข้าเอนจินสำหรับการประเมินสุดท้าย (Giho → Bo) · 7 ต.ค. 2569

**สถานะ:** `READY FOR BO REVIEW — EVALUATION ENGINE TREE INTEGRATED, NOT YET FROZEN`
🔴 **ยังไม่ติด engine tag** · ไม่สุ่ม · ไม่สร้างกองผู้ผ่าน · ไม่เปิดไฟล์ผู้สมัคร · ไม่สร้างเฉลย · ไม่แก้โปรโตคอล #22
ผลทดสอบทั้งหมด = ผลการรันในเครื่องผู้พัฒนา (ไม่มี CI) · commit/branch ของ repo ระบบอยู่ในบันทึกฝั่ง private (กติกา repo สาธารณะ)

## 1. ฐานและสิ่งที่รวม

- **ฐาน = commit ล่าสุดของ G1–G3 ที่ Bo ACCEPT** (#14 `6020507009`) — ไม่ใช่ปลาย branch ของ #14 · ไม่มี commit ของ #26
- #21 `final-holdout-guard-0.1.1` ต่อจากฐานตรง ๆ (fast-forward) · #5 `t1b-eval-entry-gate-0.1.0` merge **ไม่มี conflict · ไม่แก้โค้ด**
- `t1b-posture-0.2.0` + `t1b-scoring-3layer-0.2.0` มีอยู่ในฐานแล้ว
- diff ฐาน → รวม: **8 ไฟล์ · เพิ่ม 944 บรรทัด · ลบ 0** · ไฟล์เดิมที่ถูกแตะมีแค่ hook ของ #21 ในตัวอ่านไฟล์ 3 จุด (+3 · +3 · +8)

## 2. regression

| ชุด | ฐาน | รวมแล้ว |
|---|---|---|
| full suite | 1442 passed · 4 skipped | **1480 passed · 4 skipped** (= 1442 + 38 ของด่านพอดี · skip 4 ตัวเดิม) |
| gate #21 + #5 | — | 38 passed |
| ไฟล์ทดสอบ G-series 9 ไฟล์ | — | 279 passed |

gate regression ตามที่ #29 กำหนด (ชื่อทดสอบเต็มในบันทึก private §2):
posture fail-closed (ชนิดไม่ประกาศ · รุ่นท่าทีเปลี่ยน · ละเมิด 5 แบบ · ไม่มีทางเลี่ยง) ✅ ·
manifest ที่ระบุชัดแต่หาย fail-closed (+ สำเนา/อัปโหลดขณะหาย) ✅ ·
สำเนา/อัปโหลดไฟล์ผนึกถูกปฏิเสธ (+ ทุกทางเข้า 4 จุด) ✅ ·
workflow ปกติไม่ถดถอย (ไฟล์ทั่วไป · ยังไม่ผนึก · ไม่ตั้งค่า) ✅ + §3

## 3. finding equivalence

- เครื่องมือ `eval29-finding-fingerprint-0.1.0` ไฟล์เดียวกันรันกับสอง tree · ชุด = คู่พัฒนาสาธารณะ FY2569→FY2570 สามคู่ (`10_T1B_DATASET` · ระบุชื่อตรงตัว)
- ครอบ record · ผลจับคู่ · finding ทุกฟิลด์ (type · key · flags · ตำแหน่งหลักฐาน · ค่า · detail) ทั้งตามลำดับและแบบเซต · identity · roll-up
- canonicalize เฉพาะ path ของไฟล์ → ชื่อไฟล์ · ไม่มี timestamp/run id ให้ตัด
- findings 865 / 883 / 1400 ทั้งสองฝั่ง
- **fingerprint ฐาน = รวมแล้ว = `691545eedceae713b2b4020afbb68fd73fad527ea7dccfa19cc802647c6bf48e`** · ผลเต็มสองฝั่งตรงกันทุกไบต์ · **finding เปลี่ยน 0 รายการ**

## 4. proposed tag (ยังไม่สร้าง)

| | |
|---|---|
| proposed evaluation engine tag | `final-eval-engine-1.0.0` |
| source hash (git tree ของ `redbook/`) | `2fcb9b379f35b42540ef28739a638fadd6426660` |
| commit ที่จะ tag | commit หลักฐานของ #29 ใน repo ระบบ (ในบันทึก private) — tree `redbook/` ของ commit นั้น = ค่าข้างบน |

หลัง Bo ACCEPT: สร้าง tag ที่ commit นั้นเท่านั้น · ตรวจซ้ำว่า tree `redbook/` ตรงค่าข้างบนก่อนติด tag

## 5. ข้อจำกัด

- equivalence วัดบนชุดพัฒนาสามคู่ + ชุดทดสอบสังเคราะห์ใน full suite — ไม่ใช่ทุก input ที่เป็นไปได้
- ด่าน #21 กันเฉพาะการอ่านผ่านระบบ · ยังไม่ได้ใช้กับ holdout จริง
- branch รวม push ขึ้น repo ระบบ (private) แล้วเพื่อให้ตรวจ diff ได้ · ยังไม่มี tag
