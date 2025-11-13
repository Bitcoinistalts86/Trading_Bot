#!/bin/bash
set -e
PROJECT=${PROJECT_ID:-$(gcloud config get-value project)}
cd infra/terraform
terraform init
terraform apply -auto-approve -var="project_id=${PROJECT}"
