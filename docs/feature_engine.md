# Feature Engine

This document describes the real-time feature engine, which is a streaming pipeline built with Apache Beam and Google Cloud Dataflow. The pipeline consumes raw market data from Pub/Sub, computes a variety of trading features, and publishes them to both a real-time Pub/Sub topic and a BigQuery table for historical analysis.

## Feature Definitions

The following features are computed by the pipeline:

### Market Microstructure Features

*   **mid_price:** The midpoint between the best bid and ask price.
*   **spread:** The difference between the best bid and ask price.
*   **signed_volume:** The volume of a trade multiplied by the trade direction (1 for buys, -1 for sells).

### Rolling Window Features

These features are computed over various time windows (1s, 5s, 30s) using stateful processing in Beam.

*   **volume\_(1s, 5s, 30s):** The total trading volume in the given time window.
*   **trade\_imbalance\_5s:** The difference between the volume of buy and sell trades in a 5-second window.
*   **volatility\_30s:** The standard deviation of price returns over a 30-second window.

## Limitations

*   **Mid-Price and Spread Calculation:** The current implementation sets the `mid_price` and `spread` features to `0.0`. This is because the Binance public trade stream (`@trade`) does not provide the best bid and ask prices required to calculate these features. To compute these accurately, the data ingestion connectors would need to be updated to subscribe to the order book feed (e.g., `@depth` or `@bookTicker` streams), which is a planned future enhancement.

## Dataflow Architecture

The pipeline is designed as a streaming job that runs continuously on Google Cloud Dataflow. It consists of the following steps:

1.  **Ingest:** Reads raw trade data from the `market.binance.raw` and `market.uniswap.raw` Pub/Sub topics.
2.  **Parse & Normalize:** Parses the JSON messages and normalizes them into a common internal format. Messages that fail to parse are sent to a dead-letter topic (`features.dead_letter`) for later inspection.
3.  **Window:** Groups the trades into 1-second fixed windows based on their event timestamps.
4.  **Compute Features:** A stateful `DoFn` computes the features for each instrument within the 1-second windows.
5.  **Output:** The computed features are written to two destinations in parallel:
    *   **Pub/Sub (`features.realtime`):** For consumption by downstream real-time services like the execution engine.
    *   **BigQuery (`features.features_intraday`):** For historical analysis, model training, and backtesting.

## Latency Objective

The end-to-end latency for a message, from the time it is published by a connector to the time the corresponding feature is published to the `features.realtime` topic, should be **less than 500 milliseconds**.

## Troubleshooting

*   **Stuck Jobs:** If the Dataflow job appears to be stuck (i.e., the watermark is not advancing), check the following:
    *   **Upstream Data:** Ensure that the connectors are running and publishing data to the input Pub/Sub topics.
    *   **Errors in Logs:** Check the Dataflow job logs for any errors that might be causing the pipeline to stall.
    *   **Scaling Issues:** The job may be under-provisioned. Consider increasing the number of workers or using a larger machine type.
*   **Schema Drift:** If the schema of the incoming data changes, the parsing logic in the pipeline may fail. This will cause messages to be sent to the dead-letter topic. To resolve this, you will need to update the parsing logic in the `transforms.py` file and redeploy the pipeline.
