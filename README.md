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
├── scripts/            # build.ps1, tesseract_bundle.py, debug_ocr.py
├── vendor/tesseract/   # Tesseract portabel (isi manual; yang dibundel hanya yang dipakai)
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
Tesseract portabel: salin isi `C:\Program Files\Tesseract-OCR\` ke `vendor\tesseract\`
(boleh semuanya; saat build hanya berkas yang dipakai yang dibundel).

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
Hasil: satu berkas `dist\TimbulFishing.exe`; cukup bagikan berkas itu saja.
Perlu Microsoft Edge WebView2 Runtime (sudah ada di Windows 10/11 terbaru).

Isi exe: kode aplikasi + library Python yang di-import (PyInstaller menelusurinya otomatis) +
berkas Tesseract yang dipakai saja. `scripts\tesseract_bundle.py` memilihnya: `tesseract.exe`,
DLL yang diimpornya (dibaca dari tabel impor PE), dan `tessdata\<bahasa>.traineddata` untuk
bahasa yang dipakai `TesseractOcrEngine`. Sisanya (doc, configs, osd, DLL tak terpakai) dilewati;
bila semuanya terpakai, seluruh folder dibundel. Lihat ringkasannya dengan
`python scripts\tesseract_bundle.py --verify` (build.ps1 menjalankannya otomatis).
Darurat: `$env:TF_VENDOR_ALL = "1"` membundel seluruh folder vendor tanpa seleksi.

Catatan exe satu berkas: tiap dibuka, isinya diekstrak ke folder sementara, jadi pembukaan
pertama terasa sedikit lebih lambat daripada mode folder. Data pengguna tetap di `%APPDATA%`.

## Data
`%APPDATA%\TimbulFishing\` (rekap.tfdata, backup, log). Data dari folder lama
`ScannerBuktiTF` disalin otomatis saat pertama dibuka; folder lama tidak dihapus.
