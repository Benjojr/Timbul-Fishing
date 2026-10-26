import unittest
from datetime import date

from bukti_tf.core.formatting import format_excel_row
from bukti_tf.core.report_calculator import DailyReportCalculator
from bukti_tf.domain.daily_report import DailyInput, SessionEntry as S


def hitung(tgl, sesi=(S(), S(), S()), hadiah=0, pengeluaran=0, catatan=""):
    return DailyReportCalculator().calculate(
        DailyInput(tanggal=tgl, sesi=sesi, hadiah=hadiah, pengeluaran=pengeluaran,
                   catatan=catatan))


class ExcelRowTest(unittest.TestCase):
    def test_6_juli_lengkap(self):
        r = hitung(date(2026, 7, 6), (S(12, 90_000), S(40, 90_000), S(10, 75_000)),
                   hadiah=4_075_000, pengeluaran=175_000)
        cells = format_excel_row(r, checked=True).split("\t")
        self.assertEqual(len(cells), 14)  # sama dengan jumlah kolom laporan
        self.assertEqual(cells, [
            "2026-07-06", "Mon", "12", "40", "10", "90000", "90000", "75000",
            "5430000", "4075000", "175000", "4250000", "1180000", "Checked",
        ])

    def test_sesi_kosong_dan_tanpa_pengeluaran(self):
        # 30 Juli: hanya sesi 1; ticket sesi lain tidak dicetak walau harga diisi
        r = hitung(date(2026, 7, 30), (S(7, 100_000), S(0, 90_000), S()), hadiah=525_000)
        cells = format_excel_row(r).split("\t")
        self.assertEqual(cells[2:5], ["7", "", ""])
        self.assertEqual(cells[5:8], ["100000", "", ""])
        self.assertEqual(cells[10], "")       # pengeluaran kosong
        self.assertEqual(cells[11:], ["525000", "175000", ""])  # tanpa Checked

    def test_hari_libur(self):
        cells = format_excel_row(hitung(date(2026, 7, 9))).split("\t")
        self.assertEqual(cells[:2], ["2026-07-09", "Thu"])
        self.assertEqual(cells[8], "0")
        self.assertEqual(cells[11:13], ["0", "0"])

    def test_keterangan_gabung_checked_dan_catatan(self):
        r = hitung(date(2026, 6, 9), (S(8, 90_000), S(), S()), catatan="Minus 5.000")
        self.assertEqual(format_excel_row(r, checked=True).split("\t")[-1],
                         "Checked · Minus 5.000")
        self.assertEqual(format_excel_row(r).split("\t")[-1], "Minus 5.000")


if __name__ == "__main__":
    unittest.main()
