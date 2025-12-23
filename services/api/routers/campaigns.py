"""Campaign management routes."""

import asyncio
import logging
import sys
import os
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from middleware.auth import verify_admin
from shared.db import get_supabase_admin
from shared.scheduling import BASE_DOMAINS, create_date_in_timezone
from tasks.generate import process_generate_task
from tasks.launch import process_launch_task
from tasks.retry_failed import process_retry_failed_task
from config import Config

logger = logging.getLogger(__name__)

router = APIRouter()


class CampaignCreate(BaseModel):
    name: str
    templateSlug: Optional[str] = None
    sections: List[Dict[str, Any]] = []
    subjectLine: Dict[str, Any] = {"mode": "static", "content": ""}
    emailFormat: str = "html"
    sender: str


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    templateSlug: Optional[str] = None
    sections: Optional[List[Dict[str, Any]]] = None
    subjectLine: Optional[Dict[str, Any]] = None
    emailFormat: Optional[str] = None
    subjectPrompt: Optional[str] = None
    status: Optional[str] = None


class LaunchRequest(BaseModel):
    all: bool = True
    emailIds: Optional[List[str]] = None


class GenerateRequest(BaseModel):
    use_database_recipients: bool = True


class TestSendRequest(BaseModel):
    testEmail: str
    recipientEmailId: Optional[str] = None


class GenerateSubjectRequest(BaseModel):
    instructions: str


class PreviewGenerateRequest(BaseModel):
    sections: List[Dict[str, Any]]
    recipientData: Dict[str, Any]
    subjectLine: Optional[str] = None


class TestSendRequest(BaseModel):
    testEmail: str
    recipientEmailId: Optional[str] = None


