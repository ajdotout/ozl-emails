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
    SPARKPOST_API_KEY: Optional[str] = os.getenv("SPARKPOST_API_KEY")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

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

