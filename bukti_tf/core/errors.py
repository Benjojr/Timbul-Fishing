"""Error khusus aplikasi, agar UI bisa menampilkan pesan yang jelas."""


class ReceiptError(Exception):
    """Basis semua error pemrosesan bukti transfer."""


class ImageReadError(ReceiptError):
    """Gambar tidak dapat dibaca."""


class OcrError(ReceiptError):
    """Mesin OCR gagal berjalan."""


class UnsupportedReceiptError(ReceiptError):
    """Format bukti transfer tidak dikenali oleh parser mana pun."""


class InvalidReportInputError(ValueError):
    """Input rekap harian tidak valid (misalnya nilai negatif)."""


class ReceiptConflictError(ReceiptError):
    """Bukti yang sama sudah dipakai untuk hari lain."""

    def __init__(self, message: str, days=()):
        super().__init__(message)
        self.days = tuple(days)
