import unittest
from datetime import date

from bukti_tf.core.errors import InvalidReportInputError
from bukti_tf.core.report_calculator import DailyReportCalculator
from bukti_tf.domain.daily_report import DailyInput, SessionEntry

S = SessionEntry


def hitung(tgl, sesi, hadiah, pengeluaran=0):
    return DailyReportCalculator().calculate(
        DailyInput(tanggal=tgl, sesi=sesi, hadiah=hadiah, pengeluaran=pengeluaran)
    )


class DailyReportCalculatorTest(unittest.TestCase):
    """Angka diambil dari laporan Excel asli (Juli 2026)."""

    def test_6_juli(self):
        r = hitung(date(2026, 7, 6),
                   (S(12, 90_000), S(40, 90_000), S(10, 75_000)),
                   hadiah=4_075_000, pengeluaran=175_000)
        self.assertEqual(r.total_pemasukan, 5_430_000)
        self.assertEqual(r.total_pengeluaran, 4_250_000)
        self.assertEqual(r.sisa, 1_180_000)

    def test_7_juli(self):
        r = hitung(date(2026, 7, 7),
                   (S(14, 90_000), S(37, 115_000), S(12, 75_000)),
                   hadiah=4_715_000, pengeluaran=410_000)
        self.assertEqual(r.total_pemasukan, 6_415_000)
        self.assertEqual(r.total_pengeluaran, 5_125_000)
        self.assertEqual(r.sisa, 1_290_000)

    def test_sesi_kosong_dan_tanpa_pengeluaran(self):
        # 30 Juli: hanya sesi 1, pengeluaran kosong
        r = hitung(date(2026, 7, 30),
                   (S(7, 100_000), S(), S()), hadiah=525_000)
        self.assertEqual(r.total_pemasukan, 700_000)
        self.assertEqual(r.total_pengeluaran, 525_000)
        self.assertEqual(r.sisa, 175_000)

    def test_hari_libur_semua_nol(self):
        r = hitung(date(2026, 7, 9), (S(), S(), S()), hadiah=0)
        self.assertEqual((r.total_pemasukan, r.total_pengeluaran, r.sisa), (0, 0, 0))

    def test_sisa_bisa_negatif(self):
        r = hitung(date(2026, 7, 1), (S(1, 50_000), S(), S()), hadiah=80_000)
        self.assertEqual(r.sisa, -30_000)

    def test_nilai_negatif_ditolak(self):
        with self.assertRaises(InvalidReportInputError):
            hitung(date(2026, 7, 1), (S(-1, 50_000), S(), S()), hadiah=0)
        with self.assertRaises(InvalidReportInputError):
            hitung(date(2026, 7, 1), (S(), S(), S()), hadiah=-1)


if __name__ == "__main__":
    unittest.main()
