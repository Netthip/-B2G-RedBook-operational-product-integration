"""สุ่มชุดประเมินสุดท้ายแบบแบ่งชั้น (#22) — ตาม FINAL_EVAL_PROTOCOL 1.0.1 §4

0.2.0 (โปรโตคอล 1.0.1): stratum `TYPE_UNVERIFIED` — ผู้ผ่านเกณฑ์ที่ยืนยันประเภทไม่ได้แม้หน่วยเดียว
⇒ หยุดก่อนสุ่ม รายงานจำนวน · ห้ามย้ายเข้า S-GOV/S-PO เพื่อให้ชั้นลงตัว (คำตัดสิน Bo ข้อ 6)

ใช้:
  python final_eval_draw.py --self-test
  python final_eval_draw.py --seed-from <ไฟล์โปรโตคอลที่ตรึง> --candidates <csv นอก repo สาธารณะ> [--target 3]

เครื่องมือนี้ **ไม่เปิดไฟล์เอกสารงบประมาณใด ๆ** — อ่านเฉพาะ csv ของผู้สมัครที่ผ่านการคัดด้วย metadata
แล้ว (คอลัมน์ `unit_id,stratum,eligible`) · ผลลัพธ์พิมพ์ทาง stdout เพื่อให้ผู้รันบันทึกนอก repo สาธารณะ

วิธี (ตรึงใน §4 ของโปรโตคอล — แก้ตรงนี้ = ต้องขึ้นรุ่นโปรโตคอล):
  seed        = 16 หลักแรก (hex) ของ SHA-256 ของไบต์ไฟล์โปรโตคอลที่ตรึง (ปลายบรรทัดเป็น LF = blob ใน git)
  อันดับในชั้น = เรียงจาก SHA-256("<seed>|<stratum>|<unit_id>") น้อยไปมาก
  จัดสรร      = n = min(target, จำนวนผู้ผ่าน) · ชั้นที่มีผู้ผ่านได้ 1 ที่ก่อน (ถ้า n ไม่พอ ให้ชั้นตามลำดับ STRATA)
                · ที่เหลือให้ทีละที่แก่ชั้นที่ยังเหลือผู้ผ่านมากที่สุด (เสมอ ⇒ ตามลำดับ STRATA)
  หยุด        = ผู้ผ่านมี TYPE_UNVERIFIED ⇒ ไม่สุ่ม · ผู้ผ่าน < 2 ⇒ ไม่สุ่ม · ส่งกลับ Bo/Gift (ห้ามลดเกณฑ์)
ไม่ใช้ `random` ของ Python เพื่อให้ผลไม่ขึ้นกับรุ่นของ interpreter และตรวจด้วยมือได้
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

TOOL_VERSION = "final-eval-draw-0.2.0"
STRATA = ("S-GOV", "S-PO")  # ลำดับนี้ใช้ตัดสินเมื่อเสมอ — ตรึงใน §4.2
UNVERIFIED = "TYPE_UNVERIFIED"
MIN_UNITS = 2
CRLF, LF = bytes([13, 10]), bytes([10])


class DrawStop(Exception):
    """เงื่อนไขหยุดที่ประกาศล่วงหน้า — ห้ามแก้ด้วยการลดเกณฑ์"""


def seed_from_protocol(data: bytes) -> str:
    """ปลายบรรทัดแปลงเป็น LF ก่อน ⇒ ตรงกับไบต์ของ blob ใน git ไม่ว่าเช็กเอาต์บนระบบใด"""
    return hashlib.sha256(data.replace(CRLF, LF)).hexdigest()[:16]


def rank_key(seed: str, stratum: str, unit_id: str) -> str:
    return hashlib.sha256(f"{seed}|{stratum}|{unit_id}".encode("utf-8")).hexdigest()


def allocate(counts: dict[str, int], target: int) -> dict[str, int]:
    total = sum(counts.values())
    if total < MIN_UNITS:
        raise DrawStop(f"ผู้ผ่านเกณฑ์ {total} หน่วย < {MIN_UNITS} — ไม่สุ่ม ส่งกลับกิ๊ฟ")
    n = min(target, total)
    alloc = {s: 0 for s in STRATA}
    for s in STRATA:
        if n == 0:
            break
        if counts.get(s, 0) > 0:
            alloc[s] = 1
            n -= 1
    while n > 0:
        best = max(STRATA, key=lambda s: (counts.get(s, 0) - alloc[s], -STRATA.index(s)))
        if counts.get(best, 0) - alloc[best] <= 0:
            break
        alloc[best] += 1
        n -= 1
    return alloc


def draw(rows: list[dict], seed: str, target: int) -> dict:
    seen: set[str] = set()
    pool: dict[str, list[str]] = {s: [] for s in STRATA}
    for r in rows:
        uid, st, el = r["unit_id"].strip(), r["stratum"].strip(), r["eligible"].strip().lower()
        if uid in seen:
            raise ValueError(f"unit_id ซ้ำ: {uid}")
        seen.add(uid)
        if st not in STRATA and st != UNVERIFIED:
            raise ValueError(f"stratum ไม่รู้จัก '{st}' (ต้องเป็น {STRATA} หรือ {UNVERIFIED})")
        if el not in ("true", "false"):
            raise ValueError(f"eligible ต้องเป็น true/false: {uid}")
        if el == "true":
            pool.setdefault(st, []).append(uid)
    unverified = len(pool.pop(UNVERIFIED, []))
    if unverified:
        raise DrawStop(f"ผู้ผ่านเกณฑ์ที่ยืนยันประเภทไม่ได้ {unverified} หน่วย — ไม่สุ่ม · ห้ามย้ายเข้าชั้นอื่น")
    counts = {s: len(v) for s, v in pool.items()}
    alloc = allocate(counts, target)
    ranked = {s: sorted(v, key=lambda u, s=s: rank_key(seed, s, u)) for s, v in pool.items()}
    return {
        "tool_version": TOOL_VERSION,
        "seed": seed,
        "candidates_total": len(rows),
        "eligible_by_stratum": counts,
        "allocation": alloc,
        "selected": {s: ranked[s][: alloc[s]] for s in STRATA},
        # ลำดับสำรอง ใช้เฉพาะการแทนที่ตาม §4.4 (ล้มทางเทคนิคก่อนเริ่มทำเฉลย) เท่านั้น
        "reserve_order": {s: ranked[s][alloc[s]:] for s in STRATA},
    }


def _self_test() -> int:
    seed = seed_from_protocol(b"synthetic protocol")
    assert seed == hashlib.sha256(b"synthetic protocol").hexdigest()[:16]
    rows = [{"unit_id": f"U{i:02d}", "stratum": "S-GOV" if i < 10 else "S-PO", "eligible": "true"} for i in range(13)]
    a = draw(rows, seed, 3)
    assert a["allocation"] == {"S-GOV": 2, "S-PO": 1}, a["allocation"]
    assert draw(list(reversed(rows)), seed, 3)["selected"] == a["selected"], "ผลต้องไม่ขึ้นกับลำดับแถว"
    # ปลายบรรทัด CRLF/LF ต้องได้ seed เดียวกัน (สำเนา Windows vs blob ใน git)
    assert seed_from_protocol(b"a" + CRLF + b"b" + LF) == seed_from_protocol(b"a" + LF + b"b" + LF)
    # ชั้นเดียวมีผู้ผ่าน ⇒ ทั้งหมดจากชั้นนั้น ไม่ดึงข้ามชั้น
    only = [dict(r, eligible="true" if r["stratum"] == "S-GOV" else "false") for r in rows]
    assert draw(only, seed, 3)["allocation"] == {"S-GOV": 3, "S-PO": 0}
    # ผ่านสองหน่วย ⇒ ใช้ 2 (ไม่ลดเกณฑ์ ไม่เติม)
    two = [dict(r, eligible="true" if r["unit_id"] in ("U01", "U11") else "false") for r in rows]
    assert draw(two, seed, 3)["allocation"] == {"S-GOV": 1, "S-PO": 1}
    # ผ่านหนึ่งหน่วย ⇒ หยุด
    one = [dict(r, eligible="true" if r["unit_id"] == "U01" else "false") for r in rows]
    try:
        draw(one, seed, 3)
        raise AssertionError("ต้องหยุดเมื่อผู้ผ่าน < 2")
    except DrawStop:
        pass
    for bad in ([{"unit_id": "U1", "stratum": "S-GOV", "eligible": "true"}] * 2,
                [{"unit_id": "U1", "stratum": "X", "eligible": "true"}],
                [{"unit_id": "U1", "stratum": "S-GOV", "eligible": "yes"}]):
        try:
            draw(bad, seed, 3)
            raise AssertionError(f"ต้องล้มดัง ๆ: {bad}")
        except ValueError:
            pass
    # ผู้ผ่านที่ยืนยันประเภทไม่ได้แม้หน่วยเดียว ⇒ หยุด (ไม่ทิ้งเงียบ ๆ ไม่ย้ายชั้น)
    unv = rows + [{"unit_id": "U99", "stratum": UNVERIFIED, "eligible": "true"}]
    try:
        draw(unv, seed, 3)
        raise AssertionError("ต้องหยุดเมื่อมีผู้ผ่านที่เป็น TYPE_UNVERIFIED")
    except DrawStop:
        pass
    # TYPE_UNVERIFIED ที่ไม่ผ่านเกณฑ์อยู่แล้ว ไม่กระทบผล
    unv_ok = rows + [{"unit_id": "U99", "stratum": UNVERIFIED, "eligible": "false"}]
    assert draw(unv_ok, seed, 3)["selected"] == a["selected"]
    print(f"{TOOL_VERSION} self-test: 9/9 ผ่าน (ข้อมูลสังเคราะห์เท่านั้น)")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--seed-from", type=Path)
    p.add_argument("--candidates", type=Path)
    p.add_argument("--target", type=int, default=3)
    a = p.parse_args()
    if a.self_test:
        return _self_test()
    if not (a.seed_from and a.candidates):
        p.error("ต้องระบุ --seed-from และ --candidates")
    seed = seed_from_protocol(a.seed_from.read_bytes())
    with a.candidates.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    try:
        res = draw(rows, seed, a.target)
    except DrawStop as e:
        print(f"STOP: {e}")
        return 3
    for k, v in res.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
