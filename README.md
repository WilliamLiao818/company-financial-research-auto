# The Company

**Fundamentals, Accounting Quality, Market Performance & Valuation · Version 2.1**

The Company is a public-source research system for U.S.-listed companies. It separates reported facts, deterministic calculations, dated market observations, accounting-quality signals and analytical scenarios.

- **Live application:** [Open The Company](https://company-financial-research-auto.streamlit.app/)
- **Unified research desk:** [Open The Research Desk](https://liaoresearch.com/)

## Prebuilt research packs

128 companies are bundled as ready-to-use snapshots and require no API key. The universe preserves the original 50 and adds 78 companies across nine research sectors. It follows the cloud, AI-compute and semiconductor value chain while adding healthcare, industrial, consumer and energy businesses:

- **Cloud and software (22):** ACN, ADBE, ADSK, AMZN, CRM, CRWD, DDOG, FTNT, GOOG, IBM, INTU, MDB, META, MSFT, NET, NOW, ORCL, PANW, PLTR, SNOW, TEAM, ZS.
- **Semiconductors (25):** ADI, ALGM, AMD, ARM, AVGO, CRUS, GFS, INTC, LITE, LSCC, MCHP, MPWR, MRVL, MTSI, MU, NVDA, NXPI, ON, QCOM, RMBS, SNDK, STM, SWKS, TSM, TXN.
- **Chip equipment, design and manufacturing support (10):** AMAT, AMKR, ASML, CDNS, COHR, ENTG, KLAC, LRCX, SNPS, TER.
- **Systems and infrastructure (10):** AAPL, ANET, CSCO, DELL, FN, HPE, SMCI, STX, VRT, WDC.
- **Digital platforms and payments (8):** ABNB, BKNG, NFLX, PYPL, SHOP, SPOT, UBER, V.
- **Healthcare and life sciences (17):** ABBV, ABT, AMGN, AZN, BSX, DHR, GILD, ISRG, JNJ, LLY, MDT, MRK, NVO, PFE, REGN, TMO, VRTX.
- **Industrials and aerospace (15):** CAT, CMI, DE, EMR, ETN, GD, GE, GEV, HON, LMT, NOC, PH, ROK, RTX, TSLA.
- **Consumer and retail (13):** CL, COST, DIS, HD, KO, LOW, MCD, NKE, PEP, PG, SBUX, TGT, WMT.
- **Energy and utilities (8):** COP, CVX, DUK, EOG, NEE, SLB, SO, XOM.

Each added company has its own business description, operating drivers, KPI checklist, risk and selected peer context. A selected peer can be a customer, supplier or adjacent business rather than a strict valuation comparable. Banks and insurers are excluded because their balance sheets and cash-flow economics require a different analytical model. No competitive scores, quarterly figures, institutional targets or market shares are synthesized to fill missing coverage. Scenario starting points are editable sector stress-test assumptions, not company forecasts.

Each pack includes:

- an executive thesis and counter-thesis;
- pivotal questions and explicit decision rules;
- business-model-specific indicators and diligence questions;
- multi-year earnings, margin, cash-flow and balance-sheet diagnostics;
- a separate native-currency quarterly snapshot where an explicitly verified update is available;
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

The bundled annual series and the latest official quarter are intentionally separated. Annual charts remain comparable across fiscal years; the latest-quarter cards use explicit three-month statement columns and link directly to the verified 10-Q, 6-K or SEC-filed earnings exhibit. They are never annualized or substituted into annual history.

## Analyze another U.S. public company

The first page uses one ticker/company search. Prebuilt packs open immediately. For another U.S.-listed company, users may choose either a user-supplied Financial Modeling Prep key for normalized annual statements or the SEC Company Facts path for core annual facts. Provider keys are password-masked, used only for the current request and never written to the repository.

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
