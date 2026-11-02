# -*- coding: utf-8 -*-
"""ทะเบียนเอกสาร — ตัวตน = content hash · ไม่ใช่ชื่อไฟล์ (Gate 1 ข้อ 1)

🔴 **SYNTHETIC TEST FIXTURE** — PDF ทั้งสองแต่งขึ้น (``tests/fixtures/synthetic_pdf``)
"""
import dataclasses
import json
from pathlib import Path

import pytest

from redbook.evidence import documents as docs
from redbook.evidence import pdftext

FIX = Path(__file__).resolve().parent / "fixtures" / "synthetic_pdf"
OLD = FIX / "synthetic_old_fy2569.pdf"
NEW = FIX / "synthetic_new_fy2570.pdf"


@pytest.fixture()
def db(fresh_db):
    docs.init_schema(fresh_db)
    return fresh_db


def test_same_content_different_names_is_one_document(db, tmp_path):
    copy = tmp_path / "ชื่ออื่น_คนละชื่อ.pdf"
    copy.write_bytes(OLD.read_bytes())
    a, created_a = docs.register(OLD, media_type=docs.MEDIA_PDF, stage=docs.STAGE_DRAFT_BILL,
                                 disclosure_class=docs.DISC_SYNTHETIC, db_path=db)
    b, created_b = docs.register(copy, media_type=docs.MEDIA_PDF, stage=docs.STAGE_ENACTED_ACT,
                                 disclosure_class=docs.DISC_PUBLIC, db_path=db)
    assert created_a and not created_b
    assert a.document_id == b.document_id
    # metadata ที่ประกาศครั้งแรก **ไม่ถูกเขียนทับ**
    assert b.stage == docs.STAGE_DRAFT_BILL and b.disclosure_class == docs.DISC_SYNTHETIC
    assert set(docs.aliases(a.document_id, db)) == {OLD.name, copy.name}
    assert len(docs.list_all(db)) == 1


def test_same_name_different_content_is_two_documents(db, tmp_path):
    d1, d2 = tmp_path / "a", tmp_path / "b"
    d1.mkdir(), d2.mkdir()
    (d1 / "same.pdf").write_bytes(OLD.read_bytes())
    (d2 / "same.pdf").write_bytes(NEW.read_bytes())
    a, _ = docs.register(d1 / "same.pdf", media_type=docs.MEDIA_PDF, db_path=db)
    b, _ = docs.register(d2 / "same.pdf", media_type=docs.MEDIA_PDF, db_path=db)
    assert a.document_id != b.document_id
    assert a.document_id == "doc_" + a.content_sha256[:16]


def test_unknown_stage_and_disclosure_fail_closed(db):
    with pytest.raises(ValueError):
        docs.register(OLD, media_type=docs.MEDIA_PDF, stage="GUESSED", db_path=db)
    rec, _ = docs.register(OLD, media_type=docs.MEDIA_PDF, db_path=db)
    assert rec.stage == docs.STAGE_UNSPECIFIED
    assert rec.disclosure_class == docs.DISC_UNKNOWN
    assert rec.shareable is False, "ไม่ประกาศชั้นการเปิดเผย = เผยแพร่ไม่ได้"


def test_public_record_has_no_path_field(db):
    rec, _ = docs.register(OLD, media_type=docs.MEDIA_PDF, db_path=db)
    names = {f.name for f in dataclasses.fields(rec)}
    assert "local_path_private" not in names
    assert not any("path" in n for n in names)
    assert str(FIX) not in json.dumps(dataclasses.asdict(rec), ensure_ascii=False)


def test_private_path_verifies_hash_and_reports_missing(db, tmp_path):
    p = tmp_path / "moving.pdf"
    p.write_bytes(NEW.read_bytes())
    rec, _ = docs.register(p, media_type=docs.MEDIA_PDF, db_path=db)
    assert docs.open_path_private(rec.document_id, db_path=db) == p.resolve()
    p.write_bytes(OLD.read_bytes())          # ไฟล์ถูกแทนที่หลังลงทะเบียน
    with pytest.raises(docs.SourceUnavailable) as ei:
        docs.open_path_private(rec.document_id, db_path=db)
    assert ei.value.reason == docs.REASON_HASH_MISMATCH
    p.unlink()
    with pytest.raises(docs.SourceUnavailable) as ei2:
        docs.open_path_private(rec.document_id, db_path=db)
    assert ei2.value.reason == docs.REASON_MISSING
    with pytest.raises(docs.SourceUnavailable):
        docs.open_path_private("doc_0000000000000000", db_path=db)


