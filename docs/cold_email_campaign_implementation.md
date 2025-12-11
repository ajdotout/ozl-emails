# Cold Email Campaign System - Implementation Plan

## Overview

This document outlines the implementation plan for porting the N8N cold email workflow (`Cold Email System 4.3.json`) into a code-based system that can run on a GCP VM. The goal is to send **900 emails in 2 days** using SparkPost API with domain rotation and staggered timing.

## Key Decisions

### Email Provider
- **SparkPost API** (not SMTP)
- All 7 sending domains are already configured in SparkPost
- Domains:
  1. `connect-ozlistings.com`
  2. `engage-ozlistings.com`
  3. `get-ozlistings.com`
  4. `join-ozlistings.com`
  5. `outreach-ozlistings.com`
  6. `ozlistings-reach.com`
  7. `reach-ozlistings.com`

### Execution Pattern
- **Continuous Drip During Working Hours** (9am-5pm)
- Worker runs continuously, polling queue every 60 seconds
- Only sends emails during 9am-5pm (better open rates)
- Processes 10-20 emails per poll cycle
- Random delays: 15-100 seconds between emails

### Scope (What We're Building)
- ✅ Single email send (not sequences)
- ✅ CSV import via frontend
- ✅ Domain rotation across 7 domains
- ✅ Staggered timing with random delays
- ✅ Working hours only (9am-5pm)
- ❌ Ramp-up logic (not needed)
- ❌ Reply checking (not needed)
- ❌ Weekend logic (not needed)
- ❌ Multi-email sequences (future)

## Architecture

### Components

1. **Database (Supabase)**
   - Simple `email_queue` table
   - Stores email details, domain assignment, delays, status

2. **Frontend (Next.js API Route)**
   - CSV upload endpoint
   - Parses CSV, distributes across domains
   - Bulk inserts into queue with pre-calculated delays

3. **Python Worker (GCP VM)**
   - Polls queue every 60 seconds
   - Processes batches of 10-20 emails
   - Sends via SparkPost API with domain rotation
   - Only sends during working hours (9am-5pm)

## Database Schema

```sql
CREATE TABLE email_queue (
  id SERIAL PRIMARY KEY,
  to_email TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,  -- HTML or text email body
  from_email TEXT NOT NULL,  -- e.g., "jeff@connect-ozlistings.com"
  domain_index INTEGER NOT NULL,  -- 0-6 for 7 domains
  delay_seconds INTEGER NOT NULL,  -- Random 15-100 seconds
  status TEXT DEFAULT 'queued',  -- queued, sending, sent, failed
  metadata JSONB,  -- Store template variables, campaign info, etc.
  created_at TIMESTAMP DEFAULT NOW(),
  scheduled_for TIMESTAMP DEFAULT NOW(),  -- When to send (for future use)
  sent_at TIMESTAMP,
  error_message TEXT
);

CREATE INDEX idx_email_queue_status ON email_queue(status);
CREATE INDEX idx_email_queue_scheduled ON email_queue(scheduled_for) WHERE status = 'queued';
```

## Domain Configuration

Hardcoded in Python worker (can move to DB later):

```python
DOMAIN_CONFIG = [
    {"domain": "connect-ozlistings.com", "sender_name": "jeff"},
    {"domain": "engage-ozlistings.com", "sender_name": "jeffrey"},
    {"domain": "get-ozlistings.com", "sender_name": "jeff.richmond"},
    {"domain": "join-ozlistings.com", "sender_name": "jeff.r"},
    {"domain": "outreach-ozlistings.com", "sender_name": "jeffrey.r"},
    {"domain": "ozlistings-reach.com", "sender_name": "jeff"},
    {"domain": "reach-ozlistings.com", "sender_name": "jeffrey"},
]
```

## Implementation Details

### Frontend API Route (`/api/campaigns/upload`)

**Input**: CSV file with columns:
- `email` (required)
- `subject` (required)
- `body` (required) - or use template with variables
- Any other template variables (e.g., `first_name`, `company`)

