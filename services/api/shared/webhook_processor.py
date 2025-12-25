from .db import get_supabase_admin
import logging

async def record_delivered(campaign_id: str, contact_email: str, event: dict):
    """Record delivered event - just log the payload for analytics"""

    logging.info(f"Email delivered successfully: campaign={campaign_id}, recipient={contact_email}, payload={event}")

async def record_bounce(campaign_id: str, contact_email: str, event: dict):
    """Record bounce event

    Current implementation: Uses campaign_id from metadata + email matching
    Future enhancement: Will use contact_id directly from enhanced metadata
    """

    supabase = get_supabase_admin()

    # Update campaign_recipients
    supabase.table('campaign_recipients').update({
        'bounced_at': 'now()',
        'status': 'bounced'
    }).eq('campaign_id', campaign_id).eq('selected_email', contact_email).execute()

    # Globally suppress bounced contacts
    supabase.table('contacts').update({
        'globally_bounced': True,
        'suppression_reason': 'bounce',
        'suppression_date': 'now()'
    }).eq('email', contact_email).execute()

    logging.info(f"Recorded bounce for {contact_email} in campaign {campaign_id}")

async def record_unsubscribe(campaign_id: str, contact_email: str, event: dict):
    """Record unsubscribe event"""

    supabase = get_supabase_admin()

    # Update campaign_recipients
    supabase.table('campaign_recipients').update({
        'unsubscribed_at': 'now()',
        'status': 'unsubscribed'
    }).eq('campaign_id', campaign_id).eq('selected_email', contact_email).execute()

    # Globally suppress unsubscribed contacts
    supabase.table('contacts').update({
        'globally_unsubscribed': True,
        'suppression_reason': 'unsubscribe',
        'suppression_date': 'now()'
    }).eq('email', contact_email).execute()

    logging.info(f"Recorded unsubscribe for {contact_email} in campaign {campaign_id}")

async def record_spam_complaint(campaign_id: str, contact_email: str, event: dict):
    """Record spam complaint event"""

    supabase = get_supabase_admin()

    # Update campaign_recipients status
    supabase.table('campaign_recipients').update({
        'status': 'spam_complaint'
    }).eq('campaign_id', campaign_id).eq('selected_email', contact_email).execute()

    # Globally suppress spam complainers (most important!)
    supabase.table('contacts').update({
        'globally_unsubscribed': True,
        'suppression_reason': 'spam_complaint',
        'suppression_date': 'now()'
    }).eq('email', contact_email).execute()

    logging.warning(f"Recorded spam complaint for {contact_email} in campaign {campaign_id}")
