# -*- coding: utf-8 -*-
"""#21 — ด่านกันเปิดชุดประเมินสุดท้าย

🔴 **SYNTHETIC TEST FIXTURE** — ทุกไฟล์สร้างในโฟลเดอร์ชั่วคราว ไม่ใช้ไฟล์ชุดประเมินจริง

**สายงานผลิตภัณฑ์ · `PRODUCT EVIDENCE — POST-FREEZE`**
"""
import builtins
import io
import json

import openpyxl
import pytest

from redbook import final_holdout as G
from redbook.adapters.ao_workbook import AOWorkbookAdapter
from redbook.readers import excel_reader
from redbook.storage import files as storage


@pytest.fixture
def env(tmp_path, monkeypatch):
    """data root ชั่วคราว · manifest ในตำแหน่งตั้งต้น · ไม่มี unlock"""
    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setenv(G.DATA_ROOT_ENV, str(root))
    monkeypatch.delenv(G.MANIFEST_ENV, raising=False)
    monkeypatch.delenv(G.UNLOCK_ENV, raising=False)
    return root


def _book(path, text="SYNTHETIC TEST FIXTURE"):
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    wb.active["A1"] = text
    wb.save(path)
    wb.close()
    return path


def _seal(root, *paths):
    sealed = root / G.SEALED_DIRNAME
    sealed.mkdir(exist_ok=True)
    (root / G.MANIFEST_NAME).write_text(json.dumps(
        {"sealed_sha256": [G.sha256_of(p) for p in paths]}), encoding="utf-8")
    return sealed


def _unlock(tmp_path, monkeypatch, hashes, **extra):
    rec = {"unlock_id": "U-TEST", "approved_by": "Gift", "engine_ref": "tag-test",
           "sealed_sha256": list(hashes)}
    rec.update(extra)
    p = tmp_path / "unlock.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    monkeypatch.setenv(G.UNLOCK_ENV, str(p))
    return p


# ══════════════════════════════════════════ ชั้นเส้นทาง

@pytest.mark.parametrize("parts", [
    ("FINAL_HOLDOUT_SEALED", "a.xlsx"),
    ("x", "final_holdout_sealed", "y", "a.xlsx"),
])
def test_sealed_path_is_detected_at_any_depth(tmp_path, parts):
    assert G.is_sealed_path(tmp_path.joinpath(*parts))


def test_sealed_path_is_refused_without_reading_a_byte(env, monkeypatch):
    target = _book(env / G.SEALED_DIRNAME / "a.xlsx")
    opened = []
    real_open = builtins.open

    def spy(file, *a, **k):
        if str(file).endswith("a.xlsx"):
            opened.append(file)
        return real_open(file, *a, **k)

    monkeypatch.setattr(builtins, "open", spy)
    with pytest.raises(G.SealedFinalHoldout) as ei:
        G.guard_file(target)
    assert ei.value.code == "sealed_path"
    assert opened == [], "ต้องปฏิเสธก่อนเปิดไฟล์"


@pytest.mark.parametrize("call", [
    lambda p: AOWorkbookAdapter().extract(p),
    lambda p: AOWorkbookAdapter().inspect(p),
    lambda p: excel_reader.open_readonly_pair(p),
    lambda p: storage.detect_kind(p),
])
def test_every_installed_entry_point_refuses_the_sealed_folder(env, call):
    target = _book(env / G.SEALED_DIRNAME / "XL_FY2570_draft-bill_99999_T.xlsx")
    _seal(env, target)
    with pytest.raises(G.SealedFinalHoldout):
        call(target)


# ══════════════════════════════════════════ ชั้นแฮช

def test_a_copy_elsewhere_is_refused_by_hash(env, tmp_path):
    original = _book(env / G.SEALED_DIRNAME / "a.xlsx")
    _seal(env, original)
    copy = tmp_path / "elsewhere" / "renamed.xlsx"
    copy.parent.mkdir()
    copy.write_bytes(original.read_bytes())
    with pytest.raises(G.SealedFinalHoldout) as ei:
        AOWorkbookAdapter().extract(copy)
    assert ei.value.code == "sealed_hash"


