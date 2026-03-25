"""Alerting utilities.

This module defines helper functions to send email and SMS alerts when
queries are escalated or other notifications are triggered.  It
integrates with Twilio SendGrid for email delivery and Twilio
Programmable Messaging for SMS.  API keys and sender details are
supplied via environment variables (see `AlertSettings` in
`config.py`).

References: The SendGrid Quickstart demonstrates how to construct and
send an email using the `Mail` helper and `SendGridAPIClient`【498156021571708†L438-L456】.
The Twilio SMS example shows how to create a `Client` with your
account SID and auth token and send a message via `client.messages.create`【161392393160508†L118-L137】.
"""
from __future__ import annotations

import os
from typing import List, Optional

# Optional imports for local testing
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

from ..config import get_settings
import httpx


class SendGridAlertService:
    def __init__(self, api_key: str, from_email: str):
        if not SENDGRID_AVAILABLE:
            raise RuntimeError("SendGrid library not available. Please install 'sendgrid'.")
        self.sg = SendGridAPIClient(api_key)
        self.from_email = Email(from_email)

    def send_email(self, to_emails: List[str], subject: str, html_content: str) -> Optional[object]:
        """Send an email via SendGrid."""
        tos = [To(addr) for addr in to_emails]
        message = Mail(
            from_email=self.from_email,
            to_emails=tos,
            subject=subject,
            html_content=html_content
        )
        try:
            response = self.sg.send(message)
            return response
        except Exception as e:
            print(f"SendGrid error: {e}")
            raise


def send_sms_alert(to_phone: str, message: str) -> None:
    """Send an SMS via Twilio.

    Args:
        to_phone: Destination phone number in E.164 format (e.g. +15558675310).
        message: Message body.

    Raises:
        Exception: Any errors from the Twilio API are propagated.
    """
    if not TWILIO_AVAILABLE:
        print(f"Twilio not available - would send SMS to {to_phone}: {message}")
        return

    settings = get_settings()
    if not settings.alert.twilio_account_sid or not settings.alert.twilio_auth_token:
        print(f"Twilio credentials not configured - would send SMS to {to_phone}: {message}")
        return

    client = TwilioClient(settings.alert.twilio_account_sid, settings.alert.twilio_auth_token)
    client.messages.create(
        from_=settings.alert.alert_phone_from,
        to=to_phone,
        body=message,
    )


async def send_alert_via_function(subject: str, body: str, emails: list[str] | None = None, phones: list[str] | None = None) -> None:
    """Dispatch an alert via a custom Azure Function.

    If `ALERT_FUNCTION_URL` is configured in the environment, this helper will
    POST a JSON payload to that URL with the subject, body, email
    recipients and phone recipients.  The function can then fan out
    notifications via SendGrid, Twilio, or any other mechanism.  If
    no function URL is configured, this call is a no-op.

    Args:
        subject: The alert subject line.
        body: The message body.
        emails: Optional list of email addresses to notify.
        phones: Optional list of phone numbers to notify.

    Raises:
        httpx.HTTPError: If the HTTP request fails.
    """
    settings = get_settings()
    url = settings.alert.alert_function_url
    if not url:
        # No function configured; silently return
        return
    payload = {
        "subject": subject,
        "body": body,
        "emails": emails or [],
        "phones": phones or [],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=10.0)
        resp.raise_for_status()