"""Vertex AI training pipeline."""

from kfp import dsl
from kfp.compiler import Compiler

from google_cloud_pipeline_components.v1.bigquery import BigqueryQueryJobOp
from google_cloud_pipeline_components.v1.custom_job import CustomTrainingJobOp
from google_cloud_pipeline_components.v1.endpoint import EndpointCreateOp, ModelDeployOp
from google_cloud_pipeline_components.v1.model import ModelUploadOp


@dsl.pipeline(
    name="training-pipeline",
    description="A simple training pipeline.",
)
def pipeline(
    project_id: str,
    location: str,
    staging_bucket: str,
    display_name: str = "my-model",
):
    """Defines the training pipeline."""

    # 1. Get data from BigQuery
    get_data_op = BigqueryQueryJobOp(
        project=project_id,
        location=location,
        query=f"""
            SELECT *
            FROM `{project_id}.trading_ingest.features_ethusdt`
            LIMIT 1000
        """,
    ).set_display_name("Get Training Data")

    # 2. Train a model
    model_dir = f"{staging_bucket}/model"
    train_op = CustomTrainingJobOp(
        project=project_id,
        location=location,
        staging_bucket=staging_bucket,
        display_name="Train Model",
        worker_pool_specs=[
            {
                "machine_spec": {"machine_type": "n1-standard-4"},
                "replica_count": 1,
                "container_spec": {
                    "image_uri": "gcr.io/google-cloud/google-cloud-pipeline-components:latest",
                    "command": [
                        "python",
                        "-m",
                        "trainer.task",
                        "--train-data",
                        get_data_op.outputs["destination_table"],
                        "--model-dir",
                        model_dir,
                    ],
                },
            }
        ],
    ).set_display_name("Train Model")

    # 3. Upload the model to Vertex AI Model Registry
    upload_op = ModelUploadOp(
        project=project_id,
        display_name=display_name,
        artifact_uri=model_dir,
        serving_container_image_uri="gcr.io/google-cloud/google-cloud-pipeline-components:latest",
    ).after(train_op)

    # 4. Create an endpoint
    endpoint_op = EndpointCreateOp(
        project=project_id,
        display_name=f"{display_name}-endpoint",
    ).set_display_name("Create Endpoint")

    # 5. Deploy the model to the endpoint
    ModelDeployOp(
        model=upload_op.outputs["model"],
        endpoint=endpoint_op.outputs["endpoint"],
        dedicated_resources_machine_type="n1-standard-4",
        dedicated_resources_min_replica_count=1,
        dedicated_resources_max_replica_count=1,
    ).set_display_name("Deploy Model")


if __name__ == "__main__":
    Compiler().compile(pipeline_func=pipeline, package_path="training_pipeline.json")
