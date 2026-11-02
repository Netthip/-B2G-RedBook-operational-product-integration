# -*- coding: utf-8 -*-
"""ด่านตรวจก่อนส่งออก (preflight) — **ด่านจริง ไม่ใช่คำเตือนบนหน้าจอ**

คำสั่งกิ๊ฟ 23 ก.ย. 2569:
    *"ส่งออกไม่ได้เมื่อมีรายการค้าง ยอดไม่ลง หรือ UNMAPPED ที่ยังไม่รับทราบ"*
    และ *"มีหน้าบอกเหตุผลและทางแก้เมื่อ Preflight ไม่ผ่าน"*

หลักการ

* **ทุกด่านคำนวณจากของจริงทุกครั้ง** — เหมือน
  :func:`redbook.services.t1b.readiness_of` ไม่มีที่เก็บสถานะ "ผ่านแล้ว"
  ไม่มีปุ่มข้ามด่าน · สิ่งเดียวที่ผู้ใช้ *บันทึก* ได้คือ **การรับทราบ**
  รายการที่ระบบอ่านไม่ครบ ซึ่งผูกกับชุดรายการนั้นด้วยแฮช
* **ด่านต้องบังคับที่ฝั่งเซิร์ฟเวอร์** — ปุ่มที่กดไม่ได้บนหน้าจอไม่ใช่ด่าน
  route ที่เขียนไฟล์ต้องเรียก :func:`evaluate` ซ้ำก่อนเขียนเสมอ
* **ทุกด่านที่ไม่ผ่านต้องบอกทางแก้** — ด่านที่บอกแต่ว่า "ไม่ผ่าน"
  ผลักภาระให้ผู้ใช้เดา และคนจะหาทางอ้อมแทนที่จะแก้ต้นเหตุ

🔴 ชั้นนี้ **ห้าม import fastapi/jinja2** และห้ามเขียนอะไรลงฐานข้อมูล
"""
from __future__ import annotations

from dataclasses import dataclass

from .t1b import F_UNMAPPED, VERDICT_COMPARED, VERDICT_LABELS

PREFLIGHT_SERVICE_VERSION = "t1b-preflight-0.1.0"

# ---------------------------------------------------------------- รหัสของด่าน
#: ยังมีรายการที่ยังไม่ได้ตัดสิน
GATE_PENDING = "PENDING_DECISIONS"
#: ตารางกระทบยอดบวกกลับไม่ได้
GATE_RECONCILE = "RECONCILE_UNBALANCED"
#: มีรายการที่เครื่องยนต์อ่านไม่ครบ และยังไม่มีใครรับทราบชุดนั้น
GATE_UNMAPPED = "UNMAPPED_NOT_ACKNOWLEDGED"
#: ยังยืนยันไม่ได้ว่าสองแฟ้มเป็นหน่วยงานเดียวกัน
GATE_IDENTITY = "IDENTITY_NOT_CONFIRMED"
#: ไม่มีรายการใดที่จะส่งออก
GATE_EMPTY = "NOTHING_TO_EXPORT"

#: ลำดับการแสดงผล — เรียงตามลำดับที่ผู้ใช้ควรไล่แก้
GATE_ORDER = (GATE_IDENTITY, GATE_UNMAPPED, GATE_PENDING, GATE_RECONCILE,
              GATE_EMPTY)


@dataclass(frozen=True)
class Gate:
    """หนึ่งด่าน — ผ่านหรือไม่ผ่าน พร้อมเหตุผลและทางแก้ที่ทำตามได้จริง"""

    code: str
    #: ชื่อด่านบนหน้าจอ — ภาษาคนทำงบ ไม่ใช่รหัสของระบบ
    label: str
    ok: bool
    #: สิ่งที่พบจริง ณ ตอนนี้ (มีตัวเลขเสมอเมื่อมีตัวเลขให้บอก)
    detail: str = ""
    #: ทำอะไรต่อจึงจะผ่าน
    how_to_fix: str = ""
    #: ลิงก์ไปหน้าที่แก้เรื่องนี้ได้ — ว่างได้เมื่อแก้ในหน้าเดียวกัน
    href: str = ""
    #: ข้อความบนปุ่มของลิงก์นั้น
    action_label: str = ""


