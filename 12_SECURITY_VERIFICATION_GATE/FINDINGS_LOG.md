# FINDINGS LOG — Security Gate (#23)

**กติกา:** append-only · finding ที่ทำให้แก้โค้ดต้องมี run ที่พบ (before) และ run ที่ยืนยัน (after) · ห้ามแก้ผล before ย้อนหลัง ·
severity ใช้ชุดเดียวกับ ZAP (`High | Medium | Low | Informational`) · disposition ∈ `FIXED | ACCEPTED_RISK | FALSE_POSITIVE | REVIEW_REQUIRED`

> 🔴 ทุกรายการในตารางนี้พบจากรอบ **formative** บน target สังเคราะห์ · ห้ามอ้างเป็นผลประเมินสุดท้าย — ผลสุดท้ายอยู่ที่ `runs/20261006T172344Z-final/`

## รอบที่อ้างถึง

| run id | phase | matrix sha256 | หมายเหตุ |
|---|---|---|---|
| `20261006T165937Z-formative` | formative (before) | `38d4bdf8…` (เนื้อหาเดียวกับ `36b5230a…` ต่างเฉพาะ line ending CRLF→LF ที่ตรึงใน `68ce555`) | รอบแรกหลังเขียน matrix · ยังไม่แก้โค้ด |
| `20261006T171428Z-final` | final · **SUPERSEDED** (T-04) | `36b5230a…` | สถานะ control เท่ากับรอบถัดไป แต่แฮชไฟล์ตรวจย้อนไม่ได้ (CRLF) |
| `20261006T172053Z-final` | final · ไม่เผยแพร่ | `36b5230a…` | ขั้น L ล้มจากรูปแบบปลอมใน PNG (T-05) — เก็บเฉพาะในเครื่อง |
| `20261006T172344Z-final` | **final (after · อ้างอิง)** | `36b5230a…` | หลัง commit การแก้ทั้งหมด + T-04/T-05 · `sha256sum -c` ผ่าน · ไม่มี CR |

## finding ที่ทำให้แก้โค้ด (before → after)

| id | control | severity | สิ่งที่พบ (before) | การแก้ | after | disposition |
|---|---|---|---|---|---|---|
| **F-01** | SG-43 (DNS rebinding · ใกล้เคียง V4.1.3) | **Medium** | คำขอที่หัว `Host: evil.example` (และ `evil.example:8600`) ได้ **200** — เว็บแอปบน loopback ไม่ตรวจ Host ⇒ โดเมนของผู้โจมตีที่ resolve มาที่ 127.0.0.1 อ่าน response ข้ามไซต์ได้ (SameSite cookie ไม่กันกรณีนี้) | รายการอนุญาต `ALLOWED_HOSTS` (127.0.0.1 · localhost · [::1] · โฮสต์ที่ตั้งค่า · `REDBOOK_ALLOWED_HOSTS`) ตรวจใน `SecurityMiddleware` ก่อนทุกอย่าง · ปฏิเสธ 400 พร้อม security headers · บันทึก `host_rejected` | `20261006T172344Z-final`: H:host.allowlist PASS · test 3 กรณี PASS | FIXED |
| **F-02** | SG-39 (V16.3.3 / error page) | **Low** | หน้า **500** (unhandled exception) ออกไป **โดยไม่มี** CSP · nosniff · no-store — เพราะ handler ของ `Exception` ทำงานในชั้น ServerErrorMiddleware ซึ่งอยู่นอก `SecurityMiddleware` · เนื้อหาหน้าไม่รั่ว (ข้อความทั่วไป + error_id) แต่ขาดชั้นป้องกันเบราว์เซอร์ | handler ใส่ `SECURITY_HEADERS` ลง response เอง | `20261006T172344Z-final`: test_unhandled_exception_renders_generic_500_page PASS | FIXED |
| **F-03** | SG-20 (V5.2.3) | **Low** | ถุง zip ถูกตรวจขนาดคลายอัดและอัตราขยาย แต่ **ไม่จำกัดจำนวนสมาชิก** (มาตรฐานต้องการเพดานจำนวนไฟล์ก่อนคลาย) | `MAX_ZIP_MEMBERS = 5000` · เกิน ⇒ `upload_rejected_zip_too_many_members` | `20261006T172344Z-final`: test_zip_with_too_many_members_is_rejected PASS | FIXED |
| **F-04** | SG-29 (V3.4.5) | **Low** | หัว HTTP `Referrer-Policy: same-origin` แต่ทุกหน้ามี `<meta name="referrer" content="no-referrer">` — meta มีผลเหนือหัว ⇒ นโยบายที่ใช้จริงไม่ใช่ที่ประกาศ (และเป็นต้นเหตุเดิมของ `Origin: null` 23 ก.ย.) | meta เปลี่ยนเป็น `same-origin` ให้ตรงหัว | `20261006T172344Z-final`: H:headers.referrer PASS (meta_mismatch = 0) | FIXED |
| **F-05** | SG-42 (V13.4.6 · L3) | **Informational** | response มีหัว `Server: uvicorn` เปิดเผยผลิตภัณฑ์ของส่วนประกอบเบื้องหลัง | `uvicorn_options()` ส่วนกลาง (`redbook/web/launch.py`) ตั้ง `server_header=False` — ใช้ร่วม run_local · demo · target | `20261006T172344Z-final`: H:headers.server PASS | FIXED |

