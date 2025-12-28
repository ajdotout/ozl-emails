"""Recipient management routes."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from middleware.auth import verify_admin
from shared.db import get_supabase_admin

router = APIRouter()


class RecipientAdd(BaseModel):
    contact_ids: List[str]
    selected_emails: Optional[dict] = None  # Map of contact_id -> email


# GET /api/v1/campaigns/{campaign_id}/recipients
@router.get("/{campaign_id}/recipients")
async def list_recipients(
    campaign_id: str,
    admin_user: dict = Depends(verify_admin)
):
    """List recipients for a campaign."""
    supabase = get_supabase_admin()
    response = supabase.table("campaign_recipients").select("*, contacts(*)").eq("campaign_id", campaign_id).execute()
    
    return response.data or []


# POST /api/v1/campaigns/{campaign_id}/recipients
@router.post("/{campaign_id}/recipients")
async def add_recipients(
    campaign_id: str,
    request: RecipientAdd,
    admin_user: dict = Depends(verify_admin)
):
    """Add recipients to a campaign."""
    supabase = get_supabase_admin()
    
    # Verify campaign exists
    campaign_response = supabase.table("campaigns").select("id").eq("id", campaign_id).single().execute()
    if not campaign_response.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Prepare recipient rows
    recipients = []
    selected_emails = request.selected_emails or {}

    for contact_id in request.contact_ids:
        recipients.append({
            "campaign_id": campaign_id,
            "contact_id": contact_id,
            "selected_email": selected_emails.get(contact_id),
        })

    # Replace existing recipients for this campaign
    supabase.table("campaign_recipients").delete().eq("campaign_id", campaign_id).execute()

    # Insert new recipients
    supabase.table("campaign_recipients").insert(recipients).execute()

    # Update campaign total_recipients count
    supabase.table("campaigns").update({
        "total_recipients": len(recipients)
    }).eq("id", campaign_id).execute()

    return {"success": True, "count": len(recipients)}

