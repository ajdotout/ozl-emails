"""Main entry point for campaign runner worker.

Polls the email_queue table and sends emails via SparkPost API.
Handles Just-in-Time AI generation for emails with empty bodies.
Only sends during working hours (9am-5pm) in the configured timezone.

Scheduling approach:
- Emails are pre-scheduled with specific `scheduled_for` times during CSV upload
- The worker fetches emails where `scheduled_for <= NOW()` and sends immediately
- Domain spacing (e.g., 3.5 min between same-domain emails) is calculated at upload time
- No delays are applied during sending - timing is controlled by `scheduled_for`
"""

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

from config import Config
from db import (
    get_supabase_client, 
    get_queued_emails, 
    mark_processing, 
    mark_sent, 
    mark_failed,
    get_campaign,
    update_generated_body,
    pause_campaign
)
from email_sender import send_sparkpost_email
import prompts
import email_renderer

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
CIRCUIT_BREAKER_THRESHOLD = 10  # Consecutive errors to pause campaign


def is_working_hours() -> bool:
    """Check if current time is within working hours (9am-5pm) in configured timezone.

    Returns:
        True if current time is between 9am and 5pm in the configured timezone,
        or if DISABLE_WORKING_HOURS is set to True.
    """
    # If working hours restrictions are disabled, always return True
    if Config.DISABLE_WORKING_HOURS:
        return True

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
        # Fetch queued emails (filtering out paused campaigns)
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
    
    # Track errors per campaign for Circuit Breaker
    campaign_errors = defaultdict(int)
    paused_campaigns = set()
    
    for email in emails:
        email_id = email.get("id")
        campaign_id = email.get("campaign_id")
        to_email = email.get("to_email")
        from_email = email.get("from_email")
        subject = email.get("subject")
        body = email.get("body")
        metadata = email.get("metadata") or {}
        
        # Skip if campaign was just paused in this batch
        if campaign_id in paused_campaigns:
            continue
            
        # Basic validation
        if not all([email_id, campaign_id, to_email]):
            logger.warning(f"Email {email_id} missing ID/Campaign/To, skipping")
            mark_failed(supabase, email_id, "Missing core fields")
            failed_count += 1
            continue
        
        # Mark as processing (acts as lock)
        try:
            if not mark_processing(supabase, email_id):
                logger.debug(f"Email {email_id} already being processed, skipping")
                continue
        except Exception:
            continue
            
        processed_count += 1
        
        # --- Just-in-Time Generation ---
        if not body:
            try:
                logger.info(f"Generating content for email {email_id} (Campaign {campaign_id})")
                
                # 1. Fetch Campaign Sections
                campaign = get_campaign(supabase, campaign_id)
                if not campaign:
                    raise ValueError(f"Campaign {campaign_id} not found")
                
                sections = campaign.get("sections", [])
                email_format = (campaign.get("email_format") or "html").lower()
                
                # 2. Generate AI Content (Structured keys)
                generated_content = prompts.generate_content(sections, metadata)
                
                # 3. Render body according to campaign format (html default)
                # Note: campaign['subject'] is an object {mode, content}, but email_queue has 'subject' string
                # We use the pre-resolved subject from email_queue if available
                if email_format == "text":
                    final_body = email_renderer.generate_email_text(
                        sections=sections,
                        subject_line=subject,
                        recipient_data=metadata,
                        generated_content=generated_content,
                        campaign_id=campaign_id
                    )
                else:
                    final_body = email_renderer.generate_email_html(
                        sections=sections,
                        subject_line=subject,
                        recipient_data=metadata,
                        generated_content=generated_content,
                        campaign_id=campaign_id
                    )
                
                # 4. Save to DB
                if not update_generated_body(supabase, email_id, final_body):
                    raise RuntimeError("Failed to save generated body")
                
                body = final_body # Update local var for sending
                
                # Reset error count on success
                campaign_errors[campaign_id] = 0
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Generation failed for {email_id}: {error_msg}")
                
                # Increment error count
                campaign_errors[campaign_id] += 1
                
                # Check Circuit Breaker
                if campaign_errors[campaign_id] >= CIRCUIT_BREAKER_THRESHOLD:
                    logger.critical(f"PAUSING Campaign {campaign_id} due to {campaign_errors[campaign_id]} consecutive errors")
                    pause_success = pause_campaign(supabase, campaign_id, reason=f"High Failure Rate: {error_msg}")
                    if pause_success:
                        paused_campaigns.add(campaign_id)
                
                # Handle Retry (Push to End + Jitter?)
                # For now, just mark Failed. The plan mentions Jitter retry for 429s.
                # Assuming generic failure for now.
                mark_failed(supabase, email_id, f"Generation Error: {error_msg}")
                failed_count += 1
                continue
        
        # --- Sending ---
        if not body:
            # Should not happen after generation, but safety check
            mark_failed(supabase, email_id, "Body is empty after generation")
            failed_count += 1
            continue
        
        # Get campaign name for readable SparkPost campaign_id
        campaign_name = None
        if campaign_id:
            try:
                campaign = get_campaign(supabase, campaign_id)
                if campaign:
                    campaign_name = campaign.get("name")
            except Exception:
                # If we can't get campaign name, just use UUID
                pass
            
        try:
            success = await send_sparkpost_email(
                to_email=to_email,
                from_email=from_email,
                subject=subject,
                body=body,
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                metadata={"campaign_id": campaign_id, "email_id": email_id}
            )
            
            if success:
                mark_sent(supabase, email_id)
                sent_count += 1
            else:
                mark_failed(supabase, email_id, "SparkPost API Error")
                failed_count += 1
                
        except Exception as e:
            logger.error(f"Sending failed for {email_id}: {e}")
            mark_failed(supabase, email_id, f"Sending Error: {str(e)}")
            failed_count += 1
            
    logger.info(
        f"Batch complete: {processed_count} processed, {sent_count} sent, {failed_count} failed",
        extra={"paused_campaigns": list(paused_campaigns)}
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
    
    logger.info("Campaign runner worker starting...")
    
    while True:
        try:
            if is_working_hours():
                 logger.info("Polling for queued emails (working hours)...")
                 await process_email_batch()
            else:
                 # Log every 60 seconds (since POLL_INTERVAL is 60)
                 logger.info(
                    "Outside working hours (9am-5pm), sleeping...",
                    extra={"timezone": Config.TIMEZONE}
                 )
                 pass

            logger.debug(f"Sleeping for {POLL_INTERVAL_SECONDS} seconds before next poll")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.exception(f"Error in main loop: {e}")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def main():
    await main_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
