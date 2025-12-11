# Cold Email Campaign - Step-by-Step Implementation Plan

## Overview

This document provides a detailed, step-by-step implementation plan for building the cold email campaign system. The plan flows from **Frontend → Backend** and breaks down each feature into small, independently testable steps.

**Repositories:**
- **Frontend**: `oz-dev-dash` (Next.js)
- **Backend**: `ozl-backend` (Python worker + Supabase)

---

## Phase 1: Database Foundation

### Step 1.1: Create Database Migration
**Location**: `ozl-backend/supabase/migrations/` (or run directly in Supabase SQL editor)

**Task**: Create `email_queue` table

**SQL**:
```sql
CREATE TABLE email_queue (
  id SERIAL PRIMARY KEY,
  to_email TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  from_email TEXT NOT NULL,
  domain_index INTEGER NOT NULL,
  delay_seconds INTEGER NOT NULL,
  status TEXT DEFAULT 'queued',
  metadata JSONB,
  created_at TIMESTAMP DEFAULT NOW(),
  scheduled_for TIMESTAMP DEFAULT NOW(),
  sent_at TIMESTAMP,
  error_message TEXT
);

CREATE INDEX idx_email_queue_status ON email_queue(status);
CREATE INDEX idx_email_queue_scheduled ON email_queue(scheduled_for) WHERE status = 'queued';
```

**Test**: 
- Run migration in Supabase
- Verify table exists: `SELECT * FROM email_queue LIMIT 1;`
- Verify indexes exist

**Acceptance Criteria**: ✅ Table created with all columns and indexes

---

### Step 1.2: Test Manual Database Insert
**Location**: Supabase SQL Editor

**Task**: Insert a test row manually to verify schema

**SQL**:
```sql
INSERT INTO email_queue (
  to_email, subject, body, from_email, domain_index, delay_seconds, status
) VALUES (
  'test@example.com',
  'Test Subject',
  'Test Body',
  'jeff@connect-ozlistings.com',
  0,
  30,
  'queued'
);

SELECT * FROM email_queue WHERE to_email = 'test@example.com';
```

**Test**: Verify row inserted correctly

**Acceptance Criteria**: ✅ Can insert and query rows successfully

---

## Phase 2: Frontend - UI Components

### Step 2.1: Create Campaign Page Route
**Location**: `oz-dev-dash/src/app/admin/email-campaigns/page.tsx`

**Task**: Create basic page structure with admin layout

**Implementation**:
- Use existing admin auth pattern (check `oz-dev-dash/src/app/admin/page.tsx`)
- Create page component with header: "Email Campaign"
- Add basic layout matching existing admin pages

**Test**: 
- Navigate to `/admin/email-campaigns`
- Verify page loads (may show empty state for now)
- Verify admin auth works

**Acceptance Criteria**: ✅ Page accessible at `/admin/email-campaigns` with admin auth

---

### Step 2.2: Build File Upload Component
**Location**: `oz-dev-dash/src/components/admin/FileUpload.tsx` (or inline in page)

**Task**: Create drag & drop file upload component

**Implementation**:
- Drag & drop zone
- File picker button
- Display selected file name
- Accept only CSV files
- Show file size

**Test**:
- Upload a CSV file
- Verify file name displays
- Try uploading non-CSV (should reject)
- Verify drag & drop works

**Acceptance Criteria**: ✅ Can select CSV file via drag & drop or file picker

---

### Step 2.3: Build Campaign Status Component
**Location**: `oz-dev-dash/src/components/admin/CampaignStatus.tsx` (or inline in page)

**Task**: Create status display component

**Implementation**:
- Status badge (Sending/Completed/Paused)
- Progress bar component
- Three stat cards (Queued/Sent/Failed)
- "Refresh Stats" button
- Last updated timestamp

**Test**:
- Render component with mock data
- Verify all elements display correctly
- Test refresh button (can be no-op for now)

**Acceptance Criteria**: ✅ Status component renders with all elements

---

### Step 2.4: Integrate Components into Page
**Location**: `oz-dev-dash/src/app/admin/email-campaigns/page.tsx`

**Task**: Combine upload and status components

**Implementation**:
- Add FileUpload component
- Add CampaignStatus component (initially hidden or with empty state)
- Add "Launch Campaign" button
- Basic state management (file selected, campaign launched)

**Test**:
- Upload file → see file name
- Click "Launch Campaign" → see loading state
- Verify components render correctly together

**Acceptance Criteria**: ✅ Page shows upload area and status area

---