**Process**:
1. Parse CSV
2. For each row:
   - Assign `domain_index` using round-robin: `index % 7`
   - Generate `random_delay_seconds` (15-100)
   - Construct `from_email`: `f"{sender_name}@{domain}"`
   - Insert into `email_queue`
3. Bulk insert all rows
4. Return success with count

**Example**:
```typescript
// Round-robin domain assignment
const domainIndex = rowIndex % 7;
const domainConfig = DOMAIN_CONFIG[domainIndex];
const fromEmail = `${domainConfig.sender_name}@${domainConfig.domain}`;
const delaySeconds = Math.floor(Math.random() * (100 - 15 + 1)) + 15;
```

### Python Worker (`services/campaign-runner/`)

**Structure**:
```
campaign-runner/
├── main.py           # Main loop, polling logic
├── email_sender.py   # SparkPost API integration
├── db.py            # Supabase queries
├── config.py        # Environment variables
├── pyproject.toml   # Dependencies
└── Dockerfile       # For GCP VM deployment
```

**Main Loop** (`main.py`):
```python
while True:
    current_hour = datetime.now().hour
    
    # Only send during working hours (9am-5pm)
    if 9 <= current_hour < 17:
        # Poll queue for batch
        emails = db.get_queued_emails(limit=20)
        
        for email in emails:
            # Lock row (FOR UPDATE SKIP LOCKED)
            db.mark_processing(email.id)
            
            # Apply delay
            await asyncio.sleep(email.delay_seconds)
            
            # Send via SparkPost
            success = await email_sender.send(
                to_email=email.to_email,
                from_email=email.from_email,
                subject=email.subject,
                body=email.body
            )
            
            # Update status
            if success:
                db.mark_sent(email.id)
            else:
                db.mark_failed(email.id, error_message)
    
    # Wait 60 seconds before next poll
    await asyncio.sleep(60)
```

**Email Sender** (`email_sender.py`):
- Reuse SparkPost code from `user-event-email` service
- Modify to accept `from_email` parameter (not just Config.SPARKPOST_SENDER)
- Handle domain-specific sender addresses

**Database Queries** (`db.py`):
```python
async def get_queued_emails(limit: int = 20):
    """Fetch queued emails with row-level locking."""
    query = """
        SELECT * FROM email_queue
        WHERE status = 'queued'
        AND scheduled_for <= NOW()
        ORDER BY created_at ASC
        LIMIT $1
        FOR UPDATE SKIP LOCKED
    """
    # Execute query and return results
```

## Frontend UI Design

### Page Location
- **Route**: `/admin/email-campaigns`
- Uses existing admin authentication and layout
- Matches existing design patterns (Tailwind CSS, gray-50 background, indigo buttons)

### UI Components

#### Section 1: Upload & Launch

**File Upload Area:**
- Drag & drop zone OR "Choose File" button
- Shows selected file name after selection
- CSV format hint: "CSV should include: Email, Subject, Body (or template variables)"
- "Launch Campaign" button (enabled after file selected)

**Visual Layout:**
```
┌─────────────────────────────────────────┐
│  Email Campaign                         │
│                                         │
│  📎 Upload CSV File                     │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  Drag CSV file here or click to  │  │
│  │  browse...                        │  │
│  │                                   │  │
│  │  [Choose File]                   │  │
│  └───────────────────────────────────┘  │
│                                         │
│  📄 developers_prospective_batch.csv   │
│                                         │
│  [Launch Campaign]                     │
└─────────────────────────────────────────┘
```

#### Section 2: Campaign Status

**Summary Stats Display:**
- Status badge: "Sending" / "Completed" / "Paused"
- Progress bar: "450 of 900 sent (50%)"
- Three stat cards: Queued | Sent | Failed
- "Refresh Stats" button (manual refresh)
- Last updated timestamp

