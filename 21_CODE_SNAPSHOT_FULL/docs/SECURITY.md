# ความปลอดภัย — RedBook Verify

เอกสารนี้เป็นฐานของ **Phase 5 — Security Verification**
สถานะปัจจุบัน: มาตรการที่ทำแล้วใน Phase 1 พร้อมกรณีทดสอบอัตโนมัติ
**ยังไม่ได้รัน OWASP ZAP** (คำสั่งที่จะใช้อยู่ท้ายเอกสาร)

---

## 1. มาตรการที่ทำแล้ว (Phase 1)

| ข้อกำหนด | สิ่งที่ทำ | ที่ | ทดสอบโดย |
|---|---|---|---|
| ตรวจชนิดไฟล์จริง ไม่เชื่อนามสกุล | อ่าน magic bytes (`%PDF-` / `PK\x03\x04`) และตรวจโครงสร้างภายในถุง zip ว่ามี `[Content_Types].xml` และ `xl/workbook.xml` จริง · ไม่เชื่อ Content-Type จากเบราว์เซอร์ | `storage/files.py: detect_kind` | `test_detects_real_type_not_extension`, `test_rejects_disguised_executable`, `test_rejects_html_masquerading_as_pdf`, `test_rejects_zip_that_is_not_xlsx` |
| จำกัดขนาดไฟล์ | นับไบต์ระหว่างสตรีมและตัดทันทีที่เกิน (ค่าเริ่มต้น 80 MB, ตั้งด้วย `REDBOOK_MAX_UPLOAD_MB`) | `storage/files.py: save_stream` | `test_enforces_size_limit` |
| กัน zip bomb | ตรวจขนาดหลังคลายบีบอัดรวม (≤ 2 GB) และอัตราขยาย (≤ 250 เท่า) ก่อนให้ openpyxl เปิด | `storage/files.py` | ครอบคลุมโดยเส้นทาง `detect_kind` |
| สร้างชื่อไฟล์ภายในใหม่ | `uuid4().hex` + นามสกุลตามชนิดที่ตรวจได้ ชื่อเดิมเก็บเป็นข้อความในฐานข้อมูลเท่านั้น | `storage/files.py` | `test_accepts_real_xlsx_and_renames_internally` |
| ป้องกัน path traversal | ไม่เคยนำชื่อจากผู้ใช้มาประกอบ path · `_assert_inside()` ยืนยันว่า path ปลายทางอยู่ใต้โฟลเดอร์ที่กำหนด · `path_for()` ปฏิเสธชื่อที่มี `/`, `\`, `..` | `storage/files.py` | `test_path_for_blocks_traversal` (4 กรณี) |
| ป้องกัน XSS | Jinja2 autoescape เปิด · CSP `default-src 'none'` และ `script-src 'self'` · ไม่มี inline script/style · ตัดอักขระควบคุมออกจากชื่อไฟล์ที่แสดง | `web/security.py`, templates | `test_uploaded_filename_is_escaped_in_html` |
| ป้องกัน CSRF | double-submit cookie (`SameSite=Strict`, `HttpOnly`) + ตรวจ Origin/Referer เทียบ Host ทุกคำขอที่เปลี่ยนสถานะ | `web/security.py: verify_csrf` | `test_post_without_csrf_is_rejected`, `test_post_with_wrong_csrf_is_rejected`, `test_cross_origin_post_is_rejected` |
| ป้องกัน SQL injection | ทุกคำสั่ง SQL ใช้ parameter binding ไม่มีการต่อสตริงจากค่าที่ผู้ใช้กรอก | `storage/repository.py` | ตรวจด้วยการอ่านโค้ด (ทุก `execute` ใช้ `?`) |
| ไม่แสดง stack trace หรือ path ภายใน | exception handler กลางแปลงทุกข้อผิดพลาดเป็นหน้าเดียวพร้อม `error_id` รายละเอียดลงล็อกบนเครื่อง | `app.py: fail`, `unhandled` | `test_rejected_upload_shows_safe_message_only`, `test_not_found_page_has_no_internals` |
| ปิดหน้าที่ไม่จำเป็น | `/docs`, `/redoc`, `/openapi.json` ปิดทั้งหมด | `app.py: FastAPI(docs_url=None, …)` | `test_api_docs_are_disabled` |
| ไม่เก็บ secret ในซอร์ส | ไม่มี secret ในระบบ · CSRF token สุ่มต่อ session ด้วย `secrets.token_urlsafe` · ค่าตั้งทั้งหมดมาจาก environment variable | `web/security.py`, `config.py` | ตรวจด้วยการอ่านโค้ด |
| จำกัดการเข้าถึง | ผูก `127.0.0.1` เท่านั้น เครื่องอื่นในวงแลนเรียกไม่ได้ | `config.BIND_HOST`, `run_local.py` | — |
| จัดการไฟล์ชั่วคราว | เขียนลง `.data/tmp/` ก่อน แล้วย้าย · ลบทันทีเมื่อผิดพลาด · ล้างไฟล์ค้างทุกครั้งที่แอปเริ่มทำงาน | `storage/files.py: save_stream`, `purge_temp` | — |
| ไฟล์ต้นฉบับต้องไม่ถูกแก้ | ตั้งสิทธิ์ไฟล์ที่เก็บเป็นอ่านอย่างเดียว · ชั้น readers เปิดไฟล์โหมด `rb` เท่านั้น · ทั้งแพ็กเกจห้ามเรียก `.save()` | `storage/files.py`, `readers/` | `test_reading_does_not_modify_source`, `test_readers_open_files_read_only`, `test_no_workbook_save_calls_anywhere_in_package` |
| บันทึกเหตุการณ์ด้านความปลอดภัย | ตาราง `security_events` + แสดงในหน้า Audit Trail (ไฟล์ถูกปฏิเสธ · CSRF ไม่ผ่าน · path traversal) | `storage/audit.py` | `test_security_events_recorded` |
| Audit Trail แก้ย้อนหลังไม่ได้ | trigger ระดับฐานข้อมูลห้าม UPDATE/DELETE + สายโซ่แฮช SHA-256 ตรวจได้ | `storage/db.py`, `storage/audit.py` | `test_update_and_delete_are_blocked`, `test_tampering_is_detected` |
| local-first | ทดสอบห้าม import ไลบรารีเครือข่ายในแพ็กเกจ · CSP ปิดการเรียกออกทุกทาง | `tests/` | `test_no_outbound_network_libraries` |

### Security headers ที่ส่งทุก response

```
Content-Security-Policy: default-src 'none'; base-uri 'none'; form-action 'self';
                         frame-ancestors 'none'; script-src 'self'; style-src 'self';
                         img-src 'self' data:; font-src 'self'; connect-src 'self';
                         object-src 'none'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: geolocation=(), microphone=(), camera=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