## Phase 3: Frontend - API Routes

### Step 3.1: Create CSV Upload API Route (Parse Only)
**Location**: `oz-dev-dash/src/app/api/campaigns/upload/route.ts`

**Task**: Parse CSV file and return parsed data (no DB insert yet)

**Implementation**:
- Accept `multipart/form-data` with CSV file
- Parse CSV using a library (e.g., `papaparse` or built-in)
- Validate required columns: `Email`, `Subject`, `Body`
- Return parsed rows as JSON

**Test**:
```bash
# Test with curl or Postman
curl -X POST http://localhost:3000/api/campaigns/upload \
  -F "file=@test.csv"
```

**Expected Response**:
```json
{
  "success": true,
  "rows": [
    {"Email": "test@example.com", "Subject": "...", "Body": "..."}
  ],
  "totalRows": 1
}
```

**Acceptance Criteria**: ✅ Can upload CSV and get parsed JSON back

---

### Step 3.2: Add Domain Assignment Logic
**Location**: `oz-dev-dash/src/app/api/campaigns/upload/route.ts`

**Task**: Add domain rotation logic to parsed rows

**Implementation**:
- Define `DOMAIN_CONFIG` array (7 domains)
- For each row, assign `domain_index` (round-robin: `index % 7`)
- Generate `random_delay_seconds` (15-100)
- Construct `from_email` from domain config
- Add these fields to each row object

**Test**:
- Upload CSV with 10 rows
- Verify domain_index cycles 0-6 correctly
- Verify delays are between 15-100
- Verify from_email format is correct

**Acceptance Criteria**: ✅ Each row has correct domain_index, delay_seconds, and from_email

---

### Step 3.3: Add Template Variable Replacement
**Location**: `oz-dev-dash/src/app/api/campaigns/upload/route.ts`

**Task**: Replace template variables in Subject and Body

**Implementation**:
- For each row, find template variables (e.g., `{{Name}}`, `{{Company}}`)
- Replace with actual values from CSV columns
- Handle missing variables (leave as-is or empty string)

**Test**:
- CSV with `Name` column and body containing `{{Name}}`
- Verify `{{Name}}` replaced with actual name
- Test with missing column (should handle gracefully)

**Acceptance Criteria**: ✅ Template variables replaced correctly in Subject and Body

---

### Step 3.4: Connect to Database - Insert Queue Rows
**Location**: `oz-dev-dash/src/app/api/campaigns/upload/route.ts`

**Task**: Insert parsed rows into `email_queue` table

**Implementation**:
- Use Supabase client (check existing patterns in `oz-dev-dash`)
- Bulk insert all rows into `email_queue`
- Handle errors (duplicate emails, DB errors)
- Return success with count

**Test**:
- Upload CSV with 5 rows
- Verify 5 rows inserted into `email_queue` table
- Check status is 'queued'
- Verify all fields populated correctly

**Acceptance Criteria**: ✅ CSV upload creates rows in database

---

### Step 3.5: Create Status API Route
**Location**: `oz-dev-dash/src/app/api/campaigns/status/route.ts`

**Task**: Query database for campaign statistics

**Implementation**:
- Query `email_queue` table:
  - Count by status (queued, sent, failed)
  - Total count
  - Latest `sent_at` timestamp
- Return JSON response

**Test**:
```bash
curl http://localhost:3000/api/campaigns/status
```

**Expected Response**:
```json
{
  "status": "sending",
  "total": 900,
  "queued": 450,
  "sent": 450,
  "failed": 0,
  "lastUpdated": "2024-01-15T14:30:00Z"
}
```

**Acceptance Criteria**: ✅ Status API returns correct counts

---

### Step 3.6: Connect Frontend to Upload API
**Location**: `oz-dev-dash/src/app/admin/email-campaigns/page.tsx`

**Task**: Call upload API when "Launch Campaign" clicked

**Implementation**:
- On file upload, store file in state
- On "Launch Campaign" click:
  - Create FormData with file
  - POST to `/api/campaigns/upload`
  - Show loading state
  - Handle success/error
  - Show success message

**Test**:
- Upload CSV file
- Click "Launch Campaign"
- Verify API called
- Verify success message shown
- Check database for inserted rows

**Acceptance Criteria**: ✅ Can launch campaign from UI and see success

---

### Step 3.7: Connect Frontend to Status API
**Location**: `oz-dev-dash/src/app/admin/email-campaigns/page.tsx`

**Task**: Fetch and display campaign status

