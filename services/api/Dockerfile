FROM python:3.13-slim

# Standard Python env vars
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

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

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
