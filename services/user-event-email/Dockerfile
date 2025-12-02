FROM python:3.13-slim

# 1. Standard Python env vars
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 2. Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 3. Copy dependencies
COPY pyproject.toml uv.lock ./

# 4. Create venv and install dependencies
RUN uv sync --frozen --no-install-project

# 5. Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH"

# 6. Copy code and run
COPY . .
CMD ["uv", "run", "python", "main.py"]


