# libraries/observability/__init__.py
import logging
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def init_observability(service_name: str, app=None):
    """
    Initializes OpenTelemetry for tracing and logging.
    - Configures a TracerProvider.
    - Sets up a CloudTraceSpanExporter.
    - Instruments FastAPI and HTTPX.
    """
    # --- Tracing ---
    provider = TracerProvider()
    cloud_trace_exporter = CloudTraceSpanExporter()
    provider.add_span_processor(
        BatchSpanProcessor(cloud_trace_exporter)
    )
    trace.set_tracer_provider(provider)

    # Instrument FastAPI if an app is provided
    if app:
        FastAPIInstrumentor.instrument_app(app, service_name=service_name)

    # Instrument HTTPX for outgoing requests
    HTTPXClientInstrumentor().instrument()

    # --- Logging ---
    # Configure structured logging if needed
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Observability initialized for service: {service_name}")
