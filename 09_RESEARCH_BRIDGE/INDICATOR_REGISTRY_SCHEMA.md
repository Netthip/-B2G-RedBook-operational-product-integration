# INDICATOR REGISTRY SCHEMA — ทะเบียนตัวชี้วัด + 8 สถานะการจับคู่ + การเปิดหลักฐาน PDF

**ป้ายกำกับ:** `PRODUCT EVIDENCE — POST-FREEZE` · **ฐานอำนาจ:** `GIFT DECISION` (Issue #1 · `5595281027`) §2–§3 · Gate 1–3
**ผู้บันทึก:** Giho · **สถานะ:** `PROPOSED — รอ Bo ตรวจ` · โค้ดจริงอยู่ที่ repo `redbook-verify` (`redbook/evidence/**` · `redbook/indicators/**`) · เอกสารเต็ม `docs/INDICATOR_REGISTRY_AND_PDF_TRACEABILITY.md` ใน repo นั้น

> 🔴 ตัวอย่างทั้งหมดในเอกสารนี้มาจาก **ชุดสังเคราะห์** (`tests/fixtures/synthetic_pdf` · หน่วยงานสมมติ "สถาบันทดสอบสังเคราะห์") — เผยแพร่ได้ · **ไม่ใช่เฉลย** · ไม่ใช่ข้อค้นพบในเอกสารจริง

---

## 1. ตัวตนของเอกสาร = content hash (ไม่ใช่ชื่อไฟล์)

| ฟิลด์ | ที่มา | หมายเหตุ |
|---|---|---|
| `document_id` | `"doc_" + sha256(เนื้อไฟล์)[:16]` | ไฟล์เดียวกันสองชื่อ = document เดียว · สองไฟล์ชื่อเดียวกัน = สอง document (เทสต์) |
| `content_sha256` · `byte_size` · `page_count` | คำนวณ | |
| `stage` | **ประกาศ** | `BUDGET_REQUEST · DRAFT_BILL · ENACTED_ACT · AO_REDBOOK · AO_BLUEBOOK · SYNTHETIC_TEST · UNSPECIFIED` |
| `fiscal_year` · `authority` · `agency_label` · `version_label` · `title` | **ประกาศ** | ระบบไม่เดาจากชื่อไฟล์ |
| `disclosure_class` | **ประกาศ** | `PUBLIC_PUBLISHED · INTERNAL_NOT_PUBLISHED · SYNTHETIC · UNKNOWN` — `UNKNOWN` = เผยแพร่ไม่ได้ (fail closed) |
| `text_layer_status` | ตรวจ | `TEXT_LAYER_PRESENT / PARTIAL / ABSENT / TEXT_LAYER_NOT_CHECKED_NO_BACKEND` |
| `local_path_private` | ส่วนตัว | อยู่ในฐานข้อมูลเครื่องผู้ใช้เท่านั้น — ไม่ออกทาง view/report/export/URL (เทสต์) |
| alias ชื่อไฟล์ | บันทึกแยก | ช่วยจำ · **ไม่ใช่ตัวตน** · ไม่ออกในไฟล์ส่งออก |

---

## 2. ข้อสังเกตต้นทาง (immutable source observation)

ตาราง `ind_observations` — trigger กัน `UPDATE/DELETE` · ครบตามฟิลด์ขั้นต่ำที่กิ๊ฟกำหนด

| ฟิลด์กิ๊ฟ §2 | คอลัมน์ |
|---|---|
| `indicator_id` (stable canonical ID) | รหัสชั่วคราว `IND-xxxxxxxxxx` ต่อข้อสังเกต → ผูกเป็นรหัสเดียวกัน **หลังมนุษย์ยืนยัน** `SAME_*` (`ind_bindings` append-only) — เครื่องไม่รวมรหัสเอง |
| source document ID/version/stage/year | `document_id` → ทะเบียนเอกสาร |
| exact observed text / normalized text | `observed_text` · `normalized_text` (คนละคอลัมน์ · ไม่แทนกัน) |
| definition · unit · target/baseline · method · period | `unit` · `target_text/target_value` · `baseline_text` · `method_text` · `period_text` (อ่านจากข้อความเมื่อมี · ว่างเมื่อไม่มี) |
| page · bounding box/anchor | `page` · `x0,y0,x1,y1` (point) · `page_width/height` · `location_confidence` ∈ `EXACT_BBOX / LINE_APPROX / PAGE_ONLY` |
| source hash | `source_sha256` |
| old↔new mapping status | ตาราง `ind_mappings` (แยก) |
| reviewer decision · reason · reviewer · timestamp | ตาราง `ind_decisions` (append-only · ผูก audit) |

การสกัด (`indicator-observe-0.1.0`): บรรทัดที่มีคำบ่งชี้ `ตัวชี้วัด / เชิงปริมาณ / เชิงคุณภาพ / ค่าเป้าหมาย / หน่วยนับ` · หน้าไม่มีชั้นข้อความ ⇒ ไม่มีข้อสังเกตจากเครื่อง + ปรากฏในบัญชีหน้าเป็น `LOCATION_REVIEW_REQUIRED` (ไม่เงียบ) · ผลนับเป็น **inventory** เท่านั้น

---

## 3. แปดสถานะและกติกาที่เครื่องเสนอได้

| # | สถานะ | เครื่องเสนอเมื่อ | คนต้องยืนยัน |
|---|---|---|---|
| 1 | `SAME_EXACT` | ข้อความตรงกันทุกอักขระ และเป็น 1:1 | ไม่บังคับ |
| 2 | `SAME_WORDING_VARIANT` | `variant_key` (ตัดช่องว่าง/วรรคตอน/เลขไทย→อารบิก) เท่ากัน และเป็น 1:1 | ไม่บังคับ |
| 3 | `SAME_CONCEPT_REPHRASED` | trigram-Dice ≥ 0.75 · ไม่มีคู่แข่งใกล้ · หน่วย/ค่าเป้าหมาย/วิธี/รอบ/ตัวเลข **ไม่ต่าง** | ✅ |
| 4 | `RELATED_NOT_EQUIVALENT` | **เครื่องไม่เสนอเลย** — ผู้ตรวจเลือกเอง | ✅ |
| 5 | `DEFINITION_CHANGED` | Dice ≥ 0.75 แต่ หน่วย/ค่าเป้าหมาย/วิธี(ตัวหาร/ขอบเขต)/รอบ/ตัวเลข **ต่าง** | ✅ |
| 6 | `NEW_INDICATOR` | ใหม่ไม่มีคู่ที่ Dice ≥ 0.50 | ไม่บังคับ |
| 7 | `REMOVED_INDICATOR` | เก่าไม่มีคู่ที่ Dice ≥ 0.50 | ไม่บังคับ |
| 8 | `AMBIGUOUS_REVIEW_REQUIRED` | ข้อความซ้ำในฉบับเดียว (one-to-many) · คู่แข่งใกล้กัน (≤ 0.05) · Dice 0.50–0.75 | ✅ |

กติกาที่บังคับในโค้ด + เทสต์: สถานะ 3·4·5·8 = `human_required` เสมอ · เครื่องไม่เสนอสถานะ 4 · ความคล้ายสูงแต่นิยาม/หน่วย/ตัวเลขต่าง **ไม่มีทางได้ `SAME_*`** · จับคู่เป็น global phase (ผลไม่ขึ้นกับลำดับ) · ทุกข้อสังเกตต้องมีแถว (accounted) · เกณฑ์ 0.75/0.50/0.05 บันทึกเป็น `rules_json` + `rules_hash` ต่อรอบ

**เทสต์เชิงลบ** (`tests/test_indicator_mapping.py`): ร้อยละ 80 vs 85 · 200 คน vs 200 ครั้ง · (นับจากทั้งหมด) vs (นับจากที่ได้รับจัดสรร) · รายปี vs รายไตรมาส · ผู้ป่วย vs ผู้ป่วยนอก · ข้อความซ้ำ 2 ที่ — ทุกกรณี `human_required=True` และไม่ใช่ `SAME_*`

---

## 4. คำตัดสินของผู้ตรวจ

`ACCEPT` (รับสถานะที่เสนอ หรือระบุสถานะสุดท้ายเอง) · `REJECT` (ต้องระบุสถานะที่ถูกต้องและต่างจากที่เสนอ) · `AMBIGUOUS` (คงเป็น `AMBIGUOUS_REVIEW_REQUIRED`) · ต้องมีผู้ตรวจ · สถานะตระกูล 3/4/5/8 ต้องมีเหตุผล · **เพิ่มอย่างเดียว** (สถานะปัจจุบัน = คำตัดสินล่าสุด · ประวัติครบ) · ทุกคำตัดสินอยู่ในธุรกรรมเดียวกับ Audit Trail

---

## 5. การเปิดหลักฐาน PDF (route ที่ควบคุม · ไม่มี path · ไม่มี `file://`)

| route | ผล |
|---|---|
| `/evidence/{document_id}?page=n&obs=<id>` | หน้าหลักฐาน: id · sha256 · ขั้น · ปี · รุ่น · ชั้นการเปิดเผย · ชั้นข้อความ · ข้อความตามที่ปรากฏ · กรอบ · **ภาพหน้าพร้อมกรอบเน้น** · ปุ่มเปิด PDF ที่หน้า n |
| `/evidence/{document_id}/file#page=n` | สตรีม PDF inline (ชื่อ = `document_id.pdf`) — เบราว์เซอร์เปิดที่หน้า n |
| `/evidence/{document_id}/page/{n}.png?hl=…` | ภาพหน้า + กรอบเน้น |
| `/evidence/compare?run=&map=` | **เทียบข้างกัน** + ความต่างนิยาม/หน่วย/วิธี/รอบ + ฟอร์มคำตัดสิน · ไม่มีคะแนน |

กรณีที่ทดสอบ: ย้ายหน้า · เลขหน้าเปลี่ยน · หน้าไม่มีชั้นข้อความ (`LOCATION_REVIEW_REQUIRED`) · ข้อความซ้ำ · ไฟล์ต้นทางหาย/ถูกแทนที่ (`SOURCE_UNAVAILABLE` · 404 ไม่ crash) · id ผิดรูป (400/404)
ความเป็นส่วนตัว: ไม่มี absolute path · `file://` · raw exception · ข้อความจากเอกสารใน URL/ล็อก · ข้อความจากเอกสารที่ยังไม่เผยแพร่ในไฟล์ส่งออก (แทนด้วยตัวยึด)

ภาพประกอบ (สังเคราะห์): `assets/indicator_evidence_synthetic_old_p3_highlight.png` · `assets/indicator_evidence_synthetic_new_p4_highlight.png`

---

## 6. ตัวอย่างต่อสถานะ (สังเคราะห์ · เผยแพร่ได้ · ไม่ใช่เฉลย)

| เครื่องเสนอ | เก่า (หน้า) | ใหม่ (หน้า) |
|---|---|---|
| `SAME_EXACT` | ตัวชี้วัดที่ 1 : ร้อยละของหน่วยงานที่ได้รับการอบรม เป้าหมาย ร้อยละ 80 (2) | เหมือนเดิม (3) — ย้ายหน้า |
| `SAME_WORDING_VARIANT` | ตัวชี้วัดที่ 2 : ร้อยละของบุคลากรที่ผ่านการประเมิน (ร้อยละ 90) (2) | ตัวชี้วัดที่ 2 : ร้อยละ ของบุคลากร ที่ผ่านการประเมิน ( ร้อยละ ๙๐ ) (3) |
| `SAME_CONCEPT_REPHRASED` ✅คน | ตัวชี้วัดที่ 3 : จำนวนรายงานวิจัยที่เผยแพร่ ไม่น้อยกว่า 5 เรื่อง (2) | …ที่ได้รับการเผยแพร่… (3) |
| `DEFINITION_CHANGED` ✅คน | ตัวชี้วัดที่ 4 : …(นับจากโครงการทั้งหมด) ร้อยละ 85 (3) | …(นับจากโครงการที่ได้รับจัดสรรงบประมาณ) ร้อยละ 85 (4) |
| `AMBIGUOUS_REVIEW_REQUIRED` ✅คน | ตัวชี้วัดที่ 5 : จำนวนผู้เข้ารับการอบรม 200 คน (3) | ตัวชี้วัดที่ 5 : จำนวนหลักสูตรอบรมที่เปิดสอน 4 หลักสูตร (4) → คนอาจตัดสิน `RELATED_NOT_EQUIVALENT` |
| `AMBIGUOUS_REVIEW_REQUIRED` ×2 ✅คน | ตัวชี้วัดที่ 7 : จำนวนกิจกรรมเผยแพร่ความรู้ 12 ครั้ง (3) | ข้อความเดียวกัน 2 ที่ (4, 5) |
| `REMOVED_INDICATOR` | ตัวชี้วัดที่ 6 : ร้อยละของข้อร้องเรียนที่ได้รับการแก้ไข ร้อยละ 100 (3) | — |
| `NEW_INDICATOR` | — | ตัวชี้วัดที่ 8 : ร้อยละของระบบที่ผ่านการทดสอบความปลอดภัย ร้อยละ 95 (2) |

บัญชี: เก่า 7 ข้อสังเกต (หน้า 4 ไม่มีชั้นข้อความ → ตัวชี้วัดในหน้านั้นไม่ถูกสกัด และถูกติดป้ายให้คนกรอก) · ใหม่ 8 · 9 แถว · accounted ปิด
