import base64
from pathlib import Path

def money(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def money_to_float(value: str) -> float:
    return ensure_float(value
                        .replace(",", ".")
                        .replace("EUR", "").
                        replace("€", "")
                        .replace("USD", "").
                        replace("$", "")
                        .strip())

def ensure_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(str(value).replace(",", ".").strip())
    except Exception:
        return float(default)

def ensure_int(value, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return int(default)
        return int(
            round(
                float(
                    str(value).replace(",", ".").strip()
                )
            )
        )
    except Exception:
        return int(default)

def image_file_to_data_uri(path: str) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    ext = p.suffix.lower()
    if ext == ".svg":
        mime = "image/svg+xml"
    elif ext == ".png":
        mime = "image/png"
    else:
        mime = "image/jpeg"
    data = p.read_bytes()
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
