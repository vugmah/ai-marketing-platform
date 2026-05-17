"""Custom exception classes and FastAPI exception handlers."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


# Backward-compatible alias for modules that import APIError
APIError = AppException


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        detail: str = "An application error occurred",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        self.detail = detail
        self.status_code = status_code
        super().__init__(self.detail)


class AuthenticationError(AppException):
    """Raised when authentication fails (invalid credentials, expired token, etc.)."""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationError(AppException):
    """Raised when user lacks permission for the requested resource."""

    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundError(AppException):
    """Raised when a requested resource is not found."""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class AlreadyExistsError(AppException):
    """Raised when attempting to create a resource that already exists."""

    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_409_CONFLICT,
        )


class ValidationError(AppException):
    """Raised when request data fails validation."""

    def __init__(self, detail: str = "Validation error"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class TenantError(AppException):
    """Raised when tenant/company identification fails."""

    def __init__(self, detail: str = "Tenant identification failed"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom AppException and its subclasses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle unhandled exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI application."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
