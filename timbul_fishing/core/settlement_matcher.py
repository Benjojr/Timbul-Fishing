"""
Mencari gabungan hari yang jumlah sisanya sama dengan nominal satu bukti transfer.

Pengelola kadang mentransfer sekali untuk beberapa hari, dan tanggal transfer tidak
menentu. Jadi tanggal bukti tidak dipakai sebagai syarat; yang dipakai hanya:
  - nominal harus sama persis dengan jumlah sisa hari-hari yang dipilih,
  - hari yang dipilih belum pernah dibayar (belum terhubung ke bukti lain),
  - hari tidak boleh lebih baru dari tanggal transfer (kecuali tidak ada kecocokan lain).
Fungsi murni: tanpa GUI, file, atau database.
"""
from __future__ import annotations

from datetime import date
from itertools import combinations
from typing import List, Optional, Sequence

from timbul_fishing.domain.daily_report import DailyReport
from timbul_fishing.domain.settlement import Candidate


class SettlementMatcher:
    def __init__(self, lookback_days: int = 45, pool_size: int = 20,
                 max_days: int = 7, max_results: int = 5) -> None:
        self._lookback = lookback_days
        self._pool_size = pool_size
        self._max_days = max_days
        self._max_results = max_results

    def find(
        self,
        nominal: int,
        reports: Sequence[DailyReport],
        receipt_date: Optional[date] = None,
    ) -> List[Candidate]:
        if nominal <= 0:
            return []
        payable = sorted((r for r in reports if r.sisa > 0), key=lambda r: r.tanggal)

        if receipt_date is not None:
            strict = [r for r in payable
                      if r.tanggal <= receipt_date
                      and (receipt_date - r.tanggal).days <= self._lookback]
            found = self._search(nominal, strict, receipt_date)
            if found:
                return found
        # Tanggal transfer tidak terbaca / mungkin salah baca: longgarkan, tapi beri tanda.
        return self._search(nominal, payable, receipt_date)

    # ------------------------------------------------------------------
    def _search(self, nominal: int, pool: List[DailyReport],
                receipt_date: Optional[date]) -> List[Candidate]:
        pool = pool[-self._pool_size:]
        n = len(pool)
        if n == 0:
            return []
        sisa = [r.sisa for r in pool]

        # 1) Irisan berurutan (kasus umum: "kemarin + kemarinnya lagi")
        contiguous: List[Candidate] = []
        for i in range(n):
            total = 0
            for j in range(i, min(n, i + self._max_days)):
                total += sisa[j]
                if total == nominal:
                    contiguous.append(self._make(pool, range(i, j + 1), True, receipt_date))
                elif total > nominal:
                    break
        if contiguous:
            return self._rank(contiguous)

        # 2) Tidak berurutan: hanya jika tidak ada yang berurutan, supaya tidak ada
        #    kecocokan kebetulan yang menenggelamkan kecocokan yang benar.
        scattered: List[Candidate] = []
        for k in range(2, min(self._max_days, n) + 1):
            for idx in combinations(range(n), k):
                if sum(sisa[i] for i in idx) == nominal:
                    scattered.append(self._make(pool, idx, False, receipt_date))
        return self._rank(scattered)

    @staticmethod
    def _make(pool: List[DailyReport], idx, contiguous: bool,
              receipt_date: Optional[date]) -> Candidate:
        days = tuple(pool[i].tanggal for i in idx)
        return Candidate(
            days=days,
            total=sum(pool[i].sisa for i in idx),
            contiguous=contiguous,
            after_transfer=receipt_date is not None and max(days) > receipt_date,
        )

    def _rank(self, items: List[Candidate]) -> List[Candidate]:
        # Tidak janggal dulu, lalu paling sedikit hari, lalu yang tertua (utang terlama dibayar dulu).
        items.sort(key=lambda c: (c.after_transfer, len(c.days), c.days[0]))
        return items[: self._max_results]
