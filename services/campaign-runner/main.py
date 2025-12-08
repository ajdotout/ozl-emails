"""Main entry point for campaign runner worker.

Polls the email_queue table and sends emails via SparkPost API.
Only sends during working hours (9am-5pm) in the configured timezone.

Scheduling approach:
- Emails are pre-scheduled with specific `scheduled_for` times during CSV upload
- The worker fetches emails where `scheduled_for <= NOW()` and sends immediately
- Domain spacing (e.g., 3.5 min between same-domain emails) is calculated at upload time
- No delays are applied during sending - timing is controlled by `scheduled_for`
"""

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

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
    """Check if current time is within working hours (9am-5pm) in configured timezone.
    
    Returns:
        True if current time is between 9am and 5pm in the configured timezone.
    """
    try:
        tz = ZoneInfo(Config.TIMEZONE)
    except Exception as e:
        logger.warning(f"Invalid timezone '{Config.TIMEZONE}', falling back to UTC: {e}")
        tz = ZoneInfo("UTC")
    
    # Get current time in the configured timezone
    current_time = datetime.now(tz)
    current_hour = current_time.hour
    return 9 <= current_hour < 17


async def process_email_batch():
    """Process a batch of queued emails."""
    try:
        supabase = get_supabase_client()
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return
    
    try:
        # Fetch queued emails
        emails = get_queued_emails(supabase, limit=BATCH_SIZE)
    except Exception as e:
        logger.error(f"Failed to fetch queued emails: {e}", exc_info=True)
        return
    
    if not emails:
        logger.debug("No queued emails found")
        return
    
    logger.info(f"Processing batch of {len(emails)} emails")
    
    processed_count = 0
    sent_count = 0
    failed_count = 0
    
    for email in emails:
        email_id = email.get("id")
        to_email = email.get("to_email")
        from_email = email.get("from_email")
        subject = email.get("subject")
        body = email.get("body")
        
        if not all([email_id, to_email, from_email, subject, body]):
            logger.warning(
                f"Email {email_id} missing required fields, skipping",
                extra={
                    "email_id": email_id,
                    "has_to_email": bool(to_email),
                    "has_from_email": bool(from_email),
                    "has_subject": bool(subject),
                    "has_body": bool(body),
                }
            )
            try:
                mark_failed(supabase, email_id, "Missing required fields")
            except Exception as e:
                logger.error(f"Failed to mark email {email_id} as failed: {e}")
            failed_count += 1
            continue
        
        # Mark as processing (acts as lock)
        try:
            if not mark_processing(supabase, email_id):
                logger.debug(f"Email {email_id} already being processed, skipping")
                continue
        except Exception as e:
            logger.error(f"Failed to mark email {email_id} as processing: {e}")
            continue
        
        processed_count += 1
        
        try:
            # Note: delay_seconds is no longer used - timing is controlled by scheduled_for
            # The worker only fetches emails where scheduled_for <= NOW()
            
            # Send email
            logger.info(
                f"Sending email {email_id} to {to_email}",
                extra={
                    "email_id": email_id,
                    "to_email": to_email,
                    "from_email": from_email,
                    "subject": subject[:50] if subject else None,  # Truncate for logging
                }
            )
            success = await send_sparkpost_email(
                to_email=to_email,
                from_email=from_email,
                subject=subject,
                body=body,
            )
            
            if success:
                try:
                    mark_sent(supabase, email_id)
                    logger.info(
                        f"Email {email_id} sent successfully",
                        extra={"email_id": email_id, "to_email": to_email}
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(
                        f"Email sent but failed to update status in DB for {email_id}: {e}",
                        extra={"email_id": email_id}
                    )
            else:
                try:
                    mark_failed(supabase, email_id, "SparkPost API returned error")
                    logger.error(
                        f"Failed to send email {email_id}",
                        extra={"email_id": email_id, "to_email": to_email}
                    )
                    failed_count += 1
                except Exception as e:
                    logger.error(f"Failed to mark email {email_id} as failed: {e}")
                
        except Exception as e:
            error_msg = str(e)
            try:
                mark_failed(supabase, email_id, error_msg)
            except Exception as db_error:
                logger.error(f"Failed to mark email {email_id} as failed in DB: {db_error}")
            
            logger.exception(
                f"Exception while processing email {email_id}",
                extra={
                    "email_id": email_id,
                    "to_email": to_email,
                    "error": error_msg,
                }
            )
            failed_count += 1
    
    logger.info(
        f"Batch processing complete: {processed_count} processed, {sent_count} sent, {failed_count} failed",
        extra={
            "processed": processed_count,
            "sent": sent_count,
            "failed": failed_count,
            "total": len(emails),
        }
    )


async def main_loop():
    """Main worker loop."""
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise
    
    # Validate timezone configuration
    try:
        ZoneInfo(Config.TIMEZONE)
        logger.info(f"Using timezone: {Config.TIMEZONE}")
    except Exception as e:
        logger.warning(f"Invalid timezone '{Config.TIMEZONE}', will fall back to UTC: {e}")
    
    logger.info(
        "Campaign runner worker starting...",
        extra={
            "batch_size": BATCH_SIZE,
            "poll_interval": POLL_INTERVAL_SECONDS,
            "working_hours": "9am-5pm",
            "timezone": Config.TIMEZONE,
        }
    )
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while True:
        try:
            if is_working_hours():
                await process_email_batch()
                consecutive_errors = 0  # Reset error counter on success
            else:
                current_hour = datetime.now().hour
                logger.debug(
                    f"Outside working hours (current hour: {current_hour}), skipping",
                    extra={"current_hour": current_hour}
                )
            
            # Wait before next poll
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down gracefully...")
            break
        except Exception as e:
            consecutive_errors += 1
            logger.exception(
                f"Error in main loop (consecutive errors: {consecutive_errors}): {e}",
                extra={"consecutive_errors": consecutive_errors}
            )
            
            # If too many consecutive errors, wait longer before retrying
            if consecutive_errors >= max_consecutive_errors:
                logger.error(
                    f"Too many consecutive errors ({consecutive_errors}), "
                    f"waiting {POLL_INTERVAL_SECONDS * 5} seconds before retry"
                )
                await asyncio.sleep(POLL_INTERVAL_SECONDS * 5)
                consecutive_errors = 0  # Reset after long wait
            else:
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

