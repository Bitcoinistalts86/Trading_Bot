# Model Training Guide

This document provides an overview of the model training process, from creating a training pipeline to deploying a model to a Vertex AI Endpoint.

## How Training Works

The model training process is orchestrated by Vertex AI Pipelines. A training pipeline is defined as a series of components, with each component performing a specific task in the training workflow.

The core training pipeline is defined in `model_pipeline/train_pipeline.py`. It consists of the following steps:

1.  **Get Data:** A BigQuery job is executed to extract the training data from the `features_ethusdt` table.
2.  **Train Model:** A custom training job is launched to train a model on the extracted data. The training code is located in `model_pipeline/trainer/`.
3.  **Upload Model:** The trained model is uploaded to the Vertex AI Model Registry.
4.  **Create Endpoint:** A new Vertex AI Endpoint is created to serve the model.
5.  **Deploy Model:** The model is deployed to the endpoint.

## Running a Training Pipeline

To run a training pipeline, you first need to compile it to a JSON file. This can be done by running the pipeline script directly:

```bash
python model_pipeline/train_pipeline.py
```

This will create a `training_pipeline.json` file. You can then submit this file to Vertex AI Pipelines to run the pipeline.

## Continuous Retraining

The platform is designed for continuous retraining of models. A retraining pipeline can be triggered in one of two ways:

1.  **Manually:** A retraining pipeline can be triggered manually via the Cloud Console or the `gcloud` CLI.
2.  **Automatically:** A retraining pipeline can be triggered automatically by publishing a message to the `model.retrain.trigger` Pub/Sub topic. This is typically done by a monitoring system that detects model drift or performance degradation.

The `retraining_trigger` Cloud Run service provides a simple HTTP endpoint that can be used to publish a message to the retraining topic.
