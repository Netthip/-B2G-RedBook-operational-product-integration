# สัญญา JSON API ระหว่างหลังบ้านกับหน้าบ้าน Svelte (`/r/`)

รุ่นสัญญา: **api-contract-0.1 · หน้าบ้านตกลงครบ 5 ข้อแล้ว (26 ต.ค. 2569)**
เจ้าของเอกสาร: แชตหลังบ้าน (RedBook Verify Backend) · หน้าบ้าน = แชต "Budget Book Discovery/Verification UI"
ตัวช่วยฝั่งเซิร์ฟเวอร์: `redbook/web/api_common.py` (`read_json` · `api` · `ApiError` · `finding_json` · `finding_extras`)
เทสต์ที่บังคับสัญญา: `tests/test_api_parity.py` (วนทุกเส้นทาง `/api/` จริงของแอป + ตัวควบคุมว่าตัวตรวจจับเส้นทางไม่ปลอดภัยได้) ·
`tests/test_api_pdfpair.py` · `tests/test_api_trial.py` (ของหน้าบ้าน)

> หลักข้อเดียว: **API เป็นอีกทางเข้าของ service เดิม ไม่ใช่กติกาชุดใหม่**
> ทุกเส้นเรียก `redbook.services.*` ตัวเดียวกับหน้าเว็บเดิม · ด่าน CSRF / ล็อกผลผู้ตรวจ / ด่านก่อนส่งออก
> ต้องให้ผลเหมือนหน้าเดิมทุกกรณี และมีเทสต์ที่วนทุกเส้นทาง `/api/` บังคับไว้ (`tests/test_api_parity.py`)

## 1. ข้อตกลงร่วม

