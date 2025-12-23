# Campaign API Service

Unified FastAPI backend service for campaign management.

## Setup

1. Install dependencies:
   ```bash
   cd services/api
   uv sync
   ```

2. Create `.env` file (copy from `env.template`):
   ```bash
   cp env.template .env
   # Edit .env with your actual values
   ```

3. Run the service:
   ```bash
   uv run python main.py
   ```

The service will start on `http://localhost:8000`.

## API Endpoints

All endpoints are prefixed with `/api/v1/campaigns`.

### Campaigns
- `GET /api/v1/campaigns` - List all campaigns
- `POST /api/v1/campaigns` - Create campaign
- `GET /api/v1/campaigns/{id}` - Get campaign
- `PUT /api/v1/campaigns/{id}` - Update campaign
- `DELETE /api/v1/campaigns/{id}` - Delete campaign
- `GET /api/v1/campaigns/{id}/status` - Get campaign status
- `GET /api/v1/campaigns/{id}/summary` - Get campaign summary
- `POST /api/v1/campaigns/{id}/generate` - Start email generation (background)
- `POST /api/v1/campaigns/{id}/launch` - Launch campaign (background)
- `POST /api/v1/campaigns/{id}/retry-failed` - Retry failed emails (background)
- `POST /api/v1/campaigns/{id}/test-send` - Send test email
- `POST /api/v1/campaigns/{id}/generate-subject` - Generate subject line
- `GET /api/v1/campaigns/status` - Get global status
- `GET /api/v1/campaigns/domains` - Get domain configuration

### Emails
- `GET /api/v1/campaigns/{id}/emails` - List emails
- `GET /api/v1/campaigns/{id}/emails/{email_id}` - Get email
- `PUT /api/v1/campaigns/{id}/emails/{email_id}` - Update email
- `DELETE /api/v1/campaigns/{id}/emails/{email_id}` - Delete email

### Recipients
- `GET /api/v1/campaigns/{id}/recipients` - List recipients
- `POST /api/v1/campaigns/{id}/recipients` - Add recipients

## Authentication

All endpoints require Basic authentication. The frontend sends the `Authorization: Basic <base64(email:password)>` header derived from the admin cookie.

## Background Jobs

The following endpoints return immediately and process in the background:
- `/generate` - Stages emails from campaign_recipients
- `/launch` - Schedules emails with domain rotation
- `/retry-failed` - Reschedules failed emails

Use the `/status` endpoint to check progress.

## Development

Run with auto-reload:
```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Testing

See `TESTING_PLAN.md` for comprehensive testing instructions.

