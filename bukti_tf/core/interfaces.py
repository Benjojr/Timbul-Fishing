"""Kontrak (interface) kecil dan spesifik -> ISP.

Lapisan core hanya bergantung pada kontrak ini -> DIP.
"""
from __future__ import annotations

from datetime import date
from typing import Any, List, Optional, Protocol, Sequence, Tuple

from bukti_tf.domain.daily_record import DailyRecord
from bukti_tf.domain.daily_report import DailyReport
from bukti_tf.domain.receipt import TransferReceipt


class ImagePreprocessor(Protocol):
    def prepare(self, image_path: str) -> Any:
        """Baca gambar dari disk dan siapkan agar mudah dibaca OCR."""


class OcrEngine(Protocol):
    def read_text(self, image: Any) -> str:
        """Ubah gambar yang sudah disiapkan menjadi teks mentah."""


class ReceiptParser(Protocol):
    def can_parse(self, text: str) -> bool:
        """True jika teks tampak berasal dari format yang dikenal parser ini."""

    def parse(self, text: str) -> TransferReceipt:
        """Ambil field penting dari teks mentah."""


class ReceiptExporter(Protocol):
    def export(self, receipt: TransferReceipt, destination: str) -> None:
        """Simpan hasil ke tujuan tertentu (txt, csv, excel, ...)."""


class MonthReportExporter(Protocol):
    def export_month(self, rows: Sequence[Tuple[DailyReport, bool]],
                     path: str, title: str) -> None:
        """Tulis laporan satu bulan; tiap baris = (laporan harian, bukti cocok?)."""


class DailyRecordRepository(Protocol):
    def get(self, tanggal: date) -> Optional[DailyRecord]:
        """Ambil rekap satu tanggal, atau None jika belum pernah disimpan."""

    def save(self, record: DailyRecord) -> None:
        """Simpan rekap; jika tanggalnya sudah ada, ditimpa."""

    def delete(self, tanggal: date) -> None:
        """Hapus rekap satu tanggal (tidak error jika tidak ada)."""

    def list_month(self, year: int, month: int) -> List[DailyRecord]:
        """Semua rekap pada bulan tersebut, urut tanggal naik."""

    def list_unsettled(self, since: Optional[date] = None,
                       until: Optional[date] = None) -> List[DailyRecord]:
        """Hari tersimpan yang belum terhubung ke bukti transfer mana pun."""

    def days_for_receipt(self, receipt: TransferReceipt) -> Tuple[date, ...]:
        """Hari-hari yang sudah memakai bukti ini; kosong jika belum pernah dipakai."""

    def link_receipt(self, receipt: TransferReceipt, days: Sequence[date],
                     replace: bool = False) -> None:
        """Hubungkan satu bukti ke satu/beberapa hari tersimpan.
        Raise ReceiptConflictError jika bukti sudah dipakai di hari lain."""

    def unlink_receipt(self, tanggal: date) -> None:
        """Lepas bukti dari satu hari."""
