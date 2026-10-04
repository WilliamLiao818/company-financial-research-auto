import unittest

from company_profiles import PROFILES, accounting_quality_signals, fcf_bridge
from research import load_financials
from research_catalog import COMPANY_NAMES


class CompanyProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = load_financials()

    def test_prebuilt_snapshot_contains_the_full_company_catalog(self) -> None:
        self.assertEqual(len(COMPANY_NAMES), 50)
        self.assertEqual(set(self.frame["ticker"]), set(COMPANY_NAMES))
        self.assertEqual(set(PROFILES), set(COMPANY_NAMES))

    def test_every_prebuilt_company_has_at_least_two_annual_periods(self) -> None:
        periods = self.frame.groupby("ticker")["fiscal_year"].nunique()
        self.assertEqual(set(periods.index), set(COMPANY_NAMES))
        self.assertTrue((periods >= 2).all(), periods.loc[periods < 2].to_dict())

    def test_oracle_gross_margin_is_derived_from_reported_direct_costs(self) -> None:
        oracle = self.frame.loc[self.frame["ticker"] == "ORCL"].sort_values("fiscal_year")
        self.assertTrue(oracle["gross_profit"].notna().all())
        self.assertAlmostEqual(float(oracle.iloc[-1]["gross_margin"]), 44336000000 / 67357000000)

    def test_msft_lease_signal_is_sourced_and_adjusts_simple_fcf(self) -> None:
        signals = accounting_quality_signals(self.frame, "MSFT")
        self.assertIn("Finance lease principal outside operating cash flow", set(signals["signal"]))
        bridge = fcf_bridge(self.frame, "MSFT")
        self.assertEqual(bridge.iloc[-1]["step"], "Infrastructure-adjusted FCF")
        self.assertLess(bridge.iloc[-1]["amount_usd_billions"], bridge.iloc[0]["amount_usd_billions"])


if __name__ == "__main__":
    unittest.main()
