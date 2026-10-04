from datetime import date
import unittest

import pandas as pd

from market_data import SNAPSHOT_PATH
from research import load_financials
from research_catalog import COMPANY_NAMES, LATEST_RESULTS_SNAPSHOTS, latest_results_snapshot, target_price_snapshot


class DataFreshnessTests(unittest.TestCase):
    def test_every_explicit_quarterly_snapshot_has_a_current_official_results_link(self) -> None:
        self.assertTrue(set(LATEST_RESULTS_SNAPSHOTS).issubset(COMPANY_NAMES))
        for ticker in LATEST_RESULTS_SNAPSHOTS:
            with self.subTest(ticker=ticker):
                result = latest_results_snapshot(ticker)
                self.assertTrue(result["label"])
                self.assertRegex(result["period_end"], r"^2026-\d{2}-\d{2}$")
                self.assertTrue(result["url"].startswith("https://www.sec.gov/Archives/edgar/data/"))
                duration_days = (pd.Timestamp(result["period_end"]) - pd.Timestamp(result["period_start"])).days
                self.assertGreaterEqual(duration_days, 70)
                self.assertLessEqual(duration_days, 110)
                self.assertGreater(float(result["revenue"]), 0)
                self.assertIn(result["currency"], {"USD", "TWD", "EUR"})

    def test_tsm_fy2025_uses_the_official_20f_convenience_translation(self) -> None:
        frame = load_financials()
        tsm = frame.loc[frame["ticker"] == "TSM"].sort_values("fiscal_year")
        latest = tsm.iloc[-1]
        self.assertEqual(int(latest["fiscal_year"]), 2025)
        self.assertEqual(str(latest["fiscal_year_end"]), "2025-12-31")
        self.assertEqual(float(latest["revenue"]), 121_423_500_000)
        self.assertEqual(float(latest["assets"]), float(latest["liabilities"] + latest["equity"]))

    def test_market_snapshot_reaches_september_2026_for_every_series(self) -> None:
        frame = pd.read_csv(SNAPSHOT_PATH, parse_dates=["date"])
        self.assertEqual(frame["series"].nunique(), len(COMPANY_NAMES) + 2)
        latest_dates = frame.groupby("series")["date"].max()
        self.assertTrue((latest_dates >= pd.Timestamp("2026-09-01")).all())
        sandisk_start = frame.loc[frame["series"] == "SNDK", "date"].min()
        self.assertGreaterEqual(sandisk_start, pd.Timestamp("2025-02-01"))

    def test_old_target_observations_are_marked_stale(self) -> None:
        snapshot = target_price_snapshot("MSFT", as_of=date(2026, 9, 28))
        self.assertTrue(snapshot["stale"])


if __name__ == "__main__":
    unittest.main()
