# PUBLICATION NOTE — 20261006T165937Z-formative

คัดลอกจากโฟลเดอร์หลักฐานต้นทาง 44 ไฟล์ · `HASHES.sha256` คือของต้นทาง (ไม่แก้) จึงตรวจความครบได้

## ไฟล์ที่ **กันไว้ไม่เผยแพร่** (ยังมีแฮชใน HASHES.sha256)

เหตุผล: leak_check (Z1) พบรูปแบบเส้นทางโฟลเดอร์ผู้ใช้วินโดวส์ 3 จุด — เป็นสตริงสมมติในซอร์สของ test ที่ล้ม (traceback) ไม่ใช่ข้อมูลจริง แต่กติกาเผยแพร่คือ hit = ห้าม push · ผลราย test อยู่ใน steps/pytest/outcomes.json และ result.json ที่เผยแพร่

| ไฟล์ | sha256 |
|---|---|
| `steps/pytest/junit.xml` | `e735f548fde67c7a0ea307fe2a78ce838738c4e454f5f67f83c6ef770e703125` |
| `steps/pytest/stdout.txt` | `73348d2f0e2c90a1575a06a7e789fdd903c21806123a2532af387bd93e443bbb` |
