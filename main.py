"""Composition root: satu-satunya tempat yang tahu implementasi konkret."""
import argparse
import logging
import socket
import sys
import threading
import webbrowser

from bukti_tf.config import data_dir, database_path, locate_tesseract
from bukti_tf.instance import SingleInstance

DEFAULT_PORT = 8765
TITLE = "BuktiTF"
WINDOW_TITLE = "BuktiTF · Rekap & Verifikasi Transfer"
_WEBVIEW2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

# Halaman pertama yang tampil begitu jendela terbuka, selagi aplikasi disiapkan di latar belakang.
LOADING_HTML = """<!doctype html>
<html lang="id"><head><meta charset="utf-8"><title>BuktiTF</title>
<style>
  :root{--bg:#0E161D;--text:#E6EEF2;--muted:#8FA3AE;--primary:#2DD4BF;--track:#ffffff1a}
  @media (prefers-color-scheme: light){
    :root{--bg:#EDF2F2;--text:#16212B;--muted:#5B6F7A;--primary:#0F766E;--track:#0000001a}}
  html,body{height:100%;margin:0}
  body{background:var(--bg);color:var(--text);font:15px "Segoe UI",system-ui,sans-serif;
       display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px}
  .ring{width:52px;height:52px;border:5px solid var(--track);border-top-color:var(--primary);
        border-radius:50%;animation:r .9s linear infinite}
  h1{margin:0;font-size:22px;font-weight:600;letter-spacing:.3px}
  p{margin:0;color:var(--muted)}
  .dots::after{content:"";animation:d 1.4s steps(4,end) infinite}
  @keyframes r{to{transform:rotate(360deg)}}
  @keyframes d{0%{content:""}25%{content:"."}50%{content:".."}75%{content:"..."}}
  @media (prefers-reduced-motion: reduce){.ring{animation-duration:3s}}
</style></head>
<body><div class="ring"></div><h1>BuktiTF</h1><p>Menyiapkan aplikasi<span class="dots"></span></p></body></html>"""


def build_app(lan: bool = False):
    # Impor berat ditunda ke sini agar jendela loading bisa tampil lebih dulu.
    from bukti_tf.core.extractor import ReceiptExtractor
    from bukti_tf.core.report_calculator import DailyReportCalculator
    from bukti_tf.core.settlement_service import SettlementService
    from bukti_tf.core.transfer_checker import TransferChecker
    from bukti_tf.infra.backup import backup_database
    from bukti_tf.infra.bca_parser import BcaParser
    from bukti_tf.infra.pdf_month_exporter import PdfMonthExporter
    from bukti_tf.infra.pillow_preprocessor import PillowThresholdPreprocessor
    from bukti_tf.infra.sqlite_repository import SqliteDailyRecordRepository
    from bukti_tf.infra.tesseract_engine import TesseractOcrEngine
    from bukti_tf.infra.txt_exporter import TxtExporter
    from bukti_tf.web.app import create_app

    tesseract_cmd, tessdata_dir = locate_tesseract()
    extractor = ReceiptExtractor(
        preprocessor=PillowThresholdPreprocessor(),
        ocr=TesseractOcrEngine(tesseract_cmd, tessdata_dir),
        parsers=[BcaParser()],
    )
    db = database_path()
    backup_database(db)   # sebelum repository membuka/memigrasi file
    repository = SqliteDailyRecordRepository(db)
    calculator = DailyReportCalculator()
    service = SettlementService(repository, calculator, TransferChecker())
    return create_app(extractor, TxtExporter(), calculator, repository, service,
                      PdfMonthExporter(usaha="Timbul Fishing"), lan=lan)


def _free_port(host: str, start: int) -> int:
    """Cari port kosong dengan mencoba bind. (connect_ex ke port tertutup lambat di Windows.)"""
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise SystemExit(f"Port {start}-{start + 19} semuanya terpakai.")


def _lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # tidak mengirim paket apa pun
            return s.getsockname()[0]
    except OSError:
        return "IP-komputer-ini"


def _make_server(app, host: str, port: int):
    """Server sudah listen begitu dibuat; koneksi mengantre sampai serve_forever berjalan."""
    from werkzeug.serving import make_server
    return make_server(host, port, app, threaded=True)


