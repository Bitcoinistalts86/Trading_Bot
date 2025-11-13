CREATE OR REPLACE MODEL `PROJECT_ID.trading_models.bqml_move_predictor`
OPTIONS(model_type='logistic_reg', input_label_cols=['label'], auto_class_weights=TRUE) AS
SELECT
  CAST(label AS INT64) as label,
  vwap_1s, vwap_5s, orderflow_imbalance, bid_ask_spread
FROM `PROJECT_ID.trading_ingest.features_ethusdt`
WHERE DATE(ts) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND CURRENT_DATE();

-- Evaluate the model
SELECT
  *
FROM ML.EVALUATE(MODEL `PROJECT_ID.trading_models.bqml_move_predictor`,
  (SELECT vwap_1s, vwap_5s, orderflow_imbalance, bid_ask_spread, label FROM `PROJECT_ID.trading_ingest.features_ethusdt` LIMIT 10000))
