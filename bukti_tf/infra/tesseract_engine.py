from __future__ import annotations

import os
from typing import Any, Optional

import pytesseract

from bukti_tf.core.errors import OcrError


class TesseractOcrEngine:
    def __init__(
        self,
        tesseract_cmd: str,
        tessdata_dir: Optional[str] = None,
        lang: str = "eng",
    ) -> None:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        if tessdata_dir:
            # Lewat environment variable, bukan argumen --tessdata-dir:
            # pytesseract di Windows tidak membuang tanda kutip, dan path
            # yang mengandung spasi (mis. "Project Bukti TF") ikut rusak.
            os.environ["TESSDATA_PREFIX"] = tessdata_dir
        self._lang = lang

    def read_text(self, image: Any) -> str:
        try:
            return pytesseract.image_to_string(image, lang=self._lang)
        except pytesseract.TesseractNotFoundError as exc:
            raise OcrError(
                "Tesseract tidak ditemukan. Pastikan folder 'tesseract' ada di samping aplikasi."
            ) from exc
        except pytesseract.TesseractError as exc:
            raise OcrError(f"OCR gagal: {exc}") from exc
