"""Health check module for the AI Marketing Platform.

Provides health check endpoints, Prometheus metrics, structured logging,
and monitoring middleware for the application.
"""

from app.health.router import router

__all__ = ["router"]
