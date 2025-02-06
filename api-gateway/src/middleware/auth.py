from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from keycloak import KeycloakOpenID
from src.config.settings import get_settings
from src.utils.security import decode_jwt

class AuthMiddleware(HTTPBearer):
    def __init__(self, oidc_url: str):
        super().__init__(auto_error=True)
        self.oidc_client = KeycloakOpenID(
            server_url=oidc_url,
            client_id="retail-gateway",
            realm_name="retail",
            client_secret_key="your-secret"
        )

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        token = credentials.credentials
        
        try:
            
            userinfo = self.oidc_client.userinfo(token)
            request.state.user = userinfo
        except Exception as e:
            raise HTTPException(status_code=403, detail="Invalid token")
        
        return credentials