Cache-Control: no-store
```

---

## 2. สิ่งที่ยังไม่ได้ทำ (ต้องทำใน Phase 5 หรือก่อนใช้งานจริง)

| # | ประเด็น | หมายเหตุ |
|---|---|---|
| 1 | **ยังไม่มีการยืนยันตัวตน** ระบบเป็นผู้ใช้เดี่ยวบน loopback ใครเปิดเครื่องได้ก็ใช้ได้ | ยอมรับได้ในระยะต้นแบบ แต่ต้องระบุในเล่มว่าเป็นข้อจำกัด |
| 2 | ยังไม่ได้เข้ารหัสไฟล์ที่เก็บใน `.data/uploads/` | พึ่ง BitLocker/สิทธิ์ระดับ OS |
| 3 | ยังไม่มีนโยบายลบไฟล์อัตโนมัติเมื่อครบกำหนด | ควรกำหนดรอบการลบใน Phase 4–5 |
| 4 | ยังไม่ได้รัน ZAP baseline / active scan | คำสั่งอยู่ข้อ 4 |
| 5 | openpyxl แกะ XML ภายใน .xlsx — ความเสี่ยง XXE ต่ำเพราะ `xml.etree.ElementTree` ของ Python ไม่ขยาย external entity แต่ยังไม่ได้ทดสอบด้วยไฟล์โจมตีจริง | เพิ่มกรณีทดสอบใน Phase 5 |
| 6 | ยังไม่ได้ทดสอบ rate limit / DoS จากไฟล์ที่ทำให้ parser ช้ามาก | เพิ่มในกรณีทดสอบ Phase 5 |

---

## 3. Dependency inventory

ระบุ ณ 26 ส.ค. 2569 · Python 3.12.9 · virtualenv `.venv` ในโครงการ

### ที่ประกาศใช้โดยตรง (`requirements.txt`)

| แพ็กเกจ | เวอร์ชัน | ใช้ทำอะไร |
|---|---|---|
| fastapi | 0.141.1 | เว็บเฟรมเวิร์ก |
| uvicorn[standard] | 0.52.4 | เว็บเซิร์ฟเวอร์ |
| jinja2 | 3.1.6 | เรนเดอร์หน้าเว็บ (autoescape) |
| python-multipart | 0.0.32 | รับไฟล์อัปโหลด |
| openpyxl | 3.1.5 | อ่านไฟล์ Excel (อ่านอย่างเดียว) |
| pytest | 9.1.1 | ชุดทดสอบ (dev) |
| httpx | 0.28.1 | ไคลเอนต์สำหรับชุดทดสอบเท่านั้น (dev) — **ไม่ถูก import ในแพ็กเกจ `redbook`** |

### ที่ติดมาเป็น dependency ต่อเนื่อง

`annotated-doc 0.0.5` · `annotated-types 0.8.0` · `anyio 4.14.2` · `certifi 2026.7.22` ·
`click 8.4.2` · `colorama 0.4.6` · `et_xmlfile 2.0.0` · `h11 0.16.0` · `httpcore 1.0.9` ·
`httptools 0.8.0` · `idna 3.19` · `iniconfig 2.3.0` · `MarkupSafe 3.0.3` · `packaging 26.3` ·
`pluggy 1.6.0` · `pydantic 2.13.4` · `pydantic_core 2.46.4` · `Pygments 2.21.0` ·
`python-dotenv 1.2.3` · `PyYAML 6.0.3` · `starlette 1.6.0` · `typing-inspection 0.4.4` ·
`typing_extensions 4.16.0` · `watchfiles 1.2.0` · `websockets 17.0.1`

**ไม่มีแพ็กเกจ JavaScript / npm ในระบบ** — หน้าเว็บเรนเดอร์จากเซิร์ฟเวอร์ทั้งหมด

สร้างรายการนี้ใหม่ด้วย:

```
.venv\Scripts\python.exe -m pip freeze | sort
```

---

## 4. คำสั่ง OWASP ZAP (เตรียมไว้ ยังไม่ได้รัน)

### 4.1 Baseline Scan (ปลอดภัย ไม่ยิงคำขอที่เปลี่ยนข้อมูล)

รันแอปไว้ก่อน แล้วสั่งจาก PowerShell (ต้องมี Docker Desktop):

```bash
docker run --rm -v "${PWD}/security/zap_reports:/zap/wrk:rw" -t zaproxy/zap-stable zap-baseline.py -t http://host.docker.internal:8600 -r zap_baseline.html -J zap_baseline.json -I
```

### 4.2 Active Scan — เฉพาะเครื่องทดสอบเท่านั้น

**ห้ามรันกับอินสแตนซ์ที่มีไฟล์ราชการจริงอยู่** ให้ชี้ `REDBOOK_DATA_DIR` ไปโฟลเดอร์ทดสอบเปล่าก่อน

```bash
docker run --rm -v "${PWD}/security/zap_reports:/zap/wrk:rw" -t zaproxy/zap-stable zap-full-scan.py -t http://host.docker.internal:8600 -r zap_active.html -J zap_active.json
```

เตรียมอินสแตนซ์ทดสอบเปล่า:

```bash
REDBOOK_DATA_DIR=<USER_HOME>\dev\redbook-verify\.data_zaptest .venv\Scripts\python.exe run_local.py
```

### 4.3 สิ่งที่คาดว่า ZAP จะรายงานและคำตอบที่เตรียมไว้

| สิ่งที่ ZAP มักแจ้ง | สถานะของระบบนี้ |
|---|---|
| Missing Anti-CSRF Tokens | มีแล้ว — ฟิลด์ `csrf_token` ในทุกฟอร์ม |
| CSP header not set | มีแล้ว (`default-src 'none'`) |
| X-Frame-Options / X-Content-Type-Options missing | มีแล้ว |
| Cookie without Secure flag | ตั้งใจ — ระบบทำงานบน `http://127.0.0.1` ไม่มี TLS · ถ้าจะให้บริการนอกเครื่องต้องเปิด TLS และตั้ง `secure=True` |
| Server leaks version | uvicorn ส่ง `server: uvicorn` — พิจารณาปิดใน Phase 5 |

---

## 5. เมื่อพบช่องโหว่

บันทึกตามรูปแบบนี้ใน `docs/SECURITY_FINDINGS.md` (สร้างเมื่อเริ่ม Phase 5):
รหัส · วันที่พบ · เครื่องมือที่พบ · ระดับ · หน้า/พารามิเตอร์ที่เกี่ยวข้อง · คำอธิบาย ·
การแก้ไข (commit) · วันที่สแกนซ้ำ · ผลสแกนซ้ำ
