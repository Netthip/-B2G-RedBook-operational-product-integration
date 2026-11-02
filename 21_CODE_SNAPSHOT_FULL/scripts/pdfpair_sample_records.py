# -*- coding: utf-8 -*-
"""สุ่มระเบียนที่ระบบสกัดได้ไปให้คนทวนกับภาพหน้าเอกสาร — ตอบ REVIEW 6340074844 ข้อ 5 / 6342471856

"ไม่มีแถวอ่านไม่ได้" ไม่ได้พิสูจน์ว่าอ่านถูก — สคริปต์นี้สุ่มระเบียนแบบแบ่งชั้นตามชนิด (ค่าเงิน · ขีด/ช่องว่าง ·
ชื่อโหนด · ตัวชี้วัด · ข้อความ · หลักฐานปี) ด้วย seed ที่บันทึกไว้ แล้วตัดภาพบรรทัดของระเบียนนั้นจากหน้าเอกสาร
เพื่อให้คนติ๊ก "ตรงภาพ / ไม่ตรง / ไม่แน่ใจ" ทีละรายการ

    python scripts/pdfpair_sample_records.py --pdf <ไฟล์.pdf> --fy 2570 --out <โฟลเดอร์> [--per-kind 2 --seed 20261023]

ผลลัพธ์: ``<out>/<ชื่อไฟล์>/manifest.json`` (ระเบียน + seed + รุ่น + SHA-256 ของไฟล์) + ``crop_NN.png``
🔴 ใช้กับชุดพัฒนาเท่านั้น (ไม่ใช้กับชุดประเมินก่อนตรึง) · ผลลัพธ์มีข้อความจากเล่ม — เก็บนอก Git
"""
from __future__ import annotations

import argparse
import io
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from redbook import holdout  # noqa: E402
from redbook.core.hashing import sha256_file  # noqa: E402
from redbook.pdfbook import PDFBOOK_VERSION, profile, reader  # noqa: E402
from redbook.pdfbook import extract as ex  # noqa: E402

KIND_LABELS = {"amount": "ค่าเงิน (ค่า · หน่วย · คอลัมน์)", "dash_blank": "ช่องขีด/ช่องว่าง",
               "node": "ชื่อแผนงาน/ผลผลิต/โครงการ/กิจกรรม", "indicator": "ตัวชี้วัด (ชื่อ · หน่วยนับ · ค่าเป้าหมาย)",
               "text": "ข้อความ (วิสัยทัศน์ · พันธกิจ · ผลสัมฤทธิ์ …)", "year": "หลักฐานปีงบ"}


_TABLE = {**profile.SECTION_LABELS, "header": "หัวข้อต้นช่วงของหน่วยงาน", profile.SUB_ACTIVITY: "ตารางจำแนกตามกิจกรรม",
          profile.SUB_OUTPUT_MTEF: "ตารางเป้าหมาย/ประมาณการของผลผลิต", "location": "สถานที่ดำเนินการ",
          "objective": "วัตถุประสงค์"}
_UNIT = {"row": "หน่วยพิมพ์ในแถว", "text_column": "คอลัมน์หน่วยนับ", "table_decl": "บรรทัดประกาศหน่วยของตาราง",
         "profile_default": "ค่าตั้งต้น (ไม่พบในเอกสาร)", "assumed": "สมมติ (ไม่พบในเอกสาร)"}
_STATUS = {"dash": "พิมพ์ขีด", "blank": "ช่องว่าง (มีแถว ไม่มีตัวเลข)"}
_YEAR_KIND = {"stated": "ปีของเล่ม", "comparison": "ช่วงปีเปรียบเทียบ", "forward": "ช่วงประมาณการล่วงหน้า",
              "mention": "ปีที่กล่าวถึง"}


def _col(c: str) -> str:
    return f"ปี {c}" if c.isdigit() else c


