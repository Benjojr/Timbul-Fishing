@echo off
setlocal
if not exist vendor\tesseract\tesseract.exe (
  echo Salin Tesseract ke vendor\tesseract dulu. Lihat README.md
  exit /b 1
)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean --onedir --windowed --name ScannerBuktiTF ^
  --add-data "vendor\tesseract;tesseract" main.py
echo.
echo Selesai. Hasil: dist\ScannerBuktiTF\ScannerBuktiTF.exe
