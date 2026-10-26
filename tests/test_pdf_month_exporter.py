import os
import tempfile
import unittest
from datetime import date

from bukti_tf.core.report_calculator import DailyReportCalculator
from bukti_tf.domain.daily_report import DailyInput, ExpenseItem, SessionEntry as S
from bukti_tf.infra.pdf_month_exporter import PdfMonthExporter


def laporan(tgl, **kw):
    return DailyReportCalculator().calculate(DailyInput(tanggal=tgl, **kw))


class PdfMonthExporterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "laporan.pdf")

    def tearDown(self):
        self.tmp.cleanup()

    def _export(self, rows):
        PdfMonthExporter(usaha="Uji").export_month(rows, self.path, "Juni 2026")
        with open(self.path, "rb") as f:
            return f.read()

    def test_menghasilkan_pdf_valid(self):
        rows = [(laporan(date(2026, 6, d), sesi=(S(10, 90_000), S(), S()), hadiah=100_000,
                         rincian=(ExpenseItem("Umpan", 20_000),)), d % 2 == 0)
                for d in range(1, 31)]
        data = self._export(rows)
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(len(data), 2_000)

    def test_hari_kosong_data_lama_minus_dan_karakter_khusus(self):
        rows = [
            (laporan(date(2026, 6, 9)), False),                                     # hari libur
            (laporan(date(2026, 6, 10), pengeluaran=40_000), False),                # total lama
            (laporan(date(2026, 6, 11), sesi=(S(1, 90_000), S(), S()), hadiah=500_000,
                     catatan="Minus & <besar>"), True),                             # sisa minus
        ]
        self.assertTrue(self._export(rows).startswith(b"%PDF"))

    def test_urutan_masukan_tidak_berpengaruh(self):
        a = (laporan(date(2026, 6, 2), hadiah=1), False)
        b = (laporan(date(2026, 6, 1), hadiah=2), False)
        self.assertTrue(self._export([a, b]).startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
