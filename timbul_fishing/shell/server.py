"""Server lokal (Flask via werkzeug) yang melayani antarmuka web."""
from __future__ import annotations

import socket


def free_port(host: str, start: int) -> int:
    """Cari port kosong dengan mencoba bind. (connect_ex ke port tertutup lambat di Windows.)"""
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise SystemExit(f"Port {start}-{start + 19} semuanya terpakai.")


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # tidak mengirim paket apa pun
            return s.getsockname()[0]
    except OSError:
        return "IP-komputer-ini"


def make_server(app, host: str, port: int):
    """Server sudah listen begitu dibuat; koneksi mengantre sampai serve_forever berjalan."""
    from werkzeug.serving import make_server as _make
    return _make(host, port, app, threaded=True)
