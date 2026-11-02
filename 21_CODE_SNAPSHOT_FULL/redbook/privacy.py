# -*- coding: utf-8 -*-
"""สัญญาความเป็นส่วนตัวของผลิตภัณฑ์ — การกลบเส้นทางไฟล์และการกันเนื้อหารั่ว

🔴 คำสั่ง Bo · `BO REVIEW COMPLETE` (Issue #1) — *"privacy leakage prevention
precedes visual redesign"* และหัวข้อ SECURITY PRIORITY ข้อ 2 · 4

**สัญญาสามข้อที่ชั้นนี้บังคับ**

1. **เส้นทางไฟล์แบบสัมบูรณ์ห้ามปรากฏ** ในหน้าเว็บ · ในล็อก · ในแฟ้มรายการ
   ที่ตั้งใจจะส่งให้คนอื่น — เพราะเส้นทางบนเครื่องผู้ใช้มี *ชื่อบัญชีผู้ใช้*
   และโครงสร้างโฟลเดอร์ของเจ้าของเครื่องติดไปด้วยเสมอ
2. **ข้อผิดพลาดภายในดิบ ๆ ห้ามถึงผู้ใช้** — ไม่มี traceback ไม่มีชื่อคลาส
   ข้อยกเว้น ไม่มีข้อความจากไลบรารีภายใน · ผู้ใช้ได้ ``error_id`` ไว้แจ้งผู้ดูแล
3. **เนื้อหาในสมุดงานห้ามไหลเข้าล็อกหรือแฟ้มที่แชร์** — ยอดเงิน ชื่อรายการ
   ชื่อหน่วยงาน เป็นเอกสารราชการของผู้ใช้ · จะปรากฏได้เฉพาะบนหน้าจอที่
   ผู้ตรวจเปิดดูเองเท่านั้น

โมดูลนี้ **ไม่ขึ้นกับเว็บเฟรมเวิร์ก** จึงเรียกได้ทั้งจาก route · จาก formatter
ของ logging · และจากตัวสร้าง manifest

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
from __future__ import annotations

import re
from pathlib import Path

from . import config

#: ``0.1.0`` (1b91353) — ขอบเขตเส้นทางหยุดที่ช่องว่างแรก ⇒ กลบขาด
#: ``0.2.0`` — ขอบเขตสามข้อด้านล่าง (3691ed8) + ``<HOME>`` ไม่เก็บส่วนท้าย
#:
#: 🔴 รุ่นนี้ถูกประทับลง snapshot ของการส่งออกและ audit ของรอบ T1B **ตอนสร้าง**
#: เท่านั้น · สิ่งที่สร้างก่อนหน้าไม่มีฟิลด์นี้ ⇒ ถือว่า "ไม่ทราบ / ก่อน 0.2.0"
#: ห้ามเติมย้อนหลัง ไม่เช่นนั้นจะดูเหมือนผ่านนโยบายใหม่ทั้งที่ไม่ได้ผ่าน
#: ``0.2.1`` — "https:" ไม่นับเป็นอักษรไดรฟ์ (URL ทางการไม่ใช่เส้นทางในเครื่อง)
#: ``0.2.2`` — Bo REVIEW 6358440451: เส้นทางที่ติดหลังตัวอักษร/ตัวเลขโดยไม่มีตัวคั่นกลบได้ · ไดรฟ์ที่ตามด้วย ``//``
#: เท่านั้นที่ไม่นับ (scheme ของ URL) · เส้นทางเข้ารหัส % ใน URL/query กลบได้ · ประกาศรูปแบบที่รองรับ/ไม่รองรับ
#: ``0.2.3`` — Bo REVIEW #42 6435141649: จุดยึดที่อักษรไดรฟ์/ตัวคั่นถูกเข้ารหัสเอง หรือผสมดิบกับเข้ารหัส
#: (``%43%3A%5C…`` · ``C%3A\…`` · ``C:%5C…`` · ``%2FUsers/…`` · ``%5C%5Cserver…``) กลบได้ด้วยการหาบนข้อความที่ถอดหนึ่งชั้น ·
#: ``https%3A%2F%2F…`` (scheme ที่เข้ารหัส) ไม่ถูกกลบผิดเป็นไดรฟ์อีก
PRIVACY_VERSION = "t1b-privacy-0.2.3"

#: รูปแบบที่ :func:`redact_text` กลบได้ — มีเทสต์ทุกแบบด้วยตัวตรวจอิสระ (สตริงนกขมิ้น ไม่ใช่ regex ตัวเดียวกับตัวกลบ)
SUPPORTED_FORMS = (
    r"ไดรฟ์วินโดวส์ C:\ หรือ C:/ — ต้นข้อความ หลังตัวคั่นใด ๆ หรือติดหลังตัวอักษร/ตัวเลขโดยไม่มีตัวคั่น",
    r"UNC \\server\share\…",
    "รากระบบ /home /Users /root /var /tmp /mnt /media /opt /srv /private",
    "file:///C:/… และเส้นทางดิบใน query/fragment ของ URL",
    "เส้นทางเข้ารหัส % หนึ่งชั้นใน URL/query (C%3A%5C… · C%3A%2F… · %2FUsers%2F…) ตัวพิมพ์เล็กหรือใหญ่",
    "เข้ารหัสซ้อนสองชั้นของจุดยึดไดรฟ์ (C%253A%255C…) — ถอดหนึ่งชั้นแล้วตรงกฎจุดยึดเข้ารหัส",
    "จุดยึดเข้ารหัส % หนึ่งชั้นทั้งตัวหรือบางส่วน รวมอักษรไดรฟ์ (%43%3A%5C… · C%3A\… · C:%5C… · %2FUsers/… · %5C%5Cserver…)",
    r"backslash แบบ escape ของ JSON (C:\\Users\\…)",
)
#: รูปแบบที่ **ไม่รองรับ** (ประกาศไว้ ไม่ใช่สัญญา) — ข้อความ/ล็อกของระบบต้องไม่สร้างรูปแบบเหล่านี้
UNSUPPORTED_FORMS = (
    "เข้ารหัสซ้อนสามชั้นขึ้นไป (%25253A · %25255C) หรือ base64/hex",
    "รากระบบอื่นนอกรายการ (/etc /data …) และ ~/ (ทิลด์)",
    "เส้นทางที่ถูกตัดข้ามบรรทัด",
    "เส้นทางสัมพัทธ์ — อยู่นอกขอบเขตของตัวกลบเส้นทางสัมบูรณ์ (ชื่อแฟ้ม/โฟลเดอร์สัมพัทธ์ยังบอกบุคคลหรือหน่วยงานได้ "
    "ต้องผ่านนโยบายชื่อไฟล์/เนื้อหาอีกชั้น เช่น redact_filename)",
)

#: ป้ายแทนเส้นทางที่ถูกกลบทั้งเส้น — ใช้อักขระ ASCII ล้วนเพื่อให้ปลอดภัย
#: ทั้งใน HTML · JSON · CSV · ล็อกไฟล์ ที่ encoding อาจต่างกัน
PATH_REMOVED = "<path-removed>"

#: จุดยึดที่ถูกแทนด้วยชื่อเชิงสัญลักษณ์ — เรียงจาก **ยาวไปสั้น** ตอนใช้งาน
#: เพื่อให้เส้นทางที่ซ้อนกันถูกแทนด้วยจุดยึดที่เจาะจงที่สุด
def _anchors() -> list[tuple[Path, str]]:
    """อ่านจุดยึดจาก :mod:`config` **ทุกครั้งที่เรียก**

    🔴 ห้าม cache — ``REDBOOK_DATA_DIR`` ถูกตั้งใหม่ได้ระหว่างเทสต์และระหว่าง
    การย้ายโฟลเดอร์ข้อมูล ถ้า cache ไว้จะกลบเส้นทางเก่าแต่ปล่อยเส้นทางใหม่หลุด
    """
    out: list[tuple[Path, str]] = [
        (config.DATA_DIR, "<DATA_DIR>"),
        (config.PROJECT_ROOT, "<PROJECT_ROOT>"),
    ]
    if config.DATA_ROOT is not None:
        out.append((config.DATA_ROOT, "<DATA_ROOT>"))
    try:
        out.append((Path.home(), "<HOME>"))
    except (RuntimeError, OSError):        # ไม่มี HOME ในบางสภาพแวดล้อม
        pass
    return sorted(out, key=lambda a: len(str(a[0])), reverse=True)


# ---------------------------------------------------------------- ขอบเขตของเส้นทาง
#
# 🔴 **ข้อบกพร่องที่ Bo ชี้ (BO REVIEW · consolidated · หัวข้อ B)**
#
# รูปแบบเดิมใช้ ``[^\s...]*`` ซึ่ง **หยุดที่ช่องว่างแรก** ⇒ เส้นทางที่มีชื่อโฟลเดอร์
# หลายคำ (เช่น ``OneDrive\เรียน ป.โท\Budget Intelligence System``) ถูกกลบเฉพาะหัว
# แล้วปล่อยหางไว้ · และเพราะ :func:`find_absolute_paths` ใช้รูปแบบเดียวกัน
# มันจึงรายงานว่า "ไม่เหลือเส้นทางแล้ว" ทั้งที่ข้อมูลยังอยู่
# ⇒ **เทสต์ที่ผ่านคือส่วนหนึ่งของข้อบกพร่อง ไม่ใช่หลักฐานว่าไม่มี**
#
# **ขอบเขตที่ประกาศไว้ตอนนี้ — เรียงตามลำดับที่ใช้**
#
# 1. อยู่ในเครื่องหมายคำพูด (``"`` ``'`` `` ` ``) ⇒ ถึง **เครื่องหมายปิด**
#    (ทำได้เองเพราะชุดอักขระด้านล่างไม่รับเครื่องหมายคำพูด)
# 2. ไม่มีเครื่องหมายคำพูด และมี **นามสกุลไฟล์** ⇒ ถึงนามสกุล **ตัวท้ายสุด**
# 3. ไม่มีทั้งสองอย่าง ⇒ ถึง **จบบรรทัด**
#
# ข้อ 3 กลบเกินได้ — ยอมรับโดยเจตนา · **กลบขาดคือข้อมูลรั่ว กลบเกินคือข้อความอ่านยาก**
# ขึ้นบรรทัดใหม่เป็นขอบเสมอ มิฉะนั้นล็อกหายเป็นก้อน

#: อักขระที่นับว่ายังอยู่ในเส้นทางได้ — **ยอมรับช่องว่าง** แต่ไม่ยอมรับ
#: ขึ้นบรรทัดใหม่ เครื่องหมายคำพูด และอักขระที่วินโดวส์ห้ามใช้ในชื่อไฟล์อยู่แล้ว
_IN_PATH = r"[^\r\n<>\"'`|?*]"

_ANCHOR = (
    # 🔴 0.2.2 — อักษรไดรฟ์จับได้แม้ติดหลังตัวอักษร/ตัวเลข ("fileC:\Users…" · Bo REVIEW 6358440451) ·
    # ที่ไม่นับคือไดรฟ์ที่ตามด้วย "//" = scheme ของ URL ("https://" · "file:///") — "C:\…" "D:/…" จับเหมือนเดิม
    r"(?:[A-Za-z]:(?:\\|/(?!/))"                    # C:\ หรือ C:/ (ไม่ใช่ scheme://)
    r"|\\\\[^\\/\r\n]+[\\/]"        # UNC \\server\
    r"|/(?:home|Users|root|var|tmp|mnt|media|opt|srv|private)/"
    # 0.2.2 — เข้ารหัส % หนึ่งชั้นใน URL/query: C%3A%5C · C%3A%2F · %2FUsers%2F
    # 0.2.3 — ไม่นับ scheme ที่เข้ารหัส ("https%3A%2F%2F" = "https://" ไม่ใช่ไดรฟ์ S:)
    r"|[A-Za-z]%3[Aa]%(?:5[Cc]|2[Ff](?!%2[Ff]))"
    r"|%2[Ff](?:home|Users|root|var|tmp|mnt|media|opt|srv|private)%2[Ff])"
)

#: 🔴 ราก POSIX จำกัดเฉพาะที่รู้จัก — ห้ามใช้ ``/`` ลอย ๆ เป็นตัวจับ
#: มิฉะนั้นจะไปโดน URL · วันที่ · อัตราส่วน · เลขหัวข้อ
#:
#: สาขาแรก = มีนามสกุล (ขอบชัด) · สาขาหลัง = ไม่มีนามสกุล ⇒ ถึงจบบรรทัด
_PATH = re.compile(
    rf"{_ANCHOR}(?:{_IN_PATH}*\.[A-Za-z0-9]{{1,8}}(?![A-Za-z0-9])|{_IN_PATH}*)"
)


def _norm(text: str) -> str:
    return text.replace("\\", "/")


def redact_path(value) -> str:
    """กลบเส้นทางไฟล์หนึ่งเส้น

    * อยู่ใต้จุดยึดที่รู้จัก ⇒ แทนส่วนหัวด้วยชื่อเชิงสัญลักษณ์
      เช่น ``<DATA_DIR>/uploads/ab12.xlsx`` — ยังตรวจปัญหาได้ แต่ไม่บอกว่า
      เครื่องนี้เป็นของใครและวางโฟลเดอร์ไว้ที่ไหน
    * ไม่อยู่ใต้จุดยึดใดเลย ⇒ เหลือเพียง ``<path-removed>/<ชื่อไฟล์>``
    * เส้นทางแบบสัมพัทธ์ ⇒ คืนตามเดิม — อยู่นอกขอบเขตของตัวกลบนี้ (ชื่อแฟ้มสัมพัทธ์ยังบอกตัวตนได้ ใช้ :func:`redact_filename`)

    🔴 **ชื่อไฟล์ยังคงอยู่โดยเจตนา** เพราะผู้ตรวจต้องรู้ว่ากำลังพูดถึงแฟ้มไหน
    แต่ชื่อแฟ้มของผู้ใช้อาจมีชื่อหน่วยงานอยู่ ⇒ แฟ้มที่จะ **ส่งออกไปให้คนอื่น**
    ต้องใช้ :func:`redact_filename` เพิ่มอีกชั้น
    """
    if value is None:
        return ""
    raw = str(value)
    if not raw:
        return ""
    norm = _norm(raw)
    for anchor, token in _anchors():
        a = _norm(str(anchor)).rstrip("/")
        if not a:
            continue
        if norm == a:
            return token
        if norm.lower().startswith(a.lower() + "/"):
            return token + norm[len(a):]
    if _is_absolute(norm):
        return f"{PATH_REMOVED}/{norm.rsplit('/', 1)[-1]}"
    return norm


def _is_absolute(norm: str) -> bool:
    """สัมบูรณ์หรือไม่ — ตัดสินจาก *รูปแบบข้อความ* ไม่ใช่ระบบไฟล์ที่กำลังรันอยู่

    🔴 ต้องรู้จักทั้งสองแบบเสมอ มิฉะนั้น manifest ที่สร้างบนวินโดวส์แล้วเปิดอ่าน
    บนลินุกซ์ (หรือกลับกัน) จะกลบไม่หมด
    """
    if re.match(r"^[A-Za-z]:/", norm) or norm.startswith("//"):
        return True
    return bool(re.match(
        r"^/(?:home|Users|root|var|tmp|mnt|media|opt|srv|private)/", norm))


#: จุดยึดที่ **เก็บส่วนท้ายไว้ได้** เมื่อกลบในข้อความอิสระ
#:
#: 🔴 ``<HOME>`` **ไม่อยู่ในชุดนี้โดยเจตนา** — ใต้โฮมของผู้ใช้คือของส่วนตัวทั้งหมด
#: การเก็บส่วนท้ายไว้จะเปิดเผยโครงสร้างโฟลเดอร์และ **ชื่อแฟ้ม** ของผู้ใช้
#: ซึ่งเป็นข้อบกพร่องตระกูลเดียวกับที่รอบนี้แก้ · สามตัวที่เหลือเป็นโฟลเดอร์ของ
#: ระบบเองและของโครงการ จึงเก็บส่วนท้ายไว้ให้ตรวจปัญหาได้
_TAIL_SAFE_TOKENS = ("<DATA_DIR>", "<PROJECT_ROOT>", "<DATA_ROOT>")


_PCT = re.compile(r"(?:%[0-9A-Fa-f]{2})+")


def _unquote(s: str) -> str:
    """ถอด %XX หนึ่งชั้น (UTF-8) — ไม่ใช้ ``urllib`` (เทสต์สถาปัตยกรรมห้ามไลบรารีเครือข่ายในแพ็กเกจ)"""
    return _PCT.sub(lambda m: bytes(int(h, 16) for h in m.group(0).split("%")[1:]).decode("utf-8", "replace"), s)


def _redact_span(raw: str) -> str:
    """กลบเส้นทางหนึ่งช่วงที่ตัดมาจากข้อความอิสระ

    🔴 เข้มกว่า :func:`redact_path` โดยเจตนา — **ไม่เก็บส่วนท้ายไว้เลย**
    เว้นแต่เส้นทางนั้นอยู่ใต้จุดยึดใน :data:`_TAIL_SAFE_TOKENS`

    เหตุผล: ช่วงที่ตัดมาจากข้อความอิสระอาจกินคำอื่นเข้ามาด้วย และเส้นทางของผู้ใช้
    มีชื่อโฟลเดอร์กับชื่อแฟ้มที่บอกตัวตนหน่วยงานได้ · การเก็บ "ส่วนท้าย" ไว้
    คือรูปแบบเดียวกับที่ข้อบกพร่องรอบนี้ปล่อยหลุด
    """
    if "%" in raw:                         # 0.2.2 — เส้นทางเข้ารหัส % ใน URL: ถอดหนึ่งชั้นก่อนตัดสิน
        raw = _unquote(raw)
    out = redact_path(raw)
    return out if out.startswith(_TAIL_SAFE_TOKENS) else PATH_REMOVED


def redact_text(text) -> str:
    """กลบ **ทุก** เส้นทางสัมบูรณ์ที่ฝังอยู่ในข้อความอิสระ

    ใช้กับข้อความข้อผิดพลาด บรรทัดล็อก และช่องบรรยายใน manifest
    ขอบเขตที่ใช้ประกาศไว้ที่หัวข้อ "ขอบเขตของเส้นทาง" ด้านบน
    """
    if text is None:
        return ""
    s = str(text)
    if not s:
        return ""
    s = _PATH.sub(lambda m: _redact_span(m.group(0)), s)
    return _redact_encoded(s) if "%" in s else s


def _decoded_view(s: str) -> tuple[str, list[tuple[int, int]]]:
    """ถอด %XX หนึ่งชั้นทั้งข้อความ พร้อมตำแหน่งในต้นฉบับของอักขระที่ถอดแล้วแต่ละตัว ``(เริ่ม, จบ)``"""
    out, pos, i = [], [], 0
    for m in _PCT.finditer(s):
        for j in range(i, m.start()):
            out.append(s[j])
            pos.append((j, j + 1))
        for ch in _unquote(m.group(0)):
            out.append(ch)
            pos.append((m.start(), m.end()))
        i = m.end()
    for j in range(i, len(s)):
        out.append(s[j])
        pos.append((j, j + 1))
    return "".join(out), pos


def _redact_encoded(s: str) -> str:
    """0.2.3 (Bo REVIEW #42 6435141649): จุดยึดที่ถูกเข้ารหัส % เอง หรือผสม — ``%43%3A%5CUsers…`` · ``C%3A\\Users…`` ·
    ``C:%5CUsers…`` · ``%2FUsers/…`` · ``%5C%5Cserver…`` — หารูปแบบเส้นทางบน **ข้อความที่ถอดหนึ่งชั้น** แล้วกลบช่วงที่ตรงกัน
    ในต้นฉบับ · ไม่ถอดทั้ง URL แล้วคืนค่าที่ถอด (โครงสร้าง URL ส่วนอื่นคงเดิม) · เข้ารหัสซ้อนสองชั้นยังไม่รองรับ (ประกาศไว้)"""
    view, pos = _decoded_view(s)
    spans = [(pos[m.start()][0], pos[m.end() - 1][1], m.group(0)) for m in _PATH.finditer(view)]
    for a, b, decoded in reversed(spans):
        if "%" not in s[a:b]:
            continue                        # ไม่มีส่วนที่เข้ารหัส = รอบแรกจัดการแล้ว
        out = redact_path(decoded)
        s = s[:a] + (out if out.startswith(_TAIL_SAFE_TOKENS) else PATH_REMOVED) + s[b:]
    return s


def redact_filename(name) -> str:
    """เหลือเฉพาะ *ส่วนขยาย* ของชื่อไฟล์ — สำหรับแฟ้มที่จะส่งออกไปให้คนอื่น

    ชื่อแฟ้มที่ผู้ปฏิบัติงานตั้งเองมักมีชื่อหน่วยงานและปีอยู่ด้วย
    (เช่นเดียวกับที่ด่านตัวตนหน่วยงานใช้เป็นหลักฐาน) จึงถือเป็นเนื้อหาเอกสาร
    """
    if not name:
        return PATH_REMOVED
    leaf = _norm(str(name)).rsplit("/", 1)[-1]
    suffix = Path(leaf).suffix.lower()
    return f"{PATH_REMOVED}{suffix}" if suffix else PATH_REMOVED


def redact_obj(obj, *, filenames: bool = False):
    """กลบเส้นทางในโครงสร้างซ้อน (dict / list / tuple / str) แบบ recursive

    ``filenames=True`` ⇒ กลบชื่อไฟล์ด้วย สำหรับ manifest ที่ตั้งใจจะแชร์
    (คีย์ที่ลงท้ายด้วย ``_name`` / ``filename`` / ``file_name``)
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if filenames and isinstance(v, str) and _looks_like_filename_key(k):
                out[k] = redact_filename(v)
            else:
                out[k] = redact_obj(v, filenames=filenames)
        return out
    if isinstance(obj, (list, tuple)):
        seq = [redact_obj(v, filenames=filenames) for v in obj]
        return type(obj)(seq) if isinstance(obj, tuple) else seq
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


def _looks_like_filename_key(key: str) -> bool:
    k = str(key).lower()
    return k.endswith(("_name", "filename", "file_name")) and "agency" not in k


# ---------------------------------------------------------------- การตรวจสอบ
#: ร่องรอยของข้อผิดพลาดภายในที่ **ห้าม**ปรากฏต่อผู้ใช้
INTERNAL_ERROR_MARKERS = (
    "Traceback (most recent call last)",
    'File "',
    ", line ",
    "Exception:",
    "Error:",
    "sqlite3.",
    "openpyxl",
    "starlette",
    "fastapi",
    "site-packages",
)


def find_absolute_paths(text) -> list[str]:
    """คืนเส้นทางสัมบูรณ์ทุกเส้นที่ยังหลงเหลืออยู่ — ใช้ในเทสต์และการตรวจก่อนส่งออก

    🔴 **ใช้รูปแบบเดียวกับ :func:`redact_text` โดยเจตนา** — ถ้าตัวตรวจกับตัวกลบ
    เห็นขอบเขตไม่ตรงกัน ตัวตรวจจะรายงานว่าสะอาดทั้งที่ยังเหลือ ซึ่งเป็นข้อบกพร่อง
    ที่รอบนี้แก้ · การเปลี่ยนรูปแบบข้างใดข้างหนึ่งอย่างเดียวจะเปิดช่องนั้นซ้ำ
    """
    if not text:
        return []
    return [m.group(0) for m in _PATH.finditer(str(text))]


def assert_shareable(payload, *, where: str = "payload") -> None:
    """ยกข้อผิดพลาดถ้ายังมีเส้นทางสัมบูรณ์หลงเหลือ

    ใช้เป็นด่านสุดท้ายก่อนเขียนแฟ้มที่ตั้งใจจะส่งให้คนอื่น
    🔴 เจตนาให้ **ล้มดัง ๆ** ดีกว่าปล่อยแฟ้มที่มีชื่อบัญชีผู้ใช้ออกไปเงียบ ๆ
    """
    import json as _json

    text = payload if isinstance(payload, str) else _json.dumps(
        payload, ensure_ascii=False, default=str)
    leaks = find_absolute_paths(text)
    if leaks:
        raise ValueError(
            f"{where} ยังมีเส้นทางสัมบูรณ์ {len(leaks)} จุด — "
            f"ห้ามส่งออก (ตัวอย่างแรกถูกกลบแล้วเพื่อไม่ให้รั่วซ้ำใน error): "
            f"{redact_path(leaks[0])}"
        )
