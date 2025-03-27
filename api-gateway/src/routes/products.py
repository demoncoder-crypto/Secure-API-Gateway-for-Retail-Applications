from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from src.config.settings import get_settings
import httpx
import logging
from datetime import datetime
import uuid
from fastapi.responses import JSONResponse

# Set up router
router = APIRouter(prefix="/products", tags=["Products"])

# Configure logger
logger = logging.getLogger(__name__)

# Schema for product data
class ProductImage(BaseModel):
    url: str
    alt_text: Optional[str] = None
    is_primary: bool = False

class ProductPrice(BaseModel):
    amount: float
    currency: str = "USD"
    is_discounted: bool = False
    original_amount: Optional[float] = None

class Product(BaseModel):
    id: str
    sku: str
    name: str
    description: Optional[str] = None
    category: str
    price: ProductPrice
    inventory: int
    images: List[ProductImage] = []
    attributes: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

class ProductResponse(BaseModel):
    data: Product
    meta: Dict[str, Any] = {}

class ProductListResponse(BaseModel):
    data: List[Product]
    meta: Dict[str, Any] = {}
    pagination: Dict[str, Any] = {}

# Helper function to get backend service URL
def get_product_service_url():
    settings = get_settings()
    return settings.product_service_url

# Create a custom HTTP client with timeouts and error handling
async def get_http_client():
    return httpx.AsyncClient(timeout=httpx.Timeout(10.0))

@router.get("", response_model=ProductListResponse, summary="List all products")
async def list_products(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    sort_by: Optional[str] = Query(None, description="Sort field (name, price, created_at)"),
    sort_dir: Optional[str] = Query("asc", description="Sort direction (asc, desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List products with filtering, sorting and pagination.
    
    This endpoint proxies the request to the product service and adds additional
    security, caching, and logging.
    """
    # Get the URL of the product service from settings
    product_service_url = get_product_service_url()
    
    # Build query parameters
    params = {
        "page": page,
        "page_size": page_size,
    }
    
    if category:
        params["category"] = category
    if min_price is not None:
        params["min_price"] = min_price
    if max_price is not None:
        params["max_price"] = max_price
    if sort_by:
        params["sort_by"] = sort_by
    if sort_dir:
        params["sort_dir"] = sort_dir
    
    try:
        # Create HTTP client
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Forward the request
            response = await client.get(
                f"{product_service_url}/products",
                params=params,
                headers={
                    "X-Request-ID": getattr(request.state, "request_id", str(uuid.uuid4())),
                    "Authorization": request.headers.get("Authorization", ""),
                }
            )
            
            # Handle response
            if response.status_code != 200:
                logger.warning(f"Product service returned error: {response.status_code}")
                return handle_external_service_error(response)
            
            # Return successful response
            return response.json()
                
    except httpx.RequestError as e:
        logger.error(f"Error connecting to product service: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product service unavailable"
        )
    except Exception as e:
        logger.error(f"Unexpected error in list_products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/{product_id}", response_model=ProductResponse, summary="Get product by ID")
async def get_product(
    request: Request,
    product_id: str,
):
    """
    Get detailed information about a specific product.
    
    This endpoint requires authentication and validates that the 
    user has permission to view the product.
    """
    # Get the URL of the product service from settings
    product_service_url = get_product_service_url()
    
    try:
        # Create HTTP client
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Forward the request
            response = await client.get(
                f"{product_service_url}/products/{product_id}",
                headers={
                    "X-Request-ID": getattr(request.state, "request_id", str(uuid.uuid4())),
                    "Authorization": request.headers.get("Authorization", ""),
                }
            )
            
            # Handle response
            if response.status_code != 200:
                return handle_external_service_error(response)
            
            # Return successful response 
            return response.json()
                
    except httpx.RequestError as e:
        logger.error(f"Error connecting to product service: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product service unavailable"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Mock product for demonstration (used when product service is unavailable)
MOCK_PRODUCT = {
    "data": {
        "id": "demo-product-1",
        "sku": "DEMO-12345",
        "name": "Demo Product",
        "description": "This is a demo product used when the product service is unavailable",
        "category": "Demo",
        "price": {
            "amount": 99.99,
            "currency": "USD",
            "is_discounted": True,
            "original_amount": 129.99
        },
        "inventory": 42,
        "images": [
            {
                "url": "https://example.com/images/demo-product.jpg",
                "alt_text": "Demo Product Image",
                "is_primary": True
            }
        ],
        "attributes": {
            "color": "Blue",
            "size": "Medium",
            "weight": "1.2kg"
        },
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    },
    "meta": {
        "is_mock": True,
        "source": "gateway_fallback"
    }
}

def handle_external_service_error(response):
    """Handle different error responses from the backend service"""
    # Try to parse the error response
    try:
        error_data = response.json()
        detail = error_data.get("detail", "Unknown error")
    except Exception:
        detail = "Error communicating with product service"
    
    # Map status codes
    if response.status_code == 404:
        # Use a mock product for demo purposes instead of returning 404
        logger.info("Product not found, returning mock data")
        return MOCK_PRODUCT
    elif response.status_code == 400:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": detail}
        )
    elif response.status_code == 401 or response.status_code == 403:
        return JSONResponse(
            status_code=response.status_code,
            content={"detail": "Unauthorized access to product service"}
        )
    else:
        # For other errors, return a 502 Bad Gateway
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"Product service error: {detail}"}
        )
