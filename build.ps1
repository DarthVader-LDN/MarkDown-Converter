<#
  Build MarkItDown Converter into a standalone Windows executable.

  Run from PowerShell in this folder:
      ./build.ps1
  If you hit an execution-policy error, run once:
      Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
      ./build.ps1

  Requirements: Python 3.10 - 3.13 on PATH.
#>

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "`n==== MarkItDown Converter - build ====`n" -ForegroundColor Cyan

# Locate Python (prefer the py launcher).
$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py -3" }
      elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" }
      else { $null }

if (-not $py) {
    Write-Host "[ERROR] Python not found on PATH." -ForegroundColor Red
    Write-Host "        Install Python 3.10-3.13 from https://www.python.org/downloads/"
    Write-Host "        and tick 'Add python.exe to PATH' during setup."
    exit 1
}
Write-Host ("Using " + (Invoke-Expression "$py --version"))

# Virtual environment.
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (.venv)..."
    Invoke-Expression "$py -m venv .venv"
}
& ".\.venv\Scripts\Activate.ps1"

# Dependencies.
Write-Host "Upgrading pip..."
python -m pip install --upgrade pip | Out-Null
Write-Host "Installing dependencies (downloads onnxruntime/pandas; first run is slow)..."
python -m pip install -r requirements.txt

# Build.
Write-Host "`nBuilding executable with PyInstaller..." -ForegroundColor Cyan
python -m PyInstaller --clean --noconfirm MarkItDown-GUI.spec

Write-Host "`n==== BUILD SUCCEEDED ====" -ForegroundColor Green
$exe = Join-Path $PSScriptRoot "dist\MarkItDownConverter.exe"
if (Test-Path $exe) {
    Write-Host "Your app:  $exe"
} else {
    Write-Host ("Your app folder:  " + (Join-Path $PSScriptRoot "dist\MarkItDownConverter\"))
}
Start-Process (Join-Path $PSScriptRoot "dist")
