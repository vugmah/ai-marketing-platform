"""ERP sync module.

Exports the FastAPI router so the main application can mount it.
"""

from app.erp.router import router as erp_router

__all__ = ["erp_router"]
