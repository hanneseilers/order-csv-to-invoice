#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m invoicer.app --csv orders.csv --out out_invoices
echo "Done. PDFs in out_invoices/"
