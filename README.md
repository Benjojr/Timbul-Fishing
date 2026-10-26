# Timbul Fishing

Aplikasi desktop (Windows) untuk rekap harian pemancingan dan verifikasi transfer:
membaca gambar bukti transfer m-BCA (OCR), menghitung sisa harian, mencocokkannya dengan
transfer, dan mengekspor rekap bulanan (Excel / PDF).

Python + Flask + pywebview (Edge WebView2) + Tesseract OCR + SQLite.

## Struktur

```
timbul-fishing/
├── timbul_fishing/
│   ├── __main__.py     # titik masuk (CLI)
│   ├── bootstrap.py    # composition root: merakit semua bagian
│   ├── config.py       # lokasi Tesseract dan folder data
│   ├── domain/         # data murni (Receipt, DailyReport, ...)
│   ├── core/           # logika & kontrak (tanpa Pillow/Tesseract/Flask/SQLite)
│   ├── infra/          # OCR, parser BCA, SQLite, exporter, backup
│   ├── web/            # API Flask + static/ (index.html, app.css, app.js, loading.html)
│   └── shell/          # jendela pywebview, server lokal, dialog
├── tests/
├── scripts/            # build.ps1, debug_ocr.py
├── vendor/tesseract/   # Tesseract portabel (isi manual)
└── TimbulFishing.spec  # satu-satunya konfigurasi PyInstaller
```

Aturan ketergantungan: `infra`, `web`, `shell` boleh mengenal `core` dan `domain`;
`core` tidak boleh mengimpor Pillow, Tesseract, Flask, atau SQLite.

## Persiapan
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```
Tesseract portabel: salin `tesseract.exe`, semua `*.dll`, dan `tessdata\eng.traineddata`
dari `C:\Program Files\Tesseract-OCR\` ke `vendor\tesseract\`.

## Pengembangan
```
python -m timbul_fishing --browser      # cepat: buka di browser, tanpa jendela
python -m timbul_fishing                # jendela aplikasi
python -m unittest discover -s tests -t .
python scripts/debug_ocr.py gambar.png  # teks mentah OCR, untuk menyetel parser
```

| Yang ingin diubah | Sentuh |
|---|---|
| Regex bukti BCA | `infra/bca_parser.py` |
| Bank lain | parser baru di `infra/`, daftarkan di `bootstrap.py` |
| Rumus rekap | `core/report_calculator.py` |
| Tampilan | `web/static/` |
| Format ekspor | exporter baru di `infra/`, rakit di `bootstrap.py` |

## Build exe
```
.\scripts\build.ps1
```
Hasil: `dist\TimbulFishing\TimbulFishing.exe`. Bagikan seluruh folder.
Perlu Microsoft Edge WebView2 Runtime (sudah ada di Windows 10/11 terbaru).

## Data
`%APPDATA%\TimbulFishing\` (rekap.tfdata, backup, log). Data dari folder lama
`ScannerBuktiTF` disalin otomatis saat pertama dibuka; folder lama tidak dihapus.
