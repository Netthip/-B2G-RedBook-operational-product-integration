# -*- coding: utf-8 -*-
"""JSON ของคลังเล่มงบประมาณสำหรับหน้าบ้าน Svelte (/r/lib) — อ่านอย่างเดียวจากทะเบียนเล่มเดิม (services/books)

* ไม่เปลี่ยนสถานะ · ไม่อ่านไฟล์ PDF · ไม่ส่ง path ในเครื่อง — ส่งเฉพาะ metadata และลิงก์หน้าเผยแพร่ทางการตามทะเบียน
* หน้าคลังเล่มเดิม (/books, Jinja) ยังอยู่บนแอปเต็มตามเดิม
"""
from __future__ import annotations

from fastapi import Request

from ..services import books as book_service
from .api_common import ApiError, api


def _book(b) -> dict:
    return {"id": b.id, "fiscal_year": b.fiscal_year, "title": b.title, "headline": b.headline, "kicker": b.kicker,
            "stage": b.stage_code, "stage_label": b.stage_label, "type_group": b.type_group,
            "type_group_label": b.type_group_label, "volume": b.volume, "ministries": list(b.ministries),
            "posted": b.posted, "source_page": b.source_page, "pdf_url": b.pdf_url if b.pdf_openable else "",
            "stripe_color": b.stripe_color, "synthetic": b.synthetic}


def register(app) -> None:
    @app.get("/api/books")
    @api
    def api_books(request: Request):
        try:
            cat = book_service.catalog()
        except Exception:                      # ไฟล์ทะเบียนหาย/อ่านไม่ได้ — ไม่ส่งรายละเอียดภายใน
            raise ApiError("โหลดทะเบียนเล่มไม่สำเร็จ", 503, "server")
        return {"years": list(cat.years), "generated_at": cat.generated_at, "source": cat.source,
                "synthetic": cat.synthetic, "books": [_book(b) for b in cat.books if not b.sample_label]}


__all__ = ["register"]
