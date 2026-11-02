# -*- coding: utf-8 -*-
"""ชั้นบริการ — คั่นระหว่าง route ของเว็บกับเครื่องยนต์

🔴 คำสั่ง Bo · `BO REVIEW COMPLETE` (Issue #1) —
*"the service layer must sit between web routes and `redbook/t1b/*`"*

กติกาของชั้นนี้

1. route **ห้าม** import ``redbook.t1b.*`` โดยตรง — ต้องผ่านชั้นนี้เสมอ
2. ชั้นนี้ **ห้าม** import อะไรจาก ``fastapi`` / ``starlette`` / ``jinja2``
   เพื่อให้ทดสอบได้โดยไม่ต้องยกเว็บทั้งตัว และเปลี่ยนเฟรมเวิร์กได้โดยไม่แตะกติกา
3. สิ่งที่ออกจากชั้นนี้เป็น **projection** ที่ปลอดภัยต่อการแสดงผลแล้ว —
   ไม่มีเส้นทางไฟล์สัมบูรณ์ ไม่มี object ของเครื่องยนต์รั่วออกไป

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
