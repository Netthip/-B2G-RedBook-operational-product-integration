# -*- coding: utf-8 -*-
"""เริ่มเว็บแอปบนเครื่องผู้ใช้

ผูกกับ 127.0.0.1 เท่านั้น เครื่องอื่นในเครือข่ายเรียกไม่ได้
ต้องการเปลี่ยนพอร์ตให้ตั้ง environment variable REDBOOK_PORT
"""
import sys

import uvicorn

from redbook import config
from redbook.web.launch import uvicorn_options


def _use_utf8_console() -> None:
    """คอนโซล Windows ภาษาไทยใช้ code page 874 ซึ่งพิมพ์อักขระบางตัวไม่ได้

    ปรับ stdout/stderr เป็น UTF-8 เพื่อไม่ให้โปรแกรมล้มเพราะข้อความบนหน้าจอ
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main() -> None:
    _use_utf8_console()
    config.ensure_dirs()
    print(f"RedBook Verify: http://{config.BIND_HOST}:{config.BIND_PORT}")
    print(f"data dir: {config.DATA_DIR}")
    uvicorn.run("redbook.app:app", host=config.BIND_HOST, port=config.BIND_PORT,
                **uvicorn_options())


if __name__ == "__main__":
    main()
