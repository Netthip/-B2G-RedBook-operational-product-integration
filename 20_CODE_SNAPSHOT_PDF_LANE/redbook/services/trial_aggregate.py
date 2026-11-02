"""ตัวรวมผลตามวิธีวัดผลฉบับ 0.3 ร่าง ๒ (``05_experiment_design/RESULT_SCHEMA_R3_0.3.md``)

รับ**จำนวน**จากแต่ละรอบ (สรุปจำนวนของหน้าผู้ตรวจ) แล้วคำนวณค่าที่ประกาศล่วงหน้า — สัดส่วนคำนวณทีหลังเสมอ ·
ตัวหาร 0 = ``None`` + ``denominator_zero`` (ห้ามเป็น 0) · ตัวหาร < 10 = ไม่ส่งร้อยละ (``denominator_lt_10``) ·
ห้ามรวมข้ามชนิดคู่หรือข้ามชุด (พัฒนา/ประเมิน) · บัญชี F ไม่ปิด = :class:`AggregateError` (ห้ามรายงานสัดส่วนใด)
"""
from __future__ import annotations

import math

AGG_VERSION = "trial-aggregate-0.3.1"
MISS_CODES = ("p1", "p2", "p3", "p4", "p5")
LOCATION_STATUSES = ("undecidable", "no_box", "all_sides", "some_sides", "adjacent", "wrong")
GROUPS = ("matched", "s1", "s2", "s3", "s4")
JUDGE4 = ("full", "partial", "none", "undecidable")
LEVELS_B2 = ((4.50, "มากที่สุด"), (3.50, "มาก"), (2.50, "ปานกลาง"), (1.50, "น้อย"))


class AggregateError(ValueError):
    """ข้อมูลไม่สอดคล้อง — ห้ามรายงานสัดส่วนใด ต้องหาต้นเหตุก่อน"""


def rate(num: int, den: int) -> dict:
    """ตัวตั้ง/ตัวหารเสมอ · ร้อยละเฉพาะตัวหาร ≥ 10 · ตัวหาร 0 = คำนวณไม่ได้"""
    if den <= 0:
        return {"num": num, "den": den, "value": None, "pct": None, "reason": "denominator_zero",
                "text": "คำนวณไม่ได้"}
    value = num / den
    if den < 10:
        return {"num": num, "den": den, "value": value, "pct": None, "reason": "denominator_lt_10",
                "text": f"{num}/{den}"}
    pct = round(100 * value, 1)
    return {"num": num, "den": den, "value": value, "pct": pct, "reason": "", "text": f"{num}/{den} ({pct}%)"}


def issues(c: dict) -> dict:
    """ฝั่งรายการอ้างอิง (A1 · H1) — ``c`` = {N0, undecidable, exact, partial, miss: {p1..p5}}"""
    miss = sum(int(c.get("miss", {}).get(k, 0)) for k in MISS_CODES)
    n0, und, exact, partial = (int(c[k]) for k in ("N0", "undecidable", "exact", "partial"))
    if exact + partial + miss + und != n0:
        raise AggregateError(f"N0 ({n0}) ≠ พบตรง + บางส่วน + พลาด + ตัดสินไม่ได้ ({exact + partial + miss + und})")
    n = n0 - und
    return {"N0": n0, "undecidable": und, "N": n, "exact": exact, "partial": partial, "miss": miss,
            "miss_codes": {k: int(c.get("miss", {}).get(k, 0)) for k in MISS_CODES},
            "H1": rate(exact, n0), "supplement": rate(exact, n), "incl_partial": rate(exact + partial, n0),
            "P": exact + partial}


def location(loc: dict, P: int | None = None) -> dict:
    """หลักฐานตำแหน่ง (A2 · H2) — ``loc`` = {สถานะ: {exact: n, partial: n}} ครบ 6 × 2"""
    grid = {s: {g: int(loc.get(s, {}).get(g, 0)) for g in ("exact", "partial")} for s in LOCATION_STATUSES}
    tot = {s: grid[s]["exact"] + grid[s]["partial"] for s in LOCATION_STATUSES}
    p = sum(tot.values())
    if P is not None and P != p:
        raise AggregateError(f"สถานะตำแหน่งรวม ({p}) ≠ P ({P})")
    out = {"grid": grid, "P": p, "undecidable": tot["undecidable"],
           "H2": rate(tot["all_sides"], p - tot["undecidable"]), "all_over_P": rate(tot["all_sides"], p)}
    for g in ("exact", "partial"):
        gp = sum(grid[s][g] for s in LOCATION_STATUSES)
        out[f"H2_{g}"] = rate(grid["all_sides"][g], gp - grid["undecidable"][g])
    return out


