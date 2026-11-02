# DEPENDENCY LICENSE INVENTORY + pip-audit — FREEZE CANDIDATE (indicator/evidence)

> สร้างอัตโนมัติจาก `importlib.metadata` ของ `.venv` โครงการ · 2026-09-09T07:30:31+00:00 · Python 3.12.9 · Windows 10.0.26200
> 🔴 **ไม่ใช่ legal clearance** (Bo `5597645315` ข้อ B) — เป็นบัญชีแพ็กเกจ/เวอร์ชัน/สัญญาอนุญาตตาม metadata ที่ผู้เผยแพร่ระบุ · การตีความและข้อกำหนดที่เหลือต้องมีคนตรวจ
> · ชุดปริยาย = `requirements.lock.txt` (ไม่รวม PyMuPDF) · extra วิจัย = `requirements-research-pymupdf.txt`

## 1. บัญชีแพ็กเกจ (ทุกตัวที่ติดตั้งใน .venv รวม transitive)

| แพ็กเกจ | เวอร์ชัน | สัญญาอนุญาต (ตาม metadata) | ชุด |
|---|---|---|---|
| annotated-doc | 0.0.5 | MIT | ชุดปริยาย |
| annotated-types | 0.8.0 | MIT | ชุดปริยาย |
| anyio | 4.14.2 | MIT | ชุดปริยาย |
| certifi | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) | ชุดปริยาย |
| cffi | 2.1.1 | MIT-0 | ชุดปริยาย |
| charset-normalizer | 3.5.1 | MIT | ชุดปริยาย |
| click | 8.4.2 | BSD-3-Clause | ชุดปริยาย |
| colorama | 0.4.6 | BSD License | ชุดปริยาย |
| cryptography | 50.0.1 | Apache-2.0 OR BSD-3-Clause | ชุดปริยาย |
| et_xmlfile | 2.0.0 | MIT License | ชุดปริยาย |
| fastapi | 0.141.1 | MIT | ชุดปริยาย |
| h11 | 0.16.0 | MIT License | ชุดปริยาย |
| httpcore | 1.0.9 | BSD-3-Clause | ชุดปริยาย |
| httptools | 0.8.0 | MIT | ชุดปริยาย |
| httpx | 0.28.1 | BSD License | ชุดปริยาย |
| idna | 3.19 | BSD-3-Clause | ชุดปริยาย |
| iniconfig | 2.3.0 | MIT | ชุดปริยาย |
| Jinja2 | 3.1.6 | BSD License | ชุดปริยาย |
| MarkupSafe | 3.0.3 | BSD-3-Clause | ชุดปริยาย |
| openpyxl | 3.1.5 | MIT License | ชุดปริยาย |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | ชุดปริยาย |
| pdfminer.six | 20251230 | MIT | ชุดปริยาย |
| pdfplumber | 0.11.9 | MIT License | ชุดปริยาย |
| pillow | 12.3.0 | MIT-CMU | ชุดปริยาย |
| pip | 26.2.1 | MIT | ชุดปริยาย |
| pluggy | 1.6.0 | MIT License | ชุดปริยาย |
| pycparser | 3.0 | BSD-3-Clause | ชุดปริยาย |
| pydantic | 2.13.4 | MIT | ชุดปริยาย |
| pydantic_core | 2.46.4 | MIT | ชุดปริยาย |
| Pygments | 2.21.0 | BSD-2-Clause | ชุดปริยาย |
| PyMuPDF | 1.27.2.3 | Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License | extra วิจัย (ไม่ใช่ปริยาย) |
| pypdfium2 | 5.8.0 | BSD-3-Clause, Apache-2.0, dependency licenses | ชุดปริยาย |
| pytest | 9.1.1 | MIT | ชุดปริยาย |
| python-dotenv | 1.2.3 | BSD-3-Clause | ชุดปริยาย |
| python-multipart | 0.0.32 | Apache-2.0 | ชุดปริยาย |
| PyYAML | 6.0.3 | MIT License | ชุดปริยาย |
| starlette | 1.6.0 | BSD-3-Clause | ชุดปริยาย |
| typing-inspection | 0.4.4 | MIT | ชุดปริยาย |
| typing_extensions | 4.16.0 | PSF-2.0 | ชุดปริยาย |
| uvicorn | 0.52.4 | BSD-3-Clause | ชุดปริยาย |
| watchfiles | 1.2.0 | MIT License | ชุดปริยาย |
| websockets | 17.0.1 | BSD-3-Clause | ชุดปริยาย |

## 2. backend PDF ที่เกี่ยวข้องโดยตรง

| แพ็กเกจ | บทบาท | สัญญาอนุญาต | ข้อสังเกตที่ต้องมีคนตรวจ |
|---|---|---|---|
| pdfplumber | อ่านคำ + กรอบ (ปริยาย) | MIT | พึ่ง pdfminer.six (MIT) · Pillow (MIT-CMU) |
| pdfminer.six | ตัวแยกข้อความ | MIT | transitive: `cryptography` (Apache-2.0 OR BSD-3-Clause) · `charset-normalizer` (MIT) · `cffi` (MIT-0) · `pycparser` (BSD-3) |
| pypdfium2 | วาดหน้าเป็นภาพ (ปริยาย) | BSD-3-Clause / Apache-2.0 + dependency licenses ของ PDFium (BSD-3 · ดู notice ในแพ็กเกจ) | binary wheel ของ PDFium — ต้องเก็บ notice ตามที่แพ็กเกจกำหนดเมื่อแจกจ่าย |
| Pillow | วาดกรอบเน้นในหน่วยความจำ | MIT-CMU (HPND) | — |
| PyMuPDF | **extra วิจัยเท่านั้น** — เทสต์ equivalence | Dual: AGPL-3.0 / Artifex commercial | `LICENSE REVIEW REQUIRED` · ห้ามอยู่ในชุดปริยาย / merge / release / deploy |

## 3. pip-audit (รันกับ `requirements.lock.txt` · `--no-deps`)

* เครื่องมือ: pip-audit 2.10.1 ใน venv ชั่วคราวนอกโครงการ (`%LOCALAPPDATA%/Temp/av`) · เวลา 2026-09-09T07:30:31+00:00 · exit code 0
* ผลสะท้อน **ฐานข้อมูล advisory ณ วันรัน** เท่านั้น · ไม่ครอบโค้ดของโครงการเอง · ผลดิบเก็บไว้ที่ `docs/pip_audit_lock_2026-09-09.txt`

```
WARNING:pip_audit._cli:--no-deps is supported, but users are encouraged to fully hash their pinned dependencies
WARNING:pip_audit._cli:Consider using a tool like `pip-compile`: https://pip-tools.readthedocs.io/en/latest/#using-hashes
No known vulnerabilities found
```
