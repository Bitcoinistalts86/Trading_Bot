# Latency Budget

This document outlines the latency budget for the critical path of the trading platform, from market data ingress to order execution. The overall goal is to achieve a p95 latency of **< 100ms**.

| Component                 | Path                                     | Budget (p95) | Measurement Point                                   |
| ------------------------- | ---------------------------------------- | ------------ | --------------------------------------------------- |
| **1. Ingress**            | Exchange → Connector                     | 20ms         | Timestamp difference between exchange and connector. |
| **2. Data Pipeline**      | Connector → Pub/Sub → Features           | 15ms         | Pub/Sub publish time to feature service receive time. |
| **3. Feature Generation** | Raw Data → Feature Vector                | 15ms         | Time taken to compute all required features.          |
| **4. Model Inference**    | Feature Vector → Prediction              | 30ms         | Vertex AI Endpoint latency for a single prediction.   |
| **5. Execution Engine**   | Signal Received → Pre-trade Risk → Order | 15ms         | Time from signal ingestion to order placement.        |
| **6. Egress**             | Order → Exchange Confirmation            | 5ms          | Time from order placement to exchange ack.          |
| **Total**                 | **End-to-End**                           | **< 100ms**    |                                                     |

## Notes

-   These budgets are initial targets and will be refined based on performance testing.
-   Latency will be measured using distributed tracing (e.g., OpenTelemetry) to track the lifecycle of a message through the system.
-   The execution engine, being the most critical component, is written in Go to minimize overhead.
-   Model inference is allocated the largest budget, as complex models may require more time. Model optimization and hardware selection (e.g., GPUs) will be key to meeting this target.
