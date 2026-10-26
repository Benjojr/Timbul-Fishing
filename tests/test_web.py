import io
from datetime import date

import pytest

from bukti_tf.core.errors import UnsupportedReceiptError
from bukti_tf.core.report_calculator import DailyReportCalculator
from bukti_tf.core.settlement_service import SettlementService
from bukti_tf.core.transfer_checker import TransferChecker
from bukti_tf.domain.receipt import TransferReceipt
from bukti_tf.infra.pdf_month_exporter import PdfMonthExporter
from bukti_tf.infra.sqlite_repository import SqliteDailyRecordRepository
from bukti_tf.infra.txt_exporter import TxtExporter
from bukti_tf.web.app import HEADER_NAME, HEADER_VALUE, create_app
from bukti_tf.web.codec import parse_form, parse_int

H = {HEADER_NAME: HEADER_VALUE}


class FakeExtractor:
    def __init__(self):
        self.receipt = TransferReceipt("berhasil", "22/10/2026 09:00:00", "1234567890", "X", 250000)
        self.fail = False

    def extract(self, path):
        assert path.endswith((".png", ".jpg"))
        if self.fail:
            raise UnsupportedReceiptError("Format bukti transfer tidak dikenali.")
        return self.receipt


@pytest.fixture
def ctx(tmp_path):
    repo = SqliteDailyRecordRepository(tmp_path / "t.db")
    calc = DailyReportCalculator()
    svc = SettlementService(repo, calc, TransferChecker())
    ext = FakeExtractor()
    app = create_app(ext, TxtExporter(), calc, repo, svc, PdfMonthExporter())
    return app.test_client(), ext, repo


def form(tanggal="2026-10-19", peserta="10", harga="10.000", hadiah="", rincian=None, catatan=""):
    return {"tanggal": tanggal,
            "sesi": [{"peserta": peserta, "harga": harga}, {"peserta": "", "harga": ""},
                     {"peserta": "", "harga": ""}],
            "hadiah": hadiah, "rincian": rincian or [], "catatan": catatan}


RECEIPT = {"status": "berhasil", "waktu": "22/10/2026 09:00:00", "ke": "1234567890",
           "nama": "X", "nominal": 250000}


def post(c, url, **json):
    return c.post(url, json=json, headers=H)


# ---------------------------------------------------------------- codec
def test_parse_int_and_limits():
    assert parse_int("Rp 1.500.000") == 1500000 and parse_int("") == 0
    with pytest.raises(ValueError):
        parse_int("12a")
    with pytest.raises(ValueError):
        parse_int("9" * 13)


def test_parse_form_reports_every_bad_field():
    f = form(tanggal="", peserta="x", hadiah="1k",
             rincian=[{"keperluan": "", "nominal": ""}, {"keperluan": "Pakan", "nominal": ""}])
    data, invalid = parse_form(f)
    assert data is None
    assert set(invalid) == {"tanggal", "peserta0", "hadiah", "rincian1"}


# ---------------------------------------------------------------- guard
def test_write_requires_custom_header(ctx):
    c, _, _ = ctx
    assert c.post("/api/evaluate", json={"form": form()}).status_code == 403
    assert c.get("/").status_code == 200


def test_foreign_host_rejected_unless_lan(ctx):
    c, _, _ = ctx
    assert c.get("/", headers={"Host": "evil.example"}).status_code == 403
    assert c.get("/", headers={"Host": "localhost:8765"}).status_code == 200


# ---------------------------------------------------------------- evaluate
def test_evaluate_totals_and_check(ctx):
    c, _, _ = ctx
    r = post(c, "/api/evaluate", form=form(rincian=[{"keperluan": "Pakan", "nominal": "20.000"}])).get_json()
    assert r["report"]["pemasukan"] == "Rp 100.000"
    assert r["report"]["sisa"] == "Rp 80.000"
    assert r["check"]["status"] == "belum_ada"
    assert r["excel_row"].startswith("2026-10-19\tMon\t10")


def test_evaluate_invalid_input(ctx):
    c, _, _ = ctx
    r = post(c, "/api/evaluate", form=form(peserta="abc")).get_json()
    assert r["report"] is None and r["invalid"] == ["peserta0"]
    assert r["check"]["status"] == "invalid" and r["excel_row"] is None


def test_evaluate_matching_receipt_is_checked(ctx):
    c, _, _ = ctx
    rec = dict(RECEIPT, nominal=100000)
    r = post(c, "/api/evaluate", form=form(), receipt=rec, cover=[]).get_json()
    assert r["check"]["status"] == "checked"
    assert r["excel_row"].rstrip().endswith("Checked")


# ---------------------------------------------------------------- simpan / muat / hapus
def test_save_load_delete_roundtrip(ctx):
    c, _, repo = ctx
    r = post(c, "/api/record", form=form(catatan="ramai", rincian=[{"keperluan": "Pakan", "nominal": "5.000"}]))
    assert r.status_code == 200 and r.get_json()["saved"] == "2026-10-19"
    got = c.get("/api/record?tanggal=2026-10-19").get_json()["record"]
    assert got["form"]["catatan"] == "ramai"
    assert got["form"]["sesi"][0] == {"peserta": "10", "harga": "10.000"}
    assert got["form"]["rincian"] == [{"keperluan": "Pakan", "nominal": "5.000"}]
    assert c.get("/api/record?tanggal=2026-10-20").get_json() == {"record": None}
    assert c.delete("/api/record?tanggal=2026-10-19", headers=H).status_code == 200
    assert repo.get(date(2026, 10, 19)) is None


