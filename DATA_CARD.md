# Data card

- Source: U.S. Securities and Exchange Commission `data.sec.gov` Company Facts API.
- Coverage: Microsoft, Oracle and NVIDIA; five latest fiscal years available in the snapshot.
- Capture date: 2026-08-24.
- Unit: U.S. dollars, as filed in XBRL.
- Processing: the latest filed annual fact for each fiscal year is selected from standard US-GAAP tags.
- Derived metrics: growth, margins, simplified free cash flow, capex intensity, cash conversion and a liabilities/assets proxy are deterministic calculations.
- Scenario inputs: growth, entry/exit multiples and net debt are user assumptions and are never presented as sourced company facts.
- Limitations: company-specific tags, restatements and fiscal-calendar differences may affect comparability. Always verify material conclusions against the original filing.
- License/usage: public regulatory filings; this repository stores a normalized factual snapshot and source URLs.
