from __future__ import annotations

from bukti_tf.core.formatting import format_receipt
from bukti_tf.domain.receipt import TransferReceipt


class TxtExporter:
    def export(self, receipt: TransferReceipt, destination: str) -> None:
        with open(destination, "w", encoding="utf-8") as f:
            f.write(format_receipt(receipt) + "\n")
