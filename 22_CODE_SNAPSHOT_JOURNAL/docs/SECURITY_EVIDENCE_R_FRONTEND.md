# หลักฐานความปลอดภัยของหน้าบ้านใหม่ `/r` — ตอบ #42 REVIEW 6409941573 (ส่วนหลักฐาน #23)

สถานะ: **หลักฐานจากทีม (frontend) — ยังไม่ใช่การตรวจรับ** · โบยังไม่ได้รันซ้ำ · 26 ต.ค. 2569
ขอบเขต: หน้าบ้าน Svelte ที่ `/r` (สายทดลองตรวจ + สายเทียบเล่ม `/r/p…`) และ JSON API ที่หน้าบ้านเรียก บนเซิร์ฟเวอร์สาย PDF
(`redbook.pdf_lane_app:create_lane_app`) · ไม่รวมสาย Excel · ข้อมูลทดสอบ = ชั้นเล่มสังเคราะห์ (เทสต์) และชุดพัฒนา PDF สาธารณะ (เบราว์เซอร์)
ถ้อยคำ: ประเมินตามรายการด้านล่างเท่านั้น — **ไม่ได้อ้างว่า "ผ่าน ASVS" หรือ "ปลอดภัย"**

## ผล

| # | สิ่งที่ตรวจ | วิธี | ผล |
|---|---|---|---|
| R1 | หน้า `/r…` 8 เส้นทาง + ไฟล์ JS/CSS ได้ CSP เดียวกับหน้าเดิม: `script-src 'self'` · `style-src 'self'` · `default-src 'none'` · `object-src 'none'` · `frame-ancestors 'none'` · `connect-src 'self'` · `base-uri 'none'` + `nosniff` · `X-Frame-Options: DENY` · `Referrer-Policy: same-origin` · หน้า `no-store` · meta referrer ตรงหัว | `tests/test_frontend_security_r.py::test_pages_and_assets_carry_the_same_security_headers` | PASS |
| R2 | ไฟล์ที่ build ไม่มีสคริปต์/สไตล์ฝังในหน้า · ไม่มี `eval(`/`new Function(` · ไม่อ้าง URL เครื่องอื่น (ยกเว้นข้อความ namespace XHTML และลิงก์คำอธิบายในข้อความ error ของ Svelte — ไม่ใช่การโหลด) · ฟอนต์/ภาพจาก `/static/` เท่านั้น | `test_api_trial.py::test_built_frontend_is_csp_clean_and_served` + `test_built_bundle_loads_nothing_from_elsewhere` | PASS |
| R3 | โค้ดต้นทางไม่มี `{@html}` · `innerHTML/outerHTML/insertAdjacentHTML` · `document.write` · `eval/new Function` · `localStorage/sessionStorage/indexedDB` · `document.cookie` · `window.open/postMessage` · `style="…"` · `svelte/transition` (ฉีด `<style>`) — ข้อความทุกชิ้นผ่านการ escape ของ Svelte | `test_sources_have_no_html_injection_storage_or_dynamic_code_sinks` (+ negative control ด้วยตัวอย่างที่ฝังไว้: จับได้ทุกแบบ) | PASS |
| R4 | ลิงก์ `target="_blank"` ทุกจุดมี `rel="noopener"` · `fetch` เรียกเฉพาะ path ของ origin เดียวกัน | `test_external_links_open_without_opener_and_fetches_stay_on_this_origin` | PASS |
| R5 | คำขอ JSON ที่เปลี่ยนสถานะ: ไม่มีโทเคน / โทเคนผิด / มีโทเคนแต่ `Origin` อื่น = 403 `csrf` — ทั้งแอปเต็มและเซิร์ฟเวอร์สาย PDF · คุกกี้ `redbook_csrf` = `HttpOnly; SameSite=strict` | `test_json_writes_refuse_missing_wrong_or_cross_origin_tokens[full/lane]` + `tests/test_api_parity.py` (หลังบ้าน) | PASS |
| R6 | เซิร์ฟเวอร์สาย PDF เปิดเฉพาะเส้นทางสาย PDF — `/books` `/audit` `/t1b` `/projects` = 404 · หน้าบ้านซ่อนลิงก์ไปสาย Excel เมื่อ `/api/lane` = `pdf_only` | `test_lane_server_serves_r_and_refuses_excel_lane_pages` + `tests/test_pdf_lane_app.py` (หลังบ้าน) | PASS |
| R7 | เบราว์เซอร์จริง (Chromium ในแอป) เดินทุกหน้าใหม่: รายการรอบ · เริ่มรอบ · ภาพรวม · หลักฐาน (รวมดูทั้งหน้า) · ด่านก่อนส่งออก · Audit · หน้าทดลองตรวจ → CSP violation 0 · console error 0 · ภาพเสีย 0 | ฟัง `securitypolicyviolation` + `console.error` ในหน้า บน 8645 | PASS (ทีมรายงาน) |
| R8 | **F-01 Host allowlist (DNS rebinding)** บนเซิร์ฟเวอร์สาย PDF: `Host: evil.example` = 400 · localhost = 200 · **F-05** หัว `server` ไม่ส่งแล้ว (launcher รัน uvicorn ด้วย `server_header=False`) · แอปเต็ม (`create_app`) ยังไม่มีการแก้ของ #23 — รอ consolidation | `test_foreign_host_header_is_refused_on_the_lane_server` + `curl -I` บนเซิร์ฟเวอร์ทดสอบ | PASS (สาย PDF) |
| R9 | ZAP baseline ของ `/r` | ไม่ได้รัน — โปรโตคอล #23 จำกัด ZAP ไว้ที่เป้าสังเคราะห์ loopback ผ่าน runner ของ `sec/23` ซึ่งยังไม่อยู่ในสายนี้ | **REVIEW** (ไม่นับเป็นผ่าน) |

## ข้อจำกัด
- ทั้งหมดเป็นผลที่ทีมรันเอง · ไม่ใช่รอบ final ของ runner #23 (matrix 0.1.2) และไม่ได้ขึ้นรุ่น matrix
- R8: Host allowlist ใส่ชั่วคราวในเซิร์ฟเวอร์สาย PDF (ฝั่งหลังบ้าน) · การแก้ของ #23 ข้ออื่น (F-02/09/10/11) ยังไม่อยู่ในสายนี้ — รอโบ/กิ๊ฟตัดสินเรื่อง consolidation
- ช่องค้นหาในภาพรวมเก็บคำค้นไว้ใน URL (`?q=`) ของเครื่องตัวเอง — เป็นข้อความที่ผู้ใช้พิมพ์ ไม่ใช่ข้อมูลบุคคลที่ระบบใส่
- ไม่ครอบคลุมสาย Excel และการตรวจ privacy ของเนื้อหาเอกสาร