| เรื่อง | ข้อตกลง |
|---|---|
| ที่อยู่ | origin เดียวกับแอปเดิม · ขึ้นต้น `/api/` · JSON UTF-8 |
| GET | ไม่เปลี่ยนสถานะ (ยกเว้นเตรียมแคชเบื้องหลังแบบเดียวกับหน้าเดิม) |
| POST | เปลี่ยนสถานะ · ต้องมีหัว `X-CSRF-Token` = โทเคนจาก `GET /api/csrf` · ตรวจ Origin เหมือนฟอร์มเดิม · คุกกี้ `redbook_csrf` ยัง `HttpOnly` + `SameSite=Strict` |
| ขนาดคำขอ | body ไม่เกิน 64 KB (เกิน = 413 `too_large`) · บังคับระหว่างรับ: Content-Length เกิน = ปฏิเสธก่อนอ่าน · ไม่แจ้งความยาว = นับระหว่างรับแล้วหยุดทันที (ไม่สะสมเกินเพดาน) |
| ข้อผิดพลาด | `{"error": "<ข้อความภาษาคน กลบ path แล้ว>", "code": "<รหัส>"}` · ไม่มี stack trace / path |
| รหัส `code` | `csrf` 403 · `invalid` 400 · `not_found` 404 · `locked` 409 (ส่งผลแล้ว แก้ไม่ได้) · `not_locked` 409 (ยังไม่ส่งผล จึงยังไม่มีผลระบบ) · `gate` 409 (ด่านก่อนส่งออกไม่ผ่าน) · `superseded` 409 (รอบถูกแทน อ่านได้อย่างเดียว) · `conflict` 409 (สถานะเปลี่ยนระหว่างทาง เช่น ไฟล์เปลี่ยน/กดซ้ำ) · `too_large` 413 · `server` 500 (+ `error_id`) |
| ป้ายภาษาไทย | หลังบ้านส่ง **รหัส + ป้าย** เสมอ · หน้าบ้านแสดงป้ายจากเซิร์ฟเวอร์ ไม่เขียนป้ายเอง (ถ้อยคำเปลี่ยนได้ตามคำตัดสินโบ/กิ๊ฟ รหัสคงเดิม) |
| รุ่นเครื่องมือ | ทุกผลที่มาจากรอบเทียบมี `versions` (pdfbook · profile · profile_status · thai_repair · thai_pua_map · backend) + `profile_status_label` ให้แสดงป้าย "ยังปรับเทียบ" |
| ไฟล์ | ภาพ PNG / CSV / JSON สรุป **ใช้ URL เดิม** (GET ดาวน์โหลดตรง ผ่านด่าน + Audit เดิม): `/trial/s/{sid}/page/{side}/{n}.png` · `/trial/s/{sid}/summary.json` · `/pdfpair/runs/{rid}/f/{fid}/{A\|B}.png[?full=1]` · `/pdfpair/runs/{rid}/page/{A\|B}/{n}.png` · `/pdfpair/runs/{rid}/export.csv` |
| การเพิ่มฟิลด์ | เพิ่มฟิลด์ใหม่ได้โดยไม่ขึ้นรุ่นสัญญา (หน้าบ้านต้องไม่พังเมื่อเจอฟิลด์ที่ไม่รู้จัก) · ลบ/เปลี่ยนความหมายฟิลด์ = ขึ้นรุ่นสัญญา + แจ้งอีกฝั่งก่อน |
| หน้าบ้านรับมือรหัส | `csrf` → ขอโทเคนใหม่แล้วลองซ้ำ 1 ครั้ง · `locked`/`not_locked`/`superseded` → พาไปหน้าที่ถูก · `server` → แสดง `error_id` |
| คำขอพร้อมกัน | สายเทียบเล่ม (`/pdfpair/*` · `/api/pdfpair/*`) ทำงานที่บล็อกใน threadpool — ยิงหลายคำขอพร้อมกันได้ (ภาพ/prefetch ไม่ทำให้คำขอที่ผู้ใช้กดต่อคิว) · ด่านที่ต้องตรวจซ้ำเมื่อพร้อมกัน (รอบถูกแทน · เปลี่ยนค่าเดิมต้องมีหมายเหตุ) อยู่ในธุรกรรมเขียน · บังคับด้วย `tests/test_pdfpair_concurrency.py` |
| ป้าย | รหัส+ป้ายของโดเมน (ปากกา ผลยืนยัน หัวข้อ kind use_status การใช้ผล เหตุการณ์ Audit) มาจากเซิร์ฟเวอร์ · ถ้อยคำประกอบหน้าจอ (คำชี้แจง ปุ่ม หัวการ์ด) อยู่ฝั่งหน้าบ้าน |

## 2. วัตถุข้อสังเกต (Finding) — ใช้ทั้งสองสาย

```text
Finding = {
  id, topic, topic_label, kind, kind_label, subject, column,
  within: "A" | "B" | "",          // "" = เทียบสองฉบับ · "A"/"B" = ข้อภายในฉบับนั้น
  info: bool,                      // ข้อมูลประกอบ ไม่ต้องตัดสิน
  a: Side, b: Side,
  delta, delta_text, unit, note,
  caveats: [string],               // เหตุที่ต้องให้คนยืนยัน (หน่วย/คอลัมน์/ปี/ระบุตัวรายการ) — ต้องแสดงทุกที่ที่แสดงผล
  parts: [{label, value, raw, unit, page, flags: [code], flag_labels: [string]}],   // องค์ประกอบของผลรวม
  tolerance, tolerance_text,       // เกณฑ์ปัดเศษ ("" = ไม่ใช่กฎผลรวม) · อยู่ในเกณฑ์ ≠ ตรงเป๊ะ
}
Side = {value, raw, unit, unit_origin, unit_note, raw_note, status: "read"|"dash"|"blank"|"", amount_text,
        page, bbox: [x0,y0,x1,y1] | null, text, evidence_png: url | null}
        // amount_text ใช้หน่วยของข้อสังเกตเมื่อฝั่งนั้นไม่มีหน่วยของตัวเอง (เหมือน amount_text(f.a, f.unit) ในหน้าเดิม)
```

