# FREEZE CANDIDATE MANIFEST — indicator registry / PDF evidence detector

> **สถานะ: `FREEZE CANDIDATE — NOT TAGGED`** · ปรับหลัง **Hardening Pass 6**
> (ตอบ `BO REVIEW COMPLETE — PRE-FREEZE HARDENING PASS 5` `5615776981`)
> · เนื้อหาของ Pass 1–5 ด้านล่าง **คงไว้ตามเดิม** — เพิ่มหัวข้อไปข้างหน้าเท่านั้น
>
> _(บันทึกเดิมของ Pass 5)_ · ปรับหลัง **Hardening Pass 5**
> (ตอบ `BO REVIEW COMPLETE — PRE-FREEZE CORRECTIONS PASS 4` `5606392284`)
> · เนื้อหาของ Pass 1–4 ด้านล่าง **คงไว้ตามเดิม** — เพิ่มหัวข้อไปข้างหน้าเท่านั้น
>
> _(บันทึกเดิมของ Pass 4)_ · ปรับหลัง **Corrective Pass 4**
> (ตอบ `BO REVIEW COMPLETE — PRE-FREEZE CORRECTIONS PASS 3` `5605652708`)
> · เนื้อหาของ Pass 1–3 ด้านล่าง **คงไว้ตามเดิม** — เอกสารนี้เพิ่มหัวข้อไปข้างหน้าเท่านั้น
>
> _(บันทึกเดิมของ Pass 3)_ · ปรับหลัง **Corrective Pass 3**
> (ตอบ `BO REVIEW COMPLETE — PRE-FREEZE CORRECTIONS PASS 2` `5600162467`)
> · เนื้อหาของ Pass 1/Pass 2 ด้านล่าง **คงไว้ตามเดิม** — เอกสารนี้เพิ่มหัวข้อไปข้างหน้า ไม่ทับหลักฐานรอบก่อน
>
> _(บันทึกเดิมของ Pass 2)_ · ปรับหลัง **Corrective Pass 2**
> (ตอบ `BO REVIEW — PRE-FREEZE CORRECTIONS PASS 1` `5598957701` และ
> `BO REVIEW COMPLETE — PRE-FREEZE CORRECTIONS PASS 1` `5598526148` Lane B6.1)
> · ป้ายกำกับ `PRODUCT EVIDENCE — POST-FREEZE`
> · ผลเทสต์ทุกตัว = **developer-machine reported result** · **ไม่มี GitHub CI status** สำหรับ commit ใด ๆ ของ repo นี้ — ห้ามเขียน "CI passed"
> · tag freeze จะติด **หลัง Bo ตรวจรับ Pass 2** และ **ก่อน** ที่กิ๊ฟจะสร้าง/ผนึกเฉลยของจริง
> · ไม่มีการรันเอกสารจริง / สร้างเฉลยของงานวิจัย / scoring / unblind ในรอบนี้

## 1. สภาพแวดล้อมที่รัน (exact)

| รายการ | ค่า |
|---|---|
| Python | 3.12.9 (`.venv\Scripts\python.exe` ของโครงการ) |
| OS | Windows 11 Home Single Language · build 10.0.26200 · AMD64 |
| dependency snapshot | `requirements.lock.txt` (41 แพ็กเกจ · ชุดปริยาย · **ไม่มี PyMuPDF**) — ตรวจแล้วว่า **ไม่เปลี่ยนจาก Pass 1** |
| extra วิจัยที่ติดตั้งในเครื่องนี้ (นอกชุดปริยาย) | `requirements-research-pymupdf.txt` → `pymupdf==1.27.2.3` — ใช้เฉพาะเทสต์ equivalence และสร้าง fixture · **ไม่ใช่ส่วนของ freeze** และ **product path เรียกไม่ได้** |
| backend PDF ของผลิตภัณฑ์ | `pdfplumber 0.11.9` · `pdfminer.six 20251230` · `pypdfium2 5.8.0` · `pillow 12.3.0` (`pdftext-0.2.0` · `PdfplumberPdfiumBackend`) — **ไม่มี fallback อัตโนมัติ** |
| detector | `indicator-observe-0.2.0` · `indicator-normalize-0.1.0` · `indicator-mapping-0.2.0` (`rules_hash 2279b48175707565` · rephrase_min 0.75 · ambiguous_min 0.50 · tie_margin 0.05) · `indicator-identity-0.1.0` · `indicator-registry-0.2.0` (schema v2) · `evidence-documents-0.2.0` · `evidence-service-0.2.0` · `sealed-key-ingestion-guard-0.1.1` |
| fixture | `tests/fixtures/synthetic_pdf/` · sha256 ทั้งสี่ไฟล์ใน `MANIFEST.json` · ชุดหลัก **คงไบต์เดิมจาก Pass 1** (`b59b868b…` / `51153258…` — ไม่ย้อน/ไม่สร้างใหม่ ตามคำสั่ง Bo P1-2) + **ชุดขอบเขตที่เพิ่มใหม่** `synthetic_clipped_old.pdf` (`ba513478…`) / `synthetic_clipped_new.pdf` (`dd6fc8e3…`) ที่คงข้อความล้นขอบไว้ · ⚠️ การสร้าง PDF ใหม่ไม่ให้ไบต์เดิมทุกครั้ง (font subsetting) ⇒ แฮชเปลี่ยนได้แม้เนื้อหาเท่าเดิม |
| repo / branch | `redbook-verify` · `t1b/fy2570-mvp` · commit ของรอบแก้ = ดู handoff `HANDOFF READY FOR BO — PRE-FREEZE CORRECTIONS PASS 2` |

## 2. คำสั่งและผลการรัน (developer-machine reported result)

```
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
  started  2026-09-09T09:41:28Z
  finished 2026-09-09T09:42:39Z   (69.10 s)
  result   1005 passed · 0 failed · 0 skipped
scripts\test_report.py
  unit / synthetic 794 · private real-data integration 211 · SKIPPED(PRIVATE DATASET NOT AVAILABLE) 0
```

