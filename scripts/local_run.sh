# Run connectors locally (assumes GOOGLE_APPLICATION_CREDENTIALS set)
export GOOGLE_CLOUD_PROJECT=your-project-id
export PUBSUB_TOPIC=market.binance.ethusdt
python connectors/binance-connector/app/main.py
