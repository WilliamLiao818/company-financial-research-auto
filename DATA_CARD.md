# Data card

- Supported source families: U.S. Securities and Exchange Commission filings and Company Facts; Financial Modeling Prep annual statements when a user supplies a key; dated public market-share and target-price sources.
- Prebuilt coverage: Microsoft, Oracle, Alphabet, Broadcom, Sandisk and NVIDIA; four or five annual periods are available per company.
- Snapshot update date: 2026-08-27.
- Unit: U.S. dollars, as filed in XBRL.
- Input modes: six prebuilt packs, online ticker/CIK through SEC Company Facts, and an in-session provider-key path for other U.S.-listed companies.
- Processing: the preferred supported standard US-GAAP tag is selected first; within a tag and period, the latest-filed annual fact is retained.
- Provenance: SEC rows preserve CIK, XBRL tag, accession, form, filed date and Company Facts URL when available. Provider rows carry statement-period and source-family metadata.
- Derived metrics: growth, margins, simplified free cash flow, capex intensity, cash conversion and a liabilities/assets proxy are deterministic calculations.
- Scenario inputs: growth and entry/exit multiples are user assumptions and are never presented as sourced company facts. Dated institutional targets remain separate from The Company Bear/Base/Bull range.
- Missingness policy: unsupported or absent facts remain null; the connector does not estimate, interpolate or silently substitute company-specific values.
- Retention: user-supplied provider keys are held only in the active Streamlit session and are not written by application code. Hosting-platform logging and retention remain the deployer's responsibility.
- Limitations: company-specific tags, restatements, fiscal calendars and user-supplied CSV quality may affect comparability. Always verify material conclusions against the original filing.
- License/usage: public regulatory filings; this repository stores a normalized factual snapshot and source URLs.