async def check_and_update_completed_campaign(
    supabase,
    campaign_id: str
) -> bool:
    """
    Checks if a campaign is completed and updates its status if needed.
    
    A campaign is considered completed when:
    - Status is 'scheduled' or 'sending' (not already completed/paused/cancelled)
    - No emails are queued or processing
    - At least some emails were processed (sent + failed > 0)
    - No future scheduled emails remain
    
    Returns True if campaign was updated to completed, False otherwise.
    """
    try:
        # 1. Get campaign current status
        campaign_response = supabase.table("campaigns").select("status").eq("id", campaign_id).single().execute()
        
        if not campaign_response.data:
            return False  # Campaign not found
        
        campaign = campaign_response.data
        
        # 2. Only check campaigns that are 'scheduled' or 'sending'
        campaign_status = campaign.get("status", "draft")
        if campaign_status not in ["scheduled", "sending"]:
            return False  # Already completed, paused, cancelled, or not launched
        
        # 3. Count email statuses efficiently
        def count_for_status(status: str):
            response = supabase.table("email_queue").select("id", count="exact").eq("campaign_id", campaign_id).eq("status", status).execute()
            return response.count or 0
        
        queued = count_for_status("queued")
        processing = count_for_status("processing")
        sent = count_for_status("sent")
        failed = count_for_status("failed")
        
        # 4. Check if there are any future scheduled emails
        now_iso = datetime.utcnow().isoformat()
        future_response = supabase.table("email_queue").select("id").eq("campaign_id", campaign_id).in_("status", ["queued", "processing"]).gt("scheduled_for", now_iso).limit(1).execute()
        future_emails = future_response.data or []
        
        # 5. Determine if completed
        is_completed = (
            queued == 0 and
            processing == 0 and
            (sent + failed) > 0 and  # At least some emails were processed
            len(future_emails) == 0  # No future scheduled emails
        )
        
        # 6. Update status if completed
        if is_completed:
            update_response = supabase.table("campaigns").update({
                "status": "completed",
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", campaign_id).eq("status", campaign_status).execute()  # Optimistic locking
            
            # Check if update succeeded (optimistic locking prevents race conditions)
            if update_response.data:
                logger.info(f"Campaign {campaign_id} marked as completed")
                return True
            else:
                # Status changed between check and update, skip
                return False
        
        return False  # Not completed yet
    except Exception as e:
        logger.error(f"Error checking campaign {campaign_id} completion: {e}")
        return False


# GET /api/v1/campaigns
@router.get("")
async def list_campaigns(admin_user: dict = Depends(verify_admin)):
    """List all campaigns."""
    supabase = get_supabase_admin()
    
    response = supabase.table("campaigns").select("*").order("created_at", desc=True).execute()
    
    campaigns = response.data or []
    campaign_ids = [c["id"] for c in campaigns]
    
    # Check and update completed campaigns (on-demand check)
    # Only check campaigns that are 'scheduled' or 'sending'
    active_campaign_ids = [
        c["id"] for c in campaigns 
        if c.get("status") in ["scheduled", "sending"]
    ]
    
    if active_campaign_ids:
        # Check all active campaigns in parallel
        await asyncio.gather(*[
            check_and_update_completed_campaign(supabase, cid) 
            for cid in active_campaign_ids
        ])
        
        # Re-fetch campaigns to get updated statuses
        updated_response = supabase.table("campaigns").select("*").in_("id", campaign_ids).order("created_at", desc=True).execute()
        if updated_response.data:
            campaigns = updated_response.data
    
    # Get email stats for all campaigns using count queries (more efficient and avoids pagination limits)
    email_stats = {}
    if campaign_ids:
        # Use count queries instead of fetching all rows to avoid pagination limits
        for campaign_id in campaign_ids:
            sent_response = supabase.table("email_queue").select("id", count="exact").eq("campaign_id", campaign_id).eq("status", "sent").execute()
            failed_response = supabase.table("email_queue").select("id", count="exact").eq("campaign_id", campaign_id).eq("status", "failed").execute()
            email_stats[campaign_id] = {
                "sent": sent_response.count or 0,
                "failed": failed_response.count or 0
            }
    
    # Format response
    result = []
    for campaign in campaigns:
        stats = email_stats.get(campaign["id"], {"sent": 0, "failed": 0})
        result.append({
            "id": campaign["id"],
            "name": campaign["name"],
            "templateSlug": campaign.get("template_slug"),
            "sections": campaign.get("sections", []),
            "subjectLine": campaign.get("subject_line", {}),
            "emailFormat": campaign.get("email_format", "html"),
            "status": campaign.get("status", "draft"),
            "totalRecipients": campaign.get("total_recipients", 0),
            "sender": campaign.get("sender"),
            "sent": stats["sent"],
            "failed": stats["failed"],
            "createdAt": campaign.get("created_at"),
            "updatedAt": campaign.get("updated_at"),
        })
    
    return result


# POST /api/v1/campaigns
@router.post("")
async def create_campaign(campaign: CampaignCreate, admin_user: dict = Depends(verify_admin)):
    """Create a new campaign."""
    MAX_CAMPAIGN_NAME_LENGTH = 25
    if len(campaign.name) > MAX_CAMPAIGN_NAME_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Campaign name must be {MAX_CAMPAIGN_NAME_LENGTH} characters or less"
        )
    
    if campaign.sender not in ["todd_vitzthum", "jeff_richmond"]:
        raise HTTPException(status_code=400, detail="Valid sender is required")
    
    supabase = get_supabase_admin()
    response = supabase.table("campaigns").insert({
        "name": campaign.name,
        "template_slug": campaign.templateSlug,
        "sections": campaign.sections,
        "subject_line": campaign.subjectLine,
        "email_format": campaign.emailFormat,
        "status": "draft",
        "sender": campaign.sender,
    }).execute()
    
    if not response.data or len(response.data) == 0:
        raise HTTPException(status_code=500, detail="Failed to create campaign")
    
    data = response.data[0]
    return {
        "id": data["id"],
        "name": data["name"],
        "templateSlug": data.get("template_slug"),
        "sections": data.get("sections", []),
        "subjectLine": data.get("subject_line", {}),
        "emailFormat": data.get("email_format", "html"),
        "status": data.get("status", "draft"),
        "totalRecipients": data.get("total_recipients", 0),
        "sender": data.get("sender"),
        "createdAt": data.get("created_at"),
        "updatedAt": data.get("updated_at"),
    }


# GET /api/v1/campaigns/status
# IMPORTANT: This route must come BEFORE /{campaign_id} to avoid route conflicts
@router.get("/status")
async def get_global_status(admin_user: dict = Depends(verify_admin)):
    """Get global campaign status with 7-day schedule."""
    supabase = get_supabase_admin()
    
    # Count campaigns by status
    campaigns_response = supabase.table("campaigns").select("status").execute()
    campaigns = campaigns_response.data or []
    
    status_counts = {}
    for campaign in campaigns:
        status = campaign.get("status", "draft")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Count emails by status using count queries (more efficient and avoids pagination limits)
    def count_emails_by_status(status: str):
        response = supabase.table("email_queue").select("id", count="exact").eq("status", status).execute()
        return response.count or 0
    
    email_status_counts = {
        "staged": count_emails_by_status("staged"),
        "queued": count_emails_by_status("queued"),
        "processing": count_emails_by_status("processing"),
        "sent": count_emails_by_status("sent"),
        "failed": count_emails_by_status("failed"),
    }
    
    # Build 7-day schedule
    week_schedule = await _build_week_schedule(supabase)
    
    return {
        "campaigns": status_counts,
        "emails": email_status_counts,
        "weekSchedule": week_schedule,
    }


async def _build_week_schedule(supabase) -> List[Dict[str, Any]]:
    """Build the 7-day schedule showing queued emails per day."""
    # Configuration
    TIMEZONE = Config.TIMEZONE
    WORKING_HOUR_START = Config.WORKING_HOUR_START
    WORKING_HOUR_END = Config.WORKING_HOUR_END
    WORKING_HOURS = WORKING_HOUR_END - WORKING_HOUR_START
    INTERVAL_MINUTES = Config.INTERVAL_MINUTES
    DOMAIN_COUNT = len(BASE_DOMAINS)
    
    # Calculate capacity
    emails_per_domain_per_hour = 60 / INTERVAL_MINUTES
    MAX_DAILY_CAPACITY = int(WORKING_HOURS * emails_per_domain_per_hour * DOMAIN_COUNT)
    
    # Get current time in configured timezone
    now_utc = datetime.now(ZoneInfo("UTC"))
    tz = ZoneInfo(TIMEZONE)
    now_zoned = now_utc.astimezone(tz)
    
    year = now_zoned.year
    month = now_zoned.month
    day = now_zoned.day
    hour = now_zoned.hour
    
    # Day names
    day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    
    week_schedule = []
    DAYS_TO_SHOW = 7
    
    for day_offset in range(DAYS_TO_SHOW):
        # Calculate the date for this day
        day_date = datetime(year, month, day, tzinfo=tz) + timedelta(days=day_offset)
        
        # Create day boundaries in timezone, then convert to UTC for queries
        day_start = create_date_in_timezone(
            TIMEZONE,
            day_date.year,
            day_date.month,
            day_date.day,
            0, 0, 0
        )
        day_end = create_date_in_timezone(
            TIMEZONE,
            day_date.year,
            day_date.month,
            day_date.day,
            23, 59, 59
        )
        
        # Count emails queued for this day
        queued_response = supabase.table("email_queue").select("id", count="exact").eq("status", "queued").gte("scheduled_for", day_start.isoformat()).lt("scheduled_for", day_end.isoformat()).execute()
        queued_count = queued_response.count or 0
        
        # Count emails sent on this day (only for today)
        sent_count = 0
        if day_offset == 0:
            sent_response = supabase.table("email_queue").select("id", count="exact").eq("status", "sent").gte("sent_at", day_start.isoformat()).lt("sent_at", day_end.isoformat()).execute()
            sent_count = sent_response.count or 0
        
        # Calculate capacity for this day
        day_capacity = MAX_DAILY_CAPACITY
        remaining_hours = None
        
        if day_offset == 0:
            # Today - calculate based on current hour
            if hour < WORKING_HOUR_START:
                day_capacity = MAX_DAILY_CAPACITY
                remaining_hours = WORKING_HOURS
            elif hour >= WORKING_HOUR_END:
                day_capacity = 0
                remaining_hours = 0
            else:
                remaining_hours = WORKING_HOUR_END - hour
                day_capacity = int(remaining_hours * emails_per_domain_per_hour * DOMAIN_COUNT)
        
        # Format date for display
        date_str = f"{day_date.year}-{str(day_date.month).zfill(2)}-{str(day_date.day).zfill(2)}"
        day_of_week = day_names[day_date.weekday()]
        
        # Create day label
        if day_offset == 0:
            day_label = "Today"
        elif day_offset == 1:
            day_label = "Tomorrow"
        else:
            day_label = f"{day_of_week} {day_date.day}"
        
        used_capacity = (sent_count + queued_count) if day_offset == 0 else queued_count
        
        week_schedule.append({
            "date": date_str,
            "dayLabel": day_label,
            "dayOfWeek": day_of_week,
            "queued": queued_count,
            "sent": sent_count,
            "capacity": day_capacity,
            "remaining": max(0, day_capacity - used_capacity),
            "remainingHours": remaining_hours,
            "isToday": day_offset == 0,
        })
    
    return week_schedule


# GET /api/v1/campaigns/domains
# IMPORTANT: This route must come BEFORE /{campaign_id} to avoid route conflicts
@router.get("/domains")
async def get_domains(admin_user: dict = Depends(verify_admin)):
    """Get domain configuration."""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from shared.scheduling import BASE_DOMAINS
    
    return {
        "domains": BASE_DOMAINS,
        "count": len(BASE_DOMAINS),
    }


# GET /api/v1/campaigns/{campaign_id}
@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str, admin_user: dict = Depends(verify_admin)):
    """Get a single campaign."""
    supabase = get_supabase_admin()
    
    # Check and update campaign completion status (on-demand check)
    await check_and_update_completed_campaign(supabase, campaign_id)
    
    response = supabase.table("campaigns").select("*").eq("id", campaign_id).single().execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    data = response.data
    return {
        "id": data["id"],
        "name": data["name"],
        "templateSlug": data.get("template_slug"),
        "sections": data.get("sections", []),
        "subjectLine": data.get("subject_line", {}),
        "emailFormat": data.get("email_format", "html"),
        "status": data.get("status", "draft"),
        "totalRecipients": data.get("total_recipients", 0),
        "subjectPrompt": data.get("subject_prompt"),
        "createdAt": data.get("created_at"),
        "updatedAt": data.get("updated_at"),
    }


