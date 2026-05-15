from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def _parse_email_list(value: str | None) -> list[str]:
    if not value:
        return []

    return [
        email.strip()
        for email in value.split(",")
        if email.strip()
    ]


def _write_console_report(
    subject: str,
    html_body: str,
    text_body: str,
    artifacts_dir: str,
    recipients: list[str],
) -> None:
    artifacts_path = Path(artifacts_dir)
    artifacts_path.mkdir(parents=True, exist_ok=True)

    html_path = artifacts_path / "latest_report.html"
    text_path = artifacts_path / "latest_report.txt"

    html_path.write_text(html_body, encoding="utf-8")
    text_path.write_text(text_body, encoding="utf-8")

    print("Email backend is console.")
    print(f"Subject: {subject}")
    print(f"Recipients: {', '.join(recipients) if recipients else 'N/A'}")
    print(f"Report written to {html_path}")


def _send_smtp_email(
    subject: str,
    html_body: str,
    text_body: str,
    recipients: list[str],
) -> None:
    sender = os.getenv("EMAIL_FROM")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    if not sender:
        raise RuntimeError("EMAIL_FROM is missing.")

    if not recipients:
        raise RuntimeError("EMAIL_TO is missing or empty.")

    if not smtp_username:
        raise RuntimeError("SMTP_USERNAME is missing.")

    if not smtp_password:
        raise RuntimeError("SMTP_PASSWORD is missing.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)

    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        if smtp_use_tls:
            server.starttls()

        server.login(smtp_username, smtp_password)
        server.send_message(message, from_addr=sender, to_addrs=recipients)

    print(f"Email sent to: {', '.join(recipients)}")


def send_email(
    subject: str,
    html_body: str,
    text_body: str,
    artifacts_dir: str,
) -> None:
    backend = os.getenv("EMAIL_BACKEND", "console").lower()
    recipients = _parse_email_list(os.getenv("EMAIL_TO"))

    if backend == "console":
        _write_console_report(
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            artifacts_dir=artifacts_dir,
            recipients=recipients,
        )
        return

    if backend == "smtp":
        _send_smtp_email(
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            recipients=recipients,
        )
        return

    raise RuntimeError(f"Unsupported EMAIL_BACKEND: {backend}")