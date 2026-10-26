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


APP_NAME = "Timbul Fishing"
_FOLDER = "TimbulFishing"
_OLD_FOLDER = "ScannerBuktiTF"      # nama folder data versi lama


def data_dir() -> Path:
    """
    Folder data pengguna (database rekap, log). Sengaja di luar folder aplikasi supaya
    tidak hilang saat build ulang atau saat folder exe diganti versi baru.
    Windows: %APPDATA%\\TimbulFishing. Data dari folder lama (ScannerBuktiTF) disalin sekali.
    """
    root = os.environ.get("APPDATA")
    parent = Path(root) if root else Path.home() / ".config"
    base = parent / _FOLDER
    old = parent / _OLD_FOLDER
    if not base.exists() and old.exists():
        shutil.copytree(old, base)   # salin, bukan pindah: folder lama tetap jadi cadangan
    base.mkdir(parents=True, exist_ok=True)
    return base


DB_NAME = "rekap.tfdata"        # file data Timbul Fishing
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

def receipts_dir() -> Path:
    """
    Folder gambar bukti transfer: %APPDATA%\\TimbulFishing\\bukti (di samping database).
    Bisa dipindah dengan mengisi variabel lingkungan TIMBULFISHING_BUKTI_DIR.
    """
    override = os.environ.get("TIMBULFISHING_BUKTI_DIR")
    folder = Path(override) if override else data_dir() / "bukti"
    folder.mkdir(parents=True, exist_ok=True)
    return folder
