"""Authentication middleware for API routes."""

from fastapi import HTTPException, Depends, Header
from typing import Optional
import base64
from shared.db import get_supabase_admin


async def verify_admin(
    authorization: Optional[str] = Header(None)
) -> dict:
    """Verify admin user from Authorization header.
    
    Expects Basic auth: Authorization: Basic base64(email:password)
    
    Args:
        authorization: Authorization header value
        
    Returns:
        Admin user dict with id, email, role
        
    Raises:
        HTTPException: If authentication fails
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    if not authorization.startswith("Basic "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    try:
        encoded = authorization.split(" ", 1)[1]
        decoded = base64.b64decode(encoded).decode("utf-8")
        email, password = decoded.split(":", 1)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    supabase = get_supabase_admin()
    response = supabase.table("admin_users").select("id, email, password, role").eq("email", email).single().execute()
    
    if not response.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if response.data["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "id": response.data["id"],
        "email": response.data["email"],
        "role": response.data["role"]
    }

