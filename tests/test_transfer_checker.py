import unittest
from datetime import date

from bukti_tf.core.report_calculator import DailyReportCalculator
from bukti_tf.core.transfer_checker import TransferChecker
from bukti_tf.domain import check_result as cr
from bukti_tf.domain.daily_report import DailyInput, SessionEntry as S
from bukti_tf.domain.receipt import TransferReceipt


def laporan_6_juli():
    # sisa = 1.180.000 (sesuai Excel)
    return DailyReportCalculator().calculate(DailyInput(
        tanggal=date(2026, 7, 6),
        sesi=(S(12, 90_000), S(40, 90_000), S(10, 75_000)),
        hadiah=4_075_000, pengeluaran=175_000,
    ))


def struk(nominal, status="berhasil"):
    return TransferReceipt(status=status, nominal=nominal)


class TransferCheckerTest(unittest.TestCase):
    def setUp(self):
        self.checker = TransferChecker()
        self.report = laporan_6_juli()

    def test_checked_jika_sama(self):
        r = self.checker.check(self.report, struk(1_180_000))
        self.assertEqual(r.status, cr.CHECKED)
        self.assertEqual(r.selisih, 0)

    def test_selisih_kurang(self):
        r = self.checker.check(self.report, struk(1_100_000))
        self.assertEqual(r.status, cr.SELISIH)
        self.assertEqual(r.selisih, -80_000)

    def test_selisih_lebih(self):
        r = self.checker.check(self.report, struk(1_250_000))
        self.assertEqual((r.status, r.selisih), (cr.SELISIH, 70_000))

    def test_transfer_gagal_tidak_pernah_checked(self):
        r = self.checker.check(self.report, struk(1_180_000, status="gagal"))
        self.assertEqual(r.status, cr.GAGAL)

    def test_nominal_tidak_terbaca(self):
        r = self.checker.check(self.report, struk(None))
        self.assertEqual(r.status, cr.TIDAK_TERBACA)

    def test_status_tidak_terbaca_tapi_nominal_sama_perlu_cek(self):
        r = self.checker.check(self.report, struk(1_180_000, status="-"))
        self.assertEqual(r.status, cr.PERLU_CEK)

    def test_belum_ada_bukti(self):
        self.assertEqual(self.checker.check(self.report, None).status, cr.BELUM_ADA)

    def test_hari_libur_tanpa_transfer(self):
        libur = DailyReportCalculator().calculate(DailyInput(tanggal=date(2026, 7, 9)))
        self.assertEqual(self.checker.check(libur, None).status, cr.TIDAK_PERLU)


if __name__ == "__main__":
    unittest.main()