def test_upload_of_a_sealed_file_is_rejected(env, monkeypatch, tmp_path):
    original = _book(env / G.SEALED_DIRNAME / "a.xlsx")
    _seal(env, original)
    monkeypatch.setattr(storage.config, "TEMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(storage.config, "UPLOAD_DIR", tmp_path / "up")
    (tmp_path / "tmp").mkdir()
    (tmp_path / "up").mkdir()
    monkeypatch.setattr(storage.config, "ensure_dirs", lambda: None)
    with pytest.raises(storage.UploadRejected) as ei:
        storage.save_stream(io.BytesIO(original.read_bytes()), "anything.xlsx")
    assert ei.value.args[0] and "ชุดประเมิน" in str(ei.value)
    assert not any((tmp_path / "up").iterdir()), "ต้องไม่ถูกเก็บเข้าระบบ"


def test_ordinary_files_are_unaffected(env, tmp_path):
    other = _book(tmp_path / "dev" / "XL_FY2570_draft-bill_99999_D.xlsx", "อื่น")
    sealed = _book(env / G.SEALED_DIRNAME / "a.xlsx")
    _seal(env, sealed)
    assert AOWorkbookAdapter().extract(other)


def test_nothing_sealed_yet_means_nothing_is_blocked(env, tmp_path):
    other = _book(tmp_path / "XL_FY2570_draft-bill_99999_D.xlsx")
    assert G.sealed_hashes() == frozenset()
    assert AOWorkbookAdapter().extract(other)


# ══════════════════════════════════════════ fail-closed

def test_corrupt_manifest_fails_closed(env, tmp_path):
    (env / G.MANIFEST_NAME).write_text("{not json", encoding="utf-8")
    other = _book(tmp_path / "XL_FY2570_draft-bill_99999_D.xlsx")
    with pytest.raises(G.SealedFinalHoldout) as ei:
        AOWorkbookAdapter().extract(other)
    assert ei.value.code == "sealed_manifest_unreadable"


def test_sealed_folder_without_manifest_fails_closed(env, tmp_path):
    (env / G.SEALED_DIRNAME).mkdir()
    other = _book(tmp_path / "XL_FY2570_draft-bill_99999_D.xlsx")
    with pytest.raises(G.SealedFinalHoldout) as ei:
        AOWorkbookAdapter().extract(other)
    assert ei.value.code == "sealed_manifest_missing"


def test_manifest_with_bad_hash_list_fails_closed(env, tmp_path):
    (env / G.MANIFEST_NAME).write_text(json.dumps({"sealed_sha256": ["short"]}),
                                       encoding="utf-8")
    with pytest.raises(G.SealedFinalHoldout):
        G.sealed_hashes()


# ══════════════════════════════════════════ unlock

def test_unlock_for_a_different_file_does_not_open_this_one(env, tmp_path, monkeypatch):
    a = _book(env / G.SEALED_DIRNAME / "a.xlsx", "ก")
    b = _book(env / G.SEALED_DIRNAME / "b.xlsx", "ข")
    _seal(env, a, b)
    _unlock(tmp_path, monkeypatch, [G.sha256_of(a)])
    with pytest.raises(G.SealedFinalHoldout) as ei:
        G.guard_file(b)
    assert ei.value.code == "unlock_mismatch"


def test_matching_unlock_opens_and_leaves_an_access_record(env, tmp_path, monkeypatch):
    a = _book(env / G.SEALED_DIRNAME / "XL_FY2570_draft-bill_99999_S.xlsx")
    _seal(env, a)
    _unlock(tmp_path, monkeypatch, [G.sha256_of(a)])
    assert AOWorkbookAdapter().extract(a)
    log = (env / G.ACCESS_LOG_NAME).read_text(encoding="utf-8").splitlines()
    assert log
    entry = json.loads(log[-1])
    assert entry["sha256"] == G.sha256_of(a) and entry["unlock_id"] == "U-TEST"


def test_incomplete_unlock_is_refused(env, tmp_path, monkeypatch):
    a = _book(env / G.SEALED_DIRNAME / "a.xlsx")
    _seal(env, a)
    _unlock(tmp_path, monkeypatch, [G.sha256_of(a)], approved_by="")
    with pytest.raises(G.SealedFinalHoldout) as ei:
        G.guard_file(a)
    assert ei.value.code == "unlock_incomplete"


# ══════════════════════════════════════════ REVIEW ของ Bo (#21) — manifest ที่ระบุชัดแต่หาย

@pytest.fixture
def explicit_missing_manifest(tmp_path, monkeypatch):
    """ระบุ manifest ชัดเจน แต่ไฟล์ไม่มี · ไม่มี data root/โฟลเดอร์ปิดผนึกให้ตรวจพบ"""
    monkeypatch.delenv(G.DATA_ROOT_ENV, raising=False)
    monkeypatch.delenv(G.UNLOCK_ENV, raising=False)
    monkeypatch.setenv(G.MANIFEST_ENV, str(tmp_path / "gone" / "manifest.json"))


def test_explicit_manifest_that_is_missing_fails_closed(explicit_missing_manifest):
    with pytest.raises(G.SealedFinalHoldout) as ei:
        G.sealed_hashes()
    assert ei.value.code == "sealed_manifest_missing"


def test_copied_file_is_not_let_through_when_explicit_manifest_is_missing(
        explicit_missing_manifest, tmp_path):
    copy = _book(tmp_path / "elsewhere" / "XL_FY2570_draft-bill_99999_C.xlsx")
    with pytest.raises(G.SealedFinalHoldout):
        AOWorkbookAdapter().extract(copy)


def test_upload_is_rejected_when_explicit_manifest_is_missing(
        explicit_missing_manifest, monkeypatch, tmp_path):
    src = _book(tmp_path / "src.xlsx")
    for d in ("tmp", "up"):
        (tmp_path / d).mkdir()
    monkeypatch.setattr(storage.config, "TEMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(storage.config, "UPLOAD_DIR", tmp_path / "up")
    monkeypatch.setattr(storage.config, "ensure_dirs", lambda: None)
    with pytest.raises(storage.UploadRejected):
        storage.save_stream(io.BytesIO(src.read_bytes()), "x.xlsx")
    assert not any((tmp_path / "up").iterdir())


def test_not_configured_at_all_still_means_nothing_sealed(tmp_path, monkeypatch):
    """ยังไม่ตั้งค่าอะไรเลย (ไม่มี env ทั้งสอง) ⇒ ยังไม่มีการปิดผนึก ⇒ ไม่บล็อก"""
    for k in (G.DATA_ROOT_ENV, G.MANIFEST_ENV, G.UNLOCK_ENV):
        monkeypatch.delenv(k, raising=False)
    assert G.sealed_hashes() == frozenset()