| ชั้น | หมายเหตุ |
|---|---|
| unit / synthetic 794 | ไม่พึ่งข้อมูลจริง · ไฟล์ใหม่รอบนี้: `test_indicator_identity_binding.py` (16) · `test_indicator_conservation.py` (14) · `test_evidence_run_context.py` (17) · `test_pdf_backend_equivalence.py` เขียนใหม่ (23) |
| private 211 | รันจริงในเครื่องนี้เพราะมี `redbook-verify-data` · เครื่องที่ไม่มีต้องได้ `794 passed, 211 skipped` — ถ้าได้ 1005 แปลว่ามี private dataset |
| equivalence | สอง backend อ่าน fixture หลักได้ข้อความทุกบรรทัดเท่ากัน (9 หน้า) · กรอบต่าง ≤ 4 pt · **สถานะที่เสนอทั้งชุดเท่ากันบนทั้งสอง backend** |
| edge case (P1-2) | fixture ชุดขอบเขต **ไม่บังคับ** ให้สอง parser อ่านเท่ากัน (วัดจริงต่างกัน: x1 876 vs 595 pt) แต่บังคับว่าคู่นั้นต้องเป็น `AMBIGUOUS_REVIEW_REQUIRED` เสมอ |

## 3. dependency lock · license · audit

| รายการ | ที่ |
|---|---|
| lock (ชุดปริยาย) | `requirements.lock.txt` — หัวไฟล์เป็น ASCII โดยเจตนา (parser ของ pip-audit อ่านด้วย codepage ระบบ cp874 แล้วล้มกับอักษรไทย) |
| extra วิจัย | `requirements-research-pymupdf.txt` (`LICENSE REVIEW REQUIRED` · ห้าม merge/release/deploy) |
| บัญชีสัญญาอนุญาต (**ไม่ใช่ legal clearance**) | `docs/DEPENDENCY_LICENSE_INVENTORY.md` — 42 แพ็กเกจรวม transitive |
| pip-audit | `pip-audit 2.10.1` · target `requirements.lock.txt --no-deps` · รันสองครั้ง (Pass 1 `07:29Z` · Pass 2 `09:44Z`) · **`No known vulnerabilities found` · exit 0** ทั้งสองครั้ง · ผลดิบ `docs/pip_audit_lock_2026-09-09.txt` · สะท้อนฐานข้อมูล advisory ณ วันรันเท่านั้น · ไม่ครอบโค้ดของโครงการ · **ไม่ได้ hash-pin** (artifact เตือนเอง) |

## 4. ถ้อยคำที่ต้องใช้ให้ตรง

* ด่าน `redbook/sealed_key.py` = **accidental sealed-key ingestion guard** — "The application rejects paths matching the declared sealed-key naming convention before opening them." · **ไม่ใช่ access control** · **ไม่พิสูจน์ว่าผู้พัฒนาเข้าถึงเฉลยไม่ได้** · ผลสแกน = inventory evidence เท่านั้น
* การแก้ `redbook/services/t1b.py` (+3 บรรทัด) = **`REVIEWED — ACCEPTED`** recorded scope deviation (Bo `5597645315` ข้อ 8) · ห้าม revert
* ผลเทสต์ = developer-machine reported result · **ไม่มี CI**
* `PROVISIONAL-…` = รหัส**ชั่วคราว** · `IND-…` = canonical · **ห้ามเรียก provisional ว่า canonical**
* ชุด XLSX ของหน้า `/verify` = **POST-RUN ADJUDICATION PACKAGE** · **ห้ามใช้สร้างหรือยืนยันเฉลยที่ปิดผนึก**

## 5. สถานะ freeze blockers (union ตาม `5597709987` §3)

| รหัส | เรื่อง | สถานะ | หลักฐาน |
|---|---|---|---|
| **A** | จำกัดขอบเขตข้อกล่าวอ้าง accidental-ingestion guard | ✅ ปิด (Pass 1) | `sealed_key.py` · `test_sealed_key_guard.py` |
| **B1** | canonical `indicator_id` ข้าม run/document/year + migration | ⚠️ Pass 2 = CONDITIONAL (Bo `5600162467`) → แก้ใน **Pass 3** | `indicators/identity.py` · schema v2 + migration · `test_indicator_identity_binding.py` |
| **B2** | effective binding จากคำตัดสินล่าสุด · conflict gate · transitive | ✅ ปิด (Pass 2) | `registry.resolve_identity/effective_bindings` · เทสต์สี่กรณีของ Bo ครบ |
| **B3** | conservation gate จริง + mutation tests | ✅ ปิด (Pass 2) | `mapping.accounted` (7 ด่าน) · `test_indicator_conservation.py` |
| **B4** | แยก KEY BUILD/VERIFY ออกจาก POST-RUN ADJUDICATION | ❌ Pass 2 = **ไม่ปิด** (Bo `5600162467`) → แก้ใน **Pass 3** | `ind_key_entries` / `ind_key_seals` · route `/keybuild` · gate ที่ `/verify` · `/compare` · package |
| **B5** | evidence route พก **และตรวจ** run context | ✅ ปิด (Pass 2) | `/evidence/{doc}?run=` · `RUN_CONTEXT_MISSING` / `MISMATCH` · `test_evidence_run_context.py` |
| **B6** | permissive default backend + lock/license/audit | ✅ ปิด (Pass 1 + P1-1/P1-2 ใน Pass 2) | `pdftext-0.2.0` fail-closed · `test_pdf_backend_equivalence.py` |
| **C** | Gift ตรวจ/override ได้ทุกแถวรวม 1/2/6/7 | ✅ ปิด (Pass 1) | `test_indicator_override_1267.py` |
| **D** | ถ้อยคำ reproducibility / no-CI | ✅ ปิด (Pass 1) | เอกสารฉบับนี้ |
| **H1** | full-digest collision/equality handling | ✅ ปิด (Pass 2) | `DocumentIdCollision` · `get_by_sha256` · `verify_identity` |
| **H2** | manual observation occurrence identity | ✅ ปิด (Pass 2) | `manual_anchor()` · `test_indicator_identity_binding.py` |
| **H3** | Python/platform/backend/dependency freeze manifest | ✅ ปิด (Pass 1 · ปรับตัวเลขใน Pass 2) | เอกสารฉบับนี้ + `requirements.lock.txt` |

🔴 **การปิดในตารางนี้คือสิ่งที่ผู้พัฒนาทำและทดสอบแล้ว — ไม่ใช่การรับรองของ Bo**
สถานะทางการยังเป็น `FREEZE BLOCKED` จนกว่า Bo จะตรวจรับ Pass 2

## 6. สิ่งที่ยัง **ไม่** ปิดด้วยโค้ด (ต้องมีคนตัดสิน)

