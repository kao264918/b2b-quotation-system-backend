"""
替代方案:自動偵測 HTTPS 來判斷生產環境

將這個函數替換到 auth.py 的 resolve_cookie_policy
"""

from fastapi import Request
from typing import Tuple


def resolve_cookie_policy(request: Request) -> Tuple[bool, str]:
    """
    Auto-detect production environment based on request protocol.
    
    HTTPS requests → SameSite=None; Secure (for cross-origin)
    HTTP requests → SameSite=lax (for local development)
    
    This approach doesn't rely on ENVIRONMENT variable.
    """
    is_https = request.url.scheme == "https"
    
    if is_https:
        # Production: HTTPS with cross-origin support
        return True, "none"
    else:
        # Development: HTTP with same-site only
        return False, "lax"
