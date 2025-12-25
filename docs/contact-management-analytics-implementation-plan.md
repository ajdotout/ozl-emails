# Contact Management & Campaign Analytics System - Implementation Plan

## Overview

This document outlines the implementation of a comprehensive contact management and campaign analytics system for tracking replies, unsubscribes, bounces, and spam complaints. The system will integrate with SparkPost webhooks and Gmail API to provide real-time analytics and contact suppression.

## Architecture

### Components
1. **Webhook Processor**: Handles SparkPost events (bounces, unsubscribes, spam complaints)
2. **Reply Tracker**: Processes incoming emails via Gmail API to track replies
3. **Contact Manager**: Manages contact suppression and analytics queries
4. **Analytics Engine**: Provides campaign and contact-level metrics

### Data Flow
```
SparkPost Webhooks → Webhook Processor → Database Updates
Gmail API → Reply Processor → Database Updates
Frontend → API → Analytics Queries
```

## Phase 1: Database Schema Updates

### 1.1 Extend `campaign_recipients` Table

**Current Schema:**
```sql
campaign_recipients (
  id UUID PRIMARY KEY,
  campaign_id UUID → campaigns(id),
  contact_id UUID → contacts(id),
  selected_email TEXT,
  status TEXT,
  sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ
)
```

**Add Analytics Columns:**
```sql
ALTER TABLE campaign_recipients
  ADD COLUMN IF NOT EXISTS replied_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS reply_count INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS unsubscribed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS bounced_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_reply_subject TEXT;
```

### 1.2 Extend `contacts` Table for Global Suppression

**Add Suppression Columns:**
```sql
ALTER TABLE contacts
  ADD COLUMN IF NOT EXISTS globally_unsubscribed BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS globally_bounced BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS suppression_reason TEXT,
  ADD COLUMN IF NOT EXISTS suppression_date TIMESTAMPTZ;
```

### 1.3 Migration File

**Create:** `services/api/migrations/001_add_analytics_tracking.sql`

```sql
-- Add analytics tracking to campaign_recipients
ALTER TABLE campaign_recipients
  ADD COLUMN IF NOT EXISTS replied_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS reply_count INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS unsubscribed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS bounced_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_reply_subject TEXT;

-- Add global suppression to contacts
ALTER TABLE contacts
  ADD COLUMN IF NOT EXISTS globally_unsubscribed BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS globally_bounced BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS suppression_reason TEXT,
  ADD COLUMN IF NOT EXISTS suppression_date TIMESTAMPTZ;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_campaign_recipients_replied_at ON campaign_recipients(replied_at);
CREATE INDEX IF NOT EXISTS idx_campaign_recipients_unsubscribed_at ON campaign_recipients(unsubscribed_at);
CREATE INDEX IF NOT EXISTS idx_campaign_recipients_bounced_at ON campaign_recipients(bounced_at);
CREATE INDEX IF NOT EXISTS idx_contacts_globally_unsubscribed ON contacts(globally_unsubscribed);
CREATE INDEX IF NOT EXISTS idx_contacts_globally_bounced ON contacts(globally_bounced);
```

## Phase 2: SparkPost Webhook Processing (Priority 1)

### 2.1 Webhook Endpoint

**File:** `services/api/routers/webhooks.py`

```python
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import List
import logging

router = APIRouter()

class SparkPostEvent(BaseModel):
    event_type: str
    recipient: str
    metadata: dict
    timestamp: str
    fb_source: str = None  # For spam complaints
    fb_type: str = None    # For spam complaints

class WebhookPayload(BaseModel):
    events: List[SparkPostEvent]

@router.post("/sparkpost")
async def sparkpost_webhook(request: Request, payload: WebhookPayload):
    """Handle SparkPost webhooks for bounces, unsubscribes, spam complaints"""

    # Verify webhook signature (if configured)
    # verify_webhook_signature(request)

    processed = 0
    errors = 0

    for event in payload.events:
        try:
            await process_sparkpost_event(event)
            processed += 1
        except Exception as e:
            logging.error(f"Failed to process event {event.event_type}: {e}")
            errors += 1

    return {
        "status": "processed",
        "events_processed": processed,
        "errors": errors
    }

async def process_sparkpost_event(event: SparkPostEvent):
    """Process individual SparkPost events"""

    campaign_id = event.metadata.get("campaign_id")
    contact_email = event.recipient

    if not campaign_id:
        logging.warning(f"No campaign_id in event metadata: {event}")
        return

    if event.event_type == "bounce":
        await record_bounce(campaign_id, contact_email, event)
    elif event.event_type == "unsubscribe":
        await record_unsubscribe(campaign_id, contact_email, event)
    elif event.event_type == "spam_complaint":
        await record_spam_complaint(campaign_id, contact_email, event)
    else:
        logging.info(f"Ignoring event type: {event.event_type}")
```