@dataclass(frozen=True)
class Preflight:
    """ผลการตรวจก่อนส่งออกทั้งชุด"""

    run_id: str
    gates: tuple[Gate, ...]
    #: จำนวนรายการที่ระบบอ่านไม่ครบในรอบนี้
    unmapped_count: int = 0
    #: แฮชของชุดรายการที่ต้องรับทราบ ณ ตอนนี้
    unmapped_scope: str = ""
    #: แถวการรับทราบที่ตรงกับชุดปัจจุบัน (ถ้ามี)
    ack: dict | None = None
    #: จำนวนรายการที่จะออกไปในไฟล์
    export_count: int = 0

    @property
    def ok(self) -> bool:
        return all(g.ok for g in self.gates)

    @property
    def blocking(self) -> tuple[Gate, ...]:
        return tuple(g for g in self.gates if not g.ok)

    @property
    def blocking_count(self) -> int:
        return len(self.blocking)

    @property
    def passed(self) -> tuple[Gate, ...]:
        return tuple(g for g in self.gates if g.ok)

    def gate(self, code: str) -> Gate | None:
        """หยิบด่านเดียวตามรหัส — ให้เทมเพลตไม่ต้องรู้ลำดับของด่าน"""
        for g in self.gates:
            if g.code == code:
                return g
        return None


#: ข้อความที่แสดงเมื่อ route ปฏิเสธการส่งออก — ใช้ที่เดียวทั้งระบบ
BLOCKED_NOTICE = (
    "ยังส่งออกไม่ได้ — มีเงื่อนไขที่ต้องเคลียร์ก่อน "
    "ระบบไม่เขียนไฟล์ใดเลยเมื่อด่านยังไม่ผ่าน"
)


def unmapped_ids(view) -> tuple[str, ...]:
    """รหัสรายการที่เครื่องยนต์อ่านไม่ครบ — เรียงแล้วเพื่อให้แฮชคงที่

    🔴 ``UNMAPPED`` ไม่ได้แปลว่า "ไม่มีความต่าง" แต่แปลว่า
    **ระบบอ่านแถวนั้นไม่ครบ** จึงยังไม่รู้ว่ามีความต่างหรือไม่
    """
    return tuple(sorted(f.finding_id for f in view.findings
                        if f.finding_type == F_UNMAPPED))


