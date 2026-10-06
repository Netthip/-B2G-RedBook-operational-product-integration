# SECURITY VERIFICATION PROTOCOL — Web Security Verification Gate ของ RedBook Verify

**รุ่น:** `security-verification-protocol-0.1.0` · **ประกาศ:** 6 ตุลาคม 2569 · **ผู้ร่าง:** Giho · **ใบงาน:** #23
**สถานะ:** `PREDECLARED — PENDING BO REVIEW` · **ผู้ตัดสินสุดท้าย:** Gift
**มาตรฐานอ้างอิง:** OWASP ASVS **v5.0.0** (subset ที่ประกาศล่วงหน้า) · OWASP ZAP Baseline Scan (passive)

> 🔴 **ขอบเขตการอ้างที่ผูกพันทุกเอกสารในหมวดนี้**
>
> | อ้างได้ | ห้ามอ้าง |
> |---|---|
> | "ประเมินตาม **subset ที่ประกาศล่วงหน้า** จาก OWASP ASVS v5.0.0 จำนวน N ข้อ" | "ผ่าน OWASP ASVS" · "ได้ระดับ L1/L2/L3" |
> | "control ที่ประกาศ N · applicable M · PASS/FAIL/REVIEW/N/A = …" | "ปลอดภัย 100%" · "แฮกไม่ได้" · "ไม่มีช่องโหว่" |
> | "ไม่พบช่องโหว่ที่ประกาศไว้ในฐานข้อมูล **ณ วันที่รัน** สำหรับแพ็กเกจที่เครื่องมือตรวจได้ (x จาก y)" | "dependency ปลอดภัยทั้งหมด" |
> | "ZAP baseline (passive) พบ alert H/M/L/I = … บน target สังเคราะห์" | "ผ่าน ZAP" · penetration-test certification |
> | "ก่อนแก้ → หลังแก้ ของ finding F-xx คือ … (run A → run B)" | ผล **formative** เป็นผลประเมินสุดท้าย |
> | "leak_check ตรวจครบ A–H + Z1–Z3 · 0 hit" | "0 hit = ปลอดการเปิดเผย" |

---

## 1. คำถามวิจัยที่ด่านนี้ตอบ

> เว็บที่นำระบบตรวจเอกสารงบประมาณไปใช้ **มีมาตรการความปลอดภัยและความเป็นส่วนตัวพื้นฐานตามเกณฑ์ที่ประกาศไว้ล่วงหน้าหรือไม่
> และตรวจย้อนกลับได้ด้วยหลักฐานอะไร**

ด่านนี้ **แยกจาก** การวัดความสามารถของเครื่องยนต์ตรวจเอกสาร (T1A/T1B) โดยสิ้นเชิง —
ไม่รวมคะแนน ไม่ใช้ตัวหารร่วม ไม่ใช้ชุดข้อมูลร่วม (ใช้ข้อมูลสังเคราะห์เท่านั้น)

## 2. สิ่งที่ประกาศล่วงหน้า (predeclared) และตรึงด้วย git

| สิ่งที่ประกาศ | ไฟล์ | วิธีตรึง |
|---|---|---|
| ชุด control (51 ข้อ · 12 หมวด) + applicability + วิธีทดสอบ + ผลที่คาด + กติกาสถานะ | [`SECURITY_CONTROL_MATRIX.csv`](SECURITY_CONTROL_MATRIX.csv) | commit ใน repo นี้ · SHA-256 ของไฟล์ถูกเขียนลง `SECURITY_RUN_MANIFEST.json` ของทุกรอบ |
| กติกาการแปลงผล check → สถานะ control · นิยาม INCOMPLETE · การแยก formative/final · ถ้อยคำ | เอกสารนี้ | commit ใน repo นี้ |
| profile การติดตั้งที่ประเมิน | เอกสารนี้ §3 | ระบุใน manifest ทุกรอบ |

🔴 **ลำดับบังคับ:** matrix และ protocol ถูก commit **ก่อน** รอบ `final` ทุกครั้ง · ถ้าแก้ matrix หลังเห็นผล ⇒ ต้องขึ้นรุ่นใหม่
และรอบที่รันกับรุ่นเก่ากลายเป็น formative โดยอัตโนมัติ

