"""Pilih berkas di vendor/tesseract yang benar-benar dipakai aplikasi, supaya exe tidak
membawa seluruh instalasi Tesseract.

Dipakai oleh:
  - TimbulFishing.spec            -> select_bundle() menghasilkan daftar `datas` PyInstaller
  - python scripts/tesseract_bundle.py [--verify]   -> lihat ringkasan / uji hasil seleksi

Yang ikut dibundel:
  1. tesseract.exe
  2. DLL di folder itu yang diimpor tesseract.exe, langsung maupun berantai (dibaca dari tabel
     impor PE lewat pefile). DLL bawaan Windows tidak ada di folder, jadi otomatis tidak ikut.
  3. tessdata/<bahasa>.traineddata untuk bahasa yang dipakai TesseractOcrEngine.
Selebihnya (doc, configs, osd.traineddata, pdf.ttf, uninstaller, DLL yang tak terpakai) tidak ikut.
Bila ternyata SEMUA berkas terpakai, seluruh folder dibundel apa adanya.

Darurat: set TF_VENDOR_ALL=1 untuk membundel seluruh folder tanpa seleksi.
"""
from __future__ import annotations

import argparse
import inspect
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VENDOR = ROOT / "vendor" / "tesseract"
EXE_NAME = "tesseract.exe"


@dataclass(frozen=True)
class Selection:
    root: Path
    used: Tuple[Path, ...]      # relatif terhadap root
    skipped: Tuple[Path, ...]   # relatif terhadap root


