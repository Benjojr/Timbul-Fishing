"""Domain: data murni untuk rekap harian. Tidak ada logika hitung di sini."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Tuple


@dataclass(frozen=True)
class SessionEntry:
    """Satu sesi memancing: jumlah pemancing dan harga ticket sesi tersebut."""
    peserta: int = 0
    harga: int = 0


@dataclass(frozen=True)
class ExpenseItem:
    """Satu baris pengeluaran: untuk apa dan berapa."""
    keperluan: str = ""
    nominal: int = 0


@dataclass(frozen=True)
class DailyInput:
    """Data yang dimasukkan manual dari buku pengelola."""
    tanggal: date
    sesi: Tuple[SessionEntry, SessionEntry, SessionEntry] = (
        SessionEntry(), SessionEntry(), SessionEntry()
    )
    hadiah: int = 0
    pengeluaran: int = 0                       # total lama (satu angka); diabaikan jika ada rincian
    rincian: Tuple[ExpenseItem, ...] = ()      # pengeluaran per keperluan
    catatan: str = ""                          # keterangan bebas untuk hari ini


@dataclass(frozen=True)
class DailyReport:
    """Hasil perhitungan satu hari."""
    tanggal: date
    sesi: Tuple[SessionEntry, SessionEntry, SessionEntry]
    hadiah: int
    pengeluaran: int
    total_pemasukan: int
    total_pengeluaran: int  # hadiah + pengeluaran
    sisa: int               # total_pemasukan - total_pengeluaran
    rincian: Tuple[ExpenseItem, ...] = ()
    catatan: str = ""
