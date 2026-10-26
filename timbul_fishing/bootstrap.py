"""Composition root: satu-satunya tempat yang tahu implementasi konkret."""
from __future__ import annotations

from timbul_fishing.config import APP_NAME, database_path, locate_tesseract, receipts_dir
from timbul_fishing.infra.receipt_image_store import ReceiptImageStore


def build_app(lan: bool = False):
    # Impor berat ditunda ke sini agar jendela loading bisa tampil lebih dulu.
    from timbul_fishing.core.extractor import ReceiptExtractor
    from timbul_fishing.core.report_calculator import DailyReportCalculator
    from timbul_fishing.core.settlement_service import SettlementService
    from timbul_fishing.core.transfer_checker import TransferChecker
    from timbul_fishing.infra.backup import backup_database
    from timbul_fishing.infra.bca_parser import BcaParser
    from timbul_fishing.infra.pdf_month_exporter import PdfMonthExporter
    from timbul_fishing.infra.pillow_preprocessor import PillowThresholdPreprocessor
    from timbul_fishing.infra.sqlite_repository import SqliteDailyRecordRepository
    from timbul_fishing.infra.tesseract_engine import TesseractOcrEngine
    from timbul_fishing.infra.txt_exporter import TxtExporter
    from timbul_fishing.web.app import create_app

    tesseract_cmd, tessdata_dir = locate_tesseract()
    extractor = ReceiptExtractor(
        preprocessor=PillowThresholdPreprocessor(),
        ocr=TesseractOcrEngine(tesseract_cmd, tessdata_dir),
        parsers=[BcaParser()],          # bank lain: tambahkan parser baru di sini
    )
    db = database_path()
    backup_database(db)                 # sebelum repository membuka/memigrasi file
    repository = SqliteDailyRecordRepository(db)
    calculator = DailyReportCalculator()
    service = SettlementService(repository, calculator, TransferChecker())
    return create_app(extractor, TxtExporter(), calculator, repository, service,
                      PdfMonthExporter(usaha=APP_NAME), ReceiptImageStore(receipts_dir()),
                      lan=lan)
