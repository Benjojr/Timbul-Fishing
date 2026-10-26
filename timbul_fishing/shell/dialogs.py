"""Pesan untuk pengguna yang tetap terlihat pada exe --noconsole (print tidak akan terlihat)."""
from __future__ import annotations

import logging
import sys

from timbul_fishing.config import APP_NAME


def show(text: str, error: bool = True) -> None:
    logging.log(logging.ERROR if error else logging.INFO, text)
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, 0x10 if error else 0x40)
    else:
        print(text, file=sys.stderr)


def die(text: str) -> None:
    show(text)
    raise SystemExit(1)
