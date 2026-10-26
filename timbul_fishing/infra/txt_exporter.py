from __future__ import annotations

from timbul_fishing.core.formatting import format_receipt
from timbul_fishing.domain.receipt import TransferReceipt


class TxtExporter:
    def export(self, receipt: TransferReceipt, destination: str) -> None:
        with open(destination, "w", encoding="utf-8") as f:
            f.write(format_receipt(receipt) + "\n")
