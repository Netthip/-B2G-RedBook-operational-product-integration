# SUPERSEDED — run 20261006T172344Z-final

รอบนี้ **ถูกต้องและตรวจย้อนได้** (HASHES ตรง · ไม่มี CR) แต่ถูกแทนที่ด้วย **`20261006T231414Z-final`** หลังกิ๊ฟอนุมัติการเปลี่ยนสภาพแวดล้อม (comment 6026979007):

- ติดตั้ง `defusedxml==0.7.1` ลง .venv ประเมิน + ตรึง lock ⇒ SG-16 FAIL → PASS (F-06)
- ติดตั้ง Java (Temurin 21 JRE) + OWASP ZAP 2.17.0 ระดับผู้ใช้ ⇒ SG-50 INCOMPLETE → รันแล้ว (F-08)

รอบนี้คือ **before** ของ F-06/F-08 · คงไว้เป็นประวัติ (append-only) · ห้ามอ้างเป็นผล final
