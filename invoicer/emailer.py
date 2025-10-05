import os, ssl, smtplib
from email.message import EmailMessage

class EmailSender:
    def __init__(self, host: str, port: int, username: str = "", password: str = "", use_tls: bool = True, sender_email: str = "") -> None:
        self.host = host; self.port = port
        self.username = username; self.password = password
        self.use_tls = use_tls; self.sender_email = sender_email

    def send(self, to_email: str, subject: str, body: str, attachment_path: str):
        msg = EmailMessage()
        msg["From"] = self.sender_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        with open(attachment_path, "rb") as f:
            msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=os.path.basename(attachment_path))
        ctx = ssl.create_default_context()
        with smtplib.SMTP(self.host, self.port) as server:
            if self.use_tls:
                server.starttls(context=ctx)
            if self.username:
                server.login(self.username, self.password)
            server.send_message(msg)
