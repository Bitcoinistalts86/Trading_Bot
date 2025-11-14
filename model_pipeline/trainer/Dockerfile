# model_pipeline/trainer/Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY task.py .

ENTRYPOINT ["python", "task.py"]
