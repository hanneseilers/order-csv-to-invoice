import os, ssl, smtplib
from email.message import EmailMessage

class EmailSender:
    def __init__(self, host: str, port: int, username: str = "", password: str = "", sender_email: str = "") -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender_email = sender_email

    def send(self, messages : list = []):
        with  smtplib.SMTP_SSL(self.host, self.port, timeout=20) as server:
            server.login(self.username, self.password)

            for msg in messages:
                server.send_message(msg)
                print(f"  → sent mail to {msg["To"]}")

            server.close()

    def create_mail(self, to_email: str, subject: str, body: str, attachment_path: str):
        msg = EmailMessage()
        msg["From"] = self.sender_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        with open(attachment_path, "rb") as f:
            msg.add_attachment(f.read(), maintype="application", subtype="pdf",
                               filename=os.path.basename(attachment_path))
        return msg