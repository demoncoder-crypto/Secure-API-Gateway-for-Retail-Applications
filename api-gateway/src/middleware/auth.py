from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from src.config.keycloak import verify_token, get_user_info
from src.config.settings import get_settings
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# Routes that don't require authentication
PUBLIC_ROUTES = [
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
]

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, 
        app, 
        oidc_url: str = None,
        exclude_paths: Optional[List[str]] = None
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or PUBLIC_ROUTES
        self.settings = get_settings()
        
    async def dispatch(self, request: Request, call_next):
        # Skip authentication for excluded paths
        path = request.url.path
        if any(path.startswith(route) for route in self.exclude_paths):
            return await call_next(request)
            
        # Get token from header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return self._unauthorized_response("Missing Authorization header")
            
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                return self._unauthorized_response("Invalid authentication scheme")
        except ValueError:
            return self._unauthorized_response("Invalid Authorization header format")
            
        try:
            # Verify token
            token_info = await verify_token(token)
            
            # Add user info to request state
            request.state.user = token_info
            request.state.token = token
            
            # Check for required scopes/roles if needed
            # This could be enhanced with path-specific role requirements
            if not self._has_required_permissions(request, token_info):
                return self._forbidden_response("Insufficient permissions")
                
            return await call_next(request)
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return self._unauthorized_response("Invalid or expired token")
            
    def _unauthorized_response(self, detail: str):
        """Return a 401 Unauthorized response"""
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": detail},
            headers={"WWW-Authenticate": "Bearer"}
        )
        
    def _forbidden_response(self, detail: str):
        """Return a 403 Forbidden response"""
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": detail}
        )
        
    def _has_required_permissions(self, request: Request, token_info: dict) -> bool:
        """
        Check if the user has the required permissions for this request.
        This can be enhanced to check specific roles per endpoint.
        """
        # Simple implementation - could be expanded with path-specific permissions
        # Example: check for 'retail-api' role
        realm_access = token_info.get("realm_access", {})
        roles = realm_access.get("roles", [])
        
        # For simplicity, we're just checking if the user has any role
        # This should be customized based on your authorization requirements
        return len(roles) > 0