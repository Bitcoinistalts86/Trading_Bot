-- ml/bqml/evaluate_baseline_model.sql

-- This script evaluates the baseline BQML model and stores the metrics
-- in a new table for tracking.

CREATE OR REPLACE TABLE `model_metrics.bqml_baseline` AS
SELECT
  *
FROM
  ML.EVALUATE(MODEL `features.price_direction_model_baseline`);
