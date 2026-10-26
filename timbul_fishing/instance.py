"""Satu instance saja: instance kedua ditolak supaya dua proses tidak menulis ke file data yang sama."""
from __future__ import annotations

import sys
from pathlib import Path


class SingleInstance:
    """Kunci file tingkat-OS. Dilepas otomatis saat proses berakhir, termasuk bila crash."""

    def __init__(self, path) -> None:
        self._path = Path(path)
        self._fh = None

    def acquire(self) -> bool:
        fh = open(self._path, "a+b")
        try:
            if sys.platform == "win32":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh  # simpan referensinya selama aplikasi hidup
        return True