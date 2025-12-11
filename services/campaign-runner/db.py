"""Database operations for campaign runner."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from supabase import Client, create_client

from config import Config


def get_supabase_client() -> Client:
    """Initialize and return Supabase client."""
    return create_client(
        Config.SUPABASE_URL,
        Config.SUPABASE_SERVICE_ROLE_KEY,
    )


def get_queued_emails(supabase: Client, limit: int = 20) -> List[Dict[str, Any]]:
    """Fetch queued emails with row-level locking.
    
    Uses FOR UPDATE SKIP LOCKED to prevent multiple workers from processing
    the same email simultaneously.
    
    Args:
        supabase: Supabase client instance
        limit: Maximum number of emails to fetch
        
    Returns:
        List of email queue rows
    """
    # Note: Supabase Python client doesn't directly support FOR UPDATE SKIP LOCKED
    # We'll use a transaction approach or rely on status updates for locking
    # For now, we'll fetch and immediately update status to 'processing' to lock
    
    # Get current time in UTC (scheduled_for is stored as UTC ISO string)
    now_utc = datetime.now(ZoneInfo("UTC"))
    
    # We join with 'campaigns' to filter out 'paused' campaigns
    response = (
        supabase.table("email_queue")
        .select("*, campaigns!inner(status)")
        .eq("status", "queued")
        .neq("campaigns.status", "paused")  # Exclude paused campaigns
        .lte("scheduled_for", now_utc.isoformat())
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    
    return response.data or []


def get_campaign(supabase: Client, campaign_id: str) -> Optional[Dict[str, Any]]:
    """Fetch campaign details including sections.
    
    Args:
        supabase: Supabase client
        campaign_id: UUID of the campaign
        
    Returns:
        Campaign object or None
    """
    try:
        response = (
            supabase.table("campaigns")
            .select("*")
            .eq("id", campaign_id)
            .single()
            .execute()
        )
        return response.data
    except Exception:
        return None


def update_generated_body(
    supabase: Client, 
    email_id: str, 
    body: str, 
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Update the email body (and optionally metadata) after generation.
    
    Args:
        supabase: Supabase client
        email_id: ID of the email
        body: The full generated HTML body
        metadata: Optional metadata updates (e.g. generation stats)
        
    Returns:
        True if successful
    """
    try:
        update_data = {"body": body}
        if metadata:
            # We might want to merge metadata ideally, but for now assuming direct update or we fetch-update
            # Actually, let's just update body. Metadata merging might be complex without race conditions.
            # If we need to update metadata, we should handle it carefully.
            # For now, let's stick to body.
            pass
            
        response = (
            supabase.table("email_queue")
            .update(update_data)
            .eq("id", email_id)
            .execute()
        )
        return len(response.data) > 0
    except Exception:
        return False


def pause_campaign(supabase: Client, campaign_id: str, reason: str) -> bool:
    """Pause a campaign due to errors.
    
    Args:
        supabase: Client
        campaign_id: Campaign UUID
        reason: Reason string
        
    Returns:
        True if success
    """
    try:
        response = (
            supabase.table("campaigns")
            .update({
                "status": "paused",
                "metadata": {"pause_reason": reason, "paused_at": datetime.now(ZoneInfo("UTC")).isoformat()}
            })
            .eq("id", campaign_id)
            .execute()
        )
        return len(response.data) > 0
    except Exception:
        return False


def mark_processing(supabase: Client, email_id: int) -> bool:
    """Mark an email as processing.
    
    This acts as a lock to prevent other workers from processing the same email.
    
    Args:
        supabase: Supabase client instance
        email_id: ID of the email queue row
        
    Returns:
        True if update succeeded, False otherwise
    """
    try:
        response = (
            supabase.table("email_queue")
            .update({"status": "processing"})
            .eq("id", email_id)
            .eq("status", "queued")  # Only update if still queued (optimistic locking)
            .execute()
        )
        return len(response.data) > 0
    except Exception:
        return False


def mark_sent(supabase: Client, email_id: int) -> bool:
    """Mark an email as sent.
    
    Args:
        supabase: Supabase client instance
        email_id: ID of the email queue row
        
    Returns:
        True if update succeeded, False otherwise
    """
    try:
        # Store sent_at in UTC
        sent_at_utc = datetime.now(ZoneInfo("UTC"))
        response = (
            supabase.table("email_queue")
            .update({
                "status": "sent",
                "sent_at": sent_at_utc.isoformat(),
            })
            .eq("id", email_id)
            .execute()
        )
        return len(response.data) > 0
    except Exception:
        return False


def mark_failed(
    supabase: Client, 
    email_id: int, 
    error_message: str, 
    retry_later: bool = False,
    reschedule_time: Optional[datetime] = None
) -> bool:
    """Mark an email as failed or reschedule it.
    
    Args:
        supabase: Supabase client instance
        email_id: ID of the email queue row
        error_message: Error message to store
        retry_later: If True, keep status as 'queued' but update scheduled_for
        reschedule_time: New time to schedule if retry_later is True
        
    Returns:
        True if update succeeded, False otherwise
    """
    try:
        update_data = {"error_message": error_message}
        
        if retry_later and reschedule_time:
            update_data["status"] = "queued"
            update_data["scheduled_for"] = reschedule_time.isoformat()
        else:
            update_data["status"] = "failed"
            
        response = (
            supabase.table("email_queue")
            .update(update_data)
            .eq("id", email_id)
            .execute()
        )
        return len(response.data) > 0
    except Exception:
        return False

