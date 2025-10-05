from datetime import datetime

class InvoiceNumbering:
    def __init__(self, title : str = "", prefix: str = "RE-", date_format: str = "%d.%m.%Y", start: int = 1):
        self.titl = title
        self.prefix = prefix
        self.date_format = date_format
        self.counter = int(start)

    def next_number(self) -> str:
        s = f"{self.prefix}{datetime.now().strftime(self.date_format)}-{self.counter:03d}"
        self.counter += 1
        return s
