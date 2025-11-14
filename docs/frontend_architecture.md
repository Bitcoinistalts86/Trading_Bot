# Frontend Architecture

This document outlines the architecture of the Next.js-based web frontend for the AI Trading Platform.

## Technology Stack

-   **Framework:** Next.js (with App Router)
-   **Language:** TypeScript
-   **Styling:** Tailwind CSS
-   **Deployment:** Containerized and deployed as a Cloud Run service.

## Component Structure

The frontend is organized into a modular structure of React components located in `frontend/src/components`.

-   **`FeaturePanel.tsx`:**
    -   Establishes a WebSocket connection to the `/ws/features` endpoint provided by the `api-gateway`.
    -   Listens for incoming feature messages and displays the latest data in a real-time panel.
    -   Shows the connection status (Connected/Disconnected).

-   **`OrderTicket.tsx`:**
    -   Provides a user interface for creating simple market buy/sell orders.
    -   Submits order requests to the `POST /api/order` endpoint on the `api-gateway`.
    -   Requires a valid JWT token for authentication (to be implemented).

-   **`KillSwitchControl.tsx`:**
    -   Displays the current status of the global kill-switch by polling the `GET /api/killswitch` endpoint.
    -   Allows authorized users to activate or deactivate the kill-switch by sending a request to the `POST /api/killswitch` endpoint.

## Deployment

The frontend is containerized using a multi-stage `Dockerfile`. The build stage compiles the Next.js application, and the production stage serves the optimized static and server-side rendered components. It is deployed as a public-facing Cloud Run service.

The WebSocket URL is injected as a build-time argument (`NEXT_PUBLIC_WEBSOCKET_URL`) in the `cloudbuild.yaml` file, allowing the frontend to connect to the correct `api-gateway` environment.
