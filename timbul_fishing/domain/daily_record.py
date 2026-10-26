"""Domain: satu hari yang disimpan = isian harian + (opsional) bukti transfer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

from timbul_fishing.domain.daily_report import DailyInput
from timbul_fishing.domain.receipt import TransferReceipt


@dataclass(frozen=True)
class DailyRecord:
    data: DailyInput
    receipt: Optional[TransferReceipt] = None
    # Semua tanggal yang dibayar oleh bukti yang sama (termasuk hari ini), urut naik.
    # Kosong jika belum ada bukti; berisi 1 tanggal untuk transfer harian biasa.
    cover: Tuple[date, ...] = ()
