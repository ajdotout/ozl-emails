"""SparkPost email sending utilities."""

import logging
from typing import Any, Dict

import httpx

from config import Config

logger = logging.getLogger(__name__)

SPARKPOST_TRANSMISSIONS_URL = "https://api.sparkpost.com/api/v1/transmissions"


async def send_sparkpost_email(
    to_email: str,
    from_email: str,
    subject: str,
    body: str,
    metadata: Dict[str, Any] | None = None,
) -> bool:
    """Send an email via SparkPost transmissions API.

    Args:
        to_email: Recipient email address
        from_email: Sender email address (e.g., "jeff@connect-ozlistings.com")
        subject: Email subject line
        body: Email body (HTML or text)
        metadata: Optional metadata to attach to the email

    Returns:
        True if the API call succeeded (2xx), False otherwise.
    """
    if not Config.SPARKPOST_API_KEY:
        logger.error(
            "[sparkpost] SPARKPOST_API_KEY is not configured; cannot send email",
            extra={"to": to_email, "subject": subject, "from": from_email},
        )
        return False

    # Determine if body is HTML or plain text
    is_html = "<" in body and ">" in body
    text_body = body if not is_html else None
    html_body = body if is_html else None

    payload: Dict[str, Any] = {
        "recipients": [{"address": {"email": to_email}}],
        "content": {
            "from": from_email,
            "subject": subject,
        },
        "options": {
            "click_tracking": False,
        },
    }

    if html_body:
        payload["content"]["html"] = html_body
    if text_body:
        payload["content"]["text"] = text_body

    if metadata:
        payload["metadata"] = metadata

    logger.info(
        "[sparkpost] Sending email",
        extra={
            "to": to_email,
            "from": from_email,
            "subject": subject,
            "metadata": metadata or {},
        },
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                SPARKPOST_TRANSMISSIONS_URL,
                json=payload,
                headers={
                    "Authorization": Config.SPARKPOST_API_KEY,
                    "Content-Type": "application/json",
                },
            )

        if response.is_success:
            logger.info(
                "[sparkpost] Email sent successfully",
                extra={"to": to_email, "from": from_email, "subject": subject},
            )
            return True

        logger.error(
            "[sparkpost] Failed to send email",
            extra={
                "to": to_email,
                "from": from_email,
                "subject": subject,
                "status_code": response.status_code,
                "response": response.text,
            },
        )
        return False
    except Exception as exc:
        logger.exception(
            "[sparkpost] Exception while sending email",
            extra={
                "to": to_email,
                "from": from_email,
                "subject": subject,
                "error": str(exc),
            },
        )
        return False

