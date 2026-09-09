# ACCESS MATRIX — การประเมินทะเบียนตัวชี้วัด (Gate 0) · Gift / Giho / Generator / Scorer

**ป้ายกำกับ:** `PRODUCT EVIDENCE — POST-FREEZE` · **ฐานอำนาจ:** `GIFT DECISION — ANSWER-KEY CUSTODIAN + INDICATOR/PDF TRACEABILITY WORK ORDER` (Issue #1 · `5595281027` · 9 ก.ย. 2569) §1 และ §4 Gate 0
**ผู้บันทึก:** Giho (detector developer) · **สถานะ:** `PROPOSED — รอ Bo ตรวจ · รอกิ๊ฟยืนยันบทบาท`

> 🔴 เอกสารนี้ **ไม่ใช่** หลักฐานว่ามีเฉลยอยู่ที่ใด — เฉลยยังไม่ถูกสร้าง · สิ่งที่พิสูจน์ได้ตอนนี้คือ
> (ก) เครื่องมือของผู้พัฒนาปฏิเสธไฟล์ลักษณะเฉลยก่อนแตะเนื้อไฟล์ (บังคับด้วยโค้ด + เทสต์)
> (ข) ไม่มีไฟล์ลักษณะเฉลยในรากที่ผู้พัฒนาเข้าถึง ณ วันสแกน
> (ค) ลำดับเวลาที่ต้องรักษา (temporal separation) เขียนไว้ชัดและตรวจย้อนได้จาก audit/commit

---

## 1. บทบาทและสิทธิ์เข้าถึง

| artifact | Gift (custodian · verifier · adjudicator) | Giho (detector developer) | Generator / key builder (อิสระ) | Scorer |
|---|---|---|---|---|
| เอกสารต้นทางทั้งหมด (เก่า/ใหม่ · รวมภายใน) | ✅ อ่าน | ✅ อ่านเฉพาะที่กิ๊ฟวางให้ (public/synthetic ในรอบนี้) | ✅ อ่าน | ❌ ไม่จำเป็น |
| โค้ด detector (`redbook/indicators/**` · `redbook/evidence/**`) | อ่านได้ | ✅ เขียน — **จนถึงจุดตรึง** เท่านั้น | ❌ ห้ามแตะ | ❌ |
| detector commit/config/protocol ที่ตรึง | เห็น (hash) | ประกาศ + tag | เห็น (hash) | เห็น (hash) |
| ชุดสะอาด + กรณี defect/nuisance ที่ควบคุม | ✅ ตรวจ | ❌ **ห้ามเห็นก่อนรัน** | ✅ สร้าง | ❌ จนกว่าจะให้คะแนน |
| **เฉลยที่ปิดผนึก (sealed key)** | ✅ ตรวจ/แก้/ผนึก | ❌ **ห้ามตลอด** จนกว่ากิ๊ฟสั่ง unblind — และหลัง unblind การแก้ detector = เวอร์ชันใหม่ | ✅ สร้าง | ✅ อ่านหลัง output ถูกผนึก |
| ผลของ detector (output + hash ที่ผนึก) | เห็นหลังผนึก | ✅ สร้างจากการรัน แล้วผนึกทันที | ❌ | ✅ |
| หน้าตรวจเฉลย (`/indicators/runs/{id}/verify`) + ชุด XLSX | ✅ ใช้ตัดสิน — **ไม่มีคะแนนของเครื่อง** | สร้างซอฟต์แวร์ · ห้ามดูคำตัดสินของกิ๊ฟก่อนผนึกผล | ❌ | ❌ |
| คำตัดสินของกิ๊ฟ (`ind_decisions` · append-only) | ✅ เขียน | ❌ ห้ามดูก่อนผนึกผล detector | ❌ | ✅ หลังผนึก |
| ผลคะแนน / unblind | ✅ ปล่อยด้วยคำสั่งชัดแจ้ง | เห็นหลังกิ๊ฟปล่อย | เห็นหลังปล่อย | ✅ คำนวณ |

**ถ้าคนเดียวต้องรับหลายบทบาท** (กิ๊ฟรับทั้ง custodian/verifier/adjudicator) — ต้องบันทึกว่า **artifact ใดถูกเห็นเมื่อใด**
ตามที่กิ๊ฟสั่งไว้ · "เข้าถึงได้ทั้งหมด" = authorization ไม่ใช่การอนุญาตให้เปิดเฉลยแก่ผู้พัฒนาก่อนตรึง

---

## 2. ลำดับเวลาที่บังคับ (temporal separation)

```
T0  Giho ส่ง handoff Gate 0–4  ──►  Bo ตรวจ  ──►  (แก้ตามสั่ง)  ──►  🔒 FREEZE: tag detector commit + rules_hash + protocol
T1  Generator/Gift สร้างชุดสะอาด + defect + เฉลย (นอกรากที่ Giho เข้าถึง · นอก REDBOOK_DATA_DIR / DATA_ROOT / repo)
T2  Gift ตรวจและผนึกเฉลย (hash)
T3  Giho รัน detector ที่ตรึง  ──►  ผนึก input/output hash + หลักฐาน 6 ชั้น (ห้ามดูเฉลย · ห้ามแก้โค้ด)
T4  Scorer เทียบ output ที่ผนึก กับเฉลยที่ผนึก  ──►  รายงานแยกรายสถานะ 8 สถานะ + 3 ชั้น
T5  Gift สั่ง unblind  ──►  การแก้ detector ใด ๆ หลังจากนี้ = เวอร์ชันประเมินถัดไป ไม่ทับผลเดิม
```

🔴 รอบนี้ (handoff Gate 0–4) อยู่ที่ **T0** เท่านั้น — ไม่มี T1–T5 เกิดขึ้น

---

## 3. สิ่งที่บังคับด้วยโค้ดแล้ว (repo `redbook-verify` · branch `t1b/fy2570-mvp`)

| กลไก | ที่ | หลักฐาน |
|---|---|---|
| ด่านกันเฉลย — ปฏิเสธโฟลเดอร์ `SEALED_KEY/ answer_key/ gold_key/ …` และชื่อไฟล์มีโทเคน `ANSWER_KEY / SEALED_KEY / GOLD_KEY` **ก่อนแตะเนื้อไฟล์** | `redbook/sealed_key.py` | `tests/test_sealed_key_guard.py` — ดักทั้ง `builtins.open` และ `fitz.open` พร้อมเทสต์ที่พิสูจน์ว่าตัวดักทำงานจริง |
| ต่อด่านเข้าทุกทางเข้า: ทะเบียนเอกสาร · backend PDF · `services.t1b.read_workbook` | `evidence/documents.py` · `evidence/pdftext.py` · `services/t1b.py` | เทสต์ decoy ใน 3 ทาง · `opened == []` |
| **ไม่มีสวิตช์** env/config ปิดด่าน | `sealed_key.py` | `test_guard_has_no_environment_switch` |
| หน้าตรวจเฉลย/ชุด XLSX **ไม่มีคะแนนของเครื่อง** | `services/evidence.py` (`mappings()` คืนคะแนน 0.0 โดยปริยาย · `public_basis()` ถอดตัวเลข) | `test_internal_score_is_not_exposed_by_default` · `test_side_by_side_compare_shows_both_pages_and_no_score` · `test_verification_package_has_no_scores_paths_or_unpublished_text` |
| คำตัดสินของกิ๊ฟ append-only + ผูก audit chain | `indicators/registry.py` (`ind_decisions` trigger) | `test_decision_flow_and_indicator_binding` |

---

## 4. หลักฐานว่า ณ วันสแกน ไม่มีเฉลยในรากที่ผู้พัฒนาเข้าถึง

`sealed_key.scan_roots()` · 9 ก.ย. 2569 · ราก 3 แห่ง (`<USER_HOME>/dev` = repo clones + data · `<ONEDRIVE>/Red Vertify Project` · `<ONEDRIVE>/IS`)

| รายการ | ค่า |
|---|---|
| รายการที่สแกน (ชื่อเท่านั้น ไม่เปิดเนื้อไฟล์) | 2,750 |
| ชื่อที่เข้าข่าย | 2 — `sealed_key.py` และ `test_sealed_key_guard.py` (โค้ดของด่านเอง) |
| ไฟล์ข้อมูลลักษณะเฉลย | **ไม่พบ** |
| ไฟล์ดิบ | `assets/sealed_key_scan_2026-09-09.json` |

⚠️ ถ้อยคำที่ถูกต้อง: *"ไม่พบชื่อที่เข้าข่ายตามกติกาของด่าน ณ วันสแกน"* — **ไม่ใช่** "พิสูจน์แล้วว่าไม่มีเฉลว" · เฉลยในรูปที่ไม่ตรงกติกาชื่อ (เช่น ตั้งชื่อธรรมดา) ด่านนี้มองไม่เห็น ⇒ **ตำแหน่งเฉลยจริงต้องอยู่นอกรากทั้งสามและนอก `REDBOOK_DATA_DIR`/`REDBOOK_DATA_ROOT`** ซึ่งเป็นคำตัดสินของกิ๊ฟ

---

## 5. สิ่งที่ยังพิสูจน์ไม่ได้ / ต้องให้กิ๊ฟตัดสิน

1. **ใครเป็น generator/key builder ที่แยกสิทธิ์จริง** — Giho ทำไม่ได้ (เป็นผู้พัฒนา detector) · Bo/กิ๊ฟ/อาจารย์ ต้องกำหนด
2. **ตำแหน่งเก็บเฉลย** — ต้องอยู่นอกรากที่ Giho เข้าถึงและนอกโฟลเดอร์ที่แอปอ่าน
3. **ลำดับเวลา** — ยืนยันว่า FREEZE (T0→tag) เกิดหลัง Bo รับ handoff นี้ และก่อน T1
4. **ผู้ให้คะแนน** — เป็นกิ๊ฟเอง หรือแยกคน · ถ้าเป็นกิ๊ฟต้องบันทึกว่าเห็น output ที่ผนึกเมื่อใด
5. การเปิดเผยชื่อผู้ตรวจในหน้าตัดสิน (`reviewer`) — ตอนนี้เป็นข้อความอิสระ ไม่มีบัญชีผู้ใช้ (SYS-D-20 ยังไม่ implement)
