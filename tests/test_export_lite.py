import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from research import latest_company_summary, load_financials
from research_catalog import COMPANY_NAMES, latest_results_snapshot
from scripts.export_lite import build_lite_feed, export_story, write_lite_feed
from stress_model import PRESETS, Assumptions, compare


class PublicLiteFeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = build_lite_feed()

    def test_all_active_companies_and_only_public_brief_fields(self):
        self.assertEqual(set(self.feed), {"schema_version", "generated_at", "companies"})
        self.assertEqual(set(self.feed["companies"]), set(COMPANY_NAMES))
        frame = load_financials()
        for ticker, brief in self.feed["companies"].items():
            with self.subTest(ticker=ticker):
                self.assertEqual(set(brief), {
                    "ticker", "name", "role", "sector", "annual", "question", "thesis", "counter_thesis",
                    "peers", "cases", "latest_filing", "latest_quarter", "news", "refresh",
                })
                self.assertLessEqual(set(brief["peers"]), COMPANY_NAMES.keys())
                summary = latest_company_summary(frame, ticker)
                self.assertEqual(brief["annual"]["currency"], summary["currency"])
                self.assertEqual(brief["annual"]["revenue"], summary["revenue"])
                self.assertEqual(set(brief["cases"]), set(PRESETS))
                for case in brief["cases"].values():
                    expected = compare(brief["annual"]["revenue"], case["horizon_years"],
                                       Assumptions(**case["assumptions"]["base"]), Assumptions(**case["assumptions"]["stress"]))
                    self.assertEqual(expected, case["outputs"])
                    self.assertEqual(case["reported_facts"]["period_end"], brief["annual"]["period_end"])
                    self.assertEqual(case["reported_facts"]["filed"], brief["annual"]["filed"])

    def test_observations_keep_their_own_units_and_window(self):
        on_date = datetime.fromisoformat(self.feed["generated_at"]).date()
        for ticker, brief in self.feed["companies"].items():
            with self.subTest(ticker=ticker):
                self.assertLessEqual(set(brief["refresh"]), {"filings", "financials", "quarterly", "market", "news"})
                for feed_name, feed in brief["refresh"].items():
                    required = {"status", "attempted_at", "verified_at", "as_of"}
                    self.assertLessEqual(required, set(feed))
                    extra = {"indexed_through", "distribution_source"} if feed_name == "filings" else set()
                    self.assertLessEqual(set(feed), required | extra)
                if quarter := brief["latest_quarter"]:
                    self.assertEqual(quarter["unit"], "millions")
                    self.assertEqual(quarter["revenue"], latest_results_snapshot(ticker)["revenue"])
                    self.assertTrue(quarter["url"].startswith("https://"))
                self.assertLessEqual(len(brief["news"]), 3)
                for item in brief["news"]:
                    published = datetime.fromisoformat(item["date"]).date()
                    self.assertLessEqual(on_date - timedelta(days=90), published)
                    self.assertLessEqual(published, on_date)
                    self.assertTrue(item["url"].startswith("https://"))

    def test_only_verified_article_covers_are_exported(self):
        story = {"title": "Earnings", "publisher": "Example", "date": "2026-11-12", "url": "https://example.com/story"}
        cover = "https://cdn.example.com/newsroom/article-cover.jpg"
        self.assertEqual(export_story({**story, "image_kind": "article", "image": cover})["image"], cover)
        for kind, url in (("", cover), ("article", "http://example.com/x.jpg"), ("article", "https://www.bing.com/th?id=42"),
                          ("article", "https://example.matomo.cloud/matomo.php?idsite=42")):
            self.assertNotIn("image", export_story({**story, "image_kind": kind, "image": url}))

    def test_invalid_export_cannot_replace_previous_good_feed(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "public.json"
            write_lite_feed(target, self.feed)
            encoded = target.read_bytes()
            self.assertEqual(json.loads(encoded), self.feed)
            with self.assertRaises(ValueError):
                write_lite_feed(target, {"partial": float("nan")})
            self.assertEqual(target.read_bytes(), encoded)
            self.assertEqual(list(target.parent.iterdir()), [target])