def evaluate(view, counts, bundle, *, ack: dict | None = None,
             unmapped_scope: str = "") -> Preflight:
    """ประเมินทุกด่านของรอบหนึ่ง — **ฟังก์ชันบริสุทธิ์**

    ``view``            projection ของรอบ (:class:`~redbook.services.t1b.T1BRunView`)
    ``counts``          ผลนับจาก :func:`redbook.services.review.counts`
    ``bundle``          ชุดส่งออกจาก :func:`redbook.services.export.build`
    ``ack``             แถวการรับทราบที่ **ตรงกับชุดปัจจุบันแล้ว** หรือ ``None``
    ``unmapped_scope``  แฮชของชุดปัจจุบัน (ผู้เรียกคำนวณจากที่เก็บ)
    """
    s = view.summary
    rec = view.reconciliation
    ids = unmapped_ids(view)
    total = int(getattr(counts, "total", 0))
    pending = int(getattr(counts, "pending", 0))
    export_count = int(getattr(bundle, "count", 0))
    gates: dict[str, Gate] = {}

    # ---------------------------------------------- ด่านตัวตนหน่วยงาน
    identity_ok = (not s.identity_gate_blocked
                   and s.identity_verdict == VERDICT_COMPARED)
    gates[GATE_IDENTITY] = Gate(
        code=GATE_IDENTITY, ok=identity_ok,
        label="สองแฟ้มเป็นหน่วยงานเดียวกัน",
        detail=(VERDICT_LABELS.get(s.identity_verdict, s.identity_verdict)
                if not identity_ok else
                "ยืนยันจากเนื้อในแฟ้มแล้วว่าเป็นหน่วยงานเดียวกัน"),
        how_to_fix=(
            "ตรวจว่าไฟล์ฝั่ง A และฝั่ง B เป็นของหน่วยงานเดียวกันจริง "
            "ถ้าใส่ไฟล์สลับหน่วยงาน ให้กลับไปที่งานตรวจแล้วใส่ไฟล์ใหม่ "
            "ถ้าแฟ้มไม่มีชีตปกให้ระบบอ่านชื่อหน่วยงาน ระบบจะยืนยันให้ไม่ได้ "
            "และไม่ควรส่งออกผลจากรอบนี้"
        ),
        action_label="เปิดหน้าสรุปรอบตรวจ",
        href="/t1b/runs/" + s.run_id,
    )

    # ------------------------------------- ด่านรายการที่ระบบอ่านไม่ครบ
    if not ids:
        unmapped_detail = "ไม่มีรายการที่ระบบอ่านไม่ครบในรอบนี้"
    elif ack:
        unmapped_detail = (
            "รับทราบแล้ว %d รายการ โดย %s เมื่อ %s"
            % (len(ids), ack.get("acknowledged_by", ""), ack.get("created_at", ""))
        )
    else:
        unmapped_detail = (
            "มี %d รายการที่ระบบอ่านไม่ครบ และยังไม่มีการรับทราบ" % len(ids)
        )
    gates[GATE_UNMAPPED] = Gate(
        code=GATE_UNMAPPED, ok=(not ids or ack is not None),
        label="รับทราบรายการที่ระบบอ่านไม่ครบแล้ว",
        detail=unmapped_detail,
        how_to_fix=(
            "เปิดคิวพิจารณาแล้วกรองเฉพาะชนิด ระบบอ่านแถวนี้ไม่ครบ เพื่อดูว่าระบบ "
            "อ่านส่วนใดไม่ครบ จากนั้นกลับมาที่หน้านี้แล้วกดรับทราบ — "
            "การรับทราบผูกกับชุดรายการชุดนี้เท่านั้น ถ้ารันใหม่หรือรายการเปลี่ยน "
            "ต้องอ่านและรับทราบใหม่"
        ),
        action_label="ดูรายการที่ระบบอ่านไม่ครบ",
        href="/t1b/runs/%s/queue?ftype=%s" % (s.run_id, F_UNMAPPED),
    )

    # ---------------------------------------------------- ด่านรายการค้าง
    gates[GATE_PENDING] = Gate(
        code=GATE_PENDING, ok=pending == 0,
        label="ตัดสินครบทุกรายการแล้ว",
        detail=("เหลือ %d รายการที่ยังไม่ได้ตัดสิน" % pending if pending else
                "ตัดสินครบแล้วทั้ง %d รายการ" % total),
        how_to_fix=(
            "เปิดคิวพิจารณาแล้วกรองสถานะ ยังไม่ตัดสิน "
            "ตัดสินทีละรายการ หรือใช้การตัดสินแบบกลุ่มเมื่อเหตุผลเดียวกันทั้งชุด"
        ),
        action_label="ไปที่คิวพิจารณา",
        href="/t1b/runs/%s/queue?status=PENDING" % s.run_id,
    )

    # ----------------------------------------------------- ด่านยอดกระทบ
    gates[GATE_RECONCILE] = Gate(
        code=GATE_RECONCILE, ok=rec.balanced,
        label="ยอดข้อสังเกตกระทบกันลงตัว",
        detail=("ตารางกระทบยอดรวมได้ %d รายการ ตรงกับยอดที่รอบนี้ประกาศไว้ %d รายการ"
                % (rec.total, rec.declared_total) if rec.balanced else
                "ตารางกระทบยอดรวมได้ %d รายการ แต่รอบนี้ประกาศไว้ %d รายการ — ต่างกัน %d รายการ"
                % (rec.total, rec.declared_total,
                   abs(rec.total - rec.declared_total))),
        how_to_fix=(
            "ยอดไม่ลงตัวแปลว่าชุดข้อสังเกตที่หน้าจออ่านอยู่ กับยอดที่บันทึกไว้ "
            "ตอนรัน ไม่ใช่ชุดเดียวกัน — อย่าส่งออกจากรอบนี้ "
            "ให้กลับไปที่งานตรวจแล้วสั่งวิเคราะห์ใหม่เพื่อสร้างรอบใหม่ "
            "และแจ้งผู้ดูแลระบบพร้อมรหัสรอบตรวจนี้"
        ),
        action_label="เปิดหน้าสรุปรอบตรวจ",
        href="/t1b/runs/" + s.run_id,
    )

    # ------------------------------------------- ด่านมีของให้ส่งออกจริง
    gates[GATE_EMPTY] = Gate(
        code=GATE_EMPTY, ok=export_count > 0,
        label="มีรายการที่ยืนยันให้ส่งออก",
        detail=("พร้อมส่งออก %d รายการ" % export_count if export_count else
                "ไม่มีรายการใดที่สถานะล่าสุดเป็นการยืนยัน จึงไม่มีอะไรให้ส่งออก"),
        how_to_fix=(
            "ชุดส่งออกมีเฉพาะรายการที่สถานะล่าสุดเป็น "
            "ยืนยันว่าเป็นจุดที่ต้องแก้ หรือ ยืนยันโดยแก้ไขข้อเสนอ "
            "ถ้าไม่มีรายการใดอยู่ในสองสถานะนี้ แปลว่ายังไม่มีอะไรต้องส่งต่อ"
        ),
        action_label="ไปที่คิวพิจารณา",
        href="/t1b/runs/%s/queue" % s.run_id,
    )

    return Preflight(
        run_id=s.run_id,
        gates=tuple(gates[c] for c in GATE_ORDER),
        unmapped_count=len(ids), unmapped_scope=unmapped_scope,
        ack=ack, export_count=export_count,
    )


__all__ = [
    "PREFLIGHT_SERVICE_VERSION", "BLOCKED_NOTICE", "Gate", "Preflight",
    "GATE_ORDER", "GATE_PENDING", "GATE_RECONCILE", "GATE_UNMAPPED",
    "GATE_IDENTITY", "GATE_EMPTY", "evaluate", "unmapped_ids",
]
