# PyInstaller: satu-satunya spec. Build lewat scripts/build.ps1.
from pathlib import Path

ROOT = Path(SPECPATH)
tesseract = ROOT / "vendor" / "tesseract"

datas = [(str(ROOT / "timbul_fishing" / "web" / "static"), "timbul_fishing/web/static")]
if tesseract.exists():
    datas.append((str(tesseract), "tesseract"))   # Tesseract portabel ikut dibundel

a = Analysis(
    ["timbul_fishing/__main__.py"],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=["webview.platforms.edgechromium"],
    excludes=["tkinter", "numpy", "pandas", "matplotlib", "scipy", "cv2"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="TimbulFishing", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="TimbulFishing")
