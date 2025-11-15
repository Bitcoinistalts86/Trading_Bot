# libraries/auth/__init__.py
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from google.cloud import secretmanager
from pydantic import BaseModel

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
JWT_SECRET_ID = os.environ.get("JWT_SECRET_ID", "jwt-hmac-secret")
ALGORITHM = "HS256"

# --- Clients ---
secret_client = secretmanager.SecretManagerServiceClient()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login") # Point to the auth service login

# --- Helper Functions ---
def get_jwt_secret() -> str:
    """Fetches the JWT HMAC secret from Secret Manager."""
    name = f"projects/{PROJECT_ID}/secrets/{JWT_SECRET_ID}/versions/latest"
    response = secret_client.access_secret_version(name=name)
    return response.payload.data.decode("UTF-8")

SECRET_KEY = get_jwt_secret()

class TokenData(BaseModel):
    user_id: str | None = None
    role: str | None = None

async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Decodes the JWT and returns the user's data."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id, role=role)
    except JWTError:
        raise credentials_exception
    return token_data

async def get_current_admin_user(current_user: TokenData = Depends(get_current_user)):
    """Dependency to ensure the user is an admin."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_user
