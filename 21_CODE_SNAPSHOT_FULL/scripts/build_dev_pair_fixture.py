# -*- coding: utf-8 -*-
"""DEV fixture รูปแบบสัญญา #27 — ใช้สาธิตหน้าคู่ ร่าง ↔ พ.ร.บ. ระหว่างที่ทะเบียนจริงยังไม่มี พ.ร.บ./pairs

    python scripts/build_dev_pair_fixture.py                   # → .data_demo/dev_pair_fixture.json
    set REDBOOK_BOOK_CATALOG=.data_demo\\dev_pair_fixture.json  # แล้วเปิด demo server

กติกา (#24 · ห้ามเดาคู่ใน UI · Gift D4 แยกเอกสารสาธารณะออกจากข้อมูลสังเคราะห์)
- ไฟล์นี้ **ไม่ใช่ทะเบียนจริง** — ประกาศ ``"fixture": {"synthetic": true}`` ทุกหน้าจึงติดป้าย DEV
- เล่ม ร่าง พ.ร.บ. = แปลงจากทะเบียนสาธารณะ ``redbook/data/book_catalog.json`` (ลิงก์ทางการเดิม)
- เล่ม พ.ร.บ. = **แต่งขึ้น** · รหัสขึ้นต้น ``DEV-`` · ไม่มี URL · ไม่มีภาพปก · ชื่อมีคำว่า "ข้อมูลสังเคราะห์"
- ``pairs[]`` = แต่งขึ้นเพื่อให้เห็นทุกสถานะ (MATCHED / REVIEW_REQUIRED / CANNOT_DETERMINE)
  ไม่ได้มาจากการจับคู่ของ #27 และไม่ใช่ข้อเท็จจริงว่าเล่มใดคู่กัน
- ไม่มีตัวเลขเงิน ไม่มีข้อมูลภายใน ไม่ออกเน็ต
UI อ่านไฟล์นี้ผ่าน adapter เดิม (``books.load`` → สัญญา #27) — ไม่มี logic จับคู่ใน UI
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "redbook" / "data" / "book_catalog.json"
OUT = ROOT / ".data_demo" / "dev_pair_fixture.json"
SYN = "ข้อมูลสังเคราะห์"

#: เล่มที่ใช้สาธิต — (หน่วยรับงบ, ปีที่มี พ.ร.บ. สังเคราะห์, สถานะคู่ SAME_YEAR)
ACT_DEMO = [("กระทรวงสาธารณสุข", 2570, "MATCHED"),
            ("กระทรวงสาธารณสุข", 2569, "REVIEW_REQUIRED"),
            ("กระทรวงศึกษาธิการ", 2570, "CANNOT_DETERMINE")]
#: คู่ปีต่อปีสังเคราะห์ — (หน่วยรับงบ, ปีก่อน, ปีหลัง, สถานะ)
YEAR_DEMO = [("กระทรวงสาธารณสุข", 2569, 2570, "MATCHED"),
             ("กระทรวงสาธารณสุข", 2568, 2569, "MATCHED"),
             ("กระทรวงศึกษาธิการ", 2569, 2570, "REVIEW_REQUIRED")]


def _doc(b: dict) -> dict:
    """เล่มสาธารณะหนึ่งเล่ม → รูป ``contract.documents[]`` ที่ ``books._contract_book`` อ่าน"""
    ok = (b.get("link_check") or {}).get("is_pdf")
    label = (f"ฉบับที่ {b['doc_no']}" if b.get("doc_no") else "") + (f" เล่มที่ {b['volume']}" if b.get("volume") else "")
    return {"id": b["id"], "year": b["fiscal_year"], "stage": "DRAFT", "stage_label": "ร่าง พ.ร.บ.",
            "book_title": b["title"], "book_label": label.strip(), "doc_type": b["doc_type"],
            "doc_type_label": b.get("doc_type_label", ""), "ministry": b.get("ministries") or [],
            "pdf": {"url": b.get("pdf_url", ""), "status": "FOUND" if ok else "UNCHECKED"},
            "excel": {"urls": [], "status": "UNCHECKED"},
            "source_status": {"source_page_url": b.get("source_page", ""),
                              "verified_date": (b.get("retrieved_at") or "")[:10]}}


def _find(docs: list[dict], ministry: str, year: int) -> dict:
    hit = [d for d in docs if d["stage"] == "DRAFT" and d["year"] == year and d["doc_type"] == "expenditure_by_ministry"
           and d["ministry"] == [ministry]]
    if len(hit) != 1:
        sys.exit(f"ไม่พบเล่มฐานที่ชัดเจน ({len(hit)}): {ministry} {year}")
    return hit[0]


def build(src: Path = SRC) -> dict:
    raw = json.loads(src.read_text(encoding="utf-8"))
    docs = [_doc(b) for b in raw["books"]]
    pairs = []
    for ministry, year, status in ACT_DEMO:
        draft = _find(docs, ministry, year)
        act = {**draft, "id": f"DEV-ACT-{draft['id']}", "stage": "ACT", "stage_label": "พ.ร.บ.",
               "book_title": f"[{SYN}] {draft['book_title']}", "agency": SYN, "synthetic": True,
               "pdf": {"url": "", "status": "NOT_FOUND"}, "excel": {"urls": [], "status": "NOT_LISTED"},
               "source_status": {"source_page_url": "", "verified_date": ""}}
        docs.append(act)
        pairs.append({"kind": "SAME_YEAR", "status": status,
                      "a": {"ids": [draft["id"]]}, "b": {"ids": [act["id"]]}, "synthetic": True})
    for ministry, y0, y1, status in YEAR_DEMO:
        pairs.append({"kind": "CROSS_YEAR", "status": status,
                      "a": {"ids": [_find(docs, ministry, y0)["id"]]},
                      "b": {"ids": [_find(docs, ministry, y1)["id"]]}, "synthetic": True})
    # รูปเดียวกับทะเบียนจริงของ #27 (850d582): contract_version + pairs[] อยู่ระดับบนสุด
    return {
        "fixture": {"synthetic": True, "purpose": "DEV — สาธิตหน้าคู่เอกสาร #24 (ส่วนผลตรวจ/เนื้อหา)",
                    "note": "เล่ม พ.ร.บ. (รหัส DEV-) และ pairs[] แต่งขึ้นทั้งหมด ไม่ใช่ข้อเท็จจริง"},
        "registry_version": "dev-fixture-0.2.0",
        "contract_version": "source-contract-0.1.0",
        "retrieved_at": raw.get("generated_at", ""),
        "pairs": pairs,
        "contract": {"version": "source-contract-0.1.0",
                     "source": f"DEV fixture · {SYN} (ร่าง พ.ร.บ. จากทะเบียนสาธารณะ)",
                     "documents": docs},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    data = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"เขียน {args.out} · เอกสาร {len(data['contract']['documents'])} · คู่ {len(data['pairs'])} (สังเคราะห์)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
