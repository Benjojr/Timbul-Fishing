# BuktiTF — Rekap harian & verifikasi transfer (UI web)

Aplikasi desktop (jendela sendiri). Tampilannya ditulis dengan HTML/CSS/JS dan dirender oleh
pywebview (Windows: Microsoft Edge WebView2, sudah ada di Windows 10/11 terbaru).

```
pip install -r requirements.txt
python main.py                 # jendela aplikasi
python main.py --browser       # buka di browser biasa
python main.py --lan           # izinkan HP/PC lain di Wi-Fi yang sama (TANPA kata sandi)
python main.py --no-window     # hanya server
```

Tesseract dicari di folder `tesseract/` samping aplikasi, lalu PATH, lalu lokasi default Windows.
Data tetap di `%APPDATA%\ScannerBuktiTF\rekap.tfdata` (sama seperti versi desktop).

Pintasan: `Ctrl+V` tempel gambar bukti · `Ctrl+S` simpan · `Enter` pindah ke isian berikutnya
(Enter di nominal pengeluaran terakhir menambah baris baru).

## Struktur
- `bukti_tf/core`, `domain`, `infra` — tidak berubah dari versi desktop.
- `bukti_tf/web/app.py` — API Flask (stateless); `codec.py` JSON↔domain; `presenter.py` teks & warna status.
- `bukti_tf/web/static/` — `index.html`, `app.css`, `app.js` (tanpa library/CDN, jalan offline).

## Build exe (PyInstaller)
Folder `static` harus ikut dibundel:
`pyinstaller --onefile --noconsole --add-data "bukti_tf/web/static;bukti_tf/web/static" --add-data "tesseract;tesseract" main.py`
