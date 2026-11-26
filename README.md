# The Company

**Fundamentals, Accounting Quality, Market Performance & Valuation · Version 2.1**

The Company is a public-source research system for U.S.-listed companies. It separates reported facts, deterministic calculations, dated market observations, accounting-quality signals and analytical scenarios.

- **Live application:** [Open The Company](https://company-financial-research-auto.streamlit.app/)
- **Unified research desk:** [Open The Research Desk](https://liaoresearch.com/)

## Prebuilt research packs

The public company workspace covers 48 U.S.-listed companies across six roles:

| Research role | Companies |
| --- | --- |
| Compute & chip design | AAPL, AMD, ARM, AVGO, INTC, LSCC, MRVL, NVDA, QCOM |
| Foundry, equipment & EDA | AMAT, AMKR, ASML, CDNS, ENTG, GFS, KLAC, LRCX, SNPS, TER, TSM |
| Memory & storage | MU, RMBS, SNDK, STX, WDC |
| Networking & optics | ANET, COHR, CSCO, FN, LITE, MTSI |
| Servers, power & cooling | ADI, DELL, ETN, HPE, MPWR, SMCI, TXN, VRT |
| Cloud & AI platforms | AMZN, GOOG, IBM, META, MSFT, NET, ORCL, PLTR, SNOW |

Each pack names the specific product or activity that qualifies the company for coverage. Apple designs silicon for on-device inference, while Alphabet, Amazon and Oracle build and operate cloud infrastructure. Financial statements cover the entire issuer. The research role does not measure the share of its revenue attributable to AI.

The active list and role descriptions live in `focus_coverage.py`. The application, peer tables, PDF exports and scheduled refreshes use this coverage list. Historical public statements for companies outside the current focus remain available in the repository's data history.

Each pack includes:

- an executive thesis and counter-thesis;
- pivotal questions and explicit decision rules;
- business-model-specific indicators and diligence questions;
- multi-year earnings, margin, cash-flow and balance-sheet diagnostics;
- a separate quarterly snapshot with source, period precision and reporting currency;
- deterministic accounting-quality signals;
- reported-to-analytical cash-flow normalization where sourced;
- selected peer context, with dated market share and a revisable competitive-position rubric only where separately available;
- up to ten years of adjusted share-price performance against SPY and QQQ;
- a rolling three-month monitor of material coverage from established publications;
- recent institutional target-price observations and a separate Bear/Base/Bull analytical range where a dated snapshot is available;
- transparent operating scenarios and valuation sensitivity;
- catalysts, downside risks and an updateable monitoring dashboard;
- direct links to recent 10-K/10-Q or 20-F/6-K filings;
- a chart-led PDF with a table of contents, available after opening the company view.

Quarterly observations have independent dates, units and sources. Filed three-month figures take priority for the same quarter. A newer Yahoo Finance quarterly statement can fill an issuer coverage gap. Provider figures carry a reporting month and omit unverified filing and period-start dates. Annual charts and the valuation anchor continue to use fiscal-year results.

## Public-data boundary

The public application accepts only an explicit allowlist of company financial-statement and filing-provenance fields. Unsupported columns are rejected before they can enter the research session or a PDF export. The deployed application has no connection to personal accounts, portfolios, orders, transactions or individually tailored investment data.

The webpage and PDF share the same architecture: executive view, business and moat, financials and accounting quality, competition, long-term market performance, valuation and scenarios, catalysts and risks, and filing access. Technical appendices are intentionally kept out of the main interface.

## Accounting Quality & Normalization

The system flags review work rather than alleging misconduct. Current deterministic checks include:

- capex acceleration and simple-FCF pressure;
- cash-conversion divergence;
- standardized fact gaps;
- cash-flow classification effects supported by filing notes;
- missing or incompatible standardized facts.

For MSFT, the prebuilt pack presents finance-lease principal as an analytical cash-flow adjustment because the filed principal payment sits in financing cash flow and is excluded from conventional CFO-minus-capex FCF. The adjustment is clearly labeled as an analytical view, not a restatement.

## Research contract

- Missing or incompatible XBRL facts remain missing.
- Derived metrics use published deterministic formulas.
- User-selected peers are not automatically declared strict comparables.
- Institutional targets are dated external observations; The Company range is an explicit analytical scenario.
- Scenario ranges are not recommendations or probabilities.
- Important conclusions must be checked against the original filing.

## Local use

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Run the test suite with:

```bash
python -m unittest discover -s tests -v
```

This system supports research and review. It does not provide transaction instructions or individually tailored advice.

## Data updates

The default branch's **Refresh public company data** workflow checks all 48 active issuers daily at 03:37 UTC. On weekdays it also checks filings at 13:13, 15:13, 17:13, 19:13, 21:13 and 23:13 UTC and checks news thirty minutes later. GitHub may start scheduled runs later. A manual dispatch can refresh filings, prices, news or all three. Validated changes and per-company check dates publish together to the branch read by Streamlit and the public company briefs.

- **Reports.** The SEC submissions feed covers periodic and current U.S. and foreign issuer filings, including 10-Q, 10-K, 8-K, 6-K and 20-F. If direct access fails, the Listed public index can supply original EDGAR links after issuer and accession checks. Its published reconciliation date is shown separately. An index more than two weekdays behind, or behind a newer filing already on file, is marked delayed. Company Facts supplies comparable annual statements and explicitly tagged three-month figures. Custom tags and exhibit-only earnings can require an individual filing review. Annual statements can fall back to Yahoo Finance's dated normalized statements. Each row retains its provider and reporting currency.
- **Market.** The refresh reads daily adjusted closing observations, including SPY and QQQ, then samples the final available completed session each month. The current month is partial. Common observation dates determine returns. These are end-of-day observations.
- **News.** The refresh checks monitored indexes and original publisher links and keeps qualifying articles within the rolling 90-day window.
- **Failures.** The ledger in `data/refresh_status.json` records observation dates, attempts, last successful checks and retained data separately. Partial source delays or timeouts appear as warnings in the workflow summary and healthy updates can still publish. When an entire feed becomes unavailable across every covered company, its status publishes and the workflow raises one failure for that outage. A successful lookup re-arms this alert. Validation and publication errors fail the run.
- **Contact.** The SEC request identifies the project and its public GitHub Issues contact. A repository variable named `SEC_CONTACT_EMAIL` can specify a project contact monitored by the maintainer. No key is required for EDGAR. Public endpoint access and hosted automation schedules are subject to the providers' availability.
