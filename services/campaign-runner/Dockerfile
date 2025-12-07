FROM python:3.11-slim

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
CMD ["uv", "run", "python", "main.py"]

