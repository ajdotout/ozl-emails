"""Configuration for campaign runner worker."""

import os
from typing import Optional

from dotenv import load_dotenv

# Load variables from a local .env file when running outside Docker.
# This looks for .env in the current working directory or its parents.
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # SparkPost
    SPARKPOST_API_KEY: str = os.getenv("SPARKPOST_API_KEY", "")
    # GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")  # Commented out - switched to Groq
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # Secrets
    UNSUBSCRIBE_SECRET: str = os.getenv("UNSUBSCRIBE_SECRET", "")


    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Timezone for working hours (9am-5pm)
    # Default: Asia/Kolkata (Mumbai)
    # Production: America/Los_Angeles (Pacific Time)
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")

    # Disable working hours scheduling restrictions (9am-5pm)
    # When set to 'true', campaigns can run 24/7
    DISABLE_WORKING_HOURS: bool = os.getenv("DISABLE_WORKING_HOURS", "false").lower() == "true"

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
        # if not cls.GEMINI_API_KEY:
        #     raise ValueError("GEMINI_API_KEY environment variable is required")  # Commented out - switched to Groq
        if not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY environment variable is required")
        if not cls.UNSUBSCRIBE_SECRET:
            raise ValueError("UNSUBSCRIBE_SECRET environment variable is required")

