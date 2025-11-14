# Monitoring Plan for the Real-Time Feature Pipeline

This document outlines the monitoring strategy for the Dataflow-based real-time feature engine. The primary goal is to ensure the pipeline is healthy, processing data in a timely manner, and maintaining data quality.

## Monitoring Dashboard

All key metrics for the Dataflow job (`feature-engine-main`) are available in the **Google Cloud Monitoring** dashboard. A custom dashboard should be created to visualize the metrics listed below, filtered by the `job_name: feature-engine-main`.

## Key Metrics to Monitor

### 1. Pipeline Health & Freshness

These metrics indicate if the pipeline is running and processing data without significant delays.

*   **System Lag (seconds):** `job/system_lag`
    *   **Description:** The current maximum duration, in seconds, that an item of data has been processing or awaiting processing. This is the most critical metric for understanding pipeline health.
    *   **Alerting:** Set an alert if **System Lag > 300 seconds** for a sustained period (e.g., 5 minutes). A high lag indicates that the pipeline is falling behind and cannot keep up with the input data rate.
*   **Data Watermark Age (seconds):** `job/data_watermark_age`
    *   **Description:** The age of the data watermark. This represents the "freshness" of the data being processed.
    *   **Alerting:** Similar to System Lag, an alert should be triggered if the **Data Watermark Age > 300 seconds**.

### 2. Throughput & Backlog

These metrics help understand the volume of data being processed and identify potential bottlenecks.

*   **Elements Processed per Second:** `job/elements_processed_count` (aggregated per second)
    *   **Description:** The rate at which elements are being processed by the pipeline's transforms. This should be monitored for significant, unexplained drops, which could indicate an upstream issue (e.g., connectors are down) or an internal pipeline problem.
    *   **Alerting:** Set an alert for a sudden, sustained drop of **> 50%** from the baseline average.
*   **Estimated Backlog (bytes):** `job/backlog_bytes`
    *   **Description:** The estimated size of the unprocessed data in the input Pub/Sub subscriptions. A continuously growing backlog is a clear sign that the pipeline is under-provisioned.
    *   **Alerting:** Set an alert if **Backlog Bytes** grows continuously for more than 15 minutes.

### 3. Data Quality & Errors

These metrics help identify issues with the data itself.

*   **Dead-Letter Count:** `topic/send_message_operation_count` (filtered by `topic_id: features.dead_letter`)
    *   **Description:** The number of messages published to the dead-letter topic. This represents the number of raw messages that failed to be parsed by the pipeline.
    *   **Alerting:** An alert should be triggered if the rate of dead-letter messages exceeds a certain threshold (e.g., **> 10 messages per minute**), as this indicates a potential schema change or a bug in the parsing logic.

## Viewing Metrics

1.  Navigate to the **Monitoring** section in the Google Cloud Console.
2.  Go to **Metrics Explorer**.
3.  Select the resource type `Cloud Dataflow Job`.
4.  Choose the desired metric (e.g., `System Lag`).
5.  Filter by `job_name` and select `feature-engine-main`.
6.  (Recommended) Save the chart to a custom dashboard named "AI Trading Platform - Feature Engine".

By monitoring these key metrics, we can ensure the real-time feature pipeline remains reliable and performant.
