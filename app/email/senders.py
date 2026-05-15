from __future__ import annotations

import base64
import json
import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class EmailSendError(RuntimeError):
    pass


def send_console(subject: str, html_body: str, text_body: str, artifacts_dir: str) -> None:
    out_dir = Path(artifacts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest_report.html").write_text(html_body, encoding="utf-8")
    (out_dir / "latest_report.txt").write_text(text_body, encoding="utf-8")
    print(f"Email backend is console. Report written to {out_dir / 'latest_report.html'}")


def send_smtp(subject: str, html_body: str, text_body: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("EMAIL_FROM")
    recipient = os.getenv("EMAIL_TO")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    missing = [name for name, value in {
        "SMTP_HOST": host,
        "SMTP_USERNAME": username,
        "SMTP_PASSWORD": password,
        "EMAIL_FROM": sender,
        "EMAIL_TO": recipient,
    }.items() if not value]
    if missing:
        raise EmailSendError(f"Missing SMTP settings: {', '.join(missing)}")

    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    with smtplib.SMTP(host, port, timeout=30) as server:
        if use_tls:
            server.starttls()
        server.login(username, password)
        server.sendmail(sender, [recipient], msg.as_string())


def send_gmail_api(subject: str, html_body: str, text_body: str) -> None:
    token_json = os.getenv("GMAIL_TOKEN_JSON")
    sender = os.getenv("EMAIL_FROM")
    recipient = os.getenv("EMAIL_TO")
    if not token_json or not sender or not recipient:
        raise EmailSendError("GMAIL_TOKEN_JSON, EMAIL_FROM, and EMAIL_TO are required for Gmail API backend.")

    token_info = json.loads(token_json)
    credentials = Credentials.from_authorized_user_info(token_info, scopes=["https://www.googleapis.com/auth/gmail.send"])
    service = build("gmail", "v1", credentials=credentials)

    msg = MIMEText(html_body, "html", "utf-8")
    msg["To"] = recipient
    msg["From"] = sender
    msg["Subject"] = subject
    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    service.users().messages().send(userId="me", body={"raw": encoded}).execute()


def send_email(subject: str, html_body: str, text_body: str, artifacts_dir: str) -> None:
    backend = os.getenv("EMAIL_BACKEND", "console").lower()
    if backend == "console":
        send_console(subject, html_body, text_body, artifacts_dir)
    elif backend == "smtp":
        send_smtp(subject, html_body, text_body)
    elif backend == "gmail_api":
        send_gmail_api(subject, html_body, text_body)
    else:
        raise EmailSendError(f"Unsupported EMAIL_BACKEND: {backend}")
