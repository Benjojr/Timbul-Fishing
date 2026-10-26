from __future__ import annotations

from PIL import Image, ImageOps

from bukti_tf.core.errors import ImageReadError

_MIN_WIDTH = 1400  # OCR jauh lebih akurat pada teks yang cukup besar


class PillowThresholdPreprocessor:
    """
    Grayscale -> perbesar jika kecil -> balik warna jika gambar gelap (dark mode)
    -> autocontrast -> threshold Otsu (otomatis, tidak tergantung kecerahan foto).
    Parameter `threshold` dipertahankan agar kompatibel: jika diisi, dipakai threshold tetap.
    """

    def __init__(self, threshold: int | None = None) -> None:
        self._fixed = threshold

    def prepare(self, image_path: str) -> Image.Image:
        try:
            with Image.open(image_path) as img:
                img = ImageOps.exif_transpose(img)
                gray = img.convert("L")
        except Exception as exc:  # file rusak / bukan gambar
            raise ImageReadError("Gambar tidak dapat dibaca.") from exc

        if gray.width < _MIN_WIDTH:
            scale = _MIN_WIDTH / gray.width
            gray = gray.resize((_MIN_WIDTH, round(gray.height * scale)), Image.LANCZOS)

        hist = gray.histogram()
        total = sum(hist)
        mean = sum(i * c for i, c in enumerate(hist)) / total
        if mean < 110:  # latar gelap, teks terang -> balik agar teks hitam di latar putih
            gray = ImageOps.invert(gray)

        gray = ImageOps.autocontrast(gray, cutoff=1)
        limit = self._fixed if self._fixed is not None else self._otsu(gray.histogram())
        return gray.point(lambda p: 255 if p > limit else 0)

    @staticmethod
    def _otsu(hist) -> int:
        total = sum(hist)
        sum_all = sum(i * c for i, c in enumerate(hist))
        sum_b = w_b = 0
        best, best_var = 128, -1.0
        for t in range(256):
            w_b += hist[t]
            if w_b == 0:
                continue
            w_f = total - w_b
            if w_f == 0:
                break
            sum_b += t * hist[t]
            m_b, m_f = sum_b / w_b, (sum_all - sum_b) / w_f
            var = w_b * w_f * (m_b - m_f) ** 2
            if var > best_var:
                best, best_var = t, var
        return best
