from __future__ import annotations

from datetime import date
from typing import List, Optional, Union

from timbul_fishing.domain.daily_report import DailyReport
from timbul_fishing.domain.receipt import TransferReceipt


def format_receipt(receipt: TransferReceipt) -> str:
    nominal = "-" if receipt.nominal is None else str(receipt.nominal)
    return "\n".join(
        [
            f"Status: {receipt.status}",
            f"Waktu: {receipt.waktu}",
            f"Ke: {receipt.ke}",
            f"Nama: {receipt.nama}",
            f"Nominal: {nominal}",
        ]
    )


# Singkatan hari seperti di laporan Excel (Mon, Tue, ...)
HARI_EXCEL = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

Cell = Optional[Union[int, str, date]]


def keterangan(report: DailyReport, checked: bool = False) -> str:
    """'Checked' (jika bukti cocok) lalu catatan harian, dipisah ' · '."""
    parts = ["Checked" if checked else "", report.catatan.strip()]
    return " · ".join(p for p in parts if p)


def excel_values(report: DailyReport, checked: bool = False) -> List[Cell]:
    """
    14 kolom laporan: Tanggal, Hari, Sesi 1-3, Ticket 1-3, Total Pemasukan, Hadiah,
    Pengeluaran, Total Pengeluaran, Sisa, Keterangan. None = sel kosong.
    Pengeluaran sudah mencakup lapak gratis, jackpot, hadiah point, dan lelang.
    """

    def blank0(n: int) -> Optional[int]:
        return None if n == 0 else n

    return [
        report.tanggal,
        HARI_EXCEL[report.tanggal.weekday()],
        *[blank0(s.peserta) for s in report.sesi],
        *[blank0(s.harga) if s.peserta else None for s in report.sesi],
        report.total_pemasukan,
        blank0(report.hadiah),
        blank0(report.pengeluaran),
        report.total_pengeluaran,
        report.sisa,
        keterangan(report, checked) or None,
    ]


def _as_text(v: Cell) -> str:
    if v is None:
        return ""
    return v.isoformat() if isinstance(v, date) else str(v)


def format_excel_row(report: DailyReport, checked: bool = False) -> str:
    """Satu baris TSV untuk ditempel ke Excel; tanggal ISO, angka polos."""
    return "\t".join(_as_text(v) for v in excel_values(report, checked))
