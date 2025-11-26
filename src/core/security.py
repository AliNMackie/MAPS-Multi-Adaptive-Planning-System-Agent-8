import contextvars
from functools import wraps
from typing import Optional, Callable
from fastapi import Request, HTTPException, status
import firebase_admin
from firebase_admin import auth

# Global context variable for the current tenant
current_tenant: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_tenant", default=None)

class SecurityBreachError(Exception):
    """Raised when a severe security violation is detected (e.g. cross-tenant access attempt)."""
    pass

def tenant_scoped(func: Callable):
    """
    Decorator that enforces tenant isolation.
    It inspects the Authorization header, verifies the Firebase token,
    extracts the tenant_id, and sets it in the global context.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Inspect args/kwargs to find the Request object
        request: Optional[Request] = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        if not request:
            # Also check kwargs
            for key, value in kwargs.items():
                if isinstance(value, Request):
                    request = value
                    break
        
        if not request:
             raise HTTPException(status_code=500, detail="Request object not found in arguments. Ensure 'request: Request' is a parameter.")

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing or invalid Authorization header")

        token = auth_header.split(" ")[1]
        tenant_id = None

        try:
            # Verify the token
            decoded_token = auth.verify_id_token(token)
            tenant_id = decoded_token.get("tenant_id")

            if not tenant_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token missing tenant_id claim")
        except Exception as e:
            # Handle auth errors
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Authentication failed: {str(e)}")
            
        # Set the context variable and call the function
        token_reset = current_tenant.set(tenant_id)
        try:
            return await func(*args, **kwargs)
        finally:
            current_tenant.reset(token_reset)

    return wrapper
