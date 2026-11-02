# reviewpack — provenance ของเครื่องมือ Human Review

> **สถานะ:** provenance maintenance · คำสั่งกิ๊ฟ 7 ก.ย. 2569 (ข้อ A)
> สคริปต์ในโฟลเดอร์นี้ **ผลิต** เครื่องมือวิจัยที่ freeze แล้ว จึงต้องเก็บไว้ให้สร้างซ้ำได้
> แต่ **ไฟล์ที่ผลิตออกมาและข้อมูลจาก OneDrive ห้ามเข้า git** โดยเด็ดขาด

## เส้นทางและตัวแปรสภาพแวดล้อม

| สิ่งที่ต้องการ | มาจากไหน |
|---|---|
| ทรัพยากรภายใน repository (`.data/…`) | คิดจาก `__file__` ใน `_paths.py` |
| ราก OneDrive / ข้อมูลส่วนตัว | ตัวแปร `REDBOOK_PRIVATE_DATA_ROOT` |

ถ้าไม่ตั้ง `REDBOOK_PRIVATE_DATA_ROOT` สคริปต์ **หยุดพร้อมข้อความ**
`PRIVATE DATASET NOT AVAILABLE` และรหัสออก `2` — **ไม่ข้ามเงียบ ๆ**

```
$env:REDBOOK_PRIVATE_DATA_ROOT = "<โฟลเดอร์ Red Vertify Project บน OneDrive>"
```

## สคริปต์แต่ละตัวผลิตอะไร

| สคริปต์ | ผลิต | baseline ที่สัมพันธ์ | บทบาท |
|---|---|---|---|
| `build_review_v3.py` | — (โมดูล) | v1.3.0 presentation layer (คำสั่ง 28 ส.ค.) | **โมดูลแม่** — อีกสามสคริปต์ import จากนี่ |
| `_v3_main.py` | `Round1/HUMAN_CHECK_SAMPLE_primary_R1_WORKING_v1.3.1.xlsx` + `MIGRATION_REPORT_v1.3.1.md` | **v1.3.1 = FROZEN INSTRUMENT BASELINE FOR ROUND 1** | ย้ายคำตอบจาก working copy รุ่นก่อนโดยไม่แตะ finding/ยอดเงิน/แฮชต้นทาง |
| `_v4_grouped.py` | — (โมดูล) | v1.4.0 | จัดกลุ่ม หน่วยงาน → แผนงาน → รายการ พร้อมผลรวมรายชั้น · `read_v131()` |
| `_v4_main.py` | `Round1/…_v1.4.0.xlsx` + `MIGRATION_REPORT_v1.4.0.md` | v1.4.0 (ขึ้นรุ่นจาก v1.3.1 ซึ่งห้ามแก้) | ย้ายคำตอบ 21/21 · acceptance tests 18 ข้อ |
| `_r2_build.py` | `Round2/HUMAN_CHECK_SAMPLE_primary_R2_WORKING_v1.3.1.xlsx` | v1.3.1 (ใช้โครงสร้าง/ความหมายเดิม **ไม่ใช้ v1.4.0**) | แบบฟอร์มรอบที่ 2 · seed `20260901` · ล้าง response fields ทุกช่อง · ไม่ import คำตอบรอบ 1 |
| `check_provenance.py` | `PROVENANCE_MANIFEST.json` (git) | ทั้งสี่ artifact ข้างบน | ตรวจว่า artifact ยังเป็นไฟล์เดิมทุกไบต์ |

สคริปต์ที่ track อยู่ก่อน (`build_review_v2.py` · `review_layout_v2.py` ·
`review_writer_v2.py` · `make_review_package.py` · `migrate_answers.py` ·
`gen_reconciliation_md.py`) เป็นสาย **v2 / reviewpack-1.1.0** ซึ่งเป็นคนละรุ่นกับข้างบน

## การตรวจสร้างซ้ำ (deterministic reproduction check)

`PROVENANCE_MANIFEST.json` เก็บ **ลายนิ้วมือ** ของ artifact ทั้งสี่ — SHA-256 · ขนาด ·
ชื่อชีต · จำนวนแถวต่อชีต · **ไม่มีเนื้อในเอกสาร ไม่มียอดเงิน ไม่มีคำตอบของผู้ตรวจ**

```
python reviewpack/check_provenance.py
```

| รหัสออก | ความหมาย |
|---|---|
| `0` | artifact ทั้งสี่ตรงกับที่ freeze ไว้ทุกไบต์ |
| `1` | มีไฟล์ไม่ตรง — ห้ามใช้ต่อจนกว่าจะหาสาเหตุ |
| `2` | `PRIVATE DATASET NOT AVAILABLE` — **ไม่ใช่การผ่าน** ต้องรายงานแยก |

นอกจากนี้ `_v4_main.py` ยังเทียบ **ผลรวมรายหน่วยงานด้วยแฮช** (`AGGREGATE_HASH_V131`)
แทนการฝังยอดเงินจริงไว้ในซอร์ส — ค่าจริงยังตรวจซ้ำได้ทุกครั้งที่รันกับไฟล์ต้นทาง

## สิ่งที่ตรวจแล้วว่า **ไม่มี** ในซอร์ส

* เส้นทางสัมบูรณ์หรือชื่อผู้ใช้ — มีเทสต์ `tests/test_reviewpack_provenance.py` กันไว้
* ยอดเงินจริง — ย้ายไปเทียบด้วยแฮช (`_v4_main.py`)
* ชื่อผู้เข้าร่วม — ไม่เคยมี (แบบฟอร์มใช้ pseudonym อยู่แล้ว)
* ไฟล์ output — อยู่ใน `.data/` (ignored) และ OneDrive เท่านั้น

## หมายเหตุเรื่องการเปิดเผย

ยอดเงินที่เคยฝังอยู่ใน `_v4_main.py` เป็นตัวเลขจาก **ร่าง พ.ร.บ. ↔ พ.ร.บ. งบประมาณ 2569**
ซึ่งเป็นเอกสารที่เผยแพร่แล้วทั้งคู่ · ย้ายออกตามคำสั่งกิ๊ฟข้อ A.5 ไม่ใช่เพราะเป็นความลับ
แต่เพราะซอร์สไม่ควรเป็นที่เก็บข้อมูลผลลัพธ์ไม่ว่ากรณีใด
