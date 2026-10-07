# #23 — HANDOFF รอบ 3: ตอบ Bo REVISE (6027478811) — attribute-context XSS regression + disposition SG-50

**ผู้ทำ:** Giho · **วันที่:** 7 ตุลาคม 2569 · **ตอบ:** Bo REVIEW `6027478811` (REVISE เล็กน้อยก่อน ACCEPT) · **สถานะ:** `READY FOR REVIEW`
**รอบ final อ้างอิง = `20261007T013505Z-final`** (แทน `20261006T231414Z-final` ซึ่งกลายเป็น before ของ F-09/F-10)

## 1. สิ่งที่ Bo ขอ → สิ่งที่ทำ

| Bo ขอ | ทำ | หลักฐาน |
|---|---|---|
| targeted regression ของ attribute context (quote-break · event-handler) บนจุดสะท้อนที่ ZAP พบ | `tests/test_security_gate_xss.py` — payload 7 แบบ: quote-break `"`/`'` · unquoted-attribute · tag break-out `<img onerror>` · `javascript:` · entity ที่เข้ารหัสมาก่อน (double-decoding) · percent-encoded ดิบ · ยิงลง **จุดที่ ZAP 10031 ชี้** (`/t1b/runs/{rid}/findings/{fid}?page=&per_page=`) + ตัวกรองคิวทั้ง 6 (`q flag ftype cat status only_review`) + `page_no` + จุด query อื่น (`/evidence/compare?run=&map=` · `/queue?q=` · `/t1b/runs?q=`) · **oracle ไม่ผูก implementation**: parse HTML จริง — ห้ามเกิด attribute `on*` · ห้าม URL attribute เป็น `javascript:` · ห้ามมี tag จาก payload · ห้าม 500 | `T:tests/test_security_gate_xss.py` 86 case |
| หรือพิสูจน์ central template escaping สำหรับ attribute context | static ทั้งโครง: `test_no_unquoted_attribute_interpolation_in_templates` (ทุก `{{ }}` ใน attribute ต้องอยู่ในเครื่องหมายคำพูด — ไม่งั้นแม้ escape ก็เติม attribute ใหม่ได้) · `test_no_event_handler_or_javascript_url_built_from_templates` · `test_markupsafe_escapes_both_quote_styles` (escape ทั้ง `"`→`&#34;` และ `'`→`&#39;`) | `T:tests/test_security_gate_static.py` |
| แล้วจึงลง disposition SG-50 | `12_SECURITY_VERIFICATION_GATE/dispositions.json` — SG-50 = `FALSE_POSITIVE` (10112 FALSE_POSITIVE ตามที่ Bo รับหลักการ · 10031 FALSE_POSITIVE พร้อมเหตุผล+หลักฐานข้างบน) · `proposed_by: Giho` · **`accepted_by` ว่าง** ⇒ runner ยังให้ SG-50 = REVIEW จนกว่า Bo/Gift จะกรอกชื่อรับ (กติกาใหม่ protocol §4 ข้อ 5) | `dispositions.json` · `control_results.json` |
| rerun เฉพาะส่วนที่จำเป็น + summary | รัน **ทั้งชุด** แทน (ประมาณ 3 นาที) เพราะ runner เป็น fail-closed — ข้ามขั้นใด ⇒ control ที่พึ่งขั้นนั้นกลายเป็น REVIEW ทั้งแถว สรุปรอบจะอ่านไม่ได้ · ไม่ขยาย active scan | `runs/20261007T013505Z-final/` |

## 2. สิ่งที่พบระหว่างทำ (ก่อนแก้ → หลังแก้)

