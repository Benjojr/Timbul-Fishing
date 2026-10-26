"""Tes ringan lapisan web: pengaman dan halaman utama, tanpa OCR."""
import tempfile
import unittest
from pathlib import Path

from timbul_fishing.core.report_calculator import DailyReportCalculator
from timbul_fishing.core.settlement_service import SettlementService
from timbul_fishing.core.transfer_checker import TransferChecker
from timbul_fishing.infra.sqlite_repository import SqliteDailyRecordRepository
from timbul_fishing.infra.txt_exporter import TxtExporter
from timbul_fishing.web.app import HEADER_NAME, HEADER_VALUE, create_app
from timbul_fishing.infra.receipt_image_store import ReceiptImageStore


class WebTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        calc = DailyReportCalculator()
        repo = SqliteDailyRecordRepository(Path(self.tmp.name) / "t.tfdata")
        service = SettlementService(repo, calc, TransferChecker())
        self.images = ReceiptImageStore(Path(self.tmp.name) / "bukti")
        app = create_app(extractor=None, exporter=TxtExporter(), calculator=calc,
                         repository=repo, service=service, pdf_exporter=None,
                         images=self.images)
        self.client = app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_halaman_utama(self):
        r = self.client.get("/", base_url="http://localhost")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Timbul Fishing", r.data)

    def test_host_asing_ditolak(self):
        self.assertEqual(self.client.get("/", base_url="http://evil.example").status_code, 403)

    def test_tulis_tanpa_header_ditolak(self):
        r = self.client.post("/api/record", json={}, base_url="http://localhost")
        self.assertEqual(r.status_code, 403)
        r = self.client.post("/api/record", json={}, base_url="http://localhost",
                             headers={HEADER_NAME: HEADER_VALUE})
        self.assertNotEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
