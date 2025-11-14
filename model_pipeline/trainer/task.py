# model_pipeline/trainer/task.py
import argparse
import os
import tensorflow as tf
from google.cloud import bigquery
import pandas as pd
from sklearn.model_selection import train_test_split

def get_data(project_id, table_name):
    """Gets data from BigQuery."""
    client = bigquery.Client(project=project_id)
    query = f"""
        SELECT
            mid_price,
            volume_5s,
            trade_imbalance_5s,
            volatility_30s,
            -- Label
            CASE
                WHEN LEAD(mid_price, 60) OVER (PARTITION BY instrument ORDER BY timestamp) > mid_price THEN 1
                ELSE 0
            END AS price_direction_1m
        FROM
            `{table_name}`
        WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
        AND mid_price IS NOT NULL
        AND volume_5s IS NOT NULL
        AND trade_imbalance_5s IS NOT NULL
        AND volatility_30s IS NOT NULL
    """
    df = client.query(query).to_dataframe()
    df = df.dropna()
    return df

def create_model():
    """Creates a simple TensorFlow model."""
    model = tf.keras.models.Sequential([
        tf.keras.layers.Dense(16, activation='relu', input_shape=(4,)),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])
    model.compile(optimizer='adam',
                  loss='binary_crossentropy',
                  metrics=['accuracy'])
    return model

def main(args):
    """Main training routine."""
    df = get_data(args.project_id, args.table_name)

    X = df[['mid_price', 'volume_5s', 'trade_imbalance_5s', 'volatility_30s']].values
    y = df['price_direction_1m'].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = create_model()
    model.fit(X_train, y_train, epochs=args.epochs, batch_size=args.batch_size, validation_data=(X_test, y_test))

    # Save the model to the GCS path specified by Vertex AI
    model.save(os.environ["AIP_MODEL_DIR"])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-id', type=str, required=True)
    parser.add_argument('--table-name', type=str, required=True)
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--batch-size', type=int, default=32)
    args = parser.parse_args()
    main(args)