1. **legal clearance** ของ dependency — บัญชีสัญญาอนุญาตไม่ใช่คำวินิจฉัยทางกฎหมาย
2. **การแยกบทบาทจริง** (generator/key builder ที่ไม่ใช่ Giho · ตำแหน่งเก็บเฉลยที่ผู้พัฒนาเข้าไม่ถึง) — อยู่นอก repo ทั้งหมด
3. **เอกสารจริง** ที่จะใช้ · ชั้นการเปิดเผยของแต่ละฉบับ
4. **เกณฑ์ 0.75 / 0.50 / 0.05** — ตรึงพร้อม detector ก่อนสร้างเฉลย · ห้ามปรับหลังเห็นเฉลย
5. **OCR** สำหรับหน้าที่ไม่มีชั้นข้อความ — เป็นเวอร์ชัน detector ถัดไป (ground truth ยังต้องมาจากคน)
6. tag / merge `main` / deploy / เอกสารจริง / เฉลยจริง / scoring / unblind / ใส่ลงเล่ม


---

## 7. Corrective Pass 3 (ตอบ `BO REVIEW COMPLETE — PRE-FREEZE CORRECTIONS PASS 2` `5600162467`)

> เขียนเพิ่มแบบ **forward-only** — ตัวเลขและข้อความของ Pass 1/Pass 2 ข้างบนไม่ถูกแก้

### 7.1 สิ่งที่ Bo ตีกลับ และสิ่งที่ทำ

| รหัส | คำวินิจฉัยของ Bo | สิ่งที่แก้ใน Pass 3 |
|---|---|---|
| **B1** | *"earliest pinned ID wins is not implemented"* — โค้ดอ่าน `ind_canonical_ids` ตาม `seq` แล้วแปลงเป็น dict ทำให้ลำดับหาย · `pick_canonical()` ไล่สมาชิกที่เรียงตาม **ตัวอักษร** | `_pinned_ids()` คืนลำดับ `seq` เพิ่มมาอีกชุด · `pick_canonical(component, pinned, established_order)` เลือกด้วย `seq` น้อยสุด · เทสต์ที่ **ลำดับเวลากลับทางกับลำดับตัวอักษร** |
| **B4-a** | *"key construction still consumes detector output"* — `key_build_rows(rv)` ไล่ `rv.pairs` ⇒ การจับคู่ · จำนวนคู่ · ลำดับ ยังเป็นของ detector | ตัดทั้งเส้น — `keyuniverse.py` ใหม่ · ตาราง `ind_key_universe` สร้างจาก `ind_observations` เท่านั้น · `item_id` มาจาก `identity_key` ไม่ใช่ `mapping_id` · ลำดับกลาง (แฮชเอกสาร→หน้า→สมอ) · `record_key_entry()` เดิมถูกทำให้ **ปฏิเสธ** |
| **B4-b** | *"permits an incomplete key to unlock adjudication"* — `seal_key()` ขอเพียง `latest_key_entries()` ไม่ว่าง | ด่านครบถ้วน 9 ข้อ (`key-coverage-gate-0.1.0`) · ผนึกไม่ได้ถ้า ศูนย์/ไม่ครบ/ซ้ำ/ขาด/เกิน/จับคู่ทางเดียว/รูปทรงผิด |
| **B4-c** | seal digest ต้องผูกตัวตน การจับคู่ สถานะ เหตุผล แฮชเอกสารเต็ม เวอร์ชัน และ manifest ของจักรวาล | `keyuniverse.seal_digest()` ผูกครบทุกข้อ · เหตุผลผูกด้วย **แฮชของเหตุผล** เพื่อไม่ให้ข้อความจากเอกสารรั่วผ่านค่าที่บันทึกในที่สาธารณะ |
| **B4-d** | snapshot/seal ของผลลัพธ์ detector ต้องแยกจาก seal ของเฉลย · adjudication เปิดเมื่อผนึกครบทั้งสอง | `ind_detector_snapshots` + `seal_detector_snapshot()` · `adjudication_unlocked()` = `key_seal AND detector_snapshot` · ป้ายล็อกเปลี่ยนเป็น `ADJUDICATION_LOCKED_KEY_OR_DETECTOR_NOT_SEALED` |

### 7.2 schema v3 (migration แบบเพิ่มตาราง — ไม่แตะข้อมูลเดิม)

`ind_key_universe` · `ind_key_universe_seals` · `ind_key_answers` · `ind_detector_snapshots`
ตาราง `ind_key_entries` ของ Pass 2 **ยังอยู่ครบในฐานะประวัติ** — ไม่ถูกลบและไม่ถูกเขียนทับ
แต่ทางเขียนถูกปิด (`record_key_entry()` โยน `KeyStageError`) เพราะผูกกับ `mapping_id` ของ detector

### 7.3 ลำดับที่ระบบบังคับ

```
สร้างจักรวาลจากข้อสังเกต → ตรึงจักรวาล → กรอกคำตอบให้ครบทุกรายการ
                                              ↓
                        ผนึกเฉลย (ผ่านด่านครบถ้วนเท่านั้น)
                                              +
                        ผนึก snapshot ของผลลัพธ์ detector
                                              ↓
                              ขั้นตัดสินหลังรันจึงเปิด
```

### 7.4 negative tests ห้าชุดที่ Bo สั่ง — อยู่ที่ `tests/test_indicator_key_universe.py`

| ข้อ | เทสต์ | สิ่งที่พิสูจน์ |
|---|---|---|
| 1 | `test_negative_1_changing_detector_pairing_leaves_key_rows_untouched` | เปลี่ยนเกณฑ์จนเครื่องจับคู่ต่างออกไปจริง แล้ว `universe_digest` และรายการของขั้นเฉลย **ไม่ขยับ** |
| 2 | `test_negative_2_zero_and_partial_coverage_cannot_seal` | 0-of-N และ 1-of-N ผนึกไม่ได้ · adjudication ยังปิด |
| 3 | `test_negative_3_missing_duplicate_and_extra_items_cannot_seal` · `test_negative_3b_one_sided_pairing_is_not_accepted` | ขาด / ซ้ำ / เกิน / จับคู่ทางเดียว ผนึกไม่ได้ |
| 4 | `test_negative_4_changing_any_sealed_field_invalidates_the_digest` | เปลี่ยนสถานะ · เหตุผล · การจับคู่ · แฮชเอกสาร · เวอร์ชัน schema · manifest ⇒ digest เปลี่ยนทุกกรณี |
| 5 | `test_negative_5_complete_key_plus_detector_seal_unlocks_adjudication` | เฉลยครบ **อย่างเดียวยังไม่ปลดล็อก** ต้องผนึก snapshot ของเครื่องด้วย |

