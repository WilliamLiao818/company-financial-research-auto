from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from news_connector import _decode_google_news_url, load_company_news


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class CompanyNewsTests(unittest.TestCase):
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

    def test_bing_index_keeps_original_article_and_specific_thumbnail(self):
        rss = b"""<?xml version='1.0' encoding='UTF-8'?>
        <rss xmlns:News="https://www.bing.com/news"><channel>
          <item><title>Microsoft launches a new AI chip</title>
          <link>https://www.bing.com/news/apiclick.aspx?url=https%3A%2F%2Fwww.reuters.com%2Fbusiness%2Fmicrosoft-ai-chip</link>
          <pubDate>Mon, 10 Aug 2026 12:00:00 GMT</pubDate>
          <News:Image>http://www.bing.com/th?id=ONUT.article-specific&amp;pid=News</News:Image></item>
        </channel></rss>"""
        now = datetime(2026, 8, 28, tzinfo=timezone.utc)
        with patch("urllib.request.urlopen", return_value=_Response(rss)):
            results = load_company_news("Microsoft Corporation", "MSFT", now=now)

        self.assertEqual(results[0]["url"], "https://www.reuters.com/business/microsoft-ai-chip")
        self.assertIn("ONUT.article-specific", results[0]["image"])
        self.assertIn("w=1200", results[0]["image"])
        self.assertIn("h=675", results[0]["image"])


if __name__ == "__main__":
    unittest.main()
