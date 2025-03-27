import time
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import redis
from src.config.settings import get_settings
import logging
import platform
import sys

# Set up router
router = APIRouter(prefix="/health", tags=["Health"])

# Configure logger
logger = logging.getLogger(__name__)

# Schema for health check response
class DependencyHealth(BaseModel):
    name: str
    status: str
    message: Optional[str] = None
    error: Optional[str] = None
    latency_ms: Optional[int] = None

class HealthResponse(BaseModel):
    status: str
    api_version: str
    environment: str
    timestamp: float
    uptime: float
    dependencies: List[DependencyHealth]
    system_info: Dict[str, Any]

# Track application start time
START_TIME = time.time()

@router.get("", response_model=HealthResponse, summary="Check API health")
async def health_check():
    """
    Health check endpoint that verifies:
    - API Gateway status
    - Redis connection
    - Uptime and environment information
    
    This endpoint is public and doesn't require authentication.
    """
    settings = get_settings()
    dependencies = []
    overall_status = "healthy"
    current_time = time.time()
    
    # Check Redis connection
    redis_status = await check_redis_connection(settings.redis_url)
    dependencies.append(redis_status)
    
    # If any dependency is not healthy, mark the overall status as degraded
    if any(d.status != "healthy" for d in dependencies):
        overall_status = "degraded"
    
    # If any critical dependency is not available, mark as unhealthy
    if any(d.status == "failing" for d in dependencies):
        overall_status = "unhealthy"
    
    # Basic system info
    system_info = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
        "cpu_count": platform.os.cpu_count(),
    }
    
    return HealthResponse(
        status=overall_status,
        api_version=settings.app_version,
        environment=settings.environment,
        timestamp=current_time,
        uptime=round(current_time - START_TIME, 2),
        dependencies=dependencies,
        system_info=system_info
    )

@router.get("/ping", summary="Simple ping endpoint")
async def ping():
    """
    A lightweight ping endpoint for use in basic health checks.
    Returns a simple JSON response with "pong" message.
    """
    return {"message": "pong", "timestamp": time.time()}

@router.get("/ready", summary="Readiness check")
async def readiness_check():
    """
    Checks if the service is ready to accept traffic.
    
    This is similar to the main health check but used specifically for readiness
    probes in container orchestration environments like Kubernetes.
    """
    settings = get_settings()
    
    # Check Redis connection - critical for rate limiting
    redis_status = await check_redis_connection(settings.redis_url)
    
    if redis_status.status != "healthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not ready - Redis connection failed"
        )
    
    return {"status": "ready", "timestamp": time.time()}

async def check_redis_connection(redis_url: str) -> DependencyHealth:
    """Test Redis connection and return its status"""
    try:
        start_time = time.time()
        # Try to connect to Redis
        redis_client = redis.from_url(redis_url)
        redis_client.ping()
        latency = int((time.time() - start_time) * 1000)
        
        return DependencyHealth(
            name="redis",
            status="healthy",
            message="Connection successful",
            latency_ms=latency
        )
    except redis.exceptions.ConnectionError as e:
        return DependencyHealth(
            name="redis",
            status="failing",
            error=f"Connection error: {str(e)}",
        )
    except Exception as e:
        return DependencyHealth(
            name="redis",
            status="degraded",
            error=f"Unexpected error: {str(e)}",
        )