def _message(text: str, error: bool = True) -> None:
    """Pesan yang tetap terlihat pada exe --noconsole (print tidak akan terlihat)."""
    logging.log(logging.ERROR if error else logging.INFO, text)
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x10 if error else 0x40)
    else:
        print(text, file=sys.stderr)


def _die(text: str) -> None:
    _message(text)
    raise SystemExit(1)


def _webview2_installed() -> bool:
    """Cara resmi Microsoft: nilai `pv` pada kunci registri EdgeUpdate untuk WebView2."""
    if sys.platform != "win32":
        return True
    import winreg
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_GUID}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_GUID}"),
        (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_GUID}"),
    ]
    for root, path in keys:
        try:
            with winreg.OpenKey(root, path) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
                if version and version != "0.0.0.0":
                    return True
        except OSError:
            continue
    return False


def _run_window(host: str, port_start: int, lan: bool) -> None:
    """Jendela dibuka SEKETIKA dengan layar loading; aplikasi disiapkan di thread latar belakang."""
    try:
        import webview
    except ImportError:
        _die("Komponen jendela (pywebview) tidak ada. Pasang ulang aplikasi, atau jalankan dengan --browser.")
    if not _webview2_installed():
        _die("Microsoft Edge WebView2 Runtime belum terpasang.\n\n"
             "Unduh 'Evergreen Standalone Installer' dari microsoft.com/edge/webview2, "
             "pasang, lalu buka BuktiTF lagi.")

    webview.settings["ALLOW_DOWNLOADS"] = True   # PDF / .txt boleh diunduh
    window = webview.create_window(WINDOW_TITLE, html=LOADING_HTML,
                                   width=1240, height=820, min_size=(900, 650))

    def boot() -> None:
        try:
            port = _free_port(host, port_start)
            server = _make_server(build_app(lan=lan), host, port)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            window.load_url(f"http://localhost:{port}")
        except Exception as exc:
            logging.exception("Aplikasi gagal dimulai")
            _message(f"Aplikasi gagal dimulai:\n{exc}\n\nRincian ada di bukti_tf.log di folder data.")
            window.destroy()

    try:   # gui dipaksa: tanpa ini pywebview diam-diam memakai mesin IE lama bila WebView2 gagal
        webview.start(boot, gui="edgechromium" if sys.platform == "win32" else None)
    except Exception as exc:
        logging.exception("Jendela gagal dibuka")
        _die(f"Jendela aplikasi gagal dibuka:\n{exc}\n\nRincian ada di bukti_tf.log di folder data.")


def main() -> None:
    ap = argparse.ArgumentParser(description="BuktiTF - rekap harian & verifikasi transfer")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--lan", action="store_true",
                    help="izinkan HP/komputer lain di Wi-Fi yang sama membuka aplikasi "
                         "(tanpa kata sandi!)")
    ap.add_argument("--browser", action="store_true",
                    help="buka di browser, bukan di jendela aplikasi")
    ap.add_argument("--no-window", action="store_true",
                    help="hanya jalankan server (tanpa jendela/browser)")
    args = ap.parse_args()

    logging.basicConfig(filename=str(data_dir() / "bukti_tf.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    lock = SingleInstance(data_dir() / "bukti_tf.lock")   # tetap dirujuk sampai proses berakhir
    if not lock.acquire():
        _message("BuktiTF sudah berjalan. Cari jendelanya di taskbar.", error=False)
        raise SystemExit(0)

    host = "0.0.0.0" if args.lan else "127.0.0.1"

    if args.no_window or args.browser:
        port = _free_port(host, args.port)
        url = f"http://localhost:{port}"
        server = _make_server(build_app(lan=args.lan), host, port)
        if args.lan:
            print(f"Dari HP/komputer lain di jaringan yang sama: http://{_lan_ip()}:{port}")
            print("Peringatan: siapa pun di jaringan ini bisa membuka dan mengubah data.")
        if args.browser:
            threading.Timer(0.8, webbrowser.open, args=(url,)).start()
        print(f"BuktiTF berjalan di {url}   (Ctrl+C untuk berhenti)")
        server.serve_forever()
        return

    _run_window(host, args.port, args.lan)   # blok sampai jendela ditutup


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        logging.exception("Kesalahan fatal")
        _die("Terjadi kesalahan tak terduga. Rincian ada di bukti_tf.log di folder data aplikasi.")