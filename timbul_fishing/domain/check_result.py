"""Domain: hasil pencocokan antara sisa hitungan dan bukti transfer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

# Nilai status pencocokan
BELUM_ADA = "belum_ada"          # sisa > 0 tetapi bukti transfer belum dipilih
TIDAK_PERLU = "tidak_perlu"      # sisa <= 0 dan tidak ada bukti: memang tidak ada transfer
CHECKED = "checked"              # transfer berhasil dan nominal == sisa (satu hari atau gabungan)
SELISIH = "selisih"              # nominal != sisa
GAGAL = "gagal"                  # bukti menyatakan transfer gagal
TIDAK_TERBACA = "tidak_terbaca"  # nominal pada bukti tidak terbaca
PERLU_CEK = "perlu_cek"          # nominal == sisa, tetapi status transfer tidak terbaca
GABUNGAN = "gabungan"            # nominal tidak cocok satu hari, tetapi cocok gabungan beberapa hari
SUDAH_DIPAKAI = "sudah_dipakai"  # bukti yang sama sudah tercatat untuk hari lain


@dataclass(frozen=True)
class CheckResult:
    status: str
    sisa: int                      # sisa satu hari, atau total sisa semua hari dalam gabungan
    nominal: Optional[int] = None
    selisih: Optional[int] = None  # nominal - sisa (positif = transfer kelebihan)
    days: Tuple[date, ...] = ()    # hari yang tercakup bukti ini
    catatan: Optional[str] = None  # peringatan lunak (mis. tanggal transfer janggal)
