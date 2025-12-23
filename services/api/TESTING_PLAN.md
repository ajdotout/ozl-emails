# Campaign API Backend Migration - Testing Plan

This document provides a comprehensive testing plan for the migrated campaign API backend.

## Prerequisites

1. **Backend API Service Running**
   ```bash
   cd ozl-backend/services/api
   uv sync
   uv run python main.py
   ```
   Service should be running on `http://localhost:8000`

2. **Frontend Environment Variable**
   Add to `.env.local` in `oz-dev-dash`:
   ```bash
   NEXT_PUBLIC_BACKEND_API_URL=http://localhost:8000
   ```

3. **Database Setup**
   - Ensure Supabase is running and accessible
   - Have test campaigns and contacts in the database
   - Have admin user credentials ready

4. **API Keys**
   - SparkPost API key configured
   - Groq API key configured
   - All environment variables set in backend `.env`

## Test Categories

### 1. Authentication Tests

#### Test 1.1: Valid Authentication
- **Steps:**
  1. Login to frontend admin panel
  2. Open browser DevTools → Network tab
  3. Navigate to campaigns page
  4. Check API requests have `Authorization: Basic ...` header
- **Expected:** All requests succeed with 200 status

#### Test 1.2: Invalid Authentication
- **Steps:**
  1. Clear admin cookies
  2. Try to access campaigns page
  3. Or manually call API without auth header
- **Expected:** 401 Unauthorized responses

#### Test 1.3: Missing Authorization Header
- **Steps:**
  1. Use curl/Postman to call API without Authorization header
  2. Example: `curl http://localhost:8000/api/v1/campaigns`
- **Expected:** 401 Unauthorized

### 2. Campaign CRUD Tests

#### Test 2.1: List Campaigns
- **Endpoint:** `GET /api/v1/campaigns`
- **Steps:**
  1. Call endpoint from frontend or API client
  2. Verify response includes all campaigns
  3. Check that email stats (sent, failed) are included
- **Expected:** Returns array of campaigns with stats

#### Test 2.2: Create Campaign
- **Endpoint:** `POST /api/v1/campaigns`
- **Steps:**
  1. Create campaign via frontend
  2. Verify campaign appears in list
  3. Check database for new record
- **Expected:** Campaign created with status "draft"

#### Test 2.3: Get Campaign
- **Endpoint:** `GET /api/v1/campaigns/{id}`
- **Steps:**
  1. Get existing campaign ID
  2. Call endpoint
  3. Verify all fields are returned correctly
- **Expected:** Complete campaign object returned

#### Test 2.4: Update Campaign
- **Endpoint:** `PUT /api/v1/campaigns/{id}`
- **Steps:**
  1. Update campaign name, sections, etc.
  2. Verify changes saved
  3. Check database updated_at timestamp
- **Expected:** Campaign updated successfully

#### Test 2.5: Delete Campaign
- **Endpoint:** `DELETE /api/v1/campaigns/{id}`
- **Steps:**
  1. Create test campaign
  2. Delete it
  3. Verify campaign and associated emails deleted
- **Expected:** Campaign and emails removed from database

#### Test 2.6: Campaign Name Length Validation
- **Steps:**
  1. Try to create campaign with name > 25 characters
  2. Verify error message
- **Expected:** 400 error with message about 25 character limit

### 3. Email Generation Tests

#### Test 3.1: Start Generation (Background Job)
- **Endpoint:** `POST /api/v1/campaigns/{id}/generate`
- **Prerequisites:** Campaign in "draft" status with recipients selected
- **Steps:**
  1. Call generate endpoint
  2. Verify immediate response with "started" status
  3. Poll status endpoint to check progress
  4. Verify emails appear in email_queue with status "staged"
  5. Check campaign status changes to "staged"
- **Expected:** 
  - Immediate response: `{"status": "started", "message": "..."}`
  - After completion: staged_count > 0, campaign status = "staged"

