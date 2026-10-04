from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from news_connector import (
    OFFICIAL_DOMAINS_BY_TICKER,
    SEARCH_ALIASES,
    _decode_google_news_url,
    _dated_article_time,
    _materiality_count,
    _valid_cover_url,
    load_company_news,
    load_company_news_snapshot,
)
from research_catalog import COMPANY_NAMES


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class CompanyNewsTests(unittest.TestCase):
    def test_blank_cover_does_not_resolve_to_article_url(self):
        article_url = "https://www.reuters.com/business/example-story"

        self.assertEqual(_valid_cover_url("", base_url=article_url), "")

    def test_materiality_terms_use_word_boundaries(self):
        self.assertEqual(_materiality_count("Zach Dell is raising money for a battery startup"), 0)
        self.assertGreater(_materiality_count("Dell raises annual AI revenue forecast"), 0)
        self.assertGreater(_materiality_count("Visa will spend $2.4 billion on BioCatch"), 0)
        self.assertGreater(_materiality_count("Eli Lilly agrees to a $3.8 billion buy"), 0)

    def test_onsemi_alias_does_not_match_generic_semiconductor_phrase(self):
        self.assertNotIn("ON Semiconductor", SEARCH_ALIASES["ON"])

    def test_reuters_canonical_url_corrects_feed_date(self):
        fallback = datetime(2026, 9, 7, tzinfo=timezone.utc)

        corrected = _dated_article_time(
            "https://www.reuters.com/technology/example-story-2026-09-08/",
            fallback,
        )

        self.assertEqual(corrected.date().isoformat(), "2026-09-08")

    def test_every_prebuilt_company_has_specific_news_search_metadata(self):
        self.assertEqual(set(SEARCH_ALIASES), set(COMPANY_NAMES))
        self.assertEqual(set(OFFICIAL_DOMAINS_BY_TICKER), set(COMPANY_NAMES))
        for ticker in ("V", "ON", "NOW", "ARM", "GFS", "VRT", "GEV"):
            with self.subTest(ticker=ticker):
                self.assertNotIn(ticker.lower(), {alias.lower() for alias in SEARCH_ALIASES[ticker]})

    def test_excludes_outdated_and_low_value_articles(self):
        rss = b"""<?xml version='1.0' encoding='UTF-8'?>
        <rss xmlns:media="http://search.yahoo.com/mrss/"><channel>
          <item><title>Marvell raises annual forecast as AI demand expands - Reuters</title><link>https://news.google.com/articles/recent</link><pubDate>Thu, 27 Aug 2026 12:00:00 GMT</pubDate><source url="https://www.reuters.com">Reuters</source><media:content url="https://cdn.reuters.com/marvell-cover.jpg" medium="image" /></item>
          <item><title>Marvell Technology Inc. stock price today - WSJ</title><link>https://news.google.com/articles/quote</link><pubDate>Thu, 20 Aug 2026 12:00:00 GMT</pubDate><source url="https://www.wsj.com">WSJ</source></item>
          <item><title>Marvell completes acquisition - Reuters</title><link>https://news.google.com/articles/old</link><pubDate>Wed, 18 Dec 2019 12:00:00 GMT</pubDate><source url="https://www.reuters.com">Reuters</source></item>
        </channel></rss>"""
        now = datetime(2026, 8, 28, tzinfo=timezone.utc)
        with (
            patch("urllib.request.urlopen", return_value=_Response(rss)),
            patch("news_connector._load_bing_company_news", return_value=[]),
            patch("news_connector._decode_google_news_url", return_value="https://www.reuters.com/article/recent"),
            patch(
                "news_connector._article_metadata",
                return_value=("https://www.reuters.com/article/recent", "https://cdn.reuters.com/marvell-cover.jpg"),
            ),
        ):
            results = load_company_news("Marvell Technology, Inc.", "MRVL", now=now)

        self.assertEqual([item["date"] for item in results], ["2026-08-27"])
        self.assertIn("annual forecast", results[0]["title"])
        self.assertEqual(results[0]["image"], "https://cdn.reuters.com/marvell-cover.jpg")
        self.assertEqual(results[0]["image_kind"], "article")

    def test_decodes_google_news_url_to_original_publisher(self):
        data_id = "encoded-article-id"
        page = (
            f'<div data-n-a-id="{data_id}" data-n-a-ts="1788044507" '
            'data-n-a-sg="article-signature"></div>'
        ).encode()
        inner = json.dumps(["unused", "https://www.reuters.com/business/example"])
        rpc = ("\n" + json.dumps([["wrb.fr", "Fbv4je", inner]])).encode()

        with patch(
            "urllib.request.urlopen",
            side_effect=[_Response(page), _Response(rpc)],
        ):
            decoded = _decode_google_news_url(f"https://news.google.com/rss/articles/{data_id}")

        self.assertEqual(decoded, "https://www.reuters.com/business/example")

    def test_google_supplements_a_partial_bing_result(self):
        rss = b"""<?xml version='1.0' encoding='UTF-8'?>
        <rss xmlns:media="http://search.yahoo.com/mrss/"><channel>
          <item><title>Microsoft launches a new cloud product - Reuters</title><link>https://news.google.com/articles/cloud</link><pubDate>Thu, 27 Aug 2026 12:00:00 GMT</pubDate><source url="https://www.reuters.com">Reuters</source><media:content url="https://cdn.reuters.com/microsoft-cloud.jpg" medium="image" /></item>
        </channel></rss>"""
        bing_story = {
            "title": "Microsoft reports quarterly earnings",
            "url": "https://www.reuters.com/business/microsoft-earnings",
            "publisher": "Reuters",
            "date": "2026-08-26",
            "image": "https://cdn.reuters.com/microsoft-earnings.jpg",
            "image_kind": "article",
        }
        now = datetime(2026, 8, 28, tzinfo=timezone.utc)
        with (
            patch("urllib.request.urlopen", return_value=_Response(rss)),
            patch("news_connector._load_bing_company_news", return_value=[bing_story]),
            patch("news_connector._decode_google_news_url", return_value="https://www.reuters.com/business/microsoft-cloud"),
            patch(
                "news_connector._article_metadata",
                return_value=("https://www.reuters.com/business/microsoft-cloud", "https://cdn.reuters.com/microsoft-cloud.jpg"),
            ),
        ):
            results = load_company_news("Microsoft Corporation", "MSFT", now=now)

        self.assertEqual(len(results), 2)
        self.assertEqual(
            {item["title"] for item in results},
            {"Microsoft reports quarterly earnings", "Microsoft launches a new cloud product"},
        )

    def test_bing_index_keeps_original_article_and_specific_thumbnail(self):
        rss = b"""<?xml version='1.0' encoding='UTF-8'?>
        <rss xmlns:News="https://www.bing.com/news"><channel>
          <item><title>Microsoft launches a new AI chip</title>
          <link>https://www.bing.com/news/apiclick.aspx?url=https%3A%2F%2Fwww.reuters.com%2Fbusiness%2Fmicrosoft-ai-chip</link>
          <pubDate>Mon, 10 Aug 2026 12:00:00 GMT</pubDate>
          <News:Image>http://www.bing.com/th?id=ONUT.article-specific&amp;pid=News</News:Image></item>
        </channel></rss>"""
        now = datetime(2026, 8, 28, tzinfo=timezone.utc)
        with patch("urllib.request.urlopen", side_effect=[_Response(rss), _Response(rss)]):
            results = load_company_news("Microsoft Corporation", "MSFT", now=now)

        self.assertEqual(results[0]["url"], "https://www.reuters.com/business/microsoft-ai-chip")
        self.assertIn("ONUT.article-specific", results[0]["image"])
        self.assertIn("w=1200", results[0]["image"])
        self.assertIn("h=675", results[0]["image"])

    def test_snapshot_fallback_keeps_only_current_verified_articles(self):
        payload = {
            "generated_at": "2026-08-28T12:00:00+00:00",
            "window_days": 90,
            "companies": {
                "MRVL": [
                    {
                        "title": "Marvell expands AI data center partnership",
                        "url": "https://www.reuters.com/business/marvell-ai",
                        "publisher": "Reuters",
                        "date": "2026-08-27",
                        "image": "https://cdn.reuters.com/marvell-ai.jpg",
                        "image_kind": "article",
                    },
                    {
                        "title": "Outdated Marvell story",
                        "url": "https://www.reuters.com/business/marvell-old",
                        "publisher": "Reuters",
                        "date": "2025-08-27",
                        "image": "https://cdn.reuters.com/marvell-old.jpg",
                        "image_kind": "article",
                    },
                    {
                        "title": "Broken Marvell cover",
                        "url": "https://www.reuters.com/business/marvell-broken-cover",
                        "publisher": "Reuters",
                        "date": "2026-08-27",
                        "image": "https://www.reuters.com/business/marvell-broken-cover",
                        "image_kind": "article",
                    },
                ]
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recent_news.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            results = load_company_news_snapshot(
                "MRVL",
                now=datetime(2026, 8, 28, tzinfo=timezone.utc),
                path=path,
            )

        self.assertEqual([story["title"] for story in results], ["Marvell expands AI data center partnership"])

    def test_snapshot_fallback_orders_newest_articles_first(self):
        payload = {
            "companies": {
                "MRVL": [
                    {
                        "title": "Marvell launches AI data center product",
                        "url": "https://www.reuters.com/business/marvell-product",
                        "publisher": "Reuters",
                        "date": "2026-08-20",
                        "image": "https://cdn.reuters.com/marvell-product.jpg",
                        "image_kind": "article",
                    },
                    {
                        "title": "Marvell reports quarterly revenue growth",
                        "url": "https://www.reuters.com/business/marvell-results",
                        "publisher": "Reuters",
                        "date": "2026-08-27",
                        "image": "https://cdn.reuters.com/marvell-results.jpg",
                        "image_kind": "article",
                    },
                ]
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recent_news.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            results = load_company_news_snapshot(
                "MRVL",
                now=datetime(2026, 8, 28, tzinfo=timezone.utc),
                path=path,
            )

        self.assertEqual([story["date"] for story in results], ["2026-08-27", "2026-08-20"])


if __name__ == "__main__":
    unittest.main()
