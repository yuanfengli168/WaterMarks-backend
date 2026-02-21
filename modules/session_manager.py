"""
Session Manager - Handles user session identification
"""
import uuid
import secrets
from typing import Optional


def generate_session_id() -> str:
    """
    Generate a secure session ID.
    
    Returns:
        Unique session identifier
    """
    return secrets.token_urlsafe(32)


def get_or_create_session(session_id: Optional[str]) -> str:
    """
    Get existing session ID or create new one.
    
    Args:
        session_id: Existing session ID from cookie (if any)
        
    Returns:
        Valid session ID
    """
    if session_id and len(session_id) > 10:  # Basic validation
        return session_id
    return generate_session_id()
