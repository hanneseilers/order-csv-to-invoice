from dataclasses import dataclass

@dataclass
class Customer:
    name: str
    email: str = ""
    order_time: str = ""
