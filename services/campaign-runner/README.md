# Campaign Runner Service

Python worker service that polls the `email_queue` table and sends emails via SparkPost API.

## Setup

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Create `.env` file:
   ```bash
   SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
   SPARKPOST_API_KEY=your_sparkpost_api_key
   LOG_LEVEL=INFO
   ```

3. Run the worker:
   ```bash
   uv run python main.py
   ```

## Features

- Polls `email_queue` table every 60 seconds
- Processes batches of 10-20 emails
- Only sends during working hours (9am-5pm)
- Domain rotation across 7 domains
- Random delays between emails (15-100 seconds)
- Error handling and retry logic

