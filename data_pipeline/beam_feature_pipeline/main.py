"""A streaming feature pipeline using Apache Beam and Google Cloud Dataflow."""
import argparse
import json
from datetime import datetime

import apache_beam as beam
from apache_beam.io.gcp.bigquery import WriteToBigQuery
from apache_beam.io.gcp.pubsub import ReadFromPubSub
from apache_beam.options.pipeline_options import (
    GoogleCloudOptions,
    PipelineOptions,
    SetupOptions,
    StandardOptions,
)


class ParseMessage(beam.DoFn):
    """Parses the input Pub/Sub message."""

    def process(self, element):
        """Processes a single Pub/Sub message."""
        msg = json.loads(element.decode("utf-8"))
        # expect raw structure {exchange, instrument, ts, payload}
        ts = msg.get("ts") or datetime.utcnow().isoformat() + "Z"
        payload = msg.get("payload")
        # TODO: parse payload to extract price/qty/book snapshots
        yield {
            "exchange": msg.get("exchange"),
            "instrument": msg.get("instrument"),
            "ts": ts,
            "payload": json.dumps(payload),
        }


class RollingFeatures(beam.PTransform):
    """Computes rolling features over a window."""

    def expand(self, pcoll):
        """Applies the PTransform."""
        # Simplified example: compute dummy features
        return (
            pcoll
            | "Window" >> beam.WindowInto(beam.window.FixedWindows(5))
            | "ComputeSimpleFeatures"
            >> beam.Map(
                lambda r: {
                    "exchange": r["exchange"],
                    "instrument": r["instrument"],
                    "ts": r["ts"],
                    "vwap_1s": 0.0,
                    "vwap_5s": 0.0,
                    "orderflow_imbalance": 0.0,
                    "bid_ask_spread": 0.0,
                    "payload": r["payload"],
                }
            )
        )


def run(argv=None):
    """Runs the feature pipeline."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--input_topic", required=True)
    parser.add_argument("--output_table", required=True)
    parser.add_argument("--temp_location", required=True)
    parser.add_argument("--staging_location", required=True)
    args, pipeline_args = parser.parse_known_args(argv)

    options = PipelineOptions(pipeline_args)
    google_cloud_options = options.view_as(GoogleCloudOptions)
    google_cloud_options.project = args.project
    google_cloud_options.region = args.region
    google_cloud_options.staging_location = args.staging_location
    google_cloud_options.temp_location = args.temp_location
    options.view_as(StandardOptions).streaming = True
    options.view_as(SetupOptions).save_main_session = True

    with beam.Pipeline(options=options) as p:
        messages = (
            p
            | "ReadFromPubSub" >> ReadFromPubSub(topic=args.input_topic).with_output_types(bytes)
            | "Parse" >> beam.ParDo(ParseMessage())
            | "FeatureWindow" >> RollingFeatures()
        )

        messages | "WriteToBigQuery" >> WriteToBigQuery(
            table=args.output_table,
            custom_gcs_temp_location=args.temp_location,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
        )


if __name__ == "__main__":
    run()