## finding ที่ยัง **ไม่ปิด** (ต้องการคำตัดสิน)

| id | control | severity | สิ่งที่พบ | ทางเลือก | disposition ปัจจุบัน |
|---|---|---|---|---|---|
| **F-06** | SG-16 (V1.5.1) | **Low** | `.venv` ของแอปไม่มี `defusedxml` ⇒ openpyxl ใช้ parser มาตรฐาน · การทดสอบ XXE (entity ภายนอก) **ไม่พบการเรียกออกเครือข่ายและไม่ล่ม** แต่ขาดชั้นป้องกันตามมาตรฐาน | (ก) ติดตั้ง `defusedxml` ลง `.venv` และตรึงใน `requirements.lock.txt` แล้วรันรอบ final ใหม่ · (ข) ยอมรับความเสี่ยงโดยอ้างผลทดสอบ XXE | **REVIEW_REQUIRED** — ประกาศใน `requirements.txt` แล้ว · การแก้สภาพแวดล้อมประเมินต้องได้รับอนุญาตก่อน (คำสั่งเดิมของ Bo: ไม่แตะ `.venv`) |
| **F-08** | SG-50 (ZAP) | — | เครื่องพัฒนาไม่มี Java และ Docker ⇒ ZAP baseline รันไม่ได้ · สถานะ `INCOMPLETE` ⇒ SG-50 = REVIEW | (ก) ติดตั้ง JRE + ZAP cross-platform (ระดับผู้ใช้) · (ข) ใช้เครื่องอื่น/Docker · (ค) เลื่อน | **REVIEW_REQUIRED** — รอกิ๊ฟอนุญาตติดตั้ง |

## finding ต่อตัว gate เอง (tooling)

| id | สิ่งที่พบ | การแก้ |
|---|---|---|
| **F-07** | รอบ formative: `leak_check` บนชุดหลักฐานพบ 3 จุด — เส้นทางสมมติ `C:\\Users\\…` ในซอร์สของ test ที่ล้ม (traceback ใน stdout/junit) หลุดตัวกลบ เพราะ regex ไม่รองรับ backslash คู่ | ตัวกลบรองรับ `[\\/]+` · fixture เปลี่ยนเป็นไดรฟ์สมมติ `Q:\synthetic_home\…` · เพิ่ม test กรณี backslash คู่ · ⇒ **ยืนยันว่าขั้น L (fail-closed) ทำงานจริง**: หลักฐานที่มีเส้นทางเครื่องถูกบล็อกก่อนเผยแพร่ |
| **T-01** | test spec: `/indicators/exports/{name}` ตอบ **410** โดยออกแบบ (เส้นทางเดิมเลิกใช้ · P4-2) แต่ test รับเฉพาะ 400/404 | test รับ 410 ด้วย (fail-closed เช่นกัน) — ไม่ใช่การแก้โค้ดผลิตภัณฑ์ |
| **T-02** | `pip-audit` ไม่รายงาน `skip_reason` ของรายการที่ข้าม (40 ตรวจได้ จาก 42) ⇒ runner นับ skipped = 0 ผิด | นับจากส่วนต่าง input − audited |
| **T-04** | runner เขียนไฟล์ข้อความแบบ CRLF (ค่าปริยายของ Windows) ขณะที่โฟลเดอร์หมวดนี้ตรึง `eol=lf` ⇒ แฮชใน `HASHES.sha256` ของ run-01/run-02 **ไม่ตรงกับไฟล์ที่คน checkout ได้** · และ manifest ถูกเขียนซ้ำหลังคำนวณแฮชจึงไม่มีวันตรง | เขียน LF เสมอ (รวม raw ของ pip-audit) · HASHES ยกเว้น manifest+ตัวเอง · manifest เก็บแฮชของ HASHES · **รอบ final ที่อ้าง = run ที่สร้างหลังแก้นี้** (run ก่อนหน้าคงไว้เป็นประวัติ · ติดป้าย SUPERSEDED) |
| **T-05** | `leak_check` 0.3.x ถอดไบต์ของ PNG เป็นข้อความแล้วเจอรูปแบบ UNC ปลอม 1 จุด (รอบ `20261006T172053Z-final`) ⇒ ขั้น L ล้มโดยไม่มีสาระ | ไม่เก็บภาพหน้าจอในชุดหลักฐาน (หลักฐานขั้นเบราว์เซอร์คือ JSON) — ข้อสังเกตสำหรับ #17: ไฟล์ไบนารีแท้ (PNG) ควรยกเว้นรูปแบบ Z3 หรือเทียบ magic bytes |
| **T-03** | `pip-audit` runner เทียบชื่อแพ็กเกจที่มี `.` กับผลลัพธ์ที่ใช้ `-` ไม่ตรง ⇒ พิมพ์ `pdfminer.six` ในรายการข้ามทั้งที่ตรวจแล้ว (ตัวเลข audited 40/42 ถูกต้อง · รายการชื่อผิด) | normalize `.`→`-` ด้วย · ไม่รันรอบ final ซ้ำ — บันทึกไว้ตรง ๆ ว่ารายการชื่อใน run นี้มีข้อผิดนี้ |
