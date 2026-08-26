# The Company

**Fundamentals & Accounting Quality · Version 2.0**

The Company is an evidence-linked research system for U.S. public-company fundamentals. It separates reported SEC facts, deterministic calculations, accounting-quality signals, analytical normalization and user assumptions.

- **Live application:** [Open The Company](https://company-financial-research-auto.streamlit.app/)
- **Unified research desk:** [Open The Research Desk](https://research-systems-lab.william-liao818.chatgpt.site/)

## Prebuilt research packs

MSFT and ORCL are bundled as verified snapshots and require no API key. Each pack includes:

- an executive thesis and counter-thesis;
- pivotal questions and explicit decision rules;
- business-model-specific indicators and diligence questions;
- multi-year earnings, margin, cash-flow and balance-sheet diagnostics;
- deterministic accounting-quality signals;
- reported-to-analytical cash-flow normalization where sourced;
- quantitative peer context and a revisable competitive-position rubric;
- transparent operating scenarios and valuation sensitivity;
- catalysts, downside risks and an updateable monitoring dashboard;
- a claim-level evidence and review queue;
- a 12-page chart-led PDF, fact ledger, review queue and run-record downloads.

## Analyze another U.S. public company

The first page explains all four modes and their exact input requirements. The public SEC connector accepts a ticker or CIK and does not require a commercial key. SEC availability and an identifiable `SEC_USER_AGENT` are required. Users may also upload a saved SEC Company Facts JSON or a documented same-schema CSV. Uploaded files are processed in session memory and are not written by the application.

The webpage and PDF share the same institutional research architecture: executive view, business and moat, earnings, cash and accounting quality, peers, scenario analysis, catalysts and risks, and evidence. Raw financial rows, formulas and source records stay inside downloadable files or collapsed appendices.

## Accounting Quality & Normalization

The system flags review work rather than alleging misconduct. Current deterministic checks include:

- capex acceleration and simple-FCF pressure;
- cash-conversion divergence;
- standardized fact gaps;
- cash-flow classification effects supported by filing notes;
- evidence coverage, filing identity and fact provenance.

For MSFT, the prebuilt pack presents finance-lease principal as an analytical cash-flow adjustment because the filed principal payment sits in financing cash flow and is excluded from conventional CFO-minus-capex FCF. The adjustment is clearly labeled as an analytical view, not a restatement.

## Research contract

- Missing or incompatible XBRL facts remain missing.
- Derived metrics use published deterministic formulas.
- User-selected peers are not automatically declared strict comparables.
- Scenario outputs are assumptions, not market data or target prices.
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

This system supports research and review. It does not produce a rating, target price or transaction instruction.