### 7.5 ผลการรัน Pass 3 (developer-machine reported result · **ไม่มี CI**)

```
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
  started  2026-09-09T16:43:08Z
  finished 2026-09-09T16:44:24Z   (74.44 s)
  result   1031 passed · 0 failed · 0 skipped
scripts\test_report.py
  unit / synthetic 820 · private real-data integration 211 · SKIPPED(PRIVATE DATASET NOT AVAILABLE) 0
```

ไฟล์เทสต์ใหม่: `tests/test_indicator_key_universe.py` (22) · ตัวช่วยใหม่ `tests/keystage.py`
ด่านสถาปัตยกรรมใหม่ใน `tests/test_architecture_separation.py` (2) — handler ของขั้นเฉลยใน `app.py`
ต้องไม่อ้าง `run_view` / `pair_view` / `mappings` / `key_build_rows` เลย (ตรวจด้วย AST)

### 7.6 ข้อจำกัดที่พบระหว่าง Pass 3 — ต้องอ่านคู่กับ §6

1. **เฉลยรองรับการจับคู่แบบหนึ่งต่อหนึ่งเท่านั้น** — ถ้าผู้จัดทำเฉลยเห็นความสัมพันธ์แบบ
   หลายต่อหลาย ต้องตอบ `AMBIGUOUS_REVIEW_REQUIRED` ทั้งสองฝั่งโดยไม่ระบุคู่ แล้วอธิบายในเหตุผล
   ⇒ **ระบบยังบันทึกเฉลยแบบหลายต่อหลายตรง ๆ ไม่ได้** เป็นข้อจำกัดที่ประกาศไว้ ไม่ใช่ข้อบกพร่องที่ซ่อน
2. **แถวจาก schema v1 ที่ไม่มี `identity_key` สร้างจักรวาลของเฉลยไม่ได้** — ล้มแบบเห็นชัด
   (`KeyStageError`) ไม่ใช่สร้างจักรวาลที่พิสูจน์ตัวตนไม่ได้แล้วเดินต่อ
3. **ลำดับยังบังคับได้ แต่ตัวบุคคลยังบังคับไม่ได้** — ยังไม่มีระบบบัญชีผู้ใช้ · ช่อง "ผู้ผนึก"
   เป็นข้อความที่ผู้กรอกพิมพ์เอง ⇒ การแยกบทบาทจริงยังอยู่นอก repo (ยังเป็นข้อ 2 ของ §6)
4. **`entered_by` ของคำตอบไม่ถูกส่งกลับมาแสดงในหน้า** โดยเจตนา (ลดการชี้นำระหว่างผู้กรอกหลายคน)
   ประวัติเต็มยังอยู่ใน `ind_key_answers` และ audit chain
5. **การผนึก snapshot ของ detector ผูกกับ `rules_hash` ของรอบนั้น** — ถ้าเปลี่ยนเกณฑ์แล้วรันใหม่
   จะเป็นคนละรอบและต้องผนึกใหม่ · ระบบไม่รวมสองรอบให้อัตโนมัติ


---

## 8. Corrective Pass 4 (ตอบ `BO REVIEW COMPLETE — PRE-FREEZE CORRECTIONS PASS 3` `5605652708`)

> forward-only — ตัวเลขและข้อความของ Pass 1–3 ข้างบนไม่ถูกแก้

### 8.1 สิ่งที่ Bo ตีกลับ และสิ่งที่ทำ

| รหัส | คำวินิจฉัยของ Bo | สิ่งที่แก้ใน Pass 4 |
|---|---|---|
| **P3-1** | *"stored seals are not verified when unlocking … A stored hash is only evidence; it is not an enforcement gate until verified."* | `verify_universe_seal` / `verify_key_seal` / `verify_detector_snapshot` **คำนวณใหม่จากแถวปัจจุบัน** แล้วเทียบด้วย `hmac.compare_digest` · `adjudication_unlocked()` = `seal_verification().ok` · มีรหัสเหตุผล 12 รหัสที่แสดงบนหน้าจอ |
| **P3-2** | *"the 'independent' key universe still depends on detector extraction … if the detector fails to extract a real indicator, that item never enters `ind_observations` … The evaluation can therefore overstate recall."* | `indicators/sourceinventory.py` ใหม่ + ตาราง `ind_source_inventory` — **คนอ่านเอกสารแล้วกรอกเอง** · จักรวาลของเฉลยตั้งต้นจากทะเบียนนี้ · `detector_coverage()` เทียบให้เห็นรายการที่เครื่องสกัดตกหล่น |
| **ลำดับ** | ตรึงทะเบียนอิสระ → ผนึกผลเครื่อง → ทำและผนึกเฉลย → เปิดการเทียบผล | บังคับด้วยด่านในทุกฟังก์ชันที่เกี่ยวข้อง (มีเทสต์ทุกขั้น) |

### 8.2 schema v4 (migration แบบเพิ่มตาราง/คอลัมน์ — ไม่แตะข้อมูลเดิม)

`ind_source_inventory` · `ind_source_inventory_retractions` · คอลัมน์
`ind_runs.old_document_sha256` / `new_document_sha256` (แฮชเนื้อเอกสาร **เต็ม** บันทึกตั้งแต่สร้างรอบ)
ตารางของ Pass 3 ทั้งหมด **ยังอยู่ครบ** · เพิ่ม trigger `ind_key_universe_no_delete` ที่ Pass 3 ตกไป

### 8.3 การตรวจผนึกตรวจอะไรบ้าง

