"""General helper utility functions."""

import random
import re
import secrets
import string
import unicodedata
from datetime import datetime, timezone
from typing import Optional


def generate_random_string(length: int = 32) -> str:
    """Generate a cryptographically secure random alphanumeric string.

    Args:
        length: Length of the string to generate (default: 32).

    Returns:
        Random alphanumeric string.
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_random_token(length: int = 64) -> str:
    """Generate a URL-safe random token.

    Args:
        length: Length of the token (default: 64).

    Returns:
        URL-safe random token string.
    """
    return secrets.token_urlsafe(length)


def generate_numeric_code(length: int = 6) -> str:
    """Generate a random numeric code (e.g., OTP).

    Args:
        length: Number of digits (default: 6).

    Returns:
        Random numeric string.
    """
    return "".join(secrets.choice(string.digits) for _ in range(length))


def slugify(text: str, max_length: int = 100) -> str:
    """Convert text to URL-friendly slug.

    Steps:
    1. Normalize unicode characters
    2. Convert to lowercase
    3. Replace non-alphanumeric with hyphens
    4. Collapse multiple hyphens
    5. Strip leading/trailing hyphens
    6. Truncate to max_length

    Args:
        text: Input text to slugify.
        max_length: Maximum slug length (default: 100).

    Returns:
        URL-friendly slug string.
    """
    if not text:
        return ""

    # Normalize unicode (NFKD decomposition)
    text = unicodedata.normalize("NFKD", text)
    # Encode to ASCII, ignoring non-ASCII chars
    text = text.encode("ascii", "ignore").decode("ascii")
    # Lowercase
    text = text.lower().strip()
    # Replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Collapse multiple hyphens
    text = re.sub(r"-+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    # Truncate
    if len(text) > max_length:
        text = text[:max_length].rsplit("-", 1)[0]

    return text


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to max_length with suffix.

    Args:
        text: Input text.
        max_length: Maximum length including suffix.
        suffix: Suffix to append when truncated.

    Returns:
        Truncated text.
    """
    if not text or len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)].rstrip() + suffix


def now_utc() -> datetime:
    """Get current UTC datetime with timezone info."""
    return datetime.now(timezone.utc)


def to_iso_format(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to ISO 8601 format string.

    Args:
        dt: Datetime object or None.

    Returns:
        ISO 8601 string or None.
    """
    if dt is None:
        return None
    return dt.isoformat()


def from_iso_format(iso_string: str) -> datetime:
    """Parse ISO 8601 format string to datetime.

    Args:
        iso_string: ISO 8601 datetime string.

    Returns:
        Parsed datetime object.
    """
    return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))


def format_datetime(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M:%S") -> Optional[str]:
    """Format datetime with custom format string.

    Args:
        dt: Datetime object or None.
        fmt: Format string (default: Y-m-d H:M:S).

    Returns:
        Formatted string or None.
    """
    if dt is None:
        return None
    return dt.strftime(fmt)


def time_elapsed_since(dt: datetime) -> str:
    """Get human-readable elapsed time since a datetime.

    Args:
        dt: Past datetime.

    Returns:
        Human-readable string like '2 hours ago', '3 days ago'.
    """
    now = now_utc()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = now - dt
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif seconds < 604800:
        days = seconds // 86400
        return f"{days} day{'s' if days > 1 else ''} ago"
    elif seconds < 2592000:
        weeks = seconds // 604800
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    else:
        months = seconds // 2592000
        return f"{months} month{'s' if months > 1 else ''} ago"


def mask_email(email: str) -> str:
    """Mask an email address for display (e.g., j***@example.com).

    Args:
        email: Full email address.

    Returns:
        Masked email.
    """
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def mask_string(value: str, visible_chars: int = 4) -> str:
    """Mask a string showing only first and last visible_chars.

    Args:
        value: String to mask.
        visible_chars: Number of visible characters at start and end.

    Returns:
        Masked string.
    """
    if len(value) <= visible_chars * 2:
        return "*" * len(value)
    return value[:visible_chars] + "*" * (len(value) - visible_chars * 2) + value[-visible_chars:]