## 3. profile การติดตั้ง

| profile | ความหมาย | ผลต่อ matrix |
|---|---|---|
| **`LOOPBACK_HTTP`** (ปัจจุบัน) | ผลิตภัณฑ์ bind ที่ `127.0.0.1` · HTTP · ผู้ปฏิบัติคนเดียว · ไม่มี authentication/session · local-first ไม่โหลดทรัพยากรภายนอก | ข้อ `CONDITIONAL` ที่เงื่อนไขคือ TLS (SG-11 · SG-34) = `NOT_APPLICABLE` แต่ **บันทึกค่าที่พบ** · V6/V7 = `NOT_APPLICABLE` (SG-44) |
| `NETWORK_TLS` (อนาคต) | เปิดสู่เครือข่ายผ่าน TLS | ข้อ CONDITIONAL กลับมาบังคับ · ต้องประกาศ matrix รุ่นใหม่ที่เพิ่ม V6/V7/V12 ก่อนประเมิน |

## 4. สถานะและกติกา (fail-closed)

สถานะ control มีเพียง `PASS | FAIL | REVIEW | NOT_APPLICABLE` · สถานะ check มี `PASS | FAIL | INCOMPLETE | RECORDED`

1. `applicability = NOT_APPLICABLE` ⇒ `NOT_APPLICABLE`
2. `applicability = CONDITIONAL` และเงื่อนไขไม่เป็นจริงใน profile ⇒ `NOT_APPLICABLE`
3. check ใด `FAIL` ⇒ `FAIL`
4. check ใด `INCOMPLETE` / ไม่ได้รัน / `RECORDED` ⇒ `REVIEW` — **ห้ามนับ PASS**
5. control แบบ `manual` (SG-50 ZAP) ⇒ `REVIEW` จนกว่าจะมี disposition ของคน แม้ทุก check PASS
6. ทุก check `PASS` ⇒ `PASS`

**INCOMPLETE เกิดเมื่อ:** เครื่องมือไม่พร้อม (ZAP/pip-audit/playwright ไม่มี) · รันไม่จบ/timeout · อ่านผลไม่ได้ · test ถูก skip ·
leak_check คืน exit 3 · target เปิดไม่ขึ้น — ทุกกรณีถูกบันทึกเหตุผลใน `steps/<step>/meta.json`

**disposition ของ finding High/Medium (ZAP และ FAIL ที่ไม่แก้):** `FIXED | ACCEPTED_RISK | FALSE_POSITIVE | REVIEW_REQUIRED` + เหตุผล + หลักฐาน
บันทึกใน `dispositions.json` (คนเขียน · runner อ่านอย่างเดียว) และสรุปใน `SECURITY_RESULT_SUMMARY.md`

