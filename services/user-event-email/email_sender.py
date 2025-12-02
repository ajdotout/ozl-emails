"""Scaffold for sending SparkPost emails.

For now, this only logs the intended send; integrate the real SparkPost API later.
"""

import logging
from typing import Any, Dict

import httpx

from config import Config

logger = logging.getLogger(__name__)


async def send_sparkpost_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    metadata: Dict[str, Any] | None = None,
) -> bool:
    """Send an email via SparkPost (currently just logs).

    Returns True if the call would have succeeded.
    """
    # For now, just log the payload instead of actually calling SparkPost
    logger.info(
        "[sparkpost] Would send email",
        extra={
            "to": to_email,
            "subject": subject,
            "metadata": metadata or {},
        },
    )

    # Example of how a real SparkPost call might look (disabled for now)
    if False and Config.SPARKPOST_API_KEY:  # pragma: no cover - placeholder
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.sparkpost.com/api/v1/transmissions",
                headers={
                    "Authorization": Config.SPARKPOST_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "options": {"sandbox": False},
                    "content": {
                        "from": Config.SPARKPOST_SENDER,
                        "subject": subject,
                        "html": html_body,
                        "text": text_body or "",
                    },
                    "recipients": [{"address": {"email": to_email}}],
                    "metadata": metadata or {},
                },
            )
            response.raise_for_status()

    return True