**Implementation**:
- On page load (if campaign exists), fetch status
- On "Refresh Stats" click, fetch status
- Update CampaignStatus component with real data
- Show loading state during fetch

**Test**:
- Launch campaign
- Click "Refresh Stats"
- Verify status updates
- Verify progress bar updates
- Verify stat cards show correct numbers

**Acceptance Criteria**: ✅ Status displays real data from database

---

## Phase 4: Backend - Python Worker Setup

### Step 4.1: Create Campaign Runner Service Structure
**Location**: `ozl-backend/services/campaign-runner/`

**Task**: Create directory structure and basic files

**Files to create**:
```
campaign-runner/
├── main.py
├── email_sender.py
├── db.py
├── config.py
├── pyproject.toml
└── README.md
```

**Test**: Verify directory structure created

**Acceptance Criteria**: ✅ Directory structure exists

---

### Step 4.2: Create Config Module
**Location**: `ozl-backend/services/campaign-runner/config.py`

**Task**: Environment variable configuration

**Implementation**:
- Load from `.env` file
- Define Config class with:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `SPARKPOST_API_KEY`
  - `LOG_LEVEL`
- Add validation method

**Test**:
- Create `.env` file with test values
- Import config, verify values loaded
- Test validation (missing required vars)

**Acceptance Criteria**: ✅ Config loads environment variables correctly

---

### Step 4.3: Create Database Module
**Location**: `ozl-backend/services/campaign-runner/db.py`

**Task**: Supabase connection and query functions

**Implementation**:
- Initialize Supabase client
- Function: `get_queued_emails(limit: int)` - fetch queued emails with locking
- Function: `mark_processing(email_id)` - update status to 'processing'
- Function: `mark_sent(email_id)` - update status to 'sent'
- Function: `mark_failed(email_id, error_message)` - update status to 'failed'

**Test**:
- Connect to Supabase
- Call `get_queued_emails(5)` - verify returns rows
- Test row locking (run two workers, verify no duplicates)
- Test status updates

**Acceptance Criteria**: ✅ Can query and update database

---

### Step 4.4: Create Email Sender Module (SparkPost)
**Location**: `ozl-backend/services/campaign-runner/email_sender.py`

**Task**: SparkPost API integration

**Implementation**:
- Copy/adopt from `ozl-backend/services/user-event-email/email_sender.py`
- Modify to accept `from_email` parameter (not just Config.SPARKPOST_SENDER)
- Function: `send_email(to_email, from_email, subject, body)` - send via SparkPost
- Handle errors and return success/failure

**Test**:
- Send test email with different `from_email` addresses
- Verify email received
- Test error handling (invalid API key, etc.)

**Acceptance Criteria**: ✅ Can send emails via SparkPost with custom from addresses

---

### Step 4.5: Create Main Worker Loop (Basic)
**Location**: `ozl-backend/services/campaign-runner/main.py`

**Task**: Basic polling loop without time restrictions

**Implementation**:
- Infinite loop
- Poll database for queued emails (limit 20)
- For each email:
  - Mark as 'processing'
  - Sleep for `delay_seconds`
  - Send email
  - Update status
- Sleep 60 seconds between polls

**Test**:
- Run worker locally
- Queue 5 test emails in database
- Verify worker processes them
- Verify emails sent
- Verify status updates in DB

**Acceptance Criteria**: ✅ Worker processes emails and sends them

---

### Step 4.6: Add Working Hours Restriction
**Location**: `ozl-backend/services/campaign-runner/main.py`

**Task**: Only send during 9am-5pm

**Implementation**:
- Check current hour before processing
- If `9 <= hour < 17`: process emails
- Else: skip and wait

**Test**:
- Set system time to 8am → verify no emails sent
- Set system time to 10am → verify emails sent
- Set system time to 6pm → verify no emails sent

**Acceptance Criteria**: ✅ Worker only sends during working hours

---

### Step 4.7: Add Error Handling & Logging
**Location**: `ozl-backend/services/campaign-runner/main.py`

**Task**: Robust error handling and logging

**Implementation**:
- Try/catch around email sending
- Log each step (polling, sending, errors)
- Mark failed emails with error message
- Continue processing even if one email fails
- Structured logging (JSON format)

**Test**:
- Queue email with invalid recipient
- Verify error logged
- Verify email marked as 'failed'
- Verify worker continues processing other emails

**Acceptance Criteria**: ✅ Errors handled gracefully, logging works

---

### Step 4.8: Create Deployment Files
**Location**: `ozl-backend/services/campaign-runner/`

