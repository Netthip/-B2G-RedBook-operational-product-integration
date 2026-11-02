# -*- coding: utf-8 -*-
"""ชุดพัฒนาเล่มจริง (PDF ↔ PDF) — ดาวน์โหลดเล่มจากเว็บสำนักงบประมาณ แล้วตัดเฉพาะหน้าของหน่วยงาน

    python scripts/fetch_dev_volumes.py <manifest.json> <out_dir> [--extract-only]

``manifest.json`` (เก็บนอก Git) ::

    {"volumes": [{"key": "V11_2570_draft", "page": "<หน้าเว็บ>", "url": "https://bb.go.th/download.php?id=…",
                  "fiscal_year": 2570, "stage": "draft", "label": "ฉบับที่ 3 เล่มที่ 11"}],
     "agencies": [{"pair": "D1", "name": "สถาบันรับรองคุณภาพสถานพยาบาล",
                   "volumes": ["V11_2570_draft", "V11_2570_act"]}]}

กติกา

* ดาวน์โหลดผ่าน ``fetch_source_pdfs.fetch_one`` — allowlist โฮสต์ bb.go.th + bbstore.bb.go.th (ที่เก็บไฟล์ทางการ) · https · ตรวจ redirect ทุกทอด ·
  ขึ้นต้นด้วย ``%PDF`` · จำกัดขนาด
* ตัดหน้าด้วย :func:`redbook.pdfbook.scope.find_by_toc` — อ่านเนื้อหาเฉพาะหน้าต้นเล่ม (สารบัญ) +
  แถบขอบหน้า (เลขหน้า) + หน้าของหน่วยงานนั้น · **ไม่อ่านเนื้อหาหน้าของหน่วยงานอื่น**
* บันทึก ``register.json``: URL ต้นทาง/ปลายทาง · เวลา · ขนาด · SHA-256 ของเล่มและไฟล์ที่ตัด ·
  ช่วงหน้า · หน้าที่อ่านเนื้อหาจริง
* อยู่นอกแพ็กเกจ ``redbook`` (แพ็กเกจห้ามโค้ดเครือข่าย · ห้ามคำสั่งบันทึกไฟล์)
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_source_pdfs as fsp  # noqa: E402
from redbook.pdfbook import scope as scope_mod  # noqa: E402

MAX_BYTES = 300 * 1024 * 1024
#: download.php ของ bb.go.th ส่งต่อ (302) ไปที่เก็บไฟล์ของสำนักงบประมาณเอง — https เท่านั้น
HOSTS = set(fsp.DEFAULT_HOSTS) | {"bbstore.bb.go.th"}


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def download(man: dict, out: Path, reg: dict, log=print) -> None:
    vdir = out / "volumes"
    vdir.mkdir(parents=True, exist_ok=True)
    for v in man["volumes"]:
        dest = vdir / f"{v['key']}.pdf"
        if dest.exists() and v["key"] in reg["volumes"]:
            log(f"[มีแล้ว] {v['key']}")
            continue
        data, final_url = fsp.fetch_one(v["url"], max_bytes=MAX_BYTES, hosts=HOSTS)
        dest.write_bytes(data)
        reg["volumes"][v["key"]] = {**v, "final_url": final_url, "retrieved_at": _now(),
                                    "size_bytes": len(data), "sha256": _sha(dest)}
        log(f"[ดาวน์โหลด] {v['key']}: {len(data):,} ไบต์")


def extract(man: dict, out: Path, reg: dict, log=print) -> None:
    import pypdfium2
    edir = out / "extracts"
    edir.mkdir(parents=True, exist_ok=True)
    vols = {v["key"]: v for v in man["volumes"]}
    for ag in man["agencies"]:
        for side, vkey in zip("AB", ag["volumes"]):
            src = out / "volumes" / f"{vkey}.pdf"
            key = f"{ag['pair']}_{side}_{vkey}"
            try:
                sc, read = scope_mod.find_by_toc(src, ag["name"])
            except scope_mod.ScopeError as e:
                reg["extracts"][key] = {"pair": ag["pair"], "agency": ag["name"], "volume": vkey,
                                        "error": str(e)}
                log(f"[หาช่วงหน้าไม่ได้] {key}: {e}")
                continue
            doc = pypdfium2.PdfDocument(str(src))
            new = pypdfium2.PdfDocument.new()
            try:
                new.import_pages(doc, list(range(sc.first - 1, sc.last)))
                dest = edir / f"{key}.pdf"
                new.save(str(dest))
            finally:
                new.close()
                doc.close()
            v = vols[vkey]
            reg["extracts"][key] = {
                "pair": ag["pair"], "agency": ag["name"], "side": side, "volume": vkey,
                "fiscal_year": v["fiscal_year"], "stage": v["stage"],
                "source_sha256": reg["volumes"].get(vkey, {}).get("sha256", _sha(src)),
                "pdf_pages": [sc.first, sc.last], "method": sc.method,
                "content_pages_read": sorted(set(read)), "extract_sha256": _sha(dest),
                "extracted_at": _now()}
            log(f"[ตัดแล้ว] {key}: หน้า {sc.first}–{sc.last}")


def main(argv) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    man = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    out = Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    regp = out / "register.json"
    reg = json.loads(regp.read_text(encoding="utf-8")) if regp.exists() else {"volumes": {}, "extracts": {}}
    try:
        if "--extract-only" not in argv:
            download(man, out, reg)
        extract(man, out, reg)
    finally:
        regp.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
