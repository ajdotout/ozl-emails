"""Main entry point for campaign runner worker.

Polls the email_queue table and sends emails via SparkPost API.
Only sends during working hours (9am-5pm).
"""

import asyncio
import logging
from datetime import datetime

from config import Config
from db import get_supabase_client, get_queued_emails, mark_processing, mark_sent, mark_failed
from email_sender import send_sparkpost_email

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("campaign_runner")
logger.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))

_handler = logging.StreamHandler()
_handler.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
)

logger.addHandler(_handler)
logger.propagate = False

# Batch processing configuration
BATCH_SIZE = 20
POLL_INTERVAL_SECONDS = 60


def is_working_hours() -> bool:
    """Check if current time is within working hours (9am-5pm)."""
    current_hour = datetime.now().hour
    return 9 <= current_hour < 17


async def process_email_batch():
    """Process a batch of queued emails."""
    supabase = get_supabase_client()
    
    # Fetch queued emails
    emails = get_queued_emails(supabase, limit=BATCH_SIZE)
    
    if not emails:
        logger.debug("No queued emails found")
        return
    
    logger.info(f"Processing batch of {len(emails)} emails")
    
    for email in emails:
        email_id = email.get("id")
        to_email = email.get("to_email")
        from_email = email.get("from_email")
        subject = email.get("subject")
        body = email.get("body")
        delay_seconds = email.get("delay_seconds", 0)
        
        if not all([email_id, to_email, from_email, subject, body]):
            logger.warning(f"Email {email_id} missing required fields, skipping")
            mark_failed(supabase, email_id, "Missing required fields")
            continue
        
        # Mark as processing (acts as lock)
        if not mark_processing(supabase, email_id):
            logger.debug(f"Email {email_id} already being processed, skipping")
            continue
        
        try:
            # Apply delay
            if delay_seconds > 0:
                logger.debug(f"Waiting {delay_seconds} seconds before sending email {email_id}")
                await asyncio.sleep(delay_seconds)
            
            # Send email
            logger.info(f"Sending email {email_id} to {to_email} from {from_email}")
            success = await send_sparkpost_email(
                to_email=to_email,
                from_email=from_email,
                subject=subject,
                body=body,
            )
            
            if success:
                mark_sent(supabase, email_id)
                logger.info(f"Email {email_id} sent successfully")
            else:
                mark_failed(supabase, email_id, "SparkPost API returned error")
                logger.error(f"Failed to send email {email_id}")
                
        except Exception as e:
            error_msg = str(e)
            mark_failed(supabase, email_id, error_msg)
            logger.exception(f"Exception while processing email {email_id}: {error_msg}")


async def main_loop():
    """Main worker loop."""
    Config.validate()
    logger.info("Campaign runner worker starting...")
    
    while True:
        try:
            if is_working_hours():
                await process_email_batch()
            else:
                current_hour = datetime.now().hour
                logger.debug(f"Outside working hours (current hour: {current_hour}), skipping")
            
            # Wait before next poll
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            break
        except Exception as e:
            logger.exception(f"Error in main loop: {e}")
            # Continue running even if there's an error
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def main():
    """Async entrypoint."""
    await main_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")