สายเทียบเล่มเพิ่ม `decision: {choice, choice_label, note, decided_at} | null` และ `use` (`usable`/`excluded`/`open`/`pending`/`info`) + `use_label`

## 3. สายทดลองตรวจเล่ม (#43) — `redbook/web/api_trial.py` (หน้าบ้านเริ่มไว้แล้ว)

มีอยู่แล้ว: `GET /api/csrf` · `GET /api/trial/meta` · `GET /api/trial/books` · `POST /api/trial/start` ·
`GET /api/trial/s/{sid}` · `POST …/marks` · `POST …/marks/{mid}` · `POST …/done` · `POST …/view` · `POST …/lock` ·
`GET …/result` · `POST …/link/{mid}` · `POST …/extra/{fid}` · `POST …/survey`

ด่านที่ต้องเหมือนหน้าเดิม (มีเทสต์):
- ก่อนล็อก: ไม่มีรอบเทียบ ไม่มีข้อสังเกต ไม่มี metrics — `result`/`link`/`extra` = 409 `not_locked` และ**ไม่สร้างรอบเทียบ**
- ล็อกต้องติ๊กยืนยัน + ตรวจครบทุกหน้า · หลังล็อกแก้จุด/หน้าไม่ได้ (`locked`)
- สรุปส่งออก = `GET /trial/s/{sid}/summary.json` เดิม (จำนวนเท่านั้น + Audit แฮช)

ตกลงแล้ว (เพิ่มอย่างเดียว):
- ข้อสังเกตใน `result` เติม `finding_extras(f)` (`kind_code` · `info` · `caveats` · `delta_text` · `tolerance` ·
  `tolerance_text` · `tolerance_basis` · `parts`) — โบขอให้ความไม่แน่ใจไปถึงจุดที่ใช้ผลจริง
- `POST /api/trial/s/{sid}/undone {page}` (หน้าบ้านเพิ่มใน `api_trial.py`) → `trial.page_undone(sid, "cur", page)` ·
  ยกเลิก "ตรวจหน้านี้แล้ว" ได้ **ก่อนส่งผลเท่านั้น** (หลังส่ง = `locked` 409) · ยังไม่เคยกด = ไม่ทำอะไร · มี Audit
  `trial_page_undone` · การล็อกตรวจครบทุกหน้าซ้ำในธุรกรรมเดียวกับการล็อก (กดยกเลิกแทรกไม่ได้)
- "ตรวจหน้านี้แล้ว" = ดูหน้านี้ครบ **ไม่ใช่** "ถูกต้อง"

## 4. สายเทียบเล่ม PDF ↔ PDF (#42) — `redbook/web/api_pdfpair.py` (หลังบ้านทำ · ลงทะเบียนจาก `pdfpair_routes.register` ไม่แตะ `app.py`)

