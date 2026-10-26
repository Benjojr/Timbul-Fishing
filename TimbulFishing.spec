# PyInstaller: satu-satunya spec. Build lewat scripts/build.ps1.
# Hasil: SATU berkas dist/TimbulFishing.exe (isinya diekstrak ke folder sementara saat dijalankan).
import sys
from pathlib import Path

ROOT = Path(SPECPATH)
sys.path.insert(0, str(ROOT / "scripts"))
from tesseract_bundle import select_bundle  # noqa: E402

datas = [(str(ROOT / "timbul_fishing" / "web" / "static"), "timbul_fishing/web/static")]
# Dari vendor/tesseract hanya berkas yang dipakai (exe + DLL yang diimpor + tessdata bahasa OCR).
datas += select_bundle(ROOT / "vendor" / "tesseract", dest="tesseract")

a = Analysis(
    ["timbul_fishing/__main__.py"],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=["webview.platforms.edgechromium"],
    excludes=["tkinter", "numpy", "pandas", "matplotlib", "scipy", "cv2"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="TimbulFishing", console=False, upx=False)
