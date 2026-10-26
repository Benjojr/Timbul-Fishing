import sqlite3
from datetime import date

import pytest

from bukti_tf.core.errors import ReceiptConflictError
from bukti_tf.core.report_calculator import DailyReportCalculator
from bukti_tf.core import settlement_service as ss
from bukti_tf.core.transfer_checker import TransferChecker
from bukti_tf.domain import check_result as cr
from bukti_tf.domain.daily_record import DailyRecord
from bukti_tf.domain.daily_report import DailyInput, SessionEntry
from bukti_tf.domain.receipt import TransferReceipt
from bukti_tf.infra.sqlite_repository import SqliteDailyRecordRepository


@pytest.fixture
def env(tmp_path):
    repo = SqliteDailyRecordRepository(tmp_path / "t.db")
    calc, chk = DailyReportCalculator(), TransferChecker()
    return repo, calc, ss.SettlementService(repo, calc, chk)


def day(d, peserta, harga=10000):
    return DailyInput(tanggal=date(2026, 10, d),
                      sesi=(SessionEntry(peserta, harga), SessionEntry(), SessionEntry()))


def receipt(nominal, waktu="22/10/2026 10:00:00", status="berhasil"):
    return TransferReceipt(status=status, waktu=waktu, ke="1234567890", nama="X", nominal=nominal)


def test_combined_two_days_one_transfer(env):
    repo, calc, svc = env
    repo.save(DailyRecord(day(19, 10)))   # sisa 100.000
    repo.save(DailyRecord(day(20, 15)))   # sisa 150.000
    r = receipt(250000, "22/10/2026 09:00:00")

    sug = svc.suggest(r)
    assert [[d.day for d in c.days] for c in sug.candidates] == [[19, 20]]

    svc.apply(r, sug.candidates[0].days)
    for d in (19, 20):
        rec = repo.get(date(2026, 10, d))
        report, res = svc.evaluate(rec)
        assert res.status == cr.CHECKED and res.sisa == 250000
        assert [x.day for x in rec.cover] == [19, 20]


def test_unsaved_current_form_is_a_candidate(env):
    repo, calc, svc = env
    repo.save(DailyRecord(day(19, 10)))
    current = calc.calculate(day(20, 15))      # belum disimpan
    sug = svc.suggest(receipt(250000), current)
    assert [[d.day for d in c.days] for c in sug.candidates] == [[19, 20]]


def test_duplicate_receipt_rejected_and_detected(env):
    repo, calc, svc = env
    repo.save(DailyRecord(day(19, 10)))
    repo.save(DailyRecord(day(20, 10)))
    r = receipt(100000)
    svc.apply(r, [date(2026, 10, 19)])

    assert svc.suggest(r).duplicate_days == (date(2026, 10, 19),)
    with pytest.raises(ReceiptConflictError):
        svc.apply(r, [date(2026, 10, 20)])
    # Re-scan di hari yang sama tidak error
    svc.apply(r, [date(2026, 10, 19)])


def test_day_with_other_receipt_needs_replace(env):
    repo, calc, svc = env
    repo.save(DailyRecord(day(19, 10)))
    svc.apply(receipt(100000, "20/10/2026 08:00:00"), [date(2026, 10, 19)])
    new = receipt(90000, "21/10/2026 08:00:00")
    with pytest.raises(ReceiptConflictError):
        svc.apply(new, [date(2026, 10, 19)])
    svc.apply(new, [date(2026, 10, 19)], replace=True)
    assert repo.get(date(2026, 10, 19)).receipt.nominal == 90000


def test_settled_days_not_suggested_again(env):
    repo, calc, svc = env
    repo.save(DailyRecord(day(19, 10)))
    repo.save(DailyRecord(day(20, 10)))
    svc.apply(receipt(100000, "20/10/2026 08:00:00"), [date(2026, 10, 19)])
    sug = svc.suggest(receipt(100000, "21/10/2026 08:00:00"))
    assert [[d.day for d in c.days] for c in sug.candidates] == [[20]]


def test_delete_day_frees_receipt(env):
    repo, calc, svc = env
    repo.save(DailyRecord(day(19, 10)))
    r = receipt(100000)
    svc.apply(r, [date(2026, 10, 19)])
    repo.delete(date(2026, 10, 19))
    assert repo.days_for_receipt(r) == ()


