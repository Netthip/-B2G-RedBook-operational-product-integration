# -*- coding: utf-8 -*-
"""ขอบเขตของการกลบเส้นทาง — ปิดช่อง **false assurance** ที่ Bo ชี้

🔴 `BO REVIEW COMPLETE — HANDOFFS A/B/C/D (consolidated)` · หัวข้อ B —
*"`redact_text()` ใช้ regex ที่หยุดเมื่อเจอช่องว่าง … แม้
`find_absolute_paths()` จะรายงานว่าไม่เหลือ absolute path แล้ว
**นี่คือ false assurance ของ privacy test**"*

**อาการที่วัดได้จริงบน `c7cfaf4`**

```
IN : C:\\Users\\<user>\\OneDrive\\เรียน ป.โท\\Project\\…\\ลับ.xlsx
OUT: <HOME>/OneDrive/เรียน ป.โท\\Project\\…\\ลับ.xlsx
find_absolute_paths(OUT) -> []      ← รายงานว่าสะอาด ทั้งที่หางยังอยู่
```

ชื่อบัญชีผู้ใช้หายจริง แต่โครงสร้างโฟลเดอร์และ **ชื่อไฟล์** ยังอยู่ครบ
และเพราะ detector ใช้ regex ตัวเดียวกับ redactor เทสต์ชุดเดิมจึงผ่านหมด
🔴 **การที่เทสต์ผ่านคือส่วนหนึ่งของข้อบกพร่อง ไม่ใช่หลักฐานว่าไม่มีข้อบกพร่อง**

**ขอบเขตที่ประกาศไว้หลังแก้** (ตามที่ Bo กำหนด)

1. อยู่ในเครื่องหมายคำพูด ⇒ กลบถึง **เครื่องหมายปิด**
2. ไม่มีเครื่องหมายคำพูด และมี **นามสกุลไฟล์** ⇒ กลบถึงนามสกุล
3. ไม่มีทั้งสองอย่าง ⇒ กลบถึง **จบบรรทัด**
   — ยอมรับว่าอาจกลบข้อความท้ายบรรทัดเกินไปบ้าง · **กลบเกินปลอดภัยกว่ากลบขาด**

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import pytest

from redbook import privacy

#: ชิ้นส่วนที่ **ห้ามเหลือ** ในผลลัพธ์ — ใช้เป็นตัวชี้วัดตรง ๆ
#: ไม่พึ่ง ``find_absolute_paths`` เพราะตัวมันเองคือส่วนหนึ่งของข้อบกพร่อง
SECRET_USER = "someone"
SECRET_DIR = "โฟลเดอร์ลับ"
SECRET_FILE = "งบลับ.xlsx"

ONEDRIVE = (
    rf"C:\Users\{SECRET_USER}\OneDrive\เรียน ป.โท\{SECRET_DIR}"
    rf"\Budget Intelligence System\{SECRET_FILE}"
)


def _assert_nothing_secret_remains(out: str, *, where: str = ""):
    """🔴 ตัวชี้วัดที่ไม่พึ่ง detector ของตัวเอง"""
    for secret in (SECRET_USER, SECRET_DIR, SECRET_FILE):
        assert secret not in out, f"{where} ยังเหลือ {secret!r} ใน {out!r}"


# ══════════════════════════════════════════════════════════════════════════════
#  BD1 — เส้นทางที่มีช่องว่างในชื่อโฟลเดอร์
# ══════════════════════════════════════════════════════════════════════════════


def test_bd1_onedrive_style_path_leaves_no_tail():
    """🔴 หัวใจของข้อบกพร่อง — path จริงของเครื่องนี้มีช่องว่างในชื่อโฟลเดอร์"""
    out = privacy.redact_text(ONEDRIVE)
    _assert_nothing_secret_remains(out, where="redact_text")


def test_bd2_detector_agrees_with_the_redactor():
    """detector กับ redactor ต้องเห็นขอบเขตเดียวกัน มิฉะนั้นได้ false assurance"""
    out = privacy.redact_text(ONEDRIVE)
    assert privacy.find_absolute_paths(out) == [], out
    _assert_nothing_secret_remains(out, where="หลัง detector บอกว่าสะอาด")


def test_bd3_assert_shareable_is_not_fooled_by_a_half_redacted_path():
    """🔴 ด่านสุดท้ายต้องไม่ปล่อยผ่านของที่กลบเพียงครึ่งเดียว"""
    half = privacy.redact_text(ONEDRIVE)
    privacy.assert_shareable(half, where="ทดสอบ")   # ต้องผ่าน **เพราะสะอาดจริง**
    _assert_nothing_secret_remains(half, where="assert_shareable ผ่านแล้ว")


def test_bd4_redaction_is_idempotent():
    once = privacy.redact_text(ONEDRIVE)
    assert privacy.redact_text(once) == once


@pytest.mark.parametrize("raw", [
    rf"D:\งานราชการ\{SECRET_DIR}\{SECRET_FILE}",
    rf"\\fileserver\แผนก งบประมาณ\{SECRET_DIR}\{SECRET_FILE}",
    rf"/home/{SECRET_USER}/เอกสาร ราชการ/{SECRET_DIR}/{SECRET_FILE}",
    rf"/Users/{SECRET_USER}/My Documents/{SECRET_DIR}/{SECRET_FILE}",
])
def test_bd5_every_path_flavour_with_spaces_is_fully_redacted(raw):
    out = privacy.redact_text(raw)
    _assert_nothing_secret_remains(out, where=raw[:24])
    assert privacy.find_absolute_paths(out) == []


# ══════════════════════════════════════════════════════════════════════════════
#  BD2 — เส้นทางในเครื่องหมายคำพูด
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("quote", ['"', "'", "`"])
def test_bd10_quoted_path_is_redacted_to_the_closing_quote(quote):
    line = f"เปิดแฟ้ม {quote}{ONEDRIVE}{quote} ไม่สำเร็จ"
    out = privacy.redact_text(line)
    _assert_nothing_secret_remains(out, where=f"quoted {quote}")
    assert "ไม่สำเร็จ" in out, "ข้อความหลังเครื่องหมายปิดต้องไม่ถูกกลบไปด้วย"


def test_bd11_text_after_an_unquoted_path_with_extension_survives():
    """มีนามสกุล ⇒ ขอบชัด ⇒ ข้อความท้ายบรรทัดต้องอยู่ครบ"""
    line = f"อ่านจาก {ONEDRIVE} แล้วพบข้อผิดพลาด"
    out = privacy.redact_text(line)
    _assert_nothing_secret_remains(out, where="unquoted + extension")
    assert "แล้วพบข้อผิดพลาด" in out


def test_bd12_path_without_an_extension_is_redacted_to_end_of_line():
    """ไม่มีนามสกุลและไม่มีเครื่องหมายคำพูด ⇒ กลบถึงจบบรรทัด

    🔴 ยอมกลบเกิน · การกลบขาดคือการรั่ว การกลบเกินคือข้อความอ่านยากขึ้น
    """
    line = rf"ทำงานที่ C:\Users\{SECRET_USER}\{SECRET_DIR}"
    out = privacy.redact_text(line)
    _assert_nothing_secret_remains(out, where="no extension")


def test_bd13_multiple_paths_on_one_line_are_all_redacted():
    line = (f'สำรอง "{ONEDRIVE}" ไปที่ '
            rf"\\srv01\คลัง เอกสาร\{SECRET_DIR}\{SECRET_FILE}")
    out = privacy.redact_text(line)
    _assert_nothing_secret_remains(out, where="สองเส้นทางในบรรทัดเดียว")
    assert "srv01" not in out


def test_bd14_newline_is_always_a_boundary():
    """🔴 การกลบต้องไม่กลืนบรรทัดถัดไป มิฉะนั้นล็อกทั้งไฟล์หายเป็นก้อน"""
    text = f"บรรทัดหนึ่ง {ONEDRIVE}\nบรรทัดสองต้องอยู่ครบ"
    out = privacy.redact_text(text)
    _assert_nothing_secret_remains(out, where="หลายบรรทัด")
    assert "บรรทัดสองต้องอยู่ครบ" in out


# ══════════════════════════════════════════════════════════════════════════════
#  BD3 — ต้องไม่กลบสิ่งที่ไม่ใช่เส้นทาง
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("safe", [
    "อัตราส่วน 3/4 ของยอดรวม",
    "ปีงบประมาณ 2569/2570",
    "หมวด 7.2 แผนงานพื้นฐาน",
    "เวลา 10:28:44 น.",
    "รวมทั้งสิ้น 1,234.5678 ล้านบาท",
    "docs/DATA_FLOW_AND_RETENTION.md",
])
def test_bd20_ordinary_text_is_untouched(safe):
    assert privacy.redact_text(safe) == safe
    assert privacy.find_absolute_paths(safe) == []


def test_bd21_relative_paths_stay_readable():
    assert privacy.redact_path("redbook/services/t1b.py") == "redbook/services/t1b.py"


# ══════════════════════════════════════════════════════════════════════════════
#  BD4 — จุดยึดที่เก็บส่วนท้ายได้ กับที่เก็บไม่ได้
# ══════════════════════════════════════════════════════════════════════════════


def test_bd30_home_relative_path_keeps_no_tail_in_free_text():
    """🔴 ใต้โฮมของผู้ใช้คือของส่วนตัวทั้งหมด

    เดิม ``<HOME>`` ถูกนับเป็นจุดยึดที่เก็บส่วนท้ายได้ ⇒ ชื่อบัญชีผู้ใช้หายจริง
    แต่โครงสร้างโฟลเดอร์และ **ชื่อแฟ้ม** ยังอยู่ครบ ซึ่งเป็นข้อบกพร่องตระกูลเดียว
    กับที่รอบนี้แก้ · ตอนนี้เหลือเพียงป้ายเดียวไม่มีส่วนท้าย
    """
    from pathlib import Path

    raw = str(Path.home() / "OneDrive" / "เรียน ป.โท" / SECRET_DIR / SECRET_FILE)
    out = privacy.redact_text(raw)
    _assert_nothing_secret_remains(out, where="home-relative")
    assert "OneDrive" not in out, out


def test_bd31_system_anchors_still_keep_their_tail():
    """โฟลเดอร์ของระบบเองยังเก็บส่วนท้ายไว้ให้ตรวจปัญหาได้"""
    from redbook import config

    out = privacy.redact_text(str(config.UPLOAD_DIR / "ab12cd34.xlsx"))
    assert out == "<DATA_DIR>/uploads/ab12cd34.xlsx"
