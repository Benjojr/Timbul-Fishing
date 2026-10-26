"""Orkestrasi alur: gambar -> teks -> data terstruktur.

Kelas ini tidak tahu Pillow, Tesseract, ataupun bank tertentu (SRP + DIP).
Menambah bank baru = menambah parser ke daftar (OCP).
"""
from __future__ import annotations

from typing import Sequence

from bukti_tf.core.errors import UnsupportedReceiptError
from bukti_tf.core.interfaces import ImagePreprocessor, OcrEngine, ReceiptParser
from bukti_tf.domain.receipt import TransferReceipt


class ReceiptExtractor:
    def __init__(
        self,
        preprocessor: ImagePreprocessor,
        ocr: OcrEngine,
        parsers: Sequence[ReceiptParser],
    ) -> None:
        self._preprocessor = preprocessor
        self._ocr = ocr
        self._parsers = list(parsers)

    def extract(self, image_path: str) -> TransferReceipt:
        image = self._preprocessor.prepare(image_path)
        text = self._ocr.read_text(image)
        for parser in self._parsers:
            if parser.can_parse(text):
                return parser.parse(text)
        raise UnsupportedReceiptError("Format bukti transfer tidak dikenali.")
