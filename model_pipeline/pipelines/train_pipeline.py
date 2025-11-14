# model_pipeline/pipelines/train_pipeline.py
import kfp
from kfp.v2 import dsl
from kfp.v2.compiler import compiler
from google_cloud_pipeline_components import aiplatform as gcc_aip

@dsl.pipeline(
    name='price-prediction-train-pipeline',
    pipeline_root='gs://your-gcs-bucket/pipeline_root' # Replace with your GCS bucket
)
def pipeline(
    project: str,
    region: str,
    display_name: str,
    gcs_output_path: str,
    training_container_uri: str,
    table_name: str
):
    """Defines the training pipeline."""

    # Define the training component
    custom_job_op = gcc_aip.CustomContainerTrainingJobRunOp(
        display_name=display_name,
        container_uri=training_container_uri,
        model_serving_container_image_uri='us-docker.pkg.dev/vertex-ai/prediction/tf2-cpu.2-8:latest',
        project=project,
        location=region,
        staging_bucket=gcs_output_path,
        model_display_name=display_name,
        args=[
            f"--project-id={project}",
            f"--table-name={table_name}"
        ]
    )

    # Define the model upload component
    upload_op = gcc_aip.ModelUploadOp(
        project=project,
        display_name=display_name,
        unmanaged_container_model=custom_job_op.outputs["model"]
    )

    # Define the endpoint creation component
    endpoint_op = gcc_aip.EndpointCreateOp(
        project=project,
        display_name=display_name
    )

    # Define the model deployment component
    deploy_op = gcc_aip.ModelDeployOp(
        model=upload_op.outputs["model"],
        endpoint=endpoint_op.outputs["endpoint"],
        dedicated_resources_min_replica_count=1,
        dedicated_resources_max_replica_count=1,
        dedicated_resources_machine_type="n1-standard-2"
    )

if __name__ == '__main__':
    compiler.Compiler().compile(
        pipeline_func=pipeline,
        package_path='train_pipeline.json'
    )
