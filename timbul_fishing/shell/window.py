"""Jendela aplikasi (pywebview + Edge WebView2). Satu layar loading, lalu UI sebenarnya."""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Callable

from timbul_fishing.config import APP_NAME
from timbul_fishing.shell import dialogs
from timbul_fishing.shell.server import free_port, make_server

WINDOW_TITLE = f"{APP_NAME} · Rekap & Verifikasi Transfer"
_WEBVIEW2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
_LOADING = Path(__file__).resolve().parent.parent / "web" / "static" / "loading.html"


def webview2_installed() -> bool:
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


def run_window(build_app: Callable, host: str, port_start: int, lan: bool) -> None:
    """Jendela dibuka SEKETIKA dengan layar loading; aplikasi disiapkan di thread latar belakang."""
    try:
        import webview
    except ImportError:
        dialogs.die("Komponen jendela (pywebview) tidak ada. Pasang ulang aplikasi, "
                    "atau jalankan dengan --browser.")
    if not webview2_installed():
        dialogs.die("Microsoft Edge WebView2 Runtime belum terpasang.\n\n"
                    "Unduh 'Evergreen Standalone Installer' dari microsoft.com/edge/webview2, "
                    f"pasang, lalu buka {APP_NAME} lagi.")

    webview.settings["ALLOW_DOWNLOADS"] = True   # PDF / .txt boleh diunduh
    window = webview.create_window(WINDOW_TITLE, html=_LOADING.read_text(encoding="utf-8"),
                                   width=1240, height=820, min_size=(900, 650))

    def boot() -> None:
        try:
            port = free_port(host, port_start)
            server = make_server(build_app(lan=lan), host, port)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            window.load_url(f"http://localhost:{port}")
        except Exception as exc:
            logging.exception("Aplikasi gagal dimulai")
            dialogs.show(f"Aplikasi gagal dimulai:\n{exc}\n\nRincian ada di timbul_fishing.log "
                         "di folder data.")
            window.destroy()

    try:   # gui dipaksa: tanpa ini pywebview diam-diam memakai mesin IE lama bila WebView2 gagal
        webview.start(boot, gui="edgechromium" if sys.platform == "win32" else None)
    except Exception as exc:
        logging.exception("Jendela gagal dibuka")
        dialogs.die(f"Jendela aplikasi gagal dibuka:\n{exc}\n\nRincian ada di timbul_fishing.log "
                    "di folder data.")
