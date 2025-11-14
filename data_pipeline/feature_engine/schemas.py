# schemas.py
from apache_beam.io.gcp.internal.clients import bigquery

def get_feature_schema():
    """Returns the BigQuery schema for the features table."""
    schema = bigquery.TableSchema()

    schema.fields.append(bigquery.TableFieldSchema(
        name='instrument', type='STRING', mode='REQUIRED'))
    schema.fields.append(bigquery.TableFieldSchema(
        name='timestamp', type='TIMESTAMP', mode='REQUIRED'))
    schema.fields.append(bigquery.TableFieldSchema(
        name='mid_price', type='FLOAT', mode='NULLABLE'))
    schema.fields.append(bigquery.TableFieldSchema(
        name='spread', type='FLOAT', mode='NULLABLE'))
    schema.fields.append(bigquery.TableFieldSchema(
        name='volume_1s', type='FLOAT', mode='NULLABLE'))
    schema.fields.append(bigquery.TableFieldSchema(
        name='volume_5s', type='FLOAT', mode='NULLABLE'))
    schema.fields.append(bigquery.TableFieldSchema(
        name='trade_imbalance_5s', type='FLOAT', mode='NULLABLE'))
    schema.fields.append(bigquery.TableFieldSchema(
        name='volatility_30s', type='FLOAT', mode='NULLABLE'))

    return schema
