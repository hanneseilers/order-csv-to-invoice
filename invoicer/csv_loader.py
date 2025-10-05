import csv
from typing import Dict, List

class CSVLoader:
    def __init__(self, csv_path: str, reference_tag : str ="name", exclude_columns : list = None):
        self.csv_path = csv_path
        self.reference_tag = reference_tag
        self.exclude_columns = exclude_columns or []

    def parse_orders(self) -> Dict[str, List[dict]]:
        orders = {}
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                order_id = row.get(self.reference_tag, "UNKNOWN")
                filtered_row = {
                    k: v.strip() if isinstance(v, str) else v
                    for k, v in row.items()
                    if k not in self.exclude_columns and v not in (None, "", " ")
                }
                orders[order_id] = filtered_row
        return orders