def test_save_invalid_is_rejected(ctx):
    c, _, repo = ctx
    r = post(c, "/api/record", form=form(hadiah="zz"))
    assert r.status_code == 400 and r.get_json()["invalid"] == ["hadiah"]


def test_overwrite_needs_confirmation(ctx):
    c, _, _ = ctx
    post(c, "/api/record", form=form())
    r = post(c, "/api/record", form=form(peserta="20"))
    assert r.status_code == 409 and r.get_json()["needs_confirm"]
    assert post(c, "/api/record", form=form(peserta="20"), loaded="2026-10-19").status_code == 200
    assert post(c, "/api/record", form=form(peserta="30"), overwrite=True).status_code == 200


def test_save_links_receipt_and_blocks_reuse(ctx):
    c, _, repo = ctx
    rec = dict(RECEIPT, nominal=100000)
    r = post(c, "/api/record", form=form(), receipt=rec, cover=[]).get_json()
    assert r["cover"] == ["2026-10-19"] and r["warning"] is None
    # bukti yang sama dipakai di hari lain -> rekap tersimpan, bukti dilepas, ada peringatan
    r2 = post(c, "/api/record", form=form(tanggal="2026-10-20"), receipt=rec, cover=[]).get_json()
    assert r2["receipt"] is None and r2["cover"] == [] and r2["warning"]
    assert repo.get(date(2026, 10, 20)) is not None


# ---------------------------------------------------------------- gabungan
def test_combined_payment_flow(ctx):
    c, _, repo = ctx
    post(c, "/api/record", form=form(tanggal="2026-10-19", peserta="10"))   # sisa 100.000
    f20 = form(tanggal="2026-10-20", peserta="15")                            # sisa 150.000, belum disimpan
    ev = post(c, "/api/evaluate", form=f20, receipt=RECEIPT, cover=[]).get_json()
    assert ev["check"]["status"] == "gabungan"
    assert [x["days"] for x in ev["candidates"]] == [["2026-10-19", "2026-10-20"]]

    ap = post(c, "/api/apply", form=f20, receipt=RECEIPT, days=["2026-10-19", "2026-10-20"])
    assert ap.status_code == 200 and ap.get_json()["includes_form"]
    ev2 = post(c, "/api/evaluate", form=f20, receipt=RECEIPT, cover=ap.get_json()["cover"]).get_json()
    assert ev2["check"]["status"] == "checked" and ev2["candidates"] == []
    month = c.get("/api/month?year=2026&month=10").get_json()
    assert [r["ket"] for r in month["rows"]] == ["✓ Gabung", "✓ Gabung"]


def test_apply_to_other_days_only_detaches_form(ctx):
    c, _, _ = ctx
    post(c, "/api/record", form=form(tanggal="2026-10-18", peserta="10"))
    post(c, "/api/record", form=form(tanggal="2026-10-19", peserta="15"))
    r = post(c, "/api/apply", form=form(tanggal="2026-10-25", peserta="1"), receipt=RECEIPT,
             days=["2026-10-18", "2026-10-19"]).get_json()
    assert r["includes_form"] is False and r["cover"] == []


def test_apply_conflict_returns_409(ctx):
    c, _, _ = ctx
    post(c, "/api/record", form=form(tanggal="2026-10-18", peserta="10"))
    post(c, "/api/record", form=form(tanggal="2026-10-19", peserta="15"))
    body = dict(form=form(tanggal="2026-10-25"), receipt=RECEIPT, days=["2026-10-18", "2026-10-19"])
    assert post(c, "/api/apply", **body).status_code == 200
    assert post(c, "/api/apply", **dict(body, days=["2026-10-18"])).status_code == 409


# ---------------------------------------------------------------- OCR
def test_ocr_ok_and_errors(ctx):
    c, ext, _ = ctx
    data = {"image": (io.BytesIO(b"\x89PNG fake"), "paste.png")}
    r = c.post("/api/ocr", data=data, headers=H, content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json()["receipt"]["nominal"] == 250000
    ext.fail = True
    r = c.post("/api/ocr", data={"image": (io.BytesIO(b"x"), "a.jpg")}, headers=H,
               content_type="multipart/form-data")
    assert r.status_code == 422 and "tidak dikenali" in r.get_json()["error"]
    assert c.post("/api/ocr", headers=H).status_code == 400


# ---------------------------------------------------------------- riwayat & ekspor
def test_month_summary_excel_and_pdf(ctx):
    c, _, _ = ctx
    assert c.get("/api/month?year=2026&month=10").get_json()["summary"] is None
    assert c.get("/api/month.pdf?year=2026&month=10").status_code == 404
    post(c, "/api/record", form=form(tanggal="2026-10-19"))
    post(c, "/api/record", form=form(tanggal="2026-10-20", peserta="5"))
    m = c.get("/api/month?year=2026&month=10").get_json()
    assert m["title"] == "Oktober 2026" and len(m["rows"]) == 2
    assert "Pemasukan Rp 150.000" in m["summary"]
    assert len(m["excel"].splitlines()) == 2
    pdf = c.get("/api/month.pdf?year=2026&month=10")
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
    assert c.get("/api/month?year=2026&month=13").status_code == 400


def test_receipt_txt_download(ctx):
    c, _, _ = ctx
    r = post(c, "/api/receipt/txt", receipt=RECEIPT)
    assert r.status_code == 200 and b"Nominal: 250000" in r.data
    assert post(c, "/api/receipt/txt", receipt=None).status_code == 400
