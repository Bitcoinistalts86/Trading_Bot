# main.py
import argparse
import logging
import json

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from dateutil import parser as dateparser

from schemas import get_feature_schema
from transforms import ComputeFeaturesDoFn
from utils import parse_json


def normalize_trade(element):
    """
    Normalizes a trade from Binance or Uniswap to a common format.
    Returns None if the element is malformed.
    """
    try:
        if element.get('exchange') == 'binance':
            timestamp = dateparser.parse(element['timestamp']).timestamp()
            side = element['side'].upper()
            trade_direction = 1 if side == 'BUY' else -1
            quantity = float(element['quantity'])

            return {
                'instrument': element['instrument'],
                'timestamp': timestamp,
                'price': float(element['price']),
                'quantity': quantity,
                'side': side,
                'trade_direction': trade_direction,
                'signed_volume': quantity * trade_direction,
                'mid_price': 0.0,
                'spread': 0.0
            }
        elif element.get('exchange') == 'uniswap-v3':
            timestamp = dateparser.parse(element['timestamp']).timestamp()

            amount0_in = float(element.get('amount0_in', 0))
            amount1_in = float(element.get('amount1_in', 0))
            amount0_out = float(element.get('amount0_out', 0))
            amount1_out = float(element.get('amount1_out', 0))

            side = 'BUY' if amount0_in > 0 or amount1_in > 0 else 'SELL'
            trade_direction = 1 if side == 'BUY' else -1

            price_denominator = amount0_in + amount1_out
            price = (amount0_out + amount1_in) / price_denominator if price_denominator > 0 else 0
            quantity = amount0_in + amount1_in

            return {
                'instrument': element['pair'],
                'timestamp': timestamp,
                'price': price,
                'quantity': quantity,
                'side': side,
                'trade_direction': trade_direction,
                'signed_volume': quantity * trade_direction,
                'mid_price': 0.0,
                'spread': 0.0
            }
        else:
            return None
    except (TypeError, ValueError, KeyError, AttributeError) as e:
        logging.warning(f"Normalization failed for element {element}: {e}")
        return None


class ParseAndTag(beam.PTransform):
    """A transform to parse JSON and tag failed records."""
    def expand(self, pcoll):
        parsed = pcoll | 'Parse' >> beam.Map(lambda x: (parse_json(x), x))
        successful = parsed | 'GetSuccessful' >> beam.Filter(lambda x: x[0] is not None) | 'ExtractValue' >> beam.Map(lambda x: x[0])
        failed = parsed | 'GetFailed' >> beam.Filter(lambda x: x[0] is None) | 'ExtractRaw' >> beam.Map(lambda x: x[1])
        return successful, failed


def run():
    """Build and run the feature engine pipeline."""
    parser = argparse.ArgumentParser(description="Dataflow Feature Engine")
    parser.add_argument('--input_subscription_binance', required=True)
    parser.add_argument('--input_subscription_uniswap', required=True)
    parser.add_argument('--output_topic', required=True)
    parser.add_argument('--output_table', required=True)
    parser.add_argument('--dead_letter_topic', required=True)
    known_args, pipeline_args = parser.parse_known_args()

    pipeline_options = PipelineOptions(pipeline_args)
    pipeline_options.view_as(StandardOptions).streaming = True

    with beam.Pipeline(options=pipeline_options) as p:
        binance_trades = (
            p
            | 'ReadFromBinanceSub' >> beam.io.ReadFromPubSub(subscription=known_args.input_subscription_binance)
            | 'DecodeBinance' >> beam.Map(lambda x: x.decode('utf-8'))
        )

        uniswap_swaps = (
            p
            | 'ReadFromUniswapSub' >> beam.io.ReadFromPubSub(subscription=known_args.input_subscription_uniswap)
            | 'DecodeUniswap' >> beam.Map(lambda x: x.decode('utf-8'))
        )

        raw_trades = (binance_trades, uniswap_swaps) | 'MergeStreams' >> beam.Flatten()

        successful_parses, failed_parses = raw_trades | 'ParseAndTag' >> ParseAndTag()

        (
            failed_parses
            | 'EncodeDeadLetter' >> beam.Map(lambda x: x.encode('utf-8'))
            | 'WriteToDeadLetter' >> beam.io.WriteToPubSub(topic=known_args.dead_letter_topic)
        )

        normalized_trades = (
            successful_parses
            | 'Normalize' >> beam.Map(normalize_trade)
            | 'FilterFailedNormalization' >> beam.Filter(lambda x: x is not None)
        )

        keyed_trades = (
            normalized_trades
            | 'AssignTimestamps' >> beam.Map(lambda x: beam.window.TimestampedValue(x, x['timestamp']))
            | 'KeyByInstrument' >> beam.Map(lambda x: (x['instrument'], x))
        )

        features = keyed_trades | 'ComputeFeatures' >> beam.ParDo(ComputeFeaturesDoFn())

        (
            features
            | 'FormatForPubSub' >> beam.Map(json.dumps)
            | 'EncodeForPubSub' >> beam.Map(lambda x: x.encode('utf-8'))
            | 'WriteToPubSub' >> beam.io.WriteToPubSub(topic=known_args.output_topic)
        )

        (
            features
            | 'WriteToBigQuery' >> beam.io.WriteToBigQuery(
                table=known_args.output_table,
                schema=get_feature_schema(),
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
            )
        )

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    run()
