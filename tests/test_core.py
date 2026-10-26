import unittest

from bukti_tf.core.errors import UnsupportedReceiptError
from bukti_tf.core.extractor import ReceiptExtractor
from bukti_tf.infra.bca_parser import BcaParser

SAMPLE = """m-BCA
m-Transfer: BERHASIL
06/10/2026 10:15:30
Ke 1234567890 BUDI SANTOSO
Rp 150.000,00
"""


class FakePreprocessor:
    def prepare(self, image_path):
        return image_path


class FakeOcr:
    def __init__(self, text):
        self._text = text

    def read_text(self, image):
        return self._text


class BcaParserTest(unittest.TestCase):
    def test_parse_semua_field(self):
        r = BcaParser().parse(SAMPLE)
        self.assertEqual(r.status, "berhasil")
        self.assertEqual(r.waktu, "06/10/2026 10:15:30")
        self.assertEqual(r.ke, "1234567890")
        self.assertEqual(r.nama, "BUDI SANTOSO")
        self.assertEqual(r.nominal, 150000)

    def test_field_hilang_jadi_default(self):
        r = BcaParser().parse("m-Transfer: GAGAL")
        self.assertEqual(r.status, "gagal")
        self.assertEqual(r.ke, "-")
        self.assertIsNone(r.nominal)


class ExtractorTest(unittest.TestCase):
    def test_alur_lengkap_dengan_fake(self):
        ex = ReceiptExtractor(FakePreprocessor(), FakeOcr(SAMPLE), [BcaParser()])
        self.assertEqual(ex.extract("x.png").nominal, 150000)

    def test_format_tidak_dikenal(self):
        ex = ReceiptExtractor(FakePreprocessor(), FakeOcr("halo dunia"), [BcaParser()])
        with self.assertRaises(UnsupportedReceiptError):
            ex.extract("x.png")


if __name__ == "__main__":
    unittest.main()
