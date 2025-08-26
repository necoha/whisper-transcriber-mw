$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot/../backend"
py -3 -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements-common.txt -r requirements-win.txt
Write-Host "[OK] windows venv ready"