import httpx
import logging
import time
import uuid
from typing import Dict, Any, Optional, Union, Callable
from fastapi import Request, HTTPException, status
from src.config.settings import get_settings

# Configure logger
logger = logging.getLogger(__name__)

class ServiceClient:
    """
    A client for making requests to backend services with metrics, retries,
    and error handling.
    """
    
    def __init__(
        self,
        service_name: str,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
        retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        """
        Initialize a new service client.
        
        Args:
            service_name: A name for the service (for logging)
            base_url: The base URL for the service
            timeout: The request timeout in seconds
            retries: The number of times to retry failed requests
            backoff_factor: The backoff factor for retries
        """
        self.service_name = service_name
        self._base_url = base_url
        self.timeout = timeout
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.settings = get_settings()
        
        # If base URL not provided, try to get it from settings
        if self._base_url is None:
            self._base_url = self._get_service_url_from_settings()
            
        logger.info(f"Initialized {service_name} client with base URL: {self._base_url}")
    
    def _get_service_url_from_settings(self) -> str:
        """Get service URL from settings based on service name"""
        settings = get_settings()
        service_key = f"{self.service_name.lower().replace('-', '_')}_service_url"
        
        # Try to get from settings
        if hasattr(settings, service_key):
            return getattr(settings, service_key)
        
        # Fallback to common services
        common_services = {
            "product": settings.product_service_url,
            "order": settings.order_service_url,
            "user": settings.user_service_url,
        }
        
        for key, url in common_services.items():
            if key in self.service_name.lower():
                return url
                
        # Default fallback
        logger.warning(f"No URL found for service {self.service_name}, using localhost")
        return f"http://localhost:8000/api"
    
    async def request(
        self,
        method: str,
        path: str,
        original_request: Optional[Request] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        error_handler: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Make a request to the service.
        
        Args:
            method: The HTTP method (GET, POST, etc.)
            path: The path to request (will be appended to base URL)
            original_request: The original FastAPI request (for headers forwarding)
            headers: Additional headers to include
            params: Query parameters
            json_data: JSON data to include in the body
            timeout: Custom timeout for this request
            error_handler: Custom error handler function
            
        Returns:
            The parsed JSON response
            
        Raises:
            HTTPException: If the request fails
        """
        url = f"{self._base_url.rstrip('/')}/{path.lstrip('/')}"
        request_id = str(uuid.uuid4())
        
        # Prepare headers
        request_headers = {}
        
        # Forward headers from original request if available
        if original_request:
            # Forward authorization
            auth_header = original_request.headers.get("Authorization")
            if auth_header:
                request_headers["Authorization"] = auth_header
                
            # Forward request ID or generate a new one
            request_headers["X-Request-ID"] = getattr(
                original_request.state, "request_id", request_id
            )
        else:
            request_headers["X-Request-ID"] = request_id
        
        # Add custom headers
        if headers:
            request_headers.update(headers)
        
        # Add service client identifier
        request_headers["X-Service-Client"] = self.service_name
        
        # Prepare timeout
        request_timeout = timeout or self.timeout
        
        # Start timing
        start_time = time.time()
        
        # Configure httpx client
        client_timeout = httpx.Timeout(request_timeout)
        
        try:
            logger.debug(
                f"Making {method} request to {url} with timeout {request_timeout}s - "
                f"Request ID: {request_headers.get('X-Request-ID')}"
            )
            
            # Create client and make request
            async with httpx.AsyncClient(timeout=client_timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    json=json_data,
                )
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Log request metrics
            logger.info(
                f"{self.service_name} {method} {path} completed in {response_time:.3f}s "
                f"with status {response.status_code} - "
                f"Request ID: {request_headers.get('X-Request-ID')}"
            )
            
            # Handle errors
            if response.status_code >= 400:
                if error_handler:
                    return error_handler(response)
                else:
                    return self._default_error_handler(response)
            
            # Parse and return JSON response
            return response.json()
            
        except httpx.RequestError as e:
            # Calculate response time
            response_time = time.time() - start_time
            
            logger.error(
                f"{self.service_name} {method} {path} failed after {response_time:.3f}s: {str(e)} - "
                f"Request ID: {request_headers.get('X-Request-ID')}"
            )
            
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{self.service_name} service unavailable: {str(e)}"
            )
        except Exception as e:
            # Calculate response time
            response_time = time.time() - start_time
            
            logger.error(
                f"Unexpected error in {self.service_name} {method} {path} "
                f"after {response_time:.3f}s: {str(e)} - "
                f"Request ID: {request_headers.get('X-Request-ID')}"
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error communicating with {self.service_name} service: {str(e)}"
            )
    
    async def get(self, path: str, **kwargs) -> Dict[str, Any]:
        """Make a GET request to the service"""
        return await self.request("GET", path, **kwargs)
    
    async def post(self, path: str, **kwargs) -> Dict[str, Any]:
        """Make a POST request to the service"""
        return await self.request("POST", path, **kwargs)
    
    async def put(self, path: str, **kwargs) -> Dict[str, Any]:
        """Make a PUT request to the service"""
        return await self.request("PUT", path, **kwargs)
    
    async def delete(self, path: str, **kwargs) -> Dict[str, Any]:
        """Make a DELETE request to the service"""
        return await self.request("DELETE", path, **kwargs)
    
    async def patch(self, path: str, **kwargs) -> Dict[str, Any]:
        """Make a PATCH request to the service"""
        return await self.request("PATCH", path, **kwargs)
    
    def _default_error_handler(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Default error handler for backend service errors.
        
        Args:
            response: The httpx Response object
            
        Raises:
            HTTPException: With appropriate status code and details
        """
        status_code = response.status_code
        
        # Try to parse error response
        try:
            error_data = response.json()
            detail = error_data.get("detail", "Unknown error")
        except Exception:
            detail = f"Error from {self.service_name} service"
        
        # Map status codes
        if status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail
            )
        elif status_code == 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail
            )
        elif status_code in (401, 403):
            raise HTTPException(
                status_code=status_code,
                detail=f"Unauthorized access to {self.service_name} service"
            )
        else:
            # For other errors, return a 502 Bad Gateway
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"{self.service_name} service error: {detail}"
            )
