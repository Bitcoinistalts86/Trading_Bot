# transforms.py
import apache_beam as beam
from apache_beam.coders import coders
from apache_beam.transforms.userstate import (
    BagStateSpec, TimerSpec, on_timer, ReadModifyWriteStateSpec
)
import numpy as np
from datetime import datetime, timezone

class ComputeFeaturesDoFn(beam.DoFn):
    """Computes a unified feature vector from a stream of trades using state and timers."""

    # --- State Specs ---
    # Store trades for different window calculations
    TRADES_BAG_1S = BagStateSpec('trades_1s', coders.TupleCoder((coders.FloatCoder(), coders.FloatCoder(), coders.StringCoder())))
    TRADES_BAG_5S = BagStateSpec('trades_5s', coders.TupleCoder((coders.FloatCoder(), coders.FloatCoder(), coders.StringCoder())))
    TRADES_BAG_30S = BagStateSpec('trades_30s', coders.TupleCoder((coders.FloatCoder(), coders.FloatCoder(), coders.StringCoder())))

    # State to hold the unified feature vector before emitting
    FEATURE_VECTOR = ReadModifyWriteStateSpec('feature_vector', coders.JsonCoder())

    # --- Timer Specs ---
    # Timers to trigger feature calculation and clear state for each window
    TIMER_1S = TimerSpec('timer_1s', beam.TimeDomain.EVENT_TIME)
    TIMER_5S = TimerSpec('timer_5s', beam.TimeDomain.EVENT_TIME)
    TIMER_30S = TimerSpec('timer_30s', beam.TimeDomain.EVENT_TIME)

    # A final timer to emit the combined feature vector
    EMIT_TIMER = TimerSpec('emit_timer', beam.TimeDomain.EVENT_TIME)

    def process(
        self,
        element,
        timestamp=beam.DoFn.TimestampParam,
        trades_1s=beam.DoFn.StateParam(TRADES_BAG_1S),
        trades_5s=beam.DoFn.StateParam(TRADES_BAG_5S),
        trades_30s=beam.DoFn.StateParam(TRADES_BAG_30S),
        feature_vector=beam.DoFn.StateParam(FEATURE_VECTOR),
        timer_1s=beam.DoFn.TimerParam(TIMER_1S),
        timer_5s=beam.DoFn.TimerParam(TIMER_5S),
        timer_30s=beam.DoFn.TimerParam(TIMER_30S),
        emit_timer=beam.DoFn.TimerParam(EMIT_TIMER)
    ):
        instrument, trade = element
        trade_tuple = (trade['price'], trade['quantity'], trade['side'])

        # Add the trade to all relevant state bags
        trades_1s.add(trade_tuple)
        trades_5s.add(trade_tuple)
        trades_30s.add(trade_tuple)

        # Initialize the feature vector if it doesn't exist for this window
        current_features = feature_vector.read()
        if not current_features:
            feature_vector.write({
                'instrument': instrument,
                'timestamp': datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
                'mid_price': trade.get('mid_price', 0.0), # Calculated per-trade
                'spread': trade.get('spread', 0.0), # Calculated per-trade
            })

        # Set timers. We set them dynamically to fire at the end of the current second.
        # This ensures all events within the same second are processed before firing.
        fire_time = int(timestamp) + 1
        timer_1s.set(fire_time)
        timer_5s.set(fire_time)
        timer_30s.set(fire_time)
        emit_timer.set(fire_time + 0.5) # Emit slightly after calculations

    @on_timer(TIMER_1S)
    def on_timer_1s(self, trades_1s=beam.DoFn.StateParam(TRADES_BAG_1S), feature_vector=beam.DoFn.StateParam(FEATURE_VECTOR)):
        trades = list(trades_1s.read())
        if trades:
            volume_1s = sum(t[1] for t in trades)
            current_features = feature_vector.read()
            current_features['volume_1s'] = volume_1s
            feature_vector.write(current_features)
        trades_1s.clear()

    @on_timer(TIMER_5S)
    def on_timer_5s(self, trades_5s=beam.DoFn.StateParam(TRADES_BAG_5S), feature_vector=beam.DoFn.StateParam(FEATURE_VECTOR)):
        trades = list(trades_5s.read())
        if trades:
            volume_5s = sum(t[1] for t in trades)
            buys = sum(t[1] for t in trades if t[2] == 'BUY')
            sells = sum(t[1] for t in trades if t[2] == 'SELL')
            trade_imbalance_5s = buys - sells

            current_features = feature_vector.read()
            current_features['volume_5s'] = volume_5s
            current_features['trade_imbalance_5s'] = trade_imbalance_5s
            feature_vector.write(current_features)
        trades_5s.clear()

    @on_timer(TIMER_30S)
    def on_timer_30s(self, trades_30s=beam.DoFn.StateParam(TRADES_BAG_30S), feature_vector=beam.DoFn.StateParam(FEATURE_VECTOR)):
        trades = list(trades_30s.read())
        if trades:
            prices = [t[0] for t in trades]
            volatility_30s = np.std(np.diff(prices) / prices[:-1]) if len(prices) > 1 else 0.0

            current_features = feature_vector.read()
            current_features['volatility_30s'] = volatility_30s
            feature_vector.write(current_features)
        trades_30s.clear()

    @on_timer(EMIT_TIMER)
    def on_emit_timer(self, feature_vector=beam.DoFn.StateParam(FEATURE_VECTOR)):
        final_features = feature_vector.read()
        if final_features:
            # Fill in any features that might not have been calculated if no trades arrived
            final_features.setdefault('volume_1s', 0.0)
            final_features.setdefault('volume_5s', 0.0)
            final_features.setdefault('trade_imbalance_5s', 0.0)
            final_features.setdefault('volatility_30s', 0.0)

            yield final_features
        feature_vector.clear()
