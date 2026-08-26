# The Company

**Fundamentals & Accounting Quality · Version 2.0**

The Company is an evidence-linked research system for U.S. public-company fundamentals. It separates reported SEC facts, deterministic calculations, accounting-quality signals, analytical normalization and user assumptions.

- **Live application:** [Open The Company](https://company-financial-research-auto.streamlit.app/)
- **Unified research desk:** [Open The Research Desk](https://research-systems-lab.william-liao818.chatgpt.site/)

## Prebuilt research packs

MSFT and ORCL are bundled as verified snapshots and require no API key. Each pack includes:

- an executive thesis and counter-thesis;
- business-model-specific indicators and diligence questions;
- multi-year financial diagnostics;
- deterministic accounting-quality signals;
- reported-to-analytical cash-flow normalization where sourced;
- transparent valuation scenarios;
- a claim-level evidence and review queue;
- PDF, Markdown, fact-ledger and run-record downloads.

## Analyze another U.S. public company

The public SEC connector accepts a ticker or CIK and does not require an API key. SEC availability and an identifiable `SEC_USER_AGENT` are required. Users may also upload a saved SEC Company Facts JSON or a documented same-schema CSV. Uploaded files are processed in session memory and are not written by the application.

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
