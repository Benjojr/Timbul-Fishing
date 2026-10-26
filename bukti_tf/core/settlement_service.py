"""Alur pencocokan bukti transfer dengan hari-hari yang belum dibayar.

Menggabungkan repository + kalkulator + checker + matcher; tidak tahu GUI/OCR.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from bukti_tf.core.interfaces import DailyRecordRepository
from bukti_tf.core.report_calculator import DailyReportCalculator
from bukti_tf.core.settlement_matcher import SettlementMatcher
from bukti_tf.core.transfer_checker import TransferChecker
from bukti_tf.domain.check_result import CheckResult
from bukti_tf.domain.daily_record import DailyRecord
from bukti_tf.domain.daily_report import DailyReport
from bukti_tf.domain.receipt import TransferReceipt
from bukti_tf.domain.settlement import Suggestion

_LOOKBACK_DAYS = 45


class SettlementService:
    def __init__(
        self,
        repository: DailyRecordRepository,
        calculator: DailyReportCalculator,
        checker: TransferChecker,
        matcher: Optional[SettlementMatcher] = None,
    ) -> None:
        self._repo = repository
        self._calc = calculator
        self._checker = checker
        self._matcher = matcher or SettlementMatcher()

    # ---------- usulan untuk bukti baru ----------
    def suggest(self, receipt: TransferReceipt,
                current: Optional[DailyReport] = None) -> Suggestion:
        """
        Cari hari mana saja yang dibayar bukti ini. `current` = hasil hitung form yang sedang
        terbuka (boleh belum tersimpan); dipakai menggantikan versi tersimpan di tanggal sama.
        """
        if receipt.status == "gagal" or receipt.nominal is None:
            return Suggestion()
        used = self._repo.days_for_receipt(receipt)
        if used:
            return Suggestion(duplicate_days=used)

        paid = receipt.tanggal
        since = (paid or date.today()) - timedelta(days=_LOOKBACK_DAYS)
        reports: Dict[date, DailyReport] = {}
        for rec in self._repo.list_unsettled(since=since):
            try:
                reports[rec.data.tanggal] = self._calc.calculate(rec.data)
            except ValueError:
                continue
        if current is not None:
            existing = self._repo.get(current.tanggal)
            if existing is None or not existing.cover:
                reports[current.tanggal] = current
        return Suggestion(candidates=self._matcher.find(receipt.nominal, list(reports.values()), paid))

    # ---------- menerapkan ----------
    def apply(self, receipt: TransferReceipt, days: Sequence[date], replace: bool = False) -> None:
        self._repo.link_receipt(receipt, days, replace=replace)

    # ---------- evaluasi hari tersimpan ----------
    def evaluate(self, rec: DailyRecord) -> Tuple[DailyReport, CheckResult]:
        """Laporan + hasil cek untuk hari tersimpan; bukti gabungan dihitung atas seluruh hari."""
        report = self._calc.calculate(rec.data)  # ValueError jika isian tidak valid
        return report, self.check_live(report, rec.receipt, rec.cover)

    def check_live(self, report: DailyReport, receipt: Optional[TransferReceipt],
                   cover: Sequence[date] = ()) -> CheckResult:
        """Cek untuk form yang sedang terbuka. `cover` = hari yang berbagi bukti yang sama."""
        if receipt is None or len(cover) <= 1:
            return self._checker.check(report, receipt)
        total = report.sisa if report.tanggal in cover else 0
        for d in cover:
            if d == report.tanggal:
                continue
            other = self._repo.get(d)
            if other is None:
                continue
            try:
                total += self._calc.calculate(other.data).sisa
            except ValueError:
                continue
        return self._checker.check_total(total, receipt, cover)
