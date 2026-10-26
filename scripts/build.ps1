# Build exe: .\scripts\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -q -r requirements-dev.txt

if (-not (Test-Path vendor\tesseract\tesseract.exe)) {
    Write-Warning "vendor\tesseract\tesseract.exe tidak ada - exe tidak akan membawa Tesseract."
}

& .\.venv\Scripts\python.exe -m unittest discover -s tests -t .
if ($LASTEXITCODE -ne 0) { throw "Tes gagal; build dibatalkan." }

& .\.venv\Scripts\python.exe -m PyInstaller TimbulFishing.spec --noconfirm --clean
Write-Host "Selesai: dist\TimbulFishing\TimbulFishing.exe (bagikan seluruh folder)"
