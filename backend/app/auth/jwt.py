"""JWT Authentication exports

Re-exports from auth.service and auth.utils for backward compatibility.
"""
from app.auth.utils import (
    create_access_token,
    verify_token,
    decode_token_without_verification as decode_token,
)
from app.auth.service import get_current_user
from app.auth.schemas import UserResponse

# Optional user dependency (same as required for now)
get_current_user_optional = get_current_user