# PUT /api/v1/campaigns/{campaign_id}
@router.put("/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    campaign: CampaignUpdate,
    admin_user: dict = Depends(verify_admin)
):
    """Update a campaign."""
    MAX_CAMPAIGN_NAME_LENGTH = 25
    if campaign.name and len(campaign.name) > MAX_CAMPAIGN_NAME_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Campaign name must be {MAX_CAMPAIGN_NAME_LENGTH} characters or less"
        )
    
    supabase = get_supabase_admin()
    
    # If status is being changed to 'draft', delete all staged emails
    if campaign.status == "draft":
        supabase.table("email_queue").delete().eq("campaign_id", campaign_id).eq("status", "staged").execute()
    
    updates = {"updated_at": datetime.utcnow().isoformat()}
    if campaign.name is not None:
        updates["name"] = campaign.name
    if campaign.templateSlug is not None:
        updates["template_slug"] = campaign.templateSlug
    if campaign.sections is not None:
        updates["sections"] = campaign.sections
    if campaign.subjectLine is not None:
        updates["subject_line"] = campaign.subjectLine
    if campaign.emailFormat is not None:
        updates["email_format"] = campaign.emailFormat
    if campaign.subjectPrompt is not None:
        updates["subject_prompt"] = campaign.subjectPrompt
    if campaign.status is not None:
        updates["status"] = campaign.status
        if campaign.status == "draft":
            updates["total_recipients"] = 0
    
    response = supabase.table("campaigns").update(updates).eq("id", campaign_id).execute()
    
    if not response.data or len(response.data) == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    data = response.data[0]
    return {
        "id": data["id"],
        "name": data["name"],
        "templateSlug": data.get("template_slug"),
        "sections": data.get("sections", []),
        "subjectLine": data.get("subject_line", {}),
        "emailFormat": data.get("email_format", "html"),
        "status": data.get("status", "draft"),
        "totalRecipients": data.get("total_recipients", 0),
        "createdAt": data.get("created_at"),
        "updatedAt": data.get("updated_at"),
    }


