# -*- coding: utf-8 -*-
"""เทียบข้อเท็จจริงของสองเล่ม + ตรวจความสอดคล้องภายในแต่ละเล่ม → รายการข้อสังเกต

โหมด

* ``same_year``  — ร่าง พ.ร.บ. ↔ พ.ร.บ. (หรือฉบับก่อน/หลังปรับ) ปีงบเดียวกัน: ทุกค่าที่ต่าง = ข้อสังเกต
* ``cross_year`` — เล่มปี Y−1 ↔ เล่มปี Y: (1) งบปี Y เทียบปี Y−1 รายโหนด = **การเปลี่ยนแปลงระหว่างปี**
  (ข้อมูลประกอบ ไม่ใช่ความผิดปกติ) (2) ตัวเลข **ปีเดียวกัน** ที่ปรากฏในทั้งสองเล่ม (เช่น งบปี Y−1
  ในตารางประมาณการของเล่มปี Y) ไม่ตรงกัน = ข้อสังเกตที่ต้องตรวจ (3) ประมาณการรายจ่ายล่วงหน้าที่เปลี่ยน

🔴 ถ้อยคำ: "ต่าง" / "ไม่ตรงกัน — กรุณาตรวจ" เท่านั้น · ไม่มีคำว่า "ผิด" · ชื่อที่คล้ายกัน = **คู่ที่เสนอ**
ให้คนยืนยัน ไม่จับคู่ให้อัตโนมัติ · เกณฑ์ยอมให้คลาดของกฎผลรวม/ข้ามตาราง = ผลรวมของ "ครึ่งหนึ่งของ
หลักสุดท้ายที่พิมพ์" ของทุกค่าที่เกี่ยว (``Amount.tolerance`` · ล้านบาท 4 ตำแหน่ง → 0.00005 ต่อค่า) —
precision ใช้กำหนดเกณฑ์ปัดเศษเท่านั้น ไม่ใช่ความเชื่อมั่น

นโยบายปัดเศษ (:data:`ROUNDING_POLICY`): เกณฑ์ครึ่งหลักใช้กับค่าในหน่วยที่ใหญ่กว่าบาท (ตารางล้านบาท) เท่านั้น
และเป็น **สมมติฐานของกฎ** ว่าแต่ละค่าถูกปัดจากบาทอย่างอิสระ — เอกสารไม่ได้ระบุวิธีปัด (REVIEW 6360210542) ·
ค่าหน่วยบาททุกตาราง (รวมรายการในรายละเอียด · รายการผูกพัน) ใช้กฎผลรวมเคร่งครัด (เกณฑ์ 0) · ส่วนต่างที่อยู่ในเกณฑ์
**ไม่ได้แปลว่าตรงเป๊ะ** — ข้อสังเกตทุกข้อแสดงส่วนต่าง เกณฑ์ที่ใช้ และที่มาของเกณฑ์ (``tolerance_basis``)

ค่าที่มีธงใน :data:`extract.CONFIRM_FLAGS` (หน่วยไม่มีในเอกสาร · คอลัมน์จากระยะใกล้สุด · ปีจากข้อมูลเล่ม)
ยังเทียบให้ แต่ข้อสังเกตติด ``caveats`` = ต้องให้คนยืนยันก่อนใช้
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from decimal import Decimal

from . import profile as P
from .extract import CONFIRM_FLAGS, UNIT_ORIGINS_IN_DOCUMENT, Amount, BookFacts, Evidence, node_flags
from .text import exact_key, fmt, label_key, similarity, text_key, to_baht

MODE_SAME_YEAR = "same_year"
MODE_CROSS_YEAR = "cross_year"
MODE_LABELS = {MODE_SAME_YEAR: "ปีเดียวกัน (ร่าง พ.ร.บ. ↔ พ.ร.บ.)",
               MODE_CROSS_YEAR: "ข้ามปี (เล่มปีก่อน ↔ เล่มปีนี้)"}

RENAME_MIN_SIMILARITY = 0.72

# ── หัวข้อ (ตามรายการที่กิ๊ฟกำหนด) ────────────────────────────────────────────
T_TOTAL = "total"
T_ECON = "econ"
T_STRUCT = "struct"
T_ITEMS = "items"
T_COMMIT = "commit"
T_MTEF = "mtef"
T_IND = "ind"
T_TEXT = "text"
T_FORMAT = "format"
T_CONSIST = "consist"
T_COVER = "cover"
TOPICS = (
    (T_TOTAL, "ยอดรวมและวงเงินตามหมวดงบรายจ่าย"),
    (T_ECON, "รายจ่ายประจำและรายจ่ายลงทุน"),
    (T_STRUCT, "แผนงาน ผลผลิต/โครงการ กิจกรรม (ชื่อ เพิ่ม หาย ย้ายแผน)"),
    (T_ITEMS, "รายการที่เสนอตั้ง / ไม่เสนอตั้ง"),
    (T_COMMIT, "วงเงินรวมโครงการและรายการผูกพันข้ามปี"),
    (T_MTEF, "ประมาณการรายจ่ายล่วงหน้า (MTEF)"),
    (T_IND, "ตัวชี้วัดและค่าเป้าหมาย"),
    (T_TEXT, "วิสัยทัศน์ พันธกิจ ผลสัมฤทธิ์ และวัตถุประสงค์"),
    (T_FORMAT, "ชื่อหน่วยงาน เลขนำหน้า หัวตาราง และหน่วยของตาราง"),
    (T_CONSIST, "ความสอดคล้องภายในเล่ม (ยอดรวม ↔ รายการย่อย ↔ ตารางอื่น)"),
    (T_COVER, "ส่วนที่ระบบอ่านไม่ได้ — ต้องให้คนตรวจ"),
)
TOPIC_LABELS = dict(TOPICS)

# ประเภทข้อสังเกต → ป้ายภาษาคน
K_CHANGED = "changed"
K_ONLY_A = "only_a"
K_ONLY_B = "only_b"
K_RENAMED = "renamed_candidate"
K_MOVED = "moved"
K_YEAR_CHANGE = "year_change"
K_SAME_YEAR_DIFF = "same_year_mismatch"
K_NOT_PROPOSED = "not_proposed"
K_SUM = "sum_mismatch"
K_CROSS_TABLE = "cross_table_mismatch"
K_UNREAD = "unread"
K_SECTION_MISSING = "section_missing"
K_DASH_VS_VALUE = "dash_vs_value"
K_LABEL_VARIANT = "label_variant"
K_IDENTITY = "identity_ambiguous"
K_BLANK_VS_VALUE = "blank_vs_value"
KIND_LABELS = {
    K_BLANK_VS_VALUE: "ฉบับหนึ่งช่องนี้ว่าง (มีแถวแต่ไม่มีตัวเลข) อีกฉบับมีตัวเลข",
    K_DASH_VS_VALUE: "ฉบับหนึ่งพิมพ์ขีด (ไม่มีค่า) อีกฉบับมีตัวเลข",
    K_LABEL_VARIANT: "จับคู่ด้วยโครงคำ แต่ชื่อต่างกันที่สระ/วรรณยุกต์ — กรุณายืนยันว่าเป็นรายการเดียวกัน",
    K_IDENTITY: "ระบุตัวรายการไม่ได้แน่ชัด (ชื่อซ้ำ/โครงคำชนกัน) — กรุณาตรวจ",
    K_CHANGED: "ค่าต่างกันระหว่างสองฉบับ",
    K_ONLY_A: "มีเฉพาะฉบับ A",
    K_ONLY_B: "มีเฉพาะฉบับ B",
    K_RENAMED: "คาดว่าเป็นรายการเดียวกันแต่ชื่อเปลี่ยน — กรุณาตรวจหลักฐาน A/B",
    K_MOVED: "อยู่ใต้แผนงานต่างกัน (ปรับแผน)",
    K_YEAR_CHANGE: "เปลี่ยนแปลงจากปีก่อน",
    K_SAME_YEAR_DIFF: "ตัวเลขปีเดียวกันในสองเล่มไม่ตรงกัน — กรุณาตรวจ",
    K_NOT_PROPOSED: "ระบุว่าไม่เสนอตั้งงบประมาณ",
    K_SUM: "ผลรวมไม่เท่ากับยอดรวมที่พิมพ์ — กรุณาตรวจ",
    K_CROSS_TABLE: "ตัวเลขเดียวกันในสองตารางของเล่มเดียวกันไม่ตรงกัน — กรุณาตรวจ",
    K_UNREAD: "ระบบอ่าน/จัดหมวดไม่ได้ — ต้องให้คนตรวจ",
    K_SECTION_MISSING: "ไม่พบหัวข้อนี้ในฉบับ — ต้องให้คนตรวจว่าไม่มีจริง หรือระบบอ่านไม่พบ",
}


CAVEAT_LABELS = {
    "unit_not_in_document": "หน่วยไม่ได้มาจากเอกสาร (ใช้ค่าตั้งต้นของโปรไฟล์)",
    "column_nearest": "ตัวเลขอยู่นอกแนวหัวคอลัมน์ ระบบจัดเข้าคอลัมน์ที่ใกล้ที่สุด",
    "year_from_book_meta": "ปีของช่องนี้มาจากปีงบของเล่ม ไม่ใช่หัวตาราง",
    "identity_collision": "รายการนี้ระบุตัวไม่แน่ชัด (โครงคำชนกัน/ช่องเดียวกันมีหลายค่า) — ผลเทียบอาจรวมคนละรายการ",
    "identity_ambiguous": "ระบุรายการแม่ของแถวนี้ไม่ได้แน่ชัด — ค่าอาจเป็นของรายการชื่อเดียวกันใต้แม่อื่น",
}
ROUNDING_POLICY = ("เกณฑ์ปัดเศษ = ผลรวมครึ่งหลักสุดท้ายที่พิมพ์ของค่าในหน่วยที่ใหญ่กว่าบาท (เช่น ล้านบาท) — "
                   "เป็นสมมติฐานของกฎว่าแต่ละค่าถูกปัดจากบาทอย่างอิสระ ไม่ใช่ข้อเท็จจริงที่เอกสารระบุ "
                   "(เอกสารไม่ได้บอกวิธีปัด) · ค่าหน่วยบาทไม่ได้ปัด ใช้กฎเคร่งครัด (เกณฑ์ 0) · อยู่ในเกณฑ์ ≠ ตรงเป๊ะ")
#: ที่มาของเกณฑ์ที่ข้อสังเกตใช้ (``Finding.tolerance_basis``)
TOLERANCE_BASIS_LABELS = {"assumed_independent_rounding": "สมมติฐานของกฎ: ค่าหน่วยล้านบาทถูกปัดจากบาทอย่างอิสระ",
                          "strict": "กฎเคร่งครัด (เกณฑ์ 0)"}


@dataclass
class Side:
    value: str = ""
    raw: str = ""
    unit: str = ""
    page: int | None = None
    bbox: tuple | None = None
    text: str = ""
    unit_origin: str = ""                 # ดู ``Amount.unit_origin`` · "" = ไม่ใช่ค่าเงิน/รอบเก่า
    flags: list = field(default_factory=list)
    status: str = ""                      # read · dash · blank · "" = ไม่ใช่ค่าเงิน


@dataclass
class Finding:
    id: str
    topic: str
    kind: str
    subject: str              # ชื่อรายการ/โหนด/ตัวชี้วัด
    column: str = ""          # หมวดงบ / ปี / ฟิลด์
    a: Side = field(default_factory=Side)
    b: Side = field(default_factory=Side)
    delta: str = ""           # ผลต่าง B − A (ข้อความ · หน่วยเดียวกับค่า)
    unit: str = ""
    note: str = ""
    within: str = ""          # "A" | "B" = ข้อสังเกตภายในฉบับนั้น · "" = เทียบสองฉบับ
    info: bool = False        # True = ข้อมูลประกอบ (เช่น การเปลี่ยนแปลงระหว่างปี) ไม่ใช่ข้อที่ต้องแก้
    kind_override: str = ""   # ใช้ตอนสร้างเท่านั้น — ถ้าระบุ จะแทน ``kind``
    caveats: list = field(default_factory=list)   # เหตุที่ต้องให้คนยืนยันก่อนใช้ (CAVEAT_LABELS)
    parts: list = field(default_factory=list)     # องค์ประกอบของผลรวม [{label, value, unit, page, bbox, flags}]
    tolerance: str = ""                           # เกณฑ์ปัดเศษที่ใช้ (หน่วยเดียวกับ ``unit``) · "" = ไม่ใช่กฎผลรวม
    tolerance_basis: str = ""                     # ที่มาของเกณฑ์ (:data:`TOLERANCE_BASIS_LABELS`) · "" = ไม่ใช่กฎผลรวม/รอบเก่า

    def __post_init__(self):
        if self.kind_override:
            self.kind, self.kind_override = self.kind_override, ""

    @property
    def kind_label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)

    @property
    def topic_label(self) -> str:
        return TOPIC_LABELS.get(self.topic, self.topic)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        return cls(**{**d, "a": Side(**d["a"]), "b": Side(**d["b"])})


def _node_title(n) -> str:
    """ชื่อโหนดสำหรับแสดง — เติมระดับเมื่อป้ายในเล่มไม่ได้บอกระดับเอง"""
    lvl = P.LEVEL_LABELS.get(n.level, "")
    return n.label if (not lvl or n.label.replace(" ", "").startswith(lvl)) else f"{lvl} : {n.label}"


def _fid(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]


def _side_amount(a: Amount | None) -> Side:
    if a is None:
        return Side()
    return Side(value=a.value, raw=a.raw, unit=a.unit, page=a.ev.page, bbox=a.ev.bbox,
                text=a.ev.text, unit_origin=a.unit_origin, flags=list(a.flags), status=a.status)


def _side_ev(ev: Evidence | None, value: str = "", unit: str = "", flags=()) -> Side:
    """``flags`` = ธงของค่า/ของรายการที่ค่านี้ผูกอยู่ (เช่น ธงระบุตัวของโหนด) — ส่งต่อเป็นคำเตือนของข้อสังเกต"""
    if ev is None:
        return Side(value=value, unit=unit, flags=list(dict.fromkeys(flags)))
    return Side(value=value, unit=unit, page=ev.page, bbox=ev.bbox, text=ev.text, flags=list(dict.fromkeys(flags)))


def _identity_only(flags) -> list:
    return [x for x in flags or () if x.startswith("identity_")]


def _commit_side(c, key: str, value: str, nf: dict) -> Side:
    """ค่าหนึ่งช่องของรายการผูกพัน — หลักฐาน = บรรทัดที่ให้ค่านั้น · ธง = ธงระบุตัวของโหนด + หน่วยที่ไม่มีในบรรทัด"""
    ev, uo = c.line_of(key)
    flags = list(nf.get(c.node, ()))
    if uo and uo not in UNIT_ORIGINS_IN_DOCUMENT:
        flags.append("unit_not_in_document")
    return _side_ev(ev, value, "บาท", flags)


def _commit_key(c, name: str) -> str:
    """ป้ายช่องของรายการผูกพัน → กุญแจบรรทัด (``Commitment.line_keys``)"""
    if name == "วงเงินทั้งสิ้น":
        return "total"
    y = name.rsplit(" ", 1)[-1] if name.startswith("ผูกพัน") else name.split(" ")[1]
    return f"future:{y}" if (name.startswith("ผูกพัน") or (name.startswith("งบปี") and y in c.future)) \
        else f"year:{y}"


def _delta(a: str, b: str) -> str:
    try:
        return str(Decimal(b) - Decimal(a))
    except Exception:          # noqa: BLE001
        return ""


def _sum_tol(*amounts: Amount) -> Decimal:
    """เกณฑ์ยอมให้คลาด (หน่วยเดียวกับค่า) = ผลรวม ``rounding_tolerance`` ของทุกค่าที่เกี่ยว
    (ครึ่งหลักสุดท้ายที่พิมพ์ของค่าที่สมมติว่าถูกปัด · ค่าหน่วยบาท = 0)"""
    return sum((x.rounding_tolerance for x in amounts), Decimal(0))


def _baht_tol(*amounts: Amount) -> Decimal:
    """เหมือน :func:`_sum_tol` แต่แปลงเป็นบาท — ใช้เมื่อค่าที่เทียบอยู่คนละหน่วย"""
    return sum((to_baht(x.rounding_tolerance, x.unit) for x in amounts), Decimal(0))


@dataclass
class CompareResult:
    mode: str
    fy_a: int | None
    fy_b: int | None
    findings: list
    node_labels: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"mode": self.mode, "fy_a": self.fy_a, "fy_b": self.fy_b,
                "findings": [f.to_dict() for f in self.findings],
                "node_labels": self.node_labels}

    @classmethod
    def from_dict(cls, d: dict) -> "CompareResult":
        return cls(d["mode"], d.get("fy_a"), d.get("fy_b"),
                   [Finding.from_dict(x) for x in d["findings"]], d.get("node_labels", {}))


# ══════════════════════════════════════════════════════════════════════════════
def detect_mode(a: BookFacts, b: BookFacts) -> str:
    if a.fiscal_year and b.fiscal_year and a.fiscal_year != b.fiscal_year:
        return MODE_CROSS_YEAR
    return MODE_SAME_YEAR


def compare(a: BookFacts, b: BookFacts, mode: str = "") -> CompareResult:
    mode = mode or detect_mode(a, b)
    out: list[Finding] = []
    labels = {**{k: n.label for k, n in a.nodes.items()}, **{k: n.label for k, n in b.nodes.items()},
              **a.row_labels, **b.row_labels,
              "total": "รวมทั้งสิ้น", "": "ระดับหน่วยงาน", "budget": "งบประมาณรายจ่ายของหน่วยงาน (ต้นช่วง)",
              "offbudget": "เงินนอกงบประมาณของหน่วยงาน (ต้นช่วง)"}
    for k in list(_amount_keys(a) | _amount_keys(b)):
        if "|" in k and not k.startswith("off:"):
            head, rest = k.split("|", 1)
            hl = "" if head == "row" else labels.get(head, head.replace("grp:", ""))
            rl = "รวมทั้งสิ้น" if rest == "total" else (a.row_labels.get(k) or b.row_labels.get(k) or rest)
            labels[k] = f"{hl} · {rl}" if hl else rl
    renames = _structure(a, b, mode, out)
    _amount_tables(a, b, mode, out, labels, renames)
    _mtef(a, b, mode, out, labels, renames)
    _items(a, b, out, labels, renames, mode)
    _commitments(a, b, out, labels, mode)
    _indicators(a, b, mode, out, labels, renames)
    _texts(a, b, out, labels, renames, mode)
    _format(a, b, out, labels, renames, mode)
    for side, bf in (("A", a), ("B", b)):
        _internal(bf, side, out, labels)
        _coverage(bf, side, out)
        _identity(bf, side, out)
    _not_found_vs_unread(a, b, out)
    for f in out:      # ค่าที่ต้องให้คนยืนยัน — เทียบให้ แต่ติดเหตุไว้กับข้อสังเกต
        flags = [x for x in dict.fromkeys(list(f.a.flags) + list(f.b.flags)) if x in CONFIRM_FLAGS]
        f.caveats = [CAVEAT_LABELS.get(x, x) for x in flags]
        # องค์ประกอบของผลรวม: ยอดแม่อาจชัด แต่ลูกบางค่ามีธง — ผลรวมทั้งข้อต้องให้คนยืนยัน
        by_flag: dict[str, list] = {}
        for p in f.parts:
            for x in p.get("flags", []):
                if x in CONFIRM_FLAGS:
                    by_flag.setdefault(x, []).append(p["label"])
        for x, lbs in by_flag.items():
            if x in flags and len(lbs) == len(f.parts):
                continue
            f.caveats.append(f"องค์ประกอบของผลรวม {len(lbs)} ค่า: {CAVEAT_LABELS.get(x, x)} "
                             f"({' · '.join(lbs[:3])}{' …' if len(lbs) > 3 else ''})")
    # เรียงตามหัวข้อ → ลำดับในเล่ม (หน้า) · id ไม่ซ้ำ
    order = {t: i for i, (t, _l) in enumerate(TOPICS)}
    seen, uniq = set(), []
    for f in out:
        if f.id in seen:
            continue
        seen.add(f.id)
        uniq.append(f)
    uniq.sort(key=lambda f: (order.get(f.topic, 99), f.info,
                             (f.a.page or f.b.page or 0), (f.b.page or 0)))
    return CompareResult(mode, a.fiscal_year, b.fiscal_year, uniq, labels)


# ── โครงสร้าง ────────────────────────────────────────────────────────────────
def _structure(a: BookFacts, b: BookFacts, mode: str, out: list) -> dict:
    """คืน ``{key_b: key_a}`` ของคู่ที่ *เสนอ* ว่าชื่อเปลี่ยน (ใช้เทียบเงินต่อ แต่ยังต้องให้คนยืนยัน)"""
    ka, kb = set(a.nodes), set(b.nodes)
    nfa, nfb = node_flags(a), node_flags(b)
    only_a = sorted(ka - kb, key=lambda k: a.nodes[k].order)
    only_b = sorted(kb - ka, key=lambda k: b.nodes[k].order)
    renames: dict[str, str] = {}
    used_a = set()
    for k in only_b:
        nb = b.nodes[k]
        best, score = None, 0.0
        for j in only_a:
            na = a.nodes[j]
            if j in used_a or na.level != nb.level:
                continue
            same_parent = (na.parent == nb.parent) or (renames.get(nb.parent) == na.parent)
            if not same_parent:
                continue
            sc = similarity(na.label, nb.label)
            if sc > score:
                best, score = j, sc
        if best is not None and score >= RENAME_MIN_SIMILARITY:
            renames[k] = best
            used_a.add(best)
            na = a.nodes[best]
            out.append(Finding(_fid(T_STRUCT, K_RENAMED, best, k), T_STRUCT, K_RENAMED,
                               _node_title(nb), column="ชื่อ", a=_side_ev(na.ev, na.label, flags=nfa.get(best, ())),
                               b=_side_ev(nb.ev, nb.label, flags=nfb.get(k, ())),
                               note=f"ชื่อคล้ายกัน {score:.0%} และอยู่ใต้แผนงานเดียวกัน — "
                                    "ระบบไม่ได้ยืนยันว่าเป็นรายการเดียวกัน"))
    for j in only_a:
        if j in used_a:
            continue
        n = a.nodes[j]
        out.append(Finding(_fid(T_STRUCT, K_ONLY_A, j), T_STRUCT, K_ONLY_A, _node_title(n),
                           a=_side_ev(n.ev, n.label, flags=nfa.get(j, ())),
                           info=mode == MODE_CROSS_YEAR))
    for k in only_b:
        if k in renames:
            continue
        n = b.nodes[k]
        out.append(Finding(_fid(T_STRUCT, K_ONLY_B, k), T_STRUCT, K_ONLY_B, _node_title(n),
                           b=_side_ev(n.ev, n.label, flags=nfb.get(k, ())),
                           info=mode == MODE_CROSS_YEAR))
    # จับคู่ด้วยโครงคำ แต่ชื่อจริงต่างที่สระ/วรรณยุกต์ — ไม่รวมเงียบ
    for k in sorted(ka & kb, key=lambda k: a.nodes[k].order):
        na, nb = a.nodes[k], b.nodes[k]
        _label_variant(out, T_STRUCT, ("node", k), _node_title(nb), na.label, nb.label, na.ev, nb.ev,
                       nfa.get(k, ()), nfb.get(k, ()))
    # ย้ายแผน
    for k in ka & kb:
        na, nb = a.nodes[k], b.nodes[k]
        if na.level != P.LEVEL_PLAN and na.parent and nb.parent and na.parent != nb.parent \
                and renames.get(nb.parent) != na.parent:
            out.append(Finding(_fid(T_STRUCT, K_MOVED, k), T_STRUCT, K_MOVED,
                               _node_title(na), column="แผนงาน",
                               a=_side_ev(na.ev, a.nodes.get(na.parent).label
                                          if na.parent in a.nodes else na.parent, flags=nfa.get(k, ())),
                               b=_side_ev(nb.ev, b.nodes.get(nb.parent).label
                                          if nb.parent in b.nodes else nb.parent, flags=nfb.get(k, ()))))
    return renames


def _amount_keys(bf) -> set:
    return {x.node for x in bf.amounts}


def _index(amounts, table: str) -> dict:
    return {(x.node, x.column): x for x in amounts if x.table == table}


# ── ตารางเงิน (สรุปหมวดงบ · ประจำ/ลงทุน · เงินนอกงบประมาณ · หัวเล่ม · ยอดหมวดในรายละเอียด) ──
def _amount_tables(a, b, mode, out, labels, renames):
    tables = ((P.SEC_SUMMARY, T_TOTAL), (P.SEC_ECON, T_ECON), ("header", T_TOTAL),
              (P.SEC_DETAIL, T_TOTAL), (P.SEC_OFFBUDGET, T_TOTAL), (P.SUB_ACTIVITY, T_TOTAL))
    back = {v: k for k, v in renames.items()}
    for table, topic in tables:
        ia, ib = _index(a.amounts, table), _index(b.amounts, table)
        keys = set(ia) | {(renames.get(n, n), c) for (n, c) in ib}
        for (node, col) in sorted(keys, key=lambda k: (str(k[0]), str(k[1]))):
            if table == P.SEC_ECON and col == P.COL_TOTAL:
                continue      # ยอดรวมซ้ำกับตารางสรุป — ความสอดคล้องสองตารางตรวจในหัวข้อภายในเล่ม
            xa = ia.get((node, col))
            xb = ib.get((node, col)) or ib.get((back.get(node, node), col))
            if xa is None and xb is None:
                continue
            subj = f"{labels.get(node, node)}"
            if node.startswith("off:"):
                subj = node[4:]
            if table == P.SEC_OFFBUDGET:
                subj = f"เงินนอกงบประมาณ · {subj}"
            if table == "header":
                subj = labels.get(node, node)
            if xa is not None and xb is not None:
                va, vb = to_baht(xa.dec, xa.unit), to_baht(xb.dec, xb.unit)
                if va == vb:
                    continue
                if table == P.SEC_DETAIL:
                    sa = _index(a.amounts, P.SEC_SUMMARY).get((node, col))
                    sb = _index(b.amounts, P.SEC_SUMMARY).get((back.get(node, node), col)) or \
                        _index(b.amounts, P.SEC_SUMMARY).get((node, col))
                    if sa is not None and sb is not None and \
                            abs((to_baht(sb.dec, sb.unit) - to_baht(sa.dec, sa.unit)) - (vb - va)) \
                            <= _baht_tol(sa, sb, xa, xb):
                        continue      # ผลต่างเดียวกับตารางสรุป — แสดงครั้งเดียว
                kind = K_YEAR_CHANGE if mode == MODE_CROSS_YEAR else K_CHANGED
                info_note = ""
                if mode == MODE_CROSS_YEAR and col.isdigit():
                    if table == P.SEC_OFFBUDGET:
                        # แผนการใช้จ่ายเงินนอกงบประมาณปรับทุกปี และปีที่ผ่านไปกลายเป็นผลจริง — ข้อมูลประกอบ
                        kind = K_CHANGED
                        info_note = "แผนเงินนอกงบประมาณของปีนี้ถูกปรับในเล่มใหม่ (หรือเปลี่ยนจากแผนเป็นผลจริง)"
                    else:
                        # คอลัมน์ปีของงบประมาณที่ตั้งแล้ว — ปีเดียวกันในสองเล่มต้องตรงกัน
                        kind = K_SAME_YEAR_DIFF
                unit = xa.unit if xa.unit == xb.unit else "บาท"
                dv = (xb.dec - xa.dec) if xa.unit == xb.unit else (vb - va)
                out.append(Finding(_fid(topic, table, node, col), topic, kind, subj,
                                   column=_col_label(col), a=_side_amount(xa), b=_side_amount(xb),
                                   delta=str(dv), unit=unit,
                                   info=kind == K_YEAR_CHANGE or bool(info_note),
                                   note=(info_note + " · " if info_note else "") + _table_note(table)))
            else:
                one = xa or xb
                kind = K_ONLY_A if xa is not None else K_ONLY_B
                dash = _dash_of(b if xa is not None else a, table, node, col, renames, xa is not None)
                if dash is not None:
                    da, db = (xa, dash) if xa is not None else (dash, xb)
                    out.append(Finding(_fid(topic, table, node, col, K_DASH_VS_VALUE), topic,
                                       K_DASH_VS_VALUE, subj, column=_col_label(col),
                                       a=_side_amount(da), b=_side_amount(db), unit=one.unit,
                                       info=mode == MODE_CROSS_YEAR and col.isdigit()
                                       and not _settled_year(a, col),
                                       note="ขีด = เอกสารพิมพ์ว่าไม่มีค่า (ต่างจาก \"ไม่พบ\") · " + _table_note(table)))
                    continue
                blank = _blank_of(b if xa is not None else a, table, node, col, renames, xa is not None)
                if blank is not None:
                    ba, bb = (xa, blank) if xa is not None else (blank, xb)
                    out.append(Finding(_fid(topic, table, node, col, K_BLANK_VS_VALUE), topic,
                                       K_BLANK_VS_VALUE, subj, column=_col_label(col),
                                       a=_side_amount(ba), b=_side_amount(bb), unit=one.unit,
                                       info=mode == MODE_CROSS_YEAR and col.isdigit()
                                       and not _settled_year(a, col),
                                       note="ช่องว่าง = แถวมีอยู่แต่ไม่มีอะไรพิมพ์ในช่องนี้ (ต่างจาก \"ไม่พบแถว\" "
                                            "และไม่ได้แปลว่าเป็นศูนย์) · " + _table_note(table)))
                    continue
                if mode == MODE_CROSS_YEAR and col.isdigit():
                    continue      # ปีที่มีในเล่มเดียว = นอกช่วงที่เทียบได้
                if node not in ("total", "") and (node in a.nodes) != (node in b.nodes):
                    continue      # โหนดทั้งโหนดเพิ่ม/หาย — รายงานแล้วในหัวข้อโครงสร้าง
                out.append(Finding(_fid(topic, table, node, col, kind), topic, kind, subj,
                                   column=_col_label(col),
                                   a=_side_amount(xa), b=_side_amount(xb), unit=one.unit,
                                   info=mode == MODE_CROSS_YEAR and table != P.SEC_OFFBUDGET,
                                   note=_table_note(table)))


def _dash_of(bf: BookFacts, table: str, node: str, col: str, renames: dict, other_is_b: bool):
    """ช่องที่พิมพ์ขีดในเล่ม ``bf`` ที่ตำแหน่งเดียวกัน (คำนึงถึงคู่ชื่อเปลี่ยนที่เสนอ)"""
    back = {v: k for k, v in renames.items()}
    nodes = {node, back.get(node, node)} if other_is_b else {node, renames.get(node, node)}
    for d in bf.dashes:
        if d.table == table and d.column == col and d.node in nodes:
            return d
    return None


def _blank_of(bf: BookFacts, table: str, node: str, col: str, renames: dict, other_is_b: bool):
    """ช่องว่าง (แถวมีอยู่ ไม่มีตัวเลข) ในเล่ม ``bf`` ที่ตำแหน่งเดียวกัน"""
    back = {v: k for k, v in renames.items()}
    nodes = {node, back.get(node, node)} if other_is_b else {node, renames.get(node, node)}
    for d in getattr(bf, "blanks", []):
        if d.table == table and d.column == col and d.node in nodes:
            return d
    return None


def _part(label: str, x) -> dict:
    """องค์ประกอบของผลรวม — ค่า หน่วย หลักฐาน และธงของค่านั้น (ส่งต่อไปยังข้อสังเกต)"""
    if isinstance(x, Amount):
        return {"label": label, "value": x.value, "raw": x.raw, "unit": x.unit, "page": x.ev.page,
                "bbox": list(x.ev.bbox), "flags": list(x.flags)}
    # รายการในรายละเอียด: ธงหน่วยของบรรทัดยอด + ธงระบุตัวของโหนด (ตั้งตอนสกัด · ``extract.mark_identity``)
    return {"label": label, "value": str(x.amount or ""), "raw": str(x.amount or ""), "unit": "บาท",
            "page": x.ev.page, "bbox": list(x.ev.bbox), "flags": list(getattr(x, "flags", []))}


def _settled_year(a: BookFacts, col: str) -> bool:
    """ปีที่เป็นงบที่ตั้งแล้วในเล่ม A — ตัวเลขปีนี้ในสองเล่มต้องตรงกัน"""
    return bool(a.fiscal_year) and col.isdigit() and int(col) <= a.fiscal_year


def _col_label(col: str) -> str:
    if col.isdigit():
        return f"ปี {col}"
    return {"budget": "งบประมาณรายจ่าย", "offbudget": "เงินนอกงบประมาณ"}.get(col, col)


def _table_note(table: str) -> str:
    return {P.SEC_SUMMARY: "จากตารางสรุปตามแผนงาน/ผลผลิต และงบรายจ่าย",
            P.SEC_ECON: "จากตารางรายจ่ายประจำ/ลงทุน",
            P.SEC_DETAIL: "จากรายละเอียดงบประมาณ (ยอดหมวด)",
            P.SEC_OFFBUDGET: "จากตารางเงินนอกงบประมาณ",
            P.SEC_MTEF: "จากตารางเป้าหมายการให้บริการ งบประมาณ และประมาณการรายจ่ายล่วงหน้า",
            P.SEC_YEARS: "จากตารางเปรียบเทียบงบประมาณรายจ่ายรายปี",
            P.SUB_ACTIVITY: "จากตารางงบประมาณจำแนกตามกิจกรรม",
            P.SUB_OUTPUT_MTEF: "จากตารางเป้าหมายผลผลิตและประมาณการล่วงหน้าของผลผลิต",
            "header": "จากตารางต้นช่วงของหน่วยงาน"}.get(table, "")


# ── ประมาณการรายจ่ายล่วงหน้า ─────────────────────────────────────────────────
def _mtef(a, b, mode, out, labels, renames):
    for table in (P.SEC_MTEF, P.SUB_OUTPUT_MTEF, P.SEC_YEARS):
        _year_table(a, b, mode, out, labels, renames, table)


def _year_table(a, b, mode, out, labels, renames, table):
    ia, ib = _index(a.amounts, table), _index(b.amounts, table)
    summ = _index(a.amounts, P.SEC_SUMMARY)
    back = {v: k for k, v in renames.items()}
    keys = set(ia) | {(renames.get(n, n), c) for (n, c) in ib}
    for (node, year) in sorted(keys, key=lambda k: (str(k[0]), str(k[1]))):
        xa = ia.get((node, year))
        xb = ib.get((node, year)) or ib.get((back.get(node, node), year))
        if (xa is None) != (xb is None):
            dash = _dash_of(b if xa is not None else a, table, node, year, renames, xa is not None)
            if dash is not None:
                da, db = (xa, dash) if xa is not None else (dash, xb)
                topic = T_TOTAL if table == P.SEC_YEARS else T_MTEF
                out.append(Finding(_fid(topic, table, node, year, K_DASH_VS_VALUE), topic, K_DASH_VS_VALUE,
                                   labels.get(node, node), column=f"ปี {year}", a=_side_amount(da),
                                   b=_side_amount(db), unit=(xa or xb).unit,
                                   info=mode == MODE_CROSS_YEAR and not _settled_year(a, year),
                                   note="ขีด = เอกสารพิมพ์ว่าไม่มีค่า (ต่างจาก \"ไม่พบ\") · " + _table_note(table)))
            continue
        if xa is None or xb is None:
            continue      # ปีที่มีเล่มเดียว = นอกช่วงที่เทียบได้ (ไม่ใช่รายการหาย)
        if mode == MODE_SAME_YEAR and a.fiscal_year and year == str(a.fiscal_year) \
                and (node, P.COL_TOTAL) in summ:
            continue      # ปีงบนี้ของโหนดซ้ำกับตารางสรุป — ความสอดคล้องตรวจในหัวข้อภายในเล่ม
        if to_baht(xa.dec, xa.unit) == to_baht(xb.dec, xb.unit):
            continue
        y = int(year) if year.isdigit() else 0
        if mode == MODE_CROSS_YEAR:
            # ปีที่เป็นงบที่ตั้งแล้วในเล่ม A (ปีงบของ A) = ต้องตรงกัน · ปีถัดไป = ประมาณการเปลี่ยน
            kind = K_SAME_YEAR_DIFF if (a.fiscal_year and y <= a.fiscal_year) else K_CHANGED
            note = ("ปีนี้เป็นงบประมาณที่ตั้งแล้วในเล่มปีก่อน — ตัวเลขในเล่มปีนี้ควรตรงกัน"
                    if kind == K_SAME_YEAR_DIFF else "ประมาณการรายจ่ายล่วงหน้าของปีนี้ถูกปรับในเล่มใหม่")
        else:
            kind, note = K_CHANGED, ""
        topic = T_TOTAL if table == P.SEC_YEARS else T_MTEF
        out.append(Finding(_fid(topic, table, node, year), topic, kind, labels.get(node, node),
                           column=f"ปี {year}", a=_side_amount(xa), b=_side_amount(xb),
                           delta=str(xb.dec - xa.dec) if xa.unit == xb.unit else "",
                           unit=xa.unit, note=(note + " · " if note else "") + _table_note(table),
                           info=mode == MODE_CROSS_YEAR and kind == K_CHANGED))


# ── รายการในรายละเอียด ───────────────────────────────────────────────────────
def _items(a, b, out, labels, renames, mode=MODE_SAME_YEAR):
    back = {v: k for k, v in renames.items()}
    ia = {(i.node, i.key): i for i in a.items}
    ib = {(renames.get(i.node, i.node), i.key): i for i in b.items}
    for k in sorted(set(ia) | set(ib), key=str):
        xa, xb = ia.get(k), ib.get(k)
        node = k[0]
        x = xa or xb
        subj = f"{x.label} ({x.category or 'รายการ'} · {labels.get(node, node)})"
        if xa and xb:
            _label_variant(out, T_ITEMS, ("item",) + k, subj, xa.label, xb.label, xa.ev, xb.ev,
                           _identity_only(xa.flags), _identity_only(xb.flags))
            if xa.amount != xb.amount:
                out.append(Finding(_fid(T_ITEMS, "amt", *k), T_ITEMS, K_CHANGED, subj,
                                   column="จำนวนเงิน", a=_side_ev(xa.ev, xa.amount or "", "บาท", xa.flags),
                                   b=_side_ev(xb.ev, xb.amount or "", "บาท", xb.flags),
                                   delta=_delta(xa.amount or "0", xb.amount or "0"), unit="บาท",
                                   info=mode == MODE_CROSS_YEAR,
                                   kind_override=K_YEAR_CHANGE if mode == MODE_CROSS_YEAR else ""))
            if xa.not_proposed != xb.not_proposed:
                out.append(Finding(_fid(T_ITEMS, "np", *k), T_ITEMS, K_NOT_PROPOSED, subj,
                                   column="สถานะการเสนอตั้ง",
                                   a=_side_ev(xa.ev, "ไม่เสนอตั้ง" if xa.not_proposed else "เสนอตั้ง",
                                              flags=_identity_only(xa.flags)),
                                   b=_side_ev(xb.ev, "ไม่เสนอตั้ง" if xb.not_proposed else "เสนอตั้ง",
                                              flags=_identity_only(xb.flags))))
            continue
        if node in a.nodes and node not in b.nodes and back.get(node) is None and xb is None \
                and node not in renames.values():
            continue    # ทั้งโหนดหาย — รายงานในหัวข้อโครงสร้างแล้ว
        kind = K_ONLY_A if xa else K_ONLY_B
        out.append(Finding(_fid(T_ITEMS, kind, *k), T_ITEMS, kind, subj, column="รายการ",
                           info=mode == MODE_CROSS_YEAR,
                           a=_side_ev(xa.ev, xa.amount or "", "บาท", xa.flags) if xa else Side(),
                           b=_side_ev(xb.ev, xb.amount or "", "บาท", xb.flags) if xb else Side(),
                           unit="บาท",
                           note=("ฉบับ A ไม่มีรายการนี้ — เสนอตั้งเพิ่มในฉบับ B" if xb else
                                 "ฉบับ B ไม่มีรายการนี้ — ไม่ได้เสนอตั้งในฉบับ B")))
    paired_np = {k for k in set(ia) & set(ib) if ia[k].not_proposed != ib[k].not_proposed}
    for side, bf in (("A", a), ("B", b)):
        for i in bf.items:
            k = (renames.get(i.node, i.node) if side == "B" else i.node, i.key)
            if i.not_proposed and k not in paired_np:
                out.append(Finding(_fid(T_ITEMS, "np1", side, i.node, i.key), T_ITEMS,
                                   K_NOT_PROPOSED, f"{i.label} ({labels.get(i.node, i.node)})",
                                   column="สถานะการเสนอตั้ง",
                                   a=_side_ev(i.ev, "ไม่เสนอตั้ง") if side == "A" else Side(),
                                   b=_side_ev(i.ev, "ไม่เสนอตั้ง") if side == "B" else Side(),
                                   within=side, info=True,
                                   note=f"ฉบับ {side} ระบุข้อความว่าไม่เสนอตั้งงบประมาณ"))


# ── รายการผูกพัน ─────────────────────────────────────────────────────────────
def _commitments(a, b, out, labels, mode=MODE_SAME_YEAR):
    ia = {(c.node, c.key): c for c in a.commitments}
    ib = {(c.node, c.key): c for c in b.commitments}
    nfa, nfb = node_flags(a), node_flags(b)
    for k in sorted(set(ia) | set(ib), key=str):
        ca, cb = ia.get(k), ib.get(k)
        x = ca or cb
        subj = f"{x.label} ({labels.get(k[0], k[0])})"
        if ca and cb and mode == MODE_CROSS_YEAR:
            # เล่มปีก่อน "ผูกพันงบประมาณปี Y" ↔ เล่มปีนี้ "ปี Y ตั้งงบประมาณ" — ปีเดียวกันเทียบกันได้
            all_a = {**ca.years, **ca.future}
            all_b = {**cb.years, **cb.future}
            fields = [("วงเงินทั้งสิ้น", ca.total, cb.total)]
            for y in sorted(set(all_a) & set(all_b)):
                fields.append((f"งบปี {y}", all_a[y], all_b[y]))
            for name, va, vb in fields:
                if va and vb and va != vb:
                    out.append(Finding(_fid(T_COMMIT, *k, name), T_COMMIT, K_SAME_YEAR_DIFF, subj,
                                       column=name, a=_commit_side(ca, _commit_key(ca, name), va, nfa),
                                       b=_commit_side(cb, _commit_key(cb, name), vb, nfb),
                                       delta=_delta(va, vb), unit="บาท",
                                       note="ปีเดียวกันในรายการผูกพันของสองเล่ม (ผูกพันปีต่อไปในเล่มก่อน ↔ "
                                            "ตั้งงบประมาณในเล่มนี้) ไม่ตรงกัน"))
            continue
        if ca and cb:
            fields = [("วงเงินทั้งสิ้น", ca.total, cb.total)]
            for y in sorted(set(ca.years) | set(cb.years)):
                fields.append((f"ปี {y} ตั้งงบประมาณ", ca.years.get(y), cb.years.get(y)))
            for y in sorted(set(ca.future) | set(cb.future)):
                fields.append((f"ผูกพันงบประมาณปี {y}", ca.future.get(y), cb.future.get(y)))
            for name, va, vb in fields:
                if va != vb:
                    out.append(Finding(_fid(T_COMMIT, *k, name), T_COMMIT,
                                       K_CHANGED if va and vb else (K_ONLY_A if va else K_ONLY_B),
                                       subj, column=name, a=_commit_side(ca, _commit_key(ca, name), va or "", nfa),
                                       b=_commit_side(cb, _commit_key(cb, name), vb or "", nfb),
                                       delta=_delta(va, vb) if va and vb else "", unit="บาท"))
        else:
            kind = K_ONLY_A if ca else K_ONLY_B
            out.append(Finding(_fid(T_COMMIT, kind, *k), T_COMMIT, kind, subj, column="รายการผูกพัน",
                               a=_commit_side(ca, "total", ca.total or "", nfa) if ca else Side(),
                               b=_commit_side(cb, "total", cb.total or "", nfb) if cb else Side(),
                               unit="บาท"))


# ── ตัวชี้วัด ────────────────────────────────────────────────────────────────
def _indicators(a, b, mode, out, labels, renames):
    ia = {(i.scope, f"{i.table}|{i.key}"): i for i in a.indicators}
    ib = {(renames.get(i.scope, i.scope), f"{i.table}|{i.key}"): i for i in b.indicators}
    nfa, nfb = node_flags(a), node_flags(b)
    sev_a = lambda x, v: _side_ev(x.ev, v, flags=nfa.get(x.scope, ()))   # noqa: E731 — ธงระบุตัวของโหนดที่ตัวชี้วัดสังกัด
    sev_b = lambda x, v: _side_ev(x.ev, v, flags=nfb.get(x.scope, ()))   # noqa: E731
    only_a = [k for k in ia if k not in ib]
    only_b = [k for k in ib if k not in ia]
    pair: dict = {}
    for kb in only_b:
        best, sc = None, 0.0
        for ka in only_a:
            if ka in pair.values() or ka[0] != kb[0]:
                continue
            s = similarity(ia[ka].name, ib[kb].name)
            if s > sc:
                best, sc = ka, s
        if best is not None and sc >= RENAME_MIN_SIMILARITY:
            pair[kb] = best
    for k in sorted(set(ia) & set(ib), key=str) + [(kb, pair[kb]) for kb in pair]:
        if isinstance(k[0], tuple):
            kb, ka = k
            xa, xb = ia[ka], ib[kb]
            out.append(Finding(_fid(T_IND, K_RENAMED, *ka, *kb), T_IND, K_RENAMED, xb.name,
                               column="ชื่อตัวชี้วัด", a=sev_a(xa, xa.name), b=sev_b(xb, xb.name),
                               note="ชื่อคล้ายกัน — ระบบไม่ได้ยืนยันว่าเป็นตัวชี้วัดเดียวกัน"))
            scope = ka[0]
        else:
            xa, xb = ia[k], ib[k]
            scope = k[0]
            _label_variant(out, T_IND, ("ind",) + k, xb.name, xa.name, xb.name, xa.ev, xb.ev,
                           nfa.get(xa.scope, ()), nfb.get(xb.scope, ()))
        subj = xb.name + (f" ({labels.get(scope, scope)})" if scope else "")
        if xa.unit != xb.unit:
            out.append(Finding(_fid(T_IND, "unit", scope, xa.key, xb.key), T_IND, K_CHANGED, subj,
                               column="หน่วยนับ", a=sev_a(xa, xa.unit), b=sev_b(xb, xb.unit)))
        for y in sorted(set(xa.targets) & set(xb.targets)):
            ta_, tb_ = _target(xa.targets[y]), _target(xb.targets[y])
            if mode == MODE_CROSS_YEAR and (not ta_ or not tb_):
                continue      # ปีที่เล่มหนึ่งไม่กำหนดเป้าหมาย = นอกช่วงที่เทียบได้
            if ta_ != tb_:
                kind = K_CHANGED
                if mode == MODE_CROSS_YEAR and a.fiscal_year and y.isdigit() and int(y) < (b.fiscal_year or 0):
                    kind = K_SAME_YEAR_DIFF
                out.append(Finding(_fid(T_IND, "t", scope, xa.key, y), T_IND, kind, subj,
                                   column=_target_column(y), a=sev_a(xa, xa.targets[y]),
                                   b=sev_b(xb, xb.targets[y]),
                                   delta=_delta(xa.targets[y], xb.targets[y])))
    for k in only_a:
        if k in pair.values():
            continue
        x = ia[k]
        out.append(Finding(_fid(T_IND, K_ONLY_A, *k), T_IND, K_ONLY_A,
                           x.name + (f" ({labels.get(k[0], k[0])})" if k[0] else ""),
                           column="ตัวชี้วัด", a=sev_a(x, x.name)))
    for k in only_b:
        if k in pair:
            continue
        x = ib[k]
        out.append(Finding(_fid(T_IND, K_ONLY_B, *k), T_IND, K_ONLY_B,
                           x.name + (f" ({labels.get(k[0], k[0])})" if k[0] else ""),
                           column="ตัวชี้วัด", b=sev_b(x, x.name),
                           info=mode == MODE_CROSS_YEAR and bool(k[0]) and k[0] not in a.nodes))


def _label_variant(out, topic, key, subj, la, lb, eva, evb, fa=(), fb=()):
    if exact_key(la) != exact_key(lb):
        out.append(Finding(_fid(topic, K_LABEL_VARIANT, *key), topic, K_LABEL_VARIANT, subj,
                           column="ชื่อ", a=_side_ev(eva, la, flags=fa), b=_side_ev(evb, lb, flags=fb),
                           note="ระบบจับคู่สองชื่อนี้เพราะโครงคำ (ตัดสระ/วรรณยุกต์) ตรงกัน — "
                                "ถ้าเป็นคนละรายการ ผลเทียบเงินของรายการนี้ใช้ไม่ได้"))


def _identity(bf: BookFacts, side: str, out: list):
    """ปัญหาระบุตัวรายการภายในเล่ม (ดู ``extract.resolve_node_keys``) — มองเห็นได้ ไม่รวมเงียบ ·
    ปัญหาที่สืบทอดจากแม่ (``INHERITED_NOTES``) ไม่ทำข้อแยก — ต้นเหตุมีข้อของตัวเองแล้ว ส่วนค่าของลูกติดธงต้องยืนยัน"""
    from .extract import INHERITED_NOTES
    for x in bf.identity_issues:
        if x.get("kind") in INHERITED_NOTES:
            continue
        s = _side_ev(x.get("ev"), " | ".join(x.get("labels", [])))
        out.append(Finding(_fid(T_STRUCT, K_IDENTITY, side, x["kind"], x["key"]), T_STRUCT, K_IDENTITY,
                           (x.get("labels") or [x["key"]])[0], column=IDENTITY_LABELS.get(x["kind"], x["kind"]),
                           within=side, a=s if side == "A" else Side(), b=s if side == "B" else Side(),
                           note=x.get("note", "")))


IDENTITY_LABELS = {
    "ambiguous_parent": "ชื่อซ้ำใต้รายการแม่ต่างกัน และแถวนี้ไม่ระบุแม่",
    "skeleton_merge": "ชื่อต่างกันที่สระ/วรรณยุกต์ แต่โครงคำเดียวกัน (รวมเป็นรายการเดียว)",
    "duplicate_indicator": "ตัวชี้วัดชื่อซ้ำในตารางเดียวกัน",
}


def _target(v: str) -> str:
    v = (v or "").strip()
    return "" if v in ("-", "–", "—") else v


def _target_column(y: str) -> str:
    """ป้ายคอลัมน์ค่าของตัวชี้วัด — ปีเดี่ยว · ช่วงปี ("เริ่มต้น–2569" = ผลสะสม · "2573–จบ") · คอลัมน์อื่น"""
    if y.isdigit():
        return f"เป้าหมายปี {y}"
    return f"ค่าช่วงปี {y}" if "–" in y else f"ค่าในคอลัมน์ {y}"


# ── วิสัยทัศน์ พันธกิจ ผลสัมฤทธิ์ วัตถุประสงค์ ────────────────────────────────
_TEXT_SECTION_LABEL = {**P.SECTION_LABELS, "objective": "วัตถุประสงค์"}


def _texts(a, b, out, labels, renames=None, mode=MODE_SAME_YEAR):
    renames = renames or {}
    b_scope = lambda t: renames.get(t.scope, t.scope)  # noqa: E731
    nfa, nfb = node_flags(a), node_flags(b)
    tev_a = lambda t: _side_ev(t.ev, t.text, flags=nfa.get(t.scope, ()))   # noqa: E731 — ธงระบุตัวของโหนดเจ้าของข้อความ
    tev_b = lambda t: _side_ev(t.ev, t.text, flags=nfb.get(t.scope, ()))   # noqa: E731
    groups = sorted({(t.section, t.scope) for t in a.texts}
                    | {(t.section, b_scope(t)) for t in b.texts}, key=str)
    for sec, scope in groups:
        ta = [t for t in a.texts if t.section == sec and t.scope == scope]
        tb = [t for t in b.texts if t.section == sec and b_scope(t) == scope]
        name = _TEXT_SECTION_LABEL.get(sec, sec) + (f" · {labels.get(scope, scope)}" if scope else "")
        ka = {t.key: t for t in ta}
        kb = {t.key: t for t in tb}
        ra = [t for t in ta if t.key not in kb]
        rb = [t for t in tb if t.key not in ka]
        used = set()
        for tb_ in rb:
            best, sc = None, 0.0
            for ta_ in ra:
                if id(ta_) in used:
                    continue
                s = similarity(ta_.text, tb_.text)
                if s > sc:
                    best, sc = ta_, s
            if best is not None and (sc >= 0.5 or (len(ra) == 1 and len(rb) == 1)):
                used.add(id(best))
                out.append(Finding(_fid(T_TEXT, sec, scope, best.key, tb_.key), T_TEXT, K_CHANGED,
                                   name, column=f"ข้อ {tb_.no}" if tb_.no else "ข้อความ",
                                   a=tev_a(best), b=tev_b(tb_),
                                   note="ข้อความต่างกัน — ดูส่วนที่เปลี่ยนด้านล่าง"))
            else:
                out.append(Finding(_fid(T_TEXT, K_ONLY_B, sec, scope, tb_.key), T_TEXT, K_ONLY_B,
                                   name, column=f"ข้อ {tb_.no}" if tb_.no else "ข้อความ",
                                   b=tev_b(tb_),
                                   info=mode == MODE_CROSS_YEAR and bool(scope) and scope not in a.nodes))
        for ta_ in ra:
            if id(ta_) in used:
                continue
            out.append(Finding(_fid(T_TEXT, K_ONLY_A, sec, scope, ta_.key), T_TEXT, K_ONLY_A, name,
                               column=f"ข้อ {ta_.no}" if ta_.no else "ข้อความ",
                               a=tev_a(ta_),
                               info=mode == MODE_CROSS_YEAR and bool(scope) and scope not in b.nodes))
    # หัวข้อหลักที่ฉบับหนึ่งพบ อีกฉบับไม่พบ
    for sec in (P.SEC_VISION, P.SEC_MISSION, P.SEC_OUTCOME, P.SEC_TARGET, P.SEC_SUMMARY,
                P.SEC_ECON, P.SEC_MTEF, P.SEC_DETAIL):
        fa, fb = sec in a.coverage.sections_found, sec in b.coverage.sections_found
        if fa != fb:
            side = "B" if fa else "A"
            out.append(Finding(_fid(T_COVER, K_SECTION_MISSING, sec, side), T_COVER,
                               K_SECTION_MISSING, P.SECTION_LABELS[sec], within=side,
                               note=f"ฉบับ {'A' if fa else 'B'} พบหัวข้อนี้ แต่ฉบับ {side} ไม่พบ"))


# ── รูปแบบ: ชื่อหน่วยงาน · เลขนำหน้า · หัวตาราง · หน่วย ─────────────────────────
_SEC_NAME = {**P.SECTION_LABELS, "": "ต้นช่วง"}


def _format(a, b, out, labels, renames, mode):
    cross = mode == MODE_CROSS_YEAR
    ta, tb = a.agency_title, b.agency_title
    if ta and tb and text_key(ta) != text_key(tb):
        out.append(Finding(_fid(T_FORMAT, "agency"), T_FORMAT, K_CHANGED, "ชื่อหน่วยงาน (ต้นช่วง)",
                           column="ข้อความ", a=Side(value=ta), b=Side(value=tb),
                           note="ชื่อหน่วยงานที่พิมพ์ต้นช่วงต่างกัน"))
    # เลขนำหน้าของโหนดในแต่ละตาราง
    def nums(bf, remap=None):
        d = {}
        for x in bf.numbering:
            k = (x["section"], (remap or {}).get(x["node"], x["node"]))
            d.setdefault(k, x)
        return d
    na, nb = nums(a), nums(b, renames)
    for k in sorted(set(na) & set(nb), key=str):
        xa, xb = na[k], nb[k]
        if xa["no"] != xb["no"]:
            out.append(Finding(_fid(T_FORMAT, "no", *k), T_FORMAT, K_CHANGED,
                               labels.get(k[1], k[1]), column=f"เลขนำหน้า · {_SEC_NAME.get(k[0], k[0])}",
                               a=_side_ev(xa["ev"], xa["no"] or "(ไม่มีเลขนำหน้า)"),
                               b=_side_ev(xb["ev"], xb["no"] or "(ไม่มีเลขนำหน้า)"), info=cross,
                               note="เลขข้อ/จุด/วงเล็บที่พิมพ์นำหน้าต่างกัน"))
    ia = {(i.node, i.key): i for i in a.items}
    ib = {(renames.get(i.node, i.node), i.key): i for i in b.items}
    for k in sorted(set(ia) & set(ib), key=str):
        if ia[k].no != ib[k].no:
            out.append(Finding(_fid(T_FORMAT, "ino", *k), T_FORMAT, K_CHANGED,
                               f"{ia[k].label} ({labels.get(k[0], k[0])})", column="เลขนำหน้ารายการ",
                               a=_side_ev(ia[k].ev, ia[k].no), b=_side_ev(ib[k].ev, ib[k].no), info=cross))
    for key in sorted(set(a.headers) & set(b.headers)):
        ha, hb = a.headers[key], b.headers[key]
        if not cross and ha != hb:
            out.append(Finding(_fid(T_FORMAT, "hdr", key), T_FORMAT, K_CHANGED,
                               f"หัวตาราง · {_SEC_NAME.get(key.split(':')[0], key)}", column="ชื่อคอลัมน์",
                               a=Side(value=" | ".join(ha)), b=Side(value=" | ".join(hb)),
                               note="คอลัมน์ของตารางเดียวกันต่างกัน"))
    for sec in sorted(set(a.table_units) & set(b.table_units)):
        if a.table_units[sec] != b.table_units[sec]:
            out.append(Finding(_fid(T_FORMAT, "unit", sec), T_FORMAT, K_CHANGED,
                               f"หน่วยของตาราง · {_SEC_NAME.get(sec, sec)}", column="หน่วย",
                               a=Side(value=a.table_units[sec]), b=Side(value=b.table_units[sec]),
                               note="ระบบแปลงหน่วยเป็นบาทก่อนเทียบตัวเลขแล้ว — ข้อนี้แจ้งเฉพาะว่ารูปแบบหน่วยต่างกัน"))


def _not_found_vs_unread(a, b, out):
    """ข้อ "มีเฉพาะฉบับ X" — ถ้าอีกฉบับมีส่วนที่อ่านไม่ได้ ต้องบอกว่าอาจอยู่ในส่วนนั้น (ไม่ใช่หายแน่นอน)"""
    for f in out:
        if f.kind not in (K_ONLY_A, K_ONLY_B) or f.within:
            continue
        other = b if f.kind == K_ONLY_A else a
        n_pages, n_rows = len(other.coverage.pages_no_text), len(other.coverage.unparsed)
        if n_pages or n_rows:
            side = "B" if f.kind == K_ONLY_A else "A"
            f.note = ((f.note + " · ") if f.note else "") + (
                f"ฉบับ {side} มีส่วนที่ระบบอ่านไม่ได้ ({n_pages} หน้า · {n_rows} บรรทัด) — "
                "รายการนี้อาจอยู่ในส่วนนั้น ไม่ได้แปลว่าไม่มีแน่นอน")


# ── ความสอดคล้องภายในเล่ม ────────────────────────────────────────────────────
def _internal(bf: BookFacts, side: str, out: list, labels: dict):
    def put(topic, kind, subj, col, printed: Amount, expected: Decimal, unit, note, n,
            parts=(), tol: Decimal | None = None):
        """``parts`` = [(ป้าย, Amount|Item)] ทุกค่าที่ใช้คำนวณ — ธงของทุกองค์ประกอบส่งต่อเป็นคำเตือน
        ``tol`` = เกณฑ์ปัดเศษที่ใช้ (None = กฎเคร่งครัด 0)"""
        s = _side_amount(printed)
        exp = Side(value=str(expected), unit=unit, page=printed.ev.page, bbox=printed.ev.bbox,
                   text="ผลรวมที่ระบบคำนวณ")
        a_, b_ = (s, exp) if side == "A" else (exp, s)
        tol = tol if tol is not None else Decimal(0)
        resid = printed.dec - expected
        basis = "assumed_independent_rounding" if tol else "strict"
        out.append(Finding(_fid(topic, kind, side, subj, col), topic, kind, subj, column=col,
                           a=a_ if side == "A" else Side(), b=b_ if side == "B" else Side(),
                           delta=str(resid), unit=unit, within=side,
                           parts=[_part(lb, x) for lb, x in parts], tolerance=str(tol), tolerance_basis=basis,
                           note=f"{note} · ยอดที่พิมพ์ {fmt(printed.dec, unit)} · "
                                f"ผลรวมที่คำนวณ {fmt(expected, unit)} ({n} ค่า) · ส่วนต่าง {fmt(resid, unit)} · "
                                + (f"เกณฑ์ปัดเศษ ±{fmt(tol, unit)} ({TOLERANCE_BASIS_LABELS[basis]})" if tol
                                   else TOLERANCE_BASIS_LABELS[basis])))

    summ = _index(bf.amounts, P.SEC_SUMMARY)
    # (1) แต่ละแถว: ผลรวมหมวดงบ = คอลัมน์ "รวม"
    for (node, col), tot in summ.items():
        if col != P.COL_TOTAL:
            continue
        parts = [summ[(node, c)] for c in P.CATEGORIES if (node, c) in summ]
        if len(parts) >= 2:
            ssum = sum((p.dec for p in parts), Decimal(0))
            if abs(ssum - tot.dec) > _sum_tol(tot, *parts):
                put(T_CONSIST, K_SUM, labels.get(node, node), "รวม (ตามหมวดงบ)", tot, ssum,
                    tot.unit, "ผลรวมหมวดงบในแถวเดียวกันไม่เท่ากับช่องรวม", len(parts),
                    [(p.column, p) for p in parts], _sum_tol(tot, *parts))
    # (2) ลูกรวมกันเท่ากับแม่ — แผนงาน = ผลรวมผลผลิต/โครงการ · รวมทั้งสิ้น = ผลรวมแผนงาน
    children: dict[str, list] = {}
    for k, n in bf.nodes.items():
        if n.parent:
            children.setdefault(n.parent, []).append(k)
    plans = [k for k, n in bf.nodes.items() if n.level == P.LEVEL_PLAN]
    for table, topic in ((P.SEC_SUMMARY, T_CONSIST), (P.SEC_ECON, T_CONSIST), (P.SEC_MTEF, T_CONSIST)):
        idx = _index(bf.amounts, table)
        cols = sorted({c for (_n, c) in idx})
        for parent, kids in list(children.items()) + [("total", plans)]:
            for col in cols:
                p = idx.get((parent, col))
                vals = [idx[(k, col)] for k in kids if (k, col) in idx]
                if p is None or len(vals) < 1 or len(vals) != len(kids):
                    continue
                ssum = sum((v.dec for v in vals), Decimal(0))
                if abs(ssum - p.dec) > _sum_tol(p, *vals):
                    put(topic, K_SUM, labels.get(parent, parent), _col_label(col), p, ssum, p.unit,
                        f"ยอดของ{'รวมทั้งสิ้น' if parent == 'total' else 'แผนงาน'}ไม่เท่ากับผลรวมรายการย่อย"
                        f" ({_table_note(table) or 'ตารางประมาณการ'})", len(vals),
                        [(labels.get(v.node, v.node), v) for v in vals], _sum_tol(p, *vals))
    # (3) ประจำ + ลงทุน = รวม
    econ = _index(bf.amounts, P.SEC_ECON)
    for (node, col), tot in econ.items():
        if col != P.COL_TOTAL:
            continue
        parts = [econ[(node, c)] for c in P.ECON_COLUMNS if (node, c) in econ]
        if len(parts) == 2:
            ssum = parts[0].dec + parts[1].dec
            if abs(ssum - tot.dec) > _sum_tol(tot, *parts):
                put(T_CONSIST, K_SUM, labels.get(node, node), "รายจ่ายประจำ + รายจ่ายลงทุน", tot, ssum,
                    tot.unit, "รายจ่ายประจำรวมรายจ่ายลงทุนไม่เท่ากับยอดรวม", 2,
                    [(p.column, p) for p in parts], _sum_tol(tot, *parts))
    # (4) ข้ามตาราง: ยอดรวมของโหนดในตารางสรุป = ตารางประจำ/ลงทุน = ปีงบในตารางประมาณการ = หัวเล่ม
    mtef = _index(bf.amounts, P.SEC_MTEF)
    fy = str(bf.fiscal_year) if bf.fiscal_year else ""
    head = _index(bf.amounts, "header").get(("budget", fy))
    # ตารางประมาณการของเล่มจริง: "รวมทั้งสิ้น" รวมเงินนอกงบประมาณด้วย — เทียบกับแถว "รวมเงินงบประมาณ"
    mtef_budget = {}
    for (n, c), x in mtef.items():
        if n.endswith("|" + label_key("รวมเงินงบประมาณ")) or n.endswith("|" + label_key("เงินงบประมาณ")):
            head_key = n.split("|", 1)[0]
            if head_key.startswith("grp:"):
                continue
            mtef_budget[("total" if head_key == "row" else head_key, c)] = x
    for (node, col), tot in summ.items():
        if col != P.COL_TOTAL:
            continue
        others = [(econ.get((node, P.COL_TOTAL)), "ตารางรายจ่ายประจำ/ลงทุน"),
                  ((mtef_budget.get((node, fy)) or mtef.get((node, fy))) if fy else None,
                   f"ตารางประมาณการ ปี {fy}"),
                  (_index(bf.amounts, P.SEC_YEARS).get((node, fy)) if fy else None,
                   f"ตารางเปรียบเทียบรายปี ปี {fy}")]
        if node == "total" and head is not None:
            others.append((head, "หัวข้อต้นช่วงของหน่วยงาน"))
        for other, where in others:
            if other is None:
                continue
            va, vb = to_baht(tot.dec, tot.unit), to_baht(other.dec, other.unit)
            tol = _baht_tol(tot, other)
            if abs(va - vb) > tol:
                same = other.unit == tot.unit
                put(T_CONSIST, K_CROSS_TABLE, labels.get(node, node), f"ยอดรวม ↔ {where}", other,
                    tot.dec if same else to_baht(tot.dec, tot.unit),
                    other.unit, f"ยอดใน{where}ไม่ตรงกับตารางสรุปตามแผนงาน", 1,
                    [("ตารางสรุป · รวม", tot), (where, other)], _sum_tol(tot, other) if same else tol)
    # (5) รายละเอียด: ยอดหมวดของผลผลิต/โครงการ ↔ ตารางสรุป (บาท ↔ ล้านบาท)
    det = _index(bf.amounts, P.SEC_DETAIL)
    for (node, col), d in det.items():
        s = summ.get((node, col))
        if s is None:
            continue
        va, vb = to_baht(d.dec, d.unit), to_baht(s.dec, s.unit)
        if abs(va - vb) > _baht_tol(s, d):
            put(T_CONSIST, K_CROSS_TABLE, labels.get(node, node),
                f"{_col_label(col)} (รายละเอียด ↔ ตารางสรุป)", d, vb, "บาท",
                "ยอดในรายละเอียดงบประมาณไม่ตรงกับตารางสรุป (ตารางสรุปปัดเป็นล้านบาท 4 ตำแหน่ง)", 1,
                [("รายละเอียด", d), ("ตารางสรุป", s)], _baht_tol(s, d))
    # (6) ยอดหมวดในรายละเอียด = ผลรวมรายการที่พิมพ์ (เฉพาะหมวดที่มีรายการพิมพ์ครบ ≥ 2 รายการ)
    for (node, col), d in det.items():
        if col not in P.CATEGORIES:
            continue
        cat_items = [i for i in bf.items if i.node == node and i.category == col and i.amount]
        if not cat_items:
            continue
        # ชั้นของรายการดูจากระยะย่อหน้าบนหน้ากระดาษ — เลขข้อในเล่มจริงเริ่มนับใหม่ในชั้นที่ซ้อน
        # (1.1 → 1) → 1.1 → (1)) · รวมเฉพาะชั้นบนสุด ไม่นับซ้ำ
        top = min(i.ev.bbox[0] for i in cat_items)
        its = [i for i in cat_items if i.ev.bbox[0] - top <= 3.0]
        if len(its) >= 2:
            ssum = sum((Decimal(i.amount) for i in its), Decimal(0))
            if ssum != d.dec:
                put(T_CONSIST, K_SUM, labels.get(node, node), f"{col} (ผลรวมรายการที่พิมพ์)", d, ssum,
                    "บาท", "ยอดหมวดไม่เท่ากับผลรวมรายการที่พิมพ์ — อาจพิมพ์รายการไม่ครบ หรือยอดคลาด",
                    len(its), [(i.label, i) for i in its])
    # (7) รายการผูกพัน: วงเงินทั้งสิ้น = ผลรวมปีที่ตั้ง + ผูกพันปีต่อไป — องค์ประกอบทุกค่าชี้บรรทัดที่พิมพ์ +
    #     ธง (หน่วยไม่มีในบรรทัด · รายการแม่ระบุตัวไม่ได้) เหมือนกฎผลรวมอื่น
    nf = node_flags(bf)

    def cline(c, key: str, label: str, value: str) -> Amount:
        ev, uo = c.line_of(key)
        flags = list(nf.get(c.node, ()))
        if uo and uo not in UNIT_ORIGINS_IN_DOCUMENT:
            flags.append("unit_not_in_document")
        return Amount(P.SEC_DETAIL, c.node, label, value, "บาท", value, ev or c.ev, unit_origin=uo, flags=flags)
    for c in bf.commitments:
        if not c.total or not (c.years or c.future):
            continue
        ssum = sum((Decimal(v) for v in list(c.years.values()) + list(c.future.values())),
                   Decimal(0))
        yparts = [(f"ปี {y} ตั้งงบประมาณ", cline(c, f"year:{y}", f"ปี {y} ตั้งงบประมาณ", v))
                  for y, v in c.years.items()] + \
                 [(f"ผูกพันงบประมาณปี {y}", cline(c, f"future:{y}", f"ผูกพันงบประมาณปี {y}", v))
                  for y, v in c.future.items()]
        total = cline(c, "total", "วงเงินทั้งสิ้น", c.total)
        budget = c.parts.get(P.FUND_BUDGET)
        if budget is not None:
            # เล่มจริง: วงเงินทั้งสิ้น = เงินงบประมาณ + เงินนอกงบประมาณ · เงินงบประมาณ = ผลรวมรายปี
            off = Decimal(c.parts.get(P.FUND_OFFBUDGET, "0"))
            bud = cline(c, f"fund:{P.FUND_BUDGET}", P.FUND_BUDGET, budget)
            if Decimal(budget) + off != Decimal(c.total):
                fparts = [(P.FUND_BUDGET, bud)] + ([(P.FUND_OFFBUDGET, cline(
                    c, f"fund:{P.FUND_OFFBUDGET}", P.FUND_OFFBUDGET, c.parts[P.FUND_OFFBUDGET]))]
                    if P.FUND_OFFBUDGET in c.parts else [])
                put(T_COMMIT, K_SUM, f"{c.label} ({labels.get(c.node, c.node)})", "วงเงินทั้งสิ้น (แหล่งเงิน)",
                    total, Decimal(budget) + off, "บาท", "วงเงินทั้งสิ้นไม่เท่ากับเงินงบประมาณรวมเงินนอกงบประมาณ", 2,
                    fparts)
            if ssum != Decimal(budget):
                put(T_COMMIT, K_SUM, f"{c.label} ({labels.get(c.node, c.node)})", "เงินงบประมาณของรายการผูกพัน",
                    bud, ssum, "บาท", "เงินงบประมาณไม่เท่ากับผลรวมงบที่ตั้งแต่ละปีกับที่ผูกพันปีต่อไป",
                    len(c.years) + len(c.future), yparts)
            continue
        if ssum != Decimal(c.total):
            put(T_COMMIT, K_SUM, f"{c.label} ({labels.get(c.node, c.node)})", "วงเงินทั้งสิ้น", total,
                ssum, "บาท", "วงเงินทั้งสิ้นไม่เท่ากับผลรวมงบที่ตั้งแต่ละปีกับที่ผูกพันปีต่อไป",
                len(c.years) + len(c.future), yparts)


def _coverage(bf: BookFacts, side: str, out: list):
    for p in bf.coverage.pages_no_text:
        out.append(Finding(_fid(T_COVER, "notext", side, p), T_COVER, K_UNREAD,
                           f"หน้า {p} ไม่มีชั้นข้อความ (อาจเป็นภาพสแกน)", within=side,
                           a=Side(page=p) if side == "A" else Side(),
                           b=Side(page=p) if side == "B" else Side(),
                           note="ระบบไม่ใช้ OCR — ต้องให้คนตรวจหน้านี้เอง"))
    for ev in bf.coverage.unparsed:
        s = _side_ev(ev, ev.text)
        out.append(Finding(_fid(T_COVER, "row", side, ev.page, ev.bbox), T_COVER, K_UNREAD,
                           ev.text[:120], within=side, a=s if side == "A" else Side(),
                           b=s if side == "B" else Side(),
                           note="บรรทัดนี้มีตัวเลข แต่ระบบจัดเข้าตาราง/หมวดไม่ได้"))
