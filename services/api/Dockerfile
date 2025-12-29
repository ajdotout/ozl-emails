FROM python:3.13-slim

# Standard Python env vars
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create health check script
RUN echo '#!/usr/bin/env python3\n\
import requests\n\
import sys\n\
try:\n\
    response = requests.get("http://localhost:8000/health", timeout=5)\n\
    if response.status_code == 200:\n\
        print("Health check passed")\n\
        sys.exit(0)\n\
    else:\n\
        print(f"Health check failed: {response.status_code}")\n\
        sys.exit(1)\n\
except Exception as e:\n\
    print(f"Health check failed: {e}")\n\
    sys.exit(1)' > /usr/local/bin/healthcheck && chmod +x /usr/local/bin/healthcheck

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependencies
COPY pyproject.toml uv.lock ./

# Create venv and install dependencies
RUN uv sync --frozen --no-install-project

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy code and run
COPY . .

# Expose port 8000 for the API
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--env-file", ".env"]
