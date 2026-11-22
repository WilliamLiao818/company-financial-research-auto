from copy import deepcopy
from datetime import date
import unittest

from provider_quarter import choose_quarter, normalized_quarter, provider_check_status


TODAY = date(2026, 11, 22)


def payload(ticker, fields, end="2026-09-30", currency="USD", duration="3M"):
    return {"timeseries": {"result": [
        {"meta": {"symbol": [ticker], "type": [key]},
         key: [{"asOfDate": end, "periodType": duration, "currencyCode": currency, "reportedValue": {"raw": value}}]}
        for key, value in fields
    ]}}


class QuarterlyProviderTests(unittest.TestCase):
    def test_three_month_report_in_millions_without_invented_dates(self):
        row = normalized_quarter(payload("ARM", [("quarterlyTotalRevenue", 1_443_000_000), ("quarterlyNetIncome", -8_500_000)]), "ARM", TODAY)
        self.assertEqual(row["source_kind"], "provider")
        self.assertEqual(row["period_precision"], "month")
        self.assertEqual(row["label"], "Quarter · 2026-09")
        self.assertIsNone(row["period_start"])
        self.assertIsNone(row["filed"])
        self.assertIsNone(row["operating_income"])
        self.assertEqual(row["revenue"], 1443.0)
        self.assertEqual(row["net_income"], -8.5)

    def test_no_ttm_future_or_cross_issuer_and_period_mixing(self):
        fields = [("quarterlyTotalRevenue", 2000000), ("quarterlyOperatingIncome", 1200000), ("quarterlyNetIncome", 900000)]
        for duration in ("12M", "9M", "6M", "TTM", ""):
            self.assertFalse(normalized_quarter(payload("TSM", fields, duration=duration), "TSM", TODAY))
        self.assertFalse(normalized_quarter(payload("TSM", fields, end="2026-12-31"), "TSM", TODAY))
        with self.assertRaises(ValueError):
            normalized_quarter(payload("OTHER", fields), "TSM", TODAY)
        mixed = payload("TSM", fields, currency="TWD")
        mixed["timeseries"]["result"][1]["quarterlyOperatingIncome"][0]["currencyCode"] = "USD"
        mixed["timeseries"]["result"][2]["quarterlyNetIncome"][0]["asOfDate"] = "2026-06-30"
        q = normalized_quarter(mixed, "TSM", TODAY)
        self.assertEqual(q["currency"], "TWD")
        self.assertIsNone(q["operating_income"])
        self.assertIsNone(q["net_income"])

    def test_same_period_prefers_issuer_despite_nearby_normalized_end(self):
        official = {"period_end": "2026-09-26", "filed": "2026-10-22", "currency": "USD"}
        provider = normalized_quarter(payload("AAPL", [("quarterlyTotalRevenue", 2000000)]), "AAPL", TODAY)
        self.assertIs(choose_quarter(official, provider), official)
        self.assertIs(choose_quarter(provider, official), official)
        self.assertEqual(provider_check_status(official, provider), "fallback")
        self.assertEqual(provider_check_status({**official, "period_end": "2026-12-31"}, provider), "delayed")
        old = {**official, "period_end": "2026-06-27"}
        self.assertIs(choose_quarter(old, provider), provider)
        self.assertIs(choose_quarter(provider, old), provider)

    def test_partial_same_quarter_provider_cannot_erase_verified_values(self):
        good = normalized_quarter(payload("ASML", [("quarterlyTotalRevenue", 2000000), ("quarterlyNetIncome", 1)],currency="EUR"), "ASML", TODAY)
        missing = deepcopy(good)
        missing["net_income"] = None
        self.assertIs(choose_quarter(good, missing), good)