# DELETE /api/v1/campaigns/{campaign_id}
@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: str, admin_user: dict = Depends(verify_admin)):
    """Delete a campaign."""
    supabase = get_supabase_admin()
    
    # Delete associated emails first
    supabase.table("email_queue").delete().eq("campaign_id", campaign_id).execute()
    
    # Delete campaign
    response = supabase.table("campaigns").delete().eq("id", campaign_id).execute()
    
    return {"success": True}


# POST /api/v1/campaigns/preview/generate
# IMPORTANT: This route must come BEFORE /{campaign_id}/generate to avoid route conflicts
@router.post("/preview/generate")
async def preview_generate(
    request: PreviewGenerateRequest,
    admin_user: dict = Depends(verify_admin)
):
    """Generate preview content for email sections."""
    from shared.prompts import generate_content
    
    # Validation
    if not request.sections or not isinstance(request.sections, list):
        raise HTTPException(status_code=400, detail="Invalid sections data")
    
    if not request.recipientData or not isinstance(request.recipientData, dict):
        raise HTTPException(status_code=400, detail="Invalid recipient data")
    
    # Filter personalized sections
    personalized_sections = [
        s for s in request.sections
        if s.get('mode') == 'personalized'
    ]
    
    if not personalized_sections:
        raise HTTPException(status_code=400, detail="No personalized sections to generate")
    
    try:
        # Generate content using shared function
        generated_content = generate_content(request.sections, request.recipientData)
        
        return {"generatedContent": generated_content}
    except Exception as e:
        logger.error(f"Preview generation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate preview: {str(e)}"
        )


