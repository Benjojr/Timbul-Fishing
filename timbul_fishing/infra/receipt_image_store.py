"""Penyimpanan gambar bukti transfer di disk.

Alur: gambar yang baru dibaca OCR ditaruh di `_sementara/` (stage) dan mendapat token. Saat
rekap disimpan dan bukti berhasil terhubung ke hari, gambar dipindah ke `<YYYY-MM>/` (commit).
Yang tidak jadi dipakai dibersihkan otomatis. Gambar yang tidak dipakai lagi tidak dihapus,
hanya dipindah ke `_dihapus/`.
"""
from __future__ import annotations

import hashlib
import io
import re
import shutil
import time
from datetime import date
from pathlib import Path
from typing import Optional

from PIL import Image

_EXT = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "BMP": ".bmp"}
_TOKEN = re.compile(r"[0-9a-f]{64}")
_STAGING, _TRASH = "_sementara", "_dihapus"
_STAGING_MAX_AGE = 24 * 3600


class ReceiptImageStore:
    def __init__(self, root) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------- sementara
    def stage(self, data: bytes) -> str:
        """Validasi bahwa `data` benar-benar gambar, simpan sementara, kembalikan token."""
        try:
            with Image.open(io.BytesIO(data)) as img:
                img.verify()
                ext = _EXT.get(img.format or "")
        except Exception as exc:
            raise ValueError("Berkas bukan gambar yang dikenali.") from exc
        if ext is None:
            raise ValueError("Format gambar tidak didukung.")
        token = hashlib.sha256(data).hexdigest()
        folder = self._root / _STAGING
        folder.mkdir(exist_ok=True)
        self._purge_staging(folder)
        target = folder / f"{token}{ext}"
        if not target.exists():
            target.write_bytes(data)
        return token

    def discard(self, token: str) -> None:
        found = self._staged(token)
        if found is not None:
            found.unlink(missing_ok=True)

    def _staged(self, token: str) -> Optional[Path]:
        if not _TOKEN.fullmatch(token or ""):
            return None
        return next((self._root / _STAGING).glob(f"{token}.*"), None)

    @staticmethod
    def _purge_staging(folder: Path) -> None:
        limit = time.time() - _STAGING_MAX_AGE
        for f in folder.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < limit:
                    f.unlink()
            except OSError:
                pass

    # ---------------------------------------------------------- tetap
    def commit(self, token: str, tanggal: date) -> str:
        src = self._staged(token)
        if src is None:
            raise FileNotFoundError("Gambar sementara sudah tidak ada. Tempel ulang gambarnya.")
        rel = f"{tanggal:%Y-%m}/{tanggal.isoformat()}_{token[:10]}{src.suffix}"
        dst = self._root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            src.unlink(missing_ok=True)      # gambar yang sama sudah tersimpan
        else:
            shutil.move(str(src), str(dst))
        return rel

    def path_of(self, image: str) -> Optional[Path]:
        if not image:
            return None
        path = (self._root / image).resolve()
        if not path.is_relative_to(self._root.resolve()) or not path.is_file():
            return None
        return path

    def archive(self, image: str) -> None:
        path = self.path_of(image)
        if path is None:
            return
        dst = self._root / _TRASH / Path(image).name
        dst.parent.mkdir(exist_ok=True)
        shutil.move(str(path), str(dst))