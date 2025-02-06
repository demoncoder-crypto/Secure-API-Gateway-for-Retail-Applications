import redis
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str, limit=100, window=60):
        super().__init__(app)
        self.redis = redis.from_url(redis_url)
        self.limit = limit
        self.window = window

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"
        
        current = self.redis.incr(key)
        if current == 1:
            self.redis.expire(key, self.window)
        
        if current > self.limit:
            raise HTTPException(status_code=429, detail="Too many requests")
        
        return await call_next(request)