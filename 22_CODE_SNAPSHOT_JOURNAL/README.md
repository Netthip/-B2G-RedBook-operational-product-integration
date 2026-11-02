# RedBook Verify

ระบบตรวจสอบความถูกต้องและความสอดคล้องของเอกสารงบประมาณ — ทำงานบนเครื่องผู้ใช้ (local-first)

รับไฟล์เอกสารจริงเข้ามาเปรียบเทียบ หาความแตกต่าง แสดงหลักฐานย้อนกลับได้ถึงตำแหน่งต้นทาง
และให้**มนุษย์เป็นผู้ตัดสิน**ว่าความแตกต่างนั้นเป็นการเปลี่ยนแปลงที่ถูกต้องหรือเป็นข้อผิดพลาด

> **สถานะปัจจุบัน: Phase 1 (Foundation) + กลไก Phase 2A พร้อมแล้ว**
> ใช้งานได้จริงแล้ว: สร้างงานตรวจ · อัปโหลดไฟล์สองฝั่ง · ตรวจ metadata (กฎ M01–M05) ·
> อ่านโครงสร้างไฟล์ Excel · บันทึกคำตัดสินของผู้ตรวจพร้อมเหตุผล · Audit Trail สายโซ่แฮช ·
> ตรวจซ้ำได้ด้วยแฮชผลตรวจ · เครื่องมือสำรวจไฟล์จริงแบบ read-only (`inventory_cli`)
> **ยังไม่เปิดใช้งาน:** การเปรียบเทียบเนื้อหาระดับเซลล์ Excel (Phase 2C — รอยืนยัน mapping)
> และการเปรียบเทียบ PDF/OCR (Phase 3)
>
> ระบบที่รันอยู่มีสถานะเป็น **สภาพแวดล้อมพัฒนาและทดสอบภายในเครื่อง
> (local development/test environment)** เท่านั้น — ดู [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)
> · สถานะ Phase 0–1 ที่ได้รับการรับรองถูกตรึงไว้ที่ git tag `phase-0-1-baseline`

## หลักการที่บังคับด้วยโค้ด ไม่ใช่แค่เอกสาร

| หลักการ | บังคับที่ไหน |
|---|---|
| ใช้เฉพาะไฟล์ที่ผู้ใช้อัปโหลดจริง ไม่มีข้อมูลตัวอย่างปนผลตรวจ | ไม่มี seed data ในโค้ดและฐานข้อมูล · ไฟล์ทดสอบอยู่ใน `tests/` เท่านั้น |
| ต่างกันไม่เท่ากับผิด | `MachineStatus` ไม่มีค่าที่แปลว่าผิด (ทดสอบใน `test_status_and_model.py`) |
| ทุกผลตรวจย้อนกลับไปดูหลักฐานได้ | ทุก finding มี `loc_a` / `loc_b` ตาม `SourceLocation` |
| เก็บ Audit Trail และเวอร์ชันกฎ | ตาราง `audit_log` มี trigger ห้าม UPDATE/DELETE + ตาราง `runs` เก็บเวอร์ชันครบ |
| local-first | ผูก 127.0.0.1 · CSP ปิดทรัพยากรภายนอก · ทดสอบห้าม import ไลบรารีเครือข่าย |
| แยกตรรกะฝ่ายสร้างไฟล์ออกจากฝ่ายตรวจไฟล์ | `test_architecture_separation.py` ห้ามเรียก `.save()` และห้าม import โมดูลฝั่งสร้าง |
| ไม่เดาค่าที่เอกสารไม่มี | `CanonicalItem.set_null()` บังคับให้ระบุเหตุผลทุกครั้ง |

## ติดตั้ง

> `<USER_HOME>` ในเอกสารชุดนี้แทนโฟลเดอร์บ้านของผู้ใช้บนเครื่องนั้น
> (บนวินโดวส์คือ `C:\Users\<ชื่อผู้ใช้>`) — เขียนแบบนี้เพื่อไม่ให้ชื่อผู้ใช้ติดขึ้น git

```
cd <USER_HOME>\dev\redbook-verify
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## เริ่มใช้งาน

```
.venv\Scripts\python.exe run_local.py
```

เปิดเบราว์เซอร์ที่ `http://127.0.0.1:8600`

## รันชุดทดสอบ

```
.venv\Scripts\python.exe -m pytest -q
```

## สำรวจไฟล์จริงก่อนกำหนด mapping (Phase 2A — read-only)

