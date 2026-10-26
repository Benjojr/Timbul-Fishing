"""Cadangan harian file data. Tidak pernah melempar error: gagal backup tidak boleh menghalangi aplikasi."""
from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)
_PREFIX, _SUFFIX = "rekap-", ".tfdata"


def backup_database(db_path, keep: int = 14, today: Optional[date] = None) -> Optional[Path]:
    """
    Salin file data ke `backups/rekap-YYYYMMDD.tfdata` (satu per hari, diambil saat aplikasi
    pertama dibuka hari itu, jadi berisi kondisi akhir kemarin). Simpan `keep` terbaru.
    Memakai API backup SQLite, jadi aman walau file sedang terbuka. Mengembalikan path
    cadangan baru, atau None bila tidak ada yang dibuat.
    """
    src = Path(db_path)
    if not src.exists() or src.stat().st_size == 0:
        return None
    folder = src.parent / "backups"
    target = folder / f"{_PREFIX}{(today or date.today()):%Y%m%d}{_SUFFIX}"
    if target.exists():
        return None
    tmp = target.with_suffix(".tmp")
    try:
        folder.mkdir(exist_ok=True)
        tmp.unlink(missing_ok=True)
        with closing(sqlite3.connect(src)) as con:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                log.error("File data gagal pemeriksaan integritas; backup dilewati.")
                return None
            with closing(sqlite3.connect(tmp)) as dst:
                con.backup(dst)
        os.replace(tmp, target)
        _prune(folder, keep)
        return target
    except (sqlite3.Error, OSError):
        log.exception("Backup gagal")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def _prune(folder: Path, keep: int) -> None:
    for old in sorted(folder.glob(f"{_PREFIX}*{_SUFFIX}"))[:-keep]:
        try:
            old.unlink()
        except OSError:
            log.warning("Tidak bisa menghapus cadangan lama: %s", old)