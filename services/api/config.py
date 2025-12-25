"""Configuration for API service."""

import os
from typing import Optional
from dotenv import load_dotenv

# Load variables from a local .env file when running outside Docker.
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # SparkPost
    SPARKPOST_API_KEY: str = os.getenv("SPARKPOST_API_KEY", "")
    
    # AI
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # Secrets
    UNSUBSCRIBE_SECRET: str = os.getenv("UNSUBSCRIBE_SECRET", "")

    # Frontend
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Timezone for working hours (9am-5pm)
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Los_Angeles")

    # Disable working hours scheduling restrictions (9am-5pm)
    # When set to 'true', campaigns can run 24/7
    DISABLE_WORKING_HOURS: bool = os.getenv("DISABLE_WORKING_HOURS", "false").lower() == "true"

    # Scheduling
    WORKING_HOUR_START: int = int(os.getenv("WORKING_HOUR_START", "9"))
    WORKING_HOUR_END: int = int(os.getenv("WORKING_HOUR_END", "17"))
    INTERVAL_MINUTES: float = float(os.getenv("INTERVAL_MINUTES", "3.5"))
    JITTER_SECONDS_MAX: int = int(os.getenv("JITTER_SECONDS_MAX", "30"))

    @classmethod
    def validate(cls) -> None:
        """Validate that all required configuration variables are set."""
        if not cls.SUPABASE_URL:
            raise ValueError("SUPABASE_URL environment variable is required")
        if not cls.SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError(
                "SUPABASE_SERVICE_ROLE_KEY environment variable is required"
            )
        if not cls.SPARKPOST_API_KEY:
            raise ValueError("SPARKPOST_API_KEY environment variable is required")
        if not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY environment variable is required")
        if not cls.UNSUBSCRIBE_SECRET:
            raise ValueError("UNSUBSCRIBE_SECRET environment variable is required")

