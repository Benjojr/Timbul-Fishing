param([switch]$SkipBuild)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $SkipBuild) {
    if (-not (Test-Path "vendor\tesseract\tesseract.exe")) {
        throw "vendor\tesseract\tesseract.exe tidak ditemukan."
    }
    pyinstaller --noconfirm --clean --onedir --noconsole --name BuktiTF `
      --add-data "bukti_tf/web/static;bukti_tf/web/static" `
      --add-data "vendor/tesseract;vendor/tesseract" `
      main.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller gagal." }
}
if (-not (Test-Path "dist\BuktiTF\BuktiTF.exe")) { throw "dist\BuktiTF\BuktiTF.exe belum ada. Jalankan tanpa -SkipBuild." }

$wv = "installer\MicrosoftEdgeWebview2Setup.exe"
if (-not (Test-Path $wv)) {
    Invoke-WebRequest -Uri "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile $wv
}

# Cari ISCC.exe: PATH dulu, lalu folder bawaan Inno Setup 7 / 6 (semua pengguna maupun per pengguna).
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, "$env:LOCALAPPDATA\Programs") | Where-Object { $_ }
    $iscc = foreach ($root in $roots) {
        foreach ($ver in "Inno Setup 7", "Inno Setup 6") {
            $p = Join-Path $root "$ver\ISCC.exe"
            if (Test-Path $p) { $p }
        }
    } | Select-Object -First 1
}
if (-not $iscc) { throw "ISCC.exe tidak ditemukan. Pasang Inno Setup dari jrsoftware.org/isinfo.php." }
Write-Host "Memakai $iscc"

& $iscc "installer\BuktiTF.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup gagal." }
Write-Host "Selesai. Installer ada di installer\Output\"