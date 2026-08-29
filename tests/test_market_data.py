import unittest

from market_data import BENCHMARKS, load_market_performance


class MarketDataTests(unittest.TestCase):
    def test_company_history_uses_spy_and_qqq_benchmarks(self):
        self.assertEqual(BENCHMARKS, {"SPY": "SPY", "QQQ": "QQQ"})
        frame = load_market_performance("MSFT")
        self.assertEqual(set(frame["series"]), {"MSFT", "SPY", "QQQ"})
        self.assertTrue(frame["adjusted_close"].notna().all())


if __name__ == "__main__":
    unittest.main()
