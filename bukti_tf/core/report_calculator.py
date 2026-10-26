"""Perhitungan rekap harian. Fungsi murni: tanpa GUI, file, atau OCR."""
from __future__ import annotations

from bukti_tf.core.errors import InvalidReportInputError
from bukti_tf.domain.daily_report import DailyInput, DailyReport


class DailyReportCalculator:
    """
    total_pemasukan   = sum(peserta_i * harga_i) untuk sesi 1..3
    pengeluaran       = sum(rincian.nominal) bila ada rincian, jika tidak angka total lama
    total_pengeluaran = hadiah + pengeluaran
    sisa              = total_pemasukan - total_pengeluaran
    """

    def calculate(self, data: DailyInput) -> DailyReport:
        self._validate(data)
        total_pemasukan = sum(s.peserta * s.harga for s in data.sesi)
        pengeluaran = (sum(i.nominal for i in data.rincian)
                       if data.rincian else data.pengeluaran)
        total_pengeluaran = data.hadiah + pengeluaran
        return DailyReport(
            tanggal=data.tanggal,
            sesi=data.sesi,
            hadiah=data.hadiah,
            pengeluaran=pengeluaran,
            total_pemasukan=total_pemasukan,
            total_pengeluaran=total_pengeluaran,
            sisa=total_pemasukan - total_pengeluaran,
            rincian=data.rincian,
            catatan=data.catatan,
        )

    @staticmethod
    def _validate(data: DailyInput) -> None:
        if len(data.sesi) != 3:
            raise InvalidReportInputError("Harus ada tepat 3 sesi.")
        for i, s in enumerate(data.sesi, start=1):
            if s.peserta < 0 or s.harga < 0:
                raise InvalidReportInputError(
                    f"Sesi {i}: jumlah peserta dan harga tidak boleh negatif."
                )
        if data.hadiah < 0 or data.pengeluaran < 0:
            raise InvalidReportInputError("Hadiah dan pengeluaran tidak boleh negatif.")
        for i, item in enumerate(data.rincian, start=1):
            if item.nominal < 0:
                raise InvalidReportInputError(f"Pengeluaran baris {i}: nominal tidak boleh negatif.")
