# execution_engine/Dockerfile
FROM python:3.9-slim

WORKDIR /app

# --- Install shared library ---
# This assumes the 'libraries' directory is in the build context
COPY ../libraries /app/libraries
RUN pip install --no-cache-dir /app/libraries/state

# --- Install app dependencies ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy app code ---
COPY app/ ./app

# --- Run ---
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
