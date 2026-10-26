from __future__ import annotations

import re
from typing import Optional

from bukti_tf.domain.receipt import TransferReceipt


class BcaParser:
    """Parser untuk bukti transfer m-BCA."""

    _STATUS = re.compile(r"m-Transfer:\s*(BERHASIL|GAGAL)", re.IGNORECASE)
    _WAKTU = re.compile(r"(\d{2}/\d{2}/\d{4}\s\d{2}:\d{2}:\d{2})")
    _KE = re.compile(r"Ke\s*(\d{10})")
    _NAMA = re.compile(r"Ke\s*\d{10}\s+([A-Z ]{3,})")
    # Hanya spasi/tab (bukan newline) agar angka di baris berikutnya tidak ikut terbaca.
    _NOMINAL = re.compile(r"Rp\.?[ \t]*([0-9][0-9.,]*)", re.IGNORECASE)
    _PENANDA = re.compile(r"m-Transfer|Ke\s*\d{10}", re.IGNORECASE)

    def can_parse(self, text: str) -> bool:
        return bool(self._PENANDA.search(text))

    def parse(self, text: str) -> TransferReceipt:
        status = self._first(self._STATUS, text)
        return TransferReceipt(
            status=status.lower() if status else "-",
            waktu=self._first(self._WAKTU, text) or "-",
            ke=self._first(self._KE, text) or "-",
            nama=(self._first(self._NAMA, text) or "-").strip(),
            nominal=self.parse_nominal(text),
        )

    @staticmethod
    def _first(pattern: re.Pattern, text: str) -> Optional[str]:
        m = pattern.search(text)
        return m.group(1) if m else None

    @classmethod
    def parse_nominal(cls, text: str) -> Optional[int]:
        """
        Baca nominal rupiah. Mengambil kandidat 'Rp ...' terbesar yang valid,
        karena bukti bisa memuat beberapa angka Rp (mis. biaya admin Rp 0,00).

        Sen (",00") hanya dibuang jika memang ada: koma/titik diikuti tepat 2 digit
        di akhir. 'Rp 150.000' tanpa sen tetap 150000 (bukan 1500).
        """
        values = [v for v in (cls._to_int(raw) for raw in cls._NOMINAL.findall(text))
                  if v is not None]
        return max(values) if values else None

    @staticmethod
    def _to_int(raw: str) -> Optional[int]:
        raw = raw.rstrip(".,")
        m = re.fullmatch(r"(.*?)[.,](\d{2})", raw)
        # Pemisah sen: bagian depan harus sudah berisi pemisah ribuan atau cukup panjang;
        # "1.50" ambigu, tetapi di bukti m-BCA sen selalu ditulis ",00".
        if m and (m.group(2) == "00" or "," in raw[-3:]):
            raw = m.group(1)
        digits = re.sub(r"\D", "", raw)
        return int(digits) if digits else None
