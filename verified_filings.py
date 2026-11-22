"""Issuer statements checked against SEC filing exhibits; amounts follow the units below.

These dated observations can fill gaps when automated feeds are incomplete.
The 10-K checks cover revenue, cash purchases of PP&E and reporting dates.
Four 2026 10-Ks also have consolidated statement values for a full-row comparison.
Annual earnings releases are identified separately until an annual report supersedes them.
"""


def _filing_url(cik, accession, document):
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{document}"


def _quarter(label, start, end, filed, form, cik, accession, document, currency,
             revenue, operating_income, net_income):
    return {
        "label": label, "period_start": start, "period_end": end, "filed": filed, "form": form,
        "accession": accession, "url": _filing_url(cik, accession, document), "currency": currency,
        "unit": "millions", "revenue": revenue, "operating_income": operating_income,
        "net_income": net_income,
    }


VERIFIED_QUARTERS = {
    "TER": {
        **_quarter(
            "Q3 FY2026", "2026-06-29", "2026-09-27", "2026-10-30", "10-Q",
            97210, "0001193125-26-441091", "ter-20260927.htm", "USD", 1305.950, 401.968, 347.739,
        ),
        "note": "Net income uses consolidated net income before allocating noncontrolling interests.",
    },
    "AAPL": _quarter(
        "Q4 FY2026", "2026-06-28", "2026-09-26", "2026-11-02", "8-K Exhibit 99.1",
        320193, "0000320193-26-000024", "a8-kex991q4202609262026.htm",
        "USD", 114477, 35631, 30711,
    ),
    "AMAT": _quarter(
        "Q4 FY2026", "2026-07-27", "2026-10-25", "2026-11-12", "8-K Exhibit 99.1",
        6951, "0001628280-26-073360", "exhibit991q42026earningsre.htm", "USD", 10409, 3658, 2718,
    ),
    "AMD": _quarter(
        "Q3 2026", "2026-06-28", "2026-09-26", "2026-11-04", "10-Q",
        2488, "0000002488-26-000191", "amd-20260926.htm", "USD", 13377, 2832, 2428,
    ),
    "AMZN": _quarter(
        "Q3 2026", "2026-07-01", "2026-09-30", "2026-10-30", "10-Q",
        1018724, "0001018724-26-000040", "amzn-20260930.htm", "USD", 201944, 28076, 20685,
    ),
    "ASML": _quarter(
        "Q3 2026", "2026-06-29", "2026-09-27", "2026-10-14", "6-K Exhibit 99.3",
        937966, "0001628280-26-065813", "financial_statementsxusx.htm",
        "EUR", 11662.0, 5172.8, 4960.4,
    ),
    "GOOG": _quarter(
        "Q3 2026", "2026-07-01", "2026-09-30", "2026-10-29", "10-Q",
        1652044, "0001652044-26-000084", "goog-20260930.htm", "USD", 127577, 40576, 26468,
    ),
    "LITE": _quarter(
        "Q1 FY2027", "2026-06-28", "2026-09-26", "2026-11-03", "10-Q",
        1633978, "0001628280-26-069615", "lite-20260926.htm", "USD", 1262.6, 359.8, 360.3,
    ),
    "META": _quarter(
        "Q3 2026", "2026-07-01", "2026-09-30", "2026-10-22", "10-Q",
        1326801, "0001628280-26-066773", "meta-20260930.htm", "USD", 64601, 12988, 9860,
    ),
    "MSFT": _quarter(
        "Q1 FY2027", "2026-07-01", "2026-09-30", "2026-10-28", "10-Q",
        789019, "0001193125-26-436133", "msft-20260930.htm", "USD", 92279, 45915, 36629,
    ),
    "NVDA": _quarter(
        "Q3 FY2027", "2026-07-27", "2026-10-25", "2026-11-17", "8-K Exhibit 99.3",
        1045810, "0001045810-26-000088", "supplementalfinancialinfor.htm", "USD", 115844, 77520, 65287,
    ),
    "SNDK": _quarter(
        "Q1 FY2027", "2026-07-04", "2026-10-02", "2026-10-30", "10-Q",
        2023554, "0001628280-26-068601", "sndk-20261002.htm", "USD", 11031, 8780, 8101,
    ),
    "TSM": {
        **_quarter(
            "Q3 2026", "2026-07-01", "2026-09-30", "2026-10-15", "6-K Exhibit 99.1",
            1046179, "0001046179-26-000726", "a3q26e_withguidancexfinal.htm",
            "TWD", 1494243, 876445, 763064,
        ),
        "note": "Net income is attributable to shareholders of the parent.",
    },
}


