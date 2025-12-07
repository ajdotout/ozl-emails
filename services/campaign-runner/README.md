# Campaign Runner Service

Python worker service that polls the `email_queue` table and sends emails via SparkPost API.

## Setup

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Create `.env` file:
   ```bash
   # Supabase Configuration
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
   
   # SparkPost Configuration
   SPARKPOST_API_KEY=your_sparkpost_api_key_here
   
   # Logging
   LOG_LEVEL=INFO
   ```

3. Run the worker:
   ```bash
   uv run python main.py
   ```

## Features

- Polls `email_queue` table every 60 seconds
- Processes batches of 20 emails per cycle
- Only sends during working hours (9am-5pm)
- Domain rotation across 7 domains
- Random delays between emails (15-100 seconds)
- Error handling and retry logic

## Docker Deployment

### Build Docker Image
```bash
docker build -t campaign-runner .
```

### Run Container
```bash
docker run --env-file .env campaign-runner
```

### Run with Environment Variables
```bash
docker run \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_SERVICE_ROLE_KEY=your_key \
  -e SPARKPOST_API_KEY=your_key \
  -e LOG_LEVEL=INFO \
  campaign-runner
```