**Visual Layout:**
```
┌─────────────────────────────────────────┐
│  Campaign Status                        │
│                                         │
│  Status: 🟢 Sending                    │
│                                         │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  450 of 900 sent (50%)                 │
│                                         │
│  ┌──────┐ ┌──────┐ ┌──────┐           │
│  │ 450  │ │ 450  │ │  0   │           │
│  │Queued│ │ Sent │ │Failed│           │
│  └──────┘ └──────┘ └──────┘           │
│                                         │
│  Last updated: 2:30 PM                  │
│                                         │
│  [🔄 Refresh Stats]                    │
└─────────────────────────────────────────┘
```

### User Flow

1. Navigate to `/admin/email-campaigns`
2. Upload CSV file (drag & drop or file picker)
3. Click "Launch Campaign" (immediately after upload)
4. See success message: "Campaign launched! 900 emails queued."
5. Status section appears showing progress
6. Click "Refresh Stats" button to update numbers manually

### Frontend Files to Create

**Page Component:**
- `oz-dev-dash/src/app/admin/email-campaigns/page.tsx` - Main page component

**API Routes:**
- `oz-dev-dash/src/app/api/campaigns/upload/route.ts` - Handle CSV upload + queue emails
- `oz-dev-dash/src/app/api/campaigns/status/route.ts` - Get campaign stats from DB

**Reusable Components (Optional):**
- `oz-dev-dash/src/components/admin/FileUpload.tsx` - Drag & drop file input
- `oz-dev-dash/src/components/admin/CampaignStatus.tsx` - Progress and stats display

### CSV Format Requirements

**Required Columns:**
- `Email` (required) - Recipient email address
- `Subject` (required) - Email subject line
- `Body` (required) - Email body content (can include template variables like `{{Name}}`, `{{Company}}`)

**Optional Columns** (for template variable replacement):
- `Name` - For `{{Name}}` replacement
- `Company` - For `{{Company}}` replacement
- `Location` - For `{{Location}}` replacement
- Any other variables used in the email body template

**Example CSV:**
```csv
Email,Subject,Body,Name,Company
john@example.com,Re: Opportunity Zone Investment,"Hi {{Name}}, I wanted to reach out...",John Doe,ABC Corp
jane@example.com,Re: Opportunity Zone Investment,"Hi {{Name}}, I wanted to reach out...",Jane Smith,XYZ Inc
```

### API Endpoints

#### POST `/api/campaigns/upload`
**Request:**
- `multipart/form-data` with CSV file
- File field: `file`

**Process:**
1. Parse CSV file
2. Validate required columns (Email, Subject, Body)
3. For each row:
   - Assign `domain_index` using round-robin: `index % 7`
   - Generate `random_delay_seconds` (15-100)
   - Construct `from_email`: `f"{sender_name}@{domain}"`
   - Replace template variables in Subject and Body (e.g., `{{Name}}` → actual name)
   - Insert into `email_queue` table
4. Bulk insert all rows
5. Return success response with count

**Response:**
```json
{
  "success": true,
  "message": "Campaign launched successfully",
  "totalEmails": 900,
  "queued": 900
}
```

#### GET `/api/campaigns/status`
**Response:**
```json
{
  "status": "sending", // "sending" | "completed" | "paused"
  "total": 900,
  "queued": 450,
  "sent": 450,
  "failed": 0,
  "lastUpdated": "2024-01-15T14:30:00Z"
}
```

### Design Principles

1. **Simplicity First** - Single page, linear flow
2. **Minimal Options** - No advanced settings, just upload and launch
3. **Clear Status** - Big numbers, simple progress bar
4. **Manual Refresh** - User clicks button to update stats (no auto-refresh)
5. **Matches Existing Style** - Uses same Tailwind patterns as `/admin` dashboard

### Implementation Notes

- After launch, upload section can remain visible or be hidden (TBD)
- For now, only one active campaign at a time
- Show loading state during CSV processing
- Display error messages if CSV parsing fails or required columns missing

## Timing & Capacity

### For 900 Emails in 2 Days

