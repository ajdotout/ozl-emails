"""Background task for campaign launch."""

import logging
import random
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
from supabase import Client

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.scheduling import (
    generate_domain_config,
    get_start_time_in_timezone,
    adjust_to_working_hours,
    create_date_in_timezone,
)
from config import Config

logger = logging.getLogger(__name__)


async def process_launch_task(
    campaign_id: str,
    supabase: Client,
    request_data: Dict[str, Any]
):
    """Background task - set scheduled_for timestamps."""
    try:
        logger.info(f"Starting campaign launch for campaign {campaign_id}")
        
        # 1. Get campaign
        campaign_response = supabase.table("campaigns").select("*").eq("id", campaign_id).single().execute()
        if not campaign_response.data:
            logger.error(f"Campaign {campaign_id} not found")
            return
        
        campaign = campaign_response.data
        
        # 2. Generate domain config
        DOMAIN_CONFIG = generate_domain_config(campaign.get("sender", "jeff_richmond"))
        
        # 3. Get staged emails
        # Paginate to fetch all staged emails (Supabase has default limit of 1000)
        all_emails = request_data.get("all", True)
        email_ids = request_data.get("emailIds")
        
        BATCH_SIZE = 1000
        staged_emails = []
        offset = 0
        
        while True:
            query = supabase.table("email_queue").select("*").eq("campaign_id", campaign_id).eq("status", "staged")
            if not all_emails and email_ids:
                query = query.in_("id", email_ids)
            
            query = query.order("created_at", desc=False).range(offset, offset + BATCH_SIZE - 1)
            staged_response = query.execute()
            batch = staged_response.data or []
            
            if not batch:
                break
                
            staged_emails.extend(batch)
            
            # If we got fewer than BATCH_SIZE, we've reached the end
            if len(batch) < BATCH_SIZE:
                break
                
            offset += BATCH_SIZE
        
        if not staged_emails:
            logger.warning(f"No staged emails found for campaign {campaign_id}")
            return
        
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
        
        # Build map of last scheduled time per domain
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
        SCHEDULING_CONFIG = {
            "timezone": Config.TIMEZONE,
            "working_hour_start": Config.WORKING_HOUR_START,
            "working_hour_end": Config.WORKING_HOUR_END,
            "skip_weekends": True,
        }
        
        start_time_utc = get_start_time_in_timezone(
            Config.TIMEZONE,
            Config.WORKING_HOUR_START,
            Config.WORKING_HOUR_END,
            True
        )
        interval_ms = Config.INTERVAL_MINUTES * 60 * 1000
        
        domain_current_time: Dict[int, datetime] = {}
        round_robin_index = 0
        
        # 6. Process emails in batches
        PAGE_SIZE = 1000
        total_queued = 0
        
        for i in range(0, len(staged_emails), PAGE_SIZE):
            page_emails = staged_emails[i:i + PAGE_SIZE]
            
            for email in page_emails:
                existing_domain_index = email.get("domain_index")
                domain_index = existing_domain_index if existing_domain_index is not None else (round_robin_index % len(DOMAIN_CONFIG))
                round_robin_index += 1
                
                domain_config = DOMAIN_CONFIG[domain_index]
                jitter_ms = random.random() * Config.JITTER_SECONDS_MAX * 1000
                
                # Calculate scheduled_for
                if domain_index in domain_last_scheduled and domain_index not in domain_current_time:
                    # Has existing scheduled emails from other campaigns
                    last_scheduled = domain_last_scheduled[domain_index]
                    scheduled_for = adjust_to_working_hours(
                        last_scheduled + timedelta(milliseconds=interval_ms + jitter_ms),
                        Config.TIMEZONE,
                        Config.WORKING_HOUR_END,
                        Config.WORKING_HOUR_START,
                        True
                    )
                elif domain_index in domain_current_time:
                    # Has emails in current batch
                    scheduled_for = adjust_to_working_hours(
                        domain_current_time[domain_index] + timedelta(milliseconds=interval_ms + jitter_ms),
                        Config.TIMEZONE,
                        Config.WORKING_HOUR_END,
                        Config.WORKING_HOUR_START,
                        True
                    )
                else:
                    # First email for this domain
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
                }).eq("id", email["id"]).execute()
                
                total_queued += 1
            
            logger.info(f"Processed page {i // PAGE_SIZE + 1}: {len(page_emails)} emails")
        
        # 7. Update campaign status
        supabase.table("campaigns").update({
            "status": "scheduled",
            "updated_at": "now()",
        }).eq("id", campaign_id).execute()
        
        logger.info(f"Campaign launch completed for campaign {campaign_id}: {total_queued} emails queued")
        
    except Exception as e:
        logger.error(f"Error in launch task for campaign {campaign_id}: {e}", exc_info=True)

