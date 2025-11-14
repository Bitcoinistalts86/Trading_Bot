# api_gateway/app/auth.py
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from google.cloud import secretmanager

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
SECRET_ID = "jwt-hmac-secret"
ALGORITHM = "HS256"

# --- Secret Manager Client ---
secret_client = secretmanager.SecretManagerServiceClient()

def get_jwt_secret() -> str:
    """Fetches the JWT HMAC secret from Secret Manager."""
    if not PROJECT_ID:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set for auth.")

    name = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}/versions/latest"
    try:
        response = secret_client.access_secret_version(name=name)
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        # In a real app, you'd want more robust error handling and perhaps a startup-time fetch
        raise HTTPException(status_code=500, detail="Could not retrieve JWT secret.") from e

SECRET_KEY = get_jwt_secret()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # Placeholder, we're not implementing a token endpoint

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Validates the JWT token and returns the user payload.
    This is a stub for a real authentication system.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        # In a real app, you would look up the user in a database
        return {"username": username}
    except JWTError:
        raise credentials_exception