# POST /api/v1/campaigns/{campaign_id}/generate
@router.post("/{campaign_id}/generate")
async def generate_emails(
    campaign_id: str,
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    admin_user: dict = Depends(verify_admin)
):
    """Start email generation - returns immediately."""
    supabase = get_supabase_admin()
    
    # Verify campaign exists
    campaign_response = supabase.table("campaigns").select("*").eq("id", campaign_id).single().execute()
    if not campaign_response.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign = campaign_response.data
    if campaign["status"] not in ["draft", "staged"]:
        raise HTTPException(
            status_code=400,
            detail="Campaign must be draft or staged"
        )
    
    # Start background task
    background_tasks.add_task(process_generate_task, campaign_id, supabase)
    
    return {
        "status": "started",
        "message": "Email generation started. Click refresh to check progress."
    }


# POST /api/v1/campaigns/{campaign_id}/launch
@router.post("/{campaign_id}/launch")
async def launch_campaign(
    campaign_id: str,
    request: LaunchRequest,
    background_tasks: BackgroundTasks,
    admin_user: dict = Depends(verify_admin)
):
    """Start campaign launch - returns immediately."""
    supabase = get_supabase_admin()
    
    # Verify campaign
    campaign_response = supabase.table("campaigns").select("*").eq("id", campaign_id).single().execute()
    if not campaign_response.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign = campaign_response.data
    if campaign["status"] not in ["staged", "draft"]:
        raise HTTPException(
            status_code=400,
            detail="Campaign must be in staged or draft status to launch"
        )
    
    # Start background task
    background_tasks.add_task(process_launch_task, campaign_id, supabase, request.dict())
    
    return {
        "status": "started",
        "message": "Campaign launch started. Click refresh to check progress."
    }


# POST /api/v1/campaigns/{campaign_id}/retry-failed
@router.post("/{campaign_id}/retry-failed")
async def retry_failed(
    campaign_id: str,
    background_tasks: BackgroundTasks,
    admin_user: dict = Depends(verify_admin)
):
    """Retry failed emails - returns immediately."""
    supabase = get_supabase_admin()
    
    # Verify campaign
    campaign_response = supabase.table("campaigns").select("*").eq("id", campaign_id).single().execute()
    if not campaign_response.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Start background task
    background_tasks.add_task(process_retry_failed_task, campaign_id, supabase)
    
    return {
        "status": "started",
        "message": "Retry started. Click refresh to check progress."
    }


