"""Domain: data murni, tidak tahu soal OCR, GUI, atau file."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class TransferReceipt:
    status: str = "-"
    waktu: str = "-"
    ke: str = "-"
    nama: str = "-"
    nominal: Optional[int] = None

    @property
    def tanggal(self) -> Optional[date]:
        """Tanggal transfer dari `waktu` (dd/mm/yyyy hh:mm:ss); None jika tidak terbaca."""
        try:
            return datetime.strptime(self.waktu, "%d/%m/%Y %H:%M:%S").date()
        except ValueError:
            return None

    @property
    def fingerprint(self) -> Optional[str]:
        """
        Pengenal unik bukti (waktu + rekening + nominal) untuk mendeteksi bukti yang sama
        dipakai dua kali. None jika waktu/nominal tidak terbaca (tidak bisa dibandingkan).
        """
        if self.tanggal is None or self.nominal is None:
            return None
        return f"{self.waktu}|{self.ke}|{self.nominal}"
