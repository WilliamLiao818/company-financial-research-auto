import unittest

from company_profiles import accounting_quality_signals, fcf_bridge
from research import load_financials


class CompanyProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = load_financials()

    def test_prebuilt_snapshot_contains_only_two_companies(self) -> None:
        self.assertEqual(set(self.frame["ticker"]), {"MSFT", "ORCL"})

    def test_msft_lease_signal_is_sourced_and_adjusts_simple_fcf(self) -> None:
        signals = accounting_quality_signals(self.frame, "MSFT")
        self.assertIn("Finance lease principal outside operating cash flow", set(signals["signal"]))
        bridge = fcf_bridge(self.frame, "MSFT")
        self.assertEqual(bridge.iloc[-1]["step"], "Infrastructure-adjusted FCF")
        self.assertLess(bridge.iloc[-1]["amount_usd_billions"], bridge.iloc[0]["amount_usd_billions"])


if __name__ == "__main__":
    unittest.main()
