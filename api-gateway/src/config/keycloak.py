from keycloak import KeycloakOpenID
from src.config.settings import get_settings
from functools import lru_cache
from typing import Dict, Any, Optional


@lru_cache()
def get_keycloak_openid() -> KeycloakOpenID:
    """
    Returns a configured KeycloakOpenID client.
    
    Uses caching to avoid repeated initialization.
    """
    settings = get_settings()
    
    return KeycloakOpenID(
        server_url=settings.oidc_url,
        client_id=settings.keycloak_client_id,
        realm_name=settings.keycloak_realm,
        client_secret_key=settings.keycloak_client_secret
    )


async def get_public_key() -> str:
    """
    Retrieves the public key from Keycloak for token verification.
    """
    keycloak_client = get_keycloak_openid()
    return keycloak_client.public_key()


async def verify_token(token: str) -> Dict[str, Any]:
    """
    Verifies the JWT token and returns the decoded token information.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        The decoded token information
        
    Raises:
        Exception: If token validation fails
    """
    keycloak_client = get_keycloak_openid()
    return keycloak_client.decode_token(
        token,
        key=await get_public_key(),
        options={
            "verify_signature": True,
            "verify_aud": True,
            "verify_exp": True
        }
    )


async def get_user_info(token: str) -> Dict[str, Any]:
    """
    Gets user information using the provided token.
    
    Args:
        token: The access token
        
    Returns:
        User information
    """
    keycloak_client = get_keycloak_openid()
    return keycloak_client.userinfo(token)


async def introspect_token(token: str) -> Dict[str, Any]:
    """
    Performs token introspection to validate and get token metadata.
    
    Args:
        token: The token to introspect
        
    Returns:
        Token introspection data
    """
    keycloak_client = get_keycloak_openid()
    return keycloak_client.introspect(token)