**Task**: Dockerfile and deployment scripts

**Files**:
- `Dockerfile` - containerize worker
- `pyproject.toml` - Python dependencies
- `requirements.txt` (if not using pyproject.toml)
- `.env.example` - example environment variables

**Test**:
- Build Docker image
- Run container locally
- Verify worker starts and connects to DB

**Acceptance Criteria**: ✅ Can containerize and deploy worker

---

## Phase 5: Integration & Testing

### Step 5.1: End-to-End Test (Small Batch)
**Task**: Test full flow with 5-10 emails

**Steps**:
1. Frontend: Upload CSV with 5 emails
2. Frontend: Launch campaign
3. Verify rows in database
4. Start Python worker
5. Verify emails sent
6. Frontend: Refresh stats, verify counts

**Test**: Complete flow works end-to-end

**Acceptance Criteria**: ✅ Can send small batch successfully

---

### Step 5.2: Test Domain Rotation
**Task**: Verify emails distributed across domains

**Steps**:
1. Upload CSV with 20 emails
2. Launch campaign
3. Check database: verify domain_index cycles 0-6
4. Check sent emails: verify different from addresses

**Test**: Domain rotation works correctly

**Acceptance Criteria**: ✅ Emails distributed evenly across 7 domains

---

### Step 5.3: Test Timing & Delays
**Task**: Verify delays work correctly

**Steps**:
1. Queue emails with known delays
2. Monitor worker logs
3. Verify timing between sends matches delays

**Test**: Delays applied correctly

**Acceptance Criteria**: ✅ Random delays work as expected

---

### Step 5.4: Test Working Hours Restriction
**Task**: Verify worker respects 9am-5pm window

**Steps**:
1. Queue emails
2. Run worker outside working hours
3. Verify no emails sent
4. Run during working hours
5. Verify emails sent

**Test**: Time restrictions work

**Acceptance Criteria**: ✅ Worker only sends during working hours

---

### Step 5.5: Load Test (100+ Emails)
**Task**: Test with larger batch

**Steps**:
1. Upload CSV with 100 emails
2. Launch campaign
3. Monitor worker processing
4. Verify all emails sent
5. Check for errors or issues

**Test**: System handles larger batches

**Acceptance Criteria**: ✅ Can process 100+ emails successfully

---

## Phase 6: Deployment

### Step 6.1: Deploy Database Migration
**Location**: Supabase Dashboard

**Task**: Run migration in production

**Steps**:
1. Run SQL migration in Supabase production
2. Verify table created
3. Test insert/query

**Acceptance Criteria**: ✅ Production database ready

---

### Step 6.2: Deploy Frontend Changes
**Location**: `oz-dev-dash` (Vercel or similar)

**Task**: Deploy frontend with new routes

**Steps**:
1. Merge code to main branch
2. Deploy to production
3. Test `/admin/email-campaigns` page
4. Test API routes

**Acceptance Criteria**: ✅ Frontend deployed and accessible

---

### Step 6.3: Deploy Python Worker to GCP VM
**Location**: GCP VM instance

**Task**: Set up and run worker on VM

**Steps**:
1. Create GCP VM instance
2. Install Python 3.11+
3. Clone repo or deploy code
4. Set environment variables
5. Install dependencies
6. Run worker (or set up systemd service)
7. Monitor logs

**Acceptance Criteria**: ✅ Worker running on GCP VM

---

### Step 6.4: Production Test Run
**Task**: Test with real campaign (small batch first)

**Steps**:
1. Upload CSV with 10 real emails
2. Launch campaign
3. Monitor worker logs
4. Verify emails received
5. Check status in frontend

**Acceptance Criteria**: ✅ Production system works end-to-end

---

## Testing Checklist

After each step, verify:
- ✅ Code works as expected
- ✅ No errors in console/logs
- ✅ Database changes visible (if applicable)
- ✅ Can move to next step

## Rollback Plan

If issues arise:
1. **Database**: Can manually delete rows from `email_queue` table
2. **Frontend**: Revert deployment, old code still works
3. **Worker**: Stop worker process, no emails sent

## Notes

- **Frontend Repo**: `oz-dev-dash`
- **Backend Repo**: `ozl-backend`
- **Database**: Supabase (shared between frontend and backend)
- **Email Provider**: SparkPost API
- **Worker Host**: GCP VM

## Dependencies

- Frontend needs Supabase client (already exists)
- Backend needs Supabase Python client
- Backend needs SparkPost API key
- Both need access to same Supabase database


