# #28 — รายงานตรวจ shared log (`app.log`) ของเว็บแอป — 7 ตุลาคม 2569

**ผู้ทำ:** Giho · **ตอบ:** Bo REVIEW #23 รอบ 3 (บันทึกที่ #23 คอมเมนต์ `6030358199`) · **สถานะ:** `READY FOR REVIEW`
**ป้าย:** `SYNTHETIC ONLY` · ไม่มี active scan · ไม่แตะส่วนอื่นของ #23

## 1. คำถามของ Bo → คำตอบจากหลักฐาน

| คำถาม | คำตอบ | หลักฐาน |
|---|---|---|
| ข้อความที่เข้า shared log เป็น static text เท่านั้น หรือมาจาก user-controlled/document content? | **ผสม** — ข้อความ `detail=` เป็น static ของแอป (เช่น "ไม่พบงานตรวจที่ระบุ") **แต่ `path=` ของคำขอที่ล้มเหลวเป็น user-controlled** และถูกบันทึกตามที่ส่งมา (หลังชั้น URL ของ Starlette) · query / header (UA · Referer · Host) / ฟิลด์ฟอร์ม / ชื่อไฟล์อัปโหลด / โทเคน **ไม่เข้า**ล็อก · เนื้อหาเอกสาร (บรรทัดที่สกัดจาก PDF) **ไม่เข้า**ล็อก | probe สังเคราะห์ (marker 8 ชนิด) → `test_request_path_is_logged_sanitized_but_query_headers_and_form_are_not` · taint test ใหม่ของเลนหลักฐาน |
| long-lived process ทำให้ค่าจาก request ก่อนหน้าไหลเข้า log ที่ไม่ควรมีได้ไหม? | **ได้ในความหมายนี้:** ล็อกเป็นไฟล์ร่วมของโปรเซส — path ของ request ก่อนหน้า (ที่ล้มเหลว) อยู่ในไฟล์เดียวกับ request ถัดไปเสมอ นี่คือกลไกที่ทำให้ test ของเลนหลักฐานล้ม (ข้อความ 404 ของ **แอป** "ไม่พบรอบทะเบียนตัวชี้วัดที่ระบุ" จาก request ของชุด security ถูกนับเป็น "ข้อความเอกสาร" โดย match คำกว้าง `ตัวชี้วัดที่`) · **ไม่ใช่** ค่าจาก request หนึ่งไหลเข้าไปในบรรทัดของอีก request | รัน `test_security_gate_web.py` → `test_evidence_routes.py` ซ้ำได้ทุกครั้ง · บรรทัดที่ชนอ้างอิง path `/indicators/runs/zz-unknown/verify` (ของ test security) |
| query/path/document text สะท้อนลง log ได้ไหม? | **path ได้** (โดยตั้งใจ เพื่อวินิจฉัย) · **query/document text ไม่ได้** · 🔴 **พบ F-11**: อักขระ `U+2028` (LINE SEPARATOR) ใน path ผ่านชั้น URL มาได้ (CR/LF ถูกตัดโดย Starlette แต่ U+2028/2029 ไม่ถูกตัด) ⇒ สร้าง**บรรทัดปลอม**ในล็อกได้ (log injection) · และข้อความไม่มีเพดานความยาว (path 20,000 ตัวอักษรลงล็อกทั้งก้อน) | before: `test_log_lines_are_never_forged_by_control_chars_in_request` FAIL (บรรทัดไม่ขึ้นต้นด้วย timestamp: `ls_9c6 detail=…`) · `test_oversized_path_is_truncated_in_log` FAIL |

**ข้อสรุป:** กรณีที่ Bo ยกมาเป็น **lexical collision ของข้อความ static** จริง (พิสูจน์แล้ว) **แต่** การสืบต่อพบช่องทาง user-controlled → log ที่เป็นของจริงหนึ่งข้อ (F-11 · Low) ⇒ ทำทั้งสองทาง: ปรับ test เดิมเป็น taint-based **และ** แก้โค้ด + regression

## 2. การแก้ (F-11 · Low · FIXED)

- `RedactingFormatter` (ตัวจัดรูปแบบล็อกส่วนกลางที่ทุก `log.*` ผ่าน) กลบอักขระควบคุมทั้งหมด `[\x00-\x1f\x7f  ]` ในข้อความ**ก่อน**ประกอบบรรทัด (แทนด้วย `\xNN` ที่อ่านออก) · traceback ที่ logging แนบเองยังขึ้นบรรทัดใหม่ตามปกติ
- จำกัดความยาวข้อความหนึ่งรายการ 4,000 ตัวอักษร (`…[truncated]`)
- **ไม่เปลี่ยน**ว่า path เข้าล็อก — เป็นข้อมูลวินิจฉัยที่จำเป็น · ประกาศขอบเขตไว้ใน regression ("path เข้าได้ query/header/ฟอร์ม/ชื่อไฟล์ไม่เข้า") และใน matrix 0.1.2 (SG-46)

## 3. การปรับ test เลนหลักฐาน (Bo ขอ "ตรวจ source/taint ที่ถูกต้อง")

`tests/test_evidence_routes.py::test_log_has_no_document_text_or_paths` — เลิก match คำกว้าง `ตัวชี้วัดที่` ⇒ สกัดบรรทัดจาก PDF สังเคราะห์ทั้งสองฉบับด้วย backend ของแอป (บรรทัดยาว ≥ 8 ตัวอักษร) แล้วยืนยันว่า**ไม่มีบรรทัดใด**อยู่ในล็อก · ยังตรวจเส้นทางโฟลเดอร์และ run id ตามเดิม · รันร่วมกับชุด security ในโปรเซสเดียว **ผ่าน** แล้ว (68 passed)

## 4. regression ที่เพิ่ม (`tests/test_security_gate_logging.py` · นับใน matrix 0.1.2 SG-46)

| test | พิสูจน์ |
|---|---|
| `test_log_lines_are_never_forged_by_control_chars_in_request` | path/path-param ที่มี `%0d%0a` · `%09` · `%00` · `%1b` · `%E2%80%A8` ⇒ ทุกบรรทัดล็อกยังขึ้นต้นด้วย timestamp · ไม่มีอักขระควบคุมในไฟล์ |
| `test_request_path_is_logged_sanitized_but_query_headers_and_form_are_not` | ขอบเขตที่ประกาศ: path เข้า · query/UA/Referer/ฟอร์ม/โทเคนผิด/ชื่อไฟล์อัปโหลด **ไม่เข้า** |
| `test_oversized_path_is_truncated_in_log` | path 20,000 ตัวอักษร ⇒ บรรทัด < 5,000 และมี `[truncated]` |

## 5. ข้อจำกัด

- probe/regression ครอบเฉพาะจุดที่ `log.*` ถูกเรียกใน `redbook/` ปัจจุบัน (11 จุด · ตรวจรายการแล้ว: path · id ของระบบ · ชื่อชนิด exception · ตัวเลข) — จุดใหม่ในอนาคตได้ความคุ้มครองจาก formatter ส่วนกลางโดยอัตโนมัติเฉพาะเรื่องอักขระควบคุม/ความยาว/เส้นทางสัมบูรณ์ ไม่ใช่เรื่อง "ห้ามใส่ข้อมูลผู้ใช้" ซึ่งต้องดูราย call
- access log ของ uvicorn (stdout) อยู่นอกขอบเขตไฟล์ `app.log` — ไม่ได้ตรวจในใบนี้