def observations(c: dict) -> dict:
    """ฝั่งข้อสังเกตของระบบ (A3) — ``c`` = {F, groups: {matched,s1..s4}, s3_reasons, crosstab: {fid: {ass: n}},
    crosstab_by_group: {group: {fid: {ass: n}}}}"""
    f = int(c["F"])
    g = {k: int(c.get("groups", {}).get(k, 0)) for k in GROUPS}
    if sum(g.values()) != f:
        raise AggregateError(f"F ({f}) ≠ จ + ส1 + ส2 + ส3 + ส4 ({sum(g.values())}) — ห้ามรายงาน")
    ct = {a: {b: int(c.get("crosstab", {}).get(a, {}).get(b, 0)) for b in JUDGE4} for a in JUDGE4}
    by_group = {grp: {a: {b: int(c.get("crosstab_by_group", {}).get(grp, {}).get(a, {}).get(b, 0)) for b in JUDGE4}
                      for a in JUDGE4} for grp in GROUPS}
    # บัญชีต้องปิดเอง ไม่อาศัยผู้เรียก (Bo #43 6463289837): ข้อมูลหาย/ไม่ครบ = ปฏิเสธ ห้ามกลายเป็นผลถูก 0%
    cells = [n for r in ct.values() for n in r.values()] + \
            [n for t in by_group.values() for r in t.values() for n in r.values()]
    if any(n < 0 for n in [*g.values(), *cells]):
        raise AggregateError("จำนวนติดลบในบัญชี A3 — ห้ามรายงาน")
    if sum(sum(r.values()) for r in ct.values()) != f:
        raise AggregateError(f"ตารางไขว้ A3 รวม ({sum(sum(r.values()) for r in ct.values())}) ≠ F ({f}) "
                             "— ไม่ครบทุกข้อใน U ห้ามรายงาน")
    for grp in GROUPS:
        n = sum(sum(r.values()) for r in by_group[grp].values())
        if n != g[grp]:
            raise AggregateError(f"ตารางไขว้กลุ่ม {grp} รวม ({n}) ≠ จำนวนกลุ่ม ({g[grp]}) — ห้ามรายงาน")
    if any(sum(by_group[grp][a][b] for grp in GROUPS) != ct[a][b] for a in JUDGE4 for b in JUDGE4):
        raise AggregateError("ตารางไขว้รายกลุ่มรวมกันไม่ตรงตารางไขว้ทั้งหมด — ห้ามรายงาน")
    fid = {a: sum(ct[a].values()) for a in JUDGE4}
    ass = {b: sum(ct[a][b] for a in JUDGE4) for b in JUDGE4}
    return {"F": f, "groups": g, "s3_reasons": dict(c.get("s3_reasons", {})),
            "overflag": rate(g["s3"], f - g["s4"]),
            "fidelity": fid, "assertion": ass, "crosstab": ct, "crosstab_by_group": by_group,
            "A3_fidelity": rate(fid["full"], f - fid["undecidable"]),
            "A3_assertion": rate(ass["full"], f - ass["undecidable"]),
            "read_ok_assertion_wrong": ct["full"]["none"]}


def _sd(xs: list) -> float | None:
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def b2_level(mean: float | None) -> str | None:
    """ระดับตัดสินบนค่าจริงไม่ปัด (> 4.50 มากที่สุด · > 3.50 มาก · > 2.50 ปานกลาง · > 1.50 น้อย · อื่น น้อยที่สุด)"""
    if mean is None:
        return None
    return next((label for cut, label in LEVELS_B2 if mean > cut), "น้อยที่สุด")


