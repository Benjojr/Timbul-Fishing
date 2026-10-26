"""Domain: usulan pencocokan satu bukti transfer dengan satu atau beberapa hari."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Tuple


@dataclass(frozen=True)
class Candidate:
    days: Tuple[date, ...]
    total: int
    contiguous: bool = True        # hari-hari berurutan di antara hari yang belum dibayar
    after_transfer: bool = False   # ada hari yang tanggalnya setelah tanggal transfer (janggal)


@dataclass(frozen=True)
class Suggestion:
    candidates: List[Candidate] = field(default_factory=list)
    duplicate_days: Tuple[date, ...] = ()  # bukti ini sudah tercatat untuk hari-hari tersebut
