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
            best_bid = float(element.get('best_bid', 0.0))
            best_ask = float(element.get('best_ask', 0.0))

            return {
                'instrument': element['instrument'],
                'timestamp': timestamp,
                'price': float(element['price']),
                'quantity': quantity,
                'side': side,
                'trade_direction': trade_direction,
                'signed_volume': quantity * trade_direction,
                'mid_price': (best_bid + best_ask) / 2 if best_bid > 0 else 0.0,
                'spread': best_ask - best_bid if best_bid > 0 else 0.0
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
                'mid_price': price, # Use the swap price as the mid_price for Uniswap
                'spread': 0.0 # Spread is not applicable for Uniswap AMM
            }
        else:
            return None
    except (TypeError, ValueError, KeyError, AttributeError) as e:
        logging.warning(f"Normalization failed for element {element}: {e}")
        return None


class ParseAndTag(beam.PTransform):
    # ... (no changes)

def run():
    # ... (no changes)

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    run()
