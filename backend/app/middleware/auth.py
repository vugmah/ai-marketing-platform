"""Authentication middleware: validates JWT tokens from Authorization header."""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.auth.schemas import JWTPayload
from app.auth.utils import verify_token


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that validates JWT tokens and attaches user info to request state.

    Note: This middleware runs before route handlers. The actual user lookup
    should be done in the route-level dependency (get_current_user).
    This middleware only verifies the token signature and attaches the payload.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        auth_header = request.headers.get("Authorization", "")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            try:
                payload = verify_token(token)
                request.state.user = payload
            except Exception:
                # Token invalid - let the route handler deal with it
                request.state.user = None
        else:
            request.state.user = None

        response = await call_next(request)
        return response