| เส้นทาง | service เดิม | คืนค่า / ด่าน |
|---|---|---|
| `GET /api/pdfpair/shelf?a=&agency=` | `pdfshelf.volumes/agencies/suggest_b` | `{shelf_label, volumes:[{key,title,fiscal_year,stage,stage_label,volume_no}], a, agencies, suggest:[{key,why}], others:[key]}` · หน่วยที่กันไว้ไม่อยู่ในรายการ |
| `POST /api/pdfpair/shelf/start {a,b,agency}` | `pdfshelf.start` | `{rid}` · หน่วยที่กันไว้ = 400 |
| `POST /api/pdfpair/uploads` (multipart: `file`, `side`=A/B, `project_id`?, `source_url`?) | `pdf_upload.accept_pdf` + `source_pdfs.link` | `{project_id, side, pages, sha256, file, sides_ready:[A,B], agencies}` · CSRF ตรวจ**ก่อน**อ่าน body (header `X-CSRF-Token`) · เกินขนาด = 413 · ด่าน #23: ชนิดไฟล์จริง · PDF เสีย/มีรหัสผ่าน = 400 `pdf_unreadable` · ไม่มีหน้า = `pdf_empty` · เกิน `REDBOOK_MAX_PDF_PAGES` (3000) = `pdf_too_many_pages` · ไม่ผ่าน = ไม่มีไฟล์ค้าง + บันทึก security event · `source_url` = http(s) ≤ 1000 ตัว **บันทึกอย่างเดียว ไม่ดึง** · path ในเครื่องในลิงก์ถูกกลบ (privacy 0.2.2) · ไม่ส่ง `project_id` = สร้างโครงการ "อัปโหลดเอง · เทียบเล่ม PDF" · `agencies` ซ่อนหน่วยที่กันไว้และหน่วยในชุดประเมิน |
| `POST /api/pdfpair/uploads/{pid}/run {agency}` | `pdfshelf.start_uploaded` | `{rid}` · ต้องมีทั้งฉบับ A และ B (400) · ช่วงหน้าจากสารบัญของแต่ละไฟล์ · หน่วยที่กันไว้/หน่วยในชุดประเมิน = 400 · **ยังไม่มีดาวน์โหลดจากลิงก์** |
| ด่านชุดประเมิน (ทุกทางที่เริ่มรอบ) | `eval_guard` | รายชื่อในไฟล์ `REDBOOK_EVAL_GUARD` (ค่าเริ่ม `~/.redbook/eval_guard.json` นอก repo · `{"agencies":[…], "unlocked_for_pdfbook":""}`) · ตรงชื่อ = ปฏิเสธที่ `pdfshelf.start` · `start_uploaded` · `pdfpair.run` · และซ่อนจากรายชื่อ · ปลดได้เฉพาะรุ่นตัวสกัดที่ตรึงแล้ว (`unlocked_for_pdfbook` = `PDFBOOK_VERSION` ปัจจุบัน) · บันทึกเหตุการณ์ไม่ใส่ชื่อ · ไม่มีไฟล์ = `configured:false` ใน `GET /api/lane` · **ข้อจำกัด:** ตรวจจากชื่อหน่วยงาน — รอบแบบระบุช่วงหน้าโดยไม่ระบุหน่วยงานไม่ถูกกัน |
| `GET /api/pdfpair/runs?limit=` | `pdfpair.run_list` | `{runs:[{id, created_at, mode, mode_label, agency, superseded_by, sides:{A,B:{label, file}}, counts:{actionable, pending}}]}` · `label` = ป้ายเดียวกับหน้ารอบ (ขั้น + ปี + "ผู้ตรวจยืนยัน") · นับแบบเดียวกับ `GET …/runs/{rid}` |
| `GET /api/pdfpair/runs/{rid}` | `pdfpair.view` + `preflight` | `{run:{id, created_at, mode, mode_label, agency, versions, profile_status_label, superseded_by, supersedes, sides:{A,B:{label, file, sha256, fiscal_year, year_status, year_status_label, year_origin_label, stage, stage_status, stage_origin, first, last, pages_in_file, method_label, coverage:{sections_found, repaired_words, pages_no_text}}}}, groups:[{key,label,total,decided,pending,info}], counts:{actionable,pending,info}, use_counts, next_pending_id, item_change_ids, rounding_policy, year_warnings:[{side,text}], stage_warnings:[{side,text}], decisions:[{key,label,use,use_label,when}] (use = ผลต่อการใช้ผลถ้าเลือกตัวเลือกนี้ ตาม `DECISION_USE`: usable/excluded/open · when = "เลือกเมื่อ…" จาก `DECISION_WHEN`), preflight:{ok, use_status, use_status_label, use_status_scope, use_reasons, use_counts, actionable, use_breakdown, failing, failing_checks:[{key,label}], export_url}}` |
| `GET /api/pdfpair/runs/{rid}/findings?topic=` | `view` | `[Finding + decision + use]` |
| `GET /api/pdfpair/runs/{rid}/f/{fid}` | `view.finding` + `text_diff` | `{finding (a/b มี page_size = [กว้าง, สูง] pt ของหน้านั้น · กรอบ CropBox เดียวกับ bbox · ไม่มีหน้า = null), prev_id, next_id, next_pending_id, diff:{a:[[op,text]], b:[[op,text]]}, rounding_policy (เมื่อมี parts), writable}` |
| `POST /api/pdfpair/runs/{rid}/f/{fid}/decide {choice,note}` | `pdfpair.decide` | `{finding, next_pending_id, preflight}` · เปลี่ยนผลเดิมต้องมีเหตุผล (400 · ตรวจซ้ำในธุรกรรม) · รอบถูกแทน (รวมกรณีคำนวณซ้ำพร้อมกัน) = 409 `superseded` |
| `GET /api/pdfpair/runs/{rid}/preflight` | `pdfpair.preflight` | `{ok, checks:[{key,label,ok,detail,action:{code,label,href,finding_id?,run_id?}}], use_status, use_status_label, use_status_scope, use_reasons, use_counts, use_breakdown, failing_checks, years:{A,B:{used, known, detected, status, status_label, status_state, confirmable, origin_label, candidates, evidence:[{…, kind_label}], confirmed, pages_allowed, page_png}}, needs_rerun, mode_for_years, stage_warnings}` · `action.code` ∈ `open_finding` · `confirm_year` · `rerun` · `open_run` · `reattach` · รอบที่ถูกแทน = ไม่มี `rerun` |
| `POST /api/pdfpair/runs/{rid}/year {side,year,note,seen}` | `pdfpair.confirm_year` | preflight ใหม่ · ต้องติ๊กดูภาพ · ปีต่างจากที่อ่านได้ต้องมีหมายเหตุ · รอบถูกแทน = 409 `superseded` |
| `POST /api/pdfpair/runs/{rid}/rerun` | `pdfpair.rerun` | `{rid: <รอบใหม่>}` · ไม่ต้องคำนวณซ้ำ/ไฟล์เปลี่ยน/กดซ้ำ = 409 · ล้มกลางทาง = รอบเดิม**ไม่ถูกบล็อก** |
| `GET /api/pdfpair/runs/{rid}/audit` | `pdfpair_repo.audit_entries` + `audit.verify_chain` | `{entries:[{seq, at, action, summary, detail}], chain:{ok, …}}` |
| ส่งออก | `pdfpair.export_csv_checked` | **ใช้ `GET /pdfpair/runs/{rid}/export.csv` เดิม** — ด่านประเมินใหม่ฝั่งเซิร์ฟเวอร์ทุกครั้ง · ไม่ผ่าน = 409 ไม่เขียนไฟล์ · Audit แฮชไบต์ที่ส่งจริง · ด่าน ไฟล์ และ Audit มาจาก snapshot เดียวกัน · รอบถูกแทนหลังผ่านด่าน = 409 ไม่บันทึก |

## 5. แบ่งไฟล์ (กันแก้ชน)

| เจ้าของ | ไฟล์ |
|---|---|
| หน้าบ้าน | `frontend/**` · `redbook/static/app/**` · `redbook/web/api_trial.py` · `tests/test_api_trial.py` · บรรทัดลงทะเบียนใน `redbook/app.py` |
| หลังบ้าน | `redbook/pdfbook/**` · `redbook/services/{pdfpair,pdfshelf,trial}.py` · `redbook/storage/{pdfpair_repo,trial_repo}.py` · `redbook/web/{api_common,api_pdfpair,pdfpair_routes}.py` · `tests/test_api_*.py` · เอกสารนี้ |
| ต้องบอกกันก่อนแตะ | `redbook/app.py` · `redbook/web/security.py` · `redbook/web/trial_routes.py` · templates ของสายเทียบเล่ม/ทดลอง |

- หลังบ้านทำงานใน worktree แยก `redbook-verify-be42` (branch `be/42-backend` จาก `19bd47e`) · รวมเข้า `pdf/pair-compare` เมื่อแจ้งหน้าบ้านแล้ว
- ห้าม `git add -A` / `git commit -a` · commit เฉพาะ path ของตัวเอง
