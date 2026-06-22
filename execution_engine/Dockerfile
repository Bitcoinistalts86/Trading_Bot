FROM python:3.11-slim
WORKDIR /app

# Build context is the repo root (see cloudbuild.yaml). Copy the shared
# libraries first so `from libraries.state...` resolves, then the engine.
COPY libraries/ ./libraries/
COPY execution_engine/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY execution_engine/ ./

EXPOSE 8080
# Railway (and Cloud Run) inject $PORT; bind it, default 8080 for local.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
