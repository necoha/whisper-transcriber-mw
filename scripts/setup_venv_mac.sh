#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-common.txt -r requirements-mac.txt
echo "[OK] mac venv ready"