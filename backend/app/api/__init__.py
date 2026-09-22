"""API routes package"""
from app.api.auth import router as auth_router
from app.api.search import router as search_router
from app.api.feedback import router as feedback_router
from app.api.limits import router as limits_router

__all__ = ["auth_router", "search_router", "feedback_router", "limits_router"]
