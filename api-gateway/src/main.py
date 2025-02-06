from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware
from src.config.settings import get_settings
from src.middleware.auth import AuthMiddleware
from src.middleware.rate_limiter import RateLimiterMiddleware
from src.middleware.logging import LoggingMiddleware
from src.routes import health, products


settings = get_settings()


app = FastAPI(
    title="Retail API Gateway",
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(LoggingMiddleware),
        Middleware(RateLimiterMiddleware, redis_url=settings.redis_url),
        Middleware(AuthMiddleware, oidc_url=settings.oidc_url)
    ]
)

app.include_router(health.router)
app.include_router(products.router)