#### Test 3.2: Generation Status Check
- **Endpoint:** `GET /api/v1/campaigns/{id}/status`
- **Steps:**
  1. Start generation
  2. Immediately check status
  3. Wait a few seconds and check again
  4. Verify staged_count increases
- **Expected:** Status reflects generation progress

#### Test 3.3: Generation with No Recipients
- **Steps:**
  1. Create campaign without recipients
  2. Try to generate
  3. Check status
- **Expected:** No emails staged, appropriate status

#### Test 3.4: Re-generate Campaign
- **Steps:**
  1. Generate campaign once
  2. Modify campaign sections
  3. Generate again
  4. Verify old staged emails deleted, new ones created
- **Expected:** Fresh staging, old emails removed

### 4. Campaign Launch Tests

#### Test 4.1: Launch Campaign (Background Job)
- **Endpoint:** `POST /api/v1/campaigns/{id}/launch`
- **Prerequisites:** Campaign in "staged" status with staged emails
- **Steps:**
  1. Call launch endpoint
  2. Verify immediate response
  3. Poll status endpoint
  4. Verify emails get scheduled_for timestamps
  5. Check domain rotation (domain_index assigned)
  6. Verify campaign status changes to "scheduled"
- **Expected:**
  - Immediate response: `{"status": "started", "message": "..."}`
  - After completion: queued_count > 0, scheduled_for set, campaign status = "scheduled"

#### Test 4.2: Launch Status Check
- **Steps:**
  1. Start launch
  2. Check status repeatedly
  3. Verify queued_count increases
  4. Verify is_launching flag changes
- **Expected:** Status reflects launch progress

#### Test 4.3: Domain Rotation
- **Steps:**
  1. Launch campaign with multiple emails
  2. Check email_queue records
  3. Verify domain_index rotates across domains
  4. Verify from_email matches domain
- **Expected:** Even distribution across domains

#### Test 4.4: Scheduling Logic
- **Steps:**
  1. Launch campaign
  2. Check scheduled_for timestamps
  3. Verify intervals between same-domain emails (~3.5 min)
  4. Verify working hours only (9am-5pm)
  5. Verify weekends skipped
- **Expected:** Proper scheduling within constraints

#### Test 4.5: Cross-Campaign Domain Coordination
- **Steps:**
  1. Launch Campaign A
  2. Launch Campaign B
  3. Check scheduled_for times
  4. Verify Campaign B respects Campaign A's domain schedules
- **Expected:** No domain conflicts, proper spacing

### 5. Email Management Tests

#### Test 5.1: List Emails
- **Endpoint:** `GET /api/v1/campaigns/{id}/emails`
- **Steps:**
  1. Generate campaign
  2. List emails
  3. Verify pagination (limit/offset)
  4. Test status filter
- **Expected:** Correct emails returned, pagination works

#### Test 5.2: Get Single Email
- **Endpoint:** `GET /api/v1/campaigns/{id}/emails/{email_id}`
- **Steps:**
  1. Get email ID from list
  2. Fetch single email
  3. Verify all fields present
- **Expected:** Complete email object

#### Test 5.3: Update Email
- **Endpoint:** `PUT /api/v1/campaigns/{id}/emails/{email_id}`
- **Steps:**
  1. Update email body or subject
  2. Verify changes saved
  3. Check is_edited flag
- **Expected:** Email updated successfully

#### Test 5.4: Delete Email
- **Endpoint:** `DELETE /api/v1/campaigns/{id}/emails/{email_id}`
- **Steps:**
  1. Delete staged email
  2. Verify removed from list
  3. Check campaign total_recipients updated
- **Expected:** Email deleted, counts updated

### 6. Recipient Management Tests

#### Test 6.1: List Recipients
- **Endpoint:** `GET /api/v1/campaigns/{id}/recipients`
- **Steps:**
  1. Add recipients to campaign
  2. List recipients
  3. Verify contact data included
- **Expected:** Recipients with contact details returned

#### Test 6.2: Add Recipients
- **Endpoint:** `POST /api/v1/campaigns/{id}/recipients`
- **Steps:**
  1. Get contact IDs from database
  2. Add recipients to campaign
  3. Verify campaign_recipients table updated
