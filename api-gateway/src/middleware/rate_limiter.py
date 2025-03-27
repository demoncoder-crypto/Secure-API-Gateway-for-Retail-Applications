import redis
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from src.config.settings import get_settings
from typing import Dict, Optional, Callable

logger = logging.getLogger(__name__)

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, 
        app, 
        redis_url: str = None,
        default_limit: int = None,
        default_window: int = None,
        client_resolver: Optional[Callable[[Request], str]] = None
    ):
        super().__init__(app)
        settings = get_settings()
        
        self.redis_url = redis_url or settings.redis_url
        self.default_limit = default_limit or settings.rate_limit_per_minute
        self.default_window = default_window or settings.rate_limit_window_seconds
        
        # Client-specific rate limits
        self.client_limits: Dict[str, int] = {
            "admin": self.default_limit * 5,      # Admins get higher rate limits
            "service": self.default_limit * 10,    # Service-to-service gets even higher
            "anonymous": int(self.default_limit * 0.5)  # Anonymous gets lower
        }
        
        # Custom resolver for client identification
        self.client_resolver = client_resolver or self._default_client_resolver
        
        # Initialize Redis connection
        try:
            self.redis = redis.from_url(self.redis_url)
            # Test connection
            self.redis.ping()
            logger.info(f"Connected to Redis at {self.redis_url}")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Still create the middleware, but log the error
            # Consider implementing a fallback strategy
            self.redis = None
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting if Redis is not available
        if not self.redis:
            logger.warning("Rate limiting disabled - Redis unavailable")
            return await call_next(request)
            
        # Get client identifier and type
        client_id, client_type = await self.client_resolver(request)
        
        # Get appropriate rate limit for this client type
        limit = self.client_limits.get(client_type, self.default_limit)
        
        # Create Redis key
        key = f"rate_limit:{client_id}"
        window_key = f"{key}:window"
        
        try:
            # Get current count
            count = self.redis.get(key)
            count = int(count) if count else 0
            
            # Check if we need to create a new window
            if count == 0:
                current_time = int(time.time())
                window_expires = current_time + self.default_window
                
                pipeline = self.redis.pipeline()
                pipeline.set(key, 1)
                pipeline.expireat(key, window_expires)
                pipeline.set(window_key, window_expires)
                pipeline.expireat(window_key, window_expires)
                pipeline.execute()
                
                # Add rate limit headers
                response = await call_next(request)
                self._add_rate_limit_headers(response, 1, limit)
                return response
            else:
                # Increment and check
                count = self.redis.incr(key)
                window_expires = int(self.redis.get(window_key) or 0)
                
                # Check if exceeded
                if count > limit:
                    remaining_seconds = window_expires - int(time.time())
                    logger.warning(f"Rate limit exceeded for {client_id} ({client_type})")
                    
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": "Rate limit exceeded",
                            "reset_in_seconds": max(0, remaining_seconds)
                        },
                        headers={
                            "X-RateLimit-Limit": str(limit),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(window_expires),
                            "Retry-After": str(max(0, remaining_seconds))
                        }
                    )
                
                # Process the request
                response = await call_next(request)
                
                # Add rate limit headers
                self._add_rate_limit_headers(response, count, limit, window_expires)
                return response
                
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error during rate limiting: {e}")
            # Allow the request to proceed if Redis fails
            return await call_next(request)
        except Exception as e:
            logger.error(f"Unexpected error in rate limiter: {e}")
            return await call_next(request)
    
    def _add_rate_limit_headers(self, response, current: int, limit: int, reset: Optional[int] = None):
        """Add rate limit headers to the response"""
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current))
        
        if reset:
            response.headers["X-RateLimit-Reset"] = str(reset)
            reset_in = max(0, reset - int(time.time()))
            if reset_in > 0:
                response.headers["Retry-After"] = str(reset_in)
    
    async def _default_client_resolver(self, request: Request) -> tuple[str, str]:
        """
        Default client resolver that identifies clients based on:
        1. Token information (if authenticated)
        2. IP address (if not authenticated)
        
        Returns a tuple of (client_id, client_type)
        """
        # Check if authenticated
        if hasattr(request.state, "user"):
            # Use user ID or subject from the token
            user_info = request.state.user
            client_id = user_info.get("sub", "unknown")
            
            # Determine client type based on roles
            realm_access = user_info.get("realm_access", {})
            roles = realm_access.get("roles", [])
            
            if "admin" in roles:
                client_type = "admin"
            else:
                client_type = "authenticated"
        else:
            # Use client IP for unauthenticated requests
            client_ip = request.client.host
            client_id = f"ip:{client_ip}"
            client_type = "anonymous"
            
        return client_id, client_type