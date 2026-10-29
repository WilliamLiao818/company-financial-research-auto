import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from streamlit.testing.v1 import AppTest

from industry_context import (
    STAGE_COMPANIES,
    STAGE_TITLES,
    THEME_STAGES,
    company_url,
    context_for,
    map_url,
)
from research_catalog import COMPANY_NAMES


class IndustryContextTests(unittest.TestCase):
    def test_every_mapped_company_and_related_link_opens_a_public_pack(self) -> None:
        self.assertEqual(set(STAGE_COMPANIES), set(STAGE_TITLES))
        for stage, tickers in STAGE_COMPANIES.items():
            self.assertTrue(tickers)
            for ticker in tickers:
                with self.subTest(stage=stage, ticker=ticker):
                    self.assertIn(ticker, COMPANY_NAMES)
                    context = context_for(ticker)
                    self.assertIsNotNone(context)
                    self.assertIn(stage, context["stage_ids"])
                    self.assertTrue(context["related"])
                    self.assertEqual(len({item["ticker"] for item in context["related"]}), len(context["related"]))
                    for item in context["related"]:
                        self.assertIn(item["ticker"], COMPANY_NAMES)
                        self.assertNotEqual(item["ticker"], ticker)
                        parsed = urlparse(item["url"])
                        self.assertEqual(parsed.scheme, "https")
                        self.assertEqual(parsed.netloc, "company-financial-research-auto.streamlit.app")
                        self.assertEqual(parse_qs(parsed.query), {"ticker": [item["ticker"]]})

    def test_role_specific_map_links_select_relevant_themes(self) -> None:
        for ticker, expected_theme in (("VRT", "power-cooling"), ("LITE", "networking"), ("ANET", "networking"), ("TSM", "ai-compute"), ("NVDA", "ai-compute")):
            with self.subTest(ticker=ticker):
                parsed = urlparse(context_for(ticker)["map_url"])
                self.assertEqual((parsed.scheme, parsed.netloc, parsed.path), ("https", "liaoresearch.com", "/industry"))
                self.assertEqual(parse_qs(parsed.query), {"company": [ticker], "theme": [expected_theme]})
        for stage_ids in THEME_STAGES.values():
            self.assertTrue(set(stage_ids).issubset(STAGE_TITLES))

    def test_unmapped_companies_do_not_acquire_an_ai_role(self) -> None:
        self.assertIsNone(context_for("JNJ"))
        self.assertIsNone(map_url("JNJ"))
        self.assertIsNone(map_url("TSM", "power-cooling"))
        self.assertIsNotNone(company_url("JNJ"))

    def test_link_generation_rejects_untrusted_query_fragments(self) -> None:
        for value in ("NVDA&theme=other", "NVDA#", "NVDA\" onclick=alert(1)", "https://example.com", "UNKNOWN", ""):
            with self.subTest(value=value):
                self.assertIsNone(context_for(value))
                self.assertIsNone(company_url(value))
                self.assertIsNone(map_url(value))
        self.assertIsNone(map_url("NVDA", "ai-compute&company=MSFT"))
        self.assertEqual(company_url(" nvda "), company_url("NVDA"))

    def test_company_pages_render_only_applicable_industry_context(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        with patch("news_connector.load_company_news", return_value=[]):
            for ticker, theme in (("TSM", "ai-compute"), ("VRT", "power-cooling"), ("LITE", "networking"), ("JNJ", None)):
                with self.subTest(ticker=ticker):
                    app = AppTest.from_file(str(app_path), default_timeout=30)
                    app.query_params["ticker"] = ticker
                    app.run()
                    self.assertEqual(len(app.exception), 0)
                    context_cards = [block.value for block in app.markdown if "aria-label='Industry context'" in block.value]
                    if theme is None:
                        self.assertFalse(context_cards)
                    else:
                        self.assertEqual(len(context_cards), 1)
                        self.assertIn(f"company={ticker}&amp;theme={theme}", context_cards[0])
                        self.assertIn("Open industry map", context_cards[0])


if __name__ == "__main__":
    unittest.main()
