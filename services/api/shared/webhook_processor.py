from .db import get_supabase_admin
import logging


def get_contact_id_by_email(supabase, contact_email: str) -> str | None:
    """Get contact_id by email address.

    Returns the contact_id if found, None if not found or on error.
    """
    try:
        contact_result = supabase.table('contacts').select('id').eq('email', contact_email).single().execute()
        if not contact_result.data:
            logging.error(f"No contact found for email {contact_email}")
            return None
        return contact_result.data['id']
    except Exception as e:
        logging.error(f"Failed to lookup contact for email {contact_email}: {e}")
        return None

async def record_delivered(campaign_id: str, contact_email: str, event: dict):
    """Record delivered event - just log the payload for analytics"""

    logging.info(f"Email delivered successfully: campaign={campaign_id}, recipient={contact_email}, payload={event}")

async def record_bounce(campaign_id: str, contact_email: str, event: dict):
    """Record bounce event

    Current implementation: Uses campaign_id from metadata + email matching
    Future enhancement: Will use contact_id directly from enhanced metadata
    """

    supabase = get_supabase_admin()

    # Get contact_id by email
    contact_id = get_contact_id_by_email(supabase, contact_email)
    if not contact_id:
        return

    # Update campaign_recipients using contact_id
    try:
        result = supabase.table('campaign_recipients').update({
            'bounced_at': 'now()',
            'status': 'bounced'
        }).eq('campaign_id', campaign_id).eq('contact_id', contact_id).execute()

        logging.info(f"Campaign recipients update result: {result}")
        if hasattr(result, 'data') and not result.data:
            logging.warning(f"No campaign_recipients rows updated for campaign_id={campaign_id}, contact_id={contact_id}")

    except Exception as e:
        logging.error(f"Failed to update campaign_recipients: {e}")

    # Globally suppress bounced contacts
    try:
        supabase.table('contacts').update({
            'globally_bounced': True,
            'suppression_reason': 'bounce',
            'suppression_date': 'now()'
        }).eq('email', contact_email).execute()
    except Exception as e:
        logging.error(f"Failed to update contacts: {e}")

    logging.info(f"Recorded bounce for {contact_email} in campaign {campaign_id}")

async def record_unsubscribe(campaign_id: str, contact_email: str, event: dict):
    """Record unsubscribe event"""

    supabase = get_supabase_admin()

    # Get contact_id by email
    contact_id = get_contact_id_by_email(supabase, contact_email)
    if not contact_id:
        return

    # Update campaign_recipients using contact_id
    try:
        supabase.table('campaign_recipients').update({
            'unsubscribed_at': 'now()',
            'status': 'unsubscribed'
        }).eq('campaign_id', campaign_id).eq('contact_id', contact_id).execute()
    except Exception as e:
        logging.error(f"Failed to update campaign_recipients: {e}")

    # Globally suppress unsubscribed contacts
    try:
        supabase.table('contacts').update({
            'globally_unsubscribed': True,
            'suppression_reason': 'unsubscribe',
            'suppression_date': 'now()'
        }).eq('email', contact_email).execute()
    except Exception as e:
        logging.error(f"Failed to update contacts: {e}")

    logging.info(f"Recorded unsubscribe for {contact_email} in campaign {campaign_id}")

async def record_spam_complaint(campaign_id: str, contact_email: str, event: dict):
    """Record spam complaint event"""

    supabase = get_supabase_admin()

    # Get contact_id by email
    contact_id = get_contact_id_by_email(supabase, contact_email)
    if not contact_id:
        return

    # Update campaign_recipients status using contact_id
    try:
        supabase.table('campaign_recipients').update({
            'status': 'spam_complaint'
        }).eq('campaign_id', campaign_id).eq('contact_id', contact_id).execute()
    except Exception as e:
        logging.error(f"Failed to update campaign_recipients: {e}")

    # Globally suppress spam complainers (most important!)
    try:
        supabase.table('contacts').update({
            'globally_unsubscribed': True,
            'suppression_reason': 'spam_complaint',
            'suppression_date': 'now()'
        }).eq('email', contact_email).execute()
    except Exception as e:
        logging.error(f"Failed to update contacts: {e}")

    logging.warning(f"Recorded spam complaint for {contact_email} in campaign {campaign_id}")