def _annual(end, filed, cik, accession, document, revenue, capex, line_item):
    return {
        "fiscal_year_end": end, "filed": filed, "form": "10-K", "accession": accession,
        "url": _filing_url(cik, accession, document), "currency": "USD", "unit": "units",
        "revenue": revenue, "capex": capex, "capex_accession": accession,
        "capex_xbrl_tag": f"Primary filing table: {line_item}",
    }


VERIFIED_ANNUALS = {
    ("AAPL", 2026): _annual(
        "2026-09-26", "2026-11-03", 320193, "0000320193-26-000026", "aapl-20260926.htm",
        478_834_000_000, 9_041_000_000, "Payments for acquisition of property, plant and equipment",
    ),
    ("QCOM", 2026): _annual(
        "2026-09-27", "2026-11-04", 804328, "0000804328-26-000128", "qcom-20260927.htm",
        43_120_000_000, 2_494_000_000, "Capital expenditures",
    ),
    ("MU", 2026): _annual(
        "2026-09-03", "2026-10-09", 723125, "0000723125-26-000023", "mu-20260903.htm",
        133_188_000_000, 30_712_000_000, "Expenditures for property, plant, and equipment",
    ),
    ("MTSI", 2026): _annual(
        "2026-10-02", "2026-11-12", 1493594, "0001493594-26-000044", "mtsi-20261002.htm",
        1_327_623_000, 64_420_000, "Purchases of property and equipment",
    ),
    ("MTSI", 2025): _annual(
        "2025-10-03", "2025-11-14", 1493594, "0001493594-25-000054", "mtsi-20251003.htm",
        967_258_000, 42_551_000, "Purchases of property and equipment",
    ),
    ("MTSI", 2024): _annual(
        "2024-09-27", "2024-11-12", 1493594, "0001493594-24-000060", "mtsi-20240927.htm",
        729_578_000, 22_440_000, "Purchases of property and equipment",
    ),
}


def _statement(scale, gross_profit, cost_of_revenue, operating_income, net_income,
               operating_cash_flow, assets, liabilities, equity):
    return {field: amount * scale for field, amount in {
        "gross_profit": gross_profit, "cost_of_revenue": cost_of_revenue,
        "operating_income": operating_income, "net_income": net_income,
        "operating_cash_flow": operating_cash_flow, "assets": assets,
        "liabilities": liabilities, "equity": equity,
    }.items()}


# The amounts below follow the units printed on the financial statements.
# QCOM gross profit equals total revenues less cost of revenues.
VERIFIED_ANNUALS[("AAPL", 2026)]["statement_values"] = _statement(
    1_000_000, 233602, 245232, 158063, 132175, 145097, 404548, 292455, 112093,
)
VERIFIED_ANNUALS[("MTSI", 2026)]["statement_values"] = _statement(
    1_000, 770396, 557227, 305467, 335251, 357086, 2322851, 626184, 1696667,
)
VERIFIED_ANNUALS[("MU", 2026)]["statement_values"] = _statement(
    1_000_000, 107504, 25684, 99340, 84969, 89675, 195888, 57510, 138378,
)
VERIFIED_ANNUALS[("QCOM", 2026)]["statement_values"] = _statement(
    1_000_000, 22898, 20222, 8658, 13628, 11145, 60829, 30428, 30401,
)


# Issuer's unaudited consolidated statements in the SEC-furnished
# earnings release. All flow metrics use the twelve-month column, in whole USD.
_amat_release = VERIFIED_QUARTERS["AMAT"]
VERIFIED_ANNUAL_RELEASES = {
    ("AMAT", 2026): {
        "ticker": "AMAT", "company": "Applied Materials, Inc.", "fiscal_year": 2026,
        "fiscal_year_end": _amat_release["period_end"], "filed": _amat_release["filed"],
        "form": _amat_release["form"], "accession": _amat_release["accession"],
        "source_url": _amat_release["url"], "currency": "USD",
        "revenue": 34_446_000_000, "gross_profit": 17_219_000_000, "cost_of_revenue": 17_227_000_000,
        "operating_income": 11_087_000_000, "net_income": 10_088_000_000,
        "operating_cash_flow": 8_868_000_000, "capex": 2_672_000_000,
        "assets": 45_400_000_000, "liabilities": 19_294_000_000, "equity": 26_106_000_000,
        "capex_xbrl_tag": "Unaudited earnings release: Capital expenditures",
        "capex_accession": _amat_release["accession"], "revenue_accession": _amat_release["accession"],
    },
}
