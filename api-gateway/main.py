#!/usr/bin/env python3
"""
Main entry point for the API Gateway.
This file is used to run the application directly with Python.
"""
import uvicorn
import logging
import sys
# Remove problematic import
# from src.config.settings import get_settings
import os
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import BaseModel
import httpx
import redis
import time
from prometheus_client import Counter, Histogram
from starlette_exporter import PrometheusMiddleware, handle_metrics
from typing import Optional, Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Retail API Gateway",
    description="Secure API Gateway for Retail Applications",
    version="1.0.0",
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add metrics middleware
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", handle_metrics)

# Initialize Redis client for rate limiting
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
        socket_timeout=1,  # Short timeout to avoid long waits
    )
    # Test connection
    redis_client.ping()
    logger.info("Successfully connected to Redis")
except redis.ConnectionError:
    logger.warning("Could not connect to Redis, rate limiting will be disabled")
    redis_client = None
except Exception as e:
    logger.error(f"Error connecting to Redis: {str(e)}")
    redis_client = None

# Initialize metrics
http_requests_total = Counter(
    "http_requests_total", "Total count of HTTP requests", ["method", "endpoint", "status"]
)
http_request_duration = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "endpoint"]
)

# Initialize OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Keycloak configuration
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080/auth")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "retail")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "retail-api-gateway")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "retail-api-gateway-secret")

# Product service URL
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:3000")

# Models
class TokenData(BaseModel):
    username: Optional[str] = None
    roles: Optional[list] = None


# Middleware for request timing and counting
@app.middleware("http")
async def add_metrics(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    endpoint = request.url.path
    method = request.method
    status_code = response.status_code
    
    http_requests_total.labels(method=method, endpoint=endpoint, status=status_code).inc()
    http_request_duration.labels(method=method, endpoint=endpoint).observe(duration)
    
    # Add request ID to response headers
    response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", "")
    
    return response


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting if Redis is not available
    if redis_client is None:
        return await call_next(request)
        
    try:
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"
        
        # Get current request count
        request_count = redis_client.get(key)
        if request_count is None:
            # Set initial count and expiry
            redis_client.set(key, 1, ex=60)  # 60 seconds window
        else:
            # Increment count
            redis_client.incr(key)
            request_count = int(request_count)
            
            # Check if rate limit exceeded
            if request_count > 100:  # 100 requests per minute
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded. Please try again later."}
                )
    except Exception as e:
        # If Redis fails, log and continue without rate limiting
        logger.error(f"Rate limiting error: {str(e)}")
    
    response = await call_next(request)
    return response


# Authentication functions
async def get_token_data(token: str = Depends(oauth2_scheme)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # In a production environment, you should verify the token with Keycloak
        # This is a simplified version
        payload = jwt.decode(token, "secret", algorithms=["HS256"])
        username = payload.get("sub")
        roles = payload.get("realm_access", {}).get("roles", [])
        
        if username is None:
            raise credentials_exception
            
        return TokenData(username=username, roles=roles)
    except JWTError:
        raise credentials_exception


# Role-based access control
def has_role(required_roles: list):
    async def role_checker(token_data: TokenData = Depends(get_token_data)):
        if not any(role in token_data.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return token_data
    return role_checker


# Health check endpoint
@app.get("/health/ping", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "api-gateway"}


# API routes
@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to Retail API Gateway", "version": "1.0.0"}


# Product API routes (proxied to product service)
@app.get("/api/products", tags=["Products"])
async def get_products(request: Request, token_data: TokenData = Depends(get_token_data)):
    """Get all products"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{PRODUCT_SERVICE_URL}/products")
            return response.json()
    except httpx.ConnectError:
        # Return mock data if product service is not available
        logger.warning("Product service unavailable, returning mock data")
        return {
            "data": [
                {
                    "id": "mock-1",
                    "name": "Mock Product",
                    "description": "This is a mock product for demonstration",
                    "price": 99.99,
                    "category": "Mock",
                    "inStock": True
                }
            ]
        }


@app.get("/api/products/{product_id}", tags=["Products"])
async def get_product(product_id: str, token_data: TokenData = Depends(get_token_data)):
    """Get a specific product by ID"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{PRODUCT_SERVICE_URL}/products/{product_id}")
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Product not found")
            return response.json()
    except httpx.ConnectError:
        # Return mock data if product service is not available
        logger.warning("Product service unavailable, returning mock data")
        return {
            "data": {
                "id": product_id,
                "name": "Mock Product",
                "description": "This is a mock product for demonstration",
                "price": 99.99,
                "category": "Mock",
                "inStock": True
            }
        }


@app.post("/api/products", tags=["Products"])
async def create_product(
    request: Request, 
    token_data: TokenData = Depends(has_role(["admin", "store_manager"]))
):
    """Create a new product (requires admin or store_manager role)"""
    try:
        payload = await request.json()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PRODUCT_SERVICE_URL}/products",
                json=payload
            )
            return response.json()
    except httpx.ConnectError:
        # Return mock successful response if product service is not available
        logger.warning("Product service unavailable, returning mock response")
        return {
            "data": {
                "id": "mock-new",
                "name": payload.get("name", "New Product"),
                "description": payload.get("description", ""),
                "price": payload.get("price", 0),
                "category": payload.get("category", ""),
                "inStock": True,
                "created": "2023-03-27T12:00:00Z"
            }
        }


@app.put("/api/products/{product_id}", tags=["Products"])
async def update_product(
    product_id: str,
    request: Request,
    token_data: TokenData = Depends(has_role(["admin", "store_manager"]))
):
    """Update a product (requires admin or store_manager role)"""
    try:
        payload = await request.json()
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{PRODUCT_SERVICE_URL}/products/{product_id}",
                json=payload
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Product not found")
            return response.json()
    except httpx.ConnectError:
        # Return mock successful response if product service is not available
        logger.warning("Product service unavailable, returning mock response")
        return {
            "data": {
                "id": product_id,
                "name": payload.get("name", "Updated Product"),
                "description": payload.get("description", ""),
                "price": payload.get("price", 0),
                "category": payload.get("category", ""),
                "inStock": True,
                "updated": "2023-03-27T12:00:00Z"
            }
        }


@app.delete("/api/products/{product_id}", tags=["Products"])
async def delete_product(
    product_id: str,
    token_data: TokenData = Depends(has_role(["admin"]))
):
    """Delete a product (requires admin role)"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{PRODUCT_SERVICE_URL}/products/{product_id}")
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Product not found")
            return {"message": "Product deleted successfully"}
    except httpx.ConnectError:
        # Return mock successful response if product service is not available
        logger.warning("Product service unavailable, returning mock response")
        return {"message": "Product deleted successfully (mock)"}


# Mock token endpoint (in production, this would redirect to Keycloak)
@app.post("/token", tags=["Authentication"])
async def login():
    # This is just a mock endpoint, in production you would use Keycloak
    return {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsIm5hbWUiOiJBZG1pbiBVc2VyIiwicmVhbG1fYWNjZXNzIjp7InJvbGVzIjpbImFkbWluIl19fQ.5BG9SEK-3c5tLG9-7KjqRVYONYU1DE3Y4hCNGSISmfk",
        "token_type": "bearer",
        "expires_in": 3600
    }


if __name__ == "__main__":
    # Log startup
    logger.info(f"Starting Retail API Gateway v1.0.0")
    logger.info(f"Environment: development")
    
    # Run the application
    host = "127.0.0.1"  # Use 127.0.0.1 instead of 0.0.0.0 for easier browser access
    port = 8000
    logger.info(f"API Gateway running at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port) 