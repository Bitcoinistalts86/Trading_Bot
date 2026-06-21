# execution_engine/main.py
"""
Compatibility shim.

The Dockerfile launches `uvicorn main:app`. The real engine now lives in the
`app` package (execution_engine/app/). This module simply re-exports it so the
existing container entrypoint keeps working after consolidation.
"""
from app.main import app  # noqa: F401
