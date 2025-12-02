"""Main entry point for user event email worker.

Uses Supabase Realtime to listen to changes on the `user_events` table and
logs when a `request_vault_access` event occurs.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from config import Config
# from email_sender import send_sparkpost_email  # Uncomment when enabling real email sends

from supabase import Client, acreate_client


# Configure logging:
# - Root logger at WARNING to quiet noisy third‑party libraries (e.g. Supabase Realtime heartbeats)
# - Dedicated application logger at Config.LOG_LEVEL that logs to stdout
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("user_event_email")
logger.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))

_handler = logging.StreamHandler()
_handler.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
)

logger.addHandler(_handler)
logger.propagate = False


async def handle_realtime_event(
    payload: Dict[str, Any],
    supabase: Client,
) -> None:
    """Handle incoming realtime events from Supabase (async callback)."""
    # Supabase realtime payload shape:
    # {
    #   "data": {
    #       "schema": "public",
    #       "table": "user_events",
    #       "type": "INSERT",
    #       "record": { ... row columns ... }
    #   },
    #   "ids": [...]
    # }
    data: Dict[str, Any] = payload.get("data") or {}
    record: Dict[str, Any] = data.get("record") or {}
    event_type = record.get("event_type")

    # Log every event for observability
    logger.info("Received user_events row: %s", json.dumps(record))

    # Only proceed with developer notification logic for the events we care about
    if event_type not in {"request_vault_access", "contact_developer"}:
        return

    event_id = record.get("id")
    if not event_id:
        logger.warning(
            "[orchestrator] user_events row missing id; cannot hydrate event",
            extra={"record": record},
        )
        return

    try:
        # Fetch enriched event including user email from the view
        event_resp = (
            await supabase.table("user_events_with_email")
            .select("*")
            .eq("id", event_id)
            .single()
            .execute()
        )
        event_row: Dict[str, Any] = event_resp.data or {}
    except Exception as exc:  # pragma: no cover - network/DB errors
        logger.exception(
            "[orchestrator] Failed to load event from user_events_with_email",
            extra={"event_id": event_id, "error": str(exc)},
        )
        return

    user_email = event_row.get("email")
    metadata = event_row.get("metadata") or {}
    endpoint = event_row.get("endpoint")

    # Derive listing slug either from metadata.propertyId or from endpoint path
    slug: Optional[str] = metadata.get("propertyId")
    if not slug and isinstance(endpoint, str):
        slug = endpoint.lstrip("/") or None

    if not slug:
        logger.warning(
            "[orchestrator] Could not determine listing slug for event",
            extra={
                "event_id": event_id,
                "event_type": event_type,
                "endpoint": endpoint,
                "metadata": metadata,
            },
        )
        return

    try:
        listing_resp = (
            await supabase.table("listings")
            .select(
                "slug, developer_contact_email, developer_ca_email, developer_entity_name, developer_ca_name"
            )
            .eq("slug", slug)
            .maybe_single()
            .execute()
        )
        listing: Optional[Dict[str, Any]] = listing_resp.data
    except Exception as exc:  # pragma: no cover - network/DB errors
        logger.exception(
            "[orchestrator] Failed to load listing for event",
            extra={"event_id": event_id, "slug": slug, "error": str(exc)},
        )
        return

    if not listing:
        logger.warning(
            "[orchestrator] No listing found for slug; skipping developer notification",
            extra={"event_id": event_id, "slug": slug},
        )
        return

    developer_contact_email = listing.get("developer_contact_email")
    developer_ca_email = listing.get("developer_ca_email")
    developer_email = developer_contact_email

    if not developer_email:
        logger.warning(
            "[orchestrator] Listing has no developer contact email; skipping notification",
            extra={"event_id": event_id, "slug": slug, "listing": listing},
        )
        return

    # For now, *only* log what we would send – do not actually send emails yet.
    logger.info(
        "[orchestrator] Would send %s notification email to developer "
        "(developer_contact_email=%s, user_email=%s)",
        event_type,
        developer_contact_email,
        user_email,
        extra={
            "event_id": event_id,
            "event_type": event_type,
            "listing_slug": slug,
            "developer_email": developer_email,
            "developer_contact_email": developer_contact_email,
            "developer_ca_email": developer_ca_email,
            "developer_entity_name": listing.get("developer_entity_name"),
            "developer_ca_name": listing.get("developer_ca_name"),
            "user_email": user_email,
            "user_id": event_row.get("user_id"),
            "endpoint": endpoint,
            "metadata": metadata,
            "created_at": event_row.get("created_at"),
        },
    )

    # Example of how to actually send the email via SparkPost once ready:
    #
    # if event_type in {"request_vault_access", "contact_developer"}:
    #     subject = f"OZL notification: {event_type.replace('_', ' ').title()}"
    #     html_body = "<p>A user has triggered an event on your listing.</p>"
    #     text_body = "A user has triggered an event on your listing."
    #
    #     # NOTE: handle_realtime_event is async and is scheduled via asyncio.create_task
    #     # in the on_postgres_change wrapper, so it is safe to await other async
    #     # operations (like send_sparkpost_email) directly here.
    #     #
    #     # await send_sparkpost_email(
    #     #     to_email=developer_email,
    #     #     subject=subject,
    #     #     html_body=html_body,
    #     #     text_body=text_body,
    #     #     metadata={
    #     #         "event_id": str(event_id),
    #     #         "event_type": event_type,
    #     #         "listing_slug": slug,
    #     #         "user_email": user_email,
    #     #     },
    #     # )


async def main() -> None:
    """Async entrypoint that sets up the Supabase realtime subscription."""
    Config.validate()

    # 1. Initialize the client asynchronously using acreate_client
    supabase: Client = await acreate_client(
        Config.SUPABASE_URL,
        Config.SUPABASE_SERVICE_ROLE_KEY,
    )

    # 2. Create a channel and subscribe to changes on the user_events table
    channel = supabase.channel("user-events-realtime")

    def on_postgres_change(payload: Dict[str, Any]) -> None:
        """Wrapper to bind Supabase client into the event handler.

        The realtime library expects a sync callback, so we schedule the async
        handler on the current event loop instead of awaiting it here.
        """
        asyncio.create_task(handle_realtime_event(payload, supabase))

    await channel.on_postgres_changes(
        event="INSERT",  # can change to "*" later if needed
        schema="public",
        table="user_events",
        callback=on_postgres_change,
    ).subscribe()

    logger.info("Listening for INSERT changes on 'user_events' table...")

    # 3. Keep the script running to maintain the WebSocket connection
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down user event email worker (KeyboardInterrupt)")
    except Exception:
        logger.exception("Fatal error in user event email worker")
        raise


