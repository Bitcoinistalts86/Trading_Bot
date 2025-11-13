# Project Setup Guide

This document provides a step-by--step guide for setting up the AI Trading & Arbitrage Platform for both local development and a production environment on Google Cloud.

## Prerequisites

Before you begin, ensure you have the following tools installed:

-   **gcloud CLI:** [Installation Guide](https://cloud.google.com/sdk/docs/install)
-   **Terraform:** [Installation Guide](https://learn.hashicorp.com/tutorials/terraform/install-cli)
-   **Docker:** [Installation Guide](https://docs.docker.com/engine/install/)
-   **Node.js (v18+):** [Installation Guide](https://nodejs.org/en/download/)
-   **Python (v3.10+):** [Installation Guide](https://www.python.org/downloads/)
-   **Go (v1.20+):** [Installation Guide](https://go.dev/doc/install)
-   **Flutter SDK:** [Installation Guide](https://docs.flutter.dev/get-started/install)
-   **Protobuf Compiler (`protoc`):** [Installation Guide](https://grpc.io/docs/protoc-installation/)

## Local Development Setup

This setup is designed to run the core components of the platform on your local machine for development and testing.

### 1. Clone the Repository

```bash
git clone https://github.com/your-repo/trading-platform.git
cd trading-platform
```

### 2. Configure Google Cloud Authentication

Authenticate the gcloud CLI to your Google Cloud account. This is required for local services that interact with GCP (e.g., Pub/Sub, BigQuery).

```bash
gcloud auth application-default login
```

### 3. Set Up a Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies

```bash
# Web Frontend
cd frontend
npm install

# Mobile Frontend
cd ../mobile
flutter pub get
```

### 5. Compile Protobuf Contracts

```bash
cd contracts
protoc --python_out=. --go_out=. trading.proto
```

### 6. Run Services Locally

You can run each service in a separate terminal window.

```bash
# Data Pipeline (Example)
cd data_pipeline
python main.py

# Execution Engine (Example)
cd ../execution_engine
go run main.go

# API Gateway (Example)
cd ../api_gateway
uvicorn main:app --reload

# Web Frontend (Example)
cd ../frontend
npm run dev
```

## Production Environment Setup (Google Cloud)

This setup will provision the necessary infrastructure on Google Cloud and deploy the platform as a set of containerized services.

### 1. Configure GCP Project

Ensure you have a Google Cloud project created and the gcloud CLI is configured to use it.

```bash
gcloud config set project YOUR_PROJECT_ID
```

Enable the required APIs:

```bash
gcloud services enable \
  run.googleapis.com \
  iam.googleapis.com \
  pubsub.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  container.googleapis.com \
  aiplatform.googleapis.com
```

### 2. Set Up Terraform Backend

Configure a Cloud Storage bucket for the Terraform state backend.

```bash
gsutil mb gs://YOUR_TERRAFORM_STATE_BUCKET
```

Update `infra/main.tf` with your bucket name.

### 3. Provision Infrastructure with Terraform

Navigate to the `infra` directory and apply the Terraform configuration.

```bash
cd infra
terraform init
terraform apply
```

This will provision:
-   Cloud Run services
-   Pub/Sub topics
-   BigQuery datasets and tables
-   Cloud Storage buckets
-   IAM service accounts and permissions
-   Google Secret Manager for storing secrets

### 4. Create an Artifact Registry Repository

Create a Docker repository in Artifact Registry to store your container images.

```bash
gcloud artifacts repositories create docker-repo \
  --repository-format=docker \
  --location=us-central1
```

### 5. Configure CI/CD with Cloud Build

The `cloudbuild.yaml` file in the root of the repository is configured to build and deploy the services. You can trigger a build manually or connect it to your Git repository.

To run the build manually:

```bash
gcloud builds submit --config cloudbuild.yaml .
```

This will:
1.  Build a Docker image for each service.
2.  Push the images to Artifact Registry.
3.  Deploy the images to Cloud Run.

### 6. Verify the Deployment

Once the Cloud Build pipeline has completed, you can verify that the services are running correctly.

```bash
gcloud run services list --platform managed
```

You should see the `binance-connector` and `uniswap-connector` services listed. You can then access the web frontend via the URL provided by the Cloud Run service.