def _records(bf: ex.BookFacts) -> dict:
    out = {k: [] for k in KIND_LABELS}
    for a in bf.amounts:
        out["amount"].append({"page": a.ev.page, "bbox": list(a.ev.bbox), "read": a.raw,
                              "detail": f"ค่า {a.value} {a.unit} · ช่อง {_col(a.column)} · {_TABLE.get(a.table, a.table)} · "
                                        f"หน่วยจาก{_UNIT.get(a.unit_origin, a.unit_origin)}"
                                        + (f" · ธง {', '.join(a.flags)}" if a.flags else "")})
    for a in list(bf.dashes) + list(getattr(bf, "blanks", [])):
        out["dash_blank"].append({"page": a.ev.page, "bbox": list(a.ev.bbox), "read": a.raw or "(ว่าง)",
                                  "detail": f"{_STATUS.get(a.status, a.status)} · ช่อง {_col(a.column)} · "
                                            f"{_TABLE.get(a.table, a.table)}"})
    for n in bf.nodes.values():
        out["node"].append({"page": n.ev.page, "bbox": list(n.ev.bbox), "read": n.label,
                            "detail": f"ระดับ {profile.LEVEL_LABELS.get(n.level, n.level)}"
                                      + (f" · เลขนำหน้า {n.no}" if n.no else "")})
    for i in bf.indicators:
        tg = " · ".join(f"{y}: {v}" for y, v in i.targets.items())
        out["indicator"].append({"page": i.ev.page, "bbox": list(i.ev.bbox), "read": i.name,
                                 "detail": f"หน่วยนับ {i.unit or '—'} · {tg}"})
    for t in bf.texts:
        out["text"].append({"page": t.ev.page, "bbox": list(t.ev.bbox), "read": t.text[:200],
                            "detail": f"หัวข้อ {_TABLE.get(t.section, t.section)}"})
    for e in getattr(bf, "year_evidence", []):
        out["year"].append({"page": e["page"], "bbox": list(e.get("bbox") or []), "read": e["line"],
                            "detail": f"{_YEAR_KIND.get(e['kind'], e['kind'])} {e['year']}"
                                      + (f"–{e['end']}" if e.get('end') != e['year'] else "")
                                      + f" · {'อ่านตรงจากข้อความ' if e['direct'] else 'อนุมาน'} · คำบอก {e['cue'] or '—'}"})
    return out


def _crop(path: Path, page: int, bbox: list, zoom: float = 1.6, margin: float = 14.0) -> bytes:
    from PIL import Image
    png = reader.render_png(path, page, highlight=tuple(bbox) if bbox else None, zoom=zoom)
    if not bbox:
        return png
    img = Image.open(io.BytesIO(png)).convert("RGB")
    y0, y1 = max(0, int((bbox[1] - margin) * zoom)), min(img.height, int((bbox[3] + margin) * zoom))
    buf = io.BytesIO()
    img.crop((0, y0, img.width, y1)).save(buf, format="PNG")
    return buf.getvalue()


def sample(pdf: Path, fy: int | None, per_kind: int, seed: int, out: Path) -> dict:
    if holdout.holdout_reason(pdf):
        raise SystemExit("ไฟล์นี้อยู่ในหน่วยที่กันไว้ — ไม่สุ่ม")
    n = len(reader.page_texts(pdf))
    texts = reader.page_texts(pdf)
    bf = ex.extract(reader.page_words(pdf, list(range(1, n + 1))), fiscal_year=fy)
    from redbook.services.pdfpair import _locate_year, year_texts
    ye = ex.detect_year(year_texts(pdf, n, 1), 1)
    bf.year_evidence = _locate_year(pdf, ye.evidence)
    rng = random.Random(f"{seed}:{pdf.name}")
    rows = []
    for kind, recs in _records(bf).items():
        for r in rng.sample(recs, min(per_kind, len(recs))):
            rows.append({"kind": kind, "kind_label": KIND_LABELS[kind], **r})
    d = out / pdf.stem
    d.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(rows, 1):
        r["no"] = i
        r["crop"] = f"crop_{i:02d}.png"
        (d / r["crop"]).write_bytes(_crop(pdf, r["page"], r["bbox"]))
    man = {"file": pdf.name, "sha256": sha256_file(pdf), "fiscal_year": fy, "seed": seed, "per_kind": per_kind,
           "versions": {"pdfbook": PDFBOOK_VERSION, "profile": profile.PROFILE_VERSION},
           "population": {k: len(v) for k, v in _records(bf).items()}, "rows": rows}
    (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", nargs="+", required=True)
    ap.add_argument("--fy", type=int, nargs="+", required=True, help="ปีงบของแต่ละไฟล์ (ตามลำดับ --pdf)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-kind", type=int, default=1)
    ap.add_argument("--seed", type=int, default=20261023)
    a = ap.parse_args()
    if len(a.fy) != len(a.pdf):
        ap.error("--fy ต้องมีเท่าจำนวน --pdf")
    for p, fy in zip(a.pdf, a.fy):
        m = sample(Path(p), fy, a.per_kind, a.seed, Path(a.out))
        print(f"{m['file']}: {len(m['rows'])} รายการ · จากทั้งหมด {m['population']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