| artifact | คำนวณใหม่จาก | เทียบกับ | รหัสเหตุผลเมื่อไม่ตรง |
|---|---|---|---|
| `UNIVERSE` | แถว `ind_key_universe` **และ** ทะเบียนอิสระที่มีผล ณ ขณะนี้ | `ind_key_universe_seals.universe_digest` + `item_count` | `UNIVERSE_DIGEST_MISMATCH` · `UNIVERSE_ROWS_DIFFER_FROM_INDEPENDENT_INVENTORY` · `UNIVERSE_ITEM_COUNT_MISMATCH` · `UNIVERSE_NOT_FROZEN` |
| `KEY` | คำตอบที่มีผล + จักรวาล + แฮชเอกสาร + เวอร์ชัน + manifest | `ind_key_seals.key_digest` + `entries_count` + ด่านครบถ้วน | `KEY_DIGEST_MISMATCH` · `KEY_ANSWER_COUNT_MISMATCH` · `KEY_COVERAGE_NO_LONGER_CLOSED` · `KEY_NOT_SEALED` |
| `DETECTOR_OUTPUT` | แถว `ind_mappings` ปัจจุบัน + `rules_hash` ของรอบ | `ind_detector_snapshots` | `DETECTOR_OUTPUT_DIGEST_MISMATCH` · `DETECTOR_PAIR_COUNT_MISMATCH` · `DETECTOR_RULES_HASH_MISMATCH` · `DETECTOR_OUTPUT_NOT_SEALED` |

**ห้ามซ่อมทับ** — เมื่อไม่ตรงแล้ว `seal_*` / `freeze_*` / `record_key_answer` / `record_source_item`
ปฏิเสธทั้งหมด · ทางเดียวคือเปิดรอบประเมินใหม่ (มีเทสต์)

### 8.4 เทสต์ของรอบนี้

`tests/test_indicator_seal_verification.py` (14) — mutation ของทั้งสาม artifact ผ่านการต่อฐานข้อมูลตรง ๆ
(ต้องถอด trigger ก่อน ซึ่งเป็นสิ่งที่ผู้เข้าถึงไฟล์ฐานข้อมูลจะทำ) แล้วพิสูจน์ว่า **ล็อกกลับ** ·
`ind_mappings` แทรกแถวได้โดยไม่ต้องถอด trigger (ตารางนั้นห้ามแก้/ลบ แต่ไม่ห้ามเพิ่ม) ⇒ เป็น mutation ที่สมจริงที่สุด
`tests/test_indicator_key_universe.py` เพิ่ม 6 ข้อ — รายการที่เครื่องสกัดตกหล่น · ลำดับที่บังคับ · การถอนรายการ
`tests/test_architecture_separation.py` เพิ่ม 1 ข้อ — โมดูลทะเบียนอิสระต้องไม่รู้จักทะเบียนของ detector

### 8.5 ผลการรัน Pass 4 (developer-machine reported result · **ไม่มี CI**)

```
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
  started  2026-09-09T17:41:13Z
  finished 2026-09-09T17:42:41Z   (86.95 s)
  result   1052 passed · 0 failed · 0 skipped
scripts\test_report.py
  unit / synthetic 841 · private real-data integration 211 · SKIPPED(PRIVATE DATASET NOT AVAILABLE) 0
```

### 8.6 ข้อจำกัดที่พบระหว่าง Pass 4 — อ่านคู่กับ §6 และ §7.6

1. **ต้นทุนแรงงานของทะเบียนอิสระ** — ผู้ดูแลต้องกรอกตัวชี้วัดทีละรายการจากการอ่านเอกสารเอง
   เอกสารจริงหลายร้อยหน้าจะใช้เวลามาก · ระบบ **ไม่มี** ปุ่ม "นำเข้าจากสิ่งที่เครื่องสกัดได้"
   โดยเจตนา เพราะนั่นคือสิ่งที่ Bo สั่งห้าม · นี่เป็นข้อจำกัดเชิงกระบวนการที่ต้องยอมรับ
   หรือให้กิ๊ฟตัดสินขอบเขตของ endpoint ใหม่
2. **การเทียบทะเบียนอิสระกับข้อสังเกตของเครื่องใช้ (ฝั่ง · แฮชเอกสาร · หน้า · ข้อความรูปมาตรฐาน ·
   ลำดับที่ปรากฏ)** ไม่ใช่ `identity_key` เพราะสมอของสองฝ่ายคนละรูปโดยธรรมชาติ
   (`line:{index}` กับ `manual:{n}`) ⇒ `NO_MATCH` แปลว่า **"เครื่องไม่ได้ให้ข้อสังเกตที่เทียบเท่ากัน"**
   จะเป็นการสกัดตกหล่นจริงหรือการตัดบรรทัดต่างกัน **เป็นคำตัดสินของคน** ระบบไม่สรุปแทน
3. **`detector_coverage()` ไม่ใช่คะแนน** — เป็นการแสดงรายการที่ไม่ตรงกันเท่านั้น
   ยังไม่มี precision/recall ใด ๆ ในระบบ และห้ามอ่านตัวเลขนี้เป็นผลการประเมิน
4. **แถวจากรอบเก่า (ก่อน v4) ไม่มีแฮชเอกสารระดับรอบ** ⇒ กรอกทะเบียนอิสระไม่ได้ ระบบบอกเหตุผลตรง ๆ
   และต้องเปิดรอบใหม่ · รอบสาธิตของ Pass 3 จึงถูกล็อกกลับทั้งหมด ซึ่งเป็นพฤติกรรมที่ถูกต้อง
5. **ระบบยังบังคับได้เฉพาะลำดับ ไม่ใช่ตัวบุคคล** — ยังไม่มีระบบบัญชีผู้ใช้ (ข้อเดิมจาก Pass 3)
6. **กรณีหนึ่งต่อหลาย** ยังต้องตอบ `AMBIGUOUS_REVIEW_REQUIRED` ทั้งสองฝั่ง · ตามที่ Bo กำหนดว่า
   ก่อน scoring จริงต้องแยกกองนี้รายงานต่างหาก หรือเพิ่มความสัมพันธ์ split/merge อย่างชัดเจน —
   **ยังไม่ทำในรอบนี้เพราะอยู่นอกขอบเขตที่ Bo bound ไว้**


---

## 9. Hardening Pass 5 (ตอบ `BO REVIEW COMPLETE — PRE-FREEZE CORRECTIONS PASS 4` `5606392284`)

> forward-only — Pass 1–4 ข้างบนไม่ถูกแก้

### 9.1 สิ่งที่ Bo ตีกลับ และสิ่งที่ทำ

