from datetime import date

from bukti_tf.core.settlement_matcher import SettlementMatcher
from bukti_tf.domain.daily_report import DailyReport


def rep(d, sisa):
    return DailyReport(tanggal=date(2026, 10, d), sesi=(), hadiah=0, pengeluaran=0,
                       total_pemasukan=sisa, total_pengeluaran=0, sisa=sisa)


M = SettlementMatcher()


def days(c):
    return [d.day for d in c.days]


def test_single_day():
    r = M.find(300, [rep(19, 100), rep(20, 300)], date(2026, 10, 21))
    assert [days(c) for c in r] == [[20]]


def test_two_days_combined():
    r = M.find(450, [rep(19, 200), rep(20, 250), rep(21, 999)], date(2026, 10, 22))
    assert [days(c) for c in r] == [[19, 20]]


def test_transfer_date_irregular_two_or_three_days_later():
    reports = [rep(15, 100), rep(16, 200), rep(17, 300)]
    for paid in (date(2026, 10, 19), date(2026, 10, 20), date(2026, 10, 25)):
        r = M.find(500, reports, paid)
        assert [days(c) for c in r] == [[16, 17]], paid


def test_days_after_transfer_excluded_unless_nothing_else_matches():
    r = M.find(300, [rep(20, 300), rep(25, 300)], date(2026, 10, 21))
    assert [days(c) for c in r] == [[20]]
    r = M.find(300, [rep(25, 300)], date(2026, 10, 21))
    assert r[0].after_transfer is True


def test_contiguous_preferred_over_scattered():
    # 100+200 (hari 19,20 berurutan) vs 100+200 (19 dan 22): hanya yang berurutan
    reports = [rep(19, 100), rep(20, 200), rep(21, 50), rep(22, 200)]
    r = M.find(300, reports, date(2026, 10, 25))
    assert [days(c) for c in r] == [[19, 20]]


def test_scattered_when_no_contiguous():
    r = M.find(300, [rep(19, 100), rep(20, 50), rep(21, 200)], date(2026, 10, 25))
    assert [days(c) for c in r] == [[19, 21]]
    assert r[0].contiguous is False


def test_ambiguous_returns_all_oldest_first():
    r = M.find(300, [rep(18, 300), rep(20, 300)], date(2026, 10, 25))
    assert [days(c) for c in r] == [[18], [20]]


def test_no_match_and_non_positive_sisa_ignored():
    assert M.find(999, [rep(19, 100)], None) == []
    assert M.find(100, [rep(19, 100), rep(20, 0), rep(21, -50)], None)[0].days[0].day == 19
