# The Company

**Fundamentals, Accounting Quality & 12-Month View · Version 2.0**

The Company is a public-source research system for U.S.-listed companies. It separates reported facts, deterministic calculations, dated market observations, accounting-quality signals and analytical scenarios.

- **Live application:** [Open The Company](https://company-financial-research-auto.streamlit.app/)
- **Unified research desk:** [Open The Research Desk](https://research-systems-lab.william-liao818.chatgpt.site/)

## Prebuilt research packs

MSFT, ORCL, GOOG, AVGO, SNDK and NVDA are bundled as ready-to-use snapshots and require no API key. Each pack includes:

- an executive thesis and counter-thesis;
- pivotal questions and explicit decision rules;
- business-model-specific indicators and diligence questions;
- multi-year earnings, margin, cash-flow and balance-sheet diagnostics;
- deterministic accounting-quality signals;
- reported-to-analytical cash-flow normalization where sourced;
- selected peer context, a sourced market-share view and a revisable competitive-position rubric;
- recent institutional target-price observations with dates and a separate Bear/Base/Bull analytical range;
- transparent operating scenarios and valuation sensitivity;
- catalysts, downside risks and an updateable monitoring dashboard;
- direct links to recent 10-K and 10-Q filings;
- a 12-page chart-led PDF available from the landing page and the company view.

## Analyze another U.S. public company

The first page uses one ticker/company search. Prebuilt packs open immediately. For another U.S.-listed company, users may choose either a user-supplied Financial Modeling Prep key for normalized annual statements or the SEC Company Facts path for core annual facts. Provider keys are password-masked, used only for the current request and never written to the repository.

The webpage and PDF share the same architecture: executive view, business and moat, earnings, cash and accounting quality, competition, 12-month view, scenario analysis, catalysts and risks, and filing access. Technical appendices are intentionally kept out of the main interface.

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