### 2.1.1 Current Metadata Implementation

**Important Context:** The existing campaign runner **already sends metadata** with SparkPost emails:

```python
# Current implementation in campaign-runner/main.py
metadata={"campaign_id": campaign_id, "email_id": email_id}
```

This metadata is included in SparkPost transmissions and will be available in webhook events. However, for optimal analytics, we should enhance this metadata to include `contact_id` directly.

### 2.1.2 Enhanced Metadata for Analytics

**Current State:** Campaign runner sends basic metadata (`campaign_id`, `email_id`)

**Enhancement Needed:** Update the campaign runner to include contact_id for direct contact lookup:

```python
# Enhanced metadata (update in campaign-runner/main.py line ~226)
metadata={
    "campaign_id": campaign_id,
    "contact_id": contact_id,      # Add this for direct contact lookup
    "email_queue_id": email_id    # Rename for clarity
}
```

**Benefits:**
- Direct contact lookup in webhooks (no email address matching required)
- Better performance for analytics queries
- More robust event attribution

**Backward Compatibility:** Existing webhooks will continue working with email address matching until the metadata is enhanced.

### 2.2 Event Processing Functions

**File:** `services/api/shared/webhook_processor.py`

```python
from .db import get_db
import logging

async def record_bounce(campaign_id: str, contact_email: str, event: dict):
    """Record bounce event

    Current implementation: Uses campaign_id from metadata + email matching
    Future enhancement: Will use contact_id directly from enhanced metadata
    """

    async with get_db() as db:
        # Find contact via email (current approach)
        # Future: contact_id = event.metadata.get("contact_id")

        # Update campaign_recipients
        await db.execute("""
            UPDATE campaign_recipients
            SET bounced_at = NOW(), status = 'bounced'
            WHERE campaign_id = $1 AND selected_email = $2
        """, campaign_id, contact_email)

        # Globally suppress bounced contacts
        await db.execute("""
            UPDATE contacts
            SET globally_bounced = TRUE,
                suppression_reason = 'bounce',
                suppression_date = NOW()
            WHERE email = $1
        """, contact_email)

        logging.info(f"Recorded bounce for {contact_email} in campaign {campaign_id}")

async def record_unsubscribe(campaign_id: str, contact_email: str, event: dict):
    """Record unsubscribe event"""

    async with get_db() as db:
        # Update campaign_recipients
        await db.execute("""
            UPDATE campaign_recipients
            SET unsubscribed_at = NOW(), status = 'unsubscribed'
            WHERE campaign_id = $1 AND selected_email = $2
        """, campaign_id, contact_email)

        # Globally suppress unsubscribed contacts
        await db.execute("""
            UPDATE contacts
            SET globally_unsubscribed = TRUE,
                suppression_reason = 'unsubscribe',
                suppression_date = NOW()
            WHERE email = $1
        """, contact_email)

        logging.info(f"Recorded unsubscribe for {contact_email} in campaign {campaign_id}")

async def record_spam_complaint(campaign_id: str, contact_email: str, event: dict):
    """Record spam complaint event"""

    async with get_db() as db:
        # Update campaign_recipients status
        await db.execute("""
            UPDATE campaign_recipients
            SET status = 'spam_complaint'
            WHERE campaign_id = $1 AND selected_email = $2
        """, campaign_id, contact_email)

        # Globally suppress spam complainers (most important!)
        await db.execute("""
            UPDATE contacts
            SET globally_unsubscribed = TRUE,
                suppression_reason = 'spam_complaint',
                suppression_date = NOW()
            WHERE email = $1
        """, contact_email)

        logging.warning(f"Recorded spam complaint for {contact_email} in campaign {campaign_id}")
```