| รหัส | คำวินิจฉัยของ Bo | สิ่งที่แก้ใน Pass 5 |
|---|---|---|
| **P4-1** | รายงานหลักเปิดผลเครื่องได้ก่อนผนึก และหน้าทำเฉลยมีลิงก์ไปหน้านั้น | ทุก route ที่ประกอบผลเครื่องเรียก `detector_output_allowed()` **ก่อน** ประกอบ · หน้าล็อกใหม่ `_locked()` ไม่เรียก `run_view` · เอาลิงก์รายงานออกจากขั้นเฉลยและหน้าล็อก · ด่าน AST บังคับลำดับ "ตรวจก่อนประกอบ" ทุก handler |
| **P4-1 (พบเพิ่ม)** | — | `/indicators/runs` แสดง `n_old/n_new/n_pairs` ก่อนผนึก → ซ่อนจนกว่าตรวจผ่าน · `/evidence/{doc}?obs=` แสดงข้อความ/กรอบที่เครื่องสกัด → ล็อก · `decide` POST เดิมประกอบคู่ก่อนแล้วหน้า error แสดงคู่ได้ → ตรวจก่อน |
| **P4-2** | ไฟล์ส่งออกเดิมยังดาวน์โหลดได้หลังผนึกไม่ตรง | `ind_export_manifests` ผูกทุกไฟล์กับรอบ + digest สามชั้น + sha256 ของไฟล์ · route ใหม่ `/indicators/runs/{run}/exports/{name}` ตรวจผนึก **ใหม่ทุกครั้ง** ก่อนส่ง · route เดิมคืน **410** เสมอ · ไฟล์ที่ไม่มีบันทึกผูกถูกปฏิเสธ · **ไม่ลบไฟล์เดิม** |
| **P4-3** | ผนึกเครื่องครอบเฉพาะคู่ ไม่ครอบข้อสังเกตที่สกัดและค่าตั้ง | `detector-snapshot-0.2.0` ผูก คู่ + **ข้อสังเกตทุกตัว** + metadata 14 ฟิลด์ (เวอร์ชัน extractor/normalize/mapping/backend · rules · แฮชเอกสาร · จำนวนหน้า · page inventory · n_old/n_new/n_pairs) · เก็บ digest แยกสามส่วนเพื่อบอกได้ว่าส่วนไหนไม่ตรง · ผนึกพิธีการเก่า ⇒ `DETECTOR_SNAPSHOT_PROTOCOL_OUTDATED` |
| **P4-4** | occurrence ไม่ถูกใช้ตามที่ประกาศ · กรอกเลขหน้าเกินได้ | `detector_occurrences()` นับครั้งที่ปรากฏของเครื่องจาก `(line_index, observation_id)` ในฟังก์ชันเอง · จับคู่ด้วย **ห้าองค์ประกอบตรงตัว** · ปฏิเสธรายการที่ชี้ตำแหน่งเดียวกันซ้ำ · ตรวจเลขหน้าเทียบ `ind_runs.old/new_page_count` (จากทะเบียนเอกสาร) · ไม่ทราบจำนวนหน้า ⇒ ปฏิเสธ |

### 9.2 นิยามที่เปลี่ยน — **ครั้งที่ปรากฏ (occurrence)**

ตั้งแต่ `source-inventory-0.2.0` = **ข้อความเดียวกัน (หลังทำรูปมาตรฐาน) ปรากฏเป็นครั้งที่เท่าไรในหน้านั้น
นับจากบนลงล่าง** · ข้อความที่มีครั้งเดียวในหน้า = 1 เสมอ · ฝั่งเครื่องใช้นิยามเดียวกัน
(เดิมเอกสารของ `manual_anchor` ใช้ความหมาย "รายการที่เท่าไรของหน้า" ซึ่งขัดกับกติกาเทียบ)

### 9.3 schema v5 (migration แบบเพิ่ม — ไม่แตะข้อมูลเดิม)

`ind_runs.old_page_count` / `new_page_count` · `ind_detector_snapshots.snapshot_protocol` /
`observation_count` / `mappings_digest` / `observations_digest` / `metadata_digest` ·
ตารางใหม่ `ind_export_manifests` (append-only ด้วย trigger ทั้งแก้และลบ)
🔴 ผนึกของรอบที่ทำใน Pass 3–4 **จะไม่ผ่านการตรวจอีก** (`DETECTOR_SNAPSHOT_PROTOCOL_OUTDATED`) — เป็นพฤติกรรมที่ตั้งใจ

### 9.4 เทสต์ของรอบนี้

| ไฟล์ | สิ่งที่พิสูจน์ |
|---|---|
| `tests/test_indicator_blind_boundary.py` *(ใหม่ · 24)* | รายงาน · ขั้นตัดสิน · เทียบข้างกัน · หน้าข้อสังเกต · decide · package **ล็อกทั้งสี่สภาวะ** (0-of-N · ตรึงจักรวาลอย่างเดียว · ผนึกเครื่องอย่างเดียว · ผนึกไม่ตรง) · หน้ารายการรอบซ่อนจำนวน · ขั้นเฉลยไม่มีลิงก์ไปผลเครื่อง · สภาวะควบคุมที่ผ่านครบเปิดได้ทุก URL · ไฟล์ส่งออกถูกปฏิเสธหลัง tamper / ข้ามรอบ / เนื้อไฟล์เปลี่ยน / ไฟล์เก่าไม่มีบันทึก · ไฟล์เดิมไม่ถูกลบ |
| `tests/test_indicator_seal_verification.py` *(+12)* | ข้อสังเกตถูกแทรก / ลบ / แก้ข้อความ / แก้ธงเรขาคณิต · metadata หกฟิลด์ถูกแก้ · ผนึกพิธีการเก่า ⇒ ล็อกกลับ และ `detector_coverage` ถูกปฏิเสธ |
| `tests/test_indicator_key_universe.py` *(+9)* | regression "คนครั้งที่ 2 · เครื่องครั้งที่ 1 ⇒ `NO_MATCH`" · ลำดับเครื่องไม่ขึ้นกับลำดับข้อมูลเข้า · miss นับถูกในรอบจริง · หน้า 0 / 1 / สุดท้าย / สุดท้าย+1 · ไม่ทราบจำนวนหน้า · ตำแหน่งซ้ำ |
| `tests/test_architecture_separation.py` *(+1)* | handler ที่เรียก `run_view`/`pair_view` ต้องเรียก `detector_output_allowed` ก่อน (AST) |

