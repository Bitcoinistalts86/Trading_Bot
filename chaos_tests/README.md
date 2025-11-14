# Chaos Testing Suite

This directory contains scripts for performing chaos engineering tests on the platform. These tests are designed to simulate various failure scenarios and verify that the system responds gracefully.

## Prerequisites

-   The platform must be deployed and running.
-   The required environment variables (e.g., `API_GATEWAY_URL`, `REDIS_HOST`) must be set.

## Running the Tests

Each test can be run as a standalone Python script:

```bash
python chaos_tests/test_redis_outage.py
```

```bash
python chaos_tests/test_model_server_timeout.py
```

## Available Tests

-   **`test_redis_outage.py`**: Simulates a Redis outage by activating the `HARD` kill-switch and verifying that the `api_gateway` rejects new orders.
-   **`test_model_server_timeout.py`**: (Conceptual) Simulates a timeout from the `model_gateway` and verifies that the `execution_engine` correctly flags the trade attempt.
