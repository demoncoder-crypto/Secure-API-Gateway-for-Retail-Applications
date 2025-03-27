import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from src.config.settings import get_settings
from src.middleware.auth import AuthMiddleware
from src.middleware.rate_limiter import RateLimiterMiddleware
from src.middleware.logging import LoggingMiddleware
from src.routes import health, products
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Get application settings
settings = get_settings()

# Configure middleware
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    ),
    Middleware(LoggingMiddleware),
    Middleware(RateLimiterMiddleware, redis_url=settings.redis_url),
    Middleware(AuthMiddleware, exclude_paths=["/health", "/docs", "/redoc", "/openapi.json"]),
]

# Initialize FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A secure API gateway for retail applications",
    docs_url=None,  # We'll customize this below
    redoc_url=None,  # We'll customize this below
    openapi_url="/openapi.json" if settings.environment != "production" else None,
    middleware=middleware,
    debug=settings.debug,
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(products.router, tags=["Products"])

# Customize OpenAPI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.app_name,
        version=settings.app_version,
        description="A secure API gateway for retail applications with authentication, rate limiting, and monitoring",
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"] = openapi_schema.get("components", {})
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    
    # Add global security requirement
    openapi_schema["security"] = [{"bearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Custom docs endpoints
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{settings.app_name} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    from fastapi.openapi.docs import get_redoc_html
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{settings.app_name} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
    )

@app.get("/", include_in_schema=False)
async def root():
    """Root route that redirects to the docs"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

# Simple error handlers
@app.exception_handler(404)
async def not_found_exception_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found"}
    )

@app.exception_handler(500)
async def server_error_exception_handler(request, exc):
    logger.error(f"Internal server error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.app_name} v{settings.app_version} in {settings.environment} mode")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Shutting down {settings.app_name}")

# For direct running
if __name__ == "__main__":
    # Run server
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )