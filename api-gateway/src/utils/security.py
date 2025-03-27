import hashlib
import hmac
import time
import secrets
import jwt
import logging
from typing import Dict, Any, Optional, List, Union
from src.config.settings import get_settings

# Set up logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY = 3600  # 1 hour in seconds

def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.
    
    Args:
        length: The length of the token in bytes
        
    Returns:
        A secure random token as a hex string
    """
    return secrets.token_hex(length)

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hash a password using a secure hashing algorithm.
    
    Args:
        password: The plaintext password to hash
        salt: Optional salt to use; if None, a new salt will be generated
        
    Returns:
        A tuple of (hashed_password, salt)
    """
    if salt is None:
        salt = secrets.token_hex(16)
    
    # Use PBKDF2 with SHA-256
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,  # Number of iterations
        64  # Key length
    ).hex()
    
    return key, salt

def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        password: The plaintext password to verify
        hashed_password: The stored hash to check against
        salt: The salt used in hashing
        
    Returns:
        True if the password matches, False otherwise
    """
    calculated_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(calculated_hash, hashed_password)

def create_jwt_token(
    subject: str,
    scopes: List[str] = None,
    expires_in: int = TOKEN_EXPIRY,
    additional_claims: Dict[str, Any] = None
) -> str:
    """
    Create a JWT token with the given claims.
    
    Args:
        subject: The subject of the token (usually a user ID)
        scopes: A list of scope strings for the token
        expires_in: Token expiry time in seconds
        additional_claims: Any additional claims to include
        
    Returns:
        A signed JWT token
    """
    settings = get_settings()
    
    now = int(time.time())
    token_data = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_in,
        "iss": settings.app_name,
    }
    
    if scopes:
        token_data["scope"] = " ".join(scopes)
    
    if additional_claims:
        token_data.update(additional_claims)
    
    # In a real application, you would use a proper secret key from settings
    secret_key = settings.keycloak_client_secret
    
    return jwt.encode(token_data, secret_key, algorithm=DEFAULT_JWT_ALGORITHM)

def decode_jwt(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: The JWT token to decode
        
    Returns:
        The decoded token payload
        
    Raises:
        jwt.InvalidTokenError: If the token is invalid
    """
    settings = get_settings()
    
    try:
        # In a real application, you would use a proper secret key from settings
        secret_key = settings.keycloak_client_secret
        
        return jwt.decode(
            token,
            secret_key,
            algorithms=[DEFAULT_JWT_ALGORITHM],
            options={"verify_signature": True}
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise

def sanitize_input(input_str: str) -> str:
    """
    Basic input sanitization to help prevent injection attacks.
    
    Args:
        input_str: The input string to sanitize
        
    Returns:
        Sanitized string
    """
    if not input_str:
        return ""
        
    # Simple sanitization - for production use a proper library
    dangerous_chars = ["<", ">", "&", '"', "'", ";", "`", "$", "(", ")", "{", "}", "\\"]
    result = input_str
    for char in dangerous_chars:
        result = result.replace(char, "")
        
    return result

def has_required_scope(
    token_scopes: Union[str, List[str]],
    required_scope: str
) -> bool:
    """
    Check if a token has the required scope.
    
    Args:
        token_scopes: Space-separated scope string or list of scopes
        required_scope: The scope to check for
        
    Returns:
        True if the token has the required scope, False otherwise
    """
    if isinstance(token_scopes, str):
        scopes = token_scopes.split()
    else:
        scopes = token_scopes
        
    return required_scope in scopes

def generate_api_key() -> str:
    """
    Generate a secure API key for service-to-service communication.
    
    Returns:
        A secure API key
    """
    prefix = "rtl"  # Prefix to identify the key type
    secret = secrets.token_urlsafe(32)
    return f"{prefix}_{secret}"
