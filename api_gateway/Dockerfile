# api_gateway/Dockerfile
FROM python:3.9-slim

WORKDIR /app

# --- Install app dependencies ---
COPY api_gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy shared libraries ---
COPY libraries/ ./libraries

# --- Copy app code ---
COPY api_gateway/app/ ./api_gateway/app/

# --- Run ---
CMD ["uvicorn", "api_gateway.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
