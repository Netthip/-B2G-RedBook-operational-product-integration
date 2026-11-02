# -*- coding: utf-8 -*-
"""กลบเส้นทางเครื่องในข้อความหลักฐานก่อนเขียนลงชุดหลักฐานที่จะเผยแพร่

ใช้แยกจาก :mod:`redbook.privacy` โดยตั้งใจ — ตัวกลบนี้ต้องทำงานกับ *ผลลัพธ์ของเครื่องมือ
ภายนอก* (pytest · pip-audit · playwright · ZAP) ที่พิมพ์เส้นทางของ interpreter และ
site-packages ซึ่งอยู่นอกสามรากข้อมูลที่ privacy policy รู้จัก · กฎที่นี่หยาบกว่า
(กลบทุกเส้นทางสัมบูรณ์) เพราะหลักฐานไม่จำเป็นต้องอ่านเส้นทางได้

🔴 การกลบนี้ **ไม่ใช่** ใบอนุญาตเผยแพร่ — ชุดหลักฐานยังต้องผ่าน ``leak_check`` (ขั้น L)
"""
from __future__ import annotations

import re

_WIN_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]+(?:[^\\/\s\"'<>|:*?\]\[,;]+[\\/]*)+")
_WIN_UNC = re.compile(r"\\\\[^\\\s\"'<>|]+(?:\\[^\\\s\"'<>|]+)+")
_POSIX_HOME = re.compile(r"/(?:home|Users)/[^\s\"'<>|]+")
_FILE_URI = re.compile(r"file:///?[^\s\"'<>|]+")

PLACEHOLDER = "<path>"


def redact_text(text: str) -> str:
    if not text:
        return text
    out = _FILE_URI.sub(PLACEHOLDER, text)
    out = _WIN_UNC.sub(PLACEHOLDER, out)
    out = _WIN_PATH.sub(PLACEHOLDER, out)
    out = _POSIX_HOME.sub(PLACEHOLDER, out)
    return out


def has_absolute_path(text: str) -> bool:
    return bool(_WIN_PATH.search(text) or _WIN_UNC.search(text) or _POSIX_HOME.search(text)
                or _FILE_URI.search(text))


__all__ = ["redact_text", "has_absolute_path", "PLACEHOLDER"]
