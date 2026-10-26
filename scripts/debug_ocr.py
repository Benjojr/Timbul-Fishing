"""Lihat teks mentah hasil OCR untuk menyetel parser: python scripts/debug_ocr.py gambar.png"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from timbul_fishing.config import locate_tesseract
from timbul_fishing.infra.pillow_preprocessor import PillowThresholdPreprocessor
from timbul_fishing.infra.tesseract_engine import TesseractOcrEngine

if len(sys.argv) != 2:
    raise SystemExit("Pemakaian: python scripts/debug_ocr.py <gambar>")
cmd, tessdata = locate_tesseract()
image = PillowThresholdPreprocessor().prepare(sys.argv[1])
print(TesseractOcrEngine(cmd, tessdata).read_text(image))
