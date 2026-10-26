"""Tes unit: tanpa Tesseract dan tanpa jendela."""
import unittest
from datetime import date

from timbul_fishing.core.errors import InvalidReportInputError
from timbul_fishing.core.report_calculator import DailyReportCalculator
from timbul_fishing.domain.daily_report import DailyInput, ExpenseItem, SessionEntry
from timbul_fishing.infra.bca_parser import BcaParser

SAMPLE = """m-Transfer: BERHASIL
25/10/2026 19:04:11
Ke 1234567890 BUDI SANTOSO
Rp 1.250.000,00
Biaya admin Rp 0,00
"""


class BcaParserTest(unittest.TestCase):
    def test_parse_lengkap(self):
        r = BcaParser().parse(SAMPLE)
        self.assertEqual(r.status, "berhasil")
        self.assertEqual(r.waktu, "25/10/2026 19:04:11")
        self.assertEqual(r.ke, "1234567890")
        self.assertEqual(r.nama, "BUDI SANTOSO")
        self.assertEqual(r.nominal, 1_250_000)

    def test_nominal_tanpa_sen(self):
        self.assertEqual(BcaParser.parse_nominal("Rp 150.000"), 150_000)

    def test_can_parse(self):
        self.assertTrue(BcaParser().can_parse(SAMPLE))
        self.assertFalse(BcaParser().can_parse("struk belanja"))


class CalculatorTest(unittest.TestCase):
    def _input(self, **kw):
        sesi = (SessionEntry(10, 50_000), SessionEntry(8, 50_000), SessionEntry(5, 60_000))
        return DailyInput(tanggal=date(2026, 10, 25), sesi=sesi, **kw)

    def test_sisa(self):
        r = DailyReportCalculator().calculate(
            self._input(hadiah=300_000, rincian=(ExpenseItem("umpan", 100_000),)))
        self.assertEqual(r.total_pemasukan, 1_200_000)
        self.assertEqual(r.total_pengeluaran, 400_000)
        self.assertEqual(r.sisa, 800_000)

    def test_negatif_ditolak(self):
        with self.assertRaises(InvalidReportInputError):
            DailyReportCalculator().calculate(self._input(hadiah=-1))


if __name__ == "__main__":
    unittest.main()
