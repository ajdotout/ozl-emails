"""Background task for retrying failed emails."""

import logging
import random
import sys
import os
from datetime import datetime, timedelta
from typing import Dict
from supabase import Client

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.scheduling import (
    generate_domain_config,
    get_start_time_in_timezone,
    adjust_to_working_hours,
)
from config import Config

logger = logging.getLogger(__name__)


async def process_retry_failed_task(campaign_id: str, supabase: Client):
    """Background task - retry failed emails."""
    try:
        logger.info(f"Starting retry failed emails for campaign {campaign_id}")
        
        # 1. Get campaign
        campaign_response = supabase.table("campaigns").select("*").eq("id", campaign_id).single().execute()
        if not campaign_response.data:
            logger.error(f"Campaign {campaign_id} not found")
            return
        
        campaign = campaign_response.data
        
        # 2. Get failed emails
        # Paginate to fetch all failed emails (Supabase has default limit of 1000)
        BATCH_SIZE = 1000
        failed_emails = []
        offset = 0
        
        while True:
            failed_response = supabase.table("email_queue").select("*").eq("campaign_id", campaign_id).eq("status", "failed").order("created_at", desc=False).range(offset, offset + BATCH_SIZE - 1).execute()
            batch = failed_response.data or []
            
            if not batch:
                break
                
            failed_emails.extend(batch)
            
            # If we got fewer than BATCH_SIZE, we've reached the end
            if len(batch) < BATCH_SIZE:
                break
                
            offset += BATCH_SIZE
        
        if not failed_emails:
            logger.info(f"No failed emails found for campaign {campaign_id}")
            return
        
        # 3. Generate domain config
        DOMAIN_CONFIG = generate_domain_config(campaign.get("sender", "jeff_richmond"))
        
        # 4. Get existing scheduled emails for domain coordination
        # Paginate to fetch all existing scheduled emails (Supabase has default limit of 1000)
        # We need the most recent scheduled email per domain, so we fetch all and build the map
        existing_schedules = []
        offset = 0
        
        while True:
            existing_response = supabase.table("email_queue").select("domain_index, scheduled_for").in_("status", ["queued", "processing"]).not_.is_("scheduled_for", "null").order("scheduled_for", desc=True).range(offset, offset + BATCH_SIZE - 1).execute()
            batch = existing_response.data or []
            
            if not batch:
                break
                
            existing_schedules.extend(batch)
            
            # If we got fewer than BATCH_SIZE, we've reached the end
            if len(batch) < BATCH_SIZE:
                break
                
            offset += BATCH_SIZE
        
        domain_last_scheduled: Dict[int, datetime] = {}
        for row in existing_schedules:
            domain_index = row.get("domain_index")
            if domain_index is not None:
                scheduled_for_str = row.get("scheduled_for")
                if scheduled_for_str:
                    scheduled_for = datetime.fromisoformat(scheduled_for_str.replace("Z", "+00:00"))
                    if domain_index not in domain_last_scheduled:
                        domain_last_scheduled[domain_index] = scheduled_for
        
        # 5. Calculate scheduling
        start_time_utc = get_start_time_in_timezone(
            Config.TIMEZONE,
            Config.WORKING_HOUR_START,
            Config.WORKING_HOUR_END,
            True
        )
        interval_ms = Config.INTERVAL_MINUTES * 60 * 1000
        
        domain_current_time: Dict[int, datetime] = {}
        round_robin_index = 0
        total_retried = 0
        
        # 6. Reschedule failed emails
        for email in failed_emails:
            existing_domain_index = email.get("domain_index")
            domain_index = existing_domain_index if existing_domain_index is not None else (round_robin_index % len(DOMAIN_CONFIG))
            round_robin_index += 1
            
            domain_config = DOMAIN_CONFIG[domain_index]
            jitter_ms = random.random() * Config.JITTER_SECONDS_MAX * 1000
            
            # Calculate scheduled_for
            if domain_index in domain_last_scheduled and domain_index not in domain_current_time:
                last_scheduled = domain_last_scheduled[domain_index]
                scheduled_for = adjust_to_working_hours(
                    last_scheduled + timedelta(milliseconds=interval_ms + jitter_ms),
                    Config.TIMEZONE,
                    Config.WORKING_HOUR_END,
                    Config.WORKING_HOUR_START,
                    True
                )
            elif domain_index in domain_current_time:
                scheduled_for = adjust_to_working_hours(
                    domain_current_time[domain_index] + timedelta(milliseconds=interval_ms + jitter_ms),
                    Config.TIMEZONE,
                    Config.WORKING_HOUR_END,
                    Config.WORKING_HOUR_START,
                    True
                )
            else:
                scheduled_for = adjust_to_working_hours(
                    start_time_utc + timedelta(milliseconds=jitter_ms),
                    Config.TIMEZONE,
                    Config.WORKING_HOUR_END,
                    Config.WORKING_HOUR_START,
                    True
                )
            
            domain_current_time[domain_index] = scheduled_for
            domain_last_scheduled[domain_index] = scheduled_for
            
            # Update email
            supabase.table("email_queue").update({
                "status": "queued",
                "domain_index": domain_index,
                "from_email": f"{domain_config['display_name']} <{domain_config['sender_local']}@{domain_config['domain']}>",
                "scheduled_for": scheduled_for.isoformat(),
                "error_message": None,
            }).eq("id", email["id"]).execute()
            
            total_retried += 1
        
        logger.info(f"Retry completed for campaign {campaign_id}: {total_retried} emails rescheduled")
        
    except Exception as e:
        logger.error(f"Error in retry task for campaign {campaign_id}: {e}", exc_info=True)

