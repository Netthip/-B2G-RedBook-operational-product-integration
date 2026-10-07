# DATA CONTRACT — source-contract-0.1.0 (ใบ #27 → ใบ UI)

ไฟล์: `redbook/data/source_registry.json` (repo ระบบ) · อ่านจาก `contract.documents[]` และ `pairs[]`

UI **ไม่ต้อง scrape เว็บ** และไม่ต้องรู้กติกาจับคู่ เพราะค่าทุกค่าคำนวณไว้แล้ว

## `contract.documents[]` (หนึ่งรายการต่อเอกสาร)

| ฟิลด์ | ชนิด | หมายเหตุ |
|---|---|---|
| `id` | str | `bb-<รหัสหน้าทางการ>` คงที่ตราบที่สำนักงบประมาณไม่เปลี่ยนรหัสหน้า ใช้เป็น cache key ได้ |
| `year` | int | ปีงบประมาณ พ.ศ. |
| `stage` / `stage_label` | `DRAFT`\|`ACT` / ข้อความไทย | |
| `ministry` | list[str] | อ่านจากหัวเรื่องทางการ ว่างได้ (เช่น เอกสารระดับทั้งปี) |
| `agency` / `agency_basis` | null / str | ตอนนี้เป็น null ทุกเล่ม เพราะเล่มทางการแบ่งระดับกระทรวง/กลุ่ม `agency_basis` บอกเหตุผล |
| `book_title` / `book_label` | str | ชื่อเต็มทางการ / ชื่อสั้น เช่น "ฉบับที่ 3 เล่มที่ 4" |
| `doc_type` / `doc_type_label` | str | ดู PROTOCOL §2 |
| `thumbnail_source` | `{kind, url, rendered}` | `PDF_FIRST_PAGE` + ลิงก์ PDF ทางการ ทะเบียนไม่เก็บภาพ |
| `pdf` | `{status, url}` | PROTOCOL §1 |
| `excel` | `{status, granularity, coverage, verification_level, urls[]}` | `granularity` = `VOLUME`\|`MINISTRY` |
| `availability` | str | ภาพรวม PROTOCOL §1 |
| `source_status` | `{source_page_url, verified_date, pdf_verification_level}` | ใช้ตรวจย้อนกลับไปหน้าทางการ |
| `related_pair_ids` | list[str] | ชี้ไป `pairs[].pair_id` |
| `comparison_availability` | `{A_completeness, B_structure_book, B_structure_item, C_indicator, D_amount}` | ค่า: `SUPPORTED`\|`NOT_VERIFIED`\|`NOT_SUPPORTED`\|`NO_PAIR` |
| `observation_counts` | `{total, A?, B?}` | จำนวนข้อสังเกตที่ผูกกับเอกสารนี้ |

## `pairs[]`

`pair_id` · `kind` (`SAME_YEAR`\|`CROSS_YEAR`) · `key` · `status` (`MATCHED`\|`REVIEW_REQUIRED`\|`CANNOT_DETERMINE`) ·
`reasons[]` · `a`/`b` = `{stage, fiscal_year, ids[]}` · `evidence` · `comparison`

## กติกาการแสดงผลที่ตกลงกับใบ UI

1. คู่ที่**เชื่อมเป็นลิงก์ได้มีเฉพาะ `MATCHED`** ส่วน `REVIEW_REQUIRED`/`CANNOT_DETERMINE` ให้แสดงว่า "รอยืนยัน"
2. `NOT_LISTED`/`UNCHECKED`/ฟิลด์ว่าง ให้แสดงว่า "ยังไม่มีข้อมูล / ไม่อยู่ในส่วนที่ค้น" **ห้ามแสดงว่า "ไม่มี"**
3. `EXTERNAL_VIEWER_PAGE_OPENS_FILE_NOT_VERIFIED` ห้ามแสดงว่า "ตรวจไฟล์แล้ว"
4. ไม่อ่านค่าใด ๆ ที่ไม่อยู่ในสัญญานี้ เพราะฟิลด์อื่นใน JSON อาจเปลี่ยนโดยไม่ขึ้นรุ่นสัญญา

การเปลี่ยนชื่อหรือความหมายของฟิลด์ในตารางนี้ต้องขึ้น `contract_version`
