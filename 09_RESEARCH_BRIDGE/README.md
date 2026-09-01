# 09_RESEARCH_BRIDGE — ชั้นประสานงาน Gift × Bo × Giho

**ประเภทเอกสาร:** `COORDINATION LAYER ONLY — NOT AN AUTHORITY`
**จัดทำ:** 1 กันยายน 2569 · **ผู้ร่าง:** Giho (Research Engineer + Evidence Builder)
**สถานะ:** `DRAFT — PENDING GIFT REVIEW` · ยังไม่มีคำตัดสินรับรอง

---

## 1. เอกสารนี้คืออะไร และไม่ใช่อะไร

| เป็น | ไม่เป็น |
|---|---|
| ที่นัดพบระหว่างสายวิจัยกับสายผลิตภัณฑ์ | แหล่งความจริงของข้อกล่าวอ้างใด ๆ |
| ตัวชี้ (pointer) ไปยัง authority เดิม | สำเนาของ authority |
| บันทึกคำถามที่ยังไม่ตัดสิน | ที่ตัดสินเอง |

> 🔴 **กฎเหล็กของโฟลเดอร์นี้**
> ห้ามสร้าง authority ชุดใหม่ ห้ามคัดลอกเนื้อหาของ `CLAIM_BOUNDARY` · `Evidence Index` ·
> `Decision Register` · frozen artefacts · raw results เข้ามาไว้ที่นี่
> ให้ใช้ **ชื่อ repo + path + commit/hash** ชี้กลับไปที่ต้นทางเสมอ
> ถ้าเนื้อหาที่นี่ขัดกับ authority ต้นทาง — **authority ต้นทางถูกเสมอ** และเอกสารที่นี่คือของที่ผิด

---

## 2. หลักการที่ทั้งสามฝ่ายยึดร่วมกัน

> **The research prototype validates a verification core; it is not the complete operational RedBook workflow.**

**ฉบับที่ตรวจสอบได้ (Giho เพิ่มจากหลักฐาน):**
verification core ที่พิสูจน์แล้วทำงานบนชั้นข้อมูล **T1A — Official Flat Data Table**
ส่วนงานปฏิบัติจริงที่ต้องการ (เอกสารคาดแดง / AO workbook) อยู่บนชั้น **T1B — Official AO/RedBook Workbook**
ซึ่ง **ยังไม่มีผลการทดลองที่ freeze** — ดู `RESEARCH_PRODUCT_BOUNDARY.md` หัวข้อ 3

---

## 3. แฟ้มในโฟลเดอร์นี้

| ไฟล์ | หน้าที่ | สถานะ |
|---|---|---|
| `README.md` | ไฟล์นี้ — กติกาและสารบัญ | ร่าง |
| `CURRENT_STATE.md` | สถานะที่พิสูจน์แล้ว ณ วันที่ระบุ พร้อม pointer | ร่าง |
| `RESEARCH_PRODUCT_BOUNDARY.md` | เส้นแบ่ง RESEARCH TRACK / PRODUCT TRACK | ร่าง |
| `OPERATIONAL_PRODUCT_VISION.md` | Mode A / Mode B ตาม requirement ของ Gift | ร่าง |
| `OPEN_QUESTIONS.md` | คำถามที่รอ Gift ตัดสิน + ข้อสังเกตที่ยังไม่ปิด | ร่าง |
| `AI_HANDOFF_LOG.md` | บันทึกการส่งต่องานระหว่าง Bo กับ Giho | ร่าง |

### ความสัมพันธ์กับ `docs/` (คำตัดสิน Gift · 1 ก.ย. 2569 · `OPEN_QUESTIONS.md` `Q-02`)

repo นี้เก็บเอกสาร **สองชุดคู่กัน** โดยตั้งใจ

| ชุด | บทบาท | ผู้ดูแล |
|---|---|---|
| `docs/` | ฉบับภาษาอังกฤษ อธิบายภาพรวมให้ผู้อ่านทั่วไป | Bo |
| `09_RESEARCH_BRIDGE/` | ฉบับผูกหลักฐาน — ทุกข้อความมี path / commit / hash | Giho |

> 🔴 **เมื่อสองชุดขัดกัน** ให้ยึด `09_RESEARCH_BRIDGE/` เฉพาะข้อเท็จจริงที่มี pointer
> ส่วนภาพผลิตภัณฑ์และการเรียบเรียงให้ยึด `docs/`
> ไม่ว่ากรณีใด **authority ตัวจริงอยู่ในสายวิจัย ไม่ใช่ repo นี้**

---

## 4. บทบาทและอำนาจตัดสิน

| ผู้เกี่ยวข้อง | บทบาท | ตัดสินอะไรได้ |
|---|---|---|
| **Gift** | Principal Investigator + Product Owner | research scope · methodology · objective · claim boundary · frozen evidence · operational requirement · decision ที่มีผลผูกพัน — **ผู้ตัดสินสุดท้าย** |
| **Bo** (ChatGPT) | Research Director + Product Architect | เสนอ · ตรวจความสอดคล้องบท 1–5 · ตรวจ objective → evidence → claim · ออกแบบ product vision — **ไม่ถือข้อเสนอของตนเป็นหลักฐาน** |
| **Giho** (Claude) | Research Engineer + Evidence Builder | ตรวจไฟล์จริง · รัน engine/tests · implementation · reproducibility · evidence · commit/provenance — **ห้ามตัดสิน research interpretation หรือ methodology ใหม่เอง** ให้เสนอเป็น question/option ก่อน |

---

## 5. หัวข้อที่ใช้สื่อสารระหว่าง Bo กับ Giho

ทุกข้อความที่ต้องอภิปรายร่วมกัน (GitHub issue หรือไฟล์ handoff) ต้องขึ้นหัวข้อด้วยป้ายใดป้ายหนึ่ง:

`ENGINEERING OBSERVATION` · `RESEARCH REVIEW` · `PRODUCT REQUIREMENT` ·
`EVIDENCE` · `RISK` · `PROPOSAL` · `DECISION REQUIRED FROM GIFT`

**ข้อบังคับ 2 ข้อ**

1. ทุก assertion ที่อ้างว่าเป็นผลจริง ต้องมี **path / commit / test / evidence pointer** เมื่อเหมาะสม
2. **ห้ามถือข้อความจาก AI อีก session เป็นข้อเท็จจริง** โดยไม่เปิด authority ที่เกี่ยวข้องตรวจก่อน

---

## 6. ก่อนเขียนข้อกล่าวอ้างใด ๆ

เปิดสามไฟล์นี้ในสายวิจัยก่อนเสมอ (ชี้ตำแหน่ง ไม่คัดลอกมาที่นี่):

- `redbook-verify-is` → `00_project_control/CLAIM_BOUNDARY.md`
- `redbook-verify-is` → `08_evidence_register/EVIDENCE_INDEX.md` (frozen · commit `617ceac`)
- `redbook-verify-is` → `08_evidence_register/EVIDENCE_INDEX_SUPPLEMENT_01_INSTRUMENT_DEFECTS.md`
