import os
import tempfile
import unittest
from datetime import date

from bukti_tf.domain.daily_record import DailyRecord
from bukti_tf.domain.daily_report import DailyInput, SessionEntry as S
from bukti_tf.domain.receipt import TransferReceipt
from bukti_tf.infra.sqlite_repository import SqliteDailyRecordRepository


def rec(tgl, hadiah=1000, receipt=None):
    return DailyRecord(
        DailyInput(tanggal=tgl, sesi=(S(12, 90_000), S(), S(10, 75_000)),
                   hadiah=hadiah, pengeluaran=175_000),
        receipt,
    )


class SqliteRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = SqliteDailyRecordRepository(os.path.join(self.tmp.name, "sub", "rekap.db"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_kosong(self):
        self.assertIsNone(self.repo.get(date(2026, 7, 6)))

    def test_simpan_dan_baca_tanpa_bukti(self):
        r = rec(date(2026, 7, 6))
        self.repo.save(r)
        self.assertEqual(self.repo.get(date(2026, 7, 6)), r)

    def test_simpan_dan_baca_dengan_bukti(self):
        bukti = TransferReceipt(status="berhasil", waktu="06/07/2026 10:00:00",
                                ke="1234567890", nama="BUDI", nominal=1_180_000)
        hari = date(2026, 7, 6)
        r = rec(hari)
        self.repo.save(r)
        self.repo.link_receipt(bukti, [hari])  # bukti disimpan terpisah dari data harian
        got = self.repo.get(hari)
        self.assertEqual(got.data, r.data)
        self.assertEqual(got.receipt, bukti)
        self.assertEqual(got.cover, (hari,))

    def test_tanggal_sama_ditimpa(self):
        self.repo.save(rec(date(2026, 7, 6), hadiah=1))
        self.repo.save(rec(date(2026, 7, 6), hadiah=2))
        self.assertEqual(self.repo.get(date(2026, 7, 6)).data.hadiah, 2)
        self.assertEqual(len(self.repo.list_month(2026, 7)), 1)

    def test_list_month_terurut_dan_terfilter(self):
        for d in (date(2026, 7, 20), date(2026, 7, 6), date(2026, 8, 1), date(2026, 6, 30)):
            self.repo.save(rec(d))
        hasil = [r.data.tanggal for r in self.repo.list_month(2026, 7)]
        self.assertEqual(hasil, [date(2026, 7, 6), date(2026, 7, 20)])

    def test_hapus(self):
        self.repo.save(rec(date(2026, 7, 6)))
        self.repo.delete(date(2026, 7, 6))
        self.repo.delete(date(2026, 7, 6))  # tidak error walau sudah tidak ada
        self.assertIsNone(self.repo.get(date(2026, 7, 6)))

    def test_catatan_tersimpan_dan_dipangkas(self):
        d = DailyInput(tanggal=date(2026, 6, 9), pengeluaran=1000, catatan="  Minus 5.000 ")
        self.repo.save(DailyRecord(d))
        self.assertEqual(self.repo.get(date(2026, 6, 9)).data.catatan, "Minus 5.000")

    def test_migrasi_database_lama_tanpa_kolom_catatan(self):
        import sqlite3
        path = os.path.join(self.tmp.name, "lama.db")
        con = sqlite3.connect(path)
        con.executescript("""
            CREATE TABLE daily_record (
                tanggal TEXT PRIMARY KEY,
                peserta1 INTEGER NOT NULL, harga1 INTEGER NOT NULL,
                peserta2 INTEGER NOT NULL, harga2 INTEGER NOT NULL,
                peserta3 INTEGER NOT NULL, harga3 INTEGER NOT NULL,
                hadiah INTEGER NOT NULL, pengeluaran INTEGER NOT NULL,
                has_receipt INTEGER NOT NULL DEFAULT 0,
                r_status TEXT, r_waktu TEXT, r_ke TEXT, r_nama TEXT, r_nominal INTEGER);
            INSERT INTO daily_record (tanggal, peserta1, harga1, peserta2, harga2,
                peserta3, harga3, hadiah, pengeluaran)
            VALUES ('2026-06-07', 34, 100000, 24, 90000, 0, 0, 4320000, 50000);
        """)
        con.commit(); con.close()
        repo = SqliteDailyRecordRepository(path)
        self.assertEqual(repo.get(date(2026, 6, 7)).data.catatan, "")
        repo.save(DailyRecord(DailyInput(tanggal=date(2026, 6, 7), catatan="ok")))
        self.assertEqual(repo.get(date(2026, 6, 7)).data.catatan, "ok")

    def test_file_baru_diberi_cap_aplikasi(self):
        import sqlite3
        from bukti_tf.infra.sqlite_repository import APP_ID
        path = os.path.join(self.tmp.name, "baru.tfdata")
        SqliteDailyRecordRepository(path)
        con = sqlite3.connect(path)
        self.assertEqual(con.execute("PRAGMA application_id").fetchone()[0], APP_ID)
        con.close()

    def test_file_milik_program_lain_ditolak(self):
        import sqlite3
        path = os.path.join(self.tmp.name, "asing.db")
        con = sqlite3.connect(path)
        con.execute("PRAGMA application_id = 12345")
        con.execute("CREATE TABLE x (a)")
        con.commit(); con.close()
        with self.assertRaises(ValueError):
            SqliteDailyRecordRepository(path)


if __name__ == "__main__":
    unittest.main()
