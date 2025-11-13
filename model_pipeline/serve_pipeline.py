"""Vertex AI serving pipeline."""

from kfp import dsl
from google_cloud_pipeline_components.v1.endpoint import EndpointCreateOp, ModelDeployOp
from google_cloud_pipeline_components.v1.model import ModelUploadOp

@dsl.pipeline(
    name="serving-pipeline",
    description="A simple serving pipeline.",
)
def pipeline(
    project_id: str,
    location: str,
    model_display_name: str,
    endpoint_display_name: str,
):
    """Defines the serving pipeline."""

    # 1. Get the model from Vertex AI Model Registry
    model_op = dsl.importer(
        artifact_uri=f"aiplatform://{project_id}-{location}-models/{model_display_name}",
        artifact_class=dsl.Artifact,
        reimport=True,
    )

    # 2. Create an endpoint
    endpoint_op = EndpointCreateOp(
        project=project_id,
        display_name=endpoint_display_name,
    ).set_display_name("Create Endpoint")

    # 3. Deploy the model to the endpoint
    ModelDeployOp(
        model=model_op.outputs["artifact"],
        endpoint=endpoint_op.outputs["endpoint"],
        dedicated_resources_machine_type="n1-standard-4",
        dedicated_resources_min_replica_count=1,
        dedicated_resources_max_replica_count=1,
    ).set_display_name("Deploy Model")

if __name__ == "__main__":
    from kfp.compiler import Compiler
    Compiler().compile(
        pipeline_func=pipeline,
        package_path="serving_pipeline.json"
    )
