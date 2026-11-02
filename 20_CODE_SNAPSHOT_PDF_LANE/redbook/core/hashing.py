# -*- coding: utf-8 -*-
"""ลายนิ้วมือไฟล์และสายโซ่แฮชของ Audit Trail"""
import hashlib
from pathlib import Path

CHUNK = 1024 * 1024


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(Path(path), "rb") as fp:
        while True:
            block = fp.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
