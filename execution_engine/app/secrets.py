# execution_engine/app/secrets.py
"""
Secret resolution.

Exchange API keys were read straight from environment variables, which is fine
for local dev but wrong for production (env shows up in process listings, crash
dumps, and image layers). This resolver pulls secrets from Google Secret Manager
when configured, and falls back to env otherwise — so local/dev keeps working
unchanged while production reads from a managed secret store.

Resolution order for each secret:
  1. Explicit resource override: env `${ENV_VAR}_SECRET_RESOURCE` containing a
     full resource name (`projects/P/secrets/NAME/versions/latest`). Highest
     precedence, lets you pin any secret/version.
  2. GCP convention: when `SECRETS_BACKEND=gcp` and a project is set, read
     `projects/{project}/secrets/{secret_id}/versions/latest`.
  3. Env fallback: `os.environ[ENV_VAR]`.

Secret *values* are never logged.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("execution_engine.secrets")


class SecretResolver:
    def __init__(self, project_id: str, backend: str = "env") -> None:
        self.project_id = project_id
        self.backend = (backend or "env").lower()
        self._client = None  # lazy SecretManagerServiceClient

    def get(self, env_var: str, secret_id: str | None = None, default: str = "") -> str:
        # 1. explicit per-secret resource override
        resource = os.environ.get(f"{env_var}_SECRET_RESOURCE")
        if resource:
            val = self._fetch(resource)
            if val is not None:
                return val

        # 2. GCP convention
        if self.backend == "gcp" and self.project_id and secret_id:
            val = self._fetch(f"projects/{self.project_id}/secrets/{secret_id}/versions/latest")
            if val is not None:
                return val

        # 3. environment fallback
        return os.environ.get(env_var, default)

    def _fetch(self, resource: str) -> str | None:
        """Return the secret payload, or None on any failure (caller falls back)."""
        try:
            from google.cloud import secretmanager
            if self._client is None:
                self._client = secretmanager.SecretManagerServiceClient()
            resp = self._client.access_secret_version(name=resource)
            return resp.payload.data.decode("utf-8")
        except Exception as exc:  # noqa: BLE001 -- never crash on secret fetch
            # Log the resource name and error class only — never the value.
            logger.warning("Secret fetch failed for %s (%s); falling back.", resource, type(exc).__name__)
            return None