def aspect(rows: list) -> dict:
    """ด้านหนึ่งของแบบสอบถาม — ``rows`` = รายผู้ตอบ [คะแนนข้อ 1..k] (None = ไม่ตอบ) · ค่าเฉลี่ยรายคนก่อนรายด้าน"""
    k = max((len(r) for r in rows), default=0)
    items = []
    for i in range(k):
        xs = [r[i] for r in rows if i < len(r) and r[i] is not None]
        items.append({"n": len(xs), "missing": len(rows) - len(xs),
                      "mean": (sum(xs) / len(xs)) if xs else None, "sd": _sd(xs),
                      "freq": {v: xs.count(v) for v in (5, 4, 3, 2, 1)},
                      "median": (sorted(xs)[len(xs) // 2] if len(xs) % 2 else
                                 (sorted(xs)[len(xs) // 2 - 1] + sorted(xs)[len(xs) // 2]) / 2) if xs else None})
    person = [sum(r) / len(r) for r in rows if len(r) == k and all(x is not None for x in r)]
    mean = (sum(person) / len(person)) if person else None
    return {"items": items, "respondent_means": person, "n": len(person), "missing": len(rows) - len(person),
            "mean": mean, "sd": _sd(person), "level": b2_level(mean), "meets_H3": mean is not None and mean > 3.50}


def assertion_from_dims(dims: dict, undecidable: bool = False) -> str:
    """A3-ข ต่อข้อ — คิดเฉพาะมิติที่ไม่ใช่ N/A (N/A ไม่ทำให้ไม่ถูก และไม่ตัดข้อออกจาก U) ·
    ไม่มีความต่างจริง (real = wrong) = ไม่ถูก · ทุกมิติถูก = ถูกครบ · บางมิติผิด = ถูกบางส่วน"""
    if undecidable:
        return "undecidable"
    used = {k: v for k, v in dims.items() if v != "na"}
    if not used:
        return "undecidable"
    wrong = sum(1 for v in used.values() if v == "wrong")
    if used.get("real") == "wrong" or wrong == len(used):
        return "none"
    return "full" if wrong == 0 else "partial"


def location_errors(status: str, sides: list, search_scope: str) -> list[str]:
    """ตรวจสถานะตำแหน่งก่อนบันทึก (schema ข้อ 1.1) — คืนเหตุที่ปฏิเสธ ([] = บันทึกได้)"""
    out = []
    if status not in LOCATION_STATUSES:
        out.append("สถานะตำแหน่ง")
    if not sides or any(x not in ("A", "B") for x in sides) or len(set(sides)) != len(sides):
        out.append("ฝั่งที่เกี่ยวข้อง")
    elif len(sides) == 1 and not (search_scope or "").strip():
        out.append("ขอบเขตที่ค้นในอีกฉบับ (เพิ่ม/หายมีหลักฐานฝั่งเดียว)")
    if status == "some_sides" and len(sides) < 2:
        out.append("ถูกบางฝั่งใช้ได้เฉพาะประเด็นที่มีฝั่งที่เกี่ยวข้อง 2 ฝั่ง")
    return out


def combine(records: list) -> dict:
    """รวมจำนวนหลายคู่ — **การรวมจำนวน** (ไม่เฉลี่ยร้อยละ) · ห้ามรวมข้ามชนิดคู่หรือข้ามชุด"""
    kinds = {(r.get("pair_kind"), r.get("set")) for r in records}
    if len(kinds) > 1:
        raise AggregateError(f"ห้ามรวมข้ามชนิดคู่/ชุด: {sorted(map(str, kinds))}")

    def add(a, b):
        if isinstance(b, dict):
            return {k: add(a.get(k, 0 if not isinstance(v, dict) else {}), v) for k, v in b.items()} | \
                {k: v for k, v in a.items() if k not in b}
        return a + b
    tot: dict = {}
    for r in records:
        tot = add(tot, r.get("counts", {}))
    return tot


__all__ = ["AGG_VERSION", "AggregateError", "rate", "issues", "location", "observations", "aspect", "b2_level",
           "combine", "assertion_from_dims", "location_errors", "LOCATION_STATUSES", "JUDGE4", "GROUPS", "MISS_CODES"]