🔴 **ไม่มีคะแนนรวมถ่วงน้ำหนัก** — รายงานเป็นจำนวนนับแยกสถานะเท่านั้น (ตามใบ #23)

## 5. ขั้นตอนการรันและสิ่งที่เก็บ (reproducible runner)

runner อยู่ใน repo ระบบ (แพ็กเกจ `security_gate/` ระดับบนสุด · **แยกจาก `redbook`** เพื่อคงกติกา local-first ของผลิตภัณฑ์ที่ห้ามมีไลบรารีเครือข่าย · `security-gate-0.1.0`) · เรียกครั้งเดียว

```
python -m security_gate.runner --matrix SECURITY_CONTROL_MATRIX.csv --out <นอก git> \
    --phase formative|final [--profile LOOPBACK_HTTP] --leak-check <leak_check.py> \
    --pip-audit <pip-audit.exe> --browser-python <python ที่มี playwright> [--zap-cmd "..."]
```

| step | เครื่องมือ | check ที่ออก | raw ที่เก็บ |
|---|---|---|---|
| environment | `pip freeze --all` | `D:inventory` `D:defusedxml_present` | `frozen.txt` · `platform.json` |
| pytest | pytest — เฉพาะไฟล์ที่ matrix อ้าง (`T:`) | `T:<file>` · `T:<file>::<test>` | `junit.xml` · `stdout.txt` |
| target | uvicorn บน `127.0.0.1:<พอร์ตสุ่ม>` + ข้อมูลสังเคราะห์ (`scripts/demo_ao_workbooks.py`) ด้วยตัวเลือกเปิดเซิร์ฟเวอร์เดียวกับผู้ใช้จริง | — | `target.json` · `server_stdout.txt` |
| http_probes | httpx (passive · ไม่มี payload ทำลาย) | `H:*` 22 check | `probes.json` (URL · method · status · header) |
| browser | Playwright + Chromium headless | `B:*` 4 check | `result_raw.json` · ภาพหน้าจอ (สังเคราะห์) |
| pip_audit | pip-audit ใน venv แยกนอกโครงการ ตรวจ `frozen.txt` ของ venv แอป | `D:pip_audit` | `raw.json` · `audit_input.txt` |
| zap | OWASP ZAP (cross-platform package · JRE Temurin 21 · ติดตั้งระดับผู้ใช้ ตรวจ SHA-256 กับค่าที่ผู้เผยแพร่ประกาศ) ผ่าน **Automation Framework**: `spider` (GET-only · ไม่ส่งฟอร์ม · ≤2 นาที) + `passiveScan-wait` + `report` — **ไม่มี job activeScan** · เนื้อหาเทียบเท่า baseline scan | `Z:zap_baseline` | `zap_plan.yaml` · `report.json/html` · เวอร์ชัน ZAP/Java ใน `meta.json` |
| leak_check | `leak_check.py` (repo นี้) ต่อโฟลเดอร์หลักฐานทั้งหมด | `L:evidence_leak_check` | `stdout.txt` (ไม่มีค่า hit) |

ทุก step เก็บ `command.txt` (คำสั่งจริง) และ `meta.json` (เวลาเริ่ม/จบ UTC · exit code · เวอร์ชันเครื่องมือ) ·
ท้ายรอบเขียน `SECURITY_RUN_MANIFEST.json` · `SECURITY_RESULT_SUMMARY.md` · `control_results.json` · `HASHES.sha256`
(ทุกไฟล์ **ยกเว้น** manifest และตัว HASHES เอง — manifest เก็บ `hashes_sha256_of_HASHES_file` ⇒ ตรวจสองชั้น: `sha256sum -c HASHES.sha256` แล้วเทียบแฮชของ HASHES กับค่าใน manifest) ·
ไฟล์ข้อความทุกไฟล์เขียนด้วย **LF** และโฟลเดอร์หมวดนี้ตรึง `eol=lf` ใน `.gitattributes` เพื่อให้แฮชเท่ากันทุก checkout · **ไม่เก็บภาพหน้าจอ** (ไบนารีทำให้ตัวตรวจการรั่วเจอรูปแบบปลอม — หลักฐานของขั้นเบราว์เซอร์คือ JSON)

**การกลบก่อนเขียน:** ข้อความที่เครื่องมือพิมพ์ถูกกลบเส้นทางสัมบูรณ์ทุกรูปแบบเป็น `<path>` ก่อนลงดิสก์ ·
manifest ไม่บันทึก commit hash ของ repo ระบบ (private) แต่บันทึก **ลายนิ้วมือ** (SHA-256 ของ hash · 16 ตัวแรก) + ชื่อ branch + dirty flag ·
ชุดหลักฐานยังต้องผ่าน `leak_check` (ขั้น L) ก่อนนำขึ้น repo นี้ และ "0 hit" ไม่ใช่ใบอนุญาตเผยแพร่โดยลำพัง

## 6. target และการอนุญาต

- target = เซิร์ฟเวอร์ที่ runner เปิดเองบน loopback ด้วยโฟลเดอร์ข้อมูลชั่วคราวและ **ข้อมูลสังเคราะห์ 100%** · ลบทิ้งเมื่อจบรอบ
- runner **ไม่มีตัวเลือก**ให้ชี้ไป URL อื่น — กันการสแกนเชิงรุกต่อระบบที่ไม่ได้รับอนุญาตเชิงโครงสร้าง
- ZAP ที่อนุญาตในรุ่นนี้ = **baseline/passive เท่านั้น** · active scan อยู่นอกขอบเขต ต้องขออนุมัติแยก
- สถานะ `BLOCKED` ของ ZAP ใน `LANES_BACKLOG.md` (C-09) และ `LANE_D1P` (S-6) ถูก **ปลดเฉพาะขอบเขตนี้** โดยใบ #23 (Gift · 6 ต.ค. 2569) —
  ไม่ปลด Phase 3 PDF / Audit Trail import

## 7. การแยก formative ออกจาก final

| | formative | final |
|---|---|---|
| จุดประสงค์ | หา finding · แก้โค้ด · ดู before | ผลที่อ้างในบทวิจัย |
| เงื่อนไข | รันได้ตลอดเวลา | matrix+protocol commit แล้ว · โค้ดที่แก้จาก finding commit แล้ว · ไม่มีการแก้ matrix หลังเห็นผล |
| ป้ายใน manifest/summary | `phase: formative` + กล่องเตือนสีแดง | `phase: final` |
| การอ้าง | อ้างได้เฉพาะเป็น "ก่อนแก้" ของ finding | อ้างเป็นผลประเมิน |

**before/after:** ทุก finding ที่ทำให้แก้โค้ดต้องมี `F-xx` ใน `FINDINGS_LOG.md` พร้อม run id ของรอบที่พบ (before) และรอบที่ยืนยันว่าแก้แล้ว (after) ·
ห้ามแก้ผลรอบ before ย้อนหลัง

## 8. ตัวชี้วัดที่รายงาน (ไม่มีคะแนนรวม)

1. controls ที่ประกาศ · 2. applicable · 3. PASS / FAIL / REVIEW / N/A · 4. unresolved FAIL (และ High/Medium ของ ZAP)
5. data-leakage findings (leak_check บนหลักฐาน + เส้นทางสัมบูรณ์ในหน้าเว็บ) · 6. dependency vulnerabilities ณ วันที่รัน (ตรวจได้ x จาก y)
7. browser/security regression pass/fail · 8. ZAP alert แยก severity · 9. before → after ต่อ finding

## 9. ข้อจำกัดที่ประกาศไว้ล่วงหน้า

- check แบบ `static` เป็น heuristic จากข้อความซอร์ส (เช่น SQL ประกอบสตริง · มาร์กเกอร์การเขียนใน GET) — บอกว่า "มี/ไม่มีรูปแบบ" ไม่ใช่การพิสูจน์
- http probe ตรวจชุด URL ที่ประกาศในโค้ด probe — ไม่ใช่การ crawl ทุกเส้นทาง · ZAP baseline เป็นชั้นเสริมสำหรับส่วนที่ probe ไม่ครอบ
- ZAP รันด้วย spider แบบ GET-only (ไม่ส่งฟอร์ม) ⇒ passive rules เห็นเฉพาะหน้าที่เข้าถึงได้โดยไม่เปลี่ยนสถานะ (รอบแรกพบ 16 URL) — ไม่ใช่ coverage ของทุกเส้นทาง · SG-50 เป็น control แบบ manual: ตัวเลข alert อ้างได้ แต่สถานะ PASS ต้องมี disposition ของคนก่อน · ถ้าเครื่องไม่มี Java/ZAP ⇒ `INCOMPLETE` (ไม่ปลอมเป็น PASS)
- ผลทั้งหมดรันบนเครื่องผู้พัฒนา · **ไม่มี CI** · การทำซ้ำโดยบุคคลที่สามต้องใช้ repo ระบบ (private) จึงเป็น "ทำซ้ำได้โดยผู้มีสิทธิ์" ไม่ใช่สาธารณะ
- `pip-audit` ข้ามแพ็กเกจที่หาบน PyPI ไม่ได้ (เช่น เครื่องมือของตัวจัดการแพ็กเกจเอง) — รายงาน "ตรวจได้ x จาก y" เสมอ
