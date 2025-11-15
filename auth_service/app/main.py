# auth_service/app/main.py
import os
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from google.cloud import bigquery, secretmanager
from passlib.context import CryptContext
from jose import JWTError, jwt
import uuid

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
JWT_SECRET_ID = os.environ.get("JWT_SECRET_ID", "jwt-hmac-secret")
BQ_DATASET_ID = os.environ.get("BQ_DATASET_ID", "users")
BQ_TABLE_ID = os.environ.get("BQ_TABLE_ID", "auth_accounts")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# --- Clients ---
app = FastAPI(title="Authentication Service")
bq_client = bigquery.Client()
secret_client = secretmanager.SecretManagerServiceClient()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Helper Functions ---
def get_jwt_secret() -> str:
    """Fetches the JWT HMAC secret from Secret Manager."""
    name = f"projects/{PROJECT_ID}/secrets/{JWT_SECRET_ID}/versions/latest"
    response = secret_client.access_secret_version(name=name)
    return response.payload.data.decode("UTF-8")

SECRET_KEY = get_jwt_secret()

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- Pydantic Models ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

# --- Endpoints ---
@app.post("/signup", response_model=Token)
async def signup(user: UserCreate):
    # Check if user already exists
    query = f"SELECT email FROM `{PROJECT_ID}.{BQ_DATASET_ID}.{BQ_TABLE_ID}` WHERE email = @email"
    job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("email", "STRING", user.email)])
    query_job = bq_client.query(query, job_config=job_config)
    if query_job.result().total_rows > 0:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash password
    hashed_password = pwd_context.hash(user.password)

    # Create new user in BigQuery
    user_id = str(uuid.uuid4())
    user_row = {
        "user_id": user_id,
        "email": user.email,
        "password_hash": hashed_password,
        "role": "USER", # Default role
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    errors = bq_client.insert_rows_json(f"{PROJECT_ID}.{BQ_DATASET_ID}.{BQ_TABLE_ID}", [user_row])
    if errors:
        raise HTTPException(status_code=500, detail="Could not create user.")

    # Generate tokens
    access_token = create_access_token(
        data={"sub": user_id, "role": "USER"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    # For simplicity, we'll use a simple refresh token for now
    refresh_token = create_access_token(data={"sub": user_id}, expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@app.post("/login", response_model=Token)
async def login(user: UserLogin):
    # Find user
    query = f"SELECT user_id, email, password_hash, role FROM `{PROJECT_ID}.{BQ_DATASET_ID}.{BQ_TABLE_ID}` WHERE email = @email"
    job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("email", "STRING", user.email)])
    query_job = bq_client.query(query, job_config=job_config)
    result = list(query_job.result())
    if not result:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    db_user = result[0]
    if not pwd_context.verify(user.password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    # Update last_login_at
    query = f"""
        UPDATE `{PROJECT_ID}.{BQ_DATASET_ID}.{BQ_TABLE_ID}`
        SET last_login_at = @last_login_at
        WHERE user_id = @user_id
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("last_login_at", "TIMESTAMP", datetime.now(timezone.utc).isoformat()),
        bigquery.ScalarQueryParameter("user_id", "STRING", db_user.user_id)
    ])
    bq_client.query(query, job_config=job_config).result()

    # Generate tokens
    access_token = create_access_token(
        data={"sub": db_user.user_id, "role": db_user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_access_token(data={"sub": db_user.user_id}, expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@app.post("/refresh", response_model=Token)
async def refresh(refresh_token: str):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # In a real implementation, we would check if the refresh token is revoked

    # Find user role
    query = f"SELECT role FROM `{PROJECT_ID}.{BQ_DATASET_ID}.{BQ_TABLE_ID}` WHERE user_id = @user_id"
    job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("user_id", "STRING", user_id)])
    query_job = bq_client.query(query, job_config=job_config)
    result = list(query_job.result())
    if not result:
        raise credentials_exception

    db_user = result[0]

    # Generate new tokens
    access_token = create_access_token(
        data={"sub": user_id, "role": db_user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    new_refresh_token = create_access_token(data={"sub": user_id}, expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

    return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
