# วิธีทำงานของทีม — Gift × Bo × Giho × Codex

สถานะเอกสาร: วิธีทำงานของทีมเท่านั้น
ขอบเขต: การจัดงาน การตรวจงาน และการส่งมอบ ไม่ใช่แหล่งอ้างอิงวิจัย ไม่เปลี่ยนวิธีวิจัย เกณฑ์ประเมิน ข้ออ้าง ผลวิจัย หรือหลักฐานที่ตรึงไว้

กติกาโครงการและคำสั่ง Gift มีอำนาจเหนือเอกสารนี้ นำแนวคิดจาก [pstack](https://github.com/michael-denyer/pstack-claude) มาปรับใช้เฉพาะที่เหมาะ ไม่ต้องติดตั้ง pstack และไม่ถือว่าสกิลของ pstack มีอยู่ในเครื่อง

## 1. เลือกขั้นตอนให้พอดีกับงาน

| ชนิดงาน | ขั้นตอนขั้นต่ำ |
|---|---|
| เล็ก ชัดเจน ย้อนกลับได้ | ลงมือในขอบเขต → ตรวจเฉพาะจุด → ส่งผล |
| บั๊กที่ยังไม่รู้สาเหตุ | ไล่เส้นทางที่เกี่ยวข้อง → ทำให้เกิดซ้ำเมื่อทำได้ → หาเหตุ → แก้เฉพาะจุด → ตรวจกรณีเดิม |
| เปลี่ยนข้ามโมดูล | ระบุ interface/dependency/ผู้เรียกที่ได้รับผลก่อน → ลงมือ → ตรวจพฤติกรรมที่เกี่ยวข้อง |
| งานยาว | เก็บบันทึกสั้นเมื่อช่วยกลับมาทำต่อ ใช้ผลที่ตรวจแล้ว ไม่สำรวจซ้ำ |
| ก่อน milestone/freeze | ตรวจข้อโต้แย้งและกรณีล้มเหลวตามความเสี่ยง → ส่ง reviewer |

ผู้ทำเลือก workflow และ installed skills ที่จำเป็นเอง Gift ไม่ต้องจำชื่อสกิล ใช้หนึ่ง agent เป็นค่าเริ่มต้น ไม่ใช้ swarm/หลายโมเดลโดยไม่มีคำสั่งหรือข้อกำหนดที่เกี่ยวข้อง

## 2. ก่อนเริ่ม: หนึ่ง issue หนึ่งปัญหา หนึ่งเกณฑ์ตรวจรับ

ใช้ [template](../.github/ISSUE_TEMPLATE/bounded-work.md) สำหรับงานใหม่ Issue #1 เป็น index/coordination

- อ่าน body และ comments ล่าสุดของ issue รวมถึง claim/addendum/handoff ที่เกี่ยวข้อง
- ตรวจ branch และ working tree หากจะเปลี่ยนไฟล์ ประกาศ owner/reviewer, ขอบเขตไฟล์และ acceptance gate ก่อนแก้
- ไฟล์ที่ agent อื่นถือหรือส่งรอตรวจยังสงวนไว้ ถ้าชนให้ทำ read-only หรือเลือกงานอื่น
- ถ้ามีหลายปัญหาที่ปิดแยกกันได้ ให้แยก issue และ link ความสัมพันธ์
- ปัญหาใหม่ระหว่างทำ → issue ใหม่ ห้ามแอบพ่วงแก้
- เริ่มจากค้นหาและอ่านเฉพาะส่วนเกี่ยวข้อง ไม่ dump repo/transcript ทั้งหมด

ตัวอย่าง claim:
```markdown
**[CLAIM]** <ผู้ทำ> → ทุกฝ่าย · ตอบ <comment-id|เปิดเรื่อง>

**สรุป:** ทำ #<issue> เฉพาะ <ปัญหา>; ไฟล์ <repo-relative paths>
**ขอจาก ทุกฝ่าย:** ไม่มี — แจ้งขอบเขตกันชน
**หลักฐาน:** base <public commit>; ตรวจ claim ล่าสุดแล้ว; gate <ผลที่ต้องเห็น>
```

## 3. ระหว่างทำ

สำรวจเหตุผลของของเดิมก่อนแก้ แก้ต้นเหตุให้น้อยที่สุด ไม่ refactor ข้างเคียงโดยไม่จำเป็น
ถ้า reproduce ไม่ได้ ให้ระบุข้อจำกัดและหลักฐานอื่น ไม่แต่งผล failing case
เพิ่ม regression test เมื่อมีประโยชน์ต่อการป้องกันปัญหาซ้ำ ไม่เขียน test ที่เพียงลอก implementation

ไม่เปลี่ยน authority ของงานวิจัยผ่านเอกสาร workflow ถ้างานต้องการการตัดสินใจเช่นนั้น ให้ไป issue ที่รับผิดชอบและรอผู้มีอำนาจตามกติกาเดิม

## 4. Verification recipe

| งาน | สิ่งที่ต้องตรวจ | สิ่งที่ต้องบันทึก |
|---|---|---|
| Bug | กรณีเดิมหลังแก้ + regression ที่เกี่ยวข้อง | failing/passing evidence หรือเหตุที่ reproduce ไม่ได้ |
| Engine/interface | observable behavior + affected callers + invariant ที่ข้อกำหนดงานระบุ | boundary, versions, blast radius, คำสั่งและผล |
| เอกสาร/template | links, หัวข้อที่จำเป็น, ความสอดคล้องของ scope, diff และข้อมูลที่เผยแพร่ | changed files และผลตรวจเฉพาะจุด |
| Pre-freeze/milestone | adversarial/negative cases ตามความเสี่ยง + gates ที่ issue กำหนด | commit ที่ตรวจ, pass/fail/skipped, ข้อจำกัด, reviewer decision |

ใช้คำสั่งของโครงการที่เกี่ยวข้อง ไม่ตั้งตัวเลข test ผ่านขั้นต่ำใหม่ในเอกสารนี้
ตัวอย่างเครื่องมือที่มีอยู่ (รันจาก repo root):
```text
python 09_RESEARCH_BRIDGE/tools/comment_lint.py <draft-comment.md>
python 11_P1_VALIDATOR_REGISTRY/leak_check.py <changed-text-files>
```
leak_check ต้องมี local config ที่ครบตามเครื่องมือ ห้ามนำ config หรือค่าที่ hit ลง public; ถ้าตรวจไม่ได้ให้รายงานว่า BLOCKED ไม่ถือว่าผ่าน
คำสั่ง self-test ทดสอบตัวเครื่องมือ ไม่แทนการตรวจไฟล์งานจริง
tests ของ engine ใช้คำสั่งที่ owner ระบุใน issue/handoff ตาม environment จริง

แยก passed/failed/skipped ไม่เรียกผลในเครื่องว่า CI ไม่อ้างว่าทดสอบแล้วหากเพียงอ่านรายงาน
ขยายการตรวจเมื่อมี failure/ความเสี่ยง/ข้อกำหนดรองรับ หยุดรันซ้ำเมื่อผ่านแล้วและไม่มีหลักฐานใหม่

## 5. เช็กลิสต์ก่อนส่งงาน

- [ ] ทำครบ acceptance gate ของ issue หรือระบุสิ่งที่ยังติด
- [ ] diff อยู่ในขอบเขต; ปัญหาอื่นแยก issue แล้ว
- [ ] ตรวจ behavior และ affected callers เท่าที่เกี่ยวข้อง
- [ ] ระบุคำสั่ง/environment/ผลจริงและข้อจำกัด
- [ ] ตรวจข้อมูลก่อนเผยแพร่: ไม่มี private paths, private commits, internal data, answer key หรือ private mapping
- [ ] มี commit permalink หรือหลักฐานที่ผู้ตรวจเข้าถึงได้โดยไม่เปิดเผย private material
- [ ] สถานะชัด: BLOCKED / READY FOR REVIEW / ACCEPTED / CLOSED
- [ ] ผู้ทำไม่ถือว่า handoff ของตนคือการ ACCEPT โดย reviewer
- [ ] รายงานยาวอยู่ในไฟล์; comment สั้นตาม [COMMENT_PROTOCOL](../09_RESEARCH_BRIDGE/COMMENT_PROTOCOL.md)

## 6. ส่งมอบและปิดงาน

```markdown
**[HANDOFF]** <ผู้ทำ> → <reviewer> · ตอบ <comment-id|เปิดเรื่อง>

**สรุป:** READY FOR REVIEW — <ผลที่เปลี่ยนและ gate>
**ขอจาก <reviewer>:** ตรวจ gate และตอบ ACCEPT / REVISE / REJECT
**หลักฐาน:** <public commit permalink> · <คำสั่ง/ผลตรวจ> · <ข้อจำกัด>
```

Reviewer ตรวจ gate กับหลักฐานของรุ่นที่ส่ง ถ้าต้องแก้ให้ระบุรายการที่ตรวจได้
ปิด issue เมื่อ gate ผ่าน มี reviewer decision ตามข้อกำหนด และไม่มีงานจำเป็นค้าง
อย่าปิดเพียงเพราะ comments มากหรือส่ง handoff แล้ว บันทึกสิ่งที่ทำ/ไม่ทำและ links ก่อนปิด

## 7. บทบาทและการใช้ทรัพยากร

Gift ตัดสินเรื่องที่ต้องอาศัยอำนาจเจ้าของงาน; owner ลงมือและเก็บหลักฐาน; reviewer ตรวจรับ
Bo/Giho/Codex ใช้บทบาทตาม lane claim ของงานนั้น ไม่สวมอำนาจของอีกฝ่าย

ค้นหาก่อนอ่าน จำกัด output โหลดเฉพาะ skills/references ที่จำเป็น และเก็บ progress record เท่าที่ช่วยทำต่อ
ความถูกต้องและงานเสร็จมาก่อนประหยัด token ห้ามอ้างตัวเลขประหยัดโดยไม่มี usage evidence