- **Expected:** Recipients added successfully

### 7. Quick Operations Tests

#### Test 7.1: Test Send
- **Endpoint:** `POST /api/v1/campaigns/{id}/test-send`
- **Steps:**
  1. Create campaign with sections
  2. Call test-send with test email
  3. Check email inbox
  4. Verify email content correct
  5. Test with recipientEmailId
- **Expected:** Test email received with correct content

#### Test 7.2: Generate Subject
- **Endpoint:** `POST /api/v1/campaigns/{id}/generate-subject`
- **Steps:**
  1. Call with instructions
  2. Verify subject generated
  3. Check subject_prompt saved to campaign
- **Expected:** Valid subject line returned

### 8. Status and Summary Tests

#### Test 8.1: Campaign Status
- **Endpoint:** `GET /api/v1/campaigns/{id}/status`
- **Steps:**
  1. Check status at different campaign stages:
     - Draft (no recipients)
     - Draft (generating)
     - Staged (ready)
     - Staged (launching)
     - Scheduled (launched)
  2. Verify flags (is_generating, is_launching, etc.)
- **Expected:** Correct status flags for each stage

#### Test 8.2: Campaign Summary
- **Endpoint:** `GET /api/v1/campaigns/{id}/summary`
- **Steps:**
  1. Get summary for active campaign
  2. Verify counts (sent, failed, queued, etc.)
  3. Check SparkPost metrics (if configured)
- **Expected:** Accurate counts and metrics

#### Test 8.3: Global Status
- **Endpoint:** `GET /api/v1/campaigns/status`
- **Steps:**
  1. Call global status endpoint
  2. Verify campaign and email status counts
- **Expected:** Aggregate statistics returned

### 9. Error Handling Tests

#### Test 9.1: Campaign Not Found
- **Steps:**
  1. Call endpoints with invalid campaign ID
  2. Verify 404 responses
- **Expected:** 404 with appropriate error message

#### Test 9.2: Invalid Campaign State
- **Steps:**
  1. Try to launch campaign in wrong state
  2. Try to generate when already launched
  3. Verify 400 errors
- **Expected:** 400 with descriptive error messages

#### Test 9.3: Missing Required Fields
- **Steps:**
  1. Create campaign without required fields
  2. Verify validation errors
- **Expected:** 400 with field-specific errors

#### Test 9.4: Background Job Errors
- **Steps:**
  1. Cause error in background task (e.g., invalid data)
  2. Check logs
  3. Verify campaign state doesn't corrupt
- **Expected:** Error logged, campaign state preserved

### 10. Integration Tests

#### Test 10.1: Full Campaign Flow
- **Steps:**
  1. Create campaign
  2. Add recipients
  3. Generate emails
  4. Review emails
  5. Launch campaign
  6. Monitor sending
  7. Check summary
- **Expected:** Complete flow works end-to-end

#### Test 10.2: Large Batch Processing
- **Steps:**
  1. Create campaign with 1000+ recipients
  2. Generate emails
  3. Launch campaign
  4. Verify all emails processed
  5. Check performance
- **Expected:** Handles large batches without timeout

#### Test 10.3: Concurrent Operations
- **Steps:**
  1. Generate multiple campaigns simultaneously
  2. Launch multiple campaigns
  3. Verify no conflicts
- **Expected:** Concurrent operations work correctly

### 11. Frontend Integration Tests

#### Test 11.1: Campaign List Page
- **Steps:**
  1. Navigate to campaigns page
  2. Verify campaigns load from backend
  3. Check stats display correctly
- **Expected:** Page loads and displays data

#### Test 11.2: Campaign Editor
- **Steps:**
  1. Open campaign editor
  2. Make changes
  3. Save
  4. Verify changes persist
- **Expected:** Editor works with backend API

#### Test 11.3: Status Refresh Button
- **Steps:**
  1. Start generation/launch
  2. Click refresh button
  3. Verify status updates
