# Order_CSV to Invoice – HTML → PDF
Converts a csv file with product orders into pdf order lists ord pdf invoices

## Instalaltion
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

## Usage
python -m invoicer.app --csv orders.csv --out out_invoices