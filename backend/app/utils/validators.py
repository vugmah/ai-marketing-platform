"""Validation utilities for email, password, and phone number."""

import re
from datetime import datetime

from app.exceptions import ValidationError

# Email validation regex (RFC 5322 compliant subset)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)

# Password must contain at least 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char
PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_#^+=\-~.,:;|])[A-Za-z\d@$!%*?&_#^+=\-~.,:;|]{8,}$"
)

# International phone number regex (E.164 format)
PHONE_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")


def validate_email(email: str) -> str:
    """Validate an email address.

    Args:
        email: The email address to validate.

    Returns:
        The validated email address (lowercased).

    Raises:
        ValidationError: If the email format is invalid.
    """
    if not email or not isinstance(email, str):
        raise ValidationError(detail="Email is required")

    email = email.strip().lower()

    if len(email) > 254:
        raise ValidationError(detail="Email address is too long (max 254 characters)")

    if not EMAIL_REGEX.match(email):
        raise ValidationError(detail=f"Invalid email format: {email}")

    return email


def validate_password(password: str) -> str:
    """Validate password strength.

    Args:
        password: The password to validate.

    Returns:
        The validated password.

    Raises:
        ValidationError: If the password does not meet strength requirements.
    """
    if not password or not isinstance(password, str):
        raise ValidationError(detail="Password is required")

    if len(password) < 8:
        raise ValidationError(detail="Password must be at least 8 characters long")

    if len(password) > 128:
        raise ValidationError(detail="Password must not exceed 128 characters")

    if not PASSWORD_REGEX.match(password):
        raise ValidationError(
            detail=(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, one digit, and one special character"
            )
        )

    return password


def validate_phone_number(phone: str) -> str:
    """Validate a phone number in E.164 format.

    Args:
        phone: The phone number to validate.

    Returns:
        The validated phone number.

    Raises:
        ValidationError: If the phone number format is invalid.
    """
    if not phone or not isinstance(phone, str):
        raise ValidationError(detail="Phone number is required")

    phone = phone.strip()

    if not phone.startswith("+"):
        raise ValidationError(detail="Phone number must start with '+' (E.164 format)")

    if not PHONE_REGEX.match(phone):
        raise ValidationError(
            detail=f"Invalid phone number format: {phone}. Expected E.164 format (+1234567890)"
        )

    return phone


def validate_non_empty_string(value: str, field_name: str = "Field") -> str:
    """Validate that a string is non-empty after stripping.

    Args:
        value: The string to validate.
        field_name: Name of the field for error messages.

    Returns:
        The stripped string.

    Raises:
        ValidationError: If the string is empty.
    """
    if not value or not isinstance(value, str) or not value.strip():
        raise ValidationError(detail=f"{field_name} cannot be empty")
    return value.strip()


def validate_date_range(
    start_date: datetime,
    end_date: datetime,
    max_days: int = 365,
) -> None:
    """Validate a date range.

    Args:
        start_date: Start of the range.
        end_date: End of the range.
        max_days: Maximum allowed range in days.

    Raises:
        ValidationError: If the date range is invalid.
    """
    if start_date > end_date:
        raise ValidationError(detail="Start date must be before end date")

    delta = (end_date - start_date).days
    if delta > max_days:
        raise ValidationError(
            detail=f"Date range cannot exceed {max_days} days (got {delta} days)"
        )