### 2.3 Update Campaign Runner to Include Metadata

**File:** `services/campaign-runner/email_sender.py`

**Modify the `send_email` function to include metadata:**
```python
async def send_email(email_data: dict, campaign_id: str, contact_id: str, email_queue_id: str):
    """Send email via SparkPost with tracking metadata"""

    payload = {
        "recipients": [{"address": {"email": email_data["to_email"]}}],
        "content": {
            "from": email_data["from_email"],
            "subject": email_data["subject"],
            "html": email_data.get("html_body"),
            "text": email_data.get("text_body"),
        },
        "metadata": {
            "campaign_id": campaign_id,
            "contact_id": contact_id,
            "email_queue_id": email_queue_id,
        }
    }

    # Send via SparkPost API
    response = await sparkpost_client.send(payload)

    # Store transmission_id for correlation
    transmission_id = response.get("results", {}).get("id")

    # Update email_queue with transmission_id
    await db.update_email_queue(email_queue_id, {
        "transmission_id": transmission_id,
        "status": "sent",
        "sent_at": datetime.now()
    })

    return transmission_id
```

### 2.4 Testing Webhook Processing

**Test Script:** `services/api/test_webhook.py`

```python
import asyncio
import json
from routers.webhooks import process_sparkpost_event

async def test_webhook_processing():
    """Test webhook event processing"""

    # Test bounce event
    bounce_event = {
        "event_type": "bounce",
        "recipient": "test@example.com",
        "metadata": {"campaign_id": "test-campaign-id"},
        "timestamp": "2024-01-15T10:00:00Z"
    }

    await process_sparkpost_event(bounce_event)
    print("✅ Bounce event processed")

    # Test unsubscribe event
    unsubscribe_event = {
        "event_type": "unsubscribe",
        "recipient": "test@example.com",
        "metadata": {"campaign_id": "test-campaign-id"},
        "timestamp": "2024-01-15T10:00:00Z"
    }

    await process_sparkpost_event(unsubscribe_event)
    print("✅ Unsubscribe event processed")

    # Test spam complaint event
    spam_event = {
        "event_type": "spam_complaint",
        "recipient": "test@example.com",
        "metadata": {"campaign_id": "test-campaign-id"},
        "fb_source": "gmail",
        "timestamp": "2024-01-15T10:00:00Z"
    }

    await process_sparkpost_event(spam_event)
    print("✅ Spam complaint event processed")

if __name__ == "__main__":
    asyncio.run(test_webhook_processing())
```

## Phase 3: Reply Tracking via Gmail API

### 3.1 Gmail API Integration

**File:** `services/api/shared/gmail_processor.py`

