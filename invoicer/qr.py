import io, base64
import qrcode

class QRService:
    @staticmethod
    def make_qr_data_uri(payload: str, box_size: int = 6, border: int = 2) -> str:
        qr = qrcode.QRCode(box_size=box_size, border=border)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image()
        out = io.BytesIO()
        img.save(out, format="PNG")
        return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")

    @staticmethod
    def epc_sepa_qr_payload(iban: str, bic: str, name: str, amount: float, remittance: str, currency: str = "EUR") -> str:
        amt = f"{currency}{amount:.2f}"
        rem = (remittance or "")[:140]
        return "\n".join([
            "BCD","001","1","SCT",
            (bic or "").strip(),
            (name or "").strip(),
            (iban or "").replace(" ", "").strip(),
            amt,"",rem,""
        ])
