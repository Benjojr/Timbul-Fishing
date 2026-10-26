import pytest

from bukti_tf.infra.bca_parser import BcaParser

SAMPLE = """m-Transfer: BERHASIL
21/10/2026 19:42:10
Ke 1234567890 BUDI SANTOSO
Rp 300.000,00
"""


def test_parse_full_receipt():
    r = BcaParser().parse(SAMPLE)
    assert (r.status, r.ke, r.nama, r.nominal) == ("berhasil", "1234567890", "BUDI SANTOSO", 300000)
    assert r.tanggal.isoformat() == "2026-10-21"


@pytest.mark.parametrize("text,expected", [
    ("Rp 150.000,00", 150000),
    ("Rp 150.000", 150000),            # tanpa sen: jangan jadi 1500
    ("Rp. 2.250.000,00", 2250000),
    ("Rp 1.500.000,00\n12345", 1500000),  # angka baris berikutnya tidak ikut
    ("Biaya Rp 0,00 lalu Rp 75.000,00", 75000),
    ("tidak ada nominal", None),
])
def test_nominal(text, expected):
    assert BcaParser.parse_nominal(text) == expected
