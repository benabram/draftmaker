"""Utility to sanitize sensitive information from error messages."""

import re
from typing import Any


def sanitize_error_message(error_message: Any) -> str:
    """
    Remove sensitive information from error messages before logging.
    
    Args:
        error_message: The original error message (string or exception)
        
    Returns:
        Sanitized error message
    """
    # Convert to string if it's an exception or other type
    if not isinstance(error_message, str):
        error_message = str(error_message)
    
    # Remove API keys and secrets from URLs
    # Pattern to match key=XXX or secret=XXX in URLs
    sanitized = re.sub(
        r'[?&](key|secret|token|api_key|apikey|password|auth|consumer_key|consumer_secret|client_id|client_secret)=[^&\s\'\"]+',
        r'&\1=***REDACTED***',
        error_message,
        flags=re.IGNORECASE
    )
    
    # Remove authorization headers
    sanitized = re.sub(
        r'(Authorization|Bearer|Token)[\s:]+[^\s\'\"]+',
        r'\1: ***REDACTED***',
        sanitized,
        flags=re.IGNORECASE
    )
    
    # Remove base64 encoded credentials
    sanitized = re.sub(
        r'Basic\s+[A-Za-z0-9+/]+=*',
        'Basic ***REDACTED***',
        sanitized
    )
    
    # Remove any Discogs-specific credentials
    sanitized = re.sub(
        r'Discogs\s+(key|secret)=[^,\s]+',
        r'Discogs \1=***REDACTED***',
        sanitized,
        flags=re.IGNORECASE
    )
    
    return sanitized