```python
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import base64
import logging

class GmailProcessor:
    def __init__(self):
        credentials = service_account.Credentials.from_service_account_file(
            os.getenv('GMAIL_SERVICE_ACCOUNT_KEY_FILE'),
            scopes=['https://www.googleapis.com/auth/gmail.readonly']
        )

        # Impersonate the communications@ozlistings.com account
        credentials = credentials.with_subject(os.getenv('GMAIL_IMPERSONATE_EMAIL'))

        self.service = build('gmail', 'v1', credentials=credentials)

    async def process_new_replies(self, since_timestamp=None):
        """Process new reply emails"""

        # Search for emails to communications@ozlistings.com
        query = 'to:communications@ozlistings.com'
        if since_timestamp:
            query += f' after:{since_timestamp}'

        results = self.service.users().messages().list(
            userId='me',
            q=query,
            maxResults=100
        ).execute()

        for message_data in results.get('messages', []):
            await self.process_reply(message_data['id'])

    async def process_reply(self, message_id: str):
        """Process individual reply"""

        # Get full message
        message = self.service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()

        # Extract headers
        headers = self.parse_headers(message['payload']['headers'])
        sender_email = headers.get('From', '').lower().strip()

        # Check if it's a reply (has In-Reply-To or References)
        in_reply_to = headers.get('In-Reply-To')
        references = headers.get('References')

        if not (in_reply_to or references or headers.get('Subject', '').startswith('Re:')):
            logging.info(f"Message {message_id} is not a reply, skipping")
            return

        # Find campaign recipient
        recipient = await self.find_campaign_recipient(sender_email, in_reply_to)

        if recipient:
            await self.record_reply(recipient, {
                'subject': headers.get('Subject', ''),
                'body': self.extract_body(message['payload']),
                'message_id': message_id,
                'received_at': message['internalDate']
            })

    def parse_headers(self, headers):
        """Parse Gmail message headers into dict"""
        return {h['name']: h['value'] for h in headers}

    def extract_body(self, payload):
        """Extract email body from Gmail message"""
        # Implementation for parsing multipart emails
        pass

    async def find_campaign_recipient(self, sender_email: str, in_reply_to: str = None):
        """Find campaign recipient by email and message threading"""
        # Implementation to find recipient
        pass

    async def record_reply(self, recipient: dict, reply_data: dict):
        """Record reply in database"""
        # Implementation to update campaign_recipients
        pass
```

### 3.2 Reply Processing Service

**File:** `services/api/tasks/reply_processor.py`

```python
import asyncio
from shared.gmail_processor import GmailProcessor
import logging

class ReplyProcessor:
    def __init__(self):
        self.gmail = GmailProcessor()

    async def run_continuous(self):
        """Run continuous reply processing"""
        while True:
            try:
                await self.gmail.process_new_replies()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logging.error(f"Reply processing error: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute

    async def process_historical(self, days_back: int = 30):
        """Process historical replies"""
        # Implementation for backfilling
        pass
```

## Phase 4: Analytics API Endpoints

### 4.1 Campaign Analytics

**File:** `services/api/routers/analytics.py`

```python
from fastapi import APIRouter
from shared.db import get_db

router = APIRouter()

@router.get("/campaigns/{campaign_id}/analytics")
async def get_campaign_analytics(campaign_id: str):
    """Get analytics for a specific campaign"""

    async with get_db() as db:
        # Get metrics
        metrics = await db.fetchrow("""
            SELECT
                COUNT(*) as total_recipients,
                COUNT(CASE WHEN replied_at IS NOT NULL THEN 1 END) as replies,
                SUM(reply_count) as total_reply_count,
                COUNT(CASE WHEN unsubscribed_at IS NOT NULL THEN 1 END) as unsubscribes,
                COUNT(CASE WHEN bounced_at IS NOT NULL THEN 1 END) as bounces,
                COUNT(CASE WHEN status = 'spam_complaint' THEN 1 END) as spam_complaints
            FROM campaign_recipients
            WHERE campaign_id = $1
        """, campaign_id)

        # Get recent replies
        recent_replies = await db.fetch("""
            SELECT
                c.name as contact_name,
                c.email,
                cr.replied_at,
                cr.reply_count,
                cr.last_reply_subject
            FROM campaign_recipients cr
            JOIN contacts c ON cr.contact_id = c.id
            WHERE cr.campaign_id = $1 AND cr.replied_at IS NOT NULL
            ORDER BY cr.replied_at DESC
            LIMIT 10
        """, campaign_id)

        return {
            "metrics": dict(metrics),
            "recent_replies": [dict(row) for row in recent_replies]
        }

@router.get("/contacts/{contact_id}/campaign-history")
async def get_contact_campaign_history(contact_id: str):
    """Get campaign interaction history for a contact"""

    async with get_db() as db:
        history = await db.fetch("""
            SELECT
                camp.name as campaign_name,
                camp.created_at as campaign_date,
                cr.replied_at,
                cr.reply_count,
                cr.unsubscribed_at,
                cr.bounced_at,
                cr.status
            FROM campaign_recipients cr
            JOIN campaigns camp ON cr.campaign_id = camp.id
            WHERE cr.contact_id = $1
            ORDER BY camp.created_at DESC
        """, contact_id)

        return [dict(row) for row in history]
```

