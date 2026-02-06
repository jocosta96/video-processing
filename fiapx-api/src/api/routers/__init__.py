from .auth import router as auth_router
from .videos import router as videos_router
from .jobs import router as jobs_router
from .health import router as health_router

__all__ = ["auth_router", "videos_router", "jobs_router", "health_router"]