def engine_langs() -> Tuple[str, ...]:
    """Bahasa OCR yang dipakai aplikasi, dibaca dari nilai bawaan TesseractOcrEngine."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from timbul_fishing.infra.tesseract_engine import TesseractOcrEngine
    default = inspect.signature(TesseractOcrEngine.__init__).parameters["lang"].default
    return tuple(x for x in str(default).split("+") if x)


def pe_imports(path: Path) -> List[str]:
    """Nama DLL yang diimpor sebuah berkas PE (impor biasa dan delay-load)."""
    try:
        import pefile
    except ImportError as exc:
        raise SystemExit("Modul 'pefile' belum terpasang: pip install -r requirements-dev.txt") from exc
    pe = pefile.PE(str(path), fast_load=True)
    try:
        pe.parse_data_directories(directories=[
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
        ])
        entries = (list(getattr(pe, "DIRECTORY_ENTRY_IMPORT", []))
                   + list(getattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT", [])))
        return [e.dll.decode("ascii", "ignore") for e in entries]
    finally:
        pe.close()


def select(root: Path, langs: Sequence[str],
           imports_of: Callable[[Path], List[str]] = pe_imports) -> Selection:
    root = Path(root)
    exe = root / EXE_NAME
    if not exe.is_file():
        raise FileNotFoundError(f"{exe} tidak ada.")

    dlls = {p.name.lower(): p for p in root.glob("*.dll")}   # Windows mencari DLL di folder exe
    needed: Set[Path] = set()
    queue = [exe]
    while queue:
        for name in imports_of(queue.pop()):
            dll = dlls.get(name.lower())
            if dll is not None and dll not in needed:
                needed.add(dll)
                queue.append(dll)

    keep: Set[Path] = {exe, *needed}
    for lang in langs:
        data = root / "tessdata" / f"{lang}.traineddata"
        if not data.is_file():
            raise FileNotFoundError(f"{data} tidak ada (bahasa '{lang}' dipakai aplikasi).")
        keep.add(data)

    everything = sorted(p for p in root.rglob("*") if p.is_file())
    used = tuple(p.relative_to(root) for p in everything if p in keep)
    skipped = tuple(p.relative_to(root) for p in everything if p not in keep)
    return Selection(root, used, skipped)


def datas_for(sel: Selection, dest: str = "tesseract") -> List[Tuple[str, str]]:
    """Daftar (sumber, folder-tujuan) untuk `datas` PyInstaller."""
    if not sel.skipped:                       # semua terpakai: bundel folder apa adanya
        return [(str(sel.root), dest)]
    return [(str(sel.root / rel), (Path(dest) / rel.parent).as_posix()) for rel in sel.used]


def _mb(files: Sequence[Path], root: Path) -> float:
    return sum((root / f).stat().st_size for f in files) / 1_048_576


def report(sel: Selection) -> str:
    lines = [f"Tesseract: {len(sel.used)} berkas dibundel ({_mb(sel.used, sel.root):.1f} MB), "
             f"{len(sel.skipped)} dilewati ({_mb(sel.skipped, sel.root):.1f} MB)."]
    lines += [f"  + {p}" for p in sel.used]
    lines += [f"  - {p}" for p in sel.skipped]
    if not sel.skipped:
        lines.append("  Semua berkas terpakai: seluruh folder dibundel.")
    return "\n".join(lines)


def verify(sel: Selection, langs: Sequence[str]) -> Optional[str]:
    """Salin hasil seleksi ke folder kosong lalu jalankan Tesseract dari sana.
    Mengembalikan pesan galat, atau None bila lolos. Hanya bermakna di Windows."""
    if sys.platform != "win32":
        return "dilewati: pengujian hanya jalan di Windows"
    from PIL import Image, ImageDraw, ImageFont
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "t"
        for rel in sel.used:
            dst = base / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sel.root / rel, dst)
        exe = str(base / EXE_NAME)
        env = dict(os.environ, TESSDATA_PREFIX=str(base / "tessdata"))

        def run(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run([exe, *args], capture_output=True, text=True, env=env, timeout=120)

        r = run("--list-langs")
        if r.returncode != 0:
            return f"tesseract gagal dijalankan (kode {r.returncode}); kemungkinan ada DLL kurang.\n{r.stderr}"
        missing = [l for l in langs if l not in r.stdout]
        if missing:
            return f"bahasa tidak terbaca: {', '.join(missing)}"

        img = Image.new("L", (420, 120), 255)
        ImageDraw.Draw(img).text((10, 30), "TEST 123", fill=0, font=ImageFont.load_default(size=48))
        png = Path(tmp) / "uji.png"
        img.save(png)
        # sama seperti pytesseract: `txt` ikut sebagai argumen terakhir
        r = run(str(png), "stdout", "-l", "+".join(langs), "txt")
        if r.returncode != 0:
            return f"OCR uji gagal (kode {r.returncode}).\n{r.stderr}"
    return None


def select_bundle(root: Path = DEFAULT_VENDOR, dest: str = "tesseract") -> List[Tuple[str, str]]:
    """Dipanggil dari TimbulFishing.spec."""
    root = Path(root)
    if not (root / EXE_NAME).is_file():
        print(f"PERINGATAN: {root / EXE_NAME} tidak ada - exe tidak akan membawa Tesseract.")
        return []
    if os.environ.get("TF_VENDOR_ALL") == "1":
        print("TF_VENDOR_ALL=1: seluruh folder vendor/tesseract dibundel tanpa seleksi.")
        return [(str(root), dest)]
    sel = select(root, engine_langs())
    print(report(sel))
    return datas_for(sel, dest)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Ringkasan seleksi berkas Tesseract untuk exe.")
    ap.add_argument("--root", type=Path, default=DEFAULT_VENDOR)
    ap.add_argument("--verify", action="store_true", help="jalankan Tesseract dari hasil seleksi")
    args = ap.parse_args(argv)
    if not (args.root / EXE_NAME).is_file():
        print(f"PERINGATAN: {args.root / EXE_NAME} tidak ada - tidak ada yang diseleksi.")
        return 0
    langs = engine_langs()
    sel = select(args.root, langs)
    print(report(sel))
    if args.verify:
        err = verify(sel, langs)
        if err and not err.startswith("dilewati"):
            print(f"GAGAL: {err}\nCoba TF_VENDOR_ALL=1 untuk membundel semuanya, "
                  "lalu laporkan DLL yang kurang.")
            return 1
        print("Uji seleksi:", err or "lolos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