**พิสูจน์ว่าเทสต์จับได้จริง** — ทำลายโค้ดโดยเจตนาชั่วคราวแล้วรัน: ให้ `detector_output_allowed` คืน `True` เสมอ
⇒ 10 เทสต์ของ P4-1 ล้ม · ตัดข้อสังเกตออกจาก digest ⇒ 4 เทสต์ของ P4-3 ล้ม · กลับไปจับคู่ด้วย 4 องค์ประกอบ
⇒ 3 เทสต์ของ P4-4 ล้ม · คืนโค้ดแล้วตรวจว่าไม่มีร่องรอยเหลือ

### 9.5 ผลการรัน Pass 5 (developer-machine reported result · **ไม่มี CI**)

```
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
  started  2026-09-10T07:41:13Z
  finished 2026-09-10T07:44:07Z   (173.00 s)
  result   1099 passed · 0 failed · 0 skipped
scripts\test_report.py
  unit / synthetic 888 · private real-data integration 211 · SKIPPED(PRIVATE DATASET NOT AVAILABLE) 0
```

### 9.6 ข้อจำกัดที่พบระหว่าง Pass 5

1. **ผนึกของรอบเก่าใช้ต่อไม่ได้** — ต้องเปิดรอบใหม่ทั้งหมด (ตั้งใจ · ห้ามซ่อมทับ)
2. **หน้าเอกสาร (ไม่ชี้ข้อสังเกต) ยังเปิดได้ในขั้นเฉลย** ตามที่ Bo อนุญาต — ภาพหน้ากระดาษรับพารามิเตอร์กรอบเน้น
   `hl=` จาก URL ได้ แต่ route นั้น **ไม่อ่านผลเครื่อง** (วาดเฉพาะกรอบที่ผู้เรียกส่งมา) จึงไม่ใช่ทางรั่ว
3. **route ดาวน์โหลดเดิมคืน 410 ทุกกรณี** รวมถึงไฟล์ที่สร้างก่อน Pass 5 ซึ่งไม่มีบันทึกผูก —
   ไฟล์ยังอยู่บนดิสก์ แต่ดาวน์โหลดผ่านแอปไม่ได้อีก · ถ้าต้องการไฟล์เหล่านั้นต้องสร้างชุดใหม่จากรอบที่ผ่านการตรวจ
4. **หน้ารายการรอบคำนวณการตรวจผนึกของทุกรอบทุกครั้งที่เปิด** — ถูกต้องแต่ช้าลงเมื่อมีรอบจำนวนมาก
5. ข้อจำกัดเดิมยังอยู่: ระบบบังคับได้เฉพาะลำดับไม่ใช่ตัวบุคคล · ต้นทุนแรงงานของทะเบียนอิสระ ·
   หนึ่งต่อหลายยังไม่มีความสัมพันธ์ split/merge · `detector_coverage` ไม่ใช่คะแนน


---

## 10. Hardening Pass 6 (ตอบ `BO REVIEW COMPLETE — PRE-FREEZE HARDENING PASS 5` `5615776981`)

> forward-only — Pass 1–5 ข้างบนไม่ถูกแก้ · Bo รับ P4-2 และ P4-4 แล้วในรอบก่อน

### 10.1 สิ่งที่ Bo ตีกลับ และสิ่งที่ทำ

| รหัส | คำวินิจฉัยของ Bo | สิ่งที่แก้ใน Pass 6 |
|---|---|---|
| **P5-1** | หน้าจัดทำเฉลยแสดง `pair_count` ของเครื่อง · `key_universe_view()` ส่งวัตถุผนึกเครื่องทั้งก้อนเข้าหน้า · เทสต์ขอบเขตตรวจแค่ลิงก์ ไม่ตรวจตัวเลข | `KeyUniverseView` เหลือเพียง `detector_sealed: bool` · ผลตรวจผนึกผ่าน `BlindVerification` — ชั้นของคนแสดงผล/เหตุผลได้ ชั้นของเครื่องบอกได้แค่ **ผนึกแล้ว/ยังไม่ผนึก** · ใช้ view เดียวกันกับหน้าล็อก · เหตุผลเฉพาะของเครื่องไปที่ log ของเครื่องเท่านั้น |
| **P5-1 (พบเพิ่ม)** | — | หน้า `/audit` แสดง `n_old/n_new/n_pairs` · **`by_status` (การกระจายสถานะที่เครื่องเสนอ)** · `pair_count` · `observation_count` · แฮชผนึกเครื่อง ⇒ ปิดบังเฉพาะตอนแสดงสำหรับรอบที่ยังไม่ตรวจผ่าน · **audit chain ไม่ถูกแตะ** · หน้าล็อกเดิมแสดงเหตุผลเฉพาะของเครื่อง ⇒ opaque |
| **P5-2** | digest ของคู่ผูกเพียงหกฟิลด์ ขาด `human_required` · `differences_json` · `alternatives_json` · *"Avoid another partial field list."* | **แก้ที่ต้นเหตุ** — เลิกใช้รายการฟิลด์ที่เขียนเอง · `detector_projection_columns()` อ่านรายชื่อคอลัมน์จาก **schema จริง** ของ `ind_mappings` · `ind_observations` · `ind_runs` · `evd_documents` (สองฉบับที่รอบอ้าง) · ข้อยกเว้นเดียวที่ประกาศพร้อมเหตุผล = `evd_documents.local_path_private` · คอลัมน์ที่เพิ่มในอนาคตถูกครอบอัตโนมัติ (มีเทสต์) |
| **พิธีการ** | ขึ้นพิธีการ · 0.2.0 ต้องล็อก | `detector-snapshot-0.3.0` · ผนึก 0.2.0 ⇒ `DETECTOR_SNAPSHOT_PROTOCOL_OUTDATED` · ไม่ซ่อม/ไม่ตีความใหม่ |

### 10.2 projection มาตรฐาน `detector-snapshot-0.3.0`

`canonical_rows_digest(table, columns, rows)` — คอลัมน์เรียงตามชื่อ · แถวเรียงตามข้อความที่ serialize ·
แยก `NULL` ออกจากสตริงว่าง · ทศนิยมใช้ `repr` · ค่ายาวผูกด้วยแฮช (ไม่ให้ข้อความของเอกสารอยู่ในบรรทัดดิบ) ·
**รายชื่อคอลัมน์อยู่ในหัวของ digest** ⇒ เพิ่ม/ลบ/เปลี่ยนชื่อคอลัมน์ทำให้ผนึกไม่ตรง

