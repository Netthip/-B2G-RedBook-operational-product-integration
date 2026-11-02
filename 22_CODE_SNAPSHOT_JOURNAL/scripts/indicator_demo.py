# -*- coding: utf-8 -*-
"""สาธิตทะเบียนตัวชี้วัด + การเปิดหลักฐาน PDF เก่า/ใหม่ ด้วยชุดสังเคราะห์

ลงทะเบียน PDF สังเคราะห์สองฉบับ (content hash) → รันตัวสกัด+เสนอคู่ → พิมพ์ run_id
และ route สำหรับเปิดในเบราว์เซอร์ · ใช้ฐานข้อมูลของแอป (``REDBOOK_DATA_DIR``)

🔴 **SYNTHETIC TEST FIXTURE** — ผลที่ได้ไม่ใช่ข้อค้นพบในเอกสารจริง และไม่ใช่ผลประเมิน
🔴 เดโม **ไม่สร้างและไม่ผนึกเฉลย** — ขั้นตัดสินหลังรันและชุดส่งออกจึงถูกล็อกไว้ตาม B4

ใช้: .venv\\Scripts\\python.exe scripts\\indicator_demo.py [--package]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from redbook import config                                   # noqa: E402
from redbook.evidence import documents as docs               # noqa: E402
from redbook.services import evidence as svc                 # noqa: E402
from redbook.storage.db import init_db                       # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "synthetic_pdf"


def main() -> None:
    config.ensure_dirs()
    init_db()
    svc.init_schemas()
    old = svc.register_pdf(
        FIX / "synthetic_old_fy2569.pdf", title="เอกสารสังเคราะห์ ฉบับเก่า (ปี 2569)",
        stage=docs.STAGE_DRAFT_BILL, fiscal_year=2569, authority="SYNTHETIC",
        agency_label="สถาบันทดสอบสังเคราะห์", version_label="synthetic-old-1",
        disclosure_class=docs.DISC_SYNTHETIC, registered_by="indicator_demo")
    new = svc.register_pdf(
        FIX / "synthetic_new_fy2570.pdf", title="เอกสารสังเคราะห์ ฉบับใหม่ (ปี 2570)",
        stage=docs.STAGE_DRAFT_BILL, fiscal_year=2570, authority="SYNTHETIC",
        agency_label="สถาบันทดสอบสังเคราะห์", version_label="synthetic-new-1",
        disclosure_class=docs.DISC_SYNTHETIC, registered_by="indicator_demo")
    res = svc.run_indicator_pipeline(old.document_id, new.document_id,
                                     note="synthetic demo", label="SYNTHETIC DEMO")
    out = {
        "old_document_id": old.document_id, "old_sha256": old.content_sha256,
        "old_text_layer": old.text_layer_status,
        "new_document_id": new.document_id, "new_sha256": new.content_sha256,
        "new_text_layer": new.text_layer_status,
        "run_id": res.run_id, "n_old": res.n_old, "n_new": res.n_new,
        "n_pairs": res.n_pairs, "by_status": res.by_status,
        "accounted_closed": res.accounted["closed"], "text_backend": res.text_backend,
        "stage": svc.stage_of(res.run_id),
        "adjudication_unlocked": svc.adjudication_unlocked(res.run_id),
        "backend_evidence": svc.backend_evidence(),
        "routes": {
            "report": f"/indicators/runs/{res.run_id}",
            "key_build_verify": f"/indicators/runs/{res.run_id}/keybuild",
            "post_run_adjudication": f"/indicators/runs/{res.run_id}/verify",
            "old_page2": svc.evidence_url(old.document_id, 2, run_id=res.run_id),
            "new_page3": svc.evidence_url(new.document_id, 3, run_id=res.run_id),
        },
    }
    if "--package" in sys.argv:
        # 🔴 B4 — ชุดตัดสินหลังรันสร้างได้หลังเฉลยถูกผนึกเท่านั้น · เดโมจึงไม่สร้างให้เอง
        rv = svc.run_view(res.run_id)
        if not svc.adjudication_unlocked(res.run_id):
            out["package"] = {"blocked": svc.ADJUDICATION_LOCKED,
                              "next": out["routes"]["key_build_verify"]}
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return
        pkg = svc.write_package(rv, config.EXPORT_DIR, prepared_by="indicator_demo")
        out["package"] = {"package_id": pkg.package_id, "rows": pkg.rows,
                          "xlsx": pkg.xlsx_path.name}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
