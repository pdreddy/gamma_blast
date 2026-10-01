import unittest

import pandas as pd

from config import StrategyConfig
from backtest_engine import _prepare_day
from strategy import prepare_signal_frame, signal_from_candles


def bullish_breakout(close_location=0.93):
    rows = []
    for i in range(30):
        close = 100 + i * 0.2
        rows.append({
            "timestamp": pd.Timestamp("2026-01-01 09:15") + pd.Timedelta(minutes=3 * i),
            "open": close - 0.15,
            "high": close + 0.10,
            "low": close - 0.20,
            "close": close,
        })

    low = 105.60
    high = 105.95
    rows[-1].update(
        open=105.40,
        low=low,
        high=high,
        close=low + close_location * (high - low),
    )
    return pd.DataFrame(rows)


class QualityFilteredSignalTests(unittest.TestCase):
    def test_accepts_convincing_momentum_breakout(self):
        candles = bullish_breakout()
        signal = signal_from_candles(candles)

        self.assertIsNotNone(signal)
        self.assertEqual(signal["option_type"], "CE")
        self.assertIn("Quality-filtered", signal["reason"])

    def test_rejects_breakout_that_closes_in_middle_of_candle(self):
        candles = bullish_breakout(close_location=0.55)
        frame = prepare_signal_frame(candles)

        self.assertFalse(bool(frame.iloc[-1]["bull"]))
        self.assertIsNone(signal_from_candles(candles))

    def test_backtest_and_live_scan_use_same_signal_rules(self):
        candles = bullish_breakout()
        live_frame = prepare_signal_frame(candles)
        backtest_frame = _prepare_day(candles, StrategyConfig())

        pd.testing.assert_series_equal(
            live_frame["bull"], backtest_frame["bull"], check_names=False
        )
        pd.testing.assert_series_equal(
            live_frame["bear"], backtest_frame["bear"], check_names=False
        )


if __name__ == "__main__":
    unittest.main()