| ส่วน | ตาราง | จำนวนคอลัมน์ ณ schema v5 |
|---|---|---|
| `mappings` | `ind_mappings` | 10 |
| `observations` | `ind_observations` | 28 |
| `metadata` | `ind_runs` | 21 |
| `documents` | `evd_documents` (สองแถวของรอบ) | 17 (ยกเว้น `local_path_private`) |

### 10.3 เทสต์ของรอบนี้

| ไฟล์ | สิ่งที่พิสูจน์ |
|---|---|
| `tests/test_indicator_detector_blindness.py` *(ใหม่ · 8)* | เติมแถวหลอกก่อนผนึกจนจำนวนคู่ = **2917** และข้อสังเกต = **1373** แล้วพิสูจน์ว่าตัวเลขทั้งสองและแฮชทุกส่วน (เต็ม · 16 ตัว · 12 ตัว) **ไม่ปรากฏ** ในหน้าจัดทำเฉลย · หน้าล็อก · หน้ารายการรอบ · หน้า audit · หน้าเอกสาร ขณะที่ทะเบียนที่คนกรอกและหน้าเอกสารยังเปิดได้ · view model ไม่มีวัตถุผนึกเครื่อง · audit chain ยังตรวจผ่านและข้อมูลดิบยังครบ · **กรณีควบคุม**: หลังตรวจผ่านครบ รายละเอียดใน audit กลับมาแสดง |
| `tests/test_indicator_detector_projection.py` *(ใหม่ · 20)* | mutation **15 กรณีใน 5 กลุ่มฟิลด์** (คู่ 3 · พิกัด/ขนาดหน้า/ตำแหน่ง 3 · ความหมาย 4 · ข้อมูลกำกับรอบ 2 · บริบทเอกสาร 3) ผ่าน route จริง — ทุกกรณีปิด **รายงาน · coverage · package · export** · กรณีควบคุมเปิดครบ · projection = ทุกคอลัมน์ลบข้อยกเว้นที่ประกาศ · คอลัมน์ในอนาคตถูกครอบอัตโนมัติ · ผนึก 0.2.0 ล็อกและผนึกซ้ำไม่ได้ · digest แยก NULL/สตริงว่าง/ชนิดตัวเลข และไม่ขึ้นกับลำดับ |
| `tests/test_indicator_blind_boundary.py` | เทสต์เดิมที่ **บังคับ** ให้หน้าล็อกแสดงเหตุผลเฉพาะของเครื่อง ถูกเปลี่ยนเป็นบังคับว่า **ต้องไม่แสดง** |
| `tests/test_t1b_review_queue.py` *(addendum `5628401191`)* | **นอก lane ตัวชี้วัด — แจ้งก่อนแก้** · เทสต์เดิมนับ audit ด้วย `len(audit.entries(limit=1000))` ⇒ เมื่อฐานข้อมูลของชุดทดสอบเกิน 1,000 รายการ ผลต่างติดเพดานเป็น 0 · เปลี่ยนเป็นเทียบ `seq` ล่าสุด (ไม่ติดเพดาน) · สิ่งที่ยืนยันไม่เปลี่ยน · ไม่แตะโค้ด T1B |

**พิสูจน์ว่าเทสต์จับได้จริง** — ทำลายโค้ดโดยเจตนาชั่วคราว: กลับไปใช้รายการฟิลด์แบบ 0.2.0 · ให้หน้าเฉลยแสดงจำนวนคู่ ·
ปิดการปิดบังใน audit ⇒ **17 เทสต์ล้ม** ตรงกลุ่มที่ออกแบบไว้ (กรณี `run.*` ยังผ่านเพราะการทำลายคงคอลัมน์ `ind_runs` ไว้ครบ — สอดคล้อง) · คืนโค้ดแล้วตรวจว่าไม่เหลือร่องรอย

### 10.4 ผลการรัน Pass 6 (developer-machine reported result · **ไม่มี CI**)

```
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
  started  2026-09-11T02:11:31Z
  finished 2026-09-11T02:14:39Z   (186.19 s)
  result   1127 passed · 0 failed · 0 skipped
scripts\test_report.py
  unit / synthetic 916 · private real-data integration 211 · SKIPPED(PRIVATE DATASET NOT AVAILABLE) 0
```

### 10.5 ข้อจำกัดที่พบระหว่าง Pass 6

1. **หน้าล็อกยังบอกได้หนึ่งบิต** — เมื่อผนึกครบสามชั้นแต่ตรวจไม่ผ่าน จะแสดงว่า "ผนึกครบแล้วแต่การตรวจไม่ผ่าน ต้องเปิดรอบใหม่"
   ถ้าชั้นของคนผ่านทั้งคู่ ผู้อ่านอนุมานได้ว่าชั้นของเครื่องเปลี่ยนหลังผนึก · ไม่บอกว่า *อะไร* เปลี่ยน ·
   ตั้งใจเก็บบิตนี้ไว้เพราะกติกา "ห้ามซ่อมทับ ต้องเปิดรอบใหม่" ต้องให้ผู้ใช้รู้ว่าต้องเปิดรอบใหม่ — **ขอ Bo ยืนยัน**
2. **log ของเครื่อง** (`app.log`) ยังบันทึกจำนวนข้อสังเกต/คู่ตอนรัน pipeline และเหตุผลเฉพาะของผนึกเครื่องที่ตรวจไม่ผ่าน —
   ไม่ใช่หน้าจอ แต่ผู้ที่เข้าถึงไฟล์ในเครื่องได้อ่านได้ · สอดคล้องกับข้อจำกัดเดิมว่าระบบบังคับได้เฉพาะลำดับ ไม่ใช่ตัวบุคคล
3. **การเปลี่ยน schema ในอนาคต** (เช่น migration ที่เพิ่มคอลัมน์) ทำให้ผนึกของทุกรอบที่มีอยู่ตรวจไม่ผ่านโดยอัตโนมัติ —
   ถูกต้องตามหลักแต่ต้องวางแผน migration ให้เกิด **ก่อน** เปิดรอบประเมินจริง
4. **ผนึกของทุกรอบก่อน Pass 6 ใช้ต่อไม่ได้** (`DETECTOR_SNAPSHOT_PROTOCOL_OUTDATED`) — ตั้งใจ
5. ข้อจำกัดเดิมยังอยู่: ต้นทุนแรงงานของทะเบียนอิสระ · หนึ่งต่อหลายยังไม่มี split/merge · `detector_coverage` ไม่ใช่คะแนน ·
   ยังไม่มีบัญชีผู้ใช้
