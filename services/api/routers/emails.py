"""Email management routes."""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from middleware.auth import verify_admin
from shared.db import get_supabase_admin

router = APIRouter()


def transform_email_to_camelcase(email: Dict[str, Any]) -> Dict[str, Any]:
    """Transform email from snake_case database fields to camelCase frontend format."""
    return {
        "id": str(email.get("id", "")),
        "campaignId": email.get("campaign_id"),
        "toEmail": email.get("to_email"),
        "fromEmail": email.get("from_email"),
        "subject": email.get("subject"),
        "body": email.get("body"),
        "status": email.get("status"),
        "scheduledFor": email.get("scheduled_for"),
        "domainIndex": email.get("domain_index"),
        "isEdited": email.get("is_edited", False),
        "metadata": email.get("metadata", {}),
        "createdAt": email.get("created_at"),
        "errorMessage": email.get("error_message"),
        "sentAt": email.get("sent_at"),
    }


# GET /api/v1/campaigns/{campaign_id}/emails
@router.get("/{campaign_id}/emails")
async def list_emails(
    campaign_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    admin_user: dict = Depends(verify_admin)
):
    """List emails for a campaign."""
    supabase = get_supabase_admin()
    
    query = supabase.table("email_queue").select("*").eq("campaign_id", campaign_id)
    if status:
        query = query.eq("status", status)
    
    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    response = query.execute()
    
    emails = response.data or []
    
    # Transform snake_case to camelCase to match frontend expectations
    return [transform_email_to_camelcase(email) for email in emails]


# GET /api/v1/campaigns/{campaign_id}/emails/{email_id}
@router.get("/{campaign_id}/emails/{email_id}")
async def get_email(
    campaign_id: str,
    email_id: str,
    admin_user: dict = Depends(verify_admin)
):
    """Get a single email."""
    supabase = get_supabase_admin()
    response = supabase.table("email_queue").select("*").eq("id", email_id).eq("campaign_id", campaign_id).single().execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Email not found")
    
    return transform_email_to_camelcase(response.data)


# PUT /api/v1/campaigns/{campaign_id}/emails/{email_id}
@router.put("/{campaign_id}/emails/{email_id}")
async def update_email(
    campaign_id: str,
    email_id: str,
    updates: Dict[str, Any],
    admin_user: dict = Depends(verify_admin)
):
    """Update an email."""
    supabase = get_supabase_admin()
    
    # Transform camelCase updates to snake_case for database
    db_updates = {}
    field_mapping = {
        "toEmail": "to_email",
        "fromEmail": "from_email",
        "scheduledFor": "scheduled_for",
        "domainIndex": "domain_index",
        "isEdited": "is_edited",
        "errorMessage": "error_message",
        "sentAt": "sent_at",
        "campaignId": "campaign_id",
    }
    
    for key, value in updates.items():
        db_key = field_mapping.get(key, key)
        db_updates[db_key] = value
    
    response = supabase.table("email_queue").update(db_updates).eq("id", email_id).eq("campaign_id", campaign_id).execute()
    
    if not response.data or len(response.data) == 0:
        raise HTTPException(status_code=404, detail="Email not found")
    
    return transform_email_to_camelcase(response.data[0])


# DELETE /api/v1/campaigns/{campaign_id}/emails/{email_id}
@router.delete("/{campaign_id}/emails/{email_id}")
async def delete_email(
    campaign_id: str,
    email_id: str,
    admin_user: dict = Depends(verify_admin)
):
    """Delete an email."""
    supabase = get_supabase_admin()
    supabase.table("email_queue").delete().eq("id", email_id).eq("campaign_id", campaign_id).execute()
    
    return {"success": True}

