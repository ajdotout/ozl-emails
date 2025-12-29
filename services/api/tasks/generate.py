"""Background task for email generation."""

import logging
from typing import Dict, Any
from supabase import Client
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.email import replace_variables

logger = logging.getLogger(__name__)


async def process_generate_task(campaign_id: str, supabase: Client):
    """Background task - fetch recipients and stage emails."""
    try:
        logger.info(f"Starting email generation for campaign {campaign_id}")
        
        # 1. Get campaign configuration
        campaign_response = supabase.table("campaigns").select("*").eq("id", campaign_id).single().execute()
        if not campaign_response.data:
            logger.error(f"Campaign {campaign_id} not found")
            return
        
        campaign = campaign_response.data
        
        # 2. Fetch recipients from campaign_recipients table
        # Paginate to fetch all recipients (Supabase has default limit of 1000)
        BATCH_SIZE = 1000
        all_recipients = []
        offset = 0
        
        while True:
            recipients_response = supabase.table("campaign_recipients").select("*, contacts(*)").eq("campaign_id", campaign_id).range(offset, offset + BATCH_SIZE - 1).execute()
            batch = recipients_response.data or []
            
            if not batch:
                break
                
            all_recipients.extend(batch)
            
            # If we got fewer than BATCH_SIZE, we've reached the end
            if len(batch) < BATCH_SIZE:
                break
                
            offset += BATCH_SIZE
        
        recipients = all_recipients
        
        if not recipients:
            logger.warning(f"No recipients found for campaign {campaign_id}")
            return
        
        # 3. Delete existing staged emails
        supabase.table("email_queue").delete().eq("campaign_id", campaign_id).eq("status", "staged").execute()
        
        # 4. Build email queue rows
        subject_line_content = campaign.get("subject_line", {}).get("content", "")
        queue_rows = []
        
        for recipient in recipients:
            # Handle contact data
            contact_data = recipient.get("contacts")
            if isinstance(contact_data, list) and len(contact_data) > 0:
                contact_data = contact_data[0]
            
            if not contact_data:
                continue
            
            # Get email
            target_email = recipient.get("selected_email")
            if not target_email:
                emails = (contact_data.get("email") or "").split(",")
                emails = [e.strip() for e in emails if e.strip()]
                if emails:
                    target_email = emails[0]
            
            if not target_email:
                continue
            
            # Build metadata row
            row: Dict[str, str] = {
                **(contact_data.get("details") or {}),
                "Name": contact_data.get("name") or "",
                "Email": target_email,
                "Company": contact_data.get("company") or "",
                "Role": contact_data.get("role") or "",
                "Location": contact_data.get("location") or "",
            }

            # Programmatically split name for personalization
            full_name = contact_data.get("name") or ""
            name_parts = full_name.strip().split(" ", 1) if full_name.strip() else ["", ""]
            row["FirstName"] = name_parts[0] if name_parts[0] else ""
            row["LastName"] = name_parts[1] if len(name_parts) > 1 else ""

            # Remove lowercase duplicates
            for key in ["name", "email", "company", "role", "location"]:
                row.pop(key, None)
            
            # Generate subject with variable replacement
            subject = replace_variables(subject_line_content, row)
            
            queue_rows.append({
                "campaign_id": campaign_id,
                "to_email": target_email,
                "subject": subject,
                "body": "",  # Empty body triggers JIT generation
                "status": "staged",
                "metadata": row,
                "is_edited": False,
                "from_email": None,
                "domain_index": None,
                "scheduled_for": None,
                "delay_seconds": 0,
            })
        
        # 5. Bulk insert in chunks
        CHUNK_SIZE = 100
        for i in range(0, len(queue_rows), CHUNK_SIZE):
            chunk = queue_rows[i:i + CHUNK_SIZE]
            supabase.table("email_queue").insert(chunk).execute()
            logger.info(f"Inserted chunk {i // CHUNK_SIZE + 1} ({len(chunk)} emails)")
        
        # 6. Update campaign status
        supabase.table("campaigns").update({
            "status": "staged",
            "total_recipients": len(queue_rows),
            "updated_at": "now()",
        }).eq("id", campaign_id).execute()
        
        logger.info(f"Email generation completed for campaign {campaign_id}: {len(queue_rows)} emails staged")
        
    except Exception as e:
        logger.error(f"Error in generate task for campaign {campaign_id}: {e}", exc_info=True)
        # Optionally update campaign status to indicate error
        try:
            supabase.table("campaigns").update({
                "status": "draft",
                "updated_at": "now()",
            }).eq("id", campaign_id).execute()
        except Exception:
            pass

