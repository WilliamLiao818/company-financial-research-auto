from datetime import date
import unittest

from filing_index import parse_index


class FilingIndexTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "cik": 320193, "tickers": ["AAPL"], "source": {
                "name": "SEC EDGAR", "submissions_updated_at": "2026-11-13T00:06:39.828Z",
            },
        }
        # Submitting agent and registrant can have different accession prefixes.
        self.row = {
            "company": {"cik": 320193}, "form": "8-K", "filed": "2026-11-09",
            "accepted_at": "2026-11-09T21:30:00Z", "accession": "0001140361-26-042798",
            "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000114036126042798/",
        }
        self.today = date(2026, 11, 22)

    def test_source_time_is_separate_from_filing_and_local_check(self):
        result = parse_index(self.profile, {"filings": [dict(self.row, form="4"), self.row]},
                             "AAPL", "0000320193", self.today)
        self.assertEqual(result["indexed_at"], "2026-11-13T00:06:39.828000+00:00")
        self.assertEqual(result["filing"]["filed"], "2026-11-09")
        self.assertEqual(result["filing"]["url"], self.row["source_url"] + self.row["accession"] + "-index.htm")

    def test_excludes_other_issuers_unsafe_urls_and_future_filings(self):
        for overrides in [{"company": {"cik": 1}}, {"source_url": "https://another-site.example/"},
                          {"filed": "2027-01-01"}, {"accession": "../wrong"}, {"form": "4"}]:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                parse_index(self.profile, {"filings": [dict(self.row, **overrides)]},
                            "AAPL", 320193, self.today)

    def test_unknown_issuer_and_future_source_watermark_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_index(self.profile, {"filings": [self.row]}, "MSFT", 789019, self.today)
        self.profile["source"]["submissions_updated_at"] = "2027-01-01T00:00:00Z"
        with self.assertRaises(ValueError):
            parse_index(self.profile, {"filings": [self.row]}, "AAPL", 320193, self.today)
