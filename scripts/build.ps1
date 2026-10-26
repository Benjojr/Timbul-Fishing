# Build exe satu berkas: .\scripts\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install -q -r requirements-dev.txt

# Tampilkan berkas Tesseract yang akan dibundel, lalu uji bahwa hasil seleksinya bisa jalan.
if (-not (Test-Path vendor\tesseract\tesseract.exe)) {
    Write-Warning "vendor\tesseract\tesseract.exe tidak ada - exe tidak akan membawa Tesseract."
} else {
    & $py scripts\tesseract_bundle.py --verify
    if ($LASTEXITCODE -ne 0) { throw "Seleksi berkas Tesseract gagal; build dibatalkan." }
}

& $py -m unittest discover -s tests -t .
if ($LASTEXITCODE -ne 0) { throw "Tes gagal; build dibatalkan." }

# Sisa build lama (mode folder) dibuang agar tidak membingungkan.
if (Test-Path dist\TimbulFishing -PathType Container) { Remove-Item dist\TimbulFishing -Recurse -Force }

& $py -m PyInstaller TimbulFishing.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller gagal." }

$exe = Get-Item dist\TimbulFishing.exe
Write-Host ("Selesai: {0} ({1:N1} MB) - cukup bagikan satu berkas ini." -f $exe.FullName, ($exe.Length / 1MB))
