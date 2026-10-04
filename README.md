# The Company

**Fundamentals, Accounting Quality, Market Performance & Valuation · Version 2.1**

The Company is a public-source research system for U.S.-listed companies. It separates reported facts, deterministic calculations, dated market observations, accounting-quality signals and analytical scenarios.

- **Live application:** [Open The Company](https://company-financial-research-auto.streamlit.app/)
- **Unified research desk:** [Open The Research Desk](https://research-systems-lab.william-liao818.chatgpt.site/)

## Prebuilt research packs

Fifty companies are bundled as ready-to-use snapshots and require no API key. The expanded universe follows the cloud, AI-compute and semiconductor value chain while adding a small set of cross-sector companies for comparison:

- **Cloud and software:** MSFT, ORCL, GOOG, AMZN, META, CRM, NOW, PANW and PLTR;
- **Semiconductors:** AVGO, SNDK, NVDA, MRVL, LITE, TSM, AMD, INTC, QCOM, MU, TXN, ADI, NXPI, ARM, MCHP, ON, GFS and WDC;
- **Chip equipment, design and manufacturing support:** AMAT, ASML, KLAC, LRCX, TER, CDNS, SNPS, AMKR, ENTG and COHR;
- **Systems and infrastructure:** AAPL, ANET, CSCO, DELL, HPE, VRT and SMCI;
- **Cross-sector complements:** TSLA, V, LLY, WMT, GEV and CAT.

Each pack includes:

- an executive thesis and counter-thesis;
- pivotal questions and explicit decision rules;
- business-model-specific indicators and diligence questions;
- multi-year earnings, margin, cash-flow and balance-sheet diagnostics;
- a separate native-currency snapshot of the latest explicitly reported quarter;
- deterministic accounting-quality signals;
- reported-to-analytical cash-flow normalization where sourced;
- selected peer context, a dated market-share view where available and a revisable competitive-position rubric;
- up to ten years of adjusted share-price performance against SPY and QQQ;
- a rolling three-month monitor of material coverage from established publications;
- recent institutional target-price observations with dates and a separate Bear/Base/Bull analytical range;
- transparent operating scenarios and valuation sensitivity;
- catalysts, downside risks and an updateable monitoring dashboard;
- direct links to recent 10-K/10-Q or 20-F/6-K filings;
- a chart-led PDF with a table of contents, available after opening the company view.

The bundled annual series and the latest official quarter are intentionally separated. Annual charts remain comparable across fiscal years; the latest-quarter cards use explicit three-month statement columns and link directly to the verified 10-Q, 6-K or SEC-filed earnings exhibit. They are never annualized or substituted into annual history.

## Analyze another U.S. public company

The first page uses one ticker/company search. Prebuilt packs open immediately. For another U.S.-listed company, users may choose either a user-supplied Financial Modeling Prep key for normalized annual statements or the SEC Company Facts path for core annual facts. Provider keys are password-masked, used only for the current request and never written to the repository.

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
