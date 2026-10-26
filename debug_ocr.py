"""Alat bantu pengembangan: tampilkan teks mentah hasil OCR dari satu gambar.

Pemakaian:  python debug_ocr.py path\\ke\\gambar.png
Berguna untuk menyetel regex di infra/bca_parser.py.
"""
import sys

from bukti_tf.config import locate_tesseract
from bukti_tf.infra.pillow_preprocessor import PillowThresholdPreprocessor
from bukti_tf.infra.tesseract_engine import TesseractOcrEngine

if len(sys.argv) < 2:
    sys.exit("Pemakaian: python debug_ocr.py <gambar>")

cmd, data = locate_tesseract()
image = PillowThresholdPreprocessor(150).prepare(sys.argv[1])
print(TesseractOcrEngine(cmd, data).read_text(image))
