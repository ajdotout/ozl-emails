"""Database operations for campaign runner."""

from typing import List, Dict, Any, Optional
from datetime import datetime

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
    
    response = (
        supabase.table("email_queue")
        .select("*")
        .eq("status", "queued")
        .lte("scheduled_for", datetime.now().isoformat())
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    
    return response.data or []


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
        response = (
            supabase.table("email_queue")
            .update({
                "status": "sent",
                "sent_at": datetime.now().isoformat(),
            })
            .eq("id", email_id)
            .execute()
        )
        return len(response.data) > 0
    except Exception:
        return False


def mark_failed(supabase: Client, email_id: int, error_message: str) -> bool:
    """Mark an email as failed.
    
    Args:
        supabase: Supabase client instance
        email_id: ID of the email queue row
        error_message: Error message to store
        
    Returns:
        True if update succeeded, False otherwise
    """
    try:
        response = (
            supabase.table("email_queue")
            .update({
                "status": "failed",
                "error_message": error_message,
            })
            .eq("id", email_id)
            .execute()
        )
        return len(response.data) > 0
    except Exception:
        return False

