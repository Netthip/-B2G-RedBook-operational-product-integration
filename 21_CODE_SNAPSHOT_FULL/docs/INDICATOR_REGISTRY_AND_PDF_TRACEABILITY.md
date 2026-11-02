# ทะเบียนตัวชี้วัด + การเปิดหลักฐาน PDF เก่า–ใหม่ — ออกแบบและสถานะ (Gate 0–4)

> **ป้ายกำกับผลงาน: `PRODUCT EVIDENCE — POST-FREEZE`** · ตอบคำสั่ง
> `GIFT DECISION — ANSWER-KEY CUSTODIAN + INDICATOR/PDF TRACEABILITY WORK ORDER`
> (Issue #1 · `5595281027` · 9 กันยายน 2569) · ผู้บันทึก: Giho (detector developer)
> · เวอร์ชัน `evidence-service-0.2.0` (`pdftext-0.2.0` · `evidence-documents-0.2.0`) · `indicator-observe-0.2.0` · `indicator-mapping-0.2.0` · `indicator-registry-0.2.0` (schema v2) · `indicator-identity-0.1.0` · `sealed-key-ingestion-guard-0.1.1`
> · แก้รอบ A–D (Pass 1 · Bo `5597645315`) และรอบ B1–B5/H1–H2/P1-1/P1-2 (Pass 2 · Bo `5598957701` · `5598526148`)
>
> 🔴 เอกสารนี้ **ไม่ใช่** ผลวิจัยของ T1A ที่ freeze แล้ว · **ไม่มี** การ unblind หรือ scoring ·
> ตัวเลขทุกตัวในเอกสารนี้มาจาก **ชุดสังเคราะห์** (`tests/fixtures/synthetic_pdf`) เท่านั้น
> · ผลการรันทั้งหมดเป็น **ผลการรันในเครื่องผู้พัฒนา — ไม่มี CI**

---

## 0. Gate 0 — ตรึงและขอบเขต

| รายการ | ค่า |
|---|---|
| detector ที่จะถูกประเมิน | ตัวสกัด `indicator-observe-0.1.0` + กติกาจับคู่ `indicator-mapping-0.1.0` (`rules_hash 2279b48175707565` ที่ค่าปริยาย `rephrase_min 0.75 · ambiguous_min 0.50 · tie_margin 0.05`) + normalize `indicator-normalize-0.1.0` + backend ปริยาย `pdfplumber 0.11.9 · pdfminer.six 20251230 · pypdfium2 5.8.0` (`pdftext-0.2.0`) — ตรึงใน `requirements.lock.txt` |
| สถานะการตรึง | **`FREEZE CANDIDATE`** — commit ของ handoff นี้คือตัวเสนอให้ตรึง · การตรึงจริง (tag) เกิด **หลัง Bo รับ** และ **ก่อน** กิ๊ฟสร้าง/ผนึกเฉลย · ถ้า Bo สั่งแก้ detector หลังจากนั้น = เวอร์ชันประเมินใหม่ ไม่ทับของเดิม |
| ด่านกันการเผลออ่านเฉลย (accidental sealed-key ingestion guard · **ไม่ใช่ access control**) | `redbook/sealed_key.py` — ปฏิเสธไฟล์ในโฟลเดอร์ `SEALED_KEY/ answer_key/ gold_key/ …` หรือชื่อไฟล์มีโทเคน `ANSWER_KEY / SEALED_KEY / GOLD_KEY` **ก่อนบรรทัดแรกที่แตะไฟล์** ในทุกทางเข้า (ทะเบียนเอกสาร · backend PDF · `services.t1b.read_workbook`) · **ไม่มีสวิตช์ env/config** (มีเทสต์บังคับ) |
| inventory evidence (ไม่ใช่ข้อพิสูจน์ว่าไม่มีเฉลย / ไม่ใช่ข้อพิสูจน์ว่าผู้พัฒนาเข้าถึงไม่ได้) | `sealed_key.scan_roots()` บนสามราก (`<USER_HOME>/dev` · `<ONEDRIVE>/Red Vertify Project` · `<ONEDRIVE>/IS`) — สแกน 2,750 รายการ · พบชื่อเข้าข่าย **2** = `sealed_key.py` และ `test_sealed_key_guard.py` (โค้ดของด่านเอง) · **ไม่พบไฟล์ข้อมูลลักษณะเฉลย** · ⚠️ พิสูจน์ได้เฉพาะ "ตามกติกาชื่อ ณ วันสแกน" ไม่ใช่ข้อพิสูจน์ว่าไม่มีเฉลยในรูปอื่น |
| frozen assets ที่ไม่แตะ | ดูหมวด 8 |
| access matrix | `09_RESEARCH_BRIDGE/INDICATOR_EVAL_ACCESS_MATRIX.md` (repo สะพาน) |

🔴 **ถ้อยคำที่ถูกต้อง (Bo `5597645315` ข้อ A) — Gate 0 ในโค้ดพิสูจน์ได้ข้อเดียว**: *"The application rejects paths matching the declared sealed-key naming convention before opening them."* · ด่านนี้ **ไม่ใช่ access control** และ **ไม่พิสูจน์ว่า Giho เข้าถึงเฉลยไม่ได้** (เลี่ยงได้ด้วยการเปลี่ยนชื่อไฟล์หรือแก้โค้ด) · ผลสแกน 2,750 รายการ = **inventory evidence เท่านั้น** · การแยกบทบาทจริงอยู่นอก repo และนอกเครื่อง/บัญชีที่ผู้พัฒนาเข้าถึง: กิ๊ฟเป็น custodian/verifier/adjudicator เลือกและควบคุมตำแหน่งเฉลย · Giho ได้รับเฉพาะ input ประเมินและ output ที่ผนึกแล้ว · บันทึก hash ของเฉลยได้ แต่เนื้อเฉลยห้ามเข้ามาในรากที่ Giho เข้าถึงก่อน unblind ที่ได้รับอนุญาต · ด่านในโค้ด = defense in depth

---

## 1. Gate 1 — ทะเบียนเอกสาร (content hash) และการสกัดข้อสังเกต

### 1.1 ทะเบียนเอกสาร `redbook/evidence/documents.py`

* `document_id = "doc_" + sha256(เนื้อไฟล์)[:16]` — **ชื่อไฟล์ไม่ใช่ตัวตน**
  (เทสต์: ไฟล์เดียวกันสองชื่อ = document เดียว · สองไฟล์ชื่อเดียวกัน = สอง document)
* ฟิลด์ที่ผู้ลงทะเบียน **ประกาศ**: `title · stage · fiscal_year · authority · agency_label · version_label · disclosure_class`
  — ระบบไม่เดาจากชื่อไฟล์ · ไม่ประกาศ = `UNSPECIFIED` / `UNKNOWN` (มองเห็น ไม่ซ่อน)
* `disclosure_class` ∈ `PUBLIC_PUBLISHED · INTERNAL_NOT_PUBLISHED · SYNTHETIC · UNKNOWN` — `UNKNOWN` = **เผยแพร่ไม่ได้** (fail closed)
* `text_layer_status` ∈ `TEXT_LAYER_PRESENT · PARTIAL · ABSENT · TEXT_LAYER_NOT_CHECKED_NO_BACKEND`
* เส้นทางไฟล์จริง = คอลัมน์ `local_path_private` ในฐานข้อมูลเครื่องผู้ใช้เท่านั้น — **ไม่มี view/report/export/URL ใดคืนค่านี้** (เทสต์)
* เปิดไฟล์ทุกครั้ง **ตรวจแฮชซ้ำ** — ไฟล์ถูกแทนที่/หายไป ⇒ `SOURCE_UNAVAILABLE:<reason>` ไม่ crash

### 1.2 ชั้นข้อความ `redbook/evidence/pdftext.py`

* **สายผลิตภัณฑ์ใช้ backend สิทธิ์ผ่อนปรนตัวเดียว** (`pdfplumber` + `pypdfium2`) —
  🔴 **ไม่มี fallback อัตโนมัติ** (P1-1) · ถ้าใช้ไม่ได้ `product_backend()` คืน `None`
  และระบบรายงาน `NO_TEXT_BACKEND` แม้เครื่องจะติดตั้ง PyMuPDF อยู่ · PyMuPDF เรียกได้เฉพาะ
  `research_backend()` ซึ่งชั้นบริการ/route ไม่เรียก (เทสต์ AST บังคับ)
  · เหตุผล: การเงียบ ๆ เปลี่ยน backend = เปลี่ยนสัญญาอนุญาตของผลิตภัณฑ์โดยไม่มีใครรู้
* ทุกรอบบันทึก `backend_report()` (mode · backend · เวอร์ชัน · `fallback_allowed: false`) ลงหลักฐานของรอบ
* **ไม่ OCR** — หน้าไม่มีชั้นข้อความ ⇒ `TEXT_LAYER_ABSENT` และทุกตำแหน่งในหน้านั้น = `LOCATION_REVIEW_REQUIRED`
* ไม่มีคำสั่งบันทึกใด (เทสต์สถาปัตยกรรมกัน `.save()` ทั้งแพ็กเกจ) — กรอบเน้นวาดในหน่วยความจำแล้วส่งเป็น PNG
* 🔴 **P1-2 · ข้อความชน/ล้นขอบหน้า** — ตัวอ่านต่างชนิดอ่านบรรทัดนั้นได้ไม่เท่ากัน (วัดจริงบน
  fixture ชุดขอบเขต: x1 876 vs 595 pt) ⇒ ข้อสังเกตติดธง `TEXT_CLIPPED_AT_PAGE_EDGE`
  และคู่ของมันถูกบังคับเป็น `AMBIGUOUS_REVIEW_REQUIRED` เสมอ · **ห้ามตัดข้อความเงียบแล้วเสนอ
  mapping เป็นผลปกติ** · fixture ชุดขอบเขต (`synthetic_clipped_*.pdf`) **ห้ามแก้ให้บรรทัดสั้นลง**
* ⚠️ **ขอบเขต**: นี่คือการอ่านชั้นข้อความเพื่อชี้ตำแหน่งหลักฐาน **ไม่ใช่** การเปรียบเทียบ PDF ของสายวิจัย —
  `adapters/ministry_pdf.py` (skeleton Phase 3 · `RES-D-32`) **ไม่ถูกแตะ** และ Phase 3 ยัง blocked เท่าเดิม

### 1.3 การสกัดข้อสังเกต `redbook/indicators/observe.py` — ไม่ตัดสินความเท่าเทียม

* หนึ่งข้อสังเกต = หนึ่งบรรทัดที่มีคำบ่งชี้ (`ตัวชี้วัด · เชิงปริมาณ · เชิงคุณภาพ · ค่าเป้าหมาย · หน่วยนับ`) · หัวข้อเปล่าต่อบรรทัดถัดไป
* เก็บ `observed_text` (ตรงตามที่ปรากฏ) **แยกจาก** `normalized_text` · หน้า · กรอบ · `location_confidence`
  (`EXACT_BBOX` / `LINE_APPROX` / `PAGE_ONLY`) · หน่วย/ค่าเป้าหมาย/วิธี/รอบ/ค่าฐาน ที่อ่านได้ · แฮชเอกสาร · รุ่นตัวสกัด
* `page_inventory()` — บัญชีรายหน้า · หน้าที่ไม่มีชั้นข้อความ **ปรากฏในรายงาน** ไม่หาย
* ผลลัพธ์ = **inventory** ไม่ใช่ผลวิจัย (Gate 1 ข้อ 4)

**ผลบนชุดสังเคราะห์ (inventory เท่านั้น):** เก่า 4 หน้า (หน้า 4 ไม่มีชั้นข้อความ) · ข้อสังเกต 7 · ใหม่ 5 หน้า · ข้อสังเกต 8

---

## 2. Gate 2 — ทะเบียนตัวชี้วัด + 8 สถานะ + เทสต์เชิงลบ

### 2.1 schema (`redbook/indicators/registry.py` · ตารางขึ้นต้น `ind_`)

| ตาราง | ลักษณะ | สาระ |
|---|---|---|
| `ind_runs` | เพิ่มอย่างเดียว | เอกสารเก่า/ใหม่ (id) · รุ่นตัวสกัด/normalize/กติกา · `rules_json` + `rules_hash` · backend · จำนวน · บัญชี accounted · บัญชีหน้า |
| `ind_observations` | **immutable** (trigger กัน UPDATE/DELETE) | ฟิลด์ตามคำสั่งกิ๊ฟ §2 ทั้งหมด: `observation_id · document_id(+version/stage/year ผ่านทะเบียน) · observed_text · normalized_text · unit · target · baseline · method · period · page · bbox · location_confidence · source_sha256 · extractor_version` |
| `ind_mappings` | **immutable** | `mapping_id · old/new observation · proposed_status · human_required · basis · differences · alternatives · internal_score` |
| `ind_decisions` | **append-only** + ผูก audit chain | `decision (ACCEPT/REJECT/AMBIGUOUS) · final_status · reason · reviewer · decided_at · audit_seq` — สถานะปัจจุบัน = คำตัดสินล่าสุด |
| `ind_bindings` | append-only | **ประวัติ** การผูกเท่านั้น — 🔴 ไม่ใช่แหล่งความจริงอีกต่อไป (B2) |
| `ind_canonical_ids` | append-only | **ตรึง** canonical id ครั้งแรกที่ component เกิด ⇒ id ที่เผยแพร่แล้วไม่เปลี่ยน (B1) |
| `ind_identity_aliases` | append-only | id เดิมที่ถูกรวมเข้ากับ id หลัก ⇒ เปิดกลับได้เสมอ ไม่มี id ตายกลางทาง |
| `ind_key_entries` | append-only + audit | คำตัดสิน **ฝั่งเฉลย** (ขั้น KEY BUILD/VERIFY) — แยกจาก `ind_decisions` (B4) |
| `ind_key_seals` | append-only + audit | การผนึกเฉลย · ปลดล็อกขั้นตัดสินหลังรัน · บันทึก **แฮชของเฉลย** ไม่ใช่เนื้อเฉลย |
| `ind_schema_version` | — | schema v2 · migration แบบเพิ่มคอลัมน์ (`anchor` · `identity_key` · `geometry_flags_json`) ไม่ลบข้อมูลเดิม |

### 2.1.1 ตัวตนของตัวชี้วัด (B1 · B2)

* **`identity_key`** ของข้อสังเกต = `sha256(แฮชเอกสารเต็ม | หน้า | anchor | ข้อความที่ปรากฏ)` —
  **ไม่มี `run_id` ในสูตร** ⇒ เอกสารเดิมถูกสกัดในรอบใหม่ก็ได้กุญแจเดิม
* **canonical id** มาจาก component ของกราฟที่สร้างจาก **คำตัดสินล่าสุดของมนุษย์** เท่านั้น
  (union-find ⇒ รองรับ transitive A=B, B=C) · ตรึงครั้งแรกแล้วใช้ซ้ำ · รวม component ⇒
  ใช้ id ที่ตรึงก่อน และบันทึกที่เหลือเป็น alias
* **ยังไม่ถูกยืนยัน = `PROVISIONAL-…`** 🔴 ห้ามเรียกว่า canonical และห้ามใช้อ้างอิงข้ามรอบ
* 🔴 **binding คำนวณใหม่ทุกครั้งจากคำตัดสินล่าสุด** — ยอมรับ `SAME_*` แล้วภายหลังแก้เป็น
  non-SAME ⇒ binding **สิ้นผลทันที** (ประวัติยังครบ) · one-to-many ที่ถูกยืนยันในรอบเดียวกัน
  ⇒ **ไม่ผูก** และรายงานเป็น `IdentityConflict` ให้คนตัดสิน ไม่ใช่ "แถวสุดท้ายชนะ"

### 2.2 กติกาจับคู่ (`redbook/indicators/mapping.py` · `indicator-mapping-0.1.0`)

| เฟส | กุญแจ | สถานะที่เสนอ | คนต้องยืนยัน |
|---|---|---|---|
| 1 | ข้อความตรงกันทุกอักขระ (1:1) | `SAME_EXACT` | ไม่บังคับ |
| 2 | `variant_key` (ตัดช่องว่าง/วรรคตอน/เลขไทย) เท่ากัน (1:1) | `SAME_WORDING_VARIANT` | ไม่บังคับ |
| 1–2 | กุญแจเดียวกัน **หลายตัว** ในฉบับเดียว (one-to-many) | `AMBIGUOUS_REVIEW_REQUIRED` ทุกคู่ | ✅ |
| 3 | trigram-Dice ≥ 0.75 · ไม่มีคู่แข่งใกล้ · หน่วย/ค่า/วิธี/รอบ **ไม่ต่าง** | `SAME_CONCEPT_REPHRASED` | ✅ |
| 3 | ≥ 0.75 แต่ หน่วย/ค่าเป้าหมาย/วิธี/ตัวเลข/รอบ **ต่าง** | `DEFINITION_CHANGED` | ✅ |
| 3 | 0.50–0.75 หรือมีคู่แข่งใกล้ | `AMBIGUOUS_REVIEW_REQUIRED` | ✅ |
| บัญชี | เก่าไม่มีคู่ / ใหม่ไม่มีคู่ | `REMOVED_INDICATOR` / `NEW_INDICATOR` | ไม่บังคับ |
| — | `RELATED_NOT_EQUIVALENT` | **เครื่องไม่เสนอเลย** — ทางเลือกของผู้ตรวจ | ✅ |

* จับคู่เป็น **global phase** เรียงตาม (คะแนน, id) ⇒ ผลไม่ขึ้นกับลำดับที่อ่าน (เทสต์)
* 🔴 **conservation gate** (B3) — `accounted()` ตรวจเจ็ดข้อจากยอด input ที่เป็นอิสระ:
  id ที่ไม่รู้จัก · id ที่หายไป · การนับซ้ำนอกสถานะที่ประกาศรูปไว้ · รูปทรงของแถวต่อสถานะ ·
  สถานะนอกบัญชี · `mapping_id` ซ้ำ · ยอดรายสถานะกับยอดรวม · `closed` เป็นจริงเมื่อผ่านครบ
  · มี mutation tests ที่จงใจ drop/duplicate/inject unknown/สลับ shape แล้วด่านต้องล้ม
* **เทสต์เชิงลบ** (`tests/test_indicator_mapping.py`): ตัวเลขต่าง · หน่วยต่าง · ตัวหารเปลี่ยน · รอบเปลี่ยน · เติมคำหนึ่งคำ (ผู้ป่วย/ผู้ป่วยนอก) · ข้อความซ้ำ — **ไม่มีกรณีใดได้ `SAME_*` โดยอัตโนมัติ** แม้ความคล้ายเชิงอักขระ ≥ 0.75
* เกณฑ์ตัวเลข (0.75/0.50/0.05) เป็นค่าที่ **เสนอ** — ต้องตรึงพร้อม detector ก่อนสร้างเฉลย

---

## 3. Gate 3 — ต้นแบบเปิดหลักฐาน PDF เก่า/ใหม่

| route | ทำอะไร |
|---|---|
| `GET /evidence/{document_id}?page=n&run=<run_id>&obs=<observation_id>` | หน้าหลักฐาน: metadata (id · sha256 · ขั้น · ปี · รุ่น · ชั้นการเปิดเผย · ชั้นข้อความ) + ข้อความตามที่ปรากฏ + กรอบ + ภาพหน้าพร้อม **กรอบเน้น** + ปุ่มเปิด PDF ที่หน้า n |
| `GET /evidence/{document_id}/file#page=n` | สตรีม PDF แบบ inline ผ่านทะเบียน (ชื่อที่ผู้ใช้เห็น = `document_id.pdf`) — เบราว์เซอร์เปิดที่หน้า n |
| `GET /evidence/{document_id}/page/{n}.png?hl=x0,y0,x1,y1` | ภาพหน้า + กรอบเน้น (วาดในหน่วยความจำ) · `hl` ไม่ถูกต้อง ⇒ 400 |
| `GET /evidence/compare?run=&map=` | **เทียบข้างกัน** เก่า/ใหม่ + ความต่าง นิยาม/หน่วย/วิธี/รอบ + ฟอร์มคำตัดสิน · **ไม่มีคะแนนของเครื่อง** |
| `GET /indicators/runs/{run_id}` | รายงาน (synthetic example report) — ทุกแถวมีปุ่ม `Old evidence` / `New evidence` / `เทียบข้างกัน` |
| `GET /indicators/runs/{run_id}/keybuild` | **ขั้นจัดทำ/ยืนยันเฉลย (B4)** — ไม่มีสถานะที่เครื่องเสนอ เหตุผล หรือคะแนน · บันทึกเฉลย + ผนึก |
| `GET /indicators/runs/{run_id}/verify` | **ขั้นตัดสินหลังรัน** — 🔴 เปิดได้ก็ต่อเมื่อเฉลยของรอบนั้นถูกผนึกแล้ว (มิฉะนั้น 409 `ADJUDICATION_LOCKED_KEY_NOT_SEALED`) |

ทำไมใช้ **ภาพหน้า + ลิงก์เปิด PDF** แทน iframe: CSP ของแอป (`default-src 'none' · frame-ancestors 'none' · X-Frame-Options DENY`)
ไม่อนุญาตให้ฝัง PDF ในหน้า — การผ่อน CSP เพื่อ iframe จะลดท่าที ZAP · ภาพหน้าที่วาดจาก backend ให้กรอบเน้นได้ตรงกว่า และ
`#page=n` ยังใช้ได้ผ่าน route ที่ควบคุม (ตามที่กิ๊ฟอนุญาตใน §3)

🔴 **B5 · run context** — ลิงก์หลักฐานพก `run=` เสมอ และ route **ตรวจ** ว่าข้อสังเกตอยู่ในรอบ
และเอกสารที่ระบุจริง · ไม่ระบุรอบ ⇒ `RUN_CONTEXT_MISSING` และ **ไม่แสดง `indicator_id` ของรอบใด** ·
อ้างรอบผิด ⇒ `RUN_CONTEXT_MISMATCH` และไม่แสดงข้อสังเกตนั้น (ไม่ไปค้นรอบอื่นแทนให้)

**กรณีที่ทดสอบแล้ว (`tests/test_evidence_routes.py` · `test_evidence_run_context.py`)** — ตัวชี้วัดย้ายหน้า (เก่า p2 → ใหม่ p3) · เลขหน้าเปลี่ยน · หน้าไม่มีชั้นข้อความ (ติดป้าย `LOCATION_REVIEW_REQUIRED` และแสดงในบัญชีหน้า) · ข้อความซ้ำ (สองแถว `AMBIGUOUS` คนละหน้า) · ไฟล์ต้นทางหาย/ถูกแทนที่ (`SOURCE_UNAVAILABLE` · route ไฟล์/ภาพ = 404 ไม่ crash) · id ผิดรูป/ไม่รู้จัก ⇒ 400/404

**เทสต์ความเป็นส่วนตัว** — ไม่มี absolute path (ทดสอบด้วยชื่อโฟลเดอร์ล่อ ไม่พึ่ง detector ของตัวเอง) · ไม่มี `file://` · ไม่มี raw exception ·
URL มีเฉพาะ id/หน้า/ตัวเลข · ล็อกมีเฉพาะ id/จำนวน ไม่มีข้อความจากเอกสาร · ชุดตรวจ XLSX แทนข้อความจากเอกสาร
`INTERNAL_NOT_PUBLISHED`/`UNKNOWN` ด้วยตัวยึด · ไม่มี `internal_score`/`trigram_dice` ในหน้าตรวจ/ไฟล์

---

## 4. Gate 4 — สองขั้นที่แยกกัน (B4)

| ขั้น | artifact | เห็นอะไร |
|---|---|---|
| **KEY BUILD / VERIFY** | `ind_key_entries` · หน้า `/keybuild` | ข้อความสองฝั่งตามที่ปรากฏ · ขั้น/ปี/หน้า/แฮช · ปุ่มเปิดหลักฐาน · 🔴 **ไม่มี** สถานะที่เครื่องเสนอ เหตุผลของเครื่อง หรือคะแนน |
| **ผนึกเฉลย** | `ind_key_seals` | การกระทำของ custodian · บันทึก **แฮชของเฉลย** ไม่ใช่เนื้อเฉลย · หลังผนึกแก้เฉลยไม่ได้ |
| **POST-RUN ADJUDICATION** | `ind_decisions` · หน้า `/verify` + ชุด XLSX | แสดงสถานะที่เครื่องเสนอได้ · เปิดได้หลังผนึกเท่านั้น |

🔴 รอบนี้ **ไม่มีเฉลยจริงของงานวิจัย** — โค้ดข้างต้นคือ *กลไกการแยก* ที่ต้องมีก่อน · การผนึกเป็น
การกระทำของกิ๊ฟ (custodian) เท่านั้น · ชุด XLSX เดิมถูกเปลี่ยนบทบาทเป็น
**POST-RUN ADJUDICATION PACKAGE** และ **ห้ามใช้สร้างหรือยืนยันเฉลยที่ปิดผนึก**

## 4.1 รายละเอียดชุดตัดสินหลังรัน

* หน้า `/indicators/runs/{run_id}/verify` — กรองตามสถานะ · ทุกแถวมี ข้อความเก่า/ใหม่ตามที่ปรากฏ · ขั้น/หน้า · ความต่างนิยาม/หน่วย/วิธี · ปุ่มเปิดหลักฐาน · ปุ่มเทียบข้างกัน + ตัดสิน
* ฟอร์มคำตัดสิน: `ยอมรับ / ไม่ยอมรับ (ระบุสถานะที่ถูกต้อง) / ยังตัดสินไม่ได้` + เหตุผล + ผู้ตรวจ · กติกา: สถานะ 3·4·5·8 ต้องมีเหตุผล · `REJECT` ต้องระบุสถานะที่ต่างจากที่เสนอ · ผู้ตรวจว่างไม่ได้ · เพิ่มอย่างเดียว + audit
* ไฟล์ `indpkg_<ts>_<id>.xlsx` (3 ชีต: ชุดตรวจ · วิธีใช้ · สรุป) + `_snapshot.json` (`"scores_included": false`) — เขียนผ่าน `exporters/xlsx_writer` และ `csv_safe.neutralize` (กันสูตร) · `privacy.assert_shareable` ก่อนเขียน
* 🔴 **ไม่มีคะแนนของเครื่องในหน้าตรวจและในไฟล์** (เทสต์) — `basis` แสดงเฉพาะ *ชนิด* ของเหตุผล เช่น "ข้อความคล้ายกันเชิงอักขระ"

---

## 5. ตัวอย่างต่อสถานะ (ชุดสังเคราะห์ · เผยแพร่ได้ · ไม่ใช่เฉลย)

| สถานะที่เครื่องเสนอ | ฉบับเก่า (p) | ฉบับใหม่ (p) | คนต้องยืนยัน |
|---|---|---|---|
| `SAME_EXACT` | ตัวชี้วัดที่ 1 : ร้อยละของหน่วยงานที่ได้รับการอบรม เป้าหมาย ร้อยละ 80 (2) | เหมือนเดิม (3) — **ย้ายหน้า** | — |
| `SAME_WORDING_VARIANT` | ตัวชี้วัดที่ 2 : ร้อยละของบุคลากรที่ผ่านการประเมิน (ร้อยละ 90) (2) | ตัวชี้วัดที่ 2 : ร้อยละ ของบุคลากร ที่ผ่านการประเมิน ( ร้อยละ ๙๐ ) (3) | — |
| `SAME_CONCEPT_REPHRASED` | ตัวชี้วัดที่ 3 : จำนวนรายงานวิจัยที่เผยแพร่ ไม่น้อยกว่า 5 เรื่อง (2) | …ที่ได้รับการเผยแพร่… (3) | ✅ |
| `DEFINITION_CHANGED` | ตัวชี้วัดที่ 4 : ร้อยละของโครงการที่แล้วเสร็จตามแผน (นับจากโครงการทั้งหมด) ร้อยละ 85 (3) | …(นับจากโครงการที่ได้รับจัดสรร) ร้อยละ 85 (4) — ความต่าง: วิธีคำนวณ/ตัวหาร | ✅ |
| `AMBIGUOUS_REVIEW_REQUIRED` (คล้ายไม่พอ) | ตัวชี้วัดที่ 5 : จำนวนผู้เข้ารับการอบรม 200 คน (3) | ตัวชี้วัดที่ 5 : จำนวนหลักสูตรอบรมที่เปิดสอน 4 หลักสูตร (4) — คนอาจตัดสิน `RELATED_NOT_EQUIVALENT` | ✅ |
| `AMBIGUOUS_REVIEW_REQUIRED` (ข้อความซ้ำ) ×2 | ตัวชี้วัดที่ 7 : จำนวนกิจกรรมเผยแพร่ความรู้ 12 ครั้ง (3) | ข้อความเดียวกัน ปรากฏ 2 ที่ (4 และ 5) | ✅ |
| `REMOVED_INDICATOR` | ตัวชี้วัดที่ 6 : ร้อยละของข้อร้องเรียนที่ได้รับการแก้ไข ร้อยละ 100 (3) | — | — |
| `NEW_INDICATOR` | — | ตัวชี้วัดที่ 8 : ร้อยละของระบบที่ผ่านการทดสอบความปลอดภัย ร้อยละ 95 (2) | — |
| `RELATED_NOT_EQUIVALENT` | เครื่องไม่เสนอ (0 แถว) — ผู้ตรวจเลือกได้ในฟอร์ม | | ✅ |

หน้า 4 ของฉบับเก่าไม่มีชั้นข้อความ ⇒ ตัวชี้วัดที่ 8 (คู่มือ 3 ฉบับ) **ไม่ถูกสกัด** และรายงานบัญชีหน้าติดป้าย `LOCATION_REVIEW_REQUIRED` — เป็นช่องว่างที่คนต้องกรอกเอง (`manual_observation` · `PAGE_ONLY`)

---

## 6. ข้อจำกัดและกรณีที่ยังต้องให้คนตัดสิน

0. **ยังไม่มีการแยกบทบาทจริง** — กลไกใน §4 บังคับ *ลำดับ* (เฉลยก่อน ตัดสินทีหลัง) แต่ไม่ได้บังคับ
   *ตัวบุคคล* · การแยกสิทธิ์จริงอยู่นอก repo และเป็นคำตัดสินของกิ๊ฟ
1. ตัวสกัดใช้คำบ่งชี้แบบอนุรักษ์นิยม — ตัวชี้วัดที่เขียนโดยไม่มีคำว่า "ตัวชี้วัด/เชิงปริมาณ/เชิงคุณภาพ/ค่าเป้าหมาย/หน่วยนับ" **จะไม่ถูกสกัด** และตัวชี้วัดที่ข้ามหลายบรรทัดจะได้ `LINE_APPROX` หรือขาดท่อน
2. ไม่มี OCR — หน้าสแกน = `LOCATION_REVIEW_REQUIRED` ทั้งหน้า · ต้องกรอกด้วยคน
3. ความคล้ายเชิงอักขระ **ไม่รู้ความหมาย** — ทุกคู่ตระกูล 3/4/5/8 ต้องมีคนยืนยัน (บังคับในโค้ด)
4. เกณฑ์ 0.75/0.50/0.05 ยังไม่ผ่านการปรับกับเอกสารจริง (ห้ามปรับหลังเห็นเฉลย)
5. ฟอนต์ใน fixture คือ Tahoma (ฝังแบบ subset) — ใช้เพื่อทดสอบซอฟต์แวร์เท่านั้น
6. backend ปริยาย = `pdfplumber` (MIT · pdfminer.six MIT · Pillow MIT-CMU) + `pypdfium2` (BSD-3/Apache-2.0) ตั้งแต่ `pdftext-0.2.0` · PyMuPDF (AGPL/commercial · `LICENSE REVIEW REQUIRED`) ย้ายไป `requirements-research-pymupdf.txt` ใช้เฉพาะเทสต์ equivalence · ไม่มีไลบรารี ระบบยังทำงานแต่รายงาน `NO_TEXT_BACKEND` · บัญชีสัญญาอนุญาต: `docs/DEPENDENCY_LICENSE_INVENTORY.md` (ไม่ใช่ legal clearance)
7. `pip-audit` รันซ้ำแล้วกับชุด lock (ดู `docs/FREEZE_CANDIDATE_MANIFEST_indicator.md`) — สะท้อนฐานข้อมูล advisory ณ วันรันเท่านั้น · ไม่ครอบโค้ดของโครงการเอง
8. canonical `indicator_id` คงที่ข้ามรอบแล้ว (B1) แต่ **ผูกได้เฉพาะเมื่อมีคำตัดสินของมนุษย์** —
   ข้อสังเกตที่ยังไม่ถูกยืนยันจะเป็น `PROVISIONAL-…` ตลอด · แถวจาก schema v1 ที่ไม่มี
   `identity_key` ผูกข้ามรอบไม่ได้ (ระบบไม่เดาให้) — รอบนี้ผูกภายในรอบเดียว

---

## 7. คำสั่งที่รันจริง

```
pip install -r requirements.lock.txt                                    # สภาพแวดล้อมประเมิน (ตรึงเวอร์ชัน · ไม่มี PyMuPDF)
pip install -r requirements-research-pymupdf.txt                        # (ทางเลือก) extra วิจัยสำหรับเทสต์ equivalence เท่านั้น
.venv\Scripts\python.exe scripts\make_synthetic_indicator_pdfs.py      # สร้าง fixture (ฝ่ายสร้างไฟล์ · นอกแพ็กเกจ · ต้องมี extra วิจัย)
.venv\Scripts\python.exe scripts\indicator_demo.py --package           # ลงทะเบียน → รัน → ชุดตรวจ
.venv\Scripts\python.exe -m pytest -q                                  # ทั้ง repo
```

---

## 8. frozen assets ที่ไม่แตะ (ยืนยันจาก `git status` / รายการไฟล์ใน commit)

`redbook/t1/**` · `redbook/t1b/**` core · `redbook/t1b_eval/**` · `redbook/adapters/**` (รวม `ministry_pdf.py`) ·
tag `t1-frozen-1.0.0` (`49fbb2e`) · frozen T1A Evidence Index (repo เล่ม `617ceac`) · raw results ใน `.data/` และ `redbook-verify-data/` ·
Human Review workbook `v1.3.1` · `docs/T1B_SHADOW_RUN_*` · `docs/FORMATIVE_CASE_NVI_*` (ของ session อื่น) · `LANE_C_*` / `LANE_D1*` ในสะพาน

ไฟล์เดิมที่แก้ (เพิ่มอย่างเดียว): `redbook/app.py` (route กลุ่มใหม่ + `init_schemas`) · `redbook/static/app.css` · `requirements.txt` ·
**`redbook/services/t1b.py` — เพิ่ม 3 บรรทัด (ด่านกันการเผลออ่านเฉลยใน `read_workbook`) นอกรายการ `LANE CLAIM`** — สถานะ: **`REVIEWED — ACCEPTED`** เป็น recorded scope deviation (Bo `5597645315` ข้อ 8 · ห้าม revert)


---

## Pass 3 — ขั้นเฉลยถูกตัดขาดจากผลลัพธ์ของ detector (append-only)

> ตอบ `BO REVIEW COMPLETE — PRE-FREEZE CORRECTIONS PASS 2` (`5600162467`) ·
> เนื้อหาข้างบนไม่ถูกแก้ — หัวข้อนี้เพิ่มไปข้างหน้าเท่านั้น

**สิ่งที่เปลี่ยนในเส้นทางการเปิดหลักฐาน**

หน้า `/indicators/runs/{run}/keybuild` เดิมแสดง *คู่* ที่เครื่องเสนอ (ตัดสถานะออกแล้ว)
ตั้งแต่ Pass 3 หน้านั้นแสดง **รายการข้อสังเกต** ของทั้งสองฉบับเรียงตามลำดับกลาง
(แฮชเอกสารเต็ม → หน้า → สมอในหน้า → แฮชข้อความ) และลิงก์หลักฐานของทุกรายการ
ยังพก `run=` ตามกติกา B5 เหมือนเดิม

| เส้นทาง | ก่อน Pass 3 | ตั้งแต่ Pass 3 |
|---|---|---|
| แถวของขั้นเฉลย | `key_build_rows(rv)` ← `rv.pairs` | `key_universe_view(run)` ← `ind_key_universe` |
| ตัวระบุของแถว | `mapping_id` ของ detector | `KI-…` จาก `identity_key` ของข้อสังเกต |
| จำนวนแถว | = จำนวนคู่ที่เครื่องจับได้ | = จำนวนข้อสังเกตในเอกสารทั้งสองฉบับ |
| การเปิดหลักฐาน | `/evidence/{doc}?page=&obs=&run=` | **เหมือนเดิม** (ไม่เปลี่ยนสัญญาของ route) |

**ปุ่มผนึกมีสองปุ่ม** — ผนึกเฉลย และผนึกผลลัพธ์ของเครื่อง · ขั้นตัดสินหลังรันเปิดเมื่อครบทั้งสอง
ป้ายเมื่อยังไม่ครบ: `ADJUDICATION_LOCKED_KEY_OR_DETECTOR_NOT_SEALED`

**ไฟล์ใหม่ในรอบนี้** — `redbook/indicators/keyuniverse.py` · `tests/keystage.py` ·
`tests/test_indicator_key_universe.py`
**ไฟล์เดิมที่แก้ (เพิ่ม/แทนที่เฉพาะเส้นทางขั้นเฉลย)** — `redbook/indicators/{identity,registry}.py` ·
`redbook/services/evidence.py` · `redbook/app.py` · `redbook/templates/{indicator_keybuild,indicator_locked}.html` ·
`tests/test_{indicator_identity_binding,evidence_run_context,evidence_routes,indicator_override_1267,indicator_synthetic_pdf,architecture_separation}.py`


---

## Pass 4 — จักรวาลของเฉลยมาจากคน และผนึกถูกตรวจจริง (append-only)

> ตอบ `BO REVIEW COMPLETE — PRE-FREEZE CORRECTIONS PASS 3` (`5605652708`) ·
> เนื้อหาข้างบนไม่ถูกแก้

| เส้นทาง | Pass 3 | ตั้งแต่ Pass 4 |
|---|---|---|
| ต้นทางของรายการเฉลย | `ind_observations` ของรอบ (เครื่องสกัด) | `ind_source_inventory` (**คนอ่านเอกสารแล้วกรอก**) |
| ตัวชี้วัดที่เครื่องสกัดไม่เจอ | หายไปจากเฉลยเงียบ ๆ | **อยู่ในเฉลย** และถูกนับเป็น `NO_MATCH` |
| ข้อความที่แสดงในขั้นเฉลย | ข้อความที่เครื่องสกัดได้ | ข้อความที่คนกรอก |
| ลิงก์หลักฐานในขั้นเฉลย | ชี้ที่ข้อสังเกตของเครื่อง (`obs=`) | ชี้ที่ **หน้า** ของเอกสาร (ยังพก `run=`) เพราะเครื่องอาจไม่มีข้อสังเกตนั้น |
| การปลดล็อกขั้นตัดสิน | มีแถว seal ครบสอง | **คำนวณใหม่แล้วเทียบ** ครบสาม |

**route ใหม่** — `POST /indicators/runs/{run}/keybuild/source` (กรอกรายการ) ·
`POST …/keybuild/source/retract` (ถอนรายการก่อนตรึง)
**ไม่เปลี่ยนสัญญาของ route หลักฐาน** — `/evidence/{doc}?page=&obs=&run=` เหมือนเดิมทุกประการ

**ไฟล์ใหม่** — `redbook/indicators/sourceinventory.py` · `tests/test_indicator_seal_verification.py`
**ไฟล์เดิมที่แก้** — `redbook/indicators/{keyuniverse,registry}.py` · `redbook/services/evidence.py` ·
`redbook/app.py` · `redbook/templates/{indicator_keybuild,indicator_locked}.html` ·
`tests/keystage.py` · `tests/test_indicator_key_universe.py` · `tests/test_architecture_separation.py` ·
`tests/test_{evidence_run_context,indicator_identity_binding}.py`


---

## Pass 5 — ขอบเขตของการเปิดผลเครื่อง และลิงก์ดาวน์โหลด (append-only)

> ตอบ `BO REVIEW COMPLETE — PRE-FREEZE CORRECTIONS PASS 4` (`5606392284`) · เนื้อหาข้างบนไม่ถูกแก้

| route | ก่อน Pass 5 | ตั้งแต่ Pass 5 |
|---|---|---|
| `GET /indicators/runs/{run}` (รายงาน) | เปิดได้เสมอ | **409 หน้าล็อก** จนกว่าตรวจผนึกผ่าน |
| `GET /indicators/runs` | แสดงจำนวนข้อสังเกต/คู่ของทุกรอบ | ซ่อนจำนวนของรอบที่ยังล็อก · ลิงก์ไปขั้นจัดทำเฉลยแทน |
| `GET /evidence/{doc}?obs=…&run=…` | แสดงข้อความ/กรอบที่เครื่องสกัด (ตรวจแค่ run context) | **409** ถ้ารอบยังล็อกหรือไม่ระบุรอบ |
| `GET /evidence/{doc}?page=…&run=…` (ไม่มี `obs`) | เปิดได้ | **เปิดได้เหมือนเดิม** — ขั้นเฉลยต้องใช้ |
| `POST …/mappings/{m}/decide` | ประกอบคู่ก่อน แล้วหน้า error แสดงคู่ได้ | ตรวจผนึก **ก่อน** ประกอบคู่ |
| `GET /indicators/exports/{name}` | ส่งไฟล์ถ้าชื่อถูกและไฟล์มีอยู่ | **410 เสมอ** (ไม่มีบริบทของรอบ) |
| `GET /indicators/runs/{run}/exports/{name}` *(ใหม่)* | — | ตรวจ manifest · รอบ · ผนึก ณ ตอนนี้ · digest · sha256 ของไฟล์ ก่อนส่งทุกครั้ง |

ลิงก์ไปหน้ารายงานถูกเอาออกจาก `indicator_keybuild.html` และ `indicator_locked.html` ·
`evidence_page.html` แสดงลิงก์รายงานเฉพาะเมื่อรอบนั้นเปิดผลเครื่องได้แล้ว

**ไฟล์ใหม่** — `tests/test_indicator_blind_boundary.py`
**ไฟล์เดิมที่แก้** — `redbook/indicators/{sourceinventory,keyuniverse,registry}.py` · `redbook/services/evidence.py` ·
`redbook/app.py` · `redbook/templates/{indicator_keybuild,indicator_locked,indicator_runs,evidence_page,indicator_verify}.html` ·
`tests/keystage.py` · `tests/test_{indicator_seal_verification,indicator_key_universe,indicator_identity_binding,evidence_routes,evidence_run_context,architecture_separation}.py`


---

## Pass 6 — ขั้นเฉลยมองไม่เห็นตัวเลขของเครื่อง · ผนึกครอบทุกคอลัมน์ (append-only)

> ตอบ `BO REVIEW COMPLETE — PRE-FREEZE HARDENING PASS 5` (`5615776981`) · เนื้อหาข้างบนไม่ถูกแก้

| หน้า | Pass 5 | ตั้งแต่ Pass 6 (ก่อนตรวจผ่านครบ) |
|---|---|---|
| `/indicators/runs/{run}/keybuild` | "ผนึกแล้ว · N คู่ · แฮช …" + แฮชย่อ/เหตุผลของทุกชั้น | ชั้นเครื่อง = **ผนึกแล้ว/ยังไม่ผนึก** เท่านั้น · ชั้นของคนแสดงได้ตามเดิม |
| หน้าล็อก | ตารางเหตุผลรายชั้นรวมของเครื่อง | view เดียวกับข้างบน + ข้อความ "ผนึกครบแล้วแต่ตรวจไม่ผ่าน ต้องเปิดรอบใหม่" |
| `/audit` | `detail_json` ดิบทุกรายการ | ฟิลด์ผลเครื่องของรอบที่ยังไม่ตรวจผ่าน = `[ซ่อนจนกว่ารอบนี้ผนึกครบและตรวจผ่าน]` · chain ไม่ถูกแตะ |

**ไฟล์ใหม่** — `tests/test_indicator_detector_blindness.py` · `tests/test_indicator_detector_projection.py`
**ไฟล์เดิมที่แก้** — `redbook/indicators/{keyuniverse,registry}.py` · `redbook/services/evidence.py` · `redbook/app.py` ·
`redbook/templates/{indicator_keybuild,indicator_locked}.html` · `tests/test_indicator_blind_boundary.py`
