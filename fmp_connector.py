from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

from research import prepare_financials


BASE_URL = "https://financialmodelingprep.com/stable"


class FmpInputError(ValueError):
    pass


class FmpConnectionError(RuntimeError):
    pass


def _request(endpoint: str, params: dict[str, object], api_key: str) -> object:
    if not api_key.strip():
        raise FmpInputError("Enter your Financial Modeling Prep API key.")
    query = urllib.parse.urlencode({**params, "apikey": api_key.strip()})
    request = urllib.request.Request(
        f"{BASE_URL}/{endpoint}?{query}",
        headers={"Accept": "application/json", "User-Agent": "The-Company-Research-System/2.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise FmpConnectionError("The data provider could not be reached. Check the key and try again.") from error
    if isinstance(payload, dict) and payload.get("Error Message"):
        raise FmpConnectionError(str(payload["Error Message"]))
    return payload


def resolve_symbol(query: str, api_key: str) -> tuple[str, str]:
    cleaned = query.strip()
    if not cleaned:
        raise FmpInputError("Enter a ticker or company name.")
    if cleaned.replace(".", "").replace("-", "").isalnum() and len(cleaned) <= 7 and " " not in cleaned:
        symbol = cleaned.upper()
        profile = _request("profile", {"symbol": symbol}, api_key)
        if isinstance(profile, list) and profile:
            return symbol, str(profile[0].get("companyName") or symbol)
    matches = _request("search-symbol", {"query": cleaned, "limit": 10}, api_key)
    if not isinstance(matches, list):
        raise FmpConnectionError("The provider returned an unexpected search response.")
    for item in matches:
        exchange = str(item.get("exchangeShortName") or item.get("exchange") or "").upper()
        if exchange in {"NASDAQ", "NYSE", "AMEX"}:
            return str(item["symbol"]).upper(), str(item.get("name") or item["symbol"])
    raise FmpInputError("No U.S.-listed operating company matched that search.")


def load_financial_statements(query: str, api_key: str, years: int = 5) -> pd.DataFrame:
    symbol, company_name = resolve_symbol(query, api_key)
    params = {"symbol": symbol, "period": "annual", "limit": max(2, min(years, 10))}
    income = _request("income-statement", params, api_key)
    balance = _request("balance-sheet-statement", params, api_key)
    cash = _request("cash-flow-statement", params, api_key)
    if not all(isinstance(payload, list) for payload in (income, balance, cash)) or not income:
        raise FmpConnectionError("Annual statements were not available for this symbol on the selected plan.")

    def index_by_year(records: list[dict[str, object]]) -> dict[int, dict[str, object]]:
        output: dict[int, dict[str, object]] = {}
        for record in records:
            raw = record.get("fiscalYear") or str(record.get("date", ""))[:4]
            try:
                output[int(raw)] = record
            except (TypeError, ValueError):
                continue
        return output

    income_by_year = index_by_year(income)
    balance_by_year = index_by_year(balance)
    cash_by_year = index_by_year(cash)
    rows = []
    for fiscal_year in sorted(income_by_year)[-years:]:
        inc = income_by_year[fiscal_year]
        bal = balance_by_year.get(fiscal_year, {})
        cfs = cash_by_year.get(fiscal_year, {})
        capex = cfs.get("capitalExpenditure")
        rows.append(
            {
                "ticker": symbol,
                "company": str(inc.get("companyName") or company_name),
                "fiscal_year": fiscal_year,
                "fiscal_year_end": str(inc.get("date") or f"{fiscal_year}-12-31"),
                "filed": str(inc.get("filingDate") or inc.get("acceptedDate") or inc.get("date") or "" )[:10],
                "source_url": f"{BASE_URL}/income-statement?symbol={urllib.parse.quote(symbol)}",
                "revenue": inc.get("revenue"),
                "gross_profit": inc.get("grossProfit"),
                "cost_of_revenue": inc.get("costOfRevenue"),
                "operating_income": inc.get("operatingIncome"),
                "net_income": inc.get("netIncome"),
                "operating_cash_flow": cfs.get("operatingCashFlow") or cfs.get("netCashProvidedByOperatingActivities"),
                "capex": abs(float(capex)) if capex is not None else None,
                "assets": bal.get("totalAssets"),
                "liabilities": bal.get("totalLiabilities"),
                "equity": bal.get("totalStockholdersEquity") or bal.get("totalEquity"),
            }
        )
    if not rows:
        raise FmpConnectionError("No annual statement periods were returned.")
    return prepare_financials(pd.DataFrame(rows), input_source="user_provider_session")
