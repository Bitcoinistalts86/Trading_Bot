-- ml/bqml/create_baseline_model.sql

-- This script creates a baseline logistic regression model in BigQuery ML
-- to predict the direction of the next 1-minute price movement.

CREATE OR REPLACE MODEL `features.price_direction_model_baseline`
OPTIONS(
  MODEL_TYPE='LOGISTIC_REG',
  INPUT_LABEL_COLS=['price_direction_1m']
) AS
SELECT
  -- Features: Use lagged feature values to predict the future
  LAG(mid_price, 1) OVER (PARTITION BY instrument ORDER BY timestamp) as prev_mid_price,
  LAG(volume_5s, 1) OVER (PARTITION BY instrument ORDER BY timestamp) as prev_volume_5s,
  LAG(trade_imbalance_5s, 1) OVER (PARTITION BY instrument ORDER BY timestamp) as prev_trade_imbalance_5s,
  LAG(volatility_30s, 1) OVER (PARTITION BY instrument ORDER BY timestamp) as prev_volatility_30s,

  -- Label: 1 if the price went up in the next minute, 0 otherwise
  CASE
    WHEN LEAD(mid_price, 60) OVER (PARTITION BY instrument ORDER BY timestamp) > mid_price THEN 1
    ELSE 0
  END AS price_direction_1m
FROM
  `features.features_intraday`
-- Limit to a recent time range for training
WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY);
