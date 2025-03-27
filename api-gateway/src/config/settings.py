from pydantic import BaseSettings
from functools import lru_cache
from typing import List, Optional


class Settings(BaseSettings):
    """
    Application settings.
    
    All values can be overridden with environment variables:
    e.g., APP_ENVIRONMENT=production will set the environment to "production"
    """
    app_name: str = "Retail API Gateway"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    
    # CORS settings
    allowed_origins: List[str] = ["*"]
    
    # Redis
    redis_url: str = "redis://redis:6379/0"
    
    # Rate limiting
    rate_limit_per_minute: int = 100
    rate_limit_window_seconds: int = 60
    
    # Keycloak
    oidc_url: str = "http://keycloak:8080/auth"
    keycloak_realm: str = "retail"
    keycloak_client_id: str = "retail-gateway"
    keycloak_client_secret: str = "your-secret"
    
    # API endpoints
    product_service_url: str = "http://product-service:8001/api"
    order_service_url: str = "http://order-service:8002/api"
    user_service_url: str = "http://user-service:8003/api"
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings to improve performance.
    """
    return Settings()
