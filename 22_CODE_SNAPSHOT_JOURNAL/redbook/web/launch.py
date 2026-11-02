# -*- coding: utf-8 -*-
"""ตัวเลือกการเปิดเซิร์ฟเวอร์ที่ใช้ร่วมกันทุกทางเข้า (run_local · demo · security target)

จุดเดียวที่กำหนดว่า uvicorn เปิดด้วยค่าใด — เพื่อให้ target ที่ security gate สแกน
**เหมือนกับที่ผู้ใช้เปิดจริง** ไม่ใช่ค่าที่แต่งขึ้นเฉพาะตอนตรวจ
"""
from __future__ import annotations


def uvicorn_options() -> dict:
    """คืน keyword ที่ส่งให้ ``uvicorn.run`` นอกเหนือจาก host/port"""
    return {
        "reload": False,
        "log_level": "info",
        "access_log": True,
        # 🔴 ไม่ส่งหัว ``Server: uvicorn`` — ไม่เปิดเผยผลิตภัณฑ์/รุ่นของส่วนประกอบเบื้องหลัง
        # (ASVS V13.4.6 · Security Gate #23 · F-05)
        "server_header": False,
    }


__all__ = ["uvicorn_options"]
