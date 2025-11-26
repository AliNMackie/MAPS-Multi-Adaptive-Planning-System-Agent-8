from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from src.core.security import current_tenant
import logging

logger = logging.getLogger(__name__)

class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to ensure tenant context is clean for each request.
    While `tenant_scoped` handles setting the context for specific routes,
    this middleware provides a safety net and logging.
    """
    async def dispatch(self, request: Request, call_next):
        # Reset context variable to ensure no leakage from previous requests in the same thread/task
        # In standard asyncio/FastAPI, contextvars are properly managed, but explicit reset or initialization is good practice.
        token = current_tenant.set(None)
        
        try:
            # We could attempt to extract tenant info here for logging, 
            # but auth is handled by the `tenant_scoped` decorator or other dependencies.
            
            response = await call_next(request)
            return response
        finally:
            # Ensure context is reset after request
            current_tenant.reset(token)
