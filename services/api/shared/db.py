"""Database operations for API service."""

from supabase import Client, create_client
from config import Config


def get_supabase_admin() -> Client:
    """Initialize and return Supabase admin client."""
    return create_client(
        Config.SUPABASE_URL,
        Config.SUPABASE_SERVICE_ROLE_KEY,
    )

