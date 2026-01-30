"""Rate limiting using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from ..config import get_settings


def get_real_ip(request) -> str:
    """Get client IP, checking X-Forwarded-For for reverse proxy setups."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in the list is the original client
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


settings = get_settings()

# Create limiter instance
# If rate limiting is disabled, use a very high limit effectively disabling it
limiter = Limiter(
    key_func=get_real_ip,
    default_limits=[settings.rate_limit] if settings.rate_limit_enabled else [],
    enabled=settings.rate_limit_enabled,
)