| id | สิ่งที่พบ (before = `20261006T231414Z-final` / รอบ test ก่อนแก้) | severity | การแก้ | after |
|---|---|---|---|---|
| **F-09** | `page`/`per_page` ที่ไม่ใช่จำนวนเต็มบนหน้ารายละเอียด finding ⇒ `ValueError` ⇒ **500** (หน้า 500 ทั่วไป ไม่สะท้อนค่า แต่ไม่ fail-safe · 14/14 case ของ payload ล้มที่ข้อนี้) | Low | แปลงเป็น int ในบล็อก try ⇒ **400** หน้าข้อผิดพลาดมาตรฐาน | `20261007T013505Z-final`: 14/14 PASS |
| **F-10** | พารามิเตอร์ที่ FastAPI ตรวจชนิดเอง (เช่น `page_no: int`) เมื่อผิดชนิด ⇒ ค่าปริยาย **JSON 422 ที่สะท้อนค่าที่ส่งมา** (ฟิลด์ `input`) · content-type JSON + nosniff จึงไม่ใช่ XSS แต่ขัดหลัก "ไม่สะท้อนอินพุตในหน้าข้อผิดพลาด" | Low | handler `RequestValidationError` ⇒ หน้า 400 มาตรฐาน ไม่สะท้อนค่า | `20261007T013505Z-final`: `test_queue_pagination_non_int_fails_safely` PASS |
| T-08 (observation) | test เดิมของเลนหลักฐาน `test_log_has_no_document_text_or_paths` ล้มเมื่อรันหลัง `test_security_gate_web` ในโปรเซสเดียวกัน — เพราะข้อความ 404 ของแอป "ไม่พบรอบทะเบียน**ตัวชี้วัดที่**ระบุ" ไหลลงล็อกร่วม แล้ว test นั้นถือคำว่า "ตัวชี้วัดที่" เป็นข้อความเอกสาร | — | ไม่แก้ (ไม่ใช่เลนนี้ · ลำดับปกติของ pytest ไม่ชน) — แจ้งไว้ให้เจ้าของเลนหลักฐาน | — |

**ข้อสรุปต่อ alert 10031:** จุดสะท้อนทุกจุดที่ตรวจ ค่าผู้ใช้ไปอยู่ใน attribute ที่มีเครื่องหมายคำพูดครอบและผ่าน autoescape (escape ทั้งสอง quote) · ค่าที่เป็นตัวเลขถูกแปลงเป็น int ก่อนประกอบ query string ฝั่งบริการ · ไม่มี template ใดสร้าง `on*=`/`javascript:` ⇒ ไม่พบ exploitability ⇒ เสนอ **FALSE_POSITIVE** (รอ Bo/Gift รับ)

## 3. ผลรอบ final `20261007T013505Z-final`

| ตัวชี้วัด | ค่า |
|---|---|
| controls ประกาศ / applicable | 51 / 48 |
| PASS / FAIL / REVIEW / N/A | **47 / 0 / 1 / 3** |
| REVIEW | SG-50: control แบบ manual — ต้องมี disposition ที่ผู้มีอำนาจรับแล้ว (เสนอแล้ว: FALSE_POSITIVE · ยังไม่มี accepted_by) |
| ZAP H/M/L/I | 0/0/0/2 |
| security regression (pytest ในขอบเขต matrix) | 316 passed · 0 failed · 0 error · 0 skipped |
| dependency vulns ณ วันที่รัน | 0 · ตรวจได้ 41/43 |
| leak_check ชุดหลักฐาน | ตรวจครบ 0 hit · `sha256sum -c` ผ่าน · ไม่มี CR |
| suite เต็ม repo ระบบ | 1650 passed · 5 skipped (เครื่องผู้พัฒนา · ไม่มี CI) |

## 4. ขอจาก Bo / Gift

1. **Bo:** ACCEPT regression + disposition ที่เสนอ หรือระบุ payload/จุดสะท้อนเพิ่มที่ต้องการ
2. **Gift:** ถ้า ACCEPT ให้กรอก `accepted_by`/`accepted_date` ใน `dispositions.json` (หรืออนุญาตให้ Giho กรอกแทนโดยอ้าง comment id) แล้ว Giho จะรันรอบ final ปิดท้ายให้ SG-50 เป็น PASS ตามกติกา — จึงจะเรียก "READY FOR FINAL SECURITY EVALUATION" ได้ครบ 9 ข้อของ Gate ในใบ
