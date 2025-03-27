import time
import logging
import uuid
import json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from src.config.settings import get_settings
import traceback
from typing import Optional, Dict, Any

# Configure logger
logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, 
        app: ASGIApp,
        log_level: Optional[str] = None,
        exclude_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.settings = get_settings()
        self.log_level = log_level or self.settings.log_level
        
        # Paths to exclude from detailed logging (e.g., health checks)
        self.exclude_paths = exclude_paths or ["/health", "/metrics"]
        
    async def dispatch(self, request: Request, call_next):
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Extract basic request information
        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")
        
        # Skip detailed logging for excluded paths
        minimal_logging = any(path.startswith(excluded) for excluded in self.exclude_paths)
        
        # Log the incoming request
        if not minimal_logging:
            logger.info(f"Request started: {method} {path} - ID: {request_id}")
            
            # More detailed info at debug level
            logger.debug(
                f"Request details: {method} {path} - Client: {client_ip} - "
                f"User-Agent: {user_agent} - ID: {request_id}"
            )
        
        # Process request and catch exceptions
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Add response headers for tracking
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)
            
            # Log the response
            status_code = response.status_code
            if not minimal_logging or status_code >= 400:  # Always log errors
                log_method = logger.info if status_code < 400 else logger.warning
                log_method(
                    f"Request completed: {method} {path} - Status: {status_code} - "
                    f"Time: {process_time:.3f}s - ID: {request_id}"
                )
                
                # Log additional metrics for performance monitoring
                self._log_metrics(request, status_code, process_time)
            
            return response
            
        except Exception as e:
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log the exception
            logger.error(
                f"Request failed: {method} {path} - Error: {str(e)} - "
                f"Time: {process_time:.3f}s - ID: {request_id}"
            )
            
            # Log stack trace at debug level
            logger.debug(f"Exception traceback: {traceback.format_exc()}")
            
            # Re-raise the exception to be handled by FastAPI
            raise
            
    def _log_metrics(self, request: Request, status_code: int, process_time: float):
        """Log metrics in a format suitable for collection by monitoring systems"""
        user_id = getattr(request.state, "user", {}).get("sub", "anonymous")
        
        metrics = {
            "request_id": request.state.request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": status_code,
            "process_time_ms": int(process_time * 1000),
            "user_id": user_id,
            "timestamp": time.time(),
        }
        
        # Log in JSON format for easy parsing by log collectors
        logger.info(f"METRICS: {json.dumps(metrics)}")
