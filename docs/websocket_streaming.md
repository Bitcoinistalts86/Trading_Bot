# WebSocket Streaming Architecture

This document describes the architecture of the real-time WebSocket streaming service, which is responsible for delivering computed features from the backend to the frontend UI.

## Architecture Flow

The streaming pipeline is designed to be scalable and decoupled, using Pub/Sub as a buffer between the feature generation and the client-facing gateway.

```mermaid
graph TD
    A[Dataflow Feature Pipeline] -- Publishes Features --> B(Pub/Sub Topic: features.realtime);
    B -- Pushes Messages --> C[API Gateway (Cloud Run)];
    subgraph API Gateway
        C -- Subscribes --> D[Pub/Sub Consumer];
        D -- Forwards Message --> E[WebSocket Connection Manager];
    end
    E -- Broadcasts to Clients --> F((Frontend UI Clients));
```

## Components

1.  **Dataflow Feature Pipeline:** The Apache Beam pipeline computes features in real-time and publishes the resulting feature vectors as JSON messages to the `features.realtime` Pub/Sub topic.

2.  **Pub/Sub (`features.realtime`):** This topic acts as a durable, scalable buffer. It decouples the feature pipeline from the `api-gateway`, allowing either component to be scaled or restarted independently without data loss.

3.  **API Gateway (`api-gateway`):** A FastAPI service running on Cloud Run that serves as the WebSocket gateway.
    *   **Pub/Sub Consumer:** A background task (`pubsub_consumer.py`) within the gateway creates a subscriber to the `features.realtime` topic.
    *   **WebSocket Endpoint (`/ws/features`):** The gateway exposes a WebSocket endpoint that frontend clients can connect to.
    *   **Connection Manager:** The `ConnectionManager` class keeps track of all active WebSocket client connections.

## Data Flow

1.  A new feature vector is published to `features.realtime` by the Dataflow job.
2.  Pub/Sub pushes the message to one of the `api-gateway`'s Pub/Sub subscribers.
3.  The subscriber's callback function receives the message.
4.  The callback forwards the message content to the `ConnectionManager`.
5.  The `ConnectionManager` iterates through its list of active WebSocket connections and broadcasts the message to every connected client.
6.  The frontend client receives the message and updates the UI.

This push-based, fan-out architecture ensures that features are delivered to the UI with minimal latency.
