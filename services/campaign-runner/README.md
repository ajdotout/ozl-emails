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

### Quick Setup (Local/Development)

Use the setup script for easy deployment:

```bash
./setup.sh
```

This script will:
- Check Docker installation
- Build the Docker image
- Run the container with `.env` file
- Configure automatic restart policy
- Set up log rotation

### GCP VM Deployment

For production deployment on GCP VM, use the GCP setup script:

```bash
# Using .env file
./setup-gcp.sh

# Using GCP Secret Manager
./setup-gcp.sh --use-secret-manager --project-id YOUR_GCP_PROJECT_ID --secret-name campaign-runner-env
```

The GCP script includes:
- Support for GCP Secret Manager
- Production-ready restart policies
- Log rotation configuration
- Container lifecycle management

### Manual Docker Commands

#### Build Docker Image
```bash
docker build -t campaign-runner .
```

#### Run Container
```bash
docker run --env-file .env campaign-runner
```

#### Run with Environment Variables
```bash
docker run \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_SERVICE_ROLE_KEY=your_key \
  -e SPARKPOST_API_KEY=your_key \
  -e GROQ_API_KEY=your_key \
  -e UNSUBSCRIBE_SECRET=your_secret \
  -e LOG_LEVEL=INFO \
  -e TIMEZONE=America/Los_Angeles \
  campaign-runner
```

#### Run with Restart Policy (Production)
```bash
docker run -d \
  --name campaign-runner \
  --restart unless-stopped \
  --env-file .env \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  campaign-runner
```

### Container Management

```bash
# View logs
docker logs -f campaign-runner

# Stop container
docker stop campaign-runner

# Start container
docker start campaign-runner

# Restart container
docker restart campaign-runner

# View container status
docker ps --filter name=campaign-runner
```