# GET /api/v1/campaigns/{campaign_id}/status
@router.get("/{campaign_id}/status")
async def get_campaign_status(campaign_id: str, admin_user: dict = Depends(verify_admin)):
    """Get campaign status including generation/launch progress."""
    supabase = get_supabase_admin()
    
    # Get campaign
    campaign_response = supabase.table("campaigns").select("*").eq("id", campaign_id).single().execute()
    if not campaign_response.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign = campaign_response.data
    
    # Count staged emails (scheduled_for IS NULL)
    staged_response = supabase.table("email_queue").select("id", count="exact").eq("campaign_id", campaign_id).is_("scheduled_for", "null").execute()
    staged_count = staged_response.count or 0
    
    # Count queued emails (scheduled_for IS NOT NULL)
    queued_response = supabase.table("email_queue").select("id", count="exact").eq("campaign_id", campaign_id).not_.is_("scheduled_for", "null").execute()
    queued_count = queued_response.count or 0
    
    # Total recipients
    total_recipients = campaign.get("total_recipients", 0)
    
    # Determine status
    campaign_status = campaign.get("status", "draft")
    is_generating = campaign_status == "draft" and staged_count == 0 and total_recipients == 0
    # is_launching is true when launch is in progress (emails being queued but campaign still in staged status)
    is_launching = campaign_status == "staged" and queued_count > 0
    is_ready = campaign_status == "staged" and staged_count > 0
    is_launched = campaign_status == "scheduled" and queued_count > 0
    
    return {
        "campaign_status": campaign_status,
        "staged_count": staged_count,
        "queued_count": queued_count,
        "total_recipients": total_recipients,
        "is_generating": is_generating,
        "is_launching": is_launching,
        "is_ready": is_ready,
        "is_launched": is_launched,
    }


# GET /api/v1/campaigns/{campaign_id}/summary
@router.get("/{campaign_id}/summary")
async def get_campaign_summary(campaign_id: str, admin_user: dict = Depends(verify_admin)):
    """Get campaign summary with stats."""
    supabase = get_supabase_admin()
    
    # Check and update campaign completion status (on-demand check)
    await check_and_update_completed_campaign(supabase, campaign_id)
    
    # Get campaign
    campaign_response = supabase.table("campaigns").select("*").eq("id", campaign_id).single().execute()
    if not campaign_response.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign = campaign_response.data
    
    # Count emails by status
    def count_for_status(status: str):
        response = supabase.table("email_queue").select("id", count="exact").eq("campaign_id", campaign_id).eq("status", status).execute()
        return response.count or 0
    
    sent = count_for_status("sent")
    failed = count_for_status("failed")
    queued = count_for_status("queued")
    processing = count_for_status("processing")
    staged = count_for_status("staged")
    
    # Get last sent
    last_sent_response = supabase.table("email_queue").select("sent_at").eq("campaign_id", campaign_id).eq("status", "sent").order("sent_at", desc=True).limit(1).single().execute()
    last_sent_at = last_sent_response.data.get("sent_at") if last_sent_response.data else None
    
    # Get next scheduled
    next_scheduled_response = supabase.table("email_queue").select("scheduled_for").eq("campaign_id", campaign_id).eq("status", "queued").order("scheduled_for", desc=False).limit(1).single().execute()
    next_scheduled_for = next_scheduled_response.data.get("scheduled_for") if next_scheduled_response.data else None
    
    # SparkPost metrics (simplified - can be enhanced)
    sparkpost_metrics = {
        "deliveryRate": None,
        "bounceRate": None,
        "countDelivered": None,
        "countBounced": None,
    }
    
    if Config.SPARKPOST_API_KEY and sent > 0:
        try:
            # Construct SparkPost campaign_id
            campaign_name = campaign.get("name", "")
            sanitized_name = campaign_name[:25] if len(campaign_name) <= 25 else campaign_name[:25]
            sparkpost_campaign_id = f"{sanitized_name} - {campaign_id}"
            
            # Fetch metrics (simplified - full implementation would use proper date ranges)
            # This is a placeholder - full implementation would call SparkPost Metrics API
            pass
        except Exception:
            pass
    
    return {
        "success": True,
        "counts": {
            "sent": sent,
            "failed": failed,
            "queued": queued,
            "processing": processing,
            "staged": staged,
            "total": sent + failed + queued + processing + staged,
        },
        "lastSentAt": last_sent_at,
        "nextScheduledFor": next_scheduled_for,
        "sparkpostMetrics": sparkpost_metrics,
    }


