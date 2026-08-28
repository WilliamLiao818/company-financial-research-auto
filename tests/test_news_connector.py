from __future__ import annotations

import io
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from news_connector import load_company_news


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class CompanyNewsTests(unittest.TestCase):
    def test_excludes_outdated_and_low_value_articles(self):
        rss = b"""<?xml version='1.0' encoding='UTF-8'?>
        <rss><channel>
          <item><title>Marvell raises annual forecast as AI demand expands - Reuters</title><link>https://news.google.com/articles/recent</link><pubDate>Thu, 27 Aug 2026 12:00:00 GMT</pubDate><source url="https://www.reuters.com">Reuters</source></item>
          <item><title>Marvell Technology Inc. stock price today - WSJ</title><link>https://news.google.com/articles/quote</link><pubDate>Thu, 20 Aug 2026 12:00:00 GMT</pubDate><source url="https://www.wsj.com">WSJ</source></item>
          <item><title>Marvell completes acquisition - Reuters</title><link>https://news.google.com/articles/old</link><pubDate>Wed, 18 Dec 2019 12:00:00 GMT</pubDate><source url="https://www.reuters.com">Reuters</source></item>
        </channel></rss>"""
        now = datetime(2026, 8, 28, tzinfo=timezone.utc)
        with patch("urllib.request.urlopen", return_value=_Response(rss)):
            results = load_company_news("Marvell Technology, Inc.", "MRVL", now=now)

        self.assertEqual([item["date"] for item in results], ["2026-08-27"])
        self.assertIn("annual forecast", results[0]["title"])


if __name__ == "__main__":
    unittest.main()
