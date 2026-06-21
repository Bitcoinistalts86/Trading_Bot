FROM python:3.11-slim
WORKDIR /app

# Build context is the repo root (see cloudbuild.yaml). Copy the shared
# libraries first so `from libraries.state...` resolves, then the engine.
COPY libraries/ ./libraries/
COPY execution_engine/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY execution_engine/ ./

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
