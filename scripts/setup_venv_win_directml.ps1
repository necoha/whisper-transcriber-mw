$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot/../backend"

Write-Host "🎯 Setting up DirectML-enabled environment for AMD/Intel GPUs..." -ForegroundColor Cyan

py -3 -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -U pip

# Install common requirements
python -m pip install -r requirements-common.txt

# Install DirectML requirements
Write-Host "Installing DirectML dependencies..." -ForegroundColor Yellow
python -m pip install -r requirements-directml.txt

Write-Host "[OK] DirectML environment ready! 🚀" -ForegroundColor Green
Write-Host "DirectML supports AMD GPUs, Intel Xe Graphics, and other non-NVIDIA GPUs" -ForegroundColor Cyan