**Option 1: One Day**
- 900 emails ÷ 8 hours = 112.5 emails/hour
- ~1.9 emails/minute
- With 15-100 second delays, easily achievable
- Start at 9am, finish by 5pm

**Option 2: Two Days**
- 450 emails/day ÷ 8 hours = 56 emails/hour
- ~0.9 emails/minute
- Very comfortable pace
- More natural distribution

### Worker Polling Pattern

- Poll every **60 seconds**
- Process **10-20 emails** per poll
- Each email has **15-100 second delay**
- Natural staggering throughout the day

**Example Timeline**:
```
9:00:00 AM - Poll, get 20 emails
9:00:15 AM - Send email 1 (delay: 15s)
9:00:47 AM - Send email 2 (delay: 32s)
9:01:23 AM - Send email 3 (delay: 36s)
...
9:01:00 AM - Poll again, get next 20 emails
```

## SparkPost Integration

### API Usage
- Use SparkPost Transmissions API
- Endpoint: `https://api.sparkpost.com/api/v1/transmissions`
- Authentication: API key in header
- Payload includes `from`, `to`, `subject`, `html`, `text`

### Domain Rotation
- Each email uses different `from` address based on `domain_index`
- SparkPost handles sending through the configured domain
- All domains are already verified in SparkPost

### Code Pattern
```python
payload = {
    "recipients": [{"address": {"email": to_email}}],
    "content": {
        "from": from_email,  # e.g., "jeff@connect-ozlistings.com"
        "subject": subject,
        "html": html_body,
        "text": text_body,
    },
}
```

## Deployment

### GCP VM Setup
1. Create VM instance
2. Install Python 3.11+
3. Clone repo or deploy code
4. Set environment variables:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SPARKPOST_API_KEY`
5. Run worker: `python main.py` or use systemd service
6. Monitor logs

### Environment Variables
```bash
# Supabase
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...

# SparkPost
SPARKPOST_API_KEY=...

# Logging
LOG_LEVEL=INFO
```

## Monitoring & Debugging

### Queue Status
- Check `email_queue` table for status counts
- Monitor `sent_at` timestamps
- Review `error_message` for failures

### Logging
- Log each email send attempt
- Log polling cycles
- Log errors with details
- Use structured logging (JSON)

### Metrics to Track
- Emails queued
- Emails sent (success)
- Emails failed
- Average time to send
- Domain distribution

## Future Enhancements (Not in Initial Build)

- Multi-email sequences (Email 1, 2, 3)
- Ramp-up logic (20 → 50 → 100 emails/day)
- Weekend detection and skipping
- Reply detection and auto-pause
- Timezone-aware sending
- Campaign management UI
- Template system with variables
- A/B testing
- Analytics dashboard

## File Structure

```
ozl-backend/
├── docs/
│   └── cold_email_campaign_implementation.md (this file)
├── services/
│   └── campaign-runner/
│       ├── main.py
│       ├── email_sender.py
│       ├── db.py
│       ├── config.py
│       ├── pyproject.toml
│       └── Dockerfile
└── scripts/
    └── deploy_campaign_worker.sh
```

## Next Steps

1. ✅ Create database migration for `email_queue` table
2. ✅ Build Python worker (`campaign-runner` service)
3. ✅ Update SparkPost email sender to support multiple domains
4. ✅ Create frontend API route for CSV upload
5. ✅ Test with small batch (10-20 emails)
6. ✅ Deploy to GCP VM
7. ✅ Run full 900 email campaign

## Questions & Decisions Made

**Q: Continuous drip or scheduled batches?**  
A: Continuous drip during working hours (9am-5pm)

**Q: Can we send 900 emails in one day?**  
A: Yes, easily. ~112 emails/hour is very manageable.

**Q: Working hours or all day?**  
A: Working hours only (better open rates, more natural)

**Q: Do we need ramp-up logic?**  
A: No, not for initial build

**Q: Do we need reply checking?**  
A: No, not for initial build

**Q: SMTP or SparkPost API?**  
A: SparkPost API (already configured, simpler)