def test_registration_does_not_modify_source_file(db):
    before = docs.sha256_file(OLD)
    docs.register(OLD, media_type=docs.MEDIA_PDF, db_path=db)
    assert docs.sha256_file(OLD) == before


def test_text_layer_status_distinguishes_absent_partial_present():
    backend = pdftext.get_backend()
    if backend is None:
        pytest.skip(pdftext.NO_TEXT_BACKEND)
    old_pages = backend.pages(OLD)
    new_pages = backend.pages(NEW)
    assert pdftext.text_layer_status(old_pages) == pdftext.TEXT_LAYER_PARTIAL
    assert pdftext.text_layer_status(new_pages) == pdftext.TEXT_LAYER_PRESENT
    assert [p.page for p in old_pages if not p.has_text_layer] == [4]
    assert pdftext.text_layer_status(None) == pdftext.TEXT_LAYER_NOT_CHECKED
    assert pdftext.text_layer_status([]) == pdftext.TEXT_LAYER_ABSENT


def test_no_backend_is_reported_not_silent(monkeypatch):
    """ไม่มีไลบรารี ⇒ ต้องบอกว่า NO_TEXT_BACKEND ไม่ใช่ 'ไม่พบข้อความ'"""
    monkeypatch.setattr(pdftext, "_BACKEND_CACHE", {"product": None})
    assert pdftext.product_backend() is None
    assert pdftext.get_backend() is None
    assert pdftext.backend_name() == pdftext.NO_TEXT_BACKEND


# ══════════════════════════════════════════════════════════════════════════════
#  H1 — ตัวตนของเอกสารพิสูจน์ด้วยแฮชเต็ม · id 16 hex เป็นเพียงฉลาก
# ══════════════════════════════════════════════════════════════════════════════

def test_document_id_requires_a_full_digest():
    with pytest.raises(ValueError):
        docs.document_id_for("a" * 16)
    assert docs.document_id_for("a" * 64) == "doc_" + "a" * 16


def test_lookup_by_full_hash_and_identity_verification(db):
    rec, _ = docs.register(OLD, media_type=docs.MEDIA_PDF,
                           disclosure_class=docs.DISC_SYNTHETIC, db_path=db)
    assert docs.get_by_sha256(rec.content_sha256, db).document_id == rec.document_id
    assert docs.get_by_sha256("f" * 64, db) is None
    assert docs.verify_identity(rec.document_id, rec.content_sha256, db) is True
    assert docs.verify_identity(rec.document_id, "f" * 64, db) is False


def test_id_label_collision_is_refused_not_silently_merged(db, tmp_path):
    """🔴 H1 — ฉลาก 16 hex ชนกันแต่แฮชเต็มต่าง ⇒ ต้องปฏิเสธ ไม่กลืนเป็นเอกสารเดียว

    สร้างสถานการณ์ด้วยการใส่แถวที่มี ``document_id`` เดียวกันแต่แฮชเต็มคนละค่าลงฐานข้อมูล
    ตรง ๆ (แฮชชนจริงสร้างไม่ได้) แล้วพิสูจน์ว่า ``register`` ปฏิเสธ
    """
    import sqlite3

    real, _ = docs.register(OLD, media_type=docs.MEDIA_PDF,
                            disclosure_class=docs.DISC_SYNTHETIC, db_path=db)
    conn = sqlite3.connect(db)
    try:
        conn.execute("DELETE FROM evd_document_aliases WHERE document_id = ?",
                     (real.document_id,))
        conn.execute("UPDATE evd_documents SET content_sha256 = ? WHERE document_id = ?",
                     ("9" * 64, real.document_id))
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(docs.DocumentIdCollision) as ei:
        docs.register(OLD, media_type=docs.MEDIA_PDF,
                      disclosure_class=docs.DISC_SYNTHETIC, db_path=db)
    assert ei.value.document_id == real.document_id
    assert ei.value.existing_sha256 != ei.value.incoming_sha256
