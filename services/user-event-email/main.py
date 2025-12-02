"""Main entry point for user event email worker.

Uses Supabase Realtime to listen to changes on the `user_events` table and
logs when a `request_vault_access` event occurs.
"""

import asyncio
import json
import logging
from typing import Any, Dict

from config import Config

from supabase import acreate_client, Client


logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def handle_realtime_event(payload: Dict[str, Any]) -> None:
    """Handle incoming realtime events from Supabase (sync callback)."""
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

    # Later logic can still special-case request_vault_access
    #if event_type == "request_vault_access":
        #logger.info("Matched request_vault_access event")
        # NOTE: For now we only log. When ready, wire this into `email_sender`.


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

    await channel.on_postgres_changes(
        event="INSERT",       # can change to "*" later if needed
        schema="public",
        table="user_events",
        callback=handle_realtime_event,
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


