"""SparkPost email sending utilities."""

import argparse
import asyncio
import logging
from typing import Any, Dict

import httpx

from config import Config

logger = logging.getLogger(__name__)

SPARKPOST_TRANSMISSIONS_URL = "https://api.sparkpost.com/api/v1/transmissions"


async def send_sparkpost_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    metadata: Dict[str, Any] | None = None,
) -> bool:
    """Send an email via SparkPost transmissions API.

    Returns True if the API call succeeded (2xx), False otherwise.
    """
    if not Config.SPARKPOST_API_KEY:
        logger.error(
            "[sparkpost] SPARKPOST_API_KEY is not configured; cannot send email",
            extra={"to": to_email, "subject": subject},
        )
        return False

    payload: Dict[str, Any] = {
        "recipients": [{"address": {"email": to_email}}],
        "content": {
            "from": Config.SPARKPOST_SENDER,
            "subject": subject,
            "html": html_body,
            "text": text_body or "",
        },
    }

    if metadata:
        payload["metadata"] = metadata

    logger.info(
        "[sparkpost] Sending email",
        extra={
            "to": to_email,
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
                extra={"to": to_email, "subject": subject},
            )
            return True

        logger.error(
            "[sparkpost] Failed to send email",
            extra={
                "to": to_email,
                "subject": subject,
                "status_code": response.status_code,
                "response": response.text,
            },
        )
        return False
    except Exception as exc:  # pragma: no cover - network errors
        logger.exception(
            "[sparkpost] Exception while sending email",
            extra={"to": to_email, "subject": subject, "error": str(exc)},
        )
        return False


async def _main_cli(to_email: str) -> None:
    """Simple CLI entrypoint to send a test email."""
    subject = "Test email from OZL user-event-email service"
    html_body = "<h1>It works!</h1><p>This is HTML content from the OZL worker.</p>"
    text_body = "It works! This is text content from the OZL worker."

    success = await send_sparkpost_email(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )

    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Send a test SparkPost email using environment configuration."
    )
    parser.add_argument(
        "--to",
        required=True,
        help="Recipient email address",
    )
    args = parser.parse_args()

    asyncio.run(_main_cli(args.to))


