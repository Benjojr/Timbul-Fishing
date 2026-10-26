"""Titik masuk: `python -m timbul_fishing` (atau exe hasil build)."""
from __future__ import annotations

import argparse
import logging
import threading
import webbrowser

from timbul_fishing.bootstrap import build_app
from timbul_fishing.config import APP_NAME, data_dir
from timbul_fishing.instance import SingleInstance
from timbul_fishing.shell import dialogs
from timbul_fishing.shell.server import free_port, lan_ip, make_server
from timbul_fishing.shell.window import run_window

DEFAULT_PORT = 8765


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=f"{APP_NAME} - rekap harian & verifikasi transfer")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--lan", action="store_true",
                    help="izinkan HP/komputer lain di Wi-Fi yang sama membuka aplikasi (tanpa kata sandi!)")
    ap.add_argument("--browser", action="store_true", help="buka di browser, bukan di jendela aplikasi")
    ap.add_argument("--no-window", action="store_true", help="hanya jalankan server")
    return ap.parse_args()


def _serve_only(args: argparse.Namespace, host: str) -> None:
    port = free_port(host, args.port)
    url = f"http://localhost:{port}"
    server = make_server(build_app(lan=args.lan), host, port)
    if args.lan:
        print(f"Dari HP/komputer lain di jaringan yang sama: http://{lan_ip()}:{port}")
        print("Peringatan: siapa pun di jaringan ini bisa membuka dan mengubah data.")
    if args.browser:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    print(f"{APP_NAME} berjalan di {url}   (Ctrl+C untuk berhenti)")
    server.serve_forever()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(filename=str(data_dir() / "timbul_fishing.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    lock = SingleInstance(data_dir() / "timbul_fishing.lock")   # dirujuk sampai proses berakhir
    if not lock.acquire():
        dialogs.show(f"{APP_NAME} sudah berjalan. Cari jendelanya di taskbar.", error=False)
        raise SystemExit(0)

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    if args.no_window or args.browser:
        _serve_only(args, host)
    else:
        run_window(build_app, host, args.port, args.lan)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        logging.exception("Kesalahan fatal")
        dialogs.die("Terjadi kesalahan tak terduga. Rincian ada di timbul_fishing.log di folder data aplikasi.")
