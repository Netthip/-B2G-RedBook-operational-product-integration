# -*- coding: utf-8 -*-
"""เขียน XLSX จากแผ่นข้อมูลที่ **ผ่านการกันสูตรแล้ว** — ไม่รู้จัก finding ไม่รู้จัก decision

รับเพียง ``sheets = [(ชื่อชีต, [[cell, ...], ...]), ...]`` โดยแต่ละ cell เป็น
``("s", text, bold)`` สำหรับข้อความ (บังคับเป็น text · number_format "@")
หรือ ``("n", number, bold)`` สำหรับตัวเลข · ผู้เรียกต้อง neutralize ข้อความมาก่อน
"""
from __future__ import annotations

from pathlib import Path


def write_xlsx(path, sheets) -> None:
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, rows in sheets:
        ws = wb.create_sheet(title[:31])
        for r, row in enumerate(rows, 1):
            for c, cell in enumerate(row, 1):
                kind, value, bold = cell
                x = ws.cell(row=r, column=c, value=value)
                if kind == "s":
                    x.data_type = "s"
                    x.number_format = "@"
                if bold:
                    x.font = Font(bold=True)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    wb.close()


__all__ = ["write_xlsx"]
