# data_pipeline/beam_feature_pipeline/main.py
import argparse
import json
import logging
from datetime import datetime

import apache_beam as beam
from apache_beam.io.gcp.pubsub import ReadFromPubSub, WriteToPubSub
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions, GoogleCloudOptions
from apache_beam.transforms.combiners import MeanCombineFn
from apache_beam.transforms.trigger import AfterWatermark, AfterProcessingTime, AfterCount, Repeatedly

class ParseAndExtract(beam.DoFn):
    """Parses Pub/Sub messages and extracts core fields."""
    def process(self, element):
        try:
            msg = json.loads(element.decode("utf-8"))
            payload = msg.get("payload", {})

            price = float(payload.get("p", 0))
            qty = float(payload.get("q", 0))
            bid = float(payload.get("b", 0))
            ask = float(payload.get("a", 0))

            yield (msg.get("instrument"), {
                "price": price,
                "quantity": qty,
                "bid": bid,
                "ask": ask,
                "timestamp": msg.get("ts", datetime.utcnow().isoformat())
            })
        except Exception as e:
            logging.error(f"Error parsing message: {e}")

class ComputeWindowFeatures(beam.DoFn):
    """Computes features over a window of elements."""
    def process(self, element_tuple):
        instrument, elements = element_tuple

        if not elements:
            return

        prices = [e["price"] for e in elements if e["price"] > 0]
        quantities = [e["quantity"] for e in elements]
        bids = [e["bid"] for e in elements if e["bid"] > 0]
        asks = [e["ask"] for e in elements if e["ask"] > 0]

        # 1. VWAP (Volume-Weighted Average Price)
        numerator = sum(p * q for p, q in zip(prices, quantities))
        denominator = sum(quantities)
        vwap = numerator / denominator if denominator > 0 else (prices[0] if prices else 0)

        # 2. Average Spread
        avg_spread = 0
        if bids and asks:
            avg_spread = sum(a - b for a, b in zip(asks, bids)) / len(bids)

        # 3. Order Flow Imbalance (OFI) - Simplified
        # Sum of bid volume vs sum of ask volume as a proxy
        total_bid = sum(bids)
        total_ask = sum(asks)
        ofi = (total_bid - total_ask) / (total_bid + total_ask) if (total_bid + total_ask) > 0 else 0

        yield {
            "instrument": instrument,
            "ts": datetime.utcnow().isoformat(),
            "features": {
                "vwap": vwap,
                "avg_spread": avg_spread,
                "order_flow_imbalance": ofi,
                "sample_count": len(elements)
            }
        }

def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_topic", required=True, help="Pub/Sub topic to read from")
    parser.add_argument("--output_topic", required=True, help="Pub/Sub topic to write features to")
    parser.add_argument("--project", help="Google Cloud Project ID")
    args, pipeline_args = parser.parse_known_args(argv)

    options = PipelineOptions(pipeline_args)
    options.view_as(StandardOptions).streaming = True
    if args.project:
        options.view_as(GoogleCloudOptions).project = args.project

    with beam.Pipeline(options=options) as p:
        (
            p
            | "ReadFromPubSub" >> ReadFromPubSub(topic=args.input_topic)
            | "Parse" >> beam.ParDo(ParseAndExtract())
            | "Window" >> beam.WindowInto(
                beam.window.SlidingWindows(size=60, period=10), # 1 minute window, every 10s
                trigger=Repeatedly(AfterProcessingTime(10)),
                accumulation_mode=beam.transforms.trigger.AccumulationMode.DISCARDING
            )
            | "GroupByKey" >> beam.GroupByKey()
            | "ComputeFeatures" >> beam.ParDo(ComputeWindowFeatures())
            | "FormatOutput" >> beam.Map(lambda x: json.dumps(x).encode("utf-8"))
            | "WriteToPubSub" >> WriteToPubSub(topic=args.output_topic)
        )

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    run()