- **Expected:** Manual refresh updates status

#### Test 11.4: Error Handling in UI
- **Steps:**
  1. Cause API error (e.g., network failure)
  2. Verify error message displayed
  3. Check UI doesn't break
- **Expected:** Graceful error handling

## Testing Checklist

Use this checklist to track testing progress:

- [ ] Authentication (all tests)
- [ ] Campaign CRUD (all tests)
- [ ] Email Generation (all tests)
- [ ] Campaign Launch (all tests)
- [ ] Email Management (all tests)
- [ ] Recipient Management (all tests)
- [ ] Quick Operations (all tests)
- [ ] Status and Summary (all tests)
- [ ] Error Handling (all tests)
- [ ] Integration Tests (all tests)
- [ ] Frontend Integration (all tests)

## Manual Testing Commands

### Using curl

```bash
# Set auth token (replace with actual base64(email:password))
export AUTH="Basic $(echo -n 'admin@example.com:password' | base64)"

# List campaigns
curl -H "Authorization: $AUTH" http://localhost:8000/api/v1/campaigns

# Get campaign
curl -H "Authorization: $AUTH" http://localhost:8000/api/v1/campaigns/{id}

# Create campaign
curl -X POST -H "Authorization: $AUTH" -H "Content-Type: application/json" \
  -d '{"name":"Test Campaign","sender":"jeff_richmond","sections":[]}' \
  http://localhost:8000/api/v1/campaigns

# Generate emails
curl -X POST -H "Authorization: $AUTH" -H "Content-Type: application/json" \
  -d '{"use_database_recipients":true}' \
  http://localhost:8000/api/v1/campaigns/{id}/generate

# Check status
curl -H "Authorization: $AUTH" http://localhost:8000/api/v1/campaigns/{id}/status

# Launch campaign
curl -X POST -H "Authorization: $AUTH" -H "Content-Type: application/json" \
  -d '{"all":true}' \
  http://localhost:8000/api/v1/campaigns/{id}/launch
```

### Using Python

```python
import requests
import base64

# Setup
BASE_URL = "http://localhost:8000"
email = "admin@example.com"
password = "password"
auth = base64.b64encode(f"{email}:{password}".encode()).decode()
headers = {
    "Authorization": f"Basic {auth}",
    "Content-Type": "application/json"
}

# List campaigns
response = requests.get(f"{BASE_URL}/api/v1/campaigns", headers=headers)
print(response.json())

# Get status
campaign_id = "your-campaign-id"
response = requests.get(f"{BASE_URL}/api/v1/campaigns/{campaign_id}/status", headers=headers)
print(response.json())
```

## Performance Testing

### Test Large Campaigns
- Campaign with 10,000+ recipients
- Verify generation completes
- Verify launch completes
- Check response times

### Test Concurrent Requests
- Multiple users accessing API simultaneously
- Verify no race conditions
- Check database locks work correctly

## Regression Testing

After migration, verify:
- [ ] All existing campaigns still work
- [ ] Email sending continues to work
- [ ] No data loss occurred
- [ ] Frontend features unchanged
- [ ] Performance acceptable

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check admin cookie exists
   - Verify Authorization header format
   - Check backend auth middleware

2. **500 Internal Server Error**
   - Check backend logs
   - Verify environment variables set
   - Check database connection

3. **Background Jobs Not Completing**
   - Check backend logs
   - Verify database queries succeed
   - Check for exceptions in task functions

4. **CORS Errors**
   - Verify FRONTEND_URL in backend .env
   - Check CORS middleware configuration

5. **Status Not Updating**
   - Verify status endpoint logic
   - Check scheduled_for IS NULL queries
   - Verify campaign status transitions

## Success Criteria

Migration is successful when:
- ✅ All tests pass
- ✅ No data loss
- ✅ Performance acceptable (< 2s for most endpoints)
- ✅ Background jobs complete successfully
- ✅ Frontend works seamlessly
- ✅ No timeout errors
- ✅ Error handling works correctly

