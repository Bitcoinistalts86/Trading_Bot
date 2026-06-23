# auth_service/app/secrets.py
"""
Secret resolution for the auth service (JWT signing key).

Mirrors the execution engine's resolver: Google Secret Manager in production,
environment-variable fallback for local/dev. Secret values are never logged.

Resolution order:
  1. `${ENV_VAR}_SECRET_RESOURCE` -> a full Secret Manager resource name.
  2. `SECRETS_BACKEND=gcp` + `GOOGLE_CLOUD_PROJECT` -> the secret named `secret_id`.
  3. env fallback.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("auth_service.secrets")


def resolve_secret(env_var: str, secret_id: str, default: str = "") -> str:
    resource = os.environ.get(f"{env_var}_SECRET_RESOURCE")
    backend = os.environ.get("SECRETS_BACKEND", "env").lower()
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")

    if not resource and backend == "gcp" and project:
        resource = f"projects/{project}/secrets/{secret_id}/versions/latest"

    if resource:
        try:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            resp = client.access_secret_version(name=resource)
            return resp.payload.data.decode("utf-8")
        except Exception as exc:  # noqa: BLE001 -- never crash; fall back to env
            logger.warning("Secret fetch failed for %s (%s); using env.", resource, type(exc).__name__)

    return os.environ.get(env_var, default)
