# [REVIEW / DECISION] Bo → Giho · #22 Final Evaluation Protocol — บันทึกคำต่อคำ

**ที่มา:** Gift ส่งต่อทางแชต 7 ต.ค. 2569 (ไม่ได้โพสต์ใน Issue) · บันทึกไว้ที่นี่เพื่อ audit trail · Giho ไม่แก้ถ้อยคำ
**ตอบ:** handoff #22 คอมเมนต์ `6029168203` (`final-eval-protocol-1.0.0`)
**ผลต่อเอกสาร:** ออก `final-eval-protocol-1.0.1` (`FINAL_EVAL_PROTOCOL_1.0.1.md`)

---

รับงานรอบนี้เกือบทั้งหมด แต่ยัง ไม่อนุญาตให้เริ่ม draw final set จนกว่าจะออก protocol รุ่น `1.0.1` ตามคำตัดสินด้านล่าง

**1. Second-review proportion — ACCEPT**
ใช้ 25% เป็นค่าตายตัวของ independent second review ได้ เพราะอยู่กึ่งกลางช่วง 20–30% ที่ตัดสินไว้แล้ว
ต้องทบทวน:
* 25% ของ gold items ตามวิธีสุ่มที่ประกาศไว้ล่วงหน้า
* บวกทุก REFERRED / ambiguous case

ถ้ารายการหนึ่งเข้าได้ทั้งสองกลุ่มให้นับครั้งเดียว

**2. คำว่า "ก่อน freeze" — CLARIFY / ACCEPT**
ให้ตีความว่า: ก่อน Gold Truth ถูก finalize + sealed
ไม่ใช่ protocol freeze และไม่ใช่ engine freeze
ลำดับคือ: primary annotation → second review → adjudication → Gold Truth freeze/seal → blind run
หลัง seal ห้ามแก้เฉลยจากผลของระบบ

**3. Engine freeze timing — REJECT การเลื่อนไปก่อน unlock**
คงหลักเดิมที่เข้มกว่า:
engine ต้องถูก integrate + regression + freeze/tag ก่อน actual draw ของ final set และก่อน identity ของหน่วยที่ถูกเลือกถูกเปิดเผยต่อผู้พัฒนา engine
เหตุผล: แม้ยังไม่เห็นเนื้อหาไฟล์ การรู้ว่าหน่วยใดถูกเลือกก็อาจทำให้ปรับ rule/template handling ให้เข้ากับหน่วยนั้นได้
ดังนั้นลำดับ operational ที่ถูกต้อง:
#5 gate integrated
* #21 guard integrated

→ full regression → freeze engine tag/hash → build eligible pool จาก metadata เท่านั้น → fixed-seed stratified draw → seal selected files → Gold Truth process → unlock → blind run
หากจำเป็นต้องสร้าง eligible pool ก่อน engine freeze ทำได้ เพราะใช้ metadata/public source เท่านั้น แต่ ห้าม draw / reveal selected identities ก่อน engine freeze

**4. Engine readability — ACCEPT**
ความสามารถของ engine ในการอ่านไฟล์ ไม่ใช่ eligibility criterion
Eligibility ดูเฉพาะ external/source conditions ที่ประกาศไว้ เช่น:
* official source exists
* required Draft/Act stage exists
* required file format exists
* source identity/pairing ยืนยันได้จาก metadata
* file ไม่เสียในระดับ source/integrity

ถ้าไฟล์ valid ตาม source แต่ engine อ่านไม่ได้ตอน final run: นั่นเป็นผลของระบบ ไม่ใช่เหตุเปลี่ยนหน่วยหรือสุ่มใหม่
ต้องรายงานเป็น unable-to-process / referral / failure ตาม protocol ที่เกี่ยวข้อง

**5. Act-stage Excel / #27**
เห็นด้วยที่ไม่สมมติว่า Act Excel มีครบ
ให้ #27 สร้าง `Source Coverage Matrix` ก่อน แล้ว #22 ใช้ผลนั้นสร้าง eligible pool
ถ้า Draft↔Act Excel pair ผ่าน eligibility:
* ≥3 หน่วย → draw 3 ตาม strata
* =2 หน่วย → ใช้ 2 และประกาศ limitation
* <2 หน่วย → STOP ก่อน draw ห้ามลด eligibility และห้ามเปลี่ยน primary design เงียบ ๆ

ถ้า <2 ให้กลับมา Bo/Gift เพื่อออก protocol version ใหม่ก่อนเลือก alternative design
สามารถตรวจ feasibility จาก development units ที่ถูกใช้ไปแล้ว ได้ในระดับ source availability เพื่อดูว่า Act Excel มีจริงหรือไม่ แต่ห้ามนำ performance ของ development units มาแทน final evaluation

**6. ประเภทหน่วยงาน 13 ผู้สมัคร**
Gift ไม่ต้องยืนยันด้วยความจำหรือรายชื่อร่าง
ให้ #27 / registry ยืนยัน `agency_type` จาก official public metadata พร้อม provenance ก่อน draw
ใช้ค่า: `S-GOV` · `S-PO` · `TYPE_UNVERIFIED`
ถ้ายืนยันประเภทไม่ได้ ให้คง `TYPE_UNVERIFIED` และ ห้ามย้ายเข้า S-GOV/S-PO เพื่อให้ strata ลงตัว
ต้อง resolve ก่อน stratified draw หรือหยุดและรายงานจำนวนที่ยืนยันไม่ได้

**7. Versioning**
`final-eval-protocol-1.0.0` ที่ tag แล้ว ห้าม rewrite/delete
เพราะคำตัดสินข้อ 3 เปลี่ยนสาระ ให้สร้าง: `final-eval-protocol-1.0.1`
พร้อม forward note ว่า `1.0.0` superseded ก่อนมี final-set draw และไม่มีชุดจริงถูกเลือกภายใต้ 1.0.0

**สถานะหลังแก้**
#22 ให้ใช้คำว่า: READY TO BUILD ELIGIBLE POOL — ยังไม่ใช่ `READY TO DRAW FINAL SET`
เปลี่ยนเป็น `READY TO DRAW FINAL SET` เมื่อครบ:
* #27 source eligibility/agency type verified
* #5 + #21 อยู่ใน engine branch เดียวกัน
* regression ผ่าน
* engine tag/hash freeze แล้ว
* protocol 1.0.1 freeze แล้ว

จากนั้นจึง draw ด้วย seed ที่ตรึงไว้ โดยไม่เปิดเนื้อหาไฟล์ก่อนเลือก
ส่ง HANDOFF กลับพร้อม protocol 1.0.1 + integration/freeze status + #27 eligibility dependency เท่านั้น ยังไม่ต้อง draw ชุดจริง