# POST /api/v1/campaigns/{campaign_id}/test-send
@router.post("/{campaign_id}/test-send")
async def test_send(
    campaign_id: str,
    request: TestSendRequest,
    admin_user: dict = Depends(verify_admin)
):
    """Send a test email."""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from shared.email_renderer import generate_email_html, generate_email_text
    from shared.prompts import generate_content
    from shared.email_sender import send_sparkpost_email
    from shared.scheduling import generate_domain_config
    from shared.email import replace_variables
    
    supabase = get_supabase_admin()
    
    # Get campaign
    campaign_response = supabase.table("campaigns").select("*").eq("id", campaign_id).single().execute()
    if not campaign_response.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign = campaign_response.data
    
    # Get recipient data if recipientEmailId is provided
    recipient_data = {}
    if request.recipientEmailId:
        email_response = supabase.table("email_queue").select("*").eq("id", request.recipientEmailId).eq("campaign_id", campaign_id).single().execute()
        if email_response.data:
            recipient_data = email_response.data.get("metadata", {})
    
    # Generate content if needed
    sections = campaign.get("sections", [])
    personalized_sections = [s for s in sections if s.get("mode") == "personalized"]
    generated_content = {}
    
    if personalized_sections and recipient_data:
        try:
            generated_content = generate_content(sections, recipient_data)
        except Exception as e:
            logger.warning(f"Failed to generate content for test send: {e}")
    
    # Generate email body
    subject_line = campaign.get("subject_line", {}).get("content", "")
    email_format = campaign.get("email_format", "html")
    
    if email_format == "text":
        body = generate_email_text(sections, subject_line, recipient_data, generated_content)
    else:
        body = generate_email_html(sections, subject_line, recipient_data, generated_content)
    
    # Get domain config
    DOMAIN_CONFIG = generate_domain_config(campaign.get("sender", "jeff_richmond"))
    domain_config = DOMAIN_CONFIG[0]
    from_email = f"{domain_config['display_name']} <{domain_config['sender_local']}@{domain_config['domain']}>"
    
    # Replace variables in subject
    subject = replace_variables(subject_line, recipient_data)
    
    # Send email
    success = await send_sparkpost_email(
        to_email=request.testEmail,
        from_email=from_email,
        subject=subject,
        body=body,
        campaign_id=campaign_id,
        campaign_name=campaign.get("name"),
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send test email")
    
    return {"success": True, "message": "Test email sent successfully"}


# POST /api/v1/campaigns/{campaign_id}/generate-subject
@router.post("/{campaign_id}/generate-subject")
async def generate_subject(
    campaign_id: str,
    request: GenerateSubjectRequest,
    admin_user: dict = Depends(verify_admin)
):
    """Generate a subject line using AI."""
    import sys
    import os
    import json
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from groq import Groq
    from config import Config
    
    if not request.instructions or not request.instructions.strip():
        raise HTTPException(status_code=400, detail="Instructions are required")
    
    supabase = get_supabase_admin()
    
    # Get campaign
    campaign_response = supabase.table("campaigns").select("name, sections").eq("id", campaign_id).single().execute()
    if not campaign_response.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign = campaign_response.data
    
    # Extract email content from sections
    sections = campaign.get("sections", [])
    email_content_parts = []
    for section in sections:
        if section.get("type") == "text":
            if section.get("mode") == "personalized":
                email_content_parts.append(f"[Personalized content about {section.get('name', 'section')}]")
            else:
                email_content_parts.append(section.get("content", ""))
    
    email_content = " ".join(email_content_parts)[:500]
    
    # Build prompt
    prompt = f"""{request.instructions}

---

CAMPAIGN CONTEXT:
- Name: "{campaign.get('name', '')}"

EMAIL CONTENT CONTEXT:
{email_content}
"""
    
    # Generate using Groq
    groq_client = Groq(api_key=Config.GROQ_API_KEY)
    
    SubjectResponseSchema = {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "The generated subject line",
            },
        },
        "required": ["subject"],
        "additionalProperties": False,
    }
    
    response = groq_client.chat.completions.create(
        model="moonshotai/kimi-k2-instruct-0905",
        messages=[{"role": "user", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "subject_generation_response",
                "schema": SubjectResponseSchema,
            }
        },
    )
    
    response_content = response.choices[0].message.content
    if not response_content:
        raise HTTPException(status_code=500, detail="Empty response from AI")
    
    import json
    response_data = json.loads(response_content)
    
    if not response_data.get("subject"):
        raise HTTPException(status_code=500, detail="Invalid response structure from AI")
    
    # Persist the prompt (best-effort)
    try:
        supabase.table("campaigns").update({
            "subject_prompt": request.instructions,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", campaign_id).execute()
    except Exception:
        pass
    
    return {"subject": response_data["subject"]}