def test_group_mismatch_shows_selisih_when_a_day_is_edited(env):
    repo, calc, svc = env
    repo.save(DailyRecord(day(19, 10)))
    repo.save(DailyRecord(day(20, 15)))
    svc.apply(receipt(250000), [date(2026, 10, 19), date(2026, 10, 20)])
    repo.save(DailyRecord(day(20, 16)))        # pengelola ralat jumlah peserta
    _, res = svc.evaluate(repo.get(date(2026, 10, 19)))
    assert res.status == cr.SELISIH and res.selisih == -10000


def test_date_notes_are_soft(env):
    repo, calc, svc = env
    chk = TransferChecker()
    rep = calc.calculate(day(20, 10))
    early = chk.check(rep, receipt(100000, "19/10/2026 08:00:00"))
    late = chk.check(rep, receipt(100000, "20/11/2026 08:00:00"))
    ok3 = chk.check(rep, receipt(100000, "23/10/2026 08:00:00"))
    assert early.status == late.status == ok3.status == cr.CHECKED
    assert early.catatan and late.catatan and ok3.catatan is None


def test_legacy_receipts_migrated(tmp_path):
    p = tmp_path / "old.db"
    con = sqlite3.connect(p)
    con.executescript("""
    CREATE TABLE daily_record (tanggal TEXT PRIMARY KEY,
      peserta1 INTEGER NOT NULL, harga1 INTEGER NOT NULL, peserta2 INTEGER NOT NULL, harga2 INTEGER NOT NULL,
      peserta3 INTEGER NOT NULL, harga3 INTEGER NOT NULL, hadiah INTEGER NOT NULL, pengeluaran INTEGER NOT NULL,
      has_receipt INTEGER NOT NULL DEFAULT 0, r_status TEXT, r_waktu TEXT, r_ke TEXT, r_nama TEXT, r_nominal INTEGER);
    INSERT INTO daily_record VALUES ('2026-10-19',10,10000,0,0,0,0,0,0,1,'berhasil','20/10/2026 08:00:00','111','A',100000);
    INSERT INTO daily_record VALUES ('2026-10-20',0,0,0,0,0,0,0,0,0,NULL,NULL,NULL,NULL,NULL);
    """)
    con.commit(); con.close()
    repo = SqliteDailyRecordRepository(p)
    rec = repo.get(date(2026, 10, 19))
    assert rec.receipt.nominal == 100000 and [d.day for d in rec.cover] == [19]
    assert repo.get(date(2026, 10, 20)).receipt is None
    SqliteDailyRecordRepository(p)  # idempoten


# ---------- rincian pengeluaran ----------
from bukti_tf.domain.daily_report import ExpenseItem


def test_expense_items_sum_and_roundtrip(env):
    repo, calc, svc = env
    d = DailyInput(
        tanggal=date(2026, 10, 19),
        sesi=(SessionEntry(20, 10000), SessionEntry(), SessionEntry()),   # masuk 200.000
        hadiah=50000,
        rincian=(ExpenseItem("Pakan", 30000), ExpenseItem("Listrik", 20000)),
    )
    rep = calc.calculate(d)
    assert (rep.pengeluaran, rep.total_pengeluaran, rep.sisa) == (50000, 100000, 100000)

    repo.save(DailyRecord(d))
    got = repo.get(date(2026, 10, 19))
    assert [(i.keperluan, i.nominal) for i in got.data.rincian] == [("Pakan", 30000), ("Listrik", 20000)]
    assert got.data.pengeluaran == 50000
    # simpan ulang dengan rincian lebih sedikit: baris lama tidak tersisa
    repo.save(DailyRecord(DailyInput(tanggal=d.tanggal, sesi=d.sesi,
                                     rincian=(ExpenseItem("Pakan", 10000),))))
    assert len(repo.get(d.tanggal).data.rincian) == 1
    repo.delete(d.tanggal)
    assert repo.get(d.tanggal) is None


def test_legacy_lump_expense_still_works(env):
    repo, calc, svc = env
    repo.save(DailyRecord(DailyInput(tanggal=date(2026, 10, 19), pengeluaran=40000)))
    got = repo.get(date(2026, 10, 19))
    assert got.data.rincian == () and got.data.pengeluaran == 40000
    assert calc.calculate(got.data).total_pengeluaran == 40000


def test_negative_expense_item_rejected():
    from bukti_tf.core.errors import InvalidReportInputError
    with pytest.raises(InvalidReportInputError):
        DailyReportCalculator().calculate(
            DailyInput(tanggal=date(2026, 10, 19), rincian=(ExpenseItem("x", -1),)))
