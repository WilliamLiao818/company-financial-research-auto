# Data card

- Supported source family: U.S. Securities and Exchange Commission Company Facts, plus a documented same-schema CSV supplied by the user.
- Frozen demo coverage: Microsoft, Oracle and NVIDIA; five fiscal years available in the repository snapshot.
- Frozen demo capture date: 2026-08-24.
- Unit: U.S. dollars, as filed in XBRL.
- Input modes: frozen demo, online ticker/CIK, in-memory SEC Company Facts JSON upload, and in-memory financial CSV upload.
- Processing: the preferred supported standard US-GAAP tag is selected first; within a tag and period, the latest-filed annual fact is retained.
- Provenance: online/JSON rows preserve CIK, XBRL tag, accession, form, filed date and Company Facts URL when available. Same-schema CSV provenance is limited to fields supplied by the user.
- Derived metrics: growth, margins, simplified free cash flow, capex intensity, cash conversion and a liabilities/assets proxy are deterministic calculations.
- Scenario inputs: growth, entry/exit multiples and net debt are user assumptions and are never presented as sourced company facts.
- Missingness policy: unsupported or absent facts remain null; the connector does not estimate, interpolate or silently substitute company-specific values.
- Retention: uploaded bytes are parsed from Streamlit memory objects and are not written by application code. Hosting-platform logging and retention remain the deployer's responsibility.
- Limitations: company-specific tags, restatements, fiscal calendars and user-supplied CSV quality may affect comparability. Always verify material conclusions against the original filing.
- License/usage: public regulatory filings; this repository stores a normalized factual snapshot and source URLs.
