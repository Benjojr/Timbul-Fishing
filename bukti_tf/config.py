"""Lokasi Tesseract: bawaan aplikasi (portabel) -> PATH sistem -> lokasi instalasi default."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Tuple

_DEFAULT_INSTALL = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def locate_tesseract() -> Tuple[str, Optional[str]]:
    base = _base_dir()
    for folder in (base / "tesseract", base / "vendor" / "tesseract"):
        exe = folder / "tesseract.exe"
        if exe.exists():
            tessdata = folder / "tessdata"
            return str(exe), (str(tessdata) if tessdata.exists() else None)
    found = shutil.which("tesseract")
    return (found or _DEFAULT_INSTALL), None


def data_dir() -> Path:
    """
    Folder data pengguna (database rekap). Sengaja di luar folder aplikasi supaya
    tidak hilang saat build ulang atau saat folder exe diganti versi baru.
    Windows: %APPDATA%\\ScannerBuktiTF
    """
    root = os.environ.get("APPDATA")
    base = Path(root) / "ScannerBuktiTF" if root else Path.home() / ".scanner_bukti_tf"
    base.mkdir(parents=True, exist_ok=True)
    return base


DB_NAME = "rekap.tfdata"        # file data khusus Scanner Bukti TF
LEGACY_DB_NAME = "rekap.db"     # nama lama (SQLite biasa)


def database_path(folder: Optional[Path] = None) -> Path:
    """
    Lokasi file data aplikasi. Bila hanya ada file lama `rekap.db`, isinya disalin sekali
    ke `rekap.tfdata`; file lama dibiarkan sebagai cadangan.
    """
    folder = folder or data_dir()
    new, old = folder / DB_NAME, folder / LEGACY_DB_NAME
    if not new.exists() and old.exists():
        shutil.copy2(old, new)
    return new
