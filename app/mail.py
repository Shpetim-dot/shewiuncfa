"""Outbound transactional email.

Configured only through environment variables; there is no hard-coded provider and no
silent fallback that pretends a message was delivered.

    SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD, SMTP_FROM
    SMTP_STARTTLS (default 1), SMTP_SSL (default 0)

Without SMTP_HOST/SMTP_FROM nothing is sent: the call returns False and one warning is
logged **without** the message body, because bodies contain single-use tokens.
Set CFA_DEV_TOKENS=1 in development to have the API return tokens directly instead.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

log = logging.getLogger("cfa.mail")


def configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def send(to: str, subject: str, body: str) -> bool:
    """Send one plain-text mail. Returns True only when the SMTP server accepted it."""
    if not configured():
        log.warning("mail not sent (SMTP_HOST/SMTP_FROM unset): to=%s subject=%r", to, subject)
        return False
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", "")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body + "\n\n-- \nShewiun CFA")
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "465" if os.getenv("SMTP_SSL") == "1" else "587"))
    timeout = float(os.getenv("SMTP_TIMEOUT", "15"))
    try:
        if os.getenv("SMTP_SSL") == "1":
            server: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
            if os.getenv("SMTP_STARTTLS", "1") == "1":
                server.starttls(context=ssl.create_default_context())
        user, password = os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASSWORD", "")
        if user and password:
            server.login(user, password)
        server.send_message(msg)
        server.quit()
        log.info("mail sent to=%s subject=%r", to, subject)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        log.error("mail delivery failed to=%s: %s", to, exc.__class__.__name__)
        return False
