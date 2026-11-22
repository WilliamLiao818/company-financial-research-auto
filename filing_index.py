"""Read public filing identifiers from Listed's EDGAR distribution, with its own reconciliation time.

API and public-data terms: https://www.listed.markets/developers
https://www.listed.markets/legal/agent-api-terms
"""
from datetime import date, datetime, timezone
import json
import re
from time import monotonic, sleep
from urllib.error import HTTPError
from urllib.request import Request, urlopen


FORMS = ("10-K", "10-Q", "8-K", "20-F", "6-K", "40-F")
API = "https://www.listed.markets/api/v1/companies"


def parse_index(profile, rows, ticker, cik, today):
    cik = int(cik)
    if (profile.get("cik") != cik or ticker not in profile.get("tickers", [])
            or profile.get("source", {}).get("name") != "SEC EDGAR"):
        raise ValueError("Unrecognized company filing index")
    indexed = datetime.fromisoformat(profile["source"]["submissions_updated_at"].replace("Z", "+00:00"))
    if indexed.tzinfo is None or indexed.astimezone(timezone.utc).date() > today:
        raise ValueError("Invalid filing-index reconciliation time")
    accepted_rows = []
    for row in rows.get("filings", []):
        accession = row.get("accession", "")
        if row.get("form", "").removesuffix("/A") not in FORMS or row.get("company", {}).get("cik") != cik:
            continue
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
            continue
        filed = date.fromisoformat(row["filed"])
        if filed > today:
            continue
        directory = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
        if row.get("source_url") != directory:
            continue
        accepted_rows.append((filed, row["accepted_at"], {
            "filed": filed.isoformat(), "form": row["form"], "accession": accession,
            "url": f"{directory}{accession}-index.htm",
        }))
    if not accepted_rows:
        raise ValueError("No matching public EDGAR filing")
    return {"filing": max(accepted_rows, key=lambda item: item[:2])[2],
            "indexed_at": indexed.astimezone(timezone.utc).isoformat(), "source": "SEC EDGAR via Listed"}


class ListedIndex:
    def __init__(self):
        self.stopped = False
        self.last_request = 0.0

    def _get(self, url):
        if self.stopped:
            raise RuntimeError("Filing distribution unavailable for this run")
        sleep(max(0, 1 + self.last_request - monotonic()))
        self.last_request = monotonic()
        request = Request(url, headers={"Accept": "application/json",
                          "User-Agent": "LiaoResearch/1.0 (+https://liaoresearch.com)"})
        try:
            with urlopen(request, timeout=18) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code in (403, 429):
                self.stopped = True
            raise

    def fetch(self, ticker, cik, today):
        if not re.fullmatch(r"[A-Z0-9.-]{1,12}", ticker):
            raise ValueError("Invalid ticker")
        base = f"{API}/{ticker.lower()}"
        return parse_index(self._get(base), self._get(f"{base}/filings?limit=100"), ticker, cik, today)
