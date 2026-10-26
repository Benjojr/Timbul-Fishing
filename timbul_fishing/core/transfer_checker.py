"""Mencocokkan sisa hasil hitungan dengan nominal pada bukti transfer."""
from __future__ import annotations

from datetime import date
from typing import Optional, Sequence, Tuple

from timbul_fishing.domain import check_result as cr
from timbul_fishing.domain.check_result import CheckResult
from timbul_fishing.domain.daily_report import DailyReport
from timbul_fishing.domain.receipt import TransferReceipt

# Tanggal transfer tidak menentu (bisa 2-3 hari setelahnya), jadi hanya diberi peringatan
# lunak, tidak pernah menggagalkan pencocokan.
LATE_WARNING_DAYS = 14


class TransferChecker:
    """Aturan: transfer = sisa (satu hari, atau jumlah sisa beberapa hari yang digabung)."""

    def check(self, report: DailyReport, receipt: Optional[TransferReceipt]) -> CheckResult:
        return self.check_total(report.sisa, receipt, (report.tanggal,))

    def check_total(
        self,
        sisa: int,
        receipt: Optional[TransferReceipt],
        days: Sequence[date] = (),
    ) -> CheckResult:
        days_t: Tuple[date, ...] = tuple(days)

        if receipt is None:
            status = cr.TIDAK_PERLU if sisa <= 0 else cr.BELUM_ADA
            return CheckResult(status=status, sisa=sisa, days=days_t)

        if receipt.status == "gagal":
            return CheckResult(status=cr.GAGAL, sisa=sisa, nominal=receipt.nominal, days=days_t)

        if receipt.nominal is None:
            return CheckResult(status=cr.TIDAK_TERBACA, sisa=sisa, days=days_t)

        catatan = self._date_note(receipt, days_t)
        selisih = receipt.nominal - sisa
        if selisih != 0:
            return CheckResult(status=cr.SELISIH, sisa=sisa, nominal=receipt.nominal,
                               selisih=selisih, days=days_t, catatan=catatan)

        # nominal sama; pastikan status transfer memang terbaca BERHASIL
        status = cr.CHECKED if receipt.status == "berhasil" else cr.PERLU_CEK
        return CheckResult(status=status, sisa=sisa, nominal=receipt.nominal,
                           selisih=0, days=days_t, catatan=catatan)

    @staticmethod
    def _date_note(receipt: TransferReceipt, days: Tuple[date, ...]) -> Optional[str]:
        paid = receipt.tanggal
        if paid is None or not days:
            return None
        last = max(days)
        if paid < last:
            return "Tanggal transfer lebih awal dari tanggal rekap. Pastikan bukti ini benar."
        late = (paid - last).days
        if late > LATE_WARNING_DAYS:
            return f"Transfer {late} hari setelah tanggal rekap terakhir."
        return None
