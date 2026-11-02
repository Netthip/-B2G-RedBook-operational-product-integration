# -*- coding: utf-8 -*-
"""โหลดและตรวจรูปแบบ predeclared Security Control Matrix (CSV)

matrix เป็น **source of truth ภายนอก** (อยู่ใน repo สาธารณะ และ versioned ด้วย git)
โมดูลนี้อ่านอย่างเดียว · คืนแฮช SHA-256 ของไฟล์เพื่อผูกเข้า manifest ของแต่ละรอบ
"""
from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

MATRIX_COLUMNS = (
    "control_id", "category", "asvs_ref", "asvs_level", "control", "applicability",
    "profile_condition", "test_method", "expected_result", "evidence_type", "disposition",
)
STATUSES = ("PASS", "FAIL", "REVIEW", "NOT_APPLICABLE")
APPLICABILITY = ("APPLICABLE", "CONDITIONAL", "NOT_APPLICABLE")
#: คำนำหน้า check ที่ runner รู้จัก — T pytest · H http probe · B browser · D dependency ·
#: L leak-check · Z ZAP
CHECK_PREFIXES = ("T", "H", "B", "D", "L", "Z")


class MatrixError(ValueError):
    pass


@dataclass(frozen=True)
class Control:
    control_id: str
    category: str
    asvs_ref: str
    asvs_level: str
    control: str
    applicability: str
    profile_condition: str
    checks: tuple[str, ...]
    expected_result: str
    evidence_type: str
    disposition: str

    @property
    def manual(self) -> bool:
        return self.disposition.strip().lower().startswith("manual")

    def checks_by_prefix(self, prefix: str) -> list[str]:
        return [c for c in self.checks if c.startswith(prefix + ":")]


@dataclass
class Matrix:
    path: Path
    sha256: str
    controls: list[Control] = field(default_factory=list)

    def by_id(self) -> dict[str, Control]:
        return {c.control_id: c for c in self.controls}

    def referenced_checks(self, prefix: str | None = None) -> list[str]:
        seen: list[str] = []
        for c in self.controls:
            for chk in c.checks:
                if prefix and not chk.startswith(prefix + ":"):
                    continue
                if chk not in seen:
                    seen.append(chk)
        return seen


def _split_checks(raw: str) -> tuple[str, ...]:
    return tuple(p.strip() for p in raw.split(";") if p.strip())


def validate_rows(rows: list[dict]) -> list[str]:
    """คืนรายการข้อผิดพลาด (ว่าง = ผ่าน) — ไม่โยน เพื่อให้รายงานได้ครบทุกข้อ"""
    errors: list[str] = []
    seen: set[str] = set()
    for i, row in enumerate(rows, start=2):
        cid = (row.get("control_id") or "").strip()
        if not cid:
            errors.append(f"แถว {i}: control_id ว่าง")
            continue
        if cid in seen:
            errors.append(f"แถว {i}: control_id ซ้ำ {cid}")
        seen.add(cid)
        app = (row.get("applicability") or "").strip()
        if app not in APPLICABILITY:
            errors.append(f"{cid}: applicability '{app}' ไม่อยู่ใน {APPLICABILITY}")
        if app == "CONDITIONAL" and not (row.get("profile_condition") or "").strip():
            errors.append(f"{cid}: CONDITIONAL ต้องมี profile_condition")
        checks = _split_checks(row.get("test_method") or "")
        if not checks:
            errors.append(f"{cid}: test_method ว่าง (ทุก control ต้องมีอย่างน้อยหนึ่ง check)")
        for chk in checks:
            prefix, _, rest = chk.partition(":")
            if prefix not in CHECK_PREFIXES or not rest:
                errors.append(f"{cid}: check '{chk}' รูปแบบไม่ถูกต้อง (ต้องเป็น <T|H|B|D|L|Z>:<id>)")
        if not (row.get("expected_result") or "").strip():
            errors.append(f"{cid}: expected_result ว่าง — ต้องประกาศผลที่คาดก่อนรัน")
        if not (row.get("disposition") or "").strip():
            errors.append(f"{cid}: disposition ว่าง")
    return errors


def load_matrix(path: str | Path) -> Matrix:
    p = Path(path)
    data = p.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    if tuple(reader.fieldnames or ()) != MATRIX_COLUMNS:
        raise MatrixError(
            f"คอลัมน์ไม่ตรงที่ประกาศ: ได้ {reader.fieldnames} ต้องการ {list(MATRIX_COLUMNS)}")
    rows = list(reader)
    errors = validate_rows(rows)
    if errors:
        raise MatrixError("matrix ไม่ผ่านการตรวจรูปแบบ:\n  " + "\n  ".join(errors))
    controls = [
        Control(
            control_id=r["control_id"].strip(), category=r["category"].strip(),
            asvs_ref=r["asvs_ref"].strip(), asvs_level=r["asvs_level"].strip(),
            control=r["control"].strip(), applicability=r["applicability"].strip(),
            profile_condition=r["profile_condition"].strip(),
            checks=_split_checks(r["test_method"]),
            expected_result=r["expected_result"].strip(),
            evidence_type=r["evidence_type"].strip(), disposition=r["disposition"].strip(),
        )
        for r in rows
    ]
    return Matrix(path=p, sha256=digest, controls=controls)


__all__ = ["MATRIX_COLUMNS", "STATUSES", "APPLICABILITY", "CHECK_PREFIXES", "Control",
           "Matrix", "MatrixError", "load_matrix", "validate_rows"]
