# execution_engine/app/sinks.py
"""
Output sinks: the immutable audit ledger (BigQuery) and the execution event
stream (Pub/Sub). Both degrade gracefully -- if GCP clients or config are
absent (local dev, tests), they log and no-op instead of crashing the engine.
"""
from __future__ import annotations

import json
import logging

from .config import Settings
from .models import Execution

logger = logging.getLogger("execution_engine.sinks")


class ExecutionSink:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._publisher = None
        self._topic_path = None
        self._bq = None
        self._init_pubsub()
        self._init_bq()

    def _init_pubsub(self) -> None:
        try:
            from google.cloud import pubsub_v1
            self._publisher = pubsub_v1.PublisherClient()
            self._topic_path = self._publisher.topic_path(
                self.settings.project_id, self.settings.executions_topic,
            )
            logger.info("Pub/Sub execution topic: %s", self._topic_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Pub/Sub unavailable; executions will not be published (%s).", exc)

    def _init_bq(self) -> None:
        if not self.settings.bq_trades_table:
            logger.info("BQ_TRADES_TABLE not set; audit ledger disabled.")
            return
        try:
            from google.cloud import bigquery
            self._bq = bigquery.Client()
            logger.info("BigQuery audit ledger: %s", self.settings.bq_trades_table)
        except Exception as exc:  # noqa: BLE001
            logger.warning("BigQuery unavailable; audit ledger disabled (%s).", exc)

    async def publish(self, ex: Execution) -> None:
        payload = ex.model_dump()
        if self._publisher and self._topic_path:
            try:
                self._publisher.publish(self._topic_path, json.dumps(payload).encode())
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to publish execution %s: %s", ex.execution_id, exc)
        self._audit(payload)

    def _audit(self, payload: dict) -> None:
        if not self._bq:
            return
        try:
            errors = self._bq.insert_rows_json(self.settings.bq_trades_table, [payload])
            if errors:
                logger.error("Audit ledger insert errors: %s", errors)
        except Exception as exc:  # noqa: BLE001
            logger.error("Audit ledger insert failed: %s", exc)
