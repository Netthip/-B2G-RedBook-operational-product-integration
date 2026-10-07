# SUPERSEDED — run 20261006T231414Z-final (matrix 0.1.0)

รอบนี้ตรวจย้อนได้ครบ แต่ถูกแทนที่ด้วย **`20261007T013505Z-final`** (matrix **0.1.1** · sha256 `8b22f826…`) หลัง Bo REVIEW `6027478811` ขอ targeted regression ของ attribute-context XSS ก่อน ACCEPT:

- SG-12 เพิ่ม check `tests/test_security_gate_xss.py` + static 2 ข้อ (เข้มขึ้นเท่านั้น · ไม่แก้ expected ข้อเดิม)
- ระหว่างทำพบ F-09 (page/per_page ไม่ใช่ตัวเลข ⇒ 500) และ F-10 (JSON 422 สะท้อน input) — รอบนี้คือ **before** ของทั้งสอง

ผลของรอบนี้อ้างได้เฉพาะคู่กับ matrix 0.1.0 (`36b5230a…`) · คงไว้เป็นประวัติ (append-only)
