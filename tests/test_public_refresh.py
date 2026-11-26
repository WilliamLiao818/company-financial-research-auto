from datetime import date, datetime, timezone
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from market_data import completed_monthly_closes, load_market_performance
from scripts.refresh_public_data import check_result, filing_summary, main, merge_annual, merge_distributed_filing, quarter_summary
from research import REPORTED_FACT_FIELDS


class RefreshTests(unittest.TestCase):
    def test_alerts_once_per_entire_feed_outage_while_publishing_partial_and_recovered_checks(self):
        state = {"AAPL": "ok", "MSFT": "retained"}

        def mock_news(symbols, ledger, now, data):
            for symbol in symbols:
                previous = ledger[symbol].get("news", {})
                ledger[symbol]["news"] = check_result(previous, now, state[symbol])

        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            (data / "refresh_status.json").write_text('{"companies":{}}')
            output = data / "output"
            summary = data / "summary"
            env = {"GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(summary), "GITHUB_ACTIONS": "true"}
            args = ["refresh", "--data-dir", folder, "--feeds", "news", "--ticker", "AAPL", "--ticker", "MSFT"]
            with patch.dict(os.environ, env), patch("sys.argv", args), redirect_stdout(StringIO()), \
                    patch("scripts.refresh_public_data.refresh_news", mock_news):
                for apple_status, expected_alert in [("ok", ""), ("retained", "news"), ("retained", ""),
                                                     ("ok", ""), ("retained", "news")]:
                    state["AAPL"] = apple_status
                    main()
                    self.assertEqual(output.read_text().splitlines()[-1], f"new_outages={expected_alert}")
                    ledger = json.loads((data / "refresh_status.json").read_text())["companies"]
                    self.assertEqual(ledger["AAPL"]["news"]["status"], apple_status)
            self.assertIn("MSFT", summary.read_text())

    def test_news_or_price_failure_keeps_previous_success_time(self):
        first = check_result({}, "2026-11-20T03:00:00+00:00", "ok", "2026-11-19")
        failed = check_result(first, "2026-11-21T03:00:00+00:00", "retained")
        self.assertEqual(failed["verified_at"], first["verified_at"])
        self.assertEqual(failed["as_of"], first["as_of"])
        self.assertNotEqual(failed["attempted_at"], failed["verified_at"])

    def test_independent_index_uses_own_watermark_and_preserves_newer_known_filing(self):
        existing = {"filing": {"filed": "2026-11-17", "url": "original filing"}}
        observed = {"source": "SEC EDGAR via Listed", "indexed_at": "2026-11-13T16:00:00+00:00",
                    "filing": {"filed": "2026-11-10", "url": "older filing"}}
        now = "2026-11-22T03:00:00+00:00"
        delayed = merge_distributed_filing(existing, {}, observed, now)
        self.assertEqual((delayed["status"], delayed["as_of"], delayed["indexed_through"]),
                         ("delayed", "2026-11-17", "2026-11-13"))
        self.assertFalse(delayed["verified_at"])
        self.assertEqual(existing["filing"]["url"], "original filing")
        observed.update(indexed_at="2026-11-20T12:00:00+00:00", filing={"filed":"2026-11-19", "url":"new filing"})
        current = merge_distributed_filing(existing, delayed, observed, now)
        self.assertEqual((current["status"], existing["filing"]["url"]), ("distribution", "new filing"))

    def test_latest_disclosure_includes_foreign_current_reports(self):
        raw = {"cik": 123, "filings": {"recent": {"form": ["6-K", "20-F", "4"],
               "filingDate": ["2026-11-10", "2026-04-25", "2026-11-11"],
               "accessionNumber": ["0000000123-26-000003", "0000000123-26-000002", "0000000123-26-000004"],
               "primaryDocument": ["exhibit.htm", "annual.htm", "x.xml"]}}}
        result = filing_summary(raw, "0000000123", date(2026, 11, 12))
        self.assertEqual(result["form"], "6-K")
        self.assertIn("000000012326000003/exhibit.htm", result["url"])

    def test_no_ytd_or_cross_accession_quarter_and_native_currency(self):
        fact = {"start":"2026-07-01","end":"2026-09-30","val":1000000,"filed":"2026-10-20",
                "form":"6-K","accn":"0000000100-26-000001"}
        raw = {"cik":100, "facts":{"ifrs-full":{}}}
        for tag in ("Revenue", "OperatingProfitLoss", "ProfitLoss"):
            raw["facts"]["ifrs-full"][tag] = {"units":{ccy: [dict(fact)] for ccy in ("TWD", "USD")}}
        self.assertEqual(quarter_summary(raw,date(2026,11,22),"TWD")["currency"], "TWD")
        for rows in raw["facts"]["ifrs-full"]["ProfitLoss"]["units"].values():
            rows[0]["start"] = "2026-01-01"
        self.assertEqual(quarter_summary(raw,date(2026,11,22)), {})

    def test_secondary_does_not_replace_primary_or_verify_changed_comparative(self):
        row = {field: 20 for field in REPORTED_FACT_FIELDS}
        row.update(ticker="ACME", company="Acme", currency="USD", fiscal_year=2025,
                   fiscal_year_end="2025-09-27", filed="2025-11-05", source_url="https://www.sec.gov/Archives/edgar/test",
                   capex_accession=None, capex_xbrl_tag=None, accession=None)
        saved = pd.DataFrame([row])
        provider = saved.copy()
        provider["fiscal_year_end"] = "2025-09-30"
        result = merge_annual(saved, provider, primary=False, today=date(2026,11,22))
        pd.testing.assert_frame_equal(saved,result)
        provider["revenue"] = 35
        with self.assertRaises(ValueError):
            merge_annual(saved, provider, primary=False, today=date(2026,11,22))

    def test_only_adjusted_completed_market_sessions_contribute(self):
        stamps = [pd.Timestamp(d,tz="UTC").timestamp() for d in ["2026-10-30","2026-11-20","2026-11-23"]]
        block = {"meta":{"symbol":"TEST"},"timestamp":stamps,"indicators":{"adjclose":[{"adjclose":[9,10,100]}]}}
        result = completed_monthly_closes(block,"TEST",datetime(2026,11,23,tzinfo=timezone.utc))
        self.assertEqual(list(result.observation_date), ["2026-10-30","2026-11-20"])
        block["indicators"] = {"quote":[{"close":[9,10,100]}]}
        with self.assertRaisesRegex(RuntimeError, "No adjusted close series"):
            completed_monthly_closes(block,"TEST",datetime(2026,11,23,tzinfo=timezone.utc))

    def test_mismatched_partial_month_does_not_enter_relative_return(self):
        records = [(month,symbol,10,day) for month,day in [("2026-09-01","2026-09-30"),
            ("2026-10-01","2026-10-30"),("2026-11-01","2026-11-20")] for symbol in ["ABC","SPY","QQQ"]]
        records[-3] = ("2026-11-01","ABC",10,"2026-11-19")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"prices.csv"
            pd.DataFrame(records,columns=["date","series","adjusted_close","observation_date"]).to_csv(path,index=False)
            self.assertEqual(load_market_performance("ABC",path).date.max(),pd.Timestamp("2026-10-30"))