```
.venv\Scripts\python.exe -m redbook.inventory_cli "<ไฟล์หรือโฟลเดอร์เอกสาร>"
```

อ่านอย่างเดียว พิสูจน์ด้วย SHA-256 ก่อน/หลัง · ผลิต `FILE_INVENTORY.md`,
`WORKBOOK_STRUCTURE_REPORT.md`, `MAPPING_CANDIDATES.md`, `inventory.json`
ลงใน `.data\inventory\` (นอก git · CLI ปฏิเสธ outdir ที่อยู่ใน OneDrive)
ทุกค่าที่ตรวจพบเป็น candidate ต้องให้ผู้ใช้ยืนยันก่อนใช้ตรวจจริง

## ตำแหน่งข้อมูล

ค่าเริ่มต้น: `<USER_HOME>\dev\redbook-verify\.data\`

| โฟลเดอร์ | เก็บอะไร |
|---|---|
| `.data/uploads/` | ไฟล์ที่อัปโหลด (ตั้งชื่อใหม่ด้วย uuid + ตั้งสิทธิ์อ่านอย่างเดียว) |
| `.data/redbook.sqlite3` | งานตรวจ ผลตรวจ คำตัดสิน Audit Trail |
| `.data/logs/` | ล็อกของแอปและเหตุการณ์ด้านความปลอดภัย |
| `.data/tmp/` | ไฟล์ระหว่างอัปโหลด ถูกลบทุกครั้งที่แอปเริ่มทำงาน |

**โฟลเดอร์นี้ตั้งใจวางไว้นอก OneDrive** เพราะไฟล์ที่อัปโหลดเป็นเอกสารราชการจริง
การเก็บไว้ในโฟลเดอร์ที่ sync ขึ้นคลาวด์เท่ากับส่งข้อมูลออกนอกเครื่อง
ย้ายตำแหน่งได้ด้วย environment variable `REDBOOK_DATA_DIR`

## โครงสร้างโค้ด

```
redbook/
  config.py            ค่าตั้งทั้งหมด (path, ขนาดไฟล์, พอร์ต)
  app.py               FastAPI app + เส้นทางหน้าเว็บทั้งหมด
  core/
    canonical.py       Canonical Data Model + SourceLocation
    status.py          สถานะผลตรวจ 7 แบบ + สีสถานะ
    hashing.py         SHA-256
  storage/
    db.py              โครงสร้างฐานข้อมูล SQLite
    repository.py      คำสั่งเข้าถึงข้อมูล (parameter binding ทั้งหมด)
    files.py           คลังไฟล์อัปโหลด + การตรวจชนิดไฟล์จริง
    audit.py           Audit Trail สายโซ่แฮช + เหตุการณ์ความปลอดภัย
  readers/             ฝั่ง "อ่าน/ตรวจ" เท่านั้น ห้ามมีตรรกะสร้างไฟล์
    excel_reader.py    อ่าน Excel แบบ read-only
  rules/
    catalog.py         บัญชีกฎทั้งหมด + สถานะการพัฒนา
    finding.py         ตัวสร้างผลตรวจ + แฮชผลตรวจ (reproducibility)
    metadata_checks.py กฎ M01–M05
  web/security.py      security headers + CSRF
  templates/           หน้าเว็บ (Jinja2 autoescape)
  static/app.css       ธีมแดง-ขาว
tests/                 ชุดทดสอบ pytest
docs/                  รายงานแต่ละระยะ + สถาปัตยกรรม + ความปลอดภัย
```

## เอกสารประกอบ

- [รายงาน Phase 0 — สำรวจของเดิม](docs/PHASE0_DISCOVERY.md) *(ตรึงตาม baseline — ไม่แก้ย้อนหลัง)*
- [รายงาน Phase 1 — Foundation](docs/PHASE1_FOUNDATION.md) *(ตรึงตาม baseline — ไม่แก้ย้อนหลัง)*
- [แผนและขอบเขต Phase 2 (2A → 2B → 2C)](docs/PHASE2_PLAN.md)
- [คำถาม Q1–Q8 ฉบับเต็ม](docs/QUESTIONS_Q1_Q8.md)
- [สถานะสภาพแวดล้อม (local dev/test)](docs/ENVIRONMENT.md)
- [สถาปัตยกรรมและ Canonical Data Model](docs/ARCHITECTURE.md)
- [ความปลอดภัยและ dependency inventory](docs/SECURITY.md)