## Phase 5: Contact Management Features

### 5.1 Contact Suppression API

**File:** `services/api/routers/contacts.py`

```python
@router.get("/contacts/available")
async def get_available_contacts(search: str = None, limit: int = 50):
    """Get contacts that are not globally suppressed"""

    async with get_db() as db:
        query = """
            SELECT id, name, email, company, role, location
            FROM contacts
            WHERE globally_unsubscribed = FALSE
            AND globally_bounced = FALSE
        """

        params = []
        if search:
            query += """ AND (
                name ILIKE $1 OR
                email ILIKE $1 OR
                company ILIKE $1 OR
                role ILIKE $1 OR
                location ILIKE $1
            )"""
            params.append(f"%{search}%")

        query += " ORDER BY name LIMIT $" + str(len(params) + 1)
        params.append(limit)

        contacts = await db.fetch(query, *params)
        return [dict(contact) for contact in contacts]

@router.post("/contacts/{contact_id}/suppress")
async def suppress_contact(contact_id: str, reason: str):
    """Manually suppress a contact"""

    async with get_db() as db:
        await db.execute("""
            UPDATE contacts
            SET globally_unsubscribed = TRUE,
                suppression_reason = $2,
                suppression_date = NOW()
            WHERE id = $1
        """, contact_id, reason)

        return {"status": "suppressed"}
```

## Phase 6: Deployment & Monitoring

### 6.1 Environment Variables

**Add to `.env`:**
```bash
# Gmail API
GMAIL_SERVICE_ACCOUNT_KEY_FILE=/path/to/service-account.json
GMAIL_IMPERSONATE_EMAIL=communications@ozlistings.com

# SparkPost
SPARKPOST_API_KEY=your-api-key
SPARKPOST_WEBHOOK_SECRET=webhook-verification-secret

# Database
DATABASE_URL=postgresql://...
```

### 6.2 Service Configuration

**Update `services/api/main.py`:**
```python
# Add webhook router
from routers.webhooks import router as webhook_router
app.include_router(webhook_router, prefix="/api/webhooks")

# Add analytics router
from routers.analytics import router as analytics_router
app.include_router(analytics_router, prefix="/api/analytics")

# Start reply processor
from tasks.reply_processor import ReplyProcessor
reply_processor = ReplyProcessor()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(reply_processor.run_continuous())
```

### 6.3 Monitoring & Alerts

**Add health checks:**
```python
@router.get("/health/webhooks")
async def webhook_health():
    """Check webhook processing health"""
    # Implementation to verify webhook processing is working
    pass

@router.get("/health/gmail")
async def gmail_health():
    """Check Gmail API connectivity"""
    # Implementation to verify Gmail API access
    pass
```

## Implementation Order & Testing

### Phase 1 Testing (Webhooks Only)
1. ✅ Deploy database migrations
2. ✅ Implement webhook endpoint
3. ✅ Test webhook processing with mock events
4. ✅ Configure SparkPost webhook URL
5. ✅ Send test campaign and verify events are processed

### Phase 2 Testing (Replies)
1. ✅ Set up Gmail API credentials
2. ✅ Implement Gmail processor
3. ✅ Test reply detection and attribution
4. ✅ Deploy reply processing service

### Phase 3 Testing (Full System)
1. ✅ End-to-end campaign flow
2. ✅ Analytics queries
3. ✅ Contact suppression
4. ✅ Frontend integration

## Success Metrics

- **Webhook Processing**: <5 second processing time, 99.9% success rate
- **Reply Attribution**: >95% accuracy using Gmail threading
- **Analytics Queries**: <500ms response time
- **Contact Suppression**: 100% effective filtering

## Rollback Plan

- Webhook failures: Disable webhook in SparkPost temporarily
- Database issues: Rollback migrations
- Gmail API issues: Fallback to IMAP if needed
- Reply processing: Can be paused without affecting sending

This implementation provides comprehensive campaign analytics while maintaining system reliability and performance.
